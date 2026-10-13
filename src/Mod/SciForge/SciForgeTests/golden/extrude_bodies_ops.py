# SPDX-License-Identifier: LGPL-2.1-or-later
"""Golden-model steps for an Extrude that acts on several bodies (Fusion's extrude goes
through every body in its way: one timeline step, every body cut / joined / intersected),
built with the same code as the E dialog (sciforge/extrude.py). Registered on
builder.Builder when builder.py is imported.

Bodies are named by a step that made them (its body): "e1" is the body of extrude e1.

  {"op": "extrude", ..., "bodies": "auto" | ["e1", "e2"]}
      "auto": every body the extrusion passes through (what the dialog lists by itself);
      a list: exactly these bodies (the dialog's "Bodies to Cut" row after clicks).

  {"op": "use_body", "step": "e1"}
      The next sketches go into that body (Fusion: the sketch is made on a face or plane
      of that body).

  {"op": "expect_bodies", "bodies": {"e1": {"volume": 3500, "solids": 1}, ...},
   "used_up": ["e2"], "followers": {"x1": 1}, "steps": {"x1": 1}}
      Checks each body, the bodies a step uses up (hidden, Join merge), how many hidden
      follower steps an extrude has and how often it is listed in the timeline.

  {"op": "reopen_check", "bodies": {...as above...}}
      Saves the design, opens the file as a second design, recomputes it and checks the
      bodies there (the follower steps come back from the file).

  {"op": "expect_move_refused", "target": "e2", "after": "x1", "reason": "does not exist"}
      Dragging a step before / after another in the timeline is refused with that reason
      (a multi-body extrude moves with its hidden steps, builder.op_move; only a move
      that would put it before a body it changes exists is refused).
"""

import os
import tempfile

from .builder import Builder, BuildError


def _body(builder, step_id):
    from .bodies_ops import _body as body_of_step

    return body_of_step(builder, step_id)


def _extrude_bodies(self, step):
    spec = step["bodies"]
    if spec == "auto":
        return "auto"
    return [_body(self, s) for s in spec]


def op_use_body(self, step):
    self.body = _body(self, step["step"])


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


Builder._extrude_bodies = _extrude_bodies
Builder.op_expect_move_refused = op_expect_move_refused
Builder.op_use_body = op_use_body
Builder.op_expect_bodies = op_expect_bodies
Builder.op_reopen_check = op_reopen_check
