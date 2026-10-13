# SPDX-License-Identifier: LGPL-2.1-or-later
"""Shared steps and helpers for the joint scenarios (scenarios/joints_*.py). Everything acts
like a person: the J key, menus, clicks on faces, typing into fields, the timeline and the
browser. Kept outside scenarios/ because every file there is run as a scenario.

The usual design: Body1 = 0..40 x 0..30 x 10 (a plate), Body2 = 50..70 x 0..10 x 20 (a block
standing beside it, made with Extrude > New Body). Body2's top face centre is (60, 5, 20),
Body1's (20, 15, 10).
"""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtWidgets

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import harness as h

V = App.Vector
PLATE = (0, 0, 40, 30)
PLATE_HEIGHT = 10
BLOCK = (50, 0, 70, 10)
BLOCK_HEIGHT = 20


def near(a, c, tol=1e-6):
    return abs(a - c) <= tol


def box_is(name, box, expect, tol=1e-6):
    """Check a BoundBox against (xmin, ymin, zmin, xmax, ymax, zmax)."""
    got = [box.XMin, box.YMin, box.ZMin, box.XMax, box.YMax, box.ZMax]
    ok = all(abs(a - c) <= tol for a, c in zip(got, expect))
    return h.check(name, ok, ([round(g, 4) for g in got], expect))


def two_boxes(prefix=""):
    """Steps that make the plate and the block (Create Sketch, rectangle, E...)."""
    # the XY square is clicked just in front of the plate, where no body covers it
    steps = s.box_steps(prefix + "plate", PLATE, PLATE_HEIGHT, V(12, -8, 0))
    steps += s.box_steps(prefix + "block", BLOCK, BLOCK_HEIGHT, V(12, -8, 0), new_body=True)
    return steps


def plate():
    return s.bodies()[0]


def block():
    return s.bodies()[1]


def joints_module():
    from sciforge import joints

    return joints


def joint_list():
    return joints_module().joints(App.ActiveDocument)


def panel():
    return s.panel()


def joint_panel():
    from sciforge import joints_ui

    p = joints_ui.JointPanel.last
    return None if p is None or p._closed else p


def hover(point):
    """Move the mouse onto a 3D point and give the snap hover time to look."""
    h.move(h.screen_point(point))
    QtWidgets.QApplication.processEvents()
    for _ in range(6):
        from PySide6 import QtTest

        QtTest.QTest.qWait(40)
        QtWidgets.QApplication.processEvents()


def snap_kinds(p):
    hov = getattr(p, "hover", None)
    if hov is None:
        return []
    return sorted({c["kind"] for c in hov.candidates})


def hot_kind(p):
    hov = getattr(p, "hover", None)
    return hov.hot["kind"] if hov is not None and hov.hot is not None else None


def choose_type(p, label):
    return b.choose(p.type_box, label)


def ok():
    h.task_button("OK")


def cancel():
    h.task_button("Cancel")


def press_j():
    h.click_empty()
    h.fit()
    h.press("j")


def menu(label):
    return s.menu("ASSEMBLE", label)


def wait(ms):
    from PySide6 import QtTest

    QtTest.QTest.qWait(ms)
    QtWidgets.QApplication.processEvents()


def row_labels():
    from SciForgeTests.gui import timeline_input as t

    return t.labels()


def joint_value(joint):
    return joints_module().value(joint)


def no_dialog(where):
    h.check("no dialog after %s" % where, not Gui.Control.activeDialog(), where)


def body_placement(body):
    p = body.Placement
    return (round(p.Base.x, 4), round(p.Base.y, 4), round(p.Base.z, 4))
