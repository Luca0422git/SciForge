#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
"""Checks the user-facing documents of the GitHub page (R1 of docs/sciforge/dev/briefs/
beta-release.md):

  * every relative link and picture in README.md, CHANGELOG.md, docs/sciforge/known-issues.md,
    privacy.md, smartscreen.md and docs/sciforge/README.md points at a file or folder that exists
    in the repository, and a `#section` ending of a link to a Markdown file names a heading
    that exists there;
  * docs/sciforge/smartscreen.md has no relative links (it is pasted into every release's
    notes, where they would not work);
  * README.md carries docs/sciforge/smartscreen.md word for word between its two
    `<!-- smartscreen:begin -->` / `<!-- smartscreen:end -->` markers.

Web addresses (http, https, mailto) are not fetched.

    python3 tools/sciforge/check_links.py [--repo DIR] [FILE ...]

Prints one line per problem and exits 1 when there is one, 0 when all is well.
"""

import argparse
import os
import re
import sys

DEFAULT_FILES = [
    "README.md",
    "CHANGELOG.md",
    "docs/sciforge/README.md",
    "docs/sciforge/known-issues.md",
    "docs/sciforge/privacy.md",
    "docs/sciforge/smartscreen.md",
]
SMARTSCREEN = "docs/sciforge/smartscreen.md"
BEGIN = "<!-- smartscreen:begin -->"
END = "<!-- smartscreen:end -->"

_FENCE = re.compile(r"^\s*(```|~~~)")
_CODE_SPAN = re.compile(r"`[^`\n]*`")
_MD_LINK = re.compile(r"!?\[(?:[^\]\[]|\[[^\]]*\])*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
_HTML_ATTR = re.compile(r"""<(?:a|img|source)\b[^>]*?\b(?:href|src)\s*=\s*["']([^"']+)["']""", re.I)
_HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
_EXTERNAL = re.compile(r"^(?:[a-z][a-z0-9+.-]*:|//)", re.I)


def repo_root(start=None):
    """The repository folder: the first parent holding tools/sciforge/check_links.py."""
    here = os.path.abspath(start or os.path.dirname(__file__))
    while True:
        if os.path.isfile(os.path.join(here, "tools", "sciforge", "check_links.py")):
            return here
        parent = os.path.dirname(here)
        if parent == here:
            return None
        here = parent


def _lines_without_code(text):
    """(line number, line) of the prose lines: fenced code blocks dropped, code spans blanked."""
    fenced = False
    for number, line in enumerate(text.splitlines(), 1):
        if _FENCE.match(line):
            fenced = not fenced
            continue
        if fenced:
            continue
        yield number, _CODE_SPAN.sub("``", line)


def links(text):
    """[(line number, target)] of every link and picture in Markdown / inline HTML text."""
    found = []
    in_comment = False
    for number, line in _lines_without_code(text):
        if in_comment:
            if "-->" in line:
                in_comment = False
                line = line.split("-->", 1)[1]
            else:
                continue
        # remove whole comments, and the start of one that continues on the next lines
        line = re.sub(r"<!--.*?-->", "", line)
        if "<!--" in line:
            line = line.split("<!--", 1)[0]
            in_comment = True
        for match in _MD_LINK.finditer(line):
            found.append((number, match.group(1)))
        for match in _HTML_ATTR.finditer(line):
            found.append((number, match.group(1)))
    return found


def slug(heading):
    """GitHub's anchor for a heading: lower case, only letters, digits, - and _ kept, spaces
    become hyphens."""
    text = re.sub(r"[`*_~]", lambda m: "_" if m.group(0) == "_" else "", heading)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = text.strip().lower()
    text = re.sub(r"[^\w\- ]", "", text, flags=re.UNICODE)
    return text.replace(" ", "-")


def anchors(text):
    """The set of anchors a Markdown file offers (repeated headings get -1, -2 ...)."""
    seen, out = {}, set()
    for _number, line in _lines_without_code(text):
        match = _HEADING.match(line)
        if not match:
            continue
        base = slug(match.group(2))
        count = seen.get(base, 0)
        seen[base] = count + 1
        out.add(base if count == 0 else "%s-%d" % (base, count))
    return out


def check_file(repo, rel):
    """Problems (strings) of the links in one document."""
    problems = []
    path = os.path.join(repo, rel)
    if not os.path.isfile(path):
        return ["%s: the file does not exist" % rel]
    with open(path, "r", encoding="utf-8") as handle:
        text = handle.read()
    folder = os.path.dirname(path)
    for number, target in links(text):
        if _EXTERNAL.match(target):
            continue
        base, _hash, fragment = target.partition("#")
        base = base.split("?", 1)[0]
        if not base:
            destination = path  # a link inside this very file
        elif base.startswith("/"):
            destination = os.path.join(repo, base.lstrip("/"))
        else:
            destination = os.path.normpath(os.path.join(folder, base))
        if not os.path.exists(destination):
            problems.append("%s:%d: %s does not exist" % (rel, number, target))
            continue
        if fragment and destination.lower().endswith(".md") and os.path.isfile(destination):
            with open(destination, "r", encoding="utf-8") as handle:
                found = anchors(handle.read())
            if fragment.lower() not in found:
                problems.append("%s:%d: %s has no heading #%s" % (rel, number, target, fragment))
    if rel == SMARTSCREEN:
        for number, target in links(text):
            if not _EXTERNAL.match(target):
                problems.append(
                    "%s:%d: %s is a relative link; smartscreen.md is pasted into release "
                    "notes, use a full https:// address" % (rel, number, target)
                )
    return problems


def smartscreen_body(text):
    """smartscreen.md without its leading explanation comment, trimmed."""
    if text.lstrip().startswith("<!--"):
        text = text.split("-->", 1)[1]
    return text.strip()


def check_smartscreen_in_readme(repo):
    problems = []
    try:
        with open(os.path.join(repo, SMARTSCREEN), "r", encoding="utf-8") as handle:
            wanted = smartscreen_body(handle.read())
        with open(os.path.join(repo, "README.md"), "r", encoding="utf-8") as handle:
            readme = handle.read()
    except OSError as exc:
        return ["could not read smartscreen.md or README.md: %s" % exc]
    if BEGIN not in readme or END not in readme:
        return ["README.md: the %s / %s markers are missing" % (BEGIN, END)]
    inside = readme.split(BEGIN, 1)[1].split(END, 1)[0].strip()
    if inside != wanted:
        problems.append(
            "README.md: the text between the smartscreen markers is not docs/sciforge/"
            "smartscreen.md word for word; copy that file's text (below its first comment) there"
        )
    return problems


def check_all(repo, files=None):
    problems = []
    for rel in files or DEFAULT_FILES:
        problems.extend(check_file(repo, rel))
    if files is None:
        problems.extend(check_smartscreen_in_readme(repo))
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--repo", help="repository folder (default: found from this script)")
    parser.add_argument("files", nargs="*", help="documents to check (default: the user-facing ones)")
    args = parser.parse_args(argv)
    repo = args.repo or repo_root()
    if not repo:
        print("[SciForge] check_links: not inside the repository", file=sys.stderr)
        return 2
    problems = check_all(repo, args.files or None)
    for line in problems:
        print("[SciForge] link check: " + line)
    if problems:
        print("[SciForge] link check: %d problem(s)" % len(problems))
        return 1
    print("[SciForge] link check: all links in %d documents are fine" % len(args.files or DEFAULT_FILES))
    return 0


if __name__ == "__main__":
    sys.exit(main())
