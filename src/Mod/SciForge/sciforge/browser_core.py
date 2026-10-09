# SPDX-License-Identifier: LGPL-2.1-or-later
"""What goes where in the Fusion-style browser. Pure Python, unit tested.

Input: one dict per document object
    {"name", "label", "type_id", "visible", "body" (name of its body or None), "role"}
Output: a tree of nodes
    {"key", "label", "icon", "kind", "object" (name or None), "visible" (bool or None),
     "children": [...]}

Fusion's browser shows the design's structure, not its history (that is the
timeline): Document Settings, Named Views, Origin, Bodies, Sketches,
Construction. Modeling features (extrudes, fillets...) are not listed.
"""

NAMED_VIEWS = [
    ("Home", "Std_ViewHome"),
    ("Top", "Std_ViewTop"),
    ("Front", "Std_ViewFront"),
    ("Right", "Std_ViewRight"),
]

CONSTRUCTION_TYPES = {
    "PartDesign::Plane",
    "PartDesign::Line",
    "PartDesign::Point",
    "PartDesign::CoordinateSystem",
    "Part::DatumPlane",
    "Part::DatumLine",
    "Part::DatumPoint",
}
SKETCH_TYPES = {"Sketcher::SketchObject"}
BODY_TYPES = {"PartDesign::Body"}
ORIGIN_ROLES = ("X_Axis", "Y_Axis", "Z_Axis", "XY_Plane", "XZ_Plane", "YZ_Plane")
ORIGIN_LABELS = {
    "X_Axis": "X",
    "Y_Axis": "Y",
    "Z_Axis": "Z",
    "XY_Plane": "XY",
    "XZ_Plane": "XZ",
    "YZ_Plane": "YZ",
}


def _node(key, label, icon, kind, obj=None, visible=None, children=None):
    return {
        "key": key,
        "label": label,
        "icon": icon,
        "kind": kind,
        "object": obj,
        "visible": visible,
        "children": children or [],
    }


def _folder(key, label, icon, items):
    """A folder's eye shows 'visible' if any child is visible (Fusion behaviour)."""
    states = [c["visible"] for c in items if c["visible"] is not None]
    visible = any(states) if states else None
    return _node(key, label, icon, "folder", visible=visible, children=items)


def build(doc_label, objects, units="mm", active_body=None):
    """The whole browser tree for a document."""
    bodies, sketches, construction, origin = [], [], [], []
    for obj in objects:
        type_id = obj["type_id"]
        if type_id in BODY_TYPES:
            marker = " ●" if obj["name"] == active_body else ""
            bodies.append(
                _node(
                    "body:" + obj["name"],
                    obj["label"] + marker,
                    "document",
                    "body",
                    obj["name"],
                    obj["visible"],
                )
            )
        elif type_id in SKETCH_TYPES:
            sketches.append(
                _node(
                    "sketch:" + obj["name"],
                    obj["label"],
                    "sk_rectangle",
                    "sketch",
                    obj["name"],
                    obj["visible"],
                )
            )
        elif type_id in CONSTRUCTION_TYPES:
            icon = {"Plane": "offset_plane", "Line": "axis", "Point": "point"}.get(
                type_id.split("::")[1].replace("Datum", ""), "ucs"
            )
            construction.append(
                _node(
                    "construct:" + obj["name"],
                    obj["label"],
                    icon,
                    "construction",
                    obj["name"],
                    obj["visible"],
                )
            )
        elif obj.get("role") in ORIGIN_ROLES and (
            active_body is None or obj["body"] == active_body
        ):
            icon = "offset_plane" if obj["role"].endswith("Plane") else "axis"
            origin.append(
                _node(
                    "origin:" + obj["name"],
                    ORIGIN_LABELS[obj["role"]],
                    icon,
                    "origin",
                    obj["name"],
                    obj["visible"],
                )
            )
    origin.sort(
        key=lambda n: ORIGIN_ROLES.index(
            [r for r in ORIGIN_ROLES if ORIGIN_LABELS[r] == n["label"]][0]
        )
    )
    settings = _node(
        "settings",
        "Document Settings",
        "tl_settings",
        "settings",
        children=[
            _node("settings:units", "Units: %s" % units, "units", "units"),
        ],
    )
    views = _node(
        "views",
        "Named Views",
        "folder",
        "folder",
        children=[
            _node("view:" + label, label.upper(), "nav_lookat", "view", command)
            for label, command in NAMED_VIEWS
        ],
    )
    children = [settings, views]
    if origin:
        children.append(_folder("origin", "Origin", "folder", origin))
    if bodies:
        children.append(_folder("bodies", "Bodies", "folder", bodies))
    if sketches:
        children.append(_folder("sketches", "Sketches", "folder", sketches))
    if construction:
        children.append(_folder("construction", "Construction", "folder", construction))
    return _node("document", doc_label, "document", "document", children=children)


def signature(tree):
    """Cheap value to compare between refreshes."""
    return (
        tree["key"],
        tree["label"],
        tree["visible"],
        tuple(signature(c) for c in tree["children"]),
    )


def walk(tree):
    yield tree
    for child in tree["children"]:
        yield from walk(child)
