# SPDX-License-Identifier: LGPL-2.1-or-later
"""The SURFACE tools' table and rules (sciforge/surface_core.py), the timeline's names for
their steps and the ribbon's SURFACE tab. Runs without FreeCAD."""

import math
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from sciforge import ribbon_config  # noqa: E402
from sciforge import surface_core as core  # noqa: E402
from sciforge import timeline_core  # noqa: E402

ICONS = os.path.join(ROOT, "sciforge", "icons", "ui")
TOOLS = (
    "extrude",
    "revolve",
    "sweep",
    "loft",
    "patch",
    "ruled",
    "offset",
    "boundary_fill",
    "thicken",
    "trim",
    "untrim",
    "extend",
    "stitch",
    "unstitch",
    "reverse_normal",
)


def close(a, b, tol=1e-9):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


class TableTests(unittest.TestCase):
    def test_every_fusion_tool_is_a_kind(self):
        for kind in TOOLS:
            spec = core.spec(kind)
            for key in ("title", "icon", "type", "create", "operations", "defaults"):
                self.assertIn(key, spec, (kind, key))

    def test_types_are_unique_and_map_back(self):
        types = [spec["type"] for spec in core.KINDS.values()]
        self.assertEqual(len(types), len(set(types)))
        for kind in core.KINDS:
            self.assertEqual(core.kind_of_type(core.sciforge_type(kind)), kind)
        self.assertIsNone(core.kind_of_type("Pad"))
        self.assertIsNone(core.kind_of_type(None))

    def test_unknown_kind_is_explained(self):
        with self.assertRaises(core.SurfaceError):
            core.spec("fill")

    def test_create_and_modify_like_fusion(self):
        create = {"extrude", "revolve", "sweep", "loft", "patch", "ruled", "offset"}
        create |= {"boundary_fill", "thicken"}
        for kind in TOOLS:
            self.assertEqual(core.makes_body(kind), kind in create, kind)

    def test_operations(self):
        self.assertEqual(core.operations("patch"), ["new_body", "new_component"])
        self.assertEqual(
            core.operations("thicken"), ["join", "cut", "intersect", "new_body", "new_component"]
        )
        self.assertEqual(core.operations("boundary_fill"), core.operations("thicken"))
        self.assertEqual(core.operations("trim"), [])
        for kind in TOOLS:
            ops = core.operations(kind)
            if ops:
                self.assertIn(core.spec(kind)["defaults"].get("operation"), ops, kind)
        self.assertTrue(core.is_solid_operation("join"))
        self.assertFalse(core.is_solid_operation("new_body"))

    def test_icons_exist(self):
        names = {spec["icon"] for spec in core.KINDS.values()}
        names |= {icon for _title, icon in core.TIMELINE_KINDS.values()}
        names.add("surface_body")
        for name in names:
            self.assertTrue(os.path.isfile(os.path.join(ICONS, name + ".svg")), name)

    def test_defaults_are_copied(self):
        a = core.with_defaults("trim")
        a["cells"].append([1, 2, 3])
        self.assertEqual(core.with_defaults("trim")["cells"], [])

    def test_defaults_merge(self):
        o = core.with_defaults("extrude", {"distance": 5, "direction": None, "extra": None})
        self.assertEqual(o["distance"], 5)
        self.assertEqual(o["direction"], "one_side")  # None keeps the default
        self.assertNotIn("extra", o)

    def test_fusion_starting_values(self):
        self.assertEqual(core.with_defaults("revolve")["angle"], 360.0)
        self.assertEqual(core.with_defaults("stitch")["tolerance"], core.STITCH_TOLERANCE)
        self.assertEqual(core.with_defaults("patch")["continuity"], "connected")
        self.assertEqual(core.with_defaults("thicken")["direction"], "one_side")
        self.assertEqual(core.with_defaults("thicken")["thicken_type"], "sharp")
        self.assertEqual(core.with_defaults("extend")["extend_type"], "natural")
        self.assertEqual(core.with_defaults("untrim")["loop_type"], "all")
        self.assertTrue(core.with_defaults("unstitch")["chain"])


class TimelineTests(unittest.TestCase):
    def test_surface_steps_have_timeline_names(self):
        for sftype, tkind in core.TIMELINE_BY_TYPE.items():
            self.assertIn(tkind, timeline_core.KINDS, sftype)
            self.assertEqual(timeline_core.KIND_BY_SCIFORGE_TYPE.get(sftype), tkind, sftype)

    def test_every_timeline_step_is_a_kind(self):
        for sftype in core.TIMELINE_BY_TYPE:
            self.assertIsNotNone(core.kind_of_type(sftype), sftype)
        # the hidden first step of an unstitched piece is not in the timeline
        self.assertNotIn(core.sciforge_type("piece"), core.TIMELINE_BY_TYPE)

    def test_fusion_names(self):
        self.assertEqual(core.TIMELINE_KINDS["surface_extrude"][0], "Extrude")
        self.assertEqual(core.TIMELINE_KINDS["boundary_fill"][0], "Boundary Fill")
        self.assertEqual(core.TIMELINE_KINDS["reverse_normal"][0], "Reverse Normal")


class RibbonTests(unittest.TestCase):
    def _items(self, group):
        out = []
        for item in group["items"]:
            if isinstance(item, dict) and "items" in item:
                out.extend(self._items(item))
            elif isinstance(item, dict):
                out.append(item)
        return out

    def _labels_commands(self, group):
        return [(i.get("label"), i.get("command")) for i in self._items(group)]

    def test_surface_create(self):
        found = self._labels_commands(ribbon_config.SURFACE_CREATE)
        labels = [label for label, _c in found]
        for label in (
            "Extrude",
            "Revolve",
            "Sweep",
            "Loft",
            "Patch",
            "Ruled",
            "Offset",
            "Thicken",
            "Boundary Fill",
        ):
            self.assertIn(label, labels)
        self.assertIn(("Patch", "SciForge_Patch"), found)

    def test_surface_modify(self):
        labels = [label for label, _c in self._labels_commands(ribbon_config.SURFACE_MODIFY)]
        for label in ("Trim", "Untrim", "Extend", "Stitch", "Unstitch", "Reverse Normal"):
            self.assertIn(label, labels)

    def test_solid_tab_thicken_and_boundary_fill(self):
        found = self._labels_commands(ribbon_config.SOLID_CREATE)
        self.assertIn(("Thicken", "SciForge_Thicken"), found)
        self.assertIn(("Boundary Fill", "SciForge_BoundaryFill"), found)


class ValueTests(unittest.TestCase):
    def test_zero_distance_waits_for_the_arrow(self):
        for kind, key in (
            ("extrude", "distance"),
            ("offset", "distance"),
            ("extend", "distance"),
            ("thicken", "thickness"),
            ("ruled", "distance"),
        ):
            with self.assertRaises(core.NeedsPick):
                core.check_values(kind, core.with_defaults(kind, {key: 0.0}))

    def test_not_a_number(self):
        with self.assertRaises(core.SurfaceError) as raised:
            core.check_values("extrude", core.with_defaults("extrude", {"distance": "ten"}))
        self.assertNotIsInstance(raised.exception, core.NeedsPick)
        with self.assertRaises(core.SurfaceError):
            core.check_values("thicken", core.with_defaults("thicken", {"thickness": float("nan")}))

    def test_extrude(self):
        ok = core.with_defaults("extrude", {"distance": 10})
        core.check_values("extrude", ok)
        two = core.with_defaults("extrude", {"direction": "two_sides", "distance2": 4})
        core.check_values("extrude", two)  # distance 0 one way, 4 the other: fine
        with self.assertRaises(core.SurfaceError):
            core.check_values("extrude", dict(ok, taper=89))
        with self.assertRaises(core.SurfaceError):
            core.check_values("extrude", dict(ok, direction="sideways"))

    def test_revolve(self):
        core.check_values("revolve", core.with_defaults("revolve"))
        sym = core.with_defaults("revolve", {"direction": "symmetric", "angle": 180})
        core.check_values("revolve", sym)
        with self.assertRaises(core.SurfaceError):
            core.check_values("revolve", dict(sym, angle=190))
        with self.assertRaises(core.SurfaceError):
            core.check_values(
                "revolve",
                core.with_defaults(
                    "revolve", {"direction": "two_sides", "angle": 300, "angle2": 90}
                ),
            )
        with self.assertRaises(core.NeedsPick):
            core.check_values("revolve", core.with_defaults("revolve", {"angle": 0}))
        core.check_values("revolve", core.with_defaults("revolve", {"type": "full", "angle": 0}))

    def test_sweep_distance_is_a_share(self):
        core.check_values("sweep", core.with_defaults("sweep", {"distance": 0.5}))
        with self.assertRaises(core.SurfaceError):
            core.check_values("sweep", core.with_defaults("sweep", {"distance": 1.5}))

    def test_patch(self):
        core.check_values("patch", core.with_defaults("patch", {"continuity": "curvature"}))
        with self.assertRaises(core.SurfaceError):
            core.check_values("patch", core.with_defaults("patch", {"continuity": "G3"}))
        with self.assertRaises(core.SurfaceError):
            core.check_values("patch", core.with_defaults("patch", {"weight": 5}))

    def test_ruled(self):
        ok = core.with_defaults("ruled", {"distance": 5})
        core.check_values("ruled", ok)
        with self.assertRaises(core.SurfaceError):
            core.check_values("ruled", dict(ok, angle=90))
        core.check_values("ruled", dict(ok, angle=90, ruled_type="direction"))

    def test_extend(self):
        ok = core.with_defaults("extend", {"distance": 5})
        core.check_values("extend", ok)
        with self.assertRaises(core.SurfaceError):
            core.check_values("extend", dict(ok, distance=-5))  # natural: outwards only
        core.check_values("extend", dict(ok, distance=-5, extend_type="perpendicular"))

    def test_thicken(self):
        ok = core.with_defaults("thicken", {"thickness": -2})  # the other side
        core.check_values("thicken", ok)
        with self.assertRaises(core.SurfaceError):
            core.check_values("thicken", dict(ok, thicken_type="soft"))
        with self.assertRaises(core.SurfaceError):
            core.check_values("thicken", dict(ok, operation="trim"))

    def test_untrim(self):
        core.check_values("untrim", core.with_defaults("untrim"))
        with self.assertRaises(core.SurfaceError):
            core.check_values("untrim", core.with_defaults("untrim", {"distance": -1}))

    def test_stitch_tolerance(self):
        core.check_values("stitch", core.with_defaults("stitch"))
        for bad in (0.0, core.MAX_TOLERANCE * 2):
            with self.assertRaises(core.SurfaceError):
                core.check_values("stitch", core.with_defaults("stitch", {"tolerance": bad}))


class RangeTests(unittest.TestCase):
    def test_extrude_range(self):
        self.assertEqual(core.extrude_range("one_side", 10), (0.0, 10.0))
        self.assertEqual(core.extrude_range("one_side", -4), (-4.0, 0.0))
        self.assertEqual(core.extrude_range("two_sides", 10, 3), (-3.0, 10.0))
        self.assertEqual(core.extrude_range("symmetric", 10), (-10.0, 10.0))
        self.assertEqual(core.extrude_range("symmetric", 10, measurement="whole"), (-5.0, 5.0))

    def test_revolve_range(self):
        self.assertEqual(core.revolve_range("full", "one_side", 10), (0.0, 360.0))
        self.assertEqual(core.revolve_range("angle", "one_side", 90), (0.0, 90.0))
        self.assertEqual(core.revolve_range("angle", "one_side", -90), (-90.0, 90.0))
        self.assertEqual(core.revolve_range("angle", "symmetric", 45), (-45.0, 90.0))
        self.assertEqual(core.revolve_range("angle", "symmetric", 180), (0.0, 360.0))
        self.assertEqual(core.revolve_range("angle", "two_sides", 90, 30), (-30.0, 120.0))

    def test_thicken_offsets(self):
        self.assertEqual(core.thicken_offsets("one_side", 2), (0.0, 2.0))
        self.assertEqual(core.thicken_offsets("one_side", -2), (0.0, -2.0))
        self.assertEqual(core.thicken_offsets("symmetric", 2), (-1.0, 2.0))


class RulingTests(unittest.TestCase):
    N = (0.0, 0.0, 1.0)
    AWAY = (1.0, 0.0, 0.0)

    def test_tangent_carries_the_face_on(self):
        self.assertTrue(close(core.ruling_direction("tangent", self.N, self.AWAY, 0), self.AWAY))

    def test_normal_is_square_to_the_face(self):
        self.assertTrue(close(core.ruling_direction("normal", self.N, self.AWAY, 0), self.N))

    def test_angle_turns_towards_the_other(self):
        d = core.ruling_direction("tangent", self.N, self.AWAY, 30)
        self.assertTrue(close(d, (math.cos(math.radians(30)), 0.0, 0.5)))
        d = core.ruling_direction("normal", self.N, self.AWAY, 90)
        self.assertTrue(close(d, self.AWAY))

    def test_direction_needs_a_pick(self):
        with self.assertRaises(core.NeedsPick):
            core.ruling_direction("direction", self.N, self.AWAY, 0)
        d = core.ruling_direction("direction", self.N, self.AWAY, 0, (0.0, 3.0, 0.0))
        self.assertTrue(close(d, (0.0, 1.0, 0.0)))

    def test_bad_type_and_zero_vector(self):
        with self.assertRaises(core.SurfaceError):
            core.ruling_direction("sideways", self.N, self.AWAY, 0)
        with self.assertRaises(core.SurfaceError):
            core.ruling_direction("normal", (0.0, 0.0, 0.0), self.AWAY, 0)


class CellTests(unittest.TestCase):
    def test_choose_cells(self):
        rows = [[0.0, 5.0], [4.0, 0.001], [9.0, 8.0], []]
        self.assertEqual(core.choose_cells(rows, 0.01), ([0, 1], [2, 3]))

    def test_toggle_point(self):
        def owner(p):
            return 0 if p[0] < 10 else 1

        points = core.toggle_point([], 0, (1, 2, 3), owner)
        self.assertEqual(points, [[1.0, 2.0, 3.0]])
        points = core.toggle_point(points, 1, (20, 0, 0), owner)
        self.assertEqual(len(points), 2)
        points = core.toggle_point(points, 0, (5, 5, 5), owner)  # clicked again: dropped
        self.assertEqual(points, [[20.0, 0.0, 0.0]])


class PartTwoTests(unittest.TestCase):
    """Surface and Loft part 2 (sf/surface-2): From Object / All, Revolve To, Sweep rail and
    taper, Loft guides and end conditions."""

    def test_new_choices_follow_fusion(self):
        self.assertEqual(core.STARTS, ("profile", "offset", "object"))
        self.assertEqual(core.EXTENTS, ("distance", "to_object", "all"))
        self.assertEqual(core.REVOLVE_TYPES, ("angle", "to", "full"))
        # part 3 (sf/surface-3) added Path + Guide Surface
        self.assertEqual(core.SWEEP_TYPES, ("single", "rail", "surface"))
        self.assertEqual(core.SCALINGS, ("scale", "stretch", "none"))
        self.assertEqual(core.GUIDES, ("rails", "centerline"))
        loft = core.with_defaults("loft")
        self.assertEqual(loft["guide"], "rails")
        self.assertFalse(loft["merge"])  # Keep (see parity/surface.md: OpenCASCADE's volume)
        self.assertEqual((loft["start_condition"], loft["end_condition"]), ("free", "free"))
        self.assertEqual(core.with_defaults("sweep")["scaling"], "scale")
        self.assertFalse(core.with_defaults("extrude")["flip"])

    def test_extrude_all_and_from_object_need_no_distance(self):
        for extent in ("to_object", "all"):
            core.check_values("extrude", core.with_defaults("extrude", {"extent": extent}))
        core.check_values(
            "extrude", core.with_defaults("extrude", {"start": "object", "distance": 5})
        )
        with self.assertRaises(core.SurfaceError):
            core.check_values("extrude", core.with_defaults("extrude", {"start": "sketch"}))
        with self.assertRaises(core.SurfaceError):
            core.check_values("extrude", core.with_defaults("extrude", {"extent": "through"}))
        with self.assertRaises(core.SurfaceError):
            core.check_values(
                "extrude",
                core.with_defaults(
                    "extrude", {"direction": "two_sides", "distance": 5, "taper2": 89.5}
                ),
            )

    def test_revolve_to_needs_no_angle(self):
        core.check_values("revolve", core.with_defaults("revolve", {"type": "to", "angle": 0}))

    def test_sweep_rail_and_taper(self):
        core.check_values("sweep", core.with_defaults("sweep", {"type": "rail"}))
        core.check_values("sweep", core.with_defaults("sweep", {"taper": -20}))
        with self.assertRaises(core.SurfaceError):
            core.check_values("sweep", core.with_defaults("sweep", {"type": "guide"}))
        with self.assertRaises(core.SurfaceError):
            core.check_values("sweep", core.with_defaults("sweep", {"scaling": "grow"}))
        with self.assertRaises(core.SurfaceError):
            core.check_values("sweep", core.with_defaults("sweep", {"taper": 90}))

    def test_loft_end_values(self):
        core.check_values("loft", core.with_defaults("loft", {"start_condition": "tangent"}))
        core.check_values(
            "loft", core.with_defaults("loft", {"end_condition": "free", "end_weight": -1})
        )  # a free end ignores its weight
        for bad in (
            {"start_condition": "direction", "start_weight": 0},
            {"start_condition": "direction", "start_weight": core.MAX_END_WEIGHT + 1},
            {"end_condition": "direction", "end_angle": 95},
            {"end_condition": "smooth"},
            {"guide": "spine"},
        ):
            with self.assertRaises(core.SurfaceError, msg=bad):
                core.check_values("loft", core.with_defaults("loft", bad))

    def test_stop_angle_turns_the_shorter_way(self):
        z = (0.0, 0.0, 1.0)
        self.assertAlmostEqual(core.stop_angle((1, 0, 0), [(0, 1, 0)], z), 90.0)
        self.assertAlmostEqual(core.stop_angle((1, 0, 0), [(0, -1, 0)], z), -90.0)
        # a plane through the axis marks two half-planes: the nearer, the positive way on a tie
        self.assertAlmostEqual(core.stop_angle((1, 0, 0), [(0, 1, 0), (0, -1, 0)], z), 90.0)
        # the profile's own plane: its other half (half a turn)
        self.assertAlmostEqual(core.stop_angle((1, 0, 0), [(1, 0, 0), (-1, 0, 0)], z), 180.0)
        s45 = math.sqrt(0.5)
        self.assertAlmostEqual(core.stop_angle((1, 0, 0), [(s45, -s45, 0)], z), -45.0)
        with self.assertRaises(core.SurfaceError):
            core.stop_angle((1, 0, 0), [(1, 0, 0)], z)

    def test_all_lengths(self):
        self.assertEqual(core.all_lengths("one_side", False, 25, 10), (25.0, 0.0))
        self.assertEqual(core.all_lengths("one_side", True, 25, 10), (0.0, 10.0))
        self.assertEqual(core.all_lengths("two_sides", False, 25, -3), (25.0, 0.0))
        self.assertEqual(core.all_lengths("symmetric", False, 5, 10), (5.0, 10.0))
        with self.assertRaises(core.SurfaceError) as raised:
            core.all_lengths("one_side", False, -1, 10)
        self.assertIn("Flip", str(raised.exception))
        with self.assertRaises(core.SurfaceError):
            core.all_lengths("two_sides", False, 0, 0)

    def test_taper_factor(self):
        self.assertAlmostEqual(
            core.taper_factor(20, 10, 5), 1 + 20 * math.tan(math.radians(10)) / 5
        )
        self.assertAlmostEqual(
            core.taper_factor(20, -10, 5), 1 - 20 * math.tan(math.radians(10)) / 5
        )
        with self.assertRaises(core.SurfaceError):
            core.taper_factor(40, -45, 10)  # shrinks to nothing
        with self.assertRaises(core.SurfaceError):
            core.taper_factor(40, 10, 0)

    def test_lerp_fraction(self):
        self.assertAlmostEqual(core.lerp_fraction(0.2, 0.6, 0.5, False), 0.4)
        # closed: the shorter way round over the start
        self.assertAlmostEqual(core.lerp_fraction(0.9, 0.1, 0.5, True), 0.0)
        self.assertAlmostEqual(core.lerp_fraction(0.1, 0.9, 0.25, True), 0.05)
        self.assertAlmostEqual(core.lerp_fraction(0.2, 0.4, 1.0, True), 0.4)

    def test_similarity_moves_two_points_onto_two(self):
        cases = [
            ((0, 0, 0), (10, 0, 0), (1, 2, 3), (1, 2, 23)),  # turned a quarter, scaled 2
            ((0, 0, 0), (0, 5, 0), (3, 3, 3), (3, 8, 3)),  # moved only
            ((1, 1, 1), (2, 1, 1), (0, 0, 0), (-3, 0, 0)),  # turned half, scaled 3
            ((0, 0, 0), (1, 2, 2), (5, 5, 5), (7, 4, 6)),
        ]
        for q1, q2, r1, r2 in cases:
            m = core.similarity(q1, q2, r1, r2)
            self.assertTrue(close(core.apply_matrix(m, q1), r1, 1e-9), (q1, r1))
            self.assertTrue(close(core.apply_matrix(m, q2), r2, 1e-9), (q2, r2))
            # an even scale: lengths grow by one factor in every direction
            a = core.apply_matrix(m, (q1[0] + 1, q1[1], q1[2]))
            b = core.apply_matrix(m, (q1[0], q1[1] + 1, q1[2]))
            la = math.dist(a, core.apply_matrix(m, q1))
            lb = math.dist(b, core.apply_matrix(m, q1))
            self.assertAlmostEqual(la, lb, 9)
        for q1, q2, r1, r2 in cases:
            m = core.stretch_similarity(q1, q2, r1, r2)
            self.assertTrue(close(core.apply_matrix(m, q1), r1, 1e-9), (q1, r1))
            self.assertTrue(close(core.apply_matrix(m, q2), r2, 1e-9), (q2, r2))
        # stretched only along the rails' line: a direction square to it keeps its length
        m = core.stretch_similarity((0, 0, 0), (10, 0, 0), (0, 0, 0), (30, 0, 0))
        self.assertTrue(close(core.apply_matrix(m, (0, 4, 0)), (0, 4, 0), 1e-9))
        self.assertTrue(close(core.apply_matrix(m, (5, 0, 2)), (15, 0, 2), 1e-9))
        one = core.similarity((1, 2, 3), (1, 2, 3), (4, 4, 4), (4, 4, 4))
        self.assertTrue(close(core.apply_matrix(one, (0, 0, 0)), (3, 2, 1)))
        with self.assertRaises(core.SurfaceError):
            core.similarity((0, 0, 0), (1, 0, 0), (2, 2, 2), (2, 2, 2))


class PartThreeTests(unittest.TestCase):
    """SURFACE part 3 (sf/surface-3): Offset Type, Patch per edge / Reverse Normal, Untrim
    Manual / Keep Copy, Revolve Project Axis / Partial / To Two Sides, Sweep Guide Surface and
    rail extents, Stitch operations, closed-loft corner matching, old files."""

    def test_offset_type_sharp_by_default_old_files_rounded(self):
        self.assertEqual(core.OFFSET_TYPES, ("sharp", "rounded"))
        self.assertEqual(core.with_defaults("offset")["offset_type"], "sharp")
        # a step saved before the choice existed keeps the shape it had (Rounded)
        self.assertEqual(core.with_saved("offset", {"distance": 2})["offset_type"], "rounded")
        self.assertEqual(
            core.with_saved("offset", {"offset_type": "sharp"})["offset_type"], "sharp"
        )
        with self.assertRaises(core.SurfaceError):
            core.check_values(
                "offset", core.with_defaults("offset", {"distance": 2, "offset_type": "round"})
            )

    def test_legacy_revolve_and_sweep(self):
        self.assertTrue(core.with_defaults("revolve")["project_axis"])
        self.assertFalse(core.with_saved("revolve", {})["project_axis"])
        self.assertEqual(core.with_defaults("sweep")["rail_extent"], "perpendicular")
        self.assertEqual(core.with_saved("sweep", {})["rail_extent"], "full")
        self.assertEqual(core.with_saved("patch", {})["weight"], 0.5)

    def test_patch_defaults_and_per_edge(self):
        patch = core.with_defaults("patch")
        self.assertEqual(patch["weight"], 0.5)  # API PatchFeatureInput.groupWeight
        self.assertTrue(patch["group_edges"])
        self.assertFalse(patch["reverse"])
        core.check_values(
            "patch", core.with_defaults("patch", {"edge_continuity": ["connected", "tangent"]})
        )
        with self.assertRaises(core.SurfaceError):
            core.check_values("patch", core.with_defaults("patch", {"edge_continuity": ["G9"]}))

    def test_untrim_manual_and_keep_copy(self):
        self.assertIn("manual", core.LOOP_TYPES)
        self.assertEqual(core.LOOP_LABELS["manual"], "Manual")
        self.assertFalse(core.with_defaults("untrim")["keep_copy"])
        core.check_values("untrim", core.with_defaults("untrim", {"loop_type": "manual"}))

    def test_revolve_partial_and_to_two_sides(self):
        self.assertEqual(core.REVOLVE_LABELS["angle"], "Partial")
        with self.assertRaises(core.SurfaceError):
            core.check_values(
                "revolve", core.with_defaults("revolve", {"type": "to", "direction": "symmetric"})
            )
        core.check_values(
            "revolve", core.with_defaults("revolve", {"type": "to", "direction": "two_sides"})
        )
        # +x to +y the right-handed way (90), to -y the other way (90): a half turn in all
        self.assertEqual(
            core.two_sided_to((1, 0, 0), [(0, 1, 0)], [(0, -1, 0)], (0, 0, 1)), (-90.0, 180.0)
        )
        # the second side to the XZ plane's halves: +x is where it starts, -x half a turn
        start, sweep = core.two_sided_to((1, 0, 0), [(0, 1, 0)], [(1, 0, 0), (-1, 0, 0)], (0, 0, 1))
        self.assertAlmostEqual(start, -180.0)
        self.assertAlmostEqual(sweep, 270.0)
        self.assertAlmostEqual(core.turn_angle((1, 0, 0), [(0, 1, 0)], (0, 0, 1), -1.0), 270.0)
        with self.assertRaises(core.SurfaceError):  # the two sides overlap
            core.two_sided_to((1, 0, 0), [(0, -1, 0)], [(0, 1, 0)], (0, 0, 1))

    def test_sweep_guide_surface_and_rail_extent(self):
        core.check_values("sweep", core.with_defaults("sweep", {"type": "surface"}))
        self.assertEqual(core.SWEEP_LABELS["surface"], "Path + Guide Surface")
        with self.assertRaises(core.SurfaceError):
            core.check_values("sweep", core.with_defaults("sweep", {"rail_extent": "half"}))
        with self.assertRaises(core.SurfaceError):
            core.check_values("sweep", core.with_defaults("sweep", {"rail_distance": 1.5}))

    def test_extend_edge_alignment(self):
        self.assertEqual(core.ALIGNMENTS, ("free", "align"))
        core.check_values(
            "extend", core.with_defaults("extend", {"distance": 5, "alignment": "align"})
        )
        with self.assertRaises(core.SurfaceError):
            core.check_values(
                "extend", core.with_defaults("extend", {"distance": 5, "alignment": "aligned"})
            )

    def test_stitch_operations(self):
        self.assertEqual(core.operations("stitch"), ["new_body", "join", "cut", "intersect"])
        self.assertEqual(core.with_defaults("stitch")["operation"], "new_body")

    def test_corner_shift(self):
        square = [(0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0)]
        centre = (5, 5, 0)
        # the same square drawn from the opposite corner: start two corners on
        drawn = [(10, 10, 5), (0, 10, 5), (0, 0, 5), (10, 0, 5)]
        self.assertEqual(core.corner_shift(square, drawn, centre, (5, 5, 5)), (2, False))
        # drawn the other way round from (0, 0): reversed, no shift
        back = [(0, 0, 5), (0, 10, 5), (10, 10, 5), (10, 0, 5)]
        self.assertEqual(core.corner_shift(square, back, centre, (5, 5, 5)), (0, True))
        # different counts: left alone
        self.assertEqual(core.corner_shift(square, drawn[:3], centre, centre), (0, False))


class IsoCurveTests(unittest.TestCase):
    """Sketch > Project / Include > Isoparametric Curve: where the curves go (surface_iso)."""

    def test_distributed_spreads_evenly_off_the_edges(self):
        self.assertEqual(core.iso_fractions(1), [0.5])
        self.assertEqual(core.iso_fractions(3), [0.25, 0.5, 0.75])
        for bad in (0, -1, core.MAX_ISO_COUNT + 1):
            with self.assertRaises(core.SurfaceError):
                core.iso_fractions(bad)

    def test_single_distance_to_fraction_and_back(self):
        lengths = [0.0, 10.0, 30.0, 40.0]  # three uneven steps of the parameter
        self.assertAlmostEqual(core.fraction_at_length(lengths, 0.0), 0.0)
        self.assertAlmostEqual(core.fraction_at_length(lengths, 10.0), 1.0 / 3.0)
        self.assertAlmostEqual(core.fraction_at_length(lengths, 20.0), 0.5)
        self.assertAlmostEqual(core.fraction_at_length(lengths, 40.0), 1.0)
        for d in (0.0, 5.0, 20.0, 33.0, 40.0):
            f = core.fraction_at_length(lengths, d)
            self.assertAlmostEqual(core.length_at_fraction(lengths, f), d)
        with self.assertRaises(core.SurfaceError):  # past the face
            core.fraction_at_length(lengths, 41.0)
        with self.assertRaises(core.SurfaceError):
            core.fraction_at_length([0.0, 0.0], 0.0)

    def test_clamp(self):
        self.assertEqual(core.clamp_fraction(-0.2), 0.0)
        self.assertEqual(core.clamp_fraction(1.7), 1.0)


class WordTests(unittest.TestCase):
    def test_count_label(self):
        self.assertEqual(core.count_label(0, "edge"), "")
        self.assertEqual(core.count_label(1, "edge"), "1 edge")
        self.assertEqual(core.count_label(3, "body", "bodies"), "3 bodies")

    def test_picked_text(self):
        self.assertEqual(core.picked_text(3, {"edge": 3}), "3 edges")
        self.assertEqual(core.picked_text(3, {"body": 2, "plane": 1}), "2 bodies + 1 plane")
        self.assertEqual(core.picked_text(0, {}), "")

    def test_cell_name(self):
        self.assertEqual(core.cell_name(0, 274.889, True), "Cell 1 (274.9 mm³)")
        self.assertEqual(core.cell_name(1, 40, False), "Cell 2 (40.0 mm²)")


if __name__ == "__main__":
    unittest.main()
