# SPDX-License-Identifier: LGPL-2.1-or-later
"""SciForge's dark theme and Fusion-like viewer settings.

Colours were measured from screenshots of Fusion's stock dark theme
(docs/sciforge/parity/ui-shell.md). Everything changed here is remembered and
put back by restore(), so leaving SciForge returns FreeCAD exactly as it was.
"""
from . import log, warn

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

_VIEW_PARAMS = "User parameter:BaseApp/Preferences/View"


def _rgba(hex_color):
    """'#2a2a2a' -> FreeCAD's packed RRGGBBAA unsigned colour."""
    value = int(hex_color.lstrip("#"), 16)
    return (value << 8) | 0xFF


# (kind, name, SciForge value). Fusion: flat dark background; middle button pans,
# Shift+middle orbits, wheel zooms at the cursor, which is FreeCAD's "Revit" style.
VIEWER_SETTINGS = [
    ("Bool", "Gradient", False),
    ("Bool", "RadialGradient", False),
    ("Unsigned", "BackgroundColor", _rgba(VIEW)),
    ("String", "NavigationStyle", "Gui::RevitNavigationStyle"),
    ("Bool", "ZoomAtCursor", True),
]

_saved_qss = None
_saved_params = []


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
        import FreeCAD as App

        group = App.ParamGet(_VIEW_PARAMS)
        if not _saved_params:
            for kind, name, _ in VIEWER_SETTINGS:
                _saved_params.append((kind, name, getattr(group, "Get" + kind)(name)))
        for kind, name, value in VIEWER_SETTINGS:
            getattr(group, "Set" + kind)(name, value)
    except Exception as exc:
        warn("theme: could not apply viewer settings: %s" % exc)
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
        import FreeCAD as App

        group = App.ParamGet(_VIEW_PARAMS)
        for kind, name, value in _saved_params:
            getattr(group, "Set" + kind)(name, value)
        _saved_params.clear()
    except Exception as exc:
        warn("theme: could not restore viewer settings: %s" % exc)
