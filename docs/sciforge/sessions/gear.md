# 2026-10-16: Gear tool, spur / internal / rack (branch `sf/gear-1`)

Luca asked for "a dedicated gear tool with real-time, visual edits" and chose spur +
internal + rack (approved plan, item A3). Spec with sources, what is built and the gaps:
`docs/sciforge/parity/gear.md`. No core patch (no full build needed). MEMORY.md not edited
(this file is the session log entry).

## What was built

- `sciforge/gear_core.py` (no FreeCAD, no Qt): sizes (d = m z, outside m(z + 2), root
  m(z - 2.5), base d cos alpha, English m = 25.4 / DP), the closed outline as data (lines,
  3-point arcs, Bezier poles, circles), every check with a message that says what to change
  (largest fillet worked out by bisection), the exact area by Green's theorem (also used by
  the scenarios' expected volumes) and the preview polylines.
- FreeCAD's `fcgear` involute generator is **copied** into gear_core (LGPL, credited) with
  one added parameter, `thinning` (the backlash), because fcgear has no backlash and its
  closing checks need the thinned angles. A unit test checks the copy equals FreeCAD's
  module point for point (loaded from `src/Mod/PartDesign/fcgear/involute.py`).
- `sciforge/gear.py`: `GearProfile` (a hidden `Part::Part2DObjectPython`, attached
  FlatFace to the clicked plane / face, origin on the gear's centre, properties Module,
  DiametralPitch, Teeth, ... so a parameter can drive them) and the step: a
  `PartDesign::Pad` (Join / New Body / New Component) or `PartDesign::Pocket` (Cut) with
  `SciForgeType = "Gear"`, options as JSON in `SciForgeGear`. Built with the same helpers as
  the Coil (`primitives.build_step`, `local_support`, `attachment_offset`, formulas).
- `sciforge/gear_ui.py`: `GearPanel(PlacedPanel)`, one click (the centre) after the plane;
  the outline of the real gear follows the mouse while placing (cached per values); a
  thickness arrow with value box; Type / Standard / Rack Size switch the visible fields;
  read-only Pitch Diameter (Pitch for a rack); the last gear's values are the next one's
  (session only). `EDITORS["SciForge::Gear"]` makes the timeline / browser double-click open
  it.
- One line each in shared files: `ribbon_config.py` (Gear after Coil), `timeline_core.py`
  (kind "gear"), `primitives.py` (`HELPER_ROLES` + "GearProfile", so a left-behind profile
  is tidied like a coil section), golden `builder.py` / `schema.py` (import `gear_ops` /
  `gear_schema`), `tools/sciforge/make_icons.py` (an original gear icon).

## FreeCAD facts and traps found

- FreeCAD 1.1's Pad has `SideType` ("One side" / "Two sides" / "Symmetric"); `Midplane` is
  deprecated and prints a warning when set.
- A `PartDesign::Pocket` on a profile cuts against the profile's normal; `Reversed` makes it
  go along it. So the signed thickness (into the part negative, like Fusion) maps to
  `Pocket.Reversed = thickness > 0` and `Pad.Reversed = thickness < 0`.
- A flat face's FlatFace frame has its origin at the face's own corner (the Box's first
  corner), not at the global origin: golden steps placed on a face give x, y in that frame
  (sf_gear_cut_block uses 30, 30 for the middle of a 60 mm block made from (-30, -30)).
- fcgear's Bezier involute ends about 0.001 mm beyond the tip circle (the Higuchi fit):
  golden bounding boxes of spur gears use abs_tol 0.005.
- fcgear's internal gear uses addendum 0.6 m: that is about where the tips meet the base
  circle for 20 deg and 20 teeth. SciForge uses the full 1 m, cut back to the base circle
  when it would reach inside it.
- Internal gears' spaces narrow outwards, so their root fillet fits much less than a spur
  gear's (24 teeth, module 2: 0.744 mm vs 1.146 mm); the default fillet is 0.5 mm so every
  type starts valid.
- The origin squares are as big as the design (1.15 x its reach): a scenario's plane click
  must avoid the parts already made (a click on a gear's side face is not a plane).
- `Gui::QuantitySpinBox.setDecimals` is not reachable from Python: Number of Teeth shows
  "30.00".

## Tests (all with the real FreeCAD 1.1.4)

- Unit `test_gear_core.py`: 27 tests, pass (whole unit suite 1283, pass).
- Golden: sf_gear_spur_basic, sf_gear_edit_teeth, sf_gear_internal, sf_gear_english,
  sf_gear_rack (analytic), sf_gear_cut_block: pass.
- Scenarios: gear_spur (59 checks), gear_types (50), gear_refuse (38): pass.

## Gaps

See the end of `docs/sciforge/parity/gear.md`: helical / bevel / worm, profile shift,
AGMA's other English tooth depths, a mating helper, the gear's values in Change Parameters,
Intersect.
