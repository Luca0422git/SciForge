# SPDX-License-Identifier: LGPL-2.1-or-later
"""Surface bodies survive save and reopen, and their steps edit from the timeline, like a
Fusion user, only real input.

An L of walls (sketch lines (0, 0) - (30, 0) - (30, 20) on XY, SURFACE Extrude 10: area
500), saved. Offset both walls 3 (a new surface: 440 inside the L, or 500 + 10 (pi / 2) 3 = 547.12
outside with its rounded corner). Thicken both walls 2 (a new solid body: 960 inside or
1040 outside). Ctrl+S (Enter skips the version description), closed, opened:
the same bodies with the same icons (surface, surface, solid), the same timeline, every
step computed. Double-click "Extrude 1": its curves and distance read back; type 15, OK:
the walls, the offset surface and the solid grow by half (they follow the extrude). Undo /
Redo. Double-click "Thicken 1", Cancel: nothing changes.
"""

import math
import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import surface_steps as st
from SciForgeTests.gui import versions_input as vi

V = App.Vector
s = {}
OFFSETS = (440.0, 500 + 15 * math.pi)
THICK = (960.0, 1040.0)


def doc():
    return App.ActiveDocument


def by_label(label):
    found = doc().getObjectsByLabel(label)
    return found[0] if found else None


def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("SurfaceReopen")
    h.fit()
    h.ribbon("Create Sketch")


def pick_xy():
    st.open_sketch_clicked(V(12, -8, 0))


def draw_l():
    sk = h.in_sketch()
    h.check("sketch open on XY", sk is not None)
    if sk:
        st.add_lines(sk, [(0, 0), (30, 0), (30, 20)])


def finish():
    h.ribbon("Finish Sketch")


def extrude():
    h.fit()
    h.click_empty()
    st.tab("SURFACE")
    st.menu("CREATE", "Extrude")


def click_l():
    h.check("clicked the L", h.click_edge(V(15, 0, 0)))
    st.type_field("distance", "10")


def extrude_ok():
    st.settle()
    body = st.step_body()
    h.check("walls of 500", body is not None and st.near(st.area(body), 500.0), st.area(body))
    s["walls"] = body
    st.ok()


def offset():
    h.fit()
    st.menu("CREATE", "Offset")


def offset_a():
    pl.click_on_plane(V(15, 0, 5))


def offset_b():
    h.click(V(30, 10, 5))


def offset_distance():
    st.settle()
    p = st.panel()
    h.check("two walls", p is not None and len(p.picks["faces"]) == 2, p and p.picks)
    st.type_field("distance", "3")


def offset_ok():
    st.settle()
    body = st.step_body()
    area = st.area(body)
    h.check("an offset surface (440 or 547.12)", any(st.near(area, a, 1e-5) for a in OFFSETS), area)
    s["offset"] = body
    s["offset_area"] = area
    st.ok()


def thicken():
    h.fit()
    st.menu("CREATE", "Thicken")


def thicken_a():
    pl.click_on_plane(V(15, 0, 5))


def thicken_b():
    h.click(V(30, 10, 5))


def thicken_value():
    st.settle()
    st.type_field("thickness", "2")


def thicken_ok():
    st.settle()
    body = st.step_body()
    v = st.volume(body)
    h.check("a solid (960 or 1040)", any(st.near(v, t, 1e-5) for t in THICK), v)
    s["thick"] = body
    s["volume"] = v
    st.ok()


def save_first():
    h.check("dialog closed", st.panel() is None)
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-surface-"), "surface_reopen.FCStd")
    s["path"] = path
    doc().saveAs(path)
    h.check("saved", os.path.isfile(path), path)


def ctrl_s():
    h.check("dialog closed", st.panel() is None)
    s["titles"] = st.timeline_titles()
    s["labels"] = [s[k].Label for k in ("walls", "offset", "thick")]
    h.press(QtCore.Qt.Key_S, QtCore.Qt.ControlModifier)


def describe():
    h.check("the Save dialog asks for a version description", vi.version_dialog() is not None)
    vi.accept_save()


def close():
    h.check("saved (nothing unsaved)", not doc().isTouched())
    App.closeDocument(doc().Name)


def reopen():
    App.openDocument(s["path"])
    h.fit()


def reopened():
    from sciforge import surface

    walls, off, thick = (by_label(x) for x in s["labels"])
    s["walls"], s["offset"], s["thick"] = walls, off, thick
    h.check("the three bodies are back", None not in (walls, off, thick), s["labels"])
    if None in (walls, off, thick):
        return
    h.check(
        "the walls: a surface body, 500",
        surface.is_surface_body(walls) and st.near(st.area(walls), 500.0),
    )
    h.check(
        "the offset: a surface body",
        surface.is_surface_body(off) and st.near(st.area(off), s["offset_area"], 1e-5),
    )
    h.check("the solid", st.near(st.volume(thick), s["volume"], 1e-5), st.volume(thick))
    icons = [st.browser_icon_of(x) for x in (walls, off, thick)]
    h.check(
        "browser icons surface, surface, solid",
        icons == ["surface_body", "surface_body", "box"],
        icons,
    )
    titles = st.timeline_titles()
    h.check("the same timeline", titles == s["titles"], (titles, s["titles"]))
    steps = [x for x in doc().Objects if surface.kind_of(x)]
    h.check(
        "every surface step computed",
        steps and all("Invalid" not in x.State for x in steps),
        [(x.Name, x.State) for x in steps],
    )
    h.check(
        "the steps know they are SciForge's",
        all(type(x.Proxy).__name__ == "SurfaceFeature" for x in steps)
        and all(type(x.ViewObject.Proxy).__name__ == "SurfaceViewProvider" for x in steps),
        [(type(x.Proxy).__name__, type(x.ViewObject.Proxy).__name__) for x in steps],
    )
    h.shot("1-reopened")


def edit_extrude():
    st.tab("SURFACE")
    h.check("double-clicked Extrude 1", st.double_click_timeline("Extrude 1"))


def edit_open():
    st.settle()
    p = st.panel()
    h.check("edit dialog open", p is not None and p.editing and p.kind == "extrude")
    if p is None:
        return
    h.check("the two curves read back", len(p.picks["profile"]) == 2, p.picks["profile"])
    h.check(
        "distance 10 read back", st.near(float(p.options["distance"]), 10.0), p.options["distance"]
    )
    st.type_field("distance", "15")


def edit_ok():
    st.settle()
    st.ok()


def edited():
    h.check("dialog closed", st.panel() is None)
    h.check("the walls 750", st.near(st.area(s["walls"]), 750.0), st.area(s["walls"]))
    h.check(
        "the offset follows",
        st.near(st.area(s["offset"]), 1.5 * s["offset_area"], 1e-5),
        (st.area(s["offset"]), 1.5 * s["offset_area"]),
    )
    h.check(
        "the solid follows",
        st.near(st.volume(s["thick"]), 1.5 * s["volume"], 1e-5),
        (st.volume(s["thick"]), 1.5 * s["volume"]),
    )
    st.undo()


def undone():
    h.check("undo: walls 500", st.near(st.area(s["walls"]), 500.0), st.area(s["walls"]))
    h.check("undo: solid back", st.near(st.volume(s["thick"]), s["volume"], 1e-5))
    st.redo()


def redone():
    h.check("redo: walls 750", st.near(st.area(s["walls"]), 750.0), st.area(s["walls"]))
    h.check("redo: solid grown", st.near(st.volume(s["thick"]), 1.5 * s["volume"], 1e-5))


def edit_thicken():
    h.check("double-clicked Thicken 1", st.double_click_timeline("Thicken 1"))


def thicken_open():
    st.settle()
    p = st.panel()
    h.check("Thicken edit open", p is not None and p.editing and p.kind == "thicken")
    if p is not None:
        h.check(
            "thickness 2 read back",
            st.near(abs(float(p.options["thickness"])), 2.0),
            p.options["thickness"],
        )
    st.cancel()


def cancelled():
    h.check("Cancel closed it", st.panel() is None)
    h.check("nothing changed", st.near(st.volume(s["thick"]), 1.5 * s["volume"], 1e-5))
    h.check("the timeline unchanged", st.timeline_titles() == s["titles"], st.timeline_titles())


h.run(
    "surface_reopen",
    [
        new_design,
        pick_xy,
        draw_l,
        finish,
        extrude,
        click_l,
        extrude_ok,
        save_first,
        offset,
        offset_a,
        offset_b,
        offset_distance,
        offset_ok,
        thicken,
        thicken_a,
        thicken_b,
        thicken_value,
        thicken_ok,
        ctrl_s,
        describe,
        close,
        reopen,
        reopened,
        edit_extrude,
        edit_open,
        edit_ok,
        edited,
        undone,
        redone,
        edit_thicken,
        thicken_open,
        cancelled,
    ],
)
