# SPDX-License-Identifier: LGPL-2.1-or-later
"""Boss and Rest in an empty design, then a Boss placed by clicking a face, real input only:
PLASTIC tab > Boss and > Rest with no part (nothing opens, the reason is said, no error);
then an enclosure (no lid): Boss, click the floor inside: SciForge puts a point sketch on
the floor, raises the parting plane 3 x the screw (9 mm) and builds a standoff on the thread
side (volume by hand), a second click adds a second standoff, a click on a wall (another
face) is refused, OK, Ctrl+Z takes the bosses and their point sketch away."""

import math

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import harness as h
from SciForgeTests.gui import plastic_steps as ps

V = App.Vector
s = {}


def empty():
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("PlasticEmpty")
    ps.plastic_tab()
    Gui.Selection.clearSelection()
    h.ribbon("Boss")


def nothing_opened():
    h.check(
        "Boss with no part: no dialog", ps.boss_panel() is None and not Gui.Control.activeDialog()
    )
    h.ribbon("Rest")


def rest_nothing():
    h.check(
        "Rest with no part: no dialog", ps.rest_panel() is None and not Gui.Control.activeDialog()
    )
    App.closeDocument(App.ActiveDocument.Name)


def setup():
    doc, bottom, _lid, _sk = ps.enclosure("PlasticBossFace", lid=False, points=())
    s.update(bottom=bottom.Name)
    s["v0"] = ps.volume(bottom)
    ps.plastic_tab()


def bottom():
    return App.ActiveDocument.getObject(s["bottom"])


def start():
    Gui.Selection.clearSelection()
    h.ribbon("Boss")


def click_floor():
    h.fit()
    h.click(V(10, 32, 2))


def standoff():
    p = ps.boss_panel()
    ps.settle(p)
    h.check("a point on the floor", p is not None and len(p.refs) == 1, p and p.refs)
    sk = p.refs[0][0] if p and p.refs else None
    h.check(
        "its point sketch lies on the floor",
        sk is not None and abs(sk.getGlobalPlacement().Base.z - 2.0) < 1e-6,
    )
    h.check(
        "the parting plane raised 3 x the screw",
        p and abs(p.offset.value() - 9.0) < 1e-9,
        p and p.offset.value(),
    )
    h.check("one side only (no lid above)", p and len(p.steps) == 1, p and p.steps)
    want = s["v0"] + standoff_volume()
    v = ps.volume(bottom())
    h.check("standoff by hand (+%.2f)" % standoff_volume(), ps.near(v, want, 0.5), (v, want))
    h.check("no error", p and p.message.text() == "", p and p.message.text())
    s["v1"] = v
    h.shot("1-standoff")


def standoff_volume():
    """A default thread side (M3) from 11 mm above the floor (z 2): tip at z 10.95, the shank
    8.95 down to the floor, its tip carried on 0.9, a 1 mm root fillet, the pilot hole r 1.2
    from the top down to 1 mm above the outside."""
    t = ps.TAN1
    shank = ps.frustum(8.95, 3.75, 3.75 + 8.95 * t)
    tip = ps.frustum(0.9, 3.75 + 0.9 * t, 3.75)
    root = ps.fillet_ring(3.75 + 8.95 * t, 1.0)
    hole = math.pi * 1.2**2 * (0.9 + 8.95 + 1.0)
    return shank + tip + root - hole


def click_floor_again():
    h.click(V(30, 32, 2))


def two_standoffs():
    p = ps.boss_panel()
    ps.settle(p)
    h.check("a second point on the floor", p is not None and len(p.refs) == 2, p and p.refs)
    v = ps.volume(bottom())
    h.check("two standoffs", ps.near(v, s["v0"] + 2 * standoff_volume(), 1.0), v)


def click_wall():
    h.click(V(0, 20, 10))


def wall_refused():
    p = ps.boss_panel()
    ps.settle(p)
    text = p.message.text() if p else ""
    h.check("a point on another face is refused", "one face" in text, text)
    h.check("still two points", p and len(p.refs) == 2)


def ok():
    ps.ok()


def done():
    h.check("dialog closed", ps.boss_panel() is None)
    h.check("kept", ps.near(ps.volume(bottom()), s["v0"] + 2 * standoff_volume(), 1.0))


def undo():
    ps.undo()


def undone():
    doc = App.ActiveDocument
    h.check("Ctrl+Z: the floor as before", ps.near(ps.volume(bottom()), s["v0"], 1e-6))
    h.check(
        "Ctrl+Z: the point sketch gone too",
        doc.getObject("BossPoints001") is None
        and not [o for o in doc.Objects if o.Label == "Boss Points" and o.Name != "BossPoints"],
    )


h.run(
    "plastic_boss_face",
    [
        empty,
        nothing_opened,
        rest_nothing,
        setup,
        start,
        click_floor,
        standoff,
        click_floor_again,
        two_standoffs,
        click_wall,
        wall_refused,
        ok,
        done,
        undo,
        undone,
    ],
)
