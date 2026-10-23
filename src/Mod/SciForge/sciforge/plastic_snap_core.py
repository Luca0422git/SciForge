# SPDX-License-Identifier: LGPL-2.1-or-later
"""Snap Fit (PLASTIC > CREATE), the pure part: options, defaults from the plastic rule, the
checks the dialog shows, the hook's cross sections and catch profile, the groove / loop boxes
and the beam strain check. No FreeCAD, no Qt: unit tested (test_plastic_snap_core.py);
plastic_snap.py turns these numbers into solids.

Fusion's Snap Fit puts a cantilever hook at each sketch point between two bodies and the
part it catches on the other body (docs/sciforge/dev/research/fusion-plastic.md 2.4, 4.2,
4.3). Three types (Autodesk):

  parallel        Parallel Hook and Groove: the catch goes into a groove (a window or a
                  pocket) cut in a wall that runs along the beam
  perpendicular   Perpendicular Hook and Groove: the beam passes through a slot in a wall
                  across it and the catch hooks under that wall (the "hook undercut")
  loop            Hook and Loop: a frame built on the other body; the catch snaps behind
                  its bar

The local frame of one snap fit (all lengths in mm, angles in degrees):

  origin  the sketch point, on the parting plane
  z       the insertion axis, from the hook body towards the other body
  x       the catch direction (the sketch's x axis turned by the rotation angle)
  y       z cross x (the beam's width)

The point is the middle of the beam's catch side face at its root: the beam lies behind it
(x from -thickness to 0), the catch stands out in front (x from 0 to catch depth), from the
parting plane (z = 0) to the beam's free end (z = length).
"""

import math

TYPES = ("parallel", "perpendicular", "loop")
TYPE_TITLES = {
    "parallel": "Parallel Hook and Groove",
    "perpendicular": "Perpendicular Hook and Groove",
    "loop": "Hook and Loop",
}
SELECTIONS = ("automatic", "manual")
SELECTION_TITLES = {"automatic": "Automatic", "manual": "Manual"}
ROTATIONS = ("uniform", "independent", "aligned")
ROTATION_TITLES = {"uniform": "Uniform", "independent": "Independent", "aligned": "Aligned"}
EXTENTS = ("to_next", "distance")
EXTENT_TITLES = {"to_next": "To Next", "distance": "Distance"}

# The options a feature keeps (numbers in mm / degrees), with what the dialog calls them.
LENGTHS = (
    "extent_distance",
    "length",
    "width",
    "thickness",
    "tip_thickness",
    "catch_depth",
    "catch_length",
    "fillet",
    "clearance",
    "loop_thickness",
)
ANGLES = ("angle", "insertion_angle", "retention_angle", "draft")
LABELS = {
    "extent_distance": "Distance",
    "length": "Beam Length",
    "width": "Beam Width",
    "thickness": "Thickness at Root",
    "tip_thickness": "Thickness at Catch",
    "catch_depth": "Catch Depth",
    "catch_length": "Catch Length",
    "fillet": "Base Fillet Radius",
    "clearance": "Clearance",
    "loop_thickness": "Loop Thickness",
    "angle": "Rotation Angle",
    "insertion_angle": "Insertion Angle",
    "retention_angle": "Retention Angle",
    "draft": "Draft Angle",
}
# Fields that follow the component's plastic rule until a value is typed (Fusion links them
# to the rule: changing the rule updates the feature).
RULE_FIELDS = {
    "thickness": "thickness",
    "tip_thickness": "thickness",
    "draft": "draft_angle",
    "fillet": "nominal_radius",
    "clearance": "clearance",
    "loop_thickness": "thickness",
}
FALLBACK_RULE = {
    "thickness": 2.0,
    "draft_angle": 1.0,
    "nominal_radius": 1.0,
    "clearance": 0.1,
    "material": "ABS",
}


def defaults(rule=None):
    """The options a new Snap Fit starts with; rule: an evaluated plastic rule (mm, degrees)
    or None for SciForge's default rule."""
    rule = dict(FALLBACK_RULE, **(rule or {}))
    t = float(rule["thickness"])
    return {
        "type": "parallel",
        "selection": "automatic",
        "rotation": "uniform",
        "angle": 0.0,
        "angles": [],
        "flip": False,
        "hook": True,
        "extent": "to_next",
        "extent_distance": 2.0 * t,
        "length": 6.0 * t,
        "width": 3.0 * t,
        "thickness": t,
        "tip_thickness": t,
        "catch_depth": 0.5 * t,
        "catch_length": 1.5 * t,
        "insertion_angle": 30.0,
        "retention_angle": 90.0,
        "draft": float(rule["draft_angle"]),
        "fillet": float(rule["nominal_radius"]),
        "groove": True,
        "clearance": float(rule["clearance"]),
        "loop_thickness": t,
        "linked": sorted(RULE_FIELDS),
    }


def follow_rule(options, rule):
    """The options with every field still linked to the rule set from `rule` (evaluated)."""
    out = dict(options)
    rule = dict(FALLBACK_RULE, **(rule or {}))
    for field in out.get("linked", []):
        source = RULE_FIELDS.get(field)
        if source is not None and source in rule:
            out[field] = float(rule[source])
    return out


def unlink(options, field):
    """A value typed in a field ends its link to the rule."""
    out = dict(options)
    out["linked"] = [f for f in out.get("linked", []) if f != field]
    return out


def lead_in(options):
    """Length of the catch's lead-in ramp along the beam."""
    return options["catch_depth"] / math.tan(math.radians(options["insertion_angle"]))


def retention_run(options):
    """Length of the retention face along the beam (0 at 90 degrees: a square ledge)."""
    angle = options["retention_angle"]
    if angle >= 90.0 - 1e-9:
        return 0.0
    return options["catch_depth"] / math.tan(math.radians(angle))


def tip_width(options):
    """The beam's width at its free end (the draft narrows it towards the tip)."""
    return options["width"] - 2.0 * options["length"] * math.tan(math.radians(options["draft"]))


def catch_back(options):
    """z of the end of the catch nearest the parting plane."""
    return options["length"] - options["catch_length"] - retention_run(options)


def validate(options):
    """[] when the snap fit can be built, else the reasons (texts for the dialog)."""
    o = options
    problems = []
    if o.get("type") not in TYPES:
        problems.append("Choose a snap fit type.")
    for key in ("length", "width", "thickness", "tip_thickness", "catch_depth", "catch_length"):
        if not o.get(key, 0) > 0:
            problems.append("%s must be more than 0." % LABELS[key])
    for key in ("fillet", "clearance", "extent_distance", "loop_thickness"):
        if o.get(key, 0) < 0:
            problems.append("%s cannot be negative." % LABELS[key])
    if problems:
        return problems
    if not 0 < o["insertion_angle"] < 90:
        problems.append("Insertion Angle must lie between 0 and 90 degrees.")
    if not 0 < o["retention_angle"] <= 90:
        problems.append("Retention Angle must be more than 0 and at most 90 degrees.")
    if not 0 <= o["draft"] < 30:
        problems.append("Draft Angle must lie between 0 and 30 degrees.")
    if problems:
        return problems
    if o["catch_length"] < lead_in(o) - 1e-9:
        problems.append(
            "Catch Length (%.2f mm) is shorter than the lead-in ramp (%.2f mm at %.0f "
            "degrees): make the catch longer or raise the Insertion Angle."
            % (o["catch_length"], lead_in(o), o["insertion_angle"])
        )
    if catch_back(o) <= 0.25 * o["thickness"]:
        problems.append(
            "The catch does not fit on the beam: make Beam Length longer than Catch Length "
            "(%.2f mm with the retention face)." % (o["catch_length"] + retention_run(o))
        )
    if tip_width(o) <= 0.1 * o["width"]:
        problems.append("The Draft Angle narrows the beam to nothing: lower it or widen the beam.")
    if o["extent"] == "distance" and o["extent_distance"] <= 0:
        problems.append("Distance must be more than 0 for a Distance extent.")
    return problems


# -- the hook ---------------------------------------------------------------------------------
def beam_sections(options):
    """The beam's root and tip rectangles, [(x, y, z)] each, in the local frame."""
    o = options
    w0 = o["width"] / 2.0
    w1 = tip_width(o) / 2.0
    root = [
        (-o["thickness"], -w0, 0.0),
        (0.0, -w0, 0.0),
        (0.0, w0, 0.0),
        (-o["thickness"], w0, 0.0),
    ]
    z = o["length"]
    tip = [(-o["tip_thickness"], -w1, z), (0.0, -w1, z), (0.0, w1, z), (-o["tip_thickness"], w1, z)]
    return root, tip


def catch_profile(options):
    """The catch's outline [(x, z)] (closed, counter-clockwise seen along -y), reaching half
    the tip thickness into the beam so it fuses with it."""
    o = options
    z_tip = o["length"]
    y = o["catch_depth"]
    back = catch_back(o)
    inside = -0.5 * min(o["tip_thickness"], o["thickness"])
    return [
        (inside, back),
        (0.0, back),
        (y, z_tip - o["catch_length"]),
        (y, z_tip - lead_in(o)),
        (0.0, z_tip),
        (inside, z_tip),
    ]


def base_footprint(options):
    """The base block's rectangle under the beam root (x0, x1, y0, y1)."""
    w0 = options["width"] / 2.0
    return (-options["thickness"], 0.0, -w0, w0)


# -- the other body ---------------------------------------------------------------------------
def groove_box(options):
    """The box (x0, x1, y0, y1, z0, z1) cut from the other body (parallel: the groove the
    catch goes into; perpendicular: the slot the beam passes through, the catch hooking under
    the wall it crosses)."""
    o = options
    c = o["clearance"]
    w = o["width"] / 2.0 + c
    z1 = o["length"] + c
    if o["type"] == "perpendicular":
        return (-(o["thickness"] + o["catch_depth"] + c), c, -w, w, -c, z1)
    return (-c, o["catch_depth"] + c, -w, w, catch_back(o) - c, z1)


def ledge_z(options):
    """z of the ledge the catch's retention face rests against (the groove's or loop's edge
    nearest the parting plane)."""
    return catch_back(options) - options["clearance"]


def loop_boxes(options, reach=None):
    """(frame box, opening box) of a Hook and Loop's loop, each (x0, x1, y0, y1, z0, z1).
    The frame stands in front of the catch side (x from clearance to clearance + loop
    thickness) and runs from above the ledge down to `reach` (where it meets the loop body;
    at least past the beam's end)."""
    o = options
    c = o["clearance"]
    t = o["loop_thickness"]
    w = o["width"] / 2.0 + c
    z_open0 = ledge_z(o)
    z_open1 = o["length"] + c
    z_end = max(z_open1 + t, reach if reach is not None else 0.0)
    frame = (c, c + t, -(w + t), w + t, z_open0 - t, z_end)
    opening = (c - 1.0, c + t + 1.0, -w, w, z_open0, z_open1)
    return frame, opening


# -- strain check (cantilever beam theory, resin suppliers' design guides) --------------------
def strain_factor(options):
    """1.5 for a beam of even thickness, 1/1.09 = 0.917 when it tapers to half at the catch
    (resin suppliers' tables: deflection y = 0.67 e L^2 / t and y = 1.09 e L^2 / t; research
    critic pass C5), linear in between, clamped."""
    ratio = options["tip_thickness"] / options["thickness"]
    ratio = max(0.5, min(1.0, ratio))
    tapered = 1.0 / 1.09
    return tapered + (ratio - 0.5) / 0.5 * (1.5 - tapered)


def strain_percent(options):
    """The strain at the root while the catch is pushed in by its depth, in percent."""
    o = options
    return 100.0 * strain_factor(o) * o["thickness"] * o["catch_depth"] / (o["length"] ** 2)


def strain_note(options, material, allowable):
    """("ok" or "warn", text) for the dialog: the beam's strain against the material's
    allowable strain (percent)."""
    eps = strain_percent(options)
    if allowable is None:
        return "ok", "Strain at the root: %.1f %%" % eps
    if eps > allowable:
        return "warn", (
            "Strain at the root %.1f %% is above the %.1f %% %s allows: make the beam longer "
            "or thinner, or the catch shallower." % (eps, allowable, material)
        )
    return "ok", "Strain at the root: %.1f %% (%s allows %.1f %%)" % (eps, material, allowable)


# -- frames ------------------------------------------------------------------------------------
def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _scale(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def _unit(a):
    n = math.sqrt(_dot(a, a))
    if n < 1e-12:
        raise ValueError("zero vector")
    return (a[0] / n, a[1] / n, a[2] / n)


def rotate_about(v, axis, degrees):
    """v turned about the unit axis (right hand)."""
    a = math.radians(degrees)
    c, s = math.cos(a), math.sin(a)
    k = axis
    kxv = _cross(k, v)
    kdv = _dot(k, v)
    return tuple(v[i] * c + kxv[i] * s + k[i] * kdv * (1 - c) for i in range(3))


def frame(normal, x_axis, angle=0.0, flip=False):
    """(ex, ey, ez) of a snap fit on a sketch with this normal and x axis: ez = the insertion
    axis (minus the sketch normal: the hook body is on the normal's side; flip swaps the
    sides), ex = the sketch x turned by `angle` about the normal."""
    n = _unit(normal)
    ez = n if flip else _scale(n, -1.0)
    ex = _unit(rotate_about(_unit(x_axis), n, angle))
    ex = _unit(_sub(ex, _scale(ez, _dot(ex, ez))))
    ey = _cross(ez, ex)
    return ex, ey, ez


def aligned_x(point, reference, normal, outward=True):
    """The catch direction of an Aligned snap fit: from the reference towards the point (in
    the sketch plane), so snaps round a box all face out (outward=False: in)."""
    n = _unit(normal)
    d = _sub(point, reference)
    d = _sub(d, _scale(n, _dot(d, n)))
    d = _unit(d)
    return d if outward else _scale(d, -1.0)


def angles_for(options, count):
    """The rotation angle of each of `count` snap fits."""
    if options.get("rotation") == "independent":
        given = list(options.get("angles") or [])
        return [float(given[i]) if i < len(given) else options["angle"] for i in range(count)]
    return [options["angle"]] * count


def to_global(origin, axes, local):
    """A local (x, y, z) point in design coordinates."""
    ex, ey, ez = axes
    return tuple(
        origin[i] + ex[i] * local[0] + ey[i] * local[1] + ez[i] * local[2] for i in range(3)
    )
