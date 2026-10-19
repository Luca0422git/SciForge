# SPDX-License-Identifier: LGPL-2.1-or-later
"""MCP JSON-RPC handling (sciforge/ai/mcp_core.py) with a fake SciForge. Runs without
FreeCAD."""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sciforge.ai import mcp_core, tools_core  # noqa: E402


def request(method, params=None, request_id=1):
    message = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        message["params"] = params
    return message


class FakeSciForge:
    def __init__(self, answer=None, fail=False):
        self.calls = []
        self.answer = answer or {"text": "done", "image_png_base64": None, "is_error": False}
        self.fail = fail

    def __call__(self, name, args):
        self.calls.append((name, args))
        if self.fail:
            raise RuntimeError("the bridge broke")
        return self.answer


class Lifecycle(unittest.TestCase):
    def handle(self, message, fake=None):
        return mcp_core.handle(message, fake or FakeSciForge(), version="1.2.3")

    def test_initialize_echoes_a_supported_version(self):
        for version in ("2025-06-18", "2025-03-26", "2024-11-05"):
            reply = self.handle(request("initialize", {"protocolVersion": version}))
            self.assertEqual(reply["jsonrpc"], "2.0")
            self.assertEqual(reply["id"], 1)
            result = reply["result"]
            self.assertEqual(result["protocolVersion"], version)
            self.assertEqual(result["capabilities"], {"tools": {"listChanged": False}})
            self.assertEqual(
                result["serverInfo"], {"name": "sciforge", "title": "SciForge", "version": "1.2.3"}
            )
            self.assertIn("mm", result["instructions"])
            self.assertIn("get_design", result["instructions"])
            self.assertIn("undo", result["instructions"])

    def test_initialize_offers_the_newest_for_an_unknown_version(self):
        reply = self.handle(request("initialize", {"protocolVersion": "2099-01-01"}))
        self.assertEqual(reply["result"]["protocolVersion"], mcp_core.LATEST)
        self.assertIn(mcp_core.LATEST, mcp_core.PROTOCOL_VERSIONS)

    def test_initialize_needs_a_version(self):
        reply = self.handle(request("initialize", {}))
        self.assertEqual(reply["error"]["code"], mcp_core.INVALID_PARAMS)

    def test_notifications_get_no_reply(self):
        fake = FakeSciForge()
        self.assertIsNone(self.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}))
        self.assertIsNone(
            self.handle(
                {"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": 3}}
            )
        )
        self.assertIsNone(
            self.handle(
                {"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "undo"}}, fake
            )
        )
        self.assertEqual(fake.calls, [])  # a notification never runs a tool
        self.assertIsNone(self.handle({"jsonrpc": "2.0", "id": 5, "result": {}}))

    def test_ping(self):
        self.assertEqual(
            self.handle(request("ping", request_id="a")),
            {"jsonrpc": "2.0", "id": "a", "result": {}},
        )

    def test_unknown_method(self):
        reply = self.handle(request("resources/list"))
        self.assertEqual(reply["error"]["code"], mcp_core.METHOD_NOT_FOUND)
        self.assertEqual(reply["id"], 1)

    def test_bad_requests(self):
        reply = self.handle({"id": 1, "method": "ping"})  # no jsonrpc
        self.assertEqual(reply["error"]["code"], mcp_core.INVALID_REQUEST)
        reply = self.handle({"jsonrpc": "2.0", "id": True, "method": "ping"})
        self.assertEqual(reply["error"]["code"], mcp_core.INVALID_REQUEST)
        self.assertIsNone(reply["id"])
        reply = self.handle(request("ping", params=[1, 2]))
        self.assertEqual(reply["error"]["code"], mcp_core.INVALID_PARAMS)
        reply = self.handle("not a dict")
        self.assertEqual(reply["error"]["code"], mcp_core.INVALID_REQUEST)


class Tools(unittest.TestCase):
    def handle(self, message, fake):
        return mcp_core.handle(message, fake, version="1")

    def test_tools_list(self):
        reply = self.handle(request("tools/list"), FakeSciForge())
        self.assertEqual(reply["result"]["tools"], tools_core.mcp_tools())
        self.assertNotIn("nextCursor", reply["result"])

    def test_call_happy_path(self):
        fake = FakeSciForge({"text": "Extruded 10 mm", "is_error": False})
        args = {"profile": "s1", "distance": 10}
        reply = self.handle(request("tools/call", {"name": "extrude", "arguments": args}), fake)
        self.assertEqual(fake.calls, [("extrude", args)])
        self.assertEqual(
            reply["result"],
            {"content": [{"type": "text", "text": "Extruded 10 mm"}], "isError": False},
        )

    def test_call_with_image(self):
        fake = FakeSciForge({"text": "iso view", "image_png_base64": "iVBORw0K", "is_error": False})
        reply = self.handle(request("tools/call", {"name": "screenshot"}), fake)
        self.assertEqual(fake.calls, [("screenshot", {})])
        content = reply["result"]["content"]
        self.assertEqual(content[1], {"type": "image", "data": "iVBORw0K", "mimeType": "image/png"})

    def test_bridge_error_is_a_tool_error(self):
        fake = FakeSciForge({"text": "SciForge is busy", "is_error": True})
        reply = self.handle(request("tools/call", {"name": "undo", "arguments": {}}), fake)
        self.assertTrue(reply["result"]["isError"])

    def test_validation_problems_are_tool_errors(self):
        fake = FakeSciForge()
        args = {"edges": {"count": 4}, "radius": -1}
        reply = self.handle(request("tools/call", {"name": "fillet", "arguments": args}), fake)
        self.assertEqual(fake.calls, [])
        self.assertTrue(reply["result"]["isError"])
        self.assertIn("radius must be a number above 0", reply["result"]["content"][0]["text"])

    def test_unknown_tool_and_bad_params(self):
        fake = FakeSciForge()
        reply = self.handle(request("tools/call", {"name": "format_disk"}), fake)
        self.assertEqual(reply["error"]["code"], mcp_core.INVALID_PARAMS)
        reply = self.handle(request("tools/call", {"name": "undo", "arguments": [1]}), fake)
        self.assertEqual(reply["error"]["code"], mcp_core.INVALID_PARAMS)
        reply = self.handle(request("tools/call", {}), fake)
        self.assertEqual(reply["error"]["code"], mcp_core.INVALID_PARAMS)
        self.assertEqual(fake.calls, [])

    def test_a_failing_bridge_never_escapes(self):
        reply = self.handle(request("tools/call", {"name": "undo"}), FakeSciForge(fail=True))
        self.assertTrue(reply["result"]["isError"])
        self.assertIn("the bridge broke", reply["result"]["content"][0]["text"])
        reply = self.handle(request("tools/call", {"name": "undo"}), lambda name, args: None)
        self.assertTrue(reply["result"]["isError"])


class Framing(unittest.TestCase):
    def test_parse_line(self):
        message, error = mcp_core.parse_line(b'{"jsonrpc": "2.0", "id": 1, "method": "ping"}\n')
        self.assertEqual(message["method"], "ping")
        self.assertIsNone(error)
        self.assertEqual(mcp_core.parse_line("   \r\n"), (None, None))

    def test_parse_error(self):
        message, error = mcp_core.parse_line("{not json")
        self.assertIsNone(message)
        self.assertEqual(error["error"]["code"], mcp_core.PARSE_ERROR)
        self.assertIsNone(error["id"])
        _, error = mcp_core.parse_line(b"\xff\xfe")
        self.assertEqual(error["error"]["code"], mcp_core.PARSE_ERROR)

    def test_batch_refused(self):
        line = json.dumps([{"jsonrpc": "2.0", "id": 1, "method": "ping"}])
        message, error = mcp_core.parse_line(line)
        self.assertIsNone(message)
        self.assertEqual(error["error"]["code"], mcp_core.INVALID_REQUEST)
        self.assertIn("batch", error["error"]["message"])
        _, error = mcp_core.parse_line("42")
        self.assertEqual(error["error"]["code"], mcp_core.INVALID_REQUEST)

    def test_encode_is_one_line(self):
        data = mcp_core.encode({"jsonrpc": "2.0", "id": 1, "result": {"text": "a\nb é"}})
        self.assertTrue(data.endswith(b"\n"))
        self.assertEqual(data.count(b"\n"), 1)
        self.assertEqual(json.loads(data.decode("utf-8"))["result"]["text"], "a\nb é")


if __name__ == "__main__":
    unittest.main()
