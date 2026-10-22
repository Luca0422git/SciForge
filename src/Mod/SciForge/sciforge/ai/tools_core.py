# SPDX-License-Identifier: LGPL-2.1-or-later
"""The AI tools, as the MCP server, the bridge and the chat panel first knew them (brief
home-cloud-ai.md section 4.2). The tools themselves now live in the catalogue
(sciforge/ai/catalog), the single source of truth for every tool; this module keeps the
names older code and installed Claude extensions import: TOOLS, TOOL_NAMES, tool(),
mcp_tools(), validate(), to_steps(), step_title() and the shared help texts.

The design-changing tools turn into design steps, the JSON language of the golden models
(SciForgeTests/golden/README.md): sciforge/ai/ops builds them with the same code the golden
models prove. Pure Python: no FreeCAD, no Qt.
"""

from .catalog import (  # noqa: F401
    EDGE_TYPES,
    FACE_TYPES,
    GEOMETRY_HELP,
    SELECTOR_HELP,
    SELECTOR_KEYS,
    SKETCH_HELP,
    TOOL_NAMES,
    TOOLS,
    UNITS,
    mcp_tools,
    step_title,
    to_steps,
    tool,
    validate,
)
from .catalog.kit import check as _check  # noqa: F401
from .catalog.kit import check_selector as _check_selector  # noqa: F401
from .catalog.kit import is_type as _is_type  # noqa: F401
