# Parity spec: PLASTIC part 2 (Snap Fit, Lip, Design Advice)

Wave 6 (2026-10-23), branch `sf/plastic-2`. Luca: "There are two areas of fusion that we are
missing. Sheet metal and plastic. ... plan all the features that belong in those tabs, and
then build them all." Plan: `docs/sciforge/plan-sheet-metal-plastic-surface.md`; Fusion's
behaviour with every source: `docs/sciforge/dev/research/fusion-plastic.md` (sections 2.4,
2.5, 2.11, 4.2 - 4.4, 4.7, and its "Critic pass"). Plastic rules, Boss, Rest and Rule
Fillet are plastic-1's (`parity/plastic.md`); this area uses its contract (`plastic_core.py`,
`plastic.py`: `rule_for_body`).

Code (`src/Mod/SciForge/sciforge/`):

| Command | Qt-free maths (unit tested) | Document side (FreeCAD, no Qt) | Dialog |
|---|---|---|---|
| CREATE > Snap Fit | `plastic_snap_core.py` | `plastic_snap.py` | `plastic_snap_ui.py` |
| CREATE > Lip | `plastic_lip_core.py` | `plastic_lip.py` | `plastic_lip_ui.py` |
| INSPECT > Design Advice | `plastic_advice_core.py` | `plastic_advice.py` | `plastic_advice_ui.py` |

Status: **built, first pass** (every command, its options, live preview, arrows with value
boxes, one timeline step, edit, undo / redo, save / reopen, refusals with the reason).
No core patch.

## Behaviour spec (what Fusion does), with sources

Source tags as in the research file: **A** Autodesk (help page excerpt, API reference, blog,
release notes), **F** forum / tutorial / resin supplier guide, **G** a guess (nothing
confirms it; the sandbox could only read search excerpts). The API has **no** Snap Fit, Lip
or Design Advice objects, so their dimension lists are mostly G (research 0.1, critic CP.2
item 11).

### Snap Fit

| # | Fusion | Source |
|---|---|---|
| S1 | "Creates a cantilever snap fit feature to fasten two solid bodies together"; placed at sketch points, best on the parting plane between the two bodies | A (SLD-SNAP-FIT) |
| S2 | Types Parallel Hook and Groove, Perpendicular Hook and Groove, Hook and Loop | A (SLD-SNAP-FIT, F-MANMACHINE) |
| S3 | Selection Mode Automatic (all visible sketch points) / Manual (pick points) | A (July 2022 release notes) |
| S4 | Rotation Type Uniform / Independent (one manipulator each) / Aligned (to a plane, line or point) | A (July 2022 release notes) |
| S5 | Hook section sets the hook body; Extent To Next (base from the sketch plane to the nearest faces of a body) / Distance | A (SLD-SNAP-FIT) |
| S6 | A base fillet radius at the hook's base | A (SLD-SNAP-FIT) |
| S7 | Groove section (Parallel) / Hook Undercut section (Perpendicular) / Loop section (Hook and Loop) for the other side; a checkbox creates that side | A (SLD-SNAP-FIT) |
| S8 | Thickness and Draft Angle picked up from the plastic rule | F (F-MANMACHINE) |
| S9 | Beam length / width / thickness at root and catch, catch depth and length, insertion and retention angles | G (Inventor's Snap Fit fields, A-inv) |
| S10 | Groove = catch + clearance on every mating face | G |
| S11 | What Parallel / Perpendicular mean geometrically | G (open question 5) |
| S12 | Strain at the root: constant section e = 1.5 t y / L^2; tapered to half: e = t y / (1.09 L^2) | F (resin suppliers' guides; critic pass C5 corrected the tapered factor) |
| S13 | "Visibility controls" in the dialog | A (blog mention), meaning unknown |

### Lip

| # | Fusion | Source |
|---|---|---|
| L1 | Lip, Groove or Lip And Groove along the parting edge of an enclosure; introduced May 2023 | A (SLD-LIP, May 2023 What's New) |
| L2 | Select one or more tangent edges on a solid body; select the inside edge so the reveal is outside | A (SLD-LIP) |
| L3 | Lip And Groove: the bodies must touch so the edges line up | A (SLD-LIP) |
| L4 | Assign a plastic rule first; the dimensions come from it | A (SLD-LIP) |
| L5 | Groove dimensions follow from the lip dimensions and the clearance | A (SLD-LIP) |
| L6 | Guide Type: Face Guide (section relative to a face beside the edge) / Pull Direction (fixed direction; edges must be tangent-continuous) | A (SLD-LIP) |
| L7 | Advanced tab to fine-tune the dimensions | A (SLD-LIP) |
| L8 | Advanced fields: lip width, lip height, inner / outer draft, clearance, clearance height, groove width / depth for Groove alone, tip radius | G (Inventor's Lip, A-inv) |
| L9 | Defaults: lip width = Thickness / 2, lip height = Reveal Height, clearance = rule Clearance, drafts = rule Draft Angle | G (A-api says reveal height and clearance are "used for plastic features") |

### Design Advice

| # | Fusion | Source |
|---|---|---|
| D1 | Uses the plastic rule of the component that holds the body | A (SLD-DESIGN-ADVICE) |
| D2 | Thickness alerts outside the Thickness Range or beyond the Thickness Variation; draft alerts | A (SLD-DESIGN-ADVICE) |
| D3 | Also knife edges and undercuts | A (AU 2022 tips class, Design Advice blog) |
| D4 | It is a command ("used by the Design Advice command") | A (API PlasticRule docstrings, critic CP.2 item 12) |
| D5 | Thickness Variation in percent | A (blog) vs length (API docstring copy-paste): open question 3 |
| D6 | Pull direction, colour overlay, issues list with click-to-zoom, browser Analysis folder | G |

## What SciForge does

### Snap Fit (PLASTIC > CREATE > Snap Fit)

| Fusion | SciForge |
|---|---|
| Sketch points between the bodies | Click the sketch (its browser row or any of it): **Automatic** takes every point; **Manual**: click the points one by one (a second click takes one off). A sketch selected before the command is taken at once (with its picked points: Manual). |
| The hook body | The body behind the first point (the sketch normal's side); **Flip** puts the hook on the other side. The other body is found as the one the groove would cut (Parallel / Perpendicular) or the one under the loop (Hook and Loop) and named in the dialog. |
| Types (S2, S11 G) | **Parallel Hook and Groove**: the beam runs along a wall of the other body, the catch goes into a groove cut in it (a window when the wall is thinner than the groove). **Perpendicular Hook and Groove**: the beam passes through a slot in a wall across it, the catch hooks under that wall ("Hook Undercut"). **Hook and Loop**: a frame (Loop Thickness) is built on the other body in front of the catch, standing on it, with an opening the catch snaps through. |
| Rotation Uniform / Independent / Aligned | Rotation Angle turns every catch about the sketch normal from the sketch's X; **Independent**: an Angles field, one angle per point in order; **Aligned**: each catch faces away from the middle of the points (**Face In**: towards it), so snaps round a box all face out. |
| Extent To Next / Distance | To Next: the base block runs from the parting plane to the body (and half a thickness into it); Distance: that long. |
| Hook sizes | Beam Length, Beam Width, Thickness at Root, Thickness at Catch (taper), Catch Depth, Catch Length, Insertion Angle, Retention Angle (90 = permanent), Draft Angle (the beam's sides narrow towards the tip), Base Fillet Radius (round the root; away from the catch side when all round cannot be made, a note otherwise). |
| Groove / Hook Undercut / Loop | The checkbox makes that side; Clearance (all round); Loop Thickness (loop). |
| Rule values (S8) | Thickness at Root and at Catch, Draft Angle, Base Fillet Radius (Nominal Radius), Clearance and Loop Thickness start from the component's rule and **follow it** (changing the rule changes the snap fit) until a value is typed. The rule is named in the dialog. |
| Strain (S12) | The strain at the root while the catch is pushed in is shown against the rule material's allowable strain; above it, a yellow warning (SciForge addition; Fusion does stress in Simulation). |
| Manipulators | Blue arrows with value boxes: Beam Length (along the insertion axis) and Catch Depth. |
| Timeline | One step "Snap Fit N" in the hook body; the groove / loop is a hidden step of the other body (ModifyFollower: rolls back, suppresses, moves and deletes with the snap fit). Double-click edits; Change Parameters lists Beam Length, Width, Thickness, Catch Depth, Clearance. |
| Refusals | In the dialog, OK waits: catch shorter than its lead-in ramp, catch longer than the beam, a draft that closes the beam, angles out of range, no point, no body behind the point ("use Flip or a Distance extent"). Notes (not refusals): a snap fit that finds no wall / floor on the other body, a base fillet that cannot be made. |

### Lip (PLASTIC > CREATE > Lip)

| Fusion | SciForge |
|---|---|
| Pick tangent edges | Click the rim's edges; **Tangent Chain** (on) takes the edges joined smoothly to the one clicked (a filleted rim in one click). Edges of one body; they must lie on one flat face (the rim, the parting face) and join end to end (a closed loop or an open chain). |
| Lip / Groove / Lip And Groove | **Lip**: a lip stands on the rim from the picked edges towards the wall. **Groove**: a groove cut into the rim (its own Groove Width / Depth). **Lip And Groove**: the lip on this body and the groove (lip + Clearance each side, + Clearance Height deeper, the same drafts) in the body touching the rim, found and named in the dialog; **Swap Lip and Groove** puts the lip on the other body. |
| Guide Type | **Pull Direction**: the section is swept along the rim's normal. **Face Guide**: built the same way where the walls stand square to the rim (see Known gaps). |
| Advanced | Lip Width, Lip Height, Inner Draft, Outer Draft, Clearance, Clearance Height, Groove Width, Groove Depth, Tip Radius (round on the lip's top edges). |
| Rule values (L9) | Lip Width = Thickness / 2, Lip Height = Reveal Height, Clearance and Clearance Height = Clearance, drafts = Draft Angle; they follow the rule until typed. |
| Manipulators | Arrows with value boxes: Lip Height and Lip Width. |
| Timeline | One step "Lip N" in the picked edges' body; the other body's change is a hidden follower step. Double-click edits. |
| Refusals | A lip / groove wider than the wall ("must be less than the wall (2.00 mm) at the selected edges"), edges not on one flat face, edges that do not join, drafts that close the section, Lip And Groove with no touching body ("or use Lip alone"). |

How it is built: the picked chain is offset in the rim's plane (2D offsets with sharp joins)
to the band of the section, extruded along the pull direction; drafted sides are ruled lofts
between the bottom and top offsets. Lip and groove volumes are exact (golden models).

### Design Advice (PLASTIC > INSPECT > Design Advice)

| Fusion | SciForge |
|---|---|
| Bodies of components with a rule | The dialog starts on the shown solid bodies of components with a plastic rule (all shown bodies, with the default rule, when none has one); click a body to take it out or in. The rule of each body is named. |
| Pull direction | Z by default; click the Pull Direction box, then a plane, flat face, straight edge or axis; Flip. |
| Checks | **Thickness** (outside the rule's range), **Thickness Variation** (more than the rule's percentage from its Thickness), **Draft** (less than the rule's Minimum Draft Angle against the pull either way; faces square to the pull are fine), **Knife Edges** (convex edges sharper than 2 atan(1/2) = 53.13 degrees: thinner than the knife-edge threshold one threshold in), **Undercuts** (faces a two-part mould cannot reach along the pull). Each can be switched off. |
| Overlay | Display **Issues**: green fine, blue too thin, orange too thick, yellow draft / variation, purple undercut, knife edges drawn red; **Thickness**: a map from the rule's minimum (blue) to its maximum (red). |
| Issues list | Check, body and face (edge), and the worst value; a click selects the face and zooms to it. A summary line counts each check. |
| Browser | OK keeps it in the Analysis folder (eye shows / hides, double-click reopens the dialog, Delete removes it); never a timeline step; saved with the design. It checks again whenever one of its bodies changes. |

Wall thickness at a point: the distance along the inward normal to the next face; where that
ray runs along inside a wall (a rim's top, a hole through a wall), the wall across there
(nearest face straight through to the opposite one); thickness that breaks the rule is
measured again on the exact shape (the display triangles cut corners off round faces).

## Tests

- Scenarios (real mouse and keyboard, FreeCAD 1.1.4 under xvfb):
  `plastic2_snap` (52 checks: a snap fit on an enclosure wall and its groove, Beam Length
  typed, the catch depth arrow dragged, OK, undo / redo, edit from the timeline, Esc,
  save / reopen), `plastic2_snap_options` (49: Manual, Hook and Loop, Perpendicular,
  Automatic, Aligned, Independent, a refusal, Esc, components, an empty design),
  `plastic2_lip` (57: lip on a base and groove in its lid, drafts, height typed and dragged,
  Swap, Groove, Lip, the wall refusal, OK, undo / redo, edit, Esc, save / reopen),
  `plastic2_advice` (53: checks, click-to-zoom, options, a body left out, browser eye,
  reopen from the browser, the analysis follows the design, save / reopen, refusal, empty
  design).
- Golden models (hand-derived volumes): `plastic2_snap_parallel`, `plastic2_snap_edit_taper`,
  `plastic2_snap_loop`, `plastic2_snap_two_points`, `plastic2_lip_and_groove`,
  `plastic2_lip_drafted`, `plastic2_lip_swap`, `plastic2_groove_only`.
- Unit tests: `SciForgeTests/unit/test_plastic2_core.py` (31).

## Known gaps

- **Fusion's exact Snap Fit and Lip dialogs could not be read** (no page access, no API
  objects): labels, defaults and the Parallel / Perpendicular geometry are SciForge's
  reading (G rows above). Luca's screenshots can correct them.
- **Face Guide** builds the section along the rim's normal; on walls that lean (drafted
  walls) Fusion keeps the section at the wall's angle. SciForge refuses Face Guide on a
  slanted wall with the reason (use Pull Direction).
- **Lip edges must lie on one flat face** (the usual flat parting face). A parting line that
  steps or runs over a curved face is refused.
- **Snap Fit "visibility controls"** (S13): meaning unknown, not built.
- **Independent rotation** takes its angles in a field (one per point), not a manipulator
  per snap fit.
- **Aligned** aligns to the middle of the points (out or in), not to a picked plane, line or
  point.
- **Design Advice thickness** is sampled (up to 8 points a face), not a continuous map; a
  thin spot between samples can be missed. No alert badge on the component in the browser.
- **Injection-moulding simulation** is out of scope (outline 8).
