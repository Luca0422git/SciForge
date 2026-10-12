# One Setting Steadies the Orbit; Sketching Needs C++

The orbit tipping off axis has a simple cause and a quick fix. When you hold Shift and drag with the middle button, FreeCAD 1.1 turns the view with a "virtual trackball" (the Rounded Arcball style, stored as `OrbitStyle = 4`). A trackball adds a twist whenever the mouse moves off centre. Fusion users normally use Constrained Orbit instead. It works like a turntable: the model spins only around the ViewCube's Top/Bottom axis, and Top stays upright. Setting `OrbitStyle = 2` (FreeCAD's "Free Turntable") from SciForge's Python theme gives that behaviour today, through a quick update with no rebuild.

The ViewCube is about half done. FreeCAD's own cube (the NaviCube) already has Fusion's 26 click targets, animated view changes and the small arrows around a face-on view. But dragging it moves the cube widget around instead of turning the model, it has no Home icon, and its right-click menu is different. The look is controlled by Python settings. Drag-to-orbit and Home are best added as a small C++ change to a single file.

Sketching is the real engineering job. FreeCAD already:
- snaps to endpoints, midpoints, centres and curves;
- infers coincident, midpoint, tangent and horizontal/vertical constraints (horizontal/vertical within a fixed 2°);
- shows Fusion-like length and angle boxes while you draw.

It is missing:
- Fusion's dashed alignment guides;
- inferred perpendicular constraints;
- the "hover a point to use it as a reference" behaviour;
- constraint icons drawn next to the line;
- Fusion's meaning of the Ctrl key. In Fusion, Ctrl turns off all snapping and automatic constraints. In FreeCAD, Ctrl turns on 5° angle steps.

These need a C++ change to FreeCAD's Sketcher module, which the SciForge spec already allows.

About the evidence: no Autodesk page could be opened during the research, so every Fusion fact here comes from search-engine summaries. Autodesk's own help pages, blog and support articles confirm the broad behaviours. The numbers that decide how a sketcher feels are not published anywhere: snap distances, angle tolerances, icon colours, animation times. A short recording session in real Fusion should therefore come before the sketch work. Beyond these three areas, the biggest differences a Fusion user will hit are, in order for a robot builder:
1. components, with one "active" component that receives new work;
2. joints placed with Fusion's two-click picking;
3. Fusion's selection habits.

## No Autodesk page was opened, so every Fusion detail carries a label

The research environment could not reach autodesk.com, help.autodesk.com, the Autodesk forums, Product Design Online or the Web Archive. Each Fusion finding below therefore rests on the search engine's summary of the linked page, not on a full reading. Fusion was renamed from "Fusion 360" to "Fusion" in January 2024, so older sources use the old name ([Wikipedia](https://en.wikipedia.org/wiki/Autodesk_Fusion)). FreeCAD and SciForge findings come from reading the FreeCAD 1.1.4 source code in this repository. That is the most reliable evidence in this report. Every Fusion claim carries one of the labels below, and the tables repeat them.

| Label | What it means | How far to trust it |
|---|---|---|
| **Autodesk** | Autodesk help page, support article, blog or API reference, read through a search summary | The behaviour is right. The wording and the version may have moved on. |
| **Forum / tutorial** | Autodesk Community posts (Autodesk staff are noted) or third-party tutorials | Usually right, but often several years old |
| **Unconfirmed** | Sources disagree, there is a single old post, or nothing at all | Check in real Fusion before building it |
| **Source code** | Read directly from FreeCAD 1.1.4 or SciForge files in this repo | Reliable |

A few terms come up repeatedly. They are explained here once.

| Term | Plain meaning |
|---|---|
| Snap | The cursor jumps to an exact spot (an endpoint, a midpoint, a grid line) when it gets close |
| Inference | The program guesses your intent while you draw ("this line looks horizontal") and shows that guess |
| Constraint | A permanent rule stored in the sketch (horizontal, coincident, tangent...) that the solver keeps true |
| Auto-constraint | A constraint added for you when you click, taken from the inference showing at that moment |
| Glyph | The small icon drawn next to geometry to show a constraint |
| Heads-up boxes / OVP | The small number boxes that follow the cursor while you draw. FreeCAD calls them "on-view parameters" (OVP). |
| Turntable orbit | The model spins about a fixed vertical axis, like a record player, and tilts toward or away from you. Vertical edges stay vertical on screen. |
| Trackball orbit | You roll the model like a ball under your palm. It can twist (roll) and end up crooked. |
| Roll | Rotation about your line of sight. It is what makes vertical edges lean. |
| Pivot / orbit centre | The point the view turns around |
| Python setting | SciForge's Python code changes one of FreeCAD's stored preferences. Ships in a quick update. |
| Python overlay | SciForge draws its own widget or graphics on top of FreeCAD's 3D view, in Python. Also a quick update. |
| C++ patch | A change to FreeCAD's compiled core. It needs a full build, a `SCIFORGE:` comment and an entry in `docs/sciforge/core-patches.md`. |

## Fusion sketching turns every snap into a constraint you can see and delete

### Fusion snaps to the points you hover, and remembers the last three

In Fusion, "object snaps" and constraints are the same thing: whatever the cursor locks onto becomes a constraint when you click. An answer on the Autodesk forum describes snaps appearing as the cursor nears a circle centre or as a line is drawn level, and says holding Ctrl while picking stops the constraint from being applied ([Forum](https://forums.autodesk.com/t5/fusion-support-forum/how-do-i-turn-object-snap-on/td-p/8898853)). Starting a line on an existing point adds a Coincident constraint ([PDO tutorial](https://productdesignonline.com/learn-autodesk-fusion-in-30-days-2026-day-4/)).

Midpoints are better documented:
- An **Autodesk support article says to hold Shift and hover a line to snap to its midpoint** ([Autodesk](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/Unable-to-constrain-to-the-midpoint-of-a-line-in-Fusion-360.html)).
- This works only while a drawing command is running ([Forum](https://forums.autodesk.com/t5/fusion-support-forum/holding-shift-and-hovering-over-a-line-does-not-bring-up/td-p/11900143)).
- Passing over the midpoint without Shift also catches it ([Forum](https://forums.autodesk.com/t5/fusion-design-validate-document/snap-to-midpoint-functionality/td-p/6662693)).
- Autodesk's blog describes the midpoint glyph as a triangle, shown as "a triangle with an X" when the snap is hit ([Autodesk blog](https://www.autodesk.com/products/fusion-360/blog/quick-tip-midpoint-constraint-shortcut/)).

A sketch can snap only to geometry that is in the sketch, either drawn there or projected into it. A preference, "Auto project edges on reference", projects a body edge automatically when you snap to it, but only while you look straight at the sketch. Sources disagree on whether it is still on by default ([PDO knowledge base](https://knowledge.productdesignonline.com/article/50-day-5-cant-snap-to-edge-of-body-in-fusion-360); [Forum](https://forums.autodesk.com/t5/fusion-design-validate-document/auto-project-preferences/td-p/6836409)).

**Intersections are Fusion's weak spot.** Users report that Fusion intermittently fails to recognise where two curves cross. The usual workaround is to place a sketch point there or to Break the curve ([Forum](https://forums.autodesk.com/t5/fusion-design-validate-document/snap-point-at-the-intersection-of-two-construction-lines/td-p/6847042)). In about 2019 a forum reply said Autodesk had no plans for AutoCAD-style object snaps, and quadrant points on circles were still missing ([Forum](https://forums.autodesk.com/t5/fusion-support-forum/snapping-center-point-end-point-etc/td-p/8934886)). So to stay faithful to Fusion, SciForge does not need an intersection snap.

The subtle part is **acquisition**: how geometry becomes a reference for guides. A forum post about ten years old explains the rules ([Forum](https://forums.autodesk.com/t5/fusion-360-design-validate/snap-to-center-question/td-p/5992547)):
- existing geometry must be hovered before it becomes an inference target;
- lines created in the current command count automatically;
- **Fusion keeps at most three hovered targets**, and hovering a fourth drops the oldest;
- moving away from a hovered midpoint brings up a dashed guide line.

This rule is **Unconfirmed** for 2024 to 2026 builds. No source gives a snap distance in pixels or a hover time.

### Level and upright lines are inferred, and so is perpendicular; parallel, collinear and equal are not documented

**Horizontal/vertical (H/V).** Autodesk's blog says Fusion adds horizontal and vertical constraints automatically as you sketch ([Autodesk blog](https://www.autodesk.com/products/fusion-360/blog/mastering-sketch-constraints-autodesk-fusion-tutorial/)). A LinkedIn Learning (Lynda) course shows the inferred glyph "at the bottom of the line" while drawing. Clicking commits it, and you delete the glyph to remove the constraint ([Lynda tutorial](https://origin-www.lynda.com/Fusion-360-tutorials/Sketch-constraints-Horizontal-vertical-collinear/667363/703400-4.html)). Fusion uses **one combined Horizontal/Vertical constraint** that snaps to whichever axis is closer ([Autodesk help](https://help.autodesk.com/cloudhelp/ENU/Fusion-Sketch/files/SKT-CONSTRAIN-HORIZONTAL-VERTICAL.htm)). No source gives the angle tolerance.

**Perpendicular.** Fusion infers Perpendicular when a new line ends on another line. A 2015 idea post complained that a new vertical line ending on a horizontal line received Perpendicular instead of Vertical ([Forum idea](https://forums.autodesk.com/t5/fusion-360-ideastation-archived/horizontal-vertical-constraints-take-precedent-over/idi-p/5683627)). Whether Perpendicular still wins over H/V today is **Unconfirmed**.

**Parallel.** No source shows Parallel being inferred against a separate, non-touching line.

**Tangent.** Tangent has its own gesture. In the Line tool, you press on the last endpoint and drag: you get a **tangent arc**, and releasing returns to straight lines ([Autodesk blog](https://www.autodesk.com/products/fusion-360/blog/quick-tip-sketching-tangent-arcs/)). Moving to the other side of the line flips the arc ([Autodesk help](https://help.autodesk.com/view/fusion360/ENU/?guid=GD-SKETCH-TOOLS)). A tangent symbol shows during the drag, and Tangent is added only at the arc's start ([Tech and Espresso](https://www.techandespresso.com/blog/Fusion-360-Line-To-Arc-Shortcut-Tutorial)). Users say the gesture cannot be turned off (seen on the Inventor forum, which has the same gesture) ([Forum](https://forums.autodesk.com/t5/inventor-forum/why-does-the-line-tool-sometimes-produce-an-arc/td-p/7555396)). The 2-tangent and 3-tangent circles add Tangent constraints automatically ([PDO tutorial](https://productdesignonline.com/tips-and-tricks/how-to-use-the-circle-command-in-fusion-360-all-5-explained/)).

**Collinear and equal.** No source shows them being inferred. A forum answer says Fusion does not infer anything from construction lines or from a rectangle's invisible centre ([Forum](https://forums.autodesk.com/t5/fusion-design-validate-document/circle-in-center-of-rectangle-automatic-constraint/td-p/8966764)).

**Shape tools** come with fixed constraints of their own:
- the 2-point rectangle makes every side H/V;
- the 3-point rectangle adds Parallel and Perpendicular ([PDO tutorial](https://productdesignonline.com/tips-and-tricks/how-to-use-the-rectangle-sketch-command-in-fusion-360-all-3-explained/));
- slots add Tangent and Parallel ([PDO tutorial](https://productdesignonline.com/tips-and-tricks/how-to-use-the-slot-commands-in-fusion-360/)).

The constraints added by the centre rectangle, polygon and spline are **Unconfirmed**.

### Dashed guides exist, but their colour and what a click on them does are unsettled

Fusion draws dashed guide lines from acquired points. The evidence disagrees on the details:
- a forum thread mentions a "blue dashed inference line" in an Autodesk help video, made visible for one user by changing graphics preferences ([Forum](https://forums.autodesk.com/t5/fusion-360-design-validate/blue-inference-line/td-p/6208011));
- another describes a green dashed guide after hovering a midpoint ([Forum](https://forums.autodesk.com/t5/fusion-360-design-validate/snap-to-center-question/td-p/5992547));
- a YouTube video titled "Fusion Snap Guides" covers "the dashed blue lines that appear while sketching" ([YouTube](https://www.youtube.com/watch?v=MkVBNfVWB-I)).

No source settles four things:
- whether clicking on a guide adds a constraint (for example H/V between the two points);
- the dash pattern;
- whether the line runs from the point to the cursor or across the screen;
- whether extension guides along a line's direction exist.

Onshape, for comparison, shows orange dashed lines and accepts the constraint on click ([Onshape help](https://cad.onshape.com/help/fr_FR/Content/inferencing.htm)), but that is another product. Until someone checks in Fusion, SciForge's safest default is a guide that **moves the point but adds no constraint**.

### Ctrl turns everything off in Fusion, and FreeCAD gives Ctrl the opposite job

An Autodesk community moderator says that **holding Ctrl (Cmd on Mac) stops constraint inferencing completely** ([Forum, Autodesk staff](https://forums.autodesk.com/t5/fusion-support-forum/struggles-with-constraints/m-p/9505577)). Product Design Online gives the same tip ([PDO](https://productdesignonline.com/tips-and-tricks/2-sketch-constraint-secrets-you-should-know/)). Users add that Ctrl also turns off every snap, including the grid, and that no "snap but don't constrain" mode exists ([Forum](https://forums.autodesk.com/t5/fusion-360-design-validate/sketch-disable-constraints-but-keep-snap-to-grid/td-p/6965757)). There is no permanent off switch: idea requests for one were archived unanswered ([Forum idea](https://forums.autodesk.com/t5/fusion-360-ideastation-archived/preference-to-disable-auto-contraint-creation/idc-p/7917811)), while Autodesk Inventor does have a ribbon toggle ([Autodesk Inventor help](https://help.autodesk.com/cloudhelp/2014/ENU/Inventor/files/GUID-1E504789-DFC6-4B59-81AA-1EFC1B656FB1.htm)). To remove an unwanted auto-constraint, you hover or select its glyph and press Delete ([Autodesk support](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/How-to-delete-sketch-constraints-in-Fusion-360.html)).

AutoConstrain is a separate thing. It shipped in January 2025 on a new Automate tab and later gained gap and off-axis fixing. It is an AI tool that proposes constraints *after* you draw, not inference while you draw ([Autodesk blog](https://www.autodesk.com/products/fusion-360/blog/autoconstrain-for-fusion-is-here/); [Autodesk blog, Nov 2025](https://www.autodesk.com/products/fusion-360/blog/november-2025-product-update-whats-new/)). Treat it as a later, separate project.

Here lies a trap that neither research thread named on its own. In FreeCAD 1.1.4, **holding Ctrl while drawing switches on angle snapping in 5° steps** around the line's start point ([SnapManager.cpp](../src/Mod/Sketcher/Gui/SnapManager.cpp), Source code). A Fusion user who holds Ctrl to place a free, unconstrained line gets the opposite in SciForge today: forced angle steps, plus FreeCAD's usual auto-constraints. The proper fix is a few lines in `SnapManager::snap()` and `DrawSketchHandler::seekAutoConstraint()`.

A Python stopgap may also work, but it is untested. SciForge's existing sketch event filter would turn off FreeCAD's `Snap` master switch and the sketch's `Autoconstraints` property while Ctrl is held, and restore both on release. Both are read live ([SnapManager.cpp](../src/Mod/Sketcher/Gui/SnapManager.cpp); [ViewProviderSketch.cpp](../src/Mod/Sketcher/Gui/ViewProviderSketch.cpp)). Fusion's Shift-to-force-midpoint has no FreeCAD equivalent. FreeCAD pulls the cursor to a line's midpoint automatically within 5% of the line's length.

### Colours carry the constraint state, but the colour of inference glyphs is disputed

**Geometry colours** (Autodesk):
- normal geometry is **solid blue while under-constrained and turns black when fully constrained**;
- construction lines are dashed orange;
- locked ("fixed") geometry is green;
- projected geometry is purple ([Autodesk blog](https://www.autodesk.com/products/fusion-360/blog/sketching-basics-in-autodesk-fusion/); [Autodesk support](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/What-does-the-color-line-means-in-Fusion-360-sketch.html)).

Closed regions ("profiles") are shaded light blue ([Autodesk blog](https://www.autodesk.com/products/fusion-360/blog/fusion-360-sketch-fundamentals/)). They were orange before about 2020 ([Forum](https://forums.autodesk.com/t5/fusion-360-design-validate/sketch-blue-interior/td-p/9668011)), so older videos look different. When a sketch becomes fully constrained, a red lock appears on its icon in the browser ([Autodesk help](https://help.autodesk.com/cloudhelp/ENU/Fusion-Sketch/files/SKT-FULLY-DEFINE-CONSTRAIN-SKETCH.htm)).

**Constraint glyphs:**
- "Show Constraints" in the Sketch Palette shows or hides them all. With it off, selecting curves shows only their constraints ([Forum](https://forums.autodesk.com/t5/fusion-design-validate-document/viewing-conflicting-constraints/td-p/6476854)).
- Coincident glyphs stay hidden until you hover nearby ([Autodesk support](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/How-to-delete-sketch-constraints-in-Fusion-360.html)).
- Fusion has no built-in list of constraints. A third-party add-in exists to fill that gap ([GitHub: ConstraintsLens](https://github.com/craigulliott/ConstraintsLens)).

The colour of the *temporary* glyph shown while drawing is reported as cyan ([VDCI tutorial](https://vdci.edu/learn/cad/introduction-to-sketch-tools-and-options-in-fusion-360)) and as blue ([nakayasu lecture notes](https://lecture.nakayasu.com/en/docs/fusion360/fusion360-sketch-constraints/)). A forum user calls the hover highlight "dark blue" ([Forum](https://forums.autodesk.com/t5/fusion-design-validate-document/issues-with-preselection-highlighting-of-sketcher-constraints/m-p/10941750)). The colours in Fusion's dark theme are **Unconfirmed**. SciForge already draws fully constrained geometry white in its dark theme, and that needs a side-by-side check.

### Heads-up boxes, the Line tool, the palette, the grid and the keys

**Heads-up boxes.** After the first click of a line, two input boxes follow the cursor: **length, then angle**. Moving the mouse changes the value until you press Tab, which locks it and shows a small lock icon ([PDO tutorial](https://productdesignonline.com/tips-and-tricks/how-to-use-the-line-command-in-fusion-360-secrets-revealed/)). Tab also switches between the two boxes ([Forum](https://forums.autodesk.com/t5/fusion-design-validate-document/numerical-inputs/td-p/7643334)). Rectangles offer width and height boxes in the same way ([Autodesk help](https://help.autodesk.com/view/fusion360/ENU/?guid=SKT-SKETCH-CREATE-RECTANGLES)). The dimension box accepts a number, a reference to another dimension, or an expression ([Autodesk help](https://help.autodesk.com/view/fusion360/ENU/?guid=SKT-SKETCH-CREATE-DIMENSIONS)). The boxes for circles, arcs, polygons and slots are **Unconfirmed**.

**The Line tool:**
- it chains segments one after another;
- clicking the start point closes the shape, and Enter completes the tool ([Autodesk help](https://help.autodesk.com/cloudhelp/ENU/Fusion-Sketch/files/SKT-CREATE-LINES.htm));
- Esc leaves the tool ([PDO tutorial](https://productdesignonline.com/learn-autodesk-fusion-in-30-days-2026-day-3/));
- a double-click ends the current chain but keeps the tool active ([Tech and Espresso](https://www.techandespresso.com/blog/fusion-360-sketch-separate-lines-multiple-lines)).

**The Sketch Palette** is a floating panel with these parts ([Autodesk help](https://help.autodesk.com/cloudhelp/ENU/Fusion-Sketch/files/GUID-4183A4B7-E002-4396-AD5A-7FF3C8B2F33A.htm); [Autodesk blog](https://www.autodesk.com/products/fusion-360/blog/how-to-create-and-modify-sketch-geometry-in-fusion-360/)):
- a line-type area (construction, centerline);
- Look At;
- Sketch Grid and Snap;
- Slice;
- Show Profile, Show Points, Show Dimensions, Show Constraints and Show Projected Geometries;
- 3D Sketch;
- a tool-options area that changes with the active tool;
- Finish Sketch.

**The grid and snapping:**
- grid snapping needs **both** Sketch Grid and Snap ticked ([PDO tutorial](https://productdesignonline.com/tips-and-tricks/how-to-use-the-point-command-in-fusion-360/));
- snapping to existing points takes priority over the grid ([Forum](https://forums.autodesk.com/t5/fusion-design-validate-document/sketch-palette-options/td-p/5507033));
- the grid is **adaptive by default**: its spacing changes as you zoom. A Fixed spacing can be set under Grid and Snaps > Grid Settings ([Autodesk support](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/Grid-changes-its-spacing-and-subdivisions-after-zooming-in-out-the-model-in-Fusion-360.html)).

The default state of each palette checkbox is **Unconfirmed**.

**The keys.** Autodesk's shortcut table lists L Line, R 2-Point Rectangle, C Centre Diameter Circle, D Sketch Dimension, X Normal/Construction, T Trim, O Offset and P Project. These are the same on Windows and macOS ([Autodesk](https://www.autodesk.com/shortcuts/fusion-360)). "Auto look at sketch" is on by default ([Autodesk support](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/Auto-look-at-sketch-stops-working-mid-session-in-Fusion-360.html)).

### SciForge's sketch scorecard

Three parts of FreeCAD do the work in this table:
- **SnapManager** decides where the cursor lands. It tries an angle snap first (only while Ctrl is held), then the point or curve under the cursor, then the grid ([SnapManager.cpp](../src/Mod/Sketcher/Gui/SnapManager.cpp)).
- **seekAutoConstraint** suggests constraints: Coincident, Point-on-curve, Symmetric (FreeCAD's way of recording a midpoint), Tangent to circles, arcs and ellipses, and H/V within a **fixed 2°** ([DrawSketchHandler.cpp](../src/Mod/Sketcher/Gui/DrawSketchHandler.cpp)). It has **no Parallel or Perpendicular inference at all**.
- **The suggestion icons** are 16-pixel FreeCAD images joined onto the mouse cursor. They are not drawn in the scene.

SciForge already sets Fusion-like colours, a quiet grid, the palette and Fusion's keys. Its L tool chains lines, takes typed length and angle ("type 50, Tab, 30, Enter, which also adds the dimension"), and Enter finishes ([sketch_mode.py](../src/Mod/SciForge/sciforge/sketch_mode.py); [sketch_line.py](../src/Mod/SciForge/sciforge/sketch_line.py)).

| Fusion behaviour | Evidence | FreeCAD / SciForge today (Source code) | Gap | Most direct route |
|---|---|---|---|---|
| Snap to endpoints, centres, curves, origin, projected geometry | Autodesk, Forum | Snaps to the point or curve under the cursor and to the H/V axes. How close you must be is set by `PickRadius` (5 px). | Fusion's distance is unknown | Python setting (`PickRadius`) once measured |
| Midpoint snap and a Midpoint constraint; Shift forces it | Autodesk | Pulled to the midpoint within 5% of the length, stored as Symmetric. No Shift. | Shift, glyph look | C++ (SnapManager), small |
| Intersection snap | Forum (unreliable in Fusion) | None | None needed for parity | Leave out |
| Hover to acquire (last 3 points + current command), dashed guides, snap to another point's X or Y | Forum (old) | Nothing | **Missing** | C++: new alignment step in `SnapManager::snap()`, dashed lines drawn by `EditModeCoinManager` |
| H/V inference with a glyph beside the line | Autodesk | Fixed 2°, icon on the cursor | Tolerance not adjustable, icon in the wrong place | C++: make the tolerance a parameter, draw the glyph in the scene |
| Perpendicular to a touching line (beat H/V in 2015) | Forum (old) | None | **Missing** | C++: `seekAutoConstraint` |
| Parallel to other lines | Unconfirmed | None | Unknown | Wait for a Fusion check |
| Press-and-drag from the endpoint gives a tangent arc | Autodesk | Line→arc tangency is inferred, but L has no drag gesture | **Missing** | Python inside `sketch_line.py` (SciForge already drives the chain; untested idea), else C++ |
| Ctrl = no snaps and no constraints | Autodesk staff, tutorial | Ctrl = 5° angle snap | **Opposite** | C++, small; Python toggle as a stopgap (untested) |
| Blue/black/orange/green/purple colours, light-blue profiles | Autodesk | Blue, white, orange and purple set by SciForge; profiles shaded light blue | Fixed-green and the browser lock badge unchecked | Python settings |
| Temporary glyph colour and position | Unconfirmed (cyan vs blue) | FreeCAD icons on the cursor | Look and position | C++ scene glyphs. Swapping the icons from Python is unverified. |
| Length/angle boxes, Tab, typed values become dimensions | Tutorial, Autodesk | OVP "Dimensions only" (default 1); SciForge L adds the dimension | Lock icon look | Already close |
| Line chain, Enter, Esc, double-click, close on the start point | Autodesk, tutorial | Chain plus Enter in SciForge | Double-click behaviour not verified | Check, then Python |
| Sketch Palette | Autodesk | Done in SciForge (grid, snap, slice, profile, points, dimensions, constraints, projected, construction, Look At) | 3D Sketch, centerline, per-tool options | Python |
| Adaptive grid; grid snap only with Grid + Snap | Autodesk, tutorial | `GridAuto` adaptive; FreeCAD snaps to the grid even when it is hidden | Small | Python |
| L R C D X T O P keys | Autodesk | Done in SciForge | None | None |

**Recommended route for sketching.** Make **one coherent C++ "inference" patch in `src/Mod/Sketcher/Gui/`**, which the spec explicitly allows ("fork the Sketcher", [feature-outline.md](../docs/sciforge/feature-outline.md)). It would:
1. add an alignment step to `SnapManager::snap()` with a new snap type, keep a short list of recently hovered points, and change what Ctrl and Shift do;
2. extend `seekAutoConstraint()` with Perpendicular, plus Parallel if a Fusion check confirms it;
3. turn the hard-coded 2°, 5% and tangent tolerances into parameters;
4. draw dashed guides and scene glyphs through `EditModeCoinManager`, which already supports dashed line patterns ([EditModeCoinManager.cpp](../src/Mod/Sketcher/Gui/EditModeCoinManager.cpp)).

A Python-only version cannot be made reliable. FreeCAD decides the snapped point in C++ before SciForge sees it, so a guide drawn in Python and the point FreeCAD actually uses could disagree ([ViewProviderSketch.cpp](../src/Mod/Sketcher/Gui/ViewProviderSketch.cpp)). Everything the copy uses must also be SciForge's own: icons, colours chosen by SciForge, and wording.

## FreeCAD's NaviCube already has Fusion's 26 click targets, but not its drag or Home

### What Fusion's ViewCube does

Autodesk's reference page confirms the core behaviour ([Autodesk help](https://help.autodesk.com/cloudhelp/ENU/Fusion-GetStarted/files/GS-VIEWCUBE.htm)):
- the ViewCube sits in a corner of the canvas;
- clicking a named face gives that orthographic view, and clicking a corner gives an isometric view;
- **dragging the cube orbits the design**;
- right-clicking opens a menu.

Edges give a view halfway between two faces, so there are **26 targets: 6 faces, 12 edges and 8 corners** ([Autodesk ViewCube patent](https://patents.google.com/patent/US7782319B2/en)). Autodesk's 2008 study found **dragging the cube almost twice as fast as clicking its parts** ([Autodesk Research](https://research.autodesk.com/publications/viewcube-a-3d-orientation-indicator-and-controller)). That is a good reason to treat drag-to-orbit as essential, not optional.

**Home icon and menu.** A house icon sits above the cube and returns to the Home view. The right-click menu offers ([Autodesk help](https://help.autodesk.com/cloudhelp/ENU/Fusion-GetStarted/files/GS-VIEWCUBE.htm); [Autodesk support](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/How-to-change-the-default-position-for-Home-view-in-Fusion-360.html)):
- Go Home;
- a Camera submenu: Orthographic, Perspective, or Perspective with Ortho Faces. It is shared with the navigation bar's Display Settings.
- Set current view as Home, with Fit to View or Fixed Distance;
- Reset Home;
- "Set current view as [Face]" and "Reset [Face]", where [Face] is the face currently toward you.

**Fixed details:**
- Fusion's **cube cannot be resized** ([Autodesk support](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/Is-it-possible-to-resize-the-Viewcube-in-Fusion-360.html));
- it carries an **X/Y/Z triad with letters, red/green/blue** ([Autodesk support](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/Is-it-possible-to-place-the-letter-X-Y-Z-on-the-origin-axes-as-is-shown-in-the-View-Cube.html));
- an "Animate view transitions" preference switches the camera animation off ([Autodesk help](https://help.autodesk.com/view/fusion360/ENU/?guid=GUID-878489CD-3A23-4303-8450-C2F4F8E410B1));
- Ctrl+Alt+V shows or hides the cube on Windows ([Autodesk](https://www.autodesk.com/shortcuts/fusion-360)).

**Orientation.** **New designs are Z-up by default.** Y-up remains an option that affects only new designs ([Autodesk support](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/How-to-change-the-orientation-of-the-origin-planes-in-Fusion-360.html)). In Z-up, the Front face looks at the XZ plane ([Forum](https://forums.autodesk.com/t5/fusion-support/sketch-on-xz-plane-shows-z-positive-downwards-left-handed-coord/td-p/11675127)).

**Unconfirmed for Fusion specifically:**
- The four small triangles around a face-on view (step to the neighbouring face) and the two curved arrows (turn the view 90°). These are documented for Inventor ([Autodesk Inventor help](https://help.autodesk.com/cloudhelp/2026/ENU/Inventor-Help/files/GUID-94F44C80-7313-4529-85D1-E64ABF732700.htm)) and appear in the 2008 paper's figure ([Semantic Scholar](https://www.semanticscholar.org/paper/ViewCube:-a-3D-orientation-indicator-and-controller-Khan-Mordatch/db6644bab70a371cfb4dae856c5840ec56cb7b76/figure/7)), but no Fusion page confirms them.
- Snapping to the nearest standard view when a drag ends. The patent describes it, and AutoCAD exposes it as an option ([Autodesk AutoCAD help](https://help.autodesk.com/cloudhelp/2016/ENU/AutoCAD-Core/files/GUID-78043EE2-114B-4F08-BFD7-7E5E429708A9.htm)).
- The hover colour, the transparency when idle, label orientation and where the triad sits.
- The default Home corner. One forum post claims "Top, Right and Back" for Z-up, which is surprising ([Forum](https://forums.autodesk.com/t5/fusion-design-validate-document/view-cube-home-position/td-p/5453761)).

### SciForge's ViewCube scorecard

FreeCAD's NaviCube is a single C++ file ([NaviCube.cpp](../src/Gui/NaviCube.cpp), Source code). It draws:
- a chamfered cube with 6 face, 12 edge and 8 corner targets;
- four triangle arrows that turn **45° per click** by default (`NaviStepByTurn = 8`);
- two roll arrows, a "back side" dot and a menu icon;
- a coloured axis tripod.

It sits at 50% opacity when the pointer is away. Clicks animate over 500 ms. FreeCAD's Front view already matches Fusion's Z-up convention: the camera looks from −Y toward +Y with Z up. However, **dragging the cube moves the widget** (and only when "Movable" is ticked), and there is **no Home button**. FreeCAD's separate Home command restores a default "Top" view and then fits ([CommandView.cpp](../src/Gui/CommandView.cpp)). SciForge currently sets only the cube's colours: a light face, dark labels and a blue hover ([theme.py](../src/Mod/SciForge/sciforge/theme.py)).

| Feature | Fusion (evidence) | FreeCAD / SciForge today | Most direct route |
|---|---|---|---|
| 26 click targets, animated view change | Autodesk | Present | None |
| Face-on triangles step 90° | Unconfirmed | Arrows step 45° | Python setting `NaviStepByTurn = 4` |
| Curved roll arrows | Unconfirmed | Present | None |
| Back-side dot | Not in Fusion's documented set | Present | C++ to remove it, or leave it |
| **Drag the cube to orbit** | Autodesk | Drag moves the widget | **C++ patch in `NaviCube.cpp`**, reusing the turntable orbit |
| **Home icon**; set and reset Home (Fit to View / Fixed Distance), stored per design | Autodesk | None (command only, Top + fit) | C++ button in the same patch, or a small Python widget beside the cube; Home stored in the document from Python |
| Fusion's right-click menu | Autodesk | Different FreeCAD menu | Python: edit the `NaviCube_Menu` QMenu of each 3D view |
| Set current view as Front/Top, Reset | Autodesk | None | C++ or overlay; low priority |
| Perspective with Ortho Faces | Autodesk | Only ortho or perspective | Python: switch the camera type when a face is aligned (untested design) |
| Fixed size, X/Y/Z lettered triad | Autodesk | `CubeSize` 132 px, tripod `ShowCS` on | Python settings; compare the tripod with Fusion |
| Idle transparency, hover colour | Unconfirmed | 50%, SciForge blue `#6fb7f0` | Python settings after a check |
| Animate view transitions on/off | Autodesk | `UseNavigationAnimations`, 500 ms | Python setting |
| Show/hide with Ctrl+Alt+V | Autodesk | `ShowNaviCube` parameter | Python command plus shortcut |
| Z-up, Front = XZ | Autodesk, Forum | Same | None; Y-up would need C++ |

**Recommended route for the ViewCube:**
1. **Now, in Python:** set `NaviStepByTurn = 4`, keep `ChamferSize` around 0.06–0.10 (zero is untested and would make edges and corners unclickable), lower `BorderWidth`, and turn `NaviRotateToNearest` off so clicks land upright. Then rebuild the right-click menu in SciForge's own wording.
2. **Next, a one-file C++ patch** for drag-to-orbit and the Home icon. The cube receives mouse events before the navigation style does ([View3DInventorViewer.cpp](../src/Gui/View3DInventorViewer.cpp)), so the drag belongs in the cube. Calling the same turntable code as Shift+middle-drag makes the two feel identical.

The alternative is a full Python replacement: hide the cube, paint a new one with Qt and call `view.setCameraOrientation()`. It is worth choosing only if SciForge wants a visibly different cube without rebuilds, because it means re-implementing click detection and the drag ([NaviCube.cpp](../src/Gui/NaviCube.cpp)).

## The tipping orbit is FreeCAD's trackball default, and one setting fixes it

### Fusion's mouse and its two orbit modes

Autodesk confirms Fusion's default mouse ([Autodesk blog, 2026](https://www.autodesk.com/products/fusion-360/blog/understanding-navigation-and-preferences-in-autodesk-fusion/); [Autodesk help](https://help.autodesk.com/view/fusion360/ENU/?guid=GUID-878489CD-3A23-4303-8450-C2F4F8E410B1)):
- **middle-drag pans**;
- **Shift + middle-drag orbits**;
- the wheel zooms;
- Ctrl+Shift + middle-drag zooms continuously;
- double-clicking the wheel fits the view.

A preference offers six presets: Fusion, Alias, Inventor, SolidWorks, Tinkercad and PowerMill ([Autodesk blog](https://www.autodesk.com/products/fusion-360/blog/quick-tip-pan-zoom-orbit-preferences/)).

Fusion's API names **exactly two orbit modes, Constrained and Free** ([Autodesk API](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/DefaultOrbits.htm)). Autodesk's description, quoted on the forum, is that Constrained Orbit "will now rotate only about the Top/Bottom axis of the ViewCube, attempting to keep the Top of the ViewCube upright", while Free Orbit "allows your model to tumble in any orientation" ([Forum](https://forums.autodesk.com/t5/fusion-design-validate-document/orbit-how-does-it-really-work/td-p/6884264)). An Autodesk University tip says the same ([Autodesk University](https://www.autodesk.com/autodesk-university/article/11-Fusion-360-Tips-Tricks-2019)). Older builds chose whichever origin axis was nearest screen-up when the orbit started. Later builds always use the ViewCube's Top/Bottom axis ([Forum, 2025](https://forums.autodesk.com/t5/fusion-design-validate-document/constrained-vs-free-orbit/td-p/13689573)).

In plain words, **Constrained Orbit is a turntable**: left-right drags spin the model about the "up" axis, up-down drags tilt it toward you, and it never rolls. That is why vertical edges stay vertical ([Blender manual](https://docs.blender.org/manual/en/latest/editors/preferences/navigation.html); [Matt Keeter](https://www.mattkeeter.com/projects/rotation/)).

Two things are **Unconfirmed**:
- Which mode a fresh install uses. One forum report has the setting reverting to Free ([Forum, 2019](https://forums.autodesk.com/t5/fusion-support-forum/default-orbit-type-always-resets-to-free-orbit/td-p/8637905)), another has it switching to Constrained ([Forum, 2025](https://forums.autodesk.com/t5/fusion-support-forum/i-set-the-default-orbit-type-in-the-preferences-but-it-suddenly/td-p/13659435)).
- Whether constrained orbit stops at straight-down or lets you go over the top.

The orbit type is chosen in Preferences and in the navigation bar's Orbit dropdown, and the two are linked ([Forum](https://forums.autodesk.com/t5/fusion-support-forum/default-orbit-type-always-resets-to-free-orbit/td-p/8637905)).

### Why SciForge tips, and the fix

SciForge already copies Fusion's mouse layout by selecting FreeCAD's "Revit" style: middle pans and Shift+middle orbits ([theme.py](../src/Mod/SciForge/sciforge/theme.py); [RevitNavigationStyle.cpp](../src/Gui/Navigation/RevitNavigationStyle.cpp)). But it never sets *how* the orbit turns. It therefore inherits FreeCAD 1.1.4's default `OrbitStyle = 4`, "Rounded Arcball", a trackball variant whose own tooltip says "moving the mouse in the corners of the screen will only roll the part" ([DlgSettingsNavigation.ui](../src/Gui/PreferencePages/DlgSettingsNavigation.ui); [View3DSettings.cpp](../src/Gui/View3DSettings.cpp)). FreeCAD 1.0 defaulted to plain Trackball, which also rolls. The switch to Rounded Arcball came in a May 2025 commit (3fcadd01f5 in this repo's history). **That roll is the "off axis" tip the owner sees.**

FreeCAD's turntable code rotates about **world Z** for horizontal drags and about the **screen's horizontal axis** for vertical drags, so it cannot roll ([NavigationStyle.cpp](../src/Gui/Navigation/NavigationStyle.cpp)). Two of its styles use this code, and they differ:
- **Turntable (0)** applies only the bigger of the two mouse directions each time the mouse moves, so diagonal drags feel stepped.
- **Free Turntable (2)** applies both directions every time.

Beware the name: FreeCAD's "Free Turntable" is Fusion's *Constrained* Orbit. FreeCAD's Trackball (1) or Trackball Classic (3) is the nearest match to Fusion's *Free* Orbit.

**The fix is a Python setting.** Add `(View group, "Int", "OrbitStyle", 2)` to `VIEWER_SETTINGS` in `theme.py`, after the `NavigationStyle` line. Order matters: switching style creates a new style object that re-reads the other values. FreeCAD applies the change live to every open view, and SciForge's theme already restores old values when it is switched off ([View3DSettings.cpp](../src/Gui/View3DSettings.cpp); [theme.py](../src/Mod/SciForge/sciforge/theme.py)). A navigation-bar Orbit dropdown offering Constrained and Free can write the same parameter, 2 or 1, matching Fusion's linked dropdown. The turntable axis is hard-wired to Z, which is correct for Fusion's Z-up default. Y-up would need a C++ change.

### Pivot, zoom and the mouse details that still differ

**Fusion's pivot rule** (Autodesk) ([Autodesk support](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/How-to-reset-the-orbit-pivot-point-in-Fusion-360.html); [Autodesk support](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/Fusion-360-fails-to-orbit-around-selected-point.html)):
- it orbits about the **centre of the design's bounding box when the whole model is on screen**;
- otherwise it orbits about the point nearest the camera;
- you can set a pivot with right-click > Set Orbit Center;
- Shift + a single middle-click on the model places a **green dot** that becomes the new pivot ([Forum](https://forums.autodesk.com/t5/fusion-support-forum/set-orbit-center-amp-model-views/td-p/8578945));
- one forum reply contradicts the off-screen rule ([Forum](https://forums.autodesk.com/t5/fusion-design-validate-document/when-rotating-the-view-how-is-the-center-of-rotation-determined/td-p/12565830)).

**FreeCAD's pivot modes** (`RotationMode`):
- window centre (0), which is SciForge's current behaviour;
- the model point under the cursor (1);
- the point under the cursor, else the bounding-box centre (2).

None of these matches Fusion's rule exactly, and FreeCAD's pivot marker is red by default ([NavigationStyle.cpp](../src/Gui/Navigation/NavigationStyle.cpp); [View3DInventorViewer.cpp](../src/Gui/View3DInventorViewer.cpp)). Keep mode 0 for now: after a Fit, the window centre is the model centre. Set `RotationCenterColor` to green from Python. Fusion's exact rule and Set Orbit Center need C++, because FreeCAD's function for setting the pivot has no Python binding.

**Mouse-mapping differences.** Reading the Revit style's source shows two gaps ([RevitNavigationStyle.cpp](../src/Gui/Navigation/RevitNavigationStyle.cpp)):
- **Ctrl+Shift+middle-drag does nothing** there. Zoom-drag is Ctrl+middle or Ctrl+Shift+right instead.
- **A quick middle click re-centres the view on the clicked point.** In Fusion, a double middle click fits and Shift+middle click sets the pivot.

The most direct fix for all of these, together with the pivot rule, is a **small new C++ "Fusion" navigation style**, copied from the Revit style. That is cleaner than bending Revit's.

**Zoom and the remaining pieces:**
- **Zoom to the cursor**: Fusion zooms toward the cursor ([Forum](https://forums.autodesk.com/t5/fusion-design-validate-document/is-it-possible-to-zoom-to-mouse-cursor/td-p/7957949)), and SciForge already turns this on.
- **Wheel direction**: Fusion's default (which way is "in") is **Unconfirmed**. FreeCAD's `InvertZoom` defaults to true. A side-by-side check decides the setting.
- **Trackpad gestures**: Fusion supports two-finger pan, pinch zoom and Shift + two-finger orbit, on Mac for years and on Windows since the **September 2026** update ([Autodesk blog](https://www.autodesk.com/products/fusion-360/blog/september-2026-major-product-update-whats-new/); [Forum](https://forums.autodesk.com/t5/fusion-support-forum/macbook-trackpad-behavior-zoom-orbit-pan-randomly-changes-while/td-p/8863917)).
- **Camera modes**: Fusion has three ([Forum, Autodesk staff](https://forums.autodesk.com/t5/fusion-design-validate-document/default-camera-view-keeps-switching-to-quot-perspective-quot/td-p/12414138)). SciForge's navigation bar offers two.
- **Navigation bar**: SciForge's Orbit button is only a tooltip, and its Grid and Snaps and Viewports buttons have no command yet ([ribbon_config.py](../src/Mod/SciForge/sciforge/ribbon_config.py)).

| Behaviour | Fusion (evidence) | SciForge today (Source code) | Most direct route |
|---|---|---|---|
| Middle pans, Shift+middle orbits, wheel zooms | Autodesk | Yes (Revit style) | None |
| **Stable orbit (Constrained)** | Autodesk | **Rolls (Rounded Arcball)** | **Python setting `OrbitStyle = 2`** |
| Free orbit available; Orbit dropdown | Autodesk, Forum | No dropdown | Python (write `OrbitStyle` 1 or 2) |
| Pivot: bounding-box centre when whole model visible | Autodesk | Window centre | Keep 0; exact rule in C++ |
| Set / Reset Orbit Center; Shift+middle click pivot; green dot | Autodesk, Forum | None; red marker | Colour: Python. The rest: C++ |
| Ctrl+Shift+middle-drag zoom | Autodesk | Not mapped | C++ (Fusion style) |
| Double middle click = Fit | Autodesk | Middle click re-centres | C++ (Fusion style) |
| Zoom toward the cursor | Forum | Yes | None |
| Wheel direction, Reverse zoom option | Autodesk (option); default Unconfirmed | `InvertZoom` true | Python after a check |
| Three camera modes | Autodesk | Two | Python (Ortho Faces logic) |
| Over-the-top behaviour | Unconfirmed | FreeCAD turntable allows it | Check, then C++ if a clamp is needed |
| Y-up designs | Autodesk (option) | Z hard-wired | C++ if ever needed |

## Components, joints and selection matter more than polish for a robot builder

Outside the three focus areas, the largest gap is how Fusion organises a project. **Fusion keeps many components in one design.** A component owns bodies, sketches and construction geometry, and joints can only connect components ([Fab Academy notes](https://fabacademy.org/2026/labs/kochi/students/merin-cyriac/Assignments/Week_02/Fusion.html)). Activating a component only decides who owns new items: a hole cut while one component is active can still cut through others ([Forum, Autodesk employee](https://forums.autodesk.com/t5/fusion-design-validate-document/activate-component-what-is-it-used-for-and-perhaps-a-better/m-p/5696860)). Insert into Current Design links in another design, and Break Link makes it local ([Autodesk blog](https://www.autodesk.com/products/fusion-360/blog/fusion-files-links-components/)). FreeCAD 1.1.4 puts assemblies in a separate Assembly workbench whose Insert Component needs the other file open ([CommandInsertLink.py](../src/Mod/Assembly/CommandInsertLink.py)). SciForge's notes still list New Component as an open gap ([MEMORY.md](../MEMORY.md)).

**Joints.** Fusion has seven joint types: Rigid, Revolute, Slider, Cylindrical, Pin-slot, Planar and Ball ([Autodesk API](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/JointTypes.htm)). They are placed by **picking a snap point on each component, with the first moving to the second** ([Autodesk help](https://help.autodesk.com/cloudhelp/ENU/Fusion-Assemble/files/ASM-CREATE-JOINT.htm)). Around them sit:
- as-built joints ([Autodesk help](https://help.autodesk.com/cloudhelp/ENU/Fusion-Assemble/files/ASM-CREATE-AS-BUILT-JOINT.htm));
- motion limits and motion links ([Autodesk Learn](https://www.autodesk.com/learn/ondemand/tutorial/create-realistic-motion-in-assemblies));
- Capture/Revert Position ([Autodesk help](https://help.autodesk.com/cloudhelp/ENU/Fusion-Assemble/files/ASM-CAPTURE-POSITION.htm)).

FreeCAD's solver already does Fixed, Revolute, Cylindrical, Slider and Ball joints, with limits, grounding and simulation, but it has no Pin-slot joint ([JointObject.py](../src/Mod/Assembly/JointObject.py)). The work is therefore mostly Fusion-style picking on top of FreeCAD's Ondsel solver ([Ondsel](https://www.ondsel.com/blog/assembly-workbench-preview/)).

**Selection** belongs with the navigation work, because the spec makes "navigation and selection parity" part of the Phase 1 exit ([feature-outline.md](../docs/sciforge/feature-outline.md)). Fusion's habits:
- dragging left-to-right selects only what is fully inside the box; right-to-left selects anything touched ([Autodesk blog](https://www.autodesk.com/products/fusion-360/blog/tip-tuesday-3-ways-to-select-an-area-in-fusion-360/));
- Ctrl toggles items in and out, Shift only adds ([Autodesk help](https://help.autodesk.com/cloudhelp/ENU/Fusion-Model/files/SLD-SELECTION.htm));
- **clicking and holding for about a second opens "Select Other"**, with Depth and Parents tabs ([Autodesk help](https://help.autodesk.com/cloudhelp/ENU/Fusion-Model/files/SLD-SELECT-OBJECTS.htm));
- there are filters, including Select Through ([Autodesk help](https://help.autodesk.com/cloudhelp/ENU/Fusion-Model/files/SLD-SELECTION-FILTERS.htm)), and priority presets ([Autodesk help](https://help.autodesk.com/cloudhelp/ENU/Fusion-Model/files/SLD-SELECTION-PRIORITY-FILTERS.htm)).

FreeCAD has Clarify Selection (G, G) and separate box-selection modes ([CommandView.cpp](../src/Gui/CommandView.cpp)), but none of these Fusion habits.

The remaining items are smaller:
- **Files and versions.** Fusion makes a new version on every save ([Forum](https://forums.autodesk.com/t5/fusion-support-forum/trick-to-save-design-without-advancing-version-number/m-p/7482769)). FreeCAD autosaves every 15 minutes and keeps one backup, with no history ([StartupProcess.cpp](../src/Gui/StartupProcess.cpp)).
- **Mesh import.** Fusion converts meshes to solids (Faceted or Prismatic) ([Autodesk help](https://help.autodesk.com/cloudhelp/ENU/Fusion-Mesh/files/MESH-CONVERT-TO-SOLID.htm)), up to roughly 10,000 elements ([Autodesk support](https://autodesk.com/support/technical/article/How-to-insert-a-mesh-body-into-Fusion-360)).
- **Canvas.** Fusion calibrates an image canvas with two points and a known distance ([Autodesk help](https://help.autodesk.com/cloudhelp/ENU/Fusion-Model/files/SLD-SCALE-CANVAS.htm)).
- **Sketch Text.** Fusion has Sketch Text with Text on Path for embossed labels ([Autodesk help](https://help.autodesk.com/cloudhelp/ENU/Fusion-Sketch/files/SKT-SKETCH-CREATE-TEXT.htm)). FreeCAD has no sketch text tool, only Draft ShapeString.
- **Compute All.** Ctrl+B recomputes everything and flags failing features ([Autodesk help](https://help.autodesk.com/cloudhelp/ENU/Fusion-Model/files/SLD-COMPUTE-ALL.htm)).

SciForge has already covered several of the rest: Physical Material with mass, Delete Face, Measure, Section Analysis and Centre of Mass ([MEMORY.md](../MEMORY.md)).

| Priority for robots and 3D printing | Fusion behaviour | FreeCAD 1.1.4 / SciForge | Route |
|---|---|---|---|
| 1. Components + active component | One design, many components; activation sets the owner | Separate Assembly workbench; New Component open | Python: component = Part + Body, with an active marker |
| 2. Joints with two-click picking | 7 types, snap points, as-built, limits, Capture Position | Solver has 5 of the 7 basic types plus limits; no Pin-slot | Python UX over the Ondsel solver |
| 3. Selection habits | Window vs crossing by drag direction, Select Other, filters | Clarify Selection, box modes | Python (click-and-hold opens Clarify Selection's picker) |
| 4. Versions and recovery | Version on every save | 15-minute autosave, 1 backup | Python version browser (spec: git) |
| 5. Import vendor parts and meshes | STEP into a component, mesh to solid, calibrated canvas | Formats present, workflows clunky | Python |
| 6. Sketch Text + Emboss | Text and Text on Path | No sketch text | Python or C++ |
| Later | Drawings, surface tools, decals, contact sets | TechDraw and Surface exist | Thin wrappers |

## Order the work from one-line settings to one bundled C++ build

Each C++ patch needs a full build of SciForge on the owner's Windows machine, while Python changes ship as quick updates ([MEMORY.md](../MEMORY.md)). So the cheapest plan does all the Python first, then **bundles the three C++ patches (navigation style, NaviCube, Sketcher) into a single full build**, after the Fusion checks below have settled their numbers.

| Step | Work | Route | Delivery | Needs a Fusion check first? |
|---|---|---|---|---|
| 1 | `OrbitStyle = 2`, green pivot dot, `NaviStepByTurn = 4`, cube chamfer and border | Python settings | Quick update | No |
| 2 | ViewCube menu in SciForge's words, per-design Home, Ctrl+Alt+V, Orbit dropdown, Perspective with Ortho Faces | Python | Quick update | Partly (menu contents) |
| 3 | Ctrl stopgap in sketches; tangent-arc drag in L | Python (untested) | Quick update | Yes (Ctrl timing) |
| 4 | Fusion navigation style: Ctrl+Shift+middle zoom, double-click fit, Shift-click pivot, pivot rule, Set/Reset Orbit Center | C++ | Full build | Yes (pivot, wheel) |
| 5 | NaviCube drag-to-orbit, Home icon, drop the back-side dot | C++, one file | Same full build | Yes (snap on release) |
| 6 | Sketcher inference patch (guides, perpendicular, Ctrl/Shift, tolerances, scene glyphs) | C++ | Same full build | Yes (most items) |
| 7 | Selection parity, then components, then joints | Python, mostly | Quick updates | Some |

## Ten things to check in Fusion before coding the details

These checks are black-box observation, which the spec allows. Nothing from the screenshots is copied into SciForge as an asset. Short screen recordings are better than stills for anything that moves.

| # | What to do in Fusion | What to send | What it decides |
|---|---|---|---|
| 1 | Preferences > General: note the orbit type selected. Then Shift+middle-drag a box upward past the top view. | Screenshot of the preference, short video | Constrained vs Free default; whether the orbit stops or goes over the top |
| 2 | With the whole part visible, put the cursor on a far corner and orbit. Then zoom in so the part fills the screen and orbit again. Try a Shift + single middle click. | Video showing the green dot | Pivot rule, Set Orbit Center |
| 3 | Double-click the wheel; roll the wheel forward; Ctrl+Shift+middle-drag upward | Note which way each goes | Fit mapping, `InvertZoom`, zoom-drag direction |
| 4 | ViewCube close-ups: idle, hovering a face, an edge and a corner; in the Front view (do triangles or curved arrows appear?); the Home icon; the triad; the right-click menu. Light and dark themes if possible. | Screenshots | Opacity, hover colour, arrows, layout, menu items |
| 5 | Drag the cube and let go near a corner; click a face; click the face already facing you; click Home on a brand-new design | Video | Snap on release, animation time, default Home corner |
| 6 | Draw lines about 1°, 3°, 5° and 8° off horizontal, then open Show Constraints | Screenshots of the glyph while drawing and after | H/V tolerance, glyph colour and position |
| 7 | Hover a line's endpoint, move away sideways and click on the dashed guide. Repeat after hovering four different points. | Screenshot of the guide, constraint list after the click | Guide colour, whether a constraint is added, the "three targets" rule |
| 8 | Draw a line ending on a slanted line at about 90°; a line roughly parallel to a separate line; a vertical line ending on a horizontal line | Screenshots while drawing | Perpendicular and parallel inference, H/V vs perpendicular priority |
| 9 | Hold Ctrl while clicking near an endpoint and while drawing a near-level line; try pressing Ctrl only at the click. Shift-hover a midpoint. | Short video | Exact Ctrl and Shift behaviour |
| 10 | Draw a centre rectangle, inscribed polygon, centre-to-centre slot, centre circle, 3-point arc and fit-point spline. Also screenshot a fresh Sketch Palette and the Grid and Snaps menu. | Screenshots of the boxes while drawing and of the constraints after | Heads-up boxes per tool, built-in constraints, palette defaults |

## Conclusion

The owner's most visible complaint is the cheapest to fix. The tipping is not a FreeCAD bug: it comes from a default that changed to Rounded Arcball in 2025, and SciForge never overrode it. One more line in the theme settings gives Fusion's constrained orbit. The expensive work sits in the sketcher, and its risk is not mainly technical. The C++ entry points are clear and the spec already allows forking the Sketcher. The risk is that the details defining Fusion's "feel" are undocumented: inference tolerances, what a click on a guide adds, perpendicular-versus-H/V priority, glyph colours. Building them from guesses would break the spec's own rule that "close enough is a bug". About thirty minutes of recordings in real Fusion is therefore the critical-path task, not an optional nicety.

Two findings change the plan beyond what either research thread showed alone. First, Ctrl means opposite things in the two programs. Fusion users will trigger FreeCAD's angle snap by reflex until it is fixed, so it belongs in the first sketch release even as a stopgap. Second, the Revit mouse style that SciForge treats as "exactly Fusion" is not exact: Ctrl+Shift+middle zoom, double-click fit and Shift-click pivot all differ. A dedicated Fusion navigation style, built together with the NaviCube and Sketcher patches, turns three separate rebuilds into one.
