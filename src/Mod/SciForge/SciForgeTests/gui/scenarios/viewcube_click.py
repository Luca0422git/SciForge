# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's ViewCube in the top-right corner: click a face, an edge or a corner and the
view turns there; the part under the mouse lights up blue; the cube is see-through until
the mouse comes over it; FreeCAD's own cube (NaviCube) is gone.

A block 40 x 30 x 10, isometric view. Real clicks on the cube, moving round it like a
person: FRONT (looks along +Y, Z up), the TOP-FRONT edge (halfway: along (0, 1, -1)),
TOP (looks down -Z, +Y up), the TOP-BACK-LEFT corner (isometric from back-left-top), BACK,
the BACK-LEFT edge, LEFT, the BOTTOM-LEFT edge, BOTTOM (looks up +Z, -Y up), the
BOTTOM-FRONT-RIGHT corner. After every click outside TOP/BOTTOM the camera is level and Z
points up the screen. Then with FreeCAD's animation on: a click on FRONT turns the view
smoothly (not there at once, there half a second later)."""
import math

import FreeCAD as App
from PySide import QtCore

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import viewcube_input as vc

S2, S3 = math.sqrt(2.0), math.sqrt(3.0)
st = {}


def setup():
    vc.setup("ViewCubeClick")


def look():
    group = App.ParamGet("User parameter:BaseApp/Preferences/View")
    h.check("FreeCAD's NaviCube is switched off", not group.GetBool("ShowNaviCube", True))
    h.check(
        "FreeCAD's NaviCube is not drawn in the view",
        not h.view().getViewer().isEnabledNaviCube(),
    )
    cube = vc.cube()
    if not h.check("SciForge's ViewCube is on the 3D view", cube is not None):
        return
    gl = h.gl_widget()
    rect = cube.geometry()
    h.check("the ViewCube is visible", cube.isVisible())
    h.check(
        "it sits in the top-right corner of the view",
        gl.width() - rect.right() < 12 and rect.top() < 12,
        (rect.getRect(), gl.width()),
    )
    # FreeCAD keeps the top-right 142 px free of the command dialog that floats on the right.
    h.check("it fits above the floating command dialog", rect.bottom() <= 142, rect.getRect())
    targets = cube.targets()
    h.check(
        "the isometric view shows FRONT, RIGHT and TOP and their corner",
        all(n in targets for n in ("front", "right", "top", "top-front-right")),
        sorted(targets),
    )
    h.check(
        "no back faces are clickable from the front",
        not any(n in targets for n in ("back", "left", "bottom")),
        sorted(targets),
    )
    colour = vc.pixel(vc.sample_point("front"))
    h.check("the cube is see-through while the mouse is away", colour.alpha() < 200, colour.name())
    h.shot("1-iso")


def hover_face():
    vc.hover("front")


def hover_face_done():
    cube = vc.cube()
    h.check("FRONT is lit up under the mouse", cube.hover == "front", cube.hover)
    colour = vc.pixel(vc.sample_point("front"))
    h.check("FRONT is drawn in SciForge blue", vc.is_blue(colour), colour.name())
    h.check("the cube is opaque under the mouse", colour.alpha() == 255, colour.alpha())
    h.shot("2-hover-front")
    vc.hover("top-front")


def hover_edge_done():
    cube = vc.cube()
    h.check("the TOP-FRONT edge is lit up under the mouse", cube.hover == "top-front", cube.hover)
    h.check("the edge is drawn blue", vc.is_blue(vc.pixel(vc.sample_point("top-front"))))
    h.check("FRONT is not blue any more", not vc.is_blue(vc.pixel(vc.sample_point("front"))))
    vc.move_away()


def away_done():
    cube = vc.cube()
    h.check("nothing lit up once the mouse left", cube.hover is None, cube.hover)
    h.check("see-through again", vc.pixel(vc.sample_point("front")).alpha() < 200)


def expect(name, direction, up=None):
    def step():
        h.check("%s: looks along %s" % (name, direction), vc.looks_along(direction), vc.describe())
        if up is not None:
            h.check("%s: %s is up on screen" % (name, up), vc.up_is(up), vc.describe())
        else:
            h.check("%s: level, Z up on screen" % name, vc.z_up(), vc.describe())

    return step


def click(name):
    def step():
        vc.click(name)

    step.__name__ = "click_" + name.replace("-", "_")
    return step


def checked(name, direction, up=None):
    """A click on `name`, then (next step) the view checks."""
    check = expect(name, direction, up)

    def step():
        check()
        h.shot("click-" + name)

    step.__name__ = "check_" + name.replace("-", "_")
    return [click(name), step]


def animate():
    vc.animations(True)
    st["before"] = vc.orientation()
    vc.click("front")
    st["right_after"] = vc.turned(st["before"])
    st["left_to_go"] = vc.turned(vc.orientation(), App.Rotation(0.70710678, 0, 0, 0.70710678))


def animate_done():
    h.check(
        "with animations on, the view does not jump at once",
        st["left_to_go"] > 5.0,
        (st["right_after"], st["left_to_go"]),
    )
    h.check("and arrives at FRONT", vc.looks_along((0, 1, 0)) and vc.z_up(), vc.describe())
    vc.animations(False)


animate_done.wait_ms = 1500

h.run(
    "viewcube_click",
    [setup, look, hover_face, hover_face_done, hover_edge_done, away_done]
    + checked("front", (0, 1, 0))
    + checked("top-front", (0, 1 / S2, -1 / S2))
    + checked("top", (0, 0, -1), up=(0, 1, 0))
    + checked("top-back-left", (1 / S3, -1 / S3, -1 / S3))
    + checked("back", (0, -1, 0))
    + checked("back-left", (1 / S2, -1 / S2, 0))
    + checked("left", (1, 0, 0))
    + checked("bottom-left", (1 / S2, 0, 1 / S2))
    + checked("bottom", (0, 0, 1), up=(0, -1, 0))
    + checked("bottom-front-right", (-1 / S3, 1 / S3, 1 / S3))
    + [animate, animate_done],
)
