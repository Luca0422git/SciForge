### Session log: PLASTIC part 1 (branch `sf/plastic-1`, wave 6, 2026-10-23)

Built Fusion's PLASTIC tab part 1: Assign / Manage Plastic Rules, the rule defaults in the
SOLID dialogs, Boss, Rest and Rule Fillet. Spec and gaps: `docs/sciforge/parity/plastic.md`.

**What a user gets (plain words, for Luca)**

- PLASTIC tab > SETUP > **Assign Plastic Rule**: pick a component (or click one of its
  bodies), pick a rule (a material with its wall thickness, draft angle, corner radius...),
  OK. The bodies take the rule's material. From then on Shell opens with the rule's wall,
  Draft with its angle, Rib / Web with 0.6 x the wall, a thin Extrude with the wall; and
  when you later edit the rule, those steps (if you kept the rule's value) change with it.
- **Manage Plastic Rules**: the rules of this design and your library; New, Edit (the fields
  open under the lists; "Thickness / 2" works), Copy, Delete, Copy to Library / Design, Set As
  Default. A rule in use, or the library's default, cannot be deleted (it says why).
- CREATE > **Boss**: draw a sketch with points on the plane where the case meets its lid
  (or just click a flat face: SciForge puts the point there and raises a standoff). Boss
  builds the screw boss in the lid (head side, counterbored clearance hole, a recess) and in
  the case (thread side, pilot hole, its tip fitting the recess). Tabs for each side and
  for ribs; Flip swaps the sides; the blue arrow moves the parting plane.
- CREATE > **Rest**: a closed sketch above a curved wall becomes a flat landing with an even
  wall under it.
- MODIFY > **Rule Fillet**: the Fillet dialog in its Rule Fillet type, the radius from the
  rule.
- Boss > **Fastener > Create Component**: real (plain) screws at every boss, in a "Fastener"
  component; Pan, Round, Flat, Hex or Hex Washer heads; they follow the boss.
- The browser shows "Plastic Rule: <name>" under Document Settings; click it to assign.

**Commits**: a807084 (Boss / Rest geometry), f7c8248 (dialogs, commands, defaults, tab),
c477760 / d506fba / 59026c1 (scenarios), d103e0f (golden), 3c708d7 (core split, unit tests),
f3d4434 (critic pass), 1599346, 1c99d05, d22b14a (Boss on a face), e0764ea (Side bodies,
docs), 45ca6b0 (fastener), 715b74d (merge of `sf/sm-forming` for its browser settings-row
hook), 98a1d05 (Plastic Rule row).

**FreeCAD facts and traps found**

- `Shape.removeSplitter()` on a boolean result can corrupt the input shapes' shared
  sub-shapes (FreeCAD 1.1.4): `base.cut(a).fuse(b).removeSplitter()` changed `base`'s volume
  from 9198 to 21463. Copy the base first (`base.copy()`).
- PartDesign Thickness with Join = Intersection (SciForge's Shell Type Sharp) leaves a half
  pipe unshelled and "Valid", no error. Join = Arc works. A silent wrong result in Shell
  (not fixed here: `shelling.py` is outside the plastic area; noted for the integrator).
- A ray along a boss axis runs down the boss's own hole: re-finding the bodies of an
  existing boss that way loses the lid. An edit keeps the bodies its steps are in.
- A rib that stops a fraction of a millimetre short of a wall leaves no room for the root
  fillet (OpenCASCADE `StdFail_NotDone`); turning the ribs or using To Next works. The dialog
  says so.
- A rib slab made a hair wider for the draft trapezoid to trim was left 0.02 mm too thick
  when the draft is 0 (found by the exact golden `plastic_boss_ribs_each`; fixed).
- `fillet_ui._select()` blocks the combo's signal: to switch the Fillet dialog's Type the way
  a click does, set the index directly (`panel.type.setCurrentIndex(...)`).
- In the iso view the lid covers the parting plane's points: the scenario picks them by
  clicking the sketch's row in the browser (a sketch picked gives all its points).
- `PartDesign::Body` faces selected in the view resolve to the body's Tip: a click on the
  floor during the Boss preview lands on the preview step's copy of the floor, so "the same
  face" is checked by plane, not by name.

**Research critic pass applied** (scratchpad `research/plastic.md`, "Critic pass"):
Constant Thickness is not in Fusion (kept as a labelled SciForge extra); the rib shape None
means no ribs (the dialog offers Chamfer / Fillet, ribs switched by the Side boxes); the head
side's recess is sized to the thread side's diameter (defaults changed, golden and hand
formulas updated); To Next ribs are web-shaped; Rule Fillet is a Fillet type (the menu
entry opens the Fillet dialog in that type).

**Contract additions** (plastic-2 may use them): `plastic.library_rules / library_rule /
save_library_rule / delete_library_rule / default_rule_name / set_default_rule / is_used /
unique_name / material_key / apply_material / plastic_components / TOOL_DEFAULTS /
apply_defaults`; `plastic_core.MATERIAL_KEYS / MATERIALS / LABELS / describe`. Nothing
renamed or removed. `assign_rule` and `rule_for_component` now also look in the user's
library and use the user's default rule.

**Shared files touched** (two guarded lines each, plus an import line): `shell_ui.py`,
`draft_ui.py`, `rib_ui.py`, `extrude_ui.py` (`plastic.apply_defaults` when the dialog
opens, `plastic.remember_links` at its OK); `ribbon_config.py`
(the five plastic-1 lines only); `browser_ui.py` / `browser_core.py` (a `_plastic_rows`
function beside sm-forming's `_settings_rows`, one call, one click branch, two menu entries,
one MENUS row). `sf/sm-forming` is merged into this branch (7f7e786) for that hook. No
FreeCAD core change.

**Tests**: scenarios `plastic_rules` (67), `plastic_boss` (58), `plastic_boss_face` (30),
`plastic_boss_fastener` (23), `plastic_rest` (39), `ribbon_sweep` with SWEEP_TABS=plastic (114) pass; golden `plastic_boss_enclosure`,
`plastic_boss_fastener`, `plastic_boss_hole_radii`, `plastic_boss_ribs_each`,
`plastic_boss_blends`, `plastic_rest_cylinder`, `plastic_rule_boss_wall`,
`plastic_rule_edit_moves_boss` pass (exact, analytic); existing scenarios of the touched
dialogs pass (shell_draft 103, shell_draft_draft 85, sweep_loft_rib 68, sweep_loft_web 57,
gaps_thin_extrude 215, extrude_feel_box 108, fillet2_rule 30, sheetmetal_rules 60,
timeline_browser 92);
`test_plastic_core.py` (21) passes; `--only base`: unit 1858 OK, golden 444 pass + 2 xfail
(existing).

**Open** (see the parity doc's Known gaps): more fastener heads / drives / thread, the
alignment root / rib outer blends, per-rib extents per point, Boss / Rest in Change Parameters, Thicken / Emboss defaults,
Rib draft, the Shell Sharp half-pipe finding.
