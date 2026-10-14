# Parity spec: Drawings (outline 7.16)

Fusion's DRAWING workspace: a 2D drawing made from a design, with views placed by clicks,
section and detail views, centre marks, dimensions, notes, a title block filled from the
design, a parts list with balloons for assemblies, and PDF / DXF export; the drawing
follows the design when the design changes. SciForge builds it on FreeCAD's TechDraw
(`DrawPage`, `DrawSVGTemplate`, `DrawViewPart`, `DrawViewSection`, `DrawViewDetail`,
`DrawBrokenView`, `DrawViewDimension`, `DrawViewBalloon`, `DrawViewAnnotation`,
`DrawViewSymbol`, cosmetic lines and centre lines) with its own Fusion-style commands.

Implemented in `src/Mod/SciForge/sciforge/`: `drawing_core.py` (no FreeCAD, no Qt: sheets,
scales, the title block template, projection and section maths, dimension inference,
parts-list rows and table, hatch lines, a DXF writer; unit tests
`SciForgeTests/unit/test_drawing_core.py`), `drawing.py` (the TechDraw objects, no GUI),
`drawing_ui.py` (the drawing's tab, the mouse on the sheet, the dialogs and the 22
commands), the contextual DRAWING tab in `ribbon_config.py` / `ribbon_ui.py`, the
Drawings folder of the browser (`browser_core.py`, `browser_ui.py`), icons `dw_*`
(`tools/sciforge/make_icons.py`). No FreeCAD core change.
Status: **built and tested with real clicks in the real FreeCAD 1.1.4; not yet checked by
Luca against Fusion.**

## Behaviour spec (researched 2026-10-14)

Sources: **Autodesk** = Autodesk's Fusion help (help.autodesk.com/cloudhelp/ENU/Fusion-Drawing,
read through search excerpts: the site does not answer directly here), Autodesk Learn
tutorials and Autodesk's Fusion blog; **Forum** = Autodesk Community answers; **Guess** = no
source found, chosen to match the rest of Fusion. Behaviour only: nothing of Fusion's
wording, artwork or templates is copied (the title block is SciForge's own drawing).

| # | Fusion behaviour | Source |
|---|---|---|
| 1 | File > New Drawing > From Design (also Workspace > Drawing > From Design) opens the **Create Drawing** dialog | Autodesk: "Create a new drawing from a design" (DWG-CREATE-FROM-DESIGN), "Create Drawing reference" (DWG-REF-CREATE-DRAWING) |
| 2 | **Contents**: Full Assembly, Visible Only, or Select (pick components) | Autodesk: DWG-REF-CREATE-DRAWING; Learn "create drawings for components and assemblies" |
| 3 | Template (from scratch or a template), **Standard** ASME or ISO, **Units** in or mm, **Sheet Size** listed by standard (ISO A4..A0, ASME A..E) | Autodesk: "Create drawings from designs" (ASM-NEW-DRAWING-FROM-DESIGN), "Sheet Size reference" (DWG-REF-SHEET-SIZE) |
| 4 | Automatic (views made from the template) or Manual creation | Autodesk: DWG-CREATE-FROM-DESIGN |
| 5 | ISO drawings use first angle projection, ASME third angle; fixed once the drawing exists | Forum: "First and Third angle projection are WRONG", "Templates changing from third angle to first angle" |
| 6 | The drawing opens in its own document tab with the Drawing workspace; you are asked to place the base view | Autodesk: DWG-CREATE-FROM-DESIGN |
| 7 | **Base View**: Orientation (standard views, Home), Style (Visible Edges, Visible and Hidden Edges, Shaded, Shaded with Hidden Edges), Scale (a list or typed: ratio, fraction, decimal); Tangent Edges Full Length / Shortened / Off; the view follows the mouse, a click places it, OK | Autodesk: "Placeholder View reference", "Drawing View dialog" (DWG-REF-DRAWING-VIEW-DLG), Learn tutorials |
| 8 | **Projected View**: pick the parent view, move around it (right, left, top, bottom and the four isometric corners), click to place each, Enter or Esc ends; it inherits the parent's style and scale and moves with it | Autodesk: DWG-PROJECTED-VIEW, Learn "create projected views" |
| 9 | Double-click a view: its Drawing View dialog | Autodesk: Learn "create a section view" |
| 10 | **Section View**: pick the parent view, click the cut line's points, place the view; label A-A, hatched cut faces; Section Depth Full / Slice / Distance; lines with several segments | Autodesk: Learn "create a section view"; Forum: "Section Views acting odd" (half / aligned sections) |
| 11 | **Detail View**: pick the parent, click the centre, the circle follows the mouse, click its size, place the view at a larger scale | Autodesk: Learn "Create a detail view in a Fusion drawing" |
| 12 | **Break View**: pick start and end points, set the gap; horizontal or vertical from the view's shape; the orientation of a break cannot be changed later | Autodesk: "Break views" (DWG-BREAK-VIEW), "Break View reference", "Edit a break in a view" |
| 13 | **Center Mark** on circles (with extension lines on full circles), **Centerline** between two parallel edges, Center Mark Pattern; the view dialog can add them to every hole | Autodesk: "Create a center line" (DWG-ADD-CENTERLINE), Learn "create center marks and center lines in Fusion drawings" |
| 14 | One **Dimension** command makes the right kind (linear, aligned, angular, radius, diameter) from what is picked; isometric views cannot be dimensioned; separate Linear / Aligned / Angular / Radius / Diameter commands too | Autodesk: "Dimensions (Drawing workspace)" (DWG-DIMENSIONS); Autodesk blog "How To Create an Angular Dimension in a Fusion 360 Drawing" |
| 15 | Diameter style follows the standard (ISO aligned, ASME leader) | Forum: "trying to jog my dimensions" |
| 16 | **Text**: click two corners of the text box, type, finish; Esc cancels | Autodesk: "Create and modify text" (DWG-CREATE-TEXT) |
| 17 | Title block attributes filled from the design (part name, part number, description, material, created by, date, scale, paper size, sheet number); double-click the title block to type values, typed values override the design's | Autodesk: "Edit attributes in a title block" (DWG-TITLE-BLOCK-EDIT-ATTRIBUTES), "Properties reference" |
| 18 | **Table** (parts list) for the components a view shows: Item, Qty, Part Number, Description, Material; placed on the lower half of the sheet the header goes to the bottom; balloons are added to the view | Autodesk: "Create a parts list" (DWG-CREATE-PARTS-LIST), "Edit Parts List reference"; Learn "Create a parts list and add balloons" |
| 19 | **Balloon**: click an edge of a component on a view, then where the balloon goes; its number is the component's item in the parts list; Esc ends; balloons need a parts list | Autodesk: "Create balloons" (DWG-CREATE-BALLOON); Forum: "Balloons for top-level components" |
| 20 | **Export PDF** (current / selected / all sheets, Open PDF, uniform thin lines), **Export DXF** (current sheet), DWG and CSV | Autodesk: "Export to PDF" (DWG-EXPORT-PDF), "Export to DXF" (DWG-EXPORT-DXF), "DWG export" |
| 21 | The drawing is linked to the design; when the design changes the drawing shows it is out of date and updates | Forum: "Drawing not updated from design", "Drawing not linked to original design file" |
| 22 | Toolbar groups CREATE, MODIFY, GEOMETRY, DIMENSIONS, TEXT, SYMBOLS, TABLES, EXPORT | Autodesk: "Drawing workspace reference" (DWG-REF-DRAWING-TAB) |
| 23 | Undo / redo per command; Esc cancels a command in progress | Guess (as everywhere in Fusion) |
| 24 | Section labels skip letters that read as digits (I, O, Q...) | Guess (ASME Y14.3 practice) |
| 25 | A detail view is drawn at twice its parent's scale by default | Guess |

## What the user does (and what SciForge does)

| Fusion | SciForge |
|---|---|
| File > New Drawing > From Design; Workspace > Drawing > From Design | Same: the application menu's **New Drawing**, and the workspace button **DESIGN > Drawing > From Design...** (that menu also lists the design's drawings). An empty design is refused: "There is nothing to draw yet: the design has no solid bodies..." |
| Create Drawing: Contents, Template, Standard, Units, Sheet Size, Automatic / Manual | Same: Contents Full Assembly / Visible Only / Select (Select shows the bodies, "Component / Body", to tick); Template *SciForge title block* or *Blank sheet (frame only)*; Standard ISO / ASME (ISO for an mm design, ASME for an inch one); Units mm / in; Sheet Size ISO A4..A0 (A3) or ASME A..E (B); Views Manual or Automatic (base view, two projected views and an isometric one at an automatic scale, one undo step) |
| The drawing opens in its own tab | Same: a tab "<design> Drawing" ("... Drawing 2" for the next). While it is the active tab the ribbon shows only the **DRAWING** tab, the workspace button says DRAWING, the timeline and the navigation bar step aside; another tab brings the design's ribbon back |
| Base View: the view follows the mouse, a click places it; Orientation, Style, Scale, Tangent Edges; OK | Same: Orientation Front / Back / Top / Bottom / Left / Right / Home; the four styles (Shaded is drawn as faces filled with one light colour, see gaps); Scale from the list (50:1 .. 1:200) or typed (1:2.5, 1/4, 0.5); Tangent Edges Full Length / Off. The changes show live; Esc / Cancel leaves nothing. The title block's Scale follows the base view |
| Projected View | Same: the only base view is the parent (else click one); moving round it shows the view that will be made (first angle: the view from above goes below; third angle: above), the four corners give isometric views; a click places each; back over the parent the preview goes; Enter / Esc ends; the projected views are one undo step. They take the parent's style and scale, and stay lined up when the parent is dragged or turned |
| Double-click a view | Its dialog: Base View (orientation, style, scale, tangent edges; the projected views turn with it), Section, Detail, or Edit View (style; a broken view's gap). Cancel puts everything back. Views are moved by dragging their frame |
| Section View | Click the view, then the cut line's two ends (a line within 3 degrees of horizontal or vertical is straightened), move to the side to look from and click to place: **SECTION A-A** under the view, the cut line with arrows and letters on the parent, the cut faces hatched at 45 degrees, lined up with the parent. Label (B-B...), Scale and Hatch on / off in the dialog. Letters skip I, O, Q, S, X, Z |
| Detail View | Click the view, the centre (it snaps to a fillet's or hole's centre), the circle's size, then place the view: **DETAIL A (2:1)** at twice the parent's scale, a circle and letter on the parent. Label and Scale in the dialog |
| Break View | Click the view, then the two ends of the part to leave out: the broken view stands in for the view (the original is hidden), the break follows the direction of the two clicks; Gap (10 mm) in the dialog and in Edit View. Selecting the broken view and Del brings the original view back |
| Center Mark, Centerline | Center Mark: click circles or arcs; two dash-dot lines cross at the centre, 3 mm past the circle; a hole that has one is said; a straight edge is refused ("click a circle"); Enter / Esc ends. Centerline: click two parallel edges: a dash-dot line midway. Centre marks follow their hole when the design changes, and go when the hole goes |
| Dimension (D) | Same rules: a straight edge gives its length (horizontal, vertical, or aligned when slanted), a circle its diameter (with the diameter sign), an arc its radius (R), two parallel edges their distance, two edges at an angle the angle, points or circle centres the distance between them (horizontal / vertical / aligned from where the mouse is). The dimension follows the mouse until a click places it; each placed dimension is one undo step; the command stays for the next one; Esc drops an unplaced one, Esc again ends. Linear, Aligned, Angular, Radius and Diameter Dimension force their kind. An isometric view is refused ("An isometric view cannot be dimensioned: its lengths are drawn shorter...") |
| Text | Click two corners, type in the dialog's box (Enter makes a new line), OK: the note in the box's middle, 3.5 mm text |
| Title block | Filled from the design: Title and Part Number (the design's name), Material (the bodies' material), Drawn by (the user), Date, Scale, Size, Sheet 1 / 1, Units, the standard and its projection symbol. Double-click the title block (or MODIFY > Title Block): its fields to type in, live on the sheet; a typed field keeps its text, the others keep following the design (a renamed design renames the title); Cancel puts the old text back |
| Table (parts list) and balloons | TABLES > Table: the table follows the mouse (an outline), a click places its top left corner; rows Item, Qty, Part Number (the component's name), Description, Material, one row per component (same names counted in Qty); in the lower half of the sheet the header is at the bottom; a balloon per row is put on the view, outside it, pointing at an edge of that component. A second Table is refused ("This drawing already has a parts list."). The rows follow renamed components, and in a Full Assembly drawing a component added to the design later comes into the views and the parts list (its balloon is added with Balloon) |
| Balloon | Click an edge of a component on a view, then where the balloon goes: its number is the component's item; the next component, Enter / Esc ends; all balloons of one command are one undo step. Without a parts list it is refused ("make the parts list first (TABLES > Table)"); a click on empty paper says to click a component's edge |
| Delete | Select views, dimensions, notes, balloons or the parts list on the sheet and press Del (or MODIFY > Delete): a view takes its dimensions, balloons, sections, details and projected views with it, one undo step |
| Export PDF | EXPORT > Export PDF: Name (the drawing's), Location (the design's folder, or Documents), *Open the PDF afterwards* (ticked); Export writes the sheet as a vector PDF of the sheet size (white paper, hatching, text) and opens it. An empty name or no folder is said in the dialog, which stays |
| Export DXF | EXPORT > Export DXF: the same dialog (*Open afterwards* not ticked). The DXF (R12, the sheet in millimetres, dimension values as written on the sheet) has layers SHEET (frame, title block), VISIBLE, HIDDEN, CENTER (centre marks, centre lines, section lines), HATCH, DIMENSIONS (lines, arrows, values as on the sheet), TEXT (notes, captions, balloons) and TABLE (the parts list) |
| The drawing follows the design | Immediately: the views, dimensions (their values), centre marks, title block and parts list update when the design changes (an edit in the timeline, Undo in the design), also after the design was saved and opened again |
| Undo / redo | Every command is one undo step on the design's undo list (Ctrl+Z / Ctrl+Y on the sheet or the quick-access buttons) |
| Drawings are files of their own | Drawings are saved inside the design's file and listed in the browser's **Drawings** folder: double-click (or right-click > Open Drawing) opens one, Rename, Delete (one undo step; its tab closes). Opening a drawing does not mark the design as changed |

## Known gaps (never faked)

| Fusion | Why not (yet) |
|---|---|
| A drawing is a separate document (.f2d) linked to a design version, with an out-of-date badge and Update | SciForge keeps drawings inside the design's file (FreeCAD's TechDraw pages live in the document of the parts they show), so a drawing is always up to date. There is no separate drawing file to share; export PDF / DXF for that |
| Several sheets per drawing, the Sheet Bar, Destination "an existing drawing" | One sheet per drawing (a TechDraw page is one sheet); make another drawing for another sheet |
| Templates (Browse, Template contextual environment, custom title blocks, Add Title Block) | Only SciForge's own title block or a blank frame; editing the template's layout is not built |
| Shaded and Shaded with Hidden Edges styles | TechDraw cannot render shading: the faces are filled with one light colour |
| Tangent Edges "Shortened" | TechDraw shows tangent edges full length or not at all |
| Section Depth (Full / Slice / Distance), cut lines with several segments (offset, aligned, half sections), Breakout Section View, Exploded View | Not built: TechDraw has complex sections (`DrawComplexSection`) that could carry several segments; breakout sections and exploded views (Fusion's animation storyboards) have no TechDraw counterpart |
| A section through a hole shows the hole's seam as a line across it | TechDraw's own section cut classifies the cylinder's seam as a hard edge (its SeamVisible and SmoothVisible settings do not remove it); a fix belongs in TechDraw's DrawViewSection (FreeCAD core) |
| Detail boundary options (jagged / smooth, full boundary, connection line) | TechDraw draws a circle on the parent and the detail without a boundary |
| Break line styles; several breaks in one view; a break of a section view | One break per broken view, TechDraw's break lines |
| Center Mark Pattern, automatic centre marks and centre lines for all holes, Edge Extension | Not built (greyed in the ribbon) |
| Ordinate, Baseline and Chain dimensions; dimension text editing (tolerances, prefixes, overrides); arranging dimensions | Not built (greyed); the diameter sign and R prefix follow ISO for both standards |
| Leader, Note, Surface Texture, Feature Control Frame, Datum Identifier | Not built (greyed in the ribbon) |
| Renumber and Align Balloons; patent balloons; sub-assembly structure in the parts list; column choice and order | Not built: the parts list lists the components the view shows, first level only, with fixed columns |
| Export PDF of several sheets, uniform line weights; Export DWG; Export CSV of the parts list | One sheet per drawing; no DWG writer in FreeCAD's Python API; CSV not built |
| Rotate a view; Move with snapping | Views move by dragging their frame (TechDraw), no rotation command |
| Title block attributes Mass, Project Folder, custom attributes | Not filled: the title block has fixed fields |

## FreeCAD / TechDraw facts this relies on

- TechDraw computes the hidden-line views in a thread in the GUI: a view's edges appear a
  moment after a recompute (scenarios wait for them).
- `DrawPage.addView` centres a new view on the sheet; SciForge sets the position after
  adding it. Projection groups (`DrawProjGroup`) left their items unparented and at (0, 0)
  and could crash; SciForge makes independent views and keeps them lined up itself.
- A section's `Direction` must equal its `SectionNormal`, and both must be set before the
  section is added to the page, or the cut fails ("failed to create section CS"); its
  `SectionOrigin` is the cut line's middle in the model.
- A view's label shows only when hovered: SciForge writes the label as the view's
  `Caption` (also printed in the PDF).
- FreeCAD's default hatch colour is green with no opacity (0x00FF0000): section hatching
  never showed. SciForge sets the hatch colours of every section; the light theme's grey
  sheet colour (`TechDraw/Colors/PageColor`, `FaceColor`) is set to white while SciForge
  is on (theme.py), also for the PDF.
- A broken view's break objects must be sketches (edges raised "TopoDS::Edge" errors).
- TechDraw formats dimensions in FreeCAD's current units only; an inch drawing in a mm
  session writes its dimension text itself (`Arbitrary`), and back.
- TechDraw shows a page's tab by setting the page's Visibility, which marks the document
  as changed; SciForge clears that mark when the design was saved.
- PySide ties items added to a scene to the Python wrapper of that scene: the preview
  outlines are added through one kept wrapper and marked, or they cannot be removed.
- FreeCAD's tree brings the tab of a selected object to the front ("Sync view"): the
  browser does not put drawings in FreeCAD's selection.
- When the widget with the keyboard is hidden (a timeline step rebuilt), Qt gives the
  keyboard to the next widget that takes Tab, and a drawing's tab that took it came to the
  front: the parts of a drawing's tab take the keyboard on click only.
- A view's cosmetic lines are drawn from its last recompute: a moved centre mark needs a
  recompute of its view.

## Tests

- Scenarios (real clicks, keys and menus on the sheet; any Report-view error fails them):
  `drawing_new.py` (empty design refused, the dialog, the drawing's tab and ribbon, the
  title block, Base View by click, undo / redo, Esc, back to the design, the browser's
  Drawings folder), `drawing_views.py` (projected views in first angle, undo, dragging the
  base view, its dialog and Cancel, an ASME Automatic drawing), `drawing_section.py`
  (section through the hole, label, undo, Esc, hatching off), `drawing_detail.py` (detail
  of a fillet, label, Esc, Break View, Del), `drawing_dimensions.py` (every kind from the
  one command, undo, forced Diameter, Esc, isometric refused), `drawing_annotations.py`
  (centre mark, refusals, undo, centre line, text, title block typed / Cancel, Del),
  `drawing_export.py` (PDF read back and rendered: white paper, hatching, the caption; DXF
  read back: the hole, the dimension, centre mark, hatching, texts; empty name refused; an
  inch ASME drawing), `drawing_update.py` (fillet edited in the timeline, Undo in the
  design, the hole moved: views, dimensions, centre mark follow), `drawing_reopen.py`
  (Ctrl+S on the sheet, close, open, everything back, undo / redo after reopening, still
  following the design), `drawing_assembly.py` (Contents Select, Full Assembly, parts list
  and automatic balloons, Balloon command, refusals, a renamed component, deleting a
  drawing from the browser and Undo).
- Unit tests `SciForgeTests/unit/test_drawing_core.py` (sheets and scales, the title block
  template, projected and section maths, dimension inference and formats, parts-list rows
  and table, balloon spots, hatch lines, the DXF writer).
