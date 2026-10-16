# SPDX-License-Identifier: LGPL-2.1-or-later
"""Insert STEP (INSERT menu), only real input.

Fixture: two_parts.step, "Plate" 40 x 30 x 5 (blue) and "Peg" radius 5, height 15 (red),
two parts side by side in the file (no assembly around them).

A  INSERT > Insert STEP: one component "two_parts" (the file, as Fusion inserts a design)
   holding the components Plate (6000 mm3) and Peg (1178.1 mm3), each with its body; the
   browser lists them, the bodies' steps are "Insert STEP 1/2" in the timeline, nothing
   is left of FreeCAD's reader (no link groups); Plate blue and Peg red, as a SciForge
   Appearance and on screen. The Move dialog opens on two_parts (Fusion's Initial
   Position); Esc leaves it where it came in.
B  Ctrl+Z: no bodies. Ctrl+Y: both again, still coloured.
C  The same file again: "two_parts (2)" with its own Plate and Peg.
D  The imported bodies work like any body: Create Sketch on the Plate's top face puts a
   sketch into the Plate's body.
"""

import FreeCAD as App
from PySide import QtCore

from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import exchange_steps as x
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import insert_steps as i

V = App.Vector
BLUE = (0.2, 0.4, 0.9)
RED = (0.9, 0.3, 0.2)


def same(a, c, tol=0.02):
    return a is not None and all(abs(x - y) <= tol for x, y in zip(a, c))


def screen_colour(body):
    try:
        return tuple(round(c, 3) for c in body.Tip.ViewObject.ShapeAppearance[0].DiffuseColor[:3])
    except Exception:
        return None


def move_panel():
    from sciforge import component_move_ui, taskui

    p = taskui.current()
    return p if isinstance(p, component_move_ui.ComponentMovePanel) else None


# -- A ----------------------------------------------------------------------------------------
def a_insert():
    i.use_file(i.fixture("two_parts.step"))
    i.menu("INSERT", "Insert STEP")


a_insert.wait_ms = 2000


def a_check():
    bodies = s.bodies()
    h.check("two bodies", len(bodies) == 2, [b.Label for b in bodies])
    top = x.comp("two_parts")
    h.check("a component two_parts at the root", top is not None and x.parent_label(top) is None)
    for label in ("Plate", "Peg"):
        c = x.comp(label)
        h.check(
            "%s is a component in two_parts" % label,
            c is not None and x.parent_label(c) == "two_parts",
            c and x.parent_label(c),
        )
    plate, peg = x.body_of("Plate"), x.body_of("Peg")
    h.check(
        "Plate 6000 mm3",
        plate is not None and i.close(s.volume(plate), i.PLATE_VOLUME),
        plate and s.volume(plate),
    )
    h.check(
        "Peg 1178.1 mm3",
        peg is not None and i.close(s.volume(peg), i.PEG_VOLUME, 1e-4),
        peg and s.volume(peg),
    )
    doc = App.ActiveDocument
    leftovers = [o.Name for o in doc.Objects if o.TypeId in ("App::Link", "App::LinkGroup")]
    h.check("nothing left from the file's reader", not leftovers, leftovers)
    h.check(
        "browser lists Plate and Peg",
        i.browser_has("Plate") and i.browser_has("Peg"),
        i.browser_labels(),
    )
    if plate is not None and peg is not None:
        titles = [s.timeline_title_of(plate.Tip), s.timeline_title_of(peg.Tip)]
        h.check(
            "timeline: Insert STEP 1 and 2", titles == ["Insert STEP 1", "Insert STEP 2"], titles
        )
        h.check("Plate is blue (appearance)", same(x.look_of(plate), BLUE), x.look_of(plate))
        h.check("Peg is red (appearance)", same(x.look_of(peg), RED), x.look_of(peg))
        h.check("Plate blue on screen", same(screen_colour(plate), BLUE), screen_colour(plate))
        h.check("Peg red on screen", same(screen_colour(peg), RED), screen_colour(peg))
    h.check("the Move dialog opened on two_parts", move_panel() is not None)
    h.press(QtCore.Qt.Key_Escape)


a_check.wait_ms = 1000


# -- B ----------------------------------------------------------------------------------------
def b_undo():
    h.check("Esc closed the Move dialog", move_panel() is None)
    top = x.comp("two_parts")
    h.check(
        "two_parts stays where it came in",
        top is not None and x.near3(tuple(top.Placement.Base), (0, 0, 0)),
    )
    s.no_popups("Insert STEP")
    i.undo()


def b_check_undo():
    h.check("Ctrl+Z: no bodies", len(s.bodies()) == 0, [b.Label for b in s.bodies()])
    h.check("Ctrl+Z: no components", not x.comps(), x.labels())


def b_redo():
    i.redo()


def b_check_redo():
    bodies = s.bodies()
    h.check("Ctrl+Y: two bodies", len(bodies) == 2, [b.Label for b in bodies])
    plate = x.body_of("Plate")
    h.check(
        "still blue", plate is not None and same(x.look_of(plate), BLUE), plate and x.look_of(plate)
    )


# -- C ----------------------------------------------------------------------------------------
def c_again():
    i.menu("INSERT", "Insert STEP")


c_again.wait_ms = 2000


def c_check():
    h.press(QtCore.Qt.Key_Escape)
    labels = x.labels()
    h.check(
        "a second two_parts with its own Plate and Peg",
        labels == ["Peg", "Peg", "Plate", "Plate", "two_parts", "two_parts (2)"],
        labels,
    )
    h.check("four bodies", len(s.bodies()) == 4, [b.Label for b in s.bodies()])


c_check.wait_ms = 1000


# -- D ----------------------------------------------------------------------------------------
def d_sketch():
    # the second insert lies on top of the first: hide it, as a person would
    second = x.comp("two_parts (2)")
    if second is not None:
        second.ViewObject.Visibility = False
    h.fit()
    h.ribbon("Create Sketch")


def d_click_plate():
    h.fit()
    h.click(V(8, 8, 5))


def d_check():
    sketch = h.in_sketch()
    h.check("a sketch opened on the plate", sketch is not None)
    plate = x.body_of("Plate")
    if sketch is not None and plate is not None:
        h.check("in the Plate's body", sketch in plate.Group, [o.Label for o in plate.Group])
    i.no_file()


def d_finish():
    if h.in_sketch() is not None:
        h.ribbon("Finish Sketch")
    h.shot("end")


h.run(
    "insert_step",
    [
        i.new_design("InsertStep"),
        a_insert,
        a_check,
        b_undo,
        b_check_undo,
        b_redo,
        b_check_redo,
        c_again,
        c_check,
        d_sketch,
        d_click_plate,
        d_check,
        d_finish,
    ],
)
