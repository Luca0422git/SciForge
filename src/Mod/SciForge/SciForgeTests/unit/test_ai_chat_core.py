# SPDX-License-Identifier: LGPL-2.1-or-later
"""The chat panel's agent loop (sciforge/ai/chat_core.py) with a scripted fake model: a
two-step build, validation errors fed back, the step limit, Stop, HTTP errors as plain
sentences, and API keys that never show up in logs or messages. No network: a fake
http function, and once a local http.server on 127.0.0.1 posing as a provider. Runs
without FreeCAD."""

import http.server
import json
import os
import socket
import sys
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sciforge.ai import catalog, chat_core, providers  # noqa: E402
from sciforge.ai.providers import anthropic, gemini, openai, openai_compat  # noqa: E402

KEY = "sk-ant-api03-SECRETSECRET0123456789"
PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
SKETCH = {"plane": "XY", "geometry": [{"center_rect": [0, 0, 40, 30]}]}
EXTRUDE = {"profile": "sketch1", "distance": 10}


def fixture(name):
    with open(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures_ai", name + ".json"),
        encoding="utf-8",
    ) as f:
        return json.load(f)


def claude_tool(call_id, name, args, text=""):
    content = [{"type": "text", "text": text}] if text else []
    content.append({"type": "tool_use", "id": call_id, "name": name, "input": args})
    return (
        200,
        {
            "type": "message",
            "role": "assistant",
            "model": "claude-opus-5-5",
            "content": content,
            "stop_reason": "tool_use",
            "usage": {"input_tokens": 100, "output_tokens": 10},
        },
        None,
    )


def claude_tools(calls):
    content = [{"type": "tool_use", "id": i, "name": n, "input": a} for i, n, a in calls]
    return (
        200,
        {"type": "message", "content": content, "stop_reason": "tool_use", "usage": {}},
        None,
    )


def claude_text(text, stop="end_turn"):
    return (
        200,
        {
            "type": "message",
            "role": "assistant",
            "model": "claude-opus-5-5",
            "content": [{"type": "text", "text": text}],
            "stop_reason": stop,
            "usage": {"input_tokens": 50, "output_tokens": 5},
        },
        None,
    )


class ScriptedModel:
    """The fake provider: answers in order, remembers each request body."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.requests = []

    def __call__(self, url, headers, body):
        self.requests.append({"url": url, "headers": headers, "body": json.loads(json.dumps(body))})
        if not self.answers:
            raise AssertionError("the model was asked more often than scripted")
        answer = self.answers.pop(0)
        return answer() if callable(answer) else answer


class FakeSciForge:
    def __init__(self, answers=None):
        self.calls = []
        self.answers = answers or {}

    def __call__(self, name, args):
        self.calls.append((name, args))
        answer = self.answers.get(
            name, {"text": "%s done" % name, "image_png_base64": None, "is_error": False}
        )
        return answer(args) if callable(answer) else answer


class Recorder:
    def __init__(self):
        self.events, self.lines = [], []

    def event(self, kind, data):
        self.events.append((kind, data))

    def log(self, line):
        self.lines.append(line)

    def kinds(self):
        return [kind for kind, _data in self.events]


def make_chat(model, sciforge=None, adapter=None, key=KEY, **kwargs):
    rec = Recorder()
    chat = chat_core.Chat(
        adapter or anthropic.Adapter(),
        "claude-opus-5-5" if adapter is None else kwargs.pop("model_id", "m"),
        key=key,
        call_tool=sciforge if sciforge is not None else FakeSciForge(),
        log=rec.log,
        http=model,
        sleep=lambda s: None,
        **kwargs,
    )
    return chat, rec


class Building(unittest.TestCase):
    def test_two_step_build_then_answer(self):
        model = ScriptedModel(
            claude_tool("toolu_1", "create_sketch", SKETCH, "Sketching the base."),
            claude_tool("toolu_2", "extrude", EXTRUDE),
            claude_text("Done: a 40 x 30 x 10 mm box."),
        )
        sciforge = FakeSciForge(
            {
                "create_sketch": {
                    "text": "Created sketch1.",
                    "image_png_base64": None,
                    "is_error": False,
                }
            }
        )
        chat, rec = make_chat(model, sciforge)
        done = chat.send("make a 40 x 30 x 10 box", rec.event)
        self.assertEqual((done["ok"], done["reason"], done["steps"]), (True, "end", 3))
        self.assertEqual(done["text"], "Done: a 40 x 30 x 10 mm box.")
        self.assertEqual(sciforge.calls, [("create_sketch", SKETCH), ("extrude", EXTRUDE)])
        self.assertEqual(
            rec.kinds(),
            ["text", "tool_call", "tool_result", "tool_call", "tool_result", "text", "done"],
        )
        self.assertEqual(rec.events[-1][1], done)
        self.assertEqual(done["usage"], {"input_tokens": 250, "output_tokens": 25})
        # The second request carries the first result, linked to its call.
        second = model.requests[1]["body"]["messages"]
        self.assertEqual(second[0], {"role": "user", "content": "make a 40 x 30 x 10 box"})
        self.assertEqual(second[-1]["content"][0]["tool_use_id"], "toolu_1")
        self.assertEqual(second[-1]["content"][0]["content"][0]["text"], "Created sketch1.")
        self.assertEqual(model.requests[0]["body"]["system"], chat_core.SYSTEM_PROMPT)
        # Anthropic takes every tool of the catalogue, the first sixteen first
        tools = model.requests[0]["body"]["tools"]
        self.assertEqual(len(tools), len(catalog.TOOLS))
        self.assertEqual([t["name"] for t in tools[:16]], list(catalog.LEGACY_NAMES))
        # The history: user, assistant, results, assistant, results, assistant.
        self.assertEqual(
            [h["role"] for h in chat.history],
            ["user", "assistant", "user", "assistant", "user", "assistant"],
        )

    def test_screenshot_goes_back_as_a_picture(self):
        model = ScriptedModel(
            claude_tool("toolu_s", "screenshot", {"view": "top"}), claude_text("Looks right.")
        )
        sciforge = FakeSciForge(
            {"screenshot": {"text": "Top view.", "image_png_base64": PNG, "is_error": False}}
        )
        chat, rec = make_chat(model, sciforge)
        chat.send("show me", rec.event)
        result = model.requests[1]["body"]["messages"][-1]["content"][0]
        self.assertEqual(result["content"][1]["source"]["data"], PNG)
        tool_result = [d for k, d in rec.events if k == "tool_result"][0]
        self.assertTrue(tool_result["has_image"])
        self.assertNotIn("image_png_base64", tool_result)  # the panel gets no megabytes per event

    def test_conversation_continues_and_can_switch_provider(self):
        model = ScriptedModel(
            claude_tool("toolu_1", "create_sketch", SKETCH), claude_text("Sketch made.")
        )
        chat, rec = make_chat(model)
        chat.send("sketch a rectangle", rec.event)
        model2 = ScriptedModel(
            (
                200,
                {
                    "status": "completed",
                    "model": "gpt-6-astra",
                    "output": [
                        {
                            "type": "message",
                            "role": "assistant",
                            "content": [{"type": "output_text", "text": "It is 40 x 30."}],
                        }
                    ],
                },
                None,
            )
        )
        chat2 = chat_core.Chat(
            openai.Adapter(),
            "gpt-6-astra",
            key="sk-openai-x123",
            http=model2,
            history=chat.history,
            log=rec.log,
        )
        done = chat2.send("how big is it?")
        self.assertEqual(done["text"], "It is 40 x 30.")
        items = model2.requests[0]["body"]["input"]
        self.assertEqual(
            [i.get("type", i.get("role")) for i in items],
            ["user", "function_call", "function_call_output", "assistant", "user"],
        )
        self.assertEqual(items[1]["call_id"], items[2]["call_id"])


class FeedingErrorsBack(unittest.TestCase):
    def test_validation_error_reaches_the_model_not_sciforge(self):
        model = ScriptedModel(
            claude_tool("toolu_1", "extrude", {"profile": "sketch1"}),  # no distance
            claude_tool("toolu_2", "extrude", EXTRUDE),
            claude_text("Extruded."),
        )
        sciforge = FakeSciForge()
        chat, rec = make_chat(model, sciforge)
        done = chat.send("extrude it", rec.event)
        self.assertTrue(done["ok"])
        self.assertEqual(sciforge.calls, [("extrude", EXTRUDE)])  # the bad call never ran
        refused = model.requests[1]["body"]["messages"][-1]["content"][0]
        self.assertIs(refused["is_error"], True)
        self.assertIn("distance is missing", refused["content"][0]["text"])

    def test_unknown_tool_and_bad_json_and_failing_bridge(self):
        model = ScriptedModel(
            claude_tools([("t1", "make_coffee", {}), ("t2", "get_design", {})]),
            claude_text("ok"),
        )

        def broken(name, args):
            raise RuntimeError("the bridge broke")

        chat, rec = make_chat(model, broken)
        chat.send("go", rec.event)
        results = model.requests[1]["body"]["messages"][-1]["content"]
        self.assertIn("there is no tool called 'make_coffee'", results[0]["content"][0]["text"])
        self.assertIn(
            "SciForge could not run get_design: the bridge broke", results[1]["content"][0]["text"]
        )
        # A local model sending broken JSON is told so.
        bad = fixture("openai_compat")
        model = ScriptedModel((200, bad["bad_json"], None), (200, bad["final"], None))
        sciforge = FakeSciForge()
        chat, rec = make_chat(model, sciforge, adapter=openai_compat.Adapter(), key=None)
        done = chat.send("extrude", rec.event)
        self.assertTrue(done["ok"])
        self.assertEqual(sciforge.calls, [])
        tool_message = model.requests[1]["body"]["messages"][-1]
        self.assertEqual(tool_message["role"], "tool")
        self.assertIn("not valid JSON", tool_message["content"])


class Limits(unittest.TestCase):
    def test_max_steps(self):
        model = ScriptedModel(*[claude_tool("t%d" % i, "get_design", {}) for i in range(3)])
        chat, rec = make_chat(model, max_steps=3)
        done = chat.send("loop forever", rec.event)
        self.assertEqual((done["ok"], done["reason"], done["steps"]), (False, "max_steps", 3))
        self.assertIn("Stopped after 3 steps", done["text"])
        self.assertEqual(len(model.requests), 3)
        self.assertIn("error", rec.kinds())
        self.assertEqual(chat_core.MAX_STEPS, 25)

    def test_stop_between_steps(self):
        model = ScriptedModel(claude_tools([("t1", "get_design", {}), ("t2", "screenshot", {})]))
        holder = {}

        def sciforge(name, args):
            holder["chat"].stop()  # the person presses Stop while the first tool runs
            return {"text": "a box", "image_png_base64": None, "is_error": False}

        chat, rec = make_chat(model, sciforge)
        holder["chat"] = chat
        done = chat.send("look", rec.event)
        self.assertEqual((done["ok"], done["reason"]), (True, "stopped"))
        self.assertEqual(done["text"], chat_core.STOPPED_TEXT)
        self.assertEqual(len(model.requests), 1)  # no further request after Stop
        results = chat.history[-1]["tool_results"]
        self.assertEqual(results[0]["result"]["text"], "a box")
        self.assertEqual(results[1]["result"]["text"], "Not run: the person pressed Stop.")
        # The next message works again (the flag is cleared) and the history is valid.
        model.answers.append(claude_text("Hello again."))
        done = chat.send("hello", rec.event)
        self.assertEqual(done["text"], "Hello again.")

    def test_stop_from_another_thread(self):
        release = threading.Event()

        def slow_model(url, headers, body):
            release.wait(5)
            return claude_tool("t1", "get_design", {})

        chat, rec = make_chat(slow_model)
        worker = threading.Thread(target=lambda: rec.event("result", chat.send("hi", rec.event)))
        worker.start()
        while not chat.busy():  # Stop is pressed while the request is on its way
            pass
        chat.stop()
        release.set()
        worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(rec.events[-1][1]["reason"], "stopped")

    def test_busy(self):
        release = threading.Event()

        def slow_model(url, headers, body):
            release.wait(5)
            return claude_text("hi")

        chat, rec = make_chat(slow_model)
        worker = threading.Thread(target=chat.send, args=("one",))
        worker.start()
        while not chat.busy():
            pass
        self.assertEqual(chat.send("two")["reason"], "busy")
        release.set()
        worker.join(5)

    def test_cut_off_and_refused_answers_run_no_tools(self):
        cut = claude_tool("t1", "extrude", EXTRUDE)
        cut[1]["stop_reason"] = "max_tokens"
        model = ScriptedModel(cut, (200, {"content": [], "stop_reason": "refusal"}, None))
        sciforge = FakeSciForge()
        chat, rec = make_chat(model, sciforge)
        done = chat.send("extrude", rec.event)
        self.assertEqual(done["reason"], "max_tokens")
        self.assertIn("cut off", done["text"])
        self.assertEqual(sciforge.calls, [])
        self.assertIn("Not run", chat.history[-1]["tool_results"][0]["result"]["text"])
        done = chat.send("again", rec.event)
        self.assertEqual(done["reason"], "refusal")
        self.assertIn("declined", done["text"])

    def test_missing_key_or_model_or_text(self):
        chat, rec = make_chat(ScriptedModel(), key=None)
        done = chat.send("hi", rec.event)
        self.assertIn("Add a key for Claude (Anthropic)", done["text"])
        chat, rec = make_chat(ScriptedModel())
        self.assertEqual(chat.send("   ")["reason"], "error")

    def test_broken_event_handler_does_not_stop_the_chat(self):
        chat, rec = make_chat(ScriptedModel(claude_text("fine")))

        def bad(kind, data):
            raise ValueError("panel closed")

        self.assertEqual(chat.send("hi", bad)["text"], "fine")
        self.assertTrue(any("could not show" in line for line in rec.lines))


class HttpErrors(unittest.TestCase):
    def sentence(self, answer, adapter=None, base_url=None, **kwargs):
        model = ScriptedModel(*([answer] * 3))
        rec = Recorder()
        chat = chat_core.Chat(
            adapter or anthropic.Adapter(),
            kwargs.get("model", "claude-opus-5-5"),
            key=KEY,
            base_url=base_url,
            http=model,
            log=rec.log,
            sleep=lambda s: None,
        )
        done = chat.send("hi", rec.event)
        self.assertFalse(done["ok"])
        self.assertEqual(done["reason"], "error")
        errors = [d for k, d in rec.events if k == "error"]
        self.assertEqual(errors[-1], done["text"])
        return done["text"], model, rec

    def test_sentences(self):
        text, _m, _r = self.sentence((401, {"error": {"message": "invalid x-api-key"}}, None))
        self.assertIn("The key was refused by Claude (Anthropic)", text)
        text, _m, _r = self.sentence((403, {}, None))
        self.assertIn("key was refused", text)
        text, _m, _r = self.sentence((429, {"error": {"type": "rate_limit_error"}}, None))
        self.assertIn("too many requests or no credit", text)
        text, model, _r = self.sentence((529, {"error": {"type": "overloaded_error"}}, None))
        self.assertIn("had a problem (error 529)", text)
        self.assertEqual(len(model.requests), 1 + chat_core.RETRIES)  # retried, then gave up
        text, _m, _r = self.sentence((404, {"error": {"message": "model: nope"}}, None))
        self.assertIn("does not offer the model", text)
        text, _m, _r = self.sentence((400, {"error": {"message": "messages: bad"}}, None))
        self.assertIn("did not accept the request (error 400): messages: bad", text)
        text, _m, _r = self.sentence((0, None, "timeout"))
        self.assertIn("did not answer in time", text)
        text, _m, _r = self.sentence((0, None, "network: [Errno -2] Name or service not known"))
        self.assertIn("Check the internet connection", text)
        text, _m, _r = self.sentence((200, {"content": 5}, None))
        self.assertIn("could not read", text)

    def test_gemini_wrong_key_is_a_400(self):
        data = fixture("gemini")
        text, _m, _r = self.sentence(
            (400, data["error_key"], None), gemini.Adapter(), model="gemini-flash-latest"
        )
        self.assertIn("The key was refused by Gemini (Google)", text)

    def test_local_server_not_running(self):
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        rec = Recorder()
        chat = chat_core.Chat(
            openai_compat.Adapter(),
            "qwen3:8b",
            base_url="http://127.0.0.1:%d/v1" % port,
            log=rec.log,
        )
        done = chat.send("hi", rec.event)  # the real urllib POST
        self.assertIn("Is Ollama / LM Studio running", done["text"])

    def test_keys_never_appear(self):
        echo = (401, {"error": {"message": "the key %s is not valid" % KEY}}, None)
        text, model, rec = self.sentence(echo)
        self.assertEqual(model.requests[0]["headers"]["x-api-key"], KEY)  # it is sent...
        everything = json.dumps([rec.lines, rec.events, text])
        self.assertNotIn(KEY, everything)  # ...but never shown or logged
        self.assertNotIn("SECRETSECRET", everything)
        self.assertTrue(rec.lines and all(line.startswith("[SciForge]") for line in rec.lines))
        # Also on success, and with a network problem that mentions it.
        chat, rec = make_chat(ScriptedModel((0, None, "network: proxy refused Bearer %s" % KEY)))
        done = chat.send("hi", rec.event)
        self.assertNotIn(KEY, json.dumps([rec.lines, rec.events, done]))


class _FakeOpenAI(http.server.BaseHTTPRequestHandler):
    """A fake Responses API: create_sketch, then extrude, then an answer."""

    script = []
    seen = []

    def log_message(self, *_args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        type(self).seen.append((self.path, self.headers.get("Authorization"), body))
        raw = json.dumps(type(self).script.pop(0)).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def responses_call(call_id, name, args):
    return {
        "status": "completed",
        "model": "gpt-6-astra",
        "output": [
            {
                "type": "function_call",
                "id": "fc_" + call_id,
                "call_id": call_id,
                "name": name,
                "arguments": json.dumps(args),
            }
        ],
    }


class OverHttp(unittest.TestCase):
    def test_build_against_a_local_fake_provider(self):
        _FakeOpenAI.script = [
            responses_call("call_1", "create_sketch", SKETCH),
            responses_call("call_2", "extrude", EXTRUDE),
            {
                "status": "completed",
                "model": "gpt-6-astra",
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": "Box built."}],
                    }
                ],
            },
        ]
        _FakeOpenAI.seen = []
        server = http.server.HTTPServer(("127.0.0.1", 0), _FakeOpenAI)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            sciforge = FakeSciForge()
            rec = Recorder()
            chat = chat_core.Chat(
                providers.adapter("openai"),
                "gpt-6-astra",
                key="sk-proj-localtest1234",
                base_url="http://127.0.0.1:%d/v1" % server.server_address[1],
                call_tool=sciforge,
                log=rec.log,
            )
            done = chat.send("make a box", rec.event)
        finally:
            server.shutdown()
            server.server_close()
        self.assertEqual(done["text"], "Box built.")
        self.assertEqual([c[0] for c in sciforge.calls], ["create_sketch", "extrude"])
        path, auth, body = _FakeOpenAI.seen[2]
        self.assertEqual(path, "/v1/responses")
        self.assertEqual(auth, "Bearer sk-proj-localtest1234")
        outputs = [i for i in body["input"] if i.get("type") == "function_call_output"]
        self.assertEqual([o["call_id"] for o in outputs], ["call_1", "call_2"])
        self.assertNotIn("sk-proj-localtest1234", json.dumps(rec.lines))


class Texts(unittest.TestCase):
    def test_system_prompt_and_cost_note(self):
        for words in (
            "Fusion",
            "millimetres",
            "degrees",
            "get_design",
            "screenshot",
            "undo step",
            "ids",
            "ask the person",
        ):
            self.assertIn(words, chat_core.SYSTEM_PROMPT)
        for words in (
            "billed",
            "separately",
            "subscription",
            "screenshots",
            "sent to",
            "free and private",
        ):
            self.assertIn(words, chat_core.COST_NOTE)


if __name__ == "__main__":
    unittest.main()
