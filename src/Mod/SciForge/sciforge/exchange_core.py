# SPDX-License-Identifier: LGPL-2.1-or-later
"""Import and export with structure (Fusion's STEP assemblies, IGES, DXF of a sketch), the
decisions without FreeCAD or Qt, so they are unit tested on their own. Spec and sources:
docs/sciforge/parity/insert-export.md ("Part 2").

A file's structure is read into plain nodes (step_import.read_tree makes them from what
FreeCAD's STEP reader builds):

    {"name": "Wheel",            the product's name in the file
     "kind": "assembly"|"part",  an assembly holds other nodes, a part holds solids
     "key": "LinkGroup001",      the definition: two occurrences of one part share it
     "link": None|"LinkGroup001" a repeated occurrence: the key of what it repeats
     "pieces": [...],            the part's solids (opaque to this module)
     "children": [...]}          an assembly's nodes

Fusion's rules (Autodesk handout "Fusion 360 Large Model Management": "STEP files retain
component structure and names"; forum: "STEP files imported into Fusion create
components"; the guesses are marked in the parity doc):

- every product becomes a component named after it, nested as in the file; a part's solids
  are its bodies (Body1, Body2 ... in each component, as Fusion numbers bodies);
- an assembly that holds a part of its own name (FreeCAD and SciForge write a component's
  bodies so) keeps that part's solids as its own bodies, not one level deeper;
- a part repeated in the file comes in once; the other occurrences are copies of it
  (linked occurrences: "Wheel:1", "Wheel:2");
- File > Open: the file's top product is the design itself (its parts and assemblies are
  the design's components; a single part's solids are bodies of the design);
- Insert into the current design: the whole file is one component named after the file.
"""

import re

ASSEMBLY = "assembly"
PART = "part"

OPEN = "open"
INSERT = "insert"

# File > Open and Insert take these (FreeCAD reads both; SAT / ACIS needs a commercial kernel).
STEP_EXTENSIONS = (".step", ".stp")
IGES_EXTENSIONS = (".iges", ".igs")
CAD_EXTENSIONS = STEP_EXTENSIONS + IGES_EXTENSIONS
DESIGN_EXTENSION = ".fcstd"
NOT_READ = {
    ".sat": "SAT (ACIS) files need Autodesk's or Spatial's kernel; FreeCAD cannot read them. "
    "Save the part as STEP in the other program.",
    ".sab": "SAT (ACIS) files need Autodesk's or Spatial's kernel; FreeCAD cannot read them. "
    "Save the part as STEP in the other program.",
    ".smt": "SMT is Autodesk's own format; save the part as STEP in the other program.",
    ".f3d": "F3D is Fusion's own archive; export the design from Fusion as STEP.",
    ".dwg": "DWG is a drawing format: use Insert DXF (save the DWG as DXF first).",
}


class ExchangeError(ValueError):
    """Something the user has to change (a file SciForge cannot read, nothing to export)."""


def node(name, kind, key=None, link=None, pieces=None, children=None, place=None):
    """A node of a file's structure (see the module's doc)."""
    return {
        "name": name or "",
        "kind": kind,
        "key": key,
        "link": link,
        "pieces": list(pieces or []),
        "children": list(children or []),
        "place": place,
    }


def file_kind(path):
    """'step', 'iges', 'design' or the reason the file cannot be opened (ExchangeError)."""
    ext = _ext(path)
    if ext in STEP_EXTENSIONS:
        return "step"
    if ext in IGES_EXTENSIONS:
        return "iges"
    if ext == DESIGN_EXTENSION:
        return "design"
    if ext in NOT_READ:
        raise ExchangeError(NOT_READ[ext])
    raise ExchangeError(
        "SciForge opens designs (.FCStd), STEP (.step, .stp) and IGES (.iges, .igs) files%s."
        % ((", not %s" % ext) if ext else "")
    )


def _ext(path):
    match = re.search(r"(\.[^./\\]+)$", path or "")
    return match.group(1).lower() if match else ""


def base_name(path):
    """'Robot' for /a/b/Robot.step (also for Windows paths)."""
    name = re.split(r"[/\\]", path or "")[-1]
    return re.sub(r"\.[^.]*$", "", name) or "Imported"


# -- the structure -----------------------------------------------------------------------
def normalize(n):
    """Fold a part named like its assembly into the assembly (its solids become the
    assembly's own bodies), everywhere in the tree. Returns a new node."""
    out = dict(n)
    out["pieces"] = list(n.get("pieces") or [])
    children = []
    for child in n.get("children") or []:
        child = normalize(child)
        if (
            n.get("kind") == ASSEMBLY
            and child["kind"] == PART
            and not child.get("link")
            and child["name"] == n.get("name")
            and not out["pieces"]
        ):
            out["pieces"] = list(child["pieces"])
            out["folded"] = child.get("key")
            continue
        children.append(child)
    out["children"] = children
    return out


def plan(tops, mode, file_label):
    """What a file becomes: {"component": label or None (Insert: the file's component),
    "pieces": the solids that become bodies at that level, "children": the nodes that
    become components there, "top": the node whose frame that level has (or None),
    "part_name": the name a single body there takes (a single part's), or None}."""
    tops = [normalize(t) for t in tops if t is not None]
    if len(tops) == 1 and tops[0]["kind"] == ASSEMBLY:
        level = {"pieces": tops[0]["pieces"], "children": tops[0]["children"], "top": tops[0]}
    elif len(tops) == 1:
        level = {"pieces": tops[0]["pieces"], "children": [], "top": tops[0]}
    else:
        level = {"pieces": [], "children": tops, "top": None}
    level["component"] = file_label if mode == INSERT else None
    # a single part opened at the design's root names its body; an assembly's own bodies
    # are numbered
    level["part_name"] = tops[0]["name"] if len(tops) == 1 and tops[0]["kind"] == PART else None
    return level


def body_labels(count, at_root=False, part_name=None):
    """Names of the bodies a part's solids become: Body1, Body2 ... in a component (Fusion
    numbers bodies per component); a single solid opened at the design's root keeps the
    part's name (else the file's names would be gone)."""
    if count <= 0:
        return []
    if at_root and count == 1 and part_name:
        return [part_name]
    return ["Body%d" % (i + 1) for i in range(count)]


def count_nodes(tops):
    """(components, instances, solids) a file brings in (for the message after it)."""
    comps = instances = solids = 0
    for t in tops:
        stack = [normalize(t)]
        while stack:
            n = stack.pop()
            if n.get("link"):
                instances += 1
                continue
            comps += 1
            solids += len(n["pieces"])
            stack.extend(n["children"])
    return comps, instances, solids


def occurrences(tops):
    """{key: number of occurrences} of every definition in the file (a part used twice
    has 2)."""
    found = {}
    stack = list(tops)
    while stack:
        n = stack.pop()
        key = n.get("link") or n.get("key")
        if key:
            found[key] = found.get(key, 0) + 1
        if not n.get("link"):
            stack.extend(n.get("children") or [])
    return found


def describe(comps, instances, solids, name):
    parts = []
    if comps:
        parts.append("%d component%s" % (comps, "" if comps == 1 else "s"))
    if instances:
        parts.append("%d cop%s" % (instances, "y" if instances == 1 else "ies"))
    parts.append("%d bod%s" % (solids, "y" if solids == 1 else "ies"))
    return "%s: %s" % (name, ", ".join(parts))


# -- export ---------------------------------------------------------------------------------
# (label, file ending, kind) of the Export dialog's Type list, in Fusion's order for the
# kinds SciForge writes (Autodesk support "How to export a CAD design from Fusion").
EXPORT_TYPES = [
    ("STEP", ".step", "step"),
    ("IGES", ".igs", "iges"),
    ("STL (Binary)", ".stl", "stl"),
    ("STL (ASCII)", ".stl", "stl_ascii"),
    ("3MF", ".3mf", "3mf"),
    ("OBJ", ".obj", "obj"),
    ("DXF", ".dxf", "dxf"),
    ("DWG", ".dwg", "dwg"),
]
CAD_KINDS = ("step", "iges")
FLAT_KINDS = ("dxf", "dwg")

DWG_NONE = (
    "DWG needs a free converter that is not installed: LibreDWG (dxf2dwg), the ODA File "
    "Converter or QCAD. Install one (FreeCAD's Import-Export preferences name it), or "
    "export DXF: AutoCAD and every other CAD program open DXF too."
)


def export_kind(label):
    for entry in EXPORT_TYPES:
        if entry[0] == label:
            return entry[2]
    raise ExchangeError("Unknown type: %s" % label)


def export_extension(label):
    for entry in EXPORT_TYPES:
        if entry[0] == label:
            return entry[1]
    raise ExchangeError("Unknown type: %s" % label)


def mirror_plan(units):
    """How a component tree is written to STEP so that SciForge (and Fusion) read the same
    components back. `units`: [{"name", "bodies": n, "children": [...], "instance_of":
    name or None, "id": name}] (one per component). Returns [{"id", "as": "part" |
    "assembly" | "link" | "skip", "children": [...], "bodies_part": bool}]: a component
    with bodies only is a part of its name; with components in it, an assembly holding a
    part of its own name for its bodies (folded back by normalize()); a copy of a component
    that is written too is a second occurrence of it; an empty component is left out (STEP
    has no empty product)."""
    written = set()

    def collect(items):
        for u in items:
            if not u.get("instance_of"):
                written.add(u["id"])
            collect(u.get("children") or [])

    collect(units)

    def one(u):
        kids = [one(c) for c in u.get("children") or []]
        kids = [k for k in kids if k["as"] != "skip"]
        if u.get("instance_of") and u["instance_of"] in written:
            return {"id": u["id"], "as": "link", "children": [], "bodies_part": False}
        if not kids and not u.get("bodies"):
            return {"id": u["id"], "as": "skip", "children": [], "bodies_part": False}
        if not kids:
            return {"id": u["id"], "as": "part", "children": [], "bodies_part": True}
        return {"id": u["id"], "as": "assembly", "children": kids, "bodies_part": bool(u["bodies"])}

    return [one(u) for u in units]


def dxf_name(sketch_label):
    """The file name Save As DXF suggests for a sketch."""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", (sketch_label or "").strip()).strip(". ")
    return (name or "sketch") + ".dxf"
