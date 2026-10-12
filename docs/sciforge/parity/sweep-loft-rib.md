# Parity spec: Sweep, Loft, Rib and Web (outline 7.6)

Source: Fusion's documented behaviour (its Sweep, Loft, Rib and Web references) and everyday
use. Not yet checked against Luca's own screen captures (outline 2.4). Implemented in
`src/Mod/SciForge/sciforge/`: `sweep.py` + `sweep_ui.py`, `loft.py` + `loft_ui.py`, `rib.py` +
`rib_ui.py`, with shared pieces in `curves.py` (connected paths, tangent chains) and
`curve_pick.py` (area picker, curve highlight, the blue distance ball). Status: **first pass,
not yet signed off**.

All four are in the ribbon under SOLID > CREATE. Each one opens its dialog with nothing
selected and waits for clicks, or takes what was selected before the command. Every value
updates a live preview. Problems are explained in the dialog, which stays open and keeps the
last good preview: nothing goes to the Report view and no pop-up appears. Cancel, Esc and
Ctrl+Z leave the part as it was, and OK is one undo step. Double-click the step in the
timeline to edit it again.

## Sweep (CREATE > Sweep)

| Fusion | SciForge |
|---|---|
| Type Single Path / Path + Guide Rail / Path + Guide Surface | Single Path and Path + Guide Rail. Path + Guide Surface is listed but greyed, with the reason as its tooltip |
| Profile: a sketch area or a flat face of the part | Same. Click inside a sketch area (the preview face lights up) or on a flat face. With nothing selected, a sketch that has a single area is taken by itself |
| Path: sketch curves or edges of the part; Chain Selection takes the curves joined smoothly | Same. A joint where three or more curves meet stops the chain |
| The profile may sit anywhere on the path; the sweep starts there | Same. With the profile at an end, Distance (0 to 1) is how far along the path it goes. With the profile inside the path you get Distance One and Distance Two, one for each way |
| Blue ball on the path to drag the distance | Same, one ball for each side |
| Orientation Perpendicular / Parallel | Same |
| Taper Angle | Same. A side of the profile at distance R from the path tilts by the angle, so the end section is scaled by 1 + L·tan(angle)/R |
| Twist Angle | Same. A straight path uses an exact helix guide. A curved path uses a guide built from rotation-minimizing frames. Twist is greyed under Parallel |
| Guide Rail with Profile Scaling Scale / Stretch / None | Same: the profile grows evenly with the rail, only towards the rail, or not at all (the rail only turns it) |
| Operation Join / Cut / Intersect / New Body | Same. A new sweep that runs mostly into material starts as Cut, and the first solid is a New Body. A Cut or Intersect that misses the part is explained |
| Edit from the timeline | Same |

What is built: FreeCAD's own `PartDesign::AdditivePipe` / `SubtractivePipe` when it gives
exactly Fusion's result. That means a sketch profile and a sketch path, a single path, the
whole path, no taper, no twist, Join, Cut or New Body, and everything in one body. Otherwise
SciForge builds its own `SweepFeature` (a `PartDesign::FeaturePython`, timeline type
`SciForge::Sweep`). A face or edges of the part always use SciForge's sweep: FreeCAD loses
such names after some edits (a reopened design whose Extrude is edited), and SciForge's sweep
finds a lost face or edge again where it was (`curves.remember` / `curves.refind`). An edit
switches between the two as needed; the step keeps its place and name, and the steps built
on it (a sketch on its end face, a Press Pull, a fillet) are moved onto the new step.

A sweep or loft that does not touch the part becomes a New Body by itself (Fusion makes a new
body for it). A path lying in the profile's own plane is refused with the reason.

## Loft (CREATE > Loft)

| Fusion | SciForge |
|---|---|
| Profiles: click sketch areas, flat faces or points, in loft order | Same. A point may be the first or the last profile (a cone or a dome) |
| The profile list: reorder, remove | Same: a list with up, down and remove buttons |
| Guide Type Rails / Centerline | Same. Rails: each section is moved (one rail), or moved and scaled (two rails), so it touches the rails. Centerline: the profiles stay square to the line |
| Chain Selection for rails and centerline | Same |
| Closed (the last profile lofts back to the first) | Same. With only two profiles the dialog says why it cannot close |
| Tangent Edges Merge | Shown but greyed; see the gaps below |
| Operation Join / Cut / Intersect / New Body | Same, with the automatic choice and the miss check used by Sweep |
| Edit from the timeline | Same |

What is built: FreeCAD's `PartDesign::AdditiveLoft` / `SubtractiveLoft` when every profile is a
whole sketch (or a sketch point), there are no rails and no centerline, the operation is Join,
Cut or New Body, and everything is in one body. Otherwise SciForge builds its `LoftFeature`
(timeline type `SciForge::Loft`), which also finds a lost face of the part again.

## Rib (CREATE > Rib)

| Fusion | SciForge |
|---|---|
| Curve: an open sketch curve (lines and arcs) | Same, with Chain Selection. A curve selected before the command is taken |
| Thickness Options Symmetric / One Side (Flip Side) | Same |
| Thickness | Same, with a blue arrow |
| Depth Options To Next / Depth | Same. To Next fills the sketch plane from the curve up to the part (a gusset). Depth makes a strip that wide, with a blue arrow |
| Ends carried on to the part | Same: a rib drawn short of the walls still meets them |
| Flip (grow the other way) | Same. Growing away from the part is explained ("does not reach a face ... Flip it, or use Depth") |
| Edit from the timeline | Same |

## Web (CREATE > Web)

| Fusion | SciForge |
|---|---|
| Curves: a network of open sketch curves | Same, with Chain Selection |
| Thickness Options Symmetric / One Side, Thickness | Same. One Side is on the curve's left as drawn; Flip Side puts it on the right |
| Depth Options To Next / Depth, Flip | Same. To Next grows out of the sketch plane down to the next faces |
| Extend Curves | Same: free ends are carried on until they meet the part |
| Edit from the timeline | Same |

Both are SciForge's `RibFeature` (a `PartDesign::FeaturePython`, timeline types `SciForge::Rib`
and `SciForge::Web`), because FreeCAD has neither. A rib or web always joins the part.

SciForge refuses three cases, each with its reason in the dialog:
- a rib or web that would not touch the part;
- To Next with nothing to stop at;
- a rib or web that would only touch the part along an edge, so it would be a separate piece.
  An example is One Side turned out of the part's side face.

## Tests

QA pass (break and fix, only real input, sketches drawn with the mouse and typed sizes):
`sweep_loft_qa_sweep` (5 paths), `sweep_loft_qa_loft` (5), `sweep_loft_qa_rib` (4),
`sweep_loft_qa_web` (3) and `sweep_loft_qa_part` (4): OK / Enter with nothing picked, picks
in the wrong order, Esc in the middle of picking (the Redo list survives), another command's
key with the dialog open, values typed while the preview runs (0, negative, too big, a decimal
comma), the distance ball and the thickness arrow dragged far out and back past their start,
edits from the timeline twice with Ctrl+Z / Ctrl+Y, Ctrl+Z in an edit, save / close / reopen /
edit, and Create Sketch, Extrude, Shell and Press Pull before and after the step. Golden model
`sf_web_depth_thin_wall` (a web carried on to walls thinner than the web).

Seven scenarios from the first pass, real input only: `sweep_loft_sweep`, `sweep_loft_sweep_cut`,
`sweep_loft_sweep_rail`, `sweep_loft_loft`, `sweep_loft_loft_guides`, `sweep_loft_rib` and
`sweep_loft_web`. Between them they cover nothing selected at the start, a selection made before
the command, Cancel and Esc, editing from the timeline, undo and redo, and a second use. Each
volume is checked against a hand-derived formula.

There are also 36 golden models: `sf_sweep_*` (14), `sf_loft_*` (9), `sf_rib_*` (6) and
`sf_web_*` (7). Their ops are `sf_curves`, `sf_sweep(_edit)`, `sf_loft(_edit)` and
`sf_rib(_edit)` in `golden/sweep_loft_ops.py`. Every expected value is analytic and its
formula is in the model's note.

## Known gaps
- **Tangent Edges Merge (Loft).** The loft keeps one side face per profile curve (Fusion's
  "Keep"). A merged side is one smooth B-spline face, and OpenCASCADE's volume of such a face
  came out up to 10 % wrong here: a slot lofted to the same slot gave 7551 instead of
  8356 mm³, while the meshed shape gave 8356. Inspect and the mass would then be wrong.
- **Path + Guide Surface (Sweep).** Listed but greyed: not built yet.
- **Loft end conditions** (Free / Direction / Tangent / Curvature / Point Tangent, with
  weights and takeoff angles) are not offered. Every profile is Free.
- **Loft rails.** Rails need profiles in parallel planes, and no holes or points among the
  profiles. A rail loft is close to Fusion's but not exact: the sections are fitted to the
  rails at 8 places between each pair of profiles. The golden tolerance is 2e-3.
- **Twist** works with Orientation Perpendicular only (it is greyed under Parallel).
- **Distance boxes** (Sweep) take plain numbers, not parameters or formulas.
- **Centerline loft** may show a seam line on its sides.
- **Web One Side** works for lines and arcs. Other curves (splines) are Symmetric only.
- **Operation New Component** is out of scope (SciForge has no components yet).
- **Profile Scaling default.** The default is "Scale"; Luca should confirm that this matches
  his Fusion.
