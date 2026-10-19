# SPDX-License-Identifier: LGPL-2.1-or-later
"""The AI bridge inside SciForge (brief home-cloud-ai.md section 4.3, milestone M3).

When Preferences > AI > "Allow AI apps to control SciForge" is on (off by default), SciForge
listens on 127.0.0.1 only, at a random port, and writes <user data>/SciForge/ai/bridge.json
with that port and a random key (bridge_core.py). The MCP server an AI app starts
(sciforge_mcp.py) sends each tool call there.

A call arrives on the server's thread and waits; the work happens on SciForge's own (GUI)
thread, where FreeCAD may be touched: a timer takes the calls one by one. Every call that
changes the design is one Undo step ("AI: Extrude 10 mm"), built with the same code as the
golden models and the dialogs (sciforge/ai/ops). Safety:
  * the first call of a session asks the person in SciForge: Allow / Deny;
  * while a SciForge dialog or a sketch is open, changing calls answer "SciForge is busy";
  * overwriting a file always asks the person; there is no "run any code" tool;
  * every call is listed in the AI activity panel (with Undo and Stop).
"""

import base64
import http.server
import os
import queue
import tempfile
import threading
import time

import FreeCAD as App
import FreeCADGui as Gui

from .. import commands, log, warn
from ..compat import QtCore, QtWidgets
from . import bridge_core, tools_core

OPTION = ("User parameter:BaseApp/Preferences/Mod/SciForge/AI", "AllowControl")
WAIT = 115.0  # seconds a call waits for SciForge (the MCP server waits 120)
ASK = None  # tests: function(title, text) -> True / False instead of the question
VIEWS = {
    "iso": "viewIsometric",
    "front": "viewFront",
    "back": "viewRear",
    "top": "viewTop",
    "bottom": "viewBottom",
    "left": "viewLeft",
    "right": "viewRight",
}
BASE_NAMES = {
    "create_sketch": "Sketch",
    "extrude": "Extrude",
    "revolve": "Revolve",
    "fillet": "Fillet",
    "chamfer": "Chamfer",
    "hole": "Hole",
    "pattern": "Pattern",
    "shell": "Shell",
    "set_parameter": "Parameter",
}

_state = {
    "server": None,
    "thread": None,
    "key": None,
    "file": None,
    "timer": None,
    "jobs": queue.Queue(),
    "consent": None,  # None: not asked this session; True / False: the person's answer
    "running": False,  # a call is being worked on (the questions open nested event loops)
    "activity": [],  # (time, tool, text, is_error)
    "last_used": None,
    "listeners": [],  # functions called after every call (the activity panel, Home)
}
_builders = {}  # document name -> ops Builder attached to it


# -- on / off ----------------------------------------------------------------------------
def allowed():
    path, name = OPTION
    return App.ParamGet(path).GetBool(name, False)


def set_allowed(on):
    path, name = OPTION
    App.ParamGet(path).SetBool(name, bool(on))
    apply()


def running():
    return _state["server"] is not None


def apply():
    """Start or stop the bridge as the option says (Preferences, start-up, Stop)."""
    try:
        if allowed():
            start()
        else:
            stop()
    except Exception as exc:
        warn("AI bridge: %s" % exc)


class _Handler(http.server.BaseHTTPRequestHandler):
    server_version = "SciForge"

    def log_message(self, *_args):
        pass  # (http.server prints every request to stderr; the activity panel lists them)

    def _send(self, status, answer):
        data = bridge_core.encode_result(answer)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        try:
            self._send(404, bridge_core.error_result("not found"))
        except Exception:
            pass

    def do_POST(self):
        try:
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = -1
            status, reason = bridge_core.check_request(
                "POST",
                self.path,
                self.headers.get(bridge_core.KEY_HEADER),
                _state["key"],
                self.headers.get("Origin"),
                length,
            )
            if status != 200:
                self._send(status, bridge_core.error_result(reason))
                return
            try:
                tool, args = bridge_core.decode_request(self.rfile.read(length))
            except bridge_core.BridgeError as exc:
                self._send(400, bridge_core.error_result(str(exc)))
                return
            job = {"tool": tool, "args": args, "done": threading.Event(), "answer": None}
            _state["jobs"].put(job)
            if not job["done"].wait(WAIT):
                job["late"] = True
                self._send(
                    200,
                    bridge_core.error_result(
                        "SciForge is still working on %s (or waiting for the person to answer "
                        "a question in SciForge). Check SciForge before trying again." % tool
                    ),
                )
                return
            self._send(200, job["answer"])
        except Exception:
            pass  # (the connection went away: nothing to answer)


def _ignore_broken_pipes():
    """Linux / macOS: writing an answer to a connection the AI app already closed sends
    SIGPIPE, which ends a program that does not ignore it, and FreeCAD's embedded Python
    does not (ordinary Python does): SciForge was killed, unsaved work and all. Ignored, the
    write fails with an error the handler catches."""
    try:
        import signal

        if hasattr(signal, "SIGPIPE"):
            signal.signal(signal.SIGPIPE, signal.SIG_IGN)
    except (ValueError, OSError) as exc:  # (not the main thread)
        warn("AI bridge: %s" % exc)


def start():
    if running():
        return
    _ignore_broken_pipes()
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    server.daemon_threads = True
    _state["key"] = bridge_core.make_key()
    _state["server"] = server
    _state["thread"] = threading.Thread(
        target=server.serve_forever, name="SciForgeAIBridge", daemon=True
    )
    _state["thread"].start()
    _state["file"] = bridge_core.bridge_path(App.getUserAppDataDir())
    bridge_core.write_bridge_file(
        _state["file"], bridge_core.bridge_info(server.server_address[1], _state["key"])
    )
    if _state["timer"] is None:
        _state["timer"] = QtCore.QTimer()
        _state["timer"].setInterval(50)
        _state["timer"].timeout.connect(_pump)
    _state["timer"].start()
    log("AI bridge on (127.0.0.1, port %d)" % server.server_address[1])


def stop():
    if not running():
        return
    server = _state["server"]
    _state["server"] = None
    try:
        server.shutdown()
        server.server_close()
    except Exception as exc:
        warn("AI bridge: %s" % exc)
    bridge_core.remove_bridge_file(_state["file"], os.getpid())
    while True:  # calls still waiting: answered, not left hanging
        try:
            job = _state["jobs"].get_nowait()
        except queue.Empty:
            break
        _answer(job, bridge_core.error_result(bridge_core.NOT_RUNNING))
    _state["consent"] = None
    log("AI bridge off")


# -- the GUI thread -----------------------------------------------------------------------
def _answer(job, answer):
    job["answer"] = answer
    job["done"].set()


def _pump():
    """Takes the waiting calls one by one (on SciForge's own thread)."""
    if _state["running"]:
        return  # (a question of this call is open: its own event loop calls the timer)
    try:
        job = _state["jobs"].get_nowait()
    except queue.Empty:
        return
    _state["running"] = True
    try:
        answer = call(job["tool"], job["args"])
    except Exception as exc:
        warn("AI bridge: %s: %s" % (job["tool"], exc))
        answer = bridge_core.error_result("SciForge could not do %s: %s" % (job["tool"], exc))
    finally:
        _state["running"] = False
    _answer(job, answer)


def ask(title, text):
    """A yes / no question to the person in SciForge (True = yes)."""
    if ASK is not None:
        return bool(ASK(title, text))
    box = QtWidgets.QMessageBox(Gui.getMainWindow())
    box.setObjectName("SciForgeAIQuestion")
    box.setWindowTitle(title)
    box.setText(text)
    yes = box.addButton("Allow", QtWidgets.QMessageBox.AcceptRole)
    no = box.addButton("Deny", QtWidgets.QMessageBox.RejectRole)
    yes.setObjectName("SciForgeAIAllow")
    no.setObjectName("SciForgeAIDeny")
    box.setDefaultButton(no)
    box.exec_()
    return box.clickedButton() is yes


def _busy():
    """Why SciForge cannot change the design now, or ""."""
    try:
        if Gui.Control.activeDialog():
            return "SciForge is busy: a command dialog is open. Finish or cancel it first."
        gui_doc = Gui.ActiveDocument
        if gui_doc is not None and gui_doc.getInEdit() is not None:
            return "SciForge is busy: something is being edited (a sketch?). Finish it first."
        if QtWidgets.QApplication.activeModalWidget() is not None:
            return "SciForge is busy: a window is waiting for an answer. Close it first."
    except Exception:
        pass
    return ""


def call(tool, args, from_chat=False):
    """One tool call: a result dict (bridge_core.result). from_chat: from SciForge's own chat
    panel, where the person is the one asking (no "Allow this AI app?" question)."""
    problems = tools_core.validate(tool, args)
    if problems:
        return bridge_core.error_result("Not done: " + "; ".join(problems) + ".")
    if not from_chat and _state["consent"] is None:
        _state["consent"] = ask(
            "AI control",
            "An AI app wants to control SciForge (build, change and save designs). Every step "
            "it makes can be undone and is listed in the AI activity panel.\n\nAllow it for "
            "this session?",
        )
        log("AI bridge: the person %s AI control" % ("allowed" if _state["consent"] else "denied"))
    if not from_chat and not _state["consent"]:
        return _record(
            tool,
            bridge_core.error_result(
                "The person using SciForge did not allow AI control in this session."
            ),
        )
    entry = tools_core.tool(tool)
    if entry["changes_design"] or entry.get("writes_files"):
        reason = _busy()
        if reason:
            return _record(tool, bridge_core.error_result(reason))
    handler = {
        "get_design": _get_design,
        "screenshot": _screenshot,
        "measure": _measure,
        "undo": lambda a: _undo_redo("undo"),
        "redo": lambda a: _undo_redo("redo"),
        "save": _save,
        "export": _export,
    }.get(tool)
    try:
        answer = handler(args) if handler is not None else _build(tool, args)
    except Exception as exc:
        warn("AI bridge: %s: %s" % (tool, exc))
        answer = bridge_core.error_result("Not done: %s" % exc)
    return _record(tool, answer)


def _record(tool, answer):
    stamp = time.time()
    _state["activity"].append((stamp, tool, answer["text"], answer["is_error"]))
    del _state["activity"][:-200]
    _state["last_used"] = stamp
    for listener in list(_state["listeners"]):
        try:
            listener()
        except Exception as exc:
            warn("AI bridge: %s" % exc)
    return answer


def activity():
    return list(_state["activity"])


def last_used():
    return _state["last_used"]


def add_listener(fn):
    if fn not in _state["listeners"]:
        _state["listeners"].append(fn)


# -- the design ---------------------------------------------------------------------------------
def _doc(create=False):
    doc = App.ActiveDocument
    if doc is None and create:
        doc = App.newDocument("Untitled")
        commands.ensure_body()
        log("AI bridge: new design %s" % doc.Name)
    return doc


def _builder(doc):
    from .ops import core

    body = commands.find_body() or commands.ensure_body()
    builder = _builders.get(doc.Name)
    if builder is None or builder.doc is not doc:
        builder = _builders[doc.Name] = core.Builder.attach(doc, body)
    else:
        builder.learn()
        if body is not None:
            builder.body = body
    return builder


def _new_id(doc, builder, tool):
    base = BASE_NAMES.get(tool, "Step")
    taken = {o.Name for o in doc.Objects} | {o.Label for o in doc.Objects} | set(builder.objects)
    n = 1
    while "%s%d" % (base, n) in taken:
        n += 1
    return "%s%d" % (base, n)


def _build(tool, args):
    doc = _doc(create=True)
    builder = _builder(doc)
    step_id = _new_id(doc, builder, tool)
    steps = tools_core.to_steps(tool, args, step_id)
    title = tools_core.step_title(tool, args)
    doc.openTransaction(title)
    try:
        for step in steps:
            builder.run(step)
        doc.commitTransaction()
    except Exception as exc:
        doc.abortTransaction()
        doc.recompute()
        builder.objects.pop(step_id, None)
        return bridge_core.error_result("Not done (%s): %s" % (title, exc))
    doc.recompute()
    made = builder.objects.get(step_id)
    named = (" Its id is %r." % step_id) if made is not None else ""
    log("AI bridge: %s" % title)
    return bridge_core.result("Done: %s.%s %s" % (title, named, _summary(doc)))


def _summary(doc):
    from .. import bodies

    parts = []
    for body in bodies.solid_bodies(doc):
        shape = body.Shape
        box = shape.BoundBox
        parts.append(
            "%s: %.6g mm3, %.4g x %.4g x %.4g mm"
            % (body.Label, shape.Volume, box.XLength, box.YLength, box.ZLength)
        )
    return ("Bodies now: " + "; ".join(parts) + ".") if parts else "No solid body yet."


def _get_design(_args):
    import json

    from .. import bodies, extrude, parameters

    doc = _doc()
    if doc is None:
        return bridge_core.result("No design is open. create_sketch starts a new one.")
    info = {"design": doc.Label, "file": doc.FileName or None, "units": "mm", "bodies": []}
    for body in bodies.solid_bodies(doc):
        box = body.Shape.BoundBox
        info["bodies"].append(
            {
                "id": body.Name,
                "label": body.Label,
                "volume_mm3": round(body.Shape.Volume, 6),
                "bbox_mm": [
                    round(v, 6)
                    for v in (box.XMin, box.YMin, box.ZMin, box.XMax, box.YMax, box.ZMax)
                ],
                "solids": len(body.Shape.Solids),
            }
        )
    try:
        from .. import timeline_ops

        names = timeline_ops.timeline(doc).names()
    except Exception:
        names = [o.Name for o in doc.Objects]
    info["timeline"] = []
    for name in names:
        obj = doc.getObject(name)
        if obj is not None:
            info["timeline"].append({"id": obj.Name, "label": obj.Label, "type": obj.TypeId})
    info["parameters"] = []
    try:
        for name in parameters.user_names(doc):
            info["parameters"].append({"name": name})
    except Exception:
        pass
    info["sketches"] = []
    for obj in doc.Objects:
        if obj.TypeId == "Sketcher::SketchObject":
            try:
                areas = len(extrude.regions(obj))
            except Exception:
                areas = None
            info["sketches"].append({"id": obj.Name, "label": obj.Label, "closed_areas": areas})
    return bridge_core.result(json.dumps(info, indent=1))


def _screenshot(args):
    from .. import capture_ui

    doc = _doc()
    gui_doc = Gui.getDocument(doc.Name) if doc is not None else None
    view = gui_doc.ActiveView if gui_doc is not None else None
    if view is None or not hasattr(view, "saveImage"):
        return bridge_core.error_result("No design is open to take a picture of.")
    turn = VIEWS.get(args.get("view") or "")
    if turn:
        getattr(view, turn)()
        view.fitAll()
    width, height = int(args.get("width", 1024)), int(args.get("height", 768))
    handle, path = tempfile.mkstemp(suffix=".png", prefix="sciforge-ai-")
    os.close(handle)
    try:
        capture_ui.save(path, width, height)
        with open(path, "rb") as stream:
            data = base64.b64encode(stream.read()).decode("ascii")
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
    return bridge_core.result(
        "A %d x %d picture of %s%s."
        % (width, height, doc.Label, (" (%s view)" % args["view"]) if args.get("view") else ""),
        data,
    )


def _measure(args):
    from .. import measure
    from .ops import inspect_ops

    doc = _doc()
    if doc is None:
        return bridge_core.error_result("No design is open to measure.")
    builder = _builder(doc)
    a = inspect_ops._ref(builder, args["a"], "measure a")
    b = inspect_ops._ref(builder, args["b"], "measure b")
    found = measure.relation(measure.entity(*a), measure.entity(*b))
    words = ["distance %.6g mm" % found["distance"]]
    if found.get("angle") is not None:
        words.append("angle %.6g degrees" % found["angle"])
    return bridge_core.result("Measured: " + ", ".join(words) + ".")


def _undo_redo(which):
    doc = _doc()
    if doc is None:
        return bridge_core.error_result("No design is open.")
    names = doc.UndoNames if which == "undo" else doc.RedoNames
    if not names:
        return bridge_core.error_result("There is nothing to %s." % which)
    getattr(doc, which)()
    doc.recompute()
    return bridge_core.result("%s: %s. %s" % (which.capitalize(), names[0], _summary(doc)))


def _confirm_overwrite(path):
    return ask(
        "AI control",
        "The AI app wants to write over the file\n%s\n\nAllow it to replace that file?" % path,
    )


def _save(args):
    from .. import versions, versions_ui

    doc = _doc()
    if doc is None:
        return bridge_core.error_result("No design is open to save.")
    path = args.get("path")
    if not path:
        if not doc.FileName:
            return bridge_core.error_result(
                "This design has never been saved: give a path ending in .FCStd, or the person "
                "saves it in SciForge."
            )
        versions_ui._save_version(doc.Name, "Saved by an AI app")
        return bridge_core.result("Saved %s." % doc.FileName)
    path = os.path.abspath(path)
    if not versions.is_design(path):
        return bridge_core.error_result("The path must end in .FCStd.")
    if os.path.exists(path) and not versions.same_path(path, doc.FileName):
        if not _confirm_overwrite(path):
            return bridge_core.error_result("The person did not allow replacing %s." % path)
    versions_ui._first_save(doc.Name, path, save_as=bool(doc.FileName))
    if not os.path.isfile(path):
        return bridge_core.error_result("The design could not be saved to %s." % path)
    return bridge_core.result("Saved as %s." % path)


def _export(args):
    from .. import export

    doc = _doc()
    if doc is None:
        return bridge_core.error_result("No design is open to export.")
    label = {"step": "STEP", "stl": "STL (Binary)", "3mf": "3MF"}[args["format"]]
    path = export.with_extension(os.path.abspath(args["path"]), export.extension_of(label))
    if os.path.exists(path) and not _confirm_overwrite(path):
        return bridge_core.error_result("The person did not allow replacing %s." % path)
    body_list = export.exportable_bodies(doc)
    if label == "STEP":
        written = export.export_step(body_list, path)
    else:
        written = export.export_mesh_files(doc, body_list, label, path)[0][0]
    return bridge_core.result("Exported %s." % written)
