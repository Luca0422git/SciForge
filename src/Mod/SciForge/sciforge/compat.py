"""Qt compatibility. FreeCAD ships a `PySide` shim that maps to whichever Qt
binding it was built with (PySide6 in the 1.x series)."""

from PySide import QtCore, QtGui, QtWidgets  # noqa: F401

Signal = QtCore.Signal
