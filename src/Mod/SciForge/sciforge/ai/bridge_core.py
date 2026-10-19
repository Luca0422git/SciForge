# SPDX-License-Identifier: LGPL-2.1-or-later
"""The pure parts of the AI bridge: how SciForge and the MCP server an AI app starts find
and trust each other (docs/sciforge/dev/briefs/home-cloud-ai.md, section 4.3).

When "Allow AI apps to control SciForge" is on, SciForge (sciforge/ai/bridge.py) listens on
127.0.0.1 at a random port and writes <user data>/SciForge/ai/bridge.json with that port, a
random key and its process id. The MCP server (sciforge_mcp.py) reads the file on every
call, because SciForge may start after the AI app, and sends

    POST /call   header X-SciForge-Key: <key>   body {"tool": name, "args": {...}}

and gets back {"text": ..., "image_png_base64": ... or null, "is_error": ...}.

The key keeps other programs and web pages on the computer out: only someone who can read
the file (owner-only permissions) can control SciForge. It is compared in constant time and
never logged. Pure Python: no FreeCAD, no Qt.
"""

import hmac
import json
import os
import secrets
import tempfile
import time

BRIDGE_FILE = "bridge.json"
FOLDER = ("SciForge", "ai")  # under FreeCAD's user data folder (App.getUserAppDataDir())
CALL_PATH = "/call"
KEY_HEADER = "X-SciForge-Key"
MAX_REQUEST_BYTES = 1024 * 1024  # a tool call's arguments; answers (screenshots) can be bigger
FORMAT = 1

NOT_RUNNING = (
    "SciForge is not running, or 'Allow AI apps to control SciForge' is off in " "Preferences > AI."
)
BAD_KEY = (
    "SciForge refused the request: the connection key did not match. Turn 'Allow AI apps "
    "to control SciForge' off and on again in Preferences > AI, then try again."
)


UNREADABLE = "SciForge sent an answer that could not be read."


class BridgeError(ValueError):
    """A request or answer that is not in the bridge's format (the message says why)."""


def bridge_path(user_data_dir):
    """<user data>/SciForge/ai/bridge.json."""
    return os.path.join(user_data_dir, *FOLDER, BRIDGE_FILE)


def make_key():
    return secrets.token_urlsafe(32)


def bridge_info(port, key, pid=None):
    return {
        "format": FORMAT,
        "port": int(port),
        "key": key,
        "pid": os.getpid() if pid is None else int(pid),
        "started": int(time.time()),
    }


def write_bridge_file(path, info):
    """Write the file atomically (a temporary file in the same folder, then os.replace) so
    the MCP server never reads half a file; owner-only on POSIX (Windows: the user's own
    profile folder already keeps other accounts out)."""
    folder = os.path.dirname(os.path.abspath(path))
    os.makedirs(folder, exist_ok=True)
    handle, tmp = tempfile.mkstemp(prefix=".bridge-", suffix=".tmp", dir=folder)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(info, stream)
        if os.name == "posix":
            os.chmod(tmp, 0o600)
        for attempt in range(5):
            try:
                os.replace(tmp, path)
                break
            except PermissionError:  # Windows: a reader has the old file open for a moment
                if attempt == 4:
                    raise
                time.sleep(0.05)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def read_bridge_file(path):
    """{"port", "key", "pid"} from the file, or None when it is missing or not usable.
    Never raises."""
    try:
        with open(path, encoding="utf-8-sig") as stream:
            info = json.load(stream)
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(info, dict):
        return None
    port, key, pid = info.get("port"), info.get("key"), info.get("pid")
    if isinstance(port, bool) or not isinstance(port, int) or not 0 < port < 65536:
        return None
    if not isinstance(key, str) or not key:
        return None
    if pid is not None and (isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0):
        pid = None
    return {"port": port, "key": key, "pid": pid}


def remove_bridge_file(path, pid=None):
    """Delete the file when the bridge stops; with pid, only if that process wrote it (a
    second SciForge may have taken over). Returns True when it was removed."""
    try:
        if pid is not None:
            info = read_bridge_file(path)
            if info is not None and info["pid"] not in (None, pid):
                return False
        os.remove(path)
        return True
    except OSError:
        return False


def key_ok(header_value, key):
    """Whether the request's X-SciForge-Key matches (constant-time comparison)."""
    if not isinstance(header_value, str) or not isinstance(key, str) or not key:
        return False
    return hmac.compare_digest(header_value.encode("utf-8"), key.encode("utf-8"))


def origin_ok(origin_header):
    """Browsers send an Origin header; the MCP server and SciForge's own code do not. A
    request with one is a web page trying to reach the bridge: refuse it."""
    return not origin_header


def check_request(method, path, key_header, key, origin_header=None, length=0):
    """(HTTP status, plain reason) for a request before reading its body; 200 = go on."""
    if method != "POST" or path.split("?", 1)[0] != CALL_PATH:
        return 404, "not found"
    if not origin_ok(origin_header):
        return 403, "requests from web pages are refused"
    if not key_ok(key_header, key):
        return 403, BAD_KEY
    if length is None or length < 0 or length > MAX_REQUEST_BYTES:
        return 413, "the request is too big"
    return 200, ""


# -- envelope ---------------------------------------------------------------------------
def encode_request(tool, args):
    return json.dumps({"tool": tool, "args": args or {}}).encode("utf-8")


def decode_request(body):
    """(tool, args) from a request body; BridgeError with a plain reason otherwise."""
    try:
        data = json.loads(body.decode("utf-8") if isinstance(body, bytes) else body)
    except (ValueError, UnicodeDecodeError) as exc:
        raise BridgeError("the request is not JSON: %s" % exc)
    if not isinstance(data, dict) or not isinstance(data.get("tool"), str):
        raise BridgeError('the request must be {"tool": name, "args": {...}}')
    args = data.get("args", {})
    if args is None:
        args = {}
    if not isinstance(args, dict):
        raise BridgeError("the request's args must be an object")
    return data["tool"], args


def result(text, image_png_base64=None, is_error=False):
    return {
        "text": str(text),
        "image_png_base64": image_png_base64 or None,
        "is_error": bool(is_error),
    }


def error_result(text):
    return result(text, is_error=True)


def encode_result(answer):
    """Bytes for a result dict (as made by result())."""
    answer = answer if isinstance(answer, dict) else {}
    return json.dumps(
        result(answer.get("text", ""), answer.get("image_png_base64"), answer.get("is_error"))
    ).encode("utf-8")


def decode_result(body):
    """A result dict from the bridge's answer; a plain error result when it is not one."""
    try:
        data = json.loads(body.decode("utf-8") if isinstance(body, bytes) else body)
    except (ValueError, UnicodeDecodeError, AttributeError, TypeError):
        return error_result(UNREADABLE)
    if not isinstance(data, dict) or "text" not in data:
        return error_result(UNREADABLE)
    image = data.get("image_png_base64")
    return result(data.get("text"), image if isinstance(image, str) else None, data.get("is_error"))


# -- is SciForge still running? ---------------------------------------------------------
def pid_alive(pid):
    """Best effort: False only when the process surely does not exist (a bridge file left
    behind by a crash). Unknown cases answer True and the connection attempt decides."""
    if pid is None:
        return True
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return True
    if pid <= 0:
        return False
    if os.name == "nt":
        return _pid_alive_windows(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # it exists, it belongs to someone else
    except OSError:
        return True
    return True


def _pid_alive_windows(pid):
    try:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        process_query_limited_information = 0x1000
        still_active = 259
        error_access_denied = 5
        handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
        if not handle:
            return ctypes.get_last_error() == error_access_denied
        try:
            code = wintypes.DWORD()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return True
            return code.value == still_active
        finally:
            kernel32.CloseHandle(handle)
    except Exception:
        return True
