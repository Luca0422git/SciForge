# SPDX-License-Identifier: LGPL-2.1-or-later
"""ChatGPT's models through OpenAI's Responses API (POST /v1/responses), with plain urllib.

Checked against OpenAI's OpenAPI description (github.com/openai/openai-openapi,
openapi.yaml, version 2.3.0, read October 2026; platform.openai.com itself was not
reachable from the build machine):
  * Authorization: Bearer <key>; body model, instructions (the system prompt), input (a
    list of items), tools, max_output_tokens, store;
  * function tools are {type: "function", name, description, parameters (JSON Schema),
    strict}; strict is left off because strict mode needs every property required, which
    our optional arguments are not;
  * the answer's output holds items: message (content of output_text parts), reasoning
    (encrypted_content, summary) and function_call {call_id, name, arguments (a JSON
    string)}; status completed / incomplete with incomplete_details.reason
    max_output_tokens or content_filter;
  * a result goes back as {type: "function_call_output", call_id, output}; output may be a
    string or a list of input_text / input_image parts (image_url can be a base64 data
    URL), so screenshots ride inside the result itself;
  * store is false: nothing is kept on OpenAI's side, so the whole history is sent each
    time and reasoning items go back with their encrypted_content, as the spec asks for
    stateless use;
  * GET /v1/models lists the models (data[].id).

Non-streaming only.
"""

import copy
import json

from . import _common

NAME = "openai"
DISPLAY_NAME = "ChatGPT (OpenAI)"
NEEDS_KEY = True
BASE_URL = "https://api.openai.com/v1"
# NOT VERIFIED against OpenAI's model list (platform.openai.com unreachable from the
# sandbox): the spec's own example. The chat panel offers the models the key lists.
DEFAULT_MODEL = "gpt-6-astra"
SUPPORTS_IMAGES = True
MAX_TOKENS = 16000

# GET /v1/models also lists models that cannot chat (speech, pictures, embeddings...).
_NOT_CHAT = (
    "embedding",
    "tts",
    "whisper",
    "transcribe",
    "dall-e",
    "image",
    "audio",
    "realtime",
    "moderation",
    "davinci",
    "babbage",
    "sora",
    "translate",
)


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
                "name": name,
                "description": description,
                "parameters": copy.deepcopy(schema),
            }
            for name, description, schema in _common.tool_list(tools)
        ]

    def build_request(
        self, model, system, messages, tools, max_tokens=MAX_TOKENS, key=None, base_url=None
    ):
        headers = {"Content-Type": "application/json"}
        if key:
            headers["Authorization"] = "Bearer " + key
        body = {
            "model": model,
            "input": messages,
            "max_output_tokens": int(max_tokens or MAX_TOKENS),
            "store": False,
        }
        if system:
            body["instructions"] = system
        if tools:
            body["tools"] = self.tools(tools)
        return _common.join(base_url or BASE_URL, "/responses"), headers, body

    def parse_response(self, data):
        try:
            return self._parse(data)
        except Exception:  # an answer in a shape we do not know
            return _common.neutral_turn(stop="unreadable")

    def _parse(self, data):
        data = data if isinstance(data, dict) else {}
        output = [item for item in data.get("output") or [] if isinstance(item, dict)]
        texts, calls, progress, refused = [], [], [], False
        for index, item in enumerate(output):
            kind = item.get("type")
            if kind == "message":
                for part in item.get("content") or []:
                    if part.get("type") == "output_text" and part.get("text"):
                        texts.append(part["text"])
                    elif part.get("type") == "refusal":
                        refused = True
                        if part.get("refusal"):
                            texts.append(part["refusal"])
            elif kind == "reasoning":
                for part in item.get("summary") or []:
                    if (part.get("text") or "").strip():
                        progress.append(part["text"].strip())
            elif kind == "function_call":
                args, problem = _common.parse_args(item.get("arguments"))
                call = {
                    "id": item.get("call_id") or item.get("id") or "call_%d" % index,
                    "name": item.get("name"),
                    "args": args if args is not None else {},
                }
                if problem:
                    call["bad_args"] = problem
                calls.append(call)
        reason = (data.get("incomplete_details") or {}).get("reason")
        if refused or reason == "content_filter":
            stop = "refusal"
        elif data.get("status") == "incomplete" and reason == "max_output_tokens":
            stop = "max_tokens"
        elif data.get("status") in (None, "completed"):
            stop = "tool_use" if calls else "end"
        else:
            stop = reason or data.get("status")
        usage = data.get("usage") or {}
        return _common.neutral_turn(
            text="\n\n".join(texts),
            tool_calls=calls,
            stop=stop,
            usage={
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
            },
            progress=progress,
            raw={"provider": NAME, "model": data.get("model"), "items": output},
        )

    def tool_results_message(self, calls_and_results):
        items = []
        for call, result in calls_and_results:
            text = _common.result_text(result)
            if isinstance(result, dict) and result.get("is_error"):
                text = "Error: " + text
            image = result.get("image_png_base64") if isinstance(result, dict) else None
            if image:
                output = [
                    {"type": "input_text", "text": text},
                    {
                        "type": "input_image",
                        "image_url": "data:image/png;base64," + image,
                        "detail": "auto",
                    },
                ]
            else:
                output = text
            items.append(
                {
                    "type": "function_call_output",
                    "call_id": _common.safe_id(call.get("id")),
                    "output": output,
                }
            )
        return items

    def to_provider_messages(self, history, model=None):
        items = []
        for entry in history:
            if entry.get("role") == "user":
                if entry.get("tool_results"):
                    pairs = [(r["call"], r["result"]) for r in entry["tool_results"]]
                    items.extend(self.tool_results_message(pairs))
                elif entry.get("text"):
                    items.append({"role": "user", "content": entry["text"]})
                continue
            # Reasoning items belong to the model that wrote them: replay them only there.
            raw = _common.raw_for(entry, NAME, model)
            if raw and raw.get("items"):
                items.extend(copy.deepcopy(raw["items"]))
                continue
            if entry.get("text"):
                items.append({"role": "assistant", "content": entry["text"]})
            for index, call in enumerate(entry.get("tool_calls") or []):
                items.append(
                    {
                        "type": "function_call",
                        "call_id": _common.safe_id(call.get("id"), index),
                        "name": call.get("name"),
                        "arguments": json.dumps(call.get("args") or {}),
                    }
                )
        return items

    def list_models(self, key, base_url=None, http_get=_common.get_json):
        try:
            headers = {"Authorization": "Bearer " + key} if key else {}
            status, data, _problem = http_get(
                _common.join(base_url or BASE_URL, "/models"), headers
            )
            if status != 200 or not isinstance(data, dict):
                return []
            ids = [m.get("id") for m in data.get("data") or [] if isinstance(m, dict)]
            return sorted(
                (i for i in ids if i and not any(word in i.lower() for word in _NOT_CHAT)),
                reverse=True,
            )
        except Exception:
            return []

    def key_refused(self, status, data):
        return status in (401, 403)
