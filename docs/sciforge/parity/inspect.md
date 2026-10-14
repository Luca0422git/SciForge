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
moves both), `inspect_measure.py`, `inspect_section.py`, `inspect_com_interference.py`; the QA
passes `inspect_qa.py` .. `inspect_qa8.py` (52 paths a Fusion user takes: wrong pick order, OK
with nothing picked, Esc half way and while dragging, edits from the timeline, undo / redo,
save / reopen, deleted references, Measure in a sketch, materials, another command's key with
a dialog open, parameters and typos in value boxes, handles let go over the part and the face
picked again, the timeline marker rolled back, a body made after a section, three bodies in
Interference, the x of a selection box, Ctrl+Z / Ctrl+Y); 8 golden models `inspect_*.json`;
unit tests `test_inspect_core.py`.

## CONSTRUCT (planes, axes, points)

All 19 entries of the CONSTRUCT menu open the same kind of dialog:

| Fusion | SciForge |
|---|---|
| Start with nothing selected: the first box waits, blue | Same. While a box waits, the origin planes (squares), origin axes or origin point are drawn so they can be clicked; they go away once picked. |
| Start with something selected: it is used | Same (pre-selection fills the boxes in order). |
| Only what fits the blue box can be picked; clicks go through the rest | Same: construction planes / axes / points the box cannot take let the click through to what is behind (a corner behind a construction plane for Point at Vertex, the YZ square behind an axis for Midplane). |
| Live preview of the plane / axis / point | Same: the datum is created at once and follows every change. |
| Offset Plane: distance with a blue arrow | Same (drag or type; formulas and parameters work). Default 10 mm. |
| Offset Plane Extent: Distance / To Object (a sketch point, a corner or a construction point the plane goes through; it follows the point) | Same (2026-10-13): Extent row between Plane and the value; To Object shows an Object box instead of Distance and no arrow; the plane follows the point when the part changes. Switching an edit back to Distance keeps the plane where it is and shows that distance. |
| Value boxes take parameters and formulas; a typo is refused | Same: "gap", "gap * 3" follow the parameter and are listed under the boxes ("Distance = gap", also when editing); something that is no value ("gap +") keeps the dialog open on Enter and OK and says why. |
| Pressing / letting go of a handle is not a pick | Same: FreeCAD also selects the face under the mouse at the press and at the release of a drag; those selections are ignored for a moment (`handles3d.just_used`), so letting go of an arrow over the part never re-picks the plane or face. |
| Plane at Angle: line + angle, rotate handle | Same, with a curved blue handle. 0 deg = the plane the line already lies in (see "assumptions"). |
| Tangent Plane: curved face + angle (+ reference plane) | Face + angle (the plane touches the face where you clicked it, angle turns it round the face's axis). |
| Midplane, Plane Through Two Edges / Three Points | Same. Midplane of two parallel planes lies halfway; of two crossing planes it halves the angle (two faces of a part meeting at an edge: the plane runs from that edge through the part). |
| Plane Tangent to Face at Point | Same: a face and a point on (or near) it. |
| Plane Along Path: edge + distance (proportional / physical) | Same; Distance Type combo, a blue dot that slides along the edge. |
| Axis Through Cylinder/Cone/Torus, Two Planes, Two Points, Edge | Same. |
| Axis Perpendicular at Point / to Face at Point | One entry, "Axis Perpendicular to Face at Point": one click on a face uses the clicked spot (Fusion's "at Point"); a second pick (vertex) sets the point. |
| Point at Vertex, Through Two Edges, Three Planes, Center of Circle/Sphere/Torus, Edge and Plane, Along Path | Same. |
| OK / Cancel / Esc / Enter; one undo step | Same. Cancel and Esc leave the design as it was (also Esc while an arrow is held). Enter right after a sum typed in a value box ("70 + 5", "-15") finishes at once. |
| A construction whose references were deleted | Stays where it was with a warning in the timeline; the rest of the part keeps computing. Editing it asks for new picks (the construction itself never takes a click while it is edited). |
| Made with the timeline marker rolled back | Goes in at the marker (before the later steps), like any feature. |
| Edit: double-click in the timeline | Same: every pick and value comes back (`EDITORS` for `PartDesign::Plane/Line/Point`). |
| Construction geometry usable by other commands | Create Sketch on a construction plane (also clicking it over the part), Extrude To Object, Revolve about a construction axis, Midplane / Offset of a construction plane. Editing a plane moves everything built on it. |
| Names Plane1, Axis1, Point1 in the Construction folder | Same. |

How it maps onto FreeCAD: each entry makes a PartDesign Plane / Line / Point in the active body.
Offset Plane of a face of the same body uses FreeCAD's own attachment (FlatFace + offset, so the
distance is an expression a parameter can drive). Everything else is attached to a hidden helper
(`ConstructionFrame`, a `Part::Part2DObjectPython` in the body, `SciForgeTimeline = False`) that
computes the exact frame on every recompute from the picks; the datum carries `SciForgeConstruct`
(which entry) and `SciForgeRefs` (the picks, so the timeline knows what it depends on).

### Offset Plane To Object, picks found again (2026-10-13, gaps work)

Sources: **Autodesk** "Create an offset plane" (SLD-CONSTRUCT-OFFSET-PLANE, search excerpts):
Extent Distance or To Object; To Object takes a sketch point or a vertex and the plane stays
tied to it. **Autodesk** API: ConstructionPlaneOffsetThroughPointDefinition (a vertex, a sketch
point or a construction point). A construction built on a face, an edge or a corner that
FreeCAD loses after an earlier edit (its "missing element reference", e.g. the box's corner
after the box is made wider) now finds it again where it was (the remember-element approach of
Sweep and Loft: `curves.remember` / `curves.refind` in the hidden ConstructionFrame), so the
plane follows the corner instead of staying behind. Golden `inspect_offset_plane_to_object`,
scenario `gaps_offset_plane_to.py`.

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
| Measure inside a sketch (SKETCH tab > INSPECT, or I) | Same: the sketch stays open; Measure shows at the top of the sketch's panel and measures sketch curves and points (construction lines too); Close / Esc end Measure only; Finish Sketch ends both. |
| The Center of Mass sign can be measured from | Same: while Measure is open its centre is a dot to click (a point). |
| Values in the design's units | Same (mm / cm / m / in / ft from Document Settings). |

## Section Analysis

| Fusion | SciForge |
|---|---|
| Pick a face or plane; the part is cut there | Same: origin squares are drawn to click; the cut shows at once (Coin clip plane on every body), with coloured cut faces. |
| Distance arrow, X Angle / Y Angle rotate handles, Flip | Same (blue arrow + two curved handles at the middle of the part). One press moves one handle. |
| Distance / X Angle / Y Angle take parameters and formulas | Same: kept as expressions on the analysis ("-gap"), so the cut follows the parameter; listed under the boxes; a typo keeps the dialog open. |
| A body made after the section is cut too | Same. |
| Section colour (from body / custom swatches), Show Hatch | Same: From Body or Custom, 7 swatches, hatch lines on the cut faces. |
| Stored in the browser's Analysis folder, eye to show/hide, several at once | Same: `Section1`, `Section2` ... are document objects (`SciForgeType = "SectionAnalysis"`); hiding one removes its cut. Several sections cut together. |
| Edit the analysis | Double-click it (or right-click Edit) in the browser, or select it and run Section Analysis: the dialog opens with its values. |
| OK / Cancel / Esc, undo | Same; Cancel leaves no analysis behind. |

## Center of Mass

| Fusion | SciForge |
|---|---|
| Pick bodies (or all visible); a marker at the centre, X / Y / Z shown | Same: the black/white marker on top of the part, coordinates in the dialog. |
| Stored in the Analysis folder | Same (`Center of Mass1`), and it follows the design: picked bodies through FreeCAD's links; "all visible bodies" is measured again after every recompute, a body shown or hidden, undo / redo. |
| Mass from each body's Physical Material | Same: each body weighs its volume times its material's density (a body still on FreeCAD's Default counts as Steel, as Fusion designs start in Steel). |
| Picked bodies deleted | The marker hides and the dialog says the bodies are gone (it never switches to "all bodies"). |

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
- Tangent Plane's optional Reference Plane is not offered: Autodesk's help lists it as an
  optional pick without saying how it orients the plane (so any rule would be a guess).
- Plane / Point Along Path take one edge, not a chain (Fusion's help does not say a chain
  is taken either).
- The browser's Analysis folder opens collapsed (its items are edited by double-click or
  right-click Edit, or by selecting one and running the command again).
- Measure inside a sketch measures the sketch's own curves and points (lines, circles,
  their ends, the sketch origin and axes, projected curves); Show Snap Points inside a sketch
  is not covered by a scenario yet.
- Measure: Component filter greyed (no components yet); selection boxes show what was picked
  in words rather than "1 selected".
- Interference: "Create bodies from interferences" is not built.
