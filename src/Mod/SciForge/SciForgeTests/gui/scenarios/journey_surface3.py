# SPDX-License-Identifier: LGPL-2.1-or-later
"""Journey (wave 6), part 3: a LOFTED surface across a solid, edited early, real input.

The design (built for the scenario): a 40 x 30 x 20 box; two sketch lines: at y = -5 the
line z = 5 (x -5 .. 45), at y = 35 the line rising from z 10 to z 18.

1. SURFACE > CREATE > Loft: click the front line, click the back line where it shows past
   the box: a twisted ruled surface z = 5 + 5 v + 8 u v (u = (x + 5) / 50, v = (y + 5) / 40);
   its area checked by integration. OK: Loft 1, a surface body.
2. SURFACE > MODIFY > Split Body: click the box, click the loft in front of it: below 11400,
   above 12600. OK.
3. SURFACE > CREATE > Thicken: click the loft where it shows in front, 1: a solid shell of
   the loft (about its area x 1). OK.
4. Double-click Loft 1 (the early step): Last Profile Direction, Takeoff Angle 30: the loft
   bends; the split follows (the two pieces still make 24000, the lower one changed), the
   Thicken follows. OK.
5. Double-click Box 1 (Extrude): 3 high: the loft (z 5 and up over the box) no longer cuts it:
   the Split Body turns red with the reason, nothing is built wrong. Ctrl+Z: back.
6. Ctrl+S, close, reopen: the loft's Direction end is kept, the same pieces.
"""

import math
import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import surface4_steps as s4
from SciForgeTests.gui import surface_steps as st

V = App.Vector
s = {}
BOX = 24000.0
BELOW = 11400.0
IN_FRONT = V(20, -2.5, 5 + 5 * 0.0625 + 8 * 0.5 * 0.0625)  # on the loft, in front of the box


def loft_area(u0=0.0, u1=1.0, n=200):
    """Simpson over |Pu x Pv| = |(-320 v, -50 (5 + 8u), 2000)| (surface4_split_loft)."""

    def f(u, v):
        return math.sqrt((320 * v) ** 2 + (50 * (5 + 8 * u)) ** 2 + 2000.0**2)

    def weights(k):
        return 1 if k in (0, n) else (4 if k % 2 else 2)

    du, dv = (u1 - u0) / n, 1.0 / n
    total = 0.0
    for i in range(n + 1):
        for j in range(n + 1):
            total += weights(i) * weights(j) * f(u0 + i * du, j * dv)
    return total * du * dv / 9.0


def doc():
    return App.ActiveDocument


def titles():
    return st.timeline_titles()


def title(prefix):
    return next((t for t in titles() if t.startswith(prefix)), None)


def bad_steps():
    return [o.Label for o in doc().Objects if "Invalid" in o.State or "Error" in o.State]


def pieces():
    from sciforge import split

    feature = next((o for o in doc().Objects if split.is_split(o)), None)
    others = split.piece_bodies(feature) if feature is not None else []
    return feature, sorted([st.volume(s["box"])] + [st.volume(b) for b in others])


def setup():
    from sciforge import bodies, extrude

    s4.new_design("JourneySurface3")
    sk = s4.sketch([(0, 0), (40, 0), (40, 30), (0, 30)])
    box = bodies.body_of(sk)
    s["box_step"] = extrude.make(box, sk, {"distance": 20.0})
    doc().recompute()
    bodies.set_shown(sk, False)
    s["box"] = box
    # the XZ plane's normal is -y: offset 5 is y = -5, offset -35 is y = 35
    s["a"] = s4.sketch([(-5, 5), (45, 5)], plane="XZ_Plane", closed=False, body=box, offset=5)
    s["b"] = s4.sketch([(-5, 10), (45, 18)], plane="XZ_Plane", closed=False, body=box, offset=-35)
    h.fit()
    h.check("a 24000 box", st.near(st.volume(box), BOX), st.volume(box))
    h.click_empty()
    st.tab("SURFACE")
    st.menu("CREATE", "Loft")


# -- 1. Loft ------------------------------------------------------------------------------------
def click_front_line():
    p = st.panel()
    h.check("Loft open", p is not None and p.kind == "loft")
    h.check("clicked the front line", h.click_edge(V(20, -5, 5)))


def click_back_line():
    st.settle()
    h.check("clicked the back line past the box", h.click_edge(V(44, 35, 10 + 8 * 49 / 50.0)))


def lofted():
    st.settle()
    p = st.panel()
    h.check("two profiles", p is not None and len(p.picks["sections"]) == 2, p and p.picks)
    body = st.step_body()
    s["loft"] = body
    want = loft_area()
    h.check(
        "the loft's area by integration", st.near(st.area(body), want, 1e-6), (st.area(body), want)
    )
    st.ok()


def loft_done():
    from sciforge import surface

    h.check("dialog closed", st.panel() is None)
    h.check("Loft 1 in the timeline", "Loft 1" in titles(), titles())
    h.check("a surface body", surface.is_surface_body(s["loft"]))
    s["area"] = st.area(s["loft"])
    h.click_empty()
    Gui.Selection.clearSelection()
    st.menu("MODIFY", "Split Body")


# -- 2. Split Body ------------------------------------------------------------------------------
def split_panel():
    from sciforge import split_ui

    p = split_ui.SplitPanel.last
    return p if p is not None and not p._closed else None


def split_box():
    h.check("Split Body open", split_panel() is not None)
    h.click(V(40, 25, 3))


def split_loft():
    p = split_panel()
    h.check("the box to split", p is not None and p.options["body"] is s["box"], p and p.options)
    h.click(IN_FRONT)


def split_ok():
    st.settle()
    h.idle_step()()
    p = split_panel()
    h.check("the loft is the tool", p is not None and p.options["tools"] == [(s["loft"], "")])
    st.ok()


def split_done():
    h.check("dialog closed", split_panel() is None)
    feature, vols = pieces()
    h.check("a Split Body step", feature is not None)
    h.check("below 11400, above 12600", len(vols) == 2 and st.near(vols[0], BELOW, 1e-6), vols)
    s["vols"] = vols
    h.click_empty()
    st.menu("CREATE", "Thicken")


# -- 3. Thicken ---------------------------------------------------------------------------------
def thicken_click():
    p = st.panel()
    h.check("Thicken open", p is not None and p.kind == "thicken")
    h.click(IN_FRONT)


def thicken_type():
    st.settle()
    st.type_field("thickness", "1")


def thickened():
    st.settle()
    body = st.step_body()
    s["shell"] = body
    v = st.volume(body)
    # a 1 mm shell of a gently curved surface: its area x 1 within a hair
    h.check("about the loft's area x 1", abs(v - s["area"]) < 0.01 * s["area"], (v, s["area"]))
    st.ok()


def thicken_done():
    h.check("dialog closed", st.panel() is None)
    h.check("Thicken in the timeline", title("Thicken") is not None, titles())
    s["shell_v"] = st.volume(s["shell"])
    h.shot("1-loft-split-thicken")
    h.check("double-clicked Loft 1", st.double_click_timeline("Loft 1"))


# -- 4. edit the loft ---------------------------------------------------------------------------
def loft_edit():
    st.settle()
    p = st.panel()
    h.check("Edit Loft", p is not None and p.kind == "loft" and p.editing)
    st.choose("end_condition", "Direction")


def loft_angle():
    st.settle()
    st.type_field("end_angle", "30")


def loft_edit_ok():
    st.settle()
    p = st.panel()
    h.check("no refusal", p is not None and not p.message.text(), p and p.message.text())
    st.ok()


def loft_followed():
    st.settle()
    h.idle_step()()
    h.check("dialog closed", st.panel() is None)
    area = st.area(s["loft"])
    h.check("the loft bends (its area changed)", abs(area - s["area"]) > 1.0, (area, s["area"]))
    feature, vols = pieces()
    h.check("the split follows: the pieces still make 24000", st.near(sum(vols), BOX, 1e-6), vols)
    h.check("the pieces changed", abs(vols[0] - BELOW) > 1.0, vols)
    v = st.volume(s["shell"])
    h.check("the Thicken follows", abs(v - area) < 0.01 * area and abs(v - s["shell_v"]) > 1e-3, v)
    h.check("no step in error", not bad_steps(), bad_steps())
    s["vols2"] = vols
    s["area2"] = area
    h.check("double-clicked the box's Extrude", st.double_click_timeline("Extrude 1"))


# -- 5. an edit the split cannot follow ---------------------------------------------------------
def box_edit():
    from sciforge import extrude_ui

    p = getattr(extrude_ui, "ExtrudePanel", None)
    p = p.last if p is not None and getattr(p, "last", None) is not None else None
    h.check("Edit Extrude (the box)", p is not None and p.editing and not p._closed)
    if p is None:
        return
    s["box_panel"] = p
    from SciForgeTests.gui import dialog_input as ui

    ui.type_into(p.distance.widget, "3")


def box_typed():
    p = s.get("box_panel")
    h.check("3 typed", p is not None and st.near(p.distance.value(), 3.0), p and p.distance.value())
    h.check(
        "the preview follows (no 'Bodies to Join is empty': the piece split off later is not "
        "in the way of the box's first Extrude)",
        p is not None and not p.message.text() and st.near(s["box_step"].Length.Value, 3.0),
        p and (p.message.text(), s["box_step"].Length),
    )
    h.shot("2-box-3-preview")


def box_ok():
    """3 high: the loft (z 5 and up over the box) no longer reaches it: the split must turn
    red with the reason, never crash or split wrong."""
    h.task_button("OK")
    st.settle()
    h.idle_step()()
    h.shot("3-box-3-ok")
    h.check("the Extrude dialog closed", not Gui.Control.activeDialog())
    h.new_errors()  # the red step is reported (expected)
    feature, _vols = pieces()
    ext = s["box_step"]
    h.check("the box's Extrude is 3 high", st.near(ext.Shape.Volume, 3600.0), ext.Shape.Volume)
    status = feature.getStatusString() if feature is not None else ""
    red = feature is not None and ("Invalid" in feature.State or "Error" in feature.State)
    h.check("the Split Body is red", red, feature and feature.State)
    h.check("with the reason", "cut" in status.lower() or "split" in status.lower(), status)
    s["status"] = status


def box_refused():
    h.new_errors()
    feature, _vols = pieces()
    h.check(
        "still red", feature is not None and "Invalid" in feature.State, feature and feature.State
    )
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


box_refused.wait_ms = 2000


def box_undone():
    st.settle()
    h.idle_step()()
    h.new_errors()
    h.check("Ctrl+Z: no step in error", not bad_steps(), bad_steps())
    _feature, vols = pieces()
    h.check("the pieces back", all(st.near(a, b, 1e-6) for a, b in zip(vols, s["vols2"])), vols)
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-journey-sf3-"), "journey_surface3.FCStd")
    s["path"] = path
    s["label"] = s["loft"].Label
    s["titles"] = titles()
    doc().saveAs(path)
    h.check("saved", os.path.isfile(path), path)


def ctrl_s():
    h.press(QtCore.Qt.Key_S, QtCore.Qt.ControlModifier)


def describe():
    from SciForgeTests.gui import versions_input as vi

    h.check("the Save dialog asks for a version description", vi.version_dialog() is not None)
    vi.accept_save()


def close():
    h.check("nothing unsaved", not doc().isTouched())
    App.closeDocument(doc().Name)


def reopen():
    App.openDocument(s["path"])
    h.fit()


def reopened():
    from sciforge import bodies, surface

    found = doc().getObjectsByLabel(s["label"])
    h.check("the loft is back", bool(found), s["label"])
    if not found:
        return
    loft = found[0]
    h.check("the same loft", st.near(st.area(loft), s["area2"], 1e-9), st.area(loft))
    step = loft.Tip
    options = (bodies.load_meta(step, surface.META) or {}).get("options") or {}
    h.check("Direction kept", options.get("end_condition") == "direction", options)
    h.check("the same timeline", titles() == s["titles"], (titles(), s["titles"]))
    h.check("no step in error", not bad_steps(), bad_steps())


h.run(
    "journey_surface3",
    [
        setup,
        click_front_line,
        click_back_line,
        lofted,
        loft_done,
        split_box,
        split_loft,
        split_ok,
        split_done,
        thicken_click,
        thicken_type,
        thickened,
        thicken_done,
        loft_edit,
        loft_angle,
        loft_edit_ok,
        loft_followed,
        box_edit,
        box_typed,
        box_ok,
        box_refused,
        box_undone,
        ctrl_s,
        describe,
        close,
        reopen,
        reopened,
    ],
)
