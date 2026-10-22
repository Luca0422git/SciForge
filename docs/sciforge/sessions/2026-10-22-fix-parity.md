# Session notes: fixes after the review of the parity script and work list (`fix/parity`)

Branch `fix/parity`, from `integration` at 3e515b5 (experimental + the nine feature branches
of 2026-10-22). An adversarial review of item 5 (the parity script, core-workflows.md,
remaining-gaps.md) found nine problems, P1 to P9. Each was reproduced on this branch before
it was fixed. MEMORY.md was not edited (other agents work in parallel); merge these notes
into it.

## In plain words (for Luca)

- **The drawing did not follow an Undo (P1, a real bug).** Make a drawing, change a fillet in
  the design (the drawing follows), go back and press Ctrl+Z: the part was right again but the
  drawing still showed the changed fillet. The faster Undo from the big-design speed work
  (`undo_fast.py`) skips the rebuild when FreeCAD has already put every shape back, and a
  drawing's views keep no shape in the undo history, so nobody told them. Now, after such an
  Undo or Redo, the things built on the design that keep no shape (the drawing's views,
  dimensions, the page) are recomputed on their own; the design itself is still not rebuilt,
  so Undo stays fast.
- **The work list missed about 30 Fusion entries (P2).** Hole Table, Renumber, Align Balloons,
  Export CSV, Save As Latest, AutoConstrain, Fix/Unfix and others were on the checklist's "not
  in SciForge yet" list but on no row of `remaining-gaps.md`. They now have rows (G-85 to
  G-92, or a few more words in G-35, G-40, G-41, G-42, G-59, G-62, G-66, G-71), and a unit
  test fails whenever an entry of that list is on no row.
- **Two gaps were already fixed (P3).** Editing a pattern or an older revolve from the
  timeline does roll the design back to it, as in Fusion (a new test shows it:
  `gaps_edit_rollback.py`). G-08 is closed; G-07 is narrowed to what is really left (a
  double-click on the part in the 3D view opens the dialog without rolling back) and moved
  down to Low.
- **The workflow page was stale (P4) and too kind (P5).** It still listed two sketch gaps
  closed the same day, and it gave the sketch workflow "yes" although the work list says
  projected edges (G-02) get in the way. Workflow 1 is now **partly**, because of G-02, with
  the reason written out. A unit test fails when the page names a gap that is no longer
  open.
- **The parity script (P6 to P9):** it no longer rewrites the date when nothing changed (two
  branches regenerating on different days conflicted on that line); a checklist it cannot
  write gives a `[SciForge]` line and exit 2 instead of a Python traceback; a
  `fusion-menus.txt` saved by Notepad "with BOM" is read normally; a command found in another
  panel of the tab (Fusion's CREATE > New Component is SciForge's ASSEMBLE > New Component) is
  listed under "Present in another place", and one SciForge entry that counts for several
  Fusion entries (one sketch Chamfer for Fusion's three) is listed in a new section. The
  headline is unchanged: 457 / 631.

## What changed

| Finding | Fix | Test |
|---|---|---|
| P1 drawing stale after Ctrl+Z | `undo_fast.settle_without_rebuild`: after purging the design's touched marks, recompute only the objects built on the touched ones that have no Shape and feed no Shape (`followers()`, pure and unit tested; `_dependents()` reads FreeCAD's InListRecursive) | `drawing_update.py` failed before (3 checks), passes after, and now also checks the undo skipped the rebuild and recomputed the drawing; `test_undo_fast.FollowersTest` |
| P2 entries missing from the work list | rows G-85 to G-92, words added to G-35, G-40, G-41, G-42, G-59, G-62, G-66, G-71; the header's promise rewritten | `test_parity.TestRealMenus.test_every_missing_entry_is_on_the_work_list` (fails on the old list: 39 entries named nowhere, a few of them only worded differently, such as Soft Light under "lit environments"; it matches names as text, so a common word such as Move or Open can pass by chance) |
| P3 G-07 / G-08 already work from the timeline | G-08 closed, G-07 narrowed to the 3D-view double-click (Low), list re-ranked | `gaps_edit_rollback.py` (a pattern with real clicks, an older revolve): both roll back |
| P4 core-workflows.md names closed gaps | G-03 / G-06 removed from workflow 1, `sketch_explain.py` added as evidence; rule: a commit closing a gap updates this page | `test_parity.TestRealMenus.test_core_workflows_names_only_open_gaps` (fails on the old page: G-03, G-06, G-08) |
| P5 workflow 1 "yes" vs G-02 High | workflow 1 is **partly** (G-02 is a workaround in normal sketching) | documentation only |
| P6 date rewritten on every run | write mode keeps the file (and its date) when only the date would change | `test_writing_an_unchanged_checklist_keeps_its_date` |
| P7 traceback when the checklist cannot be written | `[SciForge] parity: could not write <path>: <reason>`, exit 2 | `test_a_checklist_that_cannot_be_written_is_reported_not_raised` |
| P8 BOM in fusion-menus.txt | read with `utf-8-sig` (both data files) | `test_a_byte_order_mark_is_ignored` |
| P9 cross-panel and shared matches | a ribbon command is looked for in its own panel first; found in another panel of the tab it is "elsewhere" (still counted, now listed); new checklist section "One SciForge entry for several Fusion entries"; the headline note says both | `test_another_panel_of_the_tab_is_elsewhere_and_shared_entries_are_listed` |

The AI copies of the three docs (`src/Mod/SciForge/docs/ai/user/...`) were regenerated with
`python3 tools/sciforge/make_ai_docs.py`.

## Decisions and things found

- `followers()` leaves alone an object without a Shape that a shape is built on (a
  spreadsheet a feature reads): recomputing it would mark the design touched again. Such an
  object only changes after an Undo when it reads the design itself, which is rare.
- A component (App::Part) and a linked copy have no Shape property either, so they are
  recomputed after such an Undo too; both recompute in no time.
- G-07: the 3D-view double-click goes to each view provider's `doubleClicked`, which calls
  its module's `edit()` directly instead of `taskui.edit_object`. Routing them all through
  `edit_object` would close G-07; not done here (about 15 view providers, and it nearly always
  opens the last step, where nothing is rolled away).

## Tests run

See the report of this session (the run results are in the commit that adds this file).
