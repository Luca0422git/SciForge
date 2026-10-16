# SPDX-License-Identifier: LGPL-2.1-or-later
"""Which clicks the closed areas (profiles) of a finished sketch take, like Fusion.

SciForge turns FreeCAD's sketch areas on (sketch_mode.PARAMS, "MakeInternals"), so a
visible sketch's areas light up under the mouse and can be clicked ("InternalFaceN").
FreeCAD alone got two things wrong compared with Fusion:

- A sketch drawn ON a face of the part (Create Sketch on the top face, two rectangles,
  Finish Sketch): FreeCAD finds the area and the face at exactly the same depth and gave
  the click to the face, so clicking area B selected the whole top face and E extruded
  that. With no command running, each visible sketch is now drawn a hair (a few
  thousandths of a mm) toward the camera: the area under the mouse lights up, a click
  selects it, Ctrl+click adds another, all by FreeCAD's own picking. The sketch's curves
  move with it, so a curve lying on the face can still be clicked.
- A command that cannot use sketch areas (Create Sketch, Hole, Shell, Fillet, Measure...,
  FreeCAD's own too): a visible sketch's area in front of a face took the click, so Shell
  and Hole got nothing and Create Sketch even fell through to the origin plane behind the
  part. While such a command runs (or a sketch is open), the areas let clicks through to
  the face or plane behind them, as before SciForge turned the areas on.

Commands that take profiles (Extrude, Press Pull, Revolve, Sweep, Loft) say so with a
method picks_sketch_areas() on their panel; while it returns True the areas can be
clicked as FreeCAD has them (no shift: those dialogs shade and pick areas lying on faces
themselves, profile_pick.py). When the same dialog waits for something else (Extrude's
To Object, Revolve's axis...) the areas let clicks through.

Coin nodes, both made and owned here: an SoTranslation right after the sketch's own
placement in its view provider's root (it moves the whole sketch, 0 when not idle) and an
SoPickStyle first inside FreeCAD's area node (SoSketchFaces, a separator: only the areas
are touched; "ignored" = pickable as FreeCAD has it). They are brought up to date just
before a mouse event reaches the 3D view (a Qt event filter that only looks at mouse
buttons and moves), so FreeCAD's picking always sees the state of that moment.
"""

import time

import FreeCAD as App
import FreeCADGui as Gui

from . import sketch_areas_core, warn
from .compat import QtCore, QtWidgets

FRONT = "SciForgeSketchFront"  # SoTranslation: the sketch a hair toward the camera
PICK = "SciForgeSketchAreaPick"  # SoPickStyle: the areas let clicks through or not
OFFSET = "SciForgeSketchAreaOffset"  # SoPolygonOffset: the areas drawn in front of faces
FULL_EVERY_S = 0.15  # mouse moves: every sketch is looked at again at most this often

IDLE = "idle"  # no command, no sketch open: sketches before the faces they lie on
PROFILES = "profiles"  # a dialog waits for profiles: as FreeCAD has it
OTHER = "other"  # any other command or edit: the areas let clicks through

_SKIP = "skip"  # a sketch whose display has no placement node (never seen in FreeCAD 1.1)
_state = {
    "on": False,
    "filter": None,
    "nodes": {},
    "warned": False,
    "sig": None,
    "at": 0.0,
    "face_areas": False,  # a visible sketch has an area only a face's edges bound
}


class _Entry:
    """SciForge's nodes in one sketch's display, and what they are set to (reading a
    Coin field through pivy is slow: it is only written when the value changes)."""

    __slots__ = ("front", "pick", "offset", "shift", "through")

    def __init__(self, front, pick, offset=None):
        self.front = front
        self.pick = pick
        self.offset = offset
        self.shift = 0.0
        self.through = False


# -- what the mouse may pick now ---------------------------------------------------------
def mode(gdoc=None):
    """IDLE, PROFILES or OTHER (see the module text)."""
    try:
        if Gui.Control.activeDialog():
            from . import taskui

            panel = taskui.current()
            wants = getattr(panel, "picks_sketch_areas", None) if panel is not None else None
            if wants is not None and wants():
                return PROFILES
            return OTHER
        gdoc = gdoc if gdoc is not None else Gui.ActiveDocument
        if gdoc is not None and gdoc.getInEdit() is not None:
            return OTHER
        return IDLE
    except Exception:
        return PROFILES  # (as FreeCAD has it)


# -- the Coin nodes of one sketch ----------------------------------------------------------
def _faces_node(root):
    """FreeCAD's node of the sketch's areas (SoSketchFaces, a separator), or None."""
    from pivy import coin

    kind = coin.SoType.fromName(coin.SbName("SoSketchFaces"))
    if kind.isBad():
        return None
    search = coin.SoSearchAction()
    search.setType(kind)
    search.setInterest(coin.SoSearchAction.FIRST)
    search.setSearchingAll(True)
    search.apply(root)
    path = search.getPath()
    if path is None:
        return None
    node = path.getTail()
    return node if node.isOfType(coin.SoGroup.getClassTypeId()) else None


def _make(root):
    """An _Entry with the nodes added to a sketch's display, or _SKIP."""
    from pivy import coin

    index = None
    for i in range(root.getNumChildren()):
        if root.getChild(i).isOfType(coin.SoTransformation.getClassTypeId()):
            index = i + 1  # right after the sketch's placement: shifts in sketch axes
            break
    if index is None:
        return _SKIP
    front = coin.SoTranslation()
    front.setName(FRONT)
    root.insertChild(front, index)
    pick = offset = None
    faces = _faces_node(root)
    if faces is not None:
        pick = coin.SoPickStyle()
        pick.setName(PICK)
        pick.style = coin.SoPickStyle.UNPICKABLE
        pick.style.setIgnored(True)  # pickable, as FreeCAD has it
        faces.insertChild(pick, 0)
        # FreeCAD draws a finished sketch's areas with no offset, at the very depth of
        # the face the sketch lies on, which FreeCAD pushes back by the default offset:
        # the two fought for the pixels (z-fighting) whenever the front shift below was 0
        # (inside a command) or out of date (a zoom). Pulled forward like the profile
        # shading of an open sketch (sketch_mode.ProfileShading).
        offset = coin.SoPolygonOffset()
        offset.setName(OFFSET)
        offset.factor.setValue(-1.0)
        offset.units.setValue(-1.0)
        faces.insertChild(offset, 0)
    return _Entry(front, pick, offset)


def _nodes(sketch, vobj, make):
    """The sketch's _Entry; made when missing if `make`, else None."""
    key = (sketch.Document.Name, sketch.Name)
    entry = _state["nodes"].get(key)
    if entry is _SKIP:
        return None
    root = vobj.RootNode
    if entry is not None and root.findChild(entry.front) >= 0:
        return entry
    if not make:
        return None
    # new sketch, or FreeCAD made its display again (undo of a delete): nodes again
    entry = _make(root)
    _state["nodes"][key] = entry
    return None if entry is _SKIP else entry


def _remove_nodes():
    for (doc_name, name), entry in list(_state["nodes"].items()):
        if entry is _SKIP:
            continue
        try:
            doc = App.getDocument(doc_name)
            obj = doc.getObject(name) if doc is not None else None
            vobj = obj.ViewObject if obj is not None else None
        except Exception:
            vobj = None
        if vobj is None:
            continue
        try:
            from pivy import coin  # noqa: F401  (for vobj.RootNode)

            root = vobj.RootNode
            if root.findChild(entry.front) >= 0:
                root.removeChild(entry.front)
            faces = _faces_node(root) if entry.pick is not None else None
            for node in (entry.pick, entry.offset):
                if faces is not None and node is not None and faces.findChild(node) >= 0:
                    faces.removeChild(node)
        except Exception as exc:
            warn("sketch areas: %s" % exc)
    _state["nodes"] = {}
    _state["sig"] = None


def forget(doc_name):
    """A design was closed: its sketches' nodes are not needed any more."""
    for key in [k for k in _state["nodes"] if k[0] == doc_name]:
        del _state["nodes"][key]


# -- bringing them up to date --------------------------------------------------------------
def update(force=True, pointer=None):
    """Set every sketch of the active design for what the mouse may pick now. Runs before
    each mouse event; never raises. A mouse move (force=False) only looks at the sketches
    again when what the mouse may pick or the view direction changed, or a little while
    has passed (a sketch shown or moved meanwhile); a click always does. `pointer`: (the
    3D view's drawing area, position) of the event: over an area only a face's projected
    edges bound (Auto project) the sketch lets the click through to the face."""
    if not _state["on"]:
        return
    try:
        gdoc = Gui.ActiveDocument
        if gdoc is None:
            return
        now = mode(gdoc)
        view = direction = None
        if now == IDLE:
            try:
                view = gdoc.ActiveView
                direction = App.Vector(view.getViewDirection())
            except Exception:
                direction = None  # not a 3D view: nothing is picked there
        turned = None if direction is None else tuple(round(c, 2) for c in direction)
        # where the pointer is decides only for the face's own areas (Auto project): with
        # nothing open, and in a dialog that takes those areas as the face (Press Pull:
        # its click picked the area by a depth tie with the face, and nothing happened)
        at = _coin_pos(pointer) if now == IDLE or (now == PROFILES and _faces_wanted()) else None
        sig = (gdoc.Document.Name, now, turned)
        moment = time.monotonic()
        recent = sig == _state["sig"] and moment - _state["at"] < FULL_EVERY_S
        if not force and recent and not (at is not None and _state["face_areas"]):
            return  # (with a face's own area shown, every move looks where the pointer is)
        _state["sig"], _state["at"] = sig, moment
        camera = None
        if direction is not None:
            try:
                p = view.getCameraNode().position.getValue()
                camera = App.Vector(p[0], p[1], p[2])
            except Exception:
                direction = None
        through = now == OTHER
        face_areas = False
        from pivy import coin  # noqa: F401  (FreeCAD hands out Coin nodes once pivy is loaded)

        for sketch in gdoc.Document.findObjects("Sketcher::SketchObject"):
            vobj = sketch.ViewObject
            if vobj is None:
                continue
            # (a hidden sketch is kept up to date too: a dialog may show it again)
            entry = _nodes(sketch, vobj, make=vobj.Visibility)
            if entry is None:
                continue
            shift = 0.0
            if direction is not None:
                placement = sketch.getGlobalPlacement()
                normal = placement.Rotation.multVec(App.Vector(0, 0, 1))
                shift = sketch_areas_core.front_shift(
                    normal.dot(direction), (camera - placement.Base).Length
                )
            if entry.shift != shift:
                entry.front.translation.setValue(0.0, 0.0, shift)
                entry.shift = shift
            through_here = through
            over = None
            if at is not None and vobj.Visibility:
                over = _over_face_area(view or gdoc.ActiveView, sketch, at)
                face_areas = face_areas or over is not None
            if over:
                shift, through_here = 0.0, True  # the face's own area: the face's click
                if entry.shift != shift:
                    entry.front.translation.setValue(0.0, 0.0, shift)
                    entry.shift = shift
            if entry.pick is not None and entry.through != through_here:
                entry.pick.style.setIgnored(not through_here)
                entry.through = through_here
        if at is not None:
            _state["face_areas"] = face_areas
    except Exception as exc:
        if not _state["warned"]:
            _state["warned"] = True
            warn("sketch areas: %s" % exc)


def _faces_wanted():
    """The open dialog takes a click on a face's own sketch area as the face."""
    try:
        from . import taskui

        panel = taskui.current()
        return bool(getattr(panel, "face_areas_are_faces", False))
    except Exception:
        return False


def _coin_pos(pointer):
    """The Coin viewport position of a mouse event on a 3D view's drawing area, or None."""
    if pointer is None:
        return None
    widget, pos = pointer
    try:
        if widget.metaObject().className() != "QOpenGLWidget":
            return None
        ratio = widget.devicePixelRatioF() or 1.0
        return (int(pos.x() * ratio), int((widget.height() - pos.y()) * ratio))
    except Exception:
        return None


def _over_face_area(view, sketch, at):
    """True when the pointer (Coin position `at`) is over an area of the sketch that only
    the face's projected edges bound and over none of the areas drawn on it; None when the
    sketch has no such area."""
    from . import extrude
    from .profile_pick import ray_plane

    own = extrude.face_areas(sketch)
    if not own:
        return None
    placement = sketch.getGlobalPlacement()
    normal = placement.Rotation.multVec(App.Vector(0, 0, 1))
    hit = ray_plane(view, at, placement.Base, normal)
    if hit is None:
        return False
    local = placement.inverse().multVec(hit[0])
    over_own = False
    for i, face in enumerate(sketch.InternalShape.Faces, start=1):
        if not face.isInside(local, 1e-6, True):
            continue
        if "InternalFace%d" % i not in own:
            return False  # a drawn area under the pointer: the sketch's click
        over_own = True
    return over_own


class _MouseFilter(QtCore.QObject):
    """update() before any widget sees a mouse button or a mouse move (without a button
    held: not while orbiting). Installed on the application, not on each 3D view: PySide
    handed back a new view's drawing area as an "already deleted" object for a while, so
    a filter could not be installed on it."""

    BUTTONS = (
        QtCore.QEvent.MouseButtonPress,
        QtCore.QEvent.MouseButtonRelease,
        QtCore.QEvent.MouseButtonDblClick,
    )

    def eventFilter(self, obj, event):
        try:
            kind = event.type()
            if kind in _POINTER_EVENTS and not _is_view(obj):
                # (the window and the view's parents see the same event before / after
                # the view: their position is not the view's, and a pass for them would
                # undo what the view's own pass set for the pointer)
                return False
            if kind == QtCore.QEvent.MouseMove:
                if event.buttons() == QtCore.Qt.NoButton:
                    update(force=False, pointer=(obj, event.position()))
            elif kind in self.BUTTONS:
                update(pointer=(obj, event.position()))
            elif kind == QtCore.QEvent.Wheel:
                # the zoom happens after this event: the shift follows the new distance
                QtCore.QTimer.singleShot(0, _update_now)
        except Exception:
            pass
        return False


def _update_now():
    update()


_POINTER_EVENTS = (
    QtCore.QEvent.MouseMove,
    QtCore.QEvent.MouseButtonPress,
    QtCore.QEvent.MouseButtonRelease,
    QtCore.QEvent.MouseButtonDblClick,
)


def _is_view(widget):
    """The 3D view's drawing area (where FreeCAD picks)."""
    try:
        return widget.metaObject().className() == "QOpenGLWidget"
    except Exception:
        return False


# -- on / off (with sketch_mode) ---------------------------------------------------------
def enable():
    if _state["on"]:
        return
    _state["on"] = True
    _state["warned"] = False
    try:
        _state["filter"] = _MouseFilter()
        QtWidgets.QApplication.instance().installEventFilter(_state["filter"])
    except Exception as exc:
        warn("sketch areas: %s" % exc)
        return
    update()


def disable():
    if not _state["on"]:
        return
    _state["on"] = False
    filt, _state["filter"] = _state["filter"], None
    if filt is not None:
        try:
            QtWidgets.QApplication.instance().removeEventFilter(filt)
        except Exception:
            pass
    _remove_nodes()


def later(function):
    """Run `function` from a Qt timer (never inside FreeCAD's own signal handling)."""
    try:
        QtCore.QTimer.singleShot(0, function)
    except Exception as exc:
        warn("sketch areas: %s" % exc)
