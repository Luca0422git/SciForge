# SPDX-License-Identifier: LGPL-2.1-or-later
"""Surface part 3, QA paths the builder's scenarios leave out (real input in the dialogs).

The design (built for the scenario): a 40 x 30 x 10 box whose four top edges are rounded r 3
(FreeCAD's fillet); a 30 x 30 patch at x 100 with a round hole r 5 at (115, 15); a cylinder
r 10, 30 high at (-60, 0).
Path F (Offset Sharp where OpenCASCADE cannot close the corners): SURFACE > Offset, click the
        box's top: the top, its four rounds and the four walls (Chain Selection: they are
        all tangent); type 2: Sharp Offset (the default) is refused with the reason
        ("Rounded Offset"), nothing is shown 10 km wide (OpenCASCADE's intersection join
        came back "valid" with faces 2e7 mm across); OK waits. Rounded Offset: 2981.67
        (measured), the offset top 2 above the box. OK: "Offset 1".
Path K (Untrim Keep Copy, save / reopen, delete): SURFACE > Untrim, Manual, click the hole's
        edge, Keep Copy, OK; Change Parameters lists no Extend Distance (Extend is off; the
        Offset lists its Distance). (Saved and reopened below: the closed patch (900) and the copy
        (900 - 25 pi) are back and fine.) Delete "Untrim 1" from the timeline: the copy body
        goes and the hole is back; Undo: both back. Double-click Untrim 1: Keep Copy read
        back; clear it: the copy goes; Cancel: the copy is back, the patch still closed.
Path I (Isoparametric Curve: an empty click, Esc, undo / redo, save / reopen): a sketch on XZ;
        Isoparametric Curve; a click on empty space: the panel asks for a face, nothing is
        kept; Esc: the tool ends, nothing kept. Again: click the cylinder, Esc: nothing kept.
        Again: click the cylinder, Enter: kept (one U curve 30 long); Ctrl+Z: gone; Ctrl+Y:
        back. Finish Sketch.
Path S (save / reopen): saved, closed, opened: Offset 1 (2981.67), the untrimmed patch and its
        copy, and the Isoparametric Curves (its proxy restored, one curve 30 long) are back,
        nothing red; a change of the cylinder's radius still moves the curve.
"""

import math
import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtWidgets

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import sketch_tools_steps as sk
from SciForgeTests.gui import surface_steps as st
from SciForgeTests.gui import timeline_input as tl

V = App.Vector
s = {}
HOLED = 900 - 25 * math.pi
ROUNDED_TOP = 2981.669  # measured: the 9 faces offset 2 with Rounded corners


def doc():
    return App.ActiveDocument


def by_label(label):
    found = doc().getObjectsByLabel(label)
    return found[0] if found else None


def new_design():
    import Part
    import Sketcher

    from sciforge import bodies, commands, extrude, sketch_ui, surface

    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("Surface3QA")
    body = commands.ensure_body()
    planes = sketch_ui.origin_planes(body)
    base = sketch_ui.create_sketch(body, (planes["XY_Plane"], ""))
    h.draw_rectangle(base, 0, 0, 40, 30)
    pad = extrude.make(body, base, {"distance": 10.0})
    doc().recompute()
    top = [
        "Edge%d" % (i + 1)
        for i, e in enumerate(pad.Shape.Edges)
        if e.BoundBox.ZMin > 10 - 1e-6 and e.BoundBox.ZMax < 10 + 1e-6
    ]
    rounds = body.newObject("PartDesign::Fillet", "Fillet")
    rounds.Base = (pad, top)
    rounds.Radius = 3.0
    commands.leave_edit()
    doc().recompute()
    s["box"] = body
    s["box_sketch"] = base
    # the patch with a hole, away from the box
    sketch = sketch_ui.create_sketch(body, (planes["XY_Plane"], ""))
    st.add_lines(sketch, [(100, 0), (130, 0), (130, 30), (100, 30)], closed=True)
    sketch.addGeometry(Part.Circle(V(115, 15, 0), V(0, 0, 1), 5))
    commands.leave_edit()
    doc().recompute()
    refs = [(sketch, "Edge%d" % (i + 1)) for i in range(5)]
    step = surface.build("patch", {"refs": refs}, {})
    doc().recompute()
    s["patch"] = bodies.body_of(step)
    s["patch_sketch"] = sketch
    # the cylinder of the isoparametric curves, a body of its own
    from sciforge import components

    cyl_body = components.new_body_in(doc(), components.active_component(doc()))
    circ = sketch_ui.create_sketch(cyl_body, (sketch_ui.origin_planes(cyl_body)["XY_Plane"], ""))
    c = circ.addGeometry(Part.Circle(V(-60, 0, 0), V(0, 0, 1), 10))
    s["radius"] = circ.addConstraint(Sketcher.Constraint("Radius", c, 10.0))
    circ.addConstraint(Sketcher.Constraint("DistanceX", -1, 1, c, 3, -60.0))
    circ.addConstraint(Sketcher.Constraint("DistanceY", -1, 1, c, 3, 0.0))
    commands.leave_edit()
    doc().recompute()
    s["cyl_step"] = extrude.make(cyl_body, circ, {"distance": 30.0})
    commands.leave_edit()
    doc().recompute()
    s["circle"] = circ
    s["cyl"] = bodies.body_of(s["cyl_step"])
    for sketch_ in (base, sketch, circ):
        bodies.set_shown(sketch_, False)
    doc().recompute()
    s["bodies"] = len(st.bodies())
    h.fit()


def offset_menu():
    h.check(
        "the box with rounded top edges",
        st.volume(s["box"]) < 12000.0 - 1.0,
        st.volume(s["box"]),
    )
    h.check("the cylinder", st.near(st.volume(s["cyl"]), math.pi * 100 * 30, 1e-6))
    h.click_empty()
    st.tab("SURFACE")
    st.menu("CREATE", "Offset")


def click_top():
    p = st.panel()
    h.check("Offset dialog open", p is not None and p.kind == "offset")
    if p is None:
        return
    h.check("Sharp Offset by default", p.options["offset_type"] == "sharp", p.options)
    h.click(V(20, 15, 10))


def type_two():
    st.settle()
    p = st.panel()
    count = len(p.picks["faces"]) if p is not None else 0
    h.check("the top, its rounds and the walls (Chain Selection: all tangent)", count == 9, count)
    st.type_field("distance", "2")


def sharp_refused():
    st.settle()
    p = st.panel()
    text = st.message()
    h.check("Sharp is refused with the reason", "sharp corners" in text, text)
    h.check("and points to Rounded Offset", "Rounded Offset" in text, text)
    body = st.step_body(p) if p is not None else None
    reach = 0.0
    if body is not None and not body.Shape.isNull() and body.Shape.Faces:
        reach = body.Shape.BoundBox.DiagonalLength
    h.check("no surface kilometres wide is shown", reach < 1000.0, reach)
    st.ok()


def ok_waits():
    st.settle()
    p = st.panel()
    h.check("OK waits while Sharp cannot be made", p is not None)
    st.choose("offset_type", "Rounded Offset")


def rounded_made():
    st.settle()
    body = st.step_body()
    s["offset"] = body
    area = st.area(body)
    h.check("Rounded: 2981.67", st.near(area, ROUNDED_TOP, 1e-5), area)
    if body is not None:
        b = body.Shape.BoundBox
        h.check("2 above the box", st.near(b.ZMax, 12.0), b)
    h.check("no warning left", "sharp corners" not in st.message(), st.message())
    st.ok()


def offset_done():
    h.check("dialog closed", st.panel() is None)
    titles = st.timeline_titles()
    h.check("Offset 1 in the timeline", "Offset 1" in titles, titles)
    s["offset_label"] = s["offset"].Label if s.get("offset") is not None else ""
    rows = _parameter_rows("SurfaceOffset")
    h.check("Change Parameters: the Offset's Distance (2)", rows == [("Distance", 2.0)], rows)
    # frame the patch (from the whole design its hole's edge is a few pixels from the face)
    Gui.Selection.clearSelection()
    Gui.Selection.addSelection(doc().Name, s["patch"].Tip.Name)
    Gui.SendMsgToActiveView("ViewSelection")
    Gui.Selection.clearSelection()
    h.click_empty()
    st.menu("MODIFY", "Untrim")


def choose_manual():
    p = st.panel()
    h.check("Untrim dialog open", p is not None and p.kind == "untrim")
    if p is None:
        return
    st.choose("loop_type", "Manual")


def click_hole():
    st.settle()
    p = st.panel()
    h.check("the Loops box takes the clicks", p is not None and p.active == "loops")
    h.check("clicked the hole's edge", h.click_edge(V(115, 10, 0)))


def keep_copy():
    st.settle()
    p = st.panel()
    h.check("1 loop", p is not None and len(p.picks["loops"]) == 1, (p and p.picks, st.message()))
    st.toggle_check("keep_copy")


def untrim_ok():
    st.settle()
    p = st.panel()
    from sciforge import bodies, surface

    pieces = surface.pieces_of(p.step) if p is not None and p.step is not None else []
    h.check("Keep Copy: one copy", len(pieces) == 1, pieces)
    if pieces:
        s["copy_label"] = bodies.body_of(pieces[0]).Label
    st.ok()


def untrim_done():
    h.check("dialog closed", st.panel() is None)
    h.check("the hole closed (900)", st.near(st.area(s["patch"]), 900.0, 1e-6))
    copy = by_label(s.get("copy_label", "?"))
    h.check("the copy (900 - 25 pi)", copy is not None and st.near(st.area(copy), HOLED, 1e-6))
    s["patch_label"] = s["patch"].Label
    rows = _parameter_rows("Untrim")
    h.check("Change Parameters: no Extend Distance while Extend is off", rows == [], rows)
    h.fit()


def _parameter_rows(kind):
    """[(label, value)] Change Parameters lists for the steps of SciForgeType `kind`."""
    from sciforge import parameters

    names = [o.Name for o in doc().Objects if getattr(o, "SciForgeType", "") == kind]
    return [
        (r["label"], round(r["value"], 6))
        for r in parameters.model_parameters(doc())
        if r["object"] in names
    ]


# -- Isoparametric Curve ----------------------------------------------------------------------
def create_sketch():
    h.click_empty()
    st.tab("SOLID")
    h.ribbon("Create Sketch")


def pick_plane():
    pl.click_square("XZ_Plane")


def start_tool():
    sketch = h.in_sketch()
    h.check("a sketch on XZ open", sketch is not None)
    s["sk"] = sketch
    si.menu_item("CREATE", "Isoparametric Curve")


def _box(name):
    for w in Gui.getMainWindow().findChildren(QtWidgets.QWidget, name):
        if w.isVisible():
            return w
    return None


def _isos():
    from sciforge import sketch_companions, surface_iso

    sketch = s.get("sk")
    if sketch is None:
        return []
    return [o for o in sketch_companions.companions(sketch) if surface_iso.is_iso(o)]


def click_nothing():
    h.check("Isoparametric Curve runs", sk.tool_title() == "Isoparametric Curve", sk.tool_title())
    si.click(V(-20, 0, 25))  # between the cylinder and the box, above both


def nothing_picked():
    t = sk.tool()
    h.check("still waiting for a face", t is not None and t.face is None, t and t.face)
    hint = _box("SciForgeIsoHint")
    text = hint.text() if hint is not None else ""
    h.check("the panel asks for a face", "face" in text, text)
    ok = _box("SciForgeIsoOK")
    h.check("OK greyed", ok is not None and not ok.isEnabled())
    h.gl_widget().setFocus()
    sk.esc()


def esc_nothing_kept():
    h.check("Esc ended the tool", sk.tool_title() != "Isoparametric Curve", sk.tool_title())
    h.check("its panel is gone", _box("SciForgeIsoCurve") is None)
    h.check("nothing kept", not _isos(), _isos())
    h.check("still in the sketch", h.in_sketch() is not None)
    si.menu_item("CREATE", "Isoparametric Curve")


def click_face():
    h.check("the tool again", sk.tool_title() == "Isoparametric Curve", sk.tool_title())
    si.click(V(-60, -10, 12), V(0.0, -1.0, 0))


def picked_then_esc():
    t = sk.tool()
    h.check("the cylinder's face is picked", t is not None and t.face is not None)
    h.gl_widget().setFocus()
    sk.esc()


def esc_after_pick():
    h.check("Esc ended it", sk.tool_title() != "Isoparametric Curve", sk.tool_title())
    h.check("Esc kept nothing", not _isos(), _isos())
    si.menu_item("CREATE", "Isoparametric Curve")


def click_face_again():
    si.click(V(-60, -10, 12), V(0.0, -1.0, 0))


def enter_keeps():
    t = sk.tool()
    h.check("picked again", t is not None and t.face is not None)
    h.gl_widget().setFocus()
    sk.enter()


enter_keeps.wait_ms = 900


def kept():
    found = _isos()
    h.check("kept: one Isoparametric Curves", len(found) == 1, found)
    if found:
        obj = found[0]
        s["iso"] = obj.Name
        lengths = [round(e.Length, 3) for e in obj.Shape.Edges]
        h.check("one U curve 30 long", lengths == [30.0], lengths)
    h.gl_widget().setFocus()
    sk.undo()


def undone():
    h.check("Ctrl+Z: the curves are gone", not _isos(), _isos())
    h.check("Ctrl+Z left the sketch open", h.in_sketch() is not None)
    h.gl_widget().setFocus()
    sk.redo()


def redone():
    found = _isos()
    h.check("Ctrl+Y: back", len(found) == 1, found)
    if found:
        s["iso"] = found[0].Name
    h.ribbon("Finish Sketch")


# -- save / reopen --------------------------------------------------------------------------------
def save():
    h.check("left the sketch", h.in_sketch() is None)
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-surface3qa-"), "surface3qa.FCStd")
    s["path"] = path
    s["iso_label"] = doc().getObject(s["iso"]).Label if doc().getObject(s.get("iso", "")) else ""
    s["sketch_label"] = s["sk"].Label
    s["circle_label"] = s["circle"].Label
    doc().saveAs(path)
    h.check("saved", os.path.isfile(path), path)


def close():
    App.closeDocument(doc().Name)


def reopen():
    App.openDocument(s["path"])
    h.fit()


def reopened():
    from sciforge import surface_iso, timeline_ops

    offset = by_label(s.get("offset_label", "?"))
    h.check("Offset 1 back (2981.67)", st.near(st.area(offset), ROUNDED_TOP, 1e-5))
    patch = by_label(s["patch_label"])
    copy = by_label(s.get("copy_label", "?"))
    h.check("the untrimmed patch (900)", st.near(st.area(patch), 900.0, 1e-6), st.area(patch))
    h.check("the copy (900 - 25 pi)", st.near(st.area(copy), HOLED, 1e-6), st.area(copy))
    iso = by_label(s.get("iso_label", "?"))
    h.check("the Isoparametric Curves are back", iso is not None)
    if iso is not None:
        h.check("its proxy is restored", surface_iso.is_iso(iso), type(iso.Proxy))
        iso.touch()
        doc().recompute()
        lengths = [round(e.Length, 3) for e in iso.Shape.Edges]
        h.check("one U curve 30 long", lengths == [30.0], lengths)
        h.check("and fine", "Invalid" not in iso.State, iso.State)
    red = [
        o.Label
        for o in doc().Objects
        if "Invalid" in o.State or timeline_ops.problem(o)[0] == "error"
    ]
    h.check("nothing red after the reopen", not red, red)
    circle = by_label(s["circle_label"])
    if circle is not None:
        circle.setDatum(s["radius"], App.Units.Quantity("12 mm"))
        doc().recompute()


def iso_follows():
    iso = by_label(s.get("iso_label", "?"))
    h.check("the curve follows the radius after the reopen", iso is not None)
    if iso is not None:
        # Single keeps its Distance from the face's first edge (47.12 mm round, Fusion's
        # distance): on r 12 that is 225 degrees round instead of 270
        b = iso.Shape.BoundBox
        r = math.hypot(b.XMin + 60.0, b.YMin)
        h.check("on the cylinder r 12", st.near(r, 12.0, 1e-6), b)
        angle = math.degrees(math.atan2(b.YMin, b.XMin + 60.0)) % 360.0
        h.check("47.12 mm round from the seam (225 degrees)", st.near(angle, 225.0, 1e-3), angle)
    tl.menu("Untrim 1", "Delete")


def untrim_deleted():
    patch = by_label(s["patch_label"])
    copy = by_label(s.get("copy_label", "?"))
    h.check("deleting Untrim 1 brings the hole back", st.near(st.area(patch), HOLED, 1e-6))
    h.check("and takes its copy away", copy is None, copy and copy.Label)
    tl.undo()


def delete_undone():
    patch = by_label(s["patch_label"])
    copy = by_label(s.get("copy_label", "?"))
    h.check("Undo: the patch closed again", st.near(st.area(patch), 900.0, 1e-6), st.area(patch))
    h.check("and the copy back", copy is not None and st.near(st.area(copy), HOLED, 1e-6))
    tl.no_popups("the Untrim delete and its undo")
    h.check("edited from the timeline", st.double_click_timeline("Untrim 1"))


def edit_keep_copy_off():
    st.settle()
    p = st.panel()
    h.check("Untrim dialog for editing", p is not None and p.kind == "untrim" and p.editing)
    if p is None:
        return
    h.check("Keep Copy read back after the reopen", p.rows["keep_copy"][0].isChecked())
    st.toggle_check("keep_copy")


def copy_gone_in_preview():
    st.settle()
    h.check("Keep Copy off: the copy goes", by_label(s.get("copy_label", "?")) is None)
    st.cancel()


def cancel_brings_copy_back():
    st.settle()
    h.check("dialog closed", st.panel() is None)
    copy = by_label(s.get("copy_label", "?"))
    h.check("Cancel: the copy is back", copy is not None and st.near(st.area(copy), HOLED, 1e-6))
    patch = by_label(s["patch_label"])
    h.check("and the patch still closed", st.near(st.area(patch), 900.0, 1e-6), st.area(patch))


h.run(
    "surface3_qa",
    [
        new_design,
        offset_menu,
        click_top,
        type_two,
        sharp_refused,
        ok_waits,
        rounded_made,
        offset_done,
        choose_manual,
        click_hole,
        keep_copy,
        untrim_ok,
        untrim_done,
        create_sketch,
        pick_plane,
        start_tool,
        click_nothing,
        nothing_picked,
        esc_nothing_kept,
        click_face,
        picked_then_esc,
        esc_after_pick,
        click_face_again,
        enter_keeps,
        kept,
        undone,
        redone,
        save,
        close,
        reopen,
        reopened,
        iso_follows,
        untrim_deleted,
        delete_undone,
        edit_keep_copy_off,
        copy_gone_in_preview,
        cancel_brings_copy_back,
    ],
)
