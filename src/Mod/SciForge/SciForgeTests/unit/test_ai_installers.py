# SPDX-License-Identifier: LGPL-2.1-or-later
"""The "+ Add an AI" file writers (sciforge/ai/installers.py), in temporary folders. Runs
without FreeCAD."""

import glob
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from sciforge.ai import installers, tools_core  # noqa: E402

PY = "/opt/SciForge/bin/python"
SCRIPT = "/opt/SciForge/Mod/SciForge/sciforge/ai/sciforge_mcp.py"
NOW = 1767225600  # a fixed time for the backup names


def _read(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


class Paths(unittest.TestCase):
    def test_server_command(self):
        self.assertEqual(installers.server_command(PY, SCRIPT), (PY, [SCRIPT]))
        self.assertEqual(
            installers.server_command(PY, SCRIPT, "/b.json"),
            (PY, [SCRIPT, "--bridge-file", "/b.json"]),
        )

    def test_config_paths(self):
        path = installers.claude_desktop_config_path(
            "win32", {"APPDATA": r"C:\Users\l\AppData\Roaming"}, "/h"
        )
        self.assertEqual(
            path,
            os.path.join(r"C:\Users\l\AppData\Roaming", "Claude", "claude_desktop_config.json"),
        )
        self.assertEqual(
            installers.claude_desktop_config_path("darwin", {}, "/h"),
            os.path.join(
                "/h", "Library", "Application Support", "Claude", "claude_desktop_config.json"
            ),
        )
        self.assertEqual(
            installers.claude_desktop_config_path("linux", {}, "/h"),
            os.path.join("/h", ".config", "Claude", "claude_desktop_config.json"),
        )
        self.assertEqual(
            installers.gemini_settings_path("/h"), os.path.join("/h", ".gemini", "settings.json")
        )


class JsonConfig(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "Claude", "claude_desktop_config.json")

    def backups(self):
        return glob.glob(self.path + ".sciforge-backup-*")

    def test_new_config(self):
        text = installers.add_to_claude_desktop(PY, [SCRIPT], path=self.path, now=NOW)
        self.assertIn("Added SciForge", text)
        self.assertIn("start it again", text)
        self.assertEqual(
            _read(self.path), {"mcpServers": {"sciforge": {"command": PY, "args": [SCRIPT]}}}
        )
        self.assertEqual(self.backups(), [])

    def test_existing_config_kept_and_backed_up(self):
        old = {"theme": "dark", "mcpServers": {"other": {"command": "node", "args": ["x.js"]}}}
        _write(self.path, json.dumps(old))
        text = installers.add_to_json_config(self.path, PY, [SCRIPT], now=NOW)
        data = _read(self.path)
        self.assertEqual(data["theme"], "dark")
        self.assertEqual(data["mcpServers"]["other"], old["mcpServers"]["other"])
        self.assertEqual(data["mcpServers"]["sciforge"], {"command": PY, "args": [SCRIPT]})
        backups = self.backups()
        self.assertEqual(len(backups), 1)
        self.assertIn(backups[0], text)
        self.assertEqual(_read(backups[0]), old)
        # the same again changes nothing; a new script path replaces the entry
        self.assertIn("already", installers.add_to_json_config(self.path, PY, [SCRIPT], now=NOW))
        self.assertEqual(len(self.backups()), 1)
        text = installers.add_to_json_config(self.path, PY, ["/new/sciforge_mcp.py"], now=NOW)
        self.assertIn("Updated", text)
        self.assertEqual(len(self.backups()), 2)
        self.assertEqual(
            _read(self.path)["mcpServers"]["sciforge"]["args"], ["/new/sciforge_mcp.py"]
        )

    def test_broken_config_refused_untouched(self):
        for text in ('{"mcpServers": {', "[1, 2]", '{"mcpServers": []}', "// comment\n{}"):
            _write(self.path, text)
            with self.assertRaises(installers.InstallError) as caught:
                installers.add_to_json_config(self.path, PY, [SCRIPT], now=NOW)
            self.assertIn(self.path, str(caught.exception))
            with open(self.path, encoding="utf-8") as handle:
                self.assertEqual(handle.read(), text)
            self.assertEqual(self.backups(), [])

    def test_empty_file_and_bom(self):
        _write(self.path, "")
        installers.add_to_json_config(self.path, PY, [SCRIPT], now=NOW)
        self.assertIn("sciforge", _read(self.path)["mcpServers"])
        with open(self.path, "w", encoding="utf-8-sig") as handle:
            handle.write('{"a": 1}')
        installers.add_to_json_config(self.path, PY, [SCRIPT], now=NOW)
        self.assertEqual(_read(self.path)["a"], 1)

    def test_uninstall(self):
        self.assertIn("nothing changed", installers.remove_from_json_config(self.path, now=NOW))
        self.assertFalse(os.path.exists(self.path))
        old = {"mcpServers": {"other": {"command": "x"}, "sciforge": {"command": PY, "args": []}}}
        _write(self.path, json.dumps(old))
        text = installers.remove_from_claude_desktop(path=self.path, now=NOW)
        self.assertIn("Removed SciForge", text)
        self.assertEqual(_read(self.path), {"mcpServers": {"other": {"command": "x"}}})
        self.assertEqual(len(self.backups()), 1)
        self.assertEqual(_read(self.backups()[0]), old)
        self.assertIn("nothing changed", installers.remove_from_json_config(self.path, now=NOW))
        _write(self.path, "{broken")
        with self.assertRaises(installers.InstallError):
            installers.remove_from_json_config(self.path, now=NOW)

    def test_gemini(self):
        path = os.path.join(self.tmp.name, ".gemini", "settings.json")
        _write(path, json.dumps({"theme": "GitHub"}))
        text = installers.add_to_gemini(
            PY, [SCRIPT, "--bridge-file", "/b.json"], path=path, now=NOW
        )
        self.assertIn("/mcp", text)
        self.assertEqual(
            _read(path),
            {
                "theme": "GitHub",
                "mcpServers": {
                    "sciforge": {"command": PY, "args": [SCRIPT, "--bridge-file", "/b.json"]}
                },
            },
        )
        self.assertIn("Removed", installers.remove_from_gemini(path=path, now=NOW))
        self.assertEqual(_read(path), {"theme": "GitHub", "mcpServers": {}})

    @unittest.skipUnless(os.name == "posix", "file modes are POSIX")
    def test_keeps_file_mode(self):
        _write(self.path, "{}")
        os.chmod(self.path, 0o640)
        installers.add_to_json_config(self.path, PY, [SCRIPT], now=NOW)
        self.assertEqual(os.stat(self.path).st_mode & 0o777, 0o640)


class Extension(unittest.TestCase):
    def test_manifest(self):
        data = installers.manifest("0.2.0", PY, bridge_file="/b.json")
        for key in ("manifest_version", "name", "version", "description", "author", "server"):
            self.assertIn(key, data)
        self.assertEqual(data["manifest_version"], "0.3")
        self.assertEqual(data["name"], "sciforge")
        self.assertEqual(data["display_name"], "SciForge")
        self.assertEqual(data["author"], {"name": "SciForge"})
        server = data["server"]
        self.assertEqual(server["type"], "python")
        self.assertEqual(server["entry_point"], installers.ENTRY_POINT)
        self.assertEqual(
            server["mcp_config"],
            {
                "command": PY,
                "args": ["${__dirname}/" + installers.ENTRY_POINT, "--bridge-file", "/b.json"],
                "env": {},
            },
        )
        self.assertEqual([t["name"] for t in data["tools"]], list(tools_core.TOOL_NAMES))
        for tool in data["tools"]:
            self.assertEqual(set(tool), {"name", "description"})
        with self.assertRaises(installers.InstallError):
            installers.manifest("0.2", PY)

    def test_build_mcpb(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "out", "SciForge.mcpb")
            files = installers.mcpb_files(ROOT)
            data = installers.manifest("0.2.0", sys.executable)
            self.assertEqual(installers.build_mcpb(out, files, data), out)
            with zipfile.ZipFile(out) as archive:
                names = archive.namelist()
                self.assertEqual(names[0], "manifest.json")
                self.assertEqual(json.loads(archive.read("manifest.json")), data)
                self.assertIn(installers.ENTRY_POINT, names)
                self.assertIn("server/sciforge/__init__.py", names)
                self.assertIn("server/sciforge/ai/__init__.py", names)
                for name in ("tools_core", "mcp_core", "bridge_core"):
                    self.assertIn("server/sciforge/ai/%s.py" % name, names)
                self.assertFalse([n for n in names if "ops/" in n])
                unpacked = os.path.join(tmp, "unpacked")
                archive.extractall(unpacked)
            # the unpacked extension starts and answers like the installed server
            script = os.path.join(unpacked, *installers.ENTRY_POINT.split("/"))
            line = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}) + "\n"
            done = subprocess.run(
                [sys.executable, script, "--bridge-file", os.path.join(tmp, "none.json")],
                input=line.encode("utf-8"),
                capture_output=True,
                timeout=30,
                cwd=tmp,
            )
            self.assertEqual(done.returncode, 0, done.stderr)
            reply = json.loads(done.stdout.decode("utf-8"))
            self.assertEqual(len(reply["result"]["tools"]), len(tools_core.TOOLS))
            self.assertEqual(os.listdir(os.path.join(tmp, "out")), ["SciForge.mcpb"])

    def test_bad_files_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "x.mcpb")
            data = installers.manifest("1.0.0", PY)
            for name in ("../evil.py", "/abs.py", "manifest.json"):
                with self.assertRaises(installers.InstallError):
                    installers.build_mcpb(out, {name: __file__}, data)
            with self.assertRaises(installers.InstallError):
                installers.build_mcpb(out, {"server/x.py": os.path.join(tmp, "missing.py")}, data)
            self.assertFalse(os.path.exists(out))


class OtherApps(unittest.TestCase):
    def test_text(self):
        text = installers.other_app_text("/opt/Sci Forge/python", [SCRIPT], platform="linux")
        self.assertIn(
            "claude mcp add --transport stdio --scope user sciforge -- '/opt/Sci Forge/python' "
            + SCRIPT,
            text,
        )
        self.assertIn("codex mcp add sciforge -- ", text)
        win = installers.other_app_text(
            r"C:\Program Files\SciForge\bin\python.exe", [r"C:\s.py"], platform="win32"
        )
        self.assertIn(r'-- "C:\Program Files\SciForge\bin\python.exe" C:\s.py', win)


if __name__ == "__main__":
    unittest.main()
