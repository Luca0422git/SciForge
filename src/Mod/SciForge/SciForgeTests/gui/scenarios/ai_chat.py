# SPDX-License-Identifier: LGPL-2.1-or-later
"""The AI chat panel (docs/sciforge/parity/ai.md, brief home-cloud-ai.md M4) against a fake
AI provider: a local server in this test that answers like Ollama / LM Studio (the
OpenAI-compatible Chat Completions API) with scripted answers. Real clicks and typing.

Path 1, the panel opens; Local or other: the address typed, List asks the server for its
  models (qwen3:8b).
Path 2, "make a 40 x 30 x 10 box": the model asks for create_sketch, then extrude, then
  answers; the box is built (12000 mm3), each step one Undo step; the model got SciForge's
  answers (the sketch's id) back.
Path 3, a model that never stops asking for tools: Stop ends the chat after the current step.
Path 4, Claude: a key typed and kept (Save key), read back, never in SciForge's log; removed.
"""

import http.server
import json
import threading
import time

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import versions_input as vi
from SciForgeTests.gui import widget_input as wi

s = {"script": [], "requests": [], "loop": False}
KEY = "sk-test-SECRET-1234567890"


def _call(name, args, n):
    return {
        "id": "chatcmpl-%d" % n,
        "object": "chat.completion",
        "model": "qwen3:8b",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_%d" % n,
                            "index": 0,
                            "type": "function",
                            "function": {"name": name, "arguments": json.dumps(args)},
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
    }


def _final(text):
    return {
        "id": "chatcmpl-final",
        "object": "chat.completion",
        "model": "qwen3:8b",
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}
        ],
    }


class _Fake(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def _json(self, data):
        body = json.dumps(data).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.endswith("/models"):
            self._json({"object": "list", "data": [{"id": "qwen3:8b", "object": "model"}]})
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        s["requests"].append(json.loads(self.rfile.read(length) or b"{}"))
        if s["loop"]:
            time.sleep(0.3)  # a real model takes seconds per answer: time to press Stop
            self._json(_call("get_design", {}, len(s["requests"])))
        elif s["script"]:
            self._json(s["script"].pop(0))
        else:
            self._json(_final("Nothing more to do."))


def panel():
    from sciforge.ai import chat_ui

    return chat_ui.panel()


def transcript():
    p = panel()
    return p.transcript.toPlainText() if p is not None else ""


def body_volume():
    doc = App.ActiveDocument
    if doc is None:
        return None
    return sum(
        o.Shape.Volume
        for o in doc.Objects
        if o.TypeId == "PartDesign::Body" and not o.Shape.isNull()
    )


def pick(combo, data):
    """Choose an entry with the keyboard (as a person tabbing through the form)."""
    index = combo.findData(data)
    combo.setFocus()
    from PySide6 import QtTest
    from PySide import QtCore

    while combo.currentIndex() != index:
        key = QtCore.Qt.Key_Down if combo.currentIndex() < index else QtCore.Qt.Key_Up
        QtTest.QTest.keyClick(combo, key)


# -- Path 1 ---------------------------------------------------------------------------------
def setup():
    import signal

    signal.signal(signal.SIGPIPE, signal.SIG_IGN)  # (as the bridge does: bridge.py)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Fake)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    s["server"] = server
    s["url"] = "http://127.0.0.1:%d/v1" % server.server_address[1]
    Gui.runCommand("SciForge_AIChat")


def choose_local():
    p = panel()
    h.check("the AI chat panel opened", p is not None and p.isVisible())
    if p is None:
        return
    h.check("it says what API use costs", "billed" in p.note.text(), p.note.text())
    pick(p.provider, "openai_compat")
    h.check("Local or other needs no key", not p.key.isVisible() and p.address.isVisible())
    vi.type_into(p.address, s["url"])
    wi.click(p.models_button)


choose_local.wait_ms = 1500


def models_listed():
    p = panel()
    items = [p.model.itemText(i) for i in range(p.model.count())]
    h.check("List asked the server for its models", items == ["qwen3:8b"], items)


# -- Path 2 ---------------------------------------------------------------------------------
def ask_for_a_box():
    s["script"] = [
        _call("create_sketch", {"plane": "XY", "geometry": [{"rect": [0, 0, 40, 30]}]}, 1),
        _call("extrude", {"profile": "Sketch1", "distance": 10}, 2),
        _final("Done: a 40 x 30 x 10 mm box."),
    ]
    p = panel()
    p.input.setFocus()
    from PySide6 import QtTest

    QtTest.QTest.keyClicks(p.input, "make a 40 x 30 x 10 box")
    wi.click(p.send_button)


ask_for_a_box.wait_ms = 6000


def box_built():
    p = panel()
    text = transcript()
    h.check("the AI's answer is shown", "Done: a 40 x 30 x 10 mm box." in text, text[-600:])
    h.check("40 x 30 x 10 = 12000 mm3", abs((body_volume() or 0) - 12000) < 1e-6, body_volume())
    doc = App.ActiveDocument
    names = doc.UndoNames[:2] if doc else []
    h.check("one Undo step each", names == ["AI: Extrude 10 mm", "AI: Sketch on XY"], names)
    h.check("Send is ready again", p.send_button.isEnabled() and not p.stop_button.isEnabled())
    tool_messages = [
        m for r in s["requests"] for m in r.get("messages", []) if m.get("role") == "tool"
    ]
    h.check(
        "the model got SciForge's answers back (the sketch's id)",
        any("'Sketch1'" in str(m.get("content")) for m in tool_messages),
        tool_messages[:1],
    )
    from sciforge.ai import catalog
    from sciforge.ai.providers import openai_compat

    sent = [t.get("function", t).get("name") for t in s["requests"][0].get("tools", [])]
    h.check(
        "the model got the tools a local model takes, the first 16 first",
        len(sent) == openai_compat.Adapter.max_tools and sent[:16] == list(catalog.LEGACY_NAMES),
        (len(sent), sent[:20]),
    )
    h.shot("chat")


# -- Path 3 ---------------------------------------------------------------------------------
def endless_model():
    s["loop"] = True
    s["before"] = len(s["requests"])
    p = panel()
    vi.type_into(p.input, "look at it again and again")
    wi.click(p.send_button)


endless_model.wait_ms = 1500


def press_stop():
    p = panel()
    h.check("Stop is offered while the chat runs", p.stop_button.isEnabled())
    wi.click(p.stop_button)


press_stop.wait_ms = 4000


def stopped():
    p = panel()
    s["loop"] = False
    asked = len(s["requests"]) - s["before"]
    h.check("Stop ended the chat", p.send_button.isEnabled() and not p.busy(), asked)
    h.check("... well before the step limit", 0 < asked < 25, asked)
    h.check("... and says so", "Stopping" in transcript(), transcript()[-300:])


# -- Path 4 ---------------------------------------------------------------------------------
def keep_a_key():
    p = panel()
    pick(p.provider, "anthropic")
    h.check("Claude needs a key", p.key.isVisible() and not p.address.isVisible())
    vi.type_into(p.key, KEY)
    wi.click(p.save_key_button)


def key_kept():
    from sciforge import secrets_store
    from sciforge.ai import chat_ui

    h.check(
        "the key is kept",
        secrets_store.read("ai.anthropic", chat_ui.secrets_folder()) == KEY,
    )
    h.check("... and never in SciForge's log", KEY not in h.report_text())
    p = panel()
    vi.type_into(p.key, "")
    wi.click(p.save_key_button)


def key_removed():
    from sciforge import secrets_store
    from sciforge.ai import chat_ui

    h.check(
        "an empty key removes it",
        secrets_store.read("ai.anthropic", chat_ui.secrets_folder()) is None,
    )
    s["server"].shutdown()
    h.check("no pop-up left", not h.popups(), h.popups())


h.run(
    "ai_chat",
    [
        setup,
        choose_local,
        models_listed,
        ask_for_a_box,
        box_built,
        endless_model,
        press_stop,
        stopped,
        keep_a_key,
        key_kept,
        key_removed,
    ],
)
