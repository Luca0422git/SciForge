# SPDX-License-Identifier: LGPL-2.1-or-later
"""The navigation bar's choices and maths, without FreeCAD or Qt: unit tested.

Visual styles      VISUAL_STYLES: Fusion's six, each as FreeCAD's draw style plus whether
                   SciForge draws the hidden edges (dashed) over it.
Environments       ENVIRONMENTS: the background each one gives the 3D view.
Camera             wants_ortho: Perspective with Ortho Faces looks straight at a face.
Pan / Zoom         pan_shift, zoom_factor, zoom_window.
Viewports          LAYOUTS, cells.
Grid               grid_step (adaptive spacing), grid_lines.
Increments         snap (Incremental Move).
"""

import math

# name, FreeCAD draw style (View3DInventorViewer override mode), hidden edges drawn dashed,
# faces filled with the background colour (a hidden-line look: FreeCAD's own "Hidden Line"
# draws every triangle's edges, so SciForge fills the faces itself)
VISUAL_STYLES = [
    ("Shaded", "Shaded", False, False),
    ("Shaded with Hidden Edges", "Flat Lines", True, False),
    ("Shaded with Visible Edges Only", "As Is", False, False),
    ("Wireframe", "Wireframe", False, False),
    ("Wireframe with Hidden Edges", "Flat Lines", True, True),
    ("Wireframe with Visible Edges Only", "Flat Lines", False, True),
]
DEFAULT_STYLE = "Shaded with Visible Edges Only"  # Fusion's default
STYLE_NAMES = [s[0] for s in VISUAL_STYLES]


def style(name):
    """(FreeCAD draw style, hidden edges dashed, faces filled with the background) of a
    visual style (the default's for an unknown name)."""
    for label, mode, hidden, fill in VISUAL_STYLES:
        if label == name:
            return mode, hidden, fill
    return style(DEFAULT_STYLE)


def background_of(name):
    """One colour for an environment's background (the middle of a gradient)."""
    top, bottom = environment(name)
    a, b = rgb(top), rgb(bottom)
    return tuple((x + y) / 2.0 for x, y in zip(a, b))


# name -> (top colour, bottom colour) of the background (one colour: flat). The first is
# SciForge's own theme (Fusion: Theme, the default). Fusion's others are lit scenes
# (pictures all round the model); SciForge gives their look of the background only.
ENVIRONMENTS = [
    ("Theme", ("#2a2a2a", "#2a2a2a")),
    ("Photo Booth", ("#f2f2f2", "#b9bec6")),
    ("Grey Room", ("#9a9ea5", "#5d6168")),
    ("Dark Sky", ("#0e1626", "#3a4a66")),
    ("Infinity Pool", ("#c9e4f2", "#6f9db8")),
    ("Tranquility Blue", ("#4f79a8", "#1d3550")),
    ("Warm Light", ("#f4e2c4", "#a98a62")),
]
DEFAULT_ENVIRONMENT = "Theme"
ENVIRONMENT_NAMES = [e[0] for e in ENVIRONMENTS]


def environment(name):
    for label, colors in ENVIRONMENTS:
        if label == name:
            return colors
    return ENVIRONMENTS[0][1]


def rgb(hex_color):
    """'#rrggbb' -> (r, g, b) in 0..1."""
    value = hex_color.lstrip("#")
    return tuple(int(value[i : i + 2], 16) / 255.0 for i in (0, 2, 4))


CAMERAS = ["Orthographic", "Perspective", "Perspective with Ortho Faces"]
DEFAULT_CAMERA = "Orthographic"


def wants_ortho(direction, tolerance_deg=0.5):
    """Perspective with Ortho Faces: orthographic while the view looks straight along an
    axis (at a face of the ViewCube), perspective otherwise."""
    x, y, z = direction
    size = math.sqrt(x * x + y * y + z * z)
    if size <= 0:
        return False
    biggest = max(abs(x), abs(y), abs(z)) / size
    return biggest >= math.cos(math.radians(tolerance_deg))


# -- pan and zoom ------------------------------------------------------------------------------
def pan_shift(dx, dy, widget_height, view_height):
    """How far (mm, along the screen's right and up) the camera moves when the mouse drags
    (dx, dy) pixels (Qt: y down) so that the model follows the mouse."""
    if widget_height <= 0:
        return 0.0, 0.0
    per_pixel = view_height / float(widget_height)
    return -dx * per_pixel, dy * per_pixel


def zoom_factor(dy, pixels_per_double=160.0):
    """View size factor for a vertical Zoom drag of dy pixels (Qt: y down): dragging up
    zooms in (smaller view), down zooms out."""
    return 2.0 ** (dy / pixels_per_double)


def zoom_window(x0, y0, x1, y1, width, height):
    """Zoom Window: the drawn rectangle (widget pixels) fills the view. Returns (cx, cy,
    factor): the rectangle's middle as fractions of the view from its middle (-0.5 .. 0.5,
    x right, y up) and the new view size as a fraction of the old. None for a rectangle
    too small to mean anything (a click)."""
    w = abs(x1 - x0)
    h = abs(y1 - y0)
    if width <= 0 or height <= 0 or w < 4 or h < 4:
        return None
    cx = ((x0 + x1) / 2.0) / width - 0.5
    cy = 0.5 - ((y0 + y1) / 2.0) / height
    factor = max(w / float(width), h / float(height))
    return cx, cy, factor


# -- viewports -----------------------------------------------------------------------------------
# layout -> panes: (column, row, columns, rows) on a grid, and the view each pane starts with
LAYOUTS = {
    "Single View": ([(0, 0, 1, 1)], ["home"], 1, 1),
    "Two Views Horizontal": ([(0, 0, 1, 1), (1, 0, 1, 1)], ["home", "front"], 2, 1),
    "Two Views Vertical": ([(0, 0, 1, 1), (0, 1, 1, 1)], ["home", "front"], 1, 2),
    "Multiple Views": (
        [(0, 0, 1, 1), (1, 0, 1, 1), (0, 1, 1, 1), (1, 1, 1, 1)],
        ["top", "front", "right", "home"],
        2,
        2,
    ),
}
LAYOUT_NAMES = list(LAYOUTS)


def cells(layout, width, height, gap=2):
    """[(x, y, w, h)] of the panes of a layout in an area width x height (Qt pixels)."""
    panes, _views, cols, rows = LAYOUTS[layout]
    out = []
    for col, row, span_c, span_r in panes:
        x0 = int(round(col * width / float(cols)))
        x1 = int(round((col + span_c) * width / float(cols)))
        y0 = int(round(row * height / float(rows)))
        y1 = int(round((row + span_r) * height / float(rows)))
        left = gap // 2 if col > 0 else 0
        right = gap - gap // 2 if col + span_c < cols else 0
        top = gap // 2 if row > 0 else 0
        bottom = gap - gap // 2 if row + span_r < rows else 0
        out.append((x0 + left, y0 + top, x1 - x0 - left - right, y1 - y0 - top - bottom))
    return out


def views_of(layout):
    return list(LAYOUTS[layout][1])


# -- grid -----------------------------------------------------------------------------------------
NICE = (1.0, 2.0, 5.0)


def grid_step(view_height, lines=6.0):
    """Adaptive grid spacing: a round number (1, 2, 5 x 10^n mm) giving about `lines`
    major lines across the view's height."""
    if view_height <= 0:
        return 10.0
    raw = view_height / lines
    power = 10.0 ** math.floor(math.log10(raw))
    for nice in NICE + (10.0,):
        if nice * power >= raw * 0.999:
            return nice * power
    return 10.0 * power


def grid_lines(centre, half, major, subdivisions):
    """Grid lines on the XY plane round `centre` (x, y), `half` mm each way, every `major`
    mm with `subdivisions` minor lines between: ([(x0, y0, x1, y1)] major, [...] minor)."""
    if major <= 0 or half <= 0:
        return [], []
    subdivisions = max(1, int(subdivisions))
    minor_step = major / subdivisions
    cx, cy = centre
    first_x = math.floor((cx - half) / minor_step)
    last_x = math.ceil((cx + half) / minor_step)
    first_y = math.floor((cy - half) / minor_step)
    last_y = math.ceil((cy + half) / minor_step)
    x_lo, x_hi = first_x * minor_step, last_x * minor_step
    y_lo, y_hi = first_y * minor_step, last_y * minor_step
    majors, minors = [], []
    if last_x - first_x > 4000 or last_y - first_y > 4000:
        return [], []
    for i in range(first_x, last_x + 1):
        x = i * minor_step
        (majors if i % subdivisions == 0 else minors).append((x, y_lo, x, y_hi))
    for j in range(first_y, last_y + 1):
        y = j * minor_step
        (majors if j % subdivisions == 0 else minors).append((x_lo, y, x_hi, y))
    return majors, minors


# -- increments ------------------------------------------------------------------------------
DEFAULT_LINEAR = 1.0  # mm
DEFAULT_ANGULAR = 15.0  # degrees


def snap(value, step):
    """Incremental Move: `value` to the nearest multiple of `step` (no step: unchanged)."""
    if step is None or step <= 0:
        return value
    return round(value / step) * step


def ground_level(z_min, size, percent):
    """Height of the ground plane: under the model's lowest point by `percent` of its size
    (Ground Plane Offset 0 = touching)."""
    return z_min - max(0.0, float(percent)) / 100.0 * max(0.0, float(size))
