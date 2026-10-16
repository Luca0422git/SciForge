# Session log: Polish, part 2 (branch `sf/polish-2`, wave 5, 2026-10-16)

Brief: `docs/sciforge/dev/briefs/polish-2.md` (+ `common.md`). Relaunch: the first polish-2
builder was stopped by the usage limit before committing; this run started from 2273d4e0ab
(Luca's four bug fixes merged). Specs with sources (Autodesk / Forum / Guess) and gaps:
`parity/extrude-presspull.md` (value boxes, top section), `parity/sketch.md` (the floating
green check), `parity/timeline-browser.md` (groups), `parity/versions.md` (milestones,
closing, Move / Copy, out of date, last section), `parity/misc.md` (Derive with structure
and versions, Preferences), `parity/ui-shell.md` (a stale gap). No core patch: no full
build needed.

## What was built

1. **Value boxes on every handle that had none.** Move's triad carries one box beside the
   handle in use (last dragged or under the mouse): X / Y / Z Distance on an arrow, X / Y / Z
   Angle on a turn handle, Pivot X / Y / Z while Set Pivot moves it; Rotate's turning handle
   shows the Angle (`move_ui.Triad` is a `taskui.BoxCarrier` now; Components' Move shares it,
   and Insert Mesh's manipulator, the same triad, got the box of its X / Y / Z fields too).
   Scale's arrows (factor / X, Y, Z Scale), Draft's angle disc, Construct's handles
   (offset, angle, along a path: the distance or the fraction), Section Analysis' three
   handles and Sweep's distance balls (`curve_pick.PathHandle` is a BoxCarrier now). Digits
   typed over the view go into the box of the handle in use. Two general improvements in
   `taskui`: `BoxCarrier.box_avoid()` (the triad's box never covers its other arrows and
   balls) and `ArrowValueBox._covered()` (no box lands under FreeCAD's floating command
   dialog over the right of the view, where it was hidden before).
2. **Fusion's floating green check** (`sketch_check.py`, hooked in `sketch_mode`): beside
   the point a line chain goes on from; a click ends the chain and the Line tool stays on.
   The splines show it once they have two points (a click makes the spline, the tool stays
   on). Follows zoom / orbit, never takes the keyboard, goes with Esc / Finish Sketch.
3. **Timeline groups**: a group's folder can be dragged (open or closed): its steps move
   together, keep their order and group, each into its own body (`timeline_core.
   plan_group_move`, `_block_keys`, `timeline_ops.move_group`, `timeline_ui._GroupButton`).
   Refused with the reason like a step (dependencies either way), into another group, or
   with the marker inside. A group holding the marker stays open (Collapse greyed, a click
   says why); the group menu has Roll History Marker Here. Esc drops a folder drag.
4. **Versions**: Milestones (Save dialog box; Version History column, Mark / Remove,
   Milestones only; Data Panel > Milestones; git tags `sciforge-milestone-<commit>`, plain
   `index.json`). Automatic version on close (Preferences > General, on by default like
   Fusion) and the Close dialog (Save with a description / Don't Save / Cancel; a design never
   saved goes through the Save dialog; quitting asks about each changed design). Data Panel
   Move... / Copy... (folder list + New Folder): a moved design keeps its versions (git mv +
   a "[SciForge] moved" commit that `GitStore._log` follows back; plain version folders
   move along) and its own links / Derives plus the project designs that insert or derive it
   are rewritten to the new place (`versions.retarget_xml`); a copy is a separate design at
   v1. Rename now keeps git versions and the users' links too. The Out-of-Date button in the
   application bar (`ribbon_ui`): an inserted design saved again (saved date in the file !=
   the one read), a Derive's source newer, or an older version open; its menu: Get Latest /
   Open the Newest Version.
5. **Derive**: a ticked component comes in as a component with its bodies and nested
   components (`derive_core.expand`, `derive._build_components`), updates bring bodies added
   to it in the source, unticking removes the whole derived component. A Version choice in
   the Derive dialog (Latest or any saved version, milestones marked): an older version is
   flagged out of date at once; Update Derive takes the newest.
6. The "Extrude rolled back before a fillet cannot switch to Cut" gap of
   timeline-browser.md was already fixed (commit 27d4492778, scenario `timeline_rolled_cut`);
   the doc said otherwise and is corrected, as is ui-shell.md's stale timeline gap.

## FreeCAD facts and traps found

- `App.closeDocument()` closes the views through `MDIView::deleteSelf` → the sub-window's
  `close()`, so a Qt `Close` event reaches the view widget for closes from code too; by then
  `Gui.getDocument(name)` already raises "Unknown document". A close watch must treat that
  as "closed from code, nothing to ask" (versions_ui `_doc_of_view`), never print a warning.
- `View3DInventorPy.graphicsView()` gives the viewer widget inside an MDI view: the way to
  map a view widget (or a `QMdiSubWindow`) to its document.
- `Document.restore()` reads a document again from its file; `App::Link`s into it follow at
  once (checked on a hidden document loaded for links): Get Latest of an inserted design.
- `git log --follow` follows copies, not only renames (git's rename following turns on
  find-copies-harder): a copied design with the same content would have taken the
  original's versions. SciForge follows only its own move commits (`GitStore._moved_from`).
- FreeCAD's floating Tasks panel (`Gui::OverlayTabWidget`) lies over the 3D view: children of
  the GL widget under it (value boxes) are hidden, and a click there goes to the panel.
- Enter in a value box takes the value and finishes the command (OK); Tab or a click
  elsewhere only takes it. Tests that keep the dialog open must leave the box with Tab.
- QTest: a click in the middle of a wide `QCheckBox` misses (only its box and text count);
  a key sent with `QTest.keyClick(gl, ...)` goes to the GL widget even after a value box took
  the keyboard (a real keyboard sends it to the focus widget).

## Tests

New scenarios (all pass, real input only):

| Scenario | Checks | Paths |
|---|---|---|
| `polish2_value_boxes` | 62 | Move: the box beside the X arrow under the mouse, following a drag, 25 typed in it; the box moving to the Z arrow, digits typed over the view going into it; Z Angle on a turn handle, 90 + Enter (value and OK), undo / redo; Scale's factor typed at its arrow, Esc; Draft's angle typed at its disc, Cancel; Insert Mesh's Z arrow box, 7 typed, Cancel |
| `polish2_sketch_check` | 101 | the check beside a line chain's end, on top of the view; it follows a zoom; a click ends the chain (the Line tool stays on, two clicks make a separate line), undo; Esc takes it away; a spline's check after its points makes the spline; none left after Finish Sketch |
| `polish2_timeline_groups` | 49 | a group's folder dragged before an earlier step (undo / redo), refused with the reason, the marker inside a group (Collapse greyed, a drag refused), Roll History Marker Here, Esc during a drag, rename, ungroup + undo, save / reopen |
| `polish2_versions` | 67 | a milestone ticked in the Save dialog, Version History's mark / Mark / Remove / Milestones only, a milestone opened read-only; the automatic version on close; with it off the Close dialog (Cancel, a description, Don't Save); a design never saved goes through the Save dialog; quitting asks first |
| `polish2_data_panel` | 38 | Move... into Parts (versions kept, the inserting design's link rewritten, moving again refused); Copy... (a separate design at v1, a second copy "Wheel 2"); Move refused while a user is open; the Out-of-Date button for an inserted design saved again, Get Latest; an older version open, Open the Newest Version |
| `polish2_derive` | 55 | a component derived with its structure (Hand inside Arm, at their places), Version v1: out of date at once, Update Derive + undo / redo, a body added in the source comes in, untick / tick, save / reopen |

Regressions run after the last change (all pass): bodies_move 85,
extrude_feel_box 108, fixdecal_body_move 132, fixsketch_move 71,
inspect_construct_axes 61, inspect_construct_planes 85, inspect_section 82, modify2_draft 72,
modify2_scale 56, shell_draft_draft 81, shell_draft_scale 80, sweep_loft_sweep 72,
value_box_dialogs 62, value_box_dialogs_2 67, value_box_units 8; fixpattern_circ 160,
fixpattern_marker 54, fixpattern_mirror 159, fixpattern_old_file 110, fixpattern_path 162,
fixpattern_rect 185, fixsketch_fillet 72, fixsketch_hole 65, fixsketch_join 89,
fixsketch_presspull 93, fixsketch_shell_draft 66, misc_derive 76, timeline_browser 92,
timeline_browser_2 133, timeline_browser_qa 222, timeline_browser_qa2 245,
timeline_browser_qa3 239, timeline_browser_qa4 280, timeline_roll_view 6,
timeline_rolled_cut 64, versions_data_panel 30, versions_link 22, versions_recovery 55,
versions_save 69; misc_preferences 84, sketch_dim_box_closes 35, sketch_draw 134,
sketch_end_line 52, sketch_infer 223, sketch_infer_tools 162, sketch_polygon 90, sketch_qa 457,
sketch_qa_keys 119, sketch_tangent_arc 102, sketch_tools_audit 99, sketch_tools_draw 151,
sketch_tools_slots 97; components2_copy 277, components2_move 344, drag_release_lost 102,
gaps_offset_plane_to 38, insert_canvas 48, insert_dxf 35, insert_mesh 65, insert_svg 38,
inspect_construct 68, inspect_construct_use 48, modify2_move_face 56, sweep_loft_sweep_rail 46.

`--only base`: unit tests 1143 OK (1 skipped; new: `GroupMoveTests` in timeline_core,
`MilestoneTests` and `MoveCopyTests` in versions, Derive's `expand` / version words and the
Preferences entry in misc cores), golden models 403 pass + the known xfail
`plate_hole_grid`, smoke and journey pass. (The container restarted once during the last
regression run; the scenarios it had not reached were run again afterwards.)

## Not built (and why)

- Move / Copy of whole folders and dragging cards onto folders in the Data Panel (Move... /
  Copy... cover designs); Fusion's per-reference Get Latest Version (Get Latest takes all).
- FreeCAD's own Close All Documents still asks FreeCAD's question (its Save makes a version
  all the same).
- A check for SciForge's own fixed-step sketch tools (they end after their last click).
- Dropping a step into a group by dragging stays possible (Fusion has none) and groups do not
  nest.
- Derive: sheet-metal flat patterns and feature parameters "From Components" (SciForge has
  neither); Fusion picks a reference's version from the Data Panel, SciForge in the dialog.
- Floating dialogs and document tabs at the top stay out of this wave (brief).
