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


def at_launch():
    """From InitGui.py, before FreeCAD picks the workbench it opens in."""
    apply()
