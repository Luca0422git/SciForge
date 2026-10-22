# SPDX-License-Identifier: LGPL-2.1-or-later
"""A sketch's projected curves, a scaled sketch and a derived sketch stay what they were when
SciForge replaces, deletes or rebuilds the step they depend on (review of the "safe sketch
geometry resets" branch, 2026-10-22).

  A  Projected edges follow a deleted step (sciforge/sketch_external.py, delete.py). A 40 x 20
     box (its width a dimension), a FreeCAD Fillet r 2 on a bottom edge, Sketch2 on the
     Fillet's top face with the top front edge projected and a line ending on it. The Fillet
     clicked in the timeline, MODIFY > Delete (real input): Sketch2 sits on the Pad's top
     face AND its projected edge comes from the Pad (it froze as a "missing reference" copy
     of the deleted Fillet: ExternalGeometry is read-only in FreeCAD 1.1, the old setattr
     failed in silence). The box made 60 wide: the projected edge is 0..60 and the line's
     end follows it to x = 60. Saved and reopened: the same.
  B  Projected face edges follow an edited pattern (pattern.relink_dependents). A boss
     patterned 3 times along X (FreeCAD's LinearPattern), Sketch2 on the third copy's top
     face with Auto project; the pattern edited with its first copy suppressed (the
     LinearPattern is replaced by SciForge's own pattern step): the four projected edges
     come from the new pattern, a boss made 8 wide makes them 8 wide too.
  C  The same for Shell/Draft (shelling._repoint), Sweep/Loft (curves.relink_users) and
     Revolve (revolve._relink_users), with a projected edge and a projected end-on edge (a
     point, whose reference FreeCAD 1.1.4 does not hand to Python): both come from the new
     step, the constraints on them kept.
  S  A sketch Scale step with a dimension that follows a parameter (scale.py): scaled 2x,
     edited to 3x, deleted: every curve is back exactly where it was (it was 4-7 mm off:
     the scale back was another scale and solve); scaled again, saved, reopened, deleted:
     back exactly.
  D  Derive of a sketch with an ellipse and a B-spline with their helper curves
     (derive.py): the derived helpers keep their roles (the foci and knot points became
     plain construction points) and the source's InternalAlignment constraints (none were
     copied), over an update too.
"""

import os
import tempfile

import FreeCAD as App

from SciForgeTests.gui import bodies_steps as b
from SciForgeTests.gui import harness as h

V = App.Vector
s = {}


def _rect(body, sketch_name, pts, support):
    import Part
    import Sketcher

    sketch = body.newObject("Sketcher::SketchObject", sketch_name)
    sketch.AttachmentSupport = support
    sketch.MapMode = "FlatFace"
    for i in range(4):
        sketch.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % 4]), False)
    for i in range(4):
        sketch.addConstraint(Sketcher.Constraint("Coincident", i, 2, (i + 1) % 4, 1))
    return sketch


def _box_sketch(body, x0, y0, x1, y1):
    """A fully constrained rectangle on XY; returns (sketch, index of its width)."""
    import Sketcher

    pts = [V(x0, y0, 0), V(x1, y0, 0), V(x1, y1, 0), V(x0, y1, 0)]
    sketch = _rect(body, "Sketch", pts, [(body.Origin.OriginFeatures[3], "")])
    for c in (("Horizontal", 0), ("Horizontal", 2), ("Vertical", 1), ("Vertical", 3)):
        sketch.addConstraint(Sketcher.Constraint(*c))
    sketch.addConstraint(Sketcher.Constraint("DistanceX", -1, 1, 0, 1, x0))
    sketch.addConstraint(Sketcher.Constraint("DistanceY", -1, 1, 0, 1, y0))
    width = sketch.addConstraint(Sketcher.Constraint("DistanceX", 0, 1, 0, 2, x1 - x0))
    sketch.addConstraint(Sketcher.Constraint("DistanceY", 1, 1, 1, 2, y1 - y0))
    return sketch, width


def _externals(sketch):
    return [(o.Name, tuple(subs)) for o, subs in sketch.ExternalGeometry]


def _ext_x(sketch, k=2):
    geos = sketch.ExternalGeo
    if len(geos) <= k:
        return None
    g = geos[k]
    return (round(g.StartPoint.x, 6), round(g.EndPoint.x, 6))


# -- A: Delete a fillet a sketch projects from ------------------------------------------------
def a_build():
    import Part
    import Sketcher

    doc = App.ActiveDocument
    body = doc.addObject("PartDesign::Body", "Body")
    sketch, width = _box_sketch(body, 0, 0, 40, 20)
    pad = body.newObject("PartDesign::Pad", "Pad")
    pad.Profile = sketch
    pad.Length = 10
    doc.recompute()
    bottom = [
        i
        for i, e in enumerate(pad.Shape.Edges, 1)
        if e.BoundBox.ZLength < 1e-6
        and abs(e.BoundBox.ZMin) < 1e-6
        and abs(e.BoundBox.YMin - 20) < 1e-6
    ][0]
    fillet = body.newObject("PartDesign::Fillet", "Fillet")
    fillet.Base = (pad, ["Edge%d" % bottom])
    fillet.Radius = 2
    doc.recompute()
    top = [
        i
        for i, f in enumerate(fillet.Shape.Faces, 1)
        if abs(f.BoundBox.ZMin - 10) < 1e-6 and f.BoundBox.ZLength < 1e-6
    ][0]
    edge = [
        i
        for i, e in enumerate(fillet.Shape.Edges, 1)
        if abs(e.BoundBox.ZMin - 10) < 1e-6
        and e.BoundBox.ZLength < 1e-6
        and abs(e.BoundBox.YMax) < 1e-6
        and e.BoundBox.XLength > 39
    ][0]
    s2 = body.newObject("Sketcher::SketchObject", "Sketch2")
    s2.AttachmentSupport = [(fillet, "Face%d" % top)]
    s2.MapMode = "FlatFace"
    doc.recompute()
    s2.addExternal("Fillet", "Edge%d" % edge, True, False)
    doc.recompute()
    line = s2.addGeometry(Part.LineSegment(V(0, 0, 0), V(10, 5, 0)), False)
    s2.addConstraint(Sketcher.Constraint("Coincident", line, 1, -3, 2))
    doc.recompute()
    s.update(a_sketch=sketch, a_width=width, a_pad=pad, a_fillet=fillet, a_s2=s2)
    h.check("A projected from the Fillet", _externals(s2) == [("Fillet", ("Edge%d" % edge,))])
    h.check("A the projected edge is 0..40", _ext_x(s2) == (0.0, 40.0), _ext_x(s2))
    h.check("A the line starts on its end", (s2.Geometry[0].StartPoint - V(40, 0, 0)).Length < 1e-6)
    h.fit()


def a_select():
    h.click_empty()
    b.click_timeline(s["a_fillet"])


def a_delete():
    h.check("A the Fillet is selected", b.selected_names() == ["Fillet"], b.selected_names())
    b.menu("MODIFY", "Delete")


a_delete.wait_ms = 1500


def _a_follows(where):
    doc = App.ActiveDocument
    s2 = doc.getObject("Sketch2")
    h.check(
        "%s: Sketch2 sits on the Pad" % where,
        [o.Name for o, _subs in s2.AttachmentSupport] == ["Pad"],
        s2.AttachmentSupport,
    )
    h.check(
        "%s: its projected edge comes from the Pad (not a frozen copy)" % where,
        [n for n, _subs in _externals(s2)] == ["Pad"],
        _externals(s2),
    )
    h.check(
        "%s: the line still ends on the projected edge" % where,
        [(c.Type, c.First, c.FirstPos, c.Second, c.SecondPos) for c in s2.Constraints]
        == [("Coincident", 0, 1, -3, 2)],
        [(c.Type, c.First, c.Second) for c in s2.Constraints],
    )
    return s2


def a_deleted():
    doc = App.ActiveDocument
    h.check("A the Fillet is gone", doc.getObject("Fillet") is None)
    s2 = _a_follows("A after Delete")
    h.check("A the projected edge is 0..40", _ext_x(s2) == (0.0, 40.0), _ext_x(s2))
    doc.openTransaction("Width")
    s["a_sketch"].setDatum(s["a_width"], App.Units.Quantity("60 mm"))
    doc.commitTransaction()
    doc.recompute()
    h.check("A the projected edge follows the part to 0..60", _ext_x(s2) == (0.0, 60.0), _ext_x(s2))
    h.check(
        "A the line's start follows it to x = 60",
        (s2.Geometry[0].StartPoint - V(60, 0, 0)).Length < 1e-6,
        s2.Geometry[0].StartPoint,
    )
    h.check("A Sketch2 is fine", "Invalid" not in s2.State and "Error" not in s2.State, s2.State)


def a_reopen():
    doc = App.ActiveDocument
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-follow-"), "follow.FCStd")
    doc.saveAs(path)
    App.closeDocument(doc.Name)
    doc = App.openDocument(path)
    doc.recompute()
    s2 = _a_follows("A reopened")
    h.check("A reopened: the projected edge is 0..60", _ext_x(s2) == (0.0, 60.0), _ext_x(s2))
    App.closeDocument(doc.Name)


# -- B: a pattern edited into SciForge's own pattern step --------------------------------------
def b_pattern():
    import Part
    import Sketcher

    from sciforge import pattern, sketch_auto_project

    doc = App.newDocument("FollowPattern")
    body = doc.addObject("PartDesign::Body", "Body")
    xy = body.Origin.OriginFeatures[3]
    base = body.newObject("PartDesign::Pad", "Pad")
    pts = [V(0, 0, 0), V(60, 0, 0), V(60, 20, 0), V(0, 20, 0)]
    base.Profile = _rect(body, "Sketch", pts, [(xy, "")])
    base.Length = 5
    doc.recompute()
    boss_sketch, width = _box_sketch(body, 2, 2, 7, 7)
    boss_sketch.AttachmentOffset = App.Placement(V(0, 0, 5), App.Rotation())
    boss = body.newObject("PartDesign::Pad", "Boss")
    boss.Profile = boss_sketch
    boss.Length = 5
    doc.recompute()
    options = {
        "pattern_type": "features",
        "objects": [(boss, "")],
        "direction": (body.Origin.OriginFeatures[0], ""),
        "quantity": 3,
        "distance": 20,
        "distribution": "spacing",
    }
    pat = pattern.build("rectangular", options)
    doc.recompute()
    face = [
        i
        for i, f in enumerate(pat.Shape.Faces, 1)
        if abs(f.BoundBox.ZMin - 10) < 1e-6 and f.BoundBox.ZLength < 1e-6 and f.BoundBox.XMin > 40
    ][0]
    s2 = body.newObject("Sketcher::SketchObject", "Sketch2")
    s2.AttachmentSupport = [(pat, "Face%d" % face)]
    s2.MapMode = "FlatFace"
    doc.recompute()
    sketch_auto_project.auto_project(s2, (pat, "Face%d" % face))
    line = s2.addGeometry(Part.LineSegment(V(0, 0, 0), V(3, 3, 0)), False)
    s2.addConstraint(Sketcher.Constraint("Coincident", line, 1, -3, 1))
    doc.recompute()
    h.check("B four projected edges", len(s2.ExternalGeo) == 6, len(s2.ExternalGeo))
    auto_before = list(getattr(s2, sketch_auto_project.PROPERTY, []))
    edited = dict(options)
    edited["suppressed"] = [0]
    doc.openTransaction("Edit Pattern")
    new = pattern.build("rectangular", edited, feature=pat)
    doc.commitTransaction()
    doc.recompute()
    h.check("B the pattern was replaced", new.Name != "RectangularPattern", new.Name)
    h.check(
        "B the projected edges come from the new pattern",
        [n for n, _subs in _externals(s2)] == [new.Name],
        _externals(s2),
    )
    h.check("B still four projected edges", len(s2.ExternalGeo) == 6, len(s2.ExternalGeo))
    auto_after = list(getattr(s2, sketch_auto_project.PROPERTY, []))
    h.check(
        "B Auto project's record follows the new curves",
        len(auto_after) == len(auto_before) and auto_after != auto_before,
        (auto_before, auto_after),
    )
    h.check(
        "B the line still starts on a projected corner",
        [(c.Type, c.First, c.Second) for c in s2.Constraints] == [("Coincident", 0, -3)],
        [(c.Type, c.First, c.Second) for c in s2.Constraints],
    )
    boss_sketch.setDatum(width, App.Units.Quantity("8 mm"))
    doc.recompute()
    xs = sorted({round(x, 6) for g in s2.ExternalGeo[2:] for x in (g.StartPoint.x, g.EndPoint.x)})
    h.check("B the projected edges follow the 8 mm boss (x 42..50)", xs == [42.0, 50.0], xs)
    h.check("B Sketch2 is fine", "Invalid" not in s2.State and "Error" not in s2.State, s2.State)
    App.closeDocument(doc.Name)


# -- C: the other helpers that move later steps to a new step ----------------------------------
def _c_setup(tag):
    import Part
    import Sketcher

    doc = App.newDocument("Follow" + tag)
    body = doc.addObject("PartDesign::Body", "Body")
    pts = [V(0, 0, 0), V(40, 0, 0), V(40, 20, 0), V(0, 20, 0)]
    sketch = _rect(body, "Sketch", pts, [(body.Origin.OriginFeatures[3], "")])
    old = body.newObject("PartDesign::Pad", "Old")
    old.Profile = sketch
    old.Length = 10
    doc.recompute()
    top = [
        i
        for i, f in enumerate(old.Shape.Faces, 1)
        if abs(f.BoundBox.ZMin - 10) < 1e-6 and f.BoundBox.ZLength < 1e-6
    ][0]
    edge = [  # the top front edge (a line in the sketch)
        i
        for i, e in enumerate(old.Shape.Edges, 1)
        if abs(e.BoundBox.ZMin - 10) < 1e-6
        and e.BoundBox.ZLength < 1e-6
        and abs(e.BoundBox.YMax) < 1e-6
    ][0]
    upright = [  # the vertical edge at (40, 20): a point in the sketch
        i
        for i, e in enumerate(old.Shape.Edges, 1)
        if e.BoundBox.ZLength > 9
        and abs(e.BoundBox.XMin - 40) < 1e-6
        and abs(e.BoundBox.YMin - 20) < 1e-6
    ][0]
    s2 = body.newObject("Sketcher::SketchObject", "S2")
    s2.AttachmentSupport = [(old, "Face%d" % top)]
    s2.MapMode = "FlatFace"
    doc.recompute()
    s2.addExternal("Old", "Edge%d" % edge, True, False)
    s2.addExternal("Old", "Edge%d" % upright, False, False)
    doc.recompute()
    a = s2.addGeometry(Part.LineSegment(V(5, 5, 0), V(10, 8, 0)), False)
    s2.addConstraint(Sketcher.Constraint("Coincident", a, 1, -3, 2))  # on the edge's end
    s2.addConstraint(Sketcher.Constraint("Coincident", a, 2, -4, 1))  # on the point
    doc.recompute()
    new = body.newObject("PartDesign::Pad", "New")  # the same box, built on the old one
    new.Profile = sketch
    new.Length = 10
    doc.recompute()
    return doc, old, new, s2


def c_helpers():
    from sciforge import curves, revolve, shelling

    cases = (
        ("Shell/Draft", lambda old, new: shelling._repoint(old, new)),
        ("Sweep/Loft", lambda old, new: curves.relink_users(old, new)),
        ("Revolve", lambda old, new: revolve._relink_users(old, new, list(old.InList))),
    )
    for tag, fn in cases:
        doc, old, new, s2 = _c_setup(tag.replace("/", ""))
        cons = [(c.Type, c.First, c.FirstPos, c.Second, c.SecondPos) for c in s2.Constraints]
        points = [
            (round(g.X, 6), round(g.Y, 6))
            for g in s2.ExternalGeo[2:]
            if g.TypeId == "Part::GeomPoint"
        ]
        h.check("C %s: one projected point at (40, 20)" % tag, points == [(40.0, 20.0)], points)
        fn(old, new)
        doc.recompute()
        h.check(
            "C %s: the attachment moved to the new step" % tag,
            [o.Name for o, _subs in s2.AttachmentSupport] == ["New"],
            s2.AttachmentSupport,
        )
        h.check(
            "C %s: both projections come from the new step" % tag,
            [n for n, subs in _externals(s2) for _sub in subs] == ["New", "New"],
            _externals(s2),
        )
        h.check(
            "C %s: the constraints on them are kept" % tag,
            [(c.Type, c.First, c.FirstPos, c.Second, c.SecondPos) for c in s2.Constraints] == cons,
            [(c.Type, c.First, c.FirstPos, c.Second, c.SecondPos) for c in s2.Constraints],
        )
        h.check("C %s: two projected curves" % tag, len(s2.ExternalGeo) == 4, len(s2.ExternalGeo))
        App.closeDocument(doc.Name)


# -- S: a sketch Scale step with a dimension that follows a parameter ---------------------------
def _s_sketch(doc):
    import Part
    import Sketcher

    from sciforge import parameters

    body = doc.addObject("PartDesign::Body", "Body")
    sketch = body.newObject("Sketcher::SketchObject", "Sketch")
    pts = [V(10, 10, 0), V(50, 10, 0), V(50, 30, 0), V(10, 30, 0)]
    for i in range(4):
        sketch.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % 4]), False)
    for i in range(4):
        sketch.addConstraint(Sketcher.Constraint("Coincident", i, 2, (i + 1) % 4, 1))
    for c in (("Horizontal", 0), ("Horizontal", 2), ("Vertical", 1), ("Vertical", 3)):
        sketch.addConstraint(Sketcher.Constraint(*c))
    width = sketch.addConstraint(Sketcher.Constraint("DistanceX", 0, 1, 0, 2, 40))
    sketch.addConstraint(Sketcher.Constraint("DistanceY", 1, 1, 1, 2, 20))
    parameters.add_user(doc, "w", "mm", "40")
    sketch.setExpression(".Constraints[%d]" % width, "Parameters.w")
    doc.recompute()
    return sketch


def _corners(sketch):
    return [(round(g.StartPoint.x, 6), round(g.StartPoint.y, 6)) for g in sketch.Geometry]


def s_scale():
    from sciforge import scale

    doc = App.newDocument("FollowScale")
    sketch = _s_sketch(doc)
    start = _corners(sketch)
    doc.openTransaction("Scale")
    record, kept = scale.make_sketch_scale(doc, [sketch], 2.0)
    doc.commitTransaction()
    doc.recompute()
    h.check("S the width follows a parameter: kept", len(kept) == 1, kept)
    h.check("S scaled", _corners(sketch) != start, _corners(sketch))
    doc.openTransaction("Edit Scale")
    scale.edit_sketch_scale(record, 3.0)
    doc.commitTransaction()
    doc.recompute()
    h.check("S edited to 3x: 60 high", abs(sketch.Geometry[1].length() - 60) < 1e-6)
    doc.openTransaction("Delete")
    doc.removeObject(record.Name)  # (the timeline's Delete; the watcher scales back)
    doc.commitTransaction()
    doc.recompute()
    h.check(
        "S deleted: every curve back where it was",
        _corners(sketch) == start,
        (_corners(sketch), start),
    )
    # again, then saved, reopened and deleted
    doc.openTransaction("Scale")
    record, _kept = scale.make_sketch_scale(doc, [sketch], 2.0)
    doc.commitTransaction()
    doc.recompute()
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-follow-scale-"), "scale.FCStd")
    doc.saveAs(path)
    App.closeDocument(doc.Name)
    doc = App.openDocument(path)
    sketch = doc.getObject("Sketch")
    record = [o for o in doc.Objects if scale.is_sketch_scale(o)][0]
    doc.openTransaction("Delete")
    doc.removeObject(record.Name)
    doc.commitTransaction()
    doc.recompute()
    h.check(
        "S reopened, deleted: every curve back where it was",
        _corners(sketch) == start,
        (_corners(sketch), start),
    )
    App.closeDocument(doc.Name)


# -- D: Derive keeps the helper curves' roles ---------------------------------------------------
def d_derive():
    import Part
    import Sketcher

    from sciforge import derive

    src = App.newDocument("FollowSource")
    body = src.addObject("PartDesign::Body", "Body")
    sketch = body.newObject("Sketcher::SketchObject", "Curves")
    sketch.addGeometry(Part.LineSegment(V(0, 0, 0), V(40, 0, 0)), False)
    sketch.addGeometry(Part.Point(V(10, 5, 0)), True)
    ellipse = sketch.addGeometry(Part.Ellipse(V(80, 10, 0), V(70, 14, 0), V(70, 10, 0)), False)
    sketch.exposeInternalGeometry(ellipse)
    spline = Part.BSplineCurve()
    spline.buildFromPoles([V(0, 40, 0), V(10, 55, 0), V(25, 35, 0), V(40, 50, 0)])
    sketch.exposeInternalGeometry(sketch.addGeometry(spline, False))
    src.recompute()
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-follow-derive-"), "source.FCStd")
    src.saveAs(path)

    def roles(sk):
        return [
            (f.Geometry.TypeId, bool(f.Construction), f.Id, f.InternalType)
            for f in sk.GeometryFacadeList
        ]

    def internal(sk):
        return sum(1 for c in sk.Constraints if c.Type == "InternalAlignment")

    want = roles(sketch)
    h.check(
        "D the source has foci and knot points",
        sum(1 for r in want if r[3] in ("EllipseFocus1", "EllipseFocus2", "BSplineKnotPoint")) >= 4,
        want,
    )
    data = derive.read_source(path)
    keys = [k for k in data["items"] if k.startswith("sketch:")]
    dst = App.newDocument("FollowDerived")
    master = derive.derive(dst, data, keys)
    dst.recompute()
    made = [o for o in dst.Objects if o.TypeId == "Sketcher::SketchObject"]
    if not h.check("D the sketch is derived", len(made) == 1, made):
        return
    derived = made[0]
    got = roles(derived)
    h.check("D every curve keeps its id, construction flag and role", got == want, (got, want))
    h.check(
        "D the helpers stay tied to their curve (InternalAlignment)",
        internal(derived) == internal(sketch) > 0,
        (internal(derived), internal(sketch)),
    )
    derived.solve()
    loose = sorted({g for g, _p in derived.getGeometryWithDependentParameters()})
    h.check("D only the plain construction point is free", loose == [1], loose)
    h.check(
        "D the derived sketch is fine",
        not derived.ConflictingConstraints and not derived.RedundantConstraints,
    )
    derive.update(master)
    dst.recompute()
    h.check(
        "D over an update: the same",
        roles(derived) == want and internal(derived) == internal(sketch),
    )
    App.closeDocument(dst.Name)
    App.closeDocument(src.Name)


h.run(
    "sketch_geometry_follow",
    [b.new_design("SketchGeometryFollow"), a_build, a_select, a_delete, a_deleted, a_reopen]
    + [b_pattern, c_helpers, s_scale, d_derive],
)
