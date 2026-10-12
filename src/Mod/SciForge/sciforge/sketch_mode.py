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
NOTIFICATIONS = "User parameter:BaseApp/Preferences/NotificationArea"


def _rgba(hex_color):
    value = int(hex_color.lstrip("#"), 16)
    return (value << 8) | 0xFF


# Fusion's sketch colours, made for SciForge's dark 3D view.
BLUE = "#5cb3ff"  # curves that can still move (under-constrained)
WHITE = "#f0f0f0"  # fully constrained curves, dimension text
ORANGE = "#f5a142"  # construction
PURPLE = "#c084fc"  # projected / included geometry
GLYPH = "#9fe0a8"  # constraint symbols
DRIVEN = "#9fb4cc"  # driven (reference) dimensions

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
    # constraint glyphs: FreeCAD draws them red, which reads as an error; Fusion's are
    # quiet light symbols. Driven (reference) dimensions: FreeCAD's dark blue is
    # unreadable on the dark background.
    (VIEW, "Unsigned", "ConstrainedIcoColor", _rgba(GLYPH)),
    (VIEW, "Unsigned", "NonDrivingConstrDimColor", _rgba(DRIVEN)),
    (VIEW, "Unsigned", "CursorTextColor", _rgba(WHITE)),
    (VIEW, "Unsigned", "CursorCrosshairColor", _rgba(WHITE)),
    # FreeCAD's pop-up balloons at the bottom of the window ("Autoconstraints cause
    # redundancy. Removing them" when a line from the origin along an axis snaps twice,
    # "Sub shape not found: Sketch.?InternalFace1"...): FreeCAD's wording, nothing a
    # Fusion user can act on. SciForge says what matters next to the mouse
    # (commands.tell) or in its dialogs; the messages stay in FreeCAD's notification
    # list and the Report view. No balloon is ever open (MaxOpenNotifications 0). The
    # "non-intrusive" setting must stay on: off, FreeCAD shows its user warnings ("Wrong
    # selection"...) as blocking message boxes instead.
    (NOTIFICATIONS, "Bool", "NonIntrusiveNotificationsEnabled", True),
    (NOTIFICATIONS, "Int", "MaxOpenNotifications", 0),
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
# Tools where Enter after one typed value draws the shape (the pointer gives the rest).
ENTER_FINISHES = {
    "SciForge_SketchLine",
    "Sketcher_CreateLine",
    "Sketcher_CreateRectangle",
    "Sketcher_CreateRectangle_Center",
    "SciForge_PolygonCircumscribed",
    "SciForge_PolygonInscribed",
}
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


def construction_mode():
    """True while FreeCAD draws new curves as construction curves (its Toggle
    Construction run with nothing selected). FreeCAD keeps that mode only in C++; its
    button icon shows it, so the icon is compared with the construction icon."""
    try:
        cmd = Gui.Command.get("Sketcher_ToggleConstruction")
        actions = cmd.getAction() if cmd is not None else []
        if not actions:
            return False
        constr = Gui.getIcon("Sketcher_ToggleConstruction_Constr")
        if constr is None:
            return False
        shown = actions[0].icon().pixmap(16, 16).toImage()
        return shown == constr.pixmap(16, 16).toImage()
    except Exception:
        return False


def normal_mode():
    """Back to normal curves (Fusion starts every sketch with normal lines; FreeCAD keeps
    construction mode from the last sketch)."""
    try:
        if construction_mode() and not Gui.Selection.getSelectionEx():
            Gui.runCommand("Sketcher_ToggleConstruction")
    except Exception as exc:
        warn("sketch line type: %s" % exc)


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
    try:
        from .sketch_infer import repair_snap

        repair_snap()
    except Exception as exc:
        warn("sketch snapping: %s" % exc)
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
        _merge_recompute_step(doc, undo=True)

    def slotRedoDocument(self, doc):
        self._settled(doc, "redo")
        _merge_recompute_step(doc, undo=False)


# FreeCAD records the recompute it runs when a sketch is closed as an undo step of its
# own ("Sketch recompute", ViewProviderSketch::unsetEdit). The first Ctrl+Z after Finish
# Sketch then seemed to do nothing, or showed the part half rebuilt (with a broken
# profile: only the features after it). In Fusion one Ctrl+Z takes back the last sketch
# change with its effect on the part, so that step is undone/redone together with the
# sketch change before it.
RECOMPUTE_STEP = "Sketch recompute"
# Steps undone and redone together with the step before them: FreeCAD's recompute on
# closing a sketch, and the constraints SciForge adds right after a click
# (sketch_infer.py: Fusion adds them with the line itself).
INFER_STEP = "Inferred Constraints"
GLUED_STEPS = (RECOMPUTE_STEP, INFER_STEP)
_merging = {"busy": False}


def _glued_next(doc):
    """The first step of the redo list goes with the step before it."""
    return bool(doc.RedoNames) and doc.RedoNames[0] in GLUED_STEPS


def _merge_recompute_step(doc, undo):
    if _merging["busy"]:
        return
    try:
        if undo:
            # the step just undone is first in the redo list
            go_on = _glued_next(doc) and bool(doc.UndoNames)
        else:
            # the step just redone is first in the undo list; a step glued to it is
            # next in the redo list
            go_on = _glued_next(doc)
    except Exception:
        return
    if go_on:
        name = doc.Name
        QtCore.QTimer.singleShot(0, lambda: _one_more_step(name, undo))


def _one_more_step(doc_name, undo):
    _merging["busy"] = True
    try:
        doc = App.getDocument(doc_name)
        # several glued steps in a row (inferred constraints, then a recompute)
        for _ in range(4):
            if undo and doc.UndoNames:
                doc.undo()
            elif not undo and doc.RedoNames:
                doc.redo()
            if not _glued_next(doc) or (undo and not doc.UndoNames):
                break
        if doc.isTouched() or any("Touched" in o.State for o in doc.Objects):
            doc.recompute()
    except Exception as exc:
        warn("undo: %s" % exc)
    finally:
        _merging["busy"] = False


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


def view_widget(gl=None):
    """The 3D view widget that has the keyboard (Gui::View3DInventorViewer): a real
    keyboard sends its keys there, not to the OpenGL drawing area inside it (which gets
    the mouse). Keys sent to the drawing area go on to it as well."""
    gl = gl if gl is not None else gl_widget()
    widget = gl
    try:
        while widget is not None:
            if widget.metaObject().className() == "Gui::View3DInventorViewer":
                return widget
            widget = widget.parentWidget()
    except Exception:
        pass
    return gl


def _same(a, b):
    """The same Qt object (Python wrappers of one widget are not always the same)."""
    if a is None or b is None:
        return False
    try:
        import shiboken6

        return shiboken6.getCppPointer(a)[0] == shiboken6.getCppPointer(b)[0]
    except Exception:
        return a is b


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


def label_point(sketch, index):
    """Sketch point where FreeCAD draws the text of dimension `index` (lengths, radius,
    diameter), or None. Lengths: LabelDistance off the middle of the measured points
    (LabelPosition along them); radius/diameter: LabelDistance beyond the circle at the
    angle LabelPosition (10 means 0), as FreeCAD's SoDatumLabel does."""
    c = sketch.Constraints[index]
    if c.Type in ("Radius", "Diameter"):
        g = sketch.Geometry[c.First]
        center, radius = getattr(g, "Center", None), getattr(g, "Radius", None)
        if center is None or radius is None:
            return None
        angle = c.LabelPosition
        if angle == 10:
            if g.TypeId == "Part::GeomArcOfCircle":
                angle = (g.FirstParameter + g.LastParameter) / 2.0
            else:
                angle = 0.0
        direction = App.Vector(math.cos(angle), math.sin(angle), 0)
        return center + direction * (radius + c.LabelDistance)
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
    return (p1 + p2) * 0.5 + normal * c.LabelDistance + direction * c.LabelPosition


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
        self._enter_follow = False
        self.shading = ProfileShading(self)
        self.display = DisplayOptions(self)
        self.polygon = PolygonPreview(self)
        from .sketch_line import LineChain

        self.line = LineChain(self)
        self.infer = None
        try:
            from .sketch_infer import Inference

            # Fusion's guides, perpendicular and Ctrl while drawing (sketch_infer.py)
            self.infer = Inference(self)
        except Exception as exc:
            warn("sketch inference: %s" % exc)
        self.fillet_watch = FilletRadius(self)
        self._refresh = QtCore.QTimer()
        self._refresh.setSingleShot(True)
        self._refresh.setInterval(120)
        self._refresh.timeout.connect(self._refreshed)
        self.filter = _ViewFilter(self)
        self.keys = _KeyFilter(self)
        self.viewer = view_widget(self.gl) if self.gl is not None else None
        self._fields = []
        self._typed = None  # the value field the user typed a value into
        if self.gl is not None:
            self.gl.installEventFilter(self.filter)
        if self.viewer is not None:
            self.viewer.installEventFilter(self.keys)
        try:
            QtWidgets.QApplication.instance().focusChanged.connect(self._focus_changed)
        except Exception as exc:
            warn("sketch mode: value fields: %s" % exc)
        for name in PALETTE_DEFAULTS:
            if name != "snap":
                self.apply_option(name)
        self._palette_tries = 0
        normal_mode()
        QtCore.QTimer.singleShot(0, self._add_palette)
        self._refreshed()

    # -- changes ---------------------------------------------------------------------
    def changed(self, prop):
        if self.infer is not None:
            self.infer.invalidate()
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
        if self.infer is not None:
            try:
                self.infer.commit_signal(kind)
            except Exception as exc:
                warn("sketch inference: %s" % exc)
        if kind == "commit":
            QtCore.QTimer.singleShot(0, self._repair)
            self.line.committed()
            self.fillet_watch.committed()
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
                if self._make_driven_if_redundant(index):
                    return
                self.edit_dimension(index)
        except Exception as exc:
            warn("dimension box: %s" % exc)

    def _make_driven_if_redundant(self, index):
        """A dimension on a size the other dimensions/constraints already set would
        over-constrain the sketch (FreeCAD keeps it and the sketch turns red). Fusion
        offers a driven dimension instead: that is what it becomes here, without asking.
        True when it was made driven."""
        sketch = self.sketch
        try:
            sketch.solve()
            bad = set(sketch.RedundantConstraints) | set(sketch.ConflictingConstraints)
        except Exception:
            return False
        if index + 1 not in bad:  # FreeCAD numbers them from 1
            return False
        doc = self.doc
        doc.openTransaction("Driven Dimension")
        try:
            sketch.setDriving(index, False)
            sketch.solve()
        except Exception:
            doc.abortTransaction()
            raise
        doc.commitTransaction()
        from . import commands

        commands.tell(
            "That size is already set by other dimensions: added as a driven dimension "
            "(it shows the size, it does not change it)."
        )
        return True

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
        """Where a dimension's text is on screen (view pixels), or None."""
        try:
            local = label_point(self.sketch, index)
            if local is None:
                return None
            world = self.sketch.getGlobalPlacement().multVec(local)
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
        self.line.stop()
        if self.infer is not None:
            self.infer.reset()
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

    def _focus_changed(self, old, new):
        """A drawing tool's on-screen value field took the keyboard: Enter and Esc typed
        there must work as in Fusion too (FreeCAD keeps those keys in the field)."""
        try:
            if self.closed or not isinstance(new, QtWidgets.QAbstractSpinBox):
                return
            if not self._is_field(new):
                return
            new.installEventFilter(self.keys)  # Qt keeps one copy; it runs first
            self._fields = [f for f in self._fields if _is_valid(f) and not _same(f, new)]
            self._fields.append(new)
            if self._typed is not None and not _same(self._typed, new):
                self._typed = None  # another field: nothing typed into it yet
        except Exception as exc:
            warn("sketch value field: %s" % exc)

    def _is_field(self, widget):
        """One of FreeCAD's on-screen value fields of this 3D view."""
        try:
            mdi = self.viewer.parentWidget() if self.viewer is not None else None
            return mdi is not None and _same(widget.parentWidget(), mdi)
        except Exception:
            return False

    def _focused_field(self):
        widget = QtWidgets.QApplication.focusWidget()
        if isinstance(widget, QtWidgets.QAbstractSpinBox) and self._is_field(widget):
            return widget
        return None

    def field_key(self, field, event):
        """A key typed into an on-screen value field of a drawing tool."""
        key = event.key()
        if key == QtCore.Qt.Key_Escape:
            # Fusion: Esc stops the tool, also right after typing a value (FreeCAD keeps
            # Esc in the field for two seconds after a digit, then resets the shape).
            if not event.isAutoRepeat():
                self.escape()
            return True
        if key in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
            if self._enter_follow or event.modifiers() & QtCore.Qt.ControlModifier:
                return False
            if not self._finishes_on_enter():
                return False
            self._accept_fields(field)
            return True
        if _is_value_key(event) or key in (QtCore.Qt.Key_Backspace, QtCore.Qt.Key_Delete):
            self._typed = field  # the user is typing a value here
            return False
        mods = event.modifiers() & ~(QtCore.Qt.ShiftModifier | QtCore.Qt.KeypadModifier)
        letter = event.text()[:1].isalpha() and mods == QtCore.Qt.NoModifier
        if letter and not event.isAutoRepeat() and not _same(self._typed, field):
            # Fusion: a tool's key switches tools at any time. FreeCAD would type the
            # letter into the field for two seconds after any value or Enter (a unit);
            # here only after a value typed into this field.
            command = _sketch_key(event)
            if command is not None:
                QtCore.QTimer.singleShot(0, lambda: _run(command))
                return True
            name = _swallowed_shortcut(event)
            if name is not None:
                QtCore.QTimer.singleShot(0, lambda: _run_shortcut(name))
                return True
        return False

    def _finishes_on_enter(self):
        from . import recent

        last = recent.last()
        if last is None or last[0] not in ENTER_FINISHES:
            return False
        return self.gl is not None and self.gl.cursor().shape() != QtCore.Qt.ArrowCursor

    def _accept_fields(self, field):
        """FreeCAD's Ctrl+Enter in a value field: every field of the shape keeps what it
        shows (the typed value, or where the pointer is) and the shape is drawn."""
        self._enter_follow = True
        try:
            for kind in (QtCore.QEvent.KeyPress, QtCore.QEvent.KeyRelease):
                event = QtGui.QKeyEvent(kind, QtCore.Qt.Key_Return, QtCore.Qt.ControlModifier, "\r")
                QtWidgets.QApplication.sendEvent(field, event)
        finally:
            self._enter_follow = False

    def enter_pressed(self):
        """Enter after typing a value while drawing. FreeCAD keeps the value and moves to
        the next on-screen field (the angle of a line, the height of a rectangle); Fusion
        draws the shape there, the pointer giving the rest. So when Enter did not finish
        the shape, the fields are accepted as they are for the user (Tab still goes to
        the next field). Enter typed in a field itself: field_key."""
        if self._enter_follow or self.closed:
            return
        try:
            if not self._finishes_on_enter():
                return
            count = len(self.sketch.Geometry)
            QtCore.QTimer.singleShot(0, lambda: self._finish_typed(count))
        except Exception as exc:
            warn("sketch Enter: %s" % exc)

    def _finish_typed(self, count):
        if self.closed or self.gl is None or not _is_valid(self.gl):
            return
        try:
            if len(self.sketch.Geometry) != count:
                return  # Enter finished the shape already
            if self.gl.cursor().shape() == QtCore.Qt.ArrowCursor:
                return
            field = self._focused_field()
            if field is not None:
                self._accept_fields(field)
                return
            self._enter_follow = True
            try:
                mods = QtCore.Qt.NoModifier
                for kind in (QtCore.QEvent.KeyPress, QtCore.QEvent.KeyRelease):
                    event = QtGui.QKeyEvent(kind, QtCore.Qt.Key_Return, mods, "\r")
                    QtWidgets.QApplication.sendEvent(self.gl, event)
            finally:
                self._enter_follow = False
        except Exception as exc:
            warn("sketch Enter: %s" % exc)

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
                    if not c.Driving:
                        from . import commands

                        commands.tell(
                            "A driven dimension only shows the size: change the dimensions "
                            "that set it."
                        )
                        return True
                    QtCore.QTimer.singleShot(0, lambda: self.edit_dimension(index, pos))
                    return True
        return False

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.line.stop()
        if self.infer is not None:
            try:
                self.infer.close()
            except Exception as exc:
                warn("sketch mode: %s" % exc)
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
        try:
            QtWidgets.QApplication.instance().focusChanged.disconnect(self._focus_changed)
        except Exception:
            pass
        hooked = [(self.gl, self.filter), (self.viewer, self.keys)]
        hooked += [(field, self.keys) for field in self._fields]
        for widget, event_filter in hooked:
            if widget is not None and _is_valid(widget):
                try:
                    widget.removeEventFilter(event_filter)
                except Exception:
                    pass
        self._fields = []
        self._typed = None
        try:
            if self.palette is not None:
                self.palette.remove()
        except Exception:
            pass
        self.palette = None


class _KeyFilter(QtCore.QObject):
    """Keys while a sketch is open. On the 3D view widget (where a real keyboard sends
    them; keys aimed at the drawing area inside it arrive here too) and on FreeCAD's
    on-screen value fields while a drawing tool runs (they take the keyboard, and FreeCAD
    passes most other keys on to the view). Never blocks FreeCAD's own handling except
    for the keys Fusion gives another meaning."""

    def __init__(self, session):
        super().__init__()
        self.session = session

    def eventFilter(self, obj, event):
        try:
            session = self.session
            if session.closed:
                return False
            kind = event.type()
            if kind not in (QtCore.QEvent.ShortcutOverride, QtCore.QEvent.KeyPress):
                return False
            if isinstance(obj, QtWidgets.QAbstractSpinBox):
                if kind == QtCore.QEvent.KeyPress:
                    return session.field_key(obj, event)
                return False
            if kind == QtCore.QEvent.ShortcutOverride:
                # Typing a value: keys go into the value box / FreeCAD's on-screen fields,
                # not to shortcuts (FreeCAD's 0-6 turn the view, M moves...).
                if session.editor is not None or _is_value_key(event):
                    event.accept()
                    return True
                if _sketch_key(event) is not None:
                    event.accept()  # the key comes back as a KeyPress below
                    return True
                return False
            key = event.key()
            if session.editor is not None:
                return session.editor.key(event)
            command = _sketch_key(event)
            if command is not None:
                QtCore.QTimer.singleShot(0, lambda: _run(command))
                return True
            if key in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
                from . import sketch_pick_ui

                if sketch_pick_ui.on_enter():
                    return True
                session.enter_pressed()
                return False
            if key == QtCore.Qt.Key_Escape:
                if not event.isAutoRepeat():
                    # Right away (a Qt key event, not a Coin callback): a timer could
                    # fire after the next key and stop the tool that key started.
                    session.escape()
                return False
            name = _swallowed_shortcut(event)
            if name is not None:
                QtCore.QTimer.singleShot(0, lambda: _run_shortcut(name))
                return True
        except Exception as exc:
            warn("sketch keys: %s" % exc)
        return False


class _ViewFilter(QtCore.QObject):
    """The mouse on the 3D view's drawing area while a sketch is open (keys: _KeyFilter).
    Never blocks FreeCAD's own handling except for the right click (marking menu)."""

    def __init__(self, session):
        super().__init__()
        self.session = session
        self.right_pressed = None

    def eventFilter(self, obj, event):
        try:
            session = self.session
            if session.closed:
                return False
            # Fusion's inference (sketch_infer.py) may hand FreeCAD a copy of the event
            # with the point moved onto a guide; the copy comes back through here.
            if session.infer is not None and session.infer.mouse(obj, event):
                return True
            kind = event.type()
            if kind == QtCore.QEvent.MouseButtonPress:
                session.last_press = event.position().toPoint()
                if session.editor is not None and not session.editor.underMouse():
                    QtCore.QTimer.singleShot(0, lambda: session.close_editor(commit=True))
                if event.button() == QtCore.Qt.RightButton:
                    # Fusion: a right click in a sketch opens the sketch's marking menu
                    self.right_pressed = event.globalPosition().toPoint()
                    return True
            elif kind == QtCore.QEvent.MouseButtonRelease:
                if event.button() == QtCore.Qt.RightButton and self.right_pressed is not None:
                    start, self.right_pressed = self.right_pressed, None
                    pos = event.globalPosition().toPoint()
                    if (pos - start).manhattanLength() <= 6:
                        from . import sketch_marking

                        QtCore.QTimer.singleShot(0, lambda: sketch_marking.open_at(pos))
                    return True
            elif kind == QtCore.QEvent.MouseButtonDblClick:
                if event.button() == QtCore.Qt.LeftButton:
                    return session.double_clicked(event.position().toPoint())
        except Exception as exc:
            warn("sketch view: %s" % exc)
        return False


# Keys that mean something else in a sketch than on the part (Fusion): M moves/copies
# sketch curves, Del deletes the selected sketch curves (whatever the part's Move/Delete
# commands do), Ctrl+C / Ctrl+X / Ctrl+V copy, cut and paste sketch curves (FreeCAD's
# own keys for them only work with its menu bar, which SciForge hides).
NONE, CTRL = QtCore.Qt.NoModifier, QtCore.Qt.ControlModifier
SKETCH_KEYS = {
    (QtCore.Qt.Key_M, NONE): "SciForge_SketchMove",
    (QtCore.Qt.Key_Delete, NONE): "Std_Delete",
    (QtCore.Qt.Key_C, CTRL): "Sketcher_CopyClipboard",
    (QtCore.Qt.Key_X, CTRL): "Sketcher_Cut",
    (QtCore.Qt.Key_V, CTRL): "paste",
}


LABELS = {"SciForge_SketchMove": "Move/Copy"}
NEEDS_CURVES = {"Sketcher_CopyClipboard": "Ctrl+C", "Sketcher_Cut": "Ctrl+X"}


def _sketch_key(event):
    if event.isAutoRepeat():
        return None
    mods = event.modifiers() & ~QtCore.Qt.KeypadModifier
    for (key, wanted), command in SKETCH_KEYS.items():
        if event.key() == key and mods == wanted:
            return command
    return None


def _swallowed_shortcut(event):
    """A SciForge key (L, C, D...) that reached the 3D view as a plain key press. Qt runs
    shortcuts before keys arrive, so this only happens when a drawing tool's value field
    had the keyboard and FreeCAD passed the key on to the view: Fusion still switches to
    that tool."""
    if event.isAutoRepeat() or _is_value_key(event):
        return None
    if event.key() in (QtCore.Qt.Key_Shift, QtCore.Qt.Key_Control, QtCore.Qt.Key_Alt):
        return None
    try:
        from . import shortcuts

        mods = event.modifiers() & ~QtCore.Qt.KeypadModifier
        combo = QtCore.QKeyCombination(mods, QtCore.Qt.Key(event.key()))
        text = QtGui.QKeySequence(combo).toString(QtGui.QKeySequence.PortableText)
        return shortcuts.bound_keys().get(shortcuts.normalise(text))
    except Exception:
        return None


def _run_shortcut(name):
    """What the shortcut itself does (shortcuts.py): the command, remembered for Repeat."""
    try:
        from . import recent

        cmd = Gui.Command.get(name)
        if cmd is None or (hasattr(cmd, "isActive") and not cmd.isActive()):
            return
        label = name
        try:
            label = (cmd.getInfo().get("menuText") or name).replace("&", "")
        except Exception:
            pass
        recent.record(name, label)
        Gui.runCommand(name)
    except Exception as exc:
        warn("%s: %s" % (name, exc))


def _run(command):
    try:
        from . import commands, recent

        if command == "paste":
            paste()
            return
        if command in NEEDS_CURVES:
            sketch = editing_sketch()
            if sketch is None or not _selected_curves(sketch):
                commands.tell("Select sketch curves first, then %s." % NEEDS_CURVES[command])
                return
        if command in LABELS:
            recent.record(command, LABELS[command])
        Gui.runCommand(command)
    except Exception as exc:
        warn("%s: %s" % (command, exc))


def _selected_curves(sketch):
    from .sketch_tools_ui import selected_curves

    return selected_curves(sketch)


def paste():
    """Ctrl+V in a sketch: FreeCAD pastes the copied curves on top of the originals;
    Fusion then lets you place them. The pasted curves are selected and Move starts:
    click a base point, then where they go (Esc leaves them where they are)."""
    from . import commands

    sketch = editing_sketch()
    if sketch is None:
        return
    before = len(sketch.Geometry)
    Gui.runCommand("Sketcher_Paste")
    new = list(range(before, len(sketch.Geometry)))
    if not new:
        commands.tell("Nothing to paste: select sketch curves and press Ctrl+C first.")
        return
    Gui.Selection.clearSelection()
    for index in new:
        Gui.Selection.addSelection(sketch.Document.Name, sketch.Name, "Edge%d" % (index + 1))

    def place():
        _run("Sketcher_Translate")
        # said once the tool's panel has settled (its start hid an earlier tip)
        QtCore.QTimer.singleShot(
            150, lambda: commands.tell("Pasted: click a base point, then where the copy goes.")
        )

    QtCore.QTimer.singleShot(0, place)


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
        """A key pressed on the 3D view while the box is open: it goes into the box.
        With the keyboard in the box itself, the keys the box does not use (Esc, arrows
        up/down...) come here on their way up: never sent back to it (they would come
        straight back here, again and again)."""
        key = event.key()
        own = _is_valid(self.edit) and self.edit.hasFocus()
        if key == QtCore.Qt.Key_Escape:
            QtCore.QTimer.singleShot(0, lambda: self.session.close_editor(commit=False))
            return True
        if key in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
            if not own:  # in the box, Enter already finished it (returnPressed)
                QtCore.QTimer.singleShot(0, lambda: self.finish(True))
            return True
        if own:
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
        """Parse the typed text: (quantity or None, expression or None). Raises
        ValueError with a message for the box when the value is not possible."""
        text = text.strip()
        if text.startswith("="):
            return None, text[1:].strip()
        try:
            q = App.Units.Quantity(text)
        except Exception:
            raise ValueError("Not a value: %s" % text)
        angle = self.is_angle()
        if q.Unit == App.Units.Quantity(1.0).Unit:  # a bare number (or 10+5*2)
            q = App.Units.Quantity("%r deg" % q.Value if angle else "%r mm" % q.Value)
        wanted = App.Units.Quantity("1 deg" if angle else "1 mm").Unit
        if q.Unit != wanted:
            raise ValueError(
                "Type %s, e.g. %s" % (("an angle", "30") if angle else ("a length", "25"))
            )
        value = q.getValueAs("deg" if angle else "mm").Value
        # Fusion refuses sizes of 0 or less: a dimension of 0 collapses the curve (FreeCAD's
        # solver then fails and the sketch breaks).
        if value <= 1e-7:
            raise ValueError("The value must be more than 0.")
        if angle and value >= 360.0:
            raise ValueError("The angle must be less than 360 deg.")
        try:
            current = self.sketch.getDatum(self.index).Value
        except Exception:
            current = 1.0
        if current < 0 and self._constraint().Type in ("DistanceX", "DistanceY", "Angle"):
            # FreeCAD keeps the direction in the sign; the user types the size.
            q = App.Units.Quantity("%r %s" % (-value, "deg" if angle else "mm"))
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
        except Exception as exc:
            self._error(str(exc) if isinstance(exc, ValueError) else "Not a value: %s" % text)
            return False
        if not self._constraint().Driving:
            self._error(
                "A driven dimension only shows the size: change the dimensions that set it."
            )
            return False
        doc.openTransaction("Edit Dimension")
        try:
            if expression is not None:
                self.sketch.setExpression(".Constraints[%d]" % self.index, expression)
                self.sketch.recompute()
            else:
                self.sketch.setDatum(self.index, q)
            if self.sketch.solve() != 0:
                raise ValueError(CONFLICT)
        except Exception as exc:
            doc.abortTransaction()
            try:
                self.sketch.solve()
            except Exception:
                pass
            self._error(_plain(exc))
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


CONFLICT = "That value does not fit the other dimensions and constraints of the sketch."

# FreeCAD's solver texts, said the way a Fusion user needs them.
PLAIN = (
    ("conflicting", CONFLICT),
    ("Negative datum", "The value must be more than 0."),
    ("is invalid", "That value is not possible here."),
    ("redundant", "That size is already set by other dimensions."),
)


def _plain(exc):
    text = _short(exc)
    for needle, said in PLAIN:
        if needle.lower() in text.lower():
            return said
    return text


# -- sketch fillet radius -------------------------------------------------------------------
FILLET_COMMANDS = ("Sketcher_CreateFillet", "Sketcher_CompCreateFillets")


class FilletRadius:
    """Fusion's sketch fillet asks for the radius. FreeCAD's fillet tool rounds the
    clicked corner with a radius taken from the mouse; the new arc then gets a radius
    dimension and the value box opens on it (type 5, Enter)."""

    def __init__(self, session):
        self.session = session
        self.seen = len(session.sketch.Geometry)

    def committed(self):
        QtCore.QTimer.singleShot(0, self._check)

    def _check(self):
        session = self.session
        if session.closed:
            return
        try:
            import Sketcher

            from . import recent

            sketch = session.sketch
            count = len(sketch.Geometry)
            new = list(range(self.seen, count))
            self.seen = count
            last = recent.last()
            if not new or last is None or last[0] not in FILLET_COMMANDS:
                return
            arcs = [i for i in new if sketch.Geometry[i].TypeId == "Part::GeomArcOfCircle"]
            if len(arcs) != 1 or session.editor is not None:
                return
            arc = arcs[0]
            doc = session.doc
            doc.openTransaction("Fillet Radius")
            try:
                index = sketch.addConstraint(
                    Sketcher.Constraint("Radius", arc, sketch.Geometry[arc].Radius)
                )
                sketch.solve()
            except Exception:
                doc.abortTransaction()
                raise
            doc.commitTransaction()
            if not session._make_driven_if_redundant(index):
                session.edit_dimension(index)
        except Exception as exc:
            warn("fillet radius: %s" % exc)


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
    _tell_broken_features(sketch)
    return True


def _tell_broken_features(sketch):
    """Features built on the sketch that could not be rebuilt after the edit (a profile
    left open, a projected edge gone): say so next to the mouse instead of leaving the
    part silently unchanged (Fusion marks them in the timeline and shows a message)."""
    try:
        broken = []
        for obj in sketch.Document.Objects:
            if obj is sketch or sketch not in obj.OutListRecursive:
                continue
            state = list(obj.State)
            if "Invalid" in state or "Error" in state:
                broken.append(obj.Label)
        if broken:
            from . import commands

            commands.tell(
                "%s cannot be rebuilt from %s any more (its profile is open or gone). "
                "Edit the sketch again, or press Ctrl+Z." % (", ".join(broken), sketch.Label)
            )
    except Exception as exc:
        warn("finish sketch: %s" % exc)


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
        # FreeCAD's edit nodes are looked up fresh on every poll and never kept: FreeCAD
        # deletes them when the sketch closes, and touching a deleted node crashes FreeCAD.
        if self.node is not None:
            mine, _ = find_node(root, "SciForgePolygonPreview")
            if mine is None:  # FreeCAD rebuilt its edit scene: our overlay went with it
                self.node = None
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
        if self.saved is None:
            self.saved = style.style.getValue()
        self.draw_style.lineWidth = style.lineWidth.getValue()
        points = [tuple(v.getValue()) for v in coords.point.getValues(0)]
        if len(points) < 6:
            self.coords.point.setNum(0)
            self.lines.numVertices.setNum(0)
            if style.style.getValue() != self.saved:
                style.style = self.saved
            return
        if style.style.getValue() != coin.SoDrawStyle.INVISIBLE:
            style.style = coin.SoDrawStyle.INVISIBLE
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
        # Only while the sketch is still open: once it has closed, FreeCAD has deleted its
        # edit nodes (with our overlay under them), and writing to a deleted node crashed
        # FreeCAD (found by the ribbon sweep scenario, faulthandler stack in MEMORY.md).
        if editing_sketch() is self.session.sketch:
            try:
                root = self.session.view.getSceneGraph()
                style, _ = find_node(root, "EditCurvesDrawStyle")
                if style is not None and self.saved is not None:
                    style.style = self.saved
                mine, parent = find_node(root, "SciForgePolygonPreview")
                if mine is not None and parent is not None:
                    parent.removeChild(mine)
            except Exception:
                pass
        self.node = None
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
