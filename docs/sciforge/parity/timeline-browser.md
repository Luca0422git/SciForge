# Parity spec: timeline and browser (outline 7.2, 7.3)

Implemented in `src/Mod/SciForge/sciforge/`: `timeline_core.py` (layout logic, unit tested),
`timeline_ops.py` (what the timeline does to the document, also used by the golden-model
builder), `timeline_ui.py`, `browser_core.py`, `browser_ui.py`, `inline_edit.py`.
Tests: `SciForgeTests/unit/test_timeline_core.py`, `test_browser_core.py`, golden models
`tl_*.json`, GUI scenarios `timeline_browser.py`, `timeline_browser_2.py`, `timeline_roll_view.py`
and the QA scenarios `timeline_browser_qa.py` .. `timeline_browser_qa4.py` (24 paths a Fusion
user takes, real mouse and keyboard input only, real-input helpers in
`SciForgeTests/gui/timeline_input.py`). Status: **first full pass + QA pass, not yet signed off
by Luca.**

## Timeline

| Fusion | SciForge | How it maps onto FreeCAD |
|---|---|---|
| One timeline for the whole design | Every body's steps, sketches, construction planes and features outside bodies in one row | Each PartDesign body keeps its own list (`Body.Group`); the lists are merged by creation order (`ID`, or the `SciForgeRank` a cross-body move sets). A body's own order is never changed by the merge. |
| Icon per feature | One icon per kind (Extrude, Revolve, Hole, Fillet, patterns, primitives, construction...) | `timeline_core.KIND_BY_TYPEID` / `KIND_BY_SCIFORGE_TYPE`; unknown SciForge features get a readable name from their `SciForgeType`. |
| History marker, drag to roll back | Drag the marker, playback buttons, Roll History Marker Here, settings > Roll History Marker to End | The marker is each body's `Tip`. A body whose first step is after the marker is empty (`Tip` None). |
| Drag a feature to reorder | Drag a step; a red line and a tooltip say why when it cannot go there | Move inside `Body.Group` (`removeObject` + `insertObject` keep the `BaseFeature` chain), then recompute. Refused: a step before something it uses (its sketch, the face it sits on, the features a pattern repeats, parameters); a fillet/chamfer/shell/Press Pull whose edges or faces do not exist on its new base; any move that would break a step that worked. A fillet moved earlier is re-pointed at the same edges on its new base (by geometry). |
| Right-click: Edit Feature, Edit Profile Sketch, Suppress/Unsuppress Features, Roll History Marker Here, Rename, Delete, Find in Browser, Find in Window, Group Features | All of these | |
| Suppress also suppresses what depends on it; Unsuppress brings both back | Same | PartDesign `Suppressed` (FreeCAD 1.1). Sketches and construction planes have none: SciForge hides them and freezes them where they are (`SciForgeSuppressed`). Steps that only fail after the suppress (edges made by the suppressed step) are suppressed too. References FreeCAD marks lost while a step is off (`?Edge2`) are put back on Unsuppress. |
| Delete keeps later features working where possible | Same | The body re-links its history around the gap; a sketch that sat on a deleted face stays where it was (yellow, with the reason); the sketch of a deleted extrude shows again. A step that cannot work any more is red and adds nothing; the steps after it still build on what came before (FreeCAD would keep the old shape and skip them). |
| Errors red, warnings yellow, reason on hover | Same, also in the browser (sketches, planes) | Reasons are rewritten in plain words ("Its profile is gone (deleted?). Edit it and pick a new profile."). While a design has red or suppressed steps, recomputes run with the Report view's error output muted (the timeline shows them instead). |
| Double-click edits | `taskui.edit_object` (each feature's own dialog via `EDITORS`, else FreeCAD's) | |
| Rename | In place (Enter keeps, Esc cancels, F2) | `Label`; a renamed step shows its own name, others "Extrude 2". |
| Groups | Group Features / Expand / Collapse / Rename / Ungroup / Suppress / Delete | `SciForgeGroup` / `SciForgeGroupName` on each member (undo works). Dragging a step out of its group takes it out; dropping it between two grouped steps puts it in. |
| Undo/Redo | Every action is one undo step; after Undo/Redo the design is recomputed so no stale red steps remain | |
| Step names never change ("Extrude 3" stays Extrude 3 when moved or when a step is added before it) | Same, but deleting an earlier step renumbers the later ones of that kind | Steps of a kind are numbered in the order they were made (FreeCAD's object `ID`; FreeCAD's label numbers also count cancelled previews). A step SciForge rebuilds as another kind (extrude -> cut) is a new object: among default labels of one kind the label order decides, and the label is kept. |
| The marker can stand anywhere, also just before a sketch (that sketch is then not drawn), and at the very beginning (Move to Beginning: an empty design) | Same (2026-10-14: also before the first step; Go to beginning and Play start from the empty design) | The Tips say which solids are active; `Document.Meta["SciForge.MarkerBefore"]` names the sketch/plane right after the marker (ignored when it no longer fits the Tips, e.g. after an undo). Sketches/planes after the marker are hidden and shown again when it passes them (`SciForgeRolledHidden`). |
| Edit a step after the marker (double-click, Edit Profile Sketch) | The design rolls to the step while its dialog/sketch is open, then the marker goes back | Not an undo step (the edit is). |
| A step added while rolled back goes in at the marker; the steps after it keep working | Same (2026-10-14: also with the marker before the first step or right before a sketch) | A fillet/chamfer/shell/draft/Press Pull whose base step changes (a step added before it, the step before it deleted, suppressed) gets FreeCAD's old edge names on a new shape ("Invalid edge link", or silently other edges): SciForge remembers the edges/faces each step was computed on and finds them again by place and size (`timeline_ops.repair_references`). FreeCAD's `Body.addObject` puts a new step before the next solid step after the Tip, or at the end of a body with no Tip (after every rolled-back step, built on all of them) and after a sketch the marker stands before: `timeline_ops.MarkerInserts` moves it to the marker (`timeline_core.place_at_marker`) inside FreeCAD's Group-change notice, before PartDesign links its base. |
| An edit that breaks a later step (box made lower than a fillet's radius) | The later step goes red, adds nothing, the steps after it still build; nothing in the Report view | `timeline_ops.settle()` runs after every recompute (feature dialogs, undo...), deferred by the timeline's document observer. |
| Play | Animates the history; starting a command stops it | Rolling the design under an open dialog committed the dialog's preview (FreeCAD commits the open undo step when another one opens). |
| Esc while dragging a step or the marker | Drops the drag | |
| Long designs | The timeline keeps the marker in view; mouse wheel and a thin bar scroll it | |
| Right-click while a command waits for picks | Not a pick; the menu entry ends the command first | A right-click selected the step and Fillet took it as "all edges of this feature". |
| Hover a step | Lights up what it made in the 3D view (the faces of an extrude/hole/fillet, a sketch's curves, a plane); nothing for steps after the marker or suppressed | `timeline_hover.py`: a face of the step's result is its own when no face of its base lies on the same surface; drawn in SciForge's own Coin nodes. |

## Browser

Order: Document Settings (Units), Named Views, Analysis (once there is one), Origin, Bodies,
Sketches, Construction, then the components (each with its own Origin, Bodies, Sketches,
Construction and nested components; the activate ring at the end of a component row and of
the design's row: `parity/components.md`). Folders appear once they have something in them.
Each row: expand arrow, eye, icon, name. Features are not listed (they are in the timeline).
Sketches and construction are called what the timeline calls them ("Sketch 2", "Plane 1", or
the name the user gave them), like Fusion, where both show one name; FreeCAD's label
("Sketch001") still finds the row (`BrowserWidget.row`). Enter in the name field without a
change renames nothing (also in the timeline: "Extrude 1" stays a number, not a fixed name).
One origin (the active body's, else the first body's; FreeCAD gives every body its own).
Suppressed sketches and planes are greyed and struck through, not shown as warnings.

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

- Extrude while rolled back before a fillet/chamfer: the Extrude dialog cannot switch to Cut
  ("... is used by Fillet"), because `extrude.dependents()` counts the fillet's `Base`, which
  only follows the history chain (owner: extrude; fix: skip `Base` when it is the step's
  `BaseFeature`, as `timeline_ops.uses()` does). A Join works.
- Groups cannot be dragged as a whole yet (their steps can).
- Steps outside any body (plain Part features) are shown in the timeline but never rolled back.
- Saved named views are stored in the document's `Meta`, which Undo does not cover.
- Errors from a recompute run while the design already has red or suppressed steps are not
  printed in the Report view (by design); they are on the timeline. The first failure of a
  healthy design still prints, so the test harness still catches new bugs.
- Bodies have no "New Body" command of their own yet; Extrude > New Body (extrude branch) and
  FreeCAD's PartDesign Body command (command search) create them.

## Marker at the beginning, one name (2026-10-14, gaps work)

Sources: **Autodesk** help "Parametric Timeline and Features" (ASM-TIMELINE, search excerpt):
the buttons left of the timeline move the marker to the beginning or the end, play, or step
one feature; the marker can be dragged to any point. **Forum** (Autodesk's community manager,
"Are revisions to Timeline inserted or appended?"): with the marker rolled back, new features
are created at the marker, not at the end. **Autodesk** API `TimelineObject.rollTo` (before or
after an object). **Guess** (from use): the browser and the timeline show one name for a sketch
or a construction plane; renaming it in one renames it in the other (SciForge did that already,
only the default names differed).

Before the first step every body has no `Tip` (an empty design; `timeline_core` counts 0
active solid steps). Golden `tl_roll_to_start` (a plate added at the start comes first: the
volume checked right after it is the plate alone), scenario `gaps_timeline_start.py` (drag the
marker before Sketch 1, a post made there goes in first, Go to end builds the box on it,
Ctrl+Z / Ctrl+Y, the browser's "Sketch 1" / "Sketch 2", Enter renames nothing, playback).

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
  all three. A drag's release must go through `QTest.mouseRelease` (the window): released with
  `sendEvent`, Qt kept the button "down" and the next click anywhere went to the dragged widget.
  Qt 6 does not pass a synthetic wheel event on to the parent: send it to the scroll viewport.
- Inserting a step before a dress-up (rolled-back marker) or deleting the step before it
  re-links the dress-up's `Base` to the new base with the old element names: "Invalid edge
  link" (or other edges). `Document.openTransaction` commits the transaction that is open (in
  every document): a timeline/browser action that opens an undo step while a command dialog
  is open must end that command first. Setting `MapMode` attaches at once and prints
  "PositionBySupport: subshape not found" (Report view and a pop-up balloon) if the face is not
  back yet: unsuppress solids, recompute, then sketches.
- A body without a Tip takes a new feature at the end of its Group (`getNextSolidFeature()`
  is null), whatever the rolled-back features are. A Python document observer may reorder the
  Group inside its `slotChangedObject(body, "Group")`: FreeCAD takes the new order as part of
  the same change (no second notice, one undo step) and `setBaseProperty` then links the
  feature's base from the new order.
- A taper added to a Pad turns its side faces into B-splines (flat, but not `GeomPlane`) and
  FreeCAD loses the names of its edges for the steps after it ("?Edge4", "missing element
  reference", printed while the Pad recomputes): `sciforge/picks.py` finds them again in the
  same recompute (`slotRecomputedObject` of the Pad comes before the later steps run).
