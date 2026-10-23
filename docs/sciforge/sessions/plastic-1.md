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

**Commits** (in order): Boss / Rest geometry; dialogs, commands, defaults, tab; scenarios;
golden models; core split and unit tests; the critic pass; Boss on a face; Side bodies;
fastener; the merge of `sf/sm-forming` (its browser settings-row hook); the Plastic Rule row;
Rest Body box; rule links of the SOLID steps; hole radii; fastener heads; ribs one by one;
counterbore / alignment blends, alignment root radius (the log from 3eeb5b1 to the branch's head).

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
`plastic_boss_fastener` (23), `plastic_rest` (39) and `ribbon_sweep` with
`SWEEP_TABS=plastic` (114) pass. Golden `plastic_boss_enclosure`, `plastic_boss_fastener`,
`plastic_boss_hole_radii`, `plastic_boss_ribs_each`, `plastic_boss_blends`,
`plastic_boss_alignment_roots`,
`plastic_rest_cylinder`, `plastic_rule_boss_wall`, `plastic_rule_edit_moves_boss` pass
(exact, analytic). The existing scenarios of the touched dialogs pass: shell_draft (103),
shell_draft_draft (85), shell_draft_hollow (72), modify2_shell (53), sweep_loft_rib (68),
sweep_loft_web (57), gaps_thin_extrude (215), extrude_feel_box (108), fillet2_rule (30),
sheetmetal_rules (60), timeline_browser (92). `test_plastic_core.py` (21) passes.
`--only base` (after the merge of `sf/sm-forming`): unit 1876 OK, golden 464 pass + 2 xfail
(existing), smoke and journey pass.

**Open** (see the parity doc's Known gaps): more fastener heads / drives / thread, the
rib outer blends, per-rib extents per point, Boss / Rest in Change
Parameters, Thicken / Emboss defaults, Rib draft, the Shell Sharp half-pipe finding.
**Merge note**: `ribbon_config.py` conflicts with `sf/plastic-2` at the PLASTIC CREATE items
(Boss / Snap Fit / Lip / Rest are adjacent lines): keep both sides' lines.

### QA pass (branch `sf/plastic-1-qa`, 2026-10-23)

An independent QA session re-ran every plastic scenario, the unit tests and the golden models
(all passed as delivered), read the whole diff and walked the paths the builder's scenarios
did not. What it found and fixed, in plain words for Luca:

- **A 3D-print rule broke Draft.** The FDM PLA / PETG rules have no draft (0 degrees). With
  one of them assigned, Draft opened at 0 degrees (which Draft refuses), and a Draft made
  earlier with another rule was quietly set to 0: still "valid", but no longer drafting the
  face. Now a rule without draft leaves Draft its own angle (`plastic.usable`).
- **Editing a Boss or a Rest after the rule changed showed old numbers.** The part was built
  with the new rule (for example a root radius of 1.25 mm) but the edit dialog showed the
  old 1.0 mm. The edit now shows what the step is built with. A new Boss also showed a root
  radius clamped to half the wall while it was built with the rule's full radius.
- **Your library settings no longer change a saved design.** A Boss or Rest in a component
  without a rule took its sizes from the library's default rule at every recompute, so
  choosing another default (Set As Default) re-sized them in every such design. They now keep
  the sizes they were made with until you assign a rule to their component.
- **Rest now says which rule it uses** ("Plastic rule: ABS 2 mm", or the default rule when
  none is assigned) and takes the rule of the body it actually builds in.
- **Boss Major Draft Angle** (Fusion's counterbore wall draft) was missing and not listed as
  a gap: it is built now (0 by default), with a golden model checked by hand.
- **Flip with a picked body**: a body picked in a Side box stays on its side of the parting
  plane when you Flip (it moves to the other box), instead of an error.
- **Ribs next to a wall no longer refuse the boss.** Switching on the default ribs of a boss
  10 mm from the case's edge refused the whole boss (FreeCAD's geometry kernel cannot round
  the foot of a rib that stops 0.25 mm short of a wall). The boss is now built, those few rib
  ends are left square, and the dialog says so and how to round them.
- **Hex screw heads fit their counterbore.** A Hex or Hex Washer head was sized across its
  flats, so its corners stuck 0.2 mm into the counterbore wall (the screw collided with the
  lid). It is sized across its corners now. A Flat (countersunk) head needs a countersink:
  on a counterbore it sank into the part, so the dialog now says to pick Countersink.
- **A lid in its own component with its own rule**: each side of the boss already used the
  rule of the body it joins, but the dialog showed one rule's numbers for both sides. It now
  shows each side's own values and names both rules.
- **Rule messages** now use the names you see in the dialog ("Nominal Radius: ..." rather
  than "nominal_radius: ..."); a Thickness typed as "Thickness / 2" explains that it cannot
  use itself; a new rule switched to inches converts its numbers (2 mm becomes 0.0787 in);
  Assign says when the design's own copy of a library rule is the one used.

New tests: scenarios `plastic_qa_rules` and `plastic_qa_tools` (an empty design, reassigning
a rule and Ctrl+Z, Esc in Manage after a followed edit, renaming a rule, the zero-draft rule,
Boss on a face then Esc, a drafted Rest then Esc, a boss edited after save and reopen, a rule
assigned after reopen, Flip with a picked body, the inch rule, a lid in its own component
with its own rule), golden `plastic_boss_major_draft` and `plastic_rest_cut` (the Rest's
cut-only case, also probed on a shelled pipe crossing the plane: exact), four unit tests (25 in all). Gaps
found but not fixed are in the parity doc's Known gaps (rules of nested components; the
plastic library settings are not reset between scenarios by the test harness: every plastic
scenario resets them itself in its setup).
