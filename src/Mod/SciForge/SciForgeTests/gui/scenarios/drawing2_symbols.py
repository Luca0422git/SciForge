# SPDX-License-Identifier: LGPL-2.1-or-later
"""Leader, Feature Control Frame, Datum Identifier and Surface Texture (the TEXT and
SYMBOLS groups of the DRAWING tab), with real clicks and typing.

The plate (drawing_fixtures.plate), ISO A3, base view Top at 1:1.

A  TEXT > Leader; a click on empty paper is refused (click an edge); the bottom edge,
   then a place below right; the text typed: a leader with its arrow on the edge and
   the text beside a landing. OK.
B  SYMBOLS > Feature Control Frame: tolerance 0.05, Maximum material, datums A and B;
   click hole 1's circle, then the frame's place: "Position | dia 0.05 (M) | A | B" with
   a leader to the hole. A tolerance that is not a number is refused in the dialog.
C  SYMBOLS > Datum Identifier: letter A by default; on the bottom edge, its box below.
   A second one on the left edge: B by default (A is taken).
D  SYMBOLS > Surface Texture: Ra 1.6, lay "=", on the top edge (the symbol stands on
   it). OK.
E  Double-click the frame: its dialog with its values; Composite: a second row 0.02 to
   A; OK: two rows. Undo: one row again; Redo: two.
F  Undo the datum B, Redo; the view moved by dragging: the leader, the frame and the
   datums go with it.
G  The DXF has the leader's text, the frame's values, the datum letters and Ra 1.6.
"""

import os


from SciForgeTests.gui import drawing2_steps as w
from SciForgeTests.gui import drawing_input as d
from SciForgeTests.gui import harness as h

state = {}


def one(kind):
    found = w.annotations(kind)
    return found[-1] if found else None


def data(obj):
    from sciforge import drawing_annot

    return drawing_annot.annotation_data(obj)


# -- A ------------------------------------------------------------------------------------------
def a_command():
    w.menu("TEXT", "Leader")


a_command.wait_ms = 1200


def a_paper():
    p = d.panel_of("LeaderPanel")
    if h.check("the Leader dialog", p is not None, d.panel()):
        d.click_at(380, 250)


def a_refused():
    p = d.panel_of("LeaderPanel")
    h.check(
        "asks for an edge", p is not None and "edge" in p.message.text(), p and p.message.text()
    )
    w.click(10.0, -25.0)  # the bottom edge


def a_place():
    w.move(35.0, -40.0)
    w.click(40.0, -45.0)


a_place.wait_ms = 1200


def a_type():
    p = d.panel_of("LeaderPanel")
    if h.check("a leader was made", one("leader") is not None and p is not None):
        d.type_into(p.text, "BREAK ALL SHARP EDGES")


def a_ok():
    obj = one("leader")
    h.check("its text", data(obj).get("lines") == ["BREAK ALL SHARP EDGES"], data(obj))
    w.ok()


a_ok.wait_ms = 1500


def a_check():
    from sciforge import drawing, drawing_annot

    obj = one("leader")
    h.check("closed", d.panel() is None)
    anchor = data(obj)["anchor"]
    h.check("on a straight edge", anchor["kind"] == "line", anchor)
    point = drawing_annot.anchor_point(anchor)
    h.check("on the bottom edge", abs(point[1] + 25.0) < 1e-6, point)
    prims = drawing_annot.prims_of(obj)
    arrow = [p for p in prims if p[0] == "poly"][0]
    tip = arrow[1][0]
    expect = drawing.local_to_page(w.base(), point)
    h.check(
        "its arrow on the edge", abs(tip[0] - expect[0]) < 1e-6 and abs(tip[1] - expect[1]) < 1e-6
    )
    h.check("its label", obj.Label == "Leader: BREAK ALL SHARP EDGES", obj.Label)


# -- B ------------------------------------------------------------------------------------------
def b_command():
    w.menu("SYMBOLS", "Feature Control Frame")


b_command.wait_ms = 1200


def b_fields():
    p = d.panel_of("FeatureControlPanel")
    if not h.check("the frame's dialog", p is not None, d.panel()):
        return
    h.check("Position by default", p.char.currentText() == "Position")
    row = p.rows[0]
    h.check("a round zone by default", row["dia"].isChecked())
    d.type_into(row["tol"], "0.05")
    d.choose(row["mod"], "Maximum material (M)")
    d.type_into(row["datums"][0][0], "A")
    d.type_into(row["datums"][1][0], "B")


b_fields.wait_ms = 1200


def b_pick():
    w.click(*w.hole_top(w.HOLE1))


def b_place():
    w.move(-55.0, 15.0)
    w.click(-70.0, 20.0)


b_place.wait_ms = 1200


def b_made():
    obj = one("fcf")
    if h.check("a frame", obj is not None):
        h.check("what it says", w.describe(obj) == "Position|⌀0.05(M)|A|B", w.describe(obj))
        h.check("on hole 1's circle", data(obj)["anchor"]["kind"] == "circle", data(obj)["anchor"])
    p = d.panel_of("FeatureControlPanel")
    d.type_into(p.rows[0]["tol"], "abc")


def b_refused():
    p = d.panel_of("FeatureControlPanel")
    h.check(
        "not a number: said", p is not None and "number" in p.message.text(), p and p.message.text()
    )
    w.ok()


def b_stays():
    p = d.panel_of("FeatureControlPanel")
    if h.check("OK refused", p is not None):
        d.type_into(p.rows[0]["tol"], "0.05")
        w.ok()


b_stays.wait_ms = 1500


def b_done():
    h.check("closed", d.panel() is None)
    h.check("still 0.05", "0.05" in w.describe(one("fcf")), w.describe(one("fcf")))


# -- C ------------------------------------------------------------------------------------------
def datum_steps(name, edge_point, place, letter):
    def command():
        w.menu("SYMBOLS", "Datum Identifier")

    command.wait_ms = 1200

    def pick():
        p = d.panel_of("DatumPanel")
        if h.check("%s: the datum's dialog" % name, p is not None, d.panel()):
            h.check(
                "%s: letter %s by default" % (name, letter),
                p.letter.text() == letter,
                p.letter.text(),
            )
            w.click(*edge_point)

    def put():
        w.click(*place)

    put.wait_ms = 1200

    def close():
        w.ok()

    close.wait_ms = 1200

    def made():
        found = [o for o in w.annotations("datum") if data(o).get("letter") == letter]
        h.check(
            "%s: datum %s" % (name, letter),
            len(found) == 1,
            [data(o) for o in w.annotations("datum")],
        )
        if found:
            state[name] = found[0].Name
            h.check("%s: its label" % name, found[0].Label == "Datum %s" % letter, found[0].Label)

    steps = [command, pick, put, close, made]
    for step in steps:
        step.__name__ = "c_%s_%s" % (name, step.__name__)
    return steps


# -- D ------------------------------------------------------------------------------------------
def d_command():
    w.menu("SYMBOLS", "Surface Texture")


d_command.wait_ms = 1200


def d_fields():
    p = d.panel_of("SurfaceTexturePanel")
    if not h.check("the texture's dialog", p is not None, d.panel()):
        return
    d.type_into(p.value, "Ra 1.6")
    d.choose(p.lay, "=")
    w.click(-10.0, 25.0)  # the top edge


d_fields.wait_ms = 1200


def d_place():
    w.click(-9.6, 25.5)  # next to where the edge was clicked: on the edge


d_place.wait_ms = 1200


def d_ok():
    w.ok()


d_ok.wait_ms = 1200


def d_check():
    from sciforge import drawing_annot

    obj = one("texture")
    if not h.check("a surface texture", obj is not None):
        return
    h.check(
        "what it says",
        w.describe(obj) == "Material removal required, Ra 1.6, lay =",
        w.describe(obj),
    )
    prims = drawing_annot.prims_of(obj)
    h.check("no leader: it stands on the edge", not [p for p in prims if p[0] == "poly"])


# -- E ------------------------------------------------------------------------------------------
def e_open():
    d.double_click_at(*w.annotation_point(one("fcf")))


e_open.wait_ms = 1500


def e_dialog():
    p = d.panel_of("FeatureControlPanel")
    if not h.check("the frame's dialog again", p is not None, d.panel()):
        return
    h.check(
        "its values", p.rows[0]["tol"].text() == "0.05" and p.rows[0]["datums"][1][0].text() == "B"
    )
    h.check("row 2 hidden", not p.rows[1]["tol"].isVisibleTo(p.form))
    w.toggle(p.composite)


def e_row2():
    p = d.panel_of("FeatureControlPanel")
    if not h.check("row 2 shown", p is not None and p.rows[1]["tol"].isVisibleTo(p.form)):
        return
    d.type_into(p.rows[1]["tol"], "0.02")
    d.type_into(p.rows[1]["datums"][0][0], "A")


def e_ok():
    h.check(
        "two rows",
        w.describe(one("fcf")) == "Position|⌀0.05(M)|A|B / Position|⌀0.02|A",
        w.describe(one("fcf")),
    )
    w.ok()


e_ok.wait_ms = 1500


def e_undo():
    d.undo()


e_undo.wait_ms = 1500


def e_undone():
    h.check(
        "undo: one row", w.describe(one("fcf")) == "Position|⌀0.05(M)|A|B", w.describe(one("fcf"))
    )
    d.redo()


e_undone.wait_ms = 1500


def e_redone():
    h.check("redo: two rows", " / " in w.describe(one("fcf")), w.describe(one("fcf")))


# -- F ------------------------------------------------------------------------------------------
def f_undo():
    state["datums"] = len(w.annotations("datum"))
    d.undo()  # (the frame's edit)
    d.undo()  # the surface texture
    d.undo()  # datum B


f_undo.wait_ms = 2000


def f_undone():
    h.check("undo: datum B gone", len(w.annotations("datum")) == state["datums"] - 1)
    d.redo()
    d.redo()
    d.redo()


f_undone.wait_ms = 2000


def f_redone():
    h.check("redo: back", len(w.annotations("datum")) == state["datums"])
    from sciforge import drawing

    state["before"] = {o.Name: (o.X.Value, o.Y.Value) for o in w.annotations()}
    state["base"] = drawing.view_position(w.base())
    x, y = state["base"]
    # by its frame, just outside the outline (drawing_views does the same)
    d.drag_page((x + 41.5, y + 26.5), (x + 56.5, y + 36.5))


f_redone.wait_ms = 2500


def f_moved():
    from sciforge import drawing

    x, y = drawing.view_position(w.base())
    dx, dy = x - state["base"][0], y - state["base"][1]
    h.check("the view moved", abs(dx) > 5 or abs(dy) > 5, (dx, dy))
    for obj in w.annotations():
        old = state["before"].get(obj.Name)
        if old is None:
            continue
        h.check(
            "%s went with it" % obj.Label,
            abs(obj.X.Value - old[0] - dx) < 0.05 and abs(obj.Y.Value - old[1] - dy) < 0.05,
            (obj.X.Value - old[0], obj.Y.Value - old[1], dx, dy),
        )
    h.shot("f-moved")


# -- G ------------------------------------------------------------------------------------------
def g_dxf():
    from sciforge import drawing, drawing_core

    folder = os.path.join(h.OUT_DIR, "drawing2")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "symbols.dxf")
    drawing.export_dxf(d.page(), path)
    with open(path, encoding="utf-8") as handle:
        ents = drawing_core.read_dxf_entities(handle.read())
    words = [e[1].get(1, [""])[0] for e in ents if e[0] == "TEXT"]
    for word in ("BREAK ALL SHARP EDGES", "0.05", "0.02", "Ra 1.6", "B"):
        h.check("the DXF has %s" % word, word in words, words)
    layers = {e[1].get(8, [""])[0] for e in ents}
    h.check("a SYMBOLS layer", "SYMBOLS" in layers, layers)


h.run(
    "drawing2_symbols",
    [w.new_design("Sym")]
    + w.sheet_steps()
    + [d.wait_geometry(1500)]
    + [a_command, a_paper, a_refused, a_place, a_type, a_ok, a_check]
    + [b_command, b_fields, b_pick, b_place, b_made, b_refused, b_stays, b_done]
    + datum_steps("first", (-20.0, -25.0), (-20.0, -42.0), "A")
    + datum_steps("second", (-40.0, 0.0), (-58.0, 0.0), "B")
    + [d_command, d_fields, d_place, d_ok, d_check]
    + [e_open, e_dialog, e_row2, e_ok, e_undo, e_undone, e_redone]
    + [f_undo, f_undone, f_redone, f_moved]
    + [g_dxf],
)
