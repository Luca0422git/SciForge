# 2026-10-21: speed with big designs (branch `wf/view-speed`)

To be copied into MEMORY.md by whoever merges (this branch does not edit MEMORY.md).
Luca approved idea 6 of `docs/sciforge/dev/cadcraft-lessons.md` ("Faster and smoother on big
models"); it follows the "Session log: speed all round" (EDIT previews) in MEMORY.md. The work
was started by one session, cut off by machine restarts twice, and finished by a second and a
third one (which re-ran the measurements and tests below). No core patch: only `src/Mod/SciForge/` changed.

## In plain words (for Luca)

SciForge now stays calm while you only look at a big design: the timeline and the browser
used to re-read the whole design twice a second "just in case", which on a design of 120 steps
ate a quarter of the processor and made orbiting stutter. Now they re-read only when FreeCAD
says something changed. Undo and Redo after editing a big design take about a second instead
of 15-19 s, because SciForge no longer rebuilds the whole design when FreeCAD has already put
back exactly the right shapes (when it cannot be sure, it rebuilds as before). The timeline and
browser rebuild 3-6x faster, adding a step to a long design is 3x faster, and a few hidden
slow spots (finding lost fillet edges again, copying big parts to check what an extrusion
touches, writing an unchanged recovery copy every 5 minutes) are gone. What still takes time
is FreeCAD's own rebuild of the geometry after an edit (OCC: 11-14 s on these test designs)
and drawing with the sandbox's software OpenGL; those are not SciForge's Python.

## Measuring: `perf_big_model` (new GUI scenario)

`SciForgeTests/gui/scenarios/perf_big_model.py` (run alone:
`run_tests.sh --scenario perf_big_model`, ~10 min) builds, through the golden-model builder:

- a plate with a dense grid of holes and rounded bosses: **1716 faces, 5124 edges**;
- a "tower" body with a long history: **121 timeline steps** (158 objects in all);
- a third body made into a component.

and times, each with the top of a cProfile (cumulative and own time) in the report:
idle (what the timers cost per second), orbit / zoom / pan frame by frame (and orbit with
four RenderCache / VBO settings), hover over the dense plate (one mouse step), select a face,
Ctrl+click a second, clear, the timeline and browser forced rebuild / explicit re-read / timer
tick with nothing changed, an edit of the plate's first step and of the tower's first step
(recompute inside the transaction like a dialog's OK, then redisplay, then Ctrl+Z and Ctrl+Y),
adding a step at the end, save and open. "wall" is what a person waits, "sciforge" the part of
it spent in Python (SciForge's code and what it calls). Report:
`perf-big-report.md` / `.json` next to the other test output. `SCIFORGE_PERF_SCALE` grows or
shrinks the design.

**Regression guard** (`SciForgeTests/gui/perf_guard.py`, unit `test_perf_guard`): both
benchmarks (`perf_benchmark`, `perf_big_model`) compare every action with a stored baseline
and list each one more than **2x slower** (and more than 5 ms slower: noise floor) as a
warning in the report and the log; `SCIFORGE_PERF_STRICT=1` makes it a failure (for runs on
the machine the baseline came from). Baseline: `SciForgeTests/gui/perf_baseline.json`
(written from this session's runs in the sandbox) or `SCIFORGE_PERF_BASELINE=<file>` (any
perf report json or a `{label: seconds}` map; `none` switches it off).
`SCIFORGE_PERF_WRITE_BASELINE=<file>` stores a run's times there (merged: both benchmarks can
share one file). Each report's table also shows, next to every time, the stored baseline and
(perf_big_model) the time before this work (`SciForgeTests/gui/perf_before.json`: the
benchmark run at commit 0b1da82), so a report says by itself how far things have come.

## Before / after (same benchmark, same design, run side by side on the same machine)

"Before" is commit 0b1da82 (the branch's base) with only the new scenario copied in; "after"
is this branch. Milliseconds; idle = busy ms per second. Software OpenGL under xvfb, 4 CPUs.

| What | wall before | wall after | sciforge before | sciforge after |
|---|---:|---:|---:|---:|
| Idle: busy time per second (timers) | 251.5 | 38.5 | 242.9 | 29.8 |
| Orbit: one frame | 44.3 | 43.9 | 17.1 | 3.1 |
| Zoom: one frame | 42.1 | 39.9 | 11.0 | 0.5 |
| Pan: one frame | 35.8 | 41.3 | 7.3 | 1.4 |
| Hover: one mouse step over the dense plate | 9.2 | 9.7 | 6.7 | 1.6 |
| Select: click a face | 39.8 | 111.2 * | 156.1 | 103.6 * |
| Select: Ctrl+click a second face | 34.8 | 29.7 | 45.0 | 20.3 |
| Select: clear the selection | 0.5 | 0.4 | 98.4 | 1.9 |
| Timeline: rebuilt (forced) | 100.3 | 28.7 | 279.3 | 33.3 |
| Timeline: timer tick, nothing changed | 22.5 | 0.1 | 22.5 | 0.0 |
| Browser: rebuilt (forced) | 65.7 | 31.0 | 256.0 | 40.1 |
| Browser: read again, nothing changed | 65.1 | 31.3 | 65.1 | 31.4 |
| Browser: timer tick, nothing changed | 63.9 | 1.1 | 63.9 | 1.1 |
| Edit plate's first step: recompute + redisplay | 13923 | 13764 | 14301 | 13769 |
| Edit plate's first step: Undo (Ctrl+Z) | 18849 | 1717 | 18020 | 119 |
| Edit plate's first step: Redo (Ctrl+Y) | 18218 | 1598 | 17306 | 114 |
| Edit first of 121 steps: recompute + redisplay | 14468 | 11490 | 17422 | 11730 |
| Edit first of 121 steps: Undo (Ctrl+Z) | 15043 | 883 | 17992 | 194 |
| Edit first of 121 steps: Redo (Ctrl+Y) | 15687 | 730 | 18513 | 134 |
| Add a step at the end (sketch + extrude) | 1374 | 446 | 1607 | 419 |
| Save the big design | 1593 | 1351 | 166 | 130 |
| Open the big design | 5404 | 5109 | 1605 | 651 |

\* one run's first click paid a one-off lazy `import` in `selection_ui._handle_under`
(77 ms, the first click of the session only); earlier runs of the branch measured 29-33 ms
wall, 25-28 ms sciforge. Orbit / zoom / pan / hover wall times are dominated by software
OpenGL drawing and vary by +-10 ms between runs; what SciForge adds per frame went from
7-17 ms (a panel's poll landing in the middle of the orbit) to 0.5-3 ms. The recompute itself
is FreeCAD/OCC (`App.Document.recompute` is 99 % of it); the 2-3 s less on the tower's edit
is the panels no longer reading the design from inside the recompute. The previous session's
first measurement (an earlier version of the scenario, edits made outside a transaction) had
55 s for the edit and 88 s for its undo, 31 s of it in `curves.refind` (fixed, see below).

View settings measured (orbit, RenderCache 0 / 1 / 2, VBO on / off): no difference beyond the
noise under software GL, so none is changed (worth measuring again on a real GPU).

## What was changed (behaviour identical)

- **Idle polls gated** (`doc_epoch.py`, new; unit `test_doc_epoch`): a counter moved by
  FreeCAD's document signals (objects made / changed / deleted / recomputed, undo / redo,
  transactions, documents opened / closed / switched, edit started / ended). The timeline
  (400 ms) and browser (500 ms) timer ticks (`_poll`) compare a key (counter, active
  document, body, component, object in edit) and read the design only when it moved, or at
  least every 5 s in case FreeCAD changed something without a signal. An explicit
  `refresh()` still always reads. Ticks that fire from inside a long recompute or while a file
  is read (FreeCAD runs Qt's events from inside them) wait for the end instead of reading a
  half-built design (33 browser + 35 timeline reads during one 20 s edit; 30 while opening).
  Found the hard way: the GUI observer must not watch the views' created / changed signals;
  asking for a view provider's Python object while FreeCAD builds it fixes its type as a
  plain one (PartDesign's `makeTemporaryVisible` was gone: "Fillet could not start picking").
- **Undo / Redo without a rebuild** (`undo_fast.py`, new; unit `test_undo_fast`, GUI
  `undo_fast`): `timeline_ui.after_undo` recomputed after every Undo / Redo (Fusion does),
  15-19 s on these designs, although FreeCAD had already put back the shapes built from the
  values it restored (every dialog's OK recomputes inside its transaction, so the transaction
  holds the shapes too). A ledger per document (from the document observer) records whether
  the design was up to date when each transaction started / ended and every change made
  outside a transaction; the rebuild is skipped only when the transaction undone started (redo:
  ended) on an up-to-date design, nothing changed outside a transaction since, every object
  left touched had its Shape put back by this Undo / Redo, and none is in error. Then the
  touched marks are cleared. Anything it cannot vouch for (its stack out of step with
  FreeCAD's, a spreadsheet or other object without a Shape, a script change in between) is
  rebuilt as before; `undo_fast.stats` and `SCIFORGE_UNDO_DEBUG=1` say which. Also: an
  after-undo arriving in the middle of a recompute now waits for it to end (it nested a
  second full recompute in the first).
- **Lost picks found again with each shape described once** (`curves._Pool`): a fillet of
  many edges on the dense plate lost them all after an edit of the first step, and looking
  for each one described every edge again (153 052 records, 31 s); now the elements of each
  shape are described once per refind (same answers, under 1 s). `curves.remember` takes one
  bounding box per part instead of one per pick.
- **Timeline keeps step buttons** whose look did not change (`timeline_ui._rebuild`,
  `_look`): making and styling 120 buttons after every change took 140 ms.
- **Browser**: `surface.is_surface_shape` counts faces (`countElement`) instead of listing
  them (23 ms per body on every read).
- **Extrude's body checks** read shapes without copying them (`bodies.global_shape(copy=False)`,
  `extrude_bodies.before_shape`; 0.2 s per body per check on the plate) and the face list with
  boxes of a body is remembered for the last few shapes (`shape_checks.face_boxes`, 0.12 s per
  preview); `extrude_prism.farthest` tessellates a copy so a body's own shape keeps no mesh.
- **Recovery copies** (`versions_ui.Recovery`) skip a design unchanged since its last copy
  (writing a big design froze the window ~2 s every 5 minutes while the person only looked).

## Ideas from the brief not done (and why)

- Background tessellation / "keep drawing the old picture while the new one is built":
  Coin and OCC are not safe off the main thread in FreeCAD; not attempted.
- Detail by zoom (simplifying tiny faces): FreeCAD's own deviation settings already apply;
  under software GL nothing measurable to gain here.
- Hover and selection: SciForge's share is already 1-2 ms per mouse step and 20-30 ms per
  click (FreeCAD's `getObjectInfo` pick and Coin are the rest); nothing worth changing.
- Opening: 5.1 s, of which FreeCAD's `openDocument` is ~4.8 s; SciForge's part went from
  1.6 s to 0.65 s (the panels no longer read while the file is restored).

## Tests

- Unit (plain Python): `test_doc_epoch`, `test_undo_fast`, `test_perf_guard` (34 tests, pass).
- GUI scenarios (new): `perf_big_model` (33 checks), `undo_fast` (35 checks: paths A-D, real
  timeline double-clicks, typing, OK, Ctrl+Z / Ctrl+Y and the quick-access Undo / Redo;
  every skipped rebuild checked against a full rebuild giving the same shapes).
- Related scenarios and `--only base`: see the results below.

Results (all on this branch's final code, real FreeCAD in the sandbox):

- `--only base`: unit 1831 tests OK (9 skipped), golden 446 pass + 2 known XFAIL
  (`plate_hole_grid`, `sf_loft_merge_slot_volume`, the same as on the base commit), smoke
  and journey all passed (run twice: by the second session and again by the third).
- Related GUI scenarios, all PASS (65 scenarios):
  - timeline / browser / selection / view: `timeline_browser`, `_2`, `_qa`, `_qa2`, `_qa3`,
    `_qa4`, `timeline_roll_view`, `timeline_rolled_cut`, `selection_box`, `_dialogs`,
    `_filters`, `_other`, `_sketch`, `view_angle_snap`, `view_origin_planes`,
    `viewcube_click`;
  - recovery copies and saving: `versions_recovery`, `versions_save`, `versions_link`,
    `versions_data_panel`, `crash_notice`, `home_screen`, `welcome_line`;
  - extrude body checks, surfaces: `extrude_bodies_highlight`, `extrude_multibody`,
    `_edit`, `_move`, `components_extrude`, `gaps_extrude_taper_to`, `surface_extrude`,
    `surface_misc`, `surface_trim`, `surface_reopen`, `gaps_thin_extrude`,
    `gaps_offset_plane_to`, `revolve_qa_to`, `extrudeface_objects`;
  - lost picks found again (curves / picks refind): `gaps_picks_kept`, `fillet_qa`,
    `fillet_qa_part`, `fillet2_edit_later`, `fillet2_sets`, `modify2_move_face`,
    `modify_replace_face`, `construct_live`, `inspect_construct_use`, `surface2_loft`;
  - Undo / Redo (after_undo now often skips its rebuild): `undo_fast`, `bodies_combine`,
    `bodies_delete`, `bodies_qa`, `bodies_qa_2`, `bodies_timeline`, `direct_history`,
    `direct_step_box`, `modify_remove`, `modify_align`, `modify2_shell`, `patterns_qa_edit`,
    `components2_pattern`, `joints2_slider`, `joints_drive`, `hole_qa`, `insert_mesh`,
    `misc_scripts`, `misc_derive`, `shell_draft_hollow`;
  - the benchmarks: `perf_benchmark` (21 checks, guard: 16 measurements compared, none more
    than 2x slower) and `perf_big_model` (33 checks, guard: 27 compared, none 2x slower).
- No existing scenario needed a changed expectation.

Last `perf_big_model` run (third session, a quieter machine than the side-by-side runs, so
everything is a little faster, FreeCAD's own work included): idle 17 ms/s, orbit / zoom /
pan 24-28 ms a frame (SciForge 0.2-1.5 ms), hover 6 ms, a click 26 ms, timeline / browser
tick 0.0 / 0.9 ms, Undo / Redo of the plate edit 1.2 / 1.1 s, of the tower edit 0.5 / 0.6 s,
open 3.8 s.

## Limitations

- The benchmark times depend on the machine and on what else runs on it (other agents ran
  FreeCAD tests at the same time): the guard only warns by default, and the stored baseline
  should be rewritten (`SCIFORGE_PERF_WRITE_BASELINE`) when it is used on another machine.
- Undo / Redo still rebuild (as before) when the ledger cannot vouch for the shapes: a change
  made by a script outside a transaction in between, a spreadsheet / parameter step (no
  Shape to put back), or an undo stack whose start it did not see. That is the safe side:
  the worst case is the old speed, never a wrong shape.
- Orbit / zoom drawing itself is software OpenGL in the sandbox; nothing measured there says
  how a real GPU behaves, and view settings (RenderCache, VBO) were left as they are.
