#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
"""Measures Fusion parity with a script instead of hand-typed guesses (idea 5 of
docs/sciforge/dev/cadcraft-lessons.md, approved by Luca 2026-10-21).

It compares two lists and writes docs/sciforge/parity-checklist.md ("do not edit by hand"):

  * Fusion's command tree by name, recorded by hand in tools/sciforge/data/fusion-menus.txt
    (an indented tree: area > panel > command; its header explains the format);
  * SciForge's real command catalogue, read from the source without starting FreeCAD:
    the ribbon, File menu, application bar, navigation bar and marking menu tables of
    sciforge/ribbon_config.py (the single source of truth for those, loaded as a plain module:
    it imports nothing), the sketch marking menu (sketch_marking.py), the browser's
    right-click menus (browser_core.MENUS), and the menus built in code (timeline, ViewCube,
    workspace button, drawing sheet bar), whose labels are read from the code with Python's
    own parser (ast), never by running it.

Names are compared case-insensitively ("Move / Copy" = "Move/Copy", a trailing "..." ignored).
Deliberate naming differences are listed in tools/sciforge/data/parity-aliases.txt
("Fusion name = SciForge name", optionally qualified by the end of the Fusion path).

A Fusion command is looked for where its [in=...] scope says (its own tab or menu). Ribbon
commands of SOLID / SURFACE / UTILITIES and the File menu, application bar and workspace menu
may also be found in another of those places (SURFACE's Fillet is SOLID's Fillet); the
checklist says where. Context menus (marking menus, browser, timeline, ViewCube, sheet bar),
the navigation bar and the SKETCH, MESH and DRAWING tabs never borrow from elsewhere: a
command that exists only on the ribbon is not in the right-click menu. A SciForge entry with
no command (shown greyed, "not available in SciForge yet") does not count as present.

It counts presence (breadth), not depth: one entry with half of Fusion's options counts as
present. The generated file says so; docs/sciforge/dev/core-workflows.md is the depth check.

    python3 tools/sciforge/parity.py            write docs/sciforge/parity-checklist.md
    python3 tools/sciforge/parity.py --check    exit 1 if that file is out of date
    python3 tools/sciforge/parity.py --summary  print the headline only

Options: --out FILE (another checklist path), --date YYYY-MM-DD (the date in the header),
--repo DIR (another repository root, for tests).
"""

import argparse
import ast
import datetime
import importlib.util
import os
import re
import sys
from collections import OrderedDict, namedtuple

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
MENUS_FILE = os.path.join("tools", "sciforge", "data", "fusion-menus.txt")
ALIASES_FILE = os.path.join("tools", "sciforge", "data", "parity-aliases.txt")
CHECKLIST_FILE = os.path.join("docs", "sciforge", "parity-checklist.md")
PACKAGE_DIR = os.path.join("src", "Mod", "SciForge", "sciforge")

# Places whose commands may be found in one another (see the module docstring).
# (Not the navigation bar: its Object Visibility "Joint Origins" is not the selection filter.)
FALLBACK_SCOPES = frozenset(
    ["tab:solid", "tab:surface", "tab:utilities", "file", "quick", "workspace"]
)

# A SciForge menu entry: where (scope), its path for the reader, its label, and whether it
# runs a command (False: listed greyed, "not available in SciForge yet").
Entry = namedtuple("Entry", "scope path label available")
# A Fusion command of fusion-menus.txt (path = area, panel, ..., name).
FusionItem = namedtuple("FusionItem", "path name unsure scopes out line")
# The result for one Fusion command. status: present, elsewhere, greyed, missing, out.
Result = namedtuple("Result", "item status where")

PRESENT = ("present", "elsewhere")


def log(message):
    print("[SciForge] parity: %s" % message)


# ------------------------------------------------------------------------------ names
def norm(name):
    """The form names are compared in: lower case, single spaces, no spaces round "/",
    no trailing "?" or "..."."""
    text = (name or "").replace("…", "...").strip()
    text = text.rstrip("?").strip()
    while text.endswith("..."):
        text = text[:-3].rstrip()
    text = re.sub(r"\s*/\s*", "/", text)
    text = re.sub(r"\s+", " ", text)
    return text.lower()


# ------------------------------------------------------------------------------ Fusion's tree
_ATTR = re.compile(r"\s*\[(in|out)=([^\]]*)\]\s*$")
_Row = namedtuple("_Row", "level name unsure attrs line")


def parse_menus(text):
    """The commands (lines without children) of a fusion-menus.txt text, as FusionItems in
    file order. Raises ValueError with the line number for a malformed line."""
    rows = []
    for number, raw in enumerate(text.splitlines(), 1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "\t" in raw:
            raise ValueError("line %d: use spaces, not tabs" % number)
        indent = len(raw) - len(raw.lstrip(" "))
        if indent % 2:
            raise ValueError("line %d: indentation must be a multiple of 2 spaces" % number)
        body, attrs = stripped, {}
        while True:
            match = _ATTR.search(body)
            if not match:
                break
            if match.group(1) in attrs:
                raise ValueError("line %d: [%s=...] given twice" % (number, match.group(1)))
            attrs[match.group(1)] = match.group(2).strip()
            body = body[: match.start()].rstrip()
        if "[" in body or "]" in body:
            raise ValueError("line %d: unknown attribute (only [in=...] and [out=...])" % number)
        unsure = body.endswith("?")
        name = body[:-1].rstrip() if unsure else body
        if not name:
            raise ValueError("line %d: no name" % number)
        rows.append(_Row(indent // 2, name, unsure, attrs, number))

    items, stack = [], []  # stack: (name, scopes, out) of the headings above
    for index, row in enumerate(rows):
        if row.level > len(stack):
            raise ValueError("line %d: indented more than one level below its heading" % row.line)
        del stack[row.level :]
        scopes = stack[-1][1] if stack else ()
        out = stack[-1][2] if stack else None
        if "in" in row.attrs:
            scopes = tuple(s.strip() for s in row.attrs["in"].split(",") if s.strip())
        if "out" in row.attrs:
            out = row.attrs["out"] or "left out on purpose"
        leaf = index + 1 == len(rows) or rows[index + 1].level <= row.level
        if leaf:
            if row.level == 0:
                raise ValueError("line %d: an area needs commands under it" % row.line)
            if not scopes:
                raise ValueError("line %d: no [in=...] scope above it" % row.line)
            path = tuple(s[0] for s in stack) + (row.name,)
            items.append(FusionItem(path, row.name, row.unsure, scopes, out, row.line))
        stack.append((row.name, scopes, out))
    return items


def parse_aliases(text):
    """[(key, [SciForge names])] of a parity-aliases.txt text. key is a tuple of normalized
    names: one name, or the end of a Fusion path ("MARKING MENU > Show/Hide")."""
    aliases = []
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.count("=") != 1:
            raise ValueError("line %d: write 'Fusion name = SciForge name'" % number)
        left, right = (part.strip() for part in line.split("="))
        key = tuple(norm(part) for part in left.split(">"))
        targets = [t.strip() for t in right.split("|") if t.strip()]
        if not all(key) or not targets:
            raise ValueError("line %d: a name is missing" % number)
        aliases.append((key, targets))
    return aliases


def alias_targets(item, aliases):
    """SciForge names an alias gives this Fusion command, the qualified aliases first."""
    path = tuple(norm(p) for p in item.path)
    qualified, plain = [], []
    for key, targets in aliases:
        if len(key) > 1 and path[-len(key) :] == key:
            qualified.extend(targets)
        elif len(key) == 1 and key[0] == path[-1]:
            plain.extend(targets)
    return qualified + plain


# ------------------------------------------------------------------------------ SciForge's menus
def _load_ribbon_config(package):
    """ribbon_config.py as a module of its own (it imports nothing, so no FreeCAD needed)."""
    path = os.path.join(package, "ribbon_config.py")
    spec = importlib.util.spec_from_file_location("sciforge_parity_ribbon_config", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _walk(entries, scope, path):
    for entry in entries:
        if entry is None:
            continue
        if "submenu" in entry:
            yield from _walk(entry["submenu"], scope, path + (entry["label"],))
        else:
            label = entry["label"]
            yield Entry(scope, path + (label,), label, entry.get("command") is not None)


def _parse(package, filename):
    with open(os.path.join(package, filename), encoding="utf-8") as handle:
        return ast.parse(handle.read(), filename)


def _module_value(tree, name):
    """The value node of a module-level NAME = ... assignment."""
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            return node.value
    raise LookupError("%s not found" % name)


def _item_calls(tree):
    """(label, available) of every item("Label", command, ...) / cfg.item(...) call."""
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        first = node.args[0]
        if name != "item" or not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
            continue
        command = node.args[1] if len(node.args) > 1 else None
        available = not (
            command is None or (isinstance(command, ast.Constant) and command.value is None)
        )
        found.append((node.lineno, first.value, available))
    return [(label, available) for _line, label, available in sorted(found)]


def _find_function(tree, name, cls=None):
    scope = tree
    if cls is not None:
        classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == cls]
        if not classes:
            raise LookupError("class %s not found" % cls)
        scope = classes[0]
    for node in ast.walk(scope):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise LookupError("function %s not found" % name)


def _literal_strings(node):
    """Strings a value node can stand for: a constant, both sides of "a if c else b", the
    values of a dict, and {...}.get(key, "default")."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.IfExp):
        return _literal_strings(node.body) + _literal_strings(node.orelse)
    if isinstance(node, ast.Dict):
        return [s for v in node.values for s in _literal_strings(v)]
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "get"
        and isinstance(node.func.value, ast.Dict)
    ):
        found = _literal_strings(node.func.value)
        for arg in node.args[1:]:
            found += _literal_strings(arg)
        return found
    return []


def _sequence(node, func):
    if isinstance(node, (ast.Tuple, ast.List)):
        return node.elts
    if isinstance(node, ast.Name):
        for inner in ast.walk(func):
            if (
                isinstance(inner, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == node.id for t in inner.targets)
                and isinstance(inner.value, (ast.Tuple, ast.List))
            ):
                return inner.value.elts
    return []


def _name_strings(name, func):
    """Strings a local variable takes in a function: from `for name in (...)`, `for a, name, b
    in ROWS` (ROWS a literal list or tuple), or `name = <value>`."""
    found = []
    for node in ast.walk(func):
        if isinstance(node, (ast.For, ast.comprehension)):
            target, position = node.target, None
            if isinstance(target, ast.Name) and target.id == name:
                position = -1
            elif isinstance(target, ast.Tuple):
                for index, elt in enumerate(target.elts):
                    if isinstance(elt, ast.Name) and elt.id == name:
                        position = index
            if position is None:
                continue
            for element in _sequence(node.iter, func):
                if position == -1:
                    found += _literal_strings(element)
                elif isinstance(element, (ast.Tuple, ast.List)) and len(element.elts) > position:
                    found += _literal_strings(element.elts[position])
        elif isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            found += _literal_strings(node.value)
    return found


def menu_labels(tree, function, cls=None, calls=None):
    """The labels a menu-building function gives its entries, read from its code: the text
    of every addAction / addMenu call (after an icon argument, if any) and of the calls named
    in `calls` ({function name: index of its label argument})."""
    func = _find_function(tree, function, cls)
    calls = dict(calls or {})
    labels = []
    for node in ast.walk(func):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        name = (
            node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
        )
        if name in ("addAction", "addMenu"):
            arg = node.args[0]
            if not isinstance(arg, (ast.Constant, ast.Name, ast.IfExp)) and len(node.args) > 1:
                arg = node.args[1]  # (icon, text)
        elif name in calls and len(node.args) > calls[name]:
            arg = node.args[calls[name]]
        else:
            continue
        if isinstance(arg, ast.Name):
            labels += _name_strings(arg.id, func)
        else:
            labels += _literal_strings(arg)
    unique = []
    for label in labels:
        if label and label not in unique:
            unique.append(label)
    return unique


# Menus built in code: (scope, path shown, file, function, class, extra label calls).
CODE_MENUS = [
    (
        "timeline:step",
        ("Timeline", "step menu"),
        "timeline_ui.py",
        "_menu",
        "TimelineWidget",
        {"add": 0},
    ),
    (
        "timeline:group",
        ("Timeline", "group menu"),
        "timeline_ui.py",
        "_group_menu",
        "TimelineWidget",
        {"add": 0},
    ),
    (
        "timeline:settings",
        ("Timeline", "settings"),
        "timeline_ui.py",
        "_settings",
        "TimelineWidget",
        None,
    ),
    (
        "timeline:playback",
        ("Timeline", "buttons"),
        "timeline_ui.py",
        "__init__",
        "TimelineWidget",
        {"_tool": 1},
    ),
    ("viewcube", ("ViewCube",), "viewcube_ui.py", "open_menu", "ViewCube", None),
    ("workspace", ("Workspace menu",), "ribbon_ui.py", "_workspace_menu", "RibbonWidget", None),
    (
        "workspace",
        ("Workspace menu", "Drawing"),
        "drawing_ui.py",
        "fill_workspace_menu",
        None,
        None,
    ),
    ("sheets", ("Sheet bar",), "drawing_sheets_ui.py", "_menu", "SheetBar", None),
]


def sciforge_catalogue(repo=REPO):
    """Every SciForge menu entry, as Entries in a stable order."""
    package = os.path.join(repo, PACKAGE_DIR)
    cfg = _load_ribbon_config(package)
    entries = []
    for tab in cfg.TABS:
        for grp in tab["groups"]:
            entries += _walk(grp["items"], "tab:" + tab["id"], (tab["title"], grp["title"]))
    entries += _walk(cfg.FILE_MENU, "file", ("File menu",))
    entries += _walk(cfg.QUICK_ACCESS, "quick", ("Application bar",))
    entries += _walk(cfg.NAV_BAR, "nav", ("Navigation bar",))
    entries += _walk(cfg.MARKING_MENU + cfg.MARKING_LIST, "marking", ("Marking menu",))
    for label, available in _item_calls(_parse(package, "marking_menu.py")):
        entries.append(Entry("marking", ("Marking menu", label), label, available))
    for label, available in _item_calls(_parse(package, "sketch_marking.py")):
        entries.append(Entry("sketch-marking", ("Sketch marking menu", label), label, available))
    menus = ast.literal_eval(_module_value(_parse(package, "browser_core.py"), "MENUS"))
    for kind, labels in menus.items():
        for label in labels:
            if label != "-":
                entries.append(Entry("browser:" + kind, ("Browser", kind, label), label, True))
    trees = {}
    for scope, path, filename, function, cls, calls in CODE_MENUS:
        tree = trees.setdefault(filename, _parse(package, filename))
        for label in menu_labels(tree, function, cls, calls):
            entries.append(Entry(scope, path + (label,), label, True))
    extras = _module_value(_parse(package, "derive_ui.py"), "MENU_EXTRAS")
    for rows in getattr(extras, "values", []):
        for row in getattr(rows, "elts", []):
            first = row.elts[0] if isinstance(row, ast.Tuple) and row.elts else None
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                label = first.value
                entries.append(
                    Entry("timeline:step", ("Timeline", "step menu", label), label, True)
                )
    return entries


# ------------------------------------------------------------------------------ matching
def _in_scope(entry_scope, scopes):
    return any(entry_scope == s or entry_scope.startswith(s + ":") for s in scopes)


def match_item(item, entries, aliases):
    """The Result for one Fusion command."""
    names = [norm(item.name)] + [norm(t) for t in alias_targets(item, aliases)]

    def look(candidates):
        for name in names:
            found = [e for e in candidates if norm(e.label) == name]
            if found:
                ready = [e for e in found if e.available]
                return (ready or found)[0], bool(ready)
        return None, False

    def rank(entry):  # the first scope of [in=...] is looked at first
        return min(i for i, s in enumerate(item.scopes) if _in_scope(entry.scope, (s,)))

    home = sorted((e for e in entries if _in_scope(e.scope, item.scopes)), key=rank)
    entry, ready = look(home)
    if entry is not None:
        return Result(item, "present" if ready else "greyed", entry)
    if item.out:
        return Result(item, "out", None)
    if set(item.scopes) <= FALLBACK_SCOPES:
        entry, ready = look([e for e in entries if e.scope in FALLBACK_SCOPES])
        if entry is not None and ready:
            return Result(item, "elsewhere", entry)
        if entry is not None:
            return Result(item, "greyed", entry)
    return Result(item, "missing", None)


def compare(items, entries, aliases):
    return [match_item(item, entries, aliases) for item in items]


# ------------------------------------------------------------------------------ the checklist
def _pct(part, whole):
    return "%.1f%%" % (100.0 * part / whole) if whole else "-"


def _where(entry):
    return " > ".join(entry.path)


def _panel(item):
    return item.path[1] if len(item.path) > 2 else "(top level)"


def _counts(results):
    present = sum(1 for r in results if r.status in PRESENT)
    return present, len(results)


def headline(results):
    present, total = _counts(results)
    return "Fusion commands present: %d / %d (%s)" % (present, total, _pct(present, total))


def render(results, entries, date):
    """The text of docs/sciforge/parity-checklist.md."""
    built = [r for r in results if not r.item.out]
    present_built, total_built = _counts(built)
    out = [r for r in results if r.item.out]
    unsure = sum(1 for r in results if r.item.unsure)
    lines = [
        "# Fusion parity checklist",
        "",
        "Generated by tools/sciforge/parity.py on %s; do not edit by hand." % date,
        "",
        "Run `python3 tools/sciforge/parity.py` after changing a menu, the Fusion list",
        "(`tools/sciforge/data/fusion-menus.txt`) or the aliases",
        "(`tools/sciforge/data/parity-aliases.txt`); the unit test `test_parity` fails while this",
        "file is out of date.",
        "",
        "## Headline",
        "",
        "**%s**" % headline(results),
        "",
        "In the areas SciForge builds (without the %d entries left out on purpose, see the end): "
        "**%d / %d (%s)**."
        % (len(out), present_built, total_built, _pct(present_built, total_built)),
        "",
        "What the number means:",
        "",
        "- It measures **presence (breadth), not depth**: a command counts as present when",
        "  SciForge has a menu entry of that name (or its alias) that runs a command. It says",
        "  nothing about whether every option of Fusion's dialog is there, or whether the",
        "  result is as good. The depth check is `docs/sciforge/dev/core-workflows.md` (everyday",
        "  workflows, end to end) and the parity docs in `docs/sciforge/parity/`.",
        "- Fusion's list is recorded by hand, by name, from memory of stock Fusion; %d of its"
        % unsure,
        '  names are marked "(not sure)" below and wait for a look at real Fusion.',
        "- Entries are menu entries: a command in two places (Delete in MODIFY and in the",
        "  marking menu) counts twice; panels Fusion repeats on several tabs count once.",
        "- SciForge's side is read from its source (`ribbon_config.py`, `sketch_marking.py`,",
        "  `browser_core.MENUS`, the timeline / ViewCube / sheet bar menus). An entry shown greyed",
        '  ("not available in SciForge yet") is not counted.',
        "",
        "## By area and panel",
        "",
        "| Area | Panel | Items | Present | % |",
        "|---|---|---:|---:|---:|",
    ]
    areas = OrderedDict()
    for result in results:
        areas.setdefault(result.item.path[0], OrderedDict()).setdefault(
            _panel(result.item), []
        ).append(result)
    for area, panels in areas.items():
        everything = [r for rows in panels.values() for r in rows]
        present, total = _counts(everything)
        note = " (left out on purpose)" if all(r.item.out for r in everything) else ""
        lines.append(
            "| **%s**%s | all | **%d** | **%d** | **%s** |"
            % (area, note, total, present, _pct(present, total))
        )
        if len(panels) > 1:
            for panel, rows in panels.items():
                present, total = _counts(rows)
                lines.append(
                    "| | %s | %d | %d | %s |" % (panel, total, present, _pct(present, total))
                )
    lines += ["", "## Not in SciForge yet", ""]
    lines.append(
        "Fusion commands SciForge does not have (the entries left out on purpose are at the end)."
    )
    lines.append('"greyed": SciForge\'s menu already shows the entry, greyed out.')
    lines.append("")
    missing = [r for r in built if r.status not in PRESENT]
    for area in areas:
        rows = [r for r in missing if r.item.path[0] == area]
        if not rows:
            continue
        lines.append("### %s (%d)" % (area, len(rows)))
        lines.append("")
        for result in rows:
            notes = []
            if result.status == "greyed":
                notes.append("greyed")
            if result.item.unsure:
                notes.append("not sure")
            suffix = " (%s)" % ", ".join(notes) if notes else ""
            lines.append("- %s%s" % (" > ".join(result.item.path[1:]), suffix))
        lines.append("")
    elsewhere = [r for r in results if r.status == "elsewhere"]
    lines += ["## Present in another place", ""]
    if elsewhere:
        lines.append(
            "Counted as present: SciForge has the command, in another place than Fusion's."
        )
        lines.append("")
        for result in elsewhere:
            lines.append("- %s: %s" % (" > ".join(result.item.path), _where(result.where)))
    else:
        lines.append("None.")
    lines.append("")
    lines += ["## Left out on purpose", ""]
    reasons = OrderedDict()
    for result in out:
        reasons.setdefault(result.item.out, []).append(result)
    for reason, rows in reasons.items():
        present, total = _counts(rows)
        names = ", ".join(" > ".join(r.item.path) for r in rows)
        lines.append("- %s (%d entries, %d present): %s" % (reason, total, present, names))
    if not reasons:
        lines.append("None.")
    # A label counts as matched for its whole family of places: every ribbon tab together
    # (SciForge repeats CONSTRUCT, INSPECT... on several tabs, Fusion's list has them once),
    # otherwise its own scope.
    family = lambda scope: "tab" if scope.startswith("tab:") else scope  # noqa: E731
    used = {(family(r.where.scope), norm(r.where.label)) for r in results if r.where is not None}
    lines += [
        "",
        "## SciForge entries with no Fusion counterpart in the list",
        "",
        "SciForge's own additions (beyond Fusion), entries Fusion has in a place the list does",
        "not cover, or a name the alias file should map. Greyed entries are left out.",
        "",
    ]
    extra = OrderedDict()
    for entry in entries:
        if entry.available and (family(entry.scope), norm(entry.label)) not in used:
            names = extra.setdefault(entry.scope, [])
            if entry.label not in names:
                names.append(entry.label)
    for scope, names in extra.items():
        if names:
            lines.append("- `%s`: %s" % (scope, ", ".join(names)))
    lines.append("")
    return "\n".join(lines)


# ------------------------------------------------------------------------------ running
def _read(repo, relative):
    with open(os.path.join(repo, relative), encoding="utf-8") as handle:
        return handle.read()


def build(repo=REPO, date=None):
    """(results, entries, checklist text) for a repository."""
    items = parse_menus(_read(repo, MENUS_FILE))
    aliases = parse_aliases(_read(repo, ALIASES_FILE))
    entries = sciforge_catalogue(repo)
    results = compare(items, entries, aliases)
    date = date or datetime.date.today().isoformat()
    return results, entries, render(results, entries, date)


_DATE_LINE = re.compile(
    r"^(Generated by tools/sciforge/parity\.py on )\S+(; do not edit by hand\.)$", re.M
)


def same_checklist(old, new):
    """True when two checklists differ at most in the date of their header."""
    blank = lambda text: _DATE_LINE.sub(r"\1DATE\2", text.replace("\r\n", "\n"))  # noqa: E731
    return blank(old) == blank(new)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--check", action="store_true", help="exit 1 if the checklist is out of date"
    )
    parser.add_argument("--summary", action="store_true", help="print the headline only")
    parser.add_argument("--out", help="checklist path (default docs/sciforge/parity-checklist.md)")
    parser.add_argument("--date", help="date for the header (default today)")
    parser.add_argument("--repo", default=REPO, help="repository root")
    args = parser.parse_args(argv)
    try:
        results, _entries, text = build(args.repo, args.date)
    except (OSError, ValueError, LookupError, SyntaxError) as exc:
        log("could not build the checklist: %s" % exc)
        return 2
    target = args.out or os.path.join(args.repo, CHECKLIST_FILE)
    if args.summary:
        print(headline(results))
        return 0
    if args.check:
        try:
            with open(target, encoding="utf-8") as handle:
                old = handle.read()
        except OSError:
            log("%s is missing: run python3 tools/sciforge/parity.py" % target)
            return 1
        if not same_checklist(old, text):
            log("%s is out of date: run python3 tools/sciforge/parity.py" % target)
            return 1
        log("checklist up to date (%s)" % headline(results))
        return 0
    with open(target, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    log("wrote %s: %s" % (os.path.relpath(target, args.repo), headline(results)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
