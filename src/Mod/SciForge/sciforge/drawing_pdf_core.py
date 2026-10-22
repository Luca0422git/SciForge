# SPDX-License-Identifier: LGPL-2.1-or-later
"""Better PDFs from drawings (Fusion's Export PDF; idea 7 of docs/sciforge/dev/
cadcraft-lessons.md): layers, searchable text, links and metadata added to the PDF
TechDraw prints. Pure Python (no FreeCAD, no Qt), unit tested in
SciForgeTests/unit/test_drawing_pdf_core.py; the FreeCAD side is drawing_pdf_export.py.

TechDraw draws a sheet with Qt's PDF writer, which keeps the drawing exactly as it looks
on screen (line weights, dash patterns, hatching, fonts) but knows nothing about what a
line is. Five things are added afterwards, without touching how anything looks:

* Layers (PDF optional content groups) a PDF viewer can switch on and off: Visible
  Edges, Hidden Edges, Centerlines and Center Marks, Hatching and Section Lines,
  Dimensions and Annotations, Border and Title Block. Which line is which is found from
  markers: before printing, drawing_pdf_export.py puts tiny, almost transparent squares
  of a code colour (red 165, the code in green and blue) into each view of the sheet,
  stacked between the kinds of things TechDraw draws there (its z-values: faces and
  hatching 10-41, edges 70, centre marks 80, section and break lines 90). They are
  printed where they sit in the drawing order, so everything between two markers is of
  the kind the first one announces. The markers are taken out of the PDF again; the
  edges of a view are told apart by their dash pattern (solid: visible; dashed at the
  view's hidden line width: hidden; any other dash: centre lines and marks), and
  everything before the first marker is the sheet's template (border and title block).
  Each painted path is wrapped in a marked-content sequence (/OC ... BDC ... EMC) that
  never crosses a q/Q, so the stream stays valid.
* Searchable, selectable text with an embedded font where TechDraw draws text as
  outlines (the title block and SciForge's SVG annotations and parts lists come from SVG,
  which Qt prints as paths): invisible text (render mode 3, as scanned documents carry
  their recognised text) placed over the drawn text, on the same layer, with osifont
  embedded as a subset (drawing_pdf_font.py). Text Qt already printed as text (dimensions,
  notes, balloons, captions) is found by reading the page and is not added twice there.
* Links: a URL (https://..., www....) or mailto: in any text becomes a clickable link.
* Metadata: title, author, subject and keywords from the drawing's title block,
  SciForge as the creating tool, in the document information and its XMP twin.
* Several sheets in one file (drawing_pdf.merge), each page keeping its own size.

A PDF/A file (FreeCAD's PDF preferences can ask Qt for one) keeps its conformance: PDF/A-1
forbids layers, so none are added to it.
"""

import datetime
import re
import zlib

from . import drawing_pdf_objects as po
from .drawing_pdf_objects import Name, Ref, String

MM = 72.0 / 25.4  # PDF points per millimetre

# (key, the name a PDF viewer shows), in the order of the viewer's layer list
LAYERS = (
    ("visible", "Visible Edges"),
    ("hidden", "Hidden Edges"),
    ("centre", "Centerlines and Center Marks"),
    ("hatching", "Hatching and Section Lines"),
    ("annotations", "Dimensions and Annotations"),
    ("border", "Border and Title Block"),
)
LAYER_NAMES = dict(LAYERS)

MARK_RED = 165
# markers stacked in a view (TechDraw's ZVALUE.h: faces 10, hatching 30-41, highlights 50,
# edges 60-70, vertices and centre marks 80, section / break / view centre lines 90,
# the view's caption and label at 0)
VIEW_BANDS = (
    ("begin", -1.0e9),  # caption, label: annotations
    ("faces", 5.0),  # faces, hatching, detail highlights: hatching and section lines
    ("edges", 55.0),  # edges: by their dash pattern
    ("marks", 75.0),  # centre marks: centre lines and marks
    ("lines", 85.0),  # section, break lines, matting: hatching and section lines
    ("end", 1.0e9),
)
OTHER_BANDS = (("begin", -1.0e9), ("end", 1.0e9))
BAND_LAYER = {"begin": "annotations", "faces": "hatching", "marks": "centre", "lines": "hatching"}

PATH_OPS = {b"m", b"l", b"c", b"v", b"y", b"h", b"re"}
CLIP_OPS = {b"W", b"W*"}
PAINT_OPS = {b"S", b"s", b"f", b"F", b"f*", b"B", b"B*", b"b", b"b*"}
FILL_COLOUR_OPS = {b"sc", b"scn", b"rg", b"g", b"k"}

URL = re.compile(r"(?:https?://|www\.|mailto:)[^\s<>\"'()\[\]{}]+", re.I)


class LayerError(ValueError):
    """A page whose drawing order cannot be given layers (it is left as it was)."""


# ------------------------------------------------------------------ markers
def marker_plan(items):
    """The markers for a sheet: `items` is [(key, kind)] (kind "view" for a view with
    edges, anything else for dimensions, notes, symbols...). Returns ([(key, band, z,
    code, (r, g, b))], {code: (key, kind, band)})."""
    plan, codes = [], {}
    code = 1
    for key, kind in items:
        for band, z in VIEW_BANDS if kind == "view" else OTHER_BANDS:
            if code > 0xFFFF:
                return plan, codes
            plan.append((key, band, z, code, (MARK_RED, code // 256, code % 256)))
            codes[code] = (key, kind, band)
            code += 1
    return plan, codes


def _marker_code(fill):
    """The code of a marker colour (r, g, b in 0..1), or None."""
    if not fill or len(fill) != 3:
        return None
    try:
        r, g, b = (float(v) * 255.0 for v in fill)
    except (TypeError, ValueError):
        return None
    if abs(r - MARK_RED) > 0.5:
        return None
    if abs(g - round(g)) > 0.05 or abs(b - round(b)) > 0.05:
        return None
    return int(round(g)) * 256 + int(round(b))


def edge_layer(dash, width, hidden_width):
    """Which layer an edge belongs to, from its dash pattern and line width."""
    lengths = [abs(float(v)) for v in (dash or []) if isinstance(v, (int, float))]
    if not lengths or not any(lengths):
        return "visible"
    if len(lengths) >= 4:
        return "centre"
    if hidden_width and isinstance(width, (int, float)):
        if abs(float(width) - hidden_width) > 0.02 * hidden_width + 1e-6:
            return "centre"
    return "hidden"


def _fill_of(op, current):
    args = op.args
    if op.op in (b"rg",) and len(args) == 3:
        return tuple(args)
    if op.op == b"g" and len(args) == 1:
        return (args[0], args[0], args[0])
    if op.op in (b"sc", b"scn"):
        if args and isinstance(args[-1], Name):
            return None  # a pattern
        if len(args) == 3:
            return tuple(args)
        if len(args) == 1:
            return (args[0], args[0], args[0])
        return None
    if op.op == b"k":
        return None
    return current


def layer_content(content, codes, hidden_widths=None):
    """The page's content with every painted path put on its layer, the markers taken
    out (and stray closepaths Qt writes, which viewers complain about). Returns
    (content, the layer keys used, the marker codes found)."""
    hidden_widths = hidden_widths or {}
    ops = po.operations(content)
    if any(op.op in (b"BMC", b"BDC", b"EMC") for op in ops):
        raise LayerError("the page already has marked content")
    n = len(ops)
    cat = [None] * n
    drop = [False] * n
    found = []
    stack = []  # (key, kind, band) of the items being drawn
    seen = False
    dash, fill, width = [], None, None
    saved = []
    path_start = None
    has_point = False
    text_start = None

    def classify(painting):
        if not seen:
            return "border"
        if not stack:
            return ""
        key, kind, band = stack[-1]
        if kind != "view":
            return "annotations"
        if band == "edges":
            return edge_layer(dash, width, hidden_widths.get(key)) if painting else "visible"
        return BAND_LAYER.get(band, "")

    for i, op in enumerate(ops):
        o = op.op
        if text_start is not None:
            if o in FILL_COLOUR_OPS:
                fill = _fill_of(op, fill)
            if o == b"ET":
                c = classify(False)
                for j in range(text_start, i + 1):
                    cat[j] = c
                text_start = None
            continue
        if o == b"BT":
            text_start = i
            continue
        if o in PATH_OPS:
            if o == b"h" and not has_point:
                drop[i] = True
                continue
            if path_start is None:
                path_start = i
            if o in (b"m", b"re"):
                has_point = True
            continue
        if o in CLIP_OPS:
            continue
        if o in PAINT_OPS or o == b"n":
            start = path_start if path_start is not None else i
            path_start, has_point = None, False
            if o == b"n":
                continue
            shape = [ops[j].op for j in range(start, i) if ops[j].op not in CLIP_OPS]
            code = _marker_code(fill) if o in (b"f", b"f*") and shape == [b"re"] else None
            if code is not None:
                for j in range(start, i + 1):
                    drop[j] = True
                found.append(code)
                info = codes.get(code)
                if info is None:
                    continue
                seen = True
                key, kind, band = info
                if band == "begin":
                    stack.append((key, kind, "begin"))
                elif band == "end":
                    for depth in range(len(stack) - 1, -1, -1):
                        if stack[depth][0] == key:
                            del stack[depth:]
                            break
                else:
                    for depth in range(len(stack) - 1, -1, -1):
                        if stack[depth][0] == key:
                            stack[depth] = (key, kind, band)
                            break
                continue
            c = classify(True)
            for j in range(start, i + 1):
                cat[j] = c
            continue
        if o in (b"Do", b"sh", b"BI"):
            cat[i] = classify(False)
            continue
        if o in (b"SC", b"SCN", b"sc", b"scn") and not op.args:
            drop[i] = True  # a colour without its values (Qt): viewers complain, then skip it
            continue
        if o == b"q":
            saved.append((dash, fill, width))
        elif o == b"Q":
            if saved:
                dash, fill, width = saved.pop()
        elif o == b"d" and op.args:
            dash = op.args[0] if isinstance(op.args[0], list) else []
        elif o == b"w" and op.args:
            width = op.args[0]
        elif o in FILL_COLOUR_OPS:
            fill = _fill_of(op, fill)
    if text_start is not None:
        raise LayerError("a text object has no end")

    out = []
    used = set()
    open_cat = None
    for i, op in enumerate(ops):
        if drop[i]:
            continue
        c = cat[i]
        if c:
            if c != open_cat:
                if open_cat:
                    out.append(b"EMC")
                out.append(b"/OC /SF%s BDC" % c.encode("ascii"))
                open_cat = c
                used.add(c)
        elif open_cat and (c == "" or op.op in (b"q", b"Q", b"BT")):
            out.append(b"EMC")
            open_cat = None
        out.append(content[op.start : op.stop])
    if open_cat:
        out.append(b"EMC")
    return b"\n".join(out) + b"\n", used, found


# ------------------------------------------------------------------ reading the page's text
def _mul(a, b):
    """Matrix product a x b of PDF matrices [a b c d e f]."""
    return [
        a[0] * b[0] + a[1] * b[2],
        a[0] * b[1] + a[1] * b[3],
        a[2] * b[0] + a[3] * b[2],
        a[2] * b[1] + a[3] * b[3],
        a[4] * b[0] + a[5] * b[2] + b[4],
        a[4] * b[1] + a[5] * b[3] + b[5],
    ]


def _apply(m, x, y):
    return m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]


def _parse_cmap(data):
    """{code: text} and the code length (bytes) from a ToUnicode CMap."""
    out = {}
    size = 2
    space = re.search(rb"begincodespacerange\s*<([0-9A-Fa-f]+)>", data)
    if space:
        size = max(1, len(space.group(1)) // 2)

    def text_of(hexdigits):
        raw = bytes.fromhex(hexdigits.decode("ascii"))
        try:
            return raw.decode("utf-16-be")
        except UnicodeDecodeError:
            return ""

    for block in re.finditer(rb"beginbfchar(.*?)endbfchar", data, re.S):
        for src, dst in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]*)>", block.group(1)):
            out[int(src, 16)] = text_of(dst)
    for block in re.finditer(rb"beginbfrange(.*?)endbfrange", data, re.S):
        body = block.group(1)
        for m in re.finditer(
            rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*(<([0-9A-Fa-f]+)>|\[([^\]]*)\])", body
        ):
            lo, hi = int(m.group(1), 16), int(m.group(2), 16)
            if hi - lo > 0xFFFF:
                continue
            if m.group(4) is not None:
                base = bytes.fromhex(m.group(4).decode("ascii"))
                for k, code in enumerate(range(lo, hi + 1)):
                    last = int.from_bytes(base[-2:], "big") + k if len(base) >= 2 else k
                    raw = base[:-2] + (last & 0xFFFF).to_bytes(2, "big")
                    try:
                        out[code] = raw.decode("utf-16-be")
                    except UnicodeDecodeError:
                        pass
            else:
                for k, dst in enumerate(re.findall(rb"<([0-9A-Fa-f]*)>", m.group(5))):
                    out[lo + k] = text_of(dst)
    return out, size


class _FontInfo:
    def __init__(self, doc, font):
        font = doc.get(font) or {}
        self.two_byte = font.get(b"Subtype") == b"Type0"
        self.map = {}
        self.widths = {}
        self.default_width = 1000.0 if self.two_byte else 500.0
        tu = font.get(b"ToUnicode")
        if isinstance(tu, Ref):
            data = doc.stream_data(tu.num)
            if data:
                self.map, size = _parse_cmap(data)
                self.two_byte = self.two_byte or size == 2
        if self.two_byte:
            kids = doc.get(font.get(b"DescendantFonts")) or []
            cid = doc.get(kids[0]) if kids else {}
            cid = cid or {}
            if isinstance(cid.get(b"DW"), (int, float)):
                self.default_width = float(cid[b"DW"])
            w = doc.get(cid.get(b"W")) or []
            i = 0
            while i < len(w):
                first = w[i]
                nxt = doc.get(w[i + 1]) if i + 1 < len(w) else None
                if isinstance(nxt, list):
                    for k, value in enumerate(nxt):
                        self.widths[int(first) + k] = float(doc.get(value) or 0)
                    i += 2
                elif i + 2 < len(w):
                    for code in range(int(first), int(nxt) + 1):
                        self.widths[code] = float(doc.get(w[i + 2]) or 0)
                    i += 3
                else:
                    break
        else:
            first = font.get(b"FirstChar")
            widths = doc.get(font.get(b"Widths")) or []
            if isinstance(first, int):
                for k, value in enumerate(widths):
                    self.widths[first + k] = float(doc.get(value) or 0)

    def codes(self, raw):
        if self.two_byte:
            return [int.from_bytes(raw[i : i + 2], "big") for i in range(0, len(raw) - 1, 2)]
        return list(raw)

    def char(self, code):
        if code in self.map:
            return self.map[code]
        if self.two_byte:
            return ""
        return bytes([code]).decode("latin-1")


def text_runs(doc, page_num, content=None):
    """The text Qt printed as text on a page: [{"text": str, "boxes": [box or None per
    character]}], one entry per line, boxes (x0, y0, x1, y1) in PDF points."""
    page = doc.objects[page_num]
    resources = doc.get(page.get(b"Resources")) or {}
    fonts = doc.get(resources.get(b"Font")) or {}
    infos = {}
    if content is None:
        content = page_content(doc, page_num)
    runs = []
    ctm = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
    saved = []
    tm = tlm = None
    font = None
    size = 1.0
    tc = tw = 0.0
    th = 1.0
    tl = rise = 0.0
    current = None

    def new_run():
        nonlocal current
        current = {"text": "", "boxes": [], "last": None}
        runs.append(current)

    def show(raw):
        nonlocal tm
        if font is None:
            return
        for code in font.codes(raw):
            ch = font.char(code)
            w0 = font.widths.get(code, font.default_width) / 1000.0
            trm = _mul([size * th, 0, 0, size, 0, rise], _mul(tm, ctm))
            x0, y0 = _apply(trm, 0, -0.2)
            x1, y1 = _apply(trm, w0, 0.8)
            box = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
            em = abs(trm[3]) or abs(trm[1]) or 1.0
            last = current["last"]
            if last is not None:
                same_line = abs(box[1] - last[1]) < 0.5 * em and box[0] > last[0] - 0.5 * em
                if not same_line:
                    new_run()
                elif box[0] - last[2] > 0.3 * em and ch != " " and current["text"][-1:] != " ":
                    current["text"] += " "
                    current["boxes"].append(None)
            if ch:
                current["text"] += ch
                current["boxes"].extend([box] + [None] * (len(ch) - 1))
                current["last"] = box
            tx = (w0 * size + tc + (tw if (not font.two_byte and code == 32) else 0.0)) * th
            tm = _mul([1, 0, 0, 1, tx, 0], tm)

    for op in po.operations(content):
        o, a = op.op, op.args
        try:
            if o == b"q":
                saved.append(list(ctm))
            elif o == b"Q":
                if saved:
                    ctm = saved.pop()
            elif o == b"cm" and len(a) == 6:
                ctm = _mul([float(v) for v in a], ctm)
            elif o == b"BT":
                tm = tlm = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
                new_run()
            elif o == b"ET":
                tm = None
            elif tm is None:
                continue
            elif o == b"Tf" and len(a) == 2:
                key = bytes(a[0])
                if key not in infos:
                    infos[key] = _FontInfo(doc, fonts.get(key))
                font, size = infos[key], float(a[1])
            elif o == b"Tm" and len(a) == 6:
                tm = tlm = [float(v) for v in a]
            elif o in (b"Td", b"TD") and len(a) == 2:
                if o == b"TD":
                    tl = -float(a[1])
                tm = tlm = _mul([1, 0, 0, 1, float(a[0]), float(a[1])], tlm)
            elif o == b"T*":
                tm = tlm = _mul([1, 0, 0, 1, 0, -tl], tlm)
            elif o == b"Tc" and a:
                tc = float(a[0])
            elif o == b"Tw" and a:
                tw = float(a[0])
            elif o == b"Tz" and a:
                th = float(a[0]) / 100.0
            elif o == b"TL" and a:
                tl = float(a[0])
            elif o == b"Ts" and a:
                rise = float(a[0])
            elif o == b"Tj" and a and isinstance(a[0], bytes):
                show(bytes(a[0]))
            elif o in (b"'", b'"') and a and isinstance(a[-1], bytes):
                if o == b'"' and len(a) == 3:
                    tw, tc = float(a[0]), float(a[1])
                tm = tlm = _mul([1, 0, 0, 1, 0, -tl], tlm)
                show(bytes(a[-1]))
            elif o == b"TJ" and a and isinstance(a[0], list):
                for part in a[0]:
                    if isinstance(part, bytes):
                        show(bytes(part))
                    elif isinstance(part, (int, float)):
                        tm = _mul([1, 0, 0, 1, -float(part) / 1000.0 * size * th, 0], tm)
        except (TypeError, ValueError, IndexError):
            continue
    out = []
    for run in runs:
        text = run["text"].rstrip()
        if text.strip():
            out.append({"text": text, "boxes": run["boxes"][: len(text)]})
    return out


def page_content(doc, page_num):
    """The decoded content of a page (its streams joined); LayerError when a stream
    uses a filter this module does not read."""
    page = doc.objects[page_num]
    contents = page.get(b"Contents")
    refs = contents if isinstance(contents, list) else [contents]
    parts = []
    for ref in refs:
        if not isinstance(ref, Ref):
            continue
        data = doc.stream_data(ref.num)
        if data is None:
            raise LayerError("the page's content uses a filter that cannot be read")
        parts.append(data)
    return b"\n".join(parts)


def _norm(text):
    return "".join(text.split()).casefold()


def _printed_here(printed, key, item, sheet_mm, media):
    """The entry of `printed` ([(text, box)]) with the same text as `item` near where the
    item goes (within three times its size), or None."""
    try:
        x, y = sheet_point(float(item["x"]), float(item["y"]), sheet_mm, media)
        reach = 3.0 * float(item.get("size") or 3.5) * MM + 0.5 * float(item.get("width") or 0) * MM
    except (KeyError, TypeError, ValueError):
        return None
    for entry in printed:
        text, box = entry
        if text != key or box is None:
            continue
        if box[0] - reach <= x <= box[2] + reach and box[1] - reach <= y <= box[3] + reach:
            return entry
    return None


# ------------------------------------------------------------------ links
def find_links(text):
    """[(start, end, uri)] of the links in a text."""
    found = []
    for m in URL.finditer(text):
        raw = m.group().rstrip(".,;:!?")
        if len(raw) < 8 and not raw.lower().startswith("mailto:"):
            continue
        uri = raw
        if raw.lower().startswith("www."):
            uri = "http://" + raw
        found.append((m.start(), m.start() + len(raw), uri))
    return found


def _union(boxes):
    boxes = [b for b in boxes if b]
    if not boxes:
        return None
    return (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )


# ------------------------------------------------------------------ added text
def sheet_point(x_mm, y_mm, sheet_mm, media):
    """Page millimetres (y up from the bottom left, as SciForge places things) -> PDF
    points. Qt anchors the drawing at the page's top: its height is rounded up to whole
    points (842 for A4's 841.89)."""
    return x_mm * MM, media[3] - (sheet_mm[1] - y_mm) * MM


def overlay(texts, font, sheet_mm, media):
    """Content bytes for invisible text over drawn text, and the links in it: `texts` is
    [{"text", "x", "y", "size", "anchor", "width", "angle", "layer"}] in page mm (x, y the
    anchor point on the baseline, size the font size, width the drawn width when known).
    Returns (content, [(rect, uri, layer)], layers used)."""
    import math

    out = [b"q"]
    links = []
    used = set()
    open_layer = None
    for item in texts:
        text = str(item.get("text") or "").replace("\n", " ").strip()
        if not text:
            continue
        try:
            size = float(item.get("size") or 3.5) * MM
            x, y = sheet_point(float(item["x"]), float(item["y"]), sheet_mm, media)
        except (KeyError, TypeError, ValueError):
            continue
        natural = font.width(text) / 1000.0 * size
        drawn = item.get("width")
        target = float(drawn) * MM if isinstance(drawn, (int, float)) and drawn > 0 else natural
        scale = 100.0
        if natural > 0 and target > 0:
            scale = max(20.0, min(500.0, 100.0 * target / natural))
        span = natural * scale / 100.0
        shift = {"middle": span / 2.0, "end": span}.get(item.get("anchor"), 0.0)
        angle = math.radians(float(item.get("angle") or 0.0))
        ca, sa = math.cos(angle), math.sin(angle)
        ox, oy = x - shift * ca, y - shift * sa
        layer = item.get("layer") or ""
        if layer != open_layer:
            if open_layer:
                out.append(b"EMC")
            if layer:
                out.append(b"/OC /SF%s BDC" % layer.encode("ascii"))
                used.add(layer)
            open_layer = layer or None
        out.append(b"BT")
        out.append(b"3 Tr")
        out.append(b"/SFText " + po.serialize(round(size, 4)) + b" Tf")
        if abs(scale - 100.0) > 0.01:
            out.append(po.serialize(round(scale, 3)) + b" Tz")
        matrix = [ca, sa, -sa, ca, ox, oy]
        out.append(b" ".join(po.serialize(round(v, 4)) for v in matrix) + b" Tm")
        out.append(po.serialize(font.encode(text)) + b" Tj")
        out.append(b"ET")
        for start, end, uri in find_links(text):
            k = scale / 100.0 * size / 1000.0
            a = font.width(text[:start]) * k
            b = font.width(text[:end]) * k
            corners = [
                (ox + u * ca - v * sa, oy + u * sa + v * ca)
                for u in (a, b)
                for v in (-0.2 * size, 0.8 * size)
            ]
            rect = (
                min(p[0] for p in corners),
                min(p[1] for p in corners),
                max(p[0] for p in corners),
                max(p[1] for p in corners),
            )
            links.append((rect, uri, layer))
    if open_layer:
        out.append(b"EMC")
    out.append(b"Q")
    return b"\n".join(out) + b"\n", links, used


# ------------------------------------------------------------------ metadata
def _xml(text):
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _iso_date(pdf_date):
    """'D:20261022043408Z' -> '2026-10-22T04:34:08Z' (None when it cannot be read)."""
    m = re.match(
        r"D:(\d{4})(\d{2})?(\d{2})?(\d{2})?(\d{2})?(\d{2})?(Z|[+-]\d{2}'?\d{2}'?)?", pdf_date or ""
    )
    if not m:
        return None
    parts = [m.group(i) or d for i, d in zip(range(1, 7), ("0000", "01", "01", "00", "00", "00"))]
    zone = m.group(7) or "Z"
    if zone != "Z":
        zone = zone.replace("'", "")
        zone = zone[:3] + ":" + zone[3:5]
    return "%s-%s-%sT%s:%s:%s%s" % tuple(parts + [zone])


def pdf_date(when=None):
    when = when or datetime.datetime.now(datetime.timezone.utc)
    return when.strftime("D:%Y%m%d%H%M%SZ")


def xmp(meta, created, modified, pdfa=None):
    """The XMP metadata packet for `meta` (title, author, subject, keywords, creator,
    producer)."""
    rows = ["<dc:format>application/pdf</dc:format>"]
    if meta.get("title"):
        rows.append(
            '<dc:title><rdf:Alt><rdf:li xml:lang="x-default">%s</rdf:li></rdf:Alt></dc:title>'
            % _xml(meta["title"])
        )
    if meta.get("author"):
        rows.append(
            "<dc:creator><rdf:Seq><rdf:li>%s</rdf:li></rdf:Seq></dc:creator>" % _xml(meta["author"])
        )
    if meta.get("subject"):
        rows.append(
            '<dc:description><rdf:Alt><rdf:li xml:lang="x-default">%s</rdf:li></rdf:Alt>'
            "</dc:description>" % _xml(meta["subject"])
        )
    if meta.get("keywords"):
        rows.append("<pdf:Keywords>%s</pdf:Keywords>" % _xml(meta["keywords"]))
    if meta.get("producer"):
        rows.append("<pdf:Producer>%s</pdf:Producer>" % _xml(meta["producer"]))
    if meta.get("creator"):
        rows.append("<xmp:CreatorTool>%s</xmp:CreatorTool>" % _xml(meta["creator"]))
    if created:
        rows.append("<xmp:CreateDate>%s</xmp:CreateDate>" % created)
    if modified:
        rows.append("<xmp:ModifyDate>%s</xmp:ModifyDate>" % modified)
        rows.append("<xmp:MetadataDate>%s</xmp:MetadataDate>" % modified)
    if pdfa:
        rows.append("<pdfaid:part>%s</pdfaid:part>" % _xml(pdfa[0]))
        if pdfa[1]:
            rows.append("<pdfaid:conformance>%s</pdfaid:conformance>" % _xml(pdfa[1]))
    text = (
        '<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>\n'
        '<x:xmpmeta xmlns:x="adobe:ns:meta/">\n'
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">\n'
        '<rdf:Description rdf:about="" xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:xmp="http://ns.adobe.com/xap/1.0/" xmlns:pdf="http://ns.adobe.com/pdf/1.3/" '
        'xmlns:pdfaid="http://www.aiim.org/pdfa/ns/id/">\n%s\n</rdf:Description>\n'
        "</rdf:RDF>\n</x:xmpmeta>\n" % "\n".join(rows)
    )
    return (text + " " * 200 + '\n<?xpacket end="w"?>').encode("utf-8")


def _pdfa_of(doc, root):
    if not isinstance(root.get(b"Metadata"), Ref):
        return None
    data = doc.stream_data(root[b"Metadata"].num) or b""
    part = re.search(rb"pdfaid:part(?:>|=\")\s*(\d)", data)
    if not part:
        return None
    conf = re.search(rb"pdfaid:conformance(?:>|=\")\s*([A-Za-z])", data)
    return part.group(1).decode(), (conf.group(1).decode() if conf else "")


# ------------------------------------------------------------------ the whole file
def enhance(data, sheets, meta, font=None):
    """The PDF `data` (one page per sheet, in order) with layers, searchable text, links
    and metadata. `sheets` is one dict (or None) per page:
      {"size": (width, height) in mm, "codes": {code: (key, kind, band)} or None,
       "hidden": {key: hidden line width in the PDF's units}, "texts": [...]}
    (texts as drawing_pdf_core.overlay wants them); `meta` has title, author, subject,
    keywords, creator, producer; `font` is a drawing_pdf_font font for the added text.
    Returns (bytes, report) where report says what was done per page."""
    doc = po.read(data)
    root = doc.get(doc.trailer.get(b"Root"))
    if not isinstance(root, dict):
        raise po.PdfError("This PDF has no catalogue.")
    pages = doc.pages()
    pdfa = _pdfa_of(doc, root)
    report = {"pages": [], "pdfa": bool(pdfa)}
    ocg_refs = {}  # layer key -> its OCG, made in LAYERS order once every page is read
    page_plans = []
    for index, num in enumerate(pages):
        info = sheets[index] if index < len(sheets) else None
        page = doc.objects[num]
        entry = {"layers": [], "markers": 0, "texts": 0, "links": 0, "note": ""}
        report["pages"].append(entry)
        media = [float(v) for v in (doc.get(page.get(b"MediaBox")) or [0, 0, 595, 842])]
        try:
            content = page_content(doc, num)
        except LayerError as exc:
            entry["note"] = str(exc)
            page_plans.append(None)
            continue
        new = content
        used = set()
        codes = (info or {}).get("codes")
        if codes is not None and not pdfa:
            try:
                new, used, found = layer_content(content, codes, (info or {}).get("hidden"))
                entry["markers"] = len(found)
                if codes and not found:
                    # no marker printed: the layers would all be wrong
                    new, used = content, set()
                    entry["note"] = "no markers were printed: no layers"
            except (LayerError, po.PdfError) as exc:
                new, used = content, set()
                entry["note"] = "no layers: %s" % exc
        links = []
        runs = []
        try:
            runs = text_runs(doc, num, content)
        except (po.PdfError, LayerError, KeyError, TypeError, ValueError) as exc:
            entry["note"] = (entry["note"] + "; " if entry["note"] else "") + "text: %s" % exc
        printed = [(_norm(r["text"]), _union(r["boxes"])) for r in runs]
        for run in runs:
            for start, end, uri in find_links(run["text"]):
                rect = _union(run["boxes"][start:end])
                if rect:
                    links.append((rect, uri, "annotations" if used else ""))
        added = []
        size = (info or {}).get("size")
        if font is not None and size:
            for item in (info or {}).get("texts") or []:
                key = _norm(str(item.get("text") or ""))
                if not key:
                    continue
                same = _printed_here(printed, key, item, size, media)
                if same is not None:
                    printed.remove(same)  # Qt printed it as text there: not twice
                    continue
                item = dict(item)
                if not used:
                    item["layer"] = ""
                added.append(item)
        if added:
            extra, extra_links, extra_used = overlay(added, font, size, media)
            # the page's own drawing leaves its transformation behind (Qt's first cm
            # is outside any q/Q): the added text starts from the page's own
            new = b"q\n" + new + b"Q\n" + extra
            links += extra_links
            used |= extra_used
            entry["texts"] = len(added)
        entry["links"] = len(links)
        entry["layers"] = [k for k, _n in LAYERS if k in used]
        for key in used:
            ocg_refs[key] = None
        page_plans.append((num, new, used, links, bool(added)))

    # the layers, one set for the whole file
    for key, name in LAYERS:
        if key in ocg_refs:
            ocg_refs[key] = doc.add({b"Type": Name(b"OCG"), b"Name": po.text_string(name)})
    font_ref = None
    if font is not None and any(p and p[4] for p in page_plans):
        font_ref = font.objects(doc)
    for plan in page_plans:
        if plan is None:
            continue
        num, content, used, links, has_text = plan
        page = dict(doc.objects[num])
        ref = doc.add({b"Filter": Name(b"FlateDecode")}, zlib.compress(content, 6))
        page[b"Contents"] = ref
        resources = doc.get(page.get(b"Resources"))
        resources = dict(resources) if isinstance(resources, dict) else {}
        if used:
            props = dict(doc.get(resources.get(b"Properties")) or {})
            for key in used:
                props[b"SF" + key.encode("ascii")] = ocg_refs[key]
            resources[b"Properties"] = props
        if has_text and font_ref is not None:
            fonts = dict(doc.get(resources.get(b"Font")) or {})
            fonts[b"SFText"] = font_ref
            resources[b"Font"] = fonts
        page[b"Resources"] = resources
        annots = list(doc.get(page.get(b"Annots")) or [])
        for rect, uri, layer in links:
            annot = {
                b"Type": Name(b"Annot"),
                b"Subtype": Name(b"Link"),
                b"Rect": [round(v, 3) for v in rect],
                b"Border": [0, 0, 0],
                b"F": 4,
                b"A": {
                    b"Type": Name(b"Action"),
                    b"S": Name(b"URI"),
                    b"URI": String(uri.encode("utf-8")),
                },
            }
            if layer and layer in ocg_refs:
                annot[b"OC"] = ocg_refs[layer]
            annots.append(doc.add(annot))
        if annots:
            page[b"Annots"] = annots
        else:
            page.pop(b"Annots", None)
        doc.objects[num] = page

    root = dict(root)
    if ocg_refs:
        order = [ocg_refs[k] for k, _n in LAYERS if k in ocg_refs]
        root[b"OCProperties"] = {
            b"OCGs": order,
            b"D": {
                b"Name": po.text_string("SciForge drawing layers"),
                b"Order": order,
                b"ON": list(order),
                b"OFF": [],
            },
        }
    # metadata
    old_info = doc.get(doc.trailer.get(b"Info"))
    old_info = old_info if isinstance(old_info, dict) else {}
    created = po.decode_text_string(old_info.get(b"CreationDate")) or pdf_date()
    modified = pdf_date()
    info = {}
    for key, field in (
        (b"Title", "title"),
        (b"Author", "author"),
        (b"Subject", "subject"),
        (b"Keywords", "keywords"),
        (b"Creator", "creator"),
        (b"Producer", "producer"),
    ):
        value = meta.get(field)
        if value:
            info[key] = po.text_string(str(value))
        elif key in old_info:
            info[key] = old_info[key]
    info[b"CreationDate"] = String(created.encode("ascii", "replace"))
    info[b"ModDate"] = String(modified.encode("ascii"))
    info[b"Trapped"] = Name(b"False")
    doc.trailer[b"Info"] = doc.add(info)
    full = dict(meta)
    for key, field in (
        (b"Title", "title"),
        (b"Author", "author"),
        (b"Subject", "subject"),
        (b"Producer", "producer"),
        (b"Creator", "creator"),
    ):
        if not full.get(field) and key in info:
            full[field] = po.decode_text_string(info[key])
    root[b"Metadata"] = doc.add(
        {b"Type": Name(b"Metadata"), b"Subtype": Name(b"XML")},
        xmp(full, _iso_date(created), _iso_date(modified), pdfa),
    )
    doc.objects[doc.trailer[b"Root"].num] = root
    version = doc.version if pdfa else max(doc.version, b"1.5")
    return doc.write(version), report


def summary(data):
    """What a PDF holds (tests, logs): pages and sizes, layer names, metadata, links."""
    doc = po.read(data)
    root = doc.get(doc.trailer.get(b"Root")) or {}
    out = {"pages": [], "layers": [], "info": {}, "links": [], "fonts": set()}
    props = doc.get(root.get(b"OCProperties")) or {}
    for ref in doc.get(props.get(b"OCGs")) or []:
        ocg = doc.get(ref) or {}
        out["layers"].append(po.decode_text_string(ocg.get(b"Name")))
    info = doc.get(doc.trailer.get(b"Info")) or {}
    for key, value in info.items():
        if isinstance(value, bytes) and not isinstance(value, Name):
            out["info"][bytes(key).decode("latin-1")] = po.decode_text_string(value)
    for num in doc.pages():
        page = doc.objects[num]
        media = [float(v) for v in (doc.get(page.get(b"MediaBox")) or [])]
        out["pages"].append(media)
        for ref in doc.get(page.get(b"Annots")) or []:
            annot = doc.get(ref) or {}
            action = doc.get(annot.get(b"A")) or {}
            if annot.get(b"Subtype") == b"Link" and action.get(b"URI") is not None:
                out["links"].append(bytes(action[b"URI"]).decode("utf-8", "replace"))
        resources = doc.get(page.get(b"Resources")) or {}
        for ref in (doc.get(resources.get(b"Font")) or {}).values():
            font = doc.get(ref) or {}
            if font.get(b"BaseFont") is not None:
                out["fonts"].add(bytes(font[b"BaseFont"]).decode("latin-1"))
    out["fonts"] = sorted(out["fonts"])
    return out
