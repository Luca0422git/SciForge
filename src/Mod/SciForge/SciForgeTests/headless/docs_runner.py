# SPDX-License-Identifier: LGPL-2.1-or-later
"""Runs every example of SciForge's documentation for AI models in real FreeCAD without a
window, so no document shows a call that does not work (Luca, 2026-10-21: "accuracy is
everything"):

  * every block of tool calls ("sciforge-calls" fences, sciforge/ai/docs_core.py) in every
    document of the docs root: the recipes, the handbook, the selector cookbook...; each
    document is one session in a fresh SciForge (all designs closed), its blocks run in
    order, every call must succeed (or fail, with "expect": {"error": true}) and match its
    "expect" (texts it contains, JSON values, a picture's size);
  * the example of every tool shown on its reference page (SciForgeTests/docs/
    tool_examples.py): its setup, then the call; the answer must still be the one recorded
    in SciForgeTests/docs/tool_results.json (the same words, numbers within 1e-4).

    freecadcmd -c "from SciForgeTests.headless import docs_runner; docs_runner.main()"

SCIFORGE_DOCS_RECORD=1 records the tool examples' answers again instead of comparing (then
run tools/sciforge/make_ai_docs.py to rewrite the pages). SCIFORGE_DOCS_FILTER runs only
the documents / tools whose name contains that text. Writes docs-report.json / .md to
SCIFORGE_HEADLESS_OUT (default: FreeCAD's user data folder). tools/sciforge/run_tests.sh runs
it with --only headless and base. The GUI scenario ai_docs_gui does the same for the
examples that need the window (run_examples(gui=True)).
"""

import base64
import json
import os
import platform
import re
import shutil
import tempfile
import time
import traceback

SHOWN_TMP = "/home/me/sciforge"  # what a temporary folder is shown as on the pages
_NUMBER = re.compile(r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")
HERE = os.path.dirname(os.path.abspath(__file__))
DOCS_TESTS = os.path.join(os.path.dirname(HERE), "docs")
RESULTS = os.path.join(DOCS_TESTS, "tool_results.json")


# -- the session ----------------------------------------------------------------------------------
def reset():
    """A fresh SciForge: every design closed, the AI tools' memory of them dropped."""
    import FreeCAD as App

    from sciforge.ai import executor
    from sciforge.ai.actions import verify_actions

    for name in list(App.listDocuments()):
        try:
            App.closeDocument(name)
        except Exception:
            pass
    executor._BUILDERS.clear()
    executor.MODIFIED.clear()
    verify_actions._SNAPSHOTS.clear()
    verify_actions._LAST.clear()
    verify_actions._COUNTER["n"] = 0


def fill_tmp(value, folder):
    if isinstance(value, str):
        return value.replace("{tmp}", folder)
    if isinstance(value, dict):
        return {k: fill_tmp(v, folder) for k, v in value.items()}
    if isinstance(value, list):
        return [fill_tmp(v, folder) for v in value]
    return value


def shown(answer, folder):
    """An answer as the documentation shows it: the temporary folder as SHOWN_TMP, a
    picture as its size."""
    text = answer.get("text", "")
    for form in {folder, os.path.realpath(folder)}:
        text = text.replace(form, SHOWN_TMP)
    out = {"text": text, "is_error": bool(answer.get("is_error"))}
    if answer.get("image_png_base64"):
        from sciforge.ai import render_core

        size = render_core.png_info(base64.b64decode(answer["image_png_base64"]))
        out["image"] = list(size) if size else None
    return out


def json_of(text):
    start = text.find("{")
    if start < 0:
        return None
    try:
        return json.loads(text[start:])
    except ValueError:
        return None


def lookup(data, path):
    """data at a dotted path ("bodies.0.volume_mm3"; "#" is the length of a list)."""
    value = data
    for part in path.split("."):
        if part == "#":
            value = len(value)
        elif isinstance(value, list):
            value = value[int(part)]
        else:
            value = value[part]
    return value


def check_expect(expect, answer):
    """Problems (sentences) of an answer against a block call's "expect"."""
    problems = []
    expect = expect or {}
    want_error = bool(expect.get("error"))
    if answer["is_error"] != want_error:
        problems.append(
            ("should have failed: " if want_error else "failed: ") + answer["text"][:600]
        )
        return problems
    for text in expect.get("contains", []):
        if text not in answer["text"]:
            problems.append("the answer lacks %r: %s" % (text, answer["text"][:400]))
    for text in expect.get("not_contains", []):
        if text in answer["text"]:
            problems.append("the answer has %r: %s" % (text, answer["text"][:400]))
    if expect.get("json"):
        data = json_of(answer["text"])
        if data is None:
            problems.append("no JSON in the answer: %s" % answer["text"][:300])
        else:
            for path, want in expect["json"].items():
                try:
                    got = lookup(data, path)
                except (KeyError, IndexError, ValueError, TypeError):
                    problems.append("the answer has no %s" % path)
                    continue
                if isinstance(want, list) and len(want) == 2 and all(
                    isinstance(v, (int, float)) and not isinstance(v, bool) for v in want
                ) and not isinstance(got, list):
                    target, tol = want
                    if not isinstance(got, (int, float)) or abs(got - target) > tol:
                        problems.append("%s is %s, expected %s +- %s" % (path, got, target, tol))
                elif got != want:
                    problems.append("%s is %r, expected %r" % (path, got, want))
    if "image" in expect:
        if answer.get("image") != list(expect["image"]):
            problems.append("the picture is %s, expected %s" % (answer.get("image"), expect["image"]))
    return problems


def same_answer(recorded, now, rel=1e-4, absolute=1e-3):
    """None when two answers say the same (numbers within the tolerance), else the first
    difference in words."""
    if recorded.get("is_error") != now.get("is_error"):
        return "it %s now: %s" % ("fails" if now.get("is_error") else "works", now["text"][:300])
    if recorded.get("image") != now.get("image"):
        return "the picture is %s, was %s" % (now.get("image"), recorded.get("image"))
    a, b = recorded.get("text", ""), now.get("text", "")
    if _NUMBER.sub("#", a) != _NUMBER.sub("#", b):
        for i, (x, y) in enumerate(zip(a.splitlines(), b.splitlines())):
            if _NUMBER.sub("#", x) != _NUMBER.sub("#", y):
                return "line %d was %r, is now %r" % (i + 1, x[:200], y[:200])
        return "the answer has %d lines, was %d" % (len(b.splitlines()), len(a.splitlines()))
    for x, y in zip(_NUMBER.findall(a), _NUMBER.findall(b)):
        fx, fy = float(x), float(y)
        if abs(fx - fy) > max(absolute, rel * max(abs(fx), abs(fy))):
            return "the number %s is now %s" % (x, y)
    return None


def _first_line(answer):
    """An answer cut to its first line with the numbers masked: what stays the same for the
    documentation tools while the documents they search change."""
    text = (answer.get("text") or "").split("\n", 1)[0]
    return dict(answer, text=_NUMBER.sub("#", text))


class Session:
    def __init__(self, gui=False):
        self.folder = tempfile.mkdtemp(prefix="sciforge-docs-")
        self.gui = gui
        self.host = self._host()

    def _host(self):
        if self.gui:
            from sciforge.ai import bridge

            return bridge.GuiHost()
        from sciforge.ai import headless

        return headless.HeadlessHost(allow_overwrite=False)

    def call(self, tool, args):
        from sciforge.ai import executor

        try:
            answer = executor.run(tool, fill_tmp(args or {}, self.folder), self.host)
        except Exception as exc:  # executor.run never raises: this would be a bug
            answer = {
                "text": "raised: %s\n%s" % (exc, traceback.format_exc()),
                "is_error": True,
                "image_png_base64": None,
            }
        return shown(answer, self.folder)

    def close(self):
        shutil.rmtree(self.folder, ignore_errors=True)


# -- documents ------------------------------------------------------------------------------------
def run_documents(text_filter="", root=None):
    """Every document with tool-call blocks: [{"label", "status", "problems", "calls",
    "seconds"}]."""
    from sciforge.ai import docs_core

    results = []
    for rel, full in docs_core.doc_files(root):
        if not rel.endswith(".md") or (text_filter and text_filter not in rel):
            continue
        with open(full, encoding="utf-8") as handle:
            text = handle.read()
        try:
            blocks = docs_core.call_blocks(text)
        except ValueError as exc:
            results.append(_row("doc " + rel, ["%s" % exc], 0, 0.0))
            continue
        if not blocks:
            continue
        start = time.time()
        reset()
        session = Session()
        problems = []
        count = 0
        try:
            for line, calls in blocks:
                for call in calls:
                    count += 1
                    answer = session.call(call["tool"], call.get("args", {}))
                    if os.environ.get("SCIFORGE_DOCS_VERBOSE"):
                        print("[SciForge] docs call %s %s -> %s" % (
                            call["tool"], json.dumps(call.get("args", {}))[:200],
                            answer["text"][: int(os.environ["SCIFORGE_DOCS_VERBOSE"])]))
                    for problem in check_expect(call.get("expect"), answer):
                        problems.append("line %d, %s: %s" % (line, call["tool"], problem))
                    if problems and answer["is_error"] and not (call.get("expect") or {}).get(
                        "error"
                    ):
                        break  # the rest of the document builds on this call
                if problems:
                    break
        finally:
            session.close()
        results.append(_row("doc " + rel, problems, count, time.time() - start))
    return results


def _row(label, problems, calls, seconds):
    return {
        "label": label,
        "status": "fail" if problems else "pass",
        "problems": problems,
        "calls": calls,
        "seconds": round(seconds, 2),
    }


# -- the tool examples ----------------------------------------------------------------------------
def example_key(example, index_of_tool):
    return "%s#%d" % (example["tool"], index_of_tool)


def numbered(examples):
    """[(key, example)]: tool#1, tool#2... in the order of EXAMPLES."""
    seen = {}
    out = []
    for ex in examples:
        seen[ex["tool"]] = seen.get(ex["tool"], 0) + 1
        out.append((example_key(ex, seen[ex["tool"]]), ex))
    return out


def spec_of(example, setups):
    """What a recorded answer was recorded for (to see that it is still current)."""
    return {
        "setup": example["setup"],
        "setup_calls": setups[example["setup"]] + example.get("setup_extra", []),
        "args": example["args"],
    }


def load_results(path=RESULTS):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}


def run_examples(record=False, text_filter="", gui=False, path=RESULTS):
    """The tool examples (only those that need the window when gui, only the others
    otherwise). Returns the report rows; with record, rewrites the recorded answers."""
    from SciForgeTests.docs import tool_examples

    recorded = load_results(path)
    rows = []
    changed = False
    for key, ex in numbered(tool_examples.EXAMPLES):
        if bool(ex.get("gui")) != bool(gui):
            continue
        if text_filter and text_filter not in key:
            continue
        start = time.time()
        reset()
        session = Session(gui=gui)
        problems = []
        spec = spec_of(ex, tool_examples.SETUPS)
        try:
            for call in spec["setup_calls"]:
                answer = session.call(call["tool"], call.get("args", {}))
                if answer["is_error"]:
                    problems.append("the setup call %s failed: %s" % (call["tool"], answer["text"]))
                    break
            if not problems:
                answer = session.call(ex["tool"], ex["args"])
                if answer["is_error"] and not ex.get("error"):
                    problems.append("failed: %s" % answer["text"][:600])
                if record:
                    if not problems:
                        recorded[key] = dict(spec, note=ex.get("note", ""), answer=answer)
                        changed = True
                else:
                    old = recorded.get(key)
                    if old is None:
                        problems.append("no recorded answer: record with SCIFORGE_DOCS_RECORD=1")
                    elif {k: old.get(k) for k in spec} != json.loads(json.dumps(spec)):
                        problems.append("recorded for other arguments: record again")
                    else:
                        if ex.get("volatile"):  # (answers about the documentation itself)
                            difference = same_answer(_first_line(old["answer"]), _first_line(answer))
                        else:
                            difference = same_answer(old["answer"], answer)
                        if difference:
                            problems.append(
                                "the answer differs from its reference page (%s): record "
                                "again with SCIFORGE_DOCS_RECORD=1, then run "
                                "tools/sciforge/make_ai_docs.py" % difference
                            )
        finally:
            session.close()
        rows.append(_row("example " + key, problems, len(spec["setup_calls"]) + 1, time.time() - start))
    if record and changed:
        keys = [k for k, _ex in numbered(tool_examples.EXAMPLES)]
        ordered = {k: recorded[k] for k in keys if k in recorded}
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(ordered, handle, indent=1, ensure_ascii=False, sort_keys=False)
            handle.write("\n")
    return rows


# -- the report -----------------------------------------------------------------------------------
def markdown(report):
    lines = [
        "# Documentation examples report",
        "",
        "FreeCAD %s, %s. %d items: %s"
        % (
            report["freecad"],
            report["platform"],
            len(report["results"]),
            "PASS" if report["passed"] else "FAIL",
        ),
        "",
        "| Item | Result | Calls | Time (s) | Problems |",
        "|---|---|---|---|---|",
    ]
    for r in report["results"]:
        lines.append(
            "| %s | %s | %d | %.2f | %s |"
            % (
                r["label"],
                r["status"].upper(),
                r["calls"],
                r["seconds"],
                "; ".join(r["problems"]).replace("|", "/").replace("\n", " ")[:600],
            )
        )
    return "\n".join(lines) + "\n"


def main():
    import FreeCAD as App

    out_dir = os.environ.get("SCIFORGE_HEADLESS_OUT") or App.getUserAppDataDir()
    os.makedirs(out_dir, exist_ok=True)
    record = bool(os.environ.get("SCIFORGE_DOCS_RECORD"))
    text_filter = os.environ.get("SCIFORGE_DOCS_FILTER", "")
    report = {
        "freecad": ".".join(App.Version()[:3]),
        "platform": platform.platform(),
        "record": record,
        "results": [],
    }
    try:
        report["results"] += run_examples(record, text_filter)
        report["results"] += run_documents(text_filter)
    except Exception as exc:
        report["results"].append(_row("session", ["%s\n%s" % (exc, traceback.format_exc())], 0, 0))
    reset()
    report["passed"] = bool(report["results"]) and all(
        r["status"] == "pass" for r in report["results"]
    )
    for r in report["results"]:
        App.Console.PrintMessage(
            "[SciForge] docs %s %s %s\n"
            % (r["status"].upper(), r["label"], "; ".join(r["problems"])[:900])
        )
    with open(os.path.join(out_dir, "docs-report.json"), "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    with open(os.path.join(out_dir, "docs-report.md"), "w", encoding="utf-8") as handle:
        handle.write(markdown(report))
    App.Console.PrintMessage(
        "[SciForge] docs summary: %d items, %d failed, %d calls%s\n"
        % (
            len(report["results"]),
            len([r for r in report["results"] if r["status"] != "pass"]),
            sum(r["calls"] for r in report["results"]),
            " (recorded)" if record else "",
        )
    )
    return report
