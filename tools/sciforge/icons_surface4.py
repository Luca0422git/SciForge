# SPDX-License-Identifier: LGPL-2.1-or-later
# SURFACE > MODIFY on surface bodies (wave 6, surface-4): the timeline / menu icons of its
# steps. Run by make_icons.py in its own namespace (@icon, poly, line, path, arrow, the
# palette...). Original artwork: two thin sheets meeting at an edge (a surface body), with
# the step's mark in the accent colour.
# flake8: noqa


def _two_sheets(fold=None):
    """Two open sheets meeting along an edge: a flat floor and a wall (a surface body).
    fold: None (a sharp edge), "round" or "bevel" (the edge rounded or cut)."""
    floor = [(6, 36), (28, 42), (42, 32), (20, 26)]
    out = poly(floor, BLUE[1], 'fill-opacity="0.85"')
    if fold is None:
        wall = [(20, 26), (42, 32), (42, 10), (20, 4)]
        out += poly(wall, BLUE[0], 'fill-opacity="0.85"')
        out += line(20, 26, 42, 32, BLUE[2], 1.6)
    elif fold == "round":
        wall = [(20, 18), (42, 24), (42, 6), (20, 0)]
        out += poly(wall, BLUE[0], 'fill-opacity="0.85"')
        out += path("M20 18 Q20 26 28 28 L42 32 Q42 26 42 24 Z", "none", 0, ORANGE)
        out += path("M20 18 Q20 26 28 28", ORANGE, 2.0)
    else:
        wall = [(20, 18), (42, 24), (42, 6), (20, 0)]
        out += poly(wall, BLUE[0], 'fill-opacity="0.85"')
        out += poly([(20, 18), (42, 24), (48, 34), (26, 28)], ORANGE)
    out += line(6, 36, 20, 26, STROKE, 1.0) + line(28, 42, 42, 32, STROKE, 1.0)
    return out


@icon("surfmod_fillet")
def _():
    return _two_sheets("round")


@icon("surfmod_chamfer")
def _():
    return _two_sheets("bevel")


@icon("surfmod_delete")
def _():
    # a sheet with a face taken out (dashed outline where it was), the hole left open
    out = poly([(6, 34), (24, 42), (44, 30), (26, 22)], BLUE[1], 'fill-opacity="0.85"')
    out += path("M26 22 L44 30 L44 8 L26 2 Z", STROKE, 1.4, extra='stroke-dasharray="3 2"')
    out += line(30, 10, 40, 22, RED, 3.2) + line(40, 10, 30, 22, RED, 3.2)
    return out


@icon("surfmod_merge")
def _():
    # two pieces of one sheet (a seam between them) joined into one face
    out = poly([(4, 34), (22, 40), (22, 22), (4, 16)], BLUE[1], 'fill-opacity="0.85"')
    out += poly([(26, 40), (44, 34), (44, 16), (26, 22)], BLUE[1], 'fill-opacity="0.85"')
    out += line(22, 22, 22, 40, BLUE[2], 1.6) + line(26, 22, 26, 40, BLUE[2], 1.6)
    out += arrow(10, 10, 20, 10, ORANGE, 2.2, 4.5) + arrow(38, 10, 28, 10, ORANGE, 2.2, 4.5)
    return out


@icon("surfmod_press_pull")
def _():
    # an open box of sheets whose floor is pulled down: the walls follow
    out = poly([(8, 30), (26, 36), (40, 28), (22, 22)], BLUE[1], 'fill-opacity="0.85"')
    out += poly([(8, 30), (8, 12), (26, 18), (26, 36)], BLUE[0], 'fill-opacity="0.85"')
    out += poly([(26, 36), (26, 18), (40, 10), (40, 28)], BLUE[0], 'fill-opacity="0.7"')
    out += arrow(30, 22, 30, 46, ORANGE, 2.4, 5.0)
    return out
