# SPDX-License-Identifier: LGPL-2.1-or-later
"""Saves FreeCAD could not finish (Luca, 2026-10-19: in his Documents folder, backed up by
Google Drive, every save stayed "test.FCStd.78026b5d-..." and Home showed no design).
FreeCAD writes a save to "<design>.FCStd.<uuid>" and renames it last; Windows refused the
rename while Google Drive held the new file. A refused rename cannot be made here, so the
file it leaves is made by hand.

Path 1, such files left in This computer's folder (three saves of one design, one of
  another): Home makes the newest of each the design and lists them; the older ones are
  kept in .sciforge/unfinished-saves.
Path 2, a save of an open design left that way: SciForge finishes it (the rename), tells
  the listeners FreeCAD did not: Home lists it first in Recent.
"""

import os
import shutil
import tempfile
import time

import FreeCAD as App

from SciForgeTests.gui import harness as h

s = {}
FILES = "User parameter:BaseApp/Preferences/Mod/SciForge/Files"
UUIDS = (
    "78026b5d-cb38-45d0-a35f-496a00000001",
    "de505953-325f-48bb-888d-ba0000000002",
    "e6be27c2-5cd8-4564-9deb-abf000000003",
    "4f39d0fd-dfb7-492f-a4aa-000000000004",
)


def home():
    from sciforge import home_ui

    return home_ui.view()


def names(row):
    page = home()
    return [t.split("\n")[0] for _k, _key, _p, t, _s in page.items(row)] if page else []


def a_save(name):
    """A complete design file, as FreeCAD writes it."""
    from sciforge import commands

    doc = App.newDocument(name)
    commands.ensure_body()
    box = doc.addObject("PartDesign::AdditiveBox", "Box")
    doc.getObject("Body").addObject(box)
    doc.recompute()
    path = os.path.join(s["scratch"], name + ".FCStd")
    doc.saveAs(path)
    return doc, path


def left_as(path, design, uuid, age):
    target = os.path.join(s["project"], "%s.FCStd.%s" % (design, uuid))
    shutil.copy(path, target)
    stamp = time.time() - age
    os.utime(target, (stamp, stamp))
    return target


# -- Path 1 -------------------------------------------------------------------------------
def setup():
    from sciforge import home_core, home_ui

    s["project"] = tempfile.mkdtemp(prefix="sciforge-unfinished-")
    s["scratch"] = tempfile.mkdtemp(prefix="sciforge-unfinished-src-")
    s["old_project"] = App.ParamGet(FILES).GetString("ProjectFolder", "")
    App.ParamGet(FILES).SetString("ProjectFolder", s["project"])
    state = home_core.empty()
    state["merged_mru"] = True
    home_ui.save_state(state)
    doc, path = a_save("Source")
    App.closeDocument(doc.Name)
    left_as(path, "test", UUIDS[0], 300)
    left_as(path, "test", UUIDS[1], 200)
    left_as(path, "test", UUIDS[2], 100)
    left_as(path, "the THING", UUIDS[3], 60)
    home_ui.show()
    home().refresh()


def designs_listed():
    from sciforge import versions

    for name in ("test", "the THING"):
        h.check(
            "%s.FCStd is made from its unfinished save" % name,
            versions.complete_save(os.path.join(s["project"], name + ".FCStd")),
        )
    listed = names("local")
    # (Source, saved in another folder to make the files, is listed too: "another folder")
    h.check("This computer lists both", {"test", "the THING"} <= set(listed), listed)
    left = [n for n in os.listdir(s["project"]) if ".FCStd." in n]
    h.check("no unfinished save left beside them", left == [], left)
    kept = os.listdir(os.path.join(s["project"], versions.UNFINISHED_FOLDER))
    h.check("the two older saves of test are kept aside", len(kept) == 2, kept)
    h.shot("listed")


designs_listed.wait_ms = 1500


# -- Path 2 -------------------------------------------------------------------------------
def save_left_unfinished():
    from sciforge import versions_ui

    doc, path = a_save("Rescued")
    design = os.path.join(s["project"], "Rescued.FCStd")
    started = time.time() - 1
    left_as(path, "Rescued", UUIDS[0], 0)
    s["done"] = versions_ui._finish_interrupted(doc, design, started, tries=4)
    s["design"] = design


save_left_unfinished.wait_ms = 1500


def rescued():
    from sciforge import versions

    h.check("SciForge finished the save", s["done"] and versions.complete_save(s["design"]))
    h.check("Home lists it first in Recent", names("recent")[:1] == ["Rescued"], names("recent"))
    for name in list(App.listDocuments()):
        App.closeDocument(name)
    App.newDocument("Scratch")  # (the harness ends on a design)
    if s.get("old_project"):
        App.ParamGet(FILES).SetString("ProjectFolder", s["old_project"])
    else:
        App.ParamGet(FILES).RemString("ProjectFolder")
    for folder in (s["project"], s["scratch"]):
        shutil.rmtree(folder, ignore_errors=True)


rescued.wait_ms = 1000

h.run("unfinished_save", [setup, designs_listed, save_left_unfinished, rescued])
