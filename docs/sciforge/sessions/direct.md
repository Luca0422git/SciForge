# Session log: direct modeling and the remaining Modify tools (branch `sf/direct`)

### 2026-10-13: Capture Design History, base features, solids without history, Replace Face, Split Face, Silhouette Split, Align, Remove (outline 7.13, 7.3, 7.7)

- Everything is on `sf/direct` (not pushed, not merged). No FreeCAD core file changed (no
  entry in `core-patches.md`). Behaviour spec with sources at the top of
  `docs/sciforge/parity/direct-modify.md`; what SciForge does and the known gaps at its end.
- **The model** (explained there): bodies stay PartDesign Bodies in both modes. A body without
  history is one frozen step (`PartDesign::FeatureBase`) fed by a hidden plain `Part::Feature`
  "base shape" that lives in the body's component. A design without history bakes every
  command at OK inside the command's own undo step (`direct.takes_commit` from
  `preview.end_transaction`, `taskui._end_transaction`, `delete.run`); a FreeCAD command
  that commits by itself is baked as its own undo step (`direct_ui.DocWatch`). The setting is
  a hidden `App::FeaturePython` "SciForgeDesign" (undoable, unlike `Document.Meta`).
- **Built**: Capture Design History on/off (the design's browser menu and the timeline's
  settings menu; a question first; the timeline hides; Undo / Redo; save / reopen); Create
  Base Feature + Finish Base Feature (a bar over the view, also in SOLID > CREATE); editing a
  base feature from the timeline (rolled back meanwhile, Finish puts the marker back);
  Press Pull / Offset Face (new, MODIFY > Offset Face) / Delete on plain solids (STEP files
  FreeCAD opened, converted meshes): the solid becomes a body built on it; Delete heals with
  OpenCASCADE's defeaturing and says why when it cannot; Replace Face; Split Face (three
  split types, Extend); Silhouette Split (three operations); Align (Bodies / Components,
  Flip, Angle; its "A" key moved to Appearance as in Fusion); Remove (MODIFY > Remove, the
  browser menus, a timeline step).
- **Tests**: unit `test_direct_core.py`, `test_align_core.py`, `test_direct_schema.py`; 13
  golden models `direct_*.json` (analytic); 10 scenarios with real input: `direct_history`,
  `direct_step_box`, `direct_base_feature`, `direct_components`, `direct_commands`,
  `modify_replace_face`, `modify_split_face`, `modify_silhouette`, `modify_align`,
  `modify_remove`. Results of the last run are in the report of this branch (see below).
- **Bugs the scenarios found (fixed)**: the origin squares' "ignore the click that went
  through to the part" window also ate a quick next click (now only the same mouse press);
  a ball's face was taken as a direction (its axis is arbitrary); history off / a base
  feature brought back bodies a Combine or a Remove had used up; editing a Remove did not
  show a body it no longer removes; Split Shelled Body refused a shelled cup (one shell like
  any solid); Split Face with a body as tool used the body's frame, not the design's.
- **FreeCAD facts / traps learned**:
  - A body inside an `App::Part` may only link objects of that part ("Link(s) ... go out of
    the allowed scope"): the base shape is moved into the body's component (`direct.rehome`).
  - `Document.Meta` is not undone by Ctrl+Z; a property of a document object is.
  - `doc.commitTransaction()` only closes a transaction that holds changes; and a dialog
    still reads its feature right after OK, so the bake + commit is deferred one event-loop
    turn (QTimer) and flushed by `commands.finish_open_dialog` before the next command.
  - `body.Shape` leaves out the placement of the component the body is in;
    `bodies.global_shape(body)` therefore does too (feature shapes are fine). Suggested as a
    separate task.
  - `Shape.reflectLines(dir, center, up, "OutLine", True, True)` gives only the visible
    outline; a polyhedron's outline is its own edges (nothing to split).
  - `Shape.defeaturing()` gives the solid back unchanged (no exception) when the gap cannot
    close: compare face count and volume.
  - FreeCAD's STEP import makes plain `Part::Feature` solids named after the translator;
    the timeline lists them until edited.
  - Scenario trap: with a small active body the origin squares are small, and a click meant
    for the XY square can hit the XZ square (the sketch then stands upright).
  - Scenario trap: the timeline numbers steps of a kind in order: after deleting "Remove 1"
    the next one is shown as "Remove 1".
- **Gaps** (details and reasons in the parity doc): one Base Feature item per body (Fusion:
  one for all); no "pseudo features" in a direct design's browser; no Press Pull Offset Type
  choice; bodies made before an open base feature can still be changed (recorded as steps);
  saving with a base feature open keeps the marker rolled back; Replace Face onto free-form
  surfaces; Split Face edges can be merged by later refining steps; Silhouette's hidden
  inner outlines; a removed component keeps its browser row; STEP files open into the
  current design (not as a design without history).
- **What next**: Luca checks the Guess rows in his Fusion (the "Finish Base Feature" place,
  Align's face-facing rule, Split Shelled Body on a solid); timeline grouping of one base
  feature id into one item; the `global_shape` fix (separate task).
