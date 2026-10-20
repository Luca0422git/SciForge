# SPDX-License-Identifier: LGPL-2.1-or-later
"""The slim lines at the top of Home (sciforge/notices_core.py) and the files the welcome line
opens (the module's own copies of the cheat sheet and the Pi 5 example). Runs without FreeCAD."""

import os
import sys
import unittest
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(ROOT)))
sys.path.insert(0, ROOT)

from sciforge import __version__  # noqa: E402
from sciforge import notices_core as nc  # noqa: E402


class FakeFlag:
    """The WelcomeShown preference."""

    def __init__(self, value=False):
        self.value, self.reads, self.writes = value, 0, []

    def get(self):
        self.reads += 1
        return self.value

    def set(self, value):
        self.writes.append(value)
        self.value = value


class WelcomeLine(unittest.TestCase):
    def welcome(self, flag):
        return nc.Welcome(flag.get, flag.set)

    def test_the_first_start_shows_it_and_sets_the_flag_at_once(self):
        flag = FakeFlag(False)
        welcome = self.welcome(flag)
        self.assertTrue(welcome.visible())
        self.assertEqual(flag.writes, [True])  # (not waiting for the x)

    def test_it_stays_up_for_the_whole_first_session(self):
        flag = FakeFlag(False)
        welcome = self.welcome(flag)
        self.assertTrue(welcome.visible())
        self.assertTrue(welcome.visible())  # Home closed and opened again: still there
        self.assertEqual(flag.reads, 1)

    def test_the_next_start_does_not_show_it(self):
        flag = FakeFlag(False)
        self.assertTrue(self.welcome(flag).visible())
        self.assertFalse(self.welcome(flag).visible())  # a new session, the flag is kept

    def test_the_x_hides_it_for_good(self):
        flag = FakeFlag(False)
        welcome = self.welcome(flag)
        self.assertTrue(welcome.visible())
        welcome.close()
        self.assertFalse(welcome.visible())
        self.assertTrue(flag.value)
        self.assertFalse(self.welcome(flag).visible())

    def test_the_x_before_anything_was_shown_still_counts(self):
        flag = FakeFlag(False)
        welcome = self.welcome(flag)
        welcome.close()
        self.assertFalse(welcome.visible())
        self.assertTrue(flag.value)

    def test_a_flag_already_set_never_shows_it(self):
        self.assertFalse(self.welcome(FakeFlag(True)).visible())

    def test_a_preference_that_cannot_be_read_shows_nothing_and_never_raises(self):
        def broken():
            raise RuntimeError("no preferences")

        welcome = nc.Welcome(broken, lambda v: None)
        self.assertFalse(welcome.visible())

    def test_a_preference_that_cannot_be_written_still_shows_the_line_once(self):
        def broken(value):
            raise RuntimeError("read-only")

        welcome = nc.Welcome(lambda: False, broken)
        self.assertTrue(welcome.visible())
        welcome.close()
        self.assertFalse(welcome.visible())

    def test_reset_is_a_new_session(self):
        flag = FakeFlag(False)
        welcome = self.welcome(flag)
        welcome.visible()
        welcome.reset()
        self.assertFalse(welcome.visible())  # the flag says it was shown


class TheTexts(unittest.TestCase):
    def test_the_welcome_text_names_the_version_and_stays_small(self):
        text = nc.welcome_text("0.1.0-beta")
        self.assertEqual(
            text,
            "Welcome to SciForge 0.1.0-beta. It works like Fusion: the ribbon, the timeline, S "
            "for search. This is a beta: save often.",
        )
        self.assertIn(__version__, nc.welcome_text(__version__))

    def test_the_crash_line_says_what_the_brief_says(self):
        self.assertEqual(nc.CRASH_TEXT, "SciForge closed unexpectedly last time.")

    def test_the_example_is_copied_into_sciforges_own_user_folder(self):
        target = nc.example_copy_target("/data")
        self.assertTrue(target.startswith(os.path.join("/data", "SciForge", "examples")))
        self.assertTrue(target.endswith(".FCStd"))

    def test_module_file_finds_a_file_or_says_empty(self):
        self.assertTrue(nc.module_file(ROOT, "VERSION").endswith("VERSION"))
        self.assertEqual(nc.module_file(ROOT, "nothing-here.md"), "")


class ShippedFiles(unittest.TestCase):
    """The welcome line's buttons work offline: the module carries its own copies."""

    def test_the_cheat_sheet_is_in_the_module(self):
        path = nc.module_file(ROOT, nc.CHEAT_SHEET_FILE)
        self.assertTrue(path, "src/Mod/SciForge/%s is missing" % nc.CHEAT_SHEET_FILE)
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("cheat sheet", text.lower())

    def test_the_example_is_a_real_design_in_the_module(self):
        path = nc.module_file(ROOT, nc.EXAMPLE_FILE)
        self.assertTrue(path, "src/Mod/SciForge/%s is missing" % nc.EXAMPLE_FILE)
        with zipfile.ZipFile(path) as archive:
            self.assertIn("Document.xml", archive.namelist())

    def test_the_module_copies_are_the_ones_in_docs(self):
        """docs/sciforge/ is where people read and edit them; the module's copy is what an
        installed SciForge opens. Edit one: copy it over the other."""
        docs = os.path.join(REPO, "docs", "sciforge")
        if not os.path.isdir(docs):
            self.skipTest("not inside the repository")
        pairs = [
            (
                os.path.join(docs, "cheat-sheet.md"),
                os.path.join(ROOT, nc.CHEAT_SHEET_FILE),
                "cp docs/sciforge/cheat-sheet.md src/Mod/SciForge/docs/cheat-sheet.md",
            ),
            (
                os.path.join(docs, "examples", "pi5-case", "pi5_case.FCStd"),
                os.path.join(ROOT, nc.EXAMPLE_FILE),
                "cp docs/sciforge/examples/pi5-case/pi5_case.FCStd "
                "src/Mod/SciForge/examples/pi5-case/",
            ),
        ]
        for original, copy, command in pairs:
            with open(original, "rb") as a, open(copy, "rb") as b:
                self.assertEqual(a.read(), b.read(), "the copy differs: run  %s" % command)

    def test_the_install_rules_carry_both_folders(self):
        with open(os.path.join(ROOT, "CMakeLists.txt"), encoding="utf-8") as handle:
            rules = handle.read()
        self.assertIn("INSTALL(DIRECTORY docs examples DESTINATION Mod/SciForge", rules)
        self.assertIn('"*.md"', rules.split("INSTALL(DIRECTORY docs examples")[1])
        self.assertIn('"*.FCStd"', rules.split("INSTALL(DIRECTORY docs examples")[1])


if __name__ == "__main__":
    unittest.main()
