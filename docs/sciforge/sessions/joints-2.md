# 2026-10-14: Joints, part 2: drag, motion, positions (branch `sf/joints-2`, wave 4)

Spec, sources and gaps: `docs/sciforge/parity/joints.md` (sections "Dragging components",
"Position modes", "Motion Link", "Contact Sets", "Motion Study", "Nested components", the
Ground paragraph, Known gaps, Tests). No core patch (no full build needed).

## What was built

- **Component Drag** (`joints_drag.py`): a plain left drag that starts on a component (an
  `App::Part`, or a root body jointed / grounded / in a rigid group or contact set) moves it
  along its joints, live: Revolute turns (a dial: the angle the pointer goes round the axis;
  seen edge-on, the nearest point of the circle), Slider slides (the point of its line nearest
  the pointer's ray), Cylindrical / Pin-Slot both, Planar in its plane, Ball about its centre;
  a component held by nothing moves in the view plane. Limits clamp, motion links follow,
  contact sets stop it where parts touch, the solver brings closed loops along (the drag
  stops where they cannot follow). Grounded parts (and parts rigidly held to them) do not
  move and a note says why. One undo step per drag ("Drag <name>"); Esc puts everything back.
  `joints.drag_plan` decides what moves (the first joint with a motion on the way from the
  pressed part to the ground, or to the part a free group hangs on). Reached through
  `selection_ui`'s view filter (no Shift / Ctrl, not inside a command, not in paint mode).
  SELECT > Component Drag (a remembered tick, on by default, reset by the test harness).
- **Capture Position prompt** (`joints_ui.position_prompt`): Joint, As-built Joint, Joint
  Origin and Rigid Group first ask when components were moved since the last captured
  position (designs with history only): Capture Position / Revert / Cancel, then the command
  opens.
- **Position modes** (`joints_ui.PositionSlot`, `joints.mode_snap`, `mode_frame`,
  `joints_core.midplane`, `line_intersection`): Simple, Between Two Faces (Plane 1, Plane 2,
  then a snap brought onto the halfway plane; the hover shows the projected snaps), Two Edge
  Intersection (Edge 1, Edge 2, where they meet extended; arcs give their end tangent), in
  the Joint dialog (one Mode per component), the As-built Joint's Position and Joint Origin.
  Stored as "twofaces" / "twoedges" records, so they follow later geometry changes; edit
  shows them again.
- **Motion Link** (`joints_motion_ui.MotionLinkPanel`, `joints.create_motion_link`,
  `follow_links`): two joints, a value each (angle / distance, a Rotate / Slide choice for a
  joint with both), Reverse, Animate; both ways; a timeline step and a row in the Joints
  folder; deleted with either joint. Turning joints now count whole turns
  (`SciForgeAngle`, kept in captured positions too): a pinion driven to 360 reads 360.
- **Contact Sets** (`ContactSetPanel`, `joints.contact_pairs`, `overlapping`): Disable
  Contact / Enable Contact Sets / Enable All Contact (ticked entries of ASSEMBLE, saved with
  the design), New Contact Set (Contacts folder in the browser); a drag and Drive Joints stop
  where parts touch (boxes, distance, then common volume; the move halved 12-14 times).
- **Motion Study** (`MotionStudyPanel`, `joints.study_pose`): joints, points (step 0..100,
  value), playhead, Play Once / Loop / Ping-Pong, speed; a Motion Studies folder at the top
  of the browser; parts go back when the dialog closes.
- **Nested components move on their own**: `joints.is_part` takes every `App::Part`;
  `part_of` returns the nearest component; placements are moved in design coordinates
  (`global_placement`, `set_global_placement`, `move_parts` skips a part inside another
  moving one); for each solve the nested parts hold their global place as their Placement
  (FreeCAD's solver reads Placement as a place in one frame) and get their own back after.
- **No automatic ground**: `ensure_ground` is gone (Joint, As-built Joint, Rigid Group).
  Hidden `AutoGround` helpers hold each free group of jointed parts (by component 2 of its
  oldest joint) only inside `joints.solve`. FreeCAD's own solve on recompute is off while
  SciForge is on (`theme.VIEWER_SETTINGS`), and `joints_ui.Watch` solves after a recompute
  when a joint is no longer satisfied.
- Fixed on the way: a Slider whose Slide axis is X (or Y) when it is first aligned was
  turned over and broken (the heading was kept about the motion axis instead of the face
  normal); a drag right on a joint's glyph now reaches the component under it; the
  browser's Rename did nothing on joint, rigid group (and new) rows (kinds missing from
  `RENAMABLE`).

## Tests (real FreeCAD 1.1.4, real input)

- Unit: `test_motion_core.py` 31 new tests (drag maths, links, contact search, studies,
  midplane, line intersection); all 934 unit tests OK.
- New scenarios: `joints2_drag` 78, `joints2_slider` 75, `joints2_modes` 70,
  `joints2_motion` 99, `joints2_nested` 55 checks, all PASS (alone and together in one
  profile).
- Older scenarios re-run and PASS: `joints_basic` 85, `joints_types` 229,
  `joints_asbuilt_group` 133, `joints_drive` 107, `joints_components` 46 (texts updated: no
  ground is added any more), `selection_box` 46, `selection_dialogs` 28, `selection_filters`
  59 (the Component Drag tick is not a mode), `selection_other` 30, `selection_sketch` 15,
  `ribbon_sweep` 214, `components_basic` 251, `components_extrude` 170, `components_move` 218.

## FreeCAD facts and traps found

- `AssemblyObject::solve` takes each moving part's `Placement` as its place in the world and
  works its markers out relative to the reference's root object (`root.getPlacementOf(sub,
  obj)`, i.e. in the root's parent frame): parts that sit in different parent frames (a
  nested `App::Part`) are mixed up. `UtilsAssembly.getGlobalPlacement` climbs `Parents` and
  is truly global. A moving part is the reference's first object (`getMovingPartFromRef`).
- `getGroundedParts` skips a `GroundedJoint` whose `ObjectToGround` is None: helpers can be
  pointed at a part only while a solve runs.
- `AssemblyObject::execute` solves on every recompute unless
  `Mod/Assembly/SolveOnRecompute` is False; a joint touches the assembly through its
  references, so every placement change of a jointed part ends in a solve on the next
  recompute.
- `preDrag` / `doDragStep` / `postDrag` (FreeCAD's own drag solver) are C++ only, not in
  `AssemblyObjectPy`: SciForge's drag is Python (drive the joint, then solve).
- `view.getObjectsInfo(pixel)` lists everything under the pointer (a joint's glyph first):
  used to grab the component under it.
- Under xvfb (no window manager) the main window is not active again after a modal
  `QMessageBox` closes, so window shortcuts (the dialogs' Esc, `preview.EscapeCancels`) stop
  firing: the prompt calls `activateWindow()` after it closes.
- Scenario trap: Create Sketch's origin squares are sized from the **active body**
  (`sketch_ui.PlanePicker`: max(20, 1.3 x its box)). After a small New Body (10 mm), a click
  on the XY plane at (12, -8, 0) misses the square and the sketch lands on XZ. Click inside
  +-10 mm (the motion scenario uses (5, -3, 0)).
- Scenario trap: a box's top-face centre has the joint's glyph drawn over it; click a few mm
  away from it when the click must reach the body.

## Gaps (what Fusion does that was not built, why)

- Fusion's drag solver pulls a whole mechanism toward the pointer through several joints;
  SciForge drives the first joint with a motion on the way to the ground (FreeCAD's drag
  solver is not reachable from Python).
- Contact does not stop Animate Joint or a motion study's playback (drags and Drive Joints
  only); contact is coarse (solids' common volume).
- Motion Study has no graph (points are typed and listed); its mode names other than Loop
  are guesses; contact sets are not in the timeline (guess).
- Between Two Faces takes the two faces and the snap on one body.
- The POSITION panel still lives in the ASSEMBLE menu; Fusion's prompt says Continue where
  SciForge says Revert / Cancel; the Component Drag tick shows in every design (Fusion: direct
  designs).
- Lock Motion, Animate Joint Relationships: not built.

## For the merger (files of other areas touched, small and marked)

- `selection_ui.py`: `_Press.dragging`; `_ViewFilter._component_drag` called where a box
  would start; `_moved`, `_released`, `_drop` and Esc in `_key` hand the drag to it.
- `theme.py`: one `VIEWER_SETTINGS` entry (`Mod/Assembly/SolveOnRecompute` False).
- `browser_core.py`, `browser_ui.py`: kinds `motion_link` (Joints folder), `contact_set`
  (Contacts folder), `motion_study` (Motion Studies folder at the top); joint rows renamable.
- `timeline_core.py`: kind `motion_link`. `bodies_gui.py`: three step icons.
- `ribbon_config.py`: ASSEMBLE Motion Link, contact entries, Motion Study; SELECT Component
  Drag (one entry each). `tools/sciforge/make_icons.py`: icons motion_link, contact_set,
  motion_study, component_drag.
- `SciForgeTests/gui/harness.py`: `prepare()` resets Component Drag.
- `SciForgeTests/gui/scenarios/selection_filters.py`: the "ticked mode" check leaves the
  Component Drag tick out.
- components-2 builds the Move dialog: a component moved there is a moved position for
  Capture Position / Revert too (`joints.remember_places(doc, parts)` before moving keeps
  Revert right); this branch is the only place a canvas drag moves components.
