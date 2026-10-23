# SPDX-License-Identifier: LGPL-2.1-or-later
"""QA paths of Boss and Rest the builder's scenarios do not walk, real input only.

Boss on a face, then Esc: the point sketch the click made and the standoff are gone, the
part is as it was. Rest with the rule's own draft (1 deg, as a beginner leaves it): the
flat 20 x 12 face is made on its pedestal, Esc leaves the cover as it was. A boss saved
and reopened: double-click it in the timeline, type a new Offset Position (the boss
moves), OK, Ctrl+Z (back); then assign a plastic rule with another wall (PMMA 2.5 mm):
the reopened boss follows the rule."""

import math
import os
import re
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
import Part

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plastic_steps as ps

V = App.Vector
s = {}


def boss_titles():
    return [t for t in ps.timeline_titles() if re.match(r"^Boss \d+$", t)]


def boss_steps(doc=None):
    doc = doc or App.ActiveDocument
    return [o for o in doc.Objects if getattr(o, "SciForgeType", "") == "Boss"]


def sketches(doc=None):
    doc = doc or App.ActiveDocument
    return sorted(o.Name for o in doc.Objects if o.TypeId == "Sketcher::SketchObject")


# -- Boss on a face, then Esc ----------------------------------------------------------------------
def face_setup():
    doc, bottom, _lid, _sk = ps.enclosure("PlasticQAFace", lid=False, points=())
    s.update(bottom=bottom.Name, v0=ps.volume(bottom), sketches=sketches(doc))
    ps.plastic_tab()
    Gui.Selection.clearSelection()
    h.ribbon("Boss")


def click_floor():
    h.fit()
    h.click(V(10, 32, 2))


def standoff_previewed():
    p = ps.boss_panel()
    ps.settle(p)
    h.check("a standoff previewed", p is not None and len(p.steps) == 1, p and p.steps)
    h.check(
        "a point sketch made on the floor",
        len(sketches()) == len(s["sketches"]) + 1,
        sketches(),
    )
    bottom = App.ActiveDocument.getObject(s["bottom"])
    h.check("the part grew", ps.volume(bottom) > s["v0"] + 1.0, ps.volume(bottom))


def esc():
    ps.esc()


def face_esc_dropped():
    doc = App.ActiveDocument
    bottom = doc.getObject(s["bottom"])
    h.check("Esc closed Boss", ps.boss_panel() is None and not Gui.Control.activeDialog())
    h.check("Esc: no boss step", boss_steps() == [], boss_steps())
    h.check("Esc: the point sketch is gone", sketches() == s["sketches"], sketches())
    h.check("Esc: the part as it was", ps.near(ps.volume(bottom), s["v0"], 1e-6))
    App.closeDocument(doc.Name)


# -- Rest with the rule's draft, then Esc ----------------------------------------------------------
def rest_setup():
    from sciforge import bodies, extrude, shelling

    ps.clear_library_prefs()
    doc = App.newDocument("PlasticQARest")
    body = bodies.new_body(doc, "Cover")
    sk = body.newObject("Sketcher::SketchObject", "Arch")
    sk.MapMode = "Deactivated"
    sk.Placement = App.Placement(V(0, 0, 0), App.Rotation(0.5, 0.5, 0.5, 0.5))  # YZ
    sk.addGeometry(Part.ArcOfCircle(Part.Circle(V(0, 0, 0), V(0, 0, 1), 20), 0.0, math.pi))
    sk.addGeometry(Part.LineSegment(V(-20, 0, 0), V(20, 0, 0)))
    doc.recompute()
    ext = extrude.make(body, sk, {"distance": 60})
    doc.recompute()
    bottom = ps.face_named(ext, V(0, 0, -1), 0)
    shelling.make(body, ext, [bottom], {"inside": 2.0, "shell_type": "rounded"})
    doc.recompute()
    landing = ps.rect_sketch(body, 22, 20, -6, 40, 6, "Landing")
    landing.Label = "Landing"
    doc.recompute()
    bodies.set_active_body(body)
    s.update(cover=body.Name, v_cover=ps.volume(body))
    h.fit()
    ps.plastic_tab()
    Gui.Selection.clearSelection()
    h.ribbon("Rest")


def click_landing():
    p = ps.rest_panel()
    h.check("Rest opens with the rule's 1 deg draft", p and abs(p.draft.value() - 1.0) < 1e-9)
    h.fit()
    h.click(V(30, 0, 22))


def rest_drafted():
    p = ps.rest_panel()
    ps.settle(p)
    h.check("no error", p is not None and p.message.text() == "", p and p.message.text())
    h.check(
        "the dialog says the rule (the default: none assigned)",
        p and p.rule_label.text() == "Plastic rule: Default (mm) (default; no rule assigned)",
        p and p.rule_label.text(),
    )
    cover = App.ActiveDocument.getObject(s["cover"])
    flat = [
        f
        for f in cover.Shape.Faces
        if abs(f.BoundBox.ZMin - 22) < 1e-6 and abs(f.BoundBox.ZMax - 22) < 1e-6
    ]
    h.check(
        "drafted rest: one flat 20 x 12 face at z 22",
        len(flat) == 1 and ps.near(flat[0].Area, 240.0, 1e-6),
        [f.Area for f in flat],
    )
    h.check("drafted rest: a valid solid", cover.Shape.isValid() and len(cover.Shape.Solids) == 1)
    flat_rest = s["v_cover"] + ps.rest_volume(2.0)
    v = ps.volume(cover)
    h.check(
        "the draft adds a little to the undrafted pedestal",
        flat_rest < v < flat_rest + 30.0,
        (v, flat_rest),
    )


def rest_esc_dropped():
    doc = App.ActiveDocument
    cover = doc.getObject(s["cover"])
    h.check("Esc closed Rest", ps.rest_panel() is None and not Gui.Control.activeDialog())
    rests = [o for o in doc.Objects if getattr(o, "SciForgeType", "") == "Rest"]
    h.check("Esc: no rest step", rests == [], rests)
    h.check("Esc: the cover as it was", ps.near(ps.volume(cover), s["v_cover"], 1e-6))
    Gui.Selection.clearSelection()
    h.ribbon("Rest")


def rest_again():
    h.fit()
    h.click(V(30, 0, 22))


def rest_ok():
    ps.settle(ps.rest_panel())
    ps.ok()


def rest_made():
    doc = App.ActiveDocument
    rests = [o for o in doc.Objects if getattr(o, "SciForgeType", "") == "Rest"]
    h.check("Rest made", ps.rest_panel() is None and len(rests) == 1, rests)
    s["v_rest"] = ps.volume(doc.getObject(s["cover"]))
    assign_rule("PMMA 2.5 mm")


def assign_rule(name):
    Gui.Selection.clearSelection()
    h.ribbon("Assign Plastic Rule")
    ps.settle(ps.assign_panel())
    ps.click_tree_row(ps.assign_panel().rules.tree, name, "Library")
    ps.ok()


def rest_follows():
    doc = App.ActiveDocument
    v = ps.volume(doc.getObject(s["cover"]))
    h.check("the Rest follows the rule's 2.5 mm wall", v > s["v_rest"] + 1.0, (v, s["v_rest"]))
    ps.double_click_timeline("Rest 1")


def rest_edit_shows_rule():
    p = ps.rest_panel()
    ps.settle(p)
    h.check("edit opens the Rest", p is not None)
    h.check(
        "the edit says the rule",
        p and p.rule_label.text() == "Plastic rule: PMMA 2.5 mm",
        p and p.rule_label.text(),
    )
    h.check(
        "the edit shows the thickness it is built with (the rule's 2.5 mm)",
        p and abs(p.thickness.value() - 2.5) < 1e-9,
        p and p.thickness.value(),
    )
    ps.esc()


def rest_closed():
    doc = App.ActiveDocument
    v = ps.volume(doc.getObject(s["cover"]))
    h.check("Esc: the Rest unchanged", ps.rest_panel() is None and v > s["v_rest"] + 1.0, v)
    App.closeDocument(doc.Name)


# -- a boss edited after save and reopen -----------------------------------------------------------
def reopen_setup():
    doc, bottom, lid, _sk = ps.enclosure("PlasticQAReopen", points=((10, 10),))
    s.update(b=bottom.Name, l=lid.Name)
    ps.plastic_tab()
    Gui.Selection.clearSelection()
    h.ribbon("Boss")


def click_points_row():
    h.check("clicked the sketch's row", ps.click_row("Boss Points"))


def side1_lid():
    p = ps.boss_panel()
    ps.settle(p)
    ps.click(p.body_fields[1].button)
    ps.click_row("Lid")


def lid_picked():
    p = ps.boss_panel()
    ps.settle(p)
    h.check("Side 1 Body: Lid", p and p.body_fields[1].button.text() == "Lid")
    h.check("no error", p and p.message.text() == "", p and p.message.text())
    ps.tab_of(p, "Boss")
    ps.check_box(p.flip)


def flip_moves_pick():
    """Flip swaps head and thread: the picked lid stays above the plane, so it is Side 2's
    body now (it was refused as Side 1's: nothing of the lid lies below the plane)."""
    p = ps.boss_panel()
    ps.settle(p)
    h.check(
        "Flip: the picked lid moves to the Side 2 box",
        p and p.body_fields[2].button.text() == "Lid" and p.body_fields[1].button.text() == "Auto",
        p and (p.body_fields[1].button.text(), p.body_fields[2].button.text()),
    )
    text = p.bodies_label.text() if p else ""
    h.check("the lid is the thread side now", "Side 2 (thread): Lid" in text, text)
    h.check("no error after Flip", p and p.message.text() == "", p and p.message.text())
    ps.check_box(p.flip)


def unflipped():
    p = ps.boss_panel()
    ps.settle(p)
    h.check("Flip back: the lid in the Side 1 box", p and p.body_fields[1].button.text() == "Lid")
    h.check("no error", p and p.message.text() == "", p and p.message.text())


def boss_ok():
    ps.settle(ps.boss_panel())
    ps.ok()


def parts():
    doc = App.ActiveDocument
    return doc.getObject(s["b"]), doc.getObject(s["l"])


def boss_made():
    b, l = parts()
    h.check("Boss made", ps.boss_panel() is None and len(boss_steps()) == 2, boss_steps())
    s.update(vb=ps.volume(b), vl=ps.volume(l))


def save_reopen():
    path = os.path.join(tempfile.mkdtemp(prefix="sf-plastic-qa-"), "PlasticQAReopen.FCStd")
    App.ActiveDocument.saveAs(path)
    App.closeDocument(App.ActiveDocument.Name)
    doc = App.openDocument(path)
    doc.recompute()
    h.fit()


def reopened():
    b, l = parts()
    h.check("reopened: same enclosure", ps.near(ps.volume(b), s["vb"], 1e-6), ps.volume(b))
    h.check("reopened: same lid", ps.near(ps.volume(l), s["vl"], 1e-6), ps.volume(l))
    titles = boss_titles()
    h.check("reopened: the boss in the timeline", len(titles) >= 1, ps.timeline_titles())
    ps.double_click_timeline(titles[0] if titles else "Boss 1")


def reopened_editing():
    p = ps.boss_panel()
    ps.settle(p)
    h.check("edit after reopen opens the Boss", p is not None)
    if p is None:
        return
    h.check("with its point", len(p.refs) == 1, p.refs)
    h.check("and both sides", len(p.steps) == 2, p.steps)
    ps.type_into(p.offset.widget, "1")


def offset_moved():
    p = ps.boss_panel()
    ps.settle(p)
    b, l = parts()
    h.check("no error", p is not None and p.message.text() == "", p and p.message.text())
    h.check(
        "the parting plane 1 mm up: the enclosure's boss longer",
        ps.volume(b) > s["vb"] + 1.0,
        (ps.volume(b), s["vb"]),
    )
    h.check("and the lid's shorter", ps.volume(l) < s["vl"] - 1.0, (ps.volume(l), s["vl"]))
    s.update(vb1=ps.volume(b), vl1=ps.volume(l))
    ps.tab_of(p, "Side 1")
    ps.type_into(p.side_widgets[1]["major_draft"].widget, "5")


def counterbore_drafted():
    """The counterbore (floor at z 21.05 + 2 = 23.05, r 3.25) widens by tan 5 deg up to the
    outside (z 30): a frustum instead of a cylinder."""
    p = ps.boss_panel()
    ps.settle(p)
    _b, l = parts()
    h.check("no error", p is not None and p.message.text() == "", p and p.message.text())
    k = math.tan(math.radians(5.0))
    length, r1 = 6.95, 3.25
    r2 = r1 + length * k
    extra = math.pi * length / 3.0 * (r1 * r1 + r1 * r2 + r2 * r2) - math.pi * r1 * r1 * length
    want = s["vl1"] - extra
    h.check(
        "Major Draft Angle 5: the counterbore widens to the outside (-%.3f)" % extra,
        ps.near(ps.volume(l), want, 1e-4),
        (ps.volume(l), want),
    )
    s["vl1"] = ps.volume(l)
    ps.type_into(p.side_widgets[1]["major_tip_radius"].widget, "0.5")


def drafted_mouth_refused():
    p = ps.boss_panel()
    ps.settle(p)
    text = p.message.text() if p else ""
    h.check(
        "a rounded mouth on a drafted counterbore is refused, said why", "Major Draft" in text, text
    )
    ps.type_into(p.side_widgets[1]["major_tip_radius"].widget, "0")


def edit_ok():
    p = ps.boss_panel()
    ps.settle(p)
    h.check("no error again", p is not None and p.message.text() == "", p and p.message.text())
    ps.ok()


def edit_kept():
    b, l = parts()
    h.check("OK: closed", ps.boss_panel() is None)
    h.check("OK keeps the move", ps.near(ps.volume(b), s["vb1"], 1e-6), ps.volume(b))
    h.check("OK keeps the drafted counterbore", ps.near(ps.volume(l), s["vl1"], 1e-6), ps.volume(l))
    h.check("both steps valid", all("Invalid" not in o.State for o in boss_steps()), boss_steps())


def undo():
    ps.undo()


def edit_undone():
    b, l = parts()
    h.check("Ctrl+Z: the enclosure as reopened", ps.near(ps.volume(b), s["vb"], 1e-6))
    h.check("Ctrl+Z: the lid as reopened", ps.near(ps.volume(l), s["vl"], 1e-6))
    Gui.Selection.clearSelection()
    h.ribbon("Assign Plastic Rule")


def pick_pmma():
    ps.click_tree_row(ps.assign_panel().rules.tree, "PMMA 2.5 mm", "Library")
    ps.ok()


def boss_follows_rule():
    from sciforge import plastic

    doc = App.ActiveDocument
    b, l = parts()
    h.check("PMMA 2.5 mm assigned", plastic.assigned_rule_name(doc) == "PMMA 2.5 mm")
    h.check(
        "the reopened boss follows the rule (root radius 1.25)",
        not ps.near(ps.volume(b), s["vb"], 1e-3),
        (ps.volume(b), s["vb"]),
    )
    h.check("both steps valid", all("Invalid" not in o.State for o in boss_steps()), boss_steps())
    ps.double_click_timeline(boss_titles()[0])


def boss_edit_shows_rule():
    p = ps.boss_panel()
    ps.settle(p)
    h.check("edit opens the Boss", p is not None)
    if p is None:
        return
    for side in (1, 2):
        w = p.side_widgets[side]
        h.check(
            "Side %d shows the root radius it is built with (the rule's 1.25)" % side,
            abs(w["root_radius"].value() - 1.25) < 1e-9,
            w["root_radius"].value(),
        )
        h.check(
            "Side %d shows the rule's clearance (0.1 / 2)" % side,
            abs(w["clearance"].value() - 0.05) < 1e-9,
            w["clearance"].value(),
        )
    ps.esc()


def boss_edit_closed():
    b, _l = parts()
    h.check("Esc closed the Boss", ps.boss_panel() is None)
    h.check("Esc: the boss unchanged", not ps.near(ps.volume(b), s["vb"], 1e-3))
    ps.clear_library_prefs()


# -- the lid in a component of its own, placed by the component ------------------------------------
def comp_setup():
    from sciforge import bodies, components

    ps.clear_library_prefs()
    doc = App.newDocument("PlasticQAComponents")
    bottom = ps.box_body(doc, "Bottom", 0, 20, "top")
    cover = components.new_component(doc, "Cover")
    lid = ps.box_body(doc, "Lid", 0, 10, "bottom", component=cover)
    cover.Placement = App.Placement(V(0, 0, 20), App.Rotation())  # the lid sits on z 20
    sk = bottom.newObject("Sketcher::SketchObject", "BossPoints")
    sk.Label = "Boss Points"
    sk.MapMode = "Deactivated"
    sk.Placement = App.Placement(V(0, 0, 20), App.Rotation())
    sk.addGeometry(Part.Point(V(10, 10, 0)))
    doc.recompute()
    bodies.set_active_body(bottom)
    s.update(cb=bottom.Name, cl=lid.Name, cvb=ps.volume(bottom), cvl=ps.volume(lid))
    h.fit()
    ps.plastic_tab()
    Gui.Selection.clearSelection()
    h.ribbon("Assign Plastic Rule")


def comp_assign_cover():
    """The Cover component (the lid) gets PMMA 2.5 mm; the enclosure (root) keeps none."""
    p = ps.assign_panel()
    ps.choose(p.combo, "Cover")
    ps.click_tree_row(p.rules.tree, "PMMA 2.5 mm", "Library")
    ps.ok()


def comp_boss():
    from sciforge import plastic

    doc = App.ActiveDocument
    cover = doc.getObject(s["cl"]).getParentGeoFeatureGroup()
    h.check("the Cover has PMMA 2.5 mm", plastic.assigned_rule_name(doc, cover) == "PMMA 2.5 mm")
    h.check("the root has no rule", plastic.assigned_rule_name(doc) == "")
    Gui.Selection.clearSelection()
    h.ribbon("Boss")


def comp_points():
    h.check("clicked the sketch's row", ps.click_row("Boss Points"))


def comp_previewed():
    p = ps.boss_panel()
    ps.settle(p)
    doc = App.ActiveDocument
    b, l = doc.getObject(s["cb"]), doc.getObject(s["cl"])
    text = p.bodies_label.text() if p else ""
    h.check(
        "the lid in its component is found as the head side",
        "Side 1 (head): Lid" in text and "Side 2 (thread): Bottom" in text,
        text,
    )
    h.check(
        "the dialog names each side's rule",
        p
        and p.rule_label.text()
        == "Plastic rule: Side 1: PMMA 2.5 mm; Side 2: Default (mm) (default; no rule assigned)",
        p and p.rule_label.text(),
    )
    w1, w2 = (p.side_widgets[1], p.side_widgets[2]) if p else ({}, {})
    h.check(
        "Side 1 (the lid, PMMA) shows root radius 1.25, Side 2 (default rule) 1.0",
        p
        and abs(w1["root_radius"].value() - 1.25) < 1e-9
        and abs(w2["root_radius"].value() - 1.0) < 1e-9,
        p and (w1["root_radius"].value(), w2["root_radius"].value()),
    )
    r2 = 5.0 + 7.95 * ps.TAN1  # the head side's shank at the lid's inside
    want_b = s["cvb"] + ps.thread_side_boss()
    want_l = s["cvl"] + ps.head_side_boss() - ps.fillet_ring(r2, 1.0) + ps.fillet_ring(r2, 1.25)
    h.check(
        "thread side in the enclosure (by hand)",
        ps.near(ps.volume(b), want_b, 1.0),
        (ps.volume(b), want_b),
    )
    h.check(
        "head side in the component's lid, with PMMA's 1.25 root radius (by hand)",
        ps.near(ps.volume(l), want_l, 1.0),
        (ps.volume(l), want_l),
    )
    h.check("no error", p and p.message.text() == "", p and p.message.text())
    ps.ok()


def comp_done():
    doc = App.ActiveDocument
    steps = boss_steps(doc)
    h.check(
        "OK: one step in each body, valid",
        len(steps) == 2 and all("Invalid" not in o.State for o in steps),
        [(o.Label, o.State) for o in steps],
    )
    ps.undo()


def comp_undone():
    doc = App.ActiveDocument
    b, l = doc.getObject(s["cb"]), doc.getObject(s["cl"])
    h.check("Ctrl+Z: no boss", boss_steps(doc) == [])
    h.check(
        "Ctrl+Z: both bodies as they were",
        ps.near(ps.volume(b), s["cvb"], 1e-6) and ps.near(ps.volume(l), s["cvl"], 1e-6),
    )


# -- the default ribs of a boss 10 mm from the case's edge -----------------------------------------
def ribs_setup():
    doc, bottom, lid, _sk = ps.enclosure("PlasticQARibs")
    s.update(rb=bottom.Name, rv=ps.volume(bottom))
    ps.plastic_tab()
    Gui.Selection.clearSelection()
    h.ribbon("Boss")


def ribs_points():
    h.check("clicked the sketch's row", ps.click_row("Boss Points"))


def ribs_on():
    p = ps.boss_panel()
    ps.settle(p)
    s["rv1"] = ps.volume(App.ActiveDocument.getObject(s["rb"]))
    ps.tab_of(p, "Ribs")
    ps.check_box(p.rib_on[2])


def ribs_default():
    """The default ribs (4, at 0 / 90 / 180 / 270 deg, 7.75 mm from the axis) of the bosses at
    (10, 10) and (50, 30) end 0.25 mm short of the case's inside walls: OpenCASCADE cannot
    round their base there. The boss is built (those rib ends square) and the dialog says
    so; it used to refuse the whole boss."""
    p = ps.boss_panel()
    ps.settle(p)
    b = App.ActiveDocument.getObject(s["rb"])
    text = p.message.text() if p else ""
    h.check("no refusal", p is not None and not text.startswith("⚠"), text)
    h.check("the dialog says which rib ends stay square", "left square" in text, text)
    h.check("the ribs are built", ps.volume(b) > s["rv1"] + 50.0, (ps.volume(b), s["rv1"]))
    h.check("one valid solid", b.Shape.isValid() and len(b.Shape.Solids) == 1)
    ps.tab_of(p, "Boss")
    ps.check_box(p.fastener)
    ps.settle(p)
    ps.choose(p.head, "Flat (countersunk)")


def flat_refused():
    """A Flat (countersunk) head on the counterbore's floor would sink into the part."""
    p = ps.boss_panel()
    ps.settle(p)
    text = p.message.text() if p else ""
    h.check(
        "a Flat head without a countersink is refused, said why",
        "needs a countersink" in text,
        text,
    )
    ps.choose(p.head, "Pan")


def pan_ok():
    p = ps.boss_panel()
    ps.settle(p)
    text = p.message.text() if p else ""
    h.check("Pan: built again (no refusal)", p is not None and not text.startswith("⚠"), text)
    ps.ok()


def ribs_done():
    h.check("OK closes the Boss", ps.boss_panel() is None)
    steps = boss_steps()
    h.check(
        "both steps valid",
        len(steps) == 2 and all("Invalid" not in o.State for o in steps),
        [o.State for o in steps],
    )
    App.closeDocument(App.ActiveDocument.Name)


h.run(
    "plastic_qa_tools",
    [
        face_setup,
        click_floor,
        standoff_previewed,
        esc,
        face_esc_dropped,
        rest_setup,
        click_landing,
        rest_drafted,
        esc,
        rest_esc_dropped,
        rest_again,
        rest_ok,
        rest_made,
        rest_follows,
        rest_edit_shows_rule,
        rest_closed,
        reopen_setup,
        click_points_row,
        side1_lid,
        lid_picked,
        flip_moves_pick,
        unflipped,
        boss_ok,
        boss_made,
        save_reopen,
        reopened,
        reopened_editing,
        offset_moved,
        counterbore_drafted,
        drafted_mouth_refused,
        edit_ok,
        edit_kept,
        undo,
        edit_undone,
        pick_pmma,
        boss_follows_rule,
        boss_edit_shows_rule,
        boss_edit_closed,
        comp_setup,
        comp_assign_cover,
        comp_boss,
        comp_points,
        comp_previewed,
        comp_done,
        comp_undone,
        ribs_setup,
        ribs_points,
        ribs_on,
        ribs_default,
        flat_refused,
        pan_ok,
        ribs_done,
    ],
)
