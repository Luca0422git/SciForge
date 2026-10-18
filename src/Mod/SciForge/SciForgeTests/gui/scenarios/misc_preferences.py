# SPDX-License-Identifier: LGPL-2.1-or-later
"""Preferences (UTILITIES > Preferences), only real input (docs/sciforge/parity/misc.md).

P1 UTILITIES > Preferences: Fusion's window: the pages on the left (General with Design and API
   under it, Material, Graphics, Unit and Value Display, Default Units with Design, Network),
   General shown first (Automatic version on close on); options SciForge cannot honour are
   greyed with the reason (the Inventor / Tinkercad / Alias / PowerMill mouse presets; Y up).
P2 Default Units > Design: Inch, OK. Ctrl+N: the new design is in inches (its browser says
   so); a design made before keeps millimetres.
P3 General: Reverse zoom direction, Apply: the mouse wheel rolled away from you now zooms out
   (it zoomed in before); off again with OK: it zooms in.
P4 Pan, Zoom, Orbit Shortcuts = SolidWorks, OK: a middle-button drag orbits (the view turns);
   back to Fusion: a middle-button drag pans (the view does not turn).
P5 General > Design: Capture design history off, OK: a new design starts without history (its
   browser offers Capture Design History); a design opened from a file keeps its own.
P6 Material: Default physical material Aluminium: a body without a material counts as
   Aluminium (its mass); General precision 4: the window says a restart is needed.
P7 Cancel throws changes away (recovery interval 7, Cancel: still 5); Restore Defaults then
   Cancel keeps everything; Restore Defaults then OK: millimetres, Fusion's mouse, zoom as
   before, history on, Steel.
P8 SciForge switched off (another workbench): FreeCAD's own zoom direction is back; on again:
   SciForge's.
"""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import dialog_input as di
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import insert_steps as i
from SciForgeTests.gui import misc_steps as m
from SciForgeTests.gui import timeline_input as t
from SciForgeTests.gui import widget_input as w

V = App.Vector
VIEW = "User parameter:BaseApp/Preferences/View"
UNITS = "User parameter:BaseApp/Preferences/Units"
PREFS = "User parameter:BaseApp/Preferences/Mod/SciForge/Preferences"
FILES = "User parameter:BaseApp/Preferences/Mod/SciForge/Files"
MIDDLE = QtCore.Qt.MiddleButton
s = {}


def dialog():
    from sciforge import preferences_ui

    d = preferences_ui.PreferencesDialog.last
    try:
        return d if d is not None and d.isVisible() else None
    except RuntimeError:
        return None


def widget(key):
    d = dialog()
    return d.widgets.get(key) if d is not None else None


def open_prefs():
    i.ribbon_tab("UTILITIES")
    h.ribbon("Preferences")
    m.process()


def page(pid):
    """Click a page in the list on the left."""
    d = dialog()
    if d is None:
        return False
    for item in d.pages.findItems("*", QtCore.Qt.MatchWildcard | QtCore.Qt.MatchRecursive):
        if item.data(0, QtCore.Qt.UserRole) == pid:
            d.pages.scrollToItem(item)
            rect = d.pages.visualItemRect(item)
            w.click(d.pages.viewport(), rect.center())
            break
    return h.check("page %s shown" % pid, d.current_page() == pid, d.current_page())


def button(name):
    d = dialog()
    return m.find_child(d, name) if d is not None else None


def press(name):
    b = button(name)
    if h.check("button %s" % name, b is not None):
        w.click(b)
        m.process()


def camera():
    return h.view().getCameraNode()


def cam_height():
    cam = camera()
    try:
        return cam.height.getValue()
    except AttributeError:
        return cam.focalDistance.getValue()


def viewer():
    """The 3D viewer around the drawing area: a real wheel event the drawing area does not take
    goes on to it (Qt hands it to the parent); a sent one has to be sent there."""
    widget = h.gl_widget()
    while widget is not None and widget.metaObject().className() != "Gui::View3DInventorViewer":
        widget = widget.parentWidget()
    return widget or h.gl_widget()


def wheel(away=True):
    """One notch of the mouse wheel over the middle of the 3D view (away from you = +120)."""
    gl = h.gl_widget()
    target = viewer()
    middle = QtCore.QPoint(gl.width() // 2, gl.height() // 2)
    QtTest.QTest.mouseMove(gl, middle)
    pos = QtCore.QPointF(target.mapFrom(gl, middle))
    event = QtGui.QWheelEvent(
        pos,
        QtCore.QPointF(gl.mapToGlobal(middle)),
        QtCore.QPoint(0, 0),
        QtCore.QPoint(0, 120 if away else -120),
        QtCore.Qt.NoButton,
        QtCore.Qt.NoModifier,
        QtCore.Qt.NoScrollPhase,
        False,
    )
    before = cam_height()
    QtWidgets.QApplication.sendEvent(target, event)
    m.process()
    return before, cam_height()


def middle_drag():
    """A middle-button drag across the view: (turned degrees, moved mm)."""
    gl = h.gl_widget()
    before_rot = h.view().getCameraOrientation()
    before_pos = V(*camera().position.getValue().getValue())
    cx, cy = gl.width() // 2, gl.height() // 2
    h.drag(QtCore.QPoint(cx - 120, cy), QtCore.QPoint(cx + 40, cy - 30), button=MIDDLE)
    QtTest.QTest.qWait(100)
    m.process()
    turned = abs(before_rot.inverted().multiply(h.view().getCameraOrientation()).Angle)
    moved = (V(*camera().position.getValue().getValue()) - before_pos).Length
    return turned, moved


def units_of(doc):
    from sciforge import browser_ui

    return browser_ui.units(doc)


def setup():
    Gui.activateWorkbench("SciForgeWorkbench")
    from sciforge import commands, extrude, sketch_ui

    App.newDocument("Prefs")
    body = commands.ensure_body()
    planes = sketch_ui.origin_planes(body)
    sk = sketch_ui.create_sketch(body, (planes["XY_Plane"], ""))
    h.draw_rectangle(sk, 0, 0, 40, 30)
    extrude.make(body, sk, {"distance": 10.0})
    App.ActiveDocument.recompute()
    s["first"] = App.ActiveDocument.Name
    h.view().setCameraType("Orthographic")
    h.fit()
    h.check("the design is in millimetres", units_of(App.ActiveDocument) == "mm")
    h.check(
        "FreeCAD's zoom direction as SciForge starts",
        App.ParamGet(VIEW).GetBool("InvertZoom", True),
    )


# -- P1 ----------------------------------------------------------------------------------------
def p1_open():
    open_prefs()


def p1_window():
    from sciforge import prefs_core

    d = dialog()
    h.check("P1 the Preferences window", d is not None and d.windowTitle() == "Preferences")
    if d is None:
        return
    titles = []
    for item in d.pages.findItems("*", QtCore.Qt.MatchWildcard | QtCore.Qt.MatchRecursive):
        parent = item.parent()
        titles.append((parent.text(0) + " > " if parent else "") + item.text(0))
    h.check(
        "P1 Fusion's pages",
        titles
        == [
            "General",
            "General > Design",
            "General > API",
            "Material",
            "Graphics",
            "Unit and Value Display",
            "Default Units",
            "Default Units > Design",
            "Network",
            "Keyboard Shortcuts",  # SciForge's own: every command's key in one list
            "3D Print",  # SciForge's own: where 3D Print sends the design
        ],
        titles,
    )
    h.check("P1 General first", d.current_page() == "general", d.current_page())
    closing = widget("version_on_close")
    h.check(
        "P1 Automatic version on close can be set, on by default (Fusion)",
        closing is not None and closing.isEnabled() and closing.isChecked(),
    )
    combo = widget("mouse_preset")
    off = []
    for index in range(combo.count()):
        if not combo.model().item(index).isEnabled():
            off.append(combo.itemText(index))
    h.check(
        "P1 mouse presets SciForge cannot give are greyed",
        off == ["Inventor", "Tinkercad", "Alias", "PowerMill"],
        off,
    )
    h.check("P1 Fusion's mouse chosen", combo.currentText() == "Fusion", combo.currentText())
    h.check("P1 the options are SciForge's data", len(prefs_core.options()) > 20)
    h.shot("1-general")


# -- P2 ----------------------------------------------------------------------------------------
def p2_units():
    page("default_units_design")
    di.choose(widget("default_units"), "Inch")
    h.shot("2-units")
    press("SciForgePreferencesOK")


def p2_new_design():
    h.check("P2 the window closed", dialog() is None)
    h.check(
        "P2 kept as FreeCAD's default unit schema", App.ParamGet(UNITS).GetInt("UserSchema", 0) == 3
    )
    h.press(QtCore.Qt.Key_N, QtCore.Qt.ControlModifier)


p2_new_design.wait_ms = 1200


def p2_check():
    doc = App.ActiveDocument
    h.check("P2 Ctrl+N made a new design", doc is not None and doc.Name != s["first"])
    h.check("P2 the new design is in inches", units_of(doc) == "in", units_of(doc))
    h.check(
        "P2 its browser says so",
        any("Units: in" in label for label in t.labels()),
        t.labels(),
    )
    h.check(
        "P2 the earlier design stays in millimetres", units_of(App.getDocument(s["first"])) == "mm"
    )
    s["second"] = doc.Name
    Gui.getDocument(doc.Name).Modified = False
    App.closeDocument(doc.Name)
    App.setActiveDocument(s["first"])
    Gui.setActiveDocument(s["first"])


# -- P3 ----------------------------------------------------------------------------------------
def p3_before():
    h.fit()
    before, after = wheel(away=True)
    h.check("P3 at first, the wheel rolled away zooms in", after < before, (before, after))
    open_prefs()


def p3_reverse():
    page("general")
    m.set_check(widget("reverse_zoom"), True)
    press("SciForgePreferencesApply")


def p3_reversed():
    h.check("P3 Apply keeps the window open", dialog() is not None)
    h.check("P3 FreeCAD's InvertZoom off", not App.ParamGet(VIEW).GetBool("InvertZoom", True))
    before, after = wheel(away=True)
    h.check("P3 now the wheel rolled away zooms out", after > before, (before, after))
    m.set_check(widget("reverse_zoom"), False)
    press("SciForgePreferencesOK")


def p3_back():
    before, after = wheel(away=True)
    h.check("P3 off again: zooms in", after < before, (before, after))


# -- P4 ----------------------------------------------------------------------------------------
def p4_open():
    h.fit()
    turned, moved = middle_drag()
    h.check(
        "P4 Fusion's mouse: a middle drag pans (no turn)",
        turned < 1e-6 and moved > 0.1,
        (turned, moved),
    )
    open_prefs()


def p4_solidworks():
    di.choose(widget("mouse_preset"), "SolidWorks")
    press("SciForgePreferencesOK")


def p4_orbit():
    h.check(
        "P4 FreeCAD's SolidWorks navigation",
        App.ParamGet(VIEW).GetString("NavigationStyle", "") == "Gui::SolidWorksNavigationStyle",
        App.ParamGet(VIEW).GetString("NavigationStyle", ""),
    )
    h.fit()
    turned, _moved = middle_drag()
    h.check("P4 SolidWorks: a middle drag orbits (the view turns)", turned > 0.05, turned)
    open_prefs()


def p4_back():
    di.choose(widget("mouse_preset"), "Fusion")
    press("SciForgePreferencesOK")


def p4_fusion_again():
    h.check(
        "P4 FreeCAD's Revit navigation (Fusion's layout) again",
        App.ParamGet(VIEW).GetString("NavigationStyle", "") == "Gui::RevitNavigationStyle",
    )
    h.fit()
    turned, moved = middle_drag()
    h.check("P4 Fusion again: the middle drag pans", turned < 1e-6 and moved > 0.1, (turned, moved))


# -- P5 ----------------------------------------------------------------------------------------
def p5_history_off():
    open_prefs()
    page("design")
    m.set_check(widget("capture_history"), False)
    y_up = widget("orientation")
    index = y_up.findText("Y up")
    h.check("P5 Y up greyed", index >= 0 and not y_up.model().item(index).isEnabled())
    press("SciForgePreferencesOK")


def p5_new():
    h.press(QtCore.Qt.Key_N, QtCore.Qt.ControlModifier)


p5_new.wait_ms = 1500


def p5_check():
    from sciforge import direct

    doc = App.ActiveDocument
    h.check("P5 a new design", doc is not None and doc.Name != s["first"])
    h.check("P5 it starts without design history", direct.is_direct(doc))
    h.check("P5 it is not marked changed", not Gui.getDocument(doc.Name).Modified)
    h.check(
        "P5 the earlier design keeps its history", not direct.is_direct(App.getDocument(s["first"]))
    )
    Gui.getDocument(doc.Name).Modified = False
    App.closeDocument(doc.Name)
    App.setActiveDocument(s["first"])
    Gui.setActiveDocument(s["first"])


# -- P6 ----------------------------------------------------------------------------------------
def p6_material():
    open_prefs()
    page("material")
    di.choose(widget("default_material"), "Aluminium")
    page("units")
    spin = widget("decimals")
    i.set_spin(spin, 4)
    press("SciForgePreferencesApply")


def p6_check():
    from sciforge import material

    d = dialog()
    note = d.restart_note.text() if d is not None else ""
    h.check(
        "P6 a restart is said for the precision", "Restart" in note and "precision" in note, note
    )
    body = h.body()
    label, rho = material.effective(body)
    h.check(
        "P6 a body without a material counts as Aluminium", label.startswith("Aluminium"), label
    )
    h.check("P6 with Aluminium's density", rho is not None and rho < 3e-6, rho)
    press("SciForgePreferencesOK")


# -- P7 ----------------------------------------------------------------------------------------
def p7_cancel():
    open_prefs()
    page("general")
    i.set_spin(widget("recovery_minutes"), 7)
    press("SciForgePreferencesCancel")


def p7_restore_cancel():
    h.check("P7 Cancel: still 5 minutes", App.ParamGet(FILES).GetInt("AutosaveMinutes", 5) == 5)
    open_prefs()
    press("SciForgePreferencesRestore")
    h.check(
        "P7 Restore Defaults shows Fusion's mouse", widget("mouse_preset").currentText() == "Fusion"
    )
    page("default_units_design")
    h.check(
        "P7 and millimetres",
        widget("default_units").currentText() == "Millimeter",
        widget("default_units").currentText(),
    )
    h.shot("7-restored")
    press("SciForgePreferencesCancel")


def p7_restore_ok():
    h.check(
        "P7 Cancel after Restore Defaults kept the choices",
        App.ParamGet(UNITS).GetInt("UserSchema", 0) == 3,
    )
    open_prefs()
    press("SciForgePreferencesRestore")
    press("SciForgePreferencesOK")


def p7_check():
    from sciforge import material

    h.check("P7 millimetres for new designs", App.ParamGet(UNITS).GetInt("UserSchema", 0) == 0)
    h.check("P7 history on for new designs", App.ParamGet(PREFS).GetBool("CaptureHistory", True))
    h.check("P7 Steel by default", material.default_key() == "steel")
    h.check("P7 precision back to FreeCAD's", "Decimals" not in App.ParamGet(UNITS).GetInts())
    h.check("P7 zoom as SciForge starts", App.ParamGet(VIEW).GetBool("InvertZoom", True))


# -- P8 ----------------------------------------------------------------------------------------
def p8_reverse_then_off():
    open_prefs()
    m.set_check(widget("reverse_zoom"), True)
    press("SciForgePreferencesOK")
    App.ParamGet(VIEW)  # (the user's own value was never set in this profile)


def p8_switch():
    h.check("P8 reversed while SciForge is on", not App.ParamGet(VIEW).GetBool("InvertZoom", True))
    Gui.activateWorkbench("PartWorkbench")


p8_switch.wait_ms = 1500


def p8_off():
    h.check(
        "P8 SciForge off: FreeCAD's own zoom direction back",
        "InvertZoom" not in App.ParamGet(VIEW).GetBools(),
    )
    Gui.activateWorkbench("SciForgeWorkbench")


p8_off.wait_ms = 1500


def p8_on():
    h.check("P8 on again: reversed", not App.ParamGet(VIEW).GetBool("InvertZoom", True))
    open_prefs()
    m.set_check(widget("reverse_zoom"), False)
    press("SciForgePreferencesOK")


def cleanup():
    from sciforge import preferences_ui

    preferences_ui.reset_for_tests()
    App.ParamGet(UNITS).RemInt("Decimals")
    m.close_all()
    h.new_errors()


h.run(
    "misc_preferences",
    [
        setup,
        p1_open,
        p1_window,
        p2_units,
        p2_new_design,
        p2_check,
        p3_before,
        p3_reverse,
        p3_reversed,
        p3_back,
        p4_open,
        p4_solidworks,
        p4_orbit,
        p4_back,
        p4_fusion_again,
        p5_history_off,
        p5_new,
        p5_check,
        p6_material,
        p6_check,
        p7_cancel,
        p7_restore_cancel,
        p7_restore_ok,
        p7_check,
        p8_reverse_then_off,
        p8_switch,
        p8_off,
        p8_on,
        cleanup,
    ],
)
