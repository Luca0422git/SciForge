# SPDX-License-Identifier: LGPL-2.1-or-later
"""The Home tab's recent designs (sciforge/home_core.py). Runs without FreeCAD."""

import os
import shutil
import sys
import tempfile
import unittest
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from sciforge import home_core as hc  # noqa: E402
from sciforge import versions  # noqa: E402


class _Stat:
    def __init__(self, mtime=100.0, attributes=0):
        self.st_mtime = mtime
        self.st_file_attributes = attributes


class HomeCore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="sciforge-home-")
        self.project = os.path.join(self.tmp, "Project")
        os.makedirs(os.path.join(self.project, "Robots"))
        self.places = {hc.LOCAL: self.project}

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def design(self, *parts, thumb=b"PNGDATA"):
        path = os.path.join(self.project, *parts)
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("Document.xml", "<Document/>")
            if thumb is not None:
                zf.writestr("thumbnails/Thumbnail.png", thumb)
        return path

    # -- the list
    def test_record_puts_the_newest_first_and_keeps_one_entry_per_design(self):
        state = hc.empty()
        arm = self.design("Arm.FCStd")
        base = self.design("Robots", "Base.FCStd")
        hc.record(state, arm, 10, self.places)
        hc.record(state, base, 20, self.places)
        hc.record(state, arm, 30, self.places)
        names = [e["name"] for e in hc.ordered(state)]
        self.assertEqual(names, ["Arm", "Base"])
        self.assertEqual(len(state["entries"]), 2)
        self.assertEqual(hc.find(state, versions.path_key(arm))["last_opened"], 30.0)

    def test_the_path_inside_the_place_is_kept(self):
        state = hc.empty()
        base = self.design("Robots", "Base.FCStd")
        entry = hc.record(state, base, 1, self.places)
        self.assertEqual((entry["location_id"], entry["rel"]), (hc.LOCAL, "Robots/Base.FCStd"))
        # another computer: the same folder somewhere else
        elsewhere = {hc.LOCAL: os.path.join(self.tmp, "Other", "SciForge")}
        self.assertEqual(
            hc.resolve(entry, elsewhere),
            os.path.join(self.tmp, "Other", "SciForge", "Robots", "Base.FCStd"),
        )
        self.assertEqual(hc.resolve(entry, {}), entry["path"])  # place unknown: last seen

    def test_a_design_outside_every_place(self):
        outside = os.path.join(self.tmp, "Desk.FCStd")
        entry = hc.record(hc.empty(), outside, 1, self.places)
        self.assertEqual((entry["location_id"], entry["rel"]), ("", ""))
        self.assertEqual(hc.resolve(entry, self.places), os.path.abspath(outside))

    def test_seen_at_its_new_place_it_is_the_same_design(self):
        state = hc.empty()
        entry = hc.record(state, self.design("Arm.FCStd"), 1, self.places)
        hc.set_pinned(state, entry["key"], True)
        moved_root = os.path.join(self.tmp, "Moved")
        shutil.copytree(self.project, moved_root)
        hc.record(state, os.path.join(moved_root, "Arm.FCStd"), 2, {hc.LOCAL: moved_root})
        self.assertEqual(len(state["entries"]), 1)
        self.assertTrue(state["entries"][0]["pinned"])

    def test_pinned_first_then_newest(self):
        state = hc.empty()
        for i, name in enumerate(("A", "B", "C")):
            hc.record(state, self.design(name + ".FCStd"), i, self.places)
        hc.set_pinned(state, versions.path_key(os.path.join(self.project, "A.FCStd")))
        self.assertEqual([e["name"] for e in hc.ordered(state)], ["A", "C", "B"])

    def test_cap_drops_the_oldest_never_a_pin(self):
        state = hc.empty()
        first = hc.record(state, os.path.join(self.project, "first.FCStd"), 0, self.places)
        hc.set_pinned(state, first["key"])
        for i in range(hc.CAP + 5):
            hc.record(state, os.path.join(self.project, "d%d.FCStd" % i), i + 1, self.places)
        self.assertEqual(len(state["entries"]), hc.CAP)
        names = {e["name"] for e in state["entries"]}
        self.assertIn("first", names)
        self.assertNotIn("d0", names)
        self.assertIn("d%d" % (hc.CAP + 4), names)

    def test_forget_clear_and_relocate(self):
        state = hc.empty()
        a = hc.record(state, self.design("A.FCStd"), 1, self.places)
        b = hc.record(state, self.design("B.FCStd"), 2, self.places)
        hc.set_pinned(state, a["key"])
        hc.clear(state)
        self.assertEqual([e["name"] for e in state["entries"]], ["A"])
        new = self.design("Robots", "A2.FCStd")
        moved = hc.relocate(state, a["key"], new, self.places)
        self.assertTrue(moved["pinned"])
        self.assertEqual(moved["rel"], "Robots/A2.FCStd")
        hc.forget(state, moved["key"])
        self.assertEqual(state["entries"], [])
        self.assertIsNone(hc.relocate(state, b["key"], new, self.places))

    def test_search(self):
        entry = hc.record(hc.empty(), self.design("Robots", "Gear Box.FCStd"), 1, self.places)
        self.assertTrue(hc.matches(entry, "gear"))
        self.assertTrue(hc.matches(entry, "robots box"))
        self.assertTrue(hc.matches(entry, ""))
        self.assertFalse(hc.matches(entry, "arm"))

    # -- the file
    def test_load_and_dump_round_trip_and_survive_a_broken_file(self):
        state = hc.empty()
        hc.record(state, self.design("Arm.FCStd"), 5, self.places)
        state["merged_mru"] = True
        again = hc.load(hc.dump(state))
        self.assertEqual(again["entries"], state["entries"])
        self.assertTrue(again["merged_mru"])
        self.assertEqual(hc.load("{not json")["entries"], [])
        self.assertEqual(hc.load("[]")["entries"], [])
        odd = hc.load('{"entries": [{"name": "no path"}, 3, {"path": "/x/Y.FCStd"}]}')
        self.assertEqual([e["name"] for e in odd["entries"]], ["Y"])

    # -- FreeCAD's own recent files
    def test_mru_paths(self):
        strings = {"MRU1": "/b.FCStd", "MRU0": "/a.FCStd", "MRU2": "/c.FCStd", "Other": "x"}
        self.assertEqual(hc.mru_paths(strings), ["/a.FCStd", "/b.FCStd", "/c.FCStd"])
        self.assertEqual(hc.mru_paths(strings, count=2), ["/a.FCStd", "/b.FCStd"])

    def test_merge_mru_once_in_its_order_older_than_now(self):
        state = hc.empty()
        now = hc.record(state, self.design("Now.FCStd"), 1000, self.places)
        paths = [self.design("A.FCStd"), self.design("B.FCStd"), "/x/notes.txt", now["path"]]
        self.assertTrue(hc.merge_mru(state, paths, 1000, self.places))
        self.assertEqual([e["name"] for e in hc.ordered(state)], ["Now", "A", "B"])
        self.assertEqual(hc.find(state, now["key"])["last_opened"], 1000.0)  # kept
        self.assertFalse(hc.merge_mru(state, [self.design("C.FCStd")], 2000, self.places))
        self.assertEqual(len(state["entries"]), 3)

    def test_sciforge_s_own_copies_are_not_remembered(self):
        user = os.path.join(self.tmp, "user", "SciForge")
        self.assertTrue(hc.remembered(os.path.join(self.project, "A.FCStd"), [user]))
        self.assertFalse(hc.remembered(os.path.join(user, "recovery", "A.FCStd"), [user]))
        self.assertFalse(
            hc.remembered(os.path.join(self.project, "A.versions", "v1.FCStd"), [user])
        )
        self.assertFalse(hc.remembered(os.path.join(self.project, "A.step"), [user]))
        self.assertFalse(hc.remembered("", [user]))

    # -- files and pictures
    def test_online_only_detection(self):
        self.assertFalse(hc.is_online_only(0))
        self.assertFalse(hc.is_online_only(0x20))  # archive
        self.assertTrue(hc.is_online_only(hc.FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS | 0x20))
        self.assertTrue(hc.is_online_only(hc.FILE_ATTRIBUTE_OFFLINE))
        self.assertTrue(hc.is_online_only(hc.FILE_ATTRIBUTE_RECALL_ON_OPEN))
        self.assertEqual(hc.file_status("x", stat=lambda p: _Stat(5, 0x400000)), (hc.ONLINE, 5))
        self.assertEqual(hc.file_status(os.path.join(self.tmp, "gone.FCStd"))[0], hc.MISSING)

    def test_thumbnail_cached_once_per_save_never_read_online_only(self):
        arm = self.design("Arm.FCStd", thumb=b"FIRST")
        cache = os.path.join(self.tmp, "thumbs")
        key = versions.path_key(arm)
        status, mtime, data = hc.load_thumbnail(arm, key, cache)
        self.assertEqual((status, data), (hc.OK, b"FIRST"))
        self.assertEqual(len(os.listdir(cache)), 1)
        self.design("Arm.FCStd", thumb=b"SECOND")  # the cached picture is used for the same
        os.utime(arm, (mtime, mtime))  # save ...
        self.assertEqual(hc.load_thumbnail(arm, key, cache)[2], b"FIRST")
        os.utime(arm, (mtime + 60, mtime + 60))  # ... a new save brings the new one
        self.assertEqual(hc.load_thumbnail(arm, key, cache)[2], b"SECOND")
        self.assertEqual(len(os.listdir(cache)), 1)  # the old picture is gone
        online = hc.load_thumbnail(arm, key, cache, stat=lambda p: _Stat(1, 0x400000))
        self.assertEqual(online, (hc.ONLINE, 1, None))
        self.assertEqual(hc.load_thumbnail(arm + "x", key, cache)[0], hc.MISSING)
        bare = self.design("Bare.FCStd", thumb=None)
        self.assertEqual(hc.load_thumbnail(bare, "k", cache)[2], None)

    def test_version_counts_one_git_call_kept_a_few_seconds(self):
        from unittest import mock

        arm = self.design("Robots", "Arm.FCStd")
        calls = []
        clock = {"now": 100.0}

        def repo_counts(root):
            calls.append(root)
            return {"Project/Robots/Arm.FCStd": 3}  # the repository holds the folder

        counter = hc.VersionCounter(keep_seconds=5, clock=lambda: clock["now"])
        with mock.patch.object(versions, "repo_root", return_value=self.tmp), mock.patch.object(
            versions, "repo_counts", side_effect=repo_counts
        ):
            self.assertEqual(counter.count(arm, self.project, True), 3)
            self.assertEqual(counter.count(arm, self.project, True), 3)
            self.assertEqual(len(calls), 1)  # one git call for the tiles of one listing
            clock["now"] += 10
            counter.count(arm, self.project, True)
            self.assertEqual(len(calls), 2)  # later: asked again (a save since)
            outside = os.path.join(self.tmp, "Desk.FCStd")
            self.assertEqual(counter.count(outside, self.project, True), 0)
            self.assertEqual(len(calls), 2)  # (not in the project folder: no git call)
        # without git: the plain store's copies (<Design>.versions/)
        store = versions.PlainStore(arm)
        store.record("first")
        self.assertEqual(hc.VersionCounter().count(arm, self.project, False), 1)

    def test_words(self):
        self.assertEqual(hc.age_text(1000, 1030), "just now")
        self.assertEqual(hc.age_text(1000, 1000 + 5 * 60), "5 min ago")
        self.assertEqual(hc.age_text(1000, 1000 + 2 * 3600 + 5), "2 h ago")
        self.assertEqual(hc.age_text(1000, 1000 + 86400 + 5), "yesterday")
        self.assertEqual(hc.age_text(1000, 1000 + 3 * 86400), "3 days ago")
        self.assertRegex(hc.age_text(1000, 1000 + 30 * 86400), r"^\d{4}-\d\d-\d\d$")
        self.assertEqual(hc.age_text(0), "")
        self.assertEqual(
            hc.subtitle("This computer", hc.OK, 1000, 3, now=1000 + 7200),
            "This computer, edited 2 h ago, v3",
        )
        self.assertEqual(hc.subtitle("This computer", hc.MISSING, None), "Not found")
        self.assertEqual(hc.subtitle("Dropbox", hc.ONLINE, 5), "Dropbox, online only")


if __name__ == "__main__":
    unittest.main()
