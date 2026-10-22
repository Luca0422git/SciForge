# SPDX-License-Identifier: LGPL-2.1-or-later
"""A value past what fits stops at the largest value that works (sciforge/value_limits.py,
Luca 2026-10-21): the search, the rounding toward the safe side, the check that the rounded
value really builds, and the cache that keeps drags from running a search on every step.
Runs without FreeCAD."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sciforge import value_limits as vl  # noqa: E402


class Counter:
    """works(value): True up to `edge` (a fillet that fits up to 3.4789 mm), counting builds."""

    def __init__(self, edge, lower=None, bad=()):
        self.edge = edge
        self.lower = lower
        self.bad = set(bad)  # values that fail although under the edge (a jumpy kernel)
        self.calls = []

    def __call__(self, value):
        self.calls.append(value)
        if round(value, 6) in self.bad:
            return False
        if self.lower is not None and value < self.lower:
            return False
        return value <= self.edge


class Tidy(unittest.TestCase):
    def test_rounds_toward_the_safe_side(self):
        self.assertEqual(vl.tidy(3.4789, 0.01, 0.0), 3.47)
        self.assertEqual(vl.tidy(-3.4789, 0.01, 0.0), -3.47)
        self.assertEqual(vl.tidy(3.4711, 0.01, 9.0), 3.48)
        self.assertEqual(vl.tidy(12.38, 0.1, 0.0), 12.3)
        self.assertEqual(vl.tidy(-12.38, 0.1, 0.0), -12.3)

    def test_a_tidy_value_stays(self):
        # 3.47 / 0.01 is 346.999... in floating point: it must not drop to 3.46
        self.assertEqual(vl.tidy(3.47, 0.01, 0.0), 3.47)
        self.assertEqual(vl.tidy(0.3, 0.1, 0.0), 0.3)
        self.assertEqual(vl.tidy(-0.3, 0.1, 0.0), -0.3)

    def test_steps(self):
        self.assertEqual(vl.step_for("deg"), 0.1)
        self.assertAlmostEqual(vl.step_for("mm"), 0.01)  # FreeCAD's default 2 decimals


class Notes(unittest.TestCase):
    def test_words(self):
        self.assertEqual(vl.note_reached(3.47, "hi"), "Largest that fits here: 3.47 mm")
        self.assertEqual(vl.note_reached(-3.2, "lo"), "Smallest that fits here: -3.20 mm")
        self.assertEqual(vl.note_reached(12.3, "hi", "deg"), "Largest that fits here: 12.3°")
        self.assertEqual(vl.note_typed(5, 3.47), "5 mm does not fit: limited to 3.47 mm")
        self.assertEqual(vl.note_typed(40, 12.3, "deg"), "40° does not fit: limited to 12.3°")

    def test_limit_errors(self):
        for text in (
            "Radius 50 mm is too big here: the round does not fit on the faces next to it.",
            "A 12 mm inside wall is too thick for this part: the walls run into each other.",
            "The faces cannot be tilted this far: try a smaller angle, or draft fewer faces.",
            "Pushing by -40 mm would remove the whole body. Use a smaller distance.",
            "At 60° the bevel never reaches the face on the other side of the edge.",
        ):
            self.assertTrue(vl.is_limit_error(text), text)
        for text in ("Select the edges or faces to fillet.", "Pick the faces to draft.", ""):
            self.assertFalse(vl.is_limit_error(text), text)


class Search(unittest.TestCase):
    def test_finds_the_tidy_limit(self):
        works = Counter(3.4789)
        limit, exact = vl.search(works, 1.0, 50.0, 0.01)
        self.assertEqual(limit, 3.47)
        self.assertTrue(exact)
        self.assertTrue(works(limit))

    def test_lower_limit(self):
        # a push into the part: -3.2 works, -3.3 removes the whole body
        works = Counter(1e9, lower=-3.2345)
        limit, _exact = vl.search(works, 0.5, -40.0, 0.01)
        self.assertEqual(limit, -3.23)

    def test_negative_angle(self):
        works = Counter(1e9, lower=-17.77)
        limit, _exact = vl.search(works, -0.1, -80.0, 0.1)
        self.assertEqual(limit, -17.7)

    def test_rounded_value_is_built_again(self):
        # 3.47 is on the failing edge (a jumpy kernel): the next tidy value toward safety
        works = Counter(3.4789, bad=[3.47])
        limit, _exact = vl.search(works, 1.0, 50.0, 0.01)
        self.assertEqual(limit, 3.46)
        self.assertIn(3.47, [round(c, 6) for c in works.calls])

    def test_not_a_limit(self):
        # nothing works (the good value itself fails): no limit, the refusal stays
        works = Counter(-1.0)
        self.assertEqual(vl.search(works, 1.0, 50.0, 0.01), (None, False))

    def test_good_known_is_not_built(self):
        works = Counter(3.4789)
        vl.search(works, 1.0, 50.0, 0.01, good_known=True)
        self.assertNotIn(1.0, works.calls)

    def test_exception_counts_as_failure(self):
        def works(value):
            if value > 2.5:
                raise RuntimeError("kernel gave up")
            return True

        self.assertEqual(vl.search(works, 0.5, 9.0, 0.01)[0], 2.5)

    def test_time_budget(self):
        # a slow part: the clock jumps 1 s a build; the search stops after MIN_TRIALS and
        # still returns a value that works (safe side)
        now = [0.0]

        def clock():
            return now[0]

        def works(value):
            now[0] += 1.0
            return value <= 3.4789

        limit, exact = vl.search(works, 0.01, 100.0, 0.01, budget=1.5, clock=clock)
        self.assertFalse(exact)
        self.assertIsNotNone(limit)
        self.assertLessEqual(limit, 3.4789)
        self.assertLessEqual(now[0], vl.MIN_TRIALS + vl.VERIFY_TRIES + 1)


class Cache(unittest.TestCase):
    def test_key_freezes_inputs(self):
        a = vl.make_key("Edge1", ["Edge1", "Edge2"], {"type": "equal", "d2": 1.0})
        b = vl.make_key("Edge1", ["Edge1", "Edge2"], {"d2": 1.0000000000001, "type": "equal"})
        self.assertEqual(a, b)
        self.assertNotEqual(a, vl.make_key("Edge1", ["Edge1"], {"type": "equal", "d2": 1.0}))
        hash(a)

    def test_clamp_both_sides(self):
        cache = vl.LimitCache()
        key = vl.make_key("x")
        cache.store(key, "hi", 3.47, 3.48)
        cache.store(key, "lo", -2.0, -2.01)
        self.assertEqual(cache.clamp(key, 9.0), (3.47, 3.47, "hi"))
        self.assertEqual(cache.clamp(key, -9.0), (-2.0, -2.0, "lo"))
        self.assertEqual(cache.clamp(key, 1.0), (1.0, None, None))
        self.assertEqual(cache.clamp(vl.make_key("other"), 9.0), (9.0, None, None))

    def test_size_bound(self):
        cache = vl.LimitCache(size=3)
        for i in range(5):
            cache.store(vl.make_key(i), "hi", 1.0, 2.0)
        self.assertEqual(len(cache.entries), 3)
        self.assertIsNone(cache.get(vl.make_key(0), "hi"))


class LimiterFlow(unittest.TestCase):
    """What a dialog does while an arrow is dragged far past the limit and back."""

    def test_one_search_for_a_whole_drag(self):
        limiter = vl.Limiter()
        works = Counter(3.4789)
        key = vl.make_key("shape", ("Edge1",), {"kind": "fillet"})
        # first step past the limit: refused by the preview, the limit is searched once
        self.assertEqual(limiter.clamp(key, 4.0), 4.0)
        limit = limiter.find(key, works, 4.0, 1.0, good_known=True)
        self.assertEqual(limit, 3.47)
        builds = len(works.calls)
        # every further drag step reuses it: no build, no search
        for value in (5.0, 8.0, 20.0, 50.0):
            self.assertEqual(limiter.clamp(key, value), 3.47)
            self.assertEqual(limiter.note, "Largest that fits here: 3.47 mm")
        self.assertEqual(len(works.calls), builds)
        self.assertEqual(limiter.searches, 1)
        # back below the limit: the value is used as it is, the note goes
        self.assertEqual(limiter.clamp(key, 2.0), 2.0)
        self.assertEqual(limiter.note, "")

    def test_typed_note(self):
        limiter = vl.Limiter()
        key = vl.make_key("k")
        limiter.cache.store(key, "hi", 3.47, 3.48)
        self.assertEqual(limiter.clamp(key, 5.0, typed=True), 3.47)
        self.assertEqual(limiter.note, "5 mm does not fit: limited to 3.47 mm")

    def test_other_inputs_search_again(self):
        limiter = vl.Limiter()
        one = vl.make_key("shape", ("Edge1",))
        two = vl.make_key("shape", ("Edge1", "Edge5"))
        self.assertEqual(limiter.find(one, Counter(3.4789), 9.0, 1.0), 3.47)
        self.assertEqual(limiter.find(two, Counter(2.2), 9.0, 1.0), 2.2)
        self.assertEqual(limiter.searches, 2)
        self.assertEqual(limiter.clamp(one, 9.0), 3.47)
        self.assertEqual(limiter.clamp(two, 9.0), 2.2)

    def test_no_limit_is_remembered(self):
        limiter = vl.Limiter()
        key = vl.make_key("k")
        works = Counter(-1.0)  # nothing works: not a limit
        self.assertIsNone(limiter.find(key, works, 9.0, 1.0))
        calls = len(works.calls)
        self.assertIsNone(limiter.find(key, works, 12.0, 1.0))
        self.assertEqual(len(works.calls), calls)
        self.assertEqual(limiter.searches, 1)

    def test_lower_side(self):
        limiter = vl.Limiter()
        key = vl.make_key("face")
        limit = limiter.find(key, Counter(1e9, lower=-3.2345), -40.0, 0.0)
        self.assertEqual(limit, -3.23)
        self.assertEqual(limiter.clamp(key, -50.0), -3.23)
        self.assertEqual(limiter.note, "Smallest that fits here: -3.23 mm")
        self.assertEqual(limiter.clamp(key, 10.0), 10.0)  # the other side has no limit


if __name__ == "__main__":
    unittest.main()
