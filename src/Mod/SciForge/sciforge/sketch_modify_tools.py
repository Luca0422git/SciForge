# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Trim, Extend and Break, on SciForge's own sketch handler (sketch_draw.py).

- Trim (T): the piece under the pointer shows in red; a click removes it back to the
  nearest intersections (FreeCAD's own trim does the cutting, constraints and all); a
  press and drag removes every piece the pointer's path crosses, in one undo step; a
  curve that nothing crosses goes whole (Fusion's help "Trim or extend sketch geometry").
- Extend: hovering shows how far the end nearest the pointer would grow; one click
  extends it to the nearest curve it meets (FreeCAD's own Extend needs two clicks and a
  drag). The new end stays on that curve (PointOnObject).
- Break: the piece between the intersections nearest to the pointer shows; a click
  breaks the curve there into two or three pieces that stay joined (Fusion's
  breakCurve); FreeCAD's own Split cut at the clicked point instead.

The curve maths and the edits are in sketch_build.py. Each click is one undo step.
"""

from . import log, warn
from . import sketch_build as build
from . import sketch_draw as draw
from . import sketch_infer_core as icore


class _CurveTool(draw.DrawTool):
    """A tool that works on the sketch curve under the pointer (no points placed)."""

    def steps(self):
        return 1

    def own_curve(self, snap):
        """The sketch's own curve under the pointer (not the axes or projected edges:
        those cannot be changed), or None."""
        geo = self.geometry()
        tol = draw.pick_pixels() * self._px()
        best = None
        for index, curve in geo.hits:
            if index < 0 or not icore.near_curve(snap.raw, curve, tol):
                continue
            d = icore.curve_distance(snap.raw, curve)
            if best is None or d < best[1]:
                best = (index, d)
        return best[0] if best else None

    def _edit(self, name, work):
        """Run `work()` in one undo step; dropped when it changed nothing (returns
        False) or failed."""
        doc = self.doc
        sketch = self.sketch
        before = (sketch.GeometryCount, len(sketch.Constraints))
        self._applying = True
        doc.openTransaction(name)
        try:
            changed = work()
            if changed:
                sketch.solve()
        except Exception as exc:
            doc.abortTransaction()
            self._applying = False
            try:
                sketch.solve()
            except Exception:
                pass
            warn("%s: %s" % (self.title, exc))
            return False
        if changed:
            doc.commitTransaction()
        else:
            doc.abortTransaction()
        self._applying = False
        self._geometry = None
        if changed:
            log(
                "%s: done (curves %d -> %d, constraints %d -> %d)"
                % (name, before[0], sketch.GeometryCount, before[1], len(sketch.Constraints))
            )
        return bool(changed)


# -- Trim ----------------------------------------------------------------------------------
class Trim(_CurveTool):
    title = "Trim"
    command = "SciForge_SketchTrim"
    DRAG_PIXELS = 4

    def __init__(self, session):
        super().__init__(session)
        self.drag_from = None  # sketch point the drag's path continues from
        self.drag_trimmed = 0
        self.drag_open = False

    def prompt(self):
        return "click the piece of a curve to remove, or press and drag across several."

    def moved(self, snap):
        geo = self.own_curve(snap)
        if geo is None:
            self.preview.show()
            return
        try:
            found = build.piece(self.sketch, geo, snap.raw)
        except Exception:
            found = None
        if found is None:
            points = draw.curve_points(self.sketch, geo)  # nothing crosses: it goes whole
        else:
            points = build.piece_points(self.sketch, geo, found[0], found[1])
        self.preview.show(remove=[points])

    def pressed(self, snap, view):
        self.drag_from = snap.raw
        self.drag_trimmed = 0
        self.drag_open = False

    def dragged(self, snap, view):
        """Press and drag: every piece the pointer's path crosses goes (Fusion)."""
        if self.drag_from is None:
            return
        start, end = self.drag_from, snap.raw
        if icore.dist(start, end) < 1e-9:
            return
        if not self.drag_open:
            if self.drag_pixels < self.DRAG_PIXELS:
                return  # not a drag yet: a click is still possible
            self.doc.openTransaction("Trim")
            self._applying = True
            self.drag_open = True
        self.drag_from = end
        try:
            self.drag_trimmed += self._trim_crossed(start, end)
        except Exception as exc:
            warn("Trim: %s" % exc)
        self.preview.show(guides=[[start, end]])

    def _trim_crossed(self, a, b):
        """Trim every piece of the sketch's own curves that the segment a-b crosses.
        Returns how many pieces went."""
        import FreeCAD as App
        import Part

        if icore.dist(a, b) < 1e-9:
            return 0
        path = Part.LineSegment(App.Vector(a[0], a[1], 0), App.Vector(b[0], b[1], 0))
        done = 0
        tried = set()
        for _ in range(20):  # each trim changes the curves: look again
            hit = None
            for geo, curve in build.curves(self.sketch, external=False):
                try:
                    points = path.intersectCC(curve)
                except Exception:
                    continue
                for p in points:
                    mark = (geo, round(p.X, 6), round(p.Y, 6), self.sketch.GeometryCount)
                    if mark not in tried:
                        hit = (geo, p, mark)
                        break
                if hit is not None:
                    break
            if hit is None:
                break
            geo, p, mark = hit
            tried.add(mark)
            before = self.sketch.Geometry[geo]
            count = self.sketch.GeometryCount
            self.sketch.trim(geo, App.Vector(p.X, p.Y, 0))
            self._geometry = None
            if self.sketch.GeometryCount != count or not _same_curve(before, self.sketch, geo):
                done += 1
        return done

    def released(self, press_snap, snap, moved):
        if self.drag_open:
            self.drag_open = False
            self._applying = False
            if self.drag_trimmed:
                self.doc.commitTransaction()
                self.sketch.solve()
                log("Trim: %d piece(s) removed by dragging" % self.drag_trimmed)
            else:
                self.doc.abortTransaction()
            self.drag_from = None
            self.preview.clear()
            return
        self.drag_from = None
        geo = self.own_curve(press_snap)
        if geo is None:
            self.say("Trim: click on a curve.")
            return
        point = press_snap.raw

        def work():
            import FreeCAD as App

            self.sketch.trim(geo, App.Vector(point[0], point[1], 0))
            return True

        self._edit("Trim", work)
        self.preview.clear()

    def stop(self):
        if self.drag_open:
            self.drag_open = False
            try:
                if self.drag_trimmed:
                    self.doc.commitTransaction()
                else:
                    self.doc.abortTransaction()
            except Exception:
                pass
        super().stop()


# -- Extend --------------------------------------------------------------------------------
class Extend(_CurveTool):
    title = "Extend"
    command = "SciForge_SketchExtend"

    def prompt(self):
        return "click near the end of a line or arc to extend it to the next curve."

    def plan(self, snap):
        geo = self.own_curve(snap)
        if geo is None:
            return None, None
        try:
            return geo, build.extend_plan(self.sketch, geo, snap.raw)
        except Exception:
            return geo, None

    def moved(self, snap):
        geo, plan = self.plan(snap)
        if plan is None:
            self.preview.show(
                picked=[draw.curve_points(self.sketch, geo)] if geo is not None else []
            )
            return
        pos, point, _other, increment = plan
        g = self.sketch.Geometry[geo]
        if g.TypeId == "Part::GeomLineSegment":
            tip = g.StartPoint if pos == 1 else g.EndPoint
            grown = [[(tip.x, tip.y), point]]
        else:
            if pos == 2:
                a1, a2 = g.LastParameter, g.LastParameter + increment
            else:
                a1, a2 = g.FirstParameter - increment, g.FirstParameter
            grown = [draw.arc_points((g.Center.x, g.Center.y), g.Radius, a1, a2)]
        self.preview.show(curves=grown, points=[point])

    def released(self, press_snap, snap, moved):
        geo, plan = self.plan(press_snap)
        if geo is None:
            self.say("Extend: click near the end of a line or an arc.")
            return
        if plan is None:
            self.say("Extend: there is no curve for this end to reach.")
            return
        self._edit("Extend", lambda: build.extend_curve(self.sketch, geo, plan))
        self.preview.clear()


# -- Break --------------------------------------------------------------------------------
class Break(_CurveTool):
    title = "Break"
    command = "SciForge_SketchBreak"

    def prompt(self):
        return "click a curve where it should be broken (at the curves crossing it)."

    def moved(self, snap):
        geo = self.own_curve(snap)
        if geo is None:
            self.preview.show()
            return
        try:
            found = build.piece(self.sketch, geo, snap.raw)
        except Exception:
            found = None
        if found is None:
            self.preview.show(picked=[draw.curve_points(self.sketch, geo)])
            return
        g = self.sketch.Geometry[geo]
        ends = []
        for t in found[:2]:
            p = g.value(t)
            ends.append((p.x, p.y))
        self.preview.show(
            picked=[build.piece_points(self.sketch, geo, found[0], found[1])], points=ends
        )

    def released(self, press_snap, snap, moved):
        geo = self.own_curve(press_snap)
        if geo is None:
            self.say("Break: click on a curve.")
            return
        point = press_snap.raw
        result = {"cuts": 0}

        def work():
            result["cuts"] = build.break_curve(self.sketch, geo, point)
            return result["cuts"] > 0

        if not self._edit("Break", work):
            self.say("Break: nothing crosses this curve here, so there is nowhere to break it.")
        self.preview.clear()


def _same_curve(before, sketch, geo):
    """The curve at index `geo` is still `before` (the trim changed nothing)."""
    try:
        after = sketch.Geometry[geo]
        if after.TypeId != before.TypeId:
            return False
        return (
            abs(after.FirstParameter - before.FirstParameter) < 1e-9
            and abs(after.LastParameter - before.LastParameter) < 1e-9
            and (after.value(after.FirstParameter) - before.value(before.FirstParameter)).Length
            < 1e-9
        )
    except Exception:
        return False


TOOLS = {cls.command: cls for cls in (Trim, Extend, Break)}
