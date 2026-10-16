# SPDX-License-Identifier: LGPL-2.1-or-later
"""Luca's report (2026-10-16): a pattern of bodies broke when its original was moved, edited or
deleted. Circular Pattern (CREATE menu), Pattern Type Bodies about the Z axis, Quantity 4:
copies turned 90, 180 and 270 degrees.

The steps (only real input) and the hand-derived numbers are in fixpattern_steps.py: the
original moved 20 up after the pattern, a hole cut in it after the pattern, its Extrude 1
(before the pattern) edited from the timeline, the original deleted, undo / redo of each,
save and reopen.
"""

from SciForgeTests.gui import fixpattern_steps as f
from SciForgeTests.gui import harness as h

h.run("fixpattern_circ", f.main_steps("circular", "FixPatternCirc"))
