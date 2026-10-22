# SPDX-License-Identifier: LGPL-2.1-or-later
"""The AI tool render with the window renderer (the one an AI app gets whenever SciForge is
open) checked on its pixels, not its words (docs/sciforge/sessions/2026-10-22-fix-aiverify.md):

Path 1, a plate with a boss; the whole body selected (as new_design leaves it): a plain
  render is not tinted by the selection (it equals the one with nothing selected), and the
  person's selection is put back.
Path 2, highlight: the boss's round face and an earlier step's top face come out orange;
  without highlight there is no orange.
Path 3, direction [1, 0, 0]: Z stays up (the boss stands on the right of the plate, nothing
  above the plate's left half), as in the software renderer.
Path 4, framing: a 1600 x 200 and a 200 x 900 picture are filled by the part (with the
  software renderer's margin), not a small patch in a wide frame.
"""

import base64
import json

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtGui
from SciForgeTests.gui import harness as h

s = {}


def call(tool, args):
    from sciforge.ai import bridge

    answer = bridge.call(tool, args, from_chat=True)
    print("[SciForge] render scenario: %s -> %s" % (tool, answer["text"][:160].replace("\n", " ")))
    return answer


def picture(answer):
    image = QtGui.QImage()
    image.loadFromData(base64.b64decode(answer.get("image_png_base64") or ""))
    return image


def pixels(image):
    return [
        [QtGui.QColor(image.pixel(x, y)).getRgb()[:3] for x in range(image.width())]
        for y in range(image.height())
    ]


def orange(rows):
    return sum(1 for row in rows for r, g, b in row if r > 200 and 90 < g < 180 and b < 80)


def part_box(rows):
    """The part's pixels (those far from the corner's background): (x0, y0, x1, y1), mask."""
    bg = rows[0][0]
    mask = [[sum(abs(c - k) for c, k in zip(p, bg)) > 60 for p in row] for row in rows]
    xs = [x for row in mask for x, on in enumerate(row) if on]
    ys = [y for y, row in enumerate(mask) if any(row)]
    if not xs:
        return None, mask
    return (min(xs), min(ys), max(xs), max(ys)), mask


def build():
    call("new_design", {"name": "RenderWindow"})
    call("create_sketch", {"plane": "XY", "geometry": [{"rect": [0, 0, 60, 40]}]})
    call("extrude", {"profile": "Sketch1", "distance": 10})
    call(
        "create_sketch",
        {"face": {"normal": [0, 0, 1], "count": 1}, "geometry": [{"circle": [50, 30, 5]}]},
    )
    answer = call("extrude", {"profile": "Sketch2", "distance": 30})
    h.check("the plate with its boss is built", not answer["is_error"], answer["text"])
    Gui.ActiveDocument.ActiveView.viewIsometric()
    Gui.SendMsgToActiveView("ViewFit")


build.wait_ms = 1500


# -- Path 1 -------------------------------------------------------------------------------------
def selection_does_not_tint():
    doc = App.ActiveDocument
    Gui.Selection.clearSelection()
    clean = pixels(picture(call("render", {"renderer": "window", "width": 200, "height": 150})))
    Gui.Selection.addSelection(doc.Name, "Body")
    selected = pixels(picture(call("render", {"renderer": "window", "width": 200, "height": 150})))
    differ = sum(
        1
        for a, b in zip(clean, selected)
        for p, q in zip(a, b)
        if sum(abs(x - y) for x, y in zip(p, q)) > 30
    )
    h.check("a selected body does not tint a plain render", differ < 20, "%d pixels differ" % differ)
    after = [x.ObjectName for x in Gui.Selection.getSelectionEx(doc.Name, 0)]
    h.check("the person's selection is put back", after == ["Body"], after)
    Gui.Selection.clearSelection()


selection_does_not_tint.wait_ms = 800


# -- Path 2 -------------------------------------------------------------------------------------
def highlight_is_orange():
    plain = call("render", {"renderer": "window", "width": 400, "height": 300})
    h.check("no orange without a highlight", orange(pixels(picture(plain))) == 0)
    marked = call(
        "render",
        {
            "renderer": "window",
            "width": 400,
            "height": 300,
            "highlight": {"faces": {"type": "cylinder", "count": 1}},
        },
    )
    count = orange(pixels(picture(marked)))
    h.check(
        "the boss's round face is orange in the window picture",
        count > 300 and "in orange" in marked["text"],
        "%d orange pixels: %s" % (count, marked["text"]),
    )
    edges = call(
        "render",
        {
            "renderer": "window",
            "width": 400,
            "height": 300,
            "highlight": {"edges": {"type": "circle", "at": {"axis": "z", "value": "max"}}},
        },
    )
    count = orange(pixels(picture(edges)))
    h.check("a marked edge is orange too", count > 40, "%d orange pixels" % count)
    earlier = call(
        "render",
        {
            "renderer": "window",
            "width": 400,
            "height": 300,
            "highlight": {"of": "Extrude1", "faces": {"normal": [0, 0, 1], "count": 1}},
        },
    )
    count = orange(pixels(picture(earlier)))
    h.check(
        "an earlier step's face is orange", count > 1000, "%d: %s" % (count, earlier["text"])
    )
    h.check("nothing of the highlight is left in the 3D view", not _leftover())


highlight_is_orange.wait_ms = 800


def _leftover():
    root = Gui.ActiveDocument.ActiveView.getSceneGraph()
    return [
        i for i in range(root.getNumChildren()) if root.getChild(i).getName() == "SciForgeAIHighlight"
    ]


# -- Path 3 -------------------------------------------------------------------------------------
def direction_keeps_z_up():
    view = Gui.ActiveDocument.ActiveView
    view.setCameraOrientation(App.Rotation(App.Vector(1, 1, 0), 70).Q)  # (some roll to undo)
    answer = call("render", {"renderer": "window", "direction": [1, 0, 0], "width": 300, "height": 300})
    box, mask = part_box(pixels(picture(answer)))
    h.check("the part is in the picture", box is not None, answer["text"])
    if box is None:
        return
    x0, y0, x1, y1 = box
    mid_x, boss_rows = (x0 + x1) // 2, y0 + int((y1 - y0) * 0.6)
    above_left = sum(1 for y in range(y0, boss_rows) for x in range(x0, mid_x) if mask[y][x])
    above_right = sum(1 for y in range(y0, boss_rows) for x in range(mid_x, x1) if mask[y][x])
    bottom = [mask[y1 - 2][x] for x in range(x0, x1)]
    h.check(
        "from +X the boss stands up on the right (Z up, Y to the right)",
        above_left < 0.02 * max(above_right, 1) and above_right > 100 and sum(bottom) > 0.8 * len(bottom),
        "box %s, left %d, right %d, bottom row %d/%d"
        % (box, above_left, above_right, sum(bottom), len(bottom)),
    )


direction_keeps_z_up.wait_ms = 800


# -- Path 4 -------------------------------------------------------------------------------------
def framing_fills_the_picture():
    for width, height in ((1600, 200), (200, 900)):
        answer = call("render", {"renderer": "window", "view": "top", "width": width, "height": height})
        image = picture(answer)
        box, _mask = part_box(pixels(image))
        h.check("a %d x %d picture" % (width, height), (image.width(), image.height()) == (width, height))
        if box is None:
            h.check("the part is in the %d x %d picture" % (width, height), False)
            continue
        x0, y0, x1, y1 = box
        # the 60 x 40 plate seen from the top fills the short side, less the margins
        short = (y1 - y0 + 1) / height if width > height else (x1 - x0 + 1) / width
        h.check(
            "the part fills the %d x %d picture" % (width, height),
            short > 0.8,
            "part box %s: %.2f of the short side" % (box, short),
        )
    print("[SciForge] render scenario camera type: %s" % Gui.ActiveDocument.ActiveView.getCameraType())


framing_fills_the_picture.wait_ms = 800


def done():
    h.check("no pop-up left", not h.popups(), h.popups())
    s["done"] = json.dumps(True)


h.run(
    "ai_render_window",
    [build, selection_does_not_tint, highlight_is_orange, direction_keeps_z_up, framing_fills_the_picture, done],
)
