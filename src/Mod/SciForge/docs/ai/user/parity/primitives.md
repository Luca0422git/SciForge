<!-- A copy of docs/sciforge/parity/primitives.md for AI models, made by tools/sciforge/make_ai_docs.py: edit the original, then run the script. -->

# Parity spec: Box, Cylinder, Sphere, Torus, Coil, Pipe (outline 7.6, Primitives)

Source: Fusion's documented behaviour for SOLID > CREATE > Box / Cylinder / Sphere / Torus /
Coil / Pipe and everyday use. Not yet checked against Luca's own screen captures (outline
2.4). Implemented in `src/Mod/SciForge/sciforge/`: `primitives_core.py` (no FreeCAD needed:
rounding, size checks, volumes, the automatic operation), `primitives.py` + `primitives_ui.py`
(Box, Cylinder, Sphere, Torus and the shared dialog base), `coil.py` + `coil_ui.py`,
`pipe.py` + `pipe_ui.py`, `undo_links.py` (see "FreeCAD bug" below). Status: **first pass,
not yet signed off**.

## Values past what fits stop at the limit (Luca's decision, 2026-10-21)

**This deliberately differs from Fusion.** Fusion refuses a value that does not fit (a
radius too big, a wall too thick, an angle too steep) with an error, and the dialog waits
until a smaller value is typed. Luca (2026-10-21): "limit edits to stop at that limit, so if
I want to chamfer something to the max I can quickly drag it without having to type
whatever obscure value the error spits out", and "add the functionality to any tool that
can give that sort of error". So in SciForge (shared helper `sciforge/value_limits.py`):

- an arrow (or disc) dragged past the limit stops there, like the end of a slider; the
  preview shows that result and a blue note under the message says "Largest that fits
  here: 3.47 mm" ("Furthest that fits here" for a limit on the other side: a push into the
  part, a negative angle); OK works at once;
- a plain number typed past the limit is set to it and the note says so: "5 mm does not
  fit: limited to 3.47 mm" (the box keeps what is being typed and shows the limit once it
  is left);
- the limit is found once (a time-budgeted bisection), rounded toward the safe side to the
  box's precision (0.01 mm, 0.1 deg) and built once more to be sure; it is kept for the
  inputs it was found for (the part, the picks, the other values), so a drag never runs a
  search on every mouse move;
- a value from a formula or parameter ("width / 2") is never rewritten: the dialog keeps
  the explanation, with "Largest that fits here: ..." added, and OK waits.

In these dialogs: Torus (Torus Diameter, Inner Diameter: the ring may not close up), Coil
(section size, angle, pitch where the turns would touch), Pipe (Section Thickness, and
the Section Size under the wall); Box / Cylinder / Sphere have no such limit. Checked with
the dialogs' own pure checks (`primitives_core`). Scenario `limits_primitives`;
`primitives_shapes`, `primitives_qa_more` M1, `primitives_qa_pipe` Q2 updated.

## What every one of these commands does

| Fusion | SciForge |
|---|---|
| Nothing selected: the origin planes show as squares; click one, or click a flat face of the part | Same (the plane picker of Create Sketch). Curved faces are refused with a note in the dialog. A plane or flat face selected before the command is taken at once |
| The plane box in the dialog: click it to pick another plane | Same ("Plane" field); the shape moves to the new plane, sizes kept |
| Place with the mouse: the cursor moves on the plane (a blue outline follows it) | Same: the mouse ray meets the plane. Within 10 px the mouse snaps onto the plane's origin and onto the corners, line ends, sketch points and circle centres that lie on the plane; elsewhere it rounds to steps that suit the zoom (1, 2.5 or 5 x 10^n, about 6 pixels) |
| Blue arrows to drag sizes after placing | Same, drawn on top of the part; they show the value while dragging |
| Typed values in the dialog (and parameters / formulas: `w`, `d / 4`) | Same; a formula keeps driving the shape (an expression), listed under the fields, and follows the parameter in Change Parameters, after undo/redo and after reopening the file |
| Operation Join / Cut / Intersect / New Body / New Component; dragging into the part switches to Cut | Same. Until you pick one yourself: mostly inside the part -> Cut, touching or overlapping -> Join, away from it or no part yet -> New Body. A Join picked by hand that touches nothing also makes a new body (never a second piece inside the part's body). New Component: a new component (Component N, under the active component) with a body holding the shape; OK activates it; Cancel, Esc or a failed preview remove it again; switching to New Body moves the shape out of it (the component goes) |
| Live preview; problems said in the dialog (OK waits) | Same; nothing goes to the Report view |
| OK = one undo step; Cancel / Esc leave nothing behind; Enter = OK; Ctrl+Z while the dialog is open = Cancel | Same |
| Double-click the step in the timeline to edit it; the step can change operation | Same: the step keeps its place and name (e.g. a Box turned to Cut swaps `AdditiveBox` for `SubtractiveBox` in place; later steps move over) |
| A second use right after the first | Same (tested) |

## Box

| Fusion | SciForge |
|---|---|
| Click the first corner, then the opposite corner; then a height arrow | Same: the rectangle follows the mouse (rubber band), then the box appears with Length, Width and Height arrows |
| Length / Width / Height fields; a negative height goes the other way | Same; height below zero goes into the part (Cut is picked by itself when it is inside) |

Built as FreeCAD's `PartDesign::AdditiveBox` / `SubtractiveBox`, attached to the plane
(`FlatFace` + `AttachmentOffset`).

## Cylinder, Sphere, Torus

| Fusion | SciForge |
|---|---|
| Cylinder: centre click, a point on the circle, then the height arrow; Diameter / Height | Same; the diameter has its own arrow too |
| Sphere: centre click; Diameter | Same; the sphere sits with its centre on the plane |
| Torus: centre click, a point on the circle; Inner Diameter, Torus Diameter, Position Inside / On Center / Outside | Same; Position says where the tube sits against the inner diameter. Arrows for both diameters |

Built as FreeCAD's `PartDesign::AdditiveCylinder` / `Sphere` / `Torus` (and the Subtractive
ones). Intersect for any of them is SciForge's `PrimitiveFeature` (a
`PartDesign::FeaturePython`), because FreeCAD's primitives only add or take away.

## Coil

| Fusion | SciForge |
|---|---|
| Centre click, a point on the circle (diameter), then the height arrow | Same |
| Type: Revolution and Height / Revolution and Pitch / Height and Pitch / Spiral | Same; switching type keeps the coil's shape (the value the new type works out is filled in) |
| Diameter, Revolutions, Height, Pitch, Angle (taper) | Same; all take parameters (Revolutions too, e.g. a unitless `n`). The fields the type does not use are hidden, and a formula in a field that gets hidden is dropped. A positive Angle widens the coil as it rises, a negative one narrows it (FreeCAD's helix only widens away from its section, so a narrowing coil is swept from its narrow end back to the plane) |
| Rotation Clockwise / Counterclockwise | Same |
| Section Circular / Square / Triangular (External) / Triangular (Internal); Section Position Inside / On Center / Outside; Section Size | Same |
| Operation (Cut when it is inside the part) | Same; Join / Cut / Intersect / New Body / New Component as for Box |
| Impossible coils (turns touching each other, section reaching the axis, an angle that closes the coil) explained | Same, in the dialog, saying what to change (e.g. the pitch must be larger than the section, 2 mm) |

Built on FreeCAD's `PartDesign::AdditiveHelix` / `SubtractiveHelix` with a small section
object made for it (a SciForge 2D object holding the section, hidden from the timeline). Spiral
uses FreeCAD's "height-turns-growth" mode with height 0.

## Pipe

| Fusion | SciForge |
|---|---|
| Path: sketch curves or model edges; Chain Selection picks the curves that continue it | Same; click again to drop a curve |
| Distance (0..1 of the path), with a blue handle at the pipe's end | Same |
| Section Circular / Square / Triangular, Section Size | Same, with a size arrow |
| Hollow + Section Thickness | Same; a wall too thick is explained |
| Operation (Join / Cut / Intersect / New Body / New Component), auto from where the pipe goes | Same (a Join that touches nothing is a new body; New Component as for Box) |
| The path sketch is hidden after OK | Same; shown again while the pipe is edited |

Built on FreeCAD's `PartDesign::AdditivePipe` / `SubtractivePipe` with two SciForge helper
objects (the path, cut to the distance, and the section), both used only by the pipe (a
timeline Delete takes them along). Sharp corners of the path are mitred ("Right corner"),
like Fusion's. Intersect, and a hollow pipe round a closed path (FreeCAD's pipe made that
ring solid), are SciForge's `PipeFeature`; a pipe that is one stays one.

## Join away from the part, New Component (2026-10-13, branch `sf/gaps`)

Sources: **Autodesk** Box / solid primitives reference (SLD-BOX-SOLID, SLD-CREATE-SOLID-PRIMITIVE,
search excerpts): Operation Join, Cut, Intersect, New Body, New Component ("creates the body in a
new component"); **Autodesk** API `FeatureOperations` (Join, Cut, Intersect, NewBody,
NewComponent: "results in the creation of a new component that contains the new body").
**Forum** "Join produces New Body" and "Recurring problem with Join vs New Body" (Autodesk
Community, 2021): a Join whose tool body touches no body comes out as a new body; "In order to
join two bodies via Extrude, the bodies need to touch each other" ("Cannot Join Bodies with
Extrude"). **Forum** "Break apart body to make separate bodies": a body *can* hold separate
lumps (left by a cut, or a profile that only partly touches); SciForge keeps those as they are.

- A Join that does not even touch the part's body is made as a New Body (Box, Cylinder, Sphere,
  Torus, Coil, Pipe; the same rule is in Extrude, Revolve, Sweep and Loft). It used to say "This
  would leave 2 separate pieces in one body" and wait. The step is saved as New Body, so its
  timeline edit reads New Body (what was made). (Guess: what Fusion's edit dialog shows then.)
- New Component in every primitive dialog, made the way Extrude / Revolve do it
  (`components.body_for_new`). Golden models `sf_join_away_new_body`, `sf_cylinder_new_component`;
  scenario `gaps_join_new_body.py` (J3, J4).

## Coils and pipes of an older SciForge rebuilt on opening (2026-10-14, gaps work)

FreeCAD keeps the shapes stored in a file and recomputes nothing when it opens one, so a coil
or pipe saved before the QA fixes of 2026-10-11 kept its old, wrong shape until it was
edited: a coil with a negative angle was its mirror image (849.83 instead of 571.39 for the
`sf_coil_taper_narrow` spring), a tapered coil on a raised face drifted, a hollow pipe round
a closed path was a solid ring. Their hidden sections notice it while the file is read (the
coil section has no `Taper` yet, the pipe section still links the path object) and, once the
file is open, `sciforge/upgrade.py` rebuilds the step from its own saved options (as an edit
+ OK would) and writes one line to the Report view ("Coil was saved by an older SciForge
... rebuilt with today's coil"). The design shows as changed; a save keeps the new shape and
the next opening rebuilds nothing. Fusion has nothing like it (its files are its own), so
there is no source: the behaviour is SciForge's. Golden `sf_coil_old_narrow_upgraded`
(fails without the rebuild), `sf_pipe_old_upgraded`; scenario `gaps_old_coil.py`. Left: no
test recreates an old hollow ring (FreeCAD's own pipe with a hollow section); it goes
through the same rebuild as the other pipes.

## FreeCAD bug found and worked around

Undo a step that put a formula on a value, then redo it: the formula comes back but its link
to the parameter does not (FreeCAD 1.1.4; Pad, the primitives and Python 2D objects alike).
Changing the parameter then changes nothing until the file is reopened. `undo_links.py`
watches undo/redo and sets the same formula again where the link is missing (outside the undo
history). This fixes it for every feature, not only these. Should be reported upstream.

## Tests

Scenarios with real mouse and keyboard input (`SciForgeTests/gui/scenarios/`):
`primitives_box.py`, `primitives_shapes.py`, `primitives_coil.py`, `primitives_pipe.py`,
`primitives_qa.py` (nothing selected, valid selection, Cancel, Esc, Enter, Ctrl+Z, edit again,
undo/redo, second use, parameters, re-pick plane, save + reopen + edit, timeline Delete), and
the QA passes `primitives_qa_paths.py` (typed sizes while placing, values changed while the
preview runs, handles dragged far and negative, edits twice), `primitives_qa_keys.py` (digits
over the 3D view, Enter, another command's key), `primitives_qa_part.py` (a part of several
features with Create Sketch / Extrude / Press Pull, problems said in the dialog, picks in the
wrong order), `primitives_qa_coil.py` (a thread groove on a rod), `primitives_qa_pipe.py`
(pipes along block edges, round a corner, hollow), `primitives_qa_more.py` (a conical spring,
a torus groove, another command's key with Pipe open) and `primitives_qa_ring.py` (a hollow
ring round a parameter-driven sketch circle, Esc mid-pick, save / reopen, timeline Delete).
Golden models `sf_box_*`, `sf_cylinder_*`, `sf_sphere_*`, `sf_torus_*`, `sf_coil_*`
(tapered and narrowing coils: `sf_coil_taper_*`), `sf_pipe_*` (mitred corners:
`sf_pipe_corner_*`, hollow rings: `sf_pipe_ring_*`) (36, volumes worked out by hand: Pappus
for coils and pipes), built with
`sciforge/ai/ops/primitive_ops.py`. Unit tests `test_primitives_core.py`.

## Known gaps

| Fusion | Why not yet |
|---|---|
| Values typed in boxes on the canvas next to the mouse | The live values are in the dialog fields (type there) |
| Snapping onto any point of an edge, midpoints, and points that are not on the plane | Snaps to the origin and to corners, line ends, sketch points and circle centres lying on the plane |
| Exact Fusion defaults (to confirm with Luca): Torus Position starts On Center; Clockwise = right-hand coil; for square and triangle sections Section Size is the circle round the section; how pipe squares/triangles are turned; the coil starts centred on the plane | Taken from the docs, not compared with a capture |
| Sharp path corners in Pipe | Mitred (cut on the corner's bisecting plane); to compare with a capture of Fusion's |
| Coil section | FreeCAD sweeps an upright section along the helix (Fusion's section may lean with the pitch) |

## Value boxes and typing over the view (2026-10-13)

Every drag handle of this dialog has a value box beside it (`taskui.ValueBoxes`): it shows the
field's text with units, follows the handle, takes a value or formula (Enter = OK, a click away
keeps it), never covers a handle or another box, and goes with the dialog. A digit, minus or
decimal point typed with the mouse over the 3D view goes into the box of the handle last dragged
or hovered (else the main one), with its text selected (`taskui.TypeOverView`; FreeCAD's view
keys 0-6 no longer turn the view while the dialog is open). Which handle a digit goes to is
SciForge's guess at Fusion's rule.
