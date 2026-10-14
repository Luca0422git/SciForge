# SPDX-License-Identifier: LGPL-2.1-or-later
"""Components and the history marker, and what an active component looks like, only real
input.

Setup: a root body (0..40 x 0..30 x 10); New Component "Lid" (Activate on); in it a sketch
and an extrude (0..40 x 40..70, 5 high).

  A  Lid active: the root body is drawn see-through (Fusion's Active Component Visibility),
     Lid itself is not. The ring of the design's row: nothing is see-through any more.
  B  Preferences > General > Design: Active component visibility off: activating Lid dims
     nothing; on again: the root body is dimmed again; then the root is activated.
  C  The marker dragged before the Lid step: Lid is hidden, its row is gone from the browser
     and its extrude is rolled back; the root body stays. The marker to the end: Lid back.
  D  With the marker before Lid, New Component "Late": its step goes in at the marker (left
     of Lid's), it is shown and in the browser; Undo removes it.
  E  Save, close, reopen with the marker before Lid: Lid is still hidden; to the end: back.
"""

import os
import tempfile

import FreeCAD as App
from PySide import QtCore

from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import component2_steps as c
from SciForgeTests.gui import component_steps as cs
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import insert_steps as i
from SciForgeTests.gui import misc_steps as m
from SciForgeTests.gui import timeline_input as t

V = App.Vector
state = {}


def look():
    from sciforge import component_look

    return component_look.ghosted(App.ActiveDocument)


def lid():
    return c.part("Lid")


def root_body():
    return App.ActiveDocument.getObject(state["root"])


def new_design():
    s.new_design("Components2Marker")()


def setup_root():
    found = cs.bodies()
    h.check("one root body", len(found) == 1, [x.Label for x in found])
    state["root"] = found[0].Name
    h.click_empty()
    h.ribbon("New Component")


def setup_name():
    cs.type_name("Lid")


def setup_ok():
    h.task_button("OK")


def setup_active():
    h.check("Lid made and active", cs.active_label() == "Lid", cs.active_label())


def setup_done():
    from sciforge import components

    inside = [b for b in cs.bodies() if components.container_of(b) is lid()]
    h.check("Lid has its body", len(inside) == 1, [b.Label for b in cs.bodies()])
    h.check("Lid 6000", c.close(c.volume(lid()), 6000), c.volume(lid()))


# -- A --------------------------------------------------------------------------------------------
def a_dimmed():
    c.browser_refresh()
    ghosts = look()
    h.check("the root body is see-through", state["root"] in ghosts, ghosts)
    h.check("Lid is not", lid().Name not in ghosts, ghosts)
    h.shot("A-lid-active")


def a_root_ring():
    cs.click_radio(App.ActiveDocument.Label)


def a_plain():
    c.browser_refresh()
    h.check("the root active", cs.active_label() is None, cs.active_label())
    h.check("nothing see-through", not look(), look())


# -- B --------------------------------------------------------------------------------------------
def b_prefs():
    i.ribbon_tab("UTILITIES")
    h.ribbon("Preferences")
    m.process()


def b_off():
    from sciforge import preferences_ui

    d = preferences_ui.PreferencesDialog.last
    if not h.check("Preferences open", d is not None and d.isVisible()):
        return
    _page(d, "design")
    box = d.widgets.get("active_component_visibility")
    if h.check("the option is there", box is not None, sorted(d.widgets)):
        h.check("on by default", box.isChecked())
        m.set_check(box, False)
    _press(d, "SciForgePreferencesOK")


def _page(d, pid):
    from SciForgeTests.gui import widget_input as w

    for item in d.pages.findItems("*", QtCore.Qt.MatchWildcard | QtCore.Qt.MatchRecursive):
        if item.data(0, QtCore.Qt.UserRole) == pid:
            d.pages.scrollToItem(item)
            w.click(d.pages.viewport(), d.pages.visualItemRect(item).center())
            break


def _press(d, name):
    from SciForgeTests.gui import widget_input as w

    button = m.find_child(d, name)
    if h.check("button %s" % name, button is not None):
        w.click(button)
        m.process()


def b_activate():
    i.ribbon_tab("SOLID")
    cs.click_radio("Lid")


def b_not_dimmed():
    c.browser_refresh()
    h.check("Lid active", cs.active_label() == "Lid", cs.active_label())
    h.check("the option off: nothing see-through", not look(), look())


def b_on():
    from sciforge import preferences_ui

    i.ribbon_tab("UTILITIES")
    h.ribbon("Preferences")
    m.process()
    d = preferences_ui.PreferencesDialog.last
    if not h.check("Preferences open", d is not None and d.isVisible()):
        return
    _page(d, "design")
    m.set_check(d.widgets.get("active_component_visibility"), True)
    _press(d, "SciForgePreferencesOK")


def b_dimmed_again():
    i.ribbon_tab("SOLID")
    c.browser_refresh()
    h.check("on again: the root body see-through", state["root"] in look(), look())
    cs.click_radio(App.ActiveDocument.Label)


# -- C --------------------------------------------------------------------------------------------
def c_roll():
    titles = t.titles()
    h.check("the timeline shows Lid", "Lid" in titles, titles)
    t.drag_marker(before_title="Lid")


def c_rolled():
    h.check("Lid hidden", not t.shown(lid()))
    labels = c.browser_labels()
    h.check("Lid gone from the browser", "Lid" not in labels, labels)
    h.check("the root body stays", t.shown(root_body()))
    states = t.states()
    h.check(
        "Lid's extrude rolled back",
        states.get("Extrude 2", ("",))[0] == "rolled_back",
        states,
    )
    h.shot("C-rolled")


def c_end():
    t.drag_marker(to_end=True)


def c_back():
    h.check("Lid shown again", t.shown(lid()))
    labels = c.browser_labels()
    h.check("Lid in the browser again", "Lid" in labels, labels)
    h.check("Lid 6000", c.close(c.volume(lid()), 6000), c.volume(lid()))


# -- D --------------------------------------------------------------------------------------------
def d_roll():
    t.drag_marker(before_title="Lid")


def d_new():
    h.click_empty()
    h.ribbon("New Component")


def d_name():
    cs.type_name("Late")
    p = cs.new_component_panel()
    if p is not None:
        cs.toggle(p.activate)  # Activate off: the root stays active


def d_ok():
    h.task_button("OK")


def d_placed():
    late = c.part("Late")
    if not h.check("Late made", late is not None, c.labels()):
        return
    titles = t.titles()
    h.check(
        "its step at the marker, before Lid's",
        "Late" in titles and titles.index("Late") < titles.index("Lid"),
        titles,
    )
    h.check("Late shown", t.shown(late))
    h.check("Late in the browser", "Late" in c.browser_labels(), c.browser_labels())
    h.check("Lid still hidden", not t.shown(lid()))


def d_undo():
    s.undo()


def d_undone():
    h.check("Undo: Late gone", c.part("Late") is None, c.labels())


# -- E --------------------------------------------------------------------------------------------
def e_save_close():
    state["path"] = os.path.join(tempfile.mkdtemp(), "components2_marker.FCStd")
    App.ActiveDocument.saveAs(state["path"])
    App.closeDocument(App.ActiveDocument.Name)


def e_open():
    App.openDocument(state["path"])
    h.fit()


def e_reopened():
    h.check("Lid still hidden", not t.shown(lid()))
    h.check("still not in the browser", "Lid" not in c.browser_labels(), c.browser_labels())


def e_end():
    t.drag_marker(to_end=True)


def e_back():
    h.check("Lid back", t.shown(lid()))
    h.check("Lid 6000", c.close(c.volume(lid()), 6000), c.volume(lid()))


h.run(
    "components2_marker",
    t.watched(
        [new_design]
        + s.box_steps("root", (0, 0, 40, 30), 10, V(12, -8, 0))
        + [setup_root, setup_name, setup_ok, setup_active]
        + s.box_steps("lid", (0, 40, 40, 70), 5, V(12, -8, 0))
        + [
            setup_done,
            a_dimmed,
            a_root_ring,
            a_plain,
            b_prefs,
            b_off,
            b_activate,
            b_not_dimmed,
            b_on,
            b_dimmed_again,
            c_roll,
            c_rolled,
            c_end,
            c_back,
            d_roll,
            d_new,
            d_name,
            d_ok,
            d_placed,
            d_undo,
            d_undone,
            e_save_close,
            e_open,
            e_reopened,
            e_end,
            e_back,
        ]
    ),
)
