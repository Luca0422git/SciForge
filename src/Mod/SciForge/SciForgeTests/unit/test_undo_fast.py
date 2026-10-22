# SPDX-License-Identifier: LGPL-2.1-or-later
"""When Undo / Redo may skip the rebuild (sciforge/undo_fast.py, Ledger): only when every
shape FreeCAD put back is the one built from the values it restored. Runs without FreeCAD."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sciforge.undo_fast import Ledger, followers  # noqa: E402

TOUCHED = [("Pad", True, False), ("Fillet", True, False), ("Body", True, False)]


def edit(led, clean_start=True, clean_end=True):
    """A dialog's OK: a transaction with the recompute inside it."""
    led.opened(clean_start)
    led.committed(clean_end, len(led.undo) + 1)


def undo(led, restored=("Pad", "Fillet", "Body")):
    for name in restored:
        led.shape_restored(name)
    return led.undone(len(led.undo) - 1)


def redo(led, restored=("Pad", "Fillet", "Body")):
    for name in restored:
        led.shape_restored(name)
    return led.redone(len(led.undo) + 1)


class LedgerTest(unittest.TestCase):
    def test_undo_and_redo_of_a_clean_edit(self):
        led = Ledger()
        edit(led)
        undo(led)
        self.assertEqual(led.why_not(TOUCHED), "")
        redo(led)
        self.assertTrue(led.may_skip(TOUCHED))

    def test_outside_change_after_the_edit(self):
        led = Ledger()
        edit(led)
        led.outside_change()  # a recompute after the commit, a script
        undo(led)
        self.assertIn("outside a transaction", led.why_not(TOUCHED))

    def test_outside_change_after_the_undo_blocks_the_redo(self):
        led = Ledger()
        edit(led)
        undo(led)
        led.outside_change()
        redo(led)
        self.assertFalse(led.may_skip(TOUCHED))

    def test_outside_change_after_the_undo_blocks_its_settling(self):
        led = Ledger()
        edit(led)
        undo(led)
        led.outside_change()  # before after_undo ran
        self.assertIn("since the Undo", led.why_not(TOUCHED))

    def test_stale_design_at_the_start(self):
        led = Ledger()
        edit(led, clean_start=False)
        undo(led)
        self.assertIn("not up to date when the transaction started", led.why_not(TOUCHED))

    def test_stale_design_at_the_end_blocks_redo(self):
        led = Ledger()
        edit(led, clean_end=False)  # e.g. the recompute came after the commit
        undo(led)
        redo(led)
        self.assertIn("not up to date when the transaction ended", led.why_not(TOUCHED))

    def test_a_touched_object_whose_shape_was_not_put_back(self):
        led = Ledger()
        edit(led)
        undo(led, restored=("Pad", "Body"))
        self.assertIn("Fillet was not put back", led.why_not(TOUCHED))

    def test_objects_without_a_shape_or_in_error(self):
        led = Ledger()
        edit(led)
        undo(led)
        self.assertIn("no shape", led.why_not([("Sheet", False, False)]))
        self.assertIn("in error", led.why_not([("Pad", True, True)]))

    def test_two_undos_in_a_row(self):
        led = Ledger()
        edit(led)
        edit(led)
        undo(led)
        self.assertTrue(led.may_skip(TOUCHED))
        led.decision = None  # (settled)
        undo(led)
        self.assertTrue(led.may_skip(TOUCHED))

    def test_outside_change_between_two_edits(self):
        led = Ledger()
        edit(led)
        led.outside_change()
        edit(led)
        undo(led)
        self.assertTrue(led.may_skip(TOUCHED))  # the second started after the change
        undo(led)
        self.assertFalse(led.may_skip(TOUCHED))  # the first did not

    def test_out_of_step_with_freecad(self):
        led = Ledger()
        edit(led)
        decision = led.undone(5)  # FreeCAD's stack is not what the ledger saw
        self.assertFalse(decision["ok"])
        self.assertIn("out of step", led.why_not(TOUCHED))
        self.assertEqual(led.undo, [])

    def test_unseen_start_forgets(self):
        led = Ledger()
        edit(led)
        led.committed(True, 2)  # a commit whose start it did not see
        self.assertEqual(led.undo, [])
        undo_decision = led.undone(0)
        self.assertFalse(undo_decision["ok"])

    def test_freecad_forgets_its_oldest(self):
        led = Ledger()
        for _ in range(3):
            edit(led)
        led.opened(True)
        led.committed(True, 3)  # FreeCAD keeps 3: the oldest went
        self.assertEqual(len(led.undo), 3)
        undo(led)
        self.assertTrue(led.may_skip(TOUCHED))

    def test_new_edit_drops_the_redo_stack(self):
        led = Ledger()
        edit(led)
        undo(led)
        edit(led)
        self.assertEqual(led.redo, [])

    def test_abort_and_outside_changes_clear_the_restored_set(self):
        led = Ledger()
        led.shape_restored("Pad")
        led.aborted()
        self.assertEqual(led.restored, set())
        led.shape_restored("Pad")
        led.outside_change()
        self.assertEqual(led.restored, set())

    def test_no_undo_seen(self):
        self.assertIn("no Undo", Ledger().why_not(TOUCHED))


class FollowersTest(unittest.TestCase):
    """What is built on the design but keeps no Shape in the undo stack is recomputed after an
    Undo / Redo that skips the rebuild (2026-10-22: a drawing kept the R8 fillets after the R8
    edit was undone)."""

    def test_a_drawing_of_the_design(self):
        deps = [
            ("Fillet001", True),  # a later step: its Shape was put back
            ("Body", True),
            ("View", False),  # TechDraw::DrawViewPart of the body
            ("Dimension", False),
            ("Page", False),
        ]
        self.assertEqual(followers(["Fillet"], deps), ["View", "Dimension", "Page"])

    def test_nothing_built_on_it(self):
        self.assertEqual(followers(["Fillet"], [("Body", True), ("Fillet001", True)]), [])

    def test_stale_objects_and_repeats_are_not_followers(self):
        deps = [("Sheet", False), ("View", False), ("View", False)]
        self.assertEqual(followers(["Sheet"], deps), ["View"])


if __name__ == "__main__":
    unittest.main()
