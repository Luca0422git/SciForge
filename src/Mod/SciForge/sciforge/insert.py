# SPDX-License-Identifier: LGPL-2.1-or-later
"""Insert (Fusion's INSERT menu) without Qt: mesh bodies, Convert Mesh, STEP files, SVG and
DXF curves into sketches, canvases (reference images). Spec and sources:
docs/sciforge/parity/insert-export.md. The maths here is unit tested outside FreeCAD; the
functions that touch a document need FreeCAD (headless is enough).

Objects made here (all found again by their SciForgeType):
  InsertMesh   a Mesh::Feature (mesh body) at document level, like a body in Fusion's
               Bodies folder; its kernel holds the file's triangles in design units.
  ConvertMesh  a PartDesign::FeaturePython step, the first step of a new body, that
               builds a solid from a mesh body (faceted, or prismatic = flat faces merged).
  InsertSTEP   the first step (PartDesign::FeatureBase) of each body made from a STEP or
               IGES file (step_import.py: the file's components and copies).
  Canvas       an Image::ImagePlane with the image kept inside the design file.
"""

import math
import os
import re

from . import log, warn


class _LazyBodies:
    """bodies.py needs FreeCAD; the maths here is unit tested without it, so the module is
    looked up when a function first needs it."""

    def __getattr__(self, name):
        from . import bodies as module

        return getattr(module, name)


bodies = _LazyBodies()

MESH_TYPE = "Mesh::Feature"
CANVAS_TYPE = "Image::ImagePlane"
CONVERT_TYPE = "PartDesign::FeaturePython"
TYPE_MESH = "InsertMesh"
TYPE_CONVERT = "ConvertMesh"
TYPE_STEP = "InsertSTEP"
TYPE_CANVAS = "Canvas"

MESH_EXTENSIONS = (".stl", ".obj", ".3mf")
STEP_EXTENSIONS = (".step", ".stp")
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tif", ".tiff")

# Fusion's Unit Type choices for a mesh (its MeshUnits order), the file's unit -> mm.
UNITS = [
    ("Centimeter", 10.0),
    ("Millimeter", 1.0),
    ("Meter", 1000.0),
    ("Inch", 25.4),
    ("Foot", 304.8),
]
UNIT_NAMES = [name for name, _ in UNITS]
UNIT_BY_SHORT = {"mm": "Millimeter", "cm": "Centimeter", "m": "Meter", "in": "Inch", "ft": "Foot"}

# DXF $INSUNITS codes -> mm (the file says what its numbers mean).
DXF_UNITS = {1: 25.4, 2: 304.8, 4: 1.0, 5: 10.0, 6: 1000.0, 8: 0.0254, 9: 0.0254 * 1000}

METHODS = ["Faceted", "Prismatic"]
OPERATIONS = ["Parametric", "Base Feature"]
FACET_WARNING = 10000  # Fusion warns above this many faces (conversion gets slow)

# A canvas starts about this big (longest side, mm) in an empty design; with bodies it is
# sized to the design, as Fusion sizes it "to the target plane" (approximate by design).
CANVAS_EMPTY_SIZE = 100.0


class InsertError(ValueError):
    """Something the user has to change (a missing file, an unreadable mesh...)."""


# -- units -----------------------------------------------------------------------------------
def unit_scale(unit):
    """mm per file unit for a Unit Type name ("Millimeter" -> 1, "Inch" -> 25.4)."""
    for name, factor in UNITS:
        if name == unit:
            return factor
    raise InsertError("Unknown unit type: %s" % unit)


def design_unit(doc):
    """The Unit Type that matches the design's units ("Millimeter" for a mm design)."""
    try:
        from . import browser_core

        short = browser_core.unit_label(int(doc.UnitSystem))
    except Exception:
        short = None
    return UNIT_BY_SHORT.get(short or "mm", "Millimeter")


def dxf_file_unit(path):
    """mm per unit the DXF file declares ($INSUNITS), or None when it says nothing."""
    try:
        with open(path, "r", errors="replace") as handle:
            head = handle.read(200000)
    except OSError:
        return None
    match = re.search(r"\$INSUNITS\s*\n\s*70\s*\n\s*(\d+)", head)
    if not match:
        return None
    return DXF_UNITS.get(int(match.group(1)))


# -- mesh placement maths (pure) ---------------------------------------------------------
def scale_matrix(factor):
    import FreeCAD as App

    return App.Matrix(factor, 0, 0, 0, 0, factor, 0, 0, 0, 0, factor, 0, 0, 0, 0, 1)


def flip_up_matrix():
    """Flip Up Direction: a Y-up file turned to Z-up (90 degrees about X, Y -> Z)."""
    import FreeCAD as App

    return App.Rotation(App.Vector(1, 0, 0), 90).toMatrix()


def bounds_after(bounds, scale=1.0, flip=False):
    """Bounding box ((xmin, ymin, zmin), (xmax, ymax, zmax)) after the scale and the flip."""
    (x0, y0, z0), (x1, y1, z1) = bounds
    if flip:  # (x, y, z) -> (x, -z, y)
        y0, y1, z0, z1 = -z1, -z0, y0, y1
    return (
        (x0 * scale, y0 * scale, z0 * scale),
        (x1 * scale, y1 * scale, z1 * scale),
    )


def center_offset(bounds):
    """Center: the position that puts the box's middle on the origin."""
    (x0, y0, z0), (x1, y1, z1) = bounds
    return (-(x0 + x1) / 2.0, -(y0 + y1) / 2.0, -(z0 + z1) / 2.0)


def ground_offset(bounds, position):
    """Move to Ground: the position (x, y kept) that rests the lowest point on Z = 0."""
    (_x0, _y0, z0), _top = bounds
    return (position[0], position[1], -z0)


def placement_of(position, angles):
    """Placement from X/Y/Z distances and X/Y/Z angles (degrees, applied X then Y then Z)."""
    import FreeCAD as App

    rot = App.Rotation(App.Vector(0, 0, 1), angles[2])
    rot = rot.multiply(App.Rotation(App.Vector(0, 1, 0), angles[1]))
    rot = rot.multiply(App.Rotation(App.Vector(1, 0, 0), angles[0]))
    return App.Placement(App.Vector(*position), rot)


def angles_of(placement):
    """(X, Y, Z) angles in degrees of a placement, the inverse of placement_of."""
    yaw, pitch, roll = placement.Rotation.toEulerAngles("XYZ")
    return (round(yaw, 6), round(pitch, 6), round(roll, 6))


# -- meshes ----------------------------------------------------------------------------------
def read_mesh(path):
    """The triangles of an STL / OBJ / 3MF file, in the file's own numbers."""
    import Mesh

    if not path or not os.path.isfile(path):
        raise InsertError("The file was not found: %s" % (path or "(no file)"))
    ext = os.path.splitext(path)[1].lower()
    if ext not in MESH_EXTENSIONS:
        raise InsertError("Choose an STL, OBJ or 3MF file (%s is not one)." % (ext or "no ending"))
    try:
        mesh = Mesh.Mesh(path)
    except Exception as exc:
        raise InsertError("The file could not be read as a mesh: %s" % exc)
    if mesh.CountFacets == 0:
        raise InsertError("The file holds no triangles.")
    return mesh


def mesh_bounds(mesh):
    box = mesh.BoundBox
    return ((box.XMin, box.YMin, box.ZMin), (box.XMax, box.YMax, box.ZMax))


def kernel_copy(obj):
    """The triangles of a mesh body without its placement. FreeCAD hands out a mesh body's
    Mesh with the body's Placement baked in (its points, bounds and Topology are all moved),
    so the triangles as stored are read from a copy put back at the origin."""
    import FreeCAD as App

    mesh = obj.Mesh.copy()
    mesh.Placement = App.Placement()
    return mesh


def placed_bounds(obj, rotation_only=False):
    """Bounds of a mesh body as it stands; rotation_only: turned but not moved (what Center
    and Move to Ground need to work out the position)."""
    import FreeCAD as App

    mesh = kernel_copy(obj)
    placement = obj.Placement
    if rotation_only:
        placement = App.Placement(App.Vector(), placement.Rotation)
    mesh.transform(placement.toMatrix())
    return mesh_bounds(mesh)


def mesh_info(mesh):
    """What the dialog says about a mesh: triangles, points, watertight, size."""
    (x0, y0, z0), (x1, y1, z1) = mesh_bounds(mesh)
    return {
        "facets": mesh.CountFacets,
        "points": mesh.CountPoints,
        "solid": bool(mesh.isSolid()),
        "size": (x1 - x0, y1 - y0, z1 - z0),
    }


def transformed_mesh(mesh, scale=1.0, flip=False):
    """A copy of the mesh in design units (scaled) and Z-up (flipped) as asked."""
    copy = mesh.copy()
    if flip:
        copy.transform(flip_up_matrix())
    if abs(scale - 1.0) > 1e-12:
        copy.transform(scale_matrix(scale))
    return copy


def _mesh_props(obj):
    bodies.add_prop(obj, "App::PropertyString", "SourceFile", "Insert", "The file it came from")
    bodies.add_prop(obj, "App::PropertyString", "UnitType", "Insert", "The file's unit type")
    bodies.add_prop(obj, "App::PropertyBool", "FlipUp", "Insert", "Y-up file turned Z-up")
    bodies.add_prop(obj, "App::PropertyFloat", "UnitScale", "Insert", "mm per file unit")


def make_mesh_body(doc, mesh, path, unit="Millimeter", flip=False, label=None):
    """The mesh body of Insert Mesh: a Mesh::Feature holding the file's triangles in design
    units, named after the file. Its Placement is the position / rotation of the dialog."""
    scale = unit_scale(unit)
    obj = doc.addObject(MESH_TYPE, "MeshBody")
    obj.Label = label or _mesh_label(doc, path)
    obj.Mesh = transformed_mesh(mesh, scale, flip)
    bodies.mark(obj, TYPE_MESH)
    _mesh_props(obj)
    obj.SourceFile = path or ""
    obj.UnitType = unit
    obj.FlipUp = bool(flip)
    obj.UnitScale = scale
    try:  # inserted while the timeline is rolled back: it goes in at the history marker
        from . import timeline_ops

        timeline_ops.place_root_step(obj)
    except Exception as exc:
        log("timeline: the mesh body stays at the end (%s)" % exc)
    return obj


def _mesh_label(doc, path):
    base = os.path.splitext(os.path.basename(path or ""))[0] or "Mesh"
    labels = {o.Label for o in doc.Objects}
    label, n = base, 1
    while label in labels:
        n += 1
        label = "%s (%d)" % (base, n)
    return label


def update_mesh_body(obj, unit, flip):
    """Change the Unit Type / Flip Up of an inserted mesh: its triangles are re-scaled and
    turned from what they are (the file is not needed again)."""
    old_scale = float(getattr(obj, "UnitScale", 1.0) or 1.0)
    old_flip = bool(getattr(obj, "FlipUp", False))
    scale = unit_scale(unit)
    changed = abs(scale - old_scale) > 1e-12 or bool(flip) != old_flip
    if not changed:
        return False
    placement = obj.Placement
    mesh = kernel_copy(obj)
    if abs(scale - old_scale) > 1e-12:
        mesh.transform(scale_matrix(scale / old_scale))
    if bool(flip) != old_flip:
        matrix = flip_up_matrix()
        if not flip:
            matrix = matrix.inverse()
        mesh.transform(matrix)
    obj.Mesh = mesh
    obj.Placement = placement  # setting the Mesh resets the body's placement
    obj.UnitType = unit
    obj.FlipUp = bool(flip)
    obj.UnitScale = scale
    return True


def is_mesh_body(obj):
    """A mesh body: an inserted mesh, or the MESH tab's step that holds a body now
    (Mesh::FeaturePython, mesh.py)."""
    try:
        return obj is not None and obj.TypeId in (MESH_TYPE, "Mesh::FeaturePython")
    except Exception:
        return False


def mesh_bodies(doc):
    return [o for o in doc.Objects if is_mesh_body(o)]


# -- Convert Mesh ----------------------------------------------------------------------------
def solid_from_mesh(mesh, method="Prismatic", tolerance=None):
    """A solid from a watertight mesh. Faceted keeps one flat face per triangle; Prismatic
    merges the triangles that lie in one plane into one face (flat faces of a box or a
    plate become single faces; round faces stay faceted: FreeCAD has no surface fitting)."""
    import Part

    if mesh is None or mesh.CountFacets == 0:
        raise InsertError("The mesh body has no triangles.")
    if tolerance is None:
        tolerance = max(1e-4, 1e-5 * mesh.BoundBox.DiagonalLength)
    shape = Part.Shape()
    shape.makeShapeFromMesh(mesh.Topology, tolerance, True)
    if shape.isNull() or not shape.Faces:
        raise InsertError("The triangles could not be sewn into faces.")
    try:
        solid = Part.makeSolid(shape)
    except Exception:
        raise InsertError(
            "The mesh is not watertight (it has holes or loose triangles), so it cannot "
            "become a solid. Repair the mesh first (MESH tab > Repair)."
        )
    if solid.isNull() or not solid.Solids:
        raise InsertError("The mesh does not close into a solid.")
    if solid.Volume < 0:
        solid.reverse()
    if method == "Prismatic":
        try:
            merged = solid.removeSplitter()
            if not merged.isNull() and merged.Solids:
                solid = merged
        except Exception as exc:
            warn("Convert Mesh: faces could not be merged (%s); kept faceted" % exc)
    return solid


class ConvertMeshFeature:
    """Saved in files as "sciforge.insert.ConvertMeshFeature": keep the name and properties."""

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        def add(kind, name, doc):
            if name not in obj.PropertiesList:
                obj.addProperty(kind, name, "ConvertMesh", doc)
                return True
            return False

        add("App::PropertyLink", "Source", "The mesh body it converts")
        if add("App::PropertyEnumeration", "Method", "Faceted, or Prismatic (flat faces merged)"):
            obj.Method = METHODS
            obj.Method = "Prismatic"
        if add("App::PropertyBool", "Parametric", "Follows the mesh body; off: a base feature"):
            obj.Parametric = True
        add("App::PropertyFloat", "Tolerance", "Sewing tolerance (0: from the mesh size)")
        bodies.mark(obj, TYPE_CONVERT)

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)

    def execute(self, obj):
        try:
            self._build(obj)
        except Exception:
            bodies.pass_through(obj)
            raise

    def _build(self, obj):
        source = obj.Source
        if not obj.Parametric and not obj.Shape.isNull() and obj.Shape.Solids:
            return  # a base feature: made once, never rebuilt from the mesh
        if source is None or not is_mesh_body(source):
            raise InsertError("Its mesh body is gone (deleted?). Edit the step and pick one.")
        tolerance = float(obj.Tolerance) or None
        solid = solid_from_mesh(kernel_copy(source), obj.Method, tolerance)
        solid.Placement = source.Placement.multiply(solid.Placement)
        body = bodies.body_of(obj)
        obj.Shape = bodies.to_local(solid, body) if body is not None else solid

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def convert_mesh(mesh_obj, method="Prismatic", parametric=True, label=None):
    """Convert Mesh: a new body whose first step builds a solid from the mesh body. Returns
    (body, step). The mesh body is hidden, as the solid takes its place in the view."""
    doc = mesh_obj.Document
    body = bodies.new_body(doc, label=label or mesh_obj.Label + " (solid)")
    step = bodies.insert_after_tip(body, CONVERT_TYPE, "ConvertMesh")
    ConvertMeshFeature(step)
    step.Source = mesh_obj
    step.Method = method
    step.Parametric = bool(parametric)
    _attach_step_view(step)
    return body, step


def _attach_step_view(obj):
    try:
        import FreeCAD as App

        if not App.GuiUp:
            return
        from .bodies_gui import StepViewProvider

        StepViewProvider(obj.ViewObject)
    except Exception:
        pass


def convert_steps(doc):
    return [o for o in doc.Objects if bodies.kind(o) == TYPE_CONVERT]


# -- STEP ------------------------------------------------------------------------------------
# STEP and IGES files come in with their structure (components, copies): step_import.py.
# What is kept here is shared with it: the part colours and the labels.
def _view_colours(obj):
    """[(r, g, b)] per face of an object's view (empty headless)."""
    try:
        vobj = obj.ViewObject
        if vobj is None or "ShapeAppearance" not in vobj.PropertiesList:
            return []
        return [tuple(float(c) for c in m.DiffuseColor[:3]) for m in vobj.ShapeAppearance]
    except Exception:
        return []


def _unique_label(doc, label, taken):
    labels = {o.Label for o in doc.Objects} | taken
    base, n = label, 1
    while label in labels:
        n += 1
        label = "%s (%d)" % (base, n)
    taken.add(label)
    return label


def insert_step(doc, path, parent=None):
    """Insert STEP: the file as one component with its structure (step_import). Returns the
    bodies made."""
    from . import exchange_core, step_import

    if not path or not os.path.isfile(path):
        raise InsertError("The file was not found: %s" % (path or "(no file)"))
    try:
        made = step_import.import_file(doc, path, exchange_core.INSERT, parent)
    except exchange_core.ExchangeError as exc:
        raise InsertError(str(exc))
    return made.bodies


def _remove_quietly(doc, obj):
    try:
        if doc.getObject(obj.Name) is not None:
            doc.removeObject(obj.Name)
    except Exception:
        pass


def _colour_body(body, colours):
    """The STEP part's colours as a SciForge Appearance (saved, undone, kept by later steps)."""
    if not colours:
        return
    try:
        from . import appearance

        tip = body.Tip
        distinct = {tuple(round(c, 3) for c in col) for col in colours}
        if len(distinct) == 1 or tip is None or len(colours) != len(tip.Shape.Faces):
            appearance.set_body(body, appearance.custom(colours[0]))
            return
        # Per-face colours: the most used colour for the body, the others on their faces.
        counts = {}
        for col in colours:
            key = tuple(round(c, 3) for c in col)
            counts[key] = counts.get(key, 0) + 1
        main = max(counts, key=counts.get)
        appearance.set_body(body, appearance.custom(main))
        for key in counts:
            if key == main:
                continue
            names = [
                "Face%d" % (i + 1)
                for i, col in enumerate(colours)
                if tuple(round(c, 3) for c in col) == key
            ]
            appearance.set_faces(body, tip, names, appearance.custom(key))
    except Exception as exc:
        warn("Insert STEP: colours not kept (%s)" % exc)


# -- SVG / DXF into a sketch -----------------------------------------------------------------
def _temp_document():
    """A hidden throw-away document for FreeCAD's importers. Returns (document, the name
    of the design that was active): making a document makes it the active one, and
    closing it leaves FreeCAD's active document pointing at the closed one in the GUI."""
    import FreeCAD as App

    active = App.ActiveDocument.Name if App.ActiveDocument is not None else None
    return App.newDocument("SciForgeImport", "import", True, True), active


def _close_temp(doc, active):
    import FreeCAD as App

    try:
        App.closeDocument(doc.Name)
    except Exception:
        pass
    restore_active_document(active)


def restore_active_document(name):
    """Make the design `name` the active document again (after a throw-away document)."""
    import FreeCAD as App

    if not name or name not in App.listDocuments():
        return
    try:
        App.setActiveDocument(name)
    except Exception as exc:
        warn("active design not restored: %s" % exc)
    if App.GuiUp:
        try:
            import FreeCADGui as Gui

            gdoc = Gui.getDocument(name)
            if gdoc is not None and gdoc.ActiveView is not None:
                Gui.getMainWindow().setActiveWindow(gdoc.ActiveView)
        except Exception:
            pass


class _dxf_dialog_off:
    """FreeCAD's DXF importer shows its own import dialog in the GUI: SciForge's dialog has
    the choices (units, layers), so FreeCAD's is kept off for the import and the user's own
    setting is put back afterwards."""

    GROUP = "User parameter:BaseApp/Preferences/Mod/Draft"
    KEY = "dxfShowDialog"

    def __enter__(self):
        import FreeCAD as App

        self.grp = App.ParamGet(self.GROUP)
        contents = self.grp.GetContents() or []
        self.had = any(entry[1] == self.KEY for entry in contents)
        self.was = self.grp.GetBool(self.KEY, True)
        self.grp.SetBool(self.KEY, False)
        return self

    def __exit__(self, *exc):
        try:
            if self.had:
                self.grp.SetBool(self.KEY, self.was)
            else:
                self.grp.RemBool(self.KEY)
        except Exception:
            pass
        return False


def _layer_of(obj, layers):
    for layer, members in layers.items():
        if obj.Name in members:
            return layer
    return None


def read_curves(path):
    """[(layer name, [edges])] of an SVG or DXF file, read with FreeCAD's importers into a
    throw-away document. The edges lie in the XY plane, in mm (the importers scale the
    file's units; SVG px count 96 per inch, as FreeCAD reads them)."""
    if not path or not os.path.isfile(path):
        raise InsertError("The file was not found: %s" % (path or "(no file)"))
    ext = os.path.splitext(path)[1].lower()
    if ext not in (".svg", ".dxf"):
        raise InsertError("Choose an SVG or DXF file.")
    doc, active = _temp_document()
    try:
        if ext == ".svg":
            import importSVG

            importSVG.insert(path, doc.Name)
        else:
            import importDXF

            with _dxf_dialog_off():
                importDXF.insert(path, doc.Name)
        doc.recompute()
        layers = {}
        for obj in doc.Objects:
            if obj.TypeId == "App::FeaturePython" and "Group" in obj.PropertiesList:
                try:
                    members = {m.Name for m in obj.Group}
                except Exception:
                    members = set()
                if members:
                    layers[obj.Label] = members
        found = {}
        order = []
        for obj in doc.Objects:
            shape = getattr(obj, "Shape", None)
            if shape is None or shape.isNull() or not shape.Edges:
                continue
            if obj.TypeId == "App::FeaturePython" and "Group" in obj.PropertiesList:
                continue  # a layer (its shape is the compound of its members)
            layer = _layer_of(obj, layers) or ("Layer 0" if ext == ".dxf" else "SVG")
            if layer not in found:
                found[layer] = []
                order.append(layer)
            # shape.Edges already carry the shape's own placement (a translated circle
            # moved twice when it was put on again: found by the SVG scenario)
            for edge in shape.Edges:
                found[layer].append(edge.copy())
        return [(layer, found[layer]) for layer in order if found[layer]]
    finally:
        _close_temp(doc, active)


def curves_bounds(edges):
    """((xmin, ymin), (xmax, ymax)) of edges in the XY plane, or None when there are none."""
    box = None
    for edge in edges:
        b = edge.BoundBox
        if box is None:
            box = [b.XMin, b.YMin, b.XMax, b.YMax]
        else:
            box = [
                min(box[0], b.XMin),
                min(box[1], b.YMin),
                max(box[2], b.XMax),
                max(box[3], b.YMax),
            ]
    return ((box[0], box[1]), (box[2], box[3])) if box else None


def plane_matrix(dx=0.0, dy=0.0, angle=0.0, scale=1.0, flip_h=False, flip_v=False):
    """The 2D transform of Fusion's Insert SVG / DXF dialog on the sketch plane: flips about
    the origin's axes, then the scale, then the turn (degrees, counter-clockwise positive on
    the sketch), then the X / Y distance. Returns a FreeCAD Matrix."""
    import FreeCAD as App

    sx = -1.0 if flip_h else 1.0
    sy = -1.0 if flip_v else 1.0
    m = App.Matrix(sx * scale, 0, 0, 0, 0, sy * scale, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1)
    turn = App.Rotation(App.Vector(0, 0, 1), angle).toMatrix()
    move = App.Matrix()
    move.move(App.Vector(dx, dy, 0))
    return move.multiply(turn.multiply(m))


def plane_transform_point(
    point, dx=0.0, dy=0.0, angle=0.0, scale=1.0, flip_h=False, flip_v=False, origin=(0.0, 0.0)
):
    """plane_matrix applied to an (x, y) point, for tests and the preview maths. `origin`:
    the file's point that lands on the sketch origin (an SVG's middle: Fusion centres the
    image on the sketch origin) and that the flips, scale and turn go about."""
    x, y = point[0] - origin[0], point[1] - origin[1]
    if flip_h:
        x = -x
    if flip_v:
        y = -y
    x, y = x * scale, y * scale
    a = math.radians(angle)
    x, y = x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)
    return (x + dx, y + dy)


def sketch_geometry(edge):
    """The Sketcher geometry for an edge lying in the XY plane, or None if it has no
    sketchable kind (a straight line, a circle or arc, an ellipse or arc, a spline; the rest
    is turned into a spline)."""
    import Part

    curve = edge.Curve
    kind = curve.TypeId
    closed = edge.isClosed()
    first, last = edge.FirstParameter, edge.LastParameter
    try:
        if kind == "Part::GeomLine":
            a, b = edge.Vertexes[0].Point, edge.Vertexes[-1].Point
            if (a - b).Length < 1e-9:
                return None
            return Part.LineSegment(_flat(a), _flat(b))
        if kind == "Part::GeomCircle":
            circle = Part.Circle(_flat(curve.Center), Part.Circle().Axis, curve.Radius)
            if closed:
                return circle
            return _arc(edge, circle, first, last)
        if kind == "Part::GeomEllipse":
            ellipse = Part.Ellipse(_flat(curve.Center), curve.MajorRadius, curve.MinorRadius)
            ellipse.AngleXU = curve.AngleXU
            if closed:
                return ellipse
            return Part.ArcOfEllipse(ellipse, first, last)
        if kind == "Part::GeomBSplineCurve":
            spline = curve.copy()
            if not closed and (
                abs(first - spline.FirstParameter) > 1e-9 or abs(last - spline.LastParameter) > 1e-9
            ):
                spline.segment(first, last)
            spline = _flat_spline(spline)
            return spline
        spline = curve.toBSpline(first, last)
        return _flat_spline(spline)
    except Exception as exc:
        warn("Insert: an edge was skipped (%s: %s)" % (kind, exc))
        return None


def _flat(vector):
    import FreeCAD as App

    return App.Vector(vector.x, vector.y, 0.0)


def _arc(edge, circle, first, last):
    import Part

    a, b = edge.Vertexes[0].Point, edge.Vertexes[-1].Point
    mid = edge.valueAt((first + last) / 2.0)
    try:
        return Part.ArcOfCircle(_flat(a), _flat(mid), _flat(b))
    except Exception:
        return Part.ArcOfCircle(circle, first, last)


def _flat_spline(spline):
    import FreeCAD as App

    poles = [App.Vector(p.x, p.y, 0.0) for p in spline.getPoles()]
    if any(abs(p.z) > 1e-9 for p in spline.getPoles()):
        spline.buildFromPolesMultsKnots(
            poles, spline.getMultiplicities(), spline.getKnots(), spline.isPeriodic(), spline.Degree
        )
    return spline


def curves_to_geometry(edges):
    """Sketcher geometry for a file's edges (what can be sketched; the rest is skipped)."""
    out = []
    for edge in edges:
        geo = sketch_geometry(edge)
        if geo is not None:
            out.append(geo)
    return out


def _spline_moved(curve, point):
    poles = [point(p) for p in curve.getPoles()]
    weights = curve.getWeights() if curve.isRational() else None
    moved = curve.copy()
    moved.buildFromPolesMultsKnots(
        poles,
        curve.getMultiplicities(),
        curve.getKnots(),
        curve.isPeriodic(),
        curve.Degree,
        weights,
    )
    return moved


def transformed_geometry(
    geos, dx=0.0, dy=0.0, angle=0.0, scale=1.0, flip_h=False, flip_v=False, origin=(0.0, 0.0)
):
    """Copies of sketch geometry moved by the dialog's values (see plane_matrix), done on the
    geometry itself so a line stays a line and a circle a circle (OpenCASCADE's shape
    transform would turn them all into B-splines). Arcs are rebuilt from three points, so
    a flip keeps them whole; an ellipse arc under a flip becomes a B-spline."""
    import FreeCAD as App
    import Part

    def point(p):
        x, y = plane_transform_point((p.x, p.y), dx, dy, angle, scale, flip_h, flip_v, origin)
        return App.Vector(x, y, 0.0)

    mirrored = bool(flip_h) != bool(flip_v)
    out = []
    for geo in geos:
        kind = geo.TypeId
        try:
            if kind == "Part::GeomLineSegment":
                out.append(Part.LineSegment(point(geo.StartPoint), point(geo.EndPoint)))
            elif kind == "Part::GeomCircle":
                out.append(Part.Circle(point(geo.Center), App.Vector(0, 0, 1), geo.Radius * scale))
            elif kind == "Part::GeomArcOfCircle":
                a, b = geo.StartPoint, geo.EndPoint
                mid = geo.value((geo.FirstParameter + geo.LastParameter) / 2.0)
                out.append(Part.ArcOfCircle(point(a), point(mid), point(b)))
            elif kind == "Part::GeomEllipse" or (kind == "Part::GeomArcOfEllipse" and not mirrored):
                ellipse = geo.Ellipse if kind == "Part::GeomArcOfEllipse" else geo
                centre = ellipse.Center
                major_end = centre + App.Vector(
                    math.cos(ellipse.AngleXU) * ellipse.MajorRadius,
                    math.sin(ellipse.AngleXU) * ellipse.MajorRadius,
                    0,
                )
                new_centre, new_end = point(centre), point(major_end)
                moved = Part.Ellipse(
                    new_centre, ellipse.MajorRadius * scale, ellipse.MinorRadius * scale
                )
                moved.AngleXU = math.atan2(new_end.y - new_centre.y, new_end.x - new_centre.x)
                if kind == "Part::GeomArcOfEllipse":
                    out.append(Part.ArcOfEllipse(moved, geo.FirstParameter, geo.LastParameter))
                else:
                    out.append(moved)
            elif kind == "Part::GeomBSplineCurve":
                out.append(_spline_moved(geo, point))
            elif hasattr(geo, "toBSpline"):
                out.append(_spline_moved(geo.toBSpline(), point))
        except Exception as exc:
            warn("Insert: a curve could not be moved (%s: %s)" % (kind, exc))
    return out


def add_geometry(sketch, geos, fixed=True):
    """Add geometry to a sketch (fixed in place with a Block constraint, as Fusion fixes
    inserted SVG / DXF geometry). Returns the geometry ids added."""
    import Sketcher

    geos = list(geos)
    if not geos:
        return []
    try:  # one call for all of them: the sketch solves once, not once per curve
        ids = list(sketch.addGeometry(geos, False))
    except Exception:
        ids = []
        for geo in geos:
            try:
                ids.append(sketch.addGeometry(geo, False))
            except Exception as exc:
                warn("Insert: a curve could not be added to the sketch (%s)" % exc)
    if fixed and ids:
        try:
            sketch.addConstraint([Sketcher.Constraint("Block", index) for index in ids])
        except Exception as exc:
            warn("Insert: the curves could not be fixed (%s)" % exc)
    return ids


def add_curves(sketch, edges, fixed=True):
    """Edges straight into a sketch (no move): curves_to_geometry + add_geometry."""
    return add_geometry(sketch, curves_to_geometry(edges), fixed)


def remove_geometry(sketch, ids):
    """Take geometry (and its constraints) out of a sketch again (a preview being redone)."""
    if not ids:
        return
    try:
        sketch.delGeometries(sorted(ids))
    except Exception as exc:
        warn("Insert: old preview geometry not removed (%s)" % exc)


def new_sketch(body, target, label=None):
    """A sketch in `body` flat on `target` ((plane, "") or (feature, "FaceN")), without its own
    undo step (the caller's dialog owns one)."""
    import FreeCADGui as Gui

    from . import sketch_ui, timeline_ops

    owner = timeline_ops.body_of(target[0])
    if owner is not None and owner is not body:
        body = owner
        try:
            Gui.ActiveDocument.ActiveView.setActiveObject("pdbody", body)
        except Exception as exc:
            warn("could not activate %s: %s" % (body.Label, exc))
    target = sketch_ui._earliest(target)
    sketch = body.newObject("Sketcher::SketchObject", "Sketch")
    sketch.AttachmentSupport = [target]
    sketch.MapMode = "FlatFace"
    if label:
        sketch.Label = label
    body.Document.recompute()
    return sketch


# -- canvases --------------------------------------------------------------------------------
def default_canvas_size(pixels, design_extent=None):
    """(width, height) in mm for an image of (w, h) pixels: the longer side as long as the
    design is big (its bounding box's longest side, 1.3 x like the origin squares), or
    CANVAS_EMPTY_SIZE in an empty design; the picture keeps its proportions."""
    w, h = pixels
    if w <= 0 or h <= 0:
        raise InsertError("The image has no size.")
    longest = CANVAS_EMPTY_SIZE
    if design_extent:
        longest = max(20.0, 1.3 * float(design_extent))
    if w >= h:
        return (longest, longest * h / float(w))
    return (longest * w / float(h), longest)


def calibrate_scale(p1, p2, distance):
    """Calibrate: the factor that makes the two picked points `distance` apart."""
    dx, dy, dz = (p2[0] - p1[0], p2[1] - p1[1], p2[2] - p1[2])
    picked = math.sqrt(dx * dx + dy * dy + dz * dz)
    if picked < 1e-9:
        raise InsertError("Click two different points on the image.")
    if distance <= 0:
        raise InsertError("The distance must be more than 0.")
    return distance / picked


def canvas_rotation(plane_rotation, angle=0.0, flip_h=False, flip_v=False):
    """The canvas's rotation: the plane's frame, turned by `angle` about its normal; a flip
    turns the picture over about the plane's Y (horizontal flip) or X (vertical flip) axis,
    which mirrors it as seen from the front (the image plane shows both sides)."""
    import FreeCAD as App

    rot = plane_rotation.multiply(App.Rotation(App.Vector(0, 0, 1), angle))
    if flip_h:
        rot = rot.multiply(App.Rotation(App.Vector(0, 1, 0), 180))
    if flip_v:
        rot = rot.multiply(App.Rotation(App.Vector(1, 0, 0), 180))
    return rot


def canvas_placement(plane_placement, dx=0.0, dy=0.0, angle=0.0, flip_h=False, flip_v=False):
    import FreeCAD as App

    base = plane_placement.Base + plane_placement.Rotation.multVec(App.Vector(dx, dy, 0))
    return App.Placement(base, canvas_rotation(plane_placement.Rotation, angle, flip_h, flip_v))


def plane_frame(target):
    """The placement of a sketch plane target ((plane, "") or (feature, "FaceN")): the
    plane's own frame, or the flat face's frame with its normal pointing out of the part."""
    import FreeCAD as App

    obj, short = target
    if not short:
        return obj.getGlobalPlacement()
    face = obj.Shape.getElement(short)
    surface = face.Surface
    rotation = surface.Rotation
    u0, u1, v0, v1 = face.ParameterRange
    normal = face.normalAt((u0 + u1) / 2.0, (v0 + v1) / 2.0)
    if rotation.multVec(App.Vector(0, 0, 1)).dot(normal) < 0:
        rotation = rotation.multiply(App.Rotation(App.Vector(1, 0, 0), 180))
    # Shapes of a body's step are in design coordinates already (PartDesign bodies have
    # no placement of their own in SciForge), so the face's centre is the frame's origin.
    return App.Placement(face.CenterOfMass, rotation)


CANVAS_PROPS = (
    ("App::PropertyFileIncluded", "ImageData", "The image, kept inside the design file"),
    ("App::PropertyInteger", "CanvasOpacity", "0 (clear) .. 100 (solid)"),
    ("App::PropertyBool", "DisplayThrough", "Seen through the bodies in front of it"),
    ("App::PropertyBool", "FlipHorizontal", "Mirrored left-right"),
    ("App::PropertyBool", "FlipVertical", "Mirrored top-bottom"),
    ("App::PropertyFloat", "XDistance", "Along the plane's X"),
    ("App::PropertyFloat", "YDistance", "Along the plane's Y"),
    ("App::PropertyFloat", "ZAngle", "Turned about the plane's normal (degrees)"),
    ("App::PropertyFloat", "ScaleX", "Width factor"),
    ("App::PropertyFloat", "ScaleY", "Height factor"),
    ("App::PropertyFloat", "BaseWidth", "Width at scale 1 (mm)"),
    ("App::PropertyFloat", "BaseHeight", "Height at scale 1 (mm)"),
    ("App::PropertyPlacement", "PlaneFrame", "The plane it sits on"),
    ("App::PropertyInteger", "PixelWidth", "The image's width in pixels"),
    ("App::PropertyInteger", "PixelHeight", "The image's height in pixels"),
)


def make_canvas(doc, path, pixels, frame, size, label=None):
    """A canvas: an image plane on `frame` (a Placement), `size` = (width, height) mm at scale
    1. The image file is copied into the design (ImageData), so the design opens with its
    canvas on another machine or after the picture was moved."""
    if not path or not os.path.isfile(path):
        raise InsertError("The image was not found: %s" % (path or "(no file)"))
    if os.path.splitext(path)[1].lower() not in IMAGE_EXTENSIONS:
        raise InsertError("Choose a PNG, JPEG, BMP, GIF or TIFF image.")
    obj = doc.addObject(CANVAS_TYPE, "Canvas")
    obj.Label = label or _mesh_label(doc, path)
    bodies.mark(obj, TYPE_CANVAS)
    bodies.hide_from_timeline(obj)  # Fusion keeps canvases out of the timeline
    keeps_copy = _image_kept_in_file(obj)
    for kind, name, text in CANVAS_PROPS:
        if name == "ImageData" and keeps_copy:
            continue  # FreeCAD's own ImageFile already saves the picture inside the design
        bodies.add_prop(obj, kind, name, "Canvas", text)
    if not keeps_copy:
        obj.ImageData = path
    obj.ImageFile = path
    obj.PixelWidth, obj.PixelHeight = int(pixels[0]), int(pixels[1])
    obj.BaseWidth, obj.BaseHeight = float(size[0]), float(size[1])
    obj.ScaleX = obj.ScaleY = 1.0
    obj.CanvasOpacity = 50
    obj.DisplayThrough = True
    obj.PlaneFrame = frame
    apply_canvas(obj)
    return obj


def _image_kept_in_file(obj):
    """FreeCAD 1.x keeps an image plane's picture inside the design file (ImageFile is a
    PropertyFileIncluded); older FreeCADs kept only the path."""
    try:
        return obj.getTypeIdOfProperty("ImageFile") == "App::PropertyFileIncluded"
    except Exception:
        return False


def canvas_options(obj):
    """The dialog values of a canvas, as a dict."""
    return {
        "opacity": int(obj.CanvasOpacity),
        "display_through": bool(obj.DisplayThrough),
        "flip_h": bool(obj.FlipHorizontal),
        "flip_v": bool(obj.FlipVertical),
        "dx": float(obj.XDistance),
        "dy": float(obj.YDistance),
        "angle": float(obj.ZAngle),
        "scale_x": float(obj.ScaleX),
        "scale_y": float(obj.ScaleY),
    }


def set_canvas_options(obj, **values):
    """Write dialog values (keys as in canvas_options) and lay the image out again."""
    names = {
        "opacity": "CanvasOpacity",
        "display_through": "DisplayThrough",
        "flip_h": "FlipHorizontal",
        "flip_v": "FlipVertical",
        "dx": "XDistance",
        "dy": "YDistance",
        "angle": "ZAngle",
        "scale_x": "ScaleX",
        "scale_y": "ScaleY",
    }
    for key, value in values.items():
        prop = names[key]
        current = getattr(obj, prop)
        if isinstance(current, bool) or prop in (
            "DisplayThrough",
            "FlipHorizontal",
            "FlipVertical",
        ):
            value = bool(value)
        elif prop == "CanvasOpacity":
            value = int(max(0, min(100, value)))
        else:
            value = float(value)
        if current != value:
            setattr(obj, prop, value)
    apply_canvas(obj)


def apply_canvas(obj):
    """XSize / YSize / Placement of the image plane from the canvas's values."""
    width = max(1e-3, float(obj.BaseWidth) * float(obj.ScaleX))
    height = max(1e-3, float(obj.BaseHeight) * float(obj.ScaleY))
    if abs(float(obj.XSize.Value) - width) > 1e-9:
        obj.XSize = width
    if abs(float(obj.YSize.Value) - height) > 1e-9:
        obj.YSize = height
    placement = canvas_placement(
        obj.PlaneFrame,
        float(obj.XDistance),
        float(obj.YDistance),
        float(obj.ZAngle),
        bool(obj.FlipHorizontal),
        bool(obj.FlipVertical),
    )
    if not obj.Placement.isSame(placement, 1e-9):
        obj.Placement = placement


def calibrate_canvas(obj, p1, p2, distance):
    """Scale the canvas so the two picked points (design coordinates) are `distance` apart,
    about its centre. Returns the factor."""
    factor = calibrate_scale(p1, p2, distance)
    obj.ScaleX = float(obj.ScaleX) * factor
    obj.ScaleY = float(obj.ScaleY) * factor
    apply_canvas(obj)
    return factor


def is_canvas(obj):
    try:
        return obj is not None and obj.TypeId == CANVAS_TYPE
    except Exception:
        return False


def canvases(doc):
    return [o for o in doc.Objects if is_canvas(o)]


def restore_canvas_images(doc):
    """A design opened where its image file is not: the copy inside the design is used."""
    fixed = []
    for obj in canvases(doc):
        try:
            if "ImageData" not in obj.PropertiesList:
                continue
            if obj.ImageFile and os.path.isfile(obj.ImageFile):
                continue
            inner = obj.ImageData
            if inner and os.path.isfile(inner):
                obj.ImageFile = inner
                fixed.append(obj.Name)
        except Exception as exc:
            warn("canvas %s: image not restored (%s)" % (obj.Label, exc))
    if fixed:
        log("canvas images taken from the design file: %s" % ", ".join(fixed))
    return fixed


def canvas_point(obj, point):
    """A design point projected onto the canvas's plane (where a click landed on it)."""
    import FreeCAD as App

    placement = obj.Placement
    normal = placement.Rotation.multVec(App.Vector(0, 0, 1))
    delta = App.Vector(*point) - placement.Base
    return App.Vector(*point) - normal * delta.dot(normal)


def design_extent(doc):
    """The longest side of the box round the design's shown bodies (0 when empty)."""
    box = None
    for body in bodies.list_bodies(doc):
        try:
            if body.Shape.isNull() or not body.Shape.Solids or not bodies.is_shown(body):
                continue
            b = body.Shape.BoundBox
        except Exception:
            continue
        box = b if box is None else box.united(b)
    if box is None:
        return 0.0
    return max(box.XLength, box.YLength, box.ZLength)
