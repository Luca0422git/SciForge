# SPDX-License-Identifier: LGPL-2.1-or-later
"""The speed benchmarks' regression guard (SciForgeTests/gui/perf_guard.py): a measurement
more than twice as slow as the stored baseline is listed; strict mode fails on it. Runs
without FreeCAD."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from SciForgeTests.gui import perf_guard  # noqa: E402


def results(**times):
    return [{"label": k, "change": v} for k, v in times.items()]


class Guard(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def baseline(self, data):
        path = os.path.join(self.tmp.name, "base.json")
        with open(path, "w") as handle:
            json.dump(data, handle)
        return path

    def test_times_of_report_and_map(self):
        report = {"results": results(a=0.1, b=0.2) + [{"label": "c", "error": "boom"}]}
        self.assertEqual(perf_guard.times_of(report), {"a": 0.1, "b": 0.2})
        self.assertEqual(perf_guard.times_of({"a": 1, "flag": True, "x": "y"}), {"a": 1.0})
        self.assertEqual(perf_guard.times_of(None), {})

    def test_slower_listed(self):
        path = self.baseline({"results": results(a=0.100, b=0.100, c=0.100)})
        guard = perf_guard.compare(results(a=0.150, b=0.250, d=1.0), path, environ={})
        self.assertEqual(guard["compared"], 2)
        self.assertEqual([r["label"] for r in guard["slower"]], ["b"])
        self.assertAlmostEqual(guard["slower"][0]["ratio"], 2.5)
        self.assertEqual(guard["missing"], ["c"])
        self.assertTrue(perf_guard.passed(guard))  # a warning only
        self.assertIn("WARNING", perf_guard.markdown(guard)[0])

    def test_noise_floor(self):
        path = self.baseline({"tiny": 0.001})
        guard = perf_guard.compare(results(tiny=0.004), path, environ={})
        self.assertEqual(guard["slower"], [])  # 4x, but 3 ms is timer noise

    def test_strict_fails(self):
        path = self.baseline({"a": 0.1})
        guard = perf_guard.compare(results(a=0.5), path, environ={"SCIFORGE_PERF_STRICT": "1"})
        self.assertFalse(perf_guard.passed(guard))
        self.assertIn("FAIL", perf_guard.markdown(guard)[0])

    def test_faster_is_fine(self):
        path = self.baseline({"a": 0.5})
        guard = perf_guard.compare(results(a=0.1), path, environ={"SCIFORGE_PERF_STRICT": "1"})
        self.assertTrue(perf_guard.passed(guard))
        self.assertIn("none more than", perf_guard.markdown(guard)[0])

    def test_no_baseline(self):
        guard = perf_guard.compare(results(a=0.1), None, environ={})
        self.assertEqual(guard["compared"], 0)
        self.assertTrue(perf_guard.passed(guard))
        self.assertIn("no baseline", perf_guard.markdown(guard)[0])
        broken = os.path.join(self.tmp.name, "broken.json")
        with open(broken, "w") as handle:
            handle.write("{not json")
        self.assertEqual(perf_guard.load(broken), {})

    def test_baseline_path(self):
        self.assertIsNone(perf_guard.baseline_path({"SCIFORGE_PERF_BASELINE": "none"}))
        self.assertEqual(perf_guard.baseline_path({"SCIFORGE_PERF_BASELINE": "/x.json"}), "/x.json")
        default = perf_guard.baseline_path({})
        self.assertEqual(default, perf_guard.DEFAULT if os.path.exists(perf_guard.DEFAULT) else None)

    def test_write_baseline_merges(self):
        path = self.baseline({"old": 0.5, "a": 9.0})
        self.assertIsNone(perf_guard.write_baseline(results(a=0.1), environ={}))
        written = perf_guard.write_baseline(results(a=0.1), environ={"SCIFORGE_PERF_WRITE_BASELINE": path})
        self.assertEqual(written, path)
        self.assertEqual(perf_guard.load(path), {"old": 0.5, "a": 0.1})

    def test_columns(self):
        """The report's baseline / before cells, in milliseconds, empty when not stored."""
        base = self.baseline({"a": 0.0125})
        before = os.path.join(self.tmp.name, "before.json")
        with open(before, "w") as handle:
            json.dump({"a": 0.5, "b": 2.0}, handle)
        cells = perf_guard.columns({"baseline": base}, before)
        self.assertEqual(cells("a"), ("12.5", "500.0"))
        self.assertEqual(cells("b"), ("", "2000.0"))
        self.assertEqual(cells("c"), ("", ""))
        self.assertEqual(perf_guard.columns({"baseline": None}, None)("a"), ("", ""))

    def test_stored_before_readable(self):
        """The times from before the speed work kept in the repository can be read."""
        if os.path.exists(perf_guard.BEFORE):
            stored = perf_guard.load(perf_guard.BEFORE)
            self.assertIn("Idle: busy time per second (timers)", stored)
            self.assertGreater(stored["Edit the plate's first step: Undo (Ctrl+Z)"], 1.0)

    def test_stored_baseline_readable(self):
        """The baseline kept in the repository is one the guard can read."""
        if os.path.exists(perf_guard.DEFAULT):
            stored = perf_guard.load(perf_guard.DEFAULT)
            self.assertTrue(stored)
            self.assertTrue(all(v >= 0 for v in stored.values()))
            # both benchmarks are in it: perf_big_model's and perf_benchmark's
            self.assertIn("Idle: busy time per second (timers)", stored)
            self.assertIn("Fillet, new, 4 vertical edges", stored)


if __name__ == "__main__":
    unittest.main()
