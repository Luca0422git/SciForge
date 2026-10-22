# SPDX-License-Identifier: LGPL-2.1-or-later
"""A small PDF reader and writer for the PDFs SciForge makes from its drawings (pure
Python, no FreeCAD, no Qt; unit tested in SciForgeTests/unit/test_drawing_pdf_core.py).

TechDraw prints a sheet with Qt's PDF writer: a plain cross-reference table, no object
streams, Flate-compressed page contents. drawing_pdf_core.py rewrites such a file to add
layers, searchable text, links and metadata; this module gives it the pieces: PDF values
as Python values (Name, String, Ref, dict, list, numbers), the operations of a content
stream with their exact bytes, and a whole file as {object number: (value, stream)}.

Only what those files use is read. Anything else (an encrypted file, a compressed
cross-reference stream from another writer) raises PdfError with a sentence that says
why, and the caller keeps the file TechDraw wrote.
"""

import re
import zlib


class PdfError(ValueError):
    """A PDF this reader cannot handle, with a sentence that says why."""


class Name(bytes):
    """A PDF name (/Type), without its slash."""

    def __repr__(self):
        return "Name(%r)" % bytes(self)


class String(bytes):
    """A PDF string, its bytes decoded (escapes resolved); `hex` keeps how it was written."""

    hex = False

    def __repr__(self):
        return "String(%r)" % bytes(self)


class HexString(String):
    hex = True


class Ref:
    """An indirect reference (12 0 R)."""

    __slots__ = ("num", "gen")

    def __init__(self, num, gen=0):
        self.num = int(num)
        self.gen = int(gen)

    def __eq__(self, other):
        return isinstance(other, Ref) and other.num == self.num and other.gen == self.gen

    def __hash__(self):
        return hash((self.num, self.gen))

    def __repr__(self):
        return "Ref(%d)" % self.num


class Keyword(bytes):
    """A bare word that is not a value (an operator in a content stream, `obj`, `R`)."""


# ------------------------------------------------------------------ tokens
_WHITE = b"\x00\t\n\x0c\r "
_TOKEN = re.compile(
    rb"(?P<ws>[\x00\t\n\x0c\r ]+)"
    rb"|(?P<comment>%[^\r\n]*)"
    rb"|(?P<dopen><<)|(?P<dclose>>>)"
    rb"|(?P<hex><[0-9A-Fa-f\x00\t\n\x0c\r ]*>)"
    rb"|(?P<aopen>\[)|(?P<aclose>\])"
    rb"|(?P<bopen>\{)|(?P<bclose>\})"
    rb"|(?P<lit>\()"
    rb"|(?P<name>/[^\x00\t\n\x0c\r ()<>\[\]{}/%]*)"
    rb"|(?P<word>[^\x00\t\n\x0c\r ()<>\[\]{}/%]+)"
)
_NUMBER = re.compile(rb"[+-]?(?:\d+\.?\d*|\.\d+)\Z")
_NAME_ESCAPE = re.compile(rb"#([0-9A-Fa-f]{2})")
_ESCAPES = {
    ord("n"): b"\n",
    ord("r"): b"\r",
    ord("t"): b"\t",
    ord("b"): b"\b",
    ord("f"): b"\f",
    ord("("): b"(",
    ord(")"): b")",
    ord("\\"): b"\\",
}


def _literal(data, pos):
    """(String, end) of the literal string whose '(' is at `pos`."""
    depth = 0
    out = bytearray()
    i = pos + 1
    n = len(data)
    while i < n:
        c = data[i]
        if c == 0x5C:  # backslash
            i += 1
            if i >= n:
                break
            e = data[i]
            if e in _ESCAPES:
                out += _ESCAPES[e]
            elif 0x30 <= e <= 0x37:
                digits = bytes([e])
                while len(digits) < 3 and i + 1 < n and 0x30 <= data[i + 1] <= 0x37:
                    i += 1
                    digits += bytes([data[i]])
                out.append(int(digits, 8) & 0xFF)
            elif e == 0x0D:  # a line continuation
                if i + 1 < n and data[i + 1] == 0x0A:
                    i += 1
            elif e != 0x0A:
                out.append(e)
        elif c == 0x28:
            depth += 1
            out.append(c)
        elif c == 0x29:
            if depth == 0:
                return String(bytes(out)), i + 1
            depth -= 1
            out.append(c)
        else:
            out.append(c)
        i += 1
    raise PdfError("A string in this PDF has no end.")


def tokens(data, pos=0, end=None):
    """(kind, value, start, stop) for every token of `data` from `pos`: kind is one of
    num, name, str, hex, word, <<, >>, [, ], {, }."""
    end = len(data) if end is None else end
    while pos < end:
        match = _TOKEN.match(data, pos)
        if match is None:
            raise PdfError("This PDF has a byte that cannot start anything (offset %d)." % pos)
        kind = match.lastgroup
        stop = match.end()
        if kind in ("ws", "comment"):
            pos = stop
            continue
        if kind == "lit":
            value, stop = _literal(data, pos)
            yield "str", value, pos, stop
        elif kind == "hex":
            digits = re.sub(rb"[\x00\t\n\x0c\r ]", b"", match.group()[1:-1])
            if len(digits) % 2:
                digits += b"0"
            yield "hex", HexString(bytes.fromhex(digits.decode("ascii"))), pos, stop
        elif kind == "name":
            raw = match.group()[1:]
            yield "name", Name(_NAME_ESCAPE.sub(lambda m: bytes([int(m.group(1), 16)]), raw)), pos, stop
        elif kind == "word":
            word = match.group()
            if _NUMBER.match(word):
                value = float(word) if (b"." in word) else int(word)
                yield "num", value, pos, stop
            else:
                yield "word", Keyword(word), pos, stop
        else:
            yield {"dopen": "<<", "dclose": ">>", "aopen": "[", "aclose": "]"}.get(
                kind, "{" if kind == "bopen" else "}"
            ), None, pos, stop
        pos = stop


class _Reader:
    """Values from a token stream (arrays, dictionaries and references assembled)."""

    def __init__(self, data, pos=0, end=None):
        self.data = data
        self.gen = tokens(data, pos, end)
        self.ahead = []

    def next(self):
        if self.ahead:
            return self.ahead.pop()
        return next(self.gen, None)

    def push(self, tok):
        self.ahead.append(tok)

    def value(self, tok=None):
        """The value starting at `tok` (or the next token); None at the end."""
        tok = tok or self.next()
        if tok is None:
            return None
        kind, value, start, stop = tok
        if kind == "num":
            if isinstance(value, int) and value >= 0:
                # "12 0 R" is a reference
                second = self.next()
                if second is not None and second[0] == "num" and isinstance(second[1], int):
                    third = self.next()
                    if third is not None and third[0] == "word" and third[1] == b"R":
                        return Ref(value, second[1])
                    if third is not None:
                        self.push(third)
                    self.push(second)
                elif second is not None:
                    self.push(second)
            return value
        if kind in ("name", "str", "hex"):
            return value
        if kind == "[":
            items = []
            while True:
                t = self.next()
                if t is None:
                    raise PdfError("An array in this PDF has no end.")
                if t[0] == "]":
                    return items
                items.append(self.value(t))
        if kind == "<<":
            out = {}
            while True:
                t = self.next()
                if t is None:
                    raise PdfError("A dictionary in this PDF has no end.")
                if t[0] == ">>":
                    return out
                if t[0] != "name":
                    raise PdfError("A dictionary key in this PDF is not a name.")
                out[t[1]] = self.value()
        if kind == "word":
            if value == b"true":
                return True
            if value == b"false":
                return False
            if value == b"null":
                return None
            return value
        raise PdfError("Unexpected %s in this PDF." % kind)


def parse_value(data):
    """The first PDF value in `data` (bytes)."""
    return _Reader(data).value()


# ------------------------------------------------------------------ writing values
def _fmt_number(value):
    if isinstance(value, bool):
        return b"true" if value else b"false"
    if isinstance(value, int):
        return b"%d" % value
    text = ("%.6f" % value).rstrip("0").rstrip(".")
    return (text if text not in ("", "-0") else "0").encode("ascii")


_NAME_PLAIN = set(range(0x21, 0x7F)) - set(b"()<>[]{}/%#")


def serialize(value):
    """PDF bytes of a value."""
    if value is None:
        return b"null"
    if isinstance(value, Ref):
        return b"%d %d R" % (value.num, value.gen)
    if isinstance(value, Name):
        return b"/" + b"".join(bytes([c]) if c in _NAME_PLAIN else b"#%02X" % c for c in value)
    if isinstance(value, String):
        if value.hex:
            return b"<" + bytes(value).hex().upper().encode("ascii") + b">"
        return b"(" + escape_string(bytes(value)) + b")"
    if isinstance(value, Keyword):
        return bytes(value)
    if isinstance(value, (bool, int, float)):
        return _fmt_number(value)
    if isinstance(value, (list, tuple)):
        return b"[" + b" ".join(serialize(v) for v in value) + b"]"
    if isinstance(value, dict):
        parts = [b"<<"]
        for key, item in value.items():
            parts.append(serialize(Name(key)) + b" " + serialize(item))
        parts.append(b">>")
        return b"\n".join(parts)
    if isinstance(value, bytes):
        return b"(" + escape_string(value) + b")"
    raise PdfError("Cannot write %r into a PDF." % (value,))


def escape_string(raw):
    out = bytearray()
    for c in raw:
        if c in (0x28, 0x29, 0x5C):
            out += b"\\" + bytes([c])
        elif c == 0x0D:
            out += b"\\r"
        elif c == 0x0A:
            out += b"\\n"
        else:
            out.append(c)
    return bytes(out)


def text_string(text):
    """A PDF text string (title, author...): plain when ASCII, else UTF-16 with its mark."""
    try:
        raw = text.encode("ascii")
        if all(32 <= c < 127 for c in raw):
            return String(raw)
    except UnicodeEncodeError:
        pass
    return String(b"\xfe\xff" + text.encode("utf-16-be"))


def decode_text_string(value):
    raw = bytes(value or b"")
    if raw.startswith(b"\xfe\xff"):
        return raw[2:].decode("utf-16-be", "replace")
    return raw.decode("latin-1")


# ------------------------------------------------------------------ content streams
class Op:
    """One operation of a content stream: its operator, operands and exact bytes."""

    __slots__ = ("op", "args", "start", "stop")

    def __init__(self, op, args, start, stop):
        self.op = op
        self.args = args
        self.start = start
        self.stop = stop

    def __repr__(self):
        return "Op(%r, %r)" % (self.op, self.args)


_INLINE_END = re.compile(rb"[\x00\t\n\x0c\r ]EI(?=[\x00\t\n\x0c\r ]|\Z)")


def operations(content):
    """Every operation of a content stream, in order (inline images included whole)."""
    reader = _Reader(content)
    ops = []
    args = []
    start = None
    while True:
        tok = reader.next()
        if tok is None:
            break
        if start is None:
            start = tok[2]
        if tok[0] == "word" and tok[1] not in (b"true", b"false", b"null"):
            op = bytes(tok[1])
            stop = tok[3]
            if op == b"BI":
                # an inline image: key/value pairs, ID, raw data, EI
                while True:
                    t = reader.next()
                    if t is None:
                        raise PdfError("An inline image in this PDF has no data.")
                    if t[0] == "word" and t[1] == b"ID":
                        break
                found = _INLINE_END.search(content, t[3] + 1)
                if found is None:
                    raise PdfError("An inline image in this PDF has no end.")
                stop = found.end()
                reader = _Reader(content, stop)
                ops.append(Op(b"BI", [], start, stop))
            else:
                ops.append(Op(op, args, start, stop))
            args = []
            start = None
        else:
            args.append(reader.value(tok))
    return ops


# ------------------------------------------------------------------ files
_OBJ_HEAD = re.compile(rb"(\d+)\s+(\d+)\s+obj\b")
_STREAM_KW = re.compile(rb"stream(\r\n|\n|\r)")


def _xref_offsets(data):
    """{object number: offset} from the classic cross-reference tables (newest first, so
    an incrementally updated file reads right), and the newest trailer's bytes."""
    match = None
    for match in re.finditer(rb"startxref\s+(\d+)", data[-4096:]):
        pass
    if match is None:
        raise PdfError("This PDF has no cross-reference table (startxref missing).")
    pos = int(match.group(1))
    offsets = {}
    trailer_bytes = None
    seen = set()
    while pos is not None and pos not in seen:
        seen.add(pos)
        if data[pos : pos + 4] != b"xref":
            raise PdfError("This PDF uses a cross-reference stream: it cannot be rewritten here.")
        at = pos + 4
        sections = re.compile(rb"\s*(\d+)\s+(\d+)[ \t]*(?:\r\n|\n|\r)")
        while True:
            head = sections.match(data, at)
            if head is None:
                break
            first, count = int(head.group(1)), int(head.group(2))
            at = head.end()
            for k in range(count):
                entry = data[at : at + 20]
                parts = entry.split()
                if len(parts) >= 3 and parts[2][:1] == b"n" and first + k not in offsets:
                    offsets[first + k] = int(parts[0])
                at += 20
        trailer_at = data.find(b"trailer", at - 1)
        if trailer_at < 0:
            raise PdfError("This PDF has no trailer.")
        reader = _Reader(data, trailer_at + 7)
        trailer = reader.value()
        if trailer_bytes is None:
            trailer_bytes = trailer
        prev = trailer.get(b"Prev") if isinstance(trailer, dict) else None
        pos = int(prev) if isinstance(prev, int) else None
    return offsets, trailer_bytes


class Document:
    """A whole PDF: objects {number: value}, streams {number: raw stream bytes}, trailer."""

    def __init__(self, objects, streams, trailer, version=b"1.4"):
        self.objects = objects
        self.streams = streams
        self.trailer = trailer
        self.version = version

    # -- reading
    def get(self, value):
        """A value with references followed."""
        seen = 0
        while isinstance(value, Ref) and seen < 32:
            value = self.objects.get(value.num)
            seen += 1
        return value

    def stream_data(self, num):
        """The decoded data of stream object `num` (Flate only); None when it cannot."""
        raw = self.streams.get(num)
        if raw is None:
            return None
        head = self.objects.get(num) or {}
        filters = self.get(head.get(b"Filter"))
        if filters is None:
            return raw
        if isinstance(filters, list):
            filters = [self.get(f) for f in filters]
        else:
            filters = [filters]
        data = raw
        for flt in filters:
            if flt == b"FlateDecode" and not self.get(head.get(b"DecodeParms")):
                try:
                    data = zlib.decompress(data)
                except zlib.error:
                    data = zlib.decompressobj().decompress(data)
            else:
                return None
        return data

    def pages(self):
        """Page object numbers, in order."""
        root = self.get(self.trailer.get(b"Root"))
        if not isinstance(root, dict):
            raise PdfError("This PDF has no catalogue.")
        found = []

        def walk(ref, depth=0):
            if depth > 32:
                return
            node = self.get(ref)
            if not isinstance(node, dict):
                return
            if node.get(b"Type") == b"Pages" or b"Kids" in node:
                for kid in self.get(node.get(b"Kids")) or []:
                    walk(kid, depth + 1)
            elif isinstance(ref, Ref):
                found.append(ref.num)

        walk(root.get(b"Pages"))
        return found

    def add(self, value, stream=None):
        """A new object; returns its Ref."""
        num = max(self.objects) + 1 if self.objects else 1
        self.objects[num] = value
        if stream is not None:
            self.streams[num] = stream
        return Ref(num)

    # -- writing
    def write(self, version=None):
        version = version or self.version
        parts = [b"%PDF-" + version + b"\n%\xe2\xe3\xcf\xd3\n"]
        pos = len(parts[0])
        offsets = {}
        for num in sorted(self.objects):
            value = self.objects[num]
            stream = self.streams.get(num)
            if stream is not None:
                value = dict(value)
                value[b"Length"] = len(stream)
                body = serialize(value) + b"\nstream\n" + stream + b"\nendstream"
            else:
                body = serialize(value)
            chunk = b"%d 0 obj\n" % num + body + b"\nendobj\n"
            offsets[num] = pos
            parts.append(chunk)
            pos += len(chunk)
        size = max(self.objects) + 1 if self.objects else 1
        xref = [b"xref\n0 %d\n" % size, b"0000000000 65535 f \n"]
        for num in range(1, size):
            if num in offsets:
                xref.append(b"%010d 00000 n \n" % offsets[num])
            else:
                xref.append(b"0000000000 65535 f \n")
        parts.append(b"".join(xref))
        trailer = {k: v for k, v in self.trailer.items() if k not in (b"Prev", b"XRefStm")}
        trailer[b"Size"] = size
        parts.append(b"trailer\n" + serialize(trailer) + b"\nstartxref\n%d\n%%%%EOF\n" % pos)
        return b"".join(parts)


def read(data):
    """A Document from PDF bytes (classic cross-reference table only)."""
    if not data.startswith(b"%PDF-"):
        raise PdfError("This is not a PDF file.")
    version = data[5:8]
    offsets, trailer = _xref_offsets(data)
    if not isinstance(trailer, dict):
        raise PdfError("This PDF's trailer could not be read.")
    if trailer.get(b"Encrypt") is not None:
        raise PdfError("This PDF is encrypted.")
    objects, streams = {}, {}
    pending_lengths = {}
    for num, offset in offsets.items():
        head = _OBJ_HEAD.match(data, offset)
        if head is None or int(head.group(1)) != num:
            raise PdfError("Object %d is not where the PDF's table says." % num)
        reader = _Reader(data, head.end())
        value = reader.value()
        objects[num] = value
        tok = reader.next()
        if isinstance(value, dict) and tok is not None and tok[0] == "word" and tok[1] == b"stream":
            kw = _STREAM_KW.match(data, tok[2])
            if kw is None:
                raise PdfError("Object %d's stream is not written as PDF wants." % num)
            begin = kw.end()
            pending_lengths[num] = (begin, value.get(b"Length"))
    for num, (begin, length) in pending_lengths.items():
        if isinstance(length, Ref):
            length = objects.get(length.num)
        stop = None
        if isinstance(length, int) and data[begin + length : begin + length + 32].lstrip(
            _WHITE
        ).startswith(b"endstream"):
            stop = begin + length
        if stop is None:
            stop = data.find(b"endstream", begin)
            if stop < 0:
                raise PdfError("Object %d's stream has no end." % num)
            if data[stop - 2 : stop] == b"\r\n":
                stop -= 2
            elif data[stop - 1 : stop] in (b"\n", b"\r"):
                stop -= 1
        streams[num] = data[begin:stop]
    return Document(objects, streams, trailer, version)
