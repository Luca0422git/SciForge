# SPDX-License-Identifier: LGPL-2.1-or-later
# PLASTIC part 2 icons (Snap Fit, Lip, Design Advice). Run by make_icons.py in its own
# namespace (icon, block, poly, path, line, rect, circle, arrow, warn_badge, the palette).
# Original drawings in SciForge's style; nothing copied from Fusion.
# flake8: noqa: F821


@icon("pl_snap_fit")
def _():
    # a grey lid with a blue cantilever hook hanging from it, the catch at its free end
    return (
        block(0, 0, 0, 24, 8, 5, GREY, 24, 16)
        + poly([(20, 21), (25, 21), (25, 40), (20, 40)], BLUE[1])
        + poly([(25, 33), (31, 37), (31, 40), (25, 44), (20, 44), (20, 40), (25, 40)], BLUE[2])
        + path("M33 26 L33 34", WHITE, 1.6)
        + poly([(30.5, 26.5), (35.5, 26.5), (33, 23)], WHITE)
    )


@icon("pl_lip")
def _():
    # section through the two halves: the base's rim with a blue lip, the lid's wall with the
    # matching groove above it
    return (
        poly([(8, 42), (8, 26), (20, 26), (20, 30), (28, 30), (28, 42)], GREY[1])
        + poly([(20, 26), (20, 19), (24, 19), (24, 26)], BLUE[1])
        + poly(
            [(8, 6), (28, 6), (28, 22), (25, 22), (25, 16), (19, 16), (19, 22), (8, 22)], GREY[0]
        )
        + line(30, 22, 40, 22, WHITE, 1.4)
        + line(30, 26, 40, 26, WHITE, 1.4)
    )


@icon("pl_design_advice")
def _():
    # a moulded part coloured by the check (green fine, yellow draft, red thin) and a magnifier
    return (
        poly([(6, 40), (6, 14), (12, 14), (12, 34), (30, 34), (30, 40)], GREEN)
        + poly([(30, 34), (36, 34), (36, 40), (30, 40)], RED)
        + poly([(6, 14), (12, 14), (12, 10), (6, 10)], "#f6dc5c")
        + circle(30, 18, 8, "none", WHITE, 2.4)
        + line(36, 24, 42, 30, WHITE, 3.0)
    )


@icon("pl_snap_groove")
def _():
    # the follower in the other body: a wall with a window the catch goes into
    return block(0, 0, 0, 6, 24, 22, GREY, 24, 32) + poly(
        [
            iso(6, 8, 14, 24, 32),
            iso(6, 16, 14, 24, 32),
            iso(6, 16, 8, 24, 32),
            iso(6, 8, 8, 24, 32),
        ],
        BLUE[2],
    )
