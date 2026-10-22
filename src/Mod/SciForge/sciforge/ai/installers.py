# SPDX-License-Identifier: LGPL-2.1-or-later
"""The "+ Add an AI" buttons' file work: tell an AI app how to start SciForge's MCP server
(docs/sciforge/dev/briefs/home-cloud-ai.md, section 4.4). Every path can be passed in, so
the tests write into temporary folders; nothing here shows a window.

Each app keeps its MCP servers in its own file:
  * Claude Desktop: claude_desktop_config.json, {"mcpServers": {name: {"command", "args",
    "env"}}}, in %APPDATA%\\Claude\\ (Windows), ~/Library/Application Support/Claude/ (macOS).
    Claude Desktop has no official Linux build; ~/.config/Claude/ is where the community
    builds look (not verified against an official source). Claude reads it at start, so it
    has to be quit and started again.
  * Gemini CLI: ~/.gemini/settings.json with the same "mcpServers" shape ("command",
    "args", optional "env", "cwd", "timeout" in ms, "trust"), checked in
    github.com/google-gemini/gemini-cli docs/tools/mcp-server.md (October 2026). `/mcp`
    inside Gemini CLI lists the servers.
  * Claude Desktop extension (.mcpb, formerly .dxt): a zip with manifest.json at its root
    plus the server's files; opening it installs it in one click. Manifest fields from
    github.com/modelcontextprotocol/mcpb MANIFEST.md (manifest_version "0.3", October 2026):
    required manifest_version, name, version (semver), description, author {name}, server
    {type "python", entry_point, mcp_config {command, args, env}}; optional display_name,
    tools [{name, description}], keywords, license. "${__dirname}" in args is replaced by
    the folder Claude unpacks the extension into.
  * Claude Code, Codex CLI and other MCP apps: a command line to copy (`claude mcp add ...
    -- <command>`, `codex mcp add <name> -- <command>`: the codex CLI's own usage line in
    openai/codex codex-rs/cli/src/mcp_cmd.rs).

A file that is changed is backed up first (<file>.sciforge-backup-<time>), a file that is not
valid JSON is never touched, and the new file is written atomically.
"""

import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import time
import zipfile

SERVER_NAME = "sciforge"
ENTRY_POINT = "server/sciforge/ai/sciforge_mcp.py"
MANIFEST_VERSION = "0.3"
_SERVER_MODULES = (
    "tools_core.py",
    "mcp_core.py",
    "mcp_resources.py",
    "bridge_core.py",
    "sciforge_mcp.py",
)
_DOCS = ("docs", "ai")  # the documents for AI models (resources sciforge://docs/...)
_CATALOG = "catalog"  # a package: every .py file in it goes into the extension


class InstallError(RuntimeError):
    """The connection could not be written; the message is a plain sentence."""


def server_command(python_exe, script_path, bridge_file=None):
    """(command, args) that start the MCP server with SciForge's own Python."""
    args = [script_path]
    if bridge_file:
        args += ["--bridge-file", bridge_file]
    return python_exe, args


# -- where the apps keep their settings -------------------------------------------------
def claude_desktop_config_path(platform=None, env=None, home=None):
    platform = sys.platform if platform is None else platform
    env = os.environ if env is None else env
    home = os.path.expanduser("~") if home is None else home
    if platform.startswith("win"):
        base = env.get("APPDATA") or os.path.join(home, "AppData", "Roaming")
        return os.path.join(base, "Claude", "claude_desktop_config.json")
    if platform == "darwin":
        return os.path.join(
            home, "Library", "Application Support", "Claude", "claude_desktop_config.json"
        )
    base = env.get("XDG_CONFIG_HOME") or os.path.join(home, ".config")
    return os.path.join(base, "Claude", "claude_desktop_config.json")


def gemini_settings_path(home=None):
    home = os.path.expanduser("~") if home is None else home
    return os.path.join(home, ".gemini", "settings.json")


# -- JSON settings files ----------------------------------------------------------------
def _read_json(path):
    """The file's JSON object ({} when the file is missing or empty); InstallError when it
    cannot be read or is not a JSON object."""
    if not os.path.exists(path):
        return {}, False
    try:
        with open(path, encoding="utf-8-sig") as stream:
            text = stream.read()
    except (OSError, UnicodeDecodeError) as exc:
        raise InstallError("SciForge could not read %s: %s" % (path, exc))
    if not text.strip():
        return {}, True
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise InstallError(
            "SciForge did not change %s because it is not valid JSON (%s). Fix or remove the "
            "file, then try again." % (path, exc)
        )
    if not isinstance(data, dict):
        raise InstallError("SciForge did not change %s: it does not hold a JSON object." % path)
    return data, True


def _backup(path, now=None):
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(now))
    target = "%s.sciforge-backup-%s" % (path, stamp)
    n = 2
    while os.path.exists(target):
        target = "%s.sciforge-backup-%s-%d" % (path, stamp, n)
        n += 1
    try:
        with open(path, "rb") as source, open(target, "xb") as copy:
            copy.write(source.read())
    except OSError as exc:
        raise InstallError(
            "SciForge could not back up %s, so it did not change it: %s" % (path, exc)
        )
    return target


def _write_atomic(path, data):
    """Write bytes through a temporary file in the same folder, keeping the old file's
    permissions."""
    folder = os.path.dirname(os.path.abspath(path))
    try:
        os.makedirs(folder, exist_ok=True)
        mode = os.stat(path).st_mode & 0o777 if os.path.exists(path) else None
        handle, tmp = tempfile.mkstemp(prefix=".sciforge-", suffix=".tmp", dir=folder)
        try:
            with os.fdopen(handle, "wb") as stream:
                stream.write(data)
            if mode is not None and os.name == "posix":
                os.chmod(tmp, mode)
            os.replace(tmp, path)
        except BaseException:
            try:
                os.remove(tmp)
            except OSError:
                pass
            raise
    except OSError as exc:
        raise InstallError("SciForge could not write %s: %s" % (path, exc))


def _dump(data):
    return (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def add_to_json_config(path, command, args, server_name=SERVER_NAME, env=None, now=None):
    """Set mcpServers.<server_name> = {"command", "args"(, "env")} in a JSON settings file,
    keeping everything else. Returns what was done, in words."""
    data, existed = _read_json(path)
    servers = data.get("mcpServers", {})
    if not isinstance(servers, dict):
        raise InstallError('SciForge did not change %s: its "mcpServers" is not an object.' % path)
    entry = {"command": command, "args": list(args)}
    if env:
        entry["env"] = dict(env)
    if servers.get(server_name) == entry:
        return "SciForge was already set up in %s; nothing changed." % path
    replaced = server_name in servers
    backup = _backup(path, now) if existed else None
    servers[server_name] = entry
    data["mcpServers"] = servers
    _write_atomic(path, _dump(data))
    words = "Updated SciForge's entry in" if replaced else "Added SciForge to"
    text = "%s %s." % (words, path)
    if backup:
        text += " The previous file was kept as %s." % backup
    return text


def remove_from_json_config(path, server_name=SERVER_NAME, now=None):
    """Remove mcpServers.<server_name>, keeping a backup. Returns what was done, in words."""
    data, existed = _read_json(path)
    servers = data.get("mcpServers")
    if not existed or not isinstance(servers, dict) or server_name not in servers:
        return "SciForge was not set up in %s; nothing changed." % path
    backup = _backup(path, now)
    del servers[server_name]
    _write_atomic(path, _dump(data))
    return "Removed SciForge from %s. The previous file was kept as %s." % (path, backup)


def is_configured(path, server_name=SERVER_NAME):
    """Whether an app's settings file has SciForge's entry (Home's AI card); never raises."""
    try:
        data, _existed = _read_json(path)
    except InstallError:
        return False
    servers = data.get("mcpServers")
    return isinstance(servers, dict) and server_name in servers


def add_to_claude_desktop(command, args, path=None, now=None):
    path = path or claude_desktop_config_path()
    text = add_to_json_config(path, command, args, now=now)
    return text + " Quit Claude Desktop completely (also from the tray) and start it again."


def remove_from_claude_desktop(path=None, now=None):
    return remove_from_json_config(path or claude_desktop_config_path(), now=now)


def add_to_gemini(command, args, path=None, now=None):
    path = path or gemini_settings_path()
    text = add_to_json_config(path, command, args, now=now)
    return text + " Start Gemini CLI again and type /mcp to check that SciForge is listed."


def remove_from_gemini(path=None, now=None):
    return remove_from_json_config(path or gemini_settings_path(), now=now)


# -- Claude Desktop extension (.mcpb) ---------------------------------------------------
_SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")


def manifest(version, python_exe, entry_point=ENTRY_POINT, bridge_file=None, tools=None):
    """The extension's manifest.json. python_exe: SciForge's bundled Python (an absolute
    path, so the extension does not depend on a Python installed on the computer)."""
    if not isinstance(version, str) or not _SEMVER.match(version):
        raise InstallError("the extension needs a version like 1.2.3, got %r" % (version,))
    args = ["${__dirname}/" + entry_point]
    if bridge_file:
        args += ["--bridge-file", bridge_file]
    if tools is None:
        from . import tools_core

        tools = [
            {"name": t["name"], "description": t["description"].split(". ")[0].rstrip(".") + "."}
            for t in tools_core.TOOLS
        ]
    return {
        "manifest_version": MANIFEST_VERSION,
        "name": SERVER_NAME,
        "display_name": "SciForge",
        "version": version,
        "description": "Lets Claude build and change the design open in SciForge, step by step "
        "and with undo.",
        "author": {"name": "SciForge"},
        "server": {
            "type": "python",
            "entry_point": entry_point,
            "mcp_config": {"command": python_exe, "args": args, "env": {}},
        },
        "tools": tools,
        "keywords": ["cad", "3d", "design", "sciforge", "freecad"],
        "license": "LGPL-2.1-or-later",
    }


def mcpb_files(mod_root):
    """{archive name: source path} of the server's files, from <Mod>/SciForge."""
    files = {"server/sciforge/__init__.py": os.path.join(mod_root, "sciforge", "__init__.py")}
    files["server/sciforge/ai/__init__.py"] = os.path.join(
        mod_root, "sciforge", "ai", "__init__.py"
    )
    for name in _SERVER_MODULES:
        files["server/sciforge/ai/" + name] = os.path.join(mod_root, "sciforge", "ai", name)
    # the tool catalogue (tools_core and the server read it): the whole package
    folder = os.path.join(mod_root, "sciforge", "ai", _CATALOG)
    for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
        if name.endswith(".py"):
            files["server/sciforge/ai/%s/%s" % (_CATALOG, name)] = os.path.join(folder, name)
    # the documents for AI models, where the server looks for them (server/docs/ai)
    docs = os.path.join(mod_root, *_DOCS)
    for here, dirs, names in os.walk(docs) if os.path.isdir(docs) else []:
        dirs[:] = sorted(d for d in dirs if not d.startswith((".", "_")))
        for name in sorted(names):
            if name.endswith((".md", ".txt", ".json")) and not name.startswith("."):
                rel = os.path.relpath(os.path.join(here, name), mod_root).replace(os.sep, "/")
                files["server/" + rel] = os.path.join(here, name)
    return files


def build_mcpb(out_path, files, manifest_data):
    """Write the .mcpb zip: manifest.json at the root plus files {archive name: source}."""
    for name in files:
        parts = name.replace("\\", "/").split("/")
        if name.startswith(("/", "\\")) or ".." in parts or ":" in name or name == "manifest.json":
            raise InstallError("%r cannot go into the extension" % name)
    for source in files.values():
        if not os.path.isfile(source):
            raise InstallError("SciForge could not find %s to put into the extension." % source)
    folder = os.path.dirname(os.path.abspath(out_path))
    try:
        os.makedirs(folder, exist_ok=True)
        handle, tmp = tempfile.mkstemp(prefix=".sciforge-", suffix=".tmp", dir=folder)
        os.close(handle)
        try:
            with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("manifest.json", json.dumps(manifest_data, indent=2))
                for name in sorted(files):
                    archive.write(files[name], name.replace("\\", "/"))
            os.replace(tmp, out_path)
        except BaseException:
            try:
                os.remove(tmp)
            except OSError:
                pass
            raise
    except OSError as exc:
        raise InstallError("SciForge could not write the extension %s: %s" % (out_path, exc))
    return out_path


# -- other apps -------------------------------------------------------------------------
def command_line(command, args, platform=None):
    parts = [command] + list(args)
    platform = sys.platform if platform is None else platform
    if platform.startswith("win"):
        return subprocess.list2cmdline(parts)
    return shlex.join(parts)


def other_app_text(command, args, platform=None):
    """What to copy for apps SciForge cannot set up itself."""
    line = command_line(command, args, platform)
    return "\n".join(
        [
            "Claude Code:",
            "  claude mcp add --transport stdio --scope user %s -- %s" % (SERVER_NAME, line),
            "Codex CLI:",
            "  codex mcp add %s -- %s" % (SERVER_NAME, line),
            "Other MCP apps (stdio server):",
            "  command: %s" % command,
            "  arguments: %s" % json.dumps(list(args)),
        ]
    )
