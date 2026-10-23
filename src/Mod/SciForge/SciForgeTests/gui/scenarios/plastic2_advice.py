# SPDX-License-Identifier: LGPL-2.1-or-later
"""PLASTIC > INSPECT > Design Advice, like a Fusion user, real input.

A base (60 x 40 x 20, 2 mm walls without draft, open top) and a solid 20 mm block beside it,
the design's root following the plastic rule "ABS 2 mm" (range 1.2 .. 3.5 mm, minimum draft
0.5 degrees). INSPECT > Design Advice: both bodies are taken, the rule is named, the faces
are coloured and the issues listed: the walls have no draft, the block is too thick. A click
on an issue selects its face (the view zooms to it). Draft unticked: no draft issues left.
Display Thickness: still drawn. A click on the block in the view leaves it out (1 body, no
thickness issue), a second click takes it back. OK: "Design Advice1" in the browser's
Analysis folder; its eye hides and shows the colours. Double-click the row: the dialog again
with its list; Esc. The block made 3 mm tall: the analysis checks again by itself (no
thickness issue). Save, close, reopen: the analysis is back with its results. A second
Design Advice with its bodies box cleared: OK refused with the reason; Cancel leaves one.
An empty design: Design Advice says what is needed, no dialog. A round boss reads its
1.5 mm wall from both of its round faces, and its hole is no undercut.
"""

import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore
from PySide6 import QtTest

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plastic2_steps as ps
from SciForgeTests.gui import versions_input as vi

V = App.Vector
s = {}


def setup():
    from sciforge import plastic

    base, _lid = ps.enclosure("Advice", lid=None)
    d = ps.doc()
    block = d.addObject("PartDesign::Body", "Block")
    block.Label = "Block"
    ps._box(block, "Additive", "BlockBox", (20, 20, 20), (80, 0, 0))
    plastic.assign_rule(d, "ABS 2 mm", None)
    d.recompute()
    s["base"], s["block"] = base, block
    h.fit()
    h.check("the rule is assigned", plastic.assigned_rule_name(d, None) == "ABS 2 mm")


def open_advice():
    ps.plastic_tab()
    ps.menu("INSPECT", "Design Advice")


def results():
    from sciforge import plastic_advice

    p = ps.advice_panel()
    obj = p.analysis if p is not None else s.get("analysis")
    return plastic_advice.results(obj) if obj is not None else {"bodies": []}


def counts():
    from sciforge import plastic_advice_core as core

    return core.summary(results())


def first_look():
    ps.settle(ps.advice_panel)
    p = ps.advice_panel()
    if not h.check("the Design Advice dialog is open", p is not None):
        return
    s["analysis"] = p.analysis
    h.check("both bodies", p.bodies_field.button.text() == "2 bodies", p.bodies_field.button.text())
    h.check("the rule is named", "ABS 2 mm" in p.rules.text(), p.rules.text())
    c = counts()
    h.check("the walls have no draft", c["draft"] >= 8, c)
    h.check("the block is too thick", c["thickness"] >= 6, c)
    h.check("no undercut in an open box", c["undercut"] == 0, c)
    h.check("the summary", "Draft" in p.summary.text(), p.summary.text())
    h.check("issues listed", p.issues.topLevelItemCount() > 10, p.issues.topLevelItemCount())
    drawn = p.analysis.ViewObject.Proxy.drawn
    h.check("both bodies coloured", set(drawn) == {"Base", "Block"}, drawn)
    h.shot("plastic2_advice_issues")
    item = p.issues.topLevelItem(0)
    s["first"] = item.data(0, QtCore.Qt.UserRole)
    rect = p.issues.visualItemRect(item)
    QtTest.QTest.mouseClick(
        p.issues.viewport(), QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, rect.center()
    )


def issue_clicked():
    QtTest.QTest.qWait(300)
    sel = Gui.Selection.getSelectionEx()
    names = [n for x in sel for n in x.SubElementNames]
    name, element = s["first"]
    h.check("the issue's face is selected", element in names, (names, s["first"]))
    p = ps.advice_panel()
    h.check("still both bodies (the zoom is no pick)", p.bodies_field.button.text() == "2 bodies")
    ps.toggle(p.checks["draft"])


def no_draft_check():
    ps.settle(ps.advice_panel)
    c = counts()
    h.check("Draft unticked: no draft issues", c["draft"] == 0, c)
    h.check("thickness still checked", c["thickness"] >= 6, c)
    ps.choose(ps.advice_panel().display, "Thickness")


def thickness_map():
    ps.settle(ps.advice_panel)
    p = ps.advice_panel()
    h.check("Display Thickness", p.analysis.Display == "Thickness")
    h.check("still drawn", len(p.analysis.ViewObject.Proxy.drawn) == 2)
    faces = plastic_results()["bodies"][0]["faces"]
    sampled = [n for n, d in faces.items() if d.get("samples")]
    h.check("the map is shaded from the faces' samples", len(sampled) >= 8, sampled)
    h.shot("plastic2_advice_thickness")
    h.click(V(90, 10, 20))


def plastic_results():
    return results()


def block_left_out():
    ps.settle(ps.advice_panel)
    p = ps.advice_panel()
    h.check(
        "a click leaves the block out",
        p.bodies_field.button.text() == "1 body",
        p.bodies_field.button.text(),
    )
    c = counts()
    h.check("no thickness issue left", c["thickness"] == 0, c)
    h.click(V(90, 10, 20))


def block_back():
    ps.settle(ps.advice_panel)
    p = ps.advice_panel()
    h.check("a second click takes it back", p.bodies_field.button.text() == "2 bodies")
    ps.ui.click(p.direction_field.button)


def click_front_for_pull():
    h.check("the Pull Direction box takes the clicks", ps.advice_panel().active == "direction")
    h.fit()
    h.click(V(30, 0, 10))


def pulled_along_y():
    ps.settle(ps.advice_panel)
    p = ps.advice_panel()
    text = p.direction_field.button.text()
    h.check("the pull is the front face's normal", "Face" in text, text)
    h.check("back to the Bodies box", p.active == "bodies")
    pull = p.analysis.PullVector
    h.check("pulled along Y", abs(abs(pull.y) - 1.0) < 1e-9, pull)
    c = counts()
    h.check("pulled along Y the box's inside is an undercut", c["undercut"] > 0, c)
    ps.toggle(p.flip)


def flipped():
    ps.settle(ps.advice_panel)
    p = ps.advice_panel()
    h.check("Flip turns the pull round", p.analysis.Flip, p.analysis.Flip)
    ps.ui.click(p.direction_field.clear)


def pull_cleared():
    ps.settle(ps.advice_panel)
    p = ps.advice_panel()
    h.check("cleared: Z again", p.direction_field.button.text() == "Z (default)")
    h.check("no undercut along Z", counts()["undercut"] == 0, counts())
    ps.toggle(p.flip)


def unflipped():
    ps.settle(ps.advice_panel)
    ps.ok()


def kept():
    h.check("the dialog closed", ps.advice_panel() is None)
    labels = ps.tl.labels()
    h.check("Design Advice1 in the browser", "Design Advice1" in labels, labels)
    titles = ps.titles()
    h.check("not a timeline step", not any("Advice" in t for t in titles), titles)
    h.check("shown", s["analysis"].ViewObject.Visibility)
    ps.click_eye("Design Advice1")


def hidden():
    QtTest.QTest.qWait(300)
    h.check("the eye hides it", not s["analysis"].ViewObject.Visibility)
    h.check("nothing drawn", not s["analysis"].ViewObject.Proxy.drawn)
    ps.click_eye("Design Advice1")


def shown_again():
    QtTest.QTest.qWait(300)
    h.check("the eye shows it again", s["analysis"].ViewObject.Visibility)
    h.check("drawn again", len(s["analysis"].ViewObject.Proxy.drawn) == 2)
    ps.tl.double_click_row("Design Advice1")


def edit_again():
    ps.settle(ps.advice_panel)
    p = ps.advice_panel()
    if not h.check("double-click opens it again", p is not None and p.editing):
        return
    h.check("its issues listed", p.issues.topLevelItemCount() > 0)
    h.check("Draft still unticked", not p.checks["draft"].isChecked())
    ps.esc()


def follows_the_design():
    h.check("Esc closed it", ps.advice_panel() is None)
    h.check("Esc kept it", ps.by_label("Design Advice1") is not None)
    box = ps.doc().getObject("BlockBox")
    box.Height = 3.0  # the block edited to 3 mm (its own dialog is not under test here)
    ps.doc().recompute()
    c = counts()
    h.check("checked again: the 3 mm block is fine", c["thickness"] == 0, c)
    ps.click_eye("Design Advice1")


def changed_while_hidden():
    QtTest.QTest.qWait(300)
    h.check("hidden", not s["analysis"].ViewObject.Visibility)
    box = ps.doc().getObject("BlockBox")
    box.Height = 20.0  # back to a 20 mm block while the analysis is hidden
    ps.doc().recompute()
    h.check("a hidden analysis waits", s["analysis"].Stale)
    h.check("its results are the old ones", counts()["thickness"] == 0, counts())
    ps.click_eye("Design Advice1")


def shown_checks_again():
    QtTest.QTest.qWait(600)
    h.check("shown again", s["analysis"].ViewObject.Visibility)
    h.check("checked now", not s["analysis"].Stale)
    c = counts()
    h.check("the 20 mm block is too thick again", c["thickness"] >= 6, c)
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-advice-"), "advice.FCStd")
    s["path"] = path
    s["summary"] = s["analysis"].Summary
    ps.doc().saveAs(path)


def ctrl_s():
    h.press(QtCore.Qt.Key_S, QtCore.Qt.ControlModifier)


def describe():
    vi.accept_save()


def close_reopen():
    App.closeDocument(ps.doc().Name)
    App.openDocument(s["path"])
    h.fit()


def reopened():
    obj = ps.by_label("Design Advice1")
    if not h.check("the analysis is back", obj is not None):
        return
    s["analysis"] = obj
    ps.doc().recompute()
    h.check("with its results", obj.Summary == s["summary"], (obj.Summary, s["summary"]))
    QtTest.QTest.qWait(300)
    h.check(
        "drawn after reopening", len(obj.ViewObject.Proxy.drawn) == 2, obj.ViewObject.Proxy.drawn
    )
    ps.plastic_tab()
    ps.menu("INSPECT", "Design Advice")


def second_one():
    ps.settle(ps.advice_panel)
    p = ps.advice_panel()
    if not h.check("a second Design Advice", p is not None and not p.editing):
        return
    ps.ui.click(p.bodies_field.clear)


def cleared():
    ps.settle(ps.advice_panel)
    p = ps.advice_panel()
    h.check(
        "no bodies", p.bodies_field.button.text() == "Select bodies", p.bodies_field.button.text()
    )
    ps.ok()


def refused():
    p = ps.advice_panel()
    h.check("OK refused: the dialog stays", p is not None)
    if p is None:
        return
    h.check("it says why", "bodies" in ps.message(p).lower(), ps.message(p))
    ps.cancel()


def one_left():
    from sciforge import plastic_advice

    h.check("Cancel left nothing", len(plastic_advice.advices(ps.doc())) == 1)
    App.newDocument("Empty")
    ps.plastic_tab()
    ps.menu("INSPECT", "Design Advice")


def empty_design():
    QtTest.QTest.qWait(300)
    h.check(
        "an empty design: no dialog", ps.advice_panel() is None and not Gui.Control.activeDialog()
    )


def round_walls():
    """A round boss (radius 3 mm, a 1.5 mm hole through it: a 1.5 mm wall). The display
    triangles cut corners off its round faces: the walls must still read 1.5 mm from both
    sides (not the corner the triangles cut), and the hole is no undercut."""
    from sciforge import plastic, plastic_advice

    d = App.newDocument("Round")
    body = d.addObject("PartDesign::Body", "Boss")
    outer = body.newObject("PartDesign::AdditiveCylinder", "Outer")
    outer.Radius, outer.Height = 3, 10
    hole = body.newObject("PartDesign::SubtractiveCylinder", "Hole")
    hole.Radius, hole.Height = 1.5, 10
    body.Tip = hole
    plastic.assign_rule(d, "ABS 2 mm", None)
    d.recompute()
    obj = plastic_advice.make(d, [body])
    d.recompute()
    faces = (plastic_advice.results(obj).get("bodies") or [{}])[0].get("faces", {})
    round_faces = [
        n for n in faces if body.Shape.getElement(n).Surface.TypeId == "Part::GeomCylinder"
    ]
    h.check("both round faces measured", len(round_faces) == 2, sorted(faces))
    readings = [(faces[n]["t_min"], faces[n]["t_max"]) for n in round_faces]
    h.check(
        "the round walls read 1.5 mm from both sides",
        all(abs(a - 1.5) < 1e-3 and abs(b - 1.5) < 1e-3 for a, b in readings),
        readings,
    )
    h.check(
        "the hole is no undercut",
        not any("undercut" in data["issues"] for data in faces.values()),
        {n: data["issues"] for n, data in faces.items()},
    )


h.run(
    "plastic2_advice",
    [
        setup,
        open_advice,
        first_look,
        issue_clicked,
        no_draft_check,
        thickness_map,
        block_left_out,
        block_back,
        click_front_for_pull,
        pulled_along_y,
        flipped,
        pull_cleared,
        unflipped,
        kept,
        hidden,
        shown_again,
        edit_again,
        follows_the_design,
        changed_while_hidden,
        shown_checks_again,
        ctrl_s,
        describe,
        close_reopen,
        reopened,
        second_one,
        cleared,
        refused,
        one_left,
        empty_design,
        round_walls,
    ],
)
