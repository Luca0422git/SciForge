# Parity spec: Shell, Draft and Scale (outline 7.6)

Source: Fusion's documented behaviour (its Shell reference: Inside/Outside Thickness,
Direction Inside/Outside/Both, Shell Type sharp or rounded) and everyday use. Not yet checked
against Luca's own screen captures (outline 2.4). Implemented in
`src/Mod/SciForge/sciforge/`: `shelling.py` + `shell_ui.py`, `drafting.py` + `draft_ui.py`,
`scale.py` + `scale_ui.py`, with the shared dialog base `pickpanel.py` and `follow.py` (later
steps keep their faces). Status: **first pass + QA pass (2026-10-11), not yet signed off**.

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

## Draft (MODIFY > Draft), type Fixed Plane

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
Reversed worked out from the pull direction).

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
| Draft type Parting Line, Draft Sides Two Sides / Symmetric | They split faces at a line; FreeCAD's Draft cannot. Shown greyed with the reason |
| Scale of sketches and components | SciForge scales bodies (the step lives in a body's timeline) |
| Non uniform scale of round faces | Exact shape, but the faces become NURBS: FreeCAD then measures their volume only to about 1 % and Refine cannot merge flat NURBS faces |
| Shell / Draft / Scale over several bodies in one step | One body per step (Fusion allows several) |
| Per-face wall thickness (outline 7.6 mentions it) | Not in Fusion's Shell dialog; OpenCASCADE supports it but FreeCAD exposes no Python call |
| A corner whose name FreeCAD loses (a Pad's corner after its length changes) | The corner with the same number is used: right as long as the part's topology does not change |
| A face of a later step that moved for good (a wall made thicker) | Found again by where it is (same kind, facing the same way, nearest): right for the usual edits; FreeCAD has no history of SciForge's own features' faces to follow instead |

## Value boxes and typing over the view (2026-10-13)

Every drag handle of this dialog has a value box beside it (`taskui.ValueBoxes`): it shows the
field's text with units, follows the handle, takes a value or formula (Enter = OK, a click away
keeps it), never covers a handle or another box, and goes with the dialog. A digit, minus or
decimal point typed with the mouse over the 3D view goes into the box of the handle last dragged
or hovered (else the main one), with its text selected (`taskui.TypeOverView`; FreeCAD's view
keys 0-6 no longer turn the view while the dialog is open). Which handle a digit goes to is
SciForge's guess at Fusion's rule.
