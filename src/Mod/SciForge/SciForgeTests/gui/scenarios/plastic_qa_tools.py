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
    ps.ok()


def edit_kept():
    b, l = parts()
    h.check("OK: closed", ps.boss_panel() is None)
    h.check("OK keeps the move", ps.near(ps.volume(b), s["vb1"], 1e-6), ps.volume(b))
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
        boss_ok,
        boss_made,
        save_reopen,
        reopened,
        reopened_editing,
        offset_moved,
        edit_kept,
        undo,
        edit_undone,
        pick_pmma,
        boss_follows_rule,
        boss_edit_shows_rule,
        boss_edit_closed,
    ],
)
