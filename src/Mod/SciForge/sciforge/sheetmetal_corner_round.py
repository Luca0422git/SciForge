# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's sheet metal Fillet and Chamfer (SHEET METAL > MODIFY, Sep 2026): round or chamfer
the corners of the plates, i.e. only the edges that run straight through the sheet's thickness,
so the part can still be laid flat (the flat pattern keeps the rounds as arcs). FreeCAD side,
no Qt: the dialog (sheetmetal_corner_round_ui.py) and the golden-model builder call make().

Fillet takes radius sets (edges + a radius each, like Fusion's sets; at least one); Chamfer
takes one equal distance per set. Any other edge (along a face, around a bend) is refused
with the reason. Sources: docs/sciforge/dev/research/fusion-sheet-metal.md 2.10.
"""

import json

import FreeCAD as App

from . import bodies, log, sheetmetal_bend as sb, sheetmetal_bend_core as core

V = App.Vector
TYPE = "PartDesign::FeaturePython"
KIND_FILLET = "SheetMetalFillet"
KIND_CHAMFER = "SheetMetalChamfer"
META = "SciForgeSmRound"


def thickness_edge(shape, edge_name, thickness):
    """'' when the edge runs straight through the sheet, else why it cannot be picked."""
    import Part

    try:
        edge = shape.getElement(edge_name)
    except Exception:
        return "%s is not an edge of the body any more." % edge_name
    if not isinstance(edge.Curve, (Part.Line, Part.LineSegment)):
        return "Only the edges through the sheet's thickness can be rounded (this one is curved)."
    a, b = edge.Vertexes[0].Point, edge.Vertexes[-1].Point
    direction = b - a
    if direction.Length < 1e-9:
        return "That edge has no length."
    direction.normalize()
    ends = 0
    for face in shape.Faces:
        if not sb.is_plane(face):
            continue
        n = sb.plane_normal(face)
        if abs(abs(n.dot(direction)) - 1.0) > 1e-6:
            continue
        for p in (a, b):
            if face.isInside(p, 1e-6, True):
                ends += 1
    normal = (direction.x, direction.y, direction.z)
    if ends < 2 or not core.is_thickness_edge(normal, normal, edge.Length, thickness):
        return (
            "Only the edges through the sheet's thickness (the corners of a plate) can be "
            "rounded or chamfered in sheet metal."
        )
    return ""


def round_shape(shape, kind, sets, thickness):
    """The solid with every set's edges filleted (kind 'fillet', value = radius) or chamfered
    ('chamfer', value = distance). sets: [{"edges": [names], "value": mm}]."""
    if not sets or not any(s.get("edges") for s in sets):
        raise sb.SheetMetalError(
            "Pick the corner edges to %s." % ("round" if kind == "fillet" else "chamfer")
        )
    targets = []
    for entry in sets:
        value = float(entry.get("value", 0.0))
        if value <= 0:
            raise sb.SheetMetalError(
                "Each %s must be more than 0." % ("radius" if kind == "fillet" else "distance")
            )
        for name in entry.get("edges", []):
            why = thickness_edge(shape, name, thickness)
            if why:
                raise sb.SheetMetalError(why)
            edge = shape.getElement(name)
            targets.append((edge.CenterOfMass, value))
    result = shape
    for point, value in targets:
        found = None
        for edge in result.Edges:
            if (edge.CenterOfMass - point).Length < 1e-6:
                found = edge
                break
        if found is None:
            raise sb.SheetMetalError("Two corners are too close together for these sizes.")
        try:
            if kind == "fillet":
                result = result.makeFillet(value, [found])
            else:
                result = result.makeChamfer(value, [found])
        except Exception:
            raise sb.SheetMetalError(
                "This %s is too big for the corner; make it smaller."
                % ("radius" if kind == "fillet" else "distance")
            )
    return sb.one_solid(result, "This %s" % kind)


class RoundFeature:
    """Saved in files as "sciforge.sheetmetal_corner_round.RoundFeature": keep the name."""

    def __init__(self, obj, kind="fillet"):
        obj.Proxy = self
        self.ensure_properties(obj, kind)

    @staticmethod
    def ensure_properties(obj, kind=None):
        def add(prop, name, doc):
            if name not in obj.PropertiesList:
                obj.addProperty(prop, name, "Sheet Metal", doc)
                return True
            return False

        add("App::PropertyLinkSub", "Edges", "The corner edges (through the thickness)")
        if add("App::PropertyLength", "Size", "Radius (Fillet) or distance (Chamfer) of set 1"):
            obj.Size = 2.0
        if add("App::PropertyBool", "Refine", "Merge faces that end up in one plane"):
            obj.Refine = True
        if kind is not None:
            bodies.mark(obj, KIND_FILLET if kind == "fillet" else KIND_CHAMFER)

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        try:
            obj.Shape = build(obj)
        except Exception:
            bodies.pass_through(obj)
            raise

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def kind_of(obj):
    return "chamfer" if bodies.kind(obj) == KIND_CHAMFER else "fillet"


def sets_of(obj):
    """[{"edges": [...], "value": mm}] of a step: the sets kept in META, their edges by name
    in the Edges link (set i owns the names listed for it)."""
    meta = bodies.load_meta(obj, META)
    link = obj.Edges
    names = list(link[1]) if link else []
    sets = meta.get("sets")
    if not sets:
        return [{"edges": names, "value": float(obj.Size)}]
    out = []
    for i, entry in enumerate(sets):
        edges = [n for n in entry.get("edges", []) if n in names]
        value = float(obj.Size) if i == 0 else float(entry.get("value", obj.Size))
        out.append({"edges": edges, "value": value})
    return out


def build(obj):
    base = obj.BaseFeature
    if base is None or base.Shape.isNull() or not base.Shape.Solids:
        raise sb.SheetMetalError("There is no sheet before this step.")
    body = bodies.body_of(obj)
    thickness = sb.rule_values(body)[0]
    shape = base.Shape.copy()
    shape.Placement = App.Placement()
    result = round_shape(shape, kind_of(obj), sets_of(obj), thickness)
    if obj.Refine:
        try:
            result = result.removeSplitter()
        except Exception:
            pass
    return result


def apply(obj, base, sets):
    names = []
    for entry in sets:
        for n in entry.get("edges", []):
            if n not in names:
                names.append(n)
    obj.Edges = (base, names)
    obj.Size = float(sets[0].get("value", 2.0)) if sets else 2.0
    bodies.save_meta(
        obj,
        META,
        {
            "sets": [
                {"edges": list(s.get("edges", [])), "value": float(s.get("value", 0))} for s in sets
            ]
        },
    )


def make(body, base, kind, sets, name=None):
    """A sheet metal Fillet / Chamfer step. sets: [{"edges": [...], "value": mm}]."""
    obj = bodies.insert_after_tip(
        body, TYPE, name or ("SMFillet" if kind == "fillet" else "SMChamfer")
    )
    RoundFeature(obj, kind)
    obj.BaseFeature = base
    apply(obj, base, sets)
    _view(obj)
    log("sheet metal %s %s made" % (kind, obj.Name))
    return obj


def read(obj):
    return obj.BaseFeature, kind_of(obj), sets_of(obj)


def describe(sets):
    return json.dumps(sets)


def _view(obj):
    if not App.GuiUp:
        return
    try:
        from . import sheetmetal_corner_round_ui

        sheetmetal_corner_round_ui.ViewProviderRound(obj.ViewObject)
    except Exception:
        pass
