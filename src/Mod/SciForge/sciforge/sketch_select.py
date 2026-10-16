# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's selection in an open sketch: a double-click on a curve selects its chain,
and a box drag keeps Fusion's modifiers (the rules: sketch_select_core.py).

FreeCAD 1.1.4 has a double-click "wire" selection of its own, but it never fired under
SciForge (checked with real double-clicks): SciForge finds the curve under the pointer
itself (sketch_draw.Geometry, the same picking its sketch tools use) and selects the
chain through Gui.Selection, so FreeCAD's sketch shows it selected and every command sees
it. The double-click and the release after it never reach FreeCAD (its own handling
toggled the clicked curve off again).

FreeCAD's sketch box (window from left to right, crossing from right to left) adds to
the selection whatever the keys; Fusion's plain box replaces it: before FreeCAD sees the
release of a box drag the selection is cleared (plain) or put aside (Ctrl, to be toggled
afterwards). Never lets an exception out (warn() and carry on)."""

import FreeCADGui as Gui

from . import log, warn
from . import sketch_select_core as core
from .compat import QtCore

BOX_PIXELS = 4  # a press and release further apart than this were a box drag
CLOSED = (
    "Part::GeomCircle",
    "Part::GeomEllipse",
)


def _xy(v):
    return (v.x, v.y)


def _ends(geo):
    """The end points of an open curve, [] for a closed one, None for a point."""
    kind = geo.TypeId
    if kind == "Part::GeomPoint":
        return None
    if kind in CLOSED:
        return []
    if kind == "Part::GeomBSplineCurve":
        try:
            if geo.isPeriodic() or geo.isClosed():
                return []
        except Exception:
            pass
    if hasattr(geo, "StartPoint") and hasattr(geo, "EndPoint"):
        return [_xy(geo.StartPoint), _xy(geo.EndPoint)]
    return []


def curves_of(sketch):
    """{geo: (kind, ends)} of the sketch's curves and projected curves (sketch_draw's
    numbering: projected curves from -3)."""
    found = {}
    for i, geo in enumerate(sketch.Geometry):
        ends = _ends(geo)
        if ends is None:
            continue
        try:
            kind = "construction" if sketch.getConstruction(i) else "normal"
        except Exception:
            kind = "normal"
        found[i] = (kind, ends)
    try:
        external = list(sketch.ExternalGeo)[2:]
    except Exception:
        external = []
    for k, geo in enumerate(external):
        ends = _ends(geo)
        if ends is None:
            continue
        found[-3 - k] = ("projected", ends)
    return found


def element_name(geo):
    """The sketch's selection name of curve `geo` ("Edge3", "ExternalEdge1")."""
    if geo >= 0:
        return "Edge%d" % (geo + 1)
    return "ExternalEdge%d" % (-geo - 2)


class SketchSelect:
    """Owned by sketch_mode.SketchSession; its view filter calls in here."""

    def __init__(self, session):
        self.session = session
        self.swallow_release = False
        self._box = None  # {"pos", "far"} of a left press on empty space

    # -- double-click -------------------------------------------------------------------
    def curve_at(self, pos):
        """The sketch curve (geo) under widget pixel `pos`, or None (the axes do not
        count)."""
        from . import sketch_draw
        from .sketch_infer import _ViewMap

        session = self.session
        if session.gl is None:
            return None
        view = _ViewMap(session, session.gl, pos)
        if not view.ok:
            return None
        geometry = sketch_draw.Geometry(session.sketch)
        best = None
        tol = sketch_draw.pick_pixels() * view.px
        from . import sketch_infer_core as icore

        for geo, curve in geometry.hits:
            if geo in (-1, -2) or not icore.near_curve(view.raw, curve, tol):
                continue
            d = icore.curve_distance(view.raw, curve)
            if best is None or d < best[1]:
                best = (geo, d)
        return best[0] if best is not None else None

    def double_clicked(self, pos):
        """A double-click with no tool running: True when it was on a curve (its chain
        gets selected)."""
        try:
            geo = self.curve_at(pos)
        except Exception as exc:
            warn("sketch chain selection: %s" % exc)
            return False
        if geo is None:
            return False
        self.swallow_release = True
        QtCore.QTimer.singleShot(0, lambda: self.select_chain(geo))
        return True

    def select_chain(self, geo):
        session = self.session
        if session.closed:
            return
        try:
            sketch = session.sketch
            keys = core.chain(curves_of(sketch), geo)
            doc = sketch.Document.Name
            for key in keys:
                name = element_name(key)
                if not Gui.Selection.isSelected(sketch, name):
                    Gui.Selection.addSelection(doc, sketch.Name, name)
            log("sketch: double-click selected a chain of %d curve(s)" % len(keys))
        except Exception as exc:
            warn("sketch chain selection: %s" % exc)

    # -- box drag ----------------------------------------------------------------------------
    def pressed(self, event):
        """A left press with no tool running (before FreeCAD sees it)."""
        self._box = None
        try:
            pre = Gui.Selection.getPreselection()
            if getattr(pre, "ObjectName", ""):
                return  # on a curve, point or dimension: FreeCAD drags it
        except Exception:
            pass
        self._box = {"pos": event.position().toPoint(), "far": 0}

    def moved(self, event):
        if self._box is None:
            return
        d = (event.position().toPoint() - self._box["pos"]).manhattanLength()
        self._box["far"] = max(self._box["far"], d)

    def released(self, event):
        """The release of a left press: when it ends a box drag, set the selection up so
        that FreeCAD's box (it adds what it encloses) gives Fusion's result."""
        box, self._box = self._box, None
        if box is None or box["far"] <= BOX_PIXELS:
            return
        try:
            mods = event.modifiers()
            plan = core.box_plan(
                bool(mods & QtCore.Qt.ShiftModifier), bool(mods & QtCore.Qt.ControlModifier)
            )
            if plan == "add":
                return
            sketch = self.session.sketch
            before = selected_names(sketch)
            Gui.Selection.clearSelection()
            if plan == "toggle":
                QtCore.QTimer.singleShot(0, lambda: self._toggle(before))
        except Exception as exc:
            warn("sketch box selection: %s" % exc)

    def _toggle(self, before):
        session = self.session
        if session.closed:
            return
        try:
            sketch = session.sketch
            boxed = selected_names(sketch)
            keep = core.toggled(before, boxed)
            Gui.Selection.clearSelection()
            doc = sketch.Document.Name
            for name in keep:
                Gui.Selection.addSelection(doc, sketch.Name, name)
        except Exception as exc:
            warn("sketch box selection: %s" % exc)


def selected_names(sketch):
    """The open sketch's selected element names ("Edge3", "Vertex2"...)."""
    names = []
    try:
        for sel in Gui.Selection.getSelectionEx():
            if sel.Object is not sketch:
                continue
            for name in sel.SubElementNames:
                short = name.rsplit(".", 1)[-1]
                if short and short not in names:
                    names.append(short)
    except Exception:
        pass
    return names
