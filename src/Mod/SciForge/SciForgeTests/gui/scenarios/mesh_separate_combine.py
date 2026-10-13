# SPDX-License-Identifier: LGPL-2.1-or-later
"""MESH > Separate a two-part STL, then Combine with another mesh body; only real input.

two_boxes.stl holds two 10 mm cubes 10 mm apart (one file, two shells, as a downloaded
multi-part print often is); bar.stl a 10 x 6 x 6 bar that pokes 5 mm into the first cube.

A  Insert Mesh two_boxes.stl: one mesh body, 2 shells.
B  Pick it in the browser, MESH > Separate: Separate Type Mesh Shells (Fusion's); at once two
   pieces "two_boxes" and "two_boxes (2)", 1000 mm3 each, the body hidden. OK: "Separate 1" in
   the timeline, the browser lists the two pieces.
C  Ctrl+Z: one body again; Ctrl+Y: the two pieces.
D  Insert Mesh bar.stl. MESH > Combine: the Target Body box waits; click the first cube, then
   the bar: Operation Join (Fusion's): 1180 mm3, closed, the bar hidden. Cut: 820 mm3,
   Intersect: 180 mm3, Merge: both kept (1360 mm3). Join and OK: "Combine 1", the bar used up.
E  A refusal: Combine the second cube with an open sheet, Join: the dialog says the bodies
   must be closed (Repair first, or Merge); OK waits; Cancel.
F  Timeline double-click Combine 1: Keep Tools on, OK: the bar is a body again (shown,
   listed), the combined cube still 1180 mm3.
"""

from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import insert_steps as i
from SciForgeTests.gui import mesh_steps as m

V = i.V
state = {}


def two_boxes_file():
    tris = m.box_triangles(0, 0, 0, 10, 10, 10) + m.box_triangles(20, 0, 0, 30, 10, 10)
    return m.write_stl("two_boxes.stl", tris)


def bar_file():
    return m.write_stl("bar.stl", m.box_triangles(5, 2, 2, 15, 8, 8))


def sheet_file():
    tris = [
        ((0.0, 0.0, 12.0), (10.0, 0.0, 12.0), (10.0, 10.0, 12.0)),
        ((0.0, 0.0, 12.0), (10.0, 10.0, 12.0), (0.0, 10.0, 12.0)),
    ]
    return m.write_stl("sheet.stl", tris)


def near(a, b, tol):
    return a is not None and abs(a - b) <= tol


# -- A ----------------------------------------------------------------------------------------
def a_check():
    b = m.body("two_boxes")
    h.check("one mesh body", b is not None and len(m.bodies()) == 1, m.browser_labels())
    if b is not None:
        info = m.analysis(b)
        h.check("2 shells", info.get("shells") == 2, info)
        state["source"] = b.Name


# -- B ----------------------------------------------------------------------------------------
def b_open():
    m.mesh_tab()
    h.fit()
    s.click_browser_row("two_boxes")
    s.menu("MODIFY", "Separate")


b_open.wait_ms = 2000


def b_dialog():
    p = m.panel()
    h.check("Separate dialog", p is not None and p.title == "Separate", p)
    if p is None:
        return
    h.check("the picked body was taken", p.body is not None and p.body.Label == "two_boxes")
    h.check("Separate Type Mesh Shells", p.separate_type.currentText() == "Mesh Shells")
    h.check("Keep Body off", not p.keep.isChecked())
    step = m.steps("MeshSeparate")
    pieces = []
    if step:
        from sciforge import mesh

        pieces = mesh.pieces_of(step[0])
    h.check("two pieces at once", len(pieces) == 2, pieces)
    if len(pieces) == 2:
        h.check(
            "named two_boxes and two_boxes (2)",
            [x.Label for x in pieces] == ["two_boxes", "two_boxes (2)"],
            [x.Label for x in pieces],
        )
        for piece in pieces:
            h.check(
                "%s: 1000 mm3" % piece.Label, near(m.volume(piece), 1000.0, 1e-6), m.volume(piece)
            )
            h.check("%s shown" % piece.Label, m.shown(piece))
    source = m.doc().getObject(state.get("source", ""))
    h.check("the body hidden", source is not None and not m.shown(source))
    h.task_button("OK")


b_dialog.wait_ms = 1500


def b_done():
    h.check("dialog closed", m.panel() is None)
    labels = sorted(x.Label for x in m.bodies())
    h.check("two bodies listed", labels == ["two_boxes", "two_boxes (2)"], labels)
    browser = m.browser_labels()
    h.check(
        "the browser lists both", "two_boxes" in browser and "two_boxes (2)" in browser, browser
    )
    step = m.steps("MeshSeparate")
    h.check(
        "timeline: Separate 1",
        bool(step) and m.timeline_title(step[0]) == "Separate 1",
        step and m.timeline_title(step[0]),
    )


# -- C ----------------------------------------------------------------------------------------
def c_undo():
    i.undo()


c_undo.wait_ms = 1500


def c_check_undo():
    h.check(
        "Ctrl+Z: one body again",
        [x.Label for x in m.bodies()] == ["two_boxes"],
        [x.Label for x in m.bodies()],
    )
    h.check("no Separate step", not m.steps("MeshSeparate"))


def c_redo():
    i.redo()


c_redo.wait_ms = 1500


def c_check_redo():
    labels = sorted(x.Label for x in m.bodies())
    h.check("Ctrl+Y: the two pieces", labels == ["two_boxes", "two_boxes (2)"], labels)
    piece = m.body("two_boxes (2)")
    h.check(
        "the second piece is 1000 mm3",
        piece is not None and near(m.volume(piece), 1000.0, 1e-6),
        piece and m.volume(piece),
    )


# -- D ----------------------------------------------------------------------------------------
def d_open():
    s.menu("MODIFY", "Combine")


d_open.wait_ms = 1500


def d_waits():
    p = m.panel()
    h.check("Combine dialog", p is not None and p.title == "Combine", p)
    if p is None:
        return
    h.check("the Target Body box waits", p.active == "body" and p.body is None, p.active)
    h.check("Operation Join", p.operation.currentText() == "Join")
    h.check("Keep Tools off", not p.keep.isChecked())
    m.click_body(m.body("two_boxes"))


d_waits.wait_ms = 1500


def d_target():
    p = m.panel()
    h.check(
        "the first cube is the target",
        p.body is not None and p.body.Label == "two_boxes",
        p.body and p.body.Label,
    )
    h.check("then the Tool Bodies box waits", p.active == "tools", p.active)
    bar = m.body("bar")
    state["bar"] = bar.Name if bar is not None else ""
    h.click(V(14.0, 5.0, 8.0))  # the end of the bar outside the cube


d_target.wait_ms = 2500


def d_join():
    p = m.panel()
    h.check("the bar is the tool", [t.Label for t in p.tools] == ["bar"], p.tools)
    step = m.steps("MeshCombine")[0]
    h.check("Join: 1180 mm3", near(m.volume(step), 1180.0, 2.0), m.volume(step))
    h.check("Join: closed", m.closed(step), m.analysis(step))
    bar = m.doc().getObject(state["bar"])
    h.check("the bar hidden", bar is not None and not m.shown(bar))
    m.choose(p.operation, "Cut")


d_join.wait_ms = 2500


def d_cut():
    step = m.steps("MeshCombine")[0]
    h.check("Cut: 820 mm3", near(m.volume(step), 820.0, 2.0), m.volume(step))
    h.check("Cut: closed", m.closed(step), m.analysis(step))
    m.choose(m.panel().operation, "Intersect")


d_cut.wait_ms = 2500


def d_intersect():
    step = m.steps("MeshCombine")[0]
    h.check("Intersect: 180 mm3", near(m.volume(step), 180.0, 2.0), m.volume(step))
    m.choose(m.panel().operation, "Merge")


d_intersect.wait_ms = 2500


def d_merge():
    step = m.steps("MeshCombine")[0]
    h.check("Merge: both kept (1360 mm3)", near(m.volume(step), 1360.0, 1e-3), m.volume(step))
    h.check("Merge: 24 faces", m.facets(step) == 24, m.facets(step))
    m.choose(m.panel().operation, "Join")


d_merge.wait_ms = 2500


def d_ok():
    h.task_button("OK")


d_ok.wait_ms = 1500


def d_done():
    h.check("dialog closed", m.panel() is None)
    cube = m.body("two_boxes")
    h.check(
        "the cube is the Combine step",
        cube is not None and cube.SciForgeType == "MeshCombine",
        cube and cube.Name,
    )
    h.check(
        "1180 mm3", cube is not None and near(m.volume(cube), 1180.0, 2.0), cube and m.volume(cube)
    )
    h.check(
        "timeline: Combine 1",
        cube is not None and m.timeline_title(cube) == "Combine 1",
        cube and m.timeline_title(cube),
    )
    h.check("the bar is used up (not listed)", m.body("bar") is None, m.browser_labels())
    h.check(
        "the browser lists two bodies",
        sorted(x.Label for x in m.bodies()) == ["two_boxes", "two_boxes (2)"],
        [x.Label for x in m.bodies()],
    )


# -- E ----------------------------------------------------------------------------------------
def e_open():
    s.menu("MODIFY", "Combine")


e_open.wait_ms = 1500


def e_target():
    s.click_browser_row("two_boxes (2)")


e_target.wait_ms = 1500


def e_tool():
    p = m.panel()
    h.check(
        "the second cube is the target",
        p is not None and p.body is not None and p.body.Label == "two_boxes (2)",
        p and p.body and p.body.Label,
    )
    s.click_browser_row("sheet")


e_tool.wait_ms = 2500


def e_refused():
    p = m.panel()
    text = p.message.text() if p else ""
    h.check("the dialog says closed bodies are needed", "closed" in text and "Repair" in text, text)
    h.task_button("OK")


e_refused.wait_ms = 1200


def e_waits():
    p = m.panel()
    h.check("OK waits", p is not None and p.title == "Combine", p)
    h.task_button("Cancel")


e_waits.wait_ms = 1500


def e_check():
    h.check("dialog closed", m.panel() is None)
    h.check("one Combine step", len(m.steps("MeshCombine")) == 1, m.steps("MeshCombine"))
    sheet = m.body("sheet")
    h.check("the sheet shown as it was", sheet is not None and m.shown(sheet))
    second = m.body("two_boxes (2)")
    h.check(
        "the second cube as it was",
        second is not None and m.shown(second) and near(m.volume(second), 1000.0, 1e-6),
    )


# -- F ----------------------------------------------------------------------------------------
def f_edit():
    s.timeline_double_click(m.steps("MeshCombine")[0])


f_edit.wait_ms = 2500


def f_keep():
    p = m.panel()
    h.check("Combine edit dialog", p is not None and p.title == "Combine", p)
    if p is None:
        return
    h.check("the bar is its tool", [t.Label for t in p.tools] == ["bar"], p.tools)
    m.tick(p.keep, True)


f_keep.wait_ms = 2500


def f_ok():
    bar = m.doc().getObject(state["bar"])
    h.check("Keep Tools: the bar shown", bar is not None and m.shown(bar))
    h.task_button("OK")


f_ok.wait_ms = 1500


def f_check():
    h.check("dialog closed", m.panel() is None)
    bar = m.body("bar")
    h.check("the bar is a body again", bar is not None and m.shown(bar), m.browser_labels())
    h.check("listed in the browser", "bar" in m.browser_labels(), m.browser_labels())
    cube = m.body("two_boxes")
    h.check(
        "the cube still 1180 mm3",
        cube is not None and near(m.volume(cube), 1180.0, 2.0),
        cube and m.volume(cube),
    )
    h.shot("end")


h.run(
    "mesh_separate_combine",
    [i.new_design("MeshSeparate")]
    + m.insert_file(two_boxes_file())
    + [a_check, b_open, b_dialog, b_done, c_undo, c_check_undo, c_redo, c_check_redo]
    + m.insert_file(bar_file())
    + [d_open, d_waits, d_target, d_join, d_cut, d_intersect, d_merge, d_ok, d_done]
    + m.insert_file(sheet_file())
    + [e_open, e_target, e_tool, e_refused, e_waits, e_check, f_edit, f_keep, f_ok, f_check],
)
