# SPDX-License-Identifier: LGPL-2.1-or-later
"""The colours a sketch curve is drawn in (sciforge/sketch_mode.py: PARAMS and
FixedColour), checked on screen: a free line blue, a fully constrained one white, a
fixed one (Fix/Unfix: FreeCAD's Block) green, a construction line orange, a locked
point green; a selected line in the selection colour and a hovered line in the hover
colour, neither of them the blue of a free line. The green stays after a hover and a
click elsewhere (FreeCAD repaints then). Fixed with Fix/Unfix through the ribbon
(real click) as well as by a Block made directly.
"""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui
from PySide6 import QtTest

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import sketch_input as si

V = App.Vector
s = {}


class _Colours:
    """sketch_mode's colours, with the expected values as a fallback so the checks still
    run (and fail on the behaviour) on a SciForge without them."""

    BLUE = "#5cb3ff"
    WHITE = "#f0f0f0"
    GREEN = "#4ad66d"
    ORANGE = "#f5a142"
    SELECT = "#3b5bdb"
    HOVER = "#246eab"

    def __init__(self):
        from sciforge import sketch_mode

        for name in ("BLUE", "WHITE", "GREEN", "ORANGE", "SELECT", "HOVER"):
            setattr(self, name, getattr(sketch_mode, name, getattr(self, name)))


def colours():
    return _Colours()


def g(point):
    return s["sk"].getGlobalPlacement().multVec(point)


def move(point):
    pos = h.screen_point(point)
    QtGui.QCursor.setPos(h.gl_widget().mapToGlobal(pos))
    h.move(pos)


def seen(point, wait=300):
    QtTest.QTest.qWait(wait)
    return si.screen_colours(g(point), 2)


def shows(label, point, hex_colour, not_colour=None):
    found = seen(point)
    ok = si.colour_near(hex_colour, found, 30)
    if ok and not_colour is not None:
        ok = not si.colour_near(not_colour, found, 12)
    h.check(label, ok, (hex_colour, si.brightest(found), sorted(set(found.values()))[:8]))
    return ok


def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("SketchColours")
    h.fit()


def create_sketch():
    h.ribbon("Create Sketch")


def pick_xy():
    pl.click_square("XY_Plane")  # where the square shows (was 12, -8, 0)


def draw():
    import Part
    import Sketcher

    sk = h.in_sketch()
    s["sk"] = sk
    h.check("sketch open", sk is not None)
    s["free"] = sk.addGeometry(Part.LineSegment(V(-60, 30, 0), V(-20, 30, 0)))
    s["fixed"] = sk.addGeometry(Part.LineSegment(V(-60, 15, 0), V(-20, 15, 0)))
    sk.addConstraint(Sketcher.Constraint("Block", s["fixed"]))
    s["full"] = sk.addGeometry(Part.LineSegment(V(-60, 0, 0), V(-20, 0, 0)))
    sk.addConstraint(Sketcher.Constraint("DistanceX", -1, 1, s["full"], 1, -60))
    sk.addConstraint(Sketcher.Constraint("DistanceY", -1, 1, s["full"], 1, 0))
    sk.addConstraint(Sketcher.Constraint("Horizontal", s["full"]))
    sk.addConstraint(Sketcher.Constraint("DistanceX", s["full"], 1, s["full"], 2, 40))
    s["constr"] = sk.addGeometry(Part.LineSegment(V(-60, -15, 0), V(-20, -15, 0)), True)
    s["locked"] = sk.addGeometry(Part.LineSegment(V(20, 30, 0), V(60, 30, 0)))
    sk.addConstraint(Sketcher.Constraint("DistanceX", -1, 1, s["locked"], 2, 60))
    sk.addConstraint(Sketcher.Constraint("DistanceY", -1, 1, s["locked"], 2, 30))
    s["ribbon"] = sk.addGeometry(Part.LineSegment(V(20, 0, 0), V(60, 0, 0)))
    App.ActiveDocument.recompute()
    move(V(0, -60, 0))  # the pointer away from every line


def check_colours():
    c = colours()
    shows("a free line is blue", V(-40, 30, 0), c.BLUE)
    shows("a fully constrained line is white", V(-40, 0, 0), c.WHITE)
    shows("a fixed (Block) line is green", V(-40, 15, 0), c.GREEN, c.WHITE)
    shows("a construction line is orange", V(-40, -15, 0), c.ORANGE)
    shows("a locked point is green", V(60, 30, 0), c.GREEN, c.WHITE)
    h.shot("1-colours")


def select_free():
    Gui.Selection.addSelection(App.ActiveDocument.Name, s["sk"].Name, "Edge%d" % (s["free"] + 1))


def check_selected():
    c = colours()
    found = seen(V(-40, 30, 0))
    h.check(
        "a selected line is not the free blue",
        not si.colour_near(c.BLUE, found, 12),
        si.brightest(found),
    )
    h.check(
        "...it is the selection colour",
        si.colour_near(c.SELECT, found, 30),
        (c.SELECT, si.brightest(found)),
    )
    Gui.Selection.clearSelection()


def hover_free():
    # rest the pointer on the line's left part; the colour is read at its middle
    move(V(-52, 30, 0))


def check_hovered():
    c = colours()
    found = seen(V(-40, 30, 0))
    h.check(
        "a hovered line is not the free blue",
        not si.colour_near(c.BLUE, found, 12),
        si.brightest(found),
    )
    h.check(
        "...it is the hover colour",
        si.colour_near(c.HOVER, found, 30),
        (c.HOVER, si.brightest(found)),
    )
    shows("the fixed line stays green while another is hovered", V(-40, 15, 0), c.GREEN, c.WHITE)


def hover_fixed():
    move(V(-52, 15, 0))


def check_hovered_fixed():
    c = colours()
    found = seen(V(-40, 15, 0))
    h.check(
        "a hovered fixed line shows the hover colour (not green)",
        si.colour_near(c.HOVER, found, 30),
        si.brightest(found),
    )
    move(V(0, -60, 0))
    shows("...and is green again when the pointer leaves", V(-40, 15, 0), c.GREEN, c.WHITE)


def fix_with_ribbon():
    """Fusion's Fix/Unfix on a selected line, from the ribbon (a Block)."""
    Gui.Selection.addSelection(App.ActiveDocument.Name, s["sk"].Name, "Edge%d" % (s["ribbon"] + 1))
    si.menu_item("CONSTRAINTS", "Fix/Unfix")


def check_ribbon_fixed():
    sk = s["sk"]
    blocks = [c for c in sk.Constraints if c.Type == "Block" and c.First == s["ribbon"]]
    h.check("Fix/Unfix put a Block on the line", len(blocks) == 1, [c.Type for c in sk.Constraints])
    Gui.Selection.clearSelection()
    move(V(0, -60, 0))
    shows("...and it is green", V(40, 0, 0), colours().GREEN, colours().WHITE)
    h.shot("2-fixed")


def click_elsewhere():
    h.click(g(V(0, -70, 0)))


def still_green():
    shows(
        "the fixed lines stay green after a click elsewhere",
        V(-40, 15, 0),
        colours().GREEN,
        colours().WHITE,
    )
    shows("...the ribbon-fixed one too", V(40, 0, 0), colours().GREEN, colours().WHITE)


def finish():
    h.ribbon("Finish Sketch")


h.run(
    "sketch_colours",
    si.watched(
        [
            new_design,
            create_sketch,
            pick_xy,
            draw,
            check_colours,
            select_free,
            check_selected,
            hover_free,
            check_hovered,
            hover_fixed,
            check_hovered_fixed,
            fix_with_ribbon,
            check_ribbon_fixed,
            click_elsewhere,
            still_green,
            finish,
        ]
    ),
)
