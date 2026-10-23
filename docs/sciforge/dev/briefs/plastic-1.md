You are building one feature area of SciForge, a FreeCAD 1.1.4 fork that must behave exactly like Autodesk Fusion. The owner, Luca, is a beginner who only tests; he wants the finished product, so build the whole area, not a slice. Read `docs/sciforge/dev/briefs/wave6-common.md` first (and `common.md` it points to).

## Your area: PLASTIC, part 1 (Assign / Manage Plastic Rules, rule defaults, the PLASTIC tab, Boss, Rest, Rule Fillet), branch `sf/plastic-1`

Fusion's behaviour, with sources: `docs/sciforge/dev/research/fusion-plastic.md`. The shared
contract `plastic_core.py` / `plastic.py` is yours to extend (never rename or remove:
plastic-2 calls it).

Build:
1. **Assign Plastic Rule** and **Manage Plastic Rules** (PLASTIC > SETUP) exactly as the
   research describes them (2.1, 2.2) (the dialog, the library of rules
   per plastic material with their values, In This Design, new / edit / copy / delete, the
   active rule, how a body or component gets its rule, how a physical material links in).
   Check the library values in `plastic_core.LIBRARY` against the research and correct them.
2. **Plastic bodies** where Fusion has the concept (browser icon / rule shown as the research
   says), and the rule's values used as defaults by the tools the research says use them
   (Shell thickness = nominal wall, Draft angle, Rib / Web thickness and draft, Boss sizes,
   Rule Fillet...): wire those defaults into the existing SciForge dialogs only through a
   small, guarded call (`plastic.default_for(body, "wall_thickness")` returning None for a
   body without a rule), never by changing those dialogs' behaviour for non-plastic bodies.
3. **The PLASTIC tab**: check the skeleton in `ribbon_config.py` against the research (menu
   order, which SOLID commands it repeats) and wire your items; repeated SOLID commands point
   at the existing SciForge commands.
4. **Boss** (every option the research lists: placement on sketch points or a face point,
   Alignment / the mating boss on the other half (head side / thread side), shape, hole type
   (simple / counterbore / countersink, through / blind / tapped where Fusion has it), outer
   diameter, draft angles, root fillet, ribs (count, angle, thickness, height, length,
   draft), offsets and clearance, extent to the opposite face) with live preview, handles
   with value boxes, timeline step, edit, undo/redo, refusals with the reason.
5. **Rest** (as the research describes it: a closed profile, the body, thickness, flip,
   draft; adds material where the body lies below the sketch plane and removes it where the
   body bulges past it).
5b. **Rule Fillet** (PLASTIC > MODIFY): opens SciForge's Fillet dialog in its Rule mode
   (`fillet_sets.py` has it) with the rule's Nominal Radius as the default radius.
6. Tests: scenarios `plastic_*.py` (8+ paths: rules dialog; a plastic box shelled with the
   rule's wall; a boss on a sketch point of a shelled enclosure with ribs and a counterbore;
   the mating boss on a lid; a rest; edit from the timeline; rule edit updates defaults;
   undo/redo; save/reopen; Esc; a refusal), golden models with hand-derived volumes, unit
   tests. Parity doc `docs/sciforge/parity/plastic.md`.
