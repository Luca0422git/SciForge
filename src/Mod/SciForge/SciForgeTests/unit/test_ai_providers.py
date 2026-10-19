# SPDX-License-Identifier: LGPL-2.1-or-later
"""The chat panel's provider adapters (sciforge/ai/providers/) against recorded answers in
fixtures_ai/. No network: list_models gets a fake GET, and the urllib helper talks to a
local http.server on 127.0.0.1. Runs without FreeCAD."""

import copy
import http.server
import json
import os
import socket
import sys
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sciforge.ai import providers, tools_core  # noqa: E402
from sciforge.ai.providers import _common, anthropic, gemini, openai, openai_compat  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
KEY = "sk-test-0123456789abcdef"


def fixture(name):
    with open(os.path.join(HERE, "fixtures_ai", name + ".json"), encoding="utf-8") as handle:
        return json.load(handle)


def walk(schema, path="root"):
    """Every (path, sub-schema) of a schema."""
    yield path, schema
    for name, sub in (schema.get("properties") or {}).items():
        yield from walk(sub, path + "." + name)
    if isinstance(schema.get("items"), dict):
        yield from walk(schema["items"], path + "[]")
    for key in ("anyOf", "oneOf"):
        for i, sub in enumerate(schema.get(key) or []):
            yield from walk(sub, "%s.%s[%d]" % (path, key, i))


JSON_TYPES = {"object", "array", "string", "number", "integer", "boolean", "null"}


def check_json_schema(test, schema, where):
    """A well-formed JSON Schema object for function arguments."""
    test.assertEqual(schema.get("type"), "object", where)
    for path, sub in walk(schema):
        test.assertIsInstance(sub, dict, path)
        kinds = sub.get("type")
        if kinds is not None:
            kinds = kinds if isinstance(kinds, list) else [kinds]
            test.assertTrue(set(kinds) <= JSON_TYPES, "%s %s: %s" % (where, path, kinds))
        if "required" in sub:
            test.assertTrue(set(sub["required"]) <= set(sub.get("properties", {})), path)
        if "enum" in sub:
            test.assertTrue(sub["enum"], path)


ADAPTERS = {
    "anthropic": anthropic.Adapter(),
    "openai": openai.Adapter(),
    "gemini": gemini.Adapter(),
    "openai_compat": openai_compat.Adapter(),
}


class Registry(unittest.TestCase):
    def test_four_providers_with_names(self):
        self.assertEqual(
            set(providers.PROVIDERS), {"anthropic", "openai", "gemini", "openai_compat"}
        )
        self.assertEqual(providers.get("anthropic")["display_name"], "Claude (Anthropic)")
        self.assertEqual(providers.get("openai")["display_name"], "ChatGPT (OpenAI)")
        self.assertEqual(providers.get("gemini")["display_name"], "Gemini (Google)")
        self.assertIn("Ollama", providers.get("openai_compat")["display_name"])
        self.assertFalse(providers.get("openai_compat")["needs_key"])
        self.assertTrue(
            all(providers.get(n)["needs_key"] for n in ("anthropic", "openai", "gemini"))
        )
        self.assertIsNone(providers.get("nope"))
        self.assertIsNone(providers.adapter("nope"))
        self.assertEqual(providers.adapter("gemini").name, "gemini")

    def test_default_models(self):
        self.assertEqual(providers.default_model("anthropic"), anthropic.DEFAULT_MODEL)
        self.assertEqual(providers.get("openai")["default_model"], openai.DEFAULT_MODEL)
        # A local server has no fixed model: the first one it lists.
        self.assertEqual(
            providers.default_model("openai_compat", models=["qwen3:8b", "x"]), "qwen3:8b"
        )
        self.assertEqual(providers.default_model("openai_compat", models=[]), "")


class ToolDefinitions(unittest.TestCase):
    def test_every_tool_once_per_adapter(self):
        for name, adapter in ADAPTERS.items():
            _url, _headers, body = adapter.build_request("m", "sys", [], tools_core.TOOLS, 100, KEY)
            json.dumps(body)  # must be plain JSON
            if name == "anthropic":
                names = [t["name"] for t in body["tools"]]
            elif name == "openai":
                names = [t["name"] for t in body["tools"]]
            elif name == "openai_compat":
                names = [t["function"]["name"] for t in body["tools"]]
            else:
                names = [d["name"] for d in body["tools"][0]["functionDeclarations"]]
            self.assertEqual(names, list(tools_core.TOOL_NAMES), name)

    def test_anthropic_tools(self):
        for tool in anthropic.Adapter().tools(tools_core.TOOLS):
            self.assertEqual(set(tool), {"name", "description", "input_schema"})
            check_json_schema(self, tool["input_schema"], tool["name"])

    def test_openai_tools(self):
        for tool in openai.Adapter().tools(tools_core.TOOLS):
            self.assertEqual(tool["type"], "function")
            self.assertNotIn("strict", tool)  # optional arguments: strict mode cannot say that
            check_json_schema(self, tool["parameters"], tool["name"])

    def test_openai_compat_tools(self):
        for tool in openai_compat.Adapter().tools(tools_core.TOOLS):
            self.assertEqual(tool["type"], "function")
            check_json_schema(self, tool["function"]["parameters"], tool["function"]["name"])

    def test_gemini_schema_subset(self):
        declarations = gemini.Adapter().tools(tools_core.TOOLS)[0]["functionDeclarations"]
        for item in declarations:
            schema = item.get("parametersJsonSchema")
            if not tools_core.tool(item["name"])["input_schema"]["properties"]:
                self.assertIsNone(schema, item["name"])  # no arguments: no schema at all
                continue
            check_json_schema(self, schema, item["name"])
            for path, sub in walk(schema):
                where = "%s %s" % (item["name"], path)
                self.assertTrue(
                    set(sub) <= gemini.SCHEMA_KEYS,
                    "%s: %s" % (where, set(sub) - gemini.SCHEMA_KEYS),
                )
                self.assertFalse(isinstance(sub.get("type"), list), where)
                self.assertTrue("type" in sub or "anyOf" in sub or "oneOf" in sub, where)

    def test_gemini_rewrites(self):
        tools = {
            d["name"]: d
            for d in gemini.Adapter().tools(tools_core.TOOLS)[0]["functionDeclarations"]
        }
        value = tools["set_parameter"]["parametersJsonSchema"]["properties"]["value"]
        self.assertEqual(value["anyOf"], [{"type": "number"}, {"type": "string"}])
        extrude = tools["extrude"]["parametersJsonSchema"]["properties"]
        self.assertEqual(extrude["distance"]["minimum"], 0)
        self.assertIn("must be above 0", extrude["distance"]["description"])
        self.assertIn("default join", extrude["operation"]["description"])
        at = tools["fillet"]["parametersJsonSchema"]["properties"]["edges"]["properties"]["at"]
        self.assertEqual(at["anyOf"][0], {"type": "object"})
        # The originals in tools_core are not touched.
        self.assertIn(
            "default", tools_core.tool("extrude")["input_schema"]["properties"]["operation"]
        )


class Requests(unittest.TestCase):
    def test_anthropic_request(self):
        url, headers, body = anthropic.Adapter().build_request(
            "claude-opus-5-5",
            "be nice",
            [{"role": "user", "content": "hi"}],
            tools_core.TOOLS,
            900,
            KEY,
        )
        self.assertEqual(url, "https://api.anthropic.com/v1/messages")
        self.assertEqual(headers["x-api-key"], KEY)
        self.assertEqual(headers["anthropic-version"], "2023-06-01")
        self.assertEqual(headers["anthropic-beta"], anthropic.BETA_UPDATES)
        self.assertEqual(body["system"], "be nice")
        self.assertEqual(body["max_tokens"], 900)
        self.assertEqual(body["thinking"], {"type": "adaptive", "display": "updates"})
        self.assertNotIn("fallbacks", body)  # never another model than the one picked
        self.assertEqual(body["output_config"], {"effort": anthropic.EFFORT})
        self.assertEqual(body["cache_control"], {"type": "ephemeral"})

    def test_anthropic_plain_request_for_other_models_and_hosts(self):
        _url, headers, body = anthropic.Adapter().build_request(
            "claude-haiku-4-5", "", [], [], 10, KEY
        )
        for key in ("thinking", "fallbacks", "output_config", "tools", "system"):
            self.assertNotIn(key, body)
        self.assertNotIn("anthropic-beta", headers)
        url, headers, body = anthropic.Adapter().build_request(
            "claude-opus-5-5", "", [], [], 10, KEY, "http://127.0.0.1:9/"
        )
        self.assertEqual(url, "http://127.0.0.1:9/v1/messages")
        self.assertNotIn("fallbacks", body)  # a proxy or test server: no server-side fallback

    def test_openai_request(self):
        url, headers, body = openai.Adapter().build_request(
            "gpt-6-astra", "sys", [], tools_core.TOOLS, 50, KEY
        )
        self.assertEqual(url, "https://api.openai.com/v1/responses")
        self.assertEqual(headers["Authorization"], "Bearer " + KEY)
        self.assertEqual(body["instructions"], "sys")
        self.assertIs(body["store"], False)
        self.assertEqual(body["max_output_tokens"], 50)

    def test_gemini_request(self):
        url, headers, body = gemini.Adapter().build_request(
            "gemini-flash-latest", "sys", [], tools_core.TOOLS, 50, KEY
        )
        self.assertEqual(
            url,
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent",
        )
        self.assertEqual(headers["x-goog-api-key"], KEY)
        self.assertNotIn(KEY, url)  # the key never goes in the URL (it would end up in logs)
        self.assertEqual(body["systemInstruction"], {"parts": [{"text": "sys"}]})
        self.assertEqual(body["generationConfig"], {"maxOutputTokens": 50})

    def test_compat_request(self):
        url, headers, body = openai_compat.Adapter().build_request(
            "qwen3:8b", "sys", [{"role": "user", "content": "hi"}], tools_core.TOOLS, 50
        )
        self.assertEqual(url, "http://localhost:11434/v1/chat/completions")
        self.assertNotIn("Authorization", headers)
        self.assertEqual(body["messages"][0], {"role": "system", "content": "sys"})
        self.assertEqual(body["messages"][1]["content"], "hi")
        url, _h, _b = openai_compat.Adapter().build_request(
            "m", "", [], [], 5, None, openai_compat.LM_STUDIO_URL
        )
        self.assertEqual(url, "http://localhost:1234/v1/chat/completions")


SKETCH_ARGS = {"plane": "XY", "geometry": [{"center_rect": [0, 0, 40, 30]}]}


class Responses(unittest.TestCase):
    def check_tool_turn(self, turn, call_id):
        self.assertEqual(turn["stop"], "tool_use")
        self.assertEqual(turn["text"], "I'll sketch the base rectangle first.")
        self.assertEqual(len(turn["tool_calls"]), 1)
        call = turn["tool_calls"][0]
        self.assertEqual(
            (call["id"], call["name"], call["args"]), (call_id, "create_sketch", SKETCH_ARGS)
        )
        self.assertEqual(tools_core.validate(call["name"], call["args"]), [])

    def test_anthropic(self):
        data = fixture("anthropic")
        turn = anthropic.Adapter().parse_response(data["tool_use"])
        self.check_tool_turn(turn, "toolu_01A09q90qw90lq917835lq9")
        self.assertEqual(turn["progress"], ["Starting with a 40 x 30 rectangle on XY."])
        self.assertEqual(turn["usage"]["input_tokens"], 5120)
        self.assertEqual(turn["raw"]["content"], data["tool_use"]["content"])
        final = anthropic.Adapter().parse_response(data["final"])
        self.assertEqual(
            (final["stop"], final["text"], final["tool_calls"]),
            ("end", "Done: a 40 x 30 x 10 mm box.", []),
        )
        self.assertEqual(anthropic.Adapter().parse_response(data["refusal"])["stop"], "refusal")

    def test_anthropic_fallback_keeps_only_the_text_before_the_switch(self):
        turn = anthropic.Adapter().parse_response(fixture("anthropic")["fallback_mid_output"])
        self.assertEqual([c["id"] for c in turn["tool_calls"]], ["toolu_kept"])
        self.assertEqual([b["type"] for b in turn["raw"]["content"]], ["text", "tool_use"])

    def test_openai(self):
        data = fixture("openai")
        turn = openai.Adapter().parse_response(data["tool_use"])
        self.check_tool_turn(turn, "call_12345xyz")
        self.assertEqual(turn["progress"], ["Sketch the base first."])
        self.assertEqual(turn["raw"]["items"], data["tool_use"]["output"])
        final = openai.Adapter().parse_response(data["final"])
        self.assertEqual((final["stop"], final["text"]), ("end", "Done: a 40 x 30 x 10 mm box."))
        self.assertEqual(openai.Adapter().parse_response(data["incomplete"])["stop"], "max_tokens")

    def test_gemini(self):
        data = fixture("gemini")
        turn = gemini.Adapter().parse_response(data["tool_use"])
        self.check_tool_turn(turn, "call_1")
        self.assertTrue(turn["tool_calls"][0]["id_generated"])
        self.assertEqual(turn["raw"]["content"], data["tool_use"]["candidates"][0]["content"])
        with_id = gemini.Adapter().parse_response(data["tool_use_with_id"])
        self.assertEqual(with_id["tool_calls"][0]["id"], "fc-8f2a")
        self.assertNotIn("id_generated", with_id["tool_calls"][0])
        final = gemini.Adapter().parse_response(data["final"])
        self.assertEqual((final["stop"], final["text"]), ("end", "Done: a 40 x 30 x 10 mm box."))
        self.assertEqual(gemini.Adapter().parse_response(data["blocked"])["stop"], "refusal")

    def test_compat(self):
        data = fixture("openai_compat")
        turn = openai_compat.Adapter().parse_response(data["tool_use"])
        self.assertEqual(turn["stop"], "tool_use")
        self.assertEqual(turn["tool_calls"][0]["args"], SKETCH_ARGS)
        bad = openai_compat.Adapter().parse_response(data["bad_json"])
        self.assertEqual(bad["stop"], "tool_use")  # finish_reason "stop" next to a tool call
        self.assertEqual(bad["tool_calls"][0]["bad_args"], "the arguments were not valid JSON")
        final = openai_compat.Adapter().parse_response(data["final"])
        self.assertEqual((final["stop"], final["text"]), ("end", "Done: a 40 x 30 x 10 mm box."))

    def test_garbage_never_raises(self):
        for adapter in ADAPTERS.values():
            for junk in (
                None,
                {},
                [],
                {"content": "x", "output": 3, "candidates": [None], "choices": [{}]},
            ):
                turn = adapter.parse_response(junk)
                self.assertEqual(turn["tool_calls"], [])


CALL = {"id": "toolu_01", "name": "screenshot", "args": {}}
SHOT = {"text": "Picture of the iso view.", "image_png_base64": PNG, "is_error": False}
FAIL = {"text": "Not done: distance is missing.", "image_png_base64": None, "is_error": True}
CALL2 = {"id": "toolu_02", "name": "extrude", "args": {"profile": "sketch1"}}


class ToolResults(unittest.TestCase):
    def test_anthropic_image_block_in_tool_result(self):
        (message,) = anthropic.Adapter().tool_results_message([(CALL, SHOT), (CALL2, FAIL)])
        self.assertEqual(message["role"], "user")
        shot, fail = message["content"]  # all results in ONE user message
        self.assertEqual(shot["tool_use_id"], "toolu_01")
        self.assertEqual(shot["content"][0], {"type": "text", "text": "Picture of the iso view."})
        self.assertEqual(
            shot["content"][1],
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": PNG}},
        )
        self.assertNotIn("is_error", shot)
        self.assertIs(fail["is_error"], True)

    def test_openai_image_inside_function_call_output(self):
        shot, fail = openai.Adapter().tool_results_message([(CALL, SHOT), (CALL2, FAIL)])
        self.assertEqual(shot["type"], "function_call_output")
        self.assertEqual(shot["call_id"], "toolu_01")
        self.assertEqual(
            shot["output"][0], {"type": "input_text", "text": "Picture of the iso view."}
        )
        self.assertEqual(shot["output"][1]["type"], "input_image")
        self.assertEqual(shot["output"][1]["image_url"], "data:image/png;base64," + PNG)
        self.assertEqual(fail["output"], "Error: Not done: distance is missing.")

    def test_gemini_function_response_with_inline_data(self):
        call = {"id": "fc-1", "name": "screenshot", "args": {}}
        gen = {"id": "call_0", "id_generated": True, "name": "extrude", "args": {}}
        (content,) = gemini.Adapter().tool_results_message([(call, SHOT), (gen, FAIL)])
        self.assertEqual(content["role"], "user")
        shot, fail = (p["functionResponse"] for p in content["parts"])
        self.assertEqual(shot["id"], "fc-1")
        self.assertEqual(shot["response"], {"output": "Picture of the iso view."})
        self.assertEqual(shot["parts"], [{"inlineData": {"mimeType": "image/png", "data": PNG}}])
        self.assertNotIn("id", fail)  # an id Gemini never gave is not sent back
        self.assertEqual(fail["response"], {"error": "Not done: distance is missing."})

    def test_compat_says_the_model_cannot_see_the_picture(self):
        shot, fail = openai_compat.Adapter().tool_results_message([(CALL, SHOT), (CALL2, FAIL)])
        self.assertEqual(shot["role"], "tool")
        self.assertEqual(shot["tool_call_id"], "toolu_01")
        self.assertIn("(a picture was taken; this model cannot see images)", shot["content"])
        self.assertNotIn(PNG, json.dumps(shot))
        self.assertTrue(fail["content"].startswith("Error: "))


def history_from(adapter, data):
    """A neutral history as the chat loop builds it from recorded answers."""
    first = adapter.parse_response(data["tool_use"])
    final = adapter.parse_response(data["final"])
    history = [{"role": "user", "text": "make a 40 x 30 x 10 box"}]
    history.append(
        {
            "role": "assistant",
            "text": first["text"],
            "tool_calls": first["tool_calls"],
            "raw": first["raw"],
        }
    )
    results = [{"call": c, "result": SHOT} for c in first["tool_calls"]]
    history.append({"role": "user", "tool_results": results})
    history.append(
        {"role": "assistant", "text": final["text"], "tool_calls": [], "raw": final["raw"]}
    )
    return history


class History(unittest.TestCase):
    def test_same_provider_gets_its_own_turns_back_unchanged(self):
        data = fixture("anthropic")
        messages = anthropic.Adapter().to_provider_messages(history_from(anthropic.Adapter(), data))
        self.assertEqual([m["role"] for m in messages], ["user", "assistant", "user", "assistant"])
        self.assertEqual(messages[1]["content"], data["tool_use"]["content"])  # thinking kept
        self.assertEqual(messages[2]["content"][0]["tool_use_id"], "toolu_01A09q90qw90lq917835lq9")

        data = fixture("openai")
        items = openai.Adapter().to_provider_messages(
            history_from(openai.Adapter(), data), "gpt-6-astra"
        )
        self.assertEqual(items[1:4], data["tool_use"]["output"])  # reasoning item kept
        self.assertEqual(items[4]["call_id"], "call_12345xyz")
        # Another OpenAI model gets the turn rebuilt, without the reasoning item.
        items = openai.Adapter().to_provider_messages(
            history_from(openai.Adapter(), data), "gpt-5.5"
        )
        self.assertNotIn("reasoning", [i.get("type") for i in items])

        data = fixture("gemini")
        contents = gemini.Adapter().to_provider_messages(history_from(gemini.Adapter(), data))
        self.assertEqual(
            contents[1], data["tool_use"]["candidates"][0]["content"]
        )  # signature kept
        self.assertNotIn("id", contents[2]["parts"][0]["functionResponse"])

    def test_switching_provider_rebuilds_valid_turns(self):
        sources = {n: history_from(ADAPTERS[n], fixture(n)) for n in ADAPTERS}
        for source, history in sources.items():
            for target, adapter in ADAPTERS.items():
                out = adapter.to_provider_messages(copy.deepcopy(history), "some-model")
                text = json.dumps(out)
                where = "%s -> %s" % (source, target)
                self.assertIn("make a 40 x 30 x 10 box", text, where)
                self.assertIn("Done: a 40 x 30 x 10 mm box.", text, where)
                if target == "anthropic":
                    uses = [
                        b["id"]
                        for m in out
                        if m["role"] == "assistant"
                        for b in m["content"]
                        if b["type"] == "tool_use"
                    ]
                    results = [
                        b["tool_use_id"]
                        for m in out
                        if m["role"] == "user" and isinstance(m["content"], list)
                        for b in m["content"]
                    ]
                    self.assertEqual(uses, results, where)
                elif target == "openai":
                    calls = [i["call_id"] for i in out if i.get("type") == "function_call"]
                    outputs = [i["call_id"] for i in out if i.get("type") == "function_call_output"]
                    self.assertEqual(calls, outputs, where)
                elif target == "openai_compat":
                    calls = [
                        c["id"]
                        for m in out
                        if m["role"] == "assistant"
                        for c in m.get("tool_calls", [])
                    ]
                    outputs = [m["tool_call_id"] for m in out if m["role"] == "tool"]
                    self.assertEqual(calls, outputs, where)
                    self.assertNotIn(PNG, text, where)
                else:
                    roles = [c["role"] for c in out]
                    self.assertEqual(roles, ["user", "model", "user", "model"], where)
                    calls = [p for c in out for p in c["parts"] if "functionCall" in p]
                    answers = [p for c in out for p in c["parts"] if "functionResponse" in p]
                    self.assertEqual(len(calls), len(answers), where)
                    if source != "gemini":  # rebuilt calls carry no ids, so answers carry none
                        self.assertTrue(
                            all("id" not in p["functionResponse"] for p in answers), where
                        )

    def test_ids_are_made_safe(self):
        history = [
            {"role": "user", "text": "hi"},
            {
                "role": "assistant",
                "text": "",
                "tool_calls": [{"id": "weird id/1", "name": "undo", "args": {}}],
            },
            {
                "role": "user",
                "tool_results": [{"call": {"id": "weird id/1", "name": "undo"}, "result": FAIL}],
            },
        ]
        out = anthropic.Adapter().to_provider_messages(history)
        self.assertEqual(out[1]["content"][0]["id"], "weird_id_1")
        self.assertEqual(out[2]["content"][0]["tool_use_id"], "weird_id_1")


class ListModels(unittest.TestCase):
    def fake_get(self, data, status=200):
        seen = []

        def get(url, headers=None):
            seen.append((url, headers))
            return status, data, None

        return get, seen

    def test_lists(self):
        get, seen = self.fake_get(fixture("anthropic")["models"])
        self.assertEqual(
            anthropic.Adapter().list_models(KEY, http_get=get),
            ["claude-opus-5-5", "claude-sonnet-5-5"],
        )
        self.assertEqual(seen[0][1]["x-api-key"], KEY)
        get, _ = self.fake_get(fixture("openai")["models"])
        self.assertEqual(
            openai.Adapter().list_models(KEY, http_get=get), ["gpt-6-astra", "gpt-5.5"]
        )
        get, seen = self.fake_get(fixture("gemini")["models"])
        self.assertEqual(
            gemini.Adapter().list_models(KEY, http_get=get),
            ["gemini-flash-latest", "gemini-3.1-pro-preview"],
        )
        self.assertNotIn(KEY, seen[0][0])
        get, _ = self.fake_get(fixture("openai_compat")["models"])
        self.assertEqual(openai_compat.Adapter().list_models(None, http_get=get), ["qwen3:8b"])

    def test_errors_give_an_empty_list(self):
        for adapter in ADAPTERS.values():
            get, _ = self.fake_get({"error": {"message": "no"}}, 401)
            self.assertEqual(adapter.list_models(KEY, http_get=get), [])

            def boom(url, headers=None):
                raise RuntimeError("down")

            self.assertEqual(adapter.list_models(KEY, http_get=boom), [])


class _Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def _answer(self, status, data):
        raw = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path.startswith("/v1/models"):
            return self._answer(200, fixture("openai_compat")["models"])
        self._answer(404, {"error": {"message": "no such page"}})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length) or b"{}")
        if self.headers.get("Authorization") == "Bearer wrong":
            return self._answer(401, {"error": {"message": "bad key"}})
        self._answer(200, {"echo": body, "path": self.path})


class LocalServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
        cls.base = "http://127.0.0.1:%d/v1" % cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_post_and_errors(self):
        status, data, problem = _common.post_json(self.base + "/chat/completions", {}, {"a": "é"})
        self.assertEqual((status, problem), (200, None))
        self.assertEqual(data["echo"], {"a": "é"})
        status, data, problem = _common.post_json(
            self.base + "/x", {"Authorization": "Bearer wrong"}, {}
        )
        self.assertEqual((status, data["error"]["message"]), (401, "bad key"))

    def test_localhost_never_goes_through_a_proxy(self):
        saved = {k: os.environ.get(k) for k in ("http_proxy", "HTTP_PROXY", "no_proxy", "NO_PROXY")}
        try:
            os.environ["http_proxy"] = os.environ["HTTP_PROXY"] = "http://127.0.0.1:9"
            os.environ.pop("no_proxy", None)
            os.environ.pop("NO_PROXY", None)
            status, _data, problem = _common.post_json(self.base + "/chat/completions", {}, {})
            self.assertEqual((status, problem), (200, None))
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    def test_list_models_over_http(self):
        models = openai_compat.Adapter().list_models(None, self.base)
        self.assertEqual(models, ["qwen3:8b"])

    def test_refused_connection(self):
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()  # nothing listens there now
        status, data, problem = _common.post_json("http://127.0.0.1:%d/v1/x" % port, {}, {})
        self.assertEqual((status, data, problem), (0, None, "refused"))


class Redaction(unittest.TestCase):
    def test_keys_are_hidden(self):
        text = (
            "key %s and sk-ant-api03-AbCdEf and AIzaSyA1234567890abcdef and Bearer abcdefghijkl"
            % KEY
        )
        hidden = _common.redact(text, KEY)
        for secret in (KEY, "sk-ant-api03", "AIzaSyA123", "abcdefghijkl"):
            self.assertNotIn(secret, hidden)
        self.assertEqual(_common.redact("a task-list stays", None), "a task-list stays")


if __name__ == "__main__":
    unittest.main()
