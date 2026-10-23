# SPDX-License-Identifier: LGPL-2.1-or-later
"""Create Flat Pattern of an L bracket the way a Fusion user does it, real input only: the
SHEET METAL tab, Create Flat Pattern with nothing picked (the dialog waits), a click on the
bracket's top face (the dialog says the flat size), OK: the FLAT PATTERN tab is the only tab,
the flat part lies on XY (98.26195 x 20 x 1: 48 + 48 + BA), Finish Flat Pattern goes back to
the folded part; undo / redo; a second Create Flat Pattern in the same component is refused;
the flat pattern follows an edit of the folded part (the extrude made 30 wide); the browser's
Flat Pattern row opens it again with a double-click; Cancel and Esc leave nothing behind."""

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import flatpattern_steps as fs
from SciForgeTests.gui import harness as h

V = App.Vector
s = {}


def setup():
    fs.setup_l("FlatL")
    s["volume"] = fs.volume()


def folded_ok():
    h.check("L bracket folded volume 1920 + 15 pi", fs.close(s["volume"], fs.L_FOLDED), s["volume"])
    from sciforge import sheetmetal

    h.check("the body is sheet metal", sheetmetal.is_sheet_metal_body(fs.body()))


def sheet_tab():
    fs.tab("sheet_metal")


def start_create():
    h.check("SHEET METAL tab selected", fs.current_tab() == "sheet_metal", fs.current_tab())
    Gui.Selection.clearSelection()
    h.ribbon("Create Flat Pattern")


def waiting():
    p = fs.sheet_panel()
    h.check("Create Flat Pattern dialog open", p is not None and fs.dialog_open())
    h.check("nothing picked yet", p is not None and p.picks["face"] == [])
    h.check("no error while waiting", p is not None and "⚠" not in p.message.text(), fs.message())
    fs.no_popups("Create Flat Pattern")
    h.check("no flat pattern yet", fs.flat_patterns() == [])


def click_top():
    h.fit()
    h.click(fs.L_TOP)


def top_picked():
    fs.settle()
    p = fs.sheet_panel()
    h.check("top face picked", p is not None and len(p.picks["face"]) == 1, p and p.picks)
    text = fs.message()
    h.check("dialog says the flat size", "98.26 x 20.00" in text, text)
    h.check("one bend", "1 bend" in text, text)
    h.shot("1-picked")


def press_ok():
    fs.ok()


def in_flat_environment():
    fs.settle()
    fp = fs.flat()
    h.check("a flat pattern was made", fp is not None)
    if fp is None:
        return
    s["fp"] = fp.Name
    h.check("FLAT PATTERN tab selected", fs.current_tab() == "flat_pattern", fs.current_tab())
    h.check("FLAT PATTERN tab shown", fs.tab_visible("flat_pattern"))
    h.check("SOLID tab hidden in the flat pattern", not fs.tab_visible("solid"))
    bb = fs.flat_box(fp)
    h.check("flat length 98.26195", bb is not None and fs.close(bb.XLength, fs.L_FLAT), bb)
    h.check("flat width 20", bb is not None and fs.close(bb.YLength, 20.0), bb)
    h.check("flat thickness 1, top face on XY", bb is not None and fs.close(bb.ZMax + 1, 1), bb)
    h.check("one bend", fp.BendCount == 1, fp.BendCount)
    h.check("flat shown", fp.ViewObject.Visibility)
    h.check("folded body hidden", not fs.body().ViewObject.Visibility)
    h.check(
        "Export DXF button shown",
        any(
            b.objectName() == "SciForgeBig_Export_DXF" and b.isVisible() for b in h.ribbon_buttons()
        ),
    )
    fs.no_popups("OK")
    h.shot("2-flat")


def finish():
    h.ribbon("Finish Flat Pattern")


def back_folded():
    h.check("back on the SHEET METAL tab", fs.current_tab() == "sheet_metal", fs.current_tab())
    h.check("FLAT PATTERN tab hidden", not fs.tab_visible("flat_pattern"))
    h.check("body shown again", fs.body().ViewObject.Visibility)
    fp = fs.flat()
    h.check("flat hidden", fp is not None and not fp.ViewObject.Visibility)
    node = fs.browser_node("flat_pattern")
    h.check("Flat Pattern row in the browser", node is not None and node["label"] == "Flat Pattern")
    h.check(
        "no timeline step for the flat pattern",
        "Flat Pattern" not in " ".join(fs.timeline_titles()),
        fs.timeline_titles(),
    )


def undo():
    fs.undo()


def undone():
    h.check("undo removes the flat pattern", fs.flat_patterns() == [])
    h.check("folded part untouched", fs.close(fs.volume(), s["volume"]), fs.volume())


def redo():
    fs.redo()


def redone():
    h.check("redo brings it back", len(fs.flat_patterns()) == 1)


def second_create():
    Gui.Selection.clearSelection()
    h.ribbon("Create Flat Pattern")


def second_click():
    h.fit()
    h.click(fs.L_TOP)


def second_refused():
    fs.settle()
    text = fs.message()
    h.check("a second flat pattern in the component is refused", "already has a flat" in text, text)


def second_ok():
    fs.ok()


def second_still_open():
    fs.settle()
    h.check("OK refused: dialog still open", fs.dialog_open())
    h.check("still one flat pattern", len(fs.flat_patterns()) == 1)


def second_cancel():
    fs.cancel()


def edit_extrude():
    # the folded part changes (the extrude 30 instead of 20): the flat pattern follows
    builder = fs.STATE["builder"]
    e1 = builder.objects["e1"]
    e1.Length = 30
    App.ActiveDocument.recompute()


def follows():
    fp = fs.flat()
    bb = fs.flat_box(fp)
    h.check(
        "flat pattern follows the edit: 30 wide", bb is not None and fs.close(bb.YLength, 30.0), bb
    )
    h.check("still 98.26195 long", bb is not None and fs.close(bb.XLength, fs.L_FLAT), bb)
    h.check("flat pattern valid", "Invalid" not in fp.State, fp.State)


def double_click_row():
    h.check("browser row double-clicked", fs.double_click_browser("Flat Pattern"))


def reopened():
    fs.settle()
    h.check(
        "double-click opens the flat pattern", fs.current_tab() == "flat_pattern", fs.current_tab()
    )


def finish_again():
    h.ribbon("Finish Flat Pattern")


def closed_again():
    h.check(
        "back to the folded part",
        fs.current_tab() != "flat_pattern" and fs.body().ViewObject.Visibility,
    )


def esc_start():
    Gui.Selection.clearSelection()
    h.ribbon("Create Flat Pattern")


def esc_press():
    fs.esc()


def after_esc():
    h.check("Esc closes the dialog", not fs.dialog_open())
    h.check("Esc leaves one flat pattern", len(fs.flat_patterns()) == 1)


h.run(
    "flatpattern_l_bracket",
    [
        setup,
        folded_ok,
        sheet_tab,
        start_create,
        waiting,
        click_top,
        top_picked,
        press_ok,
        in_flat_environment,
        finish,
        back_folded,
        undo,
        undone,
        redo,
        redone,
        second_create,
        second_click,
        second_refused,
        second_ok,
        second_still_open,
        second_cancel,
        edit_extrude,
        follows,
        double_click_row,
        reopened,
        finish_again,
        closed_again,
        esc_start,
        esc_press,
        after_esc,
    ],
)
