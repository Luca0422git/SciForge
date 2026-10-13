# SPDX-License-Identifier: LGPL-2.1-or-later
"""An inserted mesh, its converted body and a canvas survive save and reopen; only real input.

A  Insert Mesh (box STL), OK; MESH > Convert Mesh, click the mesh, OK: a 1000 mm3 body.
   INSERT > Canvas from a copy of canvas.png, click the XY square, OK.
B  Save as reopen.FCStd, delete the picture's copy, close, open the file again: the mesh body
   (12 triangles), the body (1000 mm3, 6 faces), the canvas with a picture file that exists
   (taken from inside the design) and Display Through on; the browser shows Bodies (two rows)
   and Canvases.
C  Browser double-click the canvas: Edit Canvas opens with 50 %; Cancel.
D  Timeline double-click Insert Mesh 1, X Distance 5, OK: the converted body follows (its box
   starts at x = 5), the mesh is hidden still.
E  Ctrl+Z: the body back at x = 0.
"""

import os

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import insert_steps as i
from SciForgeTests.gui import sketch_input as si

V = App.Vector
OUT = os.path.join(i.OUT, "insert_reopen")
state = {}


def mesh():
    found = i.mesh_bodies()
    return found[0] if found else None


def canvas():
    found = i.canvases()
    return found[0] if found else None


def drawn_through(obj):
    from pivy import coin

    root = obj.ViewObject.RootNode
    return (
        root.getNumChildren() == 1
        and root.getChild(0).getTypeId() == coin.SoAnnotation.getClassTypeId()
    )


# -- A ----------------------------------------------------------------------------------------
def a_mesh():
    i.use_file(i.fixture("box_20x10x5.stl"))
    h.fit()
    h.ribbon("Insert Mesh")


def a_mesh_ok():
    h.check("mesh body", mesh() is not None)
    h.task_button("OK")


def a_convert():
    i.ribbon_tab("MESH")
    h.fit()
    h.ribbon("Convert Mesh")


def a_click_mesh():
    h.click(i.mesh_click_point(mesh()))


a_click_mesh.wait_ms = 1500


def a_convert_ok():
    h.check(
        "converted body 1000", len(s.bodies()) == 1 and i.close(s.volume(s.bodies()[0]), 1000.0)
    )
    h.task_button("OK")


def a_canvas():
    state["png"] = i.temp_copy("canvas.png")
    i.use_file(state["png"])
    i.ribbon_tab("SOLID")
    h.fit()
    h.ribbon("Canvas")


def a_click_xy():
    h.click(i.XY_CLICK)


a_click_xy.wait_ms = 1200


def a_canvas_ok():
    c = canvas()
    h.check(
        "canvas made from the copy",
        # FreeCAD keeps the picture inside the design (ImageFile is the saved copy's path)
        c is not None and bool(c.ImageFile) and os.path.isfile(c.ImageFile),
        c and c.ImageFile,
    )
    h.task_button("OK")


# -- B ----------------------------------------------------------------------------------------
def b_save():
    os.makedirs(OUT, exist_ok=True)
    state["file"] = os.path.join(OUT, "reopen.FCStd")
    App.ActiveDocument.saveAs(state["file"])
    h.check("saved", os.path.isfile(state["file"]))


def b_close_and_reopen():
    os.remove(state["png"])
    App.closeDocument(App.ActiveDocument.Name)
    App.openDocument(state["file"])
    h.fit()


b_close_and_reopen.wait_ms = 2500


def b_check():
    m = mesh()
    h.check("mesh body back", m is not None and m.Mesh.CountFacets == 12, m and m.Mesh.CountFacets)
    bodies = s.bodies()
    h.check(
        "converted body back: 1000, 6 faces",
        bodies and i.close(s.volume(bodies[0]), 1000.0) and len(bodies[0].Shape.Faces) == 6,
    )
    c = canvas()
    h.check("canvas back", c is not None)
    if c is not None:
        h.check(
            "its picture exists (from inside the design)",
            bool(c.ImageFile) and os.path.isfile(c.ImageFile),
            c.ImageFile,
        )
        h.check("Display Through back on", drawn_through(c))
        h.check("50 % opacity kept", c.ViewObject.Transparency == 50, c.ViewObject.Transparency)
    labels = i.browser_labels()
    h.check("browser: Bodies and Canvases", "Bodies" in labels and "Canvases" in labels, labels)
    h.check(
        "browser lists the mesh body and the solid",
        i.browser_has("box_20x10x5") and i.browser_has("(solid)"),
        labels,
    )


# -- C ----------------------------------------------------------------------------------------
def c_edit():
    si.browser_double_click("canvas")


c_edit.wait_ms = 1200


def c_check():
    p = i.panel()
    h.check("Edit Canvas after reopen", p is not None and p.title == "Edit Canvas", p and p.title)
    if p is not None:
        h.check("50 % shown", p.opacity.value() == 50, p.opacity.value())
        h.task_button("Cancel")


# -- D ----------------------------------------------------------------------------------------
def d_edit_mesh():
    s.timeline_double_click(mesh())


d_edit_mesh.wait_ms = 1200


def d_move():
    p = i.panel()
    h.check(
        "Insert Mesh dialog after reopen", p is not None and p.title == "Insert Mesh", p and p.title
    )
    if p is not None:
        i.type_value(p.x, "5")


def d_ok():
    h.task_button("OK")


d_ok.wait_ms = 1500


def d_check():
    bodies = s.bodies()
    xmin = bodies[0].Shape.BoundBox.XMin if bodies else None
    h.check(
        "the converted body follows the mesh (x from 5)",
        xmin is not None and abs(xmin - 5) < 1e-6,
        xmin,
    )
    m = mesh()
    h.check("the mesh stays hidden", m is not None and not s.shown(m))


# -- E ----------------------------------------------------------------------------------------
def e_undo():
    i.undo()


def e_check():
    bodies = s.bodies()
    xmin = bodies[0].Shape.BoundBox.XMin if bodies else None
    h.check("Ctrl+Z: body back at x = 0", xmin is not None and abs(xmin) < 1e-6, xmin)
    i.no_file()
    h.shot("end")
    Gui.Selection.clearSelection()


h.run(
    "insert_reopen",
    [
        i.new_design("Reopen"),
        a_mesh,
        a_mesh_ok,
        a_convert,
        a_click_mesh,
        a_convert_ok,
        a_canvas,
        a_click_xy,
        a_canvas_ok,
        b_save,
        b_close_and_reopen,
        b_check,
        c_edit,
        c_check,
        d_edit_mesh,
        d_move,
        d_ok,
        d_check,
        e_undo,
        e_check,
    ],
)
