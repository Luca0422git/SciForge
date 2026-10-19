# SPDX-License-Identifier: LGPL-2.1-or-later
"""The AI bridge's file, key and message format (sciforge/ai/bridge_core.py). Runs without
FreeCAD."""

import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sciforge.ai import bridge_core  # noqa: E402


class BridgeFile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = bridge_core.bridge_path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_path(self):
        self.assertEqual(self.path, os.path.join(self.tmp.name, "SciForge", "ai", "bridge.json"))

    def test_round_trip(self):
        key = bridge_core.make_key()
        self.assertGreaterEqual(len(key), 40)
        self.assertNotEqual(key, bridge_core.make_key())
        info = bridge_core.bridge_info(50123, key, 4242)
        bridge_core.write_bridge_file(self.path, info)
        self.assertEqual(
            bridge_core.read_bridge_file(self.path), {"port": 50123, "key": key, "pid": 4242}
        )
        bridge_core.write_bridge_file(self.path, bridge_core.bridge_info(50124, key, 4242))
        self.assertEqual(bridge_core.read_bridge_file(self.path)["port"], 50124)
        leftovers = [n for n in os.listdir(os.path.dirname(self.path)) if n != "bridge.json"]
        self.assertEqual(leftovers, [])

    def test_default_pid_is_this_process(self):
        self.assertEqual(bridge_core.bridge_info(1, "k")["pid"], os.getpid())

    @unittest.skipUnless(os.name == "posix", "owner-only file modes are POSIX")
    def test_owner_only(self):
        bridge_core.write_bridge_file(self.path, bridge_core.bridge_info(1, "k", 1))
        self.assertEqual(stat.S_IMODE(os.stat(self.path).st_mode), 0o600)

    def test_tolerant_read(self):
        self.assertIsNone(bridge_core.read_bridge_file(self.path))  # missing
        os.makedirs(os.path.dirname(self.path))
        bad = [
            "{broken",
            "[]",
            json.dumps({"port": "80", "key": "k"}),
            json.dumps({"port": 0, "key": "k"}),
            json.dumps({"port": 70000, "key": "k"}),
            json.dumps({"port": True, "key": "k"}),
            json.dumps({"port": 80, "key": ""}),
            json.dumps({"port": 80}),
        ]
        for text in bad:
            with open(self.path, "w", encoding="utf-8") as handle:
                handle.write(text)
            self.assertIsNone(bridge_core.read_bridge_file(self.path), text)
        with open(self.path, "w", encoding="utf-8-sig") as handle:  # a BOM, a bad pid
            handle.write(json.dumps({"port": 80, "key": "k", "pid": "x"}))
        self.assertEqual(
            bridge_core.read_bridge_file(self.path), {"port": 80, "key": "k", "pid": None}
        )
        self.assertIsNone(bridge_core.read_bridge_file(self.tmp.name))  # a folder

    def test_remove_only_our_own(self):
        bridge_core.write_bridge_file(self.path, bridge_core.bridge_info(1, "k", 111))
        self.assertFalse(bridge_core.remove_bridge_file(self.path, pid=222))
        self.assertTrue(os.path.exists(self.path))
        self.assertTrue(bridge_core.remove_bridge_file(self.path, pid=111))
        self.assertFalse(os.path.exists(self.path))
        self.assertFalse(bridge_core.remove_bridge_file(self.path))


class Keys(unittest.TestCase):
    def test_key_ok(self):
        self.assertTrue(bridge_core.key_ok("abc", "abc"))
        self.assertFalse(bridge_core.key_ok("abd", "abc"))
        self.assertFalse(bridge_core.key_ok(None, "abc"))
        self.assertFalse(bridge_core.key_ok("", ""))
        self.assertFalse(bridge_core.key_ok("é", "e"))

    def test_check_request(self):
        check = bridge_core.check_request
        self.assertEqual(check("POST", "/call", "k", "k", None, 10), (200, ""))
        self.assertEqual(check("GET", "/call", "k", "k")[0], 404)
        self.assertEqual(check("POST", "/other", "k", "k")[0], 404)
        self.assertEqual(check("POST", "/call", "x", "k")[0], 403)
        self.assertEqual(check("POST", "/call", "k", "k", "https://evil.example")[0], 403)
        self.assertEqual(check("POST", "/call", "k", "k", None, 10**9)[0], 413)


class Envelope(unittest.TestCase):
    def test_request_round_trip(self):
        body = bridge_core.encode_request("extrude", {"distance": 10})
        self.assertEqual(bridge_core.decode_request(body), ("extrude", {"distance": 10}))
        self.assertEqual(
            bridge_core.decode_request(b'{"tool": "undo", "args": null}'), ("undo", {})
        )
        for bad in (b"nope", b"[]", b'{"args": {}}', b'{"tool": "x", "args": [1]}', b"\xff"):
            with self.assertRaises(bridge_core.BridgeError):
                bridge_core.decode_request(bad)

    def test_result_round_trip(self):
        answer = bridge_core.result("ok", "iVBOR", False)
        self.assertEqual(bridge_core.decode_result(bridge_core.encode_result(answer)), answer)
        error = bridge_core.error_result("busy")
        self.assertEqual(
            bridge_core.decode_result(bridge_core.encode_result(error)),
            {"text": "busy", "image_png_base64": None, "is_error": True},
        )

    def test_unreadable_answers(self):
        for body in (b"<html>", b"[]", b'{"is_error": false}', None):
            answer = bridge_core.decode_result(body)
            self.assertTrue(answer["is_error"])
            self.assertEqual(answer["text"], bridge_core.UNREADABLE)

    def test_not_running_sentence(self):
        self.assertIn("Preferences > AI", bridge_core.NOT_RUNNING)
        self.assertTrue(bridge_core.NOT_RUNNING.endswith("."))


class Processes(unittest.TestCase):
    def test_pid_alive(self):
        self.assertTrue(bridge_core.pid_alive(os.getpid()))
        self.assertTrue(bridge_core.pid_alive(None))
        self.assertFalse(bridge_core.pid_alive(0))
        child = subprocess.Popen([sys.executable, "-c", "pass"])
        child.wait()
        self.assertFalse(bridge_core.pid_alive(child.pid))


if __name__ == "__main__":
    unittest.main()
