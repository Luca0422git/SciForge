# Session log: modeling-2 (wave 4, branch `sf/modeling-2`)

To be copied into MEMORY.md by whoever merges (this branch does not edit MEMORY.md).
Started from `7282c76096`. No FreeCAD core file changed (no full build needed).

## What was built

1. **Holes** (`hole_tables.py` new, Qt-free, unit tested; `hole.py`, `hole_ui.py`):
   - Hole Tap Type **Taper Tapped**: NPT (ASME B1.20.1) and BSPT Rc (ISO 7-1), 1/16 to 3;
     the hole starts at the pipe thread's minor diameter at the opening and narrows 1 in 16
     on the diameter (FreeCAD Hole `Tapered`, `TaperedAngle` = 90 - 1.7899 degrees); the
     thread is cosmetic.
   - **Clearance by fastener**: Standard (ISO 273 / ASME B18.2.8), Fastener Type (socket
     head, hex head, countersunk; offered by hole type), Size, Fit Close / Normal / Loose;
     the fastener fills in the counterbore or countersink (DIN 974-1, ISO 10642 90 degrees,
     ASME 82 degrees). M6 Normal = 6.6.
   - **Modeled threads in their class** (`thread_tables.class_zone`, ISO 965-1 / ASME B1.1:
     the middle of the tolerance zone; `thread_core.class_radii`); a tapped hole's drill and
     major diameter shift with the class (FreeCAD `UseCustomThreadClearance`).
   - **A hole on a curved face follows the face**: hidden helper "Hole On Face"
     (`Part::Part2DObjectPython`, the face's u, v) whose `Spot` drives the hole sketch's
     `AttachmentOffset` by an expression.
2. **Extrude To Object** (`extrude.py`, `extrude_prism.py`, `extrude_ui.py`): Extend To
   Selected Face / To Adjacent Faces (a face), To Body / Through Body (a body), none for a
   plane; Offset per side (formulas too); **Start: Object follows** its object (hidden helper
   `ExtrudeStart`, the profile binder's Placement is an expression on its Shift).
3. **Objects To Cut for Revolve, Sweep and Loft** (`bodies_row_ui.py` new; `revolve.py`,
   `sweep.py`, `loft.py` and their dialogs; the machinery of `extrude_bodies.py`, now
   generic: `lead_kind`, `lead_tool`, `bodies_in_way`, `participants_of`): the row, the
   clicks, the blue copies, followers / lead body / Join merge, the red cut preview; body
   hiding paused while a Join preview merges; a step moved to another body goes in after
   that body's older sketches (`insert_point`, also for Extrude).
4. **Sweep values take formulas** (Distance, Distance Two, Taper, Twist): expressions on
   SciForge's sweep, listed under the fields; `curve_pick.RatioBox(formulas=True)` +
   `RatioField` adapter for `preview.FormulaInput`; a formula forces SciForge's own sweep.
5. **Sketch Chamfer** (`sketch_chamfer_core.py` Qt-free + unit tests,
   `sketch_chamfer_tool.py` on `sketch_draw.DrawTool`, `sketch_chamfer_ui.py`; ribbon
   SKETCH > MODIFY > Chamfer now runs it): Equal distance / Distance and angle / Two
   distances, a type box at the top left of the view, value boxes, dimensions from the kept
   corner point (Equal: the second is an fx expression of the first). Sketch fillet radius
   checked; the typed line angle researched (Forum: from the X axis, as FreeCAD does) and
   checked.
6. Parity docs: wave 4 sections with sources at the top of `sketch.md`, `hole-thread.md`,
   `extrude-presspull.md`, `revolve.md`, `sweep-loft-rib.md`; their known gaps updated.

## Tests

Scenarios (real input): `modeling2_holes` (84 checks), `modeling2_extrude` (53),
`modeling2_bodies` (54), `modeling2_sweep_formula` (31), `modeling2_sketch` (128); all pass.
Goldens new: `hole_taper_npt`, `hole_taper_bspt_through`, `hole_clearance_socket_cbore`,
`hole_clearance_countersunk`, `hole_curved_follows`, `thread_shaft_modeled_6e`,
`extrude_to_adjacent_faces`, `extrude_to_selected_face_extended`, `extrude_to_object_offset`,
`extrude_through_body`, `extrude_start_object_follows`, `sf_revolve_cut_two_bodies`,
`sf_revolve_cut_other_body`, `sf_sweep_join_two_bodies`, `sf_loft_cut_two_bodies`,
`sf_sweep_distance_parameter`, `sf_sweep_taper_parameter`; the modeled-thread goldens were
updated to their class. Unit tests `test_hole_tables.py`, `test_sketch_chamfer_core.py`.
Regression scenarios run and passing: every `revolve_*`, `sweep_loft_*`, `extrude_multibody*`,
`extrude_bodies_highlight`, `bodies_timeline`, `gaps_join_new_body`, `gaps_loft_ends`,
`gaps_sweep_guide_surface`, `ribbon_sweep`, `sketch_sweep`, `sketch_qa`,
`sketch_tools_audit`, `sketch_tools_modify`, `sketch_menu_switch`, `marking_menu_command`,
the hole / thread / extrude scenarios listed in the first commit.

## FreeCAD facts and traps found

- A PartDesign Body accepts only PartDesign features, datums and sketch-like objects: a
  hidden helper inside a body must be a `Part::Part2DObjectPython` (a `Part::FeaturePython`
  is refused: "Only PartDesign features, datum features and sketches can be inserted").
- FreeCAD's Hole clearance fallback factors give 5.92488 for a size the table lacks; do not
  round (the dialog and the golden then disagree).
- A Pocket To Face (FreeCAD's own) whose profile lies partly inside material also cut above
  the profile plane (900 instead of 720 in `modeling2_extrude`'s first try). Not fixed.
- `sketch.fillet(l1, l2, ref1, ref2, r, trim, createCorner=True, chamfer=True)` keeps the old
  corner as a construction point and moves the corner's constraints (also the origin
  coincidence) onto it; its construction arc holds both setbacks equal: delete it to free
  them. The two-line form with reference points works for touching and non-touching lines.
- Expressions between a sketch's own constraints work with names:
  `sketch.setExpression("Constraints.B", "Constraints.A")`.
- FreeCAD's line tool writes a typed angle as `Constraint('Angle', -1, line, value)` with
  `%f`: six decimals of a radian, so a 20 mm line ends about 1e-5 mm off the exact angle.
  `Constraint('Angle', g1, pos1, g2, pos2, v)` measures from each line's direction away from
  the given end, anticlockwise from g1 to g2.
- The timeline keeps each body's own order (its Group): a step inserted right after a solid
  step but before an older sketch of that body jumps ahead of the sketch in the timeline (and
  of other bodies' steps made in between). `extrude_bodies.insert_point`.
- Removing a Join merge that was a body's Tip, then the old lead, leaves the new end of the
  body hidden; `_show_only_tip` after a multi-body build.
- `bodies.sync_consumed` hides a body a Join preview merges, from under the next click;
  dialogs pause it while they preview a merge (Extrude did; Revolve, Sweep and Loft now too).
- PySide6: `QWidget.isVisibleTo(x)` needs a QWidget (a task Panel is not one).
- `SCIFORGE_GOLDEN_FILTER=sf_sweep` runs only the goldens whose name contains the text.

## Gaps (with the reason)

- A modeled taper pipe thread (cosmetic only); fastener types beyond socket head, hex head
  and countersunk screws.
- Sketch chamfer: no drag arrow (the pointer sizes it), lines only (no line-arc chamfer).
- The typed line angle relative to the previous line: not built because the forum threads
  found (2016-2020) say Fusion measures it from the X axis; to confirm in Luca's Fusion.
- Editing an older Revolve / Sweep / Loft does not roll the timeline back, so a body a later
  Join merged away cannot be clicked in its Objects To Cut row (Fusion rolls back for the
  edit). Objects To Cut across components was not tried.
- The Pocket To Face quirk above.

## Next

- Luca to check the Guess rows (chamfer type box place, the dimensions' form, Start Object
  following, a plane having no Extend).
- Roll the timeline back while editing an older multi-body step.
