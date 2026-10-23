# Wave 6 (night of 2026-10-23): what was added

Luca asked: plan everything Fusion has on its SHEET METAL and PLASTIC tabs, research it, build
it all in one go, and make the SURFACE tab complete. This is the breakdown.

How it was done: four research agents read what Autodesk publishes about these tabs (help
pages, the Fusion API reference, "What's New" posts 2022-2026, forum answers; sources in
`docs/sciforge/dev/research/`), the plan was written
(`docs/sciforge/plan-sheet-metal-plastic-surface.md`), then seven builder agents worked in
parallel, each followed by an independent QA agent that tried to break it and fixed what it
found, then three "journey" testers built whole parts across the new tools. Everything was
tested in real FreeCAD 1.1.4 with real mouse clicks (scenario tests), plus golden models
(parts with hand-calculated volumes) and unit tests. No FreeCAD core file was changed, so
the quick update is enough (no 3-hour build).

The new tabs sit where Fusion has them: SOLID, SURFACE, MESH, **SHEET METAL**, **PLASTIC**,
UTILITIES.

## SHEET METAL tab (new)

Sheet metal parts are made of flat walls and round bends of one thickness, so they can be
laid flat and laser-cut. Everything follows a **sheet metal rule** (thickness, bend radius,
K-factor, reliefs).

| Command | What it does |
|---|---|
| MODIFY > **Sheet Metal Rules** | Two lists (In This Design / Library); new, edit, copy, delete (refused while used), set active. Values can be formulas like `Thickness * 2`. Changing a rule updates every part that uses it. Also opened from "Sheet Metal Rule" under Document Settings in the browser. |
| CREATE > **New Component** | Type Standard / Sheet Metal, with a Rule box. |
| CREATE > **Flange** | Closed sketch -> flat plate (Side 1 / Side 2 / Centered). Open sketch line -> bent strip (every corner a bend). Edges of a sheet -> bend + wall: Height (drag arrow or type; Distance or To Object), Height Datum, Bend Position (Inside / Outside / Adjacent / Tangent), Angle (round handle), Flip, Width (Full Edge / Symmetric / Two Sides / Two Offsets), mitred corners (pick 4 edges = a tray), bend reliefs, rule overrides. |
| CREATE > **Lofted Flange** | A sheet transition between two shapes (e.g. square to circle): Brake Form (flat facets) or Die Form (smooth). Fusion has it inside the Flange window; here it is its own entry right under Flange. |
| CREATE > **Bend** | Fold a flat plate along sketch lines (Start / Center / End, angle, flip, several lines). A line across a tab bends only the tab and cuts relief slots. |
| CREATE > **Hem** | Fold an edge back: Flat, Open, Rolled, Teardrop, Rope, Double. |
| CREATE > **Join by Bend** | Join two sheet parts with one bend (Fusion's Sept 2026 tool). |
| CREATE > **Create Flat Pattern** | Click the face that stays put: the part laid flat (bend lengths from the K-factor), with the **FLAT PATTERN** tab: **Export DXF** (outline, holes, bend lines up/down on their own layers, bend notes) and **Finish Flat Pattern**. Stays in the browser; follows later edits; double-click to reopen. |
| MODIFY > **Fillet / Chamfer** (sheet metal) | Round or cut the plate corners (only edges through the thickness can be picked). |
| MODIFY > **Unfold / Refold** | Lay bends flat, sketch and cut across them, fold back. |
| MODIFY > **Rip** | Open a closed shape (a face, along an edge, between two points) so it can be laid flat. |
| MODIFY > **Corner Closure** | Close the corner between two flanges (gap or overlap, trim / round / square relief). |
| MODIFY > **Convert to Sheet Metal** | Turn a solid of even thickness (e.g. a shelled box with rounded inside corners) into sheet metal; the thickness is measured. |
| DRAWING > **Bend Table** / **Bend Note** | A flat pattern on a drawing gets a bend table and notes like "UP 90° R 1.00". |
| Repeated SOLID tools | Extrude, Hole, patterns, Mirror, Derive, Press Pull, Combine, Split, Move/Copy, Align, Delete, materials, Change Parameters. |

## PLASTIC tab (new)

Fusion's plastic tools work from a **plastic rule** per component: wall thickness, draft
angle, inside radius, lip height, clearance, material, and the limits Design Advice checks.

| Command | What it does |
|---|---|
| SETUP > **Assign Plastic Rule** / **Manage Plastic Rules** | Rule per component (click the component or one of its bodies). Library of 16 rules: ABS, PC, PC/ABS, PP, nylon, acetal, HIPS, HDPE, PBT, acrylic, TPE, and **FDM PLA / PETG for 3D printing**. The part takes the rule's material. |
| Rule defaults | Shell, Draft, Rib, Web and thin Extrude open with the rule's values (only in components that have a rule; other designs behave as before) and follow later rule changes. |
| CREATE > **Boss** | Screw bosses at sketch points: head side (clearance hole, counterbore / countersink) and thread side (pilot hole) on the two halves, ribs, drafts, rounded edges, alignment step; optional real screws as a component. Click a floor for a standoff. |
| CREATE > **Snap Fit** | Cantilever hooks at sketch points with the matching groove / slot / loop cut in the other half; three types, rotation modes, a warning when the hook would bend too far for the material. |
| CREATE > **Lip** | Lip on one half, groove in the other (or only one), drafts, clearances, rounded tip / root. |
| CREATE > **Rest** | A flat landing on a curved wall (for a label, a switch, a PCB). |
| MODIFY > **Rule Fillet** | The Fillet window in Rule mode with the rule's radius. |
| INSPECT > **Design Advice** | Checks wall thickness (range and variation), draft, knife edges and undercuts against the rule; colours the faces and lists the problems (click one to zoom). |

Injection-moulding simulation is out of scope (as agreed for simulation in general).

## SURFACE tab (completed)

The audit (`docs/sciforge/dev/research/surface-gaps.md`) found 25 gaps against Fusion's
current SURFACE tab. Closed:

- **Menus as Fusion's**: New Component, Create Base Feature, Derive, Pattern and Mirror in
  CREATE; Press Pull, Fillet, Chamfer, Merge, Split Body, Silhouette Split, Scale, Combine,
  Move/Copy, Align, materials and parameters in MODIFY; the ASSEMBLE group.
- **The MODIFY tools now work on surface bodies**: Split Body with a surface as the cutter
  (cut a solid with a lofted surface), Delete on the SURFACE tab removes a face without
  healing (SOLID tab still heals), Fillet / Chamfer of surface edges, Press Pull of surface
  faces, Merge faces, Move/Copy, Align, Scale, Pattern, Mirror (Join stitches the copy on),
  Split Face and Replace Face.
- **Options**: Offset Type Sharp / Rounded (Sharp default, old designs keep Rounded), Patch
  per-edge continuity + Reverse Normal / Flip, Untrim Manual + Keep Copy, Revolve Partial /
  Project Axis / To with Two Sides, Extrude of a flat face + Chain / Extend Faces, Sweep
  Path + Guide Surface and rail extents, closed lofts matched corner to corner, Extend
  Natural on curved faces + Align Edges, Stitch Operation (Join / Cut / Intersect), Trim by
  one face, Ruled Corner Type.
- **New**: INSPECT > Environmental Map Analysis (a studio reflected on the part) and, in a
  sketch, Project / Include > Isoparametric Curve.

## What is not like Fusion yet (honest list)

The full lists are in each parity doc's "Known gaps". The main ones:

- Fusion's web pages could not be opened from the build machine (only search snippets), so
  menu order, some defaults and some dialog layouts are best guesses, marked G in the docs.
  Your screenshots can correct them.
- Sheet metal: corner-relief holes are cut in the flat pattern, not in the folded part; a
  Brake Form lofted flange has no flat pattern yet (its facets meet in sharp folds); weld
  corner reliefs, 3-bend corners and Bend's crossing-line corner relief are not built; a
  flat hem keeps a 0.01 mm hairline gap (the 3D kernel cannot hold two touching layers).
- Plastic: Snap Fit / Lip shapes are SciForge's reading of Fusion's descriptions; Design
  Advice samples points (a very small thin spot can be missed) and takes seconds on big
  parts; Rib / Web have no draft yet.
- Surface: Patch Tangency Weight and Loft Align Edges are shown but greyed (the kernel has no
  such control); Extrude "Match Shape" not built (no description of it found); Press Pull on
  surfaces refuses some face combinations with the reason.

## Tests

- **73 new click-by-click scenario tests** in real FreeCAD (sheet metal 33, plastic 12,
  surface 28) plus **9 "journey" tests** that build whole parts across the new tools, the way
  you would: a bent aluminium bracket with mitred flanges, a hem, a corner closure and a
  hole, laid flat (size checked by hand against the bend maths), exported to DXF, then the
  rule's thickness changed and everything followed; a shelled tube converted, ripped and
  laid flat; a 4-flange tray; a two-part ABS enclosure with shells, four screw-boss pairs, a
  snap fit, a lip, a rest and Design Advice; hybrid surface parts (a box cut by a surface,
  patched, stitched, filleted, edited early in the timeline).
- **144 new golden models** (parts with hand-calculated volumes), 586 pass in all; unit tests
  1831 -> 1995, all pass.
- The QA agents fixed **78 bugs** before merging and the journey testers **6 more** that only
  show when tools are used together.
- Every command on the four tabs was clicked by the ribbon sweep test (374 checks, no errors).
- Three more fixes at the end, each proven by a test that fails on the old code: suppressing
  a surface step no longer blanks its body; Shell with Sharp corners no longer hands back an
  unshelled part without a word on some shapes (it now says to choose Rounded); Join by Bend
  keeps working when the joined body is deleted later.
- GitHub's full "SciForge tests" run (#258, before the last fixes): about 315 of 317 GUI
  scenarios passed, the Windows golden models passed. It was red on a test-setup detail
  (two unit tests need numpy, which the GitHub machine's Python lacks: fixed), one test
  that was too strict about where a click lands (fixed), and one older Home-screen test
  that found a crash notice left by some earlier test in the same batch: that one still has
  to be tracked down (noted in MEMORY.md for the next session). A new run on the final code
  started when this was pushed.
