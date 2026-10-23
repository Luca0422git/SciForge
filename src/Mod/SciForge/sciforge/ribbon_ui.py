# SPDX-License-Identifier: LGPL-2.1-or-later
"""The Fusion-style ribbon: quick-access bar, workspace button, tabs, groups with
large icons and a drop-down menu under each group name. Layout comes from
ribbon_config.py; this module only turns that data into Qt widgets."""

import FreeCADGui as Gui

from . import log, registry, ribbon_config as cfg, ui_icon, warn
from .compat import QtCore, QtGui, QtWidgets

BIG = 36  # ribbon icon size (Fusion: about 36-40 px at 100% scaling)
SMALL = 18  # menu / quick-access icon size


# Tabs shown only in their own mode (never remembered as the tab to go back to).
CONTEXTUAL = ("sketch", "drawing", "flat_pattern")


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


def shown_key(entry):
    """The key a menu shows for an entry: the current one (Change Keyboard Shortcut may have
    changed it), else the entry's own."""
    try:
        from . import command_options

        return command_options.key_for(entry)
    except Exception:
        return entry.get("key", "")


def _menu_text(entry):
    # Text after a tab is drawn right-aligned as the shortcut column, without binding the key.
    key = shown_key(entry)
    return entry["label"] + ("\t" + key if key else "")


class _MenuOptions(QtCore.QObject):
    """Fusion's three-dot button beside the command under the mouse in a drop-down, and the
    same options on a right-click (Pin to Toolbar / Unpin, Change Keyboard Shortcut)."""

    def __init__(self, menu, context):
        super().__init__(menu)
        self.menu = menu
        self.context = context
        self.entries = {}  # action -> entry
        self.current = None
        self.button = QtWidgets.QToolButton(menu)
        self.button.setObjectName("SciForgeMenuOptions")
        self.button.setText("\u22ee")  # vertical ellipsis
        self.button.setAutoRaise(True)
        self.button.setToolTip("Options: Pin to Toolbar, Change Keyboard Shortcut")
        self.button.setCursor(QtCore.Qt.PointingHandCursor)
        self.button.hide()
        self.button.clicked.connect(self._button_clicked)
        menu.installEventFilter(self)
        menu.aboutToHide.connect(self.button.hide)

    def add(self, action, entry):
        self.entries[action] = entry

    def eventFilter(self, obj, event):
        try:
            if obj is not self.menu:
                return False
            kind = event.type()
            if kind == QtCore.QEvent.MouseMove:
                pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
                self._hover(self.menu.actionAt(pos))
            elif kind == QtCore.QEvent.Leave:
                if not self.button.underMouse():
                    self.button.hide()
            elif kind == QtCore.QEvent.ContextMenu:
                action = self.menu.actionAt(event.pos())
                if action in self.entries:
                    self.current = action
                    self.open_options(self.menu.mapToGlobal(event.pos()))
                    return True
        except Exception as exc:
            warn("menu options: %s" % exc)
        return False

    def _hover(self, action):
        if action is None or action not in self.entries:
            if not self.button.underMouse():
                self.button.hide()
            return
        self.current = action
        rect = self.menu.actionGeometry(action)
        size = max(14, rect.height() - 4)
        self.button.setFixedSize(size, size)
        self.button.move(rect.right() - size - 2, rect.top() + (rect.height() - size) // 2)
        self.button.show()
        self.button.raise_()

    def _button_clicked(self):
        self.open_options(self.button.mapToGlobal(QtCore.QPoint(self.button.width(), 0)))

    def open_options(self, at):
        entry = self.entries.get(self.current)
        if entry is None:
            return
        from . import command_options

        options = command_options.options_menu(self.menu, entry, self.context)
        chosen = options.exec_(at)
        if chosen is not None:
            self.menu.close()  # Fusion closes the drop-down after an option


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


def build_menu(parent, entries, available, context=None):
    """QMenu for a list of config entries. Unavailable commands are greyed out. Each command
    has Fusion's options (three-dot button on hover, right-click): context = (tab id, group
    id, labels of the group's own big icons) for Pin to Toolbar, or None."""
    menu = QtWidgets.QMenu(parent)
    menu.setToolTipsVisible(True)
    options = _MenuOptions(menu, context)
    menu._sf_options = options  # kept with the menu
    checks = []  # (action, resolved, checked spec) re-checked each time the menu opens
    choices = None  # the ticked entries of one menu are one choice: exactly one tick
    for entry in entries:
        if entry is cfg.SEP:
            menu.addSeparator()
            continue
        if "submenu" in entry:
            submenu = build_menu(menu, entry["submenu"], available, context)
            submenu.setTitle(entry["label"])
            if entry.get("icon"):
                submenu.setIcon(ui_icon(entry["icon"]))
            menu.addMenu(submenu)
            continue
        action = menu.addAction(ui_icon(entry["icon"]), _menu_text(entry))
        action.setProperty("sciforgeIcon", entry["icon"] or "")  # (redrawn for a new look)
        resolved = resolve(entry["command"], available)
        options.add(action, entry)
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
    """Large icons on top, 'NAME ▾' underneath; the name opens the full menu. Commands pinned
    to the toolbar (ribbon_pins) get a large icon after the group's own."""

    def __init__(self, group, available, parent=None, tab_id=""):
        super().__init__(parent)
        self.group = group
        self.tab_id = tab_id
        self.available = available
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(2, 2, 2, 0)
        outer.setSpacing(0)
        self.row = QtWidgets.QHBoxLayout()
        self.row.setContentsMargins(4, 0, 4, 0)
        self.row.setSpacing(4)
        self.buttons = []
        outer.addLayout(self.row)

        self.label = QtWidgets.QToolButton()
        self.label.setProperty("role", "group")
        self.label.setText(group["title"] + " ▾")
        self.label.setToolButtonStyle(QtCore.Qt.ToolButtonTextOnly)
        self.label.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.menu = None
        self.label.clicked.connect(self.open_menu)
        outer.addWidget(self.label)
        self.refresh()

    def context(self):
        return (self.tab_id, self.group["id"], tuple(self.group["big"]))

    def refresh(self):
        """(Re)build the large icons (the group's own, then the pinned ones) and the menu (its
        keys may have changed)."""
        for button in self.buttons:
            self.row.removeWidget(button)
            button.deleteLater()
        self.buttons = []
        labels = list(self.group["big"])
        pinned = []
        try:
            from . import ribbon_pins

            pinned = [
                x
                for x in ribbon_pins.pinned(ribbon_pins.load(), self.tab_id, self.group["id"])
                if x not in labels
            ]
        except Exception as exc:
            warn("ribbon pins: %s" % exc)
        for label in labels + pinned:
            entry = cfg.find(self.group, label)
            if entry is None:
                if label not in pinned:
                    warn("ribbon: '%s' is not in group %s" % (label, self.group["title"]))
                continue
            if "submenu" in entry:  # big icon of a submenu runs its first entry
                entry = next(cfg.iter_items(entry["submenu"]))
            button = self._big_button(entry, self.available)
            button.setProperty("pinned", label in pinned)
            self.row.addWidget(button)
        old = self.menu
        self.menu = build_menu(self, self.group["items"], self.available, self.context())
        if old is not None:
            old.deleteLater()

    def _options(self, button, entry):
        from . import command_options

        menu = command_options.options_menu(button, entry, self.context())
        menu.exec_(button.mapToGlobal(QtCore.QPoint(0, button.height())))

    def _big_button(self, entry, available):
        button = QtWidgets.QToolButton()
        button.setIcon(ui_icon(entry["icon"]))
        button.setProperty("sciforgeIcon", entry["icon"] or "")  # (redrawn for a new look)
        button.setIconSize(QtCore.QSize(BIG, BIG))
        button.setFixedSize(BIG + 12, BIG + 12)
        button.setAutoRaise(True)
        resolved = resolve(entry["command"], available)
        key = shown_key(entry)
        tip = entry["label"] + ("  (%s)" % key if key else "")
        if resolved:
            button.clicked.connect(lambda _=False, r=resolved, e=entry: run(r, e["label"]))
            button.setToolTip(tip + ("\n" + entry["note"] if entry.get("note") else ""))
        else:
            button.setEnabled(False)
            button.setToolTip(tip + "\n" + (entry.get("note") or "Not available in SciForge yet"))
        button.setObjectName("SciForgeBig_" + entry["label"].replace(" ", "_"))
        # right-click: the command's options (Unpin from Toolbar, Change Keyboard Shortcut)
        button.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        button.customContextMenuRequested.connect(
            lambda _pos, b=button, e=entry: _safely(self._options, b, e)
        )
        self.buttons.append(button)
        return button

    def open_menu(self):
        self.label.setProperty("open", "true")
        self.label.style().polish(self.label)
        self.menu.exec_(self.label.mapToGlobal(QtCore.QPoint(0, self.label.height())))
        self.label.setProperty("open", "false")
        self.label.style().polish(self.label)


def _safely(function, *args):
    try:
        function(*args)
    except Exception as exc:
        warn("ribbon: %s" % exc)


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

        # The commands under the top bar: hidden while the Home tab is in front (set_home)
        self.command_area = QtWidgets.QWidget()
        self.command_area.setObjectName("SciForgeRibbonCommands")
        body = QtWidgets.QHBoxLayout(self.command_area)
        body.setContentsMargins(10, 4, 6, 4)
        body.setSpacing(10)
        body.addWidget(self._workspace_button(), 0, QtCore.Qt.AlignVCenter)

        right = QtWidgets.QVBoxLayout()
        right.setSpacing(2)
        tabs_row = QtWidgets.QHBoxLayout()
        tabs_row.setSpacing(0)
        self.tab_buttons = {}
        self.group_widgets = []
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
                widget = GroupWidget(grp, available, tab_id=tab["id"])
                self.group_widgets.append(widget)
                row.addWidget(widget)
            row.addStretch(1)
            self.page_index[tab["id"]] = self.pages.addWidget(page)
        tabs_row.addStretch(1)
        right.addLayout(tabs_row)
        # Let the ribbon clip instead of forcing the window wider (Fusion clips too).
        self.pages.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
        self.pages.setMinimumWidth(0)
        right.addWidget(self.pages)
        body.addLayout(right, 1)
        outer.addWidget(self.command_area)

        self.tab_buttons["sketch"].setVisible(False)
        # The DRAWING tab shows only while a drawing's tab is active (drawing_ui).
        self._drawing_mode = False
        if "drawing" in self.tab_buttons:
            self.tab_buttons["drawing"].setVisible(False)
        # The FLAT PATTERN tab shows only while a flat pattern is open (sheet metal).
        if "flat_pattern" in self.tab_buttons:
            self.tab_buttons["flat_pattern"].setVisible(False)
        self.select_tab("solid")

        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(700)
        self._timer.timeout.connect(self._refresh_title)
        self._timer.start()
        try:  # a new or activated window shows in the tabs at once (not at the next tick)
            area = Gui.getMainWindow().findChild(QtWidgets.QMdiArea)
            if area is not None:
                area.subWindowActivated.connect(
                    lambda *_a: QtCore.QTimer.singleShot(0, self._sync_tabs)
                )
        except Exception as exc:
            warn("document tabs: %s" % exc)

    def set_home(self, on):
        """Home in front: only the top bar (Home, File, Save, the document tabs) shows, like
        Fusion's Home; a design in front: the commands too."""
        try:
            self.command_area.setVisible(not on)
        except RuntimeError:
            pass

    def _sync_tabs(self):
        try:
            if self.isVisible():
                self.doc_tabs.sync()
        except RuntimeError:
            pass
        except Exception as exc:
            warn("document tabs: %s" % exc)

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
            button.setProperty("sciforgeIcon", entry["icon"] or "")  # (redrawn for a new look)
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
        # Fusion's document tabs, at the top (FreeCAD's own tab bar under the 3D view is
        # hidden while SciForge is on: doc_tabs)
        from .doc_tabs import DocumentTabs

        self.doc_tabs = DocumentTabs()
        row.addWidget(self.doc_tabs, 1)
        self.title = QtWidgets.QLabel("")  # (the active document's name; the tabs show it)
        self.title.setProperty("role", "document")
        self.title.hide()
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
        # The update icon (top right, before the search): shown while a newer SciForge is known
        # (update_ui.pending); its menu has Update now and What's new.
        self.update_icon = QtWidgets.QToolButton()
        self.update_icon.setObjectName("SciForgeUpdateIcon")
        self.update_icon.setIcon(ui_icon("update_available"))
        self.update_icon.setProperty("sciforgeIcon", "update_available")
        self.update_icon.setIconSize(QtCore.QSize(SMALL, SMALL))
        self.update_icon.setAutoRaise(True)
        self.update_icon.clicked.connect(self._update_menu)
        self.update_icon.hide()
        row.addWidget(self.update_icon)
        search = QtWidgets.QToolButton()
        search.setIcon(ui_icon("nav_zoom"))
        search.setProperty("sciforgeIcon", "nav_zoom")
        search.setIconSize(QtCore.QSize(SMALL, SMALL))
        search.setAutoRaise(True)
        search.setToolTip("Search commands  (S)")
        search.clicked.connect(lambda: run(("SciForge_CommandSearch", None), "Search"))
        row.addWidget(search)
        self.refresh_update()
        return bar

    def refresh_update(self):
        """Show the update icon while a newer SciForge is known."""
        try:
            from . import update_ui

            version = update_ui.pending()
            self.update_icon.setToolTip(
                "SciForge %s is available. Click to update." % version if version else ""
            )
            self.update_icon.setVisible(bool(version))
        except Exception as exc:
            warn("update icon: %s" % exc)

    def _update_menu(self):
        try:
            from . import update_ui

            version = update_ui.pending()
            if not version:
                self.refresh_update()
                return
            menu = QtWidgets.QMenu(self.update_icon)
            menu.setObjectName("SciForgeUpdateMenu")
            title = menu.addAction("SciForge %s is available" % version)
            title.setEnabled(False)
            menu.addSeparator()
            menu.addAction("Update now", lambda: QtCore.QTimer.singleShot(0, update_ui.install_now))
            menu.addAction(
                "What's new",
                lambda: QtCore.QTimer.singleShot(0, lambda: update_ui.whats_new(version)),
            )
            menu.exec_(self.update_icon.mapToGlobal(QtCore.QPoint(0, self.update_icon.height())))
        except Exception as exc:
            warn("update icon: %s" % exc)

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
            from . import freecad_tools_ui

            menu.addMenu(freecad_tools_ui.menu(menu))  # FreeCAD's workbenches (pass-through)
            menu.addSeparator()
        except Exception as exc:
            warn("file menu: %s" % exc)
        for action in Gui.getMainWindow().menuBar().actions():
            if action.menu() is not None and action.text():
                if action.text().replace("&", "").strip() == "Help":
                    try:  # Help > Report a Problem... (report_ui)
                        __import__("sciforge.report_ui").report_ui.add_help_entry(action.menu())
                    except Exception as exc:
                        warn("help menu: %s" % exc)
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

    # -- customization (Pin to Toolbar, Change Keyboard Shortcut) ------
    def refresh_customization(self):
        """Pins or keys changed: rebuild every group's large icons and menu."""
        for widget in self.group_widgets:
            try:
                widget.refresh()
            except Exception as exc:
                warn("ribbon group %s: %s" % (widget.group.get("title"), exc))

    def contextMenuEvent(self, event):
        """Right-click on the ribbon (not on a command): Reset All Toolbar Customization."""
        try:
            menu = QtWidgets.QMenu(self)
            menu.setObjectName("SciForgeRibbonMenu")
            reset = menu.addAction("Reset All Toolbar Customization")
            from . import command_options

            reset.triggered.connect(lambda: command_options.reset_all_toolbar(self))
            menu.exec_(event.globalPos())
            event.accept()
        except Exception as exc:
            warn("ribbon menu: %s" % exc)

    # -- behaviour ------------------------------------------------------
    def select_tab(self, tab_id, user=False):
        for tid, button in self.tab_buttons.items():
            button.setChecked(tid == tab_id)
        self.pages.setCurrentIndex(self.page_index[tab_id])
        if user and tab_id not in CONTEXTUAL:
            self._user_tab = tab_id

    def set_sketch_mode(self, on):
        """While a sketch is open, show and select the contextual SKETCH tab."""
        if on == self._sketch_mode:
            return
        self._sketch_mode = on
        drawing = getattr(self, "_drawing_mode", False)  # (a drawing's tab keeps DRAWING)
        self.tab_buttons["sketch"].setVisible(on and not drawing)
        if not drawing:
            back = "flat_pattern" if getattr(self, "_flat_mode", False) else self._user_tab
            self.select_tab("sketch" if on else back)
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
            elif tid == "flat_pattern":
                button.setVisible(getattr(self, "_flat_mode", False) and not on)
            else:
                button.setVisible(not on and not getattr(self, "_flat_mode", False))
        self.workspace.setText("DRAWING ▾" if on else "DESIGN ▾")
        if on:
            self.select_tab("drawing")
        elif getattr(self, "_flat_mode", False):
            self.select_tab("flat_pattern")
        else:
            self.select_tab("sketch" if self._sketch_mode else self._user_tab)
        log("ribbon: drawing mode %s" % ("on" if on else "off"))

    def set_flat_pattern_mode(self, on):
        """While a flat pattern is open (sheet metal), Fusion shows its FLAT PATTERN tab
        alone (Export DXF, Finish Flat Pattern); back to the design's tabs after.
        SCIFORGE wave 6 (sm-flat)."""
        if on == getattr(self, "_flat_mode", False) or "flat_pattern" not in self.tab_buttons:
            return
        self._flat_mode = on
        drawing = getattr(self, "_drawing_mode", False)
        for tid, button in self.tab_buttons.items():
            if tid == "flat_pattern":
                button.setVisible(on and not drawing)
            elif tid == "drawing":
                button.setVisible(drawing)
            elif tid == "sketch":
                button.setVisible(self._sketch_mode and not on and not drawing)
            else:
                button.setVisible(not on and not drawing)
        if drawing:
            return
        if on:
            self.select_tab("flat_pattern")
        else:
            back = self._user_tab if self._user_tab in self.page_index else "solid"
            self.select_tab("sketch" if self._sketch_mode else back)
        log("ribbon: flat pattern mode %s" % ("on" if on else "off"))

    def current_tab(self):
        for tid, button in self.tab_buttons.items():
            if button.isChecked():
                return tid
        return None

    def _refresh_title(self):
        try:
            if self.isVisible():
                self.doc_tabs.sync()
        except Exception as exc:
            warn("document tabs: %s" % exc)
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
