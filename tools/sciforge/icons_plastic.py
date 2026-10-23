# SPDX-License-Identifier: LGPL-2.1-or-later
# PLASTIC tab icons, part 1 (wave 6, plastic-1): Assign / Manage Plastic Rules, Boss, Rest,
# Rule Fillet. Run inside make_icons.py's namespace (block, poly, iso, ... are its helpers).
# Original artwork in the style of the existing icons.
# flake8: noqa


def _rule_card(x, y, w, h):
    """A rule sheet: a card with three value lines."""
    return (
        rect(x, y, w, h, GREY[0], 2.5, 'stroke="%s" stroke-width="0.7"' % DARK)
        + line(x + 4, y + 6, x + w - 4, y + 6, BLUE[2], 2.2)
        + line(x + 4, y + 11.5, x + w - 7, y + 11.5, GREY[2], 2.0)
        + line(x + 4, y + 17, x + w - 9, y + 17, GREY[2], 2.0)
    )


@icon("pl_assign")
def _():
    # a moulded part (open box) and the rule card pinned to it
    return (
        block(0, 0, 0, 22, 22, 9, GREY, 22, 32)
        + poly([iso(3, 3, 9, 22, 32), iso(19, 3, 9, 22, 32), iso(19, 19, 9, 22, 32), iso(3, 19, 9, 22, 32)], BLUE[2])
        + _rule_card(25, 6, 17, 22)
        + line(25, 24, 20, 28, BLUE[2], 2.0)
    )


@icon("pl_manage")
def _():
    # two rule cards and a pencil
    return (
        _rule_card(6, 6, 20, 24)
        + _rule_card(14, 14, 20, 24)
        + poly([(30, 40), (42, 28), (45, 31), (33, 43)], GOLD[1], 'stroke="%s" stroke-width="0.7"' % DARK)
        + poly([(30, 40), (33, 43), (28.5, 44.5)], DARK)
    )


@icon("pl_boss")
def _():
    # a plate with a hollow screw boss standing on it and a rib
    ox, oy = 24, 34
    cx, cy = iso(10, 10, 6, ox, oy)
    top_y = cy - 14
    return (
        block(0, 0, 0, 20, 20, 6, GREY, ox, oy)
        + poly([(cx - 5.2, cy - 2), (cx - 5.2, top_y), (cx + 5.2, top_y), (cx + 5.2, cy - 2)], BLUE[1])
        + poly([(cx + 5.2, cy - 2), (cx + 12, cy + 1.5), (cx + 5.2, top_y + 5)], BLUE[2])
        + ellipse(cx, cy - 2, 5.2, 2.6, BLUE[1])
        + ellipse(cx, top_y, 5.2, 2.6, BLUE[0], DARK, 0.7)
        + ellipse(cx, top_y, 2.2, 1.1, DARK)
    )


@icon("pl_rest")
def _():
    # a curved wall with a flat landing cut into its crown
    return (
        path("M6 34 Q24 6 42 34 Z", DARK, 0.7, GREY[1])
        + path("M10 34 Q24 12 38 34", GREY[2], 1.6)
        + poly([(15, 19), (33, 19), (31, 23), (17, 23)], BLUE[1], 'stroke="%s" stroke-width="0.7"' % DARK)
        + line(15, 19, 33, 19, BLUE[2], 2.2)
    )


@icon("pl_rule_fillet")
def _():
    # a rounded corner of a block and the rule card's corner
    return (
        path("M8 38 L8 20 Q8 10 18 10 L36 10 L36 38 Z", DARK, 0.7, GREY[1])
        + path("M8 20 Q8 10 18 10", BLUE[2], 3.0)
        + _rule_card(26, 22, 16, 21)
    )
