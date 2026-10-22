# SPDX-License-Identifier: LGPL-2.1-or-later
"""The AI tools that need the SciForge window (sciforge/ai/catalog, needs "gui"), run through
the bridge's own entry (bridge.call, as SciForge's chat panel calls it) with the window's host
(bridge.GuiHost). The headless test (SciForgeTests/headless) covers every other tool.

Path 1, a 40 x 30 x 10 block: create_sketch, extrude; each is one Undo step named "AI: ...".
Path 2, the camera: set_view top, get_view tells the camera, named_view save / go returns to
  it after set_view front, screenshot gives a PNG.
Path 3, show_hide hides the sketch; edit_step makes the block 15 mm.
Path 4, save_as through SciForge's own saving (the file exists, the design is named after it).
Path 5, create_drawing, get_drawing, export_drawing to a PDF (TechDraw prints only with the
  window).
Path 6, undo takes the last change back; a tool that needs the window is never refused here.
"""

import base64
import json
import os
import tempfile

import FreeCAD as App
from SciForgeTests.gui import harness as h

s = {"dir": tempfile.mkdtemp(prefix="sciforge-ai-gui-")}


def call(tool, args):
    from sciforge.ai import bridge

    try:
        answer = bridge.call(tool, args, from_chat=True)
    except Exception as exc:  # (the bridge must never raise: that is a failure too)
        answer = {"text": "raised %s" % exc, "is_error": True, "image_png_base64": None}
    s["last"] = answer
    return answer


def ok(name, answer, extra=True):
    h.check(name, not answer["is_error"] and extra, answer["text"][:400])


def volume():
    doc = App.ActiveDocument
    if doc is None:
        return 0.0
    return sum(
        o.Shape.Volume
        for o in doc.Objects
        if o.TypeId == "PartDesign::Body" and not o.Shape.isNull()
    )


def undo_names():
    doc = App.ActiveDocument
    return list(doc.UndoNames) if doc is not None else []


# -- Path 1 -------------------------------------------------------------------------------------
def block():
    if App.ActiveDocument is None:
        App.newDocument("AITools")
    a = call("create_sketch", {"plane": "XY", "geometry": [{"rect": [0, 0, 40, 30]}]})
    ok("create_sketch answered", a)
    sketch = [o.Name for o in App.ActiveDocument.Objects if o.TypeId == "Sketcher::SketchObject"]
    s["sketch"] = sketch[-1] if sketch else "Sketch"
    a = call("extrude", {"profile": s["sketch"], "distance": 10})
    ok("extrude made the 12000 mm3 block", a, abs(volume() - 12000) < 1)
    names = undo_names()
    h.check(
        "each AI step is one Undo step named AI: ...",
        len(names) >= 2 and names[0].startswith("AI:") and names[1].startswith("AI:"),
        names[:4],
    )
    pads = [o.Name for o in App.ActiveDocument.Objects if o.TypeId == "PartDesign::Pad"]
    s["pad"] = pads[-1] if pads else "Pad"


# -- Path 2 -------------------------------------------------------------------------------------
def camera():
    a = call("set_view", {"orientation": "top"})
    ok("set_view top answered", a)
    a = call("get_view", {})
    try:
        data = json.loads(a["text"])
    except ValueError:
        data = {}
    ok("get_view tells the camera as JSON", a, bool(data))
    s["top_view"] = data
    a = call("named_view", {"action": "save", "name": "AI top"})
    ok("named_view saved a view", a)
    call("set_view", {"orientation": "front"})
    front = json.loads(call("get_view", {})["text"] or "{}")
    a = call("named_view", {"action": "go", "name": "AI top"})
    back = json.loads(call("get_view", {})["text"] or "{}")
    ok(
        "named_view go returned to the saved camera",
        a,
        back.get("camera") == data.get("camera") and front.get("camera") != data.get("camera"),
    )
    a = call("named_view", {"action": "list"})
    ok("named_view list has it", a, "AI top" in a["text"])
    a = call("screenshot", {"view": "iso", "width": 320, "height": 240})
    png = base64.b64decode(a.get("image_png_base64") or "") if a.get("image_png_base64") else b""
    ok("screenshot gave a PNG", a, png[:8] == b"\x89PNG\r\n\x1a\n")


# -- Path 3 -------------------------------------------------------------------------------------
def hide_and_edit():
    a = call("show_hide", {"targets": [s["sketch"]], "visible": False})
    obj = App.ActiveDocument.getObject(s["sketch"])
    ok("show_hide hid the sketch", a, obj is not None and not obj.Visibility)
    a = call("edit_step", {"step": s["pad"], "set": {"distance": 15}})
    ok("edit_step made the block 15 mm (18000 mm3)", a, abs(volume() - 18000) < 1)


# -- Path 4 -------------------------------------------------------------------------------------
def save():
    path = os.path.join(s["dir"], "ai-gui.FCStd")
    a = call("save_as", {"path": path})
    ok("save_as saved through SciForge", a, os.path.isfile(path))
    s["path"] = path


# -- Path 5 -------------------------------------------------------------------------------------
def drawing():
    a = call("create_drawing", {"base_view": "Front", "projected": ["Top", "Right"]})
    ok("create_drawing made a drawing", a)
    a = call("get_drawing", {})
    ok("get_drawing lists the views", a, "View" in a["text"] or "view" in a["text"])
    pdf = os.path.join(s["dir"], "ai-gui.pdf")
    a = call("export_drawing", {"format": "pdf", "path": pdf})
    head = b""
    if os.path.isfile(pdf):
        with open(pdf, "rb") as stream:
            head = stream.read(5)
    ok("export_drawing wrote a PDF", a, head == b"%PDF-")


# -- Path 6 -------------------------------------------------------------------------------------
def undo():
    from sciforge.ai import catalog

    doc = App.ActiveDocument
    before = len(doc.UndoNames) if doc is not None else 0
    a = call("undo", {})
    after = len(App.ActiveDocument.UndoNames) if App.ActiveDocument is not None else 0
    ok("undo took the last change back", a, after < before or before == 0)
    state = {"design": True, "solid": True, "gui": True, "drawing": True}
    gui_only = [t["name"] for t in catalog.TOOLS if "gui" in t["needs"]]
    refused = [name for name in gui_only if not catalog.availability(name, state)[0]]
    h.check("there are tools that need the window", len(gui_only) >= 3, gui_only)
    h.check("no tool is refused for needing the window here", not refused, refused)
    h.check("no pop-up left", not h.popups(), h.popups())


h.run("ai_tools_gui", [block, camera, hide_and_edit, save, drawing, undo])
