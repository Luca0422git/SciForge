# SPDX-License-Identifier: LGPL-2.1-or-later
"""tools/sciforge/fake_release_server.py: the stand-in for GitHub that lets "Update now" be tried
by hand with the files of a dry run (no release published). Here the whole chain runs against
it: make_release_files writes the json, the server serves the folder, update_core checks,
plans and downloads, verifying every checksum."""

import importlib.util
import os
import shutil
import sys
import tempfile
import threading
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
REPO = os.path.abspath(os.path.join(ROOT, "..", "..", ".."))
TOOLS = os.path.join(REPO, "tools", "sciforge")

from sciforge import update_core as uc  # noqa: E402


def load(name):
    path = os.path.join(TOOLS, name + ".py")
    if not os.path.isfile(path):
        raise unittest.SkipTest("tools/ is not here (an installed SciForge)")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeReleaseServer(unittest.TestCase):
    def setUp(self):
        self.maker = load("make_release_files")
        self.fake = load("fake_release_server")
        self.tmp = tempfile.mkdtemp(prefix="sciforge-fake-release-")
        assets = os.path.join(self.tmp, "assets")
        self.folder = os.path.join(self.tmp, "release-files")
        os.makedirs(assets)
        os.makedirs(self.folder)
        self.data = {
            "SciForge_v0.1.0-beta.2-Windows-x86_64-py311-installer.exe": b"installer " * 5000,
            "SciForge_v0.1.0-beta.2-Windows-x86_64-py311.7z": b"portable " * 100,
            "SciForge_v0.1.0-beta.2-Linux-x86_64-py311.AppImage": b"appimage " * 100,
            "SciForge-quick-update-v0.1.0-beta.2.zip": b"module " * 2000,
        }
        for name, data in self.data.items():
            with open(os.path.join(assets, name), "wb") as handle:
                handle.write(data)
        files = self.maker.find_assets(assets)
        made = self.maker.build_all(
            "sciforge-v0.1.0-beta.2", "abc1234", "2026-10-21", "Luca0422git/SciForge", files,
            "## 0.1.0-beta.2\n\n- Something.\n", "# Windows protected your PC\n\nText that is long enough.\n",
            require_all=True,
        )  # fmt: skip
        for name, text in made.items():  # the dry run's artifact: the json, the sums, the notes and the zip
            with open(os.path.join(self.folder, name), "w", encoding="utf-8") as handle:
                handle.write(text)
        for name in ("SciForge-quick-update-v0.1.0-beta.2.zip", "SciForge_v0.1.0-beta.2-Windows-x86_64-py311-installer.exe"):
            shutil.copy(os.path.join(assets, name), self.folder)
        self.server, self.base, self.listing = self.fake.make_server(self.folder, 0)
        threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True).start()
        self.old_base = uc.API_BASE
        uc.API_BASE = self.base

    def tearDown(self):
        uc.API_BASE = self.old_base
        self.server.shutdown()
        self.server.server_close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_the_listing_is_one_prerelease_with_the_files_that_are_there(self):
        (entry,) = self.listing
        self.assertEqual(entry["tag_name"], "sciforge-v0.1.0-beta.2")
        self.assertTrue(entry["prerelease"])
        names = sorted(a["name"] for a in entry["assets"])
        self.assertIn("sciforge-release.json", names)
        self.assertIn("SciForge-quick-update-v0.1.0-beta.2.zip", names)
        self.assertNotIn("release-notes.md", names)
        self.assertFalse(any(not a["browser_download_url"].startswith(self.base) for a in entry["assets"]))

    def test_the_update_check_finds_it_and_plans_the_module_update_for_the_same_core(self):
        got = uc.check("0.1.0-beta", uc.BETA)
        self.assertEqual(got["status"], "newer")
        release = got["release"]
        self.assertEqual(release["manifest"]["core"], "abc1234")
        layout = {"os": "windows", "kind": "installed", "home": "C:\\Program Files\\SciForge"}
        same = uc.plan({"version": "0.1.0-beta", "core": "abc1234"}, release, layout)
        self.assertEqual((same["kind"], same["asset"]), ("module", "SciForge-quick-update-v0.1.0-beta.2.zip"))
        other = uc.plan({"version": "0.1.0-beta", "core": ""}, release, layout)
        self.assertEqual(other["kind"], "installer")

    def test_both_downloads_match_their_checksums(self):
        release = uc.check("0.1.0-beta", uc.BETA)["release"]
        layout = {"os": "windows", "kind": "installed", "home": "C:\\x"}
        for core, kind in (("abc1234", "module"), ("", "installer")):
            plan = uc.plan({"version": "0.1.0-beta", "core": core}, release, layout)
            dest = os.path.join(self.tmp, "dl-" + kind, plan["asset"])
            status, _text = uc.download(plan["url"], dest, plan["sha256"])
            self.assertEqual(status, "ok", kind)
            with open(dest, "rb") as handle:
                self.assertEqual(handle.read(), self.data[plan["asset"]])

    def test_a_folder_that_is_not_a_release_says_so(self):
        with self.assertRaises(ValueError) as caught:
            self.fake.build_listing(self.tmp, "http://127.0.0.1:1")
        self.assertIn("sciforge-release.json", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
