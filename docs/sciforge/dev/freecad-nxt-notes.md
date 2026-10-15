# FreeCAD-Nxt: what SciForge can learn from it (research, 2026-10-15)

FreeCAD-Nxt (github.com/obelisk79/FreeCAD-Nxt, by obelisk79, LGPL-2.1-or-later like
SciForge) is an add-on, not a fork: a QtQuick/QML model panel and property inspector plus a
set of 3D editing aids for stock FreeCAD. Version 0.4.0 (2026-10-14), about 31,000 lines of
Python and QML, tested mainly with PartDesign. Announced on r/FreeCAD as "open for testing".
Its license allows reusing code with attribution (keep the LGPL header and credit the author).

## Ideas worth taking (SciForge does not have them yet)

1. **"Wire is not closed" repair** (`tools/sketch_closure.py`, pure Python, and
   `tools/sketch_repair.py`). Before a feature fails, it looks at the sketch's edges and finds
   gaps (ends closer than 1 % of the sketch diagonal), duplicate and zero-length edges, loose
   ends, forks and overlapping edges. Near-miss ends get a coincident constraint; stray edges
   are bypassed by pointing the feature at the sketch's closed regions. Inside a dialog the
   repair joins that dialog's undo step, and a toast offers one-click Undo. SciForge's region
   picking only sees closed loops, so a sketch with a tiny gap shows no profile at all.
2. **Sketch health from the solver** (`tree/health.py`). Redundant constraints leave a
   sketch's `State` clean, so it reads `ConflictingConstraints`, `MalformedConstraints`,
   `RedundantConstraints`, `PartiallyRedundantConstraints`, `DoF` and `FullyConstrained`
   (probing each accessor, never calling `solve()`). Useful for warning marks on sketches in
   the browser and the timeline.
3. **Formula help in value boxes** (`tools/expressions.py`). As you type, it suggests
   parameter and object names, properties, functions (sin, sqrt, ...) and constants, and shows
   the live result. Fusion offers parameter names while typing in a field; SciForge accepts
   formulas but suggests nothing.
4. **Broken-reference marks** (`tree/DESIGN.md`, rule 4). A row gets a mark only when
   something it reads is broken, and the mark names the culprit, such as "Pad:Face3", rather
   than the row that failed. Their lesson: a mark on every row is a mark nobody reads.
5. **Rollback bar feel** (`tree/rollback.py`, DESIGN rule 10). While held, the bar follows the
   pointer smoothly; the expensive preview runs once per row crossed; released, it animates
   onto the boundary. Where the bar rests is stored apart from which step it sets, so dropping
   it between two sketches does not make it jump. Compare with SciForge's timeline marker
   (`timeline_ui.py`, the marker note in `timeline_ops`).
6. **Snap a dragged extrude length to a parallel face** (`tools/face_snap.py`). Check what
   Fusion does before copying it.

## FreeCAD facts they recorded

- FreeCAD 1.1 has its own 3D drag handles ("gizmos") on PartDesign dialogs, set by hidden
  preferences in `Gui/Gizmos` and `History/Dragger` (`tools/gizmos.py`). SciForge draws its
  own handles; keep FreeCAD's out of the way.
- FreeCAD signals neither the start of an edit nor a gizmo appearing, so Nxt polls (4 Hz idle,
  30 Hz while active) (`tools/float_input.py`).
- An open FreeCAD task panel owns its feature: OK writes the panel's fields back over any
  property set directly meanwhile (`tools/task_sync.py`).
- `LinkList` and `LinkSub` values both arrive as two-item sequences: check the shape, not the
  length (DESIGN rule 4).
- Converting an icon to `Format_Grayscale8` loses transparency (filled black); go through ARGB.

## Already in SciForge (no action)

Isolate, a history-ordered browser and timeline, value boxes beside drag handles, editing a
feature from the timeline, and showing sketches at the point in history where they were made.
