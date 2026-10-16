# SPDX-License-Identifier: LGPL-2.1-or-later
"""SURFACE > Revolve Type To and SURFACE > Sweep with a guide rail, a twist and a taper, only
real input.

Create Sketch on XZ: the profile line (10, 0) - (10, 20) and the axis line (0, -3) - (0, 25)
(global Z). Create Sketch on XY: the path (40, 0) - (40, 40) and the rail (50, 0) - (60, 40).
Create Sketch on XY: the sweep profile (40, 0) - (50, 0).
Path R1 (Revolve To a plane): SURFACE > Revolve, click the profile line, click the axis line;
        Type To: the Object box lights up and the origin planes show; click the YZ plane: a
        quarter of a cylinder r 10, h 20 (the plane is a quarter turn either way: the
        positive way). OK: "Revolve 1".
Path R2 (edit): double-click Revolve 1: Type To and the plane read back; click the XZ plane
        (the plane the profile lies on, clicked beside the profile): half a turn. OK.
Path R3 (a refusal, Cancel): Revolve again with Type To and the XY plane, which does not
        contain the axis: the dialog says why and OK waits; Cancel leaves one surface.
Path S1 (Sweep, Path + Guide Rail): SURFACE > Sweep, Type Path + Guide Rail; click the
        profile, the path, the rail: the profile grows to reach the rail, a flat strip 10 ..
        20 wide over 40 (area 600); Profile Scaling None: 10 wide (400); back to Scale. OK.
Path S2 (undo / redo).
Path S3 (edit: Single Path, Twist, Taper): double-click Sweep 1, Single Path: the rail box
        goes; Twist Angle 90: a helicoid strip (area 410.04); Twist 0, Taper Angle 10: the
        strip widens from 10 to 10 + 40 tan 10 (area 541.06); Orientation Parallel greys
        Twist and Taper; Perpendicular again. OK.
Path S4 (Esc): edit again, Taper 20, Esc: still 541.06."""

import math

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import surface_steps as st

V = App.Vector
QUARTER = 2 * math.pi * 10 * 20 / 4.0
HALF = 2 * math.pi * 10 * 20 / 2.0
RAIL = 600.0
PLAIN = 400.0
TAPERED = (10.0 + 10.0 + 40.0 * math.tan(math.radians(10))) / 2.0 * 40.0
_K = (math.pi / 2) / 40.0
HELICOID = 40.0 * (5.0 * math.sqrt(1 + (_K * 10) ** 2) + math.asinh(_K * 10) / (2 * _K))
s = {}


def surface_of(key):
    body = s.get(key)
    return st.area(body) if body is not None else 0.0


# -- the sketches ----------------------------------------------------------------------------------
def new_design():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("Surface2RevolveSweep")
    h.fit()
    h.ribbon("Create Sketch")


def pick_xz():
    st.open_sketch_clicked(V(12, 0, 8))


def draw_revolve():
    sk = h.in_sketch()
    h.check("sketch open on XZ", sk is not None and sk.AttachmentSupport[0][0].Role == "XZ_Plane")
    if sk:
        st.add_lines(sk, [(10, 0), (10, 20)])
        st.add_lines(sk, [(0, -3), (0, 25)])
        s["revolve_sketch"] = sk


def finish_revolve():
    h.ribbon("Finish Sketch")


def path_sketch():
    h.check("left the sketch", h.in_sketch() is None)
    h.fit()
    h.ribbon("Create Sketch")


def pick_xy():
    st.open_sketch_clicked(V(12, -8, 0))


def draw_path_rail():
    sk = h.in_sketch()
    h.check("sketch open on XY", sk is not None and sk.AttachmentSupport[0][0].Role == "XY_Plane")
    if sk:
        st.add_lines(sk, [(40, 0), (40, 40)])
        st.add_lines(sk, [(50, 0), (60, 40)])
        s["path_sketch"] = sk


def finish_path_rail():
    h.ribbon("Finish Sketch")


def profile_sketch():
    h.check("left the path sketch", h.in_sketch() is None)
    h.fit()
    h.ribbon("Create Sketch")


def pick_xy_again():
    st.open_sketch_clicked(V(12, -8, 0))


def draw_profile():
    sk = h.in_sketch()
    h.check("third sketch open", sk is not None)
    if sk:
        st.add_lines(sk, [(40, 0), (50, 0)])
        s["profile_sketch"] = sk


def finish_profile():
    h.ribbon("Finish Sketch")


def surface_tab():
    h.check("left the profile sketch", h.in_sketch() is None)
    h.fit()
    h.click_empty()
    st.tab("SURFACE")


# -- R1: Revolve To a plane ----------------------------------------------------------------------
def r1_revolve():
    st.menu("CREATE", "Revolve")


def r1_types():
    p = st.panel()
    h.check("Revolve dialog open", p is not None and p.kind == "revolve")
    if p is None:
        return
    box = p.rows["type"][0]
    types = [box.itemText(i) for i in range(box.count())]
    h.check("Type: Angle, To, Full", types == ["Angle", "To", "Full"], types)
    h.fit()
    h.check("clicked the profile line", h.click_edge(V(10, 0, 10)))


def r1_axis():
    st.settle()
    p = st.panel()
    h.check(
        "the Axis box takes the next click", p is not None and p.active == "axis", p and p.active
    )
    h.check("clicked the axis line", h.click_edge(V(0, 0, 22)))


def r1_type_to():
    st.settle()
    p = st.panel()
    h.check("the axis is taken", p is not None and len(p.picks["axis"]) == 1, p and p.picks)
    st.choose("type", "To")


def r1_waits():
    st.settle()
    p = st.panel()
    h.check("the Object box is shown", p is not None and p.is_shown("to_object"))
    h.check("and takes the clicks", p is not None and p.active == "to_object", p and p.active)
    h.check("the origin planes show", p is not None and p.planes is not None)
    h.check("Angle is hidden", p is not None and not p.rows["angle"][0].isVisible())
    h.check("nothing built until the object is picked", p is not None and p.step is None)
    h.click(V(0, -12, 8))


def r1_quarter():
    st.settle()
    p = st.panel()
    h.check(
        "the YZ plane is the object",
        p is not None and len(p.picks["to_object"]) == 1,
        p and p.picks,
    )
    s["revolve"] = st.step_body()
    h.check(
        "a quarter of the cylinder (the positive way)",
        st.near(surface_of("revolve"), QUARTER, 1e-5),
        surface_of("revolve"),
    )
    b = s["revolve"].Shape.BoundBox if s.get("revolve") else None
    h.check("from +X round to +Y", b is not None and b.YMin > -1e-6 and b.YMax > 9.99, b)
    h.shot("1-revolve-to")
    st.ok()


def r1_done():
    h.check("dialog closed", st.panel() is None)
    titles = st.timeline_titles()
    h.check("Revolve 1 in the timeline", "Revolve 1" in titles, titles)


# -- R2: edit, To the XZ plane -------------------------------------------------------------------
def r2_edit():
    h.check("double-clicked Revolve 1", st.double_click_timeline("Revolve 1"))


def r2_read_back():
    p = st.panel()
    h.check("edit dialog open", p is not None and p.editing)
    if p is None:
        return
    h.check("Type To read back", p.options["type"] == "to", p.options)
    h.check("the plane read back", len(p.picks["to_object"]) == 1, p.picks)
    st.click_box("to_object")


def r2_click_xz():
    p = st.panel()
    h.check("the Object box takes the clicks", p is not None and p.active == "to_object")
    h.fit()
    h.click(V(16, 0, 4))


def r2_half():
    st.settle()
    h.check(
        "to the profile's own plane: half a turn",
        st.near(surface_of("revolve"), HALF, 1e-5),
        surface_of("revolve"),
    )
    st.ok()


def r2_done():
    h.check("dialog closed", st.panel() is None)
    h.check("kept", st.near(surface_of("revolve"), HALF, 1e-5), surface_of("revolve"))


# -- R3: a refusal, Cancel ---------------------------------------------------------------------
def r3_show_sketch():
    from SciForgeTests.gui import timeline_input as tl

    h.check("eye of the revolve sketch", tl.click_eye(s["revolve_sketch"].Label))


def r3_revolve():
    h.fit()
    h.click_empty()
    st.menu("CREATE", "Revolve")


def r3_profile():
    h.check("Revolve dialog open", st.panel() is not None)
    h.fit()
    h.check("clicked the profile line", h.click_edge(V(10, 0, 4)))


def r3_axis():
    st.settle()
    h.check("clicked the axis line", h.click_edge(V(0, 0, 22)))


def r3_to():
    st.settle()
    st.choose("type", "To")


def r3_click_xy():
    h.fit()
    h.click(V(6, -10, 0))


def r3_refused():
    st.settle()
    p = st.panel()
    text = st.message()
    h.check(
        "the XY plane is picked", p is not None and len(p.picks["to_object"]) == 1, p and p.picks
    )
    h.check("the dialog says why", "contains the axis" in text, text)
    st.ok()


def r3_ok_waits():
    h.check("OK waits", st.panel() is not None)
    st.cancel()


def r3_cancelled():
    h.check("Cancel closed it", st.panel() is None)
    h.check("still one surface", len(st.surface_bodies()) == 1, st.surface_bodies())


# -- S1: Sweep with a guide rail ---------------------------------------------------------------
def s1_show_sketches():
    from sciforge import bodies

    from SciForgeTests.gui import timeline_input as tl

    for key in ("path_sketch", "profile_sketch"):
        if not bodies.is_shown(s[key]):
            tl.click_eye(s[key].Label)


def s1_sweep():
    h.fit()
    h.click_empty()
    st.menu("CREATE", "Sweep")


def s1_rail_type():
    p = st.panel()
    h.check("Sweep dialog open", p is not None and p.kind == "sweep")
    if p is None:
        return
    box = p.rows["type"][0]
    types = [box.itemText(i) for i in range(box.count())]
    h.check("Type: Single Path, Path + Guide Rail", types == ["Single Path", "Path + Guide Rail"])
    st.choose("type", "Path + Guide Rail")


def s1_click_profile():
    p = st.panel()
    h.check("the Guide Rail box is shown", p is not None and p.is_shown("rail"))
    h.check("Profile Scaling shown", p is not None and p.rows["scaling"][0].isVisible())
    h.fit()
    h.check("clicked the profile", h.click_edge(V(45, 0, 0)))


def s1_click_path():
    st.settle()
    p = st.panel()
    h.check("the Path box is next", p is not None and p.active == "path", p and p.active)
    h.check("clicked the path", h.click_edge(V(40, 25, 0)))


def s1_click_rail():
    st.settle()
    p = st.panel()
    h.check("the Guide Rail box is next", p is not None and p.active == "rail", p and p.active)
    h.check("clicked the rail", h.click_edge(V(55, 20, 0)))


def s1_scaled():
    st.settle()
    s["sweep"] = st.step_body()
    h.check(
        "Scale: the profile grows to reach the rail (600)",
        st.near(surface_of("sweep"), RAIL, 1e-5),
        surface_of("sweep"),
    )
    h.shot("2-sweep-rail")
    st.choose("scaling", "None")


def s1_none():
    st.settle()
    h.check(
        "None: the rail only turns it (400)",
        st.near(surface_of("sweep"), PLAIN, 1e-5),
        surface_of("sweep"),
    )
    st.choose("scaling", "Scale")


def s1_ok():
    st.settle()
    h.check("Scale again", st.near(surface_of("sweep"), RAIL, 1e-5), surface_of("sweep"))
    st.ok()


def s1_done():
    h.check("dialog closed", st.panel() is None)
    titles = st.timeline_titles()
    h.check("Sweep 1 in the timeline", "Sweep 1" in titles, titles)


# -- S2: undo / redo ---------------------------------------------------------------------------
def s2_undo():
    st.undo()


def s2_undone():
    h.check("undo takes the sweep away", len(st.surface_bodies()) == 1, st.surface_bodies())


def s2_redo():
    st.redo()


def s2_redone():
    found = [b for b in st.surface_bodies() if b is not s.get("revolve")]
    h.check("redo brings it back", len(found) == 1, found)
    if found:
        s["sweep"] = found[0]
    h.check("600 again", st.near(surface_of("sweep"), RAIL, 1e-5), surface_of("sweep"))


# -- S3: edit: Single Path, Twist, Taper -----------------------------------------------------
def s3_edit():
    h.check("double-clicked Sweep 1", st.double_click_timeline("Sweep 1"))


def s3_single():
    p = st.panel()
    h.check("edit dialog open", p is not None and p.editing)
    if p is None:
        return
    h.check("Path + Guide Rail read back", p.options["type"] == "rail", p.options)
    h.check("the rail read back", len(p.picks["rail"]) == 1, p.picks)
    st.choose("type", "Single Path")


def s3_twist():
    st.settle()
    p = st.panel()
    h.check("the rail box is hidden", p is not None and not p.is_shown("rail"))
    h.check("Twist and Taper shown", p is not None and p.rows["twist"][0].isVisible())
    h.check("the plain strip", st.near(surface_of("sweep"), PLAIN, 1e-5), surface_of("sweep"))
    st.type_field("twist", "90")


def s3_helicoid():
    st.settle()
    h.check(
        "Twist 90: a helicoid strip",
        st.near(surface_of("sweep"), HELICOID, 1e-3),
        (surface_of("sweep"), HELICOID),
    )
    h.shot("3-twist")
    st.type_field("twist", "0")


def s3_taper():
    st.settle()
    st.type_field("taper", "10")


def s3_tapered():
    st.settle()
    h.check(
        "Taper 10: the strip widens to 10 + 40 tan 10",
        st.near(surface_of("sweep"), TAPERED, 1e-4),
        (surface_of("sweep"), TAPERED),
    )
    st.choose("orientation", "Parallel")


def s3_parallel():
    st.settle()
    p = st.panel()
    h.check(
        "Parallel greys Twist and Taper",
        p is not None and not p.rows["twist"][0].isEnabled() and not p.rows["taper"][0].isEnabled(),
    )
    st.choose("orientation", "Perpendicular")


def s3_ok():
    st.settle()
    h.check("tapered again", st.near(surface_of("sweep"), TAPERED, 1e-4), surface_of("sweep"))
    st.ok()


def s3_done():
    h.check("dialog closed", st.panel() is None)


# -- S4: Esc ---------------------------------------------------------------------------------------
def s4_edit():
    h.check("double-clicked Sweep 1 again", st.double_click_timeline("Sweep 1"))


def s4_taper():
    p = st.panel()
    h.check(
        "Taper 10 read back", p is not None and st.near(p.options["taper"], 10.0), p and p.options
    )
    st.type_field("taper", "20")


def s4_esc():
    st.settle()
    st.esc()


def s4_done():
    h.check("Esc closed the dialog", st.panel() is None)
    h.check("unchanged", st.near(surface_of("sweep"), TAPERED, 1e-4), surface_of("sweep"))


h.run(
    "surface2_revolve_sweep",
    [
        new_design,
        pick_xz,
        draw_revolve,
        finish_revolve,
        path_sketch,
        pick_xy,
        draw_path_rail,
        finish_path_rail,
        profile_sketch,
        pick_xy_again,
        draw_profile,
        finish_profile,
        surface_tab,
        r1_revolve,
        r1_types,
        r1_axis,
        r1_type_to,
        r1_waits,
        r1_quarter,
        r1_done,
        r2_edit,
        r2_read_back,
        r2_click_xz,
        r2_half,
        r2_done,
        r3_show_sketch,
        r3_revolve,
        r3_profile,
        r3_axis,
        r3_to,
        r3_click_xy,
        r3_refused,
        r3_ok_waits,
        r3_cancelled,
        s1_show_sketches,
        s1_sweep,
        s1_rail_type,
        s1_click_profile,
        s1_click_path,
        s1_click_rail,
        s1_scaled,
        s1_none,
        s1_ok,
        s1_done,
        s2_undo,
        s2_undone,
        s2_redo,
        s2_redone,
        s3_edit,
        s3_single,
        s3_twist,
        s3_helicoid,
        s3_taper,
        s3_tapered,
        s3_parallel,
        s3_ok,
        s3_done,
        s4_edit,
        s4_taper,
        s4_esc,
        s4_done,
    ],
)
