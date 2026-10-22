# SPDX-License-Identifier: LGPL-2.1-or-later
"""Export PDF of a drawing, the FreeCAD side (needs FreeCAD's GUI: TechDraw prints its own
page scene). The PDF is rewritten by drawing_pdf_core.py, which explains what is added
(layers, searchable text, links, metadata) and how.

For every sheet:
1. markers go into TechDraw's scene: tiny items of a code colour, children of every view
   item, stacked between the kinds of things TechDraw draws in a view (marker_plan). They
   are Qt items only (the design is not touched, nothing goes into Undo) and they are
   taken out again right after printing, whatever happens. Never under the template item:
   TechDraw goes through the template's children when it prints and a foreign child there
   crashed FreeCAD (tried, 2026-10-22).
2. TechDraw prints the sheet (TechDrawGui.exportPageAsPdf, as before).
3. The text TechDraw draws as outlines is collected from SciForge's own data, the same
   that drew it: the title block and border (drawing_core.template_primitives),
   SciForge's SVG annotations (drawing_annot) and parts lists (drawing.table_layout_of),
   with the width Qt gives the text in the font the SVG asks for.
Then the sheets are put into one file (drawing_pdf.merge) and rewritten. If the rewrite
fails for any reason, the PDF TechDraw printed is kept as it is and the reason is logged:
Export PDF always gives a file.
"""

import os

import FreeCAD as App

from . import drawing, drawing_pdf, log, warn
from . import drawing_pdf_core as core
from . import drawing_pdf_font

MARKER_SIZE = 0.1  # scene units (0.01 mm): invisible, and printed almost transparent
# tests: a path where the PDF as TechDraw printed it (before the rewrite) is copied
KEEP_PRINTED = {"path": None}


def _qt():
    from PySide import QtCore, QtGui, QtWidgets

    return QtCore, QtGui, QtWidgets


def _marker_class():
    QtCore, QtGui, QtWidgets = _qt()

    class Marker(QtWidgets.QGraphicsItem):
        """A code-coloured dot in TechDraw's scene: where it is printed tells
        drawing_pdf_core.layer_content what the lines after it are."""

        # TechDraw tells its items apart by type(): the default (UserType) is TechDraw's
        # QGCustomBorder, so a marker has its own number, far from TechDraw's
        TYPE = QtWidgets.QGraphicsItem.UserType + 47110

        def __init__(self, colour, parent):
            super().__init__(parent)
            self.colour = QtGui.QColor(colour[0], colour[1], colour[2], 1)

        def type(self):
            return self.TYPE

        def boundingRect(self):
            return QtCore.QRectF(0.0, 0.0, MARKER_SIZE, MARKER_SIZE)

        def paint(self, painter, option, widget=None):
            try:
                painter.save()
                painter.setPen(QtCore.Qt.NoPen)
                painter.setBrush(self.colour)
                painter.drawRect(QtCore.QRectF(0.0, 0.0, MARKER_SIZE, MARKER_SIZE))
                painter.restore()
            except Exception as exc:
                warn("PDF marker: %s" % exc)

    return Marker


def scene_of(page):
    """TechDraw's graphics scene of a page (None when TechDraw has none for it)."""
    QtCore, QtGui, QtWidgets = _qt()
    try:
        import TechDrawGui

        scene = TechDrawGui.getSceneForPage(page)
        if scene is not None and not isinstance(scene, QtWidgets.QGraphicsScene):
            import shiboken6

            scene = shiboken6.wrapInstance(
                shiboken6.getCppPointer(scene)[0], QtWidgets.QGraphicsScene
            )
        if scene is not None:
            return scene
    except Exception as exc:
        log("no scene from TechDraw for %s (%s): looking for its tab" % (page.Label, exc))
    try:
        from . import drawing_ui

        area = drawing_ui._area()
        for sub in area.subWindowList() if area is not None else []:
            if drawing.same(drawing_ui.page_of_window(sub), page):
                for child in sub.findChildren(QtWidgets.QGraphicsView):
                    return child.scene()
    except Exception as exc:
        warn("scene of %s: %s" % (page.Label, exc))
    return None


def _rez(scene, page):
    """Scene units per millimetre (TechDraw: 10)."""
    try:
        width = float(page.Template.Width)
        rect = scene.sceneRect()
        if width > 0 and rect.width() > 0:
            return rect.width() / (3.0 * width)
    except Exception:
        pass
    return 10.0


def add_markers(page, scene, markers):
    """Markers into every view item of the page's scene, each also put into the list
    `markers` (so they can be taken out whatever happens). Returns (codes, hidden line
    widths per view)."""
    QtCore, QtGui, QtWidgets = _qt()
    doc = page.Document
    rez = _rez(scene, page)
    width, height = drawing.sheet_size_of(page)
    items, hidden, owners = [], {}, {}
    for item in scene.items():
        try:
            if item.data(0) != "QGIV":
                continue
            name = str(item.data(1) or "")
            obj = doc.getObject(name) if name else None
            if obj is None or name in owners:
                continue
            is_view = drawing.is_view(obj)
            items.append((name, "view" if is_view else "other"))
            owners[name] = item
            if is_view:
                try:
                    hidden[name] = float(obj.ViewObject.HiddenWidth) * rez
                except Exception:
                    pass
        except RuntimeError:
            continue
    plan, codes = core.marker_plan(items)
    Marker = _marker_class()
    page_rect = QtCore.QRectF(0.0, -height * rez, width * rez, height * rez)
    by_item = {}
    for name, _band, z, _code, colour in plan:
        by_item.setdefault(name, []).append((z, colour))
    for name, wanted in by_item.items():
        parent = owners[name]
        before = parent.boundingRect()
        spot = _marker_spot(parent, page_rect)
        mine = []
        for z, colour in wanted:
            marker = Marker(colour, parent)
            markers.append(marker)
            marker.setZValue(z)
            marker.setPos(spot)
            mine.append(marker)
        if parent.boundingRect() != before:
            # a marker outside what the view covers makes it bigger, and TechDraw puts
            # the caption under a view's extent: try the middle of what it covered
            middle = before.center() - QtCore.QPointF(MARKER_SIZE / 2.0, MARKER_SIZE / 2.0)
            for marker in mine:
                marker.setPos(middle)
            if parent.boundingRect() != before:
                log("PDF: a marker changes the extent of %s (its caption may move)" % name)
    return codes, hidden


def _marker_spot(item, page_rect):
    """Where an item's markers go (item coordinates): inside what it already covers, so
    it does not grow (TechDraw places a view's caption under its extent), and on the
    sheet, or Qt does not print them. A view's middle is its own origin."""
    QtCore, _QtGui, _QtWidgets = _qt()
    half = QtCore.QPointF(MARKER_SIZE / 2.0, MARKER_SIZE / 2.0)
    origin = QtCore.QPointF(0.0, 0.0)
    if page_rect.contains(item.mapToScene(origin)) and item.boundingRect().contains(origin):
        return origin - half
    covered = item.mapRectToScene(item.boundingRect()).intersected(page_rect)
    if covered.isEmpty():
        covered = page_rect
    return item.mapFromScene(covered.center()) - half


def remove_markers(markers):
    for marker in markers:
        try:
            scene = marker.scene()
            marker.setParentItem(None)
            if scene is not None:
                scene.removeItem(marker)
        except RuntimeError:
            pass  # TechDraw deleted it with its view
        except Exception as exc:
            warn("PDF marker not removed: %s" % exc)
    del markers[:]


# ------------------------------------------------------------------ text drawn as outlines
class _Recorder:
    """Stands in for drawing_core.DxfWriter and keeps the texts written to it."""

    def __init__(self):
        self.texts = []

    def text(self, x, y, height, value, layer="0", align="left", rotation=0.0):
        anchor = {"center": "middle", "right": "end"}.get(align, "start")
        self.texts.append((x, y, height, value, anchor, rotation))

    def __getattr__(self, name):
        return lambda *args, **kwargs: None


def _metrics():
    QtCore, QtGui, QtWidgets = _qt()
    font = QtGui.QFont("sans-serif")
    font.setStyleHint(QtGui.QFont.SansSerif)
    font.setPixelSize(100)
    return QtGui.QFontMetricsF(font)


def outline_texts(page):
    """[{"text", "x", "y", "size", "anchor", "width", "angle", "layer"}] in page mm: the
    text of the page TechDraw draws from SVG (as outlines in the PDF)."""
    texts = []
    try:
        metrics = _metrics()
    except Exception:
        metrics = None

    def add(x, y, size, text, anchor, angle, layer):
        text = str(text or "").strip()
        if not text:
            return
        width = None
        if metrics is not None:
            try:
                width = metrics.horizontalAdvance(text) / 100.0 * float(size)
            except Exception:
                width = None
        texts.append(
            {
                "text": text,
                "x": float(x),
                "y": float(y),
                "size": float(size),
                "anchor": anchor,
                "width": width,
                "angle": float(angle or 0.0),
                "layer": layer,
            }
        )

    if drawing.kind(page) in (drawing.TYPE, "DrawingSheet"):
        try:
            prims = drawing.core.template_primitives(
                drawing.standard_of(page),
                drawing.sheet_of(page),
                drawing.title(page),
                bool(drawing._get(page, "SciForgeTitleBlock", True)),
            )
            for prim in prims:
                if prim[0] == "text":
                    add(prim[1], prim[2], prim[3], prim[4], prim[6], 0.0, "border")
        except Exception as exc:
            warn("PDF text of %s's title block: %s" % (page.Label, exc))
    for obj in drawing.annotations(page):
        try:
            if not drawing._get(obj, "Visibility", True):
                continue
            if drawing.kind(obj) == "DrawingAnnotation":
                from . import drawing_annot

                rec = _Recorder()
                drawing_annot.to_dxf(rec, obj)
                for x, y, size, text, anchor, rot in rec.texts:
                    add(x, y, size, text, anchor, rot, "annotations")
            elif drawing.kind(obj) == "PartsList":
                layout, corner = drawing.table_layout_of(obj)
                for x, y, size, text, anchor in layout["texts"]:
                    add(
                        corner[0] + x,
                        corner[1] + y,
                        size,
                        text,
                        "middle" if anchor == "middle" else "start",
                        0.0,
                        "annotations",
                    )
        except Exception as exc:
            warn("PDF text of %s: %s" % (getattr(obj, "Label", "?"), exc))
    return texts


# ------------------------------------------------------------------ metadata
def metadata(page):
    """Title, author, subject, keywords from the drawing's title block; SciForge as the
    creating tool."""
    from . import __version__

    values = {}
    try:
        from . import drawing_sheets

        page = drawing_sheets.main_page(page)
        values = drawing.title(page) or {}
    except Exception as exc:
        warn("PDF metadata: %s" % exc)
    label = getattr(page, "Label", "")
    title = (values.get("Title") or "").strip() or label
    number = (values.get("PartNumber") or "").strip()
    description = (values.get("Description") or "").strip()
    subject = " - ".join(p for p in (number if number != title else "", description) if p)
    keywords = []
    for key, name in (
        ("PartNumber", "Part number"),
        ("Material", "Material"),
        ("Revision", "Revision"),
        ("Scale", "Scale"),
        ("Size", "Size"),
    ):
        value = (values.get(key) or "").strip()
        if value:
            keywords.append("%s: %s" % (name, value))
    try:
        freecad = ".".join(str(v) for v in App.Version()[:3])
    except Exception:
        freecad = ""
    return {
        "title": title,
        "author": (values.get("DrawnBy") or "").strip(),
        "subject": subject,
        "keywords": "; ".join(keywords),
        "creator": "SciForge %s" % __version__,
        "producer": "SciForge %s (FreeCAD %s TechDraw, Qt PDF)" % (__version__, freecad),
    }


def font_path():
    """osifont, the lettering font FreeCAD ships for TechDraw."""
    try:
        base = App.getResourceDir()
    except Exception:
        base = ""
    for path in (
        os.path.join(base, "Mod", "TechDraw", "Resources", "fonts", "osifont-lgpl3fe.ttf"),
        os.path.join(base, "examples", "osifont-lgpl3fe.ttf"),
    ):
        if os.path.isfile(path):
            return path
    return ""


# ------------------------------------------------------------------ export
def print_sheet(page, path):
    """One sheet printed by TechDraw with markers in it; returns what the rewrite needs
    to know about it."""
    info = {"size": drawing.sheet_size_of(page), "codes": None, "hidden": {}, "texts": []}
    scene = scene_of(page)
    markers = []
    try:
        if scene is not None:
            try:
                info["codes"], info["hidden"] = add_markers(page, scene, markers)
            except Exception as exc:
                remove_markers(markers)
                info["codes"] = None
                warn("PDF layers of %s left out: %s" % (page.Label, exc))
        else:
            log("PDF: %s has no scene, so no layers" % page.Label)
        drawing.print_pdf(page, path)
    finally:
        remove_markers(markers)
    try:
        info["texts"] = outline_texts(page)
    except Exception as exc:
        warn("PDF text of %s left out: %s" % (page.Label, exc))
    return info


def export(pages, path):
    """Fusion's Export PDF: `pages` (one per sheet, in order) in one PDF at `path`."""
    if not pages:
        raise drawing.DrawingError("There is no sheet to export.")
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    stem, _ext = os.path.splitext(path)
    parts, infos = [], []
    try:
        for i, sheet in enumerate(pages):
            part = path if len(pages) == 1 else "%s.sheet%d.tmp.pdf" % (stem, i + 1)
            infos.append(print_sheet(sheet, part))
            parts.append(part)
        if len(pages) > 1:
            drawing_pdf.merge_files(parts, path)
    finally:
        for part in parts:
            if part != path:
                try:
                    os.remove(part)
                except OSError:
                    pass
    if not os.path.isfile(path) or os.path.getsize(path) == 0:
        raise drawing.DrawingError("The PDF could not be written to %s." % path)
    improve(path, pages, infos)
    return path


def improve(path, pages, infos):
    """Rewrite the printed PDF with layers, searchable text, links and metadata; keep
    it as printed when that fails."""
    try:
        with open(path, "rb") as handle:
            data = handle.read()
        if KEEP_PRINTED["path"]:
            with open(KEEP_PRINTED["path"], "wb") as handle:
                handle.write(data)
        font, why = drawing_pdf_font.load(font_path())
        if why:
            log("PDF text font: %s (Helvetica is used instead)" % why)
        meta = metadata(pages[0])
        out, report = core.enhance(data, infos, meta, font)
        with open(path + ".part", "wb") as handle:
            handle.write(out)
        os.replace(path + ".part", path)
        for i, entry in enumerate(report["pages"]):
            log(
                "PDF sheet %d: layers %s, %d markers, %d texts added, %d links%s"
                % (
                    i + 1,
                    ", ".join(entry["layers"]) or "none",
                    entry["markers"],
                    entry["texts"],
                    entry["links"],
                    " (%s)" % entry["note"] if entry["note"] else "",
                )
            )
    except Exception as exc:
        try:
            os.remove(path + ".part")
        except OSError:
            pass
        warn(
            "PDF kept as TechDraw printed it (no layers, searchable title block, links "
            "or metadata): %s" % exc
        )
