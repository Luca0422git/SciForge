# SPDX-License-Identifier: LGPL-2.1-or-later
"""Linked designs by relative path (docs/sciforge/parity/versions.md).

A project folder with Wheel.FCStd (a box of 1000, closed). A new design Cart.
Path 1, Insert Design on an unsaved design asks to save it first (the link is stored
  relative to the design's file); after the save the insert goes on by itself: Cart holds a
  link to Wheel's body, volume 1000.
Path 2, Cart saved (v2): the file stores the link as the relative path "Wheel.FCStd".
Path 3, the whole project folder is moved elsewhere (a NAS folder moved as a whole): Cart
  opened from the new place finds Wheel again, no error in the report view.
Path 4, Wheel edited and saved (box of 8000): Cart reopened shows the new wheel.
Path 5, Wheel taken away: opening Cart says in plain words that the linked design was not
  found.
"""

import os
import shutil
import tempfile
import zipfile

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import versions_input as vi

s = {}
PREFS = "User parameter:BaseApp/Preferences/Mod/SciForge/Files"


def make_box(document, name, length, width, height):
    body = document.addObject("PartDesign::Body", name)
    box = document.addObject("PartDesign::AdditiveBox", name + "Box")
    body.addObject(box)
    box.Length, box.Width, box.Height = length, width, height
    document.recompute()
    Gui.getDocument(document.Name).ActiveView.setActiveObject("pdbody", body)
    return body


def near(a, b, tol=1e-3):
    return a is not None and abs(a - b) < tol


def links(document):
    return [o for o in document.Objects if o.TypeId == "App::Link"]


def link_volume(document):
    return sum(o.Shape.Volume for o in links(document) if not o.Shape.isNull())


def xlink_file(path):
    """The file path of the first link to another design in the file (empty XLink
    entries of ordinary properties are skipped)."""
    import re

    with zipfile.ZipFile(path) as zf:
        xml = zf.read("Document.xml").decode("utf-8", "replace")
    for match in re.finditer(r'<XLink file="([^"]*)"', xml):
        if match.group(1):
            return match.group(1)
    return None


def setup():
    Gui.activateWorkbench("SciForgeWorkbench")
    s["project"] = tempfile.mkdtemp(prefix="sciforge-project-")
    App.ParamGet(PREFS).SetString("ProjectFolder", s["project"])
    App.ParamGet(PREFS).SetBool("AskDescription", True)
    wheel = App.newDocument("Wheel")
    make_box(wheel, "Body", 10, 10, 10)
    h.fit()
    s["wheel"] = os.path.join(s["project"], "Wheel.FCStd")
    wheel.saveAs(s["wheel"])
    Gui.getDocument("Wheel").Modified = False
    App.closeDocument("Wheel")
    cart = App.newDocument("Cart")
    make_box(cart, "Frame", 40, 20, 2)
    h.fit()
    h.check(
        "Wheel saved and closed; Cart is new and unsaved",
        os.path.isfile(s["wheel"]) and not cart.FileName,
    )


# -- Path 1: insert into an unsaved design ----
def p1_insert():
    from sciforge import versions_ui

    versions_ui.insert_design(s["wheel"])


def p1_save_first():
    d = vi.save_dialog()
    h.check("P1 an unsaved design is asked to be saved first", d is not None, h.popups())
    vi.fill_save_dialog(name="Cart")
    vi.click_save()


p1_save_first.wait_ms = 2000


def p1_inserted():
    cart = App.getDocument("Cart")
    s["cart"] = os.path.join(s["project"], "Cart.FCStd")
    h.check("P1 Cart saved", os.path.isfile(s["cart"]))
    h.check(
        "P1 the insert went on by itself: one link",
        len(links(cart)) == 1,
        [o.Label for o in cart.Objects],
    )
    h.check(
        "P1 the link shows Wheel's box (1000)", near(link_volume(cart), 1000.0), link_volume(cart)
    )
    h.check(
        "P1 the link is named after the design",
        links(cart) and links(cart)[0].Label == "Wheel: Body",
        links(cart) and links(cart)[0].Label,
    )
    h.check("P1 Wheel is open hidden (no tab of its own)", "Wheel" in App.listDocuments())
    h.check("P1 Cart shows as changed", Gui.getDocument("Cart").Modified)
    h.shot("1-inserted")
    h.press(QtCore.Qt.Key_S, QtCore.Qt.ControlModifier)


# -- Path 2: the relative path in the file ----
def p2_describe():
    h.check("P2 the version dialog", vi.describe_and_save("with wheel"))


def p2_saved():
    h.check("P2 Cart shows as saved", not Gui.getDocument("Cart").Modified)
    h.check(
        "P2 the file stores the link by the relative path Wheel.FCStd",
        xlink_file(s["cart"]) == "Wheel.FCStd",
        xlink_file(s["cart"]),
    )
    from sciforge import versions, versions_ui

    h.check(
        "P2 Cart is v2", [v.number for v in versions_ui.store_of(s["cart"]).versions()] == [1, 2]
    )
    h.check(
        "P2 the core's relative path agrees",
        versions.relative_path(s["cart"], s["wheel"]) == "Wheel.FCStd",
    )
    for name in list(App.listDocuments()):
        Gui.getDocument(name).Modified = False
        App.closeDocument(name)


# -- Path 3: the project folder moves as a whole ----
def p3_move():
    s["moved"] = os.path.join(tempfile.mkdtemp(prefix="sciforge-nas-"), "Designs")
    shutil.move(s["project"], s["moved"])
    App.ParamGet(PREFS).SetString("ProjectFolder", s["moved"])
    s["cart2"] = os.path.join(s["moved"], "Cart.FCStd")
    s["wheel2"] = os.path.join(s["moved"], "Wheel.FCStd")
    h.check("P3 the folder moved", os.path.isfile(s["cart2"]) and not os.path.exists(s["project"]))
    App.openDocument(s["cart2"])


p3_move.wait_ms = 2000


def p3_resolved():
    cart = App.getDocument("Cart")
    h.check("P3 Cart opened from the new place", cart is not None)
    h.check(
        "P3 the link found Wheel again (1000)",
        cart is not None and near(link_volume(cart), 1000.0),
        cart and link_volume(cart),
    )
    linked = links(cart)[0].LinkedObject if cart and links(cart) else None
    h.check(
        "P3 from the moved folder",
        linked is not None
        and os.path.normcase(linked.Document.FileName) == os.path.normcase(s["wheel2"]),
        linked and linked.Document.FileName,
    )
    h.fit()
    h.shot("3-moved")
    for name in list(App.listDocuments()):
        Gui.getDocument(name).Modified = False
        App.closeDocument(name)


# -- Path 4: the linked design changes ----
def p4_edit_wheel():
    wheel = App.openDocument(s["wheel2"])
    wheel.getObject("Body").Group[0].Height = 80
    wheel.recompute()
    wheel.save()
    Gui.getDocument(wheel.Name).Modified = False
    App.closeDocument(wheel.Name)
    App.openDocument(s["cart2"])


p4_edit_wheel.wait_ms = 2000


def p4_follows():
    cart = App.getDocument("Cart")
    h.check(
        "P4 Cart shows the new wheel (8000)",
        cart is not None and near(link_volume(cart), 8000.0),
        cart and link_volume(cart),
    )
    for name in list(App.listDocuments()):
        Gui.getDocument(name).Modified = False
        App.closeDocument(name)


# -- Path 5: the linked design is missing ----
def p5_remove_wheel():
    os.rename(s["wheel2"], s["wheel2"] + ".away")
    from sciforge import commands

    s["told"] = commands._TOLD["msg"]
    App.openDocument(s["cart2"])


p5_remove_wheel.wait_ms = 2500
p5_remove_wheel.known = True  # FreeCAD prints its own 'file does not exist' error lines here


def p5_message():
    from sciforge import commands

    cart = App.getDocument("Cart")
    h.check("P5 Cart still opens", cart is not None)
    h.check(
        "P5 the link is broken",
        cart is not None and links(cart) and links(cart)[0].LinkedObject is None,
    )
    msg = commands._TOLD["msg"] or ""
    h.check(
        "P5 SciForge says the linked design was not found",
        "not found" in msg and "Wheel" in msg,
        msg,
    )
    h.new_errors()  # FreeCAD's own lines about the missing file are expected here


def cleanup():
    for name in list(App.listDocuments()):
        Gui.getDocument(name).Modified = False
        App.closeDocument(name)
    App.ParamGet(PREFS).RemString("ProjectFolder")
    shutil.rmtree(os.path.dirname(s["moved"]), ignore_errors=True)
    h.new_errors()


h.run(
    "versions_link",
    [
        setup,
        p1_insert,
        p1_save_first,
        p1_inserted,
        p2_describe,
        p2_saved,
        p3_move,
        p3_resolved,
        p4_edit_wheel,
        p4_follows,
        p5_remove_wheel,
        p5_message,
        cleanup,
    ],
)
