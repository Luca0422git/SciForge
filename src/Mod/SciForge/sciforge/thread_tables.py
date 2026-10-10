# SPDX-License-Identifier: LGPL-2.1-or-later
"""Standard thread sizes for Hole (Tapped / Clearance) and Thread. Pure Python (unit tested).

Fusion groups threads by standard, then size, then designation: "ISO Metric profile",
size 6, designation M6x1 (coarse) or M6x0.75 (fine); "ANSI Unified Screw Threads", size
1/4, designation 1/4-20 UNC, 1/4-28 UNF or 1/4-32 UNEF. FreeCAD's Hole keeps one list per
thread series instead (ISOMetricProfile, ISOMetricFineProfile, UNC, UNF, UNEF). This module
maps one onto the other.

The numbers (major diameter, pitch, tap drill, all in mm) are the standard values ISO 261 /
ISO 262 / ISO 2306 and ASME B1.1 give; they are the same rows FreeCAD's Hole uses
(src/Mod/PartDesign/App/FeatureHole.cpp), so a size picked here is one FreeCAD knows.
"""
import math

STANDARDS = (("iso", "ISO Metric profile"), ("ansi", "ANSI Unified Screw Threads"))
# FreeCAD thread series per standard, coarse first (Fusion lists the coarse pitch first).
SERIES = {"iso": ("ISOMetricProfile", "ISOMetricFineProfile"), "ansi": ("UNC", "UNF", "UNEF")}
SERIES_SUFFIX = {"UNC": "UNC", "UNF": "UNF", "UNEF": "UNEF"}
# Clearance hole fits: Fusion's names -> FreeCAD's ThreadFit per thread series.
FITS = (("close", "Close"), ("normal", "Normal"), ("loose", "Loose"))
FIT_ISO = {"close": "Fine", "normal": "Medium", "loose": "Coarse"}
FIT_UTS = {"close": "Close", "normal": "Normal", "loose": "Loose"}
# Tolerance classes (internal = nut / tapped hole, external = bolt / shaft).
CLASSES = {
    ("iso", True): ("4H", "5H", "6H", "7H", "8H", "4G", "5G", "6G", "7G", "8G"),
    ("iso", False): ("4g", "4h", "5g", "5h", "6e", "6f", "6g", "6h", "7e", "7g", "7h", "8g"),
    ("ansi", True): ("1B", "2B", "3B"),
    ("ansi", False): ("1A", "2A", "3A"),
}
DEFAULT_CLASS = {
    ("iso", True): "6H",
    ("iso", False): "6g",
    ("ansi", True): "2B",
    ("ansi", False): "2A",
}
# FreeCAD's Hole knows the internal classes of these series (ThreadClass enums).
FREECAD_CLASSES = {
    "ISOMetricProfile": ("4G", "4H", "5G", "5H", "6G", "6H", "7G", "7H", "8G", "8H"),
    "ISOMetricFineProfile": ("4G", "4H", "5G", "5H", "6G", "6H", "7G", "7H", "8G", "8H"),
    "UNC": ("1B", "2B", "3B"),
    "UNF": ("1B", "2B", "3B"),
    "UNEF": ("1B", "2B", "3B"),
}


class Designation:
    """One standard thread: label as Fusion shows it, FreeCAD's series and size name,
    major diameter, pitch and tap drill (mm)."""

    __slots__ = ("label", "standard", "size", "series", "freecad", "diameter", "pitch", "drill")

    def __init__(self, standard, size, series, freecad, diameter, pitch, drill):
        self.standard = standard
        self.size = size
        self.series = series
        self.freecad = freecad
        self.diameter = diameter
        self.pitch = pitch
        self.drill = drill
        self.label = _label(standard, size, series, pitch)

    def minor(self, internal=True):
        """Minor diameter of the basic profile (ISO 68-1): D1 = D - 2 * 5/8 * H for a nut,
        d3 = D - 2 * 17/24 * H for a bolt (H = sqrt(3)/2 * P)."""
        h = math.sqrt(3.0) / 2.0 * self.pitch
        return self.diameter - 2.0 * (5.0 / 8.0 if internal else 17.0 / 24.0) * h

    def __repr__(self):
        return "<Designation %s>" % self.label


def _trim(number):
    text = ("%.3f" % number).rstrip("0").rstrip(".")
    return text


def _label(standard, size, series, pitch):
    if standard == "iso":
        return "M%sx%s" % (size, _trim(pitch))
    tpi = int(round(25.4 / pitch))
    return "%s-%d %s" % (size, tpi, SERIES_SUFFIX[series])


def _iso_size(freecad):
    """'M6x1.0' -> '6'."""
    return freecad[1:].split("x")[0]


_ALL = None


def all_designations():
    global _ALL
    if _ALL is None:
        found = []
        for standard, series_list in SERIES.items():
            for series in series_list:
                for name, diameter, pitch, drill in TABLES[series]:
                    size = _iso_size(name) if standard == "iso" else name
                    found.append(Designation(standard, size, series, name, diameter, pitch, drill))
        _ALL = found
    return _ALL


def sizes(standard):
    """Size names of a standard, smallest first ('6', '8'... or '#10', '1/4'...)."""
    seen = {}
    for d in all_designations():
        if d.standard == standard and d.size not in seen:
            seen[d.size] = d.diameter
    return sorted(seen, key=lambda s: (seen[s], s))


def designations(standard, size):
    """The designations of one size, coarse pitch first."""
    found = [d for d in all_designations() if d.standard == standard and d.size == size]
    order = SERIES[standard]
    return sorted(found, key=lambda d: (order.index(d.series), -d.pitch))


def find(standard, label):
    """The designation with this label (e.g. 'M6x1', '1/4-20 UNC'), or None."""
    for d in all_designations():
        if d.standard == standard and d.label == label:
            return d
    return None


def from_freecad(series, name):
    """The designation of FreeCAD's (ThreadType, ThreadSize), or None."""
    for d in all_designations():
        if d.series == series and d.freecad == name:
            return d
    return None


def standard_of(series):
    for standard, series_list in SERIES.items():
        if series in series_list:
            return standard
    return None


def closest(standard, diameter, internal=False):
    """The designation a cylinder of this diameter takes (Fusion picks the size from the
    face): a shaft is threaded at its own diameter (the major diameter); a hole is drilled
    at the tap drill size, so a hole matches the size whose tap drill (or minor diameter)
    is nearest. Coarse pitch first among equals."""
    best = None
    for d in all_designations():
        if d.standard != standard:
            continue
        target = (d.drill or d.minor(True)) if internal else d.diameter
        gap = abs(target - diameter)
        rank = (round(gap, 6), SERIES[standard].index(d.series), -d.pitch)
        if best is None or rank < best[0]:
            best = (rank, d)
    return best[1] if best else None


def clearance_fit(series, fit):
    """FreeCAD's ThreadFit name for Fusion's Close / Normal / Loose."""
    table = FIT_ISO if series.startswith("ISO") else FIT_UTS
    return table.get(fit, table["normal"])


def fit_from_freecad(series, name):
    table = FIT_ISO if series.startswith("ISO") else FIT_UTS
    for fit, freecad in table.items():
        if freecad == name:
            return fit
    return "normal"


def classes(standard, internal):
    return CLASSES[(standard, bool(internal))]


def default_class(standard, internal):
    return DEFAULT_CLASS[(standard, bool(internal))]


def freecad_class(series, wanted):
    """The class FreeCAD's Hole can store for this series (its tapped holes know only the
    internal classes): the wanted one if it exists, else the series' standard one."""
    known = FREECAD_CLASSES.get(series, ())
    if wanted in known:
        return wanted
    return "6H" if series.startswith("ISO") else "2B"


# -- the tables (generated from FreeCAD 1.1.4's FeatureHole.cpp) --------------------------------
# (FreeCAD size name, major diameter, pitch, tap drill)
ISO_COARSE = (
    ("M1x0.25", 1.0, 0.25, 0.75),
    ("M1.1x0.25", 1.1, 0.25, 0.85),
    ("M1.2x0.25", 1.2, 0.25, 0.95),
    ("M1.4x0.3", 1.4, 0.3, 1.1),
    ("M1.6x0.35", 1.6, 0.35, 1.25),
    ("M1.8x0.35", 1.8, 0.35, 1.45),
    ("M2x0.4", 2.0, 0.4, 1.6),
    ("M2.2x0.45", 2.2, 0.45, 1.75),
    ("M2.5x0.45", 2.5, 0.45, 2.05),
    ("M3x0.5", 3.0, 0.5, 2.5),
    ("M3.5x0.6", 3.5, 0.6, 2.9),
    ("M4x0.7", 4.0, 0.7, 3.3),
    ("M4.5x0.75", 4.5, 0.75, 3.7),
    ("M5x0.8", 5.0, 0.8, 4.2),
    ("M6x1.0", 6.0, 1.0, 5.0),
    ("M7x1.0", 7.0, 1.0, 6.0),
    ("M8x1.25", 8.0, 1.25, 6.8),
    ("M9x1.25", 9.0, 1.25, 7.8),
    ("M10x1.5", 10.0, 1.5, 8.5),
    ("M11x1.5", 11.0, 1.5, 9.5),
    ("M12x1.75", 12.0, 1.75, 10.2),
    ("M14x2.0", 14.0, 2.0, 12.0),
    ("M16x2.0", 16.0, 2.0, 14.0),
    ("M18x2.5", 18.0, 2.5, 15.5),
    ("M20x2.5", 20.0, 2.5, 17.5),
    ("M22x2.5", 22.0, 2.5, 19.5),
    ("M24x3.0", 24.0, 3.0, 21.0),
    ("M27x3.0", 27.0, 3.0, 24.0),
    ("M30x3.5", 30.0, 3.5, 26.5),
    ("M33x3.5", 33.0, 3.5, 29.5),
    ("M36x4.0", 36.0, 4.0, 32.0),
    ("M39x4.0", 39.0, 4.0, 35.0),
    ("M42x4.5", 42.0, 4.5, 37.5),
    ("M45x4.5", 45.0, 4.5, 40.5),
    ("M48x5.0", 48.0, 5.0, 43.0),
    ("M52x5.0", 52.0, 5.0, 47.0),
    ("M56x5.5", 56.0, 5.5, 50.5),
    ("M60x5.5", 60.0, 5.5, 54.5),
    ("M64x6.0", 64.0, 6.0, 58.0),
    ("M68x6.0", 68.0, 6.0, 62.0),
)

ISO_FINE = (
    ("M1x0.2", 1.0, 0.2, 0.8),
    ("M1.1x0.2", 1.1, 0.2, 0.9),
    ("M1.2x0.2", 1.2, 0.2, 1.0),
    ("M1.4x0.2", 1.4, 0.2, 1.2),
    ("M1.6x0.2", 1.6, 0.2, 1.4),
    ("M1.8x0.2", 1.8, 0.2, 1.6),
    ("M2x0.25", 2.0, 0.25, 1.75),
    ("M2.2x0.25", 2.2, 0.25, 1.95),
    ("M2.5x0.35", 2.5, 0.35, 2.15),
    ("M3x0.35", 3.0, 0.35, 2.65),
    ("M3.5x0.35", 3.5, 0.35, 3.15),
    ("M4x0.5", 4.0, 0.5, 3.5),
    ("M4.5x0.5", 4.5, 0.5, 4.0),
    ("M5x0.5", 5.0, 0.5, 4.5),
    ("M5.5x0.5", 5.5, 0.5, 5.0),
    ("M6x0.75", 6.0, 0.75, 5.25),
    ("M7x0.75", 7.0, 0.75, 6.25),
    ("M8x0.75", 8.0, 0.75, 7.25),
    ("M8x1.0", 8.0, 1.0, 7.0),
    ("M9x0.75", 9.0, 0.75, 8.25),
    ("M9x1.0", 9.0, 1.0, 8.0),
    ("M10x0.75", 10.0, 0.75, 9.25),
    ("M10x1.0", 10.0, 1.0, 9.0),
    ("M10x1.25", 10.0, 1.25, 8.75),
    ("M11x0.75", 11.0, 0.75, 10.25),
    ("M11x1.0", 11.0, 1.0, 10.0),
    ("M12x1.0", 12.0, 1.0, 11.0),
    ("M12x1.25", 12.0, 1.25, 10.75),
    ("M12x1.5", 12.0, 1.5, 10.5),
    ("M14x1.0", 14.0, 1.0, 13.0),
    ("M14x1.25", 14.0, 1.25, 12.75),
    ("M14x1.5", 14.0, 1.5, 12.5),
    ("M15x1.0", 15.0, 1.0, 14.0),
    ("M15x1.5", 15.0, 1.5, 13.5),
    ("M16x1.0", 16.0, 1.0, 15.0),
    ("M16x1.5", 16.0, 1.5, 14.5),
    ("M17x1.0", 17.0, 1.0, 16.0),
    ("M17x1.5", 17.0, 1.5, 15.5),
    ("M18x1.0", 18.0, 1.0, 17.0),
    ("M18x1.5", 18.0, 1.5, 16.5),
    ("M18x2.0", 18.0, 2.0, 16.0),
    ("M20x1.0", 20.0, 1.0, 19.0),
    ("M20x1.5", 20.0, 1.5, 18.5),
    ("M20x2.0", 20.0, 2.0, 18.0),
    ("M22x1.0", 22.0, 1.0, 21.0),
    ("M22x1.5", 22.0, 1.5, 20.5),
    ("M22x2.0", 22.0, 2.0, 20.0),
    ("M24x1.0", 24.0, 1.0, 23.0),
    ("M24x1.5", 24.0, 1.5, 22.5),
    ("M24x2.0", 24.0, 2.0, 22.0),
    ("M25x1.0", 25.0, 1.0, 24.0),
    ("M25x1.5", 25.0, 1.5, 23.5),
    ("M25x2.0", 25.0, 2.0, 23.0),
    ("M27x1.0", 27.0, 1.0, 26.0),
    ("M27x1.5", 27.0, 1.5, 25.5),
    ("M27x2.0", 27.0, 2.0, 25.0),
    ("M28x1.0", 28.0, 1.0, 27.0),
    ("M28x1.5", 28.0, 1.5, 26.5),
    ("M28x2.0", 28.0, 2.0, 26.0),
    ("M30x1.0", 30.0, 1.0, 29.0),
    ("M30x1.5", 30.0, 1.5, 28.5),
    ("M30x2.0", 30.0, 2.0, 28.0),
    ("M30x3.0", 30.0, 3.0, 27.0),
    ("M32x1.5", 32.0, 1.5, 30.5),
    ("M32x2.0", 32.0, 2.0, 30.0),
    ("M33x1.5", 33.0, 1.5, 31.5),
    ("M33x2.0", 33.0, 2.0, 31.0),
    ("M33x3.0", 33.0, 3.0, 30.0),
    ("M35x1.5", 35.0, 1.5, 33.5),
    ("M35x2.0", 35.0, 2.0, 33.0),
    ("M36x1.5", 36.0, 1.5, 34.5),
    ("M36x2.0", 36.0, 2.0, 34.0),
    ("M36x3.0", 36.0, 3.0, 33.0),
    ("M39x1.5", 39.0, 1.5, 37.5),
    ("M39x2.0", 39.0, 2.0, 37.0),
    ("M39x3.0", 39.0, 3.0, 36.0),
    ("M40x1.5", 40.0, 1.5, 38.5),
    ("M40x2.0", 40.0, 2.0, 38.0),
    ("M40x3.0", 40.0, 3.0, 37.0),
    ("M42x1.5", 42.0, 1.5, 40.5),
    ("M42x2.0", 42.0, 2.0, 40.0),
    ("M42x3.0", 42.0, 3.0, 39.0),
    ("M42x4.0", 42.0, 4.0, 38.0),
    ("M45x1.5", 45.0, 1.5, 43.5),
    ("M45x2.0", 45.0, 2.0, 43.0),
    ("M45x3.0", 45.0, 3.0, 42.0),
    ("M45x4.0", 45.0, 4.0, 41.0),
    ("M48x1.5", 48.0, 1.5, 46.5),
    ("M48x2.0", 48.0, 2.0, 46.0),
    ("M48x3.0", 48.0, 3.0, 45.0),
    ("M48x4.0", 48.0, 4.0, 44.0),
    ("M50x1.5", 50.0, 1.5, 48.5),
    ("M50x2.0", 50.0, 2.0, 48.0),
    ("M50x3.0", 50.0, 3.0, 47.0),
    ("M52x1.5", 52.0, 1.5, 50.5),
    ("M52x2.0", 52.0, 2.0, 50.0),
    ("M52x3.0", 52.0, 3.0, 49.0),
    ("M52x4.0", 52.0, 4.0, 48.0),
    ("M55x1.5", 55.0, 1.5, 53.5),
    ("M55x2.0", 55.0, 2.0, 53.0),
    ("M55x3.0", 55.0, 3.0, 52.0),
    ("M55x4.0", 55.0, 4.0, 51.0),
    ("M56x1.5", 56.0, 1.5, 54.5),
    ("M56x2.0", 56.0, 2.0, 54.0),
    ("M56x3.0", 56.0, 3.0, 53.0),
    ("M56x4.0", 56.0, 4.0, 52.0),
    ("M58x1.5", 58.0, 1.5, 56.5),
    ("M58x2.0", 58.0, 2.0, 56.0),
    ("M58x3.0", 58.0, 3.0, 55.0),
    ("M58x4.0", 58.0, 4.0, 54.0),
    ("M60x1.5", 60.0, 1.5, 58.5),
    ("M60x2.0", 60.0, 2.0, 58.0),
    ("M60x3.0", 60.0, 3.0, 57.0),
    ("M60x4.0", 60.0, 4.0, 56.0),
    ("M62x1.5", 62.0, 1.5, 60.5),
    ("M62x2.0", 62.0, 2.0, 60.0),
    ("M62x3.0", 62.0, 3.0, 59.0),
    ("M62x4.0", 62.0, 4.0, 58.0),
    ("M64x1.5", 64.0, 1.5, 62.5),
    ("M64x2.0", 64.0, 2.0, 62.0),
    ("M64x3.0", 64.0, 3.0, 61.0),
    ("M64x4.0", 64.0, 4.0, 60.0),
    ("M65x1.5", 65.0, 1.5, 63.5),
    ("M65x2.0", 65.0, 2.0, 63.0),
    ("M65x3.0", 65.0, 3.0, 62.0),
    ("M65x4.0", 65.0, 4.0, 61.0),
    ("M68x1.5", 68.0, 1.5, 66.5),
    ("M68x2.0", 68.0, 2.0, 66.0),
    ("M68x3.0", 68.0, 3.0, 65.0),
    ("M68x4.0", 68.0, 4.0, 64.0),
    ("M70x1.5", 70.0, 1.5, 68.5),
    ("M70x2.0", 70.0, 2.0, 68.0),
    ("M70x3.0", 70.0, 3.0, 67.0),
    ("M70x4.0", 70.0, 4.0, 66.0),
    ("M70x6.0", 70.0, 6.0, 64.0),
    ("M72x1.5", 72.0, 1.5, 70.5),
    ("M72x2.0", 72.0, 2.0, 70.0),
    ("M72x3.0", 72.0, 3.0, 69.0),
    ("M72x4.0", 72.0, 4.0, 68.0),
    ("M72x6.0", 72.0, 6.0, 66.0),
    ("M75x1.5", 75.0, 1.5, 73.5),
    ("M75x2.0", 75.0, 2.0, 73.0),
    ("M75x3.0", 75.0, 3.0, 72.0),
    ("M75x4.0", 75.0, 4.0, 71.0),
    ("M75x6.0", 75.0, 6.0, 69.0),
    ("M76x1.5", 76.0, 1.5, 74.5),
    ("M76x2.0", 76.0, 2.0, 74.0),
    ("M76x3.0", 76.0, 3.0, 73.0),
    ("M76x4.0", 76.0, 4.0, 72.0),
    ("M76x6.0", 76.0, 6.0, 70.0),
    ("M80x1.5", 80.0, 1.5, 78.5),
    ("M80x2.0", 80.0, 2.0, 78.0),
    ("M80x3.0", 80.0, 3.0, 77.0),
    ("M80x4.0", 80.0, 4.0, 76.0),
    ("M80x6.0", 80.0, 6.0, 74.0),
    ("M85x2.0", 85.0, 2.0, 83.0),
    ("M85x3.0", 85.0, 3.0, 82.0),
    ("M85x4.0", 85.0, 4.0, 81.0),
    ("M85x6.0", 85.0, 6.0, 79.0),
    ("M90x2.0", 90.0, 2.0, 88.0),
    ("M90x3.0", 90.0, 3.0, 87.0),
    ("M90x4.0", 90.0, 4.0, 86.0),
    ("M90x6.0", 90.0, 6.0, 84.0),
    ("M95x2.0", 95.0, 2.0, 93.0),
    ("M95x3.0", 95.0, 3.0, 92.0),
    ("M95x4.0", 95.0, 4.0, 91.0),
    ("M95x6.0", 95.0, 6.0, 89.0),
    ("M100x2.0", 100.0, 2.0, 98.0),
    ("M100x3.0", 100.0, 3.0, 97.0),
    ("M100x4.0", 100.0, 4.0, 96.0),
    ("M100x6.0", 100.0, 6.0, 94.0),
)

UNC = (
    ("#1", 1.854, 0.397, 1.5),
    ("#2", 2.184, 0.454, 1.85),
    ("#3", 2.515, 0.529, 2.1),
    ("#4", 2.845, 0.635, 2.35),
    ("#5", 3.175, 0.635, 2.65),
    ("#6", 3.505, 0.794, 2.85),
    ("#8", 4.166, 0.794, 3.5),
    ("#10", 4.826, 1.058, 3.9),
    ("#12", 5.486, 1.058, 4.5),
    ("1/4", 6.35, 1.27, 5.1),
    ("5/16", 7.938, 1.411, 6.6),
    ("3/8", 9.525, 1.588, 8.0),
    ("7/16", 11.113, 1.814, 9.4),
    ("1/2", 12.7, 1.954, 10.8),
    ("9/16", 14.288, 2.117, 12.2),
    ("5/8", 15.875, 2.309, 13.5),
    ("3/4", 19.05, 2.54, 16.5),
    ("7/8", 22.225, 2.822, 19.5),
    ("1", 25.4, 3.175, 22.25),
    ("1 1/8", 28.575, 3.628, 25.0),
    ("1 1/4", 31.75, 3.628, 28.0),
    ("1 3/8", 34.925, 4.233, 30.75),
    ("1 1/2", 38.1, 4.233, 34.0),
    ("1 3/4", 44.45, 5.08, 39.5),
    ("2", 50.8, 5.644, 45.0),
    ("2 1/4", 57.15, 5.644, 51.5),
    ("2 1/2", 63.5, 6.35, 57.0),
    ("2 3/4", 69.85, 6.35, 63.5),
    ("3", 76.2, 6.35, 70.0),
    ("3 1/4", 82.55, 6.35, 76.5),
    ("3 1/2", 88.9, 6.35, 83.0),
    ("3 3/4", 95.25, 6.35, 89.0),
    ("4", 101.6, 6.35, 95.5),
)

UNF = (
    ("#0", 1.524, 0.317, 1.2),
    ("#1", 1.854, 0.353, 1.55),
    ("#2", 2.184, 0.397, 1.85),
    ("#3", 2.515, 0.454, 2.1),
    ("#4", 2.845, 0.529, 2.4),
    ("#5", 3.175, 0.577, 2.7),
    ("#6", 3.505, 0.635, 2.95),
    ("#8", 4.166, 0.706, 3.5),
    ("#10", 4.826, 0.794, 4.1),
    ("#12", 5.486, 0.907, 4.7),
    ("1/4", 6.35, 0.907, 5.5),
    ("5/16", 7.938, 1.058, 6.9),
    ("3/8", 9.525, 1.058, 8.5),
    ("7/16", 11.113, 1.27, 9.9),
    ("1/2", 12.7, 1.27, 11.5),
    ("9/16", 14.288, 1.411, 12.9),
    ("5/8", 15.875, 1.411, 14.5),
    ("3/4", 19.05, 1.588, 17.5),
    ("7/8", 22.225, 1.814, 20.4),
    ("1", 25.4, 2.117, 23.25),
    ("1 1/8", 28.575, 2.117, 26.5),
    ("1 3/16", 30.163, 1.588, 28.58),
    ("1 1/4", 31.75, 2.117, 29.5),
    ("1 3/8", 34.925, 2.117, 32.75),
    ("1 1/2", 38.1, 2.117, 36.0),
)

UNEF = (
    ("#12", 5.486, 0.794, 4.8),
    ("1/4", 6.35, 0.794, 5.7),
    ("5/16", 7.938, 0.794, 7.25),
    ("3/8", 9.525, 0.794, 8.85),
    ("7/16", 11.113, 0.907, 10.35),
    ("1/2", 12.7, 0.907, 11.8),
    ("9/16", 14.288, 1.058, 13.4),
    ("5/8", 15.875, 1.058, 15.0),
    ("11/16", 17.462, 1.058, 16.6),
    ("3/4", 19.05, 1.27, 18.0),
    ("13/16", 20.638, 1.27, 19.6),
    ("7/8", 22.225, 1.27, 21.15),
    ("15/16", 23.812, 1.27, 22.7),
    ("1", 25.4, 1.27, 24.3),
    ("1 1/16", 26.988, 1.411, 25.8),
    ("1 1/8", 28.575, 1.411, 27.35),
    ("1 1/4", 31.75, 1.411, 30.55),
    ("1 5/16", 33.338, 1.411, 32.1),
    ("1 3/8", 34.925, 1.411, 33.7),
    ("1 7/16", 36.512, 1.411, 35.3),
    ("1 1/2", 38.1, 1.411, 36.9),
    ("1 9/16", 39.688, 1.411, 38.55),
    ("1 5/8", 41.275, 1.411, 40.1),
    ("1 11/16", 42.862, 1.411, 41.6),
)

TABLES = {
    "ISOMetricProfile": ISO_COARSE,
    "ISOMetricFineProfile": ISO_FINE,
    "UNC": UNC,
    "UNF": UNF,
    "UNEF": UNEF,
}
