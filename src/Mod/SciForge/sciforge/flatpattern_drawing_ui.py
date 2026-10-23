# SPDX-License-Identifier: LGPL-2.1-or-later
"""DRAWING > TABLES > Bend Table (Fusion's behaviour for a flat pattern drawing; the work is
flatpattern_drawing.py): the flat pattern view picked (or the drawing's only one) gets its
bend identifiers and a table of its bends at the top left of the sheet. One undo step."""

import FreeCAD as App
import FreeCADGui as Gui

from . import commands, drawing, log, ui_icon_path, warn
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


COMMANDS = {"SciForge_DrawingBendTable": BendTableCommand}
