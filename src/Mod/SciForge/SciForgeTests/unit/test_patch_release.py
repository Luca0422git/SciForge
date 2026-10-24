# SPDX-License-Identifier: LGPL-2.1-or-later
"""tools/sciforge/patch_release.py: which full release a patch release is built on, and when a
patch must not go out (docs/sciforge/patch-release.md). Runs without FreeCAD or the network."""

import importlib.util
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPO = os.path.abspath(os.path.join(ROOT, "..", "..", ".."))
TOOL = os.path.join(REPO, "tools", "sciforge", "patch_release.py")


def load_tool():
    if not os.path.isfile(TOOL):
        raise unittest.SkipTest("tools/ is not here (an installed SciForge)")
    spec = importlib.util.spec_from_file_location("patch_release", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def release(version, files=("installer", "portable", "appimage", "module"), draft=False):
    tag = "sciforge-v" + version
    names = {
        "installer": "SciForge_v%s-Windows-x86_64-py311-installer.exe" % version,
        "portable": "SciForge_v%s-Windows-x86_64-py311.7z" % version,
        "appimage": "SciForge_v%s-Linux-x86_64-py311.AppImage" % version,
        "module": "SciForge-quick-update-v%s.zip" % version,
    }
    assets = [names[f] for f in files] + ["sciforge-release.json", "SHA256SUMS.txt"]
    return {
        "tag_name": tag,
        "draft": draft,
        "assets": [
            {"name": n, "browser_download_url": "https://example.invalid/%s/%s" % (tag, n)} for n in assets
        ],
    }, {"core": "fd4a01850d", "assets": {f: names[f] for f in files}}


class PatchReleaseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tool = load_tool()

    def fixtures(self, *entries):
        data, manifests = [], {}
        for entry, manifest in entries:
            data.append(entry)
            manifests[entry["tag_name"]] = manifest
        return self.tool.releases_of(data), manifests

    def test_same_core_takes_abbreviations(self):
        same = self.tool.same_core
        self.assertTrue(same("fd4a01850d", "fd4a018"))
        self.assertTrue(same("FD4A018", "fd4a01850d"))
        self.assertFalse(same("fd4a01850d", "ab12345"))
        self.assertFalse(same("", "fd4a018"))

    def test_base_is_the_newest_full_release_with_the_core(self):
        releases, manifests = self.fixtures(release("0.1.0-beta.2"), release("0.1.0-beta"))
        version, tag, names = self.tool.choose_base(releases, manifests, "fd4a018")
        self.assertEqual((version, tag), ("0.1.0-beta.2", "sciforge-v0.1.0-beta.2"))
        self.assertEqual(names["appimage"], "SciForge_v0.1.0-beta.2-Linux-x86_64-py311.AppImage")

    def test_a_patch_counts_as_a_base_once_it_has_all_files(self):
        releases, manifests = self.fixtures(release("0.1.0-beta.2.1"), release("0.1.0-beta.2"))
        self.assertEqual(self.tool.choose_base(releases, manifests, "fd4a018")[0], "0.1.0-beta.2.1")

    def test_release_without_all_files_or_other_core_is_no_base(self):
        partial = release("0.1.0-beta.3", files=("module",))
        other = release("0.1.0-beta.2")
        other[1]["core"] = "0000000"
        releases, manifests = self.fixtures(partial, other)
        self.assertIsNone(self.tool.choose_base(releases, manifests, "fd4a018"))

    def test_drafts_and_other_tags_are_left_out(self):
        draft = release("0.1.0-beta.3", draft=True)
        junk = ({"tag_name": "weeklies", "assets": []}, None)
        releases, _manifests = self.fixtures(draft, junk, release("0.1.0-beta.2"))
        self.assertEqual([r[0] for r in releases], ["0.1.0-beta.2"])

    def test_version_must_be_new_and_newer(self):
        releases, _m = self.fixtures(release("0.1.0-beta.2"), release("0.1.0-beta"))
        self.assertEqual(self.tool.check_version("0.1.0-beta.2.1", releases), "0.1.0-beta.2.1")
        for bad in ("0.1.0-beta.2", "0.1.0-beta.1", "junk"):
            with self.assertRaises(self.tool.PatchError):
                self.tool.check_version(bad, releases)

    def test_new_file_names_carry_the_new_version(self):
        renamed = self.tool.renamed
        self.assertEqual(
            renamed("SciForge_v0.1.0-beta.2-Windows-x86_64-py311.7z", "0.1.0-beta.2", "0.1.0-beta.2.1", ".7z"),
            "SciForge_v0.1.0-beta.2.1-Windows-x86_64-py311",
        )
        self.assertEqual(
            renamed("SciForge_v0.1.0-beta.2-Linux-x86_64-py311.AppImage", "0.1.0-beta.2", "0.1.0-beta.2.1", ".AppImage"),
            "SciForge_v0.1.0-beta.2.1-Linux-x86_64-py311",
        )

    def run_main(self, version, entries, *extra):
        data = [entry for entry, _manifest in entries]
        manifests = {entry["tag_name"]: manifest for entry, manifest in entries}
        fetched = []

        def fake_fetch(url):
            fetched.append(url)
            return manifests[url.split("/")[-2]]

        old = self.tool._fetch_manifest
        self.tool._fetch_manifest = fake_fetch
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "releases.json")
            out = os.path.join(folder, "out.txt")
            with open(path, "w") as handle:  # two pages, as gh api --paginate prints them
                handle.write(json.dumps(data[:1]) + json.dumps(data[1:]))
            try:
                code = self.tool.main(
                    ["--releases", path, "--version", version, "--core", "fd4a018", "--github-output", out]
                    + list(extra)
                )
            finally:
                self.tool._fetch_manifest = old
            text = open(out).read() if os.path.isfile(out) else ""
        return code, dict(line.split("=", 1) for line in text.splitlines() if "=" in line)

    def test_main_writes_the_base_and_the_new_names(self):
        code, out = self.run_main("0.1.0-beta.2.1", [release("0.1.0-beta.2"), release("0.1.0-beta")])
        self.assertEqual(code, 0)
        self.assertEqual(out["base_tag"], "sciforge-v0.1.0-beta.2")
        self.assertEqual(out["new_portable"], "SciForge_v0.1.0-beta.2.1-Windows-x86_64-py311")
        self.assertEqual(out["new_appimage"], "SciForge_v0.1.0-beta.2.1-Linux-x86_64-py311.AppImage")

    def test_main_refuses_a_released_version_except_in_a_trial_run(self):
        entries = [release("0.1.0-beta.2")]
        self.assertEqual(self.run_main("0.1.0-beta.2", entries)[0], 1)
        code, out = self.run_main("0.1.0-beta.2", entries, "--dry-run")
        self.assertEqual(code, 0)
        self.assertEqual(out["base_tag"], "sciforge-v0.1.0-beta.2")

    def test_main_refuses_when_the_program_changed(self):
        other = release("0.1.0-beta.2")
        other[1]["core"] = "0000000"
        self.assertEqual(self.run_main("0.1.0-beta.2.1", [other])[0], 1)


if __name__ == "__main__":
    unittest.main()
