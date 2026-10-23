# Parity spec: the SURFACE tab (outline 7.9)

Implemented in `src/Mod/SciForge/sciforge/`: `surface_core.py` (the tools as data and rules,
pure Python), `surface_geom.py` (the geometry), `surface.py` (the steps in the document),
`surface_pick.py` (picked shapes and cells drawn in the view), `surface_ui.py` (the dialogs
and commands). Status: **first pass (2026-10-14), part 2 (2026-10-16: the Extrude, Revolve,
Sweep and Loft options in the next section), part 3 (2026-10-23, wave 6: the options of the
surface tools, Environmental Map Analysis, Isoparametric Curve; next section), not yet signed
off by Luca.**

## Part 3: the options of the surface tools (wave 6, branch `sf/surface-3`)

The gaps of the audit `dev/research/surface-gaps.md` that are in the `surface*` files (its
numbers in brackets), researched in `dev/research/fusion-surface.md`. **A** = Autodesk: the
help pages (Offset [H-OFF](https://help.autodesk.com/cloudhelp/ENU/Fusion-Patch/files/SFC-OFFSET.htm),
Patch [H-PATCH-REF](https://help.autodesk.com/cloudhelp/ENU/Fusion-Patch/files/SFC-REF-PATCH.htm),
Untrim [H-UNTRIM](https://help.autodesk.com/cloudhelp/ENU/Fusion-Patch/files/SFC-UNTRIM.htm),
Revolve [H-REV-REF](https://help.autodesk.com/cloudhelp/ENU/Fusion-Patch/files/SFC-REF-REVOLVE.htm),
Sweep [H-SWP](https://help.autodesk.com/cloudhelp/ENU/Fusion-Patch/files/SFC-SWEEP.htm),
Loft [H-LOFT-REF](https://help.autodesk.com/cloudhelp/ENU/Fusion-Patch/files/SFC-REF-LOFT-DLG.htm),
Extend [H-EXTEND-REF](https://help.autodesk.com/cloudhelp/ENU/Fusion-Patch/files/SFC-REF-EXTEND.htm),
Extrude [H-EXT-REF](https://help.autodesk.com/cloudhelp/ENU/Fusion-Patch/files/SFC-REF-EXTRUDE.htm),
[Stitch](https://help.autodesk.com/view/fusion360/ENU/?contextId=SFC-STITCH)), the API reference
(`OffsetTypes`, `PatchFeatureInput.groupWeight` / `isGroupEdges`, `UntrimLoopTypes`,
`RuledSurfaceCornerTypes`, `SweepFeatureInput.guideSurfaces`, `StitchFeatureInput.operation`,
`SketchIsoparametricCurves`, the `adsk` stubs) and the product-update blogs
([May 2025](https://www.autodesk.com/products/fusion-360/blog/whats-new-may-2025-major-product-update/):
Rounded Offset; [January 2026](https://www.autodesk.com/products/fusion-360/blog/january-2026-product-update-whats-new/):
Patch Reverse Normal; [March 2026](https://www.autodesk.com/products/fusion-360/blog/march-2026-product-update-whats-new/):
Isoparametric Curve; [September 2026](https://www.autodesk.com/products/fusion-360/blog/september-2026-major-product-update-whats-new/):
closed-loft corners, Environmental Map Analysis). **G** = SciForge's guess.

| Fusion | SciForge | Src |
|---|---|---|
| Offset: Offset Type **Sharp Offset** / **Rounded Offset**, Sharp by default (May 2025) [3] | Same: Sharp carries the offset faces on until they meet (OpenCASCADE's intersection join), Rounded fills each outside corner with an arc of the distance. A design saved before part 3 keeps Rounded (its result does not change on reopen). Sharp that cannot close (OpenCASCADE fails, or comes back "valid" with faces carried on without end: QA measured 2e7 mm across on the top of a box whose top edges are rounded) is refused, "try Rounded Offset" (see the gaps) | A |
| Patch: **Group Edges** off gives a Continuity per boundary edge [8] | Same: Group Edges off lists one row per edge (Edge 1, Edge 2...), each Connected / Tangent / Curvature; a Tangent edge OpenCASCADE cannot meet is refused with the reason | A |
| Patch: **Reverse Normal** check box + **Flip** (January 2026) [8] | Same: the patch faces the other way; Flip turns it over again | A |
| Patch: Tangency Weight, 0.5 by default [8] | Shown 0.5, greyed: OpenCASCADE's plate surface takes the faces' direction but no strength (see the gaps) | A |
| Untrim: Type **Manual** (pick the loops) and **Keep Copy** [11] | Same: Manual swaps the Faces box for a Loops box (a click on an edge takes its loop: a hole or the outer boundary); Extend works on an outer loop. Keep Copy puts the surface as it was in a body of its own (it goes with the step: undo, delete, clearing Keep Copy) | A |
| Revolve: **Project Axis** (on), the extent word **Partial**, **To** with **Two Sides** [12] | Same: Project Axis lays the axis into the profile's sketch plane (off: the axis where it is; an axis square to that plane is refused with the reason); Type Partial / To / Full (saved files keep the key "angle"); To offers One Side / Two Sides (no Symmetric), Two Sides asks for Object Two and turns the first side the right-handed way to the first object, the second side the other way to the second (overlapping sides refused). A revolve saved before part 3 keeps its axis unprojected | A, G (Project Axis on in the dialog; Fusion's API starts `RevolveFeatureInput.isProjectAxis` at false, [API](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/RevolveFeatureInput_isProjectAxis.htm), and a [forum answer](https://forums.autodesk.com/t5/fusion-support-forum/bug-revolve-feature-ignores-the-selected-axis/td-p/10934400) shows the dialog projecting an axis from another sketch) |
| Extrude: flat faces as Profiles; To Object **Chain Faces / Extend Faces** [13] | Same: a click on a flat face takes the curves round it (holes too); the Faces row offers Chain Faces (the face and the faces joined smoothly to it) / Extend Faces (the face alone, carried on past its edges) | A |
| Sweep: Type **Path + Guide Surface** [7] | Same: a Guide Surface box (faces; Chain Selection adds tangent faces); the profile keeps the angle it has to the surface along the path (the solid Sweep's rule, `sweep.py`); Orientation, Taper and Twist are not offered | A |
| Sweep Path + Guide Rail: Extent **Perpendicular to Path** (default) / **Full Extents**; Path Distance and **Guide Rail Distance** [14] | Same: Perpendicular to Path stops square to the path where the shorter of path and rail ends (a shorter rail: the path's own square section through the rail's end, since QA; it used the section square to the rail, which ran a rail that leaves the path 8 mm too far and tilted the end); Full Extents runs both to their ends (the rail spread over the whole path); Guide Rail Distance takes that share of the rail. A rail sweep saved before part 3 keeps Full Extents (what it did then) | A, G (Full Extents' mapping) |
| Loft: closed profiles with the same number of clearly defined corners are matched corner to corner (September 2026) [15] | Same: when every profile is a closed curve with the same number (3 or more) of sharp corners, each profile is restarted (and turned round when drawn the other way) so that corner meets corner with the least twist; other profiles loft as before | A |
| Loft: Edge Alignment Free Edges / Align Edges / Align to Surface [15] | The row is shown with a Tangent or Curvature end; Free Edges only, the other two greyed with the reason (see the gaps) | A |
| Extend Natural carries the face's own surface on (free-form faces too) [9] | Same for faces that are their surface's parameter rectangle: cylinders, cones, spheres, tori, revolved and extruded curves are carried on by their own definition (one face, still the same surface); free-form (B-spline, Bezier) faces by their own polynomial, refitted through 24 x 24 points of it (OpenCASCADE cannot trim a B-spline past its bounds); the distance is measured along the surface's own curve from the edge (QA: an extruded spline carried on by the speed at its edge went 14.0 mm for 10). Past a sphere's pole or round onto itself: refused. Other faces: tangent bands as before | A, G (refit) |
| Extend Natural, Edge Alignment **Align Edges** [9] | Same: the extension's sides carry on the outside edges meeting the picked one (a trapezoid's slanted sides go on slanting; a flat face stays one face); where no outside edge meets it, or that one is extended too, the side leaves square to the edge as with Free Edges. A face that is its surface's parameter rectangle carries itself on, its sides being the surface's own curves (aligned either way). Neighbours turning back too sharply: refused ("Use Free Edges") | A, G (the side directions blended along the edge) |
| Stitch: Operation (New Body / Join / Cut / Intersect) when the result closes [21] | Same: Join, Cut and Intersect combine the closed stitch with the solid it touches (the step goes into that solid's body, the surfaces are used up); a stitch that does not close is refused ("do not close into a solid"), as is one that touches no solid | A |
| Trim: a single face of a body as the Trimming Tool [22] | Same: a click on a face of a solid takes that face alone (a surface body is still taken whole, as before) | A |
| Ruled: Corner Type **Rounded** / **Mitered**, Rounded by default [24] | Same: the Mitered Corners check box became the Corner Type row. Ruled Type stays Tangent first (Fusion's default was not found, **G**) | A, G |
| INSPECT > **Environmental Map Analysis** (September 2026): a live reflection of the surroundings on the faces, Reflection Strength [17] | Same: Environment Studio (three soft light strips over a dark floor) / Horizon (sky over ground), Reflection Strength 0 .. 100 % (70 by default), Opacity, High Quality; a sphere map looked up by the reflection direction (Coin's environment mapping), so the bands slide over the surface as the view turns and a kink shows as a kink; listed in the browser's Analysis folder, saved with the design | A, G (the studio pictures) |
| Sketch > Project / Include > **Isoparametric Curve** (March 2026): U or V curves of a face, one at a distance from the face edge or several distributed, associative [18] | Same: click a face in an open sketch: its U curve through the clicked place is drawn (purple); Direction U / V; Type Single (Distance from the face's first edge, measured along the face) / Distributed (Count curves spread evenly); OK or Enter keeps them. They follow the face when the design changes. Kept like Project to Surface's curves, in a companion of the sketch (FreeCAD's sketches are flat) | A, G (Single's distance measured along the middle of the face) |
| Change Parameters lists the surface features' numbers | Same: every surface step's distances, angles, ratios and tolerance are rows of Change Parameters; since QA only those its choices use (the dialog's hidden rows are hidden there: no Distance Two for One Side, no Extend Distance with Extend off), as Fusion lists a feature's values in use | A (H-MOD), G |

Implemented in `surface_core.py` (the choices, `LEGACY` / `with_saved` for files saved
before, `turn_angle` / `two_sided_to`, `corner_shift`, the isocurve fractions: unit tested),
`surface_geom.py` (`offset_faces` join type, `patch` per-edge orders and reverse,
`untrim_loops`, `project_axis`, `_rail_extent`, `match_corners`, `_grow_rectangle` / `_refit`,
`_aligned_extend`,
`stitched_operation`), `surface.py` (Keep Copy's piece body, the guide faces, the stitch
target), `surface_ui.py` (the rows), `surface_analysis*.py` (Environmental Map),
`surface_iso.py` / `surface_iso_ui.py` (Isoparametric Curve). Golden models `surface3_*` (10,
analytic) and `surface3_extend_align_edges`; scenarios `surface3_offset_patch`, `surface3_untrim_revolve` (with save / reopen
and a component), `surface3_sweep_extrude`, `surface3_stitch_trim_ruled`,
`surface3_extend_envmap`, `surface3_isocurve`.

### Part 3 QA (branch `sf/surface-3-qa`, 2026-10-23)

An independent QA pass over part 3, as Luca would click it. Fixed:

- **Offset Sharp on rounded edges gave a surface kilometres wide.** OpenCASCADE's
  intersection join (`makeOffsetShape(..., join=2)`) on the top of a box whose top edges are
  rounded (the top, the rounds and the walls: Chain Selection takes all nine, they are
  tangent) returned a shape it calls valid with faces 2e7 mm across (area 1e9 mm²); Sharp is
  the default, so this was what Luca saw first. `surface_geom._runaway` now compares the
  result with the picked faces (a sharp corner reaches d / cos(half its turn), allowed up to
  25 d) and refuses with the reason ("Try Offset Type Rounded Offset"). Rounded works there.
- **Natural Extend went too far on free-form faces.** The extension was sized by the
  surface's speed at the edge; a spline carried on past its end speeds up (an extruded spline
  went 4.59 mm for 4, 14.0 for 10). `_grow_by` now measures along the surface's own curve
  (Richardson on two polylines, 1e-10) and solves for the distance: 4.00 and 10.00.
- **Sweep Perpendicular to Path with a rail that leaves the path.** With the rail the
  shorter, the path was cut by the plane square to the *rail* at its end: a rail from
  (15, 0, 5) to (25, 30, 5) along a path up y ran the sweep to y 38.33 and tilted its end.
  It now stops at the path's own square section through the rail's end (y 30). Golden
  `surface3_sweep_rail_perpendicular` (analytic box).
- **Change Parameters listed every number of a surface step**, also those its choices do not
  use (a One Side extrude showed Distance Two, Offset, Taper Angle Two). The dialog saves the
  numbers whose rows it hides with the step's choices (`hidden_numbers`), and the step hides
  those properties whenever its choices change (`SurfaceFeature.onChanged` ->
  `surface.apply_number_modes`), so undo, redo and Cancel bring the right rows back;
  `parameters.py` passes over hidden properties as it does for FreeCAD's own features.
- **Patch, Group Edges off, a Connected edge next to a Tangent one** was refused with "walls
  this steep" although all-Tangent works on the same walls. Measured: where a Connected edge
  meets a Tangent one the patch cannot be tangent at the corner, and OpenCASCADE's plate
  surface bends away over about a third of the Tangent edge (45 degree walls: 31, 19, 9
  degrees off at 1/12, 2/12, 3/12 of it; more points or iterations in `MakeFilling` change
  nothing). The refusal now names the mix and what to do (make the edges next to it Tangent,
  Connected for all, or gentler walls); mixed edges build on walls up to about 15 degrees from
  flat.

Scenarios added: `surface3_qa` (Offset Sharp refused on rounded edges then Rounded; Untrim
Keep Copy saved and reopened, deleted from the timeline with its copy, undone, edited with
Keep Copy cleared and cancelled; Isoparametric Curve: an empty click, Esc before and after a
pick, Enter, Ctrl+Z / Ctrl+Y in the sketch, save and reopen, the curve follows a radius
change after the reopen; Change Parameters rows), `surface3_qa2` (Stitch Operation changed
while the dialog is open: New Body / Cut / Intersect / New Body, Esc restores everything;
an edit that moves a Join stitch back to New Body, undo / redo), `surface3_qa3` (Extrude of
a flat face with a hole, To Object with Extend Faces, edit read-back, Cancel, undo / redo;
Patch per-edge Continuity: refused with the mix explained on 70 degree walls, built on 15
degree walls, saved, reopened, read back, Esc), `surface3_qa4` (Revolve To with Two Sides
whose sides would overlap: refused, OK waits, Esc leaves nothing; Environmental Map undone and
redone). Also checked by probe: Sweep Path + Guide Surface on a curved guide (a radial
profile along a wavy path round a cylinder stays radial within 0.01 mm; Single Path tilts it
1 mm).

## Part 2: Extrude, Revolve, Sweep and Loft options (wave 5, branch `sf/surface-2`)

Behaviour spec, researched before building. **A** = Autodesk (help pages "Extrude a surface
body" SFC-EXTRUDE, Extrude reference SLD-REF-EXTRUDE, "Revolve a surface body" SFC-REVOLVE,
"Sweep a surface body" SFC-SWEEP, Sweep reference SLD-REF-SWEEP, "Loft a surface body"
SFC-LOFT, Loft reference SFC-REF-LOFT-DLG and the Form loft reference FRM-REF-LOFT-DLG, the API
page `LoftFeatureInput.isTangentEdgesMerged`, the blog
[How to Extrude Cuts](https://www.autodesk.com/products/fusion-360/blog/quick-tip-extruding-cuts/);
help.autodesk.com could only be read through search excerpts). **F** = Autodesk Community
forum ([Revolve TO a plane, face, or object?](https://forums.autodesk.com/t5/fusion-design-validate-document/revolve-to-a-plane-face-or-object/td-p/8342213),
[Centerline cannot be tangent to profiles](https://forums.autodesk.com/t5/fusion-design-validate-document/error-trying-to-loft-centerline-cannot-be-tangent-to-profiles/td-p/11064817),
[The centerline is not a smooth chain](https://forums.autodesk.com/t5/fusion-design-validate-document/lofting-quot-the-centerline-is-not-a-smooth-chain-quot/td-p/7279414),
[Rail is not smooth](https://forums.autodesk.com/t5/fusion-design-validate-document/rail-is-not-smooth/td-p/12952240),
[Sweep with guide rail and flat sides](https://forums.autodesk.com/t5/fusion-support-forum/sweep-with-guide-rail-incapable-of-making-flat-side-surfaces/td-p/12524141)).
**G** = SciForge's guess (nothing found; Luca's screen captures will settle it).

| Fusion | SciForge | Src |
|---|---|---|
| Extrude Start: Profile Plane / Offset / From Object. From Object starts the extrusion at a picked face, plane or point, curved faces too; the Offset value moves it on from there | Same. A plane, flat face or point parallel to the profile sets where it starts (Offset added); a slanted plane or a curved face starts every line of the extrusion where it meets the object (the crossing nearest the profile), so the surface's near edge lies on that face. A whole body is refused ("Start from a plane, a face or a point") | A |
| A start face that does not lie across the whole profile | Refused with the reason ("part of it would start nowhere. Pick a bigger face or a plane") | G |
| A taper from a slanted or curved start | Refused: "A taper needs a start parallel to the profile... Set the taper to 0" | G |
| Extent To Object: extrudes to a body, face or plane that you select | Same. A plane, flat face or point (the plane through it, square to the direction) ends it flat; a curved face ends every line where it meets the face, carried on past the face's edges when the lines run beside it; a body ends it where the lines first reach it. A profile that would partly miss is refused with the reason | A |
| To Object Chain Faces (on): the picked face and the faces joined smoothly to it | Same, on by default: a fillet and the flat face it runs into stop the extrusion as one | A |
| Extent All ("Through All" in older releases): through all visible bodies; Flip flips it over the profile plane | Same: One Side goes as far as the visible bodies reach along the sketch's normal, Flip the other way; Two Sides and Symmetric go each way as far as the bodies reach. No body that way: refused ("Flip it, or use Distance") | A |
| Revolve Type Angle / To / Full. To revolves up to a body, face, plane or vertex you click ("change the type to To, then click the face") | Same: a plane or flat face through the axis, an edge or a point; the revolve turns the shorter way round to it (the solid Revolve's rule). Picked where the profile already is: refused with the reason | A, F |
| Sweep Type Single Path / Path + Guide Rail; the rail controls the profile's scale and turn | Same: a Guide Rail box (sketch curves or edges of a body, joined ones chain) | A |
| Profile Scaling Scale (X and Y) / Stretch (X only) / None (the rail only turns the profile) | Same; Scale by default | A, G (default) |
| Taper Angle and Twist Angle with Single Path, Orientation Perpendicular | Same as the solid Sweep: the end section scaled by 1 + L·tan(angle) / R (R: the profile's distance from the path start, its farthest point when the path starts on it); taper and twist together work. Hidden with Path + Guide Rail (the rail sets the scale and the turn there, as does Orientation), greyed under Parallel | A, G (rule) |
| Loft Guide Type Rails / Centerline. Rails must meet every profile and end on or beyond the first and last; a centerline holds the sections square to it, like a sweep path | Same. One rail moves each section onto it, two rails turn, move and stretch it toward both (8 sections fitted between each pair of profiles). Rails may be edges of bodies. A rail that misses a profile, or runs out before the last one, is refused with its number | A |
| One centerline only; centerline and rails must be smooth chains | Same: one Centerline box; Chain Selection takes the smooth chain | F |
| End conditions of the first and last profile: sketch curves Connected (Free) / Direction (Takeoff Weight, Takeoff Angle); edges of a body Connected / Tangent (G1) / Curvature (G2) with Tangency Weight; a point Point Tangent | Same rows (First Profile, Last Profile), also with rails or a centerline. Built by SciForge's own end rule (`loft_ends.py`, the solid Loft's), so Curvature works without core patch #14 | A |
| Closed: the last profile lofts back to the first | Same; the Last Profile row goes away (the loop has no last end) and Direction on the first profile sets how the loop passes through it. Two profiles: refused; Closed with rails or a centerline: refused ("Clear Closed or the rails") | A, G |
| Tangent Edges Merge / Keep: merge the edges of tangent faces into one face | Same check box, off (Keep) by default: see the gaps | A, G (default) |

Implemented in `surface_core.py` (choices, value checks, `stop_angle`, `all_lengths`,
`taper_factor`, `similarity` / `stretch_similarity`: unit tested in `test_surface_core.py`),
`surface_geom.py` (the geometry), `surface.py` (Refs2 / Refs3: To Object or the bodies All goes
through, the start object, the revolve's object, the sweep's rail, the loft's rails and
centerline) and `surface_ui.py` (the rows). Golden models `surface2_*` (11, analytic); scenarios
`surface2_extrude`, `surface2_revolve_sweep`, `surface2_loft` (with save / reopen / edit) and
`surface2_solid_loft`.

## Sources

The **Src** column of every table says where a behaviour comes from:

- **A** = Autodesk's own documentation: the Fusion help pages
  ([Patch reference](https://help.autodesk.com/cloudhelp/ENU/Fusion-Patch/files/SFC-REF-PATCH.htm),
  [Patch](https://help.autodesk.com/cloudhelp/ENU/Fusion-Patch/files/SFC-PATCH.htm),
  [surfaces from sketches](https://help.autodesk.com/cloudhelp/ENU/Fusion-Patch/files/SFC-CREATE-SURFACE-FROM-SKETCH.htm),
  [surface Extrude](https://help.autodesk.com/view/fusion360/ENU/?contextId=SURFACE-EXTRUDE-CMD),
  [Ruled reference](https://help.autodesk.com/cloudhelp/ENU/Fusion-Patch/files/SFC-REF-RULED-DLG.htm),
  [modify tools for surfaces](https://help.autodesk.com/cloudhelp/ENU/Fusion-Patch/files/SFC-MODIFY-SURFACE.htm),
  [Trim](https://help.autodesk.com/cloudhelp/ENU/Fusion-Patch/files/SFC-TRIM.htm),
  [Untrim](https://help.autodesk.com/cloudhelp/ENU/Fusion-Patch/files/SFC-UNTRIM.htm),
  [Extend reference](https://knowledge.autodesk.com/search-result/caas/CloudHelp/cloudhelp/ENU/Fusion-Patch/files/modify-tools/SFC-REF-EXTEND-html.html),
  [Stitch](https://help.autodesk.com/view/fusion360/ENU/?contextId=SFC-STITCH),
  [Thicken](https://help.autodesk.com/view/fusion360/ENU/?contextId=SLD-THICKEN),
  [Boundary Fill support article](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/How-to-create-a-solid-body-with-a-boundary-fill-command-to-check-volume-in-Fusion-360.html)),
  the Fusion API reference (PatchFeatureInput, TrimFeatureInput, BoundaryFillFeatureInput,
  StitchFeatureInput, OffsetFeatures, ThickenFeatures, UntrimFeatures, ExtendFeatures,
  UnstitchFeatures, RuledSurfaceFeatureInput, ReverseNormalFeatures: their defaults are the
  dialog's), and Autodesk's blog
  ([surfaces to solids](https://www.autodesk.com/products/fusion-360/blog/how-to-turn-surface-models-into-solid-bodies-autodesk-fusion/),
  [Boundary Fill tech tip](https://www.autodesk.com/products/fusion-360/blog/tech-tip-boundary-fill-a-tool-you-should-be-using/),
  [Thicken tech tip](https://www.autodesk.com/products/fusion-360/blog/tech-tip-thicken-command-surface-vs-form-environments/)).
- **F** = the Autodesk Community forum or tutorials
  ([Unstitch chain selection](https://forums.autodesk.com/t5/fusion-design-validate-document/how-to-turn-on-names-of-body-components-also-how-to-link/td-p/10725080),
  [Unstitch pieces](https://forums.autodesk.com/t5/fusion-support-forum/unstitch-bug/td-p/7102269),
  [surface Trim help](https://forums.autodesk.com/t5/fusion-manufacture-forum/surface-trim-tool-help-updated-with-new-example/td-p/11712222),
  the forum thread giving Stitch's 1.0 mm default tolerance,
  [VDCI Thicken tutorial](https://vdci.edu/learn/fusion/fusion-thicken-surface-solid),
  [untrim tutorial](https://www.cadedllc.com/post/learn-how-to-untrim-surfaces-in-fusion)).
- **G** = SciForge's guess at Fusion's behaviour (nothing found to confirm it; Luca's screen
  captures will settle it, outline 2.4).

## How a surface body lives in a design

A surface body is a normal SciForge body (`PartDesign::Body`) whose last step has faces and no
solid. Every SURFACE tool is a step of a body: a `PartDesign::FeaturePython` with SciForge's
`SurfaceFeature` (saved in files under that name, `SciForgeType` = `SurfaceExtrude`, `Patch`,
`Trim`...). The CREATE tools (Extrude, Revolve, Sweep, Loft, Patch, Ruled, Offset; Thicken and
Boundary Fill with New Body) start a new body, like Fusion's New Body / New Component (the only
operations Fusion's surface CREATE tools offer, **A**); the MODIFY tools (Trim, Untrim, Extend,
Stitch, Unstitch, Reverse Normal) add a step to the body they change.

Why a body and not a loose `Part::Feature`: the browser's Bodies folder, the timeline (edit,
roll back, suppress, delete, reorder), components, appearances, undo, save and reopen all work
on bodies already; a loose shape would have needed all of them again and would have no
timeline. PartDesign takes a FeaturePython step whose shape is not a solid; FreeCAD's own solid
features (Pad, Fillet...) refuse a base that is not a solid, so SciForge never puts a solid
feature into a surface body: `commands.find_body()` skips surface bodies (a solid tool then
starts its own body), and a sketch made on a surface face goes into a solid body. A body
turns solid when a step makes it one (a Stitch that closes, a Join), and back when that step
is undone or rolled back; the icon follows.

| Fusion | SciForge | Src |
|---|---|---|
| Surface bodies are listed in the Bodies folder with their own icon | Same: the surface icon (a curved sheet); a solid's cube when the body becomes solid | A |
| A surface body can be picked by the other tools (Trim tool, Stitch, Boundary Fill tools, Thicken) and from the browser | Same: a click on a face of it takes the body where the box wants bodies; its browser row too | A |
| Surface bodies are saved with the design | Same (scenario `surface_reopen`: same bodies, icons, timeline; the steps edit after reopening) | A |
| Every surface tool is one timeline step, named like the tool, with its icon; double-click to edit | Same: "Extrude 1", "Patch 1", "Boundary Fill 1"... (a surface Extrude is "Extrude" like Fusion's, with the surface icon) | A |
| Stitch uses the other surfaces up; Boundary Fill with Remove Tools uses its tools up | Same as Combine: they are hidden while the step is active and come back when it is undone, rolled back, suppressed or deleted | A |
| Unstitch makes a body per face | Same: the new bodies belong to the Unstitch step (they go with it on delete or undo) | A |
| Trim and Reverse Normal can change several bodies in one step | Same: one timeline step; hidden companion steps in the other bodies | A |

## Shared behaviour of the dialogs

| Fusion | SciForge | Src |
|---|---|---|
| A tool started with nothing selected opens and waits; its first box is blue | Same; what was selected before is taken at once | A |
| A click on a picked item drops it | Same, for every box (a curve, a face, a body, a plane) | A |
| Chain Selection / Enable Chaining: one click takes the connected curves (profiles, boundaries) or the tangent ones (paths, faces, edges) | Same: on by default (the API's default `isChainSelection = True`); off: one curve or face per click | A |
| Origin planes and axes can be clicked where a box takes them | Same: the big origin squares / axis lines are drawn while such a box is blue (the view does not move) | A |
| A sketch curve lying on a face is picked rather than the face | Same: a click within a few pixels of a shown sketch curve takes the curve (FreeCAD's selection gives the face) | G |
| Live preview; arrows and angle handles to drag, with a value box | Same: handles drawn on top of the design, a value box beside each (formulas too) | A |
| A pick or value that cannot work: the dialog says why, OK waits | Same: a hint (blue) for what is missing, a reason (red) with what to try; nothing in the Report view | G |
| OK, Cancel, Esc, Ctrl+Z; one undo step | Same | A |

## CREATE

| Tool / option | Fusion | SciForge | Src |
|---|---|---|---|
| Extrude | Profiles: sketch curves (open ones too) or edges; Start Profile Plane / Offset / From Object; Direction One Side / Two Sides / Symmetric; Extent Distance / To Object / All; Taper Angle; Operation New Body / New Component | Same: Profile Plane, Offset, From Object (part 2); the three directions (Symmetric: Half / Whole Length); Distance, To Object (a plane, a face, a body or a point; Chain Faces), All (Flip); a taper per side; New Body / New Component. A straight extrude both ways is one face per curve | A |
| Revolve | Profile, Axis (a line, edge or origin axis), Type Angle / To / Full, Direction, Angle | Same (To since part 2); Symmetric turns the angle each way (at most 180) | A |
| Sweep | Single Path or Path + Guide Rail; Distance; Orientation; Twist / Taper | Same: Single Path and Path + Guide Rail with Profile Scaling (part 2); Distance and Distance Two (a share of the path, when the profile sits inside it); Orientation Perpendicular / Parallel; Twist Angle, Taper Angle | A |
| Loft | Profiles (curves, points) in order; Guide Type Rails / Centerline; end conditions; Closed; Tangent Edges Merge | Profiles in a list (Up / Down / Remove), Chain Selection, Closed; rails (one or two), a centerline, end conditions and Merge since part 2 | A |
| Patch | Boundary Edges (a closed loop: one click finds the loop), Enable Chaining, Group Edges, Continuity Connected / Tangent / Curvature (sketch curves: ignored), Tangency Weight, Interior Rails / Points, Reverse Normal | Same boxes; Continuity for edges of bodies (G0 / G1 / G2), per edge with Group Edges off (part 3); Interior Rails / Points; Reverse Normal + Flip (part 3). A boundary that does not close is refused with the count of open curves | A |
| Patch, Tangent | The patch meets the surrounding faces tangent | Same, and SciForge measures it: where OpenCASCADE could not turn the patch to meet the walls (walls steeper than its patch can follow, such as a vertical tube's rim), the dialog says so instead of making a near-flat patch | A |
| Ruled | Edges; Ruled Type Normal / Tangent / Direction; Distance; Angle; Alternate Faces; Corner Type Rounded / Mitered (default Rounded) | Same (Corner Type since part 3) | A |
| Offset | Faces (Chain Selection on: tangent faces too); Offset Type Sharp / Rounded; Distance (positive along the face normal); New Body / New Component | Same (Offset Type since part 3, Sharp by default) | A |
| Thicken | Faces or surface bodies; Thickness; Direction One Side / Symmetric; Thicken Type Sharp / Rounded (rounded corners take the thickness as radius); Operation Join / Cut / Intersect / New Body / New Component; also on the SOLID tab | Same; a negative thickness thickens the other way; Join / Cut / Intersect act on the solid the faces belong to, else the solid the thickened shape touches; too thick: refused ("use a smaller thickness") | A, F (radius) |
| Boundary Fill | Tools (bodies, surfaces, planes); cells of the closed spaces, picked in the view or the list; Remove Tools; Operation; also on the SOLID tab | Same: the cells are drawn see-through when the Cells box is blue, the one under the mouse lights up, a click picks it (blue); the list ticks them too; "No closed cell yet" when the tools close no space | A |
| Boundary Fill, Remove Tools | Off: the tools stay | Off by default | G |

## MODIFY

| Tool / option | Fusion | SciForge | Src |
|---|---|---|---|
| Trim | Trimming Tool: a surface, a plane or a sketch curve; then click the pieces to remove (they turn red; click again to keep) | Same. A sketch curve cuts straight through along its sketch's normal. A surface body (a click on any face of it) is the tool whole; a click on a face of a solid takes that face alone (part 3) | A, F (red) |
| Trim, the tool's own body | The tool surface is trimmed by the surfaces it crosses too (Trim "splits intersecting surfaces") | Same: both walls of a cross are cut, one step changes both | A |
| Trim, nothing cut | | The dialog says the tool cuts no surface and OK waits | G |
| Untrim | Faces; Type All Edges / Internal Edges / External Edges / Manual; Extend (the outer edges, a distance); Keep Copy | Same (Manual and Keep Copy since part 3); only loops that touch no other face are removed (the API's rule); none: refused with the reason | A |
| Extend | Edges (outer edges only), Enable Chaining (tangent edges); Distance (an arrow); Extend Type Natural / Perpendicular / Tangent; Edge Alignment Free / Align (Natural only) | Same (Align Edges since part 3). Natural carries the face's own surface on (a flat face stays one face; cylinders, cones, spheres, tori, revolved, extruded and free-form faces since part 3); Natural and Tangent extend outwards only, Perpendicular both ways | A |
| Stitch | Surface bodies; Tolerance (default 1.0 mm, forum); a closed result becomes a solid; the edges within tolerance are shown green, the ones left open red; Operation when it closes | Same; the open edges left are drawn red and counted, the ones the stitch closes green (part 2), "Closed" when it makes a solid; a solid picked is refused ("Unstitch it first"); New Body / Join / Cut / Intersect (part 3) | A, F (1.0 mm) |
| Unstitch | Faces or bodies; Chain Selection (on: every face joined to the clicked one) | Same: each face becomes a surface body | A, F |
| Reverse Normal | Surface bodies: every face turned over | Same, a short arrow shows which way each surface faces; a solid is refused (its faces always point out) | A |
| Replace Face, Split Face (SURFACE > MODIFY too) | Faces of solids; the target or tool may be a surface body | Same commands as on the SOLID tab (`direct-modify.md`); since modify-2 Replace Face takes any target surface, a surface body's face included | A |
| Delete | | FreeCAD's / SciForge's Delete, as before | |

## Known gaps

| Fusion | Why not yet |
|---|---|
| Patch Continuity Curvature on stock FreeCAD 1.1.4 | FreeCAD bug: `MakeFilling.add` casts order 2 to `GeomAbs_C1`, which OpenCASCADE's filling ignores (the patch silently came out tangent-less). Fixed by core patch #14 (`docs/sciforge/core-patches.md`); until a full build ships it, the dialog refuses Curvature with the reason (Tangent works). `surface_geom.g2_available()` tells a patched build |
| Patch Tangent onto vertical walls (a tube's rim) | OpenCASCADE's plate surface cannot turn that far (the reached tangency is off by about 90 degrees, measured): refused with the reason instead of a wrong patch. Sloped walls work |
| Patch Tangency Weight | OpenCASCADE's filling (`BRepFill_Filling` / GeomPlate) matches the neighbouring faces' direction but has no strength for it, so the weight could not change the shape: shown 0.5 (Fusion's default) and greyed with the reason. Group Edges off works since part 3 |
| Extrude All after the design changes | All goes through the bodies that were visible when the step was made (they are saved with it, so a reopened design gives the same surface); a body shown or added later is not taken in until the step is edited. Fusion's rule for a later change is not documented (**G**) |
| Extrude From Object with a taper from a slanted or curved start | Refused with the reason: a taper is measured from a start plane, and a curved start has none |
| Sweep Path + Guide Rail, Full Extents with a rail shorter or longer than the path | Built (part 3), but how Fusion maps the rail onto the path then was not found: SciForge spreads the rail evenly over the path, so the profile turns to keep touching it (**G**). Guide Rail Distance has a field, no drag handle on the rail yet |
| Loft with three or more rails | Refused with the reason ("one or two rails"): SciForge fits each section to the rails by a turn, move and stretch, which two rails fix exactly; more would need a real multi-rail fit (OpenCASCADE has no rail loft) |
| A closed loft with rails or a centerline | Refused with the reason (Fusion's behaviour not found, **G**) |
| Tangent Edges Merge off by default | Fusion's default was not found (the API page is cut off). Merge is off because OpenCASCADE measures the volume of a merged side (one B-spline face closed round the profile) several percent wrong: a slot lofted to the same slot gives +5.6 % (golden `sf_loft_merge_slot_volume`, expected failure); the shape itself is right (its mesh gives the true volume) |
| Loft rails between profiles that turn | The rail loft fits 8 sections between each pair of profiles: within 1 % of the true shape (a square turned a quarter round two arc rails: 3889 against 3927 mm³, golden `sf_loft_rails_turning`) |
| A loft of closed smooth profiles (no corners) that twists | Corner matching (part 3) needs sharp corners, as Fusion's September 2026 rule does; smooth closed profiles still pair where OpenCASCADE starts them |
| Extend Natural on a trimmed curved face | A face that is not its surface's parameter rectangle (a trimmed face) still gets a band (tangent, or with Align Edges along its neighbours), not its own surface: OpenCASCADE cannot grow a trimmed face's boundary along its surface |
| Extend Natural on a free-form face | Carried on by the surface's own polynomial and refitted through 24 x 24 of its points: the extended face is a new B-spline that matches the old one at those points (between them it can differ by a hair: measured 3e-6 mm on a wavy B-spline face, 2e-3 mm on a circle-to-ellipse loft carried on 20 %); a neighbouring face is sewn to it with a 0.001 mm tolerance |
| Loft Edge Alignment Align Edges / Align to Surface | Shown greyed with the reason: OpenCASCADE's loft (ThruSections) takes no direction for the side curves at a profile's ends; SciForge's own end rule (`loft_ends.py`) sets the takeoff across the profile only |
| Extrude To Object Match Shape | Not built: Fusion's documentation found does not describe it (Autodesk's Inventor has a Match Shape for open profiles, [reference](https://help.autodesk.com/cloudhelp/2015/ENU/Inventor-Help/files/GUID-951A7AC9-D30D-4834-ADB9-959AC4CD404E.htm)); the audit's row came from one search excerpt. Chain Faces / Extend Faces is built |
| Isoparametric Curve inside the sketch | Fusion puts the curves in the sketch itself; FreeCAD's sketches are flat, so they live in a companion of the sketch (like Project to Surface's): drawn, hidden, listed and deleted with the sketch, but the sketch's own tools (constraints, Trim) cannot use them. Editing them again means deleting and picking again (no edit dialog yet) |
| Environmental Map pictures | Fusion's studio images were not found; SciForge draws its own two (Studio, Horizon) |
| Offset Sharp on rounded (tangent) edges that meet at a corner | OpenCASCADE's intersection join cannot close the corner where two rounds meet (the top of a box with rounded top edges, measured): refused with the reason, Rounded works. Fusion makes it. Thicken refuses that shape too, Sharp or Rounded (OpenCASCADE: "no image for shape") |
| Patch: a Connected edge next to a Tangent one (Group Edges off) | Refused with the reason on walls steeper than about 15 to 20 degrees from flat (QA, measured): OpenCASCADE's plate surface spreads the forced corner over a third of the Tangent edge. Fusion builds it (its transition is not documented) |
| Isoparametric Curve, Single after the face grows | The curve keeps its Distance (mm along the face from its first edge), as Fusion's parameter does: on a cylinder whose radius grows from 10 to 12 a curve 47.12 mm round moves from 270 to 225 degrees (measured) |
| Boundary Fill from planes alone | Fusion is reported to need at least one body (**F**, one forum report); SciForge accepts planes alone, which does no harm, so it is kept until Luca's Fusion confirms it |
| The design's first sketch body | A new design's first sketch lives in a body (FreeCAD needs one); when the first thing made from it is a surface, that body stays in the browser with only the sketch in it. Fusion keeps sketches outside bodies |
