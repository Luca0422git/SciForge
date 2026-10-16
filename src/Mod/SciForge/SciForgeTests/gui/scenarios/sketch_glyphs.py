# SPDX-License-Identifier: LGPL-2.1-or-later
"""SciForge's own marks beside the geometry while drawing (sciforge/sketch_infer.py,
Overlay): a short level mark under a line that snapped level, an upright mark beside
one that snapped upright; drawn in the scene in the guide colour while the pointer is
there, gone after the click (FreeCAD's own constraint glyph takes over).

L, click a start, move 3 degrees off level: the mark is in the overlay and on screen
(a pixel of the guide colour where the mark is drawn); click: the mark is gone from
the overlay and from the screen. The same upright. A free direction (7 degrees off)
has no mark.
"""

import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui
from PySide6 import QtTest

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import sketch_input as si

V = App.Vector
s = {}
GUIDE = "#7ee0ff"  # sketch_infer.GUIDE_COLOR


def session():
    from sciforge import sketch_mode

    return sketch_mode.current()


def infer_state():
    sess = session()
    return sess.infer.state() if sess is not None and sess.infer is not None else {}


def g(point):
    return s["sk"].getGlobalPlacement().multVec(point)


def esc():
    h.press(QtCore.Qt.Key_Escape)


def move(point):
    pos = h.screen_point(point)
    QtGui.QCursor.setPos(h.gl_widget().mapToGlobal(pos))
    h.move(pos)


def approach(raw, towards=V(-1.0, 1.5, 0)):
    for f in (3.0, 2.0, 1.0, 0.0):
        move(g(raw + towards * f))


def marks():
    return infer_state().get("overlay", {}).get("marks", [])


def mark_middle(stroke):
    a, b = stroke[0], stroke[-1]
    return V((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0, 0)


def on_screen(point):
    """The guide colour is drawn around the 3D point."""
    QtTest.QTest.qWait(250)
    return si.colour_near(GUIDE, si.screen_colours(point, 3))


def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("SketchGlyphs")
    h.fit()


def create_sketch():
    h.ribbon("Create Sketch")


def pick_xy():
    pl.click_square("XY_Plane")  # where the square shows (was 12, -8, 0)


def ready():
    sk = h.in_sketch()
    s["sk"] = sk
    h.check("sketch open", sk is not None)
    s["px"] = si.mm_per_pixel(sk)


# == level ============================================================================
def l_key():
    h.press("l")


def l_start():
    si.click(g(V(-30, 10, 0)))


def l_near_level():
    s["l_raw"] = V(20, 10 + 50 * math.tan(math.radians(3.0)), 0)
    approach(s["l_raw"], V(1.0, 1.0, 0))
    state = infer_state()
    found = marks()
    last = state.get("last")
    h.check("3 degrees off level snaps level", last is not None and last.kind == "h", last)
    h.check(
        "the level mark is drawn (one short stroke)", len(found) == 1 and len(found[0]) == 2, found
    )
    if found:
        stroke = found[0]
        level = abs(stroke[0][1] - stroke[1][1]) < 1e-9 and abs(stroke[0][0] - stroke[1][0]) > 1e-6
        h.check(
            "...a horizontal stroke under the line, near its end",
            level and stroke[0][1] < 10,
            stroke,
        )
        s["l_mark"] = mark_middle(stroke)
        h.check(
            "...and it is on screen in the guide colour",
            on_screen(g(s["l_mark"])),
            si.screen_colours(g(s["l_mark"]), 3),
        )
    h.shot("1-level-mark")


def l_click():
    h.click(g(s["l_raw"]))


def l_after():
    sk = s["sk"]
    line = sk.Geometry[-1]
    h.check(
        "the line is level after the click", abs(line.EndPoint.y - line.StartPoint.y) < 1e-9, line
    )
    h.check("the mark is gone from the overlay after the click", not marks(), marks())
    if "l_mark" in s:
        # the pointer rests away from the old mark's spot (the chain's next line is
        # previewed from the end; the mark's spot is under the finished line's middle)
        move(g(V(40, 40, 0)))
        h.check(
            "...and gone from the screen",
            not on_screen(g(s["l_mark"])),
            si.screen_colours(g(s["l_mark"]), 3),
        )
    esc()


# == upright ===========================================================================
def u_key():
    h.press("l")


def u_start():
    si.click(g(V(50, -40, 0)))


def u_near_upright():
    # 3 degrees off upright, ending clear of the X axis (FreeCAD would snap onto it)
    s["u_raw"] = V(50 + 45 * math.tan(math.radians(3.0)), 5, 0)
    approach(s["u_raw"], V(1.0, 1.0, 0))
    found = marks()
    last = infer_state().get("last")
    h.check("3 degrees off upright snaps upright", last is not None and last.kind == "v", last)
    h.check(
        "the upright mark is drawn (one short stroke)",
        len(found) == 1 and len(found[0]) == 2,
        found,
    )
    if found:
        stroke = found[0]
        upright = (
            abs(stroke[0][0] - stroke[1][0]) < 1e-9 and abs(stroke[0][1] - stroke[1][1]) > 1e-6
        )
        h.check(
            "...a vertical stroke beside the line, near its end",
            upright and stroke[0][0] > 50,
            stroke,
        )
        s["u_mark"] = mark_middle(stroke)
        h.check(
            "...and it is on screen in the guide colour",
            on_screen(g(s["u_mark"])),
            si.screen_colours(g(s["u_mark"]), 3),
        )
    h.shot("2-upright-mark")


def u_click():
    h.click(g(s["u_raw"]))


def u_after():
    sk = s["sk"]
    line = sk.Geometry[-1]
    h.check(
        "the line is upright after the click", abs(line.EndPoint.x - line.StartPoint.x) < 1e-9, line
    )
    h.check("the mark is gone from the overlay after the click", not marks(), marks())
    esc()


# == free ==============================================================================
def f_key():
    h.press("l")


def f_start():
    si.click(g(V(-30, -40, 0)))


def f_free():
    raw = V(20, -40 + 50 * math.tan(math.radians(7.0)), 0)
    approach(raw, V(1.0, 1.0, 0))
    h.check("7 degrees off level: no mark", not marks(), marks())
    esc()


def finish():
    sk = s["sk"]
    h.check("sketch has no errors", not sk.MalformedConstraints and not sk.ConflictingConstraints)
    h.ribbon("Finish Sketch")


h.run(
    "sketch_glyphs",
    si.watched(
        [
            new_design,
            create_sketch,
            pick_xy,
            ready,
            l_key,
            l_start,
            l_near_level,
            l_click,
            l_after,
            u_key,
            u_start,
            u_near_upright,
            u_click,
            u_after,
            f_key,
            f_start,
            f_free,
            finish,
        ]
    ),
)
