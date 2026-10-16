# SPDX-License-Identifier: LGPL-2.1-or-later
"""The SKETCH > MODIFY > Fillet command: Fusion's sketch fillet between lines, arcs and
circles (sketch_fillet_tool.py). Registered by commands.py like every *_ui.py module."""

from . import sketch_fillet_tool
from .sketch_draw_ui import _command

COMMANDS = {
    "SciForge_SketchFillet": _command(
        sketch_fillet_tool.SketchFillet,
        "sk_fillet",
        "Round a corner with an arc: pick the corner (or two lines, arcs or circles), then "
        "drag or type the radius",
    ),
}
