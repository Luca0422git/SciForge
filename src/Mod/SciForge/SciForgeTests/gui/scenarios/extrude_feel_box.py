# SPDX-License-Identifier: LGPL-2.1-or-later
"""The value box next to the arrow of Extrude and Press Pull never covers the arrow's heads,
Esc in the box cancels the command, and a cut opened from the timeline shows its red at
once (review of Luca's R3 and R7). Only real input.

Box 40 x 30 x 10 (sketch, Finish, E, type 10, OK).
Press Pull  Q, click the right side face (x = 40), ViewCube FRONT: the arrow points right
            on the screen. Its + head is not under the value box (the window system says
            the 3D view is on top there) and a press on it drags the arrow (the press goes
            to whatever is on top, as with a real mouse). Type -3: red. Click the box,
            type 7, Esc: Press Pull is cancelled, nothing made, no box and no red left.
Extrude     corner view, E, click the same face, ViewCube FRONT: the same for its arrow.
            Click the box, type 0, Enter: Extrude stays open (0 makes nothing), says why,
            and the box keeps the keyboard. Esc: cancelled, nothing made, no box left.
Edit        a 10 x 10 square sketched on the top face, E, -6, OK (a pocket). Double-click
            "Extrude 2" in the timeline: the pocket shows in red at once. Esc: none left.
            Q, top face, -3, OK. Double-click "Press Pull 1": red at once; Esc: none left.
            Saved, closed and opened again: the same for "Press Pull 1" and "Extrude 2".
"""

import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore
from PySide6 import QtTest

from SciForgeTests.gui import arrow_input as a
from SciForgeTests.gui import blend_steps as bs
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import viewcube_input as vc

V = App.Vector
s = {}
BOX = 12000.0
POCKET = 10.0 * 10.0 * 6.0
SIDE = V(40, 15, 5)  # the middle of the right side face


def xpanel():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    return p if p is not None and not p._closed else None


def ppanel():
    from sciforge import presspull_ui

    p = presspull_ui.PressPullPanel.last
    return p if p is not None and not p._closed else None


def near(x, y, tol=1e-6):
    return abs(x - y) <= tol * max(1.0, abs(y))


def bound(box, lo, hi, tol=1e-3):
    return box is not None and all(
        abs(getattr(box, k) - v) <= tol
        for k, v in zip(("XMin", "YMin", "ZMin", "XMax", "YMax", "ZMax"), lo + hi)
    )


def press_pulls():
    from sciforge import presspull

    return [o for o in App.ActiveDocument.Objects if presspull.is_press_pull(o)]


def extrudes():
    from sciforge import extrude

    return [o for o in App.ActiveDocument.Objects if extrude.is_extrude(o)]


def close_if_open(what):
    """A check before failed and left the dialog open: Cancel it, so the next part runs."""
    if Gui.Control.activeDialog():
        print("[SciForge] extrude_feel_box: %s left the dialog open; Cancel" % what, flush=True)
        h.task_button("Cancel")


# -- the arrow points sideways on the screen: its heads stay grabbable ----------------------------
def head_pixels(dragger):
    """{reach: (pixel, widget on top there)} along the + head (the cone runs from 1 to 1.5
    arrow sizes from the middle; 1.25 is where a person aims)."""
    found = {}
    for reach in (1.05, 1.25, 1.45):
        pos = h.screen_point(a.arrow_point(dragger, reach))
        found[reach] = ((pos.x(), pos.y()), a.top_name(pos))
    return found


def clear_of_dialog(what, panel):
    """Like a person, pan the part to the left until its arrow is clear of the dialog that
    floats over the right of the view (the ViewCube's FRONT zooms in on the part)."""
    dragger = panel.dragger if panel is not None else None
    if not h.check("%s: an arrow" % what, dragger is not None):
        return

    def under_dialog():
        found = []
        for reach in (-1.5, -1.0, 0.0, 1.0, 1.25, 1.5, 1.7):
            pos = h.screen_point(a.arrow_point(dragger, reach))
            name = a.top_name(pos)
            if name not in ("3D view", a.BOX_NAME):
                found.append((reach, name))
        return found

    for _ in range(8):
        if not under_dialog():
            break
        h.pan(-120, 0)
    h.check("%s: the arrow is clear of the dialog" % what, not under_dialog(), under_dialog())


def check_heads(what, panel):
    """The box sits beside the sideways arrow, not over its + head."""
    dragger = panel.dragger
    if not h.check("%s: an arrow" % what, dragger is not None):
        return
    tail = h.screen_point(a.arrow_point(dragger, -1.5))
    tip = h.screen_point(a.arrow_point(dragger, 1.5))
    h.check(
        "%s: in the Front view the arrow points sideways" % what,
        abs(tip.x() - tail.x()) > 40 and abs(tip.y() - tail.y()) < 6,
        ((tail.x(), tail.y()), (tip.x(), tip.y())),
    )
    boxes = a.value_boxes(arrows_only=True)
    h.check("%s: one value box" % what, len(boxes) == 1, len(boxes))
    heads = head_pixels(dragger)
    h.check(
        "%s: the arrow's + head is not under the value box" % what,
        all(name == "3D view" for _pos, name in heads.values()),
        heads,
    )
    if boxes:
        ok, detail = a.box_near(boxes[0], dragger)
        h.check("%s: the box is still next to the arrow" % what, ok, detail)
        h.check(
            "%s: and shows the dialog's value" % what,
            boxes[0].text() == panel_field(panel).widget.text(),
            (boxes[0].text(), panel_field(panel).widget.text()),
        )


def panel_field(panel):
    return panel.distance if hasattr(panel, "distance") else panel.field


def grab_head(panel, key):
    """Press where a person grabs the + head (the press goes to whatever is on top there)
    and drag 60 px further along the arrow, the button held."""
    dragger = panel.dragger
    s[key + "_before"] = dragger.distance()
    start = h.screen_point(a.arrow_point(dragger, 1.25))
    tip = h.screen_point(a.arrow_point(dragger, 1.5))
    step = 1 if tip.x() >= start.x() else -1
    end = QtCore.QPoint(start.x() + 60 * step, start.y())
    s[key] = drag = a.HeldDrag(start, end, moves=20, every_ms=20, hold_ms=200)
    drag.run()


def grabbed(key, panel):
    drag = s.get(key)
    h.check("the held drag ran", drag is not None and drag.done, drag and drag.error)
    h.check(
        "the press on the + head reached the 3D view, not the box",
        drag is not None and drag.pressed_on == "3D view",
        drag and drag.pressed_on,
    )
    after = panel.dragger.distance() if panel and panel.dragger else None
    h.check(
        "grabbing the + head drags the arrow",
        after is not None and after > s[key + "_before"] + 0.5,
        (s[key + "_before"], after),
    )
    h.check("the box did not take the keyboard", a.focus_name() != a.BOX_NAME, a.focus_name())


def press_q():
    s["volume"] = h.solid_volume()
    h.check("box 40 x 30 x 10", near(s["volume"], BOX), s["volume"])
    h.press("q")


def click_side():
    h.click(SIDE)


def front_for_pp():
    p = ppanel()
    h.check(
        "Press Pull took the side face",
        p is not None and p.mode == "faces" and len(p.names) == 1,
        p and (p.mode, p.names, p.message.text()),
    )
    h.check("ViewCube FRONT", vc.click("front"))


def pp_pan():
    clear_of_dialog("Press Pull", ppanel())


def pp_heads():
    p = ppanel()
    if p is None:
        h.check("Press Pull open", False)
        return
    check_heads("Press Pull", p)
    h.shot("1-pp-front")
    grab_head(p, "pp_drag")


pp_heads.wait_ms = 20 * 20 + 200 + 1200


def pp_grabbed():
    p = ppanel()
    grabbed("pp_drag", p)
    h.check(
        "Press Pull: the field follows the drag",
        p is not None and p.field.value() > 0.5,
        p and p.field.value(),
    )
    h.shot("2-pp-dragged")
    ui.type_into(p.field.widget, "-3")


def pp_box_esc():
    p = ppanel()
    h.check("pushed 3 in: red", len(a.cut_nodes()) == 1, len(a.cut_nodes()))
    h.check(
        "pushed 3 in: 40 x 30 x 10 less 30 x 10 x 3",
        near(h.solid_volume(), BOX - 900.0),
        h.solid_volume(),
    )
    check_heads("Press Pull at -3", p)
    boxes = a.value_boxes(arrows_only=True)
    if not h.check("the value box is there", len(boxes) == 1, len(boxes)):
        return
    a.type_in_box(boxes[0], "7", enter=False)
    h.check("the box has the keyboard", boxes[0].hasFocus(), a.focus_name())
    h.check("7 is typed in it", boxes[0].text() == "7", boxes[0].text())
    QtTest.QTest.keyClick(boxes[0], QtCore.Qt.Key_Escape)


pp_box_esc.wait_ms = 1200


def pp_cancelled():
    h.check(
        "Esc in the value box cancels Press Pull",
        ppanel() is None and not Gui.Control.activeDialog(),
    )
    h.check("nothing made: no Press Pull step", not press_pulls(), [o.Name for o in press_pulls()])
    h.check("the part is as before", near(h.solid_volume(), s["volume"]), h.solid_volume())
    h.check(
        "no value box left",
        not a.value_boxes(visible_only=False),
        [(b.text(), b.isVisible()) for b in a.value_boxes(visible_only=False)],
    )
    h.check("no red left", not a.cut_nodes(), len(a.cut_nodes()))
    close_if_open("Esc in the Press Pull box")


# -- the same for Extrude -------------------------------------------------------------------------
def press_e():
    h.fit()
    h.press("e")


def click_side_e():
    h.click(SIDE)


def front_for_e():
    p = xpanel()
    h.check("Extrude took the side face", p is not None and len(p.profiles) == 1, p and p.profiles)
    h.check("ViewCube FRONT", vc.click("front"))


def e_pan():
    clear_of_dialog("Extrude", xpanel())


def e_heads():
    p = xpanel()
    if p is None:
        h.check("Extrude open", False)
        return
    check_heads("Extrude", p)
    h.shot("3-e-front")
    grab_head(p, "e_drag")


e_heads.wait_ms = 20 * 20 + 200 + 1200


def e_grabbed():
    p = xpanel()
    grabbed("e_drag", p)
    h.check(
        "Extrude: the distance follows the drag",
        p is not None and p.distance.value() > 0.5,
        p and p.distance.value(),
    )
    h.check("Extrude: the preview grew", h.solid_volume() > s["volume"] + 1.0, h.solid_volume())


def e_box_zero_enter():
    """The trap found in review: 0 and Enter in the box keep Extrude open (a distance of 0
    makes nothing) and the box keeps the keyboard; Esc must still cancel then."""
    boxes = a.value_boxes(arrows_only=True)
    if not h.check("the value box is there", len(boxes) == 1, len(boxes)):
        return
    a.type_in_box(boxes[0], "0", enter=True)


e_box_zero_enter.wait_ms = 1000


def e_box_esc():
    p = xpanel()
    h.check("0 + Enter in the box keeps Extrude open", p is not None)
    if p is not None:
        h.check("and it says why", "zero" in p.message.text(), p.message.text())
    boxes = a.value_boxes(arrows_only=True)
    if not h.check("the value box is there", len(boxes) == 1, len(boxes)):
        return
    h.check("the box still has the keyboard", boxes[0].hasFocus(), a.focus_name())
    QtTest.QTest.keyClick(boxes[0], QtCore.Qt.Key_Escape)


e_box_esc.wait_ms = 1200


def e_cancelled():
    h.check(
        "Esc in the value box cancels Extrude", xpanel() is None and not Gui.Control.activeDialog()
    )
    h.check(
        "nothing made: one extrude (the box)", len(extrudes()) == 1, [o.Name for o in extrudes()]
    )
    h.check("the part is as before", near(h.solid_volume(), s["volume"]), h.solid_volume())
    h.check(
        "no value box left",
        not a.value_boxes(visible_only=False),
        [(b.text(), b.isVisible()) for b in a.value_boxes(visible_only=False)],
    )
    close_if_open("Esc in the Extrude box")
    h.fit()


# -- a cut edited from the timeline shows red at once ---------------------------------------------
def sketch_on_top():
    h.ribbon("Create Sketch")


def click_top():
    h.click(V(30, 22, 10))


def draw_square():
    sk = h.in_sketch()
    h.check("sketch open on the top face", sk is not None)
    if sk is not None:
        x0, y0 = h.to_sketch(sk, V(10, 5, 10))
        x1, y1 = h.to_sketch(sk, V(20, 15, 10))
        h.draw_rectangle(sk, min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def finish_sketch():
    h.ribbon("Finish Sketch")


def e_pocket():
    h.fit()
    h.press("e")


def type_minus_6():
    p = xpanel()
    h.check("E picks the square", p is not None and len(p.profiles) == 1, p and p.profiles)
    if p is not None:
        ui.type_into(p.distance.widget, "-6")


def ok_pocket():
    h.check("red while making it", len(a.cut_nodes()) == 1, len(a.cut_nodes()))
    h.task_button("OK")


def pocket_made():
    h.check("the pocket: 12000 - 600", near(h.solid_volume(), BOX - POCKET), h.solid_volume())
    h.check("no red after OK", not a.cut_nodes(), len(a.cut_nodes()))
    h.check("timeline", ui.timeline_titles()[-1:] == ["Extrude 2"], ui.timeline_titles())
    s["volume"] = h.solid_volume()
    s["children"] = a.scene_children()


def edit_pocket():
    h.check("double-click Extrude 2", ui.double_click_timeline("Extrude 2"), ui.timeline_titles())


def pocket_red_at_once(where=""):
    p = xpanel()
    h.check("the Extrude dialog opens on Extrude 2%s" % where, p is not None and p.editing)
    nodes = a.cut_nodes()
    h.check(
        "R7: the cut shows in red at once%s (one red node)" % where, len(nodes) == 1, len(nodes)
    )
    if nodes:
        h.check(
            "R7: it is the pocket%s" % where,
            bound(a.node_box(nodes[0]), (10, 5, 4), (20, 15, 10)),
            a.node_box(nodes[0]),
        )
    h.check(
        "its value box shows -6%s" % where,
        [b.text() for b in a.value_boxes(arrows_only=True)] == [p.distance.widget.text()] if p else False,
        [b.text() for b in a.value_boxes(arrows_only=True)],
    )
    h.shot("4-edit-red" + where.replace(" ", "-"))
    h.press(QtCore.Qt.Key_Escape)


def edit_closed(where=""):
    h.check("Esc closes the edit%s" % where, not Gui.Control.activeDialog())
    h.check("R7: no red left after Esc%s" % where, not a.cut_nodes(), len(a.cut_nodes()))
    h.check(
        "the part is as before%s" % where, near(h.solid_volume(), s["volume"]), h.solid_volume()
    )
    h.check("no value box left%s" % where, not a.value_boxes(visible_only=False))
    close_if_open("the edit")


def press_q_top():
    h.press("q")


def click_top_face():
    h.click(V(32, 25, 10))  # away from the pocket


def type_minus_3():
    p = ppanel()
    h.check(
        "Press Pull took the top face", p is not None and p.mode == "faces", p and p.message.text()
    )
    if p is not None:
        ui.type_into(p.field.widget, "-3")


def ok_push():
    h.check("red while pushing in", len(a.cut_nodes()) == 1, len(a.cut_nodes()))
    h.task_button("OK")


def push_made():
    h.check(
        "Press Pull made",
        len(press_pulls()) == 1 and not Gui.Control.activeDialog(),
        [o.Name for o in press_pulls()],
    )
    h.check("no red after OK", not a.cut_nodes(), len(a.cut_nodes()))
    s["volume"] = h.solid_volume()
    h.check("pushed 3 in: 11400 - 3600 + 300", near(s["volume"], 8100.0), s["volume"])


def edit_push():
    h.check(
        "double-click Press Pull 1", ui.double_click_timeline("Press Pull 1"), ui.timeline_titles()
    )


def push_red_at_once(where=""):
    p = ppanel()
    h.check("the Press Pull dialog opens on Press Pull 1%s" % where, p is not None and p.editing)
    nodes = a.cut_nodes()
    h.check(
        "R7: the material pushed away shows in red at once%s" % where, len(nodes) == 1, len(nodes)
    )
    if nodes:
        h.check(
            "R7: it is the top 3 mm%s" % where,
            bound(a.node_box(nodes[0]), (0, 0, 7), (40, 30, 10)),
            a.node_box(nodes[0]),
        )
    h.shot("5-pp-edit-red" + where.replace(" ", "-"))
    h.press(QtCore.Qt.Key_Escape)


# -- after saving and opening again ----------------------------------------------------------------
def save_and_reopen():
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-feel-"), "feel_box.FCStd")
    App.ActiveDocument.saveAs(path)
    App.closeDocument(App.ActiveDocument.Name)
    App.openDocument(path)
    h.fit()


def reopened_edit_push():
    pulls = press_pulls()
    h.check("the Press Pull is back", len(pulls) == 1, [o.Name for o in pulls])
    if pulls:
        kept = getattr(getattr(pulls[0], "Proxy", None), "tool", None)
        h.check(
            "opened from the file: nothing of its removed material is kept yet", kept is None, kept
        )
    h.check("the part as saved", near(h.solid_volume(), s["volume"]), h.solid_volume())
    edit_push()


def reopened_push_red():
    push_red_at_once(" after reopening")


def reopened_push_closed():
    edit_closed(" after reopening")


def reopened_edit_pocket():
    edit_pocket()


def reopened_pocket_red():
    pocket_red_at_once(" after reopening")


def reopened_pocket_closed():
    edit_closed(" after reopening")


h.run(
    "extrude_feel_box",
    bs.box_steps("FeelBox")
    + [
        press_q,
        click_side,
        front_for_pp,
        pp_pan,
        pp_heads,
        pp_grabbed,
        pp_box_esc,
        pp_cancelled,
        press_e,
        click_side_e,
        front_for_e,
        e_pan,
        e_heads,
        e_grabbed,
        e_box_zero_enter,
        e_box_esc,
        e_cancelled,
        sketch_on_top,
        click_top,
        draw_square,
        finish_sketch,
        e_pocket,
        type_minus_6,
        ok_pocket,
        pocket_made,
        edit_pocket,
        pocket_red_at_once,
        edit_closed,
        press_q_top,
        click_top_face,
        type_minus_3,
        ok_push,
        push_made,
        edit_push,
        push_red_at_once,
        edit_closed,
        save_and_reopen,
        reopened_edit_push,
        reopened_push_red,
        reopened_push_closed,
        reopened_edit_pocket,
        reopened_pocket_red,
        reopened_pocket_closed,
    ],
)
