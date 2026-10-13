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
| Ending a line (Luca, 2026-10-13: "no way to end a line"): Esc exits the Line command; the green check or a double-click on the end point ends the chain and stays in the Line tool; a line that ends on existing geometry ends the chain too; Enter completes the tool; right-click: OK / Cancel (Autodesk's sketch basics course, the Create Lines help, forum answers) | Same (`sketch_end_line` scenario): Esc stops the tool; a double-click on the point the chain goes on from, or a line ending on another curve or point, ends the chain and the tool waits for a new first point (the origin and axes do not count); Enter with nothing typed completes the tool (with a value typed it still draws the shape); the right-click menu shows OK at 3 o'clock and Cancel at 9 o'clock while any tool runs: OK ends the tool and keeps what was drawn, Cancel is Esc. Not done: Fusion's floating green check near the pointer |
| R 2-point rectangle, C centre-diameter circle (type the diameter), polygons (6 sides, sides in the panel, size typed) | Same. Circumscribed polygon: the typed size is the radius of the circle it is drawn around (what the preview shows) |
| D: click a curve (or two), place, a value box opens; Enter keeps it, Esc keeps the measured value | Same (`DimensionEditor`). Refuses 0, negative sizes, text and wrong units with the reason in the box; takes expressions (`10+15*2`, `=Parameters.w`) |
| A dimension on a size that is already set: Fusion offers a driven dimension | Made a driven dimension at once (no pop-up), with a message; the sketch never ends up over-constrained |
| Double-click a dimension to change it | Same (also radius/diameter); a driven dimension says it cannot be changed |
| T trim, O offset (chain), X construction, P project, Include 3D Geometry, Mirror/patterns with nothing selected | Same (first pass). Offset keeps sharp corners |
| A constraint tool clicked with a selection that does not fit (Parallel with one line) starts and waits for picks | Same (`sketch_tools_ui._Constraint`); FreeCAD alone only noted "Wrong selection" |
| Fix/Unfix with curves selected fixes them where they are | Same: FreeCAD's Block on curves, Lock on points |
| Sketch fillet: click a corner, type the radius | Same: the radius box opens on a new radius dimension |
| Esc stops the tool, a second Esc clears the selection; Esc never leaves the sketch | Same, also with the keyboard in the side panel (after a palette click) or in FreeCAD's value field next to the pointer, right after typing a value |
| E in a sketch: finishes it and starts Extrude with the profile | Same, also with a drawing tool still running |
| M moves/copies sketch curves, Del deletes sketch curves, Ctrl+C/Ctrl+X/Ctrl+V copy/cut/paste (the copy hangs on the mouse) | Same (keys handled by the sketch view while a sketch is open) |
| A tool's key (L, C, R, D, T...) switches tools at any time, also halfway through a shape | Same, also when FreeCAD's value field has the keyboard; after a value typed into the field, letters are a unit ("12 mm") |
| Right click: the marking menu with sketch tools and Finish Sketch; OK and Cancel while a command is active | Same (`sketch_marking.py`): Repeat, Delete, Line, Undo, Finish Sketch, Circle, Sketch Dimension, Rectangle; list: Redo, Trim, Offset, Project, Move/Copy, Normal/Construction, Fit, Look At. While a tool runs, OK (3 o'clock) and Cancel (9 o'clock) replace Line and Sketch Dimension. Also after switching to another program and back (Luca saw the part menu there, 2026-10-12), and only in the open sketch's own view: another design's view gives the part menu |
| The dimension box closes when you click elsewhere, finish the sketch or start another dimension | Same; a value that cannot be set (text, or the dimension was undone while the box was open) closes the box and says why. No box is ever left over the part (Luca saw "Invalid constraint index" boxes stay, 2026-10-12) |
| Click inside a closed area of the open sketch: the profile is selected (Shift / Ctrl add, click again drops; Esc, empty space or a curve drop); E / Q extrude the selected | Same (`sketch_areas.py`, Luca R1); the area under the mouse lights up; the picked ones are a stronger blue |
| After Finish Sketch, profiles are shaded, light up and can be clicked; E / Q take them | Same, with FreeCAD's sketch areas (MakeInternals on while SciForge is on; older sketches get them when opened); the light-up and selection are FreeCAD's yellow / green |
| SKETCH PALETTE: Linetype (construction), Look At, Sketch Grid, Snap, Slice, Show Profile/Points/Dimensions/Constraints/Projected Geometries | Same (`sketch_palette.py`). Linetype turns orange while new curves are construction (X with nothing selected), and every new sketch starts with normal lines. FreeCAD's constraint/element lists are hidden |
| Closed areas shaded light blue (also where curves cross) | Same (`sketch_regions.py`) |
| Ctrl+Z after Finish Sketch takes the last sketch change back with its effect on the part (one press) | Same: FreeCAD's separate "Sketch recompute" step is undone/redone together with the change before it |
| Editing a sketch features depend on; the part follows. A profile broken by the edit: the feature fails, the user is told | Same; the message next to the mouse names the feature and says to edit again or Ctrl+Z (no FreeCAD balloon) |
| No pop-ups | FreeCAD's notification balloons are off while SciForge is on (its messages stay in its list and the Report view) |

## Inference while drawing (`sketch_infer.py`, 2026-10-12)

Built in Python on top of FreeCAD's own line tool (no C++ change, ships in a quick update).
Evidence labels as in `reports/Fusion sketching ViewCube and navigation.md`: **Autodesk**,
**Forum** (old forum posts / tutorials), **Unconfirmed** (to check in real Fusion).

| Fusion (evidence) | SciForge | Status |
|---|---|---|
| Holding Ctrl turns off all snapping and automatic constraints while drawing (Autodesk staff on the forum, tutorial) | Same, in every sketch drawing tool: the Ctrl point lands exactly where the mouse is, no coincident/on-curve/level/upright constraint for it, no grid snap. FreeCAD alone gave Ctrl the opposite job (5-degree angle steps) and still jumped to a point under the mouse | Matches |
| Ctrl only frees the point being placed; the line's start keeps what it snapped to (follows from "while picking") | Same: Ctrl on the second click keeps the start's coincident | Matches |
| Hover a point to "acquire" it; at most 3 are kept; the points of the lines drawn in the current command count automatically (Forum, about 2016) | Same: the last 3 hovered points plus every point of the lines drawn since L started (the line's own start excepted: its level/upright snap covers it) | Matches the old forum rule; **Unconfirmed** for today's Fusion (hover time, how many) |
| A dashed guide shows when the pointer lines up with an acquired point (Forum, video titles); colour blue or green, dash pattern and length unknown (Unconfirmed) | A dashed light-cyan guide (SciForge's own colour) from the acquired point to the pointer, horizontal or vertical; the point snaps onto it within 6 pixels; two guides meet at their crossing; a guide also meets a level/upright/perpendicular direction. The other coordinate keeps the grid snap | Behaviour matches; look **Unconfirmed** |
| What a click on a guide adds (Unconfirmed: no source) | A Vertical/Horizontal constraint between the two points (Fusion's H/V constraint takes two points), like Onshape. Parameter `GuideConstraint` (default on); off: the point is only placed exactly on the guide | **Unconfirmed**, an option |
| A line close to level or upright snaps and gets Horizontal/Vertical (Autodesk); tolerance not published | Within 4 degrees (FreeCAD alone: 2), parameter `HVDegrees` | Tolerance **Unconfirmed** |
| Perpendicular inferred when a new line starts from, or ends on, another line at about 90 degrees (Forum 2015) | Same, within 4 degrees (`PerpendicularDegrees`): snaps to exactly 90, a small right-angle mark at the corner while drawing, a Perpendicular constraint after the click. A line ending on another line goes to the foot of the perpendicular (on that line) | Matches; tolerance **Unconfirmed** |
| Perpendicular beat Vertical in 2015 (Forum idea post) | Level/upright wins (FreeCAD adds it); no Perpendicular on top of it (it would be redundant) | **Unconfirmed** which wins today |
| Parallel to a separate line: no source shows it | Off by default; parameter `Parallel` turns it on (to a line hovered in this command, within 3 degrees, `ParallelDegrees`) | **Unconfirmed** |
| Fusion does not infer from construction lines (Forum) | No perpendicular/parallel to construction lines (they still snap points, like FreeCAD) | Matches |
| One Ctrl+Z per drawn line | Ctrl+Z takes back SciForge's inferred constraints together with FreeCAD's automatic ones (one step, "Inferred Constraints" glued to the step before); the line itself is FreeCAD's separate step, as for every line | Close: one more press than Fusion (FreeCAD's own two steps) |
| Guides for the points of every drawing tool (Unconfirmed which tools Fusion guides) | 2026-10-13 (`sf/sketch-feel`): rectangle corners (2-point and centre), circle centre and rim point, centre-point arc centre and start, 3-point circle and arc, polygon centre and corner, slot centres. After the click the point is put exactly on the guide and a Vertical / Horizontal point-to-point constraint is added in the same glued step; a point that is no vertex of the shape (a circle's rim) is only snapped. The slot's centre line also gets level / upright / perpendicular (on the slot's side line). The curves a new constraint refers to are held still (a temporary Block) while the shape is made exact | Behaviour **Unconfirmed**; not yet: the centre-point arc's end-angle click and the slot's width click |
| A small glyph beside the line while it snaps level or upright (Autodesk) | SciForge's own mark near the pointer's end (short stroke under or beside the line) in the guide colour; after the click FreeCAD's glyph takes over. FreeCAD's cursor hint icons cannot be switched off (`Gui::ToolHandler::addCursorTail` has no switch) | Look **Unconfirmed** |
| Press-and-drag from the end of the line being drawn makes a tangent arc (Autodesk) | Same: press on the start of the line being drawn (the end of the last curve) and drag more than 6 px (`DragPixels`): an arc tangent to that curve follows the pointer with SciForge's preview and a tangent mark; release places its end (snapped to a sketch point, a guide crossing or the grid; Ctrl frees it); the chain goes on from there. Works from a line's and from an arc's end. Arc + Tangent + the end's constraints are one undo step "Tangent arc". A plain click (< 6 px) still does what it did. Setting `TangentArc` (on) | From an arc's end, the snapping, the threshold and the one undo step **Unconfirmed** |
| Fixed geometry green; fully defined black (white on dark) (Autodesk) | Blocked curves and locked points (Fix / Unfix) are painted green (`#4ad66d`) after each of FreeCAD's recolourings (`sketch_mode.FixedColour`); fully constrained stays white. Selection (`#3b5bdb`, the value FreeCAD's own packs write) and hover (`#246eab`) colours are pinned while SciForge is on so a selected or hovered line is never the free blue (FreeCAD's Light theme hovers in green); given back when SciForge is off. They are FreeCAD-wide: part selection and hover use them too | Shades **Unconfirmed**; a Block on a construction line is green (FreeCAD alone: orange) |
| Undo while the line tool draws | Review fix 2026-10-13: FreeCAD's tool keeps the point it was started on across undo and would join the next line to itself (solver failure). SciForge stops and restarts the line tool after every undo / redo and goes on from the newest remaining end, or says "Line: click where to start."; a self-joined Coincident is removed and logged | Matches (no corruption) |

Settings live in FreeCAD's parameters at `BaseApp/Preferences/Mod/SciForge/SketchInference`
(`Enabled`, `CtrlFree`, `GuideConstraint`, `GuidePixels`, `MaxHovered`, `HVDegrees`,
`PerpendicularDegrees`, `Parallel`, `ParallelDegrees`); there is no dialog yet.

How it works (and its limits): FreeCAD computes the snapped point in C++ from the mouse
pixel. SciForge's filter on the 3D view swallows each mouse event and gives FreeCAD a copy
moved to the pixel nearest to the guide, so FreeCAD's own tool draws the preview and
places the point there; after the click the point is moved exactly onto the guide and the
constraint is added. Limits found while building it:

- A pixel is about 0.1-0.3 mm, so the preview is within half a pixel of the guide; the
  finished geometry is exact (the constraint and an exact move after the click).
- FreeCAD's grid snap stays on for that copy unless it would pull the point off the guide
  (a guide from a point just off a grid line, perpendicular, parallel): then SciForge
  snaps the free coordinate to the same grid itself (FreeCAD's grid spacing is
  recomputed in Python from the camera, as `ViewProviderGridExtension` does).
- A length typed into FreeCAD's field wins: when the line's end is no longer on the
  guide, the guide is not shown and nothing is added; a level/upright/perpendicular
  direction still applies (also for a line finished with Enter).
- Cost: about 2 ms per mouse move on a 400-curve sketch (8 ms right after a change).
- FreeCAD's click jumps to a point marker under the mouse before any snapping
  (`ViewProviderSketch::mouseButtonPressed` uses the picked point's position): for Ctrl,
  SciForge shrinks the view's pick radius for that click.
- Guides: not for the centre-point arc's end-angle click and the slot's width click (the
  point placed is not at the pointer); 3-point circle / arc and circle rim points get the
  snap but no constraint and no exact move after the click (within half a pixel).
- `_check_preview` hides a guide when FreeCAD's preview is more than 3 px away; for circles
  with a radius over about 500 mm the 50-segment preview can exceed that.
- A tangent arc is also offered at a chain's first point when it sits on existing curves
  (tangent to the newest curve ending there). After Ctrl+Z of a tangent arc the Line tool
  waits for a new first point. A drag within 1 degree of the tangent makes no arc.
- FreeCAD's own hint icons for its constraints still follow the cursor; SciForge's marks
  (guide, right angle, level / upright, tangent) are drawn in the scene.
- Pressing or releasing Ctrl without moving the mouse changes nothing until the next move
  or click.
- A C++ version (`SnapManager::snap`, `DrawSketchHandler::seekAutoConstraint`) would give
  sub-pixel previews and FreeCAD's single undo step; it is not needed for the behaviour.

Scenario `sketch_infer` (all real mouse moves and clicks): Ctrl, guides (also on a sketch
on the XZ plane), perpendicular from and onto a slanted line, level within 4 degrees,
parallel off/on, a typed length beating a guide, undo/redo. 2026-10-13: `sketch_infer_tools`
(guides in every tool, undo, cost under 2 ms per move on a 400-curve sketch),
`sketch_glyphs`, `sketch_tangent_arc`, `sketch_colours` (screen pixels), `sketch_infer_undo`
(undo while drawing, L again mid-line, Leave, a turned plane in a tilted view, a tool started
outside SciForge). Unit tests `test_sketch_infer_core.py`. Settings added: `TangentArc`,
`DragPixels` (6).

## Known gaps

| Fusion | Why not yet |
|---|---|
| Shift to force a midpoint; guides for the arc's end-angle click and the slot's width click | Not built (`sketch_infer.py`) |
| Angle typed relative to the previous line | FreeCAD's angle field is measured from the X axis |
| Fusion's floating green check near the pointer while drawing a line | Not built; OK is in the right-click menu, Enter and a double-click on the end point end the line |
| Midpoint Line, 3-Point Rectangle, 2-Point/2-/3-Tangent Circle, Tangent Arc, Edge Polygon, Overall/Center Point Slot, Conic, Text, Project to Surface, 3D Sketch, Collinear/Concentric/Midpoint/Curvature constraints | Greyed in the menus (not built yet) |
| Fusion's constraint glyph look | FreeCAD's glyphs, recoloured (no red) |
