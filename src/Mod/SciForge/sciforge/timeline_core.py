# SPDX-License-Identifier: LGPL-2.1-or-later
"""The design timeline as data: one row of steps for the whole design, like Fusion.

Pure Python (no FreeCAD, no Qt) so it is unit tested outside FreeCAD.

Input: one dict per step, in the order of its own body (PartDesign keeps a body's
steps in ``Body.Group``), plus each body's Tip:

    {"name", "label", "type_id", "body" (body name or None), "key" (creation order),
     "suppressed" (bool), "error" (str), "warning" (str), "deps" ([names it uses])}

FreeCAD keeps one history per body; Fusion shows one timeline for the design. The
bodies' lists are merged by creation order (``key``), never changing the order
inside a body, so the merged row is always a valid FreeCAD history.

The history marker is FreeCAD's ``Body.Tip``: a step is active when it is at or
before its body's Tip. Only solid steps can be a Tip, so the marker always sits
just before the first rolled-back solid step (or at the end).
"""

import re
from dataclasses import dataclass, field

# kind -> (Fusion's name for the step, icon in icons/ui)
KINDS = {
    "sketch": ("Sketch", "sk_rectangle"),
    "extrude": ("Extrude", "extrude"),
    "revolve": ("Revolve", "revolve"),
    "sweep": ("Sweep", "sweep"),
    "loft": ("Loft", "loft"),
    "rib": ("Rib", "rib"),
    "web": ("Web", "web"),
    "emboss": ("Emboss", "emboss"),
    "hole": ("Hole", "hole"),
    "thread": ("Thread", "thread"),
    "box": ("Box", "box"),
    "cylinder": ("Cylinder", "cylinder"),
    "sphere": ("Sphere", "sphere"),
    "torus": ("Torus", "torus"),
    "coil": ("Coil", "coil"),
    "pipe": ("Pipe", "pipe"),
    "primitive": ("Primitive", "box"),
    "pattern_rect": ("Rectangular Pattern", "pattern_rect"),
    "pattern_circ": ("Circular Pattern", "pattern_circ"),
    "pattern": ("Pattern", "pattern_rect"),
    "mirror": ("Mirror", "mirror"),
    "thicken": ("Thicken", "thicken"),
    "fillet": ("Fillet", "fillet"),
    "chamfer": ("Chamfer", "chamfer"),
    "shell": ("Shell", "shell"),
    "draft": ("Draft", "draft"),
    "scale": ("Scale", "scale"),
    "combine": ("Combine", "combine"),
    "split_body": ("Split Body", "split_body"),
    "split_face": ("Split Face", "split_face"),
    "move": ("Move", "move"),
    "presspull": ("Press Pull", "press_pull"),
    "offset_face": ("Offset Face", "offset_face"),
    "replace_face": ("Replace Face", "replace_face"),
    "plane": ("Plane", "offset_plane"),
    "axis": ("Axis", "axis"),
    "point": ("Point", "point"),
    "ucs": ("Coordinate System", "ucs"),
    "derive": ("Derive", "derive"),
    "base": ("Base Feature", "document"),
    "group": ("Group", "folder"),
    "other": ("Feature", "workspace_design"),
}

KIND_BY_TYPEID = {
    "Sketcher::SketchObject": "sketch",
    "PartDesign::Pad": "extrude",
    "PartDesign::Pocket": "extrude",  # Fusion calls cut extrudes "Extrude" too
    "PartDesign::Revolution": "revolve",
    "PartDesign::Groove": "revolve",
    "PartDesign::Hole": "hole",
    "PartDesign::Fillet": "fillet",
    "PartDesign::Chamfer": "chamfer",
    "PartDesign::Draft": "draft",
    "PartDesign::Thickness": "shell",
    "PartDesign::Mirrored": "mirror",
    "PartDesign::LinearPattern": "pattern_rect",
    "PartDesign::PolarPattern": "pattern_circ",
    "PartDesign::MultiTransform": "pattern",
    "PartDesign::Scaled": "scale",
    "PartDesign::AdditiveLoft": "loft",
    "PartDesign::SubtractiveLoft": "loft",
    "PartDesign::AdditivePipe": "sweep",
    "PartDesign::SubtractivePipe": "sweep",
    "PartDesign::AdditiveHelix": "coil",
    "PartDesign::SubtractiveHelix": "coil",
    "PartDesign::AdditiveBox": "box",
    "PartDesign::SubtractiveBox": "box",
    "PartDesign::AdditiveCylinder": "cylinder",
    "PartDesign::SubtractiveCylinder": "cylinder",
    "PartDesign::AdditiveSphere": "sphere",
    "PartDesign::SubtractiveSphere": "sphere",
    "PartDesign::AdditiveTorus": "torus",
    "PartDesign::SubtractiveTorus": "torus",
    "PartDesign::Boolean": "combine",
    "PartDesign::FeatureBase": "base",
    "PartDesign::Plane": "plane",
    "PartDesign::Line": "axis",
    "PartDesign::Point": "point",
    "PartDesign::CoordinateSystem": "ucs",
    "PartDesign::ShapeBinder": "derive",
    "PartDesign::SubShapeBinder": "derive",
    "Part::DatumPlane": "plane",
    "Part::DatumLine": "axis",
    "Part::DatumPoint": "point",
    "Part::Box": "box",
    "Part::Cylinder": "cylinder",
    "Part::Sphere": "sphere",
    "Part::Torus": "torus",
    "Part::Helix": "coil",
    "Part::Extrusion": "extrude",
    "Part::Revolution": "revolve",
    "Part::Loft": "loft",
    "Part::Sweep": "sweep",
    "Part::Fillet": "fillet",
    "Part::Chamfer": "chamfer",
    "Part::Thickness": "shell",
    "Part::Mirroring": "mirror",
    "Part::Fuse": "combine",
    "Part::Cut": "combine",
    "Part::Common": "combine",
    "Part::MultiFuse": "combine",
    "Part::MultiCommon": "combine",
}

# SciForge's own Python features report "SciForge::<SciForgeType>".
KIND_BY_SCIFORGE_TYPE = {
    "PressPull": "presspull",
    "Extrude": "extrude",
    "OffsetFace": "offset_face",
    "ReplaceFace": "replace_face",
    "SplitBody": "split_body",
    "SplitFace": "split_face",
    "RectangularPattern": "pattern_rect",
    "CircularPattern": "pattern_circ",
    "Move": "move",
    "MoveCopy": "move",
}

# Steps that are not a solid: they never carry the history marker (FreeCAD's Tip).
NON_SOLID_KINDS = {"sketch", "plane", "axis", "point", "ucs", "derive", "group"}


def _words(camel):
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", camel).strip()


def classify(type_id):
    """Kind of a step from its FreeCAD TypeId (or "SciForge::<Type>")."""
    kind = KIND_BY_TYPEID.get(type_id)
    if kind:
        return kind
    if type_id.startswith("SciForge::"):
        name = type_id.split("::", 1)[1]
        if name in KIND_BY_SCIFORGE_TYPE:
            return KIND_BY_SCIFORGE_TYPE[name]
        low = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name).lower()
        if low in KINDS:
            return low
        return "other"
    if type_id.startswith(("PartDesign::Additive", "PartDesign::Subtractive")):
        return "primitive"
    return "other"


def title_base(type_id, kind):
    """Fusion's name for the step ("Extrude", "Press Pull", ...)."""
    if kind == "other" and type_id.startswith("SciForge::"):
        return _words(type_id.split("::", 1)[1]) or KINDS["other"][0]
    return KINDS.get(kind, KINDS["other"])[0]


def icon_for(kind):
    return KINDS.get(kind, KINDS["other"])[1]


def is_solid(kind):
    return kind not in NON_SOLID_KINDS


def _strip(text):
    return re.sub(r"[\s_]*\d+$", "", text or "").strip().lower()


def is_default_label(label, name):
    """True while the user has not renamed the step: FreeCAD's labels are the object
    name with a number ("Pad", "Pad001"); a renamed step shows its own name."""
    if not label or label == name:
        return True
    return _strip(label) == _strip(name)


@dataclass(frozen=True)
class Item:
    index: int
    name: str
    label: str
    type_id: str
    kind: str
    title: str  # "Extrude 2": Fusion's name, numbered per kind
    display: str  # what the timeline calls it: the title, or the user's own name
    body: object  # body name or None (a step outside any body)
    solid: bool
    state: str  # "done" | "rolled_back"
    suppressed: bool = False
    status: str = "ok"  # "ok" | "warning" | "error"
    message: str = ""
    key: float = 0.0
    deps: tuple = field(default=())
    group: str = ""  # timeline group id ("" = not in a group)
    group_name: str = ""

    @property
    def icon(self):
        return icon_for(self.kind)


@dataclass(frozen=True)
class Timeline:
    items: tuple
    marker: int  # slot of the history marker: number of steps before it
    tips: dict  # body name -> tip name (or None)

    @property
    def at_end(self):
        return self.marker >= len(self.items)

    def names(self):
        return [i.name for i in self.items]

    def find(self, name):
        for item in self.items:
            if item.name == name:
                return item
        return None


def merge(features):
    """Merge per-body step lists into one row by creation order.

    A body's own order is never changed. Each step is ranked by the smallest key
    from it to the end of its body (so a step inserted at the marker while rolled
    back stays at the marker), then the lists are merged like sorted lists."""
    sequences = {}
    order = []
    for f in features:
        body = f.get("body")
        if body not in sequences:
            sequences[body] = []
            order.append(body)
        sequences[body].append(f)
    effective = {}
    for body, seq in sequences.items():
        low = None
        for f in reversed(seq):
            key = float(f.get("key", 0))
            low = key if low is None else min(low, key)
            effective[id(f)] = low
    heads = {body: 0 for body in order}
    merged = []
    while True:
        best = None
        for rank, body in enumerate(order):
            seq = sequences[body]
            i = heads[body]
            if i >= len(seq):
                continue
            f = seq[i]
            sort = (effective[id(f)], float(f.get("key", 0)), rank)
            if best is None or sort < best[0]:
                best = (sort, body)
        if best is None:
            return merged
        body = best[1]
        merged.append(sequences[body][heads[body]])
        heads[body] += 1


def _status(f):
    if f.get("error"):
        return "error", f["error"]
    if f.get("warning"):
        return "warning", f["warning"]
    return "ok", ""


def build(features, tips):
    """The whole timeline. ``tips``: {body name: tip name or None}."""
    rows = merge(features)
    kinds = [classify(f["type_id"]) for f in rows]
    # A step outside any body has no Tip: it never rolls back.
    solid = [is_solid(k) and f.get("body") is not None for f, k in zip(rows, kinds)]
    positions = {}
    for f in rows:
        positions.setdefault(f.get("body"), []).append(f["name"])
    active = {}
    for i, f in enumerate(rows):
        if not solid[i]:
            continue
        body = f.get("body")
        tip = tips.get(body, "<none>")
        seq = positions.get(body, [])
        if tip == "<none>" or (tip is not None and tip not in seq):
            active[i] = True  # no information: the step is computed
        elif tip is None:
            active[i] = False
        else:
            active[i] = seq.index(f["name"]) <= seq.index(tip)
    inactive = [i for i in active if not active[i]]
    marker = min(inactive) if inactive else len(rows)

    counts = {}
    items = []
    for i, f in enumerate(rows):
        kind = kinds[i]
        base = title_base(f["type_id"], kind)
        counts[base] = counts.get(base, 0) + 1
        title = "%s %d" % (base, counts[base])
        label = f.get("label", f["name"])
        display = title if is_default_label(label, f["name"]) else label
        if solid[i]:
            state = "done" if active[i] else "rolled_back"
        elif f.get("body") is None:
            state = "done"
        else:
            state = "done" if i < marker else "rolled_back"
        status, message = _status(f)
        items.append(
            Item(
                index=i,
                name=f["name"],
                label=label,
                type_id=f["type_id"],
                kind=kind,
                title=title,
                display=display,
                body=f.get("body"),
                solid=solid[i],
                state=state,
                suppressed=bool(f.get("suppressed")),
                status=status,
                message=message,
                key=float(f.get("key", 0)),
                deps=tuple(f.get("deps", ())),
                group=f.get("group") or "",
                group_name=f.get("group_name") or "",
            )
        )
    return Timeline(tuple(items), marker, dict(tips))


def tooltip(item):
    """Hover text: the step's name, then why it is red/yellow or that it is off."""
    lines = [item.display]
    if item.display != item.title:
        lines.append(item.title)
    if item.suppressed:
        lines.append("Suppressed")
    elif item.state == "rolled_back":
        lines.append("After the history marker (not computed)")
    if item.status == "error":
        lines.append("Error: " + item.message)
    elif item.status == "warning":
        lines.append("Warning: " + item.message)
    return "\n".join(lines)


def signature(timeline, extra=None):
    """Cheap value to compare between refreshes to detect any change."""
    return (
        extra,
        timeline.marker,
        tuple(
            (i.name, i.display, i.kind, i.state, i.suppressed, i.status, i.message, i.group)
            for i in timeline.items
        ),
        tuple(sorted({(i.group, i.group_name) for i in timeline.items if i.group})),
    )


# -- groups ----------------------------------------------------------------------------
def segments(timeline, expanded=()):
    """What the timeline row shows: ("step", item) and ("group", id, name, [items],
    open). A group is a run of neighbouring steps with the same group id; it shows
    as one folder unless it is open (in ``expanded``) or the marker is inside it."""
    out = []
    items = list(timeline.items)
    i = 0
    while i < len(items):
        item = items[i]
        if not item.group:
            out.append(("step", item))
            i += 1
            continue
        j = i
        while j < len(items) and items[j].group == item.group:
            j += 1
        run = items[i:j]
        marker_inside = i < timeline.marker < j
        opened = item.group in expanded or marker_inside
        out.append(("group", item.group, item.group_name or "Group", run, opened))
        i = j
    return out


def can_group(timeline, names):
    """Fusion groups neighbouring steps that are not in a group yet. Returns
    (ok, reason)."""
    if len(names) < 2:
        return False, "Select two or more neighbouring steps (Shift+click)."
    index = {item.name: k for k, item in enumerate(timeline.items)}
    picks = sorted(index[n] for n in names if n in index)
    if len(picks) != len(names):
        return False, "Unknown step."
    if picks != list(range(picks[0], picks[-1] + 1)):
        return False, "Only neighbouring steps can be grouped."
    if any(timeline.items[k].group for k in picks):
        return False, "Some of these steps are already in a group."
    return True, ""


def new_group_id(timeline):
    used = {i.group for i in timeline.items if i.group}
    n = 1
    while "g%d" % n in used:
        n += 1
    return "g%d" % n


def new_group_name(timeline):
    names = {i.group_name for i in timeline.items if i.group}
    n = 1
    while "Group %d" % n in names:
        n += 1
    return "Group %d" % n


def groups_after_move(timeline, plan):
    """{name: group id} if the moved step's group changes: dragged out of its group
    it leaves it; dropped between two steps of a group it joins that group."""
    by_name = {i.name: i for i in timeline.items}
    order = list(plan.order)
    if plan.name not in by_name or plan.name not in order:
        return {}
    k = order.index(plan.name)
    item = by_name[plan.name]
    before = by_name[order[k - 1]].group if k > 0 else ""
    after = by_name[order[k + 1]].group if k + 1 < len(order) else ""
    if before and before == after and before != item.group:
        return {plan.name: before}
    if item.group and item.group not in (before, after):
        return {plan.name: ""}
    return {}


# -- the history marker ------------------------------------------------------------
def _solid_indexes(timeline):
    return [i for i, item in enumerate(timeline.items) if item.solid]


def tips_for_count(timeline, count):
    """{body: tip} so that the first ``count`` solid steps of the row are active."""
    solids = _solid_indexes(timeline)
    active = set(solids[:count])
    tips = {}
    for i, item in enumerate(timeline.items):
        if item.body is None:
            continue
        tips.setdefault(item.body, None)
        if item.solid and i in active:
            tips[item.body] = item.name
    return tips


def active_count(timeline):
    """How many solid steps are before the marker."""
    return len([i for i in _solid_indexes(timeline) if i < timeline.marker])


def _consistent(timeline):
    """True when exactly the solids before the marker are active."""
    for i in _solid_indexes(timeline):
        if (timeline.items[i].state == "done") != (i < timeline.marker):
            return False
    return True


def tips_for_slot(timeline, slot):
    """{body: tip} for the marker dropped after ``slot`` steps. The marker cannot go
    before the first solid step (FreeCAD needs one to show anything), so it snaps
    after it. None when nothing would change."""
    solids = _solid_indexes(timeline)
    if not solids:
        return None
    count = max(1, len([i for i in solids if i < slot]))
    if count == active_count(timeline) and _consistent(timeline):
        return None
    return tips_for_count(timeline, count)


def tips_for_item(timeline, index):
    """'Roll History Marker Here': the marker goes right after step ``index``."""
    return tips_for_slot(timeline, index + 1)


def tips_for_step(timeline, where):
    """Playback buttons: "start" | "prev" | "next" | "end". None if nowhere to go."""
    solids = _solid_indexes(timeline)
    if not solids:
        return None
    current = active_count(timeline)
    if where == "start":
        count = 1
    elif where == "end":
        count = len(solids)
    elif where == "prev":
        count = current - 1
    elif where == "next":
        count = current + 1
    else:
        raise ValueError("unknown step %r" % where)
    if count < 1 or count > len(solids):
        return None
    if count == current and _consistent(timeline):
        return None
    return tips_for_count(timeline, count)


def can_roll_forward(timeline):
    return not timeline.at_end


# -- reordering ----------------------------------------------------------------------
@dataclass(frozen=True)
class MovePlan:
    ok: bool
    reason: str
    order: tuple = ()  # all names in the new row order
    body_orders: dict = field(default_factory=dict)  # body -> names in new body order
    keys: dict = field(default_factory=dict)  # name -> new creation-order key
    marker_count: int = 0  # solid steps before the marker after the move
    marker_at_end: bool = True
    name: str = ""  # the step that moves


def plan_move(timeline, name, slot):
    """Move step ``name`` so that ``slot`` steps of the row are before it (``slot``
    counts positions in the row as it is now, 0..len). Refuses moves that put a step
    before something it uses, like Fusion. Returns a MovePlan."""
    items = list(timeline.items)
    moving = timeline.find(name)
    if moving is None:
        return MovePlan(False, "Unknown step.")
    old = moving.index
    others = [i for i in items if i.name != name]
    # Slot in the list without the moving step.
    target = slot if slot <= old else slot - 1
    target = max(0, min(target, len(others)))
    new_items = others[:target] + [moving] + others[target:]
    order = tuple(i.name for i in new_items)
    if order == tuple(i.name for i in items):
        return MovePlan(False, "", order, name=name)
    pos = {n: k for k, n in enumerate(order)}
    titles = {i.name: i.display for i in items}
    for item in new_items:
        for dep in item.deps:
            if dep in pos and pos[dep] > pos[item.name]:
                if item.name == name:
                    reason = "%s uses %s, so it cannot come before it." % (
                        titles[name],
                        titles[dep],
                    )
                else:
                    reason = "%s uses %s, so %s cannot move after it." % (
                        titles[item.name],
                        titles[name],
                        titles[name],
                    )
                return MovePlan(False, reason, order, name=name)
    body_orders = {}
    for item in new_items:
        if item.body is not None:
            body_orders.setdefault(item.body, []).append(item.name)
    body_orders = {b: tuple(v) for b, v in body_orders.items()}
    keys = _keys_for(new_items, name)
    # Keep the marker between the same steps: the moving step is before it when it
    # lands left of where the marker was.
    before_marker = [i for i in items[: timeline.marker] if i.name != name]
    marker_slot = len(before_marker)  # in the list without the moving step
    lands_before = target < marker_slot or (target == marker_slot and timeline.at_end)
    count = len([i for i in before_marker if i.solid])
    if moving.solid and lands_before:
        count += 1
    return MovePlan(
        True,
        "",
        order,
        body_orders,
        keys,
        marker_count=count,
        marker_at_end=timeline.at_end,
        name=name,
    )


def _keys_for(new_items, moved=None):
    """Creation-order keys that make merge() give exactly ``new_items``' order (only
    needed when steps of different bodies change places). Prefer a new key for the
    moved step alone; otherwise make keys grow along the row, changing only the steps
    that are out of order."""
    wanted = [i.name for i in new_items]
    rows = [{"name": i.name, "body": i.body, "key": i.key} for i in new_items]
    if [r["name"] for r in merge(rows)] == wanted:
        return {}
    if moved in wanted:
        k = wanted.index(moved)
        lo = max([i.key for i in new_items[:k]], default=None)
        hi = min([i.key for i in new_items[k + 1 :]], default=None)
        if lo is None and hi is not None:
            key = hi / 2.0
        elif hi is None and lo is not None:
            key = lo + 0.5
        elif lo is not None and lo < hi:
            key = (lo + hi) / 2.0
        else:
            key = None
        if key is not None and key > 0:
            trial = [dict(r, key=key) if r["name"] == moved else r for r in rows]
            if [r["name"] for r in merge(trial)] == wanted:
                return {moved: key}
    keys = [i.key for i in new_items]
    changed = {}
    prev = None
    for k, item in enumerate(new_items):
        if prev is None or keys[k] > prev:
            prev = keys[k]
            continue
        # next step that keeps its key and is above prev
        nxt = None
        for j in range(k + 1, len(new_items)):
            if keys[j] > prev:
                nxt = (j, keys[j])
                break
        if nxt is None:
            value = prev + 0.5
        else:
            value = prev + (nxt[1] - prev) / (nxt[0] - k + 1)
        keys[k] = value
        changed[item.name] = value
        prev = value
    return changed


def rebased(old_timeline, plan):
    """Solid steps whose previous solid in their body changes with the move: their
    edges/faces must still exist on the new base."""

    def previous(order_names, body_of):
        result = {}
        last = {}
        for n in order_names:
            item = body_of.get(n)
            if item is None or not item.solid:
                continue
            result[n] = last.get(item.body)
            last[item.body] = n
        return result

    by_name = {i.name: i for i in old_timeline.items}
    before = previous(old_timeline.names(), by_name)
    after = previous(plan.order, by_name)
    return {n: after[n] for n in after if after[n] != before.get(n)}
