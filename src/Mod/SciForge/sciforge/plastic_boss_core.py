# SPDX-License-Identifier: LGPL-2.1-or-later
"""The Boss's settings, pure Python (no FreeCAD, no Qt; unit tested): the options of both
sides, SciForge's default sizes for a screw and a plastic rule, the rule links, the checks
that refuse what cannot be built, the rib angles. plastic_boss.py builds the geometry."""

import copy

TOL = 1e-6

SHAPES = ("blank", "constant_diameter", "constant_thickness")
HOLES = ("simple", "counterbore", "countersink")
EXTENTS = ("through", "from_top", "from_bottom")
STEPS = ("none", "in", "out")
RIB_PROFILES = ("none", "chamfer", "fillet")
RIB_EXTENTS = ("length", "to_next")
RIB_EACH = ("length", "to_next", "suppressed")

SIDE_NUMBERS = (
    "diameter",
    "wall",
    "draft",
    "hole_diameter",
    "hole_draft",
    "hole_depth",
    "major_diameter",
    "major_depth",
    "countersink_angle",
    "step_diameter",
    "step_depth",
    "step_draft",
    "clearance",
    "root_radius",
    "tip_radius",
    "hole_start_radius",
    "hole_end_radius",
    "step_tip_radius",
    "step_root_radius",
    "major_tip_radius",
    "major_root_radius",
    "rib_total_angle",
    "rib_rotation",
    "rib_cut",
    "rib_chamfer_angle",
    "rib_thickness",
    "rib_draft",
    "rib_outer_draft",
    "rib_length",
    "rib_offset",
)
SIDE_CHOICES = {
    "shape": SHAPES,
    "hole": HOLES,
    "extent": EXTENTS,
    "step": STEPS,
    "rib_profile": RIB_PROFILES,
    "rib_extent": RIB_EXTENTS,
}

# Fields that follow the plastic rule while nobody typed over them: side field -> (rule
# field, factor). A typed value drops the link of that field (dialog).
RULE_LINKS = {
    "draft": ("draft_angle", 1.0),
    "wall": ("thickness", 0.6),
    "root_radius": ("nominal_radius", 1.0),
    "clearance": ("clearance", 0.5),
    "rib_thickness": ("thickness", 0.6),
    "rib_draft": ("draft_angle", 1.0),
    "step_draft": ("draft_angle", 1.0),
}


class BossError(ValueError):
    """The boss cannot be built as asked; the message says why and what to try."""


def _r(value, places=2):
    return round(float(value), places)


def side_defaults(side, rule, screw=3.0):
    """Default settings of one side for an M`screw` thread-forming screw and a plastic rule
    (plastic_core.evaluated): SciForge's own sizing from generic plastics guidance (G)."""
    t = float(rule["thickness"])
    c = float(rule["clearance"])
    d = float(screw)
    out = {
        "enabled": True,
        "shape": "constant_diameter",
        "wall": _r(0.6 * t),
        "draft": float(rule["draft_angle"]),
        "hole_draft": 0.0,
        "countersink_angle": 90.0,
        "step_draft": float(rule["draft_angle"]),
        "clearance": _r(c / 2.0, 3),
        "root_radius": _r(min(float(rule["nominal_radius"]), 0.5 * t)),
        "tip_radius": 0.0,
        "hole_start_radius": 0.0,
        "hole_end_radius": 0.0,
        "step_tip_radius": 0.0,
        "step_root_radius": 0.0,
        "major_tip_radius": 0.0,
        "major_root_radius": 0.0,
        "ribs": False,
        "rib_count": 4,
        "rib_total_angle": 360.0,
        "rib_rotation": 0.0,
        "rib_profile": "chamfer",
        "rib_cut": 1.0,
        "rib_chamfer_angle": 60.0,
        "rib_thickness": _r(0.6 * t),
        "rib_draft": float(rule["draft_angle"]),
        "rib_outer_draft": 0.0,
        "rib_extent": "length",
        "rib_offset": 1.0,
    }
    if side == 1:
        out.update(
            diameter=_r(2.5 * d + 2.5),
            hole="counterbore",
            extent="through",
            hole_diameter=_r(d + 0.4),
            hole_depth=_r(2.0 * d),
            major_diameter=_r(2.0 * d + 0.5),
            major_depth=_r(t),
            step="in",
            step_diameter=_r(2.5 * d + 2.0 * c),
            step_depth=1.0,
            rib_length=_r(1.5 * d + 2.0 * t),
        )
    else:
        out.update(
            diameter=_r(2.5 * d),
            hole="simple",
            extent="from_bottom",
            hole_diameter=_r(0.8 * d),
            hole_depth=_r(t / 2.0),
            major_diameter=_r(d + 0.5),
            major_depth=1.0,
            step="out",
            step_diameter=_r(2.5 * d),
            step_depth=_r(1.0 - c),
            rib_length=_r(1.25 * d + 2.0 * t),
        )
    return out


def default_options(rule, screw=3.0):
    """Every option of a new boss (both sides), every rule-linked field linked."""
    links = {}
    for side in (1, 2):
        for key in RULE_LINKS:
            links["side%d.%s" % (side, key)] = True
    return {
        "screw": float(screw),
        "offset": 0.0,
        "flip": False,
        "side1": side_defaults(1, rule, screw),
        "side2": side_defaults(2, rule, screw),
        "links": links,
        "fastener": dict(FASTENER_DEFAULTS),
    }


def apply_rule(options, rule):
    """The options with every still-linked field set from the rule (a copy)."""
    out = copy.deepcopy(options)
    for path, on in (options.get("links") or {}).items():
        if not on or "." not in path:
            continue
        side, key = path.split(".", 1)
        if side not in ("side1", "side2") or key not in RULE_LINKS:
            continue
        field, factor = RULE_LINKS[key]
        value = rule.get(field)
        if value is None:
            continue
        value = float(value) * factor
        out[side][key] = _r(value, 3)
    return out


FASTENER_HEADS = ("pan", "round", "flat", "hex", "hex_washer")
FASTENER_DEFAULTS = {"create": False, "head": "pan", "length": 0.0}


def check_options(options):
    """Raise BossError for options that cannot make a boss (dialog texts)."""
    fastener = dict(FASTENER_DEFAULTS)
    fastener.update(options.get("fastener") or {})
    if fastener["head"] not in FASTENER_HEADS:
        raise BossError("Fastener: unknown head type %r" % fastener["head"])
    try:
        fastener["length"] = float(fastener["length"])
    except (TypeError, ValueError):
        raise BossError("Fastener: the length must be a number (0 = auto).")
    if fastener["length"] < 0:
        raise BossError("Fastener: the length cannot be negative (0 = auto).")
    if fastener["create"] and options["side1"]["shape"] == "blank":
        raise BossError("Fastener: Side 1 is blank (no hole), there is no screw to place.")
    options["fastener"] = fastener
    for side in (1, 2):
        s = options["side%d" % side]
        for key, allowed in SIDE_CHOICES.items():
            if s.get(key) not in allowed:
                raise BossError("Side %d: unknown %s %r" % (side, key, s.get(key)))
        for key in (
            "hole_start_radius",
            "hole_end_radius",
            "step_tip_radius",
            "step_root_radius",
            "major_tip_radius",
            "major_root_radius",
        ):
            s.setdefault(key, 0.0)
        for key in SIDE_NUMBERS:
            try:
                s[key] = float(s[key])
            except (TypeError, ValueError, KeyError):
                raise BossError("Side %d: %s must be a number" % (side, key.replace("_", " ")))
        s["rib_count"] = int(s.get("rib_count", 4))
        each = s.get("rib_extents") or []
        if not isinstance(each, list) or any(e not in RIB_EACH for e in each):
            raise BossError(
                "Side %d: each rib is By Length, To Next or Suppressed (%r)" % (side, each)
            )
        s["rib_extents"] = list(each)
        if not s.get("enabled", True):
            continue
        name = "Side %d" % side
        hole = s["shape"] != "blank"
        od = outer_diameter(s)
        if od <= TOL:
            raise BossError("%s: the outer diameter must be more than 0." % name)
        if hole and s["hole_diameter"] <= TOL:
            raise BossError("%s: the hole diameter must be more than 0." % name)
        if hole and s["hole_diameter"] >= od - TOL:
            raise BossError(
                "%s: the hole (%.2f mm) must be smaller than the outer diameter (%.2f mm)."
                % (name, s["hole_diameter"], od)
            )
        if hole and s["hole"] != "simple" and s["major_diameter"] <= s["hole_diameter"] + TOL:
            raise BossError(
                "%s: the %s diameter must be larger than the hole diameter."
                % (name, "counterbore" if s["hole"] == "counterbore" else "countersink")
            )
        if hole and s["hole"] == "countersink" and not 10.0 <= s["countersink_angle"] <= 170.0:
            raise BossError("%s: the countersink angle must be 10-170 degrees." % name)
        if s["step"] != "none" and (s["step_diameter"] <= TOL or s["step_depth"] <= TOL):
            raise BossError("%s: the alignment step needs a diameter and a depth." % name)
        if s["step"] == "in" and s["step_diameter"] >= od - TOL:
            raise BossError("%s: the alignment recess must be narrower than the boss." % name)
        if s["step"] == "in" and hole and s["step_diameter"] <= s["hole_diameter"] + TOL:
            raise BossError("%s: the alignment recess must be wider than the hole." % name)
        if s["step"] == "out" and hole and s["step_diameter"] <= s["hole_diameter"] + TOL:
            raise BossError("%s: the alignment spigot must be wider than the hole." % name)
        for key in ("draft", "hole_draft", "rib_draft", "rib_outer_draft", "step_draft"):
            if not 0.0 <= s[key] < 30.0:
                raise BossError("%s: draft angles must be 0-30 degrees." % name)
        for key in (
            "clearance",
            "root_radius",
            "tip_radius",
            "hole_depth",
            "major_depth",
            "hole_start_radius",
            "hole_end_radius",
            "step_tip_radius",
            "step_root_radius",
            "major_tip_radius",
            "major_root_radius",
        ):
            if s[key] < 0:
                raise BossError("%s: %s cannot be negative." % (name, key.replace("_", " ")))
        if s.get("ribs"):
            if s["rib_count"] < 1:
                raise BossError("%s: the ribs need a quantity of 1 or more." % name)
            if not 0.0 < s["rib_total_angle"] <= 360.0:
                raise BossError("%s: the ribs' total angle must be 0-360 degrees." % name)
            if s["rib_thickness"] <= TOL:
                raise BossError("%s: the rib thickness must be more than 0." % name)
            extents = rib_extents(s)
            if all(e == "suppressed" for e in extents):
                raise BossError("%s: every rib is suppressed: switch the ribs off." % name)
            if "length" in extents and s["rib_length"] <= od / 2.0 + TOL:
                raise BossError(
                    "%s: the rib length (from the boss axis) must reach past the boss "
                    "(more than %.2f mm)." % (name, od / 2.0)
                )
            if s["rib_offset"] < 0 or s["rib_cut"] < 0:
                raise BossError("%s: rib sizes cannot be negative." % name)
    return options


def rib_extents(s):
    """Each rib's extent (Fusion sets them one by one): "length", "to_next" or
    "suppressed"; ribs not listed take the side's extent."""
    each = list(s.get("rib_extents") or [])
    count = int(s.get("rib_count", 0))
    return [each[i] if i < len(each) else s["rib_extent"] for i in range(count)]


def outer_diameter(s):
    if s["shape"] == "constant_thickness":
        return float(s["hole_diameter"]) + 2.0 * float(s["wall"])
    return float(s["diameter"])


def rib_angles(count, total, rotation):
    """Degrees of each rib from the sketch's X axis: spread evenly all round (360) or over the
    span with one rib at each end."""
    count = int(count)
    if count < 1:
        return []
    if abs(total - 360.0) < 1e-9:
        return [rotation + i * 360.0 / count for i in range(count)]
    if count == 1:
        return [rotation]
    return [rotation + i * total / (count - 1) for i in range(count)]


def summary(options):
    """A short text of what the boss will make (dialog / log)."""
    parts = []
    for side in (1, 2):
        s = options["side%d" % side]
        if not s.get("enabled", True):
            continue
        hole = "no hole" if s["shape"] == "blank" else s["hole"]
        parts.append("side %d: dia %.2f, %s" % (side, outer_diameter(s), hole))
    return "; ".join(parts)
