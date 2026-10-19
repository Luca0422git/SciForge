# SPDX-License-Identifier: LGPL-2.1-or-later
"""SciForge's light look (Luca, 2026-10-19: "people like the blinding white of default
fusion... a preferences button on the home screen would be nice"), with real clicks.

Path 1, Home > Preferences > General > Look: Light, Apply: the window turns light at once
  (the app's style, Home, the ribbon made again with dark-stroked icons, the AI panel's own
  style), the 3D view's background is light, sketches draw fully defined curves black.
Path 2, a design in the light look: its tab, the ribbon's commands, the browser.
Path 3, Look: Dark again: everything as before (style, background, sketch colours).
"""

import os

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtWidgets

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import widget_input as wi

s = {}
VIEW = "User parameter:BaseApp/Preferences/View"


def preferences():
    for w in QtWidgets.QApplication.topLevelWidgets():
        if w.objectName() == "SciForgePreferences" and w.isVisible():
            return w
    return None


def background():
    return App.ParamGet(VIEW).GetUnsigned("BackgroundColor", 0)


def fully_defined():
    return App.ParamGet(VIEW).GetUnsigned("FullyConstrainedColor", 0)


# -- Path 1 -------------------------------------------------------------------------------
def open_preferences():
    from sciforge import home_ui, theme

    from sciforge import sketch_palette

    h.check("SciForge starts dark", not theme.is_light())
    # (Luca, 2026-10-19: the sketch palette came out light grey in the dark look: the swap
    # back from light turned the dark chrome #3b4453, also the light marker, into #e8e8e8)
    changed = [
        c for c in list(theme.DARK.values()) + list(theme.TO_LIGHT) if theme.translate(c) != c
    ]
    h.check("the dark look leaves the dark colours as they are", changed == [], changed)
    h.check(
        "... the sketch palette's style unchanged",
        theme.translate(sketch_palette.STYLE) == sketch_palette.STYLE,
    )
    s["dark_background"] = background()
    s["dark_sketch"] = fully_defined()
    home_ui.show()
    wi.click(home_ui.view().preferences_button)


def choose_light():
    dialog = preferences()
    h.check("Home's Preferences opened the Preferences", dialog is not None)
    if dialog is None:
        return
    combo = dialog.findChild(QtWidgets.QComboBox, "SciForgePref_theme")
    h.check("General has Look", combo is not None)
    if combo is None:
        return
    h.check(
        "... Dark or Light",
        [combo.itemData(i) for i in range(combo.count())] == ["dark", "light"],
        [combo.itemText(i) for i in range(combo.count())],
    )
    combo.setCurrentIndex(combo.findData("light"))
    wi.click(dialog.findChild(QtWidgets.QPushButton, "SciForgePreferencesOK"))


choose_light.wait_ms = 1500


def light_now():
    from sciforge import home_ui, shell, theme, ui_icon_path

    h.check("the look is light", theme.is_light() and theme.current() == "light")
    app_style = QtWidgets.QApplication.instance().styleSheet()
    h.check(
        "the window's style is light",
        "QMainWindow, QMainWindow > QWidget { background: #f0f2f5;" in app_style,
        app_style[:160],
    )
    h.check("the 3D view's background is light", background() != s["dark_background"])
    h.check("sketches: fully defined curves dark", fully_defined() != s["dark_sketch"])
    path = ui_icon_path("qa_home")
    h.check("icons have dark strokes", "icons-light" in path and os.path.isfile(path), path)
    with open(path, encoding="utf-8") as handle:
        h.check("... no light stroke left", "#dfe3e8" not in handle.read().lower())
    ribbon = shell.ribbon()
    h.check("the ribbon was made again", ribbon is not None and ribbon.isVisible())
    page = home_ui.view()
    style = page.styleSheet() if page is not None else ""
    h.check("Home is light", "#f7f8fa" in style and "#2a2a2a" not in style)
    h.check("no pop-up left", not h.popups(), h.popups())
    h.shot("home-light")


light_now.wait_ms = 1500


# -- Path 2 -------------------------------------------------------------------------------
def design_light():
    from sciforge import ai_panel_ui, commands

    App.newDocument("LightLook")
    commands.ensure_body()
    ai_panel_ui.show("chat")


def design_shown():
    from sciforge import ai_panel_ui, shell

    h.check("the ribbon's commands show on the design", shell.ribbon().command_area.isVisible())
    style = ai_panel_ui.panel().styleSheet()
    h.check("the AI panel is light too", "#f0f2f5" in style and "#3b4453" not in style, style[:120])
    h.fit()
    h.shot("design-light")


design_shown.wait_ms = 1000


# -- Path 3 -------------------------------------------------------------------------------
def back_to_dark():
    from sciforge import preferences_ui

    preferences_ui.save({"theme": "dark"})


def dark_again():
    from sciforge import ai_panel_ui, theme, ui_icon_path

    h.check("the look is dark again", not theme.is_light() and theme.current() == "dark")
    app_style = QtWidgets.QApplication.instance().styleSheet()
    h.check(
        "the window's style is dark",
        "QMainWindow, QMainWindow > QWidget { background: #3b4453;" in app_style
        and "#f0f2f5" not in app_style,
        app_style[:160],
    )
    h.check("the 3D view's background is dark again", background() == s["dark_background"])
    h.check("sketch colours as before", fully_defined() == s["dark_sketch"])
    h.check("icons as made", "icons-light" not in ui_icon_path("qa_home"))
    style = ai_panel_ui.panel().styleSheet()
    h.check("the AI panel is dark again", "#3b4453" in style and "#f0f2f5" not in style)
    ai_panel_ui.dock().close()
    Gui.updateGui()
    h.check("no pop-up left", not h.popups(), h.popups())


h.run(
    "look_light",
    [
        open_preferences,
        choose_light,
        light_now,
        design_light,
        design_shown,
        back_to_dark,
        dark_again,
    ],
)
