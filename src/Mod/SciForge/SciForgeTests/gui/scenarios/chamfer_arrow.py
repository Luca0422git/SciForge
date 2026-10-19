# SPDX-License-Identifier: LGPL-2.1-or-later
"""The chamfer's drag arrow can be seen and grabbed (Luca: "the chamfer tool doesn't have
an arrow to drag"). Only real input.

Box 40 x 30 x 10, Chamfer, click the top-back edge in the iso view: the arrow lies on the
face toward the viewer (the top), not on the back face behind the part. A 400 x 300 x 100
part: after Fit the arrow has the same screen size as on the box (handle_look_core.ARROW_PX,
shorter only where the view foreshortens it; it was 16 px once: the size was capped at 8 mm).
A 4 x 3 x 1 part: the arrow's tips stay inside the view and within 2 part
heights of where the chamfer's size puts the arrow (the 1.5 mm minimum put it off the part).
"""
import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import arrow_input as a
from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h
from sciforge.handle_look_core import ARROW_PX

V = App.Vector
s = {}


def panel():
    return b.blend_panel()


def first_arrow():
    p = panel()
    if p is None or not p.arrows:
        return None
    return p.arrows[0]


def toward():
    return App.Vector(h.view().getViewDirection()) * -1.0


def arrow_face_normal(spot):
    """The global normal of the face the arrow lies on."""
    p = panel()
    placement = p.body.getGlobalPlacement() if p is not None and p.body else App.Placement()
    return placement.Rotation.multVec(spot["lift"])


def tips(dragger):
    return a.arrow_ends(dragger)


def span_px(dragger):
    tail, tip = (h.screen_point(q) for q in tips(dragger))
    return ((tail.x() - tip.x()) ** 2 + (tail.y() - tip.y()) ** 2) ** 0.5


def inside_view(point):
    gl = h.gl_widget()
    pos = h.screen_point(point)
    return 0 <= pos.x() < gl.width() and 0 <= pos.y() < gl.height()


# -- 1. the top-back edge of a box ---------------------------------------------------------------
def chamfer_box():
    Gui.Selection.clearSelection()
    h.fit()
    h.ribbon("Chamfer")


def click_top_back_edge():
    p = panel()
    h.check("Chamfer dialog open", p is not None and p.title == "Chamfer")
    h.click_edge(V(20, 30, 10))


def arrow_toward_viewer():
    p = panel()
    arrow = first_arrow()
    h.check("the top-back edge is picked", p is not None and len(p.refs) == 1, p and p.refs)
    h.check("one arrow for Equal Distance", arrow is not None, p and len(p.arrows))
    if arrow is None:
        return
    dragger, spot, _origin, _direction = arrow
    normal = arrow_face_normal(spot)
    h.check(
        "the arrow lies on the face toward the viewer (the top), not on the hidden back face",
        normal.dot(toward()) > 0.3,
        (tuple(round(c, 3) for c in normal), tuple(round(c, 3) for c in toward())),
    )
    h.check("the arrow is in view", all(inside_view(q) for q in tips(dragger)))
    # Luca 2026-10-18: the arrows are Fusion's small ones, one size on the screen
    # (handle_look_core.ARROW_PX); lying on a face seen in the iso view it shows shorter
    h.check("the arrow has its screen size (ARROW_PX, foreshortened at most to 3/4)",
            0.75 * ARROW_PX <= span_px(dragger) <= ARROW_PX + 2.0, span_px(dragger))
    h.shot("1-top-back-edge")
    h.task_button("Cancel")


# -- 2. a big part ------------------------------------------------------------------------------
def chamfer_big():
    h.check("the box chamfer was cancelled", panel() is None)
    Gui.Selection.clearSelection()
    h.fit()
    h.ribbon("Chamfer")


def click_big_edge():
    h.click_edge(V(200, 0, 100))  # the front-top edge


def big_arrow_visible():
    p = panel()
    arrow = first_arrow()
    h.check("the edge of the 400 mm part is picked", p is not None and len(p.refs) == 1,
            p and p.refs)
    if arrow is None:
        h.check("an arrow on the 400 mm part", False)
        return
    dragger = arrow[0]
    h.check("on a 400 mm part the arrow has the same screen size (was 16 px once)",
            0.75 * ARROW_PX <= span_px(dragger) <= ARROW_PX + 2.0, span_px(dragger))
    h.check("and not more than a quarter of the view", span_px(dragger) <= h.gl_widget().width() / 4,
            span_px(dragger))
    h.shot("2-big-part")
    h.task_button("Cancel")


# -- 3. a tiny part ----------------------------------------------------------------------------
def chamfer_tiny():
    h.check("the big chamfer was cancelled", panel() is None)
    Gui.Selection.clearSelection()
    h.fit()
    h.ribbon("Chamfer")


def click_tiny_edge():
    h.click_edge(V(2, 0, 1))  # the front-top edge of the 4 x 3 x 1 part


def tiny_arrow_on_the_part():
    p = panel()
    arrow = first_arrow()
    h.check("the edge of the 4 mm part is picked", p is not None and len(p.refs) == 1,
            p and p.refs)
    if arrow is None:
        h.check("an arrow on the 4 mm part", False)
        return
    dragger = arrow[0]
    edge_point = V(2, 0, 1)
    far = max((q - edge_point).Length for q in tips(dragger))
    # The arrow's middle marks the chamfer's size (1 mm by default) on the face: the tips
    # stay within two part heights (2 mm) of that.
    limit = 2.0 + p.distance.value()
    h.check("the arrow's tips stay within 2 part heights of the edge (plus the 1 mm size)",
            far <= limit, (far, limit))
    h.check("the arrow's tips are inside the view", all(inside_view(q) for q in tips(dragger)),
            [(h.screen_point(q).x(), h.screen_point(q).y()) for q in tips(dragger)])
    h.check("and the same screen size on the 4 mm part",
            0.75 * ARROW_PX <= span_px(dragger) <= ARROW_PX + 2.0, span_px(dragger))
    h.shot("3-tiny-part")
    h.task_button("Cancel")


def done():
    h.check("the tiny chamfer was cancelled", panel() is None)


h.run(
    "chamfer_arrow",
    b.box_steps("ChamferArrow")
    + [chamfer_box, click_top_back_edge, arrow_toward_viewer]
    + b.box_steps("ChamferBig", height=100, profile=lambda sk: h.draw_rectangle(sk, 0, 0, 400, 300))
    + [chamfer_big, click_big_edge, big_arrow_visible]
    + b.box_steps("ChamferTiny", height=1, profile=lambda sk: h.draw_rectangle(sk, 0, 0, 4, 3))
    + [chamfer_tiny, click_tiny_edge, tiny_arrow_on_the_part, done],
)
