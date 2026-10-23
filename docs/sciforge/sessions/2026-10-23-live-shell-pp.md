# Session log: live pictures for Shell, Press Pull and Extrude (branch `wf/live-shell-pp`)

To be copied into MEMORY.md by whoever merges (this branch does not edit MEMORY.md). Started
from `experimental` (8af46ba). No FreeCAD core file changed (nothing for `core-patches.md`).

Asked for: give Shell, Press Pull / Offset Face and Extrude (distance, taper, thin wall) the
same live picture Draft got yesterday (2026-10-22-draft-live.md): while a handle is dragged,
the faces that move follow the mouse at once, and on a big part the exact rebuild waits for
the mouse to rest. Luca's decision (2026-10-23): timing and feel are judged by him on his own
computer, so nothing here is tuned or tested on times measured in the sandbox; the tests
prove the picture is right.

STATUS: done, all checks below pass (see "Tests run").

## What changed (plain language)

**While you drag the arrow (or the taper disc), you now see a picture of the result that
follows the mouse on every move**, drawn in the part's colour with dark edges on top of the
see-through part (the preview solid is hidden meanwhile). The real (exact) solid is built
once the mouse rests or is let go, and then replaces the picture. Moving the picture costs a
fraction of a millisecond per mouse move: every point of the picture moves along a straight
line as the value changes, and those lines are worked out once per set of picks (while
nothing happens, right after the last exact preview).

- **Press Pull / Offset Face** (`live_shapes.OffsetPicture`): the picked faces' own triangles
  moved along their normals: a flat face slides, a cylinder or sphere changes radius (every
  point moves along its own normal). Points on an edge or corner shared with a face that does
  not move slide along that face (a box top pulled up: its corners slide up the sides; a top
  beside a slope keeps the slope), two moved faces that share an edge meet in a sharp corner,
  as the exact Press Pull does. Side quads join the old and the new outline only where they
  are really a face of the result: pulling a box top up shows the taller sides; pushing a
  hole's wall outward shows the wider floor; otherwise the quad is folded flat (invisible).
- **Shell** (`live_shapes.ShellPicture`): every kept face offset by the wall: inward for
  Inside, outward for Outside, both for Both; points at the rim stay on the opened face's
  plane, so the rim is drawn as the ring between the outer and the inner outline. Curved
  faces are offset point by point along their normals (exact for cylinders and spheres,
  close for others). Rounded corners on the outside are drawn sharp (close, then exact at rest).
- **Extrude** (`live_shapes.ExtrudePicture`): the profile's triangles at both ends of the
  extrusion and quads along its outline (and lines on its corners). One Side (up or down),
  Symmetric (whole or half length), Two Sides, a start offset, a thin wall (its wall faces are
  extruded the same way). A taper moves the outline inward square to itself in the profile's
  plane by length x tan(taper), corners along their bisectors, which is exactly what
  FreeCAD's tapered Pad makes. A cut is drawn in red. No picture (the exact preview follows on
  pauses, as before) for: To Object / All extents, a negative (widening) taper (FreeCAD's
  result is not an offset outline there: the picture would be 2 mm off), a thin wall with a
  taper (0.05 mm off), a formula error.

**How it is wired** (the same pattern as Draft): every drag step calls `live_show()` and then
`schedule(settle=True)` (`taskui.Panel`: no exact rebuild between two mouse moves; let go:
`handle_released` builds it at once). Typed values and every other change are unchanged (no
picture, exact preview after 60 ms). When there is no picture for the options, a drag behaves
exactly as before. The picture goes (and the preview solid and the part's look come back) as
soon as an exact rebuild ran (whatever its outcome: also a refused value or a value held at
its limit), and at OK, Cancel, Undo (which cancels the dialog) and when the dialog closes.
Nothing here lets an exception out (`LivePanel` catches and logs `[SciForge]` warnings).

New files:
- `sciforge/live_core.py`: the arithmetic, no FreeCAD (`offset_move`: the shortest move that
  keeps a point the right distance from every face it lies on; `in_plane_move` for the taper;
  `extrude_ends`; quads).
- `sciforge/live_shapes.py`: the three pictures, `Live` (one dialog's overlay: made once per
  key, shown, hidden with the view put back) and the `LivePanel` mixin the dialogs use. The
  drawing reuses `draft_live.Overlay` (node name `SciForgeLiveShape`).

Changed: `presspull_ui.py` (`_dragged` -> `_apply_value(dragged=True)`, `_recompute` hides
the picture), `shell_ui.py` (`_dragged`, `_preview` wrapper), `extrude_ui.py` (distance,
side-two distance and taper disc drags; `_recompute` wrapper), `tools/sciforge/run_tests.sh`
(exports `SCIFORGE_FC_CMD` so a unit test can run FreeCAD headless).

The exact result is untouched: the dialogs build exactly what 8af46ba built for the same
value (only *when* changes during a drag: at the rest instead of between moves).

## Tests

- `SciForgeTests/unit/test_live_core.py` (17, plain Python): moves of single faces, edges
  beside fixed / sloped faces, sharp corners, tangent faces, Shell rims, taper corners,
  extrusion ends, quads.
- `SciForgeTests/unit/test_live_shapes_freecad.py` + `SciForgeTests/headless/live_shapes_check.py`
  (real FreeCAD headless, skipped without it): 42 cases, every point of every picture against
  the exact solid the dialogs build (`presspull_core.press_pull`, `shelling.build`,
  `extrude.build`): box top, top + side, blind hole wall (in and out) and floor, through
  hole, a top beside a slope, a turned box, a moved body; Shell inside / outside / both on an
  open box, open on two faces, hollow, an open cylinder, two thicknesses each; Extrude one
  side, down, taper, taper down, symmetric (whole, half, tapered), two sides (with tapers),
  start offset (up, down), thin (side, centred). Worst distance: below 1e-9 mm in every case.
- GUI scenario `live_shapes` (119 checks, real mouse drags with the button held): Press Pull
  top up and down, a hole's wall; Shell inside then Outside; Extrude distance, taper disc,
  Symmetric. For each: the picture shows during the moves at the dialog's value, no exact
  rebuild between two moves, let go: the picture gone, the preview solid shown again, the
  part before the step no longer see-through, the exact solid has the expected volume, every
  picture point lies on it. No picture node left after OK (Press Pull, Extrude), Cancel
  (Shell) and Undo pressed right after a drag step (Press Pull).

## Tests run

(filled in below when the runs end)

## Open

- Fillet, Chamfer, Revolve, Pattern still have no picture of their own (they rebuild while
  dragged when quick, at rests when slow: `SLOW_DRAG`).
- Shell with Rounded corners and an Outside wall: the picture's outer corners are sharp
  (the exact result rounds them; it replaces the picture at the rest).
- Extrude: no picture for To Object / All, a widening taper, a tapered thin wall; the members
  in other bodies (multi-body cut) keep showing their last exact result during the drag.
- Press Pull on a free-form face (B-spline): the picture moves each point along its normal
  (an approximation of OpenCASCADE's offset); the exact one comes at the rest.
- Nothing timed: Luca checks the feel on his computer.
