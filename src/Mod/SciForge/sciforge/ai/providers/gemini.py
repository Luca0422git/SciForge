# SPDX-License-Identifier: LGPL-2.1-or-later
"""Gemini through Google's Gemini API (generateContent), with plain urllib.

ai.google.dev was not reachable from the build machine; this follows Google's own
python-genai library (github.com/googleapis/python-genai, google/genai/types.py,
_transformers.py and README.md, read October 2026), whose fields are the REST fields in
snake_case. Not verified against the REST pages themselves:
  * POST {base}/v1beta/models/{model}:generateContent with header x-goog-api-key; body
    contents, systemInstruction, tools [{functionDeclarations: [...]}], generationConfig
    {maxOutputTokens};
  * a declaration's parametersJsonSchema takes JSON Schema, but only this subset: type,
    format, title, description, enum, items, prefixItems, minItems, maxItems, minimum,
    maximum, anyOf, oneOf, properties, additionalProperties, required (plus
    propertyOrdering). gemini_schema() rewrites ours into it: "default" and
    "exclusiveMinimum" move into the description, a list of types becomes anyOf, and a
    schema without a type gets one (the older "parameters" field would also reject
    additionalProperties on the Gemini API);
  * the answer: candidates[0].content {role: "model", parts}; a part holds text, or
    functionCall {name, args, id?}, and may carry a thoughtSignature that must go back
    unchanged, so the model's content is replayed as it came;
  * a result goes back as a functionResponse part {name, id?, response: {output | error},
    parts: [{inlineData: {mimeType, data}}]}: FunctionResponse.parts carries the
    screenshot (multimodal function responses);
  * finishReason STOP, MAX_TOKENS, SAFETY, ...; usageMetadata promptTokenCount /
    candidatesTokenCount;
  * GET {base}/v1beta/models lists models (models[].name "models/...",
    supportedGenerationMethods, nextPageToken).
The role of the turn carrying function responses is "user" (the SDK's README uses "tool",
which it maps): not verified.

Non-streaming only.
"""

import copy
import urllib.parse

from . import _common

NAME = "gemini"
DISPLAY_NAME = "Gemini (Google)"
NEEDS_KEY = True
BASE_URL = "https://generativelanguage.googleapis.com"
DEFAULT_MODEL = "gemini-flash-latest"  # Google's alias for the current Flash model
SUPPORTS_IMAGES = True
MAX_TOKENS = 16000

SCHEMA_KEYS = {
    "type",
    "format",
    "title",
    "description",
    "enum",
    "items",
    "prefixItems",
    "minItems",
    "maxItems",
    "minimum",
    "maximum",
    "anyOf",
    "oneOf",
    "properties",
    "additionalProperties",
    "required",
    "propertyOrdering",
}

_REFUSALS = {
    "SAFETY",
    "PROHIBITED_CONTENT",
    "BLOCKLIST",
    "SPII",
    "RECITATION",
    "IMAGE_SAFETY",
    "IMAGE_PROHIBITED_CONTENT",
}


def gemini_schema(schema):
    """A copy of a JSON Schema using only the keywords Gemini's parametersJsonSchema takes."""
    if not isinstance(schema, dict):
        return {}
    notes = []
    out = {}
    for key, value in schema.items():
        if key == "properties" and isinstance(value, dict):
            out[key] = {name: gemini_schema(sub) for name, sub in value.items()}
        elif key in ("items", "additionalProperties") and isinstance(value, dict):
            out[key] = gemini_schema(value)
        elif key in ("anyOf", "oneOf", "prefixItems") and isinstance(value, list):
            out[key] = [gemini_schema(sub) for sub in value]
        elif key == "type" and isinstance(value, list):
            out["anyOf"] = [{"type": kind} for kind in value]
        elif key == "exclusiveMinimum":
            notes.append("must be above %s" % _fmt(value))
            out.setdefault("minimum", value)
        elif key == "default":
            notes.append("default %s" % _fmt(value))
        elif key in SCHEMA_KEYS:
            out[key] = copy.deepcopy(value)
    if "type" not in out and "anyOf" not in out and "oneOf" not in out:
        # A schema without a type means "anything"; ours is SciForge's "at", an object or
        # a list of objects, so say exactly that.
        out["anyOf"] = [{"type": "object"}, {"type": "array", "items": {"type": "object"}}]
    if notes:
        text = out.get("description", "")
        out["description"] = (text + " " if text else "") + "(" + "; ".join(notes) + ")"
    return out


def _fmt(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _model_path(model):
    model = str(model or DEFAULT_MODEL)
    return model if model.startswith("models/") else "models/" + model


class Adapter:
    name = NAME
    display_name = DISPLAY_NAME
    max_tools = 128  # (kept to OpenAI's 128: a request with every tool is long)
    needs_key = NEEDS_KEY
    base_url = BASE_URL
    default_model = DEFAULT_MODEL
    supports_images = SUPPORTS_IMAGES

    def tools(self, tools):
        declarations = []
        for name, description, schema in _common.tool_list(tools):
            item = {"name": name, "description": description}
            if schema.get("properties"):
                item["parametersJsonSchema"] = gemini_schema(schema)
            declarations.append(item)
        return [{"functionDeclarations": declarations}] if declarations else []

    def build_request(
        self, model, system, messages, tools, max_tokens=MAX_TOKENS, key=None, base_url=None
    ):
        headers = {"Content-Type": "application/json"}
        if key:
            headers["x-goog-api-key"] = key
        body = {
            "contents": messages,
            "generationConfig": {"maxOutputTokens": int(max_tokens or MAX_TOKENS)},
        }
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        if tools:
            body["tools"] = self.tools(tools)
        path = "/v1beta/%s:generateContent" % urllib.parse.quote(_model_path(model), safe="/.-_")
        return _common.join(base_url or BASE_URL, path), headers, body

    def parse_response(self, data):
        try:
            return self._parse(data)
        except Exception:  # an answer in a shape we do not know
            return _common.neutral_turn(stop="unreadable")

    def _parse(self, data):
        data = data if isinstance(data, dict) else {}
        candidates = data.get("candidates") or []
        candidate = candidates[0] if candidates and isinstance(candidates[0], dict) else {}
        content = candidate.get("content") or {"role": "model", "parts": []}
        texts, calls, progress = [], [], []
        for index, part in enumerate(content.get("parts") or []):
            if not isinstance(part, dict):
                continue
            if "functionCall" in part:
                fc = part["functionCall"] or {}
                call = {"name": fc.get("name")}
                if fc.get("id"):
                    call["id"] = fc["id"]
                else:  # older models give no id: make one; it is not sent back
                    call["id"], call["id_generated"] = "call_%d" % index, True
                args = fc.get("args")
                call["args"] = args if isinstance(args, dict) else {}
                if args is not None and not isinstance(args, dict):
                    call["bad_args"] = "the arguments must be a JSON object"
                calls.append(call)
            elif part.get("text"):
                (progress if part.get("thought") else texts).append(part["text"])
        reason = candidate.get("finishReason")
        if not candidates and (data.get("promptFeedback") or {}).get("blockReason"):
            stop = "refusal"
        elif reason in _REFUSALS:
            stop = "refusal"
        elif reason == "MAX_TOKENS":
            stop = "max_tokens"
        elif reason in (None, "STOP", "FINISH_REASON_UNSPECIFIED"):
            stop = "tool_use" if calls else "end"
        else:
            stop = str(reason).lower()
        usage = data.get("usageMetadata") or {}
        return _common.neutral_turn(
            text="\n\n".join(texts),
            tool_calls=calls,
            stop=stop,
            usage={
                "input_tokens": usage.get("promptTokenCount", 0),
                "output_tokens": usage.get("candidatesTokenCount", 0),
            },
            progress=progress,
            raw={"provider": NAME, "model": data.get("modelVersion"), "content": content},
        )

    def tool_results_message(self, calls_and_results, send_ids=True):
        parts = []
        for call, result in calls_and_results:
            text = _common.result_text(result)
            is_error = isinstance(result, dict) and result.get("is_error")
            response = {
                "name": call.get("name"),
                "response": {"error" if is_error else "output": text},
            }
            if send_ids and call.get("id") and not call.get("id_generated"):
                response["id"] = call["id"]
            image = result.get("image_png_base64") if isinstance(result, dict) else None
            if image:
                response["parts"] = [{"inlineData": {"mimeType": "image/png", "data": image}}]
            parts.append({"functionResponse": response})
        return [{"role": "user", "parts": parts}] if parts else []

    def to_provider_messages(self, history, model=None):
        contents = []
        replayed = False  # did the last assistant turn go back as Gemini sent it?
        for entry in history:
            if entry.get("role") == "user":
                if entry.get("tool_results"):
                    pairs = [(r["call"], r["result"]) for r in entry["tool_results"]]
                    contents.extend(self.tool_results_message(pairs, send_ids=replayed))
                elif entry.get("text"):
                    contents.append({"role": "user", "parts": [{"text": entry["text"]}]})
                continue
            # The modelVersion Gemini reports can differ from the alias asked for, so a
            # Gemini turn goes back unchanged whatever the model (thought signatures).
            raw = _common.raw_for(entry, NAME)
            replayed = bool(raw and raw.get("content", {}).get("parts"))
            if replayed:
                contents.append(copy.deepcopy(raw["content"]))
                continue
            parts = [{"text": entry["text"]}] if entry.get("text") else []
            for call in entry.get("tool_calls") or []:
                parts.append(
                    {"functionCall": {"name": call.get("name"), "args": call.get("args") or {}}}
                )
            if parts:
                contents.append({"role": "model", "parts": parts})
        return contents

    def list_models(self, key, base_url=None, http_get=_common.get_json):
        try:
            headers = {"x-goog-api-key": key} if key else {}
            ids, token = [], None
            for _page in range(10):
                url = _common.join(base_url or BASE_URL, "/v1beta/models?pageSize=1000")
                if token:
                    url += "&pageToken=" + urllib.parse.quote(token)
                status, data, _problem = http_get(url, headers)
                if status != 200 or not isinstance(data, dict):
                    break
                for model in data.get("models") or []:
                    methods = model.get("supportedGenerationMethods") or []
                    name = model.get("name") or ""
                    if "generateContent" in methods and name:
                        ids.append(name[len("models/") :] if name.startswith("models/") else name)
                token = data.get("nextPageToken")
                if not token:
                    break
            return ids
        except Exception:
            return []

    def key_refused(self, status, data):
        if status in (401, 403):
            return True
        # Gemini answers a wrong key with 400 INVALID_ARGUMENT "API key not valid".
        error = (data or {}).get("error") if isinstance(data, dict) else None
        text = str(error or "")
        return status == 400 and ("API_KEY_INVALID" in text or "API key not valid" in text)
