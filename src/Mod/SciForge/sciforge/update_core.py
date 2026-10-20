# SPDX-License-Identifier: LGPL-2.1-or-later
"""The update check's rules (pure Python: no FreeCAD, no Qt; unit tested in
SciForgeTests/unit/test_update_core.py). update_ui.py is the window side.

What it does (brief docs/sciforge/dev/briefs/beta-release.md, R3):
  * asks GitHub for the newest releases (one GET, 5 s timeout, standard library only),
  * picks the newest one that is newer than this SciForge, for the channel the user chose
    (Stable only / Betas too), through version_core (the one place that orders versions),
  * reads the release's ``sciforge-release.json`` (core id, file names, SHA-256 hashes),
  * decides how to install it (plan): the small module update when the compiled part
    (the "core") is the same, the full installer otherwise, the browser on Linux,
  * downloads a file and checks its SHA-256.

Every network call has a timeout and runs on a worker thread (update_ui); the base address
is ``API_BASE`` so the tests point it at a local fake GitHub and never touch the internet.
Nothing here raises for bad input from the network: junk gives None or an UpdateError with
a plain sentence for the person.
"""

import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import zipfile

from . import version_core

REPO = "Luca0422git/SciForge"
# Test seam: the scenarios set this to a local fake GitHub (SCIFORGE_UPDATE_API does the same
# from outside, for trying an update by hand without a real release).
API_BASE = os.environ.get("SCIFORGE_UPDATE_API") or "https://api.github.com"
SITE_BASE = "https://github.com"
TIMEOUT = 5  # seconds, for each request of the check
DOWNLOAD_TIMEOUT = 20  # seconds without a single byte
LIST_LIMIT = 10
MANIFEST_NAME = "sciforge-release.json"
MAX_JSON_BYTES = 2 * 1024 * 1024
CHECK_EVERY = 24 * 3600  # at most one automatic check a day

STABLE = "stable"
BETA = "beta"
CHANNELS = (STABLE, BETA)

# The roles of the files of a release (the keys of "assets" in sciforge-release.json).
ROLES = ("installer", "portable", "appimage", "module")

_LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1", "[::1]")
_HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")


class UpdateError(Exception):
    """Something the person can be told in one sentence. ``code``: "offline" (no network,
    timeout, GitHub down), "rate" (GitHub's request limit), "http" (another answer),
    "data" (an answer that is not what we expect)."""

    def __init__(self, code, text):
        super().__init__(text)
        self.code = code
        self.text = text


# -- addresses ---------------------------------------------------------------------------
def releases_url():
    return "%s/repos/%s/releases?per_page=%d" % (API_BASE.rstrip("/"), REPO, LIST_LIMIT)


def release_page(tag):
    """The release's page in the browser (the notes, "What's new")."""
    if tag:
        return "%s/%s/releases/tag/%s" % (SITE_BASE, REPO, urllib.parse.quote(str(tag)))
    return releases_page()


def releases_page():
    return "%s/%s/releases" % (SITE_BASE, REPO)


def user_agent(version):
    return "SciForge/%s" % version


def is_web_url(url):
    """Only http(s) addresses are ever opened or downloaded (never file:// and the like)."""
    try:
        return urllib.parse.urlparse(str(url)).scheme in ("http", "https")
    except Exception:
        return False


def _host(url):
    try:
        return (urllib.parse.urlparse(str(url)).hostname or "").lower()
    except Exception:
        return ""


def blocked(url):
    """True in a test run (SCIFORGE_NO_INTERNET=1, set by tools/sciforge/run_tests.sh) for every
    address that is not this computer's own: no test may touch the real internet."""
    return bool(os.environ.get("SCIFORGE_NO_INTERNET")) and _host(url) not in _LOCAL_HOSTS


def _open(request, timeout):
    """urlopen, but never through a proxy for this computer's own addresses (the tests' fake
    GitHub on 127.0.0.1), and never online in a test run."""
    host = _host(request.full_url)
    if blocked(request.full_url):
        raise UpdateError("offline", "Could not reach GitHub (this is a test run: no internet).")
    if host in _LOCAL_HOSTS:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        return opener.open(request, timeout=timeout)
    return urllib.request.urlopen(request, timeout=timeout)


def _explain(exc):
    """An UpdateError for what urllib raised."""
    if isinstance(exc, urllib.error.HTTPError):
        if exc.code in (403, 429):
            return UpdateError("rate", "GitHub is limiting requests right now (HTTP %d)." % exc.code)
        return UpdateError("http", "GitHub answered HTTP %d." % exc.code)
    return UpdateError("offline", "Could not reach GitHub (%s)." % _short(exc))


def _short(exc):
    reason = getattr(exc, "reason", None) or exc
    text = str(reason).strip() or exc.__class__.__name__
    return text[:120]


def http_get(url, timeout=TIMEOUT, version="", limit=MAX_JSON_BYTES):
    """The body of ``url`` (bytes, at most ``limit``). Raises UpdateError."""
    if not is_web_url(url):
        raise UpdateError("data", "Not a web address: %s" % str(url)[:80])
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": user_agent(version),
            "Accept": "application/vnd.github+json, application/json, */*",
        },
    )
    try:
        with _open(request, timeout) as response:
            body = response.read(limit + 1)
    except UpdateError:
        raise
    except Exception as exc:  # urllib's own errors, timeouts, resets, bad status lines
        raise _explain(exc)
    if len(body) > limit:
        raise UpdateError("data", "The answer from GitHub is too big.")
    return body


# -- reading what GitHub says -------------------------------------------------------------
def _safe_name(name):
    return (
        isinstance(name, str)
        and name not in ("", ".", "..")
        and "/" not in name
        and "\\" not in name
        and "\x00" not in name
        and len(name) < 200
    )


def parse_releases(data):
    """The releases that count, as [{"version", "tag", "prerelease", "page", "assets":
    {file name: address}, "sizes": {file name: bytes}}] in the order GitHub gave. Drafts,
    entries that are not SciForge release tags (``sciforge-v<version>``) and junk are left
    out; ``data`` is the parsed JSON (anything else gives [])."""
    found = []
    if not isinstance(data, list):
        return found
    for entry in data:
        try:
            if not isinstance(entry, dict) or entry.get("draft"):
                continue
            tag = entry.get("tag_name")
            if not isinstance(tag, str) or not tag.startswith(version_core.TAG_PREFIX):
                continue
            version = version_core.canonical(tag)
            if version is None:
                continue
            assets, sizes = {}, {}
            for asset in entry.get("assets") or []:
                if not isinstance(asset, dict):
                    continue
                name, url = asset.get("name"), asset.get("browser_download_url")
                if _safe_name(name) and isinstance(url, str) and is_web_url(url):
                    assets[name] = url
                    if isinstance(asset.get("size"), int):
                        sizes[name] = asset["size"]
            page = entry.get("html_url")
            found.append(
                {
                    "version": version,
                    "tag": tag,
                    "prerelease": bool(entry.get("prerelease")) or version_core.is_prerelease(version),
                    "page": page if isinstance(page, str) and is_web_url(page) else release_page(tag),
                    "assets": assets,
                    "sizes": sizes,
                    "manifest": None,
                }
            )
        except Exception:
            continue
    return found


def default_channel(installed_version):
    """Betas too while this SciForge is a beta; Stable only otherwise."""
    return BETA if version_core.is_prerelease(installed_version) else STABLE


def clean_channel(value, installed_version):
    return value if value in CHANNELS else default_channel(installed_version)


def choose(releases, installed_version, channel):
    """The newest release that is newer than ``installed_version`` and allowed by the channel
    (stable: no pre-releases), or None."""
    best = None
    for release in releases or []:
        try:
            version = release["version"]
            if not version_core.newer(version, installed_version):
                continue
            if channel != BETA and release.get("prerelease"):
                continue
            if best is None or version_core.newer(version, best["version"]):
                best = release
        except Exception:
            continue
    return best


def parse_manifest(raw):
    """sciforge-release.json as {"version", "tag", "core", "date", "notes_url", "assets":
    {role: file name}, "sha256": {file name: lowercase hash}}, or None when it is not one
    (bytes or text; never raises). A file without a valid hash is not listed under sha256."""
    try:
        if isinstance(raw, (bytes, bytearray)):
            raw = bytes(raw).decode("utf-8")
        data = json.loads(raw)
    except Exception:
        return None
    try:
        if not isinstance(data, dict):
            return None
        version = version_core.canonical(data.get("version"))
        if version is None:
            return None
        assets = {}
        if isinstance(data.get("assets"), dict):
            for role in ROLES:
                name = data["assets"].get(role)
                if _safe_name(name):
                    assets[role] = name
        sha256 = {}
        if isinstance(data.get("sha256"), dict):
            for name, digest in data["sha256"].items():
                if _safe_name(name) and isinstance(digest, str) and _HEX64.match(digest):
                    sha256[name] = digest.lower()
        tag = data.get("tag")
        notes = data.get("notes_url")
        return {
            "version": version,
            "tag": tag if isinstance(tag, str) and tag else version_core.tag_for(version),
            "core": str(data.get("core") or "").strip(),
            "date": str(data.get("date") or ""),
            "notes_url": notes if isinstance(notes, str) and is_web_url(notes) else "",
            "assets": assets,
            "sha256": sha256,
        }
    except Exception:
        return None


def attach_manifest(release, manifest):
    """The release with its manifest, or without when the manifest is for another version."""
    release = dict(release)
    ok = manifest is not None and manifest.get("version") == release.get("version")
    release["manifest"] = manifest if ok else None
    return release


def fetch_manifest(release, version="", get=None):
    """Download and parse the release's sciforge-release.json; None when it has none or it is
    not valid. Raises UpdateError only when the network itself fails."""
    get = get or http_get
    url = (release.get("assets") or {}).get(MANIFEST_NAME)
    if not url:
        return None
    return parse_manifest(get(url, version=version))


def check(installed_version, channel, get=None):
    """Ask GitHub. {"status": "newer" | "current", "release": the release with its manifest or
    None}. Raises UpdateError ("offline", "rate", "http", "data") with a plain sentence."""
    get = get or http_get
    try:
        body = get(releases_url(), version=installed_version)
        data = json.loads(body.decode("utf-8") if isinstance(body, (bytes, bytearray)) else body)
    except UpdateError:
        raise
    except Exception:
        raise UpdateError("data", "GitHub's answer could not be read.")
    if not isinstance(data, list):
        raise UpdateError("data", "GitHub's answer was not a list of releases.")
    release = choose(parse_releases(data), installed_version, clean_channel(channel, installed_version))
    if release is None:
        return {"status": "current", "release": None}
    manifest = None
    try:
        manifest = fetch_manifest(release, installed_version, get)
    except UpdateError as exc:
        if exc.code in ("offline", "rate"):
            raise
    return {"status": "newer", "release": attach_manifest(release, manifest)}


# -- how to install ------------------------------------------------------------------------
def detect_layout(platform_name, home, environ=None, exists=os.path.exists):
    """What kind of SciForge this is: {"os": "windows" | "linux" | "other", "kind":
    "installed" | "portable" | "appimage" | "linux" | "other", "home": folder}.
    ``home`` is the program's folder (App.getHomePath())."""
    environ = os.environ if environ is None else environ
    name = str(platform_name or "").lower()
    home = str(home or "")
    if name.startswith("win"):
        has_tree = bool(home) and exists(os.path.join(home, "bin")) and exists(os.path.join(home, "Mod"))
        if not has_tree:
            return {"os": "windows", "kind": "other", "home": home}
        program_files = [environ.get(k, "") for k in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432")]
        under = any(p and home.lower().replace("/", "\\").startswith(p.lower()) for p in program_files)
        return {"os": "windows", "kind": "installed" if under else "portable", "home": home}
    if name.startswith("linux"):
        return {"os": "linux", "kind": "appimage" if environ.get("APPIMAGE") else "linux", "home": home}
    return {"os": "other", "kind": "other", "home": home}


def plan(installed, release, layout):
    """How to install ``release`` (parse_releases entry, with its manifest if it had one) on
    this SciForge. ``installed``: {"version", "core"}; ``layout``: detect_layout().

    {"kind": "module" | "installer" | "browser", "asset": file name, "url", "sha256", "size",
     "page": the release page, "reason": a plain sentence}
      module     the small download that replaces Mod\\SciForge (same core, Windows installed
                 or portable build);
      installer  the full installer (a different core, or no module file);
      browser    nothing is installed from here (Linux, no verifiable file): the release
                 page opens."""
    page = (release.get("manifest") or {}).get("notes_url") or release.get("page") or releases_page()
    out = {"kind": "browser", "asset": "", "url": "", "sha256": "", "size": 0, "page": page, "reason": ""}
    manifest = release.get("manifest")

    def pick(role):
        name = (manifest or {}).get("assets", {}).get(role, "")
        url = (release.get("assets") or {}).get(name, "") if name else ""
        digest = (manifest or {}).get("sha256", {}).get(name, "") if name else ""
        if name and url and digest and is_web_url(url):
            return {
                "asset": name,
                "url": url,
                "sha256": digest,
                "size": (release.get("sizes") or {}).get(name, 0),
            }
        return None

    if layout.get("os") != "windows":
        if layout.get("kind") == "appimage":
            out["reason"] = (
                "The AppImage cannot replace itself: download the new AppImage and replace the old one."
            )
        else:
            out["reason"] = "Download the new version from the release page."
        return out
    if manifest is None:
        out["reason"] = "This release has no checksum file, so it is not installed from here."
        return out
    same_core = bool(installed.get("core")) and installed.get("core") == manifest.get("core")
    if same_core and layout.get("kind") in ("installed", "portable"):
        found = pick("module")
        if found:
            out.update(found, kind="module", reason="Only SciForge's own files changed: a small update.")
            return out
    found = pick("installer")
    if found:
        why = "The program itself changed: the full installer."
        if same_core:
            why = "This release has no small update: the full installer."
        out.update(found, kind="installer", reason=why)
        return out
    out["reason"] = "This release has no installer for Windows, so it is not installed from here."
    return out


# -- files ---------------------------------------------------------------------------------
def sha256_of(path, chunk=1024 * 1024):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            block = handle.read(chunk)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def verify(path, expected):
    """True when the file's SHA-256 is ``expected`` (never raises)."""
    try:
        return bool(expected) and sha256_of(path) == str(expected).lower()
    except Exception:
        return False


def updates_dir(user_data, version):
    """<user data>/SciForge/updates/<version>: where one release's downloads go."""
    return os.path.join(user_data, "SciForge", "updates", version_core.canonical(version) or "unknown")


def download(url, dest, expected, progress=None, cancelled=None, version=""):
    """Download ``url`` to ``dest`` and check its SHA-256 against ``expected``.

    Returns (status, text): "ok" (the file is at dest and its hash is right), "cancelled",
    "mismatch" (the file was deleted), "offline", "error". ``progress(done, total)`` (total
    0 when unknown) and ``cancelled()`` are called from the worker thread, about every
    64 KB. A file already at dest with the right hash is kept (nothing is downloaded)."""
    if verify(dest, expected):
        return "ok", dest
    if not is_web_url(url):
        return "error", "Not a web address."
    part = dest + ".part"
    try:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        request = urllib.request.Request(url, headers={"User-Agent": user_agent(version)})
        digest = hashlib.sha256()
        done = 0
        with _open(request, DOWNLOAD_TIMEOUT) as response:
            try:
                total = int(response.headers.get("Content-Length") or 0)
            except Exception:
                total = 0
            with open(part, "wb") as handle:
                while True:
                    if cancelled is not None and cancelled():
                        handle.close()
                        _remove(part)
                        return "cancelled", ""
                    block = response.read(64 * 1024)
                    if not block:
                        break
                    handle.write(block)
                    digest.update(block)
                    done += len(block)
                    if progress is not None:
                        progress(done, total)
        if total and done != total:
            _remove(part)
            return "error", "The download ended early (%d of %d bytes)." % (done, total)
        if digest.hexdigest() != str(expected).lower():
            _remove(part)
            return "mismatch", "The file's checksum does not match."
        os.replace(part, dest)
        return "ok", dest
    except Exception as exc:
        _remove(part)
        if isinstance(exc, (urllib.error.URLError, OSError)) and not isinstance(
            exc, urllib.error.HTTPError
        ):
            return "offline", "Could not reach GitHub (%s)." % _short(exc)
        return "error", _explain(exc).text if isinstance(exc, urllib.error.HTTPError) else str(exc)[:200]


def _remove(path):
    try:
        os.remove(path)
    except OSError:
        pass


def safe_extract(zip_path, dest):
    """Unzip ``zip_path`` into the (new, emptied) folder ``dest``; refuses a file that would
    land outside it. Returns the number of files. Raises ValueError / zipfile errors."""
    import shutil

    shutil.rmtree(dest, ignore_errors=True)
    os.makedirs(dest, exist_ok=True)
    root = os.path.realpath(dest)
    count = 0
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            target = os.path.realpath(os.path.join(root, member.filename))
            if target != root and not target.startswith(root + os.sep):
                raise ValueError("The update file is not what SciForge expected (%s)." % member.filename)
        for member in archive.infolist():
            archive.extract(member, root)
            if not member.is_dir():
                count += 1
    return count


# -- handing over --------------------------------------------------------------------------
def _ps_quote(text):
    return "'" + str(text).replace("'", "''") + "'"


def handover_argv(kind, pid, target="", script="", installer=""):
    """The command that carries on after SciForge quits (Windows).

    module:    PowerShell runs the quick update's install_update.ps1 on ``target`` (the
               SciForge folder): it waits for process ``pid`` to end, replaces Mod\\SciForge
               (asking for administrator rights itself when needed), and starts SciForge again.
    installer: PowerShell waits for ``pid`` to end, then starts the downloaded installer (the
               person sees the normal installer)."""
    common = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden"]
    if kind == "module":
        return common + [
            "-File", script, "-Target", target, "-WaitPid", str(int(pid)), "-Restart", "-Quiet",
        ]  # fmt: skip
    command = (
        "try { Wait-Process -Id %d -Timeout 900 -ErrorAction SilentlyContinue } catch { }; "
        "Start-Process -FilePath %s" % (int(pid), _ps_quote(installer))
    )
    return common + ["-Command", command]


# -- when ----------------------------------------------------------------------------------
def due(last_check, now, every=CHECK_EVERY):
    """True when an automatic check is allowed: never checked, a day passed, or the clock
    went backwards."""
    try:
        last = float(last_check or 0)
        return last <= 0 or now < last or now - last >= every
    except Exception:
        return True


def installed_core():
    """The core id of this build ("" when unknown: a source tree, or a quick update that
    does not know it). Written at build time into sciforge/core_info.py."""
    try:
        from . import core_info

        return str(core_info.CORE or "").strip()
    except Exception:
        return ""


def format_size(count):
    try:
        count = float(count)
    except Exception:
        return ""
    if count <= 0:
        return ""
    for unit in ("bytes", "KB", "MB", "GB"):
        if count < 1024 or unit == "GB":
            return ("%d %s" % (count, unit)) if unit == "bytes" else ("%.1f %s" % (count, unit))
        count /= 1024.0
    return ""
