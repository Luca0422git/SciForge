# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's SKETCH PALETTE: the options panel on the right while a sketch is open.

It is put at the top of FreeCAD's sketch panel (whose own sections stay below it,
folded: tool settings, solver messages, constraint and element lists). FreeCAD's
"Close" button is replaced by the palette's Finish Sketch button at the bottom.

Rows (Fusion's order): Linetype (construction), Look At, Sketch Grid, Snap, Slice,
Show Profile, Show Points, Show Dimensions, Show Constraints, Show Projected
Geometries, 3D Sketch. Options are remembered between sessions (sketch_mode.option).
"""

import FreeCADGui as Gui

from . import sketch_mode, ui_icon, ui_icon_path, warn
from .compat import QtCore, QtWidgets

ROWS = [
    ("grid", "Sketch Grid", "Show the grid on the sketch plane"),
    ("snap", "Snap", "Snap the pointer to the grid"),
    ("slice", "Slice", "Cut away the part in front of the sketch plane so the sketch is visible"),
    ("profile", "Show Profile", "Shade closed areas (profiles) light blue"),
    ("points", "Show Points", "Show the sketch points"),
    ("dimensions", "Show Dimensions", "Show the sketch dimensions"),
    ("constraints", "Show Constraints", "Show the constraint symbols"),
    ("projected", "Show Projected Geometries", "Show geometry projected from the part"),
]

STYLE = """
#SciForgeSketchPalette { background: #3b4453; border: 1px solid #56606f; border-radius: 2px; }
#SciForgeSketchPalette QLabel[role="title"] { color: #f5f5f5; font-weight: bold;
    letter-spacing: 0.5px; padding: 6px 8px; background: #2f3643; }
#SciForgeSketchPalette QToolButton[role="section"] { color: #f5f5f5; font-weight: bold;
    border: none; background: transparent; padding: 4px 6px; text-align: left; }
#SciForgeSketchPalette QLabel { color: #f5f5f5; }
#SciForgeSketchPalette QCheckBox { color: #f5f5f5; }
#SciForgeSketchPalette QPushButton[role="finish"] { background: #3fa9f5; color: #ffffff;
    border: none; border-radius: 2px; padding: 6px 14px; font-weight: bold; }
#SciForgeSketchPalette QPushButton[role="finish"]:hover { background: #63b8f7; }
#SciForgeSketchPalette QToolButton[role="option"] { background: #4a5568; border: 1px solid #56606f;
    border-radius: 2px; padding: 2px; }
#SciForgeSketchPalette QToolButton[role="option"]:hover { background: #56647a; }
#SciForgeSketchPalette QToolButton[role="option"]:checked { background: #f5a142;
    border: 1px solid #ffc27a; }
#SciForgeSketchPalette QCheckBox::indicator { width: 13px; height: 13px; border: 1px solid #8a94a3;
    border-radius: 2px; background: #2b313b; }
#SciForgeSketchPalette QCheckBox::indicator:hover { border-color: #3fa9f5; }
#SciForgeSketchPalette QCheckBox::indicator:checked { background: #3fa9f5; border-color: #3fa9f5;
    image: url(CHECK); }
#SciForgeSketchPalette QCheckBox::indicator:disabled { background: #3b4453; border-color: #5d6778; }
"""

STYLE = STYLE.replace("CHECK", ui_icon_path("palette_check").replace("\\", "/"))

# FreeCAD's sketch panel sections Fusion has no equivalent of (it shows constraints as
# glyphs on the curves, not as lists): hidden while the palette is there.
HIDDEN_SECTIONS = ("SketcherGui::TaskSketcherConstraints", "SketcherGui::TaskSketcherElements")


class Palette(QtWidgets.QFrame):
    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.session = session
        self.setObjectName("SciForgeSketchPalette")
        self.setStyleSheet(STYLE)
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 6)
        outer.setSpacing(2)
        title = QtWidgets.QLabel("SKETCH PALETTE")
        title.setProperty("role", "title")
        outer.addWidget(title)

        self.section = QtWidgets.QToolButton()
        self.section.setProperty("role", "section")
        self.section.setText("▾ Options")
        self.section.setCheckable(True)
        self.section.setChecked(True)
        self.section.toggled.connect(self._fold)
        outer.addWidget(self.section)

        self.body = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(self.body)
        form.setContentsMargins(10, 0, 10, 4)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(5)
        form.setLabelAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

        self.construction = self._tool_button(
            "sk_line",
            "Construction (X): turn the selected curves into construction "
            "curves, or (nothing selected) draw new curves as construction. "
            "Orange while new curves are construction.",
        )
        self.construction.setObjectName("SciForgePaletteConstruction")
        self.construction.setCheckable(True)
        self.construction.setChecked(sketch_mode.construction_mode())
        self.construction.clicked.connect(self._construction_clicked)
        form.addRow("Linetype", self.construction)
        self._mode = self.construction.isChecked()
        self._mode_timer = QtCore.QTimer(self)
        self._mode_timer.setInterval(300)
        self._mode_timer.timeout.connect(self._refresh_mode)
        self._mode_timer.start()

        self.look_at = self._tool_button("nav_lookat", "Look straight at the sketch")
        self.look_at.setObjectName("SciForgePaletteLookAt")
        self.look_at.clicked.connect(lambda: QtCore.QTimer.singleShot(0, session.look_at))
        form.addRow("Look At", self.look_at)

        self.boxes = {}
        for key, label, tip in ROWS:
            box = QtWidgets.QCheckBox()
            box.setObjectName("SciForgePalette_" + key)
            box.setChecked(sketch_mode.option(key))
            box.setToolTip(tip)
            box.toggled.connect(lambda on, k=key: self._toggled(k, on))
            text = QtWidgets.QLabel(label)
            text.setToolTip(tip)
            form.addRow(text, box)
            self.boxes[key] = box

        sketch3d = QtWidgets.QCheckBox()
        sketch3d.setEnabled(False)
        sketch3d.setToolTip(
            "Not available: FreeCAD sketches are flat. Use Project / Include to bring "
            "edges of the part into the sketch."
        )
        form.addRow("3D Sketch", sketch3d)
        outer.addWidget(self.body)

        self.finish = QtWidgets.QPushButton("Finish Sketch")
        self.finish.setProperty("role", "finish")
        self.finish.setObjectName("SciForgePaletteFinish")
        self.finish.clicked.connect(lambda: self._later("SciForge_FinishSketch"))
        row = QtWidgets.QHBoxLayout()
        row.setContentsMargins(8, 4, 8, 0)
        row.addStretch(1)
        row.addWidget(self.finish)
        outer.addLayout(row)
        self.hidden = []

    def _tool_button(self, icon, tip):
        button = QtWidgets.QToolButton()
        button.setProperty("role", "option")
        button.setIcon(ui_icon(icon))
        button.setIconSize(QtCore.QSize(18, 18))
        button.setToolTip(tip)
        return button

    def _fold(self, open_):
        self.body.setVisible(open_)
        self.section.setText(("▾ " if open_ else "▸ ") + "Options")

    def _construction_clicked(self, *_):
        # the button shows the drawing mode; FreeCAD's command decides (selected curves
        # are toggled, else the mode), the timer below shows the result
        self.construction.setChecked(self._mode)
        self._later("Sketcher_ToggleConstruction")

    def _refresh_mode(self):
        """Show whether new curves are drawn as construction (X with nothing selected
        switches that on: without this it was invisible until the next curve came out
        orange and made no profile)."""
        try:
            mode = sketch_mode.construction_mode()
            if self.construction.isChecked() != mode:
                self.construction.setChecked(mode)
            if mode != self._mode:
                self._mode = mode
                from . import commands

                commands.tell(
                    "New curves are construction curves (orange, no profiles). "
                    "X again (or Linetype in the palette) for normal curves."
                    if mode
                    else "New curves are normal curves again."
                )
        except Exception as exc:
            self._mode_timer.stop()
            warn("sketch palette: %s" % exc)

    def _toggled(self, key, on):
        try:
            sketch_mode.set_option(key, on)
        except Exception as exc:
            warn("sketch palette: %s" % exc)

    def _later(self, command):
        """Run a command after this click is done (Finish Sketch deletes this panel)."""

        def run():
            try:
                Gui.runCommand(command)
            except Exception as exc:
                warn("%s: %s" % (command, exc))

        QtCore.QTimer.singleShot(0, run)

    def remove(self):
        try:
            self._mode_timer.stop()
        except Exception:
            pass
        for widget in self.hidden:
            try:
                widget.setVisible(True)
            except Exception:
                pass
        self.hidden = []
        try:
            self.setParent(None)
            self.deleteLater()
        except Exception:
            pass


def sketch_panel():
    """(panel widget whose layout holds the sketch sections, TaskView) or (None, None)."""
    main = Gui.getMainWindow()
    for widget in main.findChildren(QtWidgets.QWidget):
        if widget.metaObject().className() == "SketcherGui::TaskSketcherMessages":
            parent = widget.parentWidget()
            if parent is not None and parent.layout() is not None:
                return parent
    return None


def install(session):
    """Put the palette at the top of the open sketch's panel; None if the panel is not
    there (yet)."""
    panel = sketch_panel()
    if panel is None:
        return None
    existing = panel.findChild(QtWidgets.QFrame, "SciForgeSketchPalette")
    if existing is not None:
        return existing
    palette = Palette(session, panel)
    panel.layout().insertWidget(0, palette)
    # FreeCAD's Close button: Finish Sketch is in the palette (and the ribbon). FreeCAD's
    # constraint and element lists: Fusion shows constraints as glyphs only.
    try:
        for control in Gui.getMainWindow().findChildren(QtWidgets.QWidget):
            name = control.metaObject().className()
            if name == "Gui::TaskView::TaskEditControl" or name in HIDDEN_SECTIONS:
                if control.isVisible():
                    control.setVisible(False)
                    palette.hidden.append(control)
    except Exception:
        pass
    return palette
