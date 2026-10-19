# SPDX-License-Identifier: LGPL-2.1-or-later
"""Real-input helpers for the fixdecal_* scenarios: a decal stays stuck to its face when the
body or component moves or the face changes (docs/sciforge/parity/misc.md, Decal). Not a
scenario (it lives outside scenarios/)."""

import math

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plane_input as pl
from SciForgeTests.gui import insert_steps as i
from SciForgeTests.gui import sketch_input as si

V = App.Vector
TOP = V(20, 15, 10)  # the box's top face (40 x 30 x 10), where the flat decal is clicked
SIDE = V(100, -10, 20)  # the cylinder's side (r 10, 40 high at x 100), facing -Y


def doc():
    return App.ActiveDocument


def decals():
    from sciforge import decal

    return decal.decals(doc()) if doc() is not None else []


def flat():
    found = [d for d in decals() if d.Surface == "Plane"]
    return found[0] if found else None


def wrapped():
    found = [d for d in decals() if d.Surface == "Cylinder"]
    return found[0] if found else None


def panel():
    from sciforge import decal_ui, taskui

    current = taskui.current()
    return current if isinstance(current, decal_ui.DecalPanel) else None


def use_picture():
    from sciforge import decal_ui

    decal_ui.FILE_PICKER = lambda kind: i.fixture("canvas.png")


def forget_picture():
    from sciforge import decal_ui

    decal_ui.FILE_PICKER = None


def box_and_cylinder(name, cylinder=True, tall=None):
    """A design with a box 40 x 30 x 10 (Body, a sketch extruded; its height the user
    parameter `tall` when given) and a cylinder r 10, 40 high at x 100 (Body001)."""
    from sciforge import commands, parameters, sketch_ui

    Gui.activateWorkbench("SciForgeWorkbench")
    d = App.newDocument(name)
    if tall is not None:
        parameters.add_user(d, "tall", "mm", str(tall))
    body = commands.ensure_body()
    planes = sketch_ui.origin_planes(body)
    sk = sketch_ui.create_sketch(body, (planes["XY_Plane"], ""))
    h.draw_rectangle(sk, 0, 0, 40, 30)
    pad = body.newObject("PartDesign::Pad", "Pad")
    pad.Profile = sk
    if tall is not None:
        pad.setExpression("Length", "Parameters.tall")
    else:
        pad.Length = 10
    body.Tip = pad
    found = {"box": body.Name, "pad": pad.Name}
    if cylinder:
        cyl_body = d.addObject("PartDesign::Body", "Body001")
        cyl = d.addObject("PartDesign::AdditiveCylinder", "Cylinder")
        cyl_body.addObject(cyl)
        cyl.Radius, cyl.Height = 10, 40
        cyl.Placement.Base = V(100, 0, 0)
        found["cyl"] = cyl_body.Name
    d.recompute()
    use_picture()
    h.fit()
    return found


def decal_steps(tag, point, check=None):
    """Steps: INSERT > Decal (the picture), click `point`, OK."""

    def open_():
        h.fit()
        si.menu_item("INSERT", "Decal")

    def click():
        h.check("%s: the Decal dialog waits for a face" % tag, panel() is not None)
        pl.click_on_plane(point)

    def ok():
        p = panel()
        h.check("%s: a decal laid" % tag, p is not None and p.feature() is not None, p and p.obj)
        h.task_button("OK")

    def done():
        h.check("%s: the dialog closed" % tag, panel() is None)
        if check is not None:
            check()

    open_.wait_ms = 1500
    click.wait_ms = 1500
    ok.wait_ms = 1200
    steps = [open_, click, ok, done]
    for step in steps:
        step.__name__ = "%s_%s" % (tag, step.__name__.strip("_"))
    return steps


# -- where the decal is, as drawn ---------------------------------------------------------------
def container_place(obj):
    """Where the decal's own coordinates (its body's) lie in the design."""
    from sciforge import decal

    return decal.global_place(obj)


def drawn_points(obj):
    """The decal's points as Coin draws them, in design coordinates (every transform on the
    way to them in the 3D view's scene graph applied: a component's placement, the body's)."""
    from pivy import coin

    try:
        vobj = obj.ViewObject
        node = vobj.Proxy.coords
        coords = node.point.getValues()
        view = Gui.ActiveDocument.ActiveView
        search = coin.SoSearchAction()
        search.setNode(node)
        search.setInterest(coin.SoSearchAction.FIRST)
        search.apply(view.getSceneGraph())
        path = search.getPath()
        if path is None:
            return []
        action = coin.SoGetMatrixAction(view.getViewer().getSoRenderManager().getViewportRegion())
        action.apply(path)
        matrix = action.getMatrix()
        out = []
        for c in coords:
            p = matrix.multVecMatrix(c)
            out.append(V(p[0], p[1], p[2]))
        return out
    except Exception as exc:
        h.check("drawn points readable", False, repr(exc))
        return []


def copy_points(obj):
    """[[points]] of each copy of the picture drawn on an instance of its component, in design
    coordinates (every path to the shared coordinates node after the first one)."""
    from pivy import coin

    out = []
    try:
        node = obj.ViewObject.Proxy.coords
        coords = node.point.getValues()
        view = Gui.ActiveDocument.ActiveView
        search = coin.SoSearchAction()
        search.setNode(node)
        search.setInterest(coin.SoSearchAction.ALL)
        search.apply(view.getSceneGraph())
        paths = search.getPaths()
        region = view.getViewer().getSoRenderManager().getViewportRegion()
        for k in range(1, paths.getLength()):
            action = coin.SoGetMatrixAction(region)
            action.apply(paths[k])
            matrix = action.getMatrix()
            points = []
            for c in coords:
                p = matrix.multVecMatrix(c)
                points.append(V(p[0], p[1], p[2]))
            out.append(points)
    except Exception as exc:
        h.check("copies readable", False, repr(exc))
    return out


def gap_to(shape, points):
    """How far the points lie from `shape`, at most (mm); None without points."""
    import Part

    if not points or shape is None or shape.isNull():
        return None
    step = max(1, len(points) // 40)
    return max(shape.distToShape(Part.Vertex(p))[0] for p in points[::step])


def centre(obj):
    """The decal's middle in design coordinates."""
    from sciforge import decal

    point = decal.centre(obj)[0]
    return container_place(obj).multVec(point)


def axes(obj):
    """(x, y, z) of the decal's frame in design coordinates."""
    from sciforge import decal

    _p, x, y, z = decal.centre(obj)
    rot = container_place(obj).Rotation
    return rot.multVec(x), rot.multVec(y), rot.multVec(z)


def area(obj):
    from sciforge import decal

    return decal.covered_area(obj)


def body_shape(obj):
    from sciforge import bodies

    return bodies.global_shape(obj.Body)


def gap_to_body(obj, points=None):
    """How far the drawn points lie from the body's surface, at most (mm)."""
    import Part

    shape = body_shape(obj)
    points = points if points is not None else drawn_points(obj)
    if not points:
        return None
    step = max(1, len(points) // 40)
    worst = 0.0
    for p in points[::step]:
        worst = max(worst, shape.distToShape(Part.Vertex(p))[0])
    return worst


def snapshot(obj):
    """What a check compares with later: the middle, the frame, the area, the drawn points."""
    return {
        "centre": centre(obj),
        "axes": axes(obj),
        "area": area(obj),
        "points": drawn_points(obj),
    }


def red(obj):
    state = list(obj.State)
    return "Invalid" in state or "Error" in state


def follows(tag, obj, before, place, tol=1e-3):
    """Checks: `obj` sits where `place` (design coordinates) takes it from `before`: its
    middle, its frame, the same size, drawn there on the body's face, not red."""
    if not h.check("%s: the decal is there" % tag, obj is not None):
        return False
    want = place.multVec(before["centre"])
    ok = h.check(
        "%s: its middle moved with the face" % tag,
        (centre(obj) - want).Length < tol,
        (centre(obj), want),
    )
    rot = place.Rotation
    got = axes(obj)
    turned = all((g - rot.multVec(a)).Length < 1e-4 for g, a in zip(got, before["axes"]))
    ok = h.check("%s: turned with it" % tag, turned, (got, before["axes"])) and ok
    ok = (
        h.check(
            "%s: the same size" % tag,
            abs(area(obj) - before["area"]) < 1e-3 * max(1.0, before["area"]),
            (area(obj), before["area"]),
        )
        and ok
    )
    ok = drawn_on_face(tag, obj) and ok
    return ok


def drawn_on_face(tag, obj, lift=0.06):
    points = drawn_points(obj)
    ok = h.check(
        "%s: drawn" % tag, len(points) > 3 and obj.ViewObject.Proxy.drawn()[2], len(points)
    )
    gap = gap_to_body(obj, points)
    ok = h.check("%s: drawn on the body's face" % tag, gap is not None and gap < lift, gap) and ok
    ok = h.check("%s: not red" % tag, not red(obj), (obj.State, obj.getStatusString())) and ok
    return ok


def radii(obj, axis_point, axis_dir):
    """Distances of the drawn points from a line (design coordinates)."""
    axis_dir = V(axis_dir).normalize()
    out = []
    for p in drawn_points(obj):
        rel = p - axis_point
        out.append((rel - axis_dir * rel.dot(axis_dir)).Length)
    return out


def near(a, b, tol=1e-3):
    return a is not None and b is not None and abs(a - b) <= tol


def angle_deg(a, b):
    return math.degrees(a.getAngle(b))
