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
        self.assertEqual(vl.note_reached(-3.2, "lo"), "Furthest that fits here: -3.20 mm")
        # review finding L6: a lower limit on a positive value, and a count without a unit
        self.assertEqual(vl.note_reached(2.5, "lo"), "Smallest that fits here: 2.50 mm")
        self.assertEqual(
            vl.note_typed(20.0, 9.99, ""), "20 does not fit: limited to 9.99"
        )
        self.assertEqual(vl.note_reached(9.99, "hi", ""), "Largest that fits here: 9.99")
        limiter = vl.Limiter()
        limiter.cache.store(vl.make_key("coil"), "hi", 9.99, 20.0)
        self.assertEqual(limiter.clamp(vl.make_key("coil"), 20.0, typed=True, unit=""), 9.99)
        self.assertEqual(limiter.note, "20 does not fit: limited to 9.99")
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

    def test_tidy_trials(self):
        # the trials are tidy values when one lies between: the last one that works is the
        # answer, no build of the tidy value under an untidy one (Draft on a part of 180
        # faces: 11 trial drafts of ~0.3 s became 8)
        works = Counter(7.95)
        self.assertEqual(vl.search(works, 3.0, 15.0, 0.1), (7.9, True))
        self.assertLessEqual(len(works.calls), 8)
        self.assertTrue(all(abs(v * 10 - round(v * 10)) < 1e-9 for v in works.calls))

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

    def test_a_limit_holds_its_own_side_of_zero(self):
        # a coil's height may not get under 10.01 going down, yet dragged through zero it is
        # a coil the other way (-20 works): the limit must not hold it at +10.01
        limiter = vl.Limiter()
        key = vl.make_key("coil")

        def works(value):
            return abs(value) >= 10.0 or value == 0.0

        self.assertEqual(limiter.find(key, works, 5.0, 12.0, good_known=True), 10.0)
        self.assertEqual(limiter.clamp(key, 7.0), 10.0)
        self.assertEqual(limiter.clamp(key, -20.0), -20.0)  # the other side: as it is
        # the negative side gets its own limit, kept apart
        self.assertEqual(limiter.find(key, works, -5.0, -12.0, good_known=True), -10.0)
        self.assertEqual(limiter.clamp(key, -7.0), -10.0)
        self.assertEqual(limiter.clamp(key, 7.0), 10.0)

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
        # let go right on the limit: still said
        self.assertEqual(limiter.clamp(key, 3.47), 3.47)
        self.assertEqual(limiter.note, "Largest that fits here: 3.47 mm")
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

    def test_a_search_cut_short_is_not_a_wall(self):
        # review finding L2: on a slow part the time budget stops the bisection after
        # MIN_TRIALS builds (50 -> 10, 4.47, 3.24 all refused): 2.0 (the value that worked) is
        # used for the 50 typed, but values between 2.0 and 3.24 were never tried: they must
        # be built, not held at 2.0 ("2.5 mm does not fit" while it does)
        now = [0.0]

        def clock():
            return now[0]

        works = Counter(3.0)

        def slow(value):
            now[0] += 2.0
            return works(value)

        limiter = vl.Limiter()
        limiter.search_clock = clock
        key = vl.make_key("plate", "61 edges")
        limit = limiter.find(key, slow, 50.0, 2.0, good_known=True)
        self.assertEqual(limit, 2.0)
        self.assertEqual(len(works.calls), vl.MIN_TRIALS)
        refused = min(works.calls)
        self.assertGreater(refused, 3.0)
        # 2.5 and 3.0 were never tried: used as they are (the preview tries them)
        self.assertEqual(limiter.clamp(key, 2.5, typed=True), 2.5)
        self.assertEqual(limiter.note, "")
        self.assertEqual(limiter.clamp(key, 3.0, typed=True), 3.0)
        # past the nearest refused value: held without a build, and said
        self.assertEqual(limiter.clamp(key, 9.0, typed=True), 2.0)
        self.assertEqual(limiter.note, "9 mm does not fit: limited to 2.00 mm")
        # 3.1 (under the nearest refused value) refused by its preview: the gap 2.0 .. 3.1 is
        # searched, a better limit found
        calls = len(works.calls)
        limit = limiter.find(key, slow, 3.1, 2.0, good_known=True)
        self.assertGreater(len(works.calls), calls)
        self.assertGreater(limit, 2.0)
        self.assertLessEqual(limit, 3.0)
        # and 9 is still held, at the better limit
        self.assertEqual(limiter.clamp(key, 9.0), limit)

    def test_far_apart_the_search_stays_near_the_good_value(self):
        # review finding L3: a shell wall of 0.01 works, 50 is refused, 2.9 is the limit and
        # walls of 8 to 30 crashed OpenCASCADE's validity check: the first build is not 25
        works = Counter(2.9)
        self.assertEqual(vl.search(works, 0.01, 50.0, 0.01)[0], 2.9)
        self.assertLess(works.calls[0], 1.0)
        self.assertLess(max(works.calls), 8.0)
        # the same on the negative side (a taper of -0.1 works, -50 does not)
        self.assertAlmostEqual(vl._middle(-0.1, -50.0), -(5.0**0.5))
        # close together, or across zero: the middle
        self.assertEqual(vl._middle(2.0, 4.0), 3.0)
        self.assertEqual(vl._middle(0.0, 40.0), 20.0)
        self.assertEqual(vl._middle(-1.0, 7.0), 3.0)

    def test_an_exact_limit_is_a_wall(self):
        limiter = vl.Limiter()
        key = vl.make_key("k")
        self.assertEqual(limiter.find(key, Counter(3.4789), 50.0, 1.0, good_known=True), 3.47)
        self.assertEqual(limiter.clamp(key, 3.6, typed=True), 3.47)

    def test_lower_side(self):
        limiter = vl.Limiter()
        key = vl.make_key("face")
        limit = limiter.find(key, Counter(1e9, lower=-3.2345), -40.0, 0.0)
        self.assertEqual(limit, -3.23)
        self.assertEqual(limiter.clamp(key, -50.0), -3.23)
        self.assertEqual(limiter.note, "Furthest that fits here: -3.23 mm")
        self.assertEqual(limiter.clamp(key, 10.0), 10.0)  # the other side has no limit


class FakePanel(vl.LimitedValues):
    """A dialog with one value ("wall") that fits up to `edge` for the picks it has."""

    def __init__(self, edge=3.4789):
        self.limit_init()
        self.edge = edge
        self.picks = ("Face6",)
        self.value = 1.0
        self.builds = 0

    def limit_key(self, what):
        return vl.make_key("fake", self.picks, what)

    def limit_works(self, what):
        def works(value):
            self.builds += 1
            if value > self.edge:
                raise ValueError("A %g mm wall is too thick for this part." % value)
            return True

        return works

    def limit_value(self, what):
        return self.value

    def limit_set(self, what, value):
        self.value = value

    def edit(self, value, source):
        """What the dialog does with a new value: hold it, then 'preview' it."""
        self.value = self.limit_edit("wall", value, source)
        if self.value > self.edge:
            reason = "A %g mm wall is too thick for this part." % self.value
            if self.limit_refused(reason):
                return "held"
            return "error: " + self.limit_hint(reason)
        self.limit_good()
        return "ok"


class LimitedValuesFlow(unittest.TestCase):
    def test_drag_past_the_limit_and_back(self):
        p = FakePanel()
        self.assertEqual(p.edit(2.0, "dragged"), "ok")
        self.assertEqual(p.edit(6.0, "dragged"), "held")  # searched once, from 2.0 (known)
        self.assertEqual(p.value, 3.47)
        self.assertEqual(p.limits.note, "Largest that fits here: 3.47 mm")
        builds = p.builds
        for value in (8.0, 12.0, 30.0):  # further drag steps: the cache, nothing built
            self.assertEqual(p.edit(value, "dragged"), "ok")
            self.assertEqual(p.value, 3.47)
        self.assertEqual(p.builds, builds)
        self.assertEqual(p.limits.searches, 1)
        self.assertEqual(p.edit(2.5, "dragged"), "ok")  # back below: used as it is
        self.assertEqual(p.limits.note, "")

    def test_typed(self):
        p = FakePanel()
        p.edit(1.0, "typed")
        self.assertEqual(p.edit(5.0, "typed"), "held")
        self.assertEqual(p.value, 3.47)
        self.assertEqual(p.limits.note, "5 mm does not fit: limited to 3.47 mm")

    def test_formula_is_not_rewritten(self):
        p = FakePanel()
        p.edit(1.0, "typed")
        result = p.edit(5.0, "formula")
        self.assertTrue(result.startswith("error: "), result)
        self.assertIn("Largest that fits here: 3.47 mm.", result)
        self.assertEqual(p.value, 5.0)

    def test_other_picks_other_limit(self):
        p = FakePanel()
        p.edit(1.0, "typed")
        p.edit(9.0, "dragged")
        p.picks, p.edge = ("Face6", "Face2"), 2.0  # a face added: another limit
        self.assertEqual(p.edit(9.0, "dragged"), "held")
        self.assertEqual(p.value, 2.0)
        self.assertEqual(p.limits.searches, 2)

    def test_the_note_goes_when_another_input_changes(self):
        # review finding L5: Draft held at 71.5 ("80° does not fit"), then Flip clicked: the
        # note was still shown although 80 now fits
        p = FakePanel()
        p.edit(1.0, "typed")
        self.assertEqual(p.edit(5.0, "typed"), "held")
        self.assertEqual(p.limits.note, "5 mm does not fit: limited to 3.47 mm")
        p.picks = ("Face6", "flipped")  # an input in the limit's key
        self.assertEqual(p.limits.note, "")
        p.picks = ("Face6",)  # back: the note stays gone (it was about that edit)
        self.assertEqual(p.limits.note, "")
        # a note set by the dialog itself is kept as it is
        p.limits.note = "something"
        p.picks = ("Face1",)
        self.assertEqual(p.limits.note, "something")

    def test_forget(self):
        p = FakePanel()
        p.edit(1.0, "typed")
        p.limit_forget()
        self.assertFalse(p.limit_refused("A 9 mm wall is too thick for this part."))
        self.assertEqual(p.limit_hint("too thick"), "too thick")


class FakeField:
    """A DistanceField as ShowWhenLeft sees it: a value, the text being typed, the box."""

    class Widget:
        def __init__(self):
            self.slots = []
            self.editingFinished = self

        def connect(self, slot):
            self.slots.append(slot)

        def leave(self):
            for slot in self.slots:
                slot()

    def __init__(self, value):
        self._value = value
        self._typed = None
        self.widget = FakeField.Widget()

    def value(self):
        return self._value

    def set_value(self, value):
        self._value = value


class ShowLater(unittest.TestCase):
    def test_the_limit_shows_when_the_box_is_left(self):
        field = FakeField(5.0)
        field._typed = "5"  # being typed
        shower = vl.ShowWhenLeft()
        vl.show_held(shower, "wall", field, 5.0, 3.47)
        self.assertEqual(field.value(), 5.0)  # not rewritten under the cursor
        field._typed = None
        field.widget.leave()
        self.assertEqual(field.value(), 3.47)

    def test_something_else_typed_meanwhile(self):
        field = FakeField(5.0)
        field._typed = "5"
        shower = vl.ShowWhenLeft()
        shower.hold("wall", field, 5.0, 3.47)
        field._typed, field._value = None, 2.0  # the user typed 2 instead
        field.widget.leave()
        self.assertEqual(field.value(), 2.0)

    def test_not_typing_shows_at_once(self):
        field = FakeField(5.0)
        vl.show_held(vl.ShowWhenLeft(), "wall", field, 5.0, 3.47)
        self.assertEqual(field.value(), 3.47)


class FakeTimer:
    """What Background asks of its QTimer, run by hand (tick())."""

    def __init__(self):
        self.interval = 0
        self.running = False

    def setInterval(self, ms):
        self.interval = ms

    def start(self):
        self.running = True

    def stop(self):
        self.running = False


def start_by_hand(job):
    """Background.start() without Qt: the test runs job._tick() itself."""
    job.timer = FakeTimer()
    vl.busy(job)
    job.timer.start()


class SoonPanel(FakePanel):
    """FakePanel whose refused values are looked for in the background (Draft's way)."""

    def __init__(self, edge=3.4789):
        super().__init__(edge)
        self.dragging = False
        self.ended = []

    def edit_soon(self, value, source="dragged"):
        self.value = self.limit_edit("wall", value, source)
        if self.limit_searching():
            return "waits"
        if self.value > self.edge:
            reason = "A %g mm wall is too thick for this part." % self.value
            return self.limit_refused_soon(reason, self.ended.append, lambda: self.dragging)
        self.limit_good()
        return "ok"

    def run(self, ticks=1):
        for _ in range(ticks):
            job = self._limit_job
            if job is None or job.done:
                return
            job._tick()


class BackgroundSearch(unittest.TestCase):
    def setUp(self):
        self._start = vl.Background.start
        vl.Background.start = start_by_hand  # no Qt: the tests tick the job by hand

    def tearDown(self):
        vl.Background.start = self._start

    def test_no_build_while_the_handle_is_dragged(self):
        # review finding DRAFT-2-F1: a trial build froze the dragged handle for its length
        p = SoonPanel()
        self.assertEqual(p.edit_soon(2.0), "ok")
        self.assertEqual(p.edit_soon(20.0), "later")
        p.dragging = True
        builds = p.builds
        p.run(5)
        self.assertEqual(p.builds, builds)
        self.assertEqual(p._limit_job.timer.interval, vl.Background.PAUSE_POLL_MS)
        p.dragging = False
        p.run(40)
        self.assertGreater(p.builds, builds)
        self.assertEqual(p.ended, [3.47])
        self.assertEqual(p.value, 3.47)  # held at the limit at the end

    def test_finish_does_not_wait_for_the_drag(self):
        p = SoonPanel()
        p.edit_soon(2.0)
        p.edit_soon(20.0)
        p.dragging = True
        p.limit_finish()  # OK pressed
        self.assertEqual(p.value, 3.47)
        self.assertFalse(vl.working())

    def test_back_below_what_failed_cuts_the_search_off(self):
        # review finding DRAFT-1-F2: the preview of a value that fits waited for the search
        p = SoonPanel()
        p.edit_soon(2.0)
        p.edit_soon(20.0)
        p.run(3)  # a few trials: 20 fails, something nearer is known to fail
        job = p._limit_job
        fails, works = job.progress["fails"], job.progress["works"]
        self.assertLess(fails, 20.0)
        self.assertEqual(p.edit_soon(fails + 1.0), "waits")  # still past what failed: goes on
        self.assertIs(p._limit_job, job)
        self.assertEqual(p.edit_soon(2.5), "ok")  # fits: no search, no wait
        self.assertTrue(job.done)
        self.assertIsNone(p._limit_job)
        self.assertEqual(p.ended, [])  # a search cut off says nothing
        self.assertEqual(p.value, 2.5)
        self.assertFalse(vl.working())
        # what it learnt is kept: refused again, the next search starts from there
        good, known, bad = p._limit_bracket("wall", p.limit_key("wall"), 20.0, 2.5, True)
        self.assertEqual((good, known, bad), (max(2.5, works), True, fails))

    def test_the_next_search_starts_where_the_cut_off_one_was(self):
        p = SoonPanel()
        p.edit_soon(1.0)
        p.edit_soon(50.0)
        p.run(4)
        fails = p._limit_job.progress["fails"]
        p.edit_soon(1.0)  # back: cut off
        before = p.builds
        self.assertEqual(p.edit_soon(50.0), "later")
        p.run(60)
        self.assertEqual(p.value, 3.47)
        again = p.builds - before
        q = SoonPanel()  # the same without the cut-off search
        q.edit_soon(1.0)
        q.edit_soon(50.0)
        q.run(60)
        self.assertLess(again, q.builds - 1)
        self.assertLess(fails, 50.0)

    def test_the_other_side_of_zero_cuts_off_too(self):
        p = SoonPanel()
        p.edit_soon(2.0)
        p.edit_soon(20.0)
        p.limit_edit("wall", -2.0, "dragged")
        self.assertIsNone(p._limit_job)


if __name__ == "__main__":
    unittest.main()
