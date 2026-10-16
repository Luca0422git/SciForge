# SPDX-License-Identifier: LGPL-2.1-or-later
"""SKETCH PALETTE checks of "Sketch, part 2": Slice cuts away what is in front of the
sketch; 3D Sketch inside a component; the sketch-2 commands with no sketch open. Real
clicks on the palette and in the view.

  A  an empty design: Fillet, Chamfer and the 3D Spline say they work inside a sketch
  B  a 40 x 40 x 10 block and a sketch on an Offset Plane 5 up inside it, seen from the
     top: Slice on: the part in front of the sketch (the top half) is cut away (the clip
     plane keeps only what lies behind the sketch; a pick in the middle reaches the
     sketch plane, no longer the top face); Slice off: the top face again
  C  seen from below (the other side): Slice keeps the top half instead
  D  a component (with a body) active: a sketch in it, 3D Sketch, a 3D line: its 3D Curves
     go into the component and lie where the line was drawn
"""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtWidgets

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import sketch_tools_steps as st

V = App.Vector
s = {}


def told():
    from sciforge import commands

    return commands._TOLD["msg"] or ""


def doc():
    return App.ActiveDocument


def clip_planes():
    """[(normal, distance)] of the clip planes switched on in the view."""
    from pivy import coin

    sa = coin.SoSearchAction()
    sa.setType(coin.SoClipPlane.getClassTypeId())
    sa.setInterest(coin.SoSearchAction.ALL)
    sa.setSearchingAll(True)
    sa.apply(h.view().getSceneGraph())
    out = []
    paths = sa.getPaths()
    for i in range(paths.getLength()):
        node = paths[i].getTail()
        if node.on.getValue():
            out.append(node.plane.getValue())
    return out


def keeps(plane, z):
    from pivy import coin

    return bool(plane.isInHalfSpace(coin.SbVec3f(5, 5, z)))


def pick_z():
    """The height of what the view shows in the middle of the block (from where it is
    looked at)."""
    c = h.screen_point(V(5, 5, 5))
    info = h.view().getObjectInfo((c.x(), h.gl_widget().height() - c.y()))
    return (info or {}).get("z"), (info or {}).get("Object")


# -- A ----------------------------------------------------------------------------------------
def a_empty():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("Sketch2Palette")
    h.fit()
    for command, title in (
        ("SciForge_SketchFillet", "Fillet"),
        ("SciForge_SketchChamfer", "Chamfer"),
        ("SciForge_SketchFitSpline", None),
    ):
        Gui.runCommand(command)
        QtWidgets.QApplication.processEvents()
        if title is not None:
            h.check("A %s without a sketch says why" % title, "inside a sketch" in told(), told())
    h.check(
        "A nothing was made",
        not doc().Objects or all(o.TypeId != "Sketcher::SketchObject" for o in doc().Objects),
    )


# -- B ----------------------------------------------------------------------------------------
def b_setup():
    from sciforge import commands, construct, extrude, sketch_ui

    App.closeDocument(doc().Name)
    App.newDocument("Sketch2Slice")
    body = commands.ensure_body()
    xy = (sketch_ui.origin_planes(body)["XY_Plane"], "")
    base = sketch_ui.create_sketch(body, xy)
    h.draw_rectangle(base, -20, -20, 20, 20)
    extrude.make(body, base, {"distance": 10.0})
    plane = construct.make(body, "OffsetPlane", [(xy[0], "")], {"distance": 5.0})
    doc().recompute()
    sk = sketch_ui.create_sketch(body, (plane, ""))
    doc().recompute()
    s["sk"] = sk
    h.view().viewTop()
    h.fit(iso=False)
    sketch_ui.edit_sketch(sk)


b_setup.wait_ms = 2000


def b_before():
    h.view().viewTop()
    h.fit(iso=False)
    z, obj = pick_z()
    h.check(
        "B before Slice the top face is in front", z is not None and abs(z - 10) < 1e-3, (z, obj)
    )
    si.palette_click("SciForgePalette_slice")


def b_slice():
    h.check("B Slice on", s["sk"].ViewObject.SectionView)
    planes = clip_planes()
    h.check("B one clip plane", len(planes) == 1, len(planes))
    if planes:
        h.check(
            "B it cuts away what is in front of the sketch (above it, towards the eye)",
            not keeps(planes[0], 8.0) and keeps(planes[0], 2.0),
        )
    z, obj = pick_z()
    h.check(
        "B the middle now shows the sketch's plane (no top face)",
        z is not None and z < 5.0 + 1e-3,
        (z, obj),
    )
    h.shot("B-slice")
    si.palette_click("SciForgePalette_slice")


def b_off():
    h.check("B Slice off", not s["sk"].ViewObject.SectionView)
    h.check("B no clip plane left", not clip_planes(), len(clip_planes()))
    z, obj = pick_z()
    h.check("B the top face is back", z is not None and abs(z - 10) < 1e-3, (z, obj))


# -- C ----------------------------------------------------------------------------------------
def c_below():
    h.view().viewBottom()
    h.fit(iso=False)
    si.palette_click("SciForgePalette_slice")


def c_check():
    planes = clip_planes()
    h.check(
        "C seen from below: Slice keeps the top half",
        len(planes) == 1 and keeps(planes[0], 8.0) and not keeps(planes[0], 2.0),
        len(planes),
    )
    si.palette_click("SciForgePalette_slice")


def c_finish():
    h.check("C Slice off again", not s["sk"].ViewObject.SectionView)
    h.ribbon("Finish Sketch")


# -- D ----------------------------------------------------------------------------------------
def d_component():
    from sciforge import components

    h.check("D left the sketch", h.in_sketch() is None)
    doc().openTransaction("component")
    part = components.new_component(doc())
    part.Placement = App.Placement(V(100, 0, 0), App.Rotation())
    body = components.new_body_in(doc(), part)
    doc().commitTransaction()
    components.set_active(part)
    components.activate_body(body)
    doc().recompute()
    s["part"] = part
    h.view().viewIsometric()
    h.fit()
    h.ribbon("Create Sketch")


def d_plane():
    # the component's XY plane, 100 to the right (its own origin)
    h.click(V(112, -8, 0))


def d_3d():
    sk = h.in_sketch()
    s["sk"] = sk
    st.s["sk"] = sk
    from sciforge import components

    h.check(
        "D the sketch is in the component",
        sk is not None and components.is_inside(sk, s["part"]),
        sk and sk.Label,
    )
    h.check(
        "D ...at the component's place",
        sk is not None and abs(sk.getGlobalPlacement().Base.x - 100) < 1e-6,
        sk and sk.getGlobalPlacement(),
    )
    si.palette_click("SciForgePalette_sketch3d")


def d_line():
    h.press("l")


def d_a():
    st.click(V(0, 0, 0))


def d_b():
    st.click(V(10, 0, 0))


d_b.wait_ms = 900


def d_check():
    from sciforge import components, sketch3d

    st.esc()
    obj = sketch3d.curves_of(s["sk"])
    h.check("D 3D Curves made", obj is not None)
    if obj is None:
        return
    h.check(
        "D ...in the component",
        components.container_of(obj) is s["part"],
        components.container_of(obj),
    )
    pts = sketch3d.global_points(obj)
    h.check(
        "D ...where the line was drawn (100 to the right)",
        len(pts) == 2 and abs(pts[0].x - 100) < 1e-6 and abs(pts[1].x - 110) < 1e-6,
        pts,
    )
    shape = obj.Shape.copy()
    shape.Placement = s["part"].getGlobalPlacement().multiply(shape.Placement)
    h.check(
        "D the line shows there",
        abs(shape.BoundBox.XMin - 100) < 1e-6 and abs(shape.BoundBox.XMax - 110) < 1e-6,
        shape.BoundBox,
    )
    h.ribbon("Finish Sketch")


h.run(
    "sketch2_palette",
    si.watched(
        [
            a_empty,
            b_setup,
            b_before,
            b_slice,
            b_off,
            c_below,
            c_check,
            c_finish,
            d_component,
            d_plane,
            d_3d,
            d_line,
            d_a,
            d_b,
            d_check,
        ]
    ),
)
