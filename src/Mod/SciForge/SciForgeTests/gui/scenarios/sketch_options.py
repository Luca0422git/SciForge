# SPDX-License-Identifier: LGPL-2.1-or-later
"""The SKETCH PALETTE, Create Sketch's Cancel, Include 3D Geometry and Look At.

A block is made by clicks. Create Sketch, then Cancel (and Esc): no sketch is made.
Create Sketch on the top face; a circle and its dimension. Every palette option is
clicked off and on again and must change what is shown: Sketch Grid, Slice, Show
Profile, Show Dimensions, Show Constraints, Show Points, Show Projected Geometries.
Include 3D Geometry on a vertical edge adds a reference (not a profile). Look At
turns the camera back to the sketch. Linetype turns the selected circle into
construction. Every option ends as it started (they are remembered).
"""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import sketch_input as si

V = App.Vector
s = {}


def sketches():
    return [o for o in App.ActiveDocument.Objects if o.TypeId == "Sketcher::SketchObject"]


def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("SketchOptions")
    h.fit()


def create_sketch():
    h.ribbon("Create Sketch")


def pick_xy_plane():
    h.click(V(12, -8, 0))


def rect_key():
    h.press("r")


def rect_a():
    si.click(V(0, 0, 0))


def rect_b():
    si.click(V(40, 30, 0))


def finish_1():
    h.press(QtCore.Qt.Key_Escape)
    h.ribbon("Finish Sketch")


def extrude():
    h.fit()
    h.press("e")


def extrude_ok():
    h.task_button("OK")


def block():
    h.check("block 40 x 30 x 10", si.near(h.solid_volume(), 12000.0, 1e-6), h.solid_volume())
    s["top"] = h.body().Shape.BoundBox.ZMax
    s["sketches"] = len(sketches())
    h.fit()


def create_then_cancel():
    h.ribbon("Create Sketch")


def cancel():
    h.check("Create Sketch waits for a plane, no pop-up", not h.popups(), h.popups())
    h.task_button("Cancel")


def cancelled():
    h.check("Cancel: no sketch made", len(sketches()) == s["sketches"], len(sketches()))
    h.check("Cancel: not in a sketch", h.in_sketch() is None)
    h.check("Cancel: panel closed", not Gui.Control.activeDialog())


def create_then_esc():
    h.ribbon("Create Sketch")


def esc_cancels():
    h.press(QtCore.Qt.Key_Escape)


def esc_cancelled():
    h.check("Esc: no sketch made", len(sketches()) == s["sketches"], len(sketches()))
    h.check("Esc: panel closed", not Gui.Control.activeDialog())
    h.fit()


def sketch_on_face():
    h.ribbon("Create Sketch")


def click_face():
    h.click(V(30, 22, s["top"]))


def circle_key():
    s["sk"] = h.in_sketch()
    h.check("sketch on the face", s["sk"] is not None)
    h.press("c")


def circle_c():
    si.click(V(20, 15, s["top"]))


def circle_r():
    si.click(V(25, 15, s["top"]))


def dim_key():
    h.press(QtCore.Qt.Key_Escape)
    h.press("d")


def dim_pick():
    import math

    a = math.radians(60)
    si.click(V(20 + 5 * math.cos(a), 15 + 5 * math.sin(a), s["top"]), V(0.5, 0.3, 0))


def dim_place():
    si.click(V(30, 26, s["top"]))


def dim_value():
    si.type_text("10")


def dim_done():
    h.press(QtCore.Qt.Key_Escape)
    sk = s["sk"]
    c = si.circles(sk, construction=False)
    h.check("circle diameter 10", c and si.near(c[0][1].Radius, 5.0, 1e-6), c)


def _session():
    from sciforge import sketch_mode

    return sketch_mode.current()


def _enable_flags(name_filter):
    from sciforge import sketch_mode

    node, _ = sketch_mode.find_node(h.view().getSceneGraph(), "ConstraintGroup")
    field = node.getField("enable")
    text = field.get()
    text = text.getString() if hasattr(text, "getString") else str(text)
    flags = sketch_mode._bools(text)
    return [f for f, c in zip(flags, s["sk"].Constraints) if name_filter(c)]


def _style(name):
    from pivy import coin
    from sciforge import sketch_mode

    node, _ = sketch_mode.find_node(h.view().getSceneGraph(), name)
    return None if node is None else node.style.getValue() == coin.SoDrawStyle.INVISIBLE


def grid_off():
    s["grid"] = s["sk"].ViewObject.ShowGrid
    h.check("grid shown (Fusion's default)", s["grid"])
    si.palette_click("SciForgePalette_grid")


def grid_check():
    h.check("Sketch Grid off hides the grid", not s["sk"].ViewObject.ShowGrid)
    si.palette_click("SciForgePalette_grid")


def grid_on():
    h.check("Sketch Grid on shows it again", s["sk"].ViewObject.ShowGrid)
    si.palette_click("SciForgePalette_slice")


def slice_check():
    h.check("Slice cuts the part at the sketch", s["sk"].ViewObject.SectionView)
    h.shot("1-slice")
    si.palette_click("SciForgePalette_slice")


def slice_off():
    h.check("Slice off", not s["sk"].ViewObject.SectionView)
    h.shot("2-slice-off")
    session = _session()
    h.check("profiles shaded", session.shading.attached and session.shading.count >= 1)
    si.palette_click("SciForgePalette_profile")


def profile_check():
    h.check("Show Profile off hides the shading", not _session().shading.attached)
    si.palette_click("SciForgePalette_profile")


def profile_on():
    h.check("Show Profile on shows it again", _session().shading.attached)
    si.palette_click("SciForgePalette_dimensions")


def dims_check():
    dims = _enable_flags(lambda c: c.Type in ("Diameter", "Radius", "Distance"))
    h.check("Show Dimensions off hides the dimension", dims and not any(dims), dims)
    others = _enable_flags(lambda c: c.Type not in ("Diameter", "Radius", "Distance"))
    h.check("...but not the other constraints", all(others), others)
    si.palette_click("SciForgePalette_dimensions")


def dims_on():
    dims = _enable_flags(lambda c: c.Type in ("Diameter", "Radius", "Distance"))
    h.check("Show Dimensions on shows it again", dims and all(dims), dims)
    si.palette_click("SciForgePalette_constraints")


def constraints_check():
    others = _enable_flags(lambda c: c.Type not in ("Diameter", "Radius", "Distance"))
    dims = _enable_flags(lambda c: c.Type in ("Diameter", "Radius", "Distance"))
    h.check("Show Constraints off hides the constraint symbols", not any(others), others)
    h.check("...but keeps the dimensions", dims and all(dims), dims)
    si.palette_click("SciForgePalette_constraints")


def constraints_on():
    others = _enable_flags(lambda c: c.Type not in ("Diameter", "Radius", "Distance"))
    h.check("Show Constraints on shows them again", all(others), others)
    si.palette_click("SciForgePalette_points")


def points_check():
    h.check("Show Points off hides the points", _style("PointsDrawStyle0") is True)
    si.palette_click("SciForgePalette_points")


def points_on():
    h.check("Show Points on shows them again", _style("PointsDrawStyle0") is False)
    s["ext"] = len(s["sk"].ExternalGeo)
    si.menu_item("CREATE", "Include 3D Geometry")


def include_edge():
    h.fit()
    si.click(V(40, 0, s["top"] / 2.0), V(0.0, -1.0, 0))  # a vertical edge of the block


def included():
    h.press(QtCore.Qt.Key_Escape)
    sk = s["sk"]
    added = len(sk.ExternalGeo) - s["ext"]
    h.check("Include 3D Geometry added the edge", added >= 1, added)
    if added >= 1:
        import Sketcher

        facade = Sketcher.ExternalGeometryFacade(sk.ExternalGeo[-1])
        h.check("included geometry is a reference (no profile)", not facade.testFlag("Defining"))
    si.palette_click("SciForgePalette_projected")


def projected_check():
    h.check("Show Projected Geometries off hides them", _style("CurvesExternalDrawStyle") is True)
    si.palette_click("SciForgePalette_projected")


def projected_on():
    h.check("Show Projected Geometries on shows them", _style("CurvesExternalDrawStyle") is False)
    direction = h.view().getViewDirection()
    h.check("the view was turned (precondition)", not si.vnear(direction, V(0, 0, -1), 1e-3))
    si.palette_click("SciForgePaletteLookAt")


def looked_at():
    direction = h.view().getViewDirection()
    h.check("Look At turns the camera to the sketch", si.vnear(direction, V(0, 0, -1), 1e-6))


def select_circle():
    si.click(V(25, 15, s["top"]), V(0.4, 0.2, 0))


def linetype():
    h.check("circle selected", bool(Gui.Selection.getSelectionEx()))
    si.palette_click("SciForgePaletteConstruction")


def linetype_check():
    sk = s["sk"]
    c = si.circles(sk)
    h.check("Linetype made the circle construction", c and sk.getConstruction(c[0][0]), c)


def finish():
    h.press(QtCore.Qt.Key_Escape)
    h.ribbon("Finish Sketch")


def finished():
    h.check("left the sketch", h.in_sketch() is None)
    from sciforge import sketch_mode

    defaults = {k: sketch_mode.option(k) for k in sketch_mode.PALETTE_DEFAULTS}
    h.check("palette options back to their defaults", defaults == sketch_mode.PALETTE_DEFAULTS)


h.run(
    "sketch_options",
    si.watched(
        [
            new_design,
            create_sketch,
            pick_xy_plane,
            rect_key,
            rect_a,
            rect_b,
            finish_1,
            extrude,
            extrude_ok,
            block,
            create_then_cancel,
            cancel,
            cancelled,
            create_then_esc,
            esc_cancels,
            esc_cancelled,
            sketch_on_face,
            click_face,
            circle_key,
            circle_c,
            circle_r,
            dim_key,
            dim_pick,
            dim_place,
            dim_value,
            dim_done,
            grid_off,
            grid_check,
            grid_on,
            slice_check,
            slice_off,
            profile_check,
            profile_on,
            dims_check,
            dims_on,
            constraints_check,
            constraints_on,
            points_check,
            points_on,
            include_edge,
            included,
            projected_check,
            projected_on,
            looked_at,
            select_circle,
            linetype,
            linetype_check,
            finish,
            finished,
        ]
    ),
)
