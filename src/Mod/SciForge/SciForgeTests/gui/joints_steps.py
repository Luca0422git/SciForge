# SPDX-License-Identifier: LGPL-2.1-or-later
"""Shared steps and helpers for the joint scenarios (scenarios/joints_*.py). Everything acts
like a person: the J key, menus, clicks on faces, typing into fields, the timeline and the
browser. Kept outside scenarios/ because every file there is run as a scenario.

The usual design: Body1 = 0..40 x 0..30 x 10 (a plate), Body2 = 50..70 x 0..10 x 20 (a block
standing beside it, made with Extrude > New Body). Body2's top face centre is (60, 5, 20),
Body1's (20, 15, 10).
"""

import math
import time

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtWidgets

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import harness as h

V = App.Vector
Z = App.Vector(0, 0, 1)
X = App.Vector(1, 0, 0)
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


# -- the usual joint: the block's top onto the plate's top --------------------------------
BLOCK_TOP = V(58, 6, 20)  # a click near the block's top centre (60, 5, 20)
PLATE_TOP = V(19, 14, 10)  # a click near the plate's top centre (20, 15, 10)
HOME = [50, 0, 0, 70, 10, 20]  # the block where it was made
ON_PLATE = [10, 10, 10, 30, 20, 30]  # upside down, centred on the plate's top


def click_tab(p, label):
    """Click a tab of the dialog (Position / Motion) on its title."""
    from SciForgeTests.gui import widget_input as w

    bar = p.tabs.tabBar()
    for i in range(bar.count()):
        if bar.tabText(i) == label:
            w.click(bar, bar.tabRect(i).center())
            return h.check(
                "tab %s shown" % label, p.tabs.currentIndex() == i, p.tabs.currentIndex()
            )
    return h.check("a tab %r" % label, False)


def frames(joint):
    """(joint origin 1, joint origin 2) as global placements (the stored ones: they coincide
    when the joint is at 0)."""
    jm = joints_module()
    return jm.jcs_global(joint, 0), jm.jcs_global(joint, 1)


def sample(joint, part, seconds=2.0):
    """Watch a moving joint (an animation playing) for a while: one record per moment."""
    jm = joints_module()
    out = []
    end = time.time() + seconds
    while time.time() < end:
        wait(40)
        try:
            j1, j2 = frames(joint)
            angle, slide = jm.value(joint)
            out.append(
                {
                    "angle": angle,
                    "slide": slide,
                    "j1": j1,
                    "j2": j2,
                    "plc": App.Placement(part.Placement),
                    "box": part.Shape.BoundBox,
                }
            )
        except Exception:
            pass
    return out


def spread(values):
    values = list(values)
    return (max(values) - min(values)) if values else 0.0


def tilt(a, b):
    """Angle in degrees between two directions."""
    c = max(-1.0, min(1.0, App.Vector(a).normalize().dot(App.Vector(b).normalize())))
    return math.degrees(math.acos(c))


def offset_of(rec):
    """Joint origin 1 - joint origin 2 (global vector)."""
    return rec["j1"].Base - rec["j2"].Base


def z_of(plc):
    return plc.Rotation.multVec(Z)


def x_of(plc):
    return plc.Rotation.multVec(X)


def along(vec, axis, tol=1e-5):
    """True when vec has no part across `axis` (it lies on the line)."""
    a = App.Vector(axis).normalize()
    return (vec - a * vec.dot(a)).Length <= tol


def pick_pair(prefix="pair", wait_after=900):
    """Steps: J, click the block's top, click the plate's top (the block lands on it)."""

    def press():
        press_j()

    def first():
        h.click(BLOCK_TOP)

    def second():
        h.click(PLATE_TOP)

    second.wait_ms = wait_after
    steps = [press, first, second]
    for step in steps:
        step.__name__ = "%s_%s" % (prefix, step.__name__)
    return steps


def block_box(name, expect, tol=1e-4):
    return box_is(name, block().Shape.BoundBox, expect, tol)


def browser_menu(label, entry):
    from SciForgeTests.gui import timeline_input as t

    return t.row_menu(label, entry)


def timeline_menu(title, entry):
    from SciForgeTests.gui import timeline_input as t

    return t.menu(title, entry)
