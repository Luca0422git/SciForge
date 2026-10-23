# SPDX-License-Identifier: LGPL-2.1-or-later
"""The dialog base of the SHEET METAL flat tools (Unfold, Refold, Rip, Convert to Sheet
Metal, Create Flat Pattern): picks of faces, edges and points on one body, routed to the
dialog's selection boxes by what was clicked (a flat face, a bend, an edge, a vertex).

Picking works as in pickpanel (shared with Shell and Draft): a click adds, a click on a pick
drops it, Esc cancels, Enter is OK, problems are said in the dialog. A slot is
(key, label, accepts, many): accepts(shape element name, element) says whether a pick goes
there; the first slot that takes it gets it (a single slot is replaced by a new pick).
"""

import FreeCAD as App

from . import bodies, commands, pickpanel, sheetmetal, warn
from . import sheetmetal_unfold as unfolder
from .compat import QtWidgets


def planar_face(name, item):
    return name.startswith("Face") and unfolder.is_planar(item)


def bend_face(name, item):
    return name.startswith("Face") and unfolder.is_cylinder(item)


def any_face(name, item):
    return name.startswith("Face")


def an_edge(name, item):
    return name.startswith("Edge")


def a_point(name, item):
    return name.startswith("Vertex") or name.startswith("Edge")


def start_body(sheet_metal=True):
    """(body, base) a new dialog works on: the active / selected body when it fits, else the
    first fitting body of the design (sheet metal ones for the flat tools)."""
    doc = App.ActiveDocument
    if doc is None:
        return None, None
    candidates = []
    try:
        import FreeCADGui as Gui

        for sel in Gui.Selection.getSelection() if App.GuiUp else []:
            body = bodies.body_of(sel) or (sel if bodies.is_body(sel) else None)
            if body is not None:
                candidates.append(body)
    except Exception:
        pass
    try:
        found = commands.find_body()
        if found is not None:
            candidates.append(found)
    except Exception:
        pass
    candidates += bodies.list_bodies(doc)
    for body in candidates:
        if not bodies.alive(body) or not bodies.has_solid(body):
            continue
        if sheet_metal and not sheetmetal.is_sheet_metal_body(body):
            continue
        tip = body.Tip
        if tip is not None and not tip.Shape.isNull():
            return body, tip
    return None, None


class SheetPanel(pickpanel.PickPanel):
    """Subclasses set title/icon, SLOTS, and implement build_fields() and update()."""

    title = "Sheet Metal"
    icon = None
    SHEET_METAL = True
    SLOTS = ()  # (key, label, accepts, many)
    last = None

    def __init__(self, doc, transaction, feature=None):
        super().__init__(doc, transaction)
        SheetPanel.last = self
        self.target = feature
        self.editing = feature is not None
        self.picks = {key: [] for key, _l, _a, _m in self.SLOTS}
        self.boxes = {}
        if feature is not None:
            self.body = bodies.body_of(feature)
            self.base = feature.BaseFeature
        else:
            self.body, self.base = start_body(self.SHEET_METAL)
        try:
            self.build_fields()
        except Exception as exc:
            warn("%s fields: %s" % (self.title, exc))
        self.finish_layout()
        if self.base is None:
            self.say(self.no_body_text())
            return
        try:
            if feature is not None:
                self.load(feature)
            self.start_picking()
            self.refresh_boxes()
            self.update()
        except Exception as exc:
            self.say("⚠ %s" % exc)
            warn("%s could not start picking: %s" % (self.title, exc))

    # -- to override --------------------------------------------------------------------
    def no_body_text(self):
        return "⚠ There is no sheet metal body: use Convert to Sheet Metal (MODIFY) first."

    def build_fields(self):
        pass

    def load(self, feature):
        pass

    def update(self):
        """The picks or a field changed: rebuild the step / the message."""

    # -- selection boxes ----------------------------------------------------------------
    def add_slot_rows(self):
        for key, label, _accepts, _many in self.SLOTS:
            box = QtWidgets.QPushButton()
            box.setObjectName("SciForgeSlot_" + key)
            box.setFlat(True)
            box.clicked.connect(lambda _c=False, k=key: self.clear_slot(k))
            box.setToolTip("Click to clear")
            self.boxes[key] = box
            self.layout.addRow(label, box)

    def refresh_boxes(self):
        for key, box in self.boxes.items():
            n = len(self.picks.get(key, []))
            box.setText("%d selected  ✕" % n if n else "Select")

    def clear_slot(self, key):
        try:
            if self.picks.get(key):
                self.picks[key] = []
                self.refresh_boxes()
                self._sync()
                self.update()
        except Exception as exc:
            warn("%s: %s" % (self.title, exc))

    # -- pickpanel hooks ----------------------------------------------------------------
    def _element(self, short):
        try:
            return self.base.Shape.getElement(short)
        except Exception:
            return None

    def allow(self, obj, short):
        if obj is not self.base or not short:
            return obj is not self.base and self._other_body(obj) is not None
        item = self._element(short)
        if item is None:
            return False
        return any(accepts(short, item) for _k, _l, accepts, _m in self.active_slots())

    def active_slots(self):
        return self.SLOTS

    def _other_body(self, obj):
        """(body, tip) when obj is the shown step of another body this dialog can use."""
        if self.editing:
            return None
        body = bodies.body_of(obj)
        if body is None or body is self.body or body.Tip is not obj:
            return None
        if self.SHEET_METAL and not sheetmetal.is_sheet_metal_body(body):
            return None
        return body, obj

    def picks_changed(self, added, dropped):
        changed = False
        for obj, short, _p in dropped:
            for key in self.picks:
                if obj is self.base and short in self.picks[key]:
                    self.picks[key].remove(short)
                    changed = True
        for obj, short, _p in added:
            if not short:
                continue
            if obj is not self.base:
                other = self._other_body(obj)
                if other is None:
                    continue
                self.switch_body(*other)
                self.picks = {key: [] for key in self.picks}
                changed = True
            item = self._element(short)
            if item is None:
                continue
            for key, _label, accepts, many in self.active_slots():
                if not accepts(short, item):
                    continue
                if short in self.picks[key]:
                    break
                if many:
                    self.picks[key].append(short)
                else:
                    self.picks[key] = [short]
                changed = True
                break
        if changed:
            self.refresh_boxes()
            self.update()
        return False  # update() rebuilt what it needs

    def shown(self):
        names = []
        for key in self.picks:
            names += [n for n in self.picks[key] if n not in names]
        return [(self.base, names)] if self.base is not None and names else []

    def pick(self, key):
        values = self.picks.get(key) or []
        return values[0] if values else ""

    # -- OK ------------------------------------------------------------------------------
    def ready(self):
        """None when OK may close, else the reason."""
        return None

    def accept(self):
        try:
            reason = self.ready()
        except Exception as exc:
            reason = str(exc)
        if reason:
            self.say("⚠ " + reason)
            return False
        return super().accept()
