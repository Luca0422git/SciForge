# SPDX-License-Identifier: LGPL-2.1-or-later
"""The rules of SciForge's crash log, without FreeCAD and without Qt (unit tested:
SciForgeTests/unit/test_crashlog_core.py). crashlog.py is the part that switches it on.

How it works, in plain words
  * Every start of SciForge makes two small files in <user data>/SciForge/crash/:
      session-<date>-<time>-<process number>.log   where Python's faulthandler writes what
                                                   it knows if SciForge crashes, and where
                                                   uncaught Python errors are written;
      running-<same name>.json                     the "session running" marker.
  * A clean exit removes the marker, and the log too when nothing was written to it (so the
    handful of logs kept are the ones that matter).
  * At the next start a marker whose process is gone means the last session ended without a
    clean exit (a crash, a kill, a power cut): "SciForge closed unexpectedly last time".
    A marker whose process still runs is another SciForge window open at the same time and
    is left alone.
  * Only the newest KEEP logs are kept (the older ones are deleted).

Nothing here raises: every function answers a plain value for a missing or unreadable
folder, so the crash log can never stop SciForge from starting.
"""

import json
import os
import re
import sys
import time

KEEP = 5  # session logs kept
TAIL_LINES = 300  # lines of a crash log a report carries
LOG_PREFIX, LOG_SUFFIX = "session-", ".log"
MARKER_PREFIX, MARKER_SUFFIX = "running-", ".json"
_ID = re.compile(r"^[0-9]{8}-[0-9]{6}-[0-9]+$")


# -- names -------------------------------------------------------------------------------
def folder_in(user_data):
    """<user data>/SciForge/crash"""
    return os.path.join(user_data, "SciForge", "crash")


def session_id(now, pid):
    """ "20261020-153012-4242": the start time (local) and the process number. Sorts by
    time as text, and two windows started in the same second still differ."""
    return "%s-%d" % (time.strftime("%Y%m%d-%H%M%S", time.localtime(now)), int(pid))


def log_name(sid):
    return LOG_PREFIX + sid + LOG_SUFFIX


def marker_name(sid):
    return MARKER_PREFIX + sid + MARKER_SUFFIX


def id_of(name):
    """The session id in a log or marker file name, or None for any other file."""
    try:
        for prefix, suffix in ((LOG_PREFIX, LOG_SUFFIX), (MARKER_PREFIX, MARKER_SUFFIX)):
            if name.startswith(prefix) and name.endswith(suffix):
                sid = name[len(prefix) : len(name) - len(suffix)]
                return sid if _ID.match(sid) else None
    except Exception:
        pass
    return None


def when_text(sid):
    """ "2026-10-20 15:30:12" for a session id (or the id itself when it is not one)."""
    try:
        day, clock, _pid = sid.split("-")
        return "%s-%s-%s %s:%s:%s" % (
            day[:4],
            day[4:6],
            day[6:],
            clock[:2],
            clock[2:4],
            clock[4:],
        )
    except Exception:
        return str(sid)


# -- is that process still running? -----------------------------------------------------------
def pid_alive(pid):
    """True when a process with this number is running. Junk gives False. When the answer
    cannot be found out (access denied, an unexpected error) it says True: a missing "closed
    unexpectedly" line is better than a false one."""
    try:
        pid = int(pid)
    except Exception:
        return False
    if pid <= 0:
        return False
    if pid == os.getpid():
        return True
    try:
        if sys.platform.startswith("win"):
            return _windows_alive(pid)
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except Exception:
        return True


def _windows_alive(pid):
    import ctypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    kernel.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.OpenProcess(0x1000, 0, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        # 5 = access denied: the process exists; 87 = invalid parameter: it does not
        return ctypes.get_last_error() != 87
    try:
        code = ctypes.c_ulong()
        if kernel.GetExitCodeProcess(handle, ctypes.byref(code)):
            return code.value == 259  # STILL_ACTIVE
        return True
    finally:
        kernel.CloseHandle(handle)


# -- one session ------------------------------------------------------------------------------
def begin(folder, now, pid, version=""):
    """Make the folder, the marker and the (empty) log of a session that starts now.
    Returns {"id", "log", "marker"}, or None when the folder cannot be written."""
    try:
        os.makedirs(folder, exist_ok=True)
        sid = session_id(now, pid)
        log = os.path.join(folder, log_name(sid))
        marker = os.path.join(folder, marker_name(sid))
        with open(log, "a", encoding="utf-8"):
            pass
        with open(marker, "w", encoding="utf-8") as handle:
            json.dump(
                {"id": sid, "pid": int(pid), "started": float(now), "version": str(version)},
                handle,
            )
        return {"id": sid, "log": log, "marker": marker}
    except Exception:
        return None


def end(folder, sid):
    """A clean exit: remove the marker; remove the log too when nothing was written to it.
    Returns True when the log was kept (it holds something)."""
    kept = False
    try:
        marker = os.path.join(folder, marker_name(sid))
        if os.path.isfile(marker):
            os.remove(marker)
    except Exception:
        pass
    try:
        log = os.path.join(folder, log_name(sid))
        if os.path.isfile(log):
            if os.path.getsize(log) == 0:
                os.remove(log)
            else:
                kept = True
    except Exception:
        pass
    return kept


def _read_marker(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def stale_sessions(folder, alive=pid_alive):
    """The sessions whose marker is still there although their process is gone (they did not
    end cleanly), oldest first: [{"id", "when", "pid", "version", "marker", "log",
    "log_size"}]. `alive` is a function (pid) -> bool (a test passes its own)."""
    found = []
    try:
        names = sorted(os.listdir(folder))
    except Exception:
        return found
    for name in names:
        try:
            if not (name.startswith(MARKER_PREFIX) and name.endswith(MARKER_SUFFIX)):
                continue
            sid = id_of(name)
            if sid is None:
                continue
            path = os.path.join(folder, name)
            data = _read_marker(path)
            pid = data.get("pid")
            if pid is not None and alive(pid):
                continue  # another SciForge window, still open
            log = os.path.join(folder, log_name(sid))
            size = os.path.getsize(log) if os.path.isfile(log) else 0
            found.append(
                {
                    "id": sid,
                    "when": when_text(sid),
                    "pid": pid,
                    "version": str(data.get("version", "")),
                    "marker": path,
                    "log": log if os.path.isfile(log) else "",
                    "log_size": size,
                }
            )
        except Exception:
            continue
    return found


def dismiss(folder, sessions):
    """Take the notice away: remove those sessions' markers, and their log when it is empty
    (a log with a crash in it stays, for Report a Problem)."""
    for entry in sessions:
        try:
            if os.path.isfile(entry["marker"]):
                os.remove(entry["marker"])
        except Exception:
            pass
        try:
            log = entry.get("log")
            if log and os.path.isfile(log) and os.path.getsize(log) == 0:
                os.remove(log)
        except Exception:
            pass


# -- the logs kept ------------------------------------------------------------------------------
def logs(folder):
    """[(session id, path)] of the session logs, oldest first."""
    found = []
    try:
        for name in sorted(os.listdir(folder)):
            sid = id_of(name)
            if sid is not None and name.startswith(LOG_PREFIX):
                found.append((sid, os.path.join(folder, name)))
    except Exception:
        pass
    return found


def rotate(folder, keep=KEEP, protect=()):
    """Delete all but the newest `keep` session logs (never one named in `protect`: the
    running session and sessions with an unanswered notice). Returns the names deleted."""
    deleted = []
    try:
        everything = logs(folder)
        for sid, path in everything[: max(0, len(everything) - keep)]:
            if sid in protect:
                continue
            try:
                os.remove(path)
                deleted.append(os.path.basename(path))
            except Exception:
                pass
    except Exception:
        pass
    return deleted


def last_crash_log(folder, exclude=()):
    """The newest session log that has something in it (not the running session's, not one
    named in `exclude`): (session id, path), or None."""
    try:
        for sid, path in reversed(logs(folder)):
            if sid in exclude:
                continue
            if os.path.getsize(path) > 0:
                return sid, path
    except Exception:
        pass
    return None


def tail(path, lines=TAIL_LINES, max_bytes=400000):
    """The last `lines` lines of a text file ("" when it cannot be read). Only the end of a
    big file is read."""
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as handle:
            if size > max_bytes:
                handle.seek(size - max_bytes)
            data = handle.read()
        text = data.decode("utf-8", errors="replace")
        rows = text.splitlines()
        return "\n".join(rows[-lines:])
    except Exception:
        return ""
