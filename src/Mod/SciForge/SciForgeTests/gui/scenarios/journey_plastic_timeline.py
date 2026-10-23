# SPDX-License-Identifier: LGPL-2.1-or-later
"""PLASTIC journey, part 3 (real clicks and keys; steps in journey_plastic_steps.py): the
enclosure of part 1 built again, then its timeline used across both components with the root
active: the history marker dragged before the Boss (both halves back to their shells, by
hand) and to the end (all back); the Lip suppressed from its right-click menu (the lip and
the groove in the Lid both gone) and unsuppressed; the Snap Fit deleted (its groove step goes
with it, the back wall whole again: + 21.824) and Ctrl+Z (all back)."""

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import journey_plastic_steps as j

h.run(
    "journey_plastic_timeline",
    j.build_steps() + j.timeline_steps(),
)
