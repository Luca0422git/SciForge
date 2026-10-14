# SPDX-License-Identifier: LGPL-2.1-or-later
"""Navigation bar > Grid and Snaps > Incremental Move and Set Increments, the setting side
(no Qt): while Incremental Move is on, dragging a handle (Move/Copy's arrows and rings, a
command's blue arrows and angle handles) goes in steps of the set increments, like Fusion.
The handle classes call linear() / angular() on the value they are dragged to.

Kept in the preferences (Mod/SciForge/Grid), like Fusion remembers them.
"""

from . import nav_core

PARAMS = "User parameter:BaseApp/Preferences/Mod/SciForge/Grid"


def _group():
    import FreeCAD as App

    return App.ParamGet(PARAMS)


def is_on():
    try:
        return _group().GetBool("IncrementalMove", False)
    except Exception:
        return False


def set_on(on):
    _group().SetBool("IncrementalMove", bool(on))


def linear_step():
    try:
        return float(_group().GetFloat("LinearIncrement", nav_core.DEFAULT_LINEAR))
    except Exception:
        return nav_core.DEFAULT_LINEAR


def angular_step():
    try:
        return float(_group().GetFloat("AngularIncrement", nav_core.DEFAULT_ANGULAR))
    except Exception:
        return nav_core.DEFAULT_ANGULAR


def set_steps(linear=None, angular=None):
    group = _group()
    if linear is not None and linear > 0:
        group.SetFloat("LinearIncrement", float(linear))
    if angular is not None and angular > 0:
        group.SetFloat("AngularIncrement", float(angular))


def linear(value):
    """A dragged distance (mm), in steps while Incremental Move is on."""
    if value is None or not is_on():
        return value
    return nav_core.snap(value, linear_step())


def angular(value):
    """A dragged angle (degrees), in steps while Incremental Move is on."""
    if value is None or not is_on():
        return value
    return nav_core.snap(value, angular_step())


def reset():
    """Fusion's defaults (the scenarios' harness)."""
    group = _group()
    group.SetBool("IncrementalMove", False)
    group.SetFloat("LinearIncrement", nav_core.DEFAULT_LINEAR)
    group.SetFloat("AngularIncrement", nav_core.DEFAULT_ANGULAR)
