# SPDX-License-Identifier: LGPL-2.1-or-later
"""Physical Material and Appearance (Modify menu), only real input.

Body = box 0..40 x 0..30 x 10 (12000 mm3).

Physical Material
  A  nothing selected, Modify > Physical Material: "In This Design" says Steel (default),
     the mass shown is 12000 mm3 x 7.9 g/cm3 = 94.80 g. Click Aluminium, click the body: it is
     aluminium (FreeCAD's Aluminum-Generic), mass 32.40 g, it looks satin aluminium. OK. Ctrl+Z
     gives FreeCAD's Default back, Ctrl+Y aluminium again.
  B  body selected first, Physical Material, click ABS Plastic: taken at once (12.72 g);
     Cancel: still aluminium.
Appearance
  C  nothing selected, Modify > Appearance, click "Glossy plastic, red", click the body: red.
     OK. Ctrl+Z: aluminium's look again; Ctrl+Y: red.
  D  Apply To Faces, "Glossy plastic, blue", click the top face: only that face is blue. OK.
  E  a boss on top (Extrude): the top face is still blue, the rest red (the look follows the
     face through later steps).
  F  custom colour: type #3366CC, Enter, Use, click the body; Cancel: red with the blue face
     again.
"""
import FreeCAD as App
from PySide import QtCore

from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import pattern_steps as ps
from SciForgeTests.gui import widget_input as w

V = App.Vector
RED = (0.80, 0.08, 0.08)
BLUE = (0.10, 0.28, 0.80)
state = {}


def body():
    return s.bodies()[0]


def colors(step=None):
    """Diffuse colours on screen, per face, of the body's end step."""
    step = step or body().Tip
    try:
        return [
            tuple(round(c, 3) for c in m.DiffuseColor[:3]) for m in step.ViewObject.ShapeAppearance
        ]
    except Exception:
        return []


def same(a, b, tol=0.01):
    return a is not None and b is not None and all(abs(x - y) <= tol for x, y in zip(a, b))


def click_item(view, item):
    view.scrollToItem(item)
    w.click(view.viewport(), view.visualItemRect(item).center())


def top_face_index(step=None):
    step = step or body().Tip
    for i, face in enumerate(step.Shape.Faces):
        if (
            face.Surface.TypeId == "Part::GeomPlane"
            and abs(face.CenterOfMass.z - 10) < 1e-6
            and face.Area > 1000
        ):
            return i
    return None


# -- A ----------------------------------------------------------------------------------------
def a_open():
    h.click_empty()
    h.fit()
    s.menu("MODIFY", "Physical Material")


def a_dialog():
    p = s.panel()
    h.check("Physical Material dialog", p is not None and p.title == "Physical Material", p)
    s.no_popups("Physical Material")
    if p is not None:
        rows = [p.design.item(i).text() for i in range(p.design.count())]
        h.check("in this design: Steel (default)", any("Steel (default)" in r for r in rows), rows)
        h.check("steel mass 94.80 g", "94.80 g" in p.masses.text(), p.masses.text())


def a_pick_aluminium():
    p = s.panel()
    if p is not None:
        item = p.item_for("Aluminium")
        if h.check("library has Aluminium", item is not None):
            click_item(p.library, item)


def a_click_body():
    h.click(V(20, 15, 10))


def a_assigned():
    p = s.panel()
    h.check(
        "body is aluminium",
        body().ShapeMaterial.Name == "Aluminum-Generic",
        body().ShapeMaterial.Name,
    )
    if p is not None:
        h.check("mass 32.40 g", "32.40 g" in p.masses.text(), p.masses.text())
    h.check(
        "looks satin aluminium",
        same(colors()[0] if colors() else None, (0.80, 0.81, 0.83)),
        colors(),
    )


def a_ok():
    h.task_button("OK")


def a_mass():
    from sciforge import bodies

    h.check("bodies.mass = 0.0324 kg", s.close(bodies.mass(body()), 0.0324), bodies.mass(body()))


def a_undo():
    s.undo()


def a_undone():
    h.check(
        "undo: FreeCAD's Default", body().ShapeMaterial.Name == "Default", body().ShapeMaterial.Name
    )


def a_redo():
    s.redo()


def a_redone():
    h.check(
        "redo: aluminium",
        body().ShapeMaterial.Name == "Aluminum-Generic",
        body().ShapeMaterial.Name,
    )


# -- B ----------------------------------------------------------------------------------------
def b_select():
    h.click(V(20, 15, 10))


def b_open():
    s.menu("MODIFY", "Physical Material")


def b_pick_abs():
    p = s.panel()
    if h.check("dialog open", p is not None):
        h.check("selected body waits for a material", p.pending == [body()], p.pending)
        click_item(p.library, p.item_for("ABS Plastic"))


def b_assigned():
    p = s.panel()
    h.check(
        "ABS taken at once", body().ShapeMaterial.Name == "ABS-Generic", body().ShapeMaterial.Name
    )
    if p is not None:
        h.check("mass 12.72 g", "12.72 g" in p.masses.text(), p.masses.text())


def b_cancel():
    h.task_button("Cancel")


def b_cancelled():
    h.check(
        "Cancel: aluminium again",
        body().ShapeMaterial.Name == "Aluminum-Generic",
        body().ShapeMaterial.Name,
    )


# -- C ----------------------------------------------------------------------------------------
def c_open():
    h.click_empty()
    s.menu("MODIFY", "Appearance")


def c_pick_red():
    p = s.panel()
    h.check("Appearance dialog", p is not None and p.title == "Appearance", p)
    s.no_popups("Appearance")
    if p is not None:
        item = p.item_for("Glossy plastic, red")
        if h.check("library has red plastic", item is not None):
            click_item(p.library, item)


def c_click_body():
    h.click(V(20, 15, 10))


def c_red():
    cols = colors()
    h.check("body is red", cols and all(same(c, RED) for c in cols), cols)
    h.shot("C-red")


def c_ok():
    h.task_button("OK")


def c_undo():
    s.undo()


def c_undone():
    cols = colors()
    h.check("undo: aluminium look", cols and same(cols[0], (0.80, 0.81, 0.83)), cols)


def c_redo():
    s.redo()


def c_redone():
    cols = colors()
    h.check("redo: red", cols and all(same(c, RED) for c in cols), cols)


# -- D ----------------------------------------------------------------------------------------
def d_open():
    h.click_empty()
    s.menu("MODIFY", "Appearance")


def d_faces():
    from SciForgeTests.gui import blend_steps as b

    p = s.panel()
    if h.check("dialog open", p is not None):
        b.choose(p.apply_to, "Faces")
        click_item(p.library, p.item_for("Glossy plastic, blue"))


def d_click_top():
    h.click(V(30, 20, 10))


def d_blue_top():
    cols = colors()
    top = top_face_index()
    h.check("one colour per face", len(cols) == len(body().Tip.Shape.Faces), cols)
    if top is not None and len(cols) > top:
        h.check("top face blue", same(cols[top], BLUE), cols)
        others = [c for i, c in enumerate(cols) if i != top]
        h.check("other faces red", all(same(c, RED) for c in others), cols)
    h.shot("D-blue-top")


def d_ok():
    h.task_button("OK")


# -- E: a later step --------------------------------------------------------------------------------
def e_check():
    cols = colors()
    top = top_face_index()
    h.check("new end step has colours per face", len(cols) == len(body().Tip.Shape.Faces), cols)
    if top is not None and len(cols) > top:
        h.check("top face still blue after the boss", same(cols[top], BLUE), cols)
        others = [c for i, c in enumerate(cols) if i != top]
        h.check("the boss is red", all(same(c, RED) for c in others), cols)
    h.shot("E-after-boss")


# -- F ----------------------------------------------------------------------------------------
def f_open():
    h.click_empty()
    s.menu("MODIFY", "Appearance")


def f_type_hex():
    p = s.panel()
    if h.check("dialog open", p is not None):
        w.click(p.hex)
        w.key(p.hex, QtCore.Qt.Key_A, QtCore.Qt.ControlModifier)
        w.type_text(p.hex, "#3366CC")
        w.key(p.hex, QtCore.Qt.Key_Return)
        h.check(
            "sliders follow",
            [x.value() for x in p.sliders] == [0x33, 0x66, 0xCC],
            [x.value() for x in p.sliders],
        )
        w.click(p.use_custom)
        h.check("custom look chosen", "#3366CC" in p.chosen.text(), p.chosen.text())


def f_click_body():
    h.click(V(35, 25, 10))


def f_custom():
    cols = colors()
    h.check("body is #3366CC", cols and all(same(c, (0.2, 0.4, 0.8)) for c in cols), cols)


def f_cancel():
    h.task_button("Cancel")


def f_cancelled():
    cols = colors()
    top = top_face_index()
    h.check("Cancel: red again", cols and same(cols[0 if top != 0 else 1], RED), cols)
    if top is not None and len(cols) > top:
        h.check("Cancel: top face blue again", same(cols[top], BLUE), cols)


# -- G: drag and drop ----------------------------------------------------------------------------
def g_open():
    h.click_empty()
    s.menu("MODIFY", "Appearance")


def g_drop_rubber():
    """Drag the black rubber swatch onto the body (the drop events a drag ends with)."""
    from PySide import QtGui, QtWidgets

    from sciforge import appearance_ui

    p = s.panel()
    if not h.check("dialog open", p is not None):
        return
    item = p.item_for("Rubber, black")
    mime = p.library.mimeData([item])
    h.check("a swatch drag carries its look", appearance_ui.look_of(mime) is not None)
    widget = h.gl_widget()
    pos = h.screen_point(V(35, 25, 10))
    actions = QtCore.Qt.CopyAction
    enter = QtGui.QDragEnterEvent(pos, actions, mime, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier)
    QtWidgets.QApplication.sendEvent(widget, enter)
    h.check("the 3D view takes the swatch", enter.isAccepted())
    drop = QtGui.QDropEvent(
        QtCore.QPointF(pos), actions, mime, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier
    )
    QtWidgets.QApplication.sendEvent(widget, drop)
    QtWidgets.QApplication.processEvents()


def g_black():
    cols = colors()
    h.check(
        "dropped: body is black rubber",
        cols and all(same(c, (0.08, 0.08, 0.08)) for c in cols),
        cols,
    )


def g_ok():
    h.task_button("OK")


def g_kept():
    cols = colors()
    h.check("OK: black rubber kept", cols and all(same(c, (0.08, 0.08, 0.08)) for c in cols), cols)


h.run(
    "bodies_look",
    [s.new_design("Look")]
    + s.box_steps("box", (0, 0, 40, 30), 10, V(6, -6, 0))
    + [
        a_open,
        a_dialog,
        a_pick_aluminium,
        a_click_body,
        a_assigned,
        a_ok,
        a_mass,
        a_undo,
        a_undone,
        a_redo,
        a_redone,
        b_select,
        b_open,
        b_pick_abs,
        b_assigned,
        b_cancel,
        b_cancelled,
        c_open,
        c_pick_red,
        c_click_body,
        c_red,
        c_ok,
        c_undo,
        c_undone,
        c_redo,
        c_redone,
        d_open,
        d_faces,
        d_click_top,
        d_blue_top,
        d_ok,
    ]
    + ps.make_boss("boss", (8, 8), 3, 5, V(30, 6, 10))
    + [
        e_check,
        f_open,
        f_type_hex,
        f_click_body,
        f_custom,
        f_cancel,
        f_cancelled,
        g_open,
        g_drop_rubber,
        g_black,
        g_ok,
        g_kept,
    ],
)
