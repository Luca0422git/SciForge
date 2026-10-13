# SPDX-License-Identifier: LGPL-2.1-or-later
"""Shared helpers for the MESH tab scenarios (scenarios/mesh_*.py). Everything acts like a
person: ribbon buttons and menus, clicks on the 3D view, the browser and the timeline,
typing into fields. The test meshes are written as STL files by the scenario itself (a
broken box with a hole, flipped and doubled faces; two boxes in one file; a sphere...) and
inserted with INSERT > Insert Mesh (the file dialog's answer is given beforehand, as in the
insert scenarios)."""

import math
import os

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtWidgets

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import bodies_steps as s
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import insert_steps as i

V = App.Vector
OUT = h.OUT_DIR


# -- test meshes -------------------------------------------------------------------------------
def box_triangles(x0=0.0, y0=0.0, z0=0.0, x1=20.0, y1=10.0, z1=5.0):
    """The 12 triangles of a box, facing out."""
    p = [
        (x0, y0, z0),
        (x1, y0, z0),
        (x1, y1, z0),
        (x0, y1, z0),
        (x0, y0, z1),
        (x1, y0, z1),
        (x1, y1, z1),
        (x0, y1, z1),
    ]
    quads = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    tris = []
    for a, b_, c, d in quads:
        tris.append((p[a], p[b_], p[c]))
        tris.append((p[a], p[c], p[d]))
    return tris


def sphere_triangles(r=10.0, n=24, centre=(0.0, 0.0, 0.0)):
    cx, cy, cz = centre
    rows = []
    for k in range(n + 1):
        th = math.pi * k / n
        row = []
        for j in range(2 * n):
            ph = math.pi * j / n
            row.append(
                (
                    cx + r * math.sin(th) * math.cos(ph),
                    cy + r * math.sin(th) * math.sin(ph),
                    cz + r * math.cos(th),
                )
            )
        rows.append(row)
    tris = []
    m = 2 * n
    for k in range(n):
        for j in range(m):
            a, b_ = rows[k][j], rows[k][(j + 1) % m]
            c, d = rows[k + 1][j], rows[k + 1][(j + 1) % m]
            if k > 0:
                tris.append((a, c, b_))
            if k < n - 1:
                tris.append((b_, c, d))
    return tris


def _normal(t):
    (ax, ay, az), (bx, by, bz), (cx, cy, cz) = t
    ux, uy, uz = bx - ax, by - ay, bz - az
    vx, vy, vz = cx - ax, cy - ay, cz - az
    nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    size = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
    return nx / size, ny / size, nz / size


def write_stl(name, triangles):
    """An ASCII STL in the scenario's output folder; returns its path. STL repeats every
    corner on each triangle (the 'duplicated points' every STL has)."""
    path = os.path.join(OUT, name)
    with open(path, "w") as handle:
        handle.write("solid %s\n" % os.path.splitext(name)[0])
        for t in triangles:
            handle.write("  facet normal %g %g %g\n    outer loop\n" % _normal(t))
            for x, y, z in t:
                handle.write("      vertex %.6f %.6f %.6f\n" % (x, y, z))
            handle.write("    endloop\n  endfacet\n")
        handle.write("endsolid\n")
    return path


def broken_box_stl(name="broken_box.stl"):
    """A 20 x 10 x 5 box with a hole (a bottom triangle missing), two triangles facing the
    wrong way and one triangle doubled: what downloaded STLs look like."""
    tris = box_triangles()
    tris = tris[1:]  # the hole
    tris[2] = (tris[2][0], tris[2][2], tris[2][1])  # flipped
    tris[6] = (tris[6][0], tris[6][2], tris[6][1])  # flipped
    tris.append(tris[8])  # doubled
    return write_stl(name, tris)


# -- inserting -------------------------------------------------------------------------------
def insert_file(path):
    """INSERT > Insert Mesh with this file (the file dialog answers it), then OK."""

    def open_dialog():
        i.use_file(path)
        h.ribbon("Insert Mesh")

    open_dialog.__name__ = "insert_" + os.path.splitext(os.path.basename(path))[0]

    def ok():
        p = i.panel()
        h.check("Insert Mesh dialog for %s" % os.path.basename(path),
                p is not None and p.title == "Insert Mesh", p)
        h.task_button("OK")
        i.no_file()

    ok.__name__ = "insert_ok_" + os.path.splitext(os.path.basename(path))[0]
    ok.wait_ms = 1000
    return [open_dialog, ok]


# -- the design --------------------------------------------------------------------------------
def doc():
    return App.ActiveDocument


def mesh_objects():
    d = doc()
    return [o for o in d.Objects if o.TypeId in ("Mesh::Feature", "Mesh::FeaturePython")] if d else []


def bodies():
    """The mesh bodies the browser lists (no later step uses them up), in creation order."""
    from sciforge import mesh

    return sorted(mesh.mesh_bodies(doc()), key=lambda o: o.ID)


def body(label):
    for obj in bodies():
        if obj.Label == label:
            return obj
    return None


def steps(kind):
    d = doc()
    return [o for o in d.Objects if getattr(o, "SciForgeType", "") == kind] if d else []


def panel():
    from sciforge import taskui

    return taskui.current()


def analysis(obj):
    from sciforge import mesh

    return mesh.analyze(mesh.global_mesh(obj))


def facets(obj):
    return obj.Mesh.CountFacets if obj is not None else None


def volume(obj):
    from sciforge import mesh

    return mesh.global_mesh(obj).Volume


def closed(obj):
    return bool(obj is not None and analysis(obj)["closed"])


def shown(obj):
    return obj is not None and s.shown(obj)


def click_body(obj, where=None):
    """Click a mesh body on its top (or at `where`)."""
    h.click(where if where is not None else i.mesh_click_point(obj))


def timeline_title(obj):
    return i.timeline_kind_title(obj)


def timeline_display(obj):
    return s.timeline_title_of(obj)


def browser_node(label):
    tree = s.browser()
    if tree is None:
        return None
    item = tree.row(label)
    if item is None:
        return None
    from sciforge import browser_ui

    return item.data(1, browser_ui.ROLE_NODE)


def browser_labels():
    return i.browser_labels()


def choose(combo, text):
    b.choose(combo, text)
    QtWidgets.QApplication.processEvents()


def tick(checkbox, on):
    i.set_check(checkbox, on)


def set_spin(spin, value):
    i.set_spin(spin, value)


def type_field(field, text):
    i.type_value(field, text)


def mesh_tab():
    i.ribbon_tab("MESH")


def view_direction():
    return Gui.ActiveDocument.ActiveView.getViewDirection()


def step(fn, ms=None, name=None):
    """A scenario step that waits `ms` after it (mesh work takes a moment)."""
    if ms is not None:
        fn.wait_ms = ms
    if name:
        fn.__name__ = name
    return fn
