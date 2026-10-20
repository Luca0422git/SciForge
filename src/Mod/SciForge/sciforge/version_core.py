"""SciForge's version rules in one place (pure Python, no FreeCAD, unit tested).

Versions follow semantic-versioning order:
    0.1.0-beta < 0.1.0-beta.2 < 0.1.0-beta.10 < 0.1.0-rc.1 < 0.1.0 < 0.1.1-beta
A release tag is the version with the prefix ``sciforge-v`` (``sciforge-v0.1.0-beta``). The
update check, the release notes and the About/Diagnostics/Home texts all go through here, so
"is this newer?" has exactly one answer. Nothing in this module raises: junk gives None/False.
"""

import re

TAG_PREFIX = "sciforge-v"

_PATTERN = re.compile(
    r"^(?:sciforge-v|v)?"  # a tag name or a leading v
    r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"  # pre-release: beta, beta.2, rc.1
    r"(?:\+[0-9A-Za-z.-]+)?$"  # build metadata: ignored when comparing
)


def _split(text):
    """(major, minor, patch, pre-release text or "") or None."""
    try:
        match = _PATTERN.match(text.strip())
    except Exception:
        return None
    if not match:
        return None
    major, minor, patch, pre = match.groups()
    return int(major), int(minor), int(patch), pre or ""


def parse(text):
    """A comparable key for a version or tag name, or None when it is not a version.

    Keys compare with < and ==; a final release sorts after every pre-release of it, numeric
    pre-release parts compare as numbers (beta.10 > beta.2) and sort before words."""
    parts = _split(text) if isinstance(text, str) else None
    if parts is None:
        return None
    major, minor, patch, pre = parts
    if not pre:
        return (major, minor, patch, (1,))
    identifiers = tuple((0, int(p), "") if p.isdigit() else (1, 0, p) for p in pre.split("."))
    return (major, minor, patch, (0, identifiers))


def newer(candidate, current):
    """True when ``candidate`` is a later version than ``current`` (False if either is junk)."""
    a, b = parse(candidate), parse(current)
    return a is not None and b is not None and a > b


def is_prerelease(text):
    """True for 0.1.0-beta, 0.1.0-rc.1...; False for 0.1.0 and for junk."""
    parts = _split(text) if isinstance(text, str) else None
    return bool(parts and parts[3])


def canonical(text):
    """The version without a leading v / tag prefix or build metadata, or None."""
    parts = _split(text) if isinstance(text, str) else None
    if parts is None:
        return None
    major, minor, patch, pre = parts
    return "%d.%d.%d%s" % (major, minor, patch, "-" + pre if pre else "")


def tag_for(text):
    """The release tag of a version: ``sciforge-v0.1.0-beta``; None for junk."""
    version = canonical(text)
    return TAG_PREFIX + version if version else None
