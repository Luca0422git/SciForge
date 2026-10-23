### Session log: SHEET METAL, flat (branch `sf/sm-flat`, wave 6, 2026-10-23)

Built Fusion's flat side of sheet metal: the unfolder, Create Flat Pattern with the contextual
FLAT PATTERN tab (Export DXF, Finish Flat Pattern), Unfold / Refold, Rip and Convert to Sheet
Metal. Spec and gaps: `docs/sciforge/parity/sheet-metal-flat.md`. sm-forming's branch was
merged in (its Flange makes the sheet metal bodies this area lays flat).

**What Luca can do now (plain words).** Make a part of even thickness (a shelled box with
rounded corners, or a Flange), then SHEET METAL > MODIFY > Convert to Sheet Metal and click a
big flat face: SciForge measures the thickness and makes it sheet metal. SHEET METAL > Create
Flat Pattern, click a big flat face: the part is shown laid flat (the length every bend
adds is worked out from the rule's K-factor) and the ribbon shows only FLAT PATTERN. Export
DXF writes the outline, the holes, the bend lines (up and down on separate layers) and a note
per bend for a laser cutter; the green Finish Flat Pattern goes back. The Flat Pattern stays
in the browser (double-click to open it again) and follows changes to the part. To cut a slot
across a bend: MODIFY > Unfold (click the face that stays put and the bends, or tick Unfold
All Bends), sketch and cut while it is flat, then MODIFY > Refold. A closed tube or box must
be opened first with MODIFY > Rip (a face, along an edge, or between two points).

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
  `flatpattern.py` (Flat Pattern object, DXF entities), `flatpattern_dxf.py` (R12 writer,
  read-back), `unfold_panel.py` (shared picking dialog), `unfold_ui.py`, `rip_ui.py`,
  `sm_convert_ui.py`, `flatpattern_ui.py` (environment, Export DXF dialog).
- Ribbon: the five SHEET METAL entries wired, the FLAT PATTERN contextual tab (INSPECT,
  SELECT, EXPORT, FINISH FLAT PATTERN); `ribbon_ui.set_flat_pattern_mode` and `CONTEXTUAL`.
- Browser: a Flat Pattern row under its component (double-click / Edit Flat Pattern opens it,
  Export DXF, Show/Hide Bend Lines / Bend Extents, Rename, Delete).
- Icons (`tools/sciforge/icons_flatpattern.py`): sm_flat_pattern, flat_pattern, sm_unfold,
  sm_refold, sm_rip, sm_convert, fp_export_dxf, fp_finish.
- Golden ops `sf_sm_convert`, `sf_flat_pattern` (measures the flat), `sf_unfold`, `sf_refold`,
  `sf_rip`; 10 golden models `sm_flat_*` (4 of them on sm-forming's Flange); unit tests
  `test_flatpattern_core.py`; 8 scenarios `flatpattern_*`.

**FreeCAD facts and traps found**

- `Face.isInside(point, tol, checkFace)` is no "inside the face" test (it said yes for a point
  outside an L-shaped face); use `face.isPartOfDomain(u, v)` on a UV grid.
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
  `slotFinishSaveDocument`: used to save the folded part shown while the flat pattern is open.
- Ctrl+Y leaves the redone objects touched: recompute when the flat pattern opens.
- A timeline group collapses its steps into one folder button: `timeline_titles()` no longer
  lists them; click the `SciForgeGroup_*` header to open it.
- An unfold of a shape with sides cut at an angle through the thickness (sm-forming's mitres
  on the corner's bisector plane) has skin-area x T != volume: the even-thickness check uses
  the mean of both sides' areas.

**Tests run (real FreeCAD 1.1.4)**: golden `sm_flat_*` 10/10 pass; scenarios
`flatpattern_l_bracket` 46, `flatpattern_u_channel_dxf` 50, `flatpattern_unfold_refold` 40,
`flatpattern_rip_convert` 43, `flatpattern_component_rip` 23, `flatpattern_refusals` 27,
`flatpattern_environment` 27, `flatpattern_flange` 15 checks, all PASS; unit tests all pass;
`SWEEP_TABS=sheet_metal,flat_pattern ribbon_sweep`: every sm-flat command passes, the only
failure is sm-forming's Sheet Metal Rules window (needs an INTENDED entry).

**Gaps** (details in the parity doc): Refold has no inputs (folds back everything its Unfold
laid flat); material added across a bend in the flat state is refused at the Refold; the
FLAT PATTERN tab has no sketch / construction tools; no STEP export of the flat or drawing
views with a bend table; bevelled mitres are laid flat by the stationary side's outline.
