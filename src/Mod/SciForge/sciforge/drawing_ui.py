# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's DRAWING workspace in SciForge: the commands, their dialogs and the mouse on
the sheet (the drawing logic is in drawing.py, the maths in drawing_core.py).

A drawing opens in its own tab (TechDraw's page view). While that tab is the active one
the ribbon shows only the contextual DRAWING tab, like Fusion's Drawing workspace, and
the design's timeline and navigation bar step aside. Clicks on the sheet go to the
command that is open (PageInput): placing a view, drawing a section line, picking edges
for a dimension... With no command open, a double-click edits a view or the title block,
D starts a dimension and Del deletes what is selected.
"""

import math
import os

import FreeCAD as App
import FreeCADGui as Gui

from . import commands, drawing, log, taskui, ui_icon_path, warn
from . import drawing_core as core
from .compat import QtCore, QtGui, QtWidgets

PAGE_VIEW = "TechDrawGui::MDIViewPage"
PICK_PIXELS = 8  # how near (screen pixels) a click must be to an edge to pick it
STATE = {
    "input": None,
    "mode": False,
    "connected": False,
    "observer": None,
    "timeline": False,
    "navbar": False,
}
# How an exported file is opened (a scenario swaps this to record instead of opening).
OPENER = {"open": lambda path: QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(path))}
SHADED_FACE = (0.82, 0.86, 0.9)
# Section hatching drawn like the edges. FreeCAD's default hatch colour is green with no
# opacity (0x00FF0000), so its hatching never showed on the sheet nor in the PDF.
HATCH_COLOR = (0.13, 0.145, 0.16, 1.0)
OVERLAY_KEY = 0x5F0E  # QGraphicsItem data key (and value) marking SciForge's preview items
OVERLAY_COLOR = "#ff8a1c"


def _later(fn, *args, ms=0):
    def run():
        try:
            fn(*args)
        except Exception as exc:
            warn("drawing: %s" % exc)

    QtCore.QTimer.singleShot(ms, run)


# ------------------------------------------------------------------ the page's tab
def _area():
    try:
        return Gui.getMainWindow().findChild(QtWidgets.QMdiArea)
    except Exception:
        return None


def active_page():
    """The drawing whose tab is the active one, or None."""
    area = _area()
    sub = area.activeSubWindow() if area is not None else None
    return page_of_window(sub)


def page_of_window(sub):
    """The drawing shown in an MDI sub-window (TechDraw names the tab after the page)."""
    try:
        if sub is None or sub.widget() is None:
            return None
        if sub.widget().metaObject().className() != PAGE_VIEW:
            return None
        title = sub.windowTitle().replace("[*]", "").strip()
    except RuntimeError:
        return None
    docs = [App.ActiveDocument] if App.ActiveDocument is not None else []
    docs += [d for d in App.listDocuments().values() if d not in docs]
    for doc in docs:
        for page in drawing.all_pages(doc):
            if page.Label == title:
                return page
    try:
        view = Gui.activeView()
        if view is not None and hasattr(view, "getPage"):
            page = view.getPage()
            if drawing.alive(page):
                return page
    except Exception:
        pass
    return None


def close_tab(page):
    """Close a drawing's tab (before the drawing is deleted: a page removed with undo kept
    keeps its tab open). Outside the delete's undo step, so that Undo brings the drawing
    back closed instead of reopening its tab before its sheet is back."""
    try:
        if page.ViewObject is not None and page.ViewObject.Visibility:
            page.ViewObject.hide()
    except Exception as exc:
        log("tab of %s not closed: %s" % (getattr(page, "Label", "?"), exc))


def active_tab():
    """The active tab (MDI sub-window), to come back to after a drawing is deleted."""
    area = _area()
    return area.activeSubWindow() if area is not None else None


def restore_tab(sub):
    """Make `sub` the active tab again if it still exists (FreeCAD brought another tab to
    the front when a drawing's tab closed, even one in the background)."""
    area = _area()
    if area is None or sub is None:
        return
    try:
        if any(s is sub or s == sub for s in area.subWindowList()) and (
            area.activeSubWindow() is not sub
        ):
            area.setActiveSubWindow(sub)
            _later(sync_mode, ms=0)
    except RuntimeError:
        pass  # (it was the deleted drawing's own tab)


def page_widget():
    """TechDraw's graphics view of the active drawing tab."""
    area = _area()
    sub = area.activeSubWindow() if area is not None else None
    if sub is None or sub.widget() is None:
        return None
    if sub.widget().metaObject().className() != PAGE_VIEW:
        return None
    for child in sub.findChildren(QtWidgets.QGraphicsView):
        return child
    return None


def _rez(gv, page):
    """Scene units per millimetre (TechDraw draws at 10 units per mm by default)."""
    try:
        width = float(page.Template.Width)
        rect = gv.scene().sceneRect()
        if width > 0 and rect.width() > 0:
            return rect.width() / (3.0 * width)
    except Exception:
        pass
    return 10.0


def to_page(gv, page, pos):
    """Widget (viewport) pixel -> page millimetres (y up)."""
    r = _rez(gv, page)
    sp = gv.mapToScene(QtCore.QPoint(int(pos.x()), int(pos.y())))
    return sp.x() / r, -sp.y() / r


def to_widget(gv, page, point):
    """Page millimetres -> viewport pixel."""
    r = _rez(gv, page)
    return gv.mapFromScene(QtCore.QPointF(point[0] * r, -point[1] * r))


def mm_per_pixel(gv, page):
    try:
        zoom = gv.transform().m11()
        return 1.0 / (_rez(gv, page) * zoom) if zoom > 0 else 0.5
    except Exception:
        return 0.5


def load_techdraw():
    """TechDraw's GUI module (its page view and view providers), without switching to
    FreeCAD's TechDraw workbench."""
    try:
        import TechDrawGui  # noqa: F401

        return True
    except Exception as exc:
        warn("TechDraw could not be loaded: %s" % exc)
        return False


def open_drawing(page):
    """Show a drawing in its tab (opening it if it was closed)."""
    load_techdraw()
    gdoc = None
    try:
        gdoc = Gui.getDocument(page.Document.Name)
        saved = not gdoc.Modified
    except Exception:
        saved = False
    try:
        page.ViewObject.show()
        log("drawing %s shown (active: %s)" % (page.Label, getattr(active_page(), "Label", None)))
    except Exception as exc:
        warn("could not open %s: %s" % (page.Label, exc))
        return
    if saved:
        # TechDraw opens a tab by setting the page's Visibility, which marked a saved design
        # as changed (Fusion: looking at a drawing changes nothing)
        _not_modified(gdoc)
        _later(_not_modified, gdoc, ms=0)
    _later(sync_mode, ms=50)


def _not_modified(gdoc):
    try:
        gdoc.Modified = False
    except Exception:
        pass


def show_design(doc=None):
    """Back to the design's 3D view tab (Fusion: the design's own tab)."""
    doc = doc or App.ActiveDocument
    area = _area()
    if area is None or doc is None:
        return False
    for sub in area.subWindowList():
        widget = sub.widget()
        if widget is None or widget.metaObject().className() != "Gui::View3DInventor":
            continue
        title = sub.windowTitle().replace("[*]", "")
        if title.split(" : ")[0] == doc.Label or title.startswith(doc.Label):
            area.setActiveSubWindow(sub)
            try:
                widget.setFocus()  # (the keys go to the design, no longer to the sheet)
            except RuntimeError:
                pass
            _later(sync_mode, ms=50)
            return True
    return False


def _click_focus_only(gv):
    """A drawing's tab takes the keyboard only when clicked. When the widget that has the
    keyboard disappears (a timeline step being rebuilt), Qt hands the keyboard to the next
    widget that takes it from Tab, and a drawing's tab that took it came to the front
    (double-clicking a step in the timeline switched to the drawing)."""
    widget = gv
    while widget is not None and not isinstance(widget, QtWidgets.QMdiSubWindow):
        widget = widget.parentWidget()
    if widget is None:
        return
    for child in [widget] + widget.findChildren(QtWidgets.QWidget):
        if child.focusPolicy() & QtCore.Qt.TabFocus:
            child.setFocusPolicy(QtCore.Qt.ClickFocus)


# ------------------------------------------------------------------ drawing mode
def enable():
    """Called when the SciForge interface turns on."""
    area = _area()
    if area is not None and not STATE["connected"]:
        area.subWindowActivated.connect(_window_changed)
        STATE["connected"] = True
    if STATE["observer"] is None:
        STATE["observer"] = _Observer()
        App.addDocumentObserver(STATE["observer"])
    if STATE["input"] is None:
        STATE["input"] = PageInput()
    _later(sync_mode, ms=0)


def disable():
    area = _area()
    if area is not None and STATE["connected"]:
        try:
            area.subWindowActivated.disconnect(_window_changed)
        except Exception:
            pass
        STATE["connected"] = False
    if STATE["observer"] is not None:
        try:
            App.removeDocumentObserver(STATE["observer"])
        except Exception:
            pass
        STATE["observer"] = None
    if STATE["input"] is not None:
        STATE["input"].detach()
    _set_mode(False)


def _window_changed(sub=None):
    if sub is None:
        return  # the keyboard went to a panel outside the tabs: the tab stays active
    _later(sync_mode, ms=0)


def sync_mode():
    """Drawing tab active -> DRAWING ribbon; otherwise back to the design's tabs."""
    page = active_page()
    gv = page_widget() if page is not None else None
    if gv is not None:
        try:
            _click_focus_only(gv)
        except RuntimeError:
            pass
    if STATE["input"] is not None:
        if gv is not None:
            STATE["input"].attach(gv, page)
        else:
            STATE["input"].detach()
    if page is not None:
        try:
            from . import drawing_sheets_ui

            drawing_sheets_ui.ensure_bar(page)
        except Exception as exc:
            warn("sheet bar: %s" % exc)
    current = taskui.current()
    if isinstance(current, DrawingPanel) and (page is None or not drawing.same(current.page, page)):
        current.finish()  # another tab: the drawing command ends, like Fusion's
    _set_mode(page is not None)


def is_on():
    return STATE["mode"]


def _set_mode(on):
    from . import shell

    ribbon = shell.ribbon()
    if ribbon is not None and hasattr(ribbon, "set_drawing_mode"):
        try:
            ribbon.set_drawing_mode(on)
        except Exception as exc:
            warn("drawing ribbon: %s" % exc)
    if on == STATE["mode"]:
        return
    STATE["mode"] = on
    try:
        from . import navbar_ui, timeline_ui

        dock = Gui.getMainWindow().findChild(QtWidgets.QDockWidget, "SciForgeTimelineDock")
        if on:
            STATE["timeline"] = bool(dock is not None and dock.isVisible())
            if STATE["timeline"]:
                timeline_ui.hide()  # Fusion's Drawing workspace has no timeline
            navbar_ui.hide()  # the design's orbit / look-at bar
            STATE["navbar"] = True
        else:
            if STATE["timeline"] and shell.is_on():
                timeline_ui.show()
            STATE["timeline"] = False
            if STATE["navbar"] and shell.is_on():
                navbar_ui.show()
            STATE["navbar"] = False
    except Exception as exc:
        warn("drawing mode: %s" % exc)
    log("drawing mode %s" % ("on" if on else "off"))


class _Observer:
    """After the design was recomputed, keep each drawing's title block, parts list and
    centre marks in step; after a view moved, keep projected views lined up with their
    parent (never inside the recompute or the change itself)."""

    def __init__(self):
        self.pending = set()

    def slotRecomputedDocument(self, doc):
        try:
            if drawing.drawings(doc):
                _later(refresh_drawings, doc.Name, ms=30)
        except Exception:
            pass

    def slotDeletedObject(self, obj):
        try:
            if drawing.is_page(obj):
                # Undo took a sheet away while its tab showed: close that tab
                from . import drawing_sheets_ui

                _later(drawing_sheets_ui.close_orphans, ms=50)
        except Exception:
            pass

    def slotChangedObject(self, obj, prop):
        try:
            if prop == "Label" and drawing.is_page(obj) and drawing.kind(obj) == drawing.TYPE:
                # a renamed drawing: its further sheets' tab titles follow
                _later(_relabel_sheets, obj.Document.Name, obj.Name, ms=0)
                return
            if prop not in ("X", "Y"):
                return
            if not (drawing.is_view(obj) or drawing.kind(obj) == "DrawingAnnotation"):
                return
            name = obj.Document.Name
            if name in self.pending:
                return
            self.pending.add(name)
            _later(self._align, name, ms=20)
        except Exception:
            pass

    def _align(self, doc_name):
        from . import drawing_annot

        self.pending.discard(doc_name)
        doc = App.listDocuments().get(doc_name)
        if doc is None or getattr(doc, "Transacting", False):
            return
        for page in drawing.all_pages(doc):
            drawing.keep_aligned(page)
            drawing_annot.follow(page)


def _relabel_sheets(doc_name, page_name):
    from . import drawing_sheets

    doc = App.listDocuments().get(doc_name)
    page = doc.getObject(page_name) if doc is not None else None
    if drawing.alive(page) and not getattr(doc, "Transacting", False):
        drawing_sheets.relabel(page)


LATE_REFRESH_MS = 1500  # TechDraw draws a view's lines in a thread: look again after this


def refresh_drawings(doc_name, again=True):
    doc = App.getDocument(doc_name) if doc_name in App.listDocuments() else None
    if doc is None or getattr(doc, "Restoring", False):
        return
    if again:
        # a big view's lines can come later than this first look: annotations, marks
        # and extensions that follow edges look once more (it changes only what moved)
        _later(refresh_drawings, doc_name, False, ms=LATE_REFRESH_MS)
    else:
        _later(_watch_depth, doc_name, 0, ms=DEPTH_WATCH_MS[0])
    for page in drawing.all_pages(doc):
        try:
            drawing.refresh(page)
            drawing.keep_aligned(page)
        except Exception as exc:
            warn("drawing %s: %s" % (page.Label, exc))
        try:
            apply_view_looks(page)
        except Exception as exc:
            import traceback

            log("drawing looks failed:\n%s" % traceback.format_exc())
            warn("drawing looks: %s" % exc)


DEPTH_WATCH_MS = (3000, 6000, 12000)  # a big section's lines can come later still


def _watch_depth(doc_name, step=0):
    """A straight section switches off its deeper lines (Slice / Distance) and a cut
    hole's seam line once TechDraw has drawn it, however long that takes (a quick look:
    nothing happens when they are done)."""
    doc = App.getDocument(doc_name) if doc_name in App.listDocuments() else None
    if doc is None or getattr(doc, "Restoring", False):
        return
    found = False
    try:
        for page in drawing.all_pages(doc):
            for view in drawing.all_views(page):
                if view.TypeId == drawing.SECTION:
                    found = True
                    drawing.refresh_depth(view)
    except Exception as exc:
        warn("section depth: %s" % exc)
    if found and step + 1 < len(DEPTH_WATCH_MS):
        _later(_watch_depth, doc_name, step + 1, ms=DEPTH_WATCH_MS[step + 1] - DEPTH_WATCH_MS[step])


def _rounded(color):
    return tuple(round(c, 3) for c in tuple(color)[:4])


def apply_view_looks(page):
    """What a view's style means for TechDraw's drawing of it (GUI only): Shaded fills
    the faces with one light colour (TechDraw has no shaded rendering); a section's
    hatching is drawn in the edges' colour."""
    for view in drawing.all_views(page):
        try:
            vo = getattr(view, "ViewObject", None)
            if vo is None or "FaceColor" not in vo.PropertiesList:
                continue
            shaded = drawing.style_of(view).startswith("Shaded")
            want = 0 if shaded else 100
            if vo.FaceTransparency != want:
                vo.FaceTransparency = want
            if shaded and tuple(round(c, 3) for c in vo.FaceColor[:3]) != SHADED_FACE:
                vo.FaceColor = SHADED_FACE
            if drawing.is_section(view):
                for prop in ("GeomHatchColor", "HatchColor"):
                    if prop in vo.PropertiesList and _rounded(getattr(vo, prop)) != _rounded(
                        HATCH_COLOR
                    ):
                        setattr(vo, prop, HATCH_COLOR)
        except Exception as exc:
            # (a view TechDraw could not compute refuses its colours: the view itself
            # shows the problem; the next update tries again)
            log("look of %s not set: %s" % (getattr(view, "Label", "?"), exc))


# ------------------------------------------------------------------ the mouse on the sheet
class PageInput(QtCore.QObject):
    """The sheet's mouse and keys: to the open drawing command, or the defaults (double-
    click edits, D dimension, Del delete, Esc clears)."""

    KEYS = (
        QtCore.Qt.Key_Escape,
        QtCore.Qt.Key_Return,
        QtCore.Qt.Key_Enter,
        QtCore.Qt.Key_Delete,
        QtCore.Qt.Key_D,
    )

    def __init__(self):
        super().__init__()
        self.gv = None
        self.page = None
        self.handler = None
        self.last = None  # last page point the mouse was at

    def attach(self, gv, page):
        if self.gv is gv:
            self.page = page
            return
        self.detach()
        self.gv = gv
        self.page = page
        try:
            gv.viewport().setMouseTracking(True)
            gv.viewport().installEventFilter(self)
            gv.installEventFilter(self)
        except RuntimeError:
            self.gv = None

    def detach(self):
        if self.gv is not None:
            try:
                self.gv.viewport().removeEventFilter(self)
                self.gv.removeEventFilter(self)
            except RuntimeError:
                pass
        self.gv = None

    def point(self, event):
        pos = event.position() if hasattr(event, "position") else event.pos()
        return to_page(self.gv, self.page, pos)

    def eventFilter(self, obj, event):
        try:
            return self._filter(obj, event)
        except Exception as exc:
            import traceback

            log("drawing input failed:\n%s" % traceback.format_exc())
            warn("drawing input: %s" % exc)
            return False

    def _filter(self, obj, event):
        if self.gv is None or self.page is None or not drawing.alive(self.page):
            return False
        kind = event.type()
        handler = self.handler
        viewport = self.gv.viewport()
        if obj is viewport:
            if kind == QtCore.QEvent.MouseMove:
                self.last = self.point(event)
                if handler is not None:
                    handler.on_move(self.last, event)
                return False
            if kind == QtCore.QEvent.MouseButtonPress:
                if event.button() != QtCore.Qt.LeftButton:
                    return False
                self.last = self.point(event)
                if handler is not None:
                    return bool(handler.on_press(self.last, event))
                return False
            if kind == QtCore.QEvent.MouseButtonRelease:
                if event.button() != QtCore.Qt.LeftButton:
                    return False
                if handler is not None:
                    return bool(handler.on_release(self.point(event), event))
                return False
            if kind == QtCore.QEvent.MouseButtonDblClick:
                if event.button() != QtCore.Qt.LeftButton:
                    return False
                point = self.point(event)
                if handler is not None:
                    return bool(handler.on_double(point, event))
                return default_double_click(self.page, point)
            return False
        if obj is self.gv:
            if kind == QtCore.QEvent.ShortcutOverride and event.key() in self.KEYS:
                if event.modifiers() & (QtCore.Qt.ControlModifier | QtCore.Qt.AltModifier):
                    return False
                event.accept()
                return True
            if kind == QtCore.QEvent.KeyPress and event.key() in self.KEYS:
                if event.modifiers() & (QtCore.Qt.ControlModifier | QtCore.Qt.AltModifier):
                    return False
                if handler is not None and handler.on_key(event.key(), event):
                    return True
                return default_key(self.page, event.key())
        return False


def default_double_click(page, point):
    """No command open: double-click a dimension or an annotation to edit it (Fusion's
    Dimension dialog...), a view to edit it, the title block to fill it in."""
    try:
        from . import drawing_annot_ui

        if drawing_annot_ui.edit_at(page, point):
            return True
    except Exception as exc:
        warn("edit: %s" % exc)
    try:
        from . import drawing_breakout_ui

        if drawing_breakout_ui.edit_at(page, point):
            return True
    except Exception as exc:
        warn("breakout: %s" % exc)
    view = view_at(page, point)
    if view is not None:
        _later(edit_view, view)
        return True
    if in_title_block(page, point):
        _later(TitleBlockPanel.start, page)
        return True
    return False


def default_key(page, key):
    if key == QtCore.Qt.Key_D:
        _later(Gui.runCommand, "SciForge_DrawingDimension")
        return True
    if key == QtCore.Qt.Key_Delete:
        _later(delete_selected)
        return True
    if key == QtCore.Qt.Key_Escape:
        Gui.Selection.clearSelection()
        return True
    return False


def in_title_block(page, point):
    if not getattr(page, "SciForgeTitleBlock", False):
        return False
    x0, y0, x1, y1 = core.title_block_rect(drawing.standard_of(page), drawing.sheet_of(page))
    return x0 <= point[0] <= x1 and y0 <= point[1] <= y1


def view_at(page, point, kinds=None, margin=3.0):
    """The view under a page point (the smallest one when views overlap)."""
    best = None
    for view in drawing.all_views(page):
        if kinds is not None and view.TypeId not in kinds:
            continue
        if not getattr(view, "Visibility", True):
            continue
        x, y = drawing.view_position(view)
        half_w, half_h = drawing.view_extent(view)
        if abs(point[0] - x) <= half_w + margin and abs(point[1] - y) <= half_h + margin:
            area = half_w * half_h
            if best is None or area < best[0]:
                best = (area, view)
    return best[1] if best else None


def _edges_of(view):
    """[(name, local edge)] of every edge of a view, as TechDraw names them."""
    found = []
    i = 0
    while i < 5000:
        try:
            edge = view.getEdgeBySelection("Edge%d" % i)
        except Exception:
            break
        if edge is None:
            break
        found.append(("Edge%d" % i, edge))
        i += 1
    return found


def _vertexes_of(view):
    found = []
    i = 0
    while i < 5000:
        try:
            vertex = view.getVertexBySelection("Vertex%d" % i)
        except Exception:
            break
        if vertex is None:
            break
        found.append(("Vertex%d" % i, vertex.Point))
        i += 1
    return found


def pick_at(page, point, tolerance, want_vertex=True, kinds=None, curve=None):
    """(view, element name, local point) of the edge or vertex nearest a page point, or
    (view, None, local point) on a view's empty area, or (None, None, None). `curve`
    "circle" or "line" only looks at such edges (a centre mark takes circles only)."""
    import Part

    view = view_at(page, point, kinds)
    if view is None:
        return None, None, None
    local = drawing.page_to_local(view, point)
    s = drawing.scale_of(view) or 1.0
    tol = tolerance / s
    probe = Part.Vertex(App.Vector(local[0], local[1], 0))
    if want_vertex:
        best = None
        for name, p in _vertexes_of(view):
            d = math.hypot(p.x - local[0], p.y - local[1])
            if d <= tol * 0.6 and (best is None or d < best[0]):
                best = (d, name)
        if best is not None:
            return view, best[1], local
    best = None
    hidden_shown = bool(getattr(view, "HardHidden", False))
    visible = _visible_signatures(view) if not hidden_shown else None
    near = []
    for name, edge in _edges_of(view):
        try:
            d = edge.distToShape(probe)[0]
        except Exception:
            continue
        if d > tol:
            continue
        if curve is not None and not _is_curve(edge, curve):
            continue
        near.append((round(d, 4), name, visible is None or _signature(edge, s) in visible))
        if visible is not None and _signature(edge, s) not in visible:
            continue
        if best is None or d < best[0] - 1e-9:
            best = (d, name)
    if best is None and near:
        log("pick at %s: only hidden edges near %s" % (local, near))
    return view, (best[1] if best else None), local


def _is_curve(edge, curve):
    name = edge.Curve.__class__.__name__
    if curve == "circle":
        return name == "Circle"
    if curve == "line":
        return name in ("Line", "LineSegment")
    return True


def _signature(edge, scale):
    try:
        a = edge.Vertexes[0].Point
        b = edge.Vertexes[-1].Point
        pts = sorted(
            [
                (round(a.x * scale, 3), round(a.y * scale, 3)),
                (round(b.x * scale, 3), round(b.y * scale, 3)),
            ]
        )
        return (tuple(pts), round(edge.Length * scale, 3))
    except Exception:
        return None


def _visible_signatures(view):
    found = set()
    try:
        for edge in view.getVisibleEdges(True):
            found.add(_signature(edge, 1.0))
    except Exception:
        pass
    return found


def snap_point(view, local, tolerance):
    """A clicked point moved onto a vertex, a circle's centre or an edge's middle near it
    (Fusion snaps the section line and the detail centre to such points)."""
    import Part

    s = drawing.scale_of(view) or 1.0
    tol = tolerance / s
    best = None
    for _name, p in _vertexes_of(view):
        d = math.hypot(p.x - local[0], p.y - local[1])
        if d <= tol and (best is None or d < best[0]):
            best = (d, (p.x, p.y))
    for _name, edge in _edges_of(view):
        try:
            if isinstance(edge.Curve, Part.Circle):
                c = edge.Curve.Center
                candidates = [(c.x, c.y)]
            else:
                m = edge.valueAt((edge.FirstParameter + edge.LastParameter) / 2.0)
                candidates = [(m.x, m.y)]
        except Exception:
            continue
        for q in candidates:
            d = math.hypot(q[0] - local[0], q[1] - local[1])
            if d <= tol and (best is None or d < best[0]):
                best = (d, q)
    return best[1] if best else local


# ------------------------------------------------------------------ dialogs: shared base
def _combo(items, current=None, editable=False):
    box = QtWidgets.QComboBox()
    box.addItems(list(items))
    box.setEditable(editable)
    if current is not None:
        index = box.findText(current)
        if index >= 0:
            box.setCurrentIndex(index)
        elif editable:
            box.setEditText(current)
    return box


class DrawingPanel(taskui.Panel):
    """A drawing command's dialog: one undo step; the sheet's clicks come here."""

    title = "Drawing"
    icon = "dw_base_view"
    last = None

    def __init__(self, page, transaction):
        super().__init__(page.Document, transaction)
        self.page = page
        self.gv = page_widget()
        self.overlay = []
        self._scene_ref = None
        self.hint = QtWidgets.QLabel("")
        self.hint.setWordWrap(True)
        self.hint.setObjectName("SciForgeDrawingHint")
        self.layout.addRow(self.hint)
        if STATE["input"] is None:
            STATE["input"] = PageInput()
        if self.gv is not None:
            STATE["input"].attach(self.gv, page)
        STATE["input"].handler = self
        type(self).last = self

    def say(self, text):
        try:
            self.hint.setText(text)
        except RuntimeError:
            pass

    def show(self):
        Gui.Control.showDialog(self)
        if self.gv is not None:
            try:
                self.gv.setFocus()
            except RuntimeError:
                pass
        return self

    # -- overlay drawn on the sheet (lines and circles while picking) -------------------
    def _scene(self):
        # One wrapper of the scene for the panel's life: PySide ties the items added through
        # a wrapper to it, and with a new wrapper per call the overlay's items could no
        # longer be removed (a placed table's outline stayed on the sheet).
        try:
            if self._scene_ref is None and self.gv is not None:
                self._scene_ref = self.gv.scene()
            return self._scene_ref
        except RuntimeError:
            return None

    def _keep(self, item):
        item.setZValue(1e6)
        item.setData(OVERLAY_KEY, OVERLAY_KEY)
        self.overlay.append(item)
        return item

    def _pen(self, dashed=False):
        pen = QtGui.QPen(QtGui.QColor(OVERLAY_COLOR))
        pen.setCosmetic(True)
        pen.setWidth(2)
        if dashed:
            pen.setStyle(QtCore.Qt.DashDotLine)
        return pen

    def overlay_line(self, a, b, dashed=True):
        scene = self._scene()
        if scene is None:
            return None
        r = _rez(self.gv, self.page)
        return self._keep(
            scene.addLine(a[0] * r, -a[1] * r, b[0] * r, -b[1] * r, self._pen(dashed))
        )

    def overlay_circle(self, c, radius):
        scene = self._scene()
        if scene is None:
            return None
        r = _rez(self.gv, self.page)
        return self._keep(
            scene.addEllipse(
                (c[0] - radius) * r,
                -(c[1] + radius) * r,
                2 * radius * r,
                2 * radius * r,
                self._pen(),
            )
        )

    def overlay_rect(self, x0, y0, x1, y1):
        scene = self._scene()
        if scene is None:
            return None
        r = _rez(self.gv, self.page)
        return self._keep(
            scene.addRect(
                min(x0, x1) * r, -max(y0, y1) * r, abs(x1 - x0) * r, abs(y1 - y0) * r, self._pen()
            )
        )

    def clear_overlay(self):
        self.overlay = []
        scene = self._scene()
        if scene is None:
            return
        try:
            for item in scene.items():
                if item.data(OVERLAY_KEY) == OVERLAY_KEY:
                    scene.removeItem(item)
        except RuntimeError:
            pass

    def tolerance(self):
        return PICK_PIXELS * mm_per_pixel(self.gv, self.page) if self.gv is not None else 2.0

    # -- the sheet's events (override) -------------------------------------------------
    def on_press(self, point, event):
        return True  # a command's clicks never move or select views by accident

    def on_release(self, point, event):
        return True

    def on_move(self, point, event):
        pass

    def on_double(self, point, event):
        return True

    def on_key(self, key, event):
        if key == QtCore.Qt.Key_Escape:
            _later(self.escape)
            return True
        if key in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
            _later(taskui.press_dialog_button, "accept")
            return True
        return True

    def escape(self):
        """Esc: Cancel, like Fusion (commands that keep what was placed override)."""
        taskui.press_dialog_button("reject")

    def _recompute(self):
        if self._closed:
            return
        try:
            self.doc.recompute()
            apply_view_looks(self.page)
        except Exception as exc:
            try:
                self.message.setText(str(exc))
            except RuntimeError:
                pass

    def cleanup(self):
        self.clear_overlay()
        if STATE["input"] is not None and STATE["input"].handler is self:
            STATE["input"].handler = None
        super().cleanup()

    def accept(self):
        ok = super().accept()
        if ok:
            _later(refresh_drawings, self.doc.Name, ms=50)
        return ok


def _need_page():
    page = active_page()
    if page is None:
        commands.tell(
            "Open a drawing first: File > New Drawing, or double-click one in the browser."
        )
    return page


def _start(panel_class, *args):
    if not commands.finish_open_dialog():
        return None
    page = _need_page()
    if page is None:
        return None
    try:
        return panel_class(page, *args).show()
    except drawing.DrawingError as exc:
        commands.tell(str(exc))
    except Exception as exc:
        warn("%s: %s" % (panel_class.__name__, exc))
    return None


def _single_base(page):
    bases = drawing.base_views(page)
    return bases[0] if len(bases) == 1 else None


# ------------------------------------------------------------------ New Drawing
class CreateDrawingPanel(taskui.Panel):
    """Fusion's Create Drawing dialog (File > New Drawing > From Design)."""

    title = "Create Drawing"
    icon = "dw_new"
    last = None

    def __init__(self, doc):
        super().__init__(doc, "New Drawing")
        type(self).last = self
        units = _design_units(doc)
        standard = core.default_standard(units)
        self.reference = QtWidgets.QLabel(doc.Label)
        self.layout.addRow("Design", self.reference)
        self.contents = _combo(["Full Assembly", "Visible Only", "Select"])
        self.contents.setObjectName("SciForgeDrawingContents")
        self.layout.addRow("Contents", self.contents)
        self.bodies = QtWidgets.QListWidget()
        self.bodies.setObjectName("SciForgeDrawingBodies")
        self.bodies.setMaximumHeight(110)
        for body in drawing.design_bodies(doc):
            item = QtWidgets.QListWidgetItem(_body_caption(body))
            item.setData(QtCore.Qt.UserRole, body.Name)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(QtCore.Qt.Checked)
            self.bodies.addItem(item)
        self.layout.addRow(self.bodies)
        self.bodies.setVisible(False)
        self.template = _combo(["SciForge title block", "Blank sheet (frame only)"])
        self.layout.addRow("Template", self.template)
        self.standard = _combo(core.STANDARDS, standard)
        self.layout.addRow("Standard", self.standard)
        self.units = _combo(core.UNITS, units)
        self.layout.addRow("Units", self.units)
        self.sheet = _combo(core.sheet_names(standard), core.DEFAULT_SHEET[standard])
        self.layout.addRow("Sheet Size", self.sheet)
        self.views = _combo(["Manual (place the base view)", "Automatic (base, projected, iso)"])
        self.layout.addRow("Views", self.views)
        self.contents.currentTextChanged.connect(self._contents_changed)
        self.standard.currentTextChanged.connect(self._standard_changed)
        self.finish_layout()
        self.page = None

    def _contents_changed(self, text):
        try:
            self.bodies.setVisible(text == "Select")
        except RuntimeError:
            pass

    def _standard_changed(self, text):
        try:
            self.sheet.clear()
            self.sheet.addItems(core.sheet_names(text))
            self.sheet.setCurrentText(core.DEFAULT_SHEET.get(text, "A3"))
        except RuntimeError:
            pass

    def chosen_bodies(self):
        found = []
        for i in range(self.bodies.count()):
            item = self.bodies.item(i)
            if item.checkState() == QtCore.Qt.Checked:
                body = self.doc.getObject(item.data(QtCore.Qt.UserRole))
                if body is not None:
                    found.append(body)
        return found

    def accept(self):
        load_techdraw()
        try:
            sources = drawing.sources_for(
                self.doc, self.contents.currentText(), self.chosen_bodies()
            )
            self.page = drawing.create_drawing(
                self.doc,
                sources,
                standard=self.standard.currentText(),
                units=self.units.currentText(),
                sheet=self.sheet.currentText(),
                title_block=self.template.currentIndex() == 0,
                contents=self.contents.currentText(),
            )
        except drawing.DrawingError as exc:
            self.message.setText(str(exc))
            return False
        except Exception as exc:
            self.message.setText(str(exc))
            warn("new drawing: %s" % exc)
            return False
        automatic = self.views.currentIndex() == 1
        page = self.page
        self.doc.recompute()
        ok = super().accept()
        if ok:
            open_drawing(page)
            if automatic:
                _later(automatic_views, page, ms=300)
            else:
                _later(start_base_view, page, ms=300)
        return ok


def _design_units(doc):
    try:
        from . import browser_ui

        unit = browser_ui.units(doc)
        if unit in ("in", "ft"):
            return "in"
    except Exception:
        pass
    return "mm"


def _body_caption(body):
    from . import components

    comp = components.component_of(body)
    return "%s / %s" % (comp.Label, body.Label) if comp is not None else body.Label


def start_base_view(page):
    if not drawing.same(active_page(), page):
        open_drawing(page)
    if not commands.finish_open_dialog():
        return None
    return BaseViewPanel(page).show()


def automatic_views(page):
    """Fusion's Automatic drawing: base view, two projected views and an isometric one,
    laid out on the sheet at the automatic scale. One undo step."""
    doc = page.Document
    sources = [s for s in page.SciForgeSources if drawing.alive(s)]
    if not sources:
        return None
    doc.openTransaction("Automatic Views")
    try:
        projection = page.ProjectionType
        scale = drawing.automatic_scale(page, sources, "Front")
        axes = core.view_axes(*drawing.orientation_axes("Front"))
        w, h, d = drawing.model_extent(sources, axes)
        gap = 15.0
        sx = 1.0 if projection == "Third angle" else -1.0
        dx = sx * ((w + d) / 2.0 * scale + gap)
        dy = sx * ((h + d) / 2.0 * scale + gap)
        x0, y0, x1, y1 = core.drawing_area(drawing.standard_of(page), drawing.sheet_of(page))
        block_w = (w + d) * scale + gap
        block_h = (h + d) * scale + gap
        cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
        bx = cx - sx * (block_w / 2.0 - w * scale / 2.0)
        by = cy - sx * (block_h / 2.0 - h * scale / 2.0)
        base = drawing.add_base_view(page, sources, bx, by, "Front", scale=scale)
        for vx, vy in ((0.0, dy), (dx, 0.0), (dx, dy)):
            kind = core.projected_kind(vx, vy, projection)
            drawing.add_projected(base, kind, bx + vx, by + vy)
        doc.recompute()
        taskui._end_transaction(doc)
    except Exception as exc:
        taskui._end_transaction(doc, abort=True)
        warn("automatic views: %s" % exc)
        return None
    _later(refresh_drawings, doc.Name, ms=100)
    return base


# ------------------------------------------------------------------ Base View
class BaseViewPanel(DrawingPanel):
    """Fusion's Base View: the view follows the mouse until a click places it; the
    Orientation, Style, Scale and Tangent Edges change it live."""

    title = "Base View"
    icon = "dw_base_view"

    def __init__(self, page, view=None):
        super().__init__(page, "Base View" if view is None else "Edit View")
        self.editing = view is not None
        sources = [s for s in getattr(page, "SciForgeSources", []) if drawing.alive(s)]
        if not sources:
            sources = drawing.design_bodies(page.Document)
        if not sources:
            raise drawing.DrawingError("The design has no solid bodies to draw.")
        self.placed = self.editing
        if view is None:
            x0, y0, x1, y1 = core.drawing_area(drawing.standard_of(page), drawing.sheet_of(page))
            view = drawing.add_base_view(page, sources, (x0 + x1) / 2.0, (y0 + y1) / 2.0)
        self.view = view
        self.orientation = _combo(core.ORIENTATION_NAMES, drawing.orientation_of(view))
        self.orientation.setObjectName("SciForgeDrawingOrientation")
        self.style = _combo(core.STYLES, drawing.style_of(view))
        self.style.setObjectName("SciForgeDrawingStyle")
        self.scale = _combo(core.scale_choices(), core.format_scale(drawing.scale_of(view)), True)
        self.scale.setObjectName("SciForgeDrawingScale")
        self.tangent = _combo(core.TANGENT_EDGES, drawing.tangent_of(view))
        self.layout.addRow("Orientation", self.orientation)
        self.layout.addRow("Style", self.style)
        self.layout.addRow("Scale", self.scale)
        self.layout.addRow("Tangent Edges", self.tangent)
        self.show_label = _label_rows(self, view)
        self.auto_boxes = _auto_mark_rows(self, view)
        self.orientation.currentTextChanged.connect(self._orientation)
        self.style.currentTextChanged.connect(self._style)
        self.tangent.currentTextChanged.connect(self._style)
        self.scale.currentTextChanged.connect(self._scale)
        self.finish_layout()
        self.say(
            "Change the options, then OK."
            if self.placed
            else "Move the view where you want it and click to place it."
        )
        self.doc.recompute()

    def target_view(self):
        return self.view

    def _orientation(self, text):
        if not self._closed:
            drawing.set_base_orientation(self.view, text)
            self.schedule()

    def _style(self, _text=None):
        if not self._closed:
            drawing.set_view_style(self.view, self.style.currentText(), self.tangent.currentText())
            self.schedule()

    def _scale(self, text):
        if self._closed:
            return
        value = core.parse_scale(text)
        if value is None:
            self.message.setText("Type a scale like 1:2 or 2:1.")
            return
        self.message.setText("")
        drawing.set_scale(self.view, value)
        self.schedule()

    def on_move(self, point, event):
        if not self.placed and not self._closed:
            self.view.X = point[0]
            self.view.Y = point[1]

    def on_press(self, point, event):
        if not self.placed:
            self.view.X = point[0]
            self.view.Y = point[1]
            self.placed = True
            self.say("Change the options, then OK.")
        return True


# ------------------------------------------------------------------ Projected View
class ProjectedPanel(DrawingPanel):
    """Fusion's Projected View: click the parent view, move round it and click to place a
    view in that direction; several in a row; Enter, Esc or OK ends."""

    title = "Projected View"
    icon = "dw_projected_view"

    def __init__(self, page):
        super().__init__(page, "Projected View")
        self.parent = None
        self.preview = None
        self.placed = []
        if not drawing.base_views(page):
            raise drawing.DrawingError("Place a base view first (CREATE > Base View).")
        self.finish_layout()
        preselected = [v for v in _selected_views(page) if v.TypeId == drawing.PART_VIEW]
        start = preselected[0] if len(preselected) == 1 else _single_base(page)
        if start is not None:
            self._use(start)
        else:
            self.say("Click the view to project from.")

    def _use(self, view):
        self.parent = view
        self.say("Move round the view and click to place a projected view; Enter or Esc when done.")

    def on_press(self, point, event):
        if self.parent is None:
            view = view_at(self.page, point, (drawing.PART_VIEW,))
            if view is None:
                self.message.setText("Click a base or projected view.")
                return True
            self.message.setText("")
            self._use(view)
            return True
        if self.preview is not None:
            self.placed.append(self.preview)
            self.preview = None
            self.say("Placed. Click to place another one; Enter or Esc when done.")
        return True

    def on_move(self, point, event):
        if self.parent is None or self._closed:
            return
        px, py = drawing.view_position(self.parent)
        half_w, half_h = drawing.view_extent(self.parent)
        dx, dy = point[0] - px, point[1] - py
        if not core.outside(dx, dy, half_w, half_h):
            self._drop_preview()
            return
        kind = core.projected_kind(dx, dy, self.page.ProjectionType)
        taken = {
            getattr(v, "SciForgeKind", "")
            for v in drawing.children_of(self.parent)
            if not drawing.same(v, self.preview)
        }
        if kind in taken:
            self._drop_preview()
            return
        ox, oy = core.projected_offset(kind, dx, dy)
        if self.preview is not None and getattr(self.preview, "SciForgeKind", "") != kind:
            self._drop_preview()
        if self.preview is None:
            try:
                self.preview = drawing.add_projected(self.parent, kind, px + ox, py + oy)
            except drawing.DrawingError:
                return
            self.schedule()
        else:
            self.preview.X = px + ox
            self.preview.Y = py + oy
            self.preview.SciForgeOffset = [ox, oy]

    def _drop_preview(self):
        if self.preview is not None and drawing.alive(self.preview):
            name = self.preview.Name
            try:
                self.page.removeView(self.preview)
            except Exception:
                pass
            self.doc.removeObject(name)
            self.schedule()
        self.preview = None

    def escape(self):
        taskui.press_dialog_button("accept")  # Fusion: Esc ends and keeps the placed views

    def accept(self):
        self._drop_preview()
        return super().accept()


# ------------------------------------------------------------------ Section View
PLACE_ZONE = 12.0  # mm beyond the parent view's box: a click there places the section


class SectionPanel(DrawingPanel):
    """Fusion's Section View: click the view, the cut line's points (more than two make
    a half, offset or aligned section), Enter (or move well away from the view), then
    place the section view on either side (it moves lined up with its parent)."""

    title = "Section View"
    icon = "dw_section_view"

    def __init__(self, page, section=None):
        super().__init__(page, "Section View" if section is None else "Edit View")
        self.parent = None
        self.points = []
        self.line_done = False
        self.section = section
        self.placed = section is not None
        self.side = None
        self.label = QtWidgets.QLineEdit(section.SectionSymbol if section is not None else "")
        self.label.setObjectName("SciForgeDrawingLabel")
        self.kind = QtWidgets.QLabel(
            drawing.section_kind_of(section) if section is not None else ""
        )
        self.kind.setObjectName("SciForgeSectionKind")
        self.scale = _combo(
            core.scale_choices(),
            core.format_scale(drawing.scale_of(section)) if section is not None else "",
            True,
        )
        self.style = _combo(
            core.STYLES, drawing.style_of(section) if section is not None else "Visible Edges"
        )
        self.style.setObjectName("SciForgeDrawingStyle")
        mode, value = drawing.section_depth(section) if section is not None else ("Full", 10.0)
        self.depth = _combo(drawing.DEPTH_MODES, mode)
        self.depth.setObjectName("SciForgeSectionDepth")
        self.distance = QtWidgets.QLineEdit(core._short(value or 10.0))
        self.distance.setObjectName("SciForgeSectionDistance")
        self.hatch = QtWidgets.QCheckBox("Hatch the cut faces")
        self.hatch.setChecked(section is None or section.CutSurfaceDisplay != "Hide")
        self.layout.addRow("Label", self.label)
        self.layout.addRow("Type", self.kind)
        self.layout.addRow("Scale", self.scale)
        self.layout.addRow("Style", self.style)
        self.layout.addRow("Section Depth", self.depth)
        self.layout.addRow("Distance (mm)", self.distance)
        self.layout.addRow(self.hatch)
        self.show_label = _label_rows(self, section, with_text=False)
        self.auto_boxes = _auto_mark_rows(self, section)
        self.label.textChanged.connect(self._label)
        self.scale.currentTextChanged.connect(self._scale)
        self.style.currentTextChanged.connect(self._style)
        self.depth.currentTextChanged.connect(self._depth)
        self.distance.editingFinished.connect(self._depth)
        self.hatch.toggled.connect(self._hatch)
        self._depth_rows()
        self.finish_layout()
        if section is not None:
            self.say("Change the options, then OK.")
        else:
            preselected = _selected_views(page)
            if len(preselected) == 1:
                self._parent(preselected[0])
            else:
                self.say("Click the view to cut.")

    def target_view(self):
        return self.section

    def _depth_rows(self):
        try:
            self.layout.setRowVisible(self.distance, self.depth.currentText() == "Distance")
        except Exception:
            self.distance.setEnabled(self.depth.currentText() == "Distance")

    def _parent(self, view):
        if view.TypeId == drawing.DETAIL:
            self.message.setText("Pick a base, projected or section view (not a detail view).")
            return
        self.parent = view
        self.message.setText("")
        self.say("Click where the cut line starts (it snaps to points, centres and middles).")

    def _far_out(self, point):
        """The mouse is well away from the parent view: where a section view goes."""
        px, py = drawing.view_position(self.parent)
        half_w, half_h = drawing.view_extent(self.parent)
        return abs(point[0] - px) > half_w + PLACE_ZONE or abs(point[1] - py) > half_h + PLACE_ZONE

    def on_press(self, point, event):
        if self.placed:
            return True
        if self.parent is None:
            view = view_at(self.page, point)
            if view is None:
                self.message.setText("Click on a view.")
                return True
            self._parent(view)
            return True
        if not self.line_done:
            if len(self.points) >= 2 and self._far_out(point):
                self._finish_line()
                self.on_move(point, event)
                return self._place(point)
            local = snap_point(
                self.parent, drawing.page_to_local(self.parent, point), self.tolerance()
            )
            if self.points:
                local = _straighten(self.points[-1], local)
                last = self.points[-1]
                if math.hypot(local[0] - last[0], local[1] - last[1]) < 1e-6:
                    if len(self.points) >= 2:
                        self._finish_line()  # a click on the last point again ends the line
                        return True
                    self.message.setText("Click a second point away from the first one.")
                    return True
            self.points.append(local)
            self.message.setText("")
            if len(self.points) == 1:
                self.say("Click where the cut line ends.")
            else:
                self.say(
                    "Click more points to bend the line, or Enter (or move away from the view) "
                    "and click to place the section view."
                )
            self._draw_line(None)
            return True
        return self._place(point)

    def _place(self, point):
        if self.section is not None:
            self.placed = True
            self.clear_overlay()
            self.say("Change the options, then OK.")
        return True

    def _finish_line(self):
        if len(self.points) < 2:
            self.message.setText("Click at least two points for the cut line.")
            return False
        kind = core.section_kind(self.points)
        if kind is None:
            self.message.setText("Two points of the cut line are the same: click again.")
            self.points = self.points[:1]
            return False
        self.line_done = True
        self.kind.setText(kind)
        self.clear_overlay()
        self.say("Move to the side the section view goes and click to place it.")
        return True

    def _draw_line(self, mouse_local):
        self.clear_overlay()
        pts = list(self.points)
        if mouse_local is not None:
            pts.append(mouse_local)
        for a, b in zip(pts, pts[1:]):
            self.overlay_line(
                drawing.local_to_page(self.parent, a), drawing.local_to_page(self.parent, b)
            )

    def on_key(self, key, event):
        if (
            key in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter)
            and self.parent is not None
            and not self.line_done
            and not self.placed
        ):
            if self._finish_line() and self.last_point is not None:
                _later(self.on_move, self.last_point, None)
            return True
        return super().on_key(key, event)

    last_point = None

    def on_move(self, point, event):
        if self._closed or self.placed or self.parent is None:
            return
        self.last_point = point
        if not self.line_done:
            if not self.points:
                return
            if len(self.points) >= 2 and self._far_out(point):
                if not self._finish_line():
                    return
            else:
                local = _straighten(self.points[-1], drawing.page_to_local(self.parent, point))
                self._draw_line(local)
                return
        local = drawing.page_to_local(self.parent, point)
        p1, p2 = self.points[0], self.points[1]
        line = core.section_line(p1, p2, local, self.page.ProjectionType)
        if line is None:
            return
        side = (
            1
            if line["n"][0] * (local[0] - line["mid"][0])
            + line["n"][1] * (local[1] - line["mid"][1])
            >= 0
            else -1
        )
        px, py = drawing.view_position(self.parent)
        mx, my = drawing.local_to_page(self.parent, line["mid"])
        ox, oy = core.section_offset(line, point[0] - mx, point[1] - my)
        position = (px + ox, py + oy)
        if self.section is None or side != self.side:
            label = self.label.text().strip() if self.section is not None else ""
            self._drop()
            try:
                self.section = drawing.add_section(
                    self.parent,
                    p1,
                    p2,
                    local,
                    position,
                    label=label or None,
                    points=self.points,
                    depth=self._depth_value(),
                )
            except drawing.DrawingError as exc:
                self.message.setText(str(exc))
                self.section = None
                return
            self.side = side
            if not self.hatch.isChecked():
                self.section.CutSurfaceDisplay = "Hide"
            if self.style.currentText() != drawing.style_of(self.section):
                drawing.set_view_style(self.section, self.style.currentText())
            if not self.show_label.isChecked():
                drawing.set_view_label(self.section, shown=False)
            _apply_auto_marks(self)
            self._sync_fields()
            self.schedule()
        else:
            self.section.X = position[0]
            self.section.Y = position[1]

    def _sync_fields(self):
        self.label.blockSignals(True)
        self.label.setText(self.section.SectionSymbol)
        self.label.blockSignals(False)
        self.scale.blockSignals(True)
        self.scale.setEditText(core.format_scale(drawing.scale_of(self.section)))
        self.scale.blockSignals(False)
        self.kind.setText(drawing.section_kind_of(self.section))

    def _drop(self):
        if self.section is not None and drawing.alive(self.section):
            doomed = drawing.dependents(self.section)
            helpers = [
                h
                for h in (
                    drawing._get(self.section, "CuttingToolWireObject", None),
                    drawing._get(self.section, "SciForgeDepthClip", None),
                )
                if drawing.alive(h)
            ]
            for obj in doomed:
                try:
                    if obj in list(self.page.Views):
                        self.page.removeView(obj)
                except Exception:
                    pass
                self.doc.removeObject(obj.Name)
            for helper in helpers:
                self.doc.removeObject(helper.Name)
        self.section = None

    def _label(self, text):
        text = text.strip().upper()
        if self.section is None or not text:
            return
        self.section.SectionSymbol = text
        self.section.Label = drawing.section_caption(text)
        drawing.apply_caption(self.section)
        self.schedule()

    def _scale(self, text):
        value = core.parse_scale(text)
        if self.section is None or value is None:
            return
        drawing.set_scale(self.section, value)
        self.schedule()

    def _style(self, text):
        if self.section is None or self._closed:
            return
        drawing.set_view_style(self.section, text)
        self.schedule()

    def _depth_value(self):
        mode = self.depth.currentText()
        try:
            value = float(self.distance.text().replace(",", "."))
        except ValueError:
            value = 0.0
        return (mode, value)

    def _depth(self, *_args):
        if self._closed:
            return
        self._depth_rows()
        if self.section is None:
            return
        mode, value = self._depth_value()
        try:
            drawing.set_section_depth(self.section, mode, value)
            self.message.setText("")
        except drawing.DrawingError as exc:
            self.message.setText(str(exc))
            return
        except Exception as exc:
            warn("section depth: %s" % exc)
            return
        self.schedule()

    def _hatch(self, on):
        if self.section is None:
            return
        if on:
            drawing._hatch(self.section)
        else:
            self.section.CutSurfaceDisplay = "Hide"
        self.schedule()

    def accept(self):
        if self.section is None:
            self.message.setText("Draw the cut line and place the section view first.")
            return False
        mode, value = self._depth_value()
        if mode == "Distance" and value <= 0:
            self.message.setText("Type how far behind the cut the section shows (more than 0 mm).")
            return False
        return super().accept()


# ------------------------------------------------------------------ view label and centre marks
def _label_rows(panel, view, with_text=True):
    """Fusion's View Label: its text and whether it shows (the "Show" box). A section's
    or detail's label follows its letter (with_text False: only the box)."""
    text = None
    if with_text:
        text = QtWidgets.QLineEdit(drawing.view_label(view) if view is not None else "")
        text.setObjectName("SciForgeViewLabel")
        panel.layout.addRow("View label", text)
    shown = QtWidgets.QCheckBox("Show the view label")
    shown.setObjectName("SciForgeViewLabelShown")
    shown.setChecked(drawing.label_shown(view) if view is not None else not with_text)
    panel.layout.addRow(shown)

    def changed(*_args):
        target = panel.target_view()
        if target is None or panel._closed:
            return
        drawing.set_view_label(
            target, text=text.text() if text is not None else None, shown=shown.isChecked()
        )
        panel.schedule()

    if text is not None:
        text.textEdited.connect(changed)
    shown.toggled.connect(changed)
    panel.label_text = text
    return shown


def _auto_mark_rows(panel, view):
    """Fusion's Automated Center Marks and Center Lines: which round features of the
    view get them."""
    settings = drawing.auto_mark_settings(view) if view is not None else {}
    row = QtWidgets.QWidget()
    layout = QtWidgets.QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    boxes = {}
    for key, text in (("holes", "Holes"), ("extrudes", "Round Extrudes"), ("cuts", "Round Cuts")):
        box = QtWidgets.QCheckBox(text)
        box.setObjectName("SciForgeAutoMarks_" + key)
        box.setChecked(bool(settings.get(key)))
        box.toggled.connect(lambda _on, p=panel: _apply_auto_marks(p))
        layout.addWidget(box)
        boxes[key] = box
    panel.layout.addRow("Center marks", row)
    return boxes


def _apply_auto_marks(panel):
    try:
        target = panel.target_view()
        if target is None or panel._closed:
            return
        settings = {k: b.isChecked() for k, b in panel.auto_boxes.items()}
        if settings == drawing.auto_mark_settings(target) and not any(settings.values()):
            return
        drawing.set_auto_marks(target, settings)
        panel.schedule()
    except Exception as exc:
        warn("centre marks: %s" % exc)


def _straighten(p1, p2, degrees=3.0):
    """A cut line within a few degrees of level or upright becomes exactly so."""
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    angle = math.degrees(math.atan2(dy, dx)) % 180.0
    if min(angle, 180.0 - angle) < degrees:
        return (p2[0], p1[1])
    if abs(angle - 90.0) < degrees:
        return (p1[0], p2[1])
    return p2


def _selected_views(page):
    found = []
    try:
        for sel in Gui.Selection.getSelectionEx():
            obj = sel.Object
            if (
                drawing.is_view(obj)
                and drawing.same(drawing.page_of(obj), page)
                and obj.Name not in [f.Name for f in found]
            ):
                found.append(obj)
    except Exception:
        pass
    return found


# ------------------------------------------------------------------ Detail View
class DetailPanel(DrawingPanel):
    """Fusion's Detail View: click the circle's centre, then its size, then place the
    detail (twice the parent's scale)."""

    title = "Detail View"
    icon = "dw_detail_view"

    def __init__(self, page, detail=None):
        super().__init__(page, "Detail View" if detail is None else "Edit View")
        self.parent = None
        self.centre = None
        self.radius = None
        self.detail = detail
        self.placed = detail is not None
        self.label = QtWidgets.QLineEdit(detail.Reference if detail is not None else "")
        self.label.setObjectName("SciForgeDrawingLabel")
        self.scale = _combo(
            core.scale_choices(),
            core.format_scale(drawing.scale_of(detail)) if detail is not None else "",
            True,
        )
        self.style = _combo(
            core.STYLES, drawing.style_of(detail) if detail is not None else "Visible Edges"
        )
        self.style.setObjectName("SciForgeDrawingStyle")
        self.layout.addRow("Label", self.label)
        self.layout.addRow("Scale", self.scale)
        self.layout.addRow("Style", self.style)
        self.show_label = _label_rows(self, detail, with_text=False)
        self.auto_boxes = _auto_mark_rows(self, detail)
        self.label.textChanged.connect(self._label)
        self.scale.currentTextChanged.connect(self._scale)
        self.style.currentTextChanged.connect(self._style)
        self.finish_layout()
        if detail is not None:
            self.say("Change the options, then OK.")
        else:
            preselected = _selected_views(page)
            if len(preselected) == 1:
                self._parent(preselected[0])
            else:
                self.say("Click the view to take the detail from.")

    def target_view(self):
        return self.detail

    def _style(self, text):
        if self.detail is None or self._closed:
            return
        drawing.set_view_style(self.detail, text)
        self.schedule()

    def _parent(self, view):
        self.parent = view
        self.say("Click the centre of the detail circle.")

    def on_press(self, point, event):
        if self.placed:
            return True
        if self.parent is None:
            view = view_at(self.page, point)
            if view is None:
                self.message.setText("Click on a view.")
                return True
            self._parent(view)
            return True
        local = drawing.page_to_local(self.parent, point)
        if self.centre is None:
            self.centre = snap_point(self.parent, local, self.tolerance())
            self.say("Move out and click to set the size of the circle.")
            return True
        if self.radius is None:
            radius = math.hypot(local[0] - self.centre[0], local[1] - self.centre[1])
            if radius < 1e-3:
                self.message.setText("Move away from the centre to give the circle a size.")
                return True
            self.radius = radius
            self.clear_overlay()
            self.say("Move the detail view where you want it and click to place it.")
            self.on_move(point, event)
            return True
        self.placed = True
        self.say("Change the options, then OK.")
        return True

    def on_move(self, point, event):
        if self._closed or self.placed or self.parent is None or self.centre is None:
            return
        if self.radius is None:
            self.clear_overlay()
            local = drawing.page_to_local(self.parent, point)
            r = math.hypot(local[0] - self.centre[0], local[1] - self.centre[1])
            s = drawing.scale_of(self.parent)
            self.overlay_circle(drawing.local_to_page(self.parent, self.centre), r * s)
            return
        if self.detail is None:
            self.detail = drawing.add_detail(self.parent, self.centre, self.radius, point)
            if self.style.currentText() != drawing.style_of(self.detail):
                drawing.set_view_style(self.detail, self.style.currentText())
            if not self.show_label.isChecked():
                drawing.set_view_label(self.detail, shown=False)
            _apply_auto_marks(self)
            self.label.blockSignals(True)
            self.label.setText(self.detail.Reference)
            self.label.blockSignals(False)
            self.scale.blockSignals(True)
            self.scale.setEditText(core.format_scale(drawing.scale_of(self.detail)))
            self.scale.blockSignals(False)
            self.schedule()
        else:
            self.detail.X = point[0]
            self.detail.Y = point[1]

    def _label(self, text):
        text = text.strip().upper()
        if self.detail is None or not text:
            return
        self.detail.Reference = text
        self.detail.Label = drawing.detail_caption(self.detail)
        drawing.apply_caption(self.detail)
        self.schedule()

    def _scale(self, text):
        value = core.parse_scale(text)
        if self.detail is None or value is None:
            return
        drawing.set_scale(self.detail, value)
        self.schedule()

    def accept(self):
        if self.detail is None:
            self.message.setText("Click the circle's centre and size, then place the detail.")
            return False
        return super().accept()


# ------------------------------------------------------------------ Break View
class BreakPanel(DrawingPanel):
    """Fusion's Break View: click a view, then the two ends of the part to take out; the
    direction (across or up) follows the view's longer side."""

    title = "Break View"
    icon = "dw_break_view"

    def __init__(self, page):
        super().__init__(page, "Break View")
        self.view = None
        self.a = None
        self.broken = None
        self.gap = QtWidgets.QDoubleSpinBox()
        self.gap.setRange(1.0, 100.0)
        self.gap.setSuffix(" mm")
        self.gap.setValue(10.0)
        self.gap.setObjectName("SciForgeDrawingGap")
        self.layout.addRow("Gap", self.gap)
        self.gap.valueChanged.connect(self._gap)
        self.finish_layout()
        self.say("Click the view to break.")

    def on_press(self, point, event):
        if self.broken is not None:
            return True
        if self.view is None:
            view = view_at(self.page, point)
            if view is None:
                self.message.setText("Click on a view.")
                return True
            if view.TypeId in (drawing.DETAIL, drawing.BROKEN):
                self.message.setText("Pick a base, projected or section view.")
                return True
            self.view = view
            self.say("Click where the break starts.")
            return True
        local = drawing.page_to_local(self.view, point)
        if self.a is None:
            self.a = local
            self.say("Click where the break ends.")
            return True
        try:
            self.broken = drawing.add_break(self.view, self.a, local, self.gap.value())
        except drawing.DrawingError as exc:
            self.message.setText(str(exc))
            return True
        self.clear_overlay()
        self.say("Change the gap, then OK.")
        self.schedule()
        return True

    def on_move(self, point, event):
        if self._closed or self.view is None or self.a is None or self.broken is not None:
            return
        self.clear_overlay()
        half_w, half_h = drawing.view_extent(self.view)
        x, y = drawing.view_position(self.view)
        local = drawing.page_to_local(self.view, point)
        horizontal = abs(local[0] - self.a[0]) >= abs(local[1] - self.a[1])
        for p in (self.a, local):
            q = drawing.local_to_page(self.view, p)
            if horizontal:
                self.overlay_line((q[0], y - half_h - 3), (q[0], y + half_h + 3))
            else:
                self.overlay_line((x - half_w - 3, q[1]), (x + half_w + 3, q[1]))

    def _gap(self, value):
        if self.broken is not None:
            self.broken.Gap = value
            self.schedule()

    def accept(self):
        if self.broken is None:
            self.message.setText("Click the view and the two ends of the break first.")
            return False
        return super().accept()


# ------------------------------------------------------------------ centre marks and lines
class CenterMarkPanel(DrawingPanel):
    """Fusion's Center Mark: click circles and arcs; each gets a mark. Esc or OK ends."""

    title = "Center Mark"
    icon = "dw_center_mark"

    def __init__(self, page):
        super().__init__(page, "Center Mark")
        self.made = []
        self.finish_layout()
        self.say("Click circles or arcs on the views; Enter or Esc when done.")

    def on_press(self, point, event):
        view, name, _local = pick_at(
            self.page, point, self.tolerance(), want_vertex=False, curve="circle"
        )
        info = drawing.edge_info(view, name) if view is not None and name else None
        if info is None or info["kind"] not in ("circle", "arc"):
            self.message.setText("Click on a circle or an arc.")
            return True
        self.message.setText("")
        if any(
            abs(m["c"][0] - info["center"][0]) < 1e-6 and abs(m["c"][1] - info["center"][1]) < 1e-6
            for m in drawing.center_marks(view)
        ):
            self.message.setText("That circle already has a centre mark.")
            return True
        drawing.add_center_mark(view, name)
        self.made.append(view.Name)
        view.requestPaint()
        self.say(
            "%d centre mark%s. Click more, or Enter / Esc."
            % (len(self.made), "" if len(self.made) == 1 else "s")
        )
        self.schedule()
        return True

    def escape(self):
        taskui.press_dialog_button("accept")


class CenterlinePanel(DrawingPanel):
    """Fusion's Centerline: click two parallel edges; the line goes midway between them."""

    title = "Centerline"
    icon = "dw_centerline"

    def __init__(self, page):
        super().__init__(page, "Centerline")
        self.first = None
        self.made = 0
        self.finish_layout()
        self.say("Click the first of two edges that run side by side.")

    def on_press(self, point, event):
        view, name, _local = pick_at(
            self.page, point, self.tolerance(), want_vertex=False, curve="line"
        )
        info = drawing.edge_info(view, name) if view is not None and name else None
        if info is None or info["kind"] != "line":
            self.message.setText("Click a straight edge.")
            return True
        self.message.setText("")
        if self.first is None or self.first[0] is not view:
            self.first = (view, name)
            self.say("Click the second edge.")
            return True
        try:
            drawing.add_centerline(view, self.first[1], name)
        except drawing.DrawingError as exc:
            self.message.setText(str(exc))
            return True
        self.first = None
        self.made += 1
        self.say("Centreline added. Click two more edges, or Enter / Esc.")
        self.schedule()
        return True

    def escape(self):
        taskui.press_dialog_button("accept")


# ------------------------------------------------------------------ Dimension
class DimensionPanel(DrawingPanel):
    """Fusion's Dimension: click an edge, a circle, or two things; the dimension follows
    the mouse; a click on the sheet places it. The command stays for the next one."""

    title = "Dimension"
    icon = "dw_dimension"
    FORCED = {
        "linear": ("DistanceX", "DistanceY"),
        "aligned": ("Distance",),
        "angular": ("Angle",),
        "radius": ("Radius",),
        "diameter": ("Diameter",),
    }

    def __init__(self, page, forced=None):
        super().__init__(page, "Dimension")
        self.forced = forced
        self.picks = []  # [(view, name, info)]
        self.dim = None
        self.made = []
        self.finish_layout()
        self.say(self._first_hint())

    def _first_hint(self):
        return {
            "radius": "Click an arc or a circle.",
            "diameter": "Click a circle or an arc.",
            "angular": "Click two straight edges.",
        }.get(self.forced, "Click an edge, a circle, or a point; Esc when done.")

    def on_press(self, point, event):
        view, name, local = pick_at(self.page, point, self.tolerance())
        if name is not None and drawing.is_isometric(view):
            self.message.setText(
                "An isometric view cannot be dimensioned: its lengths are drawn shorter "
                "than they are. Dimension a front, top or side view."
            )
            return True
        if (
            name is not None
            and (not self.picks or drawing.same(self.picks[0][0], view))
            and len(self.picks) < 2
        ):
            info = drawing.edge_info(view, name)
            if info is not None:
                self._pick(view, name, info, point)
                return True
        if name is not None and self.picks and not drawing.same(self.picks[0][0], view):
            self.message.setText("A dimension measures within one view: pick from the same view.")
            return True
        if self.dim is not None:
            self._place(point)
            return True
        if not self.picks:
            self.message.setText("Click on an edge, a circle or a point of a view.")
        return True

    def _pick(self, view, name, info, point):
        self.message.setText("")
        self.picks.append((view, name, info))
        Gui.Selection.addSelection(self.doc.Name, view.Name, name)
        self._rebuild(point)

    def _infer(self, place_local=None):
        infos = [p[2] for p in self.picks]
        result = core.infer_dimension(infos, place_local)
        if "type" in result and self.forced:
            allowed = self.FORCED[self.forced]
            if result["type"] not in allowed:
                if self.forced == "linear" and result["type"] == "Distance":
                    result["type"] = "DistanceX"
                elif self.forced == "aligned" and result["type"] in ("DistanceX", "DistanceY"):
                    result["type"] = "Distance"
                elif self.forced == "radius" and result["type"] == "Diameter":
                    result["type"] = "Radius"
                elif self.forced == "diameter" and result["type"] == "Radius":
                    result["type"] = "Diameter"
                elif self.forced == "angular" and len(infos) < 2:
                    return {"need": "more"}
                else:
                    return {"error": "That is not something a %s dimension measures." % self.forced}
        return result

    def _refs(self, result):
        view = self.picks[0][0]
        refs = []
        for i, (_v, name, info) in enumerate(self.picks):
            if i in result.get("use_centers", []):
                centre = drawing.center_vertex(view, info["center"])
                if centre is None:
                    return None
                refs.append(centre)
            else:
                refs.append(name)
        return refs

    def _rebuild(self, point):
        view = self.picks[0][0]
        place_local = drawing.page_to_local(view, point)
        result = self._infer(place_local)
        if "error" in result:
            self.message.setText(result["error"])
            self._clear_picks(keep_message=True)
            return
        if "need" in result:
            self.say("Click the second point or edge.")
            return
        refs = self._refs(result)
        if refs is None:
            self.message.setText(
                "Could not find that circle's centre point: pick its edge instead."
            )
            self._clear_picks(keep_message=True)
            return
        self._drop_dim()
        try:
            self.dim = drawing.add_dimension(view, refs, result["type"], point)
        except Exception as exc:
            self.message.setText(str(exc))
            self._clear_picks(keep_message=True)
            return
        self.say(
            "Move the dimension where you want it and click to place it (or click a second edge)."
        )
        self.schedule()

    def on_move(self, point, event):
        if self._closed or self.dim is None or not drawing.alive(self.dim):
            return
        view = self.picks[0][0]
        result = self._infer(drawing.page_to_local(view, point))
        if "type" in result and result["type"] != self.dim.Type:
            self.dim.Type = result["type"]
            self.dim.FormatSpec = core.dimension_format(
                drawing.units_of(self.page), drawing.standard_of(self.page), result["type"]
            )
            self.schedule()
        drawing.place_dimension(self.dim, point)

    def _place(self, point):
        drawing.place_dimension(self.dim, point)
        self.doc.recompute()
        self.made.append(self.dim.Name)
        self.dim = None
        self.picks = []
        Gui.Selection.clearSelection()
        taskui._end_transaction(self.doc)
        self.doc.openTransaction("Dimension")
        self.say("Placed. " + self._first_hint())

    def _drop_dim(self):
        if self.dim is not None and drawing.alive(self.dim):
            name = self.dim.Name
            try:
                self.page.removeView(self.dim)
            except Exception:
                pass
            self.doc.removeObject(name)
        self.dim = None

    def _clear_picks(self, keep_message=False):
        self._drop_dim()
        self.picks = []
        Gui.Selection.clearSelection()
        if not keep_message:
            self.message.setText("")

    def escape(self):
        if self.picks or self.dim is not None:
            self._clear_picks()
            self.say(self._first_hint())
            return
        taskui.press_dialog_button("accept")

    def accept(self):
        self._drop_dim()
        return super().accept()


# ------------------------------------------------------------------ Text
class TextPanel(DrawingPanel):
    """Fusion's Text: click two corners of the text box, then type."""

    title = "Text"
    icon = "dw_text"

    def __init__(self, page, note=None):
        super().__init__(page, "Text" if note is None else "Edit Text")
        self.corner = None
        self.note = note
        self.text = QtWidgets.QPlainTextEdit("\n".join(note.Text) if note is not None else "")
        self.text.setObjectName("SciForgeDrawingText")
        self.text.setMaximumHeight(90)
        self.size = QtWidgets.QDoubleSpinBox()
        self.size.setRange(1.0, 50.0)
        self.size.setSuffix(" mm")
        self.size.setValue(float(note.TextSize) if note is not None else 3.5)
        self.size.setObjectName("SciForgeDrawingTextHeight")
        self.layout.addRow("Text", self.text)
        self.layout.addRow("Height", self.size)
        self.text.textChanged.connect(self._typed)
        self.size.valueChanged.connect(self._typed)
        self.finish_layout()
        self.say(
            "Click the first corner of the text box."
            if note is None
            else "Change the text, then OK."
        )

    def on_press(self, point, event):
        if self.note is not None:
            return True
        if self.corner is None:
            self.corner = point
            self.pressed = point
            self.say("Click the opposite corner (or drag to it).")
            return True
        return self._frame(point)

    pressed = None

    def on_release(self, point, event):
        """Fusion: the text box can also be dragged open."""
        start, self.pressed = self.pressed, None
        if self.note is None and start is not None and self.corner is not None:
            if math.hypot(point[0] - start[0], point[1] - start[1]) > 1.5:
                return self._frame(point)
        return True

    def _frame(self, point):
        x0, y0 = self.corner
        x1, y1 = point
        width = abs(x1 - x0)
        centre = ((x0 + x1) / 2.0, (y0 + y1) / 2.0)
        lines = self.text.toPlainText().splitlines() or ["Text"]
        self.note = drawing.add_text(self.page, lines, centre, self.size.value(), width or None)
        self.clear_overlay()
        self.say("Type the text, then OK.")
        self.schedule()
        try:
            self.text.setFocus()
            if not self.text.toPlainText():
                self.text.setPlainText("")
        except RuntimeError:
            pass
        return True

    def on_move(self, point, event):
        if self._closed or self.corner is None or self.note is not None:
            return
        self.clear_overlay()
        self.overlay_rect(self.corner[0], self.corner[1], point[0], point[1])

    def _typed(self, *_args):
        if self.note is None or self._closed:
            return
        lines = self.text.toPlainText().splitlines() or [""]
        self.note.Text = lines
        self.note.TextSize = self.size.value()
        self.schedule()

    def on_key(self, key, event):
        if key == QtCore.Qt.Key_Escape:
            _later(self.escape)
        return True

    def accept(self):
        if self.note is None:
            self.message.setText("Click two corners of the text box first.")
            return False
        if not self.text.toPlainText().strip():
            self.message.setText("Type some text (or Cancel).")
            return False
        return super().accept()


# ------------------------------------------------------------------ Parts list and balloons
class TablePanel(DrawingPanel):
    """Fusion's Table (parts list): pick the view, then click where the table's top left
    corner goes; balloons appear on the view."""

    title = "Table"
    icon = "dw_table"

    def __init__(self, page):
        super().__init__(page, "Parts List")
        if drawing.parts_list_of(page) is not None:
            raise drawing.DrawingError("This drawing already has a parts list.")
        if not drawing.base_views(page):
            raise drawing.DrawingError(
                "Place a base view first: the parts list lists what it shows."
            )
        self.view = _single_base(page)
        self.table = None
        self.layout_size = None
        self.finish_layout()
        if self.view is not None:
            self._use(self.view)
        else:
            self.say("Click the view whose components the table lists.")

    def _use(self, view):
        self.view = view
        rows = drawing.parts_rows_for(view)
        layout = core.table_layout(rows)
        self.layout_size = (layout["width"], layout["height"])
        self.say("Move the table where you want it and click to place its top left corner.")

    def on_press(self, point, event):
        if self.table is not None:
            return True
        if self.view is None:
            view = view_at(self.page, point)
            if view is None:
                self.message.setText("Click on a view.")
                return True
            self._use(view)
            return True
        try:
            self.table, balloons = drawing.add_parts_list(self.page, self.view, point)
        except drawing.DrawingError as exc:
            self.message.setText(str(exc))
            return True
        self.clear_overlay()
        self.say(
            "Parts list with %d row%s and %d balloon%s. OK to finish."
            % (
                len(drawing.table_rows(self.table)),
                "" if len(drawing.table_rows(self.table)) == 1 else "s",
                len(balloons),
                "" if len(balloons) == 1 else "s",
            )
        )
        self.schedule()
        return True

    def on_move(self, point, event):
        if self._closed or self.view is None or self.table is not None or self.layout_size is None:
            return
        self.clear_overlay()
        w, h = self.layout_size
        self.overlay_rect(point[0], point[1], point[0] + w, point[1] - h)

    def accept(self):
        if self.table is None:
            self.message.setText("Click where the table goes first.")
            return False
        return super().accept()


class BalloonPanel(DrawingPanel):
    """Fusion's Balloon: click a component's edge on a view, then where the balloon
    goes; its number is the component's item in the parts list."""

    title = "Balloon"
    icon = "dw_balloon"

    def __init__(self, page):
        super().__init__(page, "Balloon")
        if drawing.parts_list_of(page) is None:
            raise drawing.DrawingError(
                "Balloons number the parts list's rows: make the parts list first "
                "(TABLES > Table)."
            )
        self.origin = None
        self.made = []
        self.finish_layout()
        self.say("Click an edge of a component on a view.")

    def on_press(self, point, event):
        if self.origin is None:
            view, name, local = pick_at(self.page, point, self.tolerance(), want_vertex=False)
            if view is None or name is None:
                self.message.setText("Click on an edge of a component.")
                return True
            body = drawing.component_at(view, local)
            item = drawing.item_for_body(self.page, body) if body is not None else None
            if item is None:
                self.message.setText("That is not one of the parts list's components.")
                return True
            self.message.setText("")
            self.origin = (view, point, item)
            self.say("Click where balloon %s goes." % item)
            return True
        view, origin, item = self.origin
        self.made.append(drawing.add_balloon(view, origin, point, item).Name)
        self.origin = None
        self.clear_overlay()
        self.say("Balloon %s placed. Click the next component, or Enter / Esc." % item)
        self.schedule()
        return True

    def on_move(self, point, event):
        if self._closed or self.origin is None:
            return
        self.clear_overlay()
        self.overlay_line(self.origin[1], point, dashed=False)
        self.overlay_circle(point, 4.0)

    def escape(self):
        if self.origin is not None:
            self.origin = None
            self.clear_overlay()
            self.say("Click an edge of a component on a view.")
            return
        taskui.press_dialog_button("accept")


# ------------------------------------------------------------------ editing views, title block
class EditViewPanel(DrawingPanel):
    """Fusion's Drawing View dialog for a projected or broken view: style and scale."""

    title = "Edit View"
    icon = "dw_base_view"

    def __init__(self, page, view):
        super().__init__(page, "Edit View")
        self.view = view
        self.style = _combo(core.STYLES, drawing.style_of(view))
        self.style.setObjectName("SciForgeDrawingStyle")
        self.layout.addRow("Style", self.style)
        self.style.currentTextChanged.connect(self._style)
        self.gap = None
        if view.TypeId == drawing.BROKEN:
            self.gap = QtWidgets.QDoubleSpinBox()
            self.gap.setRange(1.0, 100.0)
            self.gap.setSuffix(" mm")
            self.gap.setValue(float(view.Gap))
            self.layout.addRow("Gap", self.gap)
            self.gap.valueChanged.connect(self._gap)
        self.show_label = _label_rows(self, view)
        self.auto_boxes = _auto_mark_rows(self, view)
        self.finish_layout()
        self.say("Change the options, then OK.")

    def target_view(self):
        return self.view

    def _style(self, text):
        drawing.set_view_style(self.view, text)
        self.schedule()

    def _gap(self, value):
        self.view.Gap = value
        self.schedule()


def edit_view(view):
    """Double-click on a view: the right dialog for it (Fusion: the Drawing View dialog)."""
    if not commands.finish_open_dialog():
        return None
    page = drawing.page_of(view)
    if page is None:
        return None
    try:
        if drawing.kind(view) == "BaseView":
            return BaseViewPanel(page, view).show()
        if drawing.is_section(view):
            return SectionPanel(page, view).show()
        if view.TypeId == drawing.DETAIL:
            return DetailPanel(page, view).show()
        return EditViewPanel(page, view).show()
    except Exception as exc:
        warn("edit view: %s" % exc)
    return None


class TitleBlockPanel(DrawingPanel):
    """Fusion: double-click the title block to fill it in. A field typed here stops
    following the design."""

    title = "Title Block"
    icon = "dw_title_block"

    def __init__(self, page):
        super().__init__(page, "Edit Title Block")
        if drawing.title_template(page) is None or not getattr(page, "SciForgeTitleBlock", True):
            raise drawing.DrawingError("This sheet has no title block.")
        values = drawing.title(page)
        self.fields = {}
        for key in core.TITLE_KEYS:
            field = QtWidgets.QLineEdit(values.get(key, ""))
            field.setObjectName("SciForgeTitle_" + key)
            self.fields[key] = field
            self.layout.addRow(core.TITLE_CAPTIONS.get(key, key), field)
            field.textEdited.connect(lambda text, k=key: self._edited(k, text))
        self.finish_layout()
        self.say("Type into the fields; OK keeps them.")

    def _edited(self, key, text):
        from . import drawing_sheets

        drawing_sheets.set_title_everywhere(self.page, {key: text})
        self.schedule()

    @classmethod
    def start(cls, page):
        if not commands.finish_open_dialog():
            return None
        try:
            return cls(page).show()
        except drawing.DrawingError as exc:
            commands.tell(str(exc))
        return None


# ------------------------------------------------------------------ delete
def delete_selected():
    page = active_page()
    if page is None:
        return False
    if Gui.Control.activeDialog():
        commands.tell("Finish the open command first (OK or Cancel), then delete.")
        return False
    targets = []
    for sel in Gui.Selection.getSelectionEx("", 0):
        obj = sel.Object
        owner = drawing.page_of(obj)
        if owner is not None and owner.Name == page.Name and obj.Name != page.Name:
            if obj.Name not in [t.Name for t in targets]:
                targets.append(obj)
    if not targets:
        log(
            "delete: nothing of %s in the selection %s"
            % (
                page.Name,
                [(x.ObjectName, x.SubElementNames) for x in Gui.Selection.getSelectionEx("", 0)],
            )
        )
        commands.tell("Select views, dimensions, text or balloons on the sheet, then Delete.")
        return False
    doc = page.Document
    Gui.Selection.clearSelection()
    doc.openTransaction("Delete")
    try:
        removed = drawing.delete_objects(doc, targets)
    except Exception as exc:
        taskui._end_transaction(doc, abort=True)
        warn("drawing delete: %s" % exc)
        return False
    taskui._end_transaction(doc)
    doc.recompute()
    log("deleted from %s: %s" % (page.Label, ", ".join(removed)))
    return True


# ------------------------------------------------------------------ export
class ExportDialog(QtWidgets.QDialog):
    """Export PDF / DXF: a name, a folder and whether to open the file afterwards."""

    last = None

    def __init__(self, page, kind):
        super().__init__(Gui.getMainWindow())
        type(self).last = self
        self.page = page
        self.kind = kind
        self.setObjectName("SciForgeDrawingExport")
        self.setWindowTitle("Export %s" % kind.upper())
        from . import drawing_sheets

        layout = QtWidgets.QFormLayout(self)
        self.name = QtWidgets.QLineEdit(drawing_sheets.main_page(page).Label)
        self.name.setObjectName("SciForgeDrawingExportName")
        # Fusion: All Sheets in one PDF, or the current sheet; a DXF per sheet
        self.sheets = _combo(["All Sheets", "Current Sheet"])
        self.sheets.setObjectName("SciForgeDrawingExportSheets")
        self.folder = QtWidgets.QLineEdit(_default_folder(page.Document))
        self.folder.setObjectName("SciForgeDrawingExportFolder")
        browse = QtWidgets.QPushButton("Browse...")
        browse.clicked.connect(self._browse)
        row = QtWidgets.QHBoxLayout()
        row.addWidget(self.folder, 1)
        row.addWidget(browse)
        self.open_after = QtWidgets.QCheckBox("Open the %s afterwards" % kind.upper())
        self.open_after.setChecked(kind == "pdf")
        self.open_after.setObjectName("SciForgeDrawingExportOpen")
        self.message = QtWidgets.QLabel("")
        self.message.setWordWrap(True)
        self.message.setStyleSheet("color: #ff8a80;")
        layout.addRow("Name", self.name)
        layout.addRow("Sheets", self.sheets)
        layout.addRow("Location", row)
        layout.addRow(self.open_after)
        layout.addRow(self.message)
        buttons = QtWidgets.QDialogButtonBox()
        self.export_button = buttons.addButton("Export", QtWidgets.QDialogButtonBox.AcceptRole)
        self.export_button.setObjectName("SciForgeDrawingExportButton")
        cancel = buttons.addButton(QtWidgets.QDialogButtonBox.Cancel)
        self.export_button.clicked.connect(self._export)
        cancel.clicked.connect(self.reject)
        layout.addRow(buttons)
        self.path = None
        self.paths = []

    def _browse(self):
        try:
            folder = QtWidgets.QFileDialog.getExistingDirectory(
                self, "Location", self.folder.text()
            )
            if folder:
                self.folder.setText(folder)
        except Exception as exc:
            warn("export folder: %s" % exc)

    def _export(self):
        try:
            name = self.name.text().strip()
            folder = os.path.expanduser(self.folder.text().strip())
            if not name:
                self.message.setText("Give the file a name.")
                return
            if not folder:
                self.message.setText("Choose where the file goes.")
                return
            if not name.lower().endswith("." + self.kind):
                name += "." + self.kind
            path = os.path.join(folder, name)
            from . import drawing_sheets

            which = "all" if self.sheets.currentIndex() == 0 else "current"
            if self.kind == "pdf":
                drawing_sheets.export_pdf(self.page, path, which)
                self.paths = [path]
            else:
                self.paths = drawing_sheets.export_dxf(self.page, path, which)
                path = self.paths[0]
            self.path = path
            log("exported %s" % ", ".join(self.paths))
            if self.open_after.isChecked():
                OPENER["open"](path)
            self.accept()
            commands.tell("Exported %s" % path)
        except Exception as exc:
            self.message.setText("Could not export: %s" % exc)
            warn("export %s: %s" % (self.kind, exc))


def _default_folder(doc):
    try:
        if doc.FileName:
            return os.path.dirname(doc.FileName)
    except Exception:
        pass
    docs = os.path.join(os.path.expanduser("~"), "Documents")
    return docs if os.path.isdir(docs) else os.path.expanduser("~")


def export(kind):
    page = _need_page()
    if page is None or not commands.finish_open_dialog():
        return None
    dialog = ExportDialog(page, kind)
    dialog.show()
    return dialog


# ------------------------------------------------------------------ workspace switcher and browser
def fill_workspace_menu(menu):
    """The Drawing entry of the workspace button: From Design, then the design's drawings."""
    doc = App.ActiveDocument
    new = menu.addAction(QtGui.QIcon(ui_icon_path("dw_new")), "From Design...")
    new.triggered.connect(lambda: _later(Gui.runCommand, "SciForge_NewDrawing"))
    new.setEnabled(doc is not None)
    pages = drawing.drawings(doc) if doc is not None else []
    if pages:
        menu.addSeparator()
    for page in pages:
        action = menu.addAction(QtGui.QIcon(ui_icon_path("dw_base_view")), page.Label)
        action.triggered.connect(lambda _=False, p=page: _later(open_drawing, p))


# ------------------------------------------------------------------ commands
class _Base:
    title = ""
    tip = ""
    icon = ""

    def GetResources(self):
        return {"MenuText": self.title, "ToolTip": self.tip, "Pixmap": ui_icon_path(self.icon)}

    def IsActive(self):
        return active_page() is not None

    def Activated(self):
        try:
            self.run()
        except Exception as exc:
            warn("%s failed: %s" % (self.title, exc))

    def run(self):
        pass


class NewDrawingCommand(_Base):
    title = "New Drawing"
    tip = "A drawing of this design: views, dimensions and a title block on a sheet"
    icon = "dw_new"

    def IsActive(self):
        return App.ActiveDocument is not None

    def run(self):
        doc = App.ActiveDocument
        if doc is None:
            commands.tell("Open or make a design first.")
            return
        if not drawing.design_bodies(doc):
            commands.tell(
                "There is nothing to draw yet: the design has no solid bodies. Make a body "
                "first, then File > New Drawing."
            )
            return
        if active_page() is not None:
            show_design(doc)
        if not commands.finish_open_dialog():
            return
        CreateDrawingPanel(doc)
        Gui.Control.showDialog(CreateDrawingPanel.last)


class BaseViewCommand(_Base):
    title = "Base View"
    tip = "The first view of the design on the sheet"
    icon = "dw_base_view"

    def run(self):
        page = _need_page()
        if page is not None:
            _start(BaseViewPanel)


class ProjectedViewCommand(_Base):
    title = "Projected View"
    tip = "Views made from the base view: move round it and click"
    icon = "dw_projected_view"

    def run(self):
        _start(ProjectedPanel)


class SectionViewCommand(_Base):
    title = "Section View"
    tip = "Cut a view along a line and show the cut"
    icon = "dw_section_view"

    def run(self):
        _start(SectionPanel)


class DetailViewCommand(_Base):
    title = "Detail View"
    tip = "A circle of a view, drawn larger"
    icon = "dw_detail_view"

    def run(self):
        _start(DetailPanel)


class BreakViewCommand(_Base):
    title = "Break View"
    tip = "Leave out the middle of a long view"
    icon = "dw_break_view"

    def run(self):
        _start(BreakPanel)


class CenterMarkCommand(_Base):
    title = "Center Mark"
    tip = "Cross lines at the centre of circles and arcs"
    icon = "dw_center_mark"

    def run(self):
        _start(CenterMarkPanel)


class CenterlineCommand(_Base):
    title = "Centerline"
    tip = "A centre line midway between two parallel edges"
    icon = "dw_centerline"

    def run(self):
        _start(CenterlinePanel)


class DimensionCommand(_Base):
    title = "Dimension"
    tip = "Lengths, distances, angles, radii and diameters: the kind follows what you pick (D)"
    icon = "dw_dimension"
    forced = None

    def run(self):
        _start(DimensionPanel, self.forced)


class LinearDimensionCommand(DimensionCommand):
    title = "Linear Dimension"
    tip = "A horizontal or vertical distance"
    forced = "linear"


class AlignedDimensionCommand(DimensionCommand):
    title = "Aligned Dimension"
    tip = "A distance along the picked edge or points"
    forced = "aligned"


class AngularDimensionCommand(DimensionCommand):
    title = "Angular Dimension"
    tip = "The angle between two edges"
    forced = "angular"


class RadiusDimensionCommand(DimensionCommand):
    title = "Radius Dimension"
    tip = "The radius of an arc or circle"
    forced = "radius"


class DiameterDimensionCommand(DimensionCommand):
    title = "Diameter Dimension"
    tip = "The diameter of a circle or arc"
    forced = "diameter"


class TextCommand(_Base):
    title = "Text"
    tip = "A note on the sheet: click two corners, then type"
    icon = "dw_text"

    def run(self):
        _start(TextPanel)


class TableCommand(_Base):
    title = "Table"
    tip = "A parts list of the components a view shows, with balloons"
    icon = "dw_table"

    def run(self):
        _start(TablePanel)


class BalloonCommand(_Base):
    title = "Balloon"
    tip = "A numbered balloon pointing at a component (needs the parts list)"
    icon = "dw_balloon"

    def run(self):
        _start(BalloonPanel)


class EditViewCommand(_Base):
    title = "Edit View"
    tip = "Change the selected view (or double-click a view)"
    icon = "dw_base_view"

    def run(self):
        page = _need_page()
        if page is None:
            return
        views = _selected_views(page)
        if len(views) != 1:
            commands.tell("Select one view on the sheet (or double-click it).")
            return
        edit_view(views[0])


class TitleBlockCommand(_Base):
    title = "Title Block"
    tip = "Fill in the title block (or double-click it)"
    icon = "dw_title_block"

    def run(self):
        page = _need_page()
        if page is not None:
            TitleBlockPanel.start(page)


class DeleteCommand(_Base):
    title = "Delete"
    tip = "Delete what is selected on the sheet (a view takes its dimensions along) (Del)"
    icon = "delete"

    def run(self):
        delete_selected()


class ExportPdfCommand(_Base):
    title = "Export PDF"
    tip = "The sheet as a PDF file"
    icon = "dw_export_pdf"

    def run(self):
        export("pdf")


class ExportDxfCommand(_Base):
    title = "Export DXF"
    tip = "The sheet as a DXF file (for CAD and laser cutters)"
    icon = "dw_export_dxf"

    def run(self):
        export("dxf")


COMMANDS = {
    "SciForge_NewDrawing": NewDrawingCommand,
    "SciForge_DrawingBaseView": BaseViewCommand,
    "SciForge_DrawingProjectedView": ProjectedViewCommand,
    "SciForge_DrawingSectionView": SectionViewCommand,
    "SciForge_DrawingDetailView": DetailViewCommand,
    "SciForge_DrawingBreakView": BreakViewCommand,
    "SciForge_DrawingCenterMark": CenterMarkCommand,
    "SciForge_DrawingCenterline": CenterlineCommand,
    "SciForge_DrawingDimension": DimensionCommand,
    "SciForge_DrawingLinearDimension": LinearDimensionCommand,
    "SciForge_DrawingAlignedDimension": AlignedDimensionCommand,
    "SciForge_DrawingAngularDimension": AngularDimensionCommand,
    "SciForge_DrawingRadiusDimension": RadiusDimensionCommand,
    "SciForge_DrawingDiameterDimension": DiameterDimensionCommand,
    "SciForge_DrawingText": TextCommand,
    "SciForge_DrawingTable": TableCommand,
    "SciForge_DrawingBalloon": BalloonCommand,
    "SciForge_DrawingEditView": EditViewCommand,
    "SciForge_DrawingTitleBlock": TitleBlockCommand,
    "SciForge_DrawingDelete": DeleteCommand,
    "SciForge_DrawingExportPDF": ExportPdfCommand,
    "SciForge_DrawingExportDXF": ExportDxfCommand,
}
