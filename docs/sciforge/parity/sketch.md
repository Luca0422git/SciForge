# Parity spec: the SKETCH workspace (outline 7.5)

Source: Fusion's documented behaviour and everyday use. Not yet checked against Luca's own
screen captures (outline 2.4). Implemented in `src/Mod/SciForge/sciforge/sketch_*.py` on top of
FreeCAD 1.1.4's Sketcher. Status: **first pass + QA pass, not yet signed off**.

## What the user does (and what SciForge does)

| Fusion | SciForge |
|---|---|
| Create Sketch: the origin planes appear; click a plane or a flat face; the camera turns to look at it | Same (`sketch_ui.py`). A curved face or an edge is refused with the reason next to the mouse and does not stay selected |
| SKETCH tab; Finish Sketch (ribbon, palette, right click) always works, also with a tool running or a value being typed; the camera goes back | Same (`sketch_mode.finish_sketch`) |
| L: lines joined end to end; type the length and Enter (the pointer gives the direction), or the length, Tab, the angle, Enter; the typed length becomes a dimension; a click on the first point closes the shape and the next click starts a new chain | Same: FreeCAD's line tool (on-screen Length/Angle) joined end to end by `sketch_line.py`; one Enter after a value finishes the shape (FreeCAD alone would move to the next field) |
| R 2-point rectangle, C centre-diameter circle (type the diameter), polygons (6 sides, sides in the panel, size typed) | Same. Circumscribed polygon: the typed size is the radius of the circle it is drawn around (what the preview shows) |
| D: click a curve (or two), place, a value box opens; Enter keeps it, Esc keeps the measured value | Same (`DimensionEditor`). Refuses 0, negative sizes, text and wrong units with the reason in the box; takes expressions (`10+15*2`, `=Parameters.w`) |
| A dimension on a size that is already set: Fusion offers a driven dimension | Made a driven dimension at once (no pop-up), with a message; the sketch never ends up over-constrained |
| Double-click a dimension to change it | Same (also radius/diameter); a driven dimension says it cannot be changed |
| T trim, O offset (chain), X construction, P project, Include 3D Geometry, Mirror/patterns with nothing selected | Same (first pass). Offset keeps sharp corners |
| A constraint tool clicked with a selection that does not fit (Parallel with one line) starts and waits for picks | Same (`sketch_tools_ui._Constraint`); FreeCAD alone only noted "Wrong selection" |
| Sketch fillet: click a corner, type the radius | Same: the radius box opens on a new radius dimension |
| Esc stops the tool, a second Esc clears the selection; Esc never leaves the sketch | Same, also with the keyboard in the side panel (after a palette click) |
| E in a sketch: finishes it and starts Extrude with the profile | Same, also with a drawing tool still running |
| M moves/copies sketch curves, Del deletes sketch curves, Ctrl+C/Ctrl+X/Ctrl+V copy/cut/paste (the copy hangs on the mouse) | Same (keys handled by the sketch view while a sketch is open) |
| Right click: the marking menu with sketch tools and Finish Sketch | Same (`sketch_marking.py`): Repeat, Delete, Line, Undo, Finish Sketch, Circle, Sketch Dimension, Rectangle; list: Redo, Trim, Offset, Project, Move/Copy, Normal/Construction, Fit, Look At |
| SKETCH PALETTE: Linetype (construction), Look At, Sketch Grid, Snap, Slice, Show Profile/Points/Dimensions/Constraints/Projected Geometries | Same (`sketch_palette.py`). Linetype turns orange while new curves are construction (X with nothing selected), and every new sketch starts with normal lines. FreeCAD's constraint/element lists are hidden |
| Closed areas shaded light blue (also where curves cross) | Same (`sketch_regions.py`) |
| Ctrl+Z after Finish Sketch takes the last sketch change back with its effect on the part (one press) | Same: FreeCAD's separate "Sketch recompute" step is undone/redone together with the change before it |
| Editing a sketch features depend on; the part follows. A profile broken by the edit: the feature fails, the user is told | Same; the message next to the mouse names the feature and says to edit again or Ctrl+Z (no FreeCAD balloon) |
| No pop-ups | FreeCAD's notification balloons are off while SciForge is on (its messages stay in its list and the Report view) |

## Known gaps

| Fusion | Why not yet |
|---|---|
| Angle typed relative to the previous line | FreeCAD's angle field is measured from the X axis |
| Drag from a line's end to draw a tangent arc | FreeCAD's line tool has no arc mode (its polyline tool does, but takes no typed values) |
| Midpoint Line, 3-Point Rectangle, 2-Point/2-/3-Tangent Circle, Tangent Arc, Edge Polygon, Overall/Center Point Slot, Conic, Text, Project to Surface, 3D Sketch, Collinear/Concentric/Midpoint/Curvature constraints | Greyed in the menus (not built yet) |
| Fusion's constraint glyph look | FreeCAD's glyphs, recoloured (no red) |
