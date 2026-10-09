import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from forgecad import search_core  # noqa: E402

ENTRIES = [
    {"name": "PartDesign_Fillet", "text": "Fillet", "shortcut": ""},
    {"name": "PartDesign_Pad", "text": "Pad", "shortcut": ""},
    {"name": "Sketcher_CreateFillet", "text": "Sketch fillet", "shortcut": ""},
    {"name": "Std_ViewFitAll", "text": "Fit all", "shortcut": ""},
    {"name": "PartDesign_Chamfer", "text": "Chamfer", "shortcut": ""},
]


class SearchTests(unittest.TestCase):
    def names(self, query):
        return [e["name"] for e in search_core.rank(query, ENTRIES)]

    def test_exact_prefix_wins(self):
        self.assertEqual(self.names("fillet")[0], "PartDesign_Fillet")

    def test_subsequence_match(self):
        self.assertIn("PartDesign_Fillet", self.names("flt"))

    def test_all_tokens_must_match(self):
        self.assertEqual(self.names("sketch fillet"), ["Sketcher_CreateFillet"])

    def test_no_match(self):
        self.assertEqual(self.names("zzzz"), [])

    def test_empty_query_is_alphabetical(self):
        texts = [e["text"] for e in search_core.rank("", ENTRIES)]
        self.assertEqual(texts, sorted(texts, key=str.lower))

    def test_limit(self):
        self.assertEqual(len(search_core.rank("", ENTRIES, limit=2)), 2)


if __name__ == "__main__":
    unittest.main()
