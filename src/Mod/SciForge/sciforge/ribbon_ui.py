# SPDX-License-Identifier: LGPL-2.1-or-later
"""The Fusion-style ribbon: quick-access bar, workspace button, tabs, groups with
large icons and a drop-down menu under each group name. Layout comes from
ribbon_config.py; this module only turns that data into Qt widgets."""

import FreeCADGui as Gui

from . import log, registry, ribbon_config as cfg, ui_icon, warn
from .compat import QtCore, QtGui, QtWidgets

BIG = 36  # ribbon icon size (Fusion: about 36-40 px at 100% scaling)
SMALL = 18  # menu / quick-access icon size


def resolve(command, available):
    """Command slot -> ("Name", index or None), or None when not available."""
    if command is None:
        return None
    if command == "__menu__":
        return ("__menu__", None)
    for name in registry.alternatives(command):
        base, _, index = name.partition("#")
        if base in available:
            return (base, int(index) if index else None)
    return None


def run(resolved, label):
    """Run a command; never let an exception escape into Qt."""
    if not resolved:
        return
    name, index = resolved
    from . import recent

    recent.record(name, label, index)
    try:
        if index is None:
            Gui.runCommand(name)
        else:
            Gui.runCommand(name, index)
    except Exception as exc:
        warn("'%s' (%s) failed: %s" % (label, name, exc))


def is_active(resolved):
    try:
        cmd = Gui.Command.get(resolved[0])
        return bool(cmd.isActive()) if cmd is not None and hasattr(cmd, "isActive") else True
    except Exception:
        return True


def _menu_text(entry):
    # Text after a tab is drawn right-aligned as the shortcut column, without binding the key.
    return entry["label"] + ("\t" + entry["key"] if entry.get("key") else "")


def is_checked(spec):
    """Whether a "module:function" entry (ribbon_config.item(checked=...)) is the current
    choice. Never raises: a broken spec shows unticked."""
    try:
        import importlib

        module_name, function_name = spec.split(":", 1)
        module = importlib.import_module("." + module_name, __package__)
        return bool(getattr(module, function_name)())
    except Exception as exc:
        warn("menu tick %s: %s" % (spec, exc))
        return False


def build_menu(parent, entries, available):
    """QMenu for a list of config entries. Unavailable commands are greyed out."""
    menu = QtWidgets.QMenu(parent)
    menu.setToolTipsVisible(True)
    checks = []  # (action, resolved, checked spec) re-checked each time the menu opens
    choices = None  # the ticked entries of one menu are one choice: exactly one tick
    for entry in entries:
        if entry is cfg.SEP:
            menu.addSeparator()
            continue
        if "submenu" in entry:
            submenu = build_menu(menu, entry["submenu"], available)
            submenu.setTitle(entry["label"])
            if entry.get("icon"):
                submenu.setIcon(ui_icon(entry["icon"]))
            menu.addMenu(submenu)
            continue
        action = menu.addAction(ui_icon(entry["icon"]), _menu_text(entry))
        resolved = resolve(entry["command"], available)
        if resolved:
            action.triggered.connect(lambda _=False, r=resolved, e=entry: run(r, e["label"]))
            if entry.get("note"):
                action.setToolTip(entry["note"])
            if entry.get("checked"):
                action.setCheckable(True)
                if choices is None:
                    # Exclusive: clicking the ticked entry again keeps its tick (without
                    # the group Qt unticked it until the menu was opened again).
                    choices = QtGui.QActionGroup(menu)
                    choices.setExclusive(True)
                choices.addAction(action)
                action.setChecked(is_checked(entry["checked"]))
            elif entry.get("toggle"):
                # On or off by itself (a selection filter): the command flips it and the
                # tick is read back from the module when the menu opens again.
                action.setCheckable(True)
                action.setChecked(is_checked(entry["toggle"]))
            checks.append((action, resolved, entry.get("checked") or entry.get("toggle")))
        else:
            action.setEnabled(False)
            action.setToolTip(entry.get("note") or "Not available in SciForge yet")

    def refresh():
        for action, resolved, checked in checks:
            action.setEnabled(is_active(resolved))
            if checked:
                action.setChecked(is_checked(checked))

    menu.aboutToShow.connect(refresh)
    return menu


class GroupWidget(QtWidgets.QWidget):
    """Large icons on top, 'NAME ▾' underneath; the name opens the full menu."""

    def __init__(self, group, available, parent=None):
        super().__init__(parent)
        self.group = group
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(2, 2, 2, 0)
        outer.setSpacing(0)
        row = QtWidgets.QHBoxLayout()
        row.setContentsMargins(4, 0, 4, 0)
        row.setSpacing(4)
        self.buttons = []
        for label in group["big"]:
            entry = cfg.find(group, label)
            if entry is None:
                warn("ribbon: '%s' is not in group %s" % (label, group["title"]))
                continue
            if "submenu" in entry:  # big icon of a submenu runs its first entry
                entry = next(cfg.iter_items(entry["submenu"]))
            row.addWidget(self._big_button(entry, available))
        outer.addLayout(row)

        self.label = QtWidgets.QToolButton()
        self.label.setProperty("role", "group")
        self.label.setText(group["title"] + " ▾")
        self.label.setToolButtonStyle(QtCore.Qt.ToolButtonTextOnly)
        self.label.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.menu = build_menu(self, group["items"], available)
        self.label.clicked.connect(self.open_menu)
        outer.addWidget(self.label)

    def _big_button(self, entry, available):
        button = QtWidgets.QToolButton()
        button.setIcon(ui_icon(entry["icon"]))
        button.setIconSize(QtCore.QSize(BIG, BIG))
        button.setFixedSize(BIG + 12, BIG + 12)
        button.setAutoRaise(True)
        resolved = resolve(entry["command"], available)
        tip = entry["label"] + ("  (%s)" % entry["key"] if entry.get("key") else "")
        if resolved:
            button.clicked.connect(lambda _=False, r=resolved, e=entry: run(r, e["label"]))
            button.setToolTip(tip + ("\n" + entry["note"] if entry.get("note") else ""))
        else:
            button.setEnabled(False)
            button.setToolTip(tip + "\n" + (entry.get("note") or "Not available in SciForge yet"))
        button.setObjectName("SciForgeBig_" + entry["label"].replace(" ", "_"))
        self.buttons.append(button)
        return button

    def open_menu(self):
        self.label.setProperty("open", "true")
        self.label.style().polish(self.label)
        self.menu.exec_(self.label.mapToGlobal(QtCore.QPoint(0, self.label.height())))
        self.label.setProperty("open", "false")
        self.label.style().polish(self.label)


def _separator():
    line = QtWidgets.QFrame()
    line.setProperty("role", "separator")
    line.setFixedWidth(1)
    line.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Expanding)
    return line


class RibbonWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SciForgeRibbon")
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        available = registry.available_commands()
        self._sketch_mode = False
        self._user_tab = "solid"

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._doc_bar(available))

        body = QtWidgets.QHBoxLayout()
        body.setContentsMargins(10, 4, 6, 4)
        body.setSpacing(10)
        body.addWidget(self._workspace_button(), 0, QtCore.Qt.AlignVCenter)

        right = QtWidgets.QVBoxLayout()
        right.setSpacing(2)
        tabs_row = QtWidgets.QHBoxLayout()
        tabs_row.setSpacing(0)
        self.tab_buttons = {}
        self.pages = QtWidgets.QStackedWidget()
        self.page_index = {}
        for tab in cfg.TABS:
            button = QtWidgets.QToolButton()
            button.setProperty("role", "tab")
            button.setText(tab["title"])
            button.setCheckable(True)
            button.clicked.connect(lambda _=False, t=tab["id"]: self.select_tab(t, user=True))
            tabs_row.addWidget(button)
            self.tab_buttons[tab["id"]] = button
            page = QtWidgets.QWidget()
            row = QtWidgets.QHBoxLayout(page)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(6)
            for i, grp in enumerate(tab["groups"]):
                if i:
                    row.addWidget(_separator())
                row.addWidget(GroupWidget(grp, available))
            row.addStretch(1)
            self.page_index[tab["id"]] = self.pages.addWidget(page)
        tabs_row.addStretch(1)
        right.addLayout(tabs_row)
        # Let the ribbon clip instead of forcing the window wider (Fusion clips too).
        self.pages.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
        self.pages.setMinimumWidth(0)
        right.addWidget(self.pages)
        body.addLayout(right, 1)
        outer.addLayout(body)

        self.tab_buttons["sketch"].setVisible(False)
        # The DRAWING tab shows only while a drawing's tab is active (drawing_ui).
        self._drawing_mode = False
        if "drawing" in self.tab_buttons:
            self.tab_buttons["drawing"].setVisible(False)
        self.select_tab("solid")

        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(700)
        self._timer.timeout.connect(self._refresh_title)
        self._timer.start()

    # -- pieces ---------------------------------------------------------
    def _doc_bar(self, available):
        bar = QtWidgets.QWidget()
        bar.setProperty("role", "docbar")
        bar.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        row = QtWidgets.QHBoxLayout(bar)
        row.setContentsMargins(8, 3, 8, 3)
        row.setSpacing(6)
        for entry in cfg.QUICK_ACCESS:
            button = QtWidgets.QToolButton()
            button.setIcon(ui_icon(entry["icon"]))
            button.setIconSize(QtCore.QSize(SMALL, SMALL))
            button.setAutoRaise(True)
            button.setToolTip(
                entry["label"] + ("  (%s)" % entry["key"] if entry.get("key") else "")
            )
            if entry["command"] == "__menu__":
                button.clicked.connect(lambda _=False, b=button: self._show_app_menu(b))
            else:
                resolved = resolve(entry["command"], available)
                button.setEnabled(bool(resolved))
                button.clicked.connect(lambda _=False, r=resolved, e=entry: run(r, e["label"]))
            row.addWidget(button)
        row.addStretch(1)
        self.title = QtWidgets.QLabel("")
        self.title.setProperty("role", "document")
        row.addWidget(self.title)
        # Fusion's Out-of-Date icon: something of the design has a newer saved version
        # (versions_ui.out_of_date); its menu has Get Latest.
        self.out_of_date = QtWidgets.QToolButton()
        self.out_of_date.setObjectName("SciForgeOutOfDate")
        self.out_of_date.setAutoRaise(True)
        self.out_of_date.setToolTip("Out of date: a newer version exists. Click for Get Latest")
        self.out_of_date.clicked.connect(self._out_of_date_menu)
        self.out_of_date.hide()
        self._out_of_date_ticks = 0
        row.addWidget(self.out_of_date)
        row.addStretch(1)
        search = QtWidgets.QToolButton()
        search.setIcon(ui_icon("nav_zoom"))
        search.setIconSize(QtCore.QSize(SMALL, SMALL))
        search.setAutoRaise(True)
        search.setToolTip("Search commands  (S)")
        search.clicked.connect(lambda: run(("SciForge_CommandSearch", None), "Search"))
        row.addWidget(search)
        return bar

    def _workspace_button(self):
        button = QtWidgets.QToolButton()
        button.setProperty("role", "workspace")
        button.setText("DESIGN ▾")
        button.setFixedSize(136, 74)
        self.workspace = button
        button.clicked.connect(lambda: self._workspace_menu(button))
        return button

    def _workspace_menu(self, button):
        """Fusion's workspace switcher: Design, or Drawing (a new one from the design, or
        one of the design's drawings)."""
        menu = QtWidgets.QMenu(button)
        menu.setObjectName("SciForgeWorkspaceMenu")
        menu.setToolTipsVisible(True)
        design = menu.addAction(ui_icon("workspace_design"), "Design")
        design.setCheckable(True)
        design.setChecked(not self._drawing_mode)
        drawings = menu.addMenu(ui_icon("dw_base_view"), "Drawing")
        try:
            from . import drawing_ui

            design.triggered.connect(lambda: drawing_ui.show_design())
            drawing_ui.fill_workspace_menu(drawings)
        except Exception as exc:
            warn("workspace menu: %s" % exc)
        menu.exec_(button.mapToGlobal(QtCore.QPoint(0, button.height())))

    def _show_app_menu(self, button):
        """Fusion's File menu (ribbon_config.FILE_MENU) on top, then all of FreeCAD's menus,
        since the menu bar is hidden like in Fusion."""
        menu = QtWidgets.QMenu(button)
        menu.setObjectName("SciForgeAppMenu")
        try:
            self._fill_file_menu(menu.addMenu(ui_icon("document"), "File"))
            menu.addSeparator()
        except Exception as exc:
            warn("file menu: %s" % exc)
        for action in Gui.getMainWindow().menuBar().actions():
            if action.menu() is not None and action.text():
                menu.addMenu(action.menu())
        menu.exec_(button.mapToGlobal(QtCore.QPoint(0, button.height())))

    def _fill_file_menu(self, menu):
        menu.setObjectName("SciForgeFileMenu")
        available = set(Gui.listCommands())
        for entry in cfg.FILE_MENU:
            if entry is cfg.SEP:
                menu.addSeparator()
                continue
            resolved = resolve(entry["command"], available)
            action = menu.addAction(ui_icon(entry["icon"]), _menu_text(entry))
            action.setEnabled(bool(resolved) and is_active(resolved))
            action.triggered.connect(lambda _=False, r=resolved, e=entry: run(r, e["label"]))
        return menu

    # -- behaviour ------------------------------------------------------
    def select_tab(self, tab_id, user=False):
        for tid, button in self.tab_buttons.items():
            button.setChecked(tid == tab_id)
        self.pages.setCurrentIndex(self.page_index[tab_id])
        if user and tab_id not in ("sketch", "drawing"):
            self._user_tab = tab_id

    def set_sketch_mode(self, on):
        """While a sketch is open, show and select the contextual SKETCH tab."""
        if on == self._sketch_mode:
            return
        self._sketch_mode = on
        drawing = getattr(self, "_drawing_mode", False)  # (a drawing's tab keeps DRAWING)
        self.tab_buttons["sketch"].setVisible(on and not drawing)
        if not drawing:
            self.select_tab("sketch" if on else self._user_tab)
        log("ribbon: sketch mode %s" % ("on" if on else "off"))

    def set_drawing_mode(self, on):
        """While a drawing's tab is active, Fusion's DRAWING toolbar is the only one shown
        (the workspace button says DRAWING); back to the design's tabs after."""
        if on == self._drawing_mode or "drawing" not in self.tab_buttons:
            return
        self._drawing_mode = on
        for tid, button in self.tab_buttons.items():
            if tid == "drawing":
                button.setVisible(on)
            elif tid == "sketch":
                button.setVisible(self._sketch_mode and not on)
            else:
                button.setVisible(not on)
        self.workspace.setText("DRAWING ▾" if on else "DESIGN ▾")
        if on:
            self.select_tab("drawing")
        else:
            self.select_tab("sketch" if self._sketch_mode else self._user_tab)
        log("ribbon: drawing mode %s" % ("on" if on else "off"))

    def current_tab(self):
        for tid, button in self.tab_buttons.items():
            if button.isChecked():
                return tid
        return None

    def _refresh_title(self):
        try:
            import FreeCAD as App

            doc = App.ActiveDocument
            text = ""
            if doc is not None:
                modified = Gui.ActiveDocument is not None and Gui.ActiveDocument.Modified
                text = doc.Label + ("*" if modified else "")
            if self.title.text() != text:
                self.title.setText(text)
        except Exception:
            pass
        self._out_of_date_ticks += 1
        if self._out_of_date_ticks % 3 == 0:  # every 2 s: it reads files' dates
            self.refresh_out_of_date()

    def refresh_out_of_date(self):
        """Show the Out-of-Date button while the active design has something newer."""
        try:
            import FreeCAD as App

            from . import versions_ui

            items = versions_ui.out_of_date(App.ActiveDocument) if App.ActiveDocument else []
            if items and self.out_of_date.icon().isNull():
                self.out_of_date.setIcon(versions_ui.out_of_date_icon())
            self.out_of_date.setToolTip(
                "Out of date: %s. Click for Get Latest." % "; ".join(w for _k, _n, w in items)
                if items
                else ""
            )
            self.out_of_date.setVisible(bool(items))
        except Exception as exc:
            warn("out of date: %s" % exc)

    def _out_of_date_menu(self):
        try:
            import FreeCAD as App

            from . import versions_ui

            menu = QtWidgets.QMenu(self.out_of_date)
            menu.setObjectName("SciForgeOutOfDateMenu")
            versions_ui.out_of_date_menu(menu, App.ActiveDocument)
            menu.exec_(self.out_of_date.mapToGlobal(QtCore.QPoint(0, self.out_of_date.height())))
            self.refresh_out_of_date()
        except Exception as exc:
            warn("out of date: %s" % exc)
