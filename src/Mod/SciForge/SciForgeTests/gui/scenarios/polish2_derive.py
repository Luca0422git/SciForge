# SPDX-License-Identifier: LGPL-2.1-or-later
"""Derive with the source's structure and a chosen source version (docs/sciforge/parity/
misc.md, Derive). Only real input in the dialogs.

Source design Robot.FCStd (saved twice, closed): component "Arm" moved to x 10 holding the
body Upper (v1: 20 x 10 x 5 = 1000; v2: 40 x 10 x 5 = 2000) and the component "Hand"
(moved up 5 inside Arm) holding Finger (4 x 4 x 4 = 64); a loose body Base (30 x 30 x 2).

P1 Insert Derive into a saved design "Cell": the dialog has a Version choice (Latest (v2),
   v2, v1) and lists the components; tick Arm, OK: one Derive step; a component Arm with
   Upper (2000, at x 10..50) and in it a component Hand with Finger (at z 5..9); Base is not
   brought in; no step of their own in the timeline.
P2 Edit Derive (double-click), Version v1, OK: Upper is v1's 1000; the Derive says a newer
   version exists (yellow) and the application bar's Out-of-Date button shows.
P3 Right-click the Derive > Update Derive: the newest (2000), up to date, the button goes.
   Ctrl+Z: v1's 1000 again; Ctrl+Y: 2000.
P4 Robot saved again with a body Thumb (2 x 2 x 6) added in Hand: out of date; Update
   Derive: Thumb comes in, inside the derived Hand.
P5 Edit Derive: Arm unticked, Base ticked, OK: Arm and Hand with their bodies go, Base comes
   in as a body of its own. Ctrl+Z: Arm back.
P6 Saved, closed, opened again: the derived structure is there, up to date.
"""

import os

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import misc_steps as m
from SciForgeTests.gui import polish2_steps as p2
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import timeline_input as t
from SciForgeTests.gui import versions_input as vi

V = App.Vector
s = {}


def doc():
    return App.getDocument(s["doc"]) if s.get("doc") in App.listDocuments() else None


def master():
    from sciforge import derive

    d = doc()
    found = derive.masters(d) if d is not None else []
    return found[0] if found else None


def by_label(label, type_id=None):
    d = doc()
    if d is None:
        return None
    for obj in d.Objects:
        if obj.Label == label and (type_id is None or obj.TypeId == type_id):
            return obj
    return None


def body(label):
    return by_label(label, "PartDesign::Body")


def part(label):
    return by_label(label, "App::Part")


def gvol(obj):
    try:
        return obj.Shape.Volume if obj is not None and not obj.Shape.isNull() else None
    except Exception:
        return None


def global_box(b):
    """The body's bounding box in the design (component placements included)."""
    from sciforge import bodies

    return bodies.global_shape(b).BoundBox


def make_source(folder):
    from sciforge import components

    d = App.newDocument("Robot")
    arm = components.new_component(d, "Arm")
    arm.Placement.Base = V(10, 0, 0)
    p2.make_box(d, "Upper", 20, 10, 5, part=arm)
    hand = components.new_component(d, "Hand", arm)
    hand.Placement.Base = V(0, 0, 5)
    p2.make_box(d, "Finger", 4, 4, 4, part=hand)
    p2.make_box(d, "Base", 30, 30, 2, at=V(0, 40, 0))
    for name, label in (("Upper", "Upper"), ("Finger", "Finger"), ("Base", "Base")):
        d.getObject(name).Label = label
    d.recompute()
    path = os.path.join(folder, "Robot.FCStd")
    d.saveAs(path)
    p2.process()
    d.getObject("UpperBox").Length = 40
    d.recompute()
    d.save()
    p2.process()
    Gui.getDocument(d.Name).Modified = False
    App.closeDocument(d.Name)
    return path


def setup():
    from sciforge import derive_ui

    Gui.activateWorkbench("SciForgeWorkbench")
    s["folder"] = m.project_folder()
    p2.set_project(s["folder"])
    s["source"] = make_source(s["folder"])
    derive_ui.FILE_PICKER = lambda title: s["source"]
    d = App.newDocument("Cell")
    s["doc"] = d.Name
    d.saveAs(os.path.join(s["folder"], "Cell.FCStd"))
    Gui.getDocument(d.Name).Modified = False
    p2.process()
    h.fit()
    from sciforge import versions_ui

    listed = versions_ui.store_of(s["source"]).versions()
    h.check("Robot saved twice: v1, v2", [v.number for v in listed] == [1, 2], listed)


# -- P1 ----
def p1_open():
    si.menu_item("INSERT", "Insert Derive")


p1_open.wait_ms = 1500


def p1_dialog():
    p = m.derive_panel()
    h.check("P1 the Derive dialog", p is not None, h.popups())
    if p is None:
        return
    combo = p.version_combo
    items = [combo.itemText(i) for i in range(combo.count())] if combo else []
    h.check(
        "P1 a Version choice: Latest (v2), v2, v1",
        [i.split()[0] for i in items] == ["Latest", "v2", "v1"] and items[0] == "Latest (v2)",
        items,
    )
    groups = [p.tree.topLevelItem(i).text(0) for i in range(p.tree.topLevelItemCount())]
    h.check("P1 the components are listed first", groups[:1] == ["Components"], groups)
    first = p.tree.topLevelItem(0)
    rows = [first.child(j).text(0) for j in range(first.childCount())] if first else []
    h.check("P1 Arm, and Hand inside it", rows == ["Arm", "Arm > Hand"], rows)
    s["arm_key"] = next(
        (
            k
            for k, item in p.data["items"].items()
            if k.startswith("component:") and item["label"] == "Arm"
        ),
        None,
    )
    s["base_key"] = next(
        (
            k
            for k, item in p.data["items"].items()
            if k.startswith("body:") and item["label"] == "Base"
        ),
        None,
    )
    m.tick(p, s["arm_key"])
    h.shot("P1-dialog")


def p1_ok():
    h.task_button("OK")


p1_ok.wait_ms = 1500


def p1_made():
    arm, hand = part("Arm"), part("Hand")
    upper, finger = body("Upper"), body("Finger")
    h.check("P1 one Derive step", master() is not None)
    h.check("P1 a component Arm", arm is not None, [o.Label for o in doc().Objects])
    h.check(
        "P1 a component Hand inside Arm",
        hand is not None and hand.getParentGeoFeatureGroup() is arm,
    )
    h.check("P1 Upper inside Arm", upper is not None and upper.getParentGeoFeatureGroup() is arm)
    h.check(
        "P1 Finger inside Hand", finger is not None and finger.getParentGeoFeatureGroup() is hand
    )
    h.check("P1 Upper is the newest (2000)", p2.near(gvol(upper), 2000.0), gvol(upper))
    if upper is not None:
        bb = global_box(upper)
        h.check(
            "P1 Upper at x 10..50 (where it is in Robot)",
            p2.near(bb.XMin, 10.0) and p2.near(bb.XMax, 50.0),
            (bb.XMin, bb.XMax),
        )
    if finger is not None:
        bb = global_box(finger)
        h.check(
            "P1 Finger at z 5..9 and x 10..14",
            p2.near(bb.ZMin, 5.0) and p2.near(bb.XMin, 10.0),
            (bb.XMin, bb.ZMin),
        )
    h.check("P1 Base not brought in", body("Base") is None)
    titles = t.titles()
    h.check(
        "P1 the timeline shows one Derive step (the components are no steps)",
        [x for x in titles if x.startswith("Derive")] == [m.timeline_title(master())]
        and not [x for x in titles if x.startswith("Component")],
        titles,
    )
    shown = [o is not None and o.ViewObject.isVisible() for o in (arm, hand, upper, finger)]
    h.check("P1 Arm, Hand, Upper and Finger are shown", all(shown), shown)
    h.fit()


def p1_look():
    h.shot("P1-derived")


# -- P2: an older version ----
def p2_edit():
    t.double_click(m.timeline_title(master()))


p2_edit.wait_ms = 1500


def p2_pick_v1():
    p = m.derive_panel()
    if not h.check("P2 the Edit Derive dialog", p is not None):
        return
    combo = p.version_combo
    h.check("P2 it says Latest", combo.currentIndex() == 0, combo.currentText())
    _choose(combo, "v1")


def _choose(combo, start):
    from SciForgeTests.gui import dialog_input as ui

    for i in range(combo.count()):
        if combo.itemText(i).startswith(start):
            return ui.choose(combo, combo.itemText(i))
    return False


def p2_ok():
    h.task_button("OK")


p2_ok.wait_ms = 2600  # (the application bar looks every 2 s)


def p2_older():
    from sciforge import derive, derive_core

    upper = body("Upper")
    h.check("P2 Upper is v1's 1000", p2.near(gvol(upper), 1000.0), gvol(upper))
    h.check("P2 the Derive uses v1", derive.version_of(master()) == 1, derive.version_of(master()))
    h.check(
        "P2 out of date: a newer version exists",
        derive.state(master()) == derive_core.NEWER,
        derive.state(master()),
    )
    item = m.timeline_item(master())
    h.check(
        "P2 yellow in the timeline, saying v1",
        item is not None and item.status == "warning" and "v1 of Robot" in item.message,
        item and (item.status, item.message),
    )
    button = p2.child(Gui.getMainWindow(), "SciForgeOutOfDate")
    h.check("P2 the Out-of-Date button shows", button is not None and button.isVisible())


# -- P3: Update Derive takes the newest ----
def p3_update():
    t.menu(m.timeline_title(master()), "Update Derive")


p3_update.wait_ms = 2600


def p3_updated():
    from sciforge import derive, derive_core

    upper = body("Upper")
    h.check("P3 Upper is the newest 2000", p2.near(gvol(upper), 2000.0), gvol(upper))
    h.check("P3 the latest again", derive.version_of(master()) == 0)
    h.check("P3 up to date", derive.state(master()) == derive_core.UP_TO_DATE)
    button = p2.child(Gui.getMainWindow(), "SciForgeOutOfDate")
    h.check("P3 the Out-of-Date button went", button is not None and not button.isVisible())
    t.undo()


def p3_undone():
    h.check("P3 Ctrl+Z: v1's 1000 again", p2.near(gvol(body("Upper")), 1000.0), gvol(body("Upper")))
    t.redo()


def p3_redone():
    h.check("P3 Ctrl+Y: 2000", p2.near(gvol(body("Upper")), 2000.0), gvol(body("Upper")))


# -- P4: a new body in the source's Hand ----
def p4_change_source():
    def change(d):
        hand = [o for o in d.Objects if o.TypeId == "App::Part" and o.Label == "Hand"][0]
        thumb = p2.make_box(d, "Thumb", 2, 2, 6, part=hand)
        thumb.Label = "Thumb"

    m.edit_saved(s["source"], change)
    App.setActiveDocument(s["doc"])  # back on Cell's tab


p4_change_source.wait_ms = 1500


def p4_update():
    from sciforge import derive, derive_core

    h.check("P4 out of date after the source's save", derive.state(master()) == derive_core.NEWER)
    t.menu(m.timeline_title(master()), "Update Derive")


p4_update.wait_ms = 1500


def p4_thumb():
    thumb, hand = body("Thumb"), part("Hand")
    h.check("P4 Thumb came in", thumb is not None, [o.Label for o in doc().Objects])
    h.check(
        "P4 inside the derived Hand", thumb is not None and thumb.getParentGeoFeatureGroup() is hand
    )
    h.check("P4 Thumb 2 x 2 x 6", p2.near(gvol(thumb), 24.0), gvol(thumb))


# -- P5: untick Arm, tick Base ----
def p5_edit():
    t.double_click(m.timeline_title(master()))


p5_edit.wait_ms = 1500


def p5_ticks():
    p = m.derive_panel()
    if not h.check("P5 the Edit Derive dialog", p is not None):
        return
    m.tick(p, s["arm_key"], False)
    m.tick(p, s["base_key"], True)
    h.task_button("OK")


p5_ticks.wait_ms = 1500


def p5_changed():
    h.check(
        "P5 Arm and Hand went",
        part("Arm") is None and part("Hand") is None,
        [o.Label for o in doc().Objects if o.TypeId == "App::Part"],
    )
    h.check(
        "P5 their bodies went",
        body("Upper") is None and body("Finger") is None and body("Thumb") is None,
    )
    base = body("Base")
    h.check(
        "P5 Base came in, a body of its own",
        base is not None and base.getParentGeoFeatureGroup() is None,
    )
    h.check("P5 Base 30 x 30 x 2", p2.near(gvol(base), 1800.0), gvol(base))
    t.undo()


def p5_undone():
    h.check("P5 Ctrl+Z: Arm back with Upper", part("Arm") is not None and body("Upper") is not None)
    h.check("P5 Ctrl+Z: Base gone again", body("Base") is None)


# -- P6: save and open again ----
def p6_save():
    d = doc()
    d.save()
    Gui.getDocument(d.Name).Modified = False
    path = d.FileName
    App.closeDocument(d.Name)
    s["doc"] = App.openDocument(path).Name


p6_save.wait_ms = 1500


def p6_reopened():
    from sciforge import derive, derive_core

    h.check("P6 the Derive is there", master() is not None)
    h.check(
        "P6 Arm, Hand and their bodies",
        part("Arm") is not None
        and part("Hand") is not None
        and body("Finger") is not None
        and body("Thumb") is not None,
    )
    h.check("P6 Upper 2000", p2.near(gvol(body("Upper")), 2000.0), gvol(body("Upper")))
    h.check("P6 up to date", derive.state(master()) == derive_core.UP_TO_DATE)
    h.check("P6 no pop-up", not vi.popups_except(()), vi.popups_except(()))
    h.fit()


def p6_look():
    h.shot("P6-reopened")


STEPS = [
    setup,
    p1_open,
    p1_dialog,
    p1_ok,
    p1_made,
    p1_look,
    p2_edit,
    p2_pick_v1,
    p2_ok,
    p2_older,
    p3_update,
    p3_updated,
    p3_undone,
    p3_redone,
    p4_change_source,
    p4_update,
    p4_thumb,
    p5_edit,
    p5_ticks,
    p5_changed,
    p5_undone,
    p6_save,
    p6_reopened,
    p6_look,
]

h.run("polish2_derive", STEPS)
