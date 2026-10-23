# SPDX-License-Identifier: LGPL-2.1-or-later
"""Convert a shelled tube to sheet metal, Rip it open, flatten it, real input only: a 40 x 30
x 20 box with rounded vertical edges (radius 2) shelled 1 mm with its top and bottom taken
away (setup). SHEET METAL > MODIFY > Convert to Sheet Metal with nothing picked (the dialog
waits), a click on the front wall: Thickness 1.000 mm (read only), Template Rule, 4 bends
found, OK: the body is sheet metal ("Convert to Sheet Metal" in the timeline). Create Flat
Pattern on the closed tube is refused in the dialog ("closes on itself ... add a Rip"), OK
waits, Esc closes. Rip: Type Face, a click on the outside of the back-right corner bend: the
corner is cut away (preview), OK; undo / redo. Create Flat Pattern from the front wall now
lays it flat: 36 + 26 + 36 + 26 + 3 BA = 130.78584 long, 20 wide. Rip edited from the timeline
keeps its type and face; Cancel."""
import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import flatpattern_steps as fs
from SciForgeTests.gui import harness as h

V = App.Vector
s = {}
TUBE_VOLUME = None


def setup():
    fs.build("FlatTube", fs.TUBE_STEPS)
    s["volume"] = fs.volume()


def tube_made():
    # walls: 2 (36 + 26) * 20 * 1 + 4 quarter rings (pi/4) (2^2 - 1^2) * 20
    expect = 2 * (36 + 26) * 20 + 4 * (3.141592653589793 / 4) * 3 * 20
    h.check("tube made", fs.close(s["volume"], expect), (s["volume"], expect))


def sheet_tab():
    fs.tab("sheet_metal")


def convert():
    Gui.Selection.clearSelection()
    fs.menu("MODIFY", "Convert to Sheet Metal")


def convert_waits():
    p = fs.sheet_panel()
    h.check("Convert dialog open", p is not None and fs.dialog_open())
    h.check("thickness not known yet", p is not None and p.thickness.text() == "-")
    fs.no_popups("Convert to Sheet Metal")


def click_front():
    h.fit()
    h.click(fs.TUBE_FRONT)


def thickness_shown():
    fs.settle()
    p = fs.sheet_panel()
    h.check("thickness 1.000 mm shown", p is not None and p.thickness.text() == "1.000 mm", p and p.thickness.text())
    h.check("thickness is read only (a label)", p is not None and not hasattr(p.thickness, "setValue"))
    h.check("4 bends found", "4 bend" in fs.message(), fs.message())
    h.check("Template Rule first", p is not None and p.rule.currentText() == "Template Rule")
    h.check("matching thickness only by default", p is not None and p.matching.isChecked())
    names = [p.rule.itemText(i) for i in range(p.rule.count())] if p else []
    h.check("1 mm library rules offered", any("Steel (mm)" in n for n in names), names)
    h.check("thicker rules filtered out", not any("Aluminum (mm)" in n for n in names), names)


def convert_ok():
    fs.ok()


def converted():
    fs.settle()
    from sciforge import sheetmetal

    body = fs.body()
    h.check("dialog closed", not fs.dialog_open())
    h.check("the body is sheet metal", sheetmetal.is_sheet_metal_body(body))
    h.check("its rule is 1 mm thick", fs.close(sheetmetal.rule_for_body(body)["thickness"], 1.0))
    titles = fs.timeline_titles()
    h.check("Convert to Sheet Metal in the timeline", any(t.startswith("Convert to Sheet Metal") for t in titles), titles)
    h.check("shape unchanged", fs.close(fs.volume(), s["volume"]), fs.volume())


def flat_closed():
    Gui.Selection.clearSelection()
    h.ribbon("Create Flat Pattern")


def flat_click():
    h.fit()
    h.click(fs.TUBE_FRONT)


def closed_refused():
    fs.settle()
    text = fs.message()
    h.check("closed tube refused with the reason", "closes on itself" in text and "Rip" in text, text)


def closed_ok():
    fs.ok()


def closed_waits():
    fs.settle()
    h.check("OK refused: dialog still open", fs.dialog_open())
    h.check("no flat pattern made", fs.flat_patterns() == [])


def closed_esc():
    fs.esc()


def closed_gone():
    fs.settle()
    h.check("Esc closes the dialog", not fs.dialog_open())
    fs.no_popups("Esc")


def rip():
    Gui.Selection.clearSelection()
    h.ribbon("Rip")


def rip_dialog():
    p = fs.sheet_panel()
    h.check("Rip dialog open", p is not None and fs.dialog_open())
    if p is None:
        return
    h.check("Along Edge by default", p.type_key() == "edge", p.type_key())
    h.check("gap from the rule (1 mm)", abs(p.gap.value() - 1.0) < 1e-9, p.gap.value())
    fs.choose(p.kind, "Face")


def rip_face_type():
    p = fs.sheet_panel()
    h.check("Type Face chosen", p is not None and p.type_key() == "face")


def rip_click_corner():
    h.fit()
    h.click(fs.TUBE_CORNER)


def rip_preview():
    fs.settle()
    p = fs.sheet_panel()
    h.check("corner face picked", p is not None and len(p.picks["face"]) == 1, p and p.picks)
    v = fs.volume()
    corner = (3.141592653589793 / 4) * 3 * 20
    h.check("preview: the corner bend is cut away", fs.close(v, s["volume"] - corner), (v, s["volume"] - corner))
    h.check("no message", "⚠" not in fs.message(), fs.message())
    h.shot("1-rip")


def rip_ok():
    fs.ok()


def ripped():
    fs.settle()
    h.check("Rip dialog closed", not fs.dialog_open())
    s["ripped"] = fs.volume()


def undo():
    fs.undo()


def undone():
    h.check("undo: the tube is closed again", fs.close(fs.volume(), s["volume"]), fs.volume())


def redo():
    fs.redo()


def redone():
    h.check("redo: ripped again", fs.close(fs.volume(), s["ripped"]), fs.volume())


def flat_again():
    Gui.Selection.clearSelection()
    h.ribbon("Create Flat Pattern")


def flat_again_click():
    h.fit()
    h.click(fs.TUBE_FRONT)


def flat_again_size():
    fs.settle()
    text = fs.message()
    h.check("dialog says 130.79 x 20.00", "130.79 x 20.00" in text, text)


def flat_again_ok():
    fs.ok()


def flattened():
    fs.settle()
    bb = fs.flat_box()
    h.check("ripped tube flat: 130.78584 long", bb is not None and fs.close(bb.XLength, fs.TUBE_FLAT), bb)
    h.check("20 wide", bb is not None and fs.close(bb.YLength, 20), bb)
    h.check("3 bends", fs.flat() is not None and fs.flat().BendCount == 3)
    h.shot("2-flat")


def finish():
    h.ribbon("Finish Flat Pattern")


def edit_rip():
    titles = [t for t in fs.timeline_titles() if t.startswith("Rip")]
    h.check("Rip in the timeline", bool(titles), fs.timeline_titles())
    if titles:
        fs.double_click_timeline(titles[0])


def edit_open():
    fs.settle()
    p = fs.sheet_panel()
    h.check("Edit Rip open", p is not None and p.editing)
    h.check("type Face kept", p is not None and p.type_key() == "face")
    h.check("its face kept", p is not None and len(p.picks["face"]) == 1)


def edit_cancel():
    fs.cancel()


def after_cancel():
    fs.settle()
    h.check("Cancel: unchanged", fs.close(fs.volume(), s["ripped"]), fs.volume())


h.run(
    "flatpattern_rip_convert",
    [
        setup,
        tube_made,
        sheet_tab,
        convert,
        convert_waits,
        click_front,
        thickness_shown,
        convert_ok,
        converted,
        flat_closed,
        flat_click,
        closed_refused,
        closed_ok,
        closed_waits,
        closed_esc,
        closed_gone,
        rip,
        rip_dialog,
        rip_face_type,
        rip_click_corner,
        rip_preview,
        rip_ok,
        ripped,
        undo,
        undone,
        redo,
        redone,
        flat_again,
        flat_again_click,
        flat_again_size,
        flat_again_ok,
        flattened,
        finish,
        edit_rip,
        edit_open,
        edit_cancel,
        after_cancel,
    ],
)
