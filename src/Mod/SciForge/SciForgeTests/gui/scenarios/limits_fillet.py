# SPDX-License-Identifier: LGPL-2.1-or-later
"""A fillet radius or chamfer distance past what fits stops at the largest one that works
(Luca, 2026-10-21: "limit edits to stop at that limit, so if I want to chamfer something to
the max I can quickly drag it"). Fusion shows an error instead; this is Luca's decision. Only
real input.

Box 40 x 30 x 10, Fillet on the front top edge (its faces are 10 and 30 mm wide):
  * the arrow dragged far past the largest radius, slowly, with the button held: the radius
    stops just under 10 mm (the arrow too, like the end of a slider), the preview shows that
    round, the dialog says "Largest that fits here: ..." in blue, no error, and the limit was
    worked out once for the whole drag (no search on every mouse move);
  * dragged back: the radius follows below the limit again, the note goes;
  * 50 typed: held at the limit, the note says "50 mm does not fit: limited to ..."; OK at
    once makes the fillet with that radius;
  * a formula that is too big (parameter w = 60 mm) is not rewritten: the dialog explains,
    with the largest radius that fits, and OK waits; Cancel.
Chamfer on the right top edge: Distance and Angle with 50 typed is held at a limit (that
chamfer is built in a throw-away document to find it); Equal Distance dragged far is held at
the largest distance; OK."""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore
from PySide6 import QtTest

from SciForgeTests.gui import arrow_input as a
from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h

V = App.Vector
s = {}
FRONT_TOP = V(20, 0, 10)
RIGHT_TOP = V(40, 15, 10)


def one_edge(r, length=40):
    return b.BOX - length * b.spandrel(r)


def panel():
    return b.blend_panel()


def note(p):
    return p.limit_label.text() if p is not None and p.limit_label.isVisible() else ""


def held_drag(along, name):
    """Drag the first arrow `along` mm (negative: back toward the edge) like a hand does."""
    p = panel()
    if p is None or not p.arrows:
        h.check("%s: an arrow to drag" % name, False)
        return
    dragger, _spot, _origin, direction = p.arrows[0]
    head = a.head_point(dragger)
    start, end = h.screen_point(head), h.screen_point(head + direction * along)
    s["samples"] = []
    s["searches"] = p.limits.searches

    def sample(index):
        q = panel()
        if q is not None:
            s["samples"].append((index, q._value(q._row_key(), q.arrows[0][1]["what"])))

    s["drag"] = a.HeldDrag(start, end, moves=30, every_ms=40, hold_ms=400, sample=sample)
    s["drag"].run()


# -- Fillet ------------------------------------------------------------------------------------
def fillet_start():
    Gui.Selection.clearSelection()
    h.fit()
    h.ribbon("Fillet")


def pick_front_top():
    h.click_edge(FRONT_TOP)


def picked():
    p = panel()
    h.check("one edge picked", p is not None and len(p.refs) == 1, p and p.refs)
    h.check("its arrow", p is not None and len(p.arrows) == 1, p and len(p.arrows))
    h.check("no note yet", note(p) == "", note(p))


def drag_far():
    held_drag(40.0, "drag far")


def dragged_far():
    p = panel()
    if p is None:
        h.check("dialog still open after the drag", False)
        return
    r = p.radius.value()
    s["limit"] = r
    h.check("the radius stopped just under 10 mm (the front face is 10 high)", 9.0 < r <= 10.0, r)
    h.check("no error: the drag ended at the limit", p.message.text() == "", p.message.text())
    h.check(
        "the note says the largest that fits",
        note(p) == "Largest that fits here: %.2f mm" % r,
        note(p),
    )
    v = h.solid_volume()
    h.check("the preview shows that round", b.close(v, one_edge(r)), (v, one_edge(r)))
    from sciforge import blend

    try:
        blend.trial("fillet", p.info, p.refs, {"radius": r + 0.01})
        bigger = "works"
    except blend.BlendError:
        bigger = "refused"
    h.check("0.01 mm more does not fit (it is the limit, not a guess)", bigger == "refused", bigger)
    h.check(
        "the limit was worked out once for the whole drag",
        p.limits.searches - s["searches"] == 1,
        p.limits.searches - s["searches"],
    )
    values = [value for _i, value in s["samples"]]
    reached = [i for i, value in enumerate(values) if abs(value - r) < 1e-9]
    after = values[reached[0] :] if reached else []
    h.check(
        "once at the limit, the radius never went over it while held past it",
        after and max(after) <= r + 1e-9,
        values[-8:],
    )
    dragger, spot = p.arrows[0][0], p.arrows[0][1]
    h.check(
        "the arrow stopped at the limit too",
        abs(dragger.distance() - r * spot["per_unit"]) < 1e-6,
        (dragger.distance(), r),
    )
    h.check("nothing in the Report view", not b.report_has_kernel_errors())
    h.shot("1-held-at-limit")


dragged_far.wait_ms = 2500


def drag_back():
    held_drag(-4.0, "drag back")


def dragged_back():
    p = panel()
    r = p.radius.value() if p else 0
    h.check("dragged back, the radius follows below the limit", 1.0 < r < s["limit"] - 1.0, r)
    h.check("the note went", note(p) == "", note(p))
    v = h.solid_volume()
    h.check("the preview follows", b.close(v, one_edge(r)), (v, one_edge(r)))
    h.check("no new search coming back", p.limits.searches == 1, p and p.limits.searches)


dragged_back.wait_ms = 1500


def type_50():
    p = panel()
    if p:
        b.type_into(p.radius.widget, "50")


def typed_50():
    p = panel()
    text = note(p)
    h.check(
        "50 is held at the limit and the note says so",
        text == "50 mm does not fit: limited to %.2f mm" % s["limit"],
        text,
    )
    h.check("no error", p is not None and p.message.text() == "", p and p.message.text())
    v = h.solid_volume()
    h.check("the preview shows the largest round", b.close(v, one_edge(s["limit"])), v)


typed_50.wait_ms = 1500


def ok_at_once():
    h.task_button("OK")


def fillet_made():
    h.check("OK worked at once", b.blend_panel() is None and not Gui.Control.activeDialog())
    fl = b.blends()
    h.check("one fillet", len(fl) == 1, fl)
    if fl:
        h.check(
            "its radius is the limit", abs(fl[0].Radius.Value - s["limit"]) < 1e-9, fl[0].Radius
        )
    v = h.solid_volume()
    h.check("the part has that round", b.close(v, one_edge(s["limit"])), v)
    h.check("valid solid", h.body().Shape.isValid())
    h.shot("2-fillet-at-limit")


def add_parameter():
    from sciforge import parameters

    parameters.add_user(App.ActiveDocument, "w", "mm", "60")
    App.ActiveDocument.recompute()


def edit_fillet():
    b.timeline_double_click("Fillet 1")


def type_formula():
    p = panel()
    h.check("editing the fillet", p is not None and not p.created)
    if p:
        b.type_into(p.radius.widget, "w")
        QtTest.QTest.keyClick(p.radius.widget, QtCore.Qt.Key_Tab)  # leave the box: taken


def formula_explained():
    p = panel()
    text = p.message.text() if p else ""
    h.check("a formula that does not fit is not rewritten", p and "w" in p.formulas.text(), text)
    h.check("it is explained", "too big" in text, text)
    h.check(
        "with the largest radius that fits",
        "Largest that fits here: %.2f mm" % s["limit"] in text,
        text,
    )
    h.check("no note (nothing was held)", note(p) == "", note(p))
    h.task_button("OK")


formula_explained.wait_ms = 2500


def formula_ok_waits():
    p = panel()
    h.check("OK waits while the formula does not fit", p is not None and Gui.Control.activeDialog())
    h.task_button("Cancel")


def cancelled():
    h.check("Cancel closed it", not Gui.Control.activeDialog())
    fl = b.blends()
    h.check("the fillet kept its radius", fl and abs(fl[0].Radius.Value - s["limit"]) < 1e-9)
    s["v"] = h.solid_volume()


# -- Chamfer -----------------------------------------------------------------------------------
def chamfer_start():
    Gui.Selection.clearSelection()
    h.fit()
    h.ribbon("Chamfer")


def pick_right_top():
    h.click_edge(RIGHT_TOP)


def chamfer_picked():
    p = panel()
    h.check("Chamfer dialog with one edge", p is not None and len(p.refs) == 1, p and p.refs)


def chamfer_drag():
    held_drag(30.0, "chamfer drag")


def chamfer_dragged():
    p = panel()
    if p is None:
        h.check("Chamfer dialog open after the drag", False)
        return
    d = p.distance.value()
    s["d"] = d
    h.check("the distance stopped at the largest that fits", 5.0 < d <= 10.0, d)
    h.check("note", note(p) == "Largest that fits here: %.2f mm" % d, note(p))
    h.check("no error", p.message.text() == "", p.message.text())
    h.shot("3-chamfer-held")


chamfer_dragged.wait_ms = 2500


def chamfer_ok():
    h.task_button("OK")


def chamfer_made():
    h.check("OK worked at once", not Gui.Control.activeDialog())
    ch = [o for o in b.blends() if o.TypeId == "PartDesign::Chamfer"]
    h.check("one chamfer", len(ch) == 1, ch)
    if ch:
        h.check("its distance is the limit", abs(ch[0].Size.Value - s["d"]) < 1e-9, ch[0].Size)
    h.check("valid solid", h.body().Shape.isValid())


def angle_type():
    p = panel()
    if p:
        b.choose(p.ctype, "Distance and Angle")


def angle_type_50():
    p = panel()
    if p:
        b.type_into(p.distance.widget, "50")


def angle_limited():
    p = panel()
    text = note(p)
    h.check("Distance and Angle: 50 is held at a limit", text.startswith("50 mm does not fit"), text)
    h.check("no error", p is not None and p.message.text() == "", p and p.message.text())
    d = p.options.get("distance") if p else 0
    h.check("the distance used is under 10 mm", 1.0 < d <= 10.0, d)
    s["angle_d"] = d
    if p:
        b.choose(p.ctype, "Equal Distance")


angle_limited.wait_ms = 4000


h.run(
    "limits_fillet",
    b.box_steps("LimitsFillet")
    + [
        fillet_start,
        pick_front_top,
        picked,
        drag_far,
        dragged_far,
        drag_back,
        dragged_back,
        type_50,
        typed_50,
        ok_at_once,
        fillet_made,
        add_parameter,
        edit_fillet,
        type_formula,
        formula_explained,
        formula_ok_waits,
        cancelled,
        chamfer_start,
        pick_right_top,
        chamfer_picked,
        angle_type,
        angle_type_50,
        angle_limited,
        chamfer_drag,
        chamfer_dragged,
        chamfer_ok,
        chamfer_made,
    ],
)
