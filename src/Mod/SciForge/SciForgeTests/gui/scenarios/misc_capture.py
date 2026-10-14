# SPDX-License-Identifier: LGPL-2.1-or-later
"""Capture Image (the File menu: Menu button > File > Capture Image), only real input
(docs/sciforge/parity/misc.md). A design with a box.

P1 Menu > File > Capture Image: the Image Options window (not FreeCAD's screenshot dialog):
   Image Resolution "Current view size (W x H)", width and height greyed until Custom.
P2 Custom, width 640 with Lock aspect ratio: the height follows the view's proportions; height
   480 typed with the lock off: kept. Transparent background; OK, the file: a 640 x 480 PNG with
   a see-through background.
P3 Full HD preset: 1920 x 1080; OK: a 1920 x 1080 PNG.
P4 Cancel: no file, nothing else.
P5 No design open: the command is greyed (it saves a picture of the 3D view).
"""

import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtGui, QtWidgets

from SciForgeTests.gui import dialog_input as di
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import insert_steps as i
from SciForgeTests.gui import misc_steps as m
from SciForgeTests.gui import widget_input as w

s = {"saved": []}


def options():
    from sciforge import capture_ui

    d = capture_ui.ImageOptions.last
    try:
        return d if d is not None and d.isVisible() else None
    except RuntimeError:
        return None


def _button(d, texts):
    for button in d.findChildren(QtWidgets.QPushButton):
        if button.text().replace("&", "") in texts:
            return button
    return None


def ok_button(d):
    return _button(d, ("OK", "Ok"))


def cancel_button(d):
    return _button(d, ("Cancel",))


def setup():
    from sciforge import capture_ui, commands, extrude, sketch_ui

    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("Capture")
    body = commands.ensure_body()
    planes = sketch_ui.origin_planes(body)
    sk = sketch_ui.create_sketch(body, (planes["XY_Plane"], ""))
    h.draw_rectangle(sk, 0, 0, 40, 30)
    extrude.make(body, sk, {"distance": 10.0})
    App.ActiveDocument.recompute()
    h.fit()
    s["folder"] = tempfile.mkdtemp(prefix="sciforge-capture-")

    def save_dialog(title, start, filters):
        path = os.path.join(s["folder"], "shot%d.png" % (len(s["saved"]) + 1))
        s["saved"].append(path)
        return path

    capture_ui.SAVE_DIALOG = save_dialog


# -- P1 ----------------------------------------------------------------------------------------
def p1_open():
    s["menu"] = m.app_menu_item(["File", "Capture Image"])


p1_open.wait_ms = 1500


def p1_check():
    d = options()
    h.check("P1 the Image Options window", d is not None, h.popups())
    if d is None:
        return
    h.check("P1 the menu entry was clicked", s["menu"]["clicked"])
    h.check("P1 not FreeCAD's screenshot dialog", "Save picture" not in h.popups(), h.popups())
    h.check(
        "P1 the view's size first",
        d.preset.currentText().startswith("Current view size"),
        d.preset.currentText(),
    )
    h.check("P1 width / height greyed", not d.width.isEnabled() and not d.height.isEnabled())
    h.shot("1-options")


# -- P2 ----------------------------------------------------------------------------------------
def p2_custom():
    d = options()
    if d is None:
        return
    di.choose(d.preset, "Custom")
    ratio = d.width.value() / float(d.height.value())
    i.set_spin(d.width, 640)
    h.check(
        "P2 the height follows (lock)",
        abs(d.height.value() - round(640 / ratio)) <= 1,
        (d.height.value(), ratio),
    )
    m.set_check(d.lock, False)
    i.set_spin(d.height, 480)
    h.check("P2 lock off: 640 x 480", (d.width.value(), d.height.value()) == (640, 480))
    m.set_check(d.transparent, True)
    w.click(ok_button(d))


p2_custom.wait_ms = 2500


def p2_check():
    path = s["saved"][-1] if s["saved"] else ""
    h.check("P2 the window closed", options() is None)
    h.check("P2 a file", os.path.isfile(path), path)
    image = QtGui.QImage(path)
    h.check(
        "P2 640 x 480",
        (image.width(), image.height()) == (640, 480),
        (image.width(), image.height()),
    )
    corner = QtGui.QColor(image.pixel(2, 2)) if not image.isNull() else None
    h.check(
        "P2 a see-through background",
        image.hasAlphaChannel() and corner is not None and QtGui.qAlpha(image.pixel(2, 2)) < 255,
        corner and corner.name(),
    )
    h.check("P2 a note says it was saved", "Saved shot1.png" in m.told(), m.told())


# -- P3 ----------------------------------------------------------------------------------------
def p3_hd():
    m.app_menu_item(["File", "Capture Image"])


p3_hd.wait_ms = 1500


def p3_choose():
    d = options()
    if not h.check("P3 the window again", d is not None):
        return
    di.choose(d.preset, "1920 x 1080 (Full HD)")
    h.check("P3 1920 x 1080", (d.width.value(), d.height.value()) == (1920, 1080))
    w.click(ok_button(d))


p3_choose.wait_ms = 3000


def p3_check():
    image = QtGui.QImage(s["saved"][-1])
    h.check(
        "P3 a 1920 x 1080 picture",
        (image.width(), image.height()) == (1920, 1080),
        (image.width(), image.height()),
    )


# -- P4 ----------------------------------------------------------------------------------------
def p4_cancel():
    s["count"] = len(s["saved"])
    m.app_menu_item(["File", "Capture Image"])


p4_cancel.wait_ms = 1500


def p4_check():
    d = options()
    if h.check("P4 the window", d is not None):
        w.click(cancel_button(d))
    m.process(200)
    h.check("P4 Cancel: no file asked for", len(s["saved"]) == s["count"])
    h.check("P4 closed", options() is None)


# -- P5 ----------------------------------------------------------------------------------------
def p5_no_design():
    from sciforge import capture_ui

    m.close_all()
    h.check("P5 greyed without a design", not capture_ui.CaptureImageCommand().IsActive())


def cleanup():
    from sciforge import capture_ui

    capture_ui.SAVE_DIALOG = None
    m.close_all()
    h.new_errors()


h.run(
    "misc_capture",
    [
        setup,
        p1_open,
        p1_check,
        p2_custom,
        p2_check,
        p3_hd,
        p3_choose,
        p3_check,
        p4_cancel,
        p4_check,
        p5_no_design,
        cleanup,
    ],
)
