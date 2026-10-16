# SPDX-License-Identifier: LGPL-2.1-or-later
"""Moving bodies between components (real input).

Path A, two root bodies; New Component with Activate off: Comp exists, the root stays
        active, the first body still gets new work.
Path B, drag the first body's browser row onto Comp: the body is inside Comp (its volume
        kept); Undo puts it back at the root; Redo moves it again.
Path C, Move to Component from the second body's menu: into Comp; then back to the root
        with the same menu.
Path D, New Component with both bodies picked first: From Bodies is on and lists 2 bodies;
        OK makes one component per body, named after the bodies.
Path E, Isolate a body inside a component: the other component is hidden, its own component
        stays; Exit Isolate shows all.
Path F, the Delete key on a component row deletes it with its body; Undo brings it back.
Numbers: body1 40 x 30 x 10 = 12000; body2 40 x 30 x 10 = 12000.
"""

import FreeCAD as App
from PySide import QtCore

from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import component_steps as cs
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import timeline_input as t
from SciForgeTests.gui import widget_input as w

V = App.Vector
state = {}
BOX = 12000.0


def new_design():
    s.new_design("ComponentsMove")()
    state["doc"] = App.ActiveDocument.Label


def bodies_made():
    bodies = cs.bodies()
    h.check("two root bodies", len(bodies) == 2, [b.Label for b in bodies])
    state["b1"], state["b2"] = bodies[0].Name, bodies[1].Name
    state["l1"], state["l2"] = bodies[0].Label, bodies[1].Label


# -- Path A: a component without activating it ------------------------------------------------
def a_ribbon():
    h.click_empty()
    h.ribbon("New Component")


def a_dialog():
    panel = cs.new_component_panel()
    if not h.check("dialog open", panel is not None):
        return
    h.check("From Bodies off (nothing picked)", not panel.from_bodies.isChecked())
    cs.type_name("Comp")
    cs.toggle(panel.activate)
    h.check("Activate off", not panel.activate.isChecked())


def a_ok():
    h.task_button("OK")


def a_made():
    h.check("Comp exists", cs.component("Comp") is not None)
    h.check("root still active", cs.active_label() is None, cs.active_label())
    h.check(
        "Comp has no Bodies folder yet",
        cs.children_of(["Comp"]) == ["Origin"],
        cs.children_of(["Comp"]),
    )
    body = h.body()
    h.check(
        "a root body is still the active body",
        body is not None and cs.container_label(body) is None,
    )


# -- Path B: drag a body onto the component ------------------------------------------------------
def b_drag():
    cs.drag_row(state["l1"], "Comp")


def b_moved():
    body = App.ActiveDocument.getObject(state["b1"])
    h.check("body moved into Comp", cs.container_label(body) == "Comp", cs.container_label(body))
    h.check("volume kept", cs.near(cs.volume(body), BOX), cs.volume(body))
    h.check(
        "browser: Comp > Bodies holds it",
        cs.children_of(["Comp", "Bodies"]) == [state["l1"]],
        cs.children_of(["Comp", "Bodies"]),
    )
    h.check(
        "root Bodies has the other",
        cs.children_of(["Bodies"]) == [state["l2"]],
        cs.children_of(["Bodies"]),
    )
    h.check("root still active", cs.active_label() is None, cs.active_label())
    t.no_popups("drag")
    h.shot("b-dragged")


def b_undo():
    t.undo()


def b_undone():
    body = App.ActiveDocument.getObject(state["b1"])
    h.check(
        "Undo: body back at the root", cs.container_label(body) is None, cs.container_label(body)
    )


def b_redo():
    t.redo()


def b_redone():
    body = App.ActiveDocument.getObject(state["b1"])
    h.check("Redo: in Comp again", cs.container_label(body) == "Comp", cs.container_label(body))


# -- Path C: the menu ------------------------------------------------------------------------------
def c_menu_entries():
    entries = [e for e, _ok in t.row_menu_entries(state["l2"])]
    h.check("body menu has Move to Component", "Move to Component" in entries, entries)
    h.check(
        "body menu has Create Components from Bodies", "Create Components from Bodies" in entries
    )


def c_move():
    tree, pos = t.row_point(state["l2"])
    if pos is None:
        return
    state["ok"] = _submenu_pick(tree.viewport(), pos, "Move to Component", "Comp")


def _submenu_pick(widget, pos, submenu_text, entry_text):
    """Right-click, open a submenu and click one of its entries, like a person."""
    from PySide import QtWidgets
    from PySide6 import QtTest

    result = {"ok": False}

    def pick():
        menu = QtWidgets.QApplication.activePopupWidget()
        if not isinstance(menu, QtWidgets.QMenu):
            if result.get("tries", 0) < 20:
                result["tries"] = result.get("tries", 0) + 1
                QtCore.QTimer.singleShot(50, pick)
            return
        action = None
        for a in menu.actions():
            if a.text().replace("&", "").strip() == submenu_text:
                action = a
        if action is None or action.menu() is None:
            QtTest.QTest.keyClick(menu, QtCore.Qt.Key_Escape)
            return
        rect = menu.actionGeometry(action)
        for i in range(6):
            QtTest.QTest.mouseMove(menu, QtCore.QPoint(rect.left() + 10 + 8 * i, rect.center().y()))
        # A click on the entry opens its submenu (Qt does, as for a person's click).
        QtTest.QTest.mouseClick(menu, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, rect.center())
        QtCore.QTimer.singleShot(150, lambda: pick_entry(menu, action.menu()))

    def pick_entry(menu, sub):
        if sub is None or not sub.isVisible():
            result["detail"] = "submenu not shown"
            QtTest.QTest.keyClick(menu, QtCore.Qt.Key_Escape)
            return
        target = None
        for a in sub.actions():
            if a.text().replace("&", "").strip() == entry_text:
                target = a
        if target is None:
            result["detail"] = [a.text() for a in sub.actions()]
            QtTest.QTest.keyClick(sub, QtCore.Qt.Key_Escape)
            QtTest.QTest.keyClick(menu, QtCore.Qt.Key_Escape)
            return
        srect = sub.actionGeometry(target)
        for i in range(6):
            QtTest.QTest.mouseMove(
                sub, QtCore.QPoint(srect.left() + 10 + 6 * i, srect.center().y())
            )
        QtTest.QTest.mouseClick(sub, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, srect.center())
        result["ok"] = True

    QtCore.QTimer.singleShot(50, pick)
    w._open_menu(widget, pos, result)
    QtWidgets.QApplication.processEvents()
    return result["ok"]


def c_moved():
    body = App.ActiveDocument.getObject(state["b2"])
    h.check("menu entry clicked", state.get("ok"))
    h.check("second body in Comp", cs.container_label(body) == "Comp", cs.container_label(body))
    h.check(
        "Comp > Bodies holds both",
        sorted(cs.children_of(["Comp", "Bodies"]) or []) == sorted([state["l1"], state["l2"]]),
        cs.children_of(["Comp", "Bodies"]),
    )
    h.check("root has no Bodies folder", "Bodies" not in cs.top_labels(), cs.top_labels())


def c_move_back():
    tree, pos = t.row_point(state["l2"])
    if pos is None:
        return
    state["ok2"] = _submenu_pick(
        tree.viewport(), pos, "Move to Component", state["doc"] + " (root)"
    )


def c_back():
    body = App.ActiveDocument.getObject(state["b2"])
    h.check("root entry clicked", state.get("ok2"))
    h.check(
        "second body back at the root", cs.container_label(body) is None, cs.container_label(body)
    )
    h.check(
        "root Bodies folder back",
        cs.children_of(["Bodies"]) == [state["l2"]],
        cs.children_of(["Bodies"]),
    )


# -- Path D: From Bodies ---------------------------------------------------------------------------
def d_pick_bodies():
    t.click_row(state["l1"])
    t.click_row(state["l2"], QtCore.Qt.ControlModifier)
    h.check("two bodies selected", len(t.selected()) == 2, t.selected())


def d_ribbon():
    h.ribbon("New Component")


def d_dialog():
    panel = cs.new_component_panel()
    if not h.check("dialog open", panel is not None):
        return
    h.check("From Bodies on", panel.from_bodies.isChecked())
    h.check(
        "2 bodies listed",
        panel.bodies_label.text().startswith("2 bodies"),
        panel.bodies_label.text(),
    )


def d_ok():
    h.task_button("OK")


def d_made():
    labels = [p.Label for p in cs.components()]
    h.check(
        "one component per body, named after it",
        state["l1"] in labels and state["l2"] in labels,
        labels,
    )
    b1 = App.ActiveDocument.getObject(state["b1"])
    b2 = App.ActiveDocument.getObject(state["b2"])
    h.check(
        "first body in its component", cs.container_label(b1) == state["l1"], cs.container_label(b1)
    )
    h.check(
        "second body in its component",
        cs.container_label(b2) == state["l2"],
        cs.container_label(b2),
    )
    h.check("Comp is empty again", cs.children_of(["Comp"]) == ["Origin"], cs.children_of(["Comp"]))
    h.check(
        "the last new component is active (Activate was on)",
        cs.active_label() == state["l2"],
        cs.active_label(),
    )
    h.shot("d-from-bodies")


# -- Path E: isolate a body inside a component -----------------------------------------------------
def e_isolate():
    t.row_menu(state["l1"], "Isolate")


def e_isolated():
    b2 = App.ActiveDocument.getObject(state["b2"])
    comp2 = cs.component(state["l2"])
    comp1 = cs.component(state["l1"])
    h.check("other component hidden", comp2 is not None and not t.shown(comp2))
    h.check("other body hidden too", not t.shown(b2))
    h.check("own component shown", comp1 is not None and t.shown(comp1))


def e_exit():
    t.row_menu(state["l1"], "Exit Isolate")


def e_shown():
    b2 = App.ActiveDocument.getObject(state["b2"])
    comp2 = cs.component(state["l2"])
    h.check("all shown again", t.shown(comp2) and t.shown(b2))


# -- Path F: the Delete key ------------------------------------------------------------------------
def f_select():
    t.click_row(state["l2"])


def f_delete():
    tree = t.tree()
    w.key(tree, QtCore.Qt.Key_Delete)


def f_deleted():
    h.check(
        "component deleted", cs.component(state["l2"]) is None, [p.Label for p in cs.components()]
    )
    h.check("its body deleted", App.ActiveDocument.getObject(state["b2"]) is None)
    h.check(
        "the other body kept", cs.near(cs.volume(App.ActiveDocument.getObject(state["b1"])), BOX)
    )
    h.check(
        "root active (the active component was deleted)",
        cs.active_label() in (None, state["l1"]),
        cs.active_label(),
    )
    t.no_popups("Delete key")


def f_undo():
    t.undo()


def f_undone():
    b2 = App.ActiveDocument.getObject(state["b2"])
    h.check(
        "Undo: component and body back", cs.component(state["l2"]) is not None and b2 is not None
    )
    h.check("Undo: volume back", b2 is not None and cs.near(cs.volume(b2), BOX))
    h.shot("f-undone")


h.run(
    "components_move",
    t.watched(
        [new_design]
        + s.box_steps("body1", (0, 0, 40, 30), 10, V(6, -6, 0))
        + s.box_steps("body2", (60, 0, 100, 30), 10, V(6, -6, 0), new_body=True)
        + [
            bodies_made,
            a_ribbon,
            a_dialog,
            a_ok,
            a_made,
            b_drag,
            b_moved,
            b_undo,
            b_undone,
            b_redo,
            b_redone,
            c_menu_entries,
            c_move,
            c_moved,
            c_move_back,
            c_back,
            d_pick_bodies,
            d_ribbon,
            d_dialog,
            d_ok,
            d_made,
            e_isolate,
            e_isolated,
            e_exit,
            e_shown,
            f_select,
            f_delete,
            f_deleted,
            f_undo,
            f_undone,
        ]
    ),
)
