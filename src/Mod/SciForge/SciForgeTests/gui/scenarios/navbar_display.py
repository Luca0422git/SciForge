# SPDX-License-Identifier: LGPL-2.1-or-later
"""Navigation bar > Display Settings with real clicks on its drop-down: the six Visual
Styles (the default ticked; Shaded: no edge lines; Wireframe: no faces; the two hidden-line
styles: faces in the background colour, the edges behind dashed with Hidden Edges; Shaded
with Hidden Edges), Environment (Photo Booth: a light background; Theme again), Effects
(Ground Shadow and Ground Plane, moved down with the Ground Plane Offset slider), Object
Visibility (Sketches off: the sketch is neither drawn nor clickable; on again; Show All),
Camera (Perspective, Orthographic, Perspective with Ortho Faces: perspective in the
isometric view, orthographic after a click on the ViewCube's TOP; the same choice ticked in
the ViewCube's menu), and the choices remembered in the preferences.

The part: the 40 x 30 x 10 box, and a sketch circle r = 5 at (60, 15) on XY left shown."""

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets

from SciForgeTests.gui import analysis_steps as a
from SciForgeTests.gui import blend_steps as b
from SciForgeTests.gui import harness as h
from SciForgeTests.gui import nav_input as n
from SciForgeTests.gui import viewcube_input as vc

V = App.Vector
st = {}
CIRCLE = V(65, 15, 0)  # on the sketch circle
DS = "Display Settings"


def display():
    from sciforge import display_ui

    return display_ui


# -- a sketch left shown -------------------------------------------------------------------------
def sketch():
    h.click_empty()
    h.fit()
    h.ribbon("Create Sketch")


def plane():
    h.click(V(12, -8, 0))


def circle():
    sk = h.in_sketch()
    h.check("a sketch on XY", sk is not None)
    if sk is not None:
        h.draw_circle(sk, 60, 15, 5)
        st["sketch"] = sk.Name


def finish():
    h.ribbon("Finish Sketch")


def ready():
    sk = App.ActiveDocument.getObject(st.get("sketch", ""))
    h.check("the sketch is shown", sk is not None and sk.ViewObject.Visibility)
    h.fit()


# -- visual styles ---------------------------------------------------------------------------
def default_style():
    state = n.entry_state(DS, "Shaded with Visible Edges Only")
    h.check(
        "Shaded with Visible Edges Only is ticked (Fusion's default)", state == (True, True), state
    )
    st["base"] = a.colors()
    h.check("the faces are drawn", a.share(st["base"], "grey") > 0.4, st["base"])
    h.check("edge lines are drawn", st["base"].get("black", 0) > 20, st["base"])
    n.choose(DS, "Shaded")


def shaded():
    counts = a.colors()
    h.check("Shaded: remembered", display().get("VisualStyle") == "Shaded")
    h.check("Shaded ticked", n.entry_state(DS, "Shaded") == (True, True))
    h.check(
        "Shaded: no edge lines",
        counts.get("black", 0) < st["base"].get("black", 0) * 0.3,
        (counts, st["base"]),
    )
    h.check("Shaded: the faces still drawn", a.share(counts, "grey") > 0.4, counts)
    h.shot("1-shaded")
    n.choose(DS, "Wireframe")


def wireframe():
    counts = a.colors()
    h.check(
        "Wireframe: no faces (the background shows through)",
        a.share(counts, "background") > 0.8,
        counts,
    )
    h.check("Wireframe: the lines", counts.get("black", 0) > 20, counts)
    st["wire"] = counts
    h.shot("2-wireframe")
    n.choose(DS, "Wireframe with Visible Edges Only")


def visible_only():
    counts = a.colors()
    h.check(
        "hidden-line: faces in the background colour", a.share(counts, "background") > 0.8, counts
    )
    h.check("the model's own faces are switched off", not a.model_faces_shown())
    h.check(
        "fewer lines than Wireframe (the hidden ones are gone)",
        counts.get("black", 0) < st["wire"].get("black", 0),
        (counts, st["wire"]),
    )
    st["visible"] = counts
    h.shot("3-visible-edges")
    n.choose(DS, "Wireframe with Hidden Edges")


def hidden_dashed():
    counts = a.colors()
    light = counts.get("grey", 0) + counts.get("white", 0)
    before = st["visible"].get("grey", 0) + st["visible"].get("white", 0)
    h.check(
        "the hidden edges are drawn (light dashes)", light > before + 10, (counts, st["visible"])
    )
    h.shot("4-hidden-edges")
    n.choose(DS, "Shaded with Hidden Edges")


def shaded_hidden():
    counts = a.colors()
    h.check("Shaded with Hidden Edges: faces drawn", a.share(counts, "grey") > 0.4, counts)
    h.check("the model's own faces are back", a.model_faces_shown())
    node = display()._STATE["nodes"].get(App.ActiveDocument.Name)
    h.check("the hidden edges are drawn over them", node is not None)
    n.choose(DS, "Shaded with Visible Edges Only")


def back_default():
    h.check("back to the default", display().get("VisualStyle") == "Shaded with Visible Edges Only")
    h.check("nothing extra drawn", App.ActiveDocument.Name not in display()._STATE["nodes"])
    n.choose(DS, "Photo Booth")


# -- environment ------------------------------------------------------------------------------
def corner_pixel():
    gl = h.gl_widget()
    g = gl.mapToGlobal(QtCore.QPoint(30, 30))
    image = QtWidgets.QApplication.primaryScreen().grabWindow(0).toImage()
    c = image.pixelColor(g.x(), g.y())
    return c.red(), c.green(), c.blue()


def photo_booth():
    c = corner_pixel()
    h.check("Photo Booth: a light background", min(c) > 170, c)
    h.check("Photo Booth ticked", n.entry_state(DS, "Photo Booth") == (True, True))
    h.shot("5-photo-booth")
    n.choose(DS, "Theme")


def theme():
    c = corner_pixel()
    h.check("Theme: SciForge's dark background again", c == (42, 42, 42), c)
    n.choose(DS, "Ground Shadow")


# -- effects -------------------------------------------------------------------------------------
def shadow_on():
    h.check("Ground Shadow ticked", n.entry_state(DS, "Ground Shadow") == (True, True))
    h.check("Ground Shadow remembered", display().get("GroundShadow"))
    n.choose(DS, "Ground Plane Offset")


def offset_popup():
    popup = Gui.getMainWindow().findChild(QtWidgets.QFrame, "SciForgeGroundOffset")
    h.check("the Ground Plane Offset slider opens", popup is not None and popup.isVisible())
    if popup is not None:
        a.slide(popup.slider, 60)
        popup.close()


def shadow_low():
    h.fit()
    h.check("offset 60 %", display().get("GroundOffset") == 60)
    owners = display()._owners(App.ActiveDocument)
    z = display().ground_z(owners)
    st["ground"] = z
    h.check("the ground lies below the part", z < -10, z)
    h.check(
        "the shadow is dark under the part",
        sum(a.color_at(V(38, 2, z))) < 3 * 42,  # a corner of it the part does not hide
        a.color_at(V(38, 2, z)),
    )
    h.shot("6-shadow")
    n.choose(DS, "Ground Plane")


def plane_on():
    c = a.color_at(V(46, 15, st["ground"]))
    h.check("Ground Plane: a light floor round the shadow", sum(c) > 3 * 60, c)
    n.choose(DS, "Ground Plane")


def plane_off():
    n.choose(DS, "Ground Shadow")


def effects_off():
    h.check(
        "both effects off", not display().get("GroundShadow") and not display().get("GroundPlane")
    )
    c = a.color_at(V(38, 2, st["ground"]))
    h.check("the background under the part again", c == (42, 42, 42), c)
    st["circle"] = a.color_at(CIRCLE)
    n.choose(DS, "Sketches")


# -- object visibility -------------------------------------------------------------------------
def sketches_off():
    h.check("Sketches unticked", n.entry_state(DS, "Sketches") == (True, False))
    key = (App.ActiveDocument.Name, st.get("sketch", ""))
    h.check("the sketch is hidden in the display", key in display()._STATE["hides"])
    sk = App.ActiveDocument.getObject(st.get("sketch", ""))
    h.check("its eye is untouched", sk is not None and sk.ViewObject.Visibility)
    info = h.view().getObjectInfo(tuple(h.view().getPointOnViewport(CIRCLE)))
    h.check("it cannot be clicked", not info or info.get("Object") != st.get("sketch"), info)
    n.choose(DS, "Sketches")


def sketches_on():
    key = (App.ActiveDocument.Name, st.get("sketch", ""))
    h.check("Sketches shown again", key not in display()._STATE["hides"])
    n.choose(DS, "Show All")


def all_hidden():
    h.check(
        "Show All unticked: every kind hidden",
        set(display()._STATE["hidden"]) == set(display().KINDS),
    )
    n.choose(DS, "Show All")


def all_shown():
    h.check("Show All again: nothing hidden", not display()._STATE["hidden"])
    n.choose(DS, "Perspective")


# -- camera ----------------------------------------------------------------------------------------
def perspective():
    h.check("Perspective camera", h.view().getCameraType() == "Perspective")
    n.choose(DS, "Orthographic")


def orthographic():
    h.check("Orthographic camera", h.view().getCameraType() == "Orthographic")
    n.choose(DS, "Perspective with Ortho Faces")


def ortho_faces_iso():
    h.check(
        "Perspective with Ortho Faces: perspective in the isometric view",
        h.view().getCameraType() == "Perspective",
    )
    vc.click("top")


ortho_faces_iso.wait_ms = 1500


def ortho_faces_top():
    h.check("looking at TOP: orthographic", h.view().getCameraType() == "Orthographic")
    menu = vc.menu_texts(on="top")
    texts = [t for t, _enabled in menu.get("texts", [])]
    h.check(
        "the ViewCube's menu offers the same three", "Perspective with Ortho Faces" in texts, menu
    )
    h.check(
        "and ticks the same choice", menu.get("checked") == ["Perspective with Ortho Faces"], menu
    )
    vc.click("turn-down")


ortho_faces_top.wait_ms = 1500


def remembered():
    group = App.ParamGet("User parameter:BaseApp/Preferences/Mod/SciForge/Display")
    h.check(
        "the camera choice is remembered",
        group.GetString("Camera") == "Perspective with Ortho Faces",
    )
    from sciforge import nav_core

    face = nav_core.wants_ortho(h.view().getViewDirection())
    h.check(
        "turned 90 degrees to the next face: orthographic",
        face and h.view().getCameraType() == "Orthographic",
        h.view().getViewDirection(),
    )
    n.choose(DS, "Orthographic")


h.run(
    "navbar_display",
    b.box_steps("Display")
    + [
        sketch,
        plane,
        circle,
        finish,
        ready,
        default_style,
        shaded,
        wireframe,
        visible_only,
        hidden_dashed,
        shaded_hidden,
        back_default,
        photo_booth,
        theme,
        shadow_on,
        offset_popup,
        shadow_low,
        plane_on,
        plane_off,
        effects_off,
        sketches_off,
        sketches_on,
        all_hidden,
        all_shown,
        perspective,
        orthographic,
        ortho_faces_iso,
        ortho_faces_top,
        remembered,
    ],
)
