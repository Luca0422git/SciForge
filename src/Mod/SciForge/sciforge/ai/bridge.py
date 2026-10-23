# SPDX-License-Identifier: LGPL-2.1-or-later
"""The AI bridge inside SciForge (brief home-cloud-ai.md section 4.3, milestone M3).

When Preferences > AI > "Allow AI apps to control SciForge" is on (off by default), SciForge
listens on 127.0.0.1 only, at a random port, and writes <user data>/SciForge/ai/bridge.json
with that port and a random key (bridge_core.py). The MCP server an AI app starts
(sciforge_mcp.py) sends each tool call there.

A call arrives on the server's thread and waits; the work happens on SciForge's own (GUI)
thread, where FreeCAD may be touched: a timer takes the calls one by one and hands each to
the executor (sciforge/ai/executor.py, the same one the headless backend uses) with the GUI
host below. Every call that changes the design is one Undo step ("AI: Extrude 10 mm"), built
with the same code as the golden models and the dialogs (sciforge/ai/ops, sciforge/ai/actions).
The tools themselves are listed in the catalogue (sciforge/ai/catalog). Safety:
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
from . import bridge_core, catalog, executor

OPTION = ("User parameter:BaseApp/Preferences/Mod/SciForge/AI", "AllowControl")
WAIT = 115.0  # seconds a call waits for SciForge (the MCP server waits 120)
ASK = None  # tests: function(title, text) -> True / False instead of the question
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
                text = (
                    "SciForge is still working on %s (or waiting for the person to answer a "
                    "question in SciForge). Check SciForge before trying again." % tool
                )
                if not catalog.is_read_only(tool):  # (honest: it may still happen)
                    text += (
                        " The change may or may not be applied when it finishes: inspect the "
                        "design (get_design, get_timeline) before repeating it."
                    )
                self._send(200, bridge_core.error_result(text))
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
    problems = catalog.validate(tool, args)
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
    entry = catalog.tool(tool)
    if entry["changes_design"] or entry.get("writes_files"):
        reason = _busy()
        if reason:
            return _record(tool, bridge_core.error_result(reason))
    answer = executor.run(tool, args, host())
    return _record(tool, answer)


class GuiHost(executor.Host):
    """The executor's host inside the SciForge window: the 3D view's active body, the
    questions to the person, SciForge's own saving (version history) and screenshots."""

    gui = True

    def find_body(self, doc):
        from .. import bodies

        if doc is App.ActiveDocument:
            return commands.find_body()
        return bodies.find_body(doc)

    def ensure_body(self, doc):
        if doc is not App.ActiveDocument:
            App.setActiveDocument(doc.Name)
        return commands.ensure_body()

    def set_active_body(self, body):
        from .. import components

        try:
            components.activate_body(body)
        except Exception as exc:
            warn("AI bridge: %s" % exc)

    def confirm_overwrite(self, path):
        return _confirm_overwrite(path)

    def refuse_overwrite_text(self, path):
        if isinstance(path, (list, tuple)):
            path = ", ".join(path)
        return "The person did not allow replacing %s." % path

    def save(self, doc, path=None):
        from .. import versions_ui

        if not path:
            versions_ui._save_version(doc.Name, "Saved by an AI app")
            return doc.FileName
        versions_ui._first_save(doc.Name, path, save_as=bool(doc.FileName))
        return path

    def open_design(self, path):
        from .. import versions_ui

        doc = versions_ui.open_design(path)
        if doc is None:
            raise executor.UserError("The design %s could not be opened." % path)
        return doc

    def new_document(self, name):
        doc = App.newDocument(executor._doc_name(name))
        doc.Label = name
        return doc

    def ready(self, doc):
        pass  # (documents of the window have undo on)

    def show_document(self, doc):
        App.setActiveDocument(doc.Name)
        try:
            gdoc = Gui.getDocument(doc.Name)
            area = Gui.getMainWindow().findChild(QtWidgets.QMdiArea)
            for window in area.subWindowList() if area is not None else []:
                if window.windowTitle().split(" : ")[0].rstrip("*") in (doc.Label, doc.Name):
                    area.setActiveSubWindow(window)
                    break
            if gdoc is not None:
                Gui.ActiveDocument = gdoc
        except Exception as exc:
            warn("AI bridge: %s" % exc)

    def busy(self):
        return _busy()

    def ask(self, title, text):
        return ask(title, text)

    def view(self, doc):
        gui_doc = Gui.getDocument(doc.Name) if doc is not None else None
        view = gui_doc.ActiveView if gui_doc is not None else None
        return view if view is not None and hasattr(view, "saveImage") else None

    def selection(self, doc):
        from . import geometry_facts

        rows = []
        for sel in Gui.Selection.getSelectionEx(doc.Name):
            obj = sel.Object
            row = {"object": obj.Name, "label": obj.Label, "elements": []}
            subs = [n.split(".")[-1] for n in sel.SubElementNames if n]
            row["elements"] = subs
            try:
                shape = obj.Shape
                for element, prefix in (("faces", "Face"), ("edges", "Edge")):
                    wanted = {n for n in subs if n.startswith(prefix)}
                    if wanted:
                        refs = geometry_facts.stable_refs(shape, element, wanted)
                        from .. import bodies

                        body = obj if bodies.is_body(obj) else bodies.body_of(obj)
                        if body is not None:
                            geometry_facts.tie_to_body(refs, body.Name)
                        row.setdefault("refs", {}).update(refs)
            except Exception:
                pass
            rows.append(row)
        return rows

    def push_highlight(self, doc, marked):
        """Before render takes a picture from the window: the person's selection taken off
        (saveImage draws a selected body tinted, and never draws selected faces or edges,
        so selecting them marked nothing) and the marked faces and edges added to the 3D
        view in orange (_highlight_node). pop_highlight puts everything back."""
        saved = {"selection": [], "node": None, "root": None, "drawn": None}
        try:
            for sel in Gui.Selection.getSelectionEx(doc.Name, 0):
                names = sel.SubElementNames or ("",)
                saved["selection"] += [(sel.Object.Name, n) for n in names]
            Gui.Selection.clearSelection(doc.Name)
            Gui.Selection.clearPreselection()
        except Exception as exc:
            warn("AI render: %s" % exc)
        if marked and marked.get("source") is not None:
            saved["drawn"] = False
            try:
                view = self.view(doc)
                node = _highlight_node(doc, marked)
                if view is not None and node is not None:
                    root = view.getSceneGraph()
                    root.addChild(node)
                    saved.update(node=node, root=root, drawn=True)
            except Exception as exc:
                warn("AI render: the highlight could not be drawn: %s" % exc)
        return saved

    def pop_highlight(self, doc, saved):
        if not saved:
            return None
        try:
            if saved["node"] is not None:
                saved["root"].removeChild(saved["node"])
        except Exception as exc:
            warn("AI render: %s" % exc)
        try:
            Gui.Selection.clearSelection(doc.Name)
            for name, sub in saved["selection"]:
                Gui.Selection.addSelection(doc.Name, name, sub)
        except Exception as exc:
            warn("AI render: %s" % exc)
        return saved["drawn"]

    def screenshot(self, doc, width, height):
        from .. import capture_ui

        handle, path = tempfile.mkstemp(suffix=".png", prefix="sciforge-ai-")
        os.close(handle)
        try:
            capture_ui.save(path, width, height)
            with open(path, "rb") as stream:
                return base64.b64encode(stream.read()).decode("ascii")
        finally:
            try:
                os.remove(path)
            except OSError:
                pass


HIGHLIGHT_RGB = (1.0, 136 / 255.0, 0.0)  # render_core.HIGHLIGHT: the same orange


def _highlight_node(doc, marked):
    """A Coin node drawing the marked faces and edges of marked["source"] in orange where
    that solid is in the design. The faces are tessellated on the very shape the window
    shows, with a deflection no finer than its own, so OpenCASCADE hands back the window's
    triangles and the orange lies exactly on them (pulled forward a little: the window's
    faces are pushed back by their own polygon offset). An earlier step's solid, not shown,
    is drawn alone and its edges on top."""
    from pivy import coin

    from .. import bodies

    source = marked["source"]
    shape = source.Shape
    parent = source.getParentGeoFeatureGroup()
    place = parent.getGlobalPlacement() if parent is not None else App.Placement()
    shown = any(
        b is source or getattr(b, "Tip", None) is source
        for b in bodies.list_bodies(doc)
        if bodies.is_shown(b)
    )
    try:
        deviation = float(source.ViewObject.Deviation)
    except Exception:
        deviation = 0.5
    box = shape.BoundBox
    deflection = max((box.XLength + box.YLength + box.ZLength) / 300.0 * deviation * 1.5, 1e-3)
    root = coin.SoSeparator()
    root.setName("SciForgeAIHighlight")
    points, indexes = [], []
    for name in sorted(marked["faces"]):
        verts, tris = shape.getElement(name).tessellate(deflection)
        start = len(points)
        points += [tuple(place.multVec(v)) for v in verts]
        for a, b, c in tris:
            indexes += [a + start, b + start, c + start, -1]
    if indexes:
        faces = coin.SoSeparator()
        material = coin.SoMaterial()
        material.diffuseColor.setValue(*HIGHLIGHT_RGB)
        material.emissiveColor.setValue(*[0.35 * c for c in HIGHLIGHT_RGB])
        hints = coin.SoShapeHints()
        hints.vertexOrdering = coin.SoShapeHints.UNKNOWN_ORDERING  # (lit on both sides)
        offset = coin.SoPolygonOffset()
        offset.factor.setValue(-1.0)
        offset.units.setValue(-1.0)
        coords = coin.SoCoordinate3()
        coords.point.setValues(0, len(points), points)
        faceset = coin.SoIndexedFaceSet()
        faceset.coordIndex.setValues(0, len(indexes), indexes)
        for child in (material, hints, offset, coords, faceset):
            faces.addChild(child)
        root.addChild(faces)
    lines, counts = [], []
    for name in sorted(marked["edges"]):
        verts = shape.getElement(name).discretize(Deflection=deflection / 1.5)
        lines += [tuple(place.multVec(v)) for v in verts]
        counts.append(len(verts))
    if counts:
        edges = coin.SoSeparator()
        material = coin.SoMaterial()
        material.diffuseColor.setValue(*HIGHLIGHT_RGB)
        model = coin.SoLightModel()
        model.model = coin.SoLightModel.BASE_COLOR
        style = coin.SoDrawStyle()
        style.lineWidth.setValue(4.0)
        for child in (material, model, style):
            edges.addChild(child)
        if not shown:
            depth = coin.SoDepthBuffer()
            depth.test.setValue(False)
            edges.addChild(depth)
        coords = coin.SoCoordinate3()
        coords.point.setValues(0, len(lines), lines)
        lineset = coin.SoLineSet()
        lineset.numVertices.setValues(0, len(counts), counts)
        edges.addChild(coords)
        edges.addChild(lineset)
        root.addChild(edges)
    return root if (indexes or counts) else None


_HOST = []


def host():
    if not _HOST:
        _HOST.append(GuiHost())
    return _HOST[0]


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


# -- questions -------------------------------------------------------------------------
def _confirm_overwrite(path):
    if isinstance(path, (list, tuple)):  # (One File Per Body: one question for them all)
        return ask(
            "AI control",
            "The AI app wants to write over these files\n%s\n\nAllow it to replace them?"
            % "\n".join(path),
        )
    return ask(
        "AI control",
        "The AI app wants to write over the file\n%s\n\nAllow it to replace that file?" % path,
    )
