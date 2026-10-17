# SPDX-License-Identifier: LGPL-2.1-or-later
"""SciForge is the workbench FreeCAD opens in (Luca, 2026-10-16: "SciForge automatically
active on startup"). Fusion opens straight into its design workspace; FreeCAD opens in the
workbench of its preference General/AutoloadModule and shows its Start page.

How: SciForge's InitGui.py calls `at_launch()`. FreeCAD runs every module's InitGui.py first
and only then reads AutoloadModule to pick the workbench (Gui/StartupProcess.cpp,
activateWorkbench), so the value set here counts for this very launch. FreeCAD's Start
migrator (Mod/Start/StartMigrator.py) only rewrites AutoloadModule while it still says
"StartWorkbench", so it never undoes this.

The user's own values are kept (theme.keep_and_set) and given back when the Preferences
option "Start in SciForge" is switched off.
"""

from . import log, warn

GENERAL = "User parameter:BaseApp/Preferences/General"
START = "User parameter:BaseApp/Preferences/Mod/Start"
OPTION = ("User parameter:BaseApp/Preferences/Mod/SciForge", "StartInSciForge")
BACKUP = "User parameter:BaseApp/Preferences/Mod/SciForge/StartupBackup"
WORKBENCH = "SciForgeWorkbench"
THEME_DONE = "FirstStartThemeApplied"  # (in OPTION's group)

# (path, kind, name, SciForge's value), as theme.VIEWER_SETTINGS
SETTINGS = [
    (GENERAL, "String", "AutoloadModule", WORKBENCH),
    (START, "Bool", "ShowOnStartup", False),  # no Start page: straight into the design space
]


def wanted():
    """The Preferences option (on unless switched off)."""
    import FreeCAD as App

    path, name = OPTION
    return App.ParamGet(path).GetBool(name, True)


def is_set():
    """Both of SciForge's values are in FreeCAD's preferences."""
    import FreeCAD as App

    for path, kind, name, val in SETTINGS:
        group = App.ParamGet(path)
        if name not in getattr(group, "Get" + kind + "s")():
            return False
        if getattr(group, "Get" + kind)(name) != val:
            return False
    return True


def apply(on=None):
    """On: FreeCAD opens in SciForge without its Start page (the user's values kept); off: the
    user's own values back. Takes effect at the next launch."""
    try:
        from . import theme

        if on is None:
            on = wanted()
        if on:
            if not is_set():
                theme.keep_and_set(SETTINGS, BACKUP)
                log("FreeCAD opens in SciForge from now on")
        else:
            import FreeCAD as App

            if App.ParamGet(BACKUP).GetStrings():
                theme.give_back(SETTINGS, BACKUP)
                log("FreeCAD opens in its own start workbench again")
    except Exception as exc:
        warn("start in SciForge: %s" % exc)


# FreeCAD's floating panel on the right (the Tasks panel with the command dialogs)
OVERLAY_RIGHT = "User parameter:BaseApp/MainWindow/DockWindows/OverlayRight"
PANEL_WIDTH = 382  # what a fresh FreeCAD gives it when it opens in its own workbench


def _panel_width():
    """A fresh profile: FreeCAD sizes the right panel from the main window's minimum size
    when it is made and keeps that width for good (Gui/OverlayWidgets.cpp). Opening in
    SciForge, the ribbon is already there and the panel came out 559 px instead of 382:
    the dialogs covered a third more of the 3D view. A width already kept (the user's) is
    left as it is."""
    import FreeCAD as App

    group = App.ParamGet(OVERLAY_RIGHT)
    if group.GetInt("Width", 0) <= 100:  # (FreeCAD treats up to 100 as not set either)
        group.SetInt("Width", PANEL_WIDTH)
        # with a width kept FreeCAD reads the panel's list of docks as set by the user and
        # an unset list as empty (the Tasks panel then sat beside the view, not over it)
        if "Widgets" not in group.GetStrings():
            group.SetString("Widgets", "Tasks,")


def _system_dark():
    try:
        from .compat import QtCore, QtGui

        scheme = QtGui.QGuiApplication.styleHints().colorScheme()
        return scheme == QtCore.Qt.ColorScheme.Dark
    except Exception:
        return False


def _first_start_theme():
    """What FreeCAD's Start page does on a fresh profile (Mod/Start ThemeSelectorWidget):
    no theme chosen yet, so the FreeCAD Light preference pack (Dark when the system is
    dark) is applied: body colour, line and sketch colours, and more. Opening in SciForge
    skips the Start page, and a fresh install came out in FreeCAD's old Classic colours
    (bodies lavender, not grey). A theme already chosen is left as it is."""
    import os
    import tempfile
    import xml.etree.ElementTree as ET

    import FreeCAD as App

    window = App.ParamGet("User parameter:BaseApp/Preferences/MainWindow")
    if "StyleSheet" in window.GetStrings():
        return  # a theme was chosen (by the Start page, a pack, the user)
    marks = App.ParamGet(OPTION[0])
    if marks.GetBool(THEME_DONE, False):
        return  # applied once already (SciForge's own look stays on)
    name = "FreeCAD Dark" if _system_dark() else "FreeCAD Light"
    path = os.path.join(App.getResourceDir(), "Gui", "PreferencePacks", name, name + ".cfg")
    if not os.path.isfile(path):
        return
    # FreeCAD inserts the pack's BaseApp group into the user's (PreferencePack::
    # applyConfigChanges); Python reaches BaseApp, not the top, so the file is re-rooted
    root = ET.parse(path).getroot().find("FCParamGroup")
    base = [g for g in root.findall("FCParamGroup") if g.get("Name") == "BaseApp"]
    if not base:
        return
    out = ET.Element("FCParameters")
    top = ET.SubElement(out, "FCParamGroup", Name="Root")
    for child in list(base[0]):
        top.append(child)
    # Its colours only, not its window style (MainWindow: StyleSheet, QtStyle, Theme) nor
    # its accent colours (Themes): a change to either makes FreeCAD load its stylesheet
    # again a moment later, over SciForge's own look (the first start came out with a
    # light ribbon and greyed icons). SciForge's look has its own colours.
    for prefs in top.findall("FCParamGroup"):
        if prefs.get("Name") == "Preferences":
            for group in prefs.findall("FCParamGroup"):
                if group.get("Name") in ("MainWindow", "Themes"):
                    prefs.remove(group)
    handle, temp = tempfile.mkstemp(suffix=".cfg")
    os.close(handle)
    try:
        ET.ElementTree(out).write(temp, encoding="UTF-8", xml_declaration=True)
        App.ParamGet("User parameter:BaseApp").Insert(temp)
    finally:
        os.remove(temp)
    marks.SetBool(THEME_DONE, True)
    log("the %s theme's colours applied (a fresh profile; FreeCAD's Start page would have)" % name)


def at_launch():
    """From InitGui.py, before FreeCAD picks the workbench it opens in."""
    apply()
    try:
        if wanted():
            _first_start_theme()
            _panel_width()
    except Exception as exc:
        warn("start in SciForge: first start: %s" % exc)
