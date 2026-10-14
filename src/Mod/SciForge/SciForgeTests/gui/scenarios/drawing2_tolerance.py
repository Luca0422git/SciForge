# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Dimension dialog (double-click a dimension): tolerances, ISO fits, text,
precision, basic and reference, with real clicks and typing.

The plate (drawing_fixtures.plate), ISO A3, base view Top at 1:1. With D: hole 1's
diameter (10) and the bottom edge's length (80).

A  Double-click the diameter's value: the Dimension dialog (Measured 10, Tolerance
   None). Tolerance Fit: H7/g6 (hole basis, clearance), this dimension is the hole:
   "10 H7"; Display Class and tolerances: +0.015 over 0 beside it; the fit's limits
   are written in the dialog. OK.
B  Double-click it again: the dialog shows the fit; Display Limits: 10.015 over 10.000.
   OK. Undo: class and tolerances again; Redo: the limits.
C  The length (80): Symmetric 0.1 shows "80 +-0.100"; Cancel: TechDraw's own text again.
D  Deviation +0.1 / -0.05: stacked beside 80; a wrong pair (upper below lower) is
   refused in the dialog (it stays open); fixed, OK.
E  The diameter: Tolerance None; text before "2x " (typed) and a symbol button (the
   square sign) and text after " THRU"; precision 0.12: "2x []10.00 THRU". Basic: in a
   box. Reference instead: in parentheses. OK.
F  A custom fit: Fit Custom, hole H8, shaft f7, this dimension is the shaft: "10 f7";
   Display Fit: "10 H8/f7"; a class SciForge does not know (Q7) is refused; Esc
   cancels: the dimension keeps the reference text from E.
G  The DXF writes the toleranced texts.
"""

import os

from PySide import QtCore

from SciForgeTests.gui import drawing2_steps as w
from SciForgeTests.gui import drawing_input as d
from SciForgeTests.gui import harness as h

state = {}
DIA = w.DIA


def dia():
    return w.STORE.get("dia")


def length():
    return w.STORE.get("length")


def dlg():
    return d.panel_of("DimensionEditPanel")


def open_dialog(dim_name):
    def open_():
        dim = w.STORE.get(dim_name)
        if h.check("the %s dimension exists" % dim_name, dim is not None):
            d.double_click_at(*w.label_point(dim))

    open_.wait_ms = 1500

    def opened():
        p = dlg()
        h.check("the Dimension dialog opened", p is not None, d.panel())
        if p is not None:
            h.check("it is that dimension's", p.dim.Name == w.STORE[dim_name].Name)

    open_.__name__ = "open_" + dim_name
    opened.__name__ = "opened_" + dim_name
    return [open_, opened]


def texts(dim):
    return (
        dim.FormatSpec,
        dim.FormatSpecOverTolerance if dim.ArbitraryTolerances else "",
        dim.FormatSpecUnderTolerance if dim.ArbitraryTolerances else "",
    )


# -- A ------------------------------------------------------------------------------------------
def a_defaults():
    p = dlg()
    if p is None:
        return
    h.check("measured 10", p.measured.text() == DIA + "10", p.measured.text())
    h.check("tolerance None", p.tolerance.currentText() == "None")
    h.check("fit rows hidden", not p.fit.isVisibleTo(p.form))
    d.choose(p.tolerance, "Fit")


def a_fit():
    p = dlg()
    if p is None:
        return
    h.check("fit rows shown", p.fit.isVisibleTo(p.form))
    h.check("H7/g6 by default", p.fit.currentText() == "H7/g6", p.fit.currentText())
    h.check(
        "hole basis, clearance",
        (p.basis.currentText(), p.fit_type.currentText()) == ("Hole", "Clearance"),
    )
    h.check("the sheet: 10 H7", dia().FormatSpec == DIA + "10 H7", dia().FormatSpec)
    d.choose(p.display, "Class and tolerances")


a_fit.wait_ms = 1200


def a_tolerances():
    p = dlg()
    h.check("+0.015 over 0", texts(dia()) == (DIA + "10 H7", "+0.015", "0"), texts(dia()))
    h.check(
        "the fit's limits in the dialog",
        p is not None and "10.015" in p.fit_info.text(),
        p and p.fit_info.text(),
    )
    h.check(
        "clearance named",
        p is not None and "clearance" in p.fit_info.text(),
        p and p.fit_info.text(),
    )
    w.ok()


a_tolerances.wait_ms = 1500


def a_closed():
    h.check("closed", d.panel() is None)
    h.check(
        "the settings are kept", '"Fit"' in dia().SciForgeDimSettings, dia().SciForgeDimSettings
    )
    h.shot("a-fit")


# -- B ------------------------------------------------------------------------------------------
def b_shown():
    p = dlg()
    if p is None:
        return
    h.check(
        "the dialog shows the fit",
        p.tolerance.currentText() == "Fit" and p.fit.currentText() == "H7/g6",
    )
    h.check("and its display", p.display.currentText() == "Class and tolerances")
    d.choose(p.display, "Limits")


def b_limits():
    h.check(
        "limits 10.015 over 10.000",
        dia().FormatSpec == DIA + "10.015\n" + DIA + "10.000",
        repr(dia().FormatSpec),
    )
    h.check("no small tolerances", not dia().ArbitraryTolerances)
    w.ok()


b_limits.wait_ms = 1500


def b_undo():
    d.undo()


b_undo.wait_ms = 1500


def b_undone():
    doc = d.page().Document
    h.check(
        "undo: class and tolerances",
        texts(dia()) == (DIA + "10 H7", "+0.015", "0"),
        (texts(dia()), dia().SciForgeDimSettings, doc.UndoNames, doc.RedoNames),
    )
    d.redo()


b_undone.wait_ms = 1500


def b_redone():
    h.check("redo: the limits", dia().FormatSpec.startswith(DIA + "10.015"), dia().FormatSpec)


# -- C ------------------------------------------------------------------------------------------
def c_symmetric():
    p = dlg()
    if p is None:
        return
    h.check("measured 80", p.measured.text() == "80", p.measured.text())
    d.choose(p.tolerance, "Symmetric")


def c_value():
    p = dlg()
    if p is not None:
        h.check(
            "one tolerance field", p.upper.isVisibleTo(p.form) and not p.lower.isVisibleTo(p.form)
        )
        d.type_into(p.upper, "0.1")


def c_shown():
    h.check("80 +-0.100", length().FormatSpec == "80 ±0.100", length().FormatSpec)
    w.cancel()


c_shown.wait_ms = 1500


def c_cancelled():
    h.check(
        "Cancel: TechDraw's own text",
        not length().Arbitrary,
        (length().Arbitrary, length().FormatSpec),
    )
    h.check("no settings", not getattr(length(), "SciForgeDimSettings", "").strip("{}"))


# -- D ------------------------------------------------------------------------------------------
def d_deviation():
    p = dlg()
    if p is None:
        return
    d.choose(p.tolerance, "Deviation")
    d.type_into(p.upper, "0.1")
    d.type_into(p.lower, "-0.05")


d_deviation.wait_ms = 1200


def d_shown():
    h.check(
        "80 with +0.100 over -0.050", texts(length()) == ("80", "+0.100", "-0.050"), texts(length())
    )
    p = dlg()
    d.type_into(p.upper, "-0.2")


def d_wrong():
    p = dlg()
    h.check(
        "a wrong pair is said",
        p is not None and "upper" in p.message.text().lower(),
        p and p.message.text(),
    )
    w.ok()


def d_stays():
    p = dlg()
    h.check("OK refused: the dialog stays", p is not None)
    if p is not None:
        d.type_into(p.upper, "0.1")


def d_ok():
    w.ok()


d_ok.wait_ms = 1200


def d_kept():
    h.check("closed", d.panel() is None)
    h.check("the deviation is kept", texts(length()) == ("80", "+0.100", "-0.050"), texts(length()))


# -- E ------------------------------------------------------------------------------------------
def e_text():
    p = dlg()
    if p is None:
        return
    d.choose(p.tolerance, "None")
    d.type_into(p.prefix, "2x ")


e_text.wait_ms = 1000


def e_symbol():
    p = dlg()
    if p is None:
        return
    button = p.form.findChild(QtCore.QObject, "SciForgeDimSymbol_Square")
    if h.check("the square sign's button", button is not None):
        p.prefix.setFocus()
        p.prefix.end(False)
        button.click()
    d.type_into(p.suffix, " THRU")


def e_precision():
    p = dlg()
    h.check("2x []10 THRU", dia().FormatSpec == "2x □" + DIA + "10 THRU", dia().FormatSpec)
    d.choose(p.precision, "0.12")


def e_basic():
    h.check("two decimals", dia().FormatSpec == "2x □" + DIA + "10.00 THRU", dia().FormatSpec)
    w.toggle(dlg().basic)


def e_reference():
    h.check("basic: framed", dia().TheoreticalExact)
    p = dlg()
    w.toggle(p.basic)
    w.toggle(p.reference)


def e_ok():
    h.check(
        "reference: in parentheses",
        dia().FormatSpec == "(2x □" + DIA + "10.00 THRU)",
        dia().FormatSpec,
    )
    h.check("no frame", not dia().TheoreticalExact)
    w.ok()


e_ok.wait_ms = 1200


# -- F ------------------------------------------------------------------------------------------
def f_custom():
    p = dlg()
    if p is None:
        return
    w.toggle(p.reference)
    d.choose(p.tolerance, "Fit")
    d.choose(p.display, "Class")


def f_classes():
    p = dlg()
    d.choose(p.fit, "Custom")
    d.type_into(p.hole, "H8")
    d.type_into(p.shaft, "f7")
    d.choose(p.member, "Shaft")


f_classes.wait_ms = 1500


def f_shaft():
    h.check("10.00 f7", dia().FormatSpec.endswith(DIA + "10.00 f7 THRU"), dia().FormatSpec)
    p = dlg()
    d.choose(p.display, "Fit")


def f_fit():
    h.check("10.00 H8/f7", "H8/f7" in dia().FormatSpec, dia().FormatSpec)
    d.type_into(dlg().hole, "Q7")


def f_refused():
    p = dlg()
    h.check(
        "an unknown class is said",
        p is not None and "Q" in p.message.text(),
        p and p.message.text(),
    )
    d.click_at(380, 250)
    d.key(QtCore.Qt.Key_Escape)


f_refused.wait_ms = 1500


def f_cancelled():
    h.check("Esc cancels", d.panel() is None, d.panel())
    h.check(
        "the reference text from E is back",
        dia().FormatSpec == "(2x □" + DIA + "10.00 THRU)",
        dia().FormatSpec,
    )


# -- G ------------------------------------------------------------------------------------------
def g_dxf():
    from sciforge import drawing, drawing_core

    folder = os.path.join(h.OUT_DIR, "drawing2")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "tolerance.dxf")
    drawing.export_dxf(d.page(), path)
    with open(path, encoding="utf-8") as handle:
        ents = drawing_core.read_dxf_entities(handle.read())
    words = [e[1].get(1, [""])[0] for e in ents if e[0] == "TEXT"]
    h.check("the DXF has the deviation", "80 +0.100/-0.050" in words, words)
    h.check("and the reference", "(2x □" + DIA + "10.00 THRU)" in words, words)


HOLE1_EDGE = w.hole_top(w.HOLE1)

h.run(
    "drawing2_tolerance",
    [w.new_design("Tol")]
    + w.sheet_steps()
    + [d.wait_geometry(1500)]
    + w.dimension_steps("dia", [HOLE1_EDGE], (-50.0, 15.0), "Diameter")
    + w.dimension_steps("length", [(0.0, -25.0)], (0.0, -38.0), "DistanceX")
    + open_dialog("dia")
    + [a_defaults, a_fit, a_tolerances, a_closed]
    + open_dialog("dia")
    + [b_shown, b_limits, b_undo, b_undone, b_redone]
    + open_dialog("length")
    + [c_symmetric, c_value, c_shown, c_cancelled]
    + open_dialog("length")
    + [d_deviation, d_shown, d_wrong, d_stays, d_ok, d_kept]
    + open_dialog("dia")
    + [e_text, e_symbol, e_precision, e_basic, e_reference, e_ok]
    + open_dialog("dia")
    + [f_custom, f_classes, f_shaft, f_fit, f_refused, f_cancelled]
    + [g_dxf],
)
