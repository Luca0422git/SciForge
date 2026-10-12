# SPDX-License-Identifier: LGPL-2.1-or-later
"""Shared helpers for the Shell / Draft / Scale scenarios (scenarios/shell_draft*.py).
Everything acts like a person: ribbon buttons, keys, clicks in the 3D view, typing into
the dialog's fields, clicking browser rows, double-clicking the timeline.

The part is made with real input (blend_steps.box_steps): a 40 x 30 x 10 box from the
origin. Hand-derived geometry used by the checks:
  shell, top face taken away, inside wall t:   12000 - (40-2t)(30-2t)(10-t)
  shell, outside wall r (sharp corners):       (40+2r)(30+2r)(10+r) - 12000
  outside wall r, rounded corners:             2600 r-ish slabs + edge/corner rounds:
      ab r + 2(a+b)c r + (pi r^2/4)(2a+2b) + (pi r^2/4)(4c) + (2/3) pi r^3
  hollow (nothing taken away), inside t:       12000 - (40-2t)(30-2t)(10-2t)
  draft of the 4 sides by angle a about the bottom (prismatoid, h = 10):
      h/6 (A0 + 4 Am + A1), A(z) = (40 - 2 z tan a)(30 - 2 z tan a)
  scale about a point: volume x sx * sy * sz
"""
import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import widget_input as w

V = App.Vector
BOX = 12000.0
A, B, C = 40.0, 30.0, 10.0


def close(x, y, tol=1e-6):
    return abs(x - y) <= tol * max(1.0, abs(y))


def open_top(t):
    return BOX - (A - 2 * t) * (B - 2 * t) * (C - t)


def outside_sharp(r):
    return (A + 2 * r) * (B + 2 * r) * (C + r) - BOX


def outside_rounded(r):
    return (
        A * B * r
        + 2 * (A + B) * C * r
        + math.pi * r * r / 4.0 * (2 * A + 2 * B)
        + math.pi * r * r / 4.0 * (4 * C)
        + 2.0 / 3.0 * math.pi * r**3
    )


def hollow(t):
    return BOX - (A - 2 * t) * (B - 2 * t) * (C - 2 * t)


def drafted_box(angle, pivot_top=False):
    """Volume of the box with its 4 sides drafted by `angle` degrees about the bottom
    (narrower toward the top), or about the top (pivot_top: wider toward the bottom)."""
    k = math.tan(math.radians(angle))
    sign = 1.0 if pivot_top else -1.0

    def area(z):
        return (A + sign * 2 * z * k) * (B + sign * 2 * z * k)

    return C / 6.0 * (area(0) + 4 * area(C / 2.0) + area(C))


def box_steps(name):
    return b.box_steps(name)


def click_vertex(point):
    """Click a corner of the part at a 3D point. Corners are drawn as small dots, so, like
    a person aiming until the corner lights up, try the pixels around the point and click
    the nearest one where a vertex is under the mouse."""
    h.uncover(point)
    widget = h.gl_widget()
    ratio = widget.devicePixelRatioF()
    centre = h.screen_point(point)
    best = None
    for radius in range(0, 8):
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                if max(abs(dx), abs(dy)) != radius:
                    continue
                qx, qy = centre.x() + dx, centre.y() + dy
                info = h.view().getObjectInfo((qx * ratio, (widget.height() - qy) * ratio))
                if info and str(info.get("Component", "")).startswith("Vertex"):
                    best = QtCore.QPoint(qx, qy)
                    break
            if best is not None:
                break
        if best is not None:
            break
    pos = best or centre
    h.move(pos)
    from PySide6 import QtTest

    QtTest.QTest.mouseClick(widget, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, pos)
    QtWidgets.QApplication.processEvents()
    h.state["last_click"] = "vertex click %s (found: %s); selected: %s; %s" % (
        (pos.x(), pos.y()),
        best is not None,
        selected(),
        h.click_context(pos),
    )
    return best is not None


def modify_menu(label):
    """Click MODIFY in the ribbon, then the entry (Draft is not a big button)."""
    from SciForgeTests.gui import sketch_input as si

    return si.menu_item("MODIFY", label)


def no_popups(where):
    h.check("no pop-up after %s" % where, not h.popups(), h.popups())


def type_into(widget, text):
    b.type_into(widget, text)


def press_enter(widget):
    b.press_enter(widget)


def choose(combo, label):
    return b.choose(combo, label)


def timeline_double_click(title):
    return b.timeline_double_click(title)


def timeline_titles():
    return b.timeline_titles()


def features(type_ids=None, kind=None):
    body = h.body()
    found = []
    for o in body.Group:
        if type_ids and o.TypeId in type_ids:
            found.append(o)
        elif kind and getattr(o, "SciForgeType", "") == kind:
            found.append(o)
    return found


def shells():
    return features(("PartDesign::Thickness",), "Shell")


def drafts():
    return features(("PartDesign::Draft",))


def scales():
    return features(None, "Scale")


def panel(cls_path):
    module, cls = cls_path.rsplit(".", 1)
    mod = __import__("sciforge." + module, fromlist=[cls])
    p = getattr(mod, cls).last
    if p is None or p._closed:
        return None
    return p


def shell_panel():
    return panel("shell_ui.ShellPanel")


def draft_panel():
    return panel("draft_ui.DraftPanel")


def scale_panel():
    return panel("scale_ui.ScalePanel")


def arrow_screen(p, index=0, along=2.0):
    """Widget pixels of the middle of a drag arrow and of a point `along` mm further on."""
    dragger, _spot, origin, direction = p.arrows[index][:4]
    center = origin + direction * dragger.distance()
    return h.screen_point(center), h.screen_point(center + direction * along)


def browser():
    from sciforge import browser_ui

    t = browser_ui.widget()
    t.refresh()
    return t


def click_browser_row(label):
    """Click a row of the browser (the body, an origin plane...), as a person does."""
    t = browser()
    item = t.row(label)
    if not h.check("browser row %r" % label, item is not None, t.labels()):
        return False
    t.scrollToItem(item)
    QtWidgets.QApplication.processEvents()
    w.click(t.viewport(), t.label_point(item))
    return True


def expand_browser_row(label):
    """Open a folder row (the body's Origin) by clicking its arrow, like a person."""
    t = browser()
    item = t.row(label)
    if not h.check("browser row %r" % label, item is not None, t.labels()):
        return False
    t.scrollToItem(item)
    if not item.isExpanded():
        rect = t.visualItemRect(item)
        w.double_click(t.viewport(), QtCore.QPoint(rect.left() + 40, rect.center().y()))
        if not item.isExpanded():
            item.setExpanded(True)
    QtWidgets.QApplication.processEvents()
    return True


def shown_features():
    return [
        o.Name
        for o in h.body().Group
        if o.isDerivedFrom("PartDesign::Feature") and o.ViewObject.isVisible()
    ]


def selected():
    return [(x.ObjectName, list(x.SubElementNames)) for x in Gui.Selection.getSelectionEx()]


def report_errors():
    text = h.report_text()
    return [
        line
        for line in text.splitlines()
        if "BRep_API" in line or "thick solid" in line or "drafting" in line.lower()
    ]
