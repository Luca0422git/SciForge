#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
"""Writes the generated part of SciForge's documentation for AI models
(src/Mod/SciForge/docs/ai/: tools.md, reference/<tool>.md, examples/golden-models.md and the
copy of docs/sciforge under user/), from the tool catalogue, the recorded tool examples
(SciForgeTests/docs/tool_results.json), the golden models and the person's documentation
(src/Mod/SciForge/sciforge/ai/tool_docs.py does the writing). Run it after changing a tool,
a recorded example, a golden model or a page under docs/sciforge; the unit test
test_ai_docs_contract.py fails until you do. Files left in reference/ or user/ that are no
longer generated are deleted.

    python3 tools/sciforge/make_ai_docs.py [--check]
    python3 tools/sciforge/make_ai_docs.py --export FILE [--full]

--check: write nothing, exit 1 when a file is out of date (or stale). --export: write every
document into one Markdown file for AI apps that load files (--full adds the user/ copies).
Plain Python, no FreeCAD.
"""

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODULE = os.path.join(REPO, "src", "Mod", "SciForge")
sys.path.insert(0, MODULE)

from sciforge.ai import docs_core, tool_docs  # noqa: E402

DOCS = os.path.join(MODULE, "docs", "ai")


def plan():
    """(files to write {path: text}, stale paths to delete)."""
    files = tool_docs.generated(REPO)
    stale = []
    for folder in tool_docs.generated_folders():
        here = os.path.join(DOCS, folder)
        for root, _dirs, names in os.walk(here) if os.path.isdir(here) else []:
            for name in names:
                rel = os.path.relpath(os.path.join(root, name), DOCS).replace(os.sep, "/")
                if rel not in files:
                    stale.append(rel)
    return files, sorted(stale)


def _read(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read()
    except OSError:
        return None


def main(argv):
    if "--export" in argv:
        target = argv[argv.index("--export") + 1]
        text = docs_core.export_text(full="--full" in argv, lib=docs_core.library(DOCS))
        with open(target, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        print("[SciForge] wrote %s (%d characters)" % (target, len(text)))
        return 0
    files, stale = plan()
    old = {rel: _read(os.path.join(DOCS, rel)) for rel in files}
    changed = sorted(rel for rel, text in files.items() if old[rel] != text)
    if "--check" in argv:
        if changed or stale:
            for rel in changed:
                print("[SciForge] out of date: docs/ai/%s" % rel)
            for rel in stale:
                print("[SciForge] stale (no longer generated): docs/ai/%s" % rel)
            print("[SciForge] run tools/sciforge/make_ai_docs.py")
            return 1
        print("[SciForge] the %d generated documents are up to date" % len(files))
        return 0
    for rel in changed:
        path = os.path.join(DOCS, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(files[rel])
        print("[SciForge] wrote docs/ai/%s" % rel)
    for rel in stale:
        os.remove(os.path.join(DOCS, rel))
        print("[SciForge] deleted docs/ai/%s" % rel)
    print(
        "[SciForge] %d generated documents: %d written, %d deleted"
        % (len(files), len(changed), len(stale))
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
