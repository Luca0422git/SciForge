# SPDX-License-Identifier: LGPL-2.1-or-later
"""PLASTIC journey, part 1: a plastic enclosure built like a Fusion user builds it, only with
real clicks and keys (steps and hand numbers in journey_plastic_steps.py): a new design,
components Base and Lid from two extrudes (the Lid's from a start offset of 25), PLASTIC >
Assign Plastic Rule ABS 2 mm for each, Shell of each with the rule's 2 mm wall, Boss pairs
at four points of a sketch on the parting plane (head side in the Lid, thread side in the
Base, with ribs), a Snap Fit on the long back wall (its groove in the Base), a Lip on the
Base's rim (its groove in the Lid), a Rest on the front wall, Design Advice on both bodies."""

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import journey_plastic_steps as j

h.run(
    "journey_plastic",
    j.build_steps() + j.advice_steps(),
)
