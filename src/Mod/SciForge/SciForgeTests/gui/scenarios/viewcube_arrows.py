# SPDX-License-Identifier: LGPL-2.1-or-later
"""When a face of the ViewCube is seen straight on, four small triangles turn the view 90
degrees to the neighbouring face and two curved arrows turn the picture 90 degrees about
the line of sight (Inventor's cube has these; Fusion's exact set is unconfirmed).

A block 40 x 30 x 10, isometric view: no arrows. Click FRONT: the six arrows appear.
Up triangle: TOP (+Y up). Down: FRONT. Right: RIGHT. Left: FRONT. Left: LEFT. Right: FRONT.
Clockwise arrow: still looking at FRONT, the model's top now points right (up on screen
is -X). Counter-clockwise: FRONT upright again; once more: +X up; clockwise: FRONT.
With FreeCAD's animation on, two quick clicks on the right triangle add up: BACK. The
arrow under the mouse lights up blue."""
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import viewcube_input as vc

ARROWS = ("turn-up", "turn-down", "turn-left", "turn-right", "roll-cw", "roll-ccw")


def setup():
    vc.setup("ViewCubeArrows")


def iso():
    targets = vc.cube().targets()
    h.check(
        "no arrows while no face is seen straight on",
        not any(a in targets for a in ARROWS),
        sorted(targets),
    )
    vc.click("front")


def front():
    targets = vc.cube().targets()
    h.check("at FRONT", vc.looks_along((0, 1, 0)) and vc.z_up(), vc.describe())
    h.check(
        "FRONT straight on shows the six arrows", all(a in targets for a in ARROWS), sorted(targets)
    )
    vc.hover("turn-up")
    cube = vc.cube()
    h.check("the arrow under the mouse lights up", cube.hover == "turn-up", cube.hover)
    h.check("it is drawn blue", vc.is_blue(vc.pixel(vc.point("turn-up"))))
    h.shot("1-front-arrows")


def step(arrow, name, direction, up):
    def act():
        vc.click(arrow)

    def done():
        h.check(
            "%s turns to %s" % (arrow, name),
            vc.looks_along(direction) and vc.up_is(up),
            vc.describe(),
        )
        h.check(
            "the arrows are still there at %s" % name,
            all(a in vc.cube().targets() for a in ARROWS),
        )

    act.__name__ = "click_" + arrow.replace("-", "_")
    done.__name__ = "at_" + name.lower().replace(" ", "_")
    return [act, done]


def quick_clicks():
    vc.animations(True)
    vc.click("turn-right")
    vc.click("turn-right")


def quick_done():
    h.check(
        "two quick clicks on the right triangle add up: BACK",
        vc.looks_along((0, -1, 0)) and vc.z_up(),
        vc.describe(),
    )
    vc.animations(False)
    h.shot("3-back")


quick_done.wait_ms = 1800


def rolled_shot():
    h.shot("2-rolled")


h.run(
    "viewcube_arrows",
    [setup, iso, front]
    + step("turn-up", "TOP", (0, 0, -1), (0, 1, 0))
    + step("turn-down", "FRONT", (0, 1, 0), (0, 0, 1))
    + step("turn-right", "RIGHT", (-1, 0, 0), (0, 0, 1))
    + step("turn-left", "FRONT again", (0, 1, 0), (0, 0, 1))
    + step("turn-left", "LEFT", (1, 0, 0), (0, 0, 1))
    + step("turn-right", "FRONT once more", (0, 1, 0), (0, 0, 1))
    + step("roll-cw", "FRONT turned clockwise", (0, 1, 0), (-1, 0, 0))
    + [rolled_shot]
    + step("roll-ccw", "FRONT upright", (0, 1, 0), (0, 0, 1))
    + step("roll-ccw", "FRONT turned counter-clockwise", (0, 1, 0), (1, 0, 0))
    + step("roll-cw", "FRONT upright again", (0, 1, 0), (0, 0, 1))
    + [quick_clicks, quick_done],
)
