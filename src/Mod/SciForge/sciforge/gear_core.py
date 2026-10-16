# SPDX-License-Identifier: LGPL-2.1-or-later
"""The number logic of the Gear tool (SOLID > CREATE > Gear): no FreeCAD, no Qt, so it is
unit tested (SciForgeTests/unit/test_gear_core.py). gear.py builds the geometry from the
outline this module computes; the dialog (gear_ui.py) shows its sizes and messages.

Fusion has no Gear feature of its own: it ships a "Spur Gear" sample script (Standard,
Pressure Angle, Module / Diametral Pitch, Number of Teeth, Backlash, Root Fillet Radius,
Gear Thickness, Hole Diameter, Pitch Diameter shown read-only) that makes a sketch and an
extrude once and cannot be edited again. SciForge's Gear is a real timeline step with the
same fields plus Internal (ring) gears and Racks (docs/sciforge/parity/gear.md).

Options (dict, see DEFAULTS), lengths in mm:
  type            spur | internal | rack
  standard        metric (Module) | english (Diametral Pitch, teeth per inch)
  module          the pitch diameter divided by the number of teeth (metric)
  diametral_pitch teeth per inch of pitch diameter (english): module = 25.4 / DP
  teeth           number of teeth (a rack's, when rack_size is "teeth")
  pressure_angle  14.5 | 20 | 25 (degrees)
  backlash        how much thinner each tooth is at the pitch circle (pitch line)
  fillet          root fillet radius (0 = a sharp root)
  thickness       the gear's thickness (signed: negative goes the other way)
  symmetric       the thickness is split evenly on both sides of the plane
  hole            bore hole diameter of a spur gear (0 = none)
  rim             an internal gear's ring outside its root circle
  rack_size       teeth (the rack is teeth x pitch long) | length (cut to rack_length)
  rack_length     the rack's length when rack_size is "length"
  rack_height     material under the rack's root line
  operation       join | cut | new_body | new_component
  x, y            the centre clicked on the plane (a rack: the middle of its pitch line)

Tooth form (ISO 53 / AGMA full depth): addendum 1 module, dedendum 1.25 modules, so the
outside diameter is m(z + 2) and the root diameter m(z - 2.5). An internal gear's teeth
point inwards; their tips stop at the base circle when a full addendum would reach below
it (the flank below the base circle is no involute and would jam the pinion).

The involute outline is FreeCAD's own (src/Mod/PartDesign/fcgear/involute.py, LGPL-2.1+,
(c) 2014 David Douard, (c) 2023 Jonas Baehr, after gearUtils by Dr A.R. Collins and the
Higuchi et al. Bezier approximation): copied here with one change, `thinning`, which
turns each flank towards the middle of its tooth for the backlash (fcgear has none).
"""

import math

from .primitives_core import PrimitiveError, nice

TYPES = ("spur", "internal", "rack")
STANDARDS = ("metric", "english")
PRESSURE_ANGLES = (14.5, 20.0, 25.0)
RACK_SIZES = ("teeth", "length")
OPERATIONS = ("join", "cut", "new_body", "new_component")
INCH = 25.4
ADDENDUM = 1.0  # x module
DEDENDUM = 1.25  # x module
MIN_TEETH = {"spur": 6, "internal": 12, "rack": 1}
MAX_TEETH = 400  # more makes an outline of thousands of edges (seconds per preview)
MIN_RIM = 0.5  # x module: a thinner ring breaks between its teeth
MIN_WALL = 0.5  # x module: the least material left between a spur gear's hole and root

DEFAULTS = {
    "x": 0.0,
    "y": 0.0,
    "type": "spur",
    "standard": "metric",
    "module": 2.0,
    "diametral_pitch": 12.0,
    "teeth": 24,
    "pressure_angle": 20.0,
    "backlash": 0.0,
    "fillet": 0.5,
    "thickness": 10.0,
    "symmetric": False,
    "hole": 10.0,
    "rim": 5.0,
    "rack_size": "teeth",
    "rack_length": 100.0,
    "rack_height": 5.0,
    "operation": "new_body",
}

# The dialog fields that hold a length or a count (a parameter / formula can drive them).
NUMBER_KEYS = (
    "module",
    "diametral_pitch",
    "teeth",
    "backlash",
    "fillet",
    "thickness",
    "hole",
    "rim",
    "rack_length",
    "rack_height",
)
# Which fields each type shows (besides Standard, the module / pitch and Thickness).
USES = {
    "spur": ("teeth", "backlash", "fillet", "hole"),
    "internal": ("teeth", "backlash", "fillet", "rim"),
    "rack": ("teeth", "backlash", "fillet", "rack_size", "rack_length", "rack_height"),
}


class GearError(PrimitiveError):
    """The gear cannot be built as asked; the message says why and what to change."""


def with_defaults(options):
    out = dict(DEFAULTS)
    out.update({k: v for k, v in (options or {}).items() if v is not None})
    out.setdefault("expressions", {})
    return out


def module_of(options):
    """The module in mm, from the Module (metric) or the Diametral Pitch (english)."""
    if options.get("standard", "metric") == "english":
        dp = float(options.get("diametral_pitch", 0.0))
        if dp <= 1e-9:
            raise GearError("The Diametral Pitch must be more than 0 (teeth per inch).")
        return INCH / dp
    m = float(options.get("module", 0.0))
    if m <= 1e-9:
        raise GearError("The Module must be more than 0 mm.")
    return m


def teeth_of(options):
    return int(round(float(options.get("teeth", 0))))


def internal_addendum(z, alpha_deg):
    """An internal gear's addendum coefficient: 1, or less so its tips stop at the base
    circle (FreeCAD's internal gear uses 0.6 for the same reason; see the module doc)."""
    reach = z / 2.0 * (1.0 - math.cos(math.radians(alpha_deg)))
    return min(ADDENDUM, reach * (1.0 - 1e-9))


def sizes(options):
    """The gear's main sizes (mm), as the dialog shows them (Pitch Diameter read-only).
    Keys: module, pitch (circular pitch p = pi m), pitch_diameter, outside_diameter,
    root_diameter, base_diameter, tip_diameter (the teeth's tips; an internal gear's
    point inwards), rack_length, rack_teeth, rack_depth (top to bottom of a rack)."""
    o = with_defaults(options)
    m = module_of(o)
    z = teeth_of(o)
    alpha = math.radians(float(o["pressure_angle"]))
    d = m * z
    out = {
        "module": m,
        "pitch": math.pi * m,
        "pitch_diameter": d,
        "base_diameter": d * math.cos(alpha),
    }
    kind = o["type"]
    if kind == "spur":
        out["tip_diameter"] = out["outside_diameter"] = m * (z + 2.0 * ADDENDUM)
        out["root_diameter"] = m * (z - 2.0 * DEDENDUM)
    elif kind == "internal":
        out["root_diameter"] = m * (z + 2.0 * DEDENDUM)
        out["tip_diameter"] = d - 2.0 * m * internal_addendum(z, o["pressure_angle"])
        out["outside_diameter"] = out["root_diameter"] + 2.0 * float(o["rim"])
    else:
        out["pitch_diameter"] = 0.0
        out["base_diameter"] = 0.0
        p = math.pi * m
        if o["rack_size"] == "length":
            out["rack_length"] = float(o["rack_length"])
            out["rack_teeth"] = int(math.floor(out["rack_length"] / p + 1e-9))
        else:
            out["rack_length"] = z * p
            out["rack_teeth"] = z
        out["rack_depth"] = (ADDENDUM + DEDENDUM) * m + float(o["rack_height"])
    return out


# -- checks ---------------------------------------------------------------------------------------
def _fmt(value):
    return "%.4g" % value


def check(options):
    """Raise GearError saying what to change when the values cannot make the gear; else
    return the outline (as profile())."""
    o = with_defaults(options)
    kind = o["type"]
    if kind not in TYPES:
        raise GearError("Unknown gear type %r: Spur, Internal or Rack." % kind)
    if o["standard"] not in STANDARDS:
        raise GearError("Unknown standard %r: Metric or English." % o["standard"])
    m = module_of(o)
    alpha = float(o["pressure_angle"])
    if not any(abs(alpha - a) < 1e-6 for a in PRESSURE_ANGLES):
        raise GearError("The Pressure Angle is 14.5, 20 or 25 degrees.")
    z_raw = float(o["teeth"])
    z = teeth_of(o)
    if kind != "rack" or o["rack_size"] == "teeth":
        if abs(z_raw - z) > 1e-6:
            raise GearError("The Number of Teeth is a whole number (not %s)." % _fmt(z_raw))
        if z < MIN_TEETH[kind]:
            what = {"spur": "A spur gear", "internal": "An internal gear", "rack": "A rack"}
            raise GearError(
                "%s needs at least %d teeth (%d asked). Use more teeth."
                % (what[kind], MIN_TEETH[kind], z)
            )
        if z > MAX_TEETH:
            raise GearError(
                "%d teeth is more than this tool makes (%d). Use fewer teeth or a larger "
                "module." % (z, MAX_TEETH)
            )
    if float(o["backlash"]) < 0:
        raise GearError("The Backlash cannot be negative.")
    if float(o["fillet"]) < 0:
        raise GearError("The Root Fillet Radius cannot be negative.")
    if abs(float(o["thickness"])) < 1e-9:
        raise GearError("The Thickness cannot be 0.")
    s = sizes(o)
    if kind == "spur":
        hole = float(o["hole"])
        if hole < 0:
            raise GearError("The Hole Diameter cannot be negative (0 = no hole).")
        biggest = s["root_diameter"] - 2.0 * MIN_WALL * m
        if hole > 1e-9 and hole > biggest + 1e-9:
            raise GearError(
                "The hole (%s mm) is too big for this gear: its root circle is %s mm across. "
                "Make the Hole Diameter at most %s mm, or use more teeth or a larger module."
                % (_fmt(hole), _fmt(s["root_diameter"]), _fmt(max(biggest, 0.0)))
            )
    if kind == "internal":
        rim = float(o["rim"])
        if rim < MIN_RIM * m - 1e-9:
            raise GearError(
                "The rim (%s mm) is too thin to hold the teeth. Make the Rim Thickness at "
                "least %s mm (half the module)." % (_fmt(rim), _fmt(MIN_RIM * m))
            )
    if kind == "rack":
        if float(o["rack_height"]) <= 1e-9:
            raise GearError("The rack's Height under the teeth must be more than 0.")
        if o["rack_size"] not in RACK_SIZES:
            raise GearError("Unknown rack size %r." % o["rack_size"])
        if o["rack_size"] == "length":
            if float(o["rack_length"]) < s["pitch"] - 1e-9:
                raise GearError(
                    "The rack (%s mm) is shorter than one tooth (the pitch is %s mm). Make "
                    "it longer." % (_fmt(float(o["rack_length"])), _fmt(s["pitch"]))
                )
            if float(o["rack_length"]) / s["pitch"] > MAX_TEETH:
                raise GearError(
                    "This rack has more than %d teeth. Make it shorter or the module larger."
                    % MAX_TEETH
                )
    return profile(o)


# -- the outline ----------------------------------------------------------------------------------
# A loop is a closed list of segments in the plane (the gear's centre at 0, 0):
#   ("line", a, b)                 a straight edge from a to b
#   ("arc", a, mid, b)             a circular arc from a through mid to b
#   ("bezier", [a, p1, ..., b])    a Bezier curve (its poles)
#   ("circle", centre, radius)     a whole circle (a loop of its own)
def profile(options):
    """The gear's closed outlines: [outer loop, hole loops...]. Raises GearError."""
    o = with_defaults(options)
    if o["type"] == "rack":
        return [_rack_loop(o)]
    loops, lands = _circular(o)
    _check_lands(lands, o)
    return loops


def _circular(o):
    """(loops, lands) of a spur or internal gear; lands = the width (mm) of the flat left
    at the tips and the roots, keyed "tip" / "root" (< 0: the outline cannot close)."""
    m = module_of(o)
    z = teeth_of(o)
    alpha = math.radians(float(o["pressure_angle"]))
    backlash = float(o["backlash"])
    fillet = float(o["fillet"])
    r_ref = m * z / 2.0
    teeth = _Recorder()
    if o["type"] == "spur":
        outer, inner = _involute(
            teeth,
            m,
            z,
            alpha,
            outer_height=ADDENDUM,
            inner_height=DEDENDUM,
            inner_fillet=fillet / m,
            thinning=backlash / (2.0 * r_ref),
        )
        lands = {"tip": outer, "root": inner}
        if min(outer, inner) < _least(m):
            return [], lands
        loops = [teeth.loop()]
        hole = float(o["hole"])
        if hole > 1e-9:
            loops.append([("circle", (0.0, 0.0), hole / 2.0)])
        return loops, lands
    add = internal_addendum(z, float(o["pressure_angle"]))
    outer, inner = _involute(
        teeth,
        m,
        z,
        alpha,
        rotation=math.pi / z,
        outer_height=DEDENDUM,
        inner_height=add,
        outer_fillet=fillet / m,
        thinning=-backlash / (2.0 * r_ref),  # the generator's tooth is the ring's space
    )
    lands = {"tip": inner, "root": outer}
    if min(outer, inner) < _least(m):
        return [], lands
    rim = r_ref + DEDENDUM * m + float(o["rim"])
    return [[("circle", (0.0, 0.0), rim)], teeth.loop()], lands


def _least(m):
    return 1e-4 * m


def _check_lands(lands, o):
    """The tips and the roots must keep a flat land: else the flanks cross (a pointed or
    over-thinned tooth) or the root fillets overlap."""
    m = module_of(o)
    backlash = float(o["backlash"])
    fillet = float(o["fillet"])
    if lands["tip"] < _least(m):
        if backlash > 1e-9:
            raise GearError(
                "With this Backlash (%s mm) the teeth come to a point. Make the backlash "
                "smaller." % _fmt(backlash)
            )
        raise GearError(
            "With these values the teeth come to a point. Use more teeth or another "
            "pressure angle."
        )
    if lands["root"] < _least(m):
        if fillet > 1e-9:
            raise GearError(
                "The Root Fillet Radius (%s mm) does not fit between the teeth. Make it "
                "at most %s mm." % (_fmt(fillet), _fmt(max_fillet(o)))
            )
        raise GearError("With these values the teeth run into each other. Use more teeth.")


def max_fillet(options):
    """The largest Root Fillet Radius that still fits between the teeth (mm), rounded
    down to 0.001 mm."""
    o = with_defaults(options)
    m = module_of(o)
    if o["type"] == "rack":
        return _rack_max_fillet(o)
    lo, hi = 0.0, 1.0 * m
    for _ in range(30):
        mid = (lo + hi) / 2.0
        try:
            _loops, lands = _circular(dict(o, fillet=mid))
            fits = lands["root"] >= _least(m) and lands["tip"] >= _least(m)
        except GearError:
            fits = False
        if fits:
            lo = mid
        else:
            hi = mid
    return math.floor(lo * 1000.0) / 1000.0


# -- the involute generator (FreeCAD's fcgear, see the module doc) --------------------------------
class _Recorder:
    """fcgear's wire builder protocol (move / line / arc / curve), recording segments."""

    def __init__(self):
        self.pos = None
        self.theta = 0.0
        self.segments = []

    def move(self, p):
        self.pos = (float(p[0]), float(p[1]))

    def line(self, p):
        end = _rotate(p, self.theta)
        self.segments.append(("line", self.pos, end))
        self.pos = end

    def arc(self, p, r, sweep):
        end = _rotate(p, self.theta)
        mid = _midpoints(end, self.pos, r)[sweep]
        self.segments.append(("arc", self.pos, mid, end))
        self.pos = end

    def curve(self, *points):
        poles = [_rotate(p, self.theta) for p in points]
        self.segments.append(("bezier", [self.pos] + poles))
        self.pos = poles[-1]

    def loop(self):
        """The segments as a closed loop: the last end is set exactly onto the start
        (fcgear ends there within rounding)."""
        segs = list(self.segments)
        if not segs:
            return segs
        start = _start(segs[0])
        last = segs[-1]
        if last[0] == "line":
            segs[-1] = ("line", last[1], start)
        elif last[0] == "arc":
            segs[-1] = ("arc", last[1], last[2], start)
        else:
            segs[-1] = ("bezier", last[1][:-1] + [start])
        return segs


def _rotate(pt, rads):
    s, c = math.sin(rads), math.cos(rads)
    return (pt[0] * c - pt[1] * s, pt[0] * s + pt[1] * c)


def _mirror(pt):
    return (pt[0], -pt[1])


def _polar(radius, angle):
    return (radius * math.cos(angle), radius * math.sin(angle))


def _inv(rb, r):
    """The involute's polar angle at radius r (base circle rb)."""
    return math.sqrt(r * r - rb * rb) / rb - math.acos(rb / r)


def _midpoints(p1, p2, r):
    """The two midpoints of an arc of radius r from p2 to p1 (fcgear.midpoints)."""
    vx, vy = p2[0] - p1[0], p2[1] - p1[1]
    b = math.hypot(vx, vy)
    if b < 1e-15:
        raise GearError("A tooth outline degenerated. Change the values.")
    v = (vx / b, vy / b)
    cos_a = b / (2.0 * r)
    if cos_a > 1.0 + 1e-12:
        raise GearError("The root fillet does not fit. Make the Root Fillet Radius smaller.")
    a = math.acos(min(1.0, cos_a))
    out = []
    for sign in (1.0, -1.0):
        ux, uy = _rotate(v, sign * a)
        cx, cy = p1[0] + r * ux, p1[1] + r * uy
        mx, my = (p1[0] + p2[0]) / 2.0 - cx, (p1[1] + p2[1]) / 2.0 - cy
        dm = math.hypot(mx, my)
        if dm < 1e-15:  # a half circle: the middle of the arc is beside the chord
            mx, my = -uy, ux
            dm = 1.0
        out.append((cx + r * mx / dm, cy + r * my / dm))
    return out


def _newton(f, f_prime, x_min, x_max):
    x = (x_min + x_max) / 2.0
    for _ in range(12):
        f_x = f(x)
        if abs(f_x) < 1e-9:
            return x
        x = x - f_x / f_prime(x)
    raise GearError("The root fillet cannot meet the tooth flank. Change the Root Fillet Radius.")


def _cheby_expn(j, func):
    n = 50
    c = 0.0
    for k in range(1, n + 1):
        c += func(math.cos(math.pi * (k - 0.5) / n)) * math.cos(math.pi * j * (k - 0.5) / n)
    return 2.0 * c / n


def _cheby_poly(p, func):
    coeffs = [0.0] * (p + 1)
    t = [[0.0] * (p + 1) for _ in range(p + 1)]
    t[0][0] = 1.0
    t[1][1] = 1.0
    for k in range(1, p):
        for j in range(len(t[k]) - 1):
            t[k + 1][j + 1] = 2 * t[k][j]
        for j in range(len(t[k - 1])):
            t[k + 1][j] -= t[k - 1][j]
    fn = [_cheby_expn(k, func) for k in range(p + 1)]
    for k in range(p + 1):
        for pwr in range(p + 1):
            coeffs[pwr] += fn[k] * t[k][pwr]
    coeffs[0] -= fn[0] / 2.0
    return coeffs


def _bez_coeffs(rb, ra, order, fstart, fstop):
    """Bezier poles approximating the involute from fraction fstart to fstop of its
    length up to radius ra (fcgear.BezCoeffs)."""
    ta = math.sqrt(ra * ra - rb * rb) / rb
    te = math.sqrt(fstop) * ta
    ts = math.sqrt(fstart) * ta

    def theta(t):
        return (t * 2 - 1) * (te - ts) / 2 + (ts + te) / 2

    def fx(t):
        th = theta(t)
        return rb * (math.cos(th) + th * math.sin(th))

    def fy(t):
        th = theta(t)
        return rb * (math.sin(th) - th * math.cos(th))

    px, py = _cheby_poly(order, fx), _cheby_poly(order, fy)
    out = []
    for i in range(order + 1):
        bx = sum(math.comb(i, j) * px[j] / math.comb(order, j) for j in range(i + 1))
        by = sum(math.comb(i, j) * py[j] / math.comb(order, j) for j in range(i + 1))
        out.append((bx, by))
    return out


def _involute(
    w,
    module,
    z,
    alpha,
    rotation=0.0,
    outer_height=1.0,
    inner_height=1.0,
    outer_fillet=0.0,
    inner_fillet=0.0,
    thinning=0.0,
):
    """fcgear's _create_involute_profile (split involutes, no profile shift) with
    `thinning`: the tooth's half thickness angle at the reference circle is that much
    smaller (the backlash). Returns the widths (mm) of the outer and inner lands (the flat
    of each circle left between the flanks or fillets; < 0: the flanks cross)."""
    r_ref = z * module / 2.0
    rb = r_ref * math.cos(alpha)
    ro = r_ref + outer_height * module
    ri = r_ref - inner_height * module
    if ri <= 1e-9:
        raise GearError("Too few teeth for this tooth depth. Use more teeth.")
    fi = inner_fillet * module
    rci = ri + fi
    rfi = rci
    fo = outer_fillet * module
    rco = ro - fo
    rfo = ro
    non_involute = rfi < rb
    has_inner = fi > 0
    has_outer = fo > 0
    try:
        if has_inner and not non_involute:

            def q(r):
                return math.sqrt(r * r - rb * rb) / rb - math.asin(
                    (-(r * r) + fi * fi + rci * rci) / (2 * fi * rci)
                )

            def q_prime(r):
                return r / (math.sqrt(-(rb * rb) + r * r) * rb) + r / (
                    fi
                    * rci
                    * math.sqrt(
                        1 - 0.25 * (r * r - fi * fi - rci * rci) ** 2 / (fi * fi * rci * rci)
                    )
                )

            rfi = _newton(q, q_prime, max(rb, ri), rci)
        if has_outer:
            corr = _inv(rb, ro) + math.atan(fo / ro)

            def q(r):  # noqa: F811
                return (
                    math.sqrt(r * r - rb * rb) / rb
                    - math.asin((r * r - fo * fo - rco * rco) / (2 * fo * rco))
                    - corr
                )

            def q_prime(r):  # noqa: F811
                return r / (math.sqrt(-(rb * rb) + r * r) * rb) - r / (
                    fo
                    * rco
                    * math.sqrt(
                        1 - 0.25 * (r * r - fo * fo - rco * rco) ** 2 / (fo * fo * rco * rco)
                    )
                )

            rfo = _newton(q, q_prime, max(rb, rco), ro)
    except (ValueError, ZeroDivisionError):
        raise GearError(
            "The root fillet cannot meet the tooth flank. Make the Root Fillet Radius smaller."
        )

    pitch = 2 * math.pi / z
    base_to_ref = _inv(rb, r_ref)
    ref_to_stop = _inv(rb, rfo) - base_to_ref
    if non_involute:
        start_to_ref = base_to_ref
    else:
        start_to_ref = base_to_ref - _inv(rb, rfi)
    if fi * fi - (rci - rfi) ** 2 < -1e-12 or fo * fo - (rfo - rco) ** 2 < -1e-12:
        raise GearError("The root fillet cannot meet the tooth flank. Change it.")
    inner_w = math.sqrt(max(0.0, fi * fi - (rci - rfi) ** 2))
    inner_a = math.atan(inner_w / rfi)
    outer_w = math.sqrt(max(0.0, fo * fo - (rfo - rco) ** 2))
    outer_a = math.atan(outer_w / rfo)

    fe = 1.0
    fs = 0.01
    if not non_involute:
        fs = (rfi * rfi - rb * rb) / (rfo * rfo - rb * rb)
    fm = fs + (fe - fs) / 4
    part1 = _bez_coeffs(rb, rfo, 3, fs, fm)
    part2 = _bez_coeffs(rb, rfo, 3, fm, fe)
    inv = part1 + part2[1:]

    psi = pitch / 4 - thinning
    inv = [_rotate(pt, -base_to_ref - psi) for pt in inv]
    inv_r = [_mirror(pt) for pt in inv]

    # The flat left on the outer circle (between the flanks or their fillets) and on the
    # inner one, as widths: below 0 the flanks cross and no outline can close.
    outer_land = 2.0 * ro * (psi - ref_to_stop - outer_a)
    inner_land = ri * (pitch - 2 * (psi + start_to_ref + inner_a))
    if min(outer_land, inner_land) < 1e-4 * module:
        return outer_land, inner_land  # the caller says why

    inner_fillet_pt = _polar(rfi, -psi - start_to_ref)
    inner_fillet_back = _mirror(inner_fillet_pt)
    inner_circle_back = _polar(ri, psi + start_to_ref + inner_a)
    inner_circle_next = _polar(ri, pitch - psi - start_to_ref - inner_a)
    inner_fillet_next = _rotate(inner_fillet_pt, pitch)
    outer_fillet_pt = _polar(ro, -psi + ref_to_stop + outer_a)
    outer_circle = _mirror(outer_fillet_pt)

    thetas = [k * pitch + rotation for k in range(z)]
    if has_inner:
        w.move(_rotate(inner_fillet_next, thetas[-1]))
    else:
        w.move(_rotate(inner_circle_next, thetas[-1]))
    for theta in thetas:
        w.theta = theta
        if non_involute:
            w.line(inv[0])
        w.curve(inv[1], inv[2], inv[3])
        w.curve(inv[4], inv[5], inv[6])
        if has_outer:
            w.arc(outer_fillet_pt, fo, 1)
        w.arc(outer_circle, ro, 1)
        if has_outer:
            w.arc(inv_r[-1], fo, 1)
        w.curve(inv_r[5], inv_r[4], inv_r[3])
        w.curve(inv_r[2], inv_r[1], inv_r[0])
        if non_involute:
            w.line(inner_fillet_back)
        if has_inner:
            w.arc(inner_circle_back, fi, 0)
        w.arc(inner_circle_next, ri, 1)
        if has_inner:
            w.arc(inner_fillet_next, fi, 0)
    return outer_land, inner_land


# -- the rack -------------------------------------------------------------------------------------
def _rack_numbers(o):
    m = module_of(o)
    alpha = math.radians(float(o["pressure_angle"]))
    p = math.pi * m
    s = p / 2.0 - float(o["backlash"])  # tooth thickness on the pitch line
    return m, alpha, p, s, ADDENDUM * m, DEDENDUM * m


def _rack_corner(o):
    """(tangent length along each side, interior angle) of a root corner's fillet."""
    _m, alpha, _p, _s, _ha, _hf = _rack_numbers(o)
    theta = math.pi / 2.0 + alpha  # the space's corner between the flank and the root
    r = float(o["fillet"])
    return r / math.tan(theta / 2.0), theta


def _rack_max_fillet(o):
    m, alpha, p, s, ha, hf = _rack_numbers(o)
    root_space = p - (s + 2.0 * hf * math.tan(alpha))
    theta = math.pi / 2.0 + alpha
    flank = (ha + hf) / math.cos(alpha)
    best = min(root_space / 2.0, flank) * math.tan(theta / 2.0)
    return math.floor(max(best, 0.0) * 1000.0) / 1000.0


def _rack_tooth(c, o):
    """The top outline of one tooth centred at x = c, from the root corner on its left to
    the root corner on its right, with the root fillets: [segments], (start), (end)."""
    m, alpha, p, s, ha, hf = _rack_numbers(o)
    t = math.tan(alpha)
    left_root = (c - (s / 2.0 + hf * t), -hf)
    left_tip = (c - (s / 2.0 - ha * t), ha)
    right_tip = (c + (s / 2.0 - ha * t), ha)
    right_root = (c + (s / 2.0 + hf * t), -hf)
    r = float(o["fillet"])
    segs = []
    if r > 1e-9:
        tl, theta = _rack_corner(o)
        up_left = (math.sin(alpha), math.cos(alpha))  # from the left root corner up the flank
        up_right = (-math.sin(alpha), math.cos(alpha))
        a = _fillet(left_root, (-1.0, 0.0), up_left, r, tl, theta)
        b = _fillet(right_root, up_right, (1.0, 0.0), r, tl, theta)
        start, end = a[1], b[3]
        segs.append(a)
        segs.append(("line", a[3], left_tip))
        segs.append(("line", left_tip, right_tip))
        segs.append(("line", right_tip, b[1]))
        segs.append(b)
    else:
        start, end = left_root, right_root
        segs += [
            ("line", left_root, left_tip),
            ("line", left_tip, right_tip),
            ("line", right_tip, right_root),
        ]
    return segs, start, end


def _fillet(corner, d_in, d_out, r, tl, theta):
    """The arc rounding `corner` between the side along d_in (pointing away from the
    corner, where the outline comes from) and the side along d_out (where it goes)."""
    a = (corner[0] + d_in[0] * tl, corner[1] + d_in[1] * tl)
    b = (corner[0] + d_out[0] * tl, corner[1] + d_out[1] * tl)
    bx, by = d_in[0] + d_out[0], d_in[1] + d_out[1]
    n = math.hypot(bx, by)
    dist = r / math.sin(theta / 2.0)
    centre = (corner[0] + bx / n * dist, corner[1] + by / n * dist)
    mid = (centre[0] - bx / n * r, centre[1] - by / n * r)
    return ("arc", a, mid, b)


def _rack_top(o, centres):
    """The rack's top outline over the teeth centred at `centres` (ascending), from the
    first tooth's left root corner to the last tooth's right root corner."""
    segs = []
    previous = None
    for c in centres:
        tooth, start, end = _rack_tooth(c, o)
        if previous is not None:
            segs.append(("line", previous, start))
        segs += tooth
        previous = end
    return segs


def _rack_check(o):
    m, alpha, p, s, ha, hf = _rack_numbers(o)
    t = math.tan(alpha)
    if s - 2.0 * ha * t < 1e-4 * m:
        if float(o["backlash"]) > 1e-9:
            raise GearError(
                "With this Backlash (%s mm) the rack's teeth come to a point. Make the "
                "backlash smaller." % _fmt(float(o["backlash"]))
            )
        raise GearError("The rack's teeth come to a point. Use another pressure angle.")
    if float(o["fillet"]) > _rack_max_fillet(o) + 1e-9:
        raise GearError(
            "The Root Fillet Radius (%s mm) does not fit between the rack's teeth. Make it "
            "at most %s mm." % (_fmt(float(o["fillet"])), _fmt(_rack_max_fillet(o)))
        )


def _rack_loop(o):
    """The rack's closed outline: the pitch line on y = 0 (centred on x = 0), teeth up."""
    _rack_check(o)
    m, alpha, p, s, ha, hf = _rack_numbers(o)
    bottom = -hf - float(o["rack_height"])
    if o["rack_size"] == "length":
        length = float(o["rack_length"])
        half = length / 2.0
        count = int(math.ceil(half / p)) + 1
        centres = [k * p for k in range(-count, count + 1)]
        top = _clip(_rack_top(o, centres), -half, half)
    else:
        z = teeth_of(o)
        half = z * p / 2.0
        centres = [-half + p / 2.0 + k * p for k in range(z)]
        top = _rack_top(o, centres)
        first, last = _start(top[0]), _end(top[-1])
        top = [("line", (-half, -hf), first)] + top + [("line", last, (half, -hf))]
        top = [seg for seg in top if _length(seg) > 1e-12]
    first, last = _start(top[0]), _end(top[-1])
    loop = [("line", (-half, bottom), first)] + top
    loop += [("line", last, (half, bottom)), ("line", (half, bottom), (-half, bottom))]
    return [seg for seg in loop if _length(seg) > 1e-12]


def _clip(segs, x0, x1):
    """The part of an x-monotone outline between x = x0 and x = x1 (arcs are root fillets:
    their points lie below their centres)."""
    out = []
    for seg in segs:
        a, b = _start(seg), _end(seg)
        if b[0] <= x0 + 1e-12 or a[0] >= x1 - 1e-12:
            continue
        if seg[0] == "line":
            pa = a if a[0] >= x0 else _line_at(a, b, x0)
            pb = b if b[0] <= x1 else _line_at(a, b, x1)
            out.append(("line", pa, pb))
        else:
            centre, r = _circle_of(a, seg[2], b)
            pa = a if a[0] >= x0 else _arc_at(centre, r, x0)
            pb = b if b[0] <= x1 else _arc_at(centre, r, x1)
            out.append(("arc", pa, _arc_mid(centre, r, pa, pb), pb))
    return [seg for seg in out if _length(seg) > 1e-12]


def _line_at(a, b, x):
    k = (x - a[0]) / (b[0] - a[0])
    return (x, a[1] + k * (b[1] - a[1]))


def _arc_at(centre, r, x):
    dx = x - centre[0]
    return (x, centre[1] - math.sqrt(max(0.0, r * r - dx * dx)))


def _arc_mid(centre, r, a, b):
    a0 = math.atan2(a[1] - centre[1], a[0] - centre[0])
    a1 = math.atan2(b[1] - centre[1], b[0] - centre[0])
    mid = (a0 + a1) / 2.0  # both below the centre: no wrap between -pi and 0
    return (centre[0] + r * math.cos(mid), centre[1] + r * math.sin(mid))


# -- geometry helpers -----------------------------------------------------------------------------
def _start(seg):
    if seg[0] == "bezier":
        return seg[1][0]
    return seg[1]


def _end(seg):
    if seg[0] == "bezier":
        return seg[1][-1]
    if seg[0] == "arc":
        return seg[3]
    return seg[2]


def _length(seg):
    if seg[0] == "circle":
        return 2 * math.pi * seg[2]
    a, b = _start(seg), _end(seg)
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _circle_of(a, m, b):
    """Centre and radius of the circle through three points."""
    ax, ay = a
    bx, by = m
    cx, cy = b
    d = 2.0 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-18:
        raise GearError("A tooth outline degenerated. Change the values.")
    ux = (
        (ax * ax + ay * ay) * (by - cy)
        + (bx * bx + by * by) * (cy - ay)
        + (cx * cx + cy * cy) * (ay - by)
    ) / d
    uy = (
        (ax * ax + ay * ay) * (cx - bx)
        + (bx * bx + by * by) * (ax - cx)
        + (cx * cx + cy * cy) * (bx - ax)
    ) / d
    return (ux, uy), math.hypot(ax - ux, ay - uy)


def _arc_span(seg):
    """(centre, radius, start angle, signed sweep) of an arc through its middle point."""
    a, m, b = seg[1], seg[2], seg[3]
    centre, r = _circle_of(a, m, b)
    t0 = math.atan2(a[1] - centre[1], a[0] - centre[0])
    tm = math.atan2(m[1] - centre[1], m[0] - centre[0])
    t1 = math.atan2(b[1] - centre[1], b[0] - centre[0])
    ccw = (t1 - t0) % (2 * math.pi)
    if (tm - t0) % (2 * math.pi) <= ccw:
        return centre, r, t0, ccw
    return centre, r, t0, -((t0 - t1) % (2 * math.pi))


def _bezier_point(poles, t):
    pts = list(poles)
    while len(pts) > 1:
        pts = [((1 - t) * p[0] + t * q[0], (1 - t) * p[1] + t * q[1]) for p, q in zip(pts, pts[1:])]
    return pts[0]


def _bezier_derivative(poles, t):
    n = len(poles) - 1
    diffs = [(n * (q[0] - p[0]), n * (q[1] - p[1])) for p, q in zip(poles, poles[1:])]
    return _bezier_point(diffs, t) if len(diffs) > 1 else diffs[0]


# 8-point Gauss-Legendre on [0, 1]: exact for the polynomials of a cubic's x dy.
_GAUSS = [
    (0.0198550717512319, 0.0506142681451881),
    (0.1016667612931866, 0.1111905172266872),
    (0.2372337950418355, 0.1568533229389436),
    (0.4082826787521751, 0.1813418916891810),
    (0.5917173212478249, 0.1813418916891810),
    (0.7627662049581645, 0.1568533229389436),
    (0.8983332387068134, 0.1111905172266872),
    (0.9801449282487681, 0.0506142681451881),
]


def _x_dy(seg):
    """The integral of x dy along the segment (Green: the loop's signed area)."""
    kind = seg[0]
    if kind == "line":
        (x0, y0), (x1, y1) = seg[1], seg[2]
        return (x0 + x1) / 2.0 * (y1 - y0)
    if kind == "arc":
        (cx, _cy), r, t0, sweep = _arc_span(seg)
        t1 = t0 + sweep
        return cx * r * (math.sin(t1) - math.sin(t0)) + r * r / 2.0 * (
            sweep + (math.sin(2 * t1) - math.sin(2 * t0)) / 2.0
        )
    if kind == "circle":
        return math.pi * seg[2] ** 2
    poles = seg[1]
    total = 0.0
    for t, weight in _GAUSS:
        x = _bezier_point(poles, t)[0]
        dy = _bezier_derivative(poles, t)[1]
        total += weight * x * dy
    return total


def loop_area(loop):
    """The signed area of a closed loop (counterclockwise: positive)."""
    return sum(_x_dy(seg) for seg in loop)


def area(options):
    """The gear's face area (mm^2): the outer loop less the holes (Green's theorem on the
    exact outline: lines, arcs and the Bezier involutes)."""
    loops = profile(options)
    areas = [abs(loop_area(loop)) for loop in loops]
    biggest = max(areas)
    return biggest - (sum(areas) - biggest)


def rack_area(options):
    """A rack's area worked out by hand (unit tests compare it with area()): the base
    strip, each whole tooth's trapezoid above the root line, and each root fillet (the
    fillet fills the corner: r t - r^2 phi / 2, phi = 90 deg - alpha). Teeth mode only."""
    o = with_defaults(options)
    m, alpha, p, s, ha, hf = _rack_numbers(o)
    z = teeth_of(o)
    strip = z * p * float(o["rack_height"])  # under the root line
    tooth = s * (ha + hf) - math.tan(alpha) * (ha * ha - hf * hf)
    r = float(o["fillet"])
    corner = 0.0
    if r > 1e-9:
        tl, theta = _rack_corner(o)
        phi = math.pi - theta
        corner = r * tl - r * r * phi / 2.0
    return strip + z * tooth + 2 * z * corner


def bbox(options):
    """(xmin, ymin, xmax, ymax) of the outline (loops sampled finely)."""
    xs, ys = [], []
    for line in polylines(options, fine=True):
        for x, y in line:
            xs.append(x)
            ys.append(y)
    return (min(xs), min(ys), max(xs), max(ys))


def polylines(options, fine=False):
    """The outline as polylines (for the preview drawn while placing and for checks)."""
    return [loop_points(loop, fine) for loop in profile(options)]


def loop_points(loop, fine=False):
    out = []
    n_curve = 12 if fine else 4
    for seg in loop:
        kind = seg[0]
        if kind == "circle":
            (cx, cy), r = seg[1], seg[2]
            steps = 360 if fine else 96
            return [
                (
                    cx + r * math.cos(2 * math.pi * i / steps),
                    cy + r * math.sin(2 * math.pi * i / steps),
                )
                for i in range(steps + 1)
            ]
        if kind == "line":
            pts = [seg[1], seg[2]]
        elif kind == "arc":
            (cx, cy), r, t0, sweep = _arc_span(seg)
            n = max(2, int(abs(sweep) / (math.pi / (90 if fine else 18))) + 1)
            pts = [
                (cx + r * math.cos(t0 + sweep * i / n), cy + r * math.sin(t0 + sweep * i / n))
                for i in range(n + 1)
            ]
        else:
            pts = [_bezier_point(seg[1], i / float(n_curve)) for i in range(n_curve + 1)]
        if out:
            pts = pts[1:]
        out.extend(pts)
    return out


def edge_count(options):
    return sum(len(loop) for loop in profile(options))


def nice_thickness(options):
    """A first thickness that looks like a gear: about a third of the pitch diameter,
    rounded (Fusion's sample starts thin too)."""
    s = sizes(options)
    if options.get("type") == "rack":
        size = s["rack_depth"] * 2.0
    else:
        size = s["pitch_diameter"] / 4.0
    return nice(max(size, 1.0))
