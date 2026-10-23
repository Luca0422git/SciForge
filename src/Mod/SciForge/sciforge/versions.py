# SPDX-License-Identifier: LGPL-2.1-or-later
"""Versions, recovery copies and the project folder: the part without Qt or FreeCAD.

Fusion keeps every save of a design as a numbered version (v1, v2, ...) with a description,
lets an older version be opened read-only or promoted to the newest, writes a recovery copy
of every open design every few minutes and offers it back after a crash, and lists a
project's designs with thumbnails in its Data Panel. SciForge does all of that with local
files (the project folder, typically on the owner's NAS) instead of Autodesk's cloud:

  * a version store per design: git when the design lives in the project folder and the
    git program is installed (one repository per project folder, commits of that one file;
    GitStore), otherwise a plain folder of copies beside the design, `<Design>.versions/`,
    with an `index.json` (PlainStore). The plain store always works.
  * recovery copies in `<user data>/SciForge/recovery/`, one `.FCStd` and one `.json`
    sidecar per design, written by versions_ui's autosave and cleared on a clean save or
    close; what is left over at the next start is what a crash left behind.
  * a quick summary of a saved design read from its `Document.xml` (bodies, sketches,
    features) for the version comparison, and the thumbnail FreeCAD stores in the file.

Everything here is pure Python and unit tested (SciForgeTests/unit/test_versions_core.py);
versions_ui.py puts the dialogs, the Data Panel and the timers on top.
"""

import getpass
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import zipfile

DESIGN_SUFFIX = ".FCStd"
VERSIONS_SUFFIX = ".versions"  # <Design>.versions/ beside the design (plain store)
INDEX_FILE = "index.json"
RECOVERY_FOLDER = "recovery"  # under <user data>/SciForge/
OPEN_FOLDER = "versions-open"  # read-only copies of older versions are opened from here
TRASH_FOLDER = ".sciforge-trash"  # the Data Panel's Delete moves designs here
GIT_IGNORE = "*.FCBak\n*.FCStd1\n*.versions/\n.sciforge-trash/\n"
DEFAULT_AUTOSAVE_MINUTES = 5  # Fusion's default recovery save interval (forum reports)
MIN_AUTOSAVE_MINUTES = 1  # Fusion refuses less than 5; SciForge allows 1 for small designs
MAX_AUTOSAVE_MINUTES = 120  # Fusion's maximum (two hours)
GIT_TIMEOUT = 60  # seconds for one git call (a NAS can be slow)
# Folders the Data Panel never lists.
HIDDEN_FOLDERS = {".git", TRASH_FOLDER}
# A milestone of a git version is a tag on its commit (one commit = one version of one
# design, so the tag names the version); plain copies mark it in index.json.
MILESTONE_TAG = "sciforge-milestone-"
# Commits that only move or rename a design (the Data Panel's Move, Rename): not versions.
MOVE_MESSAGE = "[SciForge] moved"
AUTO_CLOSE_DESCRIPTION = "Automatic version on close"


class StoreError(Exception):
    """A version operation that could not be done (the message is for the user)."""


# -- names and paths -------------------------------------------------------------------
def design_name(path):
    """ "Bracket" for /nas/Bracket.FCStd (also for .fcstd, and for Windows paths anywhere)."""
    base = re.split(r"[\\/]", str(path or ""))[-1]
    if base.lower().endswith(DESIGN_SUFFIX.lower()):
        base = base[: -len(DESIGN_SUFFIX)]
    return base


def is_design(path):
    return path.lower().endswith(DESIGN_SUFFIX.lower())


# -- saves FreeCAD could not finish ----------------------------------------------------------------
# FreeCAD writes a save to "<design>.FCStd.<uuid>" and renames it to the design last. On
# Windows the rename is refused while another program holds the new file: Google Drive for
# desktop backing the folder up (Luca's Documents, 2026-10-19: every save there stayed a
# "test.FCStd.78026b5d-..." and no design appeared), an antivirus. The save is complete in
# that file; finish_save() makes it the design.
TEMP_SAVE = re.compile(
    r"^(?P<design>.+\.fcstd)\.[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
UNFINISHED_FOLDER = os.path.join(".sciforge", "unfinished-saves")
FINISH = {"last_error": ""}  # why the last finish_save could not rename (for the log)


def unfinished_saves(folder):
    """{design path: [its temporary save files, newest first]} in `folder`."""
    found = {}
    try:
        names = os.listdir(folder)
    except OSError:
        return found
    for name in names:
        match = TEMP_SAVE.match(name)
        if match:
            full = os.path.join(folder, name)
            found.setdefault(os.path.join(folder, match.group("design")), []).append(full)
    for temps in found.values():
        temps.sort(key=lambda p: _mtime_or_zero(p), reverse=True)
    return found


def _mtime_or_zero(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0


def complete_save(path):
    """A design file FreeCAD finished writing (a zip with its Document.xml)."""
    try:
        with zipfile.ZipFile(path) as archive:
            return "Document.xml" in archive.namelist()
    except (OSError, zipfile.BadZipFile):
        return False


def finish_save(design, since=None, settle=0.0, now=None):
    """Make the newest temporary save of `design` the design file (the rename FreeCAD could
    not do), when it is complete, newer than the design and at least `settle` seconds old
    (one being written now is left alone); `since`: only a save started then or later.
    The older temporary files of the design go to .sciforge/unfinished-saves beside it
    (kept, never deleted). True: done; False: there is one but it could not be renamed
    yet (try again); None: nothing to finish."""
    folder = os.path.dirname(design)
    temps = unfinished_saves(folder).get(design) or []
    now = time.time() if now is None else now
    newest = None
    for temp in temps:
        stamp = _mtime_or_zero(temp)
        if since is not None and stamp < since - 2.0:
            continue
        if now - stamp < settle or not complete_save(temp):
            continue
        newest = temp
        break
    if newest is None:
        return None
    if os.path.exists(design) and _mtime_or_zero(design) >= _mtime_or_zero(newest):
        return None  # the design is newer: that temporary file is an older, finished save
    try:
        os.replace(newest, design)
    except OSError as exc:
        # The rename stays refused on some computers (Luca's Documents, Google Drive backing
        # it up: a minute later Python could not rename either) while writing a new file
        # works, as FreeCAD's own temporary file shows: the save is written under the
        # design's name instead, and the temporary file removed when allowed.
        FINISH["last_error"] = "rename refused (%s); copied instead" % exc
        try:
            shutil.copyfile(newest, design)  # (written, never renamed)
        except OSError as exc2:
            FINISH["last_error"] = "rename refused (%s), copy refused (%s)" % (exc, exc2)
            return False
        if not complete_save(design):
            FINISH["last_error"] += "; the copy is not complete"
            return False
        try:
            os.remove(newest)
        except OSError:
            pass  # (left beside the design: Home lists designs only)
        _keep_aside(folder, [t for t in temps if t != newest])
        return True
    _keep_aside(folder, [t for t in temps if t != newest])
    return True


def _keep_aside(folder, temps):
    """The older temporary saves of a design go to .sciforge/unfinished-saves (kept)."""
    for temp in temps:
        if os.path.exists(temp):
            try:
                keep = os.path.join(folder, UNFINISHED_FOLDER)
                os.makedirs(keep, exist_ok=True)
                os.replace(temp, os.path.join(keep, os.path.basename(temp)))
            except OSError:
                pass  # (stays beside the design; Home lists designs only)


# STEP / IGES files in a project folder (uploaded): the Data Panel lists them; opening one
# makes a new design of it with its components (exchange_ui.open_file).
CAD_SUFFIXES = (".step", ".stp", ".iges", ".igs")


def is_cad_file(path):
    return path.lower().endswith(CAD_SUFFIXES)


_BAD_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def clean_name(text):
    """A design or folder name that every file system takes: no path separators or the
    characters Windows refuses, no leading/trailing dots or spaces. "" when nothing is
    left (the caller then asks for a name)."""
    text = _BAD_CHARS.sub("", str(text or ""))
    text = re.sub(r"\s+", " ", text).strip(" .")
    if text.upper() in {"CON", "PRN", "AUX", "NUL"} or re.match(r"^(COM|LPT)\d$", text.upper()):
        text += "_"
    return text


def design_path(folder, name):
    """The file of a design called `name` in `folder`."""
    return os.path.join(folder, clean_name(name) + DESIGN_SUFFIX)


def unique_name(folder, base, suffix="", existing=None):
    """`base`, or "base 2", "base 3"... so that base+suffix does not exist in folder yet.
    `existing` (names in the folder) may be given instead of looking at the disk."""
    if existing is None:
        try:
            existing = set(os.listdir(folder))
        except OSError:
            existing = set()
    taken = {n.lower() for n in existing}
    if (base + suffix).lower() not in taken:
        return base
    n = 2
    while ("%s %d%s" % (base, n, suffix)).lower() in taken:
        n += 1
    return "%s %d" % (base, n)


def same_path(a, b):
    """Two paths that name the same file (case and separators as the OS sees them)."""
    if not a or not b:
        return False
    return os.path.normcase(os.path.normpath(os.path.abspath(a))) == os.path.normcase(
        os.path.normpath(os.path.abspath(b))
    )


def inside(folder, path):
    """path lies in folder (or is folder itself)."""
    if not folder or not path:
        return False
    folder = os.path.normcase(os.path.normpath(os.path.abspath(folder)))
    path = os.path.normcase(os.path.normpath(os.path.abspath(path)))
    return path == folder or path.startswith(folder.rstrip(os.sep) + os.sep)


def relative_path(base_file_or_folder, target, is_folder=False):
    """`target` relative to the folder of `base` (a file) or to `base` itself (is_folder),
    with forward slashes, like FreeCAD writes external links into a design. None when the
    two are on different drives (Windows) and no relative path exists."""
    folder = base_file_or_folder if is_folder else os.path.dirname(base_file_or_folder)
    try:
        rel = os.path.relpath(os.path.abspath(target), os.path.abspath(folder))
    except ValueError:
        return None
    return rel.replace(os.sep, "/")


def resolve_relative(base_file, relative):
    """The file a relative link of `base_file` points at."""
    return os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(base_file)), relative))


def path_key(path):
    """A short stable id of a file path (for recovery copies and fallback stores)."""
    norm = os.path.normcase(os.path.normpath(os.path.abspath(path))) if path else ""
    return hashlib.sha1(norm.encode("utf-8", "replace")).hexdigest()[:10]


def human_size(size):
    size = float(size or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return ("%d %s" % (size, unit)) if unit == "B" else ("%.1f %s" % (size, unit))
        size /= 1024.0
    return "%.1f GB" % size


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())


def pretty_time(iso):
    """2026-10-13T14:05:09 -> "2026-10-13 14:05"; other text is passed through."""
    try:
        parsed = time.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S")
        return time.strftime("%Y-%m-%d %H:%M", parsed)
    except (ValueError, TypeError):
        return str(iso or "")


# -- safe file writing -----------------------------------------------------------------
def atomic_write_text(path, text):
    """Write a text file so that a crash half way never leaves a broken file (temp + rename)."""
    folder = os.path.dirname(path) or "."
    os.makedirs(folder, exist_ok=True)
    handle, tmp = tempfile.mkstemp(prefix=".sf-", suffix=".tmp", dir=folder)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as out:
            out.write(text)
        os.replace(tmp, path)
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def atomic_copy(src, dst):
    """Copy a file so the target is either the old file or the whole new one, never half."""
    folder = os.path.dirname(dst) or "."
    os.makedirs(folder, exist_ok=True)
    handle, tmp = tempfile.mkstemp(prefix=".sf-", suffix=".tmp", dir=folder)
    os.close(handle)
    try:
        shutil.copyfile(src, tmp)
        os.replace(tmp, dst)
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def writable_folder(folder):
    """Can files be made in `folder` (making it if needed)? A read-only share says no."""
    try:
        os.makedirs(folder, exist_ok=True)
        handle, tmp = tempfile.mkstemp(prefix=".sf-", suffix=".probe", dir=folder)
        os.close(handle)
        os.remove(tmp)
        return True
    except OSError:
        return False


def file_sha1(path, chunk=1 << 20):
    digest = hashlib.sha1()
    with open(path, "rb") as handle:
        while True:
            block = handle.read(chunk)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


# -- one version -------------------------------------------------------------------------
class VersionInfo:
    """One saved version. `number` is what the user sees (v1, v2...); `key` is what the
    store needs to find it again (a file name or a commit hash)."""

    def __init__(
        self, number, time_iso, description, size, key, backend, current=False, milestone=False
    ):
        self.number = int(number)
        self.time = time_iso or ""
        self.description = description or ""
        self.size = int(size or 0)
        self.key = key
        self.backend = backend
        self.current = bool(current)
        self.milestone = bool(milestone)  # Fusion's milestone: a version marked as one

    @property
    def label(self):
        return "v%d" % self.number

    def as_dict(self):
        return {
            "number": self.number,
            "time": self.time,
            "description": self.description,
            "size": self.size,
            "key": self.key,
            "backend": self.backend,
            "current": self.current,
            "milestone": self.milestone,
        }

    def __repr__(self):
        return "VersionInfo(%s %s %r)" % (self.label, self.time, self.description)


# -- the plain store: copies in <Design>.versions/ -----------------------------------------
class PlainStore:
    """Every version a copy `v0001.FCStd`... beside the design, listed in index.json.

    When the design's folder cannot be written (a read-only share, a CD) the copies go to
    `fallback_root/<key>-<name>/` instead (versions_ui passes <user data>/SciForge/versions)
    and `self.fallback` says so, so the user can be told."""

    backend = "copy"

    def __init__(self, design_file, fallback_root=None):
        self.design = os.path.abspath(design_file)
        self.name = design_name(self.design)
        beside = os.path.join(os.path.dirname(self.design), self.name + VERSIONS_SUFFIX)
        self.fallback = False
        if os.path.isdir(beside) or writable_folder(os.path.dirname(self.design)):
            self.folder = beside
        elif fallback_root:
            self.folder = os.path.join(fallback_root, "%s-%s" % (path_key(self.design), self.name))
            self.fallback = True
        else:
            self.folder = beside

    # index
    def _index_path(self):
        return os.path.join(self.folder, INDEX_FILE)

    def read_index(self):
        """{"design": ..., "versions": [...]} ; a missing or broken index is rebuilt from the
        copies that are there (their descriptions are then lost, nothing else)."""
        path = self._index_path()
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, dict) and isinstance(data.get("versions"), list):
                return data
        except (OSError, ValueError):
            pass
        rebuilt = {"design": os.path.basename(self.design), "versions": []}
        try:
            files = sorted(f for f in os.listdir(self.folder) if re.match(r"^v\d+\.FCStd$", f))
        except OSError:
            return rebuilt
        if os.path.isfile(path):
            try:  # keep the broken index for inspection, do not throw it away
                os.replace(path, path + ".broken-%d" % int(time.time()))
            except OSError:
                pass
        for name in files:
            full = os.path.join(self.folder, name)
            rebuilt["versions"].append(
                {
                    "number": int(name[1:-6]),
                    "time": time.strftime(
                        "%Y-%m-%dT%H:%M:%S", time.localtime(os.path.getmtime(full))
                    ),
                    "description": "",
                    "size": os.path.getsize(full),
                    "file": name,
                }
            )
        return rebuilt

    def _write_index(self, data):
        atomic_write_text(self._index_path(), json.dumps(data, indent=1, ensure_ascii=False))

    def versions(self):
        """All versions, oldest first; the newest is marked current."""
        entries = self.read_index()["versions"]
        found = []
        for e in entries:
            try:
                found.append(
                    VersionInfo(
                        e["number"],
                        e.get("time"),
                        e.get("description"),
                        e.get("size"),
                        e["file"],
                        self.backend,
                        milestone=bool(e.get("milestone")),
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
        found.sort(key=lambda v: v.number)
        if found:
            found[-1].current = True
        return found

    def count(self):
        return len(self.read_index()["versions"])

    # changes
    def record(self, description="", when=None, milestone=False):
        """Keep the design file as it is now as the next version. A file identical to the
        newest version is not copied twice (the new entry points at the same copy).
        milestone: the version is a milestone (the Save dialog's Milestone box)."""
        if not os.path.isfile(self.design):
            raise StoreError("The design file %s is not there to be versioned." % self.design)
        data = self.read_index()
        entries = data["versions"]
        number = max([e.get("number", 0) for e in entries] + [0]) + 1
        size = os.path.getsize(self.design)
        sha = file_sha1(self.design)
        file_name = "v%04d%s" % (number, DESIGN_SUFFIX)
        last = entries[-1] if entries else None
        if (
            last
            and last.get("sha1") == sha
            and os.path.isfile(os.path.join(self.folder, last["file"]))
        ):
            file_name = last["file"]
        else:
            atomic_copy(self.design, os.path.join(self.folder, file_name))
        entry = {
            "number": number,
            "time": when or now_iso(),
            "description": description or "",
            "size": size,
            "file": file_name,
            "sha1": sha,
            "by": _user(),
        }
        if milestone:
            entry["milestone"] = True
        entries.append(entry)
        data["design"] = os.path.basename(self.design)
        self._write_index(data)
        return VersionInfo(
            number, entry["time"], description, size, file_name, self.backend, True, milestone
        )

    def set_milestone(self, info, on=True):
        """Mark version `info` as a milestone (or not)."""
        data = self.read_index()
        for entry in data["versions"]:
            if entry.get("number") == info.number:
                if on:
                    entry["milestone"] = True
                else:
                    entry.pop("milestone", None)
                self._write_index(data)
                return True
        raise StoreError("%s was not found in the version list." % info.label)

    def path_of(self, info):
        return os.path.join(self.folder, info.key)

    def extract(self, info, dest_folder, file_name=None):
        """Copy version `info` to dest_folder (as "<Name> v3.FCStd" by default); the path."""
        src = self.path_of(info)
        if not os.path.isfile(src):
            raise StoreError("The copy of %s is missing (%s)." % (info.label, src))
        dest = os.path.join(
            dest_folder, file_name or "%s %s%s" % (self.name, info.label, DESIGN_SUFFIX)
        )
        atomic_copy(src, dest)
        return dest

    def promote(self, info, description=""):
        """Make version `info` the newest: its copy replaces the design file (whole or not at
        all) and is recorded as the next version."""
        src = self.path_of(info)
        if not os.path.isfile(src):
            raise StoreError("The copy of %s is missing (%s)." % (info.label, src))
        atomic_copy(src, self.design)
        return self.record(description or "Promoted %s" % info.label)


def _user():
    try:
        return getpass.getuser()
    except Exception:
        return ""


# -- the git store: one repository per project folder --------------------------------------
def _run_git(args, cwd, binary=False, stdin_text=None):
    """git with the arguments, in cwd; stdout (text unless binary). Raises StoreError with
    git's own words when it fails. No console window on Windows."""
    git = git_program()
    if not git:
        raise StoreError("The git program is not installed.")
    kwargs = {"cwd": cwd, "timeout": GIT_TIMEOUT}
    if stdin_text is not None:
        kwargs["input"] = stdin_text.encode("utf-8")
    else:
        kwargs["stdin"] = subprocess.DEVNULL
    if hasattr(subprocess, "CREATE_NO_WINDOW"):  # Windows: no flashing console
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    try:
        result = subprocess.run(
            [git] + list(args),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            **kwargs,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise StoreError("git could not run: %s" % exc)
    if result.returncode != 0:
        err = result.stderr.decode("utf-8", "replace").strip()
        raise StoreError("git %s failed: %s" % (args[0], err or "unknown error"))
    return result.stdout if binary else result.stdout.decode("utf-8", "replace")


_GIT = {"path": None, "looked": False}


def git_program():
    """The git executable, or None. Looked up once (shutil.which) per session."""
    if not _GIT["looked"]:
        _GIT["path"] = shutil.which("git")
        _GIT["looked"] = True
    return _GIT["path"]


def git_available():
    return bool(git_program())


def repo_root(folder):
    """The top folder of the git repository `folder` is in, or None."""
    if not folder or not os.path.isdir(folder) or not git_available():
        return None
    try:
        top = _run_git(["rev-parse", "--show-toplevel"], folder).strip()
    except StoreError:
        return None
    return os.path.normpath(top) if top else None


def init_repo(folder):
    """Make `folder` a git repository (nothing if it is one). The .gitignore keeps
    FreeCAD's backup files and SciForge's own folders out."""
    os.makedirs(folder, exist_ok=True)
    if repo_root(folder) is None:
        _run_git(["init", "-q"], folder)
    ignore = os.path.join(folder, ".gitignore")
    if not os.path.isfile(ignore):
        atomic_write_text(ignore, GIT_IGNORE)
    return folder


def _identity_args():
    user = _user() or "SciForge"
    return ["-c", "user.name=%s" % user, "-c", "user.email=%s@sciforge.local" % user]


class GitStore:
    """Versions of one design as the commits that touched its file in the project folder's
    repository. The description is the commit message; the version number counts the
    commits of that file from the first."""

    backend = "git"

    def __init__(self, design_file, root):
        self.design = os.path.abspath(design_file)
        self.name = design_name(self.design)
        self.root = os.path.normpath(root)
        if not inside(self.root, self.design):
            raise StoreError("%s is not inside the repository %s" % (self.design, self.root))
        self.rel = os.path.relpath(self.design, self.root).replace(os.sep, "/")

    def _log(self):
        """[(commit, date, message, path)] oldest first: the commits of the design's file,
        followed back through SciForge's own moves and renames (the Data Panel's Move and
        Rename commit a git mv with MOVE_MESSAGE), without those move commits. `path` is the
        file's path in the repository at that commit. (git's own --follow also follows a
        copy with the same content: a copied design would have taken the original's
        versions.)"""
        found = []  # newest first
        path, rev = self.rel, "HEAD"
        for _hop in range(64):
            out = _run_git(["log", "--format=%x1e%H%x1f%aI%x1f%B", rev, "--", path], self.root)
            records = parse_log(out)
            if not records:
                break
            found.extend((c, w, m, path) for c, w, m in records)
            oldest = records[-1]
            if not oldest[2].startswith(MOVE_MESSAGE):
                break
            before = self._moved_from(oldest[0], path)
            if not before:
                break
            path, rev = before, oldest[0] + "^"
        found.reverse()
        self._paths = {commit: where for commit, _w, _m, where in found}
        return [r for r in found if not r[2].startswith(MOVE_MESSAGE)]

    def _moved_from(self, commit, path):
        """The path the design had before the move commit `commit` renamed it to `path`."""
        try:
            out = _run_git(["show", "--format=", "--name-status", "-M", commit], self.root)
        except StoreError:
            return None
        for line in out.splitlines():
            cols = line.split("\t")
            if cols[0].startswith("R") and len(cols) >= 3 and cols[2].strip() == path:
                return cols[1].strip()
        return None

    def _path_at(self, commit):
        """The design file's path in the repository at `commit`."""
        paths = getattr(self, "_paths", None)
        if paths is None or commit not in paths:
            self._log()
            paths = self._paths
        return paths.get(commit, self.rel)

    def _sizes(self, hashes):
        """{commit: size of the design's blob} in one git call."""
        if not hashes:
            return {}
        lines = "\n".join("%s:%s" % (h, self._path_at(h)) for h in hashes) + "\n"
        try:
            out = _run_git(["cat-file", "--batch-check=%(objectsize)"], self.root, stdin_text=lines)
        except StoreError:
            return {}
        sizes = {}
        for h, line in zip(hashes, out.splitlines()):
            try:
                sizes[h] = int(line.strip())
            except ValueError:
                sizes[h] = 0
        return sizes

    def _milestones(self):
        """Commits marked as milestones (tags MILESTONE_TAG + commit)."""
        try:
            out = _run_git(["tag", "--list", MILESTONE_TAG + "*"], self.root)
        except StoreError:
            return set()
        return {t.strip()[len(MILESTONE_TAG) :] for t in out.splitlines() if t.strip()}

    def versions(self):
        entries = self._log()
        sizes = self._sizes([h for h, _w, _m, _p in entries])
        marked = self._milestones() if entries else set()
        found = []
        for i, (commit, when, message, _path) in enumerate(entries, start=1):
            found.append(
                VersionInfo(
                    i,
                    when[:19],
                    _description_of(message),
                    sizes.get(commit, 0),
                    commit,
                    self.backend,
                    milestone=commit in marked,
                )
            )
        if found:
            found[-1].current = True
        return found

    def count(self):
        try:
            return len(self._log())
        except StoreError:
            return 0

    def set_milestone(self, info, on=True):
        """Mark version `info` as a milestone (a tag on its commit), or take the mark off."""
        tag = MILESTONE_TAG + info.key
        if on:
            _run_git(["tag", "-f", tag, info.key], self.root)
        else:
            try:
                _run_git(["tag", "-d", tag], self.root)
            except StoreError:
                pass  # not marked: nothing to take off
        return True

    def record(self, description="", when=None, milestone=False):
        if not os.path.isfile(self.design):
            raise StoreError("The design file %s is not there to be versioned." % self.design)
        _run_git(["add", "--", self.rel], self.root)
        message = description.strip() if description else ""
        if not message:
            message = "Save"
        _run_git(
            _identity_args()
            + ["commit", "-q", "--allow-empty", "-m", message, "--only", "--", self.rel],
            self.root,
        )
        versions = self.versions()
        if not versions:
            raise StoreError("git recorded nothing for %s" % self.rel)
        newest = versions[-1]
        if milestone:
            self.set_milestone(newest, True)
            newest.milestone = True
        return newest

    def extract(self, info, dest_folder, file_name=None):
        data = _run_git(
            ["show", "%s:%s" % (info.key, self._path_at(info.key))], self.root, binary=True
        )
        os.makedirs(dest_folder, exist_ok=True)
        dest = os.path.join(
            dest_folder, file_name or "%s %s%s" % (self.name, info.label, DESIGN_SUFFIX)
        )
        handle, tmp = tempfile.mkstemp(prefix=".sf-", suffix=".tmp", dir=dest_folder)
        with os.fdopen(handle, "wb") as out:
            out.write(data)
        os.replace(tmp, dest)
        return dest

    def promote(self, info, description=""):
        folder = os.path.dirname(self.design)
        tmp = self.extract(info, folder, ".sf-promote-%s.tmp" % path_key(self.design))
        os.replace(tmp, self.design)
        return self.record(description or "Promoted %s" % info.label)


def _description_of(message):
    """The commit message as the version description ("Save" means none was given)."""
    text = (message or "").strip()
    return "" if text == "Save" else text


def parse_log(out):
    """[(commit, date, message)] from `git log --format=%x1e%H%x1f%aI%x1f%B` (as git lists
    them: newest first)."""
    found = []
    for record in out.split("\x1e"):
        record = record.strip("\n\r ")
        if not record:
            continue
        parts = record.split("\x1f")
        if len(parts) < 3:
            continue
        found.append((parts[0].strip(), parts[1].strip(), parts[2].strip()))
    return found


def count_versions(log_text):
    """{path: number of versions} from `git log --reverse -M --format=%x1e%s --name-status
    -- .`: every commit that touches a file is one version of it, a rename carries the
    count to the new path, and a commit that only moved a file (MOVE_MESSAGE) adds none."""
    counts = {}
    for record in log_text.split("\x1e"):
        lines = [line for line in record.splitlines() if line.strip()]
        if not lines:
            continue
        subject, changes = lines[0], lines[1:]
        moving = subject.startswith(MOVE_MESSAGE)
        for line in changes:
            cols = line.split("\t")
            status = cols[0].strip()
            if status.startswith("R") and len(cols) >= 3:
                old, new = cols[1].strip(), cols[2].strip()
                counts[new] = counts.pop(old, 0) + (0 if moving else 1)
            elif status.startswith("C") and len(cols) >= 3:
                counts[cols[2].strip()] = counts.get(cols[2].strip(), 0) + 1
            elif status.startswith("D") and len(cols) >= 2:
                if moving:
                    counts.pop(cols[1].strip(), None)
            elif len(cols) >= 2 and not moving:
                counts[cols[1].strip()] = counts.get(cols[1].strip(), 0) + 1
    return {k: v for k, v in counts.items() if v > 0}


def repo_counts(root):
    """{relative path: number of versions} for every file of the repository, in one git
    call (the Data Panel's version badges); moves and renames carry their count along."""
    if not root:
        return {}
    try:
        out = _run_git(
            ["log", "--reverse", "-M", "--format=%x1e%s", "--name-status", "--", "."], root
        )
    except StoreError:
        return {}
    return count_versions(out)


# -- choosing the store ------------------------------------------------------------------
def store_for(design_file, project_folder=None, use_git=True, fallback_root=None, notes=None):
    """The version store of a design: git when the design is inside the project folder, git
    is installed and wanted (the project folder is made a repository the first time);
    otherwise plain copies beside the design. `notes` (a list) collects what was decided
    in words, for the log."""
    notes = notes if notes is not None else []
    design_file = os.path.abspath(design_file)
    if use_git and project_folder and inside(project_folder, design_file):
        if not git_available():
            notes.append("git is not installed: versions are kept as copies")
        else:
            try:
                root = repo_root(project_folder)
                if root is None or not inside(root, project_folder):
                    init_repo(project_folder)
                    root = project_folder
                    notes.append("made the project folder %s a git repository" % project_folder)
                return GitStore(design_file, root)
            except StoreError as exc:
                notes.append("git cannot be used here (%s): versions are kept as copies" % exc)
    store = PlainStore(design_file, fallback_root)
    if store.fallback:
        notes.append(
            "the folder of %s cannot be written: its versions are kept in %s"
            % (os.path.basename(design_file), store.folder)
        )
    return store


def version_count(design_file, project_folder=None, use_git=True, repo_counts_cache=None):
    """How many versions a design has, cheaply (for the Data Panel's badges). With a git
    project folder, pass repo_counts(root) as the cache so one git call serves all files."""
    design_file = os.path.abspath(design_file)
    if (
        use_git
        and project_folder
        and inside(project_folder, design_file)
        and repo_counts_cache is not None
    ):
        rel = os.path.relpath(design_file, project_folder).replace(os.sep, "/")
        n = repo_counts_cache.get(rel, 0)
        if n:
            return n
    try:
        return PlainStore(design_file).count()
    except Exception:
        return 0


# -- recovery copies ---------------------------------------------------------------------
def recovery_folder(user_dir):
    return os.path.join(user_dir, "SciForge", RECOVERY_FOLDER)


def recovery_key(doc_name, file_name):
    """The id of a design's recovery copy: by its file when saved, by its name when not."""
    return path_key(file_name) if file_name else "unsaved-" + clean_name(doc_name).replace(" ", "_")


def recovery_paths(folder, key):
    """(copy file, sidecar json) of a recovery entry."""
    return os.path.join(folder, key + DESIGN_SUFFIX), os.path.join(folder, key + ".json")


def write_recovery_sidecar(folder, key, label, file_name, session):
    """Who the copy belongs to: the design's name, its file (or "" when never saved), when
    it was written and which SciForge session wrote it."""
    _, side = recovery_paths(folder, key)
    atomic_write_text(
        side,
        json.dumps(
            {
                "label": label,
                "file_name": file_name or "",
                "saved": now_iso(),
                "session": session,
            },
            indent=1,
            ensure_ascii=False,
        ),
    )


def list_recovery(folder, other_than_session=None):
    """The recovery entries in `folder` (dicts with key, label, file_name, saved, session,
    copy, size), newest first; those of `other_than_session` left out (the running session's
    own copies are not "unsaved work from a crash")."""
    found = []
    try:
        names = os.listdir(folder)
    except OSError:
        return found
    for name in sorted(names):
        if not name.lower().endswith(DESIGN_SUFFIX.lower()):
            continue
        key = name[: -len(DESIGN_SUFFIX)]
        copy, side = recovery_paths(folder, key)
        entry = {
            "key": key,
            "label": design_name(name),
            "file_name": "",
            "saved": "",
            "session": "",
        }
        try:
            with open(side, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, dict):
                for k in ("label", "file_name", "saved", "session"):
                    if data.get(k):
                        entry[k] = str(data[k])
        except (OSError, ValueError):
            pass
        if other_than_session and entry["session"] == other_than_session:
            continue
        try:
            entry["size"] = os.path.getsize(copy)
            if not entry["saved"]:
                entry["saved"] = time.strftime(
                    "%Y-%m-%dT%H:%M:%S", time.localtime(os.path.getmtime(copy))
                )
        except OSError:
            continue
        entry["copy"] = copy
        found.append(entry)
    found.sort(key=lambda e: e["saved"], reverse=True)
    return found


def recovery_session(folder, key):
    """The session that wrote a recovery entry ("" when unknown: no sidecar)."""
    _, side = recovery_paths(folder, key)
    try:
        with open(side, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return str(data.get("session", "")) if isinstance(data, dict) else ""
    except (OSError, ValueError):
        return ""


def discard_recovery(folder, key):
    """Remove one recovery entry (both files); True when something was removed."""
    removed = False
    for path in recovery_paths(folder, key):
        try:
            os.remove(path)
            removed = True
        except OSError:
            pass
    return removed


def discard_session_recovery(folder, session):
    """Remove every recovery entry a session wrote (a clean quit)."""
    for entry in list_recovery(folder):
        if entry["session"] == session:
            discard_recovery(folder, entry["key"])


def new_session_id():
    return "%d-%s" % (os.getpid(), hashlib.sha1(str(time.time()).encode()).hexdigest()[:6])


# -- what is in a saved design (no FreeCAD needed) -----------------------------------------
_OBJECT_TAG = re.compile(r'<Object\s+type="([^"]+)"\s+name="([^"]+)"')
_PROP_STRING = r'<Property\s+name="%s"[^>]*>\s*<String\s+value="([^"]*)"'
BODY_TYPES = {"PartDesign::Body"}
SKETCH_TYPES = {"Sketcher::SketchObject", "Sketcher::SketchObjectPython"}
PLUMBING_PREFIXES = ("App::Origin", "App::Line", "App::Plane", "App::Point", "App::VarSet")


def summary(design_file):
    """Counts read from Document.xml: objects, bodies, sketches, features (everything in a
    body that is not plumbing), plus label, last modified and the file size. A file that is
    not a FreeCAD design gives {"error": ...}."""
    result = {
        "file": design_file,
        "size": 0,
        "bodies": 0,
        "sketches": 0,
        "features": 0,
        "objects": 0,
    }
    try:
        result["size"] = os.path.getsize(design_file)
        with zipfile.ZipFile(design_file) as zf:
            xml = zf.read("Document.xml").decode("utf-8", "replace")
            result["thumbnail"] = "thumbnails/Thumbnail.png" in zf.namelist()
    except (OSError, zipfile.BadZipFile, KeyError) as exc:
        result["error"] = str(exc)
        return result
    types = {}
    for type_id, _name in _OBJECT_TAG.findall(xml):
        types[type_id] = types.get(type_id, 0) + 1
        result["objects"] += 1
        if type_id in BODY_TYPES:
            result["bodies"] += 1
        elif type_id in SKETCH_TYPES:
            result["sketches"] += 1
        elif type_id.startswith("PartDesign::") or type_id.startswith("Part::"):
            result["features"] += 1
    result["types"] = types
    for name in ("Label", "LastModifiedDate", "LastModifiedBy"):
        match = re.search(_PROP_STRING % re.escape(name), xml, re.S)
        if match:
            result[name[0].lower() + name[1:]] = _unescape(match.group(1))
    return result


def _unescape(text):
    return (
        text.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&amp;", "&")
    )


COMPARE_ROWS = [
    ("bodies", "Bodies"),
    ("sketches", "Sketches"),
    ("features", "Features"),
    ("objects", "Objects in the file"),
    ("volume", "Total volume (mm^3)"),
    ("size", "File size"),
    ("lastModifiedDate", "Last saved"),
]


def compare(a, b):
    """Rows (title, value of a, value of b, changed) for two summaries (volume only when
    both have it: versions_ui adds it after loading the files in FreeCAD)."""
    rows = []
    for key, title in COMPARE_ROWS:
        if key not in a and key not in b:
            continue
        va, vb = a.get(key), b.get(key)
        if key == "size":
            text_a, text_b = human_size(va), human_size(vb)
        elif key == "volume":
            text_a = "%.2f" % va if isinstance(va, (int, float)) else "?"
            text_b = "%.2f" % vb if isinstance(vb, (int, float)) else "?"
        elif key == "lastModifiedDate":
            text_a, text_b = pretty_time(va or ""), pretty_time(vb or "")
        else:
            text_a, text_b = str(va if va is not None else "?"), str(vb if vb is not None else "?")
        if key == "volume" and isinstance(va, (int, float)) and isinstance(vb, (int, float)):
            changed = abs(va - vb) > 1e-6 * max(1.0, abs(va), abs(vb))
        else:
            changed = va != vb
        rows.append((title, text_a, text_b, changed))
    return rows


def thumbnail_bytes(design_file):
    """The PNG FreeCAD stores in a design (preference Document/SaveThumbnail), or None."""
    try:
        with zipfile.ZipFile(design_file) as zf:
            return zf.read("thumbnails/Thumbnail.png")
    except (OSError, zipfile.BadZipFile, KeyError):
        return None


# -- the project folder (Data Panel) -------------------------------------------------------
def list_folder(folder):
    """(folders, designs) of a project folder, each sorted by name. Folders: dicts with name,
    path. Designs: dicts with name, path, size, modified (ISO). SciForge's and git's own
    folders and FreeCAD's backup files are left out."""
    folders, designs = [], []
    try:
        names = os.listdir(folder)
    except OSError:
        return folders, designs
    for name in sorted(names, key=str.lower):
        full = os.path.join(folder, name)
        if os.path.isdir(full):
            if name in HIDDEN_FOLDERS or name.startswith(".") or name.endswith(VERSIONS_SUFFIX):
                continue
            folders.append({"name": name, "path": full})
        elif is_design(name) or is_cad_file(name):
            try:
                stat = os.stat(full)
            except OSError:
                continue
            cad = is_cad_file(name)
            designs.append(
                {
                    "name": name if cad else design_name(name),
                    "path": full,
                    "size": stat.st_size,
                    "modified": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(stat.st_mtime)),
                    "cad": cad,
                }
            )
    return folders, designs


def breadcrumbs(project_folder, folder):
    """[(label, path)] from the project folder down to `folder` ("Project" first)."""
    crumbs = [("Project", os.path.abspath(project_folder))]
    if not inside(project_folder, folder) or same_path(project_folder, folder):
        return crumbs
    rel = os.path.relpath(os.path.abspath(folder), os.path.abspath(project_folder))
    current = os.path.abspath(project_folder)
    for part in rel.split(os.sep):
        if part in ("", "."):
            continue
        current = os.path.join(current, part)
        crumbs.append((part, current))
    return crumbs


def new_folder(parent, base="New Folder"):
    """Make "New Folder" (or "New Folder 2"...) in parent; the path."""
    name = unique_name(parent, clean_name(base) or "New Folder")
    path = os.path.join(parent, name)
    os.makedirs(path)
    return path


def rename_design(path, new_name, project_folder=None, use_git=True):
    """Rename a design and its plain version folder together; the new path. Refuses a name
    that is taken. In a git project folder the rename is recorded as a move (git mv), so
    the versions follow the new name."""
    new_name = clean_name(new_name)
    if not new_name:
        raise StoreError("Give the design a name.")
    folder = os.path.dirname(path)
    target = design_path(folder, new_name)
    if os.path.exists(target) and not same_path(target, path):
        raise StoreError("A design called %s is already in this folder." % new_name)
    users = referrers(path, project_folder) if project_folder else []
    _relocate(path, target, project_folder, use_git, None)
    for other in users:  # the designs that insert or derive it follow the new name
        try:
            here = os.path.dirname(other)
            xml, n = retarget_xml(read_design_xml(other), here, here, path, target)
            if n:
                write_design_xml(other, xml)
        except Exception:
            continue
    return target


# -- Move and Copy of designs (the Data Panel) -----------------------------------------
_XLINK_FILE = re.compile(r'(<XLink\b[^>]*?\bfile=")([^"]*)(")')
_DERIVE_PATH = re.compile(
    r'(<Property\s+name="(SourceRelative|SourceFile)"\s+type="App::PropertyString"[^>]*>\s*'
    r'<String\s+value=")([^"]*)(")'
)
# An inserted design's component keeps the other design's file name, relative to this
# design's folder, beside the XLinks of its copies (design_insert.LINKED_FILE).
_LINKED_FILE_PATH = re.compile(
    r'(<Property\s+name="SciForgeLinkedFile"\s+type="App::PropertyString"[^>]*>\s*'
    r'<String\s+value=")([^"]*)(")'
)


def _xml_unescape(text):
    return (
        text.replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&apos;", "'")
        .replace("&amp;", "&")
    )


def _xml_escape(text):
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


def link_targets(xml, holder_dir):
    """The other designs a design's Document.xml refers to: its links (FreeCAD's XLink,
    stored relative to the design's folder) and its Derives' sources, as absolute paths."""
    found = []
    for match in _XLINK_FILE.finditer(xml):
        value = _xml_unescape(match.group(2))
        if value:
            found.append(os.path.normpath(os.path.join(holder_dir, value)))
    for match in _DERIVE_PATH.finditer(xml):
        value = _xml_unescape(match.group(3))
        if not value:
            continue
        if match.group(2) == "SourceFile":
            found.append(os.path.normpath(value))
        else:
            found.append(os.path.normpath(os.path.join(holder_dir, value)))
    return found


def retarget_xml(xml, old_dir, new_dir, moved_from=None, moved_to=None):
    """A design's Document.xml with its references to other designs kept pointing at the
    same files when the design goes from folder `old_dir` to `new_dir`, and at `moved_to`
    where they pointed at `moved_from` (a referenced design that moved). Links are stored
    relative to the design's folder (as FreeCAD does), a Derive's SourceFile absolute and
    its SourceRelative relative. Returns (xml, number of references changed)."""
    changed = [0]

    def target_of(path):
        if moved_from and same_path(path, moved_from):
            return os.path.normpath(moved_to)
        return path

    def relative(target):
        try:
            return os.path.relpath(target, new_dir).replace(os.sep, "/")
        except ValueError:
            return None  # another drive (Windows): keep what was there

    def xlink(match):
        value = _xml_unescape(match.group(2))
        if not value:
            return match.group(0)
        rel = relative(target_of(os.path.normpath(os.path.join(old_dir, value))))
        if rel is None or rel == value:
            return match.group(0)
        changed[0] += 1
        return match.group(1) + _xml_escape(rel) + match.group(3)

    def derive(match):
        value = _xml_unescape(match.group(3))
        if not value:
            return match.group(0)
        if match.group(2) == "SourceFile":
            new = target_of(os.path.normpath(value))
            if same_path(new, value):
                return match.group(0)
        else:
            new = relative(target_of(os.path.normpath(os.path.join(old_dir, value))))
            if new is None or new == value:
                return match.group(0)
        changed[0] += 1
        return match.group(1) + _xml_escape(new) + match.group(4)

    def linked_file(match):
        # follows the XLinks of the same component: not counted as a reference of its own
        value = _xml_unescape(match.group(2))
        if not value:
            return match.group(0)
        rel = relative(target_of(os.path.normpath(os.path.join(old_dir, value))))
        if rel is None or rel == value:
            return match.group(0)
        return match.group(1) + _xml_escape(rel) + match.group(3)

    xml = _XLINK_FILE.sub(xlink, xml)
    xml = _DERIVE_PATH.sub(derive, xml)
    xml = _LINKED_FILE_PATH.sub(linked_file, xml)
    return xml, changed[0]


def read_design_xml(path):
    with zipfile.ZipFile(path) as zf:
        return zf.read("Document.xml").decode("utf-8")


def write_design_xml(path, xml):
    """Put a new Document.xml into a design file (whole or not at all)."""
    folder = os.path.dirname(path) or "."
    handle, tmp = tempfile.mkstemp(prefix=".sf-", suffix=".tmp", dir=folder)
    os.close(handle)
    try:
        with zipfile.ZipFile(path) as src, zipfile.ZipFile(tmp, "w") as dst:
            for item in src.infolist():
                data = src.read(item.filename)
                if item.filename == "Document.xml":
                    data = xml.encode("utf-8")
                dst.writestr(item, data)
        os.replace(tmp, path)
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def designs_in(folder):
    """Every design file under `folder` (not in .git, the trash or version folders)."""
    found = []
    for root, dirs, files in os.walk(folder):
        dirs[:] = [
            d
            for d in dirs
            if d not in HIDDEN_FOLDERS and not d.startswith(".") and not d.endswith(VERSIONS_SUFFIX)
        ]
        found.extend(os.path.join(root, f) for f in files if is_design(f))
    return found


def referrers(path, folder):
    """The designs under `folder` that refer to the design `path` (links, Derives)."""
    found = []
    for other in designs_in(folder):
        if same_path(other, path):
            continue
        try:
            xml = read_design_xml(other)
        except Exception:
            continue
        if any(same_path(t, path) for t in link_targets(xml, os.path.dirname(other))):
            found.append(other)
    return found


def _git_root_for(path, project_folder, use_git):
    if not use_git or not project_folder or not inside(project_folder, path):
        return None
    if not git_available():
        return None
    root = repo_root(project_folder)
    return root if root is not None and inside(root, path) else None


def _tracked(root, rel):
    try:
        return bool(_run_git(["ls-files", "--", rel], root).strip())
    except StoreError:
        return False


def _relocate(path, target, project_folder, use_git, fallback_root):
    """Move a design file and its plain versions; in a git project folder with git mv and a
    move commit (not a version), so its versions follow it."""
    old_store = PlainStore(path, fallback_root)
    root = _git_root_for(path, project_folder, use_git)
    rel_old = os.path.relpath(path, root).replace(os.sep, "/") if root else None
    if root and inside(root, target) and _tracked(root, rel_old):
        rel_new = os.path.relpath(target, root).replace(os.sep, "/")
        os.makedirs(os.path.dirname(target), exist_ok=True)
        _run_git(["mv", "--", rel_old, rel_new], root)
        _run_git(
            _identity_args()
            + [
                "commit",
                "-q",
                "-m",
                "%s %s to %s" % (MOVE_MESSAGE, rel_old, rel_new),
                "--only",
                "--",
                rel_old,
                rel_new,
            ],
            root,
        )
    else:
        os.replace(path, target)
    if os.path.isdir(old_store.folder):
        new_store = PlainStore(target, fallback_root)
        if not os.path.exists(new_store.folder):
            os.makedirs(os.path.dirname(new_store.folder), exist_ok=True)
            os.replace(old_store.folder, new_store.folder)


def move_design(path, dest_folder, project_folder=None, use_git=True, fallback_root=None):
    """The Data Panel's Move: the design goes to `dest_folder` with its versions; its own
    links and Derives keep pointing at the same designs, and the designs of the project
    that refer to it are pointed at its new place. Returns (new path, [designs updated]).
    Refuses (StoreError) a name taken in the destination."""
    path = os.path.abspath(path)
    dest_folder = os.path.abspath(dest_folder)
    if not os.path.isfile(path):
        raise StoreError("The design %s is not there." % path)
    if same_path(os.path.dirname(path), dest_folder):
        raise StoreError("%s is in that folder already." % design_name(path))
    target = os.path.join(dest_folder, os.path.basename(path))
    if os.path.exists(target):
        raise StoreError(
            "A design called %s is already in %s."
            % (design_name(path), os.path.basename(dest_folder))
        )
    users = referrers(path, project_folder) if project_folder else []
    _relocate(path, target, project_folder, use_git, fallback_root)
    try:
        xml, n = retarget_xml(read_design_xml(target), os.path.dirname(path), dest_folder)
        if n:
            write_design_xml(target, xml)
    except Exception:
        pass  # a file FreeCAD did not write: it moves as it is
    updated = []
    for other in users:
        try:
            folder = os.path.dirname(other)
            xml, n = retarget_xml(read_design_xml(other), folder, folder, path, target)
            if n:
                write_design_xml(other, xml)
                updated.append(other)
        except Exception:
            continue
    return target, updated


def copy_design(path, dest_folder):
    """The Data Panel's Copy: a separate design in `dest_folder` (its own versions start at
    v1, recorded by the caller); its links and Derives still point at the same designs.
    A name taken there gets a number ("Bracket 2"). Returns the new path."""
    path = os.path.abspath(path)
    dest_folder = os.path.abspath(dest_folder)
    if not os.path.isfile(path):
        raise StoreError("The design %s is not there." % path)
    name = unique_name(dest_folder, design_name(path), DESIGN_SUFFIX)
    target = os.path.join(dest_folder, name + DESIGN_SUFFIX)
    atomic_copy(path, target)
    try:
        xml, n = retarget_xml(read_design_xml(target), os.path.dirname(path), dest_folder)
        if n:
            write_design_xml(target, xml)
    except Exception:
        pass
    return target


def project_folders(project_folder):
    """[(label, path)] of the project folder and every folder in it, for the Move / Copy
    dialog: "Project", "Project / Robots", "Project / Robots / Arm"..."""
    found = [("Project", os.path.abspath(project_folder))]
    for root, dirs, _files in os.walk(project_folder):
        dirs[:] = sorted(
            (
                d
                for d in dirs
                if d not in HIDDEN_FOLDERS
                and not d.startswith(".")
                and not d.endswith(VERSIONS_SUFFIX)
            ),
            key=str.lower,
        )
        for d in dirs:
            full = os.path.join(root, d)
            rel = os.path.relpath(full, project_folder).replace(os.sep, " / ")
            found.append(("Project / " + rel, full))
    return found[:1] + sorted(found[1:], key=lambda row: row[0].lower())


def trash_design(path, project_folder):
    """Move a design (and its plain versions) into the trash folder of `project_folder` (the
    place it is in; a design outside it: a trash folder beside it) instead of deleting it;
    the new path of the design. A STEP / IGES file keeps its extension."""
    root = (
        project_folder if project_folder and inside(project_folder, path) else os.path.dirname(path)
    )
    trash = os.path.join(root, TRASH_FOLDER)
    os.makedirs(trash, exist_ok=True)
    if is_design(path):
        base, suffix = design_name(path), DESIGN_SUFFIX
    else:  # an uploaded STEP / IGES file keeps its own extension
        base, suffix = os.path.splitext(os.path.basename(path))
    name = unique_name(trash, base, suffix)
    target = os.path.join(trash, name + suffix)
    os.replace(path, target)
    versions = os.path.join(os.path.dirname(path), design_name(path) + VERSIONS_SUFFIX)
    if os.path.isdir(versions):
        try:
            os.replace(versions, os.path.join(trash, name + VERSIONS_SUFFIX))
        except OSError:
            pass
    return target


def clamp_minutes(value):
    try:
        value = int(value)
    except (TypeError, ValueError):
        return DEFAULT_AUTOSAVE_MINUTES
    return max(MIN_AUTOSAVE_MINUTES, min(MAX_AUTOSAVE_MINUTES, value))
