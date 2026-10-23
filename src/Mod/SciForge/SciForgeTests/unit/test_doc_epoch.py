# SPDX-License-Identifier: LGPL-2.1-or-later
"""The panels' poll gate (sciforge/doc_epoch.py): the timeline and the browser read the
design only when something may have changed, and at least every few seconds. Runs without
FreeCAD."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sciforge import doc_epoch  # noqa: E402


class Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


class GateTest(unittest.TestCase):
    def test_first_poll_reads(self):
        gate = doc_epoch.Gate(clock=Clock())
        self.assertTrue(gate.ready((1, "Doc")))

    def test_unchanged_key_skips_until_safety(self):
        clock = Clock()
        gate = doc_epoch.Gate(safety=2.0, clock=clock)
        gate.done((1, "Doc"))
        clock.now += 1.9
        self.assertFalse(gate.ready((1, "Doc")))
        clock.now += 0.2
        self.assertTrue(gate.ready((1, "Doc")))  # the safety read

    def test_changed_key_reads(self):
        clock = Clock()
        gate = doc_epoch.Gate(clock=clock)
        gate.done((1, "Doc", None))
        self.assertTrue(gate.ready((2, "Doc", None)))  # a change counted
        self.assertTrue(gate.ready((1, "Other", None)))  # another document in front
        self.assertTrue(gate.ready((1, "Doc", ("Doc", "Body"))))  # another active body

    def test_forget(self):
        gate = doc_epoch.Gate(clock=Clock())
        gate.done((1,))
        gate.forget()
        self.assertTrue(gate.ready((1,)))

    def test_bump_counts(self):
        before = doc_epoch.value()
        doc_epoch.bump()
        doc_epoch.bump("obj", "prop")  # (an observer's arguments are ignored)
        self.assertEqual(doc_epoch.value(), before + 2)

    def test_watchers_route_every_slot(self):
        watch = doc_epoch._watcher(doc_epoch._APP_SLOTS)
        before = doc_epoch.value()
        for name in doc_epoch._APP_SLOTS:
            getattr(watch, name)("arg")
        self.assertEqual(doc_epoch.value(), before + len(doc_epoch._APP_SLOTS))

    def test_without_freecad(self):
        """Outside FreeCAD the key is None (every poll reads, as before) and nothing raises."""
        if "FreeCAD" in sys.modules:
            self.skipTest("FreeCAD loaded")
        self.assertIsNone(doc_epoch.key())
        self.assertFalse(doc_epoch.busy())


if __name__ == "__main__":
    unittest.main()
