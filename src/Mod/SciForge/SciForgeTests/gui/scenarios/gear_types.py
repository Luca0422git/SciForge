# SPDX-License-Identifier: LGPL-2.1-or-later
"""Gear: every type and the English standard, only real input, then save and reopen.

1. Internal: Gear, XY, centre on the origin, Type Internal: the teeth point inwards, the
   Hole field goes and Rim Thickness comes (5); Number of Teeth 40; OK.
2. Rack: Gear, XY, centre at (0, 80), Type Rack: Rack Size / Height come; 10 teeth;
   Rack Size Length (the same rack, 62.83 long), Rack Length 50; OK.
3. English: Gear, XZ, centre at (120, 0), Standard English: Diametral Pitch 12.7 (the
   same tooth size), type 10; 20 teeth; Symmetric; OK. Pitch Diameter 2 in = 50.8 mm.
4. Save, close, open: the three gears are as they were; double-click "Gear 2" (the rack):
   its fields come back; 12 teeth by Number of Teeth; OK.
Volumes: gear_core.area() (the exact outline) x thickness, see gear_spur.py.
"""

import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import primitive_input as pi

V = App.Vector
s = {"made": 0.0}


def area(**options):
    from sciforge import gear_core

    return gear_core.area(options)


def near(a, b, tol=1e-6):
    return pi.near(a, b, tol)


def vol():
    return pi.total_volume()


def doc():
    return App.ActiveDocument


def panel():
    return pi.panel("GearPanel")


INTERNAL = dict(type="internal", teeth=40, rim=5)
RACK = dict(type="rack", teeth=10, rack_size="length", rack_length=50)
ENGLISH = dict(standard="english", diametral_pitch=10, teeth=20)


# -- 1. internal ----------------------------------------------------------------------------------
def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("GearTypes")
    h.fit()
    pi.menu("Gear")


def i_plane():
    h.click(V(15, -15, 0))


def i_centre():
    h.click(V(0, 0, 0))


i_centre.wait_ms = 2000


def i_type():
    p = panel()
    if p is None:
        h.check("Gear dialog", False)
        return
    h.check("a spur gear first", near(vol(), area() * 10.0), vol())
    h.check("Internal", ui.choose(p.type, "Internal"))


def i_internal():
    p = panel()
    h.check("rim shown, hole hidden", p.rim.widget.isVisible() and not p.hole.widget.isVisible())
    h.check("an internal gear, 24 teeth", near(vol(), area(type="internal") * 10.0), vol())
    ui.type_into(p.teeth.widget, "40")


i_internal.wait_ms = 2000


def i_forty():
    expected = area(**INTERNAL) * 10.0
    h.check("40 teeth, rim 5", near(vol(), expected), (vol(), expected))
    shape = pi.bodies()[0].Shape
    b = pi.bbox(shape)
    h.check("the rim's outside: 95 across", near(b[3] - b[0], 95.0, 1e-4), b)
    h.check("a ring: the centre is empty", not shape.isInside(V(0, 0, 5), 1e-6, True))
    h.fit()
    h.shot("1-internal")
    h.task_button("OK")


i_forty.wait_ms = 2000


def i_kept():
    h.check("dialog closed", pi.no_dialog())
    s["internal"] = area(**INTERNAL) * 10.0
    h.check("kept", near(vol(), s["internal"]), vol())
    h.click_empty()
    pi.menu("Gear")


# -- 2. rack --------------------------------------------------------------------------------------
def r_plane():
    p = panel()
    h.check(
        "the last gear's values come back (Fusion's sample remembers)",
        p is not None and p.type.currentText() == "Internal",
    )
    h.click(V(40, -40, 0))  # a corner of the XY square the parts leave free


def r_centre():
    h.click(V(0, 80, 0))


r_centre.wait_ms = 2000


def r_type():
    p = panel()
    if p is None:
        h.check("Gear dialog", False)
        return
    h.check("a second body", len(pi.bodies()) == 2, len(pi.bodies()))
    h.check("Rack", ui.choose(p.type, "Rack"))


r_type.wait_ms = 1000


def r_rack():
    p = panel()
    h.check(
        "rack fields shown",
        p.rack_size.isVisible()
        and p.rack_height.widget.isVisible()
        and not p.rim.widget.isVisible(),
    )
    h.check("Pitch (not Pitch Diameter)", p.pitch_label.text() == "Pitch", p.pitch_label.text())
    ui.type_into(p.teeth.widget, "10")


r_rack.wait_ms = 2000


def r_ten():
    p = panel()
    expected = area(type="rack", teeth=10) * 10.0
    h.check("a rack of 10 teeth", near(vol() - s["internal"], expected), vol() - s["internal"])
    h.check("Size by Length", ui.choose(p.rack_size, "Length"))


r_ten.wait_ms = 2000


def r_length():
    p = panel()
    h.check(
        "the same rack, by length", near(p.rack_length.value(), 62.832, 1e-4), p.rack_length.value()
    )
    h.check("teeth field hidden", not p.teeth.widget.isVisible())
    ui.type_into(p.rack_length.widget, "50")


r_length.wait_ms = 2000


def r_fifty():
    expected = area(**RACK) * 10.0
    rack = vol() - s["internal"]
    h.check("50 long", near(rack, expected), (rack, expected))
    body = pi.bodies()[1]
    b = pi.bbox(body.Shape)
    h.check("50 along x, centred", near(b[0], -25.0, 1e-4) and near(b[3], 25.0, 1e-4), b)
    h.check("teeth up to the pitch line + module", near(b[4], 82.0, 1e-4), b)
    h.fit()
    h.shot("2-rack")
    h.task_button("OK")


r_fifty.wait_ms = 2000


def r_kept():
    s["rack"] = area(**RACK) * 10.0
    h.check("kept", near(vol(), s["internal"] + s["rack"]), vol())
    h.click_empty()
    pi.menu("Gear")


# -- 3. English, symmetric, on XZ -----------------------------------------------------------------
def e_plane():
    h.click(V(10, 0, 30))  # the XZ square above the parts: nothing in front of it there


def e_centre():
    p = panel()
    h.check(
        "XZ picked",
        p is not None and p.plane_field.button.text() == "XZ Plane",
        p and p.plane_field.button.text(),
    )
    h.click(V(120, 0, 0))


e_centre.wait_ms = 2000


def e_spur():
    p = panel()
    if p is None:
        h.check("Gear dialog", False)
        return
    h.check("Spur", ui.choose(p.type, "Spur"))


e_spur.wait_ms = 1000


def e_english():
    p = panel()
    h.check("English", ui.choose(p.standard, "English"))


e_english.wait_ms = 1500


def e_dp():
    p = panel()
    h.check(
        "Diametral Pitch shown, Module hidden",
        p.dp.widget.isVisible() and not p.module.widget.isVisible(),
    )
    h.check("the same tooth size: DP 12.7", near(p.dp.value(), 12.7, 1e-6), p.dp.value())
    ui.type_into(p.dp.widget, "10")


e_dp.wait_ms = 1500


def e_teeth():
    p = panel()
    ui.type_into(p.teeth.widget, "20")


e_teeth.wait_ms = 1500


def e_symmetric():
    p = panel()
    h.check(
        "Pitch Diameter 2 in = 50.8 mm",
        p.pitch_value.text().startswith("50.8"),
        p.pitch_value.text(),
    )
    pi.tick(p.symmetric)


e_symmetric.wait_ms = 1500


def e_check():
    p = panel()
    h.check("Symmetric ticked", p.symmetric.isChecked())
    english = area(**ENGLISH) * 10.0
    made = vol() - s["internal"] - s["rack"]
    h.check("module 2.54 gear", near(made, english), (made, english))
    body = pi.bodies()[2]
    b = pi.bbox(body.Shape)
    h.check(
        "on XZ, centred on it: y from -5 to 5", near(b[1], -5.0, 1e-4) and near(b[4], 5.0, 1e-4), b
    )
    h.check("outside diameter (z + 2) / DP = 2.2 in", near(b[3] - b[0], 55.88, 1e-3), b)
    h.fit()
    h.shot("3-english")
    h.task_button("OK")


e_check.wait_ms = 2000


def e_kept():
    s["english"] = area(**ENGLISH) * 10.0
    s["volume"] = s["internal"] + s["rack"] + s["english"]
    h.check("three gears", near(vol(), s["volume"]), vol())
    titles = ui.timeline_titles()
    h.check("Gear 1, 2, 3", all("Gear %d" % k in titles for k in (1, 2, 3)), titles)


# -- 4. save and reopen ---------------------------------------------------------------------------
def save():
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-gear-"), "gears.FCStd")
    s["path"] = path
    doc().saveAs(path)
    h.check("saved", os.path.isfile(path), path)


def close():
    App.closeDocument(doc().Name)


def reopen():
    App.openDocument(s["path"])
    h.fit()


reopen.wait_ms = 2500


def reopened():
    h.check("reopened: same volume", near(vol(), s["volume"]), (vol(), s["volume"]))
    doc().recompute()
    h.check("a recompute keeps it", near(vol(), s["volume"]), vol())
    broken = [o.Label for o in doc().Objects if "Invalid" in list(o.State)]
    h.check("nothing broken", not broken, broken)
    h.check("double-click Gear 2", ui.double_click_timeline("Gear 2"), ui.timeline_titles())


reopened.wait_ms = 2500


def rack_editing():
    p = panel()
    h.check("editing the rack after reopening", p is not None and p.editing)
    if p is None:
        return
    shown = (p.type.currentText(), p.rack_size.currentText(), p.rack_length.value())
    h.check("rack by length 50 remembered", shown == ("Rack", "Length", 50.0), shown)
    h.check("Size by Number of Teeth", ui.choose(p.rack_size, "Number of Teeth"))


def rack_teeth():
    p = panel()
    h.check("the whole teeth the 50 mm rack held: 7", near(p.teeth.value(), 7.0), p.teeth.value())
    ui.type_into(p.teeth.widget, "12")


rack_teeth.wait_ms = 1500


def rack_ok():
    rack = area(type="rack", teeth=12) * 10.0
    expected = s["internal"] + rack + s["english"]
    h.check("12-tooth rack", near(vol(), expected), (vol(), expected))
    h.task_button("OK")


rack_ok.wait_ms = 2000


def rack_kept():
    h.check("dialog closed", pi.no_dialog())
    rack = area(type="rack", teeth=12) * 10.0
    h.check("kept", near(vol(), s["internal"] + rack + s["english"]), vol())
    h.check("still three gears", len(pi.bodies()) == 3)
    h.fit()
    h.shot("4-reopened")


h.run(
    "gear_types",
    [
        new_design,
        i_plane,
        i_centre,
        i_type,
        i_internal,
        i_forty,
        i_kept,
        r_plane,
        r_centre,
        r_type,
        r_rack,
        r_ten,
        r_length,
        r_fifty,
        r_kept,
        e_plane,
        e_centre,
        e_spur,
        e_english,
        e_dp,
        e_teeth,
        e_symmetric,
        e_check,
        e_kept,
        save,
        close,
        reopen,
        reopened,
        rack_editing,
        rack_teeth,
        rack_ok,
        rack_kept,
    ],
)
