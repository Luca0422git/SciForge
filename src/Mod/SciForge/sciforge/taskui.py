# SPDX-License-Identifier: LGPL-2.1-or-later
"""Building blocks for SciForge's Fusion-style command dialogs.

- DistanceField: unit-aware number field (types "5", "5 mm", "0.2 in", "=width*2"),
  optionally bound to a property so expressions/parameters work like in FreeCAD.
- ArrowDragger: the arrow you drag in the 3D view to set a distance (Coin3D; its look and
  its screen size are handle_look's).
- ArrowValueBox: the small value box next to an arrow (Fusion shows the distance there
  while you drag, and you can type a new one in it).
- BoxCarrier: what any drag handle (an arrow, a turning disc, a ball on a line) needs to
  carry such a box: where its grabbable part is, and a hook its poll calls.
- ValueBoxes: a dialog's boxes, one per handle, kept while the handles are rebuilt, and
  which one a number typed over the 3D view goes to.
- TypeOverView: digits typed with the mouse over the 3D view go into that box (Fusion),
  not to FreeCAD's view keys.
- Panel: a task-dialog base that wraps the edit in one undo step: OK keeps it,
  Cancel/Esc removes it again, like Fusion.
"""

import math
import re
import time
import weakref

import FreeCAD as App
import FreeCADGui as Gui

from . import drag_guard, increments, log, warn
from .compat import QtCore, QtGui, QtWidgets

_OPEN = {"dialog": None}


def current():
    """The SciForge task dialog that is open now (it has finish()), or None."""
    dialog = _OPEN["dialog"]
    if dialog is None or getattr(dialog, "_closed", False) or not Gui.Control.activeDialog():
        _OPEN["dialog"] = None
        return None
    return dialog


def set_current(dialog):
    _OPEN["dialog"] = dialog


# Editors for existing features: {type key: function(obj)}. The type key is the
# FreeCAD TypeId ("PartDesign::Fillet") or "SciForge::<SciForgeType>" for SciForge's
# own Python features. Feature modules declare EDITORS = {...}; commands.py collects
# them. The timeline and the browser open features with edit_object().
EDITORS = {}
# Extra entries of the timeline's right-click menu: {type key: [(text, fn(obj), enabled(obj))]}
# (a Derive's Update Derive / Break Link). Modules declare MENU_EXTRAS = {...}.
MENU_EXTRAS = {}


def dialog_button(role):
    """The enabled OK ("accept") or Cancel/Close ("reject") button of the open task
    dialog, or None. FreeCAD keeps them in the TaskEditControl's button box."""
    want = (
        QtWidgets.QDialogButtonBox.AcceptRole
        if role == "accept"
        else QtWidgets.QDialogButtonBox.RejectRole
    )
    if not Gui.Control.activeDialog():
        return None
    found = None
    for box in Gui.getMainWindow().findChildren(QtWidgets.QDialogButtonBox):
        parent = box.parentWidget()
        if parent is None or parent.metaObject().className() != "Gui::TaskView::TaskEditControl":
            continue
        for button in box.buttons():
            if box.buttonRole(button) == want and button.isEnabled():
                if button.isVisible():
                    return button
                found = found or button  # the Tasks tab may be hidden behind the Model tab
    return found


def press_dialog_button(role):
    """Click the open dialog's OK or Cancel, exactly as a mouse click on it does (the
    marking menu offers them, as Fusion's does while a command is open)."""
    try:
        button = dialog_button(role)
        if button is None:
            return False
        button.click()
        return True
    except Exception as exc:
        warn("could not press %s: %s" % ("OK" if role == "accept" else "Cancel", exc))
        return False


def type_key(obj):
    kind = getattr(obj, "SciForgeType", "")
    return "SciForge::" + kind if kind else obj.TypeId


def edit_object(obj):
    """Open the right dialog for an existing feature (Fusion: double-click in the
    timeline). Finishes whatever is open first."""
    from . import commands

    if obj is None or not commands.finish_open_dialog():
        return
    try:
        editor = EDITORS.get(type_key(obj))
    except ReferenceError:
        return  # it was the unfinished step of the dialog that was just cancelled
    from . import edit_rollback

    doc = obj.Document
    # Fusion: the marker goes to the step being edited. A step after the marker: rolled
    # forward to before its editor opens, and back once nothing is edited (as before). A
    # step before it: a SciForge dialog rolls back to it inside its undo step
    # (edit_rollback.take), so Ctrl+Z after the edit leaves the marker where it was.
    back = edit_rollback.roll_forward(obj)
    edit_rollback.request(obj)
    _unselect_whole(obj)
    try:
        if editor is not None:
            editor(obj)
        else:
            Gui.ActiveDocument.setEdit(obj.Name)
    except Exception as exc:
        warn("could not edit %s: %s" % (obj.Label, exc))
    edit_rollback.unclaimed(doc)
    if back is not None:
        edit_rollback.back_later(doc.Name, *back)


def _unselect_whole(obj):
    """The timeline click selected the step itself. Rolled to it, the step is shown; a click
    on an object FreeCAD has selected whole selects its parent (the body), so the first click
    on the step's faces in its dialog picked the whole body."""
    try:
        for sel in Gui.Selection.getSelectionEx("", 0):
            for sub in list(sel.SubElementNames) or [""]:
                found = sel.Object.getSubObject(sub, retType=1) if sub else sel.Object
                if found is obj and not sub.split(".")[-1]:
                    Gui.Selection.removeSelection(sel.Object.Document.Name, sel.Object.Name, sub)
    except Exception as exc:
        warn("could not clear the selection: %s" % exc)


_BARE_NUMBER = re.compile(r"^\s*[+-]?(\d+([.,]\d*)?|[.,]\d+)([eE][+-]?\d+)?\s*$")


class DistanceField:
    """A plain number typed in the box is in the box's own unit (mm, or degrees), like
    Fusion. FreeCAD's box reads it in the unit it *shows*: after a value below 0.1 mm it
    showed "50.00 µm", and the next "4" typed became 4 µm (found by the fillet QA)."""

    def __init__(self, value=0.0, unit="mm", on_change=None):
        self.unit = unit
        self.widget = Gui.UiLoader().createWidget("Gui::QuantitySpinBox")
        self.widget.setProperty("unit", unit)
        self.widget.setProperty("minimum", -1e9)
        self.widget.setProperty("maximum", 1e9)
        self.widget.setProperty("rawValue", float(value))
        # autoNormalize stays on: switched off, the box re-read its own rounded text when
        # it lost the focus ("12.57 mm" for 4*pi), a silent loss of precision. The cost: the
        # first Enter after a sum ("2*0.25") only evaluates it, a second Enter is OK.
        self._on_change = on_change
        self._quiet = False
        self._typed = None  # text typed since the box was last settled
        edit = self.widget.findChild(QtWidgets.QLineEdit)
        if edit is not None:
            edit.textEdited.connect(self._edited)
        self.widget.editingFinished.connect(self._settle)
        self.widget.valueChanged.connect(self._changed)

    def bind(self, obj, prop):
        """Bind to obj.prop so typed expressions (=Parameters.width) are stored on it."""
        try:
            self._binding = Gui.ExpressionBinding(self.widget).bind(obj, prop)
        except Exception as exc:
            warn("expression binding unavailable: %s" % exc)

    def value(self):
        typed = self._bare()
        return typed if typed is not None else float(self.widget.property("rawValue"))

    def set_value(self, value):
        self._typed = None
        self._quiet = True
        try:
            self.widget.setProperty("rawValue", float(value))
        finally:
            self._quiet = False

    def _bare(self):
        if self._typed is None or not _BARE_NUMBER.match(self._typed):
            return None
        return float(self._typed.strip().replace(",", "."))

    def _edited(self, text):
        self._typed = text

    def _settle(self):
        """Editing finished: a plain number typed counts in the box's unit. Only a value
        FreeCAD read in another unit is corrected; nothing is done while the dialog closes
        (leaving the box then also "finishes" it, after the value was taken)."""
        typed, self._typed = self._bare(), None
        if typed is None:
            return
        try:
            if not self.widget.isVisible():
                return
            if abs(float(self.widget.property("rawValue")) - typed) <= 1e-12:
                return
        except RuntimeError:
            return  # the box went with its dialog
        try:
            self.set_value(typed)
            owner = getattr(self._on_change, "__self__", None)
            if self._on_change is not None and not getattr(owner, "_closed", False):
                self._on_change(typed)
        except Exception as exc:
            warn("value box: %s" % exc)

    def _changed(self, *_):
        if not self._quiet and self._on_change:
            self._on_change(self.value())

    def parse(self, text):
        """The value of a plain number typed for this field somewhere else (the box next to
        an arrow): "25", "2,5", "1 in", "30 deg". A bare number is in the field's own unit,
        like a number typed in the field. ValueError says what to type instead."""
        text = (text or "").strip()
        if _BARE_NUMBER.match(text):
            return float(text.replace(",", "."))
        try:
            quantity = App.Units.Quantity(text)
        except Exception:
            raise ValueError("'%s' is not a value." % text)
        angle = self.unit == "deg"
        if quantity.Unit == App.Units.Quantity(1.0).Unit:
            return float(quantity.Value)
        if quantity.Unit != App.Units.Quantity("1 " + self.unit).Unit:
            raise ValueError(
                "Type %s, for example %s." % (("an angle", "30") if angle else ("a length", "25"))
            )
        return float(quantity.getValueAs(self.unit).Value)

    def take(self, value):
        """Show `value` and tell the dialog, as if it had been typed in the field."""
        self.set_value(value)
        if self._on_change:
            self._on_change(float(value))


def view_widget():
    """The OpenGL widget of the active 3D view (it gets the mouse and the keys), or None."""
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


class PollOnMove:
    """Runs a drag handle's poll right after each mouse move over the 3D view while a mouse
    button is held, instead of up to POLL_MS later on its timer: the dialog and the value box
    take a dragged handle's new value at once (Luca, 2026-10-22: "the angle dragger doesn't
    even update"). Coin moves the handle itself while it handles the move; the poll queued
    here runs just after that. At most one poll is queued at a time (a mouse can send moves
    faster than a poll takes). The handle's timer keeps running (hover, a lost release).
    remove() with the handle."""

    def __init__(self, poll):
        self.poll = poll
        self.queued = False
        self.alive = True
        guard = self

        class MoveFilter(QtCore.QObject):
            def eventFilter(self, obj, event):
                try:
                    if (
                        guard.alive
                        and not guard.queued
                        and event.type() == QtCore.QEvent.MouseMove
                        and event.buttons() != QtCore.Qt.NoButton
                    ):
                        guard.queued = True
                        QtCore.QTimer.singleShot(0, guard._run)
                except Exception:
                    pass
                return False

        self.filter = MoveFilter()
        self.widget = view_widget()
        if self.widget is not None:
            self.widget.installEventFilter(self.filter)

    def _run(self):
        self.queued = False
        if not self.alive:
            return
        try:
            self.poll()
        except Exception as exc:
            warn("drag: %s" % exc)

    def remove(self):
        self.alive = False
        widget, self.widget = self.widget, None
        if widget is not None:
            try:
                widget.removeEventFilter(self.filter)
            except Exception:
                pass  # the view went with its document


def poll_on_move(poll):
    """A PollOnMove for a handle's poll, or None when the 3D view is not there."""
    try:
        return PollOnMove(poll)
    except Exception as exc:
        warn("drag: %s" % exc)
        return None


def drop_poll_on_move(handle):
    mover = getattr(handle, "_move_poll", None)
    handle._move_poll = None
    if mover is not None:
        mover.remove()


def mm_per_pixel(view, point):
    """How many millimetres one pixel of the 3D view covers at the 3D `point`: from the
    camera (orthographic: its height over the view's height; perspective: the width of the
    view at the point's depth), so a handle can be given a size that looks the same on the
    screen whatever the part is. Falls back to measuring two pixels of the view."""
    try:
        from pivy import coin

        camera = view.getCameraNode()
        gl = view_widget()
        ratio = (gl.devicePixelRatioF() if gl is not None else 1.0) or 1.0
        height_px = max(float(view.getSize()[1]) / ratio, 1.0)
        if camera.isOfType(coin.SoOrthographicCamera.getClassTypeId()):
            height = float(camera.height.getValue())
        else:
            position = App.Vector(*camera.position.getValue().getValue())
            look = App.Vector(view.getViewDirection())
            depth = max((App.Vector(point) - position).dot(look), 1e-6)
            height = 2.0 * depth * math.tan(float(camera.heightAngle.getValue()) / 2.0)
        if height > 0:
            return height / height_px
    except Exception:
        pass
    try:
        x, y = view.getPointOnViewport(App.Vector(point))
        a = view.getPoint((int(x), int(y)))
        b = view.getPoint((int(x) + 10, int(y)))
        return max((a - b).Length / 10.0, 1e-6)
    except Exception:
        return 0.1


def handle_size_at(view, point, pixels=None, lo=None, hi=None):
    """The size (mm) of a drag arrow at the 3D `point` that looks the same on the screen
    whatever the part is (arrow_box_core.handle_size, with the view's own scale).
    `hi` (mm) caps it for a short picked edge, `lo` keeps it visible on a tiny part."""
    from . import arrow_box_core

    pixels = arrow_box_core.ARROW_PIXELS if pixels is None else pixels
    lo = arrow_box_core.MIN_SIZE if lo is None else lo
    return arrow_box_core.handle_size(mm_per_pixel(view, point), pixels, lo, hi)


def on_top_root(coin, place):
    """The root node of a drag handle: drawn over the part and grabbable through it, as
    Fusion's manipulators are (Luca, 2026-10-13: "arrows for dragging get occluded by
    bodies"). Coin's SoAnnotation renders its children after everything else without
    depth testing, so the arrow shows in front of a body that is nearer to the camera;
    its pick style SHAPE_ON_TOP sorts the handle's pick in front of that body's, so a
    press on the visible arrow starts the drag instead of selecting the face over it.
    `place` (the handle's SoTransform) stays child 0: the scenarios read the handle's
    position from `root.getChild(0).translation`."""
    root = coin.SoAnnotation()
    root.addChild(place)
    pick = coin.SoPickStyle()
    pick.style = coin.SoPickStyle.SHAPE_ON_TOP
    root.addChild(pick)
    return root


BOX_TAKEN = {"time": 0.0}  # when a click elsewhere last took a value typed in an arrow's box


def box_click_taken(seconds=0.5):
    """True just after a click outside an arrow's value box took what was typed in it. That
    click only leaves the box (Fusion): the value can move the arrow away from under the
    mouse, and the click must not count as a pick of what is under it then."""
    return time.time() - BOX_TAKEN["time"] < seconds


def _alive(widget):
    """False once Qt deleted the widget (its 3D view closed with the document)."""
    try:
        widget.objectName()
        return True
    except (RuntimeError, AttributeError):
        return False


class ArrowValueBox(QtWidgets.QLineEdit):
    """The value box next to a drag arrow in the 3D view, like Fusion's: it shows exactly
    what the dialog's field shows (with units) and moves with the arrow while it is
    dragged. Click it and type a value or a formula; Enter (or clicking elsewhere) takes
    it like the dialog's field does. Esc cancels the command, as it does anywhere else.
    It never takes the keyboard by itself, and it never covers the arrow's heads.

    text():        what to show (the dialog field's text)
    commit(text):  the user typed `text` here and pressed Enter
    cancel():      Esc was pressed in the box (the dialog cancels, like Esc elsewhere)
    other_side:    the box starts on the arrow's other side (a second arrow that can sit on
                   the first one: side two's)
    past_tip:      the box starts past the arrow's tip (a third one: the start offset's)
    The dialog owns the box (the arrows are rebuilt often; typing must survive that);
    discard() it when the dialog closes."""

    STYLE = (
        "QLineEdit#SciForgeArrowValue { background: #fafafa; color: #111111;"
        " border: 1px solid #3fa9f5; border-radius: 2px; padding: 1px 4px;"
        " selection-background-color: #3fa9f5; selection-color: #ffffff; }"
    )

    def __init__(self, text, commit, parent=None, cancel=None, other_side=False, past_tip=False):
        super().__init__(parent if parent is not None else view_widget())
        self.other_side = other_side  # starts on the arrow's other side (arrow_box_core.spot)
        self.past_tip = past_tip  # starts past the arrow's tip
        self.setObjectName("SciForgeArrowValue")
        self.setStyleSheet(self.STYLE)
        self.setFocusPolicy(QtCore.Qt.ClickFocus)  # never by Tab, never by itself
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating, True)
        self._text = text
        self._commit = commit
        self._cancel = cancel
        self.edited = False  # the user typed in the box since it last showed the field
        self.anchor = None  # widget pixel of the arrow point it sits next to
        self.handle_pixels = None  # (tail, tip, radius) of the handle on the screen, pixels
        self._placed = None  # what the last placement was worked out from (nothing new: skip)
        self._way = None  # the side it went to last time (arrow_box_core.spot_and_way keep)
        self.textEdited.connect(self._typed)
        self.returnPressed.connect(self._enter)
        self.hide()

    # -- what it shows -----------------------------------------------------------------
    def refresh(self):
        """Show the dialog's value, unless the user is typing in the box."""
        try:
            if self.edited or self.hasFocus():
                return
            text = self._text() or ""
            if text != self.text():
                self.setText(text)
                self.setCursorPosition(0)
            width = self.fontMetrics().horizontalAdvance(self.text() + "00") + 12
            if self.width() != max(72, width):
                self.setFixedWidth(max(72, width))
        except RuntimeError:
            pass  # the dialog's field went with its dialog
        except Exception as exc:
            warn("value box: %s" % exc)

    def place(self, view, point, direction=None, size=0.0):
        """Sit beside the arrow (Coin's SoTranslate1Dragger) whose middle is the 3D
        `point`. The arrow points along `direction`; `size` is its size (its tips are
        arrow_box_core.REACH sizes from the middle, its heads arrow_box_core.HEAD wide)."""
        from . import arrow_box_core

        tail = tip = point
        radius = 0.0
        if direction is not None and size > 0:
            along = App.Vector(direction)
            if along.Length > 1e-12:
                along.normalize()
                tail = point - along * (arrow_box_core.REACH * size)
                tip = point + along * (arrow_box_core.REACH * size)
                radius = arrow_box_core.HEAD * size
        self.place_segment(view, point, tail, tip, radius)

    def place_segment(self, view, anchor, tail, tip, radius, avoid=(), avoid_rects=()):
        """Sit beside a handle whose grabbable part runs from the 3D point `tail` to the 3D
        point `tip` and is `radius` mm wide (half its width); `anchor` is the 3D point the
        box belongs to (the handle's middle). The box goes beside the handle as it shows on
        the screen, never over it (nor over the dialog's other handles, `avoid`: their
        (tail, tip, radius) in pixels, nor over its other boxes, `avoid_rects`), so an
        arrow that points sideways (a side face in the Front view) stays grabbable. Hidden
        when the anchor is off screen."""
        from . import arrow_box_core

        parent = self.parentWidget()
        if parent is None:
            return
        avoid_rects = tuple(avoid_rects) + self._covered(parent)
        ratio = parent.devicePixelRatioF() or 1.0
        height = parent.height()

        def pixel(p):
            x, y = view.getPointOnViewport(p)
            return x / ratio, height - y / ratio

        anchor = App.Vector(anchor)
        ax, ay = pixel(anchor)
        if not (0 <= ax < parent.width() and 0 <= ay < height):
            self.hide()
            return
        self.anchor = QtCore.QPoint(int(ax), int(ay))
        tail_px = pixel(App.Vector(tail))
        tip_px = pixel(App.Vector(tip))
        radius_px = 0.0
        if radius > 0:
            # How wide the handle looks: its radius across the line of sight.
            look = App.Vector(view.getViewDirection())
            along = App.Vector(tip) - App.Vector(tail)
            side = look.cross(along) if along.Length > 1e-9 else App.Vector()
            if side.Length < 1e-9:
                side = look.cross(App.Vector(1, 0, 0))
                if side.Length < 1e-9:
                    side = look.cross(App.Vector(0, 1, 0))
            side.normalize()
            edge = pixel(anchor + side * radius)
            radius_px = ((edge[0] - ax) ** 2 + (edge[1] - ay) ** 2) ** 0.5
        self.handle_pixels = (tail_px, tip_px, radius_px)
        tail, tip, radius = tail_px, tip_px, radius_px
        box = (self.width(), self.height())
        # Placed again only when something moved (the box is polled every 30 ms by its
        # handle; working out the spot each time cost a tenth of a millisecond per handle).
        key = (
            (round(ax), round(ay), round(tail[0]), round(tail[1]), round(tip[0]), round(tip[1])),
            round(radius),
            box,
            tuple(tuple(map(round, (t[0], t[1], p[0], p[1], r))) for (t, p, r) in avoid),
            tuple(avoid_rects),
        )
        if key == self._placed and self.isVisible():
            return
        self._placed = key
        left, top, self._way = arrow_box_core.spot_and_way(
            (ax, ay),
            tail,
            tip,
            radius,
            box,
            (parent.width(), height),
            other_side=self.other_side,
            past_tip=self.past_tip,
            avoid=avoid,
            avoid_rects=avoid_rects,
            keep=self._way,
        )
        if self.pos() != QtCore.QPoint(left, top):
            self.move(left, top)
        if not self.isVisible():
            self.show()
            self.raise_()

    COVER_S = 0.5  # how long the panels found floating over the view are trusted

    def _covered(self, parent):
        """The parts of the 3D view that FreeCAD's floating panels (its overlay: the command
        dialog over the right of the view) cover, as (left, top, width, height) in the view's
        pixels: a box there would be hidden under the dialog, so it goes elsewhere."""
        now = time.monotonic()
        cached = getattr(self, "_cover_cache", None)
        if cached is not None and now - cached[0] < self.COVER_S:
            return cached[1]
        rects = []
        try:
            main = Gui.getMainWindow()
            view_rect = QtCore.QRect(parent.mapToGlobal(QtCore.QPoint(0, 0)), parent.size())
            for widget in main.findChildren(QtWidgets.QTabWidget):  # (the overlay is one)
                if widget.metaObject().className() != "Gui::OverlayTabWidget":
                    continue
                if not widget.isVisible():
                    continue
                area = QtCore.QRect(widget.mapToGlobal(QtCore.QPoint(0, 0)), widget.size())
                common = area.intersected(view_rect)
                if common.isEmpty():
                    continue
                corner = parent.mapFromGlobal(common.topLeft())
                rects.append((corner.x(), corner.y(), common.width(), common.height()))
        except Exception:
            rects = []
        self._cover_cache = (now, tuple(rects))
        return self._cover_cache[1]

    HOVER_PIXELS = 14.0

    def handle_hovered(self):
        """True while the mouse is over the handle this box belongs to (as last placed)."""
        pixels = self.handle_pixels
        parent = self.parentWidget()
        if pixels is None or parent is None or not self.isVisible():
            return False
        try:
            from . import arrow_box_core

            pos = parent.mapFromGlobal(QtGui.QCursor.pos())
            if not parent.rect().contains(pos):
                return False
            tail, tip, radius = pixels
            gap = arrow_box_core._segment_point(tail, tip, (pos.x(), pos.y()))
            return gap <= radius + self.HOVER_PIXELS
        except Exception:
            return False

    # -- typing --------------------------------------------------------------------------
    def _typed(self, _text):
        self.edited = True

    def _enter(self):
        self._take()

    def _take(self):
        if not self.edited:
            return
        self.edited = False
        text = self.text()
        try:
            self._commit(text)
        except Exception as exc:
            warn("value box: %s" % exc)
        self.refresh()

    def event(self, event):
        # Esc while typing here cancels the command, as everywhere in Fusion. Claimed before
        # Qt looks for shortcuts, so it reaches keyPressEvent below.
        try:
            if (
                event.type() == QtCore.QEvent.ShortcutOverride
                and event.key() == QtCore.Qt.Key_Escape
            ):
                event.accept()
                return True
        except Exception:
            pass
        return super().event(event)

    def keyPressEvent(self, event):
        try:
            if event.key() == QtCore.Qt.Key_Escape:
                event.accept()
                self.edited = False  # what was typed is dropped with the command
                if self._cancel is not None:
                    self._cancel()
                return
        except Exception as exc:
            warn("value box: %s" % exc)
            return
        super().keyPressEvent(event)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        # A click puts the cursor somewhere in the text; Fusion selects the value so the
        # first key replaces it.
        QtCore.QTimer.singleShot(0, self._select_all)

    def _select_all(self):
        try:
            if self.hasFocus() and not self.edited:
                self.selectAll()
        except RuntimeError:
            pass

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        # Clicking elsewhere (OK, the 3D view) keeps what was typed, like the dialog field.
        try:
            if self.edited and event.reason() == QtCore.Qt.MouseFocusReason:
                BOX_TAKEN["time"] = time.time()
            self._take()
            self.refresh()
        except Exception as exc:
            warn("value box: %s" % exc)

    def discard(self):
        """Remove the box for good (the dialog closes)."""
        self._commit = lambda _text: None
        self._text = lambda: ""
        self._cancel = None
        if not _alive(self):
            return
        try:
            self.hide()
            self.setParent(None)
            self.deleteLater()
        except RuntimeError:
            pass


_LIVE_HANDLES = weakref.WeakSet()  # every drag handle that polled lately (BoxCarrier)
LIVE_S = 0.5  # a handle that has not polled for this long has been removed


def live_handles():
    """The drag handles shown now: they poll every few tens of milliseconds while they
    live (follow_box), so one silent for half a second has gone with its dialog."""
    now = time.monotonic()
    try:
        return [h for h in list(_LIVE_HANDLES) if now - getattr(h, "_polled_at", 0.0) < LIVE_S]
    except Exception:
        return []


def handle_pixels(handle, widget):
    """(tail, tip, radius) of a handle's grabbable part in `widget` pixels (the 3D view's
    drawing widget), worked out as the value box does; None when it cannot be."""
    try:
        anchor, tail, tip, radius = handle.box_geometry()
        return geometry_pixels(handle.view, widget, anchor, tail, tip, radius)
    except Exception:
        return None


def geometry_pixels(view, widget, anchor, tail, tip, radius):
    """(tail, tip, radius) in `widget` pixels of a grabbable part given in 3D (see
    BoxCarrier.box_geometry); None when it cannot be worked out."""
    try:
        ratio = widget.devicePixelRatioF() or 1.0
        height = widget.height()

        def pixel(p):
            x, y = view.getPointOnViewport(App.Vector(p))
            return x / ratio, height - y / ratio

        anchor = App.Vector(anchor)
        ax, ay = pixel(anchor)
        radius_px = 0.0
        if radius > 0:
            look = App.Vector(view.getViewDirection())
            along = App.Vector(tip) - App.Vector(tail)
            side = look.cross(along) if along.Length > 1e-9 else App.Vector()
            if side.Length < 1e-9:
                side = look.cross(App.Vector(1, 0, 0))
                if side.Length < 1e-9:
                    side = look.cross(App.Vector(0, 1, 0))
            side.normalize()
            edge = pixel(anchor + side * radius)
            radius_px = ((edge[0] - ax) ** 2 + (edge[1] - ay) ** 2) ** 0.5
        return pixel(App.Vector(tail)), pixel(App.Vector(tip)), radius_px
    except Exception:
        return None


class BoxCarrier:
    """What a drag handle needs to carry a value box (Fusion shows the value next to every
    handle you can drag): where its grabbable part is, and a hook its poll calls so the box
    follows the handle, a turned view and the dialog's value. A handle class adds this to
    its bases and implements box_geometry() (and box_active() when it knows when it is
    dragged or hovered); its poll calls follow_box() and its remove() drop_box(). The
    dialog owns the box (taskui.ValueBoxes) and attaches it with attach_box()."""

    value_box = None  # the ArrowValueBox that follows this handle, or None
    box_owner = None  # the dialog's ValueBoxes (told which handle is in use)
    box_key = None  # this handle's key in it

    def box_geometry(self):
        """(anchor, tail, tip, radius): the 3D point the box belongs to (the handle's
        middle), the two ends of the handle's grabbable part (3D) and its half-width (mm).
        Override."""
        raise NotImplementedError

    def box_active(self):
        """True while this handle is dragged (or hovered, when the handle knows)."""
        return False

    def box_avoid(self):
        """More grabbable parts the box must not cover, [(anchor, tail, tip, radius)] in
        3D: a handle made of several (Move's triad: the arrows and turn handles that are
        not the one in use). Override."""
        return ()

    def attach_box(self, box, owner=None, key=None):
        self.value_box = box
        self.box_owner = owner
        self.box_key = key
        self.follow_box()

    HOVER_EVERY = 4  # polls: the mouse over the handle is looked for every 120 ms

    def follow_box(self):
        """Keep the box next to the handle and showing the dialog's value: run on every
        poll (it follows a drag and a turned or zoomed view). A handle in use (dragged, or
        the mouse over it) becomes the one a number typed over the view goes to."""
        # Alive: a press on this handle starts its drag, never a selection box, whether
        # or not the dialog gave it a value box (selection_ui._handle_under).
        self._polled_at = time.monotonic()
        try:
            _LIVE_HANDLES.add(self)
        except TypeError:
            pass
        box = self.value_box
        if box is None:
            return
        if not _alive(box):
            self.value_box = None
            return
        try:
            box.refresh()
            anchor, tail, tip, radius = self.box_geometry()
            owner = self.box_owner
            avoid = list(owner.other_handles(box)) if owner is not None else []
            parent = box.parentWidget()
            for part in self.box_avoid():
                pixels = geometry_pixels(self.view, parent, *part) if parent else None
                if pixels is not None:
                    avoid.append(pixels)
            rects = owner.other_boxes(box) if owner is not None else ()
            box.place_segment(self.view, anchor, tail, tip, radius, avoid=avoid, avoid_rects=rects)
            if owner is None:
                return
            self._box_polls = getattr(self, "_box_polls", 0) + 1
            hovered = self._box_polls % self.HOVER_EVERY == 0 and box.handle_hovered()
            if self.box_active() or hovered:
                owner.used(self.box_key)
        except RuntimeError:
            self.value_box = None  # the box went with its dialog
        except Exception as exc:
            warn("value box: %s" % exc)

    def drop_box(self):
        """The handle goes (rebuilt or removed): the box stays with the dialog, hidden until
        the next handle shows it again. Never hidden while the user types in it (hiding
        would take the keyboard away mid-value)."""
        _LIVE_HANDLES.discard(self)
        self._polled_at = 0.0
        box, self.value_box = self.value_box, None
        self.box_owner = None
        if box is not None and _alive(box):
            try:
                if not box.hasFocus():
                    box.hide()
            except RuntimeError:
                pass


class ValueBoxes:
    """The value boxes of one dialog, one per handle (by key: "distance", "taper",
    "radius"...). Made once and kept by the dialog: the handles are rebuilt often, and what
    is being typed must survive that. Remembers which handle was used last (dragged, or
    the mouse over it): a number typed over the 3D view goes into its box, else into the
    `default` key's box, else into the first box shown. discard() when the dialog closes."""

    def __init__(self, panel, default=None):
        self.panel = panel
        self.default = default
        self.boxes = {}
        self.last = None

    def box(self, key, text, commit, other_side=False, past_tip=False):
        """The box for `key` (made on the first call): text() gives what it shows (the
        dialog field's text), commit(text) takes what was typed in it."""
        box = self.boxes.get(key)
        if box is not None and _alive(box):
            return box
        try:
            box = ArrowValueBox(
                text, commit, cancel=self._cancel, other_side=other_side, past_tip=past_tip
            )
        except Exception as exc:
            warn("value box unavailable: %s" % exc)
            return None
        self.boxes[key] = box
        return box

    def attach(self, handle, key, text, commit, **where):
        """Give `handle` (a BoxCarrier) its box."""
        box = self.box(key, text, commit, **where)
        if box is not None and handle is not None:
            try:
                handle.attach_box(box, owner=self, key=key)
            except Exception as exc:
                warn("value box: %s" % exc)
        return box

    def _cancel(self):
        """Esc in a box cancels the command (as Esc does anywhere)."""
        panel = self.panel
        escape = getattr(panel, "escape", None)
        if escape is not None and hasattr(escape, "press"):
            escape.press()
            return
        QtCore.QTimer.singleShot(0, lambda: _reject(panel))

    def used(self, key):
        self.last = key

    def other_handles(self, box):
        """The handles of the other boxes shown, [(tail, tip, radius)] in view pixels (as
        last placed): a box must not cover them either."""
        found = []
        for other in self.boxes.values():
            if other is box or not _alive(other):
                continue
            try:
                if other.isVisible() and other.handle_pixels is not None:
                    found.append(other.handle_pixels)
            except RuntimeError:
                pass
        return found

    def other_boxes(self, box):
        """The other boxes shown, [(left, top, width, height)] in view pixels: a box never
        lands on one of them (two arrows on one spot, at 0)."""
        found = []
        for other in self.boxes.values():
            if other is box or not _alive(other):
                continue
            try:
                if other.isVisible() and other.handle_pixels is not None:
                    found.append((other.x(), other.y(), other.width(), other.height()))
            except RuntimeError:
                pass
        return found

    def current(self):
        """The box a number typed over the 3D view goes to, or None when none is shown."""
        for key in (self.last, self.default):
            box = self.boxes.get(key) if key else None
            if box is not None and _alive(box) and box.isVisible():
                return box
        for box in self.boxes.values():
            if _alive(box) and box.isVisible():
                return box
        return None

    def shown(self):
        """{key: box} of the boxes on the screen now."""
        return {k: b for k, b in self.boxes.items() if _alive(b) and b.isVisible()}

    def discard(self):
        boxes, self.boxes = list(self.boxes.values()), {}
        self.last = None
        for box in boxes:
            try:
                box.discard()
            except Exception:
                pass


def _reject(panel):
    try:
        if panel is not None and not getattr(panel, "_closed", True):
            panel.reject()
    except Exception as exc:
        warn("Esc: %s" % exc)


def _value_keys():
    """The keys that are part of a value: digits, the decimal point (or comma) and minus
    (sketch_mode.VALUE_KEYS, the sketch's own list of them)."""
    try:
        from . import sketch_mode

        return sketch_mode.VALUE_KEYS
    except Exception:
        return {getattr(QtCore.Qt, "Key_%d" % d) for d in range(10)} | {
            QtCore.Qt.Key_Period,
            QtCore.Qt.Key_Comma,
            QtCore.Qt.Key_Minus,
        }


def is_value_key(event):
    """A digit (or . , -) typed without Ctrl / Alt / Meta."""
    try:
        mods = event.modifiers() & ~(QtCore.Qt.KeypadModifier | QtCore.Qt.ShiftModifier)
        return event.key() in _value_keys() and mods == QtCore.Qt.NoModifier
    except Exception:
        return False


def sketch_open():
    """True while a sketch is being edited (its own keys then rule)."""
    try:
        from . import sketch_mode

        if sketch_mode.current() is not None:
            return True
    except Exception:
        pass
    try:
        edit = Gui.ActiveDocument.getInEdit() if Gui.ActiveDocument is not None else None
        obj = edit.Object if edit is not None else None
        return obj is not None and obj.TypeId == "Sketcher::SketchObject"
    except Exception:
        return False


def _typing_somewhere():
    """True when a text field (a dialog field, a value box) has the keyboard: the keys are
    its, never ours."""
    focus = QtWidgets.QApplication.focusWidget()
    return isinstance(focus, (QtWidgets.QLineEdit, QtWidgets.QAbstractSpinBox))


class TypeOverView:
    """Fusion: with a command open, a number typed while the mouse is over the 3D view goes
    into the value box next to the handle, and Enter finishes. FreeCAD took those digits
    as its view keys (0 isometric, 1 front, 2 top ...): the view jumped and the number was
    lost. A digit, a minus sign or a decimal point typed on the 3D view now goes into the
    dialog's current value box (`panel.typing_box()`: the box of the handle last dragged
    or hovered, else the main one), which takes the keyboard with its text selected, so the
    person types straight on; Enter there is OK, as always in the box. A dialog without a
    box (or none shown yet) can name a field instead (`panel.typing_field()`: the Box
    dialog while it is placed). An event filter on the 3D view's widgets (where the keys
    arrive), active only while the dialog is open; it never acts inside an open sketch,
    while a field or box has the keyboard, or on one of SciForge's own key shortcuts.
    remove() when the dialog closes (taskui.Panel does both)."""

    BURST = 1.5  # seconds: keys this close follow each other into the same field
    VIEWER = "Gui::View3DInventorViewer"

    def __init__(self, panel):
        self.panel = panel
        self.last = (None, 0.0)
        self.targets = []
        guard = self

        class KeyFilter(QtCore.QObject):
            def eventFilter(self, obj, event):
                return guard._filter(obj, event)

        self.filter = KeyFilter()
        try:
            gl = view_widget()
            if gl is not None:
                self.targets.append(gl)
                parent = gl.parentWidget()
                if parent is not None and parent.metaObject().className() == self.VIEWER:
                    self.targets.append(parent)  # a real keyboard sends the keys here
            for widget in self.targets:
                widget.installEventFilter(self.filter)
        except Exception as exc:
            warn("typing over the view: %s" % exc)

    def _filter(self, obj, event):
        try:
            kind = event.type()
            if kind == QtCore.QEvent.MouseMove:
                # a drag goes on (a handle, an orbit): a rebuild that waits for the mouse to
                # rest keeps waiting (Panel._tick), also while the value does not change (a
                # snapped angle)
                try:
                    if event.buttons() != QtCore.Qt.NoButton and self.panel is not None:
                        self.panel._last_motion = time.perf_counter()
                except Exception:
                    pass
                return False
            if kind not in (QtCore.QEvent.ShortcutOverride, QtCore.QEvent.KeyPress):
                return False
            panel = self.panel
            if panel is None or getattr(panel, "_closed", True):
                return False
            if not isinstance(event, QtGui.QKeyEvent) or not is_value_key(event):
                return False
            text = event.text()
            if not text or _typing_somewhere() or sketch_open() or _shortcut_key(text):
                return False
            target = panel.typing_box() if hasattr(panel, "typing_box") else None
            if target is None and hasattr(panel, "typing_field"):
                target = panel.typing_field()
            if target is None:
                return False
            event.accept()  # ShortcutOverride accepted: FreeCAD's view key does not fire
            if kind == QtCore.QEvent.KeyPress and not event.isAutoRepeat():
                now = time.time()
                fresh = self.last[0] is not target or now - self.last[1] > self.BURST
                self.last = (target, now)
                key = event.key()
                QtCore.QTimer.singleShot(0, lambda: self._type(target, key, text, fresh))
            return True
        except Exception as exc:
            warn("typing over the view: %s" % exc)
            return False

    def _type(self, target, key, text, fresh):
        try:
            if self.panel is None or getattr(self.panel, "_closed", True):
                return
            if isinstance(target, ArrowValueBox):
                edit = target if _alive(target) else None
                if edit is None or not edit.isVisible():
                    return
                edit.setFocus(QtCore.Qt.OtherFocusReason)
                edit.selectAll()  # the first key replaces the value, like Fusion's box
            else:
                edit = target.widget.findChild(QtWidgets.QLineEdit)
                if edit is None:
                    return
                if fresh or not edit.hasFocus():
                    target.widget.setFocus()
                if fresh:
                    edit.selectAll()
            # Sent as a key press, so the box reacts as to a person's typing.
            press = QtGui.QKeyEvent(QtCore.QEvent.KeyPress, key, QtCore.Qt.NoModifier, text)
            QtWidgets.QApplication.sendEvent(edit, press)
            release = QtGui.QKeyEvent(QtCore.QEvent.KeyRelease, key, QtCore.Qt.NoModifier, text)
            QtWidgets.QApplication.sendEvent(edit, release)
        except Exception as exc:
            warn("typing a value: %s" % exc)

    def remove(self):
        for widget in self.targets:
            try:
                widget.removeEventFilter(self.filter)
            except Exception:
                pass
        self.targets = []
        self.panel = None


def _shortcut_key(text):
    """True when `text` is one of SciForge's own key shortcuts (never stolen)."""
    try:
        from . import shortcuts

        return shortcuts.normalise(text) in shortcuts.bound_keys()
    except Exception:
        return False


class ArrowDragger(BoxCarrier):
    """A 1D drag handle at `origin` pointing along `direction` (both App.Vector).

    on_drag(distance) is called while dragging, on_release(distance) at the end.

    It looks like Fusion's distance arrow (handle_look): a small blue arrow standing at
    origin + direction * distance, pointing the way the distance goes (back along the line
    for a minus), the same size on the screen whatever the part or the zoom, lighter under
    the mouse and while dragged, with a thin light line back to `origin`. `size` is no
    longer used (it was the arrow's size in mm): kept so the dialogs need not change.

    The arrow is watched with a Qt timer instead of Coin dragger callbacks: Coin
    calls those in the middle of its mouse handling, where rebuilding the part
    (or swapping Extrude for Cut) changes the scene under its feet, and pivy runs
    them without taking Python's lock. Both crashed FreeCAD on a drag."""

    POLL_MS = 30

    def __init__(
        self,
        origin,
        direction,
        distance=0.0,
        size=8.0,
        on_drag=None,
        on_release=None,
        value_box=None,
    ):
        from pivy import coin

        from . import handle_look

        self.coin = coin
        self.view = Gui.ActiveDocument.ActiveView
        self.origin = App.Vector(origin)
        self.direction = App.Vector(direction)
        if self.direction.Length > 1e-12:
            self.direction.normalize()
        place = coin.SoTransform()
        place.translation.setValue(origin.x, origin.y, origin.z)
        # SoTranslate1Dragger moves along its local X axis; turn X onto `direction`.
        rot = App.Rotation(App.Vector(1, 0, 0), direction)
        place.rotation.setValue(*rot.Q)
        # over the part and grabbable through it (taskui.on_top_root, in the 3D-annotation
        # pass so the arrow is shaded right); `place` stays child 0
        self.root = handle_look.top_root(coin, place, pickable=True)
        self.guide = handle_look.Line(coin)  # the thin line from the profile to the arrow
        guide = coin.SoSeparator()
        unpickable = coin.SoPickStyle()
        unpickable.style = coin.SoPickStyle.UNPICKABLE
        guide.addChild(unpickable)
        guide.addChild(self.guide.node)
        self.root.addChild(guide)
        self.dragger = coin.SoTranslate1Dragger()
        self.dragger.translation.setValue(float(distance), 0, 0)  # mm along local X
        # The arrow points along local +X (the shapes are built along +Y), turned round
        # for a minus distance; it is drawn in pixels (handle_look.PixelScale).
        self.flip = coin.SoRotationXYZ()
        self.flip.axis.setValue(coin.SoRotationXYZ.Z)
        self.scales = []  # the drawn arrows' (SoShapeScale: right on every frame)
        self.grabs = []  # what Coin picks: kept right by the poll (handle_look.PixelScale)
        self.paints = []
        here = self.origin + self.direction * float(distance)
        for part, hot in (("translator", False), ("translatorActive", True)):
            arrow, paint = handle_look.arrow_shape(coin)
            paint.set(hot)
            scale = handle_look.PixelScale(
                coin, handle_look.unpickable(coin, arrow), self.view, here
            )
            grab = handle_look.PixelScale(
                coin, handle_look.grab_shape(coin), self.view, here, plain=True
            )
            sep = coin.SoSeparator()
            sep.addChild(self.flip)
            turn = coin.SoRotationXYZ()  # +Y (the shapes' axis) onto +X
            turn.axis.setValue(coin.SoRotationXYZ.Z)
            turn.angle.setValue(-math.pi / 2.0)
            sep.addChild(turn)
            sep.addChild(scale.node)
            sep.addChild(grab.node)
            self.dragger.setPart(part, sep)
            self.scales.append(scale)
            self.grabs.append(grab)
            self.paints.append(paint)
        self.dragger.setPart("feedback", coin.SoSeparator())
        self.dragger.setPart("feedbackActive", coin.SoSeparator())
        self.root.addChild(self.dragger)
        self.on_drag = on_drag
        self.on_release = on_release
        self._last = self.distance()
        self._was_active = False
        self._hover = False
        self._drawn = None
        self._draw()
        self.view.getSceneGraph().addChild(self.root)
        self._timer = QtCore.QTimer()
        self._timer.setInterval(self.POLL_MS)
        self._timer.timeout.connect(self._poll)
        self._timer.start()
        self._move_poll = poll_on_move(self._poll)  # dragged: polled on every mouse move
        if value_box is not None:
            self.attach_box(value_box)  # an ArrowValueBox that follows the arrow

    def distance(self):
        return float(self.dragger.translation.getValue()[0])

    def set_distance(self, distance):
        self.dragger.translation.setValue(float(distance), 0, 0)
        self._last = self.distance()
        self._draw()
        try:
            self._follow_zoom()
        except Exception as exc:
            warn("drag: %s" % exc)

    def anchor(self):
        """Where the arrow stands: origin + direction * distance (where the extrusion
        ends); the arrow points on from there."""
        return self.origin + self.direction * self.distance()

    @property
    def size(self):
        """The arrow's length (mm) at its place in the view now (handle_look_core.ARROW_PX
        on the screen)."""
        from . import handle_look

        return handle_look.mm(self.view, self.anchor(), handle_look.core.ARROW_PX)

    def pointing(self):
        """The way the arrow points: `direction`, turned round for a minus distance."""
        return self.direction * (-1.0 if self.distance() < 0 else 1.0)

    def tip(self):
        return self.anchor() + self.pointing() * self.size

    def head_point(self):
        """A point on the arrow's head (where a person grabs it)."""
        from . import handle_look_core

        return self.anchor() + self.pointing() * (handle_look_core.HEAD_AIM * self.size)

    def box_geometry(self):
        """The arrow from where it stands to its tip, as wide as its head."""
        from . import handle_look

        foot = self.anchor()
        tip = self.tip()
        width = handle_look.mm(self.view, foot, handle_look.core.half_width_px("arrow"))
        return (foot + tip) * 0.5, foot, tip, width

    def box_active(self):
        try:
            return bool(self.dragger.isActive.getValue())
        except Exception:
            return False

    def _show_value(self):
        self.follow_box()

    def _draw(self):
        """Point the arrow the way the distance goes and run the guide line to it."""
        distance = self.distance()
        if self._drawn is not None and abs(distance - self._drawn) < 1e-12:
            return
        self._drawn = distance
        self.flip.angle.setValue(math.pi if distance < 0 else 0.0)
        self.guide.set_points([(0.0, 0.0, 0.0), (distance, 0.0, 0.0)])

    def _poll(self):
        try:
            from . import handle_look

            # a release FreeCAD never passed on ends the drag here (drag_guard)
            active = drag_guard.guard_coin_dragger(self.dragger, self.root, self.view)
            # Incremental Move (navigation bar): the value goes in steps of the increment
            value = increments.linear(self.distance())
            if abs(value - self._last) > 1e-9:
                self._last = value
                if self.on_drag:
                    self.on_drag(value)
            if self._was_active and not active and self.on_release:
                self.on_release(value)
            self._was_active = active
            self._draw()
            # lighter under the mouse (the dragged arrow is the dragger's own lit part)
            hover = not active and handle_look.hovered(self.view, self.anchor(), self.tip())
            if hover != self._hover:
                self._hover = hover
                self.paints[0].set(hover)
            self._follow_zoom()
            self._show_value()
        except Exception as exc:
            warn("drag: %s" % exc)

    def _follow_zoom(self):
        """Keep the picked shape (and a drawing without SoShapeScale) at the view's scale."""
        anchor = self.anchor()
        for scale in self.scales + self.grabs:
            scale.update(self.view, anchor)

    def remove(self):
        try:
            self._timer.stop()
        except Exception:
            pass
        drop_poll_on_move(self)
        drag_guard.before_remove(self.dragger, self.root, self.view)
        try:
            self.view.getSceneGraph().removeChild(self.root)
        except Exception:
            pass
        self.drop_box()


def _end_transaction(doc, abort=False):
    """Close a dialog's undo step. doc.commitTransaction()/abortTransaction() only close a
    step that holds changes: a dialog OK'd or cancelled without a change left its step name
    pending, and the next change anywhere opened a step under that name and threw away the
    Redo list. The pending name is closed too (same as preview.end_transaction), and a
    design without history bakes the change first (preview._bakes)."""
    from . import edit_rollback, preview

    if not abort:
        edit_rollback.restore(doc)  # the marker back after an edit, in this undo step
        preview.catch_up(doc)  # the steps after the marker waited: rebuilt in this undo step
        if preview._bakes(doc):
            return
    if abort:
        edit_rollback.drop(doc)
        preview.release(doc)
        doc.abortTransaction()
    else:
        doc.commitTransaction()
    try:
        App.closeActiveTransaction(abort)
    except Exception:
        pass


class Panel:
    """Base for SciForge task dialogs. Subclasses fill self.layout and implement apply()."""

    title = "SciForge"
    icon = None
    # The preview follows a drag at most every PREVIEW_MS; a part that takes long to
    # rebuild gets more time in between (up to PREVIEW_MAX_MS), so the arrow stays smooth.
    PREVIEW_MS = 60
    PREVIEW_MAX_MS = 400
    STREAM_GAP = 0.15  # changes closer than this (seconds) are one stream (a drag)
    # A rebuild that waits for the changes to rest (schedule(settle=True), or a dialog whose
    # last rebuild took longer than SLOW_DRAG seconds) runs once no change came for PAUSE_MS:
    # the mouse paused or was let go. Never between two mouse moves (see schedule()).
    PAUSE_MS = 200
    SLOW_DRAG = 0.25

    def __init__(self, doc, transaction):
        from . import ui_icon

        self.doc = doc
        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle(self.title)
        if self.icon:
            self.form.setWindowIcon(ui_icon(self.icon))
        self.layout = QtWidgets.QFormLayout(self.form)
        self.message = QtWidgets.QLabel("")
        self.message.setWordWrap(True)
        self.message.setStyleSheet("color: #ff8a80;")
        self._timer = QtCore.QTimer()
        self._timer.setSingleShot(True)
        self._timer.setInterval(self.PREVIEW_MS)
        self._timer.timeout.connect(self._tick)
        doc.openTransaction(transaction)
        self._closed = False
        set_current(self)
        try:  # an edit rolls the marker to its step (in this undo step); the steps after
            # the marker wait while the dialog is open
            from . import edit_rollback, preview

            edit_rollback.take(doc)
            preview.hold(doc)
        except Exception as exc:
            warn("previews rebuild every step: %s" % exc)
        # Digits typed with the mouse over the 3D view go into the dialog's value box
        # (TypeOverView); removed with cleanup() / _close().
        try:
            self.typing = TypeOverView(self)
        except Exception as exc:
            warn("typing over the view: %s" % exc)
            self.typing = None

    def finish_layout(self):
        self.layout.addRow(self.message)

    # -- a number typed over the 3D view --------------------------------------------------
    def typing_box(self):
        """The value box a number typed over the 3D view goes to: the dialog's
        ValueBoxes' current one (self.value_boxes), or None."""
        boxes = getattr(self, "value_boxes", None)
        if isinstance(boxes, ValueBoxes):
            return boxes.current()
        return None

    def typing_field(self):
        """The dialog field such a number goes to when no box is shown (override), or None."""
        return None

    def _remove_typing(self):
        typing, self.typing = getattr(self, "typing", None), None
        if typing is not None:
            try:
                typing.remove()
            except Exception:
                pass

    # -- live preview ---------------------------------------------------------
    # The handle never waits for the model (Luca, 2026-10-22: "the angle dragger doesn't even
    # update either: it waits behind for the model to update"). A rebuild runs on the main
    # thread and nothing else moves meanwhile, the dragged handle included. So:
    #   * a dialog whose rebuild is quick (most: an extrude, a move) rebuilds while the handle
    #     is dragged, at the pace below (the part grows while the button is still down);
    #   * a dialog whose last rebuild took longer than SLOW_DRAG (a big part), and a dialog
    #     with a live picture of its own (Draft: draft_live.py; it passes settle=True),
    #     rebuild only once the changes have rested for PAUSE_MS (the mouse paused or was let
    #     go): never between two mouse moves, and only for the latest value.
    def schedule(self, settle=False):
        """Rebuild the preview soon. While changes keep coming (an arrow being dragged, keys
        typed) the preview follows them at a steady pace, like Fusion's, which moves with the
        mouse. A timer already running is left alone: restarting it on every change put the
        preview off until the mouse stopped moving. A change on its own (a click, a value
        typed) is shown after PREVIEW_MS; only while changes stream in (a drag sends one
        every few milliseconds) does the next rebuild wait for the calm gap after a slow one
        (see _tick). `settle`: the change comes from a handle being dragged and the dialog
        shows it live by itself, so the rebuild waits until the changes rest (PAUSE_MS); a
        dialog whose rebuild is slow (SLOW_DRAG) waits like that for every change."""
        if getattr(self, "_closed", False):
            return
        now = time.perf_counter()
        streaming = now - getattr(self, "_last_change", -1.0) < self.STREAM_GAP
        self._last_change = now
        self._waits_rest = bool(settle) or self._slow()
        if self._timer.isActive():
            return
        wait = self.PREVIEW_MS
        if self._waits_rest:
            wait = self.PAUSE_MS
        elif streaming:
            try:
                calm = int((getattr(self, "_calm_until", 0.0) - now) * 1000.0)
                wait = max(wait, min(self.PREVIEW_MAX_MS, calm))
            except Exception:
                pass
        self._timer.setInterval(wait)
        self._timer.start()

    def settle_now(self):
        """The handle was let go: the waiting rebuild runs at once (not after PAUSE_MS)."""
        if getattr(self, "_closed", False):
            return
        try:
            self._waits_rest = False
            self._last_change = time.perf_counter() - self.PAUSE_MS / 1000.0
            self._last_motion = -1.0
            if self._timer.isActive():
                self._timer.stop()
                self._timer.setInterval(0)
                self._timer.start()
        except Exception:
            pass

    def last_moved(self):
        """When the value last changed or the mouse last moved with a button held."""
        return max(getattr(self, "_last_change", -1.0), getattr(self, "_last_motion", -1.0))

    def _slow(self):
        """True when the last rebuild took so long that it would freeze a dragged handle."""
        return getattr(self, "_preview_cost", 0.0) > self.SLOW_DRAG

    def _tick(self):
        """The preview timer fired: rebuild. While a drag streams changes in, the next
        rebuild waits for a calm gap of 1.5 times this one's time (at most PREVIEW_MAX_MS),
        so the view and the arrow stay smooth on a heavy part. A rebuild that waits for the
        changes to rest (schedule(settle=True), or a slow dialog) waits until no change came
        for PAUSE_MS."""
        if getattr(self, "_closed", False):
            return
        try:
            if getattr(self.doc, "Recomputing", False):
                # A long recompute lets Qt run timers meanwhile: never start a second one.
                # The rebuild running now starts the next one when it ends (below).
                self._pending = True
                self._timer.setInterval(self.PREVIEW_MS)
                self._timer.start()
                return
        except Exception:
            pass
        try:
            if getattr(self, "_waits_rest", False):
                quiet = time.perf_counter() - self.last_moved()
                left = self.PAUSE_MS / 1000.0 - quiet
                if left > 0.001:  # still moving: look again when it may have rested
                    self._timer.setInterval(max(1, int(left * 1000.0)))
                    self._timer.start()
                    return
        except Exception:
            pass
        self._pending = False
        self._waits_rest = False
        started = time.perf_counter()
        try:
            self._recompute()
        except Exception as exc:
            warn("preview: %s" % exc)
        ended = time.perf_counter()
        self._preview_cost = ended - started
        gap = min(self.PREVIEW_MAX_MS / 1000.0, 1.5 * (ended - started))
        self._calm_until = ended + gap
        try:
            if getattr(self, "_closed", False):
                return
            if self._pending or self._timer.isActive():
                # Changes came in while it rebuilt: one more rebuild, after the calm gap when
                # they stream in (a drag), else at once (a rebuild that waits for the changes
                # to rest keeps waiting: _waits_rest).
                self._pending = False
                streaming = ended - getattr(self, "_last_change", -1.0) < self.STREAM_GAP
                self._timer.stop()
                if getattr(self, "_waits_rest", False):
                    self._timer.setInterval(self.PAUSE_MS)
                else:
                    self._timer.setInterval(
                        max(self.PREVIEW_MS, int(gap * 1000.0) if streaming else 0)
                    )
                self._timer.start()
        except Exception:
            pass

    def _recompute(self):
        if self._closed:
            return  # a change that arrived as the dialog closed
        try:
            from . import preview

            preview.recompute(self.doc)  # the steps after the marker wait (preview.hold)
            self.show_status()
        except Exception as exc:
            try:
                self.message.setText(str(exc))
            except RuntimeError:
                pass

    def feature(self):
        """The feature whose state the dialog reports (override)."""
        return None

    def show_status(self):
        obj = self.feature()
        if obj is None:
            return
        state = list(getattr(obj, "State", []))
        if "Invalid" in state or "Error" in state:
            text = obj.getStatusString() if hasattr(obj, "getStatusString") else "Invalid result"
            self.message.setText("⚠ " + text)
        else:
            self.message.setText("")

    # -- task dialog API --------------------------------------------------------
    def getStandardButtons(self):
        buttons = QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        return getattr(buttons, "value", buttons)  # PySide6 enums need .value

    def accept(self):
        from . import preview

        self._timer.stop()
        preview.recompute(self.doc)  # the steps after the marker catch up as the step closes
        obj = self.feature()
        if obj is not None and "Invalid" in list(obj.State):
            self.show_status()
            return False  # stay open, like Fusion's dialog with an error
        self.cleanup()
        _end_transaction(self.doc)
        self._close()
        log("%s done" % self.title)
        return True

    def reject(self):
        self._timer.stop()
        self.cleanup()
        _end_transaction(self.doc, abort=True)
        self.doc.recompute()
        self._close()
        return True

    def finish(self):
        """Another command is starting: keep this edit if it is valid, else drop it."""
        if not self.accept():
            self.reject()

    def _close(self):
        if _OPEN["dialog"] is self:
            _OPEN["dialog"] = None
        try:  # nothing waits after the dialog (its undo step closed and rebuilt them); a
            # dialog that closed its step itself still gets the marker back after an edit
            from . import edit_rollback, preview

            edit_rollback.restore(self.doc)
            if preview.holding(self.doc):
                preview.catch_up(self.doc)
        except Exception as exc:
            warn("could not rebuild the later steps: %s" % exc)
        self._remove_typing()
        Gui.Control.closeDialog()
        # Fusion clears the selection when a command ends. A selection left behind
        # was picked up by the next command (a second Extrude re-used the first
        # sketch, cut into the part and made it disappear).
        try:
            Gui.Selection.clearSelection()
        except Exception:
            pass
        try:
            from . import commands

            commands.leave_edit()
        except Exception as exc:
            warn("could not finish editing: %s" % exc)

    def cleanup(self):
        """Remove draggers/observers (override, call super)."""
        self._closed = True
        self._remove_typing()
