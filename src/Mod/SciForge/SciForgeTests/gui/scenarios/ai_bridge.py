# SPDX-License-Identifier: LGPL-2.1-or-later
"""AI apps building in SciForge (docs/sciforge/parity/ai.md, brief home-cloud-ai.md M3): the
real MCP server (sciforge/ai/sciforge_mcp.py) is started as an AI app starts it, and this
scenario speaks MCP to it over stdin / stdout like Claude Desktop does. SciForge's questions
are answered with real clicks.

Path 1, the server starts: initialize names SciForge; tools/list has the 16 tools.
Path 2, AI control off (the default): a call answers that SciForge is not reachable.
Path 3, switched on in Preferences > AI: the first call asks the person; Allow.
Path 4, "make a 40 x 30 x 10 box with 3 mm rounded edges": create_sketch, extrude (12000
  mm3), fillet the top edges; every step is one Undo step named "AI: ...".
Path 5, get_design and screenshot (a PNG the AI can look at).
Path 6, a command dialog open in SciForge: a changing call is refused ("SciForge is busy").
Path 7, the AI activity panel lists the calls; Undo last AI step takes the fillet away.
Path 8, the AI panel's switch turns AI control off: the next call answers that SciForge is not reachable.
Path 9, Home > + Add an AI: Gemini CLI set up (its settings file in a test folder), removed.
"""

import base64
import json
import os
import subprocess
import tempfile
import threading
import zipfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtWidgets
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import versions_input as vi
from SciForgeTests.gui import widget_input as wi

s = {"answers": {}, "next": 1}


class Mcp:
    """An AI app's side of MCP over stdio: requests go out at once, answers are read by a
    thread (SciForge answers on its own thread, which runs these steps too)."""

    def __init__(self, command, args, env):
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
        self.thread = threading.Thread(target=self._read, daemon=True)
        self.thread.start()

    def _read(self):
        for line in self.proc.stdout:
            try:
                message = json.loads(line)
                self.answers[message.get("id")] = message
            except ValueError:
                pass

    def send(self, method, params=None, notify=False):
        message = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            message["params"] = params
        if not notify:
            message["id"] = s["next"]
            s["next"] += 1
        try:
            self.proc.stdin.write((json.dumps(message) + "\n").encode("utf-8"))
            self.proc.stdin.flush()
        except OSError as exc:
            h.check(
                "the MCP server takes %s" % method, False, "%s (exit %s)" % (exc, self.proc.poll())
            )
        return message.get("id")

    def call(self, tool, args):
        return self.send("tools/call", {"name": tool, "arguments": args})

    def close(self):
        try:
            self.proc.stdin.close()
            self.proc.wait(10)
        except Exception:
            self.proc.kill()


def mcp():
    return s["mcp"]


def result(request_id):
    message = mcp().answers.get(request_id)
    return message.get("result") if message else None


def text_of(request_id):
    res = result(request_id) or {}
    return " ".join(c.get("text", "") for c in res.get("content", []) if c.get("type") == "text")


def is_error(request_id):
    return bool((result(request_id) or {}).get("isError"))


def body_volume():
    doc = App.ActiveDocument
    if doc is None:
        return None
    return sum(
        o.Shape.Volume
        for o in doc.Objects
        if o.TypeId == "PartDesign::Body" and not o.Shape.isNull()
    )


class _Panel:
    """A command dialog (as SciForge's own commands show in the task panel)."""

    def __init__(self):
        self.form = QtWidgets.QLabel("A command is open")

    def reject(self):
        return True


def question():
    return vi.dialog("SciForgeAIQuestion")


# -- Path 1 -------------------------------------------------------------------------------------
def start_server():
    from sciforge import ai_ui

    command, args = ai_ui.server_command()
    s["command"], s["args"] = command, args
    h.check("the server runs with SciForge's own script", args[0].endswith("sciforge_mcp.py"), args)
    s["mcp"] = Mcp(command, args, ai_ui.server_env())
    s["init"] = mcp().send(
        "initialize",
        {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "scenario", "version": "1"},
        },
    )


start_server.wait_ms = 2500


def initialized():
    res = result(s["init"])
    h.check("initialize answered", res is not None, mcp().answers)
    if res:
        h.check("... by SciForge", res["serverInfo"]["name"] == "sciforge", res["serverInfo"])
    mcp().send("notifications/initialized", notify=True)
    s["list"] = mcp().send("tools/list", {})


def tools_listed():
    res = result(s["list"]) or {}
    names = [t["name"] for t in res.get("tools", [])]
    h.check("tools/list has the 16 tools", len(names) == 16, names)
    h.check("... extrude and screenshot among them", "extrude" in names and "screenshot" in names)
    s["off"] = mcp().call("get_design", {})


tools_listed.wait_ms = 2000


# -- Path 2 -------------------------------------------------------------------------------------
def off_by_default():
    from sciforge.ai import bridge, bridge_core

    h.check("AI control is off by default", not bridge.allowed() and not bridge.running())
    h.check("a call says SciForge is not reachable", is_error(s["off"]), text_of(s["off"]))
    h.check("... in those words", bridge_core.NOT_RUNNING in text_of(s["off"]), text_of(s["off"]))


# -- Path 3 -------------------------------------------------------------------------------------
def switch_on():
    from sciforge import preferences_ui
    from sciforge.ai import bridge

    preferences_ui.save({"allow_ai": True})
    h.check("Preferences > AI switched the bridge on", bridge.running())
    h.check("its file tells the server where it is", os.path.isfile(s["args"][-1]), s["args"])
    from sciforge import home_ui

    page = home_ui.view()
    h.check(
        "Home's AI card says it is on",
        page is not None and "AI control: on" in page.ai_status.text(),
    )
    s["sketch"] = mcp().call(
        "create_sketch", {"plane": "XY", "geometry": [{"rect": [0, 0, 40, 30]}]}
    )


switch_on.wait_ms = 2000


def allow():
    box = question()
    h.check("the first call asks the person", box is not None)
    if box is None:
        return
    h.check("... and says what it allows", "AI app wants to control SciForge" in box.text())
    h.shot("question")
    wi.click(vi.child(box, "SciForgeAIAllow"))


allow.wait_ms = 2500


# -- Path 4 -------------------------------------------------------------------------------------
def sketch_made():
    h.check("create_sketch answered", result(s["sketch"]) is not None, mcp().answers.keys())
    h.check("... done", not is_error(s["sketch"]), text_of(s["sketch"]))
    h.check("... with its id Sketch1", "'Sketch1'" in text_of(s["sketch"]), text_of(s["sketch"]))
    s["extrude"] = mcp().call("extrude", {"profile": "Sketch1", "distance": 10})


sketch_made.wait_ms = 3000


def extruded():
    h.check("extrude done", not is_error(s["extrude"]), text_of(s["extrude"]))
    h.check("40 x 30 x 10 = 12000 mm3", abs((body_volume() or 0) - 12000) < 1e-6, body_volume())
    doc = App.ActiveDocument
    h.check(
        "one Undo step named AI: Extrude 10 mm",
        doc.UndoNames[:1] == ["AI: Extrude 10 mm"],
        doc.UndoNames[:3],
    )
    s["fillet"] = mcp().call(
        "fillet",
        {"edges": {"type": "line", "at": {"axis": "z", "value": "max"}, "count": 4}, "radius": 3},
    )


extruded.wait_ms = 3000


def filleted():
    h.check("fillet done", not is_error(s["fillet"]), text_of(s["fillet"]))
    volume = body_volume() or 0
    # four 3 mm rounds on 140 mm of edges: about (1 - pi / 4) * 9 * 140 = 270 mm3, less at
    # the corners where two rounds meet
    h.check("the rounded edges took material away", 11700 < volume < 11760, volume)
    h.check(
        "... one Undo step AI: Fillet 3 mm", App.ActiveDocument.UndoNames[:1] == ["AI: Fillet 3 mm"]
    )
    s["filleted"] = volume
    s["design"] = mcp().call("get_design", {})
    s["shot"] = mcp().call("screenshot", {"view": "iso", "width": 320, "height": 240})


filleted.wait_ms = 4000


# -- Path 5 -------------------------------------------------------------------------------------
def looked_at():
    text = text_of(s["design"])
    try:
        info = json.loads(text)
    except ValueError:
        info = {}
    h.check("get_design describes the bodies", len(info.get("bodies", [])) == 1, text[:400])
    h.check(
        "... with the volume",
        info.get("bodies") and abs(info["bodies"][0]["volume_mm3"] - s["filleted"]) < 1e-3,
    )
    h.check("... and the timeline", any(t["id"] == "Fillet1" for t in info.get("timeline", [])))
    images = [c for c in (result(s["shot"]) or {}).get("content", []) if c.get("type") == "image"]
    h.check("screenshot returns an image", len(images) == 1, text_of(s["shot"]))
    if images:
        data = base64.b64decode(images[0]["data"])
        h.check(
            "... a PNG", data[:8] == b"\x89PNG\r\n\x1a\n" and images[0]["mimeType"] == "image/png"
        )
    Gui.Control.showDialog(_Panel())  # a command dialog open in SciForge
    s["busy"] = mcp().call("extrude", {"profile": "Sketch1", "distance": 5})


looked_at.wait_ms = 3000


# -- Path 6 -------------------------------------------------------------------------------------
def refused_while_busy():
    h.check(
        "a changing call is refused while a sketch is open", is_error(s["busy"]), text_of(s["busy"])
    )
    h.check("... SciForge is busy", "SciForge is busy" in text_of(s["busy"]), text_of(s["busy"]))
    Gui.Control.closeDialog()


# -- Path 7 -------------------------------------------------------------------------------------
def activity_listed():
    from sciforge import ai_ui

    p = ai_ui.panel()
    h.check("the AI activity panel opened", p is not None and p.isVisible())
    if p is None:
        return
    lines = [p.list.item(i).text() for i in range(p.list.count())]
    h.check(
        "it lists the calls, newest first", len(lines) > 1 and "screenshot" in lines[1], lines[:3]
    )
    h.check("... the refused one on top", bool(lines) and "SciForge is busy" in lines[0])
    h.check("one line each", all("\n" not in line for line in lines), lines[:3])
    h.shot("activity")
    wi.click(p.undo_button)


activity_listed.wait_ms = 1500


def fillet_undone():
    h.check(
        "Undo last AI step took the fillet away",
        abs((body_volume() or 0) - 12000) < 1e-6,
        (body_volume(), App.ActiveDocument.UndoNames[:3]),
    )


# -- Path 8 -------------------------------------------------------------------------------------
def stop_control():
    from sciforge import ai_panel_ui

    page = ai_panel_ui.panel()
    h.check("the AI panel's switch shows AI control on", page.toggle.isChecked())
    wi.click(page.toggle)


def stopped():
    from sciforge.ai import bridge

    h.check("the switch turned AI control off", not bridge.allowed() and not bridge.running())
    s["after"] = mcp().call("get_design", {})


stopped.wait_ms = 2000


def refused_after_stop():
    from sciforge.ai import bridge_core

    h.check(
        "after Stop a call says SciForge is not reachable",
        bridge_core.NOT_RUNNING in text_of(s["after"]),
        text_of(s["after"]),
    )
    mcp().close()


# -- Path 9 -------------------------------------------------------------------------------------
def add_an_ai():
    from sciforge import ai_ui, home_ui
    from sciforge.ai import installers

    s["gemini"] = os.path.join(tempfile.mkdtemp(prefix="sciforge-gemini-"), "settings.json")
    s["old_gemini"] = installers.gemini_settings_path
    installers.gemini_settings_path = lambda home=None: s["gemini"]
    ai_ui.OPEN_FILE = lambda path: s.setdefault("opened", path)
    home_ui.show()
    wi.click(home_ui.view().add_ai_button)


def set_up_gemini():
    d = vi.dialog("SciForgeAddAIDialog")
    h.check("+ Add an AI opened its window", d is not None)
    if d is None:
        return
    app = vi.child(d, "SciForgeAddAIApp")
    app.setCurrentIndex(app.findData("gemini"))
    h.shot("add-ai")
    wi.click(vi.child(d, "SciForgeAddAISetUp"))


def gemini_set_up():
    from sciforge.ai import bridge

    try:
        with open(s["gemini"], encoding="utf-8") as handle:
            entry = json.load(handle)["mcpServers"]["sciforge"]
    except Exception as exc:
        entry = {"error": str(exc)}
    h.check(
        "Gemini CLI's settings have SciForge",
        entry.get("args", [""])[0].endswith("sciforge_mcp.py"),
        entry,
    )
    h.check("setting up switched AI control on", bridge.allowed())
    d = vi.dialog("SciForgeAddAIDialog")
    wi.click(vi.child(d, "SciForgeAddAIRemove"))


def gemini_removed():
    from sciforge import ai_ui, preferences_ui
    from sciforge.ai import installers

    with open(s["gemini"], encoding="utf-8") as handle:
        servers = json.load(handle).get("mcpServers", {})
    h.check("Remove took SciForge out again", "sciforge" not in servers, servers)
    d = vi.dialog("SciForgeAddAIDialog")
    app = vi.child(d, "SciForgeAddAIApp")
    app.setCurrentIndex(app.findData("claude"))
    wi.click(vi.child(d, "SciForgeAddAIExtension"))
    path = s.get("opened")
    names = zipfile.ZipFile(path).namelist() if path and os.path.isfile(path) else []
    h.check(
        "the Claude extension file was made and opened", "manifest.json" in names, (path, names[:5])
    )
    vi.cancel_dialog(d)
    installers.gemini_settings_path = s["old_gemini"]
    ai_ui.OPEN_FILE = None
    preferences_ui.save({"allow_ai": False})
    h.check("no pop-up left", not h.popups(), h.popups())
    if App.ActiveDocument is None:
        App.newDocument("Scratch")


h.run(
    "ai_bridge",
    [
        start_server,
        initialized,
        tools_listed,
        off_by_default,
        switch_on,
        allow,
        sketch_made,
        extruded,
        filleted,
        looked_at,
        refused_while_busy,
        activity_listed,
        fillet_undone,
        stop_control,
        stopped,
        refused_after_stop,
        add_an_ai,
        set_up_gemini,
        gemini_set_up,
        gemini_removed,
    ],
)
