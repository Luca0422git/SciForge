# SPDX-License-Identifier: LGPL-2.1-or-later
# SURFACE part 3 icons (wave 6, builder surface-3). make_icons.py runs this file in its own
# namespace, so icon / circle / path / line ... and the palette are its own. Original artwork.


@icon("environment_map")  # noqa: F821
def _():
    # a shiny ball reflecting three soft studio light strips
    out = circle(24, 24, 15, "#5b6270")  # noqa: F821
    out += ellipse(24, 15, 11, 3.2, "#c9d3df")  # noqa: F821
    out += ellipse(24, 24, 14, 2.4, "#9fb2c8")  # noqa: F821
    out += ellipse(24, 32.5, 11, 2.0, "#7d8ea3")  # noqa: F821
    out += circle(18.5, 17.5, 2.6, WHITE)  # noqa: F821
    out += circle(24, 24, 15, "none", STROKE, 0.7)  # noqa: F821
    return out
