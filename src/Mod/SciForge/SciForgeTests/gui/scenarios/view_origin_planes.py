# SPDX-License-Identifier: LGPL-2.1-or-later
"""The origin planes and axes are coloured, labelled and smaller (Luca: "the yellow axis
selector is ugly ... too big ... you can't tell which face is the x y or z. give it the red
green blue of all the rest of the axis and make it smaller. and label them."). Only real
input.

  A  New design, Create Sketch: three squares, XY blue, XZ green, YZ red (the colour of the
     axis each one faces), see-through, labelled "XY", "XZ", "YZ"; 100 mm in an empty design.
  B  The mouse over the XY square: it alone gets brighter, less see-through and a thicker
     outline; off it again: back to the idle look. Esc cancels: nothing made.
  C  A 20 x 20 x 20 box (Create Sketch on XY, rectangle 0..20, Extrude 20).
  D  Create Sketch with the box there: the squares are 20 mm (0.6 x 20 = 12, at least 20; they
     were 1.3 x = 26), the labels sit at the corners away from the box; a click at
     (-12, 0, 5), inside the old square but outside the new one, picks nothing; a click on
     the XZ square at (8, 0, -8) (under the box) opens the sketch on XZ. A rectangle
     x 25..30, z 0..5; Finish Sketch.
  E  Revolve: the origin axes it offers are labelled X, Y, Z in red, green, blue; Esc.
  F  CONSTRUCT > Offset Plane (Construct's own copy of the squares): the same colours and
     labels; the mouse lights the XY square; Esc.
  G  SOLID > CREATE > Box (the primitives' squares, sized from the whole design): the same
     rule (20 mm), coloured and labelled; Esc.
  H  The patterns' axis lines use the same colours (pattern_ui.AXIS_COLORS).
  I  Components: a component made from the body moved 40 mm along X and activated; Create
     Sketch there:
     the squares are drawn at the component's origin with the same colours and labels, a
     click on its XY square opens the sketch in the component's body; Esc.
"""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import direct_steps as d
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import primitive_input as pi
from SciForgeTests.gui import timeline_input as t

V = App.Vector
state = {}


def look():
    from sciforge import origin_look

    return origin_look


def picker():
    """The origin squares on show (Create Sketch, Construct, a primitive), or None."""
    from sciforge import sketch_ui, taskui

    for dialog in (taskui.current(), getattr(Gui.Control.activeDialog(), "__self__", None)):
        if dialog is None:
            continue
        for value in list(vars(dialog).values()) + list(getattr(dialog, "overlays", {}).values()):
            if isinstance(value, sketch_ui.PlanePicker):
                return value
    return None


def texts(root):
    """The SoText2 strings under a coin node."""
    from pivy import coin

    search = coin.SoSearchAction()
    search.setType(coin.SoText2.getClassTypeId())
    search.setInterest(coin.SoSearchAction.ALL)
    search.setSearchingAll(True)  # an axis hidden for now (square to the profile) too
    search.apply(root)
    found = []
    paths = search.getPaths()
    for i in range(paths.getLength()):
        node = paths[i].getTail()
        try:
            found.append(str(node.string.getValues()[0].getString()))
        except Exception:
            found.append(str(node.string.getValues()[0]))
    return found


def same(a, b, tol=1e-3):
    return all(abs(float(x) - float(y)) < tol for x, y in zip(a, b))


def colour(material):
    return tuple(material.diffuseColor.getValues()[0].getValue())


def width(entry):
    return float(entry.line_style.lineWidth.getValue())


def transparency(entry):
    return float(entry.material.transparency.getValues()[0])


def check_squares(where, size):
    p = picker()
    if not h.check("%s: origin squares shown" % where, p is not None):
        return None
    lk = look()
    h.check(
        "%s: XY blue, XZ green, YZ red" % where,
        same(colour(p.looks["XY_Plane"].material), lk.AXIS_RGB["Z"])
        and same(colour(p.looks["XZ_Plane"].material), lk.AXIS_RGB["Y"])
        and same(colour(p.looks["YZ_Plane"].material), lk.AXIS_RGB["X"]),
        {r: colour(e.material) for r, e in p.looks.items()},
    )
    h.check(
        "%s: see-through" % where,
        all(abs(transparency(e) - lk.IDLE_TRANSPARENCY) < 1e-3 for e in p.looks.values()),
    )
    h.check(
        "%s: labelled XY, XZ, YZ" % where,
        sorted(texts(p.root)) == ["XY", "XZ", "YZ"],
        texts(p.root),
    )
    h.check("%s: %g mm squares" % (where, size), abs(p.size - size) < 1e-6, p.size)
    return p


# -- A ------------------------------------------------------------------------------------------
def a_sketch():
    h.ribbon("Create Sketch")


def a_squares():
    check_squares("empty design", 100.0)
    h.shot("A-squares")


# -- B ------------------------------------------------------------------------------------------
def b_hover():
    h.move(h.screen_point(V(30, -20, 0)))


def b_lit():
    p = picker()
    if p is None:
        return
    lk = look()
    xy, xz = p.looks["XY_Plane"], p.looks["XZ_Plane"]
    h.check(
        "the XY square lights up: brighter, less see-through, thicker outline",
        sum(colour(xy.material)) > sum(lk.AXIS_RGB["Z"]) + 0.1
        and transparency(xy) < lk.IDLE_TRANSPARENCY - 0.1
        and width(xy) > lk.IDLE_OUTLINE,
        (colour(xy.material), transparency(xy), width(xy)),
    )
    h.check("XZ stays idle", same(colour(xz.material), lk.AXIS_RGB["Y"]) and width(xz) == 1.0)
    h.shot("B-hover-xy")
    h.move(QtCore.QPoint(20, 20))  # the empty corner of the view


def b_unlit():
    p = picker()
    if p is None:
        return
    xy = p.looks["XY_Plane"]
    h.check("off the square: idle again", same(colour(xy.material), look().AXIS_RGB["Z"]))
    h.press(QtCore.Qt.Key_Escape)


def b_cancelled():
    sketches = [o for o in App.ActiveDocument.Objects if o.TypeId.startswith("Sketcher")]
    h.check("Esc: no sketch", not sketches, sketches)
    h.check("Esc: the squares are gone", picker() is None)


# -- D ------------------------------------------------------------------------------------------
def d_sketch():
    h.click_empty()
    h.fit()
    h.ribbon("Create Sketch")


def d_squares():
    p = check_squares("with a 20 mm box", 20.0)
    if p is None:
        return
    # the labels go to the corners away from the box (its centre is at 10, 10, 10)
    from pivy import coin

    search = coin.SoSearchAction()
    search.setType(coin.SoTranslation.getClassTypeId())
    search.setInterest(coin.SoSearchAction.ALL)
    search.apply(p.root)
    spots = []
    paths = search.getPaths()
    for i in range(paths.getLength()):
        spots.append(tuple(paths[i].getTail().translation.getValue().getValue()))
    h.check(
        "labels at the corners away from the box",
        len(spots) == 3 and all(sum(c) < 0 for c in spots),
        spots,
    )
    h.shot("D-squares-with-part")
    h.click(V(-12, 0, 5))


def d_outside():
    sk = h.in_sketch()
    h.check("a click beside the smaller square picks nothing", sk is None, sk)
    h.check("Create Sketch still waits", picker() is not None)
    h.click(V(8, 0, -8))


def d_on_xz():
    sk = h.in_sketch()
    ok = sk is not None and sk.AttachmentSupport[0][0].Role == "XZ_Plane"
    where = sk and [(o.Label, getattr(o, "Role", "")) for o, _ in sk.AttachmentSupport]
    h.check("sketch open on XZ", ok, where)
    if ok:
        h.draw_rectangle(sk, 25, 0, 30, 5)


def d_finish():
    h.ribbon("Finish Sketch")


# -- E ------------------------------------------------------------------------------------------
def e_revolve():
    h.click_empty()
    h.fit()
    h.ribbon("Revolve")


def e_axes():
    from sciforge import taskui

    p = taskui.current()
    axes = getattr(p, "axes", None)
    if not h.check("Revolve offers the origin axes", axes is not None, p):
        return
    h.check("axes labelled X, Y, Z", sorted(texts(axes.root)) == ["X", "Y", "Z"], texts(axes.root))
    lk = look()
    kinds = {line[1]: colour(line[5]) for line in axes.lines if line[1] in "XYZ"}
    h.check(
        "X red, Y green, Z blue",
        all(same(kinds.get(k, ()), lk.AXIS_RGB[k]) for k in "XYZ"),
        kinds,
    )
    h.shot("E-revolve-axes")
    h.press(QtCore.Qt.Key_Escape)


def e_closed():
    from sciforge import taskui

    h.check("Esc closed Revolve", taskui.current() is None)


# -- F ------------------------------------------------------------------------------------------
def f_offset_plane():
    h.click_empty()
    h.fit()
    h.ribbon("Offset Plane")


def f_squares():
    p = check_squares("Construct", 20.0)
    if p is not None:
        h.move(h.screen_point(V(5, -5, 0)))


def f_lit():
    p = picker()
    if p is None:
        return
    xy = p.looks["XY_Plane"]
    h.check("Construct: the XY square lights up", width(xy) > look().IDLE_OUTLINE, width(xy))
    h.press(QtCore.Qt.Key_Escape)


# -- G ------------------------------------------------------------------------------------------
def g_box():
    h.click_empty()
    h.fit()
    pi.menu("Box")


def g_squares():
    check_squares("Box", 20.0)
    h.press(QtCore.Qt.Key_Escape)


# -- H ------------------------------------------------------------------------------------------
def h_pattern_colours():
    from sciforge import pattern_ui

    lk = look()
    h.check(
        "pattern axes: the same red, green, blue",
        all(same(pattern_ui.AXIS_COLORS[k + "_Axis"], lk.AXIS_RGB[k]) for k in "XYZ"),
        pattern_ui.AXIS_COLORS,
    )


# -- I ------------------------------------------------------------------------------------------
def i_component():
    h.click_empty()
    state["label"] = d.bodies()[0].Label
    t.row_menu(state["label"], "Create Components from Bodies")


def i_move():
    from sciforge import components

    part = components.component_of(d.bodies()[0])
    if not h.check("a component", part is not None):
        return
    part.Placement = App.Placement(V(40, 0, 0), App.Rotation())
    App.ActiveDocument.recompute()
    state["part"] = part.Label
    h.fit()


def i_activate():
    t.row_menu(state.get("part", "?"), "Activate")


def i_sketch():
    h.click_empty()
    h.fit()
    h.ribbon("Create Sketch")


def i_squares():
    p = check_squares("in a component", 20.0)
    if p is not None:
        h.check("squares at the component's origin", same(p.placement.Base, (40, 0, 0)))
        h.click(V(45, -5, 0))


def i_on_xy():
    sk = h.in_sketch()
    ok = sk is not None and sk.AttachmentSupport[0][0].Role == "XY_Plane"
    where = sk and [(o.Label, getattr(o, "Role", "")) for o, _ in sk.AttachmentSupport]
    h.check("sketch open on the component's XY", ok, where)
    h.ribbon("Finish Sketch")


h.run(
    "view_origin_planes",
    [s.new_design("Planes"), a_sketch, a_squares, b_hover, b_lit, b_unlit, b_cancelled]
    + s.box_steps("box", (0, 0, 20, 20), 20, V(30, -20, 0))
    + [
        d_sketch,
        d_squares,
        d_outside,
        d_on_xz,
        d_finish,
        e_revolve,
        e_axes,
        e_closed,
        f_offset_plane,
        f_squares,
        f_lit,
        g_box,
        g_squares,
        h_pattern_colours,
        i_component,
        i_move,
        i_activate,
        i_sketch,
        i_squares,
        i_on_xy,
    ],
)
