# SPDX-License-Identifier: LGPL-2.1-or-later
"""Fusion's Breakout Section View in SciForge: click a view, click a closed boundary
around what should show inside and its first point again (or Enter): the cut is made at
the depth offered (half the parts' depth); type another depth or press Default; OK.
Double-click inside the boundary later: the same dialog, with Remove Breakout. The logic
is in drawing_breakout.py."""

import math

from . import commands, drawing, drawing_breakout, drawing_ui
from .compat import QtCore, QtWidgets
from .drawing_ui import DrawingPanel, view_at

CLOSE_PIXELS = 10  # a click this near the first point closes the boundary


class BreakoutPanel(DrawingPanel):
    """Fusion's Breakout Section View: the view, the boundary's points, the depth."""

    title = "Breakout Section View"
    icon = "dw_section_view"

    def __init__(self, page, view=None):
        super().__init__(page, "Breakout Section View" if view is None else "Edit Breakout")
        self.view = view
        self.points = []
        self.closed = view is not None and drawing_breakout.has_breakout(view)
        data = drawing_breakout.breakout_of(view) if self.closed else None
        depth = data["depth"] if data else None
        self.distance = QtWidgets.QLineEdit("" if depth is None else "%g" % depth)
        self.distance.setObjectName("SciForgeBreakoutDistance")
        self.distance.setToolTip("How deep the cut goes from the front of the parts")
        self.default_button = QtWidgets.QPushButton("Default")
        self.default_button.setObjectName("SciForgeBreakoutDefault")
        self.default_button.setToolTip("Half the depth of the parts the view shows")
        row = QtWidgets.QHBoxLayout()
        row.addWidget(self.distance, 1)
        row.addWidget(self.default_button)
        self.layout.addRow("Depth (mm)", row)
        self.distance.editingFinished.connect(self._depth)
        self.default_button.clicked.connect(self._default)
        if self.closed:
            self.remove_button = QtWidgets.QPushButton("Remove Breakout")
            self.remove_button.setObjectName("SciForgeBreakoutRemove")
            self.remove_button.clicked.connect(self._remove)
            self.layout.addRow("", self.remove_button)
        self.finish_layout()
        if self.closed:
            self.say("Change the depth, then OK.")
        else:
            self.say("Click the view to break out.")

    def _value(self):
        try:
            return float(self.distance.text().replace(",", "."))
        except ValueError:
            return -1.0

    def _default(self):
        if self._closed or self.view is None:
            return
        self.distance.setText("%g" % drawing_breakout.default_depth(self.view))
        self._depth()

    def _depth(self, *_args):
        if self._closed or not self.closed or self.view is None:
            return
        try:
            drawing_breakout.set_depth(self.view, self._value())
            self.message.setText("")
        except drawing.DrawingError as exc:
            self.message.setText(str(exc))
            return
        self.schedule()

    # -- the clicks ------------------------------------------------------------------------
    def on_press(self, point, event):
        if self.closed:
            return True
        if self.view is None:
            view = view_at(self.page, point, (drawing.PART_VIEW, drawing.ITEM))
            if view is None:
                self.message.setText("Click a base or projected view.")
                return True
            if drawing_breakout.has_breakout(view):
                self.message.setText(
                    "This view has a breakout already: double-click it to change it."
                )
                return True
            if drawing.is_isometric(view):
                self.message.setText("A breakout needs a front, top or side view.")
                return True
            self.view = view
            self.message.setText("")
            self.distance.setText("%g" % drawing_breakout.default_depth(view))
            self.say("Click the points of a boundary around what should show inside.")
            return True
        local = drawing.page_to_local(self.view, point)
        if len(self.points) >= 3 and self._near_first(point):
            return self._close_boundary()
        self.points.append(local)
        self._draw(None)
        if len(self.points) >= 3:
            self.say("Click more points, or the first point again (or Enter) to close it.")
        return True

    def _near_first(self, point):
        first = drawing.local_to_page(self.view, self.points[0])
        tol = CLOSE_PIXELS * drawing_ui.mm_per_pixel(self.gv, self.page) if self.gv else 2.0
        return math.hypot(point[0] - first[0], point[1] - first[1]) <= tol

    def _close_boundary(self):
        if self._closed or self.closed:
            return True
        if len(self.points) < 3:
            self.message.setText("Click at least three points around the area.")
            return True
        value = self._value()
        if value <= 0:
            self.message.setText("Type how deep the breakout goes (more than 0 mm).")
            return True
        try:
            drawing_breakout.add_breakout(self.view, self.points, value)
        except drawing.DrawingError as exc:
            self.message.setText(str(exc))
            return True
        self.closed = True
        self.clear_overlay()
        self.say("Change the depth, then OK.")
        self.schedule()
        return True

    def _draw(self, mouse):
        self.clear_overlay()
        pts = [drawing.local_to_page(self.view, p) for p in self.points]
        if mouse is not None:
            pts.append(mouse)
        for a, b in zip(pts, pts[1:]):
            self.overlay_line(a, b, dashed=False)

    def on_move(self, point, event):
        if self._closed or self.closed or self.view is None or not self.points:
            return
        self._draw(point)

    def on_key(self, key, event):
        if key in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter) and not self.closed:
            if self.view is not None and self.points:
                drawing_ui._later(self._close_boundary)
            return True
        return super().on_key(key, event)

    def _remove(self):
        """The view shows its whole parts again (OK keeps it, Cancel brings it back)."""
        if self._closed or self.view is None:
            return
        try:
            drawing_breakout.remove_breakout(self.view)
        except Exception as exc:
            self.message.setText(str(exc))
            return
        self.doc.recompute()
        drawing_ui._later(self.accept)

    def accept(self):
        if not self.closed:
            self.message.setText("Click the view and a closed boundary first.")
            return False
        return super().accept()


def edit_at(page, point):
    """Double-click inside a breakout's boundary: its dialog (depth, Remove). True when
    the click was there."""
    view = view_at(page, point, (drawing.PART_VIEW, drawing.ITEM))
    if view is None or not drawing_breakout.has_breakout(view):
        return False
    local = drawing.page_to_local(view, point)
    if not drawing_breakout.inside(drawing_breakout.breakout_of(view)["points"], local):
        return False

    def start():
        if commands.finish_open_dialog():
            BreakoutPanel(page, view).show()

    drawing_ui._later(start)
    return True


class BreakoutCommand(drawing_ui._Base):
    title = "Breakout Section View"
    tip = "Take material away inside a boundary on a view, to show what lies inside"
    icon = "dw_section_view"

    def run(self):
        drawing_ui._start(BreakoutPanel)


COMMANDS = {"SciForge_DrawingBreakoutView": BreakoutCommand}
