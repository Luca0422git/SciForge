# SPDX-License-Identifier: LGPL-2.1-or-later
"""Ending an extrude on a face that is clicked (Luca: "when extruding, clicking on a face
should bring that extrusion to the same height as that face"). Pure logic, no FreeCAD: the
3D view part is extrude_to_face.py, the dialog extrude_ui.py.

What Fusion does (parity/extrude-presspull.md, "Click a face to end the extrude"):
- Extrude's profiles all lie in one plane, so once a profile is picked a click on a face
  elsewhere is no profile: it says where the extrusion ends.
- With the Distance extent, picking another object "only sets the extrusion distance to
  the current value" (not parametric): a flat face parallel to the profile, a vertex or a
  parallel plane sets Distance to the exact number that ends the extrusion there, plus or
  minus, and the arrow follows. Dragging the arrow over such a face or vertex snaps to it.
- A face the extrusion cannot end on at one height (curved, or tilted) is Fusion's To Object
  extent: the extent switches to To Object with that face.

Heights are signed distances along the profile's normal, measured from where the extrusion
starts (the profile plane, moved by a start offset). Points and normals are (x, y, z)
tuples, or anything with x, y, z (FreeCAD vectors).
"""

PARALLEL = 1e-6  # 1 - |cos| below this: the face is parallel to the profile
ACROSS = 1e-6  # |cos| below this: the face runs along the extrusion (cannot end on it)
FLAT = 1e-4  # mm: a face (or point) this close to a profile's plane lies in that plane

# How each kind of target is named in the dialog's words.
WHAT = {
    "face": "the face",
    "point": "the point",
    "plane": "the plane",
    "curved": "the curved face",
    "sloped": "the sloped face",
}


def _xyz(v):
    if hasattr(v, "x"):
        return (float(v.x), float(v.y), float(v.z))
    return (float(v[0]), float(v[1]), float(v[2]))


def dot(a, b):
    a, b = _xyz(a), _xyz(b)
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def height(point, origin, normal):
    """Signed distance of `point` from the plane through `origin` across `normal` (a unit
    vector), positive along the normal."""
    p, o = _xyz(point), _xyz(origin)
    return dot((p[0] - o[0], p[1] - o[1], p[2] - o[2]), normal)


def kind_of(shape, face_normal, normal):
    """How the extrusion can end on a target.

    shape: "flat" (a flat face), "plane" (a construction plane), "curved" (any other face)
    or "vertex". Returns "height" (it ends at one height: a vertex, or a flat face or plane
    parallel to the profile), "along" (a flat face or plane the extrusion runs along: it
    cannot end there) or "object" (a curved or tilted face: To Object)."""
    if shape == "vertex":
        return "height"
    if shape == "curved" or face_normal is None:
        return "object"
    c = abs(dot(face_normal, normal))
    if abs(c - 1.0) <= PARALLEL:
        return "height"
    if c <= ACROSS:
        return "along"
    return "object"


def what_of(shape, kind):
    """The word key for the target (WHAT): face, point, plane, curved or sloped."""
    if shape == "vertex":
        return "point"
    if shape == "plane":
        return "plane"
    if shape == "curved":
        return "curved"
    return "sloped" if kind == "object" else "face"


def in_profile_plane(level, levels, tol=FLAT):
    """True when a target at signed height `level` (from the first profile's plane) lies in
    the plane of one of the picked profiles (their heights `levels`, the same way)."""
    return any(abs(level - other) <= tol for other in levels)


def length_text(value):
    """12.5 -> "12.5 mm", 20 -> "20 mm", 1/3 -> "0.333 mm"."""
    text = ("%.3f" % float(value)).rstrip("0").rstrip(".")
    if text in ("-0", ""):
        text = "0"
    return text + " mm"


def side_for(level, direction, distance):
    """1 or 2: the side of the extrude a target at signed height `level` is on. One Side and
    Symmetric have one side; Two Sides: side one goes the way its distance points (along the
    normal at 0), side two the other way."""
    if direction != "two_sides":
        return 1
    toward = -1.0 if float(distance) < 0 else 1.0
    return 1 if level * toward > 0 else 2


def plan(kind, level, options, what="face", tol=FLAT):
    """What a click on a target does. `level`: its signed height from where the extrusion
    starts; options: the dialog's direction, measurement, distance, extent, extent2.

    Returns a dict with "action":
      "distance":  set the side's distance ("key": "distance" or "distance2", "value", and
                   "extent" "distance"), "note" says it in the dialog;
      "to_object": end the side ("side": 1 or 2) on the target, Extent To Object, "note";
      "refuse":    nothing changes, "message" says why."""
    words = WHAT.get(what, "the face")
    direction = options.get("direction", "one_side")
    measurement = options.get("measurement", "half")
    if kind == "along":
        return {
            "action": "refuse",
            "message": "%s runs along the extrusion, so the extrusion cannot end on it. "
            "Click a face across its path." % _cap(_that(words)),
        }
    if kind == "height":
        if abs(level) <= tol:
            return {
                "action": "refuse",
                "message": "%s is where the extrusion starts, so it cannot end there."
                % _cap(_that(words)),
            }
        if direction == "symmetric":
            each = abs(level)
            value = 2.0 * each if measurement == "whole" else each
            return _distance(
                "distance", value, snap_note("distance", value, direction, measurement, what)
            )
        side = side_for(level, direction, options.get("distance", 0.0))
        extent = options.get("extent" if side == 1 else "extent2", "distance")
        if extent == "to_object" and what in ("face", "plane"):
            # To Object chosen: the click picks its object (it stays parametric).
            return _to_object(side, direction, words)
        key = "distance" if side == 1 else "distance2"
        value = level if side == 1 else abs(level)
        return _distance(key, value, snap_note(key, value, direction, measurement, what))
    # A curved or tilted face: Fusion's To Object.
    if direction == "symmetric":
        return {
            "action": "refuse",
            "message": "A symmetric extrude goes the same distance each way, so it cannot end "
            "on %s. Click a flat face parallel to the profile, or choose One Side to extrude To "
            "Object." % words,
        }
    side = side_for(level, direction, options.get("distance", 0.0)) if abs(level) > tol else 1
    return _to_object(side, direction, words)


def snap_note(key, value, direction, measurement="half", what="face"):
    """The dialog's words for a distance set by a click or a snap: "Up to the face: 12.5 mm"
    (Two Sides: "Side Two up to the face: 8 mm"; Symmetric: "... on each side")."""
    words = WHAT.get(what, "the face")
    if direction == "symmetric" and key == "distance":
        if measurement == "whole":
            return "Up to %s: %s in all (%s on each side)" % (
                words,
                length_text(value),
                length_text(value / 2.0),
            )
        return "Up to %s: %s on each side" % (words, length_text(value))
    if direction == "two_sides":
        side = "Side One" if key == "distance" else "Side Two"
        return "%s up to %s: %s" % (side, words, length_text(value))
    return "Up to %s: %s" % (words, length_text(value))


def drag_value(key, level, direction, measurement, tol=FLAT):
    """The dialog value an arrow snaps to while it is dragged over a target at signed height
    `level` (a parallel flat face or a vertex), or None when it cannot end there. key:
    "distance" (side one, or Symmetric's arrow) or "distance2" (side two's arrow, which
    points the other way and takes a positive length)."""
    if abs(level) <= tol:
        return None
    if key == "distance2":
        return -level if -level > tol else None
    if direction == "symmetric":
        return 2.0 * abs(level) if measurement == "whole" else abs(level)
    return level


def _distance(key, value, note):
    return {
        "action": "distance",
        "key": key,
        "value": float(value),
        "extent": "distance",
        "note": note,
    }


def _to_object(side, direction, words):
    if direction == "two_sides":
        note = "Side %s ends on %s (To Object)" % ("One" if side == 1 else "Two", words)
    else:
        note = "Ends on %s (To Object)" % words
    return {"action": "to_object", "side": side, "note": note}


def _that(words):
    """ "the face" -> "that face" (said of a target that was just clicked)."""
    return "that " + words[4:] if words.startswith("the ") else words


def _cap(text):
    return text[:1].upper() + text[1:]
