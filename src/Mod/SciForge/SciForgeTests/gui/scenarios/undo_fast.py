# SPDX-License-Identifier: LGPL-2.1-or-later
"""Undo / Redo without a rebuild when FreeCAD already put the right shapes back
(sciforge/undo_fast.py; SciForge speed with big designs, 2026-10-21), with real input.

A part: a 40 x 30 x 10 block, a round hole, its four upright edges rounded (R2).

Path A, Extrude 1 edited from the timeline (14), OK; Ctrl+Z: the old part is back without a
        rebuild, and it is the right one (every step rebuilt afterwards gives the same
        shapes); Ctrl+Y: the edit is back, without a rebuild, right.
Path B, Fillet 1 edited from the timeline (R3), OK; Undo and Redo from the quick access bar:
        the same.
Path C, an edit, then a change made outside any transaction (a script moving the hole's
        sketch): the next Ctrl+Z cannot vouch for the shapes and rebuilds, and the part is
        rebuilt with the moved hole, as a recompute would.
Path D, two edits, two Ctrl+Z in a row: neither rebuilds, the part is the original one.
Path E (integration, 2026-10-22), Fillet 1 edited with 50 typed: the dialog holds it at the
        largest radius that fits (value_limits), OK; Ctrl+Z and Ctrl+Y: nothing rebuilt, right.
Path F (integration), the AI tools: edit_step of Fillet 1 through the bridge (one undo step
        "AI: ..."), then the AI's own undo / redo: nothing rebuilt, right (the AI tools settle
        an undo like the timeline does). An AI edit with a radius that does not fit is
        refused with the largest radius that fits (value_fit tries values in transactions it
        takes back): the design and the undo stack are as before, and the next Ctrl+Z still
        gives the right part.
Path G (review fix, 2026-10-22), a sketch dimension changed in MODIFY > Change Parameters
        (Sketch 1's 40 typed 44), OK; Ctrl+Z / Ctrl+Y: nothing rebuilt, right. FreeCAD solves
        the sketch again while it finishes the Undo (SketchObject::onUndoRedoFinished): those
        changes are part of the Undo, they used to count as script changes and every sketch
        edit was rebuilt.
Path H (review fix), a user parameter (depth, driving Extrude 1) changed in Change
        Parameters, OK; Ctrl+Z / Ctrl+Y: nothing rebuilt (Parameters holds only values), right.
"""

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import timeline_input as t

S = {}


def stats():
    from sciforge import undo_fast

    return dict(undo_fast.stats)


def shapes():
    """{object: (volume, bounding box)} of every solid in the design."""
    out = {}
    for o in App.ActiveDocument.Objects:
        try:
            shape = o.Shape
        except Exception:
            continue
        if shape.isNull() or not shape.Solids:
            continue
        box = shape.BoundBox
        out[o.Name] = (round(shape.Volume, 5), tuple(round(v, 5) for v in (box.XMax, box.YMax, box.ZMax)))
    return out


def tip_volume():
    tip = h.body().Tip
    return tip.Shape.Volume if tip is not None else 0.0


def setup():
    from SciForgeTests.golden.builder import Builder

    Gui.activateWorkbench("SciForgeWorkbench")
    doc = App.newDocument("UndoFast")
    builder = Builder(doc)
    for step in (
        {"op": "sketch", "id": "s1", "plane": "XY", "geometry": [{"rect": [0, 0, 40, 30]}]},
        {"op": "extrude", "id": "e1", "profile": "s1", "distance": 10},
        {"op": "sketch", "id": "s2", "plane": "XY", "geometry": [{"circle": [20, 15, 4]}]},
        {"op": "extrude", "id": "e2", "profile": "s2", "distance": 10, "operation": "cut"},
        {
            "op": "fillet",
            "id": "f1",
            "edges": {
                "any_of": [
                    {"type": "line", "parallel": [0, 0, 1], "at": {"axis": "x", "value": "min"}},
                    {"type": "line", "parallel": [0, 0, 1], "at": {"axis": "x", "value": "max"}},
                ],
                "count": 4,
            },
            "radius": 2,
        },
    ):
        builder.run(step)
    doc.recompute()
    h.fit()
    S["original"] = shapes()
    S["volume"] = tip_volume()
    h.check("the part is built", S["volume"] > 10000, S["volume"])


def remember(label):
    def step():
        S[label] = shapes()
        S["stats"] = stats()

    step.__name__ = "remember_" + label
    return step


def expect(label, fast, what):
    """The design is the one remembered under `label`; the Undo / Redo before rebuilt
    nothing (fast) or rebuilt (not fast); and every step rebuilt now gives the same shapes."""

    def step():
        now = shapes()
        before, after = S.get("stats") or {}, stats()
        skipped = after.get("skipped", 0) > before.get("skipped", 0)
        rebuilt = after.get("rebuilt", 0) > before.get("rebuilt", 0)
        if label is not None:
            h.check("%s: the design is as before" % what, now == S[label], (now, S[label]))
        if fast:
            h.check("%s: nothing rebuilt" % what, skipped and not rebuilt, (before, after))
        else:
            h.check("%s: rebuilt (cannot vouch for the shapes)" % what, rebuilt and not skipped, (before, after))
        doc = App.ActiveDocument
        touched = [o.Name for o in doc.Objects if "Touched" in o.State]
        h.check("%s: no step left waiting for a rebuild" % what, not touched, touched)
        for o in doc.Objects:
            o.touch()
        doc.recompute()
        h.check("%s: a full rebuild gives the same shapes" % what, shapes() == now, (shapes(), now))
        S["stats"] = stats()

    step.__name__ = "expect_%s%s" % (label or "rebuilt", "_fast" if fast else "_rebuilt")
    return step


# -- Path A: Extrude 1 edited, Ctrl+Z / Ctrl+Y -------------------------------------------------
def a_edit():
    t.double_click("Extrude 1")


def a_type(value="14"):
    def step():
        from sciforge import extrude_ui

        p = extrude_ui.ExtrudePanel.last
        if h.check("the Extrude dialog is open", p is not None and not p._closed):
            ui.type_into(p.distance.widget, value)

    step.__name__ = "a_type_" + value
    return step


def a_ok():
    h.task_button("OK")


def a_edited():
    h.check("the part is taller", tip_volume() > S["volume"] * 1.2, (tip_volume(), S["volume"]))
    S["edited_a"] = shapes()
    S["stats"] = stats()


def a_undo():
    t.ctrl("z")


def a_redo():
    t.ctrl("y")


# -- Path B: Fillet 1 edited, Undo / Redo from the quick access bar -----------------------------
def b_edit():
    t.double_click("Fillet 1")


def b_type(value="3"):
    def step():
        p = b.blend_panel()
        if h.check("the Fillet dialog is open", p is not None):
            b.type_into(p.radius.widget, value)

    step.__name__ = "b_type_" + value
    return step


def b_edited():
    S["edited_b"] = shapes()
    h.check("the rounds are bigger", S["edited_b"] != S["edited_a"])
    S["stats"] = stats()


def b_undo():
    t.undo()


def b_redo():
    t.redo()


# -- Path C: a change outside any transaction ------------------------------------------------------
def c_moved():
    """The rebuild after Ctrl+Z used the moved sketch: the hole is 1 mm along X."""
    centres = [
        f.Surface.Center.x
        for f in h.body().Tip.Shape.Faces
        if f.Surface.__class__.__name__ == "Cylinder" and abs(f.Surface.Radius - 4) < 1e-6
    ]
    h.check("C: the hole follows the moved sketch", centres and abs(centres[0] - 21) < 1e-6, centres)


def c_outside():
    # a script moves the hole's sketch outside any transaction, and leaves it waiting
    sketch = t.obj("Sketch 2")
    sketch.AttachmentOffset = App.Placement(App.Vector(1, 0, 0), App.Rotation())
    S["stats"] = stats()


# -- Path D: two edits, two undos ----------------------------------------------------------------
def d_check_one():
    S["stats_d"] = stats()


def d_both_fast():
    after = stats()
    h.check(
        "D: two Ctrl+Z, nothing rebuilt",
        after["skipped"] - S["stats_d"]["skipped"] == 2 and after["rebuilt"] == S["stats_d"]["rebuilt"],
        (S["stats_d"], after),
    )
    S["stats"] = S["stats_d"]  # (expect() below compares from before the two)


def d_expect():
    now = shapes()
    h.check("D: the design is as before both edits", now == S["before_d"], (now, S["before_d"]))


def d_start():
    S["before_d"] = shapes()


# -- Path E: a value held at its limit, then Undo / Redo -------------------------------------------
def e_start():
    S["before_e"] = shapes()
    S["stats"] = stats()


def e_held():
    p = b.blend_panel()
    text = p.limit_label.text() if p is not None and p.limit_label.isVisible() else ""
    h.check("E: 50 is held at the largest radius that fits", text.startswith("50 mm does not fit"), text)


e_held.wait_ms = 1500


def e_edited():
    fillet = t.obj("Fillet 1")
    radius = fillet.Radius.Value if fillet is not None else 0.0
    h.check("E: the fillet is at the limit (between 3 and 50)", 3 < radius < 50, radius)
    S["edited_e"] = shapes()
    S["stats"] = stats()


# -- Path F: the AI tools' undo steps -------------------------------------------------------------
def ai(tool, args):
    from sciforge.ai import bridge

    try:
        return bridge.call(tool, args, from_chat=True)
    except Exception as exc:  # (the bridge must never raise)
        return {"text": "raised %s" % exc, "is_error": True}


def f_start():
    S["before_f"] = shapes()
    S["stats"] = stats()


def f_edit(radius):
    def step():
        before = shapes()
        answer = ai("edit_step", {"step": t.obj("Fillet 1").Name, "set": {"radius": radius}})
        h.check("F: the AI edit_step R%s is done" % radius, not answer["is_error"], answer["text"][:300])
        names = list(App.ActiveDocument.UndoNames)
        h.check(
            "F: the rounds changed, the last undo step is named AI: ...",
            shapes() != before and names and names[0].startswith("AI:"),
            names[:3],
        )
        S["edited_f"] = shapes()
        S["stats"] = stats()

    step.__name__ = "f_edit_%s" % radius
    return step


def f_undo(which):
    def step():
        answer = ai(which, {})
        h.check("F: the AI %s is done" % which, not answer["is_error"], answer["text"][:300])

    step.__name__ = "f_" + which
    return step


def f_refused():
    S["undo_names"] = list(App.ActiveDocument.UndoNames)
    before = shapes()
    answer = ai("edit_step", {"step": t.obj("Fillet 1").Name, "set": {"radius": 50}})
    h.check(
        "F: R50 is refused with the largest radius that fits",
        answer["is_error"] and "Largest radius that fits here" in answer["text"],
        answer["text"][:400],
    )
    h.check("F: the design is as before", shapes() == before, (shapes(), before))
    names = list(App.ActiveDocument.UndoNames)
    h.check("F: the undo stack is as before", names == S["undo_names"], (names[:3], S["undo_names"][:3]))
    S["stats"] = stats()


def f_right_after_refusal():
    """Ctrl+Z after the refused AI value: the part is the one before the AI edit, whether or
    not the ledger could vouch for the shapes (the trials' transactions were taken back)."""
    now = shapes()
    after = stats()
    skipped = after["skipped"] > S["stats"]["skipped"]
    h.check("F: Ctrl+Z gives the part before the AI edit", now == S["before_f"], (now, S["before_f"]))
    print("[SciForge] undo_fast F: Ctrl+Z after the refusal %s" % ("rebuilt nothing" if skipped else "rebuilt"), flush=True)
    doc = App.ActiveDocument
    for o in doc.Objects:
        o.touch()
    doc.recompute()
    h.check("F: a full rebuild gives the same shapes", shapes() == now, (shapes(), now))
    S["stats"] = stats()


# -- Path G / H: Change Parameters (a sketch dimension, a user parameter) ------------------------
def params_dialog():
    from sciforge import parameters_ui

    return parameters_ui.ParametersDialog.last


def g_change(text):
    """MODIFY > Change Parameters, Sketch 1's width typed `text`, OK (what the dialog does
    when a value is typed in its table: parameters.change_checked inside its transaction)."""

    def step():
        from sciforge import parameters, parameters_ui

        doc = App.ActiveDocument
        S["stats"] = stats()
        dialog = parameters_ui.ParametersDialog(doc)
        dialog.show()
        sketch = t.obj("Sketch 1")
        rows = [
            r
            for r in parameters.model_parameters(doc)
            if r["object"] == sketch.Name and abs(r["value"] - 40) < 1e-6
        ]
        h.check(
            "G: Sketch 1's 40 mm is in Change Parameters",
            bool(rows),
            [(r["owner"], r["label"], r["value"]) for r in parameters.model_parameters(doc)][:12],
        )
        if not rows:
            dialog.reject()
            return
        row = rows[0]
        dialog._apply(
            lambda: parameters.set_model(doc, row, text),
            (sketch, row["path"], "%s = %s" % (row["label"], text)),
        )
        dialog.accept()

    step.__name__ = "g_change_%s" % text
    step.wait_ms = 1500
    return step


def g_edited(width):
    def step():
        box = h.body().Tip.Shape.BoundBox
        h.check("G: the part is %s mm wide" % width, abs(box.XLength - width) < 1e-6, box.XLength)
        S["edited_g"] = shapes()
        S["stats"] = stats()

    step.__name__ = "g_edited_%s" % width
    return step


def g_start():
    S["before_g"] = shapes()
    S["stats"] = stats()


def h_start():
    """A user parameter depth = 10 drives Extrude 1 (made by script: the dialog is tested)."""
    from sciforge import parameters

    doc = App.ActiveDocument
    parameters.add_user(doc, "depth", "mm", "10")
    t.obj("Extrude 1").setExpression("Length", "depth")
    doc.recompute()
    S["before_h"] = shapes()
    S["stats"] = stats()


def h_change(text):
    def step():
        from sciforge import parameters, parameters_ui

        doc = App.ActiveDocument
        S["stats"] = stats()
        dialog = parameters_ui.ParametersDialog(doc)
        dialog.show()
        dialog._apply(
            lambda: parameters.set_user(doc, "depth", text),
            (parameters.container(doc), "depth", "depth = %s" % text),
        )
        dialog.accept()

    step.__name__ = "h_change_%s" % text
    step.wait_ms = 1500
    return step


def h_edited(depth):
    def step():
        box = h.body().Tip.Shape.BoundBox
        h.check("H: the part is %s mm high" % depth, abs(box.ZLength - depth) < 1e-6, box.ZLength)
        S["edited_h"] = shapes()
        S["stats"] = stats()

    step.__name__ = "h_edited_%s" % depth
    return step


h.run(
    "undo_fast",
    [
        setup,
        h.idle_step(),
        # A
        a_edit, a_type("14"), a_ok, h.idle_step(), a_edited,
        remember("noop"),
        a_undo, h.idle_step(),
        expect("original", True, "A Ctrl+Z"),
        # the check's full rebuild was outside a transaction: a fresh edit for the redo
        a_edit, a_type("14"), a_ok, h.idle_step(), a_edited,
        a_undo, h.idle_step(), remember("undone_a"),
        a_redo, h.idle_step(),
        expect("edited_a", True, "A Ctrl+Y"),
        # B
        b_edit, b_type("3"), a_ok, h.idle_step(), b_edited,
        b_undo, h.idle_step(),
        expect("edited_a", True, "B Undo"),
        b_edit, b_type("3"), a_ok, h.idle_step(), b_edited,
        b_undo, h.idle_step(), remember("undone_b"),
        b_redo, h.idle_step(),
        expect("edited_b", True, "B Redo"),
        # C: an edit (12), a script's change; Ctrl+Z rebuilds
        a_edit, a_type("12"), a_ok, h.idle_step(), remember("ignored"),
        c_outside,
        a_undo, h.idle_step(),
        expect(None, False, "C Ctrl+Z after an outside change"),
        c_moved,
        # D: two edits, two Ctrl+Z
        d_start,
        a_edit, a_type("16"), a_ok, h.idle_step(),
        b_edit, b_type("2.5"), a_ok, h.idle_step(), d_check_one,
        a_undo, h.idle_step(), a_undo, h.idle_step(),
        d_both_fast, d_expect,
        # E: a value held at its limit by the dialog, OK, Ctrl+Z / Ctrl+Y
        e_start,
        b_edit, b_type("50"), e_held, a_ok, h.idle_step(), e_edited,
        a_undo, h.idle_step(),
        expect("before_e", True, "E Ctrl+Z after a value held at its limit"),
        b_edit, b_type("50"), e_held, a_ok, h.idle_step(), e_edited,
        a_undo, h.idle_step(), remember("undone_e"),
        a_redo, h.idle_step(),
        expect("edited_e", True, "E Ctrl+Y"),
        # F: the AI tools' undo steps
        f_start,
        f_edit(2.5), h.idle_step(),
        f_undo("undo"), h.idle_step(),
        expect("before_f", True, "F AI undo"),
        f_edit(2.5), h.idle_step(),
        f_undo("undo"), h.idle_step(), remember("undone_f"),
        f_undo("redo"), h.idle_step(),
        expect("edited_f", True, "F AI redo"),
        f_start,
        f_edit(3.5), h.idle_step(),
        f_refused, h.idle_step(),
        a_undo, h.idle_step(),
        f_right_after_refusal,
        # G: a sketch dimension in Change Parameters, Ctrl+Z / Ctrl+Y
        g_start,
        g_change("44"), h.idle_step(), g_edited(44),
        a_undo, h.idle_step(),
        expect("before_g", True, "G Ctrl+Z of a sketch dimension"),
        g_change("44"), h.idle_step(), g_edited(44),
        a_undo, h.idle_step(), remember("undone_g"),
        a_redo, h.idle_step(),
        expect("edited_g", True, "G Ctrl+Y of a sketch dimension"),
        # H: a user parameter in Change Parameters, Ctrl+Z / Ctrl+Y
        h_start,
        h_change("13"), h.idle_step(), h_edited(13),
        a_undo, h.idle_step(),
        expect("before_h", True, "H Ctrl+Z of a user parameter"),
        h_change("13"), h.idle_step(), h_edited(13),
        a_undo, h.idle_step(), remember("undone_h"),
        a_redo, h.idle_step(),
        expect("edited_h", True, "H Ctrl+Y of a user parameter"),
    ],
)
