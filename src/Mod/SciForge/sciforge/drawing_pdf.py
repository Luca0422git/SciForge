# SPDX-License-Identifier: LGPL-2.1-or-later
"""One PDF from several (Fusion's Export PDF writes every sheet of a drawing into one
file). Pure Python (no FreeCAD, no Qt), unit tested (SciForgeTests/unit/test_drawing_pdf.py).

TechDraw prints one sheet per PDF (Qt's PDF writer: PDF 1.4, a plain cross-reference
table, no object streams). The pages of several such files are put into one file: every
object is copied with its number shifted, the pages are listed in one new page tree and
the first file's catalogue points at it. Stream data is copied byte for byte. Files with
compressed cross-reference streams (other writers) are refused with a clear error.
"""

import re

_OBJ = re.compile(rb"(\d+)\s+(\d+)\s+obj\b")
_REF = re.compile(rb"(\d+)\s+0\s+R\b")
_STREAM = re.compile(rb">>\s*stream(\r\n|\n|\r)")


class PdfError(ValueError):
    """A PDF this merger cannot read, with a sentence that says why."""


def _xref_offsets(data):
    """{object number: byte offset} from the file's last cross-reference table."""
    tail = data[-2048:]
    match = re.search(rb"startxref\s+(\d+)", tail)
    if not match:
        raise PdfError("This PDF has no cross-reference table (startxref missing).")
    pos = int(match.group(1))
    if data[pos : pos + 4] != b"xref":
        raise PdfError("This PDF uses a cross-reference stream: it cannot be merged here.")
    offsets = {}
    lines = data[pos:].split(b"\n")
    i = 1
    while i < len(lines):
        line = lines[i].strip()
        if not line or line.startswith(b"trailer"):
            break
        parts = line.split()
        if len(parts) != 2:
            raise PdfError("This PDF's cross-reference table could not be read.")
        first, count = int(parts[0]), int(parts[1])
        for k in range(count):
            entry = lines[i + 1 + k].strip().split()
            if len(entry) >= 3 and entry[2] == b"n":
                offsets[first + k] = int(entry[0])
        i += count + 1
    trailer_at = data.find(b"trailer", pos)
    trailer = data[trailer_at : data.find(b"startxref", trailer_at)]
    return offsets, trailer, pos


def _objects(data):
    """{number: bytes of the object's body (between 'obj' and 'endobj')}, the trailer."""
    offsets, trailer, xref_pos = _xref_offsets(data)
    ordered = sorted(offsets.items(), key=lambda item: item[1])
    bodies = {}
    for index, (number, offset) in enumerate(ordered):
        end = ordered[index + 1][1] if index + 1 < len(ordered) else xref_pos
        chunk = data[offset:end]
        head = _OBJ.match(chunk)
        if head is None or int(head.group(1)) != number:
            raise PdfError("Object %d is not where the PDF's table says." % number)
        stop = chunk.rfind(b"endobj")
        if stop < 0:
            raise PdfError("Object %d has no end." % number)
        bodies[number] = chunk[head.end() : stop]
    return bodies, trailer


def _ref(trailer_or_dict, key):
    match = re.search(rb"/" + key + rb"\s+(\d+)\s+0\s+R", trailer_or_dict)
    return int(match.group(1)) if match else None


def _shift(body, offset):
    """Object references in a body moved by `offset` (stream data left alone)."""

    def renumber(text):
        return _REF.sub(lambda m: b"%d 0 R" % (int(m.group(1)) + offset), text)

    match = _STREAM.search(body)
    if match is None:
        return renumber(body)
    return renumber(body[: match.start()]) + body[match.start() :]


def _page_numbers(bodies, pages_number):
    """The page objects of a page tree, in order."""
    found = []
    body = bodies.get(pages_number, b"")
    kids = re.search(rb"/Kids\s*\[(.*?)\]", body, re.S)
    if not kids:
        return found
    for match in _REF.finditer(kids.group(1)):
        number = int(match.group(1))
        child = bodies.get(number, b"")
        if re.search(rb"/Type\s*/Pages\b", child):
            found += _page_numbers(bodies, number)
        else:
            found.append(number)
    return found


def page_count(data):
    bodies, trailer = _objects(data)
    root = _ref(trailer, b"Root")
    pages = _ref(bodies.get(root, b""), b"Pages")
    return len(_page_numbers(bodies, pages))


def merge(files):
    """One PDF (bytes) with every page of `files` (a list of PDF bytes), in order."""
    if not files:
        raise PdfError("No PDF to merge.")
    if len(files) == 1:
        return files[0]
    out_objects = {}
    page_refs = []
    offset = 0
    first_root = None
    info = None
    for index, data in enumerate(files):
        bodies, trailer = _objects(data)
        root = _ref(trailer, b"Root")
        pages = _ref(bodies.get(root, b""), b"Pages")
        if root is None or pages is None:
            raise PdfError("PDF %d has no page tree." % (index + 1))
        numbers = _page_numbers(bodies, pages)
        for number, body in bodies.items():
            out_objects[number + offset] = _shift(body, offset)
        page_refs += [n + offset for n in numbers]
        if index == 0:
            first_root = root
            info = _ref(trailer, b"Info")
        offset += max(bodies) + 1
    tree = offset  # the new page tree
    for number in page_refs:
        out_objects[number] = re.sub(
            rb"/Parent\s+\d+\s+0\s+R", b"/Parent %d 0 R" % tree, out_objects[number], count=1
        )
    out_objects[tree] = b"\n<<\n/Type /Pages\n/Kids [ %s ]\n/Count %d\n>>\n" % (
        b" ".join(b"%d 0 R" % n for n in page_refs),
        len(page_refs),
    )
    out_objects[first_root] = re.sub(
        rb"/Pages\s+\d+\s+0\s+R", b"/Pages %d 0 R" % tree, out_objects[first_root], count=1
    )
    size = tree + 1
    parts = [b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"]
    positions = {}
    pos = len(parts[0])
    for number in sorted(out_objects):
        chunk = b"%d 0 obj" % number + out_objects[number] + b"endobj\n"
        positions[number] = pos
        parts.append(chunk)
        pos += len(chunk)
    xref = [b"xref\n0 %d\n" % size, b"0000000000 65535 f \n"]
    for number in range(1, size):
        if number in positions:
            xref.append(b"%010d 00000 n \n" % positions[number])
        else:
            xref.append(b"0000000000 65535 f \n")
    parts.append(b"".join(xref))
    trailer = b"trailer\n<<\n/Size %d\n/Root %d 0 R\n" % (size, first_root)
    if info is not None:
        trailer += b"/Info %d 0 R\n" % info
    trailer += b">>\nstartxref\n%d\n%%%%EOF\n" % pos
    parts.append(trailer)
    return b"".join(parts)


def merge_files(paths, target):
    """Merge PDF files into `target` (which may be one of them)."""
    datas = []
    for path in paths:
        with open(path, "rb") as handle:
            datas.append(handle.read())
    merged = merge(datas)
    with open(target, "wb") as handle:
        handle.write(merged)
    return target
