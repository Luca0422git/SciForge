# Parity spec: Shell, Draft and Scale (outline 7.6)

Source: Fusion's documented behaviour (its Shell reference: Inside/Outside Thickness,
Direction Inside/Outside/Both, Shell Type sharp or rounded) and everyday use. Not yet checked
against Luca's own screen captures (outline 2.4). Implemented in
`src/Mod/SciForge/sciforge/`: `shelling.py` + `shell_ui.py`, `drafting.py` + `draft_ui.py`,
`scale.py` + `scale_ui.py`, with the shared dialog base `pickpanel.py` and `follow.py` (later
steps keep their faces). Status: **first pass + QA pass (2026-10-11), not yet signed off**.

## Behaviour spec: Parting Line, Two Side / Symmetric, several bodies, sketches (modify-2, 2026-10-14)

Sources (A = Autodesk help or API reference; F = Autodesk Community forum; G = guess, to be
checked against Fusion):

1. Autodesk help, Draft reference (`SLD-REF-DRAFT`)
   (https://help.autodesk.com/cloudhelp/ENU/Fusion-Model/files/SLD-REF-DRAFT.htm): Type Fixed
   Plane / Parting Line; Parting Line: Fix Parting Line with Draft Sides One Side / Two Side /
   Symmetric (Angle 1, Angle 2), Move Parting Line with Direction Angle Above / Below / Both
   and Fixed Edges.
2. Fusion API, `DraftFeatureInput` (`setSingleAngle`, `setTwoAngles`, `isTangentChain`,
   `isDirectionFlipped`; symmetric: "the faces are split along the parting plane and drafted
   independently using the same angle")
   (https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_DraftFeatureInput.htm),
   `PartingLineTypes`
   (https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_PartingLineTypes.htm).
3. Autodesk Community, "Closed parting line generation discussion"
   (https://forums.autodesk.com/t5/fusion-360-feedback-hub/closed-parting-line-generation-discussion/td-p/9067940).
4. Autodesk help, "Scale components, bodies, or sketches"
   (https://help.autodesk.com/cloudhelp/ENU/Fusion-Model/files/GUID-D3F6F79B-1498-48B3-B98C-7D57B620005A.htm)
   and the Scale reference (`SLD-REF-SCALE`); Fusion API `ScaleFeatureInput`
   (non-uniform scale is not allowed when sketches are among the input entities)
   (https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/ScaleFeatureInput.htm).
5. Autodesk Community, "Scale an entire sketch?" (an Autodesk team member: select the sketch
   node in the browser as the object, a default point is given, Point select picks another)
   (https://forums.autodesk.com/t5/fusion-design-validate-document/scale-an-entire-sketch/m-p/9486135);
   "Non uniform scale missing"
   (https://forums.autodesk.com/t5/fusion-support/non-uniform-scale-missing/td-p/9331453).
6. Autodesk help, Shell reference (Faces/Body selection) and the Fusion part-modelling course
   (https://app.learn-one.autodesk.com/learn/ondemand/curated/part-modeling-fusion-360/1LuvJoGK6tGIzuv0tQrbBz);
   Autodesk Community "Hollowing / Shell a complex Body"
   (https://forums.autodesk.com/t5/fusion-design-validate-document/hollowing-shell-a-complex-body/m-p/10835233).

| # | Fusion | SciForge | Source |
|---|---|---|---|
| D1 | Draft Type: Fixed Plane or Parting Line | Same (a Type drop-down at the top) | A (1) |
| D2 | Parting Line: Pull Direction (a plane or flat face), Parting Tool (a plane, a flat face, edges, sketch curves), Faces | Same three boxes, in that order: after the pull direction the Parting Tool box takes the clicks, then the Faces box. A construction plane's or an origin plane's browser row works as the parting tool | A (1, 2) |
| D3 | Fix Parting Line: the faces turn about the parting line, which stays where it is | Same: each picked face is split at the parting line; every piece turns about where it meets the line | A (1) |
| D4 | Move Parting Line (the line moves, Angle Above / Below / Both, Fixed Edges) | Listed but greyed, with the reason in its tooltip (the draft would have to add a step face where the line moved: OpenCASCADE's draft cannot) | A (1); limit: kernel |
| D5 | Draft Sides One Side: only the pull side of the parting line is drafted | Same | A (1) |
| D6 | Two Side: both sides, Angle 1 on the pull side, Angle 2 on the other, each leaning away from the line | Same (Angle 1 / Angle 2 fields; Angle 2 shows only for Two Side) | A (1, 2) |
| D7 | Symmetric: both sides, one angle | Same | A (1, 2) |
| D8 | Draft Sides also for Fixed Plane (the plane splits the faces) | Same: Two Side / Symmetric on a Fixed Plane split the faces at the plane | A (2) |
| D9 | OK without a parting tool | Refused, the dialog says the parting tool is missing | G |
| D10 | One Draft over faces of several bodies | Same: a face of another body joins the step; that body gets a hidden step (the Draft's follower) that drafts its faces with the same pull direction, parting tool and angles; undo, the timeline's Delete, suppress and the marker treat them as one step | G (Fusion features act on several bodies) |
| S1 | Shell: faces of several bodies (or several bodies) in one Shell | Same: clicking a face of another body adds that body to the step (its own hidden step, same thicknesses and type); clicking its last face again drops it. The selection box says "N faces + K other bodies" | G (6) |
| S2 | Scale: several bodies in the Entities box | Same: every clicked body is scaled by the same factor about the same point (one step, hidden steps in the other bodies). After the first body the Point box takes the next click (as before); click the Entities box again to add bodies | A (4) |
| S3 | Scale: a sketch (its browser row, or the sketch selected before Scale) | Same: the sketch's curves are scaled about the point (the design origin until a point is picked) in its own plane; its driving dimensions are scaled with it, a dimension that follows a parameter keeps its value (the dialog says which). The step is a "Scale" item in the timeline; editing it scales from the sketch as drawn; deleting it puts the sketch back | A (4), F (5); point default G |
| S4 | Scale Type Non Uniform with a sketch | Refused with the reason (Fusion scales sketches uniformly) | A (4) |

## Shell (MODIFY > Shell)

| Fusion | SciForge |
|---|---|
| Shell with nothing selected: the dialog opens and waits for faces or a body | Same. (Before, FreeCAD's Thickness ran and printed "Base feature's TopoShape is invalid".) No solid in the design: a note next to the mouse says to make one first |
| Click faces to take them away, click one again to drop it; faces (or a body) selected before pressing Shell are taken at once | Same. The part before the shell is shown see-through with the picks highlighted, the result solid inside it |
| Pick the body: it becomes hollow (a closed wall, a void inside) | Same: click the body's row in the browser (or select it before Shell). The selection box says "Body" |
| Tangent Chain (on): faces that continue a picked face smoothly are taken too | Same (`shelling.tangent_faces`) |
| Inside Thickness / Outside Thickness, Direction Inside / Outside / Both (both fields for Both) | Same, default 1 mm each, Inside |
| Shell Type: sharp or rounded corners where walls meet outside the part | Same: Sharp / Rounded |
| Blue arrows to drag the thicknesses | Same: on the rim of the first opening, on the side turned toward you (also on a round rim), or on the face turned toward you for a hollow body; drawn over the part and grabbed where they are seen (also inside the see-through part). Dragged through the surface: the thinnest wall; the arrow stays after a 0 or a typo |
| A cup (round part) with a 1 mm wall | Works. (Before the QA pass every wall of a round part drawn on screen was refused as "too thick": FreeCAD's box of a drawn cylinder is a little too small) |
| A wall too thick: the dialog says so and OK waits | Same, with the thickest wall that fits ("about 9.99 mm"); the preview keeps the last good result; nothing in the Report view |
| Parameters and formulas in the fields | Same (`wall`, `wall * 2`): stored as an expression, the shell follows the parameter |
| Edit by double-clicking the timeline; Cancel / Esc / Ctrl+Z leave the part as it was; one undo step | Same; Esc while dragging an arrow too |
| Later steps survive an edit of the shell (a sketch on its floor, a boss, a Press Pull on its wall) | Same, also when the edit changes how the shell is made (Inside to Both, faces to body): the later steps keep their faces (`follow.py`, golden `sf_shell_swap_presspull_follows`, `sf_shell_both_edit_presspull`) |
| Change Parameters lists the shell's thicknesses | Same (also for SciForge's own shell: the thicknesses its Direction uses) |

Which feature is made: faces taken away with Inside or Outside is FreeCAD's own
`PartDesign::Thickness` (Join "Intersection" = sharp, "Arc" = rounded, Reversed = inside). A
hollow body or Both is SciForge's `ShellFeature` (a `PartDesign::FeaturePython`), because
FreeCAD's Thickness copies the part unchanged when no face is taken away and has only one
thickness. Editing switches between the two when needed; the step keeps its place and name and
later steps move over to the new one.

## Draft (MODIFY > Draft), type Fixed Plane (Parting Line: D1-D10 above)

| Fusion | SciForge |
|---|---|
| Draft with nothing selected waits for the Pull Direction: click an origin plane or a flat face | Same: the box is called Pull Direction; the big origin squares appear (like Create Sketch) while it is blue; origin planes from the browser work too. A flat face clicked first becomes the pull direction (its x clears it) |
| The pull direction is shown as an arrow; clicking it, or the flip button, flips it | Same (blue arrow beside the part, so it never covers a face to click; the ⇅ button). Out of a picked face, along an origin plane's normal |
| Then the Faces box takes the clicks; click a picked face again to drop it; Tangent Chain | Same. Faces that cannot be tilted (parallel to the plane, round faces with another axis) do not light up |
| Angle field and an angle handle; positive angles make the part narrower toward the pull direction | Same; the curved blue handle sits on the drafted face's continuation beyond the plane, outside the part, so it can always be grabbed |
| An impossible draft is explained in the dialog | Same ("cannot be tilted this far"); FreeCAD's Draft often fails without any text, or skips a face silently (both caught) |
| Works on any body | Same: the first click on another body moves the dialog there |
| Edit from the timeline, Cancel, Esc, Ctrl+Z | Same |

Built on FreeCAD's `PartDesign::Draft` (NeutralPlane = the picked plane, PullDirection empty,
Reversed worked out from the pull direction). Parting Line, Two Side and Symmetric are
SciForge's `DraftFeature` (`PartDesign::FeaturePython`, `drafting.py`): the picked faces are
split at the parting line (`generalFuse` with the plane or the parting curves swept along the
pull direction), and every group of pieces that turns about the same line is drafted by
FreeCAD's own Draft in a hidden throw-away document. Changing the Type or Draft Sides in an
edit switches between the two features; later steps and the hidden steps in other bodies
move over.

## Scale (MODIFY > Scale)

| Fusion | SciForge |
|---|---|
| Scale with nothing selected waits for the entities | Same: click the part (any face) or its browser row |
| Point: the scale point | Starts at the body's origin; click a corner of the part (click it again to go back to the origin), or a point in the browser |
| Scale Type Uniform (Scale Factor) / Non Uniform (X / Y / Z Scale) | Same |
| Drag handle | Blue arrows on the part's far side that move with it (one for Uniform, three for Non Uniform); they can be grabbed again after shrinking the part (inside the see-through part); dragged through the scale point: the smallest factor |
| Later steps survive an edit of the scale (a sketch on the scaled top, a Press Pull), also Uniform to Non Uniform | Same (golden `sf_scale_non_uniform_keeps_faces`) |
| Change Parameters lists the factors | Same (the ones the Scale Type uses) |
| Edit from the timeline, Cancel, Esc, Ctrl+Z | Same |

Built as SciForge's `ScaleFeature` (`PartDesign::FeaturePython`) in the body's timeline. A
corner used as the point follows edits of earlier steps.

## Known gaps

| Fusion | Why not yet |
|---|---|
| Draft Move Parting Line (Angle Above / Below / Both, Fixed Edges) | Greyed with the reason: the parting line moving needs a new step face along it, which OpenCASCADE's draft (BRepOffsetAPI_DraftAngle) does not make |
| Draft Parting Line that bends inside one face (a 3D curve, or a stepped line crossing one face) | Each piece of a face turns about one line (its longest edge on the parting line); a parting line that is not flat where it meets a face is refused with the reason |
| Draft, Shell, Scale handles for the new options | Angle 2 has no handle of its own (typed in its field); the Angle handle drives Angle 1 |
| Scale of components | Belongs to the components area (components-2) |
| Rolling the history marker back before a sketch's Scale step | The sketch stays scaled (the step changed the sketch itself; Undo or deleting the step puts it back) |
| A sketch's Scale default point | The design origin (Fusion gives "a default point", not documented which) |
| Non uniform scale of round faces | Exact shape, but the faces become NURBS: FreeCAD then measures their volume only to about 1 % and Refine cannot merge flat NURBS faces |
| Sharp shell walls on some parts (a narrow slot open at the side of the part) | OpenCASCADE's sharp (intersection) walls give up where rounded ones work: the dialog says so and suggests Shell Type Rounded (before modify-2 it said "too thick") |
| Per-face wall thickness (outline 7.6 mentions it) | Not in Fusion's Shell dialog; OpenCASCADE supports it but FreeCAD exposes no Python call |
| A corner whose name FreeCAD loses (a Pad's corner after its length changes) | Found again where it was relative to the part's bounding box (`picks.py`, 2026-10-14; before: the corner with the same number, right only while the topology stays) |
| A face of a later step that moved for good (a wall made thicker) | Found again by where it is (same kind, facing the same way, nearest): right for the usual edits; FreeCAD has no history of SciForge's own features' faces to follow instead |

## Value boxes and typing over the view (2026-10-13)

Every drag handle of this dialog has a value box beside it (`taskui.ValueBoxes`): it shows the
field's text with units, follows the handle, takes a value or formula (Enter = OK, a click away
keeps it), never covers a handle or another box, and goes with the dialog. A digit, minus or
decimal point typed with the mouse over the 3D view goes into the box of the handle last dragged
or hovered (else the main one), with its text selected (`taskui.TypeOverView`; FreeCAD's view
keys 0-6 no longer turn the view while the dialog is open). Which handle a digit goes to is
SciForge's guess at Fusion's rule.
