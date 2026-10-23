# SPDX-License-Identifier: LGPL-2.1-or-later
"""SURFACE > Extend Natural on a curved (spherical) face and INSPECT > Environmental Map
Analysis (surface part 3), only real input in the dialogs.

The design (built for the scenario): a quarter arc r 10 in the XZ plane turned 90 degrees
about Z: an eighth of a sphere (157.08).
Path X1 (Extend Natural): SURFACE > Extend: Extend Type Natural, click the arc edge on the XZ
        plane; type 5: the sphere carried on past that edge by 5 mm (measured along the
        surface at the edge's middle): one face, still the sphere: 100 (pi / 2 + 5 / (10 cos
        45)) = 227.79. OK: "Extend 1". Undo: 157.08; Redo.
Path X2 (Align Edges): a trapezoid patch 20 / 10 wide, 10 high (150); SURFACE > Extend, Edge
        Alignment Align Edges, click its top edge, type 5: the slanted sides carried on, one
        flat face (187.5); Free Edges: square to the edge (200); Align Edges again, OK; edited
        from the timeline: Align Edges read back; Cancel.
Path M1 (Environmental Map): INSPECT > Environmental Map Analysis: Environment Studio,
        Reflection Strength 70; click the sphere: the studio reflected on it (the model's own
        faces covered); Environment Horizon and Reflection Strength 40: drawn again; OK:
        "Environmental Map1" in the browser's Analysis folder.
Path M2 (Esc): the analysis again, Esc: no second one.
Path M3 (save / reopen): saved, closed, opened: the analysis with Horizon and 40 % is drawn
        again on the extended sphere (227.79).
"""

import math

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import analysis_steps as a
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import surface_steps as st

V = App.Vector
s = {}
R = 10.0
OCTANT = 4 * math.pi * R * R / 8
EXTENDED = R * R * (math.pi / 2 + 5.0 / (R * math.cos(math.pi / 4)))


def doc():
    return App.ActiveDocument


def new_design():
    import Part
    from sciforge import bodies, commands, sketch_ui, surface

    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("Surface3ExtendEnvMap")
    body = commands.ensure_body()
    planes = sketch_ui.origin_planes(body)
    sk = sketch_ui.create_sketch(body, (planes["XZ_Plane"], ""))
    sk.addGeometry(Part.ArcOfCircle(Part.Circle(V(0, 0, 0), V(0, 0, 1), R), 0.0, math.pi / 2))
    commands.leave_edit()
    doc().recompute()
    z_axis = [o for o in body.Origin.OriginFeatures if getattr(o, "Role", "") == "Z_Axis"][0]
    step = surface.build(
        "revolve", {"refs": [(sk, "Edge1")], "refs2": [(z_axis, "")]}, {"angle": 90.0}
    )
    doc().recompute()
    s["sphere"] = bodies.body_of(step)
    s["sketch"] = sk
    h.fit()


def extend_menu():
    from sciforge import bodies

    bodies.set_shown(s["sketch"], False)  # the arc lies on the edge to click
    h.check(
        "an eighth of a sphere", st.near(st.area(s["sphere"]), OCTANT, 1e-6), st.area(s["sphere"])
    )
    h.click_empty()
    st.tab("SURFACE")
    st.menu("MODIFY", "Extend")


def click_arc():
    p = st.panel()
    h.check("Extend dialog open", p is not None and p.kind == "extend")
    if p is None:
        return
    h.check("Natural by default", p.options["extend_type"] == "natural", p.options)
    h.check("clicked the arc edge", h.click_edge(V(R * math.cos(math.radians(30)), 0, R / 2)))


def type_five():
    st.settle()
    p = st.panel()
    h.check("one edge", p is not None and len(p.picks["edges"]) == 1, p and p.picks)
    st.type_field("distance", "5")


def extended():
    st.settle()
    body = st.step_body()
    area = st.area(body)
    h.check("the sphere carried on 5 past the edge (227.79)", st.near(area, EXTENDED, 1e-5), area)
    faces = body.Shape.Faces if body is not None else []
    h.check("one face", len(faces) == 1, len(faces))
    if faces:
        kind = faces[0].Surface.TypeId
        h.check("still the sphere's own surface", "BSpline" not in kind, kind)
    h.shot("1-extend-natural-sphere")
    st.ok()


def extend_done():
    h.check("dialog closed", st.panel() is None)
    titles = st.timeline_titles()
    h.check("Extend 1 in the timeline", "Extend 1" in titles, titles)
    st.undo()


def undone():
    h.check("Undo: the eighth again", st.near(st.area(s["sphere"]), OCTANT, 1e-6))
    st.redo()


def redone():
    h.check("Redo: extended again", st.near(st.area(s["sphere"]), EXTENDED, 1e-5))


# -- Extend Natural, Edge Alignment Align Edges ---------------------------------------------
def x2_setup():
    from sciforge import bodies, commands, sketch_ui, surface

    body = bodies.body_of(s["sketch"])
    planes = sketch_ui.origin_planes(body)
    sk = sketch_ui.create_sketch(body, (planes["XY_Plane"], ""))
    st.add_lines(sk, [(30, 0), (50, 0), (45, 10), (35, 10)], closed=True)
    commands.leave_edit()
    doc().recompute()
    step = surface.build("patch", {"refs": [(sk, "Edge%d" % (i + 1)) for i in range(4)]}, {})
    doc().recompute()
    s["trapezoid"] = bodies.body_of(step)
    bodies.set_shown(sk, False)
    h.fit()
    h.click_empty()
    st.menu("MODIFY", "Extend")


def x2_align():
    p = st.panel()
    h.check("Extend dialog open", p is not None and p.kind == "extend")
    if p is None:
        return
    h.check("a trapezoid of 150", st.near(st.area(s["trapezoid"]), 150.0, 1e-6))
    box = p.rows["alignment"][0]
    items = [box.itemText(i) for i in range(box.count())]
    h.check(
        "Edge Alignment: Free Edges / Align Edges", items == ["Free Edges", "Align Edges"], items
    )
    item = box.model().item(1)
    h.check("Align Edges can be chosen", item is not None and item.isEnabled())
    st.choose("alignment", "Align Edges")


def x2_click():
    st.settle()
    h.check("clicked the trapezoid's top edge", h.click_edge(V(40, 10, 0)))


def x2_type():
    st.settle()
    st.type_field("distance", "5")


def x2_aligned():
    st.settle()
    body = st.step_body()
    area = st.area(body)
    h.check("Align Edges: the slanted sides carried on (187.5)", st.near(area, 187.5, 1e-6), area)
    h.check("one flat face", body is not None and len(body.Shape.Faces) == 1)
    h.shot("2-extend-align-edges")
    st.choose("alignment", "Free Edges")


def x2_free():
    st.settle()
    area = st.area(st.step_body())
    h.check("Free Edges: square to the edge (200)", st.near(area, 200.0, 1e-6), area)
    st.choose("alignment", "Align Edges")


def x2_ok():
    st.settle()
    st.ok()


def x2_done():
    h.check("dialog closed", st.panel() is None)
    h.check("kept aligned (187.5)", st.near(st.area(s["trapezoid"]), 187.5, 1e-6))
    h.check("edited from the timeline", st.double_click_timeline("Extend 2"))


def x2_reads_back():
    st.settle()
    p = st.panel()
    h.check("Align Edges read back", p is not None and p.options.get("alignment") == "align")
    st.cancel()


# -- Environmental Map Analysis --------------------------------------------------------------
def envmap_menu():
    a.inspect("Environmental Map Analysis")


def envmap_dialog():
    p = a.panel()
    h.check("Environmental Map dialog open", p is not None and p.kind == "EnvironmentMapAnalysis")
    if p is None:
        return
    combo = p.field("Environment")
    items = [combo.itemText(i) for i in range(combo.count())]
    h.check("Environment: Studio / Horizon", items == ["Studio", "Horizon"], items)
    slider = p.field("ReflectionStrength")
    h.check("Reflection Strength 70", slider.value() == 70, slider.value())
    h.click(V(5, 5, 7))


def _vp():
    found = a.analyses("EnvironmentMapAnalysis")
    if not found:
        return None, None
    return found[0], found[0].ViewObject.Proxy


def envmap_drawn():
    st.wait(600)
    obj, vp = _vp()
    h.check("an Environmental Map analysis", obj is not None)
    if obj is None:
        return
    h.check("on the sphere's body", obj.Targets and obj.Targets[0][0] is s["sphere"], obj.Targets)
    h.check(
        "the studio is reflected",
        getattr(vp, "environment", None) == ("Studio", 0.7),
        vp.__dict__.get("environment"),
    )
    h.check("the model's own faces are covered", not a.model_faces_shown(s["sphere"]))
    h.shot("2-environment-map")
    p = a.panel()
    if p is not None:
        a.set_combo(p.field("Environment"), "Horizon")
        a.slide(p.field("ReflectionStrength"), 40)


def envmap_changed():
    st.wait(600)
    obj, vp = _vp()
    h.check(
        "Horizon at 40 %",
        vp is not None and getattr(vp, "environment", None) == ("Horizon", 0.4),
        vp and vp.__dict__.get("environment"),
    )
    h.task_button("OK")


def envmap_done():
    h.check("dialog closed", a.panel() is None)
    found = a.analyses("EnvironmentMapAnalysis")
    h.check("one analysis kept", len(found) == 1, found)
    h.check(
        "named Environmental Map1",
        found and found[0].Label == "Environmental Map1",
        found and found[0].Label,
    )
    a.open_analysis_folder()


def envmap_again():
    labels = st.browser_labels()
    h.check(
        "Environmental Map1 in the browser's Analysis folder",
        "Environmental Map1" in labels,
        labels,
    )
    a.inspect("Environmental Map Analysis")


def envmap_esc():
    h.check("the dialog opened again", a.panel() is not None)
    st.esc()


def envmap_escaped():
    h.check("Esc closed it", a.panel() is None)
    h.check("no second analysis", len(a.analyses("EnvironmentMapAnalysis")) == 1)
    a.save_reopen("surface3_envmap.FCStd")


def reopened():
    st.wait(800)
    obj, vp = _vp()
    h.check("the analysis is back", obj is not None)
    if obj is None:
        return
    h.check("Horizon, 40 % read back", (obj.Environment, obj.ReflectionStrength) == ("Horizon", 40))
    h.check(
        "drawn again",
        getattr(vp, "environment", None) == ("Horizon", 0.4),
        getattr(vp, "environment", None),
    )
    body = obj.Targets[0][0] if obj.Targets else None
    area = st.area(body)
    h.check("the extended sphere is back (227.79)", st.near(area, EXTENDED, 1e-5), area)


h.run(
    "surface3_extend_envmap",
    [
        new_design,
        extend_menu,
        click_arc,
        type_five,
        extended,
        extend_done,
        undone,
        redone,
        x2_setup,
        x2_align,
        x2_click,
        x2_type,
        x2_aligned,
        x2_free,
        x2_ok,
        x2_done,
        x2_reads_back,
        envmap_menu,
        envmap_dialog,
        envmap_drawn,
        envmap_changed,
        envmap_done,
        envmap_again,
        envmap_esc,
        envmap_escaped,
        reopened,
    ],
)
