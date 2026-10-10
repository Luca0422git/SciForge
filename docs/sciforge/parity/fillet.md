# Parity spec: Fillet (F) and Chamfer (outline 7.7)

Source: Fusion's documented behaviour (public help topics on Fillet and Chamfer) and everyday
use. Not yet checked against Luca's own screen captures (outline 2.4). Implemented in
`src/Mod/SciForge/sciforge/fillet_ui.py` (dialogs, commands) and `sciforge/blend.py` (the
geometry rules, no GUI), on top of FreeCAD's `PartDesign::Fillet` / `PartDesign::Chamfer`
with Refine on. Status: **first pass, not yet signed off**.

## What the user does (and what SciForge does)

| Fusion | SciForge |
|---|---|
| MODIFY > Fillet or `F`; with nothing selected the dialog opens and waits | Same. The dialog says "Click edges or faces ..." |
| `F` with edges/faces already selected starts with them | Same (also for Chamfer from the ribbon or the right-click menu). Edges selected on another body make that body active |
| Click edges to add them; no Ctrl needed; click a picked edge again to drop it; clicking empty space does not lose picks | Same (FreeCAD's "greedy" selection style while the dialog is open) |
| Click a face: all its edges are rounded | Same; the face itself is stored, so if an earlier edit adds edges to that face they are rounded too |
| Click a feature (timeline): its edges are rounded | Same: a click on a timeline item adds the sharp edges that step created |
| Tangent Chain (on): tangent edges are picked together and highlighted | Same. Shown as a checked, greyed box: see gaps |
| Only edges that can be rounded light up under the mouse | Same (selection filter: smooth edges, vertices, sketches, other bodies do not highlight) |
| Live preview | The result is shown solid; the part before the fillet is shown see-through around it, with the picks highlighted at their original corner (so they stay clickable) |
| Blue drag arrow on the first picked edge | Same. It lies on the face next to the edge, its tip on the line where the round starts, pointing away from the edge; drag it out to make the round bigger |
| Radius field, units, expressions (`=Parameters.r`) | Same (typed expressions are stored on the feature) |
| Impossible radius: the dialog says so, OK stays disabled | The dialog explains it in plain words and proposes the largest radius that fits; OK waits; the preview keeps the last good result; **nothing** is printed to the Report view |
| OK / Enter finishes, Cancel / Esc cancels, one undo step | Same (Esc also works with the mouse over the 3D view) |
| Ctrl+Z while the dialog is open | Ends the dialog and takes the unfinished fillet away; Ctrl+Y brings it back as a normal step |
| Double-click the fillet in the timeline: edit with the edges shown and editable | Same. The model rolls back to the fillet while editing (later steps hidden) and comes back after OK |
| Starting another command finishes this one | Same (kept if valid, else cancelled) |

Chamfer: the same picking, plus **Chamfer Type** Equal Distance / Two Distances / Distance and
Angle, a **Flip** button (two distances, distance and angle) and one drag arrow per distance,
each lying on the face its distance is measured on (so it is visible which side is which).

Press Pull on a round or bevelled face still edits that fillet's/chamfer's size (it is the same
PartDesign feature), as before.

## Known gaps (shown greyed in the dialog with the reason, never faked)

| Fusion option | Why not yet |
|---|---|
| Tangent Chain off | OpenCASCADE always rounds the whole tangent chain (`BRepFilletAPI_MakeFillet` has no switch). Needs kernel work (outline 9.2) |
| Type: Rule Fillet, Full Round Fillet | Not built yet |
| Radius Type: Chord Length, Variable | `PartDesign::Fillet` has one constant radius. Chord length is convertible for edges between flat faces; variable needs a new feature type |
| Several selection sets with different radii in one fillet | One `PartDesign::Fillet` = one radius. Today: one fillet step per radius |
| Continuity: Curvature (G2), Tangency weight | OpenCASCADE builds circular (G1) rounds only |
| Corner Type: Setback (fillet), Miter / Blend (chamfer) | Not offered by OpenCASCADE's builders |
| A value box floating next to the drag arrow | The value is typed in the dialog |
| Window (drag-box) selection of edges inside the dialog | Not handled specially yet |

## Tests

- Scenarios (real clicks, keys, drags; any Report-view error fails them):
  `SciForgeTests/gui/scenarios/fillet.py`, `fillet_chamfer.py`, `fillet_features.py`,
  `fillet_chain.py`. Volumes are checked with hand-derived formulas (`gui/blend_steps.py`).
- Golden models `blend_*` (ops `blend_fillet`, `blend_chamfer` in the builder; same code as the
  dialogs): face pick, feature pick (inside + outside round), tangent chain on a slot, edit,
  Press Pull on a dialog-made fillet, two distances + flip, distance and angle.
- Unit tests: `SciForgeTests/unit/test_blend_core.py`.

## Lessons for other dialogs

- View-property changes (`Visibility`, `Transparency`, `Selectable`) made while a dialog's undo
  transaction is open are recorded in the undo history: a Ctrl+Z / Ctrl+Y replays them. Use
  PartDesign's `ViewObject.makeTemporaryVisible()` and Coin node fields instead, and put them
  back exactly.
- FreeCAD lets Ctrl+Z run while a task dialog is open; it commits and undoes the dialog's own
  transaction. Watch `slotUndoDocument` / `slotRedoDocument` and end the dialog.
- Esc pressed over the 3D view does not reach a SciForge task dialog (FreeCAD only handles Esc
  when the task panel has the focus): listen for `SoKeyboardEvent` on the view.
- A failing PartDesign recompute prints "Label: reason" to the Report view. Check first with a
  kernel call (`shape.makeFillet`), and mute the console observers around the preview recompute.
- A see-through shape that shares faces with an opaque one flickers (z-fighting): raise the
  opaque view provider's own `SoPolygonOffset` (a node added at the root is overridden).
