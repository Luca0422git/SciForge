# SPDX-License-Identifier: LGPL-2.1-or-later
"""Boss > Fastener > Create Component, real input only: an enclosure and its lid, Boss on the
sketch's two points, tick Create Component: a "Fastener" component with a "Screw" body holds a
pan-head M3 screw at each boss (volume by hand: the head r 3 x 1.8 on the counterbore's
floor, the shank r 1.5 down to 0.5 mm above the pilot hole's bottom, 20.55 long), Head Type
Hex (across corners 6: it fits the 6.5 counterbore), OK; edit the boss from the timeline
and untick it: the component goes; Ctrl+Z brings it back."""

import math
import re

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plastic_steps as ps

V = App.Vector
s = {}

PAN = 2 * (math.pi * 3.0**2 * 1.8 + math.pi * 1.5**2 * 20.55)
HEX_AREA = 1.5 * math.sqrt(3) * 3.0**2  # a hexagon 6 across corners (circumradius 3)
HEX = 2 * (HEX_AREA * 1.8 + math.pi * 1.5**2 * 20.55)


def fasteners():
    from sciforge import plastic_boss_fastener as pf

    return [o for o in App.ActiveDocument.Objects if pf.is_fastener(o)]


def setup():
    doc, bottom, lid, sk = ps.enclosure("PlasticFastener")
    s.update(bottom=bottom.Name, lid=lid.Name)
    ps.plastic_tab()


def start():
    Gui.Selection.clearSelection()
    h.ribbon("Boss")


def pick():
    ps.click_row("Boss Points")


def tick():
    p = ps.boss_panel()
    ps.settle(p)
    h.check("no fastener yet", fasteners() == [])
    h.check("head type hidden until ticked", p and not p.head.isVisible())
    ps.check_box(p.fastener)


def screws():
    p = ps.boss_panel()
    ps.settle(p)
    found = fasteners()
    h.check("one fastener step", len(found) == 1, found)
    if not found:
        return
    from sciforge import bodies, components

    body = bodies.body_of(found[0])
    comp = components.container_of(body)
    h.check("in a Screw body", body is not None and body.Label == "Screw", body and body.Label)
    h.check(
        "in a Fastener component",
        comp is not None and comp.Label.startswith("Fastener"),
        comp and comp.Label,
    )
    v = found[0].Shape.Volume
    h.check("two pan-head screws by hand (%.3f)" % PAN, ps.near(v, PAN, 1e-6), v)
    h.check("two solids", len(found[0].Shape.Solids) == 2)
    lid = App.ActiveDocument.getObject(s["lid"])
    h.check(
        "the screws clear the lid (clearance hole)", found[0].Shape.common(lid.Shape).Volume < 1e-6
    )
    h.check("head type shown", p and p.head.isVisible())
    h.shot("1-screws")


def hex_head():
    p = ps.boss_panel()
    ps.choose(p.head, "Hex")


def hexed():
    p = ps.boss_panel()
    ps.settle(p)
    found = fasteners()
    v = found[0].Shape.Volume if found else 0
    h.check("hex heads by hand (%.3f)" % HEX, ps.near(v, HEX, 1e-6), v)
    lid = App.ActiveDocument.getObject(s["lid"]) if "lid" in s else None
    if found and lid is not None:
        h.check(
            "the hex heads clear the counterbore (QA)",
            found[0].Shape.common(lid.Shape).Volume < 1e-6,
            found[0].Shape.common(lid.Shape).Volume,
        )


def round_head():
    p = ps.boss_panel()
    ps.choose(p.head, "Round")


def rounded():
    p = ps.boss_panel()
    ps.settle(p)
    found = fasteners()
    cap = math.pi * 1.8**2 * (3 * 3.4 - 1.8) / 3  # a dome r 3 x 1.8: sphere r 3.4
    want = 2 * (cap + math.pi * 1.5**2 * 20.55)
    v = found[0].Shape.Volume if found else 0
    h.check("round heads by hand (%.3f)" % want, ps.near(v, want, 1e-6), v)
    ps.choose(p.head, "Hex")


def ok():
    p = ps.boss_panel()
    ps.settle(p)
    ps.ok()


def done():
    h.check("dialog closed", ps.boss_panel() is None)
    h.check("the fastener kept", len(fasteners()) == 1)


def edit():
    titles = [t for t in ps.timeline_titles() if re.match(r"^Boss \d+$", t)]
    h.check("the boss steps in the timeline", len(titles) == 2, ps.timeline_titles())
    ps.double_click_timeline(titles[0])


def untick():
    p = ps.boss_panel()
    ps.settle(p)
    h.check(
        "edit shows the fastener ticked, hex",
        p and p.fastener.isChecked() and p.head.currentData() == "hex",
    )
    ps.check_box(p.fastener)


def ok_edit():
    p = ps.boss_panel()
    ps.settle(p)
    ps.ok()


def gone():
    h.check(
        "untick: the screws and their component go",
        fasteners() == []
        and not [
            o
            for o in App.ActiveDocument.Objects
            if o.TypeId == "App::Part" and o.Label.startswith("Fastener")
        ],
    )


def undo():
    ps.undo()


def back():
    h.check(
        "Ctrl+Z: the screws back",
        len(fasteners()) == 1 and ps.near(fasteners()[0].Shape.Volume, HEX, 1e-6),
    )


def save():
    import os
    import tempfile

    s["path"] = os.path.join(tempfile.mkdtemp(prefix="sf-plastic-"), "PlasticFastener.FCStd")
    App.ActiveDocument.saveAs(s["path"])


def reopen():
    App.closeDocument(App.ActiveDocument.Name)
    doc = App.openDocument(s["path"])
    doc.recompute()
    h.fit()


def reopened():
    found = fasteners()
    h.check("reopened: the screws", len(found) == 1, found)
    if found:
        h.check("reopened: hex screws by hand", ps.near(found[0].Shape.Volume, HEX, 1e-6))
        h.check("reopened: valid", "Invalid" not in found[0].State, found[0].State)


h.run(
    "plastic_boss_fastener",
    [
        setup,
        start,
        pick,
        tick,
        screws,
        hex_head,
        hexed,
        round_head,
        rounded,
        ok,
        done,
        edit,
        untick,
        ok_edit,
        gone,
        undo,
        back,
        save,
        reopen,
        reopened,
    ],
)
