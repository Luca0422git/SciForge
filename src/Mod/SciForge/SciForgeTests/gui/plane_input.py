# SPDX-License-Identifier: LGPL-2.1-or-later
"""Aim at an origin square the way a person does: at a spot of it that shows and that no
part covers (the squares are small and stay in the + quarter of their plane, like Fusion's,
so a fixed point can miss them; a hidden one is picked in the browser). Kept outside scenarios/ because every file there is run as a scenario."""

import FreeCAD as App
from PySide import QtWidgets

from SciForgeTests.gui import harness as h

# where on each square a person would aim first (fractions of its half size along its u, v)
PREFER = {"XY_Plane": (0.6, -0.6), "XZ_Plane": (0.6, 0.6), "YZ_Plane": (-0.6, 0.6)}


def picker():
    """The origin squares on show (sketch_ui.PlanePicker or a subclass), or None."""
    from sciforge import sketch_ui

    live = [p for p in sketch_ui.PlanePicker.LIVE if p.callbacks]
    return live[-1] if live else None


def settle(p):
    """The squares follow the view on a 250 ms timer: bring them up to date for this view
    (a fit just before), else they can move between aiming and clicking."""
    follow = getattr(p, "_follow_zoom", None)
    if follow is not None:
        follow()


def _takes(p, pixel, role):
    if hasattr(p, "front_plane_at"):
        return p.front_plane_at(pixel) == role
    return not p._geometry_at(pixel) and p.plane_at(pixel) == role


def square_point(role="XY_Plane", picker_=None):
    """A 3D point on the `role` square that a click there gives to that square (nothing in
    front of it, not under the dialog), nearest the preferred spot; None when none shows."""
    p = picker_ or picker()
    if p is None:
        return None
    settle(p)
    pa, pb = PREFER.get(role, (0.5, 0.5))
    steps = [i / 10.0 for i in range(-9, 10)]
    spots = sorted(
        ((a, b) for a in steps for b in steps), key=lambda ab: (ab[0] - pa) ** 2 + (ab[1] - pb) ** 2
    )
    view = h.view()
    widget = h.gl_widget()
    margin = 20
    for a, b in spots:
        point = p.spot(role, a, b)
        pixel = view.getPointOnViewport(point)
        qt = h.screen_point(point)
        inside = margin < qt.x() < widget.width() - margin
        if not (inside and margin < qt.y() < widget.height() - margin):
            continue  # off the view
        if h.covered(qt):
            continue
        x, y = float(pixel[0]), float(pixel[1])
        around = [(x + dx, y + dy) for dx in (-4, -2, 0, 2, 4) for dy in (-4, -2, 0, 2, 4)]
        around += [(x + 8, y), (x - 8, y), (x, y + 8), (x, y - 8)]
        if not all(_takes(p, (int(round(a)), int(round(b))), role) for a, b in around):
            continue
        # what is drawn can change under the mouse (a sketch's shaded area steps back and
        # shows a face lying in the plane): look again with the mouse there
        h.move(qt)
        QtWidgets.QApplication.processEvents()
        if all(_takes(p, (int(round(a)), int(round(b))), role) for a, b in around[:25]):
            return App.Vector(point)  # well inside what the square takes, not at an edge
    return None


def click_square(role="XY_Plane"):
    """Click the `role` square where it shows; when the part hides it (the squares stay at
    the origin, like Fusion's), pick the plane in the browser instead, as a person does:
    open the Origin folder and click the plane's row ("XY")."""
    point = square_point(role)
    if point is None:
        return pick_in_browser(role)
    h.click(point)
    return point


def pick_in_browser(role="XY_Plane"):
    """Open the browser's Origin folder and click the `role` plane's row."""
    from SciForgeTests.gui import bodies_steps, shell_draft_steps

    label = role.split("_")[0]  # "XY_Plane" -> "XY" (browser_core.ORIGIN_LABELS)
    tree = bodies_steps.browser()
    if tree is not None and tree.row(label) is None:
        shell_draft_steps.expand_browser_row("Origin")
    found = tree is not None and tree.row(label) is not None
    if not h.check("the %s plane in the browser" % role, found, tree and tree.labels()):
        h.shot("no-%s-square" % role)
        return None
    tree.scrollToItem(tree.row(label))  # the folder has just opened: bring the row in view
    QtWidgets.QApplication.processEvents()
    bodies_steps.click_browser_row(label)
    return label


def click_on_plane(point):
    """Click `point`, a spot on an origin plane a scenario aims at (V(12, -8, 0): on XY):
    where it shows the square or the part, there; when the square no longer covers it
    (the squares are small since 2026-10-18 and lie in their + quarter), on that plane's
    square where it shows, as a person does."""
    p = picker()
    role = _plane_of(point)
    if p is None or role is None:
        h.click(point)
        return point
    settle(p)
    pixel = h.view().getPointOnViewport(point)
    pixel = (int(round(float(pixel[0]))), int(round(float(pixel[1]))))
    if p._geometry_at(pixel) or _takes(p, pixel, role):
        h.click(point)
        return point
    return click_square(role)


def _plane_of(point, tol=1e-9):
    """The origin plane `point` lies in ("XY_Plane" for z = 0 ...), or None."""
    if abs(point.z) <= tol:
        return "XY_Plane"
    if abs(point.y) <= tol:
        return "XZ_Plane"
    if abs(point.x) <= tol:
        return "YZ_Plane"
    return None
