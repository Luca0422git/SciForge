# SPDX-License-Identifier: LGPL-2.1-or-later
# SHEET METAL forming icons (sm-forming). Run by make_icons.py in its namespace: @icon, block,
# poly, line, path, iso and the palette come from there. Original artwork.
# flake8: noqa


def _bent_sheet(colors_plate, colors_wall, ox=22, oy=34, t=2.6):
    """An L of sheet: a flat plate and a wall standing up from its far edge."""
    return block(0, 0, 0, 20, 15, t, colors_plate, ox, oy) + block(
        20 - t, 0, t, t, 15, 15, colors_wall, ox, oy
    )


@icon("sm_flange")
def _():
    return _bent_sheet(GREY, BLUE) + line(
        *iso(9, 7.5, 3.5, 22, 34), *iso(9, 7.5, 14, 22, 34), color=WHITE, w=1.6
    )


@icon("sheet_metal_body")
def _():
    t = 2.4
    return (
        block(0, 0, 0, 18, 14, t, GREY, 22, 33)
        + block(18 - t, 0, t, t, 14, 13, GREY, 22, 33)
        + block(0, 0, t, t, 14, 8, GREY, 22, 33)
    )


@icon("sm_rules")
def _():
    out = block(0, 0, 0, 22, 16, 3, GREY, 20, 30)
    # a gauge reading the sheet's thickness
    out += line(*iso(22, 16, 0, 20, 30), *iso(22, 24, 0, 20, 30), color=BLUE[2], w=1.4)
    out += line(*iso(22, 16, 3, 20, 30), *iso(22, 24, 3, 20, 30), color=BLUE[2], w=1.4)
    out += line(*iso(22, 22, -3, 20, 30), *iso(22, 22, 6, 20, 30), color=WHITE, w=1.6)
    out += line(*iso(0, 0, 9, 20, 30), *iso(12, 0, 9, 20, 30), color=STROKE, w=1.4)
    out += line(*iso(0, 0, 13, 20, 30), *iso(8, 0, 13, 20, 30), color=STROKE, w=1.4)
    return out


@icon("sm_component")
def _():
    return _bent_sheet(GREY, GREY, 20, 32) + plus_badge(37, 37, 7.5)
