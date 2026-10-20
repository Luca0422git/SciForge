# SPDX-License-Identifier: LGPL-2.1-or-later
"""Report a Problem, the part without FreeCAD (sciforge/report_core.py): redaction, the report's
layout, the GitHub address. Runs without FreeCAD."""

import os
import sys
import unittest
from urllib.parse import parse_qs, urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from sciforge import report_core as rc  # noqa: E402

WIN_HOME = "C:\\Users\\Luca"
LINUX_HOME = "/home/luca"


class Redaction(unittest.TestCase):
    def red(self, text, home=WIN_HOME, user="Luca", **kw):
        return rc.redact(text, home, user, **kw)

    # -- folders and names
    def test_a_windows_home_folder_becomes_a_tilde(self):
        text = "opened C:\\Users\\Luca\\Documents\\SciForge\\Arm.FCStd"
        self.assertEqual(self.red(text), "opened ~\\Documents\\SciForge\\Arm.FCStd")

    def test_the_settings_folder_under_appdata_goes_too(self):
        text = "Settings folder: C:\\Users\\Luca\\AppData\\Roaming\\SciForge\\"
        out = self.red(text)
        self.assertNotIn("Luca", out)
        self.assertEqual(out, "Settings folder: ~\\AppData\\Roaming\\SciForge\\")

    def test_forward_slashes_and_doubled_backslashes_and_lower_case_drive(self):
        self.assertEqual(self.red("c:/Users/Luca/x.FCStd"), "~/x.FCStd")
        self.assertEqual(self.red("'C:\\\\Users\\\\Luca\\\\x.FCStd'"), "'~\\\\x.FCStd'")
        self.assertEqual(self.red("C:\\USERS\\LUCA\\x"), "~\\x")  # (Windows ignores case)

    def test_another_persons_windows_home_folder_goes_too(self):
        self.assertEqual(self.red("C:\\Users\\Anna\\Desktop\\a.step"), "~\\Desktop\\a.step")

    def test_shared_windows_folders_are_not_a_persons_home(self):
        text = "C:\\Users\\Public\\Documents\\x"
        self.assertEqual(self.red(text), text)

    def test_a_linux_home_folder_becomes_a_tilde(self):
        out = self.red("saved /home/luca/Designs/arm.FCStd", home=LINUX_HOME, user="luca")
        self.assertEqual(out, "saved ~/Designs/arm.FCStd")

    def test_other_homes_on_linux_and_macos_go_too(self):
        self.assertEqual(self.red("/home/anna/x", home=""), "~/x")
        self.assertEqual(self.red("/Users/bob/Library/x", home=""), "~/Library/x")

    def test_a_longer_folder_name_is_not_cut_in_the_middle(self):
        out = self.red("/home/lucas/x", home=LINUX_HOME, user="")
        self.assertEqual(out, "~/x")  # (the generic rule: lucas is a person's home too)
        out = rc.redact("C:\\Users\\LucaPro\\x", "C:\\Users\\Luca", "")
        self.assertEqual(out, "~\\x")

    def test_the_user_name_by_itself_becomes_user(self):
        out = self.red("Computer name LUCA-PC, user Luca, window Luca's design")
        self.assertEqual(out, "Computer name <user>-PC, user <user>, window <user>'s design")

    def test_a_typed_sentence_keeps_the_name_but_loses_the_folder(self):
        out = self.red("Luca here: C:\\Users\\Luca\\x.FCStd is broken", bare_user=False)
        self.assertEqual(out, "Luca here: ~\\x.FCStd is broken")

    def test_a_user_name_that_is_a_plain_word_is_left_in_the_text(self):
        for name in ("root", "user", "admin", "test", "me", "ab"):
            text = "the %s sees the root of the user's test" % name
            self.assertEqual(rc.redact(text, "", name), text, name)

    def test_nothing_to_hide_nothing_changes(self):
        text = "SciForge 0.1.0-beta (build 4fd3bf320d 2026-10-20)\nFreeCAD 1.1.4\nQt 6.8.1"
        self.assertEqual(self.red(text), text)
        self.assertEqual(rc.redact("", "", ""), "")
        self.assertEqual(rc.redact(None, "", ""), "")

    # -- keys
    def test_api_keys_of_the_known_shapes_are_removed(self):
        keys = [
            "sk-ant-api03-AbCdEfGhIjKlMnOpQrStUvWxYz0123456789",
            "sk-proj-AbCdEfGhIjKlMnOpQrStUvWxYz0123456789",
            "sk-AbCdEfGhIjKlMnOpQrStUv1234567890",
            "AIzaSyA-1234567890abcdefghijklmnopqrstuv",
            "ghp_1234567890abcdefghijklmnopqrstuvwxyz",
            "github_pat_11ABCDEFG0123456789_abcdefghijklmnopqrstuvwxyz",
            "xoxb-1234567890-abcdefghij",
            "AKIAABCDEFGHIJKLMNOP",
            "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abc123_-xyz",
        ]
        for key in keys:
            out = rc.redact("AI chat: the key was %s ok" % key)
            self.assertNotIn(key[:14], out, key)
            self.assertIn("<key removed>", out, key)
            self.assertTrue(out.startswith("AI chat: the key was"))
            self.assertTrue(out.endswith(" ok"))

    def test_a_long_value_after_key_or_token_is_removed_but_the_word_stays(self):
        samples = [
            "api_key = 4f9a8c7d6e5b4a3f2e1d0c9b8a7f6e5d",
            'token: "AbCdEf0123456789AbCdEf0123456789"',
            "Authorization: Bearer abcdefghijklmnop1234567890",
            "password is hunter2hunter2hunter2hunter2",
            "secret=dGhpcyBpcyBhIHNlY3JldCB2YWx1ZQ==",
        ]
        for text in samples:
            out = rc.redact(text)
            self.assertIn("<key removed>", out, text)
            for value in (
                "4f9a8c7d6e5b",
                "AbCdEf012345",
                "abcdefghijklmnop",
                "hunter2hunter2",
                "dGhpcyBpcyBh",
            ):
                self.assertNotIn(value, out, text)
        self.assertTrue(rc.redact(samples[0]).startswith("api_key"))
        self.assertIn("token", rc.redact(samples[1]))

    def test_ordinary_words_around_key_and_token_are_left_alone(self):
        for text in (
            "Press the key to continue",
            "key SciForge_CommandSearch",
            "token expired",
            "commit 4fd3bf320d on develop",
            "A hash 4fd3bf320d5e8c1a is not after a key word",
            "Std_ViewIsometric key I",
        ):
            self.assertEqual(rc.redact(text), text)

    def test_a_long_plain_word_after_key_is_not_a_key(self):
        text = "key: Abcdefghijklmnopqrstuvwxyzabcdefghijkl"  # 38 letters, no digit
        self.assertEqual(rc.redact(text), text)

    def test_redaction_does_not_raise_on_junk(self):
        for junk in (b"bytes", 42, ["a"]):
            try:
                rc.redact(junk, "x", "y")
            except Exception:
                self.fail("redact raised on %r" % (junk,))


class TheReport(unittest.TestCase):
    def make(self, **over):
        args = dict(
            what="SciForge closed when I pressed Q.",
            expected="The face moves.",
            version="0.1.0-beta (4fd3bf320d 2026-10-20)",
            system="OS: Windows 11\nQt: 6.8.1\nOpenGL: NVIDIA\nScreen: 2560x1440, scaling 150%",
            diagnostics="SciForge 0.1.0-beta\nSettings folder: C:\\Users\\Luca\\AppData\\Roaming\\SciForge\\",
            recent=["10:00:01 info a", "10:00:02 WARNING b C:\\Users\\Luca\\x.FCStd"],
            crash_name="",
            crash_text="",
            home=WIN_HOME,
            user="Luca",
        )
        args.update(over)
        return rc.make(**args)

    def test_the_text_has_every_part_in_a_fixed_order(self):
        text = self.make(crash_name="session-1.log", crash_text="Fatal Python error")["text"]
        order = [
            "SciForge problem report",
            "Version: 0.1.0-beta",
            "System:",
            "OS: Windows 11",
            "What happened",
            "SciForge closed when I pressed Q.",
            "What I expected",
            "The face moves.",
            "Diagnostics",
            "Recent SciForge messages (newest last):",
            "10:00:02 WARNING b",
            "Crash log session-1.log (last lines):",
            "Fatal Python error",
        ]
        at = -1
        for part in order:
            found = text.find(part, at + 1)
            self.assertGreater(found, at, "%r missing or out of order in\n%s" % (part, text))
            at = found
        self.assertTrue(text.endswith("\n"))

    def test_everything_in_it_is_redacted(self):
        report = self.make(
            what="It broke in C:\\Users\\Luca\\Documents\\a.FCStd, key sk-ant-api03-AbCdEfGhIjKlMnOpQrStUvWx12",
            crash_name="s.log",
            crash_text='File "C:\\Users\\Luca\\x.py", line 1\nuser Luca',
        )
        for where in (report["text"], *report["fields"].values(), report["title"]):
            self.assertNotIn("Luca", where.replace("Luca0422git", ""), where)
            self.assertNotIn("sk-ant", where)
        self.assertIn("~\\Documents\\a.FCStd", report["text"])
        self.assertIn("<user>", report["text"])

    def test_without_text_the_report_says_so_instead_of_leaving_holes(self):
        text = self.make(what="", expected="")["text"]
        self.assertIn("(nothing written)", text)
        self.assertIn("(not said)", text)

    def test_no_crash_log_no_crash_section(self):
        text = self.make()["text"]
        self.assertNotIn("Crash log", text)

    def test_no_recent_messages_says_none(self):
        self.assertIn("(none)", self.make(recent=[])["text"])

    def test_the_title_is_the_first_line_cut_short(self):
        report = self.make(what="\n\n  First line of it\nsecond")
        self.assertEqual(report["title"], "[Bug] First line of it")
        long = self.make(what="x" * 300)
        self.assertLessEqual(len(long["title"]), len("[Bug] ") + rc.TITLE_MAX)
        self.assertTrue(long["title"].endswith("..."))
        self.assertEqual(self.make(what="")["title"], "[Bug] ")

    def test_nothing_of_the_ai_chat_or_the_stored_keys_is_imported(self):
        here = os.path.join(ROOT, "sciforge")
        for name in ("report_core.py", "report_ui.py", "crashlog.py", "crashlog_core.py"):
            with open(os.path.join(here, name), encoding="utf-8") as handle:
                source = handle.read()
            for banned in ("secrets_store", "chat_core", "chat_ui"):
                self.assertNotIn(banned, source, (name, banned))


class TheAddress(unittest.TestCase):
    def report(self, **fields):
        base = {
            "what": "It closed.",
            "expected": "It stays.",
            "version": "0.1.0-beta (abc 2026-10-20)",
            "system": "OS: Windows 11\nQt: 6.8.1",
            "diagnostics": "line one\nline two & more = 100% #1",
        }
        base.update(fields)
        return {"fields": base, "title": "[Bug] It closed.", "text": "..."}

    def query(self, url):
        parts = urlparse(url)
        self.assertEqual(parts.scheme + "://" + parts.netloc + parts.path, rc.NEW_ISSUE)
        return {k: v[0] for k, v in parse_qs(parts.query, keep_blank_values=True).items()}

    def test_the_address_names_the_repository_the_template_and_the_forms_field_ids(self):
        url, cut = rc.issue_url(self.report())
        self.assertEqual(cut, [])
        self.assertTrue(url.startswith("https://github.com/Luca0422git/SciForge/issues/new?"))
        got = self.query(url)
        self.assertEqual(got["template"], "bug_report.yml")
        self.assertEqual(got["title"], "[Bug] It closed.")
        self.assertEqual(got["what_happened"], "It closed.")
        self.assertEqual(got["expected"], "It stays.")
        self.assertEqual(got["version"], "0.1.0-beta (abc 2026-10-20)")
        self.assertEqual(got["system"], "OS: Windows 11\nQt: 6.8.1")
        self.assertEqual(got["diagnostics"], "line one\nline two & more = 100% #1")

    def test_the_field_ids_are_the_ones_the_issue_form_agreed_on(self):
        self.assertEqual(
            rc.FIELD_ID,
            {
                "what": "what_happened",
                "expected": "expected",
                "steps": "steps",
                "diagnostics": "diagnostics",
                "version": "version",
                "system": "system",
            },
        )

    def test_an_empty_field_is_left_out_so_the_form_shows_its_own_hint(self):
        got = self.query(rc.issue_url(self.report(expected=""))[0])
        self.assertNotIn("expected", got)

    def test_special_characters_and_unicode_survive_the_trip(self):
        text = 'Zeile 1\nZeile 2 \u00fc\u00df \u4e2d\u6587 "quoted" <b>&amp;</b> + ? # / \\'
        got = self.query(rc.issue_url(self.report(what=text))[0])
        self.assertEqual(got["what_happened"], text)

    def test_a_long_log_is_replaced_by_a_note_and_the_address_stays_short_enough(self):
        huge = "x" * 50000
        url, cut = rc.issue_url(self.report(diagnostics=huge))
        self.assertLessEqual(len(url), rc.URL_LIMIT)
        self.assertEqual(cut, ["diagnostics"])
        got = self.query(url)
        self.assertEqual(got["diagnostics"], rc.PASTE_NOTE)
        self.assertEqual(got["what_happened"], "It closed.")  # the short parts stay whole

    def test_an_address_that_just_fits_is_kept_whole(self):
        fits = self.report()
        base = len(rc.issue_url(fits)[0])
        room = rc.URL_LIMIT - base
        fits["fields"]["diagnostics"] += "a" * (room - 5)
        url, cut = rc.issue_url(fits)
        self.assertEqual(cut, [])
        self.assertLessEqual(len(url), rc.URL_LIMIT)
        fits["fields"]["diagnostics"] += "a" * 50
        self.assertEqual(rc.issue_url(fits)[1], ["diagnostics"])

    def test_when_even_the_typed_text_is_too_long_it_is_cut_with_a_note(self):
        url, cut = rc.issue_url(self.report(what="word " * 4000, diagnostics="d" * 10000))
        self.assertLessEqual(len(url), rc.URL_LIMIT)
        self.assertIn("what", cut)
        got = self.query(url)
        self.assertTrue(got["what_happened"].endswith(rc.CUT_NOTE))
        self.assertTrue(got["what_happened"].startswith("word word"))

    def test_multibyte_text_counts_by_its_encoded_length(self):
        url, cut = rc.issue_url(self.report(what="\u4e2d" * 3000))  # 9 characters of address each
        self.assertLessEqual(len(url), rc.URL_LIMIT)
        self.assertIn("what", cut)

    def test_a_smaller_limit_is_honoured(self):
        url, _cut = rc.issue_url(self.report(diagnostics="y" * 5000), limit=1500)
        self.assertLessEqual(len(url), 1500)


if __name__ == "__main__":
    unittest.main()
