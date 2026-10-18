# SPDX-License-Identifier: LGPL-2.1-or-later
"""A Raspberry Pi 5 case built from scratch the way a Fusion user builds it (Luca's test of
2026-10-16: "to test how well SciForge works, make a Raspberry Pi 5 case from scratch").
Only real input for picks (clicks on the 3D view, the ribbon, keys); values are typed into
the dialogs' boxes.

The Pi 5 (Raspberry Pi Ltd's mechanical drawing, all mm): board 85 x 56, M2.5 holes 3.5 mm
in from the edges (58 x 49 apart). Long edge: USB-C at 11.2, micro HDMI at 25.8 and 39.2.
Short edge: Ethernet at 10.2, USB 3 at 29.1, USB 2 at 47.0 (centres from the board's
corner). microSD under the board on the other short edge. GPIO header 2 x 20 along the
other long edge, 3.5 mm in. See pi5_board() below for the envelope used by the fit checks.

The case, in design coordinates (the board's corner sits at (3, 3), on 3 mm posts):
  Base: 91 x 62 x 25 block, vertical corners rounded 3, shelled 2 mm with the top open;
        four posts r 3 x 3 on the floor, a 2.5 mm hole 4 deep in each (M2.5 self-tapping);
        openings: front wall USB-C 10 x 5 and two micro HDMI 9 x 5; right wall Ethernet
        17 x 14.5 and two USB stacks 15 x 17; left wall microSD 14 x 3 under the board.
  Lid:  a New Body 2 mm on top, corners rounded 3, a lip 1.2 wide x 1.5 deep that drops
        into the base (0.3 mm play), six vent slots 29 x 3 over the processor (one slot cut,
        then Rectangular Pattern), an opening over the GPIO header, top edges rounded 1
        (one click: Tangent Chain takes the whole loop).
  Then: Export STEP and STL; the Pi's envelope fits (touches nothing) and the lid does not
        collide with the base.

Expected volumes are worked out by hand (see the functions below).
"""

import math
import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
import Part
from PySide import QtCore

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import dialog_input as ui
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import hole_steps as hs
from SciForgeTests.gui import shell_draft_steps as sd

V = App.Vector
s = {}

# -- the design's sizes -------------------------------------------------------------------------
L, W, H = 91.0, 62.0, 25.0  # base outside
T = 2.0  # wall and floor
R = 3.0  # outside corner radius
POST_R, POST_H = 3.0, 3.0
BOARD = V(3, 3, T + POST_H)  # the board's corner (bottom face of the PCB)
PCB = 1.6
HOLES = [(3.5, 3.5), (61.5, 3.5), (3.5, 52.5), (61.5, 52.5)]  # on the board
SCREW_D, SCREW_DEPTH = 2.5, 4.0
PCB_TOP = BOARD.z + PCB  # 6.6
# Openings: (centre along the wall, width, z bottom, z top), design coordinates.
FRONT = [(3 + 11.2, 10.0, 5.7, 10.7), (3 + 25.8, 9.0, 5.7, 10.7), (3 + 39.2, 9.0, 5.7, 10.7)]
RIGHT = [(3 + 10.2, 17.0, 6.1, 20.6), (3 + 29.1, 15.0, 6.1, 23.1), (3 + 47.0, 15.0, 6.1, 23.1)]
LEFT = [(31.0, 14.0, 2.0, 5.0)]
CUT_DEPTH = 3.0  # through the 2 mm wall into the empty inside
LID_T = 2.0
LIP_PLAY, LIP_W, LIP_D = 0.3, 1.2, 1.5
SLOT = (22.0, 48.0, 15.0, 3.0)  # centre x from, centre x to, y, width (the first vent)
SLOTS, SLOT_STEP = 6, 5.0
GPIO = (9.0, 52.5, 62.0, 58.3)  # x0, y0, x1, y1
LID_EDGE_R = 1.0


# -- hand-worked volumes --------------------------------------------------------------------------
def spandrel(r):
    """Area a round of radius r takes from a 90 degree corner."""
    return r * r * (1 - math.pi / 4)


def rounded_rect(length, width, r):
    return length * width - 4 * spandrel(r)


def block():
    return rounded_rect(L, W, R) * H


def shelled():
    # The inside is the outline offset 2 inwards: 87 x 58 with corners of radius 3 - 2 = 1.
    return block() - rounded_rect(L - 2 * T, W - 2 * T, R - T) * (H - T)


def posts():
    return 4 * math.pi * POST_R**2 * POST_H


def screw_holes():
    return 4 * math.pi * (SCREW_D / 2) ** 2 * SCREW_DEPTH


def openings(rows):
    return sum(width * (z1 - z0) * T for _c, width, z0, z1 in rows)


def base_volume(stage):
    order = ["shell", "posts", "holes", "front", "right", "left"]
    v = shelled()
    if order.index(stage) >= 1:
        v += posts()
    if order.index(stage) >= 2:
        v -= screw_holes()
    if order.index(stage) >= 3:
        v -= openings(FRONT)
    if order.index(stage) >= 4:
        v -= openings(RIGHT)
    if order.index(stage) >= 5:
        v -= openings(LEFT)
    return v


def close(a, c, tol=1e-6):
    return abs(a - c) <= tol * max(1.0, abs(c))


# -- helpers ----------------------------------------------------------------------------------------
def doc():
    return App.ActiveDocument


def look(name):
    """The view a person picks on the ViewCube before clicking what it shows."""
    view = Gui.ActiveDocument.ActiveView
    {
        "iso": view.viewIsometric,
        "top": view.viewTop,
        "front": view.viewFront,
        "right": view.viewRight,
        "left": view.viewLeft,
    }[name]()
    view.fitAll()
    settle()


def settle():
    from PySide6 import QtTest

    QtCore.QCoreApplication.processEvents()
    QtTest.QTest.qWait(150)


def look_from(direction):
    """Camera looking along `direction` (e.g. from the back left corner), then fit."""
    view = Gui.ActiveDocument.ActiveView
    rot = App.Rotation(V(0, 0, -1), V(*direction))
    view.setCameraOrientation(rot.Q)
    view.fitAll()
    settle()


def part_ok(where):
    bad = [o.Label for o in doc().Objects if "Invalid" in o.State or "Error" in o.State]
    h.check("%s: nothing in error" % where, not bad, bad)
    body = h.body()
    h.check("%s: a valid solid" % where, body is not None and body.Shape.isValid())


def base_body():
    return doc().getObject(s.get("base", "")) if s.get("base") else None


def base_volume_now():
    body = base_body()
    return body.Shape.Volume if body is not None else 0.0


def extrude_panel():
    from sciforge import extrude_ui

    p = extrude_ui.ExtrudePanel.last
    return p if p is not None and not getattr(p, "_closed", False) else None


def wait_preview(p):
    from PySide6 import QtTest

    for _ in range(80):
        timer = getattr(p, "_timer", None)
        if (timer is None or not timer.isActive()) and not getattr(doc(), "Recomputing", False):
            return
        QtTest.QTest.qWait(50)


def sketch_rects(sk, rects):
    """Rectangles given by two opposite corners in design coordinates (on the sketch plane)."""
    for a, c in rects:
        x0, y0 = h.to_sketch(sk, a)
        x1, y1 = h.to_sketch(sk, c)
        h.draw_rectangle(sk, min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
    doc().recompute()


# -- 1. the block ------------------------------------------------------------------------------------
def new_design():
    view_params = App.ParamGet("User parameter:BaseApp/Preferences/View")
    view_params.SetBool("UseNavigationAnimations", False)
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("Pi5Case")
    h.fit()


def create_sketch_xy():
    h.ribbon("Create Sketch")


def pick_xy():
    h.check("Create Sketch opens no pop-up", not h.popups(), h.popups())
    pl.click_on_plane(V(12, -8, 0))


def draw_outline():
    sk = h.in_sketch()
    if not h.check("a sketch opens on XY", sk is not None):
        return
    h.draw_rectangle(sk, 0, 0, L, W)
    doc().recompute()
    h.shot("01-outline")


def finish_outline():
    h.ribbon("Finish Sketch")


def extrude_block():
    h.fit()
    Gui.Selection.clearSelection()
    h.press(QtCore.Qt.Key_E)


def block_height():
    p = extrude_panel()
    if not h.check(
        "E opens Extrude on the finished sketch",
        p is not None and len(p.profiles) == 1,
        p and p.profiles,
    ):
        return
    ui.type_into(p.distance.widget, "25")
    wait_preview(p)


def block_ok():
    p = extrude_panel()
    h.check(
        "a new body (nothing to join)",
        p is not None and p.operation.currentText() in ("New Body", "Join"),
        p and p.operation.currentText(),
    )
    h.task_button("OK")


def block_made():
    body = h.body()
    s["base"] = body.Name if body is not None else ""
    v = base_volume_now()
    h.check("block 91 x 62 x 25", close(v, L * W * H), v)
    part_ok("block")
    h.shot("02-block")


# -- 2. rounded corners -------------------------------------------------------------------------------
def fillet_start():
    h.fit()
    Gui.Selection.clearSelection()
    h.press(QtCore.Qt.Key_F)


def fillet_front_edges():
    # The three vertical edges the isometric view shows.
    for x, y in ((0, 0), (L, 0), (L, W)):
        h.click_edge(V(x, y, H / 2), QtCore.Qt.NoModifier)


def fillet_turn():
    p = b.blend_panel()
    h.check("three corners picked", p is not None and len(p.refs) == 3, p and p.refs)
    # The fourth corner is behind the part: look from the back left (a ViewCube corner).
    look_from((1, -1, -1))


def fillet_back_edge():
    h.click_edge(V(0, W, H / 2))


def fillet_radius():
    p = b.blend_panel()
    h.check("four corners picked", p is not None and len(p.refs) == 4, p and p.refs)
    if p:
        b.type_into(p.radius.widget, "3")


def fillet_ok():
    h.task_button("OK")


def fillet_made():
    v = base_volume_now()
    h.check("corners rounded 3", close(v, block()), (v, block()))
    part_ok("fillet")
    h.fit()
    h.shot("03-rounded")


# -- 3. shell ------------------------------------------------------------------------------------------
def shell_start():
    h.fit()
    Gui.Selection.clearSelection()
    h.ribbon("Shell")


def shell_pick_top():
    h.click(V(L / 2, W / 2, H))


def shell_thickness():
    p = sd.shell_panel()
    h.check("the top face is taken away", p is not None and len(p.names()) == 1, p and p.names())
    if p:
        sd.type_into(p.inside.widget, "2")


def shell_ok():
    h.task_button("OK")


def shell_made():
    v = base_volume_now()
    h.check("shelled 2 mm, top open", close(v, base_volume("shell")), (v, base_volume("shell")))
    part_ok("shell")
    h.shot("04-shell")


# -- 4. posts ------------------------------------------------------------------------------------------
def post_centres():
    return [V(BOARD.x + x, BOARD.y + y, T) for x, y in HOLES]


def posts_sketch():
    look("top")
    Gui.Selection.clearSelection()
    h.ribbon("Create Sketch")


def posts_pick_floor():
    h.click(V(L / 2, W / 2, T))


def posts_draw():
    sk = h.in_sketch()
    if not h.check("a sketch opens on the floor", sk is not None):
        return
    z = sk.getGlobalPlacement().Base.z
    h.check("the sketch lies on the floor (z = 2)", abs(z - T) < 1e-6, z)
    for c in post_centres():
        x, y = h.to_sketch(sk, c)
        h.draw_circle(sk, x, y, POST_R)
    doc().recompute()


def posts_finish():
    h.ribbon("Finish Sketch")


def posts_extrude():
    look("top")
    Gui.Selection.clearSelection()
    h.press(QtCore.Qt.Key_E)


def posts_click():
    for c in post_centres():
        h.click(c)


def posts_height():
    p = extrude_panel()
    h.check("four circles picked", p is not None and len(p.profiles) == 4, p and p.profiles)
    if p:
        ui.type_into(p.distance.widget, "3")
        wait_preview(p)


def posts_ok():
    p = extrude_panel()
    h.check(
        "posts join the base",
        p is not None and p.operation.currentText() == "Join",
        p and p.operation.currentText(),
    )
    h.task_button("OK")


def posts_made():
    v = base_volume_now()
    h.check("four posts r 3 x 3", close(v, base_volume("posts")), (v, base_volume("posts")))
    part_ok("posts")


# -- 5. screw holes ------------------------------------------------------------------------------------
def holes_sketch():
    look("top")
    Gui.Selection.clearSelection()
    h.ribbon("Create Sketch")


def holes_pick_post():
    c = post_centres()[0]
    h.click(V(c.x + 1, c.y + 1, T + POST_H))


def holes_draw():
    sk = h.in_sketch()
    if not h.check("a sketch opens on a post's top", sk is not None):
        return
    z = sk.getGlobalPlacement().Base.z
    h.check("on the posts' tops (z = 5)", abs(z - (T + POST_H)) < 1e-6, z)
    s["holes_sketch"] = sk.Name
    for c in post_centres():
        x, y = h.to_sketch(sk, c)
        sk.addGeometry(Part.Point(V(x, y, 0)))
    doc().recompute()


def holes_finish():
    h.ribbon("Finish Sketch")


def holes_start():
    look("top")
    Gui.Selection.clearSelection()
    h.ribbon("Hole")


def holes_options():
    p = hs.hole_panel()
    if not h.check("Hole dialog open", p is not None):
        return
    ui.choose(p.placement, "From Sketch (Multiple Holes)")
    ui.choose(p.extent, "Distance")
    ui.choose(p.drill_point, "Flat")
    hs.type_into(p.diameter.widget, "2.5")
    hs.type_into(p.depth.widget, "4")


def hole_count():
    p = hs.hole_panel()
    return len(hs.centres_all(p.target)) if p is not None and p.target is not None else 0


def hole_click(i):
    """Click post i's centre point, then (a later step) see its hole come, as a person
    waits for each one: the four clicks in one step lost two on GitHub's runner (CI #142,
    #143; the dialog takes a click a moment after it)."""

    def click():
        c = post_centres()[i]
        h.click(V(c.x, c.y, T + POST_H))

    def taken():
        h.check(
            "hole %d taken" % (i + 1),
            hole_count() == i + 1,
            (hole_count(), hs.message(hs.hole_panel()) if hs.hole_panel() else "no dialog"),
        )

    click.__name__ = "holes_click_%d" % (i + 1)
    taken.__name__ = "holes_taken_%d" % (i + 1)
    return [click, h.idle_step(), taken]


def holes_ok():
    p = hs.hole_panel()
    count = len(hs.centres_all(p.target)) if p is not None and p.target is not None else 0
    h.check("four holes", count == 4, hs.message(p) if p else "no dialog")
    h.task_button("OK")


def holes_made():
    v = base_volume_now()
    h.check("four 2.5 holes 4 deep", close(v, base_volume("holes")), (v, base_volume("holes")))
    part_ok("holes")
    look("iso")
    h.shot("05-posts")


# -- 6. openings in the walls ---------------------------------------------------------------------
def wall_rects(rows, wall):
    """Corners of each opening on a wall: 'front' (y = 0), 'right' (x = L), 'left' (x = 0)."""
    out = []
    for c, width, z0, z1 in rows:
        if wall == "front":
            out.append((V(c - width / 2, 0, z0), V(c + width / 2, 0, z1)))
        else:
            x = L if wall == "right" else 0.0
            out.append((V(x, c - width / 2, z0), V(x, c + width / 2, z1)))
    return out


def centre(a, c):
    return (a + c) * 0.5


WALLS = {
    # wall: (rows, how to look at it, a point of the wall face no opening takes)
    "front": (FRONT, "iso", V(70, 0, 18)),
    "right": (RIGHT, "iso", V(L, 31, 3)),
    # (far along the wall: nearer the front, the XZ origin square stands in front of it
    # from this side, and a square in front of the part takes the click)
    "left": (LEFT, (1, 1, -1), V(0, 50, 15)),
}


def wall_steps(wall, stage):
    rows, view_name, spot = WALLS[wall]

    def turn():
        Gui.Selection.clearSelection()
        if isinstance(view_name, tuple):
            look_from(view_name)
        else:
            look(view_name)
        h.ribbon("Create Sketch")

    def pick_face():
        h.click(spot)

    def draw():
        sk = h.in_sketch()
        if not h.check("%s wall: a sketch opens on its outside face" % wall, sk is not None):
            return
        normal = sk.getGlobalPlacement().Rotation.multVec(V(0, 0, 1))
        h.check(
            "%s wall: the sketch faces outwards" % wall,
            {"front": normal.y < -0.99, "right": normal.x > 0.99, "left": normal.x < -0.99}[wall],
            normal,
        )
        sketch_rects(sk, wall_rects(rows, wall))
        h.shot("06-%s-sketch" % wall)

    def finish():
        h.ribbon("Finish Sketch")

    def extrude():
        Gui.Selection.clearSelection()
        if isinstance(view_name, tuple):
            look_from(view_name)
        else:
            look(view_name)
        h.press(QtCore.Qt.Key_E)

    def click_openings():
        p = extrude_panel()
        if p is not None and len(rows) == 1 and len(p.profiles) == 1:
            return  # one area: E took it by itself
        for a, c in wall_rects(rows, wall):
            h.click(centre(a, c))

    def depth():
        p = extrude_panel()
        h.check(
            "%s wall: %d opening(s) picked" % (wall, len(rows)),
            p is not None and len(p.profiles) == len(rows),
            p and p.profiles,
        )
        if p:
            ui.type_into(p.distance.widget, "-%g" % CUT_DEPTH)
            wait_preview(p)

    def ok():
        p = extrude_panel()
        h.check(
            "%s wall: into the part makes it a Cut" % wall,
            p is not None and p.operation.currentText() == "Cut",
            p and p.operation.currentText(),
        )
        h.check(
            "%s wall: no message" % wall,
            p is not None and p.message.text() == "",
            p and p.message.text(),
        )
        h.task_button("OK")

    def made():
        v = base_volume_now()
        h.check(
            "%s wall openings cut" % wall, close(v, base_volume(stage)), (v, base_volume(stage))
        )
        part_ok("%s openings" % wall)

    for f in (turn, pick_face, draw, finish, extrude, click_openings, depth, ok, made):
        f.__name__ = "%s_%s" % (wall, f.__name__)
    return [turn, pick_face, draw, finish, extrude, click_openings, depth, ok, made]


# -- 7. the lid ----------------------------------------------------------------------------------------
def lip_rects():
    o = T + LIP_PLAY
    i = o + LIP_W
    return [
        (V(o, o, H + LID_T), V(L - o, W - o, H + LID_T)),
        (V(i, i, H + LID_T), V(L - i, W - i, H + LID_T)),
    ]


def lip_volume():
    o = T + LIP_PLAY
    i = o + LIP_W
    return ((L - 2 * o) * (W - 2 * o) - (L - 2 * i) * (W - 2 * i)) * LIP_D


def slot_area():
    x0, x1, _y, w = SLOT
    return (x1 - x0) * w + math.pi * (w / 2) ** 2


def lid_edge_round(r):
    """A round of radius r along the lid's top outline: Pappus for the corners."""
    k = (10 - 3 * math.pi) / (12 - 3 * math.pi)  # the spandrel's centroid, from the outside
    straight = 2 * (L - 2 * R) + 2 * (W - 2 * R)
    return spandrel(r) * (straight + 2 * math.pi * (R - k * r))


def lid_volume(stage):
    order = ["plate", "corners", "lip", "vent", "vents", "gpio", "edges"]
    n = order.index(stage)
    v = L * W * LID_T
    if n >= 1:
        v = rounded_rect(L, W, R) * LID_T
    if n >= 2:
        v += lip_volume()
    if n >= 3:
        v -= slot_area() * LID_T
    if n >= 4:
        v -= (SLOTS - 1) * slot_area() * LID_T
    if n >= 5:
        v -= (GPIO[2] - GPIO[0]) * (GPIO[3] - GPIO[1]) * LID_T
    if n >= 6:
        v -= lid_edge_round(LID_EDGE_R)
    return v


def lid_body():
    return doc().getObject(s.get("lid", "")) if s.get("lid") else None


def lid_volume_now():
    body = lid_body()
    return body.Shape.Volume if body is not None else 0.0


def check_lid(stage, what):
    v = lid_volume_now()
    h.check("lid: %s" % what, close(v, lid_volume(stage)), (v, lid_volume(stage)))
    vb = base_volume_now()
    h.check("lid: %s leaves the base as it was" % what, close(vb, base_volume("left")), vb)
    body = lid_body()
    h.check("lid: %s, a valid solid" % what, body is not None and body.Shape.isValid())


def lid_sketch():
    look("iso")
    Gui.Selection.clearSelection()
    # The lid's rectangle is drawn over the rim's rounded outline. With the rim's edges
    # projected (Auto project) FreeCAD 1.1.4 makes no area where a projected corner arc
    # meets a drawn line tangent in its middle (its WireJoiner; docs/sciforge/parity/
    # sketch.md, Known gaps): this lid is drawn without them, as in Fusion's default.
    App.ParamGet("User parameter:BaseApp/Preferences/Mod/SciForge/SketchInference").SetBool(
        "AutoProject", False
    )
    h.ribbon("Create Sketch")


def lid_pick_rim():
    h.click(V(L / 2, T / 2, H))  # the front rim's top


def lid_draw():
    sk = h.in_sketch()
    if not h.check("a sketch opens on the rim", sk is not None):
        return
    z = sk.getGlobalPlacement().Base.z
    h.check("on top of the base (z = 25)", abs(z - H) < 1e-6, z)
    sketch_rects(sk, [(V(0, 0, H), V(L, W, H))])


def lid_finish():
    h.ribbon("Finish Sketch")


def lid_extrude():
    look("iso")
    Gui.Selection.clearSelection()
    s["bodies_before"] = [o.Name for o in doc().Objects if o.TypeId == "PartDesign::Body"]
    h.press(QtCore.Qt.Key_E)


def lid_new_body():
    p = extrude_panel()
    if not h.check(
        "E takes the outline by itself", p is not None and len(p.profiles) == 1, p and p.profiles
    ):
        return
    ui.type_into(p.distance.widget, "2")
    wait_preview(p)
    h.check(
        "on top of the base, Join is offered first (Fusion)",
        p.operation.currentText() == "Join",
        p.operation.currentText(),
    )
    h.check("choose New Body", ui.choose(p.operation, "New Body"))
    wait_preview(p)


def lid_ok():
    h.task_button("OK")


def lid_made():
    new = [
        o
        for o in doc().Objects
        if o.TypeId == "PartDesign::Body" and o.Name not in s.get("bodies_before", [])
    ]
    h.check("one new body", len(new) == 1, [o.Label for o in new])
    if new:
        s["lid"] = new[0].Name
    check_lid("plate", "a 2 mm plate")
    h.shot("07-lid")


def lid_fillet_start():
    look("iso")
    Gui.Selection.clearSelection()
    h.press(QtCore.Qt.Key_F)


def lid_fillet_front():
    for x, y in ((0, 0), (L, 0), (L, W)):
        h.click_edge(V(x, y, H + LID_T / 2))


def lid_fillet_turn():
    p = b.blend_panel()
    h.check("lid: three corners picked", p is not None and len(p.refs) == 3, p and p.refs)
    look_from((1, -1, -1))


def lid_fillet_back():
    h.click_edge(V(0, W, H + LID_T / 2))


def lid_fillet_radius():
    p = b.blend_panel()
    h.check("lid: four corners picked", p is not None and len(p.refs) == 4, p and p.refs)
    if p:
        b.type_into(p.radius.widget, "3")


def lid_fillet_ok():
    h.task_button("OK")


def lid_fillet_made():
    check_lid("corners", "corners rounded 3")


def lip_sketch():
    look("iso")
    Gui.Selection.clearSelection()
    h.ribbon("Create Sketch")


def lip_pick_top():
    h.click(V(70, 20, H + LID_T))


def lip_draw():
    sk = h.in_sketch()
    if not h.check("a sketch opens on the lid's top", sk is not None):
        return
    z = sk.getGlobalPlacement().Base.z
    h.check("on the lid (z = 27)", abs(z - (H + LID_T)) < 1e-6, z)
    sketch_rects(sk, lip_rects())


def lip_finish():
    h.ribbon("Finish Sketch")


def lip_extrude():
    look("top")
    Gui.Selection.clearSelection()
    h.press(QtCore.Qt.Key_E)


def lip_click_ring():
    p = extrude_panel()
    if p is not None and p.profiles:
        h.check("two areas: E waits for a click", False, p.profiles)
    o = T + LIP_PLAY + LIP_W / 2
    h.click(V(o, W / 2, H + LID_T))


def lip_depth():
    p = extrude_panel()
    h.check("the ring picked", p is not None and len(p.profiles) == 1, p and p.profiles)
    if not p:
        return
    ui.type_into(p.distance.widget, "-%g" % (LID_T + LIP_D))
    wait_preview(p)
    h.check(
        "into the lid: Cut is offered (Fusion)",
        p.operation.currentText() == "Cut",
        p.operation.currentText(),
    )
    h.check("choose Join", ui.choose(p.operation, "Join"))
    wait_preview(p)


def lip_ok():
    p = extrude_panel()
    h.check("lip: no message", p is not None and p.message.text() == "", p and p.message.text())
    h.task_button("OK")


def lip_made():
    check_lid("lip", "the lip 1.2 x 1.5 under it")


def vent_sketch():
    look("iso")
    Gui.Selection.clearSelection()
    h.ribbon("Create Sketch")


def vent_pick_top():
    h.click(V(70, 20, H + LID_T))


def vent_draw():
    sk = h.in_sketch()
    if not h.check("a sketch opens on the lid for the vent", sk is not None):
        return
    x0, x1, y, w = SLOT
    a = h.to_sketch(sk, V(x0, y, H + LID_T))
    c = h.to_sketch(sk, V(x1, y, H + LID_T))
    b.draw_slot(sk, a[0], a[1], c[0], c[1], w)
    doc().recompute()


def vent_finish():
    h.ribbon("Finish Sketch")


def vent_extrude():
    look("iso")
    Gui.Selection.clearSelection()
    s["titles_before"] = list(b.timeline_titles())
    h.press(QtCore.Qt.Key_E)


def vent_depth():
    p = extrude_panel()
    h.check("E takes the slot by itself", p is not None and len(p.profiles) == 1, p and p.profiles)
    if p:
        ui.type_into(p.distance.widget, "-2")
        wait_preview(p)
        h.check("vent: a Cut", p.operation.currentText() == "Cut", p.operation.currentText())


def vent_ok():
    h.task_button("OK")


def vent_made():
    check_lid("vent", "one vent slot")
    new = [t for t in b.timeline_titles() if t not in s.get("titles_before", [])]
    s["vent_step"] = next((t for t in new if t.startswith("Extrude")), None)
    h.check("the vent is a timeline step", s["vent_step"] is not None, new)


def pattern_start():
    from SciForgeTests.gui import pattern_steps as ps

    look("iso")
    Gui.Selection.clearSelection()
    h.ribbon("Rectangular Pattern")
    s["ps"] = ps


def pattern_pick_vent():
    if s.get("vent_step"):
        s["ps"].timeline_click(s["vent_step"])


def pattern_direction_box():
    s["ps"].click_box("direction")


def pattern_y_axis():
    look("iso")
    h.click(V(0, -12, 0))


def pattern_values():
    ps = s["ps"]
    p = ps.panel()
    if not h.check("pattern dialog open", p is not None):
        return
    d1 = p.options["direction"]
    h.check("Direction 1 is the Y axis", d1 and d1[0].Role == "Y_Axis", d1)
    ps.type_quantity(p.quantity, SLOTS)


def pattern_distance():
    p = s["ps"].panel()
    if p:
        s["ps"].type_value(p.distance_field.widget, "%g" % ((SLOTS - 1) * SLOT_STEP))


def pattern_ok():
    h.task_button("OK")


def pattern_made():
    check_lid("vents", "six vent slots")
    h.shot("08-vents")


def gpio_sketch():
    look("iso")
    Gui.Selection.clearSelection()
    h.ribbon("Create Sketch")


def gpio_pick_top():
    h.click(V(70, 20, H + LID_T))


def gpio_draw():
    sk = h.in_sketch()
    if not h.check("a sketch opens on the lid for the GPIO opening", sk is not None):
        return
    x0, y0, x1, y1 = GPIO
    sketch_rects(sk, [(V(x0, y0, H + LID_T), V(x1, y1, H + LID_T))])


def gpio_finish():
    h.ribbon("Finish Sketch")


def gpio_extrude():
    look("iso")
    Gui.Selection.clearSelection()
    h.press(QtCore.Qt.Key_E)


def gpio_depth():
    p = extrude_panel()
    h.check(
        "E takes the GPIO rectangle by itself",
        p is not None and len(p.profiles) == 1,
        p and p.profiles,
    )
    if p:
        ui.type_into(p.distance.widget, "-2")
        wait_preview(p)


def gpio_ok():
    h.task_button("OK")


def gpio_made():
    check_lid("gpio", "the GPIO opening")


def edges_start():
    look("iso")
    Gui.Selection.clearSelection()
    h.press(QtCore.Qt.Key_F)


def edges_click():
    h.click_edge(V(L / 2, 0, H + LID_T))


def edges_radius():
    p = b.blend_panel()
    h.check("one pick", p is not None and len(p.refs) == 1, p and p.refs)
    shown = sum(len(x.SubElementNames) for x in Gui.Selection.getSelectionEx())
    h.check("Tangent Chain lights up the whole top outline (8 edges)", shown == 8, shown)
    if p:
        b.type_into(p.radius.widget, "%g" % LID_EDGE_R)


def edges_ok():
    h.task_button("OK")


def edges_made():
    check_lid("edges", "top edges rounded 1")
    look("iso")
    h.shot("09-done")


# -- 8. does a Pi 5 fit? ---------------------------------------------------------------------------
def pi5_board():
    """The Pi 5's envelope: the board, its bigger parts (as boxes), the microSD card, the
    GPIO header. Sizes from the drawing and the connectors' data sheets, rounded up."""
    bx, by, bz = BOARD.x, BOARD.y, BOARD.z
    top = bz + PCB
    parts = [Part.makeBox(85, 56, PCB, V(bx, by, bz))]

    def box(x0, y0, z0, dx, dy, dz):
        parts.append(Part.makeBox(dx, dy, dz, V(x0, y0, z0)))

    box(bx + 11.2 - 4.5, by - 0.2, top, 9.0, 7.5, 3.3)  # USB-C, flush with the edge
    for cx in (25.8, 39.2):  # micro HDMI
        box(bx + cx - 3.25, by - 0.5, top, 6.5, 7.5, 3.1)
    box(bx + 85 - 21 + 2.2, by + 10.2 - 8.0, top, 21.0, 16.0, 13.5)  # Ethernet, 2.2 out
    for cy in (29.1, 47.0):  # USB stacks, 2.1 out
        box(bx + 85 - 17 + 2.1, by + cy - 6.6, top, 17.0, 13.2, 16.0)
    box(bx - 2.5, by + 28 - 6.0, bz - 1.4, 15.0, 12.0, 1.4)  # microSD card under the board
    box(bx + 32.5 - 25.5, by + 52.5 - 2.5, top, 51.0, 5.0, 8.5)  # GPIO header
    return parts


def fit_check():
    base, lid = base_body(), lid_body()
    if not h.check("both bodies exist", base is not None and lid is not None):
        return
    clash = []
    for n, piece in enumerate(pi5_board()):
        for body in (base, lid):
            common = body.Shape.common(piece).Volume
            if common > 1e-6:
                clash.append((n, body.Label, round(common, 3)))
    h.check("a Pi 5 fits: board and ports touch nothing", not clash, clash)
    overlap = base.Shape.common(lid.Shape).Volume
    h.check("the lid does not collide with the base", overlap < 1e-6, overlap)
    # Every port is reachable: a box from each port out through its opening is free.
    blocked = []
    reach = [
        ("USB-C", Part.makeBox(9.0, 6.0, 3.3, V(3 + 11.2 - 4.5, -3, PCB_TOP))),
        ("HDMI 0", Part.makeBox(6.5, 6.0, 3.1, V(3 + 25.8 - 3.25, -3, PCB_TOP))),
        ("HDMI 1", Part.makeBox(6.5, 6.0, 3.1, V(3 + 39.2 - 3.25, -3, PCB_TOP))),
        ("Ethernet", Part.makeBox(6.0, 16.0, 13.5, V(L - 3, 3 + 10.2 - 8.0, PCB_TOP))),
        ("USB 3", Part.makeBox(6.0, 13.2, 16.0, V(L - 3, 3 + 29.1 - 6.6, PCB_TOP))),
        ("USB 2", Part.makeBox(6.0, 13.2, 16.0, V(L - 3, 3 + 47.0 - 6.6, PCB_TOP))),
        ("microSD", Part.makeBox(5.0, 12.0, 1.4, V(-3, 3 + 28 - 6.0, BOARD.z - 1.4))),
        ("GPIO", Part.makeBox(51.0, 5.0, 6.0, V(3 + 32.5 - 25.5, 3 + 52.5 - 2.5, H - 1))),
    ]
    for name, path in reach:
        if base.Shape.common(path).Volume + lid.Shape.common(path).Volume > 1e-6:
            blocked.append(name)
    h.check("every port can be reached from outside", not blocked, blocked)


# -- 9. export -----------------------------------------------------------------------------------------
def export_dir():
    return os.path.join(h.OUT_DIR, "pi5_case")


def save_design():
    from SciForgeTests.gui import insert_steps as i

    os.makedirs(export_dir(), exist_ok=True)
    doc().saveAs(os.path.join(export_dir(), "pi5_case.FCStd"))
    i.record_exports()


def export_open():
    from SciForgeTests.gui import insert_steps as i

    look("iso")
    i.ribbon_tab("UTILITIES")
    h.ribbon("Export")


def export_dialog():
    from sciforge import export_ui

    d = export_ui.ExportDialog.last
    return d if d is not None and d.isVisible() else None


def export_step():
    d = export_dialog()
    if not h.check("Export dialog", d is not None):
        return
    h.check("both bodies ticked", len(d.bodies.chosen()) == 2, [x.Label for x in d.bodies.chosen()])
    b.choose(d.type, "STEP")
    b.type_into(d.folder, export_dir())
    b.type_into(d.name, "pi5_case")
    b.click_widget(d.export_button)


export_step.wait_ms = 1500


def export_step_check():
    from SciForgeTests.gui import insert_steps as i

    path = os.path.join(export_dir(), "pi5_case.step")
    if h.check("pi5_case.step written", os.path.isfile(path)):
        solids, volume = i.read_step(path)
        expect = base_volume("left") + lid_volume("edges")
        h.check(
            "STEP: 2 solids with the design's volume",
            solids == 2 and close(volume, expect, 1e-4),
            (solids, volume, expect),
        )


def export_stl_open():
    export_open()


def export_stl():
    d = export_dialog()
    if not h.check("Export dialog again", d is not None):
        return
    b.choose(d.type, "STL (Binary)")
    b.choose(d.structure, "One File Per Body")
    b.type_into(d.folder, export_dir())
    b.type_into(d.name, "pi5_case")
    b.click_widget(d.export_button)


export_stl.wait_ms = 2500


def export_stl_check():
    import glob

    stls = sorted(glob.glob(os.path.join(export_dir(), "*.stl")))
    h.check("one STL per body (base, lid)", len(stls) == 2, stls)


STEPS = [
    new_design,
    create_sketch_xy,
    pick_xy,
    draw_outline,
    finish_outline,
    extrude_block,
    block_height,
    block_ok,
    block_made,
    fillet_start,
    fillet_front_edges,
    fillet_turn,
    fillet_back_edge,
    fillet_radius,
    fillet_ok,
    fillet_made,
    shell_start,
    shell_pick_top,
    shell_thickness,
    shell_ok,
    shell_made,
    posts_sketch,
    posts_pick_floor,
    posts_draw,
    posts_finish,
    posts_extrude,
    posts_click,
    posts_height,
    posts_ok,
    posts_made,
    holes_sketch,
    holes_pick_post,
    holes_draw,
    holes_finish,
    holes_start,
    holes_options,
    *[step for i in range(4) for step in hole_click(i)],
    holes_ok,
    holes_made,
]
STEPS += wall_steps("front", "front") + wall_steps("right", "right") + wall_steps("left", "left")
STEPS += [
    lid_sketch,
    lid_pick_rim,
    lid_draw,
    lid_finish,
    lid_extrude,
    lid_new_body,
    lid_ok,
    lid_made,
    lid_fillet_start,
    lid_fillet_front,
    lid_fillet_turn,
    lid_fillet_back,
    lid_fillet_radius,
    lid_fillet_ok,
    lid_fillet_made,
    lip_sketch,
    lip_pick_top,
    lip_draw,
    lip_finish,
    lip_extrude,
    lip_click_ring,
    lip_depth,
    lip_ok,
    lip_made,
    vent_sketch,
    vent_pick_top,
    vent_draw,
    vent_finish,
    vent_extrude,
    vent_depth,
    vent_ok,
    vent_made,
    pattern_start,
    pattern_pick_vent,
    pattern_direction_box,
    pattern_y_axis,
    pattern_values,
    pattern_distance,
    pattern_ok,
    pattern_made,
    gpio_sketch,
    gpio_pick_top,
    gpio_draw,
    gpio_finish,
    gpio_extrude,
    gpio_depth,
    gpio_ok,
    gpio_made,
    edges_start,
    edges_click,
    edges_radius,
    edges_ok,
    edges_made,
    fit_check,
    save_design,
    export_open,
    export_step,
    export_step_check,
    export_stl_open,
    export_stl,
    export_stl_check,
]

h.run("pi5_case", STEPS)
