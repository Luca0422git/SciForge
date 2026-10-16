# SPDX-License-Identifier: LGPL-2.1-or-later
"""A decal goes with its component: made into a component, moved with Move/Copy (Components),
dragged with Component Drag, its body dragged into another component; only real input.
docs/sciforge/parity/misc.md, Decal (Luca: "decals dont follow their faces when moved").

Bodies: a box 40 x 30 x 10 (Body) and a cylinder r 10, 40 high at x 100 (Body001).

K1 A decal on the box's top while the box is at the root; right-click the box > Create
   Components from Bodies: the decal goes into the new component with its body (the
   browser lists it there) and stays where it is.
K2 M, Move Object Components, click the box, X Distance 25, Capture Position, OK: the
   decal moves with the component; Ctrl+Z puts both back, Ctrl+Y moves both again.
K3 M on the component again, Z Angle 90 (not captured): the decal turns with it.
K4 The cylinder made a component, a decal laid on its side inside it; Component Drag (top
   view, a drag on the cylinder): the wrapped decal goes with it, wrapped round it.
K5 The box body dragged in the browser onto the cylinder's component: its decal goes along
   (in that component now) and stays on the box's top where it is in the design.
K6 Can's row, Ctrl+C, Ctrl+V: a linked copy Can:2, Move opens on it, X Distance 60, OK: both
   pictures are drawn on the copy too (a decal belongs to its component). Move the copy
   (its row, M, Y Distance 30): the pictures go with it at once; Esc: back with it. Its eye
   off: the copy's pictures go; on: back.
"""

import FreeCAD as App
from PySide import QtCore, QtWidgets

from SciForgeTests.gui import component2_steps as c
from SciForgeTests.gui import component_steps as cs
from SciForgeTests.gui import fixdecal_steps as f
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import timeline_input as t

V = App.Vector
st = {}


def doc():
    return App.ActiveDocument


def body(key):
    return doc().getObject(st[key])


def part_of(obj):
    from sciforge import components

    return components.container_of(obj)


def global_of(obj):
    return obj.getGlobalPlacement()


def setup():
    st.update(f.box_and_cylinder("DecalComponents"))


# -- K1 ----------------------------------------------------------------------------------------
def k1_check_decal():
    obj = f.flat()
    h.check("K1 a decal on the box at the root", obj is not None and part_of(obj) is None)
    st["k1"] = f.snapshot(obj)
    st["box_label"] = body("box").Label
    t.row_menu(st["box_label"], "Create Components from Bodies")


k1_check_decal.wait_ms = 1500


def k1_rename():
    cs.rename_row(st["box_label"], "Box")  # the component is named after its body at first


k1_rename.wait_ms = 1200


def k1_check():
    obj = f.flat()
    part = part_of(body("box"))
    h.check(
        "K1 the box is in a component now", part is not None and part.Label == "Box", c.labels()
    )
    h.check(
        "K1 its decal went into the component with it",
        obj is not None and part is not None and part_of(obj) is part,
        obj and part_of(obj),
    )
    st["part"] = part.Name if part is not None else None
    labels = c.browser_labels()
    h.check("K1 the browser lists the decal", obj is not None and obj.Label in labels, labels)
    f.follows("K1 it stayed where it was", obj, st["k1"], App.Placement())


# -- K2 ----------------------------------------------------------------------------------------
def k2_press_m():
    h.click_empty()
    h.fit()
    h.press("m")


k2_press_m.wait_ms = 1200


def k2_components():
    p = c.panel()
    if h.check("K2 Move/Copy open", p is not None and p.title == "Move/Copy", p):
        c.choose(p.move_object, "Components", closes=True)


k2_components.wait_ms = 1500


def k2_click():
    h.check("K2 the components dialog", c.component_panel() is not None, c.panel())
    h.click(f.TOP)


k2_click.wait_ms = 1200


def k2_type():
    p = c.component_panel()
    part = doc().getObject(st["part"])
    if not h.check(
        "K2 the component picked", p is not None and p.options.get("components") == [part]
    ):
        return
    st["k2_before"] = App.Placement(global_of(part))
    c.type_value(p, "dx", "25")
    c.toggle(p.capture)


k2_type.wait_ms = 1500


def k2_live():
    part = doc().getObject(st["part"])
    place = global_of(part).multiply(st["k2_before"].inverse())
    h.check("K2 the component moved 25", abs(place.Base.x - 25) < 1e-6, place)
    f.follows("K2 while the dialog is open", f.flat(), st["k1"], place)
    h.task_button("OK")


k2_live.wait_ms = 1200


def k2_ok():
    part = doc().getObject(st["part"])
    h.check("K2 a captured Move step", len(c.moves()) == 1, c.moves())
    place = global_of(part).multiply(st["k2_before"].inverse())
    f.follows("K2 after OK", f.flat(), st["k1"], place)
    h.shot("K2-moved")
    h.press(QtCore.Qt.Key_Z, QtCore.Qt.ControlModifier)


k2_ok.wait_ms = 1500


def k2_undone():
    part = doc().getObject(st["part"])
    h.check("K2 Ctrl+Z: the component is back", global_of(part).isSame(st["k2_before"], 1e-9))
    f.follows("K2 Ctrl+Z", f.flat(), st["k1"], App.Placement())
    h.press(QtCore.Qt.Key_Y, QtCore.Qt.ControlModifier)


k2_undone.wait_ms = 1500


def k2_redone():
    part = doc().getObject(st["part"])
    place = global_of(part).multiply(st["k2_before"].inverse())
    h.check("K2 Ctrl+Y: moved again", abs(place.Base.x - 25) < 1e-6, place)
    f.follows("K2 Ctrl+Y", f.flat(), st["k1"], place)


# -- K3 ----------------------------------------------------------------------------------------
def k3_press_m():
    part = doc().getObject(st["part"])
    st["k3_before"] = App.Placement(global_of(part))
    st["k3"] = f.snapshot(f.flat())
    h.click_empty()
    h.fit()
    h.press("m")


k3_press_m.wait_ms = 1200


def k3_components():
    p = c.panel()
    if h.check("K3 Move/Copy open", p is not None, p):
        c.choose(p.move_object, "Components", closes=True)


k3_components.wait_ms = 1500


def k3_click():
    h.click(V(45, 15, 10))  # the box's top, 25 to the right now


k3_click.wait_ms = 1200


def k3_type():
    p = c.component_panel()
    part = doc().getObject(st["part"])
    if not h.check(
        "K3 the component picked", p is not None and p.options.get("components") == [part]
    ):
        return
    c.type_value(p, "rz", "90")


k3_type.wait_ms = 1500


def k3_ok():
    h.task_button("OK")


k3_ok.wait_ms = 1500


def k3_check():
    part = doc().getObject(st["part"])
    place = global_of(part).multiply(st["k3_before"].inverse())
    h.check("K3 the component turned 90", abs(place.Rotation.Angle - 1.5707963) < 1e-6, place)
    h.check("K3 not captured: no new step", len(c.moves()) == 1, c.moves())
    f.follows("K3 the decal turned with it", f.flat(), st["k3"], place)
    h.shot("K3-turned")


# -- K4 ----------------------------------------------------------------------------------------
def k4_component():
    t.row_menu(body("cyl").Label, "Create Components from Bodies")


k4_component.wait_ms = 1500


def k4_rename():
    cs.rename_row(body("cyl").Label, "Can")


k4_rename.wait_ms = 1200


k4_decal = f.decal_steps("k4_wrapped", f.SIDE)


def k4_top_view():
    obj = f.wrapped()
    cyl_part = part_of(body("cyl"))
    st["cyl_part"] = cyl_part.Name if cyl_part is not None else None
    h.check(
        "K4 the wrapped decal is in the cylinder's component",
        obj is not None and cyl_part is not None and part_of(obj) is cyl_part,
        obj and part_of(obj),
    )
    if obj is None or cyl_part is None:
        return
    st["k4"] = f.snapshot(obj)
    st["k4_before"] = App.Placement(global_of(cyl_part))
    h.view().viewTop()
    h.view().fitAll()
    QtWidgets.QApplication.processEvents()


k4_top_view.wait_ms = 800


def k4_drag():
    # press on the cylinder's top (z 40) and drag 20 mm in -Y, in the plane facing the view
    h.drag(h.screen_point(V(103, 3, 40)), h.screen_point(V(103, -17, 40)), steps=16)


k4_drag.wait_ms = 1500


def k4_check():
    from sciforge import joints_drag

    cyl_part = doc().getObject(st["cyl_part"])
    place = global_of(cyl_part).multiply(st["k4_before"].inverse())
    last = joints_drag.last() or {}
    h.check("K4 Component Drag moved the cylinder", place.Base.Length > 5, (place, last))
    obj = f.wrapped()
    f.follows("K4 the wrapped decal went with it", obj, st["k4"], place)
    axis_point = global_of(cyl_part).multVec(V(100, 0, 0))
    radii = f.radii(obj, axis_point, V(0, 0, 1)) if obj is not None else []
    h.check(
        "K4 still wrapped round it (10 mm from its axis)",
        radii and min(radii) > 9.95 and max(radii) < 10.1,
        radii and (min(radii), max(radii)),
    )
    h.shot("K4-dragged")
    h.fit()


k4_check.wait_ms = 800


# -- K5 ----------------------------------------------------------------------------------------
def k5_drag_row():
    st["k5"] = f.snapshot(f.flat())
    cyl_part = doc().getObject(st["cyl_part"])
    cs.drag_row(st["box_label"], cyl_part.Label)


k5_drag_row.wait_ms = 1500


def k5_check():
    cyl_part = doc().getObject(st["cyl_part"])
    obj = f.flat()
    h.check("K5 the box went into the cylinder's component", part_of(body("box")) is cyl_part)
    h.check(
        "K5 its decal went along",
        obj is not None and part_of(obj) is cyl_part,
        obj and part_of(obj),
    )
    f.follows("K5 the decal stayed on the box's top", obj, st["k5"], App.Placement())
    h.shot("K5-row")


# -- K6 ----------------------------------------------------------------------------------------
def can_copy():
    return c.part("Can:2")


def copies_on(tag, part):
    """Checks: each decal is drawn once more, on the copy `part`'s bodies."""
    shape = c.shape(part)
    for obj in (f.flat(), f.wrapped()):
        if obj is None:
            h.check("%s: the decals are there" % tag, False)
            continue
        drawn = f.copy_points(obj)
        h.check(
            "%s: %s drawn once on the copy" % (tag, obj.Label),
            obj.ViewObject.Proxy.copies_drawn() == 1 and len(drawn) == 1,
            (obj.ViewObject.Proxy.copies_drawn(), len(drawn)),
        )
        gap = f.gap_to(shape, drawn[0]) if drawn else None
        h.check(
            "%s: %s on the copy's faces" % (tag, obj.Label), gap is not None and gap < 0.06, gap
        )


def k6_select():
    st["k6"] = f.snapshot(f.flat())
    h.click_empty()
    t.click_row("Can")


k6_select.wait_ms = 800


def k6_copy():
    h.press(QtCore.Qt.Key_C, QtCore.Qt.ControlModifier)


def k6_paste():
    h.press(QtCore.Qt.Key_V, QtCore.Qt.ControlModifier)


k6_paste.wait_ms = 2000


def k6_move():
    p = c.component_panel()
    copy = can_copy()
    if h.check("K6 Move opens on the pasted Can:2", p is not None and copy is not None, c.labels()):
        c.type_value(p, "dx", "60")


k6_move.wait_ms = 1500


def k6_ok():
    h.task_button("OK")


k6_ok.wait_ms = 1500


def k6_check():
    copy = can_copy()
    if not h.check("K6 Can:2 is there", copy is not None, c.labels()):
        return
    copies_on("K6", copy)
    f.follows("K6 the original's decal did not move", f.flat(), st["k6"], App.Placement())
    h.shot("K6-copy")
    h.click_empty()
    t.click_row("Can:2")


k6_check.wait_ms = 800


def k6_press_m():
    h.press("m")


k6_press_m.wait_ms = 1500


def k6_move_copy():
    p = c.component_panel()
    copy = can_copy()
    if h.check("K6 Move on Can:2", p is not None and p.options.get("components") == [copy], p):
        c.type_value(p, "dy", "30")


k6_move_copy.wait_ms = 1500


def k6_moved():
    copies_on("K6 moved", can_copy())
    h.press(QtCore.Qt.Key_Escape)  # Esc puts the copy back where it was


k6_moved.wait_ms = 1500


def k6_back():
    copies_on("K6 Esc: back", can_copy())
    t.click_eye("Can:2")


k6_back.wait_ms = 1200


def k6_hidden():
    for obj in (f.flat(), f.wrapped()):
        h.check(
            "K6 the copy hidden: %s not drawn on it" % obj.Label,
            obj.ViewObject.Proxy.copies_drawn() == 0,
            obj.ViewObject.Proxy.copies_drawn(),
        )
    t.click_eye("Can:2")


k6_hidden.wait_ms = 1200


def k6_shown():
    copies_on("K6 shown again", can_copy())


def cleanup():
    f.forget_picture()
    for name in list(App.listDocuments()):
        App.closeDocument(name)
    h.new_errors()


h.run(
    "fixdecal_components",
    [setup]
    + f.decal_steps("k1_flat", f.TOP)
    + [
        k1_check_decal,
        k1_rename,
        k1_check,
        k2_press_m,
        k2_components,
        k2_click,
        k2_type,
        k2_live,
        k2_ok,
        k2_undone,
        k2_redone,
        k3_press_m,
        k3_components,
        k3_click,
        k3_type,
        k3_ok,
        k3_check,
        k4_component,
        k4_rename,
    ]
    + k4_decal
    + [
        k4_top_view,
        k4_drag,
        k4_check,
        k5_drag_row,
        k5_check,
        k6_select,
        k6_copy,
        k6_paste,
        k6_move,
        k6_ok,
        k6_check,
        k6_press_m,
        k6_move_copy,
        k6_moved,
        k6_back,
        k6_hidden,
        k6_shown,
        cleanup,
    ],
)
