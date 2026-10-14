# Session log: Drawings (outline 7.16), branch `sf/drawings`

Written by the Drawings builder (2026-10-14) instead of a MEMORY.md entry (see the brief:
every branch editing MEMORY.md conflicts at the merge). Merge this into MEMORY.md's session
log and status when the branch is merged.

## Built

Fusion's DRAWING workspace on FreeCAD's TechDraw, all in `src/Mod/SciForge/sciforge/`:

- `drawing_core.py` (no FreeCAD, no Qt; unit tests `SciForgeTests/unit/test_drawing_core.py`,
  41 tests): ISO / ASME sheets and scales, SciForge's own title-block template (SVG with
  FreeCAD editable texts) and its primitives for the DXF, projection (first / third angle,
  8 directions), section-line maths, dimension inference (the one Dimension command),
  dimension formats (diameter sign, R, mm / inch), parts-list rows and table, balloon
  spots, hatch lines, an R12 DXF writer and reader.
- `drawing.py` (TechDraw objects, no GUI): drawings, base / projected / section / detail /
  broken views, keeping projected views lined up, dimensions, centre marks (following
  their hole), centre lines, text, balloons, the parts list, the title block (automatic
  fields, typed fields kept), refresh after design changes (also components added to a
  Full Assembly drawing), delete with dependents, PDF and DXF export.
- `drawing_ui.py`: the drawing's tab (DRAWING ribbon only, timeline and navigation bar
  away), the mouse on the sheet (an event filter on TechDraw's QGraphicsView, page
  millimetres), preview outlines, 15 dialogs and 22 commands.
- DRAWING contextual tab and New Drawing in the application menu (`ribbon_config.py`, own
  lines only), workspace button (`ribbon_ui.py`: Design / Drawing > From Design or a
  drawing), `shell.py` (enable / disable hooks), `theme.py` (TechDraw keeps SciForge's
  window; white sheet), browser Drawings folder (open, rename, delete), icons `dw_*`.

Scenarios (all passing, check counts in the branch report): `drawing_new`,
`drawing_views`, `drawing_section`, `drawing_detail`, `drawing_dimensions`,
`drawing_annotations`, `drawing_export`, `drawing_update`, `drawing_reopen`,
`drawing_assembly`. Parity spec with sources: `docs/sciforge/parity/drawings.md`.
No FreeCAD core patch.

## FreeCAD facts and traps found

- TechDraw's hidden-line computation runs in a thread in the GUI: edges appear after a
  moment; anything that needs them (picking, extents) waits or retries.
- `DrawPage.addView` centres the view: set X / Y after adding. `DrawProjGroup` items came
  out unparented at (0, 0) and could crash: SciForge uses plain `DrawViewPart` views and
  keeps them aligned (`keep_aligned`).
- Section views: `Direction == SectionNormal`, both set before `addView`; the origin on
  the cut line; type `CutView` (a `SciForgeType` "Section" put them into the browser's
  Analysis folder). Hatch: FreeCAD's default hatch colours are green with zero alpha
  (0x00FF0000): set `GeomHatchColor` / `HatchColor` on the view object. The light theme's
  `TechDraw/Colors/PageColor` and `FaceColor` are grey and go into the PDF.
- View labels show on hover only: use `Caption`. Setting `Label` of a broken view after
  `addView` raised "Unknown C++ exception": set it before. Break objects must be sketches.
- `getVisibleEdges(True)` is scaled with Y up, `getEdgeBySelection` unscaled with Y up,
  `makeCosmeticLine` takes unscaled canonical points. Cosmetic lines are drawn from the
  view's last recompute (recompute after moving a centre mark).
- A task panel's method named `open` clashes with FreeCAD's dialog hook (it is called by
  FreeCAD): the title-block dialog's class method is `start`.
- Compare FreeCAD objects by name (`drawing.same`): Python wrappers differ.
- Showing a page's tab sets its Visibility: the document is marked changed (cleared when it
  was saved). Removing a page with undo kept leaves its tab open: close the tab first, out
  of the undo step (else Undo reopens the tab before the template exists: "Template not
  set for Page").
- FreeCAD's tree "Sync view" brings the tab of a selected object to the front: drawings are
  not put in FreeCAD's selection from the browser.
- Qt passes the keyboard to the next Tab-focusable widget when the focused one is hidden
  (timeline buttons rebuilt): a drawing's tab got it and came to the front. Its widgets
  take the keyboard on click only.
- PySide: items added through a temporary `scene()` wrapper are invalidated with it (the
  preview outlines could not be removed): keep one wrapper per panel and mark the items.
- A page's link list to bodies inside `App::Part` components must be
  `App::PropertyLinkListGlobal` (else "out of the allowed scope" on every recompute).
- TechDraw's section cut keeps a hole's seam as a hard edge: a line across the hole in a
  section through its axis (gap, core fix needed).

## Gaps (see the parity doc for the reasons)

Separate drawing files and several sheets; templates; shaded rendering (flat fill);
Section Depth, multi-segment / half / breakout sections, exploded views; detail boundary
styles; Center Mark Pattern and automatic centre marks; ordinate / baseline / chain
dimensions and dimension text editing; Leader, Note and GD&T symbols; Renumber / Align
Balloons and parts-list column choice; Export DWG / CSV and multi-sheet PDF; Rotate view.

## Next

Luca to compare with Fusion: the title block layout, the default scales and sheet, the
dimension text sizes, the parts list's place and columns. Then Section Depth and
multi-segment sections (TechDraw `DrawComplexSection`), automatic centre marks, Leader.
