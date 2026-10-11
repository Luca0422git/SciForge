# SPDX-License-Identifier: LGPL-2.1-or-later
"""Mirror with Fusion's dialog: Pattern Type (Faces / Bodies / Features), Objects and the
Mirror Plane. The plane is an origin plane (the three big squares drawn while the Mirror
Plane box waits, as in Create Sketch), a flat face of the part or a construction plane
(click it in the view or the browser). Live preview; OK / Cancel / Esc; one undo step;
double-click the Mirror in the timeline to change it. The document side is pattern.py.
"""
import FreeCAD as App

from . import pattern, ui_icon_path, warn
from .pattern_ui import PatternPanel, edit, start


class MirrorPanel(PatternPanel):
    kind = "mirror"

    def __init__(self, doc, kind="mirror", feature=None, preselection=None):
        super().__init__(doc, kind="mirror", feature=feature, preselection=preselection)


class MirrorCommand:
    def GetResources(self):
        return {
            "MenuText": "Mirror",
            "ToolTip": "Mirror features, faces or a body across a plane or a flat face, "
            "with a live preview",
            "Pixmap": ui_icon_path("mirror"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            start("mirror", MirrorPanel)
        except Exception as exc:
            warn("Mirror could not start: %s" % exc)


def edit_mirror(feature):
    edit(feature)


COMMANDS = {"SciForge_Mirror": MirrorCommand}
EDITORS = {"PartDesign::Mirrored": edit_mirror, "SciForge::Mirror": edit_mirror}
__all__ = ["MirrorPanel", "MirrorCommand", "pattern"]
