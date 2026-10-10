# SPDX-License-Identifier: LGPL-2.1-or-later
"""Parameters in a pattern's Quantity and Distance fields, the way a Fusion user does it:

1. A 40 x 30 x 10 box with a through hole r 2 at (8, 8). Two user parameters exist
   (Change Parameters made them): n = 3 (no unit) and gap = 12 mm.
2. Rectangular Pattern of the hole along X: type "n" in Quantity and "gap*2" in Distance
   (Extent): holes at x = 8, 20, 32. OK.
3. n becomes 4: the pattern follows (x = 8, 16, 24, 32).
4. Edit from the timeline: the formulas are shown. Type "n - 4" in Quantity: the dialog
   says why (less than 1) and nothing changes. Press the Up arrow in Quantity: 5, a plain
   number again (the formula is gone). Type 9000: too many, the dialog says so and OK
   waits; type 5 again. OK: FreeCAD's LinearPattern (Distance still follows gap); n = 2 no
   longer changes it.
5. A Pattern of bodies refuses a quantity formula (each copy is a body).

Hand-derived: box 12000; a through hole r 2 removes pi 2^2 10.
"""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets
from PySide6 import QtTest

from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import pattern_steps as ps

V = App.Vector
s = {}
R = 2.0
HOLE = ps.hole(R)


def centres():
    return ps.circle_centres(h.body().Shape, R, z=10)


def params():
    from sciforge import parameters

    doc = App.ActiveDocument
    # Change Parameters (its own dialog, tested by its own scenarios) made these two:
    parameters.add_user(doc, "n", "", "3")
    parameters.add_user(doc, "gap", "mm", "12")
    doc.recompute()


def start():
    Gui.Selection.clearSelection()
    h.ribbon("Rectangular Pattern")


def pick():
    ps.timeline_click("Extrude 2")


def box():
    ps.click_box("direction")


def axis():
    h.fit()
    h.click(V(-12, 0, 0))


def quantity_n():
    p = ps.panel()
    h.check("X axis picked", p and p.options["direction"] is not None)
    ps.type_quantity(p.quantity, "n")


def quantity_typed():
    p = ps.panel()
    h.check("Quantity follows n", p.options["expressions"].get("quantity") == "n")
    h.check("the field shows n's value", p.quantity.value() == 3, p.quantity.value())
    h.check("the formula is shown", "Quantity = n" in p.formulas.text(), p.formulas.text())
    ps.type_value(p.distance_field.widget, "gap*2")


def distance_typed():
    p = ps.panel()
    h.check("Distance follows gap", p.options["expressions"].get("distance") == "gap*2")
    h.check("3 holes", centres() == [(8, 8), (20, 8), (32, 8)], centres())
    h.check("no complaint", not p.message.text().startswith("⚠"), p.message.text())
    h.shot("1-formulas")
    h.task_button("OK")


def after_ok():
    found = ps.patterns()
    h.check("one pattern", len(found) == 1)
    if not found:
        return
    s["f"] = found[0]
    engine = dict(s["f"].ExpressionEngine)
    h.check("its Quantity follows n", "n" in engine.get("Quantity", ""), engine)
    h.check("timeline: Rectangular Pattern 1", "Rectangular Pattern 1" in ps.timeline_titles())
    h.check("volume: three holes", ps.close(h.solid_volume(), ps.BOX - 3 * HOLE))


def n_is_4():
    from sciforge import parameters

    parameters.set_user(App.ActiveDocument, "n", "4")
    App.ActiveDocument.recompute()
    h.fit()


def four():
    h.check("n = 4: four holes", centres() == [(8, 8), (16, 8), (24, 8), (32, 8)], centres())
    h.check("valid", h.body().Shape.isValid())


def edit():
    ps.timeline_double_click("Rectangular Pattern 1")


def edit_open():
    p = ps.panel()
    h.check("the dialog opens", p is not None and p.editing)
    if p is None:
        return
    h.check("Quantity shows 4", p.quantity.value() == 4, p.quantity.value())
    text = p.formulas.text()
    h.check("both formulas shown", "Quantity = n" in text and "gap*2" in text, text)
    ps.type_quantity(p.quantity, "n - 4")


def too_few():
    p = ps.panel()
    h.check("the dialog says why", "less than 1" in p.message.text(), p.message.text())
    h.check("the field is as it was", p.quantity.value() == 4, p.quantity.value())
    h.check("still n", p.options["expressions"].get("quantity") == "n")
    h.check("still four holes", len(centres()) == 4, centres())
    p.quantity.setFocus()
    QtTest.QTest.keyClick(p.quantity, QtCore.Qt.Key_Up)
    QtWidgets.QApplication.processEvents()


def stepped():
    p = ps.panel()
    h.check("Up arrow: 5", p.quantity.value() == 5, p.quantity.value())
    h.check("a plain number again", "quantity" not in p.options["expressions"])
    h.check(
        "five holes",
        centres() == [(8, 8), (14, 8), (20, 8), (26, 8), (32, 8)],
        centres(),
    )
    h.shot("2-stepped")
    ps.type_quantity(p.quantity, 9000)


def too_many():
    p = ps.panel()
    text = p.message.text()
    h.check("the dialog says 9000 is too many", "9000" in text and "too many" in text, text)
    h.check("still five holes", len(centres()) == 5, centres())
    h.task_button("OK")


def ok_waits():
    p = ps.panel()
    h.check("OK waits while the quantity is refused", p is not None and not p._closed)
    if p is not None:
        ps.type_quantity(p.quantity, 5)


def five_again():
    p = ps.panel()
    h.check("the complaint is gone", not p.message.text().startswith("⚠"), p.message.text())
    h.task_button("OK")


def after_edit():
    found = ps.patterns()
    h.check("still one pattern", len(found) == 1)
    if not found:
        return
    h.check(
        "FreeCAD's LinearPattern again (its Distance can follow gap)",
        found[0].TypeId == "PartDesign::LinearPattern",
        found[0].TypeId,
    )
    h.check("Distance still follows gap", any("gap" in e for _p, e in found[0].ExpressionEngine))
    from sciforge import parameters

    parameters.set_user(App.ActiveDocument, "n", "2")
    App.ActiveDocument.recompute()


def n_no_longer():
    h.check("n = 2 does not change it", len(centres()) == 5, centres())
    s["v"] = h.solid_volume()
    h.check("volume: five holes", ps.close(s["v"], ps.BOX - 5 * HOLE), s["v"])


def bodies_start():
    Gui.Selection.clearSelection()
    h.ribbon("Rectangular Pattern")


def bodies_type():
    p = ps.panel()
    if p is not None:
        b.choose(p.pattern_type, "Bodies")


def bodies_formula():
    p = ps.panel()
    h.check(
        "Pattern Type: Bodies", p.options["pattern_type"] == "bodies", p.options["pattern_type"]
    )
    ps.type_quantity(p.quantity, "n")


def bodies_refused():
    p = ps.panel()
    h.check("the dialog says why", "plain number" in p.message.text(), p.message.text())
    h.check("no formula taken", "quantity" not in p.options["expressions"])
    h.check("the field is as it was", p.quantity.value() == 2, p.quantity.value())
    h.press(QtCore.Qt.Key_Escape)


def bodies_after():
    h.check("Esc: closed", not Gui.Control.activeDialog())
    h.check("unchanged", ps.close(h.solid_volume(), s["v"]) and len(ps.patterns()) == 1)


h.run(
    "patterns_params",
    b.box_steps("PatternParams")
    + ps.make_cut("hole", (8, 8), R)
    + [
        params,
        start,
        pick,
        box,
        axis,
        quantity_n,
        quantity_typed,
        distance_typed,
        after_ok,
        n_is_4,
        four,
        edit,
        edit_open,
        too_few,
        stepped,
        too_many,
        ok_waits,
        five_again,
        after_edit,
        n_no_longer,
        bodies_start,
        bodies_type,
        bodies_formula,
        bodies_refused,
        bodies_after,
    ],
)
