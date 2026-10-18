# SPDX-License-Identifier: LGPL-2.1-or-later
"""The sketch areas FreeCAD could not make, added by SciForge.

FreeCAD 1.1.4 makes a sketch's areas ("InternalFaceN", its MakeInternals option) with a
wire joiner that gives up on some layouts and then makes no area at all: a line through
a circle inside a rectangle or on a face (Luca: a line across the face to find its
middle, a circle on it; Extrude then found nothing to pick and took the whole face), or
an arc ending tangent in the middle of a line. Fusion makes every closed area a profile.

SciForge already finds every area itself (sketch_regions, the sketch shading). Right
after FreeCAD computes a sketch, this module adds the areas FreeCAD left out to the
sketch's InternalShape. The areas FreeCAD made keep their numbers and come first, so
existing extrudes keep their profiles; Extrude, Revolve, Press Pull and the shading read
the added ones like FreeCAD's own. Nothing in the sketch itself changes, and the file
opens in FreeCAD without SciForge (the areas are saved with it).

No Qt: also used headless (the golden models), installed by extrude.ensure_regions.
"""

import FreeCAD as App

MAX_EDGES = 400  # larger sketches are left as FreeCAD made them (time)
TOL = 1e-6


def missing_areas(sketch):
    """The faces (sketch coordinates) of the areas the sketch's curves close that its
    InternalShape lacks; [] when FreeCAD made them all (or on any doubt)."""
    from . import sketch_regions

    edges = sketch_regions.sketch_edges(sketch)
    if not edges or len(edges) > MAX_EDGES:
        return []
    shape = sketch.InternalShape
    have = [] if shape.isNull() else list(shape.Faces)
    found = []
    for face in sketch_regions.regions(edges):
        point = sketch_regions.inner_point(face)
        if point is None:
            continue
        if not any(h.isInside(point, TOL, True) for h in have):
            found.append(face)
    return found


def complete(sketch):
    """Add the areas FreeCAD did not make to the sketch's InternalShape. Returns how many
    were added. The sketch is not marked as changed by it."""
    import Part

    if not getattr(sketch, "MakeInternals", False):
        return 0
    state = getattr(sketch, "State", [])
    if "Invalid" in state or "Error" in state:
        return 0
    missing = missing_areas(sketch)
    if not missing:
        return 0
    touched = "Touched" in state
    shape = sketch.InternalShape
    sketch.InternalShape = Part.Compound(([] if shape.isNull() else [shape]) + missing)
    if not touched:
        sketch.purgeTouched()
    return len(missing)


class Filler:
    """Document observer: completes every sketch's areas right after FreeCAD computed it,
    before the steps that use them are computed."""

    def slotRecomputedObject(self, obj):
        try:
            if obj.isDerivedFrom("Sketcher::SketchObject"):
                added = complete(obj)
                if added:
                    from . import log

                    log(
                        "sketch areas: FreeCAD could not make %d area%s of %s; SciForge "
                        "added %s" % (added, "" if added == 1 else "s", obj.Label,
                                      "it" if added == 1 else "them")
                    )
        except Exception as exc:
            from . import warn

            warn("sketch areas of %s: %s" % (getattr(obj, "Label", "?"), exc))


_filler = {"observer": None}


def install():
    """Watch every document (once)."""
    if _filler["observer"] is None:
        _filler["observer"] = Filler()
        App.addDocumentObserver(_filler["observer"])
