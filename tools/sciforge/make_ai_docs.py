#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
"""Writes src/Mod/SciForge/docs/ai/tools.md, the tool reference for AI models, from the tool
catalogue (src/Mod/SciForge/sciforge/ai/tool_docs.py does the writing). Run it after adding
or changing a tool; the unit test test_ai_docs_contract.py fails until you do.

    python3 tools/sciforge/make_ai_docs.py [--check]

--check: write nothing, exit 1 when the file is out of date. Plain Python, no FreeCAD.
"""

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODULE = os.path.join(REPO, "src", "Mod", "SciForge")
sys.path.insert(0, MODULE)

from sciforge.ai import tool_docs  # noqa: E402

TARGET = os.path.join(MODULE, "docs", "ai", tool_docs.FILE)


def main(argv):
    text = tool_docs.render()
    try:
        with open(TARGET, encoding="utf-8") as handle:
            old = handle.read()
    except OSError:
        old = None
    if "--check" in argv:
        if old != text:
            print("[SciForge] %s is out of date: run tools/sciforge/make_ai_docs.py" % TARGET)
            return 1
        print("[SciForge] %s is up to date" % TARGET)
        return 0
    if old == text:
        print("[SciForge] %s is up to date" % TARGET)
        return 0
    os.makedirs(os.path.dirname(TARGET), exist_ok=True)
    with open(TARGET, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    print("[SciForge] wrote %s" % TARGET)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
