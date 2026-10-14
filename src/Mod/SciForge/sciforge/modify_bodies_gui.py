# SPDX-License-Identifier: LGPL-2.1-or-later
"""View provider of the hidden follower steps of a Shell / Draft / Scale / Pattern over
several bodies (modify_bodies.py). A follower is never in the timeline or the browser; a
double-click that reaches it anyway opens the dialog of the step it follows. Saved in files
as "sciforge.modify_bodies_gui.FollowerViewProvider": keep the name."""

from . import modify_bodies, ui_icon_path, warn
from .compat import QtCore

ICONS = {
    "ShellFollower": "shell",
    "DraftFollower": "draft",
    "ScaleFollower": "scale",
    "PatternFollower": "pattern_rect",
}


class FollowerViewProvider:
    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object

    def getIcon(self):
        obj = getattr(self, "Object", None)
        return ui_icon_path(ICONS.get(getattr(obj, "SciForgeType", ""), "shell"))

    def setEdit(self, vobj, mode=0):
        if mode != 0:
            return None
        self._edit(vobj.Object)
        return True

    def unsetEdit(self, vobj, mode=0):
        return None

    def doubleClicked(self, vobj):
        self._edit(vobj.Object)
        return True

    @staticmethod
    def _edit(obj):
        try:
            lead = modify_bodies.lead_of(obj)
            if lead is not None:
                from . import taskui

                QtCore.QTimer.singleShot(0, lambda: taskui.edit_object(lead))
        except Exception as exc:
            warn("could not edit the step of %s: %s" % (obj.Label, exc))

    def dumps(self):
        return None

    def loads(self, state):
        return None

    __getstate__ = dumps
    __setstate__ = loads
