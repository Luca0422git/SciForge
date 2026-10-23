# SPDX-License-Identifier: LGPL-2.1-or-later
"""Unit tests of the pure parts of PLASTIC part 2: Snap Fit (plastic_snap_core), Lip
(plastic_lip_core) and Design Advice (plastic_advice_core). No FreeCAD needed."""

import math
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from sciforge import plastic_advice_core as advice  # noqa: E402
from sciforge import plastic_lip_core as lip  # noqa: E402
from sciforge import plastic_snap_core as snap  # noqa: E402

RULE = {
    "name": "Default (mm)",
    "thickness": 2.0,
    "draft_angle": 1.0,
    "nominal_radius": 1.0,
    "reveal_height": 1.0,
    "clearance": 0.1,
    "minimum_thickness": 1.0,
    "maximum_thickness": 4.0,
    "thickness_variation": 25.0,
    "minimum_draft_angle": 0.5,
    "knife_edge_threshold": 0.5,
    "material": "ABS",
}


class SnapDefaults(unittest.TestCase):
    def test_defaults_follow_the_rule(self):
        o = snap.defaults(dict(RULE, thickness=1.5, clearance=0.15))
        self.assertAlmostEqual(o["thickness"], 1.5)
        self.assertAlmostEqual(o["length"], 9.0)
        self.assertAlmostEqual(o["width"], 4.5)
        self.assertAlmostEqual(o["clearance"], 0.15)
        self.assertEqual(snap.validate(o), [])

    def test_defaults_without_rule_validate(self):
        self.assertEqual(snap.validate(snap.defaults()), [])

    def test_follow_rule_only_changes_linked_fields(self):
        o = snap.unlink(snap.defaults(RULE), "thickness")
        o["thickness"] = 3.0
        out = snap.follow_rule(o, dict(RULE, thickness=2.5, clearance=0.2))
        self.assertAlmostEqual(out["thickness"], 3.0)  # typed: stays
        self.assertAlmostEqual(out["tip_thickness"], 2.5)  # linked: follows
        self.assertAlmostEqual(out["clearance"], 0.2)


class SnapChecks(unittest.TestCase):
    def test_catch_shorter_than_lead_in_is_refused(self):
        o = dict(snap.defaults(), catch_length=1.0, insertion_angle=20.0)
        problems = snap.validate(o)
        self.assertTrue(problems and "lead-in" in problems[0])

    def test_catch_longer_than_beam_is_refused(self):
        o = dict(snap.defaults(), length=3.0)
        self.assertTrue(any("Beam Length" in p for p in snap.validate(o)))

    def test_draft_that_closes_the_beam_is_refused(self):
        o = dict(snap.defaults(), draft=20.0, width=3.0, length=12.0)
        self.assertTrue(any("Draft" in p for p in snap.validate(o)))

    def test_bad_angles(self):
        self.assertTrue(snap.validate(dict(snap.defaults(), insertion_angle=90.0)))
        self.assertTrue(snap.validate(dict(snap.defaults(), retention_angle=0.0)))
        self.assertEqual(snap.validate(dict(snap.defaults(), retention_angle=60.0)), [])


class SnapGeometry(unittest.TestCase):
    def setUp(self):
        self.o = dict(snap.defaults(), draft=0.0)

    def test_catch_profile(self):
        pts = snap.catch_profile(self.o)
        lead = 1.0 / math.tan(math.radians(30))
        self.assertAlmostEqual(snap.lead_in(self.o), lead)
        self.assertEqual(pts[2], (1.0, 9.0))
        self.assertAlmostEqual(pts[3][1], 12.0 - lead)
        self.assertEqual(pts[4], (0.0, 12.0))

    def test_retention_angle_runs_back(self):
        o = dict(self.o, retention_angle=45.0)
        self.assertAlmostEqual(snap.retention_run(o), 1.0)
        self.assertAlmostEqual(snap.catch_back(o), 8.0)

    def test_groove_box_parallel(self):
        x0, x1, y0, y1, z0, z1 = snap.groove_box(self.o)
        self.assertAlmostEqual(x1 - x0, 1.2)  # catch 1 + clearance both sides
        self.assertAlmostEqual(y1 - y0, 6.2)
        self.assertAlmostEqual(z0, 8.9)
        self.assertAlmostEqual(z1, 12.1)

    def test_groove_box_perpendicular_slot(self):
        x0, x1, *_rest = snap.groove_box(dict(self.o, type="perpendicular"))
        self.assertAlmostEqual(x0, -3.1)  # beam 2 + its deflection 1 + clearance
        self.assertAlmostEqual(x1, 0.1)

    def test_loop_boxes(self):
        frame, opening = snap.loop_boxes(dict(self.o, type="loop"), reach=19.0)
        self.assertAlmostEqual(frame[1] - frame[0], 2.0)
        self.assertAlmostEqual(frame[3] - frame[2], 10.2)
        self.assertAlmostEqual(frame[4], 6.9)
        self.assertAlmostEqual(frame[5], 19.0)
        self.assertAlmostEqual(opening[5] - opening[4], 3.2)

    def test_tip_width_with_draft(self):
        o = dict(self.o, draft=1.0)
        self.assertAlmostEqual(snap.tip_width(o), 6 - 24 * math.tan(math.radians(1)))

    def test_strain(self):
        # 1.5 t y / L^2 = 1.5 x 2 x 1 / 144 = 2.08 %
        self.assertAlmostEqual(snap.strain_percent(self.o), 100 * 3.0 / 144.0)
        taper = dict(self.o, tip_thickness=1.0)
        self.assertAlmostEqual(snap.strain_percent(taper), 100 * 2.0 / 1.09 / 144.0)
        state, text = snap.strain_note(dict(self.o, length=6.0, catch_length=2.0), "ABS", 2.5)
        self.assertEqual(state, "warn")
        self.assertIn("ABS", text)
        self.assertEqual(snap.strain_note(self.o, "ABS", 2.5)[0], "ok")


class SnapFrames(unittest.TestCase):
    def test_frame_points_away_from_the_sketch_normal(self):
        ex, ey, ez = snap.frame((0, 0, 1), (1, 0, 0))
        self.assertEqual(tuple(round(v, 9) for v in ez), (0, 0, -1))
        self.assertEqual(tuple(round(v, 9) for v in ex), (1, 0, 0))
        self.assertEqual(tuple(round(v, 9) for v in ey), (0, -1, 0))

    def test_flip_and_angle(self):
        ex, _ey, ez = snap.frame((0, 0, 1), (1, 0, 0), angle=90, flip=True)
        self.assertEqual(tuple(round(v, 9) for v in ez), (0, 0, 1))
        self.assertEqual(tuple(round(v, 9) for v in ex), (0, 1, 0))

    def test_aligned_faces_out(self):
        d = snap.aligned_x((2, 20, 20), (30, 20, 20), (0, 0, 1))
        self.assertEqual(tuple(round(v, 9) for v in d), (-1, 0, 0))
        d = snap.aligned_x((2, 20, 20), (30, 20, 20), (0, 0, 1), outward=False)
        self.assertEqual(tuple(round(v, 9) for v in d), (1, 0, 0))

    def test_nearest_on_line(self):
        self.assertEqual(snap.nearest_on_line((5, 7, 0), (0, 0, 0), (10, 0, 0)), (5, 0, 0))
        self.assertEqual(snap.nearest_on_line((5, 7, 0), (0, 0, 0), (0, 0, 0)), (0, 0, 0))

    def test_independent_angles(self):
        o = dict(snap.defaults(), rotation="independent", angles=[10, 20], angle=5)
        self.assertEqual(snap.angles_for(o, 3), [10.0, 20.0, 5])
        self.assertEqual(snap.angles_for(dict(o, rotation="uniform"), 2), [5, 5])

    def test_to_global(self):
        axes = snap.frame((0, 0, 1), (1, 0, 0))
        self.assertEqual(snap.to_global((58, 20, 20), axes, (1, 0, 12)), (59, 20, 8))


class LipCore(unittest.TestCase):
    def test_defaults_from_rule(self):
        o = lip.defaults(RULE)
        self.assertAlmostEqual(o["lip_width"], 1.0)
        self.assertAlmostEqual(o["lip_height"], 1.0)
        self.assertAlmostEqual(o["groove_width"], 1.1)
        self.assertEqual(lip.validate(o), [])

    def test_sections(self):
        o = dict(lip.defaults(RULE), inner_draft=0.0, outer_draft=0.0)
        self.assertEqual(lip.lip_section(o), ((0.0, 1.0), (0.0, 1.0), 1.0))
        bottom, top, d = lip.groove_section(o)
        self.assertAlmostEqual(bottom[0], -0.1)
        self.assertAlmostEqual(bottom[1], 1.1)
        self.assertAlmostEqual(d, 1.1)
        g = dict(o, type="groove")
        self.assertEqual(lip.groove_section(g)[0], (0.0, 1.1))

    def test_drafts_narrow_the_lip(self):
        o = lip.defaults(RULE)
        _b, top, h = lip.lip_section(o)
        k = math.tan(math.radians(1.0))
        self.assertAlmostEqual(top[0], k)
        self.assertAlmostEqual(top[1], 1.0 - k)
        self.assertAlmostEqual(lip.section_area((0, 1), top, h), 1.0 - k)

    def test_refusals(self):
        self.assertTrue(lip.validate(dict(lip.defaults(RULE), lip_width=0.0)))
        self.assertTrue(lip.validate(dict(lip.defaults(RULE), inner_draft=40.0)))
        tall = dict(lip.defaults(RULE), lip_height=30.0, inner_draft=29.0, outer_draft=29.0)
        self.assertTrue(any("close" in p for p in lip.validate(tall)))
        self.assertTrue(lip.wall_check(2.0, 2.0))
        self.assertEqual(lip.wall_check(1.0, 2.0), "")

    def test_follow_rule(self):
        o = lip.unlink(lip.defaults(RULE), "lip_height")
        o["lip_height"] = 3.0
        out = lip.follow_rule(o, dict(RULE, thickness=3.0, reveal_height=1.5))
        self.assertAlmostEqual(out["lip_width"], 1.5)
        self.assertAlmostEqual(out["lip_height"], 3.0)


class AdviceChecks(unittest.TestCase):
    def test_draft(self):
        self.assertAlmostEqual(advice.draft_of((1, 0, 0), (0, 0, 1)), 0.0)
        self.assertTrue(advice.draft_issue((1, 0, 0), (0, 0, 1), 0.5))
        self.assertFalse(advice.draft_issue((0, 0, 1), (0, 0, 1), 0.5))  # square to the pull
        n = (math.cos(math.radians(2)), 0, math.sin(math.radians(2)))
        self.assertFalse(advice.draft_issue(n, (0, 0, 1), 0.5))
        self.assertTrue(advice.draft_issue(n, (0, 0, 1), 3.0))

    def test_thickness(self):
        self.assertEqual(advice.thickness_issue(0.8, RULE), "thin")
        self.assertEqual(advice.thickness_issue(5.0, RULE), "thick")
        self.assertEqual(advice.thickness_issue(2.0, RULE), "")
        self.assertTrue(advice.variation_issue(2.6, RULE))
        self.assertFalse(advice.variation_issue(2.4, RULE))

    def test_knife(self):
        self.assertAlmostEqual(advice.KNIFE_ANGLE, 53.130102354, places=6)
        self.assertTrue(advice.knife_issue(30.0))
        self.assertFalse(advice.knife_issue(90.0))

    def test_undercut(self):
        up = (0, 0, 1)
        self.assertTrue(advice.undercut_issue((0, 0, 1), up, True, False))
        self.assertFalse(advice.undercut_issue((0, 0, 1), up, False, True))
        self.assertTrue(advice.undercut_issue((0, 0, -1), up, False, True))
        self.assertTrue(advice.undercut_issue((1, 0, 0), up, True, True))
        self.assertFalse(advice.undercut_issue((1, 0, 0), up, True, False))

    def test_rays(self):
        tri = [((0, 0, 5), (10, 0, 5), (0, 10, 5)), ((0, 0, 9), (10, 0, 9), (0, 10, 9))]
        hits = advice.first_hits([(1, 1, 0), (1, 1, 6), (9, 9, 0)], [(0, 0, 1)] * 3, tri)
        self.assertAlmostEqual(hits[0], 5.0)
        self.assertAlmostEqual(hits[1], 3.0)
        self.assertIsNone(hits[2])
        self.assertAlmostEqual(advice._first_hit_py((1, 1, 0), (0, 0, 1), tri, 1e-6), 5.0)

    def test_rows_and_summary(self):
        results = {
            "bodies": [
                {
                    "name": "Body",
                    "label": "Base",
                    "faces": {
                        "Face10": {"issues": {"draft": 0.0}},
                        "Face2": {"issues": {"thin": 0.8, "undercut": None}},
                    },
                    "edges": {"Edge4": 30.0},
                }
            ]
        }
        rows = advice.rows(results)
        self.assertEqual([r[0] for r in rows], ["Thickness", "Draft", "Knife Edges", "Undercuts"])
        self.assertEqual(rows[0][2], "Face2")
        counts = advice.summary(results)
        self.assertEqual(counts["knife"], 1)
        self.assertIn("Undercuts 1", advice.summary_text(results))
        self.assertIn("No issues", advice.summary_text({"bodies": []}))

    def test_blended_thickness(self):
        samples = [(0, 0, 0, 2.0), (10, 0, 0, 4.0)]
        self.assertAlmostEqual(advice.blended_thickness((0, 0, 0), samples), 2.0)
        self.assertAlmostEqual(advice.blended_thickness((5, 0, 0), samples), 3.0)
        self.assertIsNone(advice.blended_thickness((5, 0, 0), []))

    def test_colors(self):
        self.assertEqual(advice.face_color({"draft": 0, "undercut": None}), advice.UNDERCUT)
        self.assertEqual(advice.face_color({}), advice.OK)
        self.assertEqual(advice.heat_color(1.0, 1.0, 4.0), advice.THIN)


if __name__ == "__main__":
    unittest.main()
