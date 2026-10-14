# SPDX-License-Identifier: LGPL-2.1-or-later
"""ISO 286 limits and fits for drawing dimensions (Fusion's Tolerance > Fit). Pure Python
(no FreeCAD, no Qt), unit tested (SciForgeTests/unit/test_drawing_fits.py).

A tolerance class is a letter (the fundamental deviation: where the zone lies) and a
number (the IT grade: how wide it is): H7 for a hole, g6 for a shaft. A fit is a hole
class over a shaft class (H7/g6). Values are the standard's tables (ISO 286-1:2010 and
ISO 286-2) for nominal sizes up to 500 mm, in micrometres in the tables and millimetres
from the functions. Fundamental deviations of holes follow from those of shafts by the
standard's rules (the general rule and the "delta" rule for K, M, N up to IT8 and P to U
up to IT7), so only shaft letters are tabled.

Letters covered: shafts c d e f g h js k m n p r s t u, holes C D E F G H JS K M N P R S
T U; grades IT1 to IT16. Fusion's Fit lists the preferred fits by basis (hole or shaft)
and type (clearance, transition, interference), or a custom pair.
"""

import re

MAX_SIZE = 500.0

# Main size steps (over the first, up to and including the second), ISO 286-1 table 1.
STEPS = (0.0, 3.0, 6.0, 10.0, 18.0, 30.0, 50.0, 80.0, 120.0, 180.0, 250.0, 315.0, 400.0, 500.0)

# Standard tolerance grades IT1..IT16 in micrometres, one value per main step.
IT = {
    1: (0.8, 1, 1, 1.2, 1.5, 1.5, 2, 2.5, 3.5, 4.5, 6, 7, 8),
    2: (1.2, 1.5, 1.5, 2, 2.5, 2.5, 3, 4, 5, 7, 8, 9, 10),
    3: (2, 2.5, 2.5, 3, 4, 4, 5, 6, 8, 10, 12, 13, 15),
    4: (3, 4, 4, 5, 6, 7, 8, 10, 12, 14, 16, 18, 20),
    5: (4, 5, 6, 8, 9, 11, 13, 15, 18, 20, 23, 25, 27),
    6: (6, 8, 9, 11, 13, 16, 19, 22, 25, 29, 32, 36, 40),
    7: (10, 12, 15, 18, 21, 25, 30, 35, 40, 46, 52, 57, 63),
    8: (14, 18, 22, 27, 33, 39, 46, 54, 63, 72, 81, 89, 97),
    9: (25, 30, 36, 43, 52, 62, 74, 87, 100, 115, 130, 140, 155),
    10: (40, 48, 58, 70, 84, 100, 120, 140, 160, 185, 210, 230, 250),
    11: (60, 75, 90, 110, 130, 160, 190, 220, 250, 290, 320, 360, 400),
    12: (100, 120, 150, 180, 210, 250, 300, 350, 400, 460, 520, 570, 630),
    13: (140, 180, 220, 270, 330, 390, 460, 540, 630, 720, 810, 890, 970),
    14: (250, 300, 360, 430, 520, 620, 740, 870, 1000, 1150, 1300, 1400, 1550),
    15: (400, 480, 580, 700, 840, 1000, 1200, 1400, 1600, 1850, 2100, 2300, 2500),
    16: (600, 750, 900, 1100, 1300, 1600, 1900, 2200, 2500, 2900, 3200, 3600, 4000),
}
GRADES = tuple(sorted(IT))

# Intermediate steps used by the letters whose deviations change inside a main step.
FINE_STEPS = (
    0.0,
    3.0,
    6.0,
    10.0,
    14.0,
    18.0,
    24.0,
    30.0,
    40.0,
    50.0,
    65.0,
    80.0,
    100.0,
    120.0,
    140.0,
    160.0,
    180.0,
    200.0,
    225.0,
    250.0,
    280.0,
    315.0,
    355.0,
    400.0,
    450.0,
    500.0,
)

# Shaft fundamental deviations in micrometres. a-h: the upper deviation es (<= 0);
# k-u: the lower deviation ei (>= 0). One value per main step, or per fine step ("fine").
SHAFT_UPPER = {
    "d": (-20, -30, -40, -50, -65, -80, -100, -120, -145, -170, -190, -210, -230),
    "e": (-14, -20, -25, -32, -40, -50, -60, -72, -85, -100, -110, -125, -135),
    "f": (-6, -10, -13, -16, -20, -25, -30, -36, -43, -50, -56, -62, -68),
    "g": (-2, -4, -5, -6, -7, -9, -10, -12, -14, -15, -17, -18, -20),
    "h": (0,) * 13,
}
SHAFT_UPPER_FINE = {
    "c": (
        -60,
        -70,
        -80,
        -95,
        -95,
        -110,
        -110,
        -120,
        -130,
        -140,
        -150,
        -170,
        -180,
        -200,
        -210,
        -230,
        -240,
        -260,
        -280,
        -300,
        -330,
        -360,
        -400,
        -440,
        -480,
    ),
}
SHAFT_LOWER = {
    "m": (2, 4, 6, 7, 8, 9, 11, 13, 15, 17, 20, 21, 23),
    "n": (4, 8, 10, 12, 15, 17, 20, 23, 27, 31, 34, 37, 40),
    "p": (6, 12, 15, 18, 22, 26, 32, 37, 43, 50, 56, 62, 68),
}
# k for the grades IT4 to IT7 (0 for the others)
SHAFT_K = (0, 1, 1, 1, 2, 2, 2, 3, 3, 4, 4, 4, 5)
SHAFT_LOWER_FINE = {
    "r": (
        10,
        15,
        19,
        23,
        23,
        28,
        28,
        34,
        34,
        41,
        43,
        51,
        54,
        63,
        65,
        68,
        77,
        80,
        84,
        94,
        98,
        108,
        114,
        126,
        132,
    ),
    "s": (
        14,
        19,
        23,
        28,
        28,
        35,
        35,
        43,
        43,
        53,
        59,
        71,
        79,
        92,
        100,
        108,
        122,
        130,
        140,
        158,
        170,
        190,
        208,
        232,
        252,
    ),
    # (t starts above 24 mm)
    "t": (
        None,
        None,
        None,
        None,
        None,
        None,
        41,
        48,
        54,
        66,
        75,
        91,
        104,
        122,
        134,
        146,
        166,
        180,
        196,
        218,
        240,
        268,
        294,
        330,
        360,
    ),
    "u": (
        18,
        23,
        28,
        33,
        33,
        41,
        48,
        60,
        70,
        87,
        102,
        124,
        144,
        170,
        190,
        210,
        236,
        258,
        284,
        315,
        350,
        390,
        435,
        490,
        540,
    ),
}
SHAFT_LETTERS = ("c", "d", "e", "f", "g", "h", "js", "k", "m", "n", "p", "r", "s", "t", "u")
HOLE_LETTERS = tuple(letter.upper() for letter in SHAFT_LETTERS)

# Fusion's Fit lists the preferred ISO fits by basis and type (ISO 286-2 / ISO 1829).
PREFERRED_FITS = (
    ("H11/c11", "Hole", "Clearance", "Loose running"),
    ("H9/d9", "Hole", "Clearance", "Free running"),
    ("H8/f7", "Hole", "Clearance", "Close running"),
    ("H7/g6", "Hole", "Clearance", "Sliding"),
    ("H7/h6", "Hole", "Clearance", "Locational clearance"),
    ("H7/k6", "Hole", "Transition", "Locational transition"),
    ("H7/n6", "Hole", "Transition", "Locational transition (tighter)"),
    ("H7/p6", "Hole", "Interference", "Locational interference"),
    ("H7/s6", "Hole", "Interference", "Medium drive"),
    ("H7/u6", "Hole", "Interference", "Force"),
    ("C11/h11", "Shaft", "Clearance", "Loose running"),
    ("D9/h9", "Shaft", "Clearance", "Free running"),
    ("F8/h7", "Shaft", "Clearance", "Close running"),
    ("G7/h6", "Shaft", "Clearance", "Sliding"),
    ("H7/h6", "Shaft", "Clearance", "Locational clearance"),
    ("K7/h6", "Shaft", "Transition", "Locational transition"),
    ("N7/h6", "Shaft", "Transition", "Locational transition (tighter)"),
    ("P7/h6", "Shaft", "Interference", "Locational interference"),
    ("S7/h6", "Shaft", "Interference", "Medium drive"),
    ("U7/h6", "Shaft", "Interference", "Force"),
)
BASES = ("Hole", "Shaft")
FIT_TYPES = ("Clearance", "Transition", "Interference")


class FitError(ValueError):
    """A class or size the tables do not cover, with a sentence that says why."""


# ------------------------------------------------------------------ table lookup
def _step(size, steps):
    """Index of the step a nominal size falls in (over steps[i], up to steps[i + 1])."""
    if size is None or not (0.0 < size <= MAX_SIZE):
        raise FitError(
            "ISO fits are tabled for sizes from 0 to %d mm: this size is %s."
            % (MAX_SIZE, _mm(size))
        )
    for i in range(len(steps) - 1):
        if steps[i] < size <= steps[i + 1] + 1e-9:
            return i
    return len(steps) - 2


def _mm(size):
    try:
        return "%g mm" % size
    except TypeError:
        return "unknown"


def it_value(grade, size):
    """The standard tolerance ITn of a nominal size, in mm."""
    if grade not in IT:
        raise FitError("IT%s is not a grade SciForge knows (IT1 to IT16)." % grade)
    return IT[grade][_step(size, STEPS)] / 1000.0


def _shaft_fundamental(letter, grade, size):
    """(which, value in mm): the shaft letter's fundamental deviation, which = "es"
    (upper, letters a-h) or "ei" (lower, j-zc)."""
    if letter in SHAFT_UPPER:
        return "es", SHAFT_UPPER[letter][_step(size, STEPS)] / 1000.0
    if letter in SHAFT_UPPER_FINE:
        return "es", SHAFT_UPPER_FINE[letter][_step(size, FINE_STEPS)] / 1000.0
    if letter == "k":
        i = _step(size, STEPS)
        value = SHAFT_K[i] if 4 <= grade <= 7 else 0
        return "ei", value / 1000.0
    if letter in SHAFT_LOWER:
        return "ei", SHAFT_LOWER[letter][_step(size, STEPS)] / 1000.0
    if letter in SHAFT_LOWER_FINE:
        value = SHAFT_LOWER_FINE[letter][_step(size, FINE_STEPS)]
        if value is None:
            raise FitError(
                "The %s deviation starts above 24 mm (ISO 286): this size is %s."
                % (letter, _mm(size))
            )
        return "ei", value / 1000.0
    raise FitError("%s is not a shaft letter SciForge knows." % letter)


# ------------------------------------------------------------------ classes
_CLASS = re.compile(r"^\s*([A-Za-z]{1,2})\s*(\d{1,2})\s*$")


def parse_class(text):
    """'H7' -> ('H', 7), 'js6' -> ('js', 6). Raises FitError for anything else."""
    match = _CLASS.match(str(text or ""))
    if not match:
        raise FitError("Type a tolerance class like H7 (hole) or g6 (shaft).")
    letter, grade = match.group(1), int(match.group(2))
    if letter.lower() == "js":
        letter = "JS" if letter[0].isupper() else "js"
    if letter not in SHAFT_LETTERS and letter not in HOLE_LETTERS:
        raise FitError(
            "%s is not a tolerance letter SciForge knows (holes %s, shafts %s)."
            % (letter, " ".join(HOLE_LETTERS), " ".join(SHAFT_LETTERS))
        )
    if grade not in IT:
        raise FitError("IT%d is not a grade SciForge knows (1 to 16)." % grade)
    return letter, grade


def is_hole_class(text):
    letter, _grade = parse_class(text)
    return letter[0].isupper()


def shaft_deviations(letter, grade, size):
    """(es, ei) of a shaft class, mm."""
    tol = it_value(grade, size)
    if letter == "js":
        return tol / 2.0, -tol / 2.0
    which, value = _shaft_fundamental(letter, grade, size)
    if which == "es":
        return value, value - tol
    return value + tol, value


def _delta(grade, size):
    """ISO 286's delta: ITn - IT(n-1) (0 for sizes up to 3 mm)."""
    if size <= 3.0 or grade <= 1:
        return 0.0
    return it_value(grade, size) - it_value(grade - 1, size)


def hole_deviations(letter, grade, size):
    """(ES, EI) of a hole class, mm (ISO 286-1: from the shaft of the same letter)."""
    tol = it_value(grade, size)
    lower = letter.lower()
    if lower == "js":
        return tol / 2.0, -tol / 2.0
    if lower in ("c", "d", "e", "f", "g", "h"):
        _which, es = _shaft_fundamental(lower, grade, size)
        ei_hole = -es  # EI = -es
        return ei_hole + tol, ei_hole
    if lower == "k":
        if grade <= 8 and size > 3.0:
            ei_shaft = SHAFT_K[_step(size, STEPS)] / 1000.0  # (the IT4-IT7 value)
            es_hole = -ei_shaft + _delta(grade, size)
        else:
            es_hole = 0.0
        return es_hole, es_hole - tol
    if lower == "m":
        _which, ei = _shaft_fundamental("m", grade, size)
        if grade <= 8 and size > 3.0:
            es_hole = -ei + _delta(grade, size)
        else:
            es_hole = -ei
        return es_hole, es_hole - tol
    if lower == "n":
        _which, ei = _shaft_fundamental("n", grade, size)
        if size <= 3.0:
            es_hole = -ei
        elif grade <= 8:
            es_hole = -ei + _delta(grade, size)
        else:
            es_hole = 0.0
        return es_hole, es_hole - tol
    _which, ei = _shaft_fundamental(lower, grade, size)
    es_hole = -ei + (_delta(grade, size) if grade <= 7 else 0.0)
    return es_hole, es_hole - tol


def deviations(cls, size):
    """(upper, lower) deviation of a class ('H7', 'g6') at a nominal size, mm, rounded to
    the micrometre."""
    letter, grade = parse_class(cls)
    if letter[0].isupper():
        upper, lower = hole_deviations(letter, grade, size)
    else:
        upper, lower = shaft_deviations(letter, grade, size)
    return round(upper, 4), round(lower, 4)


def limits(cls, size):
    """(largest, smallest) size of a class at a nominal size, mm."""
    upper, lower = deviations(cls, size)
    return round(size + upper, 4), round(size + lower, 4)


# ------------------------------------------------------------------ fits
def parse_fit(text):
    """'H7/g6' -> ('H7', 'g6')."""
    parts = [p.strip() for p in str(text or "").split("/")]
    if len(parts) != 2:
        raise FitError("Type a fit like H7/g6 (hole class / shaft class).")
    hole, shaft = parts
    if not is_hole_class(hole):
        raise FitError("A fit starts with the hole's class (capital letter), like H7/g6.")
    if is_hole_class(shaft):
        raise FitError("A fit ends with the shaft's class (small letter), like H7/g6.")
    return hole, shaft


def fit_type(hole, shaft, size):
    """Clearance (the hole is always larger), Interference (always smaller) or
    Transition."""
    hole_max, hole_min = limits(hole, size)
    shaft_max, shaft_min = limits(shaft, size)
    if hole_min >= shaft_max - 1e-9:
        return "Clearance"
    if hole_max <= shaft_min + 1e-9:
        return "Interference"
    return "Transition"


def preferred_fits(basis=None, kind=None):
    """Fit names of the preferred list, filtered by basis and type."""
    return [
        name
        for name, b, k, _use in PREFERRED_FITS
        if (basis is None or b == basis) and (kind is None or k == kind)
    ]


def fit_use(name):
    for fit, _b, _k, use in PREFERRED_FITS:
        if fit == name:
            return use
    return ""


def clearance(hole, shaft, size):
    """(largest, smallest) clearance of a fit, mm (negative = interference)."""
    hole_max, hole_min = limits(hole, size)
    shaft_max, shaft_min = limits(shaft, size)
    return round(hole_max - shaft_min, 4), round(hole_min - shaft_max, 4)
