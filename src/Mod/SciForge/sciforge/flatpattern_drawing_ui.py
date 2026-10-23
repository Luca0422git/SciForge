# SPDX-License-Identifier: LGPL-2.1-or-later
"""DRAWING > TABLES > Bend Table and DRAWING > TEXT > Bend Note (Fusion's behaviour for a flat
pattern drawing; the work is flatpattern_drawing.py).

Bend Table: the flat pattern view picked (or the drawing's only one) gets its bend
identifiers and a table of its bends at the top left of the sheet. One undo step.
Bend Note: click bend centre lines of a flat pattern view; each gets a note along it (its
direction, angle and inside radius); OK keeps them (one undo step), Esc / Cancel drops them.
"""

import FreeCAD as App
import FreeCADGui as Gui

from . import commands, drawing, drawing_ui, log, ui_icon_path, warn
from . import drawing_core as core
from . import flatpattern_drawing as fpd


def _picked_view(page):
    try:
        for obj in Gui.Selection.getSelection():
            if fpd.flat_of(obj) is not None and drawing.same(drawing.page_of(obj), page):
                return obj
    except Exception:
        pass
    views = fpd.flat_views(page)
    return views[0] if views else None


def bend_table(page=None):
    """Make the bend table of the active drawing. Returns the table or None (said why)."""
    from . import drawing_ui

    page = page or drawing_ui.active_page()
    if page is None:
        commands.tell("Open a drawing first.")
        return None
    view = _picked_view(page)
    if view is None:
        commands.tell(
            "A bend table needs a view of a flat pattern: make a drawing of the flat pattern "
            "(New Drawing > Contents Select > Flat Pattern)."
        )
        return None
    doc = page.Document
    x0, _y0, _x1, y1 = core.drawing_area(drawing.standard_of(page), drawing.sheet_of(page))
    doc.openTransaction("Bend Table")
    try:
        table, balloons = fpd.add_bend_table(page, view, (x0 + 4.0, y1 - 4.0))
        doc.recompute()
        doc.commitTransaction()
    except drawing.DrawingError as exc:
        doc.abortTransaction()
        commands.tell(str(exc))
        return None
    except Exception as exc:
        doc.abortTransaction()
        warn("bend table: %s" % exc)
        return None
    log("bend table with %d bends on %s" % (len(balloons), page.Label))
    return table


class BendNotePanel(drawing_ui.DrawingPanel):
    """Fusion's Bend Note: every click on a bend centre line of a flat pattern view writes
    that bend's note along it."""

    title = "Bend Note"
    icon = "dw_text"

    def __init__(self, page):
        super().__init__(page, "Bend Note")
        self.notes = []
        self.finish_layout()
        self.say("Click a bend centre line of the flat pattern view.")

    def on_press(self, point, event):
        try:
            self._press(point)
        except Exception as exc:
            warn("bend note: %s" % exc)
        return True

    def _press(self, point):
        view, _name, local = drawing_ui.pick_at(
            self.page, point, self.tolerance(), want_vertex=False, curve="line"
        )
        if view is None or fpd.flat_of(view) is None:
            self.message.setText("Click a bend centre line of a flat pattern view.")
            return
        reach = self.tolerance() / (drawing.scale_of(view) or 1.0)
        index = fpd.bend_at(view, local, reach)
        if index is None:
            self.message.setText("That is not a bend centre line: click the dash-dot line.")
            return
        try:
            note = fpd.add_bend_note(self.page, view, index)
        except drawing.DrawingError as exc:
            self.message.setText(str(exc))
            return
        self.notes.append(note)
        self.message.setText("")
        self._recompute()
        self.say("%d bend note(s). Click more bend centre lines, then OK." % len(self.notes))


class BendNoteCommand(drawing_ui._Base):
    title = "Bend Note"
    tip = (
        "Click bend centre lines of a flat pattern view: each gets its direction, angle and radius"
    )
    icon = "dw_text"

    def run(self):
        page = drawing_ui._need_page()
        if page is None:
            return
        if not fpd.flat_views(page):
            commands.tell(
                "Bend notes go on a view of a flat pattern: make a drawing of the flat pattern "
                "(New Drawing > Contents Select > Flat Pattern)."
            )
            return
        drawing_ui._start(BendNotePanel)


class BendTableCommand:
    def GetResources(self):
        return {
            "MenuText": "Bend Table",
            "ToolTip": "A table of a flat pattern view's bends, with their identifiers",
            "Pixmap": ui_icon_path("dw_table"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            if not commands.finish_open_dialog():
                return
            bend_table()
        except Exception as exc:
            warn("Bend Table: %s" % exc)


COMMANDS = {
    "SciForge_DrawingBendTable": BendTableCommand,
    "SciForge_DrawingBendNote": BendNoteCommand,
}
