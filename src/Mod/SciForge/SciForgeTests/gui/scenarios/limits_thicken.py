# SPDX-License-Identifier: LGPL-2.1-or-later
"""SURFACE > Thicken: a thickness past what the faces can take stops at the thickest one
that works (Luca, 2026-10-21; Fusion refuses it, this is Luca's decision). Only real input.

A round wall: a circle of radius 10 on XY, surface-extruded 10 up. Thicken, click the wall:
50 typed one way thickens outward (it fits: pi 10 (60^2 - 10^2)), the other way it would
thicken inward past the axis: it is held just under 10 mm and the note says "50 mm does not
fit: limited to ...". The arrow dragged far inward then stops at that same limit without a
new search (it was found for these faces already). OK: a solid ring wall of that
thickness."""

import math

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import surface_steps as st

V = App.Vector
s = {}
R, H = 10.0, 10.0


def outward(t):
    return math.pi * H * ((R + t) ** 2 - R**2)


def inward(t):
    return math.pi * H * (R**2 - (R - t) ** 2)


def note(p):
    return p.limit_label.text() if p is not None and p.limit_label.isVisible() else ""


def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("LimitsThicken")
    h.fit()
    h.ribbon("Create Sketch")


def pick_xy():
    st.open_sketch_clicked(V(12, -8, 0))


def draw_circle():
    sk = h.in_sketch()
    h.check("sketch open on XY", sk is not None)
    if sk:
        st.add_circle(sk, 0, 0, R)


def finish():
    h.ribbon("Finish Sketch")


def extrude_wall():
    h.fit()
    h.click_empty()
    st.tab("SURFACE")
    st.menu("CREATE", "Extrude")


def click_circle():
    h.check("clicked the circle", h.click_edge(V(0, -R, 0)))  # not on its start vertex


def wall_distance():
    st.type_field("distance", "%g" % H)


def wall_ok():
    st.settle()
    body = st.step_body()
    h.check(
        "a round wall (area 2 pi r h)",
        body is not None and st.near(st.area(body), 2 * math.pi * R * H),
        st.area(body),
    )
    st.ok()


def thicken_menu():
    h.check("wall made", st.panel() is None)
    h.fit()
    st.menu("CREATE", "Thicken")


def click_wall():
    h.click(V(0, -R, 5))


def type_plus_50():
    st.settle()
    p = st.panel()
    h.check("Thicken with the wall picked", p is not None and len(p.picks["faces"]) == 1)
    st.type_field("thickness", "50")


def plus_50():
    st.settle()
    p = st.panel()
    s["plus"] = (p.options["thickness"], note(p), st.volume(st.step_body()))
    st.type_field("thickness", "-50")


plus_50.wait_ms = 2500


def minus_50():
    st.settle()
    p = st.panel()
    s["minus"] = (p.options["thickness"], note(p), st.volume(st.step_body()))
    plus, minus = s["plus"], s["minus"]
    limited = [x for x in (plus, minus) if abs(abs(x[0]) - 50.0) > 1e-9]
    full = [x for x in (plus, minus) if abs(abs(x[0]) - 50.0) <= 1e-9]
    h.check("one way is held at a limit, the other fits", len(limited) == 1 and len(full) == 1, s)
    if len(limited) != 1 or len(full) != 1:
        return
    t, text, v = limited[0]
    s["t"] = t
    h.check("held just under 10 mm (the radius)", 9.0 < abs(t) < 10.0, t)
    typed = "50" if t > 0 else "-50"
    h.check(
        "and said",
        text == "%s mm does not fit: limited to %.2f mm" % (typed, t),
        text,
    )
    h.check("the held wall thickens inward", st.near(v, inward(abs(t)), 1e-5), (v, inward(abs(t))))
    h.check("the other way 50 fits (outward)", st.near(full[0][2], outward(50.0), 1e-5), full[0])
    h.check("no error", "⚠" not in st.message(), st.message())
    s["searches"] = p.limits.searches
    st.type_field("thickness", "%g" % (1.0 if t > 0 else -1.0))


minus_50.wait_ms = 2500


def drag_inward():
    st.settle()
    s["drag"] = st.drag_arrow("thickness", 30.0 if s.get("t", 1) > 0 else -30.0)


drag_inward.wait_ms = 2500


def dragged_inward():
    st.settle()
    p = st.panel()
    t = p.options["thickness"] if p else 0
    h.check("the drag stopped at the same limit", abs(t - s.get("t", 0)) < 1e-9, (t, s.get("t")))
    word = "Largest" if t > 0 else "Furthest"
    h.check("the note", note(p) == "%s that fits here: %.2f mm" % (word, t), note(p))
    h.check(
        "no new search: the limit was known for these faces",
        p is not None and p.limits.searches == s["searches"],
        p and (p.limits.searches, s["searches"]),
    )
    handle = st.handle("thickness")
    h.check(
        "the arrow stopped there too",
        handle is not None and abs(handle.distance() - t) < 1e-6,
        handle and (handle.distance(), t),
    )
    h.shot("1-thicken-held")
    st.ok()


def made():
    h.check("OK worked at once", st.panel() is None and not Gui.Control.activeDialog())
    solids = [b for b in st.bodies() if b.Shape.Solids]
    vols = [b.Shape.Volume for b in solids]
    h.check(
        "a solid ring wall of that thickness",
        any(st.near(v, inward(abs(s.get("t", 0))), 1e-5) for v in vols),
        vols,
    )


h.run(
    "limits_thicken",
    [
        new_design,
        pick_xy,
        draw_circle,
        finish,
        extrude_wall,
        click_circle,
        wall_distance,
        wall_ok,
        thicken_menu,
        click_wall,
        type_plus_50,
        plus_50,
        minus_50,
        drag_inward,
        dragged_inward,
        made,
    ],
)
