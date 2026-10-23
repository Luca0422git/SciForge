# SPDX-License-Identifier: LGPL-2.1-or-later
"""SURFACE > Sweep Path + Guide Surface, Path + Guide Rail's Extent and Guide Rail Distance,
and SURFACE > Extrude of a flat face with the Chain Faces / Extend Faces choice (surface part
3), only real input in the dialogs.

The design (built for the scenario): a block 40 x 40 x 5 under the XY plane (top face at z 0,
x -20 .. 20, y 0 .. 40); on XY a path (0, 0) - (0, 40); on XY moved up 5 a rail (15, 0) -
(15, 30); on XZ a profile (-5, 5) - (15, 5).
Path G1 (Path + Guide Surface): SURFACE > Sweep, Type Path + Guide Surface: the Guide Surface
        box shows (Orientation, Taper and Twist go); click the profile, the path, then the
        block's top face: the profile keeps its angle to the face, a flat band 20 x 40 (800).
        OK: "Sweep 1".
Path G2 (edit): double-click Sweep 1: the type and the face read back; Cancel.
Path R1 (Path + Guide Rail extents): SURFACE > Sweep, Path + Guide Rail; click the profile,
        the path, the rail (10 shorter than the path): Extent reads Perpendicular to Path:
        the sweep stops square to the path where the rail ends (20 x 30 = 600); Full
        Extents: both run to their ends (the whole path, the profile turning to keep
        touching the rail spread over it); Perpendicular again and Guide Rail Distance
        0.5: half the rail, 300. Esc: nothing made.
Path E1 (a flat face as the profile): SURFACE > Extrude, click the block's front face: the
        curves round it are the profile; type 10: four walls round the 40 x 5 face (900);
        Extent To Object: the Faces row offers Chain Faces / Extend Faces; Distance again;
        OK: "Extrude 1".
"""

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import surface_steps as st

V = App.Vector
s = {}


def doc():
    return App.ActiveDocument


def new_design():
    from sciforge import commands, extrude, sketch_ui

    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("Surface3SweepExtrude")
    body = commands.ensure_body()
    planes = sketch_ui.origin_planes(body)
    base = sketch_ui.create_sketch(body, (planes["XY_Plane"], ""))
    base.AttachmentOffset = App.Placement(V(0, 0, -5), App.Rotation())
    h.draw_rectangle(base, -20, 0, 20, 40)
    extrude.make(body, base, {"distance": 5.0})
    commands.leave_edit()
    s["block"] = body
    path = sketch_ui.create_sketch(body, (planes["XY_Plane"], ""))
    st.add_lines(path, [(0, 0), (0, 40)])
    commands.leave_edit()
    s["path"] = path
    rail = sketch_ui.create_sketch(body, (planes["XY_Plane"], ""))
    rail.AttachmentOffset = App.Placement(V(0, 0, 5), App.Rotation())
    st.add_lines(rail, [(15, 0), (15, 30)])
    commands.leave_edit()
    s["rail"] = rail
    prof = sketch_ui.create_sketch(body, (planes["XZ_Plane"], ""))
    st.add_lines(prof, [(-5, 5), (15, 5)])
    commands.leave_edit()
    s["profile"] = prof
    doc().recompute()
    h.fit()


def sweep_menu():
    from sciforge import bodies

    for sk in (s["path"], s["profile"], s["rail"]):
        bodies.set_shown(sk, True)
    b = s["block"].Shape.BoundBox
    h.check("the block's top at z 0", st.near(b.ZMax, 0.0) and st.near(b.ZMin, -5.0), b)
    h.click_empty()
    st.tab("SURFACE")
    st.menu("CREATE", "Sweep")


def g1_type():
    p = st.panel()
    h.check("Sweep dialog open", p is not None and p.kind == "sweep")
    if p is None:
        return
    box = p.rows["type"][0]
    items = [box.itemText(i) for i in range(box.count())]
    h.check(
        "Type: Single Path, Path + Guide Rail, Path + Guide Surface",
        items == ["Single Path", "Path + Guide Rail", "Path + Guide Surface"],
        items,
    )
    st.choose("type", "Path + Guide Surface")


def g1_rows():
    st.settle()
    p = st.panel()
    if p is None:
        return
    h.check("the Guide Surface box is shown", p.is_shown("guide"))
    h.check("no Guide Rail box", not p.is_shown("rail"))
    h.check("no Orientation", not p.rows["orientation"][0].isVisible())
    h.check("no Taper Angle", not p.rows["taper"][0].isVisible())
    h.check("clicked the profile", h.click_edge(V(-3, 0, 5)))


def g1_path():
    st.settle()
    p = st.panel()
    h.check("the profile is taken", p is not None and len(p.picks["profile"]) == 1, p and p.picks)
    h.check("clicked the path", h.click_edge(V(0, 36, 0)))


def g1_guide():
    st.settle()
    p = st.panel()
    h.check("the path is taken", p is not None and len(p.picks["path"]) >= 1, p and p.picks)
    h.check("the Guide Surface box takes the clicks", p is not None and p.active == "guide")
    h.click(V(-12, 30, 0))


def g1_band():
    st.settle()
    p = st.panel()
    h.check("a face of the block", p is not None and len(p.picks["guide"]) == 1, p and p.picks)
    body = st.step_body()
    s["sweep"] = body
    h.check("a flat band 20 x 40 (800)", st.near(st.area(body), 800.0, 1e-6), st.area(body))
    if body is not None:
        b = body.Shape.BoundBox
        h.check("at the profile's height, z 5", st.near(b.ZMin, 5.0) and st.near(b.ZMax, 5.0), b)
    h.shot("1-sweep-guide-surface")
    st.ok()


def g1_done():
    h.check("dialog closed", st.panel() is None)
    titles = st.timeline_titles()
    h.check("Sweep 1 in the timeline", "Sweep 1" in titles, titles)
    h.check("edited from the timeline", st.double_click_timeline("Sweep 1"))


def g2_reads_back():
    st.settle()
    p = st.panel()
    h.check("Sweep dialog for editing", p is not None and p.kind == "sweep" and p.editing)
    if p is None:
        return
    h.check("Path + Guide Surface read back", p.options["type"] == "surface", p.options)
    h.check("the guide face read back", len(p.picks["guide"]) == 1, p.picks)
    h.check("no rail", not p.picks["rail"], p.picks)
    st.cancel()


def g2_cancelled():
    h.check("dialog closed", st.panel() is None)
    h.check("unchanged (800)", st.near(st.area(s["sweep"]), 800.0, 1e-6))


# -- Path + Guide Rail extents -------------------------------------------------------------------
def r1_menu():
    from sciforge import bodies

    bodies.set_shown(s["sweep"], False)  # out of the way of the curves
    for sk in (s["path"], s["profile"], s["rail"]):
        bodies.set_shown(sk, True)
    h.fit()
    h.click_empty()
    st.menu("CREATE", "Sweep")


def r1_type():
    h.check("Sweep dialog open", st.panel() is not None)
    st.choose("type", "Path + Guide Rail")


def r1_rows():
    st.settle()
    p = st.panel()
    if p is None:
        return
    h.check("Extent shown", p.rows["rail_extent"][0].isVisible())
    h.check(
        "Extent reads Perpendicular to Path",
        p.rows["rail_extent"][0].currentText() == "Perpendicular to Path",
        p.rows["rail_extent"][0].currentText(),
    )
    h.check("Guide Rail Distance shown", p.rows["rail_distance"][0].isVisible())
    h.check("clicked the profile", h.click_edge(V(-3, 0, 5)))


def r1_path():
    st.settle()
    h.check("clicked the path", h.click_edge(V(0, 36, 0)))


def r1_rail():
    st.settle()
    p = st.panel()
    h.check("the Guide Rail box takes the clicks", p is not None and p.active == "rail")
    h.check("clicked the rail", h.click_edge(V(15, 15, 5)))


def r1_perpendicular():
    st.settle()
    body = st.step_body()
    area = st.area(body)
    h.check(
        "Perpendicular to Path: stops where the rail ends (600)", st.near(area, 600.0, 1e-6), area
    )
    st.choose("rail_extent", "Full Extents")


def r1_full():
    st.settle()
    area = st.area(st.step_body())
    body = st.step_body()
    box = body.Shape.BoundBox if body is not None else None
    # the rail (30) is spread over the whole path (40): the profile turns to keep touching it
    h.check(
        "Full Extents: the whole path (to y 40 and on)",
        box is not None and box.YMax > 39.9,
        box,
    )
    h.check("and more than Perpendicular's 600", area > 600.0 + 1.0, area)
    st.choose("rail_extent", "Perpendicular to Path")


def r1_rail_distance():
    st.settle()
    st.type_field("rail_distance", "0.5")


def r1_half():
    st.settle()
    area = st.area(st.step_body())
    h.check("Guide Rail Distance 0.5: half the rail (300)", st.near(area, 300.0, 1e-6), area)
    s["count"] = len(st.bodies())
    st.esc()


def r1_escaped():
    h.check("Esc closed it", st.panel() is None)
    titles = st.timeline_titles()
    h.check("no Sweep 2", "Sweep 2" not in titles, titles)


# -- Extrude a flat face ---------------------------------------------------------------------------
def e1_menu():
    from sciforge import bodies

    for sk in (s["path"], s["profile"], s["rail"]):
        bodies.set_shown(sk, False)
    h.fit()
    h.click_empty()
    st.menu("CREATE", "Extrude")


def e1_face():
    p = st.panel()
    h.check("Extrude dialog open", p is not None and p.kind == "extrude")
    h.click(V(-12, 0, -2.5))


def e1_profile():
    st.settle()
    p = st.panel()
    picks = p.picks["profile"] if p is not None else []
    h.check(
        "the front face is the profile", len(picks) == 1 and picks[0][1].startswith("Face"), picks
    )
    st.type_field("distance", "10")


def e1_walls():
    st.settle()
    body = st.step_body()
    s["walls"] = body
    area = st.area(body)
    h.check("four walls round the 40 x 5 face (900)", st.near(area, 900.0, 1e-6), area)
    h.check("open walls: 4 faces, no solid", body is not None and len(body.Shape.Faces) == 4)
    st.choose("extent", "To Object")


def e1_faces_row():
    st.settle()
    p = st.panel()
    if p is None:
        return
    box = p.rows["chain_faces"][0]
    h.check("the Faces row is shown", box.isVisible())
    items = [box.itemText(i) for i in range(box.count())]
    h.check("Chain Faces / Extend Faces", items == ["Chain Faces", "Extend Faces"], items)
    st.choose("extent", "Distance")


def e1_ok():
    st.settle()
    area = st.area(st.step_body())
    h.check("back to the walls (900)", st.near(area, 900.0, 1e-6), area)
    h.shot("2-extrude-face")
    st.ok()


def e1_done():
    h.check("dialog closed", st.panel() is None)
    titles = st.timeline_titles()
    h.check("Extrude in the timeline", any(t.startswith("Extrude") for t in titles), titles)


h.run(
    "surface3_sweep_extrude",
    [
        new_design,
        sweep_menu,
        g1_type,
        g1_rows,
        g1_path,
        g1_guide,
        g1_band,
        g1_done,
        g2_reads_back,
        g2_cancelled,
        r1_menu,
        r1_type,
        r1_rows,
        r1_path,
        r1_rail,
        r1_perpendicular,
        r1_full,
        r1_rail_distance,
        r1_half,
        r1_escaped,
        e1_menu,
        e1_face,
        e1_profile,
        e1_walls,
        e1_faces_row,
        e1_ok,
        e1_done,
    ],
)
