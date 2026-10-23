# SPDX-License-Identifier: LGPL-2.1-or-later
"""Real-input helpers for the PLASTIC scenarios (scenarios/plastic_*.py). Not a scenario.

The parts are made in setup with SciForge's own Qt-free code (as other scenarios do); every
plastic action is real input: the ribbon's PLASTIC tab, its buttons and menus, clicks in the
3D view and the browser, typing in the dialogs, the timeline.

Hand-derived geometry (the default Boss of an M3 screw with the default rule, ABS 2 mm,
draft 1 deg, nominal radius 1 mm, clearance 0.1 mm), for an enclosure 60 x 40 x 20 shelled
2 mm (top open) and a lid 60 x 40 x 10 on top of it shelled 2 mm (bottom open), the sketch
on the parting plane z = 20:

  thread side (enclosure, Side 2): a frustum r 3.75 at the tip (z 19.95, clearance 0.05)
  widening by tan 1 deg down to the floor (z 2), a spigot r 2.9 (base r 2.9 + 0.9 tan 1)
  0.9 high on the tip, a 1 mm root fillet, minus the pilot hole r 1.2 from the spigot's top
  down to 1 mm above the outside (floor 1 mm);
  head side (lid, Side 1): a frustum r 4.5 from z 20.05 up to the lid's inside (z 28), a 1 mm
  root fillet, minus the alignment recess r 3 (drafted 1 deg) 1 mm deep, the clearance hole
  r 1.7 and the counterbore r 3.25 from 2 mm above the tip to the outside.
  A concave fillet ring of radius R around a cylinder of radius r adds
  (1 - pi/4) R^2 * 2 pi (r + R (10 - 3 pi) / (12 - 3 pi)) (Pappus).
"""

import math

import FreeCAD as App
import FreeCADGui as Gui
import Part
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import insert_steps as ins
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import timeline_input as tl
from SciForgeTests.gui import widget_input as w

V = App.Vector
TAN1 = math.tan(math.radians(1.0))


def frustum(h_, r1, r2):
    return math.pi * h_ / 3.0 * (r1 * r1 + r1 * r2 + r2 * r2)


def fillet_ring(r, R):
    return (
        (1 - math.pi / 4) * R * R * 2 * math.pi * (r + R * (10 - 3 * math.pi) / (12 - 3 * math.pi))
    )


def thread_side_boss():
    """Volume one default Side 2 boss adds to the enclosure."""
    shank = frustum(17.95, 3.75, 3.75 + 17.95 * TAN1)
    spigot = frustum(0.9, 2.9 + 0.9 * TAN1, 2.9)
    root = fillet_ring(3.75 + 17.95 * TAN1, 1.0)
    hole = math.pi * 1.2**2 * (0.9 + 17.95 + 1.0)
    return shank + spigot + root - hole


def head_side_boss():
    """Volume one default Side 1 boss adds to the lid."""
    r2 = 4.5 + 7.95 * TAN1
    shank = frustum(7.95, 4.5, r2)
    root = fillet_ring(r2, 1.0)
    recess = frustum(1.0, 3.0 - 0.02 * TAN1, 3.0 - 1.02 * TAN1)
    hole = math.pi * 1.7**2 * 1.0
    cbore = math.pi * 3.25**2 * 7.95
    return shank + root - recess - hole - cbore


def near(a, b, tol):
    return abs(a - b) <= tol


# -- the parts -------------------------------------------------------------------------------------
def rect_sketch(body, z, x0, y0, x1, y1, name="Sketch"):
    sk = body.newObject("Sketcher::SketchObject", name)
    sk.MapMode = "Deactivated"
    sk.Placement = App.Placement(V(0, 0, z), App.Rotation())
    pts = [V(x0, y0, 0), V(x1, y0, 0), V(x1, y1, 0), V(x0, y1, 0)]
    for i in range(4):
        sk.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % 4]))
    import Sketcher

    for i in range(4):
        sk.addConstraint(Sketcher.Constraint("Coincident", i, 2, (i + 1) % 4, 1))
    return sk


def face_named(feature, normal, z):
    """The name of the flat face of `feature` lying in the plane at height z (the largest
    one; `normal` is only a hint kept for readability)."""
    best = None
    for i, face in enumerate(feature.Shape.Faces, start=1):
        box = face.BoundBox
        if abs(box.ZMin - z) < 1e-6 and abs(box.ZMax - z) < 1e-6:
            if best is None or face.Area > best[0]:
                best = (face.Area, "Face%d" % i)
    return best[1] if best else None


def box_body(doc, label, z, height, open_side, wall=2.0, shell=True, component=None):
    """A 60 x 40 body from z, `height` high, shelled `wall` with its top ("top") or bottom
    ("bottom") open."""
    from sciforge import bodies, components, extrude, shelling

    if component is None:
        body = bodies.new_body(doc, label)
    else:
        body = components.new_body_in(doc, component, label)
    sk = rect_sketch(body, z, 0, 0, 60, 40, label + "Sketch")
    doc.recompute()
    ext = extrude.make(body, sk, {"distance": height})
    doc.recompute()
    if shell:
        if open_side == "top":
            name = face_named(ext, V(0, 0, 1), z + height)
        else:
            name = face_named(ext, V(0, 0, -1), z)
        shelling.make(body, ext, [name], {"inside": wall})
        doc.recompute()
    return body


def enclosure(name, lid=True, points=((10, 10), (50, 30))):
    """New design: the enclosure (Bottom) and its lid (Lid), shelled 2 mm, and a sketch
    "Boss Points" on the parting plane z = 20 with the boss points (in Bottom)."""
    Gui.activateWorkbench("SciForgeWorkbench")
    doc = App.newDocument(name)
    bottom = box_body(doc, "Bottom", 0, 20, "top")
    top = box_body(doc, "Lid", 20, 10, "bottom") if lid else None
    sk = bottom.newObject("Sketcher::SketchObject", "BossPoints")
    sk.Label = "Boss Points"
    sk.MapMode = "Deactivated"
    sk.Placement = App.Placement(V(0, 0, 20), App.Rotation())
    for x, y in points:
        sk.addGeometry(Part.Point(V(x, y, 0)))
    doc.recompute()
    from sciforge import bodies

    bodies.set_active_body(bottom)
    h.fit()
    return doc, bottom, top, sk


def volume(body):
    try:
        return body.Shape.Volume if body is not None and body.Shape.Solids else 0.0
    except Exception:
        return 0.0


# -- the ribbon -----------------------------------------------------------------------------------
def plastic_tab():
    return ins.ribbon_tab("plastic")


def menu(group, label):
    return si.menu_item(group, label)


def settle(panel, timeout_ms=8000):
    import time

    end = time.time() + timeout_ms / 1000.0
    while time.time() < end:
        QtTest.QTest.qWait(50)
        if panel is None or panel._closed:
            break
        timer = getattr(panel, "_timer", None)
        busy = (
            (timer is not None and timer.isActive())
            or getattr(panel, "_pending", False)
            or getattr(App.ActiveDocument, "Recomputing", False)
        )
        if not busy:
            break
    QtTest.QTest.qWait(80)


def boss_panel():
    from sciforge import plastic_boss_ui

    p = plastic_boss_ui.BossPanel.last
    return p if p is not None and not p._closed else None


def rest_panel():
    from sciforge import plastic_rest_ui

    p = plastic_rest_ui.RestPanel.last
    return p if p is not None and not p._closed else None


def assign_panel():
    from sciforge import plastic_rules_ui

    p = plastic_rules_ui.AssignPanel.last
    return p if p is not None and not p._closed else None


def manage_panel():
    from sciforge import plastic_rules_ui

    p = plastic_rules_ui.ManagePanel.last
    return p if p is not None and not p._closed else None


def type_into(widget, text):
    ui.type_into(widget, text)


def click(widget):
    w.click(widget)


def tab_of(panel, title):
    """Click the dialog tab whose text starts with `title`."""
    tabs = panel.tabs
    bar = tabs.tabBar()
    for i in range(tabs.count()):
        if tabs.tabText(i).startswith(title):
            w.click(bar, bar.tabRect(i).center())
            return True
    h.check("dialog tab %s" % title, False)
    return False


def check_box(box):
    """Click a check box like a person (on its box)."""
    QtTest.QTest.mouseClick(box, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, QtCore.QPoint(6, 6))
    QtWidgets.QApplication.processEvents()


def choose(combo, text):
    return ui.choose(combo, text)


def click_tree_row(tree, text, parent_text=None):
    """Click the row `text` (under the top row `parent_text`) of a dialog's tree."""
    for i in range(tree.topLevelItemCount()):
        top = tree.topLevelItem(i)
        if parent_text is not None and top.text(0) != parent_text:
            continue
        for j in range(top.childCount()):
            row = top.child(j)
            if row.text(0) == text:
                tree.scrollToItem(row)
                QtWidgets.QApplication.processEvents()
                rect = tree.visualItemRect(row)
                w.click(tree.viewport(), rect.center())
                return True
    h.check("tree row %s / %s" % (parent_text, text), False)
    return False


def timeline_titles():
    return ui.timeline_titles()


def double_click_timeline(title):
    return tl.double_click(title)


def undo():
    tl.undo() if hasattr(tl, "undo") else h.press("z", QtCore.Qt.ControlModifier)


def redo():
    tl.redo() if hasattr(tl, "redo") else h.press("y", QtCore.Qt.ControlModifier)


def click_row(label):
    return tl.click_row(label)


def esc():
    h.press(QtCore.Qt.Key_Escape)


def ok():
    return h.task_button("OK")


def cancel():
    return h.task_button("Cancel")


def clear_library_prefs():
    """The user's own plastic library and default rule (kept in the settings) back to
    none, so scenarios do not leave them for the next one."""
    try:
        from sciforge import plastic

        grp = App.ParamGet(plastic.PREF)
        grp.SetString("Library", "")
        grp.SetString("Default", "")
    except Exception:
        pass


def _band(a, r):
    """Integral of sqrt(r^2 - y^2) for y in [-a, a] (a cross-section of a cylinder)."""
    return a * math.sqrt(r * r - a * a) + r * r * math.asin(a / r)


def rest_volume(t=2.0):
    """What a rest adds on the half pipe R 20 / R 18 (axis along X at z 0) for the 20 x 12
    profile at z 22 (x 20..40, |y| <= 6), wall t <= 2, no draft: the plate (z 22-t..22),
    the ring of walls (between the profile and its offset by t) filling the air down to the
    outer skin, minus the old wall inside the ring (outer to inner skin), so the pedestal is
    hollow and open to the inside. Only valid while the plate stays above the crown
    (22 - t >= 20)."""
    a_out, a_in = 6.0, 6.0 - t
    l_out, l_in = 20.0, 20.0 - 2 * t
    plate = l_out * 2 * a_out * t
    air_out = l_out * (2 * a_out * (22 - t) - _band(a_out, 20))
    air_in = l_in * (2 * a_in * (22 - t) - _band(a_in, 20))
    old_wall = l_in * (_band(a_in, 20) - _band(a_in, 18))
    return plate + air_out - air_in - old_wall
