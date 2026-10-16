# SPDX-License-Identifier: LGPL-2.1-or-later
"""INSPECT > Curvature Map, Minimum Radius, Curvature Comb and Isocurve Analysis with real
input, on the box with its four top edges and three upright edges rounded (r = 4: where
three rounds meet the corner is a piece of a ball) and a round hole r = 5, 6 deep, cut
from the top.

Hand-derived colours: Gaussian curvature (k1 k2) is 0 on flat faces, the rounds and the
hole (green) and 1/16 on the ball corners (warm); Principal Maximum with a 5 mm limit: the
rounds (1/4 > 1/5) red, flat faces green; Principal Minimum: the rounds' smaller curvature
is 0 (green), the ball corners' 1/4 (red). Minimum Radius: the hole is the only concave
round (r = 5): green while a 5 mm tool fits, red when the minimum radius is 6; the convex
rounds are no concern (neutral grey). Curvature Comb on the hole's rim (a circle r = 5):
as many teeth as the density, all the same length (a quarter of the rim's size at scale
1), a straight edge's teeth have no length. Isocurve on the hole's wall."""

import math

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import analysis_steps as a
from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import inspect_steps as s
from SciForgeTests.gui import timeline_input as ti

V = App.Vector
st = {}
R = 4.0
UPRIGHT = [V(0, 0, 5), V(40, 0, 5), V(40, 30, 5)]
CORNER = V(36, 4, 6) + V(1, -1, 1) * (R / math.sqrt(3))  # on the ball at the front right
HOLE_WALL = V(20 - 5 / math.sqrt(2), 15 + 5 / math.sqrt(2), 7)  # its far side, seen
RIM = V(20 + 5 / math.sqrt(2), 15 - 5 / math.sqrt(2), 10)  # its near edge
FRONT_BOTTOM = V(20, 0, 0)
TOP = V(20, 6, 10)


# -- the part ---------------------------------------------------------------------------------
def part_steps():
    def fillet():
        Gui.Selection.clearSelection()
        h.fit()
        h.press("f")

    def edge_step(point):
        def pick_edge():
            h.click_edge(point)

        return pick_edge

    def radius():
        p = b.blend_panel()
        h.check("Fillet dialog with seven edges", p is not None and len(p.refs) == 7, p and p.refs)
        if p is not None:
            b.type_into(p.radius.widget, "4")

    def ok():
        h.task_button("OK")

    def rounded():
        v = h.solid_volume()
        h.check("seven edges rounded", 11000 < v < b.BOX, v)
        st["rounded"] = v
        h.click_empty()
        h.fit()
        h.ribbon("Create Sketch")

    def on_top():
        h.click(TOP)

    def circle():
        sk = h.in_sketch()
        h.check("a sketch on the top face", sk is not None)
        if sk is not None:
            x, y = h.to_sketch(sk, V(20, 15, 10))
            h.draw_circle(sk, x, y, 5)

    def finish():
        h.ribbon("Finish Sketch")

    def extrude():
        h.fit()
        h.press("e")

    def depth():
        panel = b.active_panel()
        field = getattr(getattr(panel, "distance", None), "widget", None)
        if field is not None:
            b.type_into(field, "-6")

    def cut_ok():
        h.task_button("OK")

    def holed():
        v = h.solid_volume()
        h.check(
            "the hole cut (pi 25 x 6 less)",
            b.close(st["rounded"] - v, math.pi * 25 * 6, 1e-6),
            (st["rounded"] - v),
        )
        h.fit()

    def make_room():
        # like a person: slide the part away from the Fillet dialog on the right. The 7th
        # edge lay about 10 px from the dialog's border, and on GitHub's runner (other
        # fonts, a wider dialog) the click went to the dialog: six edges taken (CI #136-141)
        h.pan(-150, 0)

    edges = [edge_step(p) for p in a.TOP_EDGES + UPRIGHT]
    return (
        [fillet, make_room]
        + edges
        + [radius, ok, rounded, on_top, circle, finish, extrude, depth, cut_ok, holed]
    )


# -- Curvature Map ----------------------------------------------------------------------------
def map_start():
    a.inspect("Curvature Map Analysis")


def map_pick():
    h.click(a.TOP_FACE)


def gaussian():
    objs = a.analyses("CurvatureMapAnalysis")
    h.check("Curvature Map1", len(objs) == 1 and objs[0].Label == "Curvature Map1")
    h.check("Gaussian by default", objs and objs[0].MapType == "Gaussian")
    st["corner"] = a.color_at(CORNER)
    h.check(
        "the ball corner is warm (it curves both ways)",
        a.name_at(CORNER) in ("orange", "yellow", "red"),
        st["corner"],
    )
    h.check("the flat top is green", a.name_at(TOP) == "green", a.color_at(TOP))
    h.check(
        "the hole's wall is green (it curves one way only)",
        a.name_at(HOLE_WALL) == "green",
        a.color_at(HOLE_WALL),
    )
    p = a.panel()
    h.check(
        "Display and Scale shown, no limit",
        p.field("MapDisplay").isVisible()
        and p.field("MapScale").isVisible()
        and not p.field("LimitRadius").isVisible(),
    )
    h.shot("1-gaussian")
    a.set_combo(p.field("MapDisplay"), "Bands")


def bands():
    objs = a.analyses("CurvatureMapAnalysis")
    h.check("Display Bands", objs and objs[0].MapDisplay == "Bands")
    a.type_spin(a.panel().field("MapScale"), "0.2")


def weaker():
    objs = a.analyses("CurvatureMapAnalysis")
    h.check("Scale 0.2", objs and abs(objs[0].MapScale - 0.2) < 1e-9)
    now = a.color_at(CORNER)
    h.check(
        "a smaller scale: the corner less warm (less red, more green)",
        now[0] < st["corner"][0] or now[1] > st["corner"][1] + 20,
        (st["corner"], now),
    )
    a.set_combo(a.panel().field("MapType"), "Principal Maximum")


def principal_max():
    p = a.panel()
    objs = a.analyses("CurvatureMapAnalysis")
    h.check("Principal Maximum", objs and objs[0].MapType == "Principal Maximum")
    label = p.layout.labelForField(p.field("LimitRadius"))
    h.check(
        "its limit is called Minimum Limit", label is not None and label.text() == "Minimum Limit"
    )
    h.check("Display and Scale hidden", not p.field("MapDisplay").isVisible())
    s.type_into(p.field("LimitRadius"), "5")


def limit_5():
    objs = a.analyses("CurvatureMapAnalysis")
    h.check("limit 5 mm", objs and abs(objs[0].LimitRadius.Value - 5) < 1e-9)
    h.check(
        "the rounds (r 4) are red", a.name_at(a.FRONT_ROUND) == "red", a.color_at(a.FRONT_ROUND)
    )
    h.check("the flat top is green", a.name_at(TOP) == "green", a.color_at(TOP))
    h.shot("2-principal-max")
    a.set_combo(a.panel().field("MapType"), "Principal Minimum")


def principal_min():
    p = a.panel()
    label = p.layout.labelForField(p.field("LimitRadius"))
    h.check(
        "Principal Minimum's limit is called Maximum Limit",
        label is not None and label.text() == "Maximum Limit",
    )
    h.check(
        "the rounds bend one way only: green",
        a.name_at(a.FRONT_ROUND) == "green",
        a.color_at(a.FRONT_ROUND),
    )
    h.check("the ball corner bends both ways: red", a.name_at(CORNER) == "red", a.color_at(CORNER))
    h.task_button("OK")


def map_kept():
    h.check(
        "Curvature Map1 kept", len(a.analyses("CurvatureMapAnalysis")) == 1 and a.panel() is None
    )
    a.open_analysis_folder()
    s.eye("Curvature Map1")


# -- Minimum Radius -------------------------------------------------------------------------------
def radius_start():
    h.check("the map hidden", a.model_faces_shown())
    a.inspect("Minimum Radius Analysis")


def radius_pick():
    h.click(a.TOP_FACE)


def tool_fits():
    objs = a.analyses("MinimumRadiusAnalysis")
    h.check("Minimum Radius1", len(objs) == 1 and objs[0].Label == "Minimum Radius1")
    h.check(
        "defaults: minimum 1 mm, tool 5 mm",
        objs
        and abs(objs[0].MinimumRadius.Value - 1) < 1e-9
        and abs(objs[0].ToolRadius.Value - 5) < 1e-9,
    )
    h.check(
        "the hole (r 5) takes a 5 mm tool: green",
        a.name_at(HOLE_WALL) == "green",
        a.color_at(HOLE_WALL),
    )
    h.check(
        "the convex rounds are no concern (grey)",
        a.name_at(a.FRONT_ROUND) == "grey",
        a.color_at(a.FRONT_ROUND),
    )
    h.shot("3-radius-ok")
    p = a.panel()
    s.type_into(p.field("ToolRadius"), "8")


def tool_8():
    s.type_into(a.panel().field("MinimumRadius"), "6")


def too_tight():
    objs = a.analyses("MinimumRadiusAnalysis")
    h.check(
        "minimum 6, tool 8",
        objs
        and abs(objs[0].MinimumRadius.Value - 6) < 1e-9
        and abs(objs[0].ToolRadius.Value - 8) < 1e-9,
    )
    h.check(
        "the hole is tighter than 6 mm: red", a.name_at(HOLE_WALL) == "red", a.color_at(HOLE_WALL)
    )
    h.shot("4-radius-tight")
    s.press_escape()


def radius_cancelled():
    h.check("Esc leaves no Minimum Radius analysis", not a.analyses("MinimumRadiusAnalysis"))
    a.inspect("Curvature Comb Analysis")


# -- Curvature Comb -------------------------------------------------------------------------------
def comb_waits():
    p = a.panel()
    h.check(
        "Curvature Comb dialog asks for edges",
        p is not None and "edges" in p.message.text(),
        p and p.message.text(),
    )
    h.click(a.TOP_FACE)


def face_refused():
    h.check("a face is no edge: nothing made", not a.analyses("CurvatureCombAnalysis"))
    h.click_edge(RIM)


def teeth(obj=None):
    objs = a.analyses("CurvatureCombAnalysis")
    obj = obj or (objs[0] if objs else None)
    if obj is None:
        return []
    proxy = obj.ViewObject.Proxy
    found = []
    for _owner, curves in getattr(proxy, "curves", []):
        for curve in curves:
            found.append([(V(*p) - V(*t)).Length for p, t, _c in curve["teeth"]])
    return found


def rim_comb():
    objs = a.analyses("CurvatureCombAnalysis")
    h.check("Curvature Comb1 on the rim", len(objs) == 1 and objs[0].Label == "Curvature Comb1")
    combs = teeth()
    h.check(
        "one comb with 30 teeth", len(combs) == 1 and len(combs[0]) == 30, [len(c) for c in combs]
    )
    if combs:
        lengths = combs[0]
        h.check(
            "a circle: all teeth the same length", max(lengths) - min(lengths) < 1e-6, lengths[:3]
        )
        reference = 10 * math.sqrt(2)  # the rim's box diagonal (the rim is flat)
        h.check(
            "a quarter of the rim's size at scale 1",
            abs(max(lengths) - reference / 4) < 0.01 * reference,
            max(lengths),
        )
    h.shot("5-comb")
    a.type_spin(a.panel().field("Density"), 10)


def density_10():
    combs = teeth()
    h.check("Density 10: ten teeth", combs and len(combs[0]) == 10, [len(c) for c in combs])
    st["length"] = max(combs[0]) if combs else 0
    a.type_spin(a.panel().field("CombScale"), "2")


def scale_2():
    combs = teeth()
    h.check("Scale 2: teeth twice as long", combs and abs(max(combs[0]) - 2 * st["length"]) < 1e-6)
    h.click_edge(FRONT_BOTTOM)


def straight_too():
    combs = teeth()
    h.check("a second edge: two combs", len(combs) == 2, [len(c) for c in combs])
    flat = [c for c in combs if c and max(c) < 1e-9]
    h.check("the straight edge's teeth have no length", len(flat) == 1)
    h.task_button("OK")


def comb_kept():
    h.check("Curvature Comb1 kept", len(a.analyses("CurvatureCombAnalysis")) == 1)
    s.undo()


def comb_undone():
    h.check("undo removes it", not a.analyses("CurvatureCombAnalysis"))
    s.redo()


def comb_redone():
    h.check("redo brings it back with its two combs", len(teeth()) == 2)
    a.inspect("Isocurve Analysis")


comb_redone.wait_ms = 900


# -- Isocurve ----------------------------------------------------------------------------------
def iso_pick():
    h.click(HOLE_WALL)


def curves(kind="IsocurveAnalysis"):
    objs = a.analyses(kind)
    if not objs:
        return []
    found = []
    for _owner, items in getattr(objs[0].ViewObject.Proxy, "curves", []):
        found += items
    return found


def iso_both():
    objs = a.analyses("IsocurveAnalysis")
    h.check("Isocurve1 on the hole's wall", len(objs) == 1 and objs[0].Label == "Isocurve1")
    found = curves()
    st["both"] = len(found)
    h.check("isocurves drawn both ways", len(found) >= 10, len(found))
    h.check("no combs yet", all(not c["teeth"] for c in found))
    h.shot("6-isocurve")
    a.set_combo(a.panel().field("IsoType"), "U")


def iso_u():
    found = curves()
    h.check("U only: fewer isocurves", 0 < len(found) < st["both"], (len(found), st["both"]))
    a.tick(a.panel().field("ShowCombs"), True)


def iso_combs():
    p = a.panel()
    found = curves()
    h.check("Curvature Combs: teeth on the isocurves", found and all(c["teeth"] for c in found))
    h.check("Density and Scale shown with the combs", p.field("Density").isVisible())
    h.task_button("OK")


def iso_kept():
    h.check("Isocurve1 kept", len(a.analyses("IsocurveAnalysis")) == 1)
    a.open_analysis_folder()
    names = ti.children("Analysis") or []
    h.check(
        "the Analysis folder lists all three",
        all(n in names for n in ("Curvature Map1", "Curvature Comb1", "Isocurve1")),
        names,
    )
    ti.row_menu("Isocurve1", "Delete")


def iso_deleted():
    h.check("Isocurve1 deleted", not a.analyses("IsocurveAnalysis"))
    st["path"] = a.save_reopen("inspect_analysis_curvature.FCStd")


iso_deleted.wait_ms = 1500


def reopened():
    h.check(
        "after reopening: the map (hidden) and the comb",
        len(a.analyses("CurvatureMapAnalysis")) == 1
        and len(a.analyses("CurvatureCombAnalysis")) == 1,
    )
    h.check("the comb is drawn again", len(teeth()) == 2, [len(c) for c in teeth()])
    objs = a.analyses("CurvatureMapAnalysis")
    h.check(
        "the map is still hidden and keeps its type",
        objs and not objs[0].ViewObject.Visibility and objs[0].MapType == "Principal Minimum",
    )


h.run(
    "inspect_analysis_curvature",
    b.box_steps("Curvature")
    + part_steps()
    + [
        map_start,
        map_pick,
        gaussian,
        bands,
        weaker,
        principal_max,
        limit_5,
        principal_min,
        map_kept,
        radius_start,
        radius_pick,
        tool_fits,
        tool_8,
        too_tight,
        radius_cancelled,
        comb_waits,
        face_refused,
        rim_comb,
        density_10,
        scale_2,
        straight_too,
        comb_kept,
        comb_undone,
        comb_redone,
        iso_pick,
        iso_both,
        iso_u,
        iso_combs,
        iso_kept,
        iso_deleted,
        reopened,
    ],
)
