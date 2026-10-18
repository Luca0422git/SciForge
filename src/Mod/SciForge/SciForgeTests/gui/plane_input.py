# SPDX-License-Identifier: LGPL-2.1-or-later
"""Aim at an origin square the way a person does: at a spot of it that shows and that no
part covers (the squares are small, in the + quarter of their plane and moved beside a part
that would hide them, so a fixed point can miss them). Kept outside scenarios/ because every file there is run as a scenario."""

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
    """Click the `role` square where it shows (a check fails when it shows nowhere)."""
    point = square_point(role)
    if not h.check("the %s square shows somewhere to click" % role, point is not None):
        return None
    h.click(point)
    return point
