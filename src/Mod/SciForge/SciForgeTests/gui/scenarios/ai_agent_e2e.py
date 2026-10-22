# SPDX-License-Identifier: LGPL-2.1-or-later
"""An AI agent builds and checks a part in the running SciForge ONLY through MCP
(docs/sciforge/dev/cadcraft-lessons.md idea 3): the real MCP server (sciforge_mcp.py) is
started as an AI app starts it and passes every call to SciForge's AI bridge; the agent's
script is the one the headless test runs (SciForgeTests/headless/agent_e2e.py: a plate,
a hole, a row of holes, a fillet, undo / redo, a timeline edit, a mistake, each checked with
inspect_design / query_geometry / check_design / diff_design numbers, render returning a
PNG and the resource sciforge://design).

Path 1, AI control on (Preferences > AI), the server starts and offers tools, resources and
  prompts.
Path 2, the agent's script through the bridge: every check of the headless run, here with
  the window (render takes the picture from SciForge's own 3D view).
Path 3, what only the window has: inspect_design names what the person selected (with a
  ref); render with renderer window and highlight leaves the person's selection and camera
  as they were.
Path 4, AI control off again.
"""

import base64
import json
import time

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
from SciForgeTests.gui import harness as h

s = {}


class Mcp:
    """The AI app's side of MCP over stdio. A request waits for its answer while Qt keeps
    running, because SciForge answers on this same (GUI) thread."""

    def __init__(self, command, args, env):
        import subprocess
        import threading

        try:  # (a write to a server that died must fail, not end FreeCAD: bridge.py)
            import signal

            signal.signal(signal.SIGPIPE, signal.SIG_IGN)
        except (AttributeError, ValueError, OSError):
            pass
        self.proc = subprocess.Popen(
            [command] + args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=env,
        )
        self.answers = {}
        self.next_id = 1
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        for line in self.proc.stdout:
            try:
                message = json.loads(line)
                self.answers[message.get("id")] = message
            except ValueError:
                pass

    def request(self, method, params=None, timeout=150.0):
        ident = self.next_id
        self.next_id += 1
        message = {"jsonrpc": "2.0", "id": ident, "method": method}
        if params is not None:
            message["params"] = params
        try:
            self.proc.stdin.write((json.dumps(message) + "\n").encode("utf-8"))
            self.proc.stdin.flush()
        except OSError as exc:
            return {"error": {"code": -1, "message": "the server is gone: %s" % exc}}
        end = time.time() + timeout
        while ident not in self.answers and time.time() < end:
            QtWidgets.QApplication.processEvents(QtCore.QEventLoop.AllEvents, 50)
            time.sleep(0.005)
        return self.answers.pop(ident, {"error": {"code": -1, "message": "no answer"}})

    def notify(self, method):
        self.proc.stdin.write((json.dumps({"jsonrpc": "2.0", "method": method}) + "\n").encode())
        self.proc.stdin.flush()

    def close(self):
        try:
            self.proc.stdin.close()
            self.proc.wait(10)
        except Exception:
            self.proc.kill()


def call(tool, args):
    answer = s["mcp"].request("tools/call", {"name": tool, "arguments": args})
    if "error" in answer:
        return {"content": [{"type": "text", "text": answer["error"]["message"]}], "isError": True}
    return answer["result"]


def read(uri):
    return s["mcp"].request("resources/read", {"uri": uri}).get("result")


# -- Path 1 -------------------------------------------------------------------------------------
def start():
    from sciforge import ai_ui, preferences_ui
    from sciforge.ai import bridge

    bridge.ASK = lambda title, text: True  # (ai_bridge clicks Allow for real)
    preferences_ui.save({"allow_ai": True})
    h.check("AI control is on", bridge.running())
    command, args = ai_ui.server_command()
    s["mcp"] = Mcp(command, args, ai_ui.server_env())
    init = s["mcp"].request(
        "initialize",
        {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "scenario", "version": "1"},
        },
    )
    caps = (init.get("result") or {}).get("capabilities", {})
    h.check(
        "the server offers tools, resources and prompts",
        {"tools", "resources", "prompts"} <= set(caps),
        init,
    )
    s["mcp"].notify("notifications/initialized")
    prompts = s["mcp"].request("prompts/list").get("result", {}).get("prompts", [])
    h.check("prompts/list has the workflow templates", len(prompts) >= 3, prompts[:1])


start.wait_ms = 1000


# -- Path 2 -------------------------------------------------------------------------------------
def agent_builds_and_checks():
    from SciForgeTests.headless import agent_e2e

    agent = agent_e2e.Agent(call, read)
    try:
        agent_e2e.script(agent)
    except Exception as exc:
        h.check("the agent's script ran to the end", False, exc)
    for row in agent.results:
        h.check("agent: %s" % row["check"], row["ok"], row["detail"])
    h.check("the agent made its checks", len(agent.results) > 50, len(agent.results))
    doc = App.ActiveDocument
    h.check(
        "the design is the agent's, in the window",
        doc is not None and doc.Label.startswith("AgentPlate"),
        doc and doc.Label,
    )
    names = [n for n in (doc.UndoNames if doc is not None else []) if n != "Add a Body"]
    h.check(  # (new_design's empty body is the window's own first step)
        "each change was one Undo step named AI: ...",
        names and all(n.startswith("AI:") for n in names),
        names[:8],
    )
    s["agent"] = agent


agent_builds_and_checks.wait_ms = 1500


# -- Path 3 -------------------------------------------------------------------------------------
def selection_and_window_render():
    from sciforge import bodies

    doc = App.ActiveDocument
    body = bodies.find_body(doc)
    tip = body.Tip if body is not None else None
    top = None
    for i, face in enumerate(tip.Shape.Faces if tip is not None else [], start=1):
        if face.Surface.__class__.__name__ == "Plane" and abs(face.CenterOfMass.z - 12) < 1e-6:
            top = "Face%d" % i
    h.check("the top face found", top is not None)
    if top is None:
        return
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(doc.Name, tip.Name, top)
    data = None
    result = call("inspect_design", {})
    text = " ".join(c.get("text", "") for c in result.get("content", []) if c["type"] == "text")
    try:
        data = json.loads(text[text.index("{") :])
    except ValueError:
        pass
    selection = (data or {}).get("selection", [])
    h.check(
        "inspect_design names the selected face",
        selection and top in selection[0]["elements"],
        selection,
    )
    refs = selection[0].get("refs", {}) if selection else {}
    h.check(
        "... with a ref that picks the top face",
        refs.get(top) and refs[top].get("normal") == [0.0, 0.0, 1.0],
        refs,
    )
    view = Gui.ActiveDocument.ActiveView
    camera = view.getCamera()
    result = call(
        "render",
        {
            "renderer": "window",
            "view": "front",
            "width": 320,
            "height": 240,
            "highlight": {"faces": {"type": "cylinder", "radius": 3}},
        },
    )
    images = [c for c in result.get("content", []) if c["type"] == "image"]
    png = base64.b64decode(images[0]["data"]) if images else b""
    h.check("render (window) returns a PNG", png[:8] == b"\x89PNG\r\n\x1a\n", result)
    words = " ".join(c.get("text", "") for c in result.get("content", []) if c["type"] == "text")
    h.check(
        "... from the window, the holes in orange",
        "window renderer" in words and "in orange" in words,
        words,
    )
    after = [
        (x.ObjectName, list(x.SubElementNames)) for x in Gui.Selection.getSelectionEx(doc.Name)
    ]
    h.check("the person's selection is as it was", after == [(tip.Name, [top])], after)
    h.check("... and the camera too", view.getCamera() == camera)
    Gui.Selection.clearSelection()
    h.shot("agent-part")


selection_and_window_render.wait_ms = 1500


# -- Path 4 -------------------------------------------------------------------------------------
def stop():
    from sciforge import preferences_ui
    from sciforge.ai import bridge

    s["mcp"].close()
    preferences_ui.save({"allow_ai": False})
    bridge.ASK = None
    h.check("AI control is off again", not bridge.running())
    h.check("no pop-up left", not h.popups(), h.popups())


h.run("ai_agent_e2e", [start, agent_builds_and_checks, selection_and_window_render, stop])
