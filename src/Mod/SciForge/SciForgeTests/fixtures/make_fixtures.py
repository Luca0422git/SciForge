# SPDX-License-Identifier: LGPL-2.1-or-later
"""Makes the small input files the insert / export tests use (run inside FreeCAD's GUI):

    xvfb-run freecad SciForgeTests/fixtures/make_fixtures.py

Every file is tiny and hand-checkable:
  box_20x10x5.stl      a 20 x 10 x 5 mm box, 12 triangles, binary STL (1000 mm3)
  box_20x10x5.obj      the same box as OBJ
  box_20x10x5.3mf      the same box as 3MF
  cylinder_r5_h10.stl  a cylinder, radius 5, height 10, Medium refinement (about 785 mm3)
  two_parts.step       "Plate" 40 x 30 x 5 (blue) and "Peg" radius 5, height 15 on it (red)
  shape.svg            a 30 x 20 mm rectangle with a 10 mm hole, in mm (hand-written; no
                       stroke attributes: FreeCAD's importer misplaces a circle that has them)
  plate.dxf            the same drawing in two layers, "Outline" and "Holes"
  canvas.png           an 80 x 40 picture with two blue dots 60 px apart (calibration)
"""

import os
import sys

import FreeCAD as App
import Import
import MeshPart
import Part

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[-1] if len(sys.argv) > 1 and os.path.isdir(sys.argv[-1]) else HERE

SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="40mm" height="30mm" viewBox="0 0 40 30">
  <rect x="5" y="5" width="30" height="20" fill="none"/>
  <circle cx="20" cy="15" r="5" fill="none"/>
</svg>
"""


def mesh(shape, linear=0.05, angular=0.3):
    return MeshPart.meshFromShape(
        Shape=shape, LinearDeflection=linear, AngularDeflection=angular, Relative=False
    )


def make_meshes():
    box = mesh(Part.makeBox(20, 10, 5), 0.1, 0.5)
    box.write(os.path.join(OUT, "box_20x10x5.stl"), "STL")
    box.write(os.path.join(OUT, "box_20x10x5.obj"), "OBJ")
    box.write(os.path.join(OUT, "box_20x10x5.3mf"), "3MF", "box")
    cylinder = mesh(Part.makeCylinder(5, 10))
    cylinder.write(os.path.join(OUT, "cylinder_r5_h10.stl"), "STL")
    print("[fixtures] meshes: box %d facets, cylinder %d" % (box.CountFacets, cylinder.CountFacets))


def make_step():
    doc = App.newDocument("Fixture")
    plate = doc.addObject("Part::Feature", "Plate")
    plate.Shape = Part.makeBox(40, 30, 5)
    plate.Label = "Plate"
    peg = doc.addObject("Part::Feature", "Peg")
    peg.Shape = Part.makeCylinder(5, 15, App.Vector(20, 15, 5))
    peg.Label = "Peg"
    doc.recompute()
    writer = Import
    if App.GuiUp:
        import ImportGui

        plate.ViewObject.ShapeColor = (0.2, 0.4, 0.9)
        peg.ViewObject.ShapeColor = (0.9, 0.3, 0.2)
        writer = ImportGui
    path = os.path.join(OUT, "two_parts.step")
    writer.export([plate, peg], path)
    App.closeDocument(doc.Name)
    with open(path, errors="replace") as handle:
        text = handle.read()
    print("[fixtures] STEP: %d colours" % text.count("COLOUR_RGB"))


def make_svg():
    with open(os.path.join(OUT, "shape.svg"), "w", encoding="utf-8") as handle:
        handle.write(SVG)


def make_dxf():
    import importDXF

    doc = App.newDocument("FixtureDxf")
    outline = doc.addObject("Part::Feature", "Outline")
    outline.Shape = Part.makePolygon(
        [
            App.Vector(5, 5, 0),
            App.Vector(35, 5, 0),
            App.Vector(35, 25, 0),
            App.Vector(5, 25, 0),
            App.Vector(5, 5, 0),
        ]
    )
    outline.Label = "Outline"
    hole = doc.addObject("Part::Feature", "Holes")
    hole.Shape = Part.Wire(Part.makeCircle(5, App.Vector(20, 15, 0)))
    hole.Label = "Holes"
    doc.recompute()
    importDXF.export([outline, hole], os.path.join(OUT, "plate.dxf"))
    App.closeDocument(doc.Name)


def make_png():
    from PySide import QtGui

    w, h = 80, 40
    img = QtGui.QImage(w, h, QtGui.QImage.Format_ARGB32)
    img.fill(QtGui.QColor(245, 240, 200))
    painter = QtGui.QPainter(img)
    painter.setPen(QtGui.QColor(200, 30, 30))
    painter.drawRect(1, 1, w - 3, h - 3)
    painter.setPen(QtGui.QColor(30, 30, 200))
    painter.setBrush(QtGui.QColor(30, 30, 200))
    painter.drawEllipse(10 - 3, 20 - 3, 6, 6)  # centre (10, 20)
    painter.drawEllipse(70 - 3, 20 - 3, 6, 6)  # centre (70, 20): 60 px apart
    painter.end()
    img.save(os.path.join(OUT, "canvas.png"))


def main():
    make_meshes()
    make_step()
    make_svg()
    make_dxf()
    if App.GuiUp:
        make_png()
    print("[fixtures] written to %s" % OUT)


if __name__ == "__main__" or App.GuiUp:
    main()
    if App.GuiUp:
        from PySide import QtCore, QtWidgets

        QtCore.QTimer.singleShot(300, QtWidgets.QApplication.instance().quit)
