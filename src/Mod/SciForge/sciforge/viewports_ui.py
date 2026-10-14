# SPDX-License-Identifier: LGPL-2.1-or-later
"""Navigation bar > Viewports, Fusion-style: Single View, or the design in several 3D views
at once (Multiple Views: Top, Front, Right and the 3D view; or two views side by side or
one above the other). Every pane is a full 3D view of the same design: click in one to
work there; each has its own camera and ViewCube. Shift+1 switches Multiple Views on and
off, like Fusion's Shift+!.

How: the extra panes are FreeCAD views of the design (Gui.Document.createView) shown side
by side in the window's view area (its sub-window mode, without title bars); Single View
closes them and puts the tabs back. Only the design's own views are tiled; the views of
other open designs wait behind until Single View.
"""

import FreeCAD as App
import FreeCADGui as Gui

from . import commands, log, nav_core, warn
from . import ui_icon_path
from .compat import QtCore, QtWidgets

GAP = 2
_STATE = {
    "layout": "Single View",
    "doc": None,  # name of the design that is split
    "base": None,  # the sub-window of the view that was there first
    "extra": [],  # sub-windows of the views made for the layout
    "hidden": [],  # sub-windows of other designs, hidden meanwhile
    "filter": None,
    "flags": None,
    "observer": None,
}


def area():
    return Gui.getMainWindow().findChild(QtWidgets.QMdiArea)


def current():
    """The layout shown now."""
    return _STATE["layout"]


def is_single():
    return current() == "Single View"


def is_two_h():
    return current() == "Two Views Horizontal"


def is_two_v():
    return current() == "Two Views Vertical"


def is_multiple():
    return current() == "Multiple Views"


def _alive(widget):
    try:
        return widget is not None and widget.parent() is not None
    except RuntimeError:
        return False


def panes():
    """The sub-windows in the layout's cells, in order: the view that was there keeps its
    camera in the 3D ("home") cell, the new views take Top, Front, Right."""
    views = nav_core.views_of(current()) if not is_single() else ["home"]
    extra = [s for s in _STATE["extra"] if _alive(s)]
    found = []
    for which in views:
        if which == "home" and _alive(_STATE["base"]):
            found.append(_STATE["base"])
        elif extra:
            found.append(extra.pop(0))
    return found


def _is_3d(sub):
    try:
        widget = sub.widget()
        return widget is not None and widget.metaObject().className() == "Gui::View3DInventor"
    except RuntimeError:
        return False


class _Resize(QtCore.QObject):
    """The panes follow the view area's size."""

    def eventFilter(self, obj, event):
        try:
            if event.type() == QtCore.QEvent.Resize and not is_single():
                QtCore.QTimer.singleShot(0, place)
        except Exception:
            pass
        return False


class _Watch:
    def slotDeletedDocument(self, doc):
        try:
            if _STATE["doc"] == doc.Name:
                QtCore.QTimer.singleShot(0, back_to_single)
        except Exception:
            pass

    def slotCreatedDocument(self, doc):
        # another design opened (New, Open): its view would float over the panes
        try:
            if not is_single():
                QtCore.QTimer.singleShot(300, _foreign_window)
        except Exception:
            pass


def back_to_single(activate=None):
    """Single View again (the split design was closed, another one opened)."""
    try:
        set_layout("Single View", quiet=True)
        if activate is not None and _alive(activate):
            area().setActiveSubWindow(activate)
    except Exception as exc:
        warn("viewports: %s" % exc)


def _foreign_window():
    """A visible view that is not one of the panes (a design opened meanwhile): back to
    tabs, with that design in front."""
    try:
        mdi = area()
        if mdi is None or is_single():
            return
        own = [s for s in [_STATE["base"]] + _STATE["extra"] if _alive(s)]
        for sub in mdi.subWindowList():
            if sub not in own and sub not in _STATE["hidden"] and sub.isVisible():
                back_to_single(activate=sub)
                return
    except Exception as exc:
        warn("viewports: %s" % exc)


def place():
    """Put the panes in their cells."""
    try:
        mdi = area()
        if mdi is None or is_single():
            return
        subs = panes()
        rect = mdi.viewport().rect()
        cells = nav_core.cells(current(), rect.width(), rect.height(), GAP)
        for sub, (x, y, w, h) in zip(subs, cells):
            try:
                sub.setGeometry(x, y, w, h)
                sub.show()
            except RuntimeError:
                continue
        _raise_bar()
    except Exception as exc:
        warn("viewports: %s" % exc)


def _raise_bar():
    try:
        from . import navbar_ui

        bar = navbar_ui.bar()
        if bar is not None:
            bar.raise_()
    except Exception:
        pass


def _turn(view, which):
    try:
        if which == "top":
            view.viewTop()
        elif which == "front":
            view.viewFront()
        elif which == "right":
            view.viewRight()
        else:
            return  # the view keeps its camera
        view.fitAll()
    except Exception as exc:
        warn("viewports: %s" % exc)


def set_layout(name, quiet=False):
    """Show the active design in `name`'s panes (Single View: back to one tabbed view)."""
    mdi = area()
    if mdi is None:
        return False
    if name == current():
        return True
    _single(mdi)
    if name == "Single View":
        if not quiet:
            log("viewports: single view")
        return True
    gui = Gui.ActiveDocument
    if gui is None or App.ActiveDocument is None:
        commands.tell("Open or start a design first.")
        return False
    base = mdi.activeSubWindow()
    if base is None or not _is_3d(base):
        commands.tell("Click in the design's 3D view first.")
        return False
    count = len(nav_core.views_of(name))
    before = list(mdi.subWindowList())
    made = []
    for _i in range(count - 1):
        view = gui.createView("Gui::View3DInventor")
        made.append(view)
    extra = [s for s in mdi.subWindowList() if s not in before]
    _STATE.update(layout=name, doc=App.ActiveDocument.Name, base=base, extra=extra)
    _STATE["flags"] = base.windowFlags()
    _STATE["hidden"] = []
    mdi.setViewMode(QtWidgets.QMdiArea.SubWindowView)
    own = [base] + extra
    for sub in mdi.subWindowList():
        if sub not in own and sub.isVisible():
            sub.hide()
            _STATE["hidden"].append(sub)
    for sub in own:
        sub.setWindowFlags(QtCore.Qt.FramelessWindowHint)
        sub.showNormal()
    if _STATE["filter"] is None:
        _STATE["filter"] = _Resize()
        mdi.viewport().installEventFilter(_STATE["filter"])
    if _STATE["observer"] is None:
        _STATE["observer"] = _Watch()
        App.addDocumentObserver(_STATE["observer"])
    place()
    # each new pane's own camera: Top, Front, Right (the first view keeps its own)
    others = [w for w in nav_core.views_of(name) if w != "home"]
    for view, which in zip(made, others):
        _turn(view, which)
    mdi.setActiveSubWindow(base)
    _after_change()
    log("viewports: %s" % name.lower())
    return True


def _single(mdi):
    """Close the extra panes, tabs again, the first view filling the area."""
    if is_single():
        return
    base = _STATE["base"]
    for sub in list(_STATE["extra"]):
        try:
            if _alive(sub):
                sub.close()
        except RuntimeError:
            pass
    for sub in _STATE["hidden"]:
        try:
            if _alive(sub):
                sub.show()
        except RuntimeError:
            pass
    try:
        if _alive(base):
            base.setWindowFlags(_STATE["flags"] or QtCore.Qt.SubWindow)
    except RuntimeError:
        pass
    mdi.setViewMode(QtWidgets.QMdiArea.TabbedView)
    try:
        if _alive(base):
            base.showMaximized()
            mdi.setActiveSubWindow(base)
    except RuntimeError:
        pass
    _STATE.update(layout="Single View", doc=None, base=None, extra=[], hidden=[], flags=None)
    _after_change()


def _after_change():
    _raise_bar()
    try:
        from . import component_colors_ui, display_ui

        display_ui.apply_all()
        component_colors_ui.refresh_views()
    except Exception as exc:
        warn("viewports: %s" % exc)


def toggle_multiple():
    """Shift+1: Multiple Views, or back to a single view."""
    return set_layout("Single View" if not is_single() else "Multiple Views")


def _command(name, tip, icon):
    class Command:
        def GetResources(self):
            return {"MenuText": name, "ToolTip": tip, "Pixmap": ui_icon_path(icon)}

        def IsActive(self):
            return True

        def Activated(self):
            try:
                set_layout(name)
            except Exception as exc:
                warn("viewports: %s" % exc)

    return Command


class ToggleCommand:
    def GetResources(self):
        return {
            "MenuText": "Multiple Views on / off",
            "ToolTip": "Show the design in four views (Top, Front, Right, 3D), or one again",
            "Pixmap": ui_icon_path("nav_viewports"),
        }

    def IsActive(self):
        return True

    def Activated(self):
        try:
            toggle_multiple()
        except Exception as exc:
            warn("viewports: %s" % exc)


COMMANDS = {
    "SciForge_ViewportSingle": _command("Single View", "One 3D view", "view_single"),
    "SciForge_ViewportTwoHorizontal": _command(
        "Two Views Horizontal", "Two 3D views side by side", "view_two_h"
    ),
    "SciForge_ViewportTwoVertical": _command(
        "Two Views Vertical", "Two 3D views one above the other", "view_two_v"
    ),
    "SciForge_ViewportMultiple": _command(
        "Multiple Views", "Four views: Top, Front, Right and 3D", "nav_viewports"
    ),
    "SciForge_ViewportsToggle": ToggleCommand,
}
