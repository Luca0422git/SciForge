# SPDX-License-Identifier: LGPL-2.1-or-later
"""AI calls and the undo list in the window (review of the AI documentation, 2026-10-22,
docs/sciforge/sessions/2026-10-22-fix-aidocs.md). The handbook says every AI call that
changes the design is one undo step named "AI: ...", and that the AI panel's Undo last AI
step undoes the newest step when an AI made it. The timeline tools used to open steps of
their own ("Suppress Fillet 1", "Roll History Marker"), so the button answered "The last
step was not made by an AI app"; group_steps made two steps; show_hide made none but left a
step open for the next change to land in."""

import FreeCAD as App

from SciForgeTests.gui import harness as h

s = {}


def call(tool, args):
    from sciforge.ai import bridge

    try:
        return bridge.call(tool, args, from_chat=True)
    except Exception as exc:
        return {"text": "raised %s" % exc, "is_error": True, "image_png_base64": None}


def names():
    doc = App.ActiveDocument
    return list(doc.UndoNames) if doc is not None else []


def build():
    a = call("new_design", {"name": "UndoSteps"})
    h.check("new design", not a["is_error"], a["text"][:200])
    a = call("create_sketch", {"plane": "XY", "geometry": [{"rect": [0, 0, 60, 40]}]})
    h.check("sketch", not a["is_error"], a["text"][:200])
    a = call("extrude", {"profile": "Sketch1", "distance": 10})
    h.check("extrude", not a["is_error"], a["text"][:200])
    a = call("fillet", {"edges": {"type": "line", "parallel": [0, 0, 1], "count": 4}, "radius": 3})
    h.check("fillet", not a["is_error"], a["text"][:200])


def suppress_then_undo_last_ai():
    from sciforge import ai_ui

    a = call("suppress_step", {"steps": ["Fillet1"]})
    h.check("suppress_step answered", not a["is_error"], a["text"][:200])
    h.check("its undo step is named AI: Suppress", names()[:1] == ["AI: Suppress"], names()[:3])
    done = ai_ui.undo_last()
    fillet = App.ActiveDocument.getObject("Fillet1")
    h.check(
        "Undo last AI step undid the AI's suppress",
        bool(done) and not getattr(fillet, "Suppressed", True),
        (done, getattr(fillet, "Suppressed", None), names()[:3]),
    )


def roll_then_undo_last_ai():
    from sciforge import ai_ui
    from sciforge import timeline_ops

    a = call("roll_timeline", {"after": "Extrude1"})
    h.check("roll_timeline answered", not a["is_error"], a["text"][:200])
    h.check("its undo step is named AI: ...", names()[:1] == ["AI: Roll history marker"], names()[:3])
    done = ai_ui.undo_last()
    h.check(
        "Undo last AI step undid the AI's roll",
        bool(done) and timeline_ops.timeline(App.ActiveDocument).at_end,
        (done, names()[:3]),
    )


def group_is_one_step():
    before = names()
    a = call("group_steps", {"steps": ["Sketch1", "Extrude1"], "name": "Base"})
    h.check("group_steps answered", not a["is_error"], a["text"][:200])
    h.check(
        "group_steps is one undo step",
        len(names()) - len(before) in (0, 1) and names()[:1] == ["AI: Group steps"]
        and names()[1:2] == before[:1],
        names()[:4],
    )
    a = call("undo", {})
    h.check("one undo takes the group back", names() == before, (a["text"][:120], names()[:4]))


def show_hide_leaves_nothing_open():
    before = names()
    a = call("show_hide", {"targets": ["Sketch1"], "visible": False})
    h.check("show_hide answered", not a["is_error"], a["text"][:200])
    h.check("show_hide is no undo step (its page says so)", names() == before, names()[:3])
    h.check("no undo step is left open", App.getActiveTransaction() is None,
            App.getActiveTransaction())
    call("show_hide", {"targets": ["Sketch1"], "visible": True})


h.run(
    "ai_undo_steps",
    [build, suppress_then_undo_last_ai, roll_then_undo_last_ai, group_is_one_step,
     show_hide_leaves_nothing_open],
)
