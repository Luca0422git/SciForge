# SPDX-License-Identifier: LGPL-2.1-or-later
"""The version shows quietly (brief beta-release.md, R0): a small grey "SciForge 0.1.0-beta.2" after
Home's heading, in Diagnostics' first line and in the AI connector's manifest; no banner and
no change to the window title. What the user sees is checked on the screen, not only the text.
"""

import os

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtWidgets

import sciforge
from SciForgeTests.gui import harness as h

# The one place the version is written (src/Mod/SciForge/VERSION): what must show
with open(os.path.join(os.path.dirname(sciforge.ROOT), "VERSION"), encoding="utf-8") as _file:
    VERSION = _file.readline().strip()


def home():
    from sciforge import home_ui

    return home_ui.view()


def label_on_home():
    page = home()
    h.check("the Home tab is open", page is not None)
    label = getattr(page, "version_label", None)
    h.check("Home has a version label", label is not None)
    if label is None:
        return
    h.check("... it says SciForge " + VERSION, label.text() == "SciForge " + VERSION, label.text())
    h.check("... it is on screen", label.isVisible() and label.width() > 0)
    heading = page.findChild(QtWidgets.QLabel, "SciForgeHomeHeading")
    h.check("... right of the heading", heading is not None and label.x() > heading.x())
    h.check("... smaller than the heading", label.font().pixelSize() <= 13, label.font().pixelSize())
    # the colour on the screen (a grab of the real screen: QWidget.grab paints without the
    # window's style sheets), the label's text dimmer than the heading's
    image = QtWidgets.QApplication.primaryScreen().grabWindow(0).toImage()

    def brightest(widget):
        top = widget.mapToGlobal(widget.rect().topLeft())
        spots = (
            image.pixelColor(top.x() + x, top.y() + y).lightness()
            for x in range(widget.width())
            for y in range(widget.height())
        )
        return max(spots)

    ink, heading_ink = brightest(label), brightest(heading)
    h.check("... the text is lit, not invisible", ink > 120, ink)
    h.check("... dimmer than the heading", ink < heading_ink, (ink, heading_ink))
    h.shot("home_version")


def title_bar_untouched():
    title = Gui.getMainWindow().windowTitle()
    h.check("the window title carries no version or beta text", "beta" not in title.lower(), title)


def diagnostics_and_manifest():
    import sciforge
    from sciforge import diagnostics

    h.check("sciforge.__version__ is " + VERSION, sciforge.__version__ == VERSION)
    first = diagnostics.report().splitlines()[0]
    h.check("Diagnostics starts with the version", first.startswith("SciForge " + VERSION), first)


h.run("version_label", [label_on_home, title_bar_untouched, diagnostics_and_manifest])
