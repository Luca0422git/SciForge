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
boxes, one timeline step, edit, undo / redo, save / reopen, refusals with the reason);
**QA pass done** (its fixes under "QA pass" below). No core patch.

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
| The hook body | Found: the body behind the first point (the sketch normal's side); **Flip** puts the hook on the other side; or click the **Hook Body** box and a body. The other body is found as the one the groove would cut (Parallel / Perpendicular) or the one under the loop (Hook and Loop), or picked in the section's **Body** box; it is named in the dialog. |
| Types (S2, S11 G) | **Parallel Hook and Groove**: the beam runs along a wall of the other body, the catch goes into a groove cut in it (a window when the wall is thinner than the groove). **Perpendicular Hook and Groove**: the beam passes through a slot in a wall across it, the catch hooks under that wall ("Hook Undercut"). **Hook and Loop**: a frame (Loop Thickness) is built on the other body in front of the catch, standing on it, with an opening the catch snaps through. |
| Rotation Uniform / Independent / Aligned | Rotation Angle turns every catch about the sketch normal from the sketch's X, also with a **rotation handle** (with its value box) at the first snap fit; **Independent**: a rotation handle per snap fit (and an Angles field, one angle per point in the sketch's order); **Aligned**: each catch faces away from the middle of the points, or from what is picked in **Align To** (a point; a straight edge: straight away from its line; a face: its centre) (**Face In**: towards it), so snaps round a box all face out. |
| Extent To Next / Distance | To Next: the base block runs from the parting plane to the body (and half a thickness into it); Distance: that long (its arrow drags it). |
| Hook sizes | Beam Length, Beam Width, Thickness at Root, Thickness at Catch (taper), Catch Depth, Catch Length, Insertion Angle, Retention Angle (90 = permanent), Draft Angle (the beam's sides narrow towards the tip), Base Fillet Radius (round the root; away from the catch side when all round cannot be made, a note otherwise). |
| Groove / Hook Undercut / Loop | The checkbox makes that side; Clearance (all round); Loop Thickness (loop); its Body box. |
| "Visibility controls" (S13, meaning unknown) | **Hide Other Body**: the other body hidden while the dialog is open, to see the hooks (shown again on OK / Cancel). |
| Rule values (S8) | Thickness at Root and at Catch, Draft Angle, Base Fillet Radius (Nominal Radius), Clearance and Loop Thickness start from the component's rule and **follow it** (changing the rule changes the snap fit) until a value is typed. The rule is named in the dialog. |
| Strain (S12) | The strain at the root while the catch is pushed in is shown against the rule material's allowable strain; above it, a yellow warning (SciForge addition; Fusion does stress in Simulation). |
| Manipulators | Blue arrows with value boxes: Beam Length (along the insertion axis), Catch Depth and, with Extent Type Distance, the base's length (research: "an extent arrow handle", G); rotation handles (above). |
| Timeline | One step "Snap Fit N" in the hook body; the groove / loop is a hidden step of the other body (ModifyFollower: rolls back, suppresses, moves and deletes with the snap fit). Double-click edits; Change Parameters lists Beam Length, Width, Thickness, Catch Depth, Clearance. |
| Join / New Body | Not a choice in Fusion's Snap Fit (research 2.4: the hook is joined into the hook body, the groove or loop made in the other body, no new bodies, G); the same here. |
| Refusals | In the dialog, OK waits: catch shorter than its lead-in ramp, catch longer than the beam, a draft that closes the beam, angles out of range, no point, no body behind any point ("use Flip or a Distance extent"). Notes (not refusals): a point with no body behind it is left out (the others are made; research: "skip the point with a warning", G), a snap fit that finds no wall / floor on the other body, a base fillet that cannot be made. |

### Lip (PLASTIC > CREATE > Lip)

| Fusion | SciForge |
|---|---|
| Pick tangent edges | Click the rim's edges; **Tangent Chain** (on) takes the edges joined smoothly to the one clicked (a filleted rim in one click); a click on the rim's flat face takes its inside edge, the face's inner loop (SciForge's shortcut: the brief's "edges / faces"; Fusion's help only speaks of edges). Edges of one body; they must lie on the flat rim (the parting face, one plane) and join end to end (a closed loop or an open chain). |
| Lip / Groove / Lip And Groove | **Lip**: a lip stands on the rim from the picked edges towards the wall. **Groove**: a groove cut into the rim (its own Groove Width / Depth). **Lip And Groove**: the lip on this body and the groove (lip + Clearance each side, + Clearance Height deeper, the same drafts) in the body touching the rim, found and named in the dialog, or picked in its **Other Body** box; **Swap Lip and Groove** puts the lip on the other body. |
| Guide Type | **Pull Direction**: the section is extruded along the rim's normal, or along a direction picked in the **Direction** box (a plane, flat face or straight edge; one along the rim is refused). **Face Guide**: the section leans with the wall beside the edges (a drafted wall: the lip's faces go on at the wall's angle, the groove's too); walls of different draft along the chain are refused with the reason. |
| Advanced | Lip Width, Lip Height, Inner Draft, Outer Draft, Clearance, Clearance Height, Groove Width, Groove Depth, Tip Radius (round on the lip's top edges), Root Radius (blend where the lip meets the rim; the groove's mouth gets the same round, so the clearance is kept). Shown, not typed: the wall at the edges and the shoulder (reveal) left beside the lip (research: Shoulder Width = wall - lip width, derived). |
| Rule values (L9) | Lip Width = Thickness / 2, Lip Height = Reveal Height, Clearance and Clearance Height = Clearance, drafts = Draft Angle; they follow the rule until typed. |
| Manipulators | Arrows with value boxes: Lip Height and Lip Width. |
| Timeline | One step "Lip N" in the picked edges' body; the other body's change is a hidden follower step. Double-click edits. |
| Refusals | A lip / groove as wide as the wall or wider ("must be less than the wall (2.00 mm) at the selected edges": no shoulder would be left, and the groove would cut the other body's wall through), edges not on one flat face, edges that do not join, drafts that close the section, Lip And Groove with no touching body ("or use Lip alone"). |

How it is built: the picked chain is offset in the rim's plane (2D offsets with sharp joins)
to the band of the section, extruded along the pull direction; drafted sides are ruled lofts
between the bottom and top offsets. Lip and groove volumes are exact (golden models).

### Design Advice (PLASTIC > INSPECT > Design Advice)

| Fusion | SciForge |
|---|---|
| Bodies of components with a rule | The dialog starts on the shown solid bodies of components with a plastic rule (all shown bodies, with the default rule, when none has one); click a body to take it out or in. The rule of each body is named. A body in a component is named "Component/Body1" in the rule line and the issues list (two components can each hold a "Body1"); a body at the design's root by its own name. |
| Pull direction | The Z of each body's component by default (research: "Z of the component"; the design's Z at the root); click the Pull Direction box, then a plane, flat face, straight edge or axis (one direction for every body); Flip. |
| Checks | **Thickness** (outside the rule's range), **Thickness Variation** (more than the rule's percentage from its Thickness), **Draft** (less than the rule's Minimum Draft Angle against the pull either way; faces square to the pull are fine), **Knife Edges** (convex edges sharper than 2 atan(1/2) = 53.13 degrees: thinner than the knife-edge threshold one threshold in), **Undercuts** (faces a two-part mould cannot reach along the pull). Each can be switched off. |
| Overlay | Display **Issues**: green fine, blue too thin, orange too thick, yellow draft / variation, purple undercut, knife edges drawn red; **Thickness**: a map from the rule's minimum (blue) to its maximum (red). |
| Issues list | Check, body and face (edge), and the worst value; a click selects the face and zooms to it. A summary line counts each check. |
| Browser | OK keeps it in the Analysis folder (eye shows / hides, double-click reopens the dialog, Delete removes it); Undo takes it away, Redo brings it back; never a timeline step; saved with the design. It checks again whenever one of its bodies changes. |

Wall thickness at a point: the distance along the inward normal to the next face; where that
ray runs along inside a wall (a rim's top, a hole through a wall), the wall across there
(nearest face straight through to the opposite one); beside the edge where two walls meet,
where that way across runs along inside the other wall, no reading (the walls' other points
show them). Points: 8 on a small face, up to 32 on a big one (about one every 3 wall
thicknesses). The rays run against the body's display triangles (meshed once, on a copy),
looked up in a grid of cubes (only the triangles near a ray are tested), and each hit is
then moved onto the exact face it lies on (the triangles cut corners off round faces: a
1.5 mm boss wall reads 1.5 mm from both of its round sides).

## Tests

- Scenarios (real mouse and keyboard, FreeCAD 1.1.4 under xvfb):
  - `plastic2_snap` (63 checks): a snap fit on an enclosure wall and its groove; Beam Length
    typed; the catch depth arrow dragged; OK; undo / redo; edit from the timeline; Esc;
    save / reopen; the design's rule changed (linked values follow, typed ones stay); Change
    Parameters lists it; timeline Delete takes its groove step too.
  - `plastic2_snap_options` (99): Manual (no point until one is clicked, then a point
    clicked), Hook and Loop, Perpendicular, Extent Type Distance (its arrow dragged: the
    base grows by its section times the drag) and back to To Next, Automatic, Aligned,
    Independent (angles typed, a rotation handle dragged), Align To a clicked face and a
    clicked edge, the other body picked, Hide Other Body, the catch-length refusal, Esc,
    components (a moved component), Hook Body picked (refused, then Flip), a point added off
    the part (left out with a note, the same one groove), an empty design.
  - `plastic2_lip` (98): lip on a base and groove in its lid (the shoulder shown); drafts;
    height typed and dragged; the edges' body refused as the other body; Swap; Groove; Lip;
    the wall refusal; Face Guide; a direction picked along the rim refused; OK; undo / redo;
    edit; Esc; save / reopen; a lip ring on a cone's round rim (Pull Direction exact, Face
    Guide leaning with the cone, exact); walls of different draft refused; a click on the
    rim's flat face (its 4 inside edges, the same lip and groove), Cancel; a lip exactly as
    wide as the wall refused (a hair less fits).
  - `plastic2_advice` (85): checks, colours, click-to-zoom, Draft unticked, Thickness
    display, a body left out and back, the pull direction picked and flipped, OK, Undo /
    Redo (gone, back and drawn), browser eye, reopen from the browser, it follows the design
    (and waits while hidden), save / reopen, the empty bodies refusal, an empty design, a
    round boss (its 1.5 mm wall read exactly from both round faces, its hole no undercut), a
    box rounded 4 mm outside with 2 mm walls (the thin top of its walls and its 1.17 mm
    bottom corners found, the walls 2 mm elsewhere, no false alarm at the corners), a
    "Body1" in each of two components named "Housing/Body1" and "Cover/Body1".
  - `ribbon_sweep` with `SWEEP_TABS=plastic` (112): every PLASTIC command opens with no
    pop-up or error.
  - `plastic2_qa` (167, added by QA): Hide Other Body ticked before the sketch is picked (the
    base hidden once found, shown again on OK); an edit from the timeline switched to Hook
    and Loop then Cancel (the groove back exactly); the Hook Body box in an edit refused
    with the reason; an edit OK'd, Undo / Redo of the edit; Ctrl+Z inside an edit (the
    dialog cancelled, the design as before it); a sketch with no points; a sketch facing
    away from the hook body (the note, then Flip finds the groove body); a Manual point
    followed after an earlier point is deleted from the sketch (the edit shows it too);
    Beam Length 20 through the floor noted, 12 not; a
    Lip edit switched to Groove then Cancel; a Lip edit OK'd, Undo / Redo; Design Advice:
    the Display switched without checking the design again, OK without checking again,
    Esc on a second one; hidden, the Lip edited, shown, Undo and Redo (it checks the bodies
    each brings back); a plate in a component turned 90 degrees (its pull is the
    component's Z: its own 4 sides lack draft), Esc leaves nothing.
- Golden models (hand-derived volumes, `SciForgeTests/golden/models/plastic2_*.json`, 19):
  snap fit parallel, edit (taper + draft), Hook and Loop, two points Aligned, Distance
  extent, Perpendicular through a panel; Lip And Groove, drafted, Swap, Groove alone, open
  chain, round rim, tip radius, root radius (with the groove's mouth round), Face Guide on a
  tapered rim; Fusion's usual flow (a hollow box split in two, Lip And Groove, Hook and
  Loop); a lip suppressed and back; a snap fit with the history marker rolled back before it
  and to the end (the other body's step follows both); a third point off the part left out.
- Unit tests: `SciForgeTests/unit/test_plastic2_core.py` (35; the ray grid is checked
  against testing every triangle).

## QA pass (2026-10-23, branch `sf/plastic-2-qa`)

Fixed:

- **Hide Other Body ticked before a sketch was picked did nothing** (no snap fit yet, so
  no other body to hide; a body found later, after a new type or a pick, was not hidden
  either). It now hides the body the grooves / loops go in whenever the preview finds it.
- **Hook Body picked in an edit was silently ignored** (the step stays in its body's
  history). The dialog now says the hooks stay on that body and how to put them on
  another (delete, make a new one).
- **No word when no body lies in front of the catches** (e.g. a sketch on the hook body's
  own face: its normal points away from that body, so the hooks went on the other body
  and no groove was made). The dialog now notes it and points to the Body box and Flip.
- **A hook running into the other body was not mentioned** (research 2.4, G: "beam longer
  than the available distance: warning"): a beam through the floor, a catch inside a
  panel thicker than its reach, a point on top of a wall. The groove / loop step now
  notes "the hook of snap fit N runs into this body: shorten Beam Length or move the
  point" when a beam or catch overlaps that body (checked headless: through a 2 mm floor,
  a loop's floor, a too-thick panel, a point on the rim; none for the normal cases).
- **OK only looked at the Snap Fit / Lip step itself**: a failed hidden step in the other
  body (the groove, slot, loop or the Lip's groove) would have been accepted and left in
  that body's history. The dialogs now show its error and keep OK waiting, like the
  step's own (defensive: no design found that fails only there).
- **Manual points followed the wrong point after a sketch edit**: the picked points were
  kept by geometry index only, so deleting an earlier point of the sketch moved the snap
  fit to another point without a word. They are now also kept by the sketch's own
  geometry ids (kept through deletes, saved with the file); a snap fit whose picked
  points were all deleted is refused with the reason instead of taking the others.
- **Design Advice checked the whole design again for a Display change and again on OK**
  (seconds to tens of seconds on a big part). Display is now an output property (no
  recompute; the colours are redrawn from the results kept), and OK only checks again
  when a change is still waiting. Shown again after a change while hidden, it recomputes
  only itself (and what it needs), not the whole document.
- **Design Advice showed results of an undone design**: a change made while it was hidden
  is checked when it is shown again, outside that change's undo step, so an Undo brought
  the bodies back but not the results (checked headless: the 20 mm results stayed on the
  2 mm part until the next recompute). It now keeps a short record of the bodies it
  checked (volume, area, faces) and checks again after an Undo / Redo, or when shown,
  if they differ. A Redo stays available.
- **Design Advice named bodies by their label only**: with a "Body1" in two components
  the rule line and the issue rows could not say which one. A body in a component is now
  named "Component/Body1" (sf/fix-sm-polish).
- **Design Advice's default pull was the design's Z** for every body; the research's spec
  is the Z of the component. A body in a turned component (a part moulded along its own
  Z, turned into place) had the wrong faces flagged for draft and undercut. Each body now
  takes its component's Z unless a direction is picked.

Behaviour that differs from the research, kept on purpose:

- The research says Fusion's Lip wants a tangent chain and refuses edges that are not
  tangent-continuous with Pull Direction (A-LIP). SciForge accepts a rim with sharp
  corners (a plain box) with either guide and builds it exactly (offsets with sharp
  joins); refusing it would leave a beginner's box without a lip.
- Face Guide follows the wall beside the picked edges; Fusion lets you pick the guide face
  on either side of the edge (A-LIP). There is no Guide Face box: the face beside an
  inside rim edge is the only wall there.
- Default Guide Type is Pull Direction (the research's guess was Face Guide, G).

## Known gaps

- **Fusion's exact Snap Fit and Lip dialogs could not be read** (no page access, no API
  objects): labels, defaults and the Parallel / Perpendicular geometry are SciForge's
  reading (G rows above). Luca's screenshots can correct them.
- **Face Guide** leans the section with the wall when the wall has one draft along the whole
  chain; walls of different draft along one chain are refused (Fusion's per-wall behaviour
  there is not documented).
- **Lip edges must lie in one plane** (the usual flat parting face; several faces in that
  plane are fine). A parting line that steps up and down or runs over a curved face is
  refused with the reason.
- **Snap Fit "visibility controls"** (S13): meaning unknown; SciForge's reading is Hide
  Other Body.
- **Aligned to a plane or face** uses the face's centre as a point; a picked straight edge
  is a line (each catch faces straight away from it).
- **Root Radius** defaults to 0 (the research's guess is the rule's Nominal Radius, which
  would not fit the default 0.1 mm clearance without the mouth round SciForge adds).
- **Design Advice thickness** is sampled (8 to 32 points a face), not a continuous map; a
  thin spot smaller than the points' spacing can be missed, and points right beside the
  edge where two walls meet give no reading (the Thickness display blends the samples into
  a smooth map). No alert badge on the component in the browser (a shared file). A hidden
  Design Advice waits and checks again when shown. A check takes about 1.5 s for a 60-face
  enclosure with bosses, 3.5 s for a 130-face one and 25 s for a plate with 400 small holes
  (406 faces; measured in the sandbox under load); it runs in the recompute, so FreeCAD
  waits that long after a change to a checked body. That includes every preview step of
  another command's dialog (dragging a Snap Fit arrow on a checked body re-checks it each
  time): hide the analysis while editing a big part. Deferring the check until the dialog
  closes was considered in QA and left out: the check would then run after the dialog's
  undo step, and an Undo would leave the analysis describing the undone design.
- **Research G rows not built**: Hook and Loop's Loop Length / Width / Opening Length (the
  loop is sized from the hook and the clearance; only Loop Thickness is typed); Groove
  Extent and Groove Wall Thickness (a groove block built where the other body has no wall:
  SciForge cuts the groove where the wall is and notes a snap fit that finds none).
- **Injection-moulding simulation** is out of scope (outline 8).
