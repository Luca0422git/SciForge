# Session log: Fillet and Chamfer live picture (branch `wf/live-fillet`)

To be copied into MEMORY.md by whoever merges (this branch does not edit MEMORY.md). Started
from `experimental` (8af46ba). No FreeCAD core file changed (nothing for `core-patches.md`).

Follows yesterday's Draft work (`2026-10-22-draft-live.md`): there, the Draft dialog got a
picture that follows the angle handle at once while the exact solid waits for the mouse to
rest. Fillet and Chamfer did not have one: on a big part (a rebuild slower than 0.25 s) the
round did not move at all until the mouse rested.

STATUS: done (geometry, dialog wiring, unit tests, golden checks, GUI scenario); test runs
listed below.

## What changed (plain language)

**1. A live picture of the round or the bevel** (`sciforge/fillet_live.py`, arithmetic in
`sciforge/fillet_live_core.py`). While the radius or distance arrow is dragged, the dialog
draws, for every edge the step rounds:

- a **fillet**: the band the rolling ball sweeps. At sample points along the edge it takes the
  two faces' normals, works out where a ball of the radius touches both faces, and draws the
  arc between the two touch points (8 segments across). The arc's points are
  `edge point + radius x (a direction fixed per sample)`, so a new radius costs one
  multiply-add per point (numpy): about 0.05-0.4 ms for the cases tested.
- a **chamfer**: the flat band from distance 1 on one face to distance 2 on the other (Equal,
  Two Distances with Flip, Distance and Angle using the same law-of-sines formula as
  `fillet_core.angle_distance2`).
- **Chord Length** and **Variable** rows: the radius per sample (Chord: from the local corner
  angle; Variable: a smooth curve through the radius points, see "Limits" below).
- **fillet sets** (several rows, several radii), **Tangent Chain** on/off, **Rule Fillet**:
  the same edges as SciForge's own step builds (`fillet_live.plan` uses `fillet_sets`'
  own rules for which set owns which edge). Full Round has no arrow: no picture.
- the outlines: the two lines where the round meets the faces and the two ends.

Where two picked edges meet at a corner, each band is cut on the plane that halves the
corner (two equal rounds meet exactly there). Where an edge ends on a flat side face that is
not square to it (the end of a spline wall's top edge), the band is cut on that face.

The picture is drawn in the part's colour with dark outlines over the see-through part, never
clickable (Coin nodes the dialog owns). The preview solid is hidden while the picture shows.
The picture is made once per set of picks and options (a few ms), right after a preview,
while nothing happens, so the first mouse move does not wait for it.

**2. The dialog waits for the rest, like Draft** (`fillet_ui.BlendPanel`). A dragged arrow
shows the picture at once and asks for the exact rebuild with `schedule(settle=True)`; while
a picture exists for the current picks, `REST_FIRST` is on (a property: without a picture,
e.g. Full Round, the dialog paces itself as before). A typed size also shows the picture at
once. The exact solid comes when the mouse rests (0.2 s; longer while the button is held) or
is let go (`taskui.handle_released`).

**3. The picture goes away** when the exact result arrives (`_recompute`), when a size is
refused (`_failed`: no picture of a size that does not fit), when the picks change, on OK,
Cancel, Ctrl+Z (`cleanup`) and when the document closes (`_abandon`). Once the largest size
that fits is known, a drag past it is held there (value_limits, unchanged), so the picture
never shows a size past the limit. The exact result at OK is built the same way as on
8af46ba (nothing in the build path changed; every existing golden model still applies).

## How it is tested (correctness only)

Luca's decision (2026-10-23): timing and feel are tested by him on his own PC; nothing here is
tuned or checked on timings measured in the sandbox.

- `SciForgeTests/unit/test_fillet_live_core.py` (12 tests, plain Python): the round's points
  lie on the ball's circle, the ball is the radius away from both faces, the ends touch the
  faces, outside and inside edges, corner angles 30-150 deg, tangent faces refused; Chord
  Length and Distance and Angle give `fillet_core`'s sizes; the Variable law goes through its
  points and stays within 0.1 mm of OpenCASCADE's measured radius; corner cuts.
- Golden models, real FreeCAD headless: new check `live_blend_expect`
  (`SciForgeTests/golden/live_checks.py`, key registered in `schema.py`): builds the picture
  for a step's picks and sizes and measures every point against the faces of the exact result
  the step built. 16 new models `live_*.json` (copies of existing blend models plus two
  spline-wall models):
  exact (0.005 mm) for a single box edge, a box's top face (4 edges, corners), a slot's
  tangent chain (lines + half circles, also re-checked at radius 3.5 and back), an inside
  bracket edge, a boss feature's circle edges, Chord Length on 90 and 120 deg edges, two
  sets, Tangent Chain off, sets with their own Tangent Chain, chamfers (Equal on a top face,
  Two Distances flipped, Distance and Angle, chamfer sets with angle and flip), a spline
  wall's top edge (fillet and chamfer).
  Looser where the picture is knowingly approximate: Rule Fillet on all edges of a box
  (0.3 mm: where three rounded edges meet, the exact solid has a round corner patch, the
  picture shows the bands cut at the corner, ~0.23 mm off there); Variable radius (0.06 mm:
  OpenCASCADE's own smooth radius law).
- GUI scenario `fillet_live` (real input, 64 checks): box by sketch + extrude; Fillet on the
  front top edge: the picture is prepared while idle; a real held drag of the arrow: the
  picture shows during the moves, at the dialog's radius, lies on the exact round (checked
  mid-drag), no exact rebuild between the moves; let go: picture gone, no node left in the
  view, the exact round's volume. Dragged far: held just under 10 mm, no picture past the
  limit once known. Typed 3 + Tab: the picture at once, then exact. Typed 2.5 then Cancel:
  no picture left, no fillet. Chamfer Two Distances: the second arrow dragged, the band
  follows and lies on the exact chamfer; OK: nothing left. Fillet, typed 2, Ctrl+Z: dialog
  ends, nothing left in the view.

## Limits (honest)

- Exact for flat faces and for a flat face meeting a cylinder, a cone or an extruded wall at
  the edge. On doubly curved faces (a sphere, a free-form surface) the band is off by about
  r^2 x curvature until the mouse rests.
- Three or more rounded edges meeting at a vertex: the round corner patch is not drawn (the
  bands are cut at halving planes). A reflex corner (bands that should run past the vertex to
  meet) leaves a small gap in the picture.
- Variable radius: OpenCASCADE's radius law between the points is its own smooth curve; the
  picture uses a smooth cubic through the points (within ~0.09 mm of OpenCASCADE's radius on
  the tested edge).
- A size past the limit, before the limit is known: the picture shows it until the mouse
  rests; then the exact rebuild fails, the largest size that fits is found (at once, as
  before; not in the background like Draft's search) and the picture goes.
- Variable radius points' positions (not their radii) are not shown live (they rebuild on
  the rest as before).

## Tests run

(filled in at the end of the session)
