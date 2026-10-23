# SPDX-License-Identifier: LGPL-2.1-or-later
"""The Data Panel's logic without Qt or FreeCAD: searching a place, sorting the cards, the
words on a card, what a drag may do, and a design's Uses / Used In. Unit tested
(SciForgeTests/unit/test_data_panel_core.py); data_panel_ui.py draws the panel.

Fusion's Data Panel (sources in docs/sciforge/parity/versions.md, "Data Panel, part 2"):
cards with the design's picture and its version number, folders first; a search box;
sorting by name or by when a design was last changed; a grid and a list view; a design's
details with its versions (newest first), "Uses" (the designs it inserts) and "Used In"
(the designs that insert it); a design dragged from the panel into the open design goes
in (SciForge: as an independent copy, Luca's request 2026-10-23); dragging a card onto a
folder moves it.
"""

import os
import time

from . import versions as store

# A design dragged out of the panel carries its file in this format (and as a file URL,
# so other programs see a file), one path per line.
MIME = "application/x-sciforge-design"

SORTS = (
    ("name", "Name"),
    ("modified", "Last saved"),
    ("size", "Size"),
)
DEFAULT_SORT = "name"
SEARCH_LIMIT = 200  # results a search lists at most (a NAS folder can hold thousands)


# -- sorting -------------------------------------------------------------------------------------
def sort_key_name(entry):
    return (entry.get("name") or "").lower()


def sort_entries(folders, designs, key=DEFAULT_SORT):
    """(folders, designs) in the panel's order: folders always first and by name (as in
    Fusion); designs by name, newest first ("Last saved") or biggest first ("Size"), then
    by name."""
    folders = sorted(folders, key=sort_key_name)
    if key == "modified":
        designs = sorted(designs, key=sort_key_name)
        designs = sorted(designs, key=lambda d: d.get("modified") or "", reverse=True)
    elif key == "size":
        designs = sorted(designs, key=sort_key_name)
        designs = sorted(designs, key=lambda d: d.get("size") or 0, reverse=True)
    else:
        designs = sorted(designs, key=sort_key_name)
    return folders, designs


def sort_name(key):
    for k, label in SORTS:
        if k == key:
            return label
    return SORTS[0][1]


def known_sort(key):
    return key if key in [k for k, _label in SORTS] else DEFAULT_SORT


# -- searching -----------------------------------------------------------------------------------
def words(query):
    return [w for w in (query or "").lower().split() if w]


def matches(name, query):
    """Every word of the query is in the name (any order, any case)."""
    found = words(query)
    text = (name or "").lower()
    return bool(found) and all(w in text for w in found)


def search(root, query, limit=SEARCH_LIMIT):
    """(folders, designs, more) under `root` whose name matches the query, in every folder
    of the place (not .git, the trash or version folders). Entries are those of
    versions.list_folder plus "where": the folder they are in, relative to `root` ("" at
    the top). `more` is True when the limit cut the list."""
    folders, designs = [], []
    if not words(query) or not root or not os.path.isdir(root):
        return folders, designs, False
    more = False
    for here, dirs, _files in os.walk(root):
        dirs[:] = sorted(
            (
                d
                for d in dirs
                if d not in store.HIDDEN_FOLDERS
                and not d.startswith(".")
                and not d.endswith(store.VERSIONS_SUFFIX)
            ),
            key=str.lower,
        )
        where = os.path.relpath(here, root)
        where = "" if where in (".", "") else where.replace(os.sep, " / ")
        found_folders, found_designs = store.list_folder(here)
        for entry in found_folders:
            if matches(entry["name"], query):
                folders.append(dict(entry, where=where))
        for entry in found_designs:
            if matches(entry["name"], query):
                designs.append(dict(entry, where=where))
        if len(folders) + len(designs) > limit:
            more = True
            break
    folders = folders[:limit]
    designs = designs[: max(0, limit - len(folders))]
    return folders, designs, more


# -- the words on a card -------------------------------------------------------------------------
def card_text(name, version_count=0, conflict=False):
    """The card's text as the panel lists it ("Arm  v2"): tests and screen readers read it;
    the card itself draws the name and the badge apart."""
    text = name + (("  v%d" % version_count) if version_count else "")
    if conflict:
        text += "  (conflict)"
    return text


def badge(version_count):
    """The version badge in the picture's corner ("V3"), "" for a file without versions."""
    return ("V%d" % version_count) if version_count else ""


def _epoch(iso):
    try:
        return time.mktime(time.strptime((iso or "")[:19], "%Y-%m-%dT%H:%M:%S"))
    except (ValueError, TypeError, OverflowError):
        return None


def age(iso, now=None):
    """'just now', '5 min ago', '2 h ago', 'yesterday', '3 days ago', or the date."""
    then = _epoch(iso)
    if then is None:
        return ""
    now = time.time() if now is None else now
    seconds = max(0.0, now - then)
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return "%d min ago" % (seconds // 60)
    if seconds < 86400:
        return "%d h ago" % (seconds // 3600)
    days = int(seconds // 86400)
    if days == 1:
        return "yesterday"
    if days < 7:
        return "%d days ago" % days
    return time.strftime("%Y-%m-%d", time.localtime(then))


def subtitle(design, now=None, where=None):
    """The card's second line: when it was saved and its size; in search results also the
    folder it is in ("in Robots / Arm")."""
    parts = []
    if where is not None:
        parts.append(("in " + where) if where else "in the top folder")
    when = age(design.get("modified"), now)
    if when:
        parts.append(when)
    if design.get("cad"):
        parts.append("STEP / IGES file")
    parts.append(store.human_size(design.get("size") or 0))
    return " · ".join(parts)


def tooltip(design, version_count=0):
    return "%s\n%s, last saved %s%s" % (
        design["path"],
        store.human_size(design.get("size") or 0),
        store.pretty_time(design.get("modified") or ""),
        (
            (", %d version%s" % (version_count, "" if version_count == 1 else "s"))
            if version_count
            else ""
        ),
    )


def status_text(folders, designs, query=None, more=False):
    if query:
        n = len(folders) + len(designs)
        if not n:
            return 'Nothing called "%s" in this place.' % query.strip()
        return '%d found for "%s"%s' % (n, query.strip(), " (the first ones)" if more else "")
    return "%d folder%s, %d design%s" % (
        len(folders),
        "" if len(folders) == 1 else "s",
        len(designs),
        "" if len(designs) == 1 else "s",
    )


# -- dragging ------------------------------------------------------------------------------------
def encode_paths(paths):
    return "\n".join(os.path.abspath(p) for p in paths if p)


def decode_paths(text):
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


def move_target(paths, folder):
    """The designs of `paths` a drop onto the folder card `folder` moves there: designs and
    STEP / IGES files not in it already (a folder never moves into itself)."""
    found = []
    for path in paths:
        if not path or not folder:
            continue
        if store.same_path(os.path.dirname(os.path.abspath(path)), folder):
            continue
        if store.is_design(path) or store.is_cad_file(path):
            found.append(path)
    return found


def insertable(path):
    """A design dragged onto an open design can go in (a FreeCAD design file)."""
    return bool(path) and store.is_design(path) and os.path.isfile(path)


def upload_kind(path):
    """What Upload (or a file dropped on the panel from outside) does with a file: "design"
    (a SciForge / FreeCAD design, copied in), "cad" (STEP / IGES, copied in, opens as a new
    design), None (not taken)."""
    if not path:
        return None
    if store.is_design(path):
        return "design"
    if store.is_cad_file(path):
        return "cad"
    return None


def upload_target(folder, path, exists=os.path.exists):
    """Where an uploaded file goes in `folder`: its name, or "Name 2", "Name 3"... when
    taken."""
    base, ext = os.path.splitext(os.path.basename(path))
    target = os.path.join(folder, base + ext)
    n = 1
    while exists(target):
        n += 1
        target = os.path.join(folder, "%s %d%s" % (base, n, ext))
    return target


# -- details: Uses and Used In -------------------------------------------------------------------
def uses(path, xml):
    """The designs `path` (its Document.xml given) inserts or derives from: [(name, path,
    found)] in file order, each once."""
    found, seen = [], set()
    for target in store.link_targets(xml, os.path.dirname(os.path.abspath(path))):
        key = os.path.normcase(os.path.normpath(target))
        if key in seen or store.same_path(target, path):
            continue
        seen.add(key)
        found.append((store.design_name(target), target, os.path.isfile(target)))
    return found


def used_in(path, root):
    """The designs in the place `root` that insert or derive from `path`: [(name, path)]."""
    return sorted(
        ((store.design_name(p), p) for p in store.referrers(path, root)),
        key=lambda row: row[0].lower(),
    )


def version_row(info, now=None):
    """A line of the details' version list: "V3  2 h ago  longer arm"."""
    when = age(info.time, now) or store.pretty_time(info.time)
    text = "V%d  %s" % (info.number, when)
    if info.description:
        text += "  " + info.description
    if info.milestone:
        text += "  ⚑"
    return text
