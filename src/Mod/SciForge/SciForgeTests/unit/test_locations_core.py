# SPDX-License-Identifier: LGPL-2.1-or-later
"""Places: clouds, NAS and other folders (sciforge/locations_core.py). Runs without
FreeCAD."""

import json
import os
import shutil
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from sciforge import locations_core as lc  # noqa: E402


class _Stat:
    def __init__(self, mtime, size):
        self.st_mtime = mtime
        self.st_size = size


class Places(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="sciforge-places-")
        self.project = os.path.join(self.tmp, "Project")
        self.dropbox = os.path.join(self.tmp, "Dropbox", "SciForge")
        self.nas = os.path.join(self.tmp, "nas", "share")
        for folder in (self.project, self.dropbox, self.nas):
            os.makedirs(folder)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_add_names_ids_and_round_trip(self):
        places = []
        box = lc.add(places, "dropbox", self.dropbox, project_folder=self.project)
        self.assertEqual((box["id"], box["name"], box["git"]), ("dropbox", "Dropbox", False))
        nas = lc.add(places, "nas", self.nas, "Garage NAS", self.project, git=True)
        self.assertTrue(nas["git"])  # a NAS may keep git versions (the person's choice)
        again = lc.load(lc.dump(places))
        self.assertEqual(again, places)
        listed = lc.all_places(self.project, again)
        self.assertEqual([p["id"] for p in listed], ["local", "dropbox", "nas"])
        self.assertEqual(lc.roots(self.project, again)["local"], self.project)

    def test_a_cloud_place_never_keeps_git(self):
        places = []
        box = lc.add(places, "dropbox", self.dropbox, git=True)
        self.assertFalse(box["git"])
        hand_edited = json.dumps({"places": [dict(box, git=True)]})
        self.assertFalse(lc.load(hand_edited)[0]["git"])

    def test_refusals_say_why(self):
        places = []
        lc.add(places, "dropbox", self.dropbox, project_folder=self.project)
        with self.assertRaisesRegex(lc.PlaceError, "already the place Dropbox"):
            lc.add(places, "folder", self.dropbox)
        with self.assertRaisesRegex(lc.PlaceError, "inside the place Dropbox"):
            lc.add(places, "folder", os.path.join(self.dropbox, "Robots"))
        with self.assertRaisesRegex(lc.PlaceError, "inside"):
            lc.add(places, "folder", os.path.join(self.tmp, "Dropbox"))
        with self.assertRaisesRegex(lc.PlaceError, "This computer"):
            lc.add(places, "folder", self.project, project_folder=self.project)
        with self.assertRaises(lc.PlaceError):
            lc.add(places, "local", self.nas)
        with self.assertRaises(lc.PlaceError):
            lc.add(places, "ftp", self.nas)
        with self.assertRaises(lc.PlaceError):
            lc.add(places, "nas", "")

    def test_two_places_of_one_kind(self):
        places = []
        lc.add(places, "folder", self.nas)
        other = lc.add(places, "folder", os.path.join(self.tmp, "Other"))
        self.assertEqual((other["id"], other["name"]), ("folder-2", "Folder 2"))
        lc.remove(places, "folder")
        self.assertEqual([p["id"] for p in places], ["folder-2"])

    def test_broken_file(self):
        self.assertEqual(lc.load("{oops"), [])
        self.assertEqual(lc.load('{"places": [{"kind": "local", "root": "/x"}, 4]}'), [])

    def test_place_of_and_status(self):
        places = lc.all_places(self.project, [])
        lc.add(places, "dropbox", self.dropbox)
        design = os.path.join(self.dropbox, "Robots", "Arm.FCStd")
        self.assertEqual(lc.place_of(design, places)["id"], "dropbox")
        self.assertEqual(lc.place_of(os.path.join(self.project, "A.FCStd"), places)["id"], "local")
        self.assertIsNone(lc.place_of(os.path.join(self.tmp, "B.FCStd"), places))
        self.assertEqual(lc.status(places[1]), lc.OK)
        self.assertEqual(
            lc.status(dict(places[1], root=os.path.join(self.tmp, "gone"))), lc.OFFLINE
        )

    # -- version stores
    def test_git_allowed(self):
        places = lc.all_places(self.project, [])
        lc.add(places, "dropbox", self.dropbox)
        lc.add(places, "nas", self.nas)
        self.assertTrue(lc.git_allowed(os.path.join(self.project, "A.FCStd"), places))
        self.assertFalse(lc.git_allowed(os.path.join(self.dropbox, "A.FCStd"), places))
        self.assertFalse(lc.git_allowed(os.path.join(self.nas, "A.FCStd"), places))
        places[2]["git"] = True
        self.assertTrue(lc.git_allowed(os.path.join(self.nas, "A.FCStd"), places))
        # the project folder itself inside a folder a cloud app syncs: no git either
        self.assertFalse(lc.git_allowed(os.path.join(self.project, "A.FCStd"), places, [self.tmp]))

    # -- changed on another computer
    def test_changed_since(self):
        path = os.path.join(self.dropbox, "Arm.FCStd")
        with open(path, "wb") as handle:
            handle.write(b"mine")
        before = lc.fingerprint(path)
        self.assertFalse(lc.changed_since(before, path))
        os.utime(path, (before["mtime"] + 30, before["mtime"] + 30))
        self.assertFalse(lc.changed_since(before, path))  # touched, not changed
        with open(path, "wb") as handle:
            handle.write(b"theirs")
        self.assertTrue(lc.changed_since(before, path))
        os.remove(path)
        self.assertFalse(lc.changed_since(before, path))  # gone: saving puts it back
        self.assertFalse(lc.changed_since(None, path))
        self.assertIsNone(lc.fingerprint(path))

    def test_keep_both_name(self):
        path = os.path.join(self.dropbox, "Arm.FCStd")
        first = lc.copy_name(path, "LAPTOP-7")
        self.assertEqual(os.path.basename(first), "Arm (LAPTOP-7).FCStd")
        taken = {first}
        second = lc.copy_name(path, "LAPTOP-7", exists=lambda p: p in taken)
        self.assertEqual(os.path.basename(second), "Arm (LAPTOP-7 2).FCStd")
        self.assertEqual(os.path.basename(lc.copy_name(path, "a/b:c")), "Arm (abc).FCStd")
        self.assertEqual(os.path.basename(lc.copy_name(path, "")), "Arm (this computer).FCStd")

    # -- open on another computer
    def test_notes(self):
        a = lc.note_file(self.dropbox, os.path.join(self.dropbox, "Arm.FCStd"))
        b = lc.note_file(self.dropbox, os.path.join(self.dropbox, "Robots", "Arm.FCStd"))
        self.assertNotEqual(a, b)
        self.assertTrue(a.startswith(os.path.join(self.dropbox, ".sciforge", "locks", "Arm-")))
        now = time.time()
        note = lc.read_note(json.dumps(lc.make_note("LAPTOP", "luca", now - 60)))
        self.assertTrue(lc.note_blocks(note, "DESKTOP", now))
        self.assertFalse(lc.note_blocks(note, "laptop", now))  # this computer's own
        self.assertFalse(lc.note_blocks(note, "DESKTOP", now + 13 * 3600))  # a crash left it
        self.assertFalse(lc.note_blocks(None, "DESKTOP", now))
        self.assertIsNone(lc.read_note("not json"))
        self.assertIsNone(lc.read_note('{"user": "x"}'))

    # -- finding the cloud folders
    def test_dropbox(self):
        env = {"APPDATA": r"C:\Users\L\AppData\Roaming", "LOCALAPPDATA": r"C:\L"}
        files = lc.dropbox_info_files(env, "/home/l", windows=True)
        self.assertEqual(len(files), 2)
        self.assertTrue(files[0].endswith("info.json"))
        self.assertEqual(
            lc.dropbox_info_files({}, "/home/l", windows=False),
            [os.path.join("/home/l", ".dropbox", "info.json")],
        )
        info = json.dumps(
            {
                "personal": {"path": "/a/Dropbox", "host": 1},
                "business": {"path": "/a/Dropbox (Team)"},
            }
        )
        self.assertEqual(
            lc.dropbox_folders([info, "broken", "[]"]),
            [("Dropbox", "/a/Dropbox"), ("Dropbox (work)", "/a/Dropbox (Team)")],
        )

    def test_onedrive(self):
        env = {"OneDrive": "C:/O", "OneDriveConsumer": "C:/O", "OneDriveCommercial": "C:/W"}
        found = lc.onedrive_folders(env, [("OneDrive", "C:/R")])
        self.assertEqual([f for _l, f in found], ["C:/R", "C:/O", "C:/W", "C:/O"])
        home = os.path.join(self.tmp, "home")
        os.makedirs(os.path.join(home, "OneDrive - Uni"))
        linux = lc.onedrive_folders({}, (), home, windows=False)
        self.assertEqual(linux, [("OneDrive", os.path.join(home, "OneDrive - Uni"))])

    def test_google_drive(self):
        prefs = json.dumps(
            {
                "per_account_preferences": [
                    {"value": {"mount_point_path": "H"}},
                    {"value": {"mount_point_path": "G:"}},
                ]
            }
        )
        self.assertEqual(lc.gdrive_mount_points(prefs, "K:"), ["H", "G:\\", "K:\\"])
        self.assertEqual(lc.gdrive_mount_points("not json"), [])
        g = os.path.join(self.tmp, "G")
        os.makedirs(os.path.join(g, "Meine Ablage"))
        os.makedirs(os.path.join(g, ".shortcut-targets-by-id"))
        self.assertEqual(
            lc.gdrive_folders([g, os.path.join(self.tmp, "nothing")]),
            [("Google Drive", os.path.join(g, "Meine Ablage"))],
        )

    def test_detect_offers_each_existing_folder_once(self):
        offers = lc.detect(
            dropbox=[("Dropbox", self.dropbox), ("Dropbox", os.path.join(self.tmp, "gone"))],
            onedrive=[("OneDrive", self.nas), ("OneDrive", self.nas + os.sep)],
        )
        self.assertEqual(
            [(o["kind"], o["path"]) for o in offers],
            [("dropbox", self.dropbox), ("onedrive", self.nas)],
        )

    # -- the copies sync apps make
    def test_dropbox_conflicted_copies(self):
        names = [
            "Arm.FCStd",
            "Arm (Luca's conflicted copy 2026-10-19).FCStd",
            "Arm (Luca's conflicted copy 2026-10-19 (1)).FCStd",
            "Arm (Luca's conflicted copy).FCStd",
            "Notes (x's conflicted copy).txt",
        ]
        found = lc.conflicts_in(names, "dropbox")
        self.assertEqual(set(found), set(names[1:4]))
        self.assertTrue(all(v == "Arm.FCStd" for v in found.values()))
        # Dropbox's words are its own: believed in any place, even with the original gone
        self.assertEqual(lc.conflict_original(names[1], [], "local"), ("Arm.FCStd", "dropbox"))

    def test_onedrive_copies_only_with_a_computer_s_name(self):
        names = [
            "Arm.FCStd",
            "Arm-DESKTOP-AB12C.FCStd",
            "Arm-luca-pc.FCStd",
            "Arm-V2.FCStd",
            "Arm-FINAL.FCStd",
            "Gear-DESKTOP-AB12C.FCStd",
        ]
        found = lc.conflicts_in(names, "onedrive", computer="LUCA-PC")
        self.assertEqual(
            found, {"Arm-DESKTOP-AB12C.FCStd": "Arm.FCStd", "Arm-luca-pc.FCStd": "Arm.FCStd"}
        )
        self.assertEqual(lc.conflicts_in(names, "local"), {})  # not in a OneDrive place

    def test_whose_copy(self):
        self.assertEqual(
            lc.conflict_who("Arm (Luca's conflicted copy 2026-10-19).FCStd", "Arm.FCStd"),
            "Luca's",
        )
        self.assertEqual(lc.conflict_who("Arm-DESKTOP-AB12C.FCStd", "Arm.FCStd"), "DESKTOP-AB12C")
        self.assertEqual(lc.conflict_who("Arm (1).FCStd", "Arm.FCStd"), "")

    def test_sidecar_picture_file(self):
        root = self.dropbox
        a = lc.sidecar_file(root, os.path.join(root, "Arm.FCStd"))
        self.assertTrue(a.startswith(os.path.join(root, ".sciforge", "thumbs", "Arm-")))
        self.assertTrue(a.endswith(".png"))
        self.assertNotEqual(a, lc.sidecar_file(root, os.path.join(root, "Sub", "Arm.FCStd")))

    def test_google_drive_copies_only_beside_the_original(self):
        names = ["Arm.FCStd", "Arm (1).FCStd", "Arm[Conflict].FCStd", "Gear (1).FCStd"]
        self.assertEqual(
            lc.conflicts_in(names, "gdrive"),
            {"Arm (1).FCStd": "Arm.FCStd", "Arm[Conflict].FCStd": "Arm.FCStd"},
        )
        self.assertEqual(lc.conflicts_in(names, "dropbox"), {})


if __name__ == "__main__":
    unittest.main()
