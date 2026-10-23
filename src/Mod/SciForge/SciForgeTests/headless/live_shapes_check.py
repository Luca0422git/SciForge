# SPDX-License-Identifier: LGPL-2.1-or-later
"""The live pictures of Press Pull, Shell and Extrude (sciforge/live_shapes.py) against the
exact solids, in real FreeCAD without a window: every point of a picture (its triangles' and
its lines' points) must lie on the solid the dialog builds for the same value.

    freecadcmd -c "from SciForgeTests.headless import live_shapes_check; live_shapes_check.main()"

Prints one line per case: "[SciForge] live check <label>: worst <mm> over <n> points" and at
the end "[SciForge] live check done <cases>". SciForgeTests/unit/test_live_shapes_freecad.py
runs it when it finds FreeCAD (run_tests.sh gives SCIFORGE_FC_CMD) and checks the lines.
"""

import FreeCAD as App
import Part

V = App.Vector


def _report(label, pic, values, exact):
    faces, lines = pic.points_at(values)
    pts = faces + lines
    worst = max([exact.distToShape(Part.Vertex(V(*q)))[0] for q in pts] or [1e9])
    print("[SciForge] live check %s: worst %.9f over %d points" % (label, worst, len(pts)))
    return 1


def _names(shape, pred):
    return ["Face%d" % i for i, f in enumerate(shape.Faces, 1) if pred(f)]


def press_pull_cases():
    from sciforge import live_shapes as ls
    from sciforge import presspull_core as ppc

    n = 0
    box = Part.makeBox(20, 10, 5)
    top = _names(box, lambda f: f.CenterOfMass.z > 4.9)
    side = _names(box, lambda f: f.CenterOfMass.x > 19.9)
    blind = box.cut(Part.makeCylinder(3, 3, V(10, 5, 2)))
    wall = _names(blind, lambda f: f.Surface.__class__.__name__ == "Cylinder")
    floor = _names(blind, lambda f: abs(f.CenterOfMass.z - 2.0) < 1e-6)
    through = box.cut(Part.makeCylinder(3, 5, V(10, 5, 0)))
    hole = _names(through, lambda f: f.Surface.__class__.__name__ == "Cylinder")
    poly = Part.makePolygon([V(0, 0, 0), V(20, 0, 0), V(15, 0, 10), V(0, 0, 10), V(0, 0, 0)])
    wedge = Part.Face(poly).extrude(V(0, 10, 0))  # a sloping side
    wedge_top = _names(wedge, lambda f: f.CenterOfMass.z > 9.9)
    placed = box.copy()
    placed.Placement = App.Placement(V(5, -3, 2), App.Rotation(V(1, 1, 0), 30))
    placed_top = _names(placed, lambda f: f.normalAt(0, 0).getAngle(V(0, 0, 1)) < 0.6)
    cases = [
        ("box top", box, top, (3.0, -2.0)),
        ("box top and side", box, top + side, (3.0, -2.0)),
        ("blind hole wall", blind, wall, (1.0, -1.0, 2.5)),
        ("blind hole floor", blind, floor, (1.0, -1.0)),
        ("through hole wall", through, hole, (1.0, -1.0)),
        ("wedge top beside a slope", wedge, wedge_top, (2.0, -2.0)),
        ("a turned box", placed, placed_top, (2.0, -1.0)),
    ]
    for label, shape, names, values in cases:
        pic = ls.OffsetPicture(shape, names)
        for d in values:
            exact = ppc.press_pull(shape, [shape.getElement(x) for x in names], d)
            n += _report("press pull %s %+g" % (label, d), pic, {"distance": d}, exact)
    # a placement (the body's) is applied to the picture's points
    place = App.Placement(V(10, 20, 30), App.Rotation(V(0, 0, 1), 40))
    pic = ls.OffsetPicture(box, top, place)
    exact = ppc.press_pull(box, [box.getElement(x) for x in top], 2.0)
    exact.Placement = place.multiply(exact.Placement)
    n += _report("press pull in a moved body", pic, {"distance": 2.0}, exact)
    return n


def shell_cases():
    from sciforge import live_shapes as ls
    from sciforge import shelling

    n = 0
    box = Part.makeBox(20, 10, 5)
    top = _names(box, lambda f: f.CenterOfMass.z > 4.9)
    front = _names(box, lambda f: f.CenterOfMass.y < 0.1)
    cup = Part.makeCylinder(5, 10)
    cup_top = _names(cup, lambda f: f.CenterOfMass.z > 9.9)
    cases = [
        ("box open top", box, top, ("inside", "outside", "both"), (1.0, 1.5), (0.6, 0.4)),
        ("box open top and front", box, top + front, ("inside", "outside", "both"), (1.0, 1.5)),
        ("box hollow", box, [], ("inside",), (1.0, 0.0), (0.5, 0.0)),
        ("a cylinder open at the top", cup, cup_top, ("inside", "outside"), (1.0, 0.8)),
    ]
    for label, shape, names, directions, *walls in cases:
        for direction in directions:
            pic = ls.ShellPicture(shape, names, direction)
            for inside, outside in walls:
                opts = dict(
                    shelling.default_options(), direction=direction, inside=inside, outside=outside
                )
                exact = shelling.build(shape, names, opts)
                n += _report(
                    "shell %s %s %g/%g" % (label, direction, inside, outside), pic, opts, exact
                )
    return n


def extrude_cases():
    from sciforge import extrude
    from sciforge import live_shapes as ls

    doc = App.newDocument("LiveShapesCheck")
    body = doc.addObject("PartDesign::Body", "Body")
    sk = body.newObject("Sketcher::SketchObject", "Sketch")
    pts = [V(0, 0, 0), V(20, 0, 0), V(20, 10, 0), V(0, 10, 0)]
    for i in range(4):
        sk.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % 4]))
    sk.addGeometry(Part.Circle(V(30, 5, 0), V(0, 0, 1), 3))
    doc.recompute()
    profiles = [(sk, "")]
    base = {"operation": "new_body"}
    cases = [
        ("one side", {"distance": 8}),
        ("one side down", {"distance": -8}),
        ("taper", {"distance": 8, "taper": 10}),
        ("taper down", {"distance": -8, "taper": 10}),
        ("symmetric whole", {"direction": "symmetric", "distance": 8}),
        ("symmetric taper", {"direction": "symmetric", "distance": 8, "taper": 5}),
        ("symmetric half", {"direction": "symmetric", "distance": 8, "measurement": "half"}),
        ("two sides", {"direction": "two_sides", "distance": 8, "distance2": 3}),
        (
            "two sides tapers",
            {"direction": "two_sides", "distance": 8, "distance2": 3, "taper": 5, "taper2": 8},
        ),
        ("start offset", {"start": "offset", "start_offset": 2, "distance": 5}),
        ("start offset down", {"start": "offset", "start_offset": 2, "distance": -5}),
        ("thin", {"thin": True, "distance": 6, "wall_thickness": 1}),
        ("thin centred", {"thin": True, "distance": 6, "wall_location": "center"}),
    ]
    n = 0
    for label, opts in cases:
        opts = dict(base, **opts)
        feat = extrude.build(profiles, opts, hide=False)
        doc.recompute()
        o = extrude.options_with_defaults(opts)
        sign = extrude._sign1(profiles, o)
        start = extrude.start_offset_of(profiles, o) * sign
        faces = extrude.section_faces(profiles, o)
        pic = ls.ExtrudePicture(faces, extrude.profile_normal(profiles) * sign)
        n += _report("extrude %s" % label, pic, {"ends": ls.extrude_ends(o, start)}, feat.Shape)
        extrude.remove(feat)
        doc.recompute()
    App.closeDocument(doc.Name)
    return n


def main():
    n = 0
    for part in (press_pull_cases, shell_cases, extrude_cases):
        try:
            n += part()
        except Exception as exc:
            print("[SciForge] live check ERROR %s: %s" % (part.__name__, exc))
    print("[SciForge] live check done %d" % n)
