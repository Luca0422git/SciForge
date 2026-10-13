# SPDX-License-Identifier: LGPL-2.1-or-later
"""Insert STEP (INSERT menu), only real input.

Fixture: two_parts.step, "Plate" 40 x 30 x 5 (blue) and "Peg" radius 5, height 15 (red).

A  INSERT > Insert STEP: two bodies "Plate" (6000 mm3) and "Peg" (1178.1 mm3), listed in the
   browser, "Insert STEP 1/2" in the timeline, nothing else left from the file (no container);
   Plate blue and Peg red, as a SciForge Appearance and on screen.
B  Ctrl+Z: no bodies. Ctrl+Y: both again, still coloured.
C  The same file again: two more bodies, "Plate (2)" and "Peg (2)".
D  The imported bodies work like any body: Create Sketch on the Plate's top face puts a
   sketch into the body "Plate".
"""

import FreeCAD as App

from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import insert_steps as i

V = App.Vector
BLUE = (0.2, 0.4, 0.9)
RED = (0.9, 0.3, 0.2)


def same(a, c, tol=0.02):
    return a is not None and all(abs(x - y) <= tol for x, y in zip(a, c))


def look_of(body):
    from sciforge import appearance

    data = appearance.get(body)
    look = data.get("body")
    return tuple(look["color"]) if look else None


def screen_colour(body):
    try:
        return tuple(round(c, 3) for c in body.Tip.ViewObject.ShapeAppearance[0].DiffuseColor[:3])
    except Exception:
        return None


def body_named(label):
    return s.body_named(label)


# -- A ----------------------------------------------------------------------------------------
def a_insert():
    i.use_file(i.fixture("two_parts.step"))
    i.menu("INSERT", "Insert STEP")


a_insert.wait_ms = 1500


def a_check():
    bodies = s.bodies()
    h.check("two bodies", len(bodies) == 2, [x.Label for x in bodies])
    plate, peg = body_named("Plate"), body_named("Peg")
    h.check(
        "Plate 6000 mm3",
        plate is not None and i.close(s.volume(plate), i.PLATE_VOLUME),
        plate and s.volume(plate),
    )
    h.check(
        "Peg 1178.1 mm3",
        peg is not None and i.close(s.volume(peg), i.PEG_VOLUME, 1e-4),
        peg and s.volume(peg),
    )
    doc = App.ActiveDocument
    leftovers = [
        o.Name for o in doc.Objects if o.TypeId in ("App::Part", "App::Link", "App::LinkGroup")
    ]
    h.check("nothing left from the file's structure", not leftovers, leftovers)
    h.check(
        "browser lists Plate and Peg",
        i.browser_has("Plate") and i.browser_has("Peg"),
        i.browser_labels(),
    )
    if plate is not None and peg is not None:
        titles = [s.timeline_title_of(plate.Tip), s.timeline_title_of(peg.Tip)]
        h.check(
            "timeline: Insert STEP 1 and 2", titles == ["Insert STEP 1", "Insert STEP 2"], titles
        )
        h.check("Plate is blue (appearance)", same(look_of(plate), BLUE), look_of(plate))
        h.check("Peg is red (appearance)", same(look_of(peg), RED), look_of(peg))
        h.check("Plate blue on screen", same(screen_colour(plate), BLUE), screen_colour(plate))
        h.check("Peg red on screen", same(screen_colour(peg), RED), screen_colour(peg))
    s.no_popups("Insert STEP")


# -- B ----------------------------------------------------------------------------------------
def b_undo():
    i.undo()


def b_check_undo():
    h.check("Ctrl+Z: no bodies", len(s.bodies()) == 0, [x.Label for x in s.bodies()])


def b_redo():
    i.redo()


def b_check_redo():
    bodies = s.bodies()
    h.check("Ctrl+Y: two bodies", len(bodies) == 2, [x.Label for x in bodies])
    plate = body_named("Plate")
    h.check(
        "still blue", plate is not None and same(look_of(plate), BLUE), plate and look_of(plate)
    )


# -- C ----------------------------------------------------------------------------------------
def c_again():
    i.menu("INSERT", "Insert STEP")


c_again.wait_ms = 1500


def c_check():
    labels = sorted(x.Label for x in s.bodies())
    h.check(
        "four bodies, the new ones numbered",
        labels == ["Peg", "Peg (2)", "Plate", "Plate (2)"],
        labels,
    )


# -- D ----------------------------------------------------------------------------------------
def d_sketch():
    h.fit()
    h.ribbon("Create Sketch")


def d_click_plate():
    # the first Plate's top face, away from the peg (both inserts lie on top of each other:
    # the second file's bodies hide... so hide them first, like a person would)
    for label in ("Plate (2)", "Peg (2)"):
        body = body_named(label)
        if body is not None:
            body.ViewObject.Visibility = False
    h.fit()
    h.click(V(8, 8, 5))


def d_check():
    sketch = h.in_sketch()
    h.check("a sketch opened on the plate", sketch is not None)
    plate = body_named("Plate")
    if sketch is not None and plate is not None:
        h.check("in the body Plate", sketch in plate.Group, [o.Label for o in plate.Group])
    i.no_file()


def d_finish():
    if h.in_sketch() is not None:
        h.ribbon("Finish Sketch")
    h.shot("end")


h.run(
    "insert_step",
    [
        i.new_design("InsertStep"),
        a_insert,
        a_check,
        b_undo,
        b_check_undo,
        b_redo,
        b_check_redo,
        c_again,
        c_check,
        d_sketch,
        d_click_plate,
        d_check,
        d_finish,
    ],
)
