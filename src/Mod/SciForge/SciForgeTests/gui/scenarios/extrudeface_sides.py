# SPDX-License-Identifier: LGPL-2.1-or-later
"""A click on a face ends the extrude there: below the sketch (a negative distance), a cut
down to a face, Two Sides (a face and a corner), Symmetric (half and whole length), what
keeps working as before (a face in the profile's plane is a profile, an empty Profiles box
takes the face), a face along the extrusion refused with a reason, and Press Pull on a
sketch area. Only real input (parity/extrude-presspull.md).

A plate 50 x 30 x 10 (x 10..60) with a tower 10 x 30 up to z 40 at its left.

Q1  A 10 x 10 square sketched on the tower's top plane but over the plate (x 30..40,
    y 10..20, z 40). E, click the plate's top: Distance -30 (down), Join, +3000. OK.
Q2  A 6 x 10 rectangle on the tower's top (x 2..8, y 10..20). E, click the plate's top:
    Distance -30, Cut by itself (shown in red), -1800. OK.
Q3  A square on the plate (x 45..55, y 5..15). E, Two Sides, click the tower's top: side one
    30 ("Side One up to the face"); click the plate's bottom front corner (60, 0, 0): side
    two 10 ("Side Two up to the point"). OK: the step's lengths 30 and 10, +3000 (side two
    runs inside the plate).
Q4  A square on the plate (x 45..55, y 18..28). E, Symmetric, click the tower's top: 30 on
    each side; Whole Length, click it again: 60 in all. OK: +3000 above, +2000 under the
    plate.
Q5  A 6 x 6 square on the tower's top (x 2..8, y 22..28). E, 5: a click on the Q3 boss's
    top (in the profile's plane, z 40) adds it as a profile and a click on its preview's
    end drops it (as before); a click on the tower's side (along the extrusion) changes
    nothing and says why. Clear the Profiles box, click the tower's top: that face is the
    profile (as before). Cancel.
Q6  A square on the plate (x 15..25, y 18..28), Finish, Q (Press Pull), click the square:
    Extrude opens on it; click the tower's top: 30. OK: +3000.

Hand-derived: 15000 + 12000 = 27000; Q1 30000; Q2 28200; Q3 31200; Q4 36200; Q6 39200.
"""

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import extrudeface_steps as x
from SciForgeTests.gui import harness as h

V = App.Vector
s = {}
PARTS = 27000.0
TOWER_TOP = V(5, 4, 40)
PLATE_TOP = V(50, 26, 10)


def step(name, fn):
    return x.named(name, fn)


def opened(tag, expect=1):
    p = x.panel()
    if not h.check("%s Extrude open" % tag, p is not None):
        return None
    h.check("%s the sketch's square is picked" % tag, len(p.profiles) == expect, p.profiles)
    h.fit()
    return p


# -- Q1: down to the plate --------------------------------------------------------------------
def q1_click():
    if opened("Q1") is not None:
        h.click(PLATE_TOP)


def q1_reached():
    p = x.panel()
    if p is None:
        return
    h.check("Q1 Distance -30 (down)", p.distance.value() == -30.0, p.distance.value())
    h.check("Q1 says so", p.info.text() == "Up to the face: -30 mm", p.info.text())
    h.check("Q1 Join", p.operation.currentData() == "join", p.operation.currentText())
    h.check("Q1 +3000", x.near(x.total(), PARTS + 3000.0), x.total())
    h.task_button("OK")


def q1_done():
    h.check("Q1 kept", x.near(x.total(), 30000.0), x.total())
    feature = x.last_extrude()
    h.check("Q1 the step is 30 long", x.length(feature) == 30.0, x.length(feature))


# -- Q2: cut down to a face -------------------------------------------------------------------
def q2_click():
    if opened("Q2") is not None:
        h.click(PLATE_TOP)


def q2_cut():
    from sciforge import cut_preview

    p = x.panel()
    if p is None:
        return
    h.check("Q2 Distance -30", p.distance.value() == -30.0, p.distance.value())
    h.check("Q2 Cut by itself", p.operation.currentData() == "cut", p.operation.currentText())
    h.check("Q2 shown in red", bool(cut_preview.find()), len(cut_preview.find()))
    h.check("Q2 -1800", x.near(x.total(), 30000.0 - 1800.0), x.total())
    h.shot("Q2-cut-down-to-the-plate")
    h.task_button("OK")


def q2_done():
    h.check("Q2 kept", x.near(x.total(), 28200.0), x.total())
    feature = x.last_extrude()
    h.check("Q2 a pocket 30 deep", x.length(feature) == 30.0, x.length(feature))


# -- Q3: Two Sides, a face and a corner -------------------------------------------------------
def q3_two_sides():
    p = opened("Q3")
    if p is not None:
        h.check("Q3 Two Sides", ui.choose(p.direction, "Two Sides"))


def q3_click_tower():
    h.fit()
    h.click(TOWER_TOP)


def q3_side_one():
    p = x.panel()
    if p is None:
        return
    h.check("Q3 side one 30", p.distance.value() == 30.0, p.distance.value())
    h.check("Q3 says side one", p.info.text() == "Side One up to the face: 30 mm", p.info.text())
    h.check("Q3 side one built", x.near(x.total(), 28200.0 + 3000.0), x.total())
    s["corner"] = x.click_vertex(V(60, 0, 0))


def q3_side_two():
    p = x.panel()
    if p is None:
        return
    h.check("Q3 the corner was clicked", s.get("corner"), h.state.get("last_click"))
    h.check("Q3 side two 10", p.distance2.value() == 10.0, p.distance2.value())
    h.check("Q3 side one still 30", p.distance.value() == 30.0, p.distance.value())
    h.check("Q3 says side two", p.info.text() == "Side Two up to the point: 10 mm", p.info.text())
    h.check("Q3 side two runs inside the plate", x.near(x.total(), 31200.0), x.total())
    h.task_button("OK")


def q3_done():
    feature = x.last_extrude()
    h.check(
        "Q3 two sides",
        getattr(feature, "SideType", None) == "Two sides",
        getattr(feature, "SideType", None),
    )
    h.check(
        "Q3 lengths 30 and 10",
        x.length(feature) == 30.0 and x.length(feature, "Length2") == 10.0,
        (x.length(feature), x.length(feature, "Length2")),
    )
    h.check("Q3 kept", x.near(x.total(), 31200.0), x.total())


# -- Q4: Symmetric ----------------------------------------------------------------------------
def q4_symmetric():
    p = opened("Q4")
    if p is not None:
        h.check("Q4 Symmetric", ui.choose(p.direction, "Symmetric"))


def q4_click():
    h.fit()
    h.click(TOWER_TOP)


def q4_half():
    p = x.panel()
    if p is None:
        return
    h.check("Q4 30 on each side", p.distance.value() == 30.0, p.distance.value())
    h.check("Q4 says so", p.info.text() == "Up to the face: 30 mm on each side", p.info.text())
    h.check("Q4 +3000 above, +2000 under", x.near(x.total(), 36200.0), x.total())
    h.check("Q4 Whole Length", ui.choose(p.measurement, "Whole Length"))


def q4_whole_click():
    h.fit()
    h.click(TOWER_TOP)


def q4_whole():
    p = x.panel()
    if p is None:
        return
    h.check("Q4 60 in all", p.distance.value() == 60.0, p.distance.value())
    h.check(
        "Q4 says so",
        p.info.text() == "Up to the face: 60 mm in all (30 mm on each side)",
        p.info.text(),
    )
    h.check("Q4 the same solid", x.near(x.total(), 36200.0), x.total())
    h.task_button("OK")


def q4_done():
    h.check("Q4 kept", x.near(x.total(), 36200.0), x.total())
    zmin = min(b.Shape.BoundBox.ZMin for b in x.bodies())
    h.check("Q4 it reaches 30 under the plate's top", x.near(zmin, -20.0), zmin)


# -- Q5: what keeps working as before ---------------------------------------------------------
def q5_type():
    p = opened("Q5")
    if p is not None:
        ui.type_into(p.distance.widget, "5")


def q5_click_coplanar():
    h.check("Q5 5 up", x.near(x.total(), 36200.0 + 180.0), x.total())
    h.fit()
    h.click(V(50, 10, 40))  # the Q3 boss's top: in the profile's plane (z 40)


def q5_added():
    p = x.panel()
    if p is None:
        return
    h.check(
        "Q5 a face in the profile's plane is added as a profile", len(p.profiles) == 2, p.profiles
    )
    h.check("Q5 the distance stays 5", p.distance.value() == 5.0, p.distance.value())
    h.check("Q5 no note about a face", "Up to" not in p.info.text(), p.info.text())
    h.check("Q5 both 5 up", x.near(x.total(), 36200.0 + 680.0), x.total())
    h.fit()
    h.click(V(50, 10, 45))  # the same face, now the end of its preview: drops it


def q5_dropped():
    p = x.panel()
    if p is None:
        return
    h.check("Q5 a click on it again drops it", len(p.profiles) == 1, p.profiles)
    h.check("Q5 back to the square", x.near(x.total(), 36200.0 + 180.0), x.total())
    h.fit()
    h.click(V(10, 15, 30))  # the tower's side: it runs along the extrusion


def q5_along():
    p = x.panel()
    if p is None:
        return
    h.check("Q5 the tower's side: nothing changes", p.distance.value() == 5.0, p.distance.value())
    h.check("Q5 says why", "runs along the extrusion" in p.message.text(), p.message.text())
    h.check("Q5 still one profile", len(p.profiles) == 1, p.profiles)
    ui.click(p.fields["profiles"].clear)


def q5_cleared():
    p = x.panel()
    if p is None:
        return
    h.check("Q5 the Profiles box is empty", not p.profiles, p.profiles)
    h.fit()
    h.click(TOWER_TOP)


def q5_face_profile():
    p = x.panel()
    if p is None:
        return
    h.check(
        "Q5 an empty Profiles box takes the tower's top as the profile",
        len(p.profiles) == 1 and p.profiles[0][1].startswith("Face"),
        p.profiles,
    )
    h.check("Q5 the distance is not changed by it", p.distance.value() == 5.0, p.distance.value())
    h.task_button("Cancel")


def q5_cancelled():
    h.check("Q5 Cancel", x.panel() is None and not Gui.Control.activeDialog())
    h.check("Q5 nothing changed", x.near(x.total(), 36200.0), x.total())


# -- Q6: Press Pull on a sketch area ----------------------------------------------------------
def q6_q():
    h.click_empty()
    h.fit()
    h.press("q")


def q6_area():
    h.click(V(16.5, 19.5, 10))


def q6_extrude():
    p = x.panel()
    if not h.check(
        "Q6 Press Pull opened Extrude on the square",
        p is not None and len(p.profiles) == 1,
        p and p.profiles,
    ):
        return
    h.fit()
    h.click(TOWER_TOP)


def q6_reached():
    p = x.panel()
    if p is None:
        return
    h.check("Q6 30", p.distance.value() == 30.0, p.distance.value())
    h.check("Q6 +3000", x.near(x.total(), 39200.0), x.total())
    h.task_button("OK")


def q6_done():
    h.check("Q6 kept", x.near(x.total(), 39200.0), x.total())
    h.check("Q6 no snap mark left", not x.snap_marks(), len(x.snap_marks()))
    h.shot("Q6-end")


h.run(
    "extrudeface_sides",
    [
        x.new_design("ExtrudeFaceSides"),
        *x.xy_block("plate", (10, 0, 60, 30), 10, 15000.0),
        *x.xy_block("tower", (0, 0, 10, 30), 40, PARTS),
        *x.face_sketch("q1", TOWER_TOP, (30, 10, 40, 20)),
        x.press_e("q1_e"),
        q1_click,
        q1_reached,
        q1_done,
        *x.face_sketch("q2", TOWER_TOP, (2, 10, 8, 20)),
        x.press_e("q2_e"),
        q2_click,
        q2_cut,
        q2_done,
        *x.face_sketch("q3", PLATE_TOP, (45, 5, 55, 15)),
        x.press_e("q3_e"),
        q3_two_sides,
        q3_click_tower,
        q3_side_one,
        q3_side_two,
        q3_done,
        *x.face_sketch("q4", PLATE_TOP, (45, 18, 55, 28)),
        x.press_e("q4_e"),
        q4_symmetric,
        q4_click,
        q4_half,
        q4_whole_click,
        q4_whole,
        q4_done,
        *x.face_sketch("q5", TOWER_TOP, (2, 22, 8, 28)),
        x.press_e("q5_e"),
        q5_type,
        q5_click_coplanar,
        q5_added,
        q5_dropped,
        q5_along,
        q5_cleared,
        q5_face_profile,
        q5_cancelled,
        # the plate's top where it shows, away from the origin squares (at 12, 2 the XZ
        # square stands in front of the face and takes the click, as it shows)
        *x.face_sketch("q6", V(45, 3, 10), (15, 18, 25, 28)),
        q6_q,
        q6_area,
        q6_extrude,
        q6_reached,
        q6_done,
    ],
)
