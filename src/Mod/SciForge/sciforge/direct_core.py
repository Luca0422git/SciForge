# SPDX-License-Identifier: LGPL-2.1-or-later
"""Design history on/off and base features as plain data (Fusion's Capture Design History
and Create Base Feature). Pure Python: no FreeCAD, no Qt, unit tested.

How SciForge maps them onto FreeCAD's PartDesign (direct.py does it):

* Every body keeps being a PartDesign Body, so every SciForge command keeps working.
* A body "without history" is a body whose solid is one frozen step: FreeCAD's
  PartDesign::FeatureBase at the start of the body, linked to a hidden plain Part::Feature
  that stores the solid in the file (its "base shape").
* A design without history ("direct") bakes every command into the bodies' base shapes
  when the command is OK'd: the new steps are removed again and the base shape takes the
  result (freeze). A base feature session does the same for its own bodies only.

The functions here decide *what* to freeze; direct.py does it on the document.

A body is described as rows in its own order (``Body.Group``), each
    {"name", "solid" (a step that makes the solid), "base" (FreeCAD's FeatureBase),
     "frozen" (a FeatureBase whose base shape is plain data, not another feature)}
"""

CAPTURE_ON = "Capture Design History"
CAPTURE_OFF = "Do Not Capture Design History"
BASE_TITLE = "Base Feature"


def history_menu_label(captures):
    """The entry Fusion shows in the design's right-click menu: the one that switches."""
    return CAPTURE_OFF if captures else CAPTURE_ON


def base_index(rows):
    """Index of the body's base step (FreeCAD keeps it first), or None."""
    if rows and rows[0].get("base"):
        return 0
    return None


def steps_to_freeze(rows, tip=None, fresh=None):
    """The solid steps a freeze takes into the base shape: those after the base up to the
    tip (the history marker) included; all solid steps up to the tip when the body has no
    base yet (the first freeze makes one). Steps after the tip stay (an edited base feature:
    they build on the new base afterwards).

    ``fresh`` (a base feature session): only steps made since it started may go in, and only
    a run of them right after the base: an older step in between (a step after the base
    feature that the marker was rolled past) ends the run, it keeps its place in the
    timeline. The last name returned is the step whose solid the base takes."""
    if tip is not None and tip not in [r["name"] for r in rows]:
        return []  # a tip outside the body (should not happen): change nothing
    start = base_index(rows)
    found = []
    for i, row in enumerate(rows):
        if start is not None and i <= start:
            continue
        if row.get("solid") and not row.get("base"):
            if fresh is not None and row["name"] not in fresh:
                break
            found.append(row["name"])
        if tip is not None and row["name"] == tip:
            break
    return found


def needs_freeze(rows, tip=None, fresh=None):
    """True when the body has steps to bake, or a base that still follows another feature
    (a copy, a split piece, a mesh conversion): a body without history is one frozen step."""
    if steps_to_freeze(rows, tip, fresh):
        return True
    start = base_index(rows)
    return start is not None and not rows[start].get("frozen")


def session_members(known, current, members):
    """Bodies a base feature session bakes: its own bodies plus every body made since the
    session started (Fusion: what is made inside a base feature belongs to it). ``known``:
    the bodies that existed at the start; ``current``: the bodies now."""
    out = [name for name in current if name in members]
    out += [name for name in current if name not in known and name not in out]
    return out


def next_base_id(existing):
    """A new base feature id ("bf1", "bf2"...) not in ``existing``."""
    n = 1
    while "bf%d" % n in set(existing):
        n += 1
    return "bf%d" % n


def marker_after_edit(saved_at_end, saved_count, solid_count):
    """Where the marker goes when a base feature edit is finished: back to the end when it
    was there, else back to the same number of solid steps (never past the end)."""
    if saved_at_end:
        return solid_count
    return max(1, min(int(saved_count), solid_count))


# -- Delete Face (heal) -----------------------------------------------------------------------
FACE_KINDS = {
    "Plane": "flat",
    "Cylinder": "round",
    "Cone": "conical",
    "Sphere": "spherical",
    "Toroid": "rounded",
    "BSplineSurface": "curved",
    "SurfaceOfRevolution": "curved",
    "SurfaceOfExtrusion": "curved",
    "OffsetSurface": "curved",
}


def delete_refusal(face_kinds, count_total):
    """What Delete says when the faces around the picked ones cannot close the gap
    (OpenCASCADE's defeaturing gives the solid back unchanged or fails). ``face_kinds``:
    the surface type names of the picked faces; ``count_total``: faces of the body."""
    n = len(face_kinds)
    if n >= count_total:
        return "Deleting every face would leave nothing. Delete the body instead."
    what = "This face" if n == 1 else "These %d faces" % n
    kinds = {FACE_KINDS.get(k, "curved") for k in face_kinds}
    hint = (
        "Pick all the faces of the feature together (a boss's sides and top, a pocket's "
        "walls and floor), or use Replace Face to move it onto another face or plane."
    )
    if kinds == {"flat"} and n == 1:
        hint = (
            "Its neighbours run parallel or away from each other, so nothing can grow into "
            "its place. Pick the whole feature's faces together, or use Replace Face or "
            "Press Pull to move it instead."
        )
    return "%s cannot be deleted: the faces around %s cannot be extended to close the gap. %s" % (
        what,
        "it" if n == 1 else "them",
        hint,
    )
