# Session log: journey-surface, a whole SURFACE part across the wave 6 tools (branch `sf/journey-sf`, 2026-10-23)

An end-to-end test of the SURFACE tab after the wave 6 merge (`wave6-integration`): one
hybrid part built the way a Fusion user builds it, with real clicks and keys, checked on the
model after every step (volumes, areas, face counts, bounding boxes, timeline names, states).

## The scenarios

| Scenario | What it builds | Checks |
|---|---|---|
| `journey_surface` | Create Sketch on the YZ square (a slanted line), SOLID Box by clicks (40 x 30, Height 20), SURFACE Extrude of the line Two Sides 45 / 5 across the box, Split Body of the box by it (9600 / 14400), SURFACE Delete of the upper piece's top (a surface body, no healing), Fillet r 3 and Chamfer 2 of two of its vertical edges (areas worked out over the slanted floor), Patch of the rim with Group Edges off (6 Continuity rows; Tangent onto the vertical walls refused with the reason, back to Connected), Stitch of the piece and the lid with Operation Join into the lower piece (24000 less the round and the bevel), SOLID Delete of the bevel (alone: refused with the reason; with the sliver it left: healed), Extrude 1 edited to Symmetric (the split follows), Box 1 edited to 25 high (every later step follows: 30000 less the round corner), Undo / Redo, Ctrl+S, close, reopen, the Patch edited after the reopen | 123 |
| `journey_surface2` | A slanted surface (Extrude 1); Offset Sharp 3 above it, Trim by a sketch line (the piece at x < 0 removed), Extend Natural 5 at the far edge, Press Pull 2, Mirror with Operation Join on the YZ square (stitched: 2 faces, one shell), Merge of the two faces (one face), Environmental Map Analysis on it, Thicken 2 (a plate of 200 W); Extrude 1 edited to Distance 55 (every later step follows: 240 W), Undo / Redo, save, close, reopen (the analysis too); Extrude 1 edited to One Side: the Trim cannot cut any more, it turns red with the reason, Ctrl+Z puts all back (the red step says why in words) | 92 |
| `journey_surface3` | A Loft between two sketch lines across a box (area by integration), Split Body (11400 / 12600), Thicken 1 of the loft, the loft edited (Last Profile Direction 30: the split and the Thicken follow, the pieces still make 24000), the box's Extrude edited to 3 high (the loft no longer reaches it: the Split Body turns red with "does not cut the body in two"), Ctrl+Z, save, close, reopen (Direction kept) | 53 |

Run: `LC_COLLATE=C tools/sciforge/run_tests.sh --freecad <FC> --out <OUT> --scenario journey_surface` (and 2, 3).

Re-run after the fixes (all PASS): unit tests (1995), `bodies_qa`, `bodies_qa_2`,
`bodies_split`, `bodies_timeline`, `components2_bodies`, `direct_components`,
`direct_history`, `direct_step_box`, `extrude_multibody`, `extrude_multibody_move`,
`modify2_bodies`, `modify_remove`, `split_preview`, `surface4_delete_merge`, `surface4_split`,
`surface4_split_loft`, `timeline_rolled_cut`. `extrude_multibody_edit` fails one timing
check ("E: the drag answered quickly", 11 to 13 s for 8 allowed) on this shared machine with
and without these changes (run alone on the `wave6-integration` extrude_bodies.py: 11.06 s);
its other 137 checks pass.

## Bugs found and fixed

1. **Editing a body's first Extrude after a Split Body was refused** ("Bodies to Join is
   empty. Click it, then click a body to take it back.", no preview, OK refused). The piece
   split off later lives in a body whose first steps (the hidden `SplitPiece` and the body's
   `PartDesign::FeatureBase` holding it) are not timeline items, so `extrude_bodies.step_times`
   gave them no place and `place_in` counted them as older than every step: the later piece was
   "in the way" of the box's own first Extrude, and as it was not in the extrude's saved list it
   was left out, leaving the list empty. Fix: a split-off piece takes the place of its Split
   Body, and a FeatureBase the place of the step it holds (`sciforge/extrude_bodies.py`). Seen
   on an extrude saved with Operation Join as a body's first step (what `extrude.make` makes
   without an operation: golden models, the AI ops); the same rule keeps later split bodies out
   of Revolve / Sweep / Fillet bodies-in-the-way when an earlier step is edited.
2. **SOLID Delete said the wrong reason for a bevel it could not heal.** The bevel's foot met a
   sliver of another face (the lower piece's slanted top the bevel left uncovered); healing the
   bevel alone would have to make that sliver vanish, which OpenCASCADE's defeaturing never does.
   The refusal said "Its neighbours run parallel or away from each other", false for a bevel
   whose walls lean over it. Now a lone flat face with a flat neighbour leaning over it
   (`delete._neighbours_turn`) is told a face beside it would have to disappear too and to
   Ctrl+click it with the face (`direct_core.delete_refusal(..., neighbours_turn)`, unit
   tested). Ctrl+clicking the sliver with the bevel heals both (the scenario does it).

## Worked around / noted (not bugs of this pass)

- After an edit makes a later step fail (the Trim, the Split Body above), the failed step is
  red with its reason, but its body keeps showing the step's last good shape (FreeCAD keeps a
  failed feature's previous Shape) and the steps after it keep theirs, not red (in
  `journey_surface2` only the Trim is red; the Extend .. Thicken after it stay as they were);
  Fusion shows the model as computed up to the failure. Both scenarios check the red state,
  that the reason is in words, that nothing new is built from it, and Ctrl+Z.
- A step that fails in a recompute writes FreeCAD's error lines to the Report view; the
  scenarios read them away in the step that causes them (`h.new_errors()`).
- The harness counts any Report line with "failed" as an error, the step names printed by the
  harness included: a step must not be called `..._failed`.
- Patch Tangent onto vertical walls is refused (documented gap, `parity/surface.md`); the
  journey uses Connected for every edge after checking the refusal.
- Offset Sharp is checked on a single face (it differs from Rounded only where faces meet;
  `surface3_offset_patch` covers two faces).

## FreeCAD facts

- A sketch on the YZ origin plane maps its x to the design's Y and its y to Z (normal +X).
- `split.order` keeps each body on the piece nearest its remembered centre: after a loft edit
  the box's body keeps the upper piece even when that piece becomes the smaller one.
