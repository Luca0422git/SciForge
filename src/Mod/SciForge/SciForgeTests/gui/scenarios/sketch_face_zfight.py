# SPDX-License-Identifier: LGPL-2.1-or-later
"""A finished sketch on a face is drawn cleanly over the face (Luca: "Faces that are
sketched on have z-fighting"), checked on screen pixels.

A block 40 x 30 x 10; Create Sketch on its top face (its edges are projected), a circle,
Finish Sketch. The sketch's areas (FreeCAD's SoSketchFaces) lie exactly on the top face:
they used to fight it for the same pixels (stripes and specks of the face's colour through
the area's) whenever SciForge's front shift was 0 (inside a command) or out of date (after
a zoom); now they are drawn with a polygon offset in front of faces
(sciforge/sketch_area_pick.py), and Extrude's shaded profiles too (profile_pick.py).

At each stage the colours of small patches inside the disc and inside the face around it
must each be one colour (within a few levels): no command; after a wheel zoom; seen at a
slant; inside Fillet (F, a command that cannot use sketch areas); inside Extrude (E, its own
profile shading). (The sandbox's software renderer resolves equal depths the same way every
time, so this guards the drawing; the stripes themselves showed on Luca's graphics card.)
"""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import sketch_input as si

V = App.Vector
s = {}
Z = 10.0
# (not the disc's centre: Extrude's arrow handle sits there)
DISC = [V(20 + dx, 15 + dy, Z) for dx, dy in ((-2.5, -2), (2, -2.5), (2.5, 2), (-2, 2.5))]
AROUND = [V(x, y, Z) for x, y in ((5, 5), (35, 5), (35, 25), (5, 25), (10, 15))]
SPREAD = 14  # levels per channel the renderer's blending may vary across a flat area


def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    doc = App.newDocument("SketchZFight")
    body = doc.addObject("PartDesign::Body", "Body")
    sk = body.newObject("Sketcher::SketchObject", "Sketch")
    sk.AttachmentSupport = [(doc.getObject("XY_Plane"), "")]
    sk.MapMode = "FlatFace"
    h.draw_rectangle(sk, 0, 0, 40, 30)
    pad = body.newObject("PartDesign::Pad", "Extrude")
    pad.Profile = sk
    pad.Length = Z
    doc.recompute()
    sk.Visibility = False
    h.fit()


def create_sketch():
    h.ribbon("Create Sketch")


def click_top():
    h.click(V(33, 24, Z))


def circle_key():
    s["sk"] = h.in_sketch()
    h.check("sketch open on the top face", s["sk"] is not None)
    h.press("c")


def centre():
    si.click(V(20, 15, Z))


def rim():
    si.click(V(26, 15, Z))


def finish():
    h.press(QtCore.Qt.Key_Escape)
    h.ribbon("Finish Sketch")


def spread(points):
    """The largest difference per channel between the screen colours of patches round
    the 3D points (one flat area of the screen)."""
    QtTest.QTest.qWait(300)
    colours = []
    for p in points:
        if h.covered(h.screen_point(p)):
            continue  # under the command's dialog
        colours += [si.rgb(c) for c in si.screen_colours(p, 2).values()]
    if not colours:
        return None
    return max(max(c[i] for c in colours) - min(c[i] for c in colours) for i in range(3))


def clean(stage):
    disc, around = spread(DISC), spread(AROUND)
    h.check(
        "%s: the disc is one colour (no z-fighting)" % stage,
        disc is not None and disc <= SPREAD,
        disc,
    )
    h.check(
        "%s: the face around it is one colour" % stage,
        around is not None and around <= SPREAD,
        around,
    )


def idle():
    h.check("left the sketch", h.in_sketch() is None)
    h.view().viewTop()
    h.fit(iso=False)
    h.move(QtCore.QPoint(5, 5))
    clean("no command")
    h.shot("1-idle")


def zoom():
    widget = h.gl_widget()
    pos = h.screen_point(V(20, 15, Z))
    for _ in range(3):
        event = QtGui.QWheelEvent(
            QtCore.QPointF(pos),
            QtCore.QPointF(widget.mapToGlobal(pos)),
            QtCore.QPoint(0, 0),
            QtCore.QPoint(0, 120),
            QtCore.Qt.NoButton,
            QtCore.Qt.NoModifier,
            QtCore.Qt.NoScrollPhase,
            False,
        )
        QtWidgets.QApplication.sendEvent(widget, event)
        QtWidgets.QApplication.processEvents()


def zoomed():
    clean("after a wheel zoom")
    h.shot("2-zoomed")
    h.fit()  # seen at a slant (iso): depths are closest there


def slanted():
    clean("seen at a slant")
    h.shot("2b-iso")
    h.view().viewTop()
    h.fit(iso=False)


def fillet():
    h.press("f")


def in_fillet():
    from sciforge import taskui

    h.check("Fillet is open", taskui.current() is not None)
    clean("inside Fillet")
    h.shot("3-fillet")
    h.press(QtCore.Qt.Key_Escape)


def extrude():
    h.press("e")


def in_extrude():
    from sciforge import extrude_ui

    h.check("Extrude is open", extrude_ui.ExtrudePanel.last is not None)
    clean("inside Extrude")
    h.shot("4-extrude")
    h.task_button("Cancel")


def done():
    h.check("the block is as it was", abs(h.solid_volume() - 12000.0) < 1e-6, h.solid_volume())


h.run(
    "sketch_face_zfight",
    si.watched(
        [
            new_design,
            create_sketch,
            click_top,
            circle_key,
            centre,
            rim,
            finish,
            idle,
            zoom,
            zoomed,
            slanted,
            fillet,
            in_fillet,
            extrude,
            in_extrude,
            done,
        ]
    ),
)
