# SPDX-License-Identifier: LGPL-2.1-or-later
"""More sketch-area picking (sketch_areas.py has the basics), only real input.

1. A sketch on the top face of a block (Luca: "when I create a sketch on an item") with
   two overlapping circles: three areas (the lens and two crescents). Inside the open
   sketch: click the lens, Shift+click the left crescent, E: both are extruded (one
   circle's worth). Clicking the lens in the dialog drops it: the crescent only.
2. Switching SciForge off gives FreeCAD's own preferences back (no sketch areas made);
   a sketch made then (an "older" sketch, MakeInternals off) gets its areas when it is
   opened, without an undo step of its own: Finish Sketch leaves the undo list as it was.
   Its ring can then be clicked after Finish Sketch and extruded with E.
3. Speed: a 50-curve plate (outline, 30 holes, 4 slots). FreeCAD's areas, the shading of
   the open sketch and the light-up under the mouse stay quick; a hole is picked inside
   the sketch and E extrudes that hole's disc only.

Hand-derived: block 40 x 30 x 10 = 12000. Circles r 8, centres 8 apart: each 64 pi; the
lens 2 r^2 acos(d / 2r) - (d / 2) sqrt(4 r^2 - d^2); a crescent = circle - lens.
(The older sketch and the plate lie beside the block: there only the picked profiles are
checked, an extrude there would be a separate solid.)"""
import math
import time

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets

from SciForgeTests.gui import arrow_input as arrows
from SciForgeTests.gui import blend_steps as bs
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import widget_input as w

V = App.Vector
SHIFT = QtCore.Qt.ShiftModifier
SKETCHER = "User parameter:BaseApp/Preferences/Mod/Sketcher"
R, D = 8.0, 8.0
LENS = 2 * R * R * math.acos(D / (2 * R)) - (D / 2) * math.sqrt(4 * R * R - D * D)
CIRCLE = math.pi * R * R
CRESCENT = CIRCLE - LENS
s = {}


def near(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


def panel():
    from sciforge import extrude_ui

    return extrude_ui.ExtrudePanel.last


def open_panel():
    p = panel()
    return p if p is not None and not p._closed and Gui.Control.activeDialog() else None


def session():
    from sciforge import sketch_mode

    return sketch_mode.current()


def area_at(sketch, point):
    from sciforge import sketch_areas_core as core

    x, y = h.to_sketch(sketch, point)
    return core.region_at(session().areas.regions, x, y)


def picked():
    ses = session()
    return ses.areas.picked_indices() if ses is not None else None


def area_name(sketch, point):
    """ "InternalFaceN" of a finished sketch's area around a global point, read from the
    sketch as it is (SciForge's extrude.regions would turn the areas on by itself)."""
    from sciforge import profile_pick

    shape = sketch.InternalShape
    if shape.isNull():
        return None
    placement = sketch.getGlobalPlacement()
    for i, face in enumerate(shape.Faces, start=1):
        face = face.copy()
        face.Placement = placement.multiply(face.Placement)
        if profile_pick.inside(face, point):
            return "InternalFace%d" % i
    return None


def profile_names():
    p = open_panel()
    return sorted(sub for _obj, sub in (p.profiles if p else []))


def selection():
    return [(x.ObjectName, list(x.SubElementNames)) for x in Gui.Selection.getSelectionEx()]


def step_button(name):
    from sciforge import timeline_ui

    widget = timeline_ui.widget()
    widget.refresh()
    QtWidgets.QApplication.processEvents()
    for button in widget._buttons:
        if button.item.name == name:
            return button
    h.check("timeline has %r" % name, False, widget.titles())
    return None


# -- 1. a sketch on the block's top face, overlapping circles ----------------------------
def sketch_on_top():
    s["top"] = h.body().Shape.BoundBox.ZMax
    h.ribbon("Create Sketch")


def click_top():
    h.click(V(30, 25, s["top"]))


def draw_circles():
    sk = h.in_sketch()
    h.check("sketch open on the top face", sk is not None)
    if sk is None:
        return
    s["face_sketch"] = sk
    z = s["top"]
    s["lens"], s["left"], s["right"] = V(20, 15, z), V(11, 15, z), V(29, 15, z)
    for cx in (16.0, 24.0):
        x, y = h.to_sketch(sk, V(cx, 15, z))
        h.draw_circle(sk, x, y, R)


def pick_lens():
    ses = session()
    h.check("three areas shaded (lens, two crescents)", ses and ses.shading.count == 3)
    si.click(s["lens"])


def shift_crescent():
    sk = s["face_sketch"]
    h.check("the lens picked", picked() == [area_at(sk, s["lens"])], picked())
    si.click_held(s["left"], SHIFT)


def press_e():
    sk = s["face_sketch"]
    h.check(
        "Shift+click adds the left crescent",
        picked() == [area_at(sk, s["lens"]), area_at(sk, s["left"])],
        picked(),
    )
    h.shot("1-lens-and-crescent")
    h.press("e")


def lens_and_crescent():
    sk = s["face_sketch"]
    want = sorted([area_name(sk, s["lens"]), area_name(sk, s["left"])])
    h.check("E extrudes the lens and the left crescent", profile_names() == want, profile_names())
    arrows.give_distance("10")  # Extrude starts at 0 (Fusion): type the distance
    v = h.solid_volume()
    h.check("block + one circle's worth (64 pi) 10 high", near(v, 12000.0 + CIRCLE * 10), v)
    h.fit()
    # the lens (seen through the preview, as in Fusion), away from the distance arrow
    h.click(V(20, 10, s["top"]))


def crescent_only():
    sk = s["face_sketch"]
    want = [area_name(sk, s["left"])]
    h.check("clicking the lens in the dialog drops it", profile_names() == want, profile_names())
    v = h.solid_volume()
    h.check("block + the crescent 10 high", near(v, 12000.0 + CRESCENT * 10), v)
    h.task_button("OK")


def crescent_done():
    v = h.solid_volume()
    h.check("OK keeps block + crescent", near(v, 12000.0 + CRESCENT * 10), v)
    s["volume"] = v
    Gui.activateWorkbench("PartDesignWorkbench")


# -- 2. SciForge off, an older sketch -----------------------------------------------------
def freecad_preferences():
    group = App.ParamGet(SKETCHER)
    h.check(
        "SciForge off: FreeCAD's own 'make sketch areas' preference is back",
        not group.GetBool("MakeInternals", False),
        group.GetBools(),
    )
    general = App.ParamGet(SKETCHER + "/General")
    h.check(
        "and FreeCAD's own area colour",
        "SketchFaceColor" not in general.GetUnsigneds(),
        general.GetUnsigneds(),
    )
    # Also after an earlier session that ended with SciForge on (CI runs several scenarios in
    # one profile; FreeCAD saves its preferences when it quits): FreeCAD's own keys are back.
    distx = Gui.Command.get("Sketcher_ConstrainDistanceX")
    h.check(
        "and FreeCAD's own L key",
        distx is not None and distx.getShortcut() == "L",
        distx and distx.getShortcut(),
    )
    import Part
    import Sketcher

    from sciforge import sketch_ui

    doc = App.ActiveDocument
    body = h.body()
    xy = sketch_ui.origin_planes(body)["XY_Plane"]
    doc.openTransaction("Old sketch")
    sk = body.newObject("Sketcher::SketchObject", "OldSketch")
    sk.AttachmentSupport = [(xy, "")]
    sk.MapMode = "FlatFace"
    h.draw_rectangle(sk, 60, 0, 80, 20)
    sk.addGeometry(Part.Circle(V(70, 10, 0), V(0, 0, 1), 5))
    sk.addConstraint(Sketcher.Constraint("Radius", sk.GeometryCount - 1, 5))
    doc.recompute()
    doc.commitTransaction()
    s["old"] = sk
    h.check("a sketch made with SciForge off has no areas", not sk.MakeInternals)
    Gui.activateWorkbench("SciForgeWorkbench")


def sciforge_back():
    h.check(
        "SciForge on again: new sketches make their areas",
        App.ParamGet(SKETCHER).GetBool("MakeInternals", False),
    )
    # something to redo: opening the older sketch must not throw it away
    doc = App.ActiveDocument
    doc.openTransaction("Rename")
    s["old"].Label = "Renamed"
    doc.commitTransaction()
    h.check("Undo button in the application bar", ui.quick_access("Undo"))


def open_old_sketch():
    doc = App.ActiveDocument
    s["undo"], s["redo"] = list(doc.UndoNames), list(doc.RedoNames)
    h.check("the rename is undone (Redo has it)", s["redo"][:1] == ["Rename"], s["redo"])
    w.double_click(step_button(s["old"].Name))


def old_sketch_open():
    sk = s["old"]
    doc = App.ActiveDocument
    h.check("the older sketch is open", h.in_sketch() is sk, h.in_sketch())
    h.check("opening it turns its areas on", sk.MakeInternals)
    h.check(
        "without an undo step, and Redo is kept",
        (list(doc.UndoNames), list(doc.RedoNames)) == (s["undo"], s["redo"]),
        (doc.UndoNames[:3], doc.RedoNames[:3]),
    )
    h.ribbon("Finish Sketch")


def old_sketch_finished():
    sk = s["old"]
    undo = list(App.ActiveDocument.UndoNames)
    h.check(
        "Finish Sketch adds at most FreeCAD's usual 'Sketch recompute' step",
        undo in (s["undo"], ["Sketch recompute"] + s["undo"]),
        (undo[:4], s["undo"][:4]),
    )
    faces = 0 if sk.InternalShape.isNull() else len(sk.InternalShape.Faces)
    h.check("the finished older sketch has its two areas (ring and disc)", faces == 2, faces)
    h.fit()
    s["ring"] = V(62, 2, 0)
    h.click(s["ring"])


def ring_selected():
    sk = s["old"]
    want = [(sk.Name, [area_name(sk, s["ring"])])]
    h.check(
        "the older sketch's ring can be clicked after Finish Sketch",
        selection() == want,
        selection(),
    )
    h.press("e")


def ring_extruded():
    sk = s["old"]
    h.check("E extrudes the ring", profile_names() == [area_name(sk, s["ring"])], profile_names())
    h.task_button("Cancel")


# -- 3. speed with 50 curves -------------------------------------------------------------
def plate():
    from sciforge import sketch_ui

    h.check("Cancel: the part as it was", near(h.solid_volume(), s["volume"]), h.solid_volume())
    body = h.body()
    planes = sketch_ui.origin_planes(body)
    sk = sketch_ui.create_sketch(body, (planes["XY_Plane"], ""))
    h.draw_rectangle(sk, 0, 100, 120, 180)
    import Part

    for i in range(6):  # 30 holes r 4
        for j in range(5):
            sk.addGeometry(Part.Circle(V(12 + i * 16, 112 + j * 12, 0), V(0, 0, 1), 4))
    for k in range(4):  # 4 slots: 2 lines + 2 arcs each
        bs.draw_slot(sk, 106, 110 + k * 18, 114, 110 + k * 18, 6)
    App.ActiveDocument.recompute()
    s["plate"] = sk
    h.check("the plate has 50 curves", sk.GeometryCount == 50, sk.GeometryCount)
    times = []
    for _ in range(3):
        sk.touch()
        t = time.time()
        sk.recompute()
        times.append(time.time() - t)
    faces = len(sk.InternalShape.Faces)
    s["recompute"] = min(times)
    print(
        "[SciForge] sketch_areas_more: 50-curve plate recompute with areas %.3f s, %d areas"
        % (s["recompute"], faces),
        flush=True,
    )
    h.check("FreeCAD finds the plate, 30 hole discs and 4 slot areas", faces == 35, faces)
    h.check(
        "recomputing the 50-curve sketch with its areas takes < 0.5 s", s["recompute"] < 0.5, times
    )
    w.double_click(step_button(sk.Name))


def plate_open():
    ses = session()
    h.check("the plate sketch is open", h.in_sketch() is s["plate"], h.in_sketch())
    if ses is None:
        return
    t = time.time()
    ses.shading.update()
    shading = time.time() - t
    t = time.time()
    ses.areas.refresh(ses.shading.shaded)
    areas = time.time() - t
    print(
        "[SciForge] sketch_areas_more: open plate sketch: shading %.3f s, pickable areas %.3f s"
        % (shading, areas),
        flush=True,
    )
    h.check("shading the open 50-curve sketch takes < 1 s", shading + areas < 1.0, shading)
    h.check("making its areas pickable takes < 0.1 s", areas < 0.1, areas)
    h.check("35 areas shaded", ses.shading.count == 35, ses.shading.count)
    # halfway between the hole's centre point and its circle (either would be picked)
    s["hole"] = V(12 + 2 * 16 + 2.0, 112 + 2 * 12, 0)
    zoom_on(s["hole"], 40.0)  # Look At turned the camera to the plate but did not zoom
    h.uncover(s["hole"])
    for f in (3.0, 1.5, 0.5):
        h.move(h.screen_point(s["hole"] + V(0.4, 0.2, 0) * f))
    h.move(h.screen_point(s["hole"]))
    QtCore.QTimer.singleShot(120, hover_timed)


def zoom_on(point, height):
    """Look at `point` with `height` mm of the plate on screen, as a person zooms in."""
    camera = h.view().getCameraNode()
    p = camera.position.getValue()
    camera.position.setValue(point.x, point.y, p[2])
    if hasattr(camera, "height"):
        camera.height.setValue(height)
    QtWidgets.QApplication.processEvents()


def hover_timed():
    ses = session()
    if ses is None:
        return
    t = time.time()
    ses.areas._hover()
    s["hover_time"] = time.time() - t
    s["hovered"] = ses.areas.hovered


def pick_hole():
    print(
        "[SciForge] sketch_areas_more: light-up under the mouse %.4f s" % s.get("hover_time", -1),
        flush=True,
    )
    h.check(
        "the light-up under the mouse takes < 30 ms",
        s.get("hover_time", 1) < 0.03,
        s.get("hover_time"),
    )
    h.check(
        "the hole under the mouse lights up",
        s.get("hovered") == area_at(s["plate"], s["hole"]),
        s.get("hovered"),
    )
    si.click(s["hole"])


def hole_picked():
    h.check("the hole is picked", picked() == [area_at(s["plate"], s["hole"])], picked())
    h.press("e")


def hole_extruded():
    names = profile_names()
    h.check("E extrudes that hole's disc only", names == [area_name(s["plate"], s["hole"])], names)
    h.task_button("Cancel")


def worst_case():
    """Info: 50 curves that all cross each other (a grid, circles and diagonals)."""
    import Part

    doc = App.ActiveDocument
    sk = doc.addObject("Sketcher::SketchObject", "Crossing")
    sk.Placement = App.Placement(V(200, 0, 0), App.Rotation())
    for i in range(5):
        for j in range(5):
            sk.addGeometry(Part.Circle(V(i * 12, j * 12, 0), V(0, 0, 1), 4))
    for i in range(6):
        sk.addGeometry(Part.LineSegment(V(-6 + i * 12, -6, 0), V(-6 + i * 12, 54, 0)))
        sk.addGeometry(Part.LineSegment(V(-6, -6 + i * 12, 0), V(54, -6 + i * 12, 0)))
    for i in range(1, 14):
        sk.addGeometry(Part.LineSegment(V(-6, -6 + i * 4.5, 0), V(-6 + i * 4.5, -6, 0)))
    sk.touch()
    t = time.time()
    sk.recompute()
    dt = time.time() - t
    print(
        "[SciForge] sketch_areas_more: 50 crossing curves: areas in %.3f s (%d areas)"
        % (dt, len(sk.InternalShape.Faces)),
        flush=True,
    )
    h.check("even 50 crossing curves make their areas in < 2 s", dt < 2.0, dt)
    doc.removeObject(sk.Name)
    doc.recompute()


steps = bs.box_steps("AreasMore") + [
    sketch_on_top,
    click_top,
    draw_circles,
    pick_lens,
    shift_crescent,
    press_e,
    lens_and_crescent,
    crescent_only,
    crescent_done,
    freecad_preferences,
    sciforge_back,
    open_old_sketch,
    old_sketch_open,
    old_sketch_finished,
    ring_selected,
    ring_extruded,
    plate,
    plate_open,
    pick_hole,
    hole_picked,
    hole_extruded,
    worst_case,
]
h.run("sketch_areas_more", si.watched(steps))
