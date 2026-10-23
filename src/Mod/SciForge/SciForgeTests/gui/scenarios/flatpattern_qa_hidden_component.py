# SPDX-License-Identifier: LGPL-2.1-or-later
"""A flat pattern opened from a hidden component (QA), real input: a sheet metal tube with one
corner ripped away, in its own component "Box", with its Flat Pattern (setup), the component
hidden. A double-click on the browser's Flat Pattern row opens it and the flat is shown (before
QA the view stayed empty: the hidden component hid the flat pattern too). Finish Flat
Pattern: the component is hidden again, as the user left it."""

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import flatpattern_steps as fs
from SciForgeTests.gui import harness as h

WALL = {"type": "plane", "normal": [0, -1, 0], "at": {"axis": "y", "value": "min"}, "count": 1}
CORNER = {
    "type": "cylinder",
    "radius": 2,
    "at": [{"axis": "x", "value": "max"}, {"axis": "y", "value": "max"}],
    "count": 1,
}
s = {}


def setup():
    builder = fs.build("FlatQAHidden", fs.TUBE_STEPS, WALL)
    builder.run({"op": "components_from_bodies", "id": "comp", "bodies": ["e1"], "label": "Box"})
    builder.run({"op": "sf_rip", "id": "rp1", "type": "face", "face": CORNER})
    builder.run({"op": "sf_flat_pattern", "id": "fp1", "face": WALL})
    App.ActiveDocument.recompute()
    s["comp"] = builder.objects["comp"]
    h.fit()


def hide_component():
    fp = fs.flat()
    h.check("a flat pattern in the component", fp is not None)
    comp = s["comp"]
    comp.ViewObject.Visibility = False  # the user switched the component off (eye icon)
    Gui.updateGui()
    h.check("component hidden", not comp.ViewObject.Visibility)


def open_flat():
    fs.double_click_browser("Flat Pattern")


def flat_shown():
    fs.settle()
    fp = fs.flat()
    h.check("FLAT PATTERN tab open", fs.current_tab() == "flat_pattern", fs.current_tab())
    h.check("the flat pattern is shown", fp is not None and fp.ViewObject.Visibility)
    h.check("its component is shown while it is open", s["comp"].ViewObject.Visibility)
    h.check("the folded tube is hidden", not fs.body().ViewObject.Visibility)
    h.shot("1-flat-in-hidden-component")


def finish():
    h.ribbon("Finish Flat Pattern")


def finished():
    fs.settle()
    h.check("back to the design's tabs", fs.current_tab() != "flat_pattern", fs.current_tab())
    h.check("the component is hidden again", not s["comp"].ViewObject.Visibility)
    fp = fs.flat()
    h.check("the flat pattern hidden", fp is not None and not fp.ViewObject.Visibility)
    fs.no_popups("a flat pattern in a hidden component")


h.run(
    "flatpattern_qa_hidden_component",
    [setup, hide_component, open_flat, flat_shown, finish, finished],
)
