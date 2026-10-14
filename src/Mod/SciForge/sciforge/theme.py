# SPDX-License-Identifier: LGPL-2.1-or-later
"""SciForge's dark theme and Fusion-like viewer settings.

Colours were measured from screenshots of Fusion's stock dark theme
(docs/sciforge/parity/ui-shell.md). Everything changed here is remembered and
put back by restore(), so leaving SciForge returns FreeCAD exactly as it was.
"""

from . import log, ui_icon_path, warn

CHROME = "#3b4453"  # ribbon, panels, timeline
MENU = "#454f61"  # drop-down menus
VIEW = "#2a2a2a"  # 3D view background
TEXT = "#f5f5f5"
TEXT_DIM = "#c3cad4"
TEXT_DISABLED = "#7d8593"
HOVER = "#56647a"
ACTIVE = "#354a63"  # pressed / open group label
LINE = "#56606f"  # separators
ACCENT = "#3fa9f5"

QSS = """
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
    background: {view}; color: {text}; border: none; alternate-background-color: #303030;
    selection-background-color: {hover}; selection-color: {text}; }}
QTreeView::item:hover {{ background: #3a4252; }}
QHeaderView::section {{ background: {chrome}; color: {text}; border: none; padding: 4px; }}

QTabWidget::pane {{ border: none; }}
QTabBar::tab {{ background: {chrome}; color: {text_dim}; padding: 6px 14px; border: none; }}
QTabBar::tab:selected {{ color: {text}; border-bottom: 2px solid {text}; }}
QTabBar::tab:hover {{ color: {text}; }}

QStatusBar {{ background: {chrome}; color: {text_dim}; }}
QScrollBar:vertical, QScrollBar:horizontal {{ background: {chrome}; border: none; width: 10px; height: 10px; }}
QScrollBar::handle {{ background: #5d6778; border-radius: 4px; min-height: 24px; min-width: 24px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0px; height: 0px; }}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QAbstractSpinBox, QTextEdit, QPlainTextEdit {{
    background: #2f3540; color: {text}; border: 1px solid {line}; border-radius: 2px; padding: 2px 4px;
    selection-background-color: {accent}; }}
QComboBox QAbstractItemView {{ background: {menu}; color: {text}; selection-background-color: {hover}; }}
QPushButton {{ background: #4a5568; color: {text}; border: 1px solid {line}; border-radius: 2px;
    padding: 4px 14px; }}
QPushButton:hover {{ background: {hover}; }}
QPushButton:default {{ border: 1px solid {accent}; }}
QCheckBox, QRadioButton, QLabel, QGroupBox {{ color: {text}; background: transparent; }}
/* An unticked box must be visible on the dark panels (it was only visible once ticked) */
QCheckBox::indicator {{ width: 13px; height: 13px; border: 1px solid #8a94a3; border-radius: 2px;
    background: #2b313b; }}
QCheckBox::indicator:hover {{ border-color: {accent}; }}
QCheckBox::indicator:checked {{ background: {accent}; border-color: {accent};
    image: url(CHECK_ICON); }}
QCheckBox::indicator:disabled {{ background: #3b4453; border-color: #5d6778; }}
QGroupBox {{ border: 1px solid {line}; margin-top: 8px; padding-top: 6px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 6px; padding: 0 3px; }}

/* FreeCAD task panels (command dialogs, the sketch's side panel) */
QSint--ActionPanel, QSint--ActionPanel QScrollArea, QSint--ActionPanel QScrollArea > QWidget > QWidget {{
    background: {chrome}; }}
QSint--ActionGroup {{ background: {chrome}; }}
QSint--ActionGroup QFrame[class="header"] {{ background: #2f3643; border: 1px solid {line};
    border-top-left-radius: 2px; border-top-right-radius: 2px; }}
QSint--ActionGroup QToolButton[class="header"] {{ color: {text}; font-weight: bold; text-align: left;
    border: none; background: transparent; }}
QSint--ActionGroup QFrame[class="header"] QLabel {{ color: {text}; background: transparent; }}
QSint--ActionGroup QFrame[class="content"] {{ background: {chrome}; border: 1px solid {line};
    border-top: none; }}
QSint--ActionGroup QFrame[class="content"] QTreeView, QSint--ActionGroup QFrame[class="content"] QListView,
QSint--ActionGroup QFrame[class="content"] QTableView {{ background: #2f3540; }}
QSint--ActionGroup QFrame[class="content"] QToolButton {{ background: #4a5568; color: {text};
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
#SciForgeRibbon QToolButton[role="tab"]:hover {{ background: transparent; color: #ffffff; }}
#SciForgeRibbon QToolButton[role="group"] {{ color: {text_dim}; font-size: 12px; letter-spacing: 0.5px;
    padding: 1px 6px; }}
#SciForgeRibbon QToolButton[role="group"]:hover, #SciForgeRibbon QToolButton[role="group"]:pressed,
#SciForgeRibbon QToolButton[role="group"][open="true"] {{ background: {active}; color: {text}; }}
#SciForgeRibbon QToolButton[role="workspace"] {{ border: 1px solid {line}; border-radius: 3px;
    font-weight: bold; font-size: 12px; padding: 4px 10px; }}
#SciForgeRibbon QFrame[role="separator"] {{ background: {line}; }}
#SciForgeRibbon QLabel[role="document"] {{ color: {text}; font-size: 13px; }}
#SciForgeRibbon QWidget[role="docbar"] {{ background: {chrome}; border-bottom: 1px solid #2f3643; }}

/* browser */
#SciForgeBrowser {{ font-size: 13px; background: {view}; }}
#SciForgeBrowser::item {{ height: 26px; }}
#SciForgeBrowser::item:selected {{ background: {hover}; }}

/* timeline and navigation bar */
#SciForgeTimeline, #SciForgeTimeline QWidget {{ background: {chrome}; }}
#SciForgeTimeline QToolButton {{ background: transparent; border: none; border-radius: 2px; padding: 2px; }}
#SciForgeTimeline QToolButton:hover {{ background: {hover}; }}
#SciForgeTimeline QToolButton[state="tip"] {{ background: {active}; }}
#SciForgeTimeline QFrame[role="marker"] {{ background: #e8e8e8; border-radius: 1px; }}
#SciForgeNavBar {{ background: {chrome}; border-radius: 3px; }}
#SciForgeNavBar QToolButton {{ background: transparent; border: none; padding: 3px; }}
#SciForgeNavBar QToolButton:hover {{ background: {hover}; border-radius: 2px; }}
""".format(
    chrome=CHROME,
    menu=MENU,
    view=VIEW,
    text=TEXT,
    text_dim=TEXT_DIM,
    disabled=TEXT_DISABLED,
    hover=HOVER,
    active=ACTIVE,
    line=LINE,
    accent=ACCENT,
)
QSS = QSS.replace("CHECK_ICON", ui_icon_path("palette_check").replace("\\", "/"))

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
    (_VIEW_PARAMS, "Unsigned", "BackgroundColor", _rgba(VIEW)),
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


def apply():
    global _saved_qss
    try:
        from PySide import QtWidgets

        app = QtWidgets.QApplication.instance()
        if _saved_qss is None:
            _saved_qss = app.styleSheet()
        app.setStyleSheet(QSS)
    except Exception as exc:
        warn("theme: could not apply stylesheet: %s" % exc)
    try:
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


def restore():
    global _saved_qss
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
