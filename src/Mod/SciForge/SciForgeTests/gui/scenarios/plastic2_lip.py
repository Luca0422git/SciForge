# SPDX-License-Identifier: LGPL-2.1-or-later
"""PLASTIC > Lip on a base and the groove in its lid, like a Fusion user, real input.

A base (60 x 40 x 20, 2 mm walls, open top) and a lid on it (60 x 40 x 10, 2 mm walls, open
bottom). The lid is hidden with its eye in the browser; PLASTIC tab > Lip; the four inside
edges of the base's rim are clicked. Lip And Groove with the default rule (lip 1 x 1, 1
degree drafts, clearance 0.1): the base gains 184.718, the lid loses 225.929 (hand-worked,
golden model plastic2_lip_drafted). Inner / Outer Draft typed 0, Lip Height 1.5: the base
gains (58 x 38 - 56 x 36) x 1.5 = 282, the lid loses (58.2 x 38.2 - 56 x 36) x 1.6 = 331.584.
The height arrow dragged: the lip follows. Swap: the other way round. Type Groove: the lid
is left alone, the base loses 207.24 x 1.1 = 227.964. Type Lip: only the lip. Lip Width 2.5
(wider than the 2 mm wall): refused in the dialog, OK keeps it open. Back to Lip And Groove,
OK: one "Lip 1" in the timeline. Undo / Redo. Double-click "Lip 1": the values read back;
Lip Height 1, OK. Double-click again, 2, Esc: unchanged. Save, close, reopen: the same.
"""

import os
import tempfile

import FreeCAD as App
from PySide import QtCore

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plastic2_steps as ps
from SciForgeTests.gui import versions_input as vi

V = App.Vector
s = {}
LIP_DRAFTED = 184.71844779349476
GROOVE_DRAFTED = 225.92851211069762
BAND = 58 * 38 - 56 * 36  # 188: the lip's band
GBAND = 58.2 * 38.2 - 56 * 36  # 207.24: the groove's band in the lid's wall
EDGES = [V(30, 2, 20), V(30, 38, 20), V(2, 20, 20), V(58, 20, 20)]


def changes():
    return ps.volume(s["base"]) - ps.BASE, ps.volume(s["lid"]) - ps.LID_SHELL


def setup():
    base, lid = ps.enclosure("Lip", lid="shell")
    s["base"], s["lid"] = base, lid
    h.fit()
    h.check("the enclosure", ps.near(ps.volume(base), ps.BASE) and ps.near(ps.volume(lid), 7872))


def hide_lid():
    ps.click_eye("Lid")


def open_lip():
    h.check("the lid is hidden", not s["lid"].ViewObject.Visibility)
    ps.plastic_tab()
    h.ribbon("Lip")


def asks_for_edges():
    p = ps.lip_panel()
    h.check("the Lip dialog is open", p is not None)
    if p is None:
        return
    h.check("it asks for the rim's edges", "edges" in ps.message(p).lower(), ps.message(p))
    h.check("Lip And Groove first", p.type.currentText() == "Lip And Groove")
    h.fit()
    h.click_edge(EDGES[0])


def click_edge(i):
    def step():
        ps.settle(ps.lip_panel)
        p = ps.lip_panel()
        text = p.field.button.text() if p is not None else ""
        h.check("edge %d picked" % i, text.startswith("%d edge" % i), (text, ps.message(p)))
        h.click_edge(EDGES[i])

    step.__name__ = "click_edge_%d" % (i + 1)
    return step


def lip_and_groove():
    ps.settle(ps.lip_panel)
    p = ps.lip_panel()
    if not h.check("still open", p is not None):
        return
    h.check(
        "4 edges picked",
        p.field.button.text() == "4 edges",
        (p.field.button.text(), p.names, ps.message(p)),
    )
    base, lid = changes()
    h.check("the lip on the base: +184.718", ps.near(base, LIP_DRAFTED, 1e-6), base)
    h.check("the groove in the lid: -225.929", ps.near(-lid, GROOVE_DRAFTED, 1e-6), lid)
    h.check("the other body is the lid", p.mate_label.text() == "Lid", p.mate_label.text())
    h.check("no error", "⚠" not in ps.message(p), ps.message(p))
    h.check("two arrows (height, width)", set(p.arrows) == {"lip_height", "lip_width"})
    h.shot("plastic2_lip_drafted")
    ps.ui.click(p.mate_field.button)


def click_base_as_mate():
    h.check("the Other Body box takes the clicks", ps.lip_panel().active == "mate")
    h.click(V(30, 0, 10))


def mate_refused():
    ps.settle(ps.lip_panel)
    p = ps.lip_panel()
    text = ps.message(p)
    h.check("the edges' own body cannot be the other body", "cannot be the one" in text, text)
    h.check("the lid stays the other body", p.mate_label.text() == "Lid", p.mate_label.text())
    ps.ui.click(p.field.button)
    ps.type_field(p, "inner_draft", "0")


def outer_draft():
    ps.settle(ps.lip_panel)
    ps.type_field(ps.lip_panel(), "outer_draft", "0")


def height():
    ps.settle(ps.lip_panel)
    base, lid = changes()
    h.check("no drafts: lip 188", ps.near(base, BAND, 1e-6), base)
    h.check("no drafts: groove 227.964", ps.near(-lid, GBAND * 1.1, 1e-6), lid)
    ps.type_field(ps.lip_panel(), "lip_height", "1.5")


def taller():
    ps.settle(ps.lip_panel)
    base, lid = changes()
    h.check("Lip Height 1.5: +282", ps.near(base, BAND * 1.5, 1e-6), base)
    h.check("the groove 0.1 deeper: -331.584", ps.near(-lid, GBAND * 1.6, 1e-6), lid)
    s["drag"] = ps.drag_arrow(ps.lip_panel(), "lip_height", 2.5)


def dragged():
    ps.settle(ps.lip_panel)
    p = ps.lip_panel()
    value = p.options["lip_height"]
    h.check("the height arrow dragged: taller", value > 1.8, value)
    base, _lid = changes()
    h.check("the lip follows the arrow", ps.near(base, BAND * value, 1e-6), (base, value))
    ps.type_field(p, "lip_height", "1.5")


def swap():
    ps.settle(ps.lip_panel)
    ps.toggle(ps.lip_panel().swap)


def swapped():
    ps.settle(ps.lip_panel)
    base, lid = changes()
    h.check("Swap: the groove in the base", ps.near(-base, GBAND * 1.6, 1e-6), base)
    h.check("Swap: the lip on the lid", ps.near(lid, BAND * 1.5, 1e-6), lid)
    ps.toggle(ps.lip_panel().swap)


def groove_type():
    ps.settle(ps.lip_panel)
    ps.choose(ps.lip_panel().type, "Groove")


def groove_only():
    ps.settle(ps.lip_panel)
    p = ps.lip_panel()
    base, lid = changes()
    h.check("Groove: the lid is left alone", ps.near(lid, 0.0, 1e-9), lid)
    h.check("Groove: 1.1 wide, 1.1 deep in the base", ps.near(-base, GBAND * 1.1, 1e-6), base)
    h.check("Groove shows its own width", p.fields["groove_width"].widget.isVisible())
    h.check("no other body for a groove alone", not ps.followers(p.target))
    ps.choose(p.type, "Lip")


def lip_only():
    ps.settle(ps.lip_panel)
    base, lid = changes()
    h.check("Lip: only the lip", ps.near(base, BAND * 1.5, 1e-6) and ps.near(lid, 0.0), (base, lid))
    ps.type_field(ps.lip_panel(), "lip_width", "2.5")


def too_wide():
    ps.settle(ps.lip_panel)
    p = ps.lip_panel()
    text = ps.message(p)
    h.check("Lip Width 2.5 refused: wider than the wall", "less than the wall" in text, text)
    ps.ok()


def ok_refused():
    p = ps.lip_panel()
    h.check("OK keeps the dialog open", p is not None)
    if p is None:
        return
    ps.type_field(p, "lip_width", "1")


def back_to_both():
    ps.settle(ps.lip_panel)
    ps.choose(ps.lip_panel().type, "Lip And Groove")


def both_again():
    ps.settle(ps.lip_panel)
    base, lid = changes()
    h.check("Lip And Groove again: +282", ps.near(base, BAND * 1.5, 1e-6), base)
    h.check("and the groove again: -331.584", ps.near(-lid, GBAND * 1.6, 1e-6), lid)
    ps.choose(ps.lip_panel().guide, "Face Guide")


def face_guide_square():
    ps.settle(ps.lip_panel)
    p = ps.lip_panel()
    base, lid = changes()
    h.check("Face Guide on square walls: no refusal", "⚠" not in ps.message(p), ps.message(p))
    h.check("Face Guide: the same lip", ps.near(base, BAND * 1.5, 1e-6), base)
    h.check("no Direction box for Face Guide", not p.direction_field.widget.isVisible())
    ps.choose(p.guide, "Pull Direction")


def direction_box():
    ps.settle(ps.lip_panel)
    p = ps.lip_panel()
    h.check("the Direction box for Pull Direction", p.direction_field.widget.isVisible())
    ps.ui.click(p.direction_field.button)


def click_front_face():
    h.check("the Direction box takes the clicks", ps.lip_panel().active == "direction")
    h.fit()
    h.click(V(30, 0, 10))


def direction_picked():
    ps.settle(ps.lip_panel)
    p = ps.lip_panel()
    text = p.direction_field.button.text()
    h.check("a direction picked", text == "Picked direction", (text, ps.message(p)))
    h.check("the edges box takes the clicks again", p.active == "edges")
    msg = ps.message(p)
    h.check("the front face's normal lies along the rim: refused", "along the rim" in msg, msg)
    ps.ui.click(p.direction_field.clear)


def direction_cleared():
    ps.settle(ps.lip_panel)
    p = ps.lip_panel()
    text = p.direction_field.button.text()
    h.check("cleared: the rim's normal again", text == "Rim normal", text)
    h.check("no refusal now", "⚠" not in ps.message(p), ps.message(p))
    h.check("the same lip", ps.near(changes()[0], BAND * 1.5, 1e-6), changes())
    ps.ok()


def one_step():
    p = ps.lip_panel()
    h.check("the dialog closed", p is None, ps.message(p))
    titles = ps.titles()
    h.check("one Lip in the timeline", titles.count("Lip 1") == 1, titles)
    s["after"] = changes()
    ps.undo()


def undone():
    base, lid = changes()
    h.check("Undo: both as before", ps.near(base, 0.0) and ps.near(lid, 0.0), (base, lid))
    ps.redo()


def redone():
    base, lid = changes()
    h.check("Redo: lip and groove", ps.near(base, s["after"][0]) and ps.near(lid, s["after"][1]))
    h.check("double-click opens the edit", ps.double_click_timeline("Lip 1"))


def edit_reads_back():
    p = ps.lip_panel()
    if not h.check("the edit dialog", p is not None and p.editing):
        return
    h.check("Lip Height read back", ps.near(p.options["lip_height"], 1.5), p.options)
    h.check("drafts read back", ps.near(p.options["inner_draft"], 0.0), p.options)
    h.check("4 edges", p.field.button.text() == "4 edges", p.field.button.text())
    ps.type_field(p, "lip_height", "1")


def edit_ok():
    ps.settle(ps.lip_panel)
    ps.ok()


def edited():
    base, lid = changes()
    h.check("edited: lip 188", ps.near(base, BAND, 1e-6), base)
    h.check("edited: groove 227.964", ps.near(-lid, GBAND * 1.1, 1e-6), lid)
    s["after"] = (base, lid)
    ps.double_click_timeline("Lip 1")


def edit_again():
    p = ps.lip_panel()
    if not h.check("the edit dialog again", p is not None):
        return
    ps.type_field(p, "lip_height", "2")


def esc():
    ps.settle(ps.lip_panel)
    base, _lid = changes()
    h.check("the preview shows 2", ps.near(base, BAND * 2, 1e-6), base)
    ps.esc()


def esc_keeps():
    h.check("Esc closed it", ps.lip_panel() is None)
    base, lid = changes()
    h.check("Esc: unchanged", ps.near(base, s["after"][0]) and ps.near(lid, s["after"][1]))
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-lip-"), "lip.FCStd")
    s["path"] = path
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
    s["base"], s["lid"] = ps.by_label("Base"), ps.by_label("Lid")
    if not h.check("both bodies are back", None not in (s["base"], s["lid"])):
        return
    ps.doc().recompute()
    base, lid = changes()
    h.check("reopened: the same lip and groove", ps.near(base, BAND) and ps.near(-lid, GBAND * 1.1))
    lips = ps.lip_steps()
    h.check("one Lip step and its groove step", len(lips) == 1 and len(ps.followers(lips[0])) == 1)
    bad = [o.Name for o in ps.doc().Objects if "Invalid" in o.State or "Error" in o.State]
    h.check("every step computed", not bad, bad)
    cone_design()


def cone_design():
    """A cone frustum (radius 10 at the bottom, 8 at the top, 10 high): its top face's rim
    leans (the cone's side)."""
    d = App.newDocument("LipCone")
    body = d.addObject("PartDesign::Body", "Cone")
    body.Label = "Cone"
    cone = body.newObject("PartDesign::AdditiveCone", "ConeShape")
    cone.Radius1, cone.Radius2, cone.Height = 10, 8, 10
    body.Tip = cone
    d.recompute()
    s["cone"] = body
    s["cone_volume"] = ps.volume(body)
    h.fit()
    ps.plastic_tab()
    h.ribbon("Lip")


def cone_lip_type():
    p = ps.lip_panel()
    if not h.check("the Lip dialog on the cone", p is not None):
        return
    ps.choose(p.type, "Lip")


def click_cone_rim():
    ps.settle(ps.lip_panel)
    h.click_edge(V(0, -8, 10))


def cone_lip():
    ps.settle(ps.lip_panel)
    p = ps.lip_panel()
    added = ps.volume(s["cone"]) - s["cone_volume"]
    # a 1 x 1 ring inside the 8 mm rim: (64 - 49) pi = 47.12, a little less with 1 degree drafts
    h.check("a lip ring on the cone's top", 45.0 < added < 47.2, (added, ps.message(p)))
    ps.choose(p.guide, "Face Guide")


def cone_face_guide():
    ps.settle(ps.lip_panel)
    p = ps.lip_panel()
    text = ps.message(p)
    h.check("Face Guide refused on the leaning cone side, with the reason", "leans" in text, text)
    ps.ok()


def cone_ok_refused():
    p = ps.lip_panel()
    h.check("OK refused: the dialog stays", p is not None)
    if p is not None:
        ps.choose(p.guide, "Pull Direction")


def cone_ok():
    ps.settle(ps.lip_panel)
    ps.ok()


def cone_done():
    h.check("Pull Direction again: OK closes it", ps.lip_panel() is None)
    h.check("one Lip on the cone", len(ps.lip_steps()) == 1)


h.run(
    "plastic2_lip",
    [
        setup,
        hide_lid,
        open_lip,
        asks_for_edges,
        click_edge(1),
        click_edge(2),
        click_edge(3),
        lip_and_groove,
        click_base_as_mate,
        mate_refused,
        outer_draft,
        height,
        taller,
        dragged,
        swap,
        swapped,
        groove_type,
        groove_only,
        lip_only,
        too_wide,
        ok_refused,
        back_to_both,
        both_again,
        face_guide_square,
        direction_box,
        click_front_face,
        direction_picked,
        direction_cleared,
        one_step,
        undone,
        redone,
        edit_reads_back,
        edit_ok,
        edited,
        edit_again,
        esc,
        esc_keeps,
        ctrl_s,
        describe,
        close_reopen,
        reopened,
        cone_lip_type,
        click_cone_rim,
        cone_lip,
        cone_face_guide,
        cone_ok_refused,
        cone_ok,
        cone_done,
    ],
)
