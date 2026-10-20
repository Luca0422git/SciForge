# SPDX-License-Identifier: LGPL-2.1-or-later
"""The GitHub page's documents (README.md, CHANGELOG.md, known-issues, privacy, smartscreen) keep
working: every relative link and picture points at something that exists, and README.md still
carries docs/sciforge/smartscreen.md word for word (tools/sciforge/check_links.py does the work,
brief docs/sciforge/dev/briefs/beta-release.md, R1).

They read the repository and are skipped in an installed copy of the module (where there is no
repository).
"""

import importlib.util
import os
import shutil
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
SCRIPT = os.path.join(REPO, "tools", "sciforge", "check_links.py")


def _load():
    spec = importlib.util.spec_from_file_location("sciforge_check_links", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipUnless(
    os.path.isfile(SCRIPT) and os.path.isfile(os.path.join(REPO, "README.md")),
    "not inside the SciForge repository",
)
class TestRepositoryDocuments(unittest.TestCase):
    def test_every_link_in_the_user_facing_documents_resolves(self):
        problems = _load().check_all(REPO)
        self.assertEqual(problems, [], "\n".join(problems))

    def test_issue_forms_exist_and_blank_issues_are_off(self):
        folder = os.path.join(REPO, ".github", "ISSUE_TEMPLATE")
        for name in ("bug_report.yml", "idea.yml", "config.yml"):
            self.assertTrue(os.path.isfile(os.path.join(folder, name)), name)
        self.assertFalse(os.path.exists(os.path.join(folder, "PROBLEM_REPORT.yml")))
        with open(os.path.join(folder, "config.yml"), encoding="utf-8") as handle:
            self.assertIn("blank_issues_enabled: false", handle.read())
        with open(os.path.join(folder, "bug_report.yml"), encoding="utf-8") as handle:
            text = handle.read()
        # the Report a Problem dialog fills these fields through the address
        for field_id in ("what_happened", "expected", "steps", "diagnostics", "version", "system"):
            self.assertIn("id: %s\n" % field_id, text)

    def test_readme_credits_freecad_and_names_autodesk_correctly(self):
        with open(os.path.join(REPO, "README.md"), encoding="utf-8") as handle:
            text = " ".join(handle.read().split())  # (line breaks do not matter)
        self.assertIn("README.FreeCAD.md", text)
        self.assertIn("not affiliated with or endorsed by Autodesk", text)
        self.assertIn("Autodesk and Fusion are trademarks of Autodesk, Inc.", text)
        self.assertNotIn("Fusion-level", text)
        self.assertTrue(os.path.isfile(os.path.join(REPO, "README.FreeCAD.md")))


@unittest.skipUnless(os.path.isfile(SCRIPT), "not inside the SciForge repository")
class TestLinkChecker(unittest.TestCase):
    """The checker itself, on small made-up folders: it must find what it should find."""

    def setUp(self):
        self.mod = _load()
        self.dir = tempfile.mkdtemp(prefix="sciforge-links-")
        self.addCleanup(shutil.rmtree, self.dir, True)

    def write(self, rel, text):
        path = os.path.join(self.dir, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)

    def problems(self, rel):
        return self.mod.check_file(self.dir, rel)

    def test_good_links_pass(self):
        self.write("a.md", "# A\n\n## Two words\n")
        self.write("img/p.png", "x")
        self.write(
            "doc.md",
            "[a](a.md) [b](a.md#two-words) [c](img/p.png) [d](https://example.org/x)\n"
            '<img src="img/p.png"> [e](#top-heading) [f](/a.md)\n\n# Top heading\n',
        )
        self.assertEqual(self.problems("doc.md"), [])

    def test_missing_file_and_missing_heading_are_found(self):
        self.write("a.md", "# A\n")
        self.write("doc.md", "[x](nope.md)\n[y](a.md#not-there)\n<img src='gone.png'>\n[z](#none)\n")
        found = self.problems("doc.md")
        self.assertEqual(len(found), 4, found)
        self.assertTrue(any("nope.md" in line for line in found))
        self.assertTrue(any("#not-there" in line for line in found))
        self.assertTrue(any("gone.png" in line for line in found))

    def test_code_and_comments_are_not_links(self):
        self.write(
            "doc.md",
            "`[x](nope.md)`\n\n```\n[y](nope.md)\n```\n<!-- [z](nope.md)\n[w](nope.md) -->\nok\n",
        )
        self.assertEqual(self.problems("doc.md"), [])

    def test_a_folder_is_a_good_target(self):
        self.write("examples/one/README.md", "# One\n")
        self.write("doc.md", "[x](examples/one) [y](examples/one/README.md)\n")
        self.assertEqual(self.problems("doc.md"), [])

    def test_smartscreen_may_not_have_relative_links(self):
        self.write("docs/sciforge/smartscreen.md", "<!-- c -->\ntext [a](b.md) [c](https://x.org)\n")
        self.write("docs/sciforge/b.md", "# B\n")
        found = self.problems("docs/sciforge/smartscreen.md")
        self.assertEqual(len(found), 1, found)
        self.assertIn("relative link", found[0])

    def test_readme_must_carry_the_smartscreen_text(self):
        self.write("docs/sciforge/smartscreen.md", "<!-- note -->\n### Title\n\nBody text.\n")
        begin, end = self.mod.BEGIN, self.mod.END
        self.write("README.md", "# R\n%s\n### Title\n\nBody text.\n%s\n" % (begin, end))
        self.assertEqual(self.mod.check_smartscreen_in_readme(self.dir), [])
        self.write("README.md", "# R\n%s\n### Title\n\nBody text changed.\n%s\n" % (begin, end))
        self.assertEqual(len(self.mod.check_smartscreen_in_readme(self.dir)), 1)
        self.write("README.md", "# R\n")
        self.assertEqual(len(self.mod.check_smartscreen_in_readme(self.dir)), 1)

    def test_slug_follows_githubs_rule(self):
        self.assertEqual(self.mod.slug("Reporting problems and ideas"), "reporting-problems-and-ideas")
        self.assertEqual(self.mod.slug('"Windows protected your PC" (SciForge is not signed)'),
                         "windows-protected-your-pc-sciforge-is-not-signed")
        self.assertEqual(self.mod.slug("What works, and what does not yet"), "what-works-and-what-does-not-yet")


if __name__ == "__main__":
    unittest.main()
