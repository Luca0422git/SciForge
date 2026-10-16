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

    def __init__(self, number, time_iso, description, size, key, backend, current=False):
        self.number = int(number)
        self.time = time_iso or ""
        self.description = description or ""
        self.size = int(size or 0)
        self.key = key
        self.backend = backend
        self.current = bool(current)

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
    def record(self, description="", when=None):
        """Keep the design file as it is now as the next version. A file identical to the
        newest version is not copied twice (the new entry points at the same copy)."""
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
        entries.append(entry)
        data["design"] = os.path.basename(self.design)
        self._write_index(data)
        return VersionInfo(number, entry["time"], description, size, file_name, self.backend, True)

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
        out = _run_git(
            ["log", "--format=%H%x1f%aI%x1f%B%x1e", "--reverse", "--", self.rel], self.root
        )
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

    def _sizes(self, hashes):
        """{commit: size of the design's blob} in one git call."""
        if not hashes:
            return {}
        lines = "\n".join("%s:%s" % (h, self.rel) for h in hashes) + "\n"
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

    def versions(self):
        entries = self._log()
        sizes = self._sizes([h for h, _, _ in entries])
        found = []
        for i, (commit, when, message) in enumerate(entries, start=1):
            found.append(
                VersionInfo(
                    i,
                    when[:19],
                    _description_of(message),
                    sizes.get(commit, 0),
                    commit,
                    self.backend,
                )
            )
        if found:
            found[-1].current = True
        return found

    def count(self):
        try:
            return int(
                _run_git(["rev-list", "--count", "HEAD", "--", self.rel], self.root).strip() or 0
            )
        except StoreError:
            return 0

    def record(self, description="", when=None):
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
        return versions[-1]

    def extract(self, info, dest_folder, file_name=None):
        data = _run_git(["show", "%s:%s" % (info.key, self.rel)], self.root, binary=True)
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


def repo_counts(root):
    """{relative path: number of commits} for every file ever committed in the repository,
    in one git call (the Data Panel's version badges)."""
    counts = {}
    if not root:
        return counts
    try:
        out = _run_git(["log", "--format=", "--name-only", "--", "."], root)
    except StoreError:
        return counts
    for line in out.splitlines():
        line = line.strip()
        if line:
            counts[line] = counts.get(line, 0) + 1
    return counts


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


def rename_design(path, new_name):
    """Rename a design and its plain version folder together; the new path. Refuses a name
    that is taken."""
    new_name = clean_name(new_name)
    if not new_name:
        raise StoreError("Give the design a name.")
    folder = os.path.dirname(path)
    target = design_path(folder, new_name)
    if os.path.exists(target) and not same_path(target, path):
        raise StoreError("A design called %s is already in this folder." % new_name)
    os.replace(path, target)
    old_versions = os.path.join(folder, design_name(path) + VERSIONS_SUFFIX)
    if os.path.isdir(old_versions):
        new_versions = os.path.join(folder, new_name + VERSIONS_SUFFIX)
        if not os.path.exists(new_versions):
            os.replace(old_versions, new_versions)
    return target


def trash_design(path, project_folder):
    """Move a design (and its plain versions) into the project's trash folder instead of
    deleting it; the new path of the design."""
    root = (
        project_folder if project_folder and inside(project_folder, path) else os.path.dirname(path)
    )
    trash = os.path.join(root, TRASH_FOLDER)
    os.makedirs(trash, exist_ok=True)
    name = unique_name(trash, design_name(path), DESIGN_SUFFIX)
    target = os.path.join(trash, name + DESIGN_SUFFIX)
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
