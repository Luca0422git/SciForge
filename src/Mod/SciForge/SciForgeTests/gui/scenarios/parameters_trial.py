# SPDX-License-Identifier: LGPL-2.1-or-later
"""Change Parameters checked on a trial (parameters.change_checked), with real input in the
dialog and in the sketch.

The part: a 40 x 20 rectangle on XY whose width is the user parameter width = 40, extruded
10 (8000 mm3). (Built by script: the dialog is what is tested.)

A  MODIFY > Change Parameters; double-click width's Expression, type 0, Enter: refused. The
   dialog says "Not changed: with width = 0, Sketch 1 would break: ..." and names the
   dimension; width is still 40 and the part still 8000 mm3.
B  Type 50: accepted, the part follows (10000 mm3), no message.
C  The extrude's Distance (model parameters) typed 0: refused, the message names the
   extrude; the distance stays 10.
B2 Type width2 (a typo: no such name): refused, the formula cannot be computed; width stays
   50 with no formula.
B3 Type -5: refused, and the message says the dimension would be -5 mm (FreeCAD holds a length
   at 0: the message shows what was typed).
C2 The sketch's height (model parameters) typed -3: refused like 0 (the profile would flip),
   "would be -3 mm"; the height stays 20.
D  OK: the dialog closes with width = 50.
E  Edit the sketch from the timeline, double-click the 20 mm dimension, type =width - 50 mm
   (a formula giving 0): the box stays open and says the value must be more than 0 (the
   formula gives 0 mm); the height stays 20.
"""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import widget_input as w

V = App.Vector
s = {}


def doc():
    return App.ActiveDocument


def dialog():
    from sciforge import parameters_ui

    d = parameters_ui.ParametersDialog.last
    return d if d is not None and d.isVisible() else None


def width():
    from sciforge import parameters

    return parameters.container(doc()).width.Value


def volume():
    return h.solid_volume()


def broken():
    return [o.Label for o in doc().Objects if "Invalid" in o.State or "Error" in o.State]


def edit_cell(view, rect, text):
    """Double-click a table/tree cell, replace its text by typing, press Enter."""
    view.window().activateWindow()
    view.window().raise_()
    QtWidgets.QApplication.processEvents()
    w.double_click(view.viewport(), rect.center())
    editors = [e for e in view.findChildren(QtWidgets.QLineEdit) if e.isVisible()]
    h.check("an editor opened in the cell", bool(editors), (rect, view.editTriggers()))
    if not editors:
        return
    editor = editors[0]
    QtTest.QTest.keyClick(editor, QtCore.Qt.Key_A, QtCore.Qt.ControlModifier)
    QtTest.QTest.keyClicks(editor, text)
    QtTest.QTest.keyClick(editor, QtCore.Qt.Key_Return)
    QtWidgets.QApplication.processEvents()


def user_row(name):
    d = dialog()
    for r in range(d.user.rowCount()):
        if d.user.item(r, 0).text() == name:
            return r
    return -1


def drain(where):
    """The trial recompute reports the failure it found in FreeCAD's Report view: expected
    here (the user sees the dialog's message), so taken out of the error check. (The Report
    view gets its lines through Qt's event queue: they are let in first.)"""
    QtTest.QTest.qWait(500)
    seen = h.new_errors()
    h.check("%s: FreeCAD reported the trial's failure (expected)" % where, True, seen)


# == the part ==================================================================================
def setup():
    import Part
    import Sketcher

    from sciforge import parameters

    Gui.activateWorkbench("SciForgeWorkbench")
    d = App.newDocument("ParametersTrial")
    body = d.addObject("PartDesign::Body", "Body")
    sk = body.newObject("Sketcher::SketchObject", "Sketch")
    sk.AttachmentSupport = [(body.Origin.OriginFeatures[3], "")]  # XY plane
    sk.MapMode = "FlatFace"
    h.draw_rectangle(sk, 0, 0, 40, 20)
    sk.addConstraint(Sketcher.Constraint("Coincident", 0, 1, -1, 1))
    s["w"] = sk.addConstraint(Sketcher.Constraint("DistanceX", 0, 1, 0, 2, 40))
    s["h"] = sk.addConstraint(Sketcher.Constraint("DistanceY", 1, 1, 1, 2, 20))
    parameters.add_user(d, "width", "mm", "40")
    sk.setExpression(".Constraints[%d]" % s["w"], "Parameters.width")
    pad = body.newObject("PartDesign::Pad", "Pad")
    pad.Profile = sk
    pad.Length = 10
    sk.Visibility = False
    d.recompute()
    s["sk"], s["pad"] = sk, pad
    del Part
    h.fit()
    h.check("the part is 40 x 20 x 10", abs(volume() - 8000) < 1e-6, volume())


# == A: refused =================================================================================
def a_open():
    si.menu_item("MODIFY", "Change Parameters")


def a_type_0():
    h.check("A: Change Parameters opened", dialog() is not None)
    d = dialog()
    row = user_row("width")
    h.check("A: width is listed", row >= 0)
    edit_cell(d.user, d.user.visualItemRect(d.user.item(row, 2)), "0")
    drain("A")


def a_check():
    d = dialog()
    text = d.message.text() if d is not None else ""
    h.check("A: refused, and says so", "Not changed: with width = 0" in text, text)
    h.check("A: names the sketch", "Sketch 1 would break" in text, text)
    h.check(
        "A: and the dimension, by the name the dialog shows",
        "dimension d%d of Line 1" % (s["w"] + 1) in text,
        text,
    )
    h.check("A: width is still 40", abs(width() - 40) < 1e-9, width())
    h.check("A: the part is unchanged", abs(volume() - 8000) < 1e-6, volume())
    h.check("A: nothing is left broken", not broken(), broken())
    QtWidgets.QApplication.processEvents()
    row = user_row("width")
    shown = d.user.item(row, 2).text() if row >= 0 else ""
    h.check("A: the table shows 40 again", shown.startswith("40"), shown)
    h.shot("A-refused")


a_check.wait_ms = 1200


# == B: accepted ================================================================================
def b_type_50():
    d = dialog()
    row = user_row("width")
    edit_cell(d.user, d.user.visualItemRect(d.user.item(row, 2)), "50")


def b_check():
    d = dialog()
    h.check("B: no message", d is not None and d.message.text() == "", d and d.message.text())
    h.check("B: width = 50", abs(width() - 50) < 1e-9, width())
    h.check("B: the part follows (50 x 20 x 10)", abs(volume() - 10000) < 1e-6, volume())


b_check.wait_ms = 1200


# == B2, B3: a typo and a negative length ===========================================================
def b2_type():
    d = dialog()
    row = user_row("width")
    edit_cell(d.user, d.user.visualItemRect(d.user.item(row, 2)), "width2")
    drain("B2")


def b2_check():
    from sciforge import parameters

    d = dialog()
    text = d.message.text() if d is not None else ""
    h.check("B2: refused", "Not changed: with width = width2" in text, text)
    h.check("B2: says the formula cannot be computed", "cannot be computed" in text, text)
    h.check("B2: width stays 50", abs(width() - 50) < 1e-9, width())
    container = parameters.container(doc())
    h.check("B2: no formula kept", not dict(container.ExpressionEngine), container.ExpressionEngine)
    h.check("B2: nothing is left broken", not broken(), broken())


b2_check.wait_ms = 1200


def b3_type():
    d = dialog()
    row = user_row("width")
    edit_cell(d.user, d.user.visualItemRect(d.user.item(row, 2)), "-5")
    drain("B3")


def b3_check():
    d = dialog()
    text = d.message.text() if d is not None else ""
    h.check("B3: refused", "Not changed: with width = -5" in text, text)
    h.check("B3: shows the value typed", "would be -5 mm" in text, text)
    h.check("B3: width stays 50", abs(width() - 50) < 1e-9, width())
    h.check("B3: nothing is left broken", not broken(), broken())


b3_check.wait_ms = 1200


# == C: a model parameter ==========================================================================
def _model_item(owner, label):
    d = dialog()
    for i in range(d.model.topLevelItemCount()):
        group = d.model.topLevelItem(i)
        if group.text(0) != owner:
            continue
        group.setExpanded(True)
        for j in range(group.childCount()):
            if group.child(j).text(1) == label:
                return group.child(j)
    return None


def c_type_0():
    d = dialog()
    item = _model_item(s["pad"].Label, "Distance")
    h.check("C: the extrude's Distance is listed", item is not None)
    if item is None:
        return
    d.model.scrollToItem(item)
    rect = d.model.visualItemRect(item)
    x = d.model.header().sectionPosition(2) + 10
    edit_cell(d.model, QtCore.QRect(x, rect.top(), 20, rect.height()), "0")
    drain("C")


def c_check():
    d = dialog()
    text = d.message.text() if d is not None else ""
    h.check("C: refused", "Not changed: with Distance = 0" in text, text)
    h.check("C: names the extrude", "Extrude 1 would break" in text, text)
    h.check("C: the distance stays 10", abs(s["pad"].Length.Value - 10) < 1e-9, s["pad"].Length)
    h.check("C: the part is unchanged", abs(volume() - 10000) < 1e-6, volume())
    h.check("C: nothing is left broken", not broken(), broken())
    h.shot("C-refused")


c_check.wait_ms = 1200


def c2_type():
    d = dialog()
    label = "d%d" % (s["h"] + 1)
    item = _model_item(s["sk"].Label, label)
    h.check("C2: the height is listed", item is not None)
    if item is None:
        return
    d.model.scrollToItem(item)
    rect = d.model.visualItemRect(item)
    x = d.model.header().sectionPosition(2) + 10
    edit_cell(d.model, QtCore.QRect(x, rect.top(), 20, rect.height()), "-3")
    drain("C2")


def c2_check():
    d = dialog()
    text = d.message.text() if d is not None else ""
    h.check("C2: refused", "Not changed: with d%d = -3" % (s["h"] + 1) in text, text)
    h.check("C2: like 0", "would be -3 mm" in text and "more than 0" in text, text)
    h.check("C2: the height stays 20", abs(s["sk"].getDatum(s["h"]).Value - 20) < 1e-9)
    h.check("C2: the part is unchanged", abs(volume() - 10000) < 1e-6, volume())
    h.check("C2: nothing is left broken", not broken(), broken())


c2_check.wait_ms = 1200


# == D: OK =========================================================================================
def d_ok():
    dialog().accept()


def d_check():
    h.check("D: the dialog closed", dialog() is None)
    h.check("D: width = 50 kept", abs(width() - 50) < 1e-9, width())


# == E: a formula typed in the sketch ===============================================================
def e_edit():
    si.timeline_double_click("Sketch 1")


def e_open_box():
    sk = h.in_sketch()
    h.check("E: the sketch is open", sk is not None)
    h.double_click(si.dimension_label(s["sk"], s["h"]))


def e_type():
    from sciforge import sketch_mode

    session = sketch_mode.current()
    h.check("E: the dimension box is open", session is not None and session.editor is not None)
    si.type_text("=width - 50 mm")
    drain("E")


def e_check():
    from sciforge import sketch_mode

    session = sketch_mode.current()
    ed = session.editor if session is not None else None
    text = ed.reason() if ed is not None else ""
    h.check("E: the box stays open", ed is not None)
    h.check("E: and says why", "must be more than 0" in text and "gives 0 mm" in text, text)
    h.check("E: the height stays 20", abs(s["sk"].getDatum(s["h"]).Value - 20) < 1e-9)
    h.check(
        "E: no formula left on the height",
        ".Constraints[%d]" % s["h"] not in dict(s["sk"].ExpressionEngine),
        s["sk"].ExpressionEngine,
    )
    si.key(QtCore.Qt.Key_Escape)


def e_finish():
    h.ribbon("Finish Sketch")


def e_done():
    h.check("E: the part is fine", not broken() and abs(volume() - 10000) < 1e-6, volume())


e_done.wait_ms = 1200

h.run(
    "parameters_trial",
    [
        setup,
        a_open,
        a_type_0,
        a_check,
        b_type_50,
        b_check,
        b2_type,
        b2_check,
        b3_type,
        b3_check,
        c_type_0,
        c_check,
        c2_type,
        c2_check,
        d_ok,
        d_check,
        e_edit,
        e_open_box,
        e_type,
        e_check,
        e_finish,
        e_done,
    ],
)
