# SPDX-License-Identifier: LGPL-2.1-or-later
"""What goes where in the Fusion-style browser. Pure Python, unit tested.

Input: one dict per document object
    {"name", "label", "type_id", "visible", "body" (name of its body or None), "role",
     "sciforge_type" (optional), "error"/"warning" (optional reason), "suppressed" (bool)}
Output: a tree of nodes
    {"key", "label", "icon", "kind", "object" (name or None), "visible" (bool or None),
     "active" (bool), "status" ("ok"|"warning"|"error"|"suppressed"), "tip", "children": [...]}

Fusion's browser shows the design's structure, not its history (that is the
timeline): Document Settings, Named Views, Analysis (once there is one), Origin,
Bodies, Sketches, Construction. Modeling features (extrudes, fillets...) are not
listed. A folder appears once it has something in it, like in Fusion.
"""

NAMED_VIEWS = [
    ("Top", "Std_ViewTop"),
    ("Front", "Std_ViewFront"),
    ("Right", "Std_ViewRight"),
    ("Home", "Std_ViewHome"),
]

# Fusion's unit choices -> FreeCAD unit schema (index in App.Units / Document.UnitSystem)
UNITS = [
    ("mm", "Millimeter", 0),  # Standard (mm, kg, s, deg)
    ("cm", "Centimeter", 4),  # Building Euro (cm, m2, m3)
    ("m", "Meter", 9),  # Meter decimal (m, m2, m3)
    ("in", "Inch", 3),  # Imperial decimal (in, lb)
    ("ft", "Foot", 7),  # Imperial for Civil Eng (ft, lb, mph)
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
ORIGIN_ROLES = ("Origin", "X_Axis", "Y_Axis", "Z_Axis", "XY_Plane", "XZ_Plane", "YZ_Plane")
ORIGIN_LABELS = {
    "Origin": "O",
    "X_Axis": "X",
    "Y_Axis": "Y",
    "Z_Axis": "Z",
    "XY_Plane": "XY",
    "XZ_Plane": "XZ",
    "YZ_Plane": "YZ",
}


def unit_label(schema):
    """'mm' for FreeCAD unit schema 0, ... (None if it is not one of Fusion's)."""
    for short, _long, index in UNITS:
        if index == schema:
            return short
    return None


def is_analysis(obj):
    kind = obj.get("sciforge_type") or ""
    return "Analysis" in kind or "Section" in kind


def _node(key, label, icon, kind, obj=None, visible=None, children=None, **extra):
    node = {
        "key": key,
        "label": label,
        "icon": icon,
        "kind": kind,
        "object": obj,
        "visible": visible,
        "active": False,
        "status": "ok",
        "tip": "",
        "children": children or [],
    }
    node.update(extra)
    return node


def _folder(key, label, items):
    """A folder's eye shows 'visible' if any child is visible (Fusion behaviour)."""
    states = [c["visible"] for c in items if c["visible"] is not None]
    visible = any(states) if states else None
    return _node(key, label, "folder", "folder", visible=visible, children=items)


def _status(obj):
    if obj.get("suppressed"):
        return "suppressed", "Suppressed in the timeline"
    if obj.get("error"):
        return "error", obj["error"]
    if obj.get("warning"):
        return "warning", obj["warning"]
    return "ok", ""


def _item(prefix, obj, icon, kind, **extra):
    status, tip = _status(obj)
    return _node(
        prefix + obj["name"],
        obj["label"],
        icon,
        kind,
        obj["name"],
        obj["visible"],
        status=status,
        tip=tip,
        **extra,
    )


JOINT_TYPES = {"Joint": "joint", "AsBuiltJoint": "joint", "RigidGroup": "rigid_group"}
JOINT_ICONS = {
    "rigid": "joint",
    "revolute": "joint_revolute",
    "slider": "joint_slider",
    "cylindrical": "joint_cylindrical",
    "pinslot": "joint_pinslot",
    "planar": "joint_planar",
    "ball": "joint_ball",
}


def build(doc_label, objects, units="mm", active_body=None, views=()):
    """The whole browser tree for a document. ``views``: names of saved named views."""
    bodies, sketches, construction, origin, analysis = [], [], [], [], []
    joints, joint_origins = [], []
    # Fusion's design has one origin. FreeCAD gives every body its own: show the active
    # body's, else the first body's (a reopened file has no active body yet).
    origin_body = active_body
    if origin_body is None:
        owners = [o["body"] for o in objects if o.get("role") in ORIGIN_ROLES and o["body"]]
        origin_body = owners[0] if owners else None
    for obj in objects:
        type_id = obj["type_id"]
        sciforge_type = obj.get("sciforge_type") or ""
        if type_id in BODY_TYPES:
            grounded = bool(obj.get("grounded"))
            node = _item(
                "body:",
                obj,
                "ground" if grounded else "box",
                "body",
                active=obj["name"] == active_body,
                grounded=grounded,
            )
            if node["active"]:
                node["tip"] = node["tip"] or "Active body: new features go here"
            if grounded:
                node["tip"] = (
                    node["tip"] + "; " if node["tip"] else ""
                ) + "Grounded: it cannot move"
            bodies.append(node)
        elif sciforge_type in JOINT_TYPES:
            kind = JOINT_TYPES[sciforge_type]
            icon = (
                "rigid_group"
                if kind == "rigid_group"
                else JOINT_ICONS.get(obj.get("joint_type"), "joint")
            )
            if sciforge_type == "AsBuiltJoint":
                icon = "joint_asbuilt"
            node = _item("joint:", obj, icon, kind, joint_type=obj.get("joint_type"))
            if obj.get("describe"):
                node["tip"] = node["tip"] or obj["describe"]
            joints.append(node)
        elif sciforge_type == "JointOrigin":
            joint_origins.append(_item("joint_origin:", obj, "joint_origin", "joint_origin"))
        elif type_id in SKETCH_TYPES:
            sketches.append(_item("sketch:", obj, "sk_rectangle", "sketch"))
        elif type_id in CONSTRUCTION_TYPES:
            icon = {"Plane": "offset_plane", "Line": "axis", "Point": "point"}.get(
                type_id.split("::")[1].replace("Datum", ""), "ucs"
            )
            construction.append(_item("construct:", obj, icon, "construction"))
        elif is_analysis(obj):
            analysis.append(_item("analysis:", obj, "section", "analysis"))
        elif obj.get("role") in ORIGIN_ROLES and (
            origin_body is None or obj["body"] == origin_body
        ):
            role = obj["role"]
            icon = (
                "point"
                if role == "Origin"
                else ("offset_plane" if role.endswith("Plane") else "axis")
            )
            origin.append(
                _node(
                    "origin:" + obj["name"],
                    ORIGIN_LABELS[role],
                    icon,
                    "origin",
                    obj["name"],
                    obj["visible"],
                    role=role,
                )
            )
    origin.sort(key=lambda n: ORIGIN_ROLES.index(n["role"]))
    settings = _node(
        "settings",
        "Document Settings",
        "tl_settings",
        "settings",
        children=[
            _node(
                "settings:units",
                "Units: %s" % units,
                "units",
                "units",
                tip="Click to change the units of this design",
            ),
        ],
    )
    named = [
        _node("view:" + label, label.upper(), "nav_lookat", "view", command)
        for label, command in NAMED_VIEWS
    ]
    named += [_node("saved_view:" + name, name, "nav_lookat", "saved_view", name) for name in views]
    children = [settings, _node("views", "Named Views", "folder", "views", children=named)]
    if analysis:
        children.append(_folder("analysis", "Analysis", analysis))
    if origin:
        children.append(_folder("origin", "Origin", origin))
    if bodies:
        children.append(_folder("bodies", "Bodies", bodies))
    if joints:
        children.append(_folder("joints", "Joints", joints))
    if joint_origins:
        children.append(_folder("joint_origins", "Joint Origins", joint_origins))
    if sketches:
        children.append(_folder("sketches", "Sketches", sketches))
    if construction:
        children.append(_folder("construction", "Construction", construction))
    return _node("document", doc_label, "document", "document", children=children)


def signature(tree):
    """Cheap value to compare between refreshes."""
    return (
        tree["key"],
        tree["label"],
        tree["visible"],
        tree["active"],
        tree["status"],
        tree["tip"],
        tuple(signature(c) for c in tree["children"]),
    )


def walk(tree):
    yield tree
    for child in tree["children"]:
        yield from walk(child)


def find(tree, key):
    for node in walk(tree):
        if node["key"] == key:
            return node
    return None


def node_for_object(tree, name, body_of=None):
    """Key of the node that shows object ``name``: itself (sketch, body, plane...),
    else its body (a feature lives in the timeline, its result in the body)."""
    for node in walk(tree):
        if node["object"] == name and node["kind"] not in ("view", "saved_view"):
            return node["key"]
    if body_of:
        for node in walk(tree):
            if node["kind"] == "body" and node["object"] == body_of:
                return node["key"]
    return None


def path_to(tree, key, _path=None):
    """Keys of the folders above ``key`` (to expand them), or None if not found."""
    _path = _path or []
    if tree["key"] == key:
        return _path
    for child in tree["children"]:
        found = path_to(child, key, _path + [tree["key"]])
        if found is not None:
            return found
    return None


# What the right-click menu offers per kind of node, in Fusion's order. The UI
# leaves out entries that do not apply (e.g. no Delete for an origin plane).
MENUS = {
    "document": ["Show All Bodies", "Show All Sketches", "Hide All Sketches", "-", "Rename"],
    "units": ["Change Active Units"],
    "settings": ["Change Active Units"],
    "views": ["New Named View"],
    "view": ["Go to View"],
    "saved_view": ["Go to View", "-", "Rename", "Delete"],
    "folder": ["Show/Hide"],
    "origin": ["Show/Hide", "-", "Create Sketch"],
    "body": [
        "Activate Body",
        "-",
        "Ground",
        "-",
        "Show/Hide",
        "Isolate",
        "Find in Window",
        "Find in Timeline",
        "-",
        "Rename",
        "Delete",
    ],
    "joint": [
        "Edit Joint",
        "Edit Joint Limits",
        "Drive Joints",
        "Animate Joint",
        "-",
        "Show/Hide",
        "Suppress",
        "Find in Timeline",
        "-",
        "Rename",
        "Delete",
    ],
    "rigid_group": [
        "Edit Rigid Group",
        "-",
        "Suppress",
        "Find in Timeline",
        "-",
        "Rename",
        "Delete",
    ],
    "joint_origin": [
        "Edit Joint Origin",
        "-",
        "Show/Hide",
        "Find in Timeline",
        "-",
        "Rename",
        "Delete",
    ],
    "sketch": [
        "Edit Sketch",
        "-",
        "Show/Hide",
        "Look At",
        "Find in Window",
        "Find in Timeline",
        "-",
        "Rename",
        "Delete",
    ],
    "construction": [
        "Edit Feature",
        "-",
        "Show/Hide",
        "Find in Window",
        "Find in Timeline",
        "-",
        "Rename",
        "Delete",
    ],
    "analysis": ["Edit Feature", "-", "Show/Hide", "-", "Rename", "Delete"],
}


def menu_for(node):
    """Right-click entries for a node ("-" is a separator)."""
    entries = list(MENUS.get(node["kind"], []))
    if node["kind"] == "folder" and node["visible"] is None:
        entries = []
    return entries
