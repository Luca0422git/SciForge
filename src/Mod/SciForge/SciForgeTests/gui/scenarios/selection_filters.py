# SPDX-License-Identifier: LGPL-2.1-or-later
"""Selection filters, priorities and Select Through from the SELECT ribbon menu, like
Fusion (parity/selection.md). Only real input, on a 40 x 30 x 10 box.

  A  the SELECT menu: Select, Window / Freeform / Paint Selection (Window ticked), the
     Selection Filters and Selection Priority submenus, Select Other, Select All.
  B  Selection Filters > Body Faces unticked: a click on the top face selects nothing and a
     note says faces are filtered out; the face does not light up under the mouse; an
     edge still selects; the setting is remembered in the preferences. Ticked again: the
     face selects.
  C  Selection Priority > Select Body Priority: a click on a face selects the whole body
     (and the body lights up under the mouse); a window around the box selects the body;
     Ctrl + click on it drops it; the same entry again clears the priority (every filter
     on; the Ctrl + click left nothing selected).
  D  Selection Filters > Select Through ticks on and off again.
  E  SciForge off (Part Design workbench): with Body Edges filtered out, an edge still
     selects there (FreeCAD's own selection); back in SciForge the filter is back (the
     edge does not select); then edges on again.
  F  inside a command: Fillet open with faces filtered out: a click on the top face is not
     picked, an edge is; faces on again while the dialog is open: a face is picked; Cancel.
     After the dialog, the filter gate is back (faces off: a click picks nothing).
"""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import selection_input as si

V = App.Vector
PARAMS = "User parameter:BaseApp/Preferences/Mod/SciForge"
TOP = V(20, 15, 10)
FRONT_TOP_EDGE = V(20, 0, 10)
st = {}


def names():
    if "names" not in st:
        st["names"] = si.name_map()
    return st["names"]


def remember_names():
    """The box's element names, read from the plain box (a dialog's preview renumbers)."""
    st["names"] = si.name_map()


def sel_ui():
    return si.selection_ui()


def corners():
    box = h.body().Shape.BoundBox
    return [
        V(x, y, z)
        for x in (box.XMin, box.XMax)
        for y in (box.YMin, box.YMax)
        for z in (box.ZMin, box.ZMax)
    ]


# -- A -------------------------------------------------------------------------------------------
def a_read_menu():
    h.fit()
    result = si.choose_select(None)
    texts = [t for t, _e, _c in result["entries"]]
    st["menu"] = result
    for want in (
        "Select",
        "Window Selection",
        "Freeform Selection",
        "Paint Selection",
        "Selection Filters",
        "Selection Priority",
        "Select Other",
        "Select All",
    ):
        h.check("A the SELECT menu has %r" % want, want in texts, texts)
    checked = [t for t, _e, c in result["entries"] if c]
    h.check("A Window Selection is the ticked mode", checked == ["Window Selection"], checked)


# -- B -------------------------------------------------------------------------------------------
def b_faces_off():
    result = si.choose_select(["Selection Filters", "Body Faces"])
    h.check("B Body Faces could be clicked in the Selection Filters submenu", result["ok"], result)
    subs = [t for t, _e, _c in result["sub"]]
    for want in (
        "Select Through",
        "Bodies",
        "Body Faces",
        "Body Edges",
        "Body Vertices",
        "Sketch Curves",
        "Sketch Points",
        "Work Geometry",
    ):
        h.check("B the filters submenu has %r" % want, want in subs, subs)
    ticked = {t: c for t, _e, c in result["sub"]}
    h.check(
        "B every filter was ticked before (and Select Through not)",
        ticked.get("Body Faces") is True
        and ticked.get("Bodies") is True
        and ticked.get("Select Through") is False,
        ticked,
    )


def b_faces_off_check():
    h.check("B Body Faces is off", not sel_ui().faces_on())
    h.check(
        "B ... remembered in the preferences",
        App.ParamGet(PARAMS).GetString("SelectionFiltersOff", "") == "faces",
        App.ParamGet(PARAMS).GetString("SelectionFiltersOff", ""),
    )
    st["told_before"] = sel_ui()._state["told"]
    h.click(TOP)


def b_face_click_check():
    h.check(
        "B a click on the top face selects nothing", not Gui.Selection.hasSelection(), si.selected()
    )
    h.check(
        "B ... and a note said faces are filtered out",
        sel_ui()._state["told"] > st.get("told_before", 0),
    )
    h.move(h.screen_point(TOP))
    h.move(h.screen_point(V(21, 16, 10)))
    h.check(
        "B the face does not light up under the mouse", si.preselected() is None, si.preselected()
    )
    h.click_edge(FRONT_TOP_EDGE)


def b_edge_click_check():
    h.check(
        "B an edge still selects",
        si.selected_elements() == {names()["edge_front_top"]},
        si.selected(),
    )
    h.click_empty()
    result = si.choose_select(["Selection Filters", "Body Faces"])
    h.check("B Body Faces ticked again", result["ok"] and sel_ui().faces_on())
    h.click(TOP)


def b_face_again_check():
    h.check("B the face selects again", si.selected_elements() == {names()["top"]}, si.selected())
    h.click_empty()


# -- C -------------------------------------------------------------------------------------------
def c_body_priority():
    result = si.choose_select(["Selection Priority", "Select Body Priority"])
    h.check("C Select Body Priority clicked", result["ok"], result)
    subs = [t for t, _e, _c in result["sub"]]
    h.check(
        "C the priority submenu has Body / Face / Edge / Component",
        subs[:4]
        == [
            "Select Body Priority",
            "Select Face Priority",
            "Select Edge Priority",
            "Select Component Priority",
        ],
        subs,
    )
    h.check("C the priority is body", sel_ui().priority() == "body", sel_ui().priority())
    h.check(
        "C ... only Bodies stays on",
        sel_ui().bodies_on() and not sel_ui().faces_on() and not sel_ui().edges_on(),
    )
    h.move(h.screen_point(V(18, 14, 10)))
    h.move(h.screen_point(TOP))


def c_hover_check():
    h.check(
        "C the whole body lights up under the mouse",
        si.preselected() == ("Body", ""),
        si.preselected(),
    )
    h.click(TOP)


def c_click_check():
    h.check(
        "C a click on a face selects the whole body",
        si.selected_objects() == ["Body"] and not si.selected_elements(),
        si.selected(),
    )
    h.click_empty()
    si.box_around(corners(), margin=25)


def c_box_check():
    h.check(
        "C a window around the box selects the body",
        si.selected_objects() == ["Body"] and not si.selected_elements(),
        si.selected(),
    )
    h.click(TOP, modifiers=QtCore.Qt.ControlModifier)


def c_ctrl_check():
    h.check(
        "C Ctrl + click on the selected body drops it",
        not Gui.Selection.hasSelection(),
        si.selected(),
    )
    result = si.choose_select(["Selection Priority", "Select Body Priority"])
    h.check("C the active priority clicked again", result["ok"], result)


def c_cleared_check():
    h.check("C ... clears the priority", sel_ui().priority() is None)
    h.check(
        "C ... every filter on again", not sel_ui().filters().is_restrictive(), sel_ui().filters()
    )
    h.click(TOP)


def c_face_again():
    h.check("C a face selects again", si.selected_elements() == {names()["top"]}, si.selected())
    h.click_empty()


# -- D -------------------------------------------------------------------------------------------
def d_through_on():
    result = si.choose_select(["Selection Filters", "Select Through"])
    h.check("D Select Through ticked", result["ok"] and sel_ui().select_through())


def d_through_off():
    result = si.choose_select(["Selection Filters", "Select Through"])
    h.check("D Select Through unticked", result["ok"] and not sel_ui().select_through())
    h.check("D ... remembered", App.ParamGet(PARAMS).GetBool("SelectThrough", True) is False)


# -- E -------------------------------------------------------------------------------------------
def e_edges_off_then_sciforge_off():
    Gui.runCommand("SciForge_SelectFilterEdges")
    h.check("E Body Edges off", not sel_ui().edges_on())
    Gui.activateWorkbench("PartDesignWorkbench")


def e_click_edge_in_freecad():
    h.fit()
    h.click_edge(FRONT_TOP_EDGE)


def e_freecad_check():
    h.check(
        "E with SciForge off the edge selects (no filter gate)",
        names()["edge_front_top"] in si.selected_elements(),
        si.selected(),
    )
    Gui.Selection.clearSelection()
    Gui.activateWorkbench("SciForgeWorkbench")


def e_back_in_sciforge():
    h.fit()
    h.check("E the filter survived the switch", not sel_ui().edges_on())
    h.click_edge(FRONT_TOP_EDGE)


def e_sciforge_check():
    h.check(
        "E back in SciForge the edge does not select", not si.selected_elements(), si.selected()
    )
    Gui.runCommand("SciForge_SelectFilterEdges")
    h.check("E Body Edges on again", sel_ui().edges_on())
    h.click_empty()


# -- F -------------------------------------------------------------------------------------------
def f_fillet_with_faces_off():
    Gui.runCommand("SciForge_SelectFilterFaces")
    h.press("f")


def f_click_face():
    panel = b.blend_panel()
    h.check("F the Fillet dialog is open", panel is not None)
    h.click(TOP)


def f_face_not_picked():
    panel = b.blend_panel()
    refs = list(getattr(panel, "refs", []) or []) if panel else None
    h.check("F with faces filtered out the dialog did not pick the face", refs == [], refs)
    h.click_edge(FRONT_TOP_EDGE)


def f_edge_picked():
    panel = b.blend_panel()
    refs = list(getattr(panel, "refs", []) or []) if panel else None
    h.check(
        "F an edge is picked by the dialog",
        refs is not None and names()["edge_front_top"] in refs,
        refs,
    )
    Gui.runCommand("SciForge_SelectFilterFaces")
    h.check("F faces on again while the dialog is open", sel_ui().faces_on())
    h.click(V(20, 15, 10))


def f_face_picked():
    panel = b.blend_panel()
    refs = list(getattr(panel, "refs", []) or []) if panel else None
    h.check("F now the face is picked too", refs is not None and names()["top"] in refs, refs)
    h.task_button("Cancel")


def f_after_dialog():
    h.check("F the dialog is closed", b.blend_panel() is None)
    Gui.runCommand("SciForge_SelectFilterFaces")
    h.click(TOP)


def f_gate_back():
    h.check(
        "F after the dialog the filter gate is back (faces off: no pick)",
        not Gui.Selection.hasSelection(),
        si.selected(),
    )
    Gui.runCommand("SciForge_SelectFilterFaces")
    h.check(
        "F every filter on at the end", not sel_ui().filters().is_restrictive(), sel_ui().filters()
    )


steps = b.box_steps("SelFilters") + [
    remember_names,
    a_read_menu,
    b_faces_off,
    b_faces_off_check,
    b_face_click_check,
    b_edge_click_check,
    b_face_again_check,
    c_body_priority,
    c_hover_check,
    c_click_check,
    c_box_check,
    c_ctrl_check,
    c_cleared_check,
    c_face_again,
    d_through_on,
    d_through_off,
    e_edges_off_then_sciforge_off,
    e_click_edge_in_freecad,
    e_freecad_check,
    e_back_in_sciforge,
    e_sciforge_check,
    f_fillet_with_faces_off,
    f_click_face,
    f_face_not_picked,
    f_edge_picked,
    f_face_picked,
    f_after_dialog,
    f_gate_back,
]

h.run("selection_filters", steps)
