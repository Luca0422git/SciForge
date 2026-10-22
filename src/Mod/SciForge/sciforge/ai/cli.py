# SPDX-License-Identifier: LGPL-2.1-or-later
"""SciForge on the command line (docs/sciforge/dev/cadcraft-lessons.md idea 4): open,
convert and script designs without the window, with the same AI tools the app offers.

    sciforge-cli info FILE                  a JSON summary (bodies, timeline, parameters)
    sciforge-cli convert IN OUT [--force]   e.g. part.FCStd -> part.step / .stl / .3mf
                                            (the answer lists what OUT does not keep)
    sciforge-cli run [FILE] --tool 'NAME {JSON}' ... [--save OUT.FCStd] [--force]
                                            run tools in order, then save
    sciforge-cli check FILE                 is the design sound (check_design as JSON;
                                            exit 1 when it has problems)
    sciforge-cli render FILE OUT.png [--view top] [--size 800x600]
                                            a picture of the design, drawn without the
                                            window
    sciforge-cli tools [--names]            the tool catalogue as JSON
    sciforge-cli docs search WORDS | read PATH [--page N] | examples WORDS
                    | export FILE [--full | --compact]
                                            SciForge's documentation for AI models: search,
                                            read, find examples, or write it all into one
                                            Markdown file (for AI apps that load files)
    sciforge-cli mcp [--headless]           the MCP server (default: forwards to the
                                            running SciForge; --headless: runs the tools
                                            here)

tools/sciforge/sciforge-cli finds FreeCAD's command-line program and runs this file with it
(`freecadcmd cli.py`, the arguments in a file named by SCIFORGE_CLI_ARGFILE, because FreeCAD
reads options itself); `tools` and `docs` also run with any Python. Output that is not ours
(FreeCAD's banner, console messages) goes to stderr, so stdout holds only the answer. Exit
status: 0 done, 1 a tool or step failed, 2 bad command line.
"""

import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))  # <Mod>/SciForge, which holds sciforge/
if sys.path and os.path.abspath(sys.path[0] or os.curdir) == _HERE:
    sys.path.pop(0)  # the script's own folder: its module names must not shadow others
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


ENV_ARGFILE = "SCIFORGE_CLI_ARGFILE"  # the wrapper's arguments, NUL-separated


def _script_args(argv):
    """The arguments meant for us: from the wrapper's file (FreeCAD's command-line program
    parses options itself, so they cannot follow the script there), else after this file in
    argv, without --pass."""
    path = os.environ.get(ENV_ARGFILE)
    if path:
        try:
            with open(path, "rb") as handle:
                data = handle.read().decode("utf-8")
            return [a for a in data.split("\0") if a != ""] if data else []
        except OSError:
            pass
    args = list(argv)
    for i, item in enumerate(args):
        if os.path.abspath(item) == os.path.abspath(__file__):
            args = args[i + 1 :]
            break
    else:
        args = args[1:]
    return [a for a in args if a != "--pass"]


def _parser():
    parser = argparse.ArgumentParser(
        prog="sciforge-cli",
        description="SciForge without its window: inspect, convert and script designs with "
        "SciForge's AI tools.",
    )
    sub = parser.add_subparsers(dest="command")
    p = sub.add_parser("info", help="a JSON summary of a design or STEP / IGES file")
    p.add_argument("file")
    p = sub.add_parser(
        "convert",
        help="open IN, write OUT (format from its extension); says what OUT does not keep",
    )
    p.add_argument("source")
    p.add_argument("target")
    p.add_argument("--force", action="store_true", help="replace OUT if it exists")
    p = sub.add_parser("run", help="run tools in order (optionally on FILE), then save")
    p.add_argument("file", nargs="?", help="a design or STEP / IGES file to start from")
    p.add_argument(
        "--tool",
        action="append",
        default=[],
        metavar="'NAME {JSON}'",
        help='a tool call, e.g. --tool \'extrude {"profile": "Sketch1", '
        '"distance": 10}\' (repeat it)',
    )
    p.add_argument("--tools-file", help='a JSON file: [{"tool": name, "arguments": {...}}]')
    p.add_argument("--save", help="save the design here (.FCStd) at the end")
    p.add_argument("--force", action="store_true", help="files may be replaced")
    p.add_argument("--keep-going", action="store_true", help="go on after a failed tool")
    p.add_argument("--json", action="store_true", help="answers as JSON")
    p = sub.add_parser("check", help="check a design: valid solids, failed steps, overlaps")
    p.add_argument("file")
    p.add_argument("--no-interference", action="store_true", help="skip the overlap check")
    p = sub.add_parser("render", help="a PNG picture of a design (no window needed)")
    p.add_argument("file")
    p.add_argument("target", help="the .png to write")
    p.add_argument(
        "--view", default="iso", choices=("iso", "front", "back", "top", "bottom", "left", "right")
    )
    p.add_argument("--size", default="800x600", help="WIDTHxHEIGHT in pixels (default 800x600)")
    p.add_argument("--force", action="store_true", help="replace OUT.png if it exists")
    p = sub.add_parser("tools", help="the tool catalogue as JSON")
    p.add_argument("--names", action="store_true", help="only the names")
    p.add_argument("--category", help="only this category")
    p = sub.add_parser("docs", help="search, read or export the documentation for AI models")
    p.add_argument("action", choices=("search", "read", "examples", "export"))
    p.add_argument("text", nargs="+", help="the words, the document's path, or the file")
    p.add_argument("--page", type=int, default=1, help="read: which page")
    p.add_argument("--full", action="store_true", help="export: add SciForge's user docs")
    p.add_argument(
        "--compact", action="store_true", help="export: leave out the tool reference pages"
    )
    p.add_argument("--force", action="store_true", help="export: replace FILE if it exists")
    p = sub.add_parser("mcp", help="the MCP server over stdin / stdout")
    p.add_argument("--headless", action="store_true", help="run the tools in this process")
    p.add_argument(
        "--bridge", action="store_true", help="forward to the running SciForge (the default)"
    )
    p.add_argument("--bridge-file", help="path of SciForge's bridge.json")
    p.add_argument(
        "--allow-overwrite", action="store_true", help="headless: tools may replace existing files"
    )
    return parser


def parse_tool(text):
    """'extrude {"profile": "Sketch1", "distance": 10}' -> ("extrude", {...}). The JSON may
    be left out for a tool without arguments. ValueError with a plain reason otherwise."""
    text = (text or "").strip()
    if not text:
        raise ValueError("an empty --tool")
    name, _sep, rest = text.partition(" ")
    rest = rest.strip()
    if not rest:
        return name, {}
    try:
        args = json.loads(rest)
    except ValueError as exc:
        raise ValueError("the arguments of %s are not JSON: %s" % (name, exc))
    if not isinstance(args, dict):
        raise ValueError("the arguments of %s must be a JSON object" % name)
    return name, args


def read_calls(options):
    """The tool calls of `run`: --tool in order, then --tools-file's. ValueError (or
    OSError: the file cannot be read) with a plain reason for a bad one (exit status 2)."""
    calls = [parse_tool(t) for t in options.tool]
    if options.tools_file:
        with open(options.tools_file, encoding="utf-8") as handle:
            try:
                items = json.load(handle)
            except ValueError as exc:
                raise ValueError("%s is not JSON: %s" % (options.tools_file, exc))
        if not isinstance(items, list):
            raise ValueError(
                '%s must hold a list: [{"tool": name, "arguments": {...}}]' % options.tools_file
            )
        for i, item in enumerate(items, start=1):
            if not isinstance(item, dict) or not isinstance(item.get("tool"), str):
                raise ValueError('item %d of %s has no "tool" name' % (i, options.tools_file))
            args = item.get("arguments", {})
            if not isinstance(args, dict):
                raise ValueError(
                    'the "arguments" of item %d of %s must be a JSON object'
                    % (i, options.tools_file)
                )
            calls.append((item["tool"], args))
    return calls


def _tools(options, out):
    from sciforge.ai import catalog

    if options.names:
        names = [
            t["name"]
            for t in catalog.TOOLS
            if not options.category or t["category"] == options.category
        ]
        out.write(("\n".join(names) + "\n").encode("utf-8"))
        return 0
    data = catalog.catalogue()
    if options.category:
        data["tools"] = [t for t in data["tools"] if t["category"] == options.category]
    out.write((json.dumps(data, indent=1, ensure_ascii=False) + "\n").encode("utf-8"))
    return 0


def _docs(options, out):
    """sciforge-cli docs ...: the documentation tools (docs_core.py), no FreeCAD needed."""
    from sciforge.ai import docs_core

    def say(text):
        out.write((text.rstrip("\n") + "\n").encode("utf-8"))

    words = " ".join(options.text)
    if options.action == "export":
        target = os.path.abspath(words)
        if os.path.exists(target) and not options.force:
            sys.stderr.write("[SciForge] %s already exists: add --force to replace it\n" % target)
            return 1
        text = docs_core.export_text(full=options.full, compact=options.compact)
        with open(target, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        say("Wrote %s (%d characters, %d documents)." % (target, len(text), text.count("\nFile: ")))
        return 0
    if options.action == "search":
        text, failed = docs_core.tool_answer("docs_search", {"query": words})
    elif options.action == "read":
        text, failed = docs_core.tool_answer("docs_read", {"path": words, "page": options.page})
    else:
        text, failed = docs_core.tool_answer("examples_search", {"query": words})
    say(text)
    return 1 if failed else 0


def parse_size(text):
    """'800x600' -> (800, 600); ValueError with a plain reason otherwise."""
    parts = (text or "").lower().split("x")
    if len(parts) != 2 or not all(p.strip().isdigit() for p in parts):
        raise ValueError("--size must be WIDTHxHEIGHT, e.g. 800x600")
    width, height = int(parts[0]), int(parts[1])
    if not (64 <= width <= 2048 and 64 <= height <= 2048):
        raise ValueError("--size must be 64 to 2048 pixels each way")
    return width, height


def _render(options, host, say):
    import base64

    from sciforge.ai import headless

    width, height = parse_size(options.size)
    target = os.path.abspath(options.target)
    if os.path.exists(target) and not options.force:
        raise ValueError("%s already exists: add --force to replace it" % target)
    headless.open_file(options.file, host)
    args = {"view": options.view, "width": width, "height": height, "renderer": "software"}
    answer = headless.call("render", args, host)
    if answer["is_error"] or not answer["image_png_base64"]:
        say(answer["text"])
        return 1
    with open(target, "wb") as handle:
        handle.write(base64.b64decode(answer["image_png_base64"]))
    say("%s Wrote %s." % (answer["text"], target))
    return 0


def _need_freecad():
    try:
        import FreeCAD  # noqa: F401
    except ImportError:
        sys.stderr.write(
            "[SciForge] this command needs FreeCAD: run it with tools/sciforge/sciforge-cli "
            "(or freecadcmd %s --pass ...)\n" % __file__
        )
        return False
    return True


def main(argv=None, out=None):
    argv = _script_args(sys.argv if argv is None else argv)
    options = _parser().parse_args(argv)
    if options.command is None:
        _parser().print_help(sys.stderr)
        return 2
    if options.command == "tools":
        return _tools(options, out or getattr(sys.stdout, "buffer", sys.stdout))
    if options.command == "docs":
        return _docs(options, out or getattr(sys.stdout, "buffer", sys.stdout))
    if options.command == "mcp":
        from sciforge.ai import sciforge_mcp

        args = []
        if options.headless:
            args.append("--headless")
        if options.bridge:
            args.append("--bridge")
        if options.bridge_file:
            args += ["--bridge-file", options.bridge_file]
        if options.allow_overwrite:
            args.append("--allow-overwrite")
        return sciforge_mcp.main(args)
    calls = []
    if options.command == "run":
        try:
            calls = read_calls(options)
        except (ValueError, OSError) as exc:
            sys.stderr.write("[SciForge] run: %s\n" % exc)
            return 2
    if not _need_freecad():
        return 2
    from sciforge.ai import headless

    out = out or headless.take_stdout()

    def say(text):
        out.write((text.rstrip("\n") + "\n").encode("utf-8"))

    try:
        if options.command == "info":
            say(json.dumps(headless.info(options.file), indent=1, ensure_ascii=False, default=str))
            return 0
        host = headless.HeadlessHost(
            allow_overwrite=getattr(options, "force", False),
            overwrite_option="--force",
            relative_base=os.getcwd(),  # (a relative path in a tool call: from here)
        )
        if options.command == "check":
            headless.open_file(options.file, host)
            args = {"interference": not options.no_interference}
            answer = headless.call("check_design", args, host)
            say(answer["text"])
            if answer["is_error"]:
                return 1
            data = json.loads(answer["text"][answer["text"].index("{") :])
            return 0 if data.get("ok") else 1
        if options.command == "render":
            return _render(options, host, say)
        if options.command == "convert":
            answer = headless.convert(options.source, options.target, host)
            say(answer["text"])
            return 1 if answer["is_error"] else 0
        if options.save:
            calls.append(("save_as", {"path": os.path.abspath(options.save)}))
        if not calls and not options.file:
            sys.stderr.write("[SciForge] run: give a file and / or --tool calls\n")
            return 2
        done = headless.run_calls(calls, host, options.file, not options.keep_going)
        failed = any(answer["is_error"] for _t, _a, answer in done)
        if options.json:
            say(
                json.dumps(
                    [
                        {"tool": t, "arguments": a, "text": r["text"], "is_error": r["is_error"]}
                        for t, a, r in done
                    ],
                    indent=1,
                    ensure_ascii=False,
                )
            )
        else:
            for tool, _args, answer in done:
                say("%s %s: %s" % ("ERROR" if answer["is_error"] else "ok", tool, answer["text"]))
        if len(done) < len(calls):
            sys.stderr.write(
                "[SciForge] stopped after the failed tool (%d of %d run)\n"
                % (len(done), len(calls))
            )
        return 1 if failed else 0
    except (RuntimeError, ValueError, OSError) as exc:
        sys.stderr.write("[SciForge] %s\n" % exc)
        return 1


def _run_as_script():
    code = 1
    try:
        code = main()
    except SystemExit as exc:  # argparse's --help and errors
        code = exc.code if isinstance(exc.code, int) else 2
    except Exception as exc:
        sys.stderr.write("[SciForge] sciforge-cli failed: %s\n" % exc)
        code = 1
    try:
        sys.stderr.flush()
    except Exception:
        pass
    os._exit(code)  # (FreeCAD's command-line program would go on into its own console)


if __name__ == "__main__" or (
    len(sys.argv) > 1
    and any(os.path.abspath(a) == os.path.abspath(__file__) for a in sys.argv[1:2])
):
    _run_as_script()
