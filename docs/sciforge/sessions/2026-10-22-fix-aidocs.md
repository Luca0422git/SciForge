# Session log: fixes from the review of the AI documentation (branch `fix/aidocs`)

To be copied into MEMORY.md by whoever merges (this branch does not edit MEMORY.md). Started
from `integration` (3e515b5). An adversarial reviewer checked item 3 (AI documentation,
docs_search / docs_read / examples_search) and found 9 problems; each was reproduced in real
FreeCAD before it was fixed. No FreeCAD core file changed (nothing for `core-patches.md`).

## What was wrong and what changed (plain language)

- **F1, M8 holes came out as M6 holes.** `hole` with `size: "8"` (as the reference page and
  the flange recipe say) built a 6.6 mm hole, the M6 clearance size, and answered "Done". The
  hole code looks up the thread designation first, and that was always the default "M6x1".
  Now `size` picks its designation (coarse thread, as the dialog does), "M8" works too, a
  `designation` sets the size, and an unknown size is refused with the list of sizes
  (`sciforge/ai/ops/hole_ops.py`). The flange recipe runs the M8 call and checks the volume.
- **F2, show_hide and activate are not undo steps.** What is shown and which body is active
  are not recorded by FreeCAD, so `undo` after them took back the step before (a fillet). The
  pages, the handbook, the tool descriptions and the chat prompt now say so, and tell the AI
  to call them again instead. Found on the way: show_hide left an empty undo step *open*, and
  the next change made outside a tool landed in it; the executor now closes it.
- **F3, Undo last AI step refused after timeline tools.** suppress / roll / move / delete /
  rename / group / capture history opened undo steps with their own names ("Suppress Fillet
  1"), so the AI panel's button said "The last step was not made by an AI app". While an AI
  call runs, these steps are now named after the call ("AI: Suppress"), as the pages said
  (`timeline_ops.undo_title`, also used by `direct.py` and `delete.py`). group_steps is one
  undo step (the name goes in with the group).
- **F4, documented defaults that were not the real ones.** hole: `drill_point` is flat in
  every case now (it became a 118 degree cone as soon as a dialog option was given), and a
  tapped hole needs a depth like every hole (it was 10 mm, silently). circular_pattern:
  quantity 3 when left out, as the page and the Circular Pattern dialog say (it was 2).
  pattern_on_path quantity 2, rectangular_pattern / pattern_on_path distance 20 and
  insert_hardware sink_head (true, false for button heads) are now documented as they are.
- **F5, docs_search.** A section that many pages have word for word (every reference page's
  "Answer") is indexed once and weighted down, so the troubleshooting section comes first for
  the warnings SciForge prints; `user/` (Luca's documents about the dialogs) weighs less than
  the AI's own pages; the size troubleshooting heading names "radius too big ... the largest
  that fits"; an unknown `scope` is told (and "handbook" means handbook.md).
- **F6, one direction rule for holes.** A hole from a sketch under the part now drills up into
  it on every path, like Fusion and the Hole dialog (the plain path drilled away and changed
  nothing). `flip: true` means "along the sketch's normal". Troubleshooting, handbook, knob
  recipe and the "no solid changed" warning were rewritten to match.
- **F7, links.** The hand-written pages link tools as `sciforge://docs/reference/<tool>.md`;
  docs_read also reads `sciforge://tools/<tool>` (its page), `sciforge://tools` (tools.md) and
  `sciforge://handbook` (the list of documents).
- **F8, small untrue statements** fixed: sketch_polygon's point (middle of an edge by
  default), drive_joint's example joint id ("Joint"), the sketch help no longer says "prefer an
  origin plane" against the handbook, a dimension's value is "mm or deg", the surface patch
  bulges to 14.8 mm (now checked by the recipe).
- **F9, Save AI handbook...** writes the compact file (about 44,000 tokens) to load and, next
  to it, the one with every tool page (about 170,000 tokens); the dialog gives both sizes in
  tokens and says the big one would fill most of a 200,000 token project. The MCP handbook
  resources give their size in tokens too.

## Tests added

- `SciForgeTests/unit/test_ai_docs_review.py` (search, links, pages, hole mapping, tokens; all
  12 fail on `integration`).
- `SciForgeTests/docs/doc_promises.py`, run by `docs_runner.run_promises` (hole sizes, hole
  defaults, pattern defaults, documentation links) in real FreeCAD.
- docs_runner checks every call of every document and example: at most one new undo step,
  named "AI: ...", none for failed calls and for show_hide / activate, and no undo step left
  open. It found two more: `delete_bodies` made a step named "Delete", and an `edit_step`
  that failed with "Largest radius that fits here" still left an empty "AI: Edit Fillet1"
  step (also on `integration`), so the AI's next `undo` did nothing visible. Both fixed: the
  executor now closes a transaction FreeCAD left open right after commit / abort (aborted when
  the call failed), before the recompute and the value search can land in it.
- GUI scenario `ai_undo_steps` (Undo last AI step after suppress and roll, group is one step,
  show_hide leaves nothing open); `ai_docs_gui` checks the two handbook files and the sizes.

## Test runs

`run_tests.sh --only base`: all passed (unit 2103, golden 451 pass + 2 known xfail, headless
202 calls, docs 141 items / 924 calls, agent 70 checks, smoke, journey, restart). Scenarios
ai_undo_steps, ai_docs_gui, ai_tools_gui, ai_bridge, ai_chat, ai_panel, ai_agent_e2e,
direct_commands, direct_components, direct_step_box, modify_remove, misc_preferences: all
passed.

## Left as it was

- `reference/docs_search.md` still ranks for queries that match its own example queries
  ("shell remove top face" puts it second): minor.
- The Fusion dialog's 118 degree drill point stays the default of the Hole dialog and of the
  golden models' `hole_at` / `hole_points` steps; only the AI tool defaults to flat, as its
  page always said.
