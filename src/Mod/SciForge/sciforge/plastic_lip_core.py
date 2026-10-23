# SPDX-License-Identifier: LGPL-2.1-or-later
"""Lip (PLASTIC > CREATE: Lip / Groove / Lip And Groove), the pure part: options, defaults from
the plastic rule, the checks the dialog shows and the cross-section of the lip and of the
groove as offsets from the picked edges. No FreeCAD, no Qt: unit tested
(test_plastic2_core.py); plastic_lip.py makes the solids.

Fusion (docs/sciforge/dev/research/fusion-plastic.md 2.5, 4.4): pick the tangent chain of
edges where the two halves of an enclosure meet (the inside edge of the rim, so the reveal is
on the outside). A Lip stands on the rim along those edges; the Groove on the touching body
is the lip grown by the clearance (sides) and the clearance height (depth), so the halves
locate and the outer part of the wall shows as a reveal line.

A section is a band across the rim, measured from the picked edges into the rim face:
(a, b) = from a to b millimetres away from the edges (a < 0: on the other side of them).
At height z above the rim face a drafted lip's band shrinks to (a + z tan(inner draft),
b - z tan(outer draft)); a groove's band at depth z the same way, so its walls run parallel
to the lip's.
"""

import math

TYPES = ("lip_and_groove", "lip", "groove")
TYPE_TITLES = {"lip_and_groove": "Lip And Groove", "lip": "Lip", "groove": "Groove"}
GUIDES = ("pull", "face")
GUIDE_TITLES = {"pull": "Pull Direction", "face": "Face Guide"}
LENGTHS = (
    "lip_width",
    "lip_height",
    "clearance",
    "clearance_height",
    "groove_width",
    "groove_depth",
    "tip_radius",
    "root_radius",
)
ANGLES = ("inner_draft", "outer_draft")
LABELS = {
    "lip_width": "Lip Width",
    "lip_height": "Lip Height",
    "clearance": "Clearance",
    "clearance_height": "Clearance Height",
    "groove_width": "Groove Width",
    "groove_depth": "Groove Depth",
    "tip_radius": "Tip Radius",
    "root_radius": "Root Radius",
    "inner_draft": "Inner Draft",
    "outer_draft": "Outer Draft",
}
RULE_FIELDS = {
    "lip_width": ("thickness", 0.5),
    "lip_height": ("reveal_height", 1.0),
    "clearance": ("clearance", 1.0),
    "clearance_height": ("clearance", 1.0),
    "inner_draft": ("draft_angle", 1.0),
    "outer_draft": ("draft_angle", 1.0),
}
FALLBACK_RULE = {"thickness": 2.0, "reveal_height": 1.0, "clearance": 0.1, "draft_angle": 1.0}


def defaults(rule=None):
    """A new Lip's options; rule: an evaluated plastic rule (mm, degrees) or None."""
    rule = dict(FALLBACK_RULE, **(rule or {}))
    t = float(rule["thickness"])
    c = float(rule["clearance"])
    h = float(rule["reveal_height"])
    return {
        "type": "lip_and_groove",
        "guide": "pull",
        "swap": False,
        "lip_width": 0.5 * t,
        "lip_height": h,
        "clearance": c,
        "clearance_height": c,
        "groove_width": 0.5 * t + c,
        "groove_depth": h + c,
        "inner_draft": float(rule["draft_angle"]),
        "outer_draft": float(rule["draft_angle"]),
        "tip_radius": 0.0,
        "root_radius": 0.0,
        "linked": sorted(RULE_FIELDS),
    }


def follow_rule(options, rule):
    out = dict(options)
    rule = dict(FALLBACK_RULE, **(rule or {}))
    for field in out.get("linked", []):
        source = RULE_FIELDS.get(field)
        if source is not None and source[0] in rule:
            out[field] = float(rule[source[0]]) * source[1]
    return out


def unlink(options, field):
    out = dict(options)
    out["linked"] = [f for f in out.get("linked", []) if f != field]
    return out


def validate(options):
    """[] when the options can make a lip, else the reasons."""
    o = options
    problems = []
    if o.get("type") not in TYPES:
        return ["Choose Lip, Groove or Lip And Groove."]
    if o["type"] == "groove":
        needed = ("groove_width", "groove_depth")
    else:
        needed = ("lip_width", "lip_height")
    for key in needed:
        if not o.get(key, 0) > 0:
            problems.append("%s must be more than 0." % LABELS[key])
    for key in ("clearance", "clearance_height", "tip_radius", "root_radius"):
        if o.get(key, 0) < 0:
            problems.append("%s cannot be negative." % LABELS[key])
    for key in ANGLES:
        if not 0 <= o.get(key, 0) < 30:
            problems.append("%s must lie between 0 and 30 degrees." % LABELS[key])
    if problems:
        return problems
    if o["type"] != "groove":
        top = lip_section(o)[1]
        if top[1] - top[0] <= 0.05 * o["lip_width"]:
            problems.append(
                "The drafts close the lip before its top: lower them or the Lip Height."
            )
        if o["tip_radius"] > 0 and 2 * o["tip_radius"] >= top[1] - top[0]:
            problems.append("Tip Radius must be less than half the lip's top width.")
        if o.get("root_radius", 0) + o["tip_radius"] >= o["lip_height"]:
            problems.append("Root Radius and Tip Radius together must be less than Lip Height.")
    else:
        bottom = groove_section(o)[1]
        if bottom[1] - bottom[0] <= 0.05 * o["groove_width"]:
            problems.append("The drafts close the groove before its bottom: lower them.")
    return problems


def _drafted(a, b, z, inner, outer):
    return (a + z * math.tan(math.radians(inner)), b - z * math.tan(math.radians(outer)))


def lip_section(options):
    """((a, b) at the rim face, (a, b) at the lip's top, height) of the lip."""
    o = options
    h = o["lip_height"]
    base = (0.0, o["lip_width"])
    return base, _drafted(base[0], base[1], h, o["inner_draft"], o["outer_draft"]), h


def groove_section(options):
    """((a, b) at the rim face, (a, b) at the groove's bottom, depth) of the groove: for Lip
    And Groove the lip grown by the clearance on both sides and the clearance height in
    depth (Autodesk: the groove follows from the lip and the clearance); for Groove alone its
    own width and depth."""
    o = options
    if o["type"] == "groove":
        base = (0.0, o["groove_width"])
        d = o["groove_depth"]
    else:
        c = o["clearance"]
        base = (-c, o["lip_width"] + c)
        d = o["lip_height"] + o["clearance_height"]
    return base, _drafted(base[0], base[1], d, o["inner_draft"], o["outer_draft"]), d


def band_area(a, b, length):
    """Area of a straight band (a, b) along `length` of edge (for checks in the tests)."""
    return (b - a) * length


def section_area(bottom, top, height):
    """Area of a (drafted) section: a trapezoid."""
    return 0.5 * ((bottom[1] - bottom[0]) + (top[1] - top[0])) * height


def wall_check(lip_width, wall):
    """The text refusing a lip as wide as the wall, or ""."""
    if wall is not None and lip_width >= wall - 1e-9:
        return "Lip Width (%.2f mm) must be less than the wall (%.2f mm) at the selected edges." % (
            lip_width,
            wall,
        )
    return ""
