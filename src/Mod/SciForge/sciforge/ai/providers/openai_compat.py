# SPDX-License-Identifier: LGPL-2.1-or-later
"""Any server that speaks OpenAI's Chat Completions API (POST {base}/chat/completions):
Ollama (http://localhost:11434/v1) and LM Studio (http://localhost:1234/v1) on this
computer, free and private, or another OpenAI-compatible service.

Checked against OpenAI's OpenAPI description (openapi.yaml 2.3.0: ChatCompletionTool,
ChatCompletionMessageToolCall, ChatCompletionRequestToolMessage, finish_reason stop /
length / tool_calls / content_filter) and Ollama's docs/api/openai-compatibility.mdx on
GitHub (October 2026: tools, max_tokens and /v1/models are supported; the API key is
"required but ignored"). LM Studio's own page was not reachable: not verified beyond
"it speaks the same API".
  * tools: [{type: "function", function: {name, description, parameters}}];
  * the answer: choices[0].message {content, tool_calls: [{id, type: "function",
    function: {name, arguments (a JSON string)}}]};
  * a result goes back as {role: "tool", tool_call_id, content (text)}. Tool messages are
    text only, so a screenshot becomes a sentence saying a picture was taken.
Local models are less reliable with tools: a call with broken JSON comes back to the
model as an error so it can try again.

Non-streaming only.
"""

import copy
import json

from . import _common

NAME = "openai_compat"
DISPLAY_NAME = "Local or other (OpenAI-compatible: Ollama, LM Studio)"
NEEDS_KEY = False
BASE_URL = "http://localhost:11434/v1"
LM_STUDIO_URL = "http://localhost:1234/v1"
# No model is the same on every computer: "" means "the first model the server lists"
# (see providers.default_model()).
DEFAULT_MODEL = ""
SUPPORTS_IMAGES = False
MAX_TOKENS = 8000

_STOPS = {
    "stop": "end",
    "length": "max_tokens",
    "tool_calls": "tool_use",
    "content_filter": "refusal",
}


class Adapter:
    name = NAME
    display_name = DISPLAY_NAME
    needs_key = NEEDS_KEY
    base_url = BASE_URL
    default_model = DEFAULT_MODEL
    supports_images = SUPPORTS_IMAGES

    def tools(self, tools):
        return [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": copy.deepcopy(schema),
                },
            }
            for name, description, schema in _common.tool_list(tools)
        ]

    def build_request(
        self, model, system, messages, tools, max_tokens=MAX_TOKENS, key=None, base_url=None
    ):
        headers = {"Content-Type": "application/json"}
        if key:
            headers["Authorization"] = "Bearer " + key
        all_messages = ([{"role": "system", "content": system}] if system else []) + messages
        body = {
            "model": model,
            "messages": all_messages,
            "max_tokens": int(max_tokens or MAX_TOKENS),
            "stream": False,
        }
        if tools:
            body["tools"] = self.tools(tools)
        return _common.join(base_url or BASE_URL, "/chat/completions"), headers, body

    def parse_response(self, data):
        try:
            return self._parse(data)
        except Exception:  # an answer in a shape we do not know
            return _common.neutral_turn(stop="unreadable")

    def _parse(self, data):
        data = data if isinstance(data, dict) else {}
        choices = data.get("choices") or []
        choice = choices[0] if choices and isinstance(choices[0], dict) else {}
        message = choice.get("message") or {}
        calls = []
        for index, item in enumerate(message.get("tool_calls") or []):
            function = item.get("function") or {}
            args, problem = _common.parse_args(function.get("arguments"))
            call = {
                "id": item.get("id") or "call_%d" % index,
                "name": function.get("name"),
                "args": args if args is not None else {},
            }
            if problem:
                call["bad_args"] = problem
            calls.append(call)
        stop = _STOPS.get(choice.get("finish_reason"), choice.get("finish_reason") or "end")
        if calls and stop == "end":
            stop = "tool_use"  # some local servers say "stop" next to tool calls
        content = message.get("content")
        if isinstance(content, list):  # some servers send parts
            content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
        usage = data.get("usage") or {}
        return _common.neutral_turn(
            text=(content or "").strip(),
            tool_calls=calls,
            stop=stop,
            usage={
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
            },
            raw=None,  # nothing hidden to replay: text and tool_calls rebuild the turn
        )

    def tool_results_message(self, calls_and_results):
        messages = []
        for call, result in calls_and_results:
            text = _common.result_text(result)
            if isinstance(result, dict) and result.get("is_error"):
                text = "Error: " + text
            if isinstance(result, dict) and result.get("image_png_base64"):
                text += " " + _common.NO_IMAGE_NOTE
            messages.append(
                {"role": "tool", "tool_call_id": _common.safe_id(call.get("id")), "content": text}
            )
        return messages

    def to_provider_messages(self, history, model=None):
        messages = []
        for entry in history:
            if entry.get("role") == "user":
                if entry.get("tool_results"):
                    pairs = [(r["call"], r["result"]) for r in entry["tool_results"]]
                    messages.extend(self.tool_results_message(pairs))
                elif entry.get("text"):
                    messages.append({"role": "user", "content": entry["text"]})
                continue
            calls = entry.get("tool_calls") or []
            if not entry.get("text") and not calls:
                continue
            message = {"role": "assistant", "content": entry.get("text") or ""}
            if calls:
                message["tool_calls"] = [
                    {
                        "id": _common.safe_id(call.get("id"), index),
                        "type": "function",
                        "function": {
                            "name": call.get("name"),
                            "arguments": json.dumps(call.get("args") or {}),
                        },
                    }
                    for index, call in enumerate(calls)
                ]
            messages.append(message)
        return messages

    def list_models(self, key, base_url=None, http_get=_common.get_json):
        try:
            headers = {"Authorization": "Bearer " + key} if key else {}
            status, data, _problem = http_get(
                _common.join(base_url or BASE_URL, "/models"), headers
            )
            if status != 200 or not isinstance(data, dict):
                return []
            ids = [m.get("id") for m in data.get("data") or [] if isinstance(m, dict)]
            return [i for i in ids if i and "embed" not in i.lower()]
        except Exception:
            return []

    def key_refused(self, status, data):
        return status in (401, 403)
