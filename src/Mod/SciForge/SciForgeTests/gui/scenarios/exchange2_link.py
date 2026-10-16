# SPDX-License-Identifier: LGPL-2.1-or-later
"""Insert into Current Design and Break Link (exchange-2, docs/sciforge/parity/
insert-export.md Part 2; Fusion: "the design is inserted as an external component ... An
Insert feature displays in the Timeline", right-click > Break Link makes it "a stand-alone
part"). Real input: the Data Panel's right-click menu, the Move dialog, the browser's
right-click menu, Ctrl+Z / Ctrl+Y.

A project folder with Wheel.FCStd (a 10 mm box, a PartDesign Box step) and Cart.FCStd (a
plate), Cart open, the Data Panel shown.
P1  Data Panel: right-click Wheel > Insert into Current Design: a component "Wheel" linked
    to Wheel's file (its body a copy, 1000 mm3, no steps of its own in the timeline but the
    component's); the Move dialog opens on it; X Distance 30, OK: it stands at X 30.
P2  Ctrl+Z: back at 0; Ctrl+Z: no Wheel; Ctrl+Y twice: linked again, at 30.
P3  Browser: right-click Wheel > Break Link: Wheel's body with its Box step is copied in
    (1000 mm3, still at 30), the component is no longer linked, the Box is in the timeline.
P4  Ctrl+Z: linked again; Ctrl+Y: independent again.
P5  Wheel inserted a second time ("Wheel (2)", linked; Esc in the Move dialog), Cart saved;
    Wheel.FCStd taken away; Cart opened again: says the linked design was not found; the
    independent Wheel is whole (1000); right-click Wheel (2) > Break Link is refused with
    the reason (the design is not there to copy its features from).
P6  The menu offers Break Link only on linked components (not on the plate's body).
"""

import os
import shutil
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import exchange_steps as x
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import insert_steps as i
from SciForgeTests.gui import timeline_input as t
from SciForgeTests.gui import versions_input as vi
from SciForgeTests.gui import widget_input as w

s = {}
PREFS = "User parameter:BaseApp/Preferences/Mod/SciForge/Files"


def cart():
    return App.getDocument("Cart") if "Cart" in App.listDocuments() else None


def wheel_comp(label="Wheel"):
    return x.comp(label, cart())


def linked(comp):
    from sciforge import design_insert

    return design_insert.is_linked(comp)


def wheel_body(label="Wheel"):
    comp = wheel_comp(label)
    found = x.bodies_in(comp, cart()) if comp is not None else []
    return found[0] if found else None


def move_panel():
    from sciforge import component_move_ui, taskui

    p = taskui.current()
    return p if isinstance(p, component_move_ui.ComponentMovePanel) else None


def setup():
    from sciforge import components

    Gui.activateWorkbench("SciForgeWorkbench")
    s["project"] = tempfile.mkdtemp(prefix="sciforge-exchange2-link-")
    App.ParamGet(PREFS).SetString("ProjectFolder", s["project"])
    App.ParamGet(PREFS).SetBool("AskDescription", True)
    wheel = App.newDocument("Wheel")
    body = wheel.addObject("PartDesign::Body", "Body")
    box = wheel.addObject("PartDesign::AdditiveBox", "Box")
    body.addObject(box)
    box.Length = box.Width = box.Height = 10
    wheel.recompute()
    s["wheel"] = os.path.join(s["project"], "Wheel.FCStd")
    wheel.saveAs(s["wheel"])
    Gui.getDocument("Wheel").Modified = False
    App.closeDocument("Wheel")
    doc = App.newDocument("Cart")
    import Part

    plate = components.new_body_in(doc, None, "Plate")
    base = doc.addObject("Part::Feature", "PlateShape")
    base.Shape = Part.makeBox(60, 40, 2, App.Vector(-70, 0, 0))
    plate.BaseFeature = base
    doc.recompute()
    s["cart"] = os.path.join(s["project"], "Cart.FCStd")
    doc.saveAs(s["cart"])
    Gui.getDocument("Cart").Modified = False
    h.fit()
    from sciforge import versions_ui

    versions_ui.show_panel()


setup.wait_ms = 1500


def menu_on_card(text_start, entry):
    lst = vi.panel_list()
    if not h.check("the Data Panel", lst is not None):
        return False
    for k in range(lst.count()):
        item = lst.item(k)
        if item.text().startswith(text_start):
            rect = lst.visualItemRect(item)
            ok = w.right_click(lst.viewport(), rect.center(), entry)
            h.check("Data Panel menu %s > %s" % (text_start, entry), ok)
            return ok
    h.check("a card %s" % text_start, False, [lst.item(k).text() for k in range(lst.count())])
    return False


# -- P1 ----------------------------------------------------------------------------------------
def p1_insert():
    menu_on_card("Wheel", "Insert into Current Design")


p1_insert.wait_ms = 2500


def p1_check():
    comp = wheel_comp()
    h.check("P1 a component Wheel", comp is not None, x.labels(cart()))
    h.check("P1 linked to Wheel's file", comp is not None and linked(comp))
    body = wheel_body()
    h.check(
        "P1 its body is a copy of Wheel's box (1000)",
        body is not None and x.near(body.Shape.Volume, 1000.0),
        body and body.Shape.Volume,
    )
    titles = i.timeline_titles()
    h.check("P1 the timeline shows the component", "Wheel" in titles, titles)
    h.check("P1 no Box step of its own (it is linked)", "Box" not in titles, titles)
    h.check("P1 the Move dialog places it", move_panel() is not None)
    p = move_panel()
    if p is not None:
        i.type_value(p.distance_fields[0], "30")


p1_check.wait_ms = 800


def p1_ok():
    h.task_button("OK")


p1_ok.wait_ms = 1200


def p1_moved():
    comp = wheel_comp()
    h.check(
        "P1 it stands at X 30",
        comp is not None and x.near3(tuple(comp.Placement.Base), (30, 0, 0)),
        comp and comp.Placement.Base,
    )
    h.shot("1-inserted")
    t.ctrl("z")


p1_moved.wait_ms = 1200


# -- P2 ----------------------------------------------------------------------------------------
def p2_undo_insert():
    comp = wheel_comp()
    h.check(
        "P2 Ctrl+Z: back at 0",
        comp is not None and x.near3(tuple(comp.Placement.Base), (0, 0, 0)),
        comp and comp.Placement.Base,
    )
    t.ctrl("z")


p2_undo_insert.wait_ms = 1500


def p2_redo():
    h.check("P2 Ctrl+Z again: no Wheel", wheel_comp() is None, x.labels(cart()))
    t.ctrl("y")


p2_redo.wait_ms = 1500


def p2_redo_move():
    comp = wheel_comp()
    h.check("P2 Ctrl+Y: linked again", comp is not None and linked(comp))
    t.ctrl("y")


p2_redo_move.wait_ms = 1500


def p2_check():
    comp = wheel_comp()
    h.check(
        "P2 Ctrl+Y again: at 30",
        comp is not None and x.near3(tuple(comp.Placement.Base), (30, 0, 0)),
        comp and comp.Placement.Base,
    )


# -- P3 ----------------------------------------------------------------------------------------
def p3_break():
    entries = [e for e, _on in t.row_menu_entries("Wheel")]
    h.check("P3 the menu offers Break Link", "Break Link" in entries, entries)
    t.row_menu("Wheel", "Break Link")


p3_break.wait_ms = 2000


def p3_check():
    comp = wheel_comp()
    h.check("P3 no longer linked", comp is not None and not linked(comp))
    body = wheel_body()
    h.check(
        "P3 the body is whole (1000)",
        body is not None and x.near(body.Shape.Volume, 1000.0),
        body and body.Shape.Volume,
    )
    h.check(
        "P3 and still at 30",
        body is not None and x.near3(x.centre(body), (35, 5, 5)),
        body and x.centre(body),
    )
    boxes = [o for o in (body.Group if body else []) if o.TypeId == "PartDesign::AdditiveBox"]
    h.check("P3 Wheel's Box step was copied in", len(boxes) == 1, body and body.Group)
    titles = i.timeline_titles()
    h.check("P3 the Box is in the timeline", any(tt.startswith("Box") for tt in titles), titles)
    h.check("P3 SciForge says it can be edited here", "edited here" in x.told(), x.told())
    t.ctrl("z")


p3_check.wait_ms = 1500


# -- P4 ----------------------------------------------------------------------------------------
def p4_redo():
    comp = wheel_comp()
    h.check("P4 Ctrl+Z: linked again", comp is not None and linked(comp))
    body = wheel_body()
    h.check("P4 its copy is whole", body is not None and x.near(body.Shape.Volume, 1000.0), body)
    t.ctrl("y")


p4_redo.wait_ms = 1500


def p4_check():
    comp = wheel_comp()
    h.check("P4 Ctrl+Y: independent again", comp is not None and not linked(comp))
    body = wheel_body()
    h.check("P4 whole", body is not None and x.near(body.Shape.Volume, 1000.0), body and body.Shape)


# -- P5 ----------------------------------------------------------------------------------------
def p5_insert_again():
    menu_on_card("Wheel", "Insert into Current Design")


p5_insert_again.wait_ms = 2500


def p5_escape():
    h.check("P5 the Move dialog", move_panel() is not None)
    h.press(QtCore.Qt.Key_Escape)


p5_escape.wait_ms = 1000


def p5_save_and_remove():
    second = wheel_comp("Wheel (2)")
    h.check("P5 a second, linked Wheel (2)", second is not None and linked(second), x.labels())
    doc = cart()
    doc.save()
    Gui.getDocument("Cart").Modified = False
    for name in list(App.listDocuments()):
        Gui.getDocument(name).Modified = False
        App.closeDocument(name)
    s["away"] = s["wheel"] + ".away"
    shutil.move(s["wheel"], s["away"])
    from sciforge import commands

    commands._TOLD["msg"] = None
    App.openDocument(s["cart"])


p5_save_and_remove.wait_ms = 2500
p5_save_and_remove.known = True  # FreeCAD's own 'file does not exist' lines


def p5_reopened():
    doc = cart()
    h.check("P5 Cart opens", doc is not None)
    msg = x.told()
    h.check("P5 SciForge says the linked design was not found", "not found" in msg, msg)
    body = wheel_body()
    h.check(
        "P5 the independent Wheel is whole",
        body is not None and x.near(body.Shape.Volume, 1000.0),
        body and body.Shape.Volume,
    )
    h.new_errors()
    t.row_menu("Wheel (2)", "Break Link")


p5_reopened.wait_ms = 1500


def p5_check():
    second = wheel_comp("Wheel (2)")
    h.check("P5 Break Link refused: still linked", second is not None and linked(second))
    msg = x.told()
    h.check("P5 it says why", "not found" in msg and "Wheel" in msg, msg)


# -- P6 ----------------------------------------------------------------------------------------
def p6_menu():
    entries = [e for e, _on in t.row_menu_entries("Plate")]
    h.check("P6 no Break Link on an ordinary body", "Break Link" not in entries, entries)
    h.check("P6 Save As Mesh is there", "Save As Mesh" in entries, entries)


def cleanup():
    from sciforge import versions_ui

    try:
        versions_ui.hide_panel()
    except Exception:
        pass
    for name in list(App.listDocuments()):
        try:
            Gui.getDocument(name).Modified = False
        except Exception:
            pass
        App.closeDocument(name)
    App.ParamGet(PREFS).RemString("ProjectFolder")
    shutil.rmtree(s["project"], ignore_errors=True)
    h.new_errors()


h.run(
    "exchange2_link",
    [
        setup,
        p1_insert,
        p1_check,
        p1_ok,
        p1_moved,
        p2_undo_insert,
        p2_redo,
        p2_redo_move,
        p2_check,
        p3_break,
        p3_check,
        p4_redo,
        p4_check,
        p5_insert_again,
        p5_escape,
        p5_save_and_remove,
        p5_reopened,
        p5_check,
        p6_menu,
        cleanup,
    ],
)
