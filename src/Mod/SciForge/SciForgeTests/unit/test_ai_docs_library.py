# SPDX-License-Identifier: LGPL-2.1-or-later
"""SciForge's documentation for AI models as a library (sciforge/ai/docs_core.py) and the
accuracy of what is in it:

  * Markdown sections, anchors, pages and tool-call blocks are read right;
  * docs_search finds the right document for realistic questions an AI asks;
  * docs_read reads documents, sections and golden models, and says what exists when asked
    for something that does not;
  * examples_search filters recipes and golden models by words, tool, op, tag and kind;
  * every tool call in every document names a real tool with arguments the catalogue accepts
    (the FreeCAD side, SciForgeTests/headless/docs_runner.py, runs them);
  * every recipe is listed, tagged and has calls; the docs tools' descriptions name only
    recipes that exist;
  * every tool has a recorded example that matches its spec (SciForgeTests/docs/);
  * the documentation tools are offered everywhere and answered by the MCP server itself;
  * the chat's system prompt carries a short index, not the documents; the single-file export
    and the command line work.
Plain Python, no FreeCAD.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
sys.path.insert(0, ROOT)

from sciforge.ai import catalog, chat_core, docs_core, mcp_core, tool_docs  # noqa: E402

DOCS = os.path.join(ROOT, "docs", "ai")
LIB = docs_core.library(DOCS)

# (a question an AI would ask, the document (or one of the documents) that must be among the
# first three answers)
QUESTIONS = (
    ("which way does an XZ sketch extrude", "handbook.md"),
    ("cut from the top face does nothing", "troubleshooting.md"),
    ("selector for the four top edges", "selectors.md"),
    ("how do I check the volume after a change", "checking.md"),
    ("undo the last AI step", "handbook.md"),
    ("history marker roll back insert feature", "handbook.md"),
    ("regions pick an area of the sketch", "sketches.md"),
    ("enclosure box with lid", "recipes/enclosure-with-lid.md"),
    ("keyway in a shaft", "recipes/shaft-with-keyway.md"),
    ("two gears meshing centre distance", "recipes/gear-pair.md"),
    ("bolt circle flange holes", "recipes/flange-bolt-pattern.md"),
    ("hex bolt with a modeled thread", "recipes/threaded-fastener.md"),
    ("snap fit hook cantilever", "recipes/snap-fit.md"),
    ("sheet metal bracket bends", "recipes/sheet-like-part.md"),
    ("knob with grip grooves", "recipes/revolved-knob.md"),
    ("loft through three profiles handle", "recipes/lofted-handle.md"),
    ("surface patch thicken panel", "recipes/surface-patch.md"),
    ("drive sizes from user parameters", ("recipes/parametric-plate.md", "handbook.md")),
    ("selector picked 4 edges expected 3", "troubleshooting.md"),
    ("fillet radius too big", "reference/fillet.md"),
    ("counterbore hole options", "reference/hole.md"),
    ("revolute joint between components", "handbook.md"),
    ("known issues of the beta", "user/known-issues.md"),
    ("keyboard shortcuts cheat sheet", "user/cheat-sheet.md"),
    ("golden models of shell", "examples/golden-models.md"),
)


def found_in_top(query, expected, n=3):
    results = docs_core.search(query, limit=n, per_doc=1, lib=LIB)["results"]
    wanted = (expected,) if isinstance(expected, str) else expected
    paths = [r["path"] for r in results]
    return any(w in paths for w in wanted), [r["uri"] for r in results]


class Markdown(unittest.TestCase):
    def test_slug_like_github(self):
        self.assertEqual(docs_core.slug("Units and coordinates"), "units-and-coordinates")
        self.assertEqual(docs_core.slug("`extrude`: Extrude"), "extrude-extrude")
        self.assertEqual(docs_core.slug("Fusion's ideas in SciForge"), "fusions-ideas-in-sciforge")
        self.assertEqual(docs_core.slug("get_help"), "get_help")

    def test_sections_skip_code_and_keep_aliases(self):
        text = "\n".join(
            [
                "# Title",
                "intro",
                '<a id="first"></a>',
                "",
                "## One",
                "```",
                "# not a heading",
                "```",
                "### Sub",
                "## One",
                "end",
            ]
        )
        secs = docs_core.sections(text)
        self.assertEqual([s["anchor"] for s in secs], ["title", "one", "sub", "one-1"])
        self.assertEqual(secs[1]["aliases"], ["first"])
        lines = text.split("\n")
        self.assertEqual(lines[secs[1]["start"] : secs[1]["end"]][-1], "### Sub")  # sub inside
        self.assertEqual(secs[1]["body_end"], 8)

    def test_call_blocks(self):
        text = 'a\n```json sciforge-calls\n[{"tool": "get_design", "args": {}}]\n```\n'
        self.assertEqual(docs_core.call_blocks(text), [(2, [{"tool": "get_design", "args": {}}])])
        with self.assertRaises(ValueError):
            docs_core.call_blocks("```json sciforge-calls\n[{oops}]\n```\n")
        with self.assertRaises(ValueError):
            docs_core.call_blocks('```json sciforge-calls\n[{"args": {}}]\n```\n')
        with self.assertRaises(ValueError):
            docs_core.call_blocks("```json sciforge-calls\n[]\n")
        self.assertEqual(docs_core.call_blocks("```json\n[1]\n```\n"), [])
        quoted = '~~~~text\n```json sciforge-calls\n[{"tool": "undo"}]\n```\n~~~~\n'
        self.assertEqual(docs_core.call_blocks(quoted), [])  # (a block quoted in an answer)

    def test_words(self):
        self.assertEqual(docs_core.words("Holes and sketches"), ["hole", "sketch"])
        self.assertIn("fillet_sets", docs_core.words("fillet_sets"))
        self.assertIn("fillet", docs_core.words("fillet_sets"))
        self.assertEqual(docs_core.words("the of and"), [])

    def test_pages(self):
        text = "\n".join("line %03d" % i for i in range(300))
        pages = docs_core._pages(text, 1000)
        self.assertEqual("\n".join(pages), text)
        self.assertTrue(all(len(p) <= 1000 for p in pages))


class Search(unittest.TestCase):
    def test_realistic_questions(self):
        missed = []
        for query, expected in QUESTIONS:
            ok, got = found_in_top(query, expected)
            if not ok:
                missed.append((query, expected, got))
        self.assertEqual(missed, [])

    def test_answer_shape_and_scope(self):
        found = docs_core.search("shell thickness", limit=5, lib=LIB)
        self.assertTrue(found["results"])
        row = found["results"][0]
        for key in ("uri", "path", "anchor", "document", "section", "score", "snippet"):
            self.assertIn(key, row)
        self.assertTrue(row["uri"].startswith("sciforge://docs/"))
        scoped = docs_core.search("fillet", scope="recipes", limit=20, lib=LIB)["results"]
        self.assertTrue(scoped)
        self.assertTrue(all(r["path"].startswith("recipes/") for r in scoped))
        one = docs_core.search("fillet", scope="handbook.md", limit=20, lib=LIB)["results"]
        self.assertTrue(all(r["path"] == "handbook.md" for r in one))
        self.assertEqual(docs_core.search("zzqqxx", lib=LIB)["results"], [])

    def test_tool_answers(self):
        text, failed = docs_core.tool_answer("docs_search", {"query": "zzqqxx"}, lib=LIB)
        self.assertFalse(failed)
        self.assertIn("Nothing in the documentation matches", text)
        text, failed = docs_core.tool_answer("docs_search", {"query": "fillet"}, lib=LIB)
        self.assertFalse(failed)
        json.loads(text[text.index("{") :])


class Read(unittest.TestCase):
    def test_document_section_and_pages(self):
        got = docs_core.read("handbook.md", lib=LIB)
        self.assertEqual(got["title"], "SciForge handbook for AI models")
        self.assertGreaterEqual(got["pages"], 1)
        got = docs_core.read("sciforge://docs/handbook.md#units-and-coordinates", lib=LIB)
        self.assertTrue(got["text"].startswith("## Units and coordinates"))
        self.assertNotIn("## Fusion's ideas", got["text"])
        alias = docs_core.read("handbook.md#bodies-and-components", lib=LIB)
        self.assertTrue(alias["text"].startswith("## Bodies"))
        long = docs_core.read("user/feature-outline.md", page_chars=4000, lib=LIB)
        self.assertGreater(long["pages"], 1)
        self.assertIn("sections", long)
        last = docs_core.read("user/feature-outline.md", page=99, page_chars=4000, lib=LIB)
        self.assertEqual(last["page"], last["pages"])

    def test_golden_and_index(self):
        got = docs_core.read("golden/box_basic", lib=LIB)
        self.assertIn("Golden model box_basic", got["text"])
        self.assertIn("extrude: extrude", got["text"])
        got = docs_core.read("index", lib=LIB)
        self.assertIn("handbook.md", got["text"])

    def test_not_found_says_what_exists(self):
        for target, words in (
            ("handbok.md", "Close: handbook.md"),
            ("handbook.md#unitz-and-coordinates", "#units-and-coordinates"),
            ("golden/box_basik", "box_basic"),
            ("sciforge://design", "is not a document"),  # (a tool URI reads its page)
            ("../secret.md", "There is no document"),
        ):
            with self.assertRaises(docs_core.NotFound) as caught:
                docs_core.read(target, lib=LIB)
            self.assertIn(words, str(caught.exception), target)
        text, failed = docs_core.tool_answer("docs_read", {"path": "nope.md"}, lib=LIB)
        self.assertTrue(failed)
        text, failed = docs_core.tool_answer(
            "docs_read", {"path": "handbook.md", "section": "ids-and-names"}, lib=LIB
        )
        self.assertFalse(failed)
        self.assertIn("section Ids and names", text)


class Examples(unittest.TestCase):
    def test_filters(self):
        recipes = docs_core.examples(kind="recipe", limit=50, lib=LIB)["results"]
        self.assertGreaterEqual(len(recipes), 12)
        self.assertTrue(all(r["kind"] == "recipe" for r in recipes))
        golden = docs_core.examples(op="sf_revolve", kind="golden", limit=50, lib=LIB)
        self.assertTrue(golden["results"])
        self.assertTrue(all("sf_revolve" in r["ops"] for r in golden["results"]))
        self.assertTrue(all("revolve" in r["tools"] for r in golden["results"]))
        shell = docs_core.examples(tool="shell", kind="recipe", lib=LIB)["results"]
        self.assertIn("enclosure-with-lid", [r["id"] for r in shell])
        tagged = docs_core.examples(tag="gear", limit=50, lib=LIB)["results"]
        self.assertTrue(tagged)
        ranked = docs_core.examples("flange bolt circle", limit=3, lib=LIB)["results"]
        self.assertEqual(ranked[0]["id"], "flange-bolt-pattern")
        text, failed = docs_core.tool_answer("examples_search", {"query": "zzqqxx"}, lib=LIB)
        self.assertFalse(failed)
        self.assertIn("No example matches", text)


class Accuracy(unittest.TestCase):
    def test_every_call_in_the_documents_is_valid(self):
        """Every block call names a tool the catalogue has, with arguments it accepts (unless
        the call is there to show a refusal); the FreeCAD side runs them."""
        bad = []
        total = 0
        for doc in LIB.docs:
            if doc.kind != "text/markdown":
                continue
            for line, calls in docs_core.call_blocks(doc.text):
                for call in calls:
                    total += 1
                    tool = call["tool"]
                    if catalog.tool(tool) is None:
                        bad.append((doc.rel, line, tool, "no such tool"))
                        continue
                    if set(call) - {"tool", "args", "expect"}:
                        bad.append((doc.rel, line, tool, "unknown keys %s" % set(call)))
                    expect = call.get("expect") or {}
                    if set(expect) - {"error", "contains", "not_contains", "json", "image"}:
                        bad.append((doc.rel, line, tool, "unknown expect %s" % set(expect)))
                    problems = catalog.validate(tool, call.get("args", {}))
                    if problems and not expect.get("error"):
                        bad.append((doc.rel, line, tool, problems))
        self.assertEqual(bad, [])
        self.assertGreater(total, 250)

    def test_recipes_are_listed_tagged_and_tested(self):
        index = LIB.doc("recipes/index.md").text
        recipes = [
            d for d in LIB.docs if d.rel.startswith("recipes/") and d.rel != "recipes/index.md"
        ]
        self.assertGreaterEqual(len(recipes), 12)
        for doc in recipes:
            self.assertIn("sciforge://docs/%s" % doc.rel, index, doc.rel)
            self.assertIn("\nTags: ", doc.text, doc.rel)
            blocks = docs_core.call_blocks(doc.text)
            self.assertTrue(blocks, doc.rel)
            first = blocks[0][1][0]
            self.assertEqual(first["tool"], "new_design", doc.rel)  # each starts afresh
            calls = [c for _l, b in blocks for c in b]
            self.assertIn("check_design", [c["tool"] for c in calls], doc.rel)

    def test_luca_list_of_parts_is_covered(self):
        ids = {e["id"] for e in docs_core.examples(kind="recipe", limit=50, lib=LIB)["results"]}
        for name in (
            "bracket",
            "enclosure-with-lid",
            "shaft-with-keyway",
            "gear-pair",
            "flange-bolt-pattern",
            "threaded-fastener",
            "snap-fit",
            "sheet-like-part",
            "revolved-knob",
            "lofted-handle",
            "surface-patch",
        ):
            self.assertIn(name, ids)

    def test_docs_tool_descriptions_name_real_recipes(self):
        words = catalog.tool("examples_search")["description"]
        for phrase, rel in (
            ("bracket", "recipes/bracket.md"),
            ("enclosure with lid", "recipes/enclosure-with-lid.md"),
            ("shaft with keyway", "recipes/shaft-with-keyway.md"),
            ("gear pair", "recipes/gear-pair.md"),
            ("flange with bolt pattern", "recipes/flange-bolt-pattern.md"),
            ("threaded fastener", "recipes/threaded-fastener.md"),
            ("snap-fit", "recipes/snap-fit.md"),
            ("sheet-like part", "recipes/sheet-like-part.md"),
            ("revolved knob", "recipes/revolved-knob.md"),
            ("lofted handle", "recipes/lofted-handle.md"),
            ("surface patch", "recipes/surface-patch.md"),
        ):
            self.assertIn(phrase, words)
            self.assertIsNotNone(LIB.doc(rel), rel)


class ToolExamples(unittest.TestCase):
    def setUp(self):
        from SciForgeTests.docs import tool_examples

        self.spec = tool_examples
        self.results = tool_docs.load_results()

    def test_every_tool_has_an_example(self):
        named = {e["tool"] for e in self.spec.EXAMPLES}
        self.assertEqual(sorted(set(catalog.TOOL_NAMES) - named), [])
        self.assertEqual(sorted(named - set(catalog.TOOL_NAMES)), [])

    def test_examples_are_valid_and_recorded_for_these_arguments(self):
        from SciForgeTests.headless import docs_runner

        for key, ex in docs_runner.numbered(self.spec.EXAMPLES):
            self.assertIn(ex["setup"], self.spec.SETUPS, key)
            for call in self.spec.SETUPS[ex["setup"]] + ex.get("setup_extra", []):
                self.assertEqual(catalog.validate(call["tool"], call["args"]), [], (key, call))
            self.assertEqual(catalog.validate(ex["tool"], ex["args"]), [], key)
            self.assertTrue(ex.get("note"), key)
            recorded = self.results.get(key)
            self.assertIsNotNone(recorded, "%s: no recorded answer (record it)" % key)
            spec = json.loads(json.dumps(docs_runner.spec_of(ex, self.spec.SETUPS)))
            self.assertEqual(
                {k: recorded.get(k) for k in spec}, spec, "%s: recorded for other calls" % key
            )
            self.assertEqual(recorded.get("note"), ex["note"], key)
            self.assertFalse(recorded["answer"]["is_error"], key)
        gui = [e["tool"] for e in self.spec.EXAMPLES if e.get("gui")]
        for name in gui:
            self.assertIn("gui", catalog.tool(name)["needs"], name)

    def test_no_recorded_answer_is_left_over(self):
        from SciForgeTests.headless import docs_runner

        keys = {k for k, _ex in docs_runner.numbered(self.spec.EXAMPLES)}
        self.assertEqual(sorted(set(self.results) - keys), [])

    def test_answers_compare_numbers_with_a_tolerance(self):
        from SciForgeTests.headless import docs_runner

        a = {"text": "Body1: 23785.4 mm3, 60 x 40", "is_error": False}
        self.assertIsNone(
            docs_runner.same_answer(a, dict(a, text="Body1: 23785.40001 mm3, 60 x 40"))
        )
        self.assertTrue(docs_runner.same_answer(a, dict(a, text="Body1: 23000 mm3, 60 x 40")))
        self.assertTrue(docs_runner.same_answer(a, dict(a, text="Body2: 23785.4 mm3, 60 x 40")))
        self.assertTrue(docs_runner.same_answer(a, dict(a, is_error=True)))

    def test_expect_checks(self):
        from SciForgeTests.headless import docs_runner

        answer = {"text": 'Done.\n{"bodies": [{"v": 10.0}], "ok": true}', "is_error": False}
        check = docs_runner.check_expect
        self.assertEqual(check({"json": {"bodies.0.v": [10, 0.1], "bodies.#": 1}}, answer), [])
        self.assertTrue(check({"json": {"bodies.0.v": [11, 0.1]}}, answer))
        self.assertTrue(check({"json": {"nope": 1}}, answer))
        self.assertTrue(check({"error": True}, answer))
        self.assertTrue(check({"contains": ["xyz"]}, answer))
        self.assertTrue(check({"not_contains": ["Done"]}, answer))
        self.assertEqual(check({"json": {"ok": True}}, answer), [])


class Offered(unittest.TestCase):
    NAMES = docs_core.TOOLS

    def test_catalogue_entries(self):
        for name in self.NAMES:
            entry = catalog.tool(name)
            self.assertIsNotNone(entry, name)
            self.assertTrue(catalog.is_read_only(name), name)
            self.assertEqual(entry["needs"], (), name)
            self.assertEqual(entry["category"], "help", name)
            self.assertIn(name, [t["name"] for t in catalog.chat_tools(48)], name)
        self.assertIn("docs", catalog.HELP)
        self.assertIn("docs_search", catalog.INSTRUCTIONS)
        self.assertTrue(catalog.validate("docs_search", {"query": "  "}))
        self.assertTrue(catalog.validate("examples_search", {}))
        self.assertEqual(catalog.validate("examples_search", {"kind": "recipe"}), [])

    def test_mcp_answers_them_with_sciforge_closed(self):
        def closed(name, args):
            raise ConnectionRefusedError("SciForge is not running")

        for name, args in (
            ("docs_search", {"query": "undo"}),
            ("docs_read", {"path": "handbook.md", "section": "ids-and-names"}),
            ("examples_search", {"tool": "gear"}),
        ):
            reply = mcp_core.handle(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": name, "arguments": args},
                },
                closed,
                "1",
            )
            self.assertFalse(reply["result"]["isError"], (name, reply))
        reply = mcp_core.handle(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "get_design", "arguments": {}},
            },
            closed,
            "1",
        )
        self.assertTrue(reply["result"]["isError"])  # the design tools still need SciForge

    def test_system_prompt_has_an_index_not_the_documents(self):
        prompt = chat_core.SYSTEM_PROMPT
        self.assertIn("docs_search", prompt)
        self.assertIn("handbook.md", prompt)
        self.assertIn("recipes/<name>.md", prompt)
        self.assertIn("reference/<tool>.md", prompt)
        self.assertLess(len(prompt), 8000)
        self.assertLess(len(docs_core.prompt_index(lib=LIB)), 3000)
        self.assertNotIn("## Units and coordinates", prompt)


class Export(unittest.TestCase):
    def test_single_file(self):
        standard = docs_core.export_text(lib=LIB)
        compact = docs_core.export_text(compact=True, lib=LIB)
        full = docs_core.export_text(full=True, lib=LIB)
        self.assertTrue(len(compact) < len(standard) < len(full))
        for text in (compact, standard, full):
            self.assertTrue(text.startswith("# " + docs_core.EXPORT_TITLE))
            self.assertIn("File: handbook.md", text)
            self.assertIn("File: recipes/bracket.md", text)
        self.assertIn("File: reference/extrude.md", standard)
        self.assertNotIn("File: reference/extrude.md", compact)
        self.assertNotIn("File: user/known-issues.md", standard)
        self.assertIn("File: user/known-issues.md", full)

    def test_command_line(self):
        cli = os.path.join(ROOT, "sciforge", "ai", "cli.py")
        done = subprocess.run(
            [sys.executable, cli, "docs", "search", "keyway", "shaft"],
            capture_output=True,
            timeout=60,
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn(b"shaft-with-keyway", done.stdout)
        done = subprocess.run(
            [sys.executable, cli, "docs", "read", "nothing.md"], capture_output=True, timeout=60
        )
        self.assertEqual(done.returncode, 1)
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "all.md")
            done = subprocess.run(
                [sys.executable, cli, "docs", "export", out, "--compact"],
                capture_output=True,
                timeout=60,
            )
            self.assertEqual(done.returncode, 0, done.stderr)
            with open(out, encoding="utf-8") as handle:
                self.assertIn("File: handbook.md", handle.read())
            done = subprocess.run(
                [sys.executable, cli, "docs", "export", out], capture_output=True, timeout=60
            )
            self.assertEqual(done.returncode, 1)  # it exists: --force to replace it


if __name__ == "__main__":
    unittest.main()
