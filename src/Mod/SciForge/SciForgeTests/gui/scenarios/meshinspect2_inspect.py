# SPDX-License-Identifier: LGPL-2.1-or-later
"""INSPECT, part 2: Interference's Create Bodies, Measure's Component filter, Minimum Radius'
Include Sharp Curves, Zebra on a mesh body; only real input.

Part (real input): Body an L: a box 40 x 30 x 10 from the origin and, joined to it, the
block x 0 .. 20 (all of y) 20 high: a sharp inner edge along y at x = 20, z = 10 (18000);
Body2 a box x 30 .. 70, y 0 .. 30, 10 high (New Body): they share x 30 .. 40, 10 x 30 x 10 =
3000; Body3 a box x 0 .. 20, y 50 .. 70, 10 high (New Body): 20 from Body.

A  INSPECT > Interference: Body and Body2 clicked, Compute: one overlap of 3000; Create Bodies
   From Interferences ticks its row; OK: a new body of exactly the shared 3000 mm3 (x 30 .. 40,
   y 0 .. 30, z 0 .. 10), one undo step with the analysis; Undo: neither; Redo: both.
B  INSPECT > Minimum Radius Analysis on Body, Include Sharp Curves: one sharp inner edge, drawn
   red along the L's corner; OK keeps it.
C  Body and Body3 made components (browser: Create Components from Bodies). Measure (I),
   Selection Filter Component: a click on Body picks its whole component (18000 mm3), one on
   Body3 its component: Distance 20. Body2 is no component's: the dialog says so.
D  A new design with a mesh sphere: INSPECT > Zebra Analysis takes the mesh body: stripes on
   its 2208 triangles; OK: Zebra1. Draft Analysis is refused for a mesh body (it says why).
   MESH > Smooth the sphere: the zebra follows the body's newest step.
"""

import FreeCAD as App
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import analysis_steps as a
from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import dialog_input as di
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import insert_steps as i
from SciForgeTests.gui import mesh_steps as m
from SciForgeTests.gui import meshinspect2_steps as e
from SciForgeTests.gui import timeline_input as t

V = App.Vector
state = {}


def near(x, y, tol=1e-3):
    return x is not None and abs(x - y) <= tol


def bodies():
    return sorted(App.ActiveDocument.findObjects("PartDesign::Body"), key=lambda o: o.ID)


def body(label):
    for obj in bodies():
        if obj.Label == label:
            return obj
    return None


def volume(obj):
    from sciforge import bodies as bt

    return bt.global_shape(obj).Volume if obj is not None else None


# -- the part ----------------------------------------------------------------------------------
def tall_steps():
    """The block x 0 .. 20, 20 high, joined to Body (Operation Join chosen in the dialog)."""

    def sketch():
        h.fit()
        h.ribbon("Create Sketch")

    def pick_xy():
        h.click(V(12, -8, 0))

    def draw():
        sk = h.in_sketch()
        h.check("sketch open on XY", sk is not None)
        if sk is not None:
            h.draw_rectangle(sk, 0, 0, 20, 30)

    def finish():
        h.ribbon("Finish Sketch")

    def extrude():
        h.fit()
        h.press("e")

    def distance():
        panel = b.active_panel()
        field = getattr(getattr(panel, "distance", None), "widget", None)
        if h.check("extrude dialog open", field is not None):
            b.type_into(field, "20")
            QtTest.QTest.keyClick(field, QtCore.Qt.Key_Tab)
            QtWidgets.QApplication.processEvents()

    def join():
        panel = b.active_panel()
        combo = getattr(panel, "operation", None)
        if h.check("extrude has an operation", combo is not None):
            b.choose(combo, "Join")

    def ok():
        h.task_button("OK")

    def made():
        h.check(
            "Body is an L of 18000", near(volume(body("Body")), 18000.0), volume(body("Body"))
        )
        h.fit()

    steps = [sketch, pick_xy, draw, finish, extrude, distance, join, ok, made]
    for step in steps:
        step.wait_ms = 1200
        step.__name__ = "tall_" + step.__name__
    return steps


# -- A ------------------------------------------------------------------------------------------
def a_start():
    state["bodies"] = len(bodies())
    h.click_empty()
    s.menu("INSPECT", "Interference")


a_start.wait_ms = 1200


def a_first():
    from sciforge import interference_ui

    p = b.active_panel()
    h.check("Interference open", isinstance(p, interference_ui.InterferencePanel), p)
    h.click(V(25, 15, 10))


def a_second():
    h.click(V(60, 15, 10))


def a_compute():
    p = b.active_panel()
    h.check("two bodies picked", len(p.picked) == 2, [o.Label for o in p.picked])
    di.click(p.compute)


a_compute.wait_ms = 1500


def a_result():
    p = b.active_panel()
    rows = p.rows()
    h.check("one overlap of 3000", len(rows) == 1 and rows[0][3] == "3000.000 mm^3", rows)
    h.check("its row can make a body", len(p._checkable()) == 1)
    h.check("not ticked yet", p.ticked() == [], p.ticked())
    a.tick(p.create_all, True)


a_result.wait_ms = 1000


def a_ticked():
    p = b.active_panel()
    h.check("Create Bodies From Interferences ticks the row", p.ticked() == [0], p.ticked())
    h.check("the dialog says what OK makes", "1 body" in p.message.text(), p.message.text())
    h.task_button("OK")


a_ticked.wait_ms = 2000


def a_made():
    found = bodies()
    h.check("a new body", len(found) == state["bodies"] + 1, [o.Label for o in found])
    new = found[-1]
    state["new"] = new.Label
    h.check("of the shared 3000 mm3", near(volume(new), 3000.0), volume(new))
    box = new.Shape.BoundBox
    h.check(
        "where the bodies overlap",
        near(box.XMin, 30) and near(box.XMax, 40) and near(box.YMax, 30) and near(box.ZMax, 10),
        box,
    )
    h.check("it is shown", s.shown(new))
    h.check("the timeline has its Base Feature", "Base Feature 1" in t.titles(), t.titles())
    from sciforge import analysis

    h.check(
        "Interference1 kept",
        [o.Label for o in analysis.of_kind(App.ActiveDocument, analysis.INTERFERENCE_KIND)]
        == ["Interference1"],
    )
    s.undo()


a_made.wait_ms = 2000


def a_undone():
    from sciforge import analysis

    h.check("Undo: no new body", len(bodies()) == state["bodies"], [o.Label for o in bodies()])
    h.check(
        "Undo: no Interference1",
        analysis.of_kind(App.ActiveDocument, analysis.INTERFERENCE_KIND) == [],
    )
    s.redo()


a_undone.wait_ms = 2000


def a_redone():
    new = body(state["new"])
    h.check("Redo: the body is back", new is not None and near(volume(new), 3000.0), new)
    h.click_empty()
    a.inspect("Minimum Radius Analysis")


a_redone.wait_ms = 1500


# -- B ------------------------------------------------------------------------------------------
def b_pick():
    p = a.panel()
    h.check("Minimum Radius dialog", p is not None and p.kind == "MinimumRadiusAnalysis", p)
    h.click(V(10, 15, 20))


b_pick.wait_ms = 1500


def b_sharp():
    p = a.panel()
    h.check("Body picked", [o.Label for o, _n in p.entries] == ["Body"], p.entries)
    a.tick(p.field("IncludeSharpCurves"), True)


b_sharp.wait_ms = 2500


def b_drawn():
    p = a.panel()
    text = p.message.text()
    h.check("one sharp inner edge", "1 sharp inner edge" in text, text)
    vp = p.analysis.ViewObject.Proxy if p.analysis is not None else None
    lines = getattr(vp, "sharp_edges", [])
    h.check("drawn: one red line", len(lines) == 1, lines)
    if lines:
        pts = lines[0]
        h.check(
            "along the L's corner (x 20, z 10)",
            all(near(q[0], 20.0) and near(q[2], 10.0) for q in pts),
            pts,
        )
    h.task_button("OK")


b_drawn.wait_ms = 1500


def b_kept():
    found = a.analyses("MinimumRadiusAnalysis")
    h.check("Minimum Radius1 kept", len(found) == 1, found)
    h.check("with Include Sharp Curves", bool(found and found[0].IncludeSharpCurves))
    h.click_empty()
    t.row_menu("Body", "Create Components from Bodies")


b_kept.wait_ms = 1500


# -- C ------------------------------------------------------------------------------------------
def c_second_component():
    t.row_menu("Body3", "Create Components from Bodies")


c_second_component.wait_ms = 1500


def c_measure():
    from sciforge import components

    parts = [components.container_of(body(x)) for x in ("Body", "Body3")]
    h.check("Body and Body3 in components", all(p is not None for p in parts), parts)
    h.check("Body2 at the top", components.container_of(body("Body2")) is None)
    h.click_empty()
    h.fit()
    h.press("i")


c_measure.wait_ms = 1500


def measure_panel():
    from sciforge import measure_ui, taskui

    p = taskui.current()
    return p if isinstance(p, measure_ui.MeasurePanel) else None


def c_filter():
    p = measure_panel()
    h.check("Measure open", p is not None)
    if p is None:
        return
    index = p.filter.findText("Component")
    item = p.filter.model().item(index)
    h.check("the Component filter can be chosen", item is not None and item.isEnabled())
    a.set_combo(p.filter, "Component")


c_filter.wait_ms = 800


def c_first():
    h.click(V(25, 15, 10))


c_first.wait_ms = 1200


def c_one():
    p = measure_panel()
    vals = p.values()
    one = vals.get("Selection 1", {})
    h.check("the whole component", one.get("Volume") == "18000.000 mm^3", vals)
    h.click(V(10, 60, 10))


c_one.wait_ms = 1200


def c_two():
    p = measure_panel()
    vals = p.values()
    h.check(
        "between the components: 20", vals.get("Results", {}).get("Distance") == "20.000 mm", vals
    )
    h.check("Delta Y 20", vals.get("Results", {}).get("Delta Y") == "20.000 mm", vals)
    di.click(p.restart)


c_two.wait_ms = 1000


def c_root_body():
    h.click(V(60, 15, 10))


c_root_body.wait_ms = 1200


def c_refused():
    p = measure_panel()
    text = p.message.text()
    h.check("a body in no component: it says so", "not in a component" in text, text)
    h.check("nothing measured", p.values() == {}, p.values())
    h.task_button("Close")


c_refused.wait_ms = 1200


# -- D ------------------------------------------------------------------------------------------
def d_closed():
    h.check("Measure closed", measure_panel() is None)


def sphere_file():
    return m.write_stl("zsphere.stl", m.sphere_triangles(10.0, 24))


def d_zebra():
    h.fit()
    a.inspect("Zebra Analysis")


d_zebra.wait_ms = 1500


def d_pick():
    p = a.panel()
    h.check("Zebra dialog", p is not None and p.kind == "ZebraAnalysis", p)
    h.click(e.on_sphere(0.1, 0.2))


d_pick.wait_ms = 2500


def d_striped():
    p = a.panel()
    sphere = m.body("zsphere")
    h.check("the mesh body taken", [o for o, _n in p.entries] == [sphere], p.entries)
    vp = p.analysis.ViewObject.Proxy if p.analysis is not None else None
    stripes = getattr(vp, "stripes", [])
    h.check("stripes drawn on it", len(stripes) == 1, stripes)
    if stripes:
        h.check(
            "on its 2208 triangles",
            stripes[0][0] == sphere.Name and len(stripes[0][1].triangles) == 2208,
            (stripes[0][0], len(stripes[0][1].triangles)),
        )
    h.task_button("OK")


d_striped.wait_ms = 1500


def d_kept():
    found = a.analyses("ZebraAnalysis")
    h.check("Zebra1 kept", [o.Label for o in found] == ["Zebra1"], [o.Label for o in found])
    import sciforge

    state["recent"] = len(sciforge.RECENT)
    a.inspect("Draft Analysis")


d_kept.wait_ms = 1500


def d_draft_refused():
    h.check(
        "no Draft dialog for a mesh body", a.panel() is None or a.panel().kind != "DraftAnalysis"
    )
    import sciforge

    said = " | ".join(sciforge.RECENT[-12:])
    h.check("it says why", "needs a solid or surface body" in said, said[-600:])
    m.mesh_tab()
    s.click_browser_row("zsphere")
    s.menu("MODIFY", "Smooth")


d_draft_refused.wait_ms = 1500


def d_smooth_ok():
    p = m.panel()
    h.check("Smooth dialog", p is not None and p.title == "Smooth", p)
    h.task_button("OK")


d_smooth_ok.wait_ms = 2500


def d_follows():
    smooth = m.steps("MeshSmooth")[-1]
    zebra = a.analyses("ZebraAnalysis")[0]
    vp = zebra.ViewObject.Proxy
    stripes = getattr(vp, "stripes", [])
    h.check(
        "the zebra follows the newest step",
        bool(stripes) and stripes[0][0] == smooth.Name,
        [x[0] for x in stripes],
    )
    h.shot("end")


d_follows.wait_ms = 1500


h.run(
    "meshinspect2_inspect",
    [s.new_design("MeshInspect2")]
    + s.box_steps("base", (0, 0, 40, 30), 10, V(6, -6, 0))
    + tall_steps()
    + s.box_steps("body2", (30, 0, 70, 30), 10, V(6, -6, 0), new_body=True)
    + s.box_steps("body3", (0, 50, 20, 70), 10, V(6, -6, 0), new_body=True)
    + [a_start, a_first, a_second, a_compute, a_result, a_ticked, a_made, a_undone, a_redone]
    + [b_pick, b_sharp, b_drawn, b_kept]
    + [c_second_component, c_measure, c_filter, c_first, c_one, c_two, c_root_body, c_refused]
    + [d_closed, i.new_design("MeshZebra")]
    + m.insert_file(sphere_file())
    + [d_zebra, d_pick, d_striped, d_kept, d_draft_refused, d_smooth_ok, d_follows],
)
