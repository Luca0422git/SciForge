# SPDX-License-Identifier: LGPL-2.1-or-later
"""The update check's rules (sciforge/update_core.py, brief beta-release.md R3). Runs without
FreeCAD. The network parts talk to a fake GitHub on this computer's own address (a thread with
http.server), never to the internet."""

import hashlib
import http.server
import json
import os
import shutil
import socket
import sys
import tempfile
import threading
import unittest
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from sciforge import update_core as uc  # noqa: E402


def sha(data):
    return hashlib.sha256(data).hexdigest()


def release_entry(tag, prerelease=False, draft=False, assets=None):
    return {
        "tag_name": tag,
        "draft": draft,
        "prerelease": prerelease,
        "html_url": "https://github.com/x/y/releases/tag/%s" % tag,
        "assets": [
            {"name": n, "browser_download_url": u, "size": 10} for n, u in (assets or {}).items()
        ],
    }


class FakeGitHub:
    """A tiny web server: routes {path: (status, bytes)}; remembers the requests' headers."""

    def __init__(self):
        self.routes = {}
        self.seen = []
        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                outer.seen.append((self.path, dict(self.headers)))
                status, body = outer.routes.get(self.path, (404, b"{}"))
                self.send_response(status)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.base = "http://127.0.0.1:%d" % self.server.server_address[1]
        threading.Thread(
            target=self.server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True
        ).start()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()


def read(path):
    with open(path, "rb") as handle:
        return handle.read()


def closed_port_base():
    """An address on this computer where nothing listens."""
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return "http://127.0.0.1:%d" % port


class Versions(unittest.TestCase):
    R = [
        {"version": "0.1.0-beta", "prerelease": True},
        {"version": "0.1.0-beta.2", "prerelease": True},
        {"version": "0.1.0-beta.10", "prerelease": True},
        {"version": "0.1.0", "prerelease": False},
        {"version": "0.1.1-beta", "prerelease": True},
    ]

    def test_a_beta_gets_the_newest_beta_or_stable(self):
        got = uc.choose(self.R, "0.1.0-beta", uc.BETA)
        self.assertEqual(got["version"], "0.1.1-beta")

    def test_beta_numbers_compare_as_numbers(self):
        got = uc.choose(self.R[:3], "0.1.0-beta.2", uc.BETA)
        self.assertEqual(got["version"], "0.1.0-beta.10")

    def test_stable_only_skips_betas(self):
        got = uc.choose(self.R, "0.1.0-beta", uc.STABLE)
        self.assertEqual(got["version"], "0.1.0")

    def test_stable_only_and_no_stable_newer_is_nothing(self):
        self.assertIsNone(uc.choose(self.R[:3], "0.1.0-beta", uc.STABLE))

    def test_a_stable_user_gets_a_beta_only_when_asked(self):
        self.assertIsNone(uc.choose(self.R, "0.1.1", uc.STABLE))
        self.assertEqual(uc.choose(self.R, "0.1.0", uc.BETA)["version"], "0.1.1-beta")

    def test_our_own_version_and_older_ones_are_not_updates(self):
        self.assertIsNone(uc.choose(self.R, "0.1.1-beta", uc.BETA))
        self.assertIsNone(uc.choose(self.R, "0.9.0", uc.BETA))

    def test_junk_in_the_list_is_skipped(self):
        junk = [None, 5, {}, {"version": None}, {"version": "soon"}] + self.R[:2]
        self.assertEqual(uc.choose(junk, "0.1.0-beta", uc.BETA)["version"], "0.1.0-beta.2")
        self.assertIsNone(uc.choose(None, "0.1.0-beta", uc.BETA))
        self.assertIsNone(uc.choose(self.R, "garbage", uc.BETA))

    def test_default_channel_follows_the_installed_version(self):
        self.assertEqual(uc.default_channel("0.1.0-beta"), uc.BETA)
        self.assertEqual(uc.default_channel("0.1.0"), uc.STABLE)
        self.assertEqual(uc.clean_channel("beta", "0.1.0"), uc.BETA)
        self.assertEqual(uc.clean_channel("stable", "0.1.0-beta"), uc.STABLE)
        self.assertEqual(uc.clean_channel("nonsense", "0.1.0-beta"), uc.BETA)
        self.assertEqual(uc.clean_channel("", "0.1.0"), uc.STABLE)


class ParseReleases(unittest.TestCase):
    def test_drafts_and_other_tags_and_junk_are_ignored(self):
        data = [
            release_entry("sciforge-v0.1.0-beta.2", True),
            release_entry("sciforge-v0.1.0-beta.3", True, draft=True),
            release_entry("1.1.4"),  # a FreeCAD tag, not ours
            release_entry("v0.2.0"),  # not our tag form
            release_entry("sciforge-vsoon"),
            "text",
            None,
            {"tag_name": 5},
        ]
        got = uc.parse_releases(data)
        self.assertEqual([r["version"] for r in got], ["0.1.0-beta.2"])
        self.assertTrue(got[0]["prerelease"])
        self.assertEqual(got[0]["tag"], "sciforge-v0.1.0-beta.2")

    def test_not_a_list_gives_nothing(self):
        for data in (None, {}, "x", 5, {"message": "rate limit"}):
            self.assertEqual(uc.parse_releases(data), [])

    def test_a_version_with_beta_is_a_prerelease_even_if_github_says_not(self):
        got = uc.parse_releases([release_entry("sciforge-v0.1.0-beta", prerelease=False)])
        self.assertTrue(got[0]["prerelease"])

    def test_assets_only_safe_names_and_web_addresses(self):
        entry = release_entry(
            "sciforge-v0.1.0",
            assets={
                "SciForge.exe": "https://example.org/a",
                "../evil": "https://example.org/b",
                "dir/x": "https://example.org/c",
                "local": "file:///etc/passwd",
            },
        )
        got = uc.parse_releases([entry])[0]
        self.assertEqual(list(got["assets"]), ["SciForge.exe"])

    def test_the_page_falls_back_to_the_tag_page(self):
        entry = release_entry("sciforge-v0.1.0")
        del entry["html_url"]
        got = uc.parse_releases([entry])[0]
        self.assertEqual(got["page"], "https://github.com/Luca0422git/SciForge/releases/tag/sciforge-v0.1.0")


GOOD = {
    "version": "0.1.0-beta.2",
    "tag": "sciforge-v0.1.0-beta.2",
    "core": "abc1234",
    "date": "2026-10-21",
    "notes_url": "https://github.com/Luca0422git/SciForge/releases/tag/sciforge-v0.1.0-beta.2",
    "assets": {
        "installer": "SciForge_x-installer.exe",
        "portable": "SciForge_x.7z",
        "appimage": "SciForge_x.AppImage",
        "module": "SciForge-quick-update-x.zip",
    },
    "sha256": {
        "SciForge_x-installer.exe": "a" * 64,
        "SciForge_x.7z": "b" * 64,
        "SciForge_x.AppImage": "c" * 64,
        "SciForge-quick-update-x.zip": "D" * 64,
    },
}


class Manifest(unittest.TestCase):
    def test_a_good_manifest_is_read(self):
        got = uc.parse_manifest(json.dumps(GOOD).encode())
        self.assertEqual(got["version"], "0.1.0-beta.2")
        self.assertEqual(got["core"], "abc1234")
        self.assertEqual(got["assets"]["module"], "SciForge-quick-update-x.zip")
        self.assertEqual(got["sha256"]["SciForge-quick-update-x.zip"], "d" * 64)  # lowercase
        self.assertEqual(got["notes_url"], GOOD["notes_url"])

    def test_text_and_bytes_both_work(self):
        self.assertIsNotNone(uc.parse_manifest(json.dumps(GOOD)))
        self.assertIsNotNone(uc.parse_manifest(json.dumps(GOOD).encode("utf-8")))

    def test_junk_gives_none_and_never_raises(self):
        for raw in (b"", b"not json", b"[]", b"5", b"null", b'{"version": "soon"}', b"\xff\xfe", None, 7, b"{}"):
            self.assertIsNone(uc.parse_manifest(raw), raw)

    def test_bad_hashes_and_names_are_dropped(self):
        data = dict(GOOD)
        data["sha256"] = {"ok.exe": "e" * 64, "short.exe": "abc", "../x": "f" * 64, "nothex.exe": "g" * 64}
        data["assets"] = {"installer": "../escape.exe", "module": "fine.zip", "unknown": "x"}
        got = uc.parse_manifest(json.dumps(data))
        self.assertEqual(got["sha256"], {"ok.exe": "e" * 64})
        self.assertEqual(got["assets"], {"module": "fine.zip"})

    def test_missing_core_and_notes_are_empty(self):
        data = {"version": "0.1.0-beta.2"}
        got = uc.parse_manifest(json.dumps(data))
        self.assertEqual(got["core"], "")
        self.assertEqual(got["notes_url"], "")
        self.assertEqual(got["tag"], "sciforge-v0.1.0-beta.2")

    def test_a_manifest_for_another_version_is_not_attached(self):
        release = uc.parse_releases([release_entry("sciforge-v0.1.0-beta.3")])[0]
        self.assertIsNone(uc.attach_manifest(release, uc.parse_manifest(json.dumps(GOOD)))["manifest"])
        self.assertIsNone(uc.attach_manifest(release, None)["manifest"])


def make_release(core="abc1234", with_assets=True, hashes=True):
    names = GOOD["assets"]
    urls = {n: "https://example.org/dl/" + n for n in names.values()} if with_assets else {}
    entry = release_entry("sciforge-v0.1.0-beta.2", True, assets=urls)
    release = uc.parse_releases([entry])[0]
    manifest = dict(uc.parse_manifest(json.dumps(GOOD)))
    manifest["core"] = core
    if not hashes:
        manifest["sha256"] = {}
    release["manifest"] = manifest
    return release


WINDOWS = {"os": "windows", "kind": "installed", "home": "C:\\Program Files\\SciForge"}
PORTABLE = {"os": "windows", "kind": "portable", "home": "C:\\SciForge"}
OLD = {"version": "0.1.0-beta", "core": "abc1234"}


class Plan(unittest.TestCase):
    def test_same_core_installed_windows_is_a_module_update(self):
        got = uc.plan(OLD, make_release(), WINDOWS)
        self.assertEqual(got["kind"], "module")
        self.assertEqual(got["asset"], "SciForge-quick-update-x.zip")
        self.assertEqual(got["sha256"], "d" * 64)
        self.assertTrue(got["url"].startswith("https://example.org/dl/"))

    def test_same_core_portable_windows_is_a_module_update(self):
        self.assertEqual(uc.plan(OLD, make_release(), PORTABLE)["kind"], "module")

    def test_a_different_core_is_the_full_installer(self):
        got = uc.plan({"version": "0.1.0-beta", "core": "old0000"}, make_release(), WINDOWS)
        self.assertEqual(got["kind"], "installer")
        self.assertEqual(got["asset"], "SciForge_x-installer.exe")

    def test_an_unknown_installed_core_is_the_full_installer(self):
        # a quick update from a test run does not know its core: never trust "same"
        got = uc.plan({"version": "0.1.0-beta", "core": ""}, make_release(core=""), WINDOWS)
        self.assertEqual(got["kind"], "installer")

    def test_a_missing_module_asset_falls_back_to_the_installer(self):
        release = make_release()
        del release["manifest"]["assets"]["module"]
        self.assertEqual(uc.plan(OLD, release, WINDOWS)["kind"], "installer")

    def test_a_module_without_a_hash_is_never_downloaded(self):
        release = make_release()
        del release["manifest"]["sha256"]["SciForge-quick-update-x.zip"]
        self.assertEqual(uc.plan(OLD, release, WINDOWS)["kind"], "installer")

    def test_nothing_verifiable_opens_the_release_page(self):
        got = uc.plan(OLD, make_release(hashes=False), WINDOWS)
        self.assertEqual(got["kind"], "browser")
        self.assertEqual(got["asset"], "")
        got = uc.plan(OLD, make_release(with_assets=False), WINDOWS)
        self.assertEqual(got["kind"], "browser")

    def test_a_release_without_a_manifest_opens_the_release_page(self):
        release = make_release()
        release["manifest"] = None
        got = uc.plan(OLD, release, WINDOWS)
        self.assertEqual(got["kind"], "browser")
        self.assertIn("releases/tag", got["page"])

    def test_the_appimage_and_other_linux_open_the_browser(self):
        appimage = uc.plan(OLD, make_release(), {"os": "linux", "kind": "appimage", "home": "/tmp/x"})
        self.assertEqual(appimage["kind"], "browser")
        self.assertIn("replace the old one", appimage["reason"])
        other = uc.plan(OLD, make_release(), {"os": "linux", "kind": "linux", "home": "/usr"})
        self.assertEqual(other["kind"], "browser")

    def test_a_windows_folder_without_bin_and_mod_is_the_installer(self):
        got = uc.plan(OLD, make_release(), {"os": "windows", "kind": "other", "home": ""})
        self.assertEqual(got["kind"], "installer")

    def test_the_page_is_the_manifests_notes_address(self):
        got = uc.plan(OLD, make_release(), WINDOWS)
        self.assertEqual(got["page"], GOOD["notes_url"])


class Layout(unittest.TestCase):
    def test_windows_installed_and_portable(self):
        env = {"ProgramFiles": "C:\\Program Files"}
        yes = lambda p: True  # noqa: E731
        got = uc.detect_layout("win32", "C:\\Program Files\\SciForge", env, yes)
        self.assertEqual((got["os"], got["kind"]), ("windows", "installed"))
        got = uc.detect_layout("win32", "D:\\Tools\\SciForge", env, yes)
        self.assertEqual((got["os"], got["kind"]), ("windows", "portable"))
        got = uc.detect_layout("win32", "C:\\Program Files\\SciForge", env, lambda p: False)
        self.assertEqual(got["kind"], "other")

    def test_linux_appimage_and_other(self):
        self.assertEqual(uc.detect_layout("linux", "/tmp/.mount_x", {"APPIMAGE": "/a/b.AppImage"})["kind"], "appimage")
        self.assertEqual(uc.detect_layout("linux", "/usr", {})["kind"], "linux")
        self.assertEqual(uc.detect_layout("darwin", "/Applications", {})["os"], "other")


class Files(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="sciforge-update-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_verify(self):
        path = os.path.join(self.tmp, "f.bin")
        with open(path, "wb") as handle:
            handle.write(b"hello")
        self.assertTrue(uc.verify(path, sha(b"hello")))
        self.assertTrue(uc.verify(path, sha(b"hello").upper()))
        self.assertFalse(uc.verify(path, sha(b"other")))
        self.assertFalse(uc.verify(path, ""))
        self.assertFalse(uc.verify(os.path.join(self.tmp, "missing"), sha(b"hello")))

    def test_safe_extract_unpacks_and_refuses_paths_outside(self):
        good = os.path.join(self.tmp, "good.zip")
        with zipfile.ZipFile(good, "w") as archive:
            archive.writestr("SciForge/InitGui.py", "x")
            archive.writestr("install_update.ps1", "y")
        out = os.path.join(self.tmp, "out")
        self.assertEqual(uc.safe_extract(good, out), 2)
        self.assertTrue(os.path.isfile(os.path.join(out, "SciForge", "InitGui.py")))
        bad = os.path.join(self.tmp, "bad.zip")
        with zipfile.ZipFile(bad, "w") as archive:
            archive.writestr("../escaped.txt", "x")
        with self.assertRaises(ValueError):
            uc.safe_extract(bad, os.path.join(self.tmp, "out2"))
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "escaped.txt")))

    def test_updates_dir(self):
        path = uc.updates_dir("/home/u/.config/SciForge-data", "sciforge-v0.1.0-beta.2")
        self.assertTrue(path.endswith(os.path.join("SciForge", "updates", "0.1.0-beta.2")))
        self.assertTrue(uc.updates_dir("/x", "junk").endswith("unknown"))

    def test_format_size(self):
        self.assertEqual(uc.format_size(0), "")
        self.assertEqual(uc.format_size("x"), "")
        self.assertEqual(uc.format_size(500), "500 bytes")
        self.assertEqual(uc.format_size(4 * 1024 * 1024), "4.0 MB")


class Timing(unittest.TestCase):
    def test_due(self):
        day = uc.CHECK_EVERY
        self.assertTrue(uc.due(0, 1000))
        self.assertTrue(uc.due(None, 1000))
        self.assertFalse(uc.due(1000, 1000 + day - 1))
        self.assertTrue(uc.due(1000, 1000 + day))
        self.assertTrue(uc.due(5000, 1000))  # the clock went backwards
        self.assertTrue(uc.due("junk", 1000))

    def test_handover_for_the_module_update(self):
        argv = uc.handover_argv("module", 4321, target="C:\\Program Files\\SciForge", script="C:\\u\\install_update.ps1")
        self.assertEqual(argv[0], "powershell.exe")
        tail = argv[argv.index("-File") :]
        self.assertEqual(
            tail,
            ["-File", "C:\\u\\install_update.ps1", "-Target", "C:\\Program Files\\SciForge",
             "-WaitPid", "4321", "-Restart", "-Quiet"],
        )  # fmt: skip

    def test_handover_for_the_installer_quotes_the_path(self):
        argv = uc.handover_argv("installer", 77, installer="C:\\Users\\O'Neil\\u\\SciForge-installer.exe")
        command = argv[argv.index("-Command") + 1]
        self.assertIn("Wait-Process -Id 77", command)
        self.assertIn("Start-Process -FilePath 'C:\\Users\\O''Neil\\u\\SciForge-installer.exe'", command)

    def test_the_core_id_defaults_to_unknown(self):
        # (a full build writes its real core id into core_info.py: only a source tree or a test
        # run's quick update says "unknown", so the module is looked at, not assumed)
        from sciforge import core_info

        self.assertEqual(uc.installed_core(), str(core_info.CORE or "").strip())
        saved = core_info.CORE
        try:
            core_info.CORE = ""
            self.assertEqual(uc.installed_core(), "")
        finally:
            core_info.CORE = saved


class Network(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="sciforge-update-")
        self.fake = FakeGitHub()
        self.old_base = uc.API_BASE
        uc.API_BASE = self.fake.base

    def tearDown(self):
        uc.API_BASE = self.old_base
        self.fake.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def listing(self, *entries):
        self.fake.routes["/repos/%s/releases?per_page=10" % uc.REPO] = (200, json.dumps(list(entries)).encode())

    def test_the_request_names_us_and_nothing_else(self):
        self.listing()
        uc.check("0.1.0-beta", uc.BETA)
        path, headers = self.fake.seen[0]
        self.assertEqual(path, "/repos/Luca0422git/SciForge/releases?per_page=10")
        self.assertEqual(headers["User-Agent"], "SciForge/0.1.0-beta")
        self.assertNotIn("Authorization", headers)
        self.assertNotIn("Cookie", headers)

    def test_newer_release_with_its_manifest(self):
        manifest = dict(GOOD, core="abc1234")
        self.fake.routes["/dl/sciforge-release.json"] = (200, json.dumps(manifest).encode())
        self.listing(
            release_entry("sciforge-v0.1.0-beta", True),
            release_entry(
                "sciforge-v0.1.0-beta.2", True, assets={uc.MANIFEST_NAME: self.fake.base + "/dl/sciforge-release.json"}
            ),
        )
        got = uc.check("0.1.0-beta", uc.BETA)
        self.assertEqual(got["status"], "newer")
        self.assertEqual(got["release"]["version"], "0.1.0-beta.2")
        self.assertEqual(got["release"]["manifest"]["core"], "abc1234")

    def test_up_to_date(self):
        self.listing(release_entry("sciforge-v0.1.0-beta", True))
        self.assertEqual(uc.check("0.1.0-beta", uc.BETA), {"status": "current", "release": None})

    def test_a_newer_release_without_a_manifest_is_still_offered(self):
        self.listing(release_entry("sciforge-v0.1.0-beta.2", True))
        got = uc.check("0.1.0-beta", uc.BETA)
        self.assertEqual(got["status"], "newer")
        self.assertIsNone(got["release"]["manifest"])

    def test_a_broken_manifest_does_not_hide_the_release(self):
        self.fake.routes["/dl/m.json"] = (200, b"{{{")
        self.listing(release_entry("sciforge-v0.1.0-beta.2", True, assets={uc.MANIFEST_NAME: self.fake.base + "/dl/m.json"}))
        got = uc.check("0.1.0-beta", uc.BETA)
        self.assertIsNone(got["release"]["manifest"])

    def test_offline(self):
        uc.API_BASE = closed_port_base()
        with self.assertRaises(uc.UpdateError) as caught:
            uc.check("0.1.0-beta", uc.BETA)
        self.assertEqual(caught.exception.code, "offline")
        self.assertIn("Could not reach GitHub", caught.exception.text)

    def test_rate_limited_and_other_http_answers(self):
        path = "/repos/%s/releases?per_page=10" % uc.REPO
        self.fake.routes[path] = (403, b'{"message":"API rate limit exceeded"}')
        with self.assertRaises(uc.UpdateError) as caught:
            uc.check("0.1.0-beta", uc.BETA)
        self.assertEqual(caught.exception.code, "rate")
        self.fake.routes[path] = (500, b"oops")
        with self.assertRaises(uc.UpdateError) as caught:
            uc.check("0.1.0-beta", uc.BETA)
        self.assertEqual(caught.exception.code, "http")

    def test_malformed_answers(self):
        path = "/repos/%s/releases?per_page=10" % uc.REPO
        for body in (b"not json", b"{}", b'{"message":"Not Found"}', b"", b"\xff\xfe", b"5"):
            self.fake.routes[path] = (200, body)
            with self.assertRaises(uc.UpdateError, msg=body) as caught:
                uc.check("0.1.0-beta", uc.BETA)
            self.assertEqual(caught.exception.code, "data", body)

    def test_an_answer_of_junk_entries_is_just_up_to_date(self):
        self.listing(None, 5, {"tag_name": "nightly"}, release_entry("sciforge-v0.1.0-beta.2", draft=True))
        self.assertEqual(uc.check("0.1.0-beta", uc.BETA)["status"], "current")

    def test_a_test_run_never_goes_online_but_may_use_the_fake_github(self):
        old = os.environ.get("SCIFORGE_NO_INTERNET")
        os.environ["SCIFORGE_NO_INTERNET"] = "1"
        try:
            self.assertTrue(uc.blocked("https://api.github.com/repos/x/releases"))
            self.assertTrue(uc.blocked("https://objects.githubusercontent.com/f"))
            self.assertFalse(uc.blocked(self.fake.base + "/x"))
            self.assertFalse(uc.blocked("http://localhost:8000/x"))
            uc.API_BASE = "https://api.github.com"
            with self.assertRaises(uc.UpdateError) as caught:
                uc.check("0.1.0-beta", uc.BETA)
            self.assertEqual(caught.exception.code, "offline")
            self.assertIn("test run", caught.exception.text)
            self.assertEqual(uc.download("https://github.com/x", os.path.join(self.tmp, "f"), "0" * 64)[0], "error")
            uc.API_BASE = self.fake.base
            self.listing()
            self.assertEqual(uc.check("0.1.0-beta", uc.BETA)["status"], "current")
        finally:
            if old is None:
                del os.environ["SCIFORGE_NO_INTERNET"]
            else:
                os.environ["SCIFORGE_NO_INTERNET"] = old

    def test_only_web_addresses_are_fetched(self):
        for url in ("file:///etc/passwd", "ftp://example.org/x", "", "javascript:1"):
            with self.assertRaises(uc.UpdateError):
                uc.http_get(url)

    def test_a_huge_answer_is_refused(self):
        self.fake.routes["/big"] = (200, b"x" * 5000)
        with self.assertRaises(uc.UpdateError):
            uc.http_get(self.fake.base + "/big", limit=1000)

    def test_download_ok_progress_and_kept_file(self):
        data = os.urandom(300 * 1024)
        self.fake.routes["/f"] = (200, data)
        dest = os.path.join(self.tmp, "sub", "f.bin")
        steps = []
        got = uc.download(self.fake.base + "/f", dest, sha(data), lambda d, t: steps.append((d, t)))
        self.assertEqual(got, ("ok", dest))
        self.assertEqual(read(dest), data)
        self.assertEqual(steps[-1], (len(data), len(data)))
        self.assertFalse(os.path.exists(dest + ".part"))
        # a second call finds the right file and does not ask again
        count = len(self.fake.seen)
        self.assertEqual(uc.download(self.fake.base + "/f", dest, sha(data))[0], "ok")
        self.assertEqual(len(self.fake.seen), count)

    def test_download_with_a_wrong_hash_deletes_the_file(self):
        self.fake.routes["/f"] = (200, b"the real file")
        dest = os.path.join(self.tmp, "f.bin")
        status, _text = uc.download(self.fake.base + "/f", dest, sha(b"something else"))
        self.assertEqual(status, "mismatch")
        self.assertFalse(os.path.exists(dest))
        self.assertFalse(os.path.exists(dest + ".part"))

    def test_a_wrong_file_already_there_is_replaced_or_refused_never_trusted(self):
        dest = os.path.join(self.tmp, "f.bin")
        with open(dest, "wb") as handle:
            handle.write(b"tampered")
        self.fake.routes["/f"] = (200, b"the real file")
        self.assertEqual(uc.download(self.fake.base + "/f", dest, sha(b"the real file"))[0], "ok")
        self.assertEqual(read(dest), b"the real file")

    def test_download_can_be_cancelled(self):
        self.fake.routes["/f"] = (200, os.urandom(500 * 1024))
        dest = os.path.join(self.tmp, "f.bin")
        calls = []

        def stop():
            calls.append(1)
            return len(calls) > 2

        status, _text = uc.download(self.fake.base + "/f", dest, "0" * 64, cancelled=stop)
        self.assertEqual(status, "cancelled")
        self.assertFalse(os.path.exists(dest))
        self.assertFalse(os.path.exists(dest + ".part"))

    def test_download_offline_and_not_found(self):
        dest = os.path.join(self.tmp, "f.bin")
        self.assertEqual(uc.download(closed_port_base() + "/f", dest, "0" * 64)[0], "offline")
        self.assertEqual(uc.download(self.fake.base + "/missing", dest, "0" * 64)[0], "error")
        self.assertEqual(uc.download("file:///etc/passwd", dest, "0" * 64)[0], "error")
        self.assertFalse(os.path.exists(dest))


if __name__ == "__main__":
    unittest.main()
