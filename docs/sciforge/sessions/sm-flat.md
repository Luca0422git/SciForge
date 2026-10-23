### Session log: SHEET METAL, flat (branch `sf/sm-flat`, wave 6, 2026-10-23)

Built Fusion's flat side of sheet metal: the unfolder, Create Flat Pattern with the contextual
FLAT PATTERN tab (Export DXF, Finish Flat Pattern), Unfold / Refold, Rip, Convert to Sheet
Metal, and the flat pattern in drawings (a view of it, a Bend Table). Spec and gaps:
`docs/sciforge/parity/sheet-metal-flat.md`. sm-forming's and sm-more's branches were merged
in (their Flange, Bend and Hem make the sheet metal bodies this area lays flat; the one
conflict, the MODIFY menu lines of `ribbon_config.py` next to Corner Closure, was resolved
keeping both), last at sm-forming ca79f2b and sm-more 8095fc3 (clean merges).

**What Luca can do now (plain words).** Make a part of even thickness (a shelled box with
rounded corners, or a Flange), then SHEET METAL > MODIFY > Convert to Sheet Metal and click a
big flat face: SciForge measures the thickness and makes it sheet metal. SHEET METAL > Create
Flat Pattern, click a big flat face: the part is shown laid flat (the length every bend adds
is worked out from the rule's K-factor) and the ribbon shows only FLAT PATTERN. Export DXF
writes the outline, the holes, the corner reliefs, the bend lines (up and down on separate
layers) and a note per bend for a laser cutter; the green Finish Flat Pattern goes back.
The corner reliefs (the round or square holes where two bends meet) follow the rule, or
the Flange's own Corner Relief setting when it has one; a corner closed with Corner
Closure keeps the closure's own relief. The
Flat Pattern stays in the browser (double-click to open it again, hover for its size) and
follows changes to the part. File > New Drawing with Contents Select can draw the flat
pattern; DRAWING > TABLES > Bend Table lists its bends. To cut a slot across a bend: MODIFY >
Unfold (click the face that stays put and the bends, or tick Unfold All Bends), sketch and
cut while it is flat, then MODIFY > Refold. A closed tube must be opened first with MODIFY >
Rip (a face, along an edge, or between two points).

**Built**

- `sheetmetal_unfold.py`: the unfolder. From the stationary face it walks the sheet's skin
  across tangent edges only, gives each face a map (walls rigid; bends developed: angle phi
  from the entry line -> phi (R + K T) along the sheet; the wall after a bend turned back
  about the axis and moved by the full bend allowance), pushes every face through the
  thickness as a slab, maps the slabs and fuses them. Some bends only (kept bends move
  rigidly). Checks: planar stationary face, edge face, closed loop ("add a Rip"), overlap,
  even thickness (T x mean of both sides' areas = volume), sharp corners named. Refold: what
  the flat state lost is cut from the folded part (walls rigidly; bends through the
  development, as exact ruled B-spline tools with cylinder caps), what it gained on a wall is
  added back. Bend lines (start / centre / end, up / down, angle, inner radius, allowance).
- `sheetmetal_flat.py` (Unfold / Refold steps, timeline group), `rip.py`, `sm_convert.py`,
  `flatpattern.py` (Flat Pattern object, corner reliefs, DXF entities), `flatpattern_core.py`
  (corner maths), `flatpattern_dxf.py` (R12 writer, read-back), `flatpattern_drawing.py`
  (Bend Table), `unfold_panel.py` (shared picking dialog), `unfold_ui.py`, `rip_ui.py`,
  `sm_convert_ui.py`, `flatpattern_ui.py` (environment, Export DXF), `flatpattern_drawing_ui.py`.
- Ribbon: the five SHEET METAL entries wired, the FLAT PATTERN contextual tab (INSPECT,
  SELECT, EXPORT, FINISH FLAT PATTERN), DRAWING > TABLES > Bend Table;
  `ribbon_ui.set_flat_pattern_mode` and `CONTEXTUAL`.
- Browser: a Flat Pattern row under its component (double-click / Edit Flat Pattern opens it,
  Export DXF, Show/Hide Bend Lines / Bend Extents, Rename, Delete; tooltip with its size).
- Drawings: the flat pattern in Create Drawing's Select list, its base view from the top
  (`drawing.py` 2 lines + the Bend Table refresh hook, `drawing_ui.py`).
- Icons (`tools/sciforge/icons_flatpattern.py`): sm_flat_pattern, flat_pattern, sm_unfold,
  sm_refold, sm_rip, sm_convert, fp_export_dxf, fp_finish.
- Corner reliefs on the flat: the edge Flange's own Corner Relief override (shape, size,
  placement; sm-forming's `corner_reliefs(step)`) wins over the rule; Intersection and
  Tangent placement; a corner closed by sm-more's Corner Closure gets no rule relief (the
  closure's own relief is in the folded part already). Corners are matched in the folded
  part, where the two bend axes meet.
- Golden ops `sf_sm_convert`, `sf_flat_pattern` (measures the flat), `sf_unfold`, `sf_refold`,
  `sf_rip`; 17 golden models `sm_flat_*` (6 on sm-forming's Flange, 5 on sm-more's Bend,
  Hem and Corner Closure); unit tests `test_flatpattern_core.py`; 11 scenarios
  `flatpattern_*`.

**FreeCAD facts and traps found**

- `Face.isInside(point, tol, checkFace)` is no "inside the face" test (it said yes for a point
  outside an L-shaped face); use `face.isPartOfDomain(u, v)` on a UV grid. Picking the grid
  point farthest (in grid steps) from any outside point is cheap and good enough; calling
  `distToShape` for every grid point doubled the unfold time.
- A PartDesign feature's `Shape` keeps the feature's Placement; `obj.Shape = base.Shape.copy()`
  in a FeaturePython step rotated the body (the sketch was on XZ). Pass `bodies.baked(shape)`.
  Booleans and shapes built from located faces come out baked already.
- `Part.makeLoft` of two non-planar closed B-spline rings (solid=True) gives an invalid solid
  (its caps); polygons loft fine but make hundreds of facets. A tool made of
  `Part.makeRuledSurface` sides + `Part.Face(cylinder, wire)` caps + `Part.Shell` /
  `Part.Solid` is valid and exact. The two rings must be interpolated with the same
  parameters (`interpolate(pts, Parameters=[...])`), else the ruled faces skew; a closed edge
  is split into four open pieces so both rings start at the same place.
- `ViewObject.LineColorArray` colours a Part shape's edges one by one (the bend lines of a
  compound: flat solid edges first, then the loose lines in the order added). Set the data it
  needs (BendsJson) before `obj.Shape`, since `updateData("Shape")` fires on that assignment.
- App document observers get `slotStartSaveDocument(doc, filename)` /
  `slotFinishSaveDocument` (the folded part is saved shown while the flat pattern is open) and
  `slotActivateDocument` (another design's tab closes the flat pattern).
- Ctrl+Y leaves the redone objects touched: recompute when the flat pattern opens.
- A timeline group collapses its steps into one folder button: `timeline_titles()` no longer
  lists them; click the `SciForgeGroup_*` header to open it.
- An unfold of a shape with sides cut at an angle through the thickness (sm-forming's mitres
  on the corner's bisector plane) has skin-area x T != volume: the even-thickness check uses
  the mean of both sides' areas.
- An R12 DXF is ASCII: the degree sign is `%%d`. FreeCAD's own DXF importer reads the
  SPLINE entities in it.
- A TechDraw balloon's OriginX / OriginY are offsets in the view's own (unscaled) units, and
  `getVisibleEdges(True)` is in another frame (y differs): compute anchors from the model with
  `drawing_core.to_view`.
- A boolean (sm-more's Corner Closure with a Tangent relief) can leave a face with an open
  "slit" wire (and `face.OuterWire` may be that slit), edges 0.0002 mm long, and curve ends a
  tolerance away from their vertices. Rebuilding such a face from mapped wires failed with
  "Wire is not closed" / "Wires are not coplanar": the unfolder now starts and ends every
  mapped edge at the vertices, maps slivers as lines, leaves open wires out and projects a
  developed bend onto its plane.
- A FeaturePython's `PropertyLength` reads back as a Quantity: `radius + fp.Thickness` fails
  (`float()` it first).
- The scratchpad folder is shared with other sessions: another builder overwrote probe files
  with the same names (p5.py, p6.py). Use names with the area in them.

**Tests run (real FreeCAD 1.1.4)**: every `flatpattern_*` scenario passes (counts in the
branch report), golden `sm_flat_*` 14/14, `--only base` passed (unit, golden 465 + 2 known
xfail, smoke, journey), sm-forming's 4 and sm-more's 7 scenarios pass on the merged branch,
`SWEEP_TABS=sheet_metal,flat_pattern,drawing`: every command passes but sm-forming's Sheet
Metal Rules window (needs an INTENDED entry in `ribbon_sweep.py`).

**Gaps** (details in the parity doc): Refold has no inputs (folds back everything its Unfold
laid flat); material added across a bend in the flat state is refused at the Refold; the
FLAT PATTERN tab has no sketch / construction tools; no STEP export of the flat; corner
reliefs are on the flat only (Round / Square; no weld shapes); bevelled mitres are
laid flat by the stationary side's outline; sm-more's Brake Form lofted flange has sharp
folds (no bend radius) and is refused naming the sharp edge; flanges at an inside corner
overlap when laid flat and are refused.
