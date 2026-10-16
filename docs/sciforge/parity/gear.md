# Parity spec: Gear (spur, internal, rack)

Luca asked for "a dedicated gear tool with real-time, visual edits" and chose spur +
internal + rack (approved plan, item A3). Implemented in `src/Mod/SciForge/sciforge/`:
`gear_core.py` (no FreeCAD, unit tested: sizes, the tooth outline, every check and its
message), `gear.py` (the profile object and the Pad / Pocket step), `gear_ui.py` (the
dialog, on `primitives_ui.PlacedPanel` like the Coil). Status: **first pass**.

## Behaviour spec (what Fusion does), with sources

Fusion has **no Gear feature of its own**. It ships a "Spur Gear" sample script / add-in
(UTILITIES > ADD-INS > Scripts and Add-Ins). SciForge copies that sample's inputs and
goes beyond it (a real, editable timeline step). Source column: **Autodesk** (Autodesk's
own pages), **Forum** (Autodesk Community answers), **Guess** (not confirmed by a source
found in this session; the sample's own dialog can be checked by Luca at home).

| # | Fusion's Spur Gear sample | Source |
|---|---|---|
| 1 | It is a script / add-in run from UTILITIES > ADD-INS > Scripts and Add-Ins, not a CREATE command | Autodesk: [Create & Insert Gears in Autodesk Fusion (blog)](https://www.autodesk.com/products/fusion-360/blog/create-insert-gears-autodesk-fusion/) |
| 2 | Key inputs: number of teeth, module, pressure angle, root fillet radius; the add-in checks the largest allowable root fillet (a too large fillet gives a warning) | Autodesk: same blog |
| 3 | Module for metric gears, diametral pitch for English (inch) gears; diametral pitch = teeth / pitch diameter | Autodesk: same blog; Forum: [cadforum.cz thread quoting the sample's maths (pitch diameter = teeth / diametral pitch)](https://www.cadforum.cz/forum-archive/forum-posts/fusion-360-script-spurgear-22033.html) |
| 4 | The Pitch Diameter is shown read-only | Autodesk: same blog |
| 5 | Gear Thickness is the extruded height of the gear | Autodesk: same blog |
| 6 | Backlash is an input (the clearance between mating teeth) | Autodesk: same blog |
| 7 | Hole Diameter (a bore) is an input | Guess (in the brief from the sample's dialog; a third-party add-in has the same field: [FMGears on the Autodesk App Store](https://marketplace.autodesk.com/apps/c82ceb2d-8595-4c74-b0a8-f2d22c83364e)) |
| 8 | Standard drop-down English / Metric; Pressure Angle drop-down 14.5 / 20 / 25 degrees | Guess (from the brief; 14.5 and 20 are the commercial standards, e.g. Martin gears) |
| 9 | The result is a new component holding a sketch and an extrude; two gears make two components | Forum: [gear design thread](https://forums.autodesk.com/t5/fusion-api-and-scripts-forum/gear-design/m-p/11677680) ("they generate separate components instead of separate bodies") |
| 10 | The gear cannot be edited afterwards: changing parameters does not change it (re-run the script) | Forum: [gear design thread](https://forums.autodesk.com/t5/fusion-api-and-scripts/gear-design/m-p/11679209) ("the generated gears will not change after modifying the parameters") |
| 11 | It fails on small modules / some tooth counts (an arc of the tip comes out nearly flat) | Forum: [gear design thread, answer by Brian Ekins](https://forums.autodesk.com/t5/fusion-api-and-scripts-forum/gear-design/m-p/11675512) |
| 12 | The sample remembers the last values for the next run | Guess |
| 13 | No internal (ring) gear and no rack in Autodesk's sample (third-party add-ins add them) | Autodesk blog lists spur only; FMGears listing (spur, internal, rack) |
| 14 | Placement: the sample puts the gear at the origin of a new component (move it afterwards) | Guess |

Fusion facts re-checked by web search in this session; autodesk.com pages could only be read
through search excerpts (the fetch tool could not reach the site).

## What SciForge does

| Fusion (sample) | SciForge |
|---|---|
| Run the script from Scripts and Add-Ins | SOLID > CREATE > **Gear...** (next to Coil, own icon); also in command search (S) |
| Gear at the origin of a new component | Pick a plane or a flat face (origin squares, or a face; one selected before is taken at once), the gear's **outline follows the mouse**, click its centre (a rack: the middle of its pitch line). Mouse snapping as for the primitives |
| Inputs in a modal dialog, then one build | The same inputs in the side dialog with a **live preview**: every change (a field, a drop-down, the arrow) redraws the gear at once |
| Standard English / Metric; Module or Diametral Pitch | Same. Switching keeps the same tooth size (module 2 <-> DP 12.7) |
| Pressure Angle 14.5 / 20 / 25 | Same |
| Number of Teeth, Backlash, Root Fillet Radius, Gear Thickness, Hole Diameter | Same (Thickness also has a blue arrow with a value box; Symmetric splits it on both sides of the plane; a negative thickness goes the other way) |
| Pitch Diameter read-only | Same (a rack shows its Pitch, the distance between teeth) |
| Spur only | **Type: Spur / Internal / Rack**. Internal: the teeth point inwards, Rim Thickness is the ring outside the roots. Rack: Rack Size by Number of Teeth (length = teeth x pitch) or by Length (cut to length, centred on the click), Height = material under the roots |
| A new component | Operation **New Body** first (the gear's own body; New Component as the sample does, Join, Cut). Join onto a part that the gear does not touch makes a new body (as every SciForge tool) |
| Not editable; re-run the script | A real timeline step "Gear N" (no sketch of its own). **Double-click it to edit** every value; Undo / Redo; survives save / reopen |
| No parameters | A parameter or formula typed in Module, DP, Teeth, Backlash, Fillet, Thickness, Hole, Rim, Rack Length / Height keeps driving the gear (Change Parameters updates it) |
| Remembers its last inputs | Same within a session (the next Gear dialog starts with the last gear's values; place, operation and formulas never carry over) |
| Warns about a too large root fillet | Every value that cannot make a gear is refused in the dialog with what to change, and OK waits; the last good preview stays: too few teeth (spur < 6, internal < 12), a hole bigger than the root circle allows ("at most N mm"), a rim thinner than half a module, a fillet that does not fit ("at most N mm", worked out), a backlash that makes the teeth pointed, a rack shorter than one tooth, 0 thickness |
| Fails on small modules (flat tip arcs) | The outline is computed exactly (lines, arcs, Bezier involutes) without sketch solving; small modules work |

### Tooth form

ISO 53 / AGMA full depth for all three standards' angles: addendum 1 m, dedendum 1.25 m.
Spur: outside diameter m(z + 2), root diameter m(z - 2.5), base diameter d cos(alpha),
pitch diameter d = m z (English: d = z / DP inches). The involute is FreeCAD's own
`fcgear` (LGPL; Higuchi Bezier approximation, root fillet tangent to the flank); SciForge
copies its generator into `gear_core.py` with one change: the backlash turns each flank
by B / (2 r) towards the middle of its tooth (each tooth is B thinner at the pitch circle;
on a rack each flank moves B / 2 along the pitch line). An internal gear's tips stop at the
base circle when a full addendum would reach inside it (a non-involute tip would jam the
pinion; FreeCAD's internal gear uses 0.6 m for the same reason). Root fillet radius in mm
= fcgear's `filletCoeff` x module.

## Tests

- Unit: `SciForgeTests/unit/test_gear_core.py` (27): the copied generator equals FreeCAD's
  fcgear point for point; sizes; closed loops; the rack area worked out by hand equals the
  outline's area (Green's theorem); backlash; every refusal and its message.
- Golden: `sf_gear_spur_basic`, `sf_gear_edit_teeth`, `sf_gear_internal`, `sf_gear_english`
  (bbox analytic, volume baseline-freecad-1.1.4), `sf_gear_rack` (all analytic),
  `sf_gear_cut_block` (Pocket into a block) and `sf_gear_join_block` (Join onto it), baseline.
- Scenarios (real mouse and keyboard): `gear_spur` (main use, 24 -> 30 teeth with the
  preview, arrow drag, OK, Undo / Redo, timeline edit, Cancel, Esc), `gear_types`
  (Internal, Rack by teeth and by length, English on XZ with Symmetric, save / reopen and
  edit the rack), `gear_refuse` (refusals, a parameter driving the teeth, a cut into a
  selected face, Ctrl+Z / Ctrl+Y, New Component).

## Gaps (not built yet)

- **Helical, bevel, worm, planetary sets** and **profile shift**: not in Fusion's sample
  either; profile shift is one fcgear coefficient away if Luca needs it.
- **English 14.5 deg / fine-pitch tooth depths**: the sample may use AGMA's other
  dedendum formulas (1.157 / DP, fine pitch 1.2 / DP + 0.002 in); SciForge uses 1.25 m for
  every standard (Guess: not confirmed without the sample's code, which must not be
  copied anyway).
- **Pitch Diameter as an input** (type a diameter, get the module): read-only, as in the
  sample.
- **Mating helper** (place a second gear in mesh at the right centre distance): Fusion has
  none; worth doing with joints later.
- **Change Parameters** lists the gear's Pad Length (thickness) like an extrude's; the
  teeth, module and the rest are not listed there yet (they live on the hidden profile).
- **Number of Teeth shows two decimals** ("30.00"): FreeCAD's quantity box does not expose
  its decimals to Python.
- **Intersect** is not offered (a Pad / Pocket cannot intersect; Fusion's sample has no
  operation at all).
