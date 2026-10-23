# Parity spec: the PLASTIC tab, part 1 (rules, Boss, Rest, Rule Fillet)

Built in wave 6 on branch `sf/plastic-1` (2026-10-23). Part 2 (Snap Fit, Lip, Design Advice)
is `parity/plastic-2.md`. Code in `src/Mod/SciForge/sciforge/`:

| File | What |
|---|---|
| `plastic_core.py` | the rule contract (fields, library, expressions in `Thickness`); plastic-1 added `MATERIAL_KEYS`, `MATERIALS`, `LABELS`, `describe()` |
| `plastic.py` | where a design keeps its rules (`PlasticRules` object), assignment per component, `default_for`; plastic-1 added the user library (`library_rules`, `save_library_rule`, `delete_library_rule`, `default_rule_name`, `set_default_rule`), `is_used`, `unique_name`, `material_key`, `apply_material`, `plastic_components`, `TOOL_DEFAULTS` and `apply_defaults` |
| `plastic_rules_ui.py` | Assign Plastic Rule, Manage Plastic Rules, Rule Fillet (commands and dialogs) |
| `plastic_boss_core.py` | the Boss's settings (no FreeCAD: defaults, rule links, checks, rib angles) |
| `plastic_boss.py` | the Boss's geometry and its step `SciForge::Boss` (one per side) |
| `plastic_boss_ui.py` | the Boss dialog and command |
| `plastic_boss_fastener.py` | the Boss's screws (Fastener > Create Component), step `SciForge::BossFastener` |
| `plastic_rest.py`, `plastic_rest_ui.py` | the Rest's geometry, step `SciForge::Rest`, dialog and command |
| `ai/ops/plastic_ops.py` | golden / AI steps `sf_plastic_rule`, `sf_boss`, `sf_boss_fastener`, `sf_rest` |
| `tools/sciforge/icons_plastic.py` | icons `pl_assign`, `pl_manage`, `pl_boss`, `pl_rest`, `pl_rule_fillet` (original artwork) |

The rule defaults go into the existing dialogs by one guarded line each:
`shell_ui.py`, `draft_ui.py`, `rib_ui.py` (Rib and Web), `extrude_ui.py`
(`plastic.apply_defaults(options, body, tool)`, which does nothing for a body whose component
has no rule), and one more line at each dialog's OK (`plastic.remember_links(feature, tool)`)
links the values that are the rule's. The browser's Document Settings get a "Plastic Rule: <name>" row (the active
component's rule; a click opens Assign Plastic Rule), through the settings-row hook sm-forming
added to `browser_ui.py` / `browser_core.py` (merged from `sf/sm-forming`).

## Behaviour spec (with sources)

Sources: `docs/sciforge/dev/research/fusion-plastic.md` and its critic pass (in the
scratchpad copy `research/plastic.md`, section "Critic pass"). **A** = Autodesk (help pages
SLD-SETUP-PLASTIC-RULES, SLD-BOSS, SLD-CREATE-SOLID-FROM-SKETCH, the Fusion blog posts on
plastic rules and bosses, the July 2022 What's New, the Fusion API reference: `PlasticRule`,
`BossFeatureInput`, `BossFeatureSideInput`, the enum pages and the official Boss sample),
**F** = forum / tutorial, **G** = SciForge's guess (nothing found; Luca's screenshots can
settle it).

### Plastic rules

| Fusion | SciForge | Src |
|---|---|---|
| PLASTIC > SETUP holds Assign Plastic Rule and Manage Plastic Rules | Same, SETUP first on the tab, Assign as the big button | A (panel), G (place) |
| A rule is assigned to a component, never to a single body | Same: the component's `SciForgePlasticRule` (the root: `PlasticRules.RootRule`); a body follows its component | A |
| The Assign dialog: pick the component (browser or canvas), the rule from In This Design / Library; a row opens to show its values | Same: a component list (the design and every component), a click on a body or component in the canvas / browser picks its component, two lists whose rows open to every value | A |
| Picking a library rule copies it into the design | Same (`assign_rule`); when the design already has a rule of that name the component takes the design's copy (library edits never change a design silently) | A (copy), G (same name) |
| The rule's material becomes the component's physical material | Same for the materials SciForge's library has (ABS, PC, PP, Nylon, Acetal, Acrylic, PLA, PETG); PC/ABS, HIPS, HDPE, PBT and TPE have none yet: the dialog says the bodies keep theirs | A, G (mapping) |
| Manage Plastic Rules: two lists, a pencil to edit, New, Copy, Delete, Set As Default (library) | Same as buttons under the lists (New, Edit, Copy, Delete, Copy to Library, Copy to Design, Set As Default); Edit opens the rule's fields under the lists (not a second window) | A, G (buttons) |
| Edit Plastic Rule fields: Name, Units (fixed once made), Material, Thickness, Draft Angle, Nominal Radius, Reveal Height, Clearance, Thickness Range min / max, Thickness Variation, Minimum Draft Angle, Knife Edge Threshold | Same fields; lengths may be expressions in Thickness ("Thickness / 2"), a bare number is in the rule's units; switching a new rule's Units converts its plain numbers (2 mm becomes 0.0787 in; QA pass) | A, G (conversion) |
| Thickness must lie in the thickness range; the default library rule and a rule in use cannot be deleted | Same, each refusal said in the dialog | A |
| Editing a design rule (or giving the component another rule) updates the features that use it | Boss and Rest values that came from the rule follow it (linked until typed over; golden `plastic_rule_edit_moves_boss`). A Shell, Draft, Rib / Web or thin Extrude whose value was the rule's when its dialog was OK'd is linked too (`plastic.remember_links`, one line at each dialog's OK) and follows the rule (`plastic.follow`); a value typed over, or a formula, is left alone | A, G (links) |
| The library: Fusion ships base rules in metric and imperial and several resins | SciForge's own library (16 rules: Default mm / in, ABS, PC, PC/ABS, PP, PA66, POM, HIPS, HDPE, PBT, PMMA, TPE, FDM PLA / PETG); values checked against the research table (unit test) | A (existence), G (values) |
| The library is the user's (cloud) | The user's own rules and the default choice are kept in SciForge's settings (`Mod/SciForge/Plastic`), the built-in ones always there (an edited built-in rule replaces it) | G |
| Not a timeline step | Same (the assignment is an undo step) | G |
| The rule shows with the component (tooltip / property view) | A "Plastic Rule: <name>" row under Document Settings (the active component's), a click opens Assign; the component's property `SciForgePlasticRule` | G |

### Rule defaults in the repeated SOLID commands

| Command | Field | Rule value | Src |
|---|---|---|---|
| Shell | Inside / Outside thickness | Thickness | A |
| Draft | Angle (and the second side's) | Draft Angle; a rule without draft (0 deg: FDM PLA / PETG) leaves Draft its own angle, and a linked Draft keeps its angle (Draft refuses 0, and a Draft set to 0 silently stops drafting; QA) | A (Draft uses the rule), G (field, the 0 case) |
| Rib, Web | Thickness | 0.6 x Thickness | A (uses the rule), G (factor) |
| Extrude (thin) | Wall thickness (both sides) | Thickness | A (Extrude uses the rule), G (field) |
| Fillet, Rule Fillet | Radius | Nominal Radius (Rule Fillet only) | G |
| Boss | drafts, wall, root radius, rib thickness and draft, clearance | Draft Angle, 0.6 x Thickness, Nominal Radius, Clearance / 2 per side | A (`thickness`, `taperAngle` are rule references), G (mapping) |
| Rest | Thickness, Draft Angle | Thickness, Draft Angle | G |

A design without a rule opens every SOLID dialog exactly as before (checked in
`plastic_rules`). The PLASTIC-only tools (Boss, Rest, Rule Fillet) use the library's default
rule when the component has none, and say so in the dialog.

### Boss (PLASTIC > CREATE)

| Fusion | SciForge | Src |
|---|---|---|
| Points: sketch points of one sketch on the parting plane | Same (click a point; a sketch picked before or clicked in the browser gives all its points); points of two sketches are refused | A |
| (brief) a point on a face | A click on a flat face puts a point sketch on that face and raises the parting plane 3 x the screw (a standoff); more clicks on the same face add points; another face is refused | G |
| Side 1 = head side along the sketch's normal, Side 2 = thread side against it; Flip swaps them | Same | A |
| Each side finds the nearest visible solid body along its direction; a side with no body is left out | Same (the dialog lists the two bodies); a point with no body on either side is refused | A |
| Participant bodies may be given (else found) | Side 1 Body / Side 2 Body boxes: Auto, or click the box then a body (in the view or the browser); a picked body the side's direction does not meet is refused in the dialog; the box's x goes back to Auto; Flip moves a picked body to the other box (it stays on its side of the plane) | A (API `participantBodies`), G (boxes) |
| Offset Position moves the parting face along the normal | Same, with a blue arrow and its value box | A |
| One feature per side, joined into its body | One `SciForge::Boss` step per side in its body ("Boss 1", "Boss 2" in the timeline); both share the settings, editing either opens the one dialog | A |
| Shape: Blank / Constant Diameter (Constant Thickness "not supported yet") | Blank and Constant Diameter; Constant Thickness is offered as a SciForge extra, labelled so | A (critic C1) |
| Hole Type Simple / Counterbore / Countersink; the head side always goes through; the thread side Through / From Bottom (a floor) / From Top (a depth) | Same; head side's counterbore / countersink open from the outside face, its floor "material under the head" above the tip; thread side's at the tip | A |
| Diameter, draft (wider towards the root), hole diameter and draft, major diameter and depth, countersink angle (90) | Same | A |
| Major Draft Angle (the counterbore wall's draft) | Same, the wall widening to the counterbore's mouth (either side); 0 by default (a plain counterbore the screw head fits), not linked to the rule; a Major Tip Radius on a drafted counterbore is refused with the reason (added by the QA pass; golden `plastic_boss_major_draft`) | A (field), G (default 0) |
| Alignment Step None / In / Out with diameter, depth, draft | Same. Defaults: Side 1 In with a recess of Side 2's diameter + 2 x clearance (Fusion's sample sizes the recess to the mate's diameter), Side 2 Out of its own diameter (its tip carried on 1 mm - clearance into the recess) | A (critic C8), G (clearance, Out) |
| Offset Clearance pulls each side's tip back from the parting face | Same (rule Clearance / 2 per side) | A, G (default) |
| Root Radius, Tip Radius, Hole Start / End Radius, Major Tip / Root Radius, Alignment Tip / Root Radius | Same (root: the rule's Nominal Radius; the others 0); the hole's start radius rounds its mouth (a simple hole; the head side's hole at the tip), the end radius its blind bottom; the counterbore's mouth and floor corner; the recess's mouth and floor corner, or the spigot's top edge and foot (a spigot narrower than the tip). Made as exact revolved rounds or fillets of the cutting tools, so they cannot fail on the part | A, G (defaults) |
| Ribs per side: Quantity, Total Angle (360), Rotation from the sketch X, Thickness, Draft, Outer Draft, Length from the axis or To Next, Step Offset, a Chamfer (angle, size) or Fillet top corner; a To Next rib is web-shaped | Same; the Side 1 / Side 2 check boxes switch ribs on (Fusion's rib shape None = no ribs) | A (critic C2, CP.2 #6) |
| Each rib's extent: By Length / To Next / Suppressed (`setRibExtent`) | Each Rib: one list per rib (up to 12), for all the side's points; a changed side-wide Extent resets them | A, G (all points) |
| Fastener: Create Component (a screw at every boss, in a component of its own), Head Type, Drive, Thread Form, Length, material / finish text | Create Component with Head Type Pan / Round / Flat (countersunk) / Hex / Hex Washer and Length (0 = Auto: 0.5 mm short of the pilot hole's bottom); the head sits on the counterbore's floor, in the countersink, or on the outside face; the screws follow the boss (editing them opens the boss) | A (section), G (sizes) |
| Defaults from the screw size (Thread Diameter) | M3 by default: head side clearance hole d + 0.4, outer 2.5 d + 2.5, counterbore 2 d + 0.5, material under the head = Thickness; thread side pilot 0.8 d, outer 2.5 d, floor Thickness / 2; changing the Thread Diameter re-sizes both sides | G |

### Rest (PLASTIC > CREATE)

| Fusion | SciForge | Src |
|---|---|---|
| A closed sketch profile and a body; the profile becomes a flat face, material removed where the body bulges past it and added where it lies below, Thickness and draft | Same: what lies past the sketch plane inside the profile is cut; a plate Thickness thick under the flat face, side walls Thickness thick (drafted, wider towards the body) down to the old wall; in a shelled part the old wall inside the walls is removed (even wall, the inside open), in a solid part the pedestal is solid | A (outcome), G (construction) |
| Flip | Turns the inside round (default: the side of the part's centre of mass); a profile that lies over nothing is refused in the dialog | G |
| The body | Body box: Auto (the body the profile lies over; the sketch's own body first) or picked (click the box, then the body); the dialog says where it builds | A (a body is an input), G (box) |
| Thickness / draft from the rule | Same, linked until typed over; a blue arrow drags the thickness. The dialog says the rule ("Plastic rule: <name>", or the default "(default; no rule assigned)"); the linked values come from the rule of the body the rest builds in, and an edit shows the values it is built with now (a rule edited since) | G |

### Rule Fillet (PLASTIC > MODIFY)

| Fusion | SciForge | Src |
|---|---|---|
| A Fillet type (Fillet / Rule Fillet / Full Round Fillet), not a plastic command | The PLASTIC MODIFY menu's Rule Fillet entry opens SciForge's Fillet dialog already in its Rule Fillet type (everything else is the Fillet dialog of `fillet_sets.py`) | A (critic C3) |
| Radius | The rule's Nominal Radius | G |

## Tests

| Kind | Name | What |
|---|---|---|
| Scenario | `plastic_rules` (67 checks) | Assign (lists, values, library rule copied, material), undo / redo, Shell / Draft / Rib / thin Extrude open with the rule's values, Manage (edit with a refused range, Save, in-use and default rules not deleted, New, Copy, Set As Default, Esc drops design changes), a component's own rule picked by clicking its body, Rule Fillet's type and radius, save and reopen |
| Scenario | `plastic_boss` (58 checks) | enclosure and lid, Boss waits, points from the sketch's browser row, both sides' volumes by hand, ribs turned 45, rib 2 suppressed and back, a too wide hole refused (OK waits), OK, undo / redo, edit from the timeline with Flip then Esc, a second Boss cancelled with Esc, save and reopen |
| Scenario | `plastic_boss_face` (30 checks) | Boss and Rest in an empty design (nothing opens), a boss by clicking the floor (point sketch, standoff by hand), a second point, a body picked for Side 1 that its direction does not meet (refused) then back to Auto, another face refused, OK, undo |
| Scenario | `plastic_boss_fastener` (23 checks) | Create Component: a Fastener component with pan-head screws (volume by hand, clear of the lid), Hex and Round heads, OK, edit and untick (the component goes), undo, save and reopen |
| Scenario | `plastic_rest` (39 checks) | a shelled half pipe, Rest waits, a click in the profile, the pedestal by hand, the Body box (picked, then Auto), thicker wall, Flip refused, OK, undo / redo, edit from the timeline and Esc, save and reopen |
| Golden | `plastic_boss_enclosure` | both sides, counterbore and alignment, no drafts / fillets: exact |
| Golden | `plastic_rest_cylinder` | a solid pedestal on a round bar |
| Golden | `plastic_rule_boss_wall` | a rule edited to 2.5 mm drives a Constant Thickness boss |
| Golden | `plastic_rule_edit_moves_boss` | editing the rule after the boss moves it |
| Golden | `plastic_boss_fastener` | the enclosure's bosses with their pan-head screws (exact) |
| Golden | `plastic_boss_hole_radii` | the pilot holes' mouth and bottom rounded (Pappus, exact) |
| Golden | `plastic_boss_ribs_each` | four square ribs per boss, the second suppressed (exact) |
| Golden | `plastic_boss_blends` | counterbore tip / root, recess and spigot tip radius (Pappus, exact) |
| Golden | `plastic_boss_alignment_roots` | the recess's floor corner and a narrow spigot's foot rounded (Pappus, exact) |
| Golden | `plastic_rest_cut` | a rest whose plane lies below a round bar's crown: only cuts (exact; QA pass) |
| Golden | `plastic_boss_major_draft` | the enclosure's counterbores drafted 5 deg (frustum by hand, exact; QA pass) |
| Scenario | `plastic_qa_rules` (QA pass) | an empty design (Assign gives the default rule and is no timeline step, Ctrl+Z; Manage opens and Esc; Rule Fillet says it needs a solid); a Shell made with the rule follows a reassigned rule, Ctrl+Z puts both back; Assign names the design's copy of a library rule it already holds; Manage: an edit the Shell follows at once, Esc drops both; rename a rule (still assigned, browser row renamed), Ctrl+Z; a new rule switched to inches converts its numbers; a Draft linked to PP 1.5 mm keeps its angle when FDM PLA (no draft) is assigned, a new Draft then opens with its own 1 deg, ABS moves the linked Draft to 1 deg and makes the part ABS, Ctrl+Z (PLA, 1.5 deg) / Ctrl+Y; the browser row's right-click menu opens Manage |
| Scenario | `plastic_qa_tools` (QA pass) | Boss on a face then Esc (no step, no point sketch left); a Rest with the rule's 1 deg draft (flat 20 x 12 face), Esc; a Rest OK'd, then PMMA 2.5 mm assigned: the Rest follows, its edit says the rule and shows 2.5; a boss saved and reopened: edit from the timeline, Offset 1 (moves), Major Draft Angle 5 (frustum by hand), a rounded drafted mouth refused, OK, Ctrl+Z; the default ribs switched on at the enclosure's bosses (the rib ends by the walls left square, said, OK); PMMA assigned after reopen: the boss follows, its edit shows the rule's root radius 1.25; Side 1 Body picked (the lid) then Flip: the lid moves to the Side 2 box, no error; the lid in a component of its own (placed by the component) with PMMA 2.5 mm, the enclosure with no rule: each side found, built and shown with its own rule (volumes by hand), OK, Ctrl+Z |
| Unit | `test_plastic_core.py` (24) | the library against the research table, inch rules, expressions, refusals, describe, materials; Boss defaults, rule links, refusals, rib angles; the PLASTIC tab's wiring |

## Known gaps (not built, with the reason)

- **Boss fastener details**: Round Washer and Oval heads, Drive Type,
  Thread Form and Thread Angle, the material and finish text, and a modelled thread (the
  screw is plain; Fusion carries the thread cosmetically). Fusion's fastener has no API
  (critic CP.2 #10) so the sizes are SciForge's.
- **Boss blends not built**: the rib outer fillet and a separate rib base fillet (the ribs'
  base takes the root radius), rounds at a countersink's mouth, and an alignment root radius
  on a spigot as wide as the boss's tip (there is no corner; refused with the reason).
- **Per-rib extent per point**: Fusion sets each rib of each point; SciForge sets each rib
  once for all the side's points (Each Rib).
- **A rib ending within the root radius of a wall**: OpenCASCADE cannot round the base of
  that rib's end (StdFail_NotDone; each of those edges fails alone, every other root edge
  rounds). Since the QA pass the boss is built with those rib ends left square and the dialog
  says so ("N rib ends next to a wall are left square: ... shorten the ribs, turn them, or
  run them To Next"); before, the whole boss was refused, and the default ribs of a boss
  10 mm from the case's edge (7.75 mm long, 0.25 mm short of the inside wall) hit it. If the
  rest still cannot be rounded the dialog refuses as before. Fusion rounds them.
- **Rest clearance** (Inventor's Rest has one; Fusion's is unconfirmed) and a drafted rest on a
  profile with holes (refused with the reason: set the draft to 0).
- **Boss and Rest values in Change Parameters**: not listed (a rule-linked value would
  override a number typed there); edit them in their dialogs.
- **Rule links of steps made before the rule was assigned**: only values that were the
  rule's at the dialog's OK follow it (Fusion links the parameter when the dialog opens).
- **Thicken and Emboss defaults**: Thicken lives in the SURFACE builders' files (surface-3
  owns them); Emboss has no draft in Fusion either (critic C4) and its depth mapping is a
  guess. Not wired.
- **Rib / Web draft and base fillet** (Fusion's Design Extension step): SciForge's Rib has no
  draft yet, so the rule's draft has nowhere to go.
- **Configurations' plastic rule table**: not built (SciForge has no configurations).
- **Rules of nested components** (QA pass): a rule assigned to a component gives its
  material, and its rule links, to the bodies of its sub-components that have no rule of
  their own, but `default_for` / `rule_for_body` of such a body give no rule (no
  inheritance). Fusion's behaviour for sub-components is not documented.
- **Plastic settings between test scenarios**: the user library and the default rule
  (`Mod/SciForge/Plastic`) are not reset by `harness.run`'s `prepare()`; every plastic
  scenario resets them in its setup (`plastic_steps.clear_library_prefs`). A plastic-2
  scenario after a failed plastic one in a CI shard could inherit another default rule.

## QA pass (sf/plastic-1-qa, 2026-10-23)

Fixed: a rule without draft drove Draft to 0 (refused when opening Draft, and a linked
Draft silently stopped drafting: valid, volume of the undrafted box); Boss / Rest edits
showed the values stored when they were made, not the rule's values they are built with
after a rule edit or reassignment (root radius 1.0 shown, 1.25 built); a new boss's root
radius was clamped to T / 2 in the dialog while the step used the nominal radius; Rest did
not say which rule it used and took the active body's rule rather than the rule of the body
it builds in; rule refusals named the internal keys ("nominal_radius: ...") and a Thickness
typed as "Thickness / 2" said "unknown name 'Thickness'"; Major Draft Angle (A-api) was not
built and not listed as a gap; Flip with a body picked in a Side box kept the body on the
side number (so it was looked for on the wrong side of the plane: an error) instead of on its
side of the plane; switching a new rule's Units kept the numbers (2 mm became 2 in), they are
converted now (G); Assign showed the library's values for a library rule the design already
holds under that name, while the component takes the design's copy (it says so now); a boss
whose two bodies are in components with different rules was built with each body's rule but
showed the active body's rule's values for both sides (each side shows its own rule's values
now, and the dialog names both rules); turning on the default ribs of a boss 10 mm from the
case's edge refused the whole boss (the rib ends 0.25 mm from the wall cannot be rounded by
OpenCASCADE): those rib ends are left square now, said in the dialog. New: scenarios `plastic_qa_rules`, `plastic_qa_tools`,
golden `plastic_boss_major_draft`, unit tests. Every builder scenario, the plastic golden
models, the unit tests and the shared dialogs' scenarios pass after the fixes.

## Findings while building

- FreeCAD 1.1.4: `Shape.removeSplitter()` on a boolean result can change the shapes the result
  was made from (their shared sub-shapes): a `base.cut(...).fuse(...).removeSplitter()`
  turned `base`'s volume from 9198 to 21463. `plastic_boss` and `plastic_rest` work on
  `base.copy()`.
- FreeCAD 1.1.4: PartDesign Thickness with Join = Intersection (SciForge's Shell Type Sharp)
  returns a half pipe unshelled but "Valid" (no error, same volume); Join = Arc (Rounded)
  shells it. This is a Shell problem outside the plastic area (`shell_ui` / `shelling.py`):
  a silent wrong result to fix (refuse, or fall back to Rounded with a note).
