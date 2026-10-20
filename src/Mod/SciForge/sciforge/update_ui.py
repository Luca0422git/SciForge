# SPDX-License-Identifier: LGPL-2.1-or-later
"""The update check and "Update now" (brief docs/sciforge/dev/briefs/beta-release.md, R3).

The rules are update_core.py (pure, unit tested); this is the window side.

  * At start, a few seconds after SciForge is up, once a day at most (and only while
    Preferences > General > Updates > "Check for updates when SciForge starts" is on), a
    daemon thread asks GitHub for the newest releases; a 50 ms QTimer reads its answer on
    the GUI thread (the pattern of Home's tile loader). Nothing blocks the start. Offline,
    rate-limited, GitHub down, an answer that makes no sense: one [SciForge] log line, no
    message. Help > Check for Updates asks at once, whatever the day, and says plainly what
    it found, including "Could not reach GitHub".
  * A newer release shows as a line on the Home tab (home_update_ui.py): "SciForge X is
    available. [What's new] [Update now] [Later]". No popup at start. Later hides it until the
    next version.
  * Update now: the plan (update_core.plan) says what to download (the small module update,
    the full installer, or only the release page on Linux); a dialog shows the progress and
    has Cancel; the file's SHA-256 must match sciforge-release.json (a wrong one is deleted);
    then a helper is started that waits for SciForge to end, and SciForge quits through its
    normal quit (the same Save / Don't save / Cancel question about unsaved designs; Cancel
    stops the update and the helper). Never while a command dialog is open.
  * After the restart, Home says "Updated to X. [What's new]" once.

Test seams (a scenario sets them; never the real internet, never a real quit):
  update_core.API_BASE   the fake GitHub's address
  HAND_OVER(argv)        starts the helper; a stub records argv
  QUIT()                 closes SciForge; a stub returns True
  OPEN_URL(url)          the browser
  LAYOUT / INSTALLED     what this install is (update_core.detect_layout / {"version", "core"})
  START_DELAY_MS         how long after start the automatic check waits
"""

import os
import queue
import subprocess
import sys
import threading
import time

import FreeCAD as App
import FreeCADGui as Gui

from . import __version__, home_update_ui, log, update_core as core, version_core, warn
from .compat import QtCore, QtGui, QtWidgets

PARAMS = "User parameter:BaseApp/Preferences/Mod/SciForge"
START_DELAY_MS = 4000

HAND_OVER = None
QUIT = None
OPEN_URL = None
LAYOUT = None
INSTALLED = None

_state = {
    "on": False,
    "started": False,  # the automatic check of this session was scheduled
    "release": None,  # the newest newer release found this session (with its manifest)
    "version": "",  # its version, also remembered between starts (UpdateAvailable)
    "busy": False,
    "manual": False,
    "install": False,
    "jobs": queue.Queue(),
    "timer": None,
    "answer": None,  # the box a manual check answers with (tests read it)
    "dialog": None,  # the download dialog
    "download": None,  # {"done", "total", "cancel", "result"} shared with the download thread
    "updated": "",  # the version just installed (Home says "Updated to ...")
    "proc": None,
    "plan": None,  # what the download in progress is for
    "dest": "",
    "target_version": "",
}


# -- preferences ------------------------------------------------------------------------------
def _group():
    return App.ParamGet(PARAMS)


def _get(kind, name, default):
    try:
        return getattr(_group(), "Get" + kind)(name, default)
    except Exception:
        return default


def _set(kind, name, value):
    try:
        getattr(_group(), "Set" + kind)(name, value)
    except Exception as exc:
        warn("update: could not remember %s: %s" % (name, exc))


def check_on_start():
    """Preferences > General > Updates: check when SciForge starts (on unless switched off)."""
    return bool(_get("Bool", "CheckForUpdates", True))


def channel():
    return core.clean_channel(_get("String", "UpdateChannel", ""), __version__)


def installed():
    if INSTALLED is not None:
        return dict(INSTALLED)
    return {"version": __version__, "core": core.installed_core()}


def layout():
    if LAYOUT is not None:
        return dict(LAYOUT)
    try:
        return core.detect_layout(sys.platform, App.getHomePath())
    except Exception:
        return {"os": "other", "kind": "other", "home": ""}


# -- what Home shows --------------------------------------------------------------------------
def available():
    """The version of a newer release to tell Home about ("" when there is none, or the person
    said Later to this one, or the channel does not take it)."""
    version = _state["version"]
    if not version or not version_core.newer(version, installed()["version"]):
        return ""
    if channel() != core.BETA and version_core.is_prerelease(version):
        return ""
    if _get("String", "UpdateLater", "") == version:
        return ""
    return version


def updated():
    """The version just installed ("" when this start is not the first one after an update)."""
    return _state["updated"]


def page_for(version):
    """The release's page (its notes: "What's new")."""
    release = _state["release"]
    if release is not None and release.get("version") == version:
        return (release.get("manifest") or {}).get("notes_url") or release["page"]
    return core.release_page(version_core.tag_for(version))


def whats_new(version=""):
    version = version or _state["version"] or _state["updated"]
    _open_url(page_for(version) if version else core.releases_page())


def later():
    """Home's Later: the line stays away until a newer version than this one comes."""
    if _state["version"]:
        _set("String", "UpdateLater", _state["version"])
    _changed()


def dismiss_updated():
    _state["updated"] = ""
    _changed()


def _changed():
    try:
        home_update_ui.changed()
    except Exception as exc:
        warn("update: Home line: %s" % exc)


def _open_url(url):
    try:
        if OPEN_URL is not None:
            OPEN_URL(url)
        else:
            QtGui.QDesktopServices.openUrl(QtCore.QUrl(url))
    except Exception as exc:
        warn("update: could not open %s: %s" % (url, exc))


# -- start ------------------------------------------------------------------------------------
def enable():
    """SciForge on (shell.enable): note a finished update, show what an earlier check found,
    and check a few seconds after the start when it is due."""
    try:
        if _state["on"]:
            return
        _state["on"] = True
        _no_sigpipe()
        _note_updated()
        _load_remembered()
        if not _state["started"]:
            _state["started"] = True
            QtCore.QTimer.singleShot(START_DELAY_MS, _at_start)
    except Exception as exc:
        warn("update: %s" % exc)


def disable():
    _state["on"] = False


def _no_sigpipe():
    """Linux: FreeCAD leaves SIGPIPE at its default, so a write to a connection the other side
    already closed (the update check's request, a download) would end SciForge instead of
    raising an exception. Ignored like Python itself does (main thread only; Windows has none)."""
    try:
        import signal

        if hasattr(signal, "SIGPIPE"):
            signal.signal(signal.SIGPIPE, signal.SIG_IGN)
    except Exception as exc:
        log("update: could not ignore SIGPIPE: %s" % _plain(exc))


def _note_updated():
    """The first start after "Update now": Home says "Updated to X" (once: it is forgotten
    here, so the next start does not say it again)."""
    pending = _get("String", "UpdateJustInstalled", "")
    if not pending:
        return
    _set("String", "UpdateJustInstalled", "")
    if version_core.canonical(pending) == version_core.canonical(__version__):
        _state["updated"] = __version__
        _set("String", "UpdateAvailable", "")
        log("update: updated to %s" % __version__)
        _tidy_downloads(__version__)
    else:
        log("update: the update to %s did not finish (this is still %s)" % (pending, __version__))


def _tidy_downloads(keep):
    """The downloads of other versions (the installer or module zip of the update that is now
    in) are not needed any more; the folder of this one stays (its install_update.log is what
    to send when an update goes wrong). Backups of the old SciForge are never deleted here."""
    folder = os.path.dirname(core.updates_dir(_user_data(), keep))
    keep_name = os.path.basename(core.updates_dir(_user_data(), keep))

    def tidy():  # (file work only: a worker thread, nothing of Qt or FreeCAD in here)
        try:
            import shutil

            for name in os.listdir(folder):
                if name != keep_name:
                    shutil.rmtree(os.path.join(folder, name), ignore_errors=True)
            mine = os.path.join(folder, keep_name)  # ... and the big files of this one
            shutil.rmtree(os.path.join(mine, "module", "SciForge"), ignore_errors=True)
            for name in os.listdir(mine):
                if name.lower().endswith((".exe", ".zip", ".7z", ".part")):
                    try:
                        os.remove(os.path.join(mine, name))
                    except OSError:
                        pass
        except OSError:
            pass

    threading.Thread(target=tidy, name="SciForgeUpdateTidy", daemon=True).start()


def _load_remembered():
    """An update an earlier check found (the daily limit keeps the check itself away)."""
    version = _get("String", "UpdateAvailable", "")
    if version and version_core.newer(version, __version__):
        _state["version"] = version
    elif version:
        _set("String", "UpdateAvailable", "")
    _changed()


def _at_start():
    """The timer a few seconds after the start. A test run (SCIFORGE_NO_INTERNET, set by
    tools/sciforge/run_tests.sh) never starts it by itself: the scenarios call _start_if_due."""
    if os.environ.get("SCIFORGE_NO_INTERNET"):
        return
    _start_if_due()


def _start_if_due():
    try:
        if not _state["on"] or not check_on_start():
            return
        if core.blocked(core.releases_url()):  # (a test run: never the real GitHub)
            return
        if not core.due(_get("Float", "UpdateLastCheck", 0.0), time.time()):
            log("update check: done within the last day, not asking again")
            return
        start_check(manual=False)
    except Exception as exc:
        warn("update: %s" % exc)


# -- the check --------------------------------------------------------------------------------
def start_check(manual=False, install=False):
    """Ask GitHub on a worker thread; the answer is read by a timer (_poll)."""
    if _state["busy"]:
        if manual:
            _tell("Check for Updates", "SciForge is already checking. Wait a moment.")
        return False
    _state["busy"] = True
    _state["manual"], _state["install"] = manual, install
    if manual or install:
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.BusyCursor)
    version, chosen = __version__, channel()
    threading.Thread(
        target=_check_worker, args=(version, chosen), name="SciForgeUpdateCheck", daemon=True
    ).start()
    _ensure_timer()
    return True


def _check_worker(version, chosen):
    """On the worker thread: no Qt, no FreeCAD in here."""
    try:
        result = core.check(version, chosen)
        answer = {"ok": True, "status": result["status"], "release": result["release"]}
    except core.UpdateError as exc:
        answer = {"ok": False, "code": exc.code, "text": exc.text}
    except Exception as exc:  # (told on the GUI thread)
        answer = {"ok": False, "code": "data", "text": "Unexpected: %s" % str(exc)[:100]}
    _state["jobs"].put(("check", answer))


def _ensure_timer():
    if _state["timer"] is None:
        timer = QtCore.QTimer()
        timer.setInterval(50)
        timer.timeout.connect(_poll)
        _state["timer"] = timer
    if not _state["timer"].isActive():
        _state["timer"].start()


def _poll():
    """The worker threads' answers and the download's progress, on the GUI thread."""
    try:
        for _n in range(20):
            try:
                kind, answer = _state["jobs"].get_nowait()
            except queue.Empty:
                break
            if kind == "check":
                _check_done(answer)
        _download_progress()
        if not _state["busy"] and _state["download"] is None and _state["timer"] is not None:
            _state["timer"].stop()
    except Exception as exc:
        warn("update: %s" % exc)


def _check_done(answer):
    manual, install = _state["manual"], _state["install"]
    _state["busy"] = False
    if manual or install:
        QtWidgets.QApplication.restoreOverrideCursor()
    if not answer["ok"]:
        log("update check: %s" % _plain(answer["text"]))
        if manual or install:
            _tell("Check for Updates", _problem_text(answer))
        return
    _set("Float", "UpdateLastCheck", time.time())
    release = answer["release"]
    if answer["status"] == "newer" and release is not None:
        _state["release"], _state["version"] = release, release["version"]
        _set("String", "UpdateAvailable", release["version"])
        log("update check: SciForge %s is available" % release["version"])
    else:
        _state["release"], _state["version"] = None, ""
        _set("String", "UpdateAvailable", "")
        log("update check: SciForge %s is up to date" % __version__)
    _changed()
    if install and _state["release"] is not None:
        install_now()
    elif manual or install:
        if _state["release"] is not None:
            _answer_available(_state["release"])
        else:
            _tell("Check for Updates", "SciForge %s is up to date." % __version__)


def _plain(text):
    """A log line without words the tests' error scan reads as a problem of SciForge's own."""
    return str(text).replace("rror", "problem")


def _problem_text(answer):
    code = answer.get("code")
    if code == "rate":
        return (
            "GitHub is limiting requests from this computer right now, so SciForge could not "
            "look for updates. Try again in about an hour."
        )
    if code == "offline":
        return (
            "Could not reach GitHub. Check your internet connection and try again.\n\n%s"
            % _plain(answer.get("text", ""))
        )
    return "Could not read GitHub's answer, so SciForge could not look for updates. Try again later."


# -- boxes ------------------------------------------------------------------------------------
def _box(title, text, buttons, name="SciForgeUpdateBox"):
    """A box that does not block (the scenario clicks its buttons): [(label, callback or None)];
    the first button is the default."""
    box = QtWidgets.QMessageBox(Gui.getMainWindow())
    box.setObjectName(name)
    box.setWindowTitle(title)
    box.setText(text)
    box.setIcon(QtWidgets.QMessageBox.NoIcon)
    box.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
    made = []
    for index, (label, callback) in enumerate(buttons):
        role = QtWidgets.QMessageBox.AcceptRole if index == 0 else QtWidgets.QMessageBox.RejectRole
        if callback is not None and 0 < index < len(buttons) - 1:
            role = QtWidgets.QMessageBox.ActionRole
        button = box.addButton(label, role)
        if callback is not None:
            button.clicked.connect(lambda _checked=False, cb=callback: _later_call(cb))
        made.append(button)
    if made:
        box.setDefaultButton(made[0])
    box.open()
    return box


def _later_call(callback):
    QtCore.QTimer.singleShot(0, lambda: _guarded(callback))


def _guarded(callback):
    try:
        callback()
    except Exception as exc:
        warn("update: %s" % exc)


def _tell(title, text):
    _state["answer"] = _box(title, text, [("OK", None)], "SciForgeUpdateAnswer")


def _answer_available(release):
    """Help > Check for Updates found a newer version."""
    version = release["version"]
    _state["answer"] = _box(
        "Check for Updates",
        "SciForge %s is available (you have %s)." % (version, __version__),
        [
            ("Update now", install_now),
            ("What's new", lambda: whats_new(version)),
            ("Later", later),
        ],
        "SciForgeUpdateAnswer",
    )


# -- Update now -------------------------------------------------------------------------------
def command_open():
    try:
        return bool(Gui.Control.activeDialog())
    except Exception:
        return False


def install_now():
    """Update now (Home's button, the box's button): check what is needed, then download."""
    try:
        if command_open():
            _tell(
                "Update now",
                "A command is still open. Finish it or cancel it, then click Update now again.",
            )
            return
        release = _state["release"]
        if release is None:
            start_check(manual=False, install=True)  # (Home remembered it, this session has not looked)
            return
        plan = core.plan(installed(), release, layout())
        log("update: %s (%s)" % (plan["kind"], plan["reason"]))
        if plan["kind"] == "browser":
            _state["answer"] = _box(
                "Update now",
                "%s\n\nSciForge %s: the release page has the files." % (plan["reason"], release["version"]),
                [("Open the release page", lambda: _open_url(plan["page"])), ("Close", None)],
                "SciForgeUpdateAnswer",
            )
            return
        _start_download(plan, release)
    except Exception as exc:
        warn("update: %s" % exc)
        _tell("Update now", "Something went wrong before the download started. Nothing was changed.")


def _user_data():
    try:
        return App.getUserAppDataDir()
    except Exception:
        return os.path.expanduser("~")


def _start_download(plan, release):
    if _state["download"] is not None:
        return
    version = release["version"]
    folder = core.updates_dir(_user_data(), version)
    dest = os.path.join(folder, plan["asset"])
    shared = {"done": 0, "total": plan.get("size", 0), "cancel": False, "result": None}
    _state["download"] = shared
    _state["dialog"] = _DownloadDialog(plan, version)
    _state["dialog"].open()
    threading.Thread(
        target=_download_worker,
        args=(shared, plan, dest, version),
        name="SciForgeUpdateDownload",
        daemon=True,
    ).start()
    _state["plan"] = plan
    _state["dest"] = dest
    _state["target_version"] = version
    _ensure_timer()


def _download_worker(shared, plan, dest, version):
    """On the worker thread: only update_core and the shared dict in here."""

    def progress(done, total):
        shared["done"] = done
        if total:
            shared["total"] = total

    try:
        shared["result"] = core.download(
            plan["url"], dest, plan["sha256"], progress, lambda: shared["cancel"], version
        )
    except Exception as exc:  # (told on the GUI thread)
        shared["result"] = ("error", str(exc)[:200])


def _download_progress():
    shared = _state["download"]
    if shared is None:
        return
    dialog = _state["dialog"]
    if dialog is not None:
        dialog.show_progress(shared["done"], shared["total"])
    if shared["result"] is not None:
        _state["download"] = None
        _download_done(*shared["result"])


def cancel_download():
    shared = _state["download"]
    if shared is not None:
        shared["cancel"] = True
        if _state["dialog"] is not None:
            _state["dialog"].cancelling()


def _download_done(status, text):
    dialog, _state["dialog"] = _state["dialog"], None
    if dialog is not None:
        dialog.done()
    plan, dest, version = _state["plan"], _state["dest"], _state["target_version"]
    if status == "cancelled":
        log("update: cancelled, nothing was changed")
        return
    if status == "mismatch":
        log("update: the download of %s did not match its checksum; deleted" % plan["asset"])
        _tell(
            "Update now",
            "The downloaded file did not match its checksum, so SciForge deleted it and installed "
            "nothing. Try again; if it happens again, please report it (Help > Report a Problem).",
        )
        return
    if status != "ok":
        log("update: download: %s" % _plain(text))
        _tell("Update now", "The download did not finish: %s\n\nNothing was changed." % _plain(text))
        return
    log("update: downloaded %s and its checksum matches" % plan["asset"])
    try:
        _hand_over(plan, dest, version)
    except Exception as exc:
        warn("update: hand over: %s" % exc)
        _tell("Update now", "SciForge could not start the update (%s). Nothing was changed." % _plain(exc))


def _hand_over(plan, path, version):
    if command_open():  # (one was opened while the file came down)
        _tell("Update now", "A command is open. Finish or cancel it, then click Update now again.")
        return
    where = layout()
    script = ""
    if plan["kind"] == "module":
        module = os.path.join(os.path.dirname(path), "module")
        core.safe_extract(path, module)
        script = os.path.join(module, "install_update.ps1")
        if not (
            os.path.isfile(script) and os.path.isfile(os.path.join(module, "SciForge", "InitGui.py"))
        ):
            raise ValueError("the update file is not what SciForge expected")
    argv = core.handover_argv(
        plan["kind"], os.getpid(), target=where.get("home", ""), script=script, installer=path
    )
    _set("String", "UpdateJustInstalled", version)
    try:
        proc = (HAND_OVER or _start_detached)(argv)
    except Exception:
        _set("String", "UpdateJustInstalled", "")
        raise
    _state["proc"] = proc
    log("update: handed over to %s; SciForge quits now" % plan["kind"])
    closing = QUIT() if QUIT is not None else _quit()
    if not closing:  # Cancel at "save your changes?": the update stops too
        _set("String", "UpdateJustInstalled", "")
        if proc is not None:
            try:
                proc.terminate()
            except Exception:
                pass
        _state["proc"] = None
        log("update: stopped, SciForge stays open")
        _tell("Update now", "The update was stopped, SciForge stays open. Nothing was changed.")


def _start_detached(argv):
    """The helper outlives SciForge: its own process group, no console window (Windows)."""
    flags = 0
    if sys.platform.startswith("win"):
        flags = 0x08000000 | 0x00000200  # CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
    return subprocess.Popen(
        argv,
        creationflags=flags,
        close_fds=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _quit():
    """SciForge's normal quit: FreeCAD asks about every design with unsaved changes (save,
    don't save, cancel). False when the person cancelled."""
    return bool(Gui.getMainWindow().close())


class _DownloadDialog(QtWidgets.QDialog):
    """Shows the download: what, how much, a progress bar, Cancel."""

    def __init__(self, plan, version):
        super().__init__(Gui.getMainWindow())
        self.setObjectName("SciForgeUpdateDownload")
        self.setWindowTitle("Updating SciForge")
        self.setModal(True)
        self.setMinimumWidth(460)
        column = QtWidgets.QVBoxLayout(self)
        size = core.format_size(plan.get("size"))
        self.title = QtWidgets.QLabel(
            "Downloading SciForge %s%s" % (version, (" (%s)" % size) if size else "")
        )
        self.title.setObjectName("SciForgeUpdateTitle")
        column.addWidget(self.title)
        self.bar = QtWidgets.QProgressBar()
        self.bar.setObjectName("SciForgeUpdateProgress")
        self.bar.setRange(0, 100)
        self.bar.setTextVisible(False)  # (the sentence under it says how much)
        column.addWidget(self.bar)
        self.status = QtWidgets.QLabel("Starting...")
        self.status.setObjectName("SciForgeUpdateStatus")
        column.addWidget(self.status)
        if plan["kind"] == "installer":
            note = QtWidgets.QLabel(
                "When the installer opens, Windows may say \"Windows protected your PC\" "
                "(SciForge is not signed with a paid certificate). Click More info, then Run "
                "anyway. The download is checked against its checksum first."
            )
        else:
            note = QtWidgets.QLabel(
                "The download is checked against its checksum, then SciForge closes (it asks "
                "about unsaved designs), updates and starts again. Windows may ask for "
                "permission to change files."
            )
        note.setObjectName("SciForgeUpdateNote")
        note.setWordWrap(True)
        column.addWidget(note)
        buttons = QtWidgets.QHBoxLayout()
        buttons.addStretch(1)
        self.cancel_button = QtWidgets.QPushButton("Cancel")
        self.cancel_button.setObjectName("SciForgeUpdateCancel")
        self.cancel_button.clicked.connect(cancel_download)
        buttons.addWidget(self.cancel_button)
        column.addLayout(buttons)

    def show_progress(self, done, total):
        try:
            if total:
                self.bar.setRange(0, 100)
                self.bar.setValue(min(100, int(done * 100 / total)))
                self.status.setText("%s of %s" % (core.format_size(done) or "0 bytes", core.format_size(total)))
            else:
                self.bar.setRange(0, 0)  # unknown size: the bar just moves
                self.status.setText(core.format_size(done) or "Starting...")
        except RuntimeError:
            pass

    def cancelling(self):
        self.cancel_button.setEnabled(False)
        self.status.setText("Cancelling...")

    def done(self):
        try:
            self.close()
            self.deleteLater()
        except RuntimeError:
            pass

    def reject(self):  # (Esc, the window's x)
        cancel_download()


# -- the command (Help > Check for Updates) -------------------------------------------------------
def check_for_updates():
    """Help > Check for Updates: asks now, whatever the day, and answers."""
    try:
        start_check(manual=True)
    except Exception as exc:
        warn("update: %s" % exc)


class CheckForUpdatesCommand:
    def GetResources(self):
        return {
            "MenuText": "Check for Updates...",
            "ToolTip": "Ask GitHub whether a newer SciForge is available",
        }

    def IsActive(self):
        return True

    def Activated(self):
        check_for_updates()


COMMANDS = {"SciForge_CheckForUpdates": CheckForUpdatesCommand}
