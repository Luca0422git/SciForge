# SPDX-License-Identifier: LGPL-2.1-or-later
"""Revolve, Sweep and Loft acting on several bodies (Fusion's Objects To Cut; wave 4,
modeling-2), only real input. Two plates 40 x 30 x 10 (x 0..40 and 50..90, y -15..15), the
second made as a New Body.

1. Revolve a 70 x 5 rectangle on the XY plane about the X axis, Full, Cut: the row "Bodies to
   Cut" lists both plates, the rod cuts both (one timeline step). Click the row, click the
   second plate: it is left out (only the first is cut); click it again: taken back. The
   row's x leaves every body out: the dialog says the row is empty and OK is refused; click
   both plates to take them back. OK.
2. Edit the revolve from the timeline: the row starts from its saved list; leave the second
   plate out, OK: only the first plate keeps the cut.
3. Ctrl+Z / Ctrl+Y.
4. Sweep a 10 x 4 rectangle on the first plate's end face along a line across the gap, Join:
   it touches both plates, so the row lists both and one Join merges them. OK.
5. Loft between two equal rectangles below and above the plates, Cut: both plates (now one
   body) lose a block. Esc (nothing changes).
6. Save, close, reopen: the revolve still acts on its bodies.

Hand-derived: a rod r 5 about X over x 10..80: its upper half lies in each plate over 30 mm,
pi 25 / 2 * 30 each; the bar 10 x 10 x 4 = 400 bridges the gap; the loft block (x 30..60,
y -5..5) takes 10 x 10 x 10 out of each plate.
"""

import math
import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import hole_steps as hs
from SciForgeTests.gui import sweep_loft_steps as st
from SciForgeTests.gui import widget_input as w

V = App.Vector
s = {}
PLATE = 12000.0
HALF = math.pi * 25 / 2 * 30


def near(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


def doc():
    return App.ActiveDocument


def bodies():
    from sciforge import bodies as b

    return [x for x in b.list_bodies(doc()) if b.is_shown(x)]


def volumes():
    return sorted(round(b.Shape.Volume, 6) for b in bodies() if not b.Shape.isNull())


def total():
    return sum(b.Shape.Volume for b in bodies() if not b.Shape.isNull())


def rpanel():
    from sciforge import revolve_ui

    p = revolve_ui.RevolvePanel.last
    return p if p is not None and not p._closed else None


def spanel():
    from sciforge import sweep_ui

    p = sweep_ui.SweepPanel.last
    return p if p is not None and not p._closed else None


def lpanel():
    from sciforge import loft_ui

    p = loft_ui.LoftPanel.last
    return p if p is not None and not p._closed else None


# -- two plates --------------------------------------------------------------------------------
def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("M2Bodies")
    h.fit()
    h.ribbon("Create Sketch")


def pick_xy():
    h.click(V(12, -8, 0))


def draw_plate1():
    sk = h.in_sketch()
    h.check("sketch open on XY", sk is not None)
    if sk:
        h.draw_rectangle(sk, 0, -15, 40, 15)


def finish():
    h.ribbon("Finish Sketch")


def extrude():
    h.click_empty()
    h.fit()
    h.press("e")


def plate_distance():
    p = ui_extrude_panel()
    if p is not None:
        ui.type_into(p.distance.widget, "10")


def ui_extrude_panel():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    return p if p is not None and not p._closed else None


def ok():
    h.task_button("OK")


def plate1_made():
    h.check("plate 1", near(total(), PLATE), total())


def sketch2():
    h.click_empty()
    h.ribbon("Create Sketch")


def pick_xy_free():
    h.fit()
    h.click(V(-15, -20, 0))  # the XY square, left of the plate


def draw_plate2():
    sk = h.in_sketch()
    h.check("second sketch open", sk is not None)
    if sk:
        h.draw_rectangle(sk, 50, -15, 90, 15)


def plate2_options():
    p = ui_extrude_panel()
    if p is None:
        return
    ui.type_into(p.distance.widget, "10")
    h.check("New Body", ui.choose(p.operation, "New Body"))


def plates_made():
    h.check("two plates", len(bodies()) == 2 and near(total(), 2 * PLATE), (bodies(), total()))
    s["plate2"] = [b for b in bodies() if b.Shape.BoundBox.XMin > 45][0]
    s["plate1"] = [b for b in bodies() if b.Shape.BoundBox.XMin < 5][0]
    h.fit()


# -- 1. Revolve Cut through both ---------------------------------------------------------------
def rod_sketch():
    h.click_empty()
    h.ribbon("Create Sketch")


def rod_pick_xy():
    h.fit()
    h.click(V(-15, -20, 0))


def draw_rod():
    sk = h.in_sketch()
    h.check("1 rod sketch open", sk is not None)
    if sk:
        h.draw_rectangle(sk, 10, 0, 80, 5)


def revolve():
    h.click_empty()
    h.fit()
    h.ribbon("Revolve")


def click_x_axis():
    p = rpanel()
    h.check("1 the rectangle picked by itself", p is not None and len(p.profiles) == 1)
    h.click(V(-25, 0, 0))  # the X axis, left of the plates


def revolve_options():
    p = rpanel()
    if p is None:
        return
    h.check("1 the X axis", p.axis is not None and "X" in p.axis[0].Role, p.axis)
    h.check("1 Type Full", ui.choose(p.type, "Full"))
    h.check("1 Cut", ui.choose(p.operation, "Cut"))


def both_cut():
    p = rpanel()
    if p is None:
        return
    h.check(
        "1 the row: Bodies to Cut, 2 bodies",
        p.bodies_row.label.text() == "Bodies to Cut"
        and p.fields["bodies"].button.text() == "2 bodies",
        (p.bodies_row.label.text(), p.fields["bodies"].button.text()),
    )
    h.check("1 both plates lose the rod's half", near(total(), 2 * (PLATE - HALF)), volumes())
    h.shot("1-revolve-two-bodies")
    w.click(p.fields["bodies"].button)


def leave_out():
    p = rpanel()
    if p is None:
        return
    h.check("1 the row takes the clicks", p.active == "bodies", p.active)
    h.click(V(85, 10, 10))  # the second plate's top


def left_out():
    p = rpanel()
    h.check(
        "1 the second plate left out: only the first is cut",
        near(total(), 2 * PLATE - HALF)
        and p is not None
        and p.fields["bodies"].button.text() == "1 body",
        (volumes(), p and p.fields["bodies"].button.text()),
    )
    h.click(V(85, 10, 10))


def taken_back():
    p = rpanel()
    h.check(
        "1 taken back: both cut",
        near(total(), 2 * (PLATE - HALF)),
        (volumes(), p and p.message.text(), p and p.fields["bodies"].button.text()),
    )
    if p is not None:
        w.click(p.fields["bodies"].clear)  # the row's x: every body left out


def cleared():
    p = rpanel()
    if p is None:
        return
    h.check(
        "1 an empty row is refused with the reason",
        "is empty" in p.message.text() and "click a body" in p.message.text().lower(),
        p.message.text(),
    )
    ok()  # refused: the dialog stays


def ok_refused():
    h.check("1 OK is refused while the row is empty", rpanel() is not None)
    h.click(V(85, 10, 10))  # take the second plate back


def one_back():
    h.click(V(5, 10, 10))  # and the first


def both_back():
    p = rpanel()
    h.check(
        "1 both taken back: both cut",
        near(total(), 2 * (PLATE - HALF)) and p is not None and "⚠" not in p.message.text(),
        (volumes(), p and p.message.text()),
    )
    ok()


def revolve_done():
    from sciforge import extrude_bodies

    h.check("1 OK closed the dialog", rpanel() is None)
    h.check("1 kept", near(total(), 2 * (PLATE - HALF)), volumes())
    leads = [o for o in doc().Objects if extrude_bodies.lead_kind(o) == "revolve"]
    h.check(
        "1 one timeline step with a hidden step in the other plate",
        len(leads) == 1 and len(extrude_bodies.followers_of(leads[0])) == 1,
        leads,
    )
    s["revolve_title"] = ui.timeline_titles()[-1] if ui.timeline_titles() else ""


# -- 2. Edit the revolve -----------------------------------------------------------------------
def edit_revolve():
    h.fit()
    h.check("2 double-click the revolve", ui.double_click_timeline(s["revolve_title"] or "?"))


def edit_open():
    p = rpanel()
    h.check("2 editing the revolve", p is not None and p.editing)
    if p is None:
        return
    h.check(
        "2 the row starts from its two bodies",
        p.fields["bodies"].button.text() == "2 bodies",
        p.fields["bodies"].button.text(),
    )
    w.click(p.fields["bodies"].button)


def edit_leave_out():
    h.click(V(85, 10, 10))  # the second plate's top


def edit_ok():
    p = rpanel()
    h.check(
        "2 one body left in the row",
        p is not None and p.fields["bodies"].button.text() == "1 body",
        p and p.fields["bodies"].button.text(),
    )
    ok()


def edited():
    h.check("2 the second plate keeps its material", near(total(), 2 * PLATE - HALF), volumes())


# -- 3. Undo / redo ----------------------------------------------------------------------------
def undo():
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


def undone():
    h.check("3 Ctrl+Z: both cut again", near(total(), 2 * (PLATE - HALF)), volumes())


def redo():
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


def redone():
    h.check("3 Ctrl+Y: the edit again", near(total(), 2 * PLATE - HALF), volumes())


# -- 4. Sweep Join across the gap --------------------------------------------------------------
def bar_sketch():
    h.click_empty()
    h.ribbon("Create Sketch")


def bar_face():
    h.fit()
    h.click(V(40, 10, 7))  # the first plate's end face, facing the second (off the rod)


def draw_bar():
    sk = h.in_sketch()
    h.check("4 sketch on the end face", sk is not None)
    if sk:
        a = h.to_sketch(sk, V(40, -5, 6))
        b = h.to_sketch(sk, V(40, 5, 10))
        h.draw_rectangle(sk, min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]))


def path_sketch():
    h.click_empty()
    h.ribbon("Create Sketch")


def path_xz():
    h.fit()
    h.click(V(-10, 0, 18))  # the XZ square, above and left of the first plate


def draw_path():
    import Part

    sk = h.in_sketch()
    h.check("4 path sketch on XZ", sk is not None)
    if sk:
        a = h.to_sketch(sk, V(40, 0, 8))
        b = h.to_sketch(sk, V(50, 0, 8))
        sk.addGeometry(Part.LineSegment(V(a[0], a[1], 0), V(b[0], b[1], 0)))
        doc().recompute()


def sweep():
    h.click_empty()
    h.fit()
    st.menu("Sweep")


def pick_profile_and_path():
    p = spanel()
    h.check("4 the sweep dialog", p is not None)
    if p is None:
        return
    if not p.profiles:
        h.click(V(40, 0, 8))  # inside the bar's area on the end face
    h.check("4 the profile", bool(p.profiles), p.profiles)


def pick_path():
    p = spanel()
    if p is None:
        return
    if p.active != "path":
        w.click(p.fields["path"].button)
    h.click_edge(V(45, 0, 8))


def sweep_join():
    p = spanel()
    if p is None:
        return
    h.check("4 the path", bool(p.path), p.path)
    h.check("4 Join", ui.choose(p.operation, "Join"))


def sweep_built():
    p = spanel()
    if p is None:
        return
    h.check(
        "4 the row: Bodies to Join, 2 bodies",
        p.fields["bodies"].button.text() == "2 bodies",
        p.fields["bodies"].button.text(),
    )
    # While the dialog is open the merged-in plate stays shown (it can still be clicked to
    # leave it out, as in Extrude); the joined body already holds both plates and the bar.
    h.check(
        "4 the joined body: both plates and the bar",
        any(near(v, 2 * PLATE - HALF + 400) for v in volumes()),
        (volumes(), len(bodies())),
    )
    h.shot("4-sweep-join")
    ok()


def sweep_done():
    h.check("4 OK", spanel() is None)
    h.check("4 kept", len(bodies()) == 1 and near(total(), 2 * PLATE - HALF + 400), volumes())


# -- 5. Loft Cut, then Esc ---------------------------------------------------------------------
def low_sketch():
    h.click_empty()
    h.ribbon("Create Sketch")


def low_xy():
    h.fit()
    h.click(V(-15, -20, 0))


def draw_low():
    sk = h.in_sketch()
    h.check("5 low sketch", sk is not None)
    if sk:
        h.draw_rectangle(sk, 30, -5, 60, 5)


def high_sketch():
    h.click_empty()
    h.ribbon("Create Sketch")


def high_face():
    h.fit()
    h.click(V(5, 10, 10))  # the first plate's top


def draw_high():
    sk = h.in_sketch()
    h.check("5 sketch on the top", sk is not None)
    if sk:
        a = h.to_sketch(sk, V(30, -5, 10))
        b = h.to_sketch(sk, V(60, 5, 10))
        h.draw_rectangle(sk, min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]))


def loft():
    h.click_empty()
    h.fit()
    st.menu("Loft")


def loft_profiles():
    p = lpanel()
    h.check("5 the loft dialog", p is not None)
    if p is None:
        return
    h.click(V(35, 0, 10))  # the top rectangle (one of its areas)


def loft_second():
    p = lpanel()
    if p is None:
        return
    Gui.ActiveDocument.ActiveView.viewBottom()  # turn the view: the rectangle is under
    Gui.ActiveDocument.ActiveView.fitAll()
    h.click(V(45, 0, 0))  # the lower rectangle, seen from below


def loft_cut():
    p = lpanel()
    if p is None:
        return
    s["loft_profiles"] = len(p.profiles)
    h.check("5 two profiles", len(p.profiles) == 2, p.profiles)
    h.check("5 Cut", ui.choose(p.operation, "Cut"))
    h.fit()


def loft_built():
    p = lpanel()
    if p is None:
        return
    if s.get("loft_profiles", 0) >= 2:
        h.check(
            "5 the loft cuts the plates' blocks",
            total() < 2 * PLATE - HALF + 400 - 1.0,
            (volumes(), p.message.text()),
        )
    h.press(QtCore.Qt.Key_Escape)


def loft_esc():
    h.check("5 Esc closed the loft", lpanel() is None)
    h.check("5 Esc: nothing changed", near(total(), 2 * PLATE - HALF + 400), volumes())


# -- 6. Save, close, reopen --------------------------------------------------------------------
def save():
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-m2-bodies-"), "m2_bodies.FCStd")
    s["path"] = path
    doc().saveAs(path)
    h.check("6 saved", os.path.isfile(path), path)
    App.closeDocument(doc().Name)


def reopen():
    App.openDocument(s["path"])
    h.fit()


def reopened():
    from sciforge import extrude_bodies, revolve

    h.check("6 same part after reopening", near(total(), 2 * PLATE - HALF + 400), volumes())
    leads = [o for o in doc().Objects if extrude_bodies.lead_kind(o) == "revolve"]
    stored = revolve.read(leads[0])[2].get("bodies") if leads else None
    h.check(
        "6 the revolve keeps one body in its list", stored is not None and len(stored) == 1, stored
    )
    h.check("6 every body valid", all(b.Shape.isValid() for b in bodies()))
    hs.no_popups("Objects To Cut")


draw_plate1.wait_ms = 300
both_cut.wait_ms = 1200
left_out.wait_ms = 1200
taken_back.wait_ms = 1200
cleared.wait_ms = 1200
both_back.wait_ms = 1200
sweep_built.wait_ms = 1500
edit_ok.wait_ms = 1200
loft_built.wait_ms = 1500

h.run(
    "modeling2_bodies",
    [
        new_design,
        pick_xy,
        draw_plate1,
        finish,
        extrude,
        plate_distance,
        ok,
        plate1_made,
        sketch2,
        pick_xy_free,
        draw_plate2,
        finish,
        extrude,
        plate2_options,
        ok,
        plates_made,
        rod_sketch,
        rod_pick_xy,
        draw_rod,
        finish,
        revolve,
        click_x_axis,
        revolve_options,
        both_cut,
        leave_out,
        left_out,
        taken_back,
        cleared,
        ok_refused,
        one_back,
        both_back,
        revolve_done,
        edit_revolve,
        edit_open,
        edit_leave_out,
        edit_ok,
        edited,
        undo,
        undone,
        redo,
        redone,
        bar_sketch,
        bar_face,
        draw_bar,
        finish,
        path_sketch,
        path_xz,
        draw_path,
        finish,
        sweep,
        pick_profile_and_path,
        pick_path,
        sweep_join,
        sweep_built,
        sweep_done,
        low_sketch,
        low_xy,
        draw_low,
        finish,
        high_sketch,
        high_face,
        draw_high,
        finish,
        loft,
        loft_profiles,
        loft_second,
        loft_cut,
        loft_built,
        loft_esc,
        save,
        reopen,
        reopened,
    ],
)
