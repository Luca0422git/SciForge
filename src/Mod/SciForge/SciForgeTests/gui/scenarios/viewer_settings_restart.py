# SPDX-License-Identifier: LGPL-2.1-or-later
"""SciForge puts FreeCAD's own viewer settings back when it is switched off, also after a
session that ended with SciForge on (FreeCAD saves its preferences when it quits, with
SciForge's values in them).

Found on GitHub: each test part shares one FreeCAD profile, so an earlier scenario had quit
with SciForge on; viewcube_menu then switched to Part Design and FreeCAD's own cube did not
come back, because SciForge had taken its own values for the user's. A user who quits with
SciForge on and later uses another workbench would have met the same.

A new session is imitated by reloading SciForge's theme module (its memory is gone, the
preferences stay), as when FreeCAD starts again:
  1. Before SciForge: FreeCAD's cube is shown. SciForge on: it is hidden, the orbit is the
     turntable.
  2. "Restart" with SciForge on, then Part Design: FreeCAD's cube is back and every setting
     SciForge changes is as it was before SciForge.
  3. SciForge on again; "restart" and go to Part Design without SciForge ever being on in
     that session: the same.
"""
import importlib

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import harness as h

st = {}


def preferences():
    """The values of the settings SciForge changes (None: not set, FreeCAD's default)."""
    from sciforge import theme

    found = {}
    for path, kind, name, _ in theme.VIEWER_SETTINGS:
        group = App.ParamGet(path)
        exists = name in getattr(group, "Get" + kind + "s")()
        found["%s/%s" % (path.split("/")[-1], name)] = (
            getattr(group, "Get" + kind)(name) if exists else None
        )
    return found


def navicube_on():
    return h.view().getViewer().isEnabledNaviCube()


def differences():
    now = preferences()
    return {k: (st["before"][k], now[k]) for k in now if now[k] != st["before"].get(k)}


def start():
    Gui.activateWorkbench("PartDesignWorkbench")
    App.newDocument("ViewerRestart")
    st["before"] = preferences()


def before_sciforge():
    h.check("before SciForge, FreeCAD's cube is shown", navicube_on())
    Gui.activateWorkbench("SciForgeWorkbench")


def sciforge_on():
    h.check("with SciForge, FreeCAD's cube is hidden", not navicube_on())
    orbit = App.ParamGet("User parameter:BaseApp/Preferences/View").GetInt("OrbitStyle")
    h.check("with SciForge, the turntable orbit", orbit == 2, orbit)
    # A new session with SciForge on: the theme's memory is gone, the preferences stay.
    from sciforge import theme

    importlib.reload(theme)
    theme.apply()
    Gui.activateWorkbench("PartDesignWorkbench")


def restored_after_restart():
    h.check("after a restart with SciForge on, FreeCAD's cube is back", navicube_on())
    h.check("every setting is as before SciForge", not differences(), differences())
    Gui.activateWorkbench("SciForgeWorkbench")


def on_again():
    h.check("SciForge on again: FreeCAD's cube hidden", not navicube_on())
    # A new session that starts in another workbench: SciForge never comes on in it.
    from sciforge import shell, theme

    importlib.reload(theme)
    shell._state["on"] = False
    Gui.activateWorkbench("PartDesignWorkbench")


def restored_elsewhere():
    h.check("a session in another workbench gets FreeCAD's cube back", navicube_on())
    h.check("and every setting as before SciForge", not differences(), differences())


h.run(
    "viewer_settings_restart",
    [start, before_sciforge, sciforge_on, restored_after_restart, on_again, restored_elsewhere],
)
