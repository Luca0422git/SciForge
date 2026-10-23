# Session log: Draft angle in real time (branch `wf/draft-live`)

To be copied into MEMORY.md by whoever merges (this branch does not edit MEMORY.md). Started
from `experimental` (c59634a). No FreeCAD core file changed (nothing for `core-patches.md`).

Luca, on his Windows PC with a real GPU: "Draft is still extremely slow. The whole point of
being able to drag the angle of a draft is to see it update in real time. I can barely call it
real time. And the angle dragger doesn't even update either: it waits behind for the model to
update. It takes at least 1-3 seconds to update. Make it faster."

STATUS: done, then reviewed (13 findings); the fixes are in "Review fixes" at the end.

## Why it was slow (measured, plain language)

A preview rebuild runs on the main thread: while it runs, nothing else moves, the dragged
handle included. During a drag the dialog rebuilt the exact drafted solid every ~60-400 ms, so
the handle froze for the length of each rebuild. On a realistic part (100 x 60 x 30 block,
179 faces, its 8 outer side walls drafted) one rebuild cost ~0.9 s in the sandbox:

- 0.52 s `drafting.undrafted()` (a check that no picked face was skipped: it measured the area
  and centre of every face of the result for every picked face);
- 0.30 s the document recompute (the Draft itself ~0.05 s, the rest FreeCAD's drawing of the
  new solid);
- the limit search (an angle past what fits): up to 1.5 s of trial builds, all at once.

Found on the way (a bug): past the steepest angle that fits, FreeCAD's own Draft makes a broken
solid without an error; the dialog showed it as if it worked, and OK then silently refused.

## What changed (plain language)

**1. The handle never waits for the model.** While the angle disc is dragged, the Draft
dialog no longer builds the exact solid between two mouse moves. It builds it once the mouse
rests for 0.2 s (`taskui.Panel.PAUSE_MS`; holding the button still counts as resting) or is
let go (`settle_now()`), and only for the latest angle. The dialog asks for this with
`schedule(settle=True)` and `REST_FIRST = True` (`taskui.Panel.schedule` / `_tick`). A mouse
move with a button held keeps the wait going even when the value does not change (a snapped
angle), seen by the 3D view's event filter (`TypeOverView` notes `panel._last_motion`).

**2. A live picture of the drafted faces** (`sciforge/draft_live.py`, arithmetic in
`draft_live_core.py`, unit tested): the picked faces' own triangles and edges, each point
moved square to the pull direction by `-h * (tan(angle) - tan(lean))` (h = its height above
the hinge; OpenCASCADE sets the angle absolutely, measured: a face leaning 5 deg drafted 3 deg
ends at 3 deg). A point on two side faces (a box corner) moves so that it stays on both moved
faces; tangent faces share one move; a face beside it that is not drafted holds it on itself.
Two Side / Symmetric / a Parting Line's One Side bend the picture at the hinge (triangles cut
there). Shown in the part's colour with its edges, over the see-through part before the step,
never pickable; the preview solid is hidden meanwhile and comes back with the exact solid.
Every point of the picture lies exactly on the exact drafted solid (checked: box face, four
sides, negative angles, Two Side, Symmetric, Parting Line, pocket walls, a filleted block's
tangent chain, cylinder, ellipse and spline walls (draft_walls), a body moved and turned, an
edit from the timeline). Cost: ~0.2-0.4 ms per angle (numpy); made once per set of picks
(~10 ms for a box, ~80 ms for 8 walls of a 179-face part) while nothing happens, right after
the preview (`_live_soon`). A typed angle shows the picture at once too.

**3. Handles take every mouse move at once** (`taskui.PollOnMove`): a handle's poll ran on a
30 ms timer, so the dialog and the value box took a new value up to 30 ms (plus any rebuild)
late. Now the poll also runs right after each mouse move with a button held (an event filter
on the 3D view, at most one queued). For every dialog's handles: `taskui.ArrowDragger`,
`extrude_ui.AngleDragger` (Extrude taper, Draft, Pattern), `handles3d._Handle` (Shell, Press
Pull, Scale, Draft's pull arrow, construction planes ...), Revolve's angle, Move's triad,
the primitives' arrows, the Hole's centre.

**4. The limit search no longer freezes the dialog** (`value_limits.Background`,
`search_steps`, `Limiter.find_steps`, `LimitedValues.limit_refused_soon`): an angle past what
fits is looked for one trial build per turn of the event loop; the handle keeps moving between
the builds and the dialog says "Finding the steepest angle that fits…". The time budget counts
only the builds' time (same results as before; unit tested). OK during a search finishes it
first. Other dialogs keep the search at once (their builds are quick on the parts tested).

**5. The exact preview is cheaper**:
- `drafting.undrafted()`: 0.52 s -> ~13 ms on the 179-face part (only faces with the same box
  are measured; boxes kept per shape).
- `drafting.draft_shape()` keeps its last 8 results and refusals per (shape, faces, spec): the
  limit search's builds are not built again by the preview (SciForge's own DraftFeature).
- The scratch document's objects are never drawn (`_unseen`): in the GUI FreeCAD tessellated
  the whole part 2-3 times per trial build: one trial 0.49 s -> 0.25 s. No `.copy()` of the
  result, the base volume kept.
- The validity check of FreeCAD's Draft result (the bug above, now refused and held at the
  limit) costs ~0.15 s on 179 faces: an angle no steeper than one found sound for the same
  picks is taken as sound; OK checks what it keeps.

**6. Generally, for every dialog** (`taskui.Panel`): a dialog whose last rebuild took longer
than `SLOW_DRAG` (0.25 s) waits for the rest like Draft does, so a big part never freezes a
dragged handle; quicker dialogs keep rebuilding while dragged (Luca's Extrude request R2: "the
part grows while the button is still down"), unchanged.

**Tests**: `SciForgeTests/unit/test_draft_live_core.py` (22), GUI scenarios `draft_live`
(the picture on every case above, with real mouse drags) and `perf_draft` (the numbers);
`harness.next_step` waits while a limit search runs (`value_limits.working()`), as it waits for
a recompute.

## Measured (scenario `perf_draft`, real mouse moves every 16 ms, sandbox with software OpenGL)

Milliseconds, two runs each, old code (c59634a) and new, run one after the other on the same
loaded machine. "Freeze" = the longest time the program did not run while the mouse moved
(the handle stands still that long); with software OpenGL each frame alone costs 30-50 ms.

| What | before | after |
|---|---:|---:|
| Box: value box takes a mouse move (median) | 18-24 | 2 |
| Box: longest freeze while moving | 55-60 | 55-58 (frames only) |
| Box: live picture after a mouse move (median) | none | 26-43 |
| Box: exact solid after the mouse stops | 78-93 (built during the drag) | 211-235 (0.2 s rest + build) |
| Part (179 faces): value box takes a mouse move (median) | 26-79 | 2 |
| Part: longest freeze while moving | 657-692 | 54-55 |
| Part: live picture after a mouse move (median) | none | 14-26 |
| Part: exact solid after the mouse stops | 0-421 | 627-720 |
| Part: one exact rebuild (typed angle, with the redraw) | 821-908 | 356-364 |
| Part: one trial build of the limit search | 428-436 | 229-272 |
| Part, dragged past what fits: longest freeze while moving | 639-726 | 75-87 |
| Part, past what fits: the dialog's work per handle move (worst) | 1-2 | 2-7 |
| Part, past what fits: exact solid (held at the limit) after the mouse stops | 544-1192 | ~3550 (search in the background) |

So the handle and the box follow every move (the dialog's own work per move is 0-7 ms), the
picture shows the new angle within a frame, and nothing freezes for more than a frame. The
exact solid now comes 0.2 s after the mouse rests (on purpose); on the big part past the limit
the steepest angle is found in ~2-3 s with "Finding the steepest angle that fits…" shown and
the handle free (before, the same search froze the handle in 0.6-0.7 s pieces during the drag).
On Luca's PC with a real GPU the frames are much cheaper, so the freezes left are smaller still.
Baselines for the speed guard are in `SciForgeTests/gui/perf_baseline.json` (20 entries).

## Tests run (all passing)

- `--only base`: unit 2188 (9 skipped), golden 451 + 2 known xfail, headless AI 282 calls, docs
  runner, MCP agent, smoke, journey, restarts.
- GUI scenarios (137, run in 3 parallel shards): every `shell*`, `draft*`, `modify2*`,
  `limits*`, `undo_fast`, `extrude*`, `revolve*`, `fillet*`, `chamfer*`, `pattern*`, `hole*`,
  `primitives*`, `gaps_edit_rollback`, `construct_live`, the rollback / timeline-edit ones
  (`bodies_timeline`, `components*_marker`, `timeline_browser*`, `timeline_rolled_cut`,
  `direct_*`, `fixpattern_marker`, `inspect_qa7`, `meshinspect2_groups`, `modify_remove`,
  `polish2_timeline_groups`, `sweep_loft_qa_sweep`), `draft_live`, `perf_draft`. Two failed in
  the parallel run: `draft_live` (the limit under load was 6.9 deg: the check now takes 6-8) and
  `components2_marker` (passes alone; the old code fails it the same way under load).
- `perf_benchmark`: passes; the guard once flagged "Move, X distance" 9-13 ms vs 2.9 ms, a third
  run gave 2 ms (the old code gave 2-3 ms in the same conditions): noise.

## Open / what other dialogs need

- Only Draft has a live picture. Fillet, Chamfer, Shell, Press Pull, Extrude, Revolve, Pattern
  now take every mouse move at once (PollOnMove) and stop rebuilding between mouse moves when a
  rebuild takes longer than 0.25 s (`SLOW_DRAG`); below that they still rebuild while dragged
  (as Luca asked for Extrude). For a big part they then show the result only at pauses: each
  needs its own cheap picture (Press Pull / Shell: the moved faces; Fillet / Chamfer: the
  blend's band; Extrude: the profile swept) to feel like Draft does now.
- Their limit searches still run at once (`limit_refused`); `limit_refused_soon` is generic and
  can be wired the same way as in `draft_ui.py`.
- The validity check of FreeCAD's Draft result is skipped for angles no steeper than one found
  sound (same picks): a part that breaks at a smaller angle but not a larger one would show a
  broken preview until OK (which checks). Not seen.
- The exact rebuild of the big part still costs ~0.3 s, mostly FreeCAD tessellating the new
  solid for the view; a coarser display during the dialog would change a view property (an undo
  step), so it was left.
- Nothing measured on a real GPU (sandbox: software OpenGL).

## Review fixes (adversarial review, 13 findings; same branch)

Each finding was reproduced first with the reviewers' own scenarios (rv_live2/6/7, rv_ok,
rv_feel), then fixed, with a check that fails on the code before the fix and passes after.
New scenarios: `draft_live_fixes` (F1-F6, 2-F7) and `drag_rest` (2-F1, 2-F2, 2-F3, 2-F5,
2-F6); unit tests in `test_value_limits` (background search) and `test_draft_live_core`
(sloping tops). Both scenarios fail on 5314634 (18 of 34 checks) and pass now.

What was wrong and what changed, in plain language:

- **F1 - OK / Enter right after typing a too-steep angle did nothing.** OK started the
  search for the steepest angle in the background and then saw "no result yet". Now OK runs
  that search to its end at once (with a wait cursor), takes the angle it finds and closes in
  one press (`DraftPanel._limit_refuse`, `_accepting`). On the 179-face part this takes a few
  seconds (each trial draft ~0.3 s); on a box ~0.5 s.
- **F2 / 2-F1 - a search for an angle you had already left kept running.** Typing or
  dragging back below the nearest angle the search had found to fail now stops it at once
  (`LimitedValues._limit_stale`), and the new angle gets its exact preview at the normal pace
  (3.4 s -> 0.7 s after typing 3). What the stopped search learnt is kept: if the new angle is
  too steep too, the next search starts from there (`_limit_partial`, `find_steps(fails=)`).
  While the mouse moves with the button held, the search builds nothing (`Background(paused=)`,
  `DraftPanel._dragging`): no more 0.3-0.4 s freezes of the disc during a search.
- **F3 - the live picture was off where a drafted wall meets a sloping top that is not
  drafted** (a wedge; also a hole wall under its chamfer). The picture moved every point square
  to the pull direction and kept its height, which cannot keep a point on a sloping face; its
  outline moved half as far as its face. Now such points slide along the turned wall until they
  are back on the sloping face (`draft_live_core.slanted_cap`, `turned_row`, `slide`;
  `draft_live.Picture._cap_edges` / `_on_caps` / `_slide`). Wedge at 15 deg: 0.35 / 1.29 mm
  off -> 0.000 mm (faces and lines).
- **F4 - a live picture for picks that are refused whatever the angle.** When the refusal
  does not depend on the angle (a round face in the chain, nothing on the pull side of the
  parting line...: `drafting.angle_free`), no picture is drawn and the message stays.
- **F5 - "the largest angle that fits" changed from run to run** (6.9 / 7.6 / 7.8 deg): the
  search stopped on its 1.5 s time budget. Draft's search now runs to its end
  (`DraftPanel.LIMIT_BUDGET`, 12 s of build time at most): 7.9 deg every time, the same as OK
  finds. To keep that from taking longer, the search now tries tidy values (7.9, 8.0) when one
  lies between the two it knows: the last one that works is the answer, no extra build to check
  it (`value_limits._tidy_middle`, `_settled`): about a fifth fewer trial builds for every
  dialog's limit search, the same limits (checked on 3000 random cases against the old search).
- **F6 - wrong limit on bodies sketched on YZ / XZ** (also in c59634a). Their solid carries a
  turned Placement, and the throw-away draft used for the limit search lost it: the face was
  tilted about the wrong axis, so 60 deg was refused ("limited to 36.8"). The Placement is now
  built into the shape first (`drafting._unplaced`): 71.5 deg, as for the same box sketched on
  XY.
- **2-F2 - on a heavy part the first move of a drag froze the arrow for 0.5-1.3 s** (Press
  Pull, Extrude; also in c59634a). The dialog only knew the cost of its last rebuild, the
  cheap one when it opened (nothing built yet). Now on a part of 120 faces or more, a drag waits
  for the mouse to rest until a rebuild made during a drag has shown it is quick
  (`taskui.Panel._slow`, `_held_cost`, `_heavy_part`).
- **2-F3 - a short stop during a drag (0.2 s) started a rebuild that froze the next moves.**
  While the button stays down, the rebuild now waits 1.5 times its last cost (0.1-0.45 s)
  instead of 0.2 s (`Panel._rest_needed`, `HELD_REST*`): a hesitation of 0.32 s on the
  179-face part no longer rebuilds; a longer stop, or letting go, does.
- **2-F5 - the last result of a slow dialog came 0.2 s late after letting go.** Every drag
  handle now tells the dialog when it is let go (`taskui.handle_released`, called by
  ArrowDragger, handles3d's handles and the angle disc): the waiting rebuild runs at once.
- **2-F6 - Press Pull and Extrude rebuilt the same value again after letting go** (a second
  1.2 s freeze on the part; also in c59634a). Let go at the value of the last drag step, they
  do not take it again (`PressPullPanel._released`, `ExtrudePanel._again`).
- **2-F7 - the disc held at a limit inside its snap-to-0 zone jumped between 1.5 and 0 deg**
  (also in c59634a). The disc no longer snaps an angle the dialog put there, nor one past a
  limit the dialog holds (`AngleDragger.hold`, `_held_past`): it stays at 1.5 deg.
- **2-F4 - past the steepest angle, the held exact solid comes ~3.5-4.5 s after the mouse
  stops** (was 0.5-1.2 s in c59634a, which searched during the drag and froze the disc for it).
  Partly improved (a fifth fewer trial builds), mostly deferred: each trial draft costs ~0.25 s,
  two thirds of it the validity check of the whole solid (BRepCheck), and the search needs ~8 of
  them. Checking only the faces the draft changed would cut a failing trial from ~0.2 to
  ~0.03 s, but could miss a broken shell; running the trials on another thread is not possible
  with FreeCAD's documents. The disc and the live picture stay free meanwhile, and letting go or
  OK gives the result.

### The trade-off Luca should know about (2-F3 / 2-F5)

While the mouse button stays down, a heavy dialog now waits a little longer before it builds
the exact result (1.5 times its last rebuild, at most 0.45 s, instead of 0.2 s), so that a short
stop to look does not freeze the next moves. Letting go builds at once. So on the 179-face part
the exact result comes ~0.25 s later than before **if you stop and keep holding the button**
(Fillet ~1.0 s instead of ~0.6-0.7 s), and immediately when you let go. Draft shows its live
picture meanwhile. If this feels slow on your PC, `taskui.Panel.HELD_REST_MAX_MS` is the knob.

### Measured after the fixes (reviewers' rv_feel, same cases, sandbox, software OpenGL)

ms; "old" = c59634a, "review" = 5314634 (before these fixes), "now" = this branch. Freezes over
100 ms are counted between the press and the release (the rebuild at rest while the button is
held counts too).

| Case | freezes >100 ms old / review / now | exact result after the last move old / review / now |
|---|---|---|
| Draft box, steady | 0 / 0 / 0 | 99 / 239 / 227 |
| Draft 179-face part, steady | 16 / 3 / 2 | 594 / 663 / 842 |
| Draft part, hesitant (0.32 s stops) | 14 / 10 / 2 | 558 / 437 / 706 |
| Draft part, past the limit and back | 44 / 13 / 5 | 643 / 471 / 753 |
| Draft part, past the limit, quickly back (2-F1) | 23 / 10 / 3 (longest 577 / 403 / 202) | 629 / 342 / 795 |
| Draft 270-face part, hesitant | 15 / 8 / 2 | 1096 / 654 / 879 |
| Draft hole walls, past the limit (2-F4) | 15 / 2 / 2 | 1326 / 3676 / 2863 |
| Draft hole walls, held at 1.5 deg and dragged on (2-F7) | 39 / 0 / 0 | stays at 1.5 deg (was 1.5 / 0 / 0 ...) |
| Press Pull part, steady (2-F2) | 21 / 3 / 1 (no rebuild while moving; was 1.3 s at the press) | 1193 / 1418 / 1490 |
| Press Pull part, hesitant | 29 / 9 / 1 | 3050 / 1437 / 1746 |
| Extrude part, steady | 13 / 10 / 5 | 1284 / 1497 / 693 |
| Fillet part, hesitant | 33 / 15 / 2 | 611 / 700 / 1006 |
| Chamfer part, hesitant | 33 / 14 / 2 | 641 / 773 / 996 |

Other numbers: OK right after typing 15 deg on the part closes at once at 7.9 deg in 4-5 s (wait
cursor; before: 0.6 s and the dialog stayed open); typing 3 during a search: exact preview after
0.7 s (was 3.4 s); the limit on the part is 7.9 deg in every run; the wedge picture is 0.000 mm
off (was 0.35 / 1.29 mm). perf_draft: box exact after the mouse stops 218 ms (baseline 235); part
816 ms (627, the longer held rest); part past the limit 4.8 s (3.6 s: the held rest plus a search
that now runs to its end); longest freeze while moving 41 / 57 / 86 ms.

Still open (seen, not part of the review): Extrude's arrow on the 179-face part still stalls
0.27-0.32 s on some moves without any rebuild (its snap to faces under the mouse, a pick per
move); a Draft of a box's front face whose top edge is chamfered is refused at every angle
(FreeCAD's Draft next to a sloping face; c59634a showed a broken solid instead); the docs runner
compares the drawing title block's date, so `get_drawing#1` fails on any day after the recording
day (2026-10-23: "-22 is now -23"), unrelated to Draft.

### Tests run for the fixes (all passing)

- Unit: 2198 (9 skipped), including `test_value_limits` (40) and `test_draft_live_core` (26).
- `--only base`: golden 451 + 2 known xfail, headless AI 282 calls, MCP agent 81 checks, smoke,
  journey, restarts; docs runner 140 / 141 (the date one above, not related).
- The whole GUI suite (427 scenarios, 3 parallel shards): 409 passed in the shards; the 18 that
  failed (17 in one shard whose clicks landed off target from the first sketch scenario on:
  sketch_*, primitives_box, misc_decal...; and limits_extrude_other, a real one, fixed: a
  release that rebuilds nothing still shows the limit hint) all pass when run again. Then every
  extrude*, presspull, limits* scenario again on the final code (34): pass.
- `draft_live_fixes` (23 checks), `drag_rest` (11), `draft_live` (125), `perf_draft` (19),
  `perf_benchmark` (no measurement over 2x its baseline), `limits_shell_draft`, `draft_curved`,
  `shell_draft_qa_draft`.
