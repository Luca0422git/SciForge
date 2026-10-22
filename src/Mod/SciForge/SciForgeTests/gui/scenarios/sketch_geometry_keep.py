# SPDX-License-Identifier: LGPL-2.1-or-later
"""Construction curves and geometry ids survive every SciForge tool that sets a sketch's
curves (sciforge/sketch_geometry.py; Luca, 2026-10-22: "fix the sketch tools bug, the loose
end you left open").

FreeCAD 1.1.4 hands a sketch point to Python without its sketch data, so assigning
`sketch.Geometry = [...]` turned every construction point (the old corner a sketch fillet
keeps) into a real point with a new id: the sketch's shape got a stray vertex, and what
named the point by its id (FreeCAD's element map, external references, SciForge's picks)
lost it. A fully constrained 20 x 10 rectangle (-30, 0)-(-10, 10), its top-right corner
filleted with SciForge's own Fillet (real clicks and keys: MODIFY > Fillet, the corner, 3,
Enter: the old corner stays as a construction point on both lines), then:

  E  sketch_explain puts curves back (a copy of the filleted sketch in its own document):
     E1 inferred guesses that only fit by squeezing a line (add_checked takes the weakest
        out and puts the curves back), E2 a redundant constraint whose culprits are found
        by switching constraints off (redundant_culprits puts the curves back), E3 a
        constraint solved without (check_new's _solve_without puts the curves back): each
        time the old corner stays construction with its id, the other curves keep theirs
  S  Finish Sketch; the sketch's browser row, MODIFY > Scale, factor 2, OK (real input):
     every curve keeps its construction flag and id, the constraints are the same (the
     dimensions doubled), still fully constrained, the profile 4 times the area, no stray
     vertex; Ctrl+Z: as before
  T  the sketch opened again from the timeline, SKETCH > CREATE > Text (real input), its
     frame's corner dragged (text.set_frame): the rectangle's curves keep their flags and ids
  R  Finish Sketch, save, close, reopen: the old corner is still a construction point
  D  a sketch derived from a saved design (derive.update deletes and adds every curve):
     the derived curves keep their source's ids over an update
"""

import os
import tempfile

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import modify2_steps as m
from SciForgeTests.gui import shell_draft_steps as sd
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import sketch_tools_steps as st
from SciForgeTests.gui import text_input as ti

V = App.Vector
s = st.s
CORNER = V(-10, 10, 0)


def sk():
    sketch = App.ActiveDocument.getObject(s.get("name", "")) if App.ActiveDocument else None
    return sketch if sketch is not None else st.sketch()


def state(sketch):
    """[(type, construction, geometry id, internal role)] of every curve, read with
    everything FreeCAD keeps on it (GeometryFacadeList)."""
    return [
        (f.Geometry.TypeId, bool(f.Construction), f.Id, f.InternalType)
        for f in sketch.GeometryFacadeList
    ]


def constraints(sketch, values=True):
    return [
        (c.Type, c.First, c.FirstPos, c.Second, c.SecondPos, c.Third)
        + ((round(c.Value, 6),) if values else ())
        for c in sketch.Constraints
    ]


def areas(sketch):
    from sciforge import sketch_regions

    return sorted(round(f.Area, 6) for f in sketch_regions.profile_regions(sketch))


def locked(sketch):
    from sciforge import sketch_explain

    sketch.solve()
    return sketch_explain.fully_constrained(sketch)


def corner_points(sketch, where=CORNER, tol=1e-6):
    return [
        i
        for i, g in enumerate(sketch.Geometry)
        if g.TypeId == "Part::GeomPoint" and (V(g.X, g.Y, 0) - where).Length < tol
    ]


def same_state(where, sketch, want, upto=None):
    now = state(sketch)
    if upto is not None:
        now = now[:upto]
    changed = [(i, a, b) for i, (a, b) in enumerate(zip(want, now)) if a != b]
    h.check(
        "%s: every curve keeps its construction flag and geometry id" % where,
        len(now) == len(want) and not changed,
        changed or (len(now), len(want)),
    )
    points = corner_points(sketch, s["corner_at"])
    h.check(
        "%s: the old corner is still a construction point" % where,
        len(points) == 1 and sketch.getConstruction(points[0]),
        [(i, sketch.getConstruction(i)) for i in points],
    )


# -- setup: a fully constrained rectangle, its corner filleted with real input --------------
def setup():
    import Part
    import Sketcher

    sketch = st.sketch()
    s["name"] = sketch.Name
    doc = App.ActiveDocument
    doc.openTransaction("Rectangle")
    pts = [V(-30, 0, 0), V(-10, 0, 0), V(-10, 10, 0), V(-30, 10, 0)]
    lines = [sketch.addGeometry(Part.LineSegment(pts[i], pts[(i + 1) % 4])) for i in range(4)]
    cons = [Sketcher.Constraint("Coincident", lines[i], 2, lines[(i + 1) % 4], 1) for i in range(4)]
    cons += [
        Sketcher.Constraint("Horizontal", lines[0]),
        Sketcher.Constraint("Horizontal", lines[2]),
        Sketcher.Constraint("Vertical", lines[1]),
        Sketcher.Constraint("Vertical", lines[3]),
        Sketcher.Constraint("DistanceX", -1, 1, lines[0], 1, -30.0),
        Sketcher.Constraint("DistanceY", -1, 1, lines[0], 1, 0.0),
        Sketcher.Constraint("Distance", lines[0], 20.0),
        Sketcher.Constraint("Distance", lines[1], 10.0),
    ]
    sketch.addConstraint(cons)
    doc.commitTransaction()
    sketch.solve()
    doc.recompute()
    h.fit(iso=False)
    h.check("the rectangle is fully constrained", locked(sketch), sketch.DoF)


def fillet_open():
    si.menu_item("MODIFY", "Fillet")


def fillet_corner():
    h.check("SciForge's Fillet runs", st.tool_title() == "Fillet", st.tool_title())
    st.click(CORNER)


def fillet_radius():
    h.check(
        "the corner point picks both lines",
        st.tool() is not None and st.tool().step == 2,
        st.tool() and st.tool().step,
    )
    st.keys("3\n")


fillet_radius.wait_ms = 900


def fillet_check():
    sketch = sk()
    arcs = [g for g in sketch.Geometry if g.TypeId == "Part::GeomArcOfCircle"]
    h.check("a fillet of radius 3", len(arcs) == 1 and st.near(arcs[0].Radius, 3.0), arcs)
    points = corner_points(sketch)
    h.check(
        "the old corner stays as a construction point",
        len(points) == 1 and sketch.getConstruction(points[0]),
        points,
    )
    st.sketch_ok("fillet")
    h.check("still fully constrained", locked(sketch), sketch.DoF)
    s["corner_at"] = CORNER
    s["base"] = state(sketch)
    s["cons"] = constraints(sketch)
    s["areas"] = areas(sketch)
    h.check("one profile", len(s["areas"]) == 1, s["areas"])
    st.esc()


# -- E: sketch_explain puts curves back ------------------------------------------------------
def _copy(name):
    """A copy of the filleted sketch (every curve with its sketch data) in a new document."""
    src = sk()
    d = App.newDocument(name)
    copy = d.addObject("Sketcher::SketchObject", "Sketch")
    copy.GeometryFacadeList = src.GeometryFacadeList
    copy.Constraints = src.Constraints
    copy.solve()
    h.check("%s: the copy has the same curves" % name, state(copy) == s["base"], state(copy))
    return d, copy


def _tilt(sketch, index, dy):
    """Move the end of a line by dy without solving, keeping its sketch data (the sketch's
    curves then no longer meet its constraints: what the solver moves while the explanations
    switch constraints off)."""
    import Sketcher

    facades = sketch.GeometryFacadeList
    f = facades[index]
    g = f.Geometry
    g.EndPoint = V(g.EndPoint.x, g.EndPoint.y + dy, 0)
    for ext in f.getExtensions():
        g.setExtension(ext)
    facades[index] = Sketcher.GeometryFacade(g)
    sketch.GeometryFacadeList = facades


def _back_to_doc():
    doc = Gui.getDocument(s["doc"])
    if doc is not None:
        App.setActiveDocument(s["doc"])
        Gui.ActiveDocument = doc


def e_collapse():
    """E1 (sketch_explain.add_checked): of Parallel to a level line, a Coincident and a
    Vertical, only the line squeezed to nothing fits all three: the curves are put back and
    the Parallel goes."""
    import Part
    import Sketcher

    from PySide6 import QtTest
    from sciforge import sketch_explain

    s["doc"] = App.ActiveDocument.Name
    d, copy = _copy("KeepCollapse")
    n = len(s["base"])
    level = copy.addGeometry(Part.LineSegment(V(0, 0, 0), V(30, 0, 0)))
    copy.addConstraint(Sketcher.Constraint("Horizontal", level))
    new = copy.addGeometry(Part.LineSegment(V(30, 0, 0), V(30.2, 20, 0)))
    copy.solve()
    kept = sketch_explain.add_checked(
        copy,
        [
            Sketcher.Constraint("Parallel", new, level),
            Sketcher.Constraint("Coincident", new, 1, level, 2),
            Sketcher.Constraint("Vertical", new),
        ],
    )
    types = sorted(c.Type for c in kept)
    h.check("E1 the Coincident and the Vertical are kept", types == ["Coincident", "Vertical"])
    same_state("E1", copy, s["base"], upto=n)
    h.check(
        "E1 the rectangle's constraints are unchanged",
        constraints(copy)[: len(s["cons"])] == s["cons"],
        constraints(copy)[: len(s["cons"])],
    )
    copy.solve()
    h.check("E1 the profile is unchanged", areas(copy)[:1] == s["areas"], areas(copy))
    App.closeDocument(d.Name)
    _back_to_doc()
    QtTest.QTest.qWait(300)
    h.check("E1 FreeCAD reported the squeezed try (expected)", True, h.new_errors())


e_collapse.notes_ok = ("Invalid solution", "Both points are equal")


def e_redundant():
    """E2 (check_new -> redundant_culprits): a second Horizontal on a level line that the
    solver has not put level yet; the culprit search solves with constraints switched off,
    which moves the line: the curves are put back."""
    import Part
    import Sketcher

    from sciforge import sketch_explain

    d, copy = _copy("KeepRedundant")
    n = len(s["base"])
    line = copy.addGeometry(Part.LineSegment(V(0, -20, 0), V(10, -20, 0)))
    copy.addConstraint(Sketcher.Constraint("Horizontal", line))
    copy.solve()
    _tilt(copy, line, 2.0)
    first = len(copy.Constraints)
    copy.addConstraint(Sketcher.Constraint("Horizontal", line))
    finding = sketch_explain.check_new(copy, [first])
    h.check("E2 the repeat is found", finding.kind == "redundant", finding.kind)
    tilted = copy.Geometry[line].EndPoint.y
    h.check("E2 the curves are as they were (put back)", abs(tilted + 18.0) < 1e-9, tilted)
    same_state("E2", copy, s["base"], upto=n)
    App.closeDocument(d.Name)
    _back_to_doc()


def e_without():
    """E3 (check_new's _solve_without, which check_new runs when the solver fails without
    naming the new constraints): the sketch solved with the new constraint switched off
    moves the line; the curves are put back."""
    import Part
    import Sketcher

    from sciforge import sketch_explain

    d, copy = _copy("KeepWithout")
    n = len(s["base"])
    line = copy.addGeometry(Part.LineSegment(V(0, -20, 0), V(10, -20, 0)))
    copy.addConstraint(Sketcher.Constraint("Horizontal", line))
    copy.solve()
    _tilt(copy, line, 2.0)
    first = len(copy.Constraints)
    copy.addConstraint(Sketcher.Constraint("Horizontal", line))  # (the solve then fails)
    sketch_explain._solve_without(copy, [first])
    tilted = copy.Geometry[line].EndPoint.y
    h.check("E3 the curves are as they were (put back)", abs(tilted + 18.0) < 1e-9, tilted)
    same_state("E3", copy, s["base"], upto=n)
    App.closeDocument(d.Name)
    _back_to_doc()


# -- S: Modify > Scale on the sketch ---------------------------------------------------------
def s_finish():
    h.ribbon("Finish Sketch")


def s_closed():
    h.check("the sketch closes", h.in_sketch() is None)
    same_state("S closed", sk(), s["base"])
    s["vertices"] = len(sk().Shape.Vertexes)  # (the open sketch's shape is from before)
    h.check("S the old corner is no vertex of the shape", s["vertices"] == 5, s["vertices"])
    Gui.Selection.clearSelection()
    h.click_empty()


def s_row():
    m.click_row(sk().Label)


def s_menu():
    sd.modify_menu("Scale")


def s_factor():
    p = m.panel_of("scale_ui", "ScalePanel")
    h.check("Scale opens on the sketch", p is not None and p.sketches == [sk()])
    if p is not None:
        sd.type_into(p.factor.widget, "2")


def s_ok():
    h.task_button("OK")


def s_check():
    sketch = sk()
    h.check("S the dialog closed", m.no_dialog())
    s["corner_at"] = CORNER * 2
    same_state("S", sketch, s["base"])
    want = [c[:-1] for c in s["cons"]]
    h.check(
        "S the same constraints", constraints(sketch, False) == want, constraints(sketch, False)
    )
    values = [c[-1] for c in constraints(sketch)]
    sizes = ("Distance", "DistanceX", "DistanceY", "Radius")
    doubled = [round(2 * c[-1], 6) if c[0] in sizes else c[-1] for c in s["cons"]]
    h.check("S the dimensions doubled", values == doubled, (values, doubled))
    st.s["sk"] = sketch
    st.sketch_ok("S")
    h.check("S still fully constrained", locked(sketch), sketch.DoF)
    h.check(
        "S the profile is 4 times the area",
        [round(a / 4, 6) for a in areas(sketch)] == s["areas"],
        (areas(sketch), s["areas"]),
    )
    h.check(
        "S no stray vertex in the sketch's shape",
        len(sketch.Shape.Vertexes) == s["vertices"],
        (len(sketch.Shape.Vertexes), s["vertices"]),
    )
    m.undo()


def s_undone():
    s["corner_at"] = CORNER
    same_state("S Ctrl+Z", sk(), s["base"])
    h.check("S Ctrl+Z: the profile as it was", areas(sk()) == s["areas"], areas(sk()))


# -- T: a text's frame dragged in the same sketch ------------------------------------------
def t_open():
    titles = [t for t in sd.timeline_titles() if t.startswith("Sketch")]
    h.check("the sketch is in the timeline", bool(titles), sd.timeline_titles())
    if titles:
        si.timeline_double_click(titles[0])


def t_ready():
    sketch = h.in_sketch()
    h.check("the sketch is open again", sketch is not None and sketch.Name == s["name"])
    s["sketch"] = sketch
    h.view().viewTop()
    h.fit(iso=False)


def t_drag():
    obj = s.get("text")
    if not h.check("T the text is made", obj is not None):
        return
    (cx, cy), _a, w, hh = ti.frame_of(obj)
    s["frame0"] = (cx, cy, w, hh)
    h.drag(ti.screen(sk(), cx + w, cy + hh), ti.screen(sk(), cx + w + 10, cy + hh + 5), steps=16)


def t_check():
    obj = s.get("text")
    if obj is None:
        return
    (cx, cy), _a, w, hh = ti.frame_of(obj)
    h.check("T the frame is bigger", w > s["frame0"][2] + 1, ((cx, cy, w, hh), s["frame0"]))
    same_state("T", sk(), s["base"], upto=len(s["base"]))
    h.check(
        "T the rectangle's constraints are unchanged",
        constraints(sk())[: len(s["cons"])] == s["cons"],
        constraints(sk())[: len(s["cons"])],
    )
    h.check("T the profile is unchanged", areas(sk()) == s["areas"], areas(sk()))


# -- R: saved and reopened -----------------------------------------------------------------
def r_finish():
    h.ribbon("Finish Sketch")


def r_save():
    h.check("the sketch closes", h.in_sketch() is None)
    s["state_t"] = state(sk())
    path = os.path.join(tempfile.mkdtemp(prefix="sciforge-keep-"), "keep.FCStd")
    s["path"] = path
    App.ActiveDocument.saveAs(path)
    App.closeDocument(App.ActiveDocument.Name)


def r_reopen():
    App.openDocument(s["path"])
    h.fit()


def r_check():
    sketch = App.ActiveDocument.getObject(s["name"])
    if not h.check("R reopened: the sketch is there", sketch is not None):
        return
    h.check("R reopened: every curve as saved", state(sketch) == s["state_t"], state(sketch))
    same_state("R", sketch, s["base"], upto=len(s["base"]))


# -- D: a derived sketch keeps its ids over an update -----------------------------------------
def d_derive():
    import Part
    import Sketcher

    from sciforge import derive

    folder = tempfile.mkdtemp(prefix="sciforge-keep-derive-")
    src = App.newDocument("KeepSource")
    body = src.addObject("PartDesign::Body", "Body")
    sketch = body.newObject("Sketcher::SketchObject", "Outline")
    sketch.addGeometry(Part.LineSegment(V(0, 0, 0), V(10, 0, 0)))
    sketch.addGeometry(Part.Point(V(5, 5, 0)), True)
    sketch.addGeometry(Part.LineSegment(V(0, 0, 0), V(0, 10, 0)))
    sketch.delGeometry(0)  # (the ids are no longer 1, 2, 3)
    sketch.addGeometry(Part.LineSegment(V(0, 0, 0), V(10, 0, 0)))
    src.recompute()
    path = os.path.join(folder, "source.FCStd")
    src.saveAs(path)
    source_ids = [sketch.getGeometryId(i) for i in range(len(sketch.Geometry))]
    data = derive.read_source(path)
    keys = [k for k in data["items"] if k.startswith("sketch:")]
    dst = App.newDocument("KeepDerived")
    master = derive.derive(dst, data, keys)
    dst.recompute()
    made = [o for o in dst.Objects if o.TypeId == "Sketcher::SketchObject"]
    if not h.check("D the sketch is derived", len(made) == 1, made):
        return
    derived = made[0]
    first = state(derived)
    h.check(
        "D the derived curves have the source's ids",
        [x[2] for x in first] == source_ids,
        (first, source_ids),
    )
    h.check("D the point stays construction", first[0][1] is True, first)
    # the source's line made longer, saved, the Derive updated
    facades = sketch.GeometryFacadeList
    f = facades[2]
    g = f.Geometry
    g.EndPoint = V(12, 0, 0)
    for ext in f.getExtensions():
        g.setExtension(ext)
    facades[2] = Sketcher.GeometryFacade(g)
    sketch.GeometryFacadeList = facades
    src.recompute()
    src.save()
    derive.update(master)
    dst.recompute()
    second = state(derived)
    h.check("D the update took the change", abs(derived.Geometry[2].EndPoint.x - 12) < 1e-9)
    h.check("D the derived curves keep their ids over an update", second == first, (first, second))
    App.closeDocument(dst.Name)
    App.closeDocument(src.Name)


h.run(
    "sketch_geometry_keep",
    si.watched(
        st.start_steps("SketchGeometryKeep")
        + [
            setup,
            fillet_open,
            fillet_corner,
            fillet_radius,
            fillet_check,
            e_collapse,
            e_redundant,
            e_without,
            s_finish,
            s_closed,
            s_row,
            s_menu,
            s_factor,
            s_ok,
            s_check,
            s_undone,
            t_open,
            t_ready,
        ]
        + ti.text_steps(s, (0, 20), (40, 35), "SF")
        + [
            t_drag,
            t_check,
            r_finish,
            r_save,
            r_reopen,
            r_check,
            d_derive,
        ]
    ),
)
