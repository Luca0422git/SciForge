"""The version rules (sciforge/version_core.py) and the places that must agree on the version."""

import os
import re
import unittest

from sciforge import __version__, version_core as vc

HERE = os.path.dirname(os.path.abspath(__file__))
MODULE = os.path.abspath(os.path.join(HERE, "..", ".."))


class OrderTest(unittest.TestCase):
    ORDER = [
        "0.1.0-beta",
        "0.1.0-beta.2",
        "0.1.0-beta.10",
        "0.1.0-rc.1",
        "0.1.0",
        "0.1.1-beta",
        "0.1.1",
        "0.2.0",
        "1.0.0",
    ]

    def test_every_neighbour_pair_is_ordered(self):
        for older, later in zip(self.ORDER, self.ORDER[1:]):
            self.assertLess(vc.parse(older), vc.parse(later), (older, later))
            self.assertTrue(vc.newer(later, older), (later, older))
            self.assertFalse(vc.newer(older, later), (older, later))

    def test_the_whole_list_sorts_to_itself(self):
        shuffled = list(reversed(self.ORDER))
        self.assertEqual(sorted(shuffled, key=vc.parse), self.ORDER)

    def test_numbers_compare_as_numbers(self):
        self.assertTrue(vc.newer("0.10.0", "0.9.0"))
        self.assertTrue(vc.newer("0.1.0-beta.10", "0.1.0-beta.9"))
        # numeric pre-release parts sort before words, a longer list after its prefix
        self.assertTrue(vc.newer("0.1.0-beta", "0.1.0-1"))
        self.assertTrue(vc.newer("0.1.0-beta.1", "0.1.0-beta"))

    def test_equal_versions_are_not_newer(self):
        self.assertFalse(vc.newer("0.1.0-beta", "0.1.0-beta"))
        self.assertEqual(vc.parse("v0.1.0"), vc.parse("0.1.0"))
        self.assertEqual(vc.parse("0.1.0+build5"), vc.parse("0.1.0"))


class NamesTest(unittest.TestCase):
    def test_tag_names_and_a_leading_v_are_accepted(self):
        for text in ("sciforge-v0.1.0-beta", "v0.1.0-beta", "0.1.0-beta", " 0.1.0-beta\n"):
            self.assertEqual(vc.canonical(text), "0.1.0-beta", text)
            self.assertEqual(vc.parse(text), vc.parse("0.1.0-beta"), text)

    def test_tag_for(self):
        self.assertEqual(vc.tag_for("0.1.0-beta"), "sciforge-v0.1.0-beta")
        self.assertEqual(vc.tag_for("v0.1.0"), "sciforge-v0.1.0")
        self.assertEqual(vc.tag_for("sciforge-v0.1.0-beta.2"), "sciforge-v0.1.0-beta.2")

    def test_is_prerelease(self):
        for text in ("0.1.0-beta", "0.1.0-beta.2", "0.1.0-rc.1", "sciforge-v0.1.1-beta"):
            self.assertTrue(vc.is_prerelease(text), text)
        for text in ("0.1.0", "v1.2.3", "0.1.0+build"):
            self.assertFalse(vc.is_prerelease(text), text)


class JunkTest(unittest.TestCase):
    JUNK = [
        None,
        42,
        3.5,
        [],
        {},
        b"0.1.0",
        "",
        " ",
        "beta",
        "0.1",
        "0.1.0.0",
        "a.b.c",
        "01.2.3",
        "0.1.0-",
        "0.1.0-beta..2",
        "0.1.0 beta",
        "sciforge-0.1.0",
        "latest",
    ]

    def test_junk_gives_none_and_never_raises(self):
        for text in self.JUNK:
            self.assertIsNone(vc.parse(text), repr(text))
            self.assertIsNone(vc.canonical(text), repr(text))
            self.assertIsNone(vc.tag_for(text), repr(text))
            self.assertFalse(vc.is_prerelease(text), repr(text))
            self.assertFalse(vc.newer(text, "0.1.0"), repr(text))
            self.assertFalse(vc.newer("9.9.9", text), repr(text))


class OneVersionTest(unittest.TestCase):
    def test_the_version_file_the_literal_and_the_package_agree(self):
        path = os.path.join(MODULE, "VERSION")
        if not os.path.isfile(path):
            self.skipTest("no VERSION file next to the module")
        with open(path, encoding="utf-8") as handle:
            text = handle.read().strip()
        self.assertIsNotNone(vc.parse(text), text)
        self.assertEqual(__version__, text)
        with open(os.path.join(MODULE, "sciforge", "__init__.py"), encoding="utf-8") as handle:
            literal = re.search(r'_FALLBACK_VERSION = "([^"]+)"', handle.read())
        self.assertIsNotNone(literal)
        self.assertEqual(literal.group(1), text, "update _FALLBACK_VERSION with VERSION")

    def test_it_is_a_beta_for_now(self):
        self.assertTrue(vc.is_prerelease(__version__))


if __name__ == "__main__":
    unittest.main()
