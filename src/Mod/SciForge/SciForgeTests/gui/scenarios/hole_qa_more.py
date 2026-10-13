# SPDX-License-Identifier: LGPL-2.1-or-later
"""More of the Hole the way Fusion users use it, trying to break it (QA, only real input).
A 40 x 30 x 10 box with a boss d12 x 8 in its middle.

Path 16, Extents To: a hole down the boss To the box's top face (8 deep). The boss is made
         taller afterwards (timeline edit of its Extrude): the hole still ends on the box's
         top (Fusion's To follows its face). Edit the hole: To and its face are shown.
         Save, close, reopen: it still follows; Ctrl+Z.
Path 17, From Sketch for a beginner: OK with nothing picked, a sketch line clicked (lines
         do not count), two points clicked, Esc: nothing made. The sketch selected in the
         browser, then H: both points at once; Enter over the view.
Path 18, H pressed again while the Hole dialog is open: the first hole is kept, the new
         dialog starts empty.
Path 19, a tapped hole made Modeled and OK clicked at once, while FreeCAD still computes the
         thread: no error; OK works once the preview is there.
Path 20, the right-click marking menu while the dialog is open: OK keeps the hole, Cancel
         drops the next one.
Path 21, Suppress the hole in the timeline and back.

Volumes by hand (hole_steps has the formulas); the boss adds pi 36 h.
"""
import math
import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
import Part
from PySide import QtCore
from PySide6 import QtTest

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import hole_steps as hs
from SciForgeTests.gui import timeline_input as ti
from SciForgeTests.gui import widget_input as w

V = App.Vector
s = {}
BOSS_R = 6.0


def doc():
    return App.ActiveDocument


def dialog_open():
    return bool(Gui.Control.activeDialog())


def panel():
    return hs.hole_panel()


def msg():
    return hs.message(panel())


def boss(height):
    return math.pi * BOSS_R * BOSS_R * height


def broken():
    return [o.Label for o in doc().Objects if "Invalid" in o.State or "Error" in o.State]


def part_ok(where):
    h.check("%s: nothing in error" % where, not broken(), broken())
    h.check("%s: valid solid" % where, h.body().Shape.isValid())
    tip = h.body().Tip
    h.check("%s: the part is shown" % where, tip is not None and tip.ViewObject.isVisible())


def slow(fn, ms=4000):
    fn.wait_ms = ms  # a modeled thread takes a moment: a person waits for the busy cursor
    return fn


def to_helpers():
    from sciforge import hole

    return [o for o in doc().Objects if hole.is_to_helper(o)]


# -- Path 16: Extents To follows its face -------------------------------------------------------
def p16_h():
    s["v"] = h.solid_volume()
    h.check("box with boss", hs.close(s["v"], hs.BOX + boss(8)), s["v"])
    h.press("h")


def p16_click_boss():
    h.fit()
    h.click(V(22, 17, 18))


def p16_to():
    p = panel()
    h.check("P16 a preview on the boss", p is not None and p.target is not None, msg())
    if p is None:
        return
    hs.type_into(p.pos_x.widget, "20")
    hs.type_into(p.pos_y.widget, "15")
    hs.type_into(p.diameter.widget, "5")
    b.choose(p.drill_point, "Flat")
    b.choose(p.extent, "To")


def p16_waits():
    p = panel()
    h.check("P16 To: the object box takes the clicks", p and p.fields["to"].button.isChecked())
    h.check("P16 no warning while it waits", "⚠" not in msg(), msg())
    h.click(V(35, 25, 10))  # the box's top face, beside the boss


def p16_picked():
    p = panel()
    h.check("P16 the box's top is the To face", p is not None and p.options.get("to"), msg())
    h.check(
        "P16 depth worked out: 8",
        p is not None and p.target is not None and abs(p.target.Depth.Value - 8) < 1e-6,
        p and p.target and p.target.Depth,
    )
    v = h.solid_volume()
    expect = s["v"] - hs.cylinder(5, 8)
    h.check("P16 the hole ends on the box's top", hs.close(v, expect), (v, expect))
    h.shot("p16-to")
    h.task_button("OK")


def p16_taller():
    h.check("P16 closed", not dialog_open())
    h.check("P16 one helper follows the face", len(to_helpers()) == 1, to_helpers())
    titles = hs.timeline_titles()
    h.check("P16 the helper is no timeline step", not any("To" in t for t in titles), titles)
    labels = ti.labels()
    h.check("P16 nor a browser row", not any(" To" in x for x in labels), labels)
    b.timeline_double_click("Extrude 2", click_first=True)


def p16_type_12():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    h.check("P16 editing the boss", p is not None and p.editing and not p._closed)
    if p:
        hs.type_into(p.distance.widget, "12")


def p16_ok():
    h.task_button("OK")


def p16_followed():
    v = h.solid_volume()
    expect = hs.BOX + boss(12) - hs.cylinder(5, 12)
    h.check("P16 the hole still ends on the box's top (12 deep)", hs.close(v, expect), (v, expect))
    hl = hs.holes()
    h.check("P16 its depth followed", hl and abs(hl[0].Depth.Value - 12) < 1e-6, hl and hl[0].Depth)
    part_ok("P16")
    s["v"] = v
    b.timeline_double_click("Hole 1", click_first=True)


def p16_edit():
    p = panel()
    h.check("P16 editing Hole 1", p is not None and p.editing)
    if p is None:
        return
    h.check("P16 Extents To shown", p.extent.currentText() == "To", p.extent.currentText())
    text = p.fields["to"].button.text()
    h.check("P16 with its face", text.startswith("Face"), text)
    h.check("P16 the depth shows 12", abs(p.depth.value() - 12) < 1e-6, p.depth.value())
    h.check("P16 and cannot be typed (To works it out)", not p.depth.widget.isEnabled())
    h.task_button("Cancel")


def p16_save():
    h.check("P16 Cancel kept it", hs.close(h.solid_volume(), s["v"]), h.solid_volume())
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-hole-qa-more-"), "hole_qa_more.FCStd")
    s["path"] = path
    doc().saveAs(path)
    App.closeDocument(doc().Name)


def p16_open():
    App.openDocument(s["path"])
    h.fit()


def p16_reopened():
    h.check("P16 reopened: same part", hs.close(h.solid_volume(), s["v"]), h.solid_volume())
    h.check("P16 the helper is back", len(to_helpers()) == 1, to_helpers())
    part_ok("P16 reopened")
    b.timeline_double_click("Extrude 2", click_first=True)


def p16_type_6():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    h.check("P16 editing the boss after reopening", p is not None and p.editing and not p._closed)
    if p:
        hs.type_into(p.distance.widget, "6")


def p16_ok2():
    h.task_button("OK")


def p16_followed_again():
    v = h.solid_volume()
    expect = hs.BOX + boss(6) - hs.cylinder(5, 6)
    h.check("P16 after reopening it still follows (6 deep)", hs.close(v, expect), (v, expect))
    part_ok("P16 after the second edit")
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def p16_undone():
    h.check("P16 Ctrl+Z: 12 deep again", hs.close(h.solid_volume(), s["v"]), h.solid_volume())
    part_ok("P16 after undo")


# -- Path 17: From Sketch, beginner -------------------------------------------------------------
Q1 = V(5, 5, 10)
Q2 = V(35, 5, 10)


def p17_sketch():
    h.fit()
    h.ribbon("Create Sketch")


def p17_top():
    h.click(V(36, 26, 10))


def p17_draw():
    sk = h.in_sketch()
    h.check("P17 sketch on the top face", sk is not None)
    if sk is None:
        return
    s["sketch"] = sk.Name
    for q in (Q1, Q2):
        x, y = h.to_sketch(sk, q)
        sk.addGeometry(Part.Point(V(x, y, 0)))
    a = h.to_sketch(sk, V(30, 27, 10))
    c = h.to_sketch(sk, V(36, 27, 10))
    sk.addGeometry(Part.LineSegment(V(a[0], a[1], 0), V(c[0], c[1], 0)))
    doc().recompute()


def p17_finish():
    h.ribbon("Finish Sketch")


def p17_h():
    Gui.Selection.clearSelection()
    s["holes"] = len(hs.holes())
    s["objects"] = len(doc().Objects)
    h.press("h")


def p17_from_sketch():
    p = panel()
    if p:
        b.choose(p.placement, "From Sketch (Multiple Holes)")


def p17_ok_nothing():
    h.task_button("OK")


def p17_refused():
    h.check("P17 OK with no point picked keeps the dialog", dialog_open() and panel() is not None)
    h.check("P17 it says to click points", "point" in msg().lower(), msg())
    h.fit()
    h.click(V(33, 27, 10))  # the sketch's line


def p17_line():
    p = panel()
    h.check("P17 a line makes no hole", p is not None and p.target is None)
    h.check("P17 and cannot be picked", not Gui.Selection.getSelectionEx())
    h.click(Q1)


def p17_one():
    p = panel()
    spots = hs.centres_all(p.target) if p and p.target else []
    h.check("P17 the first point: a hole", len(spots) == 1, (spots, msg()))
    h.click(Q2)


def p17_two():
    p = panel()
    spots = hs.centres_all(p.target) if p and p.target else []
    h.check("P17 the second point: two holes", len(spots) == 2, (spots, msg()))
    h.press(QtCore.Qt.Key_Escape)


def p17_esc():
    h.check("P17 Esc closed it", not dialog_open())
    h.check("P17 nothing made", len(hs.holes()) == s["holes"], hs.holes())
    h.check("P17 no object left", len(doc().Objects) == s["objects"], len(doc().Objects))
    sk = doc().getObject(s.get("sketch", ""))
    h.check("P17 the sketch is still shown (it was not used)", sk is not None and hs.visible(sk))
    h.check("P17 the part as it was", hs.close(h.solid_volume(), s["v"]), h.solid_volume())
    part_ok("P17 after Esc")
    if sk is not None:
        ti.click_row(sk.Label)


def p17_h_selected():
    h.press("h")


def p17_both():
    p = panel()
    spots = hs.centres_all(p.target) if p and p.target else []
    h.check("P17 the selected sketch: both points at once", len(spots) == 2, (spots, msg()))
    if p:
        b.choose(p.extent, "Distance")
        hs.type_into(p.diameter.widget, "3")
        hs.type_into(p.depth.widget, "4")


def p17_enter():
    h.click_empty()
    h.press(QtCore.Qt.Key_Return)


def p17_done():
    h.check("P17 Enter over the view finished it", not dialog_open())
    v = h.solid_volume()
    expect = s["v"] - 2 * hs.cylinder(3, 4)
    h.check("P17 two holes d3 x 4", hs.close(v, expect), (v, expect))
    sk = doc().getObject(s.get("sketch", ""))
    h.check("P17 the used sketch is hidden", sk is not None and not hs.visible(sk))
    part_ok("P17")
    s["v"] = v


# -- Path 18: H again while the dialog is open ------------------------------------------------
def p18_h():
    s["holes"] = len(hs.holes())
    h.press("h")


def p18_click():
    h.fit()
    h.click(V(36, 10, 10))


def p18_h_again():
    p = panel()
    h.check("P18 a preview", p is not None and p.target is not None, msg())
    s["first"] = p
    h.press("h")


def p18_fresh():
    p = panel()
    h.check("P18 a new Hole dialog", p is not None and p is not s.get("first"))
    h.check("P18 it starts with nothing placed", p is not None and p.target is None)
    h.check("P18 the first hole was kept", len(hs.holes()) == s["holes"] + 1, hs.holes())
    h.press(QtCore.Qt.Key_Escape)


def p18_done():
    h.check("P18 Esc closed the second one", not dialog_open())
    h.check("P18 one hole more", len(hs.holes()) == s["holes"] + 1, hs.holes())
    v = h.solid_volume()
    expect = s["v"] - hs.cylinder(3, 4)
    last = hs.holes()[-1] if hs.holes() else None
    detail = last and (
        last.Diameter.Value,
        last.Depth.Value,
        last.DrillPoint,
        hs.centre_of(last),
        last.HoleCutType,
        last.ThreadType,
    )
    h.check("P18 it has the last settings: d3 x 4", hs.close(v, expect), (v, expect, detail))
    part_ok("P18")
    s["v"] = v


# -- Path 19: OK while a modeled tapped hole is computed ------------------------------------------
def p19_h():
    s["holes"] = len(hs.holes())
    h.press("h")


def p19_click():
    h.fit()
    h.click(V(34, 25, 10))


def p19_tapped():
    p = panel()
    h.check("P19 a preview", p is not None and p.target is not None, msg())
    if p:
        b.choose(p.extent, "All")
        hs.type_into(p.diameter.widget, "5")
        b.choose(p.tap_type, "Tapped")


def p19_modeled_ok():
    p = panel()
    h.check(
        "P19 M6x1 from the d5 hole",
        p is not None and p.designation.currentText() == "M6x1",
        p and p.designation.currentText(),
    )
    if p:
        hs.click_checkbox(p.modeled)
        QtTest.QTest.qWait(80)  # the preview starts (60 ms)...
        h.task_button("OK")  # ... and OK comes while FreeCAD is still cutting the thread


p19_modeled_ok.wait_ms = 5000


def p19_after():
    if dialog_open():
        # OK said to wait: press it again now that the preview is there.
        h.task_button("OK")


p19_after.wait_ms = 3000


def p19_done():
    h.check("P19 the hole was made", not dialog_open() and len(hs.holes()) == s["holes"] + 1)
    hl = hs.holes()
    h.check("P19 modeled", hl and hl[-1].ModelThread and hl[-1].Threaded)
    v = h.solid_volume()
    lo, hi = s["v"] - hs.cylinder(6, 10), s["v"] - hs.cylinder(5, 10)
    h.check("P19 the thread is cut (between the drill and the major diameter)", lo < v < hi, v)
    part_ok("P19")
    s["v"] = v


# -- Path 20: OK / Cancel in the marking menu ---------------------------------------------------
def open_menu():
    from sciforge import marking_menu

    marking_menu._last_menu["widget"] = None
    gl = h.gl_widget()
    w.click(gl, QtCore.QPoint(gl.width() - 140, 140), button=QtCore.Qt.RightButton)
    menu = marking_menu._last_menu["widget"]
    h.check("P20 right click opens the marking menu", menu is not None and menu.isVisible())
    return menu


def p20_h():
    s["holes"] = len(hs.holes())
    h.press("h")


def p20_click():
    h.fit()
    h.click(V(10, 15, 10))


def p20_menu_ok():
    p = panel()
    h.check("P20 a preview", p is not None and p.target is not None, msg())
    if p:
        b.choose(p.tap_type, "Simple")
        b.choose(p.extent, "Distance")
        hs.type_into(p.pos_x.widget, "10")
        hs.type_into(p.pos_y.widget, "15")
        hs.type_into(p.diameter.widget, "3")
        hs.type_into(p.depth.widget, "4")


def p20_ok():
    menu = open_menu()
    if menu is None:
        return
    h.check("P20 the right slot (3 o'clock) is OK", menu.slots[2].text() == "OK", menu.slots[2].text())
    w.click(menu.slots[2])


def p20_kept():
    h.check("P20 OK in the marking menu finished the hole", not dialog_open())
    h.check("P20 one hole more", len(hs.holes()) == s["holes"] + 1, hs.holes())
    v = h.solid_volume()
    expect = s["v"] - hs.cylinder(3, 4)
    h.check("P20 d3 x 4", hs.close(v, expect), (v, expect))
    s["v"] = v
    h.press("h")


def p20_click2():
    h.fit()
    h.click(V(30, 15, 10))


def p20_cancel():
    p = panel()
    h.check("P20 a second preview", p is not None and p.target is not None, msg())
    menu = open_menu()
    if menu is None:
        return
    for i in range(menu.list.count()):
        row = menu.list.item(i)
        if row.text().split("    ")[0] == "Cancel":
            w.click(menu.list.viewport(), menu.list.visualItemRect(row).center())
            return
    h.check("P20 the list has Cancel", False)


def p20_cancelled():
    h.check("P20 Cancel in the marking menu closed it", not dialog_open())
    h.check("P20 no hole added", len(hs.holes()) == s["holes"] + 1, hs.holes())
    h.check("P20 the part as it was", hs.close(h.solid_volume(), s["v"]), h.solid_volume())
    part_ok("P20")


# -- Path 21: Suppress / Unsuppress -------------------------------------------------------------
def suppressed_titles():
    return sorted(t for t, (_state, _status, off) in ti.states().items() if off)


def p21_suppress():
    ti.menu("Hole 3", "Suppress Features")


def p21_suppressed():
    v = h.solid_volume()
    expect = s["v"] + hs.cylinder(3, 4)
    h.check(
        "P21 Hole 3 suppressed: only its material is back (the later holes stay)",
        hs.close(v, expect),
        (v, expect, suppressed_titles()),
    )
    h.check("P21 nothing else went off", suppressed_titles() == ["Hole 3"], suppressed_titles())
    h.check("P21 its sketch stays hidden", all(not hs.visible(x) for x in hs.helper_sketches()))
    part_ok("P21 Hole 3 off")
    ti.menu("Hole 3", "Unsuppress Features")


def p21_back():
    h.check("P21 unsuppressed", hs.close(h.solid_volume(), s["v"]), h.solid_volume())
    part_ok("P21 Hole 3 on")
    ti.menu("Hole 1", "Suppress Features")


def p21_hole1():
    v = h.solid_volume()
    h.check("P21 Hole 1 (with its To helper) off: material back", v > s["v"] + 200, v)
    part_ok("P21 Hole 1 off")
    ti.menu("Hole 1", "Unsuppress Features")


def p21_hole1_back():
    h.check("P21 Hole 1 back", hs.close(h.solid_volume(), s["v"]), h.solid_volume())
    part_ok("P21")
    h.check("P21 no kernel errors in the Report view", not b.report_has_kernel_errors())
    hs.no_popups("Hole QA (more)")
    h.shot("p21-end")


h.run(
    "hole_qa_more",
    ti.watched(
        b.box_steps("HoleQAMore")
        + hs.make_boss("boss", radius=BOSS_R, height=8.0, at=(20.0, 15.0))
        + [
            p16_h,
            p16_click_boss,
            p16_to,
            p16_waits,
            p16_picked,
            p16_taller,
            p16_type_12,
            p16_ok,
            p16_followed,
            p16_edit,
            p16_save,
            p16_open,
            p16_reopened,
            p16_type_6,
            p16_ok2,
            p16_followed_again,
            p16_undone,
            p17_sketch,
            p17_top,
            p17_draw,
            p17_finish,
            p17_h,
            p17_from_sketch,
            p17_ok_nothing,
            p17_refused,
            p17_line,
            p17_one,
            p17_two,
            p17_esc,
            p17_h_selected,
            p17_both,
            p17_enter,
            p17_done,
            p18_h,
            p18_click,
            p18_h_again,
            p18_fresh,
            p18_done,
            p19_h,
            p19_click,
            p19_tapped,
            p19_modeled_ok,
            p19_after,
            p19_done,
            p20_h,
            slow(p20_click),
            p20_menu_ok,
            p20_ok,
            p20_kept,
            p20_click2,
            p20_cancel,
            p20_cancelled,
            p21_suppress,
            p21_suppressed,
            p21_back,
            p21_hole1,
            p21_hole1_back,
        ]
    ),
)
