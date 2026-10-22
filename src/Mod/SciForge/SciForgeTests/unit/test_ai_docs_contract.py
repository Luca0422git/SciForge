# SPDX-License-Identifier: LGPL-2.1-or-later
"""Contract tests that keep the documentation for AI models from drifting
(docs/sciforge/dev/cadcraft-lessons.md idea 3, "docs that cannot drift"), and the MCP
resources and prompts (sciforge/ai/mcp_resources.py) honest:

  * the tool table of docs/ai/tools.md lists exactly what tools/list answers, in order;
  * every tool of the catalogue has its section there, and the file is exactly what
    tools/sciforge/make_ai_docs.py writes from the catalogue now;
  * every resource resources/list names can be read, every document is listed, every
    sciforge:// link in the documents points to something that exists;
  * every prompt can be fetched and names only tools that exist;
  * the checking tools (catalog/verify_tools.py) are offered and described.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
sys.path.insert(0, ROOT)

from sciforge.ai import catalog, installers, mcp_core, mcp_resources, tool_docs  # noqa: E402

DOCS = os.path.join(ROOT, "docs", "ai")
REPO = os.path.abspath(os.path.join(ROOT, "..", "..", ".."))
LINK = re.compile(r"sciforge://[A-Za-z0-9_./{}<>-]+")


def rpc(method, params=None, call_tool=None, request_id=1):
    message = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        message["params"] = params
    return mcp_core.handle(message, call_tool or FakeSciForge(), version="1.0")


class FakeSciForge:
    """call_tool for the design resources: answers like SciForge does (a sentence, then
    JSON)."""

    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def __call__(self, name, args):
        self.calls.append((name, args))
        if self.fail:
            return {"text": "SciForge is not running.", "image_png_base64": None, "is_error": True}
        body = json.dumps({"tool": name, "args": args})
        return {"text": "Done.\n" + body, "image_png_base64": None, "is_error": False}


def read_doc(name):
    with open(os.path.join(DOCS, name), encoding="utf-8") as handle:
        return handle.read()


class ToolReference(unittest.TestCase):
    def test_table_equals_tools_list(self):
        listed = [t["name"] for t in rpc("tools/list")["result"]["tools"]]
        self.assertEqual(tool_docs.table_names(read_doc(tool_docs.FILE)), listed)

    def test_every_tool_has_a_section(self):
        text = read_doc(tool_docs.FILE)
        for name in catalog.TOOL_NAMES:
            self.assertIn("### `%s`:" % name, text, name)
            self.assertIn('<a id="%s"></a>' % name, text, name)

    def test_file_is_what_the_catalogue_writes(self):
        self.assertEqual(
            read_doc(tool_docs.FILE),
            tool_docs.render(),
            "docs/ai/tools.md is out of date: run tools/sciforge/make_ai_docs.py",
        )

    def test_generator_script_agrees(self):
        script = os.path.join(REPO, "tools", "sciforge", "make_ai_docs.py")
        if not os.path.isfile(script):
            self.skipTest("not in the source tree")
        done = subprocess.run([sys.executable, script, "--check"], capture_output=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    def test_every_help_topic_is_written_once(self):
        text = read_doc(tool_docs.FILE)
        for topic in catalog.HELP:
            self.assertEqual(text.count('<a id="help-%s"></a>' % topic), 1, topic)
        for match in re.findall(r"\(#(help-[a-z_]+)\)", text):
            self.assertIn('<a id="%s"></a>' % match, text)
        for match in re.findall(r"\]\(#([a-z_0-9-]+)\)", text):
            self.assertIn('<a id="%s"></a>' % match, text, match)


class Resources(unittest.TestCase):
    def test_initialize_offers_resources_and_prompts(self):
        caps = rpc("initialize", {"protocolVersion": "2025-11-25"})["result"]["capabilities"]
        self.assertIn("resources", caps)
        self.assertIn("prompts", caps)

    def test_every_listed_resource_can_be_read(self):
        listed = rpc("resources/list")["result"]["resources"]
        uris = [r["uri"] for r in listed]
        self.assertEqual(len(uris), len(set(uris)))
        for row in listed:
            self.assertTrue(row["uri"].startswith("sciforge://"))
            self.assertTrue(row["name"] and row.get("mimeType"), row)
            reply = rpc("resources/read", {"uri": row["uri"]})
            self.assertIn("result", reply, (row["uri"], reply))
            contents = reply["result"]["contents"]
            self.assertEqual(len(contents), 1)
            self.assertEqual(contents[0]["uri"], row["uri"])
            self.assertTrue(contents[0]["text"].strip(), row["uri"])
            if contents[0]["mimeType"] == "application/json":
                json.loads(contents[0]["text"])

    def test_every_document_is_listed(self):
        uris = {r["uri"] for r in mcp_resources.resources()}
        files = mcp_resources.doc_files(DOCS)
        self.assertIn(tool_docs.FILE, [rel for rel, _full in files])
        self.assertIn("README.md", [rel for rel, _full in files])
        for rel, _full in files:
            self.assertIn("sciforge://docs/%s" % rel, uris)
            self.assertIn("sciforge://docs/%s" % rel, mcp_resources.docs_index(DOCS))

    def test_links_in_the_documents_exist(self):
        listed = {r["uri"] for r in mcp_resources.resources()}
        for rel, full in mcp_resources.doc_files(DOCS):
            with open(full, encoding="utf-8") as handle:
                text = handle.read()
            for link in LINK.findall(text):
                link = link.rstrip(".")
                if "{" in link or "<" in link:
                    continue  # a template written out (sciforge://docs/{path}, .../<path>)
                if link.startswith("sciforge://step/"):
                    continue
                if link.startswith("sciforge://tools/"):
                    name = link[len("sciforge://tools/") :]
                    if name.startswith("<"):
                        continue
                    self.assertIn(name, catalog.TOOL_NAMES, "%s in %s" % (link, rel))
                    continue
                self.assertIn(link, listed, "%s in %s" % (link, rel))

    def test_design_resources_ask_sciforge(self):
        fake = FakeSciForge()
        for uri, tool in (
            ("sciforge://design", "inspect_design"),
            ("sciforge://design/check", "check_design"),
            ("sciforge://design/timeline", "get_timeline"),
        ):
            contents = rpc("resources/read", {"uri": uri}, fake)["result"]["contents"]
            self.assertEqual(contents[0]["mimeType"], "application/json")
            self.assertEqual(json.loads(contents[0]["text"])["tool"], tool)
        contents = rpc("resources/read", {"uri": "sciforge://step/Extrude1"}, fake)["result"]
        self.assertEqual(json.loads(contents["contents"][0]["text"])["args"], {"step": "Extrude1"})
        self.assertEqual([c[0] for c in fake.calls][-1], "get_step")

    def test_design_resource_when_sciforge_is_not_there(self):
        contents = rpc("resources/read", {"uri": "sciforge://design"}, FakeSciForge(True))
        content = contents["result"]["contents"][0]
        self.assertEqual(content["mimeType"], "text/plain")
        self.assertIn("not running", content["text"])

    def test_templates(self):
        templates = rpc("resources/templates/list")["result"]["resourceTemplates"]
        names = {t["uriTemplate"] for t in templates}
        self.assertEqual(
            names,
            {
                "sciforge://step/{id}",
                "sciforge://tools/{name}",
                "sciforge://help/{topic}",
                "sciforge://docs/{path}",
            },
        )
        tool = rpc("resources/read", {"uri": "sciforge://tools/render"})["result"]["contents"]
        self.assertEqual(json.loads(tool[0]["text"])["name"], "render")
        catalogue = rpc("resources/read", {"uri": "sciforge://tools"})["result"]["contents"]
        self.assertEqual(len(json.loads(catalogue[0]["text"])["tools"]), len(catalog.TOOLS))

    def test_unknown_and_unsafe_uris(self):
        for uri in (
            "sciforge://nothing",
            "sciforge://tools/no_such_tool",
            "sciforge://help/nope",
            "sciforge://docs/../sciforge/__init__.py",
            "sciforge://docs//etc/passwd",
            "sciforge://docs/.hidden.md",
            "sciforge://docs/missing.md",
            "file:///etc/passwd",
        ):
            reply = rpc("resources/read", {"uri": uri})
            self.assertEqual(reply["error"]["code"], mcp_resources.RESOURCE_NOT_FOUND, uri)
            self.assertEqual(reply["error"]["data"], {"uri": uri})
        self.assertEqual(rpc("resources/read", {})["error"]["code"], mcp_core.INVALID_PARAMS)

    def test_docs_root_from_the_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "guides"))
            with open(os.path.join(tmp, "guides", "first.md"), "w", encoding="utf-8") as handle:
                handle.write("# First steps\n\nHello.\n")
            with open(os.path.join(tmp, "skip.bin"), "wb") as handle:
                handle.write(b"\0")
            os.environ[mcp_resources.ENV_DOCS] = tmp
            try:
                listed = {r["uri"]: r for r in mcp_resources.resources()}
                self.assertIn("sciforge://docs/guides/first.md", listed)
                self.assertEqual(listed["sciforge://docs/guides/first.md"]["title"], "First steps")
                self.assertNotIn("sciforge://docs/skip.bin", listed)
                text = rpc("resources/read", {"uri": "sciforge://docs/guides/first.md"})
                self.assertIn("Hello.", text["result"]["contents"][0]["text"])
            finally:
                os.environ.pop(mcp_resources.ENV_DOCS, None)


class Prompts(unittest.TestCase):
    def test_every_prompt_names_real_tools(self):
        for prompt in mcp_resources.PROMPTS:
            for tool in prompt["tools"]:
                self.assertIn(tool, catalog.TOOL_NAMES, (prompt["name"], tool))
            args = {a["name"]: "x" for a in prompt["arguments"] if a.get("required")}
            text = mcp_resources.get_prompt(prompt["name"], args)["messages"][0]["content"]["text"]
            for tool in prompt["tools"]:
                self.assertIn(tool, text, (prompt["name"], tool))
            self.assertNotIn("{", text.replace('{"', ""), prompt["name"])  # all filled in

    def test_list_and_get(self):
        listed = rpc("prompts/list")["result"]["prompts"]
        names = [p["name"] for p in listed]
        for name in ("model_part", "fix_failed_step", "prepare_for_3d_printing"):
            self.assertIn(name, names)
        reply = rpc(
            "prompts/get",
            {
                "name": "model_part",
                "arguments": {"description": "a 40 x 30 x 10 box", "material": "PLA"},
            },
        )
        message = reply["result"]["messages"][0]
        self.assertEqual(message["role"], "user")
        self.assertIn("a 40 x 30 x 10 box", message["content"]["text"])
        self.assertIn("physical_material", message["content"]["text"])
        reply = rpc(
            "prompts/get", {"name": "prepare_for_3d_printing", "arguments": {"format": "stl"}}
        )
        self.assertIn("format stl", reply["result"]["messages"][0]["content"]["text"])

    def test_bad_requests(self):
        self.assertEqual(rpc("prompts/get", {"name": "nope"})["error"]["code"], -32602)
        self.assertEqual(rpc("prompts/get", {"name": "model_part"})["error"]["code"], -32602)
        reply = rpc("prompts/get", {"name": "review_design", "arguments": {"extra": "1"}})
        self.assertEqual(reply["error"]["code"], -32602)
        self.assertEqual(rpc("prompts/get", {})["error"]["code"], -32602)


class CheckingTools(unittest.TestCase):
    NAMES = ("inspect_design", "query_geometry", "check_design", "render", "diff_design")

    def test_offered_read_only_and_early_for_small_providers(self):
        for name in self.NAMES:
            entry = catalog.tool(name)
            self.assertIsNotNone(entry, name)
            self.assertTrue(catalog.is_read_only(name), name)
            self.assertIn(name, [t["name"] for t in catalog.chat_tools(48)], name)
        self.assertIn("checking", catalog.HELP)
        for name in self.NAMES:
            self.assertIn(name, catalog.HELP["checking"])

    def test_rules(self):
        self.assertIn(
            "give view or direction, not both",
            catalog.validate("render", {"view": "top", "direction": [1, 1, 1]}),
        )
        self.assertTrue(catalog.validate("render", {"highlight": {"of": "Body"}}))
        self.assertTrue(catalog.validate("render", {"highlight": {"faces": {"normal": 1}}}))
        self.assertEqual(catalog.validate("render", {"highlight": {"edges": {"type": "line"}}}), [])
        self.assertTrue(
            catalog.validate(
                "query_geometry", {"element": "edges", "select": {"normal": [0, 0, 1]}}
            )
        )
        self.assertEqual(
            catalog.validate(
                "query_geometry",
                {
                    "element": "vertices",
                    "select": {"at": {"axis": "z", "value": "max"}, "count": 4},
                },
            ),
            [],
        )
        self.assertTrue(catalog.validate("diff_design", {}))
        self.assertEqual(catalog.validate("measure", {"a": {"origin": True}}), [])

    def test_mcp_marks_them_read_only(self):
        tools = {t["name"]: t for t in rpc("tools/list")["result"]["tools"]}
        for name in self.NAMES:
            self.assertTrue(tools[name]["annotations"]["readOnlyHint"], name)


class CompactAnswers(unittest.TestCase):
    def test_short_parts_on_one_line_and_same_data(self):
        from sciforge.ai import bridge_core

        data = {
            "bodies": [{"id": "Body", "bbox_mm": {"min": [0, 0, 0], "max": [60, 40, 10]}}],
            "ref": {"type": "plane", "normal": [0, 0, 1], "count": 1},
            "long": ["x" * 30] * 5,
            "empty": [],
        }
        text = bridge_core.compact_json(data)
        self.assertEqual(json.loads(text), data)
        self.assertIn('"ref": {"type": "plane", "normal": [0, 0, 1], "count": 1}', text)
        self.assertIn('"bbox_mm": {"min": [0, 0, 0], "max": [60, 40, 10]}', text)
        self.assertTrue(all(len(line) <= 110 for line in text.splitlines()), text)
        self.assertEqual(bridge_core.compact_json([]), "[]")
        self.assertEqual(bridge_core.compact_json("é"), '"é"')


class ClaudeExtension(unittest.TestCase):
    def test_the_extension_carries_the_documents_and_serves_them(self):
        files = installers.mcpb_files(ROOT)
        self.assertIn("server/sciforge/ai/mcp_resources.py", files)
        self.assertIn("server/docs/ai/%s" % tool_docs.FILE, files)
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "SciForge.mcpb")
            installers.build_mcpb(out, files, installers.manifest("1.0.0", sys.executable))
            with zipfile.ZipFile(out) as archive:
                archive.extractall(os.path.join(tmp, "x"))
            script = os.path.join(tmp, "x", *installers.ENTRY_POINT.split("/"))
            lines = "".join(
                json.dumps({"jsonrpc": "2.0", "id": i, "method": m, "params": p}) + "\n"
                for i, (m, p) in enumerate(
                    (
                        ("resources/read", {"uri": "sciforge://docs/tools.md"}),
                        ("prompts/list", {}),
                    ),
                    start=1,
                )
            )
            env = dict(os.environ)
            env.pop(mcp_resources.ENV_DOCS, None)
            done = subprocess.run(
                [sys.executable, script, "--bridge-file", os.path.join(tmp, "none.json")],
                input=lines.encode("utf-8"),
                capture_output=True,
                timeout=30,
                cwd=tmp,
                env=env,
            )
            self.assertEqual(done.returncode, 0, done.stderr)
            replies = [json.loads(line) for line in done.stdout.decode("utf-8").splitlines()]
            self.assertEqual(replies[0]["result"]["contents"][0]["text"], tool_docs.render())
            self.assertTrue(replies[1]["result"]["prompts"])


if __name__ == "__main__":
    unittest.main()
