# SPDX-License-Identifier: LGPL-2.1-or-later
"""The house above the ViewCube goes Home; Home belongs to the design (Fusion).

A block 40 x 30 x 10, saved to a file. FRONT (the cube lets the mouse wheel through to
the view), zoomed in, then the house: the isometric view
from front-right-top, fitted (the whole block on screen, filling it). Right-click > Set
Current View as Home > Fit to View on the TOP-FRONT edge view; FRONT; house: TOP-FRONT,
fitted. Fixed Distance on the FRONT-RIGHT edge view, zoomed in: TOP and fit; house: that
view and that zoom again. Right-click > Reset Home; house: isometric again. Home set to the
BOTTOM-FRONT-RIGHT corner, saved, the design closed and opened again: the house goes to
that corner. A new design has the default Home."""
import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtGui, QtWidgets

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import viewcube_input as vc

ISO = App.Rotation(0.4247081321999479, 0.1759200437218226, 0.339851090706265, 0.8204732639190053)
st = {}


def setup():
    vc.setup("ViewCubeHome")
    st["path"] = os.path.join(tempfile.mkdtemp(prefix="sciforge-home-"), "home_test.FCStd")
    App.ActiveDocument.saveAs(st["path"])


def fitted():
    """The whole block is on screen and fills a good part of it (Fit to View)."""
    gl = h.gl_widget()
    box = h.body().Shape.BoundBox
    xs, ys = [], []
    for x in (box.XMin, box.XMax):
        for y in (box.YMin, box.YMax):
            for z in (box.ZMin, box.ZMax):
                p = h.screen_point(App.Vector(x, y, z))
                xs.append(p.x())
                ys.append(p.y())
    inside = min(xs) >= 0 and min(ys) >= 0 and max(xs) <= gl.width() and max(ys) <= gl.height()
    share = max((max(xs) - min(xs)) / gl.width(), (max(ys) - min(ys)) / gl.height())
    return inside and share > 0.45, (min(xs), min(ys), max(xs), max(ys), round(share, 2))


def camera_field(name):
    import re

    found = re.search(r"^\s*%s\s+(.*)$" % name, h.view().getCamera(), re.M)
    return [float(v) for v in found.group(1).split()] if found else None


def wheel_over_cube():
    """The mouse wheel turned over the cube: the cube must leave it to the view under it
    (Qt then hands a real wheel event on to the view, which zooms)."""
    cube = vc.cube()
    pos = QtCore.QPointF(vc.point("front"))
    event = QtGui.QWheelEvent(
        pos,
        QtCore.QPointF(cube.mapToGlobal(pos.toPoint())),
        QtCore.QPoint(0, 0),
        QtCore.QPoint(0, 120),
        QtCore.Qt.NoButton,
        QtCore.Qt.NoModifier,
        QtCore.Qt.NoScrollPhase,
        False,
    )
    QtWidgets.QApplication.sendEvent(cube, event)
    return not event.isAccepted()


def default_home():
    vc.click("front")
    h.check("the cube lets the mouse wheel through to the view", wheel_over_cube())
    st["height"] = camera_field("height")
    h.view().zoomIn()
    h.view().zoomIn()


def zoomed():
    h.check("zoomed in", camera_field("height") != st["height"])
    h.check("still at FRONT", vc.looks_along((0, 1, 0)), vc.describe())
    vc.click("home")


def home_default_done():
    h.check(
        "the house goes to the isometric view (front-right-top)",
        vc.turned(ISO) < 0.01 and vc.z_up(),
        vc.describe(),
    )
    ok, detail = fitted()
    h.check("Home fits the whole model on screen", ok, detail)
    h.shot("1-default-home")
    vc.click("top-front")


def set_fit():
    st["home"] = vc.orientation()
    result = vc.choose(["Set Current View as Home", "Fit to View"])
    h.check("the menu has Set Current View as Home > Fit to View", result["ok"], result)


def set_fit_done():
    meta = App.ActiveDocument.Meta
    h.check("Home is stored in the design", "SciForgeHome" in meta, sorted(meta))
    vc.click("front")
    h.view().zoomIn()
    h.view().zoomIn()


def go_fit():
    vc.click("home")


def go_fit_done():
    h.check(
        "the house goes to the new Home (TOP-FRONT edge view)",
        vc.turned(st["home"]) < 0.01 and vc.z_up(),
        vc.describe(),
    )
    ok, detail = fitted()
    h.check("a Fit to View Home fits the model", ok, detail)
    vc.click("front-right")
    h.view().zoomIn()


def set_fixed():
    st["home"] = vc.orientation()
    st["camera"] = {f: camera_field(f) for f in ("height", "position", "focalDistance")}
    result = vc.choose(["Set Current View as Home", "Fixed Distance"])
    h.check("the menu has Set Current View as Home > Fixed Distance", result["ok"], result)


def leave_fixed():
    vc.click("top-front-right")
    vc.click("top")
    h.fit(iso=False)


def go_fixed():
    st["height_before"] = camera_field("height")
    vc.click("home")


def go_fixed_done():
    h.check(
        "the house goes to the Fixed Distance Home's direction (FRONT-RIGHT edge)",
        vc.turned(st["home"]) < 0.01 and vc.z_up(),
        vc.describe(),
    )
    now = {f: camera_field(f) for f in ("height", "position", "focalDistance")}
    same = all(
        now[f] is not None
        and st["camera"][f] is not None
        and all(abs(a - b) <= 1e-3 * max(1.0, abs(b)) for a, b in zip(now[f], st["camera"][f]))
        for f in now
    )
    h.check(
        "Fixed Distance brings back the same zoom and position",
        same and now["height"] != st["height_before"],
        (now, st["camera"]),
    )
    h.shot("2-fixed-distance-home")
    result = vc.choose(["Reset Home"])
    h.check("the menu has Reset Home", result["ok"], result)


def reset_done():
    h.check("Reset Home removes the stored Home", "SciForgeHome" not in App.ActiveDocument.Meta)
    vc.click("front")
    vc.click("home")


def reset_home_done():
    h.check(
        "after Reset Home the house goes to the isometric view again",
        vc.turned(ISO) < 0.01,
        vc.describe(),
    )
    ok, detail = fitted()
    h.check("and fits the model", ok, detail)
    vc.click("front")
    vc.click("bottom-front")
    vc.click("bottom-front-right")
    st["home"] = vc.orientation()
    vc.choose(["Set Current View as Home", "Fit to View"])
    App.ActiveDocument.save()


def reopen():
    App.closeDocument(App.ActiveDocument.Name)
    App.openDocument(st["path"])
    Gui.SendMsgToActiveView("ViewFit")


def reopened():
    meta = App.ActiveDocument.Meta
    h.check("the reopened design still has its Home", "SciForgeHome" in meta, sorted(meta))
    if h.check("the reopened view has a ViewCube", vc.cube() is not None):
        h.view().viewFront()
        vc.click("home")


def reopened_home():
    h.check(
        "after save and reopen the house goes to the stored Home (BOTTOM-FRONT-RIGHT)",
        vc.turned(st["home"]) < 0.01,
        vc.describe(),
    )
    h.shot("3-reopened-home")
    App.newDocument("ViewCubeHomeNew")


def new_design():
    vc.click("home")


def new_design_done():
    h.check(
        "a new design's house goes to the isometric view",
        vc.turned(ISO) < 0.01 and vc.z_up(),
        vc.describe(),
    )


h.run(
    "viewcube_home",
    [
        setup,
        default_home,
        zoomed,
        home_default_done,
        set_fit,
        set_fit_done,
        go_fit,
        go_fit_done,
        set_fixed,
        leave_fixed,
        go_fixed,
        go_fixed_done,
        reset_done,
        reset_home_done,
        reopen,
        reopened,
        reopened_home,
        new_design,
        new_design_done,
    ],
)
