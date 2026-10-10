# SPDX-License-Identifier: LGPL-2.1-or-later
"""Thread on a shaft the way a Fusion user does it, only real input:

1. A 40 x 30 x 10 box with a boss d6 x 12 on top (sketch on the top face, E).
2. CREATE > Thread with nothing selected: the dialog waits; only round faces light up.
3. Click the boss's side: a cosmetic M6x1 (class 6g, outside) thread, the part unchanged,
   a dashed helix drawn on the boss.
4. Modeled: the real thread is cut. Full Length off, Thread Length 8, Offset 2; drag the
   blue length arrow; M6x0.75; Left hand. OK.
5. Ctrl+Z / Ctrl+Y; edit from the timeline (Modeled off again); Cancel a second thread.

Hand-derived volumes: a modeled thread removes, per mm of length, the cross-section
(2 pi / P) * integral of r w(r) dr over the groove (thread_core.removed_area): the ISO 68-1
groove is P/4 wide at the root (R - 5H/8) and opens at 60 degrees; the shaft is the major
diameter. Cosmetic threads remove nothing.
"""
import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import hole_steps as hs
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import widget_input as w

V = App.Vector
s = {}
BOSS = hs.BOX + math.pi * 9.0 * 12.0
# On the boss's side facing the viewer, nearer its top end (z 22) than its foot (z 10).
SIDE = V(20 + 3 * math.cos(math.radians(-45)), 15 + 3 * math.sin(math.radians(-45)), 19)


def removed(length, pitch=1.0):
    from sciforge import thread_core

    return thread_core.removed_volume(3.0, pitch, False, 3.0, length)


def drawn():
    from sciforge import thread_ui

    return thread_ui.CosmeticThreads.count(App.ActiveDocument.Name)


def open_thread():
    Gui.Selection.clearSelection()
    si.menu_item("CREATE", "Thread")


def waiting():
    p = hs.thread_panel()
    h.check("Thread dialog open", p is not None and p.title == "Thread")
    if p is None:
        return
    h.check("nothing picked yet", p.target is None and not p.faces)
    h.check("no error before picking", p.message.text() == "", p.message.text())
    h.check("model unchanged", hs.close(h.solid_volume(), BOSS))
    h.check("a flat face cannot be picked", not p.allow(h.body().Tip, _top_face()))
    hs.no_popups("Thread with nothing selected")
    h.shot("1-waiting")


def _top_face():
    for i, f in enumerate(h.body().Tip.Shape.Faces, start=1):
        if f.Surface.TypeId == "Part::GeomPlane" and abs(f.CenterOfMass.z - 22) < 1e-6:
            return "Face%d" % i
    return "Face1"


def click_side():
    h.fit()
    h.click(SIDE)


def cosmetic():
    p = hs.thread_panel()
    h.check("a thread is previewed", p is not None and p.target is not None, hs.message(p))
    if p is None or p.target is None:
        return
    h.check(
        "size taken from the face: M6x1",
        p.designation.currentText() == "M6x1",
        p.designation.currentText(),
    )
    h.check(
        "outside thread class 6g",
        p.thread_class.currentText() == "6g",
        p.thread_class.currentText(),
    )
    h.check("the dialog says outside", "Outside" in p.info.text(), p.info.text())
    h.check("cosmetic: the part is unchanged", hs.close(h.solid_volume(), BOSS), h.solid_volume())
    h.check("cosmetic: a dashed helix is drawn", drawn() == 1, drawn())
    h.shot("2-cosmetic")


def tick_modeled():
    p = hs.thread_panel()
    if p:
        hs.click_checkbox(p.modeled)


tick_modeled.wait_ms = 2500  # a modeled thread takes a moment


def modeled():
    v = h.solid_volume()
    expect = BOSS - removed(12)
    h.check("modeled M6x1 over the boss's 12 mm", hs.close(v, expect), (v, expect))
    h.check("valid solid", h.body().Shape.isValid())
    h.check("no cosmetic drawing for a modeled thread", drawn() == 0, drawn())
    h.shot("3-modeled")


def untick_full():
    p = hs.thread_panel()
    if p:
        hs.click_checkbox(p.full_length)


untick_full.wait_ms = 2500  # FreeCAD blocks input while a modeled thread is computed


def partial_fields():
    p = hs.thread_panel()
    h.check(
        "Thread Length and Offset shown",
        p and p.length.widget.isVisible() and p.offset.widget.isVisible(),
    )
    if p:
        hs.type_into(p.length.widget, "8")
        hs.type_into(p.offset.widget, "2")


partial_fields.wait_ms = 2500


def partial():
    v = h.solid_volume()
    expect = BOSS - removed(8)
    p = hs.thread_panel()
    t = p.target if p else None
    h.check(
        "thread 8 long, 2 from the end",
        hs.close(v, expect),
        (
            v,
            expect,
            p and (p.length.value(), p.offset.value()),
            t and (t.Length, t.Offset, t.FullLength),
        ),
    )
    h.check("length arrow shown", p and "length" in p.draggers)
    h.check(
        "the thread starts 2 below the top, the end nearer the click: z 12 to 20",
        _global_span(p.target if p else None) == (12.0, 20.0),
        _global_span(p.target if p else None),
    )


def _global_span(feature):
    """(z low, z high) the thread covers, in the model's coordinates (the boss is upright)."""
    from sciforge import thread

    if feature is None:
        return None
    rec = thread.computed(feature).get("threads", [])
    if len(rec) != 1:
        return None
    t = rec[0]
    ends = [round(t["base"][2] + t["axis"][2] * z, 6) for z in (t["z0"], t["z1"])]
    return (min(ends) + 0.0, max(ends) + 0.0)


def drag_length():
    p = hs.thread_panel()
    arrow = p.draggers.get("length") if p else None
    if arrow is None:
        h.check("length arrow to drag", False)
        return
    s["before"] = p.length.value()
    hs.drag_arrow(p.length_origin, p.length_direction, arrow.distance(), -2.0)


drag_length.wait_ms = 2500


def dragged():
    p = hs.thread_panel()
    length = p.length.value() if p else 0
    h.check(
        "dragging the arrow back shortens the thread",
        length < s["before"] - 0.5,
        (s["before"], length),
    )
    v = h.solid_volume()
    expect = BOSS - removed(length)
    h.check("preview follows the dragged length", hs.close(v, expect), (v, expect))
    if p:
        hs.type_into(p.length.widget, "8")


dragged.wait_ms = 2500


def fine_pitch():
    p = hs.thread_panel()
    if p:
        b.choose(p.designation, "M6x0.75")


fine_pitch.wait_ms = 2500


def fine():
    v = h.solid_volume()
    expect = BOSS - removed(8, 0.75)
    h.check("M6x0.75 fine thread", hs.close(v, expect), (v, expect))
    p = hs.thread_panel()
    if p:
        b.choose(p.direction, "Left hand")


fine.wait_ms = 2500


def left():
    p = hs.thread_panel()
    h.check("left-hand thread", p and p.target and p.target.LeftHanded)
    v = h.solid_volume()
    expect = BOSS - removed(8, 0.75)
    h.check("a left-hand thread removes the same", hs.close(v, expect), (v, expect))
    h.shot("4-left")


def ok():
    h.task_button("OK")


ok.wait_ms = 1500


def after_ok():
    h.check("dialog closed", hs.thread_panel() is None and not Gui.Control.activeDialog())
    shape = h.body().Shape
    expect = BOSS - removed(8, 0.75)
    h.check("thread kept", hs.close(shape.Volume, expect), (shape.Volume, expect))
    h.check("valid solid", shape.isValid())
    th = hs.threads()
    h.check("one Thread, the end of the timeline", len(th) == 1 and h.body().Tip is th[0], th)
    h.check("Thread 1 in the timeline", "Thread 1" in hs.timeline_titles(), hs.timeline_titles())
    h.check("no leftover selection", not Gui.Selection.getSelectionEx())
    s["v"] = shape.Volume
    h.shot("5-thread1")


def undo():
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


undo.wait_ms = 1500


def after_undo():
    h.check(
        "Ctrl+Z removes the thread",
        hs.close(h.solid_volume(), BOSS) and not hs.threads(),
        (h.solid_volume(), hs.threads()),
    )


def redo():
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


redo.wait_ms = 2500


def after_redo():
    h.check(
        "Ctrl+Y brings it back",
        hs.close(h.solid_volume(), s["v"]) and len(hs.threads()) == 1,
        h.solid_volume(),
    )
    h.fit()


def edit_from_timeline():
    b.timeline_double_click("Thread 1")


def edit_open():
    p = hs.thread_panel()
    h.check("double-click opens the Thread dialog on it", p is not None and p.editing)
    if p is None:
        return
    h.check(
        "its settings are shown",
        p.designation.currentText() == "M6x0.75"
        and p.modeled.isChecked()
        and not p.full_length.isChecked()
        and abs(p.length.value() - 8) < 1e-9
        and p.direction.currentText() == "Left hand",
        (p.designation.currentText(), p.modeled.isChecked(), p.length.value()),
    )
    h.check("its face is picked", len(p.faces) == 1, p.faces)
    hs.click_checkbox(p.modeled)


edit_open.wait_ms = 2000


def edit_ok():
    h.task_button("OK")


def after_edit():
    h.check(
        "cosmetic again: the part as before", hs.close(h.solid_volume(), BOSS), h.solid_volume()
    )
    h.check("still one thread", len(hs.threads()) == 1)
    h.check("drawn as a cosmetic thread", drawn() == 1, drawn())
    s["objects"] = len(App.ActiveDocument.Objects)
    h.shot("6-cosmetic-again")


def cancel_start():
    h.fit()
    si.menu_item("CREATE", "Thread")


def cancel_click():
    h.click(SIDE)


def cancel_preview():
    p = hs.thread_panel()
    h.check("a second thread is previewed", p is not None and p.target is not None)
    h.task_button("Cancel")


def after_cancel():
    h.check("Cancel leaves the model as it was", hs.close(h.solid_volume(), BOSS))
    h.check("no new objects", len(App.ActiveDocument.Objects) == s["objects"])
    h.check("dialog closed", not Gui.Control.activeDialog())
    h.check("still drawn once", drawn() == 1, drawn())
    h.check("no kernel errors in the Report view", not b.report_has_kernel_errors())
    hs.no_popups("the thread scenario")


h.run(
    "hole_thread",
    b.box_steps("Thread")
    + hs.make_boss("boss", radius=3.0, height=12.0)
    + [
        open_thread,
        waiting,
        click_side,
        cosmetic,
        tick_modeled,
        modeled,
        untick_full,
        partial_fields,
        partial,
        drag_length,
        dragged,
        fine_pitch,
        fine,
        left,
        ok,
        after_ok,
        undo,
        after_undo,
        redo,
        after_redo,
        edit_from_timeline,
        edit_open,
        edit_ok,
        after_edit,
        cancel_start,
        cancel_click,
        cancel_preview,
        after_cancel,
    ],
)
