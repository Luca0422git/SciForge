# SPDX-License-Identifier: LGPL-2.1-or-later
"""tools/sciforge/make_release_files.py: the release's notes, sciforge-release.json and
SHA256SUMS.txt (brief beta-release.md R3). Runs without FreeCAD, on temp-folder fixtures: the real
CHANGELOG.md and docs/sciforge/smartscreen.md are written by other work and may be absent."""

import contextlib
import hashlib
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
REPO = os.path.abspath(os.path.join(ROOT, "..", "..", ".."))
TOOL = os.path.join(REPO, "tools", "sciforge", "make_release_files.py")

from sciforge import __version__, update_core as uc  # noqa: E402


def load_tool():
    if not os.path.isfile(TOOL):
        raise unittest.SkipTest("tools/ is not here (an installed SciForge)")
    spec = importlib.util.spec_from_file_location("make_release_files", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CHANGELOG = """# Changelog

Newest first.

## [0.1.0-beta.2] - 2026-11-01

### Fixed
- The thing that was broken.

## 0.1.0-beta - 2026-10-20

First public beta.

### Sketching
- Lines, circles, the palette.

## 0.0.9 (never released)

- Old.
"""

SMARTSCREEN = """# Windows protected your PC

SciForge is not signed with a paid certificate, so Windows is careful.

1. Click **More info**.
2. Click **Run anyway**.
"""


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tool = load_tool()
        self.tmp = tempfile.mkdtemp(prefix="sciforge-release-")
        self.assets = os.path.join(self.tmp, "assets")
        self.contents = {}
        for sub, name, data in (
            ("a", "SciForge_0.1.0-beta-Windows-x86_64-py311-installer.exe", b"installer bytes"),
            ("a", "SciForge_0.1.0-beta-Windows-x86_64-py311-installer.exe-SHA256.txt", b"checksum file"),
            ("b", "SciForge_0.1.0-beta-Windows-x86_64-py311.7z", b"portable bytes"),
            ("b", "SciForge_0.1.0-beta-Windows-x86_64-py311.7z-SHA256.txt", b"checksum file"),
            ("c", "SciForge_0.1.0-beta-Linux-x86_64-py311.AppImage", b"appimage bytes"),
            ("d", "SciForge-quick-update-0.1.0-beta.zip", b"module bytes"),
        ):
            os.makedirs(os.path.join(self.assets, sub), exist_ok=True)
            with open(os.path.join(self.assets, sub, name), "wb") as handle:
                handle.write(data)
            self.contents[name] = data

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def build(self, tag="sciforge-v0.1.0-beta", **kw):
        args = dict(
            tag=tag, core="abc1234", date="2026-10-20", repo="Luca0422git/SciForge",
            files=self.tool.find_assets(self.assets), changelog=CHANGELOG,
            smartscreen=SMARTSCREEN, require_all=True,
        )  # fmt: skip
        args.update(kw)
        return self.tool.build_all(**args)


class Files(Fixture):
    def test_roles_by_name(self):
        c = self.tool.classify
        self.assertEqual(c("SciForge_x-installer.exe"), "installer")
        self.assertEqual(c("SciForge_x.7z"), "portable")
        self.assertEqual(c("SciForge_x.AppImage"), "appimage")
        # the packaging tool sits next to the AppImage in the build folder: never a release file
        self.assertEqual(c("appimagetool-x86_64.AppImage"), "")
        self.assertEqual(c("SciForge-quick-update-x.zip"), "module")
        for other in ("SciForge_x-installer.exe-SHA256.txt", "SciForge_x.7z-SHA256.txt", "other.zip", "README.md"):
            self.assertEqual(c(other), "", other)

    def test_find_assets_looks_in_every_subfolder_and_skips_checksum_files(self):
        found = self.tool.find_assets(self.assets)
        self.assertEqual(sorted(found), ["appimage", "installer", "module", "portable"])

    def test_two_files_of_one_role_is_an_error(self):
        with open(os.path.join(self.assets, "a", "other-installer.exe"), "wb") as handle:
            handle.write(b"x")
        with self.assertRaises(self.tool.ReleaseFilesError):
            self.tool.find_assets(self.assets)


class Changelog(Fixture):
    def test_the_section_of_a_version(self):
        text = self.tool.changelog_section(CHANGELOG, "0.1.0-beta")
        self.assertTrue(text.startswith("First public beta."))
        self.assertIn("### Sketching", text)
        self.assertIn("Lines, circles, the palette.", text)
        self.assertNotIn("The thing that was broken", text)
        self.assertNotIn("Old.", text)

    def test_beta_2_is_not_found_by_beta_and_the_other_way_round(self):
        text = self.tool.changelog_section(CHANGELOG, "0.1.0-beta.2")
        self.assertIn("The thing that was broken", text)
        self.assertNotIn("First public beta", text)
        only_beta_2 = "## [0.1.0-beta.2] - x\n\n- two\n"
        self.assertIsNone(self.tool.changelog_section(only_beta_2, "0.1.0-beta"))
        self.assertIsNone(self.tool.changelog_section("## 0.1.0-beta\n\n- x\n", "0.1.0"))
        self.assertIsNone(self.tool.changelog_section("## 0.1.0\n\n- x\n", "0.1.0-beta"))

    def test_heading_styles(self):
        for heading in ("## 0.1.0-beta", "## [0.1.0-beta]", "## v0.1.0-beta (2026-10-20)",
                        "## 0.1.0-beta - 2026-10-20", "##   [0.1.0-beta](https://x/y) - date",
                        "## sciforge-v0.1.0-beta"):  # fmt: skip
            got = self.tool.changelog_section("%s\n\nbody text\n\n## 0.0.1\n\nold\n" % heading, "0.1.0-beta")
            self.assertEqual(got, "body text", heading)

    def test_windows_line_endings_work(self):
        text = CHANGELOG.replace("\n", "\r\n")
        self.assertIn("First public beta.", self.tool.changelog_section(text, "0.1.0-beta"))

    def test_no_section_junk_and_an_empty_section(self):
        self.assertIsNone(self.tool.changelog_section(CHANGELOG, "9.9.9"))
        self.assertIsNone(self.tool.changelog_section(CHANGELOG, "junk"))
        self.assertIsNone(self.tool.changelog_section(None, "0.1.0-beta"))
        self.assertIsNone(self.tool.changelog_section("## 0.1.0-beta\n\n## 0.0.1\n- x\n", "0.1.0-beta"))
        self.assertIsNone(self.tool.changelog_section("", "0.1.0-beta"))

    def test_a_third_level_heading_does_not_end_the_section(self):
        got = self.tool.changelog_section("## 0.1.0-beta\n### Added\n- a\n### Fixed\n- b\n", "0.1.0-beta")
        self.assertIn("### Fixed", got)

    def test_smartscreen_block_takes_its_title_as_a_section_heading(self):
        block = self.tool.smartscreen_block(SMARTSCREEN)
        self.assertTrue(block.startswith("## Windows protected your PC\n"))
        self.assertIn("Run anyway", block)
        plain = self.tool.smartscreen_block("Just text.\n")
        self.assertTrue(plain.startswith("## Windows protected your PC\n\nJust text."))


class Built(Fixture):
    def test_the_json_has_the_briefs_shape_and_the_right_hashes(self):
        made = self.build()
        data = json.loads(made["sciforge-release.json"])
        self.assertEqual(list(data), ["version", "tag", "core", "date", "notes_url", "assets", "sha256"])
        self.assertEqual(data["version"], "0.1.0-beta")
        self.assertEqual(data["tag"], "sciforge-v0.1.0-beta")
        self.assertEqual(data["core"], "abc1234")
        self.assertEqual(data["date"], "2026-10-20")
        self.assertEqual(data["notes_url"], "https://github.com/Luca0422git/SciForge/releases/tag/sciforge-v0.1.0-beta")
        self.assertEqual(sorted(data["assets"]), ["appimage", "installer", "module", "portable"])
        self.assertEqual(data["assets"]["module"], "SciForge-quick-update-0.1.0-beta.zip")
        self.assertEqual(len(data["sha256"]), 4)
        for name, digest in data["sha256"].items():
            self.assertEqual(digest, hashlib.sha256(self.contents[name]).hexdigest(), name)

    def test_what_the_update_check_reads_comes_back_whole(self):
        # the json is what update_core reads: the same names, hashes and core
        manifest = uc.parse_manifest(self.build()["sciforge-release.json"])
        self.assertIsNotNone(manifest)
        self.assertEqual(manifest["core"], "abc1234")
        self.assertEqual(len(manifest["sha256"]), 4)
        release = {
            "version": "0.1.0-beta", "tag": "sciforge-v0.1.0-beta", "prerelease": True,
            "page": "https://example.org/r", "manifest": manifest, "sizes": {},
            "assets": {n: "https://example.org/dl/" + n for n in manifest["sha256"]},
        }  # fmt: skip
        layout = {"os": "windows", "kind": "installed", "home": "C:\\Program Files\\SciForge"}
        same = uc.plan({"version": "0.0.1", "core": "abc1234"}, release, layout)
        self.assertEqual((same["kind"], same["asset"]), ("module", "SciForge-quick-update-0.1.0-beta.zip"))
        other = uc.plan({"version": "0.0.1", "core": "zzz"}, release, layout)
        self.assertEqual(other["kind"], "installer")

    def test_sha256sums_is_the_sha256sum_format(self):
        lines = self.build()["SHA256SUMS.txt"].splitlines()
        self.assertEqual(len(lines), 4)
        self.assertEqual(lines, sorted(lines, key=lambda l: l.split("  ", 1)[1]))
        for line in lines:
            digest, name = line.split("  ", 1)
            self.assertEqual(digest, hashlib.sha256(self.contents[name]).hexdigest())
        self.assertFalse(any("SHA256.txt" in line for line in lines))

    def test_the_notes_have_every_part(self):
        notes = self.build()["release-notes.md"]
        self.assertTrue(notes.startswith("First public beta."))  # the changelog section first
        self.assertIn("### Sketching", notes)
        self.assertNotIn("The thing that was broken", notes)  # not another version's
        self.assertIn("## Which file do I download?", notes)
        self.assertIn("-installer.exe` (the installer)", notes)
        self.assertIn("## Windows protected your PC", notes)
        self.assertIn("**Run anyway**", notes)  # the fixed text, whole
        self.assertIn("## How to update", notes)
        self.assertIn("Help > Check for Updates", notes)
        self.assertIn("## Checksums (SHA-256)", notes)
        self.assertIn(hashlib.sha256(self.contents["SciForge_0.1.0-beta-Windows-x86_64-py311.7z"]).hexdigest(), notes)
        self.assertIn("Get-FileHash", notes)
        self.assertTrue(notes.endswith("\n"))

    def test_the_notes_of_the_smartscreen_text_come_from_the_file_given(self):
        notes = self.build(smartscreen="# Windows protected your PC\n\nA different sentence here.\n")["release-notes.md"]
        self.assertIn("A different sentence here.", notes)
        self.assertNotIn("Run anyway", notes)

    def test_a_dry_run_of_one_platform_leaves_out_what_is_missing(self):
        files = {k: v for k, v in self.tool.find_assets(self.assets).items() if k in ("installer", "portable")}
        made = self.build(files=files, require_all=False)
        data = json.loads(made["sciforge-release.json"])
        self.assertEqual(sorted(data["assets"]), ["installer", "portable"])
        self.assertNotIn("Linux", made["release-notes.md"])
        with self.assertRaises(self.tool.ReleaseFilesError) as caught:
            self.build(files=files, require_all=True)
        self.assertIn("appimage", str(caught.exception))

    def test_a_beta_two_tag_uses_its_own_section(self):
        made = self.build(tag="sciforge-v0.1.0-beta.2")
        self.assertIn("The thing that was broken", made["release-notes.md"])
        self.assertEqual(json.loads(made["sciforge-release.json"])["version"], "0.1.0-beta.2")


class Problems(Fixture):
    def test_each_problem_says_what_is_wrong(self):
        cases = [
            (dict(changelog=None), "CHANGELOG.md is missing"),
            (dict(changelog="## 0.0.1\n- x\n"), "no section for 0.1.0-beta"),
            (dict(smartscreen=None), "smartscreen.md is missing"),
            (dict(core=""), "core id"),
            (dict(core="  "), "core id"),
            (dict(tag="v0.1.0-beta"), "not a release tag"),
            (dict(tag="nonsense"), "not a release tag"),
            (dict(files={}), "no release files"),
        ]
        for kw, words in cases:
            with self.assertRaises(self.tool.ReleaseFilesError, msg=words) as caught:
                self.build(**kw)
            self.assertIn(words, str(caught.exception))

    def run_main(self, *extra, changelog=CHANGELOG, smartscreen=SMARTSCREEN):
        paths = {}
        for name, text in (("CHANGELOG.md", changelog), ("smartscreen.md", smartscreen)):
            paths[name] = os.path.join(self.tmp, name)
            if os.path.exists(paths[name]):
                os.remove(paths[name])
            if text is not None:
                with open(paths[name], "w", encoding="utf-8") as handle:
                    handle.write(text)
        out = os.path.join(self.tmp, "out")
        argv = [
            "--tag", "sciforge-v0.1.0-beta", "--core", "abc1234", "--assets", self.assets, "--out", out,
            "--date", "2026-10-20", "--changelog", paths["CHANGELOG.md"], "--smartscreen", paths["smartscreen.md"],
        ] + list(extra)  # fmt: skip
        err, text = io.StringIO(), io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(text):
            code = self.tool.main(argv)
        return code, err.getvalue(), out

    def test_the_command_line_writes_the_three_files(self):
        code, err, out = self.run_main("--require-all")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(sorted(os.listdir(out)), ["SHA256SUMS.txt", "release-notes.md", "sciforge-release.json"])
        with open(os.path.join(out, "sciforge-release.json"), encoding="utf-8") as handle:
            self.assertEqual(json.load(handle)["core"], "abc1234")

    def test_the_list_of_files_to_attach(self):
        listing = os.path.join(self.tmp, "attach.txt")
        code, err, out = self.run_main("--require-all", "--list-file", listing)
        self.assertEqual((code, err), (0, ""))
        with open(listing, encoding="utf-8") as handle:
            lines = handle.read().splitlines()
        names = [os.path.basename(line) for line in lines]
        self.assertEqual(len(lines), 6)
        self.assertIn("sciforge-release.json", names)
        self.assertIn("SHA256SUMS.txt", names)
        self.assertNotIn("release-notes.md", names)  # (the notes are the release's text)
        self.assertFalse(any(n.endswith("-SHA256.txt") and n != "SHA256SUMS.txt" for n in names))
        for line in lines:
            self.assertTrue(os.path.isfile(line), line)

    def test_the_command_line_stops_with_a_clear_message_when_a_text_is_missing(self):
        code, err, out = self.run_main(changelog=None)
        self.assertEqual(code, 1)
        self.assertIn("[SciForge] make_release_files: CHANGELOG.md is missing", err)
        self.assertFalse(os.path.exists(out))
        code, err, _out = self.run_main(smartscreen=None)
        self.assertEqual(code, 1)
        self.assertIn("smartscreen.md is missing", err)
        code, err, _out = self.run_main(changelog="## 0.0.1\n- x\n")
        self.assertEqual(code, 1)
        self.assertIn("no section for 0.1.0-beta", err)


class RealFiles(unittest.TestCase):
    """The real CHANGELOG.md and smartscreen.md (written by the docs work): when they exist,
    the release job must be able to use them."""

    def test_the_changelog_has_a_section_for_this_version(self):
        tool = load_tool()
        path = os.path.join(REPO, "CHANGELOG.md")
        if not os.path.isfile(path):
            self.skipTest("CHANGELOG.md is not written yet")
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        self.assertIsNotNone(tool.changelog_section(text, __version__), "no section for %s" % __version__)

    def test_smartscreen_text_is_not_empty(self):
        tool = load_tool()
        path = os.path.join(REPO, "docs", "sciforge", "smartscreen.md")
        if not os.path.isfile(path):
            self.skipTest("smartscreen.md is not written yet")
        with open(path, encoding="utf-8") as handle:
            self.assertGreater(len(tool.smartscreen_block(handle.read())), 80)


class CoreId(unittest.TestCase):
    """tools/sciforge/core_id.sh in a throw-away git repository."""

    def test_the_id_is_the_last_commit_of_the_compiled_part_only(self):
        import subprocess

        script = os.path.join(REPO, "tools", "sciforge", "core_id.sh")
        if not os.path.isfile(script) or shutil.which("git") is None:
            self.skipTest("no tools/ or no git here")
        tmp = tempfile.mkdtemp(prefix="sciforge-core-")
        try:
            def git(*args):
                return subprocess.run(
                    ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"] + list(args),
                    cwd=tmp, check=True, capture_output=True, text=True,
                ).stdout.strip()  # fmt: skip

            def commit(path, text):
                full = os.path.join(tmp, path)
                os.makedirs(os.path.dirname(full), exist_ok=True)
                with open(full, "a", encoding="utf-8") as handle:
                    handle.write(text)
                git("add", "-A")
                git("commit", "-q", "-m", "change " + path)
                return git("rev-parse", "--short", "HEAD")

            git("init", "-q")
            os.makedirs(os.path.join(tmp, "tools", "sciforge"))
            shutil.copy(script, os.path.join(tmp, "tools", "sciforge", "core_id.sh"))
            cpp = commit("src/Gui/Main.cpp", "int main(){}\n")

            def core():
                return subprocess.run(
                    ["bash", os.path.join(tmp, "tools", "sciforge", "core_id.sh")],
                    cwd=tmp, capture_output=True, text=True,
                )  # fmt: skip

            self.assertEqual(core().stdout.strip(), cpp)
            commit("src/Mod/SciForge/sciforge/x.py", "x = 1\n")
            commit("src/Mod/SciForge/VERSION", "0.1.0-beta.2\n")
            commit("docs/sciforge/a.md", "text\n")
            self.assertEqual(core().stdout.strip(), cpp, "SciForge's own files and docs do not change the core")
            pkg = commit("package/WindowsInstaller/x.nsi", "x\n")
            self.assertEqual(core().stdout.strip(), pkg)
            cmake = commit("CMakeLists.txt", "x\n")
            self.assertEqual(core().stdout.strip(), cmake)
            # a shallow clone cannot know: it must say so instead of printing a wrong id
            shallow = os.path.join(tmp, "shallow")
            subprocess.run(["git", "clone", "-q", "--depth", "1", "file://" + tmp, shallow], check=True, capture_output=True)
            result = subprocess.run(["bash", os.path.join(shallow, "tools", "sciforge", "core_id.sh")], cwd=shallow, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("shallow", result.stderr)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
