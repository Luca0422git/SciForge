# SPDX-License-Identifier: LGPL-2.1-or-later
"""The golden models' checks: steps that measure the design (or something about it) and
fail the model with the difference when it is off. They build nothing, so they live here
with the tests, not in SciForge's design steps (sciforge/ai/ops/). Registered on
builder.Builder when builder.py is imported. A pick ("ref") is as in
sciforge/ai/ops/inspect_ops.py.

  {"op": "expect_bodies", "bodies": {"e1": {"volume": 3500, "solids": 1}, ...},
   "used_up": ["e2"], "followers": {"x1": 1}, "steps": {"x1": 1}}
      Checks each body, the bodies a step uses up (hidden, Join merge), how many hidden
      follower steps an extrude has and how often it is listed in the timeline.

  {"op": "reopen_check", "bodies": {...as above...}}
      Saves the design, opens the file as a second design, recomputes it and checks the
      bodies there (the follower steps come back from the file).

  {"op": "expect_move_refused", "target": "e2", "after": "x1", "reason": "does not exist"}
      Dragging a step before / after another in the timeline is refused with that reason
      (a multi-body extrude moves with its hidden steps, core.Builder.op_move; only a move
      that would put it before a body it changes exists is refused).

  {"op": "construct_expect", "target": "p1", "point": [x, y, z],
   "normal": [x, y, z] | "direction": [x, y, z]}
      planes: point lies on the plane, normal either way round; axes: point on the line,
      direction either way round; points: the point itself
  {"op": "measure_expect", "a": ref, "b": ref, "distance": d, "angle": deg}
  {"op": "section_expect", "plane": ref, "distance": 0, "x_angle": 0, "y_angle": 0,
   "flip": false, "kept_volume": v, "cap_area": a}
  {"op": "com_expect", "features": ["e1"] (their bodies; none = every body), "point": [x, y, z]}
  {"op": "interference_expect", "features": ["e1", "e2"], "include_coincident": false,
   "volume": v, "pairs": n}
  {"op": "blend_radius_expect", "at": [x, y, z], "radius": r, "tol": 0.01}
      The round on a 90 degree edge passes (sqrt(2) - 1) R from the old corner `at`: the
      radius measured there must be `radius` (a Variable fillet's radius points).
  {"op": "expect_component", "step": "c1"}
      the step's body lies in a component of its own (operation new_component)
  {"op": "expect_radius", "step": "s1", "max": r, "min": r0}
      the step's body stays within `max` (and beyond `min`) of the Z axis
"""

import math
import os
import tempfile

import FreeCAD as App

from sciforge.ai.ops.extrude_bodies_ops import _body
from sciforge.ai.ops.inspect_ops import _bodies, _ref

from .builder import Builder, BuildError

V = App.Vector
TOL = 1e-6


def _close(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


def _check_body(where, body, want):
    problems = []
    shape = body.Shape
    volume = 0.0 if shape.isNull() else shape.Volume
    solids = 0 if shape.isNull() else len(shape.Solids)
    if "volume" in want and not _close(volume, want["volume"]):
        problems.append(
            "%s %s volume %.6g, expected %.6g" % (where, body.Label, volume, want["volume"])
        )
    if "solids" in want and solids != want["solids"]:
        problems.append(
            "%s %s has %d solids, expected %d" % (where, body.Label, solids, want["solids"])
        )
    if "valid" in want and not shape.isNull() and shape.isValid() != want["valid"]:
        problems.append("%s %s valid=%s" % (where, body.Label, shape.isValid()))
    return problems


def op_expect_bodies(self, step):
    from sciforge import bodies, extrude_bodies, timeline_ops

    problems = []
    for step_id, want in step.get("bodies", {}).items():
        problems += _check_body("", _body(self, step_id), want)
    used = bodies.consumed(self.doc)
    for step_id in step.get("used_up", []):
        body = _body(self, step_id)
        if body.Name not in used:
            problems.append("%s is not used up" % body.Label)
    for step_id, count in step.get("followers", {}).items():
        lead = self.objects.get(step_id)
        have = len(extrude_bodies.followers_of(lead)) if lead is not None else 0
        if have != count:
            problems.append("%s has %d follower steps, expected %d" % (step_id, have, count))
    if "steps" in step:
        names = timeline_ops.timeline(self.doc).names()
        for step_id, count in step["steps"].items():
            obj = self.objects.get(step_id)
            have = names.count(obj.Name) if obj is not None else 0
            if have != count:
                problems.append("timeline lists %s %d times, expected %d" % (step_id, have, count))
        helpers = [n for n in names if extrude_bodies.is_follower(self.doc.getObject(n))]
        if helpers:
            problems.append("follower steps listed in the timeline: %s" % helpers)
    for obj in self.doc.Objects:
        state = list(getattr(obj, "State", []))
        if extrude_bodies.is_follower(obj) and ("Invalid" in state or "Error" in state):
            problems.append("%s failed: %s" % (obj.Label, obj.getStatusString()))
    if problems:
        raise BuildError("expect_bodies: %s" % "; ".join(problems))


def op_reopen_check(self, step):
    import FreeCAD as App

    names = {step_id: _body(self, step_id).Name for step_id in step.get("bodies", {})}
    folder = tempfile.mkdtemp(prefix="sciforge-golden-")
    path = os.path.join(folder, "reopen.FCStd")
    self.doc.saveCopy(path)  # the design being built stays as it is (not renamed)
    copy = App.openDocument(path)
    try:
        copy.recompute()
        problems = []
        for step_id, want in step.get("bodies", {}).items():
            body = copy.getObject(names[step_id])
            if body is None:
                problems.append("%s is missing after reopening" % names[step_id])
                continue
            problems += _check_body("reopened", body, want)
        from sciforge import extrude_bodies

        broken = [
            o.Label
            for o in copy.Objects
            if extrude_bodies.is_follower(o) and "Invalid" in list(getattr(o, "State", []))
        ]
        if broken:
            problems.append("reopened followers failed: %s" % broken)
        missing = [
            o.Label for o in copy.Objects if extrude_bodies.is_follower(o) and o.Source is None
        ]
        if missing:
            problems.append("reopened followers lost their extrude: %s" % missing)
        if problems:
            raise BuildError("reopen_check: %s" % "; ".join(problems))
    finally:
        App.closeDocument(copy.Name)
        try:
            os.remove(path)
            os.rmdir(folder)
        except OSError:
            pass


def op_expect_move_refused(self, step):
    """Dragging `target` before `before` (or after `after`) in the timeline must be refused
    with the reason: a multi-body extrude cannot come before a body it changes exists."""
    from sciforge import timeline_ops

    name = self.objects[step["target"]].Name
    ref = step.get("before", step.get("after"))
    names = timeline_ops.timeline(self.doc).names()
    slot = names.index(self.objects[ref].Name) + (0 if "before" in step else 1)
    try:
        timeline_ops.move(self.doc, name, slot)
    except timeline_ops.TimelineError as exc:
        if step.get("reason", "") not in str(exc):
            raise BuildError("expect_move_refused: refused for another reason: %s" % exc)
        return
    raise BuildError("expect_move_refused: %s was moved" % step["target"])


def _parallel(a, b):
    a, b = V(a), V(b)
    a.normalize()
    b.normalize()
    return a.cross(b).Length < 1e-7


def op_construct_expect(self, step):
    datum = self.objects.get(step["target"])
    if datum is None or self.ops.get(step["target"]) != "construct":
        raise BuildError("construct_expect: %r is not a construct step" % step["target"])
    gp = datum.getGlobalPlacement()
    z = gp.Rotation.multVec(V(0, 0, 1))
    point = V(*step["point"])
    problems = []
    if datum.TypeId == "PartDesign::Plane":
        gap = abs((point - gp.Base).dot(z))
        if gap > TOL:
            problems.append("the point is %.6g from the plane" % gap)
        if "normal" in step and not _parallel(z, step["normal"]):
            problems.append("normal %s, expected %s" % (z, step["normal"]))
    elif datum.TypeId == "PartDesign::Line":
        gap = (point - gp.Base).cross(z).Length
        if gap > TOL:
            problems.append("the point is %.6g from the axis" % gap)
        if "direction" in step and not _parallel(z, step["direction"]):
            problems.append("direction %s, expected %s" % (z, step["direction"]))
    else:
        if (gp.Base - point).Length > TOL:
            problems.append("point at %s, expected %s" % (gp.Base, point))
    if problems:
        raise BuildError("construct_expect %r: %s" % (step["target"], "; ".join(problems)))


def op_measure_expect(self, step):
    from sciforge import measure

    a = _ref(self, step["a"], "measure_expect a")
    b = _ref(self, step["b"], "measure_expect b")
    try:
        r = measure.relation(measure.entity(*a), measure.entity(*b))
    except measure.MeasureError as exc:
        raise BuildError("measure_expect: %s" % exc)
    problems = []
    if "distance" in step and not _close(r["distance"], step["distance"]):
        problems.append("distance %.9g, expected %.9g" % (r["distance"], step["distance"]))
    if "angle" in step and (r["angle"] is None or not _close(r["angle"], step["angle"])):
        problems.append("angle %s, expected %.9g" % (r["angle"], step["angle"]))
    if problems:
        raise BuildError("measure_expect: %s" % "; ".join(problems))


def op_section_expect(self, step):
    from sciforge import section

    ref = _ref(self, step["plane"], "section_expect")
    try:
        place = section.cut_frame(
            ref,
            step.get("distance", 0.0),
            step.get("x_angle", 0.0),
            step.get("y_angle", 0.0),
            step.get("flip", False),
        )
    except section.SectionError as exc:
        raise BuildError("section_expect: %s" % exc)
    shape = self.body.Shape
    problems = []
    if "kept_volume" in step:
        kept = section.kept_volume(shape, place)
        if not _close(kept, step["kept_volume"]):
            problems.append("kept volume %.9g, expected %.9g" % (kept, step["kept_volume"]))
    if "cap_area" in step:
        area = sum(f.Area for f in section.cap_faces(shape, place))
        if not _close(area, step["cap_area"]):
            problems.append("cut face %.9g, expected %.9g" % (area, step["cap_area"]))
    if problems:
        raise BuildError("section_expect: %s" % "; ".join(problems))


def op_com_expect(self, step):
    from sciforge import analysis

    obj = analysis.make_com(self.doc, _bodies(self, step))
    self.doc.recompute()
    try:
        if "Invalid" in list(obj.State):
            raise BuildError("com_expect: %s" % obj.getStatusString())
        point = V(*step["point"])
        if (obj.Position - point).Length > TOL:
            raise BuildError("com_expect: centre at %s, expected %s" % (obj.Position, point))
    finally:
        self.doc.removeObject(obj.Name)


def op_interference_expect(self, step):
    from sciforge import analysis

    obj = analysis.make_interference(
        self.doc, _bodies(self, step), step.get("include_coincident", False)
    )
    self.doc.recompute()
    try:
        if "Invalid" in list(obj.State):
            raise BuildError("interference_expect: %s" % obj.getStatusString())
        found = analysis.results(obj)
        problems = []
        if "pairs" in step and len(found) != step["pairs"]:
            problems.append("%d pairs, expected %d" % (len(found), step["pairs"]))
        if "volume" in step:
            total = sum(v for _a, _b, v in found)
            if not _close(total, step["volume"]):
                problems.append("overlap %.9g, expected %.9g" % (total, step["volume"]))
        if problems:
            raise BuildError("interference_expect: %s" % "; ".join(problems))
    finally:
        self.doc.removeObject(obj.Name)


def op_blend_radius_expect(self, step):
    import FreeCAD as App
    import Part

    shape = self.body.Shape
    point = App.Vector(*step["at"])
    measured = shape.distToShape(Part.Vertex(point))[0] / (math.sqrt(2.0) - 1.0)
    if abs(measured - float(step["radius"])) > float(step.get("tol", 0.01)):
        raise BuildError(
            "blend_radius_expect at %s: radius %.4f, expected %g"
            % (step["at"], measured, step["radius"])
        )
    return None


def op_expect_component(self, step):
    """The step's body lies in a component of its own (Fusion's New Component), and that
    component holds nothing else."""
    from sciforge import components

    obj = self.objects.get(step["step"])
    body = obj.getParentGeoFeatureGroup() if obj is not None else None
    part = components.container_of(body) if body is not None else None
    if part is None:
        raise BuildError("expect_component: %r is not in a component" % step["step"])
    inside = [o.Label for o in part.Group if components.is_body(o) or components.is_component(o)]
    if inside != [body.Label]:
        raise BuildError("expect_component: %s holds %s" % (part.Label, inside))


def op_expect_radius(self, step):
    """The step's body stays within `max` (and beyond `min`) of the Z axis: a profile swept
    along a curve on a cylinder with Path + Guide Surface keeps hugging it."""
    from sciforge import bodies

    obj = self.objects.get(step["step"])
    body = bodies.body_of(obj) if obj is not None else None
    if body is None:
        raise BuildError("expect_radius: %r is not in a body" % step["step"])
    points = []
    for face in body.Shape.Faces:
        points += [v.Point for v in face.Vertexes]
        points += face.tessellate(0.1)[0]
    radii = [(p.x * p.x + p.y * p.y) ** 0.5 for p in points]
    if max(radii) > step["max"] or min(radii) < step.get("min", 0.0):
        raise BuildError(
            "expect_radius: %s reaches %.4f .. %.4f from the Z axis, expected %s .. %s"
            % (body.Label, min(radii), max(radii), step.get("min", 0.0), step["max"])
        )


Builder.op_expect_bodies = op_expect_bodies
Builder.op_reopen_check = op_reopen_check
Builder.op_expect_move_refused = op_expect_move_refused
Builder.op_construct_expect = op_construct_expect
Builder.op_measure_expect = op_measure_expect
Builder.op_section_expect = op_section_expect
Builder.op_com_expect = op_com_expect
Builder.op_interference_expect = op_interference_expect
Builder.op_blend_radius_expect = op_blend_radius_expect
Builder.op_expect_component = op_expect_component
Builder.op_expect_radius = op_expect_radius

from . import export_checks  # noqa: E402,F401  (registers export_report_expect and its setups)
from . import live_checks  # noqa: E402,F401  (registers live_blend_expect)
