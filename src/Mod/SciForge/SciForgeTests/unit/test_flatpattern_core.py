# SPDX-License-Identifier: LGPL-2.1-or-later
"""Pure-Python parts of the SHEET METAL flat tools (sm-flat): the flat pattern's DXF writer
and read-back, the bend maths the flat sizes rest on, the FLAT PATTERN tab, the browser's
Flat Pattern node and the golden step format."""

import math
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from sciforge import browser_core, flatpattern_dxf as fdxf, ribbon_config as cfg  # noqa: E402
from sciforge import flatpattern_core as fcore  # noqa: E402
from sciforge import sheetmetal_core as core  # noqa: E402


def _bend(up=True):
    return {
        "up": up,
        "angle": 90.0,
        "radius": 1.0,
        "start": [(48.0, 0.0), (48.0, 20.0)],
        "centre": [(49.130973, 0.0), (49.130973, 20.0)],
        "end": [(50.261947, 0.0), (50.261947, 20.0)],
    }


OUTER = [
    ("line", 0, 0, 98.26, 0),
    ("line", 98.26, 0, 98.26, 20),
    ("line", 98.26, 20, 0, 20),
    ("line", 0, 20, 0, 0),
]


class DxfTest(unittest.TestCase):
    def test_layers_and_counts(self):
        text = fdxf.write(OUTER, [("circle", 30, 10, 3)], [_bend(True), _bend(False)])
        counts = fdxf.count_by_layer(text)
        self.assertEqual(counts[fdxf.OUTER], {"LINE": 4})
        self.assertEqual(counts[fdxf.INTERIOR], {"CIRCLE": 1})
        self.assertEqual(counts[fdxf.BEND_UP], {"LINE": 1})
        self.assertEqual(counts[fdxf.BEND_DOWN], {"LINE": 1})
        self.assertEqual(counts[fdxf.EXTENT], {"LINE": 4})
        self.assertEqual(counts[fdxf.TEXT], {"TEXT": 2})
        for name, _color, _lt in fdxf.LAYERS:
            self.assertIn(name, text)
        self.assertIn("AC1009", text)

    def test_options_drop_lines(self):
        text = fdxf.write(
            OUTER, [], [_bend()], {"center_lines": False, "extent_lines": False, "notes": False}
        )
        counts = fdxf.count_by_layer(text)
        self.assertNotIn(fdxf.BEND_UP, counts)
        self.assertNotIn(fdxf.EXTENT, counts)
        self.assertNotIn(fdxf.TEXT, counts)

    def test_polyline_and_spline(self):
        poly = ("polyline", [(0, 0), (1, 0.1), (2, 0)], False)
        spline = ("spline", 3, [0, 0, 0, 0, 1, 1, 1, 1], [(0, 0), (1, 1), (2, 1), (3, 0)])
        counts = fdxf.count_by_layer(fdxf.write([], [poly, spline], []))
        self.assertEqual(counts[fdxf.INTERIOR], {"POLYLINE": 1, "SPLINE": 1})

    def test_arc(self):
        counts = fdxf.count_by_layer(fdxf.write([("arc", 0, 0, 5, 0, 90)], [], []))
        self.assertEqual(counts[fdxf.OUTER], {"ARC": 1})

    def test_unknown_entity(self):
        with self.assertRaises(ValueError):
            fdxf.write([("blob", 1)], [], [])

    def test_note(self):
        self.assertEqual(fdxf.note(_bend(True)), "UP 90.0%%d R1")
        text = fdxf.write(OUTER, [], [_bend(True)])
        text.encode("ascii")  # an R12 DXF is plain ASCII
        self.assertTrue(fdxf.note(_bend(False)).startswith("DOWN"))


class CornerTest(unittest.TestCase):
    """Corner reliefs go where two bends' centre lines cross near their ends."""

    def _bend(self, a, b):
        return {"centre": [a, b]}

    def test_tray_corner(self):
        # a tray's right and top bends: lines x = 49.13 (y 2..28) and y = 29.13 (x 2..48)
        bends = [self._bend((49.13, 2), (49.13, 28)), self._bend((2, 29.13), (48, 29.13))]
        found = fcore.corner_points(bends, reach=8.0)
        self.assertEqual(len(found), 1)
        x, y, i, j = found[0]
        self.assertAlmostEqual(x, 49.13)
        self.assertAlmostEqual(y, 29.13)
        self.assertEqual((i, j), (0, 1))

    def test_parallel_and_far(self):
        u = [self._bend((29, 0), (29, 20)), self._bend((87, 0), (87, 20))]
        self.assertEqual(fcore.corner_points(u, reach=8.0), [])
        # crossing in the middle of a long line is no corner
        t = [self._bend((0, 10), (100, 10)), self._bend((50, 12), (50, 40))]
        self.assertEqual(fcore.corner_points(t, reach=5.0), [])

    def test_relief_size(self):
        rule = core.evaluated(core.library_rule(core.DEFAULT_RULE))
        self.assertEqual(fcore.relief_size(rule), ("round", 4.0))
        rule["corner_relief_2bend_shape"] = "tear"
        self.assertEqual(fcore.relief_size(rule)[1], 0.0)

    def test_line_crossing(self):
        self.assertIsNone(fcore.line_crossing((0, 0), (1, 0), (0, 1), (1, 1)))
        self.assertEqual(fcore.line_crossing((0, 0), (2, 0), (1, -1), (1, 1)), (1.0, 0.0))

    def _zone(self, start, centre, end):
        return {"start": start, "centre": centre, "end": end}

    def test_placements(self):
        # tray corner: the right bend runs x 48 -> 50.26 (centre 49.13), the top one y 28 ->
        # 30.26 (centre 29.13); both 2.26 wide
        right = fcore.bend_frame(
            self._zone([(48, 2), (48, 28)], [(49.13, 2), (49.13, 28)], [(50.26, 2), (50.26, 28)])
        )
        top = fcore.bend_frame(
            self._zone([(2, 28), (48, 28)], [(2, 29.13), (48, 29.13)], [(2, 30.26), (48, 30.26)])
        )
        p, d, out, half = right
        self.assertAlmostEqual(half, 1.13)
        self.assertAlmostEqual(out[0], 1.0)
        self.assertAlmostEqual(abs(d[1]), 1.0)
        x, y = fcore.relief_centre("intersection", right, top, 4.0)
        self.assertAlmostEqual(x, 49.13)
        self.assertAlmostEqual(y, 29.13)
        x, y = fcore.relief_centre("vertex", right, top, 4.0)
        self.assertAlmostEqual(x, 48.0)
        self.assertAlmostEqual(y, 28.0)
        # tangent: the 4 mm relief reaches the far side of both zones (50.26 - 2 = 48.26)
        x, y = fcore.relief_centre("tangent", right, top, 4.0)
        self.assertAlmostEqual(x, 48.26)
        self.assertAlmostEqual(y, 28.26)
        self.assertIsNone(fcore.relief_centre("intersection", right, right, 4.0))

    def test_axes_meet_and_nearest(self):
        # two bend axes of a tray at z 2: along y at x 49, along x at y 29
        m = fcore.axes_meet((49, 0, 2), (0, 1, 0), (0, 29, 2), (1, 0, 0))
        self.assertEqual([round(c, 9) for c in m], [49, 29, 2])
        self.assertIsNone(fcore.axes_meet((0, 0, 0), (1, 0, 0), (0, 1, 0), (2, 0, 0)))
        pts = [(0, 0, 0), (49, 30, 1), (49, 29.5, 2.5)]
        self.assertEqual(fcore.nearest((49, 29, 2), pts, 3.0), 2)
        self.assertIsNone(fcore.nearest((49, 29, 2), pts[:1], 3.0))


class BendMathsTest(unittest.TestCase):
    """The flat sizes the golden models expect (T 1, R 1, K 0.44)."""

    def test_l_bracket(self):
        ba = core.bend_allowance(90, 1.0, 1.0, 0.44)
        self.assertAlmostEqual(ba, math.pi / 2 * 1.44, places=9)
        self.assertAlmostEqual(48 + 48 + ba, 100 - core.bend_deduction(90, 1, 1, 0.44), places=9)
        self.assertAlmostEqual(48 + 48 + ba, 98.26195, places=5)

    def test_flat_hem_neutral_radius(self):
        # a bend with no inner radius still has a neutral layer at K * T
        self.assertAlmostEqual(core.bend_allowance(180, 0.0, 1.0, 0.44), math.pi * 0.44)


class RibbonTest(unittest.TestCase):
    def test_flat_pattern_tab(self):
        tab = next(t for t in cfg.TABS if t["id"] == "flat_pattern")
        self.assertTrue(tab.get("contextual"))
        titles = [g["title"] for g in tab["groups"]]
        self.assertEqual(titles[-1], "FINISH FLAT PATTERN")
        self.assertIn("EXPORT", titles)
        self.assertEqual(cfg.TABS[0]["id"], "solid")

    def test_sheet_metal_commands_wired(self):
        tab = next(t for t in cfg.TABS if t["id"] == "sheet_metal")
        names = set()
        for grp in tab["groups"]:
            for entry in cfg.iter_items(grp["items"]):
                if entry and entry.get("command"):
                    command = entry["command"]
                    names.update(command if isinstance(command, tuple) else [command])
        for name in (
            "SciForge_CreateFlatPattern",
            "SciForge_Unfold",
            "SciForge_Refold",
            "SciForge_Rip",
            "SciForge_ConvertToSheetMetal",
        ):
            self.assertIn(name, names)


class BrowserTest(unittest.TestCase):
    def test_flat_pattern_node(self):
        objects = [
            {"name": "Body", "label": "Body", "type_id": "PartDesign::Body", "visible": True},
            {
                "name": "FlatPattern",
                "label": "Flat Pattern",
                "type_id": "Part::FeaturePython",
                "visible": False,
                "sciforge_type": "FlatPattern",
                "describe": "Flat 98.26 x 20.00 mm, 1 bend(s)",
            },
        ]
        for obj in objects:
            obj.setdefault("body", None)
            obj.setdefault("component", None)
        folders = browser_core._folders(objects, "Body", None)
        kinds = [n["kind"] for n in folders]
        self.assertIn("flat_pattern", kinds)
        node = next(n for n in folders if n["kind"] == "flat_pattern")
        self.assertEqual(node["icon"], "flat_pattern")
        self.assertIn("98.26 x 20.00", node["tip"])
        self.assertIn("Export DXF", browser_core.MENUS["flat_pattern"])


class GoldenSchemaTest(unittest.TestCase):
    def setUp(self):
        from SciForgeTests.golden import schema

        self.schema = schema

    def _model(self, steps):
        return {
            "id": "x",
            "title": "x",
            "steps": steps,
            "expect": {"volume": 1, "source": "analytic", "note": "x"},
        }

    def test_good_steps(self):
        sel = {"type": "plane", "count": 1}
        self.schema.validate(
            self._model(
                [
                    {"op": "sf_sm_convert", "id": "c", "face": sel},
                    {"op": "sf_unfold", "id": "u", "face": sel, "all": True},
                    {"op": "sf_refold", "id": "r", "unfold": "u"},
                    {"op": "sf_rip", "id": "p", "type": "face", "face": sel},
                    {"op": "sf_flat_pattern", "id": "f", "face": sel},
                ]
            )
        )

    def test_bad_steps(self):
        sel = {"type": "plane", "count": 1}
        bad = [
            [{"op": "sf_unfold", "id": "u", "face": sel}],
            [{"op": "sf_refold", "id": "r", "unfold": "nope"}],
            [{"op": "sf_rip", "id": "p", "type": "points", "point1": sel}],
            [{"op": "sf_rip", "id": "p", "type": "slice", "face": sel}],
        ]
        for steps in bad:
            with self.assertRaises(Exception):
                self.schema.validate(self._model(steps))


if __name__ == "__main__":
    unittest.main()
