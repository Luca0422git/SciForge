# SPDX-License-Identifier: LGPL-2.1-or-later
"""Shared steps for the scenarios about ending an extrude on a clicked face
(scenarios/extrudeface_*.py): blocks made like Luca makes them (Create Sketch, a rectangle,
Finish Sketch, E, a height, OK), sketches on faces, and what the Extrude dialog shows. Every
step is real input; kept outside scenarios/ because every file there is run as a scenario.
"""

import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h

V = App.Vector


def panel():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    return p if p is not None and not p._closed else None


def near(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


def doc():
    return App.ActiveDocument


def bodies():
    d = doc()
    return [] if d is None else sorted(d.findObjects("PartDesign::Body"), key=lambda o: o.ID)


def total():
    """The volume of every shown body."""
    found = 0.0
    for body in bodies():
        try:
            if body.ViewObject.Visibility and not body.Shape.isNull():
                found += body.Shape.Volume
        except Exception:
            pass
    return found


def union_volume():
    """The volume of the shown bodies taken together (where they are in the design, inside
    their components), so a body merged into another or touching it counts once."""
    from sciforge import bodies as sb

    shapes = []
    for body in bodies():
        try:
            if body.ViewObject.Visibility and not body.Shape.isNull():
                shapes.append(sb.global_shape(body))
        except Exception:
            pass
    if not shapes:
        return 0.0
    if len(shapes) == 1:
        return shapes[0].Volume
    return shapes[0].fuse(shapes[1:]).Volume


def extrudes():
    from sciforge import extrude

    d = doc()
    return [] if d is None else [o for o in d.Objects if extrude.is_extrude(o)]


def last_extrude():
    found = extrudes()
    return found[-1] if found else None


def length(feature, prop="Length"):
    try:
        return float(getattr(feature, prop).Value)
    except Exception:
        return None


def named(name, fn):
    fn.__name__ = name
    return fn


def new_design(name):
    def new_design():
        Gui.activateWorkbench("SciForgeWorkbench")
        App.newDocument(name)
        h.fit()

    return named("new_design_" + name, new_design)


def xy_block(name, rect, height, expect_total, click=V(12, -8, 0)):
    """Steps: Create Sketch, the XY plane clicked at `click`, a rectangle rect (x0, y0, x1, y1),
    Finish Sketch, E, the height typed, OK; then the shown bodies' volume is checked."""

    def sketch():
        h.click_empty()
        h.fit()
        h.ribbon("Create Sketch")

    def plane():
        h.click(click)

    def draw():
        sk = h.in_sketch()
        h.check("%s: sketch open on XY" % name, sk is not None)
        if sk is not None:
            h.draw_rectangle(sk, *rect)

    def finish():
        h.ribbon("Finish Sketch")

    def extrude():
        h.click_empty()
        h.fit()
        h.press("e")

    def distance():
        p = panel()
        if h.check("%s: Extrude open" % name, p is not None):
            ui.type_into(p.distance.widget, "%g" % height)

    def ok():
        h.task_button("OK")

    def made():
        h.check("%s: volume" % name, near(total(), expect_total), (total(), expect_total))
        h.fit()

    steps = [sketch, plane, draw, finish, extrude, distance, ok, made]
    return [named("%s_%s" % (name, s.__name__), s) for s in steps]


def face_sketch(name, face_point, rect, keep=None):
    """Steps: Create Sketch on the face clicked at `face_point`, a rectangle over the global
    x0, y0, x1, y1 of `rect` (at the face's height), Finish Sketch. keep: a dict that gets
    the sketch under "sketch"."""

    def sketch():
        h.click_empty()
        h.fit()
        h.ribbon("Create Sketch")

    def face():
        h.click(face_point)

    def draw():
        sk = h.in_sketch()
        h.check("%s: sketch open on the face" % name, sk is not None)
        if sk is None:
            return
        z = face_point.z
        a = h.to_sketch(sk, V(rect[0], rect[1], z))
        b = h.to_sketch(sk, V(rect[2], rect[3], z))
        h.draw_rectangle(sk, min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]))
        if keep is not None:
            keep["sketch"] = sk

    def finish():
        h.ribbon("Finish Sketch")

    steps = [sketch, face, draw, finish]
    return [named("%s_%s" % (name, s.__name__), s) for s in steps]


def press_e(name):
    def press():
        h.click_empty()
        h.fit()
        h.press("e")

    return named(name, press)


def info_text():
    p = panel()
    return p.info.text() if p is not None else None


def message_text():
    p = panel()
    return p.message.text() if p is not None else None


def save_and_close(state, filename):
    def save():
        path = os.path.join(tempfile.mkdtemp(prefix="sciforge-extrudeface-"), filename)
        state["path"] = path
        doc().saveAs(path)
        App.closeDocument(doc().Name)

    return named("save_and_close", save)


def reopen(state):
    def reopen():
        App.openDocument(state["path"])
        h.fit()

    return named("reopen", reopen)


def timeline_extrude_title():
    """The timeline title of the newest extrude ("Extrude 4"), or None."""
    numbered = []
    for title in ui.timeline_titles():
        head, _, number = title.rpartition(" ")
        if head == "Extrude" and number.isdigit():
            numbered.append((int(number), title))
    return max(numbered)[1] if numbered else None


def escape():
    h.press(QtCore.Qt.Key_Escape)


def click_vertex(point):
    """Click a corner at a 3D point, aiming like a person does until the corner (not the
    edge or face next to it) lights up: the pixels around the point are tried, nearest
    first. Returns what was under the mouse."""
    from PySide6 import QtTest
    from PySide import QtWidgets

    h.uncover(point)
    widget = h.gl_widget()
    ratio = widget.devicePixelRatioF()
    centre = h.screen_point(point)
    best = None
    for radius in range(0, 7):
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                if best is not None or max(abs(dx), abs(dy)) != radius:
                    continue
                qx, qy = centre.x() + dx, centre.y() + dy
                info = h.view().getObjectInfo((qx * ratio, (widget.height() - qy) * ratio))
                if info and str(info.get("Component", "")).startswith("Vertex"):
                    best = QtCore.QPoint(qx, qy)
    pos = best or centre
    h.move(pos)
    QtTest.QTest.mouseClick(widget, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, pos)
    QtWidgets.QApplication.processEvents()
    h.state["last_click"] = "vertex click %s (found: %s); %s" % (
        (pos.x(), pos.y()),
        best is not None,
        h.click_context(pos),
    )
    return best is not None


def snap_marks():
    from sciforge import extrude_to_face

    try:
        return extrude_to_face.find(Gui.ActiveDocument.ActiveView)
    except Exception:
        return []
