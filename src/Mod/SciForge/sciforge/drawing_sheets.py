# SPDX-License-Identifier: LGPL-2.1-or-later
"""Several sheets in one drawing (Fusion's Sheet Bar), on TechDraw (no Qt: the sheet bar
is in drawing_sheets_ui.py).

A TechDraw page is one sheet. A SciForge drawing is its first page (SciForgeType
"Drawing", listed in the browser) plus the pages added as further sheets (SciForgeType
"DrawingSheet", SciForgeDrawingOf = the first page's name, not listed). The first page
keeps the order of all sheets (SciForgeSheets: page names) and every page its sheet
name (SciForgeSheetName, "Sheet 1"...). A sheet's number is its place in that order:
the title block shows "2 / 3" and follows when sheets are added, deleted or moved.
Fields typed into a title block are the drawing's (they show on every sheet); the scale
is each sheet's own (its first base view).
"""

import os


from . import drawing
from . import drawing_pdf, log, warn

SHEET_TYPE = "DrawingSheet"


class SheetError(ValueError):
    """A sheet operation that cannot be done, with a sentence that says why."""


def is_sheet_page(obj):
    return drawing.is_page(obj) and drawing.kind(obj) == SHEET_TYPE


def main_page(page):
    """The drawing (first page) a sheet belongs to."""
    if page is None or not is_sheet_page(page):
        return page
    name = drawing._get(page, "SciForgeDrawingOf", "")
    main = page.Document.getObject(name) if name else None
    return main if drawing.alive(main) else page


def sheets(page):
    """Every sheet of the drawing `page` belongs to, in the Sheet Bar's order."""
    main = main_page(page)
    if main is None:
        return []
    doc = main.Document
    names = list(drawing._get(main, "SciForgeSheets", []) or [])
    found = []
    for name in names:
        obj = doc.getObject(name)
        if drawing.is_page(obj) and obj not in found:
            found.append(obj)
    if main not in found:
        found.insert(0, main)
    # a sheet made by an older version or brought back by Undo without the list
    for obj in drawing.all_pages(doc):
        if is_sheet_page(obj) and drawing._get(obj, "SciForgeDrawingOf", "") == main.Name:
            if obj not in found:
                found.append(obj)
    return found


def sheet_number(page):
    """(number, count) of a sheet in its drawing."""
    found = sheets(page)
    for i, sheet in enumerate(found):
        if drawing.same(sheet, page):
            return i + 1, len(found)
    return 1, max(1, len(found))


def sheet_name(page):
    name = drawing._get(page, "SciForgeSheetName", "")
    if name:
        return name
    number, _count = sheet_number(page)
    return "Sheet %d" % number


def _save_order(main, pages):
    drawing._add(main, "App::PropertyStringList", "SciForgeSheets", [p.Name for p in pages])


def page_label(main, name):
    """The tab title of a further sheet: the drawing's name and the sheet's."""
    return "%s: %s" % (main.Label, name)


def relabel(main):
    """Further sheets' labels follow the drawing's name (Rename in the browser)."""
    for page in sheets(main):
        if page is main:
            continue
        want = page_label(main, sheet_name(page))
        if page.Label != want:
            page.Label = want


def _next_name(main):
    taken = {sheet_name(p) for p in sheets(main)}
    n = len(taken) + 1
    while "Sheet %d" % n in taken:
        n += 1
    return "Sheet %d" % n


def add_sheet(page, index=None):
    """A new, empty sheet in the drawing of `page` (Fusion: the Sheet Bar's +, the same
    size and title block as the active sheet), at `index` in the order (the end by
    default). Returns the new page."""
    main = main_page(page)
    doc = main.Document
    order = sheets(main)
    if "SciForgeSheetName" not in main.PropertiesList:
        drawing._add(main, "App::PropertyString", "SciForgeSheetName", "Sheet 1")
    name = _next_name(main)
    sources = [s for s in (drawing._get(page, "SciForgeSources", []) or []) if drawing.alive(s)]
    if not sources:
        sources = [s for s in (drawing._get(main, "SciForgeSources", []) or []) if drawing.alive(s)]
    new = drawing.create_drawing(
        doc,
        sources or drawing.design_bodies(doc),
        standard=drawing.standard_of(page),
        units=drawing.units_of(page),
        sheet=drawing.sheet_of(page),
        title_block=bool(drawing._get(page, "SciForgeTitleBlock", True)),
        label=page_label(main, name),
        contents=drawing._get(main, "SciForgeContents", ""),
    )
    drawing._mark(new, SHEET_TYPE)
    drawing._add(new, "App::PropertyString", "SciForgeDrawingOf", main.Name)
    drawing._add(new, "App::PropertyString", "SciForgeSheetName", name)
    edits = list(drawing._get(main, "SciForgeTitleEdits", []) or [])
    typed = {k: v for k, v in drawing.title(main).items() if k in edits}
    if typed:
        drawing.set_title(new, typed, by_hand=True)
    if index is None or index < 0 or index > len(order):
        index = len(order)
    order.insert(index, new)
    _save_order(main, order)
    refresh_titles(main)
    log("sheet %s added to %s (%d sheets)" % (name, main.Label, len(order)))
    return new


def rename_sheet(page, name):
    name = (name or "").strip()
    if not name:
        raise SheetError("Give the sheet a name.")
    main = main_page(page)
    for other in sheets(main):
        if not drawing.same(other, page) and sheet_name(other) == name:
            raise SheetError("Another sheet of this drawing is called %s." % name)
    drawing._add(page, "App::PropertyString", "SciForgeSheetName", name)
    if page is not main:
        page.Label = page_label(main, name)


def move_sheet(page, index):
    """Move a sheet to place `index` (0 = first) of the Sheet Bar."""
    main = main_page(page)
    order = sheets(main)
    current = [i for i, p in enumerate(order) if drawing.same(p, page)]
    if not current:
        return False
    sheet = order.pop(current[0])
    index = max(0, min(len(order), index))
    order.insert(index, sheet)
    _save_order(main, order)
    refresh_titles(main)
    return current[0] != index


def _promote(new_main, old_main):
    """The first page is being deleted: another sheet becomes the drawing."""
    order = [p for p in sheets(old_main) if not drawing.same(p, old_main)]
    label = old_main.Label
    edits = list(drawing._get(old_main, "SciForgeTitleEdits", []) or [])
    contents = drawing._get(old_main, "SciForgeContents", "")
    drawing._mark(new_main, drawing.TYPE)
    drawing._add(new_main, "App::PropertyString", "SciForgeDrawingOf", "")
    drawing._add(new_main, "App::PropertyStringList", "SciForgeTitleEdits", edits)
    drawing._add(new_main, "App::PropertyString", "SciForgeContents", contents)
    for page in order:
        if page is not new_main:
            drawing._add(page, "App::PropertyString", "SciForgeDrawingOf", new_main.Name)
    _save_order(new_main, order)
    return label


def delete_sheet(page):
    """Delete one sheet and everything on it (Fusion: right-click > Delete Sheet). The
    last sheet of a drawing cannot go (delete the drawing in the browser instead).
    Returns the sheet to show next."""
    main = main_page(page)
    order = sheets(main)
    if len(order) <= 1:
        raise SheetError(
            "A drawing keeps at least one sheet: delete the whole drawing in the browser "
            "(Drawings folder) instead."
        )
    index = [i for i, p in enumerate(order) if drawing.same(p, page)][0]
    rest = [p for p in order if not drawing.same(p, page)]
    show = rest[min(index, len(rest) - 1)]
    if drawing.same(page, main):
        label = _promote(rest[0], main)
        main = rest[0]
        drawing.delete_drawing(page)
        main.Label = label
        relabel(main)
    else:
        drawing.delete_drawing(page)
        _save_order(main, rest)
    refresh_titles(main)
    return show


def refresh_titles(page):
    """Every sheet's number and count in its title block."""
    changed = False
    for sheet in sheets(page):
        try:
            changed |= drawing.refresh_title(sheet)
        except Exception as exc:
            warn("title block of %s: %s" % (sheet.Label, exc))
    return changed


def set_title_everywhere(page, values):
    """Typed title block fields are the drawing's: every sheet shows them."""
    for sheet in sheets(page):
        drawing.set_title(sheet, values, by_hand=True)


# ------------------------------------------------------------------ export
def export_pdf(page, path, which="all"):
    """Fusion's Export PDF: all sheets in one PDF (which="all") or the given sheet."""
    pages = sheets(page) if which == "all" else [page]
    if len(pages) == 1:
        return drawing.export_pdf(pages[0], path)
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    parts = []
    stem, _ext = os.path.splitext(path)
    try:
        for i, sheet in enumerate(pages):
            part = "%s.sheet%d.tmp.pdf" % (stem, i + 1)
            drawing.export_pdf(sheet, part)
            parts.append(part)
        drawing_pdf.merge_files(parts, path)
    finally:
        for part in parts:
            try:
                os.remove(part)
            except OSError:
                pass
    if not os.path.isfile(path) or os.path.getsize(path) == 0:
        raise drawing.DrawingError("The PDF could not be written to %s." % path)
    return path


def dxf_paths(page, path, which="all"):
    """[(sheet, file)] of an Export DXF: one file per sheet, named after the sheet when
    there are several (a DXF holds one sheet)."""
    pages = sheets(page) if which == "all" else [page]
    if len(pages) == 1:
        return [(pages[0], path)]
    stem, ext = os.path.splitext(path)
    out = []
    for sheet in pages:
        out.append((sheet, "%s - %s%s" % (stem, _safe(sheet_name(sheet)), ext or ".dxf")))
    return out


def _safe(name):
    return "".join(c if c.isalnum() or c in " -_." else "_" for c in name).strip() or "Sheet"


def export_dxf(page, path, which="all"):
    written = []
    for sheet, target in dxf_paths(page, path, which):
        drawing.export_dxf(sheet, target)
        written.append(target)
    return written


def sheet_title_value(page):
    number, count = sheet_number(page)
    return "%d / %d" % (number, count)
