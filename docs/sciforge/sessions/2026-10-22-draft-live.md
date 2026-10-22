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

## What changed

TODO: filled in at the end.

## State

- Built: live picture (draft_live.py, draft_live_core.py), preview waits for the mouse to rest
  (taskui.Panel.schedule settle / SLOW_DRAG), handles polled on every mouse move
  (taskui.PollOnMove), limit search in the background (value_limits.Background), faster
  undrafted(), result cache, scratch objects never drawn, validity check.
- Tests passing so far: perf_draft, limits_shell_draft, draft_curved, shell_draft_qa_draft.
- To do: unit test of draft_live_core, GUI scenario draft_live (picture checks), baselines,
  the full list of related scenarios, --only base.
