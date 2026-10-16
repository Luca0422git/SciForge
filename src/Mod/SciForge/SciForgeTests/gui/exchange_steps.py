# SPDX-License-Identifier: LGPL-2.1-or-later
"""Shared helpers for the exchange-2 scenarios (scenarios/exchange2_*.py): the fixture files
are made with FreeCAD itself (a STEP assembly, a broken file, a SAT stand-in), and the
checks read the components, copies and bodies a file became.

The robot (robot.step), built as another CAD program would write it:

    Robot                       the file's top product
      Base                      a part: a 60 x 40 x 10 box at the origin, blue
      Drive                     an assembly at (30, 0, 5)
        Axle                    a part: a cylinder r 2, 50 long along Y from y = -5, grey
        Wheel                   a part at (0, -10, 0): a cylinder r 8, 5 thick along Y, red
        Wheel                   the same part again at (0, 45, 0), turned 180 degrees
"""

import math
import os

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import harness as h

V = App.Vector
BLUE = (0.2, 0.4, 0.9)
RED = (0.9, 0.3, 0.2)
GREY = (0.6, 0.6, 0.6)
BASE_VOLUME = 24000.0
AXLE_VOLUME = math.pi * 4 * 50
WHEEL_VOLUME = math.pi * 64 * 5
# where the bodies' middles are in the design (file) coordinates
BASE_CENTRE = (30.0, 20.0, 5.0)
AXLE_CENTRE = (30.0, 20.0, 5.0)
WHEEL_CENTRE = (30.0, -7.5, 5.0)
WHEEL2_CENTRE = (30.0, 42.5, 5.0)


def out(name):
    return os.path.join(h.OUT_DIR, name)


def make_robot(path):
    """Write robot.step (see the module's doc) with FreeCAD's STEP writer, colours kept."""
    import ImportGui
    import Part

    active = App.ActiveDocument.Name if App.ActiveDocument is not None else None
    doc = App.newDocument("RobotFixture")

    def part(name, shape, parent, colour):
        p = doc.addObject("App::Part", name)
        p.Label = name
        f = doc.addObject("Part::Feature", name + "Shape")
        f.Label = name
        f.Shape = shape
        f.ViewObject.ShapeColor = colour
        p.addObject(f)
        parent.addObject(p)
        return p

    robot = doc.addObject("App::Part", "Robot")
    robot.Label = "Robot"
    part("Base", Part.makeBox(60, 40, 10), robot, BLUE)
    drive = doc.addObject("App::Part", "Drive")
    drive.Label = "Drive"
    robot.addObject(drive)
    drive.Placement = App.Placement(V(30, 0, 5), App.Rotation())
    part("Axle", Part.makeCylinder(2, 50, V(0, -5, 0), V(0, 1, 0)), drive, GREY)
    wheel = part("Wheel", Part.makeCylinder(8, 5, V(0, 0, 0), V(0, 1, 0)), drive, RED)
    wheel.Placement = App.Placement(V(0, -10, 0), App.Rotation())
    link = doc.addObject("App::Link", "Wheel2")
    link.LinkedObject = wheel
    link.Label = "Wheel"
    link.Placement = App.Placement(V(0, 45, 0), App.Rotation(V(0, 0, 1), 180))
    drive.addObject(link)
    doc.recompute()
    ImportGui.export([robot], path)
    Gui.getDocument(doc.Name).Modified = False
    App.closeDocument(doc.Name)
    if active and active in App.listDocuments():
        App.setActiveDocument(active)
    return path


def make_bad_files():
    """A STEP file that is not one, and a SAT file (FreeCAD cannot read ACIS)."""
    broken = out("broken.step")
    with open(broken, "w") as handle:
        handle.write("ISO-10303-21;\nthis is not a STEP file\n")
    sat = out("bracket.sat")
    with open(sat, "w") as handle:
        handle.write("700 0 1 0\n")
    return broken, sat


def doc():
    return App.ActiveDocument


def comps(document=None):
    from sciforge import components

    return components.list_components(document or doc())


def comp(label, document=None):
    for c in comps(document):
        if c.Label == label:
            return c
    return None


def labels(document=None):
    return sorted(c.Label for c in comps(document))


def parent_label(obj):
    from sciforge import components

    container = components.container_of(obj)
    return container.Label if container is not None else None


def bodies_in(component, document=None):
    from sciforge import components

    return components.bodies_in(document or doc(), component)


def is_instance(component):
    from sciforge import instances

    return instances.is_instance(component)


def centre(body):
    """The middle of a body's solid where it stands in the design."""
    from sciforge import bodies

    box = bodies.global_shape(body).BoundBox
    return (box.Center.x, box.Center.y, box.Center.z)


def near3(a, b, tol=0.01):
    return a is not None and all(abs(x - y) <= tol for x, y in zip(a, b))


def near(a, b, tol=1e-3):
    return a is not None and abs(a - b) <= tol * max(1.0, abs(b))


def body_of(component_label, document=None):
    c = comp(component_label, document)
    found = bodies_in(c, document) if c is not None else []
    return found[0] if found else None


def look_of(body):
    from sciforge import appearance

    data = appearance.get(body)
    look = data.get("body")
    return tuple(look["color"]) if look else None


def same_colour(a, c, tol=0.02):
    return a is not None and all(abs(x - y) <= tol for x, y in zip(a, c))


def told():
    from sciforge import commands

    return commands._TOLD.get("msg") or ""


def use_open_file(path):
    from sciforge import exchange_ui

    exchange_ui.OPEN_PICKER = (lambda p=path: p) if path else None


def check_robot(prefix, document=None, top=None):
    """The robot's components, copies, bodies and where they are (P1, after reopening and
    after a STEP round trip)."""
    document = document or doc()
    found = labels(document)
    wanted = ["Axle", "Base", "Drive", "Wheel", "Wheel:2"] + ([top] if top else [])
    h.check("%s components %s" % (prefix, wanted), found == sorted(wanted), found)
    wheel2 = comp("Wheel:2", document)
    h.check("%s Wheel:2 is a copy of Wheel" % prefix, wheel2 is not None and is_instance(wheel2))
    for label in ("Axle", "Wheel", "Wheel:2"):
        c = comp(label, document)
        h.check(
            "%s %s is in Drive" % (prefix, label),
            c is not None and parent_label(c) == "Drive",
            c and parent_label(c),
        )
    drive = comp("Drive", document)
    h.check(
        "%s Drive is at the top%s" % (prefix, (" of " + top) if top else ""),
        drive is not None and parent_label(drive) == top,
        drive and parent_label(drive),
    )
    for label, volume, where in (
        ("Base", BASE_VOLUME, BASE_CENTRE),
        ("Axle", AXLE_VOLUME, AXLE_CENTRE),
        ("Wheel", WHEEL_VOLUME, WHEEL_CENTRE),
        ("Wheel:2", WHEEL_VOLUME, WHEEL2_CENTRE),
    ):
        body = body_of(label, document)
        h.check("%s %s has one body" % (prefix, label), body is not None)
        if body is None:
            continue
        h.check(
            "%s %s's body is %.1f mm3" % (prefix, label, volume),
            near(body.Shape.Volume, volume),
            body.Shape.Volume,
        )
        h.check(
            "%s %s's body stands where the file has it %s" % (prefix, label, where),
            near3(centre(body), where),
            centre(body),
        )
    base = body_of("Base", document)
    h.check("%s the base body is Body1" % prefix, base is not None and base.Label == "Body1")
