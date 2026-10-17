# 2026-10-16: the 3D view and handles, Phase 3 of Luca's list (branch `sf/view-3`)

Plan: `/root/.claude/plans/fancy-hugging-horizon.md`, items F11-F14 (F15 was already built:
Move's value boxes). Specs with sources: `parity/ui-shell.md` ("Origin planes, axes and turn
handles"), `parity/direct-modify.md` (Align A7-A10), `parity/selection.md` (Body priority
hover, a gate FreeCAD dropped), short notes in `parity/revolve.md` and `parity/bodies.md`.
No core patch (no full build needed).

## What was built

### F11 Origin planes red / green / blue, smaller, labelled
- `origin_look.py` (new, colours and sizes are plain data, unit `test_origin_look`): one
  colour per axis (X red, Y green, Z blue, the values Revolve's axes had); a plane takes the
  colour of the axis it faces (XY blue, XZ green, YZ red); see-through (0.80), under the
  mouse brighter, less see-through (0.55) with a 3 px outline; a screen label (SoText2 in an
  SoAnnotation, 16 pt) "XY" / "XZ" / "YZ" near the corner farthest from the part's centre;
  `SquareLook` builds and paints one square.
- Size: 0.6 x the largest side of the design's visible bodies (`sketch_ui.design_box`, in the
  active body's axes; was 1.3 x the active body), at least 20 mm; 100 mm in an empty body
  as before (the view is framed on them). One size per square
  (`origin_look.square_sizes_for`, `PlanePicker.sizes` / `half_of(role)`): a square the
  parts hide round the origin sticks out of them by 15 % of their size (at least 5 mm):
  XY under parts covering the origin, XZ / YZ through parts on both sides of them (out of
  their nearer side or above their top). Found by the sweep: without it a box centred on
  the origin hid every square (Split Body could not take XZ). `primitives_ui` keeps its
  design-wide sizing (`design_box`, `PlanePicker.resize`).
- `sketch_ui.PlanePicker` uses it; its subclasses (Construct's `_origin_planes_class`, the
  patterns' `front_planes`, primitives' `DesignPlanes`) light squares through the new
  `PlanePicker.light(role)` (the copied IDLE / HOVER loops are gone). The Mesh plane cut's
  own squares look the same.
- Because the squares are smaller, a square drawn **in front of** the part now takes the
  click where it is drawn (`PlanePicker._not_behind`): with the old rule (any face under
  the mouse takes the click) the XZ square of a thin plate centred on the origin could not
  be clicked at all (insert_svg). A face lying in the square's plane keeps the click: the
  tie is measured square to the plane (2 % of the half size), not along the line of
  sight (a tube's side seen at a grazing angle is drawn as facets well behind the plane
  along the line of sight: surface_boundary_fill).
- Axis lines: Revolve's / Construct's (`revolve_ui.AxisPicker`) and the patterns'
  (`pattern_ui.AxisPicker`, now in the shared colours) carry an "X" / "Y" / "Z" label on
  their + half (40 % out: their ends are often off the screen).

### F12 Angle snapping and the protractor wheel
- `angle_snap_core.py` (new, unit `test_angle_snap_core`): snap to multiples of 45 degrees
  when within 6 px of arc along the ring as drawn (1..4 degrees); Ctrl held = raw;
  Incremental Move on = its steps (and a step on a 45 multiple lights its tick).
- `protractor.py` (new): `snap_angle(view, raw, centre, axis, zero, radius)` (Ctrl from
  `QApplication.keyboardModifiers()`, ring size from `getPointOnViewport`) and
  `ProtractorRing` (ring, ticks every 15, longer at 45, longest at 90, the snapped tick lit
  yellow, a dashed needle, "90.0 deg" text), `Wheel` (show / update / hide), `WHEELS` and
  `LAST` for tests.
- Applied in `revolve_ui.AngleHandle` (Revolve, Move's Rotate handle, and through
  `handles3d.angle_handle` Plane at Angle, Section, Emboss, the Mesh plane cut; Surface's
  revolve), `move_ui.Triad` turn handles, `extrude_ui.AngleDragger` (taper, Draft's disc,
  the patterns' Total Angle disc, Insert's and Decal's turn discs). `handles3d._stepped_angle`
  is gone: Incremental Move's steps are the handle's own now (the drawn handle shows them
  too, it used to show the raw angle).

### F13 Align: which point of a face or edge
- `align.snap_points(obj, sub)` (joints' `_shape_snaps` on the global shape: a face's centre,
  corners, edge middles, circle centres; an edge's centre / middle / ends) and
  `align.at_point(frame, point)` (the face's normal kept).
- `align_ui`: a `joints_ui.SnapHover` subclass (`_snap_hover_class`) shows the dots of the
  face or edge under the mouse (bigger dots than joints', no triad); the dot within 14 px of
  the pointer is lit, else the first (centre); From and To take the lit dot. Ctrl held keeps
  the face's dots (the click on its corner or edge is then taken as the face at that dot).
  Frames are stored, so an edit keeps the snapped points.

### F14 Body priority hover inside tools
- `selection_ui`: the hover is a SoLocation2Event callback on each view (`_watch_hover`,
  `_hover_moved`); FreeCAD runs it right after its own preselection of the same move, so the
  body is lit again before the view is drawn (no blink). It runs while a non-sketch edit mode
  is on (Coil, Pipe, a construction); `_sketch_edit()` replaces `_in_edit()` there.
- `_body_target(info)`: the body or loose solid (`analysis.body_of`, plus a loose solid in a
  component) and its selection path; a body in a component is lit and clicked as
  `Part.Body001.` (`_body_element`; `_Element.is_selected` reads the path).
- `_gate_lost()` / `_refresh_gate()`: a refused kind preselected while no command is open
  means FreeCAD's C++ gate replaced SciForge's and was removed: the gate is put back.

## FreeCAD facts and traps (for the next session)

- `SoFCUnifiedSelection::handleEvent` preselects first, then traverses its children; the
  view's `SoEventCallback` (`view.addEventCallback`) is one of them, so a Python
  SoLocation2Event callback runs after FreeCAD's preselection of that very move (a
  `QTimer.singleShot(0)` from a Qt event filter runs later, possibly after a redraw).
- `SelectionSingleton::setPreselect` calls `rmvPreselect()` before asking the gate: a refused
  element under the mouse clears whatever was preselected, every move.
- `Gui.Selection.setPreselection` defaults to MsgSource Internal: the gate is not asked.
- No Python getter for the active selection gate; a C++ `addSelectionGate` silently replaces
  (deletes) the Python one.
- With preselection mode OFF on the unified selection node, programmatic SetPreselect is not
  drawn either (do not use it to stop FreeCAD's own preselection).
- `QTest.mouseMove` / `mouseClick` are spontaneous events and set
  `QApplication.keyboardModifiers()` to their own modifiers (none): a test holding Ctrl must
  send its moves with `ControlModifier` (or by `sendEvent`, which leaves the state alone).
- `SoRotateDiscDragger` computes each motion from where the press began: setting its
  `rotation` between motions (the snap) does not add up.
- `SoSearchAction` skips inactive `SoSwitch` children unless `setSearchingAll(True)`.
- Scene nodes are added from timers (the handles' polls), never inside a Coin mouse callback.
- A sketch's shaded area (sketch_area_pick) steps back when the mouse comes over it: what
  `getObjectInfo` finds at a pixel can change once the mouse is there (a face lying in a
  plane appears). A test that aims must look again with the mouse there.
- FreeCAD's isometric camera looks from (+X, -Y, +Z): a click on the XY square at (a, -a, 0),
  the XZ square at (a, 0, -a) with 2a beyond the half size, the YZ square at (0, -a, a) has
  no other square in front of it. Squares behind the clicked point count too (a click beside
  a smaller XY square can land on the XZ square behind it).

## Tests (real FreeCAD 1.1.4, one profile per run)

New scenarios: `view_origin_planes` (53 checks), `view_angle_snap` (47), `modify_align_points`
(225), `selection_filters` extended with G-I (75): all pass. Unit: `test_origin_look`,
`test_angle_snap_core` (1256 unit tests pass). `--only base` (unit, golden, smoke, journey):
all pass on the final code.

Regression sweep of the brief's areas (revolve*, patterns*, inspect_construct*,
shell_draft*, bodies_move, modify_align*, selection_*, primitives_*, insert_*, surface*,
mesh_plane_cut, emboss_*, inspect_section, joints*, pi5_case, view_*): all pass; the
scenarios the sweep found failing were fixed and re-run alone on the final code
(revolve_axes, revolve_qa, revolve_qa_more, surface_boundary_fill, bodies_qa, bodies_split,
components2_bodies, view_origin_planes pass). The rest of the suite (list B, about 230
scenarios that pick origin squares) was converted to `plane_input.click_square` where a
step picks a square, but not swept to the end in this session (time): the next full CI run
is the check for it.

Scenario changes: a step that picks an origin square at a fixed point beside the part now
aims where the square shows (`SciForgeTests/gui/plane_input.py`: a spot nothing covers, well
inside the square, re-checked with the mouse there); `bodies_steps.box_steps` and the
joints / fixpattern / sketch_tools helpers do the same.

## Not built (and why)

- Sketch lines' 45-degree snap and the sketch's Rotate: the sketch area (sf/sketch-3) /
  FreeCAD's `Sketcher_Rotate`.
- The snap tolerance is in the view's device pixels (a high-DPI screen pulls a little less).
- Align's dots on sketch points and construction points: faces and edges only.
- Body priority clicks inside edit-mode tools (Coil, Pipe, construction) stay FreeCAD's (the
  hover lights the body; those tools take faces, planes and paths, not bodies).
- Construct's own origin squares keep "the part under the mouse takes the click".

## Shared files touched (for the merger)

`sketch_ui.py` (PlanePicker only), `construct_ui.py`, `pattern_ui.py`, `primitives_ui.py`,
`revolve_ui.py`, `mesh_cut_ui.py`, `move_ui.py`, `extrude_ui.py`, `handles3d.py`,
`align.py`, `align_ui.py`, `selection_ui.py`; test helpers `bodies_steps` callers and
`joints_steps.py` (the XY pick point moved from (12, -8, 0) to (6, -6, 0)).

## Follow-up on the integrated code (branch `sf/fix-vw`, 2026-10-17)

- A face of the part keeps the click where a see-through origin square is drawn in front
  of it again (the depth rule of view-3 is dropped): 0.6 x a wide design makes the XZ square
  stand far above a flat part, and it took clicks meant for the top face (modeling2_bodies
  part 5: the top sketch went onto XZ; patterns_circ: the hole's sketch on the disc's top
  went onto XZ). In exchange the vertical squares stick out *beside* a part lying on both
  sides of them (not above it, where the top face is behind them).
- Revolve's angle handle seen edge-on: the drag adds small steps; they were added to the
  snapped angle and pulled back onto it every time, so the handle never moved
  (revolve_qa_bodies P19). The steps now add to the hand's own (unsnapped) angle.
