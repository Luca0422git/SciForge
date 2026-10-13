# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's mouse details and the orbit choice (plan A2, A3), all with real input.

A block 40 x 30 x 10, isometric view, SciForge on. Checked:
  * SciForge's defaults: constrained orbit (OrbitStyle 2), the orbit about the window's
    middle (RotationMode 0), FreeCAD's red orbit dot off; the Orbit button of the
    navigation bar has a drop-down with Constrained Orbit (ticked) and Free Orbit.
  * Zoomed in so the block spills out of the view, a double-click of the middle button
    fits it (the camera's height changes, every corner is on screen again).
  * A single middle click on the block leaves the camera where it is (FreeCAD's Revit
    style re-centres the view on the clicked point).
  * Ctrl + Shift + middle-drag upwards zooms in; the orientation does not change. A plain
    middle-drag still pans. A double-click with the wheel kept down and moved a little
    (plain, Shift on empty space, Ctrl+Shift) leaves FreeCAD idle afterwards: moving the
    mouse with no button down pans, orbits and zooms nothing.
  * Shift + a single middle click on the top face sets the orbit centre there: the green
    dot (SciForge's own Coin node) is in the scene at the clicked point, the camera did not
    move. A Shift + middle-drag then turns about it: the dot stays on the same pixel while
    the point that was in the middle of the window moves; no roll.
  * Reset Orbit Center in the right-click menu removes the centre and the dot; the same
    drag then turns about the window's middle (FreeCAD's orbit), about as much and the same
    way round as the orbit about the dot.
  * Set Orbit Center in the right-click menu: the next click on the block sets the centre
    (and selects nothing); the Reset command removes it.
  * Orbit drop-down: Free Orbit sets OrbitStyle 4, is remembered in SciForge's preferences
    and applied again by theme.apply() (a new session); a diagonal Shift + middle-drag now
    rolls. The ViewCube's drag follows the choice. Constrained Orbit: back to 2, no roll.
  * A design closed with a centre set, then a new design with the same name: no centre,
    no dot, the orbit turns about the window's middle.
  * SciForge off (Part Design): FreeCAD's OrbitStyle, RotationMode and ShowRotationCenter
    are exactly as before SciForge, the dot is gone and Shift + middle click sets nothing.
    Back in SciForge: the constrained orbit again."""
import importlib
import math

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import viewcube_input as vc
from SciForgeTests.gui import widget_input as w

V = App.Vector
VIEW = "User parameter:BaseApp/Preferences/View"
SCIFORGE = "User parameter:BaseApp/Preferences/Mod/SciForge"
WATCHED = (("Int", "OrbitStyle"), ("Int", "RotationMode"), ("Bool", "ShowRotationCenter"))
MIDDLE = QtCore.Qt.MiddleButton
NONE = QtCore.Qt.NoModifier
SHIFT = QtCore.Qt.ShiftModifier
CTRL = QtCore.Qt.ControlModifier
PIVOT_POINT = V(32, 22, 10)  # on the top face, away from the middle
SECOND_POINT = V(8, 6, 10)
ORBIT_DRAG = ((-150, 60), (-30, 20))  # start and end, pixels from the window's middle
st = {}


def orbit_ui():
    try:
        from sciforge import orbit_ui

        return orbit_ui
    except ImportError:
        return None


def freecad_values():
    group = App.ParamGet(VIEW)
    found = {}
    for kind, name in WATCHED:
        exists = name in getattr(group, "Get%ss" % kind)()
        found[name] = getattr(group, "Get" + kind)(name) if exists else None
    return found


def orbit_style():
    return App.ParamGet(VIEW).GetInt("OrbitStyle", -1)


def remembered_mode():
    return App.ParamGet(SCIFORGE).GetString("OrbitMode", "")


def process():
    QtWidgets.QApplication.processEvents()


def gl():
    return h.gl_widget()


def camera():
    return h.view().getCameraNode()


def cam_pos():
    return V(*camera().position.getValue().getValue())


def cam_height():
    return camera().height.getValue()


def orientation():
    return h.view().getCameraOrientation()


def roll():
    return abs(orientation().multVec(V(1, 0, 0)).z)


def turned(before):
    return math.degrees(before.inverted().multiply(orientation()).Angle)


def azimuth():
    """Compass direction of the camera's line of sight (degrees)."""
    view = orientation().multVec(V(0, 0, -1))
    return math.degrees(math.atan2(view.y, view.x))


def centre():
    widget = gl()
    return QtCore.QPoint(widget.width() // 2, widget.height() // 2)


def off(dx, dy):
    c = centre()
    return QtCore.QPoint(c.x() + dx, c.y() + dy)


def centre_point_3d():
    """The 3D point on the focal plane in the middle of the window."""
    widget = gl()
    ratio = widget.devicePixelRatioF()
    c = centre()
    return V(*h.view().getPoint(int(c.x() * ratio), int((widget.height() - c.y()) * ratio)))


def middle_click(pos, modifiers=NONE):
    h.move(pos)
    QtTest.QTest.mouseClick(gl(), MIDDLE, modifiers, pos)
    process()


def middle_double_click(pos, modifiers=NONE, wobble=0):
    """The events of a real double-click: press, release, double-click, release.
    (QTest.mouseDClick alone sends just the double-click event and keeps the button
    "down" for the test's later moves.) `wobble`: the mouse moves that many pixels with
    the button still down after the second press, before letting go."""
    widget = gl()
    h.move(pos)
    QtTest.QTest.mousePress(widget, MIDDLE, modifiers, pos)
    QtTest.QTest.mouseRelease(widget, MIDDLE, modifiers, pos)
    second = QtGui.QMouseEvent(
        QtCore.QEvent.MouseButtonDblClick,
        QtCore.QPointF(pos),
        QtCore.QPointF(widget.mapToGlobal(pos)),
        MIDDLE,
        MIDDLE,
        modifiers,
    )
    QtWidgets.QApplication.sendEvent(widget, second)
    end = pos
    if wobble:
        end = QtCore.QPoint(pos.x() + wobble, pos.y() + wobble)
        move = QtGui.QMouseEvent(
            QtCore.QEvent.MouseMove,
            QtCore.QPointF(end),
            QtCore.QPointF(widget.mapToGlobal(end)),
            QtCore.Qt.NoButton,
            MIDDLE,
            modifiers,
        )
        QtWidgets.QApplication.sendEvent(widget, move)
    QtTest.QTest.mouseRelease(widget, MIDDLE, modifiers, end)
    process()


def empty_spot():
    """A pixel of the view with nothing of the model under it (bottom-left corner)."""
    widget = gl()
    ratio = widget.devicePixelRatioF()
    for pos in (QtCore.QPoint(30, widget.height() - 30), QtCore.QPoint(30, 30)):
        info = h.view().getObjectInfo(
            (int(pos.x() * ratio), int((widget.height() - pos.y()) * ratio))
        )
        if not info:
            return pos
    return QtCore.QPoint(30, widget.height() - 30)


def orbit_drag(modifiers=SHIFT):
    (ax, ay), (bx, by) = ORBIT_DRAG
    h.drag(off(ax, ay), off(bx, by), button=MIDDLE, modifiers=modifiers)


def model_on_screen():
    box = h.body().Shape.BoundBox
    widget = gl()
    for x in (box.XMin, box.XMax):
        for y in (box.YMin, box.YMax):
            for z in (box.ZMin, box.ZMax):
                p = h.screen_point(V(x, y, z))
                if not (0 <= p.x() < widget.width() and 0 <= p.y() < widget.height()):
                    return False
    return True


def pivot():
    module = orbit_ui()
    return module.pivot() if module is not None else None


def markers():
    module = orbit_ui()
    return module.marker_points(h.view()) if module is not None else []


def near(a, b, tol):
    return (a - b).Length <= tol


# -- the navigation bar's Orbit drop-down -----------------------------------------------------


def nav_orbit_button():
    bar = Gui.getMainWindow().findChild(QtWidgets.QWidget, "SciForgeNavBar")
    if bar is None:
        return None
    for button in bar.findChildren(QtWidgets.QToolButton):
        if button.toolTip().split("\n")[0].strip() == "Orbit":
            return button
    return None


def _click_action(menu, action):
    rect = menu.actionGeometry(action)
    for i in range(6):
        QtTest.QTest.mouseMove(menu, QtCore.QPoint(rect.left() + 10 + 8 * i, rect.center().y()))
    QtTest.QTest.mouseMove(menu, rect.center())
    QtTest.QTest.mouseClick(menu, QtCore.Qt.LeftButton, NONE, rect.center())


def choose_orbit(text):
    """Click the Orbit button of the navigation bar, read its drop-down and click `text`
    (None: only read, then Esc). {'ok', 'texts': [(entry, enabled)], 'checked': [entries]}."""
    result = {"ok": False, "texts": [], "checked": []}
    button = nav_orbit_button()
    if button is None:
        h.check("the navigation bar has an Orbit button", False)
        return result

    def pick(tries=0):
        menu = QtWidgets.QApplication.activePopupWidget()
        if not isinstance(menu, QtWidgets.QMenu):
            if tries < 40:
                QtCore.QTimer.singleShot(50, lambda: pick(tries + 1))
            return
        result["texts"] = [
            (a.text().replace("&", "").strip(), a.isEnabled())
            for a in menu.actions()
            if not a.isSeparator()
        ]
        result["checked"] = [
            a.text().replace("&", "").strip() for a in menu.actions() if a.isChecked()
        ]
        action = None
        for a in menu.actions():
            if a.text().replace("&", "").strip() == text:
                action = a
        if action is None or not action.isEnabled():
            QtTest.QTest.keyClick(menu, QtCore.Qt.Key_Escape)
            return
        _click_action(menu, action)
        result["ok"] = True

    QtCore.QTimer.singleShot(50, pick)
    w.click(button)  # the drop-down opens its own event loop; pick() runs inside it
    process()
    return result


# -- the right-click marking menu ----------------------------------------------------------


def open_marking_menu():
    from sciforge import marking_menu

    marking_menu._last_menu["widget"] = None
    widget = gl()
    w.click(widget, QtCore.QPoint(widget.width() - 140, 140), button=QtCore.Qt.RightButton)
    menu = marking_menu._last_menu["widget"]
    h.check("a right click opens the marking menu", menu is not None and menu.isVisible())
    return menu


def rows(menu):
    return [menu.list.item(i) for i in range(menu.list.count())]


def click_row(menu, text):
    for row in rows(menu):
        if row.text().split("    ")[0] == text:
            rect = menu.list.visualItemRect(row)
            w.click(menu.list.viewport(), rect.center())
            return True
    h.check("list row %r exists" % text, False, [r.text() for r in rows(menu)])
    return False


# -- steps ----------------------------------------------------------------------------------


def before_sciforge():
    Gui.activateWorkbench("PartDesignWorkbench")
    App.ParamGet(SCIFORGE).RemString("OrbitMode")  # a fresh install's choice
    st["values_before"] = freecad_values()


def setup():
    vc.setup("OrbitFeel")


def defaults():
    module = orbit_ui()
    h.check("orbit_ui is there", module is not None)
    values = freecad_values()
    h.check("constrained orbit (FreeCAD's Free Turntable, 2)", values["OrbitStyle"] == 2, values)
    h.check("the orbit turns about the window's middle", values["RotationMode"] == 0, values)
    h.check("FreeCAD's red orbit dot is off", values["ShowRotationCenter"] is False, values)
    h.check(
        "the remembered mode is Constrained", module is not None and module.mode() == "constrained"
    )
    result = choose_orbit(None)
    h.check(
        "the Orbit button lists Constrained Orbit and Free Orbit",
        [t for t, _ in result["texts"]] == ["Constrained Orbit", "Free Orbit"],
        result,
    )
    h.check("Constrained Orbit is ticked", result["checked"] == ["Constrained Orbit"], result)


def zoom_in_for_fit():
    camera().height.setValue(cam_height() * 0.3)
    process()
    h.check("zoomed in: the block spills out of the view", not model_on_screen())
    st["height"] = cam_height()
    st["pos"] = cam_pos()
    middle_double_click(centre())


def double_click_done():
    h.check("a middle double-click fits: the camera's height changed", cam_height() != st["height"])
    h.check("and the whole block is on screen again", model_on_screen())
    h.shot("1-after-fit")
    # A single middle click on the block: the camera must stay (Revit re-centres on it).
    st["pos"] = cam_pos()
    st["before"] = orientation()
    middle_click(h.screen_point(V(4, 4, 10)))


def single_click_done():
    h.check("a single middle click does not move the camera", near(cam_pos(), st["pos"], 1e-6))
    h.check("nor turn it", turned(st["before"]) < 1e-6, turned(st["before"]))
    st["height"] = cam_height()
    h.drag(off(0, 80), off(0, -80), button=MIDDLE, modifiers=CTRL | SHIFT)


def zoom_drag_done():
    h.check(
        "Ctrl+Shift+middle-drag upwards zooms in",
        cam_height() < 0.9 * st["height"],
        (st["height"], cam_height()),
    )
    h.check("the zoom drag does not turn the view", turned(st["before"]) < 1e-6)
    h.shot("2-after-zoom-drag")
    st["pos"] = cam_pos()
    h.drag(off(0, 0), off(120, 0), button=MIDDLE)


def pan_done():
    h.check("a plain middle-drag still pans", not near(cam_pos(), st["pos"], 1e-3), cam_pos())
    h.check("and does not turn the view", turned(st["before"]) < 1e-6)
    h.fit()
    # A double-click with the wheel kept down and moved a little before letting go, plain
    # (Fit), with Shift on empty space and with Ctrl+Shift: FreeCAD must not be left
    # panning, orbiting or zooming by itself afterwards (review finding).
    middle_double_click(centre(), NONE, wobble=10)
    middle_double_click(empty_spot(), SHIFT, wobble=10)
    middle_double_click(off(80, 60), CTRL | SHIFT, wobble=10)
    st["pos"] = cam_pos()
    st["before"] = orientation()
    st["height"] = cam_height()
    for dx, dy in ((40, 30), (-120, 60), (90, -80)):  # the mouse moves, no button down
        h.move(off(dx, dy))


def not_stuck():
    h.check(
        "after a double-click with a wobble, FreeCAD is not left panning by itself",
        near(cam_pos(), st["pos"], 1e-6),
        (st["pos"], cam_pos()),
    )
    h.check("nor orbiting by itself", turned(st["before"]) < 1e-6, turned(st["before"]))
    h.check("nor zooming by itself", abs(cam_height() - st["height"]) < 1e-9, cam_height())
    h.fit()
    # Shift + a single middle click on the top face: the orbit centre goes there.
    st["pos"] = cam_pos()
    st["pivot_px"] = h.screen_point(PIVOT_POINT)
    middle_click(st["pivot_px"], SHIFT)


def shift_click_done():
    point = pivot()
    h.check("Shift+middle click sets the orbit centre", point is not None, point)
    if point is not None:
        h.check("at the clicked point of the top face", near(point, PIVOT_POINT, 0.6), point)
    dots = markers()
    h.check("the green dot is in the scene", len(dots) == 1, dots)
    if dots and point is not None:
        h.check("at the orbit centre", near(dots[0], point, 1e-6), dots[0])
    h.check("the click did not move the camera", near(cam_pos(), st["pos"], 1e-6))
    h.shot("3-orbit-centre")
    st["before"] = orientation()
    st["azimuth"] = azimuth()
    st["centre_3d"] = centre_point_3d()
    st["pivot_px"] = h.screen_point(point) if point is not None else None
    orbit_drag()


def pivot_orbit_done():
    point = pivot()
    h.check("Shift+middle-drag with a centre turned the view", turned(st["before"]) > 8)
    h.check("without rolling", roll() < 1e-6, roll())
    if point is not None and st["pivot_px"] is not None:
        now = h.screen_point(point)
        h.check(
            "the orbit centre stayed on the same pixel",
            (now - st["pivot_px"]).manhattanLength() <= 2,
            (st["pivot_px"], now),
        )
    moved = (h.screen_point(st["centre_3d"]) - centre()).manhattanLength()
    h.check("while the window's middle point moved (not FreeCAD's orbit)", moved > 5, moved)
    st["turn_pivot"] = turned(st["before"])
    st["way_pivot"] = azimuth() - st["azimuth"]
    h.shot("4-orbited-about-centre")
    menu = open_marking_menu()
    if menu is not None:
        texts = [r.text().split("    ")[0] for r in rows(menu)]
        h.check(
            "the menu lists Set Orbit Center and Reset Orbit Center",
            "Set Orbit Center" in texts and "Reset Orbit Center" in texts,
            texts,
        )
        click_row(menu, "Reset Orbit Center")


def reset_done():
    h.check("Reset Orbit Center removed the centre", pivot() is None, pivot())
    h.check("and the dot", markers() == [], markers())
    h.fit()
    st["before"] = orientation()
    st["azimuth"] = azimuth()
    orbit_drag()


def freecad_orbit_done():
    h.check("without a centre, Shift+middle-drag still orbits", turned(st["before"]) > 8)
    h.check("without rolling", roll() < 1e-6, roll())
    ratio = st["turn_pivot"] / max(1e-9, turned(st["before"]))
    h.check(
        "the orbit about the centre turns about as much as FreeCAD's own",
        0.65 < ratio < 1.5,
        (st["turn_pivot"], turned(st["before"])),
    )
    way = azimuth() - st["azimuth"]
    h.check("and the same way round", way * st["way_pivot"] > 0, (way, st["way_pivot"]))
    h.fit()
    menu = open_marking_menu()
    if menu is not None:
        click_row(menu, "Set Orbit Center")


def set_via_menu():
    Gui.Selection.clearSelection()
    h.click(SECOND_POINT)


def set_via_menu_done():
    point = pivot()
    h.check("Set Orbit Center, then a click: the centre is there", point is not None, point)
    if point is not None:
        h.check("at the clicked point", near(point, SECOND_POINT, 0.6), point)
    h.check("the click selected nothing", not Gui.Selection.getSelectionEx())
    h.check("the dot moved there", len(markers()) == 1 and near(markers()[0], point, 1e-6))
    Gui.runCommand("SciForge_ResetOrbitCenter")


def reset_command_done():
    h.check("the Reset Orbit Center command removed it", pivot() is None and markers() == [])
    result = choose_orbit("Free Orbit")
    h.check("Free Orbit chosen in the Orbit drop-down", result["ok"], result)


def free_done():
    h.check("Free Orbit sets FreeCAD's Rounded Arcball (4)", orbit_style() == 4, orbit_style())
    h.check("and is remembered in SciForge's preferences", remembered_mode() == "free")
    result = choose_orbit(None)
    h.check("Free Orbit is ticked now", result["checked"] == ["Free Orbit"], result)
    st["before"] = orientation()
    h.drag(off(-60, -40), off(140, 90), button=MIDDLE, modifiers=SHIFT)


def free_rolls():
    h.check("a diagonal drag turned the view", turned(st["before"]) > 10)
    h.check("the free orbit can roll", roll() > 1e-3, roll())
    h.fit()
    # A new session: theme.apply() keeps the user's value and applies the remembered mode.
    from sciforge import theme

    App.ParamGet(VIEW).SetInt("OrbitStyle", 2)
    saved = theme._saved_qss
    importlib.reload(theme)
    theme._saved_qss = saved
    theme.apply()


def restart_done():
    h.check("after a restart the remembered Free Orbit is applied", orbit_style() == 4)
    st["before"] = orientation()
    st["up"] = orientation().multVec(V(0, 1, 0))
    vc.drag("top", 60, 0)


def cube_free_done():
    h.check("the ViewCube's drag turns the view in Free mode", vc.turned(st["before"]) > 10)
    up = orientation().multVec(V(0, 1, 0))
    h.check(
        "a sideways cube drag in Free mode turns about the camera's own up axis",
        (up - st["up"]).Length < 1e-6,
        (up, st["up"]),
    )
    h.fit()
    result = choose_orbit("Constrained Orbit")
    h.check("Constrained Orbit chosen again", result["ok"], result)


def constrained_done():
    h.check("Constrained Orbit sets OrbitStyle 2", orbit_style() == 2, orbit_style())
    h.check("and is remembered", remembered_mode() == "constrained")
    st["before"] = orientation()
    h.drag(off(-60, -40), off(140, 90), button=MIDDLE, modifiers=SHIFT)


def constrained_rolls_not():
    h.check("a diagonal drag turned the view", turned(st["before"]) > 10)
    h.check("the constrained orbit never rolls", roll() < 1e-6, roll())
    h.fit()
    middle_click(h.screen_point(PIVOT_POINT), SHIFT)


def closed_design():
    # A design closed with an orbit centre set, then a new design with the same name: the
    # centre must not come back (invisible, the orbit turned about it; review finding).
    h.check("a centre is set in the design about to be closed", pivot() is not None)
    App.closeDocument(App.ActiveDocument.Name)
    vc.setup("OrbitFeel")


def closed_design_done():
    h.check("a new design with the same name has no orbit centre", pivot() is None, pivot())
    h.check("and no dot", markers() == [], markers())
    st["centre_3d"] = centre_point_3d()
    orbit_drag()
    moved = (h.screen_point(st["centre_3d"]) - centre()).manhattanLength()
    h.check("its orbit turns about the window's middle again", moved <= 2, moved)
    h.fit()
    middle_click(h.screen_point(PIVOT_POINT), SHIFT)


def off_sciforge():
    h.check("a centre is set before leaving SciForge", pivot() is not None and len(markers()) == 1)
    Gui.activateWorkbench("PartDesignWorkbench")


def off_done():
    h.check(
        "SciForge off: OrbitStyle, RotationMode and ShowRotationCenter exactly as before",
        freecad_values() == st["values_before"],
        (st["values_before"], freecad_values()),
    )
    h.check("no SciForge dot left in the view", markers() == [], markers())
    h.check("and no orbit centre", pivot() is None)
    middle_click(h.screen_point(PIVOT_POINT), SHIFT)


def off_click_done():
    h.check("Shift+middle click sets nothing without SciForge", pivot() is None and markers() == [])
    Gui.activateWorkbench("SciForgeWorkbench")


def back_on():
    h.check("back in SciForge: the constrained orbit", orbit_style() == 2, orbit_style())


h.run(
    "orbit_feel",
    [
        before_sciforge,
        setup,
        defaults,
        zoom_in_for_fit,
        double_click_done,
        single_click_done,
        zoom_drag_done,
        pan_done,
        not_stuck,
        shift_click_done,
        pivot_orbit_done,
        reset_done,
        freecad_orbit_done,
        set_via_menu,
        set_via_menu_done,
        reset_command_done,
        free_done,
        free_rolls,
        restart_done,
        cube_free_done,
        constrained_done,
        constrained_rolls_not,
        closed_design,
        closed_design_done,
        off_sciforge,
        off_done,
        off_click_done,
        back_on,
    ],
)
