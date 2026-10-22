# SPDX-License-Identifier: LGPL-2.1-or-later
"""SciForge's documentation for AI models inside the window (sciforge/ai/docs_core.py,
docs/ai/):

Path 1, the reference examples that need the window (screenshot, set_view, get_view: the
  "gui" examples of SciForgeTests/docs/tool_examples.py) run with the window's host and
  answer what their reference pages show (SCIFORGE_DOCS_RECORD=1 records them again).
Path 2, the documentation tools through the bridge's own entry, as SciForge's chat panel
  calls them: docs_search finds the troubleshooting page for "cut does nothing", docs_read
  reads one section of the handbook, examples_search finds the flange recipe; the chat's
  system prompt carries the short index of the documents (not the documents).
Path 3, + Add an AI > Save AI handbook... (a real click) writes every document into one
  Markdown file and shows where; the folder is opened (a stand-in here).
"""

import os

import FreeCAD as App
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import versions_input as vi
from SciForgeTests.gui import widget_input as wi

s = {}


def call(tool, args):
    from sciforge.ai import bridge

    try:
        answer = bridge.call(tool, args, from_chat=True)
    except Exception as exc:  # (the bridge must never raise: that is a failure too)
        answer = {"text": "raised %s" % exc, "is_error": True, "image_png_base64": None}
    return answer


# -- Path 1 -------------------------------------------------------------------------------------
def gui_examples():
    from SciForgeTests.headless import docs_runner

    record = bool(os.environ.get("SCIFORGE_DOCS_RECORD"))
    rows = docs_runner.run_examples(record=record, gui=True)
    names = [r["label"] for r in rows]
    h.check(
        "the reference examples that need the window ran",
        len(rows) >= 3 and any("screenshot" in n for n in names),
        names,
    )
    for row in rows:
        h.check(
            "%s answers what its page shows" % row["label"],
            row["status"] == "pass",
            "; ".join(row["problems"])[:600],
        )
    if App.ActiveDocument is None:
        App.newDocument("Scratch")


# -- Path 2 -------------------------------------------------------------------------------------
def docs_tools():
    from sciforge.ai import chat_core

    a = call("docs_search", {"query": "cut does nothing", "limit": 3})
    h.check(
        "docs_search finds the troubleshooting page",
        not a["is_error"] and "troubleshooting.md" in a["text"],
        a["text"][:300],
    )
    a = call("docs_read", {"path": "handbook.md", "section": "units-and-coordinates"})
    h.check(
        "docs_read reads one section",
        not a["is_error"]
        and "## Units and coordinates" in a["text"]
        and "## Fusion's ideas" not in a["text"],
        a["text"][:300],
    )
    a = call("examples_search", {"query": "flange bolt circle", "limit": 3})
    h.check(
        "examples_search finds the flange recipe",
        not a["is_error"] and "flange-bolt-pattern" in a["text"],
        a["text"][:300],
    )
    a = call("docs_read", {"path": "nothing-here.md"})
    h.check("docs_read says when a document is not there", a["is_error"], a["text"][:200])
    prompt = chat_core.SYSTEM_PROMPT
    h.check(
        "the chat's system prompt has the index of the documents, not the documents",
        "docs_search" in prompt and "recipes/<name>.md" in prompt and len(prompt) < 8000,
        len(prompt),
    )


# -- Path 3 -------------------------------------------------------------------------------------
def open_add_ai():
    from sciforge import ai_ui, home_ui

    ai_ui.OPEN_FILE = lambda path: s.setdefault("opened", path)
    home_ui.show()
    wi.click(home_ui.view().add_ai_button)


def save_handbook():
    d = vi.dialog("SciForgeAddAIDialog")
    h.check("+ Add an AI opened its window", d is not None)
    if d is None:
        return
    button = vi.child(d, "SciForgeAddAIHandbook")
    h.check("it has Save AI handbook...", button is not None and button.isVisible())
    if button is not None:
        wi.click(button)


def handbook_saved():
    from sciforge import ai_ui
    from sciforge.ai import docs_core

    path = os.path.join(App.getUserAppDataDir(), "SciForge", "ai", ai_ui.HANDBOOK_NAME)
    text = ""
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
    h.check(
        "the handbook file has every document",
        text.startswith("# " + docs_core.EXPORT_TITLE)
        and "File: handbook.md" in text
        and "File: reference/extrude.md" in text
        and "File: recipes/bracket.md" in text,
        (path, len(text)),
    )
    d = vi.dialog("SciForgeAddAIDialog")
    shown = vi.child(d, "SciForgeAddAIText").toPlainText() if d is not None else ""
    h.check("the dialog says where it is", path in shown, shown[:300])
    h.check("its folder was opened", s.get("opened") == os.path.dirname(path), s.get("opened"))
    if d is not None:
        vi.cancel_dialog(d)
    ai_ui.OPEN_FILE = None
    h.check("no pop-up left", not h.popups(), h.popups())


h.run("ai_docs_gui", [gui_examples, docs_tools, open_add_ai, save_handbook, handbook_saved])
