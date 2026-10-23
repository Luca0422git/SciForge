# SPDX-License-Identifier: LGPL-2.1-or-later
"""Boss the way a Fusion user does it, real input only: an enclosure and its lid (shelled
2 mm), a sketch with two points on the parting plane. PLASTIC tab > Boss with nothing
picked (the dialog waits, no error), click the sketch's row in the browser (its points are
taken), the preview builds the head side in the lid and the thread side in the enclosure
(volumes worked out by hand in plastic_steps), ribs on the thread side turned 45 degrees,
a hole wider than the boss (refused in the dialog, OK waits), OK, Ctrl+Z / Ctrl+Y, edit by
double-clicking the timeline (Flip swaps the sides; Esc leaves it as it was), a second Boss
cancelled with Esc, save and reopen."""

import os
import re
import tempfile

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plastic_steps as ps
from SciForgeTests.gui import versions_input as vi

V = App.Vector
s = {}


def setup():
    doc, bottom, lid, sk = ps.enclosure("PlasticBoss")
    s.update(doc=doc, bottom=bottom.Name, lid=lid.Name, sketch=sk.Name)
    s["v_bottom"] = ps.volume(bottom)
    s["v_lid"] = ps.volume(lid)
    h.check(
        "enclosure made (60x40x20 shelled 2)", ps.near(s["v_bottom"], 48000 - 56 * 36 * 18, 1e-6)
    )
    h.check("lid made (60x40x10 shelled 2)", ps.near(s["v_lid"], 24000 - 56 * 36 * 8, 1e-6))
    ps.plastic_tab()


def boss_titles(titles):
    return [t for t in titles if re.match(r"^Boss \d+$", t)]


def bodies():
    doc = App.ActiveDocument
    return doc.getObject(s["bottom"]), doc.getObject(s["lid"])


def start_boss():
    Gui.Selection.clearSelection()
    h.ribbon("Boss")


def waiting():
    p = ps.boss_panel()
    h.check("Boss dialog open", p is not None and Gui.Control.activeDialog())
    if p is None:
        return
    h.check("nothing picked yet", p.refs == [] and p.steps == [])
    h.check("points box says Select points", p.field.button.text() == "Select points")
    h.check("no error while waiting", p.message.text() == "", p.message.text())
    b, l = bodies()
    h.check("model unchanged while waiting", ps.near(ps.volume(b), s["v_bottom"], 1e-6))
    h.check("the rule shown (default)", "Plastic rule" in p.rule_label.text(), p.rule_label.text())
    h.shot("1-waiting")


def click_sketch_row():
    h.check("clicked the sketch's row", ps.click_row("Boss Points"))


def previewed():
    p = ps.boss_panel()
    ps.settle(p)
    h.check("two points taken", p is not None and len(p.refs) == 2, p and p.refs)
    h.check("box says 2 points", p and p.field.button.text() == "2 points")
    h.check("one step per side", p and len(p.steps) == 2, p and p.steps)
    b, l = bodies()
    vb, vl = ps.volume(b), ps.volume(l)
    want_b = s["v_bottom"] + 2 * ps.thread_side_boss()
    want_l = s["v_lid"] + 2 * ps.head_side_boss()
    h.check(
        "thread side in the enclosure (hand: +2 x %.2f)" % ps.thread_side_boss(),
        ps.near(vb, want_b, 1.0),
        (vb, want_b),
    )
    h.check(
        "head side in the lid (hand: +2 x %.2f)" % ps.head_side_boss(),
        ps.near(vl, want_l, 1.0),
        (vl, want_l),
    )
    h.check(
        "both bodies valid solids",
        b.Shape.isValid() and l.Shape.isValid() and len(b.Shape.Solids) == 1,
    )
    text = p.bodies_label.text() if p else ""
    h.check(
        "sides named in the dialog",
        "Side 1 (head): Lid" in text and "Side 2 (thread): Bottom" in text,
        text,
    )
    h.check("offset arrow shown", p is not None and p.arrow is not None)
    h.check("no error", p and p.message.text() == "", p and p.message.text())
    s["v_b1"], s["v_l1"] = vb, vl
    h.shot("2-preview")


def ribs_tab():
    p = ps.boss_panel()
    ps.tab_of(p, "Ribs")


def ribs_on():
    p = ps.boss_panel()
    ps.check_box(p.rib_on[2])


def rib_side_2():
    p = ps.boss_panel()
    ps.choose(p.rib_side, "Side 2")


def rib_rotation():
    p = ps.boss_panel()
    ps.type_into(p.rib_fields["rib_rotation"].widget, "45")


def ribs_made():
    p = ps.boss_panel()
    ps.settle(p)
    h.check("ribs on side 2", p and p.options["side2"]["ribs"])
    h.check("rotation typed 45", p and abs(p.options["side2"]["rib_rotation"] - 45) < 1e-9)
    b, l = bodies()
    vb = ps.volume(b)
    h.check("ribs add material to the enclosure", vb > s["v_b1"] + 50, (vb, s["v_b1"]))
    h.check("the lid unchanged by side 2's ribs", ps.near(ps.volume(l), s["v_l1"], 1e-6))
    h.check("enclosure still one valid solid", b.Shape.isValid() and len(b.Shape.Solids) == 1)
    h.check("no error", p and p.message.text() == "", p and p.message.text())
    s["v_b2"] = vb
    h.shot("3-ribs")


def suppress_rib_2():
    p = ps.boss_panel()
    h.check("one list per rib", p and len(p.each_combos) == 4, p and len(p.each_combos))
    ps.choose(p.each_combos[1], "Suppressed")


def rib_2_gone():
    p = ps.boss_panel()
    ps.settle(p)
    h.check(
        "rib 2 suppressed",
        p and p.options["side2"]["rib_extents"] == ["length", "suppressed", "length", "length"],
        p and p.options["side2"].get("rib_extents"),
    )
    b, _l = bodies()
    v = ps.volume(b)
    h.check("one rib less at each point", v < s["v_b2"] - 10, (v, s["v_b2"]))
    h.check("still one valid solid", b.Shape.isValid() and len(b.Shape.Solids) == 1)
    ps.choose(p.each_combos[1], "By Length")


def rib_2_back():
    p = ps.boss_panel()
    ps.settle(p)
    b, _l = bodies()
    h.check("rib 2 back", ps.near(ps.volume(b), s["v_b2"], 1e-6), ps.volume(b))


def side1_tab():
    p = ps.boss_panel()
    ps.tab_of(p, "Side 1")


def huge_hole():
    p = ps.boss_panel()
    ps.type_into(p.side_widgets[1]["hole_diameter"].widget, "20")


def refused():
    p = ps.boss_panel()
    ps.settle(p)
    text = p.message.text() if p else ""
    h.check("too wide a hole explained", "smaller than the outer diameter" in text, text)


def ok_refused():
    ps.ok()


def still_open():
    p = ps.boss_panel()
    h.check("OK waits while the hole is too wide", p is not None and Gui.Control.activeDialog())


def hole_back():
    p = ps.boss_panel()
    ps.type_into(p.side_widgets[1]["hole_diameter"].widget, "3.4")


def ok():
    p = ps.boss_panel()
    ps.settle(p)
    h.check("message cleared", p and p.message.text() == "", p and p.message.text())
    ps.ok()


def done():
    h.check("dialog closed", ps.boss_panel() is None and not Gui.Control.activeDialog())
    titles = ps.timeline_titles()
    h.check("two Boss steps in the timeline", len(boss_titles(titles)) == 2, titles)
    b, l = bodies()
    h.check("enclosure kept with ribs", ps.near(ps.volume(b), s["v_b2"], 1e-6))
    h.check("lid kept", ps.near(ps.volume(l), s["v_l1"], 1e-6))
    h.shot("4-done")


def undo():
    ps.undo()


def undone():
    b, l = bodies()
    h.check("Ctrl+Z: enclosure as before", ps.near(ps.volume(b), s["v_bottom"], 1e-6), ps.volume(b))
    h.check("Ctrl+Z: lid as before", ps.near(ps.volume(l), s["v_lid"], 1e-6), ps.volume(l))


def redo():
    ps.redo()


def redone():
    b, l = bodies()
    h.check(
        "Ctrl+Y: bosses back",
        ps.near(ps.volume(b), s["v_b2"], 1e-6) and ps.near(ps.volume(l), s["v_l1"], 1e-6),
    )


def edit():
    ps.double_click_timeline(boss_titles(ps.timeline_titles())[0])


def editing():
    p = ps.boss_panel()
    ps.settle(p)
    h.check("edit dialog open with both points", p is not None and len(p.refs) == 2)
    h.check("edit keeps the ribs", p and p.options["side2"]["ribs"])
    h.check("edit keeps both steps", p and len(p.steps) == 2)


def flip():
    p = ps.boss_panel()
    ps.tab_of(p, "Boss")
    ps.check_box(p.flip)


def flipped():
    p = ps.boss_panel()
    ps.settle(p)
    b, l = bodies()
    text = p.bodies_label.text() if p else ""
    h.check("Flip: the enclosure is the head side now", "Side 1 (head): Bottom" in text, text)
    h.check("flipped bodies valid", b.Shape.isValid() and l.Shape.isValid())
    h.check("flipped result differs", not ps.near(ps.volume(b), s["v_b2"], 1.0), ps.volume(b))
    h.check("no error", p and p.message.text() == "", p and p.message.text())


def esc_edit():
    ps.esc()


def edit_cancelled():
    b, l = bodies()
    h.check(
        "Esc: the edit is dropped",
        ps.near(ps.volume(b), s["v_b2"], 1e-6) and ps.near(ps.volume(l), s["v_l1"], 1e-6),
    )
    h.check("dialog closed", ps.boss_panel() is None)


def second_boss():
    Gui.Selection.clearSelection()
    h.ribbon("Boss")


def second_pick():
    ps.click_row("Boss Points")


def second_esc():
    p = ps.boss_panel()
    ps.settle(p)
    # the rays along the first bosses' axes now run down their holes: the lid's head side
    # has a through hole, so only the enclosure is found at these points
    h.check(
        "second boss previews",
        p is not None and len(p.steps) >= 1,
        p and (p.steps, p.message.text()),
    )
    ps.esc()


def second_gone():
    titles = ps.timeline_titles()
    h.check("Esc: no new steps", len(boss_titles(titles)) == 2, titles)
    b, l = bodies()
    h.check(
        "Esc: volumes as before",
        ps.near(ps.volume(b), s["v_b2"], 1e-6) and ps.near(ps.volume(l), s["v_l1"], 1e-6),
    )


def save():
    doc = App.ActiveDocument
    path = os.path.join(tempfile.mkdtemp(prefix="sf-plastic-"), "PlasticBoss.FCStd")
    s["path"] = path
    doc.saveAs(path)


def reopen():
    App.closeDocument(App.ActiveDocument.Name)
    doc = App.openDocument(s["path"])
    doc.recompute()
    h.fit()


def reopened():
    doc = App.ActiveDocument
    b, l = doc.getObject(s["bottom"]), doc.getObject(s["lid"])
    h.check("reopened: enclosure same", ps.near(ps.volume(b), s["v_b2"], 1e-6), ps.volume(b))
    h.check("reopened: lid same", ps.near(ps.volume(l), s["v_l1"], 1e-6), ps.volume(l))
    steps = [o for o in doc.Objects if getattr(o, "SciForgeType", "") == "Boss"]
    h.check(
        "reopened: both boss steps valid",
        len(steps) == 2 and all("Invalid" not in o.State for o in steps),
        [o.State for o in steps],
    )
    h.shot("5-reopened")


h.run(
    "plastic_boss",
    [
        setup,
        start_boss,
        waiting,
        click_sketch_row,
        previewed,
        ribs_tab,
        ribs_on,
        rib_side_2,
        rib_rotation,
        ribs_made,
        suppress_rib_2,
        rib_2_gone,
        rib_2_back,
        side1_tab,
        huge_hole,
        refused,
        ok_refused,
        still_open,
        hole_back,
        ok,
        done,
        undo,
        undone,
        redo,
        redone,
        edit,
        editing,
        flip,
        flipped,
        esc_edit,
        edit_cancelled,
        second_boss,
        second_pick,
        second_esc,
        second_gone,
        save,
        reopen,
        reopened,
    ],
)
