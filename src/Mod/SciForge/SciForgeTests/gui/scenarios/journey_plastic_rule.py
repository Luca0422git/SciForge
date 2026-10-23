# SPDX-License-Identifier: LGPL-2.1-or-later
"""PLASTIC journey, part 2 (real clicks and keys; steps in journey_plastic_steps.py): the
enclosure of part 1 built again (components Base and Lid, ABS 2 mm, shells, Boss pairs with
ribs, Snap Fit, Lip And Groove, Rest), then the design's rule edited in Manage Plastic Rules
to a 2.5 mm wall: both Shell steps (by hand), the Boss's ribs (0.6 x 2.5), the Snap Fit's
beam, the Lip's width (2.5 / 2) and the Rest's thickness follow; Ctrl+Z puts every one back
to 2 mm, Ctrl+Y to 2.5. Saved, closed, reopened: the same volumes and steps; the Boss edited
by double-clicking it in the timeline (Offset Position 1 moves both halves), OK, Ctrl+Z; the
Snap Fit edited (the rule's 2.5 mm and the turn read back, Beam Length 14), OK; the Lip
edited (4 edges, the rule's width 1.25, Lip Height 1.5 grows it), Esc leaves it."""

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import journey_plastic_steps as j

h.run(
    "journey_plastic_rule",
    j.build_steps() + j.rule_steps() + j.reopen_steps(),
)
