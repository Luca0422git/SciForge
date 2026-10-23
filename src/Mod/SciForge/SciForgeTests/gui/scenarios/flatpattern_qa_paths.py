# SPDX-License-Identifier: LGPL-2.1-or-later
"""The paths the sm-flat builder's scenarios left out (QA), real input only, on a shelled tube
(40 x 30 x 20, corner radius 2, 1 mm; made in setup, not converted yet).

1. Convert to Sheet Metal from the front wall, OK; Ctrl+Z: the body is no longer sheet metal
   and the step is gone; Ctrl+Y: back.
2. Rip, Along Edge: a click on the line where the right wall meets the corner bend (preview,
   20 mm3), then a click on the bend's curved rim: refused ("straight edge"); OK is refused too
   (it kept the last good rip under the error before QA); Esc leaves the tube closed and no
   Rip in the timeline.
3. Rip, Type Face, a click on the back-right corner bend, OK.
4. Unfold from the front wall, Unfold All Bends ticked (the tube lies flat: 130.79 long), then
   unticked: the dialog asks for bends and OK is refused (before QA, OK kept every bend
   unfolded with the box unticked); ticked again, OK. Refold, OK: folded again.
5. Saved and reopened: Convert, Rip, Unfold and Refold come back with their own step classes,
   valid, the same shape; a forced recompute from the Convert step changes nothing; the
   Unfold ... Refold folder is still in the timeline; the Rip edited from the timeline keeps
   its type and face, Cancel changes nothing.
6. Create Flat Pattern from the front wall (130.79 x 20); Export DXF, Cancel: no file written;
   Finish Flat Pattern."""

import math
import os

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import flatpattern_steps as fs
from SciForgeTests.gui import harness as h

V = App.Vector
s = {}
CORNER = (math.pi / 4) * 3 * 20  # the back-right quarter ring ripped away (Type Face)


def setup():
    fs.build("FlatQA", fs.TUBE_STEPS)
    s["volume"] = fs.volume()
    s["path"] = os.path.join(fs.out_dir(), "flat_qa.FCStd")
    s["dxf"] = os.path.join(fs.out_dir(), "flat_qa_cancelled.dxf")
    for path in (s["path"], s["dxf"]):
        if os.path.exists(path):
            os.remove(path)


def not_sheet_metal():
    from sciforge import sheetmetal

    h.check("the tube is not sheet metal yet", not sheetmetal.is_sheet_metal_body(fs.body()))
    fs.tab("sheet_metal")


# -- 1. Convert, undo / redo ----------------------------------------
def convert():
    Gui.Selection.clearSelection()
    fs.menu("MODIFY", "Convert to Sheet Metal")


def convert_click():
    h.fit()
    h.click(fs.TUBE_FRONT)


def convert_ok():
    fs.settle()
    p = fs.sheet_panel()
    h.check("thickness 1.000 mm", p is not None and p.thickness.text() == "1.000 mm")
    fs.ok()


def is_sheet_metal(expect, where):
    from sciforge import sheetmetal

    fs.settle()
    body = fs.body()
    titles = fs.timeline_titles()
    step = any(t.startswith("Convert to Sheet Metal") for t in titles)
    h.check(
        "%s: sheet metal %s" % (where, "yes" if expect else "no"),
        sheetmetal.is_sheet_metal_body(body) == expect,
    )
    h.check("%s: Convert step %s" % (where, "there" if expect else "gone"), step == expect, titles)


def converted():
    h.check("Convert dialog closed", not fs.dialog_open())
    is_sheet_metal(True, "OK")


def undo_convert():
    fs.undo()


def convert_undone():
    is_sheet_metal(False, "Ctrl+Z")


def redo_convert():
    fs.redo()


def convert_redone():
    is_sheet_metal(True, "Ctrl+Y")
    h.check("shape unchanged", fs.close(fs.volume(), s["volume"]), fs.volume())


# -- 2. Rip: a refused pick after a good preview ----------------------------------------
def rip_edge():
    Gui.Selection.clearSelection()
    h.ribbon("Rip")


def rip_edge_click():
    p = fs.sheet_panel()
    h.check("Rip dialog open, Along Edge", p is not None and p.type_key() == "edge")
    h.fit()
    h.click_edge(V(40, 2, 10))  # the right wall's line where it meets the corner bend


def rip_edge_preview():
    fs.settle()
    v = fs.volume()
    h.check("preview: a 1 mm gap (20 mm3)", fs.close(v, s["volume"] - 20, 2e-4), v)


def rip_click_arc():
    h.click_edge(V(fs.TUBE_CORNER.x, fs.TUBE_CORNER.y, 20))  # the bend's curved top rim


def rip_arc_refused():
    fs.settle()
    text = fs.message()
    h.check("the curved edge is refused", "straight edge" in text, text)


def rip_refused_ok():
    fs.ok()


def rip_ok_waits():
    fs.settle()
    h.check("OK refused while the pick is refused: dialog open", fs.dialog_open())
    text = fs.message()
    h.check("OK says why", "straight edge" in text, text)
    fs.no_popups("OK on a refused rip")


def rip_esc():
    fs.esc()


def rip_escaped():
    fs.settle()
    h.check("Esc closes the Rip", not fs.dialog_open())
    h.check("the tube is closed again", fs.close(fs.volume(), s["volume"]), fs.volume())
    titles = fs.timeline_titles()
    h.check("no Rip in the timeline", not any(t.startswith("Rip") for t in titles), titles)


# -- 3. Rip a corner face ----------------------------------------
def rip_face():
    Gui.Selection.clearSelection()
    h.ribbon("Rip")


def rip_face_type():
    p = fs.sheet_panel()
    h.check("Face offered", p is not None and fs.choose(p.kind, "Face"))


def rip_face_click():
    h.fit()
    h.click(fs.TUBE_CORNER)


def rip_face_ok():
    fs.settle()
    v = fs.volume()
    h.check("preview: the corner bend cut away", fs.close(v, s["volume"] - CORNER), v)
    fs.ok()


def rip_face_done():
    fs.settle()
    h.check("Rip closed", not fs.dialog_open())
    s["ripped"] = fs.volume()
    h.check("ripped", fs.close(s["ripped"], s["volume"] - CORNER), s["ripped"])


# -- 4. Unfold: OK follows what the dialog shows ----------------------------------------
def unfold():
    Gui.Selection.clearSelection()
    h.ribbon("Unfold")


def unfold_click():
    h.fit()
    h.click(fs.TUBE_FRONT)


def tick_all():
    fs.settle()
    p = fs.sheet_panel()
    if p is not None:
        fs.click_check(p.all_bends)


def all_flat():
    fs.settle()
    p = fs.sheet_panel()
    t = p.target if p is not None else None
    bb = t.Shape.BoundBox if t is not None else None
    length = max(bb.XLength, bb.YLength, bb.ZLength) if bb is not None else None
    h.check(
        "Unfold All Bends: the ripped tube lies flat (130.79 long)",
        length is not None and fs.close(length, fs.TUBE_FLAT),
        bb,
    )


def untick_all():
    p = fs.sheet_panel()
    if p is not None:
        fs.click_check(p.all_bends)


def asks_bends():
    fs.settle()
    p = fs.sheet_panel()
    h.check("Unfold All Bends unticked", p is not None and not p.all_bends.isChecked())
    text = fs.message()
    h.check("the dialog asks for bends", "bends" in text, text)


def unfold_refused_ok():
    fs.ok()


def unfold_ok_waits():
    fs.settle()
    h.check("OK with no bends is refused: dialog open", fs.dialog_open())
    text = fs.message()
    h.check("OK says why", "bends" in text, text)


def tick_again():
    p = fs.sheet_panel()
    if p is not None:
        fs.click_check(p.all_bends)


def unfold_ok():
    fs.settle()
    fs.ok()


def unfolded():
    fs.settle()
    h.check("Unfold closed", not fs.dialog_open())
    bb = fs.body().Shape.BoundBox
    length = max(bb.XLength, bb.YLength, bb.ZLength)
    h.check("the body is flat", fs.close(length, fs.TUBE_FLAT), bb)
    # the flat sheet is (36 + 26 + 36 + 26 + 3 BA) x 20 x 1: with K 0.44 a bend lays flat a
    # little shorter than its mid-thickness arc, so the volume is not the folded one
    h.check(
        "the flat sheet: 130.79 x 20 x 1", fs.close(fs.volume(), fs.TUBE_FLAT * 20), fs.volume()
    )


def refold():
    Gui.Selection.clearSelection()
    h.ribbon("Refold")


def refold_ok():
    fs.settle()
    h.check("Refold dialog open", fs.refold_panel() is not None)
    fs.ok()


def refolded():
    fs.settle()
    h.check("Refold closed", not fs.dialog_open())
    bb = fs.body().Shape.BoundBox
    h.check("folded again: 40 x 30 x 20", fs.close(bb.XLength, 40) and fs.close(bb.YLength, 30), bb)
    h.check("refolded volume", fs.close(fs.volume(), s["ripped"]), fs.volume())


# -- 5. Save and reopen ----------------------------------------
STEP_CLASSES = {
    "ConvertToSheetMetal": "ConvertFeature",
    "Rip": "RipFeature",
    "Unfold": "UnfoldFeature",
    "Refold": "RefoldFeature",
}


def save_reopen():
    doc = App.ActiveDocument
    doc.recompute()
    doc.saveAs(s["path"])
    h.check("saved", os.path.isfile(s["path"]), s["path"])
    App.closeDocument(doc.Name)
    App.openDocument(s["path"])
    App.ActiveDocument.recompute()


def _steps():
    from sciforge import bodies

    out = {}
    for obj in App.ActiveDocument.Objects:
        kind = bodies.kind(obj)
        if kind in STEP_CLASSES:
            out[kind] = obj
    return out


def reopened():
    from sciforge import bodies, sheetmetal

    steps = _steps()
    for kind, cls in sorted(STEP_CLASSES.items()):
        obj = steps.get(kind)
        h.check("reopened: %s step there" % kind, obj is not None)
        if obj is None:
            continue
        proxy = getattr(obj, "Proxy", None)
        h.check(
            "reopened: %s keeps its class %s" % (kind, cls),
            type(proxy).__name__ == cls,
            type(proxy).__name__,
        )
        h.check("reopened: %s valid" % kind, "Invalid" not in obj.State, obj.State)
        vp = getattr(getattr(obj, "ViewObject", None), "Proxy", None)
        h.check(
            "reopened: %s view provider" % kind,
            type(vp).__name__ == "ViewProviderFlatStep",
            type(vp).__name__,
        )
    body = next((b for b in bodies.list_bodies(App.ActiveDocument)), None)
    s["body2"] = body
    h.check(
        "reopened: still sheet metal", body is not None and sheetmetal.is_sheet_metal_body(body)
    )
    v = body.Shape.Volume if body is not None else 0.0
    h.check("reopened: same shape", fs.close(v, s["ripped"]), v)


def forced_recompute():
    steps = _steps()
    first = steps.get("ConvertToSheetMetal")
    if first is not None:
        first.touch()
    App.ActiveDocument.recompute()
    for kind, obj in sorted(steps.items()):
        h.check(
            "recomputed after reopening: %s valid" % kind, "Invalid" not in obj.State, obj.State
        )
    body = s.get("body2")
    v = body.Shape.Volume if body is not None else 0.0
    h.check("recomputed after reopening: same shape", fs.close(v, s["ripped"]), v)


def group_kept():
    from sciforge import timeline_ops

    items = timeline_ops.timeline(App.ActiveDocument, deps=False).items
    groups = {i.kind: i.group for i in items if i.kind in ("unfold", "refold")}
    h.check(
        "reopened: Unfold and Refold still grouped",
        groups.get("unfold") and groups.get("unfold") == groups.get("refold"),
        groups,
    )


def edit_rip():
    fs.tab("sheet_metal")
    h.fit()
    titles = [t for t in fs.timeline_titles() if t.startswith("Rip")]
    h.check("reopened: Rip in the timeline", bool(titles), fs.timeline_titles())
    if titles:
        fs.double_click_timeline(titles[0])


def edit_rip_open():
    fs.settle()
    p = fs.sheet_panel()
    h.check("reopened: Edit Rip open", p is not None and p.editing)
    h.check("reopened: type Face kept", p is not None and p.type_key() == "face")
    h.check("reopened: its face kept", p is not None and len(p.picks["face"]) == 1)


def edit_rip_cancel():
    fs.cancel()


def edit_rip_cancelled():
    fs.settle()
    h.check("Cancel closes Edit Rip", not fs.dialog_open())
    body = s.get("body2")
    v = body.Shape.Volume if body is not None else 0.0
    h.check("Cancel: unchanged", fs.close(v, s["ripped"]), v)


# -- 6. Flat pattern, Export DXF cancelled ----------------------------------------
def flat_pattern():
    Gui.Selection.clearSelection()
    h.ribbon("Create Flat Pattern")


def flat_click():
    h.fit()
    h.click(fs.TUBE_FRONT)


def flat_ok():
    fs.settle()
    text = fs.message()
    h.check("the dialog says 130.79 x 20.00", "130.79 x 20.00" in text, text)
    fs.ok()


def flat_open():
    fs.settle()
    h.check("FLAT PATTERN tab open", fs.current_tab() == "flat_pattern", fs.current_tab())


def export():
    h.ribbon("Export DXF")


def export_cancel():
    fs.settle()
    p = fs.export_panel()
    h.check("Export DXF dialog open", p is not None)
    if p is not None:
        p.path.setText(s["dxf"])
    fs.cancel()


def export_cancelled():
    fs.settle()
    h.check("Cancel closes Export DXF", not fs.dialog_open())
    h.check("Cancel writes no file", not os.path.exists(s["dxf"]), s["dxf"])
    h.check("still in the flat pattern", fs.current_tab() == "flat_pattern", fs.current_tab())


def finish():
    h.ribbon("Finish Flat Pattern")


def finished():
    fs.settle()
    h.check("back to the design's tabs", fs.current_tab() != "flat_pattern", fs.current_tab())
    body = s.get("body2")
    h.check("the folded part shown", body is not None and body.ViewObject.Visibility)
    fs.no_popups("the QA paths")


h.run(
    "flatpattern_qa_paths",
    [
        setup,
        not_sheet_metal,
        convert,
        convert_click,
        convert_ok,
        converted,
        undo_convert,
        convert_undone,
        redo_convert,
        convert_redone,
        rip_edge,
        rip_edge_click,
        rip_edge_preview,
        rip_click_arc,
        rip_arc_refused,
        rip_refused_ok,
        rip_ok_waits,
        rip_esc,
        rip_escaped,
        rip_face,
        rip_face_type,
        rip_face_click,
        rip_face_ok,
        rip_face_done,
        unfold,
        unfold_click,
        tick_all,
        all_flat,
        untick_all,
        asks_bends,
        unfold_refused_ok,
        unfold_ok_waits,
        tick_again,
        unfold_ok,
        unfolded,
        refold,
        refold_ok,
        refolded,
        save_reopen,
        reopened,
        forced_recompute,
        group_kept,
        edit_rip,
        edit_rip_open,
        edit_rip_cancel,
        edit_rip_cancelled,
        flat_pattern,
        flat_click,
        flat_ok,
        flat_open,
        export,
        export_cancel,
        export_cancelled,
        finish,
        finished,
    ],
)
