# Session log: Draft angle in real time (branch `wf/draft-live`)

To be copied into MEMORY.md by whoever merges (this branch does not edit MEMORY.md). Started
from `experimental` (c59634a). No FreeCAD core file changed (nothing for `core-patches.md`).

Luca, on his Windows PC with a real GPU: "Draft is still extremely slow. The whole point of
being able to drag the angle of a draft is to see it update in real time. I can barely call it
real time. And the angle dragger doesn't even update either: it waits behind for the model to
update. It takes at least 1-3 seconds to update. Make it faster."

STATUS: work in progress (this file is kept current; see "State" at the end).

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

## State

- Built: live picture (draft_live.py, draft_live_core.py), preview waits for the mouse to rest
  (taskui.Panel.schedule settle / SLOW_DRAG), handles polled on every mouse move
  (taskui.PollOnMove), limit search in the background (value_limits.Background), faster
  undrafted(), result cache, scratch objects never drawn, validity check.
- Tests passing so far: perf_draft, limits_shell_draft, draft_curved, shell_draft_qa_draft.
- To do: unit test of draft_live_core, GUI scenario draft_live (picture checks), baselines,
  the full list of related scenarios, --only base.
