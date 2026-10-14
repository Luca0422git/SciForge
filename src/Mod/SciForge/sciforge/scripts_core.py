# SPDX-License-Identifier: LGPL-2.1-or-later
"""Scripts and Add-Ins without FreeCAD or Qt: what is in the scripts and add-ins folders, the
names a new one may have, the files Create writes, the Run on Startup list. Unit tested
(SciForgeTests/unit/test_misc_cores.py); scripts_ui.py is the dialog.

Fusion (sources in docs/sciforge/parity/misc.md): a script runs once when Run is pressed; an
add-in is loaded (its run() is called) and stays until Stop (its stop()); either can be set to
run when the program starts. SciForge's scripts are FreeCAD macros (the macro folder);
SciForge's add-ins are folders with a Python file of the same name that defines run() and
stop(), like Fusion's (the code inside uses FreeCAD's API, not Fusion's).
"""

import os
import re

SCRIPT_EXTENSIONS = (".FCMacro", ".py")
SCRIPT = "script"
ADDIN = "addin"
KIND_TITLES = {SCRIPT: "Script", ADDIN: "Add-In"}
NAME_MAX = 60


class ScriptError(ValueError):
    """Something the person must change; the message says what."""


def is_script_file(name):
    return name.lower().endswith(
        tuple(e.lower() for e in SCRIPT_EXTENSIONS)
    ) and not name.startswith((".", "__"))


def list_scripts(folder, listdir=os.listdir, isfile=os.path.isfile):
    """[{"name", "kind", "path"}] of the scripts in a folder, by name (case ignored)."""
    found = []
    try:
        names = listdir(folder) if folder else []
    except OSError:
        names = []
    for name in names:
        path = os.path.join(folder, name)
        if is_script_file(name) and isfile(path):
            found.append({"name": os.path.splitext(name)[0], "kind": SCRIPT, "path": path})
    return sorted(found, key=lambda e: e["name"].lower())


def list_addins(folder, listdir=os.listdir, isdir=os.path.isdir, isfile=os.path.isfile):
    """[{"name", "kind", "path" (its folder), "main" (its .py)}]: Fusion's add-in layout, one
    folder per add-in with a Python file of the folder's name inside."""
    found = []
    try:
        names = listdir(folder) if folder else []
    except OSError:
        names = []
    for name in names:
        path = os.path.join(folder, name)
        main = os.path.join(path, name + ".py")
        if not name.startswith((".", "__")) and isdir(path) and isfile(main):
            found.append({"name": name, "kind": ADDIN, "path": path, "main": main})
    return sorted(found, key=lambda e: e["name"].lower())


def entry_key(entry):
    return "%s:%s" % (entry["kind"], entry["name"])


def check_name(name, kind, taken=()):
    """The cleaned name of a new script or add-in; ScriptError says what is wrong."""
    name = (name or "").strip()
    if not name:
        raise ScriptError("Give it a name.")
    if len(name) > NAME_MAX:
        raise ScriptError("The name is too long (at most %d characters)." % NAME_MAX)
    if kind == ADDIN:
        if not re.match(r"^[A-Za-z][A-Za-z0-9_]*$", name):
            raise ScriptError(
                "An add-in's name starts with a letter and has only letters, digits and _ "
                "(it is a Python module)."
            )
    elif not re.match(r"^[A-Za-z][A-Za-z0-9_ \-]*$", name):
        raise ScriptError(
            "A script's name starts with a letter and has only letters, digits, spaces, - and _."
        )
    if name.lower() in {t.lower() for t in taken}:
        raise ScriptError("There is already one called %s." % name)
    return name


def _comment(description):
    lines = [d.strip() for d in (description or "").splitlines() if d.strip()]
    return "\n".join("# " + line for line in lines) or "# (no description)"


def script_template(name, description=""):
    """A new script: Run executes it once with the design that is open."""
    return """# -*- coding: utf-8 -*-
# SciForge script "{name}"
{comment}
#
# Runs once when you press Run in UTILITIES > Scripts and Add-Ins (or at start-up when
# Run on Startup is ticked). It uses FreeCAD's Python API on the design that is open.

import FreeCAD as App


def main():
    doc = App.ActiveDocument
    if doc is None:
        App.Console.PrintMessage("{name}: open a design first\\n")
        return
    App.Console.PrintMessage("{name}: %d objects in %s\\n" % (len(doc.Objects), doc.Label))


main()
""".format(name=name, comment=_comment(description))


def addin_template(name, description=""):
    """A new add-in: run() when it is loaded (Run, or at start-up), stop() when it is stopped."""
    return """# -*- coding: utf-8 -*-
# SciForge add-in "{name}"
{comment}
#
# UTILITIES > Scripts and Add-Ins: Run calls run(context) and keeps the add-in loaded; Stop
# calls stop(context). Tick Run on Startup to load it every time SciForge starts.

import FreeCAD as App


def run(context):
    App.Console.PrintMessage("{name} started\\n")


def stop(context):
    App.Console.PrintMessage("{name} stopped\\n")
""".format(name=name, comment=_comment(description))


def new_file(kind, folder, name):
    """(path to write, folder to make or None) for a new script or add-in."""
    if kind == ADDIN:
        path = os.path.join(folder, name)
        return os.path.join(path, name + ".py"), path
    return os.path.join(folder, name + ".FCMacro"), None


def parse_startup(text):
    """The Run on Startup keys ("script:Name;addin:Other") as a set."""
    return {k.strip() for k in (text or "").split(";") if ":" in k and k.strip()}


def startup_text(keys):
    return ";".join(sorted(set(keys)))


def startup_order(entries, keys):
    """The entries to run at start-up, scripts after add-ins (an add-in a script needs is
    loaded first), each group by name."""
    keys = set(keys)
    chosen = [e for e in entries if entry_key(e) in keys]
    return [e for e in chosen if e["kind"] == ADDIN] + [e for e in chosen if e["kind"] == SCRIPT]


def matches(entry, text):
    """The filter box: every word of `text` in the entry's name (case ignored)."""
    words = (text or "").lower().split()
    name = entry["name"].lower()
    return all(w in name for w in words)


def short_error(exc_text, limit=300):
    """The last line of a traceback (what went wrong), shortened for the dialog."""
    lines = [line for line in (exc_text or "").strip().splitlines() if line.strip()]
    text = lines[-1].strip() if lines else "unknown error"
    return text if len(text) <= limit else text[: limit - 1] + "…"
