# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's sketch environment on top of FreeCAD's Sketcher.

While SciForge is on, every sketch that is opened (FreeCAD "edit mode") behaves like
a Fusion sketch:

- Esc stops the drawing tool; a second Esc clears the selection. Esc never closes
  the sketch (only Finish Sketch does).
- No pop-ups: a new dimension gets a small box next to it where you type the value
  (Enter keeps it, Esc keeps the measured value). Double-clicking a dimension opens
  the same box instead of FreeCAD's "Insert length" window.
- Closed regions (profiles) are shaded light blue while you draw, also where curves
  cross (sketch_regions.py).
- The SKETCH PALETTE sits at the top of the sketch panel (sketch_palette.py): Look At,
  grid, snap, slice, show profiles/points/dimensions/constraints/projected geometry.
- Sketch curves use Fusion's colours on the dark background (blue = not fully
  constrained, white = fully constrained, orange = construction, purple = projected).
- The circumscribed polygon previews and builds with the mouse on the middle of an
  edge (FreeCAD's polygon tool only knows corners).

Everything here is undone by disable(): parameters get their old values back.

Rules followed (docs/sciforge/dev/feature-guide.md): FreeCAD's Python event and
observer hooks only schedule work with QTimer.singleShot; Coin nodes are only read and
changed from Qt timers (never from pivy callbacks).
"""
import math

import FreeCAD as App
import FreeCADGui as Gui

from . import log, warn
from .compat import QtCore, QtGui, QtWidgets

SKETCHER = "User parameter:BaseApp/Preferences/Mod/Sketcher"
SKETCHER_GENERAL = SKETCHER + "/General"
SNAP = SKETCHER + "/Snap"
VIEW = "User parameter:BaseApp/Preferences/View"
PALETTE_PARAMS = "User parameter:BaseApp/Preferences/Mod/SciForge/SketchPalette"


def _rgba(hex_color):
    value = int(hex_color.lstrip("#"), 16)
    return (value << 8) | 0xFF


# Fusion's sketch colours, made for SciForge's dark 3D view.
BLUE = "#5cb3ff"  # curves that can still move (under-constrained)
WHITE = "#f0f0f0"  # fully constrained curves, dimension text
ORANGE = "#f5a142"  # construction
PURPLE = "#c084fc"  # projected / included geometry

# (group, kind, name, value) set while SciForge is on; old values come back in disable().
PARAMS = [
    # Esc never leaves the sketch (Fusion: only Finish Sketch does)
    (SKETCHER, "Bool", "LeaveSketchWithEscape", False),
    # no modal "Insert length" window after a dimension: SciForge's in-place box instead
    (SKETCHER, "Bool", "ShowDialogOnDistanceConstraint", False),
    # Fusion has no constraint/element lists: keep FreeCAD's folded under the palette
    (SKETCHER, "Bool", "ExpandedConstraintsWidget", False),
    (SKETCHER, "Bool", "ExpandedElementsWidget", False),
    # projected edges form profiles, like Fusion's (Include 3D Geometry: reference only)
    (SKETCHER_GENERAL, "Bool", "AlwaysExtGeoReference", False),
    # Fusion's grid: quiet solid lines, every 10th a little brighter
    (SKETCHER_GENERAL, "Int", "GridLinePattern", 0xFFFF),
    (SKETCHER_GENERAL, "Int", "GridDivLinePattern", 0xFFFF),
    (SKETCHER_GENERAL, "Int", "GridDivLineWidth", 1),
    (SKETCHER_GENERAL, "Unsigned", "GridLineColor", _rgba("#33383f")),
    (SKETCHER_GENERAL, "Unsigned", "GridDivLineColor", _rgba("#4b525d")),
    (VIEW, "Unsigned", "EditedEdgeColor", _rgba(BLUE)),
    (VIEW, "Unsigned", "CreateLineColor", _rgba(BLUE)),
    (VIEW, "Unsigned", "FullyConstraintElementColor", _rgba(WHITE)),
    (VIEW, "Unsigned", "FullyConstrainedColor", _rgba(WHITE)),
    (VIEW, "Unsigned", "ConstructionColor", _rgba(ORANGE)),
    (VIEW, "Unsigned", "FullyConstraintConstructionElementColor", _rgba(ORANGE)),
    (VIEW, "Unsigned", "ExternalColor", _rgba(PURPLE)),
    (VIEW, "Unsigned", "ExternalDefiningColor", _rgba(PURPLE)),
    (VIEW, "Unsigned", "ConstrainedDimColor", _rgba(WHITE)),
    (VIEW, "Unsigned", "CursorTextColor", _rgba(WHITE)),
    (VIEW, "Unsigned", "CursorCrosshairColor", _rgba(WHITE)),
]

# Sketch palette options (Fusion's defaults); remembered between sessions.
PALETTE_DEFAULTS = {
    "grid": True,
    "snap": True,
    "slice": False,
    "profile": True,
    "points": True,
    "dimensions": True,
    "constraints": True,
    "projected": True,
}

DIMENSIONAL = ("Distance", "DistanceX", "DistanceY", "Radius", "Diameter", "Angle")
# Commands after which a new dimension gets the in-place value box.
DIMENSION_COMMANDS = {
    "Sketcher_Dimension",
    "Sketcher_CompDimensionTools",
    "Sketcher_ConstrainDistance",
    "Sketcher_ConstrainDistanceX",
    "Sketcher_ConstrainDistanceY",
    "Sketcher_ConstrainRadius",
    "Sketcher_ConstrainDiameter",
    "Sketcher_ConstrainRadiam",
    "Sketcher_ConstrainAngle",
    "SciForge_SketchDimension",
}

_state = {
    "on": False,
    "saved": [],
    "observer": None,
    "app_observer": None,
    "session": None,
    "profilelib": None,
    "polygon": None,  # {"circumscribed": bool} while SciForge's polygon tool runs
}


# -- palette options ------------------------------------------------------------------
def option(name):
    try:
        group = App.ParamGet(PALETTE_PARAMS)
        return group.GetBool(name, PALETTE_DEFAULTS[name])
    except Exception:
        return PALETTE_DEFAULTS.get(name, True)


def set_option(name, value):
    """Change a palette option and apply it to the open sketch."""
    try:
        App.ParamGet(PALETTE_PARAMS).SetBool(name, bool(value))
    except Exception as exc:
        warn("sketch palette: %s" % exc)
    if name == "snap":
        _set_param(SNAP, "Bool", "SnapToGrid", bool(value))
    session = current()
    if session is not None:
        session.apply_option(name)


def _set_param(path, kind, name, value):
    try:
        getattr(App.ParamGet(path), "Set" + kind)(name, value)
    except Exception as exc:
        warn("could not set %s: %s" % (name, exc))


# -- on / off -----------------------------------------------------------------------
def enable():
    if _state["on"]:
        return
    _state["on"] = True
    _save_and_apply(PARAMS + [(SNAP, "Bool", "SnapToGrid", option("snap"))])
    _patch_profilelib()
    try:
        observer = _GuiObserver()
        Gui.addDocumentObserver(observer)
        _state["observer"] = observer
        app_observer = _AppObserver()
        App.addDocumentObserver(app_observer)
        _state["app_observer"] = app_observer
    except Exception as exc:
        warn("sketch mode: cannot follow sketch editing: %s" % exc)
    sketch = editing_sketch()
    if sketch is not None:
        _start(sketch)


def disable():
    if not _state["on"]:
        return
    _state["on"] = False
    _end()
    for key, remove in (
        ("observer", Gui.removeDocumentObserver),
        ("app_observer", App.removeDocumentObserver),
    ):
        if _state[key] is not None:
            try:
                remove(_state[key])
            except Exception:
                pass
            _state[key] = None
    _unpatch_profilelib()
    _restore_params()


def _save_and_apply(params):
    if not _state["saved"]:
        for path, kind, name, _ in params:
            try:
                group = App.ParamGet(path)
                existed = name in getattr(group, "Get" + kind + "s")()
                value = getattr(group, "Get" + kind)(name) if existed else None
                _state["saved"].append((path, kind, name, value))
            except Exception as exc:
                warn("sketch mode: cannot read %s: %s" % (name, exc))
    for path, kind, name, value in params:
        _set_param(path, kind, name, value)


def _restore_params():
    for path, kind, name, value in _state["saved"]:
        try:
            group = App.ParamGet(path)
            if value is None:
                getattr(group, "Rem" + kind)(name)
            else:
                getattr(group, "Set" + kind)(name, value)
        except Exception as exc:
            warn("sketch mode: cannot restore %s: %s" % (name, exc))
    _state["saved"] = []


# -- which sketch is open --------------------------------------------------------------
def editing_sketch():
    """The sketch being edited in the active document, or None."""
    try:
        gdoc = Gui.ActiveDocument
        edit = gdoc.getInEdit() if gdoc is not None else None
        obj = edit.Object if edit is not None else None
        if obj is not None and obj.TypeId == "Sketcher::SketchObject":
            return obj
    except Exception:
        pass
    return None


def current():
    """The open SketchSession, or None."""
    session = _state["session"]
    if session is not None and session.closed:
        _state["session"] = None
        return None
    return session


class _GuiObserver:
    """FreeCAD tells us when a sketch opens/closes; the work runs later from a timer."""

    def slotInEdit(self, vp):
        try:
            obj = vp.Object
            if obj is not None and obj.TypeId == "Sketcher::SketchObject":
                name, doc = obj.Name, obj.Document.Name
                QtCore.QTimer.singleShot(0, lambda: _start_named(doc, name))
        except Exception as exc:
            warn("sketch mode: %s" % exc)

    def slotResetEdit(self, vp):
        try:
            QtCore.QTimer.singleShot(0, _end_if_closed)
        except Exception as exc:
            warn("sketch mode: %s" % exc)


class _AppObserver:
    """Changes to the open sketch (new curves, constraints) refresh the shading,
    the display options and open the dimension box. Only schedules work."""

    def slotChangedObject(self, obj, prop):
        session = _state["session"]
        if session is None or session.closed:
            return
        try:
            if prop in ("Geometry", "Constraints", "ExternalGeo", "Placement") and (
                obj.Name == session.name and obj.Document.Name == session.doc_name
            ):
                session.changed(prop)
        except Exception:
            pass

    def _settled(self, doc, kind):
        session = _state["session"]
        if session is None or session.closed:
            return
        try:
            if doc.Name == session.doc_name:
                session.settled(kind, len(session.sketch.Constraints))
        except Exception:
            pass

    def slotCommitTransaction(self, doc):
        self._settled(doc, "commit")

    def slotAbortTransaction(self, doc):
        self._settled(doc, "abort")

    def slotUndoDocument(self, doc):
        self._settled(doc, "undo")

    def slotRedoDocument(self, doc):
        self._settled(doc, "redo")


def _start_named(doc_name, name):
    try:
        doc = App.getDocument(doc_name)
        sketch = doc.getObject(name) if doc is not None else None
        if sketch is not None and editing_sketch() is sketch:
            _start(sketch)
    except Exception as exc:
        warn("sketch mode: could not prepare the sketch: %s" % exc)


def repark_keys():
    """FreeCAD makes the Sketcher's buttons only when a sketch is first opened, and
    those come with the Sketcher's own one-letter keys (C coincident, T tangent, E
    equal, P parallel...). Two owners of a key make Qt ignore both, so C and T did
    nothing in a sketch. When that happens the Fusion keys are bound again, which
    parks the new FreeCAD keys too (shortcuts.py gives them back when SciForge is off)."""
    from . import shortcuts

    keys = set(shortcuts.bound_keys())
    if not keys:
        return False
    for name in Gui.listCommands():
        try:
            cmd = Gui.Command.get(name)
            current_key = cmd.getShortcut() if cmd is not None else ""
        except Exception:
            continue
        if current_key and shortcuts.normalise(current_key) in keys:
            shortcuts.restore()
            shortcuts.apply()
            return True
    return False


def _start(sketch):
    session = current()
    if session is not None and session.sketch is sketch:
        return
    _end()
    if not _state["on"]:
        return
    try:
        repark_keys()
    except Exception as exc:
        warn("sketch keys: %s" % exc)
    try:
        _state["session"] = SketchSession(sketch)
        log("sketch %s: Fusion sketch mode on" % sketch.Label)
    except Exception as exc:
        warn("sketch mode: %s" % exc)


def _end_if_closed():
    session = current()
    if session is not None and editing_sketch() is not session.sketch:
        _end()


def _end():
    session = _state["session"]
    _state["session"] = None
    if session is not None:
        try:
            session.close()
        except Exception as exc:
            warn("sketch mode: closing: %s" % exc)


# -- helpers for the 3D view ----------------------------------------------------------
def gl_widget():
    """The OpenGL widget of the active 3D view (receives mouse and keys)."""
    try:
        area = Gui.getMainWindow().findChild(QtWidgets.QMdiArea)
        sub = area.activeSubWindow() or (area.subWindowList() or [None])[-1]
        if sub is None:
            return None
        for widget in sub.findChildren(QtWidgets.QWidget):
            if widget.metaObject().className() == "QOpenGLWidget":
                return widget
    except Exception:
        pass
    return None


def find_node(root, name):
    """(node, its parent) for the first Coin node called `name` under root (also inside
    switches), or (None, None). The search path dies with the search action, so only
    the nodes (kept alive by the scene graph) are returned."""
    from pivy import coin

    action = coin.SoSearchAction()
    action.setName(coin.SbName(name))
    action.setInterest(coin.SoSearchAction.FIRST)
    action.setSearchingAll(True)
    action.apply(root)
    path = action.getPath()
    if path is None or path.getLength() < 2:
        return None, None
    node = path.getTail()
    parent = path.getNodeFromTail(1)
    return node, parent


def _is_valid(widget):
    try:
        import shiboken6

        return widget is not None and shiboken6.isValid(widget)
    except Exception:
        try:
            widget.objectName()
            return True
        except Exception:
            return False


# -- the open sketch -----------------------------------------------------------------
class SketchSession:
    def __init__(self, sketch):
        self.sketch = sketch
        self.doc = sketch.Document
        self.name = sketch.Name
        self.doc_name = sketch.Document.Name
        self.closed = False
        self.view = Gui.ActiveDocument.ActiveView
        self.gl = gl_widget()
        self.constraint_count = len(sketch.Constraints)
        self.editor = None
        self.palette = None
        self.last_press = None
        self.shading = ProfileShading(self)
        self.display = DisplayOptions(self)
        self.polygon = PolygonPreview(self)
        self._refresh = QtCore.QTimer()
        self._refresh.setSingleShot(True)
        self._refresh.setInterval(120)
        self._refresh.timeout.connect(self._refreshed)
        self.filter = _ViewFilter(self)
        if self.gl is not None:
            self.gl.installEventFilter(self.filter)
        for name in PALETTE_DEFAULTS:
            if name != "snap":
                self.apply_option(name)
        self._palette_tries = 0
        QtCore.QTimer.singleShot(0, self._add_palette)
        self._refreshed()

    # -- changes ---------------------------------------------------------------------
    def changed(self, prop):
        self._refresh.start()

    def _refreshed(self):
        if self.closed:
            return
        try:
            self.shading.update()
            self.display.apply()
        except Exception as exc:
            warn("sketch display: %s" % exc)

    def settled(self, kind, count):
        """A sketch operation was committed, aborted or undone (called by FreeCAD's
        document signal: only counts here, the box opens from a timer). A dimension
        the Dimension tool just placed gets the value box. FreeCAD adds the dimension
        already while it follows the mouse, so only a committed one counts."""
        grew = count > self.constraint_count
        self.constraint_count = count
        if kind == "commit":
            QtCore.QTimer.singleShot(0, self._repair)
        if kind == "commit" and grew:
            QtCore.QTimer.singleShot(0, lambda: self._new_dimension(count - 1))

    def _repair(self):
        """FreeCAD's trim can leave an invalid constraint behind (sketch_fix.py)."""
        if self.closed:
            return
        try:
            from . import sketch_fix

            if not sketch_fix.bad_coincidences(self.sketch):
                return
            self.doc.openTransaction("Repair Trim")
            try:
                fixed = sketch_fix.repair(self.sketch)
                self.sketch.solve()
            except Exception:
                self.doc.abortTransaction()
                raise
            self.doc.commitTransaction()
            log("repaired %d constraint(s) FreeCAD's trim made invalid" % fixed)
        except Exception as exc:
            warn("could not repair the sketch: %s" % exc)

    def _new_dimension(self, index):
        if self.closed or self.editor is not None:
            return
        try:
            from . import recent

            last = recent.last()
            if last is None or last[0] not in DIMENSION_COMMANDS:
                return
            constraints = self.sketch.Constraints
            if index >= len(constraints):
                return
            c = constraints[index]
            if c.Type in DIMENSIONAL and c.Driving:
                self.edit_dimension(index)
        except Exception as exc:
            warn("dimension box: %s" % exc)

    # -- palette options -----------------------------------------------------------------
    def apply_option(self, name):
        try:
            value = option(name)
            vp = self.sketch.ViewObject
            if name == "grid":
                if bool(vp.ShowGrid) != value:
                    vp.ShowGrid = value
            elif name == "slice":
                self.set_slice(value)
            elif name == "profile":
                self.shading.set_visible(value)
            elif name in ("points", "dimensions", "constraints", "projected"):
                self.display.apply()
        except Exception as exc:
            warn("sketch palette %s: %s" % (name, exc))

    def set_slice(self, on):
        vp = self.sketch.ViewObject
        if bool(vp.SectionView) == bool(on):
            return
        tv = vp.TempoVis
        if tv is None:
            return
        reverted = False
        try:
            direction = self.view.getViewDirection()
            normal = self.sketch.getGlobalPlacement().Rotation.multVec(App.Vector(0, 0, 1))
            reverted = direction.dot(normal) > 0
        except Exception:
            pass
        tv.sketchClipPlane(self.sketch, bool(on), reverted)

    def look_at(self):
        try:
            Gui.runCommand("Sketcher_ViewSketch")
        except Exception as exc:
            warn("look at: %s" % exc)

    # -- the palette -----------------------------------------------------------------------
    def _add_palette(self):
        if self.closed:
            return
        try:
            from . import sketch_palette

            self.palette = sketch_palette.install(self)
        except Exception as exc:
            warn("sketch palette: %s" % exc)
            self.palette = None
        if self.palette is None and self._palette_tries < 10:
            self._palette_tries += 1
            QtCore.QTimer.singleShot(100, self._add_palette)

    # -- dimensions --------------------------------------------------------------------
    def edit_dimension(self, index, pos=None):
        """Open the value box for dimension `index` (at pos, view pixels)."""
        if self.gl is None:
            return
        self.close_editor(commit=True)
        label = self.label_pixel(index)
        if label is not None:
            pos, centred = label, True  # over the dimension's text, like Fusion
        else:
            centred = False
            if pos is None:
                pos = self.last_press or self.gl.mapFromGlobal(QtGui.QCursor.pos())
        self.editor = DimensionEditor(self, index, pos, centred)

    def label_pixel(self, index):
        """Where a length dimension's text is on screen (view pixels), or None."""
        try:
            sketch = self.sketch
            c = sketch.Constraints[index]
            if c.Type not in ("Distance", "DistanceX", "DistanceY"):
                return None

            def point(geo, pos):
                g = sketch.Geometry[geo]
                return {1: g.StartPoint, 2: g.EndPoint}.get(pos, getattr(g, "Center", None))

            if c.Second >= 0:
                p1, p2 = point(c.First, c.FirstPos), point(c.Second, c.SecondPos)
            elif c.First >= 0 and c.FirstPos == 0:
                g = sketch.Geometry[c.First]
                p1, p2 = g.StartPoint, g.EndPoint
            else:
                return None
            if p1 is None or p2 is None:
                return None
            if c.Type == "DistanceX":
                p2 = App.Vector(p2.x, p1.y, 0)
            elif c.Type == "DistanceY":
                p2 = App.Vector(p1.x, p2.y, 0)
            direction = p2 - p1
            if direction.Length < 1e-9:
                return None
            direction.normalize()
            normal = App.Vector(-direction.y, direction.x, 0)
            mid = (p1 + p2) * 0.5 + normal * c.LabelDistance + direction * c.LabelPosition
            world = sketch.getGlobalPlacement().multVec(mid)
            x, y = self.view.getPointOnViewport(world)
            ratio = self.gl.devicePixelRatioF()
            return QtCore.QPoint(int(x / ratio), int(self.gl.height() - y / ratio))
        except Exception:
            return None

    def close_editor(self, commit=True):
        editor = self.editor
        self.editor = None
        if editor is not None:
            editor.finish(commit)

    # -- Esc -------------------------------------------------------------------------
    def escape(self):
        """Fusion: Esc stops the tool; with no tool running it clears the selection.
        FreeCAD has already handled the key (and reset a half-drawn shape)."""
        if self.closed or editing_sketch() is not self.sketch:
            return
        try:
            from . import sketch_pick_ui, sketch_tools_ui

            sketch_tools_ui.stop_waiting()  # Offset waiting for a curve
            sketch_pick_ui.stop_waiting()  # Mirror, patterns... waiting for curves
            sketch_pick_ui.close_box()  # Rectangular Pattern panel: cancel
        except Exception:
            pass
        _state["polygon"] = None if not self.polygon.active else _state["polygon"]
        try:
            Gui.runCommand("Sketcher_StopOperation")  # quits the tool, clears the selection
        except Exception:
            pass
        try:
            Gui.Selection.clearSelection()
        except Exception:
            pass

    def double_clicked(self, pos):
        """A double click on a dimension edits it in place (no FreeCAD pop-up)."""
        try:
            pre = Gui.Selection.getPreselection()
            names = list(getattr(pre, "SubElementNames", []) or [])
            obj = getattr(pre, "Object", None)
        except Exception:
            return False
        if obj is not self.sketch:
            return False
        for name in names:
            short = name.rsplit(".", 1)[-1]
            if short.startswith("Constraint"):
                try:
                    index = int(short[len("Constraint") :]) - 1
                    c = self.sketch.Constraints[index]
                except Exception:
                    continue
                if c.Type in DIMENSIONAL:
                    QtCore.QTimer.singleShot(0, lambda: self.edit_dimension(index, pos))
                    return True
        return False

    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            from . import sketch_pick_ui

            sketch_pick_ui.settle_box()
        except Exception as exc:
            warn("sketch mode: %s" % exc)
        try:
            self._refresh.stop()
        except Exception:
            pass
        self.close_editor(commit=True)
        for part in (self.polygon, self.shading, self.display):
            try:
                part.remove()
            except Exception as exc:
                warn("sketch mode: %s" % exc)
        if self.gl is not None and _is_valid(self.gl):
            try:
                self.gl.removeEventFilter(self.filter)
            except Exception:
                pass
        try:
            if self.palette is not None:
                self.palette.remove()
        except Exception:
            pass
        self.palette = None


class _ViewFilter(QtCore.QObject):
    """Keys and mouse on the 3D view while a sketch is open. Never blocks FreeCAD's
    own handling except for keys typed into SciForge's dimension box."""

    def __init__(self, session):
        super().__init__()
        self.session = session

    def eventFilter(self, obj, event):
        try:
            session = self.session
            if session.closed:
                return False
            kind = event.type()
            if kind == QtCore.QEvent.ShortcutOverride:
                # Typing a value: keys go into the value box / FreeCAD's on-screen fields,
                # not to shortcuts (FreeCAD's 0-6 turn the view, M moves...).
                if session.editor is not None or _is_value_key(event):
                    event.accept()
                    return True
            elif kind == QtCore.QEvent.KeyPress:
                key = event.key()
                if session.editor is not None:
                    return session.editor.key(event)
                if key in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
                    from . import sketch_pick_ui

                    if sketch_pick_ui.on_enter():
                        return True
                if key == QtCore.Qt.Key_Escape and not event.isAutoRepeat():
                    # Right away (a Qt key event, not a Coin callback): a timer could
                    # fire after the next key and stop the tool that key started.
                    session.escape()
            elif kind == QtCore.QEvent.MouseButtonPress:
                session.last_press = event.position().toPoint()
                if session.editor is not None and not session.editor.underMouse():
                    QtCore.QTimer.singleShot(0, lambda: session.close_editor(commit=True))
            elif kind == QtCore.QEvent.MouseButtonDblClick:
                if event.button() == QtCore.Qt.LeftButton:
                    return session.double_clicked(event.position().toPoint())
        except Exception as exc:
            warn("sketch view: %s" % exc)
        return False


VALUE_KEYS = {getattr(QtCore.Qt, "Key_%d" % d) for d in range(10)} | {
    QtCore.Qt.Key_Period,
    QtCore.Qt.Key_Comma,
    QtCore.Qt.Key_Minus,
}


def _is_value_key(event):
    """A digit (or . , -) typed without Ctrl/Alt: part of a value, never a shortcut
    while sketching (Fusion has no number shortcuts)."""
    mods = event.modifiers() & ~(QtCore.Qt.KeypadModifier | QtCore.Qt.ShiftModifier)
    return event.key() in VALUE_KEYS and mods == QtCore.Qt.NoModifier


# -- the value box for dimensions -------------------------------------------------------
class DimensionEditor(QtWidgets.QFrame):
    """Fusion's in-place dimension box: shows the measured value selected; type a
    value or an expression (=width*2), Enter keeps it, Esc keeps the measured one."""

    def __init__(self, session, index, pos, centred=False):
        super().__init__(session.gl)
        self.session = session
        self.sketch = session.sketch
        self.index = index
        self.setObjectName("SciForgeDimensionEditor")
        self.setStyleSheet(
            "#SciForgeDimensionEditor { background: #f5f5f5; border: 1px solid #3fa9f5;"
            " border-radius: 2px; }"
            " QLineEdit { background: #ffffff; color: #111111; border: none; padding: 1px 3px;"
            " selection-background-color: #3fa9f5; selection-color: #ffffff; }"
            " QLabel { color: #b00020; background: #f5f5f5; padding: 1px 3px; }"
        )
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)
        self.edit = QtWidgets.QLineEdit(self)
        self.edit.setObjectName("SciForgeDimensionValue")
        self.edit.setMinimumWidth(90)
        self.message = QtWidgets.QLabel("", self)
        self.message.setWordWrap(True)
        self.message.hide()
        layout.addWidget(self.edit)
        layout.addWidget(self.message)
        self.edit.setText(self._current_text())
        self.edit.selectAll()
        self.edit.returnPressed.connect(lambda: self.finish(True))
        self.adjustSize()
        if centred:
            x, y = pos.x() - self.width() // 2, pos.y() - self.height() // 2
        else:
            x, y = pos.x() + 12, pos.y() - self.height() - 6
        x = max(0, min(x, session.gl.width() - self.width() - 4))
        y = max(0, min(y, session.gl.height() - self.height() - 4))
        self.move(x, y)
        self.show()
        self.raise_()
        self.edit.setFocus()
        self._done = False
        self._fresh = True
        self.edit.textEdited.connect(self._edited)
        log("dimension: type a value and press Enter")

    def _edited(self, _text):
        self._fresh = False

    def _constraint(self):
        return self.sketch.Constraints[self.index]

    def is_angle(self):
        return self._constraint().Type == "Angle"

    def _current_text(self):
        try:
            expressions = dict(self.sketch.ExpressionEngine)
            path = ".Constraints[%d]" % self.index
            if path in expressions:
                return "=" + expressions[path]
            q = self.sketch.getDatum(self.index)
            if self.is_angle():
                return "%g deg" % round(q.getValueAs("deg").Value, 6)
            return "%g mm" % round(q.getValueAs("mm").Value, 6)
        except Exception:
            return ""

    def key(self, event):
        """A key pressed on the 3D view while the box is open: it goes into the box."""
        key = event.key()
        if key == QtCore.Qt.Key_Escape:
            QtCore.QTimer.singleShot(0, lambda: self.session.close_editor(commit=False))
            return True
        if key in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
            QtCore.QTimer.singleShot(0, lambda: self.finish(True))
            return True
        if self._fresh and event.text():
            self.edit.selectAll()  # the first key replaces the shown value, as in Fusion
        self._fresh = False
        copy = QtGui.QKeyEvent(
            QtCore.QEvent.KeyPress, key, event.modifiers(), event.text(), False, 1
        )
        QtWidgets.QApplication.sendEvent(self.edit, copy)
        return True

    def _value(self, text):
        """Parse the typed text: (quantity or None, expression or None)."""
        text = text.strip()
        if text.startswith("="):
            return None, text[1:].strip()
        q = App.Units.Quantity(text)
        if q.Unit == App.Units.Quantity(1.0).Unit:  # a bare number
            q = App.Units.Quantity("%r deg" % q.Value if self.is_angle() else "%r mm" % q.Value)
        return q, None

    def finish(self, commit):
        if self._done:
            return
        if commit and not self.apply():
            return  # stay open with the message, like Fusion
        self._done = True
        if self.session.editor is self:
            self.session.editor = None
        try:
            self.hide()
            self.deleteLater()
        except Exception:
            pass
        try:
            gl = self.session.gl
            if gl is not None and _is_valid(gl):
                gl.setFocus()
        except Exception:
            pass

    def apply(self):
        """Set the dimension; False (and a message) when the value is not possible."""
        text = self.edit.text()
        if text.strip() == self._current_text().strip() or not text.strip():
            return True
        doc = self.sketch.Document
        try:
            q, expression = self._value(text)
        except Exception:
            self._error("Not a value: %s" % text)
            return False
        doc.openTransaction("Edit Dimension")
        try:
            if expression is not None:
                self.sketch.setExpression(".Constraints[%d]" % self.index, expression)
                self.sketch.recompute()
            else:
                self.sketch.setDatum(self.index, q)
            if self.sketch.solve() != 0:
                raise ValueError("that value conflicts with the other dimensions/constraints")
        except Exception as exc:
            doc.abortTransaction()
            try:
                self.sketch.solve()
            except Exception:
                pass
            self._error(_short(exc))
            return False
        doc.commitTransaction()
        log("dimension set to %s" % text.strip())
        return True

    def _error(self, text):
        self.message.setText(text)
        self.message.show()
        self.adjustSize()
        self.edit.setFocus()
        self.edit.selectAll()


def _short(exc):
    text = str(exc).strip().splitlines()[0] if str(exc).strip() else exc.__class__.__name__
    return text[:160]


# -- profile shading ----------------------------------------------------------------------
class ProfileShading:
    """Light-blue fill of the closed regions of the open sketch (Fusion's profiles)."""

    FILL = (0.45, 0.77, 1.0)
    TRANSPARENCY = 0.72

    def __init__(self, session):
        from pivy import coin

        self.coin = coin
        self.session = session
        self.visible = True
        self.root = coin.SoSeparator()
        self.root.setName("SciForgeSketchProfiles")
        pick = coin.SoPickStyle()
        pick.style = coin.SoPickStyle.UNPICKABLE
        self.root.addChild(pick)
        # Drawn a hair in front of the part's faces (FreeCAD pushes those back), so a
        # sketch on a face shows its profiles; the sketch curves sit higher still.
        offset = coin.SoPolygonOffset()
        offset.factor = -1.0
        offset.units = -1.0
        self.root.addChild(offset)
        hints = coin.SoShapeHints()
        hints.vertexOrdering = coin.SoShapeHints.UNKNOWN_ORDERING
        self.root.addChild(hints)
        self.transform = coin.SoTransform()
        self.root.addChild(self.transform)
        material = coin.SoMaterial()
        material.diffuseColor.setValue(*self.FILL)
        material.emissiveColor.setValue(*[c * 0.5 for c in self.FILL])
        material.transparency.setValue(self.TRANSPARENCY)
        self.root.addChild(material)
        self.coords = coin.SoCoordinate3()
        self.faces = coin.SoIndexedFaceSet()
        self.root.addChild(self.coords)
        self.root.addChild(self.faces)
        self.count = 0
        self.attached = False

    def set_visible(self, on):
        self.visible = bool(on)
        self._attach(self.visible)

    def _attach(self, on):
        try:
            graph = self.session.view.getSceneGraph()
            if on and not self.attached:
                graph.addChild(self.root)
                self.attached = True
            elif not on and self.attached:
                graph.removeChild(self.root)
                self.attached = False
        except Exception as exc:
            warn("profile shading: %s" % exc)

    def update(self):
        from . import sketch_regions

        sketch = self.session.sketch
        placement = sketch.getGlobalPlacement()
        self.transform.translation.setValue(*placement.Base)
        self.transform.rotation.setValue(*placement.Rotation.Q)
        faces = sketch_regions.sketch_regions(sketch)
        self.count = len(faces)
        points, index = [], []
        for face in faces:
            try:
                verts, tris = face.tessellate(0.05)
            except Exception:
                continue
            base = len(points)
            points += [(v.x, v.y, 0.0) for v in verts]
            for a, b, c in tris:
                index += [base + a, base + b, base + c, -1]
        self.coords.point.setNum(0)
        self.faces.coordIndex.setNum(0)
        if points:
            self.coords.point.setValues(0, len(points), points)
            self.faces.coordIndex.setValues(0, len(index), index)
        self._attach(self.visible)

    def remove(self):
        self._attach(False)


# -- what is shown --------------------------------------------------------------------
class DisplayOptions:
    """Show Points / Dimensions / Constraints / Projected Geometries.

    FreeCAD has no switches for these, so the Sketcher's own (named) Coin nodes are
    adjusted from a Qt timer: point and projected-curve draw styles, and the
    per-constraint switchboard. FreeCAD rewrites the switchboard whenever it redraws,
    so it is checked again a few times a second while something is hidden."""

    def __init__(self, session):
        self.session = session
        self.saved_styles = {}
        self._timer = QtCore.QTimer()
        self._timer.setInterval(200)
        self._timer.timeout.connect(self.apply)

    def _hidden(self):
        return {
            name: not option(name) for name in ("points", "dimensions", "constraints", "projected")
        }

    def apply(self):
        if self.session.closed:
            return
        try:
            hidden = self._hidden()
            root = self.session.view.getSceneGraph()
            self._styles(root, hidden)
            self._constraints(root, hidden)
            if any(hidden.values()):
                if not self._timer.isActive():
                    self._timer.start()
            elif self._timer.isActive():
                self._timer.stop()
        except Exception as exc:
            self._timer.stop()
            warn("sketch display options: %s" % exc)

    def _styles(self, root, hidden):
        from pivy import coin

        names = ["CurvesExternalDrawStyle", "CurvesExternalDefiningDrawStyle"]
        wanted = {n: hidden["projected"] for n in names}
        for layer in range(4):
            wanted["PointsDrawStyle%d" % layer] = hidden["points"]
        for name, hide in wanted.items():
            node, _ = find_node(root, name)
            if node is None:
                continue
            key = name
            if hide:
                if key not in self.saved_styles:
                    self.saved_styles[key] = node.style.getValue()
                if node.style.getValue() != coin.SoDrawStyle.INVISIBLE:
                    node.style = coin.SoDrawStyle.INVISIBLE
            elif key in self.saved_styles:
                node.style = self.saved_styles.pop(key)

    def _constraints(self, root, hidden):
        node, _ = find_node(root, "ConstraintGroup")
        if node is None:
            return
        field = node.getField("enable")
        if field is None:
            return
        constraints = self.session.sketch.Constraints
        if node.getNumChildren() != len(constraints):
            return  # FreeCAD is rebuilding; next round
        wanted = []
        for c in constraints:
            show = not c.InVirtualSpace
            if c.Type in DIMENSIONAL:
                show = show and not hidden["dimensions"]
            else:
                show = show and not hidden["constraints"]
            wanted.append(show)
        text = "[%s]" % ", ".join("TRUE" if w else "FALSE" for w in wanted)
        current = field.get()
        current = current.getString() if hasattr(current, "getString") else str(current)
        if _bools(current) == wanted:
            return
        field.set(text)

    def remove(self):
        self._timer.stop()
        try:
            root = self.session.view.getSceneGraph()
            for name, style in list(self.saved_styles.items()):
                node, _ = find_node(root, name)
                if node is not None:
                    node.style = style
        except Exception:
            pass
        self.saved_styles = {}


def _bools(text):
    """Parse a Coin SoMFBool string ("[ TRUE, FALSE ]" or "TRUE")."""
    body = text.replace("[", " ").replace("]", " ").replace(",", " ").split()
    return [b.upper() in ("TRUE", "1") for b in body]


# -- circumscribed polygon ------------------------------------------------------------------
def polygon_tool_active():
    """True while FreeCAD's polygon tool is running (its "Sides" field is shown)."""
    try:
        for widget in Gui.getMainWindow().findChildren(QtWidgets.QWidget):
            if widget.metaObject().className() != "SketcherGui::TaskSketcherTool":
                continue
            if not widget.isVisible():
                return False
            for label in widget.findChildren(QtWidgets.QLabel):
                if label.isVisible() and label.text().strip().startswith("Sides"):
                    return True
            return False
    except Exception:
        pass
    return False


def finish_sketch():
    """Fusion's Finish Sketch: works with a drawing tool running or a value being typed
    (the typed value is kept). False when no sketch is open."""
    from . import commands

    sketch = editing_sketch()
    if sketch is None:
        return False
    session = current()
    if session is not None:
        session.close_editor(commit=True)
        session.polygon.stop()
    try:
        from . import sketch_pick_ui

        sketch_pick_ui.stop_waiting()
        sketch_pick_ui.close_box(accept=True)  # Fusion: finishing keeps the pattern
    except Exception as exc:
        warn("finish sketch: %s" % exc)
    _state["polygon"] = None
    label = sketch.Label
    commands.leave_edit()
    try:
        Gui.Selection.clearSelection()
    except Exception:
        pass
    log("sketch %s finished" % label)
    return True


def start_polygon(circumscribed):
    """Run FreeCAD's polygon tool (6 sides, sides changeable in the palette or with
    U/J) in Fusion's inscribed or circumscribed form."""
    _state["polygon"] = {"circumscribed": bool(circumscribed)}
    Gui.runCommand("Sketcher_CreateHexagon")
    session = current()
    if session is not None:
        session.polygon.start(circumscribed)


class PolygonPreview:
    """For the circumscribed polygon: FreeCAD's tool previews a corner at the mouse.
    Its preview curve is hidden and redrawn turned by half a side and grown so the
    mouse is on the middle of an edge, which is what the finished polygon will be."""

    POLL_MS = 30

    def __init__(self, session):
        self.session = session
        self.active = False
        self.node = None
        self.style = None
        self.saved = None
        self._timer = QtCore.QTimer()
        self._timer.setInterval(self.POLL_MS)
        self._timer.timeout.connect(self._poll)
        self._idle = 0

    def start(self, circumscribed):
        self.stop()
        if not circumscribed:
            return
        self.active = True
        self._idle = 0
        self._timer.start()

    def _poll(self):
        try:
            if self.session.closed:
                self.stop()
                return
            mode = _state["polygon"]
            if not polygon_tool_active():
                self._idle += 1
                if self._idle > 3:  # the tool ended
                    _state["polygon"] = None
                    self.stop()
                return
            self._idle = 0
            if not mode or not mode.get("circumscribed"):
                return
            self._draw()
        except Exception as exc:
            warn("polygon preview: %s" % exc)
            self.stop()

    def _draw(self):
        from pivy import coin

        root = self.session.view.getSceneGraph()
        coords, parent = find_node(root, "EditCurvesCoordinate")
        style, _ = find_node(root, "EditCurvesDrawStyle")
        if coords is None or style is None or parent is None:
            return
        if self.node is None:
            self.node = coin.SoSeparator()
            self.node.setName("SciForgePolygonPreview")
            self.draw_style = coin.SoDrawStyle()
            self.draw_style.style = coin.SoDrawStyle.LINES
            self.draw_style.lineWidth = style.lineWidth.getValue()
            self.coords = coin.SoCoordinate3()
            self.lines = coin.SoLineSet()
            self.node.addChild(self.draw_style)
            self.node.addChild(self.coords)
            self.node.addChild(self.lines)
            parent.addChild(self.node)
            self.parent = parent
        if self.style is None:
            self.style = style
            self.saved = style.style.getValue()
        self.draw_style.lineWidth = style.lineWidth.getValue()
        points = [tuple(v.getValue()) for v in coords.point.getValues(0)]
        if len(points) < 6:
            self.coords.point.setNum(0)
            self.lines.numVertices.setNum(0)
            if self.style.style.getValue() != self.saved:
                self.style.style = self.saved
            return
        if self.style.style.getValue() != coin.SoDrawStyle.INVISIBLE:
            self.style.style = coin.SoDrawStyle.INVISIBLE
        sides = len(points) // 2
        cx = sum(p[0] for p in points) / len(points)
        cy = sum(p[1] for p in points) / len(points)
        z = points[0][2]
        turn = math.pi / sides
        grow = 1.0 / math.cos(turn)
        cos_t, sin_t = math.cos(turn), math.sin(turn)
        out = []
        for i in range(0, sides * 2, 2):
            x, y = points[i][0] - cx, points[i][1] - cy
            out.append(
                (cx + grow * (cos_t * x - sin_t * y), cy + grow * (sin_t * x + cos_t * y), z)
            )
        out.append(out[0])
        self.coords.point.setValues(0, len(out), out)
        self.lines.numVertices.setValue(len(out))

    def stop(self):
        self._timer.stop()
        self.active = False
        try:
            if self.style is not None and self.saved is not None:
                self.style.style = self.saved
        except Exception:
            pass
        try:
            if self.node is not None:
                self.parent.removeChild(self.node)
        except Exception:
            pass
        self.node = None
        self.style = None
        self.saved = None

    def remove(self):
        self.stop()


def _patch_profilelib():
    """FreeCAD's polygon tool finishes through ProfileLib.RegularPolygon.makeRegularPolygon
    (Python). While SciForge's circumscribed polygon runs, the clicked point is the
    middle of an edge and the construction circle touches the edges."""
    try:
        import ProfileLib.RegularPolygon as rp
    except Exception as exc:
        warn("polygon: %s" % exc)
        return
    if _state["profilelib"] is not None:
        return
    original = rp.makeRegularPolygon
    _state["profilelib"] = (rp, original)

    def makeRegularPolygon(
        sketch,
        sides,
        centerPoint=App.Vector(0, 0, 0),
        firstCornerPoint=App.Vector(-20.00, 34.64, 0),
        construction=False,
    ):
        mode = _state["polygon"]
        if not mode or not mode.get("circumscribed"):
            return original(sketch, sides, centerPoint, firstCornerPoint, construction)
        from . import sketch_polygon

        sketch_polygon.add_polygon(sketch, sides, centerPoint, firstCornerPoint, True, construction)

    rp.makeRegularPolygon = makeRegularPolygon


def _unpatch_profilelib():
    saved = _state["profilelib"]
    _state["profilelib"] = None
    if saved is not None:
        module, original = saved
        module.makeRegularPolygon = original
