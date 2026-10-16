# Parity spec: Drawings (outline 7.16)

Fusion's DRAWING workspace: a 2D drawing made from a design, with views placed by clicks,
section and detail views, centre marks, dimensions, notes, a title block filled from the
design, a parts list with balloons for assemblies, and PDF / DXF export; the drawing
follows the design when the design changes. SciForge builds it on FreeCAD's TechDraw
(`DrawPage`, `DrawSVGTemplate`, `DrawViewPart`, `DrawViewSection`, `DrawViewDetail`,
`DrawBrokenView`, `DrawViewDimension`, `DrawViewBalloon`, `DrawViewAnnotation`,
`DrawViewSymbol`, cosmetic lines and centre lines) with its own Fusion-style commands.

Implemented in `src/Mod/SciForge/sciforge/`: `drawing_core.py` (no FreeCAD, no Qt: sheets,
scales, the title block template, projection and section maths, section types, dimension
inference, parts-list rows and table, hatch lines, a DXF writer; unit tests
`SciForgeTests/unit/test_drawing_core.py`), `drawing_fits.py` (ISO 286 limits and fits;
`test_drawing_fits.py`), `drawing_dims_core.py` (a dimension's text: override, text
before / after, precision, tolerances, fits, basic, reference; `test_drawing_dims_core.py`),
`drawing_annot_core.py` (leaders, feature control frames, datum identifiers, surface
texture, ordinates, arc lengths as shapes, their SVG and DXF; `test_drawing_annot_core.py`),
`drawing_pdf.py` (one PDF from the sheets' PDFs; tested there too), `drawing.py` (the
TechDraw objects, no GUI), `drawing_annot.py` (dimension settings and annotations that
follow their edges), `drawing_sheets.py` (several sheets per drawing, export of all
sheets), `drawing_depth.py` (Section Depth, and no seam line across a cut hole: the
section's lines that lie deeper, or only on a hole's seam, switched off),
`drawing_breakout.py` (Breakout Section View: the trimmed copy a view draws, its floor's
hatching), `drawing_breakout_ui.py` (its command and dialog), `drawing_ui.py` (the drawing's tab, the mouse on the sheet, the view dialogs and
22 commands), `drawing_annot_ui.py` (the Dimension dialog and 10 commands: Ordinate,
Baseline, Chain, Arc Length, Edit Dimension, Leader, Feature Control Frame, Datum
Identifier, Surface Texture, Edge Extension), `drawing_sheets_ui.py` (the sheet bar; New
Sheet, Delete Sheet), the contextual DRAWING tab in `ribbon_config.py` / `ribbon_ui.py`,
the Drawings folder of the browser (`browser_core.py`, `browser_ui.py`), icons `dw_*`
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

### Part 2 (researched 2026-10-14: annotations, sheets, more views)

| # | Fusion behaviour | Source |
|---|---|---|
| 26 | Double-click a dimension: the Dimension dialog opens (its value becomes editable); what is set there overrides the Document Settings for that dimension | Autodesk: "Dimension reference (Drawing workspace)" (DWG-REF-DIMENSION-DLG); Forum: "Overriding Drawing Dimensions" |
| 27 | Tolerance types Symmetrical, Deviation, Limit and Fit; Symmetrical takes one value, Deviation and Limit an upper and a lower one | Autodesk: DWG-REF-DIMENSION-DLG, "Edit tolerance" (DWG-EDIT-TOLERANCE), support article "Adding tolerances to dimension in the Fusion drawing environment" |
| 28 | Fit: choose the basis (Hole / Shaft), the fit type, a preferred fit class or Custom, and see the resulting limits | Autodesk: DWG-REF-DIMENSION-DLG ("Hole/Shaft sets which feature is the base for the fit") |
| 29 | Fit classes follow ISO 286 (H7/g6 ...); the preferred fits by type: clearance, transition, interference | ISO 286-1/-2 (the tables); Autodesk: support article (H6, H7 fits) |
| 30 | Linear precision is picked from a list (0, 0.1, 0.12, ...) | Autodesk: DWG-REF-DIMENSION-DLG, "How to change the dimension precision" |
| 31 | Text can be written before / after a dimension's value and symbols inserted (diameter, square, degree...) | Forum: "multiple lines of text can be added to any dimension"; Guess (symbol list from ISO 129 / ASME Y14.5) |
| 32 | A basic dimension is boxed and has no tolerance; a reference dimension is in parentheses | ASME Y14.5 / ISO 129 practice; Forum: reference dimensions take no tolerance |
| 33 | Ordinate Dimension: place the origin (0,0) on a view (an edge, a corner), then each point and where its value goes; the values are associated with the geometry | Autodesk: "How to set ordinate dimension from model origin"; Forum: "ordinate dimensioning", "placing origin for ordinates at a corner that has been filleted" |
| 34 | Baseline Dimension: pick an existing linear dimension's extension line, then further points: each measured from the same base; Chain: each from the end of the one before | Autodesk: "Create chain dimensions", Learn "Create baseline and chain dimensions in Fusion drawings" |
| 35 | Leader: click an edge for the arrow, click for the leader line, type the text in the text box; double-click edits it | Autodesk: "Create and modify leader notes (Drawing workspace)" |
| 36 | SYMBOLS: Surface Texture, Feature Control Frame and Datum Identifier attach to model edges (and to dimensions); a datum identifier: pick the edge, a start point, the next point; its letter is edited in the dialog | Autodesk: "Geometric tolerancing symbols" (DWG-SYMBOLS), DRAWINGS-DATUM-IDENTIFIER-CMD |
| 37 | A feature control frame: geometric characteristic, tolerance (diameter zone, material condition), up to three datum references, a composite second row | Guess from ASME Y14.5 / ISO 1101 (Fusion's FCF help page was not found) |
| 38 | Surface texture: basic / material removal required / prohibited; ASME writes the values above the tick, ISO below the line | Forum: Fusion product manager on surface texture (ASME / ISO); ISO 1302 |
| 39 | Several sheets per drawing in the Sheet Bar: + adds a sheet with the active sheet's properties; right-click a thumbnail: Add Sheet, Rename Sheet, Delete Sheet; drag to reorder | Autodesk: "Drawing sheets" (GUID-F08CCC38), DWG-ADD-SHEET; Learn "Creating Multiple Sheets" |
| 40 | The title block's sheet number and count follow the Sheet Bar's order ("1/3") | Autodesk: "Drawing sheets"; third-party title block guide (SHEET attribute) |
| 41 | Export PDF: All Sheets (or the selected ones) always in one PDF | Autodesk: DWG-EXPORT-PDF |
| 42 | Section View: click more points to bend the cut line; the type follows: Full, Half (two segments at a right angle), Offset (jogged), Aligned (angled) | Autodesk: DWG-CREATE-SECTION-VIEW; Forum: "Section Views acting odd" (half / aligned) |
| 43 | Section Depth: Full (everything), Slice (only what the line cuts), Distance (up to a distance behind the line) | Autodesk: Drawing View dialog (DWG-CREATE-SECTION-VIEW) |
| 44 | Drawing View dialog: Automated Center Marks and Center Lines for Holes, Round Extrudes, Round Cuts | Autodesk: "Create a base view placeholder", Learn "create center marks and center lines" |
| 45 | Edge Extension (GEOMETRY): two edges extended to their intersection, which takes dimensions (a filleted corner) | Forum: "drawings - placing origin for ordinates at a corner that has been filleted" |
| 46 | Text box placed by clicking two corners or dragging | Autodesk: DWG-CREATE-TEXT; Guess for the drag |
| 47 | A view's label can be edited and shown or hidden | Autodesk: Drawing View dialog; Guess for the default (section / detail shown, others hidden) |
| 48 | **Breakout Section View** (CREATE): on a drawing view, a closed profile; Fusion cuts away what lies inside it from the front, by default half the design's depth, any depth typed; a button goes back to the default depth; one breakout per view | Autodesk: "Create breakout section views" (DWG-CREATE-BREAKOUT-SECTION-VIEW), "Breakout Section View dialog" (DWG-REF-BREAKOUT-SECTION-VIEW-DLG), "Breakout section views" (DWG-BREAKOUT-SECTION-VIEW); VDCI tutorial "Cutaway Section View with Breakout Tool" |
| 49 | Isometric views made from a view with a breakout show its cut | Autodesk: DWG-BREAKOUT-SECTION-VIEW |
| 50 | A breakout is edited later (its depth) or removed | Autodesk: "Edit breakout sections" (DWG-EDIT-BREAKOUT-SECTION-VIEW); Guess for opening it by a double-click inside the profile |

## What the user does (and what SciForge does)

| Fusion | SciForge |
|---|---|
| File > New Drawing > From Design; Workspace > Drawing > From Design | Same: the application menu's **New Drawing**, and the workspace button **DESIGN > Drawing > From Design...** (that menu also lists the design's drawings). An empty design is refused: "There is nothing to draw yet: the design has no solid bodies..." |
| Create Drawing: Contents, Template, Standard, Units, Sheet Size, Automatic / Manual | Same: Contents Full Assembly / Visible Only / Select (Select shows the bodies, "Component / Body", to tick); Template *SciForge title block* or *Blank sheet (frame only)*; Standard ISO / ASME (ISO for an mm design, ASME for an inch one); Units mm / in; Sheet Size ISO A4..A0 (A3) or ASME A..E (B); Views Manual or Automatic (base view, two projected views and an isometric one at an automatic scale, one undo step) |
| The drawing opens in its own tab | Same: a tab "<design> Drawing" ("... Drawing 2" for the next). While it is the active tab the ribbon shows only the **DRAWING** tab, the workspace button says DRAWING, the timeline and the navigation bar step aside; another tab brings the design's ribbon back |
| Base View: the view follows the mouse, a click places it; Orientation, Style, Scale, Tangent Edges; OK | Same: Orientation Front / Back / Top / Bottom / Left / Right / Home; the four styles (Shaded is drawn as faces filled with one light colour, see gaps); Scale from the list (50:1 .. 1:200) or typed (1:2.5, 1/4, 0.5); Tangent Edges Full Length / Off. The changes show live; Esc / Cancel leaves nothing. The title block's Scale follows the base view |
| Projected View | Same: the only base view is the parent (else click one); moving round it shows the view that will be made (first angle: the view from above goes below; third angle: above), the four corners give isometric views; a click places each; back over the parent the preview goes; Enter / Esc ends; the projected views are one undo step. They take the parent's style and scale, and stay lined up when the parent is dragged or turned |
| Double-click a view | Its dialog: Base View (orientation, style, scale, tangent edges; the projected views turn with it), Section, Detail, or Edit View (style; a broken view's gap). Cancel puts everything back. Views are moved by dragging their frame |
| Section View | Click the view, then the cut line's points (each within 3 degrees of horizontal or vertical is straightened); more than two bend the line; Enter (or a click on the last point again) ends it, and so does moving well away from the view (more than 12 mm past it); move to the side to look from and click to place: **SECTION A-A** under the view, the cut line with arrows and letters on the parent, the cut faces hatched at 45 degrees, lined up with the parent. The dialog shows the Type found from the line (Full; Half: two segments at a right angle; Offset: jogged; Aligned: another angle; TechDraw's complex section cuts along the bent line) and has Label (B-B...), Scale, Style (hidden edges), Section Depth (Full / Slice / Distance with its mm), Hatch on / off, Show the view label, Center marks. Letters skip I, O, Q, S, X, Z. Depth on a bent line is refused ("works with a straight cut line"). Slice and Distance switch off the section's lines that lie deeper (the cut faces stay TechDraw's own); a hole cut in half shows no line along its middle |
| Breakout Section View | CREATE > Breakout Section View: click a base or projected view (an isometric one, a section, a detail or a view with a breakout already is refused with a message); the Depth box offers half the parts' depth; click the corners of a boundary around what should show (a preview follows the mouse) and the first corner again (or Enter): the cut is made, what lies inside shows in the view, the floor of the cut is hatched; type another depth (or press Default) and see it change; OK (one undo step), Esc / Cancel leaves nothing. The view's dimensions and annotations stay; an isometric view projected from it shows the cut too, other projected views the whole parts. Double-click inside the boundary later: Edit Breakout (depth, **Remove Breakout**). It follows the design and is saved with it |
| Detail View | Click the view, the centre (it snaps to a fillet's or hole's centre), the circle's size, then place the view: **DETAIL A (2:1)** at twice the parent's scale, a circle and letter on the parent. Label and Scale in the dialog |
| Break View | Click the view, then the two ends of the part to leave out: the broken view stands in for the view (the original is hidden), the break follows the direction of the two clicks; Gap (10 mm) in the dialog and in Edit View. Selecting the broken view and Del brings the original view back |
| Center Mark, Centerline | Center Mark: click circles or arcs; two dash-dot lines cross at the centre, 3 mm past the circle; a hole that has one is said; a straight edge is refused ("click a circle"); Enter / Esc ends. Centerline: click two parallel edges: a dash-dot line midway. Centre marks follow their hole when the design changes, and go when the hole goes |
| Dimension (D) | Same rules: a straight edge gives its length (horizontal, vertical, or aligned when slanted), a circle its diameter (with the diameter sign), an arc its radius (R), two parallel edges their distance, two edges at an angle the angle, points or circle centres the distance between them (horizontal / vertical / aligned from where the mouse is). The dimension follows the mouse until a click places it; each placed dimension is one undo step; the command stays for the next one; Esc drops an unplaced one, Esc again ends. Linear, Aligned, Angular, Radius and Diameter Dimension force their kind. An isometric view is refused ("An isometric view cannot be dimensioned: its lengths are drawn shorter...") |
| Text | Click two corners or drag the box open, type in the dialog's box (Enter makes a new line), OK: the note in the box's middle, 3.5 mm text |
| Double-click a dimension: the Dimension dialog | Measured value; Text before, Override value, Text after, with symbol buttons (diameter, R, square, degree, plus/minus, arc, depth, counterbore, countersink) typing into the field used last; Precision (Default, 0 ... 0.1234); Tolerance None / Symmetric / Deviation / Limits / Fit with Upper and Lower; for Fit: Basis (Hole / Shaft), Fit type, Fit (the ISO preferred fits of that basis and type, or Custom with typed hole and shaft classes), "This dimension is the" Hole / Shaft, Display (Class: "10 H7"; Class and tolerances: +0.015 over 0 beside it; Limits: 10.015 over 10.000; Fit: "10 H7/g6") and the fit's limits and clearance written in the dialog; Tolerance precision; Basic (boxed, no tolerance); Reference (in parentheses). Live on the sheet; a wrong entry (an upper below the lower, a class SciForge does not know, a size over 500 mm for a fit) is said in the dialog and OK waits; Cancel / Esc puts it back; one undo step. Also DIMENSIONS > Edit Dimension on a selected dimension |
| Ordinate Dimension | Click the origin (a corner, an edge's end or a circle's centre), then a point, then where its value goes: up or down measures across (x, the value along the leader in ISO, level in ASME), sideways measures up (y); the origin gets its 0 on that axis; the next values snap onto the first one's line when near it; each placing is one undo step; Esc drops a picked point, Esc again ends. The values follow the design |
| Baseline / Chain Dimension | Click an existing horizontal or vertical dimension near the end to start from, then more points (corners, circle centres, edge ends): Baseline makes each from that end, stacked 8 mm further out; Chain each from the point before, on the first one's line. Real TechDraw dimensions (they follow the design and take the Dimension dialog) |
| Arc Length Dimension | Click an arc, then the place: extension lines, a dimension arc with arrows and the length with the arc sign; a whole circle is refused (it takes a diameter) |
| Leader | Click an edge (the arrow goes on it), then where the text goes (a landing towards it), type the text; double-click edits it; drag its text to move it (the arrow stays) |
| Feature Control Frame | Characteristic (the 14 of ISO 1101), tolerance with a round zone and a material condition (M / L), primary / secondary / tertiary datums with modifiers, Composite (a second row sharing the symbol cell); click an edge for the leader, or empty paper for a frame alone, then the place; double-click edits it. The symbols are drawn from lines and circles (no font needed) |
| Datum Identifier | The next free letter by default (A, B...); click the edge (a filled triangle stands on it), then where the box goes |
| Surface Texture | Symbol (basic, material removal required, prohibited), roughness ("Ra 3.2"), lay, All around; click the edge, then the place: on the edge (a click next to where it was picked) or away with a leader; ISO writes the value under the long leg's line, ASME above |
| Edge Extension | GEOMETRY > Edge Extension: click two straight edges; thin lines run from their ends to where they meet and a point there takes dimensions (a rounded corner's sharp corner); it follows the edges when the design changes |
| Drawing View dialog extras | Every view's dialog (base, projected, section, detail, broken) has Center marks: Holes, Round Extrudes, Round Cuts (centre marks where those rounds are seen end on, centre lines where seen from the side, 3 mm past them, following the design) and the view label (base and projected views: its text and Show; section and detail views: Show). Section and detail dialogs have Style, so hidden edges can be shown per view |
| Several sheets | Every drawing's tab has a sheet bar along its bottom: one tab per sheet and a +. + adds an empty sheet (same size, standard and title block) and shows it; clicking a tab shows that sheet in the drawing's one tab; right-click a tab: New Sheet (after it), Rename Sheet (its name becomes a box: Enter keeps, Esc not; also by double-click), Delete Sheet (the sheet and everything on it; the last sheet cannot go: "delete the whole drawing in the browser instead"), Move Left / Right; dragging a tab moves the sheet. Each is one undo step. The title blocks number the sheets "2 / 3" in the bar's order; fields typed into a title block show on every sheet; each sheet's scale is its own. Deleting the first sheet keeps the drawing (its name passes to the next sheet). The browser lists the drawing once; deleting it there deletes all its sheets |
| Title block | Filled from the design: Title and Part Number (the design's name), Material (the bodies' material), Drawn by (the user), Date, Scale, Size, Sheet (1 / 1, its place among the drawing's sheets), Units, the standard and its projection symbol. Double-click the title block (or MODIFY > Title Block): its fields to type in, live on the sheet; a typed field keeps its text, the others keep following the design (a renamed design renames the title); Cancel puts the old text back |
| Table (parts list) and balloons | TABLES > Table: the table follows the mouse (an outline), a click places its top left corner; rows Item, Qty, Part Number (the component's name), Description, Material, one row per component (same names counted in Qty); in the lower half of the sheet the header is at the bottom; a balloon per row is put on the view, outside it, pointing at an edge of that component. A second Table is refused ("This drawing already has a parts list."). The rows follow renamed components, and in a Full Assembly drawing a component added to the design later comes into the views and the parts list (its balloon is added with Balloon) |
| Balloon | Click an edge of a component on a view, then where the balloon goes: its number is the component's item; the next component, Enter / Esc ends; all balloons of one command are one undo step. Without a parts list it is refused ("make the parts list first (TABLES > Table)"); a click on empty paper says to click a component's edge |
| Delete | Select views, dimensions, notes, balloons or the parts list on the sheet and press Del (or MODIFY > Delete): a view takes its dimensions, balloons, sections, details and projected views with it, one undo step |
| Export PDF | EXPORT > Export PDF: Name (the drawing's), Sheets (All Sheets / Current Sheet), Location (the design's folder, or Documents), *Open the PDF afterwards* (ticked); Export writes the sheets as one vector PDF, each page its sheet's size (white paper, hatching, text), and opens it. An empty name or no folder is said in the dialog, which stays |
| Export DXF | EXPORT > Export DXF: the same dialog (*Open afterwards* not ticked); All Sheets writes one DXF per sheet named after it ("name - Sheet 1.dxf"). The DXF (R12, the sheet in millimetres, dimension values as written on the sheet, tolerances on one line) has layers SHEET (frame, title block), VISIBLE, HIDDEN, CENTER (centre marks, automated ones, centre lines, section lines with their bends), HATCH, DIMENSIONS (lines, arrows, values as on the sheet, ordinates, arc lengths), TEXT (notes, captions, balloons, leaders), SYMBOLS (feature control frames, datums, surface texture) and TABLE (the parts list) |
| The drawing follows the design | Immediately: the views, dimensions (their values), centre marks, title block and parts list update when the design changes (an edit in the timeline, Undo in the design), also after the design was saved and opened again |
| Undo / redo | Every command is one undo step on the design's undo list (Ctrl+Z / Ctrl+Y on the sheet or the quick-access buttons) |
| Drawings are files of their own | Drawings are saved inside the design's file and listed in the browser's **Drawings** folder: double-click (or right-click > Open Drawing) opens one, Rename, Delete (one undo step; its tab closes). Opening a drawing does not mark the design as changed |

## Known gaps (never faked)

| Fusion | Why not (yet) |
|---|---|
| A drawing is a separate document (.f2d) linked to a design version, with an out-of-date badge and Update | SciForge keeps drawings inside the design's file (FreeCAD's TechDraw pages live in the document of the parts they show), so a drawing is always up to date. There is no separate drawing file to share; export PDF / DXF for that |
| The Sheet Bar's thumbnails, Destination "an existing drawing", sheets of different sizes | The sheet bar shows names, not pictures; a new sheet takes the active sheet's size and title block (change of size per sheet not built); a new drawing is always a new drawing |
| Templates (Browse, Template contextual environment, custom title blocks, Add Title Block) | Only SciForge's own title block or a blank frame; editing the template's layout is not built |
| Shaded and Shaded with Hidden Edges styles | TechDraw cannot render shading: the faces are filled with one light colour |
| Tangent Edges "Shortened" | TechDraw shows tangent edges full length or not at all |
| Exploded View | Exploded views come from Fusion's animation storyboards, which SciForge does not have |
| Breakout: a sketched spline profile picked in the dialog; components left out of the cut; "move the start point to the front" | The boundary is a polygon of clicked points (no spline), where it cuts material TechDraw draws ordinary lines (Fusion: a thin break line); every part is cut; the depth is measured from the front of the parts when the breakout is made and again after every change (so the start-point button is not needed). A section or detail view made from a view with a breakout shows the breakout too (TechDraw cuts and enlarges what the parent view draws); a break view of a view with a breakout shows the whole parts |
| Section Depth on a bent cut line; a bend's seam line; Distance cutting a line in two | Depth works on straight lines only (refused with a message on bent ones), and so does the hiding of a cut hole's seam line; TechDraw's complex section draws a thin line where the offset line jogs (Fusion draws none). TechDraw can only switch a whole line off: a line that is partly within the Distance shows whole. After a design change a big section's deeper lines are switched off once TechDraw has drawn it (SciForge looks again 1.5, 3, 6 and 12 s later) |
| Detail boundary options (jagged / smooth, full boundary, connection line) | TechDraw draws a circle on the parent and the detail without a boundary |
| Break line styles; several breaks in one view; a break of a section view | One break per broken view, TechDraw's break lines |
| Center Mark Pattern; telling a Hole feature from a Round Cut | Not built (greyed); Holes and Round Cuts both mark every inner round (SciForge cannot tell which feature made a cylinder) |
| Arranging dimensions (Arrange, spacing); Hole and Thread notes | Not built; Baseline stacks 8 mm apart |
| Feature control frames and surface texture attached to a dimension; frames without a leader dragged under a dimension stay "associated" | They attach to edges (or stand alone on the paper) |
| Note (TEXT group), Weld symbol | Not built (greyed); Weld was optional in the brief |
| Leader with several segments; text styles (fonts, bold, lists, justification) in notes | One straight leader line with a landing; plain text |
| Tolerance on angles shown stacked | Angles take Symmetric / Deviation / Limits; Fit is refused for angles (there is no ISO fit for an angle) |
| Ordinate dimensions with separate X and Y origins, jogged ordinate leaders, an origin on an edge's middle | One origin point per set; straight leaders |
| Renumber and Align Balloons; patent balloons; sub-assembly structure in the parts list; column choice and order | Not built: the parts list lists the components the view shows, first level only, with fixed columns |
| Export DWG; Export CSV of the parts list; uniform line weights in the PDF | No DWG writer in FreeCAD's Python API; CSV not built |
| Rotate a view; Move with snapping | Views move by dragging their frame (TechDraw), no rotation command |
| Title block attributes Mass, Project Folder, custom attributes | Not filled: the title block has fixed fields |

## FreeCAD / TechDraw facts this relies on

- **A Python event filter on a TechDraw view must go before the view is deleted** (crash
  found by Luca, 2026-10-16: closing a drawing closed the whole program). Closing a
  drawing's tab deletes `MDIViewPage` and its `QGVPage`; `~QWidget` sends one last event
  through the widget's own event filters, and PySide wrapping the half-deleted widget for
  SciForge's `PageInput.eventFilter` segfaults (`QObject::property` in
  `PySide::getWrapperForQObject`). Nothing in the Python filter can guard it: it never
  runs. `PageInput` now watches the tab's `QMdiSubWindow` for its Close event (x, Window >
  Close) and a Gui document observer for `slotDeletedDocument` (closing the design deletes
  its tabs without a Close event), and takes its filters off first. Scenario
  `drawing_close` (x with the Base View dialog open, x after a view, Window > Close, the
  design closed with the drawing current).

Part 2 (2026-10-14):

- `DrawView.findParentPage()` crashes FreeCAD (a segfault in TechDraw) for a view that
  is on no page yet: `drawing.page_of` uses the InList only.
- `DrawViewDimension.getLinearPoints()` returns its points scaled, from the view's
  centre, with y down (the DXF's dimension lines were mirrored before).
- A dimension's tolerance texts show only with `EqualTolerance = False`; with
  `ArbitraryTolerances` the two `FormatSpecOver/UnderTolerance` strings are written as
  they are, stacked beside the value at `TolSizeAdjust` (TechDraw/Dimensions, 0.5 by
  default; SciForge sets 0.7 while it is on). A two-line `FormatSpec` (Arbitrary) shows
  limits stacked; `TheoreticalExact` draws the basic box.
- TechDraw files a "Drag Dimension" undo step whenever a selected dimension's value is
  laid out again (its text changed size) and then deselected: the Dimension dialog
  clears the selection before its own step, so one Undo takes back the dialog.
- A task panel's attribute must not shadow `taskui.Panel` methods (`feature`, `finish`,
  `schedule`...): an attribute `feature = None` made OK fail with "NoneType is not
  callable" and left the panel's mouse handler alive.
- `getGeometricCenter()` measures the parts with the 3D view's mesh; TechDraw centres a
  view on the exact bounding box (a copy without mesh): 0.02 mm apart on an R8 fillet.
  `drawing.centre_of` computes TechDraw's centre.
- `makeCosmeticVertex` takes y-up points (it inverts them itself); `makeCosmeticLine`
  too; `formatGeometricEdge(index, style, weight, colour, visible)` hides one edge by
  index (the sheet and the PDF respect it; `clearGeomFormats()` undoes all).
- `DrawViewSection` cuts its parent view's shape (`getShapeToCut` uses the BaseView's
  `getSourceShape()`), never its own `Source`: a section's depth cannot be given by a
  trimmed copy as its Source; SciForge switches the deeper lines off instead, matching
  them by geometry (`getEdgeByIndex(i)`: unscaled, from the section's middle, the same
  way up as `getVisibleEdges(True)`) against `TechDraw.projectEx` of the trimmed parts,
  centred where TechDraw centres a section (the box of the cut pieces in the view's
  axes), and again whenever the section's lines or the parts change.
- A boolean leaves the straight seam (or the join of two halves) of a hole's round face
  as an ordinary edge, which TechDraw's section draws as a hard line across the cut hole;
  such a line, covered by no other edge, is switched off the same way.
- `DrawViewPart.execute()` does nothing while the view's previous hidden-line removal
  still runs: a trimmed copy changed right after a recompute was missed by its view. The
  breakout's copy is a `Part::FeaturePython` linking the parts, so it is remade in the
  recompute before its view (its proxy class is found again when the file is opened).
- `TechDraw::DrawComplexSection` cuts along a sketch (CuttingToolWireObject) that lies
  square to the parent view's direction; `ProjectionStrategy` Offset for jogged / half
  sections, Aligned for angled ones; SectionNormal from the first segment.
- An SVG `DrawViewSymbol` is placed by its middle (X, Y), at its size in mm with
  ScaleType Custom and Scale 1; its texts and shapes go into the PDF as vectors.
- One PDF per page from `TechDrawGui.exportPageAsPdf`; TechDraw's "print all" writes
  every page of the document (all drawings), so SciForge merges the sheets' PDFs itself
  (`drawing_pdf.py`: Qt's PDFs have a plain cross-reference table).
- FreeCAD's MDI view is a QMainWindow: the sheet bar is a toolbar at its bottom. FreeCAD
  makes the MDI tabs movable (`setTabsMovable(True)`), so a new sheet's tab can take the
  old sheet's place.
- A page removed by Undo while its tab shows leaves the tab open: the tab of a page that
  is gone is closed after the deletion (`drawing_sheets_ui.close_orphans`).

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

Part 2 scenarios (real clicks; any Report-view error fails them): `drawing2_tolerance`
(the Dimension dialog: fit H7 with tolerances, as limits, undo / redo, symmetric,
Cancel, deviation, a wrong pair refused, text before / after and a symbol button,
precision, basic, reference, a custom fit H8/f7, an unknown class refused, Esc, the
DXF), `drawing2_ordinate` (ordinates from a corner on both axes, lined up, Esc, undo /
redo, baseline, chain, arc length and its refusal, following the design),
`drawing2_symbols` (leader and its refusal, feature control frame with two datums, a
non-number refused, two datums with their default letters, surface texture on an edge,
editing the frame into a composite one, undo / redo, the view dragged: everything goes
with it, the DXF), `drawing2_sheets` (the sheet bar, +, a base view and a section on
sheet 2, switching, rename in place, move with undo / redo, PDF of all sheets (2 pages)
and of the current one, a DXF per sheet, delete with undo / redo, deleting the first
sheet, the last one refused), `drawing2_sections` (offset section through two holes,
undo / redo, half section, Esc, Slice and Distance depth switching off the deeper lines,
hidden edges, the view label, depth refused on a bent line, an aligned section, no seam
line across a hole cut in half), `drawing2_breakout` (Esc, a breakout with a clicked
boundary and a typed depth: the hole inside shows, the floor hatched; undo / redo; a
second one refused; its dialog by double-click: a depth through the part, Default, undo;
following the design; an isometric view inherits it; the DXF; Remove and undo; save and
reopen; deleting the view takes the copy), `drawing2_views` (automated centre marks and centre
lines, undo / redo, hidden edges per view, edge extension and a dimension to its point,
the view label with undo, a text box dragged open, following the design),
`drawing2_update` (fillet edited in the timeline, a hole moved and resized, Undo in the
design: tolerances, ordinates, leaders, frames, marks, extensions, sections follow),
`drawing2_reopen` (save, close, open: everything back, the dialog edits and undoes,
still following the design). Unit tests: `test_drawing_fits.py`,
`test_drawing_dims_core.py`, `test_drawing_annot_core.py` (with the PDF merge),
`test_drawing_core.py` (section types).

Part 1:

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
