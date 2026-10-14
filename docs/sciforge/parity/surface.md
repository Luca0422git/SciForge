# Parity spec: the SURFACE tab (outline 7.9)

Implemented in `src/Mod/SciForge/sciforge/`: `surface_core.py` (the tools as data and rules,
pure Python), `surface_geom.py` (the geometry), `surface.py` (the steps in the document),
`surface_pick.py` (picked shapes and cells drawn in the view), `surface_ui.py` (the dialogs
and commands). Status: **first pass (2026-10-14), not yet signed off by Luca.**

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
| Extrude | Profiles: sketch curves (open ones too) or edges; Start Profile Plane / Offset / From Object; Direction One Side / Two Sides / Symmetric; Extent Distance / To Object / All; Taper Angle; Operation New Body / New Component | Profile Plane, Offset; the three directions (Symmetric: Half / Whole Length); Distance, To Object (a plane or flat face); a taper per side; New Body / New Component. A straight extrude both ways is one face per curve | A |
| Revolve | Profile, Axis (a line, edge or origin axis), Type Angle / Full, Direction, Angle | Same; Symmetric turns the angle each way (at most 180) | A |
| Sweep | Single Path or Path + Guide Rail; Distance; Orientation; Twist / Taper | Single Path; Distance and Distance Two (a share of the path, when the profile sits inside it); Orientation Perpendicular / Parallel; Twist Angle | A |
| Loft | Profiles (curves, points) in order; rails; Closed | Profiles in a list (Up / Down / Remove), Chain Selection, Closed | A |
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
| Stitch | Surface bodies; Tolerance (default 1.0 mm, forum); a closed result becomes a solid | Same; the open edges left are drawn red and counted, "Closed" when it makes a solid; a solid picked is refused ("Unstitch it first") | A, F (1.0 mm) |
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
| Extrude Start From Object, Extent All, To Object's Chain Faces | Not built (Profile Plane / Offset and Distance / To Object are) |
| Revolve Type To | Not built |
| Sweep Path + Guide Rail, Taper Angle | Not built (the rail choice is greyed with the reason); the solid Sweep has them |
| Loft rails, centerline, end conditions | Not built |
| Offset corner type | The research mentions sharp / rounded offset corners (unconfirmed, **F**); SciForge's offset rounds convex corners |
| Extend Edge Alignment Align Edges | Not built (greyed); Natural on a free-form face falls back to a tangent band |
| Stitch: edges within tolerance shown green | SciForge shows the edges left open (red) |
| Boundary Fill from planes alone | Fusion is reported to need at least one body (**F**); SciForge accepts planes alone |
| The design's first sketch body | A new design's first sketch lives in a body (FreeCAD needs one); when the first thing made from it is a surface, that body stays in the browser with only the sketch in it. Fusion keeps sketches outside bodies |
