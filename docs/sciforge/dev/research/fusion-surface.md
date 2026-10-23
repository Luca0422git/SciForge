# Fusion SURFACE tab: behaviour spec for SciForge (research, 2026-10-23)

Black-box documentation research only (behaviour, option names, choices, defaults). SciForge copies
Fusion's behaviour, never its assets, wording or code (CLAUDE.md).

## How this was researched, and its limits

- help.autodesk.com, autodesk.com and forums.autodesk.com could **not be fetched** from the
  sandbox (DNS/proxy refused). Everything from them comes from **web-search excerpts** of those pages.
- The Fusion API reference was read in two ways: (1) search excerpts of the current API pages
  (help.autodesk.com/cloudhelp/ENU/Fusion-360-API/...), (2) the full text of Autodesk's own API
  definition file `adsk/fusion.py` as repackaged on PyPI (`adsk` 2.0.12157, early 2022; API
  docstrings give option names, enum orders and defaults). Newer API additions (2022-2026) come from
  search excerpts only.
- The shared web-search budget (200 per turn, all agents) ran out before the exact 2025-2026 menu
  order could be confirmed from a screenshot or a tutorial listing. Menu **positions** below are
  therefore mostly **G**; the **presence** of each command is sourced.
- Tags: **A** = Autodesk (help page, API reference, Autodesk blog / release notes; URL given),
  **F** = forum or third-party tutorial (URL given), **G** = inference (ours; Luca's screen captures
  settle it).

Short URL keys used in the tables:

| Key | URL |
|---|---|
| H-MOD | https://help.autodesk.com/cloudhelp/ENU/Fusion-Patch/files/SFC-MODIFY-SURFACE.htm |
| H-FROMGEO | https://help.autodesk.com/cloudhelp/ENU/Fusion-Patch/files/SFC-CREATE-SURFACE-FROM-SKETCH.htm |
| H-EXT / H-EXT-REF | https://help.autodesk.com/cloudhelp/ENU/Fusion-Patch/files/SFC-EXTRUDE.htm , .../SFC-REF-EXTRUDE.htm |
| H-REV / H-REV-REF | .../Fusion-Patch/files/SFC-REVOLVE.htm , .../SFC-REF-REVOLVE.htm |
| H-SWP | .../Fusion-Patch/files/SFC-SWEEP.htm |
| H-LOFT / H-LOFT-REF | .../Fusion-Patch/files/SFC-LOFT.htm , .../SFC-REF-LOFT-DLG.htm |
| H-PATCH / H-PATCH-REF | .../Fusion-Patch/files/SFC-PATCH.htm , .../SFC-REF-PATCH.htm |
| H-OFF / H-OFF-REF | .../Fusion-Patch/files/SFC-OFFSET.htm , .../SFC-REF-OFFSET.htm |
| H-THK | https://help.autodesk.com/cloudhelp/ENU/Fusion-Model/files/GUID-471827A2-EDAE-411B-A1F5-C87B54615D53.htm |
| H-TRIM / H-TRIM-REF | .../Fusion-Patch/files/SFC-TRIM.htm , .../SFC-REF-TRIM.htm |
| H-UNTRIM | .../Fusion-Patch/files/SFC-UNTRIM.htm |
| H-EXTEND / H-EXTEND-REF | .../Fusion-Patch/files/SFC-EXTEND.htm , .../SFC-REF-EXTEND.htm |
| H-STITCH | https://help.autodesk.com/view/fusion360/ENU/?contextId=SFC-STITCH |
| H-UNSTITCH | .../Fusion-Patch/files/SFC-UNSTITCH.htm , .../SFC-REF-UNSTITCH.htm |
| H-REVN | .../Fusion-Patch/files/GUID-3B2D0A04-B93C-4F63-9512-00D91F042C2D.htm |
| H-MERGE | .../Fusion-Patch/files/SFC-MERGE.htm , .../SFC-REF-MERGE.htm |
| H-FILCH | .../Fusion-Patch/files/SFC-FILLET-CHAMFER.htm |
| H-SFIL / H-SCHAM | .../Fusion-Model/files/SLD-REF-FILLET.htm , .../SLD-REF-CHAMFER.htm |
| H-MIRROR | .../Fusion-Model/files/SLD-REF-MIRROR-DIALOG.htm , .../SLD-PATTERNS.htm |
| H-CURVMAP | .../Fusion-Model/files/GUID-03B235BA-C271-42D0-B3C6-09DFE9E60E30.htm |
| API:<Name> | https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/<Name>.htm |
| API-STUB | Autodesk `adsk/fusion.py` 2.0.12157 via https://pypi.org/project/adsk/ (docstrings) |
| B-MAY25 | https://www.autodesk.com/products/fusion-360/blog/whats-new-may-2025-major-product-update/ (+ https://www.autodesk.com/products/fusion-360/blog/autodesk-fusion-6-month-rewind/) |
| B-SEP25 | https://www.autodesk.com/products/fusion-360/blog/september-2025-product-update-whats-new/ |
| B-JAN26 | https://www.autodesk.com/products/fusion-360/blog/january-2026-product-update-whats-new/ |
| B-MAR26 | https://www.autodesk.com/products/fusion-360/blog/march-2026-product-update-whats-new/ |
| B-JUL26 | https://www.autodesk.com/products/fusion-360/blog/july-2026-major-product-update-whats-new/ |
| B-SEP26 | https://www.autodesk.com/products/fusion-360/blog/september-2026-major-product-update-whats-new/ (+ .../fusion-september-2026-update-top-features/) |
| RN-2026 | https://help.autodesk.com/view/fusion360/ENU/?guid=FIC-REL-NOTES-INC |
| B-BFILL | https://www.autodesk.com/products/fusion-360/blog/?p=11811 (Boundary Fill tech tip) |
| B-CFG | https://www.autodesk.com/products/fusion-360/blog/?p=83571 (Configure tab in surface commands) |
| B-TOL | https://www.autodesk.com/products/fusion-360/blog/fusion-360-3d-modeling-loose-tolerances/ |
| B-PATCOMP | https://www.autodesk.com/products/fusion-360/blog/autodesk-fusion-mirror-and-pattern-compute-options/ |
| B-SWP | https://www.autodesk.com/products/fusion-360/blog/?p=56141 (Get Smart Part 2: Sweep) |
| F-STOL | https://forums.autodesk.com/t5/fusion-design-validate-document/stitch-problem/m-p/6619111 |
| F-STUBE | https://forums.autodesk.com/t5/fusion-design-validate-document/intersect-sketch-accuracy-issue/td-p/6849444 |
| F-MERGE | https://forums.autodesk.com/t5/fusion-design-validate-document/merge-surfaces/m-p/9629574 |
| F-DELFACE | https://forums.autodesk.com/t5/fusion-360-ideastation-archived/delete-face/idc-p/6453888 |
| F-FIL2 | https://forums.autodesk.com/t5/fusion-360-ideastation-archived/filleting-two-intersecting-surfaces-in-the-patch-environment/m-p/6698674 |
| F-TRIM | https://forums.autodesk.com/t5/fusion-manufacture-forum/surface-trim-tool-help-updated-with-new-example/td-p/11712222 |
| F-BFCELL | https://forums.autodesk.com/t5/fusion-design-validate-document/boundary-fill-cell-selection/td-p/13174495 |
| F-UNSTITCH | https://forums.autodesk.com/t5/fusion-support-forum/unstitch-bug/m-p/7107351 |
| F-VDCI | https://vdci.edu/learn/fusion/fusion-thicken-surface-solid |
| F-COURSE | https://www-pt.autodesk.com/learn/ondemand/course/fusion360-design-for-manufacturing-cert-prep/unit/7G2VROdDsmySRS7S5pQ9Ty (Autodesk course; tagged A where it is Autodesk's own) |

---

## 1. Tab layout and menu order

The Design workspace tabs are SOLID, SURFACE, MESH, SHEET METAL, (PLASTIC), UTILITIES/TOOLS; each
tab is a set of panels (A: [API:UserInterface_UM](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/UserInterface_UM.htm)). The SURFACE tab was formerly the "Patch" workspace (A, Autodesk blog "Fusion 360 is getting a fresh new look").

**Panels of the SURFACE tab (left to right)**, best reconstruction:

| # | Panel | Notes | Src |
|---|---|---|---|
| 1 | CREATE | surface-creation tools (below) | A (H-FROMGEO) |
| 2 | MODIFY | surface-edit tools (below) | A (H-MOD) |
| 3 | CONFIGURE | only if the SOLID tab has it in the same build (Configurations, 2023+); B-CFG says surface commands (Trim, Untrim, Extend, Stitch, Unstitch, Reverse Normal) got a contextual Configure tab | A (B-CFG) for the configure support, G for a panel on this tab |
| 4 | ASSEMBLE | shared panel (New Component, Joint, ...), as on SOLID | G |
| 5 | CONSTRUCT | same panel as SOLID (planes, axes, points). July 2026: perpendicular planes on curved faces, resize, offset during creation, mirror construction geometry | G (same panel); A (B-JUL26) for the 2026 additions |
| 6 | INSPECT | same panel as SOLID; Sept 2026 regrouped the Inspect menu and added **Environmental Map Analysis** | A (B-SEP26, RN-2026) |
| 7 | INSERT | same panel as SOLID | G |
| 8 | SELECT | same panel as SOLID | G |

SciForge today: `[SURFACE_CREATE, SURFACE_MODIFY, CONSTRUCT, INSPECT, INSERT, SELECT]`
(`src/Mod/SciForge/sciforge/ribbon_config.py` line ~1086). Missing vs SOLID: CONFIGURE, ASSEMBLE (G).

### SURFACE > CREATE (menu order; presence sourced, positions G unless stated)

| # | Command | Src (presence) | Note |
|---|---|---|---|
| 1 | New Component | G | shared head of CREATE on every Design tab |
| 2 | Create Sketch | G | |
| 3 | Create Form (enters the Form contextual environment) | G | |
| 4 | Create Base Feature (Hybrid/history designs) | G | |
| 5 | Derive | G | |
| — | separator | | |
| 6 | Extrude | A (H-EXT, F-COURSE) | |
| 7 | Revolve | A (H-REV) | |
| 8 | Sweep | A (H-SWP) | |
| 9 | Loft | A (H-LOFT) | |
| 10 | Patch | A (H-PATCH) | |
| 11 | Ruled | A (H-FROMGEO) | |
| 12 | Offset | A (H-OFF) | |
| — | separator | | |
| 13 | Pattern ▸ Rectangular Pattern / Circular Pattern / Pattern on Path | A (H-MIRROR: "Design > Solid or Surface > Create") | |
| 14 | Mirror | A (H-MIRROR) | |
| — | separator | | |
| 15 | Thicken | A (H-THK, also on SOLID) | |
| 16 | Boundary Fill | A (B-BFILL: "at the lower end of the Create drop down menu") | last or near-last: A |

Not a Fusion command: "Offset Curve to Surface" (only Maya's `offsetCurveOnSurface` turned up; nothing
in Fusion help or API) (G, from absence). The nearest Fusion features are the sketch's Project to
Surface / Intersection Curve and, since **March 2026**, **Sketch > Create > Project/Include >
Isoparametric Curve** (U or V curves of a face; one curve at a distance from the face edge, or several
distributed; associative by default; API `SketchIsoparametricCurves`, "introduced April 2026")
(A: B-MAR26, API:SketchIsoparametricCurves, API:SketchIsoparametricCurve_isUDirection). July 2026:
Manage Lost Projections relinks isoparametric curves (A: B-JUL26 / RN-2026).

### SURFACE > MODIFY (menu order; presence sourced, positions G unless stated)

H-MOD lists the surface modify tools as: Press Pull, Fillet, Chamfer, Trim, Untrim, Extend, Stitch,
Unstitch, Merge, Reverse Normal, Scale, Split Face, Split Body (A). Reconstructed menu:

| # | Command | Src | Note |
|---|---|---|---|
| 1 | Press Pull (Q) | A (H-MOD) | faces / fillets of surface bodies |
| 2 | Fillet (F) | A (H-FILCH: "Surface > Modify > Fillet") | edges of surface bodies |
| 3 | Chamfer | A (H-FILCH: "Surface > Modify > Chamfer") | |
| — | separator | | |
| 4 | Trim | A (H-TRIM) | |
| 5 | Untrim | A (H-UNTRIM) | |
| 6 | Extend | A (H-EXTEND) | |
| 7 | Stitch | A (H-STITCH) | |
| 8 | Unstitch | A (H-UNSTITCH) | |
| 9 | Reverse Normal | A (H-REVN) | |
| 10 | Merge (only with design history OFF) | A (H-MERGE, H-MOD) | hidden/absent in parametric designs (F-MERGE) |
| — | separator | | |
| 11 | Replace Face | G (also SOLID) | API `replaceFaceFeatures` (A, API-STUB) |
| 12 | Split Face | A (H-MOD) | |
| 13 | Split Body | A (H-MOD) | |
| 14 | Silhouette Split | G | API `silhouetteSplitFeatures` (A, API-STUB) |
| 15 | Scale | A (H-MOD) | |
| 16 | Combine | G | |
| — | separator | | |
| 17 | Move/Copy (M) | G | |
| 18 | Align | G | |
| 19 | Delete (Del) | A (API:SurfaceDeleteFaceFeatures, F-DELFACE) | in the surface context a face is deleted **without healing** |
| — | separator | | |
| 20 | Physical Material / Appearance (A) / Manage Materials | G | shared tail of MODIFY |
| 21 | Change Parameters / Compute All | G | |

---

## 2. CREATE commands

Common to all surface CREATE commands: the Operation list holds only **New Body** (default) and
**New Component**; the result is an open (surface) body; no end caps (A: API-STUB `PatchFeatureInput.operation`,
`OffsetFeatureInput.operation`, `SweepFeatureInput.isSolid`; H-EXT). In the 2025+ design types,
**New Component is offered only in a Hybrid design** (A: H-EXT).

### 2.1 Extrude (surface)

| Input | Type/choices | Default | What it does | Src |
|---|---|---|---|---|
| Profiles | sketch profiles, open or closed sketch curves, planar faces, single-line text, edges of bodies | — | the curves swept straight into surfaces | A (H-EXT, H-EXT-REF) |
| Chaining | check box | on | off: one edge/curve per click (extrude a single edge) | A (F-COURSE) |
| Start | Profile Plane / Offset Plane (Offset value) / From Object (Object + Offset) | Profile Plane | where the extrusion starts | A (H-EXT) |
| Direction | One Side / Two Sides (distance per side) / Symmetric | One Side | | A (H-EXT) |
| Measurement (Symmetric) | Half Length / Whole Length | Half Length (G) | how the symmetric distance is measured | A (H-EXT) |
| Extent Type | Distance / To Object / All | Distance | All = through the design; To Object = to a body, face or plane | A (H-EXT) |
| Distance | length, arrow handle | — | | A |
| To Object: Chain Faces | Chain Faces / Extend Faces | Chain Faces (G) | stop on the picked face and the faces tangent to it, or on the picked face extended | A (H-EXT-REF; wording from the solid page) |
| To Object: Match Shape | check box | off (G) | the extrusion ends on the faces adjacent to the selected face, matching its shape | A (H-EXT-REF) |
| Flip (All) | button | — | All goes the other way | A (existing parity doc) |
| Taper Angle | angle (per side with Two Sides) | 0 deg | tapers the extrusion | A (H-EXT) |
| Operation | New Body / New Component (Hybrid only) | New Body | | A (H-EXT) |

### 2.2 Revolve (surface)

| Input | Type/choices | Default | What it does | Src |
|---|---|---|---|---|
| Profile | sketch profiles/curves, edges | — | | A (H-REV) |
| Axis | linear (or circular, per the page) object: sketch line, edge, construction / origin axis | — | the axis turned around | A (H-REV-REF) |
| Project Axis | check box | on (G) | projects the axis onto the profile's sketch plane; off keeps the axis where it is | A (H-REV-REF) |
| Extent Type | **Partial** (Angle) / **To Object** / **Full** | Partial (G) | Partial: to an angle; To Object: to a body, face or plane; Full: 360 deg | A (H-REV-REF) |
| Direction (Partial) | One Side / Two Sides (angle per side) / Symmetric | One Side | | A (H-REV-REF) |
| Direction (To Object) | One Side / Two Sides | One Side | Symmetric not offered | A (H-REV-REF) |
| Angle | angle, handle | 360? (G) | | A |
| Operation | New Body / New Component | New Body | | A |

Note: Fusion's UI word is **Partial**, not "Angle" (SciForge's current label). (A)

### 2.3 Sweep (surface)

| Input | Type/choices | Default | What it does | Src |
|---|---|---|---|---|
| Type | Single Path / Path + Guide Rail / **Path + Guide Surface** | Single Path | | A (H-SWP) |
| Profile | sketch profile, sketch curve, planar face(s) (co-planar) | — | | A (H-SWP, API-STUB `profile`) |
| Path | sketch curves / edges (a smooth chain) | — | | A |
| Chain Selection | check box | on | tangent chains of path; with a guide surface also adds tangent-connected faces as guides | A (API:SweepFeatureInput_isChainSelection) |
| Distance (Single Path) | 0..1 share of the path (shown as %) | 1.0 (100 %) | how far along the path | A (H-SWP; API-STUB `distanceOne`) |
| Distance Two | 0..1 | 1.0 (0 if the path is closed) | the other side when the path runs on both sides of the profile; ignored with a guide rail | A (API-STUB `distanceTwo`) |
| Orientation (Single Path) | Perpendicular / Parallel | Perpendicular | ignored with a guide rail | A (API-STUB `orientation`) |
| Taper Angle (Single Path, Perpendicular) | angle; negative = inward | 0 | ignored with a guide rail / surface | A (H-SWP, API-STUB) |
| Twist Angle (Single Path) | angle | 0 | twist round the path | A (H-SWP) |
| Guide Rail | sketch curve / edge | — | controls scale and turn of the profile | A (H-SWP) |
| Profile Scaling (Guide Rail) | Scale / Stretch / None | **Scale** | | A (API-STUB `profileScaling`) |
| Extent (Guide Rail) | Perpendicular to Path / Full Extents | **Perpendicular to Path** | where the sweep stops relative to the rail | A (H-SWP, API-STUB `extent`) |
| Path Distance / Guide Rail Distance | 0..1 | 1.0 (G) | shares of path / rail used | A (existing parity doc) |
| Flip direction | toggle | off | rail sweeps whose path runs on both sides of the profile | A (API-STUB `isDirectionFlipped`) |
| Guide Surface (Path + Guide Surface) | faces (array of BRepFace) | — | controls the profile's scale and orientation (twist relative to the surface normal); tangent faces chained by default | A (H-SWP, B-SWP, API:SweepFeatureInput_guideSurfaces "introduced January 2024") |
| Operation | New Body / New Component | New Body | surface sweep has no end caps | A |

### 2.4 Loft (surface)

| Input | Type/choices | Default | What it does | Src |
|---|---|---|---|---|
| Profiles | ordered list: sketch profiles/curves, edges, points (first/last) | — | sections the loft passes through | A (H-LOFT) |
| Chain Selection / Tangent Chain | check box | on (G) | one click takes the chain | A (H-LOFT) |
| End condition (first / last profile) | Connected (G0, "Free") / Direction / Tangent (G1) / Curvature (G2) / Smooth / Sharp / Point Tangent | Connected | Direction: sketch curves; G1/G2: body edges; Sharp / Point Tangent: a point | A (H-LOFT-REF) |
| Takeoff Weight, Takeoff Angle | numbers | 1, 0 deg (G) | only with Direction | A (H-LOFT-REF) |
| Tangency Weight | number | 1 (G) | with Tangent / Smooth / Point Tangent | A (H-LOFT-REF; F tutorial) |
| **Edge Alignment** (surface loft, first/last profile on an edge with G1/G2) | **Free Edges / Align Edges / Align to Surface** | Free Edges (G) | Free: no alignment; Align Edges: follow the tangent (G2: also curvature) of a non-tangent-continuous edge at the profile end; Align to Surface: follow the surface's parameter-curve direction at the profile end with the greatest angle to the profile tangent | A (H-LOFT-REF) |
| Guide Type | Rails / Centerline | Rails | | A (H-LOFT) |
| Rails | 2D/3D curves; must cross every profile and end on/beyond the first and last | — | | A (H-LOFT) |
| Centerline | one curve; need not cross the profiles; sections held normal to it | — | | A (H-LOFT) |
| Closed | check box | off | first profile reused as last, smooth join | A (API-STUB `isClosed`) |
| Tangent Edges | Merge / Keep | not found (G) | Merge removes edges between tangent faces | A (H-LOFT-REF, API-STUB `isTangentEdgesMerged`) |
| Operation | New Body / New Component | New Body | | A |

Sept 2026 (v.2705.1.11): **deterministic mapping for closed loft profiles with matching numbers of
clearly defined corners** (corners matched predictably; other cases unchanged; no dialog change)
(A: B-SEP26, RN-2026).

### 2.5 Patch

| Input | Type/choices | Default | What it does | Src |
|---|---|---|---|---|
| Boundary Edges | a sketch profile, one sketch curve, one open B-Rep edge (used by one face only), or a path; an open pick auto-finds the connected closed loop | — | the hole to fill | A (H-PATCH-REF; API-STUB `boundaryCurve`) |
| Enable Chaining | check box | on (G) | one click takes the loop | A (H-PATCH-REF) |
| Group Edges | check box | **on** | on: one Continuity + Tangency Weight for all edges (the first edge's); off: one row per edge, each with its own Continuity and Weight | A (H-PATCH-REF, API:PatchFeatureInput_isGroupEdges) |
| Continuity | Connected (G0) / Tangent (G1) / Curvature (G2) | **Connected** | match to the neighbour faces; ignored for sketch curves | A (API-STUB `continuity`; H-PATCH-REF) |
| Tangency Weight | number | **0.5** | strength of the tangent pull; ignored with Connected | A (API:PatchFeatureInput_groupWeight, API:PatchFeatureInput_getContinuity) |
| Interior Rails / Points | sketch curves, paths, sketch points, B-Rep edges, construction points | none | interior curves/points the patch must pass through | A (H-PATCH-REF; API:PatchFeature_interiorRailsAndPoints "introduced November 2022") |
| **Reverse Normal** + **Flip** | check box + button | off | flips the new patch's normal inside the command (saves a Reverse Normal step) | A (B-JAN26 v.2606.1.22, RN-2026, H-PATCH) |
| Operation | New Body / New Component | New Body | | A (API-STUB) |

### 2.6 Ruled

| Input | Type/choices | Default | What it does | Src |
|---|---|---|---|---|
| Edges / Profile | sketch curves or B-Rep edges (a profile built from edges) | — | the edges the ruled band grows from | A (API-STUB `profile`) |
| Ruled Type | Normal / Tangent / Direction (API enum order: Tangent, Normal, Direction) | not found (G: Normal, the first in the dialog) | band normal to, tangent to the face, or along a direction | A (API-STUB `RuledSurfaceTypes`) |
| Direction | linear edge, construction axis, planar face, construction plane | — | only for Direction; picking one switches the type to Direction | A (API-STUB `direction`) |
| Distance | length | — | band width | A (API-STUB) |
| Angle | angle | 0 (G) | angle of the band relative to the reference face | A (API-STUB) |
| Alternate Faces | check box | off | for an edge shared by two faces (solid edge, interior surface edge): measure the angle from the other face | A (API-STUB `alternateFace`) |
| Corner Type | Rounded / Mitered | **Rounded** | how the band turns round convex corners | A (API-STUB `cornerType`, API:RuledSurfaceCornerTypes) |
| Operation | New Body / New Component | New Body | | A (API-STUB) |

### 2.7 Offset (surface)

| Input | Type/choices | Default | What it does | Src |
|---|---|---|---|---|
| Faces | faces of any bodies (several bodies allowed) | — | | A (H-OFF; API-STUB) |
| Chain Selection | check box | **on** | adds tangent-connected faces | A (H-OFF-REF; API-STUB createInput default true) |
| **Offset Type** | **Sharp Offset / Rounded Offset** | **Sharp** | corner handling, "similar to the Shell tool": Sharp = original behaviour (extended/sharp corners), Rounded = rounded offset corners | A (B-MAY25 "Rounded Offset Now Available in Surface Offset"; H-OFF; API:fusion_OffsetTypes, API:fusion_OffsetFeature_offsetType "introduced September 2026") |
| Distance | length, arrow handle; positive = along the face normal, negative = against | — | | A (API-STUB `distance`) |
| Operation | New Body / New Component | New Body | | A (API-STUB) |

Date note: UI option shipped May 2025 (A, B-MAY25); the API enum arrived September 2026 (A).

### 2.8 Thicken (also SOLID > CREATE)

| Input | Type/choices | Default | What it does | Src |
|---|---|---|---|---|
| Faces | faces and/or surface bodies, any components, need not touch | — | | A (H-THK; API-STUB) |
| Chain Selection | check box | **on** | tangent-connected faces too; clear to pick single faces | A (H-THK; API-STUB createInput default true) |
| Thickness | length; positive = outside, negative = inside | — | cannot remove a face: the maximum is where a face would vanish | A (H-THK) |
| Direction | One Side / Symmetric | One Side (G) | | A (H-THK; API-STUB `isSymmetric`) |
| **Thicken Type** | **Sharp / Rounded** | **Sharp** | Rounded rounds the offset corners (plastic-part friendly) | A (B-SEP25 "New Rounded Thicken", v.2604.1.25; API:ThickenFeatureInput_thickenType, API:fusion_ThickenTypes "introduced September 2025"); F (F-VDCI) |
| Operation | Join / Cut / Intersect / New Body / New Component | New Body (G) | | A (API-STUB `operation`) |

### 2.9 Boundary Fill (also SOLID > CREATE)

| Input | Type/choices | Default | What it does | Src |
|---|---|---|---|---|
| Select Tools (Tools) | construction planes and open or closed bodies | — | the walls; Fusion computes the closed cells | A (API:BoundaryFillFeatures_createInput; API-STUB `tools`) |
| Select Cells | ticks per cell (canvas or list); window selection picks only cells fully inside | none | the selected cells are **kept** (opposite of Trim, where selected cells are removed) | A (API:BRepCell_isSelected); F (F-BFCELL) |
| Remove Tools | check box | off (G) | consume the tool bodies | A (existing parity doc) |
| Operation | Join / Cut / Intersect / New Body / New Component | New Body (G) | | A (API-STUB `operation`) |

### 2.10 Pattern and Mirror on surfaces

| Input | Type/choices | Default | What it does | Src |
|---|---|---|---|---|
| Pattern ▸ | Rectangular / Circular / Pattern on Path; Object Type Faces / Bodies / Features / Components | — | as on SOLID; surface bodies can be patterned as bodies | A (H-MIRROR / SLD-PATTERNS) |
| Compute Option | Optimized / Identical / Adjust | Feature patterns default to **Identical** since Jan 2026 | | A (B-PATCOMP; B-JAN26) |
| Mirror: Operation Join | — | — | mirrored **surface bodies are stitched** to the originals | A (H-MIRROR) |
| Mirror: Stitch Tolerance | length | not found | used when joining mirrored surface bodies | A (API:MirrorFeatureInput_stitchTolerance) |

---

## 3. MODIFY commands

### 3.1 Fillet / Chamfer on surface bodies

Surface > Modify > Fillet / Chamfer: pick edges of a surface body, shape with the manipulator or the
dialog, OK (A: H-FILCH). The dialog is the SOLID one (A: H-SFIL, H-SCHAM):

| Input | Type/choices | Default | What it does | Src |
|---|---|---|---|---|
| Type | Fillet / Rule Fillet / Full Round Fillet | Fillet | Rule Fillet: all edges of one set, or shared edges of two sets; Round/Fillets topology | A (H-SFIL) |
| Edges / Faces / Features | selection sets | — | | A (H-SFIL) |
| Radius Type | Constant / Chord Length / Variable (single edges) / Asymmetric | Constant | | A (H-SFIL) |
| Continuity | Tangent (G1) / Curvature (G2) | G1 | | A (H-SFIL) |
| Tangency Weight | number (G2) | 1 (G) | | A (API:ChordLengthFilletEdgeSetInput_tangencyWeight) |
| Corner Type | Rolling Ball / Setback | Rolling Ball (G) | | A (H-SFIL) |
| Tangent Chain | check box | on | | A (H-SFIL) |
| Chamfer Type | Equal Distance / Two Distance / Distance and Angle; Corner Type Chamfer / Miter / Blend | Equal Distance | | A (H-SCHAM) |

Rule: Fusion **cannot fillet between two separate surface bodies**; trim both, Stitch them into one
body, then fillet the shared edge (F: F-FIL2). No "surface blend between two bodies" command was found
(G). Rule Fillet on surface bodies: not confirmed (G).

### 3.2 Trim

| Input | Type/choices | Default | What it does | Src |
|---|---|---|---|---|
| Trim Tool | a surface (patch) body, a B-Rep face, a construction plane or a sketch curve | — | intersects the surfaces to trim; "splits intersecting surfaces" (the tool is cut too) | A (API-STUB `trimTool`, H-MOD) |
| Cells / Objects to remove | cells computed from the tool; click the pieces to remove | none | selected cells are **removed** | A (API-STUB `bRepCells`; API:BRepCell_isSelected) |
| — | the tool must cross the whole surface (extend it first) | | | F (F-TRIM) |

### 3.3 Untrim

| Input | Type/choices | Default | What it does | Src |
|---|---|---|---|---|
| Faces (or edges/loops in Manual) | faces of surface bodies only | — | | A (H-UNTRIM; API-STUB) |
| Type | All Edges / Internal Edges / External Edges / **Manual** | All Edges (G: enum 0) | Manual: pick the loops/edges yourself; Ctrl/Cmd suppresses the preview while editing the set | A (H-UNTRIM; API:UntrimLoopTypes) |
| Extend | distance | 0 | extends the untrimmed face past its old outer edge (All / External only) | A (H-UNTRIM; API-STUB `extensionDistance`) |
| **Keep Copy** | check box | off (G) | keeps a copy of the original surface | A (H-UNTRIM) |
| rule | only loops whose edges have a single face can be removed | | | A (API-STUB) |

### 3.4 Extend

| Input | Type/choices | Default | What it does | Src |
|---|---|---|---|---|
| Edges | outer edges of an open body, all from one body | — | | A (API-STUB createInput) |
| Enable Chaining | check box | **on** | tangent/curvature-continuous, end-connected edges added | A (H-EXTEND-REF; API-STUB) |
| Distance | length; Natural and Tangent: positive only; Perpendicular: ±(positive = along the faces' normal) | — | | A (API-STUB createInput) |
| Extend Type | Natural / Tangent / Perpendicular | Natural (G: enum 0) | Natural continues the face's own surface (curvature-aware); Tangent adds flat faces tangent to it; Perpendicular adds faces square to it. Tangent and Perpendicular need end-connected edges; Natural does not | A (H-EXTEND, H-EXTEND-REF, API-STUB) |
| Edge Alignment (Natural only) | Free Edges (G0) / Align Edges (G1) | Free Edges (G: enum 0) | | A (H-EXTEND-REF; API-STUB `extendAlignment`) |

July 2026 fix: extending a thickened surface extended both inner and outer edges when only the outer
was picked (A: RN-2026) - i.e. only the picked edges must move.

### 3.5 Stitch

| Input | Type/choices | Default | What it does | Src |
|---|---|---|---|---|
| Stitch Surfaces | surface (open) bodies | — | | A (API-STUB) |
| Tolerance | length (slider + value) | **1.0 mm** (cannot be changed as a default) | max gap closed ("tolerant edge" = a tube of that radius); keep it small | F (F-STOL, F-STUBE); A (B-TOL) |
| Analysis display | edges within tolerance green; counts of free edges and edges to be stitched | — | | A (H-STITCH) |
| Operation | New Body / Join / ... | New Body (G) | used only when the result is a closed solid | A (API-STUB `operation`) |
| result | several closed volumes → several solids; several shells not closed → one surface body | | | A (API-STUB) |

### 3.6 Unstitch

| Input | Type/choices | Default | What it does | Src |
|---|---|---|---|---|
| Faces / Bodies | faces of solids or surfaces, any bodies | — | each face becomes its own surface body | A (H-UNSTITCH; API-STUB) |
| Chain Selection | check box | **on** | adds the tangentially connected faces | A (H-UNSTITCH; API:UnstitchFeatures_add) |

Forum: unstitching/deleting can leave disconnected shells reported as one body (bug) (F: F-UNSTITCH).

### 3.7 Reverse Normal

| Input | Type/choices | Default | What it does | Src |
|---|---|---|---|---|
| Surface bodies | one or more open bodies | — | all faces of each body reversed; mainly to repair imports | A (H-REVN; API-STUB) |

### 3.8 Merge (direct modeling only)

| Input | Type/choices | Default | What it does | Src |
|---|---|---|---|---|
| Faces | two or more adjacent faces of one surface body | — | merged into one face (repairing imports, simplifying for analysis) | A (H-MERGE) |
| availability | only with design history off, or inside a base feature; not a timeline feature | | | A (H-MOD; API:Features_mergeFacesFeatures); F (F-MERGE) |

### 3.9 Delete (surface context)

| Behaviour | Src |
|---|---|
| On the SURFACE tab, deleting faces removes them **without healing** (SurfaceDeleteFaceFeature; a solid becomes a surface body at the first deleted face). On SOLID, Delete heals the hole (DeleteFaceFeature, fails if it cannot) | A (API:SurfaceDeleteFaceFeatures, API:DeleteFaceFeatures); F (F-DELFACE) |

### 3.10 Split Face, Split Body, Silhouette Split, Replace Face, Scale, Press Pull

| Command / input | Type/choices | Default | Src |
|---|---|---|---|
| Split Face: Faces to Split | faces of solid and/or open bodies | — | A (API-STUB) |
| Split Face: Splitting Tool | bodies, planes, faces, sketch curves (one or several) | — | A (API-STUB) |
| Split Face: Split Type | Split with Surface (intersection) / Along Vector (direction: linear edge, sketch line, construction line, planar face normal) / Closest Point | Surface intersection (G: enum 0) | A (API-STUB `SplitFaceSplitTypes`) |
| Split Face: Extend Splitting Tool | check box | on (G) | A (API-STUB) |
| Split Body: Body to Split | solid **or open** bodies | — | A (API-STUB `splitBodies`) |
| Split Body: Splitting Tool | body (solid or open), construction plane, profile, face | — | A (API-STUB) |
| Split Body: Extend Splitting Tool | check box | on (G) | A (API-STUB) |
| Silhouette Split: Target Body | one solid body | — | A (API-STUB) |
| Silhouette Split: View Direction | construction axis, linear edge, planar face, construction plane | — | A (API-STUB) |
| Silhouette Split: Operation | Split Faces Only / Shelled Body / Solid Body | Split Faces Only (G: enum 0) | A (API-STUB `SilhouetteSplitOperations`) |
| Replace Face | source faces, target face/surface body | — | A (API `replaceFaceFeatures`); behaviour in `parity/direct-modify.md` |
| Scale | listed among surface modify tools | — | A (H-MOD) |
| Press Pull | resizes faces, bodies, fillets, chamfers; makes a Press Pull / Offset Face feature | — | A (H-MOD; API-STUB `OffsetFacesFeatures` "created in the UI using Press Pull") |

---

## 4. INSPECT additions relevant to surfaces

| Tool | What it does | Src |
|---|---|---|
| Curvature Comb, Zebra, Draft, Curvature Map, Isocurve, Accessibility, Minimum Radius Analysis | existing surface-quality tools (SciForge has them) | A (H-CURVMAP) / repo |
| **Environmental Map Analysis** (Sept 2026) | live reflection map on picked geometry to judge surface quality and curvature continuity; stays active while editing; several analysis nodes; reflection strength setting | A (B-SEP26, RN-2026) |
| Inspect menu regrouped (Sept 2026) | "improved grouping" (exact grouping not found) | A (B-SEP26) |
| API Oct 2026 | curvature comb / curvature map / iso-curve analysis exposed in the API | A (search excerpt of API What's New) |

---

## 5. Timeline of surface changes found (2022-2026)

| When | Change | Src |
|---|---|---|
| Jul 2022 | Stitch/Unstitch faster on imported CATIA surfaces | A (Fusion blog ?p=33146) |
| Nov 2022 | Patch Interior Rails / Points (API) | A (API:PatchFeature_interiorRailsAndPoints) |
| (Nov + Mar, year unclear) | contextual Configure tab in Trim, Untrim, Extend, Stitch, Unstitch, Reverse Normal | A (B-CFG) |
| Jan 2024 | Sweep Path + Guide Surface (API guideSurfaces) | A (API:SweepFeatureInput_guideSurfaces) |
| May 2025 | Surface Offset: Offset Type Sharp / Rounded | A (B-MAY25) |
| Jul 2025 | sketch Offset can offset an existing offset | F (Fabbaloo, https://www.fabbaloo.com/news/fusion-360-adds-mesh-texture-extrude-feature-for-advanced-surface-detailing) |
| Sep 2025 | Thicken Type Sharp / Rounded ("New Rounded Thicken") | A (B-SEP25) |
| Jan 2026 | Patch: Reverse Normal check box + Flip; feature patterns default to Identical | A (B-JAN26, RN-2026) |
| Mar/Apr 2026 | Sketch Isoparametric Curve (surface U/V curves) | A (B-MAR26, API) |
| Jul 2026 | construction-geometry upgrades; Extend fix (only picked edges); lost isoparametric projections relinkable | A (B-JUL26, RN-2026) |
| Sep 2026 | Loft: deterministic mapping of closed profiles with matching corners; Environmental Map Analysis; Inspect regrouped; Offset API enum | A (B-SEP26, RN-2026, API) |

---

## 6. Gap list against SciForge today (from `ribbon_config.py`, `parity/surface.md`, a grep of `surface*.py`) (G)

Menu items Fusion has on SURFACE that SciForge's SURFACE tab lacks:
- CREATE: New Component, Derive, Pattern ▸ (3), Mirror (SciForge has these on SOLID only; they must
  accept surface bodies, Mirror Join must stitch with a Stitch Tolerance), Create Form (skip: no Form).
- MODIFY: Press Pull, Fillet, Chamfer (must work on edges of surface bodies: `fillet_*.py` has no
  surface handling), Split Body (open bodies too), Silhouette Split, Scale, Combine, Move/Copy, Align,
  Merge (direct only: optional), materials/appearance/parameters tail.
- Panels: ASSEMBLE (and CONFIGURE if SOLID has it).
- INSPECT: Environmental Map Analysis.

Dialog options missing in the SciForge surface tools (no trace found by a grep of `surface_ui.py` / `surface_core.py`; G):
- Offset: **Offset Type Sharp / Rounded** (SciForge rounds convex corners always; parity doc lists it as unconfirmed - it is now confirmed, default Sharp).
- Patch: **Reverse Normal + Flip**; Group Edges off and Tangency Weight are greyed (known gap).
- Untrim: **Manual** type, **Keep Copy**.
- Revolve: **Project Axis** check box; the extent label **Partial** (SciForge says Angle).
- Extrude: **Match Shape** (To Object); Chain Faces vs Extend Faces choice.
- Sweep: **Path + Guide Surface** type; Path + Guide Rail **Extent Full Extents / Perpendicular to Path** and the two distances (known gap).
- Loft: **Edge Alignment Free Edges / Align Edges / Align to Surface**; closed-profile corner mapping (Sept 2026); Tangent Edges default unknown.
- Extend: Align Edges (greyed, known gap).
- Stitch: Operation (when the result is solid).
- Delete on the SURFACE tab: delete faces without healing (check `delete.py`).
- Sketch: Isoparametric Curve under Project/Include.
