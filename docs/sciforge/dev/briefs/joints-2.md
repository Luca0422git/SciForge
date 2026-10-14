You are building one feature area of SciForge, a FreeCAD 1.1.4 fork that must behave exactly like Autodesk Fusion. The owner, Luca, is a beginner who only tests; he wants the finished product, so build the whole area, not a slice. Wave 4 closes the gaps listed at the end of the parity docs (`docs/sciforge/dev/remaining-gaps.md` is the survey).

## Your area: Joints, part 2 (drag, motion, positions), branch `sf/joints-2`

Joints exist (`joints_core.py`, `joints.py`, `joints_ui.py`; read `docs/sciforge/parity/joints.md` to the end and the joints session log). Build:
1. **Component Drag**: dragging a component in the canvas with the left mouse moves it within its joints' degrees of freedom (a revolute joint turns, a slider slides, a free component moves on the view plane; grounded and rigidly grouped parts stay; limits are respected), live, one undo step per drag; Fusion's "Capture Position" prompt when the design has history (joints already have Capture Position / Revert). Coordinate: this is the only place a canvas drag moves components (components-2 builds the Move dialog).
2. **Joint position modes**: Fusion's Joint dialog Mode for each joint origin: Simple, Between Two Faces, Two Edge Intersection (and the snap points it offers); the joint origin preview.
3. **Motion Link** (link two joints' motion with a ratio/distance, e.g. gear and rack; Fusion's ASSEMBLE > Motion Link: drives one when the other moves, Reverse, Animate).
4. **Contact Sets** (Enable Contact Sets, New Contact Set of bodies: dragging stops where they touch; a coarse collision check by bounding boxes then OCC distance is fine).
5. **Motion Study** (a timeline of joint values over steps with Play, as in Fusion's Motion Study dialog), if time allows.
6. Fix the docs' open items: nested components move on their own, free joints are not auto-grounded.
Scenarios `joints2_*.py` (8+ paths: drag a revolute arm 90° (angle measured), drag a slider to its limit, a free component dragged on the view plane, a grounded part does not move, a joint origin Between Two Faces, a motion link gear/rack (one turn → the rack moves 2πr), contact sets stop a drag, capture position / revert, undo/redo, save/reopen). Unit tests for the Qt-free maths (DOF projection of a drag, motion link ratio). Update `docs/sciforge/parity/joints.md`.
