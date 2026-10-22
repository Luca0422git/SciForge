# SPDX-License-Identifier: LGPL-2.1-or-later
"""The short message after an export or an import that says what the file leaves out or
what did not come in (export_report.py counts, export_report_core.py words it).

One small card in the bottom right corner of the 3D view, over the design: a title
("Exported two.stl"), "Not kept in this file:" and a line per item. No popup, no button to
press: it goes away by itself after a few seconds (longer for a longer list; the mouse
over it keeps it), or with its x. Nothing is shown when nothing is lost. Every report also
goes to the Report view ([SciForge] Not in two.stl: ...), and the last ones are kept in
recent() for the AI tools and the tests.

Every entry point catches its own errors: an export that worked never fails because its
report could not be shown.
"""

from . import export_report, log, warn
from . import export_report_core as core

RECENT_MAX = 20
_state = {"widget": None, "recent": []}

QSS = """
#SciForgeNotice { background: #3b4453; border: 1px solid #56606f; border-radius: 4px; }
#SciForgeNotice QLabel { background: transparent; color: #f5f5f5; }
#SciForgeNoticeTitle { font-weight: bold; }
#SciForgeNoticeLead { color: #c3cad4; }
#SciForgeNoticeClose { background: transparent; color: #c3cad4; border: none;
    font-size: 14px; padding: 0 4px; }
#SciForgeNoticeClose:hover { color: #ffffff; }
"""


def recent():
    """The last reports, newest last: [{"title", "lead", "lines", "kind"}]."""
    return list(_state["recent"])


def clear_recent():
    del _state["recent"][:]


def current():
    """The notice widget when it is on screen, else None (tests)."""
    widget = _state["widget"]
    try:
        if widget is not None and widget.isVisible():
            return widget
    except RuntimeError:
        _state["widget"] = None
    return None


def show(title, lead, lines, kind="export"):
    """Show the card (GUI) and remember the report. `lines`: the items' sentences."""
    entry = {"title": title, "lead": lead, "lines": list(lines), "kind": kind}
    _state["recent"].append(entry)
    del _state["recent"][:-RECENT_MAX]
    try:
        import FreeCAD as App

        if not App.GuiUp:
            return entry
        widget = _widget()
        if widget is not None:
            widget.present(title, lead, lines)
    except Exception as exc:
        warn("the export / import message could not be shown: %s" % exc)
    return entry


# -- entry points for the export and import paths --------------------------------------------
def report_export(file_name, entries, verb="Exported", lead="Not kept in this file:"):
    """After an export: the card and the log line, when the file leaves something out.
    Returns the entries."""
    try:
        if not entries:
            return entries
        export_report.log_report(file_name, entries)
        show(
            "%s %s" % (verb, file_name),
            lead,
            core.notice_lines(entries),
            "export",
        )
    except Exception as exc:
        warn("export report: %s" % exc)
    return entries


def report_losses(doc, objects, fmt, file_name, purpose="file", verb="Exported", **options):
    """Count and show what an export of `objects` as `fmt` leaves out (see
    export_report.losses). Never raises."""
    entries = export_report.safe_losses(doc, objects, fmt, purpose, **options)
    several = str(file_name).endswith(" files")  # One File Per Body: "3 files"
    lead = "Not kept in these files:" if several else "Not kept in this file:"
    return report_export(file_name, entries, verb, lead)


def report_combined(file_names, reports, verb="Exported"):
    """Several files at once (Export Everything): reports = [(format name, entries)]."""
    try:
        entries = core.combine(reports)
        return report_export(file_names, entries, verb, "Not kept in these files:")
    except Exception as exc:
        warn("export report: %s" % exc)
        return []


def report_import(file_name, entries, verb="Inserted"):
    """After an import: what the file had that did not come in (or came in changed)."""
    try:
        if not entries:
            return entries
        log(
            "%s %s. Not brought in, or changed: %s."
            % (verb, file_name, "; ".join(e["text"] for e in entries))
        )
        show(
            "%s %s" % (verb, file_name),
            "Not brought in, or changed:",
            core.notice_lines(entries),
            "import",
        )
    except Exception as exc:
        warn("import report: %s" % exc)
    return entries


# -- the card --------------------------------------------------------------------------------
def _widget():
    widget = _state["widget"]
    try:
        if widget is not None:
            widget.objectName()  # raises when Qt deleted it
            return widget
    except RuntimeError:
        pass
    import FreeCADGui as Gui

    window = Gui.getMainWindow()
    if window is None:
        return None
    widget = _make_notice(window)
    _state["widget"] = widget
    return widget


def _make_notice(window):
    from .compat import QtCore, QtWidgets

    class Notice(QtWidgets.QFrame):
        def __init__(self, parent):
            super().__init__(parent)
            self.setObjectName("SciForgeNotice")
            self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating, True)
            self.setFocusPolicy(QtCore.Qt.NoFocus)
            self.setFixedWidth(380)
            try:
                from . import theme

                self.setStyleSheet(theme.translate(QSS))
            except Exception:
                self.setStyleSheet(QSS)
            outer = QtWidgets.QVBoxLayout(self)
            outer.setContentsMargins(12, 8, 8, 10)
            outer.setSpacing(4)
            top = QtWidgets.QHBoxLayout()
            top.setSpacing(4)
            self.title = QtWidgets.QLabel("")
            self.title.setObjectName("SciForgeNoticeTitle")
            self.title.setWordWrap(True)
            self.close_button = QtWidgets.QToolButton()
            self.close_button.setObjectName("SciForgeNoticeClose")
            self.close_button.setText("×")
            self.close_button.setToolTip("Close")
            self.close_button.setFocusPolicy(QtCore.Qt.NoFocus)
            self.close_button.clicked.connect(self._close_clicked)
            top.addWidget(self.title, 1)
            top.addWidget(self.close_button, 0, QtCore.Qt.AlignTop)
            outer.addLayout(top)
            self.lead = QtWidgets.QLabel("")
            self.lead.setObjectName("SciForgeNoticeLead")
            outer.addWidget(self.lead)
            self.body = QtWidgets.QLabel("")
            self.body.setObjectName("SciForgeNoticeBody")
            self.body.setWordWrap(True)
            self.body.setTextFormat(QtCore.Qt.PlainText)
            outer.addWidget(self.body)
            self.timer = QtCore.QTimer(self)
            self.timer.setSingleShot(True)
            self.timer.timeout.connect(self._time_up)
            self.hide()
            try:
                parent.installEventFilter(self)
            except Exception:
                pass

        def present(self, title, lead, lines):
            self.title.setText(title)
            self.lead.setText(lead)
            self.body.setText("\n".join("• " + line for line in lines))
            self.adjustSize()
            self.place()
            self.show()
            self.raise_()
            self.timer.start(min(30000, 10000 + 2000 * len(lines)))

        def place(self):
            """Bottom right of the 3D view area (the MDI area), 12 px in."""
            try:
                window = self.parentWidget()
                area = window.centralWidget()
                if area is not None:
                    corner = area.mapTo(window, QtCore.QPoint(area.width(), area.height()))
                else:
                    corner = QtCore.QPoint(window.width(), window.height())
                self.adjustSize()
                x = max(0, corner.x() - self.width() - 12)
                y = max(0, corner.y() - self.height() - 12)
                self.move(x, y)
            except Exception:
                pass

        def eventFilter(self, obj, event):
            try:
                if event.type() == QtCore.QEvent.Resize and self.isVisible():
                    self.place()
            except Exception:
                pass
            return False

        def enterEvent(self, event):
            try:
                self.timer.stop()
            except Exception:
                pass
            super().enterEvent(event)

        def leaveEvent(self, event):
            try:
                if self.isVisible():
                    self.timer.start(5000)
            except Exception:
                pass
            super().leaveEvent(event)

        def _close_clicked(self, *_args):
            try:
                self.timer.stop()
                self.hide()
            except Exception as exc:
                warn("message: %s" % exc)

        def _time_up(self):
            try:
                self.hide()
            except Exception:
                pass

    return Notice(window)
