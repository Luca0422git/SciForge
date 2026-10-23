# SPDX-License-Identifier: LGPL-2.1-or-later
"""The review of the documentation for AI models (2026-10-22,
docs/sciforge/sessions/2026-10-22-fix-aidocs.md): the parts that need no FreeCAD. What
needs FreeCAD (the hole sizes, the undo steps, the defaults) is checked by
SciForgeTests/headless/docs_runner.py (SciForgeTests/docs/doc_promises.py).
"""

import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
sys.path.insert(0, ROOT)

from sciforge.ai import catalog, docs_core, tool_docs  # noqa: E402


class Search(unittest.TestCase):
    def test_boilerplate_does_not_fill_the_results(self):
        # every reference page has the same Answer section: it is indexed once
        found = docs_core.search("Warning: no solid changed what to do", limit=8)
        sections = [(r["section"], r["snippet"]) for r in found["results"]]
        answers = [r for r in found["results"] if r["section"] == "Answer"]
        self.assertLessEqual(len(answers), 1, sections)
        self.assertEqual(
            found["results"][0]["uri"],
            "sciforge://docs/troubleshooting.md#it-points-the-wrong-way-nothing-changed",
        )

    def test_size_that_does_not_fit_is_found(self):
        found = docs_core.search("radius too big largest that fits", limit=3)
        self.assertEqual(found["results"][0]["path"], "troubleshooting.md")

    def test_unknown_scope_is_told(self):
        text, failed = docs_core.tool_answer("docs_search", {"query": "fillet", "scope": "nope"})
        self.assertTrue(failed)
        self.assertIn("'nope' is not a folder or document", text)
        text, failed = docs_core.tool_answer(
            "docs_search", {"query": "fillet", "scope": "handbook"}
        )
        self.assertFalse(failed)
        self.assertIn("handbook.md", text)


class Links(unittest.TestCase):
    def test_tool_and_handbook_uris_can_be_read(self):
        for target, rel in (
            ("sciforge://tools/query_geometry", "reference/query_geometry.md"),
            ("sciforge://tools/hole#arguments", "reference/hole.md#arguments"),
            ("sciforge://tools", "tools.md"),
            ("sciforge://handbook", "index"),
        ):
            text, failed = docs_core.tool_answer("docs_read", {"path": target})
            self.assertFalse(failed, (target, text[:200]))
            self.assertIn("sciforge://docs/" + rel, text.split("\n", 1)[0])

    def test_written_docs_link_tools_by_their_pages(self):
        lib = docs_core.library()
        for doc in lib.docs:
            if doc.rel.startswith("user/"):
                continue
            self.assertNotIn("(sciforge://tools/", doc.text, doc.rel)


class Pages(unittest.TestCase):
    def test_view_state_tools_are_no_undo_step(self):
        for name in ("show_hide", "activate"):
            flags = tool_docs._flags(catalog.tool(name))
            self.assertIn("not an undo step", flags)
            self.assertNotIn("one undo step", flags)

    def test_dimension_value_unit(self):
        node = {"type": "number", "description": "mm (lengths) or degrees (angles)"}
        self.assertEqual(tool_docs._unit("value", node), "mm or deg")
        self.assertEqual(tool_docs._unit("angle", {"type": "number"}), "deg")

    def test_documented_defaults(self):
        props = lambda name: catalog.tool(name)["input_schema"]["properties"]  # noqa: E731
        self.assertEqual(props("circular_pattern")["quantity"]["default"], 3)
        self.assertEqual(props("pattern_on_path")["quantity"]["default"], 2)
        self.assertEqual(props("rectangular_pattern")["distance"]["default"], 20)
        self.assertNotIn("default", props("insert_hardware")["sink_head"])
        self.assertEqual(props("hole")["drill_point"]["default"], "flat")

    def test_drive_joint_example_names_the_first_joint(self):
        self.assertEqual(catalog.tool("drive_joint")["examples"][0]["arguments"]["joint"], "Joint")


class Hole(unittest.TestCase):
    def test_dialog_options_keep_the_flat_drill_point(self):
        steps = catalog.to_steps(
            "hole",
            {"sketch": "s2", "diameter": 6, "depth": 8, "hole_type": "counterbore",
             "cbore_diameter": 11, "cbore_depth": 3},
            "h",
        )
        self.assertEqual(steps[0]["op"], "hole_points")
        self.assertEqual(steps[0]["drill_point"], "flat")
        steps = catalog.to_steps(
            "hole", {"sketch": "s2", "diameter": 6, "depth": 8, "drill_point": "angle"}, "h"
        )
        self.assertEqual(steps[0]["drill_point"], "angle")

    def test_tapped_hole_needs_a_depth(self):
        problems = catalog.validate(
            "hole", {"sketch": "s2", "tap_type": "tapped", "designation": "M8x1.25"}
        )
        self.assertTrue(any("give depth" in p for p in problems), problems)
        self.assertEqual(
            catalog.validate(
                "hole",
                {"sketch": "s2", "tap_type": "tapped", "designation": "M8x1.25", "depth": 12},
            ),
            [],
        )


class Handbook(unittest.TestCase):
    def test_sizes_in_tokens(self):
        self.assertEqual(docs_core.tokens_text(677559), "169,000")
        self.assertEqual(docs_core.tokens_text(2000), "500")
        compact = len(docs_core.export_text(compact=True))
        big = len(docs_core.export_text())
        self.assertLess(compact, big / 2)


if __name__ == "__main__":
    unittest.main()
