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
| **Extents** Distance / To / All | Same. To: click a face or an origin/construction plane (also in the browser); while the To box waits, the dialog says so (no warning) and OK waits for the click. The hole keeps ending on that face when an earlier step moves it (a hidden helper in the body measures the depth on every recompute; golden `hole_to_face_follows`) |
| **Hole Type** Simple / Counterbore / Countersink | Same, with counterbore diameter and depth, countersink diameter and angle |
| **Hole Tap Type** Simple / Clearance / Tapped | Same. Clearance: ISO 273 (Close / Normal / Loose) or ASME B18.2.8 by thread size. Tapped: Thread Type (ISO Metric profile, ANSI Unified Screw Threads), Size, Designation, Class, Direction, **Modeled**, Full Tap Depth / Tap Depth. The size starts from the hole's diameter; the diameter becomes the tap drill or clearance size |
| **Drill Point** Flat / Angle (118 deg) | Same. The depth is measured to the end of the full diameter; the point comes on top |
| Blue arrows: depth, diameter | A blue arrow above the hole sets its depth (drag it down to drill deeper; dragged far up it stops at 0.1 mm), one at the rim the diameter (Simple tap type; pulled in through the centre it stops at its smallest, it does not grow again) |
| Value fields take parameters and formulas | Same in every Hole and Thread value field ("holedepth", "width / 2 + 1"): the hole follows the parameter later; a typo is said in the dialog and Enter / OK wait; a plain number typed over a formula wins at once |
| A hole that does not reach the part | Said in the dialog ("The hole misses the part...") and OK waits, also when the centre dot is dragged off the part |
| A tapped hole that is not modeled shows a thread texture | Drawn as a dashed helix inside the hole and the major diameter as a dashed circle at its mouth |
| Problems are shown in the dialog | Same, in plain words (counterbore narrower than the hole, too deep, a face the hole never reaches...); OK waits; nothing in the Report view |
| OK / Enter, Cancel / Esc, one undo step; Fusion starts the next hole with the last settings | Same; Enter works with the mouse over the 3D view too, and the marking menu offers OK / Cancel. A dialog closed without a change keeps the Redo list |
| Another command while the dialog is open | Its key (E, F, H, Q...) keeps a good hole and starts the command, or drops a hole that cannot be made. Ctrl+Z cancels the hole being made, Ctrl+S / N / O finish it first (a file never holds a half-made hole), Delete deletes nothing |
| Edit: double-click the hole in the timeline | Same; the hole's point is moved in the dialog. Double-clicking its sketch in the browser, or timeline "Edit Profile Sketch", opens the same dialog |

## Thread

| Fusion | SciForge |
|---|---|
| CREATE > Thread; click cylindrical faces (only those light up) | Same; a face selected before the command is taken at once. Several faces of the same size can share one thread |
| A shaft gets an outside thread, a hole an inside one; the size comes from the diameter | Same (a hole's size from its tap drill); the dialog says "Outside thread, d 6 mm, 12 mm long" |
| **Modeled** off: cosmetic thread | The part is unchanged; the thread is recorded (size, class, hand, length) and drawn as a dashed helix on the face |
| **Modeled** on | The real thread: ISO 68-1 basic profile (60 deg) swept along a helix and cut. A shaft wider than the major diameter is turned down to it, a hole narrower than the minor diameter is bored up to it |
| **Full Length**, or Thread Length + Offset | Same; the thread starts at the end of the face nearer to where it was clicked; a blue arrow drags the length (it stops at the face's end and at 0.1 mm). A length longer than the face becomes the face's length. Thread Length / Offset take parameters and formulas |
| Thread Type, Size, Designation, Class, Direction | Same lists as the Hole (ISO metric coarse and fine, UNC / UNF / UNEF) |
| Edit from the timeline, undo, Esc / Cancel | Same; Enter over the 3D view is OK, Ctrl+Z cancels, Ctrl+S finishes first, as for the Hole |
| An earlier step changes the part | The thread stays on its cylinder; when FreeCAD loses the face's name it is found again by where the cylinder is (same axis and radius) |

## Known gaps (never faked)

| Fusion option | Why not yet |
|---|---|
| Hole Tap Type **Taper Tapped** (NPT) | Not offered yet. FreeCAD's Hole has NPT sizes and a taper; the dialog does not use them yet |
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
  a curved face and dragging it along the face, inside thread from a selected hole wall),
  `hole_edges.py` (empty design, Ctrl+Z / Ctrl+Y inside the open dialog, a hole in a second
  body). Volumes hand-derived (`gui/hole_steps.py`).
- QA scenarios (trying to break it the way users do): `hole_qa.py` (paths 1-8: nothing
  picked, values before picks, Esc mid-pick, the Redo list, fast typing, 0 / negative
  values, arrows dragged far and through, the dot dragged off the part, three timeline edits
  with a person's double-click, other commands' keys, Ctrl+S, save / reopen / edit, a
  parameter in Depth), `hole_qa_part.py` (paths 9-15: a part of many steps, Press Pull after,
  an earlier Extrude edited, From Sketch with the sketch picked in the browser, the sketch
  edited, a hole inserted with the marker rolled back, a modeled thread following a taller
  boss), `hole_qa_thread.py` (T1-T7: nothing picked, values first, arrow far / back, timeline
  edits, inside thread on a hole, other keys, a parameter in Thread Length, Ctrl+S and
  reopen), `hole_qa_more.py` (paths 16-21: To following its face also after reopening, From
  Sketch for a beginner, H inside H, OK during a slow recompute, marking menu OK / Cancel,
  Suppress).
- Golden models `hole_*` and `thread_*` (ops `hole_at`, `hole_points`, `thread` in
  `golden/hole_ops.py`; the same code as the dialogs). From the QA: `hole_to_face_follows`
  (To keeps the hole on its face after an edit), `hole_second_survives_first` (deleting the
  first of two holes leaves the second on its face), `thread_second_after_modeled` (a thread
  whose face an earlier thread split keeps working).
- Unit tests: `SciForgeTests/unit/test_thread_core.py` (sizes, groove, volumes, lengths).
