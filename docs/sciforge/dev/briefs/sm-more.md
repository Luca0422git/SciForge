You are building one feature area of SciForge, a FreeCAD 1.1.4 fork that must behave exactly like Autodesk Fusion. The owner, Luca, is a beginner who only tests; he wants the finished product, so build the whole area, not a slice. Read `docs/sciforge/dev/briefs/wave6-common.md` first (and `common.md` it points to).

## Your area: SHEET METAL, more forming tools (Bend, Hem, Join by Bend, Corner Closure, Lofted Flange, sheet metal Fillet / Chamfer), branch `sf/sm-more`

Fusion's behaviour, with sources: `docs/sciforge/dev/research/fusion-sheet-metal.md`. Use the
shared contract (`sheetmetal_core.py`, `sheetmetal.py`: `rule_for_body` and friends); do not
edit those two files. sm-forming owns the Flange and commits its "bend + wall at an edge"
function in `sheetmetal_form.py` early: `git merge sf/sm-forming` when you need it (and again
later for its fixes). Until then build what does not need it (Bend first). Every solid you
make must be flat walls + cylindrical bends of the rule's thickness with the rule's inner
bend radius, so sm-flat's unfolder can flatten it.

Build (each with Fusion's dialog options, live preview, handles with value boxes, timeline
step, edit later, undo/redo, refusals with the reason):
1. **Bend** (Fusion's Fold; SHEET METAL > CREATE > Bend): stationary side (a top or bottom
   face), one or more bend lines (sketch lines on or parallel to that face, crossing the
   sheet), angle, Bend Line position Start / Center / End (where the bend zone lies against
   the line in the flat state), Flip, bend relief and corner relief use as the research says;
   the moving side swings round a bend of the rule's radius; the body is changed, not added
   to. The bend zone is the flat region the bend allowance covers: build the bent zone on the
   bend's cylinders (map the zone's outline in (angle, axial) parameters: the development is
   linear), so holes in the zone come through.
2. **Hem** (CREATE > Hem): edges (several), types Flat / Open / Rolled / Teardrop / Rope /
   Double with their values (Length, Gap, Angle, Radius, Setback), Bend Position, Flip, Miter
   Corners, rule overrides.
2b. **Join by Bend** (Fusion, Sep 2026): First Edge on one sheet metal body, Second Edge on
   another of the same thickness; the plates are extended or trimmed so one bend of the
   rule's radius (or the Bend Radius override) joins them into one body; refusals for
   different thicknesses or no possible bend.
3. **Corner Closure** (where the research puts it): two flanges meeting at a corner,
   dominant / submissive edges, miter gap, the 2-bend / 3-bend relief shapes, extend aligned.
4. **Lofted Flange**: Fusion has it as the Lofted type of the Flange dialog (sm-forming's).
   Build it as its own command right under Flange in the menu (say so in your parity doc's
   gaps: one dialog later); two profiles on separate planes (lines and arcs), Brake Form
   (straight bends: facets joined by bends, unfoldable) and Die Form (smooth: shown, and the
   flat pattern refused with the reason if it cannot be developed), facet control for Brake.
5. **Sheet metal Fillet / Chamfer** (Fusion, Sep 2026; research 2.10): only the edges through
   the thickness of one sheet metal body can be picked (others refused), radius sets for
   Fillet, distance for Chamfer; the flat pattern keeps the rounds. Wire them in place of the
   SOLID Fillet / Chamfer entries of the SHEET METAL tab's MODIFY menu (keep the solid ones
   as the fallback for non-sheet-metal bodies, or keep both entries: follow the research).
6. Tests: scenarios `smmore_*.py` (8+ paths: bend a flat plate on a centre line, two bend
   lines, each hem type, a corner closure between two flanges, a brake-formed lofted flange
   from a square to a circle, edit from the timeline, undo/redo, save/reopen, Esc, a
   refusal), golden models (append to `sheetmetal_ops.py` / `sheetmetal_schema.py` in a block
   headed `# --- sm-more ---`), unit tests. Parity doc `docs/sciforge/parity/
   sheet-metal-more.md`.
