# SPDX-License-Identifier: LGPL-2.1-or-later
"""The ViewCube's right-click menu, Ctrl+Alt+V, and the cube following SciForge on and off.

A block 40 x 30 x 10, isometric view. Right-click the cube: SciForge's menu (Go Home,
Orthographic, Perspective, Set Current View as Home, Reset Home), Orthographic ticked, and
not the marking menu of the 3D view; a right click on a see-through corner of the cube's
square is the view's (marking menu). Perspective: the camera is a perspective one (ticked
in the menu next time); Orthographic: back. From FRONT, Go Home: the isometric view.
Ctrl+Alt+V hides the cube, again shows it. Switching to the Part Design workbench (SciForge
off): no SciForge cube, FreeCAD's own NaviCube is back; back to SciForge: the other way."""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import viewcube_input as vc

st = {}
ISO = App.Rotation(0.4247081321999479, 0.1759200437218226, 0.339851090706265, 0.8204732639190053)
ENTRIES = [
    "Go Home",
    "Orthographic",
    "Perspective",
    "Perspective with Ortho Faces",
    "Set Current View as Home",
    "Reset Home",
]


def setup():
    vc.setup("ViewCubeMenu")


def menu():
    from sciforge import marking_menu

    marking_menu._last_menu["widget"] = None
    result = vc.menu_texts()
    texts = [t for t, _ in result["texts"]]
    h.check("right-click on the cube opens the ViewCube menu", texts == ENTRIES, result)
    h.check("Orthographic is ticked", result["checked"] == ["Orthographic"], result["checked"])
    h.check(
        "the 3D view's marking menu did not open",
        marking_menu._last_menu["widget"] is None,
    )


def corner_right_click():
    """A right click on a see-through corner of the cube's square is for the 3D view."""
    from sciforge import marking_menu

    marking_menu._last_menu["widget"] = None
    cube = vc.cube()
    seen = []

    def close_cube_menu():  # only if the cube's menu wrongly opened (it would wait forever)
        for w in QtWidgets.QApplication.topLevelWidgets():
            if w.objectName() == "SciForgeViewCubeMenu" and w.isVisible():
                seen.append(w)
                w.close()

    QtCore.QTimer.singleShot(400, close_cube_menu)
    corner = QtCore.QPoint(cube.width() - 3, cube.height() - 3)
    h.check("nothing of the cube is drawn in that corner", cube.hit(corner.x(), corner.y()) is None)
    vc._open_menu(cube, corner)
    QtWidgets.QApplication.processEvents()
    st["marking"] = marking_menu._last_menu["widget"]
    st["marking_shown"] = st["marking"] is not None and st["marking"].isVisible()
    st["cube_menu"] = seen


def corner_done():
    menu = st["marking"]
    h.check(
        "a right click on a see-through corner opens the view's marking menu",
        st["marking_shown"],
    )
    h.check("and not the ViewCube menu", not st["cube_menu"])
    if menu is not None and menu.isVisible():
        QtTest.QTest.keyClick(menu, QtCore.Qt.Key_Escape)


def perspective():
    result = vc.choose(["Perspective"])
    h.check("Perspective chosen from the menu", result["ok"], result)


def perspective_done():
    h.check("the camera is perspective", h.view().getCameraType() == "Perspective")
    h.shot("1-perspective")
    result = vc.menu_texts()
    h.check("Perspective is ticked now", result["checked"] == ["Perspective"], result["checked"])
    vc.choose(["Orthographic"])


def orthographic_done():
    h.check("the camera is orthographic again", h.view().getCameraType() == "Orthographic")
    vc.click("front")


def go_home():
    h.check("at FRONT", vc.looks_along((0, 1, 0)), vc.describe())
    result = vc.choose(["Go Home"])
    h.check("Go Home chosen from the menu", result["ok"], result)


def go_home_done():
    h.check("Go Home turns to the isometric view", vc.turned(ISO) < 0.01, vc.describe())


def hide():
    from sciforge import shortcuts

    h.check(
        "Ctrl+Alt+V is bound to Show/Hide ViewCube",
        shortcuts.bound_keys().get("CTRL+ALT+V") == "SciForge_ToggleViewCube",
        shortcuts.bound_keys().get("CTRL+ALT+V"),
    )
    h.press(QtCore.Qt.Key_V, QtCore.Qt.ControlModifier | QtCore.Qt.AltModifier)


def hidden():
    cube = vc.cube()
    h.check("Ctrl+Alt+V hides the cube", cube is not None and not cube.isVisible())
    h.shot("2-hidden")
    h.press(QtCore.Qt.Key_V, QtCore.Qt.ControlModifier | QtCore.Qt.AltModifier)


def shown():
    cube = vc.cube()
    h.check("Ctrl+Alt+V again shows it", cube is not None and cube.isVisible())
    Gui.activateWorkbench("PartDesignWorkbench")


def freecad_cube():
    cube = vc.cube()
    h.check("without SciForge there is no SciForge cube", cube is None or not cube.isVisible())
    h.check(
        "and FreeCAD's NaviCube is back",
        h.view().getViewer().isEnabledNaviCube(),
    )
    h.shot("3-freecad")
    Gui.activateWorkbench("SciForgeWorkbench")


def back_in_sciforge():
    cube = vc.cube()
    h.check("back in SciForge the ViewCube is there", cube is not None and cube.isVisible())
    h.check("and FreeCAD's NaviCube is hidden again", not h.view().getViewer().isEnabledNaviCube())


h.run(
    "viewcube_menu",
    [
        setup,
        menu,
        corner_right_click,
        corner_done,
        perspective,
        perspective_done,
        orthographic_done,
        go_home,
        go_home_done,
        hide,
        hidden,
        shown,
        freecad_cube,
        back_in_sciforge,
    ],
)
