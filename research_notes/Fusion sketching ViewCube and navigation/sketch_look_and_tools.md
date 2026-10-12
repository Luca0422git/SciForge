# Fusion sketch environment: look and tool behavior (excluding inference/snapping)

Source access note: in this sandbox, WebFetch could not resolve any host and the proxy refused direct downloads of help.autodesk.com (HTTP 403). Every finding below therefore comes from search-engine excerpts of the linked pages, not from reading the full pages. Each item says what kind of source it is: **[Official doc]** = help.autodesk.com, **[Official blog/support]** = autodesk.com Fusion blog or Autodesk support article, **[Forum]** = Autodesk Community, **[Tutorial]** = third-party tutorial sites (Product Design Online, Tech & Espresso, etc.). Anything not backed by a source is under "Inferences" (my reasoning or unverified recollection) or "Gaps". Inference/snapping, alignment lines and H/V/perpendicular/tangent inference are covered by a separate researcher and left out here.

## 1. Colors and line styles of sketch geometry

### Takeaway
Fusion encodes state in color. Under-constrained normal geometry is solid blue, fully constrained geometry is black, construction geometry is dashed orange, fixed geometry is green and projected geometry is purple. Closed profiles in the active sketch are shaded light blue in current releases (they were orange before about 2020). A fully constrained sketch shows a small red lock on its icon in the browser.

### Cited Findings
- **Normal sketch geometry**: "the default line type used to create 2D features in a sketch that contribute to the sketch profile, and displays as a solid blue line when unconstrained." [Official blog] — [Sketching basics in Autodesk Fusion](https://www.autodesk.com/products/fusion-360/blog/sketching-basics-in-autodesk-fusion/)
- **Fully constrained**: geometry turns black once fully constrained, meaning "the size and position of all sketch geometry is completely defined." [Official doc] — [Fully define and constrain sketches](https://help.autodesk.com/cloudhelp/ENU/Fusion-Sketch/files/SKT-FULLY-DEFINE-CONSTRAIN-SKETCH.htm); [Official support] color key (black = fully constrained, blue = not fully constrained, purple = projected) — [What do the line colors mean in Fusion sketch](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/What-does-the-color-line-means-in-Fusion-360-sketch.html)
- **Fixed geometry**: "any Sketch, Construction, or Centerline geometry that you have locked in place", shown **green**. [Official blog] — [Sketching basics in Autodesk Fusion](https://www.autodesk.com/products/fusion-360/blog/sketching-basics-in-autodesk-fusion/)
- **Projected geometry**: "an associative reference to profiles of 2D or 3D geometry from outside the sketch that are projected onto the sketch plane", shown as **purple lines and points**. [Official blog] — [Sketching basics in Autodesk Fusion](https://www.autodesk.com/products/fusion-360/blog/sketching-basics-in-autodesk-fusion/); same color key in the [support article](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/What-does-the-color-line-means-in-Fusion-360-sketch.html)
- **Construction geometry**: "displays as dashed orange geometry when unconstrained". Construction lines are references and do **not** contribute to profiles. [Official blog/doc] — [Sketches in Fusion](https://www.autodesk.com/products/fusion-360/blog/fusion-360-sketch-fundamentals/); support article lists "Orange dashed: Construction line" — [line colors article](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/What-does-the-color-line-means-in-Fusion-360-sketch.html)
- **Centerline**: a separate line type "used to revolve sketch profiles or define symmetry". The search excerpt described it as looking like construction (orange, non-solid). One excerpt attached "Contributes to the sketch profile" to the centerline definition, which may be a garbled excerpt. See Gaps. [Official blog] — [Sketches in Fusion](https://www.autodesk.com/products/fusion-360/blog/fusion-360-sketch-fundamentals/)
- **July 2025**: Fusion added "Diametric dimensions, which automatically recognize your center lines and provide the diameter dimensions." This confirms centerlines act as a symmetry axis for dimensioning. [Official blog] — [July 2025 Product Update](https://www.autodesk.com/products/fusion-360/blog/july-2025-product-update-whats-new/)
- **Profile shading (current)**: "A sketch profile is shaded blue when it is closed and can be used to Extrude 3D shapes or perform 3D boolean operations like Join, Cut, and Intersect." [Official blog/doc] — [Sketches in Fusion](https://www.autodesk.com/products/fusion-360/blog/fusion-360-sketch-fundamentals/)
- **Version change, profile shading**: users noted "Blue for 2020, orange before the upgrade" and "older videos are orange, newer videos are light blue, works the same". [Forum] — [Sketch - Blue Interior](https://forums.autodesk.com/t5/fusion-360-design-validate/sketch-blue-interior/td-p/9668011); older orange-era thread: [Moving sketch out of plane loses the orange shading](https://forums.autodesk.com/t5/fusion-support-forum/moving-sketch-out-of-plane-loses-the-orange-shading-i-need-to/td-p/7434864)
- Shading disappears when the sketch is no longer planar. All curves of a profile must be in one sketch for the profile to be recognized. [Forum] — [orange shading thread](https://forums.autodesk.com/t5/fusion-support-forum/moving-sketch-out-of-plane-loses-the-orange-shading-i-need-to/td-p/7434864)
- Debug trick used by tutorials: draw a temporary line across a shape. If both halves shade, the loop is closed. If only one side fills, the gap is on the unshaded side. [Tutorial] — [Open Profiles in Fusion 360](https://pierskitech.com/guides/fusion-360-open-profile-wont-extrude)
- **Fully constrained sketch in the browser**: a **red lock** appears on the sketch's icon in the browser when the sketch is fully constrained. [Official doc] — [Fully define and constrain sketches](https://help.autodesk.com/cloudhelp/ENU/Fusion-Sketch/files/SKT-FULLY-DEFINE-CONSTRAIN-SKETCH.htm). Users often misread it as "locked against editing". An Autodesk Community Manager said the lock and black color may be missing if the solver does not recognize full definition, and that full constraint is optional (its main value is stability under edit). [Forum] — [What does a red "lock" icon mean on a sketch icon?](https://forums.autodesk.com/t5/fusion-design-validate-document/what-does-a-red-quot-lock-quot-icon-mean-on-a-sketch-icon/m-p/9134607)
- **History**: constraint-status coloring started as a Preview preference ("Preferences > Preview > Sketch: Color geometry based on constraint status"), under which fully constrained geometry turns black. It is now standard behavior. [Forum, old] — [Seeing which constraints are on a sketch](https://forums.autodesk.com/t5/fusion-design-validate-document/seeing-which-constraints-are-on-a-sketch/td-p/6255116)
- **Preselection (hover) color**: a user complained that the **dark blue preselection highlight** is hard to see on black (constrained) geometry, and asked which theme XML entry controls it. [Forum] — [Issues with preselection highlighting of sketcher constraints](https://forums.autodesk.com/t5/fusion-design-validate-document/issues-with-preselection-highlighting-of-sketcher-constraints/m-p/10941750)
- **Selected profiles**: a user said selected and unselected profiles are hard to tell apart (accessibility complaint). Colors live in theme XML files and are not exposed as a preference. [Forum] — [Highlight color when selecting sketch profiles](https://forums.autodesk.com/t5/fusion-design-validate-document/highlight-color-when-selecting-sketch-profiles/m-p/6873109)

### Inferences
- The color scheme implies the solver reports a per-entity "degrees of freedom remaining" state (blue = free, black = fully defined) plus a per-sketch "fully defined" flag that drives the browser lock badge. SciForge's sketcher solver (FreeCAD Sketcher already reports DOF) can map onto this directly.
- Fixed (green) overrides the constrained/unconstrained colors. Projected (purple) is a separate category that shows whatever the constraint status.
- Recollection, unverified in this session: sketch points (line endpoints, arc centers) draw as small dots in the same color as their state (blue or black). Selected curves draw in a brighter/lighter highlight color than the blue preselection. Treat these as unconfirmed.

### Gaps
- Exact centerline line pattern (dash-dot vs dashed) and whether centerlines contribute to profiles. The search excerpt was ambiguous. My recollection is that centerlines are orange dash-dot and do NOT form profiles, but this is unconfirmed.
- Exact RGB values for any state. Not documented, and only in theme XML files that I could not read.
- Appearance of sketch points (shape, size, filled or hollow). No source found.
- Exact selection highlight color. Only the preselection "dark blue" is mentioned, by a forum user.
- Whether over-constrained or conflicting geometry gets its own color (some CAD tools use red). Not found.

## 2. Constraint glyphs (display, show/hide, hover, delete)

### Takeaway
Constraints draw as small icon glyphs next to the geometry they apply to. The "Show Constraints" checkbox in the Sketch Palette shows or hides them all. With it off, selecting curves shows only the constraints on those curves. To delete a constraint, hover or select its glyph and press Delete, or right-click and choose Delete.

### Cited Findings
- Sketch Palette has **Show Constraints** ("shows or hides sketch constraints") and **Show Dimensions**. [Official doc] — [Sketch Palette reference](https://help.autodesk.com/view/fusion360/ENU/?guid=GUID-4183A4B7-E002-4396-AD5A-7FF3C8B2F33A); [Official support] — [How to Hide/Show Sketch dimensions & Constraints](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/How-to-hide-show-all-dimensions-while-being-sketch-mode.html)
- With **Show Constraints unchecked**, no glyphs show, and "select the sketch curves you are interested in and see all the constraints ONLY related to the curves you selected." [Forum] — [Viewing 'conflicting' constraints](https://forums.autodesk.com/t5/fusion-design-validate-document/viewing-conflicting-constraints/td-p/6476854); [Seeing which constraints are on a sketch](https://forums.autodesk.com/t5/fusion-design-validate-document/seeing-which-constraints-are-on-a-sketch/td-p/6255116)
- **Deleting**: "hover over a sketch constraint, then click Delete on your keyboard, or right click and click Delete". Clicking a sketch point or line may be needed before more constraints appear. [Official support] — [How to delete sketch constraints in Autodesk Fusion](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/How-to-delete-sketch-constraints-in-Fusion-360.html)
- Some glyphs (notably **coincident**) are hidden until you hover near the related element or enable display. The **Select** tool must be active to pick glyphs; otherwise clicks may go to the active creation tool. [Official support + Forum] — [How to delete sketch constraints](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/How-to-delete-sketch-constraints-in-Fusion-360.html); [Easy way to remove constraints](https://forums.autodesk.com/t5/fusion-design-validate-document/easy-way-to-remove-constraints/td-p/5119582)
- **Bulk delete**: set the selection filter to sketch constraints, window-select, then Delete. Point-level constraints may not be caught and must be removed one at a time. [Forum] — [remove all constraints in one fell swoop](https://forums.autodesk.com/t5/fusion-design-validate-document/remove-all-constraints-in-one-fell-swoop/td-p/7559362)
- **Pattern constraint glyph**: sketch patterns add a pattern constraint with its own glyph, and that constraint blocks Trim on the patterned geometry. Selecting the pattern glyph and deleting it frees the geometry. [Forum] — [Help with Sketch Trim command](https://forums.autodesk.com/t5/fusion-design-validate-document/help-with-sketch-trim-command/td-p/5900460)
- Offset also leaves an editable glyph: "double-clicking the offset glyph lets you edit its inputs, including selected entities, dimensions and flips." [Forum] — [How do I edit Sketch offset direction?](https://forums.autodesk.com/t5/fusion-support-forum/how-do-i-edit-sketch-offset-direction/td-p/7587916)
- A third-party add-in (ConstraintsLens) exists because Fusion has no built-in list of constraints. This suggests the canvas glyphs are the only native constraint UI. [Third-party] — [ConstraintsLens on GitHub](https://github.com/craigulliott/ConstraintsLens)
- **Constraint set** (12 constraints taught in tutorials): horizontal/vertical, coincident, tangent, equal, parallel, perpendicular, fix/unfix, midpoint, concentric, collinear, symmetry, curvature. [Tutorial] — [Day 17: Learn all 12 Fusion 360 sketch constraints](https://productdesignonline.com/day-17-of-learn-fusion-360-in-30-days-for-complete-beginners-2023-edition-learn-all-12-fusion-360-sketch-constraints/)

### Inferences
- A faithful copy should: draw each constraint as a small glyph offset from the midpoint of its entity (or near the shared point); highlight the constrained entities when the glyph is hovered; allow glyph selection plus Delete and a right-click Delete; and keep coincident glyphs hidden by default. Glyph visibility should follow the palette checkbox, with a "selected-only" fallback when the checkbox is off.
- Paired constraints (parallel, equal, tangent) probably show a glyph on each participating entity, and hovering one highlights both. This is common practice but was not confirmed in sources found here.

### Gaps
- Exact glyph shapes and colors, and whether glyphs change color when hovered or selected. No source described them, and SciForge must design its own icons anyway.
- Whether the Show Constraints display behavior changed in 2023 to 2026 releases. No release note found.
- What exactly happens when a new constraint conflicts with existing ones (message text, whether it is refused). Not found.

## 3. Heads-up dimension input while drawing

### Takeaway
After the first click of a line, two small input boxes follow the cursor: length, then angle. Typing sets a value. Tab locks the typed value (a small lock appears) and moves focus to the other box. Enter or a click places the segment. Values typed this way become sketch dimensions. Rectangles offer width and height boxes the same way. Entered values accept units and expressions (as in the dimension edit box).

### Cited Findings
- After the first click of a line, "two numerical input boxes appear. The first sets length and the second sets angle." Moving the mouse changes the value until you press **Tab**, which "stops that, and a lock icon appears." [Tutorial] — [How to Use the Line Command in Fusion 360 (secrets revealed)](https://productdesignonline.com/tips-and-tricks/how-to-use-the-line-command-in-fusion-360-secrets-revealed/)
- Tab switches between the line's length and angle. [Forum] — [Numerical inputs](https://forums.autodesk.com/t5/fusion-design-validate-document/numerical-inputs/td-p/7643334); for a line tangent to a circle, "specify the angle by hitting Tab key while creating a line". [Forum] — [How to input angle of tangent line?](https://forums.autodesk.com/t5/fusion-design-validate-document/how-to-input-angle-of-tangent-line/td-p/6521719)
- You can enter both length and angle before ending the line command. A preference named "Edit Dimension when created" was reported by users to make no visible difference to this. [Forum] — [Dimension entering](https://forums.autodesk.com/t5/fusion-design-validate-document/dimension-entering/td-p/5979272)
- Values typed in the line tool become sketch dimensions on the geometry. Geometry without them stays blue (not fully defined). [Tutorial/Forum via search excerpt] — [PDO line command](https://productdesignonline.com/tips-and-tricks/how-to-use-the-line-command-in-fusion-360-secrets-revealed/); [Dimension entering](https://forums.autodesk.com/t5/fusion-design-validate-document/dimension-entering/td-p/5979272)
- **2-Point Rectangle**: "click to place the opposite corner point, or specify the length, width, or both values, then click to place the rectangle." [Official doc] — [Create rectangles](https://help.autodesk.com/view/fusion360/ENU/?guid=SKT-SKETCH-CREATE-RECTANGLES)
- For rectangles, "pressing the tab key after typing out a dimension locks the dimension in place." [Tutorial] — [How to Use the Rectangle Sketch Command (all 3 explained)](https://productdesignonline.com/tips-and-tricks/how-to-use-the-rectangle-sketch-command-in-fusion-360-all-3-explained/). Rectangles drawn with typed sizes can still be under-constrained in position (they float until located with dimensions or constraints). [Tutorial] — [CADbrief: rectangle with precise dimensions](https://cadbrief.com/how-to-draw-a-rectangle-with-precise-dimensions-in-autodesk-fusion/)
- The Sketch Dimension edit box accepts "a number, referencing an existing dimension, or entering an expression", accepted with Enter. [Official doc] — [Sketch dimensions](https://help.autodesk.com/view/fusion360/ENU/?guid=SKT-SKETCH-CREATE-DIMENSIONS)

### Inferences
- The HUD boxes probably accept the same grammar as the dimension box (units like "10 mm" or "1 in", arithmetic, parameter names), since both create the same dimension objects. Not confirmed for the HUD specifically.
- Model for SciForge: each tool exposes an ordered list of HUD fields (Line: length, angle; 2-point rectangle: width, height; center-diameter circle: diameter; polygon: size and side count). Each field has three states: following the cursor, typed but not locked, and locked (Tab). Only locked or typed fields create driving dimensions when the entity is committed. Fields left alone create no dimension.
- Recollection, unverified: the center-diameter circle shows one diameter box. Arcs show radius and sweep-angle boxes. Slot shows length and width boxes.

### Gaps
- Circle, arc, polygon, slot HUD fields: no source found in this session.
- Whether pressing Enter with an untouched field commits the cursor value, and whether Shift-Tab goes back a field. Not found.
- Whether HUD-created dimensions are placed at a default offset, and where. Not found.

## 4. Line tool interaction

### Takeaway
The Line tool chains segments: each click ends one segment and starts the next. Pressing and dragging from the last endpoint switches to a tangent arc, and releasing returns to lines. Clicking the start point closes the profile. Double-click ends the current chain but keeps the tool active. Esc exits the tool. The official doc says Enter completes the tool.

### Cited Findings
- "While using the Line tool, you can transition to the Tangent Arc tool by holding down the mouse button, and back to the Line tool, by releasing the mouse button." [Official blog] — [QUICK TIP: Sketching Tangent Arcs](https://www.autodesk.com/products/fusion-360/blog/quick-tip-sketching-tangent-arcs/)
- "Pause over an end point, then click and drag to create an arc segment that is tangent to the previous line segment. Move the mouse to the opposite side of the line segment to flip the direction of the arc." [Official doc] — [Sketch tools overview](https://help.autodesk.com/view/fusion360/ENU/?guid=GD-SKETCH-TOOLS)
- "Click the start point to create a closed sketch profile." Press **Enter** to complete the tool. [Official doc] — [Create lines in a sketch](https://help.autodesk.com/cloudhelp/ENU/Fusion-Sketch/files/SKT-CREATE-LINES.htm)
- The line command stays active and you keep creating lines until you press **Escape** to exit. [Tutorial] — [Day 3 of Learn Autodesk Fusion in 30 Days (2026 Edition)](https://productdesignonline.com/learn-autodesk-fusion-in-30-days-2026-day-3/)
- Double-click ends the current chain but keeps the Line command active. Escape fully releases it. The author notes double-click "can be a little problematic". [Tutorial] — [Fusion 360 Sketching Separate Lines and Multiple Lines](https://www.techandespresso.com/blog/fusion-360-sketch-separate-lines-multiple-lines); [Line To Arc Shortcut](https://www.techandespresso.com/blog/Fusion-360-Line-To-Arc-Shortcut-Tutorial)
- Note: sources give slightly different ways to end a chain (Enter per Autodesk doc, Escape per tutorial, double-click per community article). Whether all three coexist in current builds was not verified.

### Inferences
- Likely state machine: Idle → (click) → Drawing (rubber-band from last point) → (click) commit segment and stay in Drawing from the new point → (click on chain start) commit, close, return to Idle with the tool still active → (double-click or Enter) end chain, Idle with tool active → (Esc in Idle) leave the tool and go to Select. A press-drag that starts on the current endpoint switches to tangent-arc preview until mouse-up.
- Recollection, unverified: Esc while mid-chain discards only the rubber-band segment (already committed segments stay). The right-click marking menu while the Line tool is active offers OK / Cancel and repeat-style entries, as elsewhere in Fusion.

### Gaps
- Right-click menu contents while the Line tool is active: not found.
- Whether clicking the start point ends the chain or continues it from the start point: the doc excerpt only says it closes the profile.

## 5. Other sketch tools (create and modify)

### Takeaway
Fusion's Create menu offers several variants of each primitive: 3 rectangle, 5 circle, 3 arc, 3 polygon and 5 slot kinds, plus fit-point and control-point splines. Modify tools (Trim, Extend, Break) preview the affected segment on hover, then click to act. Offset, Mirror and patterns open small dialogs and leave constraints behind. Project/Include creates purple, linked geometry. Since January 2025 an AI "AutoConstrain" tool sits in an Automate tab.

### Cited Findings
**Rectangles**
- 2-Point Rectangle (opposite corners, or typed width and height), 3-Point Rectangle (first edge sets width and direction, third click sets height), Center Rectangle. [Official doc + Tutorial] — [Create rectangles](https://help.autodesk.com/view/fusion360/ENU/?guid=SKT-SKETCH-CREATE-RECTANGLES); [PDO rectangle (all 3 explained)](https://productdesignonline.com/tips-and-tricks/how-to-use-the-rectangle-sketch-command-in-fusion-360-all-3-explained/)

**Circles**
- Center Diameter, 2-Point, 3-Point, 2-Tangent and 3-Tangent circles. The circle type can be switched while the tool is running via the Sketch Palette's tool options. [Official doc + Tutorial] — [Sketch tools overview](https://help.autodesk.com/view/fusion360/ENU/?guid=GD-SKETCH-TOOLS); [learndesign.tech: all 2D sketch tools](https://learndesign.tech/uncategorized/how-to-use-all-2d-cad-sketch-tools-in-fusion-360/)

**Arcs**
- 3-Point Arc, Center Point Arc, Tangent Arc. [Official doc + Tutorial] — [Arcs in sketches](https://help.autodesk.com/cloudhelp/ENU/Fusion-Sketch/files/SKT-SKETCH-CREATE-ARCS.htm); [PDO arc command (all 3 explained)](https://productdesignonline.com/tips-and-tricks/how-to-use-the-arc-command-in-fusion-360-all-3-explained/)

**Polygons**
- Circumscribed (sized by the circle it surrounds), Inscribed (center, side count, radius to a corner), Edge (edge length, orientation, side count). [Official doc/Tutorial via excerpt] — [Sketch tools overview](https://help.autodesk.com/view/fusion360/ENU/?guid=GD-SKETCH-TOOLS); [LearnDesk polygon lesson](https://www.learndesk.us/class/6238179591979008/lesson/3c44cb8d420dcde9f29a5fe0b359ccc9)

**Slots**
- Center to Center, Overall, Center Point. Some guides also list Three-Point Arc Slot and Center Point Arc Slot. [Official doc + Tutorial] — [Sketch tools overview](https://help.autodesk.com/view/fusion360/ENU/?guid=GD-SKETCH-TOOLS); [learndesign.tech](https://learndesign.tech/uncategorized/how-to-use-all-2d-cad-sketch-tools-in-fusion-360/)

**Splines**
- Fit Point Spline passes through the clicked points. A Control Point Spline also exists (the curve is pulled toward, not through, the control points). [Tutorial] — [How to Use the Spline Commands in Fusion 360](https://productdesignonline.com/tips-and-tricks/how-to-use-the-spline-commands-in-fusion-360/). The search excerpt did not describe control-point behavior in detail.

**Trim / Extend / Break**
- Trim "trims sketch geometry to the nearest extended intersection with other geometry in the active sketch." Pause over a segment to preview it, then click. "If no intersection exists, the sketch geometry is deleted." [Official doc] — [Trim or extend sketch geometry](https://help.autodesk.com/cloudhelp/ENU/Fusion-Sketch/files/SKT-TRIM-EXTEND.htm)
- The segment under the cursor turns **red** as the trim preview. The tool stays active after each cut. [Tutorial + Forum] — [How to Use the Trim Command](https://productdesignonline.com/tips-and-tricks/how-to-use-the-trim-command-in-fusion-360/); [Help with Sketch Trim command](https://forums.autodesk.com/t5/fusion-design-validate-document/help-with-sketch-trim-command/td-p/5900460)
- "Press and hold to trim": dragging with the button held across several segments trims each one it crosses. [Tutorial, title only] — [LinkedIn Learning: Press and hold to trim](https://www.linkedin.com/learning/fusion-360-tips-tricks-and-techniques/press-and-hold-to-trim)
- Projected (linked) curves cannot be trimmed until their link is broken. Pattern-constrained curves cannot be trimmed until the pattern constraint is deleted. [Forum] — [Help with Sketch Trim command](https://forums.autodesk.com/t5/fusion-design-validate-document/help-with-sketch-trim-command/td-p/5900460)
- Extend lengthens to the nearest intersection with the same hover preview. If none exists, nothing happens. Users report that the end nearest the cursor is the one extended. [Official doc + Forum] — [Trim or extend](https://help.autodesk.com/cloudhelp/ENU/Fusion-Sketch/files/SKT-TRIM-EXTEND.htm); [extend tool in sketch](https://forums.autodesk.com/t5/fusion-design-validate-document/extend-tool-in-sketch/td-p/6487737)
- Break splits a curve where it crosses other geometry without deleting anything (hover to preview, click to break). [Official doc] — [Sketch modification tools](https://help.autodesk.com/cloudhelp/ENU/Fusion-Sketch/files/SKT-SKETCH-MODIFY-TOOLS.htm); [Forum] — [Splitting any line into segments](https://forums.autodesk.com/t5/fusion-design-validate-document/splitting-any-line-or-arc-circle-into-segments/td-p/6365115)

**Fillet / Chamfer**
- The sketch modify tools include Fillet and Chamfer. Chamfer types: Equal Distance, Distance and Angle, Two Distances. [Official doc] — [Sketch modification tools](https://help.autodesk.com/cloudhelp/ENU/Fusion-Sketch/files/SKT-SKETCH-MODIFY-TOOLS.htm)

**Offset**
- The dialog offsets a curve, a chain of connected curves or a profile. **Chain Selection** (on) picks all connected curves; only one selection set can be offset at a time. A Flip button (or a negative value) reverses the side. Double-click the offset glyph later to edit. [Official doc + Forum + Tutorial] — [Offset help](https://help.autodesk.com/view/fusion360/ENU/?contextId=SKT-OFFSET); [Offset Tool is Making me Crazy](https://forums.autodesk.com/t5/fusion-support-forum/offset-tool-is-making-me-crazy/td-p/9164143); [How do I edit Sketch offset direction?](https://forums.autodesk.com/t5/fusion-support-forum/how-do-i-edit-sketch-offset-direction/td-p/7587916); [Complete Guide to the Offset Tool](https://www.techandespresso.com/blog/fusion-360-offset-tool-guide)
- One search excerpt said newer Offset dialogs have a direction choice (One Side / Two Sides / Symmetric). Not confirmed on an official page. Treat as possibly a newer feature.
- Unchecking "projection link" during projection can fix chain-selection problems on projected curves, but leaves unconstrained copies. [Forum] — [Sketch offset bugs and weird behaviour](https://forums.autodesk.com/t5/fusion-support-forum/sketch-offset-bugs-and-weird-behaviour/td-p/8585862)

**Mirror / patterns**
- Sketch Mirror copies the selected curves across a straight line (construction or normal, never curved) and adds a **Symmetry** constraint. [Official doc] — [Create a sketch mirror](https://help.autodesk.com/view/fusion360/ENU/?guid=SKT-CREATE-MIRROR)
- Sketch Rectangular Pattern copies in one or two chosen directions (rows and columns). Sketch Circular Pattern copies evenly around a chosen center point. Individual copies can be suppressed in either. [Official doc] — [Sketch mirrors and patterns](https://help.autodesk.com/view/fusion360/ENU/?guid=SKT-SKETCH-CREATE-MIRRORS-PATTERNS)
- There is no sketch pattern along a path. Autodesk staff steer users to the solid Pattern on Path. [Forum, old] — [Sketch pattern along a path](https://forums.autodesk.com/t5/fusion-design-validate-document/sketch-pattern-along-a-path/td-p/7710089)

**Project / Include**
- Submenu: **Project** (edges or faces onto the sketch plane), **Intersect** (contour where the sketch plane cuts the model), **Include 3D Geometry** (edges, work geometry, sketch curves brought in as 3D), **Project to Surface** (sketch curves wrapped onto B-rep faces, with Closest Point or Along Vector). [Official doc] — [Project/Include](https://help.autodesk.com/view/fusion360/ENU/?guid=SKT-SKETCH-CREATE-PROJECT-INCLUDE); [Project to Surface](https://help.autodesk.com/view/fusion360/ENU/?guid=SKT-PROJECT-TO-SURFACE)
- Projected geometry stays associative (updates when the source changes) and shows purple. The link is removed via right-click **Break Link** on the geometry. [Official blog + Forum] — [How to Project Geometry onto a Sketch Plane](https://www.autodesk.com/products/fusion-360/blog/how-to-project-geometry-onto-a-sketch-plane-in-fusion/); [turn projected Sketch geometry into something useful](https://forums.autodesk.com/t5/fusion-design-validate-document/how-do-you-turn-projected-sketch-geometry-into-something-useful/td-p/6916478)

**Text**
- The Text dialog has two types: **Text** (inside a rectangular frame that can be dimensioned and constrained) and **Text On Path** (follows a selected curve and updates when the curve changes). Height is in document units. [Official doc] — [Reference: Text dialog](https://help.autodesk.com/cloudhelp/ENU/Fusion-Sketch/files/SKT-REF-TEXT-DIALOG.htm). Driving text height with a parameter is fragile: editing the text can replace the parameter with a fixed value. [Forum] — [Controlling text height with parameters](https://forums.autodesk.com/t5/fusion-support-forum/controlling-text-height-with-parameters/td-p/8981637)

**AutoConstrain (2025, version change)**
- January 2025: AutoConstrain released under a new **Automate** tab in the Sketch environment. It proposes candidate constraint and dimension sets, and the user picks one or clicks Generate More. [Official blog] — [AutoConstrain for Fusion is here!](https://www.autodesk.com/products/fusion-360/blog/autoconstrain-for-fusion-is-here/)
- May 2025: "AutoConstrain from Datum" (pre-select a datum). AutoConstrain is disabled when the sketch is already fully constrained. [Official blog] — [May 2025 Product Update](https://www.autodesk.com/products/fusion-360/blog/whats-new-may-2025-major-product-update/)
- July 2025: dimensions editable while the AutoConstrain dialog is open; diametric dimensions from centerlines; offset and Finish Sketch up to 4x faster. [Official blog] — [July 2025 Product Update](https://www.autodesk.com/products/fusion-360/blog/july-2025-product-update-whats-new/)
- November 2025: AutoConstrain detects and fixes small gaps, off-axis lines and near-tangent arcs, with a tolerance slider. Also a fix for slow extension of existing line chains. [Official blog] — [November 2025 Product Update](https://www.autodesk.com/products/fusion-360/blog/november-2025-product-update-whats-new/)

### Inferences
- Trim's "delete the whole curve if there is no intersection" rule plus drag-to-trim is cheap to copy and gives a strong Fusion feel.
- Every derived tool (Mirror, Offset, patterns, Project) leaves a persistent, editable relationship (a symmetry constraint, an offset glyph, a pattern constraint, a projection link) rather than plain copies. SciForge should model these as constraints or links, not one-shot geometry.

### Gaps
- Sketch Fillet details (pick two curves or a corner point, radius box, whether repeated fillets get equal constraints): not found in this session.
- Ellipse, Conic Curve, Point tool and Sketch Scale behavior: not researched (time budget).
- Control Point Spline handle display and degree options: not found.
- The Offset "Two Sides / Symmetric" option needs confirmation against the current help page.

## 6. Sketch Dimension tool

### Takeaway
Press D, pick one entity or two, move the mouse to choose the dimension type and placement, click to place, then type a value or expression in the edit box and press Enter. Circles get diameter dimensions and arcs get radius dimensions; right-click before placing to toggle. If a dimension would over-constrain the sketch, Fusion offers to create it as a driven (reference) dimension, shown in parentheses.

### Cited Findings
- Start from Sketch > Create > Sketch Dimension or press **D**. Single lines, parallel lines or two points give linear dimensions. Non-parallel lines give angular dimensions. Circles give diameters and arcs give radii. Type a number, reference another dimension or enter an expression, then press Enter. Move away from the geometry and click to place. [Official doc] — [Sketch dimensions](https://help.autodesk.com/view/fusion360/ENU/?guid=SKT-SKETCH-CREATE-DIMENSIONS); [Create dimensions (context help)](https://help.autodesk.com/view/fusion360/ENU/?contextId=SKT-CREATE-DIMENSIONS)
- Angular: after picking two lines, the side of the cursor picks which of the four angle quadrants is dimensioned. [Tutorial] — [How to Dimension Sketches in Fusion 360](https://productdesignonline.com/fusion-360-tutorials/how-to-dimension-sketches-in-fusion-360/)
- **Right-click before placing** opens options for that dimension, such as the radius/diameter toggle (the value is converted automatically) or **Driven**. [Official blog] — [5 Essential Right-Click Tricks for Sketch Dimensions](https://www.autodesk.com/products/fusion-360/blog/sketch-dimensions-autodesk-fusion/)
- Driving is the default. If the new dimension would over-constrain the sketch, Fusion shows a prompt of the form "Adding this dimension will over-constrain the sketch… Choose OK to create a Driven Dimension." Driven dimensions show their value **in parentheses** and appear read-only and greyed in the Parameters dialog. [Official doc + Forum] — [Sketch dimensions](https://help.autodesk.com/view/fusion360/ENU/?guid=SKT-SKETCH-CREATE-DIMENSIONS); [Automatically accept Driven Dimension](https://forums.autodesk.com/t5/fusion-design-validate-document/automatically-accept-driven-dimension/td-p/10507038); [Creating reference dimensions](https://forums.autodesk.com/t5/fusion-design-validate-document/creating-reference-dimensions/td-p/6395249)
- An existing dimension can be switched with right-click **Toggle Driven**. A driven dimension must be made driving before it can be edited (double-click to edit). [Forum] — [Swap driven dimension in over-constrained sketch](https://forums.autodesk.com/t5/fusion-support-forum/swap-driven-dimension-in-over-constrained-sketch/td-p/9386673)
- Users have asked for a preference to skip the driven-dimension prompt. None was confirmed. [Forum] — [Automatically accept Driven Dimension](https://forums.autodesk.com/t5/fusion-design-validate-document/automatically-accept-driven-dimension/td-p/10507038)
- Sources conflict on whether driven dimensions can be used in formulas or the Parameters list: the Fusion blog says yes, some forum users say no. [Official blog vs Forum] — [5 Right-Click Tricks](https://www.autodesk.com/products/fusion-360/blog/sketch-dimensions-autodesk-fusion/); contradicted by forum excerpts in [driven dimension with geometry constraint defect](https://forums.autodesk.com/t5/fusion-support-forum/driven-dimension-with-geometry-constraint-defect/td-p/8103328)
- Sketch dimensions can be shown and edited **outside** the sketch: right-click the sketch in the browser and choose Show Dimensions. [Official blog] — [View and Edit Sketch Dimensions Outside of Sketches](https://www.autodesk.com/products/fusion-360/blog/view-edit-sketch-dimensions-autodesk-fusion/)
- Autodesk recommends applying constraints before dimensioning. [Official blog] — [How to Create Dimensions in Sketches](https://www.autodesk.com/products/fusion-360/blog/dimensions-in-sketches-fusion/)

### Inferences
- Dimension names (d1, d2, …) become user-editable model parameters (implied by "reference an existing dimension" and the Parameters dialog mention). SciForge already has a Change Parameters dialog, so sketch dimensions should register there.
- The driven-dimension prompt is a good pattern to copy: never refuse a dimension, offer to make it a reference instead.

### Gaps
- Exact visual style of dimensions (arrow style, text color, extension lines) and the look of the inline edit box. Not described in found sources.
- Point-to-line and point-to-point dimension orientation rules (horizontal vs vertical vs aligned chosen by cursor position). Common CAD behavior but not confirmed for Fusion here.

## 7. Sketch Palette

### Takeaway
The Sketch Palette is a floating panel that appears while a sketch is active. It has a line-type selector (construction, centerline), a Look At button, display toggles (Sketch Grid, Snap, Slice, Show Profile, Show Points, Show Dimensions, Show Constraints, Show Projected Geometries, 3D Sketch), a tool-options area that changes with the active tool, and a Finish Sketch button.

### Cited Findings
- The palette controls "linetypes and visibility of objects like the Sketch Grid, Points, Dimensions, Constraints, and Projected Geometry on the fly while you sketch." [Official blog] — [How To Create and Modify Sketch Geometry](https://www.autodesk.com/products/fusion-360/blog/how-to-create-and-modify-sketch-geometry-in-fusion-360/)
- **Look At**: rotates the camera to face the active sketch plane. [Official doc] — [Sketch Palette reference](https://help.autodesk.com/cloudhelp/ENU/Fusion-Sketch/files/GUID-4183A4B7-E002-4396-AD5A-7FF3C8B2F33A.htm)
- **Slice**: "temporarily cuts through bodies where they intersect with the active sketch plane", removing material between the sketch and the camera. It is stored per sketch (the API exposes it as a sketch property). [Official doc + API] — [Sketch Palette reference](https://help.autodesk.com/cloudhelp/ENU/Fusion-Sketch/files/GUID-4183A4B7-E002-4396-AD5A-7FF3C8B2F33A.htm); [Sketch object (API)](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/Sketch.htm)
- **Sketch Grid** and **Snap** are separate toggles. Sketch points snap to the grid only when both are checked. [Tutorial] — [How to Use the Point Command](https://productdesignonline.com/tips-and-tricks/how-to-use-the-point-command-in-fusion-360/)
- **Show Profile** toggles the shading of closed profiles. When a profile won't close, Autodesk suggests turning on Show Profile and **Show Points** to find endpoints that are close but not touching. [Official doc] — [Sketch Palette reference](https://help.autodesk.com/cloudhelp/ENU/Fusion-Sketch/files/GUID-4183A4B7-E002-4396-AD5A-7FF3C8B2F33A.htm). Turning Show Profile off removes the profile shading. [Forum] — [Close a sketch to create a profile](https://forums.autodesk.com/t5/fusion-design-validate-document/close-a-sketch-to-create-a-profile/td-p/6972831)
- **Show Points**, **Show Dimensions**, **Show Constraints**, **Show Projected Geometries** each show or hide their item in the active sketch. [Official doc] — [Sketch Palette reference](https://help.autodesk.com/view/fusion360/ENU/?guid=GUID-4183A4B7-E002-4396-AD5A-7FF3C8B2F33A)
- **3D Sketch** lets lines and splines take points off the sketch plane by snapping to body vertices, work points and so on. [Forum] — [Sketch palette options](https://forums.autodesk.com/t5/fusion-design-validate-document/sketch-palette-options/td-p/5507033); [Official doc] — [3D sketch](https://help.autodesk.com/view/fusion360/ENU/?guid=SKT-3D-SKETCH). With 3D Sketch checked, "Auto look at sketch" is overridden. [Official support] — [Auto look at sketch stops working](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/Auto-look-at-sketch-stops-working-mid-session-in-Fusion-360.html)
- **Construction toggle**: available in the palette, or press X with the entity selected. [Tutorial via excerpt] — [Introduction to Sketch Tools and Options in Fusion 360 (VDCI)](https://vdci.edu/learn/cad/introduction-to-sketch-tools-and-options-in-fusion-360)
- Grid snapping ranks below alignment to existing points (if you want to align with a sketch point, you don't want the grid). [Forum, Autodesk staff via excerpt] — [Sketch palette options](https://forums.autodesk.com/t5/fusion-design-validate-document/sketch-palette-options/td-p/5507033)
- **Finish Sketch** is available in both the toolbar and the palette. [Official blog] — [Understanding The Fusion 360 Sketch Environment](https://www.autodesk.com/products/fusion-360/blog/fusion-360-sketch-environment/)
- If the palette goes missing, users find it again through the toolbar or by resetting the layout. [Forum] — [Sketch Palette Missing](https://forums.autodesk.com/t5/fusion-design-validate-document/sketch-palette-missing/td-p/6554878)

### Inferences
- Likely defaults (recollection, unverified): Sketch Grid on, Snap on, Slice off, Show Profile on, Show Points on, Show Dimensions on, Show Constraints on, Show Projected Geometries on, 3D Sketch off.
- The palette's top area changes per tool (for example, circle type while the Circle tool runs), so it doubles as the tool-options panel. SciForge can reuse its task-panel area for the same purpose.

### Gaps
- Official default states for each checkbox: not found.
- Exact current layout order and whether the line-type section has separate Construction, Centerline and Fixed buttons: not confirmed (the official reference page was not readable here).

## 8. Sketch grid

### Takeaway
The sketch grid is adaptive by default: major spacing and subdivisions change as you zoom. It can be switched to Fixed with a set major spacing and number of subdivisions via Grid Settings in the Grid and Snaps menu of the bottom navigation bar. Grid snapping needs both the Sketch Grid and Snap palette toggles on.

### Cited Findings
- Adaptive is the default. In Adaptive mode the grid changes spacing and subdivisions as you zoom, in both Sketch and 3D views. [Official support] — [Grid changes its spacing and subdivisions after zooming](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/Grid-changes-its-spacing-and-subdivisions-after-zooming-in-out-the-model-in-Fusion-360.html)
- Navigation toolbar > Grids and Snaps > Grid Settings: choose Adaptive or Fixed. Fixed sets the major grid spacing and the number of subdivisions. [Official support] — [How to edit your grid spacing](https://help.autodesk.com/view/fusion360/ENU/?caas=caas%2Fsfdcarticles%2Fsfdcarticles%2FHow-to-edit-your-grid-spacing-in-Fusion-360.html)
- The Grids and Snaps menu also has a **Layout Grid**, separate from the sketch grid. One user found that with Fixed and 1 inch spacing, gridlines still seemed to change with zoom. [Forum] — [Gridlines change when zooming even when Grid is "Fixed"](https://forums.autodesk.com/t5/fusion-support-forum/gridlines-change-when-zooming-amp-moving-project-even-when-grid/td-p/12366913)
- "Snap to Grid" in that menu makes grid intersections targets when moving objects. [Forum] — [Grid Snap.... How do I disable it?](https://forums.autodesk.com/t5/fusion-360-design-validate/grid-snap-how-do-i-disable-it/td-p/5451851)
- Sketch-level grid snapping needs both palette toggles (Sketch Grid and Snap). [Tutorial] — [PDO point command](https://productdesignonline.com/tips-and-tricks/how-to-use-the-point-command-in-fusion-360/)

### Inferences
- A practical adaptive rule: pick the major spacing from a 1-2-5 or 1-10 series so that major lines stay a comfortable number of pixels apart, with a fixed subdivision count. That is my design suggestion, not Fusion's documented algorithm.

### Gaps
- Default spacing values, major/minor line colors and weights, and whether the grid fades out at grazing angles: not found.
- Whether Snap is on or off by default in the Sketch Palette: not confirmed.

## 9. Entering and finishing a sketch

### Takeaway
Creating or editing a sketch rotates the camera to look straight at the sketch plane ("Auto look at sketch", on by default in Preferences > General > Design). A contextual Sketch tab appears in the toolbar with the Sketch Palette. Finish Sketch (in the toolbar and the palette) closes the tab and returns to the 3D design environment.

### Cited Findings
- "Auto look at sketch" is enabled by default. It rotates the view to face the sketch plane when a sketch is created or edited, and can be turned off under Preferences > General > Design. [Official support + blog] — [Auto look at sketch does not work or stops working](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/Auto-look-at-sketch-stops-working-mid-session-in-Fusion-360.html); [Understanding the Fusion 360 Sketch Environment](https://www.autodesk.com/products/fusion-360/blog/fusion-360-sketch-environment/)
- The view can flip or rotate unexpectedly when editing a sketch (the support article explains it is the look-at aligning to the sketch's orientation). [Official support] — [View flips or rotates when editing or creating a sketch](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/View-flips-or-rotates-when-editing-a-sketch-in-Fusion-360.html); also [Why Doesn't Fusion 360 Look Directly at the Sketch?](https://productdesignonline.com/tips-and-tricks/why-doesnt-fusion-360-look-directly-at-the-sketch/)
- "Once you finish defining a sketch, on the toolbar or in the Sketch Palette, click Finish Sketch. The Sketch contextual tab disappears from the toolbar and you return to the 3D design environment." Right-clicking a sketch can find it in the canvas or the Timeline. [Official blog] — [Understanding The Fusion 360 Sketch Environment](https://www.autodesk.com/products/fusion-360/blog/fusion-360-sketch-environment/)
- Edit a sketch later via browser > right-click > Edit Sketch. [Official support] — [How to delete sketch constraints](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/How-to-delete-sketch-constraints-in-Fusion-360.html)
- An Autodesk University handout by Jeff Strater (Fusion sketch team) covers sketch tips; listed for follow-up, contents not read. — [MFG121944 Fusion 360 Sketching: Tips to Get the Most Out of Your Sketch](https://static.au-uw2-prd.autodesk.com/Class_Handout_MFG121944_Fusion_360_Sketching_Tips_to_Get_the_Most_Out_of_Your_Sketch_Jeff_Strater.pdf)
- July 2025: Finish Sketch made up to 4x faster. [Official blog] — [July 2025 Product Update](https://www.autodesk.com/products/fusion-360/blog/july-2025-product-update-whats-new/)

### Inferences
- Recollection, unverified: Esc cancels the active sketch tool and returns to Select. A second Esc clears the selection. Esc does not finish the sketch. In the timeline, a sketch is one feature icon. Double-clicking it (or Edit Sketch) rolls the model back to that point and reopens the sketch.

### Gaps
- Esc behavior in the sketch environment: no source found.
- Timeline icon appearance and roll-back behavior for sketches: not covered (possibly in the navigation/timeline researcher's scope).
- Whether finishing the sketch restores the camera view from before sketch entry: not found.

## 10. Keyboard shortcuts in the Sketch environment

### Takeaway
Official default keys: L Line, R 2-Point Rectangle, C Center Diameter Circle, D Sketch Dimension, X Normal/Construction toggle, T Trim, O Offset, P Project, E Extrude, Q Press Pull, S toolbox/shortcut box, Shift+S Scripts and Add-ins. They are the same on Windows and macOS.

### Cited Findings
- Autodesk's official shortcut table lists: **L** Line, **R** 2-Point Rectangle, **C** Center Diameter Circle, **T** Trim, **O** Offset, **P** Project, **X** Normal / Construction, **D** Sketch Dimension. The sketch keys are identical on Windows and macOS. [Official] — [Autodesk Fusion keyboard shortcuts](https://www.autodesk.com/shortcuts/fusion-360)
- **S** is "Model Toolbox" in Autodesk's table (a searchable command box). Product Design Online calls it "Sketch Shortcuts" inside the sketch environment. **Shift+S** is Scripts and Add-ins in both. [Official + Tutorial] — [Autodesk shortcuts](https://www.autodesk.com/shortcuts/fusion-360); [PDO Autodesk Fusion Hotkeys](https://productdesignonline.com/tips-and-tricks/autodesk-fusion-hotkeys-keyboard-shortcuts/)
- **E** Extrude, **Q** Press Pull and other modeling keys work in the model workspace. [Official blog] — [15+ Essential Fusion Shortcuts](https://www.autodesk.com/products/fusion-360/blog/fusion-360-modeling-commands-shortcuts/); [SolidProfessor list](https://solidprofessor.com/blog/fusion-360-keyboard-shortcuts-thatll-increase-your-design-efficiency/)
- PDO lists **Spacebar** as Repeat Last Command. Not seen in the official excerpt. [Tutorial] — [PDO hotkeys](https://productdesignonline.com/tips-and-tricks/autodesk-fusion-hotkeys-keyboard-shortcuts/)
- Shortcuts are customizable (hover a command in the toolbar > three-dot menu > Change Keyboard Shortcut). [Official blog] — [Keyboard Shortcuts in Fusion](https://www.autodesk.com/products/fusion-360/blog/quick-tip-custom-keyboard-shortcuts/); [Shortcuts to Switch Between Sketching & Modeling](https://www.autodesk.com/products/fusion-360/blog/how-to-switch-between-sketching-modeling-environments-keyboard-shortcuts/)

### Inferences
- E (Extrude) works while a sketch is active and implicitly finishes the sketch. This matches typical Fusion workflow but was not confirmed in a source here.
- Keys SciForge should bind inside its sketch mode at minimum: L, R, C, D, X, T, O, P, plus Esc (cancel tool) and Delete (delete selected geometry, constraint or dimension).

### Gaps
- Official sketch-specific default shortcuts beyond those listed (Fillet, Mirror, Arc, Spline, Point, Polygon have none by default, as far as I recall; unconfirmed).
- Escape and Enter semantics in the sketch environment: not covered by any found source.
- Whether a Repeat Last Command key exists by default (Spacebar per PDO vs Enter in other CAD): unconfirmed.
