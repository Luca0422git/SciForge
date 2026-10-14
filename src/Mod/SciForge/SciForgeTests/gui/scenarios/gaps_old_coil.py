# SPDX-License-Identifier: LGPL-2.1-or-later
"""A coil saved by SciForge before the 2026-10-11 fixes is rebuilt when the file is opened.

Setup (made in code, what is tested is the opening): a coil narrowing 10 degrees as it rises
(d20, 4 turns, 20 high, a d2 circle inside, centre (3, -2) on XY), then made to look as saved
before the fixes: FreeCAD's helix with the negative angle as is, which is the mirror image
(it goes down through the plane and widens: 849.83 instead of 571.39), the section without
the property the fixes added. Saved, closed.
Path O1, the file opened again: right after opening the coil is rebuilt with today's code
         (571.39, it rises from the plane), the Report view says so in one line, the design
         shows as changed, nothing is red.
Path O2, Ctrl+S (Enter in the version box), closed, opened again: no rebuild this time (no
         new line), still 571.39.

Hand-derived (sf_coil_taper_narrow): V = pi x 2 pi x 4 x (9 - 10 tan 10)."""

import math
import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import timeline_input as t
from SciForgeTests.gui import versions_input as vi

RIGHT = math.pi * 2 * math.pi * 4 * (9 - 10 * math.tan(math.radians(10)))
MIRROR = 849.8323525930454  # FreeCAD 1.1.4's helix with the negative angle (old SciForge)
st = {}


def doc():
    return App.ActiveDocument


def coil_obj():
    from sciforge import coil

    found = [o for o in doc().Objects if coil.is_coil(o)]
    return found[0] if found else None


def lines():
    return [line for line in h.report_text().splitlines() if "older SciForge" in line]


def close(a, b, tol=1e-4):
    return a is not None and abs(a - b) <= tol * max(1.0, abs(b))


# -- setup: an old file ---------------------------------------------------------------------
def setup():
    from sciforge import coil, primitives

    Gui.activateWorkbench("SciForgeWorkbench")
    d = App.newDocument("OldCoil")
    body = d.addObject("PartDesign::Body", "Body")
    xy = [f for f in body.Origin.OriginFeatures if f.Role == "XY_Plane"][0]
    options = {
        "diameter": 20,
        "type": "rev_height",
        "revolutions": 4,
        "height": 20,
        "section": "circular",
        "section_position": "inside",
        "section_size": 2,
        "angle": -10,
        "x": 3,
        "y": -2,
    }
    feature = coil.make((xy, ""), options)
    d.recompute()
    h.check("today's coil: 571.39", close(h.solid_volume(), RIGHT), h.solid_volume())
    # As saved before the fixes (the same as the golden builder's "age" step).
    section = d.getObject(primitives.load_meta(feature, coil.META)["helpers"][-1])
    section.Taper = 0.0
    feature.Angle = -10.0
    feature.Reversed = False
    section.touch()
    d.recompute()
    section.removeProperty("Taper")
    h.check("the old mirror image: 849.83", close(h.solid_volume(), MIRROR), h.solid_volume())
    st["folder"] = tempfile.mkdtemp(prefix="sciforge-old-coil-")
    st["path"] = os.path.join(st["folder"], "OldCoil.FCStd")
    d.saveAs(st["path"])
    App.closeDocument(d.Name)
    st["lines"] = len(lines())


# -- O1: open it --------------------------------------------------------------------------------
def o1_open():
    App.openDocument(st["path"])
    h.fit()


o1_open.wait_ms = 2500


def o1_rebuilt():
    h.check("rebuilt on opening: 571.39", close(h.solid_volume(), RIGHT), h.solid_volume())
    box = h.body().Shape.BoundBox
    # The d2 section is centred on the plane: -1 .. 21 (the mirror image went down to -21).
    h.check("it rises from the plane", box.ZMin > -1.5 and box.ZMax > 19, (box.ZMin, box.ZMax))
    new = lines()[st["lines"] :]
    h.check("one line in the Report view", len(new) == 1 and "Coil" in new[0], new)
    h.check("the design shows as changed", Gui.ActiveDocument.Modified)
    states = t.states()
    h.check("nothing red", all(v[1] == "ok" for v in states.values()), states)
    obj = coil_obj()
    h.check("one coil step", obj is not None, [o.Name for o in doc().Objects])
    h.shot("1-rebuilt")
    st["lines"] = len(lines())
    h.fit()
    h.press(QtCore.Qt.Key_S, QtCore.Qt.ControlModifier)


# -- O2: saved, opened again --------------------------------------------------------------------
def o2_describe():
    h.check("the version box", vi.accept_save())


def o2_close():
    h.check("saved", not Gui.ActiveDocument.Modified)
    App.closeDocument(doc().Name)


def o2_open():
    App.openDocument(st["path"])
    h.fit()


o2_open.wait_ms = 2500


def o2_same():
    h.check("still 571.39", close(h.solid_volume(), RIGHT), h.solid_volume())
    h.check("no rebuild this time", lines()[st["lines"] :] == [], lines()[st["lines"] :])
    h.check("not changed", not Gui.ActiveDocument.Modified)
    t.no_popups("the end")


h.run("gaps_old_coil", [setup, o1_open, o1_rebuilt, o2_describe, o2_close, o2_open, o2_same])
