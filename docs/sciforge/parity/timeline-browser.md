# Parity spec: timeline and browser (outline 7.2, 7.3)

Implemented in `src/Mod/SciForge/sciforge/`: `timeline_core.py` (layout logic, unit tested),
`timeline_ops.py` (what the timeline does to the document, also used by the golden-model
builder), `timeline_ui.py`, `browser_core.py`, `browser_ui.py`, `inline_edit.py`.
Tests: `SciForgeTests/unit/test_timeline_core.py`, `test_browser_core.py`, golden models
`tl_*.json`, GUI scenarios `timeline_browser.py` and `timeline_browser_2.py` (real mouse and
keyboard input only). Status: **first full pass, not yet signed off by Luca.**

## Timeline

| Fusion | SciForge | How it maps onto FreeCAD |
|---|---|---|
| One timeline for the whole design | Every body's steps, sketches, construction planes and features outside bodies in one row | Each PartDesign body keeps its own list (`Body.Group`); the lists are merged by creation order (`ID`, or the `SciForgeRank` a cross-body move sets). A body's own order is never changed by the merge. |
| Icon per feature | One icon per kind (Extrude, Revolve, Hole, Fillet, patterns, primitives, construction...) | `timeline_core.KIND_BY_TYPEID` / `KIND_BY_SCIFORGE_TYPE`; unknown SciForge features get a readable name from their `SciForgeType`. |
| History marker, drag to roll back | Drag the marker, playback buttons, Roll History Marker Here, settings > Roll History Marker to End | The marker is each body's `Tip`. A body whose first step is after the marker is empty. |
| Drag a feature to reorder | Drag a step; a red line and a tooltip say why when it cannot go there | Move inside `Body.Group` (`removeObject` + `insertObject` keep the `BaseFeature` chain), then recompute. Refused: a step before something it uses (its sketch, the face it sits on, the features a pattern repeats, parameters); a fillet/chamfer/shell/Press Pull whose edges or faces do not exist on its new base; any move that would break a step that worked. A fillet moved earlier is re-pointed at the same edges on its new base (by geometry). |
| Right-click: Edit Feature, Edit Profile Sketch, Suppress/Unsuppress Features, Roll History Marker Here, Rename, Delete, Find in Browser, Find in Window, Group Features | All of these | |
| Suppress also suppresses what depends on it; Unsuppress brings both back | Same | PartDesign `Suppressed` (FreeCAD 1.1). Sketches and construction planes have none: SciForge hides them and freezes them where they are (`SciForgeSuppressed`). Steps that only fail after the suppress (edges made by the suppressed step) are suppressed too. References FreeCAD marks lost while a step is off (`?Edge2`) are put back on Unsuppress. |
| Delete keeps later features working where possible | Same | The body re-links its history around the gap; a sketch that sat on a deleted face stays where it was (yellow, with the reason); the sketch of a deleted extrude shows again. A step that cannot work any more is red and adds nothing; the steps after it still build on what came before (FreeCAD would keep the old shape and skip them). |
| Errors red, warnings yellow, reason on hover | Same, also in the browser (sketches, planes) | Reasons are rewritten in plain words ("Its profile is gone (deleted?). Edit it and pick a new profile."). While a design has red or suppressed steps, recomputes run with the Report view's error output muted (the timeline shows them instead). |
| Double-click edits | `taskui.edit_object` (each feature's own dialog via `EDITORS`, else FreeCAD's) | |
| Rename | In place (Enter keeps, Esc cancels, F2) | `Label`; a renamed step shows its own name, others "Extrude 2". |
| Groups | Group Features / Expand / Collapse / Rename / Ungroup / Suppress / Delete | `SciForgeGroup` / `SciForgeGroupName` on each member (undo works). Dragging a step out of its group takes it out; dropping it between two grouped steps puts it in. |
| Undo/Redo | Every action is one undo step; after Undo/Redo the design is recomputed so no stale red steps remain | |

## Browser

Order: Document Settings (Units), Named Views, Analysis (once there is one), Origin, Bodies,
Sketches, Construction. Folders appear once they have something in them. Each row: expand
arrow, eye, icon, name. Features are not listed (they are in the timeline).

- Eye: shows/hides; a folder's eye does all of its rows. Origin planes/axes show what is really
  on screen (FreeCAD shows them through their Origin); turning one on alone hides the others.
- Selection both ways: a row click selects the object in the 3D view; selecting it in the 3D
  view or the timeline selects the row; clicking empty space clears it. Hover lights the object
  up in the 3D view. Faces and edges picked in the 3D view do not select a row (as in Fusion).
- Right-click menus per kind (`browser_core.MENUS`): body (Activate Body, Show/Hide, Isolate,
  Find in Window, Find in Timeline, Rename, Delete), sketch (Edit Sketch, Show/Hide, Look At,
  Find in Window, Find in Timeline, Rename, Delete), construction (Edit Feature, ...), origin
  (Show/Hide, Create Sketch), Named Views (New Named View), saved view (Go to View, Rename,
  Delete), document (Show All Bodies, Show All Sketches, Hide All Sketches, Rename).
- Double-click a body: activate it (bold, with a dot). Double-click a sketch/plane: edit it.
- Units: click "Units: mm" for Change Active Units (Millimeter, Centimeter, Meter, Inch, Foot,
  Set as Default) in the task panel. FreeCAD keeps units per document (`Document.UnitSystem`).
- Named Views: TOP, FRONT, RIGHT, HOME, plus saved views (stored in the document's `Meta`).
- F2 renames, Delete deletes (one undo step, same rules as the timeline).

## Known gaps

- The marker cannot go before the first solid step (FreeCAD needs a Tip to show a body; the
  shared smoke test also expects the snap). Fusion lets you roll to an empty design.
- Steps outside any body (plain Part features) are shown in the timeline but never rolled back.
- No hover highlight of a step's faces from the timeline yet (Fusion highlights them).
- Saved named views are stored in the document's `Meta`, which Undo does not cover.
- Errors from a recompute run while the design already has red or suppressed steps are not
  printed in the Report view (by design); they are on the timeline. The first failure of a
  healthy design still prints, so the test harness still catches new bugs.
- Bodies have no "New Body" command of their own yet; Extrude > New Body (extrude branch) and
  FreeCAD's PartDesign Body command (command search) create them.

## FreeCAD 1.1 findings (worth copying into MEMORY.md)

- A PartDesign feature that fails keeps its last good shape, and FreeCAD skips every step after
  it, so the 3D view keeps showing geometry that no longer exists. `timeline_ops.recompute()`
  passes the step's base shape through and rebuilds the steps after it.
- A body whose Tip has no shape (everything suppressed) fails with "Tip shape is empty" and keeps
  its old shape; SciForge empties it.
- `Suppressed` features are still computed; if they fail FreeCAD prints "Failed to recompute
  suppressed feature" every time. References to edges/faces that vanish while a step is off
  are rewritten to `?Edge2` and never come back on their own: SciForge stores them before
  suppressing and puts them back on Unsuppress.
- After a reorder, a fillet keeps its old edge *names*, which can mean other edges (or none) on
  the new base: re-point it by geometry.
- Undo/Redo restore shapes but not the error state of steps; recompute afterwards.
- Origin planes/axes are drawn through their `App::Origin`: a plane's own `Visibility` is usually
  True while nothing shows.
- `Gui.Selection.removePreselection()` does not exist in 1.1; it is `clearPreselection()`.
- Qt test input: a `QMenu` ignores a click that comes without mouse movement since it opened;
  `QTest.mouseDClick` sends only the double-click event (send press/release first); widgets
  added to a visible layout are hidden until the event loop runs. `widget_input.py` handles
  all three.
