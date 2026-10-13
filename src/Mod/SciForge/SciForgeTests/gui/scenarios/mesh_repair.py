# SPDX-License-Identifier: LGPL-2.1-or-later
"""MESH > Repair on a broken STL, then Convert Mesh to a solid; only real input.

The STL is made here: a 20 x 10 x 5 box with a hole (a triangle missing), two triangles facing
the wrong way and a doubled triangle (and, as in every STL, each corner repeated on every
triangle).

A  INSERT > Insert Mesh with it: the browser flags the body (a warning: not closed, the
   hole and the flipped faces named).
B  MESH > Repair: the dialog waits for a body; click it: Repair Type is Stitch and Remove
   (Fusion's), the problems are listed, Preview is off (the body shown as it is).
C  Close Holes with Preview: still not closed (the doubled triangle), the dialog says to try
   Wrap or Rebuild.
D  Stitch and Remove: closed, 12 faces, 1000 mm3.
E  OK: one body in the browser, no warning; "Repair 1" in the timeline; the inserted mesh is
   used up (hidden, not listed).
F  Ctrl+Z: the repair is gone and the broken body back (warning again); Ctrl+Y: repaired.
G  MESH > Convert Mesh, click the repaired body: a solid of 1000 mm3.
H  A flat sheet (a surface, no inside): Repair > Rebuild says it cannot be repaired and OK
   waits; Cancel leaves the sheet as it was.
"""

from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import insert_steps as i
from SciForgeTests.gui import mesh_steps as m

state = {}


def broken():
    return m.body("broken_box")


# -- A ----------------------------------------------------------------------------------------
def a_check():
    body = broken()
    h.check("the broken box is a mesh body", body is not None, m.browser_labels())
    if body is None:
        return
    info = m.analysis(body)
    h.check("the STL has a hole", info["holes"] == 1, info)
    h.check("and flipped faces", info["flipped"] > 0, info)
    node = m.browser_node("broken_box")
    h.check(
        "the browser flags it (not closed)",
        node is not None and node["status"] == "warning" and "Repair" in node["tip"],
        node and (node["status"], node["tip"]),
    )
    state["insert"] = body.Name


# -- B ----------------------------------------------------------------------------------------
def b_open():
    m.mesh_tab()
    h.fit()
    h.ribbon("Repair")


def b_waits():
    p = m.panel()
    h.check("Repair dialog", p is not None and p.title == "Repair", p)
    s.no_popups("Repair")
    h.check("no step yet", not m.steps("MeshRepair"))
    if p is not None:
        h.check("Repair Type starts at Stitch and Remove",
                p.repair_type.currentText() == "Stitch and Remove", p.repair_type.currentText())
        h.check("Preview off", not p.preview.isChecked())


def b_click():
    m.click_body(broken())


b_click.wait_ms = 1500


def b_picked():
    p = m.panel()
    steps = m.steps("MeshRepair")
    h.check("a Repair step", len(steps) == 1, steps)
    if p is None:
        return
    h.check("the Body box names it", "broken_box" in p.fields["body"].button.text(),
            p.fields["body"].button.text())
    text = p.info.text()
    h.check("the problems are listed", "1 hole" in text and "flipped" in text, text)
    h.check("Preview off says so", "Tick Preview" in text, text)
    if steps:
        h.check("not computed yet: the body as it was", m.facets(steps[0]) == 12, m.facets(steps[0]))


# -- C ----------------------------------------------------------------------------------------
def c_close_holes():
    p = m.panel()
    m.choose(p.repair_type, "Close Holes")
    m.tick(p.preview, True)


c_close_holes.wait_ms = 1500


def c_check():
    p = m.panel()
    step = m.steps("MeshRepair")[0]
    text = p.info.text()
    h.check("Close Holes: not closed yet, try Wrap or Rebuild",
            "Not closed yet" in text and "Wrap" in text, text)
    h.check("the preview is the step", m.shown(step), step.Name)


# -- D ----------------------------------------------------------------------------------------
def d_stitch():
    p = m.panel()
    m.choose(p.repair_type, "Stitch and Remove")


d_stitch.wait_ms = 1500


def d_check():
    p = m.panel()
    step = m.steps("MeshRepair")[0]
    text = p.info.text()
    h.check("Stitch and Remove: closed", "closed (watertight)" in text, text)
    h.check("12 faces", m.facets(step) == 12, m.facets(step))
    h.check("1000 mm3", i.close(m.volume(step), 1000.0, 1e-6), m.volume(step))
    h.check("no warning in the dialog", p.message.text() == "", p.message.text())


# -- E ----------------------------------------------------------------------------------------
def e_ok():
    h.task_button("OK")


e_ok.wait_ms = 1200


def e_check():
    h.check("dialog closed", m.panel() is None)
    body = broken()
    h.check("one body named broken_box", len([b for b in m.bodies() if b.Label == "broken_box"]) == 1,
            [b.Label + "/" + b.Name for b in m.bodies()])
    if body is not None:
        h.check("the body is the Repair step", body.SciForgeType == "MeshRepair", body.Name)
        h.check("closed", m.closed(body))
        node = m.browser_node("broken_box")
        h.check("no warning in the browser", node is not None and node["status"] == "ok",
                node and (node["status"], node["tip"]))
        h.check("timeline: Repair 1", m.timeline_title(body) == "Repair 1", m.timeline_title(body))
        h.check("shown as Repair 1 (its own name)", m.timeline_display(body) == "Repair 1",
                m.timeline_display(body))
    insert = m.doc().getObject(state.get("insert", ""))
    h.check("the inserted mesh is used up (hidden)", insert is not None and not m.shown(insert))
    h.check("the browser lists one body", i.browser_labels().count("broken_box") == 1,
            i.browser_labels())


# -- F ----------------------------------------------------------------------------------------
def f_undo():
    i.undo()


f_undo.wait_ms = 1200


def f_check_undo():
    h.check("Ctrl+Z: no Repair step", not m.steps("MeshRepair"))
    insert = m.doc().getObject(state.get("insert", ""))
    h.check("the broken body is shown again", insert is not None and m.shown(insert))
    node = m.browser_node("broken_box")
    h.check("the warning is back", node is not None and node["status"] == "warning",
            node and node["status"])


def f_redo():
    i.redo()


f_redo.wait_ms = 1200


def f_check_redo():
    body = broken()
    h.check("Ctrl+Y: repaired again", body is not None and body.SciForgeType == "MeshRepair",
            body and body.Name)
    h.check("closed", m.closed(body))
    insert = m.doc().getObject(state.get("insert", ""))
    h.check("the inserted mesh hidden again", insert is not None and not m.shown(insert))


# -- G ----------------------------------------------------------------------------------------
def g_convert():
    h.ribbon("Convert Mesh")


def g_click():
    m.click_body(broken())


g_click.wait_ms = 1500


def g_ok():
    p = m.panel()
    h.check("Convert Mesh dialog", p is not None and p.title == "Convert Mesh", p)
    h.task_button("OK")


g_ok.wait_ms = 1500


def g_check():
    bodies = s.bodies()
    h.check("a solid body", len(bodies) == 1, len(bodies))
    if bodies:
        h.check("1000 mm3", i.close(s.volume(bodies[0]), 1000.0, 1e-6), s.volume(bodies[0]))
        h.check("named after the mesh", bodies[0].Label == "broken_box (solid)", bodies[0].Label)


# -- H ----------------------------------------------------------------------------------------
def h_sheet_file():
    tris = [((0, 0, 0), (10, 0, 0), (10, 10, 0)), ((0, 0, 0), (10, 10, 0), (0, 10, 0))]
    state["sheet"] = m.write_stl("sheet.stl", [tuple(tuple(float(c) for c in p) for p in t)
                                               for t in tris])


def h_insert():
    i.use_file(state["sheet"])
    h.ribbon("Insert Mesh")


def h_insert_ok():
    h.task_button("OK")
    i.no_file()


h_insert_ok.wait_ms = 1000


def h_repair():
    sheet = m.body("sheet")
    h.check("the sheet is a mesh body", sheet is not None, m.browser_labels())
    s.click_browser_row("sheet")
    h.ribbon("Repair")


h_repair.wait_ms = 1200


def h_rebuild():
    p = m.panel()
    h.check("Repair took the picked sheet", p is not None and p.body is not None
            and p.body.Label == "sheet", p and p.body and p.body.Label)
    m.choose(p.repair_type, "Rebuild")
    m.tick(p.preview, True)


h_rebuild.wait_ms = 2500


def h_refused():
    p = m.panel()
    text = p.message.text() if p else ""
    h.check("the dialog says it cannot be repaired", "no volume" in text or "cannot" in text, text)
    h.task_button("OK")


h_refused.wait_ms = 1500


def h_stays_open():
    p = m.panel()
    h.check("OK waits", p is not None and p.title == "Repair", p)
    h.check("still says why", p is not None and "no volume" in p.message.text(),
            p and p.message.text())
    h.task_button("Cancel")


h_stays_open.wait_ms = 1200


def h_check():
    h.check("dialog closed", m.panel() is None)
    sheet = m.body("sheet")
    h.check("the sheet is as it was", sheet is not None and sheet.TypeId == "Mesh::Feature"
            and m.facets(sheet) == 2, sheet and (sheet.TypeId, m.facets(sheet)))
    h.check("one Repair step (the box's)", len(m.steps("MeshRepair")) == 1, m.steps("MeshRepair"))
    h.shot("end")


h.run(
    "mesh_repair",
    [i.new_design("MeshRepair")]
    + m.insert_file(m.broken_box_stl())
    + [
        a_check,
        b_open,
        b_waits,
        b_click,
        b_picked,
        c_close_holes,
        c_check,
        d_stitch,
        d_check,
        e_ok,
        e_check,
        f_undo,
        f_check_undo,
        f_redo,
        f_check_redo,
        g_convert,
        g_click,
        g_ok,
        g_check,
        h_sheet_file,
        h_insert,
        h_insert_ok,
        h_repair,
        h_rebuild,
        h_refused,
        h_stays_open,
        h_check,
    ],
)
