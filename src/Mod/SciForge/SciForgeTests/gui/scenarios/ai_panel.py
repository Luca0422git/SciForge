# SPDX-License-Identifier: LGPL-2.1-or-later
"""The AI panel (docs/sciforge/parity/ai.md; Luca, 2026-10-19), with real clicks.

Path 1, in an open design: UTILITIES > AI opens the AI panel at the right; its title bar
  has an X; the X closes it; AI again opens it, and once more closes it (a toggle).
Path 2, its AI control switch turns the option on and off; Home's switch follows.
Path 3, Your AIs: none added says so; two chat keys kept (Claude, ChatGPT) show as two AIs,
  each with its badge, on the panel and on Home; double-click Claude: the Chat tab with
  Claude chosen. The keys are removed again.
Path 4, Home: the browser is closed while Home is in front and back on the design; Home's
  Preferences button opens SciForge's Preferences.
"""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import widget_input as wi

s = {}
KEYS = {"anthropic": "sk-ant-TEST-111", "openai": "sk-TEST-222"}


def page():
    from sciforge import ai_panel_ui

    return ai_panel_ui.panel()


def shown():
    from sciforge import ai_panel_ui

    return ai_panel_ui.is_shown()


def utilities():
    from sciforge import shell

    wi.click(shell.ribbon().tab_buttons["utilities"])


def big(label):
    for button in h.ribbon_buttons():
        if button.objectName() == "SciForgeBig_" + label.replace(" ", "_"):
            return button
    return None


# -- Path 1 -------------------------------------------------------------------------------
def setup():
    from sciforge import commands
    from sciforge.ai import bridge

    s["allowed"] = bridge.allowed()
    App.newDocument("AIPanel")
    commands.ensure_body()
    utilities()


def ai_button():
    button = big("AI")
    h.check("UTILITIES has an AI button", button is not None)
    h.check("... with its own icon", button is not None and not button.icon().isNull())
    if button is not None:
        wi.click(button)


def panel_open():
    from sciforge import ai_panel_ui

    h.check("AI opened the AI panel in the design", shown())
    dock = ai_panel_ui.dock()
    main = Gui.getMainWindow()
    h.check(
        "... at the right",
        main.dockWidgetArea(dock) == QtCore.Qt.RightDockWidgetArea,
        main.dockWidgetArea(dock),
    )
    close = dock.titleBarWidget().close_button
    h.check("its title bar has an X", close.isVisible() and not close.icon().isNull())
    h.shot("panel")
    wi.click(close)


def x_closed():
    h.check("the X closed the panel", not shown())
    wi.click(big("AI"))


def opened_again():
    h.check("AI opened it again", shown())
    wi.click(big("AI"))


def toggled_closed():
    h.check("AI once more closed it (a toggle)", not shown())
    wi.click(big("AI"))


# -- Path 2 -------------------------------------------------------------------------------
def switch_on():
    from sciforge.ai import bridge

    bridge.set_allowed(False)
    page().refresh()
    h.check("the switch shows AI control off", not page().toggle.isChecked())
    wi.click(page().toggle)


def switched_on():
    from sciforge import home_ui
    from sciforge.ai import bridge

    h.check("the switch turned AI control on", bridge.allowed())
    h.check("... and says so", "On:" in page().toggle_state.text(), page().toggle_state.text())
    home = home_ui.view()
    h.check("Home's switch follows", home is None or home.ai_toggle.isChecked())
    wi.click(page().toggle)


def switched_off():
    from sciforge.ai import bridge

    h.check("the switch turned it off again", not bridge.allowed())


# -- Path 3 -------------------------------------------------------------------------------
def no_ai_yet():
    from sciforge import secrets_store
    from sciforge.ai import chat_ui

    for name in KEYS:
        secrets_store.delete(chat_ui.key_name(name), chat_ui.secrets_folder())
    s["address"] = App.ParamGet(chat_ui.PREFS).GetString("ChatAddress", "")
    App.ParamGet(chat_ui.PREFS).RemString("ChatAddress")
    page().refresh()
    names = [n for n in page().names() if n.startswith(("Claude (", "ChatGPT", "Gemini ("))]
    h.check("no chat AI listed before a key is kept", names == [], page().names())


def keep_two_keys():
    from sciforge import secrets_store
    from sciforge.ai import chat_ui

    for name, key in KEYS.items():
        secrets_store.store(chat_ui.key_name(name), key, chat_ui.secrets_folder())
    from sciforge import ai_ui

    ai_ui._refresh_home()


def two_ais_listed():
    from sciforge import home_ui

    names = page().names()
    h.check(
        "both AIs are listed",
        "Claude (Anthropic)" in names and "ChatGPT (OpenAI)" in names,
        names,
    )
    icons = [page().apps.item(i).icon().isNull() for i in range(page().apps.count())]
    h.check("each with its badge", icons and not any(icons), icons)
    home = home_ui.view()
    h.check(
        "Home lists them too",
        home is not None and "Claude (Anthropic)" in home.ai_names(),
        home and home.ai_names(),
    )
    h.shot("ais")
    apps = page().apps
    for i in range(apps.count()):
        if apps.item(i).text().startswith("Claude (Anthropic)"):
            wi.double_click(apps.viewport(), apps.visualItemRect(apps.item(i)).center())


def claude_chosen():
    p = page()
    h.check("double-click: the Chat tab", p.tabs.currentWidget() is p.chat)
    h.check("... with Claude chosen", p.chat.provider_name() == "anthropic", p.chat.provider_name())
    from sciforge import secrets_store
    from sciforge.ai import chat_ui

    for name in KEYS:
        secrets_store.delete(chat_ui.key_name(name), chat_ui.secrets_folder())
    if s.get("address"):
        App.ParamGet(chat_ui.PREFS).SetString("ChatAddress", s["address"])
    p.refresh()
    h.check("the keys are gone again", "Claude (Anthropic)" not in p.names(), p.names())


# -- Path 4 -------------------------------------------------------------------------------
def browser_dock():
    from sciforge import browser_ui

    return browser_ui._state.get("dock")


def to_home():
    h.check("the browser shows on the design", browser_dock().isVisible())
    wi.click(wi.quick_access("Home"))


def browser_closed_on_home():
    from sciforge import home_ui

    h.check("Home is in front", home_ui.is_active())
    h.check("the browser is closed on Home", not browser_dock().isVisible())
    h.shot("home")
    wi.click(home_ui.view().preferences_button)


def preferences_open():
    dialog = None
    for w in QtWidgets.QApplication.topLevelWidgets():
        if w.objectName() == "SciForgePreferences" and w.isVisible():
            dialog = w
    h.check("Home's Preferences opened SciForge's Preferences", dialog is not None)
    if dialog is not None:
        dialog.reject()
    bar = h.document_tabs()
    for i in range(bar.count()):
        if bar.tabText(i).startswith("AIPanel"):
            wi.click(bar, bar.tabRect(i).center())


def browser_back():
    from sciforge.ai import bridge

    h.check("the browser is back on the design", browser_dock().isVisible())
    bridge.set_allowed(s["allowed"])
    h.check("no pop-up left", not h.popups(), h.popups())


h.run(
    "ai_panel",
    [
        setup,
        ai_button,
        panel_open,
        x_closed,
        opened_again,
        toggled_closed,
        switch_on,
        switched_on,
        switched_off,
        no_ai_yet,
        keep_two_keys,
        two_ais_listed,
        claude_chosen,
        to_home,
        browser_closed_on_home,
        preferences_open,
        browser_back,
    ],
)
