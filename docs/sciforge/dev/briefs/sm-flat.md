You are building one feature area of SciForge, a FreeCAD 1.1.4 fork that must behave exactly like Autodesk Fusion. The owner, Luca, is a beginner who only tests; he wants the finished product, so build the whole area, not a slice. Read `docs/sciforge/dev/briefs/wave6-common.md` first (and `common.md` it points to).

## Your area: SHEET METAL, flat (unfold engine, Unfold / Refold, Flat Pattern, DXF, Rip, Convert to Sheet Metal), branch `sf/sm-flat`

Fusion's behaviour, with sources: `docs/sciforge/dev/research/fusion-sheet-metal.md`. Use the
shared contract (`sheetmetal_core.py`: rules, `bend_allowance`, `neutral_radius`;
`sheetmetal.py`: `rule_for_body`, `is_sheet_metal_body`, `make_sheet_metal_body`); do not
edit those two files. sm-forming builds the Flange that makes sheet metal bodies; until you
merge its branch, test on solids you build yourself with Part (a plate fused with a bend made
by revolving a rectangle, and a wall).

The hardest piece, do it first: **the unfolder** (`sheetmetal_unfold.py`, FreeCAD Part, no
document, no Qt). Input: a solid of flat walls and cylindrical bends of constant thickness
T, a stationary planar face (a top or bottom face of a wall, not an edge face), K-factor.
Suggested method (prove it on real FreeCAD early): find T (distance to the parallel
opposite face); collect the faces of the stationary face's side by walking across tangent
(G1) edges only (planar <-> cylindrical), never across the sharp thickness edges; give every
face a mapping into the stationary plane: walls get rigid transforms, a bend reached across
its tangent edge is developed (a point at angle phi from that edge maps to the edge
position + phi * (R_neutral) along the in-plane direction away from the parent, where
R_neutral = R_inner + K * T, R_inner/R_outer known from the face's convexity), and the wall
beyond a bend gets (rotation about the bend axis by the bend angle) then (translation by
the developed length); map each face's wires (sample curves on bends, keep lines/circles
exact on walls), fuse the mapped faces into one flat face, extrude it by T. Also output the
bend lines (start, end, centre; up/down; angle; radius) for every bend. Holes and cuts in
walls must come through; cuts that cross a bend should too (sampled). Unit-test the pure
maths; prove the shape with golden models (flat area = sum of wall areas + bend
allowances x widths, flat volume = folded volume within tolerance, since K-factor
changes the length). Then:

1. **Create Flat Pattern** (SHEET METAL > CREATE): pick the stationary face; the flat pattern
   appears in the browser under its body (Fusion's Flat Pattern node; one per component as
   Fusion has it) and the contextual **FLAT PATTERN** tab opens (like the SKETCH and DRAWING
   contextual tabs: integration-map.md section 1) with **Export DXF** (Convert Splines to
   Polylines option; layers: outer profiles, interior profiles, bend centre lines, bend extent
   lines, text, as the research lists; bend lines up/down) and **Finish Flat Pattern**. The
   flat pattern follows later edits of the folded body. Double-click / right-click in the
   browser reopens it and exports.
2. **Unfold / Refold** (Fusion: Unfold in MODIFY): stationary face, bends to unfold or Unfold
   All Bends; the design is shown flat so the user can sketch and cut across bends; Refold
   folds it back with the cuts carried onto the folded walls (rigid for wall regions; bend
   regions mapped through the development). Timeline steps as Fusion shows them.
3. **Rip** (Face Rip, Along Edge with Gap, Between Points with Gap and offsets) so closed
   shapes (a box from a converted solid, a tube) can be flattened.
4. **Convert to Sheet Metal**: pick a wide face of a solid of uniform thickness; the detected
   thickness shown (read only); Template Rule (a new rule from the thickness) or a rule from
   the design/library (copied with the thickness set) with "Show rules with matching
   thickness only"; sharp edges between walls become bends? (follow the research; if Fusion
   needs bends already there, refuse sharp corners with the reason). A non-uniform solid is
   refused with the reason.
5. Tests: scenarios `flatpattern_*.py` (8+ paths: flat pattern of an L bracket and of a U
   channel with a hole in a wall; Export DXF read back (count entities per layer); flat
   pattern follows an edit; Unfold, cut across a bend, Refold; Rip a converted box then flatten
   it; Convert a shelled box; a refusal; undo/redo; save/reopen; Esc), golden models with
   hand-derived flat sizes, unit tests. Parity doc `docs/sciforge/parity/sheet-metal-flat.md`.
