# SPDX-License-Identifier: LGPL-2.1-or-later
"""The fonts of this computer, for sketch text (text.py). Pure Python: no FreeCAD, no Qt.

Fusion's Text dialog lists the fonts installed on the computer by family name ("Arial",
"Times New Roman") and has Bold and Italic buttons that pick the family's bold or italic
face. FreeCAD draws glyph outlines from a font *file* (Part.makeWireString, FreeType), so
SciForge needs the file of each family and style. This module finds them on Windows and
Linux by reading the font files themselves (no fontconfig, no registry): the OpenType
tables 'name' (family and style names), 'OS/2' and 'head' (bold / italic flags, metrics),
'hhea' and 'hmtx' (advance widths), 'cmap' (which glyph a character uses), 'kern' (pair
kerning, the table FreeType's FT_Get_Kerning reads) and 'post' (underline position).

  read_info(path)        one font file: names, flags and metrics (FontInfo)
  Catalog(faces)         families -> faces, the face for (family, bold, italic)
  scan(dirs, cache)      every font file in the folders (cached by path, size, mtime)
  system_dirs()          where this computer keeps its fonts (Windows / Linux), plus the
                         fonts FreeCAD itself ships (always there: the default fallback)

Only TrueType (.ttf), OpenType (.otf, CFF outlines too) and the first face of a
collection (.ttc) are listed: FreeCAD's makeWireString always opens face 0 of a file.
"""

import json
import os
import struct

EXTENSIONS = (".ttf", ".otf", ".ttc")
MAX_FILES = 6000  # a folder tree with more font files is cut short (scan time)
MAX_DEPTH = 6

# Fusion's text starts in Arial on Windows. On Linux the metric-compatible Liberation
# Sans / Arimo come first, then common sans fonts, then what FreeCAD itself ships
# (DejaVu Sans in its bundle, osifont with TechDraw): one of them is always there.
DEFAULT_FAMILIES = (
    "Arial",
    "Liberation Sans",
    "Arimo",
    "Helvetica",
    "DejaVu Sans",
    "FreeSans",
    "Noto Sans",
    "Ubuntu",
    "Segoe UI",
    "Calibri",
    "osifont",
)

# OS/2 fsSelection bits
FS_ITALIC = 1 << 0
FS_BOLD = 1 << 5
FS_REGULAR = 1 << 6
FS_USE_TYPO_METRICS = 1 << 7
FS_OBLIQUE = 1 << 9
# head macStyle bits
MAC_BOLD = 1 << 0
MAC_ITALIC = 1 << 1


class FontError(ValueError):
    """A file that is no font SciForge can read (the message says why)."""


# -- reading the tables ---------------------------------------------------------------------
def _u16(data, at):
    return struct.unpack_from(">H", data, at)[0]


def _i16(data, at):
    return struct.unpack_from(">h", data, at)[0]


def _u32(data, at):
    return struct.unpack_from(">I", data, at)[0]


def _directory(handle):
    """{tag: (offset, length)} of the font's tables (face 0 of a collection)."""
    handle.seek(0)
    head = handle.read(12)
    if len(head) < 12:
        raise FontError("too short to be a font")
    tag = head[:4]
    base = 0
    if tag == b"ttcf":
        count = _u32(head, 8)
        if count < 1:
            raise FontError("empty font collection")
        handle.seek(12)
        base = _u32(handle.read(4), 0)
        handle.seek(base)
        head = handle.read(12)
        if len(head) < 12:
            raise FontError("broken font collection")
        tag = head[:4]
    if tag not in (b"\x00\x01\x00\x00", b"OTTO", b"true"):
        raise FontError("not a TrueType / OpenType font")
    count = _u16(head, 4)
    if count > 200:
        raise FontError("too many tables")
    records = handle.read(16 * count)
    if len(records) < 16 * count:
        raise FontError("broken table directory")
    tables = {}
    for i in range(count):
        name = records[16 * i : 16 * i + 4].decode("latin-1")
        offset = _u32(records, 16 * i + 8)
        length = _u32(records, 16 * i + 12)
        tables[name] = (offset, length)
    return tables


def _table(handle, tables, name, limit=None):
    """The bytes of a table, or None if the font has none."""
    entry = tables.get(name)
    if entry is None:
        return None
    offset, length = entry
    if limit is not None:
        length = min(length, limit)
    handle.seek(offset)
    data = handle.read(length)
    return data if len(data) == length else None


def _names(data):
    """{nameID: text} preferring Windows English, then any Windows / Unicode, then Mac."""
    if data is None or len(data) < 6:
        return {}
    count = _u16(data, 2)
    strings = _u16(data, 4)
    found = {}  # nameID -> (rank, text)
    for i in range(count):
        at = 6 + 12 * i
        if at + 12 > len(data):
            break
        platform, encoding, language, name_id, length, offset = struct.unpack_from(">6H", data, at)
        raw = data[strings + offset : strings + offset + length]
        if platform in (0, 3):
            try:
                text = raw.decode("utf-16-be")
            except UnicodeDecodeError:
                continue
            rank = 0 if (platform == 3 and language == 0x409) else (1 if platform == 3 else 2)
        elif platform == 1 and encoding == 0:
            text = raw.decode("mac_roman", "replace")
            rank = 3
        else:
            continue
        text = text.strip("\x00").strip()
        if not text:
            continue
        old = found.get(name_id)
        if old is None or rank < old[0]:
            found[name_id] = (rank, text)
    return {key: value[1] for key, value in found.items()}


def _cmap(data):
    """{code point: glyph id} from the best Unicode subtable (formats 0, 4, 6, 12)."""
    if data is None or len(data) < 4:
        return {}
    count = _u16(data, 2)
    choices = []
    for i in range(count):
        at = 4 + 8 * i
        if at + 8 > len(data):
            break
        platform, encoding = _u16(data, at), _u16(data, at + 2)
        offset = _u32(data, at + 4)
        if offset + 2 > len(data):
            continue
        fmt = _u16(data, offset)
        rank = {
            (3, 10): 0,
            (0, 6): 1,
            (0, 4): 1,
            (3, 1): 2,
            (0, 3): 3,
            (0, 1): 3,
            (0, 0): 3,
            (3, 0): 4,
            (1, 0): 5,
        }.get((platform, encoding))
        if rank is None or fmt not in (0, 4, 6, 12):
            continue
        choices.append((rank, fmt, offset, (platform, encoding)))
    for _rank, fmt, offset, key in sorted(choices):
        try:
            table = _CMAP_READERS[fmt](data, offset)
        except (struct.error, IndexError):
            continue
        if key == (3, 0):  # symbol fonts map their glyphs at U+F000 + the byte
            table = dict(table)
            for code, glyph in list(table.items()):
                if 0xF000 <= code <= 0xF0FF:
                    table.setdefault(code - 0xF000, glyph)
        if table:
            return table
    return {}


def _cmap0(data, offset):
    return {code: data[offset + 6 + code] for code in range(256) if data[offset + 6 + code]}


def _cmap4(data, offset):
    segments = _u16(data, offset + 6) // 2
    ends = offset + 14
    starts = ends + 2 * segments + 2
    deltas = starts + 2 * segments
    ranges = deltas + 2 * segments
    table = {}
    for i in range(segments):
        end = _u16(data, ends + 2 * i)
        start = _u16(data, starts + 2 * i)
        delta = _i16(data, deltas + 2 * i)
        range_offset = _u16(data, ranges + 2 * i)
        if start > end:
            continue
        for code in range(start, min(end, 0xFFFE) + 1):
            if range_offset == 0:
                glyph = (code + delta) & 0xFFFF
            else:
                at = ranges + 2 * i + range_offset + 2 * (code - start)
                if at + 2 > len(data):
                    continue
                glyph = _u16(data, at)
                if glyph:
                    glyph = (glyph + delta) & 0xFFFF
            if glyph:
                table[code] = glyph
    return table


def _cmap6(data, offset):
    first, count = _u16(data, offset + 6), _u16(data, offset + 8)
    table = {}
    for i in range(count):
        glyph = _u16(data, offset + 10 + 2 * i)
        if glyph:
            table[first + i] = glyph
    return table


def _cmap12(data, offset):
    groups = _u32(data, offset + 12)
    table = {}
    for i in range(min(groups, 100000)):
        at = offset + 16 + 12 * i
        start, end, glyph = struct.unpack_from(">3I", data, at)
        if end - start > 0x30000:
            continue
        for code in range(start, end + 1):
            table[code] = glyph + (code - start)
    return table


_CMAP_READERS = {0: _cmap0, 4: _cmap4, 6: _cmap6, 12: _cmap12}


def _kern(data):
    """{(left glyph, right glyph): value} from a 'kern' table (Microsoft format 0)."""
    pairs = {}
    if data is None or len(data) < 4 or _u16(data, 0) != 0:
        return pairs
    count = _u16(data, 2)
    at = 4
    for _ in range(count):
        if at + 6 > len(data):
            break
        length = _u16(data, at + 2)
        coverage = _u16(data, at + 4)
        fmt = coverage >> 8
        horizontal = coverage & 1
        minimum = coverage & 2
        cross = coverage & 4
        if fmt == 0 and horizontal and not minimum and not cross:
            n = _u16(data, at + 6)
            for i in range(n):
                p = at + 14 + 6 * i
                if p + 6 > len(data):
                    break
                left, right, value = struct.unpack_from(">HHh", data, p)
                pairs[(left, right)] = pairs.get((left, right), 0) + value
        at += max(length, 6)
    return pairs


# -- one font file ----------------------------------------------------------------------------
class FontInfo:
    """What SciForge knows about one font file. Names and flags are read at once; the
    tables for layout (advances, characters, kerning) only when first asked for."""

    def __init__(self, path):
        self.path = path
        self.family = ""
        self.style = ""
        self.full_name = ""
        self.bold = False
        self.italic = False
        self.weight = 400
        self.units_per_em = 1000
        self.ascender = 800
        self.descender = -200
        self.line_gap = 0
        self.cap_height = 0
        self.x_height = 0
        self.underline_position = 0
        self.underline_thickness = 0
        self.italic_angle = 0.0
        self.typo_metrics = False
        self.ft_height = 0  # FreeType's face->height (its outline scale in makeWireString)
        self._cmap = None
        self._advances = None
        self._kern = None
        self._hmetrics = 0

    # -- reading ------------------------------------------------------------------------
    def load_names(self, handle, tables):
        names = _names(_table(handle, tables, "name"))
        # nameID 1/2 group Regular, Bold, Italic and Bold Italic in one family, the way the
        # Windows font list (and Fusion's) shows them; 16/17 are the typographic names.
        self.family = names.get(1) or names.get(16) or names.get(4) or ""
        self.style = names.get(2) or names.get(17) or "Regular"
        self.full_name = names.get(4) or ("%s %s" % (self.family, self.style)).strip()
        head = _table(handle, tables, "head")
        mac_style = 0
        if head is not None and len(head) >= 54:
            self.units_per_em = _u16(head, 18) or 1000
            mac_style = _u16(head, 44)
        os2 = _table(handle, tables, "OS/2")
        selection = 0
        if os2 is not None and len(os2) >= 78:
            version = _u16(os2, 0)
            self.weight = _u16(os2, 4) or 400
            selection = _u16(os2, 62)
            typo = (_i16(os2, 68), _i16(os2, 70), _i16(os2, 72))
            win = (_u16(os2, 74), _u16(os2, 76))
            self.typo_metrics = bool(selection & FS_USE_TYPO_METRICS)
            if version >= 2 and len(os2) >= 90:
                self.x_height = _i16(os2, 86)
                self.cap_height = _i16(os2, 88)
        else:
            typo = win = None
        self.bold = bool(selection & FS_BOLD or mac_style & MAC_BOLD) or self.weight >= 700
        self.italic = bool(selection & (FS_ITALIC | FS_OBLIQUE) or mac_style & MAC_ITALIC)
        hhea = _table(handle, tables, "hhea")
        if hhea is not None and len(hhea) >= 36:
            self.ascender = _i16(hhea, 4)
            self.descender = _i16(hhea, 6)
            self.line_gap = _i16(hhea, 8)
            self._hmetrics = _u16(hhea, 34)
        # FreeType's face->height: hhea, else OS/2 typo, else OS/2 win (sfnt_load_face)
        if self.ascender or self.descender:
            self.ft_height = self.ascender - self.descender + self.line_gap
        elif typo is not None and (typo[0] or typo[1]):
            self.ft_height = typo[0] - typo[1] + typo[2]
        elif win is not None:
            self.ft_height = win[0] + win[1]
        # FreeType takes the line metrics from OS/2 when the font asks for it (and when
        # hhea has none): the same rule here, so lines are spaced as FreeType would.
        if typo is not None and (self.typo_metrics or not (self.ascender or self.descender)):
            self.ascender, self.descender, self.line_gap = typo
        post = _table(handle, tables, "post", limit=32)
        if post is not None and len(post) >= 12:
            self.italic_angle = _i16(post, 4) + _u16(post, 6) / 65536.0
            self.underline_position = _i16(post, 8)
            self.underline_thickness = _i16(post, 10)
        if not self.cap_height:
            self.cap_height = int(round(0.7 * self.units_per_em))
        if not self.x_height:
            self.x_height = int(round(0.5 * self.units_per_em))
        if self.underline_thickness <= 0:
            self.underline_thickness = max(1, int(round(0.05 * self.units_per_em)))
        if self.underline_position == 0:
            self.underline_position = -int(round(0.1 * self.units_per_em))

    def _load_layout(self):
        if self._cmap is not None:
            return
        self._cmap, self._advances, self._kern = {}, [], {}
        try:
            with open(self.path, "rb") as handle:
                tables = _directory(handle)
                self._cmap = _cmap(_table(handle, tables, "cmap"))
                hmtx = _table(handle, tables, "hmtx")
                if hmtx is not None and self._hmetrics:
                    count = min(self._hmetrics, len(hmtx) // 4)
                    self._advances = [_u16(hmtx, 4 * i) for i in range(count)]
                self._kern = _kern(_table(handle, tables, "kern"))
        except (OSError, FontError, struct.error):
            pass

    # -- layout numbers (font units) ----------------------------------------------------------
    @property
    def line_height(self):
        """Distance between two baselines (FreeType's face->height)."""
        return self.ascender - self.descender + self.line_gap

    def glyph(self, char):
        self._load_layout()
        return self._cmap.get(ord(char), 0)

    def has_char(self, char):
        return self.glyph(char) != 0

    def advance(self, char):
        """Advance width of a character (font units). Missing glyphs use glyph 0's."""
        self._load_layout()
        advances = self._advances
        if not advances:
            return self.units_per_em // 2
        glyph = self._cmap.get(ord(char), 0)
        return advances[glyph] if glyph < len(advances) else advances[-1]

    def kerning(self, left, right):
        """Pair kerning between two characters (font units, usually negative)."""
        self._load_layout()
        if not self._kern:
            return 0
        return self._kern.get((self.glyph(left), self.glyph(right)), 0)

    def to_dict(self):
        keys = (
            "family",
            "style",
            "full_name",
            "bold",
            "italic",
            "weight",
            "units_per_em",
            "ascender",
            "descender",
            "line_gap",
            "cap_height",
            "x_height",
            "underline_position",
            "underline_thickness",
            "italic_angle",
            "typo_metrics",
            "ft_height",
            "_hmetrics",
        )
        return {key: getattr(self, key) for key in keys}

    @classmethod
    def from_dict(cls, path, data):
        info = cls(path)
        for key, value in data.items():
            if hasattr(info, key):
                setattr(info, key, value)
        return info

    def __repr__(self):
        return "<FontInfo %s %s %s>" % (self.family, self.style, os.path.basename(self.path))


def read_info(path):
    """FontInfo of a font file. Raises FontError (or OSError) for anything else."""
    with open(path, "rb") as handle:
        tables = _directory(handle)
        info = FontInfo(path)
        info.load_names(handle, tables)
    if not info.family:
        raise FontError("the font has no family name")
    return info


# -- every font of the computer ---------------------------------------------------------------
def system_dirs(platform=None, environ=None, home=None, extra=()):
    """The folders that hold fonts on this computer (only the ones that exist)."""
    import sys

    platform = platform or sys.platform
    environ = os.environ if environ is None else environ
    home = home or os.path.expanduser("~")
    found = []
    if platform.startswith("win"):
        windir = environ.get("WINDIR") or environ.get("SystemRoot") or "C:\\Windows"
        found.append(os.path.join(windir, "Fonts"))
        local = environ.get("LOCALAPPDATA")
        if local:
            found.append(os.path.join(local, "Microsoft", "Windows", "Fonts"))
    else:
        data_home = environ.get("XDG_DATA_HOME") or os.path.join(home, ".local", "share")
        found.append(os.path.join(data_home, "fonts"))
        found.append(os.path.join(home, ".fonts"))
        for base in (environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share").split(":"):
            if base:
                found.append(os.path.join(base, "fonts"))
        found += ["/usr/share/fonts", "/usr/local/share/fonts"]
    found += list(extra)
    unique = []
    for path in found:
        path = os.path.normpath(path)
        if path not in unique and os.path.isdir(path):
            unique.append(path)
    return unique


def font_files(dirs, limit=MAX_FILES):
    """Every font file under the folders (sorted, at most `limit`)."""
    found = []
    seen = set()
    for top in dirs:
        top_depth = top.rstrip(os.sep).count(os.sep)
        for root, subdirs, files in os.walk(top, followlinks=True):
            if root.count(os.sep) - top_depth >= MAX_DEPTH:
                subdirs[:] = []
            for name in sorted(files):
                if not name.lower().endswith(EXTENSIONS):
                    continue
                path = os.path.join(root, name)
                try:
                    key = os.path.realpath(path)
                except OSError:
                    key = path
                if key in seen:
                    continue
                seen.add(key)
                found.append(path)
                if len(found) >= limit:
                    return found
    return found


def _stamp(path):
    try:
        st = os.stat(path)
        return [int(st.st_mtime), int(st.st_size)]
    except OSError:
        return None


def scan(dirs, cache_path=None, limit=MAX_FILES):
    """A Catalog of the fonts in `dirs`. With `cache_path` (a JSON file) the names of a
    file that did not change since the last scan are not read again."""
    cache = {}
    if cache_path:
        try:
            with open(cache_path, "r", encoding="utf-8") as handle:
                cache = json.load(handle)
        except (OSError, ValueError):
            cache = {}
    faces = []
    fresh = {}
    for path in font_files(dirs, limit):
        stamp = _stamp(path)
        if stamp is None:
            continue
        entry = cache.get(path)
        info = None
        if entry and entry.get("stamp") == stamp:
            if entry.get("bad"):
                fresh[path] = entry
                continue
            info = FontInfo.from_dict(path, entry.get("info", {}))
        if info is None:
            try:
                info = read_info(path)
            except (OSError, FontError, struct.error, ValueError) as exc:
                fresh[path] = {"stamp": stamp, "bad": str(exc)[:80]}
                continue
        fresh[path] = {"stamp": stamp, "info": info.to_dict()}
        faces.append(info)
    if cache_path and fresh != cache:
        try:
            folder = os.path.dirname(cache_path)
            if folder and not os.path.isdir(folder):
                os.makedirs(folder)
            with open(cache_path, "w", encoding="utf-8") as handle:
                json.dump(fresh, handle)
        except OSError:
            pass
    return Catalog(faces)


def _style_rank(info, bold, italic):
    """How well a face fits a wanted style: 0 is exact; lower is better."""
    rank = 0
    if info.bold != bold:
        rank += 2
    if info.italic != italic:
        rank += 1
    # among equals, the plainest weight (Regular 400 / Bold 700) wins
    target = 700 if bold else 400
    return rank * 1000 + abs(info.weight - target)


class Catalog:
    """Families -> faces. face_for(family, bold, italic) gives the file to draw with and
    whether bold / italic must be made up (a family without a bold face)."""

    def __init__(self, faces):
        self.faces = list(faces)
        self._families = {}
        for info in self.faces:
            self._families.setdefault(info.family, []).append(info)
        self._lower = {name.lower(): name for name in self._families}

    def families(self):
        return sorted(self._families, key=lambda n: n.lower())

    def __len__(self):
        return len(self.faces)

    def find_family(self, name):
        """The family as the catalog spells it (case does not matter), or None."""
        if not name:
            return None
        if name in self._families:
            return name
        return self._lower.get(name.lower())

    def faces_of(self, family):
        return list(self._families.get(self.find_family(family) or "", []))

    def face_for(self, family, bold=False, italic=False):
        """(FontInfo, make_bold, make_italic) for the family's best face, or None when the
        family is not installed. make_bold / make_italic: the family has no such face, so
        the outline must be made bolder / slanted (as Windows does)."""
        faces = self.faces_of(family)
        if not faces:
            return None
        best = min(faces, key=lambda f: (_style_rank(f, bold, italic), f.path))
        return best, bool(bold and not best.bold), bool(italic and not best.italic)

    def default_family(self, preferred=DEFAULT_FAMILIES):
        for name in preferred:
            found = self.find_family(name)
            if found:
                return found
        names = self.families()
        return names[0] if names else None

    def file_family(self, path):
        """The family of a font file the catalog knows, or None."""
        norm = os.path.normcase(os.path.normpath(path or ""))
        for info in self.faces:
            if os.path.normcase(os.path.normpath(info.path)) == norm:
                return info.family
        return None
