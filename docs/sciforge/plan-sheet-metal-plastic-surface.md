# Plan: SHEET METAL, PLASTIC and SURFACE part 3 (wave 6, 2026-10-23)

Luca, 2026-10-23 (overnight): "There are two areas of fusion that we are missing. Sheet metal
and plastic. ... plan all the features that belong in those tabs, and then build them all. In
one shot. Both tabs. And ... take a look at the surface tab and make sure everything is fully
fledged out. Research what fusion has to offer and include it in the plan."

This reverses the decision of 2026-10-09 ("No SHEET METAL, PLASTIC or MANAGE tabs"). MANAGE
(Autodesk's cloud data management) stays out of scope (outline 8).

## How Fusion's behaviour was found

Four research agents read Autodesk's help pages, the Fusion API reference (its feature input
classes give option names, enums and defaults), Autodesk's "What's New" posts 2022-2026, the
Autodesk forum and tutorials; a critic agent per tab then searched again for anything missed.
The results, with a source for every fact (A = Autodesk, F = forum/tutorial, G = our guess),
are kept in `docs/sciforge/dev/research/`:

- `fusion-sheet-metal.md`, `fusion-plastic.md`, `fusion-surface.md` (behaviour specs)
- `surface-gaps.md` (SciForge's SURFACE tab audited against Fusion's, with file:line evidence)
- `integration-map.md` (how a tab, a body kind, a step, an icon and a test plug into SciForge)

The sandbox could not open web pages (only search excerpts), so menu *order* is mostly a guess;
the *presence* of every command and most option names and defaults are sourced.

## SHEET METAL tab (new)

Fusion's sheet metal works from a **sheet metal rule** (thickness, bend radius, K-factor,
reliefs). A sheet metal body is made of flat walls and round bends of that thickness, so it can
always be laid flat (the **flat pattern**) for laser cutting.

| Command (Fusion's menu) | What it does | Builder |
|---|---|---|
| CREATE > New Component (Standard / Sheet Metal) | a component that holds sheet metal | sm-forming |
| CREATE > Flange | base flange (a closed sketch -> a flat plate), contour flange (an open sketch line -> a bent strip), edge flange (pick edges -> bend + wall), with height datum, bend position, angle, flip, width types, mitred corners, reliefs and rule overrides | sm-forming |
| CREATE > Flange, Lofted type | a flange lofted between two profiles (Brake Form / Die Form) | sm-more (own entry for now) |
| CREATE > Bend | bends a flat sheet along sketch lines (Fusion's Fold) | sm-more |
| CREATE > Hem | folds an edge back: Flat / Open / Rolled / Teardrop / Rope / Double | sm-more |
| CREATE > Join by Bend | a bend that joins two sheet bodies (Fusion, Sep 2026) | sm-more |
| CREATE > Create Flat Pattern | the part laid flat; the FLAT PATTERN tab with Export DXF (bend lines, layers) and Finish Flat Pattern | sm-flat |
| MODIFY > Fillet / Chamfer (sheet metal) | round or chamfer plate corners only (keeps it unfoldable) | sm-more |
| MODIFY > Unfold / Refold | lay bends flat, cut across them, fold back | sm-flat |
| MODIFY > Rip | open a closed shape (face, along an edge, between points) | sm-flat |
| MODIFY > Corner Closure | close the corner between two flanges with a gap and relief | sm-more |
| MODIFY > Convert to Sheet Metal | turn a solid of even thickness into sheet metal | sm-flat |
| MODIFY > Sheet Metal Rules | the rules dialog: library, In This Design, every rule field | sm-forming |
| Repeated SOLID commands | Extrude, Hole, patterns, Mirror, Derive, Press Pull, Combine, Split, Move, materials... | (existing) |

## PLASTIC tab (new)

Fusion's plastic tools work from a **plastic rule** per component (nominal wall thickness,
draft angle, nominal radius, reveal height, clearance, material, Design Advice limits).

| Command | What it does | Builder |
|---|---|---|
| SETUP > Assign Plastic Rule / Manage Plastic Rules | rule per component; library of materials (ABS, PC, PP, nylon, ..., PLA/PETG for printing) | plastic-1 |
| CREATE > Boss | screw boss with hole, counterbore/countersink, ribs, draft, fillets; the mating boss on the other half | plastic-1 |
| CREATE > Snap Fit | cantilever snap with catch and the mating groove | plastic-2 |
| CREATE > Lip | lip and groove where two halves meet | plastic-2 |
| CREATE > Rest | a flat landing on a curved wall (adds or removes material) | plastic-1 |
| MODIFY > Rule Fillet | the Fillet dialog in its Rule mode, default radius from the rule | plastic-1 |
| INSPECT > Design Advice | checks wall thickness, thickness variation, draft, knife edges, undercuts against the rule | plastic-2 |
| Rule defaults in Shell, Thicken, Draft, Rib, Web, Emboss, Extrude (thin), Fillet | values come from the component's rule | plastic-1 |
| Repeated SOLID commands | Extrude, Revolve, Sweep, Loft, Rib, Web, Emboss, Hole, Thread, Shell, Draft, ... | (existing) |

Injection-moulding simulation is out of scope (outline 8).

## SURFACE tab (part 3: everything Fusion has that SciForge did not)

The audit (`dev/research/surface-gaps.md`) lists every missing or partial command and option;
builder **surface-3** closes them, the biggest first: the MODIFY tools Fusion repeats on surface
bodies (Press Pull, Fillet and Chamfer between surfaces, Merge, Delete without healing, Scale,
Combine, Silhouette Split, Move/Copy, Align, materials, parameters), Pattern and Mirror in
CREATE, the ASSEMBLE group, Revolve's Partial / Project Axis, Extrude's Match Shape / Extend
Faces, and the remaining option gaps of `parity/surface.md`.

## How it is built

Six builder agents in parallel git worktrees (branches `sf/sm-forming`, `sf/sm-flat`,
`sf/sm-more`, `sf/plastic-1`, `sf/plastic-2`, `sf/surface-3`), briefs in
`docs/sciforge/dev/briefs/` (`wave6-common.md` + one per builder). Shared contracts written
before they start: `sheetmetal_core.py` / `sheetmetal.py` (sheet metal rules, sheet metal
bodies, bend maths) and `plastic_core.py` / `plastic.py` (plastic rules per component, the
`default_for` hook). Each builder: research gaps -> Qt-free geometry -> dialogs -> scenarios
with real clicks in FreeCAD 1.1.4 -> golden models -> parity doc. Then a QA agent per area
reviews and fixes, the orchestrator merges into `develop`, runs the tests and pushes; GitHub's
"SciForge tests" run is the full sweep.

## Known limits up front

- OpenCASCADE has no sheet metal kernel: the flat pattern is SciForge's own unfolder
  (planar walls + cylindrical bends). Die-formed lofted flanges are curved in two directions
  and cannot be laid flat exactly; that is refused with the reason.
- Fusion's exact menu order could not be read (no page access); the order follows the sources
  and SciForge's SOLID tab. Luca's screenshots can correct it.
