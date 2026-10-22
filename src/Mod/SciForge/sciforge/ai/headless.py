# SPDX-License-Identifier: LGPL-2.1-or-later
"""SciForge without its window (docs/sciforge/dev/cadcraft-lessons.md idea 4): every AI tool
run in-process under FreeCAD's command-line mode, for the command line (sciforge/ai/cli.py,
tools/sciforge/sciforge-cli) and for the MCP server's --headless mode (sciforge_mcp.py).

The tools run through the same executor as in the app (sciforge/ai/executor.py), so they
build exactly what the AI bridge builds; what differs is the host: no person to ask, so a
file that exists is never replaced unless the host was made with allow_overwrite (the
command line's --force / --allow-overwrite); saving is a plain FreeCAD save (the app adds
its version history); the tools that need the window (screenshot, set_view...) answer that
they need it. Needs FreeCAD (freecadcmd / SciForgeCmd)."""

import json
import os
import sys

import FreeCAD as App

from .. import log, warn
from . import bridge_core, catalog, executor


class HeadlessHost(executor.Host):
    gui = False

    def __init__(self, allow_overwrite=False):
        executor.Host.__init__(self)
        self.allow_overwrite = bool(allow_overwrite)


def call(tool, args=None, host=None):
    """Run one tool -> a bridge_core result {text, image_png_base64, is_error}."""
    return executor.run(tool, args or {}, host or HeadlessHost())


class InProcessClient:
    """call_tool(name, args) for the MCP server: the tools run here, in this process."""

    def __init__(self, host=None):
        self.host = host or HeadlessHost()

    def call_tool(self, name, args):
        try:
            return call(name, args, self.host)
        except Exception as exc:  # (executor.run never raises; this is belt and braces)
            warn("headless %s: %s" % (name, exc))
            return bridge_core.error_result("SciForge could not run %s: %s" % (name, exc))


IMPORT_LEAD = "\nNot brought in, or changed:"


def open_file(path, host, notes=None):
    """Open a design or a STEP / IGES file (as File > Open does) as the active design.
    notes (a list): gets the lines saying what the file had that did not come in."""
    answer = call("open_design", {"path": os.path.abspath(path)}, host)
    if answer["is_error"]:
        raise RuntimeError(answer["text"])
    if notes is not None and IMPORT_LEAD in answer["text"]:
        notes.append(answer["text"][answer["text"].index(IMPORT_LEAD) :])
    return App.ActiveDocument


def info(path, host=None):
    """A JSON-ready summary of a file: the design (get_design), the timeline and every
    body's physical properties."""
    host = host or HeadlessHost()
    open_file(path, host)
    out = {"file": os.path.abspath(path)}
    for key, tool in (
        ("design", "get_design"),
        ("timeline", "get_timeline"),
        ("properties", "physical_properties"),
        ("parameters", "list_parameters"),
    ):
        answer = call(tool, {}, host)
        if answer["is_error"]:
            out[key] = {"error": answer["text"]}
            continue
        text = answer["text"]
        body = text[text.index("{") :] if "{" in text else text
        try:
            out[key] = json.loads(body)
        except ValueError:
            out[key] = text
    return out


FORMATS = {
    ".step": "step",
    ".stp": "step",
    ".igs": "iges",
    ".iges": "iges",
    ".stl": "stl",
    ".3mf": "3mf",
    ".obj": "obj",
    ".brep": "brep",
    ".brp": "brep",
    ".fcstd": "fcstd",
}


def convert(source, target, host=None):
    """Open source, write target (format by its extension). Returns the tool's answer: the
    file written, what it does not keep (export_report) and, for a STEP / IGES source, what
    did not come in from it."""
    host = host or HeadlessHost()
    ext = os.path.splitext(target)[1].lower()
    fmt = FORMATS.get(ext)
    if fmt is None:
        raise RuntimeError(
            "SciForge cannot write %s files (it writes %s)."
            % (ext or "these", ", ".join(sorted(set(FORMATS))))
        )
    notes = []
    open_file(source, host, notes)
    if fmt == "fcstd":
        answer = call("save_as", {"path": os.path.abspath(target)}, host)
    else:
        answer = call("export", {"format": fmt, "path": os.path.abspath(target)}, host)
    if notes and not answer["is_error"]:
        answer = dict(answer, text=answer["text"] + "".join(notes))
    return answer


def run_calls(calls, host=None, start=None, stop_on_error=True):
    """Run [(tool, args)] in order (start: a file opened first). Returns [(tool, args,
    answer)]; stops at the first error unless stop_on_error is False."""
    host = host or HeadlessHost()
    if start:
        open_file(start, host)
    done = []
    for tool, args in calls:
        answer = call(tool, args, host)
        done.append((tool, args, answer))
        log(
            "headless %s: %s"
            % (tool, answer["text"].splitlines()[0][:200] if answer["text"] else "")
        )
        if answer["is_error"] and stop_on_error:
            break
    return done


def take_stdout():
    """Command-line FreeCAD writes its banner and console messages to stdout, which belongs
    to our answers (MCP messages, JSON): the real stdout is kept for them and everything
    else that writes to file descriptor 1 goes to stderr. Returns a binary stream."""
    try:
        sys.stdout.flush()
    except Exception:
        pass
    fd = os.dup(1)
    os.dup2(2, 1)
    sys.stdout = sys.stderr
    return os.fdopen(fd, "wb", buffering=0)


def tool_names():
    return list(catalog.TOOL_NAMES)
