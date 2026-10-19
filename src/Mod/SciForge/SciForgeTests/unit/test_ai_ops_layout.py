# SPDX-License-Identifier: LGPL-2.1-or-later
"""Where the design steps live (sciforge/ai/ops/, shared by the golden models and the AI
tools): product code never imports the tests, every *_ops.py file is registered, the
golden models' checks stay with the tests. Runs without FreeCAD."""

import ast
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PACKAGE = os.path.join(ROOT, "sciforge")
OPS = os.path.join(PACKAGE, "ai", "ops")


def _tree(path):
    with open(path, encoding="utf-8") as handle:
        return ast.parse(handle.read(), path)


def _imports(tree):
    """Every module name an import in the file names (also imports inside functions)."""
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append("." * node.level + node.module)
        elif isinstance(node, ast.ImportFrom):  # from . import sketch_ops
            names += ["." * node.level + alias.name for alias in node.names]
    return names


def _python_files(folder):
    for here, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for name in files:
            if name.endswith(".py"):
                yield os.path.join(here, name)


class AiOpsLayout(unittest.TestCase):
    def test_product_code_never_imports_the_tests(self):
        bad = []
        for path in _python_files(PACKAGE):
            for name in _imports(_tree(path)):
                if name.split(".")[0] == "SciForgeTests":
                    bad.append("%s imports %s" % (os.path.relpath(path, ROOT), name))
        self.assertEqual(bad, [])

    def test_package_files_import_nothing(self):
        # sciforge.ai must be importable outside FreeCAD (the MCP server an AI app starts)
        for path in (os.path.join(PACKAGE, "ai", "__init__.py"), os.path.join(OPS, "__init__.py")):
            self.assertEqual(_imports(_tree(path)), [], path)

    def test_every_ops_file_is_registered_by_core(self):
        registered = {n[1:] for n in _imports(_tree(os.path.join(OPS, "core.py"))) if n[:1] == "."}
        on_disk = {name[:-3] for name in os.listdir(OPS) if name.endswith("_ops.py")}
        self.assertTrue(on_disk)
        self.assertEqual(on_disk - registered, set())

    def test_checks_stay_with_the_tests(self):
        found = []
        for path in _python_files(OPS):
            for node in ast.walk(_tree(path)):
                if isinstance(node, ast.FunctionDef) and node.name.startswith("op_"):
                    if "expect" in node.name or node.name in ("op_reopen_check", "op_age"):
                        found.append("%s: %s" % (os.path.basename(path), node.name))
        self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()
