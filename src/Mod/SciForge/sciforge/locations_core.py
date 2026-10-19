# SPDX-License-Identifier: LGPL-2.1-or-later
"""Places: where designs live (brief home-cloud-ai.md section 3). No Qt, no FreeCAD (unit
tested: SciForgeTests/unit/test_locations_core.py); locations_ui.py shows and uses them.

A place is a folder on this computer: the project folder ("This computer", always first),
the folder a cloud app keeps in sync (Dropbox, OneDrive, Google Drive), a NAS share or any
other folder. FreeCAD only ever opens and saves files in these folders; the cloud's own app
moves them (milestone M2, "phase A"). Places are kept in <user data>/SciForge/locations.json:

    {"version": 1, "places": [{"id": "dropbox", "kind": "dropbox", "name": "Dropbox",
                               "root": "C:/Users/Luca/Dropbox/SciForge", "git": false}]}

Also here, as plain rules:
  * which version store a design gets (no git inside a folder a cloud app syncs: syncing
    many small files while git writes them breaks the repository);
  * the copies sync apps make when two computers changed one file ("conflicted copy");
  * "changed on another computer": the file on disk is not the one that was opened;
  * the note a computer leaves while a design is open on it (.sciforge/locks/), so
    another computer can say "open on LAPTOP since 14:02".
"""

import hashlib
import json
import os
import re
import time

from . import versions

VERSION = 1
LOCAL = "local"  # This computer: the project folder (not stored: from the preference)

# kind -> (name shown, kept in sync by a cloud app)
KINDS = {
    "local": ("This computer", False),
    "dropbox": ("Dropbox", True),
    "onedrive": ("OneDrive", True),
    "gdrive": ("Google Drive", True),
    "nas": ("NAS", False),
    "folder": ("Folder", False),
}
CLOUD_KINDS = {kind for kind, (_name, cloud) in KINDS.items() if cloud}
SUBFOLDER = "SciForge"  # the folder SciForge suggests inside a cloud
META = ".sciforge"  # beside the designs of a place: thumbs/, locks/ (small files sync fine)

OK = "ok"
OFFLINE = "offline"
NOTE_HOURS = 12  # an open-elsewhere note older than this is forgotten (a crash left it)


class PlaceError(ValueError):
    """A place cannot be added as asked (the message says why, in plain words)."""


# -- the list ---------------------------------------------------------------------------
def local_place(project_folder):
    return {
        "id": LOCAL,
        "kind": "local",
        "name": KINDS["local"][0],
        "root": project_folder,
        "git": True,
    }


def _clean(raw):
    if not isinstance(raw, dict):
        return None
    kind = raw.get("kind")
    root = raw.get("root")
    if kind not in KINDS or kind == "local" or not isinstance(root, str) or not root:
        return None
    return {
        "id": str(raw.get("id") or kind),
        "kind": kind,
        "name": str(raw.get("name") or KINDS[kind][0]),
        "root": root,
        "git": bool(raw.get("git", False)) and kind not in CLOUD_KINDS,
    }


def load(text):
    """The places kept (not This computer), from the file's text; a broken file gives none."""
    try:
        data = json.loads(text) if text else {}
    except ValueError:
        return []
    places = []
    for raw in data.get("places", []) if isinstance(data, dict) else []:
        place = _clean(raw)
        if place is not None and all(p["id"] != place["id"] for p in places):
            places.append(place)
    return places


def dump(places):
    kept = [p for p in places if p["kind"] != "local"]
    return json.dumps({"version": VERSION, "places": kept}, indent=1)


def all_places(project_folder, places):
    """This computer first, then the places kept."""
    return [local_place(project_folder)] + [p for p in places if p["kind"] != "local"]


def roots(project_folder, places):
    """{place id: root}: what home_core needs to keep a design per place."""
    return {p["id"]: p["root"] for p in all_places(project_folder, places)}


def find(places, place_id):
    for place in places:
        if place["id"] == place_id:
            return place
    return None


def new_id(kind, places):
    taken = {p["id"] for p in places}
    if kind not in taken:
        return kind
    n = 2
    while "%s-%d" % (kind, n) in taken:
        n += 1
    return "%s-%d" % (kind, n)


def add(places, kind, root, name=None, project_folder=None, git=False):
    """A new place (the wizard's last step). Refused, in words: an unknown kind, a folder
    that is already a place, inside one or around one (a design would belong to two)."""
    if kind not in KINDS or kind == "local":
        raise PlaceError("Unknown kind of place: %s" % kind)
    if not root:
        raise PlaceError("Choose a folder first.")
    root = os.path.normpath(os.path.abspath(root))
    others = list(places) + ([local_place(project_folder)] if project_folder else [])
    for other in others:
        if versions.same_path(other["root"], root):
            raise PlaceError("%s is already the place %s." % (root, other["name"]))
        if versions.inside(other["root"], root):
            raise PlaceError(
                "%s is inside the place %s (%s)." % (root, other["name"], other["root"])
            )
        if versions.inside(root, other["root"]):
            raise PlaceError(
                "The place %s (%s) is inside %s." % (other["name"], other["root"], root)
            )
    taken = {p["name"] for p in others}
    name = (name or "").strip() or KINDS[kind][0]
    base, n = name, 2
    while name in taken:
        name = "%s %d" % (base, n)
        n += 1
    place = {
        "id": new_id(kind, places),
        "kind": kind,
        "name": name,
        "root": root,
        "git": bool(git) and kind not in CLOUD_KINDS,
    }
    places.append(place)
    return place


def remove(places, place_id):
    """Disconnect: SciForge forgets the place; the folder and its designs stay."""
    places[:] = [p for p in places if p["id"] != place_id]


def place_of(path, all_list):
    """The place a file is in (the innermost one), or None."""
    best = None
    for place in all_list:
        if place["root"] and versions.inside(place["root"], path):
            if best is None or len(place["root"]) > len(best["root"]):
                best = place
    return best


def status(place, isdir=os.path.isdir):
    """OK, or OFFLINE when the folder is not reachable now (the cloud app not running, the
    NAS off): its designs show greyed, never an error."""
    try:
        return OK if place["root"] and isdir(place["root"]) else OFFLINE
    except (OSError, ValueError):
        return OFFLINE


# -- version stores ----------------------------------------------------------------------
def git_allowed(path, all_list, sync_roots=()):
    """Whether a design's versions may be kept with git. Never inside a folder a cloud app
    syncs (a place of a cloud kind, or a detected sync folder even when it is not a place:
    the project folder could be inside Dropbox); a NAS or other folder as its place says."""
    if any(root and versions.inside(root, path) for root in sync_roots):
        return False
    place = place_of(path, all_list)
    if place is None:
        return True
    if place["kind"] in CLOUD_KINDS:
        return False
    return place["kind"] == "local" or bool(place.get("git"))


# -- changed on another computer ----------------------------------------------------------
def fingerprint(path, stat=os.stat, sha1=versions.file_sha1):
    """What the file was when it was opened: {mtime, size, sha1}, or None (no file)."""
    try:
        info = stat(path)
    except (OSError, ValueError):
        return None
    try:
        digest = sha1(path)
    except OSError:
        digest = ""
    return {"mtime": info.st_mtime, "size": info.st_size, "sha1": digest}


def changed_since(before, path, stat=os.stat, sha1=versions.file_sha1):
    """The file on disk is no longer the one that was opened (another computer saved it and
    the sync app brought it here). Its date alone changing is not enough: the content is
    compared (a sync app can touch a file's date without changing it)."""
    if not before:
        return False
    try:
        info = stat(path)
    except (OSError, ValueError):
        return False  # gone: saving puts it back
    if info.st_size == before["size"] and info.st_mtime == before["mtime"]:
        return False
    try:
        return sha1(path) != before["sha1"]
    except OSError:
        return True


KEEP_BOTH = "keep_both"
REPLACE = "replace"
OPEN_THEIRS = "open_theirs"
CHOICES = (KEEP_BOTH, REPLACE, OPEN_THEIRS)  # the dialog's buttons; Keep both is the default


def copy_name(path, computer, exists=os.path.exists):
    """Keep both: mine is saved beside theirs as "<Name> (LAPTOP).FCStd" (a number added
    when that is taken too)."""
    folder = os.path.dirname(path)
    name = versions.design_name(path)
    label = re.sub(r"[^A-Za-z0-9 _-]", "", str(computer or "")).strip() or "this computer"
    candidate = os.path.join(folder, "%s (%s)%s" % (name, label, versions.DESIGN_SUFFIX))
    n = 2
    while exists(candidate):
        candidate = os.path.join(folder, "%s (%s %d)%s" % (name, label, n, versions.DESIGN_SUFFIX))
        n += 1
    return candidate


# -- open on another computer --------------------------------------------------------------
def _meta_file(root, path, folder, suffix):
    rel = os.path.relpath(os.path.abspath(path), os.path.abspath(root)).replace(os.sep, "/")
    stamp = hashlib.sha1(rel.lower().encode("utf-8")).hexdigest()[:8]
    return os.path.join(root, META, folder, "%s-%s%s" % (versions.design_name(path), stamp, suffix))


def note_file(root, path):
    """The note of a design inside a place: <root>/.sciforge/locks/<name>-<id>.json (the id
    keeps two designs of one name in different folders apart)."""
    return _meta_file(root, path, "locks", ".json")


def sidecar_file(root, path):
    """The small picture saved beside a design in a cloud place
    (<root>/.sciforge/thumbs/<name>-<id>.png): another computer's Home shows it without
    downloading a design its cloud app keeps online only."""
    return _meta_file(root, path, "thumbs", ".png")


def make_note(computer, user, now=None):
    return {
        "computer": str(computer or ""),
        "user": str(user or ""),
        "since": float(time.time() if now is None else now),
    }


def read_note(text):
    try:
        data = json.loads(text)
    except (TypeError, ValueError):
        return None
    if not isinstance(data, dict) or not data.get("computer"):
        return None
    try:
        data["since"] = float(data.get("since") or 0)
    except (TypeError, ValueError):
        data["since"] = 0.0
    return data


def note_blocks(note, me, now=None, hours=NOTE_HOURS):
    """Whether a note means "open on another computer right now": another computer's, and
    younger than `hours` (an older one was left by a crash). Never a hard lock: the person
    can open it anyway or read-only."""
    if not note:
        return False
    if str(note.get("computer", "")).lower() == str(me or "").lower():
        return False
    now = time.time() if now is None else now
    return 0 <= now - float(note.get("since") or 0) < hours * 3600


# -- finding the cloud folders on this computer ------------------------------------------
# Sources and uncertainties: docs/sciforge/parity/cloud.md. Every function takes what it
# reads as arguments (environment, files, registry values), so the rules are tested with
# made-up computers.
GDRIVE_MY_DRIVE = (
    "My Drive",
    "Meine Ablage",
    "Mon Drive",
    "Mi unidad",
    "Il mio Drive",
    "Meu Drive",
    "Mijn Drive",
    "Mój dysk",
)


def dropbox_info_files(env, home, windows):
    """Where the Dropbox app writes info.json (its folder's location)."""
    if windows:
        return [
            os.path.join(env[var], "Dropbox", "info.json")
            for var in ("APPDATA", "LOCALAPPDATA")
            if env.get(var)
        ]
    return [os.path.join(home, ".dropbox", "info.json")]


def dropbox_folders(info_texts):
    """[(label, folder)] from info.json texts: {"personal": {"path": ...}, "business": ...}."""
    found = []
    for text in info_texts:
        try:
            data = json.loads(text)
        except (TypeError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        for key, label in (("personal", "Dropbox"), ("business", "Dropbox (work)")):
            account = data.get(key)
            if isinstance(account, dict) and isinstance(account.get("path"), str):
                found.append((label, account["path"]))
    return found


def onedrive_folders(env, registry_folders=(), home="", listdir=os.listdir, windows=True):
    """[(label, folder)]: OneDrive's own account list (registry Accounts\\*\\UserFolder,
    passed in), then its environment variables; elsewhere ~/OneDrive*."""
    found = [(label, folder) for label, folder in registry_folders if folder]
    for var, label in (
        ("OneDriveConsumer", "OneDrive"),
        ("OneDriveCommercial", "OneDrive (work)"),
        ("OneDrive", "OneDrive"),
    ):
        if env.get(var):
            found.append((label, env[var]))
    if not windows and home:
        try:
            names = sorted(listdir(home))
        except OSError:
            names = []
        found += [("OneDrive", os.path.join(home, n)) for n in names if n.startswith("OneDrive")]
    return found


def gdrive_mount_points(per_account_json="", default_mount=""):
    """Drive for desktop's own settings (registry DriveFS: PerAccountPreferences, a JSON
    whose layout Google does not document; DefaultMountPoint set by an administrator)."""
    points = []
    try:
        data = json.loads(per_account_json) if per_account_json else {}
    except ValueError:
        data = {}

    def walk(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key == "mount_point_path" and isinstance(item, str):
                    points.append(item)
                else:
                    walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(data)
    if default_mount:
        points.append(default_mount)
    return [p if len(p) > 2 or not p.endswith(":") else p + "\\" for p in points]


def gdrive_folders(roots, listdir=os.listdir, isdir=os.path.isdir):
    """[(label, folder)]: the "My Drive" folder (its name follows the language) at the root
    of Drive for desktop's drive (G: unless taken or changed) or of a mirrored folder."""
    found = []
    for root in roots:
        try:
            names = listdir(root)
        except (OSError, ValueError):
            continue
        for name in names:
            if name in GDRIVE_MY_DRIVE and isdir(os.path.join(root, name)):
                found.append(("Google Drive", os.path.join(root, name)))
                break
    return found


def detect(dropbox=(), onedrive=(), gdrive=(), isdir=os.path.isdir):
    """What the wizard offers: [{"kind", "label", "path"}], each existing folder once."""
    offers = []
    seen = []
    for kind, pairs in (("dropbox", dropbox), ("onedrive", onedrive), ("gdrive", gdrive)):
        for label, path in pairs:
            try:
                if not path or not isdir(path):
                    continue
            except (OSError, ValueError):
                continue
            if any(versions.same_path(path, other) for other in seen):
                continue
            seen.append(path)
            offers.append({"kind": kind, "label": label, "path": os.path.normpath(path)})
    return offers


# -- the copies sync apps make ---------------------------------------------------------------
_DROPBOX = re.compile(
    r"^(?P<base>.+?) \((?P<who>.+?)'s conflicted copy(?: (?P<date>\d{4}-\d{2}-\d{2}))?"
    r"(?: \(\d+\))?\)(?P<ext>\.[^.]*)$",
    re.IGNORECASE,
)
_GDRIVE = re.compile(r"^(?P<base>.+?)(?:\s?\[Conflict\]| \(\d+\))(?P<ext>\.[^.]*)$", re.IGNORECASE)


def conflict_original(name, siblings, kind="", computer=""):
    """(original file name, the app that made the copy) when `name` is a sync app's
    conflict copy of a design, else None. siblings: the names in the same folder.
    Dropbox's names say so themselves; OneDrive adds "-COMPUTER" (only in a OneDrive place,
    the original beside it, and the name this computer's own or a typical Windows computer
    name); Google Drive's naming is not documented: "[Conflict]" or " (1)" only in
    a Google Drive place with the original beside it."""
    if not versions.is_design(name):
        return None
    lower = {s.lower() for s in siblings}
    match = _DROPBOX.match(name)
    if match:
        return match.group("base") + match.group("ext"), "dropbox"
    if kind == "onedrive":
        stem, ext = os.path.splitext(name)
        for i, char in enumerate(stem):  # (a computer's name can hold hyphens itself)
            if char != "-" or i == 0:
                continue
            original, pc = stem[:i] + ext, re.sub(r"-\d+$", "", stem[i + 1 :])
            own = bool(computer) and pc.lower() == computer.lower()
            # a Windows computer's name (DESKTOP-AB12C), not a name a person gives a
            # version ("Bracket-V2", "Arm-FINAL")
            typical = pc.isupper() and len(pc) >= 5 and any(c.isdigit() or c == "-" for c in pc)
            if (own or typical) and original.lower() in lower:
                return original, "onedrive"
    match = _GDRIVE.match(name)
    if match and kind == "gdrive":
        original = match.group("base") + match.group("ext")
        if original.lower() in lower:
            return original, "gdrive"
    return None


def conflicts_in(names, kind="", computer=""):
    """{copy name: original name} of a folder's listing."""
    found = {}
    for name in names:
        hit = conflict_original(name, names, kind, computer)
        if hit is not None:
            found[name] = hit[0]
    return found


def conflict_who(name, original):
    """Whose copy it is, for the tile ("Luca's" for Dropbox, the computer for OneDrive),
    or "" when the name does not say (Google Drive)."""
    match = _DROPBOX.match(name)
    if match:
        return "%s's" % match.group("who")
    stem, base = os.path.splitext(name)[0], os.path.splitext(original)[0]
    if stem.lower().startswith(base.lower() + "-"):
        return stem[len(base) + 1 :]
    return ""
