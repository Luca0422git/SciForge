# SPDX-License-Identifier: LGPL-2.1-or-later
"""The sketch Text's frame resized by dragging a corner (parity/text-emboss.md T17 and
"Sketch, part 2"), real input only. Fusion (Autodesk help "Create text in a sketch"; the
frame is sketch geometry, Forum): dragging a frame corner resizes the frame, the opposite
corner stays, the letters keep their height and are laid out again inside the frame.

  A  a text "SF" in the frame (0, 0)-(40, 15); its top-right corner dragged to (60, 25): the
     frame is 60 x 25 from the same bottom-left corner, the letters keep their height and
     sit inside; one undo step (Ctrl+Z puts the frame back, Ctrl+Y again)
  B  the bottom-left corner dragged to (-10, -5): the top-right corner stays
  C  a dimension on the frame's bottom side holds the width: a drag cannot change it, the
     reason by the pointer; Ctrl+Z
  D  Finish Sketch, save, close, reopen: the frame keeps its size and the letters
"""

import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import text_input as ti

V = App.Vector
s = {}
TOL = 0.6  # mm: a drag ends within a pixel or two of the aimed point (the camera below)


def near(a, b, tol):
    return abs(a - b) <= tol


def doc():
    return App.ActiveDocument


def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("TextFrame")
    h.fit()
    h.ribbon("Create Sketch")


def pick_xy():
    pl.click_square("XY_Plane")  # where the square shows (was 12, -8, 0)


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
    cam.position.setValue(20.0, 10.0, 100.0)
    QtWidgets.QApplication.processEvents()


def letters_height(obj):
    shape = obj.Shape.copy()
    shape.Placement = App.Placement()
    return shape.BoundBox.YLength


def drag(a, b):
    sk = s["sketch"]
    h.drag(ti.screen(sk, *a), ti.screen(sk, *b), steps=16)


def frame():
    return ti.frame_of(s["text"])


# -- A ----------------------------------------------------------------------------------------
def a_ready():
    obj = s["text"]
    s["letters"] = letters_height(obj)
    s["height"] = obj.TextHeight.Value
    s["f0"] = frame()
    (cx, cy), angle, w, hh = s["f0"]
    # (the frame's corners are where the clicks landed: within a pixel of the aim)
    h.check(
        "A the text's frame about (0, 0) 40 x 15",
        near(cx, 0, TOL) and near(cy, 0, TOL) and near(w, 40, TOL) and near(hh, 15, TOL),
        frame(),
    )
    drag((cx + w, cy + hh), (60, 25))


def a_check():
    obj = s["text"]
    (cx, cy), angle, w, hh = frame()
    (x0, y0), _a0, _w0, _h0 = s["f0"]
    h.check(
        "A the bottom-left corner stays",
        near(cx, x0, 1e-6) and near(cy, y0, 1e-6),
        (frame(), s["f0"]),
    )
    h.check(
        "A the top-right corner follows the pointer to about (60, 25)",
        near(cx + w, 60, TOL) and near(cy + hh, 25, TOL),
        frame(),
    )
    h.check("A the frame stays upright", near(angle, 0, 1e-6), angle)
    h.check(
        "A the letters keep their height",
        near(obj.TextHeight.Value, s["height"], 1e-9)
        and near(letters_height(obj), s["letters"], 1e-6),
        (obj.TextHeight.Value, letters_height(obj), s["letters"]),
    )
    h.check("A the letters sit inside the frame", ti.letters_in_frame(obj), ti.letters_box(obj))
    h.check(
        "A one undo step 'Resize Text Frame'",
        doc().UndoNames and doc().UndoNames[0] == "Resize Text Frame",
        doc().UndoNames[:3],
    )
    h.check(
        "A the text keeps the frame's size",
        near(obj.FrameWidth.Value, w, 1e-6),
        (obj.FrameWidth.Value, w),
    )
    s["a_frame"] = frame()
    h.shot("A-resized")
    h.press("z", QtCore.Qt.ControlModifier)


def a_undone():
    (cx, cy), _a, w, hh = frame()
    want = s["f0"]
    h.check(
        "A Ctrl+Z: the frame as it was",
        near(w, want[2], 1e-6) and near(hh, want[3], 1e-6),
        (frame(), want),
    )
    h.check(
        "A ...and the letters inside it", ti.letters_in_frame(s["text"]), ti.letters_box(s["text"])
    )
    h.press("y", QtCore.Qt.ControlModifier)


def a_redone():
    (cx, cy), _a, w, hh = frame()
    want = s["a_frame"]
    h.check(
        "A Ctrl+Y: resized again",
        near(w, want[2], 1e-6) and near(hh, want[3], 1e-6),
        (frame(), want),
    )


# -- B ----------------------------------------------------------------------------------------
def b_drag():
    (cx, cy), _a, w, hh = frame()
    s["top_right"] = (cx + w, cy + hh)
    drag((0, 0), (-10, -5))


def b_check():
    (cx, cy), _a, w, hh = frame()
    tr = (cx + w, cy + hh)
    h.check(
        "B the top-right corner stays",
        near(tr[0], s["top_right"][0], 1e-6) and near(tr[1], s["top_right"][1], 1e-6),
        (tr, s["top_right"]),
    )
    h.check(
        "B the bottom-left corner went to about (-10, -5)",
        near(cx, -10, TOL) and near(cy, -5, TOL),
        frame(),
    )
    h.check("B the letters sit inside", ti.letters_in_frame(s["text"]), ti.letters_box(s["text"]))


# -- C ----------------------------------------------------------------------------------------
def c_dimension():
    import Sketcher

    from sciforge import text

    sk = s["sketch"]
    obj = s["text"]
    bottom = text.geo_index(sk, obj.FrameIds[0])
    (cx, cy), _a, w, hh = frame()
    s["c_width"] = w
    doc().openTransaction("Frame width")
    sk.addConstraint(Sketcher.Constraint("DistanceX", bottom, 1, bottom, 2, w))
    doc().commitTransaction()
    sk.solve()
    (cx, cy), _a, w, hh = frame()
    drag((cx + w, cy + hh), (cx + w + 15, cy + hh + 5))


def c_check():
    from sciforge import commands

    (cx, cy), _a, w, hh = frame()
    h.check("C the dimension holds the width", near(w, s["c_width"], 1e-6), (w, s["c_width"]))
    told = commands._TOLD["msg"] or ""
    h.check("C the reason by the pointer", "dimension" in told, told)


# -- D ----------------------------------------------------------------------------------------
def d_finish():
    h.ribbon("Finish Sketch")


def d_save():
    h.check("D the sketch closes", h.in_sketch() is None)
    s["frame"] = frame()
    s["name"] = s["text"].Name
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-text-frame-"), "frame.FCStd")
    s["path"] = path
    doc().saveAs(path)
    App.closeDocument(doc().Name)


def d_reopen():
    App.openDocument(s["path"])
    h.fit()


def d_check():
    obj = doc().getObject(s["name"])
    h.check("D reopened: the text is there", obj is not None)
    if obj is None:
        return
    s["text"] = obj
    (cx, cy), _a, w, hh = frame()
    want = s["frame"]
    h.check(
        "D reopened: the frame kept its size",
        near(w, want[2], 1e-6) and near(hh, want[3], 1e-6),
        (frame(), want),
    )
    h.check("D reopened: the letters inside it", ti.letters_in_frame(obj), ti.letters_box(obj))


h.run(
    "sketch2_text_frame",
    si.watched(
        [new_design, pick_xy, sketch_open]
        + ti.text_steps(s, (0, 0), (40, 15), "SF")
        + [
            a_ready,
            a_check,
            a_undone,
            a_redone,
            b_drag,
            b_check,
            c_dimension,
            c_check,
            d_finish,
            d_save,
            d_reopen,
            d_check,
        ]
    ),
)
