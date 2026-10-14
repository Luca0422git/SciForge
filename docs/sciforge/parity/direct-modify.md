# Parity spec: direct modeling and the remaining Modify tools (outline 7.13, 7.3, 7.7)

Capture Design History on/off, Create Base Feature, Press Pull / Offset Face / Delete on bodies
without history, Replace Face, Split Face, Silhouette Split, Align, Remove.

Status: **built, not yet signed off** (branch `sf/direct`; the **Guess** rows and the known
gaps below need checking in Luca's Fusion).

## Fusion's behaviour, researched before building

Autodesk's own sites (help.autodesk.com, forums.autodesk.com) cannot be opened from the
sandbox: the rows below come from the summaries of those pages that web search returns. Each
row says where it comes from: **Autodesk** (help page, API reference, Learn course, support
article), **Forum** (Autodesk Community answer or tutorial) or **Guess** (not found; to be
checked in Luca's Fusion).

### Sources

1. Autodesk help, "Switch a design to Direct Modeling mode" (`ASM-DO-NOT-CAPTURE-DESIGN-HISTORY`)
   and "Design modeling modes" (`ASM-DESIGN-MODELING-MODES`).
2. Autodesk help / Learn, "Activity 2: Edit features using direct modeling"
   (`GUID-C71DA01A-E210-46E7-B61A-04C96DCA1F15`).
3. Autodesk help, "Create a base feature" (`SLD-CREATE-BASE-FEATURE`); Fusion API
   `BaseFeature.startEdit()` / `finishEdit()` (BaseFeature sample).
4. Autodesk Community, "A Question about Base Features" (bodies made outside a base feature
   cannot be changed inside it); "How to re-capture design History??"; "Enabling Capture
   Design History crashes Fusion360" (bodies show as a Base Feature); Autodesk blog "Copy &
   Paste in Fusion" (pasted bodies stay base features).
5. Autodesk support article "Press Pull does not create a timeline feature in Fusion"
   (Offset Type: Automatic / Edit Feature / New Offset) and the Community threads "Offset face
   not added to the timeline, base feature changed instead", "Press/Pull features not adding
   to timeline", "Can't offset just one face".
6. Autodesk help, "Offset faces" (`SLD-OFFSET-FACES`).
7. Autodesk help, Replace Face (`MODEL-REPLACE-FACE-CMD`); Fusion API
   `ReplaceFaceFeatures.createInput(sourceFaces, isTangentChain, targetFaces)`; Community
   "Cannot get replace face to work", "How to replace a face with replace face".
8. Autodesk help, "Divide a face into multiple faces" (Split Face); Fusion API
   `SplitFaceFeatureInput` (default split type, `isSplittingToolExtended`).
9. Autodesk help, "Silhouette Split reference" (`SLD-REF-SILHOUETTE-SPLIT`); Fusion API
   `SilhouetteSplitFeatures.createInput(viewDirection, targetBody, operation)`; Community
   "Silhouette split not working".
10. Autodesk help, Align (`SLD-ALIGN-CMD`); Community "Align Tool: Changing 'angle' sometimes
    'flips' instead" (defect FUS-99810), "Align tool reduced functionality", "How to Align a
    body with origin plane".
11. Autodesk shortcut list (autodesk.com/shortcuts/fusion-360), CAD Forum's Fusion shortcut
    table.
12. Autodesk help, Remove (`SLD-REMOVE`); Community "What is the difference between Delete and
    Remove a Component or Body?", "Delete unwanted body after body split".
13. Autodesk Community: "Delete Face" (ideas: the solid Delete heals, the Patch workspace does
    not), "Trying to delete a face in Fusion", "Deleting faces on a body curve"; Fusion API
    `DeleteFaceFeature` vs `SurfaceDeleteFaceFeature`.
14. Autodesk Community, "Capture Design History off after import?" (STEP files open as
    designs without history).

### Capture Design History (outline 7.3)

| # | Fusion | Source |
|---|---|---|
| H1 | A design is either parametric (history captured, timeline at the bottom) or direct (no history). New designs are parametric. | Autodesk (1) |
| H2 | Turn history off: right-click the design's top row in the browser, "Do not capture Design History" (newer releases: "Change to Direct Modeling Mode"); the same entry is in the timeline's settings menu. | Autodesk (1) |
| H3 | Turning it off asks first (the "Delete Parametric History" dialog, a button of that name and Cancel). Confirmed: the timeline and every parametric feature are removed; the bodies keep their shape. | Autodesk (1) |
| H4 | Without history the timeline is gone; every command still works and changes the bodies directly. Fusion keeps "pseudo features" (extrude, fillet, hole...) in the browser to pick their faces; fillets, chamfers and holes can be edited there, others only dissolved or deleted. | Autodesk (1), Forum (Autodesk engineering director's answer) |
| H5 | Turn history on: right-click the top row, "Capture Design History". The timeline comes back with one Base Feature holding everything made without history; the old features do not come back. | Autodesk (2), Forum (4) |
| H6 | Undo works in both modes; turning history off can be undone. | Forum (tutorial: "history can be restored by undoing") |
| H7 | STEP / IGES files open as designs without history. | Forum (14) |

### Create Base Feature (SOLID > CREATE)

| # | Fusion | Source |
|---|---|---|
| B1 | Only in a parametric design. Starting it puts a Base Feature item in the timeline (at the marker) and opens a direct-modeling environment. | Autodesk (3) |
| B2 | Inside it, operations are not recorded one by one: only the Base Feature shows in the timeline (feature nodes appear in the browser). | Autodesk (3) |
| B3 | Operations inside affect only the base feature's own bodies; a body made before it cannot be picked (e.g. as Body to Split). | Autodesk (3), Forum (4) |
| B4 | Finish Base Feature returns to the parametric design: one timeline item. | Autodesk (3) |
| B5 | The base feature can be edited later (Edit Feature in the timeline): the same environment, then Finish again. The features inside cannot be edited (no record of them). | Autodesk (3) |
| B6 | Press Pull (Automatic) on a face of a base feature's body edits the base feature itself (no new timeline item). | Autodesk (5), Forum (5) |
| B7 | Where "Finish Base Feature" is (a toolbar panel like Finish Sketch) | Guess |

### Press Pull, Offset Face and Delete on bodies without history (outline 7.0, 7.13)

| # | Fusion | Source |
|---|---|---|
| P1 | Press Pull's Offset Type: Automatic (default: edit the feature that made the face), Edit Feature, New Offset (an Offset Face item in the timeline). On an imported body Automatic edits its Base Feature. | Autodesk (5), Forum (5) |
| P2 | Modify > Offset Face: pick faces (Ctrl adds), drag the arrow or type a distance, OK: an Offset Face item in the timeline, double-click to edit. | Autodesk (6) |
| P3 | In a design without history the same commands change the body at once (nothing recorded). | Autodesk (1) |
| P4 | Delete with faces selected (solid): the faces go and the neighbours are extended to close the solid (heal); a face whose neighbours cannot close the gap is refused (Fusion's surface Delete Face leaves a hole instead). | Forum (13) |
| P5 | Deleting a whole feature's faces (all faces of a boss, a hole's wall, a fillet) removes the feature from the solid. | Forum (13) |

### Replace Face (SOLID > MODIFY)

| # | Fusion | Source |
|---|---|---|
| R1 | Dialog: Source Faces (faces of one body, to remove), Tangent Chain (default on), Target Faces (solid faces, surface faces/bodies or construction planes). | Autodesk (7) |
| R2 | The source faces are removed, the faces around them are extended or trimmed to the target, the new face at the target is stitched in. | Autodesk (7) |
| R3 | The target must fully cross the region being extended or trimmed, else it fails. | Autodesk (7), Forum (7) |
| R4 | A Replace Face item in the timeline, editable; live preview. | Autodesk (7) (feature object), Guess (preview) |

### Press Pull Offset Type, Replace Face onto any surface (modify-2, 2026-10-14)

Sources: (5) above; Autodesk help, Press Pull reference (`SLD-REF-PRESS-PULL`: a face is
offset or moved, a sketch profile extruded; Press Pull can turn into Extrude); Autodesk blog
"QUICK TIP: Press Pull" and "QUICK TIP: Offset Face Control"
(https://www.autodesk.com/products/fusion-360/blog/quick-tip-press-pull/,
https://www.autodesk.com/products/fusion-360/blog/quick-tip-control-offset-faces/); Autodesk
Community "Can't modify from existing radius with press pull"
(https://forums.autodesk.com/t5/fusion-support-forum/can-t-modify-from-existing-radius-with-press-pull/td-p/8858232).

| # | Fusion | SciForge | Source |
|---|---|---|---|
| O1 | Press Pull on faces has an Offset Type: Automatic (the default), Modify Existing Feature, New Offset | Same three, Automatic chosen (hidden for Offset Face, which always adds its step, and when editing a Press Pull step) | Autodesk (5), Forum (5) |
| O2 | Modify Existing Feature: the feature that made the face changes, no new timeline item | The end face of an extrude (one side, Distance) makes that extrude longer or shorter; a face an earlier Press Pull / Offset Face put there changes that step's distance; the dialog names the step that changes. A face no feature can change that way (a side face, a fillet's face, faces of two features) is refused with the reason and "use New Offset"; a distance that follows a parameter is refused too (change the parameter) | Autodesk (5), Forum (5) |
| O3 | New Offset: always a new Offset Face / Press Pull item | Same (a Press Pull step; a fillet's face is offset, not given another radius) | Autodesk (5) |
| O4 | Automatic: Fusion edits the feature that made the face when it can (a fillet's radius, a base feature), else adds an offset | As before modify-2: a fillet's or chamfer's face changes its size, inside an open base feature the change is baked into it, every other face gets a Press Pull step. Whether Automatic also lengthens an extrude when its end face is pulled is not settled by the sources (Modify Existing Feature does it) | Autodesk (5), Guess (extrude end) |
| Q1 | Replace Face onto a curved target (a cone, a torus, a free-form surface face) | Any surface OpenCASCADE gives: the target is extended a quarter of its size beyond its edges (a cone not past its apex) so it crosses the faces' way; its inner side is found by sweeping it backward along the replaced faces' direction. Flat, cylinder and ball targets keep their exact rule. A target that still does not cross the faces' way is refused with the reason | Autodesk (7) |

### Split Face (SOLID > MODIFY)

| # | Fusion | Source |
|---|---|---|
| S1 | Dialog: Faces to Split, Splitting Tool (sketch curves, a face, a construction plane), Extend Splitting Tool, Split Type. | Autodesk (8) |
| S2 | Split Type: Split with Surface (default: where the tool surface crosses the face), Along Vector (the tool projected along an edge, a face's normal or an axis), Closest Point (the tool projected to the nearest point of the face). | Autodesk (8) |
| S3 | Extend Splitting Tool (Split with Surface only) extends the tool so it crosses the whole face. | Autodesk (8) |
| S4 | The body stays one body with more faces; a Split Face item in the timeline. | Autodesk (8) |

### Silhouette Split (SOLID > MODIFY)

| # | Fusion | Source |
|---|---|---|
| L1 | Dialog: View Direction (construction axis, straight edge, flat face or plane), Target Body, Operation. | Autodesk (9) |
| L2 | Operation Split Faces Only: the body's faces are split along its outline seen from that direction; it stays one body. | Autodesk (9) |
| L3 | Split Solid Body: the body is split into two at the outline, which must lie in one plane. | Autodesk (9), Forum (9) |
| L4 | Split Shelled Body: for a shelled (hollow) body, split into two. | Autodesk (9) |
| L5 | It fails on bodies whose outline it cannot find (simple shapes work: a sphere). | Autodesk API note, Forum (9) |

### Align (SOLID > MODIFY)

| # | Fusion | Source |
|---|---|---|
| A1 | Dialog: Objects (Bodies / Components), From (geometry on the object that moves: a point, a line, a plane, a circle, a coordinate system), To (geometry it goes to). | Autodesk (10) |
| A2 | Flip turns the result 180 degrees; Angle turns it 90 degrees per click. | Autodesk (10), Forum (10) |
| A3 | Moves without making a relationship (later changes do not keep it aligned). | Autodesk (10) |
| A4 | An Align item in the timeline, double-click to edit. | Autodesk (10) |
| A5 | Two faces picked end up in one plane, facing each other (a block's bottom put on a top face sits on it). | Forum (10: "the faces end up aligned"), Guess (facing each other) |
| A6 | Key: none. Fusion's A is Appearance (the SciForge ribbon showed "A" beside Align). | Autodesk (11) |

### Remove (SOLID > MODIFY)

| # | Fusion | Source |
|---|---|---|
| X1 | Modify > Remove, or Remove in a body's / component's right-click menu: a Remove item in the timeline for each body or component removed. | Autodesk (12) |
| X2 | The body is gone from that point of the timeline on; rolling the marker before the Remove (or deleting the Remove item) brings it back. Delete instead deletes the features that made the body. | Forum (12) |
| X3 | Typical use: throw away one half after a Split Body. | Forum (12) |

## What SciForge does (and how it maps onto FreeCAD)

Code (all in `src/Mod/SciForge/sciforge/`):

| File | What |
|---|---|
| `direct_core.py` | Qt-free rules (unit tested): which steps a bake removes, base feature ids and titles, the history menu label, what Delete says when the gap cannot close |
| `direct.py`, `direct_ui.py` | Capture Design History on/off, Create / Finish Base Feature, editing a base feature, solids without history made into bodies, the bake after each command |
| `presspull_ui.py`, `presspull.py` | Press Pull on solids without history; Offset Face (Modify > Offset Face) |
| `delete.py` | Delete on faces of solids without history; the healing refusal |
| `replace_face.py`, `replace_face_ui.py` | Replace Face |
| `split_face.py`, `split_face_ui.py` | Split Face |
| `silhouette.py`, `silhouette_ui.py` | Silhouette Split |
| `align_core.py`, `align.py`, `align_ui.py` | Align (the maths is Qt-free and unit tested) |
| `remove.py`, `remove_ui.py` | Remove |
| `modify_common.py` | what the Modify dialogs share (a click on a solid without history makes it a body; the origin squares) |

### The model: how a design "without history" is kept in FreeCAD

FreeCAD has no direct-modeling mode. SciForge keeps every body a PartDesign Body in both
modes, so every SciForge command works the same way on it, and stores the difference in the
body's **first step**:

* A body without history has exactly one solid step: FreeCAD's `PartDesign::FeatureBase`,
  which takes its solid from a hidden plain `Part::Feature` (the "base shape", Label
  "Body (base)", it lives in the body's component because FreeCAD refuses links out of a
  component). Sketches and construction planes stay in the body.
* "Baking" a change: the command builds its step exactly as in a parametric design (same
  code, same preview), and when it is OK'd the result is copied into the base shape and the
  new steps are deleted, all inside the command's own undo step (`preview.end_transaction`,
  `taskui._end_transaction` and `delete.run` call `direct.takes_commit` /
  `bake_before_commit`; a FreeCAD command that commits by itself is baked as an undo step of
  its own). So Ctrl+Z / Ctrl+Y undo and redo a direct edit like any other.
* Whether the design captures history is a hidden `App::FeaturePython` "SciForgeDesign"
  (`CaptureHistory`), not the document's metadata: an object property is undone with Ctrl+Z,
  metadata is not.
* A base feature in a parametric design is the same thing: the body's first step, marked with
  a base feature id (`SciForgeBaseId`) so the timeline shows it as "Base Feature N".

| Fusion | SciForge |
|---|---|
| H1, H2: the design's right-click menu "Do not capture Design History"; also in the timeline's settings menu | same entry in the browser's top row menu and in the timeline's settings (gear) menu |
| H3: the question before the history goes (Delete Parametric History / Cancel) | a question in SciForge's own words: Remove History / Cancel. Cancel keeps everything |
| H3: the timeline and every feature removed, the bodies keep their shape | every body is baked into one frozen step; the timeline panel hides; the sketches and construction planes stay; bodies a Combine or a Remove used up are deleted (they are not in the design any more) |
| H4: every command changes the bodies directly | Press Pull, Offset Face, Fillet, Extrude (join / cut / new body), Delete on faces, Replace Face, Split Face, Align, Move, Combine...: the command's step is baked at OK, nothing is recorded |
| H5: Capture Design History: a new timeline starting with one Base Feature | the entry (same menu) brings the timeline back; each body's frozen step becomes a Base Feature (they share one base feature id); later commands are steps again |
| H6: undo in both modes | turning history off and on are one undo step each; direct edits undo and redo |
| H7: STEP files open without history | FreeCAD's own STEP import gives plain solids (no body). The first Press Pull, Offset Face, Delete on a face or Modify pick on one makes it a body whose base feature holds the imported solid; the import is then hidden (Cancel shows it again). The same works for any plain solid (a converted mesh, a Part workbench solid) |
| B1, B2, B4: Create Base Feature, edits not recorded one by one, Finish Base Feature, one timeline item | CREATE > Create Base Feature opens a bar over the view ("Finish Base Feature" button, also in the CREATE menu). Bodies made while it is open belong to it: whatever is done to them (sketches, extrudes, Press Pull, Delete, fillets...) is baked into their base feature at each OK, their sketches leave the timeline. Finish closes it |
| B5: edit the base feature later | double-click "Base Feature N" in the timeline: the marker rolls back to it, the bar says what is edited, edits on its bodies are baked into it (no new step), Finish puts the marker back where it was and the later steps rebuild on the edited solid |
| B6: Press Pull (Automatic) on a face of a base feature edits it | in a parametric design Press Pull adds a Press Pull step after the base feature (Fusion's "New Offset"); inside an open base feature it is baked into it |
| O1-O4: Press Pull Offset Type | Automatic / Modify Existing Feature / New Offset in the Press Pull dialog (`offset_type.py`) |
| P2: Modify > Offset Face, an Offset Face item, double-click to edit | same (Press Pull's faces mode without its fillet / sketch-area modes); the step is titled "Offset Face N" |
| P4, P5: Delete on faces heals; refused when the neighbours cannot close the gap | same (OpenCASCADE's `BRepAlgoAPI_Defeaturing`); the refusal says why and what to do instead, next to the pointer, nothing changes |
| R1-R4: Replace Face | Source Faces (one body), Tangent Chain (on by default), Target (a face of any body, an origin square, a construction plane); live preview; a "Replace Face N" step, editable. The target must lie across the faces' way, else the reason is said in the dialog and OK keeps it open. A step sees the design as it is at its place in the timeline: editing the target's own earlier step moves the replaced faces with it |
| S1-S4: Split Face | Faces to Split, Splitting Tool (a sketch or one of its curves, an origin square, a construction plane, a face of any body, another body), Split Type (Split with Surface by default, Along Vector with its Direction, Closest Point), Extend Splitting Tool (off by default, only for Split with Surface); one body with more faces; a "Split Face N" step |
| L1-L5: Silhouette Split | View Direction (an origin square or construction plane, an axis, a straight edge, a flat face, a cylinder's axis; a ball's face gives none and is refused), Target Body, Operation Split Faces Only (default) / Split Solid Body (refused when the outline is not flat, as in Fusion) / Split Shelled Body; split pieces become new bodies like Split Body's |
| A1-A6: Align | Objects (Bodies / Components), From, To, Flip, Angle (90 degrees per click about the To geometry); two flat faces end up facing each other; an "Align N" step (bodies: a step in the body; components: a step outside the bodies that set the component's placement, deleting it puts the component back); no key (A is Appearance) |
| X1-X3: Remove | Modify > Remove (selection first, or a dialog that waits for clicks) and Remove in a body's / component's browser menu: a "Remove N" step per body (named after the component for a component); the body hides and leaves the browser; rolling the marker before it, deleting or suppressing it brings the body back. In a design without history Remove deletes (there is no timeline to hold it) and says so |

### Tested

Scenarios (real mouse and keyboard in FreeCAD 1.1.4 under xvfb): `direct_history`,
`direct_step_box`, `direct_base_feature`, `direct_components`, `direct_commands`, `modify_replace_face`,
`modify_split_face`, `modify_silhouette`, `modify_align`, `modify_remove`. Golden models
(`golden/models/direct_*.json`, analytic numbers): Replace Face up / edited down, Split Face
(origin plane, then a Press Pull on one half, Closest Point, Extend), Silhouette Split (faces,
solid, edited back), Align (faces facing, Flip + Angle), Remove, history off / on with a Press
Pull after it. Unit tests: `test_direct_core.py`, `test_align_core.py`,
`test_direct_schema.py`. modify-2: scenario `modify2_presspull_type` (Modify Existing Feature on an extrude's end, undo / redo, New Offset, Modify Existing on that offset, a side face refused); golden models `modify2_presspull_modify_extrude`, `modify2_presspull_modify_pocket`, `modify2_presspull_modify_offset`, `modify2_presspull_new_offset`, `modify2_replace_face_cone`.

## Known gaps (never faked: listed here)

| Fusion behaviour | SciForge now | Why |
|---|---|---|
| Capture Design History makes one Base Feature for all bodies | one "Base Feature" item per body (they share an id, editing one opens a session for that body) | FreeCAD's base is a step of each body; one item for several bodies needs the timeline module to group items by id |
| Fusion keeps "pseudo features" (extrude, fillet, hole) in the browser of a direct design, editable for fillets / chamfers / holes | not built: the features are baked away; sketches stay | nothing of a baked feature is left to edit; would need a recognizer of fillets / holes in a plain solid |
| Press Pull Modify Existing Feature on a base feature's face, a revolve's or a sweep's face, a hole's wall | refused with the reason (use New Offset): only an extrude's end and an earlier Press Pull's faces are changed in place | each kind of feature needs its own rule for which value moves the face; base features would need the bake of an open base feature |
| Press Pull Automatic on an extrude's end face | adds a Press Pull step (Modify Existing Feature lengthens the extrude) | the sources do not settle what Fusion's Automatic does there; 32 Press Pull scenarios rely on the step |
| B3: an open base feature refuses bodies made before it | they can be changed; those changes are recorded as normal steps (with their own timeline items), not baked into the base feature | refusing would block Luca's common case (pull a face of another body while a base feature is open) without a gain; documented here |
| a base feature open while the design is saved | saving keeps the marker where the session put it; reopening shows the design rolled back to the base feature, without the session (double-click the base feature and Finish, or drag the marker to the end) | the session lives in memory, not in the file |
| Replace Face onto a curved target that ends before the faces' way | the target is extended by a quarter of its size; farther than that is refused with the reason | OpenCASCADE extends a free-form surface only approximately; a big extension of a NURBS face can turn back on itself |
| faces split by Split Face stay split whatever comes later | they stay split until a later step that tidies faces (Refine: an Extrude join, a Press Pull of the neighbour) merges faces lying in one plane again | FreeCAD's `removeSplitter` merges coplanar faces; SciForge's steps refine like Fusion's |
| Split Shelled Body on a closed shelled body: the parting surface between inner and outer outline | a non-flat outline is swept along the view direction to make the parting surface; inner outlines hidden behind the outer surface are not used | OpenCASCADE's outline (`HLRBRep`, `reflectLines` "OutLine") gives the visible outline only |
| Silhouette Split along a direction where the outline is only existing edges (a box seen along its diagonal) | refused with the reason | the outline then is the box's own edges: nothing to split |
| Rolling the timeline marker back before a component's Align puts the component back | the component stays where the Align put it (Undo or deleting the Align step does put it back) | the step lives outside the bodies and only recorded the move; the marker moves bodies' steps |
| Remove of a component | its bodies get Remove steps and hide; the component's row stays in the browser | the browser module lists components whatever their bodies do |
| A STEP file opened from the Data Panel / Open opens as a design without history | FreeCAD's import adds plain solids to the open (parametric) design; they become bodies on the first edit | opening files is the insert / versions modules' area |
| the plain solids FreeCAD's STEP import makes are listed in the timeline with the importer's name (e.g. "Open CASCADE STEP translator 7.8 2") until edited | as said | the timeline module lists every plain solid; when one is made a body it is hidden behind the body's Base Feature |
