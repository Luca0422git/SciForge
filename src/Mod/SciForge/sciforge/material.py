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
FREECAD_DEFAULT_UUID = "7f9fd73b-50c9-41d8-b7b2-575a030c1eeb"


class MaterialError(ValueError):
    pass


def entry(key):
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
    """The library rows whose FreeCAD material exists here."""
    return [e for e in entries() if library_material(e["freecad"]) is not None]


def density_of(key):
    """kg/mm^3 of a library entry, or None."""
    row = entry(key)
    mat = library_material(row["freecad"]) if row else None
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
    return ""


def effective(body):
    """(label, density kg/mm^3) the body counts with: its material, or Steel while it is
    still on FreeCAD's Default (Fusion's designs start in Steel)."""
    key = key_of(body)
    if key:
        return entry(key)["label"], density_of(key)
    name = bodies.material_name(body)
    try:
        uuid = body.ShapeMaterial.UUID
    except Exception:
        uuid = ""
    if uuid == FREECAD_DEFAULT_UUID or not name or name == "Default":
        return entry(DEFAULT_KEY)["label"] + " (default)", density_of(DEFAULT_KEY)
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
    mat = library_material(row["freecad"])
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
