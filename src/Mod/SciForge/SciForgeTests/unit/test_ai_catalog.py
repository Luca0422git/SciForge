# SPDX-License-Identifier: LGPL-2.1-or-later
"""The AI tool catalogue (sciforge/ai/catalog), the single source of truth for every tool:
each tool is fully described (title, description, Fusion command, category, schema with only
the supported keywords, examples that pass its own checks), names are unique, every op of
the step builder is reachable from a tool, every action has its handler, validation answers
in plain sentences, availability says why not, the design steps fit the golden format, and
the MCP list, the chat panel's list, the Claude extension and `sciforge-cli tools` all come
from it. Runs without FreeCAD (the FreeCAD side is SciForgeTests/headless)."""

import ast
import glob
import json
import os
import re
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from sciforge.ai import catalog, installers, mcp_core, tools_core  # noqa: E402
from sciforge.ai.catalog import kit, registry  # noqa: E402
from SciForgeTests.golden import schema as golden  # noqa: E402

AI = os.path.join(ROOT, "sciforge", "ai")
OPS = os.path.join(AI, "ops")
KEYWORDS = {
    "type",
    "properties",
    "required",
    "additionalProperties",
    "enum",
    "items",
    "minItems",
    "maxItems",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "default",
    "description",
}
TYPES = {"object", "array", "string", "number", "integer", "boolean", "null"}


def _walk(node, path, out):
    out.append((path, node))
    for key, sub in node.get("properties", {}).items():
        _walk(sub, path + "." + key, out)
    if isinstance(node.get("items"), dict):
        _walk(node["items"], path + "[]", out)
    return out


def _builder_ops():
    names = set()
    for path in [os.path.join(OPS, "core.py")] + glob.glob(os.path.join(OPS, "*_ops.py")):
        with open(path, encoding="utf-8") as handle:
            tree = ast.parse(handle.read(), path)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("op_"):
                names.add(node.name[3:])
            if isinstance(node, ast.Attribute) and node.attr.startswith("op_"):
                names.add(node.attr[3:])
    return names


def _action_names():
    """The tools sciforge/ai/actions handles: @action("name") in its modules."""
    found = {}
    for path in glob.glob(os.path.join(AI, "actions", "*.py")):
        with open(path, encoding="utf-8") as handle:
            tree = ast.parse(handle.read(), path)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for deco in node.decorator_list:
                    if (
                        isinstance(deco, ast.Call)
                        and getattr(deco.func, "id", "") == "action"
                        and deco.args
                        and isinstance(deco.args[0], ast.Constant)
                    ):
                        found[deco.args[0].value] = os.path.basename(path)
    return found


def _literal(path, name):
    with open(path, encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == name:
            return node.value
    raise AssertionError("%s not in %s" % (name, path))


class Described(unittest.TestCase):
    def test_names_are_unique_and_plain(self):
        names = [t["name"] for t in catalog.TOOLS]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(tuple(names), catalog.TOOL_NAMES)
        self.assertGreaterEqual(len(names), 100)
        for name in names:
            self.assertRegex(name, r"^[a-z][a-z_]*[a-z]$")
            self.assertLessEqual(len(name), 64)  # (every AI API's limit for a tool name)

    def test_the_first_sixteen_come_first(self):
        self.assertEqual(catalog.TOOL_NAMES[:16], catalog.LEGACY_NAMES)

    def test_every_tool_is_described(self):
        for t in catalog.TOOLS:
            with self.subTest(tool=t["name"]):
                self.assertTrue(t["title"].strip())
                self.assertGreater(len(t["description"]), 60)
                self.assertIn(t["category"], registry.CATEGORY_KEYS)
                self.assertTrue(t["ribbon"].strip())
                self.assertTrue(t["examples"], "every tool has an example")
                for e in t["examples"]:
                    self.assertEqual(set(e), {"arguments", "note"})
                    self.assertTrue(e["note"].strip())
                self.assertIsInstance(t["changes_design"], bool)
                self.assertIsInstance(t["writes_files"], bool)
                self.assertIn(t["kind"], ("steps", "action"))
                for need in t["needs"]:
                    self.assertIn(need, registry.NEEDS)
                self.assertEqual(t["input_schema"]["type"], "object")
                self.assertIs(t["input_schema"].get("additionalProperties"), False)

    def test_every_category_has_tools(self):
        used = {t["category"] for t in catalog.TOOLS}
        self.assertEqual(used, set(registry.CATEGORY_KEYS))

    def test_schemas_use_only_the_supported_subset(self):
        for t in catalog.TOOLS:
            for path, node in _walk(t["input_schema"], t["name"], []):
                with self.subTest(path=path):
                    self.assertLessEqual(set(node), KEYWORDS)
                    kinds = node.get("type", [])
                    kinds = kinds if isinstance(kinds, list) else [kinds]
                    self.assertLessEqual(set(kinds), TYPES)
                    for key in node.get("required", []):
                        self.assertIn(key, node["properties"])
                    if "enum" in node:
                        self.assertTrue(node["enum"])
                    if "default" in node:
                        problems = []
                        kit.check(node, node["default"], path, problems)
                        self.assertEqual(problems, [])
                    if path != t["name"] and "description" not in node and "enum" not in node:
                        # a property without words must at least be self-explaining
                        self.assertTrue(node.get("type") or node.get("properties"), path)
            json.dumps(t["input_schema"])

    def test_every_property_is_explained_somewhere(self):
        """A top-level argument has its own description, or the tool's text names it."""
        for t in catalog.TOOLS:
            for key, node in t["input_schema"].get("properties", {}).items():
                with self.subTest(tool=t["name"], argument=key):
                    self.assertTrue(
                        "description" in node or key in t["description"] or "enum" in node,
                        "%s.%s is explained nowhere" % (t["name"], key),
                    )

    def test_examples_pass_their_own_checks(self):
        for t in catalog.TOOLS:
            for e in t["examples"]:
                with self.subTest(tool=t["name"], note=e["note"]):
                    self.assertEqual(catalog.validate(t["name"], e["arguments"]), [])

    def test_read_only_flags(self):
        for t in catalog.TOOLS:
            read_only = catalog.is_read_only(t["name"])
            self.assertEqual(read_only, not (t["changes_design"] or t["writes_files"]))
            if t["destructive"]:
                self.assertFalse(read_only, t["name"])
        for name in (
            "get_design",
            "get_timeline",
            "get_step",
            "get_sketch",
            "list_tools",
            "measure",
            "physical_properties",
            "list_parameters",
            "get_help",
        ):
            self.assertTrue(catalog.is_read_only(name), name)
        for name in ("extrude", "edit_step", "delete_step", "save", "export", "joint"):
            self.assertFalse(catalog.is_read_only(name), name)

    def test_shared_texts(self):
        for topic in catalog.HELP:
            self.assertTrue(catalog.help_text(topic).strip(), topic)
        listed = catalog.help_text("tools")
        for name in catalog.TOOL_NAMES:
            self.assertIn("  %s - " % name, listed)
        from sciforge.ai.catalog import history_tools

        self.assertEqual(set(history_tools.HELP_TOPICS), set(catalog.HELP) | {"tools"})
        self.assertIn(catalog.SELECTOR_HELP.replace("\n", " "), catalog.INSTRUCTIONS)
        self.assertEqual(mcp_core.INSTRUCTIONS, catalog.INSTRUCTIONS)


class Reach(unittest.TestCase):
    def test_every_builder_op_is_reached_by_a_tool(self):
        builder = _builder_ops()
        self.assertIn("sf_sweep", builder)  # (the source scan works)
        listed = set()
        for t in catalog.TOOLS:
            listed |= set(t["ops"])
        self.assertLessEqual(listed, builder, "a tool lists an op the builder lacks")
        missing = builder - listed - set(catalog.TEST_ONLY_OPS) - set(catalog.AI_TOOLS_TO_COME)
        self.assertEqual(missing, set(), "ops no tool builds")

    def test_test_only_ops_are_real(self):
        known = _builder_ops() | set(golden.STEP_KEYS)
        self.assertLessEqual(set(catalog.TEST_ONLY_OPS), known)

    def test_ai_tools_to_come_are_real_and_still_to_come(self):
        self.assertLessEqual(set(catalog.AI_TOOLS_TO_COME), _builder_ops())
        listed = set()
        for t in catalog.TOOLS:
            listed |= set(t["ops"])
        self.assertEqual(
            listed & set(catalog.AI_TOOLS_TO_COME), set(), "a tool builds it: drop it from the list"
        )

    def test_every_action_has_its_handler(self):
        handlers = _action_names()
        actions = {t["name"] for t in catalog.TOOLS if t["kind"] == "action"}
        self.assertEqual(set(handlers) - set(catalog.TOOL_NAMES), set(), "a handler of no tool")
        self.assertEqual(actions - set(handlers), set(), "an action tool without a handler")
        steps = {t["name"] for t in catalog.TOOLS if t["kind"] == "steps"}
        self.assertEqual(steps & set(handlers), set(), "a step tool with a handler too")

    def test_construct_presets_are_construct_py_s(self):
        from sciforge.ai.catalog import more_tools

        specs = _literal(os.path.join(ROOT, "sciforge", "construct.py"), "SPECS")
        keys = {k.value for k in specs.keys}
        ours = set(more_tools.PLANE_PRESETS + more_tools.AXIS_PRESETS + more_tools.POINT_PRESETS)
        self.assertEqual(ours, keys)
        self.assertEqual(set(more_tools.PRESET_REFS), keys)

    def test_materials_are_material_py_s(self):
        from sciforge.ai.catalog import modify_tools

        rows = ast.literal_eval(_literal(os.path.join(ROOT, "sciforge", "material.py"), "LIBRARY"))
        self.assertEqual(set(modify_tools.MATERIALS), {r[0] for r in rows})

    def test_surface_kinds_are_surface_core_s(self):
        from sciforge.ai.catalog import more_tools

        kinds = _literal(os.path.join(ROOT, "sciforge", "surface_core.py"), "KINDS")
        names = {k.value for k in kinds.keys} - {"piece"}  # (piece: a hidden step)
        self.assertEqual(set(more_tools.SURFACE_KINDS), names)


class Validation(unittest.TestCase):
    SENTENCE = re.compile(r"^[A-Za-z0-9_\[\].\"'(]")

    def assertPlain(self, problems, where):
        self.assertTrue(problems, where)
        for p in problems:
            self.assertIsInstance(p, str)
            self.assertTrue(self.SENTENCE.match(p), "%s: %r" % (where, p))
            for noise in ("Traceback", "Error(", "<class", "{'", "None"):
                self.assertNotIn(noise, p, "%s: %r" % (where, p))

    def test_wrong_arguments_get_plain_sentences(self):
        for t in catalog.TOOLS:
            with self.subTest(tool=t["name"]):
                self.assertPlain(catalog.validate(t["name"], {"colour": "red"}), t["name"])
                self.assertPlain(catalog.validate(t["name"], ["not", "an object"]), t["name"])
                for key, node in t["input_schema"].get("properties", {}).items():
                    wrong = {
                        "object": "text",
                        "array": 3,
                        "string": 7,
                        "number": "x",
                        "integer": 1.5,
                        "boolean": "yes",
                    }
                    kind = node.get("type")
                    if isinstance(kind, str) and kind in wrong:
                        args = dict(t["examples"][0]["arguments"], **{key: wrong[kind]})
                        self.assertPlain(catalog.validate(t["name"], args), t["name"] + "." + key)

    def test_unknown_tool(self):
        problems = catalog.validate("delete_everything", {})
        self.assertEqual(len(problems), 1)
        self.assertIn("no tool called 'delete_everything'", problems[0])

    def test_compact_selectors_are_checked_everywhere(self):
        bad = {"normal": [0, 0, 0], "colour": 1}
        self.assertTrue(catalog.validate("emboss", {"sketch": "s", "faces": bad}))
        rows = {"sets": [{"edges": {"type": "plane"}, "radius": 1}]}
        self.assertIn(
            "sets[0].edges.type must be one of line, circle, ellipse, bspline for edges",
            catalog.validate("fillet_sets", rows),
        )
        side = {"component": "a", "face": {"along": [0, 0, 0]}}
        self.assertTrue(catalog.validate("joint", {"first": side, "second": side}))

    def test_rules(self):
        v = catalog.validate
        self.assertTrue(v("press_pull", {"distance": 1}))  # nothing picked
        self.assertTrue(
            v("press_pull", {"faces": {"all": True}, "edges": {"all": True}, "distance": 1})
        )
        self.assertTrue(v("loft", {"profiles": [{"profile": "s1"}]}))
        self.assertTrue(v("sweep", {"profile": "s1", "path": "p", "type": "rail"}))
        self.assertTrue(v("primitive", {"kind": "sphere", "length": 3}))
        self.assertTrue(v("draft", {"plane": "AB", "faces": {"all": True}}))
        self.assertTrue(v("scale", {"factor": 2, "factors": [1, 1, 1]}))
        self.assertTrue(v("move_copy", {"bodies": ["a"], "faces": {"all": True}}))
        self.assertTrue(v("move_copy", {"faces": {"all": True}, "move_type": "rotate"}))
        self.assertTrue(v("roll_timeline", {"to": "end", "after": "x"}))
        self.assertTrue(
            v(
                "sketch_dimension",
                {
                    "sketch": "s",
                    "kind": "radius",
                    "items": [{"curve": 0}, {"curve": 1}],
                    "value": 3,
                },
            )
        )
        self.assertTrue(
            v("sketch_constraint", {"sketch": "s", "kind": "symmetric", "items": [{"curve": 0}]})
        )
        self.assertTrue(v("export", {"format": "dxf", "path": "/a.dxf"}))
        self.assertTrue(v("export", {"format": "stl", "path": "/a.stl", "sketch": "s"}))
        self.assertTrue(v("open_design", {"path": "/a.txt"}))
        self.assertTrue(v("hole", {"face": {"all": True}, "diameter": 3, "depth": 2}))
        self.assertEqual(
            v(
                "hole",
                {
                    "face": {"normal": [0, 0, 1], "count": 1},
                    "at": [1, 2, 3],
                    "diameter": 3,
                    "depth": 2,
                },
            ),
            [],
        )
        self.assertTrue(v("extrude", {"profile": "s", "to": {"plane": "QQ"}}))
        self.assertEqual(v("extrude", {"profile": "s", "to": {"plane": "XY"}}), [])
        self.assertTrue(v("revolve", {"profile": "s", "axis": "W"}))
        self.assertEqual(v("revolve", {"profile": "s", "axis": {"sketch": "s", "axis": "H"}}), [])
        self.assertTrue(v("shell", {"faces": {"all": True}}))  # no thickness
        self.assertEqual(v("shell", {"body": True, "inside": 2}), [])
        self.assertTrue(v("edit_step", {"step": "x"}))
        self.assertTrue(v("named_view", {"action": "go"}))
        self.assertTrue(v("surface", {"kind": "trim"}))
        self.assertTrue(v("construct_plane", {"preset": "AxisEdge", "refs": [{"plane": "XY"}]}))


class Availability(unittest.TestCase):
    def test_reasons(self):
        nothing = {"design": False, "solid": False, "gui": False, "drawing": False}
        ok, why = catalog.availability("fillet", nothing)
        self.assertFalse(ok)
        self.assertIn("No design is open", why)
        ok, why = catalog.availability("fillet", dict(nothing, design=True))
        self.assertFalse(ok)
        self.assertIn("no solid body", why)
        self.assertEqual(
            catalog.availability("fillet", dict(nothing, design=True, solid=True)), (True, "")
        )
        ok, why = catalog.availability("screenshot", dict(nothing, design=True))
        self.assertFalse(ok)
        self.assertIn("window", why)
        self.assertEqual(catalog.availability("create_sketch", nothing), (True, ""))
        self.assertEqual(catalog.availability("list_tools", nothing), (True, ""))
        ok, why = catalog.availability("add_drawing_view", dict(nothing, design=True))
        self.assertIn("create_drawing", why)

    def test_tool_list(self):
        rows = catalog.tool_list({"design": True, "solid": False, "gui": True})
        self.assertEqual(len(rows), len(catalog.TOOLS))
        fillet = [r for r in rows if r["name"] == "fillet"][0]
        self.assertFalse(fillet["available"])
        self.assertTrue(fillet["why_not"])
        self.assertTrue(all(r["category"] == "modify" for r in catalog.tool_list(None, "modify")))


class Steps(unittest.TestCase):
    def test_example_steps_fit_the_golden_format(self):
        """Every op a step tool's examples build is one the builder has, listed in the tool's
        ops, with only keys the golden format knows for it."""
        for t in catalog.TOOLS:
            if t["kind"] != "steps":
                continue
            for e in t["examples"]:
                with self.subTest(tool=t["name"], note=e["note"]):
                    steps = catalog.to_steps(t["name"], e["arguments"], "x1")
                    self.assertTrue(steps)
                    for step in steps:
                        self.assertIn(step["op"], t["ops"])
                        if step["op"] not in golden.STEP_KEYS:
                            continue
                        required, optional = golden.STEP_KEYS[step["op"]]
                        keys = set(step) - {"op"}
                        self.assertLessEqual(required - {"id"} - keys, set(), step)
                        self.assertLessEqual(keys - required - optional, set(), step)

    def test_action_tools_make_no_steps(self):
        for t in catalog.TOOLS:
            if t["kind"] == "action":
                self.assertEqual(
                    catalog.to_steps(t["name"], t["examples"][0]["arguments"], "x1"), []
                )

    def test_mappings(self):
        steps = catalog.to_steps("shell", {"body": True, "thickness": 2}, "s")
        self.assertEqual(
            steps, [{"op": "sf_shell", "id": "s", "body": True, "direction": "inside", "inside": 2}]
        )
        steps = catalog.to_steps(
            "draft",
            {"plane": "XY", "faces": {"all": True}, "angle": 2, "sides": "two", "angle2": 3},
            "d",
        )
        self.assertEqual(steps[0]["op"], "sf_draft2")
        steps = catalog.to_steps("scale", {"sketch": "s1", "factor": 2}, "c")
        self.assertEqual(steps, [{"op": "sf_scale_sketch", "id": "c", "sketch": "s1", "factor": 2}])
        steps = catalog.to_steps("move_copy", {"faces": {"all": True}, "dz": 3}, "m")
        self.assertEqual(steps[0]["move"], [0, 0, 3])
        steps = catalog.to_steps(
            "hole",
            {
                "sketch": "s2",
                "diameter": 5,
                "depth": 4,
                "tap_type": "tapped",
                "designation": "M6x1",
            },
            "h",
        )
        self.assertEqual(steps[0]["op"], "hole_points")
        steps = catalog.to_steps("rib", {"curves": "s"}, "r")
        self.assertEqual(steps, [{"op": "sf_rib", "id": "r", "kind": "rib", "curves": "s"}])
        steps = catalog.to_steps(
            "press_pull", {"faces": {"all": True}, "distance": 2, "offset_type": "modify"}, "p"
        )
        self.assertEqual(steps[0]["op"], "press_pull_type")
        steps = catalog.to_steps("capture_design_history", {"on": False}, None)
        self.assertEqual(steps, [{"op": "history_off"}])
        steps = catalog.to_steps(
            "create_sketch", {"on": "Plane", "geometry": [{"circle": [0, 0, 1]}]}, "s"
        )
        self.assertEqual(steps[0]["on"], "Plane")
        golden.validate(
            {
                "id": "x",
                "title": "x",
                "steps": [
                    {"op": "sketch", "id": "p", "plane": "XY", "geometry": [{"circle": [0, 0, 1]}]},
                    dict(steps[0], id="s2"),
                ],
                "expect": {"volume": 1, "source": "analytic"},
            }
        )

    def test_extended_extrude_keeps_the_old_steps(self):
        old = catalog.to_steps("extrude", {"profile": "s1", "distance": 10}, "e1")
        self.assertEqual(
            old,
            [{"op": "extrude", "id": "e1", "profile": "s1", "distance": 10, "operation": "join"}],
        )
        new = catalog.to_steps(
            "extrude", {"profile": "s1", "to": {"plane": "XY"}, "thin": {"thickness": 1}}, "e2"
        )
        self.assertEqual(new[0]["extent"], "to_object")
        self.assertEqual(new[0]["thin"], {"thickness": 1})


class Lists(unittest.TestCase):
    def test_mcp_tools_from_the_catalogue(self):
        tools = catalog.mcp_tools()
        self.assertEqual([t["name"] for t in tools], list(catalog.TOOL_NAMES))
        self.assertEqual(tools, tools_core.mcp_tools())
        for item in tools:
            entry = catalog.tool(item["name"])
            self.assertEqual(
                item["annotations"]["readOnlyHint"], catalog.is_read_only(item["name"])
            )
            self.assertEqual(item["annotations"]["destructiveHint"], entry["destructive"])
            self.assertEqual(item["description"], entry["description"])

    def test_mcp_protocol_with_every_tool(self):
        calls = []

        def call_tool(name, args):
            calls.append(name)
            return {"text": "done %s" % name, "image_png_base64": None, "is_error": False}

        def request(params, request_id=1):
            message = {"jsonrpc": "2.0", "id": request_id, "method": "tools/call", "params": params}
            return mcp_core.handle(message, call_tool, "1")

        listed = mcp_core.handle(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, call_tool, "1"
        )
        self.assertEqual(listed["result"]["tools"], catalog.mcp_tools())
        for t in catalog.TOOLS:
            ok = request({"name": t["name"], "arguments": t["examples"][0]["arguments"]})
            self.assertFalse(ok["result"]["isError"], t["name"])
            bad = request({"name": t["name"], "arguments": {"colour": "red"}})
            self.assertTrue(bad["result"]["isError"], t["name"])  # (input validation errors
            text = bad["result"]["content"][0]["text"]  # are tool execution errors)
            self.assertIn("arguments are not right", text)
            self.assertIn("colour is not a known argument", text)
        # Bad calls never reach SciForge; the documentation tools are answered by the MCP
        # server itself (docs_core), so they never reach it either.
        from sciforge.ai import docs_core

        self.assertEqual(calls, [n for n in catalog.TOOL_NAMES if n not in docs_core.TOOLS])
        self.assertEqual(request({"name": "nope", "arguments": {}})["error"]["code"], -32602)
        self.assertEqual(request({"name": "extrude", "arguments": [1]})["error"]["code"], -32602)

    def test_chat_tools(self):
        everything = catalog.chat_tools()
        self.assertEqual(len(everything), len(catalog.TOOLS))
        self.assertEqual([t["name"] for t in everything[:16]], list(catalog.LEGACY_NAMES))
        some = catalog.chat_tools(48)
        self.assertEqual(len(some), 48)
        self.assertEqual(
            [t["name"] for t in some[16 : 16 + len(catalog.CHAT_ORDER)]][:5],
            list(catalog.CHAT_ORDER[:5]),
        )
        for name in catalog.CHAT_ORDER:
            self.assertIsNotNone(catalog.tool(name), name)

    def test_catalogue_json(self):
        data = json.loads(json.dumps(catalog.catalogue()))
        self.assertEqual([t["name"] for t in data["tools"]], list(catalog.TOOL_NAMES))
        for t in data["tools"]:
            self.assertFalse([k for k in t if k.startswith("_")])

    def test_cli_tools_prints_the_catalogue(self):
        script = os.path.join(AI, "cli.py")
        # Output buffered as for any program reading it: the CLI ends with os._exit, and a
        # short answer it did not flush was lost (seen on CI only, where PYTHONUNBUFFERED is unset)
        env = {k: v for k, v in os.environ.items() if k != "PYTHONUNBUFFERED"}
        done = subprocess.run(
            [sys.executable, script, "tools"], capture_output=True, timeout=60, env=env
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout.decode("utf-8")), catalog.catalogue())
        done = subprocess.run(
            [sys.executable, script, "tools", "--names", "--category", "drawing"],
            capture_output=True,
            timeout=60,
            env=env,
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        names = done.stdout.decode("utf-8").split()
        self.assertEqual(names, [t["name"] for t in catalog.TOOLS if t["category"] == "drawing"])
        done = subprocess.run(
            [sys.executable, script, "docs", "search", "extrude"],
            capture_output=True,
            timeout=60,
            env=env,
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue(done.stdout.strip(), "docs search printed nothing")

    def test_claude_extension_lists_every_tool_and_carries_the_catalogue(self):
        data = installers.manifest("1.0.0", "/py")
        self.assertEqual([t["name"] for t in data["tools"]], list(catalog.TOOL_NAMES))
        files = installers.mcpb_files(ROOT)
        for path in glob.glob(os.path.join(AI, "catalog", "*.py")):
            self.assertIn("server/sciforge/ai/catalog/" + os.path.basename(path), files)


class CommandLine(unittest.TestCase):
    def test_parse_tool(self):
        from sciforge.ai import cli

        self.assertEqual(
            cli.parse_tool('extrude {"profile": "s", "distance": 2}'),
            ("extrude", {"profile": "s", "distance": 2}),
        )
        self.assertEqual(cli.parse_tool("get_design"), ("get_design", {}))
        for bad in ("", 'extrude {"a": ', "extrude [1, 2]"):
            with self.assertRaises(ValueError):
                cli.parse_tool(bad)

    def test_arguments_from_the_wrapper_s_file(self):
        import tempfile

        from sciforge.ai import cli

        with tempfile.NamedTemporaryFile("wb", delete=False) as handle:
            handle.write('run\0--tool\0extrude {"a": 1}\0--save\0/x y/z.FCStd\0'.encode())
        self.addCleanup(os.remove, handle.name)
        os.environ[cli.ENV_ARGFILE] = handle.name
        self.addCleanup(os.environ.pop, cli.ENV_ARGFILE, None)
        self.assertEqual(
            cli._script_args(["freecadcmd", "cli.py"]),
            ["run", "--tool", 'extrude {"a": 1}', "--save", "/x y/z.FCStd"],
        )

    def test_bad_tool_calls_are_a_bad_command_line(self):
        """Exit status 2 (bad command line) for a --tool or a --tools-file item that cannot
        be read, said before FreeCAD is even needed (review 2026-10-22, F6)."""
        import tempfile

        script = os.path.join(AI, "cli.py")
        done = subprocess.run(
            [sys.executable, script, "run", "--tool", "extrude {bad json"],
            capture_output=True,
            timeout=60,
        )
        self.assertEqual(done.returncode, 2)
        self.assertIn("not JSON", done.stderr.decode("utf-8"))
        for items, words in (
            ('[{"name": "extrude"}]', 'no "tool" name'),
            ('{"tool": "extrude"}', "must hold a list"),
            ('[{"tool": "extrude", "arguments": [1]}]', "must be a JSON object"),
            ("[{", "is not JSON"),
        ):
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
                handle.write(items)
            self.addCleanup(os.remove, handle.name)
            done = subprocess.run(
                [sys.executable, script, "run", "--tools-file", handle.name],
                capture_output=True,
                timeout=60,
            )
            self.assertEqual(done.returncode, 2, items)
            self.assertIn(words, done.stderr.decode("utf-8"), items)

    def test_close_design_names_its_design(self):
        """close_design with design names one: it runs with no active design (headless
        FreeCAD may have none after a close; review 2026-10-22, F4)."""
        self.assertEqual(catalog.tool("close_design")["needs"], ())
        state = {"gui": False, "design": False, "solid": False, "drawing": False}
        self.assertTrue(catalog.availability("close_design", state)[0])

    def test_needs_freecad_said_plainly(self):
        script = os.path.join(AI, "cli.py")
        done = subprocess.run(
            [sys.executable, script, "info", "x.FCStd"], capture_output=True, timeout=60
        )
        self.assertEqual(done.returncode, 2)
        self.assertIn("needs FreeCAD", done.stderr.decode("utf-8"))

    def test_mcp_headless_needs_freecad_said_plainly(self):
        script = os.path.join(AI, "sciforge_mcp.py")
        done = subprocess.run(
            [sys.executable, script, "--headless"], capture_output=True, input=b"", timeout=60
        )
        self.assertEqual(done.returncode, 2)
        self.assertIn("needs FreeCAD", done.stderr.decode("utf-8"))
        done = subprocess.run(
            [sys.executable, script, "--headless", "--bridge"],
            capture_output=True,
            input=b"",
            timeout=60,
        )
        self.assertEqual(done.returncode, 2)


if __name__ == "__main__":
    unittest.main()
