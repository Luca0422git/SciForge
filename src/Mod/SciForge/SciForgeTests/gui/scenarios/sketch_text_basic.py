# SPDX-License-Identifier: LGPL-2.1-or-later
"""Sketch Text, the everyday path (Luca: "write text on a face, extrude it"), real input
only. Fusion's behaviour (Autodesk help "Create text in a sketch", "Reference: Text
dialog"):

T1  SKETCH > CREATE > Text opens the Text dialog; it waits for the frame's first corner.
T2  two clicks place the frame; the dialog then waits for the text.
T3  typing shows the letters inside the frame at once (preview), in the chosen height.
T4  OK makes the text (one undo step): it belongs to the sketch, has its frame (four
    construction lines held as a rectangle), and is no timeline step of its own.
T5  an empty text is refused: OK keeps the dialog open and says why.
T6  Ctrl+Z takes the text and its frame away; Ctrl+Y brings them back.
T7  after Finish Sketch, E takes the sketch's only profile, the text, by itself; dragging
    the distance up extrudes the letters (the volume is the letters' area times it).
"""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets

from SciForgeTests.gui import arrow_input as arrows
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import text_input as ti

V = App.Vector
s = {}


def near(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("TextBasic")
    h.fit()
    h.ribbon("Create Sketch")


def pick_xy():
    h.click(V(12, -8, 0))


def sketch_open():
    sk = h.in_sketch()
    h.check("sketch open on XY", sk is not None)
    s["sketch"] = sk
    h.view().viewTop()
    h.view().fitAll()


def zoom():
    # show about 120 mm across the view: the text frame is 60 x 20 mm
    sk = s["sketch"]
    cam = h.view().getCameraNode()
    try:
        cam.height.setValue(140.0)
    except Exception:
        pass
    cam.position.setValue(30.0, 10.0, 100.0)
    QtWidgets.QApplication.processEvents()
    del sk


def open_text():
    ti.open_text_tool()


def t1_dialog_waits():
    d = ti.dialog()
    h.check("T1 the Text dialog opened", d is not None)
    if d is None:
        return
    h.check(
        "T1 it waits for the frame's first corner", "first corner" in d.hint.text(), d.hint.text()
    )
    h.check("T1 Type is Text", d.type_box.currentData() == "text")
    fonts = [d.font_box.itemText(i) for i in range(d.font_box.count())]
    h.check("T1 the font list comes from the computer", len(fonts) >= 1, fonts[:10])
    h.check("T1 a font is chosen", bool(d.font_box.currentText()), d.font_box.currentText())
    h.shot("t1-dialog")


def t2_first_corner():
    ti.click_sketch(s["sketch"], 5, 5)


def t2_second_corner():
    d = ti.dialog()
    h.check(
        "T2 after one click it waits for the opposite corner",
        d is not None and "opposite corner" in d.hint.text(),
        d and d.hint.text(),
    )
    ti.click_sketch(s["sketch"], 65, 25)


def t2_frame_placed():
    d = ti.dialog()
    h.check("T2 the frame is placed", d is not None and d.frame_placed)
    if d is None:
        return
    corner, angle, width, height = d.frame()
    h.check(
        "T2 frame from corner to corner",
        near(corner[0], 5, 0.05)
        and near(corner[1], 5, 0.05)
        and near(width, 60, 0.05)
        and near(height, 20, 0.05),
        d.frame(),
    )
    h.check("T2 it waits for the text", "Type the text" in d.hint.text(), d.hint.text())


def t3_type():
    ti.type_text("SciForge")
    d = ti.dialog()
    ti.type_field(d.height, "8")


def t3_preview():
    d = ti.dialog()
    QtCore.QThread.msleep(100)
    QtWidgets.QApplication.processEvents()
    h.check(
        "T3 the letters show (preview)",
        d is not None and d.plan is not None,
        d and d.message.text(),
    )
    if d is None or d.plan is None:
        return
    x0, y0, x1, y1 = d.plan.bounds()
    corner, angle, width, height = d.frame()
    h.check(
        "T3 the letters sit in the frame (left, top)",
        x0 >= corner[0] - 0.5 and y1 <= corner[1] + height + 0.5 and x1 > x0 + 10,
        (x0, y0, x1, y1),
    )
    h.check("T3 the height is used (capital about 0.7 of 8 mm)", 4.0 < (y1 - y0) < 9.0, y1 - y0)
    s["layer_points"] = ti.layer().preview_lines[0].point.getNum()
    h.check("T3 the preview is drawn", s["layer_points"] > 50, s["layer_points"])
    h.shot("t3-preview")


def t4_ok():
    ti.ok()


def t4_made():
    sk = s["sketch"]
    found = ti.texts(sk)
    h.check("T4 OK made one text", len(found) == 1, found)
    if not found:
        return
    obj = s["text"] = found[0]
    h.check("T4 it says SciForge", obj.ResolvedText == "SciForge", obj.ResolvedText)
    h.check("T4 height 8", near(obj.TextHeight.Value, 8.0))
    h.check("T4 dialog closed", ti.dialog() is None)
    frame = [i for i in range(len(sk.Geometry)) if sk.getConstruction(i)]
    h.check("T4 its frame: four construction lines", len(frame) == 4, frame)
    h.check(
        "T4 the frame is held as a rectangle (7 constraints)",
        len(sk.Constraints) == 7,
        len(sk.Constraints),
    )
    h.check("T4 the letters are faces", len(obj.Shape.Faces) >= 7, len(obj.Shape.Faces))
    s["area"] = sum(f.Area for f in obj.Shape.Faces)
    from sciforge import timeline_ui

    widget = timeline_ui.widget()
    widget.refresh()
    titles = widget.titles()
    h.check("T4 no timeline step of its own", not any("Text" in t for t in titles), titles)
    doc = App.ActiveDocument
    h.check(
        "T4 one undo step 'Text'", doc.UndoNames and doc.UndoNames[0] == "Text", doc.UndoNames[:3]
    )
    h.shot("t4-made")


def t5_empty_refused():
    ti.open_text_tool()


def t5_place_and_ok():
    ti.click_sketch(s["sketch"], 5, 40)
    ti.click_sketch(s["sketch"], 40, 55)
    ti.ok()


def t5_check():
    d = ti.dialog()
    h.check("T5 an empty text keeps the dialog open", d is not None)
    if d is None:
        return
    h.check(
        "T5 and says why",
        "empty" in d.message.text().lower() or "type some text" in d.message.text().lower(),
        d.message.text(),
    )
    h.check("T5 nothing was made", len(ti.texts(s["sketch"])) == 1)
    ti.cancel()


def t5_cancelled():
    h.check("T5 Cancel closes it", ti.dialog() is None)
    h.check("T5 still one text", len(ti.texts(s["sketch"])) == 1)


def t6_undo():
    h.press("z", QtCore.Qt.ControlModifier)


def t6_undone():
    sk = s["sketch"]
    h.check("T6 Ctrl+Z took the text away", len(ti.texts(sk)) == 0, ti.texts(sk))
    h.check("T6 and its frame", len(sk.Geometry) == 0, len(sk.Geometry))
    h.press("y", QtCore.Qt.ControlModifier)


def t6_redone():
    sk = s["sketch"]
    found = ti.texts(sk)
    h.check("T6 Ctrl+Y brought it back", len(found) == 1)
    h.check("T6 with its frame", len(sk.Geometry) == 4, len(sk.Geometry))
    if found:
        s["text"] = found[0]


def t7_finish():
    h.ribbon("Finish Sketch")


def t7_finished():
    h.check("T7 sketch closed", h.in_sketch() is None)
    obj = s["text"]
    h.check("T7 the text shows with the sketch", obj.ViewObject.Visibility)
    h.check("T7 its shape is up to date", "Touched" not in obj.State, obj.State)
    h.fit()
    h.press("e")


def t7_extrude():
    from sciforge import extrude_ui

    panel = extrude_ui.ExtrudePanel.last
    h.check("T7 Extrude opened", panel is not None and not panel._closed)
    if panel is None:
        return
    h.check("T7 it took the text by itself", panel.profiles == [(s["text"], "")], panel.profiles)
    arrows.give_distance("2")


def t7_ok():
    h.task_button("OK")


def t7_done():
    vol = h.solid_volume()
    h.check(
        "T7 the letters are extruded (area x 2)",
        near(vol, s["area"] * 2.0, 1e-3),
        (vol, s["area"] * 2.0),
    )
    h.check("T7 the text's sketch is hidden after OK", not s["sketch"].ViewObject.Visibility)
    h.check("T7 and the text with it", not s["text"].ViewObject.Visibility)
    h.shot("t7-extruded")


h.run(
    "sketch_text_basic",
    [
        new_design,
        pick_xy,
        sketch_open,
        zoom,
        open_text,
        t1_dialog_waits,
        t2_first_corner,
        t2_second_corner,
        t2_frame_placed,
        t3_type,
        t3_preview,
        t4_ok,
        t4_made,
        t5_empty_refused,
        t5_place_and_ok,
        t5_check,
        t5_cancelled,
        t6_undo,
        t6_undone,
        t6_redone,
        t7_finish,
        t7_finished,
        t7_extrude,
        t7_ok,
        t7_done,
    ],
)
