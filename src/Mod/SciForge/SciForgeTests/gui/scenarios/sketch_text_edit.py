# SPDX-License-Identifier: LGPL-2.1-or-later
"""Sketch Text, changing a text that exists, real input only. Fusion's behaviour (Autodesk
help "Create text in a sketch", "Edit text in a sketch"; Fusion forum threads on moving
and rotating sketch text):

D1  a double-click on the text opens the Text dialog with its values; changing the text
    and the height and pressing OK changes it (one undo step "Edit Text").
D2  Esc in that dialog leaves the text as it was.
D3  dragging the letters moves the text and its frame (one undo step "Move Text"); Ctrl+Z
    puts it back, Ctrl+Y moves it again.
D4  in the dialog, a click on a frame dot makes it the turning point; dragging the round
    handle turns the frame about it; typing an Angle turns it there too; OK keeps it, the
    letters inside the turned frame.
D5  a click picks the text; Delete deletes it with its frame; Ctrl+Z brings it back.
D6  right-click on the text > Explode Text turns it into sketch curves (no text left);
    Ctrl+Z makes it a text again.
"""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import text_input as ti

V = App.Vector
s = {}


def near(a, b, tol):
    return abs(a - b) <= tol


def doc():
    return App.ActiveDocument


def undo_name(name):
    return bool(doc().UndoNames) and doc().UndoNames[0] == name


def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("TextEdit")
    h.fit()
    h.ribbon("Create Sketch")


def pick_xy():
    h.click(V(12, -8, 0))


def sketch_open():
    sk = h.in_sketch()
    h.check("sketch open on XY", sk is not None)
    s["sketch"] = sk
    h.view().viewTop()
    cam = h.view().getCameraNode()
    try:
        cam.height.setValue(160.0)
    except Exception:
        pass
    cam.position.setValue(40.0, 20.0, 100.0)
    QtWidgets.QApplication.processEvents()


def first_letter():
    return ti.at(s["sketch"], *ti.middle_of_first_letter(s["text"]))


# -- D1 double-click edits ----------------------------------------------------------------------
def d1_double_click():
    h.double_click(first_letter())


def d1_dialog():
    d = ti.dialog()
    h.check("D1 the double-click opened the Text dialog", d is not None)
    if d is None:
        return
    h.check("D1 it edits the text", d.target is s["text"], d.target)
    h.check("D1 with its text", d.text_box.toPlainText() == "Hello", d.text_box.toPlainText())
    h.check("D1 and its height", d.height.text().split()[0] in ("8", "8.0"), d.height.text())
    h.check("D1 the frame is already placed", d.frame_placed)
    ti.type_text("Robot")
    ti.type_field(d.height, "10")


def d1_ok():
    QtCore.QThread.msleep(100)
    QtWidgets.QApplication.processEvents()
    ti.ok()


def d1_changed():
    obj = s["text"]
    h.check("D1 the dialog closed", ti.dialog() is None)
    h.check("D1 the text says Robot", obj.ResolvedText == "Robot", obj.ResolvedText)
    h.check("D1 height 10", near(obj.TextHeight.Value, 10.0, 1e-9), obj.TextHeight)
    h.check("D1 still one text", len(ti.texts(s["sketch"])) == 1)
    h.check("D1 still its four frame lines", len(s["sketch"].Geometry) == 4)
    h.check("D1 one undo step 'Edit Text'", undo_name("Edit Text"), doc().UndoNames[:3])
    h.check("D1 the letters inside the frame", ti.letters_in_frame(obj), ti.letters_box(obj))
    h.shot("d1-edited")


# -- D2 Esc -------------------------------------------------------------------------------------
def d2_open():
    h.double_click(first_letter())


def d2_type_and_escape():
    d = ti.dialog()
    h.check("D2 the dialog opened again", d is not None)
    if d is None:
        return
    s["undo_count"] = len(doc().UndoNames)
    ti.type_text("Something else")
    h.press(QtCore.Qt.Key_Escape)


def d2_kept():
    obj = s["text"]
    h.check("D2 Esc closed the dialog", ti.dialog() is None)
    h.check("D2 the text is unchanged", obj.ResolvedText == "Robot", obj.ResolvedText)
    h.check("D2 no undo step", len(doc().UndoNames) == s["undo_count"], doc().UndoNames[:3])


# -- D3 drag to move ----------------------------------------------------------------------------
def d3_drag():
    obj = s["text"]
    s["frame_before"] = ti.frame_of(obj)
    x, y = ti.middle_of_first_letter(obj)
    sk = s["sketch"]
    start = ti.screen(sk, x, y)
    end = ti.screen(sk, x + 20, y + 10)
    a, b = si.sketch_at(sk, start), si.sketch_at(sk, end)
    s["moved_by"] = (b[0] - a[0], b[1] - a[1])
    h.drag(start, end, steps=16)


def d3_moved():
    obj = s["text"]
    (x0, y0), a0, w0, h0 = s["frame_before"]
    now = ti.frame_of(obj)
    h.check("D3 the frame is still there", now is not None)
    if now is None:
        return
    (x1, y1), a1, w1, h1 = now
    dx, dy = s["moved_by"]
    h.check(
        "D3 the drag moved the text the mouse's way",
        near(x1 - x0, dx, 0.05)
        and near(y1 - y0, dy, 0.05)
        and abs(dx - 20) < 1
        and abs(dy - 10) < 1,
        ((x1 - x0, y1 - y0), (dx, dy)),
    )
    h.check(
        "D3 without turning or resizing it",
        near(a1, a0, 1e-6) and near(w1, w0, 1e-6) and near(h1, h0, 1e-6),
        now,
    )
    h.check("D3 the letters went with it", ti.letters_in_frame(obj), ti.letters_box(obj))
    h.check("D3 one undo step 'Move Text'", undo_name("Move Text"), doc().UndoNames[:3])
    s["frame_moved"] = now
    h.press("z", QtCore.Qt.ControlModifier)


def d3_undone():
    (x0, y0), _a, _w, _h = s["frame_before"]
    (x1, y1), _a, _w, _h = ti.frame_of(s["text"])
    h.check("D3 Ctrl+Z put it back", near(x1, x0, 1e-6) and near(y1, y0, 1e-6), (x1, y1))
    h.check("D3 the letters too", ti.letters_in_frame(s["text"]), ti.letters_box(s["text"]))
    h.press("y", QtCore.Qt.ControlModifier)


def d3_redone():
    (x0, y0), _a, _w, _h = s["frame_moved"]
    (x1, y1), _a, _w, _h = ti.frame_of(s["text"])
    h.check("D3 Ctrl+Y moved it again", near(x1, x0, 1e-6) and near(y1, y0, 1e-6), (x1, y1))


# -- D4 turning ---------------------------------------------------------------------------------
def d4_open():
    h.double_click(first_letter())


def d4_pick_pivot():
    from sciforge import text_core

    d = ti.dialog()
    h.check("D4 the dialog opened", d is not None)
    if d is None:
        return
    s["center"] = text_core.snap_points(*d.frame())["center"]
    ti.click_sketch(s["sketch"], *s["center"])


def d4_drag_handle():
    d = ti.dialog()
    h.check("D4 a click on the middle dot makes it the turning point", d.pivot == "center")
    sk = s["sketch"]
    hx, hy = d.handle_point()
    cx, cy = s["center"]
    ex, ey = cx - (hy - cy), cy + (hx - cx)  # a quarter turn to the left about the middle
    h.drag(ti.screen(sk, hx, hy), ti.screen(sk, ex, ey), steps=24)


def d4_turned():
    from sciforge import text_core

    d = ti.dialog()
    _corner, angle, _w, _h = d.frame()
    h.check("D4 the handle turned the frame a quarter turn", near(angle, 90.0, 1.5), angle)
    QtCore.QThread.msleep(100)
    QtWidgets.QApplication.processEvents()
    h.check("D4 the previewed letters turn with it", ti.preview_in_frame(d))
    h.check("D4 the Angle box shows it", near(float(d.angle.text()), angle, 0.01), d.angle.text())
    center = text_core.snap_points(*d.frame())["center"]
    h.check(
        "D4 about the middle (it stayed put)",
        near(center[0], s["center"][0], 1e-6) and near(center[1], s["center"][1], 1e-6),
        (center, s["center"]),
    )
    ti.type_field(d.angle, "30")


def d4_typed():
    d = ti.dialog()
    QtCore.QThread.msleep(100)
    QtWidgets.QApplication.processEvents()
    _corner, angle, _w, _h = d.frame()
    h.check("D4 typing 30 turns it to 30 degrees", near(angle, 30.0, 1e-6), angle)
    h.check("D4 the previewed letters turn with the frame", ti.preview_in_frame(d))
    h.shot("d4-turned")
    ti.ok()


def d4_kept():
    from sciforge import text_core

    obj = s["text"]
    found = ti.frame_of(obj)
    h.check(
        "D4 OK kept the turn: the frame lines at 30 degrees",
        found is not None and near(found[1], 30, 1e-6),
        found,
    )
    if found is None:
        return
    h.check("D4 the text's angle is 30", near(obj.Angle.Value, 30.0, 1e-6), obj.Angle)
    center = text_core.snap_points(*found)["center"]
    h.check(
        "D4 still about the middle",
        near(center[0], s["center"][0], 1e-6) and near(center[1], s["center"][1], 1e-6),
        center,
    )
    h.check("D4 the letters turned with the frame", ti.letters_in_frame(obj), ti.letters_box(obj))
    h.check("D4 one undo step 'Edit Text'", undo_name("Edit Text"), doc().UndoNames[:3])


# -- D5 Delete ----------------------------------------------------------------------------------
def d5_pick():
    ti.click_sketch(s["sketch"], *ti.middle_of_first_letter(s["text"]))


def d5_delete():
    layer = ti.layer()
    h.check(
        "D5 the click picked the text",
        layer is not None and layer.picked() == [s["text"]],
        layer and layer.picked(),
    )
    h.press(QtCore.Qt.Key_Delete)


def d5_deleted():
    sk = s["sketch"]
    h.check("D5 Delete deleted the text", ti.texts(sk) == [], ti.texts(sk))
    h.check("D5 and its frame", len(sk.Geometry) == 0, len(sk.Geometry))
    h.check("D5 one undo step 'Delete Text'", undo_name("Delete Text"), doc().UndoNames[:3])
    h.press("z", QtCore.Qt.ControlModifier)


def d5_back():
    sk = s["sketch"]
    found = ti.texts(sk)
    h.check("D5 Ctrl+Z brought it back", len(found) == 1, found)
    h.check("D5 with its frame", len(sk.Geometry) == 4, len(sk.Geometry))
    if found:
        s["text"] = found[0]
        h.check("D5 the same text", found[0].ResolvedText == "Robot", found[0].ResolvedText)


# -- D6 Explode ---------------------------------------------------------------------------------
def d6_right_click():
    s["edges"] = len(s["text"].Shape.Edges)
    h.click(first_letter(), button=QtCore.Qt.RightButton)


def d6_menu():
    labels = []
    menu = si.marking_menu()
    if menu is not None:
        listing = menu.findChild(QtWidgets.QListWidget, "SciForgeMarkingList")
        labels = [listing.item(i).text() for i in range(listing.count())]
    h.check(
        "D6 the right-click menu offers Explode Text",
        any("Explode Text" in t for t in labels),
        labels,
    )
    h.check("D6 and Edit Text", any("Edit Text" in t for t in labels), labels)
    ti.marking_list_click("Explode Text")


def d6_exploded():
    sk = s["sketch"]
    h.check("D6 no text left", ti.texts(sk) == [], ti.texts(sk))
    curves = [i for i in range(len(sk.Geometry)) if not sk.getConstruction(i)]
    frame = [i for i in range(len(sk.Geometry)) if sk.getConstruction(i)]
    h.check(
        "D6 the letters are sketch curves", len(curves) >= s["edges"], (len(curves), s["edges"])
    )
    h.check("D6 the frame is gone", frame == [], frame)
    h.check("D6 one undo step 'Explode Text'", undo_name("Explode Text"), doc().UndoNames[:3])
    h.shot("d6-exploded")
    h.press("z", QtCore.Qt.ControlModifier)


def d6_undone():
    sk = s["sketch"]
    found = ti.texts(sk)
    h.check("D6 Ctrl+Z made it a text again", len(found) == 1, found)
    h.check("D6 and only its frame in the sketch", len(sk.Geometry) == 4, len(sk.Geometry))


steps = [new_design, pick_xy, sketch_open]
steps += ti.text_steps(s, (5, 5), (65, 25), "Hello", 8)
steps += [
    d1_double_click,
    d1_dialog,
    d1_ok,
    d1_changed,
    d2_open,
    d2_type_and_escape,
    d2_kept,
    d3_drag,
    d3_moved,
    d3_undone,
    d3_redone,
    d4_open,
    d4_pick_pivot,
    d4_drag_handle,
    d4_turned,
    d4_typed,
    d4_kept,
    d5_pick,
    d5_delete,
    d5_deleted,
    d5_back,
    d6_right_click,
    d6_menu,
    d6_exploded,
    d6_undone,
]
h.run("sketch_text_edit", steps)
