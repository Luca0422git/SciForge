# SPDX-License-Identifier: LGPL-2.1-or-later
"""The Data Panel's Move / Copy and the Out-of-Date button, like Fusion
(docs/sciforge/parity/versions.md).

A project folder (git) with Wheel.FCStd (a 10 mm cube, saved twice: v1, v2), the folders
Parts and Old, and Cart.FCStd, which inserts Wheel (a link by a relative path).

P1 Data Panel, right-click Wheel > Move...: the folders of the project are listed; Parts,
   Move: Wheel is in Parts with its two versions (v2 in the history, the badge "v2"), and
   Cart now points at Parts/Wheel.FCStd. Moving it again into Parts is refused with words.
P2 Right-click Wheel > Copy... > Old, Copy: Old/Wheel.FCStd is a separate design, v1
   ("Copy of Wheel v2"); the original keeps its v2; a second copy is "Wheel 2".
P3 Move while Cart is open: refused ("Close Cart first"), nothing moved.
P4 Out of date: Cart is open (its Wheel link shows the 1000 cube); another computer saves
   Wheel again (a 20 mm cube written over Parts/Wheel.FCStd): the application bar shows the
   Out-of-Date button; its menu says what is newer; Get Latest reads Wheel again: the link
   shows the 8000 cube, the button goes.
P5 An older version open (Gear v1 of a design saved twice) shows the button too; its menu
   offers Open the Newest Version, which opens the design itself.
"""

import os
import shutil
import tempfile
import time

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import polish2_steps as p2
from SciForgeTests.gui import versions_input as vi
from SciForgeTests.gui import widget_input as wi

s = {}


def ui():
    from sciforge import versions_ui

    return versions_ui


def versions(path):
    return ui().store_of(path).versions()


def button():
    return p2.child(Gui.getMainWindow(), "SciForgeOutOfDate")


def setup():
    Gui.activateWorkbench("SciForgeWorkbench")
    s["project"] = tempfile.mkdtemp(prefix="sciforge-project-")
    p2.set_project(s["project"])
    for folder in ("Parts", "Old"):
        os.makedirs(os.path.join(s["project"], folder))
    wheel = App.newDocument("Wheel")
    body = p2.make_box(wheel, "Body", 10, 10, 10)
    s["wheel"] = os.path.join(s["project"], "Wheel.FCStd")
    p2.save_new(wheel, s["wheel"])
    p2.process()
    body.Group[0].Length = 10.0001
    wheel.recompute()
    body.Group[0].Length = 10
    wheel.recompute()
    wheel.save()
    p2.process()
    App.closeDocument(wheel.Name)
    # another computer's newer Wheel (a 20 mm cube), kept aside for P4
    big = App.newDocument("WheelBig")
    p2.make_box(big, "Body", 20, 20, 20)
    s["big"] = os.path.join(tempfile.mkdtemp(prefix="sciforge-other-"), "Wheel.FCStd")
    time.sleep(1.1)  # its saved date differs from Wheel's (FreeCAD keeps whole seconds)
    big.saveAs(s["big"])
    App.closeDocument(big.Name)
    cart = App.newDocument("Cart")
    p2.make_box(cart, "Frame", 40, 20, 2)
    s["cart"] = os.path.join(s["project"], "Cart.FCStd")
    p2.save_new(cart, s["cart"])
    ui().insert_design(s["wheel"])
    cart.save()
    p2.process()
    for name in list(App.listDocuments()):
        App.closeDocument(name)
    h.check(
        "set-up: Wheel has v1, v2",
        [v.number for v in versions(s["wheel"])] == [1, 2],
        versions(s["wheel"]),
    )
    h.check("set-up: Cart links Wheel.FCStd", 'file="Wheel.FCStd"' in xml(s["cart"]))


def xml(path):
    from sciforge import versions

    return versions.read_design_xml(path)


# -- P1: Move ----
def p1_panel():
    Gui.runCommand("SciForge_DataPanel")


def p1_menu():
    ok = p2.panel_menu("Wheel", "Move...")
    h.check("P1 right-click Wheel > Move...", ok)


def p1_dialog():
    d = p2.dialog("SciForgeMoveCopyDialog")
    h.check("P1 the Move dialog", d is not None, vi.popups_except(()))
    if d is None:
        return
    folders = p2.child(d, "SciForgeMoveCopyFolders")
    labels = [folders.item(i).text() for i in range(folders.count())]
    h.check(
        "P1 it lists the project's folders",
        labels[:1] == ["Project  (here now)"]
        and "Project / Old" in labels
        and "Project / Parts" in labels,
        labels,
    )
    h.shot("P1-move-dialog")
    d.choose(os.path.join(s["project"], "Parts"))
    wi.click(p2.child(d, "SciForgeMoveCopyOk"))


def p1_moved():
    s["moved"] = os.path.join(s["project"], "Parts", "Wheel.FCStd")
    h.check("P1 Wheel is in Parts", os.path.isfile(s["moved"]) and not os.path.exists(s["wheel"]))
    listed = versions(s["moved"])
    h.check("P1 its versions came along", [v.number for v in listed] == [1, 2], listed)
    h.check("P1 Cart points at Parts/Wheel.FCStd", 'file="Parts/Wheel.FCStd"' in xml(s["cart"]))
    _l, item = p2.panel_item("Wheel")
    h.check("P1 Wheel's card left the project's top folder", item is None)
    ui().panel().set_folder(os.path.join(s["project"], "Parts"))
    _l, item = p2.panel_item("Wheel")
    h.check(
        "P1 its card in Parts shows v2",
        item is not None and item.text().endswith("v2"),
        item.text() if item else None,
    )
    s["refused"] = ui().move_design(s["moved"], os.path.join(s["project"], "Parts"))


def p1_refused():
    h.check("P1 moving it where it is: refused", s["refused"] is None)
    h.check("P1 nothing changed", os.path.isfile(s["moved"]))


# -- P2: Copy ----
def p2_menu():
    ok = p2.panel_menu("Wheel", "Copy...")
    h.check("P2 right-click Wheel > Copy...", ok)


def p2_dialog():
    d = p2.dialog("SciForgeMoveCopyDialog")
    h.check("P2 the Copy dialog", d is not None)
    if d is None:
        return
    d.choose(os.path.join(s["project"], "Old"))
    wi.click(p2.child(d, "SciForgeMoveCopyOk"))


def p2_copied():
    copy = os.path.join(s["project"], "Old", "Wheel.FCStd")
    h.check("P2 Old/Wheel.FCStd made", os.path.isfile(copy))
    listed = versions(copy) if os.path.isfile(copy) else []
    h.check("P2 a separate design: v1", [v.number for v in listed] == [1], listed)
    h.check(
        "P2 described as a copy", listed and listed[0].description == "Copy of Wheel v2", listed
    )
    h.check("P2 the original keeps v1, v2", [v.number for v in versions(s["moved"])] == [1, 2])
    again = ui().copy_design(s["moved"], os.path.join(s["project"], "Old"))
    h.check(
        "P2 a second copy is Wheel 2", again and os.path.basename(again) == "Wheel 2.FCStd", again
    )


# -- P3: Move while a design that uses it is open ----
def p3_open_cart():
    ui().open_design(s["cart"])


def p3_refused():
    cart = p2.doc_named("Cart")
    h.check("P3 Cart open", cart is not None)
    h.check(
        "P3 Cart shows the Wheel link (1000)",
        cart and p2.near(p2.link_volume(cart), 1000.0),
        cart and p2.link_volume(cart),
    )
    moved = ui().move_design(s["moved"], s["project"])
    h.check("P3 Move refused while Cart is open", moved is None and os.path.isfile(s["moved"]))
    from sciforge import commands

    said = commands._TOLD.get("msg") or ""
    h.check(
        "P3 it says to close Cart (Wheel is only read for Cart's link)",
        "Close Cart first" in said,
        said,
    )


# -- P4: out of date, Get Latest ----
def p4_other_computer():
    h.check("P4 no Out-of-Date button yet", not button().isVisible())
    shutil.copyfile(s["big"], s["moved"])  # Wheel saved again elsewhere (the NAS)


p4_other_computer.wait_ms = 2600  # the application bar looks every 2 s


def p4_shown():
    b = button()
    h.check("P4 the Out-of-Date button shows", b is not None and b.isVisible())
    h.check("P4 it says what is newer", "Wheel was saved again" in b.toolTip(), b.toolTip())
    h.shot("P4-out-of-date")
    result = p2.click_menu_entry(b, "Get Latest")
    h.check("P4 its menu has Get Latest", result["ok"], result.get("texts"))


def p4_latest():
    cart = p2.doc_named("Cart")
    h.check(
        "P4 the link shows the newer 8000 cube",
        p2.near(p2.link_volume(cart), 8000.0),
        p2.link_volume(cart),
    )
    h.check("P4 nothing is out of date now", not ui().out_of_date(cart), ui().out_of_date(cart))


p4_latest.wait_ms = 2600


def p4_hidden():
    h.check("P4 the button went", not button().isVisible())
    for name in list(App.listDocuments()):  # Cart, and the Wheel it loaded (hidden)
        App.closeDocument(name)


# -- P5: an older version open ----
def p5_open_older():
    info = versions(s["moved"])[0]
    s["older"] = ui().open_version(s["moved"], info)


p5_open_older.wait_ms = 2600


def p5_button():
    b = button()
    h.check("P5 an older version shows the button", b.isVisible(), b.toolTip())
    h.check("P5 it says so", "v1 of Wheel" in b.toolTip(), b.toolTip())
    result = p2.click_menu_entry(b, "Open the Newest Version")
    h.check("P5 Open the Newest Version", result["ok"], result.get("texts"))


def p5_newest():
    newest = ui().doc_for_file(s["moved"])
    h.check("P5 the design itself opened", newest is not None, list(App.listDocuments()))
    if newest is not None:
        h.check("P5 with the newest cube", p2.near(p2.volume(newest), 8000.0), p2.volume(newest))
    ui().hide_panel()


STEPS = [
    setup,
    p1_panel,
    p1_menu,
    p1_dialog,
    p1_moved,
    p1_refused,
    p2_menu,
    p2_dialog,
    p2_copied,
    p3_open_cart,
    p3_refused,
    p4_other_computer,
    p4_shown,
    p4_latest,
    p4_hidden,
    p5_open_older,
    p5_button,
    p5_newest,
]

h.run("polish2_data_panel", STEPS)
