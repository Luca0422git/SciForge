# SPDX-License-Identifier: LGPL-2.1-or-later
"""Design step for Fusion's Emboss, built with the same SciForge code as the Emboss
dialog (sciforge/emboss.py). Registered on core.Builder when the package is imported.

  {"op": "emboss", "id": "em1", "sketch": "s2", "faces": <face selector>,
   "depth": 1, "effect": "emboss" | "deboss", "h": 0, "v": 0, "angle": 0,
   "tangent_chain": true}
      Every closed area of the sketch step is a profile (as if all were clicked); the
      faces come from the part as it is (body Tip). A negative depth swaps the effect,
      as in Fusion.
"""

from . import selectors
from .core import Builder, BuildError

OPTIONS = ("depth", "effect", "h", "v", "angle", "tangent_chain")


def op_emboss(self, step):
    from sciforge import emboss, extrude
    from sciforge import emboss_core as core

    sketch = self.objects.get(step["sketch"])
    if sketch is None or self.ops.get(step["sketch"]) != "sketch":
        raise BuildError("emboss %r: 'sketch' must name an earlier sketch" % step["id"])
    self.doc.recompute()
    base = self._tip()
    names = selectors.select(base.Shape, step["faces"], "faces")
    if not names:
        raise BuildError("emboss %r: the face selector picked nothing" % step["id"])
    profiles = [(sketch, name) for name, _face in extrude.regions(sketch)]
    if not profiles:
        raise BuildError("emboss %r: the sketch has no closed area" % step["id"])
    options = core.default_options()
    options.update({k: step[k] for k in OPTIONS if k in step})
    try:
        feature = emboss.make(self.body, base, profiles, names, options, name=step["id"])
    except core.EmbossError as exc:
        raise BuildError("emboss %r: %s" % (step["id"], exc))
    self.objects[step["id"]] = feature
    self.ops[step["id"]] = "emboss"
    self._recompute(step, feature)
    return feature


Builder.op_emboss = op_emboss
