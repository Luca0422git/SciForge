# Parity spec: the SURFACE tab (outline 7.9)

Implemented in `src/Mod/SciForge/sciforge/`: `surface_core.py` (the tools as data and rules,
pure Python), `surface_geom.py` (the geometry), `surface.py` (the steps in the document),
`surface_pick.py` (picked shapes and cells drawn in the view), `surface_ui.py` (the dialogs
and commands). Status: **first pass (2026-10-14), part 2 (2026-10-16: the Extrude, Revolve,
Sweep and Loft options in the next section), not yet signed off by Luca.**

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
| Patch | Boundary Edges (a closed loop: one click finds the loop), Enable Chaining, Group Edges, Continuity Connected / Tangent / Curvature (sketch curves: ignored), Tangency Weight, Interior Rails / Points | Same boxes; Continuity for edges of bodies (G0 / G1 / G2); Interior Rails / Points. A boundary that does not close is refused with the count of open curves | A |
| Patch, Tangent | The patch meets the surrounding faces tangent | Same, and SciForge measures it: where OpenCASCADE could not turn the patch to meet the walls (walls steeper than its patch can follow, such as a vertical tube's rim), the dialog says so instead of making a near-flat patch | A |
| Ruled | Edges; Ruled Type Normal / Tangent / Direction; Distance; Angle; Alternate Faces; Mitered Corners (default rounded) | Same | A |
| Offset | Faces (Chain Selection on: tangent faces too); Distance (positive along the face normal); New Body / New Component | Same | A |
| Thicken | Faces or surface bodies; Thickness; Direction One Side / Symmetric; Thicken Type Sharp / Rounded (rounded corners take the thickness as radius); Operation Join / Cut / Intersect / New Body / New Component; also on the SOLID tab | Same; a negative thickness thickens the other way; Join / Cut / Intersect act on the solid the faces belong to, else the solid the thickened shape touches; too thick: refused ("use a smaller thickness") | A, F (radius) |
| Boundary Fill | Tools (bodies, surfaces, planes); cells of the closed spaces, picked in the view or the list; Remove Tools; Operation; also on the SOLID tab | Same: the cells are drawn see-through when the Cells box is blue, the one under the mouse lights up, a click picks it (blue); the list ticks them too; "No closed cell yet" when the tools close no space | A |
| Boundary Fill, Remove Tools | Off: the tools stay | Off by default | G |

## MODIFY

| Tool / option | Fusion | SciForge | Src |
|---|---|---|---|
| Trim | Trimming Tool: a surface, a plane or a sketch curve; then click the pieces to remove (they turn red; click again to keep) | Same. A sketch curve cuts straight through along its sketch's normal. A whole body (a click on any face of it) can be the tool | A, F (red) |
| Trim, the tool's own body | The tool surface is trimmed by the surfaces it crosses too (Trim "splits intersecting surfaces") | Same: both walls of a cross are cut, one step changes both | A |
| Trim, nothing cut | | The dialog says the tool cuts no surface and OK waits | G |
| Untrim | Faces; Type All Edges / Internal Edges / External Edges; Extend (the outer edges, a distance) | Same; only loops that touch no other face are removed (the API's rule); none: refused with the reason | A |
| Extend | Edges (outer edges only), Enable Chaining (tangent edges); Distance (an arrow); Extend Type Natural / Perpendicular / Tangent; Edge Alignment Free / Align (Natural only) | Same, except Align Edges (greyed with the reason). Natural carries the face's own surface on where it can (a flat face stays one face; cylinders, cones); Natural and Tangent extend outwards only, Perpendicular both ways | A |
| Stitch | Surface bodies; Tolerance (default 1.0 mm, forum); a closed result becomes a solid; the edges within tolerance are shown green, the ones left open red | Same; the open edges left are drawn red and counted, the ones the stitch closes green (part 2), "Closed" when it makes a solid; a solid picked is refused ("Unstitch it first") | A, F (1.0 mm) |
| Unstitch | Faces or bodies; Chain Selection (on: every face joined to the clicked one) | Same: each face becomes a surface body | A, F |
| Reverse Normal | Surface bodies: every face turned over | Same, a short arrow shows which way each surface faces; a solid is refused (its faces always point out) | A |
| Replace Face, Split Face (SURFACE > MODIFY too) | Faces of solids; the target or tool may be a surface body | Same commands as on the SOLID tab (`direct-modify.md`); since modify-2 Replace Face takes any target surface, a surface body's face included | A |
| Delete | | FreeCAD's / SciForge's Delete, as before | |

## Known gaps

| Fusion | Why not yet |
|---|---|
| Patch Continuity Curvature on stock FreeCAD 1.1.4 | FreeCAD bug: `MakeFilling.add` casts order 2 to `GeomAbs_C1`, which OpenCASCADE's filling ignores (the patch silently came out tangent-less). Fixed by core patch #14 (`docs/sciforge/core-patches.md`); until a full build ships it, the dialog refuses Curvature with the reason (Tangent works). `surface_geom.g2_available()` tells a patched build |
| Patch Tangent onto vertical walls (a tube's rim) | OpenCASCADE's plate surface cannot turn that far (the reached tangency is off by about 90 degrees, measured): refused with the reason instead of a wrong patch. Sloped walls work |
| Patch: Group Edges off (a continuity per edge), Tangency Weight | OpenCASCADE's filling has no tangency weight; per-edge continuity is possible in it but its dialog rows are not built. Both shown greyed with the reason |
| Extrude All after the design changes | All goes through the bodies that were visible when the step was made (they are saved with it, so a reopened design gives the same surface); a body shown or added later is not taken in until the step is edited. Fusion's rule for a later change is not documented (**G**) |
| Extrude From Object with a taper from a slanted or curved start | Refused with the reason: a taper is measured from a start plane, and a curved start has none |
| Sweep Path + Guide Rail: Full Extents / Perpendicular To Path, Path Distance and Guide Rail Distance (**A**) | Not built: the rail sweep runs the share of the path set by Distance (the whole path by default). Needs a second distance handle on the rail and the rule for where Perpendicular To Path stops |
| Loft with three or more rails | Refused with the reason ("one or two rails"): SciForge fits each section to the rails by a turn, move and stretch, which two rails fix exactly; more would need a real multi-rail fit (OpenCASCADE has no rail loft) |
| A closed loft with rails or a centerline | Refused with the reason (Fusion's behaviour not found, **G**) |
| Tangent Edges Merge off by default | Fusion's default was not found (the API page is cut off). Merge is off because OpenCASCADE measures the volume of a merged side (one B-spline face closed round the profile) several percent wrong: a slot lofted to the same slot gives +5.6 % (golden `sf_loft_merge_slot_volume`, expected failure); the shape itself is right (its mesh gives the true volume) |
| Loft rails between profiles that turn | The rail loft fits 8 sections between each pair of profiles: within 1 % of the true shape (a square turned a quarter round two arc rails: 3889 against 3927 mm³, golden `sf_loft_rails_turning`) |
| A closed loft of sketch profiles that twists | OpenCASCADE pairs the profiles' start points as they come; a profile drawn from another corner makes a twisted closed loop (no start-point matching yet) |
| Offset corner type | The research mentions sharp / rounded offset corners (unconfirmed, **F**); SciForge's offset rounds convex corners. Not built while Fusion's option is unconfirmed |
| Extend Edge Alignment Align Edges | Not built (greyed); Natural on a free-form face falls back to a tangent band. OpenCASCADE has no extension that keeps neighbouring extended edges aligned; it needs SciForge's own surface building |
| Boundary Fill from planes alone | Fusion is reported to need at least one body (**F**, one forum report); SciForge accepts planes alone, which does no harm, so it is kept until Luca's Fusion confirms it |
| The design's first sketch body | A new design's first sketch lives in a body (FreeCAD needs one); when the first thing made from it is a surface, that body stays in the browser with only the sketch in it. Fusion keeps sketches outside bodies |
