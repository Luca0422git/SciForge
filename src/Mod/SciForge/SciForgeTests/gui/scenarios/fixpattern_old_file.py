# SPDX-License-Identifier: LGPL-2.1-or-later
"""A design saved before the fix of 2026-10-16 (fixtures/pattern_bodies_v1.FCStd, made by
fixtures/make_old_pattern.py at d5a3690b9d): a 40 x 30 x 10 box, a Rectangular Pattern of the
body along X (Spacing 50, Quantity 3), a Mirror of it as a New Body across YZ, and then a Move
of the original 20 up. The old code saved every copy moved with the original (z 20..30).

  A  Opened: the patterns are upgraded while the file is read (they now copy the body as it
     stands at the pattern) and computed again once it is open: the copies are back at
     z 0..10 (Body2 x 50..90, Body3 x 100..140, Body4 x -40..0), the original stays moved
     (z 20..30), nothing red.
  B  Extrude 1 (before the patterns) edited from the timeline to 15: every copy follows
     (18000, z 0..15). Undo.
  C  The original moved again (M, 10 more up): only the original moves.
  D  The original deleted (browser, MODIFY > Delete): the copies stay. Undo.
  E  Saved and opened again: the same.
"""

import os
import shutil

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import fixpattern_steps as f
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import pattern_steps as ps

V = App.Vector
HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURE = os.path.join(
    os.path.dirname(os.path.dirname(HERE)), "fixtures", "pattern_bodies_v1.FCStd"
)
COPIES = {"Body2": (50, 90), "Body3": (100, 140), "Body4": (-40, 0)}


def check_all(where, height, z0):
    """Copies from z 0 to `height`; the original from z `z0`, as tall."""
    doc = App.ActiveDocument
    for label, (x0, x1) in COPIES.items():
        body = s.body_named(label)
        if not h.check(
            "%s: %s is there" % (where, label), body is not None, [x.Label for x in s.bodies()]
        ):
            continue
        bb = body.Shape.BoundBox
        h.check(
            "%s: %s at x %g..%g, z 0..%g" % (where, label, x0, x1, height),
            abs(bb.XMin - x0) < 1e-4
            and abs(bb.XMax - x1) < 1e-4
            and abs(bb.ZMin) < 1e-4
            and abs(bb.ZMax - height) < 1e-4,
            (bb.XMin, bb.XMax, bb.ZMin, bb.ZMax),
        )
        h.check(
            "%s: %s %g" % (where, label, 1200 * height),
            s.close(s.volume(body), 1200 * height),
            s.volume(body),
        )
    if z0 is not None:
        f.check_original(1200 * height, z0, z0 + height, where)
    f.no_red(where)
    return doc


# -- A ----------------------------------------------------------------------------------------
def a_open():
    Gui.activateWorkbench("SciForgeWorkbench")
    path = os.path.join(h.OUT_DIR, "fixpattern_old_file.FCStd")
    shutil.copy(FIXTURE, path)
    App.openDocument(path)
    h.fit()


a_open.wait_ms = 3000


def a_upgraded():
    from sciforge import pattern

    doc = App.ActiveDocument
    found = [o for o in doc.Objects if pattern.is_body_pattern(o)]
    h.check("two patterns of bodies", len(found) == 2, [o.Label for o in found])
    h.check(
        "each copies the body's step before it (not the body)",
        all(o.Source is not None and o.Source.TypeId != "PartDesign::Body" for o in found),
        [(o.Label, o.Source and o.Source.TypeId) for o in found],
    )
    check_all("opened", 10, 20)
    titles = ps.timeline_titles()
    h.check(
        "the timeline: Extrude 1, the patterns, Move 1",
        all(t in titles for t in ("Extrude 1", "Rectangular Pattern 1", "Mirror 1", "Move 1")),
        titles,
    )
    helpers = [o for o in doc.Objects if pattern.is_body_copy(o)]
    h.check(
        "the copies' hidden copy features stay hidden (FreeCAD showed them on opening)",
        len(helpers) == 3 and not any(o.ViewObject.Visibility for o in helpers),
        [(o.Name, o.ViewObject.Visibility) for o in helpers],
    )
    h.shot("A-opened")
    h.click_empty()
    h.fit()
    h.click(V(70, 15, 10))  # Body2's top


def a_copy_picked():
    from sciforge import bodies

    found = [x.Object for x in Gui.Selection.getSelectionEx()]
    picked = [bodies.body_of(o) for o in found]
    h.check(
        "a click on a copy picks that copy's body",
        bool(picked) and all(b is not None and b.Label == "Body2" for b in picked),
        [(o.Name, b.Label if b is not None else None) for o, b in zip(found, picked)],
    )
    h.click_empty()


# -- B ----------------------------------------------------------------------------------------
def b_edit():
    h.click_empty()
    ps.timeline_double_click("Extrude 1")


def b_distance():
    p = b.active_panel()
    field = getattr(getattr(p, "distance", None), "widget", None)
    if h.check("the extrude's dialog", field is not None, p):
        s.type_value(field, "15")


def b_ok():
    h.task_button("OK")


def b_edited():
    check_all("edit 15", 15, 20)
    s.undo()


def b_undone():
    check_all("undo of the edit", 10, 20)


# -- C ----------------------------------------------------------------------------------------
def c_select():
    h.click_empty()
    h.fit()
    h.click(V(20, 15, 30))


def c_press_m():
    h.press("m")


def c_dz():
    p = s.panel()
    if h.check("Move/Copy open", p is not None and hasattr(p, "distance_fields"), p):
        h.check(
            "the original moves",
            [x.Name for x in p.options["bodies"]] == ["Body"],
            [x.Label for x in p.options["bodies"]],
        )
        s.type_value(p.distance_fields[2].widget, "10")


def c_ok():
    h.task_button("OK")


def c_moved():
    check_all("moved again", 10, 30)


# -- D ----------------------------------------------------------------------------------------
def d_select():
    h.click_empty()
    s.click_browser_row("Body")


def d_delete():
    s.menu("MODIFY", "Delete")


def d_deleted():
    h.check("the original is gone", f.original() is None)
    check_all("original deleted", 10, None)
    s.undo()


def d_undone():
    check_all("undo of the delete", 10, 30)


# -- E ----------------------------------------------------------------------------------------
def e_reopen():
    doc = App.ActiveDocument
    path = os.path.join(h.OUT_DIR, "fixpattern_old_file_saved.FCStd")
    doc.saveAs(path)
    App.closeDocument(doc.Name)
    App.openDocument(path)
    h.fit()


e_reopen.wait_ms = 2500


def e_reopened():
    check_all("saved and opened again", 10, 30)


h.run(
    "fixpattern_old_file",
    [a_open, a_upgraded, a_copy_picked]
    + [b_edit, b_distance, b_ok, b_edited, b_undone]
    + [c_select, c_press_m, c_dz, c_ok, c_moved]
    + [d_select, d_delete, d_deleted, d_undone]
    + [e_reopen, e_reopened],
)
