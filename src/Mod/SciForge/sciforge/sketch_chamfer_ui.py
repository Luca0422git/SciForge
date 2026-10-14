# SPDX-License-Identifier: LGPL-2.1-or-later
"""The SKETCH > MODIFY > Chamfer command: Fusion's sketch chamfer with its three types
(sketch_chamfer_tool.py). Registered by commands.py like every *_ui.py module."""

from . import sketch_chamfer_tool
from .sketch_draw_ui import _command

COMMANDS = {
    "SciForge_SketchChamfer": _command(
        sketch_chamfer_tool.SketchChamfer,
        "sk_chamfer",
        "Cut a corner off with a straight line: pick the corner (or its two lines), then "
        "type the distance (Equal distance, Distance and angle, Two distances)",
    ),
}
