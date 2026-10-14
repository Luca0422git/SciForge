# SPDX-License-Identifier: LGPL-2.1-or-later
"""Physical Material: what a body is made of (its density, so its mass), no Qt.
material_ui.py is the dialog; Inspect reads the mass through bodies.mass().

The material is FreeCAD's own: the body's ShapeMaterial (FreeCAD's Materials library), so it
is saved in the file, every step of the body has it, and other FreeCAD tools see it too. A
material also gives the body its look (appearance.set_material_look), unless an Appearance
was given to the body, as in Fusion.

Fusion starts every design in Steel; FreeCAD starts with a "Default" material of almost no
weight. A body still on FreeCAD's Default counts as Steel for its mass (effective()).
"""

from . import appearance, bodies

# (key, label, FreeCAD library material, look key, group)
LIBRARY = [
    ("steel", "Steel", "Steel-Generic", "steel_satin", "Metal"),
    ("stainless", "Stainless Steel", "Steel-X5CrNi18-10", "stainless", "Metal"),
    ("iron", "Iron", "Iron-Generic", "cast_iron", "Metal"),
    ("aluminium", "Aluminium", "Aluminum-Generic", "aluminium_satin", "Metal"),
    ("aluminium_6061", "Aluminium 6061", "Aluminum-6061-T6", "aluminium_satin", "Metal"),
    ("copper", "Copper", "Copper-Generic", "copper", "Metal"),
    ("titanium", "Titanium", "Ti-6Al-4V", "titanium", "Metal"),
    ("abs", "ABS Plastic", "ABS-Generic", "plastic_white", "Plastic"),
    ("pla", "PLA", "PLA-Generic", "plastic_grey", "Plastic"),
    ("pet", "PET / PETG", "PET-Generic", "plastic_clear", "Plastic"),
    ("nylon", "Nylon 6", "PA6-Generic", "plastic_matte_white", "Plastic"),
    ("polycarbonate", "Polycarbonate", "PC-Molded", "plastic_clear", "Plastic"),
    ("acetal", "Acetal (POM)", "POM-Copolymer-Generic", "plastic_matte_white", "Plastic"),
    ("acrylic", "Acrylic (PMMA)", "PMMA-Generic", "plastic_clear", "Plastic"),
    ("polypropylene", "Polypropylene", "PP-Generic", "plastic_matte_white", "Plastic"),
    ("ptfe", "PTFE", "PTFE-Generic", "plastic_matte_white", "Plastic"),
    ("peek", "PEEK", "PEEK-Generic", "plastic_matte_black", "Plastic"),
    ("wood", "Wood", "Wood-Generic", "wood_light", "Other"),
    ("glass", "Glass", "Glass-Generic", "glass_clear", "Other"),
]
DEFAULT_KEY = "steel"
DEFAULT_PREF = "User parameter:BaseApp/Preferences/Mod/SciForge/Preferences"
FREECAD_DEFAULT_UUID = "7f9fd73b-50c9-41d8-b7b2-575a030c1eeb"


class MaterialError(ValueError):
    pass


USER_LIBRARY = "User"  # FreeCAD's library in the user's settings folder
USER_FOLDER = "SciForge"  # where Manage Materials > New Material keeps the user's own
USER_PREFIX = "user:"
DENSITY_MODEL = "454661e5-265b-4320-8e6f-fcf6223ac3af"  # FreeCAD's Mechanical/Density model
FAVORITES = "MaterialFavorites"


def entry(key):
    if str(key or "").startswith(USER_PREFIX):
        for row in user_entries():
            if row["key"] == key:
                return row
        return None
    for row in LIBRARY:
        if row[0] == key:
            return {
                "key": row[0],
                "label": row[1],
                "freecad": row[2],
                "look": row[3],
                "group": row[4],
            }
    return None


def entries():
    return [entry(row[0]) for row in LIBRARY]


def _manager():
    import Materials

    return Materials.MaterialManager()


def user_entries():
    """The user's own materials (Manage Materials > New Material), from FreeCAD's User
    library: {"key": "user:<uuid>", "label", "freecad", "look", "group": "My Materials",
    "uuid"}. A material made from a library one looks like it."""
    rows = []
    try:
        manager = _manager()
        for uuid, mat in manager.Materials.items():
            if mat.LibraryName != USER_LIBRARY or uuid in _DELETED:
                continue
            full = manager.getMaterial(uuid)
            rows.append(
                {
                    "key": USER_PREFIX + uuid,
                    "label": full.Name,
                    "freecad": full.Name,
                    "look": _look_of_parent(getattr(full, "Parent", "")),
                    "base": _base_of_parent(getattr(full, "Parent", ""))[0],
                    "group": "My Materials",
                    "uuid": uuid,
                }
            )
    except Exception:
        return []
    return sorted(rows, key=lambda r: r["label"].lower())


_DELETED = set()  # user materials deleted this session (FreeCAD keeps them in its cache)


def _look_of_parent(uuid):
    return _base_of_parent(uuid)[1]


def _base_of_parent(uuid):
    """(library key, look key) of the library material a user's material was made from."""
    for row in LIBRARY:
        mat = library_material(row[2])
        if mat is not None and uuid and mat.UUID == uuid:
            return row[0], row[3]
    return DEFAULT_KEY, "plastic_grey"


def material_of(row):
    """FreeCAD's material for an entry (library or the user's own), or None."""
    if row is None:
        return None
    if row.get("uuid"):
        try:
            return _manager().getMaterial(row["uuid"])
        except Exception:
            return None
    return library_material(row["freecad"])


def taken_names():
    names = set()
    try:
        for uuid, mat in _manager().Materials.items():
            if uuid not in _DELETED:  # a deleted one's name can be used again
                names.add(mat.Name.lower())
    except Exception:
        pass
    names.update(row[1].lower() for row in LIBRARY)
    return names


def create_user_material(name, base_key, density):
    """Manage Materials > New Material: a material of the user's own, made from a library
    one (`base_key`) with its own name and density (g/cm^3), kept in FreeCAD's User library
    (so FreeCAD's own tools see it too). Returns its key."""
    name = (name or "").strip()
    if not name:
        raise MaterialError("Give the new material a name.")
    if any(c in name for c in '\\/:*?"<>|'):
        raise MaterialError("A material's name cannot have \\ / : * ? \" < > |.")
    if name.lower() in taken_names():
        raise MaterialError("There is already a material called %s." % name)
    try:
        density = float(density)
    except (TypeError, ValueError):
        raise MaterialError("The density is a number in g/cm³.") from None
    if density <= 0:
        raise MaterialError("The density must be more than 0 g/cm³.")
    base = material_of(entry(base_key))
    if base is None:
        raise MaterialError("Pick the material it is based on.")
    manager = _manager()
    mat = manager.inheritMaterial(base.UUID)
    mat.Name = name
    try:
        if not mat.hasPhysicalModel(DENSITY_MODEL):
            mat.addPhysicalModel(DENSITY_MODEL)  # not every parent's model is carried over
    except Exception:
        pass
    mat.setPhysicalValue("Density", "%r g/cm^3" % density)
    manager.save(USER_LIBRARY, mat, "%s/%s.FCMat" % (USER_FOLDER, name), saveAsCopy=True)
    try:
        manager.refresh()
    except Exception:
        pass
    for row in user_entries():
        if row["label"] == name:
            return row["key"]
    raise MaterialError("%s was saved but FreeCAD does not list it." % name)


def user_material_file(row):
    import os

    import FreeCAD as App

    return os.path.join(App.getUserAppDataDir(), "Material", USER_FOLDER, row["label"] + ".FCMat")


def delete_user_material(key):
    """Remove one of the user's own materials from the User library (bodies made of it keep
    it in their design). False when it is not one of the user's."""
    import os

    row = entry(key)
    if row is None or not row.get("uuid"):
        return False
    path = user_material_file(row)
    if os.path.isfile(path):
        os.remove(path)
    _DELETED.add(row["uuid"])
    try:
        _manager().refresh()
    except Exception:
        pass
    return True


def favorites():
    """The keys of the favourite materials (Manage Materials), in the order they were added."""
    try:
        import FreeCAD as App

        text = App.ParamGet(DEFAULT_PREF).GetString(FAVORITES, "")
    except Exception:
        return []
    return [k for k in text.split(";") if k]


def set_favorite(key, on):
    import FreeCAD as App

    keys = [k for k in favorites() if k != key]
    if on:
        keys.append(key)
    App.ParamGet(DEFAULT_PREF).SetString(FAVORITES, ";".join(keys))


_CACHE = {}


def library_material(name):
    """FreeCAD's library material of this name, or None (cached)."""
    if name in _CACHE:
        return _CACHE[name]
    found = None
    try:
        import Materials

        manager = Materials.MaterialManager()
        for uuid, mat in manager.Materials.items():
            if mat.Name == name and mat.LibraryName == "System":
                found = manager.getMaterial(uuid)
                break
    except Exception:
        found = None
    _CACHE[name] = found
    return found


def available():
    """The library rows whose FreeCAD material exists here, then the user's own."""
    return [e for e in entries() if library_material(e["freecad"]) is not None] + user_entries()


def density_of(key):
    """kg/mm^3 of a library entry, or None."""
    row = entry(key)
    mat = material_of(row) if row else None
    if mat is None:
        return None
    try:
        return float(mat.getPhysicalValue("Density").getValueAs("kg/mm^3"))
    except Exception:
        return None


def key_of(body):
    """The library key of the body's material ("" when it is not one of the list)."""
    name = bodies.material_name(body)
    try:
        uuid = body.ShapeMaterial.UUID
    except Exception:
        uuid = ""
    if uuid == FREECAD_DEFAULT_UUID or not name or name == "Default":
        return ""
    for row in LIBRARY:
        if row[2] == name:
            return row[0]
    for row in user_entries():
        if row["uuid"] == uuid:
            return row["key"]
    return ""


def default_key():
    """The material a body counts as until it is given one: Preferences > Material > Default
    physical material (Fusion's designs start in Steel)."""
    key = DEFAULT_KEY
    try:
        import FreeCAD as App

        key = App.ParamGet(DEFAULT_PREF).GetString("DefaultMaterial", DEFAULT_KEY) or DEFAULT_KEY
    except Exception:
        return DEFAULT_KEY
    return key if entry(key) is not None else DEFAULT_KEY


def effective(body):
    """(label, density kg/mm^3) the body counts with: its material, or the default material
    (Steel unless the Preferences say otherwise) while it is still on FreeCAD's Default."""
    key = key_of(body)
    if key:
        return entry(key)["label"], density_of(key)
    name = bodies.material_name(body)
    try:
        uuid = body.ShapeMaterial.UUID
    except Exception:
        uuid = ""
    if uuid == FREECAD_DEFAULT_UUID or not name or name == "Default":
        default = default_key()
        return entry(default)["label"] + " (default)", density_of(default)
    return name, bodies.density(body)


def mass(body):
    """kg, from the effective material (None without a solid)."""
    label, rho = effective(body)
    if rho is None or not bodies.has_solid(body):
        return None
    return body.Shape.Volume * rho


def assign(body, key):
    """Make the body of this material (and give it the material's look)."""
    row = entry(key)
    if row is None:
        raise MaterialError("Unknown material %r." % key)
    mat = material_of(row)
    if mat is None:
        raise MaterialError("FreeCAD's material library has no %s." % row["freecad"])
    try:
        current = body.ShapeMaterial.UUID
    except Exception:
        current = None
    if current != mat.UUID:
        body.ShapeMaterial = mat
        for step in body.Group:  # every step, so a rolled-back marker shows it too
            try:
                if "ShapeMaterial" in step.PropertiesList and step.ShapeMaterial.UUID != mat.UUID:
                    step.ShapeMaterial = mat
            except Exception:
                pass
    appearance.set_material_look(body, appearance.find(row["look"]))
    _remember_user_material(body, row)


USER_PROP = "SciForgeUserMaterial"


def _remember_user_material(body, row):
    """A material of the user's own is only in that computer's User library: the body keeps
    its name, density and base in the design, so it can be made again where it is missing."""
    import json

    if row.get("uuid"):
        rho = density_of(row["key"])
        text = json.dumps(
            {"name": row["label"], "density": rho * 1e6 if rho else None, "base": row.get("base")}
        )
        bodies.add_prop(body, "App::PropertyString", USER_PROP, "Base", "", True)
        if getattr(body, USER_PROP) != text:
            setattr(body, USER_PROP, text)
    elif USER_PROP in body.PropertiesList and getattr(body, USER_PROP):
        setattr(body, USER_PROP, "")


def restore_user_materials(doc):
    """A design opened where its bodies' own materials are not in the User library (another
    computer): they are made again from what the bodies keep, and given back. Returns the
    bodies fixed."""
    import json

    fixed = []
    for body in bodies.list_bodies(doc):
        text = getattr(body, USER_PROP, "") if USER_PROP in body.PropertiesList else ""
        if not text:
            continue
        try:
            data = json.loads(text)
        except ValueError:
            continue
        name = data.get("name")
        if not name or bodies.material_name(body) == name:
            continue
        key = None
        for row in user_entries():
            if row["label"] == name:
                key = row["key"]
        try:
            if key is None and data.get("density"):
                key = create_user_material(name, data.get("base") or DEFAULT_KEY, data["density"])
            if key is not None:
                assign(body, key)
                fixed.append(body)
        except Exception:
            continue  # it keeps FreeCAD's Default (counted as the default material)
    return fixed
