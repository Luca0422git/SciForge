# Session log: mesh and inspect part 2 (branch `sf/mesh-inspect-2`, 2026-10-16)

Brief: `docs/sciforge/dev/briefs/mesh-inspect-2.md`. Spec with sources (Autodesk / Forum /
Guess per row) and gaps: the "Wave 5" sections at the top of `docs/sciforge/parity/mesh.md`,
`parity/inspect.md` and `parity/inspect-analysis.md`. No FreeCAD core file was changed.

## What was built

- **MESH > MODIFY > Direct Edit** (`mesh_direct_ui.py`, maths in `mesh_edit_core.py`):
  one dialog with the selection palette and the tools. Selection Paint (a brush, its size in
  mm; click or drag), Window (drag a box: left to right takes faces inside, right to left
  faces it crosses) or Free Form (draw round them); Select Back Faces off by default (only
  faces that face you and nothing hides); Select Filter Faces / Face Groups; Ctrl takes faces
  off; an empty click clears. Grow (Shift+Up), Shrink (Shift+Down), Invert (Alt+N), Expand To
  Face Groups (Alt+G), Expand To Connected (Alt+C), Clear. Tools: Delete (Del), Erase And
  Fill (Minimal / Uniform with Density), Create Face Group, Reverse Normal, Move (an arrow
  along the faces' mean normal or X / Y / Z, a Distance box, the move shows at once and Apply
  Move keeps it), Smooth (Smoothness, the rim of the region stays put). The edits are listed;
  Remove Last Edit takes the newest back. Finish Direct Edit (or OK) makes one timeline step
  "Mesh Base Feature 1"; double-click opens it again with its edits; Cancel / Esc leave the
  step as it was.
- How the step keeps its edits: a `Mesh::FeaturePython` step (`MeshDirectEdit`) with a list
  of JSON lines (`Edits`), each edit naming its faces by their centres. On recompute the
  edits are played again on the body as the step before leaves it (a prefix cache makes a
  new edit or a dragged move cheap). Faces that are gone are reported in the step's info.
- **PREPARE > Create Face Group** (pick faces with the brush, OK: one new face group) and
  **Combine Face Groups** (click two or more touching groups: one group; groups that do not
  touch are refused with the reason) in `mesh_groups_ui.py`. Smooth also takes face groups
  now (like Reverse Normal), smoothing only those.
- **Mesh steps roll back with the history marker**: every MESH step (Insert Mesh,
  Tessellate, Repair, Smooth ... Direct Edit) is a root step that `rolls`
  (`timeline_ops.rolls_back`); `timeline_ops.follow_mesh_steps` marks the steps after the
  marker `SciForgeRolledBack` (headless too), hides them and their pieces, and
  `bodies.sync_consumed` shows the step before. A design of mesh bodies only can have its
  marker moved (`timeline_core.marker_for_slot` returns the note alone). A mesh step made
  while the marker is rolled back goes in at the marker (`place_root_step`), and the body's
  later steps then build on it (`mesh.insert_before_rolled`), as Fusion does.
- **INSPECT > Interference: Create Bodies**: a Create Body tick per overlap and "Create Bodies
  From Interferences" for all; OK makes each ticked overlap a new body (a base feature
  holding exactly the shared volume) in the same undo step as the analysis
  (`analysis.create_bodies`). Interference now compares bodies where they show (moved
  components count).
- **Measure: Component filter**: a click on any body of a component picks the whole
  component (Volume and Area of all its bodies, the minimum distance and Delta X / Y / Z to
  the other pick); a body at the top of the design is refused with the reason.
- **Zebra Analysis on mesh bodies** (the Fusion API lists mesh bodies for Zebra): stripes on
  the mesh's own triangles, following the body's newest step; the other analyses refuse a
  mesh body and say why; a mesh body rolled back by the marker says so in the dialog.
- **Minimum Radius: Include Sharp Curves**: the sharp inner edges drawn red and counted.
- Icons `mesh_direct_edit`, `mesh_create_group`, `mesh_combine_groups` (`make_icons.py`);
  ribbon MESH > PREPARE (Create / Combine Face Groups) and MODIFY (Direct Edit).

## FreeCAD facts and traps (for the next session)

- `Mesh.nearestFacetOnRay` walks the facets with float tests: a ray through a vertex (the
  pole of a sphere) can slip between the facets there and return a facet on the far side.
  `DirectEditPanel._facet_under` casts four rays nudged by a fraction of a pixel and keeps
  the nearest hit.
- Coin: `SoFaceSet.numVertices.setValues(0, n, ...)` only writes over the start of the field;
  after a selection shrinks, the old tail stays and Coin reads past the points (SIGSEGV in
  `SoFaceSet`). Cut both fields with `setNum(0)` first (`mesh_pick_ui.FacetMarks.show`).
- A mesh built from points and facets keeps the facet order; reading an STL back reorders
  the points but not the facets. Points are stored as float32: compare centres with a
  tolerance (`EditState.quantum`), never exactly.
- Hole rims next to faces whose normals were turned over do not chain as directed loops;
  `mesh_edit_core.rim_loops` chains them undirected and orients each loop by the majority
  winding (also used by MESH > Erase And Fill now).
- Laplace smoothing with the rim fixed lowers a bump; Taubin (FreeCAD's) barely moves a small
  region and an open edge next to it pins it.
- Surface overlays on a mesh body need a negative `SoPolygonOffset` (the mesh's own faces
  have none), otherwise they fight for the same pixels.
- `from PySide import QtTest` fails in FreeCAD 1.1.4's shim: use `from PySide6 import QtTest`.
- The newer black on the sandbox adds a blank line after module docstrings; files of other
  areas were kept as they were.

## Tests

- Scenarios: `meshinspect2_direct` (79 checks), `meshinspect2_groups` (74),
  `meshinspect2_inspect` (81), `meshinspect2_reedit` (76): brush paint and delete, box and
  free-form selection, back faces, move a face group (arrow and Distance), smooth a region,
  Remove Last Edit, create / combine face groups (and the refusal), the marker rolled before a
  mesh step and a step made at the marker, interference bodies (volume 3000 checked), measure
  between two components, Include Sharp Curves, zebra on a mesh, undo / redo, save / reopen,
  re-edit from the timeline, Cancel and Esc.
- Unit tests: `test_mesh_edit_core.py` (18), `test_timeline_core.py`
  (`MeshStepsAndTheMarkerTests`); all 1142 unit tests pass.
- Re-run and passing: every `mesh_*` scenario and `insert_mesh`, `fixpattern_marker`, the
  `timeline_*` scenarios, every `inspect_*` scenario, `--only base`, `check_install.sh`.

## Not built (see the parity docs' gap lists)

The Direct Mesh Editing contextual tab, a frozen base feature (edits are played again
instead), Move with rotation (triad), Ctrl+Z per edit inside the dialog, rim double-click,
Remesh / Reduce on face groups, Shift+F face-group display toggle, playback buttons stepping
over mesh steps, Cycle Component Color, analyses other than Zebra on meshes, Include Sharp
Curves on Curvature Comb (no source).

## Changes in other areas (for the merger)

- `timeline_ops.py`: `MESH_TYPES`, `ROLLED_BACK`, `is_mesh_step`, `rolls_back` includes mesh
  steps, `follow_mesh_steps` (called from `show_marker_state` and at the end of `settle`).
- `timeline_core.py`: three kinds; `marker_for_slot` without solid steps returns the note.
- `bodies.py` (`is_active_step` of a root step), `browser_ui.py` (`_marker_hidden`),
  `insert.py` (`make_mesh_body` placed at the marker), `mesh_pick_ui.py` (FacetMarks fix).
- `analysis.py` (`solid_of` uses `bodies.global_shape`, `overlaps`, `create_bodies`),
  `interference_ui.py`, `measure.py`, `measure_ui.py`, `surface_analysis.py`,
  `surface_analysis_ui.py`, `ribbon_config.py` (own lines only).
