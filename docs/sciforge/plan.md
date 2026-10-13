# SciForge plan: what is left, in order (2026-10-12)

Written after the research report `reports/Fusion sketching ViewCube and navigation.md`.
The part-modeling core (sketch, extrude, revolve, hole, fillet, patterns, shell, sweep,
loft, body tools, inspect, timeline, browser) is built and tested (133 click-through
scenarios, about 17,000 checks, green on GitHub). This plan covers what is still missing,
most urgent first.

## How the work ships (why most items are Python)

- **Python changes** reach Luca with the quick update (download from the newest green
  "SciForge tests" run, about a minute to install). They are tested here, click by click,
  before they are pushed.
- **C++ changes** (FreeCAD's compiled core) need the Windows full build
  (`sciforge-build.yml`, about 3 hours). They cannot be tested here (the tests run
  the official FreeCAD plus the SciForge module). Three earlier C++ fixes (patches #4,
  #6, #7) are still waiting for that build.

So every item below takes the Python route when there is one, and C++ only as a fallback,
bundled into one full build.

## Now: the three things Luca asked for first

### A. Stable orbit (Fusion's Constrained Orbit) [small] — done 2026-10-13 (`parity/ui-shell.md`, Orbit)

What Fusion does: Shift + middle-drag spins the model about its up axis and tilts it
toward or away from you; it never rolls, so vertical edges stay vertical.
Why SciForge tips: FreeCAD 1.1 switched its default orbit to "Rounded Arcball" (a
trackball that rolls) in 2025, and SciForge never overrode it.

1. Set FreeCAD's "Free Turntable" orbit (`OrbitStyle = 2`), which is Fusion's
   Constrained Orbit, in SciForge's viewer settings. Scenario: orbit with Shift+middle
   in several directions, check the camera never rolls (the up axis stays vertical on
   screen).
2. An Orbit choice in the bottom navigation bar: Constrained (default) or Free, like
   Fusion's.
3. Mouse details where FreeCAD's "Revit" style differs from Fusion, done in Python by
   catching the mouse before FreeCAD: double-click the wheel to fit; Ctrl+Shift+middle-drag
   to zoom; Shift + single middle click to set the orbit centre (green dot); Reset Orbit
   Center in the right-click menu. Each with a scenario.

### B. Fusion's ViewCube [medium] — done 2026-10-12 (`parity/ui-shell.md`, ViewCube)

What Fusion does: a cube in the top-right corner. Click a face, edge or corner (26
targets) and the view turns there smoothly; **drag the cube to orbit**; a small house
icon goes Home; right-click offers Go Home, Orthographic / Perspective / Perspective with
Ortho Faces, Set current view as Home (Fit to View or Fixed Distance), Reset Home; an
X/Y/Z triad in red/green/blue. FreeCAD's cube has the 26 targets but dragging moves the
widget, it has no Home icon, its arrows turn 45 degrees and its menu is different.

Route: **SciForge's own cube, drawn in Python** over the 3D view (FreeCAD's cube hidden).
It is drawn from the camera every frame, so it always matches the view; clicks are found
by testing which drawn region is under the mouse; dragging uses the same turntable orbit
as Shift+middle so both feel the same. SciForge's own drawing and words (nothing copied
from Autodesk's artwork). Parts:

1. The cube: bevelled faces, edges and corners, face labels, hover highlight, idle
   transparency, the X/Y/Z triad.
2. Click -> animated turn to the view (faces: straight on; edges: between two faces;
   corners: isometric); face-on arrows that turn 90 degrees.
3. Drag -> constrained orbit; on release, nothing snaps (to be checked in Fusion).
4. Home icon; Home stored per design; the right-click menu above.
5. Scenarios for each, with real clicks and drags on the cube.

### C. Sketching that feels like Fusion [large] — done 2026-10-13 except items noted in `parity/sketch.md` gaps

What Fusion does while you draw: hover a point to "acquire" it; dashed guide lines show
when the cursor lines up with it; a line close to level or plumb snaps and shows a small
glyph beside it; a line ending on another line at about 90 degrees snaps perpendicular;
every glyph showing at the click becomes a real constraint (which you can see and
delete); holding Ctrl turns all of that off; press-and-drag from a line's end makes a
tangent arc; geometry is blue until fully defined, then black.

What FreeCAD already does: snaps to endpoints, midpoints, centres and curves; infers
coincident, point-on-curve, midpoint, tangent and horizontal/vertical (fixed 2 degrees);
length and angle boxes while drawing (SciForge's Line already uses them). Missing: the
dashed guides and snapping to them, perpendicular (and maybe parallel) inference, glyphs
beside the line, Fusion's Ctrl (in FreeCAD, Ctrl does the opposite: 5-degree angle
steps), the tangent-arc drag.

Status 2026-10-12: the feasibility test passed, the Python route works (no C++ needed).
Items 2, 3, 4 are built for Line (L) in `sketch_infer.py` (Ctrl in every tool), with
the guide and a right-angle mark drawn by SciForge (part of 5); see
`parity/sketch.md`. Still to do: guides for the other tools' points, 5 (glyphs for
level/upright), 6, 7, and Luca's Fusion checks 3-6 for the tolerances.

Route: a **SciForge "inference layer" in Python** on top of FreeCAD's tools:

1. **Feasibility test first** (small): catch the mouse before FreeCAD, move the pointer's
   position onto a guide (so FreeCAD's own tool lands exactly there), and add the
   constraint after the click. If FreeCAD's tool does not accept a moved position
   reliably, fall back to a C++ Sketcher patch for the snapping part (then the full
   build becomes necessary).
2. Ctrl = no snapping and no automatic constraints while held (Fusion's meaning).
3. Dashed alignment guides from the last few hovered points (horizontal and vertical),
   snapping to them; the constraint added on click.
4. Perpendicular (and, if Fusion does it, parallel) inference with a glyph beside the
   line, added as a constraint on click.
5. Glyphs drawn beside the geometry in SciForge's own style (not FreeCAD's cursor icons).
6. Press-and-drag from the end of a line for a tangent arc in Line (L).
7. Colours checked against Fusion (fixed geometry green; fully defined black or white in
   the dark theme).
8. A scenario per behaviour, drawing with real mouse moves and clicks.

## Next: the rest, in order (for multi-part robotics and 3D printing)

1. **Selection like Fusion** [medium]: drag left-to-right selects what is fully inside,
   right-to-left what it touches; click and hold for "Select Other" (FreeCAD's Clarify
   Selection under it); selection filters.
2. **Components** [large]: many components in one design, one active component that gets
   new work, New Component, the browser's component tree.
3. **Joints** [large]: Fusion's two-click joint picking (snap points on each part), the 7
   joint types, As-built joints, Ground, Rigid Group, limits, Drive Joints, Capture
   Position, Motion Link. FreeCAD 1.1's Assembly solver already does most joint types,
   limits and motion, so this is mostly Fusion-style picking and dialogs on top.
4. **Versions and recovery** [medium]: a version on every save with a history list (local
   files, git underneath), autosave and crash recovery. — done 2026-10-13 (branch
   `sf/versions`, `parity/versions.md`): also the Data Panel and Insert Design by relative
   path.
5. **Import of bought parts and meshes** [medium]: STEP into a component, mesh to solid,
   DXF/SVG into a sketch, a calibrated canvas (reference image).
6. **Sketch Text and Emboss** [medium].
7. **Direct edits on imported parts** (no history) [medium].
8. **Smaller gaps in built features** (each parity doc lists them): Thin extrude, taper
   with To Object, loft end conditions and guide surface, Offset Plane To Object, curvature
   / zebra / draft analysis, timeline marker before the first solid, browser names that
   match the timeline, the length-in-an-angle-box bug, old coils/pipes, Join that does not
   touch the part becoming a New Body, picked edges kept after reopen + edit.
9. **Later**: drawings (on FreeCAD's TechDraw), surface tools in Fusion's style, decals,
   contact sets, trackpad gestures, Y-up designs.
10. **Making it an app**: name, icons, installer, Linux package, a Fusion-to-SciForge
    cheat sheet, speed and stability.

## Housekeeping

- **The full build** (`sciforge-build.yml`): run #2 compiled the C++ fixes on Windows and
  Linux, but its packaged SciForge lacked 81 modules (install rules kept by hand). Fixed on
  2026-10-12; the next run should give Luca a working download.
- `MEMORY.md` status checkboxes partly out of date (for example "Unified Revolve / Hole /
  Fillet dialogs" is done): tidy at the next update.

## What Luca can do to help (optional, at the office)

Short screen recordings or screenshots in real Fusion settle the details no web page
gives. Nothing from them is copied into SciForge; they are only for matching behaviour.
Most useful first:

1. Preferences > General: which orbit type is set; then orbit a box upwards past the top
   view (does it stop or go over the top?).
2. The ViewCube: idle, hovering a face, an edge, a corner; the Front view (are there
   small arrows around it?); the Home icon; the right-click menu; drag it and let go.
3. Draw lines about 1, 3, 5 and 8 degrees off level: which ones snap level, and the glyph.
4. Hover a line's end point, move away sideways: the dashed guide; click on it, then look
   at the constraints that were added.
5. A line ending on a slanted line at about 90 degrees; a line roughly parallel to a
   separate line: which glyphs show.
6. Hold Ctrl while drawing near a point and near level.

The full list of ten checks is at the end of the research report.
