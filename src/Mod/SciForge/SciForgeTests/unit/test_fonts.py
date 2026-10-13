# SPDX-License-Identifier: LGPL-2.1-or-later
"""sciforge/fonts.py: reading font files (names, flags, metrics, characters, kerning) and
choosing a family's face for Bold / Italic. Runs without FreeCAD: the fonts are small
synthetic files built here, table by table (no font file of the computer is needed)."""

import json
import os
import shutil
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sciforge import fonts  # noqa: E402


def _name_table(names):
    """'name' table with Windows (3, 1, 0x409) UTF-16 records {nameID: text}."""
    records, strings = [], b""
    for name_id, text in sorted(names.items()):
        raw = text.encode("utf-16-be")
        records.append(struct.pack(">6H", 3, 1, 0x409, name_id, len(raw), len(strings)))
        strings += raw
    header = struct.pack(">3H", 0, len(records), 6 + 12 * len(records))
    return header + b"".join(records) + strings


def _cmap_format4(mapping):
    """A format 4 subtable: one segment per character (plus the closing 0xFFFF)."""
    codes = sorted(mapping)
    segments = [(c, c, mapping[c] - c) for c in codes] + [(0xFFFF, 0xFFFF, 1)]
    n = len(segments)
    ends = b"".join(struct.pack(">H", e) for _s, e, _d in segments)
    starts = b"".join(struct.pack(">H", s) for s, _e, _d in segments)
    deltas = b"".join(struct.pack(">h", ((d + 0x8000) & 0xFFFF) - 0x8000) for _s, _e, d in segments)
    ranges = b"\x00\x00" * n
    body = struct.pack(">4H", 2 * n, 0, 0, 0) + ends + b"\x00\x00" + starts + deltas + ranges
    return struct.pack(">3H", 4, 6 + len(body), 0) + body


def _cmap_format12(mapping):
    groups = b"".join(struct.pack(">3I", c, c, g) for c, g in sorted(mapping.items()))
    return struct.pack(">HHIII", 12, 0, 16 + len(groups), 0, len(mapping)) + groups


def _cmap(mapping, fmt=4):
    sub = _cmap_format4(mapping) if fmt == 4 else _cmap_format12(mapping)
    platform, encoding = (3, 1) if fmt == 4 else (3, 10)
    return struct.pack(">2H", 0, 1) + struct.pack(">2HI", platform, encoding, 12) + sub


def _kern(pairs):
    data = b"".join(struct.pack(">HHh", l, r, v) for (l, r), v in sorted(pairs.items()))
    sub = struct.pack(">3H4H", 0, 14 + len(data), 0x0001, len(pairs), 0, 0, 0) + data
    return struct.pack(">2H", 0, 1) + sub


def build_font(
    family="Testy",
    style="Regular",
    bold=False,
    italic=False,
    weight=None,
    upem=1000,
    advances=(500, 600, 700, 400),
    chars="ABC",
    kern=None,
    cmap_format=4,
    typo=False,
    post=(-100, 50),
    cap=700,
):
    """Bytes of a TrueType font with the tables fonts.py reads (no outlines)."""
    weight = weight or (700 if bold else 400)
    selection = (fonts.FS_BOLD if bold else 0) | (fonts.FS_ITALIC if italic else 0)
    if not bold and not italic:
        selection |= fonts.FS_REGULAR
    if typo:
        selection |= fonts.FS_USE_TYPO_METRICS
    mac = (fonts.MAC_BOLD if bold else 0) | (fonts.MAC_ITALIC if italic else 0)
    head = bytearray(54)
    struct.pack_into(">I", head, 0, 0x00010000)
    struct.pack_into(">I", head, 12, 0x5F0F3CF5)
    struct.pack_into(">H", head, 18, upem)
    struct.pack_into(">H", head, 44, mac)
    hhea = bytearray(36)
    struct.pack_into(">I", hhea, 0, 0x00010000)
    struct.pack_into(">hhh", hhea, 4, 800, -200, 90)
    struct.pack_into(">H", hhea, 34, len(advances))
    hmtx = b"".join(struct.pack(">Hh", a, 0) for a in advances)
    os2 = bytearray(96)
    struct.pack_into(">H", os2, 0, 2)
    struct.pack_into(">H", os2, 4, weight)
    struct.pack_into(">H", os2, 62, selection)
    struct.pack_into(">hhh", os2, 68, 750, -250, 0)
    struct.pack_into(">HH", os2, 74, 900, 300)
    struct.pack_into(">hh", os2, 86, 500, cap)
    post_table = bytearray(32)
    struct.pack_into(">I", post_table, 0, 0x00030000)
    struct.pack_into(">hh", post_table, 8, post[0], post[1])
    names = {1: family, 2: style, 4: "%s %s" % (family, style)}
    mapping = {ord(c): i + 1 for i, c in enumerate(chars)}
    tables = {
        "head": bytes(head),
        "hhea": bytes(hhea),
        "hmtx": hmtx,
        "OS/2": bytes(os2),
        "post": bytes(post_table),
        "name": _name_table(names),
        "cmap": _cmap(mapping, cmap_format),
    }
    if kern:
        glyph_pairs = {(mapping[ord(a)], mapping[ord(b)]): v for (a, b), v in kern.items()}
        tables["kern"] = _kern(glyph_pairs)
    tags = sorted(tables)
    offset = 12 + 16 * len(tags)
    directory, blob = b"", b""
    for tag in tags:
        data = tables[tag]
        padded = data + b"\x00" * (-len(data) % 4)
        directory += tag.encode("latin-1") + struct.pack(">3I", 0, offset + len(blob), len(data))
        blob += padded
    header = struct.pack(">IHHHH", 0x00010000, len(tags), 0, 0, 0)
    return header + directory + blob


class FontFolder(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="sciforge-fonts-")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def write(self, name, data):
        path = os.path.join(self.dir, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(data)
        return path


class ReadInfoTests(FontFolder):
    def test_names_flags_and_metrics(self):
        path = self.write("t.ttf", build_font(family="Testy", style="Bold", bold=True))
        info = fonts.read_info(path)
        self.assertEqual(info.family, "Testy")
        self.assertEqual(info.style, "Bold")
        self.assertTrue(info.bold)
        self.assertFalse(info.italic)
        self.assertEqual(info.units_per_em, 1000)
        self.assertEqual((info.ascender, info.descender, info.line_gap), (800, -200, 90))
        self.assertEqual(info.line_height, 1090)
        self.assertEqual(info.ft_height, 1090)  # FreeType: hhea
        self.assertEqual(info.cap_height, 700)
        self.assertEqual((info.underline_position, info.underline_thickness), (-100, 50))

    def test_typo_metrics_flag(self):
        path = self.write("t.ttf", build_font(typo=True))
        info = fonts.read_info(path)
        # lines spaced by OS/2 typo metrics when the font asks for it...
        self.assertEqual((info.ascender, info.descender, info.line_gap), (750, -250, 0))
        # ... but FreeType's outline scale (makeWireString) still uses hhea
        self.assertEqual(info.ft_height, 1090)

    def test_advances_characters_kerning(self):
        path = self.write(
            "t.ttf",
            build_font(advances=(250, 600, 700, 450), chars="ABC", kern={("A", "B"): -40}),
        )
        info = fonts.read_info(path)
        self.assertEqual(info.advance("A"), 600)
        self.assertEqual(info.advance("C"), 450)
        self.assertEqual(info.advance("Z"), 250)  # missing: glyph 0's advance
        self.assertTrue(info.has_char("B"))
        self.assertFalse(info.has_char("Z"))
        self.assertEqual(info.kerning("A", "B"), -40)
        self.assertEqual(info.kerning("B", "A"), 0)

    def test_cmap_format_12(self):
        path = self.write("t.ttf", build_font(chars="xyé", cmap_format=12))
        info = fonts.read_info(path)
        self.assertEqual(info.glyph("é"), 3)
        self.assertEqual(info.glyph("q"), 0)

    def test_italic_from_flags(self):
        path = self.write("t.ttf", build_font(style="Italic", italic=True))
        info = fonts.read_info(path)
        self.assertTrue(info.italic)
        self.assertFalse(info.bold)

    def test_not_a_font(self):
        path = self.write("x.ttf", b"this is not a font at all")
        with self.assertRaises(fonts.FontError):
            fonts.read_info(path)

    def test_collection_first_face(self):
        face = build_font(family="Collected")
        header = struct.pack(">4sIII", b"ttcf", 0x00010000, 1, 16)
        # the face's table offsets are relative to the file: shift them by the header
        count = struct.unpack_from(">H", face, 4)[0]
        shifted = bytearray(face)
        for i in range(count):
            at = 12 + 16 * i + 8
            struct.pack_into(">I", shifted, at, struct.unpack_from(">I", face, at)[0] + 16)
        path = self.write("c.ttc", header + bytes(shifted))
        self.assertEqual(fonts.read_info(path).family, "Collected")

    def test_dict_round_trip(self):
        path = self.write("t.ttf", build_font(family="Round"))
        info = fonts.read_info(path)
        again = fonts.FontInfo.from_dict(path, info.to_dict())
        self.assertEqual(again.family, "Round")
        self.assertEqual(again.ft_height, info.ft_height)
        self.assertEqual(again.advance("A"), info.advance("A"))


class CatalogTests(FontFolder):
    def make_family(self):
        self.write("fam/R.ttf", build_font(family="Fam", style="Regular"))
        self.write("fam/B.ttf", build_font(family="Fam", style="Bold", bold=True))
        self.write("fam/I.ttf", build_font(family="Fam", style="Italic", italic=True))
        self.write("solo/S.ttf", build_font(family="Solo", style="Regular"))
        self.write("solo/readme.txt", b"not a font")
        self.write("solo/broken.ttf", b"broken")

    def test_scan_lists_families(self):
        self.make_family()
        cat = fonts.scan([self.dir])
        self.assertEqual(cat.families(), ["Fam", "Solo"])
        self.assertEqual(len(cat), 4)

    def test_face_for_styles(self):
        self.make_family()
        cat = fonts.scan([self.dir])
        info, make_bold, make_italic = cat.face_for("Fam", bold=True)
        self.assertTrue(info.path.endswith("B.ttf"))
        self.assertEqual((make_bold, make_italic), (False, False))
        # no Bold Italic face: the bold one, slanted by SciForge
        info, make_bold, make_italic = cat.face_for("fam", bold=True, italic=True)
        self.assertTrue(info.path.endswith("B.ttf"))
        self.assertEqual((make_bold, make_italic), (False, True))
        # a family with one face: everything made up from it
        info, make_bold, make_italic = cat.face_for("Solo", bold=True, italic=True)
        self.assertTrue(info.path.endswith("S.ttf"))
        self.assertEqual((make_bold, make_italic), (True, True))
        self.assertIsNone(cat.face_for("Nope"))

    def test_default_family_order(self):
        self.make_family()
        cat = fonts.scan([self.dir])
        self.assertEqual(cat.default_family(("Missing", "Solo", "Fam")), "Solo")
        self.assertEqual(cat.default_family(("Missing",)), "Fam")  # first by name
        self.assertIsNone(fonts.Catalog([]).default_family())

    def test_cache_skips_unchanged_files(self):
        self.make_family()
        cache = os.path.join(self.dir, "cache", "fonts.json")
        first = fonts.scan([os.path.join(self.dir, "fam")], cache)
        self.assertEqual(len(first), 3)
        with open(cache, encoding="utf-8") as handle:
            data = json.load(handle)
        self.assertEqual(len(data), 3)
        # a cached entry is used as is: a changed family name in the cache shows up
        key = sorted(data)[0]
        data[key]["info"]["family"] = "FromCache"
        with open(cache, "w", encoding="utf-8") as handle:
            json.dump(data, handle)
        second = fonts.scan([os.path.join(self.dir, "fam")], cache)
        self.assertIn("FromCache", second.families())

    def test_file_family(self):
        self.make_family()
        cat = fonts.scan([self.dir])
        path = os.path.join(self.dir, "solo", "S.ttf")
        self.assertEqual(cat.file_family(path), "Solo")
        self.assertIsNone(cat.file_family(os.path.join(self.dir, "x.ttf")))


class SystemDirTests(unittest.TestCase):
    def test_windows_folders(self):
        base = tempfile.mkdtemp()
        try:
            os.makedirs(os.path.join(base, "Win", "Fonts"))
            os.makedirs(os.path.join(base, "Local", "Microsoft", "Windows", "Fonts"))
            env = {"WINDIR": os.path.join(base, "Win"), "LOCALAPPDATA": os.path.join(base, "Local")}
            dirs = fonts.system_dirs("win32", env, home=base)
            self.assertEqual(
                dirs,
                [
                    os.path.join(base, "Win", "Fonts"),
                    os.path.join(base, "Local", "Microsoft", "Windows", "Fonts"),
                ],
            )
        finally:
            shutil.rmtree(base, ignore_errors=True)

    def test_linux_folders(self):
        base = tempfile.mkdtemp()
        try:
            os.makedirs(os.path.join(base, ".local", "share", "fonts"))
            os.makedirs(os.path.join(base, "data", "fonts"))
            env = {"XDG_DATA_DIRS": os.path.join(base, "data")}
            dirs = fonts.system_dirs("linux", env, home=base)
            self.assertIn(os.path.join(base, ".local", "share", "fonts"), dirs)
            self.assertIn(os.path.join(base, "data", "fonts"), dirs)
            self.assertNotIn(os.path.join(base, ".fonts"), dirs)  # missing folders left out
        finally:
            shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
