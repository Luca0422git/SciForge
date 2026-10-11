# Parity spec: CONSTRUCT and INSPECT (Measure, Section Analysis, Center of Mass, Interference)

Source: Fusion's documented CONSTRUCT and INSPECT commands and everyday Fusion behaviour (copied
behaviour only, never Fusion's assets or wording). Implemented in `src/Mod/SciForge/sciforge/`:
`construct.py` (geometry, no Qt) + `construct_ui.py` (dialog), `measure.py` + `measure_ui.py`,
`section.py` + `section_ui.py`, `analysis.py` + `com_ui.py` + `interference_ui.py`, shared helpers
`handles3d.py` (blue arrows, path handle, clickable dots) and `bodypick.py` (body picking, hint
colours). Status: **built and tested with real clicks, not yet signed off by Luca**.

Tests: scenarios `inspect_construct.py` (Offset Plane, every path), `inspect_construct_planes.py`
(the other 7 planes), `inspect_construct_axes.py` (axes and points), `inspect_construct_use.py`
(Extrude To Object a construction plane, Revolve about a construction axis, editing the plane
moves both), `inspect_measure.py`, `inspect_section.py`, `inspect_com_interference.py`; 6 golden
models `inspect_*.json`; unit tests `test_inspect_core.py`.

## CONSTRUCT (planes, axes, points)

All 19 entries of the CONSTRUCT menu open the same kind of dialog:

| Fusion | SciForge |
|---|---|
| Start with nothing selected: the first box waits, blue | Same. While a box waits, the origin planes (squares), origin axes or origin point are drawn so they can be clicked; they go away once picked. |
| Start with something selected: it is used | Same (pre-selection fills the boxes in order). |
| Live preview of the plane / axis / point | Same: the datum is created at once and follows every change. |
| Offset Plane: distance with a blue arrow | Same (drag or type; formulas and parameters work). Default 10 mm. |
| Plane at Angle: line + angle, rotate handle | Same, with a curved blue handle. 0 deg = the plane the line already lies in (see "assumptions"). |
| Tangent Plane: curved face + angle (+ reference plane) | Face + angle (the plane touches the face where you clicked it, angle turns it round the face's axis). |
| Midplane, Plane Through Two Edges / Three Points | Same. Midplane of two parallel planes lies halfway; of two crossing planes it halves the angle. |
| Plane Tangent to Face at Point | Same: a face and a point on (or near) it. |
| Plane Along Path: edge + distance (proportional / physical) | Same; Distance Type combo, a blue dot that slides along the edge. |
| Axis Through Cylinder/Cone/Torus, Two Planes, Two Points, Edge | Same. |
| Axis Perpendicular at Point / to Face at Point | One entry, "Axis Perpendicular to Face at Point": one click on a face uses the clicked spot (Fusion's "at Point"); a second pick (vertex) sets the point. |
| Point at Vertex, Through Two Edges, Three Planes, Center of Circle/Sphere/Torus, Edge and Plane, Along Path | Same. |
| OK / Cancel / Esc / Enter; one undo step | Same. Cancel and Esc leave the design as it was. |
| Edit: double-click in the timeline | Same: every pick and value comes back (`EDITORS` for `PartDesign::Plane/Line/Point`). |
| Construction geometry usable by other commands | Create Sketch on a construction plane (also clicking it over the part), Extrude To Object, Revolve about a construction axis, Midplane / Offset of a construction plane. Editing a plane moves everything built on it. |
| Names Plane1, Axis1, Point1 in the Construction folder | Same. |

How it maps onto FreeCAD: each entry makes a PartDesign Plane / Line / Point in the active body.
Offset Plane of a face of the same body uses FreeCAD's own attachment (FlatFace + offset, so the
distance is an expression a parameter can drive). Everything else is attached to a hidden helper
(`ConstructionFrame`, a `Part::Part2DObjectPython` in the body, `SciForgeTimeline = False`) that
computes the exact frame on every recompute from the picks; the datum carries `SciForgeConstruct`
(which entry) and `SciForgeRefs` (the picks, so the timeline knows what it depends on).

## Measure (I)

| Fusion | SciForge |
|---|---|
| Click one or two things: face, edge, vertex, body | Same. A third click starts a new measure (Selection 1 = the new pick). |
| Selection Filter: Face/Edge/Vertex, Body, Component | Same list; Component is greyed (no components yet). |
| Precision list | Same steps 0 .. 0.1234567; default 0.123. |
| Results: Distance (minimum), Angle, Delta X / Y / Z, Area, Length, Volume, Position, Radius/Diameter | Same. Distance is the true minimum between the two (OpenCASCADE `distToShape`; endless planes and axes measured as such). Angles between lines/planes are shown 0..90 deg. |
| Show Snap Points (start, end, middle, centre) | Same: dots on the edge/face under the mouse; clicking one measures that point. |
| Click a value to copy it | Same (clipboard). |
| Dimension drawn in the 3D view | A line between the closest points with the distance written next to it. |
| Restart Selection, Close | Same. Measure changes nothing in the design (no undo step). |
| Values in the design's units | Same (mm / cm / m / in / ft from Document Settings). |

## Section Analysis

| Fusion | SciForge |
|---|---|
| Pick a face or plane; the part is cut there | Same: origin squares are drawn to click; the cut shows at once (Coin clip plane on every body), with coloured cut faces. |
| Distance arrow, X Angle / Y Angle rotate handles, Flip | Same (blue arrow + two curved handles at the middle of the part). |
| Section colour (from body / custom swatches), Show Hatch | Same: From Body or Custom, 7 swatches, hatch lines on the cut faces. |
| Stored in the browser's Analysis folder, eye to show/hide, several at once | Same: `Section1`, `Section2` ... are document objects (`SciForgeType = "SectionAnalysis"`); hiding one removes its cut. Several sections cut together. |
| Edit the analysis | Select it in the browser and run Section Analysis: the dialog opens with its values (see gaps). |
| OK / Cancel / Esc, undo | Same; Cancel leaves no analysis behind. |

## Center of Mass

| Fusion | SciForge |
|---|---|
| Pick bodies (or all visible); a marker at the centre, X / Y / Z shown | Same: the black/white marker on top of the part, coordinates in the dialog. |
| Stored in the Analysis folder | Same (`Center of Mass1`), and it follows the design: picked bodies through FreeCAD's links; "all visible bodies" is measured again after every recompute, a body shown or hidden, undo / redo. |

Volume-weighted over the picked solids (one material assumed).

## Interference

| Fusion | SciForge |
|---|---|
| Pick 2+ bodies, Compute, list of interfering pairs with volumes | Same: a table (#, Body 1, Body 2, Volume); overlaps drawn red on top of the part. |
| Include Coincident Faces | Same: touching bodies are listed with volume 0 and their shared faces drawn orange. |
| Stored in the Analysis folder | Same (`Interference1`), results kept and shown again when edited. |

## Assumptions to confirm with Luca

- Plane at Angle: which plane is 0 deg. SciForge: the plane the line already lies in (a sketch
  line: its sketch; an edge: the flat face next to it; origin X / Y / Z axis: XY / YZ / XZ).
- Angle direction: SciForge turns right-handed about the line pointing "up" (Z, else Y, else X),
  so the same value gives the same plane whichever way the edge runs.
- Section Analysis cuts away the side the picked face's outside points to (the blue arrow
  points that way; for a top face, what is above the cut), and Flip keeps that side instead.
- Measure shows angles 0..90 deg between two lines or planes (no "outside" angle).

## Known gaps (honest list)

- Tangent Plane has no "Reference Plane" input (the angle turns about the face's own axis).
- Plane / Point Along Path take one edge (not a chain); Physical distance on a non-uniform
  spline is measured along the curve once (not re-measured when the curve changes shape).
- Offset Plane has no "To Object" extent.
- Section Analysis, Center of Mass and Interference are edited by selecting them in the browser
  and running the command again; double-click / right-click Edit in the browser for Analysis
  items belongs to the browser (the dialogs declare `EDITORS` for it). The Analysis folder opens
  collapsed.
- Center of Mass assumes one material (density) for every body.
- Measure: Component filter greyed (no components yet); selection boxes show what was picked
  in words rather than "1 selected".
- Interference: "Create bodies from interferences" is not built.
