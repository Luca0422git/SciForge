# SPDX-License-Identifier: LGPL-2.1-or-later
"""SciForge's crash log (brief docs/sciforge/dev/briefs/beta-release.md, R2).

start() runs first thing when FreeCAD's window starts (InitGui.py). It
  * writes what Python's faulthandler knows into <user data>/SciForge/crash/session-*.log if
    SciForge crashes (a segmentation fault, an abort: the stack of every thread),
  * also writes uncaught Python errors there (sys.excepthook and threading.excepthook are
    chained: the earlier hook still runs) and into SciForge's recent messages,
  * keeps a "session running" marker that a clean exit removes, so the next start can say
    "SciForge closed unexpectedly last time" (Home shows that line: home_notices_ui),
  * keeps the newest 5 logs.
The rules are in crashlog_core.py. Nothing here may stop SciForge from starting or raise:
a folder that cannot be written gives one [SciForge] warning and no crash log.
"""

import atexit
import faulthandler
import os
import sys
import threading
import time
import traceback

from . import __version__, _remember, log, warn
from . import crashlog_core as core

_state = {
    "started": False,
    "folder": None,
    "session": None,  # {"id", "log", "marker"}
    "file": None,
    "crashed": [],  # the sessions that did not end cleanly (until Dismiss)
    "old_excepthook": None,
    "old_thread_hook": None,
    "ended": False,
}


def folder():
    """<user data>/SciForge/crash (a test may set _state["folder"] to a scratch folder)."""
    if _state["folder"]:
        return _state["folder"]
    import FreeCAD as App

    return core.folder_in(App.getUserAppDataDir())


def start():
    """Switch the crash log on (once). Never raises."""
    if _state["started"]:
        return
    _state["started"] = True
    try:
        where = folder()
        # the sessions the last run(s) left behind, before this session makes its own marker
        _state["crashed"] = core.stale_sessions(where)
        session = core.begin(where, time.time(), os.getpid(), __version__)
        if session is None:
            warn("crash log: the folder %s cannot be written, no crash log this time" % where)
            return
        _state["session"] = session
        _state["session_folder"] = where  # (folder() may be pointed elsewhere by a test)
        protect = {s["id"] for s in _state["crashed"]} | {session["id"]}
        core.rotate(where, core.KEEP, protect)
        handle = open(session["log"], "a", encoding="utf-8", buffering=1)
        _state["file"] = handle
        try:
            faulthandler.enable(file=handle, all_threads=True)
        except Exception as exc:
            warn("crash log: faulthandler could not be switched on: %s" % exc)
        _state["old_excepthook"] = sys.excepthook
        sys.excepthook = _excepthook
        if hasattr(threading, "excepthook"):
            _state["old_thread_hook"] = threading.excepthook
            threading.excepthook = _thread_hook
        atexit.register(end)
        _connect_quit()
        note = ""
        if _state["crashed"]:
            note = " (the last session did not end cleanly)"
        log("crash log: %s%s" % (session["log"], note))
    except Exception as exc:
        warn("crash log: %s" % exc)


def _connect_quit():
    """Qt's aboutToQuit: the clean exit of the window (atexit is the second chance)."""
    try:
        from .compat import QtWidgets

        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(end)
    except Exception as exc:
        warn("crash log: cannot follow the exit: %s" % exc)


def end():
    """A clean exit: the marker goes, an empty log goes. Safe to call twice."""
    try:
        if _state["ended"] or _state["session"] is None:
            return
        _state["ended"] = True
        try:
            faulthandler.disable()
        except Exception:
            pass
        handle, _state["file"] = _state["file"], None
        if handle is not None:
            try:
                handle.close()
            except Exception:
                pass
        if sys.excepthook is _excepthook:
            sys.excepthook = _state["old_excepthook"] or sys.__excepthook__
        if hasattr(threading, "excepthook") and threading.excepthook is _thread_hook:
            threading.excepthook = _state["old_thread_hook"] or threading.__excepthook__
        core.end(_state.get("session_folder") or folder(), _state["session"]["id"])
    except Exception:
        pass


def _write(text):
    handle = _state["file"]
    if handle is None:
        return
    handle.write(text)
    handle.flush()


def _excepthook(exc_type, exc_value, exc_tb):
    try:
        text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        _write("[%s] Uncaught Python error\n%s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), text))
        _remember("ERROR", "uncaught %s: %s" % (getattr(exc_type, "__name__", exc_type), exc_value))
    except Exception:
        pass
    old = _state["old_excepthook"] or sys.__excepthook__
    old(exc_type, exc_value, exc_tb)


def _thread_hook(args):
    try:
        text = "".join(
            traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)
        )
        who = getattr(args.thread, "name", "?")
        _write(
            "[%s] Uncaught Python error in thread %s\n%s\n"
            % (time.strftime("%Y-%m-%d %H:%M:%S"), who, text)
        )
        _remember(
            "ERROR", "uncaught %s in thread %s: %s" % (args.exc_type.__name__, who, args.exc_value)
        )
    except Exception:
        pass
    old = _state["old_thread_hook"]
    if old is not None:
        old(args)


# -- what the rest of SciForge asks ---------------------------------------------------------
def rescan():
    """Look at the folder again for sessions that did not end cleanly (start() does it once;
    tests and a second look use this). Returns the list."""
    try:
        _state["crashed"] = core.stale_sessions(folder())
    except Exception as exc:
        warn("crash log: %s" % exc)
        _state["crashed"] = []
    return list(_state["crashed"])


def pending():
    """The sessions that did not end cleanly and whose notice nobody has answered yet."""
    return list(_state["crashed"])


def dismiss():
    """The notice is answered: their markers go (a log with something in it stays, for
    Report a Problem)."""
    try:
        core.dismiss(folder(), _state["crashed"])
    except Exception as exc:
        warn("crash log: %s" % exc)
    _state["crashed"] = []


def last_crash_log():
    """(session id, path) of the newest earlier session log with something in it, or None."""
    try:
        own = _state["session"]["id"] if _state["session"] else ""
        return core.last_crash_log(folder(), exclude=(own,))
    except Exception:
        return None


def tail(path, lines=core.TAIL_LINES):
    return core.tail(path, lines)
