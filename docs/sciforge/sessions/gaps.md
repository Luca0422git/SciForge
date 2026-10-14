# Session log: closing known gaps (branch `sf/gaps`, 2026-10-13 .. 2026-10-14)

To be copied into MEMORY.md by whoever merges (this branch does not edit MEMORY.md).

## What was done (one commit per item or two)

1. **Thin Extrude** and **tapers with every extent** (To Object, Two Sides with a taper per
   side). Scenarios `gaps_thin_extrude`, `gaps_extrude_taper_to`; goldens (see
   `parity/extrude-presspull.md`).
2. **A Join that touches nothing makes a New Body** (Extrude, Revolve, Sweep, Loft, the
   primitives) and **New Component** for Box, Cylinder, Sphere, Torus, Coil and Pipe (a
   component under the active one with the body inside; removed again when the preview
   fails). Hole already refused a hole off the part. Scenario `gaps_join_new_body`; goldens
   `sf_join_away_new_body`, `sf_cylinder_new_component`.
3. **Loft end conditions** (Connected, Direction with takeoff weight and angle, Point
   Tangent; Tangent / Smooth for face profiles) and **Sweep Path + Guide Surface**.
   `loft_ends.py`, `loft_ends_core.py` (unit tested). Scenarios `gaps_loft_ends`,
   `gaps_sweep_guide_surface`; goldens `sf_loft_ends_*`, `sf_sweep_guide_surface`.
4. **Offset Plane Extent To Object** (through a corner / point, following it); every
   construction now finds a lost pick again (`curves.refind` in the hidden frame).
   Scenario `gaps_offset_plane_to`; golden `inspect_offset_plane_to_object`.
5. **The history marker before the first step** (an empty design; Go to beginning and Play
   start there); a step made at the marker goes in at the marker also with no Tip or with
   the marker before a sketch (`timeline_ops.MarkerInserts`, `timeline_core.place_at_marker`).
   **The browser uses the timeline's names** ("Sketch 2", "Plane 1"); Enter without a change
   renames nothing (browser and timeline). Scenario `gaps_timeline_start`; golden
   `tl_roll_to_start`.
6. **A formula of the wrong kind is refused** (a length typed into an angle field, an angle
   into a distance, a length into a count) in every field fed by `preview.FormulaInput`
   (`extrude.check_kind`). Scenario `gaps_formula_units`.
7. **Picked edges / faces / corners kept** when FreeCAD loses their names (`picks.py`,
   memory `SciForgePicks` saved in the file; fixed in the same recompute, before the step
   runs). Goldens `picks_fillet_chamfer_kept_after_reopen`, `picks_shell_kept_on_taper`
   (new golden ops `reopen`, `age`); scenario `gaps_picks_kept`.
8. **Coils and pipes of an older SciForge rebuilt on opening** with a log line
   (`upgrade.py`). Goldens `sf_coil_old_narrow_upgraded`, `sf_pipe_old_upgraded`; scenario
   `gaps_old_coil`.
9. **Parity gaps reviewed**: stale entries removed or corrected (extrude's binder in the
   timeline, used-up bodies in the browser, Pattern on Path's timeline name, Scale's lost
   corner); the rest are listed below with reasons.

## FreeCAD 1.1 findings (worth copying into MEMORY.md)

- `Part.Solid(...)` errors escape every `except` (the script stops): use `Part.makeSolid` /
  `Part.makeShell`, which raise a catchable error.
- OpenCASCADE's volume of B-spline faces is up to about 1 % off (a cylinder lofted between
  spline circles: +0.9 %); polygon profiles are exact.
- A body without a Tip takes a new feature at the end of its Group (after every rolled-back
  step). A Python observer may reorder `Body.Group` inside `slotChangedObject(body, "Group")`:
  FreeCAD takes it as part of the same change and links the feature's base from the new
  order (no second notice, one undo step).
- A taper added to a Pad turns its flat side faces into B-splines and loses the names of its
  edges for the steps after it ("?Edge4", "missing element reference", printed while the Pad
  recomputes); `slotRecomputedObject` of the Pad comes before the later steps run, so they
  can be pointed at the right edge in time. FreeCAD's Draft cannot draft such a B-spline face.
- FreeCAD keeps shapes stored in a file and recomputes nothing on opening: a fix in a
  feature's code only reaches old files when the step is rebuilt (upgrade.py does it for
  coils and pipes).
- Origin squares of Create Sketch are sized from the active body: right after a new body is
  made they can be small; a face under the mouse wins over a square.

## Gaps left, and why

- Loft end conditions with rails, a centerline or on a closed loft (greyed); Tangent Edges
  Merge; OpenCASCADE's ~1 % volume of spline faces (Inspect can be off by that much).
- A Join whose profiles only partly touch keeps the far piece in the body (Fusion guess).
- Offset Plane: Tangent Plane's Reference Plane (Autodesk does not say what it does), Plane /
  Point Along Path take one edge, not a chain.
- The marker standing before a component's step does not hide the component (steps outside
  bodies never roll back); a New Body made while rolled back lands at the end of the
  timeline (its steps are the newest).
- Picks: an edge or face that really moved far (more than a quarter of the part) or changed
  kind is not taken for the old one (the step goes red, like Fusion asks to repair); a
  Draft of a tapered extrude's side face stays red (FreeCAD's Draft refuses B-spline faces).
  FreeCAD's "missing element reference" line still appears in the Report view (printed
  before SciForge can act).
- Formula units: Fillet / Chamfer already refused; fields that take no formulas at all
  (Move, Loft end values, Sweep's distance ratios) still take plain numbers only.
- Combine "New Component", Pattern Type Components: not built (components are new; the
  Combine dialog and the patterns of components belong to their own areas).
- Hole Taper Tapped (NPT), clearance by fastener type, thread class tolerances: not built.

## Small changes in other areas (for the merger)

- `components_core.same_new` (New Body / New Component switch), `pattern.py` (`makeSolid`),
  `curves.py` (`remember` / `refind` take the memory property; matching relative to the
  part's bounding box, a 30 degree turn allowed, nothing farther than a quarter of the part).
- Timeline / browser: `timeline_core`, `timeline_ops`, `timeline_ui`, `browser_core`,
  `browser_ui` (marker at the start, inserts at the marker, shared names, picks paused during
  suppress / delete / move).
- Tests of other areas updated for the new behaviour: `smoke_gui.py` (empty start, "Sketch 1"
  in the browser), `timeline_browser*.py`, `sketch_input.browser_double_click` (finds a row
  by FreeCAD's label too), `revolve_qa.py` P2 and `timeline_browser_qa4.py` P24 (a piece away
  from the part is a New Body), `extrude_presspull_qa7.py` (an extrusion up to a whole body
  joins that body too, as in `gaps_extrude_taper_to` X2), `revolve_qa_more.py` P15/P16 (the
  ring apart from the part is a New Body: every body is counted), `shell_draft_qa_shell.py` P4
  (after a drag too far the last good preview is any wall that fits, not only the thin one),
  `sweep_loft_loft_guides.py` (wait), several op-list checks ("New Component"), golden
  builder (`reopen`, `age`, roll `start`, picks installed) and runner (closes a reopened
  document).

## Tests seen failing that this branch did not cause

- `bodies_combine` fails the same way on the branch's base commit (A: "Body1 is the target":
  the bodies' labels / order since the components merge).
- `sweep_loft_web` sometimes keeps the previous preview after a click (a second curve, Extend
  Curves, Flip) and then fails a run of checks; it passed and failed on the same commits,
  also where the changed code never runs (checked with a log line). Suggested as its own task.

## Final runs (2026-10-14, branch head)

`--only base`: unit 469 OK; golden 314 pass + 1 xfail (`plate_hole_grid`, core patch #4);
smoke 71/71; journey all pass. Scenarios, one at a time: every `extrude*`, `sweep_loft*`,
`fillet*`, `inspect_construct*`, `hole*`, `patterns*`, `shell_draft*`, `revolve*`,
`primitives*`, `timeline*`, `components*`, `bodies*` and `gaps_*` scenario passes, except
`bodies_combine` (fails the same way on the base commit) and `sweep_loft_web` (flaky, see
above; passed twice in a row at the end).
