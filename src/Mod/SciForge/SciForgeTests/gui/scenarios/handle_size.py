# SPDX-License-Identifier: LGPL-2.1-or-later
"""Drag handles keep one size on the screen (Luca, 2026-10-18: "SciForge has some janky
looking arrows and sometimes they are oversized and sometimes they are tiny. It should be
a consistant size. same thing for the angle dragger"). Only real input.

A small block (4 x 3 x 1) and a big one (400 x 300 x 100), each in its own design. On each:
press E, click the top face, Distance 2 (the small) / 50 (the big): Extrude's blue arrow and
its taper disc show. Measured after Fit, zoomed out and zoomed in:

  - the arrow's on-screen length (its foot and tip projected to pixels) is
    handle_look_core.ARROW_PX as the iso view shows a vertical line, within 2 px, and the
    same everywhere within 2 px;
  - the blue pixels along the drawn arrow (a screen grab) run the same length everywhere
    within 3 px: what is drawn keeps its size, not only the maths;
  - the white of the taper disc across its middle is its 2 x DISC_RADIUS_PX within 3 px;
  - the scale Coin last drew the handle with (SoShapeScale) is the scale the handle grabs
    and places its value box with, within 2 %.

Esc, then M and a click on the block: Move's manipulator, measured the same way (its X arrow
from the centre to the tip, TRIAD_PX as the iso view shows it). Screenshots: each Extrude
and Move view, and a close-up (4 x) of the arrow and the taper disc.
"""
import math
import os

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets

from SciForgeTests.gui import arrow_input as a
from SciForgeTests.gui import harness as h

V = App.Vector
s = {"arrow": {}, "blue": {}, "disc": {}, "triad": {}, "scale": {}}


def core():
    from sciforge import handle_look_core

    return handle_look_core


def extrude_panel():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    return None if p is None or p._closed else p


def move_panel():
    from sciforge import taskui

    p = taskui.current()
    return p if p is not None and getattr(p, "title", "") == "Move/Copy" else None


def grab():
    screen = QtGui.QGuiApplication.primaryScreen()
    image = screen.grabWindow(0).toImage()
    return image, image.width() / float(max(screen.geometry().width(), 1))


def pixel_at(image, ratio, pos):
    gl = h.gl_widget()
    at = gl.mapToGlobal(QtCore.QPoint(int(round(pos[0])), int(round(pos[1]))))
    x = min(max(int(at.x() * ratio), 0), image.width() - 1)
    y = min(max(int(at.y() * ratio), 0), image.height() - 1)
    c = image.pixelColor(x, y)
    return c.red(), c.green(), c.blue()


def blue(rgb):
    r, g, b = rgb
    return b > r + 60 and b > g + 15


def white(rgb):
    return min(rgb) >= 225


def blue_run(image, ratio, foot, tip):
    """Pixels from the first to the last strongly blue one on the line from 3 px before the
    arrow's foot to 4 px past its tip (the drawn arrow)."""
    fx, fy, tx, ty = foot.x(), foot.y(), tip.x(), tip.y()
    length = math.hypot(tx - fx, ty - fy)
    if length < 1:
        return 0.0
    ux, uy = (tx - fx) / length, (ty - fy) / length
    found = []
    t = -3.0
    while t <= length + 4.0:
        if blue(pixel_at(image, ratio, (fx + ux * t, fy + uy * t))):
            found.append(t)
        t += 0.5
    return (found[-1] - found[0]) if found else 0.0


def white_run(image, ratio, centre):
    """Pixels from the first to the last white one across the disc's middle (left to right,
    14 px each side: the value box beside it starts further out)."""
    found = [
        dx
        for dx in [x * 0.5 for x in range(-28, 29)]
        if white(pixel_at(image, ratio, (centre.x() + dx, centre.y())))
    ]
    return (found[-1] - found[0]) if found else 0.0


def vertical_factor():
    """How long a vertical line shows on the screen for its length (the iso view tilts it)."""
    look = V(h.view().getViewDirection())
    look.normalize()
    return math.sqrt(max(0.0, 1.0 - look.z * look.z))


def axis_factor(axis):
    look = V(h.view().getViewDirection())
    look.normalize()
    d = look.dot(axis)
    return math.sqrt(max(0.0, 1.0 - d * d))


def closeup(label, points):
    """A 4 x close-up of the screen round `points` (widget pixels), saved beside the shots."""
    try:
        gl = h.gl_widget()
        xs = [p.x() for p in points]
        ys = [p.y() for p in points]
        left, top = max(min(xs) - 45, 0), max(min(ys) - 45, 0)
        right, bottom = min(max(xs) + 45, gl.width()), min(max(ys) + 45, gl.height())
        corner = gl.mapToGlobal(QtCore.QPoint(int(left), int(top)))
        image, ratio = grab()
        crop = image.copy(
            int(corner.x() * ratio),
            int(corner.y() * ratio),
            int((right - left) * ratio),
            int((bottom - top) * ratio),
        )
        crop = crop.scaled(crop.width() * 4, crop.height() * 4)
        path = os.path.join(h.OUT_DIR, "handle_size-closeup-%s.png" % label)
        crop.save(path)
        print("[SciForge] handle_size: close-up %s" % path, flush=True)
    except Exception as exc:
        print("[SciForge] handle_size: no close-up: %s" % exc, flush=True)


def park_mouse():
    """The mouse to a free corner of the view: a handle under it is lit (lighter colours)."""
    h.move(QtCore.QPoint(40, h.gl_widget().height() - 40))


def uncover_handles():
    """Pan, as a person would, when a handle went under the floating dialog."""
    p = extrude_panel()
    if p is None:
        return
    taper = p.draggers.get("taper")
    for point in [p.dragger.anchor(), p.dragger.tip()] + (
        [taper.point_at(taper.angle())] if taper is not None else []
    ):
        h.uncover(point)


def zoom(factor):
    """Zoom the view about its middle (`factor` > 1: further out)."""
    park_mouse()
    camera = h.view().getCameraNode()
    try:
        camera.height.setValue(camera.height.getValue() * factor)
    except AttributeError:  # a perspective camera: step back along the view
        look = V(h.view().getViewDirection())
        position = V(*camera.position.getValue().getValue())
        focal = camera.focalDistance.getValue()
        target = position + look * focal
        moved = target - look * (focal * factor)
        camera.position.setValue(moved.x, moved.y, moved.z)
        camera.focalDistance.setValue(focal * factor)
    QtWidgets.QApplication.processEvents()
    uncover_handles()


def make_block(name, x, y, z):
    from sciforge import commands, extrude, sketch_ui

    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument(name)
    body = commands.ensure_body()
    sk = sketch_ui.create_sketch(body, (sketch_ui.origin_planes(body)["XY_Plane"], ""))
    h.draw_rectangle(sk, 0, 0, x, y)
    extrude.make(body, sk, {"distance": z})
    App.ActiveDocument.recompute()
    Gui.Selection.clearSelection()
    h.fit()


# -- Extrude ------------------------------------------------------------------------------------
def measure_extrude(label):
    p = extrude_panel()
    if not h.check("%s: Extrude open with its arrow" % label, p is not None and p.dragger):
        return
    arrow = p.dragger
    taper = p.draggers.get("taper")
    h.check("%s: and its taper disc" % label, taper is not None)
    length = a.screen_length(arrow)
    s["arrow"][label] = length
    want = core().ARROW_PX * vertical_factor()
    h.check(
        "%s: the arrow is ARROW_PX on the screen (%.1f px as the view shows it)" % (label, want),
        abs(length - want) <= 2.0,
        round(length, 2),
    )
    scale = a.drawn_scale(arrow)
    h.check(
        "%s: the arrow is drawn at the scale it is grabbed with" % label,
        scale is not None and scale[0] and abs(scale[0] - scale[1]) <= 0.02 * scale[1],
        scale,
    )
    image, ratio = grab()
    foot, tip = (h.screen_point(q) for q in a.arrow_ends(arrow))
    s["blue"][label] = blue_run(image, ratio, foot, tip)
    h.check(
        "%s: the drawn (blue) arrow runs most of that length" % label,
        0.75 * want <= s["blue"][label] <= want + 4.0,
        (s["blue"][label], round(want, 1)),
    )
    if taper is not None:
        centre3 = taper.point_at(taper.angle())
        centre = h.screen_point(centre3)
        s["disc"][label] = white_run(image, ratio, centre)
        h.check(
            "%s: the taper disc is 2 x DISC_RADIUS_PX across on the screen" % label,
            abs(s["disc"][label] - 2.0 * core().DISC_RADIUS_PX) <= 3.0,
            s["disc"][label],
        )
        scale = a.drawn_scale(taper, centre3)
        h.check(
            "%s: the disc is drawn at the scale it is grabbed with" % label,
            scale is not None and scale[0] and abs(scale[0] - scale[1]) <= 0.02 * scale[1],
            scale,
        )
        closeup("extrude-" + label, [foot, tip, centre])
    h.shot("extrude-" + label)


def measure_move(label):
    p = move_panel()
    triad = getattr(p, "triad", None) if p is not None else None
    if not h.check("%s: Move's manipulator shown" % label, triad is not None):
        return
    x = V(1, 0, 0)
    centre = h.screen_point(triad.center)
    tip = h.screen_point(triad.center + x * triad.size)
    length = math.hypot(tip.x() - centre.x(), tip.y() - centre.y())
    s["triad"][label] = length
    want = core().TRIAD_PX * axis_factor(x)
    h.check(
        "%s: the X arrow is TRIAD_PX from the centre (%.1f px as the view shows it)"
        % (label, want),
        abs(length - want) <= 2.0,
        round(length, 2),
    )
    drawn = triad.pixels.drawn_mm_per_px()
    from sciforge import handle_look

    maths = handle_look.mm_per_px(triad.view, triad.center)
    h.check(
        "%s: the manipulator is drawn at the scale it is grabbed with" % label,
        drawn and abs(drawn - maths) <= 0.02 * maths,
        (drawn, maths),
    )
    tips = [h.screen_point(triad.center + axis * triad.size) for axis in (x, V(0, 1, 0), V(0, 0, 1))]
    closeup("move-" + label, [centre] + tips)
    h.shot("move-" + label)


def steps_for(name, size, face, distance):
    def setup():
        make_block("HandleSize%s" % name.capitalize(), *size)

    def press_e():
        h.press("e")

    def click_face():
        h.click(face)

    def give():
        a.give_distance(distance)

    give.wait_ms = 1500

    def fit():
        h.fit()
        park_mouse()

    fit.wait_ms = 900

    def at_fit():
        measure_extrude(name + "-fit")

    def out():
        zoom(3.0)

    out.wait_ms = 900

    def at_out():
        measure_extrude(name + "-out")

    def close():
        zoom(1.0 / 6.0)

    close.wait_ms = 900

    def at_close():
        measure_extrude(name + "-in")

    def esc():
        h.press(QtCore.Qt.Key_Escape)

    def move_m():
        h.check("%s: Extrude closed" % name, extrude_panel() is None)
        h.click_empty()
        h.fit()
        h.press("m")

    def move_click():
        h.click(face)
        park_mouse()

    move_click.wait_ms = 900

    def move_fit():
        measure_move(name + "-fit")

    def move_out():
        zoom(2.5)

    move_out.wait_ms = 900

    def move_at_out():
        measure_move(name + "-out")

    def move_esc():
        h.press(QtCore.Qt.Key_Escape)

    steps = [
        setup, press_e, click_face, give, fit, at_fit, out, at_out, close, at_close, esc,
        move_m, move_click, move_fit, move_out, move_at_out, move_esc,
    ]
    for step in steps:
        step.__name__ = "%s_%s" % (name, step.__name__)
    return steps


def compare():
    for what, key, tol in (
        ("the Extrude arrow", "arrow", 2.0),
        ("the drawn arrow", "blue", 3.0),
        ("the taper disc", "disc", 3.0),
        ("Move's arrow", "triad", 2.0),
    ):
        values = s[key]
        spread = (max(values.values()) - min(values.values())) if values else None
        h.check(
            "%s keeps one size on the screen (small / big part, Fit / out / in): %s px"
            % (what, "?" if spread is None else "%.1f" % spread),
            len(values) >= 4 and spread is not None and spread <= tol,
            {k: round(v, 1) for k, v in values.items()},
        )
    h.check("no pop-ups", not h.popups(), h.popups())


h.run(
    "handle_size",
    steps_for("small", (4, 3, 1), V(2, 1.5, 1), "2")
    + steps_for("big", (400, 300, 100), V(200, 150, 100), "50")
    + [compare],
)
