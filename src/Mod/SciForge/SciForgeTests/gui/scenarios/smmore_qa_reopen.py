# SPDX-License-Identifier: LGPL-2.1-or-later
"""QA of the sm-more steps after save and reopen, only real input for what is tested: a design
with a Hem and a two-set Fillet on one plate, a Corner Closure between two flanges, a Join by
Bend (the other body used up) and a Brake Form Lofted Flange (a new body) is saved, closed and
reopened: every step rebuilds to the same shape and the joined body stays hidden. Then each
step is double-clicked in the timeline: its dialog comes back with its picks (the Fillet with
both sets), a value is changed (the preview follows), Cancel or Esc leaves the step and the
part exactly as they were. Last, the Join by Bend is deleted from the timeline (the other body
comes back) and Ctrl+Z puts it back (hidden again). The steps are set up in code, like other
scenarios' setup."""

import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
import Part

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import hole_steps as hs
from SciForgeTests.gui import smmore_steps as st

V = App.Vector
s = {}
OUTLINE = [(0, 0), (95, 0), (95, 5), (100, 5), (100, 40), (0, 40)]
SKIPPED = ("Part::PropertyPartShape", "App::PropertyMaterial", "App::PropertyMaterialList")


def edge_at(shape, point):
    vertex = Part.Vertex(point)
    for i, edge in enumerate(shape.Edges, 1):
        if edge.distToShape(vertex)[0] < 1e-4:
            return "Edge%d" % i
    raise RuntimeError("no edge through %r" % point)


def setup():
    from sciforge import bodies, pickpanel
    from sciforge import sheetmetal_bend_join as sj
    from sciforge import sheetmetal_corner as sc
    from sciforge import sheetmetal_corner_round as sr
    from sciforge import sheetmetal_hem as sh
    from sciforge import sheetmetal_lofted as sl

    doc = st.new_design("SmQaReopen")
    # a notched plate with two edge flanges, its corner closed
    s["corner"], _c = st.plate(0, 0, 100, 40, outline=OUTLINE, label="Cornered")
    st.edge_flange(s["corner"], V(100, 20, 1), 20)
    st.edge_flange(s["corner"], V(50, 0, 1), 20)
    tip = s["corner"].Tip
    sc.make(
        s["corner"],
        tip,
        edge_at(tip.Shape, V(100, 5, 12)),
        edge_at(tip.Shape, V(95, 0, 12)),
        {},
    )
    doc.recompute()
    # a plate hemmed at one end, two corners at the other end filleted in two sets
    s["hemmed"], _p = st.plate(0, 100, 100, 140, body=st.new_body(), label="Hemmed")
    tip = s["hemmed"].Tip
    sh.make(s["hemmed"], tip, [edge_at(tip.Shape, V(100, 120, 1))], {"type": "open"})
    doc.recompute()
    tip = s["hemmed"].Tip
    sr.make(
        s["hemmed"],
        tip,
        "fillet",
        [
            {"edges": [edge_at(tip.Shape, V(0, 100, 0.5))], "value": 5.0},
            {"edges": [edge_at(tip.Shape, V(0, 140, 0.5))], "value": 8.0},
        ],
    )
    doc.recompute()
    # two plates joined by a bend; the flat one is used up
    s["flat"], _f = st.plate(0, 200, 50, 240, body=st.new_body(), label="Flat")
    s["upright"], _u = st.plate(
        200, 5, 240, 45, z=60, body=st.new_body(), plane="YZ_Plane", label="Upright"
    )
    tip = s["upright"].Tip
    other = s["flat"].Tip
    sj.make(
        s["upright"],
        tip,
        edge_at(tip.Shape, V(60, 220, 5)),
        other,
        edge_at(other.Shape, V(50, 220, 1)),
        {},
    )
    doc.recompute()
    bodies.sync_consumed(doc)
    # a square-to-round Brake Form lofted flange in a new body
    host = st.new_body()
    square = st.profile_sketch(
        host,
        [(-20, 380, 20, 380), (20, 380, 20, 420), (20, 420, -20, 420), (-20, 420, -20, 380)],
    )
    circle = st.profile_sketch(host, [("c", 0, 400, 15)], z=30)
    s["lofted"] = sl.target_body(doc, "new_body", None, "Steel (mm)")
    sl.make(s["lofted"], [(square, [])], [(circle, [])], {"forming": "brake"})
    doc.recompute()
    pickpanel.activate(s["hemmed"])
    h.fit()


NAMES = ("corner", "hemmed", "upright", "lofted")


def made():
    from sciforge import bodies

    for key in NAMES:
        h.check("%s body built" % key, st.volume(s[key]) > 100, (key, st.volume(s[key])))
    h.check("the flat plate is used up (hidden)", not bodies.is_shown(s["flat"]))
    s["volumes"] = {key: st.volume(s[key]) for key in NAMES}
    s["names"] = {key: s[key].Name for key in NAMES + ("flat",)}
    titles = st.timeline_titles()
    for title in ("Corner Closure 1", "Hem 1", "Fillet 1", "Join by Bend 1", "Lofted Flange 1"):
        h.check("timeline shows %s" % title, title in titles, titles)


def save_close():
    doc = App.ActiveDocument
    s["path"] = os.path.join(tempfile.mkdtemp(prefix="sciforge-smqa-"), "smqa.FCStd")
    doc.saveAs(s["path"])
    App.closeDocument(doc.Name)


def reopen():
    App.openDocument(s["path"])
    App.ActiveDocument.recompute()
    h.fit()


def reopened():
    from sciforge import bodies

    doc = App.ActiveDocument
    for key in NAMES + ("flat",):
        s[key] = doc.getObject(s["names"][key])
    for key in NAMES:
        h.check(
            "%s rebuilds to the same shape" % key,
            st.close(st.volume(s[key]), s["volumes"][key]),
            (st.volume(s[key]), s["volumes"][key]),
        )
    for kind in (
        "SheetMetalHem",
        "SheetMetalCornerClosure",
        "SheetMetalJoinBend",
        "SheetMetalLoftedFlange",
        "SheetMetalFillet",
    ):
        found = st.steps(kind)
        h.check(
            "%s step back, valid, with its proxy" % kind,
            len(found) == 1
            and "Invalid" not in list(found[0].State)
            and found[0].Proxy is not None
            and found[0].ViewObject.Proxy is not None,
            found,
        )
    h.check("the flat plate is still used up (hidden)", not bodies.is_shown(s["flat"]))


# -- edit from the timeline, change a value, Cancel / Esc ------------------------------------
def edit_case(title, kind, panel_name, change, check_open, leave="cancel"):
    """Double-click `title`, check the dialog, change a value, leave with Cancel or Esc."""

    def snapshot():
        step = st.steps(kind)[0]
        # the user's values (shapes, materials and the picks' geometry record are rebuilt)
        return {
            p: str(getattr(step, p))
            for p in step.PropertiesList
            if p
            not in (
                "Label",
                "Label2",
                "ExpressionEngine",
                "Visibility",
                "SciForgePicks",
                "ShapeMaterial",
            )
            and step.getTypeIdOfProperty(p) not in SKIPPED
            and not p.startswith("_")
        }

    def open_it():
        s["before"] = snapshot()
        s["vols"] = {key: st.volume(s[key]) for key in NAMES}
        Gui.Selection.clearSelection()
        h.check("double-click %s" % title, st.double_click_timeline(title))

    def change_it():
        p = current(panel_name)
        st.settle(p)
        h.check("%s: edit dialog open" % title, p is not None and p.editing)
        if p is None:
            return
        check_open(p)
        change(p)

    def changed():
        p = current(panel_name)
        st.settle(p)
        h.check(
            "%s: the preview follows the change" % title,
            any(not st.close(st.volume(s[k]), s["vols"][k]) for k in NAMES),
            [st.volume(s[k]) for k in NAMES],
        )
        h.check("%s: no message" % title, st.message(p) == "", st.message(p))

    def leave_it():
        if leave == "esc":
            st.esc()
        else:
            st.cancel()

    def left():
        h.check("%s: dialog closed" % title, current(panel_name) is None)
        now = snapshot()
        h.check(
            "%s: the step's values are as they were" % title,
            now == s["before"],
            [(k, s["before"].get(k), now.get(k)) for k in now if now.get(k) != s["before"].get(k)],
        )
        for key in NAMES:
            h.check(
                "%s: %s as it was" % (title, key),
                st.close(st.volume(s[key]), s["vols"][key]),
                (st.volume(s[key]), s["vols"][key]),
            )
        h.check(
            "%s: still one step" % title,
            len(st.steps(kind)) == 1 and "Invalid" not in list(st.steps(kind)[0].State),
        )

    steps = [open_it, change_it, changed, leave_it, left]
    for fn in steps:
        fn.__name__ = "%s_%s" % (fn.__name__, kind)
    return steps


def current(name):
    import importlib

    module, cls = name.rsplit(".", 1)
    return st.panel(getattr(importlib.import_module(module), cls))


def hem_open(p):
    h.check(
        "Hem: the edge comes back, type Open",
        len(p.picks["edges"]) == 1 and p.value("type") == "open",
        (p.picks, p.value("type")),
    )


def hem_change(p):
    st.choose(p, "type", "Rolled")


def fillet_open(p):
    h.check(
        "Fillet: both sets come back (5 mm kept, 8 mm being edited)",
        len(p.sets) == 1
        and st.close(p.sets[0]["value"], 5.0)
        and len(p.picks["edges"]) == 1
        and st.close(p.value("value"), 8.0),
        (p.sets, p.picks, p.value("value")),
    )


def fillet_change(p):
    st.type_into(p, "value", "3")


def corner_open(p):
    h.check(
        "Corner Closure: both edges come back, Symmetric Gap",
        len(p.picks["dominant"]) == 1
        and len(p.picks["submissive"]) == 1
        and p.value("alignment") == "symmetric",
    )


def corner_change(p):
    st.choose(p, "relief", "Tear")


def join_open(p):
    h.check(
        "Join by Bend: both edges come back",
        len(p.picks["first"]) == 1 and len(p.picks["second"]) == 1,
        p.picks,
    )


def join_change(p):
    st.toggle(p, "use_rule_radius")
    st.type_into(p, "radius", "3")


def lofted_open(p):
    h.check(
        "Lofted Flange: both profiles come back, Brake Form",
        len(p.picks["profile1"]) == 1
        and len(p.picks["profile2"]) == 1
        and p.value("forming") == "brake",
        p.picks,
    )
    box = p.fields["operation"]
    h.check(
        "Lofted Flange: Operation cannot be changed in an edit (greyed, says why)",
        not box.isEnabled() and "edit" in box.toolTip().lower(),
        (box.isEnabled(), box.toolTip()),
    )


def lofted_change(p):
    st.choose(p, "forming", "Die Form")


# -- delete the Join by Bend from the timeline ------------------------------------------------
def delete_join():
    hs.timeline_menu("Join by Bend 1", "Delete")


def join_deleted():
    from sciforge import bodies

    st.settle()
    h.check("Join by Bend deleted", not st.steps("SheetMetalJoinBend"))
    h.check("the flat plate is back (shown)", bodies.is_shown(s["flat"]))
    h.check(
        "the upright plate is as it was before the join", st.close(st.volume(s["upright"]), 1600)
    )


def undo_delete():
    st.undo()


def delete_undone():
    from sciforge import bodies

    st.settle()
    h.check("Ctrl+Z: Join by Bend back", len(st.steps("SheetMetalJoinBend")) == 1)
    h.check(
        "the joined shape is back",
        st.close(st.volume(s["upright"]), s["volumes"]["upright"]),
        st.volume(s["upright"]),
    )
    h.check("the flat plate is used up again (hidden)", not bodies.is_shown(s["flat"]))
    h.shot("smmore-qa-reopen")


h.run(
    "smmore_qa_reopen",
    [setup, made, save_close, reopen, reopened]
    + edit_case(
        "Hem 1", "SheetMetalHem", "sciforge.sheetmetal_hem_ui.HemPanel", hem_change, hem_open
    )
    + edit_case(
        "Fillet 1",
        "SheetMetalFillet",
        "sciforge.sheetmetal_corner_round_ui.RoundPanel",
        fillet_change,
        fillet_open,
        leave="esc",
    )
    + edit_case(
        "Corner Closure 1",
        "SheetMetalCornerClosure",
        "sciforge.sheetmetal_corner_ui.CornerPanel",
        corner_change,
        corner_open,
    )
    + edit_case(
        "Join by Bend 1",
        "SheetMetalJoinBend",
        "sciforge.sheetmetal_bend_join_ui.JoinBendPanel",
        join_change,
        join_open,
        leave="esc",
    )
    + edit_case(
        "Lofted Flange 1",
        "SheetMetalLoftedFlange",
        "sciforge.sheetmetal_lofted_ui.LoftedPanel",
        lofted_change,
        lofted_open,
    )
    + [delete_join, join_deleted, undo_delete, delete_undone],
)
