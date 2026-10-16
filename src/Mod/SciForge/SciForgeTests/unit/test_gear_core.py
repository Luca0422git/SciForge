# SPDX-License-Identifier: LGPL-2.1-or-later
"""Gear tool: the number logic of sciforge/gear_core.py (sizes, the tooth outline, the
checks and their messages) and the golden-model format of its steps. Runs without
FreeCAD."""

import copy
import glob
import importlib.util
import json
import math
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
MODULE = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, MODULE)

from SciForgeTests.golden import schema  # noqa: E402
from sciforge import gear_core as core  # noqa: E402
from sciforge import timeline_core  # noqa: E402

PI = math.pi
CUT_BLOCK = 34246.27758037516  # golden sf_gear_cut_block (FreeCAD 1.1.4)
FCGEAR = os.path.join(os.path.dirname(MODULE), "PartDesign", "fcgear", "involute.py")


def _fcgear():
    """FreeCAD's own involute module (pure Python), when the source tree has it."""
    if not os.path.isfile(FCGEAR):
        return None
    spec = importlib.util.spec_from_file_location("fcgear_involute_for_tests", FCGEAR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _points(segments):
    out = []
    for seg in segments:
        if seg[0] == "bezier":
            out += seg[1]
        else:
            out += list(seg[1:])
    return out


def _message(options):
    try:
        core.check(options)
    except core.GearError as exc:
        return str(exc)
    return ""


class SizeTests(unittest.TestCase):
    def test_metric_sizes(self):
        s = core.sizes({"module": 2, "teeth": 24, "pressure_angle": 20})
        self.assertAlmostEqual(s["pitch_diameter"], 48.0)
        self.assertAlmostEqual(s["outside_diameter"], 52.0)  # m(z + 2)
        self.assertAlmostEqual(s["root_diameter"], 43.0)  # m(z - 2.5)
        self.assertAlmostEqual(s["base_diameter"], 48.0 * math.cos(math.radians(20)))
        self.assertAlmostEqual(s["pitch"], 2 * PI)

    def test_english_sizes(self):
        s = core.sizes({"standard": "english", "diametral_pitch": 10, "teeth": 20})
        self.assertAlmostEqual(s["module"], 2.54)
        self.assertAlmostEqual(s["pitch_diameter"], 20 / 10.0 * 25.4)  # z / DP inches
        self.assertAlmostEqual(s["outside_diameter"], 22 / 10.0 * 25.4)

    def test_internal_sizes(self):
        s = core.sizes({"type": "internal", "module": 2, "teeth": 40, "rim": 5})
        self.assertAlmostEqual(s["root_diameter"], 85.0)  # teeth point in: m(z + 2.5)
        self.assertAlmostEqual(s["outside_diameter"], 95.0)
        self.assertAlmostEqual(s["tip_diameter"], 76.0)  # full addendum: m(z - 2)

    def test_internal_tips_stop_at_the_base_circle(self):
        s = core.sizes({"type": "internal", "module": 2, "teeth": 24})
        self.assertAlmostEqual(s["tip_diameter"], s["base_diameter"], places=6)
        self.assertGreaterEqual(s["tip_diameter"], s["base_diameter"])

    def test_rack_sizes(self):
        s = core.sizes({"type": "rack", "module": 2, "teeth": 10, "rack_height": 5})
        self.assertAlmostEqual(s["rack_length"], 20 * PI)
        self.assertAlmostEqual(s["rack_depth"], 2.25 * 2 + 5)
        s = core.sizes({"type": "rack", "module": 2, "rack_size": "length", "rack_length": 40})
        self.assertEqual(s["rack_teeth"], 6)


class OutlineTests(unittest.TestCase):
    def test_same_outline_as_freecads_fcgear(self):
        fc = _fcgear()
        if fc is None:
            self.skipTest("FreeCAD's fcgear is not in this source tree")

        for z, fillet in ((24, 0.38), (9, 0.375), (40, 0.0)):
            mine = core._Recorder()
            core._involute(
                mine,
                2.0,
                z,
                math.radians(20),
                outer_height=1.0,
                inner_height=1.25,
                inner_fillet=fillet,
            )
            theirs = core._Recorder()
            theirs.close = lambda: None
            fc.CreateExternalGear(theirs, 2.0, z, 20, True, 1.0, 1.25, fillet)
            a, b = _points(mine.segments), _points(theirs.segments)
            self.assertEqual(len(a), len(b))
            self.assertLess(max(math.dist(p, q) for p, q in zip(a, b)), 1e-12)
        mine = core._Recorder()
        core._involute(
            mine,
            2.0,
            40,
            math.radians(20),
            rotation=PI / 40,
            outer_height=1.25,
            inner_height=0.6,
            outer_fillet=0.375,
        )
        theirs = core._Recorder()
        theirs.close = lambda: None
        fc.CreateInternalGear(theirs, 2.0, 40, 20, True, 0.6, 1.25, 0.375)
        a, b = _points(mine.segments), _points(theirs.segments)
        self.assertLess(max(math.dist(p, q) for p, q in zip(a, b)), 1e-12)

    def test_every_loop_closes(self):
        for options in (
            {},
            {"type": "internal", "teeth": 40},
            {"type": "rack"},
            {"type": "rack", "rack_size": "length", "rack_length": 37.3},
            {"backlash": 0.3, "pressure_angle": 14.5},
            {"teeth": 6, "fillet": 0.2, "hole": 0},
        ):
            for loop in core.check(options):
                if loop[0][0] == "circle":
                    continue
                for seg, nxt in zip(loop, loop[1:] + loop[:1]):
                    self.assertLess(math.dist(core._end(seg), core._start(nxt)), 1e-12, options)

    def test_tips_and_roots(self):
        xmin, ymin, xmax, ymax = core.bbox({"module": 2, "teeth": 24})
        for value in (-xmin, -ymin, xmax, ymax):
            self.assertAlmostEqual(value, 26.0, delta=0.002)  # tooth tips on the axes
        xmin, _y, xmax, _y2 = core.bbox({"type": "internal", "module": 2, "teeth": 40})
        self.assertAlmostEqual(xmax, 47.5)  # root 42.5 + rim 5

    def test_hole_and_ring_areas(self):
        solid = core.area({"hole": 0})
        self.assertAlmostEqual(core.area({"hole": 10}), solid - PI * 25.0, places=6)
        ring = core.area({"type": "internal", "teeth": 40, "rim": 5})
        self.assertLess(ring, PI * (47.5**2 - 38.0**2))
        self.assertGreater(ring, PI * (47.5**2 - 42.5**2))

    def test_the_spur_area_lies_between_root_and_tip_circles(self):
        a = core.area({"module": 2, "teeth": 24, "hole": 0})
        self.assertGreater(a, PI * 21.5**2)
        self.assertLess(a, PI * 26.0**2)
        # About half of the ring between the root and tip circles is tooth.
        self.assertAlmostEqual((a - PI * 21.5**2) / (PI * (26.0**2 - 21.5**2)), 0.5, delta=0.1)

    def test_rack_area_by_hand(self):
        for options in (
            {"type": "rack", "teeth": 10, "fillet": 0.5},
            {"type": "rack", "teeth": 7, "fillet": 0.0, "pressure_angle": 14.5},
            {"type": "rack", "teeth": 3, "fillet": 0.3, "backlash": 0.2, "pressure_angle": 25},
        ):
            self.assertAlmostEqual(core.area(options), core.rack_area(options), places=7)
        # The golden model sf_gear_rack: 464.16697654 x 6.
        self.assertAlmostEqual(
            core.rack_area({"type": "rack", "teeth": 10, "fillet": 0.5}) * 6, 2785.0018592494, 6
        )

    def test_rack_backlash_thins_every_tooth(self):
        plain = core.area({"type": "rack", "teeth": 10, "fillet": 0})
        thin = core.area({"type": "rack", "teeth": 10, "fillet": 0, "backlash": 0.2})
        self.assertAlmostEqual(plain - thin, 10 * 0.2 * 2.25 * 2.0, places=9)  # z B (ha + hf)

    def test_backlash_turns_the_flanks(self):
        plain = core.area({"hole": 0})
        thin = core.area({"hole": 0, "backlash": 0.2})
        # Each flank turns by B / (2 r): about z * delta * (ro^2 - r_root^2) less area.
        delta = 0.2 / 48.0
        self.assertAlmostEqual((plain - thin) / (24 * delta * (26.0**2 - 21.5**2)), 1.0, delta=0.1)
        ring = core.area({"type": "internal", "teeth": 40})
        thinner = core.area({"type": "internal", "teeth": 40, "backlash": 0.2})
        self.assertLess(thinner, ring)  # the ring's teeth get thinner too

    def test_rack_cut_to_length(self):
        xmin, ymin, xmax, ymax = core.bbox(
            {"type": "rack", "rack_size": "length", "rack_length": 37.3}
        )
        self.assertAlmostEqual(xmin, -18.65)
        self.assertAlmostEqual(xmax, 18.65)
        self.assertAlmostEqual(ymin, -7.5)
        self.assertAlmostEqual(ymax, 2.0)

    def test_golden_baselines_match_the_outline_area(self):
        # FreeCAD 1.1.4 padded the outline gear.py makes from this one: the same area.
        self.assertAlmostEqual(
            core.area({"module": 2, "teeth": 24, "fillet": 0.5, "hole": 10}) * 10,
            16993.535427592553,
            places=5,
        )
        cut = core.area({"module": 1.5, "teeth": 16, "fillet": 0.3, "hole": 0}) * 4
        self.assertAlmostEqual(36000.0 - cut, CUT_BLOCK, places=5)

    def test_preview_polylines(self):
        lines = core.polylines({"hole": 10})
        self.assertEqual(len(lines), 2)
        self.assertGreater(len(lines[0]), 24 * 10)


class CheckTests(unittest.TestCase):
    def test_defaults_build(self):
        for kind in core.TYPES:
            self.assertTrue(core.check({"type": kind}), kind)

    def test_too_few_teeth(self):
        self.assertIn("at least 6 teeth", _message({"teeth": 5}))
        self.assertIn("at least 12 teeth", _message({"type": "internal", "teeth": 10}))
        self.assertIn("whole number", _message({"teeth": 20.5}))
        self.assertIn("more than this tool makes", _message({"teeth": 900}))

    def test_hole_too_big(self):
        text = _message({"hole": 42})
        self.assertIn("too big", text)
        self.assertIn("at most 41 mm", text)  # root 43 less a wall of half a module each side
        self.assertEqual(_message({"hole": 41}), "")

    def test_rim_too_thin(self):
        self.assertIn("at least 1 mm", _message({"type": "internal", "teeth": 40, "rim": 0.5}))

    def test_fillet_too_big_says_the_largest(self):
        text = _message({"fillet": 1.5})
        self.assertIn("at most 1.146 mm", text)
        biggest = core.max_fillet({})
        self.assertEqual(_message({"fillet": biggest}), "")
        self.assertIn("Root Fillet", _message({"type": "rack", "fillet": 2.0}))
        self.assertEqual(
            _message({"type": "rack", "fillet": core.max_fillet({"type": "rack"})}), ""
        )

    def test_backlash_too_big(self):
        self.assertIn("come to a point", _message({"backlash": 2.0}))
        self.assertIn("come to a point", _message({"type": "rack", "backlash": 2.0}))
        self.assertIn("negative", _message({"backlash": -0.1}))

    def test_other_values(self):
        self.assertIn("Thickness", _message({"thickness": 0}))
        self.assertIn("14.5, 20 or 25", _message({"pressure_angle": 30}))
        self.assertIn("Module", _message({"module": 0}))
        self.assertIn("Diametral Pitch", _message({"standard": "english", "diametral_pitch": 0}))
        self.assertIn(
            "shorter than one tooth",
            _message({"type": "rack", "rack_size": "length", "rack_length": 5}),
        )
        self.assertIn("Height", _message({"type": "rack", "rack_height": 0}))

    def test_small_gears_at_every_pressure_angle(self):
        for angle in core.PRESSURE_ANGLES:
            self.assertEqual(_message({"teeth": 6, "pressure_angle": angle, "hole": 0}), "")


class TimelineAndSchemaTests(unittest.TestCase):
    def test_timeline_calls_it_gear(self):
        kind = timeline_core.classify("SciForge::Gear")
        self.assertEqual(kind, "gear")
        self.assertEqual(timeline_core.title_base("SciForge::Gear", kind), "Gear")
        self.assertTrue(timeline_core.is_solid(kind))

    def _model(self, name):
        path = os.path.join(MODULE, "SciForgeTests", "golden", "models", name + ".json")
        with open(path) as handle:
            return json.load(handle)

    def test_golden_models_are_valid(self):
        names = glob.glob(os.path.join(MODULE, "SciForgeTests", "golden", "models", "sf_gear_*"))
        self.assertGreaterEqual(len(names), 3)
        for path in names:
            with open(path) as handle:
                schema.validate(json.load(handle))

    def test_bad_steps_are_refused(self):
        model = self._model("sf_gear_spur_basic")
        for key, value in (("type", "bevel"), ("teeth", "many"), ("symmetric", 1), ("bogus", 1)):
            bad = copy.deepcopy(model)
            bad["steps"][0][key] = value
            with self.assertRaises(Exception, msg=key):
                schema.validate(bad)
        bad = copy.deepcopy(self._model("sf_gear_edit_teeth"))
        bad["steps"][1]["target"] = "nothing"
        with self.assertRaises(Exception):
            schema.validate(bad)


if __name__ == "__main__":
    unittest.main()
