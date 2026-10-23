# SPDX-License-Identifier: LGPL-2.1-or-later
# SHEET METAL icons of the sm-more builder (Bend, Hem, Join by Bend, Corner Closure, Lofted
# Flange, sheet metal Fillet / Chamfer). Run by make_icons.py in its namespace (icon, path,
# poly, line, circle, block, iso, GREY, BLUE, STROKE ... are its helpers). Original artwork.
# A sheet is drawn as a thick stroke (its cross-section) or an isometric plate.


def _smm_sheet(d, color, w=4.2):
    return path(d, color, w)


def _smm_plate(points, colors):
    return poly(points, colors[0], 'stroke="%s" stroke-width="0.7"' % STROKE)


@icon("sm_bend")
def _smm_icon_bend():
    flat = [iso(-14, -2, 0), iso(4, -2, 0), iso(4, 14, 0), iso(-14, 14, 0)]
    up = [iso(4, -2, 0), iso(4, -2, 18), iso(4, 14, 18), iso(4, 14, 0)]
    return (
        _smm_plate(flat, GREY)
        + poly(up, BLUE[1], 'stroke="%s" stroke-width="0.7"' % STROKE)
        + line(
            *iso(4, -6, 0), *iso(4, 18, 0), color=ORANGE, w=1.6, extra='stroke-dasharray="2.5 2"'
        )
        + arrow(*iso(-6, 6, 4), *iso(2, 6, 14), color=WHITE, w=1.8, head=4.5)
    )


@icon("sm_hem")
def _smm_icon_hem():
    return (
        _smm_sheet("M6 30 H30", GREY[2])
        + _smm_sheet("M30 30 A6 6 0 0 0 30 18 H14", BLUE[2])
        + line(30, 36, 30, 40, STROKE, 1.2)
        + line(14, 36, 14, 40, STROKE, 1.2)
        + line(14, 38, 30, 38, STROKE, 1.2)
    )


@icon("sm_join_bend")
def _smm_icon_join_bend():
    return (
        _smm_sheet("M6 36 H22", GREY[2])
        + _smm_sheet("M34 26 V8", GREY[2])
        + _smm_sheet("M22 36 H26 A8 8 0 0 0 34 28 V26", BLUE[2])
        + circle(24, 36, 2.2, POINT)
        + circle(34, 24, 2.2, POINT)
    )


@icon("sm_corner_closure")
def _smm_icon_corner_closure():
    base = [iso(-12, -12, 0), iso(12, -12, 0), iso(12, 12, 0), iso(-12, 12, 0)]
    wall_a = [iso(12, -12, 0), iso(12, 8, 0), iso(12, 8, 14), iso(12, -12, 14)]
    wall_b = [iso(-12, 12, 0), iso(8, 12, 0), iso(8, 12, 14), iso(-12, 12, 14)]
    close_a = [iso(12, 8, 0), iso(12, 11, 0), iso(12, 11, 14), iso(12, 8, 14)]
    close_b = [iso(8, 12, 0), iso(11, 12, 0), iso(11, 12, 14), iso(8, 12, 14)]
    edge = 'stroke="%s" stroke-width="0.7"' % STROKE
    return (
        _smm_plate(base, GREY)
        + poly(wall_a, GREY[2], edge)
        + poly(wall_b, GREY[1], edge)
        + poly(close_a, BLUE[2], edge)
        + poly(close_b, BLUE[1], edge)
    )


@icon("sm_lofted_flange")
def _smm_icon_lofted_flange():
    return (
        path("M8 34 L24 40 L40 34 L24 28 Z", GREY[1], 1.6, BLUE[1] + '" fill-opacity="0.55')
        + ellipse(24, 14, 9, 4, "none", STROKE, 1.6)
        + line(8, 34, 15, 14, BLUE[2], 1.4)
        + line(40, 34, 33, 14, BLUE[2], 1.4)
        + line(24, 40, 24, 18, BLUE[2], 1.4)
        + line(24, 28, 24, 10, BLUE[2], 1.0)
    )


@icon("sm_fillet")
def _smm_icon_fillet():
    plate = [iso(-14, -14, 0), iso(14, -14, 0), iso(14, 6, 0), iso(6, 14, 0), iso(-14, 14, 0)]
    return _smm_plate(plate, GREY) + path(
        "M%.2f %.2f Q%.2f %.2f %.2f %.2f" % (*iso(14, 2, 0), *iso(14, 14, 0), *iso(2, 14, 0)),
        BLUE[2],
        3.0,
    )


@icon("sm_chamfer")
def _smm_icon_chamfer():
    plate = [iso(-14, -14, 0), iso(14, -14, 0), iso(14, 4, 0), iso(4, 14, 0), iso(-14, 14, 0)]
    return _smm_plate(plate, GREY) + line(*iso(14, 4, 0), *iso(4, 14, 0), color=BLUE[2], w=3.0)
