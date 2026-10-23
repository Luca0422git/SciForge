### Session log: SHEET METAL, flat (branch `sf/sm-flat`, wave 6, 2026-10-23)

Built Fusion's flat side of sheet metal: the unfolder, Create Flat Pattern with the contextual
FLAT PATTERN tab (Export DXF, Finish Flat Pattern), Unfold / Refold, Rip, Convert to Sheet
Metal, and the flat pattern in drawings (a view of it, a Bend Table). Spec and gaps:
`docs/sciforge/parity/sheet-metal-flat.md`. sm-forming's and sm-more's branches were merged
in (their Flange, Bend and Hem make the sheet metal bodies this area lays flat; the one
conflict, the MODIFY menu lines of `ribbon_config.py` next to Corner Closure, was resolved
keeping both), last at sm-forming ca79f2b and sm-more 0d6f795 (clean merges).

**What Luca can do now (plain words).** Make a part of even thickness (a shelled box with
rounded corners, or a Flange), then SHEET METAL > MODIFY > Convert to Sheet Metal and click a
big flat face: SciForge measures the thickness and makes it sheet metal. SHEET METAL > Create
Flat Pattern, click a big flat face: the part is shown laid flat (the length every bend adds
is worked out from the rule's K-factor) and the ribbon shows only FLAT PATTERN. Export DXF
writes the outline, the holes, the corner reliefs, the bend lines (up and down on separate
layers) and a note per bend for a laser cutter; the green Finish Flat Pattern goes back.
The corner reliefs (the round or square holes where two flanges meet) follow the rule,
or the Flange's own Corner Relief setting when it has one; a corner closed with
Corner Closure keeps the closure's own relief, and a part folded with Bend lines
lays flat as the sheet it was bent from. The
Flat Pattern stays in the browser (double-click to open it again, hover for its size) and
follows changes to the part. File > New Drawing with Contents Select can draw the flat
pattern; DRAWING > TABLES > Bend Table lists its bends, and DRAWING > TEXT > Bend Note
writes a bend's direction, angle and radius along the bend line you click. To cut a slot across a bend: MODIFY >
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
  SELECT, EXPORT, FINISH FLAT PATTERN), DRAWING > TABLES > Bend Table, DRAWING > TEXT >
  Bend Note; `ribbon_ui.set_flat_pattern_mode` and `CONTEXTUAL`.
- Browser: a Flat Pattern row under its component (double-click / Edit Flat Pattern opens it,
  Export DXF, Show/Hide Bend Lines / Bend Extents, Rename, Delete; tooltip with its size).
- Drawings: the flat pattern in Create Drawing's Select list, its base view from the top
  (`drawing.py` 2 lines + the Bend Table refresh hook, `drawing_ui.py`); DRAWING > TABLES >
  Bend Table; DRAWING > TEXT > Bend Note (click bend centre lines; the notes follow edits).
- Icons (`tools/sciforge/icons_flatpattern.py`): sm_flat_pattern, flat_pattern, sm_unfold,
  sm_refold, sm_rip, sm_convert, fp_export_dxf, fp_finish.
- Corner reliefs on the flat: the edge Flange's own Corner Relief override (shape, size,
  placement; sm-forming's `corner_reliefs(step)`) wins over the rule; Intersection and
  Tangent placement; only corners an edge Flange mitred get one: a corner closed by
  sm-more's Corner Closure keeps the closure's relief, corners of sm-more's Bend lines
  and Hems keep what the folded part has. Corners are matched in the folded part, where
  the two bend axes meet. A Die Form lofted flange is refused naming the step
  (`Developable`); an OpenCASCADE failure inside the unfolder is said as a reason.
- Golden ops `sf_sm_convert`, `sf_flat_pattern` (measures the flat), `sf_unfold`, `sf_refold`,
  `sf_rip`; 18 golden models `sm_flat_*` (6 on sm-forming's Flange, 6 on sm-more's Bend,
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

**Tests run (real FreeCAD 1.1.4)**, on the branch with sm-forming (ca79f2b) and sm-more
(0d6f795) merged: all 11 `flatpattern_*` scenarios pass (counts in the branch report);
golden `sm_flat_*` 18/18 and the whole golden set 509 + 2 known xfail; unit tests 1909 OK;
`--only base` (unit, golden, smoke, journey) passes; every sm-more scenario (8) passes, and
every sm-forming scenario (6) passed after the sm-forming merge; `drawing_new`,
`drawing_annotations` pass; `ribbon_sweep` with `SWEEP_TABS=sheet_metal,flat_pattern,drawing`
passes (175 checks). `ribbon_customize` failed once under load in an earlier full run and
passed alone.

**Gaps** (details in the parity doc): Refold has no inputs (folds back everything its Unfold
laid flat); material added across a bend in the flat state is refused at the Refold; the
FLAT PATTERN tab has no sketch / construction tools; no STEP export of the flat; corner
reliefs are on the flat only (Round / Square; no weld shapes); bevelled mitres are
laid flat by the stationary side's outline; sm-more's Brake Form lofted flange has sharp
folds (no bend radius) and is refused naming the sharp edge; flanges at an inside corner
overlap when laid flat and are refused; a bend note's text cannot be edited.

### QA pass (branch `sf/sm-flat-qa`, 2026-10-23)

An independent QA session ran every `flatpattern_*` scenario, the unit tests and the golden
models on `sf/sm-flat` (all passed), read the whole diff, probed the unfolder in real FreeCAD
and added scenarios for the paths the builder's did not cover. What it fixed (in plain
words for Luca):

- **Rip: OK after a refused pick.** Rip showed a good gap, then a click on a curved edge was
  refused in the dialog, but OK still cut the earlier gap. OK now checks what the dialog
  shows and says why it cannot finish.
- **Unfold: OK after unticking Unfold All Bends.** After the preview, unticking the box (or
  clearing the bends) still unfolded every bend on OK. OK now takes the dialog as it is and
  asks for the bends; a part with no bend at all is refused ("There is no bend to unfold").
- **Two sheet metal bodies.** Starting Unfold on one body and then clicking the other left a
  broken Unfold in the first one. The dialog now moves cleanly to the body you click.
- **Flat pattern after a new thickness.** Changing the rule's thickness moved the plate's
  top face and the flat pattern went red ("the stationary face is gone"). It now finds the
  face again and follows, as Fusion's does (golden `sm_flat_thickness_change`).
- **Flat pattern after a Move.** Moving the part with MODIFY > Move (even a plain shift)
  turned the flat pattern red. It now keeps its face and follows (golden
  `sm_flat_moved_body`).
- **Flat pattern while unfolded.** With an Unfold not yet refolded, the flat pattern (and so
  the DXF) lost the bend lines of the bends already laid flat, without a word. It now shows
  the part as it was before the Unfold, and Create Flat Pattern asks you to Refold first.
- **Flat pattern in a hidden component.** Opening it showed an empty screen; now its
  component is shown while it is open and hidden again when you finish.
- **Export DXF over an existing file.** A file name typed in the box replaced an existing
  file without asking; OK now says it exists and a second OK replaces it.
- Smaller: Show/Hide Bend Lines always closes its undo step; the "face is gone" message
  now says to delete and recreate the flat pattern (Edit Flat Pattern cannot pick a face).

New golden models: `sm_flat_thickness_change`, `sm_flat_moved_body`. New scenarios:
`flatpattern_qa_paths`, `flatpattern_qa_partial`, `flatpattern_qa_two_bodies`,
`flatpattern_qa_hidden_component` (details in the parity doc's Tests). FreeCAD facts: a FeaturePython step's preview made in one body must be removed when a
pick dialog switches to another body (PickPanel.switch_body keeps the subclass's target);
a PartDesign step's Shape is in its body's frame while `body.Shape` carries the body's
Placement; a golden model cannot see that a Part::FeaturePython went Invalid (its last
shape stays), so a QA golden changes the rule after the edit to force a new flat.
`sketch_draw` fails its "sketch palette shown" check on this machine both on this branch and
on the develop base before sm-flat (d50a665): not caused by this area.
