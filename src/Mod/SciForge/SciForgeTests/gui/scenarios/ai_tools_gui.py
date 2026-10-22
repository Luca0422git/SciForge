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
Path 7 (integration, 2026-10-22), export STEP with the window open: the answer says what the
  file does not keep (the timeline, the sketch) and the window shows the same message card
  (export_report_ui); colours are written with the window, so no colour line.
Path 8 (review fixes, 2026-10-22), One File Per Body over files that exist: the person is
  asked once, naming every file; denied, nothing is written; allowed, both are replaced. Two
  designs where one's name is the other's id: switch_design refuses and names both ids;
  closing a design makes another one active and the answer says which.
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


# -- Path 7 -------------------------------------------------------------------------------------
def export_report():
    from sciforge import export_report_ui

    export_report_ui.clear_recent()
    path = os.path.join(s["dir"], "ai-gui.step")
    a = call("export", {"format": "step", "path": path})
    ok(
        "export says what the STEP does not keep",
        a,
        os.path.isfile(path)
        and "Not kept in this file:" in a["text"]
        and "- the timeline (" in a["text"]
        and "colours" not in a["text"],
    )
    cards = export_report_ui.recent()
    h.check(
        "the window shows the same message card",
        bool(cards)
        and cards[-1]["title"] == "Exported ai-gui.step"
        and all(line in a["text"] for line in cards[-1]["lines"]),
        cards[-1:] if cards else cards,
    )


# -- Path 8 -------------------------------------------------------------------------------------
def per_body_overwrite():
    import glob

    from sciforge.ai import bridge

    asked = []
    s["allow"] = False

    def answer(title, text):
        asked.append(text)
        return s["allow"]

    bridge.ASK = answer
    try:
        call("create_sketch", {"plane": "XY", "geometry": [{"rect": [60, 0, 20, 20]}]})
        sketch = [
            o.Name for o in App.ActiveDocument.Objects if o.TypeId == "Sketcher::SketchObject"
        ][-1]
        a = call("extrude", {"profile": sketch, "distance": 5, "operation": "new_body"})
        ok("a second body for One File Per Body", a)
        args = {
            "format": "stl",
            "path": os.path.join(s["dir"], "parts.stl"),
            "one_file_per_body": True,
        }
        a = call("export", args)
        files = sorted(glob.glob(os.path.join(s["dir"], "parts-*.stl")))
        ok("one file per body wrote two files", a, len(files) == 2 and not asked)
        for path in files:
            with open(path, "w") as stream:
                stream.write("kept")
        a = call("export", args)
        kept = all(open(p).read() == "kept" for p in files)
        h.check(
            "replacing them asks the person once, naming both files",
            len(asked) == 1 and all(os.path.basename(p) in asked[0] for p in files),
            asked,
        )
        h.check("denied: refused and nothing written", a["is_error"] and kept, a["text"][:300])
        s["allow"] = True
        a = call("export", args)
        replaced = all(open(p).read() != "kept" for p in files)
        ok("allowed: both files replaced", a, len(asked) == 2 and replaced)
    finally:
        bridge.ASK = None


def same_names():
    first = App.ActiveDocument.Name
    call("new_design", {"name": first})  # its name is the first design's id
    second = App.ActiveDocument
    a = call("switch_design", {"design": first})
    h.check(
        "a name that is another design's id is refused with both ids",
        a["is_error"] and repr(first) in a["text"] and repr(second.Name) in a["text"],
        a["text"][:300],
    )
    h.check("the active design stayed", App.ActiveDocument is second, App.ActiveDocument.Name)
    from sciforge.ai import bridge

    bridge.ASK = lambda title, text: True  # (close it without saving: allowed)
    try:
        a = call("close_design", {"design": second.Name, "discard_changes": True})
    finally:
        bridge.ASK = None
    doc = App.ActiveDocument
    ok(
        "closing a design names the one that is now active",
        a,
        doc is not None and ("now %s (id %r)" % (doc.Label, doc.Name)) in a["text"],
    )
    h.check("no pop-up left", not h.popups(), h.popups())


h.run(
    "ai_tools_gui",
    [
        block,
        camera,
        hide_and_edit,
        save,
        drawing,
        undo,
        export_report,
        per_body_overwrite,
        same_names,
    ],
)
