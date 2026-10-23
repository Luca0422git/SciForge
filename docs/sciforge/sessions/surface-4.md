# Session log: surface-4, SURFACE MODIFY on surface bodies (wave 6, branch `sf/surface-4`, 2026-10-23)

Brief: `docs/sciforge/dev/briefs/surface-4.md`. Parity doc (behaviour spec with sources,
how it works, known gaps): `docs/sciforge/parity/surface-modify.md`.

## What was built

The SOLID tools Fusion repeats on its SURFACE tab now work on surface bodies, and Merge is
new (all in one undo step, a timeline step with edit, saved with the design):

| Command | How |
|---|---|
| Split Body | a surface body as the Splitting Tool (a click on its face takes the whole body; Extend Splitting Tool carries on only the open edges that touch or run inside the body, so a smaller surface still cuts the solid in two and a twisted loft whose edges lie outside is not curled back into it); a surface body can be split (its pieces are surface bodies) |
| Delete | on the SURFACE tab faces go without healing (step `SurfaceDeleteFace`; a solid, also a STEP part without history, becomes a surface body); SOLID heals as before; faces of a surface body never heal |
| Fillet / Chamfer | new steps `SurfaceFillet` / `SurfaceChamfer` (Radius Type Constant / Chord Length / Variable; Equal / Two Distances / Distance and Angle + Flip; Tangent Chain; drag arrow + value box); F and SOLID's Fillet / Chamfer hand over when the picks are on a surface body (or nothing is picked on the SURFACE tab); a solid's edge clicked in the surface dialog goes back to the SOLID dialog |
| Press Pull (Q) | step `SurfacePressPull`. A flat face of a surface body moves along its normal: among flat polygons its corners slide along the edges leaving them (slanted walls follow exactly); faces running along the move grow or are cut back; neighbours at an angle (a cone under a lid) are carried on along their own surface or cut back and the lid is rebuilt in the moved plane; several flat faces facing different ways (two walls of a box or tray) each move along their own normal; one curved face is offset (a cup's wall, the floor follows). An edge of a surface body opens its Fillet; a surface fillet's face opens that fillet |
| Move/Copy, Align, Scale | the steps accept a body with faces (no solid needed); Move Object Faces moves flat faces of a surface body (the faces round them follow) |
| Pattern (Rect / Circ / Path), Mirror | bodies of type Bodies; a surface pick switches Pattern Type to Bodies; Mirror Join stitches the copy on with a Stitch Tolerance (dialog row, default 1 mm, kept on edit) |
| Merge (ribbon entry wired) | `SciForge_SurfaceMerge`: adjacent faces on one surface become one face (`UnifySameDomain`); faces that meet smoothly are refitted as one surface (filling through their boundary and sample points, refused when it moves them more than 0.01 mm / 0.1 %); a sharp edge is refused with the reason (step `SurfaceMerge`). Works in a design without history too (where Fusion offers it) |
| Split Face, Replace Face | the SOLID steps take a surface body: Split Face divides its faces and sews them back (Merge joins them again); Replace Face moves one face (or touching faces: a floor and its fillet) onto a flat or curved target (a cylinder: an arched floor), the faces round them carried on or cut back |
| Parameters | the surface dialogs' Radius / Distance fields take parameters and formulas (expressions on the step) |
| Combine, Silhouette Split | a surface body refused with a clear reason (Stitch / Thicken / Split Face) |
| Physical Material | lists surface bodies under In This Design |

New files: `sciforge/surfmod_core.py` (rules, unit tested), `sciforge/surfmod.py` (geometry +
`SurfaceModifyFeature`, saved as `sciforge.surfmod.SurfaceModifyFeature`: never rename),
`sciforge/surfmod_ui.py` (dialog on `pickpanel.PickPanel`, hand-overs, Merge command,
`ViewProviderSurfaceModify`), `tools/sciforge/icons_surface4.py` (5 icons `surfmod_*`),
`SciForgeTests/gui/surface4_steps.py`, 16 scenarios `surface4_*`, 22 golden models
`surface4_*`, `SciForgeTests/unit/test_surfmod_core.py`.

Shared files touched (small, each marked "surface-4"): `split.py`, `split_ui.py`,
`split_face.py`, `replace_face.py`, `move_face.py`, `delete.py`, `delete_ui.py`, `fillet_ui.py`,
`presspull_ui.py`, `move.py`, `align.py`, `scale.py`, `scale_ui.py`, `pattern.py`,
`pattern_ui.py`, `combine.py`, `silhouette.py`, `material_ui.py`, `ribbon_config.py` (the
Merge line only), `ai/ops/bodies_ops.py` (`measure_bodies` measures a surface body's faces),
the `# --- surface-4 ---` blocks in `ai/ops/surface3_ops.py` and
`SciForgeTests/golden/surface3_schema.py` (appended to the scaffold, right after its
header). No FreeCAD core change.

## FreeCAD / OpenCASCADE facts found (probed in FreeCAD 1.1.4)

- `PartDesign::Fillet` on a body whose base is a shell: Invalid, "Base feature's shape is not
  a solid". `shell.makeFillet(r, edges)` / `makeChamfer(d, edges)` / `makeChamfer(d1, d2,
  edges)` work, but return a **Compound of loose faces**: sew them again
  (`surface_geom.sew`) to keep one shell. A free edge (one face) fails with "BRep_API: command
  not done"; refuse it before. `makeFillet(r1, r2, edges)` is a radius changing evenly from
  each edge's start to its end; there is no chord-length law in the Python API.
- `ShapeUpgrade.UnifySameDomain(shape, UnifyEdges, UnifyFaces, ConcatBSplines)`: the third
  argument must be True to merge faces (passing False silently merged nothing). Never run it
  on a whole body after a change: it also merges faces the user split on purpose.
- `shell.defeaturing(faces)` refuses shells (`BOPAlgo_AlertTooFewArguments`): delete without
  healing = sew the remaining faces.
- `BOPTools.SplitAPI.slice(solid, [shell])` splits a solid by an open shell; slicing a shell
  by a plane gives a compound of shells (`surface_geom.shells_or_faces` lists the pieces).
- Carrying a twisted loft's edges on (`surface_geom.extend`, Natural or Tangent) curls the new
  parts back into a box it already crosses: a split then cut two extra slivers off. Only
  edges inside the body are carried on now.
- `surface_geom.extend` grows a cone / cylinder face exactly only when it has 4 edges; a full
  round face (3 edges: two circles and the seam) gets Tangent BSpline bands, whose
  `BoundBox` is loose (`optimalBoundingBox()` is tight). `surface.toShape(u0, u1, v0, v1)`
  on the face's own parameter rectangle grows it exactly (`surfmod._carry_on`); a cone's
  apex is at v = -Radius / sin(SemiAngle).
- A cone's seam line ends on its top circle: picking "the edge through a point of the
  circle" at the seam's end finds the seam; pick another point of the circle.
- `surface_geom.away_in_face` points OUT of the face (into = its negative).
- Black (the installed version) reformats a few old lines of shared files (a blank line after
  a module docstring, a long `if (...)`): never run black on a whole shared file; only lint.
- In the iso view an open box's floor is hidden near its front and right walls: click floor
  points near the back-left (y > depth / 2, x < width - height).
- The XZ origin plane's normal is -Y: a surface extruded from an XZ sketch goes to y < 0, a
  sketch offset +5 on it lies at y = -5.

## Tests (all with FreeCAD 1.1.4 in the sandbox)

- Scenarios, the final run (16, all PASS, 517 checks): surface4_component 24,
  surface4_delete_merge 48, surface4_direct 35, surface4_fillet 55, surface4_misc 28,
  surface4_move_faces 27, surface4_move_mirror 41, surface4_pattern 27, surface4_presspull
  50, surface4_presspull_faces 22, surface4_presspull_shade 19, surface4_replace_face 28,
  surface4_split 25, surface4_split_face 25, surface4_split_loft 44, surface4_step_part 19.
- Regression (scenarios of the tools touched, all PASS): bodies_combine 93, bodies_delete
  64, bodies_move 85, bodies_split 85, split_preview 67, extrude_presspull_presspull 53,
  modify2_presspull_type 48, fillet 67, fillet_chamfer 48, fillet2_chamfer 37, patterns_rect
  88, patterns_circ 68, patterns_mirror 64, fixpattern_mirror 159, shell_draft_scale 80,
  modify2_scale 58, modify_align 232, modify_silhouette 199, misc_materials 51,
  surface_stitch 63, surface_misc 70, modify_split_face 238, modify_replace_face 245,
  modify2_move_face 56.
- Wider regression (other scenarios of those tools, all PASS): components2_move 345,
  components2_pattern 278, components_move 219, delete_designs 36, direct_commands 189,
  direct_step_box 186, extrude_multibody_move 48, extrude_presspull_options 43,
  extrude_presspull_qa 133 / qa2 78 / qa3 75 / qa4 69 / qa5 86 / qa6 35 / qa7 36,
  fillet2_component 24, fillet2_variable 40, fillet_qa 114, fillet_qa_chamfer 62,
  fixdecal_body_move 132, fixpattern_circ 160, fixpattern_path 163, fixpattern_rect 185,
  modify2_pattern_adjust 51, modify2_pattern_path 36, modify_align_points 224, modify_remove
  309, patterns_path 58, patterns_qa 54, patterns_qa_more 52, shell_draft_qa_scale 368.
- `--only base` (final): unit 1866 OK (9 skipped; 18 in test_surfmod_core.py), golden 462
  pass + 2 xfail (old upstream bugs; the 22 `surface4_*` models pass), smoke 79 PASS, journey
  25 PASS, restart both phases PASS. (One earlier base run had the smoke's "Press Pull +5"
  check read the volume before the recompute while a probe loaded the machine; it passed on
  the two runs without other load.)

## Gaps (details and evidence in the parity doc)

Press Pull of a face next to a tangent face (a floor next to a fillet: Fusion lets the
fillet follow), of several curved faces, of a curved face with a tangent neighbour, of faces
facing different ways that are not among flat polygons; Replace Face onto a ball, or of a
face chain that reaches an open edge; Merge of faces that meet at a sharp edge (faces that meet
smoothly are refitted); surface Fillet's Variable-with-points, G2, Setback and Rule options;
Merge offered with history on (Fusion hides it); a surface body's steps are not baked into
a Base Feature when history is off (`direct.freeze` bakes solids only).

## QA pass (branch `sf/surface-4-qa`, 2026-10-23)

An independent QA session ran every surface4 scenario, the unit tests and the golden models
on the builder's head (all passed: 16 scenarios, 517 checks; unit 1866 OK; golden 462 + 2
xfail), read the whole diff, probed the geometry headless (Press Pull of slanted, filleted
and two-wall cases, Chord Length, chamfer types, refusals: all matched the maths) and added
two scenarios for the paths not walked yet.

Fixed (details in the parity doc's "QA pass"):

- Deleting a step from the timeline broke the surface steps after it: a Press Pull whose
  floor the deleted Fillet had changed lost its pick (red), and a Delete Face after it kept
  its face number while the faces were numbered again, so it silently deleted the left wall
  instead of the right one. Each surface-4 step now remembers a point inside each pick
  (hidden `SciForgePickPoints`, flag NoRecompute so writing it in `execute` touches nothing)
  and finds its picks again by it (`surfmod._names_on`, `refound_picks`, `_checked`).
- Suppress Features on a surface-4 step blanked the body (FreeCAD's PartDesign passes a
  suppressed step's base through as a solid: a shell comes out empty) and turned the steps
  after it red. `SurfaceModifyFeature.onChanged` puts the surface before it back when FreeCAD
  empties a suppressed step; `surfmod.effective_base` skips a suppressed empty step. The
  other surface steps (surface.py) still come out empty when suppressed: for surface-3.
- Press Pull of a wall next to a fillet now says the real reason (a tangent neighbour).
- F with a face of a surface body selected opened the dialog on another surface body.
- The surface dialog could leave its new step behind in the first body when the user
  dropped the last pick and clicked another body before the preview ran.

FreeCAD facts: a PropertyLinkSub to a deleted step is emptied by FreeCAD (delete.py re-links
it first only when the element is unchanged in the step before); a property added with
attribute 4 | 16 (Hidden | NoRecompute) can be written in `execute` without leaving the
document touched; PartDesign's Suppressed on a PartDesign::FeaturePython never calls its
`execute`: it sets the Shape to the base's solid (empty for a shell) and calls `onChanged`.

New scenarios: `surface4_qa` (empty design; edits cancelled with Esc for Fillet, Press Pull,
Delete Face; one Ctrl+Z after a cancelled edit; Press Pull of a floor with a rounded corner;
the Fillet deleted in the timeline under a Press Pull and a Delete Face; Suppress and
Unsuppress Features on the Press Pull; Merge; save,
close, reopen, edit) and `surface4_qa_reopen` (Mirror Join with Stitch Tolerance 0.5 and
Split Body by a surface across a save and a reopen; a Split Body edit cancelled with Esc).

QA results with the fixes (FreeCAD 1.1.4, run one at a time): `surface4_qa` 87 PASS,
`surface4_qa_reopen` 41 PASS, the builder's 16 surface4 scenarios all PASS (the same counts as
above), regression fillet 67, fillet_chamfer 48, extrude_presspull_presspull 53,
surface_stitch 63, surface_misc 70 all PASS; `--only base`: unit 1866 OK (9 skipped), golden
462 pass + 2 xfail, smoke 79 PASS, journey 25 PASS, restart both phases PASS. Each fix was
shown on the code before it: a headless probe (the Press Pull red and the wrong wall deleted
after deleting the Fillet) and `surface4_qa` on the old `surfmod.py` (the body blank, area 0,
after Suppress Features).

Left for later (also in the parity doc's Known gaps): suppressing a surface.py step
(Extrude, Patch, Stitch...) still empties it (surface-3's files); surface Fillet / Chamfer
take edges only (Fusion also takes faces); Scale merges a surface body's coplanar faces
(Refine), Fusion keeps them; the builder's gaps above.
