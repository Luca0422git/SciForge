# SPDX-License-Identifier: LGPL-2.1-or-later
"""The golden models' export report checks (needs FreeCAD; format in export_schema.py).

export_report_expect asks sciforge/export_report.losses() what a file would leave out of
the design, compares it with the model's `expect`, then (roundtrip, the default) writes the
file the way File > Export does and reads it back, so every claim is proven on the real
file, not guessed:

  STEP  read back with SciForge's own STEP reader: the components are there, the bodies
        whose names the report says are lost come back under other names (and only
        those), no sketch, no parameter, no timeline step but the imported shapes, no
        physical material; headless, no colour either (the report says so).
  IGES  read back: no components, no body name.
  STL   one mesh, no names, no colours (binary: every triangle's colour bytes are 0).
  3MF   one object per body with its name, the unit as chosen, no colour or material.
  OBJ   one named group per body, no material file.
  DXF   (a sketch) as many curves as the sketch has (construction left out), no point, no
        dimension.
"""

import os
import shutil
import struct
import tempfile
import zipfile

import FreeCAD as App

from .builder import Builder, BuildError

UNIT_FACTOR = {"Millimeter": 1.0, "Centimeter": 10.0, "Meter": 1000.0, "Inch": 25.4, "Foot": 304.8}


def _bodies_of_steps(builder, ids):
    from sciforge import bodies

    found = []
    for step_id in ids:
        obj = builder.objects.get(step_id)
        body = obj if obj is not None and obj.TypeId.startswith("Mesh::") else bodies.body_of(obj)
        if body is None:
            raise BuildError("export_report_expect: %r is not in a body" % step_id)
        if body not in found:
            found.append(body)
    return found


def _target(builder, step):
    target = step.get("target")
    if target is None:
        return None
    if isinstance(target, list):
        return _bodies_of_steps(builder, target)
    obj = builder.objects.get(target)
    if obj is None:
        raise BuildError("export_report_expect: unknown target %r" % target)
    return obj


def op_hide_bodies(self, step):
    """Test setup: hide the steps' bodies (the browser's eye icon, headless)."""
    for body in _bodies_of_steps(self, step["bodies"]):
        body.Visibility = False
    self.doc.recompute()


def op_sketch_extras(self, step):
    """Test setup: points and construction lines added to a sketch."""
    import Part

    sketch = self.objects[step["target"]]
    for x, y in step.get("points", []):
        sketch.addGeometry(Part.Point(App.Vector(x, y, 0)))
    for x0, y0, x1, y1 in step.get("construction", []):
        sketch.addGeometry(Part.LineSegment(App.Vector(x0, y0, 0), App.Vector(x1, y1, 0)), True)
    self.doc.recompute()


def op_export_report_expect(self, step):
    from sciforge import export_report

    fmt = step["format"]
    target = _target(self, step)
    options = {k: step[k] for k in ("unit", "per_body") if k in step}
    got = export_report.losses(self.doc, target, fmt, **options)
    counts = {item["key"]: item["count"] for item in got}
    if counts != step["expect"]:
        raise BuildError(
            "export_report_expect %s: got %s, expected %s (%s)"
            % (fmt, counts, step["expect"], " | ".join(i["text"] for i in got))
        )
    if not step.get("roundtrip", True):
        return
    folder = tempfile.mkdtemp(prefix="sciforge_export_report_")
    try:
        _roundtrip(self, fmt, target, counts, options, folder)
    finally:
        shutil.rmtree(folder, ignore_errors=True)


# -- round trips -----------------------------------------------------------------------------
def _fail(fmt, text):
    raise BuildError("export_report_expect %s round trip: %s" % (fmt, text))


def _scope(target):
    from sciforge import components

    if target is None:
        return "design", None, None
    if isinstance(target, list):
        return "bodies", None, target
    if components.is_component(target):
        return "component", target, None
    return "bodies", None, [target]


def _roundtrip(builder, fmt, target, counts, options, folder):
    from sciforge import export_report_core as core

    key = core.format_key(fmt)
    if key == "dxf":
        return _dxf_roundtrip(builder, target, counts, folder)
    from sciforge import export_report

    scope, component, chosen = _scope(target)
    written, _hidden = export_report._written(builder.doc, key, scope, component, chosen)
    if key in ("step", "iges"):
        return _cad_roundtrip(builder, key, scope, component, chosen, written, counts, folder)
    return _mesh_roundtrip(builder, fmt, key, written, counts, options, component, folder)


def _cad_roundtrip(builder, key, scope, component, chosen, written, counts, folder):
    from sciforge import bodies, components, exchange, export_report, material, parameters
    from sciforge import step_import, timeline_ops
    from sciforge import exchange_core as xcore

    doc = builder.doc
    path = os.path.join(folder, "roundtrip." + ("step" if key == "step" else "igs"))
    exchange.export_cad(doc, key, path, scope, target=component, chosen=chosen)
    back = App.newDocument("export_report_back")
    try:
        made = step_import.import_file(back, path, xcore.OPEN)
        back.recompute()
        labels = [b.Label for b in bodies.list_bodies(back)]
        pool = list(labels)
        lost = 0
        for body in written:
            if body.Label in pool:
                pool.remove(body.Label)
            else:
                lost += 1
        if lost != counts.get("names", 0):
            _fail(
                key,
                "%d body names lost, the report says %d (back: %s, written: %s)"
                % (lost, counts.get("names", 0), labels, [b.Label for b in written]),
            )
        back_comps = {c.Label for c in components.list_components(back)}
        sent = set()
        for body in written:
            for parent in components.ancestors(body):
                if parent is not component:  # the exported component is the file's top
                    sent.add(parent.Label)
        if key == "step" and not sent <= back_comps:
            _fail(key, "components %s did not come back (%s)" % (sorted(sent), sorted(back_comps)))
        if key == "iges" and back_comps:
            _fail(key, "IGES should hold no components, came back with %s" % sorted(back_comps))
        if back.findObjects("Sketcher::SketchObject"):
            _fail(key, "a sketch came back")
        if parameters.own_names(back):
            _fail(key, "parameters came back")
        bases = export_report.base_features(back)
        real = [
            o
            for o, _b in timeline_ops.steps(back)
            if not components.is_component(o)
            and bodies.kind(o) not in export_report.SHAPE_ONLY_STEPS
            and o.Name not in bases
        ]
        if real:
            _fail(key, "timeline steps came back: %s" % [o.Label for o in real])
        if any(material.key_of(b) for b in bodies.list_bodies(back)):
            _fail(key, "a physical material came back")
        if counts.get("looks"):
            # (the reader gives uncoloured parts its default grey, so the file itself is
            # looked at)
            found = step_colours(path) if key == "step" else iges_colours(path)
            if found:
                _fail(key, "the report says colours are lost, but the file has %d" % found)
        if made.notes.get("loose_faces") or made.notes.get("loose_curves"):
            _fail(key, "reading SciForge's own file left things out: %s" % made.notes)
    finally:
        App.closeDocument(back.Name)


def _mesh_roundtrip(builder, fmt, key, written, counts, options, component, folder):
    import Mesh

    from sciforge import exchange, export
    from sciforge import export_report_core as core

    unit = options.get("unit", "Millimeter")
    path = os.path.join(folder, "roundtrip" + export.extension_of(fmt))
    frame = exchange.component_frame(component) if component is not None else None
    files = export.export_mesh_files(
        builder.doc,
        written,
        fmt,
        path,
        unit=unit,
        per_body=options.get("per_body", False),
        frame=frame,
    )
    labels = [b.Label for b in written]
    if key in ("stl", "stl_ascii"):
        if options.get("per_body") and len(written) > 1:
            if len(files) != len(written):
                _fail(key, "%d files for %d bodies" % (len(files), len(written)))
            return
        data = open(files[0][0], "rb").read()
        if key == "stl":
            count = struct.unpack("<I", data[80:84])[0]
            colours = {data[84 + i * 50 + 48 : 84 + i * 50 + 50] for i in range(count)}
            if colours - {b"\x00\x00"}:
                _fail(key, "binary STL triangles carry colour bytes")
            if any(label.encode() in data[:80] for label in labels if len(label) > 3):
                _fail(key, "a body name is in the STL header")
        else:
            text = data.decode("utf-8", "replace")
            if text.count("endsolid") != 1:
                _fail(key, "ASCII STL should hold one solid, holds %d" % text.count("endsolid"))
        mesh = Mesh.Mesh(files[0][0])
        if counts.get("merged") and mesh.countComponents() < counts["merged"]:
            _fail(
                key,
                "%d bodies merged, but the mesh has %d pieces"
                % (counts["merged"], mesh.countComponents()),
            )
        return
    if key == "3mf":
        with zipfile.ZipFile(files[0][0]) as archive:
            model = [
                archive.read(n).decode("utf-8") for n in archive.namelist() if n.endswith(".model")
            ]
        facts = core.three_mf_facts(model[0])
        if facts["objects"] != len(written):
            _fail(key, "%d objects for %d bodies" % (facts["objects"], len(written)))
        if facts["colours"]:
            _fail(key, "the 3MF has colours, the report says they are lost")
        if facts["file_unit"] != unit:
            _fail(key, "the 3MF says %s, %s was chosen" % (facts["file_unit"], unit))
        for label in labels:
            if 'name="%s"' % label not in model[0]:
                _fail(key, "body %s has no named object" % label)
        return
    if key == "obj":
        text = open(files[0][0], encoding="utf-8", errors="replace").read()
        if core.obj_has_colours(text):
            _fail(key, "the OBJ names a material file")
        groups = [line[2:].strip() for line in text.splitlines() if line.startswith("g ")]
        if groups != labels:
            _fail(key, "groups %s, bodies %s" % (groups, labels))


def step_colours(path):
    """How many colour definitions a STEP file holds (OpenCASCADE writes red, green, blue
    ... as named colours, the others as RGB)."""
    with open(path, encoding="utf-8", errors="replace") as handle:
        text = handle.read()
    return text.count("COLOUR_RGB") + text.count("DRAUGHTING_PRE_DEFINED_COLOUR")


def iges_colours(path):
    """How many entities of an IGES file have a colour: colour definitions (type 314)
    and directory entries whose colour number (second line, columns 17-24) is set."""
    lines = [line.rstrip("\r\n") for line in open(path, encoding="utf-8", errors="replace")]
    entries = [line for line in lines if len(line) >= 73 and line[72] == "D"]
    count = 0
    for first, second in zip(entries[0::2], entries[1::2]):
        if first[0:8].strip() == "314":
            count += 1
        elif second[16:24].strip() not in ("", "0"):
            count += 1
    return count


def dxf_entities(path):
    """{entity type: count} of a DXF's ENTITIES section."""
    lines = [line.strip() for line in open(path, encoding="utf-8", errors="replace")]
    out = {}
    section = None
    for i in range(0, len(lines) - 1, 2):
        code, value = lines[i], lines[i + 1]
        if code == "0" and value == "SECTION" and i + 3 < len(lines):
            section = lines[i + 3]
            continue
        if code == "0" and value == "ENDSEC":
            section = None
            continue
        if code == "0" and section == "ENTITIES":
            out[value] = out.get(value, 0) + 1
    return out


def _dxf_roundtrip(builder, sketch, counts, folder):
    from sciforge import exchange

    path = exchange.export_dxf((sketch, ""), os.path.join(folder, "roundtrip.dxf"))
    found = dxf_entities(path)
    curves = sum(
        v
        for k, v in found.items()
        if k in ("LINE", "ARC", "CIRCLE", "ELLIPSE", "SPLINE", "LWPOLYLINE", "POLYLINE")
    )
    wanted = len(sketch.Shape.Edges)  # construction geometry is not in the sketch's shape
    if curves != wanted:
        _fail("DXF", "%d curves written, the sketch shows %d (%s)" % (curves, wanted, found))
    for kind in ("POINT", "DIMENSION"):
        if found.get(kind):
            _fail(
                "DXF", "%d %s entities written, the report says they are lost" % (found[kind], kind)
            )
    total = len(sketch.Geometry)
    if counts.get("construction_curves") or counts.get("points"):
        if curves >= total:
            _fail("DXF", "every geometry of the sketch was written (%d of %d)" % (curves, total))


# -- imports ---------------------------------------------------------------------------------
DXF_EXTRAS = "\n".join(
    [
        "0",
        "SECTION",
        "2",
        "HEADER",
        "9",
        "$INSUNITS",
        "70",
        "4",
        "0",
        "ENDSEC",
        "0",
        "SECTION",
        "2",
        "ENTITIES",
        "0",
        "LINE",
        "8",
        "0",
        "10",
        "0",
        "20",
        "0",
        "30",
        "0",
        "11",
        "50",
        "21",
        "0",
        "31",
        "0",
        "0",
        "CIRCLE",
        "8",
        "0",
        "10",
        "25",
        "20",
        "25",
        "30",
        "0",
        "40",
        "10",
        "0",
        "TEXT",
        "8",
        "0",
        "10",
        "5",
        "20",
        "5",
        "30",
        "0",
        "40",
        "2.5",
        "1",
        "HELLO",
        "0",
        "POINT",
        "8",
        "0",
        "10",
        "1",
        "20",
        "1",
        "30",
        "0",
        "0",
        "HATCH",
        "8",
        "0",
        "10",
        "0",
        "20",
        "0",
        "30",
        "0",
        "2",
        "SOLID",
        "70",
        "1",
        "71",
        "0",
        "91",
        "0",
        "75",
        "0",
        "76",
        "1",
        "98",
        "0",
        "0",
        "ENDSEC",
        "0",
        "EOF",
        "",
    ]
)
SVG_EXTRAS = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="100mm" height="50mm" viewBox="0 0 100 50">'
    '<rect x="10" y="10" width="30" height="20" fill="none" stroke="black"/>'
    '<text x="50" y="20">Label</text>'
    '<image x="60" y="5" width="10" height="10" href="data:image/png;base64,iVBORw0KGgo="/>'
    "</svg>"
)
THREE_MF = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<model unit="inch" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
    '<resources><basematerials id="1"><base name="red" displaycolor="#FF0000"/></basematerials>'
    "%s</resources><build>%s</build></model>"
)
TETRA = (
    '<object id="%d" type="model" name="T%d"><mesh><vertices>'
    '<vertex x="%d" y="0" z="0"/><vertex x="%d" y="0" z="0"/><vertex x="%d" y="1" z="0"/>'
    '<vertex x="%d" y="0" z="1"/></vertices><triangles><triangle v1="0" v2="2" v3="1"/>'
    '<triangle v1="0" v2="1" v3="3"/><triangle v1="1" v2="2" v3="3"/>'
    '<triangle v1="0" v2="3" v3="2"/></triangles></mesh></object>'
)


def make_import_file(name, folder):
    """Write one of the import test files (export_schema.IMPORT_FILES) into `folder`."""
    import Mesh
    import Part

    path = os.path.join(folder, name)
    if name == "open_box.stl":  # a 10 mm box with one side (two triangles) missing
        box = Mesh.createBox(10, 10, 10)
        points, facets = box.Topology
        Mesh.Mesh([[points[i] for i in f] for f in facets[2:]]).write(path)
    elif name == "two_objects_inch.3mf":  # two closed tetrahedra, red, in inches
        objects = "".join(TETRA % (n + 2, n, 3 * n, 3 * n + 1, 3 * n, 3 * n) for n in range(2))
        build = "".join('<item objectid="%d"/>' % (n + 2) for n in range(2))
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("3D/3dmodel.model", THREE_MF % (objects, build))
            archive.writestr(
                "[Content_Types].xml",
                '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/'
                '2006/content-types"><Default Extension="model" ContentType="application/'
                'vnd.ms-package.3dmanufacturing-3dmodel+xml"/></Types>',
            )
            archive.writestr(
                "_rels/.rels",
                '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/'
                'package/2006/relationships"><Relationship Target="/3D/3dmodel.model" '
                'Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/'
                '3dmodel"/></Relationships>',
            )
    elif name in ("mixed.step", "faces.igs"):
        import Import

        box = Part.makeBox(10, 10, 10)
        if name == "mixed.step":  # one part: a solid, 5 loose faces and a loose line
            shape = Part.makeCompound(
                [
                    box.translated(App.Vector(40, 0, 0)),
                    Part.Shell(box.Faces[1:]),
                    Part.makeLine(App.Vector(20, 0, 0), App.Vector(30, 0, 0)),
                ]
            )
        else:  # faces only that do not close (IGES written as loose faces)
            shape = Part.Shell(box.Faces[1:])
        doc = App.newDocument("import_report_file", "file", True, True)
        try:
            feature = doc.addObject("Part::Feature", "Mixed")
            feature.Shape = shape
            doc.recompute()
            Import.export([feature], path)
        finally:
            App.closeDocument(doc.Name)
    elif name == "extras.dxf":
        with open(path, "w") as handle:
            handle.write(DXF_EXTRAS)
    elif name == "extras.svg":
        with open(path, "w") as handle:
            handle.write(SVG_EXTRAS)
    return path


def import_items(path):
    """What export_report says an import of `path` did not bring in, read the way the
    Insert commands and File > Open read it."""
    from sciforge import export_report, insert, step_import

    ext = os.path.splitext(path)[1].lower()
    if ext in (".stl", ".3mf", ".obj"):
        mesh = insert.read_mesh(path)
        return export_report.mesh_import_items(path, mesh, "Millimeter")
    if ext in (".step", ".stp", ".igs", ".iges"):
        notes = {}
        step_import.read_tree(path, notes)
        return export_report.cad_import_items(notes)
    notes = {}
    raw = insert.read_curves(path, notes)
    geos = sum(len(insert.curves_to_geometry(edges)) for _name, edges in raw)
    notes["skipped"] = sum(len(edges) for _name, edges in raw) - geos
    return export_report.curve_import_items(path, notes)


def op_import_report_expect(self, step):
    folder = tempfile.mkdtemp(prefix="sciforge_import_report_")
    try:
        got = import_items(make_import_file(step["file"], folder))
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    counts = {}
    for item in got:
        counts[item["key"]] = counts.get(item["key"], 0) + item["count"]
    if counts != step["expect"]:
        raise BuildError(
            "import_report_expect %s: got %s, expected %s (%s)"
            % (step["file"], counts, step["expect"], " | ".join(i["text"] for i in got))
        )


Builder.op_import_report_expect = op_import_report_expect
Builder.op_export_report_expect = op_export_report_expect
Builder.op_hide_bodies = op_hide_bodies
Builder.op_sketch_extras = op_sketch_extras
