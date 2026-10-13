# Parity spec: direct modeling and the remaining Modify tools (outline 7.13, 7.3, 7.7)

Capture Design History on/off, Create Base Feature, Press Pull / Offset Face / Delete on bodies
without history, Replace Face, Split Face, Silhouette Split, Align, Remove.

Status: **being built** (branch `sf/direct`).

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

(Filled in as each part is built and tested.)
