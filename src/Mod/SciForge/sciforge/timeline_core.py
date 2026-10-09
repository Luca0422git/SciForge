"""Timeline model: turns a PartDesign body's feature list into timeline items.
Pure Python, no FreeCAD/Qt, so it is unit tested outside FreeCAD."""

from dataclasses import dataclass

# Fusion-style names for FreeCAD feature types.
KIND_BY_TYPEID = {
    "Sketcher::SketchObject": "sketch",
    "PartDesign::Pad": "extrude",
    "PartDesign::Pocket": "extrude",  # Fusion calls cut extrudes "Extrude" too
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
    "SciForge::PressPull": "presspull",
    "SciForge::Extrude": "extrude",
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
    "presspull": "Press Pull",
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


# Timeline icons, by kind (files in icons/ui, made by tools/sciforge/make_icons.py).
KIND_ICONS = {
    "sketch": "sk_rectangle",
    "extrude": "extrude",
    "cut": "extrude",
    "revolve": "revolve",
    "groove": "revolve",
    "hole": "hole",
    "fillet": "fillet",
    "chamfer": "chamfer",
    "draft": "draft",
    "shell": "shell",
    "presspull": "press_pull",
    "pattern": "pattern_rect",
    "loft": "loft",
    "sweep": "sweep",
    "datum": "offset_plane",
    "primitive": "box",
    "other": "workspace_design",
}


def icon_for(kind):
    return KIND_ICONS.get(kind, KIND_ICONS["other"])


def step_target(items, where):
    """Feature to make the Tip for the playback buttons.

    where: "start" | "prev" | "next" | "end". Only solid features can be a Tip,
    so steps skip sketches and datums. Returns None when there is nowhere to go.
    """
    solids = [i for i, item in enumerate(items) if is_solid(item.kind)]
    if not solids:
        return None
    tips = [i for i, item in enumerate(items) if item.state == "tip"]
    current = tips[0] if tips else solids[-1]
    if where == "start":
        target = solids[0]
    elif where == "end":
        target = solids[-1]
    elif where == "prev":
        earlier = [i for i in solids if i < current]
        target = earlier[-1] if earlier else None
    elif where == "next":
        later = [i for i in solids if i > current]
        target = later[0] if later else None
    else:
        raise ValueError("unknown step %r" % where)
    if target is None or target == current:
        return None
    return items[target].name


def drop_target(items, slot):
    """Feature to make the Tip when the marker is dropped after `slot` items (0..len).

    The marker can only sit after a solid feature, so it snaps back to the nearest
    one on the left (or to the first solid if dropped before everything).
    Returns None when nothing changes."""
    solids = [i for i, item in enumerate(items) if is_solid(item.kind)]
    if not solids:
        return None
    left = [i for i in solids if i < slot]
    target = left[-1] if left else solids[0]
    if items[target].state == "tip":
        return None
    if all(item.state != "tip" for item in items) and target == solids[-1]:
        return None  # already at the end
    return items[target].name
