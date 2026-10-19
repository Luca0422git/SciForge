# SPDX-License-Identifier: LGPL-2.1-or-later
"""SciForge's look (dark, its own, or light like Fusion's default) and Fusion-like viewer
settings.

Dark colours were measured from screenshots of Fusion's stock dark theme
(docs/sciforge/parity/ui-shell.md); the light ones follow Fusion's default white look
(Luca, 2026-10-19: "people like the blinding white of default fusion"), chosen in
Preferences > General > Look (Home's Preferences button). Everything changed here is
remembered and put back by restore(), so leaving SciForge returns FreeCAD exactly as it was.

The light look changes the app's style sheet, the style sheets SciForge's panels set
themselves (written with the dark colours: translate() swaps them, a hook on setStyleSheet
does it as they are set), the icons' light strokes (ui_icon), the 3D view's background and
the sketch colours. Switching is live; a few icons of FreeCAD's own menus change at the next
start.
"""

import re

from . import log, ui_icon_path, warn

PREF = ("User parameter:BaseApp/Preferences/Mod/SciForge", "Theme")
THEMES = ("dark", "light")

DARK = dict(
    chrome="#3b4453",  # ribbon, panels, timeline
    menu="#454f61",  # drop-down menus
    view="#2a2a2a",  # 3D view background
    text="#f5f5f5",
    text_dim="#c3cad4",
    disabled="#7d8593",
    hover="#56647a",
    active="#354a63",  # pressed / open group label
    line="#56606f",  # separators
    accent="#3fa9f5",
    field="#2f3540",  # text boxes
    button="#4a5568",
    header="#2f3643",
    alternate="#303030",  # every other row
    tree_hover="#3a4252",
    handle="#5d6778",  # scroll bars
    check="#2b313b",
    check_line="#8a94a3",
    marker="#e8e8e8",  # the timeline's history marker
    bright="#ffffff",
)
LIGHT = dict(
    chrome="#f0f2f5",
    menu="#ffffff",
    view="#f7f8fa",
    text="#1f2329",
    text_dim="#5b6573",
    disabled="#9aa3ae",
    hover="#dde5ef",
    active="#cde2f7",
    line="#c9ced6",
    accent="#3fa9f5",
    field="#ffffff",
    button="#e6eaf0",
    header="#e3e7ec",
    alternate="#f4f6f8",
    tree_hover="#e8eef5",
    handle="#b8bfc9",
    check="#ffffff",
    check_line="#8a94a3",
    marker="#3b4453",
    bright="#000000",
)

# The dark colours SciForge's own panels write in their style sheets, and their light ones.
# White and black are never swapped (text on blue buttons, a drawing's paper).
_EXTRA = {
    "#343a46": "#e3e8ef",
    "#3b4250": "#d5dae1",
    "#2f3540": "#ffffff",
    "#b8c7d9": "#4a5a70",
    "#8cc4ff": "#1f6fbf",
    "#9aa4b1": "#5f6977",
    "#9aa4b2": "#5f6977",
    "#9aa4b5": "#5f6977",
    "#8a94a6": "#5f6977",
    "#9fb3c8": "#4f6378",
    "#b8c4d0": "#4f5b68",
    "#b9bec6": "#5f6977",
    "#9fb4cc": "#3d5f85",
    "#ff8a80": "#c62828",
    "#ef6f6c": "#c62828",
    "#ff6b6b": "#c62828",
    "#ff5c5c": "#c62828",
    "#ffb74d": "#a35f00",
    "#ffcc66": "#8a6100",
    "#9fe0a0": "#2e7d32",
    "#9fe0a8": "#2e7d32",
    "#7fd18b": "#2e7d32",
    "#63b3ff": "#1f78c8",
    "#4da3ff": "#1f78c8",
    "#5aa0e6": "#1f78c8",
    "#5a4a2a": "#fff1d6",
    "#dfe3e8": "#3b4453",
}
TO_LIGHT = dict(_EXTRA)
for _key, _dark in DARK.items():
    if _dark not in ("#ffffff", "#000000") and DARK[_key] != LIGHT[_key]:
        TO_LIGHT.setdefault(_dark, LIGHT[_key])
# ... and back: a panel made while the light look was on keeps light colours in its style
# (the light palette's colours are used nowhere else, so they can only come from it)
TO_DARK = {
    LIGHT[_key]: _dark
    for _key, _dark in DARK.items()
    if LIGHT[_key] != _dark and LIGHT[_key] not in ("#ffffff", "#000000")
}
_HEX = re.compile(r"#[0-9a-fA-F]{6}\b")


def current():
    """The look chosen in Preferences: "dark" (SciForge's own) or "light"."""
    try:
        import FreeCAD as App

        name = App.ParamGet(PREF[0]).GetString(PREF[1], "dark")
    except Exception:
        name = "dark"
    return name if name in THEMES else "dark"


def is_light():
    return _state["name"] == "light"


def translate(text, light=None):
    """A style sheet in the colours of the look in use (written with the dark colours, or
    with the light palette's by a panel made while the light look was on)."""
    if not text:
        return text
    table = TO_LIGHT if (is_light() if light is None else light) else TO_DARK
    return _HEX.sub(lambda m: table.get(m.group(0).lower(), m.group(0)), text)


_state = {"name": "dark", "hook": None}


def own_background(widget):
    """The background a panel's own style sheet gives it ("#Name { background: #..." for
    its object name), in the look in use; None if it gives none."""
    try:
        match = re.search(
            r"#%s\s*(?:,[^{]*)?\{[^}]*?background(?:-color)?\s*:\s*(#[0-9a-fA-F]{6})"
            % re.escape(widget.objectName()),
            widget.styleSheet() or "",
        )
        return match.group(1) if match else None
    except RuntimeError:
        return None


class OwnBackground:
    """Mix-in for a panel (a QFrame) whose style sheet gives it a background: it paints
    that background itself. On Luca's Windows such panels came out white (and see-through
    on hover) inside FreeCAD's Tasks overlay: the sketch palette, Home's AI column; their
    style sheet's background was not drawn there (it was on Linux)."""

    def paintEvent(self, event):
        colour = own_background(self)
        if colour:
            from PySide import QtGui

            painter = QtGui.QPainter(self)
            try:
                painter.fillRect(self.rect(), QtGui.QColor(colour))
            finally:
                painter.end()
        super().paintEvent(event)


def _use(name):
    """The module's colours (CHROME, TEXT...: read by the panels) for the look `name`."""
    global CHROME, MENU, VIEW, TEXT, TEXT_DIM, TEXT_DISABLED, HOVER, ACTIVE, LINE, ACCENT, FIELD
    global QSS
    _state["name"] = name if name in THEMES else "dark"
    p = LIGHT if _state["name"] == "light" else DARK
    CHROME, MENU, VIEW, TEXT = p["chrome"], p["menu"], p["view"], p["text"]
    TEXT_DIM, TEXT_DISABLED, HOVER = p["text_dim"], p["disabled"], p["hover"]
    ACTIVE, LINE, ACCENT, FIELD = p["active"], p["line"], p["accent"], p["field"]
    QSS = _QSS.format(**p).replace("CHECK_ICON", ui_icon_path("palette_check").replace("\\", "/"))


_QSS = """
QMainWindow, QMainWindow > QWidget {{ background: {chrome}; color: {text}; }}
QWidget {{ color: {text}; }}
QToolTip {{ background: {menu}; color: {text}; border: 1px solid {line}; padding: 4px 6px; }}

QMenuBar {{ background: {chrome}; color: {text}; }}
QMenuBar::item:selected {{ background: {hover}; }}
QMenu {{ background: {menu}; color: {text}; border: 1px solid {line}; padding: 3px 0px; }}
QMenu::item {{ padding: 4px 26px 4px 8px; }}
QMenu::item:selected {{ background: {hover}; }}
QMenu::item:disabled {{ color: {disabled}; }}
QMenu::separator {{ height: 1px; background: {text_dim}; margin: 3px 4px; }}
QMenu::icon {{ padding-left: 6px; }}

QDockWidget {{ color: {text}; titlebar-close-icon: none; }}
QDockWidget::title {{ background: {chrome}; padding: 6px 8px; text-align: left; }}
QTreeView, QTreeWidget, QListView, QListWidget, QTableView {{
    background: {view}; color: {text}; border: none; alternate-background-color: {alternate};
    selection-background-color: {hover}; selection-color: {text}; }}
QTreeView::item:hover {{ background: {tree_hover}; }}
QHeaderView::section {{ background: {chrome}; color: {text}; border: none; padding: 4px; }}

QTabWidget::pane {{ border: none; }}
QTabBar::tab {{ background: {chrome}; color: {text_dim}; padding: 6px 14px; border: none; }}
QTabBar::tab:selected {{ color: {text}; border-bottom: 2px solid {text}; }}
QTabBar::tab:hover {{ color: {text}; }}

QStatusBar {{ background: {chrome}; color: {text_dim}; }}
QScrollBar:vertical, QScrollBar:horizontal {{ background: {chrome}; border: none; width: 10px; height: 10px; }}
QScrollBar::handle {{ background: {handle}; border-radius: 4px; min-height: 24px; min-width: 24px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0px; height: 0px; }}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QAbstractSpinBox, QTextEdit, QPlainTextEdit {{
    background: {field}; color: {text}; border: 1px solid {line}; border-radius: 2px; padding: 2px 4px;
    selection-background-color: {accent}; }}
QComboBox QAbstractItemView {{ background: {menu}; color: {text}; selection-background-color: {hover}; }}
QPushButton {{ background: {button}; color: {text}; border: 1px solid {line}; border-radius: 2px;
    padding: 4px 14px; }}
QPushButton:hover {{ background: {hover}; }}
QPushButton:default {{ border: 1px solid {accent}; }}
QCheckBox, QRadioButton, QLabel, QGroupBox {{ color: {text}; background: transparent; }}
/* An unticked box must be visible on the dark panels (it was only visible once ticked) */
QCheckBox::indicator {{ width: 13px; height: 13px; border: 1px solid {check_line}; border-radius: 2px;
    background: {check}; }}
QCheckBox::indicator:hover {{ border-color: {accent}; }}
QCheckBox::indicator:checked {{ background: {accent}; border-color: {accent};
    image: url(CHECK_ICON); }}
QCheckBox::indicator:disabled {{ background: {chrome}; border-color: {handle}; }}
QGroupBox {{ border: 1px solid {line}; margin-top: 8px; padding-top: 6px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 6px; padding: 0 3px; }}

/* FreeCAD task panels (command dialogs, the sketch's side panel) */
QSint--ActionPanel, QSint--ActionPanel QScrollArea, QSint--ActionPanel QScrollArea > QWidget > QWidget {{
    background: {chrome}; }}
QSint--ActionGroup {{ background: {chrome}; }}
QSint--ActionGroup QFrame[class="header"] {{ background: {header}; border: 1px solid {line};
    border-top-left-radius: 2px; border-top-right-radius: 2px; }}
QSint--ActionGroup QToolButton[class="header"] {{ color: {text}; font-weight: bold; text-align: left;
    border: none; background: transparent; }}
QSint--ActionGroup QFrame[class="header"] QLabel {{ color: {text}; background: transparent; }}
QSint--ActionGroup QFrame[class="content"] {{ background: {chrome}; border: 1px solid {line};
    border-top: none; }}
QSint--ActionGroup QFrame[class="content"] QTreeView, QSint--ActionGroup QFrame[class="content"] QListView,
QSint--ActionGroup QFrame[class="content"] QTableView {{ background: {field}; }}
QSint--ActionGroup QFrame[class="content"] QToolButton {{ background: {button}; color: {text};
    border: 1px solid {line}; border-radius: 2px; padding: 1px; min-height: 16px; }}
QSint--ActionGroup QFrame[class="content"] QToolButton:checked {{ background: {active}; border-color: {accent}; }}
QSint--ActionGroup QFrame[class="content"] QToolButton:hover {{ background: {hover}; }}
QSint--ActionGroup QFrame[class="separator"] {{ background: transparent; }}

/* SciForge ribbon */
#SciForgeRibbon {{ background: {chrome}; border: none; }}
#SciForgeRibbon QToolButton {{ background: transparent; border: none; color: {text}; }}
#SciForgeRibbon QToolButton:hover {{ background: {hover}; border-radius: 2px; }}
#SciForgeRibbon QToolButton:pressed {{ background: {active}; }}
#SciForgeRibbon QToolButton:disabled {{ color: {disabled}; }}
#SciForgeRibbon QToolButton[role="tab"] {{ color: {text}; padding: 3px 18px 4px 18px; font-size: 13px;
    letter-spacing: 0.5px; border-bottom: 2px solid transparent; }}
#SciForgeRibbon QToolButton[role="tab"]:checked {{ border-bottom: 2px solid {text}; }}
#SciForgeRibbon QToolButton[role="tab"]:hover {{ background: transparent; color: {bright}; }}
#SciForgeRibbon QToolButton[role="group"] {{ color: {text_dim}; font-size: 12px; letter-spacing: 0.5px;
    padding: 1px 6px; }}
#SciForgeRibbon QToolButton[role="group"]:hover, #SciForgeRibbon QToolButton[role="group"]:pressed,
#SciForgeRibbon QToolButton[role="group"][open="true"] {{ background: {active}; color: {text}; }}
#SciForgeRibbon QToolButton[role="workspace"] {{ border: 1px solid {line}; border-radius: 3px;
    font-weight: bold; font-size: 12px; padding: 4px 10px; }}
#SciForgeRibbon QFrame[role="separator"] {{ background: {line}; }}
#SciForgeRibbon QLabel[role="document"] {{ color: {text}; font-size: 13px; }}
#SciForgeRibbon QWidget[role="docbar"] {{ background: {chrome}; border-bottom: 1px solid {header}; }}

/* browser */
#SciForgeBrowser {{ font-size: 13px; background: {view}; }}
#SciForgeBrowser::item {{ height: 26px; }}
#SciForgeBrowser::item:selected {{ background: {hover}; }}

/* timeline and navigation bar */
#SciForgeTimeline, #SciForgeTimeline QWidget {{ background: {chrome}; }}
#SciForgeTimeline QToolButton {{ background: transparent; border: none; border-radius: 2px; padding: 2px; }}
#SciForgeTimeline QToolButton:hover {{ background: {hover}; }}
#SciForgeTimeline QToolButton[state="tip"] {{ background: {active}; }}
#SciForgeTimeline QFrame[role="marker"] {{ background: {marker}; border-radius: 1px; }}
#SciForgeNavBar {{ background: {chrome}; border-radius: 3px; }}
#SciForgeNavBar QToolButton {{ background: transparent; border: none; padding: 3px; }}
#SciForgeNavBar QToolButton:hover {{ background: {hover}; border-radius: 2px; }}
"""
CHROME = MENU = VIEW = TEXT = TEXT_DIM = TEXT_DISABLED = HOVER = ACTIVE = LINE = ACCENT = ""
FIELD = QSS = ""
_use(current())

_VIEW_PARAMS = "User parameter:BaseApp/Preferences/View"


def _rgba(hex_color):
    """'#2a2a2a' -> FreeCAD's packed RRGGBBAA unsigned colour."""
    value = int(hex_color.lstrip("#"), 16)
    return (value << 8) | 0xFF


_NAVICUBE_PARAMS = "User parameter:BaseApp/Preferences/NaviCube"
_TECHDRAW_COLORS = "User parameter:BaseApp/Preferences/Mod/TechDraw/Colors"

# (parameter group, kind, name, SciForge value). Fusion: flat dark background; middle
# button pans, Shift+middle orbits, wheel zooms at the cursor (FreeCAD's "Revit" style);
# the orbit is Fusion's Constrained Orbit: it turns about the up axis and tilts, never
# rolls (FreeCAD's "Free Turntable", 2; FreeCAD 1.1's default "Rounded Arcball", 4, rolls
# the model off axis). OrbitStyle comes after NavigationStyle: a new style re-reads it.
# The Orbit drop-down of the navigation bar (orbit_ui.py) may change OrbitStyle to the
# Free orbit afterwards; the user's own value kept here still comes back.
# The orbit turns about the middle of the window (RotationMode 0, Fusion turns about the
# model's centre after a fit) or about the orbit centre a person sets with Shift + middle
# click (orbit_ui.py draws its own green dot; FreeCAD's red dot stays hidden).
# FreeCAD's own cube (the NaviCube) is hidden: SciForge draws Fusion's ViewCube itself
# (viewcube_ui.py). Its colours below only matter if someone turns it back on.
# A light ViewCube with dark labels and a blue hover.
VIEWER_SETTINGS = [
    (_VIEW_PARAMS, "Bool", "Gradient", False),
    (_VIEW_PARAMS, "Bool", "RadialGradient", False),
    (_VIEW_PARAMS, "Unsigned", "BackgroundColor", _rgba(VIEW)),  # (set_theme updates it)
    (_VIEW_PARAMS, "String", "NavigationStyle", "Gui::RevitNavigationStyle"),
    (_VIEW_PARAMS, "Int", "OrbitStyle", 2),
    (_VIEW_PARAMS, "Int", "RotationMode", 0),
    (_VIEW_PARAMS, "Bool", "ShowRotationCenter", False),
    (_VIEW_PARAMS, "Bool", "ZoomAtCursor", True),
    (_VIEW_PARAMS, "Bool", "ShowNaviCube", False),
    # FreeCAD's own long-press "Clarify Selection" menu is off: SciForge shows Fusion's
    # Select Other list on a long press instead (selection_ui.py).
    (_VIEW_PARAMS, "Bool", "EnableLongPressClarifySelection", False),
    (_NAVICUBE_PARAMS, "Unsigned", "BaseColor", (0xF0F0F0 << 8) | 0xE6),
    (_NAVICUBE_PARAMS, "Unsigned", "EmphaseColor", _rgba("#4a4f57")),
    (_NAVICUBE_PARAMS, "Unsigned", "HiliteColor", _rgba("#6fb7f0")),
    # Components (Fusion): every component has its own Body1, and Create Components from
    # Bodies names the component after its body. FreeCAD would rename the second "Body1"
    # to "Body1001" unless duplicate labels are allowed (its own tree copes with them).
    ("User parameter:BaseApp/Preferences/Document", "Bool", "DuplicateLabels", True),
    # Drawings (drawing_ui.py): opening a drawing keeps SciForge's window; FreeCAD would
    # switch to its TechDraw workbench and turn the SciForge interface off.
    ("User parameter:BaseApp/Preferences/Mod/TechDraw/General", "Bool", "SwitchToWB", False),
    # A drawing's sheet is white, like the paper it is printed on (Fusion), and so are the
    # cut faces under a section's hatching; FreeCAD's light theme makes both grey, and the
    # grey went into the exported PDF as well.
    (_TECHDRAW_COLORS, "Unsigned", "PageColor", _rgba("#ffffff")),
    (_TECHDRAW_COLORS, "Unsigned", "FaceColor", _rgba("#ffffff")),
    # Joints (joints.py): SciForge solves the assembly itself (nested components, free
    # groups of jointed parts held while solving). FreeCAD's own solve on every recompute
    # knows neither and would move a nested component to the wrong place.
    ("User parameter:BaseApp/Preferences/Mod/Assembly", "Bool", "SolveOnRecompute", False),
    # A dimension's tolerances (drawing_annot.py) at 0.7 of its text, not half: Fusion
    # writes them nearly as large as the value, so they stay readable on paper.
    ("User parameter:BaseApp/Preferences/Mod/TechDraw/Dimensions", "Float", "TolSizeAdjust", 0.7),
]

_saved_qss = None

# The user's own values of VIEWER_SETTINGS, kept until SciForge is switched off. In
# FreeCAD's preferences, not in memory: FreeCAD saves its preferences when it quits, so
# quitting while SciForge was on left SciForge's values as "the user's", and memory alone
# then restored SciForge's values the next time (FreeCAD's own cube never came back).
BACKUP = "User parameter:BaseApp/Preferences/Mod/SciForge/ViewerBackup"
_ABSENT = "absent"  # the user had never set it: removed again, FreeCAD's default applies


def _backup_key(path, name):
    return "%s.%s" % (path.split("Preferences/")[-1].replace("/", "."), name)


def _encode(kind, value):
    if kind == "Bool":
        return "=1" if value else "=0"
    return "=%s" % value


def _decode(kind, text):
    text = text[1:]
    if kind == "Bool":
        return text == "1"
    if kind in ("Int", "Unsigned"):
        return int(text)
    if kind == "Float":
        return float(text)
    return text


def keep_and_set(settings, backup_path=BACKUP):
    """Set SciForge's values of `settings` [(path, kind, name, value)], after keeping the
    user's own values in FreeCAD's preferences under `backup_path` (a value kept from a
    session that ended with SciForge on is the user's and stays)."""
    import FreeCAD as App

    backup = App.ParamGet(backup_path)
    saved = backup.GetStrings()
    for path, kind, name, _ in settings:
        key = _backup_key(path, name)
        if key in saved:
            continue  # kept from a session that ended with SciForge on: the user's value
        try:
            group = App.ParamGet(path)
            # Whether the user had set it at all: if not, give_back() removes it again so
            # FreeCAD falls back to its own default (not to 0/False).
            if name in getattr(group, "Get" + kind + "s")():
                backup.SetString(key, _encode(kind, getattr(group, "Get" + kind)(name)))
            else:
                backup.SetString(key, _ABSENT)
        except Exception as exc:
            warn("cannot keep %s: %s" % (name, exc))
    for path, kind, name, value in settings:
        try:
            getattr(App.ParamGet(path), "Set" + kind)(name, value)
        except Exception as exc:
            warn("cannot set %s: %s" % (name, exc))


def give_back(settings, backup_path=BACKUP):
    """Put back the user's own values kept by keep_and_set (nothing when none is kept)."""
    import FreeCAD as App

    backup = App.ParamGet(backup_path)
    saved = backup.GetStrings()
    for path, kind, name, _ in settings:
        key = _backup_key(path, name)
        if key not in saved:
            continue
        try:
            text = backup.GetString(key)
            group = App.ParamGet(path)
            if text == _ABSENT:
                getattr(group, "Rem" + kind)(name)
            else:
                getattr(group, "Set" + kind)(name, _decode(kind, text))
            backup.RemString(key)
        except Exception as exc:
            warn("cannot give back %s: %s" % (name, exc))


def _install_hook():
    """Style sheets SciForge's panels set (with the dark colours) come out in the colours of
    the look in use; the original is kept on the widget (property sciforgeQss) for a later
    switch. Only Python callers pass here: FreeCAD's own widgets follow the app's style."""
    from PySide import QtWidgets

    if _state["hook"] is not None:
        return
    original = QtWidgets.QWidget.setStyleSheet

    def set_style_sheet(widget, text):
        try:
            if text and "#" in text:
                widget.setProperty("sciforgeQss", text)
                text = translate(text)
        except Exception:
            pass
        return original(widget, text)

    QtWidgets.QWidget.setStyleSheet = set_style_sheet
    _state["hook"] = original


def _remove_hook():
    from PySide import QtWidgets

    if _state["hook"] is not None:
        QtWidgets.QWidget.setStyleSheet = _state["hook"]
        _state["hook"] = None


def _restyle_widgets():
    """Every panel SciForge styled, in the colours of the look in use."""
    from PySide import QtWidgets

    original = _state["hook"] or QtWidgets.QWidget.setStyleSheet
    for widget in QtWidgets.QApplication.allWidgets():
        try:
            text = widget.property("sciforgeQss")
            if text:
                original(widget, translate(text))
        except RuntimeError:
            pass


def _view_background():
    """The 3D view's background for the look in use (open views follow FreeCAD's setting)."""
    import FreeCAD as App

    value = _rgba(VIEW)
    for i, entry in enumerate(VIEWER_SETTINGS):
        if entry[2] == "BackgroundColor":
            VIEWER_SETTINGS[i] = (entry[0], entry[1], entry[2], value)
    App.ParamGet(_VIEW_PARAMS).SetUnsigned("BackgroundColor", value)


def set_theme(name):
    """Switch SciForge's look now (Preferences > General > Look): colours, panels, icons,
    3D view, sketch colours. Returns the look in use."""
    import FreeCAD as App

    App.ParamGet(PREF[0]).SetString(PREF[1], name if name in THEMES else "dark")
    _use(current())
    try:
        from PySide import QtWidgets

        from . import _ICON_CACHE

        _ICON_CACHE.clear()
        QtWidgets.QApplication.instance().setStyleSheet(QSS)
        _restyle_widgets()
        _view_background()
    except Exception as exc:
        warn("theme: %s" % exc)
    for step in ("sketch_mode", "shell", "home_ui"):
        try:
            module = __import__("sciforge." + step, fromlist=["x"])
            getattr(module, "theme_changed", lambda: None)()
        except Exception as exc:
            warn("theme: %s: %s" % (step, exc))
    log("look: %s" % _state["name"])
    return _state["name"]


def apply():
    global _saved_qss
    _use(current())
    try:
        from PySide import QtWidgets

        app = QtWidgets.QApplication.instance()
        if _saved_qss is None:
            _saved_qss = app.styleSheet()
        _install_hook()
        app.setStyleSheet(QSS)
    except Exception as exc:
        warn("theme: could not apply stylesheet: %s" % exc)
    try:
        _view_background_entry()
        keep_and_set(VIEWER_SETTINGS)
    except Exception as exc:
        warn("theme: could not apply viewer settings: %s" % exc)
    try:
        # The remembered orbit choice (Constrained or Free) replaces the OrbitStyle above;
        # the user's own value is already kept.
        from . import orbit_ui

        orbit_ui.apply_mode()
    except Exception as exc:
        warn("theme: could not apply the orbit choice: %s" % exc)
    log("theme applied")


def _view_background_entry():
    for i, entry in enumerate(VIEWER_SETTINGS):
        if entry[2] == "BackgroundColor":
            VIEWER_SETTINGS[i] = (entry[0], entry[1], entry[2], _rgba(VIEW))


def restore():
    global _saved_qss
    try:
        _remove_hook()
    except Exception as exc:
        warn("theme: %s" % exc)
    try:
        from PySide import QtWidgets

        if _saved_qss is not None:
            QtWidgets.QApplication.instance().setStyleSheet(_saved_qss)
            _saved_qss = None
    except Exception as exc:
        warn("theme: could not restore stylesheet: %s" % exc)
    try:
        give_back(VIEWER_SETTINGS)
    except Exception as exc:
        warn("theme: could not restore viewer settings: %s" % exc)
