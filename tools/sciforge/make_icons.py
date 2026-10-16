#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
"""Generates SciForge's icon set as SVG files.

    python3 tools/sciforge/make_icons.py            # writes src/Mod/SciForge/sciforge/icons/ui/*.svg

The icons are original artwork drawn from a few shared building blocks
(isometric blocks, an accent face, badges, sketch strokes) so that the whole
set has one consistent look: flat-shaded light-grey solids with a light-blue
"this is what the tool acts on" face, thin light strokes with blue points for
sketch tools, red-orange for constraints, a green plus for "create".
That is the visual language of modern CAD ribbons in general; no icon is
traced from or derived from another product's artwork.

Every icon is drawn on a 48x48 canvas. Edit a recipe below and re-run.
"""

import math
import os
import sys

OUT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "..",
    "src",
    "Mod",
    "SciForge",
    "sciforge",
    "icons",
    "ui",
)

# ---- palette ----------------------------------------------------------------
GREY = ("#ececec", "#d2d4d7", "#aeb2b8")  # top, left, right faces of a neutral solid
BLUE = ("#bfe5ff", "#8fd0ff", "#5aaee8")  # the face/solid the tool creates or changes
DBLUE = ("#7cc4f5", "#4da3e0", "#2f7fbf")
GREEN = "#3cc46a"
ORANGE = "#f2a66a"
PURPLE = ("#e2d4ff", "#c4aef5", "#9f86dd")
GOLD = ("#f6dc8c", "#e8c460", "#c9a23e")
RED = "#ef6f6c"
STROKE = "#dfe3e8"  # sketch lines on the dark ribbon
POINT = "#4fb0f5"
WHITE = "#f5f5f5"
DARK = "#2b313b"

ICONS = {}

# Every primitive records the area it covers, so each icon can be framed tightly
# around its drawing (svg() turns this into the viewBox).
_BOUNDS = []


def _grow(x, y, pad=0.0):
    _BOUNDS.append((x - pad, y - pad, x + pad, y + pad))


def icon(name):
    def register(fn):
        ICONS[name] = fn
        return fn

    return register


# ---- primitives ---------------------------------------------------------------
def P(points):
    return " ".join("%.2f,%.2f" % p for p in points)


def poly(points, fill, extra=""):
    for x, y in points:
        _grow(x, y)
    return '<polygon points="%s" fill="%s" %s/>' % (P(points), fill, extra)


def line(x1, y1, x2, y2, color=STROKE, w=2.0, extra=""):
    _grow(x1, y1, w / 2)
    _grow(x2, y2, w / 2)
    return (
        '<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" stroke="%s" stroke-width="%.2f" '
        'stroke-linecap="round" %s/>' % (x1, y1, x2, y2, color, w, extra)
    )


def path(d, color=STROKE, w=2.0, fill="none", extra=""):
    _path_bounds(d, w / 2)
    return (
        '<path d="%s" stroke="%s" stroke-width="%.2f" fill="%s" stroke-linecap="round" '
        'stroke-linejoin="round" %s/>' % (d, color, w, fill, extra)
    )


def circle(cx, cy, r, fill="none", stroke=None, w=2.0):
    _grow(cx, cy, r + (w / 2 if stroke else 0))
    s = ' stroke="%s" stroke-width="%.2f"' % (stroke, w) if stroke else ""
    return '<circle cx="%.2f" cy="%.2f" r="%.2f" fill="%s"%s/>' % (cx, cy, r, fill, s)


def rect(x, y, w, h, fill, rx=0, extra=""):
    _grow(x, y)
    _grow(x + w, y + h)
    return '<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" rx="%.2f" fill="%s" %s/>' % (
        x,
        y,
        w,
        h,
        rx,
        fill,
        extra,
    )


def ellipse(cx, cy, rx, ry, fill="none", stroke=None, w=2.0):
    _grow(cx - rx, cy - ry)
    _grow(cx + rx, cy + ry)
    s = ' stroke="%s" stroke-width="%.2f"' % (stroke, w) if stroke else ""
    return '<ellipse cx="%.2f" cy="%.2f" rx="%.2f" ry="%.2f" fill="%s"%s/>' % (
        cx,
        cy,
        rx,
        ry,
        fill,
        s,
    )


def _path_bounds(d, pad):
    """Approximate bounds of an SVG path (end and control points)."""
    import re

    tokens = re.findall(r"[MmLlHhVvQqCcAaZz]|-?\d*\.?\d+", d)
    x = y = 0.0
    cmd = "M"
    i = 0
    nums = {"M": 2, "L": 2, "H": 1, "V": 1, "Q": 4, "C": 6, "A": 7, "Z": 0}
    while i < len(tokens):
        if tokens[i].isalpha():
            cmd = tokens[i]
            i += 1
            if cmd in "Zz":
                continue
        n = nums[cmd.upper()]
        args = [float(t) for t in tokens[i : i + n]]
        i += n
        rel = cmd.islower()
        up = cmd.upper()
        if up == "H":
            x = x + args[0] if rel else args[0]
        elif up == "V":
            y = y + args[0] if rel else args[0]
        elif up == "A":
            x, y = (x + args[5], y + args[6]) if rel else (args[5], args[6])
            _grow(x, y, pad + args[0] * 0.3)
            continue
        else:
            for k in range(0, n, 2):
                px, py = (x + args[k], y + args[k + 1]) if rel else (args[k], args[k + 1])
                _grow(px, py, pad)
            x, y = (x + args[-2], y + args[-1]) if rel else (args[-2], args[-1])
        _grow(x, y, pad)


def pt(x, y, color=POINT, r=2.6):
    return rect(x - r, y - r, 2 * r, 2 * r, color, 0.6)


# isometric projection: x goes down-right, y goes down-left, z goes up
ISO_C, ISO_S = math.cos(math.radians(30)), math.sin(math.radians(30))


def iso(x, y, z, ox=24, oy=24, s=1.0):
    return (ox + (x - y) * ISO_C * s, oy + (x + y) * ISO_S * s - z * s)


def block(x, y, z, dx, dy, dz, colors=GREY, ox=24, oy=30, s=1.0):
    """Shaded isometric box; returns svg for its three visible faces."""
    c = lambda a, b, h: iso(a, b, h, ox, oy, s)  # noqa: E731
    top = [c(x, y, z + dz), c(x + dx, y, z + dz), c(x + dx, y + dy, z + dz), c(x, y + dy, z + dz)]
    left = [c(x, y + dy, z), c(x + dx, y + dy, z), c(x + dx, y + dy, z + dz), c(x, y + dy, z + dz)]
    right = [c(x + dx, y, z), c(x + dx, y + dy, z), c(x + dx, y + dy, z + dz), c(x + dx, y, z + dz)]
    return poly(top, colors[0]) + poly(left, colors[1]) + poly(right, colors[2])


def plus_badge(cx=37, cy=37, r=8.5):
    return (
        circle(cx, cy, r, GREEN)
        + rect(cx - 5, cy - 1.4, 10, 2.8, WHITE, 1)
        + rect(cx - 1.4, cy - 5, 2.8, 10, WHITE, 1)
    )


def arrow(x1, y1, x2, y2, color=WHITE, w=2.4, head=5.5):
    ang = math.atan2(y2 - y1, x2 - x1)
    hx1 = x2 - head * math.cos(ang - 0.5)
    hy1 = y2 - head * math.sin(ang - 0.5)
    hx2 = x2 - head * math.cos(ang + 0.5)
    hy2 = y2 - head * math.sin(ang + 0.5)
    bx, by = x2 - head * 0.7 * math.cos(ang), y2 - head * 0.7 * math.sin(ang)
    return line(x1, y1, bx, by, color, w) + poly([(x2, y2), (hx1, hy1), (hx2, hy2)], color)


def svg(body, bounds, min_size=30.0, pad=1.5):
    """Square viewBox around the drawing, so every icon fills its button like the others.
    min_size keeps small glyphs (a point, a short line) from being blown up."""
    if bounds:
        x0 = max(0.0, min(b[0] for b in bounds))
        y0 = max(0.0, min(b[1] for b in bounds))
        x1 = min(48.0, max(b[2] for b in bounds))
        y1 = min(48.0, max(b[3] for b in bounds))
    else:
        x0 = y0 = 0.0
        x1 = y1 = 48.0
    size = max(x1 - x0, y1 - y0, min_size) + 2 * pad
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    box = "%.2f %.2f %.2f %.2f" % (cx - size / 2, cy - size / 2, size, size)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="%s">' % box
        + body
        + "</svg>\n"
    )


# ---- design: create --------------------------------------------------------------
@icon("sketch_create")
def _():
    return (
        path("M8 10 H34 V34 H8 Z", STROKE, 1.8, extra='stroke-dasharray="3 2.5"')
        + path("M12 30 Q14 16 30 14", STROKE, 2)
        + pt(12, 30)
        + pt(30, 14)
        + pt(8, 10, POINT, 2.2)
        + pt(34, 34, POINT, 2.2)
        + plus_badge()
    )


@icon("extrude")
def _():
    return (
        block(0, 0, 0, 20, 20, 3, GREY, 22, 33)
        + block(2, 2, 3, 16, 16, 18, BLUE, 22, 33)
        + arrow(42, 30, 42, 6, WHITE, 2.2)
    )


@icon("revolve")
def _():
    return (
        path("M9 30 Q24 18 39 30 L39 38 Q24 26 9 38 Z", "none", 0, BLUE[1])
        + path("M9 30 Q24 18 39 30", BLUE[0], 3)
        + path("M9 38 Q24 26 39 38", BLUE[2], 3)
        + poly([(39, 30), (44, 33), (44, 41), (39, 38)], GREY[2])
        + path("M10 14 Q24 4 38 14", WHITE, 2)
        + poly([(10, 14), (11, 8), (15, 13)], WHITE)
    )


@icon("sweep")
def _():
    return (
        path("M8 38 C8 22 22 26 22 12 L30 12 C30 30 16 26 16 38 Z", "none", 0, BLUE[1])
        + path("M8 38 C8 22 22 26 22 12", BLUE[2], 2)
        + rect(22, 8, 8, 4, BLUE[0])
        + path("M36 40 C36 26 42 22 42 10", STROKE, 1.6, extra='stroke-dasharray="3 2"')
    )


@icon("loft")
def _():
    return (
        poly([(10, 36), (26, 42), (38, 36), (22, 30)], GREY[1])
        + poly([(10, 36), (16, 12), (30, 14), (26, 42)], BLUE[1])
        + poly([(26, 42), (30, 14), (36, 12), (38, 36)], BLUE[2])
        + poly([(16, 12), (22, 8), (36, 12), (30, 14)], BLUE[0])
    )


@icon("hole")
def _():
    return (
        block(0, 0, 0, 22, 22, 18, GREY, 24, 30)
        + ellipse(24, 21, 7, 4, DBLUE[2])
        + ellipse(24, 20, 7, 4, DARK)
        + ellipse(24, 21.5, 5.6, 2.4, DBLUE[1])
    )


@icon("thread")
def _():
    body = rect(18, 8, 12, 32, GREY[1], 2)
    for y in range(10, 38, 5):
        body += line(17, y + 3, 31, y, BLUE[2], 2.4)
    return body


@icon("pattern_rect")
def _():
    out = ""
    for x, y in ((8, 8), (30, 8), (8, 30), (30, 30)):
        out += rect(x, y, 10, 10, BLUE[1], 1.5)
    return (
        line(18, 13, 30, 13, STROKE, 1.6)
        + line(13, 18, 13, 30, STROKE, 1.6)
        + line(35, 18, 35, 30, STROKE, 1.6)
        + line(18, 35, 30, 35, STROKE, 1.6)
        + out
    )


@icon("pattern_circ")
def _():
    out = circle(24, 24, 13, "none", STROKE, 1.4)
    for k in range(6):
        a = math.radians(90 + 60 * k)
        out += circle(24 + 13 * math.cos(a), 24 - 13 * math.sin(a), 4.2, BLUE[1])
    return out


@icon("mirror")
def _():
    return (
        poly([(22, 8), (22, 40), (8, 40)], BLUE[1])
        + poly([(26, 8), (26, 40), (40, 40)], GREY[1])
        + line(24, 4, 24, 44, STROKE, 1.4, 'stroke-dasharray="3 2"')
    )


@icon("box")
def _():
    return block(0, 0, 0, 20, 20, 18, BLUE, 24, 32)


@icon("cylinder")
def _():
    return (
        ellipse(24, 36, 13, 6, BLUE[2])
        + rect(11, 14, 26, 22, BLUE[1])
        + rect(24, 14, 13, 22, BLUE[2])
        + ellipse(24, 14, 13, 6, BLUE[0])
    )


@icon("sphere")
def _():
    return '<defs><radialGradient id="g" cx="0.35" cy="0.35" r="0.75"><stop offset="0" stop-color="%s"/>' '<stop offset="1" stop-color="%s"/></radialGradient></defs>' % (
        BLUE[0],
        BLUE[2],
    ) + circle(
        24, 24, 15, "url(#g)"
    )


@icon("torus")
def _():
    return (
        ellipse(24, 25, 17, 9, BLUE[1])
        + ellipse(24, 22, 16, 7.5, BLUE[0])
        + ellipse(24, 24, 7, 3.2, DARK)
    )


@icon("coil")
def _():
    out = ""
    for y in range(12, 38, 6):
        out += path("M10 %d Q24 %d 38 %d" % (y + 4, y - 4, y), BLUE[1], 3.4)
    return out


@icon("pipe")
def _():
    return (
        path("M8 36 Q8 12 36 12", BLUE[2], 10)
        + path("M8 36 Q8 12 36 12", BLUE[1], 6)
        + ellipse(38, 12, 2.5, 5, BLUE[0])
    )


@icon("thicken")
def _():
    return path("M8 26 Q24 14 40 26", STROKE, 1.6, extra='stroke-dasharray="3 2"') + path(
        "M8 32 Q24 20 40 32 L40 38 Q24 26 8 38 Z", "none", 0, BLUE[1]
    )


@icon("boundary_fill")
def _():
    return (
        poly([(8, 30), (24, 38), (40, 30), (24, 22)], BLUE[1])
        + line(8, 12, 8, 34, ORANGE, 2)
        + line(40, 12, 40, 34, ORANGE, 2)
        + line(8, 14, 24, 6, STROKE, 1.4)
        + line(24, 6, 40, 14, STROKE, 1.4)
    )


@icon("rib")
def _():
    return (
        block(0, 0, 0, 22, 4, 18, GREY, 24, 32)
        + block(0, 4, 0, 4, 18, 18, GREY, 24, 32)
        + poly([iso(4, 4, 14, 24, 32), iso(4, 18, 0, 24, 32), iso(4, 4, 0, 24, 32)], BLUE[1])
    )


@icon("web")
def _():
    return (
        rect(8, 8, 32, 32, "none", 0, 'stroke="%s" stroke-width="3"' % GREY[1])
        + line(10, 10, 38, 38, BLUE[1], 3)
        + line(38, 10, 10, 38, BLUE[1], 3)
    )


@icon("emboss")
def _():
    return (
        block(0, 0, 0, 24, 24, 6, GREY, 24, 30)
        + '<text x="24" y="27" font-family="sans-serif" font-weight="bold" font-size="13" '
        'text-anchor="middle" fill="%s">Aa</text>' % BLUE[2]
    )


@icon("derive")
def _():
    return block(0, 0, 0, 16, 16, 14, GREY, 28, 30) + arrow(6, 34, 18, 26, WHITE, 2.4)


# ---- design: modify --------------------------------------------------------------
@icon("press_pull")
def _():
    return (
        block(0, 0, 0, 22, 22, 8, GREY, 24, 34)
        + block(0, 0, 8, 22, 22, 3, BLUE, 24, 34)
        + arrow(24, 22, 24, 4, WHITE, 2.4)
    )


@icon("fillet")
def _():
    o = (24, 30)
    c = lambda x, y, z: iso(x, y, z, *o)  # noqa: E731
    out = block(0, 0, 0, 20, 20, 12, GREY, *o)
    # rounded top-front edge, drawn as a blue curved band
    pts = [c(20, 0, 12)] + [
        c(20 - 6 + 6 * math.sin(t), 0, 12 - 6 + 6 * math.cos(t))
        for t in [i * math.pi / 2 / 8 for i in range(9)]
    ]
    out += block(0, 0, 12, 14, 20, 6, GREY, *o)
    band = [c(14, 0, 18), c(14, 20, 18)]
    band += [
        c(14 + 6 * math.sin(t), 20, 12 + 6 * math.cos(t))
        for t in [i * math.pi / 2 / 8 for i in range(9)]
    ]
    band += [
        c(14 + 6 * math.sin(t), 0, 12 + 6 * math.cos(t))
        for t in [i * math.pi / 2 / 8 for i in reversed(range(9))]
    ]
    out += poly(band, BLUE[1])
    side = [c(14, 20, 12), c(14, 20, 18)] + [
        c(14 + 6 * math.sin(t), 20, 12 + 6 * math.cos(t))
        for t in [i * math.pi / 2 / 8 for i in range(9)]
    ]
    out += poly(side, GREY[1])
    del pts
    return out


@icon("chamfer")
def _():
    o = (24, 30)
    c = lambda x, y, z: iso(x, y, z, *o)  # noqa: E731
    return (
        block(0, 0, 0, 20, 20, 12, GREY, *o)
        + block(0, 0, 12, 14, 20, 6, GREY, *o)
        + poly([c(14, 0, 18), c(14, 20, 18), c(20, 20, 12), c(20, 0, 12)], BLUE[1])
        + poly([c(14, 20, 12), c(14, 20, 18), c(20, 20, 12)], GREY[1])
    )


@icon("shell")
def _():
    o = (24, 30)
    c = lambda x, y, z: iso(x, y, z, *o)  # noqa: E731
    return (
        block(0, 0, 0, 22, 22, 16, GREY, *o)
        + poly([c(3, 3, 16), c(19, 3, 16), c(19, 19, 16), c(3, 19, 16)], DARK)
        + poly([c(3, 3, 16), c(19, 3, 16), c(19, 3, 4), c(3, 3, 4)], BLUE[2])
        + poly([c(3, 3, 16), c(3, 19, 16), c(3, 19, 4), c(3, 3, 4)], BLUE[1])
        + poly([c(3, 3, 4), c(19, 3, 4), c(19, 19, 4), c(3, 19, 4)], BLUE[0])
    )


@icon("draft")
def _():
    return (
        poly([(10, 40), (38, 40), (32, 10), (16, 10)], GREY[1])
        + poly([(32, 10), (38, 40), (42, 38), (36, 10)], BLUE[1])
        + line(36, 8, 42, 40, STROKE, 1.2, 'stroke-dasharray="2 2"')
    )


@icon("scale")
def _():
    return (
        block(0, 0, 0, 10, 10, 10, GREY, 18, 36)
        + path("M14 8 H40 V34", STROKE, 1.6, extra='stroke-dasharray="3 2"')
        + arrow(24, 24, 38, 10, WHITE, 2.2)
    )


@icon("combine")
def _():
    return block(0, 0, 0, 14, 14, 14, BLUE, 18, 36) + block(0, 0, 0, 14, 14, 14, BLUE, 30, 22)


@icon("offset_face")
def _():
    return block(0, 0, 0, 20, 20, 14, GREY, 24, 32) + poly(
        [
            iso(22, 0, 0, 24, 32),
            iso(22, 20, 0, 24, 32),
            iso(22, 20, 14, 24, 32),
            iso(22, 0, 14, 24, 32),
        ],
        BLUE[1],
        'fill-opacity="0.85"',
    )


@icon("replace_face")
def _():
    return (
        block(0, 0, 0, 20, 20, 10, GREY, 24, 34)
        + path("M8 14 Q24 2 40 14", BLUE[1], 4)
        + arrow(24, 12, 24, 20, WHITE, 2)
    )


@icon("split_face")
def _():
    return (
        block(0, 0, 0, 20, 20, 14, GREY, 24, 32)
        + poly(
            [
                iso(0, 0, 14, 24, 32),
                iso(10, 0, 14, 24, 32),
                iso(10, 20, 14, 24, 32),
                iso(0, 20, 14, 24, 32),
            ],
            BLUE[0],
        )
        + line(*iso(10, 0, 14, 24, 32), *iso(10, 20, 14, 24, 32), BLUE[2], 2)
    )


@icon("split_body")
def _():
    return (
        block(0, 0, 0, 20, 20, 6, GREY, 24, 38)
        + block(0, 0, 9, 20, 20, 6, BLUE, 24, 38)
        + line(4, 26, 44, 26, BLUE[2], 2)
    )


@icon("silhouette_split")
def _():
    return (
        ellipse(24, 30, 14, 8, GREY[2])
        + ellipse(24, 22, 14, 8, BLUE[1])
        + line(8, 26, 40, 26, STROKE, 1.4, 'stroke-dasharray="3 2"')
    )


@icon("move")
def _():
    return (
        arrow(24, 24, 24, 4)
        + arrow(24, 24, 24, 44)
        + arrow(24, 24, 4, 24)
        + arrow(24, 24, 44, 24)
        + circle(24, 24, 3, WHITE)
    )


@icon("align")
def _():
    return (
        rect(8, 8, 3, 32, STROKE)
        + rect(13, 12, 22, 9, BLUE[1], 1.5)
        + rect(13, 26, 14, 9, BLUE[1], 1.5)
    )


@icon("delete")
def _():
    return line(12, 12, 36, 36, RED, 5) + line(36, 12, 12, 36, RED, 5)


@icon("remove")
def _():
    return block(0, 0, 0, 14, 14, 12, GREY, 18, 32) + arrow(26, 24, 44, 24, RED, 2.6)


@icon("material")
def _():
    out = circle(24, 24, 15, WHITE)
    for i in range(4):
        for j in range(4):
            if (i + j) % 2:
                out += rect(9 + i * 7.5, 9 + j * 7.5, 7.5, 7.5, "#5b6270")
    return (
        '<clipPath id="c"><circle cx="24" cy="24" r="15"/></clipPath>'
        + '<g clip-path="url(#c)">'
        + out
        + "</g>"
        + circle(24, 24, 15, "none", "#9aa3b0", 1)
    )


@icon("appearance")
def _():
    colors = ["#ef6f6c", "#f2c14e", "#3cc46a", "#4fb0f5", "#9f86dd", "#f28fcf"]
    out = ""
    for k, col in enumerate(colors):
        a0, a1 = math.radians(60 * k), math.radians(60 * (k + 1))
        out += '<path d="M24 24 L%.2f %.2f A15 15 0 0 1 %.2f %.2f Z" fill="%s"/>' % (
            24 + 15 * math.cos(a0),
            24 + 15 * math.sin(a0),
            24 + 15 * math.cos(a1),
            24 + 15 * math.sin(a1),
            col,
        )
    return out


@icon("parameters")
def _():
    return (
        '<text x="24" y="32" font-family="serif" font-style="italic" font-size="24" '
        'text-anchor="middle" fill="%s">fx</text>' % STROKE
    )


@icon("compute")
def _():
    return path("M36 16 A13 13 0 1 0 38 28", BLUE[1], 3.4) + poly(
        [(36, 6), (40, 18), (28, 17)], BLUE[1]
    )


# ---- construct --------------------------------------------------------------------
def _plane(ox, oy, color, w=14, h=26, skew=6):
    return poly([(ox, oy + skew), (ox + w, oy), (ox + w, oy + h), (ox, oy + h + skew)], color)


@icon("offset_plane")
def _():
    return _plane(8, 10, GREY[1]) + _plane(26, 6, BLUE[1]) + arrow(16, 24, 30, 22, WHITE, 1.8, 4)


@icon("plane_angle")
def _():
    return (
        _plane(8, 12, GREY[1])
        + poly([(22, 34), (40, 12), (42, 20), (24, 42)], BLUE[1])
        + path("M18 30 A10 10 0 0 1 26 22", STROKE, 1.4)
    )


@icon("tangent_plane")
def _():
    return circle(18, 26, 11, GREY[1]) + poly([(26, 6), (34, 4), (34, 40), (26, 44)], BLUE[1])


@icon("midplane")
def _():
    return _plane(4, 10, GREY[1], 10) + _plane(34, 6, GREY[1], 10) + _plane(19, 8, BLUE[1], 10)


@icon("plane_perp")
def _():
    return poly([(6, 32), (28, 24), (42, 30), (20, 40)], GREY[1]) + poly(
        [(20, 32), (20, 8), (34, 4), (34, 28)], BLUE[1]
    )


@icon("plane_two_edges")
def _():
    return (
        _plane(12, 8, BLUE[1], 22, 28)
        + line(12, 14, 12, 42, ORANGE, 3)
        + line(34, 8, 34, 36, ORANGE, 3)
    )


@icon("plane_three_points")
def _():
    return (
        _plane(10, 8, BLUE[1], 26, 28)
        + pt(14, 18, ORANGE, 3)
        + pt(32, 14, ORANGE, 3)
        + pt(22, 36, ORANGE, 3)
    )


@icon("plane_along_path")
def _():
    return path("M6 40 Q20 6 42 12", ORANGE, 2.4) + _plane(16, 10, BLUE[1], 12, 22)


@icon("axis")
def _():
    return (
        ellipse(24, 34, 11, 5, GREY[2])
        + rect(13, 14, 22, 20, GREY[1])
        + ellipse(24, 14, 11, 5, GREY[0])
        + line(24, 2, 24, 46, ORANGE, 2.4)
    )


@icon("axis_two_points")
def _():
    return line(8, 40, 40, 8, ORANGE, 2.4) + pt(14, 34, BLUE[2], 3.2) + pt(34, 14, BLUE[2], 3.2)


@icon("axis_edge")
def _():
    return block(0, 0, 0, 18, 18, 16, GREY, 24, 32) + line(
        *iso(18, 0, -6, 24, 32), *iso(18, 0, 24, 24, 32), ORANGE, 2.6
    )


@icon("point")
def _():
    return block(0, 0, 0, 18, 18, 16, GREY, 24, 32) + circle(*iso(18, 18, 16, 24, 32), 4, ORANGE)


@icon("ucs")
def _():
    return (
        arrow(10, 38, 40, 38, "#ef6f6c", 2.4)
        + arrow(10, 38, 10, 8, "#3cc46a", 2.4)
        + arrow(10, 38, 28, 22, "#4fb0f5", 2.4)
    )


# ---- inspect -----------------------------------------------------------------------
@icon("measure")
def _():
    out = rect(6, 26, 36, 12, GOLD[1], 1.5)
    for i, x in enumerate(range(9, 41, 4)):
        out += line(x, 26, x, 30 if i % 2 else 33, "#7a5b17", 1.4)
    return out + arrow(24, 16, 42, 16, WHITE, 1.8, 4) + arrow(24, 16, 6, 16, WHITE, 1.8, 4)


@icon("section")
def _():
    o = (24, 30)
    c = lambda x, y, z: iso(x, y, z, *o)  # noqa: E731
    return (
        block(0, 0, 0, 20, 20, 16, GREY, *o)
        + poly(
            [c(10, 0, 0), c(10, 20, 0), c(10, 20, 16), c(10, 0, 16)], BLUE[1], 'fill-opacity="0.9"'
        )
        + path("M6 6 H42 V42 H6 Z", BLUE[1], 1.6, extra='stroke-dasharray="4 3"')
    )


@icon("interference")
def _():
    return (
        rect(8, 10, 20, 20, BLUE[1], 2)
        + rect(20, 18, 20, 20, GREY[1], 2)
        + rect(20, 18, 8, 12, RED)
    )


@icon("center_of_mass")
def _():
    return circle(
        24, 24, 13, "none", STROKE, 2
    ) + '<path d="M24 11 A13 13 0 0 1 37 24 L24 24 Z" ' 'fill="%s"/><path d="M24 37 A13 13 0 0 1 11 24 L24 24 Z" fill="%s"/>' % (
        STROKE,
        STROKE,
    )


@icon("curvature")
def _():
    out = path("M6 36 Q24 4 42 36", BLUE[1], 2.4)
    for k in range(1, 8):
        t = k / 8
        x = (1 - t) ** 2 * 6 + 2 * (1 - t) * t * 24 + t * t * 42
        y = (1 - t) ** 2 * 36 + 2 * (1 - t) * t * 4 + t * t * 36
        out += line(x, y, x, y - 8 - 6 * math.sin(math.pi * t), ORANGE, 1.2)
    return out


@icon("zebra")
def _():
    out = circle(24, 24, 15, "#5b6270")
    for k in range(-3, 4):
        off = k * 4.2  # stripe centre distance from the middle, perpendicular to stripes
        half = math.sqrt(max(0.0, 15 * 15 - off * off)) - 0.5
        a = math.radians(-25)
        cx, cy = 24 - off * math.sin(a), 24 + off * math.cos(a)
        out += line(
            cx - half * math.cos(a),
            cy - half * math.sin(a),
            cx + half * math.cos(a),
            cy + half * math.sin(a),
            STROKE,
            2.2,
        )
    return out


# ---- insert ------------------------------------------------------------------------
@icon("insert_component")
def _():
    return (
        block(0, 0, 0, 16, 16, 14, GREY, 30, 28)
        + path("M6 36 Q8 24 20 26", WHITE, 2.4)
        + poly([(20, 22), (24, 27), (18, 30)], WHITE)
    )


@icon("canvas")
def _():
    return (
        rect(6, 8, 36, 30, "#5aaee8", 2)
        + poly([(6, 38), (18, 22), (28, 32), (34, 26), (42, 34), (42, 38)], "#2f7fbf")
        + circle(32, 16, 3.5, "#f6dc8c")
    )


@icon("insert_mesh")
def _():
    pts = [(24, 6), (40, 14), (40, 32), (24, 42), (8, 32), (8, 14)]
    out = poly(pts, GOLD[1])
    for a in pts:
        out += line(24, 24, a[0], a[1], GOLD[2], 1.2)
    return out + line(8, 14, 40, 32, GOLD[2], 1.2) + line(40, 14, 8, 32, GOLD[2], 1.2)


@icon("insert_svg")
def _():
    return (
        rect(10, 6, 26, 34, WHITE, 2)
        + '<text x="23" y="30" font-family="sans-serif" font-size="10" '
        'font-weight="bold" text-anchor="middle" fill="%s">SVG</text>' % DBLUE[2]
    )


@icon("insert_dxf")
def _():
    return (
        rect(10, 6, 26, 34, WHITE, 2)
        + '<text x="23" y="30" font-family="sans-serif" font-size="10" '
        'font-weight="bold" text-anchor="middle" fill="%s">DXF</text>' % DBLUE[2]
    )


@icon("decal")
def _():
    return block(0, 0, 0, 20, 20, 14, GREY, 24, 32) + poly(
        [
            iso(20, 4, 3, 24, 32),
            iso(20, 16, 3, 24, 32),
            iso(20, 16, 11, 24, 32),
            iso(20, 4, 11, 24, 32),
        ],
        "#f28fcf",
    )


# ---- assemble / select ----------------------------------------------------------------
@icon("new_component")
def _():
    return (
        block(0, 0, 0, 10, 10, 9, GREY, 16, 38)
        + block(0, 0, 0, 10, 10, 9, GREY, 32, 38)
        + block(0, 0, 0, 10, 10, 9, GREY, 24, 24)
        + plus_badge(38, 12, 7)
    )


@icon("joint")
def _():
    return (
        block(0, 0, 0, 12, 12, 10, GREY, 16, 38)
        + block(0, 0, 0, 12, 12, 10, BLUE, 32, 20)
        + circle(26, 30, 4, ORANGE)
        + path("M20 32 Q26 30 30 24", STROKE, 1.6)
    )


def _two_blocks():
    return block(0, 0, 0, 12, 12, 10, GREY, 16, 38) + block(0, 0, 0, 12, 12, 10, BLUE, 32, 20)


@icon("joint_revolute")
def _():
    # a hinge: the two blocks and a curved turn arrow about an axis
    return (
        _two_blocks()
        + circle(26, 30, 3.5, ORANGE)
        + path("M17 24 A10 10 0 0 1 35 24", STROKE, 1.8)
        + poly([(35, 24), (31, 20), (31, 27)], STROKE)
    )


@icon("joint_slider")
def _():
    return (
        _two_blocks()
        + arrow(14, 10, 38, 10, STROKE, 2.0, 4.5)
        + arrow(38, 10, 14, 10, STROKE, 2.0, 4.5)
    )


@icon("joint_cylindrical")
def _():
    return (
        _two_blocks()
        + path("M17 24 A10 10 0 0 1 35 24", STROKE, 1.8)
        + poly([(35, 24), (31, 20), (31, 27)], STROKE)
        + arrow(26, 20, 26, 6, STROKE, 2.0, 4.5)
    )


@icon("joint_pinslot")
def _():
    return (
        _two_blocks()
        + rect(14, 7, 24, 7, "none", 3.5, 'stroke="%s" stroke-width="1.8"' % STROKE)
        + circle(26, 10.5, 2.6, ORANGE)
        + path("M20 32 A6 6 0 0 1 32 32", STROKE, 1.6)
    )


@icon("joint_planar")
def _():
    return (
        _two_blocks()
        + poly(
            [(10, 14), (30, 8), (44, 12), (24, 18)],
            "none",
            'stroke="%s" stroke-width="1.8"' % STROKE,
        )
        + arrow(22, 13, 36, 10, STROKE, 1.8, 4)
    )


@icon("joint_ball")
def _():
    return (
        _two_blocks()
        + circle(26, 30, 5, ORANGE)
        + path("M15 20 A12 12 0 0 1 37 20", STROKE, 1.6)
        + path("M17 36 A11 11 0 0 0 35 36", STROKE, 1.6)
    )


@icon("joint_asbuilt")
def _():
    # the two blocks stay where they are: a tick where the joint goes
    return _two_blocks() + circle(26, 30, 4, ORANGE) + path("M20 10 L25 15 L34 5", GREEN, 2.4)


@icon("joint_origin")
def _():
    return (
        block(0, 0, 0, 16, 16, 12, GREY, 24, 36)
        + arrow(24, 24, 40, 24, "#ef6f6c", 2.2)
        + arrow(24, 24, 24, 8, "#3cc46a", 2.2)
        + arrow(24, 24, 12, 32, "#4fb0f5", 2.2)
    )


@icon("rigid_group")
def _():
    return (
        block(0, 0, 0, 10, 10, 9, GREY, 16, 38)
        + block(0, 0, 0, 10, 10, 9, GREY, 32, 38)
        + block(0, 0, 0, 10, 10, 9, BLUE, 24, 24)
        + rect(
            8, 6, 32, 36, "none", 3, 'stroke="%s" stroke-width="2" stroke-dasharray="4 3"' % ORANGE
        )
    )


@icon("ground")
def _():
    # a body held down: an anchor badge
    return (
        block(0, 0, 0, 16, 16, 12, GREY, 22, 32)
        + line(38, 24, 38, 42, ORANGE, 2.4)
        + path("M30 36 Q38 46 46 36", ORANGE, 2.4)
        + circle(38, 21, 3, "none", ORANGE, 2.2)
        + line(32, 28, 44, 28, ORANGE, 2.4)
    )


@icon("drive_joints")
def _():
    return (
        _two_blocks()
        + path("M14 10 A12 12 0 0 1 38 10", STROKE, 1.8)
        + poly([(38, 10), (34, 5), (33, 12)], STROKE)
        + poly([(24, 6), (24, 14), (31, 10)], GREEN)
    )


@icon("position")
def _():
    # a captured position: a block with a pin above it
    return (
        block(0, 0, 0, 16, 16, 12, GREY, 22, 34)
        + circle(36, 12, 5, ORANGE)
        + poly([(31, 14), (41, 14), (36, 24)], ORANGE)
    )


@icon("motion_link")
def _():
    # two turning joints tied together: two dials and a link between them
    return (
        circle(14, 30, 8, "none", STROKE, 2.0)
        + circle(34, 18, 8, "none", STROKE, 2.0)
        + circle(14, 30, 2.5, ORANGE)
        + circle(34, 18, 2.5, ORANGE)
        + line(19, 26, 29, 21, GREEN, 2.6)
        + poly([(29, 21), (24, 21), (27, 25)], GREEN)
    )


@icon("contact_set")
def _():
    # two blocks touching, a spark where they meet
    return (
        block(0, 0, 0, 12, 12, 10, GREY, 15, 36)
        + block(0, 0, 0, 12, 12, 10, BLUE, 33, 36)
        + poly(
            [(24, 8), (27, 16), (34, 14), (28, 20), (31, 27), (24, 22), (17, 27), (20, 20)], ORANGE
        )
    )


@icon("motion_study")
def _():
    # a graph of a joint's value over the steps, with a play mark
    return (
        line(8, 40, 42, 40, STROKE, 1.8)
        + line(8, 40, 8, 8, STROKE, 1.8)
        + path("M8 36 L18 30 L28 14 L40 18", ORANGE, 2.2)
        + circle(18, 30, 2.4, POINT)
        + circle(28, 14, 2.4, POINT)
        + poly([(32, 26), (32, 38), (42, 32)], GREEN)
    )


@icon("component_drag")
def _():
    # a component and the hand-drag arrow
    return (
        block(0, 0, 0, 14, 14, 11, BLUE, 20, 34)
        + arrow(30, 22, 44, 12, STROKE, 2.2, 5)
        + _cursor(28, 22)
    )


@icon("select")
def _():
    return rect(
        6, 6, 32, 28, "none", 0, 'stroke="%s" stroke-width="2" stroke-dasharray="4 3"' % GREEN
    ) + poly([(28, 22), (28, 44), (33, 39), (37, 46), (40, 44), (36, 37), (43, 37)], WHITE)


def _cursor(x=28, y=22):
    """The select arrow (shared by the selection icons)."""
    return poly(
        [
            (x, y),
            (x, y + 22),
            (x + 5, y + 17),
            (x + 9, y + 24),
            (x + 12, y + 22),
            (x + 8, y + 15),
            (x + 15, y + 15),
        ],
        WHITE,
    )


@icon("select_window")
def _():
    # Window selection: a solid box, the small part fully inside it is the one taken.
    return (
        rect(5, 7, 30, 26, "none", 0, 'stroke="%s" stroke-width="2"' % DBLUE[0])
        + block(0, 0, 0, 9, 9, 8, BLUE, 20, 26, 0.8)
        + _cursor(30, 26)
    )


@icon("select_freeform")
def _():
    # Freeform (lasso) selection: a loose loop drawn around the part.
    return (
        path("M8 14 C 4 26, 14 38, 26 34 C 36 31, 40 20, 34 12 C 28 5, 12 4, 8 14 Z", DBLUE[0], 2)
        + block(0, 0, 0, 8, 8, 7, BLUE, 21, 24, 0.75)
        + _cursor(30, 26)
    )


@icon("select_paint")
def _():
    # Paint selection: a brush stroke across the part.
    return (
        block(0, 0, 0, 16, 16, 12, GREY, 22, 32)
        + path("M6 30 C 14 18, 24 30, 40 14", DBLUE[0], 5)
        + _cursor(28, 24)
    )


@icon("select_through")
def _():
    # Select Through: the front face see-through, the hidden edges dashed.
    return (
        block(0, 0, 0, 18, 18, 14, GREY, 24, 32)
        + line(24, 46, 24, 24, DBLUE[0], 1.8, 'stroke-dasharray="3 2"')
        + line(24, 24, 8, 15, DBLUE[0], 1.8, 'stroke-dasharray="3 2"')
        + line(24, 24, 40, 15, DBLUE[0], 1.8, 'stroke-dasharray="3 2"')
    )


@icon("select_filter")
def _():
    # Selection filters: a funnel.
    return path("M8 8 H40 L28 24 V40 L20 36 V24 Z", STROKE, 2.2, DBLUE[1])


@icon("select_priority")
def _():
    # Selection priority: three kinds stacked, the first one lit.
    return (
        rect(10, 8, 28, 8, DBLUE[1], 2)
        + rect(10, 20, 28, 8, "#5c6675", 2)
        + rect(10, 32, 28, 8, "#5c6675", 2)
    )


@icon("select_other")
def _():
    # Select Other: a short list beside the pointer.
    return (
        rect(6, 10, 22, 28, "#454f61", 2, 'stroke="%s" stroke-width="1.5"' % STROKE)
        + rect(9, 14, 16, 5, DBLUE[1], 1)
        + rect(9, 22, 16, 5, "#7d8593", 1)
        + rect(9, 30, 16, 5, "#7d8593", 1)
        + _cursor(28, 20)
    )


@icon("select_body")
def _():
    return block(0, 0, 0, 18, 18, 14, BLUE, 24, 32)


@icon("select_face")
def _():
    return block(0, 0, 0, 18, 18, 14, GREY, 24, 32) + poly(
        [
            iso(0, 0, 14, 24, 32),
            iso(18, 0, 14, 24, 32),
            iso(18, 18, 14, 24, 32),
            iso(0, 18, 14, 24, 32),
        ],
        BLUE[1],
    )


@icon("select_edge")
def _():
    a, b = iso(18, 0, 14, 24, 32), iso(18, 18, 14, 24, 32)
    return block(0, 0, 0, 18, 18, 14, GREY, 24, 32) + line(a[0], a[1], b[0], b[1], DBLUE[0], 3.2)


@icon("select_vertex")
def _():
    x, y = iso(18, 18, 14, 24, 32)
    return block(0, 0, 0, 18, 18, 14, GREY, 24, 32) + circle(x, y, 4, DBLUE[0], WHITE, 1.5)


@icon("select_sketch")
def _():
    return line(8, 36, 24, 12) + line(24, 12, 40, 36) + pt(8, 36) + pt(24, 12) + pt(40, 36)


@icon("select_work")
def _():
    return poly(
        [(10, 34), (22, 10), (40, 10), (28, 34)], "none", 'stroke="%s" stroke-width="2"' % STROKE
    ) + line(6, 40, 42, 40, DBLUE[0], 2)


# ---- sketch ---------------------------------------------------------------------------
@icon("sk_line")
def _():
    return line(8, 36, 40, 12) + pt(8, 36) + pt(40, 12)


@icon("sk_rectangle")
def _():
    return path("M9 12 H39 V36 H9 Z") + pt(9, 12) + pt(39, 36)


@icon("sk_circle")
def _():
    return circle(24, 24, 15, "none", STROKE, 2) + pt(24, 24) + line(24, 24, 35, 13, POINT, 1.6)


@icon("sk_arc")
def _():
    return path("M8 36 A17 17 0 0 1 40 30") + pt(8, 36) + pt(40, 30) + pt(25, 14)


@icon("sk_polygon")
def _():
    pts = [
        (
            24 + 15 * math.cos(math.radians(90 + 60 * k)),
            24 - 15 * math.sin(math.radians(90 + 60 * k)),
        )
        for k in range(6)
    ]
    return path("M" + " L".join("%.1f %.1f" % p for p in pts) + " Z") + pt(24, 24)


@icon("sk_ellipse")
def _():
    return ellipse(24, 24, 17, 10, "none", STROKE, 2) + pt(24, 24) + pt(41, 24, POINT, 2.2)


@icon("sk_slot")
def _():
    return path("M16 16 H32 A8 8 0 0 1 32 32 H16 A8 8 0 0 1 16 16 Z") + pt(16, 24) + pt(32, 24)


@icon("sk_spline")
def _():
    return path("M6 38 C14 6 26 42 42 10") + pt(6, 38) + pt(18, 22) + pt(30, 26) + pt(42, 10)


@icon("sk_conic")
def _():
    return path("M8 38 Q16 8 40 10") + pt(8, 38) + pt(40, 10) + pt(16, 8, ORANGE, 2.2)


@icon("sk_point")
def _():
    return (
        line(24, 10, 24, 38, STROKE, 1.6)
        + line(10, 24, 38, 24, STROKE, 1.6)
        + pt(24, 24, POINT, 3.4)
    )


@icon("sk_text")
def _():
    return (
        '<text x="24" y="36" font-family="sans-serif" font-size="30" text-anchor="middle" '
        'fill="none" stroke="%s" stroke-width="1.6">A</text>' % STROKE
    )


@icon("sk_mirror")
def _():
    return (
        path("M20 10 L20 38 L8 38 Z")
        + path("M28 10 L28 38 L40 38 Z", POINT)
        + line(24, 4, 24, 44, STROKE, 1.2, 'stroke-dasharray="3 2"')
    )


@icon("sk_pattern_circ")
def _():
    out = circle(24, 24, 13, "none", STROKE, 1.2)
    for k in range(6):
        a = math.radians(60 * k)
        out += circle(24 + 13 * math.cos(a), 24 + 13 * math.sin(a), 3.6, "none", POINT, 1.8)
    return out


@icon("sk_pattern_rect")
def _():
    out = ""
    for x in (10, 30):
        for y in (10, 30):
            out += path("M%d %d h8 v8 h-8 Z" % (x, y), POINT, 1.8)
    return out + line(18, 14, 30, 14, STROKE, 1.2, 'stroke-dasharray="2 2"')


@icon("sk_dimension")
def _():
    return (
        line(8, 10, 8, 40, STROKE, 1.6)
        + line(40, 10, 40, 40, STROKE, 1.6)
        + arrow(24, 22, 9, 22, POINT, 2, 5)
        + arrow(24, 22, 39, 22, POINT, 2, 5)
    )


@icon("sk_fillet")
def _():
    return path("M8 40 V24 A14 14 0 0 1 22 10 H40") + path(
        "M8 18 V10 H16", STROKE, 1.2, extra='stroke-dasharray="2 2"'
    )


@icon("sk_chamfer")
def _():
    return path("M8 40 V20 L18 10 H40") + path(
        "M8 18 V10 H16", STROKE, 1.2, extra='stroke-dasharray="2 2"'
    )


@icon("sk_trim")
def _():
    return (
        line(4, 12, 44, 12, STROKE, 1.6, 'stroke-dasharray="3 2"')
        + circle(18, 36, 5, "none", WHITE, 2.4)
        + circle(30, 36, 5, "none", WHITE, 2.4)
        + line(21, 32, 34, 8, WHITE, 2.6)
        + line(27, 32, 14, 8, WHITE, 2.6)
    )


@icon("sk_offset")
def _():
    return path("M40 10 H18 A10 10 0 0 0 18 30 H40", POINT) + path(
        "M40 18 H18 A2 2 0 0 0 18 22 H40"
    )


@icon("sk_extend")
def _():
    return (
        line(40, 6, 40, 42, STROKE, 2)
        + line(8, 24, 26, 24)
        + line(26, 24, 40, 24, POINT, 2, 'stroke-dasharray="3 2"')
    )


@icon("sk_break")
def _():
    return line(6, 30, 22, 22) + line(26, 20, 42, 12) + pt(24, 21, ORANGE, 3)


@icon("sk_scale")
def _():
    return path("M8 40 V24 H24 V40 Z") + path(
        "M8 24 V8 H40 V40 H24", POINT, 1.6, extra='stroke-dasharray="3 2"'
    )


@icon("sk_move")
def _():
    return ICONS["move"]()


@icon("sk_project")
def _():
    return (
        poly([(10, 12), (34, 6), (38, 18), (14, 24)], GREY[1])
        + path("M10 40 L34 34", POINT)
        + arrow(22, 18, 22, 34, ORANGE, 1.6, 4)
    )


@icon("sk_intersect")
def _():
    return poly([(6, 18), (30, 10), (42, 26), (18, 34)], GREY[1], 'fill-opacity="0.8"') + line(
        10, 30, 38, 18, POINT, 2.4
    )


# constraints (red-orange glyphs, like constraint markers in the canvas)
@icon("c_coincident")
def _():
    return line(8, 36, 24, 20, RED, 2) + line(24, 20, 40, 34, RED, 2) + circle(24, 20, 4, RED)


@icon("c_collinear")
def _():
    return (
        line(6, 34, 20, 26, RED, 2.4)
        + line(28, 22, 42, 14, RED, 2.4)
        + line(20, 26, 28, 22, RED, 1, 'stroke-dasharray="2 2"')
    )


@icon("c_concentric")
def _():
    return (
        circle(24, 24, 15, "none", RED, 2)
        + circle(24, 24, 8, "none", RED, 2)
        + circle(24, 24, 2, RED)
    )


@icon("c_midpoint")
def _():
    return line(6, 34, 42, 14, RED, 2) + poly([(24, 18), (29, 25), (19, 25)], RED)


@icon("c_fix")
def _():
    out = line(24, 6, 24, 30, RED, 2.6) + line(10, 32, 38, 32, RED, 2.6)
    for x in range(12, 38, 6):
        out += line(x, 36, x - 4, 42, RED, 1.6)
    return out


@icon("c_parallel")
def _():
    return line(10, 38, 30, 10, RED, 2.6) + line(20, 38, 40, 10, RED, 2.6)


@icon("c_perpendicular")
def _():
    return (
        line(10, 8, 10, 40, RED, 2.6)
        + line(10, 40, 42, 40, RED, 2.6)
        + rect(10, 32, 8, 8, "none", 0, 'stroke="%s" stroke-width="1.4"' % RED)
    )


@icon("c_horizontal")
def _():
    return line(6, 24, 42, 24, RED, 2.6) + pt(6, 24, RED) + pt(42, 24, RED)


@icon("c_vertical")
def _():
    return line(24, 6, 24, 42, RED, 2.6) + pt(24, 6, RED) + pt(24, 42, RED)


@icon("c_tangent")
def _():
    return circle(22, 28, 11, "none", RED, 2.4) + line(8, 12, 42, 26, RED, 2.4)


@icon("c_smooth")
def _():
    return path("M6 36 C16 36 18 14 28 14 C34 14 38 20 42 24", RED, 2.4)


@icon("c_equal")
def _():
    return rect(10, 14, 28, 6, RED, 1) + rect(10, 28, 28, 6, RED, 1)


@icon("c_symmetric")
def _():
    return (
        line(24, 4, 24, 44, RED, 1.4, 'stroke-dasharray="3 2"')
        + pt(12, 24, RED, 3)
        + pt(36, 24, RED, 3)
        + path("M14 18 Q24 8 34 18", RED, 1.6)
    )


@icon("finish_sketch")
def _():
    return circle(24, 24, 16, GREEN) + path("M15 24 L22 31 L34 17", WHITE, 4)


@icon("cancel")
def _():
    return circle(24, 24, 16, RED) + path("M17 17 L31 31 M31 17 L17 31", WHITE, 4)


# ---- chrome: quick access, timeline, navigation ----------------------------------------
@icon("qa_menu")
def _():
    return (
        rect(10, 12, 28, 4, STROKE, 1.5)
        + rect(10, 22, 28, 4, STROKE, 1.5)
        + rect(10, 32, 28, 4, STROKE, 1.5)
    )


@icon("qa_new")
def _():
    return path("M12 6 H28 L36 14 V42 H12 Z", STROKE, 2.4) + path("M28 6 V14 H36", STROKE, 2)


@icon("qa_open")
def _():
    return path("M6 14 H18 L22 18 H40 V38 H6 Z", STROKE, 2.4)


@icon("qa_save")
def _():
    return (
        path("M8 8 H34 L40 14 V40 H8 Z", STROKE, 2.4)
        + rect(15, 8, 16, 10, STROKE, 1)
        + rect(14, 26, 20, 14, "none", 0, 'stroke="%s" stroke-width="2"' % STROKE)
    )


@icon("qa_undo")
def _():
    return path("M14 18 H30 A9 9 0 0 1 30 36 H18", STROKE, 3) + poly(
        [(6, 18), (16, 10), (16, 26)], STROKE
    )


@icon("qa_redo")
def _():
    return path("M34 18 H18 A9 9 0 0 0 18 36 H30", STROKE, 3) + poly(
        [(42, 18), (32, 10), (32, 26)], STROKE
    )


def _tl(shape):
    return shape


@icon("tl_start")
def _():
    return rect(10, 12, 4, 24, STROKE) + poly([(38, 12), (38, 36), (16, 24)], STROKE)


@icon("tl_prev")
def _():
    return poly([(34, 12), (34, 36), (14, 24)], STROKE)


@icon("tl_play")
def _():
    return poly([(16, 10), (16, 38), (38, 24)], STROKE)


@icon("tl_next")
def _():
    return poly([(14, 12), (14, 36), (34, 24)], STROKE) + rect(34, 12, 3, 24, STROKE)


@icon("tl_end")
def _():
    return poly([(10, 12), (10, 36), (32, 24)], STROKE) + rect(34, 12, 4, 24, STROKE)


@icon("tl_settings")
def _():
    out = circle(24, 24, 10, "none", STROKE, 5)
    for k in range(8):
        a = math.radians(45 * k)
        out += line(
            24 + 12 * math.cos(a),
            24 + 12 * math.sin(a),
            24 + 17 * math.cos(a),
            24 + 17 * math.sin(a),
            STROKE,
            5,
        )
    return out


@icon("nav_orbit")
def _():
    return (
        ellipse(24, 24, 17, 7, "none", STROKE, 2.2)
        + line(24, 6, 24, 42, STROKE, 2.2)
        + poly([(38, 26), (44, 22), (42, 30)], STROKE)
    )


@icon("orbit_center")
def _():
    """Set / Reset Orbit Center: the green dot the orbit turns about, inside the orbit ring."""
    return (
        ellipse(24, 24, 17, 7, "none", STROKE, 2.2)
        + circle(24, 24, 5.5, GREEN, DARK, 1.5)
        + line(24, 6, 24, 14, STROKE, 2.2)
        + line(24, 34, 24, 42, STROKE, 2.2)
    )


@icon("nav_lookat")
def _():
    return (
        rect(8, 18, 32, 22, "none", 2, 'stroke="%s" stroke-width="2.4"' % STROKE)
        + rect(14, 10, 20, 8, STROKE, 2)
        + rect(14, 24, 20, 10, BLUE[1])
    )


@icon("nav_pan")
def _():
    return path(
        "M16 40 V18 a3 3 0 0 1 6 0 V24 V12 a3 3 0 0 1 6 0 V24 V14 a3 3 0 0 1 6 0 V30 "
        "Q34 42 24 42 Q18 42 12 32 L8 26 a3 3 0 0 1 5 -3 L16 28",
        STROKE,
        2.2,
    )


@icon("nav_zoom")
def _():
    return (
        circle(20, 20, 11, "none", STROKE, 2.6)
        + line(28, 28, 40, 40, STROKE, 4)
        + line(16, 20, 24, 20, STROKE, 2)
        + line(20, 16, 20, 24, STROKE, 2)
    )


@icon("nav_fit")
def _():
    return path("M6 16 V6 H16 M32 6 H42 V16 M42 32 V42 H32 M16 42 H6 V32", STROKE, 2.4) + circle(
        24, 24, 7, "none", STROKE, 2.4
    )


@icon("nav_display")
def _():
    return (
        rect(6, 8, 36, 24, "none", 2, 'stroke="%s" stroke-width="2.4"' % STROKE)
        + rect(18, 34, 12, 4, STROKE)
        + block(0, 0, 0, 8, 8, 7, BLUE, 24, 26)
    )


@icon("nav_grid")
def _():
    out = ""
    for k in range(4):
        out += line(8 + k * 10.6, 8, 8 + k * 10.6, 40, STROKE, 1.6) + line(
            8, 8 + k * 10.6, 40, 8 + k * 10.6, STROKE, 1.6
        )
    return out


@icon("nav_viewports")
def _():
    return (
        rect(6, 8, 16, 14, STROKE, 1.5)
        + rect(26, 8, 16, 14, STROKE, 1.5)
        + rect(6, 26, 16, 14, STROKE, 1.5)
        + rect(26, 26, 16, 14, STROKE, 1.5)
    )


# -- INSPECT analyses and the navigation bar (sf/inspect-nav) ------------------------------
@icon("draft_analysis")
def _():
    return (
        poly([(10, 40), (24, 40), (24, 10), (16, 10)], "#3cc46a")
        + poly([(24, 40), (38, 40), (32, 10), (24, 10)], "#ef6f6c")
        + arrow(24, 30, 24, 4, WHITE, 2.2)
    )


@icon("curvature_map")
def _():
    out = ""
    colors = ["#3cc46a", "#a8d84a", "#f6dc5c", "#f2a14a", "#ef6f6c"]
    for i, color in enumerate(colors):
        out += path(
            "M%.1f 40 Q24 %.1f %.1f 40" % (6 + i * 3.2, 6 + i * 6.0, 42 - i * 3.2),
            color,
            3.0,
        )
    return out


@icon("isocurve")
def _():
    out = path("M6 38 Q24 6 42 38", STROKE, 1.6)
    for k in range(1, 5):
        t = k / 5
        x = (1 - t) ** 2 * 6 + 2 * (1 - t) * t * 24 + t * t * 42
        out += path("M%.1f %.1f Q%.1f %.1f %.1f %.1f" % (x - 6, 42, x, 30, x + 4, 14), POINT, 1.6)
    out += path("M8 30 Q24 14 40 30", ORANGE, 1.6)
    return out


@icon("accessibility")
def _():
    return (
        poly(
            [(6, 40), (42, 40), (42, 26), (30, 26), (30, 34), (18, 34), (18, 26), (6, 26)], GREY[1]
        )
        + rect(18, 34, 12, 6, "#ef6f6c")
        + poly([(6, 26), (18, 26), (18, 29), (6, 29)], "#3cc46a")
        + poly([(30, 26), (42, 26), (42, 29), (30, 29)], "#3cc46a")
        + arrow(24, 4, 24, 22, WHITE, 2.2)
    )


@icon("min_radius")
def _():
    return (
        poly([(8, 40), (40, 40), (40, 10), (32, 10), (32, 24), (24, 32), (8, 32)], GREY[1])
        + path("M32 22 Q32 32 22 32", "#ef6f6c", 3.0)
        + circle(26, 26, 5, "none", WHITE, 1.4)
    )


@icon("component_colors")
def _():
    return (
        block(0, 0, 0, 10, 10, 10, ("#bfe5ff", "#8fd0ff", "#5aaee8"), 16, 38)
        + block(0, 0, 0, 10, 10, 10, ("#f6dc8c", "#e8c460", "#c9a23e"), 32, 38)
        + block(0, 0, 0, 10, 10, 10, ("#c8f0c8", "#8ed69a", "#5cb36c"), 24, 24)
    )


@icon("nav_zoom_window")
def _():
    return (
        rect(
            6,
            10,
            28,
            22,
            "none",
            0,
            'stroke="%s" stroke-width="1.6" stroke-dasharray="3 2"' % STROKE,
        )
        + circle(32, 30, 7, "none", STROKE, 2.2)
        + line(37, 35, 43, 41, STROKE, 2.6)
    )


@icon("view_single")
def _():
    return rect(6, 8, 36, 32, "none", 1.5, 'stroke="%s" stroke-width="2"' % STROKE)


@icon("view_two_h")
def _():
    return rect(6, 8, 16, 32, STROKE, 1.5) + rect(26, 8, 16, 32, STROKE, 1.5)


@icon("view_two_v")
def _():
    return rect(6, 8, 36, 14, STROKE, 1.5) + rect(6, 26, 36, 14, STROKE, 1.5)


@icon("grid_snap")
def _():
    out = ""
    for k in range(4):
        out += line(8 + k * 10.6, 8, 8 + k * 10.6, 40, "#7d8593", 1.2) + line(
            8, 8 + k * 10.6, 40, 8 + k * 10.6, "#7d8593", 1.2
        )
    return out + circle(18.6, 29.2, 4, POINT) + path("M18.6 29.2 L36 12", WHITE, 1.6)


@icon("increment")
def _():
    out = line(6, 34, 42, 34, STROKE, 1.6)
    for k in range(5):
        out += line(8 + k * 8, 30, 8 + k * 8, 38, STROKE, 1.6)
    return out + arrow(8, 22, 40, 22, POINT, 2.2)


@icon("workspace_design")
def _():
    return block(0, 0, 0, 16, 16, 14, BLUE, 24, 30)


@icon("eye")
def _():
    return path("M4 24 Q24 6 44 24 Q24 42 4 24 Z", STROKE, 2.6) + circle(24, 24, 6.5, STROKE)


@icon("eye_off")
def _():
    return (
        path("M4 24 Q24 6 44 24 Q24 42 4 24 Z", "#7d8593", 2.6)
        + circle(24, 24, 6.5, "#7d8593")
        + line(8, 40, 40, 8, "#7d8593", 3)
    )


@icon("folder")
def _():
    return path("M5 14 H19 L23 18 H43 V40 H5 Z", "none", 0, "#c9d1dc") + rect(
        5, 21, 38, 19, "#e3e8ee", 1
    )


@icon("document")
def _():
    return block(0, 0, 0, 16, 16, 14, GREY, 24, 30)


@icon("base_feature")
def _():
    # A body kept as it is (no steps): a solid with a blue "held" badge (a clamp).
    return (
        block(0, 0, 0, 16, 16, 14, GREY, 21, 30)
        + circle(36, 35, 9, DBLUE[1])
        + path("M31 31 L31 39 M41 31 L41 39 M31 35 L41 35", WHITE, 2.6)
    )


@icon("units")
def _():
    return (
        rect(9, 6, 30, 36, WHITE, 2)
        + line(15, 16, 33, 16, "#8a93a3", 2.2)
        + line(15, 24, 33, 24, "#8a93a3", 2.2)
        + line(15, 32, 27, 32, "#8a93a3", 2.2)
    )


@icon("insert_step")
def _():
    # Two bodies arriving from a file (a tag with "STEP" over a grey block)
    return (
        block(0, 0, 0, 16, 16, 12, GREY, 30, 30)
        + rect(4, 4, 28, 16, WHITE, 2)
        + '<text x="18" y="16" font-family="sans-serif" font-size="9" '
        'font-weight="bold" text-anchor="middle" fill="%s">STEP</text>' % DBLUE[2]
    )


@icon("convert_mesh")
def _():
    # A triangle mesh on the left turning into a smooth block on the right
    pts = [(6, 20), (18, 14), (18, 34), (6, 40)]
    out = poly(pts, GOLD[1]) + line(6, 20, 18, 34, GOLD[2], 1.2) + line(18, 14, 6, 40, GOLD[2], 1.2)
    out += arrow(20, 27, 28, 27, WHITE, 2.2, 4.5)
    out += block(0, 0, 0, 12, 12, 12, GREY, 36, 30, 0.9)
    return out


@icon("export")
def _():
    # A box leaving through an opening to the right
    return (
        path("M8 10 H26 V40 H8 Z", STROKE, 2.4)
        + block(0, 0, 0, 10, 10, 10, GREY, 17, 28, 0.7)
        + arrow(24, 24, 42, 24, WHITE, 2.6, 6)
    )


@icon("export_all")
def _():
    # A folder with several files flying out of it
    return (
        path("M6 14 H18 L21 18 H40 V38 H6 Z", STROKE, 2.2, DARK)
        + rect(14, 22, 10, 12, WHITE, 1.5)
        + rect(20, 19, 10, 12, "#cfe6ff", 1.5)
        + rect(26, 16, 10, 12, GOLD[1], 1.5)
        + arrow(30, 10, 42, 6, WHITE, 2.2, 5)
    )


@icon("calibrate")
def _():
    # Two points on a picture with a measured distance between them
    return (
        rect(6, 10, 36, 28, "#5aaee8", 2)
        + line(13, 30, 35, 18, WHITE, 2.0)
        + pt(13, 30, "#f6dc8c", 3.2)
        + pt(35, 18, "#f6dc8c", 3.2)
    )


# ---- MESH tab (SciForge's own drawings: a gold triangle mesh is "a mesh body") ---------------
def mesh_patch(points, fill=None, edge=None, inner=()):
    """A gold mesh piece: the outline `points` filled, its triangle lines from the first point
    and the extra `inner` lines."""
    fill = fill or GOLD[1]
    edge = edge or GOLD[2]
    out = poly(points, fill)
    for a in points[2:-1]:
        out += line(points[0][0], points[0][1], a[0], a[1], edge, 1.1)
    for x1, y1, x2, y2 in inner:
        out += line(x1, y1, x2, y2, edge, 1.1)
    return out


HEX = [(24, 7), (39, 15), (39, 33), (24, 41), (9, 33), (9, 15)]


@icon("mesh_repair")
def _():
    # a mesh with a dark hole, and the green plus that fills it
    pts = HEX
    out = mesh_patch(pts, inner=[(24, 7, 24, 41), (9, 15, 39, 33), (39, 15, 9, 33)])
    out += poly([(24, 24), (39, 15), (39, 33)], DARK)
    return out + plus_badge(35, 35, 8)


@icon("mesh_remesh")
def _():
    # coarse triangles on the left, an even fine grid on the right
    out = poly([(6, 10), (24, 10), (24, 38), (6, 38)], GOLD[1])
    out += line(6, 10, 24, 38, GOLD[2], 1.2) + line(6, 38, 24, 10, GOLD[2], 1.0)
    out += poly([(24, 10), (42, 10), (42, 38), (24, 38)], GOLD[0])
    for k in range(1, 4):
        y = 10 + 7 * k
        out += line(24, y, 42, y, GOLD[2], 0.9)
    for k in range(1, 3):
        x = 24 + 6 * k
        out += line(x, 10, x, 38, GOLD[2], 0.9)
    for k in range(4):
        out += line(24, 17 + 7 * k - 7, 42, 17 + 7 * k, GOLD[2], 0.7)
    return out


@icon("mesh_reduce")
def _():
    # a dense mesh becomes a few big triangles
    out = poly([(4, 12), (18, 12), (18, 36), (4, 36)], GOLD[1])
    for k in range(1, 4):
        out += line(4, 12 + 6 * k, 18, 12 + 6 * k, GOLD[2], 0.8)
    out += line(4, 12, 18, 36, GOLD[2], 0.8) + line(11, 12, 11, 36, GOLD[2], 0.8)
    out += arrow(20, 24, 28, 24, WHITE, 2.0, 4.5)
    out += poly([(30, 12), (44, 12), (44, 36), (30, 36)], GOLD[1])
    out += line(30, 12, 44, 36, GOLD[2], 1.2)
    return out


@icon("mesh_smooth")
def _():
    # a jagged mesh edge and the smooth line it becomes
    out = poly(
        [(6, 38), (6, 26), (12, 18), (18, 26), (24, 14), (30, 24), (36, 16), (42, 26), (42, 38)],
        GOLD[1],
    )
    out += path("M6 22 C14 12 22 30 30 18 C36 9 40 14 42 20", "#7cc4f5", 2.6)
    return out


@icon("mesh_plane_cut")
def _():
    # a mesh piece and a blue plane through it, the part past the plane faded
    out = mesh_patch(
        [(8, 14), (30, 8), (40, 18), (40, 36), (18, 42), (8, 32)],
        inner=[(30, 8, 18, 42), (40, 18, 8, 32)],
    )
    out += poly([(4, 30), (30, 4), (44, 12), (18, 38)], "#5aaee8", 'fill-opacity="0.75"')
    return out


@icon("mesh_separate")
def _():
    out = mesh_patch([(4, 14), (18, 10), (20, 30), (6, 36)])
    out += mesh_patch([(28, 18), (42, 14), (44, 34), (30, 38)])
    out += arrow(22, 6, 30, 6, WHITE, 2.0, 4) + arrow(24, 42, 16, 42, WHITE, 2.0, 4)
    return out


@icon("mesh_combine")
def _():
    out = mesh_patch([(4, 12), (26, 8), (28, 30), (8, 34)])
    out += mesh_patch([(18, 18), (42, 14), (44, 38), (20, 40)], GOLD[0])
    return out


@icon("mesh_reverse_normal")
def _():
    out = mesh_patch([(8, 34), (24, 12), (40, 34)])
    out += arrow(24, 30, 24, 4, "#7cc4f5", 2.4, 5)
    out += arrow(30, 34, 30, 46, "#ef6f6c", 2.0, 4.5)
    return out


@icon("mesh_shell")
def _():
    # a hollow mesh ring
    out = mesh_patch(HEX, inner=[(24, 7, 24, 41), (9, 15, 39, 33), (39, 15, 9, 33)])
    out += poly([(24, 15), (32, 19.5), (32, 28.5), (24, 33), (16, 28.5), (16, 19.5)], DARK)
    return out


@icon("mesh_erase_fill")
def _():
    out = mesh_patch(HEX, inner=[(24, 7, 24, 41), (9, 15, 39, 33), (39, 15, 9, 33)])
    out += circle(24, 24, 9, "#bfe5ff", "#2f7fbf", 1.6)
    out += line(18, 24, 30, 24, "#2f7fbf", 1.0) + line(24, 18, 24, 30, "#2f7fbf", 1.0)
    return out


@icon("mesh_delete_faces")
def _():
    out = mesh_patch(HEX, inner=[(24, 7, 24, 41), (9, 15, 39, 33), (39, 15, 9, 33)])
    out += poly([(24, 24), (39, 15), (39, 33)], RED)
    return out + line(30, 21, 36, 27, WHITE, 2.0) + line(36, 21, 30, 27, WHITE, 2.0)


@icon("mesh_face_groups")
def _():
    out = poly([(24, 24), (24, 7), (39, 15), (39, 33)], GOLD[1])
    out += poly([(24, 24), (39, 33), (24, 41), (9, 33)], "#7cc4f5")
    out += poly([(24, 24), (9, 33), (9, 15), (24, 7)], "#a8e6b0")
    for a, b, c, d in ((24, 7, 24, 24), (39, 33, 24, 24), (9, 33, 24, 24)):
        out += line(a, b, c, d, DARK, 1.6)
    return out


@icon("mesh_direct_edit")
def _():
    # a mesh piece with a few faces picked (blue) and a brush tip over them
    out = mesh_patch(HEX, inner=[(24, 7, 24, 41), (9, 15, 39, 33), (39, 15, 9, 33)])
    out += poly([(24, 24), (39, 15), (39, 33)], "#7cc4f5")
    out += poly([(24, 24), (24, 7), (39, 15)], "#7cc4f5")
    out += line(18, 40, 33, 22, WHITE, 3.0)
    return out + circle(34, 21, 3.2, WHITE, DARK, 1.2)


@icon("mesh_create_group")
def _():
    # faces gathered into one coloured group, with a plus
    out = mesh_patch(HEX, inner=[(24, 7, 24, 41), (9, 15, 39, 33), (39, 15, 9, 33)])
    out += poly([(24, 24), (9, 33), (9, 15), (24, 7)], "#a8e6b0")
    out += line(24, 7, 24, 24, DARK, 1.4) + line(9, 33, 24, 24, DARK, 1.4)
    return out + plus_badge(37, 37, 7.5)


@icon("mesh_combine_groups")
def _():
    # two face groups (green, blue) joined into one (green) across their shared edge
    out = poly([(6, 34), (16, 12), (26, 34)], "#a8e6b0")
    out += poly([(22, 34), (32, 12), (42, 34)], "#7cc4f5")
    out += poly([(16, 12), (32, 12), (26, 34), (22, 34)], "#a8e6b0")
    out += line(16, 12, 26, 34, DARK, 1.2) + line(32, 12, 22, 34, DARK, 1.2)
    return out + arrow(32, 42, 16, 42, WHITE, 2.0, 4.0)


@icon("mesh_tessellate")
def _():
    # a solid block on the left becomes triangles on the right
    out = block(0, 0, 0, 12, 12, 12, GREY, 12, 30, 0.9)
    out += arrow(21, 24, 28, 24, WHITE, 2.0, 4.5)
    out += mesh_patch([(30, 14), (44, 14), (44, 36), (30, 36)], inner=[(30, 25, 44, 25)])
    return out


@icon("mesh_section")
def _():
    # a mesh with the orange line where a plane cuts it, on a sketch plane
    out = path("M4 34 L18 42 L44 30 L30 22 Z", STROKE, 1.4, extra='stroke-dasharray="3 2"')
    out += mesh_patch([(12, 8), (34, 6), (38, 26), (14, 30)], inner=[(34, 6, 14, 30)])
    out += path("M13 20 C20 16 28 22 37 17", "#f2a66a", 2.6)
    return out


@icon("not_available")
def _():
    return circle(24, 24, 14, "none", "#7d8593", 2.4) + line(14, 34, 34, 14, "#7d8593", 2.4)


# ---- surface tools (SURFACE tab, surface_ui.py) ----------------------------------------
# A surface is drawn as a thin curved sheet: a light front and a darker back edge, so it
# never reads as a solid block.
def _sheet(x0, y0, x1, y1, lift=8, depth=10, color=BLUE, opacity=None):
    """A curved sheet from (x0, y0) to (x1, y1) bulging up by `lift`, `depth` deep."""
    mx, my = (x0 + x1) / 2.0, (y0 + y1) / 2.0 - lift
    extra = 'fill-opacity="%.2f"' % opacity if opacity is not None else ""
    d = "M%.1f %.1f Q%.1f %.1f %.1f %.1f L%.1f %.1f Q%.1f %.1f %.1f %.1f Z" % (
        x0,
        y0,
        mx,
        my,
        x1,
        y1,
        x1 - depth * 0.5,
        y1 - depth,
        mx - depth * 0.5,
        my - depth,
        x0 - depth * 0.5,
        y0 - depth,
    )
    edge = "M%.1f %.1f Q%.1f %.1f %.1f %.1f" % (x0, y0, mx, my, x1, y1)
    return path(d, "none", 0, color[1], extra) + path(edge, color[2], 1.6)


@icon("surface_body")
def _():
    return _sheet(12, 34, 40, 34, 10, 14)


@icon("surface_extrude")
def _():
    return (
        poly([(8, 38), (30, 38), (30, 16), (8, 16)], BLUE[1], 'fill-opacity="0.85"')
        + line(8, 38, 30, 38, ORANGE, 2.4)
        + line(8, 16, 30, 16, BLUE[2], 1.6)
        + arrow(38, 36, 38, 10, WHITE, 2.2)
    )


@icon("surface_revolve")
def _():
    return (
        path("M10 34 Q24 22 38 34 L38 18 Q24 6 10 18 Z", "none", 0, BLUE[1])
        + path("M10 34 Q24 22 38 34", BLUE[2], 1.6)
        + line(10, 18, 10, 34, ORANGE, 2.4)
        + path("M12 42 Q24 48 36 42", WHITE, 2)
        + poly([(36, 42), (30, 41), (34, 46)], WHITE)
    )


@icon("surface_sweep")
def _():
    return (
        path("M8 38 C10 24 22 28 24 12 L32 14 C30 30 18 26 16 40 Z", "none", 0, BLUE[1])
        + line(8, 38, 16, 40, ORANGE, 2.4)
        + path("M12 39 C14 26 26 28 28 13", STROKE, 1.4, extra='stroke-dasharray="3 2"')
    )


@icon("surface_loft")
def _():
    return (
        poly([(8, 36), (14, 12), (36, 10), (34, 38)], BLUE[1], 'fill-opacity="0.9"')
        + line(8, 36, 34, 38, ORANGE, 2.4)
        + line(14, 12, 36, 10, ORANGE, 2.4)
    )


@icon("patch")
def _():
    return (
        path("M10 30 Q12 14 24 12 Q38 12 38 28 Q36 40 24 40 Q10 40 10 30 Z", "none", 0, BLUE[1])
        + path(
            "M10 30 Q12 14 24 12 Q38 12 38 28 Q36 40 24 40 Q10 40 10 30 Z",
            ORANGE,
            2.2,
        )
        + path("M16 30 Q24 22 32 28", BLUE[0], 1.4)
    )


@icon("ruled")
def _():
    return (
        poly([(8, 34), (28, 34), (40, 18), (20, 18)], BLUE[1], 'fill-opacity="0.85"')
        + poly([(8, 34), (28, 34), (28, 40), (8, 40)], GREY[1])
        + line(8, 34, 28, 34, ORANGE, 2.6)
    )


@icon("surface_offset")
def _():
    return _sheet(10, 40, 38, 40, 10, 10) + path(
        "M12 24 Q24 10 36 24", STROKE, 1.6, extra='stroke-dasharray="3 2"'
    )


@icon("trim")
def _():
    return (
        poly([(8, 38), (24, 38), (24, 14), (8, 14)], BLUE[1])
        + poly([(24, 38), (40, 38), (40, 14), (24, 14)], RED, 'fill-opacity="0.55"')
        + line(24, 8, 24, 44, WHITE, 2.2)
    )


@icon("untrim")
def _():
    return (
        poly([(8, 38), (40, 38), (40, 12), (8, 12)], BLUE[1])
        + circle(24, 25, 7, "none", BLUE[0], 1.6)
        + path("M17 25 A7 7 0 0 1 31 25", WHITE, 1.6, extra='stroke-dasharray="2.5 2"')
    )


@icon("surface_extend")
def _():
    return (
        poly([(8, 38), (26, 38), (26, 14), (8, 14)], BLUE[1])
        + poly([(26, 38), (36, 38), (36, 14), (26, 14)], BLUE[0], 'fill-opacity="0.5"')
        + line(26, 14, 26, 38, ORANGE, 2.2)
        + arrow(28, 26, 42, 26, WHITE, 2.0, 5)
    )


@icon("stitch")
def _():
    zig = "M24 10 L20 15 L28 20 L20 25 L28 30 L20 35 L24 40"
    return (
        poly([(6, 38), (24, 40), (24, 10), (8, 12)], BLUE[1])
        + poly([(24, 40), (42, 38), (40, 12), (24, 10)], BLUE[2])
        + path(zig, WHITE, 1.8)
    )


@icon("unstitch")
def _():
    return (
        poly([(6, 38), (20, 40), (20, 10), (8, 12)], BLUE[1])
        + poly([(28, 40), (42, 38), (40, 12), (28, 10)], BLUE[2])
        + line(24, 8, 24, 42, STROKE, 1.4, 'stroke-dasharray="3 2"')
    )


@icon("reverse_normal")
def _():
    return (
        _sheet(10, 32, 38, 32, 8, 10)
        + arrow(24, 22, 24, 6, WHITE, 2.0, 5)
        + arrow(24, 30, 24, 44, ORANGE, 2.0, 5)
    )


# ---- drawing workspace (outline 7.16) ---------------------------------------------
PAPER = "#f4f6f8"
INK = "#3a4350"
DASHDOT = 'stroke-dasharray="6 2 1.5 2"'


def sheet(x=7, y=8, w=34, h=30):
    """A drawing sheet: a white page with a thin frame."""
    return rect(x, y, w, h, PAPER, 1.5) + path(
        "M%d %d H%d V%d H%d Z" % (x + 2, y + 2, x + w - 2, y + h - 2, x + 2), "#c3cad3", 1.0
    )


@icon("dw_new")
def _():
    return (
        sheet()
        + path("M12 14 H26 V26 H12 Z", INK, 1.8)
        + circle(19, 20, 2.6, "none", INK, 1.4)
        + plus_badge(37, 37, 8)
    )


@icon("dw_base_view")
def _():
    return (
        sheet()
        + path("M13 15 H33 V29 H13 Z", INK, 2.0)
        + circle(23, 22, 3.6, "none", INK, 1.6)
        + rect(28, 31, 11, 5, POINT, 1)
    )


@icon("dw_projected_view")
def _():
    return (
        sheet()
        + path("M11 13 H22 V22 H11 Z", INK, 1.8)
        + path("M11 27 H22 V34 H11 Z", "#6f7a88", 1.6)
        + path("M27 13 H36 V22 H27 Z", "#6f7a88", 1.6)
        + arrow(23, 17.5, 26, 17.5, POINT, 1.6, 3)
        + arrow(16.5, 23, 16.5, 26, POINT, 1.6, 3)
    )


@icon("dw_section_view")
def _():
    hatch = "".join(line(15 + i * 4, 30, 19 + i * 4, 24, "#6f7a88", 1.0) for i in range(4))
    return (
        sheet()
        + path("M13 14 H33 V31 H13 Z", INK, 1.8)
        + hatch
        + line(23, 10, 23, 36, ORANGE, 1.6, DASHDOT)
        + arrow(20, 11, 15, 11, ORANGE, 1.6, 3.5)
        + arrow(26, 11, 31, 11, ORANGE, 1.6, 3.5)
    )


@icon("dw_detail_view")
def _():
    return (
        sheet()
        + path("M11 30 V16 H27", INK, 1.8)
        + circle(14, 19, 5.5, "none", ORANGE, 1.4)
        + circle(31, 28, 8, PAPER, INK, 1.6)
        + path("M26 34 V24 H37", INK, 2.2)
    )


@icon("dw_break_view")
def _():
    return (
        sheet()
        + path("M10 18 H19 L21 21 L18 24 L20 27 H10 Z", INK, 1.8)
        + path("M38 18 H27 L29 21 L26 24 L28 27 H38", INK, 1.8)
    )


@icon("dw_centerline")
def _():
    return (
        sheet()
        + line(13, 14, 13, 32, INK, 2.0)
        + line(33, 14, 33, 32, INK, 2.0)
        + line(23, 11, 23, 35, ORANGE, 1.6, DASHDOT)
    )


@icon("dw_center_mark")
def _():
    return (
        sheet()
        + circle(23, 23, 8, "none", INK, 2.0)
        + line(11, 23, 35, 23, ORANGE, 1.5, DASHDOT)
        + line(23, 11, 23, 35, ORANGE, 1.5, DASHDOT)
    )


@icon("dw_dimension")
def _():
    return (
        sheet()
        + line(12, 30, 12, 15, "#6f7a88", 1.2)
        + line(34, 30, 34, 15, "#6f7a88", 1.2)
        + arrow(22, 19, 12.5, 19, POINT, 1.6, 3.5)
        + arrow(24, 19, 33.5, 19, POINT, 1.6, 3.5)
        + path("M12 30 H34", INK, 2.2)
    )


@icon("dw_text")
def _():
    return (
        sheet()
        + path("M15 32 L22 14 L29 32 M18 26 H26", INK, 2.4)
        + line(31, 30, 36, 30, "#6f7a88", 1.4)
    )


@icon("dw_symbol")
def _():
    return sheet() + path("M13 24 L18 31 L30 13 H36", INK, 2.0)


@icon("dw_table")
def _():
    rows = "".join(line(10, 17 + i * 5, 36, 17 + i * 5, INK, 1.0) for i in range(4))
    return (
        sheet()
        + path("M10 12 H36 V34 H10 Z", INK, 1.6)
        + rect(10, 12, 26, 5, "#cfe6ff")
        + rows
        + line(16, 12, 16, 34, INK, 1.0)
        + line(22, 12, 22, 34, INK, 1.0)
    )


@icon("dw_balloon")
def _():
    return (
        sheet()
        + path("M12 31 H22 V22 H12 Z", "#6f7a88", 1.6)
        + line(18, 26, 27, 18, INK, 1.4)
        + circle(31, 15, 5.5, PAPER, INK, 1.8)
        + line(31, 12.5, 31, 17.5, INK, 1.6)
    )


@icon("dw_export_pdf")
def _():
    return (
        sheet(7, 8, 26, 30)
        + path("M11 14 H25 V24 H11 Z", INK, 1.6)
        + rect(24, 28, 18, 10, RED, 2)
        + arrow(30, 18, 41, 18, WHITE, 2.2, 5)
    )


@icon("dw_export_dxf")
def _():
    return (
        sheet(7, 8, 26, 30)
        + path("M11 14 H25 V24 H11 Z", INK, 1.6)
        + rect(24, 28, 18, 10, DBLUE[1], 2)
        + arrow(30, 18, 41, 18, WHITE, 2.2, 5)
    )


@icon("dw_title_block")
def _():
    return (
        sheet()
        + path("M21 26 H39 V36 H21 Z", INK, 1.6)
        + line(21, 31, 39, 31, INK, 1.0)
        + line(30, 26, 30, 36, INK, 1.0)
    )


# Icons kept exactly as drawn (main() empties the folder first, so they live here too).
# palette_check: the tick of a ticked check box (theme.py, sketch_palette.py), 14 px.
RAW = {
    "palette_check": (
        '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 14 14">\n'
        '  <path d="M3 7.2 L5.8 10 L11 4" fill="none" stroke="#ffffff" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round"/>\n'
        "</svg>\n"
    ),
}


def main():
    os.makedirs(OUT, exist_ok=True)
    for name in os.listdir(OUT):
        if name.endswith(".svg"):
            os.remove(os.path.join(OUT, name))
    for name, text in sorted(RAW.items()):
        with open(os.path.join(OUT, name + ".svg"), "w", encoding="utf-8") as handle:
            handle.write(text)
    for name, fn in sorted(ICONS.items()):
        _BOUNDS.clear()
        body = fn()
        with open(os.path.join(OUT, name + ".svg"), "w", encoding="utf-8") as handle:
            handle.write(svg(body, list(_BOUNDS)))
    print("[SciForge] wrote %d icons to %s" % (len(ICONS) + len(RAW), os.path.normpath(OUT)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
