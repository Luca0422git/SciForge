# Fusion sketch inference and snapping while drawing (2D sketch)

How these notes were made: every autodesk.com domain was blocked in the research sandbox (help.autodesk.com, forums.autodesk.com and the Fusion blog returned DNS or proxy errors), and so were productdesignonline.com, hackaday.io and web.archive.org. Nothing below comes from reading a page in full. All cited facts come from search-engine result summaries of the pages linked, and those summaries were sometimes garbled. Treat every citation as "the linked page says roughly this" and re-check any load-bearing detail in a real Fusion session or on the live page. Labels used throughout:
- **[OFFICIAL]**: Autodesk help, an Autodesk support article, or the Autodesk Fusion blog.
- **[STAFF]**: an Autodesk employee or moderator posting on the forum.
- **[FORUM]**: a user report on the Autodesk Community forum.
- **[TUTORIAL]**: a third-party tutorial or course (Product Design Online, Lynda/LinkedIn Learning, VDCI and similar).
- **[INFERENCE]**: my own reasoning or a design suggestion for SciForge, not a Fusion fact.

No source I found gives any numeric pixel tolerance, angle tolerance or timing for Fusion's sketch inference.

## 1. Point snaps while drawing: which exist, how they are indicated, and whether hovering "acquires" a point

### Takeaway
While a sketch command is running, Fusion snaps to sketch points and endpoints, curve midpoints (Shift forces this), circle and arc centers, curves themselves (on-curve), the sketch origin and projected geometry. Each snap becomes a constraint (coincident or midpoint) when the click lands. Hovering does "acquire" geometry as an inference target: Fusion keeps the last three hovered entities, plus entities created in the current command, and draws dashed guide lines from them. This works like a reduced version of AutoCAD object snap tracking. Fusion has no reliable intersection snap and, at least historically, no quadrant snap.

### Cited Findings
- [STAFF/FORUM] What other CAD programs call "object snaps" are, in Fusion, sketch constraints applied automatically while sketching. You see them when the cursor nears a circle center or when you draw a horizontal or vertical line. If they do not appear after placement, check "Show Constraints" in the Sketch Palette. Holding Ctrl while picking points stops a constraint from being applied. — [How do I turn object snap on?](https://forums.autodesk.com/t5/fusion-support-forum/how-do-i-turn-object-snap-on/td-p/8898853)
- [OFFICIAL] Midpoint: an Autodesk support article says to "hold down the SHIFT key and hover over the line to be constrained to select the midpoint". — [Unable to constrain to the midpoint of a line in Fusion](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/Unable-to-constrain-to-the-midpoint-of-a-line-in-Fusion-360.html)
- [FORUM] Shift-hover finds the midpoint only while a command (for example Line) is active. — [Holding shift and hovering over a line does not bring up midpoint snap](https://forums.autodesk.com/t5/fusion-support-forum/holding-shift-and-hovering-over-a-line-does-not-bring-up/td-p/11900143)
- [FORUM] Without Shift, passing the cursor over a line's midpoint while sketching also shows the midpoint snap. — [Snap to midpoint functionality](https://forums.autodesk.com/t5/fusion-design-validate-document/snap-to-midpoint-functionality/td-p/6662693)
- [OFFICIAL blog] The midpoint constraint is shown as a triangle icon. A quick tip says you know you have hit the midpoint when you see "a triangle with an X". — [Master Midpoint Constraints (Fusion Blog)](https://www.autodesk.com/products/fusion-360/blog/mastering-midpoint-constraints-autodesk-fusion/); [QUICK TIP: Midpoint Constraint Shortcut](https://www.autodesk.com/products/fusion-360/blog/quick-tip-midpoint-constraint-shortcut/)
- [TUTORIAL] Starting a line on an existing sketch point automatically adds a Coincident constraint. — [PDO Learn Fusion in 30 Days 2026, Day 4](https://productdesignonline.com/learn-autodesk-fusion-in-30-days-2026-day-4/)
- [TUTORIAL] Coincident ("alignment") constraints are applied automatically where line segments and curves connect. — [Fusion 360 Sketch Constraints (nakayasu lecture notes)](https://lecture.nakayasu.com/en/docs/fusion360/fusion360-sketch-constraints/)
- [FORUM] **Acquisition and inference targets.** Existing sketch geometry has to be hovered before it becomes an inference target. Lines created during the current command are added automatically. Fusion keeps at most three geometries as targets, and hovering a fourth drops the first, which limits unnecessary inferences. To get a dropped target's inference back, hover it again. Example given: start a line on one line's midpoint, move to the vertical line's center, then move away, and a green dashed guide appears. The post is about 10 years old. — [Snap to center question](https://forums.autodesk.com/t5/fusion-360-design-validate/snap-to-center-question/td-p/5992547)
- [FORUM] Hovering the sketch Origin and then moving toward the target point gives a blue dotted constraint preview, so the origin can be acquired like any other point. — reported in the same search cluster as [Snap to center question](https://forums.autodesk.com/t5/fusion-design-validate-document/snap-to-center-question/td-p/5992547). The exact thread was not confirmed.
- [FORUM] Intersections are unreliable. Users report Fusion "intermittently not recognizing the intersection" of curves, and the usual workaround is to place a sketch point at the crossing, use Break to create snappable points, or Project/Intersect from another sketch. — [Snap point at the intersection of two construction lines](https://forums.autodesk.com/t5/fusion-design-validate-document/snap-point-at-the-intersection-of-two-construction-lines/td-p/6847042); [Circle will not snap to intersection of two construction lines when moved](https://forums.autodesk.com/t5/fusion-design-validate-document/circle-will-not-snap-to-intersection-of-two-construction-lines/td-p/7421590)
- [FORUM] A user reply (about 2019) said Autodesk had "no plans to create a sketch 'object snap' functionality similar to AutoCAD". Other users noted that midpoint snap had already been implemented but quadrant snap was still missing. — [Snapping, center point, end point, etc.](https://forums.autodesk.com/t5/fusion-support-forum/snapping-center-point-end-point-etc/td-p/8934886); [object snaps](https://forums.autodesk.com/t5/fusion-design-validate-document/object-snaps/td-p/6352184); [Idea: Include better snapping features in sketching](https://forums.autodesk.com/t5/fusion-360-ideastation-archived/include-better-snapping-features-in-sketching/idi-p/7561367)
- [OFFICIAL/TUTORIAL] Projected geometry: a sketch can snap only to geometry that is in the sketch, either drawn there or projected in. The preference "Auto project edges on reference" (Preferences > General > Design) projects a body edge automatically when you reference it while drawing. It only works when you view the sketch straight on, to prevent accidental projections at an angle. It used to be on by default, and a later comment says it no longer is. A second preference, "Auto project geometry on active sketch planes", also exists. — [PDO Knowledge: Can't snap to edge of body](https://knowledge.productdesignonline.com/article/50-day-5-cant-snap-to-edge-of-body-in-fusion-360); [Auto project preferences](https://forums.autodesk.com/t5/fusion-design-validate-document/auto-project-preferences/td-p/6836409); [Project and include geometry in sketches (Fusion Help)](https://help.autodesk.com/cloudhelp/ENU/Fusion-Sketch/files/SKT-SKETCH-CREATE-PROJECT-INCLUDE.htm)
- [FORUM] If you delete entities with a window selection, you can also delete the projected reference geometry, and then you have to project it again before you can snap to it. — [Snapping to reference points in sketching breaks](https://forums.autodesk.com/t5/fusion-design-validate-document/snapping-to-reference-points-in-sketching-breaks/m-p/6242419/highlight/true)
- [FORUM] Users report snapping "through" the model to edges and points behind visible bodies. — [Sketch snapping through](https://forums.autodesk.com/t5/fusion-design-validate-document/sketch-snapping-through-snapping-to-objects-edges-points-behind/td-p/10792909)
- [OFFICIAL, other workspaces] Fusion's **Drawing** workspace has its own object-snap system, with snap symbols near the cursor (vertices, edge and face centers, sketch points). In **Measure**, holding Ctrl locks to snap points and holding Shift hides them. Neither is the sketch inference system, but both show that Autodesk uses Ctrl and Shift as snap modifiers elsewhere in the product. — [Fusion Help: Drawing object snaps](https://help.autodesk.com/view/fusion360/ENU/?contextId=DWG-OBJECT-SNAPS)

### Inferences
- [INFERENCE] The snap model to copy has two parts:
  - a. Direct point snaps under the cursor: endpoints and sketch points, center, midpoint, on-curve, origin, projected points. Each produces a constraint on click: coincident, or midpoint for a midpoint snap.
  - b. A small most-recently-used list of acquired entities: the last 3 hovered, plus everything created in the running command. Their key points produce dashed alignment guides.
- [INFERENCE] Intersection and quadrant snaps are places where SciForge could go beyond Fusion. To stay faithful to Fusion, SciForge would leave them out, or keep them as a pure position snap with no constraint, since Fusion has no single constraint for "on the intersection".

### Gaps
- No source describes the marker shape, color or size used for endpoint, center or on-curve snaps (only the midpoint "triangle with an X" is described). From memory, unverified: the hovered point or curve is highlighted, and a small constraint-style glyph (for example a coincident or midpoint symbol) appears next to the cursor. This needs checking in a live Fusion session.
- No pixel snap radius was found, and nothing on whether the radius scales with display DPI.
- The "three inference targets" rule comes from one forum post about 10 years old. It is not confirmed for 2024 to 2026 builds.
- Whether quadrant points on circles have been added since about 2019 is unconfirmed.

## 2. Horizontal and vertical inference

### Takeaway
When a line being drawn is close to horizontal or vertical, Fusion snaps it to the exact axis direction, shows the horizontal or vertical constraint glyph next to the line while you draw, and applies that constraint when the click lands. No source gives the angle tolerance.

### Cited Findings
- [TUTORIAL] While drawing a line, Fusion shows a horizontal inferred constraint at the bottom of the line. Clicking commits it, and the Horizontal/Vertical constraint is applied. To remove it, select the constraint icon and delete it. — [Lynda: Migrating from AutoCAD to Fusion 360, "Sketch constraints: Horizontal, vertical, collinear"](https://origin-www.lynda.com/Fusion-360-tutorials/Sketch-constraints-Horizontal-vertical-collinear/667363/703400-4.html)
- [OFFICIAL blog] "Fusion will assist by automatically adding constraints like horizontal/vertical alignment" as you sketch. — [Sketch Constraints in Autodesk Fusion Tutorial (Fusion Blog)](https://www.autodesk.com/products/fusion-360/blog/mastering-sketch-constraints-autodesk-fusion-tutorial/)
- [OFFICIAL] A single Horizontal/Vertical constraint snaps a line, or two points, to whichever of the horizontal or vertical axes is closer to its current orientation. Fusion uses one combined H/V constraint, not two separate tools. — [Add a horizontal or vertical constraint (Fusion Help)](https://help.autodesk.com/cloudhelp/ENU/Fusion-Sketch/files/SKT-CONSTRAIN-HORIZONTAL-VERTICAL.htm)
- [TUTORIAL] A horizontal constraint is applied automatically when a line is drawn level, and automatic constraints can be selected and deleted afterwards. — [How to Use the Line Command in Fusion 360 (secrets revealed), PDO](https://productdesignonline.com/tips-and-tricks/how-to-use-the-line-command-in-fusion-360-secrets-revealed/); [PDO 2026 Day 3](https://productdesignonline.com/learn-autodesk-fusion-in-30-days-2026-day-3/)
- [TUTORIAL] In 3D sketching, drawing along an axis also adds a "horizontal/vertical" constraint automatically. — [Introduction to 3D Sketching in Fusion 360, PDO](https://productdesignonline.com/fusion-360-tutorials/introduction-to-3d-sketching-in-fusion-360/)
- [FORUM, 2015] Priority conflict: when a new horizontal or vertical line ends on another horizontal or vertical line, Fusion infers a Perpendicular constraint to that line instead of the H/V constraint. The poster asked for H/V to take precedence. Whether this changed is unknown. — [Idea: Horizontal/Vertical constraints take precedent over perpendicular constraints](https://forums.autodesk.com/t5/fusion-360-ideastation-archived/horizontal-vertical-constraints-take-precedent-over/idi-p/5683627)

### Inferences
- [INFERENCE] Apply H/V to the segment itself, measured in the sketch's own coordinate system, not the screen. Because Fusion has one combined H/V constraint, a single glyph type that is drawn rotated or labeled for each direction is enough.
- [INFERENCE] SciForge has to choose an angle threshold. A few degrees, or an angle derived from a fixed pixel offset at the cursor, would match the feel. This is a design choice, not a Fusion number.

### Gaps
- No angle tolerance was found (for example plus or minus 3 or 5 degrees), and nothing on whether it is computed in degrees or in screen pixels at the cursor.
- The exact appearance of the inferred H/V glyph (a small icon in a box next to the line, as in the permanent glyphs?) is described only as "at the bottom of the line". Its color is disputed (see section 8).

## 3. Perpendicular and parallel inference relative to other lines

### Takeaway
Fusion does infer Perpendicular. The documented case is a new line that ends on, or connects to, another line. In at least the older behavior, perpendicular even took precedence over H/V. I found no source confirming that Fusion infers **Parallel** to an arbitrary non-touching line while you draw, or describing a highlight on the reference line for perpendicular or parallel.

### Cited Findings
- [FORUM, 2015] A new line drawn horizontal or vertical that lands on another H/V line receives a Perpendicular constraint, not H/V. — [Horizontal/Vertical constraints take precedent over perpendicular constraints](https://forums.autodesk.com/t5/fusion-360-ideastation-archived/horizontal-vertical-constraints-take-precedent-over/idi-p/5683627)
- [TUTORIAL] Perpendicular does not require the lines to touch when applied manually, and the glyph appears on only one of the related lines. — [Understanding Sketch Constraints in Fusion 360 (Noble Desktop)](https://blog.nobledesktop.com/learn/cad/understanding-sketch-constraints-in-fusion-360)
- [TUTORIAL] The 3-point rectangle adds Parallel and Perpendicular automatically. This is tool-generated geometry, not inference against existing lines (see section 7). — [How to Use the Rectangle Sketch Command (all 3 explained), PDO](https://productdesignonline.com/tips-and-tricks/how-to-use-the-rectangle-sketch-command-in-fusion-360-all-3-explained/)
- [TUTORIAL] Secondary sources say modern Fusion infers likely constraints as you sketch, such as midpoints and tangencies, but they do not list Parallel. — [Varsity Tutors: Geometric Constraints](https://www.varsitytutors.com/practice/subjects/autodesk-fusion-360/lessons/geometric-constraints) (low-authority source)

### Inferences
- [INFERENCE] Given the three-target rule in section 1, any perpendicular or parallel inference against a non-connected line would likely need that line to be acquired (hovered) first. That is how SolidWorks-style inference usually limits noise. This is unconfirmed for Fusion.
- [INFERENCE] A conservative way to stay faithful: infer Perpendicular to (a) the previous segment in the same Line chain and (b) a line the new segment starts or ends on. Leave Parallel inference out until it is observed in Fusion.

### Gaps
- Whether Fusion shows Parallel inference while drawing: not confirmed by any source.
- Whether the reference line is highlighted during a perpendicular or parallel inference: not described anywhere.
- The precedence order in 2024 to 2026 builds when H/V and Perpendicular both apply: only the 2015 report exists.

## 4. Tangent, collinear, coincident, equal, concentric and midpoint inference

### Takeaway
- **Coincident** and **midpoint** are inferred on click, as point snaps.
- **Tangent** has a dedicated gesture: in the Line tool, press on the endpoint of the last segment and drag to get a tangent arc, which shows a tangent glyph and adds Tangent at its start. Arc and circle tools (tangent arc, 2-tangent circle, 3-tangent circle) add Tangent constraints automatically.
- **Concentric** comes from snapping a new circle's center onto an existing center, which in practice gives Coincident on the center point.
- No source describes automatic Collinear or Equal inference.

### Cited Findings
- [OFFICIAL blog] Tangent arc from the Line tool: go back to the endpoint, click and drag with the left button held, and a tangent arc is created. Release, then click to continue the line chain. — [QUICK TIP: Sketching Tangent Arcs (Fusion Blog)](https://www.autodesk.com/products/fusion-360/blog/quick-tip-sketching-tangent-arcs/)
- [TUTORIAL] A tangent symbol appears while you drag out the arc. The tangent arc adds a Tangent constraint at its first point only. In the demo, a tangency at the second end appeared only because the geometry happened to line up. — [Fusion 360 Line To Arc Shortcut Tutorial (Tech and Espresso)](https://www.techandespresso.com/blog/Fusion-360-Line-To-Arc-Shortcut-Tutorial); [How to Use the Arc Command (all 3 explained), PDO](https://productdesignonline.com/tips-and-tricks/how-to-use-the-arc-command-in-fusion-360-all-3-explained/)
- [FORUM] Users say the drag-to-arc gesture cannot be turned off and is easy to trigger by accident. Using the Arc tool's Tangent Arc instead avoids it. (The thread is on the Inventor forum, which has the same gesture.) — [Why does the line tool sometimes produce an arc?](https://forums.autodesk.com/t5/inventor-forum/why-does-the-line-tool-sometimes-produce-an-arc/td-p/7555396)
- [TUTORIAL] Circles made with the 2-tangent or 3-tangent options get Tangent constraints to the chosen lines automatically. — [How to Use the Circle Command (all 5 explained), PDO](https://productdesignonline.com/tips-and-tricks/how-to-use-the-circle-command-in-fusion-360-all-5-explained/)
- [FORUM/TUTORIAL] Midpoint: snapped by hovering or with Shift, shown as a triangle icon (see section 1). — [Fusion Blog midpoint](https://www.autodesk.com/products/fusion-360/blog/mastering-midpoint-constraints-autodesk-fusion/)
- [FORUM] A forum answer about putting a circle at the center of a rectangle says Fusion does not infer constraints from construction lines or a rectangle's virtual center. You add a construction diagonal and a Midpoint or Coincident yourself. — [Circle in center of rectangle - automatic constraint?](https://forums.autodesk.com/t5/fusion-design-validate-document/circle-in-center-of-rectangle-automatic-constraint/td-p/8966764)
- [TUTORIAL] "Sketch: horizontal, vertical, collinear" is a lesson title in the Lynda AutoCAD-to-Fusion course. The search summary did not say whether Collinear is inferred or only applied by hand. — [Lynda course page](https://origin-www.lynda.com/Fusion-360-tutorials/Sketch-constraints-Horizontal-vertical-collinear/667363/703400-4.html)

### Inferences
- [INFERENCE] "Concentric" while drawing is in practice the center-point snap. Fusion's forum answer names "near a circle center" as a typical auto-constraint moment. SciForge can turn a center snap of a new circle onto an existing center into Coincident on the centers, or into a Concentric constraint. Which one Fusion records is unconfirmed.
- [INFERENCE] Tangent inference for a line drawn off the end of an arc (not via drag-arc) probably exists, given the general "suggesting tangencies" claims, but there is no direct source. Build it only behind observation.

### Gaps
- Automatic Equal inference (for example a new circle with the same radius as a hovered circle): no source, so probably not in Fusion.
- Automatic Collinear inference (for example a new line along the extension of an existing line): no source.
- The tangent-arc drag threshold (how many pixels of drag before the gesture switches from click to drag): not found.

## 5. Dashed alignment, extension and tracking lines

### Takeaway
Fusion does draw dashed or dotted guide lines while sketching, sometimes called "inference lines" or "snap guides". They come from acquired points, such as hovered endpoints, centers, midpoints and the origin, and appear when the cursor lines up with that point. Sources describe the color variously as blue or green. They act as a position snap. Whether a constraint is created from them is unclear, and their visibility has depended on graphics settings.

### Cited Findings
- [FORUM] An Autodesk help video showed a "blue dashed inference line" when hovering over a line endpoint. A user who could not see it later made it appear by changing graphics preferences. The thread is about 1,850 days old, roughly 2021. — [Blue Inference Line](https://forums.autodesk.com/t5/fusion-360-design-validate/blue-inference-line/td-p/6208011)
- [FORUM] Hovering a line's center, then moving away from it, gives a **green dashed** guide. Targets are limited to the last three hovered plus the geometry of the current command. — [Snap to center question](https://forums.autodesk.com/t5/fusion-360-design-validate/snap-to-center-question/td-p/5992547)
- [FORUM] Hovering the Origin and then moving to the target point gives a **blue dotted** constraint preview. — same search cluster as above, exact thread unconfirmed.
- [TUTORIAL video] "Fusion Snap Guides" (YouTube) explains "the dashed blue lines that appear while sketching" and "what they can and cannot do". Only its description could be read. — [Fusion Snap Guides (YouTube)](https://www.youtube.com/watch?v=MkVBNfVWB-I)
- [OFFICIAL, comparison] Onshape shows an **orange dashed** line for H/V inference, and clicking while it is visible accepts the inferred constraint. Cimatron shows an orange dashed line for near-H/V and a purple dashed line connecting two endpoints that share an X or Y. These are not Fusion behavior, but they are common patterns in the industry. — [Onshape: Automatic inferencing](https://cad.onshape.com/help/fr_FR/Content/inferencing.htm); [Cimatron: horizontal or vertical alignment](https://help.cimatron.com/en/2026/horizontal_or_vertical_alignment.htm)
- [FORUM] Some users perceive "snapping to an invisible grid", which may be these guides or grid snap. See section 6. — [Snap option in sketch palette](https://forums.autodesk.com/t5/fusion-design-validate-document/snap-option-in-sketch-palette/m-p/10365852)

### Inferences
- [INFERENCE] Spec for SciForge:
  - When the cursor's X or Y is within N pixels of an acquired point's X or Y (in sketch coordinates), snap the cursor onto that line.
  - Draw a thin dashed line from the acquired point to the cursor, in a single accent color.
  - Keep it on screen only while the alignment holds.
  - When two guides are active (one horizontal, one vertical), snap to their crossing. This is the AutoCAD tracking feature that Fusion approximates.
- [INFERENCE] Whether the guide creates a constraint on click: the "blue dotted constraint preview" wording suggests one might, for example H/V between the two points. Since nothing is confirmed, the safer default is a position-only snap with no constraint.

### Gaps
- Whether clicking on a guide creates a constraint, and which one (for example Horizontal/Vertical between the two points): unconfirmed.
- Dash pattern, line weight, the exact color in current themes, and whether the line runs from the point to the cursor or across the whole screen: unconfirmed.
- Whether extension guides along a line's direction (collinear extension) exist: no source.
- Which graphics setting controls guide visibility (the 2021 forum fix): not identified.

## 6. How auto-applied constraints are decided, and how to suppress or force them

### Takeaway
Whatever inference is showing when the click lands becomes a permanent constraint. Holding **Ctrl (Cmd on macOS)** while drawing suppresses all inferred constraints, and it also suppresses snapping, including coincident and grid snap. Holding **Shift** forces a midpoint snap. As far as the sources show, there is no preference that turns inference off for good; users have requested one. Grid snap is a separate toggle: Sketch Palette "Snap", or Display Settings > Grid and Snaps. Unwanted constraints are removed by selecting the glyph and deleting it. AutoConstrain (2025) is a separate after-the-fact AI tool, not inference while drawing.

### Cited Findings
- [STAFF] An Autodesk community moderator says that holding Ctrl (Cmd on Mac) "stops constraint inferencing", and "no constraints will be inferred". — [Struggles with Constraints](https://forums.autodesk.com/t5/fusion-support-forum/struggles-with-constraints/m-p/9505577); [Sketch Constraints](https://forums.autodesk.com/t5/fusion-support-forum/sketch-constraints/m-p/9515185)
- [TUTORIAL] "Hold down the CTRL key (CMD on Mac OS) to disable the auto-creation of constraints while creating any piece of sketch geometry." — [2 Sketch Constraint Secrets You Should Know, PDO](https://productdesignonline.com/tips-and-tricks/2-sketch-constraint-secrets-you-should-know/); the same tip appears on [Hackaday.io project 163649](https://hackaday.io/project/163649)
- [FORUM] Ctrl also disables coincident constraints, and "will disable snapping completely", including grid snapping. Users said there is no "snap without constraints" mode. — [sketch - disable constraints, but keep snap to grid](https://forums.autodesk.com/t5/fusion-360-design-validate/sketch-disable-constraints-but-keep-snap-to-grid/td-p/6965757); [The snaps are killing me](https://forums.autodesk.com/t5/fusion-design-validate-document/the-snaps-are-killing-me/td-p/7309263); [Disable snapping temporarily](https://forums.autodesk.com/t5/fusion-design-validate-document/disable-snapping-temporarily/td-p/6609586); [how to turn off all snapping](https://forums.autodesk.com/t5/fusion-design-validate-document/how-to-turn-off-all-snapping-i-want-to-draw-free-verticalother/td-p/6391107)
- [FORUM] Ctrl "does not always work". For example, while moving a sketch object it brings up a menu. — [Struggles with Constraints](https://forums.autodesk.com/t5/fusion-support-forum/struggles-with-constraints/m-p/9505577)
- [FORUM] Users asked for a preference to disable automatic constraint creation, or only some types of it. These archived ideas were not shown as implemented. — [Idea: preference to disable auto-constraint creation](https://forums.autodesk.com/t5/fusion-360-ideastation-archived/preference-to-disable-auto-contraint-creation/idc-p/7917811); [Idea: disable specific automatic constraint creation](https://forums.autodesk.com/t5/fusion-360-ideastation-archived/sketch-automatic-constraint-creation-disable-specific/idc-p/7922002); [Idea: Turn off "snap to object" only](https://forums.autodesk.com/t5/fusion-360-ideastation-archived/turn-off-quot-snap-to-object-quot-only/idi-p/5492838)
- [OFFICIAL, Inventor, for contrast] Inventor has the same Ctrl-to-suppress behavior plus a ribbon toggle (Constraint Inference and Persistence) that turns inference off entirely. Fusion appears not to have that toggle. — [Inventor 2014 Help: Control constraint inference and automatic constraints](https://help.autodesk.com/cloudhelp/2014/ENU/Inventor/files/GUID-1E504789-DFC6-4B59-81AA-1EFC1B656FB1.htm)
- [OFFICIAL] Shift plus hover forces the midpoint snap (see section 1). — [Autodesk support article](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/Unable-to-constrain-to-the-midpoint-of-a-line-in-Fusion-360.html)
- [TUTORIAL] Snap to Grid is on by default and can be turned off at the bottom of the window under Display Settings > Grid and Snaps. When you move items, they move incrementally. — [Lynda: Fusion 360 Tips, Tricks and Techniques, "Snap to grid/incremental move"](https://www.lynda.com/Fusion-360-tutorials/Snap-grid-incremental-move/2810401/2825306-4.html)
- [FORUM] The Sketch Palette has a "Snap" checkbox described as enabling or disabling snapping to the sketch grid. One user says it still snaps when the grid is hidden. — [Snap option in sketch palette](https://forums.autodesk.com/t5/fusion-design-validate-document/snap-option-in-sketch-palette/m-p/10365852)
- [FORUM/TUTORIAL] To remove an auto-applied constraint, select its glyph and press Delete, or right-click > Delete. The Sketch Palette's "Show Constraints" option controls whether the glyphs are shown. — [Lynda AutoCAD-to-Fusion lesson](https://origin-www.lynda.com/Fusion-360-tutorials/Sketch-constraints-Horizontal-vertical-collinear/667363/703400-4.html); [How do I turn object snap on?](https://forums.autodesk.com/t5/fusion-support-forum/how-do-i-turn-object-snap-on/td-p/8898853)
- [OFFICIAL blog, version change] **AutoConstrain** was announced at AU 2024 and shipped in the January 2025 update. It lives on the Sketch **Automate** tab and uses a transformer model to propose the missing constraints and dimensions for an existing sketch. Later 2025 updates let it fix tiny gaps, off-axis lines and near-tangent arcs, and added a results card with tolerance and per-constraint-type controls. It works after the fact and does not change inference while drawing. — [AutoConstrain for Fusion is here!](https://www.autodesk.com/products/fusion-360/blog/autoconstrain-for-fusion-is-here/); [Autodesk Research: Using AI to power AutoConstrain](https://www.research.autodesk.com/blog/using-ai-to-power-autoconstrain-in-fusion-automated-sketching/); [Fusion Year in Review 2025](https://www.autodesk.com/products/fusion-360/blog/autodesk-fusion-year-in-review-2025/)

### Inferences
- [INFERENCE] Decision rule to copy: at click time, commit exactly the set of inferences currently shown, so what you see is what you get. If Ctrl is held, commit nothing and do not snap: the raw cursor position is used. If Shift is held over a curve, snap to its midpoint and commit Midpoint.
- [INFERENCE] One Fusion annoyance that SciForge could fix as an optional preference: Fusion has no way to keep point snaps while suppressing H/V and other glyph constraints. Leave it off by default to stay Fusion-faithful.

### Gaps
- Whether Ctrl must be held at the moment of the click only, or for the whole drag: not stated.
- Whether Ctrl also suppresses the tangent-arc drag gesture: not stated.
- No source documents a current (2024 to 2026) global "disable inference" preference, so it most likely still does not exist, but this could not be checked against live help pages.

## 7. Differences between the Line, Rectangle, Circle, Arc, Spline, Polygon and Slot tools

### Takeaway
- The Line tool has the richest inference: point snaps, H/V, perpendicular, the drag-to-tangent-arc gesture and dashed guides, plus chaining until Esc.
- Shape tools mostly add fixed "internal" constraints that come with the shape: 2-point rectangle gets H/V on each side, 3-point rectangle gets Parallel plus Perpendicular, slots get Tangent plus Parallel, tangent circles get Tangent.
- Each shape tool's own click points still use the same point snaps (coincident to existing points, center snaps and so on).
- Spline, Polygon and the center rectangle are poorly documented.

### Cited Findings
- [TUTORIAL] Line tool: stays active after each segment so you can chain segments until Esc. Length and angle can be typed while drawing. Level lines get Horizontal automatically. — [PDO Line command](https://productdesignonline.com/tips-and-tricks/how-to-use-the-line-command-in-fusion-360-secrets-revealed/)
- [OFFICIAL blog] Line tool tangent-arc drag gesture (section 4). — [Fusion Blog tangent arcs](https://www.autodesk.com/products/fusion-360/blog/quick-tip-sketching-tangent-arcs/)
- [TUTORIAL] 2-point rectangle: every side gets an automatic Horizontal or Vertical constraint. — [PDO Rectangle (all 3)](https://productdesignonline.com/tips-and-tricks/how-to-use-the-rectangle-sketch-command-in-fusion-360-all-3-explained/)
- [TUTORIAL] 3-point rectangle: automatic Parallel on the opposite sides and a Perpendicular at one corner, so it can sit at any angle. — [PDO Rectangle (all 3)](https://productdesignonline.com/tips-and-tricks/how-to-use-the-rectangle-sketch-command-in-fusion-360-all-3-explained/)
- [OFFICIAL] Center rectangle: click a center, then a corner (or type dimensions). Help says the rectangle "and any construction geometry, constraints, and dimensions that are added to them" display in the canvas, but the summary did not list them. — [Fusion Help: Create rectangles](https://help.autodesk.com/view/fusion360/ENU/?guid=SKT-CREATE-RECTANGLES)
- [TUTORIAL] Slots: "depending on which slot command you use, a series of geometry and constraints will automatically be applied", including Tangent where the arcs meet the lines and Parallel on the lines. Some slot types still need an arc dimension to be fully constrained. — [How to Use the Slot Commands, PDO](https://productdesignonline.com/tips-and-tricks/how-to-use-the-slot-commands-in-fusion-360/)
- [TUTORIAL] Circles: the 2-tangent and 3-tangent circles add Tangent constraints automatically. — [PDO Circle (all 5)](https://productdesignonline.com/tips-and-tricks/how-to-use-the-circle-command-in-fusion-360-all-5-explained/)
- [TUTORIAL] Arcs: the 3-point, center-point and tangent arc types are explained, with the tangent arc being the one that adds Tangent. — [PDO Arc (all 3)](https://productdesignonline.com/tips-and-tricks/how-to-use-the-arc-command-in-fusion-360-all-3-explained/)
- [FORUM] Polygon: a circumscribed polygon is built around a construction circle. A user needed a Tangent to that construction circle plus a fixed point at the origin to fully constrain it; until locked, it rotates about the center. — [Constraints of a Circumscribed Polygon](https://forums.autodesk.com/t5/fusion-design-validate-document/constraints-of-a-circumscribed-polygon/td-p/12016046)
- [TUTORIAL] Center rectangle centered on the origin: a common question. Forum answers suggest Midpoint or H/V tricks, which suggests the tool does not lock the center to the origin by itself unless you click on the origin. — [Quickly sketch a rectangle centered at origin](https://forums.autodesk.com/t5/fusion-design-validate-document/quickly-sketch-a-rectangle-centered-at-origin-how-to/td-p/10897497)

### Inferences
- [INFERENCE] Implementation split: (1) a shared "point picker" used by every tool's clicks, which handles point snaps, guides, Ctrl and Shift and returns a position plus a list of point constraints; (2) a per-tool "segment inference", currently only Line (H/V, perpendicular to the previous segment or the target line, tangent arc gesture); (3) per-tool fixed internal constraints added on finish (rectangle, slot, polygon, tangent circles).
- [INFERENCE] The 2-point rectangle's H/V sides mean its edges always follow the sketch axes. The 3-point rectangle is the one for rotated rectangles. SciForge should keep that split.

### Gaps
- Center rectangle: the exact constraints are not confirmed. From memory, unverified: recent Fusion versions add construction diagonals with the center point placed as Midpoint on a diagonal, plus H/V on the sides. This must be checked.
- Spline (fit-point and control-point): no source on inference. Presumably only point snaps on the fit points, and Tangent when a spline starts at a curve end. Unconfirmed.
- Polygon (inscribed, circumscribed, edge): the exact list of Equal, construction circle and Coincident constraints is unconfirmed.
- Whether H/V inference applies to the first edge of a 3-point rectangle or polygon: unconfirmed.

## 8. What inference looks like visually: glyph colors, reference highlight, how long things are shown

### Takeaway
The inferred constraint appears as a small constraint glyph (the same symbol set as the permanent constraint icons) next to the line or cursor. It follows the cursor and disappears the moment the inference no longer applies; it becomes a permanent glyph only on click. Sources disagree on the color: cyan, blue and yellow are all reported, which probably reflects different versions and themes. Dashed guides are reported as blue or green. No source gives a delay or duration; everything is described as live feedback that updates with each mouse move.

### Cited Findings
- [TUTORIAL] "Sketch Constraints automatically infer in a **cyan** color, and then follow you around the drawing." — [VDCI: Introduction to Sketch Tools and Options in Fusion 360](https://vdci.edu/learn/cad/introduction-to-sketch-tools-and-options-in-fusion-360)
- [TUTORIAL] Before a shape is finished, the candidate constraints are shown as **blue** icons. Separately, fixed (locked) geometry is shown in **green**. — [nakayasu lecture notes](https://lecture.nakayasu.com/en/docs/fusion360/fusion360-sketch-constraints/)
- [TUTORIAL] One secondary source describes the automatic constraints added while sketching as **yellow** glyphs. The search summary did not identify which of the returned pages said this, so the attribution is weak. — returned alongside [Understanding Sketch Constraints in Fusion 360 (Noble Desktop)](https://blog.nobledesktop.com/learn/cad/understanding-sketch-constraints-in-fusion-360) and [Fusion 360 Constraints & Dimensions (autocadeverything)](https://autocadeverything.com/fusion-360-constraints/). The three color reports (cyan, blue, yellow) contradict each other.
- [FORUM] Dashed guides are described as "blue dashed" ([Blue Inference Line](https://forums.autodesk.com/t5/fusion-360-design-validate/blue-inference-line/td-p/6208011)), as "green dashed" ([Snap to center question](https://forums.autodesk.com/t5/fusion-360-design-validate/snap-to-center-question/td-p/5992547)), and as "dashed blue lines" in the [Fusion Snap Guides video](https://www.youtube.com/watch?v=MkVBNfVWB-I).
- [OFFICIAL] For context, sketch geometry colors (not inference colors): under-constrained geometry is blue, and fully constrained geometry turns black (light theme) or white-ish (dark theme). An Autodesk article explains cases where a fully constrained sketch is not all black. — [A fully constrained sketch is not shown in all black in Fusion](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/A-fully-constrained-sketch-is-not-shown-in-all-black-in-Fusion-360.html)
- [FORUM/TUTORIAL] Permanent glyphs are small icons (perpendicular, tangent, equal and so on) placed next to the constrained entity. They are shown or hidden with the Sketch Palette's "Show Constraints". — [How do I turn object snap on?](https://forums.autodesk.com/t5/fusion-support-forum/how-do-i-turn-object-snap-on/td-p/8898853); [Noble Desktop](https://blog.nobledesktop.com/learn/cad/understanding-sketch-constraints-in-fusion-360)
- [OFFICIAL blog] Midpoint glyph described as a triangle, and "a triangle with an X" when the snap is hit. — [Fusion Blog midpoint quick tip](https://www.autodesk.com/products/fusion-360/blog/quick-tip-midpoint-constraint-shortcut/)

### Inferences
- [INFERENCE] For SciForge: draw the transient glyphs and guides in a single accent color that stands apart from both the "under-constrained" and "fully constrained" geometry colors. A cyan or blue accent matches most reports. Draw the guide lines thin and dashed. Draw the glyphs with SciForge's own icon set: copy the behavior, never Fusion's icons. Update on every mouse move with no delay, and remove the glyphs the moment the condition stops holding.
- [INFERENCE] Show the transient glyph near the segment being drawn (H/V at the line's midpoint or base) or next to the snap point (coincident, midpoint). On click, turn it into the permanent glyph.

### Gaps
- The exact inference glyph color in 2024 to 2026 light and dark themes: conflicting reports, not confirmed.
- Whether the reference entity (the hovered line or point) gets a highlight color while it is an inference target: not described.
- Any hover-dwell time needed to acquire a target (AutoCAD uses a short pause): not described for Fusion. The forum wording "hover over or touch" suggests a pass-over with no pause is enough. Unconfirmed.
- No image or video frame of the current UI could be examined, since all of these sites were blocked. A short session in a real Fusion install, or frame-by-frame review of the "Fusion Snap Guides" video, would settle the colors, marker shapes and click behavior of the guides.
