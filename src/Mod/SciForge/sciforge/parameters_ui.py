# SPDX-License-Identifier: LGPL-2.1-or-later
"""Change Parameters dialog (Fusion: Modify > Change Parameters).

Top: user parameters (Name, Unit, Expression, Value, Comment), with + / -.
Bottom: model parameters, every dimension in the design, editable in place.
Expressions may use parameter names directly: `width / 2 + wall`.
Everything is one undo step; Cancel puts the design back as it was.
"""
import FreeCAD as App
import FreeCADGui as Gui

from . import log, parameters, parameters_core as core, ui_icon, ui_icon_path, warn
from .compat import QtCore, QtWidgets

USER_COLUMNS = ["Name", "Unit", "Expression", "Value", "Comment"]
MODEL_COLUMNS = ["Parameter", "Name", "Expression", "Value"]


def _fmt(value, unit):
    if isinstance(value, float):
        text = ("%.4f" % value).rstrip("0").rstrip(".")
    else:
        text = str(value)
    return text + (" " + unit if unit else "")


class ParametersDialog(QtWidgets.QDialog):
    last = None

    def __init__(self, doc, parent=None):
        super().__init__(parent or Gui.getMainWindow())
        ParametersDialog.last = self
        self.doc = doc
        self.setWindowTitle("Parameters")
        self.setWindowIcon(ui_icon("parameters"))
        self.resize(760, 560)
        doc.openTransaction("Change Parameters")
        self._loading = False

        layout = QtWidgets.QVBoxLayout(self)
        head = QtWidgets.QHBoxLayout()
        head.addWidget(QtWidgets.QLabel("<b>User Parameters</b>"))
        head.addStretch(1)
        self.add_button = QtWidgets.QToolButton()
        self.add_button.setText("+")
        self.add_button.setToolTip("Add a user parameter")
        self.add_button.clicked.connect(self.add_parameter)
        self.remove_button = QtWidgets.QToolButton()
        self.remove_button.setText("−")
        self.remove_button.setToolTip("Delete the selected user parameter")
        self.remove_button.clicked.connect(self.remove_parameter)
        head.addWidget(self.add_button)
        head.addWidget(self.remove_button)
        layout.addLayout(head)

        self.user = QtWidgets.QTableWidget(0, len(USER_COLUMNS))
        self.user.setHorizontalHeaderLabels(USER_COLUMNS)
        self.user.horizontalHeader().setStretchLastSection(True)
        self.user.verticalHeader().setVisible(False)
        self.user.itemChanged.connect(self._user_changed)
        layout.addWidget(self.user, 1)

        layout.addWidget(QtWidgets.QLabel("<b>Model Parameters</b>"))
        self.model = QtWidgets.QTreeWidget()
        self.model.setColumnCount(len(MODEL_COLUMNS))
        self.model.setHeaderLabels(MODEL_COLUMNS)
        self.model.itemChanged.connect(self._model_changed)
        layout.addWidget(self.model, 2)

        self.message = QtWidgets.QLabel("")
        self.message.setWordWrap(True)
        self.message.setStyleSheet("color: #ff8a80;")
        layout.addWidget(self.message)
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.reload()

    # -- filling -------------------------------------------------------------------
    def reload(self):
        self._loading = True
        try:
            rows = parameters.user_parameters(self.doc)
            self.user.setRowCount(len(rows))
            for r, row in enumerate(rows):
                cells = [
                    row["name"],
                    row["unit"],
                    row["expression"] or _fmt(row["value"], ""),
                    _fmt(row["value"], row["unit"]),
                    row["comment"],
                ]
                for c, text in enumerate(cells):
                    item = QtWidgets.QTableWidgetItem(text)
                    if c in (0, 1, 3):
                        item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
                    self.user.setItem(r, c, item)
            self.user.resizeColumnsToContents()
            expanded = {
                self.model.topLevelItem(i).text(0)
                for i in range(self.model.topLevelItemCount())
                if self.model.topLevelItem(i).isExpanded()
            }
            self.model.clear()
            groups = {}
            for row in parameters.model_parameters(self.doc):
                group = groups.get(row["owner"])
                if group is None:
                    group = QtWidgets.QTreeWidgetItem(self.model, [row["owner"]])
                    group.setExpanded(not expanded or row["owner"] in expanded)
                    groups[row["owner"]] = group
                item = QtWidgets.QTreeWidgetItem(
                    group,
                    [
                        "",
                        row["label"],
                        row["expression"] or _fmt(row["value"], row["unit"]),
                        _fmt(row["value"], row["unit"]),
                    ],
                )
                item.setData(0, QtCore.Qt.UserRole, row)
                item.setFlags(item.flags() | QtCore.Qt.ItemIsEditable)
            for c in range(len(MODEL_COLUMNS)):
                self.model.resizeColumnToContents(c)
        finally:
            self._loading = False

    # -- editing -------------------------------------------------------------------
    def _apply(self, fn):
        try:
            fn()
            self.doc.recompute()
            self.message.setText("")
        except Exception as exc:
            self.message.setText("⚠ %s" % exc)
        QtCore.QTimer.singleShot(0, self.reload)

    def _user_changed(self, item):
        if self._loading or item.column() not in (2, 4):
            return
        name = self.user.item(item.row(), 0).text()
        if item.column() == 2:
            self._apply(lambda: parameters.set_user(self.doc, name, item.text()))
        else:
            obj = parameters.container(self.doc)
            self._apply(lambda: obj.setDocumentationOfProperty(name, item.text()))

    def _model_changed(self, item, column):
        if self._loading or column != 2:
            return
        row = item.data(0, QtCore.Qt.UserRole)
        if row is None:
            return
        self._apply(lambda: parameters.set_model(self.doc, row, item.text(2)))

    def add_parameter(self, name=None, unit="mm", text="10", comment=""):
        if name is None:
            name, ok = QtWidgets.QInputDialog.getText(self, "Add Parameter", "Name:")
            if not ok or not name.strip():
                return
            unit, ok = QtWidgets.QInputDialog.getItem(
                self, "Add Parameter", "Unit:", ["mm", "deg", ""], 0, False
            )
            if not ok:
                return
            text, ok = QtWidgets.QInputDialog.getText(
                self, "Add Parameter", "Expression or value:", text="10"
            )
            if not ok:
                return
        self._apply(lambda: parameters.add_user(self.doc, name.strip(), unit, text, comment))

    def remove_parameter(self):
        row = self.user.currentRow()
        if row < 0:
            return
        name = self.user.item(row, 0).text()
        self._apply(lambda: parameters.remove_user(self.doc, name))

    def accept(self):
        self.doc.recompute()
        self.doc.commitTransaction()
        log("parameters changed")
        super().accept()

    def reject(self):
        self.doc.abortTransaction()
        self.doc.recompute()
        super().reject()


class ChangeParametersCommand:
    def GetResources(self):
        return {
            "MenuText": "Change Parameters",
            "ToolTip": "Named user parameters and every dimension " "of the design in one table",
            "Pixmap": ui_icon_path("parameters"),
        }

    def IsActive(self):
        return App.ActiveDocument is not None

    def Activated(self):
        try:
            dialog = ParametersDialog(App.ActiveDocument)
            dialog.show()
        except Exception as exc:
            warn("Change Parameters failed to open: %s" % exc)
