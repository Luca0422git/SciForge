# SPDX-License-Identifier: LGPL-2.1-or-later
"""The small MCP server an AI app (Claude Desktop, Gemini CLI, Claude Code ...) starts to
reach SciForge (docs/sciforge/dev/briefs/home-cloud-ai.md, section 4.4):

    python sciforge_mcp.py [--bridge-file PATH]

It speaks MCP over stdin / stdout (one JSON message per line, mcp_core.py) and passes each
tool call on to the AI bridge inside SciForge (bridge_core.py) over 127.0.0.1 with the key
from bridge.json. It runs with FreeCAD's own Python, so nothing has to be installed, but it
never imports FreeCAD: SciForge does the work, this process only carries messages. Logs go
to stderr (stdout is only for MCP messages) and never contain a key.

Where bridge.json is: --bridge-file, else the SCIFORGE_BRIDGE_FILE environment variable,
else the first one found of the places SciForge's user data folder can be (see
candidate_bridge_files), looked up again on every call because SciForge may start later.
"""

import argparse
import os
import queue
import socket
import sys
import threading
import urllib.error
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))  # <Mod>/SciForge, which holds sciforge/
if sys.path and os.path.abspath(sys.path[0] or os.curdir) == _HERE:
    sys.path.pop(0)  # the script's own folder: its module names must not shadow others
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sciforge.ai import bridge_core, mcp_core, tools_core  # noqa: E402,F401

TIMEOUT = 120.0  # seconds; one design step can take a while to compute
ENV_BRIDGE_FILE = "SCIFORGE_BRIDGE_FILE"


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

    def __init__(self, bridge_file=None, timeout=TIMEOUT):
        self.bridge_file = bridge_file
        self.timeout = timeout
        # 127.0.0.1 must never go through a proxy set in the environment (HTTP_PROXY ...)
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def call_tool(self, name, args):
        try:
            return self._call(name, args)
        except Exception as exc:
            log("[SciForge] MCP: call %s failed: %s" % (name, exc))
            return bridge_core.error_result("SciForge could not run %s: %s" % (name, exc))

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
                return bridge_core.decode_result(response.read())
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
            return bridge_core.error_result(
                "SciForge did not answer within %d seconds; the step may still be running. "
                "Check SciForge before trying again." % self.timeout
            )
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, (socket.timeout, TimeoutError)):
                return bridge_core.error_result(
                    "SciForge did not answer within %d seconds." % self.timeout
                )
            return bridge_core.error_result(bridge_core.NOT_RUNNING)
        except ConnectionError:
            return bridge_core.error_result(bridge_core.NOT_RUNNING)


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


def main(argv=None, stdin=None, stdout=None):
    parser = argparse.ArgumentParser(description="SciForge's MCP server (stdio).")
    parser.add_argument("--bridge-file", help="path of SciForge's bridge.json")
    options = parser.parse_args(argv)
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


if __name__ == "__main__":
    sys.exit(main())
