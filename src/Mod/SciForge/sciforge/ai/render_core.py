# SPDX-License-Identifier: LGPL-2.1-or-later
"""A small software renderer for the AI tool render (docs/sciforge/dev/cadcraft-lessons.md
idea 3: "render returning the image itself"), used when there is no SciForge window to take
the picture from: the headless backend, the command line, the MCP server's --headless mode,
or a window whose 3D view cannot be captured (no graphics card).

It draws triangles (the bodies' faces, tessellated by the caller) with a depth buffer and
flat shading from two lights fixed to the camera, then the edges on top (hidden ones are
left out), a small X / Y / Z axis triad in the corner (red, green, blue as in Fusion's view
cube), anti-aliased by drawing at twice the size and averaging. The camera is orthographic,
looking from one of Fusion's standard views (iso = Fusion's Home view: from the front,
right and top) or from any direction, and fits the scene to the picture. The result is a PNG
written here (zlib, no imaging library), so the AI app gets the picture itself.

Pure Python plus numpy (FreeCAD ships numpy; the unit tests run it with plain Python). No
FreeCAD, no Qt: sciforge/ai/actions/verify_actions.py turns a design into the scene.
"""

import math
import struct
import zlib

# view name -> (the direction the camera looks FROM, the screen's up direction). The
# standard views of Fusion's view cube with Z up, as SciForge sets them (Front looks along
# +Y, Top down -Z with Y up, Right along -X; iso from front, right and top).
VIEWS = {
    "iso": ((1.0, -1.0, 1.0), (0.0, 0.0, 1.0)),
    "front": ((0.0, -1.0, 0.0), (0.0, 0.0, 1.0)),
    "back": ((0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
    "top": ((0.0, 0.0, 1.0), (0.0, 1.0, 0.0)),
    "bottom": ((0.0, 0.0, -1.0), (0.0, -1.0, 0.0)),
    "left": ((-1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
    "right": ((1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
}
VIEW_NAMES = ("iso", "front", "back", "top", "bottom", "left", "right")

BODY_COLORS = (
    (168, 180, 196),  # a light steel blue: the first body
    (204, 178, 140),
    (150, 190, 160),
    (196, 160, 196),
    (210, 200, 130),
    (140, 180, 210),
)
HIGHLIGHT = (255, 136, 0)  # what the AI asked to see marked: orange
EDGE = (36, 40, 48)
SKETCH = (30, 90, 200)
BACKGROUND_TOP = (250, 251, 253)
BACKGROUND_BOTTOM = (218, 224, 232)
AXIS_COLORS = ((220, 50, 47), (40, 160, 60), (40, 90, 220))
SUPERSAMPLE = 2
SUPERSAMPLE_UP_TO = 2048 * 2048  # pixels; a bigger picture is drawn once (memory)
MARGIN = 0.06  # of the picture, around a fitted scene


class RenderError(ValueError):
    """The scene cannot be drawn (the message says why, in a sentence)."""


def _np():
    try:
        import numpy

        return numpy
    except ImportError:
        raise RenderError(
            "Drawing a picture without the SciForge window needs numpy, which this Python "
            "does not have."
        )


# -- camera ---------------------------------------------------------------------------------
def _unit(v):
    n = math.sqrt(sum(c * c for c in v))
    if n < 1e-12:
        raise RenderError("A view direction cannot be [0, 0, 0].")
    return tuple(c / n for c in v)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def camera(view="iso", direction=None, up=None):
    """(right, up, forward) unit vectors: screen x, screen y and into the screen. direction:
    where the camera looks from ([x, y, z]); otherwise the named view."""
    if direction is None:
        if view not in VIEWS:
            raise RenderError(
                "There is no view called %r (they are %s)." % (view, ", ".join(VIEW_NAMES))
            )
        direction, default_up = VIEWS[view]
        up = up or default_up
    eye = _unit(direction)
    forward = (-eye[0], -eye[1], -eye[2])
    up = _unit(up or (0.0, 0.0, 1.0))
    if abs(_dot(up, forward)) > 0.999:  # looking straight along "up": Y is up instead
        up = (0.0, 1.0, 0.0) if abs(forward[1]) < 0.999 else (0.0, 0.0, 1.0)
    right = _unit(_cross(forward, up))
    up = _cross(right, forward)
    return right, up, forward


# -- the scene ------------------------------------------------------------------------------
def _items(value):
    """A list or an array of points / triangles as given (None: none)."""
    return [] if value is None else value


def render(
    meshes,
    lines=(),
    width=800,
    height=600,
    view="iso",
    direction=None,
    background=True,
    triad=True,
):
    """Draw the scene; returns (png bytes, info).

    meshes: [{"points": [(x, y, z), ...], "triangles": [(i, j, k), ...], "color": (r, g, b)}]
    (lists or numpy arrays; several meshes may share one points array; "in_front": true
    draws it over a face it lies on)
    lines: [{"points": [(x, y, z), ...] (a polyline), "color": (r, g, b), "width": px,
    "on_top": draw also where hidden}]. info: {"width", "height", "view", "mm_per_pixel",
    "triangles"}."""
    np = _np()
    width, height = int(width), int(height)
    if not (16 <= width <= 4096 and 16 <= height <= 4096):
        raise RenderError("The picture must be 16 to 4096 pixels wide and high.")
    right, up, forward = camera(view, direction)
    basis = np.array([right, up, forward], dtype=float).T  # (3, 3): world -> screen

    pts_all = []
    prepared = []
    for mesh in meshes:
        pts = np.asarray(_items(mesh.get("points")), dtype=float).reshape(-1, 3)
        tris = np.asarray(_items(mesh.get("triangles")), dtype=np.int64).reshape(-1, 3)
        if len(pts) == 0 or len(tris) == 0:
            continue
        if tris.min() < 0 or tris.max() >= len(pts):
            raise RenderError("A triangle refers to a point that is not there.")
        prepared.append(
            (pts, tris, mesh.get("color") or BODY_COLORS[0], bool(mesh.get("in_front")))
        )
        pts_all.append(pts)
    line_items = []
    for line in lines:
        pts = np.asarray(_items(line.get("points")), dtype=float).reshape(-1, 3)
        if len(pts) < 2:
            continue
        line_items.append(
            (pts, line.get("color") or EDGE, float(line.get("width", 1)), bool(line.get("on_top")))
        )
        pts_all.append(pts)

    s = SUPERSAMPLE if width * height <= SUPERSAMPLE_UP_TO else 1
    W, H = width * s, height * s
    image = np.empty((H, W, 3), dtype=np.float32)  # (float32: half the memory)
    if background:
        top, bottom = np.array(BACKGROUND_TOP, float), np.array(BACKGROUND_BOTTOM, float)
        t = np.linspace(0.0, 1.0, H)[:, None]
        image[:] = (top * (1 - t) + bottom * t)[:, None, :]
    else:
        image[:] = 255.0
    zbuf = np.full((H, W), np.inf, dtype=np.float32)

    if pts_all:
        every = np.vstack(pts_all) @ basis
        lo, hi = every.min(axis=0), every.max(axis=0)
    else:
        lo, hi = np.zeros(3), np.zeros(3)
    span_x, span_y = max(hi[0] - lo[0], 1e-9), max(hi[1] - lo[1], 1e-9)
    usable = 1.0 - 2.0 * MARGIN
    scale = min(W * usable / span_x, H * usable / span_y)
    if not pts_all or (hi[0] - lo[0] < 1e-9 and hi[1] - lo[1] < 1e-9):
        scale = 1.0 * s
    cx, cy = (lo[0] + hi[0]) / 2.0, (lo[1] + hi[1]) / 2.0
    depth_span = max(hi[2] - lo[2], max(span_x, span_y) * 1e-3, 1e-9)

    def to_screen(world):
        p = world @ basis
        return np.column_stack(
            (W / 2.0 + (p[:, 0] - cx) * scale, H / 2.0 - (p[:, 1] - cy) * scale, p[:, 2])
        )

    lights = [
        (_unit(tuple(-forward[i] * 0.85 + up[i] * 0.35 - right[i] * 0.25 for i in range(3))), 0.58),
        (_unit(tuple(-forward[i] * 0.5 - up[i] * 0.3 + right[i] * 0.6 for i in range(3))), 0.18),
    ]
    count = 0
    for pts, tris, color, in_front in prepared:
        scr = to_screen(pts)
        if in_front:  # (wins over a face it lies on: the polygon offset of OpenGL)
            scr[:, 2] -= depth_span * 2e-3
        a, b, c = pts[tris[:, 0]], pts[tris[:, 1]], pts[tris[:, 2]]
        normals = np.cross(b - a, c - a)
        lengths = np.linalg.norm(normals, axis=1)
        lengths[lengths < 1e-30] = 1.0
        normals /= lengths[:, None]
        shade = np.full(len(tris), 0.40)
        for direction_l, strength in lights:
            shade += strength * np.abs(normals @ np.array(direction_l))
        colors = np.clip(np.outer(np.minimum(shade, 1.08), np.array(color, float)), 0, 255)
        count += _fill(np, image, zbuf, scr, tris, colors)

    bias = depth_span * 4e-3
    for pts, color, line_width, on_top in line_items:
        _polyline(np, image, zbuf, to_screen(pts), color, max(1.0, line_width) * s, bias, on_top)

    if triad:
        _triad(np, image, right, up, forward, s)

    small = image.reshape(height, s, width, s, 3).mean(axis=(1, 3))
    rgb = np.clip(np.rint(small), 0, 255).astype(np.uint8)
    info = {
        "width": width,
        "height": height,
        "view": view if direction is None else [round(float(v), 6) for v in direction],
        "mm_per_pixel": round(float(s / scale), 6) if pts_all else None,
        "triangles": int(count),
    }
    return png_bytes(rgb), info


ROW_BUDGET = 1 << 18  # (triangle, pixel row) pairs handled at once
PIXEL_BUDGET = 1 << 20  # covered pixels handled at once: memory stays near 100 MB


def _fill(np, image, zbuf, scr, tris, colors):
    """Draw the triangles with the depth buffer; returns how many covered a pixel. Every
    triangle is drawn row by row on the pixels whose centre it covers, all triangles at
    once in batches (no Python loop per triangle: the long thin triangles of a face with
    hundreds of holes made that loop take tens of seconds), the batches bounded so a big
    picture does not take gigabytes."""
    H, W = zbuf.shape
    tx, ty, tz = scr[:, 0][tris], scr[:, 1][tris], scr[:, 2][tris]
    area = (tx[:, 1] - tx[:, 0]) * (ty[:, 2] - ty[:, 0]) - (tx[:, 2] - tx[:, 0]) * (
        ty[:, 1] - ty[:, 0]
    )
    # the pixel rows whose centre (row + 0.5) lies within the triangle's height
    y0 = np.maximum(np.ceil(ty.min(axis=1) - 0.5), 0).astype(np.int64)
    y1 = np.minimum(np.floor(ty.max(axis=1) - 0.5), H - 1).astype(np.int64)
    keep = (np.abs(area) > 1e-12) & (y1 >= y0) & (tx.max(axis=1) >= 0) & (tx.min(axis=1) < W)
    which = np.nonzero(keep)[0]
    drawn = np.zeros(len(tris), dtype=bool)
    if not len(which):
        return 0
    heights = y1[which] - y0[which] + 1
    ends = np.cumsum(heights)
    zflat = zbuf.reshape(-1)
    iflat = image.reshape(-1, 3)
    first_tri = 0
    while first_tri < len(which):
        done_before = ends[first_tri] - heights[first_tri]
        last_tri = int(np.searchsorted(ends, done_before + ROW_BUDGET, side="right"))
        last_tri = max(last_tri, first_tri + 1)
        sub, h = which[first_tri:last_tri], heights[first_tri:last_tri]
        first_tri = last_tri
        t = np.repeat(sub, h)
        row = np.repeat(y0[sub], h) + (np.arange(int(h.sum())) - np.repeat(np.cumsum(h) - h, h))
        yc = row + 0.5
        left = np.full(len(t), np.inf)
        right = np.full(len(t), -np.inf)
        for i, j in ((0, 1), (1, 2), (2, 0)):
            ya, yb, xa, xb = ty[t, i], ty[t, j], tx[t, i], tx[t, j]
            dy = yb - ya
            slanted = np.abs(dy) >= 1e-12
            on = slanted & ((yc - ya) * (yc - yb) <= 0)
            x = xa + (yc - ya) * (xb - xa) / np.where(slanted, dy, 1.0)
            left = np.where(on, np.minimum(left, x), left)
            right = np.where(on, np.maximum(right, x), right)
        ok = np.isfinite(left)
        first = np.maximum(np.ceil(left[ok] - 0.5), 0).astype(np.int64)
        last = np.minimum(np.floor(right[ok] - 0.5), W - 1).astype(np.int64)
        t, row = t[ok], row[ok]
        ok = last >= first
        t, row, first, last = t[ok], row[ok], first[ok], last[ok]
        counts = last - first + 1
        done = np.cumsum(counts)
        a = 0
        while a < len(t):
            before = done[a] - counts[a]
            b = max(int(np.searchsorted(done, before + PIXEL_BUDGET, side="right")), a + 1)
            c = counts[a:b]
            tri = np.repeat(t[a:b], c)
            row_of = np.repeat(row[a:b], c)
            col = np.repeat(first[a:b], c) + (
                np.arange(int(c.sum())) - np.repeat(np.cumsum(c) - c, c)
            )
            a = b
            px, py = col + 0.5, row_of + 0.5
            ax, bx, cx = tx[tri, 0], tx[tri, 1], tx[tri, 2]
            ay, by, cy = ty[tri, 0], ty[tri, 1], ty[tri, 2]
            inv = 1.0 / area[tri]
            w0 = ((bx - px) * (cy - py) - (cx - px) * (by - py)) * inv
            w1 = ((cx - px) * (ay - py) - (ax - px) * (cy - py)) * inv
            depth = w0 * tz[tri, 0] + w1 * tz[tri, 1] + (1.0 - w0 - w1) * tz[tri, 2]
            pix = row_of * W + col
            order = np.lexsort((depth, pix))  # by pixel, the nearest first
            pix, depth, tri = pix[order], depth[order], tri[order]
            nearest = np.ones(len(pix), dtype=bool)
            nearest[1:] = pix[1:] != pix[:-1]
            pix, depth, tri = pix[nearest], depth[nearest], tri[nearest]
            nearer = depth < zflat[pix]
            pix, depth, tri = pix[nearer], depth[nearer], tri[nearer]
            zflat[pix] = depth
            iflat[pix] = colors[tri]
            drawn[tri] = True
    return int(drawn.sum())


def _polyline(np, image, zbuf, scr, color, width, bias, on_top=False):
    """A polyline 'width' pixels wide where it is not hidden behind a face."""
    H, W = zbuf.shape
    p0, p1 = scr[:-1], scr[1:]
    lengths = np.hypot(p1[:, 0] - p0[:, 0], p1[:, 1] - p0[:, 1])
    steps = np.maximum(np.ceil(lengths * 2.0).astype(np.int64), 1)
    seg = np.repeat(np.arange(len(p0)), steps + 1)
    starts = np.repeat(np.cumsum(steps + 1) - (steps + 1), steps + 1)
    t = (np.arange(len(seg)) - starts) / np.repeat(steps, steps + 1)
    pts = p0[seg] + (p1[seg] - p0[seg]) * t[:, None]
    radius = max(0.0, (width - 1.0) / 2.0)
    r = int(math.ceil(radius))
    color = np.array(color, float)
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx * dx + dy * dy > radius * radius + 0.25:
                continue
            ix = np.floor(pts[:, 0] + dx).astype(np.int64)
            iy = np.floor(pts[:, 1] + dy).astype(np.int64)
            ok = (ix >= 0) & (ix < W) & (iy >= 0) & (iy < H)
            ix, iy, depth = ix[ok], iy[ok], pts[ok, 2]
            if not on_top:
                visible = depth <= zbuf[iy, ix] + bias
                ix, iy = ix[visible], iy[visible]
            image[iy, ix] = color


def _triad(np, image, right, up, forward, s):
    """X / Y / Z arrows in the lower left corner, the nearest drawn last."""
    H, W = image.shape[:2]
    size = 34.0 * s
    ox, oy = 18.0 * s + size, H - 18.0 * s - size
    axes = []
    for i, color in enumerate(AXIS_COLORS):
        v = [0.0, 0.0, 0.0]
        v[i] = 1.0
        axes.append((_dot(v, forward), _dot(v, right), _dot(v, up), color))
    zbuf = np.full(image.shape[:2], np.inf)
    for _depth, sx, sy, color in sorted(axes, reverse=True):
        end = (ox + sx * size, oy - sy * size)
        line = np.array([[ox, oy, 0.0], [end[0], end[1], 0.0]])
        _polyline(np, image, zbuf, line, color, 2.5 * s, 0.0, on_top=True)


# -- PNG --------------------------------------------------------------------------------------
def png_bytes(rgb):
    """A PNG file (8-bit RGB) from an (height, width, 3) uint8 array."""
    height, width = int(rgb.shape[0]), int(rgb.shape[1])
    raw = b"".join(b"\x00" + rgb[row].tobytes() for row in range(height))

    def chunk(tag, data):
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw, 6))
        + chunk(b"IEND", b"")
    )


def png_info(data):
    """(width, height) of a PNG file's bytes, or None when they are not a PNG."""
    if not isinstance(data, (bytes, bytearray)) or len(data) < 24:
        return None
    if data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        return None
    return struct.unpack(">II", data[16:24])


def png_pixels(data):
    """The pixels of a PNG this module wrote (8-bit RGB, no interlace) as a list of rows of
    (r, g, b): for the tests, which look at what was drawn. None for other PNGs."""
    size = png_info(data)
    if size is None or data[24:29] != bytes([8, 2, 0, 0, 0]):
        return None
    width, height = size
    pos, idat = 8, b""
    while pos < len(data):
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        tag = data[pos + 4 : pos + 8]
        if tag == b"IDAT":
            idat += data[pos + 8 : pos + 8 + length]
        pos += 12 + length
    raw = zlib.decompress(idat)
    stride = width * 3 + 1
    rows = []
    for y in range(height):
        line = raw[y * stride : (y + 1) * stride]
        if line[0] != 0:
            return None
        rows.append([tuple(line[1 + 3 * x : 4 + 3 * x]) for x in range(width)])
    return rows
