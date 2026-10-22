# SPDX-License-Identifier: LGPL-2.1-or-later
"""The built-in chat panel's agent loop, without any window or network code of its own
(docs/sciforge/dev/briefs/home-cloud-ai.md, section 4.5), so it can be unit tested.

The person types a request; Chat.send() asks the model; when the model calls SciForge's
tools (the catalogue, sciforge/ai/catalog: as many as the provider takes, the most useful
first) each call is checked with tools_core.validate() and run
through call_tool (the chat panel's callback, which runs bridge.call on the GUI thread);
the results (text, and screenshots as pictures) go back to the model; this repeats until
the model answers in words, MAX_STEPS requests were made, or stop() was called.

Threads: send() blocks for as long as the model works, so the chat panel runs it on a
worker thread. stop() may be called from any thread; it is checked between steps and
between tool calls (a request already on its way is not cut off). on_event(kind, data)
reports progress from the worker thread: the GUI must hand it over to the GUI thread.

Nothing here raises: problems come back as plain sentences (event "error" and the
result's text). API keys never appear in logs or messages.
"""

import threading
import time

from . import catalog, tools_core
from .providers import _common

MAX_STEPS = 25
RETRIES = 2  # for "the provider had a problem" (5xx / overloaded) answers
RETRY_DELAYS = (2, 6)

SYSTEM_PROMPT = (
    "You are the design assistant inside SciForge, a parametric CAD program that works "
    "like Autodesk Fusion. You build and change the design open in SciForge with the tools "
    "you are given: sketches, then extrude, revolve, sweep, loft, hole, fillet, chamfer, "
    "shell, patterns, assemblies, drawings and parameters, each as a step in the design's "
    "timeline; get_timeline, get_step and edit_step read and change what exists, list_tools "
    "lists every tool and get_help explains selectors, picks and curves. All lengths are "
    "millimetres (mm) and all angles degrees. Call get_design before changing a design, and use "
    "get_design or screenshot after a change to check that it came out as intended. Every "
    "tool call that changes the design is one undo step in SciForge; undo takes back the "
    "last one. Refer to earlier steps by the ids get_design and the tools report (for "
    "example the sketch id as an extrude's profile). If a tool answers with an error, read "
    "it, fix the arguments and try again. When the request is unclear or a choice matters "
    "(a size, which face, whether to replace a file), ask the person instead of guessing. "
    "Keep answers short and plain: the person may be new to CAD. How to pick faces and "
    "edges: " + catalog.SELECTOR_HELP.replace("\n", " ")
)

COST_NOTE = (
    "Using an AI through its API is billed by that provider for each use, separately from "
    "any chat subscription (such as Claude Pro or ChatGPT Plus). The design's data and the "
    "screenshots the AI takes are sent to that provider. The local option (Ollama or LM "
    "Studio on this computer) is free and private: nothing leaves your computer."
)

STOPPED_TEXT = (
    "Stopped. The steps already made stay in the design's timeline; Undo takes them back."
)

EVENTS = ("text", "progress", "tool_call", "tool_result", "error", "done")


def post_json(url, headers, body, timeout=_common.DEFAULT_TIMEOUT):
    """POST JSON with urllib: (status, data, problem); see providers._common.request_json."""
    return _common.post_json(url, headers, body, timeout)


def describe_error(status, data, problem, provider_name, base_url="", model="", adapter=None):
    """A plain sentence for a failed request (keys are hidden by the caller)."""
    who = provider_name or "The AI provider"
    if status == 0:
        if problem == "refused":
            if _common.is_local(base_url):
                return (
                    "Nothing answered at %s. Is Ollama / LM Studio running (and is its server "
                    "switched on)?" % base_url
                )
            return "Could not reach %s: the connection was refused." % who
        if problem == "timeout":
            return "%s did not answer in time. Try again in a moment." % who
        detail = str(problem or "").replace("network: ", "")
        return "Could not reach %s. Check the internet connection (%s)." % (who, detail)
    refused = adapter.key_refused(status, data) if adapter is not None else status in (401, 403)
    if refused:
        return (
            "The key was refused by %s. Check it in the AI settings: it may be mistyped, "
            "revoked, or for another account." % who
        )
    if status in (402, 429):
        return (
            "%s says there were too many requests or no credit is left. Wait a minute and "
            "try again, or check your plan and billing on the provider's website." % who
        )
    if status >= 500:
        return "%s had a problem (error %d). Try again in a moment." % (who, status)
    message = _error_message(data)
    if status == 404:
        return "%s does not offer the model %r (%s). Pick another model." % (
            who,
            model,
            message or "not found",
        )
    return "%s did not accept the request (error %d): %s" % (who, status, message or "no detail")


def _error_message(data):
    if not isinstance(data, dict):
        return ""
    error = data.get("error")
    if isinstance(error, dict):
        text = error.get("message") or error.get("status") or ""
    elif isinstance(error, str):
        text = error
    else:
        text = data.get("message") or data.get("text") or ""
    text = " ".join(str(text).split())
    return text[:300]


def _result(text, image=None, is_error=False):
    return {"text": text, "image_png_base64": image or None, "is_error": bool(is_error)}


class Chat:
    """One conversation with one provider. history holds the neutral history (see
    providers/_common.py); give an earlier history to continue it with another provider."""

    def __init__(
        self,
        adapter,
        model,
        key=None,
        base_url=None,
        call_tool=None,
        log=None,
        http=post_json,
        max_steps=MAX_STEPS,
        max_tokens=None,
        system=SYSTEM_PROMPT,
        tools=None,
        history=None,
        sleep=time.sleep,
    ):
        self.adapter = adapter
        self.model = model or getattr(adapter, "default_model", "")
        self.base_url = base_url or getattr(adapter, "base_url", "")
        self.call_tool = call_tool
        self.http = http
        self.max_steps = max(1, int(max_steps))
        self.max_tokens = max_tokens
        self.system = system
        self.tools = (
            catalog.chat_tools(getattr(adapter, "max_tools", None)) if tools is None else tools
        )
        self.history = list(history or [])
        self.usage = {"input_tokens": 0, "output_tokens": 0}
        self._key = key or None
        self._log = log or _common.default_log
        self._sleep = sleep
        self._stop = threading.Event()
        self._busy = threading.Lock()
        self._running = threading.Event()
        self._last_error = ""

    # -- small helpers ----------------------------------------------------------------
    @property
    def provider_name(self):
        return getattr(self.adapter, "display_name", "The AI provider")

    def busy(self):
        """True while send() works (from the moment Stop can take effect)."""
        return self._running.is_set()

    def stop(self):
        """Ask send() to stop at the next step (thread-safe)."""
        self._stop.set()

    def stopped(self):
        return self._stop.is_set()

    def _hide(self, text):
        return _common.redact(text, self._key)

    def log(self, message):
        try:
            self._log(self._hide("[SciForge] AI chat: %s" % message))
        except Exception:
            pass

    def _emit(self, on_event, kind, data):
        if on_event is None:
            return
        try:
            on_event(kind, data)
        except Exception as exc:
            self.log("the chat panel could not show a %s event: %s" % (kind, exc))

    # -- the loop ---------------------------------------------------------------------
    def send(self, user_text, on_event=None):
        """Send the person's message and work until the model's final answer.

        Returns {"ok", "reason" ("end", "stopped", "max_steps", "max_tokens", "refusal",
        "error", "busy"), "text" (the final answer or the problem in a sentence), "steps",
        "usage"}; the same dict is sent as the "done" event."""
        if not self._busy.acquire(blocking=False):
            done = {"ok": False, "reason": "busy", "text": "The AI is still working.", "steps": 0}
            done["usage"] = dict(self.usage)
            self._emit(on_event, "error", done["text"])
            return done
        try:
            self._stop.clear()
            self._running.set()
            try:
                done = self._send(user_text, on_event)
            except Exception as exc:  # never let a bug escape into the chat panel
                self.log("unexpected problem: %s" % exc)
                done = self._finish(False, "error", "Something went wrong in the chat: %s" % exc, 0)
                self._emit(on_event, "error", done["text"])
            done["text"] = self._hide(done["text"])
        finally:
            self._running.clear()
            self._busy.release()
        self._emit(on_event, "done", done)  # after the release: the next send() may follow
        return done

    def _finish(self, ok, reason, text, steps):
        return {"ok": ok, "reason": reason, "text": text, "steps": steps, "usage": dict(self.usage)}

    def _send(self, user_text, on_event):
        text = (user_text or "").strip()
        if not text:
            return self._finish(False, "error", "There is no message to send.", 0)
        if getattr(self.adapter, "needs_key", False) and not self._key:
            message = "Add a key for %s first (AI settings)." % self.provider_name
            self._emit(on_event, "error", message)
            return self._finish(False, "error", message, 0)
        if not self.model:
            message = "Pick a model first."
            self._emit(on_event, "error", message)
            return self._finish(False, "error", message, 0)
        self.history.append({"role": "user", "text": text})
        self.log("asking %s (%s)" % (self.provider_name, self.model))
        steps = 0
        last_text = ""
        while steps < self.max_steps:
            if self.stopped():
                return self._finish(True, "stopped", STOPPED_TEXT, steps)
            steps += 1
            turn = self._ask(on_event)
            if turn is None:
                message = self._last_error
                return self._finish(False, "error", message, steps)
            for note in turn["progress"]:
                self._emit(on_event, "progress", note)
            entry = {"role": "assistant", "text": turn["text"], "tool_calls": turn["tool_calls"]}
            if turn.get("raw") is not None:
                entry["raw"] = turn["raw"]
            self.history.append(entry)
            if turn["text"]:
                last_text = turn["text"]
                self._emit(on_event, "text", turn["text"])
            calls = turn["tool_calls"]
            if turn["stop"] == "refusal":
                self._close(calls, "Not run: the answer was declined.")
                message = last_text or "%s declined this request." % self.provider_name
                return self._finish(False, "refusal", message, steps)
            if turn["stop"] == "max_tokens":
                self._close(calls, "Not run: the answer was cut off before it was complete.")
                message = (last_text + "\n\n" if last_text else "") + (
                    "(The answer was cut off because it got too long.)"
                )
                return self._finish(False, "max_tokens", message, steps)
            if not calls:
                if turn["stop"] == "pause":
                    continue  # the provider paused a long turn: ask it to go on
                return self._finish(True, "end", last_text or "(The AI gave no answer.)", steps)
            self._run_calls(calls, on_event)
        message = (
            'Stopped after %d steps without a final answer. Say "go on" to let the AI '
            "continue, or ask in smaller steps." % self.max_steps
        )
        self._emit(on_event, "error", message)
        return self._finish(False, "max_steps", message, steps)

    def _ask(self, on_event):
        """One request -> the neutral turn, or None (self._last_error says why)."""
        self._last_error = ""
        messages = self.adapter.to_provider_messages(self.history, self.model)
        kwargs = {"key": self._key, "base_url": self.base_url}
        if self.max_tokens:
            kwargs["max_tokens"] = self.max_tokens
        url, headers, body = self.adapter.build_request(
            self.model, self.system, messages, self.tools, **kwargs
        )
        for attempt in range(RETRIES + 1):
            try:
                status, data, problem = self.http(url, headers, body)
            except Exception as exc:
                status, data, problem = 0, None, "network: %s" % exc
            if status == 200 and problem is None and isinstance(data, dict):
                turn = self.adapter.parse_response(data)
                if turn["stop"] == "unreadable":
                    break
                for key in self.usage:
                    value = (turn.get("usage") or {}).get(key)
                    if isinstance(value, int):
                        self.usage[key] += value
                return turn
            retry = status >= 500 and attempt < RETRIES and not self.stopped()
            self.log(
                "request failed (status %s%s)%s"
                % (status, ", " + problem if problem else "", ", trying again" if retry else "")
            )
            if not retry:
                break
            self._sleep(RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)])
        if status == 200:
            message = "%s sent an answer SciForge could not read." % self.provider_name
        else:
            message = describe_error(
                status, data, problem, self.provider_name, self.base_url, self.model, self.adapter
            )
        self._last_error = self._hide(message)
        self._emit(on_event, "error", self._last_error)
        return None

    def _run_calls(self, calls, on_event):
        results = []
        for call in calls:
            if self.stopped():
                result = _result("Not run: the person pressed Stop.", is_error=True)
            else:
                self._emit(on_event, "tool_call", dict(call))
                result = self._run_tool(call)
                self._emit(
                    on_event,
                    "tool_result",
                    {
                        "id": call.get("id"),
                        "name": call.get("name"),
                        "text": result["text"],
                        "is_error": result["is_error"],
                        "has_image": bool(result["image_png_base64"]),
                    },
                )
            results.append({"call": call, "result": result})
        self.history.append({"role": "user", "tool_results": results})

    def _close(self, calls, sentence):
        """Answer calls that will not run, so the history stays valid for every API."""
        if calls:
            results = [{"call": c, "result": _result(sentence, is_error=True)} for c in calls]
            self.history.append({"role": "user", "tool_results": results})

    def _run_tool(self, call):
        name = call.get("name")
        if call.get("bad_args"):
            return _result(
                "Not done: %s. Send the arguments again." % call["bad_args"], is_error=True
            )
        args = call.get("args") or {}
        problems = tools_core.validate(name, args)
        if problems:
            self.log("%s: arguments refused (%s)" % (name, "; ".join(problems)))
            return _result("Not done: " + "; ".join(problems) + ".", is_error=True)
        if self.call_tool is None:
            return _result("Not done: SciForge is not connected to this chat.", is_error=True)
        self.log("running %s" % name)
        try:
            answer = self.call_tool(name, args)
        except Exception as exc:
            self.log("%s failed: %s" % (name, exc))
            return _result("SciForge could not run %s: %s" % (name, exc), is_error=True)
        if not isinstance(answer, dict):
            return _result("SciForge gave no answer for %s." % name, is_error=True)
        text = answer.get("text")
        return _result(
            text if isinstance(text, str) else str(text or ""),
            answer.get("image_png_base64"),
            answer.get("is_error", False),
        )

    def reset(self):
        """Forget the conversation (not while send() runs)."""
        if not self._busy.locked():
            self.history = []
            self.usage = {"input_tokens": 0, "output_tokens": 0}
