# Parity spec: Hole (H) and Thread (outline 7.6)

Source: Fusion's documented behaviour and everyday use. Not yet checked against Luca's own
screen captures (outline 2.4). Implemented in `src/Mod/SciForge/sciforge/hole_ui.py` (Hole
dialog and command), `sciforge/hole.py` (the geometry rules, no GUI; on top of FreeCAD's
`PartDesign::Hole` with Refine on), `sciforge/thread_ui.py` + `sciforge/thread.py` +
`sciforge/thread_core.py` (Thread, a SciForge timeline feature), `sciforge/thread_tables.py`
(ISO metric and Unified sizes, the same rows as FreeCAD's Hole). Status: **first pass, not yet
signed off**.

## Hole: what the user does (and what SciForge does)

| Fusion | SciForge |
|---|---|
| CREATE > Hole or `H`; with nothing selected the dialog waits for a face | Same; it says "Click a face ..." and changes nothing until then |
| Placement **Single Hole**: click a face, the hole is where you clicked | Same, on flat and curved faces (on a curved face the hole goes in square to the surface at the click). Under the hood a hidden sketch "Hole N Sketch" with one point sits on the face; the hole and its sketch are one undo step |
| Click elsewhere on the face (or another face) to move it; drag the centre point | Same: the blue dot is dragged over the face; X / Y fields show and take the position on the face |
| **Reference**: click up to two edges, type the distances from them | Same: the distances are constraints to the edges, so the hole follows them when the part changes (golden `hole_references_follow_edge`). Two parallel edges cannot both be references |
| Placement **From Sketch (Multiple Holes)**: click sketch points (circle centres too) | Same; click a picked point again to drop it. A sketch selected before `H` starts From Sketch with all its points. Holes drill into the part (turned round by themselves for a sketch under it; **Flip** turns them) and the used sketch is hidden on OK |
| **Extents** Distance / To / All | Same. To: click a face or an origin/construction plane (also in the browser) |
| **Hole Type** Simple / Counterbore / Countersink | Same, with counterbore diameter and depth, countersink diameter and angle |
| **Hole Tap Type** Simple / Clearance / Tapped | Same. Clearance: ISO 273 (Close / Normal / Loose) or ASME B18.2.8 by thread size. Tapped: Thread Type (ISO Metric profile, ANSI Unified Screw Threads), Size, Designation, Class, Direction, **Modeled**, Full Tap Depth / Tap Depth. The size starts from the hole's diameter; the diameter becomes the tap drill or clearance size |
| **Drill Point** Flat / Angle (118 deg) | Same. The depth is measured to the end of the full diameter; the point comes on top |
| Blue arrows: depth, diameter | A blue arrow above the hole sets its depth (drag it down to drill deeper), one at the rim the diameter (Simple tap type) |
| A tapped hole that is not modeled shows a thread texture | Drawn as a dashed helix inside the hole and the major diameter as a dashed circle at its mouth |
| Problems are shown in the dialog | Same, in plain words (counterbore narrower than the hole, too deep, a face the hole never reaches...); OK waits; nothing in the Report view |
| OK / Enter, Cancel / Esc, one undo step; Fusion starts the next hole with the last settings | Same |
| Edit: double-click the hole in the timeline | Same; the hole's point is moved in the dialog. Double-clicking its sketch in the browser, or timeline "Edit Profile Sketch", opens the same dialog |

## Thread

| Fusion | SciForge |
|---|---|
| CREATE > Thread; click cylindrical faces (only those light up) | Same; a face selected before the command is taken at once. Several faces of the same size can share one thread |
| A shaft gets an outside thread, a hole an inside one; the size comes from the diameter | Same (a hole's size from its tap drill); the dialog says "Outside thread, d 6 mm, 12 mm long" |
| **Modeled** off: cosmetic thread | The part is unchanged; the thread is recorded (size, class, hand, length) and drawn as a dashed helix on the face |
| **Modeled** on | The real thread: ISO 68-1 basic profile (60 deg) swept along a helix and cut. A shaft wider than the major diameter is turned down to it, a hole narrower than the minor diameter is bored up to it |
| **Full Length**, or Thread Length + Offset | Same; the thread starts at the end of the face nearer to where it was clicked; a blue arrow drags the length |
| Thread Type, Size, Designation, Class, Direction | Same lists as the Hole (ISO metric coarse and fine, UNC / UNF / UNEF) |
| Edit from the timeline, undo, Esc / Cancel | Same |

## Known gaps (never faked)

| Fusion option | Why not yet |
|---|---|
| Hole Tap Type **Taper Tapped** (NPT) | Not offered yet. FreeCAD's Hole has NPT sizes and a taper; the dialog does not use them yet |
| Extents **To** following the target later | The depth is worked out when the dialog applies; if the target face moves in a later edit, open the hole and press OK again. FreeCAD's Hole has no "up to face" depth |
| Clearance hole **fastener type** (socket head, hex...) | Clearance sizes follow the thread size (ISO 273 / ASME B18.2.8), not a fastener catalogue |
| Thread **Class** in modeled geometry | The class is recorded; the modeled thread uses the basic profile (no tolerance offsets) |
| Cosmetic thread texture | Drawn as dashed lines (helix, and a circle at a tapped hole's mouth) |
| A hole on a curved face following the face | The hole keeps its place in the body if the curved face moves later (its sketch cannot be attached to a curved face) |
| Depth to the tip instead of the shoulder | FreeCAD measures to the shoulder; Fusion's default to be confirmed with Luca |

## Tests

- Scenarios (real clicks, keys, drags, menus; any Report-view error fails them):
  `SciForgeTests/gui/scenarios/hole.py` (Single Hole, arrows, types, references, edit,
  Cancel/Esc, undo/redo, timeline Delete), `hole_sketch.py` (From Sketch, flip),
  `hole_tapped.py` (tapped, modeled, clearance fits, ANSI, To a plane), `hole_thread.py`
  (cosmetic / modeled / partial / left-hand thread on a shaft), `hole_thread_inside.py` (hole on
  a curved face, inside thread from a selected hole wall). Volumes hand-derived
  (`gui/hole_steps.py`).
- Golden models `hole_*` and `thread_*` (ops `hole_at`, `hole_points`, `thread` in
  `golden/hole_ops.py`; the same code as the dialogs).
- Unit tests: `SciForgeTests/unit/test_thread_core.py` (sizes, groove, volumes, lengths).
