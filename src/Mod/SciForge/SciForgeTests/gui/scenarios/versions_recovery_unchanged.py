# SPDX-License-Identifier: LGPL-2.1-or-later
"""Recovery copies of unchanged designs are not written again (versions_ui.Recovery,
SciForge speed with big designs; review finding F2, 2026-10-22).

Writing a recovery copy of a big design freezes the window for seconds, so a design that did
not change since its last copy is skipped. Writing one design's copy moved the change counter
(doc_epoch) that the other designs' copies compare with, so with two changed designs open
every tick rewrote both. The recovery timer is stopped and the ticks are made by hand:
1. one changed design: the first tick writes it, the second writes nothing;
2. a second changed design: the next tick writes it, the two ticks after it write nothing;
3. a real change to the first design: the next tick writes its copy again (at least it).
"""

import FreeCAD as App
import FreeCADGui as Gui

from SciForgeTests.gui import harness as h

S = {}


def rec():
    from sciforge import versions_ui

    return versions_ui.recovery()


def make(name):
    from SciForgeTests.golden.builder import Builder
    from sciforge import versions_ui

    doc = App.newDocument(name)
    b = Builder(doc)
    b.run({"op": "sketch", "id": "s1", "plane": "XY", "geometry": [{"rect": [0, 0, 40, 30]}]})
    b.run({"op": "extrude", "id": "e1", "profile": "s1", "distance": 10})
    doc.recompute()
    versions_ui.set_modified(doc, True)
    S["pad_" + name] = b.objects["e1"]
    return doc


def setup():
    Gui.activateWorkbench("SciForgeWorkbench")
    rec().timer.stop()  # the ticks are made by hand below
    S["a"] = make("RecUnchangedA")


def tick(tag):
    def step():
        from sciforge import doc_epoch

        r = rec()
        before = r.written
        n = r.save_all(forced=False)
        print(
            "[SciForge] recovery tick %s: wrote %s (written %d -> %d), epoch %d"
            % (tag, n, before, r.written, doc_epoch.value()),
            flush=True,
        )
        S[tag] = r.written - before

    step.__name__ = "tick_" + tag
    step.wait_ms = 1500
    return step


def one_checks():
    h.check("one design: the first tick writes it", S["one_1"] == 1, S["one_1"])
    h.check("one design: unchanged, the second tick writes nothing", S["one_2"] == 0, S["one_2"])


def second():
    S["b"] = make("RecUnchangedB")


def two_checks():
    h.check("two designs: the first tick writes the new one", S["two_1"] >= 1, S["two_1"])
    h.check("two designs: unchanged, the next tick writes nothing", S["two_2"] == 0, S["two_2"])
    h.check("two designs: unchanged, the tick after writes nothing", S["two_3"] == 0, S["two_3"])


def change_a():
    doc = S["a"]
    pad = S["pad_RecUnchangedA"]
    doc.openTransaction("taller")
    pad.Length = 15
    doc.recompute()
    doc.commitTransaction()


def changed_checks():
    h.check("a real change: the next tick writes the copy again", S["changed_1"] >= 1, S["changed_1"])
    h.check("after it, unchanged again: nothing written", S["changed_2"] == 0, S["changed_2"])


def cleanup():
    from sciforge import versions

    r = rec()
    for entry in versions.list_recovery(r.folder):
        try:
            versions.discard_recovery(r.folder, entry["key"])
        except Exception:
            pass
    for name in ("RecUnchangedA", "RecUnchangedB"):
        try:
            App.closeDocument(name)
        except Exception:
            pass
    r.start()


h.run(
    "versions_recovery_unchanged",
    [
        setup,
        tick("one_1"),
        tick("one_2"),
        one_checks,
        second,
        tick("two_1"),
        tick("two_2"),
        tick("two_3"),
        two_checks,
        change_a,
        tick("changed_1"),
        tick("changed_2"),
        changed_checks,
        cleanup,
    ],
)
