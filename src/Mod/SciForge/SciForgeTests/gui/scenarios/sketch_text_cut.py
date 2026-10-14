# SPDX-License-Identifier: LGPL-2.1-or-later
"""Text cut into a part (Luca: "write text on a face, cut it 0.6 mm down"), then saved,
reopened on a computer without the font, and exploded; real input only. Fusion's
behaviour (Autodesk help "Create text in a sketch", "Explode Text"; forum threads on
missing fonts):

C1  Create Sketch on the top face of a 60 x 30 x 10 block, Text "LUCA" 10 mm high.
C2  Finish Sketch, E takes the text; dragging the distance 0.6 down cuts the letters in
    (Cut on its own); the volume taken is the letters' area x 0.6.
C3  Ctrl+S, close, reopen: the same part; the timeline step opens the sketch, a
    double-click on the letters opens the Text dialog with the saved values; "LUCA 2"
    + OK: the cut follows the new text.
C4  the design reopened where its font is missing: a plain message says which font is
    missing and which one is used; the part keeps its letters; the Text dialog says it
    too, and OK rebuilds the text in the font used.
C5  right-click > Explode Text: the letters become sketch curves; the cut keeps the same
    letters (it now uses the sketch's areas); Ctrl+Z gives the text back.
"""

import os
import re
import tempfile
import zipfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import arrow_input as arrows
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import text_input as ti
from SciForgeTests.gui import timeline_input as tl
from SciForgeTests.gui import versions_input as vi

V = App.Vector
BLOCK = 60.0 * 30.0 * 10.0
DEPTH = 0.6
MISSING = "Imaginary Sans SciForge"
s = {}


def near(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


def doc():
    return App.ActiveDocument


def undo_name(name):
    return bool(doc().UndoNames) and doc().UndoNames[0] == name


def letters_area(obj):
    return sum(f.Area for f in obj.Shape.Faces)


def top_view():
    h.view().viewTop()
    cam = h.view().getCameraNode()
    try:
        cam.height.setValue(90.0)
    except Exception:
        pass
    cam.position.setValue(30.0, 15.0, 100.0)
    QtWidgets.QApplication.processEvents()


def new_part():
    """A 60 x 30 x 10 block, saved once (the later saves are Ctrl+S)."""
    Gui.activateWorkbench("SciForgeWorkbench")
    d = App.newDocument("TextCut")
    from sciforge import commands

    body = commands.ensure_body()
    box = body.newObject("PartDesign::AdditiveBox", "Box")
    box.Length, box.Width, box.Height = 60, 30, 10
    d.recompute()
    s["path"] = os.path.join(tempfile.mkdtemp(prefix="sciforge-text-cut-"), "TextCut.FCStd")
    d.saveAs(s["path"])
    h.check("setup: the block", near(h.solid_volume(), BLOCK), h.solid_volume())
    h.fit()
    h.ribbon("Create Sketch")


# -- C1 -----------------------------------------------------------------------------------------
def c1_pick_top():
    h.click(V(30, 15, 10))


def c1_sketch_open():
    sk = h.in_sketch()
    h.check("C1 a sketch opened on the top face", sk is not None)
    s["sketch"] = sk
    if sk is not None:
        z = sk.getGlobalPlacement().multVec(V(0, 0, 0)).z
        h.check("C1 at the top (z 10)", near(z, 10.0), z)
    top_view()


def corner(x, y):
    return lambda: h.to_sketch(s["sketch"], V(x, y, 10))


# -- C2 -----------------------------------------------------------------------------------------
def c2_finish():
    obj = s["text"]
    h.check("C1 the text says LUCA", obj is not None and obj.ResolvedText == "LUCA")
    s["area"] = letters_area(obj)
    h.ribbon("Finish Sketch")


def c2_extrude():
    h.check("C2 sketch closed", h.in_sketch() is None)
    h.fit()
    h.press("e")


def c2_distance():
    from sciforge import extrude_ui

    panel = extrude_ui.ExtrudePanel.last
    h.check("C2 Extrude opened", panel is not None and not panel._closed)
    if panel is None:
        return
    if panel.profiles != [(s["text"], "")]:
        # a sketch on a face may hold the face's outline too: pick the letters
        x, y = ti.middle_of_first_letter(s["text"])
        ti.click_sketch(s["sketch"], x, y)
        QtWidgets.QApplication.processEvents()
    h.check("C2 the text is the profile", panel.profiles == [(s["text"], "")], panel.profiles)
    arrows.give_distance("-%g" % DEPTH)


def c2_cut():
    from sciforge import extrude_ui

    panel = extrude_ui.ExtrudePanel.last
    h.check(
        "C2 going down into the part makes it a Cut",
        panel.operation.currentData() == "cut",
        panel.operation.currentData(),
    )
    h.task_button("OK")


def c2_done():
    expect = BLOCK - s["area"] * DEPTH
    h.check(
        "C2 the letters are cut 0.6 deep",
        near(h.solid_volume(), expect, 1e-5),
        (
            h.solid_volume(),
            expect,
        ),
    )
    b = h.body().Shape.BoundBox
    h.check("C2 nothing sticks out of the block", near(b.ZMax, 10.0), b.ZMax)
    s["v"] = h.solid_volume()
    h.shot("c2-cut")
    h.press(QtCore.Qt.Key_S, QtCore.Qt.ControlModifier)


# -- C3 save, reopen, edit ----------------------------------------------------------------------
def c3_saved():
    vi.accept_save()


def c3_close():
    h.check("C3 saved (nothing unsaved)", not doc().isTouched(), doc().Name)
    App.closeDocument(doc().Name)


def c3_open():
    App.openDocument(s["path"])
    h.fit()


def c3_reopened():
    from sciforge import text

    h.check("C3 reopened: the same part", near(h.solid_volume(), s["v"], 1e-6), h.solid_volume())
    texts = [o for o in doc().Objects if text.is_text(o)]
    h.check("C3 the text is still a text", len(texts) == 1, texts)
    if not texts:
        return
    s["text"] = texts[0]
    s["sketch"] = texts[0].Sketch
    titles = tl.titles()
    s["sketch_step"] = next((t for t in titles if "Sketch" in t), None)
    h.check("C3 the sketch is on the timeline", s["sketch_step"] is not None, titles)
    tl.double_click(s["sketch_step"])


def c3_in_sketch():
    h.check("C3 the sketch opened", h.in_sketch() is s["sketch"])
    top_view()


def c3_double_click():
    h.double_click(ti.at(s["sketch"], *ti.middle_of_first_letter(s["text"])))


def c3_dialog():
    d = ti.dialog()
    h.check("C3 the double-click opened the Text dialog", d is not None)
    if d is None:
        return
    h.check("C3 with the saved text", d.text_box.toPlainText() == "LUCA")
    h.check("C3 and height", d.height.text().split()[0] in ("10", "10.0"), d.height.text())
    ti.type_text("LUCA 2")


def c3_ok():
    QtCore.QThread.msleep(100)
    QtWidgets.QApplication.processEvents()
    ti.ok()


def c3_finish():
    h.check("C3 the text says LUCA 2", s["text"].ResolvedText == "LUCA 2", s["text"].ResolvedText)
    s["area"] = letters_area(s["text"])
    h.ribbon("Finish Sketch")


def c3_followed():
    expect = BLOCK - s["area"] * DEPTH
    h.check(
        "C3 the cut follows the new text",
        near(h.solid_volume(), expect, 1e-5),
        (h.solid_volume(), expect),
    )
    s["v"] = h.solid_volume()
    h.press(QtCore.Qt.Key_S, QtCore.Qt.ControlModifier)


# -- C4 the font is missing ---------------------------------------------------------------------
def c4_saved():
    vi.accept_save()


def c4_close_and_change_font():
    """Another computer: the file names a font this one does not have."""
    s["font"] = s["text"].Font
    App.closeDocument(doc().Name)
    path = s["path"]
    with zipfile.ZipFile(path) as src:
        items = [(info, src.read(info.filename)) for info in src.infolist()]
    changed = 0
    with zipfile.ZipFile(path + ".new", "w", zipfile.ZIP_DEFLATED) as dst:
        for info, data in items:
            if info.filename == "Document.xml":
                xml = data.decode("utf-8")
                xml, changed = re.subn(
                    r'(<Property name="Font" type="App::PropertyString"[^>]*>\s*<String value=")'
                    r'[^"]*(")',
                    r"\g<1>%s\g<2>" % MISSING,
                    xml,
                )
                data = xml.encode("utf-8")
            dst.writestr(info, data)
    os.replace(path + ".new", path)
    h.check("C4 setup: the file now names a missing font", changed == 1, changed)


def c4_open():
    from sciforge import RECENT

    s["recent"] = len(RECENT)
    App.openDocument(s["path"])
    h.fit()
    QtTest.QTest.qWait(500)


def c4_told():
    from sciforge import RECENT, text

    said = [line for line in RECENT[s["recent"] :] if MISSING in line]
    h.check("C4 a message says which font is missing", bool(said), RECENT[-5:])
    h.check(
        "C4 and which font is used instead",
        any(text.default_family() in line for line in said),
        said,
    )
    h.check("C4 it shows next to the mouse", MISSING in si.tooltip(), si.tooltip())
    h.check("C4 the part keeps its letters", near(h.solid_volume(), s["v"], 1e-6))
    texts = [o for o in doc().Objects if text.is_text(o)]
    s["text"] = texts[0] if texts else None
    s["sketch"] = s["text"].Sketch if s["text"] else None
    h.check("C4 the text still names its font", s["text"] and s["text"].Font == MISSING)
    tl.double_click(s["sketch_step"])


def c4_in_sketch():
    h.check("C4 the sketch opened", h.in_sketch() is s["sketch"])
    top_view()


def c4_double_click():
    h.double_click(ti.at(s["sketch"], *ti.middle_of_first_letter(s["text"])))


def c4_dialog():
    from sciforge import text

    d = ti.dialog()
    h.check("C4 the Text dialog opened", d is not None)
    if d is None:
        return
    h.check("C4 the dialog says the font is missing", MISSING in d.hint.text(), d.hint.text())
    h.check("C4 and names the one used", text.default_family() in d.hint.text(), d.hint.text())
    h.shot("c4-missing-font")
    ti.ok()


def c4_rebuilt():
    from sciforge import text

    obj = s["text"]
    h.check("C4 OK keeps the text", ti.dialog() is None and obj.ResolvedText == "LUCA 2")
    h.check("C4 drawn in the font used", obj.FontUsed == text.default_family(), obj.FontUsed)


# -- C5 explode ---------------------------------------------------------------------------------
def c5_right_click():
    s["edges"] = len(s["text"].Shape.Edges)
    h.click(ti.at(s["sketch"], *ti.middle_of_first_letter(s["text"])), button=QtCore.Qt.RightButton)


def c5_menu():
    ti.marking_list_click("Explode Text")


def c5_exploded():
    sk = s["sketch"]
    h.check("C5 no text left", ti.texts(sk) == [], ti.texts(sk))
    curves = [i for i in range(len(sk.Geometry)) if not sk.getConstruction(i)]
    h.check("C5 the letters are sketch curves", len(curves) >= s["edges"], len(curves))
    h.check("C5 one undo step 'Explode Text'", undo_name("Explode Text"), doc().UndoNames[:3])
    h.ribbon("Finish Sketch")


def c5_same_cut():
    from sciforge import extrude

    ext = [o for o in doc().Objects if extrude.is_extrude(o)]
    h.check("C5 the extrude now uses the sketch", ext and ext[0].Profile[0] is s["sketch"], ext)
    h.check(
        "C5 the cut keeps the same letters",
        near(h.solid_volume(), s["v"], 1e-5),
        (h.solid_volume(), s["v"]),
    )
    h.shot("c5-exploded")
    h.press("z", QtCore.Qt.ControlModifier)


def c5_undone():
    from sciforge import text

    texts = [o for o in doc().Objects if text.is_text(o)]
    h.check("C5 Ctrl+Z gave the text back", len(texts) == 1, texts)
    h.check("C5 the part as before", near(h.solid_volume(), s["v"], 1e-5), h.solid_volume())


steps = [new_part, c1_pick_top, c1_sketch_open]
steps += ti.text_steps(s, corner(5, 5), corner(55, 25), "LUCA", 10)
steps += [
    c2_finish,
    c2_extrude,
    c2_distance,
    c2_cut,
    c2_done,
    c3_saved,
    c3_close,
    c3_open,
    c3_reopened,
    c3_in_sketch,
    c3_double_click,
    c3_dialog,
    c3_ok,
    c3_finish,
    c3_followed,
    c4_saved,
    c4_close_and_change_font,
    c4_open,
    c4_told,
    c4_in_sketch,
    c4_double_click,
    c4_dialog,
    c4_rebuilt,
    c5_right_click,
    c5_menu,
    c5_exploded,
    c5_same_cut,
    c5_undone,
]
h.run("sketch_text_cut", steps)
