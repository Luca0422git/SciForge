# SPDX-License-Identifier: LGPL-2.1-or-later
"""Selection in an open sketch: the double-click chain and the box modifiers (no FreeCAD)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from sciforge import sketch_select_core as core  # noqa: E402

RECT = {
    0: ("normal", [(0, 0), (40, 0)]),
    1: ("normal", [(40, 0), (40, 30)]),
    2: ("normal", [(40, 30), (0, 30)]),
    3: ("normal", [(0, 30), (0, 0)]),
}


class Chain(unittest.TestCase):
    def test_rectangle_from_any_edge(self):
        for start in RECT:
            self.assertEqual(sorted(core.chain(RECT, start)), [0, 1, 2, 3])

    def test_start_comes_first(self):
        self.assertEqual(core.chain(RECT, 2)[0], 2)

    def test_separate_chain_stays_out(self):
        curves = dict(RECT)
        curves[4] = ("normal", [(50, 0), (70, 0)])
        curves[5] = ("normal", [(70, 0), (70, 20)])
        self.assertEqual(sorted(core.chain(curves, 4)), [4, 5])
        self.assertEqual(sorted(core.chain(curves, 0)), [0, 1, 2, 3])

    def test_other_kind_is_not_joined(self):
        curves = dict(RECT)
        curves[6] = ("construction", [(40, 30), (50, 40)])
        self.assertEqual(sorted(core.chain(curves, 0)), [0, 1, 2, 3])
        self.assertEqual(core.chain(curves, 6), [6])

    def test_closed_curve_alone(self):
        curves = dict(RECT)
        curves[7] = ("normal", [])
        self.assertEqual(core.chain(curves, 7), [7])
        self.assertNotIn(7, core.chain(curves, 0))

    def test_branches_are_followed(self):
        curves = {
            0: ("normal", [(0, 0), (10, 0)]),
            1: ("normal", [(10, 0), (20, 0)]),
            2: ("normal", [(10, 0), (10, 10)]),
        }
        self.assertEqual(sorted(core.chain(curves, 0)), [0, 1, 2])

    def test_tolerance(self):
        curves = {0: ("normal", [(0, 0), (10, 0)]), 1: ("normal", [(10.0000001, 0), (10, 5)])}
        self.assertEqual(sorted(core.chain(curves, 0)), [0, 1])
        curves[1] = ("normal", [(10.01, 0), (10, 5)])
        self.assertEqual(core.chain(curves, 0), [0])

    def test_projected_curves_chain_among_themselves(self):
        curves = {
            0: ("normal", [(0, 0), (10, 0)]),
            -3: ("projected", [(10, 0), (10, 10)]),
            -4: ("projected", [(10, 10), (0, 10)]),
        }
        self.assertEqual(sorted(core.chain(curves, -3)), [-4, -3])
        self.assertEqual(core.chain(curves, 0), [0])

    def test_unknown_start(self):
        self.assertEqual(core.chain(RECT, 99), [])


class Box(unittest.TestCase):
    def test_plans(self):
        self.assertEqual(core.box_plan(False, False), "replace")
        self.assertEqual(core.box_plan(True, False), "add")
        self.assertEqual(core.box_plan(False, True), "toggle")
        self.assertEqual(core.box_plan(True, True), "toggle")

    def test_toggled(self):
        self.assertEqual(core.toggled(["Edge1", "Edge2"], ["Edge2", "Edge3"]), ["Edge1", "Edge3"])
        self.assertEqual(core.toggled([], ["Edge1"]), ["Edge1"])
        self.assertEqual(core.toggled(["Edge1"], []), ["Edge1"])


if __name__ == "__main__":
    unittest.main()
