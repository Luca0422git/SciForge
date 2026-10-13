# SPDX-License-Identifier: LGPL-2.1-or-later
"""What the Modify dialogs of the direct-modeling tools share (Replace Face, Split Face,
Silhouette Split, Align): picks on a solid without history make it a body first (its base
feature holds the solid; shown again on Cancel), a face clicked on the dialog's own preview
means the same face before the step, and the big origin squares while a box waits for a
plane."""

import time

from . import bodies, direct, warn

OVERLAY_CLICK_S = 0.8
SAME_PRESS_S = 0.1  # a mouse press this close to the square's click is that click


def body_of_pick(panel, obj):
    """The body a pick means; a plain solid (a STEP part FreeCAD opened, a converted mesh)
    becomes a body built on it (inside the dialog's undo step)."""
    body = bodies.body_of(obj)
    if body is not None:
        return body
    if direct.is_adoptable(obj):
        body = direct.adopt(obj)
        adopted = getattr(panel, "_adopted", None)
        if adopted is None:
            adopted = panel._adopted = []
        adopted.append(obj)
        return body
    return None


def restore_adopted(panel, ok):
    """Cancel took the new body away again: the plain solid shows again."""
    if ok:
        return
    for obj in getattr(panel, "_adopted", []) or []:
        try:
            if bodies.alive(obj) and not any(bodies.is_body(u) for u in obj.InList):
                bodies.set_shown(obj, True)
        except Exception:
            pass
    panel._adopted = []


def face_on_base(obj, short, step):
    """(base step, "FaceN") for a face clicked on ``obj``: a click on the dialog's own
    preview ``step`` (or a later step of its body) means that face before the step; None
    when the face was made by the step itself."""
    from . import profile_pick

    if step is None or not bodies.alive(step):
        return (obj, short)
    if bodies.body_of(obj) is not bodies.body_of(step):
        return (obj, short)
    base = step.BaseFeature
    if obj is base:
        return (obj, short)
    face = profile_pick.global_face(obj, short)
    if face is None or base is None:
        return None
    name = profile_pick.face_name_in(base, face)
    return (base, name) if name else None


class PlaneSquares:
    """The three big origin squares (like Create Sketch) while a box waits for a plane; a
    click on one calls ``take((plane, ""))`` a moment later. The click on a square is also
    seen by FreeCAD as a click on the part behind it: took_click() tells the dialog to let
    that one pick go (only that one: a new mouse press is a new pick, however quick)."""

    def __init__(self, panel, take):
        self.panel = panel
        self.take = take
        self.picker = None
        self.clicked_at = 0.0
        self.pressed_at = 0.0
        self._mouse_cb = None
        try:
            self._mouse_cb = panel.view.addEventCallback("SoMouseButtonEvent", self._mouse)
        except Exception:
            self._mouse_cb = None  # took_click() then goes by the time alone

    def _mouse(self, info):
        try:
            if info.get("State") == "DOWN":
                self.pressed_at = time.time()
        except Exception:
            pass

    def show(self, body):
        if self.picker is not None or body is None:
            return
        try:
            from .pattern_ui import front_planes

            self.picker = front_planes()(self.panel.view, body, self._clicked)
        except Exception as exc:
            warn("%s: origin planes unavailable: %s" % (self.panel.title, exc))

    def hide(self):
        if self.picker is not None:
            try:
                self.picker.remove()
            except Exception:
                pass
            self.picker = None

    def close(self):
        """The dialog closes: the squares go and the mouse is no longer watched."""
        self.hide()
        if self._mouse_cb is not None:
            try:
                self.panel.view.removeEventCallback("SoMouseButtonEvent", self._mouse_cb)
            except Exception:
                pass
            self._mouse_cb = None

    def _clicked(self, plane):
        self.clicked_at = time.time()
        from .compat import QtCore

        QtCore.QTimer.singleShot(0, lambda: self.take((plane, "")))

    def took_click(self):
        """True for the pick made by the click on a square (not for a later click)."""
        if time.time() - self.clicked_at >= OVERLAY_CLICK_S:
            return False
        return self.pressed_at - self.clicked_at < SAME_PRESS_S


def ref_text(ref):
    """What a selection box shows for (object, sub)."""
    if not ref:
        return ""
    obj, sub = ref[0], ref[1]
    if obj is None:
        return ""
    if not sub:
        return obj.Label
    body = bodies.body_of(obj)
    where = body.Label if body is not None else obj.Label
    if obj.TypeId == "Sketcher::SketchObject":
        return "Curve of %s" % obj.Label
    return "%s of %s" % (sub.rstrip("0123456789"), where)


def faces_text(names):
    n = len(names or [])
    return "%d face%s" % (n, "" if n == 1 else "s") if n else ""
