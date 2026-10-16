# SPDX-License-Identifier: LGPL-2.1-or-later
"""Project / Include and Project to Surface (parity/sketch.md "Sketch, part 2"), real
clicks for the projections.

A block 40 x 30 x 10 (x 0..40, y 10..40; its width a dimension of its sketch) and a
cylinder of radius 10 round (70, 25), 30 high (its radius a dimension).

  A  a sketch on XY, P, a click on the block's top front edge: a projected (purple) line
     in the sketch at y = 10 from x 0 to 40; Finish Sketch
  B  the block made 50 wide: the projected line follows (x 0 to 50)
  C  a sketch on XZ holding a line in front of the cylinder; Project to Surface: the
     cylinder's face, Next, the line, Along Vector, OK: the curve lies on the cylinder,
     on its front
  D  Finish Sketch: the browser lists "Projected Curves" under that sketch; no timeline
     step of their own; the sketch's eye hides and shows them
  E  the cylinder made radius 12: the curve follows onto the new face
  F  the sketch deleted (browser): its Projected Curves go too; Ctrl+Z brings both back
  G  save, close, reopen: they still belong to the sketch and lie on the cylinder
"""

import math
import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import sketch_tools_steps as st

V = App.Vector
s = {}


def doc():
    return App.ActiveDocument


def projected():
    from sciforge import sketch_companions

    sk = s.get("sk2")
    return sketch_companions.companions(sk, "ProjectedCurves") if sk is not None else []


def on_cylinder(obj, radius, centre=(70.0, 25.0)):
    """Every sample of the curves is `radius` from the cylinder's axis, on its front."""
    pts = []
    for e in obj.Shape.Edges:
        span = e.LastParameter - e.FirstParameter
        pts += [e.valueAt(e.FirstParameter + span * i / 12.0) for i in range(13)]
    dists = [math.hypot(p.x - centre[0], p.y - centre[1]) for p in pts]
    front = all(p.y < centre[1] for p in pts)
    return bool(pts) and all(abs(d - radius) < 1e-3 for d in dists) and front, dists


# -- setup ------------------------------------------------------------------------------------
def setup():
    import Part
    import Sketcher

    from sciforge import commands, extrude, sketch_ui

    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("Sketch2Project")
    body = commands.ensure_body()
    xy = (sketch_ui.origin_planes(body)["XY_Plane"], "")
    base = sketch_ui.create_sketch(body, xy)
    h.draw_rectangle(base, 0, 10, 40, 40)
    s["width"] = base.addConstraint(Sketcher.Constraint("DistanceX", 0, 1, 0, 2, 40.0))
    base.addConstraint(Sketcher.Constraint("DistanceX", -1, 1, 0, 1, 0.0))
    base.addConstraint(Sketcher.Constraint("DistanceY", -1, 1, 0, 1, 10.0))
    base.addConstraint(Sketcher.Constraint("DistanceY", 1, 1, 1, 2, 30.0))
    extrude.make(body, base, {"distance": 10.0})
    s["base"] = base
    # the cylinder, a body of its own
    body2 = doc().addObject("PartDesign::Body", "Body001")
    xy2 = (sketch_ui.origin_planes(body2)["XY_Plane"], "")
    circ = sketch_ui.create_sketch(body2, xy2)
    c = circ.addGeometry(Part.Circle(V(70, 25, 0), V(0, 0, 1), 10))
    s["radius"] = circ.addConstraint(Sketcher.Constraint("Radius", c, 10.0))
    circ.addConstraint(Sketcher.Constraint("DistanceX", -1, 1, c, 3, 70.0))
    circ.addConstraint(Sketcher.Constraint("DistanceY", -1, 1, c, 3, 25.0))
    doc().recompute()
    extrude.make(body2, circ, {"distance": 30.0})
    s["circle"] = circ
    from sciforge import components

    components.activate_body(body)  # the block's body: Create Sketch goes there
    doc().recompute()
    h.fit()


# -- A ----------------------------------------------------------------------------------------
def a_create():
    h.ribbon("Create Sketch")


def a_plane():
    h.click(V(12, -8, 0))


def a_project():
    sk = h.in_sketch()
    h.check(
        "A a sketch on XY",
        sk is not None and abs(sk.getGlobalPlacement().Rotation.multVec(V(0, 0, 1)).z) > 0.999,
    )
    s["sk1"] = sk
    s["ext"] = len(sk.ExternalGeo)
    h.press("p")


def a_edge():
    h.check("A clicked the block's top front edge", h.click_edge(V(20, 10, 10)))


def a_check():
    h.press(QtCore.Qt.Key_Escape)
    sk = s["sk1"]
    added = len(sk.ExternalGeo) - s["ext"]
    h.check("A the edge is projected into the sketch", added == 1, added)
    if added:
        g = sk.ExternalGeo[-1]
        ends = sorted(
            [
                (round(g.StartPoint.x, 6), round(g.StartPoint.y, 6)),
                (round(g.EndPoint.x, 6), round(g.EndPoint.y, 6)),
            ]
        )
        h.check("A the projected line: y 10, x 0 to 40", ends == [(0.0, 10.0), (40.0, 10.0)], ends)
    h.shot("A-projected")
    h.ribbon("Finish Sketch")


# -- B ----------------------------------------------------------------------------------------
def b_wider():
    h.check("A left the sketch", h.in_sketch() is None)
    doc().openTransaction("wider")
    s["base"].setDatum(s["width"], App.Units.Quantity("50 mm"))
    doc().commitTransaction()
    doc().recompute()


def b_check():
    sk = s["sk1"]
    g = sk.ExternalGeo[-1]
    xs = sorted([round(g.StartPoint.x, 6), round(g.EndPoint.x, 6)])
    h.check("B the projected line follows the block: x 0 to 50", xs == [0.0, 50.0], xs)
    h.check("B the sketch is fine", "Invalid" not in sk.State and "Error" not in sk.State, sk.State)


# -- C ----------------------------------------------------------------------------------------
def c_create():
    h.fit()
    h.ribbon("Create Sketch")


def c_plane():
    h.click(V(12, 0, 8))


def c_line():
    import Part

    sk = h.in_sketch()
    h.check(
        "C a sketch on XZ",
        sk is not None and abs(sk.getGlobalPlacement().Rotation.multVec(V(0, 0, 1)).y) > 0.999,
    )
    s["sk2"] = sk
    st.s["sk"] = sk
    inv = sk.getGlobalPlacement().inverse()
    a, b = inv.multVec(V(64, 0, 15)), inv.multVec(V(76, 0, 15))
    doc().openTransaction("line")
    s["line"] = sk.addGeometry(Part.LineSegment(V(a.x, a.y, 0), V(b.x, b.y, 0)))
    doc().commitTransaction()
    sk.solve()
    doc().recompute()
    si.menu_item("CREATE", "Project to Surface")


def c_face():
    h.check("C Project to Surface runs", st.tool_title() == "Project to Surface", st.tool_title())
    s["count"] = len(projected())
    si.click(V(70, 15, 22), V(0.0, -1.0, 0))  # the cylinder's front, above the line


def c_next():
    t = st.tool()
    h.check("C the cylinder's face is picked", t is not None and len(t.faces) == 1, t and t.faces)
    st.enter()


def c_curve():
    st.click(_sketch_xy(V(68, 0, 15)))


def _sketch_xy(point):
    local = s["sk2"].getGlobalPlacement().inverse().multVec(point)
    return V(local.x, local.y, 0)


def c_type():
    from PySide import QtWidgets

    from sciforge import sketch_project_tool

    t = st.tool()
    h.check("C the line is picked", t is not None and len(t.curves) == 1, t and t.curves)
    box = None
    for w in Gui.getMainWindow().findChildren(QtWidgets.QComboBox, "SciForgeProjectType"):
        if w.isVisible():
            box = w
    h.check("C the Projection Type box", box is not None)
    if box is not None:
        from SciForgeTests.gui import dialog_input as ui

        h.check("C Along Vector", ui.choose(box, sketch_project_tool.sketch_project.TYPES[1]))
    h.gl_widget().setFocus()


def c_ok():
    st.enter()


c_ok.wait_ms = 900


def c_check():
    found = projected()
    h.check("C Projected Curves made, the sketch's own", len(found) == s["count"] + 1, found)
    if found:
        ok, dists = on_cylinder(found[-1], 10.0)
        h.check("C the curve lies on the cylinder's front (radius 10)", ok, dists)
        s["projected"] = found[-1].Name
    h.shot("C-project-to-surface")


# -- D ----------------------------------------------------------------------------------------
def d_finish():
    h.ribbon("Finish Sketch")


def d_browser():
    from sciforge import browser_ui, timeline_ops

    obj = doc().getObject(s["projected"])
    tree = browser_ui.widget()
    tree.refresh(force=True)
    item = tree.row(obj.Label)
    parent = item.parent() if item is not None else None
    node = parent.data(1, browser_ui.ROLE_NODE) if parent is not None else {}
    h.check(
        "D the browser lists the Projected Curves under their sketch",
        node.get("object") == s["sk2"].Name,
        (tree.labels(), node.get("object")),
    )
    names = timeline_ops.timeline(doc()).names()
    h.check("D no timeline step of their own", obj.Name not in names, names)
    s["sk2"].ViewObject.Visibility = False


def d_hidden():
    obj = doc().getObject(s["projected"])
    h.check("D the sketch hidden: its projected curves too", not obj.ViewObject.Visibility)
    s["sk2"].ViewObject.Visibility = True


def d_shown():
    obj = doc().getObject(s["projected"])
    h.check("D shown with it again", obj.ViewObject.Visibility)


# -- E ----------------------------------------------------------------------------------------
def e_radius():
    doc().openTransaction("radius")
    s["circle"].setDatum(s["radius"], App.Units.Quantity("12 mm"))
    doc().commitTransaction()
    doc().recompute()


def e_check():
    obj = doc().getObject(s["projected"])
    ok, dists = on_cylinder(obj, 12.0)
    h.check("E the curve follows the cylinder (radius 12)", ok, dists)


# -- F ----------------------------------------------------------------------------------------
def f_delete():
    from sciforge import browser_ui

    tree = browser_ui.widget()
    tree.refresh(force=True)
    item = tree.row(s["sk2"].Label)
    h.check("F the sketch's row", item is not None)
    s["sk2_name"] = s["sk2"].Name
    if item is not None:
        tree.delete([item.data(1, browser_ui.ROLE_NODE)])


f_delete.wait_ms = 900


def f_check():
    h.check("F the sketch is gone", doc().getObject(s["sk2_name"]) is None)
    h.check("F ...its Projected Curves too", doc().getObject(s["projected"]) is None)
    st.undo()


f_check.wait_ms = 900


def f_undone():
    h.check("F Ctrl+Z: the sketch is back", doc().getObject(s["sk2_name"]) is not None)
    h.check("F ...with its Projected Curves", doc().getObject(s["projected"]) is not None)
    s["sk2"] = doc().getObject(s["sk2_name"])


# -- G ----------------------------------------------------------------------------------------
def g_save():
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-sketch2-project-"), "project.FCStd")
    s["path"] = path
    doc().saveAs(path)
    App.closeDocument(doc().Name)


def g_reopen():
    App.openDocument(s["path"])
    h.fit()


def g_check():
    from sciforge import sketch_companions

    obj = doc().getObject(s["projected"])
    sk = doc().getObject(s["sk2_name"])
    h.check(
        "G reopened: the Projected Curves belong to their sketch",
        obj is not None and sketch_companions.owner(obj) is sk,
    )
    if obj is not None:
        doc().recompute()
        ok, dists = on_cylinder(obj, 12.0)
        h.check("G reopened: on the cylinder", ok, dists)


h.run(
    "sketch2_project",
    si.watched(
        [
            setup,
            a_create,
            a_plane,
            a_project,
            a_edge,
            a_check,
            b_wider,
            b_check,
            c_create,
            c_plane,
            c_line,
            c_face,
            c_next,
            c_curve,
            c_type,
            c_ok,
            c_check,
            d_finish,
            d_browser,
            d_hidden,
            d_shown,
            e_radius,
            e_check,
            f_delete,
            f_check,
            f_undone,
            g_save,
            g_reopen,
            g_check,
        ]
    ),
)
