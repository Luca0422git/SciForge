# SPDX-License-Identifier: LGPL-2.1-or-later
"""sciforge/ai/sciforge_mcp.py as an AI app runs it: a separate process spoken to over
stdin / stdout, first with SciForge not running, then with a fake bridge (http.server on
127.0.0.1) standing in for SciForge. Runs without FreeCAD."""

import http.server
import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from sciforge.ai import bridge_core, sciforge_mcp, tools_core  # noqa: E402

SCRIPT = os.path.join(ROOT, "sciforge", "ai", "sciforge_mcp.py")
WAIT = 20  # seconds


class FakeBridge:
    """Answers POST /call like SciForge's bridge, with a fixed key."""

    def __init__(self, key):
        self.key = key
        self.calls = []
        owner = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length") or 0)
                status, reason = bridge_core.check_request(
                    "POST",
                    self.path,
                    self.headers.get(bridge_core.KEY_HEADER),
                    owner.key,
                    self.headers.get("Origin"),
                    length,
                )
                if status != 200:
                    self._send(status, bridge_core.encode_result(bridge_core.error_result(reason)))
                    return
                tool, args = bridge_core.decode_request(self.rfile.read(length))
                owner.calls.append((tool, args))
                if tool == "screenshot":
                    answer = bridge_core.result("the iso view", "iVBORw0KGgo=")
                elif tool == "undo":
                    answer = bridge_core.error_result("SciForge is busy: finish the open dialog")
                else:
                    answer = bridge_core.result("1 body, volume 8000 mm3")
                self._send(200, bridge_core.encode_result(answer))

            def _send(self, status, body):
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


class McpProcess:
    def __init__(self, bridge_file):
        env = dict(os.environ)
        env[sciforge_mcp.ENV_BRIDGE_FILE] = bridge_file
        env["PYTHONIOENCODING"] = "utf-8"
        self.process = subprocess.Popen(
            [sys.executable, SCRIPT],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            cwd=tempfile.gettempdir(),
        )
        self.lines = queue.Queue()
        self.stderr = []
        threading.Thread(target=self._read, daemon=True).start()
        threading.Thread(target=self._read_err, daemon=True).start()
        self.next_id = 0

    def _read(self):
        for line in iter(self.process.stdout.readline, b""):
            self.lines.put(line)
        self.lines.put(None)

    def _read_err(self):
        for line in iter(self.process.stderr.readline, b""):
            self.stderr.append(line.decode("utf-8", "replace"))

    def send(self, message):
        self.process.stdin.write((json.dumps(message) + "\n").encode("utf-8"))
        self.process.stdin.flush()

    def receive(self):
        line = self.lines.get(timeout=WAIT)
        if line is None:
            raise AssertionError("the server stopped: %s" % "".join(self.stderr))
        return json.loads(line.decode("utf-8"))

    def request(self, method, params=None):
        self.next_id += 1
        message = {"jsonrpc": "2.0", "id": self.next_id, "method": method}
        if params is not None:
            message["params"] = params
        self.send(message)
        reply = self.receive()
        assert reply["id"] == self.next_id, reply
        return reply

    def close(self):
        try:
            self.process.stdin.close()
        except OSError:
            pass
        code = self.process.wait(timeout=WAIT)
        self.process.stdout.close()
        self.process.stderr.close()
        return code


class ServerProcess(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.bridge_file = bridge_core.bridge_path(self.tmp.name)
        self.mcp = McpProcess(self.bridge_file)
        self.addCleanup(self.tmp.cleanup)

    def tearDown(self):
        if self.mcp.process.poll() is None:
            self.mcp.close()

    def start(self):
        reply = self.mcp.request(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1"},
            },
        )
        self.assertEqual(reply["result"]["protocolVersion"], "2025-06-18")
        self.assertEqual(reply["result"]["serverInfo"]["name"], "sciforge")
        self.mcp.send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def call(self, name, args=None):
        reply = self.mcp.request("tools/call", {"name": name, "arguments": args or {}})
        return reply["result"]

    def test_without_sciforge(self):
        self.start()
        tools = self.mcp.request("tools/list")["result"]["tools"]
        self.assertEqual([t["name"] for t in tools], list(tools_core.TOOL_NAMES))
        result = self.call("get_design")
        self.assertTrue(result["isError"])
        self.assertEqual(result["content"][0]["text"], bridge_core.NOT_RUNNING)
        self.assertEqual(self.mcp.request("ping")["result"], {})
        self.mcp.process.stdin.write(b"{broken\n")
        self.mcp.process.stdin.flush()
        self.assertEqual(self.mcp.receive()["error"]["code"], -32700)
        self.assertEqual(self.mcp.close(), 0)  # EOF: a clean exit
        self.assertTrue(any(line.startswith("[SciForge]") for line in self.mcp.stderr))

    def test_stale_bridge_file(self):
        child = subprocess.Popen([sys.executable, "-c", "pass"])
        child.wait()
        bridge_core.write_bridge_file(self.bridge_file, bridge_core.bridge_info(1, "k", child.pid))
        self.start()
        result = self.call("get_design")
        self.assertEqual(result["content"][0]["text"], bridge_core.NOT_RUNNING)

    def test_with_a_fake_sciforge(self):
        self.start()
        key = bridge_core.make_key()
        bridge = FakeBridge(key)
        self.addCleanup(bridge.close)
        # SciForge starts after the AI app: the file is read on each call
        bridge_core.write_bridge_file(self.bridge_file, bridge_core.bridge_info(bridge.port, key))
        result = self.call("get_design")
        self.assertEqual(
            result,
            {"content": [{"type": "text", "text": "1 body, volume 8000 mm3"}], "isError": False},
        )
        result = self.call("screenshot", {"view": "iso"})
        self.assertEqual(
            result["content"][1], {"type": "image", "data": "iVBORw0KGgo=", "mimeType": "image/png"}
        )
        result = self.call("undo")
        self.assertTrue(result["isError"])
        self.assertIn("busy", result["content"][0]["text"])
        result = self.call("fillet", {"radius": 0, "edges": {"count": 1}})  # never sent
        self.assertTrue(result["isError"])
        self.assertEqual([c[0] for c in bridge.calls], ["get_design", "screenshot", "undo"])
        self.assertEqual(bridge.calls[1][1], {"view": "iso"})

        bridge_core.write_bridge_file(
            self.bridge_file, bridge_core.bridge_info(bridge.port, "wrong-key")
        )
        result = self.call("get_design")
        self.assertTrue(result["isError"])
        self.assertEqual(result["content"][0]["text"], bridge_core.BAD_KEY)
        self.assertEqual(len(bridge.calls), 3)
        self.assertEqual(self.mcp.close(), 0)
        log = "".join(self.mcp.stderr)
        self.assertNotIn(key, log)
        self.assertNotIn("wrong-key", log)


class BridgeFileLocation(unittest.TestCase):
    def test_explicit_and_environment(self):
        self.assertEqual(sciforge_mcp.find_bridge_file("/x/b.json", env={}), "/x/b.json")
        env = {sciforge_mcp.ENV_BRIDGE_FILE: "/y/b.json"}
        self.assertEqual(sciforge_mcp.find_bridge_file(None, env=env), "/y/b.json")

    def test_candidates(self):
        with tempfile.TemporaryDirectory() as home:
            share = os.path.join(home, ".local", "share")
            for folder in ("v1-0", "v1-1", "v1-10", "notes"):
                os.makedirs(os.path.join(share, "SciForge", folder))
            dirs = sciforge_mcp.candidate_user_data_dirs({}, "linux", home)
            self.assertEqual(
                dirs[:4],
                [
                    os.path.join(share, "SciForge", "v1-10"),
                    os.path.join(share, "SciForge", "v1-1"),
                    os.path.join(share, "SciForge", "v1-0"),
                    os.path.join(share, "SciForge"),
                ],
            )
            self.assertEqual(dirs[-1], os.path.join(share, "FreeCAD"))
            win = sciforge_mcp.candidate_user_data_dirs({"APPDATA": "C:/AD"}, "win32", home)
            self.assertEqual(
                win, [os.path.join("C:/AD", "SciForge"), os.path.join("C:/AD", "FreeCAD")]
            )
            mac = sciforge_mcp.candidate_user_data_dirs({}, "darwin", home)
            self.assertEqual(
                mac[0], os.path.join(home, "Library", "Application Support", "SciForge")
            )
            custom = sciforge_mcp.candidate_user_data_dirs(
                {"FREECAD_USER_DATA": "/data"}, "linux", home
            )
            self.assertEqual(custom[0], "/data")
            path = bridge_core.bridge_path(os.path.join(share, "SciForge", "v1-1"))
            bridge_core.write_bridge_file(path, bridge_core.bridge_info(1, "k"))
            files = sciforge_mcp.candidate_bridge_files({}, "linux", home)
            self.assertIn(path, files)


if __name__ == "__main__":
    unittest.main()
