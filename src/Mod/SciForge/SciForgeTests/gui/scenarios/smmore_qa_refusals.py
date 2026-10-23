# SPDX-License-Identifier: LGPL-2.1-or-later
"""QA of the sm-more commands where they cannot work, only real input: in an empty design
Hem, Join by Bend, Corner Closure, Fillet and Chamfer of the SHEET METAL tab say why next to the
mouse (no dialog, no pop-up, no error), and Lofted Flange opens and waits, Esc makes nothing.
On a solid (not sheet metal) body the SHEET METAL tab's Fillet opens the SOLID Fillet. Join by
Bend of a 1 mm steel plate and a 1.5 mm aluminium plate is refused with the reason (OK waits),
Esc leaves both plates as they were; Hem opened on the steel plate then a click on the aluminium
one moves there (the Length follows its rule, a Gap typed stays). A Lofted Flange previewed in
a new body, then Esc: the new body is gone again and the profiles' sketches are still shown."""

import FreeCAD as App
import FreeCADGui as Gui
import Part

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import smmore_steps as st

V = App.Vector
s = {}


def told():
    from sciforge import commands

    return str(commands._TOLD.get("msg") or "")


def empty():
    from sciforge import commands

    st.new_design("SmQaEmpty")
    commands._TOLD["msg"] = None
    h.fit()


def refused_in_empty(label, group=None):
    def open_it():
        from sciforge import commands

        Gui.Selection.clearSelection()
        commands._TOLD["msg"] = None
        st.tab()
        if group is None:
            h.ribbon(label)
        else:
            st.menu(group, label)

    def refused():
        st.settle()
        h.check(
            "%s in an empty design: no dialog" % label,
            not Gui.Control.activeDialog(),
        )
        h.check("%s: no pop-up" % label, not h.popups(), h.popups())
        h.check(
            "%s: says a sheet metal body is needed" % label,
            "sheet metal body" in told(),
            told(),
        )

    open_it.__name__ = "open_" + label.replace(" ", "_").lower()
    refused.__name__ = "refused_" + label.replace(" ", "_").lower()
    return [open_it, refused]


def lofted_in_empty():
    Gui.Selection.clearSelection()
    st.tab()
    st.menu("CREATE", "Lofted Flange")


def lofted_waits():
    from sciforge import sheetmetal_lofted_ui

    p = st.panel(sheetmetal_lofted_ui.LoftedPanel)
    h.check("Lofted Flange opens in an empty design", p is not None)
    h.check(
        "it asks for the first profile",
        p is not None and "first profile" in p.help.text(),
        p and p.help.text(),
    )


def lofted_esc():
    st.esc()


def lofted_nothing():
    from sciforge import sheetmetal_lofted_ui

    doc = App.ActiveDocument
    h.check(
        "Esc: closed, no body made",
        st.panel(sheetmetal_lofted_ui.LoftedPanel) is None
        and not doc.findObjects("PartDesign::Body"),
        [o.Name for o in doc.findObjects("PartDesign::Body")],
    )
    App.closeDocument(doc.Name)


# -- the SHEET METAL tab's Fillet on a solid body ---------------------------------------------
def solid_body():
    from sciforge import commands, extrude, pickpanel, sketch_ui

    st.new_design("SmQaSolid")
    body = commands.ensure_body()
    planes = sketch_ui.origin_planes(body)
    sketch = body.newObject("Sketcher::SketchObject", "Square")
    sketch.AttachmentSupport = [(planes["XY_Plane"], "")]
    sketch.MapMode = "FlatFace"
    pts = [V(0, 0, 0), V(30, 0, 0), V(30, 30, 0), V(0, 30, 0)]
    for i in range(4):
        sketch.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % 4]))
    App.ActiveDocument.recompute()
    extrude.make(body, sketch, {"distance": 10.0})
    App.ActiveDocument.recompute()
    pickpanel.activate(body)
    s["solid"] = body
    s["solid_volume"] = st.volume(body)
    h.fit()


def sm_fillet_on_solid():
    Gui.Selection.clearSelection()
    st.tab()
    st.menu("MODIFY", "Fillet")


def solid_fillet_opened():
    from sciforge import sheetmetal_corner_round_ui as ui

    st.settle()
    h.check(
        "a solid body: the SOLID Fillet opens instead",
        bool(Gui.Control.activeDialog()) and st.panel(ui.RoundPanel) is None,
    )


def solid_esc():
    st.esc()


def solid_untouched():
    st.settle()
    h.check("Esc: dialog closed", not Gui.Control.activeDialog())
    h.check("the solid is as it was", st.close(st.volume(s["solid"]), s["solid_volume"]))
    App.closeDocument(App.ActiveDocument.Name)


# -- Join by Bend of two thicknesses ----------------------------------------------------------
def thick_plate(x0, y0, x1, y1, thickness, rule):
    from sciforge import extrude, sheetmetal, sketch_ui

    doc = App.ActiveDocument
    body = st.new_body()
    planes = sketch_ui.origin_planes(body)
    sketch = body.newObject("Sketcher::SketchObject", "PlateSketch")
    sketch.AttachmentSupport = [(planes["XY_Plane"], "")]
    sketch.MapMode = "FlatFace"
    pts = [V(x0, y0, 0), V(x1, y0, 0), V(x1, y1, 0), V(x0, y1, 0)]
    for i in range(4):
        sketch.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % 4]))
    doc.recompute()
    extrude.make(body, sketch, {"distance": thickness})
    sheetmetal.make_sheet_metal_body(body, rule)
    doc.recompute()
    return body


def two_thicknesses():
    from sciforge import pickpanel

    st.new_design("SmQaJoin")
    s["alu"] = thick_plate(0, 0, 50, 40, 1.5, "Aluminum (mm)")
    s["alu"].Label = "Aluminium"
    s["upright"], _u = st.plate(
        0, 5, 40, 45, z=60, body=st.new_body(), plane="YZ_Plane", label="Upright"
    )
    s["alu_volume"] = st.volume(s["alu"])
    pickpanel.activate(s["upright"])
    h.fit()


def open_join():
    Gui.Selection.clearSelection()
    st.tab()
    st.menu("CREATE", "Join by Bend")


def click_first():
    h.fit()
    h.click_edge(V(60, 20, 5))


def view_top():
    from sciforge import sheetmetal_bend_join_ui as ui

    p = st.panel(ui.JoinBendPanel)
    h.check("first edge picked", p is not None and len(p.picks["first"]) == 1, p and p.picks)
    Gui.ActiveDocument.ActiveView.viewTop()
    h.fit(iso=False)


def click_alu():
    h.click_edge(V(50, 20, 1.5))


def thickness_refused():
    from sciforge import sheetmetal_bend_join_ui as ui

    p = st.panel(ui.JoinBendPanel)
    st.settle(p)
    h.check(
        "the aluminium plate's edge is picked",
        p is not None and len(p.picks["second"]) == 1,
        p and p.picks,
    )
    h.check(
        "different thicknesses explained",
        "different thicknesses" in st.message(p),
        st.message(p),
    )
    h.check("nothing joined", not st.steps("SheetMetalJoinBend"))
    st.ok()


def ok_waits():
    from sciforge import sheetmetal_bend_join_ui as ui

    h.check("OK waits", st.panel(ui.JoinBendPanel) is not None)
    st.esc()


def join_untouched():
    from sciforge import bodies
    from sciforge import sheetmetal_bend_join_ui as ui

    st.settle()
    h.check("Esc: closed", st.panel(ui.JoinBendPanel) is None)
    h.check("the upright plate is as it was", st.close(st.volume(s["upright"]), 1600.0))
    h.check("the aluminium plate is as it was", st.close(st.volume(s["alu"]), s["alu_volume"]))
    h.check("the aluminium plate is still shown", bodies.is_shown(s["alu"]))


def hem_from_steel():
    from sciforge import pickpanel

    pickpanel.activate(s["upright"])
    Gui.Selection.clearSelection()
    h.fit(iso=False)
    st.tab()
    h.ribbon("Hem")


def hem_on_steel():
    from sciforge import sheetmetal_hem_ui

    p = st.panel(sheetmetal_hem_ui.HemPanel)
    h.check(
        "Hem opens on the steel plate, Length 4 T = 4 mm",
        p is not None and p.body is s["upright"] and st.close(p.value("length"), 4.0),
        p and (p.body.Label, p.value("length")),
    )
    st.type_into(p, "gap", "0.6")


def click_alu_edge():
    h.click_edge(V(50, 20, 1.5))


def hem_on_alu():
    from sciforge import sheetmetal_hem_ui

    p = st.panel(sheetmetal_hem_ui.HemPanel)
    st.settle(p)
    h.check(
        "the dialog moved to the aluminium plate",
        p is not None and p.body is s["alu"] and len(p.picks["edges"]) == 1,
        p and (p.body.Label, p.picks),
    )
    h.check(
        "Length follows its rule (4 T = 6 mm); the Gap typed stays 0.6",
        p is not None and st.close(p.value("length"), 6.0) and st.close(p.value("gap"), 0.6),
        p and (p.value("length"), p.value("gap")),
    )
    h.check("the hem is previewed on the aluminium plate", st.volume(s["alu"]) > s["alu_volume"])
    st.esc()


def hem_left():
    st.settle()
    h.check("Esc: the aluminium plate as it was", st.close(st.volume(s["alu"]), s["alu_volume"]))
    App.closeDocument(App.ActiveDocument.Name)


# -- Lofted Flange previewed in a new body, then Esc ------------------------------------------
def lofted_setup():
    from sciforge import commands

    st.new_design("SmQaLofted")
    host = commands.ensure_body()
    s["square"] = st.profile_sketch(
        host, [(-20, -20, 20, -20), (20, -20, 20, 20), (20, 20, -20, 20), (-20, 20, -20, -20)]
    )
    s["circle"] = st.profile_sketch(host, [("c", 0, 0, 15)], z=30)
    s["bodies"] = len(App.ActiveDocument.findObjects("PartDesign::Body"))
    h.fit()


def lofted_open():
    Gui.Selection.clearSelection()
    st.tab()
    st.menu("CREATE", "Lofted Flange")


def lofted_square():
    h.fit()
    h.click_edge(V(0, -20, 0))


def lofted_circle():
    h.click_edge(V(15, 0, 30))


def lofted_previewed():
    from sciforge import sheetmetal_lofted_ui

    p = st.panel(sheetmetal_lofted_ui.LoftedPanel)
    st.settle(p, 15000)
    count = len(App.ActiveDocument.findObjects("PartDesign::Body"))
    h.check("the preview is in a new body", count == s["bodies"] + 1, count)
    h.check("one Lofted Flange previewed", len(st.steps("SheetMetalLoftedFlange")) == 1)


def lofted_escape():
    st.esc()


def lofted_gone():
    from sciforge import sheetmetal_lofted_ui

    st.settle()
    doc = App.ActiveDocument
    count = len(doc.findObjects("PartDesign::Body"))
    h.check("Esc: closed", st.panel(sheetmetal_lofted_ui.LoftedPanel) is None)
    h.check("Esc: the new body is gone", count == s["bodies"], count)
    h.check("Esc: no Lofted Flange", not st.steps("SheetMetalLoftedFlange"))
    h.check(
        "Esc: the profiles' sketches are still shown",
        s["square"].ViewObject.Visibility and s["circle"].ViewObject.Visibility,
    )


h.run(
    "smmore_qa_refusals",
    [empty]
    + refused_in_empty("Hem")
    + refused_in_empty("Join by Bend", "CREATE")
    + refused_in_empty("Corner Closure", "MODIFY")
    + refused_in_empty("Fillet", "MODIFY")
    + refused_in_empty("Chamfer", "MODIFY")
    + [
        lofted_in_empty,
        lofted_waits,
        lofted_esc,
        lofted_nothing,
        solid_body,
        sm_fillet_on_solid,
        solid_fillet_opened,
        solid_esc,
        solid_untouched,
        two_thicknesses,
        open_join,
        click_first,
        view_top,
        click_alu,
        thickness_refused,
        ok_waits,
        join_untouched,
        hem_from_steel,
        hem_on_steel,
        click_alu_edge,
        hem_on_alu,
        hem_left,
        lofted_setup,
        lofted_open,
        lofted_square,
        lofted_circle,
        lofted_previewed,
        lofted_escape,
        lofted_gone,
    ],
)
