# SPDX-License-Identifier: LGPL-2.1-or-later
"""The PLASTIC journey (scenarios/journey_plastic*.py): a real plastic enclosure built the way
a Fusion user builds it, only with real clicks and keys, every PLASTIC tool used together on
one design. Not a scenario (kept outside scenarios/).

The design (all numbers by hand):
  Base: component "Base", a 80 x 50 rectangle on XY extruded 25 (100000 mm3).
  Lid:  component "Lid", the same rectangle extruded 10 from a start offset of 25 (z 25..35,
        40000 mm3).
  Rule: PLASTIC > Assign Plastic Rule, "ABS 2 mm" from the library, for each component.
  Shell: the Base's top face removed (the Lid hidden), the Shell opens with the rule's 2 mm:
        100000 - 76 x 46 x 23 = 19592; the Lid's bottom face removed (the Base hidden, seen
        from below): 40000 - 76 x 46 x 8 = 12032.
  Boss: a sketch on the Base's rim (the parting plane z 25) with four points 10 mm in from
        the corners; head side in the Lid, thread side in the Base, ribs on the thread side.
  Snap Fit: a sketch on the rim with one point on the inside of the long back wall
        (40, 48): the hook hangs from the Lid, its groove is cut in the Base's back wall.
  Lip: the four inside edges of the Base's rim, Lip And Groove: the lip on the Base, the
        groove in the Lid.
  Rest: an offset plane 3 mm in front of the Base's front wall, a 20 x 10 rectangle on it,
        PLASTIC > Rest: a pad standing 3 mm out of the wall.
"""

import math
import os
import re
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
import Part
from PySide import QtCore, QtWidgets

from SciForgeTests.gui import arrow_input as ai
from SciForgeTests.gui import component_steps as cs
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import insert_steps as ins
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import plastic2_steps as p2
from SciForgeTests.gui import plastic_steps as p1
from SciForgeTests.gui import shell_draft_steps as sd
from SciForgeTests.gui import timeline_input as tl

V = App.Vector
s = {}

BASE_BOX = 80 * 50 * 25.0  # 100000
LID_BOX = 80 * 50 * 10.0  # 40000
BASE_SHELL = BASE_BOX - 76 * 46 * 23  # 19592
LID_SHELL = LID_BOX - 76 * 46 * 8  # 12032
BOSS_POINTS = [(10, 10), (70, 10), (10, 40), (70, 40)]
SNAP_POINT = (40, 48)
RIM_EDGES = [V(40, 2, 25), V(40, 48, 25), V(2, 25, 25), V(78, 25, 25)]


def near(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


def doc():
    return App.ActiveDocument


def body_of(component_label):
    found = component_bodies(component_label)
    return found[0] if found else None


def component_bodies(component_label):
    part = cs.component(component_label)
    if part is None:
        return []
    return [obj for obj in part.Group if obj.TypeId == "PartDesign::Body"]


def base():
    return body_of("Base")


def lid():
    return body_of("Lid")


def vol(obj):
    return p2.volume(obj)


def titles():
    return tl.titles()


def named(pattern):
    return [t for t in titles() if re.match(pattern, t)]


def step(fn, name):
    fn.__name__ = name
    return fn


def tab(label):
    ins.ribbon_tab(label)


def settle():
    p1.settle(None, 300)


def ok_errors(where):
    bad = [o.Label for o in doc().Objects if "Invalid" in o.State or "Error" in o.State]
    see_through = [b.Label for b in (base(), lid()) if b is not None and b.ViewObject.Transparency]
    h.check("%s: no body left see-through" % where, not see_through, see_through)
    return h.check("%s: every step computed" % where, not bad, bad)


# -- 1. a new design, two components ------------------------------------------------------------
def new_design():
    p1.clear_library_prefs()
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("JourneyPlastic")
    s["doc"] = doc().Label
    h.fit()
    tab("plastic")


def component_steps(label):
    def ribbon_new():
        Gui.Selection.clearSelection()
        h.ribbon("New Component")

    def typed():
        panel = cs.new_component_panel()
        if h.check("%s: New Component dialog" % label, panel is not None):
            cs.type_name(label)

    def ok():
        h.task_button("OK")

    def made():
        h.check(
            "%s: component made and active" % label, cs.active_label() == label, cs.active_label()
        )
        h.check("%s: no dialog left" % label, not tl.dialog_open())

    return [
        step(ribbon_new, "%s_new_component" % label),
        step(typed, "%s_name" % label),
        step(ok, "%s_ok" % label),
        step(made, "%s_made" % label),
    ]


def sketch_rect_steps(label, rect):
    def create():
        h.fit()
        h.ribbon("Create Sketch")

    def plane():
        pl.click_square("XY_Plane")

    def draw():
        sk = h.in_sketch()
        if h.check("%s: sketch open" % label, sk is not None):
            h.check(
                "%s: the sketch is in the component" % label,
                cs.container_label(sk) == label,
                cs.container_label(sk),
            )
            h.draw_rectangle(sk, *rect)

    def finish():
        h.ribbon("Finish Sketch")

    return [
        step(create, "%s_create_sketch" % label),
        step(plane, "%s_xy" % label),
        step(draw, "%s_rectangle" % label),
        step(finish, "%s_finish_sketch" % label),
    ]


def extrude_panel():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    return p if p is not None and not p._closed else None


def base_steps():
    def extrude():
        h.fit()
        h.press("e")

    def distance():
        h.check("Base: extrude dialog", ai.give_distance("25"))

    def ok():
        h.task_button("OK")

    def made():
        b = base()
        if not h.check("Base: a body in Base", b is not None):
            return
        h.check("Base: 80 x 50 x 25 = 100000", near(vol(b), BASE_BOX), vol(b))
        h.check("Base: 6 faces", len(b.Shape.Faces) == 6, len(b.Shape.Faces))
        box = b.Shape.BoundBox
        h.check("Base: z 0..25", near(box.ZMin, 0) and near(box.ZMax, 25), box)

    return (
        component_steps("Base")
        + sketch_rect_steps("Base", (0, 0, 80, 50))
        + [
            step(extrude, "base_extrude"),
            step(distance, "base_distance"),
            step(ok, "base_ok"),
            step(made, "base_made"),
        ]
    )


def lid_steps():
    def root():
        cs.click_radio(s["doc"])

    def root_active():
        h.check("the design (root) active", cs.active_label() is None, cs.active_label())

    def extrude():
        h.fit()
        h.press("e")

    def start_offset():
        p = extrude_panel()
        if not h.check("Lid: extrude dialog", p is not None):
            return
        ui.choose(p.start, "Offset")
        ui.type_into(p.start_offset.widget, "25")

    def distance():
        h.check("Lid: distance typed", ai.give_distance("10"))

    def operation():
        # The Lid's box only touches the Base's top: the automatic operation is Join, and a
        # SciForge Join merges every body it touches, in any component (parity
        # extrude-presspull.md, "Objects To Cut" row), so the Lid would land in the Base's
        # body. A Fusion user making the Lid in its own component picks New Body here.
        p = extrude_panel()
        if p is None:
            return
        h.check(
            "Lid: automatic operation Join (touches the Base), not Cut",
            p.operation.currentText() == "Join",
            p.operation.currentText(),
        )
        ui.choose(p.operation, "New Body")

    def ok():
        h.task_button("OK")

    def made():
        b = lid()
        if not h.check("Lid: a body in Lid", b is not None):
            return
        h.check("Lid: 80 x 50 x 10 = 40000", near(vol(b), LID_BOX), vol(b))
        box = b.Shape.BoundBox
        h.check("Lid: z 25..35 (started 25 up)", near(box.ZMin, 25) and near(box.ZMax, 35), box)
        h.check("Base unchanged", near(vol(base()), BASE_BOX), vol(base()))
        h.check(
            "Lid: one body (the sketch's own; no empty body left beside it)",
            len(component_bodies("Lid")) == 1,
            [o.Label for o in component_bodies("Lid")],
        )
        h.check(
            "timeline (Lid active): Lid, Sketch 2, Extrude 2",
            titles() == ["Lid", "Sketch 2", "Extrude 2"],
            titles(),
        )
        sketches = [o for o in doc().Objects if o.TypeId == "Sketcher::SketchObject"]
        h.check(
            "both sketches hidden by their extrudes",
            sketches and not any(o.ViewObject.Visibility for o in sketches),
            [(o.Label, o.ViewObject.Visibility) for o in sketches],
        )
        see_through = [b.Label for b in (base(), lid()) if b.ViewObject.Transparency]
        h.check("no body left see-through", not see_through, see_through)
        h.shot("journey_pl_1_boxes")

    return (
        [step(root, "root_activate"), step(root_active, "root_active")]
        + component_steps("Lid")
        + sketch_rect_steps("Lid", (0, 0, 80, 50))
        + [
            step(extrude, "lid_extrude"),
            step(start_offset, "lid_start_offset"),
            step(distance, "lid_distance"),
            step(operation, "lid_operation"),
            step(ok, "lid_ok"),
            step(made, "lid_made"),
        ]
    )


# -- 2. the plastic rule ------------------------------------------------------------------------
def assign_steps(label, rule="ABS 2 mm"):
    def open_assign():
        tab("plastic")
        Gui.Selection.clearSelection()
        h.ribbon("Assign Plastic Rule")

    def pick_component():
        p = p1.assign_panel()
        if not h.check("%s: Assign dialog" % label, p is not None):
            return
        ui.choose(p.combo, label)

    def pick_rule():
        p = p1.assign_panel()
        if p is None:
            return
        h.check(
            "%s: component picked" % label, p.combo.currentText() == label, p.combo.currentText()
        )
        where = (
            "In This Design"
            if p.rules.design is not None
            and any(
                p.rules.design.child(i).text(0) == rule for i in range(p.rules.design.childCount())
            )
            else "Library"
        )
        s["assign_where_" + label] = where
        p1.click_tree_row(p.rules.tree, rule, where)

    def ok():
        p = p1.assign_panel()
        if p is not None:
            h.check(
                "%s: %s picked" % (label, rule),
                p.rules.current() is not None and p.rules.current()[1] == rule,
                p.rules.current(),
            )
        p1.ok()

    def assigned():
        from sciforge import material, plastic

        part = cs.component(label)
        h.check("%s: Assign closed" % label, p1.assign_panel() is None)
        h.check(
            "%s: the rule is %s" % (label, rule),
            plastic.assigned_rule_name(doc(), part) == rule,
            plastic.assigned_rule_name(doc(), part),
        )
        b = body_of(label)
        h.check("%s: rule thickness 2" % label, plastic.default_for(b, "thickness") == 2.0)
        h.check("%s: ABS" % label, material.key_of(b) == "abs", material.key_of(b))
        h.check(
            "one copy of the rule in the design",
            [r["name"] for r in plastic.design_rules(doc())] == [rule],
            [r["name"] for r in plastic.design_rules(doc())],
        )
        h.check("%s: not a timeline step" % label, not named(r".*Rule.*"), titles())

    return [
        step(open_assign, "%s_assign" % label),
        step(pick_component, "%s_assign_component" % label),
        step(pick_rule, "%s_assign_rule" % label),
        step(ok, "%s_assign_ok" % label),
        step(assigned, "%s_assigned" % label),
    ]


# -- 3. shells -----------------------------------------------------------------------------------
def shell_steps():
    def hide_lid():
        tl.click_eye("Lid")

    def open_shell():
        h.check("Lid hidden", not tl.shown(cs.component("Lid")) if hasattr(tl, "shown") else True)
        Gui.Selection.clearSelection()
        h.ribbon("Shell")

    def rule_wall():
        p = sd.shell_panel()
        if not h.check("Base: Shell open", p is not None):
            return
        h.check(
            "Base: Shell's wall from the rule (2 mm)",
            abs(p.inside.value() - 2.0) < 1e-9,
            p.inside.value(),
        )
        h.fit()
        h.click(V(40, 25, 25))

    def ok():
        p1.settle(sd.shell_panel())
        p1.ok()

    def shelled():
        b = base()
        h.check("Base shelled 2 mm (19592)", near(vol(b), BASE_SHELL), vol(b))
        h.check("Base: 11 faces (open top)", len(b.Shape.Faces) == 11, len(b.Shape.Faces))
        h.check("one Shell step", len(shells()) == 1, [o.Label for o in shells()])
        h.check("Lid untouched", near(vol(lid()), LID_BOX), vol(lid()))

    def show_lid():
        tl.click_eye("Lid")

    def hide_base():
        h.check("Lid shown again", lid().Visibility and cs.component("Lid").Visibility)
        tl.click_eye("Base")

    def from_below():
        from SciForgeTests.gui import viewcube_input as vc

        h.check("Base hidden", not cs.component("Base").Visibility)
        vc.click("bottom-front-right")

    def open_shell2():
        h.view().fitAll()
        Gui.Selection.clearSelection()
        h.ribbon("Shell")

    def rule_wall2():
        p = sd.shell_panel()
        if not h.check("Lid: Shell open", p is not None):
            return
        h.check(
            "Lid: Shell's wall from the rule (2 mm)",
            abs(p.inside.value() - 2.0) < 1e-9,
            p.inside.value(),
        )
        h.click(V(40, 25, 25))

    def ok2():
        p1.settle(sd.shell_panel())
        p1.ok()

    def shelled2():
        b = lid()
        h.check("Lid shelled 2 mm (12032)", near(vol(b), LID_SHELL), vol(b))
        h.check("Lid: 11 faces (open bottom)", len(b.Shape.Faces) == 11, len(b.Shape.Faces))
        h.check("two Shell steps", len(shells()) == 2, [o.Label for o in shells()])
        h.check("Lid's timeline: its Shell", "Shell 2" in titles(), titles())
        h.check("Base still 19592", near(vol(base()), BASE_SHELL), vol(base()))

    def show_base():
        tl.click_eye("Base")

    def both_shown():
        h.check("Base shown again", cs.component("Base").Visibility)
        h.fit()
        ok_errors("shells")
        h.shot("journey_pl_2_shells")

    return [
        step(hide_lid, "hide_lid"),
        step(open_shell, "base_shell"),
        step(rule_wall, "base_shell_rule_wall"),
        step(ok, "base_shell_ok"),
        step(shelled, "base_shelled"),
        step(show_lid, "show_lid"),
        step(hide_base, "hide_base"),
        step(from_below, "view_from_below"),
        step(open_shell2, "lid_shell"),
        step(rule_wall2, "lid_shell_rule_wall"),
        step(ok2, "lid_shell_ok"),
        step(shelled2, "lid_shelled"),
        step(show_base, "show_base"),
        step(both_shown, "both_shown"),
    ]


# -- 4. sketches on the parting plane --------------------------------------------------------------
def shells():
    return [o for o in doc().Objects if o.TypeId == "PartDesign::Thickness"]


def thread_side_boss(height=22.95):
    """Volume one default Side 2 boss adds to the Base: plastic_steps' thread side, its
    shank from the floor (z 2) to the tip (z 24.95)."""
    tan1 = math.tan(math.radians(1.0))
    shank = p1.frustum(height, 3.75, 3.75 + height * tan1)
    spigot = p1.frustum(0.9, 3.75 + 0.9 * tan1, 3.75)
    root = p1.fillet_ring(3.75 + height * tan1, 1.0)
    hole = math.pi * 1.2**2 * (0.9 + height + 1.0)
    return shank + spigot + root - hole


def objects(pred):
    return [o for o in doc().Objects if pred(o)]


def bosses():
    from sciforge import plastic_boss

    return objects(plastic_boss.is_boss)


def snaps():
    from sciforge import plastic_snap

    return objects(plastic_snap.is_snap_fit)


def lips():
    from sciforge import plastic_lip

    return objects(plastic_lip.is_lip)


def rests():
    from sciforge import plastic_rest

    return objects(plastic_rest.is_rest)


def rim_sketch_steps(key, points):
    """Create Sketch, click the Base's rim (the parting plane; the Lid hidden so the rim
    shows), points at the global (x, y, 25), Finish Sketch, the Lid shown again."""

    def hide_lid():
        tab("plastic")
        if cs.component("Lid").Visibility:
            tl.click_eye("Lid")

    def create():
        h.check("%s: Lid hidden" % key, not cs.component("Lid").Visibility)
        h.fit()
        h.ribbon("Create Sketch")

    def rim():
        h.click(V(40, 1, 25))

    def draw():
        sk = h.in_sketch()
        if not h.check("%s: sketch open on the rim" % key, sk is not None):
            return
        s[key] = sk.Name
        z = sk.getGlobalPlacement().Base.z
        h.check("%s: on the parting plane z 25" % key, near(z, 25.0), sk.getGlobalPlacement())
        h.check(
            "%s: the sketch is in the Base" % key,
            cs.container_label(sk) == "Base",
            cs.container_label(sk),
        )
        for x, y in points:
            lx, ly = h.to_sketch(sk, V(x, y, 25))
            sk.addGeometry(Part.Point(V(lx, ly, 0)), False)
        doc().recompute()

    def finish():
        h.ribbon("Finish Sketch")

    def done():
        sk = doc().getObject(s[key])
        h.check("%s: %d points" % (key, len(points)), len(sk.Geometry) == len(points))
        tl.click_eye("Lid")

    def lid_back():
        h.check("%s: Lid shown again" % key, cs.component("Lid").Visibility)
        h.fit()

    return [
        step(hide_lid, "%s_hide_lid" % key),
        step(create, "%s_create_sketch" % key),
        step(rim, "%s_click_rim" % key),
        step(draw, "%s_points" % key),
        step(finish, "%s_finish" % key),
        step(done, "%s_done" % key),
        step(lid_back, "%s_lid_back" % key),
    ]


# -- 5. Boss --------------------------------------------------------------------------------------
def boss_steps():
    def start():
        tab("plastic")
        Gui.Selection.clearSelection()
        s["v_base0"], s["v_lid0"] = vol(base()), vol(lid())
        h.ribbon("Boss")

    def pick_sketch():
        p = p1.boss_panel()
        if not h.check("Boss dialog open", p is not None):
            return
        h.check("Boss: the rule named", "ABS 2 mm" in p.rule_label.text(), p.rule_label.text())
        label = doc().getObject(s["boss_sketch"]).Label
        h.check("Boss: clicked the sketch's row", tl.click_row(label), label)

    def previewed():
        p = p1.boss_panel()
        p1.settle(p)
        if not h.check("Boss: still open", p is not None):
            return
        h.check("Boss: 4 points", len(p.refs) == 4, p.refs)
        h.check("Boss: one step per side", len(p.steps) == 2, p.steps)
        h.check("Boss: no error", p.message.text() == "", p.message.text())
        vb, vl = vol(base()), vol(lid())
        want_b, want_l = 4 * thread_side_boss(), 4 * p1.head_side_boss()
        h.check(
            "Boss: thread sides in the Base (hand: 4 x %.2f)" % thread_side_boss(),
            abs(vb - s["v_base0"] - want_b) < 2.0,
            (vb - s["v_base0"], want_b),
        )
        h.check(
            "Boss: head sides in the Lid (hand: 4 x %.2f)" % p1.head_side_boss(),
            abs(vl - s["v_lid0"] - want_l) < 2.0,
            (vl - s["v_lid0"], want_l),
        )
        text = p.bodies_label.text()
        h.check("Boss: both sides named", "Side 1" in text and "Side 2" in text, text)
        s["v_base_b0"] = vb
        p1.tab_of(p, "Ribs")

    def ribs_on():
        p = p1.boss_panel()
        p1.check_box(p.rib_on[2])

    def ribs_made():
        p = p1.boss_panel()
        p1.settle(p)
        if not h.check("Boss: open for ribs", p is not None):
            return
        h.check("Boss: ribs on the thread side", p.options["side2"]["ribs"])
        v = vol(base())
        h.check("Boss: ribs add material", v > s["v_base_b0"] + 40, (v, s["v_base_b0"]))
        h.check(
            "Boss: Base one valid solid", base().Shape.isValid() and len(base().Shape.Solids) == 1
        )
        h.check("Boss: Lid one valid solid", lid().Shape.isValid() and len(lid().Shape.Solids) == 1)
        h.shot("journey_pl_3_boss")
        p1.ok()

    def made():
        h.check("Boss dialog closed", p1.boss_panel() is None)
        found = bosses()
        h.check("two Boss steps (one per side)", len(found) == 2, [o.Label for o in found])
        owners = sorted(str(cs.container_label(b)) for b in found)
        h.check("one Boss in each component", owners == ["Base", "Lid"], owners)
        s["v_base_boss"], s["v_lid_boss"] = vol(base()), vol(lid())
        ok_errors("boss")

    return [
        step(start, "boss_start"),
        step(pick_sketch, "boss_pick_sketch"),
        step(previewed, "boss_previewed"),
        step(ribs_on, "boss_ribs_on"),
        step(ribs_made, "boss_ribs_made"),
        step(made, "boss_made"),
    ]


# -- 6. Snap Fit ----------------------------------------------------------------------------------
def snap_steps():
    def start():
        tab("plastic")
        Gui.Selection.clearSelection()
        h.ribbon("Snap Fit")

    def pick_sketch():
        p = p2.snap_panel()
        if not h.check("Snap Fit dialog open", p is not None):
            return
        h.check("Snap Fit: the rule named", "ABS 2 mm" in p.rule_label.text(), p.rule_label.text())
        label = doc().getObject(s["snap_sketch"]).Label
        h.check("Snap Fit: clicked the sketch's row", tl.click_row(label), label)

    def turn():
        p2.settle(p2.snap_panel)
        p = p2.snap_panel()
        if not h.check("Snap Fit: still open", p is not None):
            return
        h.check(
            "Snap Fit: 1 point", p.field.button.text().startswith("1 point"), p.field.button.text()
        )
        # the catch faces the sketch's X; the user turns it to face the back wall (+Y), as
        # Fusion's rotation handle does: the angle of +Y seen in the sketch
        sk = doc().getObject(s["snap_sketch"])
        local = sk.getGlobalPlacement().Rotation.inverted().multVec(V(0, 1, 0))
        angle = math.degrees(math.atan2(local.y, local.x)) % 360.0
        s["snap_angle"] = angle
        ui.type_into(p.angle.widget, "%g" % round(angle, 6))

    def previewed():
        p2.settle(p2.snap_panel)
        p = p2.snap_panel()
        if not h.check("Snap Fit: still open after the turn", p is not None):
            return
        h.check("Snap Fit: turned", near(p.options["angle"], s["snap_angle"]), p.options["angle"])
        h.check("Snap Fit: no error", not p.error and "⚠" not in p2.message(p), p2.message(p))
        added = vol(lid()) - s["v_lid_boss"]
        cut = s["v_base_boss"] - vol(base())
        # beam 12 x 6 x 2 = 144 and its catch ~12.8, hanging from the parting plane, the
        # base fillet; joined into the Lid (one solid)
        h.check("Snap Fit: the hook on the Lid (~159)", 150 < added < 270, added)
        h.check("Snap Fit: Lid one solid", len(lid().Shape.Solids) == 1, len(lid().Shape.Solids))
        h.check("Snap Fit: its groove in the Base (21.824)", near(cut, p2.GROOVE, 1e-4), cut)
        box = Part.makeBox(6.4, 1.2, 25, V(36.8, 48.0, 0)).common(base().Shape)
        wall = 6.4 * 1.2 * 25  # that piece of the back wall (and floor) before the groove
        h.check(
            "Snap Fit: the whole groove is in the back wall at x 40",
            near(wall - box.Volume, p2.GROOVE, 1e-6),
            (wall, box.Volume),
        )
        h.shot("journey_pl_4_snap")
        p2.ok()

    def made():
        h.check("Snap Fit dialog closed", p2.snap_panel() is None)
        found = snaps()
        if not h.check("one Snap Fit step", len(found) == 1, [o.Label for o in found]):
            return
        h.check("in the Lid", cs.container_label(found[0]) == "Lid", cs.container_label(found[0]))
        h.check("its groove step in the Base", len(p2.followers(found[0])) == 1)
        s["v_base_snap"], s["v_lid_snap"] = vol(base()), vol(lid())
        ok_errors("snap fit")

    return [
        step(start, "snap_start"),
        step(pick_sketch, "snap_pick_sketch"),
        step(turn, "snap_turn"),
        step(previewed, "snap_previewed"),
        step(made, "snap_made"),
    ]


# -- 7. Lip ----------------------------------------------------------------------------------------
LIP_BAND = 78 * 48 - 76 * 46  # 248: a 1 x 1 lip round the 80 x 50 rim
LIP_DRAFTED = LIP_BAND - 0.5 * 0.017455064928217585 * (2 * (78 + 48) + 2 * (76 + 46))


def lip_steps():
    def hide_lid():
        tab("plastic")
        tl.click_eye("Lid")

    def start():
        h.check("Lip: Lid hidden", not cs.component("Lid").Visibility)
        Gui.Selection.clearSelection()
        h.ribbon("Lip")

    def asks():
        p = p2.lip_panel()
        if not h.check("Lip dialog open", p is not None):
            return
        h.check("Lip: Lip And Groove first", p.type.currentText() == "Lip And Groove")
        h.fit()
        h.click_edge(RIM_EDGES[0])

    def edge(i):
        def fn():
            p2.settle(p2.lip_panel)
            p = p2.lip_panel()
            text = p.field.button.text() if p is not None else ""
            h.check(
                "Lip: edge %d picked" % i, text.startswith("%d edge" % i), (text, p2.message(p))
            )
            h.click_edge(RIM_EDGES[i])

        return step(fn, "lip_edge_%d" % (i + 1))

    def made_preview():
        p2.settle(p2.lip_panel)
        p = p2.lip_panel()
        if not h.check("Lip: still open", p is not None):
            return
        h.check(
            "Lip: 4 edges",
            p.field.button.text() == "4 edges",
            (p.field.button.text(), p2.message(p)),
        )
        gain = vol(base()) - s["v_base_snap"]
        loss = s["v_lid_snap"] - vol(lid())
        h.check(
            "Lip: the lip on the Base (+%.3f)" % LIP_DRAFTED, near(gain, LIP_DRAFTED, 1e-4), gain
        )
        h.check("Lip: the groove in the Lid (~300)", 280 < loss < 320, loss)
        h.check("Lip: the other body found", p.mate_label.text() != "", p.mate_label.text())
        h.check("Lip: no error", "⚠" not in p2.message(p), p2.message(p))
        h.check(
            "Lip: the shoulder beside the 1 mm lip on the 2 mm wall",
            "shoulder beside the lip: 1.00 mm" in p.shoulder.text(),
            p.shoulder.text(),
        )
        h.shot("journey_pl_5_lip")
        p2.ok()

    def made():
        h.check("Lip dialog closed", p2.lip_panel() is None)
        found = lips()
        if not h.check("one Lip step", len(found) == 1, [o.Label for o in found]):
            return
        h.check("in the Base", cs.container_label(found[0]) == "Base", cs.container_label(found[0]))
        s["v_base_lip"], s["v_lid_lip"] = vol(base()), vol(lid())
        tl.click_eye("Lid")

    def shown():
        h.check("Lid shown again", cs.component("Lid").Visibility)
        ok_errors("lip")

    return [
        step(hide_lid, "lip_hide_lid"),
        step(start, "lip_start"),
        step(asks, "lip_asks"),
        edge(1),
        edge(2),
        edge(3),
        step(made_preview, "lip_preview"),
        step(made, "lip_made"),
        step(shown, "lip_lid_shown"),
    ]


# -- 8. Rest ---------------------------------------------------------------------------------------
def construct_panel():
    from sciforge import construct_ui, taskui

    panel = taskui.current()
    return panel if isinstance(panel, construct_ui.ConstructPanel) else None


def rest_steps():
    def offset_plane():
        tab("solid")
        Gui.Selection.clearSelection()
        h.ribbon("Offset Plane")

    def click_front():
        h.fit()
        h.click(V(40, 0, 12))

    def distance():
        p = construct_panel()
        if not h.check("Offset Plane dialog", p is not None and p.datum is not None):
            return
        ui.type_into(p.distance.widget, "3")

    def plane_ok():
        p = construct_panel()
        y = p.datum.getGlobalPlacement().Base.y if p is not None and p.datum else None
        h.check("the plane 3 mm in front of the wall (y -3)", y is not None and near(y, -3.0), y)
        h.task_button("OK")

    def create():
        h.check("Offset Plane closed", construct_panel() is None)
        h.fit()
        h.ribbon("Create Sketch")

    def click_plane():
        h.click(V(40, -3, 12))

    def draw():
        sk = h.in_sketch()
        if not h.check("Rest: sketch open on the plane", sk is not None):
            return
        s["rest_sketch"] = sk.Name
        y = sk.getGlobalPlacement().Base.y
        h.check("Rest: the sketch at y -3", near(y, -3.0), sk.getGlobalPlacement())
        a = h.to_sketch(sk, V(30, -3, 6))
        b = h.to_sketch(sk, V(50, -3, 16))
        h.draw_rectangle(sk, min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]))

    def finish():
        h.ribbon("Finish Sketch")

    def start():
        tab("plastic")
        Gui.Selection.clearSelection()
        h.ribbon("Rest")

    def click_profile():
        p = p1.rest_panel()
        if not h.check("Rest dialog open", p is not None):
            return
        h.check("Rest: the rule named", "ABS 2 mm" in p.rule_label.text(), p.rule_label.text())
        h.check(
            "Rest: thickness 2 from the rule", near(p.thickness.value(), 2.0), p.thickness.value()
        )
        h.fit()
        h.click(V(40, -3, 11))

    def previewed():
        p = p1.rest_panel()
        p1.settle(p)
        if not h.check("Rest: still open", p is not None):
            return
        h.check("Rest: the profile picked", len(p.refs) == 1, p.refs)
        h.check("Rest: no error", p.message.text() == "", p.message.text())
        gain = vol(base()) - s["v_base_lip"]
        # plate 20 x 10 x 2 = 400, walls (20 x 10 - 16 x 6) x 1 = 104, the old wall inside
        # them 16 x 6 x 2 = 192 taken away: +312 (the 1 deg draft moves it a little)
        h.check("Rest: a pad 3 mm out of the wall (~+312)", 295 < gain < 330, gain)
        flat = [
            f
            for f in base().Shape.Faces
            if near(f.BoundBox.YMin, -3.0) and near(f.BoundBox.YMax, -3.0)
        ]
        h.check(
            "Rest: one flat 20 x 10 face at y -3",
            len(flat) == 1 and near(flat[0].Area, 200.0, 1e-6),
            [f.Area for f in flat],
        )
        h.shot("journey_pl_6_rest")
        p1.ok()

    def made():
        h.check("Rest dialog closed", p1.rest_panel() is None)
        h.check("one Rest step", len(rests()) == 1)
        h.check("Base one valid solid", base().Shape.isValid() and len(base().Shape.Solids) == 1)
        s["v_base_rest"], s["v_lid_rest"] = vol(base()), vol(lid())
        ok_errors("rest")

    return [
        step(offset_plane, "rest_offset_plane"),
        step(click_front, "rest_click_front"),
        step(distance, "rest_plane_distance"),
        step(plane_ok, "rest_plane_ok"),
        step(create, "rest_create_sketch"),
        step(click_plane, "rest_click_plane"),
        step(draw, "rest_rectangle"),
        step(finish, "rest_finish"),
        step(start, "rest_start"),
        step(click_profile, "rest_click_profile"),
        step(previewed, "rest_previewed"),
        step(made, "rest_made"),
    ]


# -- 9. Design Advice -------------------------------------------------------------------------------
def advice_steps():
    def start():
        tab("plastic")
        Gui.Selection.clearSelection()
        p2.menu("INSPECT", "Design Advice")

    def looked():
        from sciforge import plastic_advice, plastic_advice_core

        p2.settle(p2.advice_panel, 30000)
        p = p2.advice_panel()
        if not h.check("Design Advice open", p is not None):
            return
        text = p.bodies_field.button.text()
        h.check("Advice: both bodies", text == "2 bodies", text)
        h.check("Advice: the rule named", "ABS 2 mm" in p.rules.text(), p.rules.text())
        c = plastic_advice_core.summary(plastic_advice.results(p.analysis))
        count = p.issues.topLevelItemCount()
        h.check("Advice: issues listed", count > 0, count)
        h.check("Advice: the walls have no draft", c["draft"] >= 4, c)
        h.check("Advice: a summary", p.summary.text() != "", p.summary.text())
        h.check("Advice: no error", "⚠" not in p2.message(p), p2.message(p))
        s["advice_counts"] = c
        h.shot("journey_pl_7_advice")
        p2.ok()

    def kept():
        from sciforge import plastic_advice

        found = objects(plastic_advice.is_advice)
        h.check("Advice kept in the browser (one analysis)", len(found) == 1, found)
        h.check("Advice: no timeline step", not named(r".*Advice.*"), titles())
        same = near(vol(base()), s["v_base_rest"]) and near(vol(lid()), s["v_lid_rest"])
        h.check("Advice changed no body", same)

    return [step(start, "advice_start"), step(looked, "advice_looked"), step(kept, "advice_kept")]


def build_steps():
    """The whole enclosure: components, rule, shells, Boss, Snap Fit, Lip, Rest."""
    return (
        [new_design]
        + base_steps()
        + lid_steps()
        + assign_steps("Base")
        + assign_steps("Lid")
        + shell_steps()
        + rim_sketch_steps("boss_sketch", BOSS_POINTS)
        + boss_steps()
        + rim_sketch_steps("snap_sketch", [SNAP_POINT])
        + snap_steps()
        + lip_steps()
        + rest_steps()
    )
