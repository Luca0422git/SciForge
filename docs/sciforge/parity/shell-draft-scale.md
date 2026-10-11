# Parity spec: Shell, Draft and Scale (outline 7.6)

Source: Fusion's documented behaviour (its Shell reference: Inside/Outside Thickness,
Direction Inside/Outside/Both, Shell Type sharp or rounded) and everyday use. Not yet checked
against Luca's own screen captures (outline 2.4). Implemented in
`src/Mod/SciForge/sciforge/`: `shelling.py` + `shell_ui.py`, `drafting.py` + `draft_ui.py`,
`scale.py` + `scale_ui.py`, with the shared dialog base `pickpanel.py`. Status: **first pass,
not yet signed off**.

## Shell (MODIFY > Shell)

| Fusion | SciForge |
|---|---|
| Shell with nothing selected: the dialog opens and waits for faces or a body | Same. (Before, FreeCAD's Thickness ran and printed "Base feature's TopoShape is invalid".) No solid in the design: a note next to the mouse says to make one first |
| Click faces to take them away, click one again to drop it; faces (or a body) selected before pressing Shell are taken at once | Same. The part before the shell is shown see-through with the picks highlighted, the result solid inside it |
| Pick the body: it becomes hollow (a closed wall, a void inside) | Same: click the body's row in the browser (or select it before Shell). The selection box says "Body" |
| Tangent Chain (on): faces that continue a picked face smoothly are taken too | Same (`shelling.tangent_faces`) |
| Inside Thickness / Outside Thickness, Direction Inside / Outside / Both (both fields for Both) | Same, default 1 mm each, Inside |
| Shell Type: sharp or rounded corners where walls meet outside the part | Same: Sharp / Rounded |
| Blue arrows to drag the thicknesses | Same: on the rim of the first opening (on the face turned toward you for a hollow body), drawn over the part |
| A wall too thick: the dialog says so and OK waits | Same, with the thickest wall that fits ("about 9.99 mm"); the preview keeps the last good result; nothing in the Report view |
| Parameters and formulas in the fields | Same (`wall`, `wall * 2`): stored as an expression, the shell follows the parameter |
| Edit by double-clicking the timeline; Cancel / Esc / Ctrl+Z leave the part as it was; one undo step | Same |

Which feature is made: faces taken away with Inside or Outside is FreeCAD's own
`PartDesign::Thickness` (Join "Intersection" = sharp, "Arc" = rounded, Reversed = inside). A
hollow body or Both is SciForge's `ShellFeature` (a `PartDesign::FeaturePython`), because
FreeCAD's Thickness copies the part unchanged when no face is taken away and has only one
thickness. Editing switches between the two when needed; the step keeps its place and name and
later steps move over to the new one.

## Draft (MODIFY > Draft), type Fixed Plane

| Fusion | SciForge |
|---|---|
| Draft with nothing selected waits for the plane: click an origin plane or a flat face | Same: the big origin squares appear (like Create Sketch) while the Plane box is blue; origin planes from the browser work too |
| The pull direction is shown as an arrow across the plane; a button flips it | Same (blue arrow; the ⇅ button). Out of a picked face, along an origin plane's normal |
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
| Drag handle | Blue arrows on the part's far side that move with it (one for Uniform, three for Non Uniform) |
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
| Scale arrow when shrinking | It moves inside the see-through part, where Coin gives the click to the part; type the factor instead |
| A corner whose name FreeCAD loses (a Pad's corner after its length changes) | The corner with the same number is used: right as long as the part's topology does not change |
