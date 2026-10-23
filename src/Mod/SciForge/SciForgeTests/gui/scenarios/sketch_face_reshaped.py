# SPDX-License-Identifier: LGPL-2.1-or-later
"""Create Sketch on a face a later step reshaped projects the face as it is now (Luca,
2026-10-23: "when I select a face to sketch on, it doesn't project the right face": the top
of a drafted block came in as the block's top before the Draft, larger than the part).

The sketch hangs on the earliest step that has the face (sketch_ui._earliest: suppressing
the Draft or fillet must not take it along, fixsketch_fillet E), while Auto project brings
in the face as it is now, and keeps it so (sketch_auto_project.follow).

1. A 40 x 30 x 20 block, its four walls drafted 10 deg from the XY plane (SciForge's Draft):
   Create Sketch, click the top: the sketch hangs on the block, the projected curves are
   the drafted top's outline (smaller than 40 x 30), from the Draft, all of them on the
   face. Finish.
2. A 40 x 30 x 20 block with its four top edges filleted r 3: Create Sketch, click the top:
   on the block, the projected outline is the fillet's 34 x 24, not 40 x 30. A line drawn
   from one projected corner to another (held there by two coincidences). Finish.
3. Suppress the fillet in the timeline: the sketch stays on (not suppressed), its
   projected outline is the block's top again (40 x 30) and the line went with its
   corners. Unsuppress: 34 x 24 again, the line back.
4. Delete the fillet: 40 x 30, nothing broken; Ctrl+Z: the fillet and 34 x 24 are back.
"""

import FreeCAD as App
import FreeCADGui as Gui
import Part

from PySide import QtCore, QtWidgets

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import sketch_input as si
from SciForgeTests.gui import widget_input as w

V = App.Vector
s = {}
BLOCK = [
    {"op": "sketch", "id": "s1", "plane": "XY", "geometry": [{"rect": [0, 0, 40, 30]}]},
    {"op": "extrude", "id": "e1", "profile": "s1", "distance": 20},
]
DRAFT = {
    "op": "sf_draft",
    "id": "d1",
    "plane": "XY",
    "faces": {"along": [0, 0, 1], "type": "plane", "count": 4},
    "angle": 10,
}
FILLET = {
    "op": "fillet",
    "id": "f1",
    "edges": {"type": "line", "at": {"axis": "z", "value": "max"}, "count": 4},
    "radius": 3,
}


def build(name, steps):
    from SciForgeTests.golden.builder import Builder

    Gui.activateWorkbench("SciForgeWorkbench")
    doc = App.newDocument(name)
    builder = Builder(doc)
    for step in steps:
        builder.run(step)
    doc.recompute()
    s["builder"] = builder
    h.fit()


def top_face():
    """(step, 'FaceN', face) of the body's newest step: its highest flat face up."""
    tip = h.body().Tip
    best = None
    for i, face in enumerate(tip.Shape.Faces, start=1):
        if face.Surface.TypeId == "Part::GeomPlane" and face.normalAt(0, 0).z > 0.99:
            if best is None or face.BoundBox.ZMax > best[2].BoundBox.ZMax:
                best = (tip, "Face%d" % i, face)
    return best


def projected(sketch):
    """The projected (purple) curves in the part's coordinates."""
    shapes = [g.toShape() for g in list(sketch.ExternalGeo)[2:]]
    if not shapes:
        return None
    matrix = sketch.getGlobalPlacement().toMatrix()
    return Part.Compound(shapes).transformGeometry(matrix)


def build_drafted():
    build("SketchFaceDraft", BLOCK + [DRAFT])


def build_filleted():
    build("SketchFaceFillet", BLOCK + [FILLET])


def click_top():
    s["top"] = top_face()
    h.ribbon("Create Sketch")


def click_centre():
    face = s["top"][2]
    h.click(face.CenterOfMass)


def source(sketch):
    """The object the sketch's projected curves come from."""
    from sciforge import sketch_auto_project

    return sketch_auto_project.source(sketch)[0]


def check_projection(label, want_step, size=None):
    def step():
        sk = h.in_sketch()
        h.check("%s: sketch open on the top" % label, sk is not None)
        if sk is None:
            return
        s["sketch"] = sk.Name
        support = sk.AttachmentSupport
        on = support[0][0] if support else None
        h.check(
            "%s: it hangs on the block (e1), not on the %s" % (label, want_step),
            on is not None and on.Name == s["builder"].objects["e1"].Name,
            support,
        )
        src = source(sk)
        h.check(
            "%s: the curves are projected from the %s" % (label, want_step),
            src is not None and src.Name == s["builder"].objects[want_step].Name,
            src.Name if src is not None else None,
        )
        face = s["top"][2]
        curves = projected(sk)
        h.check("%s: the face's edges are projected" % label, curves is not None)
        if curves is None:
            return
        want, got = face.OuterWire.BoundBox, curves.BoundBox
        h.check(
            "%s: the projected outline is the face's (%.2f x %.2f)"
            % (label, want.XLength, want.YLength),
            all(
                abs(a - b) < 1e-4
                for a, b in (
                    (want.XMin, got.XMin),
                    (want.YMin, got.YMin),
                    (want.XMax, got.XMax),
                    (want.YMax, got.YMax),
                )
            ),
            (
                (got.XMin, got.YMin, got.XMax, got.YMax),
                (want.XMin, want.YMin, want.XMax, want.YMax),
            ),
        )
        if size is not None:
            h.check(
                "%s: %g x %g" % (label, size[0], size[1]),
                si.near(got.XLength, size[0], 1e-6) and si.near(got.YLength, size[1], 1e-6),
                (got.XLength, got.YLength),
            )
        far = [v.Point for v in curves.Vertexes if face.distToShape(Part.Vertex(v.Point))[0] > 1e-6]
        h.check("%s: every projected curve lies on the face" % label, not far, far[:4])
        h.shot(label)

    step.__name__ = "projected_" + label
    return step


def draw_line():
    """A line from the projected curves' first corner to the next, held by coincidences
    (as drawing it with the snaps on them makes it)."""
    import Sketcher

    sk = h.in_sketch()
    if sk is None:
        return
    ext = list(sk.ExternalGeo)
    lines = [(-(i + 1), g) for i, g in enumerate(ext) if i >= 2 and isinstance(g, Part.LineSegment)]
    (g1, l1), (g2, l2) = lines[0], lines[1]
    k = sk.addGeometry(Part.LineSegment(l1.StartPoint, l2.StartPoint))
    sk.addConstraint(Sketcher.Constraint("Coincident", k, 1, g1, 1))
    sk.addConstraint(Sketcher.Constraint("Coincident", k, 2, g2, 1))
    App.ActiveDocument.recompute()
    s["line"] = line_ends(sk)
    s["corners"] = (corner(sk, l1.StartPoint), corner(sk, l2.StartPoint))


def corner(sk, point):
    return sk.getGlobalPlacement().multVec(point)


def line_ends(sk):
    line = sk.Geometry[0]
    return (corner(sk, line.StartPoint), corner(sk, line.EndPoint))


def finish():
    h.ribbon("Finish Sketch")


def finished():
    h.check("Finish Sketch: closed", h.in_sketch() is None)
    h.check("no pop-up", not h.popups(), h.popups())


def close_all():
    for doc in list(App.listDocuments().values()):
        App.closeDocument(doc.Name)


def timeline_button(name):
    from sciforge import timeline_ui

    tl = timeline_ui.widget()
    tl.refresh(force=True)
    QtWidgets.QApplication.processEvents()
    for button in tl._buttons:
        if button.item.name == name:
            return button
    h.check("timeline shows %s" % name, False, tl.titles())
    return None


def timeline_menu(entry):
    def step():
        button = timeline_button(s["builder"].objects["f1"].Name)
        if button is not None:
            h.check("timeline: %s" % entry, w.right_click(button, w.center(button), entry))

    step.__name__ = "timeline_" + entry.lower().replace(" ", "_")
    return step


def ctrl_z():
    h.press("z", QtCore.Qt.ControlModifier)


def check_outline(label, size, line_moved):
    """The sketch is on, unbroken, its projected outline `size` and lying on the top face of
    the body as it is now; its line on the projected corners (moved with them or not)."""

    def step():
        from sciforge import timeline_ops

        doc = App.ActiveDocument
        sk = doc.getObject(s["sketch"])
        h.check("%s: the sketch is there" % label, sk is not None)
        if sk is None:
            return
        h.check("%s: the sketch is on (not suppressed)" % label, not timeline_ops.is_suppressed(sk))
        state = list(sk.State)
        h.check("%s: the sketch works" % label, "Invalid" not in state and "Error" not in state, state)
        support = sk.AttachmentSupport
        h.check(
            "%s: it still hangs on the block" % label,
            support and support[0][0].Name == s["builder"].objects["e1"].Name,
            support,
        )
        curves = projected(sk)
        got = curves.BoundBox if curves is not None else None
        h.check(
            "%s: projected outline %g x %g" % (label, size[0], size[1]),
            got is not None
            and si.near(got.XLength, size[0], 1e-6)
            and si.near(got.YLength, size[1], 1e-6),
            (got.XLength, got.YLength) if got is not None else None,
        )
        face = top_face()[2]
        far = [v.Point for v in curves.Vertexes if face.distToShape(Part.Vertex(v.Point))[0] > 1e-6] if curves else []
        h.check("%s: every projected curve lies on the top face" % label, curves is not None and not far, far[:4])
        ends = line_ends(sk)
        same = all((a - b).Length < 1e-6 for a, b in zip(ends, s["line"]))
        h.check(
            "%s: the line on the corners %s" % (label, "moved with them" if line_moved else "is back"),
            same != line_moved,
            (ends, s["line"]),
        )
        if line_moved:
            pts = [v.Point for v in curves.Vertexes]
            h.check(
                "%s: its ends are on the projected corners" % label,
                all(any((e - p).Length < 1e-6 for p in pts) for e in ends),
                ends,
            )
        h.check("%s: no pop-up" % label, not h.popups(), h.popups())
        h.shot(label)

    step.__name__ = "outline_" + label.replace(" ", "_").replace(",", "")
    return step


h.run(
    "sketch_face_reshaped",
    [
        build_drafted,
        click_top,
        click_centre,
        check_projection("draft", "d1"),
        finish,
        finished,
        close_all,
        build_filleted,
        click_top,
        click_centre,
        check_projection("fillet", "f1", size=(34.0, 24.0)),
        draw_line,
        finish,
        finished,
        timeline_menu("Suppress Features"),
        h.idle_step(),
        check_outline("fillet suppressed", (40.0, 30.0), True),
        timeline_menu("Unsuppress Features"),
        h.idle_step("wait_unsuppress"),
        check_outline("fillet unsuppressed", (34.0, 24.0), False),
        timeline_menu("Delete"),
        h.idle_step("wait_delete"),
        check_outline("fillet deleted", (40.0, 30.0), True),
        ctrl_z,
        h.idle_step("wait_undo"),
        check_outline("delete undone", (34.0, 24.0), False),
        close_all,
    ],
)
