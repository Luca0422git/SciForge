# SPDX-License-Identifier: LGPL-2.1-or-later
"""Turns the SciForge interface on and off as a whole.

The interface is not tied to the SciForge workbench being active: editing a
sketch makes FreeCAD switch to its Sketcher workbench, but Fusion keeps the
same window and just adds a SKETCH tab. So:

  * SciForge workbench activated          -> interface on (SOLID tab)
  * Sketcher activated while it is on     -> stays on, SKETCH tab shown
  * any other workbench activated         -> interface off, FreeCAD as before

Everything changed while on (theme, toolbars, menu bar, shortcuts, docks) is
put back when it turns off.
"""
from . import config, log, warn
from .compat import QtCore, QtWidgets

SCIFORGE_WB = "SciForgeWorkbench"
SKETCH_WB = "SketcherWorkbench"

_state = {
    "on": False,
    "connected": False,
    "ribbon": None,
    "hidden": [],
    "menubar": None,
    "panels": [],
}


def is_on():
    return _state["on"]


def ribbon():
    return _state["ribbon"]


def _main():
    import FreeCADGui as Gui

    return Gui.getMainWindow()


def _connect():
    if _state["connected"]:
        return
    try:
        _main().workbenchActivated.connect(on_workbench)
        _state["connected"] = True
    except Exception as exc:
        warn("cannot follow workbench changes: %s" % exc)


def on_workbench(name):
    """Called for every workbench change (Qt signal) and from SciForge's Activated()."""
    try:
        name = str(name)
        if name == SCIFORGE_WB:
            enable()
            _set_sketch_mode(False)
        elif name == SKETCH_WB and _state["on"]:
            # FreeCAD just put the Sketcher's toolbars up; hide them after it is done.
            _hide_toolbars_soon()
            _set_sketch_mode(True)
        elif _state["on"]:
            disable()
    except Exception as exc:
        warn("workbench change to %s: %s" % (name, exc))


def _set_sketch_mode(on):
    if _state["ribbon"] is not None:
        _state["ribbon"].set_sketch_mode(on)


def _sketch_mode_on():
    """Fusion's sketch environment (Esc, dimension box, palette, profiles, colours)."""
    from . import sketch_mode

    sketch_mode.enable()


def _sketch_mode_off():
    from . import sketch_mode

    sketch_mode.disable()


def enable():
    _connect()
    if not config.USE_RIBBON:  # legacy mode: plain toolbars, no theme
        if not _state["on"]:
            from . import shortcuts, timeline_ui

            _state["on"] = True
            shortcuts.apply()
            timeline_ui.show()
            _safely(_sketch_mode_on)
        return
    if _state["on"]:
        _hide_toolbars_soon()
        return
    from . import navbar_ui, shortcuts, theme, timeline_ui

    _state["on"] = True
    theme.apply()
    _show_ribbon()
    _hide_toolbars()
    _hide_menubar()
    _safely(lambda: __import__("sciforge.browser_ui").browser_ui.show())
    _install_close_guard()
    _hide_panels()
    shortcuts.apply()
    timeline_ui.show()
    navbar_ui.show()
    _safely(lambda: __import__("sciforge.marking_menu").marking_menu.enable())
    _safely(_sketch_mode_on)
    log("interface on")


def disable():
    if not _state["on"]:
        return
    from . import navbar_ui, shortcuts, theme, timeline_ui

    _state["on"] = False
    _safely(_sketch_mode_off)
    if not config.USE_RIBBON:
        shortcuts.restore()
        timeline_ui.hide()
        return
    for step in (
        lambda: __import__("sciforge.marking_menu").marking_menu.disable(),
        shortcuts.restore,
        timeline_ui.hide,
        navbar_ui.hide,
        _restore_panels,
        _restore_menubar,
        _restore_toolbars,
        _hide_ribbon,
        lambda: __import__("sciforge.browser_ui").browser_ui.hide(),
        theme.restore,
    ):
        try:
            step()
        except Exception as exc:
            warn("turning interface off: %s" % exc)
    log("interface off")


# -- ribbon ------------------------------------------------------------
def _show_ribbon():
    from .ribbon_ui import RibbonWidget

    main = _main()
    holder = main.findChild(QtWidgets.QToolBar, "SciForgeRibbonBar")
    if holder is None:
        holder = QtWidgets.QToolBar("SciForge Ribbon", main)
        holder.setObjectName("SciForgeRibbonBar")
        holder.setMovable(False)
        holder.setFloatable(False)
        holder.setContentsMargins(0, 0, 0, 0)
        holder.layout().setContentsMargins(0, 0, 0, 0)
        holder.toggleViewAction().setVisible(False)  # not listed, never saved as hidden
        _state["ribbon"] = RibbonWidget(holder)
        holder.addWidget(_state["ribbon"])
        main.addToolBar(QtCore.Qt.TopToolBarArea, holder)
    holder.show()


def _hide_ribbon():
    holder = _main().findChild(QtWidgets.QToolBar, "SciForgeRibbonBar")
    if holder is not None:
        holder.hide()


# -- FreeCAD's own toolbars and menu bar ----------------------------------
def _hide_toolbars_soon():
    """FreeCAD (re)shows a workbench's toolbars after announcing the switch, partly
    from its own timers, so hide again once it is done."""
    for delay in (0, 150, 600):
        QtCore.QTimer.singleShot(delay, lambda: _state["on"] and _hide_toolbars())


def _hide_toolbars():
    """Hide every other toolbar. Hiding the toggle action first makes FreeCAD's
    ToolBarManager::saveState() skip the toolbar, so the hidden state is never
    written to the user's preferences."""
    known = {id(bar) for bar, _ in _state["hidden"]}
    for bar in _main().findChildren(QtWidgets.QToolBar):
        if bar.objectName() == "SciForgeRibbonBar" or not bar.isVisible():
            continue
        action = bar.toggleViewAction()
        if id(bar) not in known:  # remember the state from before SciForge only
            _state["hidden"].append((bar, action.isVisible()))
        action.setVisible(False)
        bar.hide()


# Toolbars FreeCAD shows in every workbench.
GLOBAL_TOOLBARS = {
    "File",
    "Edit",
    "Workbench",
    "View",
    "Structure",
    "Help",
    "Macro",
    "Clipboard",
    "Individual views",
    "Navigation",
}


def _restore_toolbars():
    """Give the toolbars back. Show only those that belong to the workbench being
    switched to; FreeCAD already decided the rest while SciForge had them hidden."""
    import FreeCADGui as Gui

    try:
        wanted = set(Gui.activeWorkbench().listToolbars()) | GLOBAL_TOOLBARS
    except Exception:
        wanted = GLOBAL_TOOLBARS
    for bar, action_visible in _state["hidden"]:
        try:
            bar.toggleViewAction().setVisible(action_visible)
            if bar.objectName() in wanted:
                bar.show()
        except RuntimeError:  # toolbar deleted by FreeCAD meanwhile
            pass
    _state["hidden"] = []


def _hide_menubar():
    bar = _main().menuBar()
    _state["menubar"] = bar.isVisible()
    bar.hide()


def _restore_menubar():
    if _state["menubar"]:
        _main().menuBar().show()
    _state["menubar"] = None


class _CloseGuard(QtCore.QObject):
    """FreeCAD saves toolbar/dock layout when its window closes. Turn SciForge off
    first so only FreeCAD's own layout is saved; if the close is cancelled (unsaved
    changes > Cancel), turn it back on."""

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.Close and _state["on"]:
            disable()
            QtCore.QTimer.singleShot(0, _reenable_if_still_open)
        return False


def _reenable_if_still_open():
    import FreeCADGui as Gui

    try:
        main = _main()
        if main.isVisible() and Gui.activeWorkbench().name() == SCIFORGE_WB:
            enable()
    except Exception:
        pass


_guard = {"filter": None}


def _install_close_guard():
    if _guard["filter"] is None:
        _guard["filter"] = _CloseGuard()
        _main().installEventFilter(_guard["filter"])


def _hide_panels():
    """Fusion has no property editor under the browser and no status bar."""
    main = _main()
    panels = [
        w
        for w in main.findChildren(QtWidgets.QWidget)
        if w.metaObject().className() == "Gui::PropertyView"
    ]
    panels.append(main.statusBar())
    for widget in panels:
        if widget.isVisible():
            _state["panels"].append(widget)
            widget.hide()


def _restore_panels():
    for widget in _state["panels"]:
        try:
            widget.show()
        except RuntimeError:
            pass
    _state["panels"] = []


def _safely(step):
    try:
        step()
    except Exception as exc:
        warn("interface: %s" % exc)
