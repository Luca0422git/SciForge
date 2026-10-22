# SPDX-License-Identifier: LGPL-2.1-or-later
"""The AI tools that are not design steps (sciforge/ai/catalog says which): reading the
design, the timeline, parameters, design files, drawings, the view, sketch editing,
assembly. Each action is a function (ctx, args) -> bridge_core result, registered with
@action("tool name"); sciforge/ai/executor.py calls it after the arguments were checked and
the tool is available. Actions call the same SciForge code as the commands and dialogs
(timeline_ops, parameters, drawing, joints...), never raw FreeCAD calls that would skip
SciForge's behaviour. Needs FreeCAD."""

ACTIONS = {}


def action(name):
    def register(fn):
        ACTIONS[name] = fn
        return fn

    return register


from . import document_actions  # noqa: E402,F401
from . import inspect_actions  # noqa: E402,F401
from . import sketch_actions  # noqa: E402,F401
from . import timeline_actions  # noqa: E402,F401
from . import assemble_actions  # noqa: E402,F401
from . import drawing_actions  # noqa: E402,F401
from . import view_actions  # noqa: E402,F401
