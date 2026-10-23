# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's sketch Text, without GUI code: the Text dialog (text_ui.py), Extrude, Emboss
and the golden-model builder all use this module.

A text belongs to a sketch, like Fusion's (one entity of the sketch, edited with a
double-click, exploded into curves on request). In FreeCAD it is a small object of its
own next to the sketch, in the same body:

  SketchText   a Part::Part2DObjectPython (SciForgeType / SciForgeRole "SketchText") that
               keeps what the Text dialog shows (text, height, font, bold / italic /
               underline, alignment, character spacing, flips, type, path placement) and
               whose shape is the letters as flat faces in the sketch's plane. Extrude and
               Emboss take it as one profile (Fusion: a click on a text picks the whole
               text); PartDesign's Pad uses its faces directly. It is never a timeline step
               or a browser row of its own: it is part of its sketch.
  the frame    Type Text: four construction lines in the sketch, a rectangle that can be
               dimensioned and constrained like any sketch geometry (Fusion's text frame).
               The letters are set inside it (alignment), turned with it (Angle) and move
               with it. The text finds its lines by their geometry ids (FrameIds), which
               FreeCAD keeps across edits, undo and saving.
  the path     Type Text On Path: a curve of the sketch (PathId) the letters follow.

The letters' outlines come from FreeCAD's FreeType reader (Part.makeWireString) for the
font file of the chosen family (fonts.py finds it); each character is outlined once per
font and placed with text_core's layout. A family that is not installed (a design opened
on another computer) falls back to the default family and says so; the saved shape stays
as it was until the text is computed again.
"""

import math
import os

import FreeCAD as App

from . import fonts, log, sketch_geometry, warn
from . import text_core as core

TYPE = "Part::Part2DObjectPython"
KIND = "SketchText"
ROLE_PROP = "SciForgeRole"
CACHE_EM = 100.0  # glyph outlines are made at this em size, then scaled
TYPE_NAMES = {"text": "Text", "path": "Text On Path"}
H_NAMES = {"left": "Left", "center": "Center", "right": "Right"}
V_NAMES = {"top": "Top", "middle": "Middle", "bottom": "Bottom"}
DEFAULT_HEIGHT = 5.0
TOL = 1e-7


class TextError(core.TextError):
    """The text cannot be made; the message says why and what to do."""


# -- fonts ------------------------------------------------------------------------------------
_FONTS = {"catalog": None, "told": set(), "missing": []}
# called with the document's name when a text of an opening design lacks its font
# (text_ui shows the message once the design is open)
ON_FONT_MISSING = []


def freecad_font_files():
    """Font files FreeCAD itself ships (there whatever the computer has): DejaVu Sans in
    its Python bundle (matplotlib), osifont with TechDraw, the AppImage's own folder."""
    found = []
    try:
        res = App.getResourceDir()
        folder = os.path.join(res, "Mod", "TechDraw", "Resources", "fonts")
        if os.path.isdir(folder):
            found += [
                os.path.join(folder, n)
                for n in sorted(os.listdir(folder))
                if n.lower().startswith("osifont") and n.lower().endswith(".ttf")
            ]
    except Exception:
        pass
    try:
        import sys

        for base in sys.path:
            folder = os.path.join(base, "matplotlib", "mpl-data", "fonts", "ttf")
            if os.path.isdir(folder):
                found += [
                    os.path.join(folder, n)
                    for n in sorted(os.listdir(folder))
                    if n.startswith("DejaVuSans") and n.endswith(".ttf")
                ]
                break
    except Exception:
        pass
    return found


def freecad_font_dirs():
    found = []
    try:
        folder = os.path.join(App.getHomePath(), "fonts")  # the Linux AppImage's own fonts
        if os.path.isdir(folder):
            found.append(folder)
    except Exception:
        pass
    return found


def _cache_file():
    try:
        return os.path.join(App.getUserAppDataDir(), "SciForge", "fonts.json")
    except Exception:
        return None


class _Catalog(fonts.Catalog):
    pass


def catalog(refresh=False):
    """Every font family of this computer (fonts.Catalog), scanned once per session."""
    if _FONTS["catalog"] is None or refresh:
        dirs = fonts.system_dirs(extra=freecad_font_dirs())
        found = fonts.scan(dirs, _cache_file())
        extra = []
        known = {os.path.normcase(f.path) for f in found.faces}
        for path in freecad_font_files():
            if os.path.normcase(path) in known:
                continue
            try:
                extra.append(fonts.read_info(path))
            except Exception:
                continue
        _FONTS["catalog"] = fonts.Catalog(found.faces + extra)
        log("fonts: %d families found" % len(_FONTS["catalog"].families()))
    return _FONTS["catalog"]


def default_family():
    return catalog().default_family()


def resolve_font(family, bold=False, italic=False):
    """(FontInfo, make_bold, make_italic, family used, note). A family that is not on
    this computer is replaced by the default one, and `note` says so."""
    cat = catalog()
    note = ""
    used = cat.find_family(family) if family else None
    if used is None:
        fallback = cat.default_family()
        if fallback is None:
            raise TextError(
                "No font was found on this computer. Install a TrueType font (for example "
                "DejaVu Sans) and try again."
            )
        if family:
            note = (
                "The font '%s' is not installed on this computer: the text uses '%s'. "
                "Pick a font to keep it that way." % (family, fallback)
            )
        used = fallback
    face = cat.face_for(used, bold, italic)
    if face is None:
        raise TextError("The font '%s' cannot be read." % used)
    info, make_bold, make_italic = face
    return info, make_bold, make_italic, used, note


# -- glyph outlines -----------------------------------------------------------------------------
class GlyphShape:
    """One character's outline at CACHE_EM, pen origin at (0, 0) on the baseline: Part
    wires and faces, and the same as plain points for drawing (polylines, triangles)."""

    __slots__ = ("wires", "faces", "outlines", "points", "triangles")

    def __init__(self, wires, faces):
        self.wires = wires
        self.faces = faces
        self.outlines = []
        self.points = []
        self.triangles = []
        for wire in wires:
            try:
                pts = wire.discretize(Deflection=CACHE_EM * 0.002)
                self.outlines.append([(p.x, p.y) for p in pts])
            except Exception:
                continue
        for face in faces:
            try:
                verts, tris = face.tessellate(CACHE_EM * 0.004)
            except Exception:
                continue
            base = len(self.points)
            self.points += [(v.x, v.y) for v in verts]
            self.triangles += [(base + a, base + b, base + c) for a, b, c in tris]


class _FontGlyphs:
    """The glyphs of one font file (and one synthetic weight), made on demand."""

    def __init__(self, info, make_bold):
        self.info = info
        self.make_bold = make_bold
        self.height_param = None
        self.glyphs = {}

    def _param(self):
        """The makeWireString height that gives an em of CACHE_EM. FreeCAD's FreeType
        reader scales by the font's line height (FreeType's face->height, from 'hhea'),
        so the number depends on the font: worked out from that and checked against a
        real outline (two letters' advance)."""
        if self.height_param is not None:
            return self.height_param
        import Part

        info = self.info
        height = getattr(info, "ft_height", 0) or info.line_height or info.units_per_em
        guess = CACHE_EM * height / 3072.0
        param = guess
        try:
            probe = None
            for ch in "HMXNO0o":
                if info.has_char(ch):
                    probe = ch
                    break
            if probe is not None:
                pair = Part.makeWireString(probe + probe, info.path, guess, 0.0)
                if len(pair) == 2 and pair[0] and pair[1]:
                    a = Part.Compound(pair[0]).BoundBox.XMin
                    b = Part.Compound(pair[1]).BoundBox.XMin
                    measured = b - a
                    expected = (
                        (info.advance(probe) + info.kerning(probe, probe))
                        * CACHE_EM
                        / info.units_per_em
                    )
                    if measured > 1e-9 and abs(measured / expected - 1.0) > 0.01:
                        param = guess * expected / measured
        except Exception as exc:
            warn("font %s: %s" % (os.path.basename(info.path), exc))
        self.height_param = param
        return param

    def get(self, char):
        shape = self.glyphs.get(char)
        if shape is None:
            shape = self._make(char)
            self.glyphs[char] = shape
        return shape

    def _make(self, char):
        import Part

        if char.isspace():
            return GlyphShape([], [])
        try:
            made = Part.makeWireString(char, self.info.path, self._param(), 0.0)
        except Exception as exc:
            warn("font %s: '%s': %s" % (os.path.basename(self.info.path), char, exc))
            return GlyphShape([], [])
        wires = [w for chunk in made for w in chunk if w is not None and not w.isNull()]
        closed = [w for w in wires if w.isClosed()]
        faces = make_faces(closed) if closed else []
        if self.make_bold and faces:
            faces = _embolden(faces)
            wires = [w for f in faces for w in f.Wires]
        return GlyphShape(wires, faces)


_GLYPHS = {}


def font_glyphs(info, make_bold=False):
    key = (os.path.normcase(info.path), bool(make_bold))
    found = _GLYPHS.get(key)
    if found is None:
        found = _FontGlyphs(info, make_bold)
        _GLYPHS[key] = found
    return found


def make_faces(wires):
    """Faces from a glyph's closed contours (holes inside letters kept), like Draft's
    ShapeString: FreeCAD's bullseye face maker, then the others for awkward fonts."""
    import Part

    for maker in ("Part::FaceMakerBullseye", "Part::FaceMakerCheese", "Part::FaceMakerSimple"):
        try:
            faces = list(Part.makeFace(wires, maker).Faces)
            for face in faces:
                face.validate()
            break
        except Exception:
            faces = []
    out = []
    for face in faces:
        try:
            if face.normalAt(0, 0).z < 0:
                face.reverse()
        except Exception:
            pass
        out.append(face)
    return out


def _embolden(faces):
    """A bolder letter for a family without a bold face: the outline grows by em/48 on
    each side (FreeType's synthetic bold), counters shrink."""
    grown = []
    for face in faces:
        try:
            result = face.makeOffset2D(CACHE_EM / 48.0, 0, False, False, False)
            grown += list(result.Faces)
        except Exception:
            grown.append(face)
    return grown


# -- the plan: where every letter goes -----------------------------------------------------------
class Placement2D:
    """One glyph placed: its outline and the affine transform (text_core) to the sketch."""

    __slots__ = ("shape", "transform", "char")

    def __init__(self, shape, transform, char):
        self.shape = shape
        self.transform = transform
        self.char = char


class Plan:
    """Everything one text draws, in sketch coordinates (no OpenCASCADE work yet): the
    placed glyphs, underline boxes, the frame or path, and notes for the dialog."""

    def __init__(self):
        self.glyphs = []  # [Placement2D]
        self.underlines = []  # [[(x, y)] * 4] rectangles
        self.frame = None  # (corner, angle, width, height) for Type Text
        self.path_points = None  # [(x, y)] the path, for drawing
        self.notes = []
        self.text = ""
        self.font = ""

    # -- drawing data (pure Python) ---------------------------------------------------
    def outlines(self):
        """[[(x, y), ...]] closed polylines of every letter and underline."""
        out = []
        for g in self.glyphs:
            t = g.transform
            for line in g.shape.outlines:
                out.append([core.apply(t, x, y) for x, y in line])
        for box in self.underlines:
            out.append(list(box) + [box[0]])
        return out

    def triangles(self):
        """(points [(x, y)], triangles [(i, j, k)]) filling every letter and underline."""
        points, tris = [], []
        for g in self.glyphs:
            t = g.transform
            base = len(points)
            points += [core.apply(t, x, y) for x, y in g.shape.points]
            tris += [(base + a, base + b, base + c) for a, b, c in g.shape.triangles]
        for box in self.underlines:
            base = len(points)
            points += list(box)
            tris += [(base, base + 1, base + 2), (base, base + 2, base + 3)]
        return points, tris

    def bounds(self):
        """(x0, y0, x1, y1) of the letters, or None."""
        xs, ys = [], []
        for line in self.outlines():
            for x, y in line:
                xs.append(x)
                ys.append(y)
        if not xs:
            return None
        return min(xs), min(ys), max(xs), max(ys)

    # -- OpenCASCADE faces ----------------------------------------------------------------
    def faces(self):
        """The letters as Part faces in sketch coordinates (z = 0), overlapping letters and
        the underline merged, every face facing +Z."""
        import Part

        out = []
        for g in self.glyphs:
            if not g.shape.faces:
                continue
            matrix = _matrix(g.transform)
            try:
                # the contours are moved, then made into flat faces again: a slant (made up
                # italic) turns a moved face into a curved NURBS one that would not merge
                # with its neighbours or the underline
                wires = [w.transformGeometry(matrix) for w in g.shape.wires]
                out += make_faces([w for w in wires if w.isClosed()])
            except Exception as exc:
                warn("text: letter '%s': %s" % (g.char, exc))
        boxes = []
        for box in self.underlines:
            try:
                poly = Part.makePolygon([App.Vector(x, y, 0) for x, y in box + [box[0]]])
                boxes.append(Part.Face(poly))
            except Exception as exc:
                warn("text: underline: %s" % exc)
        out = _merge_overlaps(out + boxes)
        fixed = []
        for face in out:
            try:
                if face.normalAt(0, 0).z < 0:
                    face.reverse()
            except Exception:
                pass
            fixed.append(face)
        return fixed

    def shape(self):
        import Part

        faces = self.faces()
        if faces:
            return Part.Compound(faces)
        wires = []
        for g in self.glyphs:  # a single-line (stick) font: lines only, no areas
            matrix = _matrix(g.transform)
            for wire in g.shape.wires:
                try:
                    wires.append(wire.transformGeometry(matrix))
                except Exception:
                    continue
        return Part.Compound(wires)


def _matrix(t):
    a, b, c, d, e, f = t
    return App.Matrix(a, b, 0, e, c, d, 0, f, 0, 0, 1, 0, 0, 0, 0, 1)


def _overlap(a, b):
    ba, bb = a.BoundBox, b.BoundBox
    return not (
        ba.XMax < bb.XMin - TOL
        or bb.XMax < ba.XMin - TOL
        or ba.YMax < bb.YMin - TOL
        or bb.YMax < ba.YMin - TOL
    )


def _merge_overlaps(faces):
    """Letters that overlap (a tight spacing, an underline through descenders, a bold
    made up) become one face: overlapping profiles would make a broken extrusion."""
    if len(faces) < 2:
        return faces
    groups = []  # lists of faces that touch
    for face in faces:
        hits = [g for g in groups if any(_overlap(face, o) and _area_overlap(face, o) for o in g)]
        if not hits:
            groups.append([face])
            continue
        merged = [face]
        for g in hits:
            merged += g
            groups.remove(g)
        groups.append(merged)
    out = []
    for group in groups:
        if len(group) == 1:
            out.append(group[0])
            continue
        try:
            fused = group[0].fuse(group[1:]).removeSplitter()
            out += list(fused.Faces)
        except Exception as exc:
            warn("text: could not merge overlapping letters: %s" % exc)
            out += group
    return out


def _area_overlap(a, b):
    try:
        common = a.common(b)
        return common.Area > 1e-6 * max(1.0, min(a.Area, b.Area))
    except Exception:
        return False


# -- the spec: what the dialog shows ----------------------------------------------------------
def default_spec():
    return {
        "type": "text",
        "text": "",
        "height": DEFAULT_HEIGHT,
        "font": "",
        "bold": False,
        "italic": False,
        "underline": False,
        "h_align": "left",
        "v_align": "top",
        "spacing": 0.0,
        "flip_h": False,
        "flip_v": False,
        "angle": 0.0,
        "corner": (0.0, 0.0),
        "width": 0.0,
        "frame_height": 0.0,
        "frame_ids": [],
        "path_id": 0,
        "above": True,
        "fit": False,
    }


def check_spec(spec):
    core.check_height(spec["height"])
    core.check_spacing(spec["spacing"])
    if spec["type"] not in core.TYPES:
        raise TextError("Unknown text type %r." % spec["type"])


def plan(spec, sketch=None, text=None, lookup=None):
    """The Plan of a spec. `text`: the resolved text (else evaluated from spec["text"]);
    `sketch` gives the frame lines and the path. Raises TextError."""
    check_spec(spec)
    if text is None:
        text = core.evaluate(spec["text"], lookup)
    core.check_text(text)
    info, make_bold, make_italic, used, note = resolve_font(
        spec["font"], spec["bold"], spec["italic"]
    )
    result = Plan()
    result.text = text
    result.font = used
    if note:
        result.notes.append(note)
    glyphs = font_glyphs(info, make_bold)
    unit = spec["height"] / CACHE_EM
    italic = core.shear_x(core.ITALIC_SLANT) if make_italic else core.IDENTITY
    local = core.chain(core.scaling(unit), italic)  # glyph cache -> layout mm
    missing = sorted({c for c in text if not c.isspace() and not info.has_char(c)})
    if missing:
        result.notes.append(
            "'%s' has no %s: shown as the font's empty box."
            % (used, ", ".join("'%s'" % c for c in missing[:8]))
        )
    if spec["type"] == "path":
        _plan_path(result, spec, sketch, text, info, make_bold, glyphs, local)
    else:
        _plan_frame(result, spec, sketch, text, info, make_bold, glyphs, local)
    if not result.glyphs:
        raise TextError("Type some text first: an empty text makes no profile.")
    return result


def frame_of(spec, sketch):
    """(corner, angle, width, height): the frame lines in the sketch when they are there,
    else the spec's own values."""
    if sketch is not None and spec.get("frame_ids"):
        found = read_frame(sketch, spec["frame_ids"])
        if found is not None:
            return found
    return (
        tuple(spec["corner"]),
        float(spec["angle"]),
        float(spec["width"]),
        float(spec["frame_height"]),
    )


def _plan_frame(result, spec, sketch, text, info, make_bold, glyphs, local):
    corner, angle, width, height = frame_of(spec, sketch)
    result.frame = (corner, angle, width, height)
    placed, lines = core.block(
        text,
        info,
        spec["height"],
        spec["spacing"],
        spec["h_align"],
        spec["v_align"],
        width,
        height,
        bold=make_bold,
    )
    frame = core.frame_transform(corner, angle, width, height, spec["flip_h"], spec["flip_v"])
    for g in placed:
        shape = glyphs.get(g.char)
        if not shape.wires:
            continue
        t = core.chain(local, core.translation(g.x, g.y), frame)
        result.glyphs.append(Placement2D(shape, t, g.char))
    if spec["underline"]:
        for x0, x1, baseline in lines:
            if x1 - x0 < 1e-9:
                continue
            bx0, by0, bx1, by1 = core.underline_box(info, spec["height"], x0, x1, baseline)
            box = [(bx0, by0), (bx1, by0), (bx1, by1), (bx0, by1)]
            mapped = [core.apply(frame, x, y) for x, y in box]
            if core.determinant(frame) < 0:
                mapped.reverse()
            result.underlines.append(mapped)


def _plan_path(result, spec, sketch, text, info, make_bold, glyphs, local):
    edge = path_edge(sketch, spec["path_id"]) if sketch is not None else None
    if edge is None:
        raise TextError("Select the path: click a curve of the sketch for the text to follow.")
    sampler = PathSampler(edge)
    try:
        result.path_points = [(p.x, p.y) for p in sampler.edge.discretize(Deflection=0.05)]
    except Exception:
        result.path_points = None
    line = " ".join(core.lines_of(text))
    placed, lines = core.block(
        line, info, spec["height"], spec["spacing"], "left", "bottom", 0.0, 0.0, bold=make_bold
    )
    # (block() puts a single line's baseline at the descent: back onto 0)
    for g in placed:
        g.y = 0.0
    width = lines[0][1] - lines[0][0] if lines else 0.0
    length = sampler.length
    slots = core.path_slots(
        placed, width, length, spec["h_align"], spec["fit"], closed=sampler.closed
    )
    if not spec["fit"] and width > length + 1e-6:
        result.notes.append(
            "The text is longer than the path (%.1f mm of %.1f mm): it runs past its end."
            % (width, length)
        )
    offset = 0.0 if spec["above"] else core.below_offset(info, spec["height"])
    for g, distance in slots:
        shape = glyphs.get(g.char)
        if not shape.wires:
            continue
        if spec["flip_h"]:
            distance = length - distance
        point, tangent = sampler.at(distance)
        if spec["flip_h"]:
            tangent = (-tangent[0], -tangent[1])
        t = core.path_glyph_transform(point, tangent, g, offset, False, spec["flip_v"])
        result.glyphs.append(Placement2D(shape, core.compose(t, local), g.char))
    if spec["underline"]:
        result.notes.append("Underline is not drawn for text on a path.")


# -- the path -----------------------------------------------------------------------------------
class PathSampler:
    """A sketch curve read in Fusion's reading direction: lines, arcs and open splines left
    to right along their chord (the letters stand above the curve as seen in the sketch);
    full circles and ellipses clockwise from their lowest point, so a centred text sits
    at the top. Beyond its ends the path goes on straight."""

    def __init__(self, edge):
        self.edge = edge
        self.length = edge.Length
        self.reverse = False
        self.start_length = 0.0
        first, last = edge.FirstParameter, edge.LastParameter
        p0, p1 = edge.valueAt(first), edge.valueAt(last)
        self.closed = edge.isClosed() or (p1 - p0).Length < 1e-9
        if self.closed:
            # closed: start at the lowest point, go clockwise
            lowest = min(
                (first + (last - first) * i / 360.0 for i in range(361)),
                key=lambda u: edge.valueAt(u).y,
            )
            self.start_length = self._length_to(lowest)
            # the curve's own direction at the bottom: +x means counter-clockwise
            if edge.tangentAt(lowest).x > 0:
                self.reverse = True
        else:
            dx, dy = p1.x - p0.x, p1.y - p0.y
            if dx < -1e-9 or (abs(dx) <= 1e-9 and dy < 0):
                self.reverse = True

    def _length_to(self, u):
        try:
            return self.edge.Curve.length(self.edge.FirstParameter, u)
        except Exception:
            return 0.0

    def _param(self, s):
        """Curve parameter at arc length s (0..length) from the curve's own start."""
        return self.edge.getParameterByLength(max(0.0, min(self.length, s)))

    def at(self, s):
        """((x, y), unit tangent) at reading distance s; beyond the ends: straight on."""
        L = self.length
        closed = self.edge.isClosed()
        if closed:
            s_mod = s % L if L > 0 else 0.0
            if self.reverse:
                own = (self.start_length - s_mod) % L
            else:
                own = (self.start_length + s_mod) % L
            u = self._param(own)
            p = self.edge.valueAt(u)
            t = self.edge.tangentAt(u)
            if self.reverse:
                t = t * -1.0
            return (p.x, p.y), _unit(t)
        over = 0.0
        if s < 0.0:
            over, s = s, 0.0
        elif s > L:
            over, s = s - L, L
        own = L - s if self.reverse else s
        u = self._param(own)
        p = self.edge.valueAt(u)
        t = self.edge.tangentAt(u)
        if self.reverse:
            t = t * -1.0
        tx, ty = _unit(t)
        return (p.x + tx * over, p.y + ty * over), (tx, ty)


def _unit(v):
    length = math.hypot(v.x, v.y)
    if length < 1e-12:
        return (1.0, 0.0)
    return (v.x / length, v.y / length)


# -- geometry in the sketch: ids, the frame, the path -----------------------------------------
def geo_index(sketch, geo_id):
    """The index of the sketch geometry with this id (FreeCAD's GeometryId), or None."""
    if not geo_id:
        return None
    try:
        count = len(sketch.Geometry)
        for i in range(count):
            if sketch.getGeometryId(i) == geo_id:
                return i
    except Exception:
        pass
    return None


def geo_id(sketch, index):
    return sketch.getGeometryId(index)


def path_edge(sketch, path_id):
    """The path curve as an edge in sketch coordinates, or None."""
    index = geo_index(sketch, path_id)
    if index is None:
        return None
    try:
        return sketch.Geometry[index].toShape()
    except Exception:
        return None


def read_frame(sketch, ids):
    """(corner, angle, width, height) of the frame lines [bottom, right, top, left], or
    None when one of them is gone."""
    if not ids or len(ids) != 4:
        return None
    lines = []
    for gid in ids:
        index = geo_index(sketch, gid)
        if index is None:
            return None
        geo = sketch.Geometry[index]
        if not hasattr(geo, "StartPoint") or geo.TypeId != "Part::GeomLineSegment":
            return None
        lines.append(geo)
    bottom, right, top, left = lines
    bl = (bottom.StartPoint.x, bottom.StartPoint.y)
    br = (bottom.EndPoint.x, bottom.EndPoint.y)
    tr = (top.StartPoint.x, top.StartPoint.y)
    tl = (top.EndPoint.x, top.EndPoint.y)
    return core.frame_from_corners(bl, br, tr, tl)


def add_frame(sketch, corner, angle, width, height):
    """Four construction lines forming the text frame, held as a rectangle (it can turn,
    move and change size, never lose its square corners). Returns their geometry ids
    [bottom, right, top, left]."""
    import Part
    import Sketcher

    corners = core.frame_corners(corner, angle, width, height)
    points = [App.Vector(x, y, 0) for x, y in corners]
    indices = []
    for i in range(4):
        line = Part.LineSegment(points[i], points[(i + 1) % 4])
        indices.append(sketch.addGeometry(line, True))
    constraints = [
        Sketcher.Constraint("Coincident", indices[i], 2, indices[(i + 1) % 4], 1) for i in range(4)
    ]
    constraints += [
        Sketcher.Constraint("Perpendicular", indices[0], indices[1]),
        Sketcher.Constraint("Parallel", indices[0], indices[2]),
        Sketcher.Constraint("Parallel", indices[1], indices[3]),
    ]
    first = len(sketch.Constraints)
    sketch.addConstraint(constraints)
    try:
        # Fusion shows a text frame without constraint symbols: they work, unseen
        sketch.setVirtualSpace(list(range(first, len(sketch.Constraints))), True)
    except Exception:
        pass
    _solve(sketch)
    return [sketch.getGeometryId(i) for i in indices]


def _solve(sketch):
    """Solve the sketch so an open sketch shows what was added at once (FreeCAD draws an
    edited sketch from its last solve)."""
    try:
        sketch.solve()
    except Exception:
        pass


def set_frame(sketch, ids, corner, angle, width, height):
    """Put the frame lines at a new place / angle / size (the dialog's Angle, a drag of
    the rotation handle). The sketch's solver keeps any dimension the user added: the
    frame then stays where those put it. Returns True if the lines took the new place."""
    indices = [geo_index(sketch, gid) for gid in ids or []]
    if len(indices) != 4 or any(i is None for i in indices):
        return False
    corners = [App.Vector(x, y, 0) for x, y in core.frame_corners(corner, angle, width, height)]
    geos = sketch.Geometry
    changes = {}
    for k, index in enumerate(indices):
        geo = geos[index]
        geo.StartPoint = corners[k]
        geo.EndPoint = corners[(k + 1) % 4]
        changes[index] = geo
    # only the frame lines change; the sketch's other curves keep their construction flags
    # and ids (assigning sketch.Geometry made construction points normal ones)
    sketch_geometry.set_geometry(sketch, changes)
    try:
        sketch.solve()
    except Exception:
        pass
    now = read_frame(sketch, ids)
    if now is None:
        return False
    (cx, cy), a, w, h = now
    return (
        abs(cx - corner[0]) < 1e-5
        and abs(cy - corner[1]) < 1e-5
        and abs(core.normal_angle(a - angle)) < 1e-4
        and abs(w - width) < 1e-5
        and abs(h - height) < 1e-5
    )


def move_frame(sketch, ids, dx, dy):
    """Move the frame lines by (dx, dy) with the sketch's solver (a drag of the text)."""
    indices = [geo_index(sketch, gid) for gid in ids or []]
    if len(indices) != 4 or any(i is None for i in indices):
        return False
    sketch.moveGeometries([(i, 0) for i in indices], App.Vector(dx, dy, 0), True)
    return True


def remove_frame(sketch, ids):
    indices = sorted(
        (i for i in (geo_index(sketch, gid) for gid in ids or []) if i is not None), reverse=True
    )
    if indices:
        sketch.delGeometries(indices)
        _solve(sketch)


# -- the text object --------------------------------------------------------------------------
def _add(obj, kind, name, doc, group="Text", hidden=False):
    if name in obj.PropertiesList:
        return False
    obj.addProperty(kind, name, group, doc)
    if hidden:
        obj.setEditorMode(name, 2)
    return True


def _set_enum(obj, prop, items, value):
    try:
        if list(obj.getEnumerationsOfProperty(prop) or []) != list(items):
            setattr(obj, prop, list(items))
    except Exception:
        setattr(obj, prop, list(items))
    setattr(obj, prop, value)


class TextFeature:
    """The proxy of a SketchText object. Saved documents store "sciforge.text.TextFeature":
    keep the name and the property names stable."""

    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)

    @staticmethod
    def ensure_properties(obj):
        _add(obj, "App::PropertyLink", "Sketch", "The sketch the text belongs to", hidden=True)
        _add(obj, "App::PropertyString", "Text", "The text (Fusion: 'text' + parameter)")
        if _add(obj, "App::PropertyLength", "TextHeight", "Height of the letters' em box"):
            obj.TextHeight = DEFAULT_HEIGHT
        _add(obj, "App::PropertyString", "Font", "Font family")
        for name, tip in (
            ("Bold", "Bold letters"),
            ("Italic", "Slanted letters"),
            ("Underline", "A line under the text"),
            ("FlipHorizontal", "Mirror left to right"),
            ("FlipVertical", "Mirror top to bottom"),
        ):
            _add(obj, "App::PropertyBool", name, tip)
        if _add(obj, "App::PropertyEnumeration", "TextType", "Text in a frame, or on a path"):
            obj.TextType = ["Text", "Text On Path"]
        if _add(obj, "App::PropertyEnumeration", "HorizontalAlignment", "Left, centre or right"):
            obj.HorizontalAlignment = ["Left", "Center", "Right"]
        if _add(obj, "App::PropertyEnumeration", "VerticalAlignment", "Top, middle or bottom"):
            obj.VerticalAlignment = ["Top", "Middle", "Bottom"]
        _add(obj, "App::PropertyFloat", "CharacterSpacing", "Percent of the font's spacing")
        _add(obj, "App::PropertyAngle", "Angle", "The frame's angle")
        _add(obj, "App::PropertyIntegerList", "FrameIds", "The frame lines", hidden=True)
        _add(obj, "App::PropertyVector", "Corner", "The frame's corner", hidden=True)
        _add(obj, "App::PropertyLength", "FrameWidth", "The frame's width", hidden=True)
        _add(obj, "App::PropertyLength", "FrameHeight", "The frame's height", hidden=True)
        _add(obj, "App::PropertyInteger", "PathId", "The path curve", hidden=True)
        if _add(obj, "App::PropertyBool", "AbovePath", "Letters above the path (else below)"):
            obj.AbovePath = True
        _add(obj, "App::PropertyBool", "FitToPath", "Spread the letters over the whole path")
        if _add(obj, "App::PropertyString", "ResolvedText", "The text as drawn"):
            obj.setEditorMode("ResolvedText", 1)
        _add(obj, "App::PropertyString", "FontUsed", "The font family drawn", hidden=True)
        _add(obj, "App::PropertyLink", "Parameters", "Parameters the text uses", hidden=True)
        if _add(obj, "App::PropertyString", ROLE_PROP, "What SciForge made this for", "SciForge"):
            obj.setEditorMode(ROLE_PROP, 2)
        setattr(obj, ROLE_PROP, KIND)
        if "SciForgeType" not in obj.PropertiesList:
            obj.addProperty("App::PropertyString", "SciForgeType", "Base", "", 4)
        obj.SciForgeType = KIND
        for name in (
            "Placement",
            "AttachmentSupport",
            "MapMode",
            "MapReversed",
            "MapPathParameter",
            "AttachmentOffset",
        ):
            try:
                if name in obj.PropertiesList:
                    obj.setEditorMode(name, 2)
            except Exception:
                pass

    def onDocumentRestored(self, obj):
        self.ensure_properties(obj)
        try:
            family = obj.Font
            if family and catalog().find_family(family) is None:
                key = (obj.Document.Name, obj.Name)
                if key not in _FONTS["told"]:
                    _FONTS["told"].add(key)
                    # A plain note, not a warning: nothing is wrong with the design.
                    msg = (
                        "%s uses the font '%s', which this computer does not have. It keeps "
                        "its saved letters until it is rebuilt, then it uses '%s'. Double-click "
                        "the text to pick another font." % (obj.Label, family, default_family())
                    )
                    log(msg)
                    _FONTS["missing"].append((obj.Document.Name, msg))
                    for call in list(ON_FONT_MISSING):
                        try:
                            call(obj.Document.Name)
                        except Exception:
                            pass
        except Exception:
            pass

    def execute(self, obj):
        sketch = obj.Sketch
        if sketch is None:
            raise TextError("%s has lost its sketch." % obj.Label)
        spec = spec_of(obj)
        lookup = parameter_lookup(obj.Document)
        text = core.evaluate(spec["text"], lookup)
        result = plan(spec, sketch, text=text)
        shape = result.shape()
        obj.Shape = shape
        obj.Placement = sketch.Placement
        if obj.ResolvedText != text:
            obj.ResolvedText = text
        if obj.FontUsed != result.font:
            obj.FontUsed = result.font
        for note in result.notes:
            key = (obj.Document.Name, obj.Name, note)
            if key not in _FONTS["told"]:
                _FONTS["told"].add(key)
                log("%s: %s" % (obj.Label, note))

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads


def is_text(obj):
    try:
        return obj is not None and getattr(obj, "SciForgeType", "") == KIND and obj.TypeId == TYPE
    except Exception:
        return False


def texts_of(sketch):
    """The texts that belong to a sketch, oldest first."""
    if sketch is None:
        return []
    found = []
    try:
        for obj in sketch.InList:
            if is_text(obj) and obj.Sketch is sketch:
                found.append(obj)
    except Exception:
        return []
    return sorted(found, key=lambda o: o.ID if hasattr(o, "ID") else 0)


def sketch_of(obj):
    return obj.Sketch if is_text(obj) else None


def spec_of(obj):
    """The spec (default_spec's keys) of a text object."""
    spec = default_spec()
    spec.update(
        {
            "type": "path" if obj.TextType == "Text On Path" else "text",
            "text": obj.Text,
            "height": float(obj.TextHeight.Value),
            "font": obj.Font,
            "bold": bool(obj.Bold),
            "italic": bool(obj.Italic),
            "underline": bool(obj.Underline),
            "h_align": str(obj.HorizontalAlignment).lower(),
            "v_align": str(obj.VerticalAlignment).lower(),
            "spacing": float(obj.CharacterSpacing),
            "flip_h": bool(obj.FlipHorizontal),
            "flip_v": bool(obj.FlipVertical),
            "angle": float(obj.Angle.Value),
            "corner": (float(obj.Corner.x), float(obj.Corner.y)),
            "width": float(obj.FrameWidth.Value),
            "frame_height": float(obj.FrameHeight.Value),
            "frame_ids": list(obj.FrameIds),
            "path_id": int(obj.PathId),
            "above": bool(obj.AbovePath),
            "fit": bool(obj.FitToPath),
        }
    )
    return spec


def _set(obj, prop, value):
    """Set only real changes (a same-value write is a change FreeCAD records)."""
    current = getattr(obj, prop)
    try:
        current = current.Value if hasattr(current, "Value") else current
    except Exception:
        pass
    if isinstance(value, float) and isinstance(current, (int, float)):
        if abs(current - value) < 1e-12:
            return
    elif current == value:
        return
    setattr(obj, prop, value)


def apply_spec(obj, spec):
    """Write a spec onto a text object (the dialog's OK). The frame lines are not moved
    here (set_frame does that)."""
    _set(obj, "TextType", TYPE_NAMES[spec["type"]])
    _set(obj, "Text", spec["text"])
    if not has_expression(obj, "TextHeight"):
        _set(obj, "TextHeight", float(spec["height"]))
    _set(obj, "Font", spec["font"])
    _set(obj, "Bold", bool(spec["bold"]))
    _set(obj, "Italic", bool(spec["italic"]))
    _set(obj, "Underline", bool(spec["underline"]))
    _set(obj, "HorizontalAlignment", H_NAMES[spec["h_align"]])
    _set(obj, "VerticalAlignment", V_NAMES[spec["v_align"]])
    _set(obj, "CharacterSpacing", float(spec["spacing"]))
    _set(obj, "FlipHorizontal", bool(spec["flip_h"]))
    _set(obj, "FlipVertical", bool(spec["flip_v"]))
    _set(obj, "Angle", float(spec["angle"]))
    corner = App.Vector(float(spec["corner"][0]), float(spec["corner"][1]), 0)
    if (obj.Corner - corner).Length > 1e-12:
        obj.Corner = corner
    _set(obj, "FrameWidth", float(spec["width"]))
    _set(obj, "FrameHeight", float(spec["frame_height"]))
    if list(obj.FrameIds) != list(spec["frame_ids"]):
        obj.FrameIds = list(spec["frame_ids"])
    _set(obj, "PathId", int(spec["path_id"] or 0))
    _set(obj, "AbovePath", bool(spec["above"]))
    _set(obj, "FitToPath", bool(spec["fit"]))
    _link_parameters(obj, spec["text"])


def has_expression(obj, prop):
    """True if a property follows a formula (FreeCAD expression)."""
    try:
        return any(path == prop for path, _expr in obj.ExpressionEngine)
    except Exception:
        return False


def formula_of(obj, prop):
    """The formula a property follows, as the user types it ("h * 2"), or ""."""
    try:
        from . import parameters_core

        for path, expr in obj.ExpressionEngine:
            if path == prop:
                return parameters_core.from_freecad(expr)
    except Exception:
        pass
    return ""


def set_height_formula(obj, formula):
    """TextHeight follows a formula of parameters ("h * 2"), or none ("" = a number)."""
    from . import parameters, parameters_core

    if formula:
        expr = parameters_core.to_freecad(formula, parameters.user_names(obj.Document))
        if dict(obj.ExpressionEngine).get("TextHeight") != expr:
            obj.setExpression("TextHeight", expr)
    elif has_expression(obj, "TextHeight"):
        obj.setExpression("TextHeight", None)


def _link_parameters(obj, expr):
    """A text that names parameters follows them: it links the parameters' container so
    FreeCAD recomputes it when they change."""
    try:
        from . import parameters

        uses = core.is_expression(expr) and any(kind == "name" for kind, _ in core._tokens(expr))
        holder = parameters.container(obj.Document) if uses else None
    except Exception:
        holder = None
    if obj.Parameters is not holder:
        obj.Parameters = holder


def parameter_lookup(doc):
    """lookup(name) for text expressions: the design's user parameters by name."""

    def lookup(name):
        from . import parameters

        holder = parameters.container(doc)
        if holder is None:
            raise KeyError(name)
        short = name.split(".", 1)[1] if name.startswith("Parameters.") else name
        if short not in holder.PropertiesList:
            raise KeyError(name)
        return getattr(holder, short)

    return lookup


def _attach_view_provider(obj):
    try:
        if not App.GuiUp or obj.ViewObject is None:
            return
        from .text_ui import ViewProviderText

        ViewProviderText(obj.ViewObject)
    except Exception as exc:
        warn("text display: %s" % exc)


def make(sketch, spec, name="Text"):
    """A new SketchText in the sketch's body, right after the sketch (Type Text: with its
    frame lines). Not recomputed. Raises TextError."""
    check_spec(spec)
    doc = sketch.Document
    spec = dict(spec)
    if spec["type"] == "text" and not spec.get("frame_ids"):
        spec["frame_ids"] = add_frame(
            sketch, spec["corner"], spec["angle"], spec["width"], spec["frame_height"]
        )
    obj = doc.addObject(TYPE, name)
    TextFeature(obj)
    obj.Sketch = sketch
    parent = sketch.getParentGeoFeatureGroup()
    try:
        if parent is not None and parent.TypeId == "PartDesign::Body":
            parent.insertObject(obj, sketch, True)
        elif parent is not None:
            parent.addObject(obj)
    except Exception as exc:
        warn("text: could not place %s next to %s: %s" % (obj.Name, sketch.Label, exc))
    apply_spec(obj, spec)
    obj.Label = next_label(doc)
    _attach_view_provider(obj)
    return obj


def next_label(doc):
    """Text1, Text2... (Fusion numbers its sketch texts per design)."""
    used = {o.Label for o in doc.Objects if is_text(o)}
    n = 1
    while "Text%d" % n in used:
        n += 1
    return "Text%d" % n


def remove(obj):
    """Delete a text and its frame lines."""
    sketch = obj.Sketch
    doc = obj.Document
    if sketch is not None and obj.TextType == "Text":
        try:
            remove_frame(sketch, list(obj.FrameIds))
        except Exception as exc:
            warn("text: frame lines: %s" % exc)
    _forget_hidden(obj)
    doc.removeObject(obj.Name)


def _forget_hidden(obj):
    """FreeCAD's sketch edit hides what depends on the sketch (its texts) and shows it
    again when the sketch closes (Show.TempoVis); a text deleted in between made that
    printed as errors ("failed to restore detail"). Its saved visibility is dropped
    (texts follow their sketch's visibility anyway, text_ui.sync_all)."""
    if not App.GuiUp:
        return
    try:
        from Show import TVStack

        doc = obj.Document
        stack = TVStack.mainStack(doc, create_if_missing=False)
        if stack is None:
            return
        prefix = obj.Name + "."
        for tv in stack:
            if tv is None:
                continue
            for store in (getattr(tv, "data", {}), getattr(tv, "data_requested", {})):
                for key in list(store):
                    if (
                        isinstance(key, tuple)
                        and len(key) == 3
                        and key[1] == doc.Name
                        and isinstance(key[2], str)
                        and key[2].startswith(prefix)
                    ):
                        store.pop(key, None)
    except Exception as exc:
        log("text: sketch visibility: %s" % exc)


def users(obj):
    """Objects that use the text (as a profile): not its body or component, which only
    hold it."""
    found = []
    try:
        for other in obj.InList:
            if other is obj or is_text(other):
                continue
            if other.TypeId in ("PartDesign::Body", "App::Part", "App::DocumentObjectGroup"):
                continue
            found.append(other)
    except Exception:
        pass
    return found


# -- Explode Text ---------------------------------------------------------------------------------
def outline_geometry(shape):
    """Sketch curves (lines and B-splines) of a text shape's edges, grouped per wire in
    order: [[geometry, ...], ...]."""
    groups = []
    for face in shape.Faces or []:
        for wire in face.Wires:
            groups.append(_wire_geometry(wire))
    if not shape.Faces:
        for wire in shape.Wires:
            groups.append(_wire_geometry(wire))
    return [g for g in groups if g]


def _wire_geometry(wire):
    import Part

    out = []
    for edge in wire.OrderedEdges if hasattr(wire, "OrderedEdges") else wire.Edges:
        curve = edge.Curve
        a, b = edge.FirstParameter, edge.LastParameter
        p0, p1 = edge.valueAt(a), edge.valueAt(b)
        name = type(curve).__name__
        try:
            if name in ("Line", "LineSegment"):
                if (p1 - p0).Length > 1e-9:
                    out.append(Part.LineSegment(p0, p1))
                continue
            if name == "BSplineCurve" and curve.Degree == 1:
                poles = curve.getPoles()
                if len(poles) == 2 or all(_collinear(poles[0], poles[-1], p) for p in poles[1:-1]):
                    if (p1 - p0).Length > 1e-9:
                        out.append(Part.LineSegment(p0, p1))
                    continue
            if name == "Circle":
                if edge.isClosed():
                    out.append(curve.copy())
                else:
                    out.append(Part.ArcOfCircle(curve.copy(), a, b))
                continue
            spline = edge.toNurbs().Edges[0].Curve
            spline = spline.copy()
            try:
                if abs(spline.FirstParameter - a) > 1e-12 or abs(spline.LastParameter - b) > 1e-12:
                    spline.segment(a, b)
            except Exception:
                pass
            out.append(spline)
        except Exception as exc:
            warn("explode: an edge was left out: %s" % exc)
    return out


def _collinear(a, b, p, tol=1e-7):
    ab = b - a
    if ab.Length < 1e-12:
        return True
    return ab.cross(p - a).Length / ab.Length < tol


def explode(obj):
    """Fusion's Explode Text: the letters become ordinary sketch curves (joined end to end
    by coincident constraints); the text, its frame and its parameters go. Features that
    extruded or embossed the text are pointed at the sketch areas of the letters instead.
    Returns the number of curves added. Raises TextError."""
    import Sketcher

    sketch = obj.Sketch
    if sketch is None:
        raise TextError("%s has lost its sketch." % obj.Label)
    shape = obj.Shape
    if shape.isNull() or not (shape.Faces or shape.Edges):
        obj.recompute()
        shape = obj.Shape
    if shape.isNull() or not (shape.Faces or shape.Edges):
        raise TextError("%s has nothing to explode." % obj.Label)
    local = shape.copy()
    local.Placement = App.Placement()  # the shape is in sketch coordinates
    ink = [f.copy() for f in local.Faces]
    groups = outline_geometry(local)
    added = 0
    constraints = []
    for group in groups:
        indices = list(sketch.addGeometry(group, False))
        if not indices:
            continue
        added += len(indices)
        count = len(indices)
        for k in range(count):
            i, j = indices[k], indices[(k + 1) % count]
            if count == 1:
                break
            pair = _joined(sketch, i, j)
            if pair is not None:
                constraints.append(Sketcher.Constraint("Coincident", i, pair[0], j, pair[1]))
    if constraints:
        sketch.addConstraint(constraints)
    _solve(sketch)
    users_before = users(obj)
    if obj.TextType == "Text":
        remove_frame(sketch, list(obj.FrameIds))
    _repoint(obj, sketch, ink, users_before)
    _forget_hidden(obj)
    obj.Document.removeObject(obj.Name)
    return added


def _joined(sketch, i, j):
    """(pos on i, pos on j) of the end of curve i meeting curve j's start (1 start, 2 end)."""
    gi, gj = sketch.Geometry[i], sketch.Geometry[j]
    best = None
    for pi, a in ((2, gi.EndPoint), (1, gi.StartPoint)):
        for pj, b in ((1, gj.StartPoint), (2, gj.EndPoint)):
            d = (a - b).Length
            if d < 1e-6 and (best is None or d < best[0]):
                best = (d, pi, pj)
    return None if best is None else (best[1], best[2])


def _repoint(obj, sketch, ink, users_list):
    """Features that used the text as a profile use the sketch areas of its letters."""
    if not users_list:
        return
    try:
        from . import extrude

        sketch.recompute()
        areas = extrude.regions(sketch)  # global coordinates
        placement = sketch.getGlobalPlacement()
        names = []
        for name, face in areas:
            point = extrude.interior_point(face)
            local = placement.inverse().multVec(point)
            local.z = 0.0
            if any(f.isInside(local, 1e-5, True) for f in ink):
                names.append(name)
    except Exception as exc:
        warn("explode: %s" % exc)
        names = []
    for other in users_list:
        for prop in ("Profile", "Profiles", "Support"):
            if prop not in other.PropertiesList:
                continue
            try:
                value = getattr(other, prop)
                kind = other.getTypeIdOfProperty(prop)
                if kind == "App::PropertyLinkSub":
                    if value and value[0] is obj:
                        setattr(other, prop, (sketch, names) if names else None)
                elif kind in ("App::PropertyLinkSubList", "App::PropertyXLinkSubList"):
                    entries = []
                    for linked, subs in value:
                        if linked is obj:
                            if names:
                                entries.append((sketch, tuple(names)))
                        else:
                            entries.append((linked, subs))
                    setattr(other, prop, entries)
            except Exception as exc:
                warn("explode: %s keeps the text as profile: %s" % (other.Label, exc))
