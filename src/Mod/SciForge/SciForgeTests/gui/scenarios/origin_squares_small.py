# SPDX-License-Identifier: LGPL-2.1-or-later
"""The origin squares of Create Sketch are small like Fusion's (Luca, 2026-10-18, with a
picture of Fusion's: "make it small like that, but keep the color"), with real clicks.

A  A new design, Create Sketch: the view shows the origin with room round it (not zoomed
   onto the squares); each square is about origin_look.SCREEN_SIDE pixels on the screen and
   lies in the + quarter of its plane, a little off the axes; colours XY blue, XZ green, YZ
   red as before.
B  Zoom in: the squares keep their size on the screen.
C  Esc. A box 60 x 40 x 20 centred on the origin; Create Sketch: every square still shows
   somewhere to click (moved beside the part); a click on the XZ square makes a sketch on XZ.
"""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl

V = App.Vector
s = {}
ROLES = ("XY_Plane", "XZ_Plane", "YZ_Plane")


def side_px(p, role):
    """The square's longest side on the screen (px): its 4 corners projected."""
    corners = [p.spot(role, a, b) for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    pts = [h.screen_point(c) for c in corners]
    return max(
        ((pts[i].x() - pts[(i + 1) % 4].x()) ** 2 + (pts[i].y() - pts[(i + 1) % 4].y()) ** 2)
        ** 0.5
        for i in range(4)
    )


def a_start():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("SmallSquares")
    h.ribbon("Create Sketch")


def a_small():
    from sciforge import origin_look

    p = pl.picker()
    if not h.check("the origin squares show", p is not None):
        return
    want = origin_look.SCREEN_SIDE
    for role in ROLES:
        px = side_px(p, role)
        # seen at an angle a side looks shorter; never longer
        h.check("%s is small: about %d px on the screen" % (role, want),
                0.45 * want <= px <= 1.05 * want, round(px, 1))
        mu, mv = p.middle_of(role)
        h.check("%s lies in the + quarter, off the axes" % role,
                mu - p.half_of(role) > 0 and mv - p.half_of(role) > 0, (mu, mv))
    # the view keeps room round the origin: its pixel is well inside the view
    origin = h.screen_point(V(0, 0, 0))
    widget = h.gl_widget()
    h.check("the origin is in the middle part of the view",
            0.2 * widget.width() < origin.x() < 0.8 * widget.width()
            and 0.2 * widget.height() < origin.y() < 0.8 * widget.height(),
            (origin.x(), origin.y(), widget.width(), widget.height()))
    look = {role: tuple(round(c, 2) for c in p.looks[role].material.diffuseColor[0])
            for role in ROLES}
    h.check("XY blue, XZ green, YZ red",
            max(range(3), key=lambda i: look["XY_Plane"][i]) == 2
            and max(range(3), key=lambda i: look["XZ_Plane"][i]) == 1
            and max(range(3), key=lambda i: look["YZ_Plane"][i]) == 0, look)
    s["px"] = side_px(p, "XY_Plane")
    h.shot("A-empty-design")
    Gui.activeView().zoomIn()
    Gui.activeView().zoomIn()


def b_zoomed():
    p = pl.picker()
    px = side_px(p, "XY_Plane") if p is not None else None
    h.check("zoomed in: the squares keep their size on the screen",
            px is not None and abs(px - s["px"]) <= 0.12 * s["px"], (px, s["px"]))
    h.press(QtCore.Qt.Key_Escape)


b_zoomed.wait_ms = 1200


def c_part():
    h.check("Esc closed the picker", pl.picker() is None)
    doc = App.ActiveDocument
    body = doc.getObject("Body") or doc.addObject("PartDesign::Body", "Body")
    box = body.newObject("PartDesign::AdditiveBox", "Box")
    box.Length, box.Width, box.Height = 60, 40, 20
    box.Placement = App.Placement(V(-30, -20, 0), App.Rotation())
    doc.recompute()
    h.fit()
    h.ribbon("Create Sketch")


def c_beside():
    for role in ROLES:
        h.check("%s still shows somewhere to click" % role, pl.square_point(role) is not None)
    h.shot("C-beside-the-part")
    pl.click_square("XZ_Plane")


def c_on_xz():
    sk = h.in_sketch()
    h.check("a sketch opens on XZ", sk is not None)
    if sk is not None:
        normal = sk.getGlobalPlacement().Rotation.multVec(V(0, 0, 1))
        h.check("its normal is along Y", abs(abs(normal.y) - 1.0) < 1e-6, normal)
        h.ribbon("Finish Sketch")


h.run("origin_squares_small", [a_start, a_small, b_zoomed, c_part, c_beside, c_on_xz])
