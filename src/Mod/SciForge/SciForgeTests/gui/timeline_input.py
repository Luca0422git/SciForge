# SPDX-License-Identifier: LGPL-2.1-or-later
"""Real-input helpers for the timeline and browser scenarios
(scenarios/timeline_browser*.py): click, double-click, drag and right-click the
timeline's icons, its history marker and the browser's rows, the way a person does
(Qt test events delivered to the widgets, see widget_input.py). Not a scenario."""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import widget_input as w

V = App.Vector


def near(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1.0, abs(b))


def doc():
    return App.ActiveDocument


def volume(body=None):
    """Volume of a body (default: the active one), 0 when it has no solid."""
    b = body or h.body()
    if isinstance(b, str):
        b = doc().getObject(b)
    if b is None or b.Shape.isNull():
        return 0.0
    try:
        return b.Shape.Volume
    except Exception:
        return 0.0


def step(fn, name):
    """A scenario step under its own name (steps built in loops/closures)."""
    fn.__name__ = name
    return fn


# -- the timeline ------------------------------------------------------------------------
def tl():
    from sciforge import timeline_ui

    widget = timeline_ui.widget()
    widget.refresh()  # rebuilds only when the design changed
    QtWidgets.QApplication.processEvents()  # new widgets get shown and laid out
    return widget


def titles():
    return tl().titles()


def item(title):
    for i in tl().items():
        if i.display == title:
            return i
    return None


def button(title, quiet=False):
    for b in tl()._buttons:
        if b.item.display == title:
            return b
    if not quiet:
        h.check("timeline has %r" % title, False, titles())
    return None


def obj(title):
    """The document object behind a timeline step."""
    i = item(title)
    return doc().getObject(i.name) if i is not None else None


def click(title, modifiers=QtCore.Qt.NoModifier):
    b = button(title)
    if b is not None:
        w.click(b, w.center(b), modifiers)
    return b is not None


def double_click(title):
    b = button(title)
    if b is not None:
        w.double_click(b)
    return b is not None


def menu(title, entry):
    b = button(title)
    ok = b is not None and w.right_click(b, w.center(b), entry)
    h.check("timeline menu %s > %s" % (title, entry), ok)
    return ok


def menu_entries(title):
    """[(text, enabled)] of a step's right-click menu."""
    b = button(title)
    return w.menu_texts(b, w.center(b)) if b is not None else []


def drag_step(title, before_title=None, after_last=False):
    """Drag a step and drop it just left of another step (or after the last one)."""
    b = button(title)
    if b is None:
        return False
    if after_last:
        last = tl()._buttons[-1]
        end = last.mapToGlobal(QtCore.QPoint(last.width() + 6, last.height() // 2))
    else:
        target = button(before_title)
        if target is None:
            return False
        end = target.mapToGlobal(QtCore.QPoint(2, target.height() // 2))
    w.drag(b, w.center(b), end)
    return True


def drag_marker(before_title=None, to_end=False):
    """Drag the history marker and drop it just left of a step (or after the last)."""
    marker = tl().marker()
    if not h.check("history marker shown", marker is not None):
        return False
    if to_end:
        last = tl()._buttons[-1]
        end = last.mapToGlobal(QtCore.QPoint(last.width() + 30, last.height() // 2))
    else:
        target = button(before_title)
        if target is None:
            return False
        end = target.mapToGlobal(QtCore.QPoint(1, target.height() // 2))
    w.drag(marker, QtCore.QPoint(4, 4), end)
    return True


def playback(where):
    """Click a playback button: start, prev, play, next, end."""
    b = tl().findChild(QtWidgets.QToolButton, "SciForgeTimeline_" + where)
    if h.check("playback button %s" % where, b is not None):
        w.click(b)


def states():
    return {i.display: (i.state, i.status, i.suppressed) for i in tl().items()}


def rename_field():
    return tl().findChild(QtWidgets.QLineEdit, "SciForgeTimelineRename")


# -- the browser --------------------------------------------------------------------------
def tree():
    from sciforge import browser_ui

    t = browser_ui.widget()
    t.refresh()  # rebuilds only when the design changed (rows stay valid)
    return t


def labels():
    return tree().labels()


def row_point(label, eye=False):
    """(tree, point) of a row, read in one go so the row cannot be rebuilt in between."""
    t = tree()
    found = t.row(label)
    h.check("browser row %r" % label, found is not None, t.labels())
    if found is None:
        return t, None
    # a person scrolls to the row first (an open Origin folder can push it out of view)
    t.scrollToItem(found)
    QtWidgets.QApplication.processEvents()
    return t, (t.eye_point(found) if eye else t.label_point(found))


def click_row(label, modifiers=QtCore.Qt.NoModifier):
    t, pos = row_point(label)
    if pos is not None:
        w.click(t.viewport(), pos, modifiers)
    return pos is not None


def click_eye(label):
    t, pos = row_point(label, eye=True)
    if pos is not None:
        w.click(t.viewport(), pos)
    return pos is not None


def double_click_row(label):
    t, pos = row_point(label)
    if pos is not None:
        w.double_click(t.viewport(), pos)
    return pos is not None


def row_menu(label, entry):
    t, pos = row_point(label)
    ok = pos is not None and w.right_click(t.viewport(), pos, entry)
    h.check("browser menu %s > %s" % (label, entry), ok)
    return ok


def row_menu_entries(label):
    t, pos = row_point(label)
    return w.menu_texts(t.viewport(), pos) if pos is not None else []


def children(label):
    """Labels of the rows inside a folder row."""
    found = tree().row(label)
    if found is None:
        return None
    return [found.child(i).text(1) for i in range(found.childCount())]


def selected_rows():
    return [i.text(1) for i in tree().selectedItems()]


def selected():
    return [x.ObjectName for x in Gui.Selection.getSelectionEx()]


def browser_field():
    return tree().findChild(QtWidgets.QLineEdit)


# -- keys and buttons ------------------------------------------------------------------------
def undo():
    w.click(w.quick_access("Undo"))


def redo():
    w.click(w.quick_access("Redo"))


def ctrl(key_letter):
    """Ctrl+<letter> on the 3D view (Ctrl+Z, Ctrl+Y, Ctrl+S)."""
    h.press(getattr(QtCore.Qt, "Key_" + key_letter.upper()), QtCore.Qt.ControlModifier)


def dialog_open():
    return bool(Gui.Control.activeDialog())


def no_popups(where):
    return h.check("no pop-up after %s" % where, not h.popups(), h.popups())


def shown(obj_):
    return bool(obj_ is not None and obj_.ViewObject is not None and obj_.ViewObject.Visibility)


# FreeCAD messages a person sees as errors (red in the Report view and a pop-up balloon)
# that the harness's word list ("error", "failed"...) does not catch.
MORE_ERRORS = (
    "positionbysupport",
    "not found",
    "missing element",
    "tip shape is empty",
    "<exception>",
)
_report = {"seen": None}


def report_problems():
    """Report-view lines with one of MORE_ERRORS that appeared since the last call."""
    lines = [line.strip() for line in h.report_text().splitlines()]
    if _report["seen"] is None:
        _report["seen"] = len(lines)
    fresh = lines[_report["seen"] :]
    _report["seen"] = len(lines)
    return [line for line in fresh if any(word in line.lower() for word in MORE_ERRORS)]


def watched(steps):
    """The steps, each also checking FreeCAD's pop-up balloons (sketch_input.watched) and
    the Report view for the messages in MORE_ERRORS, after the step before."""
    from SciForgeTests.gui import sketch_input as si

    wrapped = []
    previous = ["start"]
    for one in si.watched(steps):

        def run(one=one):
            found = report_problems()
            h.check("Report view clean after %s" % previous[0], not found, found)
            previous[0] = one.__name__
            one()

        run.__name__ = one.__name__
        if hasattr(one, "wait_ms"):
            run.wait_ms = one.wait_ms
        wrapped.append(run)
    return wrapped
