# SPDX-License-Identifier: LGPL-2.1-or-later
"""More ways Fusion users run Revolve (QA, only real input).

A shaft: Create Sketch on XZ, R, a 10 x 20 rectangle from the origin, Finish, Revolve
about the Z axis, OK (r 10, h 20). A second sketch on XZ, a 4 x 6 rectangle hanging below
the origin (x 0..4, z -6..0), Finish (unused).

Path 11, Revolve from inside an older sketch: double-click Sketch 1 (the shaft's, already
         used) in the timeline, then Revolve from the SOLID tab: the sketch is finished and
         the area of the sketch you were in is taken (Fusion), not the newest unused one.
         Esc.
Path 12, two designs open: a second design with a block. Back in the first, Revolve (the
         unused area is taken), then a click on the other design's block: nothing is taken
         from it; back in the first design, the Z axis, OK. The other design is unchanged.
Path 13, the marking menu while Revolve is open: right click, OK keeps the revolve. Delete
         with the dialog open deletes nothing.
Path 14, the timeline marker rolled back: drag the marker before Revolve 2, revolve a new
         sketch, then drag the marker to the end: the new revolve sits before Revolve 2 and
         both are in the part.
Path 15, a construction line drawn in the profile's own sketch (X, then L) as the axis:
         it is drawn dashed to click; Symmetric with "45 deg" typed (a unit in the field).
         The ring does not touch the part: a New Body (Fusion's rule for a Join apart).
Path 16, editing: clear the axis with its x, OK: the dialog stays open and says why; Esc:
         the revolve is unchanged.
"""
import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore
from PySide6 import QtTest

from SciForgeTests.gui import arrow_input as arrows
from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import revolve_input as ri
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import timeline_input as ti
from SciForgeTests.gui import widget_input as w

V = App.Vector
PI = math.pi
SHAFT = 2000.0 * PI
Z_AXIS = (V(0, 0, 0), V(0, 0, 1))
s = {}


def doc():
    return App.ActiveDocument


def main_doc():
    return App.getDocument(s["doc"])


def panel():
    return ri.panel()


def msg():
    p = panel()
    return p.message.text() if p is not None else ""


def dialog_open():
    return bool(Gui.Control.activeDialog())


def near(a, c, tol=1e-6):
    return ri.near(a, c, tol)


def esc():
    h.press(QtCore.Qt.Key_Escape)


def vol():
    return h.solid_volume()


def total():
    """Volume of every body (a revolve that does not touch the part is a New Body)."""
    return sum(
        o.Shape.Volume
        for o in App.ActiveDocument.Objects
        if o.TypeId == "PartDesign::Body" and not o.Shape.isNull() and o.Shape.Solids
    )


def main_vol():
    body = main_doc().getObject(s["body"])
    return body.Shape.Volume if body is not None and not body.Shape.isNull() else 0.0


def invalid(document=None):
    return [o.Label for o in (document or doc()).Objects if "Invalid" in o.State]


def sketch_click(point):
    si.click(point, approach=V(1.0, 0, 0.6))


def solid_tab():
    from sciforge import shell

    QtTest.QTest.mouseClick(shell.ribbon().tab_buttons["solid"], QtCore.Qt.LeftButton)
    QtCore.QCoreApplication.processEvents()


def area_volume(sketch, angle=360.0):
    areas = ri.regions(sketch)
    return ri.pappus(areas[0][1], *Z_AXIS, angle=angle) if len(areas) == 1 else 0.0


# == the shaft and an unused sketch ===============================================================
def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("RevolveQAMore")
    s["doc"] = doc().Name
    h.fit()
    h.ribbon("Create Sketch")


def shaft_plane():
    h.click(V(12, 0, 8))


def shaft_rect():
    s["sk1"] = h.in_sketch()
    h.check("sketch 1 on XZ", s["sk1"] is not None)
    h.press("r")


def shaft_corner():
    sketch_click(V(0, 0, 0))


def shaft_size():
    si.move_towards(V(8, 0, 16), V(0.45, 0, 0.9))
    si.type_text("10", enter=False)
    si.tab()
    si.type_text("20")


def shaft_finish():
    esc()
    h.ribbon("Finish Sketch")


def shaft_revolve():
    h.fit()
    h.ribbon("Revolve")


def shaft_axis():
    h.fit()
    h.click(V(0, 0, 32))


def shaft_ok():
    h.check("shaft preview", near(vol(), SHAFT), vol())
    h.task_button("OK")


def sketch2():
    h.check("shaft made", not dialog_open() and near(vol(), SHAFT), vol())
    s["body"] = h.body().Name
    h.fit()
    h.click_empty()
    h.ribbon("Create Sketch")


def sketch2_plane():
    h.click(V(11, 0, -9))  # the XZ square beside the shaft


def sketch2_rect():
    s["sk2"] = h.in_sketch()
    h.check("sketch 2 open", s["sk2"] is not None and s["sk2"] is not s["sk1"])
    h.press("r")


def sketch2_corner():
    sketch_click(V(0, 0, 0))


def sketch2_size():
    si.move_towards(V(3, 0, -5), V(0.45, 0, -0.9))
    si.type_text("4", enter=False)
    si.tab()
    si.type_text("6")


def sketch2_finish():
    esc()
    h.ribbon("Finish Sketch")


# == Path 11: Revolve from inside an older sketch ==================================================
def p11_edit_sketch1():
    areas = ri.regions(s["sk2"])
    h.check("sketch 2: one area below the shaft", len(areas) == 1, areas)
    s["boss"] = area_volume(s["sk2"])
    b.timeline_double_click("Sketch 1", click_first=True)


def p11_solid_tab():
    h.check("P11 editing Sketch 1", h.in_sketch() is s["sk1"], h.in_sketch())
    solid_tab()


def p11_revolve():
    h.ribbon("Revolve")


def p11_open():
    p = panel()
    h.check("P11 Revolve opens", p is not None)
    h.check("P11 the sketch is finished", h.in_sketch() is None)
    if p is not None:
        h.check(
            "P11 the area of the sketch you were in is taken (Fusion)",
            len(p.profiles) == 1 and p.profiles[0][0] is s["sk1"],
            p.profiles,
        )
    esc()


def p11_closed():
    h.check("P11 Esc closes", not dialog_open())
    h.check("P11 the shaft is unchanged", near(vol(), SHAFT), vol())
    h.check("P11 Sketch 1 is hidden again (it is used)", not s["sk1"].ViewObject.Visibility)


# == Path 12: two designs ==========================================================================
def p12_other():
    App.newDocument("Other")
    s["other"] = doc().Name
    h.fit()
    h.ribbon("Create Sketch")


def p12_other_plane():
    h.click(V(12, -8, 0))


def p12_other_rect():
    h.press("r")


def p12_other_corner():
    si.click(V(0, 0, 0))


def p12_other_size():
    si.move_towards(V(8, 6, 0), V(0.8, 0.6, 0))
    si.type_text("20", enter=False)
    si.tab()
    si.type_text("15")


def p12_other_finish():
    esc()
    h.ribbon("Finish Sketch")


def p12_other_extrude():
    h.fit()
    h.press("e")


def p12_other_ok():
    arrows.type_distance("10")  # Extrude starts at 0 (Fusion): type the distance
    h.task_button("OK")


def p12_back():
    h.check("the other design's block", near(vol(), 20 * 15 * 10), vol())
    s["other_objects"] = len(doc().Objects)
    b.click_tab("RevolveQAMore")


def p12_revolve():
    h.check("back in the first design", doc().Name == s["doc"], doc().Name)
    h.fit()
    h.ribbon("Revolve")


def p12_to_other():
    p = panel()
    h.check("P12 the unused area is taken", p is not None and len(p.profiles) == 1)
    b.click_tab("Other")


def p12_click_other():
    h.check("P12 the other design is shown", doc().Name == s["other"], doc().Name)
    h.fit()
    h.click(V(10, 7, 10))  # the other design's block


def p12_not_taken():
    p = panel()
    h.check("P12 the dialog is still open", p is not None)
    if p is not None:
        h.check(
            "P12 nothing of the other design is taken",
            all(o.Document.Name == s["doc"] for o, _ in p.profiles)
            and (p.axis is None or p.axis[0].Document.Name == s["doc"]),
            (p.profiles, p.axis),
        )
        h.check("P12 still one area", len(p.profiles) == 1, p.profiles)
    b.click_tab("RevolveQAMore")


def p12_axis():
    h.check("P12 back in the first design", doc().Name == s["doc"], doc().Name)
    h.fit()
    h.click(V(0, 0, 32))


def p12_ok():
    p = panel()
    h.check("P12 the Z axis", p is not None and p.axis is not None and p.axis[0].Role == "Z_Axis")
    h.task_button("OK")


def p12_done():
    want = SHAFT + s["boss"]
    h.check("P12 the boss is added", near(main_vol(), want), (main_vol(), want))
    other = App.getDocument(s["other"])
    h.check(
        "P12 the other design is unchanged",
        len(other.Objects) == s["other_objects"] and not invalid(other),
        len(other.Objects),
    )
    h.check("P12 nothing broken", not invalid(main_doc()), invalid(main_doc()))
    App.closeDocument(s["other"])


# == Path 13: the marking menu's OK; Delete deletes nothing ========================================
def open_menu():
    from sciforge import marking_menu

    marking_menu._last_menu["widget"] = None
    gl = h.gl_widget()
    w.click(gl, QtCore.QPoint(gl.width() - 140, 140), button=QtCore.Qt.RightButton)
    menu = marking_menu._last_menu["widget"]
    h.check("right click opens the marking menu", menu is not None and menu.isVisible())
    return menu


def p13_sketch():
    App.setActiveDocument(s["doc"])
    h.check("P13 in the first design", doc().Name == s["doc"])
    s["v13"] = vol()
    h.fit()
    h.click_empty()
    h.ribbon("Create Sketch")


def p13_plane():
    h.fit()
    h.click(V(14, 0, -14))  # the XZ square below and beside the part


def p13_rect():
    s["sk3"] = h.in_sketch()
    h.check("P13 sketch 3 open", s["sk3"] is not None)
    h.press("r")


def p13_corner():
    sketch_click(V(12, 0, 0))


def p13_size():
    si.move_towards(V(15, 0, 3), V(0.7, 0, 0.7))
    si.type_text("4", enter=False)
    si.tab()
    si.type_text("4")


def p13_finish():
    esc()
    h.ribbon("Finish Sketch")


def p13_revolve():
    areas = ri.regions(s["sk3"])
    h.check("P13 one area", len(areas) == 1, areas)
    s["ring"] = area_volume(s["sk3"])
    h.fit()
    h.ribbon("Revolve")


def p13_axis():
    h.fit()
    h.click(V(0, 0, 32))


def p13_cut():
    p = panel()
    h.check("P13 a preview", p is not None and p.target is not None, msg())
    h.check(
        "P13 a ring beside the shaft: Join", p is not None and p.operation.currentText() == "Join"
    )
    if p is not None:
        b.choose(p.operation, "Cut")


def p13_cut_ok():
    h.check(
        "P13 a cut that misses the part is explained",
        "does not touch" in msg(),
        msg(),
    )
    h.task_button("OK")


def p13_cut_refused():
    h.check("P13 OK waits while the cut misses the part", dialog_open() and panel() is not None)
    p = panel()
    if p is not None:
        b.choose(p.operation, "Join")


def p13_delete():
    p = panel()
    h.check("P13 Join again: no warning", "⚠" not in msg(), msg())
    s["objects"] = len(doc().Objects)
    b.press_guarded(QtCore.Qt.Key_Delete)


def p13_menu():
    h.check("P13 Delete deleted nothing", len(doc().Objects) == s["objects"], len(doc().Objects))
    h.check("P13 the dialog is still open", panel() is not None)
    h.check("P13 no pop-up", not b.POPUPS, b.POPUPS)
    menu = open_menu()
    if menu is None:
        return
    h.check(
        "P13 the right slot (3 o'clock) is OK", menu.slots[2].text() == "OK", menu.slots[2].text()
    )
    w.click(menu.slots[2])


def p13_done():
    h.check("P13 OK from the marking menu closes the dialog", not dialog_open())
    want = s["v13"] + s["ring"]
    h.check("P13 the ring is kept", near(vol(), want), (vol(), want))
    s["v13"] = vol()


# == Path 14: the timeline marker rolled back ======================================================
def p14_roll():
    titles = ti.titles()
    h.check("P14 three revolves in the timeline", "Revolve 3" in titles, titles)
    ti.drag_marker(before_title="Revolve 2")


def p14_rolled():
    want = SHAFT
    h.check("P14 rolled back: only the shaft", near(vol(), want), (vol(), want))
    h.fit()
    h.click_empty()
    h.ribbon("Create Sketch")


def p14_plane():
    h.fit()
    h.click(V(11, 0, -9))  # the XZ square beside the shaft (the squares fit the shaft now)


def p14_rect():
    s["sk4"] = h.in_sketch()
    h.check("P14 sketch 4 open", s["sk4"] is not None)
    h.press("r")


def p14_corner():
    sketch_click(V(0, 0, 20))


def p14_size():
    si.move_towards(V(2, 0, 23), V(0.6, 0, 0.8))
    si.type_text("3", enter=False)
    si.tab()
    si.type_text("5")


def p14_finish():
    esc()
    h.ribbon("Finish Sketch")


def p14_revolve():
    areas = ri.regions(s["sk4"])
    h.check("P14 one area on top of the shaft", len(areas) == 1, areas)
    s["top"] = area_volume(s["sk4"])
    h.fit()
    h.ribbon("Revolve")


def p14_axis():
    h.fit()
    h.click(V(0, 0, 38))


def p14_ok():
    p = panel()
    h.check("P14 Join on top", p is not None and p.operation.currentText() == "Join")
    want = SHAFT + s["top"]
    h.check("P14 preview at the marker", near(vol(), want), (vol(), want))
    h.task_button("OK")


def p14_to_end():
    titles = ti.titles()
    revolves = [t for t in titles if t.startswith("Revolve")]
    h.check("P14 four revolves", len(revolves) == 4, titles)
    if len(revolves) == 4:
        h.check(
            "P14 the new one sits before Revolve 2 (at the marker)",
            titles.index(revolves[1]) < titles.index("Revolve 2")
            and revolves[1] not in ("Revolve 2", "Revolve 3"),
            titles,
        )
    ti.drag_marker(to_end=True)


def p14_end():
    want = s["v13"] + s["top"]
    h.check("P14 rolled to the end: everything", near(vol(), want), (vol(), want))
    h.check("P14 nothing broken", not invalid(), invalid())
    s["v14"] = vol()


# == Path 15: a construction line of the profile's own sketch, Symmetric, a unit typed ==========
def p15_sketch():
    h.fit()
    h.click_empty()
    h.ribbon("Create Sketch")


def p15_plane():
    h.fit()
    h.click(V(16, 0, -18))  # the XZ square, below and beside the part


def p15_rect():
    s["sk5"] = h.in_sketch()
    h.check("P15 sketch 5 open", s["sk5"] is not None)
    if s["sk5"] is not None:
        support = s["sk5"].AttachmentSupport
        h.check(
            "P15 sketch 5 on XZ",
            support and getattr(support[0][0], "Role", "") == "XZ_Plane",
            [(o.Name, sub) for o, sub in support],
        )
    h.press("r")


def p15_corner():
    sketch_click(V(12, 0, -16))


def p15_size():
    si.move_towards(V(15, 0, -19), V(0.7, 0, -0.7))
    si.type_text("4", enter=False)
    si.tab()
    si.type_text("4")


def p15_construction():
    esc()
    h.press("x")  # construction mode (Fusion's X with nothing selected)


def p15_line():
    h.press("l")


def p15_line_a():
    sketch_click(V(24, 0, -16))


def p15_line_b():
    sketch_click(V(24, 0, -22))


def p15_finish():
    esc()
    esc()
    h.ribbon("Finish Sketch")


def p15_revolve():
    from sciforge import revolve

    lines = revolve.construction_lines(s["sk5"])
    h.check("P15 one construction line", len(lines) == 1, lines)
    areas = ri.regions(s["sk5"])
    h.check("P15 one area (the construction line is not an outline)", len(areas) == 1, areas)
    if lines and areas:
        _n, a, c = lines[0]
        g = s["sk5"].getGlobalPlacement()
        s["axis5"] = (g.multVec(a), g.multVec(c) - g.multVec(a))
        s["ring5"] = ri.pappus(areas[0][1], *s["axis5"])
    h.fit()
    h.ribbon("Revolve")


def p15_dashed():
    p = panel()
    h.check("P15 the area is taken", p is not None and len(p.profiles) == 1)
    if p is None:
        return
    dashed = [l for l in p.axes.lines if l[1] == "construction" and l[0][0] is s["sk5"]]
    h.check("P15 the construction line is drawn to click", len(dashed) == 1, p.axes.lines)
    h.fit()
    h.shot("p15-dashed")
    if dashed:
        h.click((dashed[0][2] + dashed[0][3]) * 0.5)


def p15_symmetric():
    p = panel()
    if p is None:
        return
    h.check(
        "P15 the construction line is the axis",
        p.axis is not None and p.axis[0] is s["sk5"] and p.axis[1].startswith("Axis"),
        p.axis and (p.axis[0].Name, p.axis[1]),
    )
    want = s["v14"] + s["ring5"]
    # The ring does not touch the part: a New Body (Fusion), so every body is counted.
    h.check("P15 a full ring", near(total(), want), (total(), want))
    b.choose(p.direction, "Symmetric")
    ui.type_into(p.angle.widget, "45 deg")


def p15_typed():
    p = panel()
    h.check("P15 '45 deg' is 45", p is not None and near(p.angle.value(), 45.0), p.angle.value())
    want = s["v14"] + s["ring5"] / 4.0
    h.check("P15 symmetric 45 each way: a quarter ring", near(total(), want), (total(), want))
    h.check("P15 no warning", "⚠" not in msg(), msg())
    h.shot("p15-construction")
    h.task_button("OK")


def p15_done():
    want = s["v14"] + s["ring5"] / 4.0
    h.check("P15 kept", not dialog_open() and near(total(), want), (total(), want))
    s["v15"] = total()


# == Path 16: editing, the axis cleared, OK refused, Esc ===========================================
def p16_edit():
    titles = [t for t in ti.titles() if t.startswith("Revolve")]
    s["t16"] = titles[-1] if titles else "Revolve 5"
    b.timeline_double_click(s["t16"], click_first=True)


def p16_clear():
    p = panel()
    h.check("P16 editing", p is not None and p.editing)
    if p is None:
        return
    h.check("P16 Symmetric is shown", p.direction.currentText() == "Symmetric")
    h.check("P16 45 is shown", near(p.angle.value(), 45.0), p.angle.value())
    w.click(p.fields["axis"].clear)


def p16_ok():
    p = panel()
    h.check("P16 the axis is cleared", p is not None and p.axis is None)
    h.task_button("OK")


def p16_refused():
    h.check("P16 OK without an axis keeps the dialog open", dialog_open() and panel() is not None)
    h.check("P16 the dialog says why", "axis" in msg().lower(), msg())
    esc()


def p16_esc():
    h.check("P16 Esc closes", not dialog_open())
    h.check("P16 the revolve is unchanged", near(total(), s["v15"]), (total(), s["v15"]))
    h.check("P16 nothing broken", not invalid(), invalid())
    h.check("P16 the part is shown", ri.shown(h.body()))
    h.shot("p16-end")
    b.timeline_double_click("Revolve 1", click_first=True)


def p16_first_cut():
    p = panel()
    h.check("P16 editing the first revolve", p is not None and p.editing)
    if p is not None:
        b.choose(p.operation, "Cut")


def p16_first_cut_said():
    h.check("P16 a cut with no solid before it is explained", "no solid to cut" in msg(), msg())
    h.task_button("OK")


def p16_first_cut_refused():
    h.check("P16 OK waits", dialog_open() and panel() is not None)
    esc()


def p16_first_esc():
    h.check("P16 Esc closes", not dialog_open())
    h.check("P16 the part is unchanged", near(total(), s["v15"]), (total(), s["v15"]))
    h.check(
        "P16 the first revolve is a Revolution again",
        ri.revolves()[0].TypeId == "PartDesign::Revolution",
    )
    h.check("P16 nothing broken", not invalid(), invalid())


STEPS = [
    new_design,
    shaft_plane,
    shaft_rect,
    shaft_corner,
    shaft_size,
    shaft_finish,
    shaft_revolve,
    shaft_axis,
    shaft_ok,
    sketch2,
    sketch2_plane,
    sketch2_rect,
    sketch2_corner,
    sketch2_size,
    sketch2_finish,
    p11_edit_sketch1,
    p11_solid_tab,
    p11_revolve,
    p11_open,
    p11_closed,
    p12_other,
    p12_other_plane,
    p12_other_rect,
    p12_other_corner,
    p12_other_size,
    p12_other_finish,
    p12_other_extrude,
    p12_other_ok,
    p12_back,
    p12_revolve,
    p12_to_other,
    p12_click_other,
    p12_not_taken,
    p12_axis,
    p12_ok,
    p12_done,
    p13_sketch,
    p13_plane,
    p13_rect,
    p13_corner,
    p13_size,
    p13_finish,
    p13_revolve,
    p13_axis,
    p13_cut,
    p13_cut_ok,
    p13_cut_refused,
    p13_delete,
    p13_menu,
    p13_done,
    p14_roll,
    p14_rolled,
    p14_plane,
    p14_rect,
    p14_corner,
    p14_size,
    p14_finish,
    p14_revolve,
    p14_axis,
    p14_ok,
    p14_to_end,
    p14_end,
    p15_sketch,
    p15_plane,
    p15_rect,
    p15_corner,
    p15_size,
    p15_construction,
    p15_line,
    p15_line_a,
    p15_line_b,
    p15_finish,
    p15_revolve,
    p15_dashed,
    p15_symmetric,
    p15_typed,
    p15_done,
    p16_edit,
    p16_clear,
    p16_ok,
    p16_refused,
    p16_esc,
    p16_first_cut,
    p16_first_cut_said,
    p16_first_cut_refused,
    p16_first_esc,
]

h.run("revolve_qa_more", ti.watched(STEPS))
