# SPDX-License-Identifier: LGPL-2.1-or-later
"""Insert STEP into the current design: the whole file as one component with its structure,
then Fusion's Initial Position (the Move dialog) places it (exchange-2,
docs/sciforge/parity/insert-export.md Part 2). Real input; the file dialog is the only
stand-in (insert_ui.FILE_PICKER).

A design "Cart" with a plate body.
P1  INSERT > Insert STEP, robot.step: a component "robot" at the root holding Base and Drive
    (Axle, Wheel, Wheel:2 a copy of Wheel); the plate is untouched; the Move dialog opens on
    "robot".
P2  X Distance 100, OK: the robot moved 100 along X (its bodies with it).
P3  Ctrl+Z: the move undone (robot at 0); Ctrl+Z: the insert undone (no robot, the plate
    stays); Ctrl+Y twice: back, moved.
P4  Base activated (its ring), Insert STEP of two_parts.step: "two_parts" goes inside Base,
    with Plate and Peg; Esc in the Move dialog leaves it where it came in.
P5  The design activated again, robot.step once more: "robot (2)".
P6  The file dialog cancelled: nothing happens. A broken file: refused with the reason,
    nothing added.
"""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import component_steps as c
from SciForgeTests.gui import exchange_steps as x
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import insert_steps as i
from SciForgeTests.gui import timeline_input as t

s = {}


def setup():
    import Part

    from sciforge import components

    Gui.activateWorkbench("SciForgeWorkbench")
    s["robot"] = x.make_robot(x.out("robot.step"))
    s["broken"], _sat = x.make_bad_files()
    doc = App.newDocument("Cart")
    body = components.new_body_in(doc, None, "Plate")
    base = doc.addObject("Part::Feature", "PlateShape")
    base.Shape = Part.makeBox(100, 50, 5, App.Vector(-120, 0, 0))
    body.BaseFeature = base
    doc.recompute()
    h.fit()
    s["plate"] = body.Name


def plate():
    return App.ActiveDocument.getObject(s["plate"])


def move_panel():
    from sciforge import component_move_ui, taskui

    p = taskui.current()
    return p if isinstance(p, component_move_ui.ComponentMovePanel) else None


# -- P1 ----------------------------------------------------------------------------------------
def p1_insert():
    i.use_file(s["robot"])
    i.menu("INSERT", "Insert STEP")


p1_insert.wait_ms = 2500


def p1_check():
    robot = x.comp("robot")
    h.check("P1 a component robot", robot is not None, x.labels())
    h.check("P1 at the root", robot is not None and x.parent_label(robot) is None)
    x.check_robot("P1", top="robot")
    h.check(
        "P1 the plate is untouched", plate() is not None and x.near(plate().Shape.Volume, 25000.0)
    )
    p = move_panel()
    h.check("P1 the Move dialog opened (Initial Position)", p is not None, h.popups())
    if p is not None:
        picked = [o.Label for o in p.options.get("components", [])]
        h.check("P1 it moves the robot", picked == ["robot"], picked)
    h.check("P1 SciForge says what came in", "robot.step" in x.told(), x.told())
    h.shot("1-inserted")


# -- P2 ----------------------------------------------------------------------------------------
def p2_type():
    p = move_panel()
    if p is None:
        return
    i.type_value(p.distance_fields[0], "100")


p2_type.wait_ms = 800


def p2_ok():
    h.task_button("OK")


p2_ok.wait_ms = 1200


def p2_check():
    robot = x.comp("robot")
    h.check("P2 the dialog closed", move_panel() is None)
    h.check(
        "P2 the robot moved 100 along X",
        robot is not None and x.near3(tuple(robot.Placement.Base), (100, 0, 0)),
        robot and robot.Placement.Base,
    )
    base = x.body_of("Base")
    h.check(
        "P2 its bodies with it",
        base is not None and x.near3(x.centre(base), (130, 20, 5)),
        base and x.centre(base),
    )


# -- P3 ----------------------------------------------------------------------------------------
def p3_undo_move():
    t.ctrl("z")


p3_undo_move.wait_ms = 1200


def p3_undo_insert():
    robot = x.comp("robot")
    h.check(
        "P3 Ctrl+Z: the robot back where it came in",
        robot is not None and x.near3(tuple(robot.Placement.Base), (0, 0, 0)),
        robot and robot.Placement.Base,
    )
    t.ctrl("z")


p3_undo_insert.wait_ms = 1500


def p3_redo():
    h.check("P3 Ctrl+Z again: no robot", x.comp("robot") is None, x.labels())
    h.check("P3 no components left", not x.comps(), x.labels())
    h.check("P3 the plate stays", plate() is not None)
    t.ctrl("y")


p3_redo.wait_ms = 1500


def p3_redo_move():
    x.check_robot("P3 redo", top="robot")
    t.ctrl("y")


p3_redo_move.wait_ms = 1500


def p3_check():
    robot = x.comp("robot")
    h.check(
        "P3 Ctrl+Y twice: moved again",
        robot is not None and x.near3(tuple(robot.Placement.Base), (100, 0, 0)),
        robot and robot.Placement.Base,
    )


# -- P4 ----------------------------------------------------------------------------------------
def p4_activate_base():
    c.click_radio("Base")


p4_activate_base.wait_ms = 800


def p4_insert():
    from sciforge import components

    active = components.active_component(App.ActiveDocument)
    h.check("P4 Base is active", active is not None and active.Label == "Base", active)
    i.use_file(i.fixture("two_parts.step"))
    i.menu("INSERT", "Insert STEP")


p4_insert.wait_ms = 2500


def p4_escape():
    h.check("P4 the Move dialog opened", move_panel() is not None)
    h.press(QtCore.Qt.Key_Escape)


p4_escape.wait_ms = 1200


def p4_check():
    part = x.comp("two_parts")
    h.check("P4 two_parts is inside Base", part is not None and x.parent_label(part) == "Base")
    for label in ("Plate", "Peg"):
        found = x.comp(label)
        h.check(
            "P4 %s is in two_parts" % label,
            found is not None and x.parent_label(found) == "two_parts",
            found and x.parent_label(found),
        )
    h.check(
        "P4 Esc left it where it came in (Base's origin)",
        part is not None and x.near3(tuple(part.Placement.Base), (0, 0, 0)),
        part and part.Placement.Base,
    )
    peg = x.body_of("Peg")
    h.check(
        "P4 the Peg stands on the plate, moved with the robot",
        peg is not None and x.near3(x.centre(peg), (120, 15, 12.5)),
        peg and x.centre(peg),
    )
    h.check("P4 no dialog left", move_panel() is None)


# -- P5 ----------------------------------------------------------------------------------------
def p5_activate_root():
    c.click_radio(App.ActiveDocument.Label)


p5_activate_root.wait_ms = 800


def p5_insert():
    i.use_file(s["robot"])
    i.menu("INSERT", "Insert STEP")


p5_insert.wait_ms = 2500


def p5_escape():
    h.press(QtCore.Qt.Key_Escape)


p5_escape.wait_ms = 1000


def p5_check():
    second = x.comp("robot (2)")
    h.check("P5 a second robot: robot (2)", second is not None, x.labels())
    h.check("P5 at the root", second is not None and x.parent_label(second) is None)
    wheels = [o for o in x.comps() if o.Label.startswith("Wheel:")]
    h.check("P5 each robot has its own wheel copy", len(wheels) == 2, [o.Label for o in wheels])


# -- P6 ----------------------------------------------------------------------------------------
def p6_cancelled():
    s["count"] = len(App.ActiveDocument.Objects)
    from sciforge import insert_ui

    insert_ui.FILE_PICKER = lambda kind: None
    i.menu("INSERT", "Insert STEP")


def p6_broken():
    h.check(
        "P6 a cancelled file dialog adds nothing",
        len(App.ActiveDocument.Objects) == s["count"] and move_panel() is None,
    )
    i.use_file(s["broken"])
    i.menu("INSERT", "Insert STEP")


p6_broken.wait_ms = 2000
p6_broken.known = True  # OpenCASCADE's own reader lines about the broken file


def p6_check():
    h.check("P6 the broken file adds nothing", len(App.ActiveDocument.Objects) == s["count"])
    msg = x.told()
    h.check("P6 SciForge says why", "could not be read" in msg or "Nothing" in msg, msg)
    h.check("P6 no Move dialog", move_panel() is None)
    i.no_file()
    h.new_errors()
    h.fit()
    h.shot("6-end")


def cleanup():
    for name in list(App.listDocuments()):
        try:
            Gui.getDocument(name).Modified = False
        except Exception:
            pass
        App.closeDocument(name)
    h.new_errors()


h.run(
    "exchange2_step_insert",
    [
        setup,
        p1_insert,
        p1_check,
        p2_type,
        p2_ok,
        p2_check,
        p3_undo_move,
        p3_undo_insert,
        p3_redo,
        p3_redo_move,
        p3_check,
        p4_activate_base,
        p4_insert,
        p4_escape,
        p4_check,
        p5_activate_root,
        p5_insert,
        p5_escape,
        p5_check,
        p6_cancelled,
        p6_broken,
        p6_check,
        cleanup,
    ],
)
