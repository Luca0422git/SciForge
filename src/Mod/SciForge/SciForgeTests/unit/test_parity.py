# SPDX-License-Identifier: LGPL-2.1-or-later
"""tools/sciforge/parity.py: the script that measures Fusion parity by comparing Fusion's command
tree (tools/sciforge/data/fusion-menus.txt, by name) with SciForge's real menus and writes
docs/sciforge/parity-checklist.md (idea 5 of docs/sciforge/dev/cadcraft-lessons.md).

The parser and matcher are tested on small made-up inputs; the rest reads the repository (the
real menus, the real lists, and --check: the checklist must be up to date) and is skipped in an
installed copy of the module, where there is no repository.
"""

import contextlib
import importlib.util
import io
import os
import shutil
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
SCRIPT = os.path.join(REPO, "tools", "sciforge", "parity.py")
IN_REPO = os.path.isfile(SCRIPT) and os.path.isfile(
    os.path.join(REPO, "tools", "sciforge", "data", "fusion-menus.txt")
)


def _load():
    spec = importlib.util.spec_from_file_location("sciforge_parity", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


parity = _load() if os.path.isfile(SCRIPT) else None

SAMPLE = """
# a comment
SOLID [in=tab:solid]
  CREATE
    Extrude
    Pattern
      Rectangular Pattern
      Circular Pattern?
    Create Form [out=sculpting]
  MODIFY
    Fillet
SURFACE [in=tab:surface]
  MODIFY
    Fillet
    Trim
MARKING MENU [in=marking]
  Measure
BROWSER [in=browser]
  Body [in=browser:body]
    Isolate
"""


def _run(*args):
    """main(args) with its printing captured: (exit code, printed text)."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = parity.main(list(args))
    return code, out.getvalue()


@unittest.skipUnless(parity is not None, "tools/sciforge/parity.py not found")
class TestParseMenus(unittest.TestCase):
    def test_only_lines_without_children_are_commands(self):
        items = parity.parse_menus(SAMPLE)
        names = [i.name for i in items]
        self.assertEqual(
            names,
            [
                "Extrude",
                "Rectangular Pattern",
                "Circular Pattern",
                "Create Form",
                "Fillet",
                "Fillet",
                "Trim",
                "Measure",
                "Isolate",
            ],
        )
        self.assertNotIn("Pattern", names)  # a submenu heading
        self.assertNotIn("CREATE", names)  # a panel

    def test_paths_scopes_and_out_are_inherited(self):
        items = {i.path: i for i in parity.parse_menus(SAMPLE)}
        rect = items[("SOLID", "CREATE", "Pattern", "Rectangular Pattern")]
        self.assertEqual(rect.scopes, ("tab:solid",))
        self.assertIsNone(rect.out)
        self.assertEqual(items[("SOLID", "CREATE", "Create Form")].out, "sculpting")
        self.assertEqual(items[("BROWSER", "Body", "Isolate")].scopes, ("browser:body",))
        self.assertEqual(items[("MARKING MENU", "Measure")].scopes, ("marking",))

    def test_question_mark_marks_a_name_not_sure(self):
        items = {i.name: i for i in parity.parse_menus(SAMPLE)}
        self.assertTrue(items["Circular Pattern"].unsure)
        self.assertFalse(items["Extrude"].unsure)

    def test_malformed_lines_are_refused_with_their_line(self):
        bad = {
            "odd indent": "A [in=x]\n   B\n",
            "tab": "A [in=x]\n\tB\n",
            "jump": "A [in=x]\n    B\n",
            "no scope": "A\n  B\n",
            "lone area": "A [in=x]\n",
            "unknown attribute": "A [in=x]\n  B [where=y]\n",
        }
        for why, text in bad.items():
            with self.assertRaises(ValueError, msg=why) as caught:
                parity.parse_menus(text)
            self.assertIn("line", str(caught.exception), why)


@unittest.skipUnless(parity is not None, "tools/sciforge/parity.py not found")
class TestNamesAndAliases(unittest.TestCase):
    def test_norm_ignores_case_spaces_dots_and_question_marks(self):
        self.assertEqual(parity.norm("Move / Copy"), parity.norm("move/copy"))
        self.assertEqual(parity.norm("Hardware..."), "hardware")
        self.assertEqual(parity.norm("Hardware…"), "hardware")
        self.assertEqual(parity.norm("  Select   Other? "), "select other")

    def test_aliases_plain_and_qualified(self):
        aliases = parity.parse_aliases(
            "# c\nActivate Component = Activate\nMARKING MENU > Show/Hide = Hide | Show\n"
        )
        item = parity.FusionItem(
            ("BROWSER", "Body", "Activate Component"),
            "Activate Component",
            False,
            ("browser",),
            None,
            1,
        )
        self.assertEqual(parity.alias_targets(item, aliases), ["Activate"])
        marking = parity.FusionItem(
            ("MARKING MENU", "Show/Hide"), "Show/Hide", False, ("marking",), None, 1
        )
        browser = parity.FusionItem(
            ("BROWSER", "Body", "Show/Hide"), "Show/Hide", False, ("browser",), None, 1
        )
        self.assertEqual(parity.alias_targets(marking, aliases), ["Hide", "Show"])
        self.assertEqual(parity.alias_targets(browser, aliases), [])

    def test_bad_alias_lines_are_refused(self):
        for text in ("no equals sign", "a = b = c", " = b", "a = "):
            with self.assertRaises(ValueError, msg=text):
                parity.parse_aliases(text)


@unittest.skipUnless(parity is not None, "tools/sciforge/parity.py not found")
class TestMatching(unittest.TestCase):
    def setUp(self):
        E = parity.Entry
        self.entries = [
            E("tab:solid", ("SOLID", "CREATE", "Extrude"), "Extrude", True),
            E("tab:solid", ("SOLID", "CREATE", "Rectangular Pattern"), "Rectangular Pattern", True),
            E("tab:solid", ("SOLID", "CREATE", "Circular Pattern"), "Circular Pattern", False),
            E("tab:solid", ("SOLID", "MODIFY", "Fillet"), "Fillet", True),
            E("tab:solid", ("SOLID", "INSPECT", "Measure"), "Measure", True),
            E("tab:surface", ("SURFACE", "MODIFY", "Trim"), "Trim", True),
            E("browser:component", ("Browser", "component", "Isolate"), "Isolate", True),
        ]
        self.results = {
            r.item.path: r for r in parity.compare(parity.parse_menus(SAMPLE), self.entries, [])
        }

    def status(self, *path):
        return self.results[path].status

    def test_present_in_its_own_place(self):
        self.assertEqual(self.status("SOLID", "CREATE", "Extrude"), "present")
        self.assertEqual(self.status("SURFACE", "MODIFY", "Trim"), "present")

    def test_a_greyed_entry_is_not_present(self):
        self.assertEqual(self.status("SOLID", "CREATE", "Pattern", "Circular Pattern"), "greyed")

    def test_ribbon_tabs_may_borrow_from_each_other(self):
        result = self.results[("SURFACE", "MODIFY", "Fillet")]
        self.assertEqual(result.status, "elsewhere")
        self.assertEqual(result.where.path, ("SOLID", "MODIFY", "Fillet"))

    def test_context_menus_never_borrow_from_the_ribbon(self):
        self.assertEqual(self.status("MARKING MENU", "Measure"), "missing")
        # Isolate exists for components, not in the body's menu
        self.assertEqual(self.status("BROWSER", "Body", "Isolate"), "missing")

    def test_out_of_scope_entries_are_out_not_missing(self):
        self.assertEqual(self.status("SOLID", "CREATE", "Create Form"), "out")

    def test_an_alias_finds_the_sciforge_name(self):
        items = parity.parse_menus("SOLID [in=tab:solid]\n  INSPECT\n    Measure Tool\n")
        aliases = parity.parse_aliases("Measure Tool = Measure")
        (result,) = parity.compare(items, self.entries, aliases)
        self.assertEqual(result.status, "present")
        (result,) = parity.compare(items, self.entries, [])
        self.assertEqual(result.status, "missing")

    def test_render_has_the_header_headline_table_and_lists(self):
        text = parity.render(list(self.results.values()), self.entries, "2026-01-02")
        self.assertIn(
            "Generated by tools/sciforge/parity.py on 2026-01-02; do not edit by hand.", text
        )
        # Extrude, Rectangular Pattern, both Fillets (SURFACE's found on SOLID) and Trim
        self.assertIn("**Fusion commands present: 5 / 9 (55.6%)**", text)
        self.assertIn("**5 / 8 (62.5%)**", text)  # without the entry left out on purpose
        self.assertIn("presence (breadth), not depth", text)
        self.assertIn("| **SOLID** | all | **5** | **3** | **60.0%** |", text)
        self.assertIn("| | CREATE | 4 | 2 | 50.0% |", text)
        self.assertIn("## Not in SciForge yet", text)
        self.assertIn("- CREATE > Pattern > Circular Pattern (greyed, not sure)", text)
        self.assertIn("- SURFACE > MODIFY > Fillet: SOLID > MODIFY > Fillet", text)
        self.assertIn("- sculpting (1 entries, 0 present): SOLID > CREATE > Create Form", text)

    def test_another_panel_of_the_tab_is_elsewhere_and_shared_entries_are_listed(self):
        # Fusion's CREATE > New Component is SciForge's ASSEMBLE > New Component: counted, but
        # listed where it is; ASSEMBLE > Joint Origin is found in its own panel first
        E = parity.Entry
        entries = [
            E("tab:solid", ("SOLID", "CREATE", "Joint Origin"), "Joint Origin", True),
            E("tab:solid", ("SOLID", "ASSEMBLE", "New Component"), "New Component", True),
            E("tab:solid", ("SOLID", "ASSEMBLE", "Joint Origin"), "Joint Origin", True),
        ]
        items = parity.parse_menus(
            "SOLID [in=tab:solid]\n  CREATE\n    New Component\n"
            "  ASSEMBLE\n    New Component\n    Joint Origin\n"
        )
        results = parity.compare(items, entries, [])
        found = {r.item.path: (r.status, r.where.path) for r in results}
        self.assertEqual(
            found[("SOLID", "CREATE", "New Component")],
            ("elsewhere", ("SOLID", "ASSEMBLE", "New Component")),
        )
        self.assertEqual(
            found[("SOLID", "ASSEMBLE", "New Component")],
            ("present", ("SOLID", "ASSEMBLE", "New Component")),
        )
        self.assertEqual(
            found[("SOLID", "ASSEMBLE", "Joint Origin")],
            ("present", ("SOLID", "ASSEMBLE", "Joint Origin")),
        )
        text = parity.render(results, entries, "2026-01-02")
        self.assertIn("- SOLID > CREATE > New Component: SOLID > ASSEMBLE > New Component\n", text)
        self.assertIn("## One SciForge entry for several Fusion entries", text)
        self.assertIn(
            "- SOLID > ASSEMBLE > New Component: SOLID > CREATE > New Component; "
            "SOLID > ASSEMBLE > New Component\n",
            text,
        )

    def test_a_byte_order_mark_is_ignored(self):
        # Windows Notepad's "UTF-8 with BOM": the first line is still a comment
        folder = tempfile.mkdtemp(prefix="sciforge-parity-")
        self.addCleanup(shutil.rmtree, folder, True)
        with open(os.path.join(folder, "menus.txt"), "wb") as handle:
            handle.write(b"\xef\xbb\xbf" + SAMPLE.lstrip("\n").encode("utf-8"))
        text = parity._read(folder, "menus.txt")
        self.assertEqual(parity.parse_menus(text), parity.parse_menus(SAMPLE.lstrip("\n")))

    def test_only_the_date_may_differ_for_check(self):
        text = parity.render(list(self.results.values()), self.entries, "2026-01-02")
        later = parity.render(list(self.results.values()), self.entries, "2027-05-06")
        self.assertTrue(parity.same_checklist(text, later))
        self.assertTrue(parity.same_checklist(text.replace("\n", "\r\n"), later))
        self.assertFalse(parity.same_checklist(text, later.replace("55.6%", "56.0%")))


@unittest.skipUnless(IN_REPO, "not inside the SciForge repository")
class TestRealMenus(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.entries = parity.sciforge_catalogue(REPO)
        with open(os.path.join(REPO, parity.MENUS_FILE), encoding="utf-8") as handle:
            cls.items = parity.parse_menus(handle.read())
        with open(os.path.join(REPO, parity.ALIASES_FILE), encoding="utf-8") as handle:
            cls.aliases = parity.parse_aliases(handle.read())

    def has(self, scope, label, available=True):
        return any(
            e.scope == scope and e.label == label and e.available == available for e in self.entries
        )

    def test_every_sciforge_menu_is_read(self):
        # one entry of each source, so a refactor that breaks the static reading is noticed
        expected = [
            ("tab:solid", "Extrude"),
            ("tab:sketch", "Sketch Dimension"),
            ("tab:drawing", "Base View"),
            ("file", "New Design"),
            ("quick", "Data Panel"),
            ("nav", "Free Orbit"),
            ("marking", "Press Pull"),
            ("marking", "OK"),
            ("sketch-marking", "Finish Sketch"),
            ("sketch-marking", "Cancel"),
            ("browser:body", "Isolate"),
            ("browser:document", "Capture Design History"),
            ("timeline:step", "Roll History Marker Here"),
            ("timeline:step", "Edit Feature"),
            ("timeline:step", "Suppress Features"),
            ("timeline:step", "Unsuppress Features"),
            ("timeline:step", "Update Derive"),
            ("timeline:group", "Ungroup"),
            ("timeline:settings", "Expand All Groups"),
            ("timeline:playback", "Go to beginning"),
            ("viewcube", "Go Home"),
            ("viewcube", "Perspective with Ortho Faces"),
            ("viewcube", "Fixed Distance"),
            ("workspace", "Design"),
            ("workspace", "From Design..."),
            ("sheets", "New Sheet"),
            ("sheets", "Move Right"),
        ]
        missing = [pair for pair in expected if not self.has(*pair)]
        self.assertEqual(missing, [])

    def test_greyed_ribbon_entries_are_read_as_not_available(self):
        self.assertTrue(self.has("tab:drawing", "Export DWG", available=False))
        self.assertFalse(self.has("tab:drawing", "Export DWG", available=True))

    def test_every_fusion_scope_names_a_sciforge_place_or_an_area_left_out(self):
        scopes = {e.scope for e in self.entries}
        unknown = []
        for item in self.items:
            for scope in item.scopes:
                known = any(s == scope or s.startswith(scope + ":") for s in scopes)
                if not known and not item.out:
                    unknown.append("line %d: %s" % (item.line, scope))
        self.assertEqual(unknown, [])

    def test_every_alias_still_matches_a_fusion_name_and_a_sciforge_label(self):
        labels = {parity.norm(e.label) for e in self.entries}
        stale = []
        for key, targets in self.aliases:
            used = any(parity.alias_targets(item, [(key, targets)]) for item in self.items)
            if not used:
                stale.append("no Fusion name: %s" % " > ".join(key))
            for target in targets:
                if parity.norm(target) not in labels:
                    stale.append("no SciForge label: %s" % target)
        self.assertEqual(stale, [])

    # Names a row of remaining-gaps.md uses for a checklist entry (its words differ)
    GAP_WORDS = {
        "show/hide data panel": "view submenu",
        "show/hide browser": "view submenu",
        "show/hide text commands": "view submenu",
        "show/hide navigation bar": "view submenu",
        "show/hide viewcube": "view submenu",
        "show/hide timeline": "view submenu",
        "select component priority": "component priority",
        "components": "selection filters > components",
    }

    def test_every_missing_entry_is_on_the_work_list(self):
        # remaining-gaps.md is the one work list: an entry of the checklist's "Not in SciForge
        # yet" (missing or greyed, not left out on purpose) that no row names is never worked on
        with open(os.path.join(REPO, "docs", "sciforge", "dev", "remaining-gaps.md"), encoding="utf-8") as handle:
            gaps = parity.norm(handle.read().replace("\n", " "))
        forgotten = []
        for result in parity.compare(self.items, self.entries, self.aliases):
            if result.item.out or result.status in parity.PRESENT:
                continue
            name = parity.norm(result.item.name)
            if name not in gaps and self.GAP_WORDS.get(name, "\0") not in gaps:
                forgotten.append(" > ".join(result.item.path))
        self.assertEqual(forgotten, [], "add them to docs/sciforge/dev/remaining-gaps.md")

    def test_core_workflows_names_only_open_gaps(self):
        # a gap closed on the work list must not stay "missing" on the workflow page
        # (2026-10-22: workflow 1 still listed G-03 and G-06 after they were closed)
        import re

        dev = os.path.join(REPO, "docs", "sciforge", "dev")
        with open(os.path.join(dev, "remaining-gaps.md"), encoding="utf-8") as handle:
            gaps = handle.read()
        with open(os.path.join(dev, "core-workflows.md"), encoding="utf-8") as handle:
            page = handle.read()
        open_ids = set(re.findall(r"^\|(?: *\d+ *\|)? *(G-\d+) *\|", gaps, re.M))
        self.assertGreater(len(open_ids), 50)
        named = set(re.findall(r"\bG-\d+\b", page))
        self.assertEqual(sorted(named - open_ids), [], "closed or unknown gaps named")

    def test_the_numbers_add_up(self):
        results = parity.compare(self.items, self.entries, self.aliases)
        self.assertEqual(len(results), len(self.items))
        self.assertGreater(len(results), 400)  # Fusion's tree is big; a truncated file shows
        statuses = {r.status for r in results}
        self.assertLessEqual(statuses, {"present", "elsewhere", "greyed", "missing", "out"})
        # the core modelling commands are found (a parsing slip would drop them)
        present = {r.item.path for r in results if r.status == "present"}
        for path in (
            ("SOLID", "CREATE", "Extrude"),
            ("SOLID", "MODIFY", "Press Pull"),
            ("SKETCH", "CREATE", "Line"),
            ("TIMELINE", "Feature", "Roll History Marker Here"),
        ):
            self.assertIn(path, present)


@unittest.skipUnless(IN_REPO, "not inside the SciForge repository")
class TestCheckMode(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp(prefix="sciforge-parity-")
        self.addCleanup(shutil.rmtree, self.folder, True)
        self.out = os.path.join(self.folder, "checklist.md")

    def test_the_committed_checklist_is_up_to_date(self):
        code, printed = _run("--check")
        self.assertEqual(code, 0, printed + " (run python3 tools/sciforge/parity.py)")
        self.assertIn("[SciForge]", printed)

    def test_check_passes_after_writing_and_fails_after_a_change(self):
        self.assertEqual(_run("--out", self.out, "--date", "2026-01-02")[0], 0)
        with open(self.out, encoding="utf-8") as handle:
            text = handle.read()
        self.assertTrue(text.startswith("# Fusion parity checklist"))
        self.assertIn("Fusion commands present: ", text)
        # another day: still up to date
        self.assertEqual(_run("--check", "--out", self.out, "--date", "2026-02-03")[0], 0)
        with open(self.out, "w", encoding="utf-8") as handle:
            handle.write(text.replace("| Area |", "| Tab |"))
        code, printed = _run("--check", "--out", self.out)
        self.assertEqual(code, 1)
        self.assertIn("out of date", printed)

    def test_writing_an_unchanged_checklist_keeps_its_date(self):
        # two branches regenerating on different days must not conflict on the date line
        self.assertEqual(_run("--out", self.out, "--date", "2026-01-02")[0], 0)
        code, printed = _run("--out", self.out, "--date", "2026-02-03")
        self.assertEqual(code, 0)
        self.assertIn("already up to date", printed)
        with open(self.out, encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("parity.py on 2026-01-02;", text)
        with open(self.out, "w", encoding="utf-8") as handle:
            handle.write(text.replace("| Area |", "| Tab |"))
        self.assertEqual(_run("--out", self.out, "--date", "2026-02-03")[0], 0)
        with open(self.out, encoding="utf-8") as handle:
            self.assertIn("parity.py on 2026-02-03;", handle.read())

    def test_a_checklist_that_cannot_be_written_is_reported_not_raised(self):
        for target in (os.path.join(self.folder, "no-such-folder", "x.md"), self.folder):
            code, printed = _run("--out", target, "--date", "2026-01-02")
            self.assertEqual(code, 2, target)
            self.assertIn("[SciForge] parity: could not write", printed)

    def test_check_fails_when_the_checklist_is_missing(self):
        code, printed = _run("--check", "--out", os.path.join(self.folder, "nothing.md"))
        self.assertEqual(code, 1)
        self.assertIn("missing", printed)

    def test_a_broken_fusion_list_is_reported_not_raised(self):
        repo = os.path.join(self.folder, "repo")
        for relative in (parity.MENUS_FILE, parity.ALIASES_FILE):
            os.makedirs(os.path.dirname(os.path.join(repo, relative)), exist_ok=True)
        shutil.copy(
            os.path.join(REPO, parity.ALIASES_FILE), os.path.join(repo, parity.ALIASES_FILE)
        )
        with open(os.path.join(repo, parity.MENUS_FILE), "w", encoding="utf-8") as handle:
            handle.write("SOLID [in=tab:solid]\n   Extrude\n")
        code, printed = _run("--repo", repo, "--out", self.out)
        self.assertEqual(code, 2)
        self.assertIn("line 2", printed)


if __name__ == "__main__":
    unittest.main()
