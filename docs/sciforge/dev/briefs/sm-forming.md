You are building one feature area of SciForge, a FreeCAD 1.1.4 fork that must behave exactly like Autodesk Fusion. The owner, Luca, is a beginner who only tests; he wants the finished product, so build the whole area, not a slice. Read `docs/sciforge/dev/briefs/wave6-common.md` first (and `common.md` it points to).

## Your area: SHEET METAL, forming (rules, sheet metal bodies, Flange), branch `sf/sm-forming`

Fusion's behaviour, with sources: `docs/sciforge/dev/research/fusion-sheet-metal.md`. The
shared contract `sheetmetal_core.py` / `sheetmetal.py` is yours to extend (never rename or
remove: sm-flat and sm-more call it).

Build:
1. **Sheet Metal Rules** (SHEET METAL > MODIFY > Sheet Metal Rules): Fusion's dialog with the
   two lists (In This Design / Library), New / Edit (the rule fields: thickness, bend radius,
   K-factor, miter/rip/seam gap, bend relief shape + width/depth/remnant, 2-bend corner relief
   shape/placement/size, 3-bend corner relief shape/radius, units; values as numbers or
   expressions in Thickness), copy a library rule into the design, delete (refused while
   used), set the active rule; editing a rule recomputes every body that follows it. Check
   the library values against the research and correct `sheetmetal_core.LIBRARY`.
2. **Sheet metal bodies**: the browser shows them with their own icon (a bent sheet), a
   sheet-metal-aware `find_body` (SHEET METAL tools work on sheet metal bodies; SOLID tools
   keep working on them as Fusion allows: Extrude cut, Hole, patterns), the timeline names
   and icons of your steps, a rule row/indicator where Fusion shows the body's rule. Follow
   how SURFACE bodies were integrated (integration-map.md section 3).
3. **Flange** (SHEET METAL > CREATE > Flange), every mode in one dialog as Fusion has it:
   - Base flange: a closed sketch profile (or several) -> a flat sheet of the rule's thickness,
     Orientation Side 1 / Side 2 / Centered, a new sheet metal body with the chosen rule (Rule
     drop-down in the dialog), New Body / New Component.
   - Contour flange: an open profile (lines and arcs; chain) -> the profile thickened to the
     rule's thickness with every sharp corner made a bend of the rule's radius, Distance (drag
     handle), side/direction options from the research.
   - Edge flange: edges of a sheet metal body (several; tangent chain) -> bend + wall. Height
     Distance or To Object, Height Datum (Inner Faces / Outer Faces / Tangent To Bend), Bend
     Position (Inside / Outside / Adjacent / Tangent), Angle (default 90), Flip, Width (Full
     Edge / Symmetric / Two Sides / Two Offsets), mitered corners where two selected edges
     meet (2-bend corner relief by the rule), bend reliefs at bend ends that do not run the
     whole edge (Straight / Tear / Round, width, depth, remnant), and the rule overrides
     (bend radius, bend relief, corner relief) with their check boxes.
   - Live preview, the blue arrows/handles with value boxes, OK/Cancel, timeline step, edit
     from the timeline, undo/redo, refusals with the reason (curved edge, edge not on a sheet
     metal body, flange that would cross the body...).
   The geometry goes in a Qt-free `sheetmetal_form.py` (FreeCAD Part, no document) so the
   golden builder, tests and sm-more (Hem reuses your "bend + wall at an edge" function: keep
   it a clean public function with a docstring and commit it EARLY, within your first hour)
   can call it. Every solid you make must be flat walls + cylindrical bends of the rule's
   thickness, with the bend's inner radius = the rule's bend radius, so sm-flat's unfolder
   can flatten it.
3b. **New Component** gets Fusion's Type: Standard / Sheet Metal (a Sheet Metal component
   has an active rule: `sheetmetal.set_active_rule(doc, name, component)`); a small, guarded
   change in the New Component dialog that leaves the Standard path as it is.
4. The SHEET METAL tab itself: check the skeleton in `ribbon_config.py` against the research
   (menu order, which SOLID commands it repeats) and wire your items; New Component and the
   repeated SOLID commands point at the existing SciForge commands.
5. Tests: scenarios `sheetmetal_*.py` (8+ paths: rules dialog new/edit/library copy/delete
   refused; base flange from a rectangle; contour flange from an L line; edge flange on one
   edge with each height datum and bend position; edge flanges on two meeting edges with a
   miter; partial width with reliefs; To Object; edit from the timeline; rule edit
   recomputes; undo/redo; save/reopen; Esc/Cancel; a refusal), golden models with
   hand-derived volumes (an L bracket's volume = flat length x width x thickness with the
   bend allowance), unit tests for your pure code. Parity doc `docs/sciforge/parity/
   sheet-metal.md` with the behaviour table (Src A/F/G) and Known gaps.
