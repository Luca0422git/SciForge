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

## Wave 4: Objects To Cut for Sweep and Loft, Sweep values as formulas (branch `sf/modeling-2`, 2026-10-14)

Sources: no Autodesk page found that names Objects To Cut for Sweep or Loft (the help's
"Solids from sketches" covers them only briefly); the brief asks for it and Extrude and
Revolve have it (Autodesk "Revolve a solid body": "Objects to Cut: Check or uncheck objects
to cut"), so the rows below are **Guess** following SciForge's Extrude
(`parity/extrude-presspull.md`, R8). Every Fusion value field takes a parameter or a formula
(**Autodesk** parameters help).

| Fusion (source) | SciForge |
|---|---|
| Sweep and Loft: a Join, Cut or Intersect acts on every body the solid passes through (Join: also touches); the dialog lists them and one can be left out (Guess) | Same row and clicks as Extrude and Revolve: "Bodies to Cut / Join / Intersect", "N bodies", click the row then a body; one timeline step with hidden follower steps; a Join merges the bodies; while the dialog is open a merged body stays visible so it can still be clicked away; a Cut shows its solid in red |
| Sweep's Distance, Distance Two, Taper Angle and Twist Angle take a parameter or a formula (Autodesk) | Same: "share", "share / 2", "lean": the formula goes on the sweep as an expression and is listed under the fields; the sweep follows the parameter later; a plain number typed over it, or the blue ball dragged, drops the formula. A sweep with a formula is always SciForge's own sweep (FreeCAD's Pipe has no Distance property to carry it) |

Tests: scenarios `modeling2_bodies` (a sweep joining two plates across a gap, a loft cutting
them, Esc) and `modeling2_sweep_formula` (Distance and Taper as formulas, a parameter changed
later, edit, undo / redo, save / reopen); goldens `sf_sweep_join_two_bodies`,
`sf_loft_cut_two_bodies`, `sf_sweep_distance_parameter`, `sf_sweep_taper_parameter`.

## Wave 5: Loft part 2 (branch `sf/surface-2`, 2026-10-16)

Sources: **Autodesk** Loft reference and "Loft a solid body" (SLD-LOFT-SOLID, search excerpts):
"select an end condition or continuity for the first and last profiles"; Guide Type Rails /
Centerline; Tangent Edges Merge "merges edges of tangent faces into a single face", Keep
"maintains edges between adjacent tangent faces"; Closed "connects the first and last
profiles". **Autodesk** API `LoftFeatureInput.isTangentEdgesMerged`: true merges the faces so
the edge between them no longer exists (its default was not readable). **Autodesk** Form loft
reference: rails must intersect each section and end on or beyond the first and last.
**Forum** ([Centerline cannot be tangent to profiles](https://forums.autodesk.com/t5/fusion-design-validate-document/error-trying-to-loft-centerline-cannot-be-tangent-to-profiles/td-p/11064817),
[Rails cannot be tangent to profiles](https://forums.autodesk.com/t5/fusion-design-validate-document/lofting-error-rails-cannot-be-tangent-to-profiles/td-p/12317597),
[Introduction to Loft using rail curves](https://forums.autodesk.com/t5/fusion-design-validate-document/introduction-to-loft-using-rail-curves-in-fusion/td-p/7296238)):
one centerline only; it guides the shape in general while rails force it; rails and the
centerline must be smooth chains. **Autodesk** parameters help: every value field takes a
parameter or a formula. **Guess** where marked.

| Fusion (source) | SciForge |
|---|---|
| Tangent Edges Merge: profile curves joined smoothly (a slot's lines and arcs) loft into one side face (Autodesk) | Same check box (it was greyed). The tangent runs of each profile are joined into one polynomial B-spline curve first, so OpenCASCADE lofts one face per run. Off (Keep) by default: see the gaps. A merged loft is always SciForge's own loft (`MergeTangentEdges` property) |
| End conditions with rails or a centerline (Autodesk: offered for the first and last profile whatever the guide) | Same: Direction, Tangent, Curvature and Point Tangent now also with rails and with a centerline. The rail or centerline leads the loft between the profiles, the condition sets how it leaves each end (the columns of the side faces are interpolated again through the profiles and the fitted sections, with the end derivative) |
| End conditions on a closed loft (Guess: the loop has no last end) | The Last Profile row goes away; Direction on the first profile sets how the loop passes through it (both sides the same, so the loop is smooth there). Tangent or Curvature on a closed loft's first profile (an edge of a body) is refused with the reason: the loop runs through it, it cannot end on faces there |
| Rails that are edges of bodies (Autodesk: "rails are 2D or 3D curves", edges included) | Same: a click on an edge of another body in the Rails box takes it as a rail (it used to be read as a body for Objects To Cut); Chain Selection takes the edges joined smoothly to it |
| A click on a face right beside an edge, in the Rails or Centerline box | **Guess** (a rail is always a curve): the edge of that face within 6 px of the click is taken. An edge lying on another body's face (a prism's edge touching a slot's round end) is drawn at the same depth as that face, and the face took clicks on the edge itself |
| Rails between profiles in planes that are not parallel (a turn) (Autodesk) | Same (it was refused): the sections are fitted to the rails as they turn, stretched toward the rails at 8 places between each pair of profiles. Within 1 % of the true shape (see the gaps) |
| A centerline that runs on past the profiles (Guess: the loft ends at the profiles) | The loft runs between the first and the last profile; the rest of the line is not used |
| Takeoff Weight, Takeoff Angle and Tangency Weight take a parameter or formula (Autodesk) | Same: a parameter or a formula with parameters ("w", "w * 2") goes on the loft as an expression and is read back when the loft is edited; a plain number or sum ("0.5 * 2") is a value, as in every SciForge dialog |

Tests: scenario `surface2_solid_loft` (Merge, a rail on another body with Direction ends, a
parameter for the weight, a number over it, a centerline with ends, Closed refusal, undo /
redo, Esc: 77 checks);
goldens `sf_loft_merge_slot`, `sf_loft_merge_slot_volume` (expected failure: OpenCASCADE's
volume), `sf_loft_rails_ends`, `sf_loft_centerline_ends`, `sf_loft_closed_direction`,
`sf_loft_rail_body_edges`, `sf_loft_rails_turning`. The surface loft has the same options
(`parity/surface.md`, part 2).

## Sweep (CREATE > Sweep)

| Fusion | SciForge |
|---|---|
| Type Single Path / Path + Guide Rail / Path + Guide Surface | Same (Path + Guide Surface since 2026-10-13: see below) |
| Profile: a sketch area or a flat face of the part | Same. Click inside a sketch area (the preview face lights up) or on a flat face. With nothing selected, a sketch that has a single area is taken by itself |
| Path: sketch curves or edges of the part; Chain Selection takes the curves joined smoothly | Same. A joint where three or more curves meet stops the chain |
| The profile may sit anywhere on the path; the sweep starts there | Same. With the profile at an end, Distance (0 to 1) is how far along the path it goes. With the profile inside the path you get Distance One and Distance Two, one for each way |
| Blue ball on the path to drag the distance | Same, one ball for each side |
| Orientation Perpendicular / Parallel | Same |
| Taper Angle | Same. A side of the profile at distance R from the path tilts by the angle, so the end section is scaled by 1 + L·tan(angle)/R |
| Twist Angle | Same. A straight path uses an exact helix guide. A curved path uses a guide built from rotation-minimizing frames. Twist is greyed under Parallel |
| Guide Rail with Profile Scaling Scale / Stretch / None | Same: the profile grows evenly with the rail, only towards the rail, or not at all (the rail only turns it) |
| Operation Join / Cut / Intersect / New Body / New Component | Same. A new sweep that runs mostly into material starts as Cut, and the first solid is a New Body. A Cut or Intersect that misses the part is explained. New Component: `parity/components.md` |
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
body for it), and so does one with Join picked by hand (2026-10-13: Fusion never leaves a
second piece in the body; sources in `parity/revolve.md`, "A Join that touches nothing").
A path lying in the profile's own plane is refused with the reason.

## Loft (CREATE > Loft)

| Fusion | SciForge |
|---|---|
| Profiles: click sketch areas, flat faces or points, in loft order | Same. A point may be the first or the last profile (a cone or a dome) |
| The profile list: reorder, remove | Same: a list with up, down and remove buttons |
| Guide Type Rails / Centerline | Same. Rails (sketch curves or edges of any body): each section is moved (one rail), or moved and scaled (two rails), so it touches the rails. Centerline: the profiles stay square to the line |
| Chain Selection for rails and centerline | Same |
| Closed (the last profile lofts back to the first) | Same. With only two profiles the dialog says why it cannot close |
| Tangent Edges Merge | Same since wave 5, off by default; see the gaps below |
| End conditions of the first and the last profile: a sketch profile Connected / Direction (Takeoff Weight, Takeoff Angle), an edge or face of a body Connected (G0) / Tangent (G1) / Curvature (G2) (Tangency Weight), a point Sharp / Point Tangent (a dome; Tangency Weight) | Same choices (rows First Profile / Last Profile under the list; Fusion puts them in the list), also with rails, a centerline or Closed since wave 5 (a closed loft: the first profile only). See "End conditions" below |
| Operation Join / Cut / Intersect / New Body / New Component | Same, with the automatic choice and the miss check used by Sweep |
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

There are also 42 golden models: `sf_sweep_*` (15), `sf_loft_*` (14), `sf_rib_*` (6) and
`sf_web_*` (7). Their ops are `sf_curves`, `sf_sweep(_edit)`, `sf_loft(_edit)` and
`sf_rib(_edit)` in `golden/sweep_loft_ops.py`. Every expected value is analytic and its
formula is in the model's note.

## Known gaps
- **Tangent Edges Merge (Loft)** is built (wave 5) but off by default. A merged side is one
  smooth B-spline face closed round the profile, and OpenCASCADE's volume of such a face is
  several percent wrong: the merged slot gives 8824 instead of 8356 mm³ (+5.6 %, golden
  `sf_loft_merge_slot_volume`, an expected failure), while its mesh gives 8356. With Merge on,
  Inspect's volume and mass of the loft are off by that much; the shape is right.
- **Path + Guide Surface (Sweep)** keeps the profile's angle to the surface by the faces'
  normal at the nearest point of the path (Fusion's exact rule is not documented); a path far
  from the surface still uses the nearest faces. Two Sides is not offered for this type.
- **Loft end conditions.** How long the end derivative is for a weight (weight x the
  distance to the next profile), the sign of the takeoff angle (positive opens the loft out)
  and Point Tangent's scale are SciForge's guesses at Fusion's rule. Values are typed; Fusion
  also has a drag arrow. With rails, the condition holds at the profile and the rails take
  over within the first fitted section (an eighth of the way to the next profile).
- **Volumes of round lofts.** OpenCASCADE measures the volume of B-spline faces up to about
  1 % wrong (a cylinder lofted between two spline circles: +0.9 %; its mesh is right). A
  plain loft between circles stays exact (OpenCASCADE makes a cone); with end conditions the
  sides are splines, so Inspect's volume of such a loft can be off by that much.
- **Loft rails.** No holes or points among the profiles. A rail loft is close to Fusion's but
  not exact: the sections are fitted to the rails at 8 places between each pair of profiles
  (golden tolerance 2e-3 between parallel profiles; a quarter turn round two arc rails comes
  within 1 %: 3889 against 3927 mm³, `sf_loft_rails_turning`). Between parallel profiles two
  rails scale a section evenly; between turning profiles (and in the surface loft) they
  stretch it only toward the rails, Fusion's Profile Scaling being unknown for a loft. With
  more than two rails the solid loft follows the first two (the surface loft refuses them).
  A closed loft cannot follow rails or a centerline (refused with the reason).
- **Twist** works with Orientation Perpendicular only (it is greyed under Parallel).
- **Objects To Cut** (Sweep, Loft): as for Revolve, editing an older step does not roll the
  timeline back, so a body a later Join merged away cannot be clicked in the row.
- **Centerline loft** may show a seam line on its sides.
- **Web One Side** works for lines and arcs. Other curves (splines) are Symmetric only.
- **Profile Scaling default.** The default is "Scale"; Luca should confirm that this matches
  his Fusion.

## Path + Guide Surface (2026-10-13, gaps work)

Sources: **Autodesk** Sweep reference / Sweep a surface body (SLD-REF-SWEEP, SFC-SWEEP, search
excerpts): Type Single Path, Path + Guide Rail, Path + Guide Surface; "for a Path + Guide
Surface sweep, select a guide surface"; its only setting is Distance. **Autodesk** API
(SweepFeatureInput.orientation): the orientation setting is ignored when a guide rail or a
guide surface is given. **Guess**: the surface's normal turns the profile (it keeps the angle
it has to the surface at the start).

SciForge: Type Path + Guide Surface, a Guide Surface box that takes faces of the part (click a
picked face again to drop it), Distance and Operation; no taper, twist or orientation, like
Fusion. Built as SciForge's sweep with an auxiliary spine: a curve beside the path along the
faces' normal, so OpenCASCADE turns the profile with it. A thin strip swept along the slanted
ellipse of a cut cylinder stays on the cylinder (19.5 .. 20.6 from its axis; a Single Path sweep
turns it out to 17.3 .. 22.7). Golden `sf_sweep_guide_surface` (new op `expect_radius`),
scenario `gaps_sweep_guide_surface.py` (pick, edit, undo / redo).

## End conditions (2026-10-13, gaps work)

Sources: **Autodesk** Loft reference (search excerpts, GUID-EC6CECCD..., SLD-LOFT-SOLID): "select
an end condition or continuity for the first and last profiles"; Direction "applies an angle
measured off the sketch plane ... available when the Loft profile is a 2D sketch", Takeoff
Weight "the amount of influence the takeoff angle has along the Loft path", Takeoff Angle "the
start angle of the transition from the profile"; Tangent (G1) / Curvature (G2) "available when
the Loft profile is the edge or face of a body"; Point Tangent "applies tangency at the point to
create a dome shape", Tangency Weight for Tangent, Smooth and Point Tangent. **Forum**
("Can't make loft to have free continuity", "Loft ending angle"): a sketch profile only offers
Connected and Direction; with rails Direction has no visible effect. **Guess**: defaults
weight 1, angle 0; positive angles open the loft out; the free other end has no bend.

How SciForge makes it (`loft_ends.py`, math in `loft_ends_core.py`, unit tested): OpenCASCADE
lofts through the profiles; each side face's control points at the profiles are kept and every
column is interpolated again by a cubic with the end derivative the condition asks for
(Direction: the profile's normal tilted by the angle; Tangent: along the faces next to the
picked face, square to its edge, averaged at corners so the sides stay closed; Curvature: also
their bend across the edge; Point Tangent: flat over the point, toward the axis), weight x the
distance to the next profile long. Round profiles are made polynomial within 1e-7 mm first.
Golden models `sf_loft_ends_*` (5, analytic: Hermite cubics), scenario `gaps_loft_ends.py`
(Tangent + Direction, an edit to weight 2 with undo / redo, a Point Tangent dome).

## Value boxes and typing over the view (2026-10-13)

Every drag handle of this dialog has a value box beside it (`taskui.ValueBoxes`): it shows the
field's text with units, follows the handle, takes a value or formula (Enter = OK, a click away
keeps it), never covers a handle or another box, and goes with the dialog. A digit, minus or
decimal point typed with the mouse over the 3D view goes into the box of the handle last dragged
or hovered (else the main one), with its text selected (`taskui.TypeOverView`; FreeCAD's view
keys 0-6 no longer turn the view while the dialog is open). Which handle a digit goes to is
SciForge's guess at Fusion's rule.
