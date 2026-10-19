# SPDX-License-Identifier: LGPL-2.1-or-later
"""Silhouette Split (MODIFY > Silhouette Split) like Fusion, only real input.

Part: a ball, SOLID > CREATE > Sphere on the XY square, centre at the origin, diameter 20
(4000 pi / 3, one round face).

  A  MODIFY > Silhouette Split with nothing selected: the dialog waits for the View
     Direction (the origin squares show); Operation is Split Faces Only (Fusion's default).
     A click on the ball's round face is refused in the dialog (it gives no direction).
  B  The XY square (looking down Z), then the ball: its outline seen from above is the
     equator: two faces, one body, same volume, previewed; OK: a "Silhouette Split 1"
     step. Undo / Redo.
  C  Double-click Silhouette Split 1: Operation Split Solid Body: two bodies (the halves,
     2000 pi / 3 each), previewed; OK. Undo: one ball again; Redo.
  D  Edit again: Split Shelled Body: the ball's outline is flat, so the same two halves;
     View Direction cleared and the ball's round face clicked: refused in the dialog, OK
     keeps it open; Cancel: still the two halves from Split Solid Body.
  E  Save, close, open: two halves, the step still edits.
"""

import math
import os

import FreeCAD as App

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import direct_steps as d
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import primitive_input as pi
from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import timeline_input as t
from SciForgeTests.gui import widget_input as wi

V = App.Vector
BALL = 4000 * math.pi / 3
HALF = BALL / 2
state = {}


def ball():
    return d.bodies()[0]


def total():
    return sum(d.volume(b) for b in d.bodies() if d.shown(b))


def splits():
    return [o for o in d.doc().Objects if getattr(o, "SciForgeType", "") == "SilhouetteSplit"]


def errors():
    return {k: v for k, v in t.states().items() if v[1] not in ("ok", "")}


# -- the ball ---------------------------------------------------------------------------------
def sphere_start():
    h.fit()
    pi.menu("Sphere")


def sphere_plane():
    p = pi.panel("SpherePanel")
    h.check("Sphere waits for a plane", p is not None and p.state == "plane")
    pl.click_square("XY_Plane")  # where the square shows (was 15, -15, 0)


def sphere_centre():
    p = pi.panel("SpherePanel")
    h.check("placing", p is not None and p.state == "place", p and p.state)
    pl.click_on_plane(V(0, 0, 0))


sphere_centre.wait_ms = 1200


def sphere_diameter():
    p = pi.panel("SpherePanel")
    if h.check("the sphere is placed", p is not None and p.state == "ready", p and p.state):
        ui.type_into(p.diameter.widget, "20")


def sphere_ok():
    h.task_button("OK")


def sphere_made():
    h.check("one ball", len(d.bodies()) == 1, [b.Label for b in d.bodies()])
    h.check("the ball: 4000 pi / 3", d.near(d.volume(ball()), BALL), d.volume(ball()))
    h.check("one round face", len(ball().Shape.Faces) == 1, len(ball().Shape.Faces))
    h.fit()


# -- A ------------------------------------------------------------------------------------------
def a_start():
    h.click_empty()
    d.ribbon_menu("MODIFY", "Silhouette Split")


def a_waits():
    p = d.panel()
    if not h.check("Silhouette Split dialog", p is not None and p.title == "Silhouette Split", p):
        return
    h.check("the View Direction box waits", p.active == "direction", p.active)
    h.check("the origin squares show", p.squares.picker is not None)
    h.check(
        "Split Faces Only by default",
        p.operation.currentData() == "faces",
        p.operation.currentText(),
    )
    h.check("no pop-up", not h.popups(), h.popups())


def a_click_round():
    h.click(V(5, -5, 50**0.5))


def a_refused():
    p = d.panel()
    msg = d.message()
    h.check("a round face gives no direction: said", "view direction" in msg, msg)
    h.check(
        "still waiting for the direction",
        p is not None and p.active == "direction" and p.options["direction"] is None,
        p and p.options,
    )


# -- B ------------------------------------------------------------------------------------------
def b_click_xy():
    pl.click_square("XY_Plane")  # where the square shows (was 12, 12, 0)


def b_click_ball():
    p = d.panel()
    h.check(
        "direction taken", p is not None and p.options["direction"] is not None, p and p.options
    )
    h.check("now the Target Body box", p is not None and p.active == "body", p and p.active)
    h.click(V(5, -5, 50**0.5))


def b_preview():
    p = d.panel()
    h.check("the ball picked", p is not None and p.options["body"] is ball(), p and p.options)
    h.check("preview: two faces", len(ball().Shape.Faces) == 2, len(ball().Shape.Faces))
    h.check("one body", len(d.bodies()) == 1, [b.Label for b in d.bodies()])
    h.check("same volume", d.near(d.volume(ball()), BALL), d.volume(ball()))
    h.check(
        "the dialog says so", p is not None and "1 more face" in p.note.text(), p and p.note.text()
    )
    h.shot("B-preview")


def b_ok():
    h.task_button("OK")


def b_done():
    h.check("dialog closed", d.panel() is None)
    h.check("a Silhouette Split step", "Silhouette Split 1" in t.titles(), t.titles())
    h.check("two faces", len(ball().Shape.Faces) == 2, len(ball().Shape.Faces))


def b_undo():
    t.undo()


def b_undone():
    h.check("undo: one face", len(ball().Shape.Faces) == 1, len(ball().Shape.Faces))
    h.check("undo: no step", not splits(), splits())


def b_redo():
    t.redo()


def b_redone():
    h.check("redo: two faces", len(ball().Shape.Faces) == 2, len(ball().Shape.Faces))


# -- C ------------------------------------------------------------------------------------------
def c_edit():
    h.fit()
    h.check(
        "double-click Silhouette Split 1",
        ui.double_click_timeline("Silhouette Split 1"),
        t.titles(),
    )


def c_solid():
    p = d.panel()
    if h.check("the edit dialog", p is not None and p.editing, p):
        d.choose("operation", "Split Solid Body")


def c_preview():
    found = d.bodies()
    h.check("preview: two bodies", len(found) == 2, [b.Label for b in found])
    if len(found) == 2:
        h.check(
            "two halves",
            d.near(d.volume(found[0]), HALF) and d.near(d.volume(found[1]), HALF),
            [d.volume(b) for b in found],
        )
        h.check(
            "one above, one below",
            sorted(round(b.Shape.BoundBox.ZMin, 6) for b in found) == [-10.0, 0.0],
            [b.Shape.BoundBox for b in found],
        )
    p = d.panel()
    h.check(
        "the dialog says 2 bodies",
        p is not None and "2 bodies" in p.note.text(),
        p and p.note.text(),
    )
    h.shot("C-halves")


def c_ok():
    h.task_button("OK")


def c_done():
    h.check("dialog closed", d.panel() is None)
    found = d.bodies()
    h.check("two bodies", len(found) == 2, [b.Label for b in found])
    h.check("both shown", all(d.shown(b) for b in found))
    h.check("total kept", d.near(total(), BALL), total())
    labels = t.labels()
    h.check(
        "both in the browser",
        all(any(x.startswith(b.Label) for x in labels) for b in found),
        labels,
    )
    h.check("still one step", len(splits()) == 1, splits())


def c_undo():
    t.undo()


def c_undone():
    shown = [b for b in d.bodies() if d.shown(b)]
    h.check(
        "undo: one ball",
        len(shown) == 1 and d.near(d.volume(shown[0]), BALL),
        [(b.Label, d.volume(b)) for b in shown],
    )


def c_redo():
    t.redo()


def c_redone():
    shown = [b for b in d.bodies() if d.shown(b)]
    h.check("redo: two halves", len(shown) == 2, [b.Label for b in shown])


# -- D ------------------------------------------------------------------------------------------
def d_edit():
    h.click_empty()
    h.check(
        "double-click Silhouette Split 1 again",
        ui.double_click_timeline("Silhouette Split 1"),
        t.titles(),
    )


def d_shelled():
    p = d.panel()
    if h.check("the edit dialog", p is not None and p.editing, p):
        h.check(
            "it shows Split Solid Body",
            p.operation.currentData() == "body",
            p.operation.currentText(),
        )
        d.choose("operation", "Split Shelled Body")


def d_shelled_split():
    p = d.panel()
    h.check(
        "Split Shelled Body: two halves too",
        p is not None and "2 bodies" in p.note.text(),
        p and (p.note.text(), d.message()),
    )
    wi.click(p.fields["direction"].clear)


def d_click_round():
    p = d.panel()
    h.check(
        "the View Direction box waits", p is not None and p.active == "direction", p and p.active
    )
    h.click(V(5, -5, 50**0.5))


def d_refused():
    msg = d.message()
    h.check("the reason is said", "view direction" in msg, msg)


def d_ok():
    h.task_button("OK")


def d_still_open():
    p = d.panel()
    h.check("OK keeps the dialog open", p is not None and not p._closed, p)


def d_cancel():
    h.task_button("Cancel")


def d_cancelled():
    h.check("dialog closed", d.panel() is None)
    shown = [b for b in d.bodies() if d.shown(b)]
    h.check(
        "cancel: still the two halves",
        len(shown) == 2 and all(d.near(d.volume(b), HALF) for b in shown),
        [d.volume(b) for b in shown],
    )
    h.check("no step in error", not errors(), errors())


# -- E ------------------------------------------------------------------------------------------
def e_save_close_open():
    path = os.path.join(h.OUT_DIR, "modify_silhouette.FCStd")
    if os.path.exists(path):
        os.remove(path)
    App.ActiveDocument.saveAs(path)
    App.closeDocument(App.ActiveDocument.Name)
    App.openDocument(path)


def e_reopened():
    d.doc().recompute()
    shown = [b for b in d.bodies() if d.shown(b)]
    h.check(
        "reopened: two halves",
        len(shown) == 2 and all(d.near(d.volume(b), HALF) for b in shown),
        [d.volume(b) for b in shown],
    )
    h.check("reopened: the step", "Silhouette Split 1" in t.titles(), t.titles())
    h.check("reopened: no step in error", not errors(), errors())
    h.fit()


def e_edit():
    h.check(
        "double-click Silhouette Split 1 after reopening",
        ui.double_click_timeline("Silhouette Split 1"),
        t.titles(),
    )


def e_faces_only():
    p = d.panel()
    if h.check("the edit dialog", p is not None and p.editing, p):
        d.choose("operation", "Split Faces Only")


def e_ok():
    h.task_button("OK")


def e_one_ball():
    shown = [b for b in d.bodies() if d.shown(b)]
    h.check(
        "back to one ball with two faces",
        len(shown) == 1 and len(shown[0].Shape.Faces) == 2 and d.near(d.volume(shown[0]), BALL),
        [(b.Label, d.volume(b)) for b in shown],
    )
    h.check("no step in error", not errors(), errors())


h.run(
    "modify_silhouette",
    t.watched(
        [
            s.new_design("Silhouette"),
            sphere_start,
            sphere_plane,
            sphere_centre,
            sphere_diameter,
            sphere_ok,
            sphere_made,
            a_start,
            a_waits,
            a_click_round,
            a_refused,
            b_click_xy,
            b_click_ball,
            b_preview,
            b_ok,
            b_done,
            b_undo,
            b_undone,
            b_redo,
            b_redone,
            c_edit,
            c_solid,
            c_preview,
            c_ok,
            c_done,
            c_undo,
            c_undone,
            c_redo,
            c_redone,
            d_edit,
            d_shelled,
            d_shelled_split,
            d_click_round,
            d_refused,
            d_ok,
            d_still_open,
            d_cancel,
            d_cancelled,
            e_save_close_open,
            e_reopened,
            e_edit,
            e_faces_only,
            e_ok,
            e_one_ball,
        ]
    ),
)
