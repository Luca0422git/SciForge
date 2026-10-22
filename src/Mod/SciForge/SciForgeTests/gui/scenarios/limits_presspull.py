# SPDX-License-Identifier: LGPL-2.1-or-later
"""Press Pull: a distance or radius past what works stops at the furthest one that does
(Luca, 2026-10-21; Fusion refuses it, this is Luca's decision). Only real input.

Box 40 x 30 x 10, Q, the top face: the arrow dragged far down into the part (button held,
slowly) stops just before the push would remove the whole body (-9.99 mm), the arrow too;
the preview is that thin slab, the note says "Furthest that fits here: -9.99 mm", no
error, one search for the whole drag; dragged back up the distance follows and the note
goes; -50 typed is held at the limit and said; OK at once.

A second box, Q on the front top edge (a fillet): 50 typed is held at the largest radius
(just under 10 mm), OK; the fillet face clicked with Q again edits that radius: 50 is held
there too; a formula that is too big (parameter big = 40 mm) is not rewritten: explained,
with the limit."""
import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import arrow_input as a
from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h

V = App.Vector
s = {}
TOP = V(20, 15, 10)
FRONT_TOP = V(20, 0, 10)


def panel():
    from sciforge import presspull_ui

    p = presspull_ui.PressPullPanel.last
    return p if p is not None and not p._closed else None


def note(p):
    return p.limit_label.text() if p is not None and p.limit_label.isVisible() else ""


def msg(p):
    return p.message.text() if p is not None else ""


def slab(d):
    return 1200.0 * (10.0 + d)


def held(along, name):
    p = panel()
    if p is None or p.dragger is None:
        h.check("%s: the arrow" % name, False)
        return
    dragger = p.dragger
    head = a.head_point(dragger)
    s["samples"] = []

    def sample(_index):
        q = panel()
        if q is not None:
            s["samples"].append(q.field.value())

    s["drag"] = a.HeldDrag(
        h.screen_point(head),
        h.screen_point(head + dragger.direction * along),
        moves=30,
        every_ms=40,
        hold_ms=400,
        sample=sample,
    )
    s["drag"].run()


# -- faces ------------------------------------------------------------------------------------
def q_top():
    h.click_empty()
    h.press("q")


def click_top():
    h.fit()
    h.click(TOP)


def top_picked():
    p = panel()
    h.check("Press Pull: the top face", p is not None and len(p.names) == 1, p and p.names)
    h.check("its arrow", p is not None and p.dragger is not None)
    s["searches"] = p.limits.searches if p else 0


def drag_down():
    held(-30.0, "push down")


def pushed_far():
    p = panel()
    if p is None:
        h.check("dialog open after the drag", False)
        return
    d = p.field.value()
    s["d"] = d
    h.check("the push stopped just before it removes the body", -10.0 < d < -9.0, d)
    h.check("no error", msg(p) == "", msg(p))
    h.check(
        "the note",
        note(p) == "Furthest that fits here: %.2f mm" % d,
        (note(p), p.limits.note, p.limit_label.text(), p.limit_label.isVisible()),
    )
    v = h.solid_volume()
    h.check("the preview is that slab", b.close(v, slab(d)), (v, slab(d)))
    h.check(
        "worked out once for the whole drag",
        p.limits.searches - s["searches"] == 1,
        p.limits.searches - s["searches"],
    )
    h.check(
        "the arrow stopped at the limit",
        abs(p.dragger.distance() - d) < 1e-6,
        (p.dragger.distance(), d),
    )
    h.shot("1-push-held")


pushed_far.wait_ms = 3000


def drag_up():
    held(4.0, "back up")


def back_up():
    p = panel()
    d = p.field.value() if p else 0
    h.check("dragged back up, the distance follows", s["d"] + 1.0 < d < 0.0, d)
    h.check("the note went", note(p) == "", note(p))
    v = h.solid_volume()
    h.check("the preview follows", b.close(v, slab(d)), (v, slab(d)))


back_up.wait_ms = 1500


def type_minus_50():
    p = panel()
    if p:
        b.type_into(p.field.widget, "-50")


def typed_minus_50():
    p = panel()
    h.check(
        "-50 is held at the limit, and said",
        note(p) == "-50 mm does not fit: limited to %.2f mm" % s["d"],
        note(p),
    )
    h.check("no error", msg(p) == "", msg(p))
    h.task_button("OK")


typed_minus_50.wait_ms = 1500


def pushed():
    h.check("OK worked at once", panel() is None and not Gui.Control.activeDialog())
    v = h.solid_volume()
    h.check("the part is the thinnest slab", b.close(v, slab(s["d"])), v)
    h.check("valid solid", h.body().Shape.isValid())


# -- an edge (fillet), then its fillet face -----------------------------------------------------
def q_edge():
    Gui.Selection.clearSelection()
    h.click_empty()
    h.press("q")


def click_edge():
    h.fit()
    h.click_edge(FRONT_TOP)


def edge_picked():
    p = panel()
    h.check("Press Pull on an edge: a fillet", p is not None and p.mode == "fillet", p and p.mode)
    if p:
        b.type_into(p.field.widget, "50")


def fillet_held():
    p = panel()
    r = p.target.Radius.Value if p and p.target is not None else 0
    s["r"] = r
    h.check("50 is held at the largest radius", 9.0 < r <= 10.0, r)
    h.check("and said", note(p) == "50 mm does not fit: limited to %.2f mm" % r, note(p))
    h.check("no error", msg(p) == "", msg(p))
    h.task_button("OK")


fillet_held.wait_ms = 2500


def fillet_made():
    h.check("OK worked at once", panel() is None and not Gui.Control.activeDialog())
    h.check("valid solid", h.body().Shape.isValid())
    from sciforge import parameters

    parameters.add_user(App.ActiveDocument, "big", "mm", "40")


def q_fillet_face():
    Gui.Selection.clearSelection()
    h.click_empty()
    h.press("q")


def click_fillet_face():
    h.fit()
    # the middle of the round on the front top edge
    import math

    r = s["r"]
    h.click(V(20, r - r * math.cos(math.pi / 4), 10 - r + r * math.sin(math.pi / 4)))


def editing_fillet():
    p = panel()
    h.check("the fillet face edits its radius", p is not None and p.mode == "edit_blend")
    if p:
        b.type_into(p.field.widget, "50")


def edit_held():
    p = panel()
    h.check("50 is held there too", note(p).startswith("50 mm does not fit"), note(p))
    h.check("no error", msg(p) == "", msg(p))
    if p:
        ui.type_into(p.field.widget, "big")


edit_held.wait_ms = 2500


def formula_explained():
    p = panel()
    text = msg(p)
    h.check("a formula is not rewritten", p is not None and p.formula == "big", p and p.formula)
    h.check("explained", text.startswith("⚠"), text)
    h.check("with the limit", "Largest that fits here: %.2f mm" % s["r"] in text, text)
    h.task_button("Cancel")


formula_explained.wait_ms = 3000


def cancelled():
    h.check("Cancel closed it", not Gui.Control.activeDialog())
    h.check("valid solid", h.body().Shape.isValid())


h.run(
    "limits_presspull",
    b.box_steps("LimitsPressPull")
    + [
        q_top,
        click_top,
        top_picked,
        drag_down,
        pushed_far,
        drag_up,
        back_up,
        type_minus_50,
        typed_minus_50,
        pushed,
    ]
    + b.box_steps("LimitsPressPullEdge")
    + [
        q_edge,
        click_edge,
        edge_picked,
        fillet_held,
        fillet_made,
        q_fillet_face,
        click_fillet_face,
        editing_fillet,
        edit_held,
        formula_explained,
        cancelled,
    ],
)
