# SPDX-License-Identifier: LGPL-2.1-or-later
"""Derive / Insert Derive without FreeCAD or Qt: what can be derived, the item keys a Derive
remembers, where its source design is, whether the source changed since, the names derived
parameters get. Unit tested (SciForgeTests/unit/test_misc_cores.py).

Fusion (sources in docs/sciforge/parity/misc.md): Derive brings bodies, sketches,
construction geometry and parameters of another saved design into this one, linked: when the
source design is saved again the Derive is out of date and an update brings the changes in.
"""

import hashlib
import os
import re

KINDS = ("component", "body", "sketch", "construction", "parameter")
GROUP_TITLES = {
    "component": "Components",
    "body": "Bodies",
    "sketch": "Sketches",
    "construction": "Construction",
    "parameter": "Parameters",
}
SEP = ":"


class DeriveError(ValueError):
    """A derive that cannot be done as asked; the message says why and what to try."""


# -- the items a Derive remembers ---------------------------------------------------------------
def item_key(kind, name):
    """ "body:Body001": the kind of item and its object (or parameter) name in the source."""
    if kind not in KINDS:
        raise DeriveError("Unknown kind of item: %r" % kind)
    if not name:
        raise DeriveError("An item needs a name.")
    return "%s%s%s" % (kind, SEP, name)


def parse_item(key):
    """(kind, name) of an item key; (None, None) for something else."""
    kind, sep, name = str(key or "").partition(SEP)
    if not sep or kind not in KINDS or not name:
        return None, None
    return kind, name


def result_map(entries):
    """{item key: destination object name} from "key=Name" strings (what a Derive stores)."""
    found = {}
    for entry in entries or []:
        key, sep, name = str(entry).rpartition("=")
        if sep and key and name:
            found[key] = name
    return found


def result_entries(mapping):
    """The stored form of result_map(), in a stable order."""
    return ["%s=%s" % (key, mapping[key]) for key in sorted(mapping)]


def plan_edit(old_keys, new_keys):
    """(added, removed, kept) item keys when a Derive's ticks change from old to new, in
    the order the new ticks list them (removed in the old order)."""
    old = list(dict.fromkeys(old_keys or []))
    new = list(dict.fromkeys(new_keys or []))
    added = [k for k in new if k not in old]
    removed = [k for k in old if k not in new]
    kept = [k for k in new if k in old]
    return added, removed, kept


def tree(rows):
    """The groups the Derive dialog shows, in Fusion's browser order: [(kind, title, [row])].
    rows: [{"kind", "name", "label", "component" (label or None), ...}]. Only groups with
    something in them are listed; within a group the rows keep the source's order."""
    groups = []
    for kind in KINDS:
        members = [r for r in rows if r.get("kind") == kind]
        if members:
            groups.append((kind, GROUP_TITLES[kind], members))
    return groups


def row_text(row):
    """What a row of the dialog says: "Body1", "Arm > Body1" (in a component), "width = 12 mm"."""
    label = row.get("label") or row.get("name") or "?"
    if row.get("component"):
        label = "%s > %s" % (row["component"], label)
    if row.get("kind") == "parameter" and row.get("value_text"):
        label = "%s = %s" % (label, row["value_text"])
    return label


def summary(keys):
    """ "2 bodies, 1 sketch and 3 parameters" for item keys (what a Derive brought in)."""
    counts = {kind: 0 for kind in KINDS}
    for key in keys or []:
        kind, _name = parse_item(key)
        if kind:
            counts[kind] += 1
    words = {
        "component": ("component", "components"),
        "body": ("body", "bodies"),
        "sketch": ("sketch", "sketches"),
        "construction": ("construction object", "construction objects"),
        "parameter": ("parameter", "parameters"),
    }
    parts = [
        "%d %s" % (counts[k], words[k][0] if counts[k] == 1 else words[k][1])
        for k in KINDS
        if counts[k]
    ]
    if not parts:
        return "nothing"
    if len(parts) == 1:
        return parts[0]
    return ", ".join(parts[:-1]) + " and " + parts[-1]


def expand(keys, items):
    """What a Derive makes for its ticked `keys`, with Fusion's structure: a ticked component
    comes with its bodies and the components inside it (at any depth), as components.
    `items`: read_source()'s items ({key: data}; a component's data names its "parent",
    "children" and "bodies" by item key). Returns (components to make, parents first;
    {item key: the component key it goes into} for what lies inside a ticked component;
    the other ticked keys, made flat as before)."""
    ticked = [k for k in keys or [] if k in items]
    chosen = {k for k in ticked if parse_item(k)[0] == "component"}

    def ancestor_ticked(key):
        parent = (items.get(key) or {}).get("parent")
        seen = set()
        while parent and parent not in seen:
            if parent in chosen:
                return True
            seen.add(parent)
            parent = (items.get(parent) or {}).get("parent")
        return False

    made, inside = [], {}

    def walk(key, parent):
        if key in made or key not in items:
            return
        made.append(key)
        if parent:
            inside[key] = parent
        data = items[key]
        for body in data.get("bodies", []):
            if body in items:
                inside[body] = key
        for child in data.get("children", []):
            walk(child, key)

    for key in ticked:
        if key in chosen and not ancestor_ticked(key):
            walk(key, None)
    flat = [k for k in ticked if k not in made and k not in inside]
    return made, inside, flat


# -- parameters ---------------------------------------------------------------------------------
_NAME = re.compile(r"^(.*?)(?:_(\d+))?$")


def unique_name(name, taken):
    """A derived parameter's name in this design: its own when free, else Fusion's numbered
    one ("width" -> "width_1", "width_2"...)."""
    taken = set(taken or ())
    if name not in taken:
        return name
    n = 1
    while "%s_%d" % (name, n) in taken:
        n += 1
    return "%s_%d" % (name, n)


# -- the source design --------------------------------------------------------------------------
def resolve_source(design_file, relative, absolute, exists=os.path.isfile):
    """The source file to read: the relative path from this design's folder first (a project
    folder moved as a whole keeps working), then the absolute path it was derived from.
    None when neither is there."""
    if relative and design_file:
        candidate = os.path.normpath(
            os.path.join(os.path.dirname(os.path.abspath(design_file)), relative)
        )
        if exists(candidate):
            return candidate
    if absolute and exists(absolute):
        return absolute
    return None


def stamp(mtime, size, digest=""):
    """What a Derive remembers of the source file it read: "mtime|size|sha1"."""
    return "%.6f|%d|%s" % (float(mtime), int(size), digest or "")


def parse_stamp(text):
    """(mtime, size, digest) of a stamp; (None, None, "") for an empty or broken one."""
    parts = str(text or "").split("|")
    if len(parts) != 3:
        return None, None, ""
    try:
        return float(parts[0]), int(parts[1]), parts[2]
    except ValueError:
        return None, None, ""


def file_digest(path, chunk=1 << 20):
    """sha1 of a file's bytes (to tell a copied, unchanged file from a newer version)."""
    sha = hashlib.sha1()
    with open(path, "rb") as handle:
        while True:
            block = handle.read(chunk)
            if not block:
                break
            sha.update(block)
    return sha.hexdigest()


def file_stamp(path):
    st = os.stat(path)
    return stamp(st.st_mtime, st.st_size, file_digest(path))


UP_TO_DATE, NEWER, MISSING, BROKEN = "up to date", "newer", "missing", "link broken"


def compare_stamp(stored, mtime, size, digest_of=None):
    """UP_TO_DATE or NEWER for a source file now at (mtime, size). A different time or size
    is only "newer" when the content differs too (`digest_of()` gives it): a project folder
    copied elsewhere has new times but the same designs. Returns (state, refreshed stamp or
    None when the stored one still holds)."""
    old_time, old_size, old_digest = parse_stamp(stored)
    if old_time is None:
        return NEWER, None  # never read: whatever is there is news
    if abs(old_time - float(mtime)) < 1e-6 and old_size == int(size):
        return UP_TO_DATE, None
    if digest_of is not None and old_digest:
        digest = digest_of()
        if digest == old_digest:
            return UP_TO_DATE, stamp(mtime, size, digest)
    return NEWER, None


def version_words(number, newest):
    """The Derive dialog's Version choice: "Latest (v5)" or "v2"."""
    if not number:
        return "Latest (v%d)" % newest if newest else "Latest"
    return "v%d" % number


def state_words(state, source_name, version=0):
    """What the dialog and the timeline say about a Derive in each state (`version`: the
    source version it was pinned to, 0 for the latest)."""
    if state == NEWER and version:
        return (
            "Out of date: this Derive uses v%d of %s and a newer version exists. Right-click "
            "the Derive in the timeline > Update Derive to take the newest."
            % (version, source_name)
        )
    if state == NEWER:
        return (
            "Out of date: %s was saved again after this Derive. Right-click the Derive in the "
            "timeline > Update Derive (or edit it and press Update)." % source_name
        )
    if state == MISSING:
        return (
            "The source design %s was not found: the derived objects keep their last shape. "
            "Keep linked designs inside the project folder and move the folder as a whole."
            % source_name
        )
    if state == BROKEN:
        return "Link broken: no longer follows %s." % source_name
    return "Up to date with %s." % source_name


def check_cycle(this_file, source_file, sources_of_source, same=None):
    """Refuse a derive that would loop: the source is this design, or the source derives
    from this design already. `sources_of_source`: files the source's own Derives read."""
    same = same or (lambda a, b: _norm(a) == _norm(b))
    if this_file and same(this_file, source_file):
        raise DeriveError("A design cannot derive from itself. Pick another design.")
    for path in sources_of_source or ():
        if this_file and path and same(path, this_file):
            raise DeriveError(
                "%s already derives from this design: a design cannot derive from a design "
                "that derives from it." % design_name(source_file)
            )


def _norm(path):
    return os.path.normcase(os.path.normpath(os.path.abspath(path or "")))


def design_name(path):
    base = re.split(r"[\\/]", str(path or ""))[-1]
    if base.lower().endswith(".fcstd"):
        base = base[:-6]
    return base


def copy_name(folder, token):
    """A hidden name beside the source for the copy a Derive reads (the source itself is
    never opened, so an open source and its unsaved changes are left alone)."""
    return os.path.join(folder, ".sciforge-derive-%s.FCStd" % re.sub(r"[^A-Za-z0-9]", "", token))
