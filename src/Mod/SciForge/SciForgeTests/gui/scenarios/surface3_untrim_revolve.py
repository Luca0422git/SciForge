# SPDX-License-Identifier: LGPL-2.1-or-later
"""SURFACE > Untrim Type Manual and Keep Copy; SURFACE > Revolve Project Axis, Partial, To with
Two Sides, New Component; save and reopen (surface part 3), only real input in the dialogs.

The design (built for the scenario): a 30 x 30 patch at the origin with a round hole r 5 at
(15, 15); a sketch on XZ with the axis line (0, -3) - (0, 25) (global Z) and a line P1
(10, 0) - (10, 10); a sketch on XZ moved 5 off it with a line P2 (30, 0) - (30, 20).
Path U1 (Untrim Manual): SURFACE > Untrim, Type Manual: the Loops box takes the clicks (the
        Faces box goes); click the hole's edge: "1 loop", the hole closes (900). Keep Copy:
        a new body with the surface as it was (900 - 25 pi). OK: "Untrim 1".
Path U2 (undo / redo): Undo: the hole is back and the copy body gone; Redo: both back.
Path U3 (edit): double-click Untrim 1: Manual, 1 loop and Keep Copy read back; clear Keep
        Copy: the copy body goes. OK.
Path R1 (Revolve Partial, Project Axis, New Component): SURFACE > Revolve: Type reads Partial
        / To / Full, Project Axis is on; click P2, click the axis line; type 90: the axis laid
        into P2's plane, a quarter cylinder r 30 (942.48); Project Axis off: about the Z axis
        itself, r sqrt(925) (955.38); on again; Operation New Component: the body goes in a
        new component. OK: "Revolve 1".
Path R2 (To, Two Sides): SURFACE > Revolve, click P1, the axis line; Type To: Direction
        offers One Side / Two Sides only; click the YZ plane: a quarter turn (314.16); Two
        Sides: the Object Two box takes the clicks; click the XZ plane: the other side turns
        half a turn to it: three quarters of the cylinder r 10, h 10 (471.24). OK.
Path S (save / reopen): saved, closed, opened: the untrimmed face (900), the revolves (942.48,
        471.24) are back; double-click Revolve 2: To, Two Sides and both objects read back;
        Cancel.
"""

import math
import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import surface_steps as st
from SciForgeTests.gui import versions_input as vi

V = App.Vector
s = {}
HOLED = 900 - 25 * math.pi
R1_ON = math.pi * 30 * 20 / 2
R1_OFF = math.pi * math.sqrt(925) * 20 / 2
QUARTER = math.pi * 10 * 10 / 2
THREE_QUARTERS = 0.75 * 2 * math.pi * 10 * 10


def doc():
    return App.ActiveDocument


def by_label(label):
    found = doc().getObjectsByLabel(label)
    return found[0] if found else None


def new_design():
    import Part
    from sciforge import bodies, commands, sketch_ui, surface

    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("Surface3UntrimRevolve")
    body = commands.ensure_body()
    planes = sketch_ui.origin_planes(body)
    sk = sketch_ui.create_sketch(body, (planes["XY_Plane"], ""))
    st.add_lines(sk, [(0, 0), (30, 0), (30, 30), (0, 30)], closed=True)
    sk.addGeometry(Part.Circle(V(15, 15, 0), V(0, 0, 1), 5))
    commands.leave_edit()
    doc().recompute()
    refs = [(sk, "Edge%d" % (i + 1)) for i in range(5)]
    s["patch_step"] = surface.build("patch", {"refs": refs}, {})
    doc().recompute()
    s["patch"] = bodies.body_of(s["patch_step"])
    s["patch_sketch"] = sk
    axis = sketch_ui.create_sketch(body, (planes["XZ_Plane"], ""))
    st.add_lines(axis, [(0, -3), (0, 25)])
    st.add_lines(axis, [(10, 0), (10, 10)])
    commands.leave_edit()
    s["axis_sketch"] = axis
    moved = sketch_ui.create_sketch(body, (planes["XZ_Plane"], ""))
    moved.AttachmentOffset = App.Placement(V(0, 0, 5), App.Rotation())
    st.add_lines(moved, [(30, 0), (30, 20)])
    commands.leave_edit()
    s["moved_sketch"] = moved
    doc().recompute()
    s["bodies"] = len(st.bodies())
    h.fit()


def untrim_menu():
    from sciforge import bodies

    h.check("a patch with a hole", st.near(st.area(s["patch"]), HOLED, 1e-6), st.area(s["patch"]))
    for sk in (s["patch_sketch"], s["axis_sketch"], s["moved_sketch"]):
        bodies.set_shown(sk, False)  # the circle lies on the hole's edge, the others in front
    h.check("the sketches hidden", not bodies.is_shown(s["patch_sketch"]))
    h.click_empty()
    st.tab("SURFACE")
    st.menu("MODIFY", "Untrim")


def choose_manual():
    p = st.panel()
    h.check("Untrim dialog open", p is not None and p.kind == "untrim")
    if p is None:
        return
    box = p.rows["loop_type"][0]
    items = [box.itemText(i) for i in range(box.count())]
    h.check(
        "Type: All / Internal / External Edges, Manual",
        items == ["All Edges", "Internal Edges", "External Edges", "Manual"],
        items,
    )
    st.choose("loop_type", "Manual")


def loops_box():
    st.settle()
    p = st.panel()
    if p is None:
        return
    h.check("the Loops box is shown", p.is_shown("loops"))
    h.check("the Faces box is not", not p.is_shown("faces"))
    h.check("the Loops box takes the clicks", p.active == "loops", p.active)
    h.fit()
    h.check("clicked the hole's edge", h.click_edge(V(15, 10, 0)))  # not at its seam point


def hole_closed():
    st.settle()
    p = st.panel()
    if p is None:
        return
    h.check(
        "1 loop",
        len(p.picks["loops"]) == 1,
        (p.picks, p.active, st.message(), p.fields["loops"].button.text()),
    )
    body = st.step_body(p)
    h.check("the hole closes (900)", body is not None and st.near(st.area(body), 900.0, 1e-6))
    st.toggle_check("keep_copy")


def copy_made():
    st.settle()
    p = st.panel()
    from sciforge import bodies, surface

    pieces = surface.pieces_of(p.step) if p is not None and p.step is not None else []
    h.check("Keep Copy: one copy", len(pieces) == 1, pieces)
    if pieces:
        copy = bodies.body_of(pieces[0])
        s["copy"] = copy
        h.check("the copy is the surface as it was", st.near(st.area(copy), HOLED, 1e-6))
        h.check("in a body of its own", copy is not s["patch"])
    h.check("one more body", len(st.bodies()) == s["bodies"] + 1, st.bodies())
    h.shot("1-untrim-keep-copy")
    st.ok()


def untrim_done():
    h.check("dialog closed", st.panel() is None)
    titles = st.timeline_titles()
    h.check("Untrim 1 in the timeline", "Untrim 1" in titles, titles)
    st.undo()


def untrim_undone():
    h.check("Undo: the hole is back", st.near(st.area(s["patch"]), HOLED, 1e-6))
    h.check("and the copy body gone", len(st.bodies()) == s["bodies"], st.bodies())
    st.redo()


def untrim_redone():
    h.check("Redo: closed again", st.near(st.area(s["patch"]), 900.0, 1e-6))
    h.check("and the copy back", len(st.bodies()) == s["bodies"] + 1, st.bodies())
    h.check("edited from the timeline", st.double_click_timeline("Untrim 1"))


def untrim_reads_back():
    st.settle()
    p = st.panel()
    h.check("Untrim dialog for editing", p is not None and p.kind == "untrim" and p.editing)
    if p is None:
        return
    h.check("Manual read back", p.options["loop_type"] == "manual", p.options)
    h.check("1 loop read back", len(p.picks["loops"]) == 1, p.picks)
    h.check("Keep Copy read back", p.rows["keep_copy"][0].isChecked())
    st.toggle_check("keep_copy")


def copy_gone():
    st.settle()
    h.check("Keep Copy off: the copy body goes", len(st.bodies()) == s["bodies"], st.bodies())
    st.ok()


def untrim_edited():
    h.check("dialog closed", st.panel() is None)
    h.check("still 900", st.near(st.area(s["patch"]), 900.0, 1e-6))
    h.check("no copy", len(st.bodies()) == s["bodies"], st.bodies())


# -- Revolve: Project Axis, Partial, New Component ----------------------------------------------
def revolve_menu():
    from sciforge import bodies

    for sk in (s["axis_sketch"], s["moved_sketch"]):
        bodies.set_shown(sk, True)
    h.fit()
    h.click_empty()
    st.menu("CREATE", "Revolve")


def _on(sketch, x, y):
    return sketch.getGlobalPlacement().multVec(V(x, y, 0))


def r1_types():
    p = st.panel()
    h.check("Revolve dialog open", p is not None and p.kind == "revolve")
    if p is None:
        return
    box = p.rows["type"][0]
    types = [box.itemText(i) for i in range(box.count())]
    h.check("Type: Partial, To, Full", types == ["Partial", "To", "Full"], types)
    h.check("Project Axis on", p.rows["project_axis"][0].isChecked())
    h.check("clicked P2", h.click_edge(_on(s["moved_sketch"], 30, 12)))


def r1_axis():
    st.settle()
    p = st.panel()
    h.check("the Axis box takes the next click", p is not None and p.active == "axis")
    h.check("clicked the axis line", h.click_edge(_on(s["axis_sketch"], 0, 22)))


def r1_angle():
    st.settle()
    st.type_field("angle", "90")


def r1_projected():
    st.settle()
    body = st.step_body()
    s["rev1"] = body
    h.check("projected axis: r 30 (942.48)", st.near(st.area(body), R1_ON, 1e-5), st.area(body))
    st.toggle_check("project_axis")


def r1_not_projected():
    st.settle()
    area = st.area(s["rev1"])
    h.check("Project Axis off: r sqrt(925) (955.38)", st.near(area, R1_OFF, 1e-5), area)
    st.toggle_check("project_axis")


def r1_component():
    st.settle()
    h.check("on again: 942.48", st.near(st.area(s["rev1"]), R1_ON, 1e-5))
    st.choose("operation", "New Component")


def r1_ok():
    st.settle()
    from sciforge import components

    body = st.step_body()
    s["rev1"] = body
    container = components.container_of(body) if body is not None else None
    h.check("the body is in a new component", container is not None, container)
    h.check("still 942.48", st.near(st.area(body), R1_ON, 1e-5), st.area(body))
    st.ok()


def r1_done():
    h.check("dialog closed", st.panel() is None)
    titles = st.timeline_titles()
    h.check("Revolve 1 in the timeline", "Revolve 1" in titles, titles)


# -- Revolve To with Two Sides ----------------------------------------------------------------
def r2_menu():
    from sciforge import bodies

    for sk in (s["axis_sketch"], s["moved_sketch"]):  # the revolve hid them
        bodies.set_shown(sk, True)
    for body in (s["patch"], s["rev1"]):  # out of the way, as a person clicks the eyes
        bodies.set_shown(body, False)
    h.fit()
    h.click_empty()
    st.menu("CREATE", "Revolve")


def r2_profile():
    h.check("Revolve dialog open", st.panel() is not None)
    h.check("clicked P1", h.click_edge(_on(s["axis_sketch"], 10, 5)))


def r2_axis():
    st.settle()
    h.check("clicked the axis line", h.click_edge(_on(s["axis_sketch"], 0, 22)))


def r2_type_to():
    st.settle()
    st.choose("type", "To")


def r2_directions():
    st.settle()
    p = st.panel()
    if p is None:
        return
    box = p.rows["direction"][0]
    h.check("Direction is shown with To", box.isVisible())
    item = box.model().item(2)
    h.check("Symmetric is not offered with To", item is not None and not item.isEnabled())
    h.check("the Object box takes the clicks", p.active == "to_object", p.active)
    h.fit()
    pl.click_on_plane(V(0, -12, 8))


def r2_quarter():
    st.settle()
    body = st.step_body()
    s["rev2"] = body
    h.check("to YZ: a quarter turn (157.08)", st.near(st.area(body), QUARTER, 1e-5), st.area(body))
    st.choose("direction", "Two Sides")


def r2_two_sides():
    st.settle()
    p = st.panel()
    if p is None:
        return
    h.check("the Object Two box is shown", p.is_shown("to_object2"))
    h.check("and takes the clicks", p.active == "to_object2", p.active)
    h.fit()
    pl.click_on_plane(V(-16, 0, 15))


def r2_three_quarters():
    st.settle()
    p = st.panel()
    h.check("two objects", p is not None and len(p.refs()["refs3"]) == 2, p and p.refs())
    s["rev2"] = st.step_body()  # Two Sides waited for its second object: a new preview
    area = st.area(s["rev2"])
    h.check(
        "three quarters of the cylinder (471.24)",
        st.near(area, THREE_QUARTERS, 1e-5),
        (area, st.message()),
    )
    h.shot("2-revolve-two-sides")
    st.ok()


def r2_done():
    h.check("dialog closed", st.panel() is None)
    titles = st.timeline_titles()
    h.check("Revolve 2 in the timeline", "Revolve 2" in titles, titles)


# -- save / reopen ------------------------------------------------------------------------------
def save_first():
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-surface3-"), "surface3.FCStd")
    s["path"] = path
    s["labels"] = [s[k].Label for k in ("patch", "rev1", "rev2")]
    doc().saveAs(path)
    h.check("saved", os.path.isfile(path), path)
    h.press(QtCore.Qt.Key_S, QtCore.Qt.ControlModifier)


def describe():
    h.check("the Save dialog asks for a version description", vi.version_dialog() is not None)
    vi.accept_save()


def close():
    App.closeDocument(doc().Name)


def reopen():
    App.openDocument(s["path"])
    h.fit()


def reopened():
    patch, rev1, rev2 = (by_label(x) for x in s["labels"])
    h.check("the bodies are back", None not in (patch, rev1, rev2), s["labels"])
    if None in (patch, rev1, rev2):
        return
    h.check("the untrimmed face (900)", st.near(st.area(patch), 900.0, 1e-6), st.area(patch))
    h.check("Revolve 1 (942.48)", st.near(st.area(rev1), R1_ON, 1e-5), st.area(rev1))
    h.check("Revolve 2 (471.24)", st.near(st.area(rev2), THREE_QUARTERS, 1e-5), st.area(rev2))
    s["rev2"] = rev2
    h.check("edited from the timeline", st.double_click_timeline("Revolve 2"))


def reopened_reads_back():
    st.settle()
    p = st.panel()
    h.check("Revolve dialog for editing", p is not None and p.kind == "revolve" and p.editing)
    if p is None:
        return
    h.check("To read back", p.options["type"] == "to", p.options)
    h.check("Two Sides read back", p.options["direction"] == "two_sides", p.options)
    h.check(
        "both objects read back",
        len(p.picks["to_object"]) == 1 and len(p.picks["to_object2"]) == 1,
        p.picks,
    )
    st.cancel()


def reopened_cancelled():
    h.check("dialog closed", st.panel() is None)
    h.check("unchanged", st.near(st.area(s["rev2"]), THREE_QUARTERS, 1e-5))


h.run(
    "surface3_untrim_revolve",
    [
        new_design,
        untrim_menu,
        choose_manual,
        loops_box,
        hole_closed,
        copy_made,
        untrim_done,
        untrim_undone,
        untrim_redone,
        untrim_reads_back,
        copy_gone,
        untrim_edited,
        revolve_menu,
        r1_types,
        r1_axis,
        r1_angle,
        r1_projected,
        r1_not_projected,
        r1_component,
        r1_ok,
        r1_done,
        r2_menu,
        r2_profile,
        r2_axis,
        r2_type_to,
        r2_directions,
        r2_quarter,
        r2_two_sides,
        r2_three_quarters,
        r2_done,
        save_first,
        describe,
        close,
        reopen,
        reopened,
        reopened_reads_back,
        reopened_cancelled,
    ],
)
