# SPDX-License-Identifier: LGPL-2.1-or-later
"""Ends drags whose mouse release never reached the handle.

Luca: "sometimes when i click and drag arrows ... the arrow gets stuck on my cursor even
after i release my mouse button." Four ways the release is lost (found by reproducing each
with real mouse input):

1. FreeCAD's selection keeps a release that lands on a part (it selects the face and marks
   the event handled), so a handle listening through view.addEventCallback never sees it.
   Move makes this likely: the body follows the arrow and ends up under the mouse.
2. While the document recomputes, FreeCAD's progress bar filters every mouse release out
   of the application (Gui/ProgressBar.cpp). A preview recompute runs on every drag step,
   so a release at the wrong moment is eaten, for every kind of handle.
3. A double-click: FreeCAD's navigation holds the second press back and hands it to the
   scene only with the release, so a handle starts a drag after the button is already up.
4. A Coin dragger left grabbing and then clicked again forgets that it still holds the
   viewer's event grab; when the dialog later replaces the arrow, the viewer keeps a
   pointer to the freed node and FreeCAD crashed on the next mouse move.

Qt always knows whether the left button is down (QApplication.mouseButtons()), whatever
happened to the release event. Every handle checks it on its poll: dragging with no
button held means the drag is over.
"""
import time

import FreeCAD as App

from . import warn
from .compat import QtCore, QtWidgets


def left_held():
    try:
        return bool(QtWidgets.QApplication.mouseButtons() & QtCore.Qt.LeftButton)
    except Exception:
        return True  # cannot tell: never end a drag on a guess


def recomputing():
    doc = App.ActiveDocument
    return bool(doc is not None and getattr(doc, "Recomputing", False))


def end_lost_drag(handle, idle=False):
    """For handles that follow the mouse through view callbacks (their `_drag` is truthy
    while dragging): end a drag whose release was lost, as if the button came up. Their
    own poll then calls on_release. Returns True when it ended one."""
    try:
        if not getattr(handle, "_drag", None) or left_held():
            return False
        handle._drag = idle
        handle._released = True
        handle._last_event = time.time()
        try:
            from . import handles3d

            handles3d.touch()
        except Exception:
            pass
        return True
    except Exception as exc:
        warn("drag: %s" % exc)
        return False


def _event_action(view):
    return view.getViewer().getSoEventManager().getHandleEventAction()


def end_coin_drag(root, view):
    """End a Coin dragger's drag under `root` with a release of its own: the viewer's own
    event action (the one holding the dragger as its grabber) gets a left-button release
    and is applied to the handle's sub-graph only. The dragger then runs its normal end of
    drag: not active any more, the grab given back, its finish callbacks run. Not while
    the document recomputes (no Coin traversal inside it): the next poll does it."""
    if recomputing():
        return False
    try:
        from pivy import coin

        action = _event_action(view)
        event = coin.SoMouseButtonEvent()
        event.setButton(coin.SoMouseButtonEvent.BUTTON1)
        event.setState(coin.SoButtonEvent.UP)
        event.setTime(coin.SbTime.getTimeOfDay())
        event.setPosition(coin.SbVec2s(1, 1))
        action.setEvent(event)
        action.apply(root)
        return True
    except Exception as exc:
        warn("drag: could not end a lost drag: %s" % exc)
        return False


def release_grab(node, view):
    """Before a Coin dragger is removed: if the viewer still has it as its event grabber,
    give the grab back, so the viewer never keeps a pointer to a freed node (cause 4)."""
    try:
        action = _event_action(view)
        grabber = action.getGrabber()
        if grabber is not None and grabber == node:
            action.releaseGrabber()
            return True
    except Exception as exc:
        warn("drag: %s" % exc)
    return False


def guard_coin_dragger(dragger, root, view):
    """For Coin draggers polled by a timer: True when the dragger is still dragging after
    the guard (a lost release is ended here)."""
    try:
        active = bool(dragger.isActive.getValue())
        if active and not left_held() and end_coin_drag(root, view):
            active = bool(dragger.isActive.getValue())
        return active
    except Exception as exc:
        warn("drag: %s" % exc)
        return False


def before_remove(dragger, root, view):
    """For Coin draggers about to be taken out of the scene."""
    try:
        if bool(dragger.isActive.getValue()):
            end_coin_drag(root, view)
    except Exception as exc:
        warn("drag: %s" % exc)
    release_grab(dragger, view)
