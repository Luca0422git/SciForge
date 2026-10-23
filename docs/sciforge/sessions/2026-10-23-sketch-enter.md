# 2026-10-23: sketch-enter (time spent entering and leaving a sketch)

Branch `wf/sketch-enter` (from experimental 8af46ba). Session was short (Luca had about 45
minutes), so this is a measurement plus one small, safe change, not the full rework.

## In plain words

Opening a sketch (Create Sketch, or double-clicking one) and closing it (Finish Sketch) each
make FreeCAD switch to its own Sketcher workbench and back. SciForge uses that switch to show
and hide the SKETCH tab. I measured where the time goes and found that the switch itself is
about half of it. Removing the switch would make entering and leaving noticeably quicker, but
it touches how the Sketcher's own keys and toolbars come into being, and there was no time
to prove nothing breaks, so I did not do it. I wrote down exactly what it would take (below).

What did change: when FreeCAD puts the Sketcher's toolbars up during the switch, SciForge now
hides them straight away, before the window is laid out and drawn with them, instead of only
on the next turn of the event loop (it still checks again at 0, 150 and 600 ms as before).
The end result on screen is the same; it just avoids laying the window out with toolbars that
are about to go. The sandbox cannot show whether that is noticeable (software drawing); Luca
judges the feel.

## Measurements (sandbox, software OpenGL, 4 shared CPUs: information only)

New scenario `sketch_enter_perf` (writes `sketch-enter-report.md` with full profiles next to
the test output). Wall time of the action plus the events it queues.

| Action | before (8af46ba) | after |
| --- | --- | --- |
| Create Sketch (ribbon + plane click, first sketch of the session) | 535 ms | 612 ms |
| Edit a sketch (setEdit, what a double-click does), median of 5 | 270 ms | 276 ms |
| Finish Sketch, median of 6 | 204 ms | 182 ms |
| Experiment: same sketch with `EditingWorkbench` empty (no switch) | - | enter 167 ms, leave 84 ms |

The differences before/after are within the sandbox's noise. The experiment row is the
interesting one: without the workbench switch, entering is ~110 ms and leaving ~100 ms
quicker here.

Where the time goes (profiles):

* Edit (270 ms): `setEdit` 108 ms, of which the TempoVis workbench switch 30 ms (FreeCAD
  rebuilding toolbars/menus in C++); then ~160 ms in the event loop (laying out and drawing
  the window and 3D view, C++). SciForge's own Python work is small: sketch session start
  20 ms (palette 11 ms), the app-wide mouse filter of `sketch_area_pick` 22 ms (it sees all
  ~7500 Qt events the switch produces, ~3 microseconds each), `_hide_toolbars` 5 ms.
* Finish (190 ms): `resetEdit` 38 ms (workbench switch back 20 ms), then ~145 ms in the event
  loop; mouse filter 10 ms (3800 events). No repeated recompute was found.
* Create Sketch: the first switch to the Sketcher in a session costs 160 ms on its own
  (FreeCAD loads the Sketcher workbench and makes its toolbars); `addObject` 80 ms.

## What removing the switch would take (not done)

`ViewProviderSketch::setEdit` runs `tv.activateWorkbench(ViewObject.EditingWorkbench)` only
when that property is non-empty. To keep SciForge's workbench active:

1. `EditingWorkbench` is a saved property: setting it on sketches would be written into the
   files (stock FreeCAD would then not switch to the Sketcher when opening them). It would
   have to be set only while SciForge is on and never saved (e.g. a core patch in
   ViewProviderSketch asking a hook, or setting it just before every `setEdit`, which does
   not cover FreeCAD's own double-click in the tree/3D view).
2. The SKETCH tab, sketch mode and toolbar handling would follow SciForge's own edit hooks
   (`sketch_mode` already starts its session from the edit itself) instead of
   `shell.on_workbench("SketcherWorkbench")`.
3. The Sketcher's own commands and keys: FreeCAD makes the Sketcher's toolbar buttons (and
   with them its one-letter keys) when the Sketcher workbench is activated
   (`sketch_mode.repark_keys`). Without the switch, those keys that SciForge does not bind
   itself may stop working; this has to be checked key by key (`sketch_qa_keys`, `keys`).
4. Then every sketch*/fixsketch*/sketch2_*/sketch_tools_*/modeling2_sketch scenario,
   Undo across sketch edits, sketches in other bodies/components, and FreeCAD with SciForge
   off.

## Tests

* `sketch_enter_perf` (new): sketch opens, SKETCH tab up, Finish closes it, SKETCH tab gone,
  5 rounds; the experiment puts the property back and leaves nothing in edit.
* `--only base` at 8af46ba (before any change): everything passes except the headless
  "docs examples" check `get_drawing#1` (a number -22 is now -23): already failing at
  8af46ba, unrelated to sketches.
* Results of the runs after the change: see the report at the end of the session (below).
