# SURFACE tab: SciForge vs Fusion gap audit (2026-10-23)

This audit compares the Fusion spec in `research/surface.md` with SciForge's code on `develop` at
a00bd39. It is based on the code, not the docs. All paths are under `src/Mod/SciForge/sciforge/`
unless stated otherwise.

**Probes**: real FreeCAD 1.1.4 ran headless (`.sciforge-cache/freecad/squashfs-root/AppRun freecadcmd`).
The scripts are in `scratchpad/probe/p1..p4.py` and their results in `p*.out`. Each probe result
quoted below was measured.

- Shell fillet: `makeFillet(2, edges)` on an open box shell (5 faces) returned a valid 6-face
  compound. Filleting the 4 bottom edges gave 9 faces, all valid. `makeChamfer` gave 7 faces,
  valid. Filleting the shared edge of a B-spline loft face and a plane gave a valid result.
  Filleting a free edge raised "no suitable edges" (expected).
- Offset of the open box shell: `makeOffsetShape(2, 1e-6, False, False, 0, join, False)` with
  join=0 (arcs, what SciForge uses) gives 17 faces (cylinders and spheres at the corners). With
  join=2 (intersection) it gives 5 planes, valid. That is Fusion's **Sharp** offset.
- Split: `BOPTools.SplitAPI.slice(solid box, [2-face L shell])` gives 2 solids (6000 + 2000).
  Slicing with a B-spline loft surface gives 2 solids. Slicing a shell with a plane gives
  2 shells. A face too small to cross the solid gives 1 solid, so Extend is needed.
- Shells also work with `transformGeometry` (non-uniform scale), `mirror` and sewing a subset of
  faces (delete without healing).
- `MakePipeShell` has `setSpineSupport` and `setAuxiliarySpine`. `MakeFilling.add(edge, face,
  order, bound)` takes a continuity per edge. `GeomPlate.BuildPlateSurface` and
  `CurveConstraint` are exposed. `BSplineSurface.value(u, v)` outside the bounds extrapolates,
  but `toShape(u outside bounds)` gives an invalid face. pivy has `SoTextureCoordinateEnvironment`
  and `SoTextureCubeMap`. `uIso` and `vIso` exist. No GeomLib `ExtendSurfByLength` and no per-face
  offset (`BRepOffset_MakeOffset::SetOffsetOnFace`) are bound to Python.
- On a real surface body made by `surface.build("extrude", ...)`:
  - `move.build`: `MoveError "Body2 has no solid to move."`
  - `split.check`: `SplitError "Body2 has no solid to split."`
  - `delete.heal(face of the surface)`: `DeleteError "This face cannot be deleted: the faces
    around it cannot be extended to close the gap..."` (wrong and misleading for a surface).

**Effort**: S = under 1 h; M = 1 to 3 h; L = more than 3 h, or the kernel is the limit.

**Ownership warning (wave 6)**: the surface-3 builder owns only the `surface*` files
(`dev/briefs/wave6-common.md`). Rows 1, 2, 4, 5, 6, 10 and 16 touch solid-tool files that no
builder owns (`split.py`, `delete*.py`, `fillet*.py`, `move.py`, `align.py`, `pattern*.py`,
`scale.py`, `presspull*.py`). There are two ways to handle them:

- (a) The orchestrator allows small "accept a shell" edits there.
- (b) surface-3 builds surface-only kinds in `surface_core.py`, `surface_geom.py`, `surface.py`
  and `surface_ui.py`, such as `surface_fillet`, `surface_chamfer`, `surface_delete` and
  `surface_split`, and points the SURFACE ribbon entries at them.

The table below names the file for each fix and says which route fits.

## Ranked gaps (value to someone making product shapes)

| # | Fusion command/option | SciForge today (file:line evidence) | Gap | Effort | Suggested implementation |
|---|---|---|---|---|---|
| 1 | **Split Body with a surface body as the Splitting Tool**, and Split Body of open bodies (Fusion: tool = "body (solid or open)"; Body to Split = "solid or open bodies"). This is the classic hybrid workflow: cut a solid with a sculpted surface | `split.py:93-95` refuses a body tool that has no solid ("%s has no solid to split with"). `split.py:377-378` refuses a surface body to split. `split.py:220` keeps only `result.Solids`. A single face of a surface is taken (`split.py:96-110`), but only planes and cylinders are extended. Split Body is not in `SURFACE_MODIFY` (`ribbon_config.py:525-542`) | Tool: refused. Splitting an open body: refused. The menu entry is missing | S (tool) + M (open bodies, extend free-form tool) | In `split.tool_shape`, return the shell (`shape.Shells` or `Faces`) when the body has no solid. Probe: `slice(box, [shell])` gives 2 solids. Extend Splitting Tool for a surface tool: grow its free edges with `surface_geom.extend(..., "natural")`, or fall back to tangent bands, so it crosses `around`. Open bodies: in `split_shape`, keep `result.Shells` or `Faces` when the input has no solid. Each piece becomes a surface body through `surface_result`. Add `item("Split Body", "SciForge_SplitBody", "split_body")` after Split Face in `SURFACE_MODIFY`. Route (a), or route (b) as `surface_split` |
| 2 | **Delete on the SURFACE tab: faces removed without healing** (SurfaceDeleteFaceFeature; a solid becomes a surface body at the first deleted face) | `delete.py:556-557` needs `base.Shape.Solids`. `delete.py:586-598` `heal()` defeatures and refuses when no solid remains. The probe deleting a face of a surface body gets a misleading "cannot be extended to close the gap" refusal. `delete_ui.py` has no surface case. The ribbon reuses SOLID's Delete (`ribbon_config.py:541`) | Deleting a face of any surface body fails. Deleting a solid's face from the SURFACE tab heals instead of opening the body | S/M | New kind `surface_delete` (`SciForgeType "SurfaceDeleteFace"`), MODIFY. Geometry = `surface_geom.unstitch(target, faces)[0]`: the rest sewn, the taken faces dropped; `Part.Solid` is not rebuilt. Route a face click into it when the face's body `is_surface_body`, or when the SURFACE tab is active (`ribbon_ui` knows the tab). SOLID keeps healing. Add a `SURFACE_MODIFY` "Delete" entry pointing at a surface-aware command |
| 3 | **Offset: Offset Type Sharp / Rounded, default Sharp** (Fusion May 2025, A) | `surface_geom.py:1582` always calls `makeOffsetShape(d, 1e-6, False, False, 0, 0, False)`, so join=0 (arcs). The defaults have no offset type (`surface_core.py:184`). `OffsetPanel` has no widget (`surface_ui.py:1900-1911`). The parity doc's Known gaps calls it "unconfirmed", but it is now confirmed | SciForge's default result **differs from Fusion's**: rounded corners instead of sharp. Fusion's option is missing | S | `surface_core`: `OFFSET_TYPES = ("sharp","rounded")`, default `"sharp"`, added to `check_values`. `surface_geom.offset_faces(faces, d, offset_type)`: join=2 for sharp, 0 for rounded (probe: open box, join=2 gives 5 valid planes). If join=2 throws, refuse with the reason ("try Rounded"). `OffsetPanel.add_combo("offset_type", "Offset Type", ...)`. Store it in the step's JSON, with old files defaulting to rounded so saved designs keep their shape |
| 4 | **Fillet / Chamfer on edges of surface bodies** (Surface > Modify > Fillet / Chamfer, A: H-FILCH) | `fillet_ui.py:103-110` `solid_base` returns None without `Solids`. `fillet_ui.py:2271-2275` refuses "needs a solid to round". `commands.find_body()` skips surface bodies (`commands.py:29,56`). `fillet_sets.py:170,446,810,857,1085` check `.Solids`. Fillet and Chamfer are not in `SURFACE_MODIFY` | Refused, and missing from the menu | M | Probe: `shell.makeFillet` and `makeChamfer` work on open shells, B-spline faces included. Route (b): kinds `surface_fillet` (Radius, Tangent Chain; Constant only, with Chord Length / Variable / G2 greyed with the reason) and `surface_chamfer` (Equal Distance / Two Distance / Distance and Angle via `makeChamfer(d1, d2, edges)`). Edges must have 2 faces in the same body (`faces_of_edge`). A free edge or an edge between bodies is refused: "Stitch them first" (Fusion's rule, F-FIL2). Add both entries to the head of `SURFACE_MODIFY` |
| 5 | **Move/Copy (M) and Align on surface bodies** | `move.py:293-294` `check()` refuses "has no solid to move". `move.py:191,224` MoveFeature / CopyFeature need `.Solids`. `align.py:260,401-402` does the same. The `surface.py:10` docstring claims Move/Copy works for surface bodies; the probe shows it does not. Neither is in `SURFACE_MODIFY` | Refused, the docstring is wrong, and both menu entries are missing | S | Replace `has_solid` and `.Solids` with "has faces" (`not Shape.isNull() and Shape.Faces`) in `move.py` and `align.py`. The geometry is a plain transform, which works on shells. Route (a) only: no surface-only variant makes sense. Add Move/Copy (M) and Align to `SURFACE_MODIFY` |
| 6 | **Pattern ▸ (Rectangular / Circular / on Path) and Mirror of surface bodies**. Mirror Operation Join stitches the copies with a Stitch Tolerance (A: H-MIRROR, API stitchTolerance) | `pattern_ui.py:2282-2286` refuses unless the (non-surface) `find_body()` tip has a solid ("needs a solid to repeat"). `pattern.py:2399-2402` BodyPatternFeature refuses "no solid before this step to copy". `pattern.is_solid_feature` excludes surface steps from Features patterns. Neither is in `SURFACE_CREATE` (`ribbon_config.py:504-523`) | Refused, and missing from the menu | M | Bodies type: accept a surface body; copies are shells in new surface bodies, through the same `BodyPatternFeature`, relaxing `.Solids`. Mirror Join on a surface: `surface_geom.stitch([orig, mirrored], tol)` instead of a fuse, plus a Stitch Tolerance row (default 1 mm, G). Add `sub("Pattern", ...)` and Mirror between Offset and Thicken in `SURFACE_CREATE` (Fusion order) |
| 7 | **Sweep: Type Path + Guide Surface** (A: H-SWP, API guideSurfaces Jan 2024) | `surface_core.py:53` `SWEEP_TYPES = ("single","rail")`. `surface_ui.py:1473` combo has 2 types. The SOLID sweep already does it: `sweep.py:610-650` `guide_faces()` and `_surface_aux()`, an auxiliary spine offset along the face normal | Missing on the surface Sweep | S/M | Add `"surface"` to `SWEEP_TYPES`, a "Guide Surface" face box on `refs3` (Chain Selection adds tangent faces), and in `surface_geom.sweep_curves` reuse `sweep._surface_aux(spine, sweep.guide_faces(refs), size)` with `MakePipeShell.setAuxiliarySpine` (as `_pipe(..., aux)` already does for twist). Distance only, as Fusion does. `MakePipeShell.setSpineSupport` (Darboux) is an alternative |
| 8 | **Patch: Reverse Normal + Flip** (Jan 2026), **Group Edges off** (per-edge Continuity + Weight rows), **Tangency Weight** (default 0.5) | `surface_ui.py:1786` Group Edges greyed. `surface_ui.py:1796` Tangency Weight greyed. `surface_core.py:156` weight default 1.0, range 0.1-2.0 (`:70`), while Fusion's default is 0.5 (A). No reverse option. `surface_geom.py:1383` already passes an order per edge | Reverse: missing. Per-edge continuity: greyed though OCC supports it. Weight: not possible as asked | S (reverse) / M (per-edge) / L (weight) | Reverse: a check box plus `face.reverse()` after `_fill`, or `surface_result(...).reversed()`. Per-edge: store `edge_continuity: [..]` aligned with `refs`. The panel gets a list widget of the boundary edges, each with a combo. `_fill` then uses each edge's own order (already one `mk.add` per edge). Weight: keep greyed, but show 0.5 as Fusion does. A possible later route: `GeomPlate.CurveConstraint` with G1 criterion scaling. Low payoff |
| 9 | **Extend Natural on free-form, sphere, torus, revolved and extruded faces**; **Edge Alignment Align Edges** | `surface_geom.py:2006` `_grow_rectangle` handles only cylinders and cones. Every other non-planar face falls back to tangent bands (`surface_geom.py:1961-1979`). Align Edges greyed (`surface_ui.py:2058-2071`, `surface_core.py:43`) | Natural is wrong (tangent) on most product surfaces. Align: missing | M (natural) / L (align) | Natural: for analytic surfaces with an open parameter range (`SurfaceOfExtrusion`, `SurfaceOfRevolution`, Sphere, Toroid in their periodic limits), use `surface.toShape(u0-du, ...)` as `_grow_rectangle` does. For B-splines, the probe shows `value()` extrapolates past the bounds, but `toShape` past them gives an invalid face. Instead, sample a band `value(u,v)` from the edge to `d` beyond, then `BSplineSurface.approximate` it into a band face sewn to the original (G1 at the seam), and keep the original face untouched. Align Edges: L. It needs neighbouring bands to share their side curves (build each band from a common corner curve). Keep it greyed unless there is time |
| 10 | **Scale on surface bodies** (H-MOD lists Scale) | `scale.py:105-106` `scaled()` refuses "Make a solid first". `scale.py:237,323` need `.Solids`. Scale is not in `SURFACE_MODIFY` | Refused, and missing from the menu | S | Accept shells in `scaled()` and `ScaleFeature.execute`. The probe shows non-uniform `transformGeometry` on a shell is valid. Route (a). Add a Scale entry |
| 11 | **Untrim: Type Manual** (pick loops / edges) and **Keep Copy** | `surface_core.py:45` `LOOP_TYPES` has 3 types. `surface_core.py:222` defaults have no keep_copy. `UntrimPanel` (`surface_ui.py:2020-2040`) | Missing | S (Keep Copy) / M (Manual) | Keep Copy: in `_c_untrim`, also emit a new surface body holding the original faces, as Unstitch pieces do (`_sync_pieces`). Manual: add a "loops" box that takes free edges and expands each to its wire; `untrim()` drops only the wires containing a picked edge. Same rule as today: only wires whose edges have one face |
| 12 | **Revolve: Project Axis** check box; extent label **Partial** (not "Angle"); **To Object with Two Sides** | `surface_ui.py:1355` labels the types "Angle / To / Full". `surface_ui.py:1366` hides Direction unless Angle. `surface_geom.py:880-901` `_check_axis` uses the axis as it is, with no projection | Missing option, wrong wording, missing direction | S | Project Axis (default on, G): project the axis line onto the profile's plane (`plane_of(wires)`) before `revolve_curves`. Rename the label to "Partial" and keep the key `"angle"` for old files. To with Two Sides: two objects (refs3 plus a new refs slot), two stop angles, revolve from −a2 to a1 |
| 13 | **Extrude: To Object Match Shape; Chain Faces / Extend Faces choice; planar faces as Profiles** | `surface_ui.py:1173-1175` has only a Chain Faces check box. `ExtrudePanel.boxes` profile accepts `("curve","sketch")` (`surface_ui.py:1138`), so a planar face click is refused | Partial | S (faces as profiles) / M (Match Shape) | Profiles: in `interpret`, a planar face on the profile box expands to its outer and inner wires' edges. Extend Faces is SciForge's current curved-face behaviour (the parity doc says lines "carried on past the face's edges"). Expose it as a combo "Chain Faces / Extend Faces" mapping onto `chain_faces`. Match Shape: end the extrusion on the faces adjacent to the picked face (`_extrude_to_shape` with the neighbour faces as the target). M, low priority |
| 14 | **Sweep Path + Guide Rail: Extent Perpendicular to Path / Full Extents; Path Distance and Guide Rail Distance** | Known gap (parity/surface.md Known gaps). `surface_core.py:116-126` defaults have no extent and no rail distance | Missing | M | `sweep.py` (solid) does not have it either. Perpendicular to Path: trim the rail sweep where the plane square to the path end meets the rail. Full Extents: run the whole rail, with the profile scaled to the rail's end. Two ratios on refs2 and refs3 |
| 15 | **Loft: Edge Alignment Free Edges / Align Edges / Align to Surface**; closed-loft corner matching (Sept 2026); 3+ rails | `surface_core.py:128-147` loft defaults have no alignment. The parity doc's Known gaps lists "closed loft of profiles that twists (no start-point matching)" and "3+ rails refused" | Missing | M (corner matching) / L (alignment, 3+ rails) | Corner matching: before `Part.makeLoft` (`surface_geom.py:1113`), rotate each closed wire's start vertex to the corner nearest the previous wire's start corner (equal corner counts only, as Fusion does). Align Edges / Align to Surface need custom section tangents: L, keep greyed |
| 16 | **Press Pull (Q) on surface faces and edges** | `presspull.py:57` refuses "needs a solid before it". The geometry is slab-and-fuse (`presspull_core.py:38-170`). Not in `SURFACE_MODIFY` | Refused, and missing from the menu | L | Edges: hand them to row 4's surface fillet. Faces: Offset Face on a shell is not bound (no per-face `SetOffsetOnFace`). Instead, drop the face, `makeOffsetShape` that face alone, extend its neighbours naturally (row 9), trim them against the moved face (`cells_for_trim`), then sew. List it greyed with the reason if row 9 is not done |
| 17 | **INSPECT > Environmental Map Analysis** (Sept 2026, A: B-SEP26) | `ribbon_config.py:214-243` INSPECT has Zebra, Curvature Map and so on, but no environment map. `surface_analysis.py:27-47` KINDS has no such kind | Missing | M | New kind `EnvironmentMapAnalysis` in `surface_analysis.py`. The UI reuses the zebra path (`surface_analysis_ui.py:687-700`) but uses `coin.SoTextureCoordinateEnvironment` and a generated studio-strip `SoTexture2` (the probe confirms the pivy classes exist), with Reflection Strength = texture blend. It stays live while editing (same timer as unlocked zebra) |
| 18 | **Sketch > Project/Include > Isoparametric Curve** (Mar 2026; U/V curves of a face, one at a distance or several distributed) | `ribbon_config.py:828-833` Project / Include has Project, Intersect, Include 3D, Project to Surface. No iso curve | Missing (sketch tab, but surface-driven) | M | `face.Surface.uIso(u)` / `vIso(v)` (probed), trimmed to the face (`face.common` or `Part.Edge(curve, a, b)` clipped by `face.section`), added as 3D geometry the way `SciForge_SketchInclude3D` adds it. Distance from the face edge maps to the parameter by arc length. Outside surface-3's ownership: sketch area |
| 19 | **SURFACE > MODIFY tail and other existing commands**: Silhouette Split, Combine, Physical Material, Appearance, Manage Materials, Change Parameters, Compute All. CREATE head: Derive, Create Base Feature | Present in `SOLID_MODIFY` (`ribbon_config.py:124-172`) and `SOLID_CREATE`, absent from `SURFACE_MODIFY` and `SURFACE_CREATE`. Appearance and Physical Material work on any body (`material.assign` has no solid check). The material dialog's list shows `solid_bodies` only (`material_ui.py:139,150`) | Menu entries missing | S | Ribbon only: copy the SOLID items into the SURFACE groups in Fusion's order (see below). Silhouette Split: Fusion needs a solid target (A: API-STUB), so the entry is enough and its refusal stands. Combine: Fusion combines solids only (G), so the entry is enough and should refuse a surface with "use Stitch". Optional: list surface bodies too in `material_ui._fill_design` |
| 20 | **ASSEMBLE panel on the SURFACE tab** (G; shared panel) | `ribbon_config.py:1086` surface groups = `[SURFACE_CREATE, SURFACE_MODIFY, CONSTRUCT, INSPECT, INSERT, SELECT]`. SOLID has ASSEMBLE (`:1081`) | Missing panel | S | Add `ASSEMBLE` in the same slot SOLID uses (after INSERT, per SciForge's screenshot-checked SOLID order). Luca's screenshot settles whether Fusion puts it before CONSTRUCT |
| 21 | **Stitch: Operation New Body / Join / ...** (used when the result is closed) | `surface_core.py:242` operations = `("new_body",)` | Partial | S | Allow `SOLID_OPERATIONS`. When the stitch closes into a solid and the operation is Join, Cut or Intersect, reuse `surface_geom.thicken_cut(base, solid, op)` against the target solid (as Thicken does) |
| 22 | **Trim tool: a single (non-planar) face of a body** | `TrimPanel.boxes` tool accepts `("sketch_curve","body","plane")` (`surface_ui.py:2326`). A curved face click takes the whole body | Partial (whole body instead of one face) | S | Accept `"face"` and pass that face alone to `trim_cutter` |
| 23 | **Merge** (direct-modeling designs only: merge adjacent faces of one surface body) | Not present anywhere (`grep Merge surface*.py` finds nothing). `Part.ShapeUpgrade.UnifySameDomain` only merges same-geometry faces | Missing (Fusion hides it in parametric designs) | L, low value | Skip, or offer it inside Create Base Feature only: `UnifySameDomain`, plus refit of non-same-domain faces with `BSplineSurface.approximate` (L) |
| 24 | **Ruled: default Ruled Type**, and Corner Type shown as a Rounded / Mitered choice | `surface_core.py:169` defaults to `"tangent"`; dialog order Tangent / Normal / Direction (`surface_ui.py:1823-1827`); Mitered is a check box (`:1832`) | Unverified (G) | S | Wait for Luca's screen capture: research says Fusion's first dialog entry may be Normal (G). Change the default only if confirmed |
| 25 | **New Component offered only in Hybrid designs** (2025 design types) | `surface_core.py:24` always offers New Component | Policy difference (A: H-EXT) | S | Only if SciForge adopts Fusion's design types. Note it in the parity doc |

## Menu and panel order differences

- **Panels**:
  - Fusion: CREATE, MODIFY, (CONFIGURE), ASSEMBLE, CONSTRUCT, INSPECT, INSERT, SELECT.
  - SciForge: CREATE, MODIFY, CONSTRUCT, INSPECT, INSERT, SELECT (`ribbon_config.py:1086`).
  - ASSEMBLE is missing. CONFIGURE does not exist in SciForge at all.
- **CREATE**:
  - Fusion: [New Component], Create Sketch, [Create Form], [Create Base Feature], [Derive] | Extrude,
    Revolve, Sweep, Loft, Patch, Ruled, Offset | **[Pattern ▸, Mirror]** | Thicken, Boundary Fill.
  - SciForge: Create Sketch | Extrude ... Offset | Thicken, Boundary Fill (`ribbon_config.py:504-523`).
  - The order of the commands present matches. Missing: Derive, Create Base Feature, Pattern ▸,
    Mirror (and New Component; Create Form is out of scope).
- **MODIFY**:
  - Fusion: **Press Pull, Fillet, Chamfer** | Trim, Untrim, Extend, Stitch, Unstitch, Reverse Normal,
    (Merge) | Replace Face, Split Face, **Split Body, Silhouette Split, Scale, Combine** |
    **Move/Copy, Align**, Delete | **Physical Material, Appearance, Manage Materials** |
    **Change Parameters, Compute All**.
  - SciForge: Trim ... Reverse Normal | Replace Face, Split Face | Delete (`ribbon_config.py:525-542`).
  - The relative order of the commands present matches. Everything in bold is missing.
- **Toolbar big icons**: SciForge CREATE = Extrude, Loft, Patch, Thicken; MODIFY = Trim, Extend,
  Stitch. Fusion's choice is unconfirmed (G): it needs Luca's screenshot.
- **Wording**: Revolve "Angle" should read "Partial" (A). Ruled "Mitered Corners" check box vs a
  Corner Type choice (G). The Patch Tangency Weight default shows 1.0, where Fusion's is 0.5.

## Already at parity (checked in code, no action)

- Extrude: Start, Direction, Extent, Taper, Symmetric Measurement.
- Revolve: Full and To.
- Sweep: Single Path and Guide Rail with Profile Scaling, Taper, Twist, Orientation, Distance / Distance Two.
- Loft: rails ≤ 2, Centerline, end conditions, Closed, Merge.
- Patch: Connected / Tangent, Interior Rails/Points; G2 waits for core patch #14.
- Ruled: all three types, Angle, Alternate Faces, Mitered.
- Thicken: Sharp / Rounded, Symmetric, all operations.
- Boundary Fill: cells, Remove Tools, operations.
- Trim: cells, mutual trim.
- Untrim: All, Internal, External, Extend.
- Extend: Natural, Tangent, Perpendicular, chaining.
- Stitch: tolerance 1 mm, green/red edge display, closing into a solid.
- Unstitch: chain.
- Reverse Normal.
- Replace Face and Split Face are on the menu.
