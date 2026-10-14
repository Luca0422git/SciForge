# Session log: the SURFACE tab (branch `sf/surface`)

To be folded into `MEMORY.md` at the merge (the surface session did not edit it).

### 2026-10-13 / 14: SURFACE tab (outline 7.9, branch `sf/surface`)
- New: `surface_core.py` (the 15 tools as data: titles, icons, step types, CREATE / MODIFY,
  operations, Fusion's starting values; value checks, ranges, ruling direction, cell
  choice, words; pure Python), `surface_geom.py` (the geometry: extrude / revolve / sweep /
  loft of open or closed curves, patch with continuity and a measured tangency, ruled,
  offset, thicken sharp / rounded / symmetric, trim cells, boundary-fill cells, untrim,
  extend, stitch with a working tolerance, unstitch, reverse), `surface.py` (the steps: one
  `PartDesign::FeaturePython` with `SurfaceFeature` per tool, links that survive reopening,
  numbers in properties so formulas work, Trim / Reverse Normal over several bodies as a
  leader + hidden followers, Unstitch pieces as bodies of their own, Stitch and Boundary
  Fill's Remove Tools using bodies up like Combine), `surface_pick.py` (picked shapes drawn
  over the design, clickable cells cast against their triangles), `surface_ui.py` (15
  dialogs on `BodyPanel`, value boxes on every handle, commands, timeline editors, a delete
  watch). 14 new icons (`make_icons.py`). Ribbon SURFACE tab and the SOLID tab's Thicken /
  Boundary Fill wired.
- Surface bodies are PartDesign bodies whose last step is a surface (reasons in
  `parity/surface.md`): the browser shows them with the surface icon (`browser_core` /
  `browser_ui`), `commands.find_body()` never hands a surface body to a solid tool,
  `sketch_ui.create_sketch` keeps a sketch clicked on a surface face in a solid body, and
  the timeline knows the surface steps (`timeline_core` takes `surface_core`'s names).
- Core patch #14 (`BRepOffsetAPI_MakeFillingPyImp.cpp`): `MakeFilling.add(..., 2)` gave
  `GeomAbs_C1` (ignored by OpenCASCADE) instead of G2. Needs the full build; until then
  Patch refuses Curvature with the reason (`surface_geom.g2_available()`).
- Tests (real FreeCAD 1.1.4, real clicks): `surface_extrude` 60, `surface_patch` 70,
  `surface_trim` 59, `surface_stitch` 61, `surface_thicken` 74, `surface_boundary_fill` 58,
  `surface_misc` 70, `surface_reopen` 44 checks, all PASS. Unit: `test_surface_core.py`
  (39). Golden: 8 `surface_*` models (op `sf_surface`, `golden/surface_ops.py`), all PASS.
  Regressions PASS: `ribbon_sweep` (SWEEP_TABS=surface,solid) 156, `timeline_browser` 92,
  `timeline_browser_qa2` 245, `sketch_face` 118, `components_basic` 251, `bodies_qa` 312;
  `--only base`: unit 574 OK, golden 302 pass + the known xfail `plate_hole_grid`.
- Facts learned:
  - `Part.Shape.sewShape(tol)` ignores its tolerance in 1.1.4's Python; `fixTolerance(tol)`
    then `Part.Shell(faces)` sews within it (Stitch).
  - `generalFuse` maps the pieces of each argument only when every face is its own argument
    (a shell or compound argument gives no map): Trim and Boundary Fill pass faces one by one.
  - `Shell.getFreeEdges()` gives the boundary edges and leaves the seams of round faces out
    (a face not in a shell is wrapped in `Part.Shell([face])` first); its edges are copies:
    match them back to the shape's own edges before `isSame`.
  - OpenCASCADE's plate (Patch) cannot meet vertical walls tangent (the G1 error stays at
    90 degrees): measure the reached tangency and refuse.
  - `makeOffsetShape(..., join=0 (arc), fill=True)` fails on open shells ("ThruSections
    failed"): Thicken Rounded is the sharp solid cut down to the faces thickened one by one
    plus round bars along the corners and balls where corners meet.
  - FreeCAD's view callbacks do not always pass the mouse release: pick on the press.
  - A click on a sketch curve lying on a face of another body selects the face, although
    `getObjectInfo` reports the curve: the dialogs look for a shown sketch curve within a few
    pixels of a face click.
  - `PlanePicker` frames the view when the body has no solid; surface dialogs restore the
    camera afterwards.
  - An origin plane belongs to its body (`body_of`): a Trim with the trimmed body's own XY
    plane must not take it as "the tool's own body".
- Open (see the parity doc's gaps): Extrude From Object / All, Revolve To, Sweep rail and
  taper, Loft rails / end conditions, Patch per-edge continuity and Tangency Weight, Extend
  Align Edges, Offset corner type. For the merge: add `Replace Face` / `Split Face`
  (`SciForge_ReplaceFace`, `SciForge_SplitFace`, from the direct-modeling branch) to
  `ribbon_config.SURFACE_MODIFY`.
