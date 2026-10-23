<!-- A copy of docs/sciforge/parity/sheet-metal-flat.md for AI models, made by tools/sciforge/make_ai_docs.py: edit the original, then run the script. -->

# Parity spec: SHEET METAL, flat (Flat Pattern, Unfold / Refold, Rip, Convert to Sheet Metal)

Wave 6, branch `sf/sm-flat` (2026-10-23). Implemented in `src/Mod/SciForge/sciforge/`:

| File | What it holds |
|---|---|
| `sheetmetal_unfold.py` | the unfolder (FreeCAD Part only, no document, no Qt): walls and bends found from a stationary face, laid flat by the rule's K-factor; some bends only (Unfold); refold of what was cut in the flat state; the flat's frame on XY |
| `sheetmetal_flat.py` | the Unfold and Refold steps (`PartDesign::FeaturePython`, timeline `SciForge::Unfold` / `SciForge::Refold`), grouped in the timeline |
| `rip.py` | the Rip step (`SciForge::Rip`): Face, Along Edge, Between Points |
| `sm_convert.py` | Convert to Sheet Metal (`SciForge::ConvertToSheetMetal`): thickness detection, rule choice, the step |
| `flatpattern.py` | the Flat Pattern object (`Part::FeaturePython` beside the body, one per component), its bend data and the DXF entities |
| `flatpattern_dxf.py` | the DXF writer and read-back (pure Python, unit tested) |
| `unfold_panel.py` | the shared picking dialog (faces, bends, edges, points routed to their boxes) |
| `unfold_ui.py`, `rip_ui.py`, `sm_convert_ui.py`, `flatpattern_ui.py` | commands, dialogs, the FLAT PATTERN environment, view providers, timeline names and icons |
| `ai/ops/flatpattern_ops.py` | golden / AI steps `sf_sm_convert`, `sf_flat_pattern`, `sf_unfold`, `sf_refold`, `sf_rip` |

Shared files changed (lines of this area only): `ribbon_config.py` (the five SHEET METAL
entries and the FLAT PATTERN tab), `ribbon_ui.py` (the contextual FLAT PATTERN tab:
`set_flat_pattern_mode`, `CONTEXTUAL`), `browser_core.py` / `browser_ui.py` (the Flat
Pattern node, its menu and double-click), `drawing_ui.py` / `drawing.py` (a flat pattern in
the Create Drawing list; its base view from the top; DRAWING > TABLES > Bend Table in
`flatpattern_drawing*.py` and one ribbon line). No FreeCAD core change.

Fusion's behaviour comes from `docs/sciforge/dev/research/fusion-sheet-metal.md` (sections 2.6
to 2.12, 4.2, 4.8 and the critic pass; **A** = Autodesk help / API, **F** = forum or
tutorial, **G** = guess). One extra search this session (WebSearch, 2026-10-23): an Autodesk
forum answer says a shelled box with sharp corners cannot be converted directly, "some
corrections made, such as adding fillets" (F, forums.autodesk.com "Convert to sheet meal",
m-p/12566467); SolidWorks' help (an analogue) says fillets become bends.

## How the flat is made (all tools)

| Fusion | SciForge | Src |
|---|---|---|
| A stationary face lies on the flat's XY plane; the rest is flattened against it | The stationary face (a flat top or bottom face of a wall) stays put; walls and bends are found by walking across tangent edges only (wall to bend, bend to bend), never across the thickness's sharp edges | A[R35], research 4.8 |
| Each bend is laid flat by its bend allowance BA = angle x (R + K T) | A point at angle phi from a bend's entry line goes to phi x (R + K T) along the sheet; the wall after it is turned back about the bend axis and moved by the full BA (critic pass CP1 item 1) | A[R6], D |
| Inner radius from the rule's Bend Radius | Read from the geometry (inner cylinder, or outer - T); a bend with no inner face (a flat hem) uses R = 0 | CP2 item 10 |
| K-factor from the rule | `sheetmetal.rule_for_body(body)["k_factor"]` | A[R6] |
| Holes and cuts come through | A wall's holes are its face's inner wires; a cut across a bend is developed point by point (B-spline, or a line when it stays straight) | G |
| Closed loops must be ripped | Refused: "the sheet closes on itself (a closed loop, like a tube or a box): add a Rip" | A[R47] |
| Non-uniform thickness fails | Refused: "the body is not one sheet of even thickness ..."; the check is T x the mean area of the two sides = volume (exact for walls, bends and side faces cut at an angle like a mitre) | F[F5] |
| Overlap in the flat | Refused: "the flat shape overlaps itself ...: add a Rip or change the stationary face" | research 4.8 |
| A body that is not sheet metal | Flat Pattern / Unfold / Rip refuse: use Convert to Sheet Metal first | A[R49] |
| Faces curved two ways (die-formed) | Refused: "curved in two directions (not a bend)" | plan, G |

## Create Flat Pattern (SHEET METAL > CREATE) and the FLAT PATTERN tab

| Fusion | SciForge | Src |
|---|---|---|
| Pick a stationary face on the top or bottom of the part (not an edge face) | Same; an edge face is refused ("pick a wide top or bottom face"); the dialog says the flat size ("Flat: 98.26 x 20.00 mm, 1 bend(s), thickness 1.00 mm") before OK | A[R35], A[R49] |
| One flat pattern per component; a second fails | Refused in the dialog ("this component already has a flat pattern ... delete it first"), OK waits | A[R35] |
| A Flat Pattern node under the component; double-click / Activate opens it | A "Flat Pattern" row under its component (or the design); double-click or right-click > Edit Flat Pattern opens it | G, A[R48] |
| The flat pattern is modal; the FLAT PATTERN contextual tab; Finish Flat Pattern (green check, Export DXF left of it) | The design's tabs hide, FLAT PATTERN (INSPECT, SELECT, EXPORT > Export DXF, FINISH FLAT PATTERN) is the only tab; the folded part is hidden and the flat shown from the top (its component too while it is open, when the user had hidden it: QA); Finish goes back to the tab and the camera you had | A[R48], F[F13], F[F14] |
| 2-bend corner relief on the flat (Round / Square) where two bends meet, at the Relief Placement; the flange's own Corner Relief override wins over the rule; a Corner Closure decides its own corner | Same on the flat pattern (and so in the DXF): Round = a hole of the Size's diameter (sm-forming's reading of Size), Square = a square of that side along the first bend; Intersection = centred where the two bend centre lines cross, Tangent = moved so the relief reaches the far side of both bend zones (sm-more's Corner Closure reading); a relief goes at the corners an edge Flange mitres (sm-forming's `corner_reliefs(step)`), the Flange's own (Override Corner Relief: shape, size, placement) else the rule's; a corner a Corner Closure step closed gets none (its Tear / Trim To Bend / Round / Square is already in the folded part), nor do corners made by sm-more's Bend lines or Hems or by Convert (the flat keeps what the folded part has); "Corner Reliefs" property to switch it off; Tear / Trim To Bend / weld shapes add nothing. The folded part keeps its corner as the Flange made it | A[R1], A[R24], research 4.6, G |
| Bend lines (centre) and bend extents (tangent lines); up / down; up bends red in drawings | Shown on the flat: centre lines red (up) / blue (down), extent lines grey; right-click > Show/Hide Bend Lines / Bend Extents | A[R36], A[R37], F[F9] |
| The flat pattern follows edits of the folded model | Same: it recomputes when the body changes; the stationary face is found again by where it was when face names change, and when it only moved along its normal (a new rule thickness moves the plate's top face: QA), else by its name while it is still flat (a Move step that turns the part: QA); the flat is laid out from the body's own frame, so a moved body keeps it; while an Unfold has no Refold yet the flat pattern shows the body as it was before that Unfold (all its bend lines; cuts made while unfolded come with the Refold) and Create Flat Pattern says to Refold first (QA) | G |
| Timeline "FlatPattern1" | Not a timeline step (the browser row only) | F[F10], G |
| Flat placed on XY | The stationary face at z = 0 facing +Z, the sheet below, its longest straight edge along +X, the outline's corner at the origin | G |

### A drawing of the flat pattern

| Fusion | SciForge | Src |
|---|---|---|
| Drawing > From Design, the flat pattern as the view source | File > New Drawing, Contents Select lists "Flat Pattern / <body>" (unticked); its Base View defaults to Top (the flat lies on XY); outline, holes and bend lines are drawn | F[F9], A[R37] |
| Tables > Bend Table, pick a flat pattern view: a table of the bends, identifiers added to the view | DRAWING > TABLES > Bend Table: the picked (or only) flat pattern view gets balloons B1, B2 ... on its bend centre lines (left to right) and a table BEND ID / DIRECTION / ANGLE / RADIUS / K-FACTOR at the top left of the sheet; one undo step; one per drawing; it follows the flat (a new K-factor, moved bends) | A[R17], G (columns, balloons) |
| Bend Note: click bend centre lines of a flat pattern view; each note shows the bend's information along its centre line (help page "Create and modify bend notes") | DRAWING > TEXT > Bend Note: each click on a bend centre line writes "UP 90° R 1.00" (direction, angle, inside radius) beside the line's middle, turned with the line (reading left to right or upwards); a click elsewhere or on a bend that has its note is refused with the reason; OK keeps them (one undo step), Esc drops them; the notes follow later edits (text and place). Editing a note's contents is not built | Autodesk help (DWG-CREATE-BEND-NOTE), G (format, place) |
| Bend Identifier (leaderless labels above each bend centre line) | The Bend Table's balloons stand for them (with a leader); no separate command | Autodesk help (DWG-CREATE-BEND-IDENTIFIER) |

### Export DXF (FLAT PATTERN > EXPORT, or right-click the Flat Pattern)

| Fusion | SciForge | Src |
|---|---|---|
| Export bend center lines (on), Export bend extent lines (on), Convert Splines to Polylines (off), Tolerance 0.01 cm | Same options and defaults, in the dialog with the file name; a name typed for a file that exists asks first ("exists: OK again replaces it", QA) | A[R36], F[F4] |
| Outer profiles, interior profiles, bend centre lines, bend extent lines, text on their own layers; bend lines in another line type | Layers OUTER_PROFILES, INTERIOR_PROFILES, BEND_CENTER_LINES_UP (red, CENTER), BEND_CENTER_LINES_DOWN (blue, CENTER), BEND_EXTENT_LINES (HIDDEN), TEXT (a note per bend: "UP 90.0%%d R1", which CAD shows as UP 90.0° R1) | F[F4], F[F9], G (names, notes) |
| 1:1 in document units | AutoCAD R12 in mm: LINE, CIRCLE, ARC; a spline as SPLINE (POLYLINE when converting); an ellipse (a slanted hole meeting a wall) as a SPLINE within 0.001 mm (QA: it became a polyline at the greyed-out 0.1 mm Tolerance) | G |

## Unfold / Refold (SHEET METAL > MODIFY)

| Fusion | SciForge | Src |
|---|---|---|
| Stationary Entity, Bends (inner or outer faces), Unfold All Bends (off) | Same, with the preview being the step itself; a cylinder face picked is a bend, a flat face the stationary entity; OK keeps what the dialog shows (a bend cleared or Unfold All Bends unticked after the preview is refused, QA); a body with no bend is refused ("There is no bend to unfold"); a click on another sheet metal body moves the dialog there and drops the preview from the first | A[R32], A[R48] |
| Features after it act on the flat body until a Refold | Same: sketch on XY, Extrude cut through the flat sheet across a bend | A[R12] |
| Refold bends the part back; features between act on the folded walls | Refold folds every bend its Unfold laid flat; material cut away in the flat state is cut from the folded part (walls rigidly, bends through the development: the cut's outline folded onto the bend, straight through the sheet); material added on a wall is added back | A[R12], A[R46] |
| Unfold and Refold a pair; everything between grouped in the timeline | Same: one timeline folder named after the Unfold | A[R46] |
| Refold available once an Unfold is open | Refold with nothing unfolded says so next to the mouse and opens nothing; Unfold on a body already unfolded says "Refold it first" | A[R50] |
| Timeline names Unfold<n>, Refold<n> | "Unfold 1", "Refold 1" (icons of their own); double-click edits | A[R12] |

## Rip (SHEET METAL > MODIFY)

| Fusion | SciForge | Src |
|---|---|---|
| Type Face / Along Edge / Between Points | Same (Along Edge first, G) | A[R33] |
| Face: removes the whole face | The face and the sheet under it are cut away (a bend face separates the walls) | A[R33], G(Inv) |
| Along Edge with a gap | A straight edge: where two walls meet at an angle, a gap centred on the plane halving the corner; where a wall meets a bend (a tangent line), a gap centred on that line straight through the sheet; a curved edge is refused | A[R33], G |
| Between Points with a gap and offsets; point 2 on point 1's face | A vertex, or an edge with an offset from its start; a slot of the gap's width through the sheet; point 2 off point 1's face is refused | A[R33] |
| Gap defaults to the rule's Miter/Rip/Seam Gap | Same | A[R6], G |
| (a rip that cuts the part in two) | Refused: "the rip would cut the body in 2 pieces: a rip only opens a closed shape" | G |
| (a pick or value refused after a good preview) | OK is refused with the reason (QA: it used to keep the last good rip) | G |
| Timeline Rip<n> | "Rip 1"; double-click edits; Gap in Change Parameters | G |

## Convert to Sheet Metal (SHEET METAL > MODIFY)

| Fusion | SciForge | Src |
|---|---|---|
| Pick a wide flat face; thickness measured there, read only | Same: "Thickness 1.000 mm" is a label | A[R8], A[R9] |
| Template Rule (new rule from the thickness) or a rule of the design / library, duplicated with the thickness set | Template Rule = "Converted <T> mm" (the default rule's K-factor, gap and relief; bend radius from the bends found); a chosen rule whose thickness matches is used as it is, otherwise copied as "<rule> <T> mm" | A[R8] |
| Show rules with matching thickness only | Same (on by default, G) | A[R8] |
| The Standard parent component becomes Sheet Metal (one way); in a Sheet Metal component its active rule is used | Same (sm-forming's `sheetmetal_component`); a component rule of another thickness is refused | A[R34], A[R9] |
| Cylindrical faces of constant thickness become bends, planar pairs flanges | Same (the unfolder's walk) | G |
| Sharp corners cannot be converted; add fillets | Refused naming the edge: "edge EdgeN is a sharp corner between two walls, not a bend: fillet it (inside with the bend radius, outside with radius + thickness), then convert it" (QA: it said "or Rip it", but Rip needs a sheet metal body); nothing is inserted silently (CP2 item 6) | F (forum 12566467), CP2 item 6 |
| Non-uniform thickness refused | Refused with the reason | F[F5] |
| A timeline step | "Convert to Sheet Metal 1" (the shape passes through; red if the body later stops being one even sheet); a double-click says the conversion is one way | G |

## Tests

- Golden models (`SciForgeTests/golden/models/sm_flat_*.json`, 16, hand-derived sizes with
  T = R = 1, K = 0.44, BA = 2.26195): L bracket 98.26195 x 20; U channel with a hole
  116.52389 x 20 - 9 pi; one bend of a U unfolded; slot cut across a bend in the flat state
  and refolded (removes (2/1.44)(2^2 - 1^2)/2 x 10); converted tube with a corner ripped
  away 130.78584; tube ripped between points 132.04779; sm-forming's edge flange 59.26195 x
  30, its partial flange with straight reliefs, its contour L, its mitred tray (bbox), the
  same edge flange with a K 0.33 rule (59.08916); sm-more's Bend (the flat is the 100 x 40
  plate it was bent from), its open hem (BA = pi (0.25 + 0.44)) and flat hem (R 0.005), its
  box folded from a plus-shaped blank by four Bend lines (the 100 x 100 blank again, 8400);
  three with a hand-derived box and a measured volume: sm-more's Corner Closure (Tear) laid
  flat, 119.26195 x 79.26195 (walls 21 - (R + T) = 19), no rule relief at the closed
  corner; the same with its Round Tangent relief (sliver edges and a slit left by that
  boolean); the tray with the Flange's Square 3 mm corner relief override.
- Every sm-forming / sm-more golden part was also laid flat in a probe: all flatten
  (rolled, teardrop, rope and double hems, Join by Bend, every Corner Closure, mitres,
  sm-more's tab bends) except the lofted flanges (sharp folds or curved two ways: refused),
  sm-forming's flanges at an inside corner of an L-shaped plate (the two flanges lie over
  each other when laid flat: refused as an overlap) and parts whose largest +Z face is an
  edge face.
- Scenarios (real clicks): `flatpattern_l_bracket`, `flatpattern_u_channel_dxf`,
  `flatpattern_unfold_refold`, `flatpattern_rip_convert`, `flatpattern_component_rip`,
  `flatpattern_refusals`, `flatpattern_environment`, `flatpattern_flange`,
  `flatpattern_drawing` (with Bend Table and Bend Note), `flatpattern_tray`,
  `flatpattern_corners` (a Corner Closure's corner gets no rule relief; the Flange's
  corner relief edited in its dialog to Square 3 mm, the flat pattern follows).
- Unit tests: `SciForgeTests/unit/test_flatpattern_core.py` (DXF writer and read-back, the
  bend maths of the flat sizes, corner crossings and relief placements, the FLAT PATTERN
  tab, the browser node, the golden format).
- QA pass (branch `sf/sm-flat-qa`): golden `sm_flat_thickness_change` (the edge flange's
  rule made 2 mm thick after its flat pattern exists: 58.52389 x 30 x 2) and
  `sm_flat_moved_body` (the U channel turned 90 degrees about X and shifted by Move steps,
  then K 0.33: the flat follows, 116.17832 long); scenarios
  `flatpattern_qa_paths` (Convert undo / redo; a Rip pick refused after a good preview, OK
  refused, Esc; Unfold All Bends unticked after the preview, OK refused; Convert, Rip,
  Unfold and Refold saved and reopened, their classes and view providers back, a forced
  recompute changing nothing, the Unfold ... Refold folder kept, the Rip edited from the
  timeline and cancelled; Export DXF cancelled writes nothing; an existing file asked about
  before it is replaced), `flatpattern_qa_partial`
  (one bend of a U unfolded; Create Flat Pattern before the Refold refused; the Unfold edited
  from the timeline to all bends with its Refold after it, undone; the Flat Pattern deleted from the browser, undo / redo),
  `flatpattern_qa_two_bodies` (Unfold moved from one sheet metal body to another; a flat
  plate has no bend to unfold), `flatpattern_qa_hidden_component` (a flat pattern opened
  from a hidden component).
- Checked by hand in real FreeCAD (QA probes): flat lengths and up / down of single bends
  of 30, 45, 90 and 135 degrees with T 1 to 2, R 0.5 to 2, K 0.3 to 0.5 (L1 + angle (R +
  K T) + L2, both sides as the stationary face); a hole on the far wall refolds to the
  same place; holes and a window across a bend's tangent lines refold with the bend's
  share grown by (R + T/2) / (R + K T) (the sheet's middle is longer than its neutral line).

## Known gaps

- **Refold has no inputs**: it folds back every bend of its Unfold (Fusion's Refold may
  take a stationary entity and some bends, research §2.7 rows are G). Partial refolds would
  leave an Unfold half open; not built.
- **Material added across a bend in the unfolded state** is refused at the Refold ("add it
  after the Refold"); material added on a wall comes back. Fusion's behaviour unknown.
- **FLAT PATTERN tab contents**: only INSPECT, SELECT, EXPORT (Export DXF) and FINISH; no
  sketches or construction geometry on the flat (Fusion allows them, A[R35]). The flat
  pattern is a shape beside the body, not a component of its own.
- **Flat pattern STEP export** (Fusion: A[R36] preview): not built. In drawings, a bend
  note's contents cannot be edited (Fusion's "modify bend notes"), there is no separate
  Bend Identifier command (the Bend Table's balloons do that), and the bend lines have no
  up / down styles.
- **Side faces cut at an angle through the thickness** (sm-forming's mitres are bevelled
  along the corner's bisector plane): the flat takes the stationary side's outline, so its
  volume differs a little from the folded part's; a real (square) mitre cut has no such
  difference.
- **Corner reliefs are on the flat only**: the 2-bend relief (the Flange's override, else
  the rule's; Round / Square, Intersection / Tangent) is cut into the flat pattern where two
  bends meet, but the folded part keeps the corner the Flange made (sm-forming's gap), so
  an Unfold / Refold does not show it (a Corner Closure with a Round / Square relief does
  cut it into the folded part). The weld shapes are not built. A corner counts as closed
  by a Corner Closure when both its picked flange ends lie within 2 (R + T) + 2 mm of where
  the two bend axes meet. Bend reliefs are whatever the folded part has (sm-forming's
  flanges cut them).
- **Flanges at an inside corner** (sm-forming's L-shaped plate with flanges on both edges
  of the inside corner) lie over each other when laid flat: the flat pattern is refused
  ("the flat shape overlaps itself"); Fusion's handling is not documented. No single flat
  sheet makes that part: both flanges need the same square of sheet next to the corner.
- **sm-more's Brake Form lofted flange** meets in sharp folds (no bend radius): the flat
  pattern refuses it naming a sharp edge; with bends of the rule's radius between its facets
  it would lay flat. Die Form (curved two ways) is refused saying the step is formed by a die
  (its `Developable` property).
- **Along Edge between two walls** cuts symmetrically about the corner's bisector plane;
  Fusion's exact gap placement is not documented (research §5 item 6).
- **The DXF is R12**: a SPLINE entity in an R12 file is read by FreeCAD, LibreCAD and most
  CAM tools but not by strict R12 readers; tick Convert Splines to Polylines for those
  (Fusion recommends it for laser shops too, F[F4]).
- **Up / down**: a bend is "up" when it folds toward the stationary face's side (Fusion's
  isBendUp, A[R35]); the DXF and the canvas colour them; drawings draw both alike.
- The ribbon sweep (`SWEEP_TABS=sheet_metal,flat_pattern`) passes (sm-forming added the
  INTENDED entry for its Sheet Metal Rules window).
- **Left open by the QA pass** (G, not fixed): the Unfold step keeps its stationary face and
  bends by face name only (the Flat Pattern also remembers where its face is), so an edit
  before it that renumbers faces can make it take another face; Tangent placement is
  also applied to Square corner reliefs (the research has it for Round only); a second
  converted body with the same thickness but another bend radius replaces the first one's
  "Converted <T> mm" template rule; a bend added to the part after its Bend Table was made
  gets a table row but no identifier balloon, and a bend removed keeps its old balloon (the
  refresh runs from a timer outside an undo step, so it only moves what exists).

## Journey pass (2026-10-23, `sf/journey-sm`)

A whole sheet metal part was built across sm-forming, sm-more and sm-flat with real input
(`journey_sheetmetal`, `journey_sheetmetal_convert`, `journey_sheetmetal_tray`). The one
failure it met, the Flat Pattern turning red after the rule's Thickness changed ("the
stationary face is gone after an edit"), is the one the QA pass fixed in parallel
(`flatpattern._moved`, golden `sm_flat_thickness_change`); the journey's own golden
`sm_flat_thickness_follow` (an L bracket, 1 mm then 2 mm, analytic) checks it too.
