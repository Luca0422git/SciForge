"""Timeline model: turns a PartDesign body's feature list into timeline items.
Pure Python, no FreeCAD/Qt, so it is unit tested outside FreeCAD."""
from dataclasses import dataclass

# Fusion-style names for FreeCAD feature types.
KIND_BY_TYPEID = {
    "Sketcher::SketchObject": "sketch",
    "PartDesign::Pad": "extrude",
    "PartDesign::Pocket": "cut",
    "PartDesign::Revolution": "revolve",
    "PartDesign::Groove": "groove",
    "PartDesign::Hole": "hole",
    "PartDesign::Fillet": "fillet",
    "PartDesign::Chamfer": "chamfer",
    "PartDesign::Draft": "draft",
    "PartDesign::Thickness": "shell",
    "PartDesign::Mirrored": "pattern",
    "PartDesign::LinearPattern": "pattern",
    "PartDesign::PolarPattern": "pattern",
    "PartDesign::MultiTransform": "pattern",
    "PartDesign::AdditiveLoft": "loft",
    "PartDesign::SubtractiveLoft": "loft",
    "PartDesign::AdditivePipe": "sweep",
    "PartDesign::SubtractivePipe": "sweep",
    "PartDesign::AdditiveHelix": "sweep",
    "PartDesign::SubtractiveHelix": "sweep",
    "PartDesign::Plane": "datum",
    "PartDesign::Line": "datum",
    "PartDesign::Point": "datum",
    "PartDesign::CoordinateSystem": "datum",
    "PartDesign::ShapeBinder": "datum",
    "PartDesign::SubShapeBinder": "datum",
}

KIND_TITLES = {
    "sketch": "Sketch",
    "extrude": "Extrude",
    "cut": "Cut",
    "revolve": "Revolve",
    "groove": "Groove",
    "hole": "Hole",
    "fillet": "Fillet",
    "chamfer": "Chamfer",
    "draft": "Draft",
    "shell": "Shell",
    "pattern": "Pattern",
    "loft": "Loft",
    "sweep": "Sweep",
    "datum": "Construct",
    "primitive": "Primitive",
    "other": "Feature",
}

# Kinds that change the solid. Only these can be a body's Tip.
NON_SOLID_KINDS = {"sketch", "datum"}


def classify(type_id):
    kind = KIND_BY_TYPEID.get(type_id)
    if kind:
        return kind
    if type_id.startswith(("PartDesign::Additive", "PartDesign::Subtractive")):
        return "primitive"
    return "other"


def is_solid(kind):
    return kind not in NON_SOLID_KINDS


@dataclass(frozen=True)
class Item:
    index: int
    name: str
    label: str
    type_id: str
    kind: str
    title: str
    state: str  # "done" | "tip" | "pending" | "rolled_back"


def build_items(features, tip_name):
    """features: list of {"name","label","type_id"} in body order."""
    kinds = [classify(f["type_id"]) for f in features]
    solid_indexes = [i for i, k in enumerate(kinds) if is_solid(k)]
    last_solid = solid_indexes[-1] if solid_indexes else None

    names = [f["name"] for f in features]
    if tip_name in names:
        tip_index = names.index(tip_name)
    else:
        tip_index = last_solid

    counts = {}
    items = []
    for i, feature in enumerate(features):
        kind = kinds[i]
        counts[kind] = counts.get(kind, 0) + 1
        if tip_index is None or i < tip_index:
            state = "done"
        elif i == tip_index:
            state = "tip"
        elif tip_index == last_solid:
            state = "pending"  # e.g. a fresh sketch waiting for its extrude
        else:
            state = "rolled_back"
        items.append(
            Item(
                index=i,
                name=feature["name"],
                label=feature.get("label", feature["name"]),
                type_id=feature["type_id"],
                kind=kind,
                title="%s %d" % (KIND_TITLES[kind], counts[kind]),
                state=state,
            )
        )
    return items


def rollback_target(items, index):
    """Name of the solid feature to set as Tip for 'roll back to here'.

    Sketches and datums cannot be a Tip, so walk back to the nearest solid.
    Returns None when there is nothing valid (or it is already the tip).
    """
    for i in range(index, -1, -1):
        if is_solid(items[i].kind):
            return None if items[i].state == "tip" else items[i].name
    return None


def last_solid_name(items):
    for item in reversed(items):
        if is_solid(item.kind):
            return item.name
    return None


def can_roll_forward(items):
    return any(item.state == "rolled_back" for item in items)


def signature(items, body_name):
    """Cheap value to compare between refreshes to detect any change."""
    return (body_name, tuple((i.name, i.label, i.kind, i.state) for i in items))
