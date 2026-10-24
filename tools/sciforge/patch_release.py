#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
"""The checks of a patch release, and the full release it is built on (docs/sciforge/patch-release.md).

A patch release ships a new SciForge module without the hours-long build: the compiled program
(the "core", tools/sciforge/core_id.sh) must be the same as in an earlier full release, whose
installer, portable build and AppImage it reuses. Every installed SciForge with that core then
updates itself with Update now (update_core.plan: a module-only update).

  tools/sciforge/patch_release.py --releases FILE --version V --core ID [--github-output FILE]
                                  [--dry-run]

--releases  GitHub's list of releases as JSON (`gh api repos/OWNER/NAME/releases --paginate`)
--version   the patch's version (src/Mod/SciForge/VERSION)
--core      this commit's core id

Checks that the version is not released yet and is newer than every release (else no SciForge
would offer it), then picks the base: the newest published release whose sciforge-release.json
has the same core and all four files (installer, portable, AppImage, quick update). Prints the
base's tag; --github-output gets base_tag, base_version, base_portable, base_appimage (the
base's file names) and new_portable, new_appimage (the patch's names: the version in them
changed). Fails with a plain sentence otherwise. --dry-run: a version that is already released
or not newer is only a warning (a trial run of the workflow publishes nothing).

The choosing is pure (choose_base, unit tested: SciForgeTests/unit/test_patch_release.py); the
command line downloads each candidate's sciforge-release.json.
"""

import argparse
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, "src", "Mod", "SciForge"))
from sciforge import version_core  # noqa: E402  (pure Python, no FreeCAD)

MANIFEST = "sciforge-release.json"
FULL_ROLES = ("installer", "portable", "appimage", "module")


class PatchError(Exception):
    """A reason the patch cannot go out, in a sentence for Luca."""


def same_core(a, b):
    """Core ids are short git hashes; two abbreviations of one commit can differ in length."""
    a, b = str(a or "").strip().lower(), str(b or "").strip().lower()
    if not a or not b:
        return False
    return a.startswith(b) or b.startswith(a)


def releases_of(data):
    """[(version, tag, {asset name: download address})] of the published SciForge releases."""
    found = []
    for entry in data if isinstance(data, list) else []:
        if not isinstance(entry, dict) or entry.get("draft"):
            continue
        tag = entry.get("tag_name")
        version = version_core.canonical(tag) if isinstance(tag, str) else None
        if not version or version_core.tag_for(version) != tag:
            continue
        assets = {}
        for asset in entry.get("assets") or []:
            if isinstance(asset, dict) and asset.get("name") and asset.get("browser_download_url"):
                assets[asset["name"]] = asset["browser_download_url"]
        found.append((version, tag, assets))
    return found


def check_version(version, releases):
    """PatchError unless ``version`` is a version, not released yet and newer than every release."""
    canonical = version_core.canonical(version)
    if not canonical:
        raise PatchError("src/Mod/SciForge/VERSION (%r) is not a version like 0.1.0-beta.2.1" % version)
    for other, tag, _assets in releases:
        if other == canonical:
            raise PatchError(
                "%s is already released (%s): put the next number in src/Mod/SciForge/VERSION, "
                "for example %s.1" % (canonical, tag, canonical)
            )
        if not version_core.newer(canonical, other):
            raise PatchError(
                "%s is not newer than the release %s: SciForge would not offer it. Use a higher "
                "number in src/Mod/SciForge/VERSION" % (canonical, other)
            )
    return canonical


def choose_base(releases, manifests, core):
    """(version, tag, {role: file name}) of the newest release with the same core and all four
    files, by its sciforge-release.json (``manifests``: {tag: parsed JSON or None}); None when
    there is none."""
    best = None
    for version, tag, assets in releases:
        manifest = manifests.get(tag)
        if not isinstance(manifest, dict) or not same_core(manifest.get("core"), core):
            continue
        roles = manifest.get("assets") or {}
        if not all(roles.get(role) in assets for role in FULL_ROLES):
            continue
        if best is None or version_core.newer(version, best[0]):
            best = (version, tag, {role: roles[role] for role in FULL_ROLES})
    return best


def renamed(name, base_version, version, suffix):
    """The patch's file name for the base's ``name`` (its ``suffix`` cut off): the version in it
    changed (SciForge_v0.1.0-beta.2-Linux-x86_64-py311 -> SciForge_v0.1.0-beta.2.1-Linux-...)."""
    stem = name[: -len(suffix)] if suffix and name.endswith(suffix) else name
    old = "_v%s-" % base_version
    if old in stem:
        return stem.replace(old, "_v%s-" % version, 1)
    return "SciForge_v%s-%s" % (version, stem.split("-", 1)[1] if "-" in stem else stem)


def _fetch_manifest(url):
    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            return json.loads(response.read(1024 * 1024).decode("utf-8"))
    except Exception:
        return None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--releases", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--core", required=True)
    parser.add_argument("--github-output", default="")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        with open(args.releases, "r", encoding="utf-8") as handle:
            text = handle.read()
        # `gh api --paginate` prints one JSON list per page, back to back
        data, decoder, at = [], json.JSONDecoder(), 0
        while at < len(text):
            while at < len(text) and text[at].isspace():
                at += 1
            if at >= len(text):
                break
            page, at = decoder.raw_decode(text, at)
            data += page if isinstance(page, list) else []
        releases = releases_of(data)
        try:
            version = check_version(args.version, releases)
        except PatchError as exc:
            version = version_core.canonical(args.version)
            if not (args.dry_run and version):
                raise
            print("::warning::(trial run, nothing is published) %s" % exc)
        manifests = {
            tag: _fetch_manifest(assets[MANIFEST]) for _v, tag, assets in releases if MANIFEST in assets
        }
        base = choose_base(releases, manifests, args.core)
        if base is None:
            raise PatchError(
                "no full release has the compiled part this commit has (core %s): the program "
                "itself changed since the last full release, so this needs the full build "
                "(Actions > SciForge build, started by a tag), not a patch" % args.core
            )
    except PatchError as exc:
        print("::error::%s" % exc)
        print("[SciForge] patch release: %s" % exc, file=sys.stderr)
        return 1
    base_version, base_tag, names = base
    outputs = {
        "base_tag": base_tag,
        "base_version": base_version,
        "base_portable": names["portable"],
        "base_appimage": names["appimage"],
        "new_portable": renamed(names["portable"], base_version, version, ".7z"),
        "new_appimage": renamed(names["appimage"], base_version, version, ".AppImage") + ".AppImage",
    }
    print("[SciForge] patch %s on %s (same compiled part, core %s)" % (version, base_tag, args.core))
    for key, value in outputs.items():
        print("  %s=%s" % (key, value))
    if args.github_output:
        with open(args.github_output, "a", encoding="utf-8") as handle:
            handle.write("".join("%s=%s\n" % item for item in outputs.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
