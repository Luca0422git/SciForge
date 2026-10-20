#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
"""Makes the three generated files of a SciForge release (brief beta-release.md, R3):

  sciforge-release.json  what the update check reads: version, tag, core id, date, the release
                         notes' address, the files by role and every file's SHA-256
  SHA256SUMS.txt         the same hashes in the format `sha256sum -c` reads
  release-notes.md       the GitHub release's text: this version's section of CHANGELOG.md, which
                         file to download, the fixed "Windows protected your PC" text
                         (docs/sciforge/smartscreen.md), how to update, the checksums

  tools/sciforge/make_release_files.py --tag sciforge-v0.1.0-beta --core abc1234 \\
      --assets DIR --out DIR [--date YYYY-MM-DD] [--repo OWNER/NAME] [--require-all]

--assets is searched (all sub-folders) for the installer (*-installer.exe), the portable build
(*.7z), the AppImage (*.AppImage) and the quick update (SciForge-quick-update-*.zip).
--require-all: all four must be there (a release from a tag); without it a missing one is just
left out (a manual dry run of one platform).

The functions are pure (text in, text out) and unit tested with temp-folder fixtures
(SciForgeTests/unit/test_make_release_files.py). The command line fails with a clear message
when CHANGELOG.md has no section for the version or smartscreen.md is missing: a release
without them must not go out.
"""

import argparse
import datetime
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "src", "Mod", "SciForge"))
from sciforge import version_core  # noqa: E402  (pure Python, no FreeCAD)

DEFAULT_REPO = "Luca0422git/SciForge"
ROLES = ("installer", "portable", "appimage", "module")
CHANGELOG = os.path.join(REPO_ROOT, "CHANGELOG.md")
SMARTSCREEN = os.path.join(REPO_ROOT, "docs", "sciforge", "smartscreen.md")


class ReleaseFilesError(Exception):
    """A problem to tell the person plainly (the command line prints it and stops)."""


# -- the files of a release ------------------------------------------------------------------
def classify(name):
    """The role of a built file by its name, or "" (checksum files and others are no role)."""
    if name.endswith("-installer.exe"):
        return "installer"
    if name.endswith(".7z"):
        return "portable"
    if name.endswith(".AppImage"):
        return "appimage"
    if name.startswith("SciForge-quick-update-") and name.endswith(".zip"):
        return "module"
    return ""


def find_assets(folder):
    """{role: path} of the release files below ``folder``. Two files of one role is an error."""
    found = {}
    for root, dirs, files in os.walk(folder):
        dirs.sort()
        for name in sorted(files):
            role = classify(name)
            if not role:
                continue
            if role in found:
                raise ReleaseFilesError(
                    "two files for the %s: %s and %s" % (role, found[role], os.path.join(root, name))
                )
            found[role] = os.path.join(root, name)
    return found


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


# -- CHANGELOG.md and smartscreen.md ----------------------------------------------------------
def changelog_section(text, version):
    """The body of ``version``'s section of CHANGELOG.md (the text under a "## " heading that
    names the version, up to the next "## " heading), stripped; None when there is none.
    The heading may be "## 0.1.0-beta", "## [0.1.0-beta] - 2026-10-20", "## v0.1.0-beta (date)":
    the version must stand on its own (0.1.0-beta is not found in a 0.1.0-beta.2 heading)."""
    version = version_core.canonical(version)
    if not version or not isinstance(text, str):
        return None
    name = re.compile(
        r"(?<![0-9A-Za-z_.+-])(?:sciforge-v|v)?" + re.escape(version) + r"(?![0-9A-Za-z_+-]|\.[0-9A-Za-z])"
    )
    lines = text.replace("\r\n", "\n").split("\n")
    start = None
    for index, line in enumerate(lines):
        if re.match(r"^##(?!#)\s", line) and name.search(line):
            start = index + 1
            break
    if start is None:
        return None
    body = []
    for line in lines[start:]:
        if re.match(r"^##(?!#)\s", line):
            break
        body.append(line)
    result = "\n".join(body).strip()
    return result or None


def smartscreen_block(text):
    """The fixed Windows SmartScreen text as a section: its own first-line title becomes a "##"
    heading (any level), or "## Windows protected your PC" is added when it has none."""
    text = text.replace("\r\n", "\n").strip()
    first, _sep, rest = text.partition("\n")
    match = re.match(r"^#{1,6}\s+(.*)$", first)
    if match:
        return "## %s\n%s" % (match.group(1).strip(), rest)
    return "## Windows protected your PC\n\n" + text


# -- the generated files ---------------------------------------------------------------------
def release_json(version, tag, core, date, repo, names, hashes):
    """sciforge-release.json's text. ``names``: {role: file name}; ``hashes``: {file name: hex}."""
    data = {
        "version": version,
        "tag": tag,
        "core": core,
        "date": date,
        "notes_url": "https://github.com/%s/releases/tag/%s" % (repo, tag),
        "assets": {role: names[role] for role in ROLES if role in names},
        "sha256": {name: hashes[name] for name in sorted(hashes)},
    }
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def checksums_text(hashes):
    """SHA256SUMS.txt: `sha256sum -c` format (hash, two spaces, file name), by name."""
    return "".join("%s  %s\n" % (hashes[name], name) for name in sorted(hashes))


def release_notes(version, tag, section, smartscreen, names, hashes, repo=DEFAULT_REPO):
    parts = [section.strip(), ""]
    parts.append("## Which file do I download?")
    parts.append("")
    if "installer" in names:
        parts.append("- **Windows, recommended:** `%s` (the installer)." % names["installer"])
    if "portable" in names:
        parts.append(
            "- **Windows, without installing:** `%s` (unzip it with 7-Zip, then run `bin\\SciForge.exe`)."
            % names["portable"]
        )
    if "appimage" in names:
        parts.append(
            "- **Linux:** `%s` (make it executable with `chmod +x`, then run it)." % names["appimage"]
        )
    parts.append(
        "- You do not need the other files: `sciforge-release.json` and the quick update"
        + (" (`%s`)" % names["module"] if "module" in names else "")
        + " are what SciForge's own updater reads."
    )
    parts += ["", smartscreen_block(smartscreen), ""]
    parts += [
        "## How to update",
        "",
        "SciForge checks for updates when it starts (Preferences > General > Updates switches that "
        "off). In SciForge, open **Help > Check for Updates**, then click **Update now**: it "
        "downloads the new version, checks it against the checksums below and installs it. "
        "You can also download the new installer from this page and run it over the old one.",
        "",
    ]
    if "module" in names:
        parts += [
            "The quick update (`%s`) only swaps SciForge's own files: unzip it and double-click "
            "`install_update.cmd` (the README inside says more)." % names["module"],
            "",
        ]
    parts += ["## Checksums (SHA-256)", "", "```"]
    parts += ["%s  %s" % (hashes[name], name) for name in sorted(hashes)]
    parts += ["```", ""]
    if "installer" in names:
        parts += [
            "To check a download on Windows, open PowerShell in the folder and run "
            "`Get-FileHash .\\%s -Algorithm SHA256`; the result must be the same as above." % names["installer"],
            "",
        ]
    return "\n".join(parts).rstrip() + "\n"


def build_all(tag, core, date, repo, files, changelog, smartscreen, require_all=False):
    """{file name: text} for the three generated files. ``files``: {role: path of a built
    file}. Raises ReleaseFilesError with a plain sentence."""
    version = version_core.canonical(tag)
    if version is None or version_core.tag_for(version) != tag:
        raise ReleaseFilesError("%r is not a release tag like %s0.1.0-beta" % (tag, version_core.TAG_PREFIX))
    if not str(core or "").strip():
        raise ReleaseFilesError("the core id is empty (tools/sciforge/core_id.sh makes it)")
    if not files:
        raise ReleaseFilesError("no release files found")
    missing = [role for role in ROLES if role not in files]
    if require_all and missing:
        raise ReleaseFilesError("missing release files: %s" % ", ".join(missing))
    if changelog is None:
        raise ReleaseFilesError("CHANGELOG.md is missing")
    section = changelog_section(changelog, version)
    if section is None:
        raise ReleaseFilesError(
            "CHANGELOG.md has no section for %s (add a heading like '## %s - %s' with what changed)"
            % (version, version, date)
        )
    if smartscreen is None:
        raise ReleaseFilesError("docs/sciforge/smartscreen.md is missing")
    names = {role: os.path.basename(path) for role, path in files.items()}
    hashes = {names[role]: sha256_file(path) for role, path in files.items()}
    return {
        "sciforge-release.json": release_json(version, tag, core, date, repo, names, hashes),
        "SHA256SUMS.txt": checksums_text(hashes),
        "release-notes.md": release_notes(version, tag, section, smartscreen, names, hashes, repo),
    }


def _read(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()
    except OSError:
        return None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--tag", required=True, help="the release tag, sciforge-v<version>")
    parser.add_argument("--core", required=True, help="the core id (tools/sciforge/core_id.sh)")
    parser.add_argument("--assets", required=True, help="folder with the built files")
    parser.add_argument("--out", required=True, help="folder for the three generated files")
    parser.add_argument("--date", default="", help="YYYY-MM-DD (default: today, UTC)")
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--changelog", default=CHANGELOG)
    parser.add_argument("--smartscreen", default=SMARTSCREEN)
    parser.add_argument("--require-all", action="store_true")
    parser.add_argument(
        "--list-file", default="", help="write the paths to attach to the GitHub release here, one per line"
    )
    args = parser.parse_args(argv)
    date = args.date or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    try:
        files = find_assets(args.assets)
        made = build_all(
            args.tag, args.core, date, args.repo, files,
            _read(args.changelog), _read(args.smartscreen), args.require_all,
        )  # fmt: skip
    except ReleaseFilesError as exc:
        print("[SciForge] make_release_files: %s" % exc, file=sys.stderr)
        return 1
    os.makedirs(args.out, exist_ok=True)
    for name, text in made.items():
        with open(os.path.join(args.out, name), "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
    if args.list_file:
        attach = [files[role] for role in ROLES if role in files]
        attach += [os.path.join(args.out, name) for name in ("sciforge-release.json", "SHA256SUMS.txt")]
        with open(args.list_file, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("".join(path + "\n" for path in attach))
    print("[SciForge] release files for %s written to %s: %s" % (args.tag, args.out, ", ".join(made)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
