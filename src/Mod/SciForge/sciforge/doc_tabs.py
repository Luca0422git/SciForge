# SPDX-License-Identifier: LGPL-2.1-or-later
"""The open documents as tabs at the top, in SciForge's application bar, like Fusion's
document tabs (Luca, 2026-10-16: "the toolbar where open documents sit should be at the top.
like fusion"). FreeCAD keeps its own tab bar under the 3D view (QMdiArea in tabbed mode,
QTabWidget::South in MainWindow.cpp).

How it is built: FreeCAD's own tab bar keeps working but is hidden while SciForge is on, and
this bar mirrors it (same tabs, same order, same current one). A click here selects the tab
there (which activates its window); a tab's x selects it and closes the active window, as
FreeCAD's own x does. Code that moves FreeCAD's tabs (drawing sheets) keeps working.
"""

from . import log, warn
from .compat import QtCore, QtWidgets

_state = {"hidden": None, "filter": None}


def _area():
    try:
        import FreeCADGui as Gui

        return Gui.getMainWindow().findChild(QtWidgets.QMdiArea)
    except Exception:
        return None


def mdi_tabs():
    """FreeCAD's own document tab bar (a direct child of the MDI area), or None."""
    area = _area()
    if area is None:
        return None
    # by FreeCAD's name for it (MainWindow.cpp): findChildren(QTabBar, "", FindDirectChildrenOnly)
    # returns nothing in FreeCAD 1.1.4's PySide (the "" name), only options= works
    bar = area.findChild(QtWidgets.QTabBar, "mdiAreaTabBar")
    if bar is not None:
        return bar
    for bar in area.findChildren(QtWidgets.QTabBar, options=QtCore.Qt.FindDirectChildrenOnly):
        return bar
    return None


def _clean(text):
    return (text or "").replace("[*]", "").strip()


class _KeepHidden(QtCore.QObject):
    """FreeCAD (or Qt) shows the MDI tab bar again when the view mode changes: hide it."""

    def eventFilter(self, obj, event):
        try:
            if event.type() == QtCore.QEvent.Show and _state["hidden"] is obj:
                QtCore.QTimer.singleShot(0, obj.hide)
        except Exception:
            pass
        return False


def hide_mdi_tabs(on):
    """SciForge on: FreeCAD's tab bar under the 3D view hidden (the tabs are at the top);
    off: shown again."""
    try:
        bar = mdi_tabs()
        old = _state["hidden"]
        if old is not None and old is not bar:
            try:
                old.removeEventFilter(_state["filter"])
            except RuntimeError:
                pass
            _state["hidden"] = None
        if bar is None:
            return
        if on:
            if _state["filter"] is None:
                _state["filter"] = _KeepHidden()
            if _state["hidden"] is not bar:
                bar.installEventFilter(_state["filter"])
                _state["hidden"] = bar
            bar.hide()
        else:
            if _state["hidden"] is bar:
                bar.removeEventFilter(_state["filter"])
                _state["hidden"] = None
            bar.show()
    except Exception as exc:
        warn("document tabs: %s" % exc)


class DocumentTabs(QtWidgets.QTabBar):
    """The mirror of FreeCAD's document tabs, in the application bar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SciForgeDocumentTabs")
        self.setTabsClosable(True)
        self.setDocumentMode(True)
        self.setDrawBase(False)
        self.setExpanding(False)
        self.setUsesScrollButtons(True)
        self.setElideMode(QtCore.Qt.ElideRight)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self._syncing = False
        self.currentChanged.connect(self._clicked)
        self.tabCloseRequested.connect(self._close)

    def entries(self):
        """[(text, icon)] of FreeCAD's tabs, and its current index."""
        bar = mdi_tabs()
        if bar is None:
            return [], -1
        return [(_clean(bar.tabText(i)), bar.tabIcon(i)) for i in range(bar.count())], (
            bar.currentIndex()
        )

    def sync(self):
        """Show FreeCAD's tabs here (names, icons, order, the current one)."""
        if self._syncing:
            return
        self._syncing = True
        try:
            hide_mdi_tabs(True)  # (a new tab bar after a view mode change)
            items, current = self.entries()
            texts = [self.tabText(i) for i in range(self.count())]
            if texts != [t for t, _i in items]:
                while self.count():
                    self.removeTab(0)
                for text, icon in items:
                    self.setTabToolTip(self.addTab(icon, text), text)
            if 0 <= current < self.count() and self.currentIndex() != current:
                self.setCurrentIndex(current)
            self.setVisible(bool(items))
        except Exception as exc:
            warn("document tabs: %s" % exc)
        finally:
            self._syncing = False

    def _clicked(self, index):
        if self._syncing or index < 0:
            return
        try:
            bar = mdi_tabs()
            if bar is not None and bar.currentIndex() != index:
                bar.setCurrentIndex(index)  # FreeCAD's bar activates the window
        except Exception as exc:
            warn("document tab: %s" % exc)

    def _close(self, index):
        try:
            bar = mdi_tabs()
            area = _area()
            if bar is None or area is None or not 0 <= index < bar.count():
                return
            log("document tab closed: %s" % self.tabText(index))
            # the same as FreeCAD's own x: its tab bar asks the MDI area to close that window
            bar.tabCloseRequested.emit(index)
            QtCore.QTimer.singleShot(0, self.sync)
        except Exception as exc:
            warn("document tab close: %s" % exc)
