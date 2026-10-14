# SPDX-License-Identifier: LGPL-2.1-or-later
"""Components: the pure logic (no FreeCAD, no Qt), unit tested.

A design is a tree of "units": the root (None), components and bodies. The tree is given
as ``parents``: {unit name: name of the component it is in, or None for the root}.
Components are the names in ``components`` (a set); everything else in ``parents`` is a
body. Fusion's rules that these functions decide:

- Isolate hides everything but the picked unit, what is inside it and what is above it.
- A unit is "inside" a component when that component is one of its containers; the root
  contains everything.
- New components are named Component1, Component2 ... (Fusion's numbering: the number
  after the ones in use, like SciForge's bodies; renamed components do not count).
- A unit can be moved into any component that is not itself, not inside it, and not the
  one it is already in.
"""

import re


def next_label(labels, base="Component"):
    """The next free "Component<n>" name given the labels in use."""
    taken = set(labels)
    n = len([x for x in taken if re.match(r"^%s\d+$" % re.escape(base), x or "")]) + 1
    while "%s%d" % (base, n) in taken:
        n += 1
    return "%s%d" % (base, n)


def ancestors(parents, name):
    """Containers of a unit, nearest first (the root is not listed)."""
    found = []
    seen = set()
    current = parents.get(name)
    while current is not None and current not in seen:
        seen.add(current)
        found.append(current)
        current = parents.get(current)
    return found


def descendants(parents, name):
    """Every unit inside a component, at any depth."""
    found = []
    todo = [name]
    while todo:
        current = todo.pop()
        for unit, parent in parents.items():
            if parent == current and unit not in found:
                found.append(unit)
                todo.append(unit)
    return found


def is_inside(parents, name, component):
    """True when ``name`` lies in ``component`` (at any depth); the root holds all."""
    if component is None:
        return True
    return name == component or component in ancestors(parents, name)


def isolate_hidden(parents, target):
    """Names Isolate hides for ``target``: every other unit that is neither above it nor
    inside it (Fusion: "isolate selected bodies or components and hide all other
    objects")."""
    keep = {target} | set(ancestors(parents, target)) | set(descendants(parents, target))
    return [name for name in parents if name not in keep]


def move_targets(parents, components, moving):
    """Components (and the root, as None) the units ``moving`` may be moved into: not one
    of them, not inside one of them, and not the container they are all in already."""
    moving = list(moving)
    forbidden = set(moving)
    for name in moving:
        forbidden.update(descendants(parents, name))
    containers = {parents.get(name) for name in moving}
    same = containers.pop() if len(containers) == 1 else object()
    targets = []
    if same is not None:
        targets.append(None)
    for name in components:
        if name in forbidden or name == same:
            continue
        targets.append(name)
    return targets


def visible_steps(step_components, parents, active):
    """Which timeline steps show while ``active`` (a component name, or None for the root)
    is the active component: Fusion's timeline shows the active component's features and
    those of the components inside it. ``step_components``: {step name: the component the
    step belongs to (None for the root), or the step's own name for a component step}."""
    if active is None:
        return set(step_components)
    shown = set()
    for step, component in step_components.items():
        if component is None:
            continue
        if is_inside(parents, component, active):
            shown.add(step)
    return shown


def body_label(labels, base="Body"):
    """Fusion numbers bodies per component: the first body of a new component is Body1,
    the next one Body2. Every body already in the component counts (a renamed one, or the
    first root body that keeps FreeCAD's own "Body" label), the same rule as
    bodies._next_label, so Extrude's New Body and Combine's New Body name alike: with
    "Body" there, the next body is Body2, never a second "1"."""
    taken = set(labels)
    n = len(labels) + 1
    while "%s%d" % (base, n) in taken:
        n += 1
    return "%s%d" % (base, n)


def same_new(made, wanted):
    """True when the body a step made with operation `made` (as saved) still serves it for
    operation `wanted`. Switching between New Body and New Component moves the result (a
    body beside the source body, or a body in a new component), so the step's old body is
    not reused then; any other change keeps it (it decides elsewhere)."""
    news = ("new_body", "new_component")
    if made not in news or wanted not in news:
        return True
    return made == wanted


# -- instances (Copy / Paste of a component, patterns of components) ----------------------------
# Fusion names every occurrence of a component "<name>:<n>": the original is :1, a pasted
# instance :2, the next :3 ... (a pattern's copies too). Editing one changes all of them.
INSTANCE_RE = re.compile(r"^(?P<base>.*):(?P<n>\d+)$")


def instance_label(base, n):
    return "%s:%d" % (base, n)


def split_instance_label(label):
    """("Bracket", 2) for "Bracket:2"; (label, None) for a label without a number."""
    found = INSTANCE_RE.match(label or "")
    if not found:
        return label, None
    return found.group("base"), int(found.group("n"))


def next_instance_number(used):
    """The next free occurrence number (the original is 1, so instances start at 2)."""
    taken = {int(n) for n in used if n is not None}
    n = 2
    while n in taken:
        n += 1
    return n


def paste_new_label(label, labels):
    """Paste New makes an independent component named after the copied one: "Bracket (1)",
    then "Bracket (2)" ... (a guess at Fusion's naming)."""
    base = re.sub(r"\s*\(\d+\)$", "", split_instance_label(label)[0] or "Component")
    taken = set(labels)
    n = 1
    while "%s (%d)" % (base, n) in taken:
        n += 1
    return "%s (%d)" % (base, n)


# -- picking a component in the 3D view -------------------------------------------------------
def component_to_pick(chain, active):
    """The component a click picks when Move's Object type is Components (Fusion selects the
    occurrence just below the active component on the way to what was clicked).
    ``chain``: the containers of the clicked object, nearest first (names); ``active``: the
    active component (None: the root). None when the object lies in no component."""
    chain = list(chain)
    if not chain:
        return None
    if active is None or active not in chain:
        return chain[-1]
    index = chain.index(active)
    return chain[index - 1] if index > 0 else chain[0]


# -- Move: Set Pivot ---------------------------------------------------------------------------
def pivot_shift(rotation, distances, old_pivot, new_pivot):
    """Free Move turns about a pivot and then moves by the distances. Setting the pivot
    somewhere else must not move what was already moved: the distances change by
    (I - R)(old - new). ``rotation``: 3x3 rows; the rest (x, y, z)."""
    diff = [old_pivot[i] - new_pivot[i] for i in range(3)]
    turned = [sum(rotation[r][c] * diff[c] for c in range(3)) for r in range(3)]
    return tuple(distances[i] + diff[i] - turned[i] for i in range(3))


# -- the history marker and component steps ------------------------------------------------------
def placement_steps_in_effect(steps):
    """Fusion's captured moves of a component: which of them count where the history marker
    stands. ``steps``: [(name, done, suppressed)] in timeline order. Returns the names whose
    movement is applied, in order (a rolled-back or suppressed move is skipped)."""
    return [name for name, done, suppressed in steps if done and not suppressed]
