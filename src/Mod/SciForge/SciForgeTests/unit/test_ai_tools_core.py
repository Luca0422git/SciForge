# SPDX-License-Identifier: LGPL-2.1-or-later
"""The first sixteen AI tools through sciforge/ai/tools_core.py (the names older code and
installed extensions import; the tools live in the catalogue, sciforge/ai/catalog, whose own
tests are in test_ai_catalog.py): well-formed schemas, plain-sentence validation, and design
steps in exactly the golden models' language (checked with the golden format checker and
against real model files). Runs without FreeCAD."""

import ast
import copy
import glob
import json
import os
import re
import sys
import unittest

# The module root (src/Mod/SciForge) holds the sciforge and SciForgeTests packages.
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from sciforge.ai import tools_core  # noqa: E402
from SciForgeTests.golden import schema  # noqa: E402

OPS = os.path.join(ROOT, "sciforge", "ai", "ops")
MODELS = os.path.join(ROOT, "SciForgeTests", "golden", "models")
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

TOP4 = {"type": "line", "at": {"axis": "z", "value": "max"}, "count": 4}
TOP_FACE = {"normal": [0, 0, 1], "count": 1}

VALID = {
    "get_design": {},
    "screenshot": {"view": "top", "width": 800, "height": 600},
    "measure": {"a": {"face": TOP_FACE}, "b": {"plane": "XY"}},
    "create_sketch": {"plane": "XY", "geometry": [{"rect": [0, 0, 40, 20], "name": "base"}]},
    "extrude": {"profile": "s1", "distance": 10},
    "revolve": {"profile": "s1", "axis": "Y", "angle": 90},
    "fillet": {"edges": TOP4, "radius": 3},
    "chamfer": {"edges": TOP4, "distance": 1, "angle": 30},
    "hole": {"sketch": "s2", "diameter": 6, "through_all": True},
    "pattern": {
        "kind": "rectangular",
        "features": ["c1"],
        "direction": "X",
        "count": 3,
        "spacing": 20,
    },
    "shell": {"faces": TOP_FACE, "thickness": 2},
    "set_parameter": {"name": "width", "value": "depth * 2", "unit": "mm"},
    "undo": {},
    "redo": {},
    "save": {"path": "/tmp/part.FCStd"},
    "export": {"format": "stl", "path": "/tmp/part.stl"},
}

EXPECT = {"volume": 1, "source": "analytic"}


def _walk(schema_obj, path, out):
    out.append((path, schema_obj))
    for key, sub in schema_obj.get("properties", {}).items():
        _walk(sub, path + "." + key, out)
    if "items" in schema_obj:
        _walk(schema_obj["items"], path + "[]", out)
    return out


def _op_names():
    """Every op_<name> the step builder has, read from the source (it needs FreeCAD)."""
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


def _model(steps):
    return {"id": "ai", "title": "AI steps", "steps": steps, "expect": dict(EXPECT)}


def _without_defaults(step):
    defaults = {"operation": "join", "direction": "inside"}
    return {k: v for k, v in step.items() if defaults.get(k, object()) != v}


class SchemaShape(unittest.TestCase):
    def test_every_tool_is_described(self):
        self.assertEqual(len(tools_core.TOOL_NAMES), len(set(tools_core.TOOL_NAMES)))
        for tool in tools_core.TOOLS:
            self.assertRegex(tool["name"], r"^[a-z][a-z_]*$")
            self.assertTrue(tool["title"].strip(), tool["name"])
            self.assertGreater(len(tool["description"]), 30, tool["name"])
            self.assertIsInstance(tool["changes_design"], bool)
            self.assertIsInstance(tool["writes_files"], bool)
            self.assertEqual(tool["input_schema"]["type"], "object")

    def test_the_brief_s_tools_are_all_there(self):
        wanted = (
            "get_design screenshot measure create_sketch extrude revolve fillet chamfer hole "
            "pattern shell set_parameter undo redo save export"
        ).split()
        # they keep their names, and come first (in the brief's order) in tools/list
        self.assertEqual(sorted(wanted), sorted(tools_core.TOOL_NAMES[:16]))
        read_only = {
            t["name"] for t in tools_core.TOOLS if not t["changes_design"] and t["name"] in wanted
        }
        self.assertEqual(read_only, {"get_design", "screenshot", "measure", "save", "export"})

    def test_schemas_use_only_the_supported_subset(self):
        for tool in tools_core.TOOLS:
            for path, node in _walk(tool["input_schema"], tool["name"], []):
                self.assertLessEqual(set(node), KEYWORDS, path)
                kinds = node.get("type", [])
                kinds = kinds if isinstance(kinds, list) else [kinds]
                self.assertLessEqual(set(kinds), TYPES, path)
                for key in node.get("required", []):
                    self.assertIn(key, node["properties"], path)
                if "enum" in node:
                    self.assertTrue(node["enum"], path)
                if "default" in node:
                    problems = []
                    tools_core._check(node, node["default"], path, problems)
                    self.assertEqual(problems, [], path)
            json.dumps(tool["input_schema"])

    def test_valid_examples_cover_every_tool_and_pass(self):
        self.assertEqual(list(VALID), list(tools_core.TOOL_NAMES[:16]))
        for name, args in VALID.items():
            self.assertEqual(tools_core.validate(name, args), [], name)

    def test_mcp_tools_shape(self):
        tools = tools_core.mcp_tools()
        self.assertEqual([t["name"] for t in tools], list(tools_core.TOOL_NAMES))
        for item, source in zip(tools, tools_core.TOOLS):
            self.assertEqual(
                set(item), {"name", "title", "description", "inputSchema", "annotations"}
            )
            self.assertEqual(item["inputSchema"], source["input_schema"])
            self.assertIsNot(item["inputSchema"], source["input_schema"])
            if item["name"] in VALID:  # none of the first sixteen destroys anything
                self.assertFalse(item["annotations"]["destructiveHint"])
        hints = {t["name"]: t["annotations"]["readOnlyHint"] for t in tools}
        self.assertTrue(hints["get_design"])
        self.assertTrue(hints["screenshot"])
        self.assertFalse(hints["extrude"])
        self.assertFalse(hints["export"])  # writes a file


class SelectorDocs(unittest.TestCase):
    def test_filters_match_selectors_py(self):
        with open(os.path.join(OPS, "selectors.py"), encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
        doc = ast.get_docstring(tree)
        listed = re.findall(r"^    ([a-z_]+) ", doc, re.M)
        self.assertEqual(tuple(listed), tools_core.SELECTOR_KEYS)
        for key in listed:
            self.assertIn("  %s:" % key, tools_core.SELECTOR_HELP)
        types = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
                if node.targets[0].id in ("_EDGE_TYPES", "_FACE_TYPES"):
                    types[node.targets[0].id] = set(ast.literal_eval(node.value).values())
        self.assertEqual(set(tools_core.EDGE_TYPES), types["_EDGE_TYPES"])
        self.assertEqual(set(tools_core.FACE_TYPES), types["_FACE_TYPES"])

    def test_readme_examples_are_in_the_help(self):
        with open(
            os.path.join(ROOT, "SciForgeTests", "golden", "README.md"), encoding="utf-8"
        ) as f:
            readme = f.read()
        block = readme.split("### Selectors", 1)[1].split("```json", 1)[1].split("```", 1)[0]
        text = " ".join(line.split("//")[0].strip() for line in block.strip().splitlines())
        decoder, examples, at = json.JSONDecoder(), [], 0
        while at < len(text):
            example, end = decoder.raw_decode(text, at)
            examples.append(example)
            at = end + 1
        self.assertEqual(len(examples), 3)
        for example in examples:
            self.assertIn(json.dumps(example), tools_core.SELECTOR_HELP)
            if "normal" in example:
                args = {"faces": example, "thickness": 1}
                self.assertEqual(tools_core.validate("shell", args), [])
            else:
                self.assertEqual(tools_core.validate("fillet", {"edges": example, "radius": 1}), [])


class Validation(unittest.TestCase):
    def problems(self, name, args):
        return tools_core.validate(name, args)

    def test_unknown_tool(self):
        problems = self.problems("delete_everything", {})
        self.assertEqual(len(problems), 1)
        self.assertIn("no tool called", problems[0])

    def test_wrong_types(self):
        self.assertIn("radius must be a number", self.problems("fillet", {"radius": "3"}))
        self.assertIn("radius must be a number", self.problems("fillet", {"radius": True}))
        self.assertIn("the arguments must be an object", self.problems("fillet", ["radius", 3]))
        self.assertIn(
            "count must be a whole number",
            self.problems("pattern", dict(VALID["pattern"], count=2.5)),
        )
        self.assertEqual(self.problems("pattern", dict(VALID["pattern"], count=3.0)), [])

    def test_missing_required(self):
        self.assertIn("radius is missing", self.problems("fillet", {"edges": TOP4}))
        self.assertIn("geometry is missing", self.problems("create_sketch", {"plane": "XY"}))
        self.assertIn("a is missing", self.problems("measure", {"b": {"origin": True}}))

    def test_out_of_range(self):
        self.assertEqual(
            self.problems("fillet", {"edges": TOP4, "radius": 0}),
            ["radius must be a number above 0"],
        )
        self.assertIn("width must be at most 4096", self.problems("screenshot", {"width": 10000}))
        self.assertIn(
            "angle must be at most 360", self.problems("revolve", dict(VALID["revolve"], angle=400))
        )
        self.assertIn(
            "view must be one of: iso, front, back, top, bottom, left, right",
            self.problems("screenshot", {"view": "side"}),
        )

    def test_unknown_argument(self):
        self.assertIn(
            "colour is not a known argument",
            self.problems("extrude", dict(VALID["extrude"], colour="red")),
        )

    def test_nested_paths(self):
        problems = self.problems(
            "create_sketch",
            {"plane": "XY", "geometry": [{"rect": [0, 0, 1, 1]}, {"circle": [0, 0]}]},
        )
        self.assertEqual(problems, ["geometry[1].circle must have exactly 3 items"])

    def test_sketch_rules(self):
        both = {"plane": "XY", "face": TOP_FACE, "geometry": [{"circle": [0, 0, 1]}]}
        self.assertTrue(any("not both" in p for p in self.problems("create_sketch", both)))
        two = {"plane": "XY", "geometry": [{"circle": [0, 0, 1], "rect": [0, 0, 1, 1]}]}
        self.assertTrue(any("exactly one of" in p for p in self.problems("create_sketch", two)))
        flat = {"plane": "XY", "geometry": [{"rect": [0, 0, 0, 5]}]}
        self.assertTrue(any("no area" in p for p in self.problems("create_sketch", flat)))
        zero = {"plane": "XY", "geometry": [{"circle": [0, 0, 0]}]}
        self.assertTrue(any("above 0" in p for p in self.problems("create_sketch", zero)))

    def test_extrude_rules(self):
        self.assertIn(
            "distance is missing (or set through_all to true)",
            self.problems("extrude", {"profile": "s1"}),
        )
        self.assertEqual(self.problems("extrude", {"profile": "s1", "through_all": True}), [])
        self.assertTrue(
            self.problems("extrude", {"profile": "s1", "distance": 5, "direction": "two_sides"})
        )
        self.assertTrue(self.problems("extrude", {"profile": "s1", "distance": 5, "distance2": 3}))

    def test_selector_rules(self):
        def fillet(edges):
            return self.problems("fillet", {"edges": edges, "radius": 1})

        self.assertTrue(any("not a known argument" in p for p in fillet({"colour": "red"})))
        self.assertTrue(any("type must be one of" in p for p in fillet({"type": "plane"})))
        self.assertTrue(any("only applies to faces" in p for p in fillet({"normal": [0, 0, 1]})))
        self.assertTrue(any("[0, 0, 0]" in p for p in fillet({"parallel": [0, 0, 0]})))
        self.assertTrue(
            any("axis must be x, y or z" in p for p in fillet({"at": {"axis": "w", "value": 1}}))
        )
        self.assertTrue(fillet({"all": True, "type": "line"}))
        nested = {"on_faces": {"normal": [0, 0, 1], "colour": 1}, "count": 4}
        self.assertTrue(any("on_faces.colour" in p for p in fillet(nested)))
        self.assertTrue(any("any_of[1]" in p for p in fillet({"any_of": [TOP4, {"type": "x"}]})))
        self.assertEqual(fillet({"on_faces": TOP_FACE, "count": 4}), [])
        self.assertEqual(
            fillet({"at": [{"axis": "X", "value": 5}, {"axis": "z", "value": "max"}]}), []
        )
        shell = self.problems("shell", {"faces": {"type": "line"}, "thickness": 1})
        self.assertTrue(any("for faces" in p for p in shell))

    def test_other_rules(self):
        self.assertTrue(self.problems("fillet", {"radius": 1}))  # nothing picked
        self.assertTrue(
            self.problems("chamfer", {"edges": TOP4, "distance": 1, "distance2": 2, "angle": 30})
        )
        self.assertTrue(self.problems("hole", {"sketch": "s2", "diameter": 6}))
        self.assertTrue(
            self.problems("hole", {"sketch": "s2", "diameter": 6, "depth": 3, "through_all": True})
        )
        small = {
            "sketch": "s2",
            "diameter": 6,
            "depth": 3,
            "counterbore": {"diameter": 5, "depth": 1},
        }
        self.assertTrue(any("bigger" in p for p in self.problems("hole", small)))
        self.assertTrue(
            self.problems("pattern", {"kind": "rectangular", "features": ["c1"], "count": 3})
        )
        self.assertTrue(
            self.problems("pattern", {"kind": "circular", "features": ["c1"], "count": 3})
        )
        mixed = dict(VALID["pattern"], axis="Z")
        self.assertTrue(any("circular" in p for p in self.problems("pattern", mixed)))
        self.assertTrue(self.problems("set_parameter", {"name": "2wide", "value": 3}))
        self.assertTrue(self.problems("save", {"path": "/tmp/part.step"}))
        self.assertTrue(self.problems("export", {"format": "step", "path": "/tmp/part.stl"}))
        self.assertEqual(self.problems("export", {"format": "step", "path": "/tmp/a.STP"}), [])
        self.assertTrue(
            self.problems("measure", {"a": {"plane": "XY", "axis": "Z"}, "b": {"origin": True}})
        )


class Steps(unittest.TestCase):
    def steps(self, calls):
        """Run (tool, args, id) calls through validate and to_steps."""
        steps = []
        for name, args, step_id in calls:
            self.assertEqual(tools_core.validate(name, args), [], name)
            steps += tools_core.to_steps(name, args, step_id)
        return steps

    def test_non_step_tools_make_no_steps(self):
        for name in ("get_design", "screenshot", "measure", "undo", "redo", "save", "export"):
            self.assertEqual(tools_core.to_steps(name, VALID[name], "x1"), [])
        with self.assertRaises(ValueError):
            tools_core.to_steps("nope", {}, "x1")

    def test_every_step_passes_the_golden_format_checker(self):
        sketch_top = {"plane": "XY", "offset": 10, "geometry": [{"circle": [20, 15, 1]}]}
        calls = [
            ("set_parameter", {"name": "width", "value": 40, "unit": "mm"}, "unused"),
            ("create_sketch", VALID["create_sketch"], "s1"),
            ("extrude", {"profile": "s1", "distance": 10, "taper": 2}, "e1"),
            ("fillet", VALID["fillet"], "f1"),
            ("chamfer", {"edges": TOP4, "distance": 1, "distance2": 2, "flip": True}, "c0"),
            ("chamfer", {"features": ["e1"], "distance": 1}, "c00"),
            ("create_sketch", sketch_top, "s2"),
            (
                "hole",
                {"sketch": "s2", "diameter": 3, "depth": 4, "countersink": {"diameter": 6}},
                "h1",
            ),
            (
                "extrude",
                {
                    "profile": "s2",
                    "through_all": True,
                    "operation": "cut",
                    "flip": True,
                    "regions": [[20, 15]],
                },
                "c1",
            ),
            ("pattern", dict(VALID["pattern"], direction2="Y", count2=2, spacing2=5), "p1"),
            (
                "pattern",
                {"kind": "circular", "features": ["c1"], "axis": "Z", "count": 4, "angle": 90},
                "p2",
            ),
            ("shell", {"faces": TOP_FACE, "thickness": 1, "direction": "outside"}, "sh1"),
            (
                "create_sketch",
                {
                    "face": {"normal": [0, 0, -1], "count": 1},
                    "geometry": [
                        {"slot": [5, 5, 15, 5, 3]},
                        {"polygon": {"center": [30, 10], "radius": 4, "sides": 6.0}},
                        {"polyline": [[0, 0], [5, 0], [0, 5]]},
                        {"center_rect": [20, 10, 4, 4]},
                        {"line": [0, 0, 1, 1]},
                    ],
                },
                "s3",
            ),
            (
                "extrude",
                {
                    "profile": "s3",
                    "distance": 4,
                    "direction": "two_sides",
                    "distance2": 2,
                    "operation": "new_body",
                },
                "e3",
            ),
            ("create_sketch", {"plane": "XZ", "geometry": [{"rect": [10, 0, 20, 5]}]}, "s4"),
            ("revolve", {"profile": "s4", "axis": "Z"}, "r1"),
            (
                "revolve",
                {
                    "profile": "s4",
                    "axis": "sketch_v",
                    "angle": 90,
                    "operation": "new_body",
                    "regions": [[15, 2]],
                },
                "r2",
            ),
            (
                "extrude",
                {
                    "profile": "s4",
                    "distance": 6,
                    "direction": "symmetric",
                    "operation": "intersect",
                },
                "e4",
            ),
        ]
        steps = self.steps(calls)
        self.assertEqual(len(steps), len(calls))
        schema.validate(_model(steps))
        self.assertTrue(isinstance(steps[12]["geometry"][1]["polygon"]["sides"], int))

    def test_emitted_ops_exist_in_the_builder(self):
        builder_ops = _op_names()
        self.assertIn("sketch", builder_ops)  # the source scan works
        emitted = set()
        for name, args in VALID.items():
            emitted |= {s["op"] for s in tools_core.to_steps(name, args, "x1")}
        emitted |= {
            s["op"]
            for s in tools_core.to_steps(
                "pattern", {"kind": "circular", "features": ["c1"], "axis": "Z", "count": 3}, "x"
            )
        }
        self.assertEqual(
            emitted,
            {
                "sketch",
                "extrude",
                "sf_revolve",
                "blend_fillet",
                "blend_chamfer",
                "hole",
                "pattern_rect",
                "pattern_circ",
                "shell",
                "parameter",
            },
        )
        self.assertLessEqual(emitted, builder_ops)
        used = set()
        for path in glob.glob(os.path.join(MODELS, "*.json")):
            with open(path, encoding="utf-8") as handle:
                used |= {step["op"] for step in json.load(handle)["steps"]}
        self.assertLessEqual(emitted, used)  # every op is proven by some golden model

    def _model_steps(self, name):
        with open(os.path.join(MODELS, name + ".json"), encoding="utf-8") as handle:
            return json.load(handle)["steps"]

    def assertSameSteps(self, ours, theirs):
        self.assertEqual([_without_defaults(s) for s in ours], theirs)

    def test_reproduces_plate_hole_grid(self):
        ours = self.steps(
            [
                (
                    "create_sketch",
                    {"plane": "XY", "geometry": [{"rect": [0, 0, 60, 40], "name": "plate"}]},
                    "s1",
                ),
                ("extrude", {"profile": "s1", "distance": 5}, "e1"),
                (
                    "create_sketch",
                    {
                        "plane": "XY",
                        "offset": 5,
                        "geometry": [{"circle": [10, 10, 3], "name": "hole"}],
                    },
                    "s2",
                ),
                (
                    "extrude",
                    {"profile": "s2", "operation": "cut", "through_all": True, "flip": True},
                    "c1",
                ),
                (
                    "pattern",
                    {
                        "kind": "rectangular",
                        "features": ["c1"],
                        "direction": "X",
                        "count": 3,
                        "spacing": 20,
                        "direction2": "Y",
                        "count2": 2,
                        "spacing2": 20,
                    },
                    "p1",
                ),
            ]
        )
        self.assertSameSteps(ours, self._model_steps("plate_hole_grid"))

    def test_reproduces_hole_counterbore_and_flange(self):
        theirs = self._model_steps("hole_counterbore")
        ours = self.steps(
            [
                (
                    "create_sketch",
                    {"plane": "XY", "geometry": [{"rect": [0, 0, 40, 40], "name": "plate"}]},
                    "s1",
                ),
                ("extrude", {"profile": "s1", "distance": 10}, "e1"),
                (
                    "create_sketch",
                    {
                        "plane": "XY",
                        "offset": 10,
                        "geometry": [{"circle": [20, 20, 1], "name": "pt"}],
                    },
                    "s2",
                ),
                (
                    "hole",
                    {
                        "sketch": "s2",
                        "diameter": 6.6,
                        "through_all": True,
                        "counterbore": {"diameter": 11, "depth": 6.5},
                    },
                    "h1",
                ),
            ]
        )
        self.assertEqual([_without_defaults(s) for s in ours][3], theirs[3])
        self.assertEqual(ours[2]["geometry"], theirs[2]["geometry"])
        flange = self._model_steps("flange_polar_holes")
        circ = tools_core.to_steps(
            "pattern", {"kind": "circular", "features": ["c1"], "axis": "Z", "count": 6}, "p1"
        )
        self.assertEqual(circ, [flange[-1]])

    def test_reproduces_shell_and_chamfer(self):
        theirs = self._model_steps("shell_open_box")[2]
        ours = tools_core.to_steps("shell", {"thickness": 2, "faces": TOP_FACE}, "sh1")
        self.assertEqual([_without_defaults(s) for s in ours], [theirs])
        theirs = self._model_steps("blend_chamfer_angle")[2]
        args = {"distance": 3, "angle": 30, "edges": copy.deepcopy(theirs["edges"])}
        self.assertEqual(tools_core.to_steps("chamfer", args, "c1"), [theirs])

    def test_parameter_step_has_no_id(self):
        steps = tools_core.to_steps("set_parameter", {"name": "w", "value": "d / 4"}, "x")
        self.assertEqual(steps, [{"op": "parameter", "name": "w", "value": "d / 4"}])

    def test_arguments_are_copied(self):
        args = copy.deepcopy(VALID["fillet"])
        step = tools_core.to_steps("fillet", args, "f1")[0]
        step["edges"]["count"] = 99
        self.assertEqual(args["edges"]["count"], 4)


class Titles(unittest.TestCase):
    def test_titles(self):
        title = tools_core.step_title
        self.assertEqual(title("extrude", {"profile": "s1", "distance": 10}), "AI: Extrude 10 mm")
        self.assertEqual(title("extrude", {"through_all": True}), "AI: Extrude through all")
        self.assertEqual(title("fillet", {"radius": 3}), "AI: Fillet 3 mm")
        self.assertEqual(title("chamfer", {"distance": 0.5}), "AI: Chamfer 0.5 mm")
        self.assertEqual(title("create_sketch", {"plane": "XZ"}), "AI: Sketch on XZ")
        self.assertEqual(title("revolve", {"angle": 90}), "AI: Revolve 90 degrees")
        self.assertEqual(
            title("pattern", {"kind": "circular", "count": 6}), "AI: Circular pattern x6"
        )
        self.assertEqual(title("set_parameter", {"name": "w", "value": 5}), "AI: Parameter w = 5")
        self.assertEqual(title("undo", {}), "AI: Undo")
        self.assertEqual(title("fillet", None), "AI: Fillet")
        for name in tools_core.TOOL_NAMES:
            args = VALID.get(name) or tools_core.tool(name)["examples"][0]["arguments"]
            self.assertTrue(title(name, args).startswith("AI: "), name)


if __name__ == "__main__":
    unittest.main()
