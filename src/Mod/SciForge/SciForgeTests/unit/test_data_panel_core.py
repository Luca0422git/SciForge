# SPDX-License-Identifier: LGPL-2.1-or-later
"""The Data Panel's logic (data_panel_core): search, sort, card words, drops, Uses / Used
In. Runs without FreeCAD."""

import os
import shutil
import sys
import tempfile
import time
import unittest
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sciforge import data_panel_core as dp  # noqa: E402
from sciforge import versions  # noqa: E402

DOC = '<?xml version="1.0"?><Document><Objects>%s</Objects></Document>'


def write_design(path, links=()):
    """A minimal design file: Document.xml with an XLink per linked file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    body = "".join('<XLink file="%s" name="Body"/>' % link for link in links)
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("Document.xml", DOC % body)
    return path


class Info:
    def __init__(self, number, when, description="", milestone=False):
        self.number, self.time, self.description, self.milestone = (
            number,
            when,
            description,
            milestone,
        )


class SortTests(unittest.TestCase):
    FOLDERS = [{"name": "robots"}, {"name": "Arms"}]
    DESIGNS = [
        {"name": "base", "modified": "2026-10-20T10:00:00", "size": 300},
        {"name": "Arm", "modified": "2026-10-22T10:00:00", "size": 100},
        {"name": "cart", "modified": "2026-10-21T10:00:00", "size": 300},
    ]

    def names(self, key):
        folders, designs = dp.sort_entries(self.FOLDERS, self.DESIGNS, key)
        return [f["name"] for f in folders] + [d["name"] for d in designs]

    def test_by_name_folders_first(self):
        self.assertEqual(self.names("name"), ["Arms", "robots", "Arm", "base", "cart"])

    def test_last_saved_newest_first(self):
        self.assertEqual(self.names("modified"), ["Arms", "robots", "Arm", "cart", "base"])

    def test_size_biggest_first_then_by_name(self):
        self.assertEqual(self.names("size"), ["Arms", "robots", "base", "cart", "Arm"])

    def test_unknown_sort_is_by_name(self):
        self.assertEqual(dp.known_sort("colour"), "name")
        self.assertEqual(dp.known_sort("size"), "size")
        self.assertEqual(dp.sort_name("modified"), "Last saved")


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="sf-dp-")
        write_design(os.path.join(self.root, "Arm.FCStd"))
        write_design(os.path.join(self.root, "Robots", "Arm Joint.FCStd"))
        write_design(os.path.join(self.root, "Robots", "Wheel.FCStd"))
        os.makedirs(os.path.join(self.root, "Arm parts"))
        write_design(os.path.join(self.root, ".sciforge-trash", "Arm old.FCStd"))
        write_design(os.path.join(self.root, "Arm.versions", "v0001.FCStd"))
        with open(os.path.join(self.root, "Robots", "arm.step"), "w") as handle:
            handle.write("ISO-10303-21;")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_words_any_order_any_case(self):
        self.assertTrue(dp.matches("Arm Joint", "joint arm"))
        self.assertFalse(dp.matches("Arm Joint", "arm wheel"))
        self.assertFalse(dp.matches("Arm", "   "))

    def test_search_looks_in_every_folder_but_the_hidden_ones(self):
        folders, designs, more = dp.search(self.root, "ARM")
        self.assertFalse(more)
        self.assertEqual([(f["name"], f["where"]) for f in folders], [("Arm parts", "")])
        found = sorted((d["name"], d["where"]) for d in designs)
        self.assertEqual(found, [("Arm", ""), ("Arm Joint", "Robots"), ("arm.step", "Robots")])

    def test_search_stops_at_its_limit(self):
        folders, designs, more = dp.search(self.root, "arm", limit=2)
        self.assertTrue(more)
        self.assertLessEqual(len(folders) + len(designs), 2)

    def test_empty_query_finds_nothing(self):
        self.assertEqual(dp.search(self.root, ""), ([], [], False))
        self.assertEqual(dp.search(os.path.join(self.root, "nowhere"), "arm"), ([], [], False))


class CardTests(unittest.TestCase):
    NOW = time.mktime(time.strptime("2026-10-23T12:00:00", "%Y-%m-%dT%H:%M:%S"))

    def test_card_text_is_what_the_list_always_said(self):
        self.assertEqual(dp.card_text("Arm", 2), "Arm  v2")
        self.assertEqual(dp.card_text("robot.step"), "robot.step")
        self.assertEqual(dp.card_text("Bracket", 1, True), "Bracket  v1  (conflict)")

    def test_badge(self):
        self.assertEqual(dp.badge(3), "V3")
        self.assertEqual(dp.badge(0), "")

    def test_age(self):
        self.assertEqual(dp.age("2026-10-23T11:59:30", self.NOW), "just now")
        self.assertEqual(dp.age("2026-10-23T11:00:00", self.NOW), "1 h ago")
        self.assertEqual(dp.age("2026-10-22T10:00:00", self.NOW), "yesterday")
        self.assertEqual(dp.age("2026-10-01T10:00:00", self.NOW), "2026-10-01")
        self.assertEqual(dp.age("not a date", self.NOW), "")

    def test_subtitle(self):
        design = {"modified": "2026-10-23T11:55:00", "size": 2048}
        self.assertEqual(dp.subtitle(design, self.NOW), "5 min ago · 2.0 KB")
        self.assertEqual(
            dp.subtitle(design, self.NOW, where="Robots"),
            "in Robots · 5 min ago · 2.0 KB",
        )
        self.assertTrue(dp.subtitle(design, self.NOW, where="").startswith("in the top folder"))
        cad = dict(design, cad=True)
        self.assertIn("STEP / IGES file", dp.subtitle(cad, self.NOW))

    def test_status(self):
        self.assertEqual(dp.status_text([1], [1, 2]), "1 folder, 2 designs")
        self.assertEqual(dp.status_text([], [1], "arm"), '1 found for "arm"')
        self.assertEqual(dp.status_text([], [], "zz "), 'Nothing called "zz" in this place.')

    def test_version_row(self):
        row = dp.version_row(Info(3, "2026-10-23T10:00:00", "longer arm", True), self.NOW)
        self.assertEqual(row, "V3  2 h ago  longer arm  ⚑")


class DropTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="sf-dp-")
        self.arm = write_design(os.path.join(self.root, "Arm.FCStd"))
        self.robots = os.path.join(self.root, "Robots")
        os.makedirs(self.robots)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_paths_survive_the_drag(self):
        text = dp.encode_paths([self.arm, ""])
        self.assertEqual(dp.decode_paths(text), [os.path.abspath(self.arm)])
        self.assertEqual(dp.decode_paths("\n  \n"), [])

    def test_a_folder_takes_designs_from_elsewhere_only(self):
        inside = os.path.join(self.robots, "Wheel.FCStd")
        self.assertEqual(dp.move_target([self.arm], self.robots), [self.arm])
        self.assertEqual(dp.move_target([inside], self.robots), [])
        self.assertEqual(dp.move_target([os.path.join(self.root, "notes.txt")], self.robots), [])

    def test_only_designs_go_into_a_design(self):
        self.assertTrue(dp.insertable(self.arm))
        self.assertFalse(dp.insertable(os.path.join(self.root, "gone.FCStd")))
        self.assertFalse(dp.insertable(os.path.join(self.root, "robot.step")))

    def test_upload(self):
        self.assertEqual(dp.upload_kind("a/B.FCStd"), "design")
        self.assertEqual(dp.upload_kind("a/robot.STP"), "cad")
        self.assertIsNone(dp.upload_kind("a/notes.txt"))
        self.assertEqual(
            dp.upload_target(self.root, "/x/Arm.FCStd"), os.path.join(self.root, "Arm 2.FCStd")
        )
        self.assertEqual(
            dp.upload_target(self.root, "/x/Base.FCStd"), os.path.join(self.root, "Base.FCStd")
        )


class ReferenceTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="sf-dp-")
        self.wheel = write_design(os.path.join(self.root, "Parts", "Wheel.FCStd"))
        self.cart = write_design(
            os.path.join(self.root, "Cart.FCStd"),
            ["Parts/Wheel.FCStd", "Parts/Wheel.FCStd", "Gone.FCStd"],
        )
        self.robot = write_design(
            os.path.join(self.root, "Robots", "Robot.FCStd"), ["../Parts/Wheel.FCStd"]
        )

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_uses_each_once_with_missing_ones_said(self):
        found = dp.uses(self.cart, versions.read_design_xml(self.cart))
        self.assertEqual([(n, there) for n, _p, there in found], [("Wheel", True), ("Gone", False)])

    def test_used_in_finds_every_design_of_the_place_that_inserts_it(self):
        self.assertEqual([n for n, _p in dp.used_in(self.wheel, self.root)], ["Cart", "Robot"])
        self.assertEqual(dp.used_in(self.cart, self.root), [])


if __name__ == "__main__":
    unittest.main()
