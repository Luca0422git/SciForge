# SPDX-License-Identifier: LGPL-2.1-or-later
"""Small pieces every provider adapter needs: plain-JSON HTTP with urllib, hiding API keys
in any text we show or log, and the neutral conversation history the chat panel keeps.

Why a neutral history: the person can switch between Claude, ChatGPT, Gemini and a local
model between sessions, so the chat panel keeps ONE history in its own words and each
adapter turns it into its API's messages (to_provider_messages). A history entry is:

  {"role": "user", "text": "make a 40 x 30 x 10 box"}
  {"role": "assistant", "text": "...", "tool_calls": [{"id", "name", "args"}],
   "raw": {"provider": "anthropic", "model": "...", ...}}
  {"role": "user", "tool_results": [{"call": {"id", "name", "args"},
                                     "result": {"text", "image_png_base64", "is_error"}}]}

"raw" is what the provider sent back, kept so the SAME provider gets its own turn back
unchanged (Anthropic's thinking blocks, OpenAI's reasoning items and Gemini's thought
signatures must be returned as they came). Another provider rebuilds the turn from text
and tool_calls. The history only ever grows: earlier turns are never edited, because
some APIs reject a conversation whose earlier turns were changed.

Pure Python standard library: no FreeCAD, no Qt.
"""

import json
import re
import socket
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_TIMEOUT = 300  # seconds: a thinking model can take minutes for one answer
LIST_TIMEOUT = 15
NO_IMAGE_NOTE = "(a picture was taken; this model cannot see images)"

_LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1", "0.0.0.0")
_KEY_SHAPES = re.compile(
    r"(\bsk-[A-Za-z0-9_*-]{3,}|\bAIza[0-9A-Za-z_*-]{10,}|\bBearer\s+[A-Za-z0-9._*-]{8,})"
)
_SAFE_ID = re.compile(r"[^A-Za-z0-9_-]")


def default_log(line):
    print(line, file=sys.stderr)


def redact(text, *secrets):
    """text with every given secret and anything shaped like an API key hidden."""
    if not isinstance(text, str):
        text = str(text)
    for secret in secrets:
        if isinstance(secret, str) and len(secret) >= 4:
            text = text.replace(secret, "[key hidden]")
    return _KEY_SHAPES.sub("[key hidden]", text)


def is_local(url):
    try:
        host = urllib.parse.urlsplit(url).hostname or ""
    except ValueError:
        return False
    return host.lower() in _LOCAL_HOSTS


def _opener(url):
    # Never send localhost through a proxy (Windows often has a system proxy set, and a
    # proxy cannot reach Ollama / LM Studio on this computer).
    handlers = [urllib.request.HTTPSHandler(context=ssl.create_default_context())]
    if is_local(url):
        handlers.append(urllib.request.ProxyHandler({}))
    return urllib.request.build_opener(*handlers)


def _problem(exc):
    """A short word for a network failure: refused, timeout or network: <reason>."""
    reason = getattr(exc, "reason", exc)
    if isinstance(reason, ConnectionRefusedError) or isinstance(exc, ConnectionRefusedError):
        return "refused"
    if isinstance(reason, (socket.timeout, TimeoutError)) or isinstance(
        exc, (socket.timeout, TimeoutError)
    ):
        return "timeout"
    return "network: %s" % reason


def request_json(method, url, headers=None, body=None, timeout=DEFAULT_TIMEOUT):
    """One HTTP request with a JSON body and a JSON answer. Never raises.

    Returns (status, data, problem): status is the HTTP status (0 when no answer came),
    data the decoded JSON object (or None) and problem None, "refused", "timeout",
    "network: <reason>" or "bad_json"."""
    try:
        payload = None
        all_headers = {"Accept": "application/json"}
        all_headers.update(headers or {})
        if body is not None:
            payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
            all_headers.setdefault("Content-Type", "application/json")
        req = urllib.request.Request(url, data=payload, headers=all_headers, method=method)
        try:
            with _opener(url).open(req, timeout=timeout) as answer:
                status, raw = answer.status, answer.read()
        except urllib.error.HTTPError as exc:
            status = exc.code
            try:
                raw = exc.read()
            except Exception:
                raw = b""
        except (urllib.error.URLError, OSError) as exc:
            return 0, None, _problem(exc)
        if not raw:
            return status, None, None if status < 400 else "bad_json"
        try:
            data = json.loads(raw.decode("utf-8"))
        except ValueError:
            return status, {"text": raw.decode("utf-8", "replace")[:500]}, "bad_json"
        return status, data, None
    except Exception as exc:  # a broken URL or anything else: still an answer
        return 0, None, "network: %s" % exc


def post_json(url, headers, body, timeout=DEFAULT_TIMEOUT):
    return request_json("POST", url, headers, body, timeout)


def get_json(url, headers=None, timeout=LIST_TIMEOUT):
    return request_json("GET", url, headers, None, timeout)


def join(base_url, path):
    return base_url.rstrip("/") + "/" + path.lstrip("/")


def safe_id(value, index=0):
    """A tool call id every API accepts (letters, digits, _ and -, at most 64)."""
    text = _SAFE_ID.sub("_", str(value or ""))[:64]
    return text or "call_%d" % index


def parse_args(text):
    """Arguments sent as a JSON string -> (dict, None) or (None, problem sentence)."""
    if isinstance(text, dict):
        return text, None
    if text is None or (isinstance(text, str) and not text.strip()):
        return {}, None
    try:
        value = json.loads(text)
    except (TypeError, ValueError):
        return None, "the arguments were not valid JSON"
    if not isinstance(value, dict):
        return None, "the arguments must be a JSON object"
    return value, None


def tool_list(tools):
    """(name, description, schema) for each tool of tools_core.TOOLS (or a similar list)."""
    result = []
    for item in tools or []:
        schema = item.get("input_schema") or {"type": "object", "properties": {}}
        result.append((item["name"], item.get("description", ""), schema))
    return result


def result_text(result):
    text = result.get("text") if isinstance(result, dict) else None
    return text if isinstance(text, str) and text else "(no text)"


def neutral_turn(text="", tool_calls=None, stop="end", usage=None, progress=None, raw=None):
    return {
        "text": text,
        "tool_calls": tool_calls or [],
        "stop": stop,
        "usage": usage or {},
        "progress": progress or [],
        "raw": raw,
    }


def raw_for(entry, provider, model=None):
    """The entry's raw turn when it came from this provider (and, when model is given,
    this model); else None."""
    raw = entry.get("raw")
    if not isinstance(raw, dict) or raw.get("provider") != provider:
        return None
    if model is not None and raw.get("model") != model:
        return None
    return raw
