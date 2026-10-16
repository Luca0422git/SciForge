# SPDX-License-Identifier: LGPL-2.1-or-later
"""Selection rules inside an open sketch (no FreeCAD, no Qt: unit tested).

Fusion (Autodesk Community and Fusion's sketch course "Selecting sketch chained
entities"): a double-click on a sketch curve selects the chain of curves joined to it
end to end, without a window selection. SciForge's rule: every curve reachable from the
clicked one through shared end points (branches too), of the same kind as the clicked
curve (normal, construction or projected: Guess, a construction line touching a profile
is not part of the profile's chain). A closed curve (circle, ellipse, closed spline) is
a chain of its own.

A box drag in the sketch (FreeCAD's own window / crossing box): Fusion's modifiers, the
same as on the part (parity/selection.md): a plain box replaces the selection, Shift adds,
Ctrl adds what was not selected and removes what was.
"""

TOL = 1e-6


def _close(a, b, tol):
    return abs(a[0] - b[0]) <= tol and abs(a[1] - b[1]) <= tol


def chain(curves, start, tol=TOL):
    """The keys of the chain of `start`, in the order they are reached (start first).

    curves: {key: (kind, ends)}; ends: the (x, y) end points of an open curve, [] for a
    closed one. Only curves of start's kind join the chain."""
    if start not in curves:
        return []
    kind, _ends = curves[start]
    found = [start]
    seen = {start}
    frontier = [start]
    while frontier:
        nxt = []
        for key in frontier:
            ends = curves[key][1]
            if not ends:
                continue
            for other, (other_kind, other_ends) in curves.items():
                if other in seen or other_kind != kind or not other_ends:
                    continue
                if any(_close(a, b, tol) for a in ends for b in other_ends):
                    seen.add(other)
                    found.append(other)
                    nxt.append(other)
        frontier = nxt
    return found


def box_plan(shift, ctrl):
    """What a box drag does with the selection: "replace", "add" or "toggle"."""
    if ctrl:
        return "toggle"
    if shift:
        return "add"
    return "replace"


def toggled(before, boxed):
    """Ctrl + box: what was selected and not boxed, plus what was boxed and not selected
    (in a stable order: the old ones first)."""
    boxed_set = set(boxed)
    before_set = set(before)
    return [k for k in before if k not in boxed_set] + [k for k in boxed if k not in before_set]
