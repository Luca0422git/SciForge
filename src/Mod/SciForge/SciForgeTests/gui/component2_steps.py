# SPDX-License-Identifier: LGPL-2.1-or-later
"""Real-input helpers for the components-2 scenarios (scenarios/components2_*.py): moving,
copying and patterning whole components. Not a scenario (it lives outside scenarios/)."""

import FreeCAD as App
import Part
from PySide import QtCore, QtWidgets

from SciForgeTests.gui import harness as h

V = App.Vector


def doc():
    return App.ActiveDocument


def part(label):
    from sciforge import components

    for obj in components.list_components(doc()):
        if obj.Label == label:
            return obj
    return None


def labels():
    from sciforge import components

    return [p.Label for p in components.list_components(doc())]


def shape(obj):
    """The solids of a component (its bodies, nested ones too) or a body, design
    coordinates."""
    from sciforge import bodies, components

    if obj is None:
        return Part.Shape()
    found = (
        components.bodies_in(doc(), obj, recursive=True) if components.is_component(obj) else [obj]
    )
    shapes = [bodies.global_shape(b) for b in found if bodies.has_solid(b)]
    return Part.makeCompound(shapes) if shapes else Part.Shape()


def volume(obj):
    s = shape(obj)
    return 0.0 if s.isNull() else s.Volume


def box_of(obj):
    s = shape(obj)
    if s.isNull():
        return None
    b = s.BoundBox
    return [b.XMin, b.YMin, b.ZMin, b.XMax, b.YMax, b.ZMax]


def box_is(name, obj, expect, tol=1e-5):
    got = box_of(obj)
    ok = got is not None and all(abs(a - c) <= tol for a, c in zip(got, expect))
    return h.check(name, ok, (got, expect))


def close(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


def at(obj):
    return obj.Placement.Base if obj is not None else None


def placed(name, obj, expect, tol=1e-6):
    got = at(obj)
    return h.check(name, got is not None and (got - expect).Length <= tol, (got, expect))


def panel():
    from sciforge import taskui

    return taskui.current()


def component_panel():
    from sciforge import component_move_ui

    p = panel()
    return p if isinstance(p, component_move_ui.ComponentMovePanel) else None


def moves():
    from sciforge import component_move

    return component_move.steps(doc())


def field(p, key):
    return {
        "dx": p.distance_fields[0],
        "dy": p.distance_fields[1],
        "dz": p.distance_fields[2],
        "rx": p.angle_fields[0],
        "ry": p.angle_fields[1],
        "rz": p.angle_fields[2],
        "angle": p.angle,
        "px": p.pivot_fields[0],
        "py": p.pivot_fields[1],
        "pz": p.pivot_fields[2],
    }[key].widget


def type_value(p, key, text):
    from SciForgeTests.gui import bodies_steps as s

    s.type_value(field(p, key), text)


def choose(combo, text, closes=False):
    """Pick `text` in a drop-down. ``closes``: the choice replaces the dialog (Move Object),
    so the drop-down is gone once the choice is made."""
    from SciForgeTests.gui import dialog_input

    try:
        ok = dialog_input.choose(combo, text)
    except RuntimeError:
        ok = closes  # the dialog was replaced while the choice was confirmed
    return h.check("drop-down offers %s" % text, ok)


def click_button(button):
    from PySide6 import QtTest

    QtTest.QTest.mouseClick(button, QtCore.Qt.LeftButton)
    QtWidgets.QApplication.processEvents()


def toggle(box):
    from SciForgeTests.gui import bodies_steps as s

    s.toggle(box)


def drag_arrow(index, along):
    """Drag arrow `index` of the move manipulator by `along` mm, on its shaft."""
    p = panel()
    triad = getattr(p, "triad", None)
    if not h.check("manipulator shown", triad is not None):
        return
    axis = [V(1, 0, 0), V(0, 1, 0), V(0, 0, 1)][index]
    start = triad.center + axis * (0.75 * triad.size)
    h.drag(h.screen_point(start), h.screen_point(start + axis * along))


def timeline_title(obj):
    from SciForgeTests.gui import bodies_steps as s

    return s.timeline_title_of(obj)


def browser_refresh():
    from sciforge import browser_ui

    tree = browser_ui.widget()
    if tree is not None:
        tree.refresh(force=True)
    QtWidgets.QApplication.processEvents()


def browser_labels():
    """Every row label of the browser, from the top."""
    from SciForgeTests.gui import timeline_input as t

    browser_refresh()
    return t.tree().labels()
