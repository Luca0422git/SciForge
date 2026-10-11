# SPDX-License-Identifier: LGPL-2.1-or-later
"""Appearance (how a body or a face looks) and the look a Physical Material gives a body.
No Qt: appearance_ui.py is the dialog; material.py uses set_material_look().

The look is stored in the design (a hidden "SciForgeAppearance" property of the body, JSON),
so it is saved with the file and every change is undone with Ctrl+Z like any other step:

  {"body": look or null,          Appearance given to the whole body
   "material": look or null,      the look of its Physical Material (below "body")
   "faces": [{"point": [x, y, z], "normal": [x, y, z], "look": look}, ...]}
                                  Appearance given to single faces (body coordinates)

A look: {"key", "label", "color": [r, g, b] (0..1), "shininess" (0..1), "transparency" (0..1)}.

FreeCAD keeps colours on each step's view, and a step added later starts grey; sync() puts
the stored looks on every step of every body after each recompute and undo (bodies_gui.Watch).
A face keeps its look while it survives later steps: faces are found again by a point on them
and their direction (Fusion keeps a face's appearance the same way across edits).
"""
import json

import FreeCAD as App

from . import bodies

PROP = "SciForgeAppearance"
_COLORED = {}  # document name -> {names of bodies given a look on screen}
_APPLIED = {}  # (document, step) -> what the step's look was made from (skips repeats)

# (key, label, group, (r, g, b), shininess, transparency)
LIBRARY = [
    ("steel_satin", "Steel, satin", "Metal", (0.62, 0.63, 0.65), 0.45, 0.0),
    ("steel_polished", "Steel, polished", "Metal", (0.76, 0.77, 0.79), 0.9, 0.0),
    ("stainless", "Stainless steel, brushed", "Metal", (0.70, 0.71, 0.72), 0.6, 0.0),
    ("aluminium_satin", "Aluminium, satin", "Metal", (0.80, 0.81, 0.83), 0.5, 0.0),
    ("aluminium_black", "Aluminium, anodized black", "Metal", (0.13, 0.13, 0.14), 0.5, 0.0),
    ("aluminium_blue", "Aluminium, anodized blue", "Metal", (0.16, 0.32, 0.62), 0.5, 0.0),
    ("titanium", "Titanium", "Metal", (0.55, 0.55, 0.57), 0.45, 0.0),
    ("cast_iron", "Iron, cast", "Metal", (0.30, 0.30, 0.31), 0.2, 0.0),
    ("brass", "Brass", "Metal", (0.78, 0.62, 0.30), 0.7, 0.0),
    ("copper", "Copper", "Metal", (0.80, 0.47, 0.33), 0.7, 0.0),
    ("chrome", "Chrome", "Metal", (0.86, 0.87, 0.89), 1.0, 0.0),
    ("plastic_black", "Glossy plastic, black", "Plastic", (0.06, 0.06, 0.06), 0.8, 0.0),
    ("plastic_white", "Glossy plastic, white", "Plastic", (0.93, 0.93, 0.92), 0.8, 0.0),
    ("plastic_grey", "Glossy plastic, grey", "Plastic", (0.47, 0.48, 0.50), 0.8, 0.0),
    ("plastic_red", "Glossy plastic, red", "Plastic", (0.80, 0.08, 0.08), 0.8, 0.0),
    ("plastic_orange", "Glossy plastic, orange", "Plastic", (0.95, 0.45, 0.05), 0.8, 0.0),
    ("plastic_yellow", "Glossy plastic, yellow", "Plastic", (0.95, 0.80, 0.10), 0.8, 0.0),
    ("plastic_green", "Glossy plastic, green", "Plastic", (0.10, 0.55, 0.20), 0.8, 0.0),
    ("plastic_blue", "Glossy plastic, blue", "Plastic", (0.10, 0.28, 0.80), 0.8, 0.0),
    ("plastic_purple", "Glossy plastic, purple", "Plastic", (0.45, 0.18, 0.65), 0.8, 0.0),
    ("plastic_matte_black", "Matte plastic, black", "Plastic", (0.09, 0.09, 0.09), 0.1, 0.0),
    ("plastic_matte_white", "Matte plastic, white", "Plastic", (0.88, 0.88, 0.86), 0.1, 0.0),
    ("plastic_clear", "Clear plastic", "Plastic", (0.85, 0.90, 0.95), 0.9, 0.65),
    ("rubber_black", "Rubber, black", "Rubber", (0.08, 0.08, 0.08), 0.05, 0.0),
    ("rubber_grey", "Rubber, grey", "Rubber", (0.38, 0.38, 0.39), 0.05, 0.0),
    ("glass_clear", "Glass, clear", "Glass", (0.80, 0.90, 0.92), 0.95, 0.75),
    ("wood_light", "Wood, light", "Other", (0.76, 0.60, 0.42), 0.2, 0.0),
    ("wood_dark", "Wood, dark", "Other", (0.42, 0.27, 0.16), 0.2, 0.0),
]


def _look(row):
    key, label, group, color, shininess, transparency = row
    return {
        "key": key,
        "label": label,
        "group": group,
        "color": list(color),
        "shininess": shininess,
        "transparency": transparency,
    }


def library():
    return [_look(row) for row in LIBRARY]


def find(key):
    for row in LIBRARY:
        if row[0] == key:
            return _look(row)
    return None


def custom(color, shininess=0.5, transparency=0.0):
    """A look in any colour (Fusion: a custom appearance). color: (r, g, b) 0..1."""
    r, g, b = [max(0.0, min(1.0, float(c))) for c in color]
    text = "#%02X%02X%02X" % (round(r * 255), round(g * 255), round(b * 255))
    return {
        "key": "custom" + text,
        "label": "Custom " + text,
        "group": "Custom",
        "color": [r, g, b],
        "shininess": shininess,
        "transparency": transparency,
    }


def hex_color(look):
    r, g, b = look["color"]
    return "#%02X%02X%02X" % (round(r * 255), round(g * 255), round(b * 255))


def same(a, b):
    if a is None or b is None:
        return a is b
    return a.get("key") == b.get("key") and [round(c, 4) for c in a["color"]] == [
        round(c, 4) for c in b["color"]
    ]


# -- stored in the design --------------------------------------------------------------------------
def get(body):
    try:
        data = json.loads(getattr(body, PROP, "") or "{}")
    except Exception:
        data = {}
    data.setdefault("body", None)
    data.setdefault("material", None)
    data.setdefault("faces", [])
    return data


def _put(body, data):
    if not any((data.get("body"), data.get("material"), data.get("faces"))):
        text = ""
    else:
        text = json.dumps(data, sort_keys=True)
    if PROP not in body.PropertiesList:
        if not text:
            return
        body.addProperty("App::PropertyString", PROP, "Base", "Appearance (SciForge)", 4)
    if getattr(body, PROP) != text:
        setattr(body, PROP, text)


def set_body(body, look):
    """Give the whole body a look (its faces' own looks are replaced, as in Fusion)."""
    data = get(body)
    data["body"] = look
    data["faces"] = []
    _put(body, data)


def set_material_look(body, look):
    data = get(body)
    data["material"] = look
    _put(body, data)


def set_faces(body, feature, names, look):
    """Give single faces a look. `feature`: the step the face names belong to (the Tip)."""
    data = get(body)
    frame = frame_of(feature)
    for name in names:
        try:
            face = feature.Shape.getElement(name)
        except Exception:
            continue
        point, normal = _probe(face)
        data["faces"] = [f for f in data["faces"] if not _matches(face, f, _shift(frame, f))]
        data["faces"].append(
            {"point": list(point), "normal": list(normal), "look": look, "frame": _save(frame)}
        )
    _put(body, data)


# -- faces moved by Move steps ---------------------------------------------------------------------
def _move_of(step, body_place):
    """The movement a Move step gives the body's solid, in body coordinates, or None."""
    from . import move

    if not move.is_move(step) or move.is_copy(step) or bodies.is_suppressed(step):
        return None
    movement = step.Movement
    if body_place.isIdentity():
        return movement
    return body_place.inverse().multiply(movement).multiply(body_place)


def frame_of(step):
    """How the Move steps up to and including `step` have moved its body's solid (body
    coordinates): a face given a look before a Move is found again after it, moved."""
    place = App.Placement()
    body = bodies.body_of(step)
    if body is None:
        return place
    body_place = body.getGlobalPlacement()
    for obj in body.Group:
        movement = _move_of(obj, body_place)
        if movement is not None:
            place = movement.multiply(place)
        if obj is step:
            break
    return place


def _save(place):
    return [float(c) for c in list(place.Base) + list(place.Rotation.Q)]


def _load(value):
    try:
        values = [float(c) for c in value]
        return App.Placement(App.Vector(*values[:3]), App.Rotation(*values[3:7]))
    except Exception:
        return App.Placement()


def _shift(frame, entry):
    """What takes an entry's point from where it was given its look to `frame`."""
    given = _load(entry["frame"]) if entry.get("frame") else App.Placement()
    shift = frame.multiply(given.inverse())
    return None if move_identity(shift) else shift


def move_identity(place, tol=1e-12):
    return place.Base.Length < tol and abs(place.Rotation.Angle) < tol


def copy_body_appearance(source, target):
    """A body made from another (a copy, a split-off piece) looks the same."""
    data = get(source)
    data["faces"] = []
    _put(target, data)


def effective(body):
    """The look the whole body has: its Appearance, else its material's, else None."""
    data = get(body)
    return data.get("body") or data.get("material")


def looks_in_design(doc):
    """[(look, [bodies])] of the looks used in the design ("In This Design")."""
    found = []
    for body in bodies.list_bodies(doc):
        data = get(body)
        for look in [data.get("body") or data.get("material")] + [f["look"] for f in data["faces"]]:
            if not look:
                continue
            for entry in found:
                if same(entry[0], look):
                    if body not in entry[1]:
                        entry[1].append(body)
                    break
            else:
                found.append((look, [body]))
    return found


# -- faces found again -------------------------------------------------------------------------------
def _probe(face):
    """A point inside the face and its outward direction there."""
    u0, u1, v0, v1 = face.ParameterRange
    u, v = (u0 + u1) / 2.0, (v0 + v1) / 2.0
    point = face.valueAt(u, v)
    try:
        import Part

        if not face.isInside(point, 1e-6, True):
            point = face.CenterOfMass
            if face.distToShape(Part.Vertex(point))[0] > 1e-6:
                point = face.Vertexes[0].Point if face.Vertexes else point
        u, v = face.Surface.parameter(point)
    except Exception:
        pass
    return point, face.normalAt(u, v)


def _matches(face, entry, shift=None):
    import Part

    point = App.Vector(*entry["point"])
    normal = App.Vector(*entry["normal"])
    if shift is not None:
        point = shift.multVec(point)
        normal = shift.Rotation.multVec(normal)
    try:
        if face.distToShape(Part.Vertex(point))[0] > 1e-5:
            return False
        u, v = face.Surface.parameter(point)
        return face.normalAt(u, v).dot(normal) > 0.999
    except Exception:
        return False


def face_looks(shape, data, frame=None):
    """[look or None] per face of `shape` (body coordinates). `frame`: how Move steps have
    moved the body's solid at this step (frame_of)."""
    frame = frame if frame is not None else App.Placement()
    shifts = [_shift(frame, entry) for entry in data["faces"]]
    out = []
    for face in shape.Faces:
        look = None
        for entry, shift in zip(data["faces"], shifts):
            if _matches(face, entry, shift):
                look = entry["look"]
        out.append(look)
    return out


# -- on screen ----------------------------------------------------------------------------------
def material_of(look):
    """FreeCAD's App.Material for a look."""
    r, g, b = look["color"]
    shine = float(look.get("shininess", 0.5))
    spec = 0.15 + 0.6 * shine
    return App.Material(
        DiffuseColor=(r, g, b),
        AmbientColor=(r * 0.25, g * 0.25, b * 0.25),
        SpecularColor=(spec, spec, spec),
        EmissiveColor=(0.0, 0.0, 0.0),
        Shininess=max(0.02, shine),
        Transparency=float(look.get("transparency", 0.0)),
    )


def _same_materials(a, b):
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        if [round(c, 3) for c in x.DiffuseColor[:3]] != [round(c, 3) for c in y.DiffuseColor[:3]]:
            return False
        if abs(x.Transparency - y.Transparency) > 1e-3 or abs(x.Shininess - y.Shininess) > 1e-3:
            return False
    return True


def _default_material():
    """The look FreeCAD gives a part that has none (its Part colour preferences), worked out
    the way FreeCAD does (Materials' defaultAppearance). App.Material() alone is FreeCAD's
    built-in lavender grey: faces left without a look turned that colour instead of the grey
    every other part has."""
    try:
        base = App.Material()
    except Exception:
        return None
    try:
        params = App.ParamGet("User parameter:BaseApp/Preferences/View")

        def color(name, fallback):
            if params.GetUnsigned(name, 1) == 1 and params.GetUnsigned(name, 2) == 2:
                return tuple(fallback[:3])  # not set: FreeCAD's built-in default
            packed = params.GetUnsigned(name, 0)
            return tuple(((packed >> shift) & 255) / 255.0 for shift in (24, 16, 8))

        return App.Material(
            DiffuseColor=color("DefaultShapeColor", base.DiffuseColor),
            AmbientColor=color("DefaultAmbientColor", base.AmbientColor),
            SpecularColor=color("DefaultSpecularColor", base.SpecularColor),
            EmissiveColor=color("DefaultEmissiveColor", base.EmissiveColor),
            Shininess=params.GetInt("DefaultShapeShininess", 90) / 100.0,
            Transparency=params.GetInt("DefaultShapeTransparency", 0) / 100.0,
        )
    except Exception:
        return base


def apply(body):
    """Put the stored looks on every step of the body (GUI only)."""
    if not App.GuiUp or not bodies.alive(body):
        return
    data = get(body)
    whole = data.get("body") or data.get("material")
    if not whole and not data["faces"]:
        return
    _COLORED.setdefault(body.Document.Name, set()).add(body.Name)
    base = material_of(whole) if whole else _default_material()
    text = getattr(body, PROP, "")
    frame = App.Placement()
    body_place = body.getGlobalPlacement()
    for step in body.Group:
        try:
            movement = _move_of(step, body_place)
        except Exception:
            movement = None
        if movement is not None:
            frame = movement.multiply(frame)
        if not step.isDerivedFrom("PartDesign::Feature"):
            continue
        vobj = step.ViewObject
        if vobj is None or "ShapeAppearance" not in vobj.PropertiesList:
            continue
        try:
            shape = step.Shape
            if shape.isNull():
                continue
            key = (body.Document.Name, step.Name)
            stamp = (shape.hashCode(), text, len(vobj.ShapeAppearance))
            if _APPLIED.get(key) == stamp:
                continue  # nothing changed since the look was put on (big designs stay quick)
            if data["faces"]:
                per_face = face_looks(shape, data, frame)
                if any(per_face):
                    wanted = [material_of(look) if look else base for look in per_face]
                else:
                    wanted = [base]
            else:
                wanted = [base]
            current = list(vobj.ShapeAppearance)
            if not _same_materials(current, wanted):
                vobj.ShapeAppearance = wanted
            _APPLIED[key] = (shape.hashCode(), text, len(vobj.ShapeAppearance))
        except Exception:
            continue


def sync(doc):
    """Looks on every step of every body; a body whose look was taken away (undo) gets
    FreeCAD's plain look back."""
    if not App.GuiUp:
        return
    colored = set()
    for body in bodies.list_bodies(doc):
        if PROP in body.PropertiesList and getattr(body, PROP):
            apply(body)
            colored.add(body.Name)
    for name in _COLORED.get(doc.Name, set()) - colored:
        body = doc.getObject(name)
        if body is not None:
            reset_view(body)
    _COLORED[doc.Name] = colored


def reset_view(body):
    """Back to FreeCAD's look (after an appearance was removed by undo or cleared)."""
    if not App.GuiUp:
        return
    base = _default_material()
    for step in body.Group:
        _APPLIED.pop((body.Document.Name, step.Name), None)
        vobj = getattr(step, "ViewObject", None)
        if vobj is None or "ShapeAppearance" not in vobj.PropertiesList:
            continue
        try:
            vobj.ShapeAppearance = [base]
        except Exception:
            pass
