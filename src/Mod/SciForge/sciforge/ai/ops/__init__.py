# SPDX-License-Identifier: LGPL-2.1-or-later
"""Design steps: JSON objects such as {"op": "extrude", "profile": "s1", "distance": 10},
built in a real FreeCAD document with the code the SciForge dialogs use.

  core.py        Builder (runs one step at a time) and BuildError (a plain sentence that
                 says which step failed and why), the basic steps (sketch, extrude,
                 revolve, fillet, chamfer, shell, hole, patterns, parameters, edits,
                 timeline moves). Importing it registers every *_ops.py step on Builder.
  selectors.py   picks edges and faces by geometry ("the 4 top edges"), never by name
  *_ops.py       the steps of one area each (holes, patterns, sweeps, surfaces ...)

The golden models (SciForgeTests/golden/) build with this code and add their checks on
top, so 434 reference parts prove what an AI tool builds. Code here never imports from
SciForgeTests. Needs FreeCAD: import core only inside FreeCAD.
"""
