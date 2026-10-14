# SPDX-License-Identifier: LGPL-2.1-or-later
"""Section views with bends and Section Depth (CREATE > Section View), with real clicks.

The plate (drawing_fixtures.plate: holes at (-20, -10) and (20, 10) of the Top view),
ISO A3 (first angle), base view Top at 1:1.

A  Offset section through both holes: click the view, then the cut line's points below
   hole 1, at its middle, across to hole 2's middle, and above the part; Enter ends the
   line; move right and click: SECTION A-A, a complex section of type Offset, lined up
   with the base view, 10 x 50, both holes cut (lines at their sides).
B  Undo removes it (and its cut line); Redo brings it back.
C  Half section: three points (above the part, its middle, out to the right); moving
   well away from the view ends the line; placed on the left: type Half.
D  Esc while drawing a line: nothing new, no preview left.
E  A straight section across through hole 2, placed below (it looks at the part below
   the cut: hole 1 lies 15 to 25 mm behind it), then its dialog (double-click): the
   style with hidden edges and Section Depth Slice: the lines behind the cut faces are
   switched off, hole 1's among them; Distance 30: hole 1 shows again; Distance 15: it
   lies deeper, off again; the view label hidden then shown. OK.
F  The offset section's dialog: Section Depth Slice is refused (it works on straight
   lines) and the section stays whole; Cancel.
G  Aligned section: from the left, to hole 1's middle, then slanting to hole 2's middle;
   Enter; placed above: type Aligned, TechDraw lays the slanted cut flat.
H  A straight section down through hole 1, placed far right (it looks at the half of the
   hole where the round face's seam runs): no line along the hole's middle (TechDraw
   draws one; Fusion does not), the hole's sides and every other line stay.
"""

from PySide import QtCore
from PySide6 import QtTest

from SciForgeTests.gui import drawing2_steps as w
from SciForgeTests.gui import drawing_input as d
from SciForgeTests.gui import harness as h

state = {}


def sections():
    from sciforge import drawing

    page = d.page()
    return [v for v in drawing.all_views(page) if drawing.is_section(v)] if page else []


def section(label):
    for view in sections():
        if view.SectionSymbol == label:
            return view
    return None


def base_pos():
    from sciforge import drawing

    return drawing.view_position(w.base())


# -- A ------------------------------------------------------------------------------------------
def a_command():
    h.ribbon("Section View")


def a_line():
    p = d.panel_of("SectionPanel")
    if not h.check("Section View dialog", p is not None, d.panel()):
        return
    w.click(10.0, 5.0)  # the view
    for u, v in ((-20.0, -33.0), (-20.0, 0.0), (20.0, 0.0), (20.0, 33.0)):
        w.click(u, v)


a_line.wait_ms = 1200


def a_enter():
    p = d.panel_of("SectionPanel")
    h.check("four points", p is not None and len(p.points) == 4, p and p.points)
    d.key(QtCore.Qt.Key_Return)


def a_place():
    x, y = base_pos()
    d.move_to(x + 70, y + 8)
    d.move_to(x + 90, y + 5)


a_place.wait_ms = 2500


def a_click():
    found = sections()
    h.check("the section follows the mouse", len(found) == 1, found)
    x, y = base_pos()
    d.click_at(x + 90, y + 5)


a_click.wait_ms = 1000


def a_ok():
    p = d.panel_of("SectionPanel")
    h.check("its type: Offset", p is not None and p.kind.text() == "Offset", p and p.kind.text())
    d.ok()


a_ok.wait_ms = 2500


def a_check():
    from sciforge import drawing

    sec = section("A")
    if not h.check("SECTION A-A", sec is not None, [s.SectionSymbol for s in sections()]):
        return
    h.check("a complex section", sec.TypeId == drawing.COMPLEX, sec.TypeId)
    h.check("Offset strategy", sec.ProjectionStrategy == "Offset", sec.ProjectionStrategy)
    profile = sec.CuttingToolWireObject
    h.check("its cut line: 3 segments", profile is not None and len(profile.Geometry) == 3)
    bx, by = base_pos()
    sx, sy = drawing.view_position(sec)
    h.check("lined up with the base view", abs(sy - by) < 1e-4, (sy, by))
    half_w, half_h = drawing.view_extent(sec)
    h.check("10 x 50", abs(half_w - 5.0) < 0.05 and abs(half_h - 25.0) < 0.05, (half_w, half_h))
    sides = sorted(
        round(e.BoundBox.YMin, 3)
        for e in sec.getVisibleEdges(True)
        if abs(e.BoundBox.YMin - e.BoundBox.YMax) < 1e-6
    )
    for side in (-15.0, -5.0, 5.0, 15.0):
        h.check("a hole side at %g" % side, any(abs(v - side) < 0.02 for v in sides), sides)
    state["profile"] = profile.Name
    h.shot("a-offset")


a_check.wait_ms = 1000


# -- B ------------------------------------------------------------------------------------------
def b_undo():
    d.undo()


b_undo.wait_ms = 1500


def b_undone():
    h.check("undo: no section", not sections(), sections())
    doc = d.page().Document
    h.check("its cut line went too", doc.getObject(state["profile"]) is None)
    d.redo()


b_undone.wait_ms = 2500


def b_redone():
    sec = section("A")
    h.check("redo: back", sec is not None and len(sec.getVisibleEdges()) > 0)


# -- C ------------------------------------------------------------------------------------------
def c_command():
    h.ribbon("Section View")


def c_line():
    w.click(10.0, 5.0)
    for u, v in ((0.0, 33.0), (0.0, 0.0), (50.0, 0.0)):
        w.click(u, v)


c_line.wait_ms = 1200


def c_away():
    x, y = base_pos()
    d.move_to(x - 70, y + 4)
    d.move_to(x - 90, y + 2)


c_away.wait_ms = 2500


def c_place():
    found = sections()
    h.check("the half section follows the mouse", len(found) == 2, found)
    x, y = base_pos()
    d.click_at(x - 90, y + 2)


c_place.wait_ms = 1000


def c_ok():
    p = d.panel_of("SectionPanel")
    h.check("type Half", p is not None and p.kind.text() == "Half", p and p.kind.text())
    d.ok()


c_ok.wait_ms = 2500


def c_check():
    sec = section("B")
    if not h.check("SECTION B-B", sec is not None, [s.SectionSymbol for s in sections()]):
        return
    h.check("it has geometry", len(sec.getVisibleEdges()) > 0)
    h.check("Offset strategy for a half section", sec.ProjectionStrategy == "Offset")


# -- D ------------------------------------------------------------------------------------------
def d_command():
    h.ribbon("Section View")


def d_points():
    w.click(10.0, 5.0)
    w.click(-30.0, 33.0)
    w.click(-30.0, 10.0)
    w.move(-10.0, 10.0)


def d_escape():
    d.key(QtCore.Qt.Key_Escape)


def d_nothing():
    h.check("Esc: still two sections", len(sections()) == 2, sections())
    h.check("dialog closed", d.panel() is None)
    h.check("no preview left", d.previews_left() == 0, d.previews_left())


# -- E ------------------------------------------------------------------------------------------
def e_command():
    h.ribbon("Section View")


def e_line():
    w.click(10.0, 5.0)
    w.click(-48.0, 10.0)
    w.click(48.0, 10.0)
    x, y = base_pos()
    d.move_to(x + 3, y - 55)
    d.move_to(x + 2, y - 70)


e_line.wait_ms = 2500


def e_place():
    x, y = base_pos()
    d.click_at(x + 2, y - 70)


e_place.wait_ms = 1000


def e_ok():
    d.ok()


e_ok.wait_ms = 2500


def e_open():
    from sciforge import drawing

    sec = section("C")
    if not h.check("SECTION C-C", sec is not None, [s.SectionSymbol for s in sections()]):
        return
    state["lines"] = len(sec.getVisibleEdges())
    x, y = drawing.view_position(sec)
    half_w, _half_h = drawing.view_extent(sec)
    d.double_click_at(x + half_w - 1.0, y)


e_open.wait_ms = 1500


def hole1_lines_off():
    """The section's lines switched off for its depth that are hole 1's sides (its middle
    is 20 mm behind the cut: |x| 15 and 25 across, upright through the middle)."""
    from sciforge import drawing_depth

    found = []
    for _i, x, y in drawing_depth.stored(section("C")):
        if abs(y) < 0.5 and min(abs(abs(x) - 15.0), abs(abs(x) - 25.0)) < 0.5:
            found.append(x)
    return found


def e_slice():
    p = d.panel_of("SectionPanel")
    if not h.check("the section's dialog", p is not None, d.panel()):
        return
    h.check("depth Full", p.depth.currentText() == "Full")
    h.check("no distance yet", not p.distance.isVisibleTo(p.form))
    d.choose(p.style, "Visible and Hidden Edges")
    d.choose(p.depth, "Slice")


e_slice.wait_ms = 4000


def e_sliced():
    from sciforge import drawing, drawing_depth

    sec = section("C")
    h.check("Slice", drawing.section_depth(sec)[0] == "Slice", drawing.section_depth(sec))
    h.check("hidden edges on", sec.HardHidden)
    h.check(
        "it still cuts the parts the base view shows",
        [s.Name for s in sec.Source] == [s.Name for s in w.base().Source],
        [s.Name for s in sec.Source],
    )
    off = drawing_depth.stored(sec)
    lines = drawing_depth.section_lines(sec)
    h.check(
        "lines behind the cut faces are switched off (some, not all)",
        0 < len(off) < len(lines),
        (len(off), len(lines)),
    )
    hole1 = hole1_lines_off()
    h.check(
        "hole 1's sides among them (on one side of the middle)",
        len(hole1) >= 2 and (all(x > 0 for x in hole1) or all(x < 0 for x in hole1)),
        hole1,
    )
    p = d.panel_of("SectionPanel")
    d.choose(p.depth, "Distance")


e_sliced.wait_ms = 1000


def e_distance():
    p = d.panel_of("SectionPanel")
    h.check("the distance box shows", p is not None and p.distance.isVisibleTo(p.form))
    d.type_into(p.distance, "30")
    QtTest.QTest.keyClick(p.distance, QtCore.Qt.Key_Tab)  # (leaving the box keeps it)


e_distance.wait_ms = 3000


def e_deeper():
    from sciforge import drawing

    sec = section("C")
    h.check(
        "Distance 30", drawing.section_depth(sec) == ("Distance", 30.0), drawing.section_depth(sec)
    )
    h.check("hole 1 shows again (within 30 mm)", hole1_lines_off() == [], hole1_lines_off())
    p = d.panel_of("SectionPanel")
    d.type_into(p.distance, "15")
    QtTest.QTest.keyClick(p.distance, QtCore.Qt.Key_Tab)


e_deeper.wait_ms = 3000


def e_shallow():
    from sciforge import drawing

    sec = section("C")
    h.check(
        "Distance 15", drawing.section_depth(sec) == ("Distance", 15.0), drawing.section_depth(sec)
    )
    h.check("hole 1 is off again (20 mm deep)", len(hole1_lines_off()) >= 2, hole1_lines_off())
    w.toggle(d.panel_of("SectionPanel").show_label)


e_shallow.wait_ms = 1500


def e_style():
    sec = section("C")
    h.check("label hidden", sec.Caption == "", sec.Caption)
    w.toggle(d.panel_of("SectionPanel").show_label)


def e_label():
    sec = section("C")
    h.check("label shown again", sec.Caption == "SECTION C-C", sec.Caption)
    d.ok()


e_label.wait_ms = 2500


def e_done():
    from sciforge import drawing

    h.check("dialog closed", d.panel() is None)
    sec = section("C")
    h.check("OK kept Distance 15", drawing.section_depth(sec) == ("Distance", 15.0))
    h.check("and hole 1 off", len(hole1_lines_off()) >= 2, hole1_lines_off())
    h.shot("e-depth")


# -- F ------------------------------------------------------------------------------------------
def f_open():
    from sciforge import drawing

    sec = section("A")
    x, y = drawing.view_position(sec)
    half_w, _half_h = drawing.view_extent(sec)
    d.double_click_at(x + half_w - 1.0, y)


f_open.wait_ms = 1500


def f_slice():
    p = d.panel_of("SectionPanel")
    if h.check("the offset section's dialog", p is not None, d.panel()):
        d.choose(p.depth, "Slice")


f_slice.wait_ms = 1000


def f_refused():
    from sciforge import drawing

    p = d.panel_of("SectionPanel")
    h.check(
        "refused: straight lines only",
        p is not None and "straight" in p.message.text(),
        p and p.message.text(),
    )
    h.check("still whole", drawing.section_depth(section("A"))[0] == "Full")
    d.cancel()


f_refused.wait_ms = 1500


def f_done():
    h.check("dialog closed", d.panel() is None)


# -- G ------------------------------------------------------------------------------------------
def g_command():
    h.ribbon("Section View")


def g_line():
    w.click(10.0, 5.0)
    for u, v in ((-48.0, -10.0), (-20.0, -10.0), (20.0, 10.0)):
        w.click(u, v)


g_line.wait_ms = 1200


def g_enter():
    d.key(QtCore.Qt.Key_Return)


def g_place():
    x, y = base_pos()
    d.move_to(x + 3, y + 60)
    d.move_to(x + 2, y + 72)


g_place.wait_ms = 3000


def g_click():
    x, y = base_pos()
    d.click_at(x + 2, y + 72)


def g_ok():
    p = d.panel_of("SectionPanel")
    h.check("type Aligned", p is not None and p.kind.text() == "Aligned", p and p.kind.text())
    d.ok()


g_ok.wait_ms = 3000


def g_check():
    sec = section("D")
    if not h.check("SECTION D-D", sec is not None, [s.SectionSymbol for s in sections()]):
        return
    h.check("Aligned strategy", sec.ProjectionStrategy == "Aligned", sec.ProjectionStrategy)
    h.check("it has geometry", len(sec.getVisibleEdges()) > 0, len(sec.getVisibleEdges()))
    h.shot("g-aligned")


# -- H ------------------------------------------------------------------------------------------
def h_command():
    h.ribbon("Section View")


def h_line():
    w.click(10.0, 5.0)
    w.click(-20.0, 35.0)
    w.click(-20.0, -35.0)
    x, y = base_pos()
    d.move_to(x + 140, y + 3)
    d.move_to(x + 160, y + 2)


h_line.wait_ms = 2500


def h_place():
    x, y = base_pos()
    d.click_at(x + 160, y + 2)


h_place.wait_ms = 1000


def h_ok():
    d.ok()


h_ok.wait_ms = 4000


def h_check():
    from sciforge import drawing, drawing_depth

    sec = section("E")
    if not h.check("SECTION E-E", sec is not None, [s.SectionSymbol for s in sections()]):
        return
    h.check("a straight cut", sec.TypeId == drawing.SECTION, sec.TypeId)
    h.check("depth Full", drawing.section_depth(sec)[0] == "Full")
    off = drawing_depth.stored(sec)
    # the section shows the plate's 10 mm thickness across and its 50 mm up: hole 1's
    # middle is 10 mm below the middle of what lies behind the cut (y 15 of 0..50)
    seam = [item for item in off if abs(item[1]) < 0.3 and abs(item[2] + 10.0) < 0.3]
    h.check("the line along the hole's middle is off", len(seam) == 1, off)
    h.check("nothing else is off", len(seam) == len(off), off)
    indices = {item[0] for item in off}
    sides = []
    for i, edge in drawing_depth.section_lines(sec):
        a, b = edge.Vertexes[0].Point, edge.Vertexes[-1].Point
        level = abs(a.y - b.y) < 0.01 and abs(a.x - b.x) > 1.0
        if level and min(abs(a.y + 5.0), abs(a.y + 15.0)) < 0.05:
            sides.append(i)
    h.check("the hole's sides stay", len(sides) >= 2 and not indices & set(sides), (sides, off))
    h.shot("h-seam")


h.run(
    "drawing2_sections",
    [w.new_design("Sec")]
    + w.sheet_steps()
    + [d.wait_geometry(1500)]
    + [a_command, a_line, a_enter, a_place, a_click, a_ok, a_check]
    + [b_undo, b_undone, b_redone]
    + [c_command, c_line, c_away, c_place, c_ok, c_check]
    + [d_command, d_points, d_escape, d_nothing]
    + [e_command, e_line, e_place, e_ok, e_open, e_slice, e_sliced, e_distance, e_deeper]
    + [e_shallow]
    + [e_style, e_label, e_done]
    + [f_open, f_slice, f_refused, f_done]
    + [g_command, g_line, g_enter, g_place, g_click, g_ok, g_check]
    + [h_command, h_line, h_place, h_ok, h_check],
)
