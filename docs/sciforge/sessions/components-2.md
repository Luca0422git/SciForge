# Session log: components part 2 (branch `sf/components-2`, 2026-10-14)

Brief: `docs/sciforge/dev/briefs/components-2.md`. Spec with sources and gaps:
`docs/sciforge/parity/components.md` (section "Part 2"), plus rows in `parity/bodies.md`
(Combine New Component, Split Body with several tools, Move Object Components, Set Pivot) and
`parity/patterns.md` (Pattern Type Components).

## What was built

- **Move/Copy of components** (`component_move.py`, `component_move_ui.py`): Move Object
  Bodies / Components in the Move dialog (switching keeps the move type and values; a
  component selected before M opens the components dialog directly). Free Move, Translate,
  Rotate, Point to Point, Point to Position move the component's `App::Part` Placement.
  A canvas click picks the component just below the active one on the way to what was
  clicked. Grounded components and a pattern's copies are refused with the reason. **Capture
  Position** (unticked by default, a guess) records a "Move" step in the timeline
  (`ComponentMove`, edited by double-click; suppress / delete / the marker put the component
  back). Create Copy makes a linked instance and moves that.
- **Set Pivot** (in `move_ui.py`, shared with bodies): a checkable Set Pivot button and its
  own "✓ Done" button; while on, the arrows move only the manipulator, a click snaps it to a
  corner / edge middle / circle centre / face centre, Pivot X / Y / Z can be typed. Nothing
  moves while setting it (`components_core.pivot_shift` adjusts the distances).
- **Copy / Paste / Paste New** (`clipboard_ui.py`, `instances.py`): Ctrl+C / Ctrl+V and the
  browser's right-click Copy / Paste / Paste New. Paste makes a linked instance "Name:2" (the
  original shows "Name:1"); its bodies are `InstanceCopy` copies of the original's bodies, so
  editing the original changes every instance. Paste New makes an independent component
  "Name (1)" with copies of all its features (in the timeline). After a paste the Move dialog
  opens on the pasted component. A pasted body opens Move with Create Copy. In a sketch,
  Ctrl+C / Ctrl+V still copy sketch curves.
- **Combine New Component** (`combine.py`, `combine_ui.py`) and **Split Body with several
  tools** in one step (`split.py`, `split_ui.py`, "2 tools" in the box).
- **Pattern Type Components** for Rectangular, Circular and Pattern on Path
  (`component_pattern.py`, hooks in `pattern.py` / `pattern_ui.py`): one root step; its copies
  are instances placed by the pattern; quantity, distance, angle, suppression, edit from the
  timeline, delete / undo take the copies away. Mirror stays greyed for components.
- **Active Component Visibility** (`component_look.py`): while a component is active,
  everything outside it is drawn see-through (75 %); Preferences > General > Design >
  "Active component visibility" switches it off.
- **The marker and components**: a component step, a captured Move and a pattern of
  components roll back with the marker (`timeline_ops._follow_root_steps`,
  `hide_by_marker`); a component whose step is after the marker is hidden in the window and
  the browser; new root steps made while rolled back go in at the marker
  (`timeline_ops.place_root_step`).
- **New Body command**: not built, Fusion has none (bodies come from features).
- Fixes found on the way: a body copy / split piece / pattern-of-bodies copy of a body inside
  a moved component landed moved twice and FreeCAD warned "Link(s) ... go out of the allowed
  scope" (its first step now sits in the body's container and takes its shape in the body's
  own coordinates: `move.py`, `split.py`, `pattern.py`).

## FreeCAD facts and traps (for the next session)

- A body's BaseFeature that lives outside the body's `App::Part` prints "Link(s) ... go out
  of the allowed scope", and the base shape is taken in the body's local coordinates: put the
  base feature into the same container and convert its shape with `bodies.to_local`.
- Changing an `App::Part`'s Placement touches the part and recomputes everything that
  depends on it (instance copies follow without extra code).
- `doc.copyObject(part, True)` deep-copies a component, but the new part is created after
  its features: the timeline would put the component step after its own features
  (`instances._step_before_its_features` fixes the rank).
- `doc.HasPendingTransaction` does not tell whether a transaction is open; the document
  watch skips its work while `Restoring`, `Transacting` or `Recomputing` and defers to a timer.
- Coin: an `SoMaterial` with only `transparency` set and `setOverride(True)` at index 0 of a
  view provider's RootNode makes the whole object see-through and leaves its colours alone;
  removing the node undoes it. It is no document change (no undo step, nothing saved).
- Editing a feature makes its component active; the timeline then shows only that
  component's steps (scenarios read all titles with `component2_steps`' helpers).
- The Create Sketch origin squares (PlanePicker) are sized from the body's current shape: in
  a split body they can be small, click near the middle.

## Changes in other areas (for the merger)

- `move_ui.py`: Move Object combo (Bodies / Components), Set Pivot / Done and Pivot X/Y/Z,
  `panel_for_selection()`; `MovePanel(doc, feature=None, carry=None, picks=None)`.
- `pattern.py` / `pattern_ui.py`: Pattern Type Components (modify-2 owns Compute options:
  expect a merge in `pattern_ui.py`'s form code).
- `timeline_core.py` (root steps sorted by key, "rolls"), `timeline_ops.py` (marker follows
  root steps, `place_root_step`, suppress / delete hooks), `browser_core.py` /
  `browser_ui.py` (Copy / Paste / Paste New menus, marker-hidden rows, "Name:1" labels,
  instance rename), `components.py` (`editable`, new component at the marker),
  `config.py` (Ctrl+C / Ctrl+V), `prefs_core.py` / `preferences_ui.py` (one new option).
- Golden: `component_ops.py` (new), `builder.py` (roll "before"), `bodies_ops.py`,
  `schema.py`; scenarios `bodies_split.py` (path B) and `bodies_qa.py` (path F, the Split
  Body edit) clear the tool box with its X before picking the new plane, now that the box
  takes several tools (a click on another plane adds it).
- No FreeCAD core files changed.

## Gaps (also in `parity/components.md`, Known gaps)

Nested components flattened in instances; editing goes through the original; deleting the
original freezes its instances; Mirror of components; a pattern's copies cannot be moved on
their own; uncaptured moves cannot be reverted without joints (Fusion's "position pending"
question is not asked); paste across designs; Selection filter Components and Component Drag
(selection / joints-2 work).

## Tests

Scenarios (real clicks): `components2_move` (344 checks), `components2_copy` (277),
`components2_pattern` (278), `components2_bodies` (298), `components2_marker` (208). Golden
models `comp_move_captured_roll`, `comp_move_rotate_pivot`, `comp_paste_instance_follows`,
`comp_paste_new_independent`, `comp_pattern_circular_6`, `comp_pattern_rect_extent`,
`bodies_split_two_planes`, `bodies_combine_new_component`. Unit tests in
`test_components_core.py` (labels, picks, pivot, history) and `test_timeline_core.py`.
