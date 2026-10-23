# SPDX-License-Identifier: LGPL-2.1-or-later
# Icons of the SHEET METAL flat tools (sm-flat, wave 6): Create Flat Pattern, Unfold, Refold,
# Rip, Convert to Sheet Metal and the FLAT PATTERN tab. Run by make_icons.py in its namespace
# (GREY, BLUE, STROKE, poly, path, line, rect, arrow, circle ... come from there).
# Original artwork in the style of the other icons.
# flake8: noqa


def _flat_sheet(dash=True):
    """A flat sheet in plan, an L-shaped outline with a dashed bend line."""
    out = poly([(6, 14), (42, 14), (42, 34), (24, 34), (24, 42), (6, 42)], GREY[1])
    out += path("M6 14 H42 V34 H24 V42 H6 Z", STROKE, 1.4)
    if dash:
        out += line(6, 24, 42, 24, BLUE[2], 1.6, 'stroke-dasharray="3 2"')
    return out


@icon("sm_flat_pattern")
def _():
    return _flat_sheet() + rect(30, 4, 14, 8, BLUE[1], 1.5)


@icon("flat_pattern")
def _():
    return _flat_sheet()


@icon("sm_unfold")
def _():
    # a bent sheet: a wall standing up on a base, and its unfolded copy in blue
    return (
        poly([(6, 40), (26, 40), (26, 36), (10, 36), (10, 10), (6, 10)], GREY[1])
        + path("M6 40 H26 V36 H10 V10 H6 Z", STROKE, 1.2)
        + poly([(26, 40), (44, 40), (44, 36), (26, 36)], BLUE[1])
        + path("M14 12 Q34 12 38 30", BLUE[2], 2)
        + poly([(34, 28), (42, 29), (38, 34)], BLUE[2])
    )


@icon("sm_refold")
def _():
    return (
        poly([(4, 40), (44, 40), (44, 36), (4, 36)], BLUE[1])
        + path("M4 40 H44 V36 H4 Z", STROKE, 1.2)
        + poly([(40, 34), (44, 34), (44, 10), (40, 10)], GREY[1])
        + path("M28 32 Q30 14 38 12", BLUE[2], 2)
        + poly([(36, 8), (42, 12), (35, 16)], BLUE[2])
    )


@icon("sm_rip")
def _():
    # a square tube seen from its end, opened by a gap at one corner
    return (
        path("M14 8 H40 V40 H8 V14", STROKE, 5)
        + path("M14 8 H40 V40 H8 V14", GREY[1], 3)
        + line(6, 6, 16, 16, RED, 2.2)
    )


@icon("sm_convert")
def _():
    o = (16, 30)
    return (
        block(0, 0, 0, 12, 12, 10, GREY, *o)
        + arrow(22, 22, 32, 22, BLUE[2], 2.2, 5)
        + poly([(34, 40), (46, 40), (46, 37), (37, 37), (37, 12), (34, 12)], BLUE[1])
        + path("M34 40 H46 V37 H37 V12 H34 Z", STROKE, 1.0)
    )


@icon("fp_export_dxf")
def _():
    return (
        _flat_sheet(dash=False)
        + rect(24, 28, 20, 12, DBLUE[1], 2)
        + arrow(28, 34, 41, 34, WHITE, 2.2, 5)
    )


@icon("fp_finish")
def _():
    return circle(24, 24, 16, GREEN) + path("M15 24 L22 31 L34 17", WHITE, 4)
