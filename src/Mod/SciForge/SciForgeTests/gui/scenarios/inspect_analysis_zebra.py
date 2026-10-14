# SPDX-License-Identifier: LGPL-2.1-or-later
"""INSPECT > Zebra Analysis with real input, on the box with its top edges rounded (r = 4):
an empty design refused with a reason; nothing selected (the dialog waits, OK says why);
the top face clicked (the body gets stripes: black and white on the screen, the model's
own faces switched off under them); Direction, Repeats, Opacity, Lock Stripes (the stripes
stay while the view turns; unlocked they move), High Quality; OK (Zebra1 in the browser's
Analysis folder); its eye hides it (the model looks as before) and shows it again; edited
by double-click and Cancelled (values back); undo / redo; saved and opened again (still
striped); deleted from the browser (model back); a new one cancelled with Esc."""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import analysis_steps as a
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import inspect_steps as s
from SciForgeTests.gui import timeline_input as ti

st = {}
KIND = "ZebraAnalysis"


def texcoords():
    """The stripe coordinates drawn on the first body (from the view provider's node)."""
    objs = a.analyses(KIND)
    if not objs:
        return []
    proxy = objs[0].ViewObject.Proxy
    if not proxy.stripes:
        return []
    node = proxy.stripes[0][3]
    return [node.point[i][0] for i in range(node.point.getNum())]


def spread():
    values = texcoords()
    return (max(values) - min(values)) if values else 0.0


# -- an empty design ---------------------------------------------------------------------------
def empty_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("ZebraEmpty")
    a.inspect("Zebra Analysis")


def empty_refused():
    from sciforge import commands

    h.check("no dialog in an empty design", a.panel() is None)
    msg = commands._TOLD.get("msg") or ""
    h.check("it says there is no body yet", "no body" in msg, msg)
    App.closeDocument(App.ActiveDocument.Name)


# -- the zebra ---------------------------------------------------------------------------------
def start():
    a.inspect("Zebra Analysis")


def waits():
    p = a.panel()
    h.check("Zebra Analysis dialog open", p is not None and p.title == "Zebra Analysis")
    if p is None:
        return
    h.check("nothing made yet", not a.analyses(KIND))
    h.check("the Bodies box is blue", p.box.button.isChecked())
    h.check("it asks for bodies", "bodies" in p.message.text(), p.message.text())
    h.check("model faces drawn", a.model_faces_shown())
    h.task_button("OK")


def ok_refused():
    p = a.panel()
    h.check("OK with nothing picked keeps the dialog open", p is not None)
    h.check("and says what to do", p is not None and "Click the bodies" in p.message.text())
    h.click(a.TOP_FACE)


def striped():
    p = a.panel()
    objs = a.analyses(KIND)
    h.check("Zebra1 made", len(objs) == 1 and objs[0].Label == "Zebra1", [o.Label for o in objs])
    h.check("the box says Body", p is not None and p.box.button.text() == "Body")
    h.check("the model's own faces are off under the stripes", not a.model_faces_shown())
    counts = a.colors()
    st["counts"] = counts
    h.check("black stripes on the screen", a.share(counts, "black") > 0.15, counts)
    h.check("white stripes on the screen", a.share(counts, "white") > 0.15, counts)
    h.check("default direction Vertical", objs and objs[0].Direction == "Vertical")
    h.check("default 20 repeats", objs and objs[0].Repeats == 20)
    st["spread20"] = spread()
    st["tex_v"] = texcoords()
    h.shot("1-zebra")
    a.set_combo(p.field("Direction"), "Horizontal")


def horizontal():
    objs = a.analyses(KIND)
    h.check("Direction Horizontal", objs and objs[0].Direction == "Horizontal")
    tex = texcoords()
    changed = len(tex) == len(st["tex_v"]) and any(
        abs(x - y) > 1e-3 for x, y in zip(tex, st["tex_v"])
    )
    h.check("the stripes turned (other coordinates)", changed)
    counts = a.colors()
    h.check("still striped", a.share(counts, "black") > 0.1 and a.share(counts, "white") > 0.1)
    h.shot("2-horizontal")
    st["spread20"] = spread()
    a.type_spin(a.panel().field("Repeats"), 5)


def repeats_5():
    objs = a.analyses(KIND)
    h.check("Repeats 5", objs and objs[0].Repeats == 5)
    ratio = spread() / st["spread20"] if st["spread20"] else 0
    h.check("a quarter of the stripes", abs(ratio - 0.25) < 0.01, ratio)
    a.slide(a.panel().field("Opacity"), 40)


def opacity_40():
    objs = a.analyses(KIND)
    h.check("Opacity 40", objs and objs[0].Opacity == 40)
    counts = a.colors()
    h.check(
        "no pure black or white any more (mixed with the body's grey)",
        a.share(counts, "black", "white") < 0.05,
        counts,
    )
    h.shot("3-opacity")
    a.slide(a.panel().field("Opacity"), 100)


def lock():
    a.tick(a.panel().field("LockStripes"), True)


def locked():
    objs = a.analyses(KIND)
    h.check("Lock Stripes on", objs and objs[0].LockStripes)
    h.check("the camera was kept", objs and objs[0].LockedHeight > 0)
    st["locked"] = texcoords()
    gl = h.gl_widget()
    c = gl.rect().center()
    h.drag(
        c,
        QtCore.QPoint(c.x() + 120, c.y() + 40),
        button=QtCore.Qt.MiddleButton,
        modifiers=QtCore.Qt.ShiftModifier,
    )


def locked_stay():
    tex = texcoords()
    same = len(tex) == len(st["locked"]) and all(
        abs(x - y) < 1e-9 for x, y in zip(tex, st["locked"])
    )
    h.check("locked stripes stay on the model when it turns", same)
    a.tick(a.panel().field("LockStripes"), False)


def unlocked():
    st["unlocked"] = texcoords()
    gl = h.gl_widget()
    c = gl.rect().center()
    h.drag(
        c,
        QtCore.QPoint(c.x() - 120, c.y() - 40),
        button=QtCore.Qt.MiddleButton,
        modifiers=QtCore.Qt.ShiftModifier,
    )


unlocked.wait_ms = 900


def moved():
    tex = texcoords()
    changed = len(tex) == len(st["unlocked"]) and any(
        abs(x - y) > 1e-3 for x, y in zip(tex, st["unlocked"])
    )
    h.check("unlocked stripes move when the view turns", changed)
    st["points"] = len(tex)
    a.tick(a.panel().field("HighQuality"), True)


moved.wait_ms = 1200


def high_quality():
    tex = texcoords()
    h.check("High Quality: a finer display", len(tex) > st["points"] * 2, (len(tex), st["points"]))
    a.tick(a.panel().field("HighQuality"), False)
    h.fit()


def ok():
    h.task_button("OK")


def kept():
    h.check("the dialog closed", a.panel() is None)
    objs = a.analyses(KIND)
    h.check("Zebra1 kept", len(objs) == 1)
    a.open_analysis_folder()
    h.check(
        "in the browser's Analysis folder",
        "Zebra1" in (ti.children("Analysis") or []),
        ti.children("Analysis"),
    )
    h.check("not in the timeline", not any("Zebra" in t for t in s.timeline_titles()))
    h.check("still drawn", not a.model_faces_shown())
    s.eye("Zebra1")


def hidden():
    objs = a.analyses(KIND)
    h.check("hidden with its eye", objs and not objs[0].ViewObject.Visibility)
    h.check("the model's faces are back", a.model_faces_shown())
    counts = a.colors()
    h.check("no stripes on the screen", a.share(counts, "white") < 0.02, counts)
    h.shot("4-hidden")
    s.eye("Zebra1")


def shown_again():
    h.check("shown again", not a.model_faces_shown())
    ti.double_click_row("Zebra1")


def editing():
    p = a.panel()
    h.check("double-click opens Edit Zebra1", p is not None and p.editing)
    if p is None:
        return
    h.check("its values are back (Repeats 5)", p.field("Repeats").value() == 5)
    h.check("Direction Horizontal", p.field("Direction").currentText() == "Horizontal")
    a.type_spin(p.field("Repeats"), 12)


def edited():
    objs = a.analyses(KIND)
    h.check("the edit shows at once (12)", objs and objs[0].Repeats == 12)
    h.task_button("Cancel")


def cancelled():
    objs = a.analyses(KIND)
    h.check("Cancel puts Repeats back to 5", objs and objs[0].Repeats == 5)
    h.check("still one analysis", len(objs) == 1)
    s.undo()


def undone():
    h.check("undo removes the zebra", not a.analyses(KIND))
    h.check("the model's faces are back", a.model_faces_shown())
    s.redo()


def redone():
    objs = a.analyses(KIND)
    h.check("redo brings it back", len(objs) == 1)
    h.check("and draws it", not a.model_faces_shown())


redone.wait_ms = 900


def save():
    st["path"] = a.save_reopen("inspect_analysis_zebra.FCStd")


save.wait_ms = 1500


def reopened():
    objs = a.analyses(KIND)
    h.check("after reopening: Zebra1", len(objs) == 1 and objs[0].Label == "Zebra1")
    h.check("its Repeats", objs and objs[0].Repeats == 5)
    h.check("drawn again", not a.model_faces_shown())
    counts = a.colors()
    h.check("striped on the screen", a.share(counts, "white") > 0.05, counts)
    h.shot("5-reopened")
    a.open_analysis_folder()
    ti.row_menu("Zebra1", "Delete")


def deleted():
    h.check("deleted from the browser", not a.analyses(KIND))
    h.check("the model's faces are back", a.model_faces_shown())
    a.inspect("Zebra Analysis")


def esc_new():
    h.click(a.TOP_FACE)


def esc_made():
    h.check("a new zebra shows", len(a.analyses(KIND)) == 1)
    s.press_escape()


def esc_done():
    h.check("Esc closes the dialog", a.panel() is None)
    h.check("and leaves nothing", not a.analyses(KIND))
    h.check("the model's faces are back", a.model_faces_shown())


h.run(
    "inspect_analysis_zebra",
    [empty_design, empty_refused]
    + a.filleted_block_steps("Zebra")
    + [
        start,
        waits,
        ok_refused,
        striped,
        horizontal,
        repeats_5,
        opacity_40,
        lock,
        locked,
        locked_stay,
        unlocked,
        moved,
        high_quality,
        ok,
        kept,
        hidden,
        shown_again,
        editing,
        edited,
        cancelled,
        undone,
        redone,
        save,
        reopened,
        deleted,
        esc_new,
        esc_made,
        esc_done,
    ],
)
