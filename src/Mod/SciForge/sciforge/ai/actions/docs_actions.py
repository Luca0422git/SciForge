# SPDX-License-Identifier: LGPL-2.1-or-later
"""The documentation tools (catalog/docs_tools.py: docs_search, docs_read, examples_search):
they read SciForge's documentation for AI models through sciforge/ai/docs_core.py, the same
code the MCP server answers them with when SciForge is closed."""

from .. import bridge_core, docs_core
from . import action


def _answer(tool, args):
    text, is_error = docs_core.tool_answer(tool, args)
    return bridge_core.error_result(text) if is_error else bridge_core.result(text)


@action("docs_search")
def docs_search(ctx, args):
    return _answer("docs_search", args)


@action("docs_read")
def docs_read(ctx, args):
    return _answer("docs_read", args)


@action("examples_search")
def examples_search(ctx, args):
    return _answer("examples_search", args)
