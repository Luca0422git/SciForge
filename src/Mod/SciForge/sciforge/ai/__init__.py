# SPDX-License-Identifier: LGPL-2.1-or-later
"""SciForge's AI connectors (docs/sciforge/dev/briefs/home-cloud-ai.md, section 4).

ops/  the design steps an AI tool performs (sketch, extrude, fillet, hole, patterns...),
      the same code the golden models run (SciForgeTests/golden/).

Nothing here is imported at start and nothing runs unless the person switches the AI
options on. This file imports nothing, so parts that run outside FreeCAD (the MCP server
an AI app starts) can live in this package.
"""
