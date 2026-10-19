# SPDX-License-Identifier: LGPL-2.1-or-later
"""Design steps for an Extrude that acts on several bodies (Fusion's extrude goes
through every body in its way: one timeline step, every body cut / joined / intersected),
built with the same code as the E dialog (sciforge/extrude.py). Registered on
core.Builder when the package is imported.

Bodies are named by a step that made them (its body): "e1" is the body of extrude e1.
The golden models' checks of several bodies (expect_bodies, reopen_check,
expect_move_refused) are in SciForgeTests/golden/checks.py.

  {"op": "extrude", ..., "bodies": "auto" | ["e1", "e2"]}
      "auto": every body the extrusion passes through (what the dialog lists by itself);
      a list: exactly these bodies (the dialog's "Bodies to Cut" row after clicks).

  {"op": "use_body", "step": "e1"}
      The next sketches go into that body (Fusion: the sketch is made on a face or plane
      of that body).
"""

from .core import Builder


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


Builder._extrude_bodies = _extrude_bodies
Builder.op_use_body = op_use_body
