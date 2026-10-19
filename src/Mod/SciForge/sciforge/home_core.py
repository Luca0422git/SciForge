# SPDX-License-Identifier: LGPL-2.1-or-later
"""The Home tab's recent designs, without Qt or FreeCAD (unit tested:
SciForgeTests/unit/test_home_core.py). home_ui.py shows them.

The list is one JSON file, <user data>/SciForge/home/recent.json:

    {"version": 1, "merged_mru": true, "entries": [
        {"key": "3f2a...", "path": "D:/NAS/SciForge/Arm.FCStd", "location_id": "local",
         "rel": "Robots/Arm.FCStd", "name": "Arm", "last_opened": 1760870000.0,
         "pinned": false}, ...]}

A design is remembered by its place ("location_id", the project folder "local" for now; the
clouds and NAS of milestone M2 later) and its path inside it ("rel"): the same cloud folder
sits at another drive letter on another computer, and the design is still found. "path" is
where it was last seen, for designs outside every place.

Thumbnails are the PNG FreeCAD stores in a design, copied once into
<user data>/SciForge/home/thumbs/ so Home draws them without opening every design (a NAS
over Wi-Fi). A file the cloud app keeps online only is never read for its picture: reading
it would download it (Windows marks it with file attributes).
"""

import hashlib
import json
import os
import time

from . import versions

VERSION = 1
CAP = 50  # designs remembered (pinned ones always stay)
LOCAL = "local"  # the place "This computer": the project folder

# Windows file attributes of a file a cloud app keeps online only (os.stat st_file_attributes)
FILE_ATTRIBUTE_OFFLINE = 0x1000
FILE_ATTRIBUTE_RECALL_ON_OPEN = 0x40000
FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS = 0x400000
ONLINE_ONLY = (
    FILE_ATTRIBUTE_OFFLINE | FILE_ATTRIBUTE_RECALL_ON_OPEN | FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS
)

OK = "ok"
MISSING = "missing"
ONLINE = "online_only"


# -- the file --------------------------------------------------------------------------
def empty():
    return {"version": VERSION, "merged_mru": False, "entries": []}


def _clean_entry(raw):
    """An entry as read from the file, or None when it is not one (a hand-edited file)."""
    if not isinstance(raw, dict):
        return None
    path = raw.get("path")
    if not isinstance(path, str) or not path:
        return None
    try:
        last = float(raw.get("last_opened") or 0.0)
    except (TypeError, ValueError):
        last = 0.0
    return {
        "key": str(raw.get("key") or versions.path_key(path)),
        "path": path,
        "location_id": str(raw.get("location_id") or ""),
        "rel": str(raw.get("rel") or ""),
        "name": str(raw.get("name") or versions.design_name(path)),
        "last_opened": last,
        "pinned": bool(raw.get("pinned", False)),
    }


def load(text):
    """The list from the file's text. A broken or empty file gives an empty list (Home must
    open anyway), never an error."""
    state = empty()
    try:
        data = json.loads(text) if text else {}
    except ValueError:
        return state
    if not isinstance(data, dict):
        return state
    state["merged_mru"] = bool(data.get("merged_mru", False))
    entries = data.get("entries")
    for raw in entries if isinstance(entries, list) else []:
        entry = _clean_entry(raw)
        if entry is not None and find(state, entry["key"]) is None:
            state["entries"].append(entry)
    return state


def dump(state):
    return json.dumps(
        {
            "version": VERSION,
            "merged_mru": bool(state.get("merged_mru")),
            "entries": state.get("entries", []),
        },
        indent=1,
    )


# -- places ----------------------------------------------------------------------------
def place_of(path, places):
    """(location id, path inside it with "/") of the place holding `path`, or ("", "").
    places: {location id: root folder}."""
    for location_id, root in places.items():
        if root and versions.inside(root, path) and not versions.same_path(root, path):
            rel = os.path.relpath(os.path.abspath(path), os.path.abspath(root))
            return location_id, rel.replace(os.sep, "/")
    return "", ""


def resolve(entry, places):
    """Where the design is on this computer: inside its place when that place is known
    here, else where it was last seen."""
    root = places.get(entry.get("location_id") or "")
    if root and entry.get("rel"):
        return os.path.normpath(os.path.join(root, *entry["rel"].split("/")))
    return entry["path"]


def remembered(path, skip_folders=()):
    """Whether opening or saving `path` belongs in the list: designs only, not SciForge's
    own copies (recovery copies, an older version opened read-only: skip_folders) nor
    the plain store's version files (<Design>.versions/)."""
    if not path or not versions.is_design(path):
        return False
    if any(folder and versions.inside(folder, path) for folder in skip_folders):
        return False
    parts = os.path.normpath(os.path.abspath(path)).split(os.sep)
    return not any(part.endswith(versions.VERSIONS_SUFFIX) for part in parts[:-1])


# -- changes ---------------------------------------------------------------------------
def find(state, key):
    for entry in state["entries"]:
        if entry["key"] == key:
            return entry
    return None


def _same(entry, key, location_id, rel):
    if entry["key"] == key:
        return True
    return bool(location_id and rel and entry["location_id"] == location_id and entry["rel"] == rel)


def record(state, path, when, places, name=None):
    """`path` was opened or saved at `when` (seconds): first in the list (pins stay),
    one entry per design, at most CAP. Returns the entry."""
    path = os.path.abspath(path)
    key = versions.path_key(path)
    location_id, rel = place_of(path, places)
    entry = None
    for old in list(state["entries"]):
        if _same(old, key, location_id, rel):
            if entry is None:
                entry = old
            else:
                state["entries"].remove(old)  # (the same design listed twice: keep one)
    if entry is None:
        entry = {"pinned": False}
        state["entries"].append(entry)
    entry.update(
        key=key,
        path=path,
        location_id=location_id,
        rel=rel,
        name=name or versions.design_name(path),
        last_opened=float(when),
    )
    _cap(state)
    return entry


def _cap(state):
    pinned = [e for e in state["entries"] if e["pinned"]]
    rest = sorted((e for e in state["entries"] if not e["pinned"]), key=lambda e: -e["last_opened"])
    keep = pinned + rest[: max(0, CAP - len(pinned))]
    state["entries"] = [e for e in state["entries"] if any(e is k for k in keep)]


def mru_paths(strings, count=None):
    """FreeCAD's own recent files (User parameter:BaseApp/Preferences/RecentFiles: MRU0 the
    newest, MRU1 ..., up to its RecentFiles count), from that group's strings."""
    numbered = []
    for name, value in strings.items():
        if name.startswith("MRU") and name[3:].isdigit() and value:
            numbered.append((int(name[3:]), value))
    numbered.sort()
    if count is not None:
        numbered = [(i, v) for i, v in numbered if i < count]
    return [value for _i, value in numbered]


def merge_mru(state, paths, when, places, skip_folders=()):
    """The first time: FreeCAD's recent files join the list (in their order, older than
    anything opened now). Later starts leave the list alone. True when it changed."""
    if state.get("merged_mru"):
        return False
    state["merged_mru"] = True
    for index, path in enumerate(paths):
        if not remembered(path, skip_folders):
            continue
        if find(state, versions.path_key(os.path.abspath(path))) is None:
            record(state, path, when - (index + 1), places)
    return True


def set_pinned(state, key, on=True):
    entry = find(state, key)
    if entry is not None:
        entry["pinned"] = bool(on)
    return entry


def forget(state, key):
    """Remove from list (the file itself stays where it is)."""
    state["entries"] = [e for e in state["entries"] if e["key"] != key]


def relocate(state, key, new_path, places):
    """Locate...: the design moved; it keeps its pin and its place in the list."""
    entry = find(state, key)
    if entry is None:
        return None
    pinned, when = entry["pinned"], entry["last_opened"]
    forget(state, key)
    moved = record(state, new_path, when, places)
    moved["pinned"] = pinned
    return moved


def clear(state):
    """Clear List: every design that is not pinned (a pin is a choice to keep it)."""
    state["entries"] = [e for e in state["entries"] if e["pinned"]]


def ordered(state):
    """Pinned designs first, each group newest first."""
    return sorted(state["entries"], key=lambda e: (not e["pinned"], -e["last_opened"]))


def matches(entry, text):
    """The search box: every word in the name or the path inside its place."""
    hay = ("%s %s" % (entry.get("name", ""), entry.get("rel", ""))).lower()
    return all(word in hay for word in str(text or "").lower().split())


# -- the files -------------------------------------------------------------------------
def is_online_only(attributes):
    """A Windows file the cloud app keeps online only (OneDrive, Google Drive and Dropbox
    "online-only" files): reading it downloads it."""
    return bool(int(attributes or 0) & ONLINE_ONLY)


def file_status(path, stat=os.stat):
    """(OK | MISSING | ONLINE, modified time or None)."""
    try:
        info = stat(path)
    except (OSError, ValueError):
        return MISSING, None
    if is_online_only(getattr(info, "st_file_attributes", 0)):
        return ONLINE, info.st_mtime
    return OK, info.st_mtime


def thumb_file(cache_dir, key, mtime):
    """The cached picture of a design as saved at `mtime` (a new save is a new file)."""
    stamp = hashlib.sha1(("%s:%r" % (key, float(mtime or 0))).encode("utf-8")).hexdigest()
    return os.path.join(cache_dir, "%s-%s.png" % (key, stamp[:12]))


def load_thumbnail(path, key, cache_dir, stat=os.stat, sidecar=None):
    """(status, mtime, PNG bytes or None) for one tile. Runs on Home's worker thread: file
    work only. The cache gets the picture once per save; older pictures of the same design
    are removed. A design kept online only shows its small sidecar picture (written beside
    it in a cloud place) when there is one."""
    status, mtime = file_status(path, stat)
    if status == ONLINE and sidecar and file_status(sidecar, stat)[0] == OK:
        try:
            with open(sidecar, "rb") as handle:
                return status, mtime, handle.read()
        except OSError:
            pass
    if status != OK:
        return status, mtime, None
    target = thumb_file(cache_dir, key, mtime)
    try:
        with open(target, "rb") as handle:
            return status, mtime, handle.read()
    except OSError:
        pass
    data = versions.thumbnail_bytes(path)
    if not data:
        return status, mtime, None
    try:
        os.makedirs(cache_dir, exist_ok=True)
        for name in os.listdir(cache_dir):
            if name.startswith(key + "-") and name != os.path.basename(target):
                try:
                    os.remove(os.path.join(cache_dir, name))
                except OSError:
                    pass
        temp = target + ".tmp"
        with open(temp, "wb") as handle:
            handle.write(data)
        os.replace(temp, target)
    except OSError:
        pass  # (no cache: the picture is still shown)
    return status, mtime, data


class VersionCounter:
    """The tiles' version counts (Home's worker thread). With a git project folder one git
    call serves every design, as for the Data Panel's badges, and is kept a few seconds;
    elsewhere the plain store's copies are counted."""

    def __init__(self, keep_seconds=5.0, clock=time.time):
        self.keep = keep_seconds
        self.clock = clock
        self._memo = {}  # project folder -> (when, {path inside it: count})

    def _counts(self, project):
        now = self.clock()
        cached = self._memo.get(project)
        if cached is not None and now - cached[0] < self.keep:
            return cached[1]
        counts = {}
        root = versions.repo_root(project)
        if root:
            counts = versions.repo_counts(root)
            if not versions.same_path(root, project):  # (the repository holds the folder)
                counts = {
                    os.path.relpath(os.path.join(root, k), project).replace(os.sep, "/"): n
                    for k, n in counts.items()
                }
        self._memo[project] = (now, counts)
        return counts

    def count(self, path, project, use_git):
        counts = None
        if use_git and project and versions.inside(project, path):
            counts = self._counts(project)
        return versions.version_count(path, project, use_git, counts)


# -- words -----------------------------------------------------------------------------
def age_text(then, now=None):
    """'just now', '5 min ago', '2 h ago', 'yesterday', '3 days ago', or the date."""
    if not then:
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


def subtitle(place_name, status, mtime, version_count=0, now=None):
    """The tile's second line: where it is and when it was last saved."""
    if status == MISSING:
        return "Not found"
    if status == ONLINE:
        return "%s, online only" % place_name if place_name else "Online only"
    words = [place_name] if place_name else []
    if mtime:
        words.append("edited " + age_text(mtime, now))
    if version_count:
        words.append("v%d" % version_count)
    return ", ".join(words)
