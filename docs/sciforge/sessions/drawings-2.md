### 2026-10-14: Drawings part 2: annotations, sheets, more views (branch `sf/drawings-2`)

Written by the drawings-2 builder (wave 4) instead of a MEMORY.md entry (every branch
editing MEMORY.md conflicts at the merge). Merge this into MEMORY.md's session log when
the branch is merged. The behaviour spec with its sources and the gaps are in
`docs/sciforge/parity/drawings.md` (part 2 rows 26-50, the gaps table, the facts list).

#### Built

All in `src/Mod/SciForge/sciforge/`, no FreeCAD core change:

- **Dimension dialog** (double-click a dimension, or DIMENSIONS > Edit Dimension):
  override, text before / after, symbol buttons, precision, Tolerance None / Symmetric /
  Deviation / Limits / Fit (ISO 286 classes, preferred fits by basis and type or
  custom, which member the dimension is, display Class / Class and tolerances / Limits /
  Fit, the fit's limits and clearance in the dialog), tolerance precision, Basic,
  Reference. `drawing_fits.py` (ISO 286 tables for 0-500 mm, holes from shafts by the
  standard's rules), `drawing_dims_core.py` (the texts), `drawing_annot.py`
  (settings kept as JSON on the dimension, written into TechDraw's Arbitrary text and
  tolerance strings, refreshed when the value changes), `drawing_annot_ui.py`.
- **Ordinate, Baseline, Chain, Arc Length** dimensions. Ordinates and arc lengths are
  SVG symbols that follow their points; baseline and chain make real TechDraw
  dimensions.
- **Leader, Feature Control Frame (with composite rows), Datum Identifier, Surface
  Texture, Edge Extension.** Annotations are TechDraw `DrawViewSymbol`s whose SVG is
  drawn from `drawing_annot_core.py` primitives (also written to the DXF); each is
  anchored to an edge by name and shape and finds it again after design changes; it
  moves with its view; dragging its text moves the text and keeps the arrow.
- **Several sheets per drawing** (`drawing_sheets.py`, `drawing_sheets_ui.py`): a
  sheet bar at the bottom of the drawing's tab (a toolbar of the MDI view), +, right-
  click New / Rename (in place) / Delete / Move Left / Right, drag to reorder, one tab
  per drawing, title blocks "n / N", typed title fields shared, the first sheet's
  deletion passes the drawing on, Undo of a sheet closes its orphan tab. Export PDF of
  all sheets in one file (`drawing_pdf.py` merges TechDraw's one-page PDFs), a DXF per
  sheet.
- **Sections with bends** (half, offset, aligned via `TechDraw::DrawComplexSection` and
  a hidden profile sketch) and **Section Depth** Full / Slice / Distance
  (`drawing_depth.py`: TechDraw keeps drawing its section; the lines that lie deeper
  than the depth are switched off one by one, matched by geometry against TechDraw's
  own hidden-line removal of the trimmed parts, again after every change). The same
  switch removes TechDraw's line along the middle of a hole cut in half (straight
  sections). Style and view label in the section and detail dialogs.
- **Breakout Section View** (`drawing_breakout.py`, `drawing_breakout_ui.py`): click a
  view, the corners of a boundary and the first corner again; the view draws a trimmed
  copy of its parts (a hidden `Part::FeaturePython` remade before the view in every
  recompute), the cut floor hatched with cosmetic lines; depth typed or Default (half
  the parts); double-click inside to change it or Remove Breakout; an isometric view
  projected from it shows the cut too.
- **Automated centre marks and centre lines** per view (Holes, Round Extrudes, Round
  Cuts), the **view label** (text, Show), a **text box dragged** open.
- Ribbon: the greyed DRAWING entries Ordinate / Baseline / Chain, Edge Extension,
  Leader, Surface Texture, Feature Control Frame, Datum Identifier, Breakout Section
  View wired; Arc Length and
  Edit Dimension added. `theme.py`: TechDraw's tolerance text at 0.7 of the value (a
  Float preference, kept and given back like the others).

Scenarios (all passing, check counts in the last run): `drawing2_tolerance` (100),
`drawing2_ordinate` (46), `drawing2_symbols` (72), `drawing2_sheets` (87),
`drawing2_sections` (77), `drawing2_views` (50), `drawing2_update` (40),
`drawing2_reopen` (44), `drawing2_breakout` (95). Unit tests: `test_drawing_fits.py`,
`test_drawing_dims_core.py`, `test_drawing_annot_core.py` (with the PDF merge),
`test_drawing_core.py` (section types, breakout boundaries). The ten older drawing
scenarios pass unchanged.

#### FreeCAD facts and traps found

- `DrawView.findParentPage()` segfaults FreeCAD for a view on no page yet (TechDraw
  dereferences a null page): never call it; use the InList.
- `DrawViewDimension.getLinearPoints()` is y-down from the view's centre: the DXF's
  linear dimension lines were mirrored before this branch (fixed).
- Tolerance texts need `EqualTolerance = False`; `ArbitraryTolerances` takes the two
  strings as they are; a two-line Arbitrary `FormatSpec` stacks limits.
- TechDraw files a "Drag Dimension" undo step when a selected dimension label is laid
  out again and then deselected: clear the selection before opening an undo step that
  changes a dimension's text.
- Never give a task panel an attribute named like a `taskui.Panel` method (`feature`):
  OK then fails inside FreeCAD ("NoneType is not callable") and the panel's sheet mouse
  handler stays alive (later clicks warn "QLabel already deleted").
- `getGeometricCenter()` uses the 3D mesh's bounding box; TechDraw centres on the exact
  one (0.02 mm apart on an R8 fillet): `drawing.centre_of` computes TechDraw's.
- `makeCosmeticVertex` / `makeCosmeticLine` take y-up points; `formatGeometricEdge(i,
  style, weight, colour, visible)` hides a geometry edge by index (indices change on
  every recompute: SciForge matches the edges by geometry and works the list out again
  after every change).
- `DrawViewSection` cuts its parent view's shape (`getShapeToCut` takes the BaseView's
  `getSourceShape()`), never its own `Source`: the first Section Depth (a trimmed copy as
  the section's Source) changed nothing on the sheet; its checks looked at the copy, not
  at the drawn lines. Test what is drawn.
- `DrawViewPart.execute()` returns at once while the view's previous hidden-line removal
  still runs: a source shape changed 30 ms after a recompute was missed (a flaky check).
  A shape a view draws must be remade inside the recompute (a FeaturePython linking its
  inputs), not after it.
- A boolean leaves a hole's straight seam (or the join of its halves) as an ordinary
  edge: TechDraw's section draws it as a hard line across the cut hole.
- A complex section's profile must be a sketch square to the parent's direction; TechDraw
  draws a line where an offset cut jogs.
- FreeCAD's MDI views are QMainWindows (a toolbar can go at the bottom); FreeCAD's MDI
  tabs are movable. A page removed by Undo while its tab shows leaves the tab open.
- PySide: a menu opened with `popup()` returns at once; scenario helpers
  (`widget_input.right_click`) expect `exec()`.

#### Gaps (see the parity doc for the reasons)

Exploded views; the breakout's spline profile, components left out of its cut; depth
and the seam fix on bent cut lines; the jog line of offset sections; a line partly
within a Distance shows whole; sheet thumbnails and per-sheet sizes;
Center Mark Pattern and Hole vs Round Cut; arranging dimensions; hole notes; Note and
Weld; multi-segment leaders and rich text; FCF / texture attached to dimensions;
separate X / Y ordinate origins; DWG, CSV.

#### Next

Luca to compare with Fusion: the Dimension dialog's order and wording, the fit display
choices, the sheet bar, the symbols' look (frame cell sizes, datum triangle, surface
texture proportions), the ordinate text direction (ISO turned, ASME level), the
breakout's dialog. Then Arrange Dimensions, hole and thread notes, the seam fix for
bent sections.
