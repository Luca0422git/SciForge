# SPDX-License-Identifier: LGPL-2.1-or-later
"""SURFACE > MODIFY on surface bodies (wave 6, surface-4): the pure rules, no FreeCAD, no Qt
(unit tested in SciForgeTests/unit/test_surfmod_core.py).

Fusion repeats SOLID's MODIFY tools on its SURFACE tab and they work on surface bodies
(open bodies: faces, no solid). SciForge's steps for the ones a solid's PartDesign feature
cannot do on a surface (docs/sciforge/parity/surface-modify.md):

  surface_fillet       Fillet on edges of a surface body (each edge between two faces of it)
  surface_chamfer      Chamfer on the same edges: Equal Distance, Two Distances, Distance
                       and Angle
  surface_delete_face  Delete on the SURFACE tab: faces removed without healing (a solid
                       becomes a surface body at the first deleted face)
  surface_merge        Merge: adjacent faces of one surface body that lie on one surface
                       become one face
  surface_press_pull   Press Pull on a flat face of a surface body: the face moves along its
                       normal, the faces around it (which run along the pull) follow
"""

# kind -> SciForgeType of its step
TYPES = {
    "surface_fillet": "SurfaceFillet",
    "surface_chamfer": "SurfaceChamfer",
    "surface_delete_face": "SurfaceDeleteFace",
    "surface_merge": "SurfaceMerge",
    "surface_press_pull": "SurfacePressPull",
}
KIND_BY_TYPE = {v: k for k, v in TYPES.items()}

# kind -> (its title, its own icon in icons/ui: the browser / tree icon of the step)
TIMELINE_KINDS = {
    "surface_fillet": ("Fillet", "surfmod_fillet"),
    "surface_chamfer": ("Chamfer", "surfmod_chamfer"),
    "surface_delete_face": ("Delete Face", "surfmod_delete"),
    "surface_merge": ("Merge", "surfmod_merge"),
    "surface_press_pull": ("Press Pull", "surfmod_press_pull"),
}
# In Fusion a fillet on a surface body is the same Fillet feature as on a solid (one row of
# numbers and one icon in the timeline): these steps show as the SOLID kinds there
# (timeline_core.KINDS). Merge is a kind of its own.
TIMELINE_SHARED = {
    "SurfaceFillet": "fillet",
    "SurfaceChamfer": "chamfer",
    "SurfaceDeleteFace": "delete_face",
    "SurfacePressPull": "presspull",
    "SurfaceMerge": "surface_merge",
}
# the dialog's header icon per kind (the SOLID command's, as Fusion's dialog is the same)
DIALOG_ICONS = {
    "surface_fillet": "fillet",
    "surface_chamfer": "chamfer",
    "surface_delete_face": "delete",
    "surface_merge": "surfmod_merge",
    "surface_press_pull": "press_pull",
}

# Fusion's Radius Type: Constant, Chord Length, Variable. On surface bodies SciForge builds
# Constant and Variable (Radius at the edge's start, End Radius at its end; OpenCASCADE's
# makeFillet(r1, r2)); Chord Length is shown greyed with the reason.
RADIUS_TYPES = ("constant", "variable")
RADIUS_LABELS = {"constant": "Constant", "variable": "Variable", "chord": "Chord Length"}
CHAMFER_TYPES = ("equal", "two", "angle")
CHAMFER_LABELS = {
    "equal": "Equal Distance",
    "two": "Two Distances",
    "angle": "Distance and Angle",
}

DEFAULTS = {
    "surface_fillet": {
        "radius": 1.0,
        "radius_type": "constant",
        "radius2": 1.0,
        "tangent_chain": True,
    },
    "surface_chamfer": {
        "chamfer_type": "equal",
        "distance": 1.0,
        "distance2": 1.0,
        "angle": 45.0,
        "flip": False,
        "tangent_chain": True,
    },
    "surface_delete_face": {},
    "surface_merge": {},
    "surface_press_pull": {"distance": 0.0},
}

# Mirror / Pattern with Operation Join on surface bodies: the copies are stitched to the
# original, gaps up to this closed (Fusion's Stitch Tolerance; its default was not found,
# SciForge uses Stitch's own 1 mm: G).
STITCH_TOLERANCE = 1.0

TITLES = {
    "surface_fillet": "Fillet",
    "surface_chamfer": "Chamfer",
    "surface_delete_face": "Delete Face",
    "surface_merge": "Merge",
    "surface_press_pull": "Press Pull",
}


class SurfaceModifyError(ValueError):
    """The step cannot be made as asked; the message says why and what to try."""


class NeedsPick(SurfaceModifyError):
    """A selection box still waits for its click (or a value for its typing)."""


def kind_of_type(sciforge_type):
    return KIND_BY_TYPE.get(sciforge_type or "")


def with_defaults(kind, options=None):
    merged = dict(DEFAULTS.get(kind, {}))
    merged.update(options or {})
    return merged


def check_values(kind, options):
    """Raise SurfaceModifyError / NeedsPick for values the step cannot take."""
    o = options
    if kind == "surface_fillet":
        if float(o["radius"]) <= 1e-7:
            raise NeedsPick("Type a radius bigger than 0, or drag the arrow.")
        if o.get("radius_type", "constant") not in RADIUS_TYPES:
            raise SurfaceModifyError(
                "Chord Length fillets are not made on surface bodies: pick Constant or Variable."
            )
        if o.get("radius_type") == "variable" and float(o.get("radius2", 0.0)) <= 1e-7:
            raise NeedsPick("Type the End Radius (bigger than 0).")
    elif kind == "surface_chamfer":
        if o["chamfer_type"] not in CHAMFER_TYPES:
            raise SurfaceModifyError("Pick a chamfer type.")
        if float(o["distance"]) <= 1e-7:
            raise NeedsPick("Type a distance bigger than 0, or drag the arrow.")
        if o["chamfer_type"] == "two" and float(o["distance2"]) <= 1e-7:
            raise NeedsPick("Type the second distance (bigger than 0).")
        if o["chamfer_type"] == "angle" and not 0.0 < float(o["angle"]) < 90.0:
            raise SurfaceModifyError("The angle must be between 0 and 90 degrees.")
    elif kind == "surface_press_pull":
        if abs(float(o["distance"])) <= 1e-7:
            raise NeedsPick("Drag the arrow or type a distance (+ pulls, - pushes).")


def chamfer_distances(options):
    """(distance on the edge's first face, distance on the second) of a chamfer, in mm. A
    Distance and Angle chamfer: the second side is distance x tan(angle). Flip swaps the
    sides (Fusion's flip of the reference face)."""
    import math

    kind = options["chamfer_type"]
    d1 = float(options["distance"])
    if kind == "equal":
        d2 = d1
    elif kind == "two":
        d2 = float(options["distance2"])
    else:
        d2 = d1 * math.tan(math.radians(float(options["angle"])))
    if options.get("flip") and kind != "equal":
        d1, d2 = d2, d1
    return d1, d2


def delete_heals(tab, faces_of_surface_body):
    """Fusion decides by where Delete is run: on the SOLID tab a solid's faces are healed
    (DeleteFaceFeature: the faces around grow to close the gap); on the SURFACE tab faces are
    removed and the hole stays (SurfaceDeleteFaceFeature: a solid becomes a surface body).
    A surface body has nothing to heal: its faces are always just removed."""
    if faces_of_surface_body:
        return False
    return tab != "surface"


def press_pull_action(direction_dot, distance):
    """What a face next to a pushed / pulled face does at their shared edge: "extend" (it
    grows by a band as long as the move) or "trim" (it is cut back to the moved face).
    direction_dot: + when the neighbour runs from the edge the way the face moves (its
    normal), - when it runs the other way."""
    if abs(direction_dot) < 1e-9:
        raise SurfaceModifyError(
            "A face next to it lies along it, not across: it cannot follow the move."
        )
    if direction_dot * distance < 0:
        return "extend"
    return "trim"


# Merge of faces that only meet smoothly refits them as one surface (Fusion: Merge "will
# change the shape of the surface", F): refused when that moves the surface more than this
# (mm), or this share of the faces' size.
MERGE_DEVIATION = 0.01
MERGE_DEVIATION_SHARE = 1e-3


def merge_outcome(picked, after, smooth=False):
    """The Merge dialog's verdict on picked faces (count) that became `after` faces. smooth:
    the faces that did not merge meet smoothly (tangent), so they can be refitted."""
    if picked < 2:
        raise NeedsPick("Select two or more faces next to each other on one surface body.")
    if after >= picked and not smooth:
        raise SurfaceModifyError(
            "These faces lie on different surfaces and meet at a sharp edge, so they cannot "
            "become one face. Merge joins faces that lie on one surface (pieces left by Split "
            "Face, Trim or a patch) or meet smoothly (tangent)."
        )
    if after >= picked:  # smooth: refitted as one surface (merge_refit_message says more)
        return "The %d faces become one face (refitted)." % picked
    if after == 1:
        return "The %d faces become one face." % picked
    return "The %d faces become %d faces (only faces on one surface merge)." % (picked, after)


def merge_refit_message(picked, deviation, size):
    """The verdict on faces that meet smoothly, refitted as one surface that moves by
    `deviation` (mm) at most; `size` is the faces' size (their bounding box diagonal)."""
    limit = max(MERGE_DEVIATION, MERGE_DEVIATION_SHARE * size)
    if deviation > limit:
        raise SurfaceModifyError(
            "One surface through these faces would move them by %.2f mm, more than %.2f mm: "
            "they are not smooth enough to merge. Merge fewer faces at a time." % (deviation, limit)
        )
    return "The %d faces become one face (refitted: the surface moves by %.3f mm at most)." % (
        picked,
        deviation,
    )
