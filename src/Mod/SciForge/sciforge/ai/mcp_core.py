# SPDX-License-Identifier: LGPL-2.1-or-later
"""The Model Context Protocol (MCP) messages SciForge answers, without any sockets or
files, so it can be unit tested (docs/sciforge/dev/briefs/home-cloud-ai.md, section 4.4).

An AI app (Claude Desktop, Gemini CLI, ...) starts sciforge_mcp.py and talks JSON-RPC 2.0
to it over stdin / stdout. The stdio transport sends one JSON-RPC message per line: UTF-8
JSON with no newline inside it; anything else the server wants to say goes to stderr.
SciForge offers tools, resources and prompts: initialize, ping, tools/list and tools/call
(with text and PNG image results), resources/list, resources/templates/list and
resources/read (the open design, the tool catalogue, the help topics and the documents for
AI models: mcp_resources.py), prompts/list and prompts/get (workflow templates). The tools
come from the catalogue (sciforge/ai/catalog). Arguments that break a tool's rules come
back as a tool result with isError and plain sentences (MCP 2025-11-25: input validation
errors are tool execution errors, so the model can correct itself); an unknown tool or
params that are not an object are protocol errors (-32602).

Checked against the MCP specification's text on GitHub
(modelcontextprotocol/modelcontextprotocol, docs/specification/2025-06-18/basic/transports
.mdx and lifecycle.mdx, and schema/2025-11-25/schema.ts) in October 2026:
  * version negotiation: answer the client's version when we support it, else our newest;
  * 2025-06-18 removed JSON-RPC batching, and 2025-11-25 has no batch type either, so a
    JSON array is refused with "Invalid Request";
  * tools carry a "title" (2025-06-18); older clients ignore fields they do not know.
The tools part did not change between the versions below, so one answer fits them all.
"""

import json

from . import catalog, mcp_resources, tools_core

PROTOCOL_VERSIONS = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")
LATEST = PROTOCOL_VERSIONS[0]

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

# What every AI app reads first (MCP "instructions"): what SciForge is, the workflow and the
# shared rules the tools' descriptions refer to (selectors, picks, sketch planes, curves). From
# the catalogue, like the tools.
INSTRUCTIONS = catalog.INSTRUCTIONS


def error_response(request_id, code, message):
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _result(request_id, result):
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def parse_line(line):
    """One line from stdin -> (message, None), (None, error response) or (None, None) for a
    blank line. Batches (JSON arrays) get an error: MCP does not have them any more."""
    if isinstance(line, bytes):
        try:
            line = line.decode("utf-8")
        except UnicodeDecodeError:
            return None, error_response(None, PARSE_ERROR, "Parse error: the line is not UTF-8")
    text = line.strip().lstrip("﻿")
    if not text:
        return None, None
    try:
        message = json.loads(text)
    except ValueError as exc:
        return None, error_response(None, PARSE_ERROR, "Parse error: %s" % exc)
    if isinstance(message, list):
        return None, error_response(
            None, INVALID_REQUEST, "Invalid Request: JSON-RPC batches are not supported by MCP"
        )
    if not isinstance(message, dict):
        return None, error_response(None, INVALID_REQUEST, "Invalid Request: not a JSON object")
    return message, None


def encode(message):
    """A message as one line of UTF-8 JSON ending in a newline (json escapes the newlines
    inside strings, so the line never breaks)."""
    return (json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def negotiate(client_version):
    return client_version if client_version in PROTOCOL_VERSIONS else LATEST


def tool_result(text, image_png_base64=None, is_error=False):
    """MCP CallToolResult from the bridge's answer."""
    content = [{"type": "text", "text": text if isinstance(text, str) else str(text)}]
    if image_png_base64:
        content.append({"type": "image", "data": image_png_base64, "mimeType": "image/png"})
    return {"content": content, "isError": bool(is_error)}


def _valid_id(value):
    return isinstance(value, (str, int)) and not isinstance(value, bool)


def handle(message, call_tool, version="0", log=None):
    """Answer one JSON-RPC message (a dict). Returns the response dict, or None when no
    answer is due (notifications, and responses the client sends us).

    call_tool(name, args) -> {"text": str, "image_png_base64": str or None, "is_error": bool}
    version: SciForge's version, for serverInfo. log: optional callable(str) for problems.
    Never raises."""
    request_id = message.get("id") if isinstance(message, dict) else None
    try:
        return _handle(message, call_tool, version, log)
    except Exception as exc:  # never let a bad message stop the server
        if log:
            log("[SciForge] MCP: could not answer a message: %s" % exc)
        if isinstance(message, dict) and "id" in message and _valid_id(request_id):
            return error_response(request_id, INTERNAL_ERROR, "Internal error: %s" % exc)
        return None


def _handle(message, call_tool, version, log):
    if not isinstance(message, dict):
        return error_response(None, INVALID_REQUEST, "Invalid Request: not a JSON object")
    method = message.get("method")
    is_notification = "id" not in message
    if method is None:
        if is_notification or "result" in message or "error" in message:
            return None  # a response to something we never ask: ignore it
        return error_response(message.get("id"), INVALID_REQUEST, "Invalid Request: no method")
    if is_notification:
        return None  # notifications/initialized, notifications/cancelled, ...: no reply
    request_id = message["id"]
    if not _valid_id(request_id) or message.get("jsonrpc") != "2.0" or not isinstance(method, str):
        return error_response(
            request_id if _valid_id(request_id) else None,
            INVALID_REQUEST,
            'Invalid Request: needs jsonrpc "2.0", a string or number id and a method',
        )
    params = message.get("params", {})
    if params is None:
        params = {}
    if not isinstance(params, dict):
        return error_response(
            request_id, INVALID_PARAMS, "Invalid params: params must be an object"
        )

    if method == "initialize":
        client_version = params.get("protocolVersion")
        if not isinstance(client_version, str):
            return error_response(
                request_id, INVALID_PARAMS, "Invalid params: protocolVersion is missing"
            )
        return _result(
            request_id,
            {
                "protocolVersion": negotiate(client_version),
                "capabilities": {
                    "tools": {"listChanged": False},
                    "resources": {"subscribe": False, "listChanged": False},
                    "prompts": {"listChanged": False},
                },
                "serverInfo": {"name": "sciforge", "title": "SciForge", "version": str(version)},
                "instructions": INSTRUCTIONS,
            },
        )
    if method == "ping":
        return _result(request_id, {})
    if method == "tools/list":
        return _result(request_id, {"tools": tools_core.mcp_tools()})
    if method == "tools/call":
        return _call(request_id, params, call_tool, log)
    if method in ("resources/list", "resources/templates/list", "resources/read"):
        return _resources(request_id, method, params, call_tool)
    if method in ("prompts/list", "prompts/get"):
        return _prompts(request_id, method, params)
    return error_response(request_id, METHOD_NOT_FOUND, "Method not found: %s" % method)


def _call(request_id, params, call_tool, log):
    name = params.get("name")
    args = params.get("arguments", {})
    if args is None:
        args = {}
    if not isinstance(name, str) or not isinstance(args, dict):
        return error_response(
            request_id, INVALID_PARAMS, "Invalid params: tools/call needs a name and arguments"
        )
    if tools_core.tool(name) is None:
        return error_response(request_id, INVALID_PARAMS, "Unknown tool: %s" % name)
    problems = tools_core.validate(name, args)
    if problems:
        text = "The %s arguments are not right: %s." % (name, "; ".join(problems))
        return _result(request_id, tool_result(text, is_error=True))
    try:
        answer = call_tool(name, args)
    except Exception as exc:
        if log:
            log("[SciForge] MCP: %s failed: %s" % (name, exc))
        return _result(
            request_id, tool_result("SciForge could not run %s: %s" % (name, exc), is_error=True)
        )
    if not isinstance(answer, dict):
        return _result(
            request_id, tool_result("SciForge gave no answer for %s." % name, is_error=True)
        )
    return _result(
        request_id,
        tool_result(
            answer.get("text", ""), answer.get("image_png_base64"), answer.get("is_error", False)
        ),
    )


def _resources(request_id, method, params, call_tool):
    """resources/list (everything at once: no cursor), resources/templates/list and
    resources/read; an unknown URI is error -32002 (MCP's "Resource not found")."""
    if method == "resources/list":
        return _result(request_id, {"resources": mcp_resources.resources()})
    if method == "resources/templates/list":
        return _result(request_id, {"resourceTemplates": mcp_resources.templates()})
    uri = params.get("uri")
    if not isinstance(uri, str) or not uri:
        return error_response(
            request_id, INVALID_PARAMS, "Invalid params: resources/read needs a uri"
        )
    try:
        contents = mcp_resources.read(uri, call_tool)
    except mcp_resources.ResourceError as exc:
        answer = error_response(request_id, exc.code, str(exc))
        if exc.data is not None:
            answer["error"]["data"] = exc.data
        return answer
    return _result(request_id, {"contents": contents})


def _prompts(request_id, method, params):
    if method == "prompts/list":
        return _result(request_id, {"prompts": mcp_resources.prompts()})
    name = params.get("name")
    if not isinstance(name, str):
        return error_response(
            request_id, INVALID_PARAMS, "Invalid params: prompts/get needs a name"
        )
    try:
        return _result(request_id, mcp_resources.get_prompt(name, params.get("arguments")))
    except mcp_resources.ResourceError as exc:
        return error_response(request_id, exc.code, str(exc))
