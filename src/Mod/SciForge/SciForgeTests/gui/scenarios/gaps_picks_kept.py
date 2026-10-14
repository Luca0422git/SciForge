# SPDX-License-Identifier: LGPL-2.1-or-later
"""A fillet keeps its edge when the extrude under it changes after the design was saved and
opened again (Fusion keeps a step on what it picked), only real input.

Part: box 40 x 30 x 10, the front top edge rounded r2 (F, click the edge, type 2, OK).
Path K1, Ctrl+S: the Save dialog (Name PicksKept, Location a fresh folder), Save; the design
         is closed and the file opened again.
Path K2, Extrude 1 edited from the timeline: Taper Angle 3, OK. FreeCAD alone loses the
         name of the rounded edge ("?Edge4") and the round goes red; SciForge remembered
         where the edge was (in the file) and the round stays on it, not red.
Path K3, Ctrl+Z: no taper, the round still there; Ctrl+Y: tapered again.
Path K4, Ctrl+S (Enter in the version box), closed and opened again: unchanged.

Numbers: the round removes 40 * 2^2 (1 - pi/4) from the 12000 box; with the taper the part
measures 12330.796885 (the same as building the tapered extrude first and rounding the
same edge after: baseline on FreeCAD 1.1.4)."""

import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import timeline_input as t
from SciForgeTests.gui import versions_input as vi

V = App.Vector
ROUNDED = b.BOX - 40 * b.spandrel(2)
TAPERED = 12330.796885096093
st = {}


def doc():
    return App.ActiveDocument


def fillet_ok():
    item = t.item("Fillet 1")
    return item is not None and item.status == "ok" and item.state == "done"


# -- the round ----------------------------------------------------------------------------------
def k0_fillet():
    Gui.Selection.clearSelection()
    h.ribbon("Fillet")


def k0_edge():
    h.fit()
    h.click_edge(V(20, 0, 10))


def k0_radius():
    p = b.blend_panel()
    if h.check("the front top edge picked", p is not None and len(p.refs) == 1):
        ui.type_into(p.radius.widget, "2")


def k0_ok():
    h.check("r2 preview", b.close(h.solid_volume(), ROUNDED), h.solid_volume())
    h.task_button("OK")


def k0_made():
    h.check("Fillet 1 made", fillet_ok() and b.close(h.solid_volume(), ROUNDED), t.titles())


# -- K1: save, close, open --------------------------------------------------------------------
def k1_ctrl_s():
    st["folder"] = tempfile.mkdtemp(prefix="sciforge-picks-")
    h.fit()
    h.press(QtCore.Qt.Key_S, QtCore.Qt.ControlModifier)


def k1_dialog():
    h.check("the Save dialog", vi.fill_save_dialog(name="PicksKept", location=st["folder"]))
    vi.click_save()


def k1_saved():
    path = os.path.join(st["folder"], "PicksKept.FCStd")
    st["path"] = path
    h.check("PicksKept.FCStd written", os.path.isfile(path), os.listdir(st["folder"]))
    App.closeDocument(doc().Name)


def k1_open():
    App.openDocument(st["path"])
    h.fit()


def k1_opened():
    h.check("the round is back", fillet_ok() and b.close(h.solid_volume(), ROUNDED), t.states())
    b.timeline_double_click("Extrude 1", click_first=True)


# -- K2: a taper under the round ------------------------------------------------------------
def k2_taper():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    if h.check("Extrude 1 opens", p is not None and not p._closed):
        ui.type_into(p.taper.widget, "3")


def k2_ok():
    h.task_button("OK")


k2_ok.wait_ms = 1500


def k2_kept():
    h.check("dialog closed", not Gui.Control.activeDialog())
    h.check("the round is not red", fillet_ok(), t.states())
    h.check(
        "the round stays on its edge: 12330.80",
        b.close(h.solid_volume(), TAPERED, 1e-6),
        h.solid_volume(),
    )
    fillet = t.obj("Fillet 1")
    subs = list(fillet.Base[1]) if fillet is not None else []
    h.check("its edge has a name again", subs and not subs[0].startswith("?"), subs)
    h.shot("1-tapered")
    t.ctrl("z")


# -- K3: undo / redo --------------------------------------------------------------------------
def k3_undone():
    h.check("Ctrl+Z: no taper, the round", b.close(h.solid_volume(), ROUNDED), h.solid_volume())
    h.check("still not red", fillet_ok(), t.states())
    t.ctrl("y")


def k3_redone():
    h.check("Ctrl+Y: tapered", b.close(h.solid_volume(), TAPERED, 1e-6), h.solid_volume())
    h.check("still not red", fillet_ok(), t.states())


# -- K4: save again, open again ---------------------------------------------------------------
def k4_ctrl_s():
    h.fit()
    h.press(QtCore.Qt.Key_S, QtCore.Qt.ControlModifier)


def k4_describe():
    h.check("the version box", vi.accept_save())


def k4_saved():
    h.check("saved", not Gui.ActiveDocument.Modified)
    App.closeDocument(doc().Name)


def k4_open():
    App.openDocument(st["path"])
    h.fit()


def k4_opened():
    h.check("unchanged after opening", b.close(h.solid_volume(), TAPERED, 1e-6), h.solid_volume())
    h.check("the round is not red", fillet_ok(), t.states())
    t.no_popups("the end")
    h.shot("2-end")


h.run(
    "gaps_picks_kept",
    b.box_steps("PicksKept")
    + [
        k0_fillet,
        k0_edge,
        k0_radius,
        k0_ok,
        k0_made,
        k1_ctrl_s,
        k1_dialog,
        k1_saved,
        k1_open,
        k1_opened,
        k2_taper,
        k2_ok,
        k2_kept,
        k3_undone,
        k3_redone,
        k4_ctrl_s,
        k4_describe,
        k4_saved,
        k4_open,
        k4_opened,
    ],
)
