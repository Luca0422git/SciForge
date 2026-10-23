# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's SURFACE tools as plain data and small rules. Pure Python (no FreeCAD, no Qt),
unit tested in SciForgeTests/unit/test_surface_core.py.

Every surface tool (Extrude, Revolve, Sweep, Loft, Patch, Ruled, Offset, Boundary Fill,
Trim, Untrim, Extend, Stitch, Unstitch, Reverse Normal, Thicken) is one "kind" of SciForge
surface step. KINDS says, per kind, what Fusion calls it, which icon it has, whether it
makes a new body (CREATE) or changes the body it acts on (MODIFY), which operations its
dialog offers and the dialog's starting values. The geometry is in surface_geom.py, the
document side in surface.py, the dialogs in surface_ui.py.
"""

import math


class SurfaceError(ValueError):
    """The step cannot be built as asked; the message says why and what to try."""


class NeedsPick(SurfaceError):
    """A selection box still waits for its click (the dialog shows it as a hint)."""


CREATE_OPERATIONS = ("new_body", "new_component")
SOLID_OPERATIONS = ("join", "cut", "intersect", "new_body", "new_component")
OPERATION_LABELS = {
    "join": "Join",
    "cut": "Cut",
    "intersect": "Intersect",
    "new_body": "New Body",
    "new_component": "New Component",
}

DIRECTIONS = ("one_side", "two_sides", "symmetric")
DIRECTION_LABELS = {"one_side": "One Side", "two_sides": "Two Sides", "symmetric": "Symmetric"}
MEASUREMENTS = ("half", "whole")
CONTINUITY = {"connected": 0, "tangent": 1, "curvature": 2}  # Fusion's G0 / G1 / G2
CONTINUITY_LABELS = {"connected": "Connected", "tangent": "Tangent", "curvature": "Curvature"}
RULED_TYPES = ("tangent", "normal", "direction")
RULED_LABELS = {"tangent": "Tangent", "normal": "Normal", "direction": "Direction"}
EXTEND_TYPES = ("natural", "perpendicular", "tangent")
EXTEND_LABELS = {"natural": "Natural", "perpendicular": "Perpendicular", "tangent": "Tangent"}
ALIGNMENTS = ("free", "align")
ALIGNMENT_LABELS = {"free": "Free Edges", "align": "Align Edges"}
LOOP_TYPES = ("all", "internal", "external", "manual")
LOOP_LABELS = {
    "all": "All Edges",
    "internal": "Internal Edges",
    "external": "External Edges",
    "manual": "Manual",
}
THICKEN_TYPES = ("sharp", "rounded")
THICKEN_LABELS = {"sharp": "Sharp", "rounded": "Rounded"}
# Offset Type (Fusion May 2025): Sharp keeps the offset faces meeting in sharp edges (the
# faces carried on until they meet), Rounded rounds the convex corners (an arc of the
# distance about the corner). Sharp is Fusion's default; steps saved before SciForge had
# the choice keep Rounded (LEGACY below), so a reopened design keeps its shape.
OFFSET_TYPES = ("sharp", "rounded")
OFFSET_LABELS = {"sharp": "Sharp Offset", "rounded": "Rounded Offset"}
# Ruled Corner Type (Fusion: Rounded / Mitered, default Rounded) -> the "mitered" option.
CORNER_TYPES = (("Rounded", False), ("Mitered", True))
ORIENTATIONS = ("perpendicular", "parallel")
REVOLVE_TYPES = ("angle", "to", "full")
# Fusion's word for the Angle extent is Partial (the key stays "angle" in saved files).
REVOLVE_LABELS = {"angle": "Partial", "to": "To", "full": "Full"}
EXTENTS = ("distance", "to_object", "all")
STARTS = ("profile", "offset", "object")
SWEEP_TYPES = ("single", "rail", "surface")
SWEEP_LABELS = {
    "single": "Single Path",
    "rail": "Path + Guide Rail",
    "surface": "Path + Guide Surface",
}
# Path + Guide Rail extent (Fusion: where the sweep stops relative to the rail).
RAIL_EXTENTS = ("perpendicular", "full")
RAIL_EXTENT_LABELS = {"perpendicular": "Perpendicular to Path", "full": "Full Extents"}
SCALINGS = ("scale", "stretch", "none")
SCALING_LABELS = {"scale": "Scale", "stretch": "Stretch", "none": "None"}
GUIDES = ("rails", "centerline")
# Loft end conditions (loft_ends_core.CONDITIONS): which ones a profile offers depends on
# what it is (a sketch curve: Connected / Direction; an edge of a body: Connected / Tangent
# / Curvature; a point: Sharp / Point Tangent).
END_CONDITIONS = ("free", "direction", "tangent", "curvature", "point_tangent")
MAX_END_WEIGHT = 20.0
MAX_TAPER = 89.0

# Stitch: Autodesk staff on the Autodesk Community ("Stitch problem" thread): the dialog
# starts at 1.0 mm. The tolerance is what may be closed, never more than 10 mm here.
STITCH_TOLERANCE = 1.0
MAX_TOLERANCE = 10.0
MIN_TOLERANCE = 1e-6
# Patch: Fusion's tangency weight scale (its fillet weights run 0.1 .. 2.0); the Patch
# dialog starts at 0.5 (API PatchFeatureInput.groupWeight).
WEIGHT_RANGE = (0.1, 2.0)
PATCH_WEIGHT = 0.5

KINDS = {
    "extrude": {
        "title": "Extrude",
        "icon": "surface_extrude",
        "type": "SurfaceExtrude",
        "create": True,
        "operations": CREATE_OPERATIONS,
        "defaults": {
            "start": "profile",
            "start_offset": 0.0,
            "direction": "one_side",
            "measurement": "half",
            "extent": "distance",
            "distance": 0.0,
            "distance2": 0.0,
            "taper": 0.0,
            "taper2": 0.0,
            "flip": False,
            "chain_faces": True,
            "chain": True,
            "operation": "new_body",
        },
    },
    "revolve": {
        "title": "Revolve",
        "icon": "surface_revolve",
        "type": "SurfaceRevolve",
        "create": True,
        "operations": CREATE_OPERATIONS,
        "defaults": {
            "type": "angle",
            "direction": "one_side",
            "angle": 360.0,
            "angle2": 0.0,
            "project_axis": True,
            "chain": True,
            "operation": "new_body",
        },
    },
    "sweep": {
        "title": "Sweep",
        "icon": "surface_sweep",
        "type": "SurfaceSweep",
        "create": True,
        "operations": CREATE_OPERATIONS,
        "defaults": {
            "type": "single",
            "distance": 1.0,
            "distance2": 1.0,
            "orientation": "perpendicular",
            "twist": 0.0,
            "taper": 0.0,
            "scaling": "scale",
            "rail_extent": "perpendicular",
            "rail_distance": 1.0,
            "chain": True,
            "operation": "new_body",
        },
    },
    "loft": {
        "title": "Loft",
        "icon": "surface_loft",
        "type": "SurfaceLoft",
        "create": True,
        "operations": CREATE_OPERATIONS,
        "defaults": {
            "guide": "rails",
            "closed": False,
            "merge": False,
            "start_condition": "free",
            "start_weight": 1.0,
            "start_angle": 0.0,
            "end_condition": "free",
            "end_weight": 1.0,
            "end_angle": 0.0,
            "chain": True,
            "operation": "new_body",
        },
    },
    "patch": {
        "title": "Patch",
        "icon": "patch",
        "type": "Patch",
        "create": True,
        "operations": CREATE_OPERATIONS,
        "defaults": {
            "continuity": "connected",
            "weight": PATCH_WEIGHT,
            "group_edges": True,
            "edge_continuity": [],
            "reverse": False,
            "chain": True,
            "operation": "new_body",
        },
    },
    "ruled": {
        "title": "Ruled",
        "icon": "ruled",
        "type": "Ruled",
        "create": True,
        "operations": CREATE_OPERATIONS,
        "defaults": {
            "ruled_type": "tangent",
            "distance": 0.0,
            "angle": 0.0,
            "alternate": False,
            "mitered": False,
            "chain": True,
            "operation": "new_body",
        },
    },
    "offset": {
        "title": "Offset",
        "icon": "surface_offset",
        "type": "SurfaceOffset",
        "create": True,
        "operations": CREATE_OPERATIONS,
        "defaults": {
            "distance": 0.0,
            "offset_type": "sharp",
            "chain": True,
            "operation": "new_body",
        },
    },
    "boundary_fill": {
        "title": "Boundary Fill",
        "icon": "boundary_fill",
        "type": "BoundaryFill",
        "create": True,
        "operations": SOLID_OPERATIONS,
        "defaults": {"cells": [], "remove_tools": False, "operation": "new_body"},
    },
    "thicken": {
        "title": "Thicken",
        "icon": "thicken",
        "type": "Thicken",
        "create": True,
        "operations": SOLID_OPERATIONS,
        "defaults": {
            "thickness": 0.0,
            "direction": "one_side",
            "thicken_type": "sharp",
            "chain": True,
            "operation": "new_body",
        },
    },
    "trim": {
        "title": "Trim",
        "icon": "trim",
        "type": "Trim",
        "create": False,
        "operations": (),
        "defaults": {"cells": []},
    },
    "untrim": {
        "title": "Untrim",
        "icon": "untrim",
        "type": "Untrim",
        "create": False,
        "operations": (),
        "defaults": {"loop_type": "all", "extend": False, "distance": 0.0, "keep_copy": False},
    },
    "extend": {
        "title": "Extend",
        "icon": "surface_extend",
        "type": "SurfaceExtend",
        "create": False,
        "operations": (),
        "defaults": {
            "distance": 0.0,
            "extend_type": "natural",
            "alignment": "free",
            "chain": True,
        },
    },
    "stitch": {
        "title": "Stitch",
        "icon": "stitch",
        "type": "Stitch",
        "create": False,
        # Fusion: the operation is used when the stitch closes into a solid
        "operations": ("new_body", "join", "cut", "intersect"),
        "defaults": {"tolerance": STITCH_TOLERANCE, "operation": "new_body"},
    },
    "unstitch": {
        "title": "Unstitch",
        "icon": "unstitch",
        "type": "Unstitch",
        "create": False,
        "operations": (),
        "defaults": {"chain": True},
    },
    "reverse_normal": {
        "title": "Reverse Normal",
        "icon": "reverse_normal",
        "type": "ReverseNormal",
        "create": False,
        "operations": (),
        "defaults": {},
    },
    "piece": {  # the first (hidden) step of a body Unstitch made
        "title": "Unstitch",
        "icon": "unstitch",
        "type": "SurfacePiece",
        "create": False,
        "operations": (),
        "defaults": {},
    },
}

# Options a step saved before SciForge had them reads as it was built then (a reopened
# design keeps its shape): an Offset without Offset Type was Rounded, a Revolve without
# Project Axis used the axis where it is, a rail Sweep ran both curves to their ends.
LEGACY = {
    "offset": {"offset_type": "rounded"},
    "revolve": {"project_axis": False},
    "sweep": {"rail_extent": "full"},
}

# SciForgeType -> kind
BY_TYPE = {spec["type"]: kind for kind, spec in KINDS.items()}

# The timeline's kind of each surface step (timeline_core.KIND_BY_SCIFORGE_TYPE), with the
# name and icon Fusion shows there.
TIMELINE_KINDS = {
    "surface_extrude": ("Extrude", "surface_extrude"),
    "surface_revolve": ("Revolve", "surface_revolve"),
    "surface_sweep": ("Sweep", "surface_sweep"),
    "surface_loft": ("Loft", "surface_loft"),
    "patch": ("Patch", "patch"),
    "ruled": ("Ruled", "ruled"),
    "surface_offset": ("Offset", "surface_offset"),
    "boundary_fill": ("Boundary Fill", "boundary_fill"),
    "trim": ("Trim", "trim"),
    "untrim": ("Untrim", "untrim"),
    "surface_extend": ("Extend", "surface_extend"),
    "stitch": ("Stitch", "stitch"),
    "unstitch": ("Unstitch", "unstitch"),
    "reverse_normal": ("Reverse Normal", "reverse_normal"),
}
TIMELINE_BY_TYPE = {
    "SurfaceExtrude": "surface_extrude",
    "SurfaceRevolve": "surface_revolve",
    "SurfaceSweep": "surface_sweep",
    "SurfaceLoft": "surface_loft",
    "Patch": "patch",
    "Ruled": "ruled",
    "SurfaceOffset": "surface_offset",
    "BoundaryFill": "boundary_fill",
    "Thicken": "thicken",
    "Trim": "trim",
    "Untrim": "untrim",
    "SurfaceExtend": "surface_extend",
    "Stitch": "stitch",
    "Unstitch": "unstitch",
    "ReverseNormal": "reverse_normal",
}


def spec(kind):
    if kind not in KINDS:
        raise SurfaceError("Unknown surface tool %r." % kind)
    return KINDS[kind]


def title(kind):
    return spec(kind)["title"]


def sciforge_type(kind):
    return spec(kind)["type"]


def kind_of_type(sciforge_type):
    """The kind of a SciForgeType ("Patch" -> "patch"), or None for other steps."""
    return BY_TYPE.get(sciforge_type or "")


def makes_body(kind):
    """True for the CREATE tools: their step is the first step of a body of its own."""
    return bool(spec(kind)["create"])


def with_defaults(kind, options=None):
    merged = dict(spec(kind)["defaults"])
    # a value left empty (None) keeps the starting value
    merged.update({k: v for k, v in (options or {}).items() if v is not None})
    for key, value in list(merged.items()):
        if isinstance(value, list):
            merged[key] = list(value)
    return merged


def with_saved(kind, saved):
    """The options of a saved step: what it saved, the LEGACY value for an option it was
    saved without, the starting values for the rest."""
    saved = dict(saved or {})
    for key, value in LEGACY.get(kind, {}).items():
        saved.setdefault(key, value)
    return with_defaults(kind, saved)


def operations(kind):
    return list(spec(kind)["operations"])


def is_solid_operation(operation):
    return operation in ("join", "cut", "intersect")


# -- values ------------------------------------------------------------------------------------
def _finite(value, what):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise SurfaceError("%s must be a number." % what)
    if math.isnan(number) or math.isinf(number):
        raise SurfaceError("%s must be a number." % what)
    return number


def check_values(kind, options):
    """Raise SurfaceError (with what to type instead) for values the tool cannot use.
    Values are mm and degrees; a distance of 0 is a hint (NeedsPick), like Fusion's
    dialog waiting for the arrow to be dragged."""
    o = options
    if kind == "extrude":
        if o.get("direction") not in DIRECTIONS:
            raise SurfaceError("Pick One Side, Two Sides or Symmetric.")
        if o.get("start", "profile") not in STARTS:
            raise SurfaceError("Pick Profile Plane, Offset or From Object.")
        if o.get("extent", "distance") not in EXTENTS:
            raise SurfaceError("Pick Distance, To Object or All.")
        d1 = _finite(o.get("distance", 0.0), "Distance")
        d2 = _finite(o.get("distance2", 0.0), "Distance Two")
        taper = _finite(o.get("taper", 0.0), "Taper Angle")
        taper2 = _finite(o.get("taper2", 0.0), "Taper Angle Two")
        _finite(o.get("start_offset", 0.0), "Offset")
        if o.get("extent", "distance") == "distance":
            total = abs(d1) + (abs(d2) if o.get("direction") == "two_sides" else 0.0)
            if total < 1e-7:
                raise NeedsPick("Drag the arrow or type a distance.")
        if abs(taper) >= MAX_TAPER or abs(taper2) >= MAX_TAPER:
            raise SurfaceError("The taper angle must be between -89 and 89 degrees.")
    elif kind == "revolve":
        if o.get("type") not in REVOLVE_TYPES:
            raise SurfaceError("Pick Partial, To or Full.")
        if o.get("direction") not in DIRECTIONS:
            raise SurfaceError("Pick One Side, Two Sides or Symmetric.")
        if o.get("type") == "to" and o.get("direction") == "symmetric":
            raise SurfaceError("To turns One Side or Two Sides (each side to its own object).")
        a1 = _finite(o.get("angle", 0.0), "Angle")
        a2 = _finite(o.get("angle2", 0.0), "Angle Two")
        if o.get("type") == "angle":
            total = abs(a1) + (abs(a2) if o.get("direction") == "two_sides" else 0.0)
            if total < 1e-7:
                raise NeedsPick("Drag the handle or type an angle.")
            if o.get("direction") == "symmetric" and abs(a1) > 180.0 + 1e-9:
                raise SurfaceError(
                    "A symmetric revolve turns the angle each way: at most 180 degrees."
                )
            if total > 360.0 + 1e-9:
                raise SurfaceError("A revolve turns at most 360 degrees in all.")
    elif kind == "sweep":
        if o.get("type", "single") not in SWEEP_TYPES:
            raise SurfaceError("Pick Single Path, Path + Guide Rail or Path + Guide Surface.")
        if o.get("rail_extent", "perpendicular") not in RAIL_EXTENTS:
            raise SurfaceError("Pick Perpendicular to Path or Full Extents.")
        for key, what in (
            ("distance", "Distance"),
            ("distance2", "Distance Two"),
            ("rail_distance", "Guide Rail Distance"),
        ):
            value = _finite(o.get(key, 1.0), what)
            if not 0.0 <= value <= 1.0:
                raise SurfaceError("%s is a share of the path: type a number from 0 to 1." % what)
        _finite(o.get("twist", 0.0), "Twist Angle")
        taper = _finite(o.get("taper", 0.0), "Taper Angle")
        if abs(taper) >= MAX_TAPER:
            raise SurfaceError("The taper angle must be between -89 and 89 degrees.")
        if o.get("orientation") not in ORIENTATIONS:
            raise SurfaceError("Pick Perpendicular or Parallel.")
        if o.get("scaling", "scale") not in SCALINGS:
            raise SurfaceError("Pick Scale, Stretch or None.")
    elif kind == "loft":
        if o.get("guide", "rails") not in GUIDES:
            raise SurfaceError("Pick Rails or Centerline.")
        for end, what in (("start", "first"), ("end", "last")):
            if o.get(end + "_condition", "free") not in END_CONDITIONS:
                raise SurfaceError("Pick an end condition for the %s profile." % what)
            weight = _finite(o.get(end + "_weight", 1.0), "The weight")
            angle = _finite(o.get(end + "_angle", 0.0), "The takeoff angle")
            if o.get(end + "_condition", "free") == "free":
                continue
            if not 0.0 < weight <= MAX_END_WEIGHT:
                raise SurfaceError(
                    "The weight must be more than 0 and at most %g." % MAX_END_WEIGHT
                )
            if not -MAX_TAPER <= angle <= MAX_TAPER:
                raise SurfaceError("The takeoff angle must be between -89 and 89 degrees.")
    elif kind == "patch":
        if o.get("continuity") not in CONTINUITY:
            raise SurfaceError("Pick Connected, Tangent or Curvature.")
        for value in o.get("edge_continuity") or []:
            if value not in CONTINUITY:
                raise SurfaceError("Pick Connected, Tangent or Curvature for every edge.")
        weight = _finite(o.get("weight", 1.0), "Tangency Weight")
        if not WEIGHT_RANGE[0] - 1e-9 <= weight <= WEIGHT_RANGE[1] + 1e-9:
            raise SurfaceError(
                "Tangency Weight runs from %.1f to %.1f." % (WEIGHT_RANGE[0], WEIGHT_RANGE[1])
            )
    elif kind == "ruled":
        if o.get("ruled_type") not in RULED_TYPES:
            raise SurfaceError("Pick Tangent, Normal or Direction.")
        distance = _finite(o.get("distance", 0.0), "Distance")
        angle = _finite(o.get("angle", 0.0), "Angle")
        if abs(distance) < 1e-7:
            raise NeedsPick("Drag the arrow or type a distance.")
        if abs(angle) >= 90.0 - 1e-9 and o.get("ruled_type") != "direction":
            raise SurfaceError("The angle must be between -90 and 90 degrees.")
    elif kind in ("offset", "extend"):
        distance = _finite(o.get("distance", 0.0), "Distance")
        if abs(distance) < 1e-7:
            raise NeedsPick("Drag the arrow or type a distance.")
        if kind == "offset" and o.get("offset_type", "sharp") not in OFFSET_TYPES:
            raise SurfaceError("Pick Sharp Offset or Rounded Offset.")
        if kind == "extend":
            if o.get("extend_type") not in EXTEND_TYPES:
                raise SurfaceError("Pick Natural, Perpendicular or Tangent.")
            if distance < 0 and o.get("extend_type") != "perpendicular":
                raise SurfaceError(
                    "Natural and Tangent extend outwards only: type a positive distance."
                )
    elif kind == "thicken":
        thickness = _finite(o.get("thickness", 0.0), "Thickness")
        if abs(thickness) < 1e-7:
            raise NeedsPick("Drag the arrow or type a thickness.")
        if o.get("direction") not in ("one_side", "symmetric"):
            raise SurfaceError("Pick One Side or Symmetric.")
        if o.get("thicken_type") not in THICKEN_TYPES:
            raise SurfaceError("Pick Sharp or Rounded.")
    elif kind == "untrim":
        if o.get("loop_type") not in LOOP_TYPES:
            raise SurfaceError("Pick All Edges, Internal Edges, External Edges or Manual.")
        distance = _finite(o.get("distance", 0.0), "Extend distance")
        if distance < 0:
            raise SurfaceError("The extend distance must not be negative.")
    elif kind == "stitch":
        tol = _finite(o.get("tolerance", STITCH_TOLERANCE), "Tolerance")
        if not MIN_TOLERANCE <= tol <= MAX_TOLERANCE:
            raise SurfaceError(
                "Type a tolerance from 0.000001 to %g mm: gaps up to it are closed." % MAX_TOLERANCE
            )
    operation = o.get("operation")
    allowed = operations(kind)
    if allowed and operation not in allowed:
        raise SurfaceError("Pick one of: %s." % ", ".join(OPERATION_LABELS[op] for op in allowed))


# -- ranges ---------------------------------------------------------------------------------
def extrude_range(direction, distance, distance2=0.0, measurement="half"):
    """(start, end) along the profile's normal, in mm, the way Fusion's Direction reads the
    distances: One Side 0..d, Two Sides -d2..d, Symmetric -d..d (Half Length) or
    -d/2..d/2 (Whole Length)."""
    d1, d2 = float(distance), float(distance2)
    if direction == "two_sides":
        return -d2, d1
    if direction == "symmetric":
        half = abs(d1) / 2.0 if measurement == "whole" else abs(d1)
        return -half, half
    return (0.0, d1) if d1 >= 0 else (d1, 0.0)


def revolve_range(rtype, direction, angle, angle2=0.0):
    """(start angle, sweep) in degrees about the axis (right-handed)."""
    if rtype == "full":
        return 0.0, 360.0
    a1, a2 = float(angle), float(angle2)
    if direction == "symmetric":
        a = abs(a1)
        if 2.0 * a >= 360.0 - 1e-9:
            return 0.0, 360.0
        return -a, 2.0 * a
    if direction == "two_sides":
        return -a2, a1 + a2
    return (0.0, a1) if a1 >= 0 else (a1, -a1)


def stop_angle(start, directions, axis):
    """Revolve Type To: the signed degrees (right-handed about `axis`) from the profile's
    direction `start` (from the axis, square to it) to the nearest of `directions` (the
    half-planes the object marks), the shorter way round; half a turn either way goes the
    positive way, like the solid revolve (revolve.stop_angle). All unit 3-tuples."""
    best = None
    for w in directions:
        cross = (
            start[1] * w[2] - start[2] * w[1],
            start[2] * w[0] - start[0] * w[2],
            start[0] * w[1] - start[1] * w[0],
        )
        angle = math.degrees(
            math.atan2(
                sum(a * c for a, c in zip(axis, cross)), sum(a * b for a, b in zip(start, w))
            )
        )
        if abs(angle) < 1e-6:
            continue
        shorter = best is None or abs(angle) < abs(best) - 1e-9
        if shorter or (abs(abs(angle) - abs(best)) <= 1e-9 and angle > best):
            best = angle
    if best is None:
        raise SurfaceError(
            "The object is where the profile already is. Pick one the revolve turns to."
        )
    return best


def turn_angle(start, directions, axis, sign):
    """Revolve To with Two Sides: the degrees (more than 0, less than 360) the profile turns
    `sign` way (+1 right-handed about `axis`, -1 the other way) until it reaches the first of
    `directions`. All unit 3-tuples."""
    best = None
    for w in directions:
        cross = (
            start[1] * w[2] - start[2] * w[1],
            start[2] * w[0] - start[0] * w[2],
            start[0] * w[1] - start[1] * w[0],
        )
        angle = math.degrees(
            math.atan2(
                sum(a * c for a, c in zip(axis, cross)), sum(a * b for a, b in zip(start, w))
            )
        )
        angle = (angle * sign) % 360.0
        if angle < 1e-6 or angle > 360.0 - 1e-6:
            continue
        if best is None or angle < best:
            best = angle
    if best is None:
        raise SurfaceError(
            "The object is where the profile already is. Pick one the revolve turns to."
        )
    return best


def two_sided_to(start, first, second, axis):
    """Revolve To with Two Sides: (start angle, sweep) in degrees. The first side turns the
    right-handed way to the first object, the second side the other way to the second."""
    a1 = turn_angle(start, first, axis, 1.0)
    a2 = turn_angle(start, second, axis, -1.0)
    if a1 + a2 > 360.0 + 1e-9:
        raise SurfaceError(
            "The two sides would overlap (%.0f + %.0f degrees is more than a full turn). Pick "
            "objects that leave a gap between them, or use Full." % (a1, a2)
        )
    return -a2, a1 + a2


def corner_shift(previous, corners, centre_prev, centre):
    """Loft of closed profiles with the same number of corners (Fusion Sept 2026): the
    (shift, reverse) that lines `corners` up with the corners of the profile before it, so
    corner i of one meets corner i of the next. previous / corners: points (3-tuples) in
    order round each profile; centres: their middles. The pairing with the shortest total
    distance between matched corners (each measured from its profile's middle) wins; on a
    tie the profile keeps its own start and direction."""
    n = len(corners)
    if n == 0 or n != len(previous):
        return 0, False

    def rel(p, c):
        return tuple(a - b for a, b in zip(p, c))

    prev = [rel(p, centre_prev) for p in previous]
    mine = [rel(p, centre) for p in corners]
    best = None
    for reverse in (False, True):
        for shift in range(n):
            cost = 0.0
            for i in range(n):
                q = mine[(shift - i) % n] if reverse else mine[(i + shift) % n]
                cost += math.sqrt(sum((a - b) ** 2 for a, b in zip(prev[i], q)))
            key = (round(cost, 9), reverse, shift)
            if best is None or key < best[0]:
                best = (key, shift, reverse)
    return best[1], best[2]


def all_lengths(direction, flip, reach_up, reach_down):
    """Extent All: (length along the normal, length against it) from the start plane, given
    how far the visible bodies reach each way (mm, <= 0: nothing that way). One Side goes
    the normal's way (Flip: the other); Two Sides and Symmetric go both ways."""
    up = max(0.0, float(reach_up))
    down = max(0.0, float(reach_down))
    if direction == "one_side":
        up, down = (0.0, down) if flip else (up, 0.0)
    if up < 1e-7 and down < 1e-7:
        raise SurfaceError(
            "No visible body lies that way: All extrudes through the visible bodies. "
            + ("Flip it, or use Distance." if direction == "one_side" else "Use Distance.")
        )
    return up, down


def taper_factor(length, angle_deg, reach):
    """How much a tapered sweep's end section is scaled: a profile point `reach` from the
    path moves out by length * tan(angle) (Fusion: the taper tilts the sweep's sides)."""
    reach = float(reach)
    if reach < 1e-9:
        raise SurfaceError("The profile sits on the path: there is nothing to taper.")
    factor = 1.0 + float(length) * math.tan(math.radians(float(angle_deg))) / reach
    if factor <= 1e-3:
        raise SurfaceError(
            "The taper angle shrinks the profile to nothing before the end of the path. Use a "
            "smaller angle or a shorter distance."
        )
    return factor


def lerp_fraction(a, b, t, closed):
    """A place on a profile (0..1 along it) between `a` and `b` at share t; on a closed
    profile the shorter way round (0 and 1 are the same place)."""
    a, b = float(a), float(b)
    if closed:
        d = (b - a) % 1.0
        if d > 0.5:
            d -= 1.0
        return (a + d * t) % 1.0
    return a + (b - a) * t


def similarity(q1, q2, r1, r2):
    """The turn + even scale + move (a 3 x 4 matrix as rows) taking q1 to r1 and q2 to r2,
    turning the least: a loft section moved so that it touches two rails. With q1 == q2
    (one rail) it is a plain move."""

    def sub(a, b):
        return [x - y for x, y in zip(a, b)]

    def dot(a, b):
        return sum(x * y for x, y in zip(a, b))

    def cross(a, b):
        return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]

    a = sub(q2, q1)
    b = sub(r2, r1)
    la, lb = math.sqrt(dot(a, a)), math.sqrt(dot(b, b))
    if la < 1e-12:
        move = sub(r1, q1)
        return [[1.0, 0.0, 0.0, move[0]], [0.0, 1.0, 0.0, move[1]], [0.0, 0.0, 1.0, move[2]]]
    if lb < 1e-12:
        raise SurfaceError("The rails meet here, so the profile would shrink to nothing.")
    an = [x / la for x in a]
    bn = [x / lb for x in b]
    axis = cross(an, bn)
    s = math.sqrt(dot(axis, axis))
    c = dot(an, bn)
    if s < 1e-12:
        if c > 0:
            rot = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
        else:  # half a turn about any axis square to a
            helper = [1.0, 0.0, 0.0] if abs(an[0]) < 0.9 else [0.0, 1.0, 0.0]
            k = cross(an, helper)
            lk = math.sqrt(dot(k, k))
            k = [x / lk for x in k]
            rot = [[2 * k[i] * k[j] - (1.0 if i == j else 0.0) for j in range(3)] for i in range(3)]
    else:
        k = [x / s for x in axis]
        kx, ky, kz = k
        v = 1.0 - c
        rot = [
            [c + kx * kx * v, kx * ky * v - kz * s, kx * kz * v + ky * s],
            [ky * kx * v + kz * s, c + ky * ky * v, ky * kz * v - kx * s],
            [kz * kx * v - ky * s, kz * ky * v + kx * s, c + kz * kz * v],
        ]
    scale = lb / la
    m = [[rot[i][j] * scale for j in range(3)] for i in range(3)]
    moved = [sum(m[i][j] * q1[j] for j in range(3)) for i in range(3)]
    shift = sub(r1, moved)
    return [m[i] + [shift[i]] for i in range(3)]


def stretch_similarity(q1, q2, r1, r2):
    """Like similarity(), but the section grows only along the line between the two rails
    (the rest keeps the size the plain loft gives it): turned the least, stretched along
    r1 -> r2, moved so that q1 lands on r1 and q2 on r2."""
    m = similarity(q1, q2, r1, r2)
    a = [y - x for x, y in zip(q1, q2)]
    b = [y - x for x, y in zip(r1, r2)]
    la = math.sqrt(sum(c * c for c in a))
    lb = math.sqrt(sum(c * c for c in b))
    if la < 1e-12 or lb < 1e-12:
        return m
    k = lb / la
    bn = [c / lb for c in b]
    # m's 3 x 3 part is (turn) x k: take k out of the directions square to b
    rot = [[m[i][j] / k for j in range(3)] for i in range(3)]
    stretch = [
        [(1.0 if i == j else 0.0) + (k - 1.0) * bn[i] * bn[j] for j in range(3)] for i in range(3)
    ]
    lin = [[sum(stretch[i][t] * rot[t][j] for t in range(3)) for j in range(3)] for i in range(3)]
    moved = [sum(lin[i][j] * q1[j] for j in range(3)) for i in range(3)]
    return [lin[i] + [r1[i] - moved[i]] for i in range(3)]


def apply_matrix(m, p):
    return tuple(sum(m[i][j] * p[j] for j in range(3)) + m[i][3] for i in range(3))


def thicken_offsets(direction, thickness):
    """(where the thickening starts, how thick) along the face normal: One Side 0 .. t,
    Symmetric -t/2 .. t/2."""
    t = float(thickness)
    if direction == "symmetric":
        return -t / 2.0, t
    return 0.0, t


# -- vectors (tuples) --------------------------------------------------------------------------
def _norm(v):
    length = math.sqrt(sum(c * c for c in v))
    if length < 1e-12:
        raise SurfaceError("A direction of zero length.")
    return tuple(c / length for c in v)


def ruling_direction(ruled_type, normal, away, angle_deg, direction=None):
    """Which way a Ruled surface leaves an edge (a unit vector, as a tuple).

    normal: the face's normal at the edge; away: the direction in the face, square to the
    edge, pointing out of the face; angle_deg: Fusion's Angle. Tangent: the face carried on
    (away), turned by the angle towards the normal. Normal: square to the face, turned by
    the angle towards `away`. Direction: the given direction (the angle tilts it towards
    `away`)."""
    n = _norm(normal)
    a = _norm(away)
    t = math.radians(float(angle_deg))
    if ruled_type == "tangent":
        base, towards = a, n
    elif ruled_type == "normal":
        base, towards = n, a
    elif ruled_type == "direction":
        if direction is None:
            raise NeedsPick("Pick the direction: a straight edge, an axis or a plane.")
        base, towards = _norm(direction), a
    else:
        raise SurfaceError("Pick Tangent, Normal or Direction.")
    out = tuple(math.cos(t) * b + math.sin(t) * w for b, w in zip(base, towards))
    return _norm(out)


# -- cells (Trim, Boundary Fill) -----------------------------------------------------------------
def choose_cells(distances, tolerance):
    """Which cells the stored points name. distances[i][j]: distance from stored point i to
    cell j. Each point takes its nearest cell when that is within `tolerance`. Returns
    (sorted cell indices, indices of the points that found no cell)."""
    chosen, lost = set(), []
    for i, row in enumerate(distances):
        if not row:
            lost.append(i)
            continue
        best = min(range(len(row)), key=lambda j: (row[j], j))
        if row[best] <= tolerance:
            chosen.add(best)
        else:
            lost.append(i)
    return sorted(chosen), lost


def toggle_point(points, cell_index, cell_point, owner, tolerance=1e-6):
    """A click on cell `cell_index`: the stored points (lists [x, y, z]) without the ones
    naming this cell (owner(point) == cell_index), or with the cell's point added."""
    keep = [p for p in points if owner(p) != cell_index]
    if len(keep) != len(points):
        return keep
    return keep + [[float(c) for c in cell_point]]


# -- words ---------------------------------------------------------------------------------------
def count_label(count, noun, plural=None):
    if count <= 0:
        return ""
    if count == 1:
        return "1 %s" % noun
    return "%d %s" % (count, plural or noun + "s")


def picked_text(refs_count, kinds):
    """'3 edges', '1 face', '2 bodies', '2 curves + 1 point' from {'edge': 3, ...}."""
    nouns = {
        "edge": ("edge", "edges"),
        "curve": ("curve", "curves"),
        "face": ("face", "faces"),
        "body": ("body", "bodies"),
        "point": ("point", "points"),
        "plane": ("plane", "planes"),
        "profile": ("profile", "profiles"),
        "cell": ("cell", "cells"),
        "loop": ("loop", "loops"),
    }
    parts = []
    for key in ("profile", "curve", "edge", "face", "body", "plane", "point", "cell", "loop"):
        n = kinds.get(key, 0)
        if n:
            single, plural = nouns[key]
            parts.append(count_label(n, single, plural))
    return " + ".join(parts) if parts else ""


def cell_name(index, size, solid):
    """'Cell 2 (125.0 mm³)' / 'Cell 2 (40.0 mm²)' for the cells list."""
    unit = "mm³" if solid else "mm²"
    return "Cell %d (%.1f %s)" % (index + 1, size, unit)
