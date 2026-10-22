# SPDX-License-Identifier: LGPL-2.1-or-later
"""A TrueType font embedded in a PDF as a subset (pure Python, no FreeCAD, no Qt; unit
tested in SciForgeTests/unit/test_drawing_pdf_core.py).

The searchable text SciForge adds to a drawing's PDF (drawing_pdf_core.py) is written
with osifont, the ISO 3098 lettering font FreeCAD ships for TechDraw. Only the glyphs the
text uses are kept (the others are emptied, glyph numbers unchanged, so a character's
code in the PDF is its glyph number: Identity-H with an identity CIDToGIDMap), and a
ToUnicode map says which character each glyph is, which is what makes the text
searchable and copyable.

A font's licence is respected: its OS/2 fsType says whether it may be embedded at all
(restricted licence or bitmap only: it is refused, FontRefused) and whether it may be
cut down to a subset (no subsetting: the whole font is embedded).
"""

import hashlib
import struct
import zlib

from .drawing_pdf_objects import HexString, Name, String


class FontError(ValueError):
    """A font file this module cannot read."""


class FontRefused(FontError):
    """The font's licence does not allow embedding it in a document."""


def _u16(data, at):
    return struct.unpack_from(">H", data, at)[0]


def _i16(data, at):
    return struct.unpack_from(">h", data, at)[0]


def _u32(data, at):
    return struct.unpack_from(">I", data, at)[0]


def _checksum(data):
    data = data + b"\0" * (-len(data) % 4)
    total = 0
    for (value,) in struct.iter_unpack(">I", data):
        total = (total + value) & 0xFFFFFFFF
    return total


class TrueType:
    """The parts of a TrueType font a PDF needs: metrics, the character map, glyphs."""

    def __init__(self, data):
        if len(data) < 12:
            raise FontError("This font file is too short.")
        version = data[:4]
        if version not in (b"\x00\x01\x00\x00", b"true"):
            raise FontError("This is not a TrueType font (OpenType CFF and collections are not read).")
        self.data = data
        count = _u16(data, 4)
        self.tables = {}
        for i in range(count):
            at = 12 + 16 * i
            tag = data[at : at + 4].decode("latin-1")
            offset, length = _u32(data, at + 8), _u32(data, at + 12)
            if offset + length > len(data):
                raise FontError("The font's %s table is cut short." % tag)
            self.tables[tag] = (offset, length)
        for need in ("head", "hhea", "maxp", "hmtx", "loca", "glyf", "cmap"):
            if need not in self.tables:
                raise FontError("The font has no %s table." % need)
        head = self.table("head")
        self.units = _u16(head, 18) or 1000
        self.bbox = [_i16(head, 36), _i16(head, 38), _i16(head, 40), _i16(head, 42)]
        self.long_loca = _i16(head, 50) == 1
        hhea = self.table("hhea")
        self.ascent = _i16(hhea, 4)
        self.descent = _i16(hhea, 6)
        metrics = _u16(hhea, 34)
        self.num_glyphs = _u16(self.table("maxp"), 4)
        hmtx = self.table("hmtx")
        self.advances = []
        last = 0
        for gid in range(self.num_glyphs):
            if gid < metrics:
                last = _u16(hmtx, 4 * gid)
            self.advances.append(last)
        self.cap_height = self.ascent
        self.fs_type = 0
        self.weight = 400
        if "OS/2" in self.tables:
            os2 = self.table("OS/2")
            if len(os2) >= 10:
                self.weight = _u16(os2, 4)
                self.fs_type = _u16(os2, 8)
            if len(os2) >= 90 and _u16(os2, 0) >= 2:
                self.cap_height = _i16(os2, 88) or self.ascent
        self.italic_angle = 0.0
        if "post" in self.tables:
            post = self.table("post")
            if len(post) >= 8:
                self.italic_angle = struct.unpack_from(">i", post, 4)[0] / 65536.0
        self.cmap = self._read_cmap()
        self.name = self._read_name() or "SciForgeFont"

    def table(self, tag):
        offset, length = self.tables[tag]
        return self.data[offset : offset + length]

    # -- the character map
    def _read_cmap(self):
        cmap = self.table("cmap")
        best = None
        for i in range(_u16(cmap, 2)):
            at = 4 + 8 * i
            platform, encoding, offset = _u16(cmap, at), _u16(cmap, at + 2), _u32(cmap, at + 4)
            fmt = _u16(cmap, offset)
            rank = {(3, 10): 4, (0, 4): 3, (0, 6): 3, (3, 1): 2, (0, 3): 1}.get((platform, encoding))
            if rank is None or fmt not in (4, 12):
                continue
            if best is None or rank > best[0]:
                best = (rank, offset, fmt)
        if best is None:
            raise FontError("The font has no Unicode character map.")
        _rank, offset, fmt = best
        out = {}
        if fmt == 4:
            segs = _u16(cmap, offset + 6) // 2
            ends = offset + 14
            starts = ends + 2 * segs + 2
            deltas = starts + 2 * segs
            ranges = deltas + 2 * segs
            for s in range(segs):
                end, start = _u16(cmap, ends + 2 * s), _u16(cmap, starts + 2 * s)
                delta, rng = _i16(cmap, deltas + 2 * s), _u16(cmap, ranges + 2 * s)
                for code in range(start, min(end, 0xFFFE) + 1):
                    if rng == 0:
                        gid = (code + delta) & 0xFFFF
                    else:
                        at = ranges + 2 * s + rng + 2 * (code - start)
                        gid = _u16(cmap, at) if at + 2 <= len(cmap) else 0
                        if gid:
                            gid = (gid + delta) & 0xFFFF
                    if gid:
                        out[code] = gid
        else:
            groups = _u32(cmap, offset + 12)
            for g in range(groups):
                at = offset + 16 + 12 * g
                start, end, first = _u32(cmap, at), _u32(cmap, at + 4), _u32(cmap, at + 8)
                for code in range(start, min(end, 0x10FFFF) + 1):
                    out[code] = first + code - start
        return out

    def _read_name(self):
        if "name" not in self.tables:
            return None
        name = self.table("name")
        count, strings = _u16(name, 2), _u16(name, 4)
        found = {}
        for i in range(count):
            at = 6 + 12 * i
            platform, encoding, _lang, name_id = (_u16(name, at + 2 * k) for k in range(4))
            length, offset = _u16(name, at + 8), _u16(name, at + 10)
            if name_id != 6:
                continue
            raw = name[strings + offset : strings + offset + length]
            try:
                text = raw.decode("utf-16-be") if platform in (0, 3) else raw.decode("latin-1")
            except UnicodeDecodeError:
                continue
            found[(platform, encoding)] = text
        for key in ((3, 1), (1, 0), (0, 3)):
            if key in found:
                clean = "".join(c for c in found[key] if c.isalnum() or c in "-_")
                return clean or None
        return None

    # -- glyphs
    def glyph(self, char):
        """The glyph number of a character (0, the missing glyph, when the font has none)."""
        return self.cmap.get(ord(char), 0)

    def advance(self, gid):
        """A glyph's advance in thousandths of the font size."""
        if 0 <= gid < len(self.advances):
            return self.advances[gid] * 1000.0 / self.units
        return 0.0

    def width(self, text):
        """The width of `text` in thousandths of the font size."""
        return sum(self.advance(self.glyph(c)) for c in text)

    def _offsets(self):
        loca = self.table("loca")
        if self.long_loca:
            return [_u32(loca, 4 * i) for i in range(self.num_glyphs + 1)]
        return [2 * _u16(loca, 2 * i) for i in range(self.num_glyphs + 1)]

    def _components(self, data):
        """Glyph numbers a composite glyph is made of."""
        found = []
        if len(data) < 10 or _i16(data, 0) >= 0:
            return found
        at = 10
        while at + 4 <= len(data):
            flags, gid = _u16(data, at), _u16(data, at + 2)
            found.append(gid)
            at += 4 + (4 if flags & 0x0001 else 2)
            if flags & 0x0008:
                at += 2
            elif flags & 0x0040:
                at += 4
            elif flags & 0x0080:
                at += 8
            if not flags & 0x0020:
                break
        return found

    def check_licence(self):
        """FontRefused when the font's licence (OS/2 fsType) forbids embedding it."""
        if self.fs_type & 0x000F == 0x0002:
            raise FontRefused("The font's licence does not allow embedding it (restricted).")
        if self.fs_type & 0x0200:
            raise FontRefused("The font's licence allows only bitmaps to be embedded.")

    def subset(self, gids):
        """A font file with only the glyphs `gids` (and what they are made of) kept, glyph
        numbers unchanged. The whole font when its licence forbids subsetting."""
        self.check_licence()
        if self.fs_type & 0x0100:
            return self.data
        offsets = self._offsets()
        glyf = self.table("glyf")
        keep = {0}
        todo = [g for g in gids if 0 <= g < self.num_glyphs]
        while todo:
            gid = todo.pop()
            if gid in keep and gid != 0:
                continue
            keep.add(gid)
            for part in self._components(glyf[offsets[gid] : offsets[gid + 1]]):
                if part not in keep and part < self.num_glyphs:
                    todo.append(part)
        new_glyf = bytearray()
        new_loca = []
        for gid in range(self.num_glyphs):
            new_loca.append(len(new_glyf))
            if gid in keep:
                new_glyf += glyf[offsets[gid] : offsets[gid + 1]]
                new_glyf += b"\0" * (-len(new_glyf) % 4)
        new_loca.append(len(new_glyf))
        head = bytearray(self.table("head"))
        struct.pack_into(">I", head, 8, 0)  # checkSumAdjustment, set below
        struct.pack_into(">h", head, 50, 1)  # long offsets
        tables = {
            "head": bytes(head),
            "glyf": bytes(new_glyf),
            "loca": b"".join(struct.pack(">I", o) for o in new_loca),
        }
        for tag in ("cmap", "hhea", "maxp", "hmtx", "cvt ", "fpgm", "prep", "OS/2", "post", "name"):
            if tag in self.tables:
                tables[tag] = self.table(tag)
        return _assemble(tables)


def _assemble(tables):
    tags = sorted(tables)
    count = len(tags)
    power = 1
    while power * 2 <= count:
        power *= 2
    header = struct.pack(">IHHHH", 0x00010000, count, power * 16, power.bit_length() - 1,
                         count * 16 - power * 16)
    offset = 12 + 16 * count
    records = []
    body = bytearray()
    for tag in tags:
        data = tables[tag]
        records.append(struct.pack(">4sIII", tag.encode("latin-1"), _checksum(data),
                                   offset + len(body), len(data)))
        body += data + b"\0" * (-len(data) % 4)
    font = bytearray(header + b"".join(records) + body)
    head_at = 12 + 16 * count + sum(
        len(tables[t]) + (-len(tables[t]) % 4) for t in tags[: tags.index("head")]
    )
    struct.pack_into(">I", font, head_at + 8, (0xB1B0AFBA - _checksum(bytes(font))) & 0xFFFFFFFF)
    return bytes(font)


# ------------------------------------------------------------------ PDF objects
def _to_unicode(pairs):
    """A ToUnicode CMap for [(gid, text)]."""
    lines = [
        b"/CIDInit /ProcSet findresource begin",
        b"12 dict begin",
        b"begincmap",
        b"/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def",
        b"/CMapName /Adobe-Identity-UCS def",
        b"/CMapType 2 def",
        b"1 begincodespacerange",
        b"<0000> <FFFF>",
        b"endcodespacerange",
    ]
    for start in range(0, len(pairs), 100):
        chunk = pairs[start : start + 100]
        lines.append(b"%d beginbfchar" % len(chunk))
        for gid, text in chunk:
            lines.append(b"<%04X> <%s>" % (gid, text.encode("utf-16-be").hex().upper().encode("ascii")))
        lines.append(b"endbfchar")
    lines += [b"endcmap", b"CMapName currentdict /CMapResource defineresource pop", b"end", b"end"]
    return b"\n".join(lines) + b"\n"


class EmbeddedFont:
    """A TrueType font being used in a PDF: collects the characters written with it, then
    becomes the PDF objects (a Type0 font over a CIDFontType2 with its subset)."""

    def __init__(self, font):
        self.font = font
        self.used = {}  # gid -> character

    def encode(self, text):
        """The string to show `text` with this font (two bytes per glyph)."""
        out = bytearray()
        for char in text:
            gid = self.font.glyph(char)
            if gid and gid not in self.used:
                self.used[gid] = char
            out += struct.pack(">H", gid)
        return HexString(bytes(out))

    def width(self, text):
        return self.font.width(text)

    def objects(self, document):
        """Add the font's objects to a drawing_pdf_objects.Document; returns the Ref of
        the Type0 font."""
        font = self.font
        gids = sorted(self.used)
        program = font.subset(gids)
        tag = "".join(
            chr(65 + b % 26) for b in hashlib.sha1(repr(gids).encode("ascii")).digest()[:6]
        )
        base = Name(("%s+%s" % (tag, font.name)).encode("ascii", "replace"))
        k = 1000.0 / font.units
        stream = zlib.compress(program)
        program_ref = document.add(
            {b"Length1": len(program), b"Filter": Name(b"FlateDecode")}, stream
        )
        descriptor = document.add(
            {
                b"Type": Name(b"FontDescriptor"),
                b"FontName": base,
                b"Flags": 4,
                b"FontBBox": [round(v * k) for v in font.bbox],
                b"ItalicAngle": font.italic_angle,
                b"Ascent": round(font.ascent * k),
                b"Descent": round(font.descent * k),
                b"CapHeight": round(font.cap_height * k),
                b"StemV": 80,
                b"FontFile2": program_ref,
            }
        )
        widths = []
        for gid in gids:
            widths += [gid, [round(font.advance(gid), 3)]]
        cid = document.add(
            {
                b"Type": Name(b"Font"),
                b"Subtype": Name(b"CIDFontType2"),
                b"BaseFont": base,
                b"CIDSystemInfo": {
                    b"Registry": String(b"Adobe"),
                    b"Ordering": String(b"Identity"),
                    b"Supplement": 0,
                },
                b"FontDescriptor": descriptor,
                b"CIDToGIDMap": Name(b"Identity"),
                b"DW": round(font.advance(0)),
                b"W": widths,
            }
        )
        cmap = _to_unicode([(gid, self.used[gid]) for gid in gids])
        to_unicode = document.add({b"Filter": Name(b"FlateDecode")}, zlib.compress(cmap))
        return document.add(
            {
                b"Type": Name(b"Font"),
                b"Subtype": Name(b"Type0"),
                b"BaseFont": base,
                b"Encoding": Name(b"Identity-H"),
                b"DescendantFonts": [cid],
                b"ToUnicode": to_unicode,
            }
        )


class StandardFont:
    """Helvetica, one of the fonts every PDF viewer has (used when no TrueType font can be
    embedded); WinAnsi encoding, so characters outside it become '?'."""

    # Helvetica advances (thousandths) for ASCII 32..126
    _WIDTHS = [
        278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278,
        556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 278, 278, 584, 584, 584, 556,
        1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778,
        667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556,
        333, 556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556,
        556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584,
    ]

    def encode(self, text):
        return String(text.encode("cp1252", "replace"))

    def width(self, text):
        total = 0
        for c in text:
            code = ord(c)
            total += self._WIDTHS[code - 32] if 32 <= code <= 126 else 556
        return float(total)

    def objects(self, document):
        return document.add(
            {
                b"Type": Name(b"Font"),
                b"Subtype": Name(b"Type1"),
                b"BaseFont": Name(b"Helvetica"),
                b"Encoding": Name(b"WinAnsiEncoding"),
            }
        )


def load(path):
    """An EmbeddedFont for the TrueType file at `path`, or a StandardFont (and the reason)
    when it cannot be read or its licence forbids embedding it."""
    try:
        with open(path, "rb") as handle:
            font = TrueType(handle.read())
        font.check_licence()
        return EmbeddedFont(font), None
    except (OSError, FontError, struct.error, IndexError) as exc:
        return StandardFont(), str(exc)
