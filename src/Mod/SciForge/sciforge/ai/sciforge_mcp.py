# SPDX-License-Identifier: LGPL-2.1-or-later
"""The small MCP server an AI app (Claude Desktop, Gemini CLI, Claude Code ...) starts to
reach SciForge (docs/sciforge/dev/briefs/home-cloud-ai.md, section 4.4):

    python sciforge_mcp.py [--bridge] [--bridge-file PATH]
    freecadcmd sciforge_mcp.py --pass --headless [--allow-overwrite]

It speaks MCP over stdin / stdout (one JSON message per line, mcp_core.py). By default it
passes each tool call on to the AI bridge inside the running SciForge (bridge_core.py) over
127.0.0.1 with the key from bridge.json; it runs with FreeCAD's own Python, so nothing has to
be installed, but it never imports FreeCAD: SciForge does the work, this process only carries
messages. When SciForge is not reachable a call says so: it never switches to running the
tools itself. With --headless (under FreeCAD's command-line program, which
tools/sciforge/sciforge-cli finds) the tools run in this process instead, on designs opened
here (sciforge/ai/headless.py). Logs go to stderr (stdout is only for MCP messages) and never
contain a key.

A reply that gets lost (the connection breaks, or SciForge takes too long) is handled
honestly: a read-only tool is asked again; a tool that changes the design is not, and the
answer says the change may or may not have been applied, so the AI checks the design first
(an idea from CADCraft, docs/sciforge/dev/cadcraft-lessons.md idea 3).

Where bridge.json is: --bridge-file, else the SCIFORGE_BRIDGE_FILE environment variable,
else the first one found of the places SciForge's user data folder can be (see
candidate_bridge_files), looked up again on every call because SciForge may start later.
"""

import argparse
import http.client
import os
import queue
import socket
import sys
import threading
import time
import urllib.error
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))  # <Mod>/SciForge, which holds sciforge/
if sys.path and os.path.abspath(sys.path[0] or os.curdir) == _HERE:
    sys.path.pop(0)  # the script's own folder: its module names must not shadow others
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sciforge.ai import bridge_core, catalog, mcp_core, tools_core  # noqa: E402,F401

TIMEOUT = 120.0  # seconds; one design step can take a while to compute
ENV_BRIDGE_FILE = "SCIFORGE_BRIDGE_FILE"
RETRIES = 2  # a read-only tool whose reply was lost is asked again this many times
RETRY_WAIT = 0.5  # seconds before asking again
MAYBE_APPLIED = (
    "The answer from SciForge was lost (%s), so the change %s may or may not have been "
    "applied. Do not repeat it blindly: inspect the design first (get_design or "
    "get_timeline), then decide."
)


class _LostReply(Exception):
    """The request reached SciForge (or may have) but its answer never came back."""


def log(text):
    try:
        sys.stderr.write(text + "\n")
        sys.stderr.flush()
    except Exception:
        pass


def _version():
    try:
        import sciforge

        return sciforge.__version__
    except Exception:
        return "0"


def _versioned(base):
    """base/v<major>-<minor> folders, newest first, then base itself."""
    found = []
    try:
        for name in os.listdir(base):
            parts = name[1:].split("-") if name.startswith("v") else []
            if len(parts) == 2 and all(p.isdigit() for p in parts):
                found.append((int(parts[0]), int(parts[1]), name))
    except OSError:
        pass
    return [os.path.join(base, name) for _, _, name in sorted(found, reverse=True)] + [base]


def candidate_user_data_dirs(env=None, platform=None, home=None):
    """Where FreeCAD 1.1 puts the user data folder (App.getUserAppDataDir()), SciForge's first.

    FreeCAD 1.1's layout (src/App/ApplicationDirectories.cpp, configurePaths lines 238-243,
    getStandardPaths lines 468-478, versionStringForPath lines 498-503,
    appendVersionIfPossible lines 163-191): <data home>/<ExeName>/v<major>-<minor>/ when that
    versioned folder exists, where data home is %APPDATA% on Windows, ~/Library/Application
    Support on macOS and $XDG_DATA_HOME or ~/.local/share on Linux; FREECAD_USER_DATA, when
    set, is used as it is (getCustomPaths). SciForge's ExeName is "SciForge" with the vendor
    left out (src/Main/MainGui.cpp lines 189-193); stock FreeCAD's is "FreeCAD"."""
    env = os.environ if env is None else env
    platform = sys.platform if platform is None else platform
    home = os.path.expanduser("~") if home is None else home
    result = []
    if env.get("FREECAD_USER_DATA"):
        result.append(env["FREECAD_USER_DATA"])
    if platform.startswith("win"):
        base = env.get("APPDATA") or os.path.join(home, "AppData", "Roaming")
    elif platform == "darwin":
        base = os.path.join(home, "Library", "Application Support")
    else:
        base = env.get("XDG_DATA_HOME") or os.path.join(home, ".local", "share")
    for app in ("SciForge", "FreeCAD"):
        result += _versioned(os.path.join(base, app))
    return result


def candidate_bridge_files(env=None, platform=None, home=None):
    return [bridge_core.bridge_path(d) for d in candidate_user_data_dirs(env, platform, home)]


def find_bridge_file(explicit=None, env=None):
    """The bridge file to use now: the given one, the environment's, or the first that
    exists (None when there is none yet)."""
    env = os.environ if env is None else env
    if explicit:
        return explicit
    if env.get(ENV_BRIDGE_FILE):
        return env[ENV_BRIDGE_FILE]
    for path in candidate_bridge_files(env):
        if os.path.isfile(path):
            return path
    return None


class BridgeClient:
    """Sends tool calls to SciForge's bridge."""

    def __init__(self, bridge_file=None, timeout=TIMEOUT, retries=RETRIES, retry_wait=RETRY_WAIT):
        self.bridge_file = bridge_file
        self.timeout = timeout
        self.retries = retries
        self.retry_wait = retry_wait
        # 127.0.0.1 must never go through a proxy set in the environment (HTTP_PROXY ...)
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def call_tool(self, name, args):
        try:
            return self._call_honestly(name, args)
        except Exception as exc:
            log("[SciForge] MCP: call %s failed: %s" % (name, exc))
            return bridge_core.error_result("SciForge could not run %s: %s" % (name, exc))

    def _call_honestly(self, name, args):
        """A lost reply: read-only tools are asked again, changing tools never are."""
        read_only = catalog.is_read_only(name)
        attempt = 0
        while True:
            try:
                return self._call(name, args)
            except _LostReply as lost:
                if read_only and attempt < self.retries:
                    attempt += 1
                    log("[SciForge] MCP: %s: reply lost (%s), asking again" % (name, lost))
                    time.sleep(self.retry_wait)
                    continue
                if read_only:
                    return bridge_core.error_result(
                        "SciForge did not answer %s (%s), also when asked again. Check that "
                        "SciForge is not busy, then try again." % (name, lost)
                    )
                return bridge_core.error_result(MAYBE_APPLIED % (lost, name))

    def _call(self, name, args):
        path = find_bridge_file(self.bridge_file)
        info = bridge_core.read_bridge_file(path) if path else None
        if info is None or not bridge_core.pid_alive(info["pid"]):
            return bridge_core.error_result(bridge_core.NOT_RUNNING)
        request = urllib.request.Request(
            "http://127.0.0.1:%d%s" % (info["port"], bridge_core.CALL_PATH),
            data=bridge_core.encode_request(name, args),
            headers={"Content-Type": "application/json", bridge_core.KEY_HEADER: info["key"]},
            method="POST",
        )
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                body = response.read()
        except urllib.error.HTTPError as exc:
            body = b""
            try:
                body = exc.read()
            except Exception:
                pass
            if exc.code == 403:
                return bridge_core.error_result(bridge_core.BAD_KEY)
            answer = bridge_core.decode_result(body)
            if answer["text"] == bridge_core.UNREADABLE:
                return bridge_core.error_result(
                    "SciForge answered with an error (HTTP %d)." % exc.code
                )
            answer["is_error"] = True
            return answer
        except (socket.timeout, TimeoutError):
            raise _LostReply("no answer within %d seconds; it may still be working" % self.timeout)
        except urllib.error.URLError as exc:
            reason = exc.reason
            if isinstance(reason, (socket.timeout, TimeoutError)):
                raise _LostReply("no answer within %d seconds" % self.timeout)
            if isinstance(reason, (ConnectionResetError, ConnectionAbortedError, BrokenPipeError)):
                raise _LostReply("the connection broke")
            return bridge_core.error_result(bridge_core.NOT_RUNNING)  # refused: never sent
        except ConnectionRefusedError:
            return bridge_core.error_result(bridge_core.NOT_RUNNING)
        except (
            ConnectionResetError,
            ConnectionAbortedError,
            BrokenPipeError,
            http.client.RemoteDisconnected,
            http.client.IncompleteRead,
            http.client.BadStatusLine,
        ) as exc:
            raise _LostReply("the connection broke: %s" % (exc.__class__.__name__,))
        except ConnectionError:
            return bridge_core.error_result(bridge_core.NOT_RUNNING)
        answer = bridge_core.decode_result(body)
        if answer["text"] == bridge_core.UNREADABLE and not body:
            raise _LostReply("an empty answer")
        return answer


class Server:
    """Reads MCP messages from stdin and writes answers to stdout. Tool calls run one at a
    time on a worker thread (SciForge does one step at a time anyway) so pings and
    tools/list are answered while a step computes."""

    def __init__(self, call_tool, stdin, stdout, version):
        self.call_tool = call_tool
        self.stdin = stdin
        self.stdout = stdout
        self.version = version
        self.lock = threading.Lock()
        self.jobs = queue.Queue()
        self.worker = threading.Thread(target=self._work, name="sciforge-mcp-calls", daemon=True)

    def send(self, message):
        if message is None:
            return
        data = mcp_core.encode(message)
        with self.lock:
            try:
                self.stdout.write(data)
                self.stdout.flush()
            except Exception as exc:
                log("[SciForge] MCP: could not write an answer: %s" % exc)

    def answer(self, message):
        self.send(mcp_core.handle(message, self.call_tool, self.version, log))

    def _work(self):
        while True:
            message = self.jobs.get()
            if message is None:
                return
            self.answer(message)

    def run_in_line(self):
        """Every message in turn on this thread (headless: FreeCAD runs the tools here, and
        FreeCAD wants its own thread)."""
        while True:
            try:
                line = self.stdin.readline()
            except Exception as exc:
                log("[SciForge] MCP: reading stdin failed: %s" % exc)
                break
            if not line:
                break
            try:
                message, error = mcp_core.parse_line(line)
                if error is not None:
                    self.send(error)
                elif message is not None:
                    self.answer(message)
            except Exception as exc:
                log("[SciForge] MCP: could not handle a message: %s" % exc)

    def run(self):
        self.worker.start()
        while True:
            try:
                line = self.stdin.readline()
            except Exception as exc:
                log("[SciForge] MCP: reading stdin failed: %s" % exc)
                break
            if not line:
                break  # EOF: the AI app closed the connection
            try:
                message, error = mcp_core.parse_line(line)
                if error is not None:
                    self.send(error)
                elif isinstance(message, dict) and message.get("method") == "tools/call":
                    self.jobs.put(message)
                elif message is not None:
                    self.answer(message)
            except Exception as exc:
                log("[SciForge] MCP: could not handle a message: %s" % exc)
        self.jobs.put(None)
        self.worker.join(TIMEOUT + 5)


def _arguments(argv):
    """Our arguments (FreeCAD's command-line program passes them after --pass)."""
    return [a for a in argv if a != "--pass"]


def main(argv=None, stdin=None, stdout=None):
    parser = argparse.ArgumentParser(description="SciForge's MCP server (stdio).")
    parser.add_argument("--bridge-file", help="path of SciForge's bridge.json")
    parser.add_argument(
        "--bridge",
        action="store_true",
        help="forward the tools to the running SciForge (the default)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="run the tools in this process (needs FreeCAD's command-line program)",
    )
    parser.add_argument(
        "--allow-overwrite",
        action="store_true",
        help="headless: tools may replace files that exist",
    )
    raw = sys.argv[1:] if argv is None else argv
    if argv is None:
        for i, item in enumerate(sys.argv):  # under freecadcmd: what follows this file
            if os.path.abspath(item) == os.path.abspath(__file__):
                raw = sys.argv[i + 1 :]
                break
    options = parser.parse_args(_arguments(raw))
    if options.headless and (options.bridge or options.bridge_file):
        log("[SciForge] MCP: --headless runs the tools here; it takes no bridge options")
        return 2
    if options.headless:
        return _main_headless(options, stdin, stdout)
    stdin = stdin if stdin is not None else sys.stdin.buffer
    stdout = stdout if stdout is not None else sys.stdout.buffer
    client = BridgeClient(options.bridge_file)
    log("[SciForge] MCP server %s started" % _version())
    try:
        Server(client.call_tool, stdin, stdout, _version()).run()
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        log("[SciForge] MCP server stopped: %s" % exc)
        return 1
    log("[SciForge] MCP server stopped")
    return 0


def _main_headless(options, stdin=None, stdout=None):
    try:
        import FreeCAD  # noqa: F401
    except ImportError:
        log(
            "[SciForge] MCP: --headless needs FreeCAD: start it with tools/sciforge/sciforge-cli "
            "mcp --headless (or freecadcmd sciforge_mcp.py --pass --headless)"
        )
        return 2
    from sciforge.ai import headless

    stdin = stdin if stdin is not None else sys.stdin.buffer
    stdout = stdout if stdout is not None else headless.take_stdout()
    client = headless.InProcessClient(headless.HeadlessHost(options.allow_overwrite))
    log("[SciForge] MCP server %s started (headless: the tools run here)" % _version())
    try:
        Server(client.call_tool, stdin, stdout, _version()).run_in_line()
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        log("[SciForge] MCP server stopped: %s" % exc)
        return 1
    log("[SciForge] MCP server stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
elif len(sys.argv) > 1 and os.path.abspath(sys.argv[1]) == os.path.abspath(__file__):
    _code = main()  # run as a script by FreeCAD's command-line program
    try:
        sys.stderr.flush()
    except Exception:
        pass
    os._exit(_code or 0)
