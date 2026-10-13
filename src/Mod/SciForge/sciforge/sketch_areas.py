# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's profile picking inside an open sketch (the rules: sketch_areas_core.py).

In Fusion you click inside a closed area of the sketch you are drawing (not on a curve,
a point or a dimension) and that area (profile) is selected; Ctrl or Shift + click adds
more, a second click drops one, Esc or a click on empty space drops them all. E or Q
then extrudes exactly the selected areas.

FreeCAD's sketch can only select its own areas once it is closed ("InternalFaceN"), so
SciForge keeps the picks of the open sketch itself, as a point well inside each picked
area. They are drawn over the profile shading of the sketch (sketch_mode.ProfileShading):
picked areas in a stronger blue, the area under the mouse a little lighter. When E or Q
closes the sketch, profiles() finds the area of the closed sketch that holds each point.

Mouse events come from the sketch's view filter (sketch_mode._ViewFilter); everything that
looks at the sketch runs later from a Qt timer, never inside FreeCAD's own click handling.
"""

import FreeCAD as App
import FreeCADGui as Gui

from . import sketch_areas_core as core
from . import warn
from .compat import QtCore

PICKED = (0.12, 0.53, 0.90)  # the picked-profile blue of the Extrude dialog (profile_pick)
PICKED_TRANSPARENCY = 0.35
HOVER = (0.55, 0.82, 1.0)
HOVER_TRANSPARENCY = 0.55
CLICK_SLOP = 4  # pixels: a press and a release this close are a click (not a box selection)
NEAR_PX = 5  # pixels: a click this close to a curve or a point is a click on that curve
HOVER_MS = 40


def _waiting():
    """True while a SciForge sketch command waits for curves to be clicked (Mirror,
    patterns, Offset...) or the circumscribed polygon runs: clicks are theirs."""
    try:
        from . import sketch_mode, sketch_pick_ui, sketch_tools_ui

        if sketch_pick_ui._state.get("waiter") is not None:
            return True
        if getattr(sketch_tools_ui._WaitForCurve, "current", None) is not None:
            return True
        if sketch_mode._state.get("polygon"):
            return True
    except Exception:
        pass
    return False


class AreaPicker:
    """The picked and the hovered areas of one open sketch (SketchSession.areas)."""

    def __init__(self, session):
        from pivy import coin

        self.coin = coin
        self.session = session
        self.picks = []  # (x, y) sketch mm: a point inside each picked area, in pick order
        self.hovered = None  # index of the area under the mouse
        self.regions = []  # sketch_areas_core.Region per shaded area
        self.faces = []  # the same areas as Part faces (sketch coordinates; None: a text)
        self.text_keys = {}  # region index -> the sketch text it is (text_ui: one area)
        self._press = None  # (position, modifiers) of a left press that may be a pick
        self._mouse = None  # last mouse position over the view (widget pixels)
        self._curves = None  # the sketch's curves and points as one shape (for "on a curve")
        self.root = coin.SoSeparator()
        self.root.setName("SciForgeSketchPickedProfiles")
        offset = coin.SoPolygonOffset()  # in front of the plain shading (which is at -1)
        offset.factor = -2.0
        offset.units = -2.0
        self.root.addChild(offset)
        self.picked_layer = self._layer(PICKED, PICKED_TRANSPARENCY)
        self.hover_layer = self._layer(HOVER, HOVER_TRANSPARENCY)
        session.shading.root.addChild(self.root)
        self._hover_timer = QtCore.QTimer()
        self._hover_timer.setSingleShot(True)
        self._hover_timer.setInterval(HOVER_MS)
        self._hover_timer.timeout.connect(self._hover)

    def _layer(self, color, transparency):
        coin = self.coin
        sep = coin.SoSeparator()
        material = coin.SoMaterial()
        material.diffuseColor.setValue(*color)
        material.emissiveColor.setValue(*[c * 0.6 for c in color])
        material.transparency.setValue(transparency)
        coords = coin.SoCoordinate3()
        faces = coin.SoIndexedFaceSet()
        sep.addChild(material)
        sep.addChild(coords)
        sep.addChild(faces)
        self.root.addChild(sep)
        return coords, faces

    # -- the areas -----------------------------------------------------------------------
    def refresh(self, shaded):
        """The shading was redrawn: shaded = [(face, points, triangles)] per area, in
        sketch coordinates. Picks whose area is gone are dropped."""
        try:
            self.faces = [face for face, _p, _t in shaded]
            self.regions = [core.Region(points, triangles) for _f, points, triangles in shaded]
            # Fusion: a sketch text is one profile (all its letters), picked like an area
            self.text_keys = {}
            for obj, points, triangles in _text_areas(self.session):
                self.text_keys[len(self.regions)] = obj
                self.faces.append(None)
                self.regions.append(core.Region(points, triangles))
            self.picks = core.keep_valid(self.picks, self.regions)
            self.hovered = None
            self._curves = None
            self._draw()
        except Exception as exc:
            warn("sketch areas: %s" % exc)

    def points(self):
        """The picked areas (a point inside each, sketch mm), in pick order."""
        return list(core.keep_valid(self.picks, self.regions))

    def picked_indices(self):
        return core.picked_regions(self.picks, self.regions)

    def clear(self):
        """Esc, Show Profile off: no area is picked any more."""
        if self.picks or self.hovered is not None:
            self.picks = []
            self.hovered = None
            self._draw()

    def _set(self, picks):
        self.picks = picks
        self._draw()

    def _draw(self):
        picked = core.picked_regions(self.picks, self.regions)
        self._fill(self.picked_layer, picked)
        hover = self.hovered
        self._fill(self.hover_layer, [hover] if hover is not None and hover not in picked else [])

    def _fill(self, layer, indices):
        coords, faces = layer
        points, index = [], []
        for i in indices:
            if not 0 <= i < len(self.regions):
                continue
            region = self.regions[i]
            base = len(points)
            points += [(x, y, 0.0) for x, y in region.points]
            for a, b, c in region.triangles:
                index += [base + a, base + b, base + c, -1]
        coords.point.setNum(0)
        faces.coordIndex.setNum(0)
        if points:
            coords.point.setValues(0, len(points), points)
            faces.coordIndex.setValues(0, len(index), index)

    # -- can areas be clicked now ----------------------------------------------------------
    def _usable(self):
        """No drawing tool runs, no value box is open, no command waits for curves and the
        profiles are shown (Show Profile in the palette)."""
        session = self.session
        if session.closed or not session.shading.visible or session.editor is not None:
            return False
        gl = session.gl
        if gl is None or gl.cursor().shape() != QtCore.Qt.ArrowCursor:
            return False  # FreeCAD's drawing tools show their own cursor
        return not _waiting()

    def _sketch_item_under_mouse(self):
        """True if FreeCAD lights up a curve, point, dimension or axis of this sketch."""
        try:
            pre = Gui.Selection.getPreselection()
            if getattr(pre, "ObjectName", "") != self.session.name:
                return False
            if getattr(pre, "DocumentName", self.session.doc_name) != self.session.doc_name:
                return False
            return any(name for name in pre.SubElementNames)
        except Exception:
            return False

    def _sketch_point(self, pos):
        """Sketch (x, y) under widget pixel `pos`, or None."""
        from . import profile_pick

        session = self.session
        gl = session.gl
        ratio = gl.devicePixelRatioF()
        coin_pos = (int(pos.x() * ratio), int((gl.height() - pos.y() - 1) * ratio))
        placement = session.sketch.getGlobalPlacement()
        normal = placement.Rotation.multVec(App.Vector(0, 0, 1))
        hit = profile_pick.ray_plane(session.view, coin_pos, placement.Base, normal)
        if hit is None:
            return None
        local = placement.inverse().multVec(hit[0])
        return (local.x, local.y)

    def _near_curve(self, point, pos):
        """True if the sketch point is within a few pixels of a curve or point of the
        sketch (FreeCAD's highlight under the mouse can lag behind a quick click)."""
        import Part

        a = self._sketch_point(QtCore.QPoint(pos.x() + 10, pos.y()))
        if a is None:
            return False
        mm_per_px = ((a[0] - point[0]) ** 2 + (a[1] - point[1]) ** 2) ** 0.5 / 10.0
        if self._curves is None:
            shapes = []
            sketch = self.session.sketch
            geometry = list(sketch.Geometry)
            try:
                geometry += list(sketch.ExternalGeo)[2:]  # projected curves (not the axes)
            except Exception:
                pass
            for geo in geometry:
                try:
                    shapes.append(geo.toShape())
                except Exception:
                    continue
            self._curves = Part.Compound(shapes) if shapes else False
        if not self._curves:
            return False
        probe = Part.Vertex(App.Vector(point[0], point[1], 0))
        return probe.distToShape(self._curves)[0] <= NEAR_PX * mm_per_px

    def _anchor(self, index):
        """A point well inside area `index` (its middle can be in a hole), or None."""
        try:
            if self.faces[index] is None:  # a text: the middle of its biggest triangle
                return _triangle_anchor(self.regions[index])
            from . import extrude

            p = extrude.interior_point(self.faces[index])
            return (p.x, p.y)
        except Exception:
            return None

    # -- mouse (called by sketch_mode._ViewFilter with Qt's events) ------------------------
    def pressed(self, pos, modifiers):
        try:
            self._press = None
            if self._usable():
                self._press = (QtCore.QPoint(pos), modifiers)
        except Exception as exc:
            warn("sketch areas: %s" % exc)

    def released(self, pos):
        try:
            press, self._press = self._press, None
            if press is None or (pos - press[0]).manhattanLength() > CLICK_SLOP:
                return  # a box selection or a drag, not a click
            QtCore.QTimer.singleShot(0, lambda: self._clicked(*press))
        except Exception as exc:
            warn("sketch areas: %s" % exc)

    def _clicked(self, pos, modifiers):
        """After FreeCAD has handled the click: an area, a curve or empty space. (What
        FreeCAD lights up is read now, not at the press: right after a move off a
        selected curve it still showed that curve.)"""
        try:
            if self.session.closed:
                return
            additive = bool(modifiers & (QtCore.Qt.ControlModifier | QtCore.Qt.ShiftModifier))
            point = self._sketch_point(pos)
            if point is None:
                return
            on_text = core.region_at(self.regions, point[0], point[1]) in self.text_keys
            if not on_text and (self._sketch_item_under_mouse() or self._near_curve(point, pos)):
                if not additive and self.picks:
                    self._set([])  # the curve (or dimension) is the selection now
                return
            hit = core.region_at(self.regions, point[0], point[1])
            anchor = self._anchor(hit) if hit is not None else None
            if anchor is not None and core.region_at(self.regions, *anchor) != hit:
                anchor = None  # (shaded with a coarse tessellation: keep the click point)
            self._set(core.click(self.picks, self.regions, point, additive, anchor))
        except Exception as exc:
            warn("sketch areas: %s" % exc)

    def moved(self, pos):
        try:
            self._mouse = QtCore.QPoint(pos)
            self._hover_timer.start()
        except Exception as exc:
            warn("sketch areas: %s" % exc)

    def left(self):
        self._mouse = None
        if self.hovered is not None:
            self.hovered = None
            self._draw()

    def _hover(self):
        try:
            if self.session.closed:
                return
            found = None
            if (
                self._mouse is not None
                and self.regions
                and self._usable()
                and not self._sketch_item_under_mouse()
            ):
                point = self._sketch_point(self._mouse)
                if point is not None:
                    found = core.region_at(self.regions, point[0], point[1])
            if found != self.hovered:
                self.hovered = found
                self._draw()
        except Exception as exc:
            warn("sketch areas: %s" % exc)

    def remove(self):
        try:
            self._hover_timer.stop()
        except Exception:
            pass
        try:
            self.session.shading.root.removeChild(self.root)
        except Exception:
            pass


def _text_areas(session):
    """[(text, points, triangles)] of the open sketch's texts (text_ui), or []."""
    try:
        from . import text_ui

        return text_ui.area_entries(session)
    except Exception:
        return []


def _triangle_anchor(region):
    """The middle of a region's biggest triangle (a point surely inside it)."""
    best, anchor = -1.0, None
    pts = region.points
    for i, j, k in region.triangles:
        a, b, c = pts[i], pts[j], pts[k]
        area = abs((b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1]))
        if area > best:
            best = area
            anchor = ((a[0] + b[0] + c[0]) / 3.0, (a[1] + b[1] + c[1]) / 3.0)
    return anchor


def _text_at(sketch, x, y):
    """The sketch's text whose letters hold sketch point (x, y), or None."""
    try:
        from . import text

        point = sketch.Placement.multVec(App.Vector(x, y, 0))  # the text's own coordinates
        for obj in text.texts_of(sketch):
            if "Touched" in obj.State or obj.Shape.isNull():
                obj.recompute()
            if any(f.isInside(point, 1e-4, True) for f in obj.Shape.Faces):
                return obj
    except Exception as exc:
        warn("sketch text: %s" % exc)
    return None


# -- the picks become profiles ------------------------------------------------------------
def profiles(sketch, points):
    """[(sketch, "InternalFaceN")] for points picked inside the open sketch, once it is
    closed and recomputed (FreeCAD's areas of the sketch): for each point the smallest
    area holding it, in pick order, each once. A point on a text gives (text, ""): the
    whole text is one profile, as in Fusion."""
    from . import extrude, profile_pick

    if sketch is None or not points:
        return []
    try:
        areas = extrude.regions(sketch)
    except Exception as exc:
        warn("sketch areas of %s: %s" % (sketch.Label, exc))
        return []
    placement = sketch.getGlobalPlacement()
    found = []
    for x, y in points:
        on_text = _text_at(sketch, x, y)
        if on_text is not None:
            if (on_text, "") not in found:
                found.append((on_text, ""))
            continue
        point = placement.multVec(App.Vector(x, y, 0))
        best = None
        for sub, face in areas:
            if profile_pick.inside(face, point) and (best is None or face.Area < best[1].Area):
                best = (sub, face)
        if best is not None and (sketch, best[0]) not in found:
            found.append((sketch, best[0]))
    return found


def ensure_areas(sketch, tries=0):
    """A sketch made before SciForge turned FreeCAD's sketch areas on (an older file, or
    made while SciForge was off) gets them when it is opened, so after Finish Sketch its
    areas can be clicked like a new sketch's. FreeCAD builds them when the sketch is
    recomputed, which Finish Sketch does anyway (FreeCAD's own "Sketch recompute" step).
    The switch itself is set outside any undo step: no step of its own, the Redo list is
    kept, and Ctrl+Z never turns the areas off again."""
    try:
        if sketch is None or "MakeInternals" not in sketch.PropertiesList:
            return
        if sketch.MakeInternals:
            return
        doc = sketch.Document
        if App.getActiveTransaction() is not None or getattr(doc, "HasPendingTransaction", False):
            if tries < 20:  # inside someone's undo step: it would be undone with it
                doc_name, name = doc.Name, sketch.Name

                def again():
                    try:
                        obj = App.getDocument(doc_name).getObject(name)
                    except Exception:
                        obj = None
                    ensure_areas(obj, tries + 1)

                QtCore.QTimer.singleShot(250, again)
            return
        from . import log

        sketch.MakeInternals = True
        log("%s: its closed areas can be picked after Finish Sketch (older sketch)" % sketch.Label)
    except Exception as exc:
        warn("sketch areas: %s" % exc)
