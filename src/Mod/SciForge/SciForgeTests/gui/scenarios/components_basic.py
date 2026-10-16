# SPDX-License-Identifier: LGPL-2.1-or-later
"""Components the way Fusion users use them (real input only).

Path A, New Component from the ribbon: the dialog proposes Component1 and Activate; the
        name is typed (Bracket), OK. The browser shows the component with the activate
        ring filled; the timeline shows its step.
Path B, work goes into the active component: Create Sketch, a rectangle, E, 10: the body
        is Bracket > Bodies > Body1; the root has no Bodies folder.
Path C, activate the root with the ring on the design's row, sketch and extrude again: a
        root body; the timeline (root active) shows every step.
Path D, a nested component from Bracket's menu: Parent is Bracket; the new one (Pin) is
        active and the timeline shows only its steps, with a note about the hidden ones;
        activating Bracket shows Bracket's and Pin's.
Path E, rename Pin to Axle in the browser: the timeline step follows.
Path F, Isolate Bracket hides the root body; the menu offers Exit Isolate; it shows again.
Path G, Create Components from Bodies on the root body: a component named after the body
        holding it; the active component stays.
Path H, Delete the new component: body gone; Undo brings both back; Redo removes them.
Path I, save and reopen: the components, their bodies and the volumes are back; the root
        is active after opening (Fusion).
Numbers: box 40 x 30 x 10 = 12000; box 20 x 20 x 5 = 2000.
"""

import os

import FreeCAD as App
from PySide import QtCore

from SciForgeTests.gui import arrow_input as ai
from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import component_steps as cs
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import timeline_input as t

V = App.Vector
state = {}
BOX = 12000.0
SMALL = 2000.0


def new_design():
    s.new_design("Components")()
    state["doc"] = App.ActiveDocument.Label


# -- Path A: New Component ----------------------------------------------------------------------
def a_ribbon():
    h.ribbon("New Component")


def a_dialog():
    panel = cs.new_component_panel()
    if not h.check("New Component dialog opens", panel is not None):
        return
    h.check("default name Component1", panel.name.text() == "Component1", panel.name.text())
    h.check("Activate on by default", panel.activate.isChecked())
    h.check(
        "Parent is the root",
        panel.parent_box.currentText().endswith("(root)"),
        panel.parent_box.currentText(),
    )
    cs.type_name("Bracket")


def a_ok():
    h.task_button("OK")


def a_made():
    part = cs.component("Bracket")
    h.check("Bracket exists", part is not None, [p.Label for p in cs.components()])
    h.check("Bracket is active", cs.active_label() == "Bracket", cs.active_label())
    h.check("no dialog left", not t.dialog_open())
    node = cs.node_of("Bracket")
    h.check("browser row Bracket, active ring", node is not None and node["active"], node)
    root = t.tree().topLevelItem(0).data(1, QtCore.Qt.UserRole)
    h.check("root ring not filled", not root["active"])
    h.check("timeline shows the component step", t.titles() == ["Bracket"], t.titles())
    h.shot("a-bracket")


# -- Path B: into the active component ------------------------------------------------------------
def b_sketch():
    h.fit()
    h.ribbon("Create Sketch")


def b_plane():
    pl.click_square("XY_Plane")  # where the square shows (was 12, -8, 0)


def b_draw():
    sk = h.in_sketch()
    h.check("sketch open", sk is not None)
    if sk is not None:
        h.draw_rectangle(sk, 0, 0, 40, 30)
        h.check("the sketch's body is in Bracket", cs.container_label(sk) == "Bracket")


def b_finish():
    h.ribbon("Finish Sketch")


def b_extrude():
    h.fit()
    h.press("e")


def b_distance():
    h.check("extrude dialog", ai.give_distance("10"))


def b_ok():
    h.task_button("OK")


def b_made():
    body = h.body()
    h.check("a body", body is not None)
    if body is None:
        return
    state["b1"] = body.Name
    h.check("body in Bracket", cs.container_label(body) == "Bracket", cs.container_label(body))
    h.check("named Body1 (numbered per component)", body.Label == "Body1", body.Label)
    h.check("volume 12000", cs.near(cs.volume(body), BOX), cs.volume(body))
    h.check(
        "browser: Bracket > Bodies > Body1",
        cs.children_of(["Bracket", "Bodies"]) == ["Body1"],
        cs.children_of(["Bracket", "Bodies"]),
    )
    h.check(
        "root has no Bodies folder",
        cs.top_labels() == ["Document Settings", "Named Views", "Bracket"],
        cs.top_labels(),
    )
    h.check(
        "timeline: Bracket, Sketch 1, Extrude 1",
        t.titles() == ["Bracket", "Sketch 1", "Extrude 1"],
        t.titles(),
    )
    h.shot("b-body-in-bracket")


# -- Path C: the root again ------------------------------------------------------------------------
def c_activate_root():
    cs.click_radio(state["doc"])


def c_root_active():
    h.check("root active", cs.active_label() is None, cs.active_label())
    root = t.tree().topLevelItem(0).data(1, QtCore.Qt.UserRole)
    h.check("root ring filled", root["active"])
    h.check("Bracket ring empty", not cs.node_of("Bracket")["active"])
    h.check("root shows every step", len(t.titles()) == 3, t.titles())


def c_sketch():
    h.fit()
    h.ribbon("Create Sketch")


def c_plane():
    pl.click_square("XY_Plane")  # where the square shows (was 12, -8, 0)


def c_draw():
    sk = h.in_sketch()
    h.check("sketch open", sk is not None)
    if sk is not None:
        h.check("the sketch's body is at the root", cs.container_label(sk) is None)
        h.draw_rectangle(sk, 60, 0, 80, 20)


def c_finish():
    h.ribbon("Finish Sketch")


def c_extrude():
    h.fit()
    h.press("e")


def c_distance():
    h.check("extrude dialog", ai.give_distance("5"))


def c_ok():
    h.task_button("OK")


def c_made():
    body = h.body()
    h.check("a root body", body is not None and cs.container_label(body) is None)
    if body is None:
        return
    state["b2"] = body.Name
    state["b2_label"] = body.Label
    h.check("volume 2000", cs.near(cs.volume(body), SMALL), cs.volume(body))
    h.check(
        "browser: root folders then Bracket",
        cs.top_labels()
        == ["Document Settings", "Named Views", "Origin", "Bodies", "Sketches", "Bracket"],
        cs.top_labels(),
    )
    h.check(
        "timeline (root): every step",
        t.titles() == ["Bracket", "Sketch 1", "Extrude 1", "Sketch 2", "Extrude 2"],
        t.titles(),
    )
    h.check("Bracket's body kept", cs.near(cs.volume(cs.body_labelled("Body1")), BOX))
    h.shot("c-root-body")


# -- Path D: nested --------------------------------------------------------------------------------
def d_menu():
    t.row_menu("Bracket", "New Component")


def d_dialog():
    panel = cs.new_component_panel()
    if not h.check("dialog from the menu", panel is not None):
        return
    h.check(
        "Parent is Bracket",
        panel.parent_box.currentText() == "Bracket",
        panel.parent_box.currentText(),
    )
    cs.type_name("Pin")


def d_ok():
    h.task_button("OK")


def d_made():
    pin = cs.component("Pin")
    h.check("Pin exists", pin is not None)
    if pin is None:
        return
    h.check("Pin inside Bracket", cs.container_label(pin) == "Bracket", cs.container_label(pin))
    h.check("Pin active", cs.active_label() == "Pin", cs.active_label())
    h.check("browser: Pin under Bracket", "Pin" in (cs.children_of(["Bracket"]) or []))
    h.check("timeline shows only Pin's steps", t.titles() == ["Pin"], t.titles())
    note = cs.hidden_note()
    h.check("a note counts the hidden steps", note is not None and note.startswith("5 "), note)
    h.shot("d-pin-active")


def d_activate_bracket():
    cs.click_radio("Bracket")


def d_bracket_steps():
    h.check("Bracket active", cs.active_label() == "Bracket", cs.active_label())
    h.check(
        "timeline: Bracket's and Pin's steps",
        t.titles() == ["Bracket", "Sketch 1", "Extrude 1", "Pin"],
        t.titles(),
    )
    body = h.body()
    h.check("Bracket's body is the active one again", body is not None and body.Label == "Body1")


def d_root_menu():
    """New Component from the design's row goes to the root, whatever is active."""
    t.row_menu(state["doc"], "New Component")


def d_root_dialog():
    panel = cs.new_component_panel()
    if not h.check("dialog from the design's row", panel is not None):
        return
    h.check(
        "Parent is the root (Bracket is active)",
        panel.parent_box.currentText().endswith("(root)"),
        panel.parent_box.currentText(),
    )
    # Bracket and Pin were renamed: no component is called Component<n>, so Component1.
    h.check("Component1 proposed", panel.name.text() == "Component1", panel.name.text())


def d_root_cancel():
    h.task_button("Cancel")


def d_root_nothing():
    h.check("Cancel made nothing", len(cs.components()) == 2, [p.Label for p in cs.components()])
    h.check("Bracket still active", cs.active_label() == "Bracket", cs.active_label())


# -- Path E: rename --------------------------------------------------------------------------------
def e_rename():
    cs.rename_row("Pin", "Axle")


def e_renamed():
    h.check("renamed to Axle", cs.component("Axle") is not None and cs.component("Pin") is None)
    h.check("timeline step follows", "Axle" in t.titles(), t.titles())


# -- Path F: isolate -------------------------------------------------------------------------------
def f_isolate():
    t.row_menu("Bracket", "Isolate")


def f_isolated():
    root_body = App.ActiveDocument.getObject(state["b2"])
    h.check("root body hidden", not t.shown(root_body))
    h.check("Bracket's body shown", t.shown(cs.body_labelled("Body1")))
    entries = [e for e, _ok in t.row_menu_entries("Bracket")]
    h.check("menu offers Exit Isolate", "Exit Isolate" in entries, entries)


def f_exit():
    t.row_menu("Bracket", "Exit Isolate")


def f_back():
    root_body = App.ActiveDocument.getObject(state["b2"])
    h.check("root body shown again", t.shown(root_body))


# -- Path G: Create Components from Bodies ---------------------------------------------------------
def g_menu():
    t.row_menu(state["b2_label"], "Create Components from Bodies")


def g_made():
    part = cs.component(state["b2_label"])
    body = App.ActiveDocument.getObject(state["b2"])
    h.check("component named after the body", part is not None, [p.Label for p in cs.components()])
    h.check("body inside it", part is not None and cs.container_label(body) == part.Label)
    h.check("active component unchanged", cs.active_label() == "Bracket", cs.active_label())
    h.check("volume kept", cs.near(cs.volume(body), SMALL))
    h.check(
        "browser: the component holds the body",
        cs.children_of([state["b2_label"], "Bodies"]) == [state["b2_label"]],
        cs.children_of([state["b2_label"], "Bodies"]),
    )
    h.shot("g-from-bodies")


# -- Path H: delete, undo, redo --------------------------------------------------------------------
def h_delete():
    t.row_menu(state["b2_label"], "Delete")


def h_deleted():
    h.check("component gone", cs.component(state["b2_label"]) is None)
    h.check("its body gone", App.ActiveDocument.getObject(state["b2"]) is None)
    h.check("Bracket's body kept", cs.near(cs.volume(cs.body_labelled("Body1")), BOX))
    t.no_popups("Delete")


def h_undo():
    t.undo()


def h_undone():
    body = App.ActiveDocument.getObject(state["b2"])
    h.check("Undo: component back", cs.component(state["b2_label"]) is not None)
    h.check("Undo: body back with its volume", body is not None and cs.near(cs.volume(body), SMALL))
    h.check(
        "body still inside the component",
        body is not None and cs.container_label(body) == state["b2_label"],
    )


def h_redo():
    t.redo()


def h_redone():
    h.check("Redo: component gone again", cs.component(state["b2_label"]) is None)


def h_undo_again():
    t.undo()


# -- Path I: save and reopen -----------------------------------------------------------------------
def i_save():
    path = os.path.join(h.OUT_DIR, "components_basic.FCStd")
    state["path"] = path
    App.ActiveDocument.saveAs(path)
    App.closeDocument(App.ActiveDocument.Name)


def i_reopen():
    App.openDocument(state["path"])
    h.fit()


def i_back():
    doc = App.ActiveDocument
    labels = sorted(p.Label for p in cs.components())
    h.check("components back", labels == sorted(["Bracket", "Axle", state["b2_label"]]), labels)
    axle = cs.component("Axle")
    h.check("Axle still inside Bracket", axle is not None and cs.container_label(axle) == "Bracket")
    body = doc.getObject(state["b2"])
    h.check(
        "root body in its component",
        body is not None and cs.container_label(body) == state["b2_label"],
    )
    h.check("volumes back", cs.near(sum(cs.volume(b) for b in cs.bodies()), BOX + SMALL))
    h.check("root active after opening", cs.active_label() is None, cs.active_label())
    h.check("browser lists Bracket", "Bracket" in cs.top_labels(), cs.top_labels())
    h.check(
        "timeline: every step",
        t.titles()
        == ["Bracket", "Sketch 1", "Extrude 1", "Sketch 2", "Extrude 2", "Axle", state["b2_label"]],
        t.titles(),
    )
    h.shot("i-reopened")


h.run(
    "components_basic",
    t.watched(
        [
            new_design,
            a_ribbon,
            a_dialog,
            a_ok,
            a_made,
            b_sketch,
            b_plane,
            b_draw,
            b_finish,
            b_extrude,
            b_distance,
            b_ok,
            b_made,
            c_activate_root,
            c_root_active,
            c_sketch,
            c_plane,
            c_draw,
            c_finish,
            c_extrude,
            c_distance,
            c_ok,
            c_made,
            d_menu,
            d_dialog,
            d_ok,
            d_made,
            d_activate_bracket,
            d_bracket_steps,
            d_root_menu,
            d_root_dialog,
            d_root_cancel,
            d_root_nothing,
            e_rename,
            e_renamed,
            f_isolate,
            f_isolated,
            f_exit,
            f_back,
            g_menu,
            g_made,
            h_delete,
            h_deleted,
            h_undo,
            h_undone,
            h_redo,
            h_redone,
            h_undo_again,
            i_save,
            i_reopen,
            i_back,
        ]
    ),
)
