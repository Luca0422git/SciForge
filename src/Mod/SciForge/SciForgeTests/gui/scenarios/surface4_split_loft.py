# SPDX-License-Identifier: LGPL-2.1-or-later
"""SURFACE > MODIFY > Split Body with a LOFTED surface (the hybrid workflow), then a split of
the lofted surface itself, real input.

A 40 x 30 x 20 box (solid) and a lofted surface body between two lines that cross the box:
at y = -5 the line z = 5 (x -5..45), at y = 35 the line rising from z 10 to z 18: a twisted
ruled surface z = 5 + 5v + 8uv (u = (x + 5) / 50, v = (y + 5) / 40). Below it in the box
lies 2000 x 5.7 = 11400, above 12600.

Path 1: SURFACE tab, MODIFY > Split Body: click the box, then the loft where it sticks out in
front of the box: the whole loft is the tool; two pieces, 11400 and 12600; OK: a "Split
Body" step, the loft stays a surface. Path 2 (edit): double-click the step in the timeline,
turn Extend Splitting Tool off: the loft's edges are all outside the box, so the pieces are
the same; OK. Path 3 (a surface body split, a refusal): Split Body, click the loft (the body
to split), click the box's top face: the plane z = 20 does not reach the loft (it rises to
18): the dialog says why; click the top face again (it drops), click the box's right face
(x = 40): the loft falls into two surface bodies at x = 40 (areas checked by integrating the
loft's area element); OK. Undo: the loft whole again; Redo.
"""

import math

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import bodies_steps as bs
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import surface4_steps as s4
from SciForgeTests.gui import surface_steps as st

V = App.Vector
s = {}
BOX = 24000.0
BELOW = 11400.0
IN_FRONT = V(20, -2.5, 5 + 5 * 0.0625 + 8 * 0.5 * 0.0625)  # on the loft, in front of the box


def loft_area(u0, u1, n=200):
    """The loft's area for u0 <= u <= u1 (all v), by Simpson's rule over |Pu x Pv| =
    |(-320 v, -50 (5 + 8u), 2000)|."""

    def f(u, v):
        return math.sqrt((320 * v) ** 2 + (50 * (5 + 8 * u)) ** 2 + 2000.0**2)

    def weights(k):
        return 1 if k in (0, n) else (4 if k % 2 else 2)

    du, dv = (u1 - u0) / n, 1.0 / n
    total = 0.0
    for i in range(n + 1):
        for j in range(n + 1):
            total += weights(i) * weights(j) * f(u0 + i * du, j * dv)
    return total * du * dv / 9.0


def doc():
    return App.ActiveDocument


def split_panel():
    from sciforge import split_ui

    p = split_ui.SplitPanel.last
    return p if p is not None and not p._closed else None


def settle():
    st.settle()
    h.idle_step()()


def setup():
    from sciforge import bodies, extrude, surface

    s4.new_design("Surface4SplitLoft")
    sk = s4.sketch([(0, 0), (40, 0), (40, 30), (0, 30)])
    box_body = bodies.body_of(sk)
    extrude.make(box_body, sk, {"distance": 20.0})
    doc().recompute()
    bodies.set_shown(sk, False)
    s["box"] = box_body
    # the XZ plane's normal is -y: offset 5 is y = -5, offset -35 is y = 35
    a = s4.sketch([(-5, 5), (45, 5)], plane="XZ_Plane", closed=False, body=box_body, offset=5)
    b = s4.sketch([(-5, 10), (45, 18)], plane="XZ_Plane", closed=False, body=box_body, offset=-35)
    step = surface.build("loft", {"refs": [(a, "Edge1"), (b, "Edge1")]}, {"groups": [1, 1]})
    doc().recompute()
    for sketch in (a, b):
        bodies.set_shown(sketch, False)
    s["loft"] = bodies.body_of(step)
    s["loft_area"] = st.area(s["loft"])
    h.fit()
    h.check("a 24000 box", st.near(st.volume(s["box"]), BOX), st.volume(s["box"]))
    h.check("the loft is a surface body", surface.is_surface_body(s["loft"]))
    h.check(
        "the loft's area by integration",
        st.near(s["loft_area"], loft_area(0.0, 1.0), 1e-6),
        (s["loft_area"], loft_area(0.0, 1.0)),
    )


def split_menu():
    st.tab("SURFACE")
    Gui.Selection.clearSelection()
    st.menu("MODIFY", "Split Body")


def click_box():
    h.check("the Split Body dialog", split_panel() is not None)
    h.click(V(40, 25, 3))


def click_loft():
    p = split_panel()
    h.check(
        "the box is the body to split",
        p is not None and p.options["body"] is s["box"],
        p and p.options["body"],
    )
    h.click(IN_FRONT)


def volumes_of(p):
    from sciforge import split

    feature = p.target if p is not None else None
    others = split.piece_bodies(feature) if feature is not None else []
    return others, sorted([st.volume(s["box"])] + [st.volume(b) for b in others])


def pieces():
    settle()
    p = split_panel()
    h.check(
        "the whole loft is the tool",
        p is not None and p.options["tools"] == [(s["loft"], "")],
        p and p.options["tools"],
    )
    others, vols = volumes_of(p)
    h.check("one new body", len(others) == 1, others)
    h.check("below the loft 11400", st.near(vols[0], BELOW, 1e-6), vols)
    h.check("above it 12600", st.near(vols[1], BOX - BELOW, 1e-6), vols)
    h.check(
        "the box's body keeps the bigger piece",
        st.near(st.volume(s["box"]), BOX - BELOW, 1e-6),
        st.volume(s["box"]),
    )
    h.shot("1-split-by-loft")
    st.ok()


def split_done():
    from sciforge import split, surface

    h.check("dialog closed", split_panel() is None)
    feature = next((o for o in doc().Objects if split.is_split(o)), None)
    h.check("a Split Body step", feature is not None)
    s["piece"] = split.piece_bodies(feature)[0] if feature is not None else None
    h.check("the loft is still a surface body", surface.is_surface_body(s["loft"]))
    titles = st.timeline_titles()
    s["title"] = next((t for t in titles if t.startswith("Split Body")), None)
    h.check("Split Body in the timeline", s["title"] is not None, titles)
    if s["title"]:
        st.double_click_timeline(s["title"])


def edit_open():
    settle()
    p = split_panel()
    h.check("Edit Split Body open", p is not None and p.editing, p)
    h.check("Extend Splitting Tool on", p is not None and p.extend.isChecked())
    if p is not None:
        bs.toggle(p.extend)


def extend_off():
    settle()
    p = split_panel()
    h.check("Extend off", p is not None and not p.extend.isChecked())
    h.check("no refusal", p is not None and not p.message.text(), p and p.message.text())
    others, vols = volumes_of(p)
    h.check(
        "the same pieces: the loft's edges are outside the box",
        len(others) == 1 and st.near(vols[0], BELOW, 1e-6) and st.near(vols[1], BOX - BELOW),
        vols,
    )
    st.ok()


def edited():
    from sciforge import split

    h.check("dialog closed", split_panel() is None)
    feature = next((o for o in doc().Objects if split.is_split(o)), None)
    h.check(
        "Extend Splitting Tool off is kept",
        feature is not None and not split.read(feature)["extend"],
    )
    h.check("still 12600 in the box", st.near(st.volume(s["box"]), BOX - BELOW, 1e-6))
    split_menu()


def click_loft_to_split():
    h.check("a new Split Body dialog", split_panel() is not None and not split_panel().editing)
    h.click(IN_FRONT)


def click_top():
    p = split_panel()
    h.check(
        "the loft is the body to split",
        p is not None and p.options["body"] is s["loft"],
        p and p.options["body"],
    )
    h.click(V(20, 15, 20))


def top_refused():
    settle()
    p = split_panel()
    tools = p.options["tools"] if p is not None else []
    h.check("the top face is the tool", len(tools) == 1 and tools[0][1].startswith("Face"), tools)
    text = p.message.text() if p is not None else ""
    h.check("says the tool does not cut the loft in two", "does not cut" in text, text)
    h.check("no pieces made", p is not None and p.target is None, p and p.target)
    h.click(V(20, 15, 20))


def top_dropped():
    settle()
    p = split_panel()
    h.check("a second click drops the top face", p is not None and not p.options["tools"])
    h.click(V(40, 25, 3))


def loft_pieces():
    from sciforge import split, surface

    settle()
    p = split_panel()
    h.check("no refusal", p is not None and not p.message.text(), p and p.message.text())
    feature = p.target if p is not None else None
    others = split.piece_bodies(feature) if feature is not None else []
    h.check("one new body", len(others) == 1, others)
    if len(others) != 1:
        return
    piece = others[0]
    h.check("the loft keeps a surface", surface.is_surface_body(s["loft"]))
    h.check("the new piece is a surface body", surface.is_surface_body(piece))
    big, small = st.area(s["loft"]), st.area(piece)
    right = loft_area(0.9, 1.0)  # x 40..45
    h.check("the pieces make the loft", st.near(big + small, s["loft_area"], 1e-6))
    h.check(
        "the piece past x = 40: its area by integration",
        st.near(small, right, 1e-5),
        (small, right),
    )
    bb = piece.Shape.BoundBox
    h.check("it lies past x = 40", abs(bb.XMin - 40) < 1e-6 and abs(bb.XMax - 45) < 1e-6, bb)
    s["loft_piece"] = piece
    h.shot("2-loft-split")
    st.ok()


def loft_split_done():
    h.check("dialog closed", split_panel() is None)
    s["split_area"] = st.area(s["loft"])
    st.undo()


def undone():
    h.check(
        "undo: the loft whole",
        st.near(st.area(s["loft"]), s["loft_area"], 1e-6),
        st.area(s["loft"]),
    )
    st.redo()


def redone():
    h.check(
        "redo: split again",
        st.near(st.area(s["loft"]), s["split_area"], 1e-6),
        st.area(s["loft"]),
    )
    h.check("the box untouched", st.near(st.volume(s["box"]), BOX - BELOW, 1e-6))


h.run(
    "surface4_split_loft",
    [
        setup,
        split_menu,
        click_box,
        click_loft,
        pieces,
        split_done,
        edit_open,
        extend_off,
        edited,
        click_loft_to_split,
        click_top,
        top_refused,
        top_dropped,
        loft_pieces,
        loft_split_done,
        undone,
        redone,
    ],
)
