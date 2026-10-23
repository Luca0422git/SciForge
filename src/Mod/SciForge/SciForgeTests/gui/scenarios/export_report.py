# SPDX-License-Identifier: LGPL-2.1-or-later
"""What an export leaves out (sciforge/export_report*.py): the short message over the 3D view
after File > Export, only real input (the system's folder dialog and folder opener are the
only stand-ins, as in export_formats).

Design: box1 0..40 x 0..30 x 10 and box2 50..80 x 0..30 x 10 (a New Body), each drawn and
extruded; box1 is given an orange look and the design a parameter (setup).

A  UTILITIES > Export, STL (Binary), name "parts", Export: the message "Exported parts.stl /
   Not kept in this file:" shows in the bottom right corner of the 3D view, not as a pop-up,
   with the timeline (4 steps), 2 sketches, 1 parameter, "2 bodies become one mesh" and the
   colours of 1 body; the same line is in the Report view.
B  A click on its x: the message goes away.
C  Export, STEP, Export: the message lists the timeline, the sketches, the parameter and
   the name of 1 body (Body comes back as Body1), but no colours: with the window open the
   STEP file keeps them (it holds box1's orange, read in the file itself).
D  Export, 3MF, Selected bodies with only box2 ticked: names and unit are kept; the message
   lists box2's 1 step (its sketch was drawn in box1's body, active then) and no colour (box2
   has no look).
"""

import os
import shutil

import FreeCAD as App
from PySide import QtWidgets

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import insert_steps as i
from SciForgeTests.gui import widget_input as w

OUT = os.path.join(i.OUT, "export_report")
ORANGE = (0.9, 0.4, 0.1)  # not one of STEP's named colours: written as COLOUR_RGB
state = {}


def dialog():
    from sciforge import export_ui

    d = export_ui.ExportDialog.last
    return d if d is not None and d.isVisible() else None


def notice():
    from sciforge import export_report_ui

    return export_report_ui.current()


def notice_text():
    n = notice()
    if n is None:
        return ""
    return "%s\n%s\n%s" % (n.title.text(), n.lead.text(), n.body.text())


def step_rgb(path):
    """The COLOUR_RGB values of a STEP file (an entity can run over several lines)."""
    import re

    text = open(path, encoding="utf-8", errors="replace").read().replace("\n", "")
    found = []
    for match in re.finditer(r"COLOUR_RGB\('[^']*',([^,]+),([^,]+),([^)]+)\)", text):
        try:
            found.append(tuple(float(v) for v in match.groups()))
        except ValueError:
            pass
    return found


def setup():
    from sciforge import appearance, bodies, export_report_ui, parameters

    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT)
    doc = App.ActiveDocument
    doc.saveAs(os.path.join(OUT, "parts_design.FCStd"))
    i.record_exports()
    first = bodies.list_bodies(doc)[0]
    appearance.set_body(first, appearance.custom(ORANGE))
    appearance.apply(first)
    parameters.add_user(doc, "wall", "mm", "2")
    doc.recompute()
    export_report_ui.clear_recent()
    state["first"] = first.Label


def open_export():
    h.fit()
    i.ribbon_tab("UTILITIES")
    h.ribbon("Export")


def set_location_and_name(name):
    d = dialog()
    if d is None:
        return
    b.type_into(d.folder, OUT)
    b.type_into(d.name, name)


def press_export():
    d = dialog()
    if d is not None:
        b.click_widget(d.export_button)


press_export.wait_ms = 2000


# -- A ----------------------------------------------------------------------------------------
def a_stl():
    d = dialog()
    if not h.check("Export dialog open", d is not None):
        return
    b.choose(d.type, "STL (Binary)")
    set_location_and_name("parts")


def a_check():
    h.check("parts.stl written", os.path.isfile(os.path.join(OUT, "parts.stl")), os.listdir(OUT))
    n = notice()
    text = notice_text()
    h.check("A the message shows", n is not None, text)
    s.no_popups("the STL export (the message is no pop-up)")
    for part in (
        "Exported parts.stl",
        "Not kept in this file:",
        "the timeline (4 steps)",
        "2 sketches",
        "1 parameter",
        "2 bodies become one mesh",
        "the colours of 1 body",
    ):
        h.check("A message says %r" % part, part in text, text)
    h.check("A no hidden body to report", "hidden" not in text, text)
    if n is not None:
        window = n.parentWidget()
        area = window.centralWidget()
        corner = area.mapTo(window, area.rect().bottomRight())
        geo = n.geometry()
        h.check(
            "A in the bottom right corner of the 3D view",
            geo.right() <= corner.x()
            and geo.bottom() <= corner.y()
            and geo.right() > corner.x() - 60
            and geo.bottom() > corner.y() - 60,
            (geo, corner),
        )
        h.check("A it did not take the keyboard", QtWidgets.QApplication.focusWidget() is not n)
    h.check(
        "A the Report view has the line",
        "[SciForge] Not in parts.stl: the timeline (4 steps)" in h.report_text(),
        h.report_text()[-800:],
    )
    h.shot("stl-message")


# -- B ----------------------------------------------------------------------------------------
def b_close():
    n = notice()
    if h.check("B message still up", n is not None):
        w.click(n.close_button)


def b_check():
    h.check("B the x closed the message", notice() is None)


# -- C ----------------------------------------------------------------------------------------
def c_step():
    d = dialog()
    if not h.check("Export dialog open", d is not None):
        return
    b.choose(d.type, "STEP")
    set_location_and_name("parts")


def c_check():
    path = os.path.join(OUT, "parts.step")
    h.check("parts.step written", os.path.isfile(path), os.listdir(OUT))
    text = notice_text()
    h.check("C the message shows", notice() is not None, text)
    for part in ("Exported parts.step", "the timeline (4 steps)", "2 sketches", "1 parameter"):
        h.check("C message says %r" % part, part in text, text)
    h.check("C the name of 1 body (Body comes back as Body1)", "the names of 1 body" in text, text)
    h.check("C no colours lost: STEP keeps them with the window open", "colours" not in text, text)
    h.check("C no mesh merge for STEP", "one mesh" not in text, text)
    if os.path.isfile(path):
        found = step_rgb(path)
        h.check(
            "C the STEP file holds box1's orange",
            any(all(abs(a - b) < 0.01 for a, b in zip(rgb, ORANGE)) for rgb in found),
            found,
        )
    s.no_popups("the STEP export")


# -- D ----------------------------------------------------------------------------------------
def d_3mf_second():
    d = dialog()
    if not h.check("Export dialog open", d is not None):
        return
    b.choose(d.type, "3MF")
    b.choose(d.what, "Selected bodies")
    i.check_list_item(d.bodies, 0, False)
    set_location_and_name("second")


def d_check():
    h.check("second.3mf written", os.path.isfile(os.path.join(OUT, "second.3mf")), os.listdir(OUT))
    text = notice_text()
    h.check("D the message shows", notice() is not None, text)
    # box2's sketch was drawn in the first body (the one active then): box2 holds its extrude
    h.check("D box2's history: 1 step", "the timeline (1 step)" in text, text)
    h.check("D no sketch in box2", "sketch" not in text, text)
    h.check("D no colour lost (box2 has no look)", "colours" not in text, text)
    h.check("D 3MF keeps names and unit", "one mesh" not in text and "unit" not in text, text)
    h.check("D no joints line for chosen bodies", "joint" not in text, text)
    h.shot("end")


h.run(
    "export_report",
    [i.new_design("ExportReport")]
    + s.box_steps("box1", (0, 0, 40, 30), 10, i.XY_CLICK)
    + s.box_steps("box2", (50, 0, 80, 30), 10, i.XY_CLICK, new_body=True)
    + [
        setup,
        open_export,
        a_stl,
        press_export,
        a_check,
        b_close,
        b_check,
        open_export,
        c_step,
        press_export,
        c_check,
        open_export,
        d_3mf_second,
        press_export,
        d_check,
    ],
)
