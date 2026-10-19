# SPDX-License-Identifier: LGPL-2.1-or-later
"""Send to Slicer (UTILITIES > MAKE > 3D Print) without Qt or FreeCAD: which slicers are
installed, the command that opens a file in one, what the print file is called and where
its copy goes. Unit tested (SciForgeTests/unit/test_slicer_core.py); export_ui.PrintDialog
is the dialog. Spec and sources: docs/sciforge/parity/insert-export.md (3D Print).

Fusion's 3D Print lists the print utilities it found on the computer, plus Custom (you point
it at the program); SciForge does the same with the slicers people use today. Detection only
looks in the usual install folders and on the PATH: no registry, nothing written, nothing
started.

Every function takes the file system as small functions (is_file, is_dir, listdir), so the
rules for Windows, Linux and macOS are all tested on any machine.
"""

import ntpath
import posixpath
import re

OTHER = "other"  # "Other... (pick the program)": Fusion's Custom print utility
FILE_ONLY = "file"  # "Save file only": Fusion's Export (no utility)
OTHER_LABEL = "Other... (pick the program)"
FILE_ONLY_LABEL = "Save file only"

NONE_FOUND = (
    "No slicer was found on this computer. Choose \"Other... (pick the program)\" and pick "
    "your slicer's program, or \"Save file only\" to save the file and open it yourself."
)
NO_PROGRAM = "Pick your slicer's program first (the … button next to Program)."

# The slicers SciForge looks for, in the order the list shows them.
#   win:     paths under Program Files / Program Files (x86) / %LOCALAPPDATA%\Programs;
#            a "<prefix>*" folder means any folder starting so (Cura puts its version in it)
#   path:    program names looked up on the PATH (Linux, macOS)
#   flatpak: Flathub ids (Linux: /var/lib/flatpak/exports/bin, ~/.local/share/...)
#   appimage: words an AppImage's file name starts with (~/Applications, ~/Downloads, ~/bin)
#   mac:     app bundles in /Applications or ~/Applications
SLICERS = [
    {
        "id": "prusaslicer",
        "name": "PrusaSlicer",
        "win": [r"Prusa3D\PrusaSlicer\prusa-slicer.exe", r"PrusaSlicer\prusa-slicer.exe"],
        "path": ["prusa-slicer", "PrusaSlicer", "prusaslicer"],
        "flatpak": ["com.prusa3d.PrusaSlicer"],
        "appimage": ["prusaslicer"],
        "mac": ["PrusaSlicer.app", "Original Prusa Drivers/PrusaSlicer.app"],
    },
    {
        "id": "bambustudio",
        "name": "Bambu Studio",
        "win": [r"Bambu Studio\bambu-studio.exe", r"BambuStudio\bambu-studio.exe"],
        "path": ["bambu-studio", "BambuStudio"],
        "flatpak": ["com.bambulab.BambuStudio"],
        "appimage": ["bambu_studio", "bambu-studio", "bambustudio"],
        "mac": ["BambuStudio.app", "Bambu Studio.app"],
    },
    {
        "id": "orcaslicer",
        "name": "OrcaSlicer",
        "win": [r"OrcaSlicer\orca-slicer.exe", r"Orca Slicer\orca-slicer.exe"],
        "path": ["orca-slicer", "OrcaSlicer", "orcaslicer"],
        "flatpak": ["io.github.softfever.OrcaSlicer", "com.orcaslicer.OrcaSlicer"],
        "appimage": ["orcaslicer", "orca-slicer", "orca_slicer"],
        "mac": ["OrcaSlicer.app"],
    },
    {
        "id": "cura",
        "name": "UltiMaker Cura",
        "win": [
            r"UltiMaker Cura*\UltiMaker-Cura.exe",
            r"Ultimaker Cura*\Ultimaker-Cura.exe",
            r"Ultimaker Cura*\Cura.exe",
        ],
        "path": ["ultimaker-cura", "UltiMaker-Cura", "cura"],
        "flatpak": ["com.ultimaker.cura"],
        "appimage": ["ultimaker-cura", "ultimaker_cura", "cura"],
        "mac": ["UltiMaker Cura.app", "Ultimaker Cura.app"],
    },
]


def slicer(slicer_id):
    for entry in SLICERS:
        if entry["id"] == slicer_id:
            return entry
    return None


def platform_key(name):
    """'win', 'mac' or 'linux' from sys.platform ('win32', 'darwin', 'linux'...)."""
    name = (name or "").lower()
    if name.startswith("win") or name.startswith("cygwin"):
        return "win"
    if name.startswith("darwin") or name == "mac":
        return "mac"
    return "linux"


def _paths(path):
    """ntpath for a Windows path (with backslashes), posixpath otherwise."""
    return ntpath if "\\" in (path or "") else posixpath


def _version_key(text):
    return tuple(int(n) for n in re.findall(r"\d+", text))


def _listdir(listdir, folder):
    try:
        return list(listdir(folder))
    except Exception:
        return []


def _win_roots(env):
    roots = []
    for key in ("ProgramW6432", "ProgramFiles", "ProgramFiles(x86)"):
        value = env.get(key) or env.get(key.upper())
        if value:
            roots.append(value)
    local = env.get("LOCALAPPDATA")
    if local:
        roots.append(ntpath.join(local, "Programs"))
    if not roots:
        roots = [r"C:\Program Files", r"C:\Program Files (x86)"]
    seen, out = set(), []
    for root in roots:
        if root.lower() not in seen:
            seen.add(root.lower())
            out.append(root)
    return out


def _win_find(entry, env, is_file, listdir):
    for root in _win_roots(env):
        for rel in entry["win"]:
            folder, exe = ntpath.split(rel)
            if folder.endswith("*"):
                prefix = folder[:-1].lower()
                names = [n for n in _listdir(listdir, root) if n.lower().startswith(prefix)]
                for name in sorted(names, key=_version_key, reverse=True):  # newest first
                    candidate = ntpath.join(root, name, exe)
                    if is_file(candidate):
                        return candidate
            else:
                candidate = ntpath.join(root, rel)
                if is_file(candidate):
                    return candidate
    return None


def _path_dirs(env, sep):
    return [d for d in (env.get("PATH") or "").split(sep) if d]


def _posix_find(entry, env, home, is_file, is_dir, listdir, mac):
    for folder in _path_dirs(env, ":"):
        for name in entry["path"]:
            candidate = posixpath.join(folder, name)
            if is_file(candidate):
                return candidate
    if mac:
        for apps in ("/Applications", posixpath.join(home, "Applications") if home else None):
            if not apps:
                continue
            for bundle in entry["mac"]:
                candidate = posixpath.join(apps, bundle)
                if is_dir(candidate):
                    return candidate
        return None
    flatpak_bins = ["/var/lib/flatpak/exports/bin"]
    if home:
        flatpak_bins.append(posixpath.join(home, ".local/share/flatpak/exports/bin"))
    for folder in flatpak_bins:
        for app_id in entry["flatpak"]:
            candidate = posixpath.join(folder, app_id)
            if is_file(candidate):
                return candidate
    if home:
        for sub in ("Applications", "Downloads", "bin", ".local/bin"):
            folder = posixpath.join(home, sub)
            names = _listdir(listdir, folder)
            hits = [
                n
                for n in names
                if n.lower().endswith(".appimage")
                and any(n.lower().startswith(word) for word in entry["appimage"])
            ]
            for name in sorted(hits, key=_version_key, reverse=True):
                candidate = posixpath.join(folder, name)
                if is_file(candidate):
                    return candidate
    return None


def find_slicers(platform, env, is_file, is_dir=None, listdir=None, home=None):
    """[(id, name, program)] of the slicers installed, in SLICERS order (each once).
    platform: sys.platform; env: the environment ({'PATH': ..., 'ProgramFiles': ...});
    is_file(path): a program that can be run; is_dir(path): a folder (macOS .app bundles);
    listdir(folder): its entries; home: the user's home folder."""
    is_dir = is_dir or (lambda p: False)
    listdir = listdir or (lambda p: [])
    env = env or {}
    key = platform_key(platform)
    found = []
    for entry in SLICERS:
        try:
            if key == "win":
                program = _win_find(entry, env, is_file, listdir)
            else:
                program = _posix_find(entry, env, home, is_file, is_dir, listdir, key == "mac")
        except Exception:
            program = None
        if program:
            found.append((entry["id"], entry["name"], program))
    return found


# -- the "Send to" list ---------------------------------------------------------------------
def send_to_entries(found):
    """[(key, label)] of the Send to drop-down: the slicers found, Other..., Save file only."""
    return [(sid, name) for sid, name, _program in found] + [
        (OTHER, OTHER_LABEL),
        (FILE_ONLY, FILE_ONLY_LABEL),
    ]


def default_target(found, remembered="", other_program=""):
    """What Send to starts at: the choice made last time (when it is still there), else the
    first slicer found, else the program picked under Other... before, else Save file only."""
    ids = [sid for sid, _name, _program in found]
    if remembered in ids or remembered == FILE_ONLY:
        return remembered
    if remembered == OTHER and other_program:
        return OTHER
    if ids:
        return ids[0]
    if other_program:
        return OTHER
    return FILE_ONLY


def program_for(target, found, other_program=""):
    """The program a Send to choice starts ('' for Save file only, or Other with none)."""
    if target == FILE_ONLY:
        return ""
    if target == OTHER:
        return (other_program or "").strip()
    for sid, _name, program in found:
        if sid == target:
            return program
    return ""


def check_program(program, is_file, is_dir=None):
    """'' when the program can be started, else what to tell the person."""
    program = (program or "").strip()
    if not program:
        return NO_PROGRAM
    if is_file(program) or (is_dir is not None and program.endswith(".app") and is_dir(program)):
        return ""
    return "The slicer program was not found: %s" % program


def launch_command(program, files, platform):
    """(program, arguments) that open the files in the slicer. A macOS .app goes through
    `open -a`; a Windows shortcut (.lnk) or batch file through `cmd /c start`, which is what
    a double click does; anything else gets the files as its arguments."""
    program = (program or "").strip()
    if not program:
        raise ValueError(NO_PROGRAM)
    files = list(files)
    key = platform_key(platform)
    lower = program.lower()
    if key == "mac" and lower.endswith(".app"):
        return "open", ["-a", program] + files
    if key == "win" and lower.endswith((".lnk", ".bat", ".cmd")):
        return "cmd", ["/c", "start", "", program] + files
    return program, files


def slicer_name(target, found, other_program=""):
    """How the dialog and the messages call the chosen slicer."""
    for sid, name, _program in found:
        if sid == target:
            return name
    if target == OTHER and other_program:
        base = _paths(other_program).basename(other_program)
        return re.sub(r"\.(exe|app|lnk|appimage|bat|cmd|sh)$", "", base, flags=re.I) or base
    return "your slicer"


# -- units and files ------------------------------------------------------------------------
def send_unit(unit, sending):
    """The unit the file is written in: a slicer always gets millimetres (every slicer works in
    mm; an STL has no unit at all, so anything else would come in the wrong size); a saved
    file keeps the Unit Type chosen."""
    return "Millimeter" if sending else unit


def print_name(design, labels):
    """The print file's name: the body's name for one body, the design's for several."""
    name = labels[0] if len(labels) == 1 else design
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", (name or "").strip()).strip(". ")
    return cleaned or "part"


def free_path(path, exists):
    """`path`, or `name-2.ext`, `name-3.ext`... when a file is there already (a copy beside
    the design never overwrites anything: a slicer saves its projects as .3mf too)."""
    if not exists(path):
        return path
    base, ext = _paths(path).splitext(path)
    n = 2
    while exists("%s-%d%s" % (base, n, ext)):
        n += 1
    return "%s-%d%s" % (base, n, ext)


def copy_folder(design_file, fallback):
    """Where 'Save a copy' puts the file: beside the design, or `fallback` (the last export
    folder or home) for a design that was never saved."""
    if design_file:
        return _paths(design_file).dirname(design_file)
    return fallback


def stale_files(entries, now, max_age_days=7):
    """Names of temporary print files old enough to delete: [(name, modified time)]."""
    limit = now - max_age_days * 86400
    return [name for name, mtime in entries if mtime < limit]
