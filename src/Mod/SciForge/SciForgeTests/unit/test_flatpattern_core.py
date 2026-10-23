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
        self.assertEqual(fdxf.note(_bend(True)), "UP 90.0° R1")
        self.assertTrue(fdxf.note(_bend(False)).startswith("DOWN"))


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
