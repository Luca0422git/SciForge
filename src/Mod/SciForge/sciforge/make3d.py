# SPDX-License-Identifier: LGPL-2.1-or-later
"""3D print export (Fusion: Utilities > Make > 3D Print), outline 7.12. No GUI code.

Turns a body into a triangle mesh and writes STL or 3MF. Quality presets are
the maximum distance between the mesh and the true surface (mm) and the
maximum angle between neighbouring triangles (radians), like Fusion's
refinement settings.
"""
QUALITY = {
    "Low": (0.1, 0.5),
    "Medium": (0.05, 0.3),
    "High": (0.01, 0.15),
}
FORMATS = ("3mf", "stl")


class ExportError(ValueError):
    pass


def mesh_of(shape, quality="Medium"):
    import MeshPart

    if shape is None or shape.isNull() or not shape.Solids:
        raise ExportError("Nothing solid to export: the body is empty.")
    linear, angular = QUALITY[quality]
    return MeshPart.meshFromShape(
        Shape=shape, LinearDeflection=linear, AngularDeflection=angular, Relative=False
    )


def export(shape, path, quality="Medium"):
    """Write `shape` to `path` (.3mf or .stl). Returns the mesh."""
    ext = path.rsplit(".", 1)[-1].lower()
    if ext not in FORMATS:
        raise ExportError("Choose a .3mf or .stl file name.")
    mesh = mesh_of(shape, quality)
    if not mesh.isSolid():
        raise ExportError("The mesh is not watertight; a slicer would reject it. Check the body.")
    mesh.write(path)
    return mesh
