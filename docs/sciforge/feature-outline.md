# SciForge: Feature Outline (v2)

**Goal: SciForge must be Fusion. Not "Fusion-like". Not "Fusion-adjacent". Fusion-level functionality and feel, so the owner can build the same objects the same way he builds them in Autodesk Fusion today.**

Handoff document for the implementing model. Read sections 0-5 fully before writing any code.

---

## 0. NON-NEGOTIABLES (read first)

1. **The target is Fusion parity.** If the owner can make an object in Fusion with a given sequence of commands, he must be able to make the same object in SciForge with the same sequence of commands, with the same dialogs, options, defaults, previews and results. "Close enough" is a bug, not a milestone.
2. **Press/Pull is mandatory** and is a centerpiece (see 7.0). The single smart tool that offsets faces, moves faces, and edits fillets and chamfers by dragging or typing a value, with live preview, recorded in the timeline.
3. **A fork of FreeCAD is explicitly allowed and expected** wherever an add-on cannot reach Fusion parity. Do not stop at "the add-on API doesn't allow it." Go into the C++ core.
4. **This is a long-term moonshot, not a quick win.** Do not trade parity for speed of delivery. Order the work by dependency and risk, and do the hard parts first rather than last.
5. **Out of scope** (do not build): sculpting / T-spline, simulation and FEA, generative design, rendering and animation, CAM, electronics, cloud collaboration. See section 8.
6. **Everything stays local and open.** No telemetry, no accounts, no cloud dependency. Project files live on the owner's NAS.
7. **Copy behavior, never assets.** No Autodesk icons, artwork, wording, code, or binaries. Black-box observation of how Fusion behaves is the method; reverse engineering Fusion's software is forbidden (see 2.5).
8. **Honesty over optimism.** If something cannot reach parity with the OpenCASCADE kernel, say so with evidence (a failing benchmark), and propose the real fix (kernel work, a different algorithm), not a workaround that quietly lowers the bar.

---

## 1. Mission

Build **SciForge**: a Fusion-class parametric CAD application, built by forking FreeCAD and reworking its interface, document model, sketcher, feature engine and selection/navigation until the Fusion workflow is reproduced end to end.

What changed from v1 of this outline: v1 treated FreeCAD as a fixed engine with a skin on top and set an 80% ceiling. That is retired. v2 treats the entire FreeCAD codebase as raw material that SciForge may change.

## 2. What "Fusion-level" means (how we will know)

### 2.1 Parity levels

- **A, Exact:** Same workflow, same options, same defaults, same keystrokes, same visual feedback. Required for everything marked P0.
- **B, Equivalent:** Same capability and result, UI may differ in layout details. Acceptable for P1.
- **C, Acceptable:** Capability exists and is usable. Allowed only for P2.

### 2.2 Per-feature acceptance template (applies to every feature)

A feature is done only when all of these hold:
- Same option set as Fusion's dialog (every checkbox, dropdown, and mode).
- Same selection behavior (what can be picked, hover highlight, what auto-selects).
- Live preview while editing values, updating as fast as Fusion does on a typical part.
- Appears in the timeline, is editable afterwards, and survives edits to earlier steps wherever Fusion's does.
- Undo/redo works.
- Fails with a clear message that says why and what to try, never a silent no-op or a crash.
- Has a golden-model test (2.3).

### 2.3 Parity benchmark suite ("golden models")

Create and maintain a suite of at least 30 reference parts, grown to 100+, defined as **step lists** (e.g. "sketch on XY, rectangle 40x20, extrude 10, fillet top edges 2 mm, shell 1.5 mm removing top face..."). Include: bracket, enclosure with lid lip and screw bosses, gear, bottle (loft + shell), threaded fastener, hinge, snap-fit clip, pipe fitting (sweep), heat sink (patterns), a part edited at step 2 after 20 more steps (reference stability test), and Press/Pull cases on every face type. Each golden model records: steps, expected dimensions/volume/area, and pass/fail across SciForge versions. CI runs them headless.

If the owner still has access to Fusion's scripting or the previously used Fusion MCP integration, use it to generate reference geometry and metrics (volume, area, bounding box, face counts) for each golden model, and compare against SciForge's output. Ask the owner first.

### 2.4 Parity capture process

Before each feature area is built: the owner records short screen captures and screenshots of the Fusion workflow (every dialog state, every option, hover/preview behavior), plus a list of the keystrokes and mouse actions he uses. The implementer writes a **behavior spec** from those (not from memory) and gets sign-off before coding. This is the source of truth for "what Fusion does."

### 2.5 Legal boundaries

- Fusion is a commercial product. Do not decompile, disassemble, or otherwise reverse engineer it. Do not copy its icons, artwork, strings, file formats beyond what is needed to import the owner's own files through documented/open formats (STEP, STL, 3MF, DXF, SVG).
- Generic CAD terms (Extrude, Fillet, Loft) are fine. Autodesk-specific branding is not. Use original icons and original wording for anything that is not a standard CAD term.
- FreeCAD is LGPL-2.1-or-later. The fork keeps that license, publishes source for distributed binaries, and keeps copyright notices. Choose the fork name and branding to avoid implying it is FreeCAD itself (the name is SciForge).

## 3. Strategy: the SciForge fork

### 3.1 Principles

1. **New code goes in new modules.** SciForge's own workbench/module lives in its own folder under the source tree. Touch FreeCAD's core only where required, with small, documented patches. This keeps merging upstream releases survivable.
2. **Track upstream.** Merge each FreeCAD stable release (and selected fixes from master) on a schedule. Every core patch carries a comment tag `SCIFORGE:` and an entry in `docs/core-patches.md` explaining why it exists and whether it could be upstreamed.
3. **Upstream what is generic.** Bug fixes, kernel robustness work, and API additions that help everyone are contributed back. It lowers merge cost and builds the owner's reputation.
4. **Parity-driven development.** Each work item is traced to a golden model or behavior spec. No feature is built "because it is cool."
5. **Hardest risks first.** Press/Pull engine, fillet robustness and reference stability are scheduled early because they determine whether the project can reach its goal at all.

### 3.2 Build and delivery infrastructure (Phase 0, mandatory)

- Fork FreeCAD at the latest stable tag (1.1.x as of Oct 2026) into a repository named **SciForge**.
- Reproducible Windows build (use FreeCAD's documented dependency environment, verify the current official instructions for 1.1.x) and a Linux build. Document exact steps.
- **Continuous integration builds the binaries** (self-hosted runner on the owner's NAS, or a hosted CI during development). The owner must not be required to compile C++ locally for each iteration: CI produces an installer/portable zip he downloads and tests.
- Headless test runner for the golden models and unit tests.
- Branding pass: application name, icon set, installer, user-data folder name, so SciForge and FreeCAD can be installed side by side without conflicts.
- Crash reporting stays local (log files the owner can paste back).

## 4. Context about the owner and the working method

- Owner: Luca, 22, IT/cybersecurity background, 3D printing and robotics experience, **a beginner at software engineering** who is directing the project. He tests, he does not write code. Explain what you build in plain language and avoid unexplained jargon.
- Primary platform: **Windows 10/11**. Second: **Linux**. macOS is out of scope.
- Method: the model writes code in a sandbox that cannot run SciForge's GUI. The owner downloads CI builds, tests, and pastes back logs and screenshots. Therefore: small increments, rich diagnostics, automated tests for everything that can be tested headlessly, and manual test scripts the owner can follow in minutes.
- Pace: months to years. Plan in milestones with exit criteria (section 10), not dates.
- Daily user: the owner designs printable parts, mechanisms and robotics hardware. Prioritize the workflows he uses.

## 5. Architecture principles

1. **Never crash on bad input.** Every command handler, timer and event callback catches, logs with a `[SciForge]` prefix, and leaves the document valid.
2. **Pure-logic cores** (no GUI, no document) for anything testable in isolation; unit tested.
3. **Data-driven UI layout.** Toolbars, tabs, menus and shortcuts are defined in data files, not scattered through code.
4. **Cross-platform from day one.** No platform-specific code without a guard.
5. **Performance budget.** Live previews and the timeline must stay responsive on models with several hundred features; profile before optimizing, but treat lag as a parity bug.
6. **Standard, open file formats.** Native files stay plain and portable. A one-click "export everything to open formats" command exists from the first usable build.
7. **Qt via PySide6 for Python UI; C++/Qt for performance-critical or core UI.** Keep the Python/C++ split deliberate and documented.

Implementation levels used below: **[L1]** script, **[L2]** Python/Qt module, **[L3]** C++ core or new C++ module, **[K]** geometry-kernel-level (OpenCASCADE usage or new geometry algorithms), **[UP]** worth contributing upstream.

Priorities: **P0** parity-critical for everyday modeling, **P1** needed to replace Fusion for the owner's real projects, **P2** completeness, **P3** only if time allows.

## 6. Current state

A first add-on draft exists (called "Forge" at the time, to be renamed SciForge): a workbench with Design/Sketch/View toolbars, a Fusion-style shortcut map, command search, and a timeline bar with rollback, 22 passing tests against fakes, **never run in real FreeCAD**. Treat it as a throwaway prototype of the interface layer. Under the fork it becomes the seed of the SciForge shell module or is replaced by a better C++ implementation.

---

## 7. Feature requirements (in scope)

Organized the way Fusion's Design workspace is organized. Parity level A unless stated.

### 7.0 SPOTLIGHT: Press/Pull [P0, L3/K, hardest item, start early]

One command that reproduces Fusion's Press Pull behavior:
- **Smart inference from selection.** Select faces: offset/move them. Select edges: fillet or chamfer them. Select a filleted/chamfered face: edit its radius/distance. Select faces on primitive shapes (cylinder, cone, sphere): change radius/size. The tool infers the operation; the user never picks "which operation."
- **Interactive manipulation.** Drag an arrow in the viewport or type a distance in the dialog, with **live preview** during drag, snapping and unit expressions allowed.
- **Offset-type options** matching Fusion's: offset face, with "tangent chain" selection, direction handling, and the ability to push a face inward to remove material or outward to add.
- **Multi-face edits** in one operation; adjacent faces extended or trimmed to stay a valid solid.
- **Works on parametric history and on imported/featureless bodies** (the latter via the direct editing layer, 7.13).
- **Timeline entry** appropriate to the operation, editable later; if history is not captured, applies directly.
- **Failure handling:** if the result would be invalid, show the preview in an error state and explain why (e.g. "offset would collapse a wall") instead of failing silently.
- Technical program: see 9.1. Needs a research spike on OpenCASCADE's offset, draft and local-operation algorithms, shape healing and face-extension/re-intersection; prior art in FreeCAD and other open-source CAD; and a plan for cases OCC cannot handle (custom algorithms).

*Acceptance:* a defined set of at least 40 Press/Pull scenarios (planar, cylindrical, conical, spherical, filleted, chamfered, multi-face, with and without history) pass, and the owner confirms by hand that it feels like Fusion's.

### 7.1 Shell and workspace [P0]
- Fusion-style layout: tabbed toolbar (Solid, Surface, Utilities; limited Mesh) with Create / Modify / Assemble / Construct / Inspect / Insert / Select groups, drop-down menus per group, browser on the left, timeline at the bottom, ViewCube top right, navigation bar at the bottom of the viewport.
- Contextual behavior: sketch tools appear only while sketching; contextual enabling by selection.
- Command search (S), editable shortcut map matching Fusion's defaults, repeat last command, right-click marking menu.
- Original icon set and dark theme with matching density.

### 7.2 Browser panel [P0]
Document settings, named views, origin, components, bodies, sketches, construction geometry; visibility toggles, rename, drag-organize, activate component, isolate, right-click context actions. Not FreeCAD's native tree.

### 7.3 Timeline and history [P0]
- Timeline with per-feature icons, hover highlight of the feature's geometry, double-click edit, draggable **rollback marker**, edits made while rolled back insert at the marker.
- Drag-to-reorder where dependencies allow, with clear rejection messages otherwise.
- Suppress/unsuppress, rename, delete with dependency warning, feature groups.
- Error states with message on hover and a one-click jump to the failing reference.
- **Design history capture on/off** (parametric mode vs direct mode), switchable per design like Fusion.
- Robust to edits: see 9.3.

### 7.4 Parameters [P0]
User and model parameters table (name, unit, expression, value, comment, favorites), usable in every numeric field, unit-aware expressions, rename propagation, warnings on deleting a used parameter.

### 7.5 Sketching [P0, L3, fork the Sketcher]
- Full Fusion geometry set: line, rectangles (2-point, 3-point, center), circles (center, 2-point, 3-point, tangent), arcs (3-point, tangent, center), polygon, ellipse, slot variants, spline (fit point and control vertex with handles), conic, point, text.
- **Smart Dimension tool (D)** with the same inference and in-place editing; all dimension types.
- **Auto-constraining and inference** while drawing (snap markers, glyphs, tangent/perpendicular/coincident inferred), constraint glyphs, hover and delete.
- Under/fully-constrained visual feedback and DOF count like Fusion's color states.
- Drag-to-solve behavior that feels the same (solver stability, no jumping geometry).
- Modify tools: trim, extend, break, fillet, chamfer, offset, mirror, rectangular/circular patterns, move/copy, scale, rotate.
- Project, Include 3D geometry, Intersect; construction toggle (X); Sketch Palette options; Slice; import DXF/SVG; profile/region detection with nested loops; sketch entry via plane/face picker with automatic look-at.
- Solver work: evaluate the existing constraint solver (planegcs) for the behaviors above; extend or replace where it falls short (see 9.4).

### 7.6 Create (solid features) [P0 unless noted, all with live preview]
- **Extrude:** all start types (profile plane, offset, from object) and extent types (distance, to object, through all, two sides, symmetric), taper, thin extrude, join / cut / intersect / new body / new component, multi-profile selection, direction flip.
- **Revolve:** axis from line/edge/axis, full/angle/to object, symmetric, all operation types.
- **Sweep** [P0]: path, guide rail, profile orientation modes (perpendicular/parallel), taper, twist, distance along path.
- **Loft** [P0]: profiles and rails, centerline, per-profile tangency/curvature continuity, closed loft.
- **Rib, Web, Emboss** [P1]
- **Hole** [P0]: simple, counterbore, countersink; tapped; placement by sketch points and references; standard size tables; drill point options.
- **Thread** [P1]: modeled and cosmetic, standard tables.
- **Primitives** [P1]: box, cylinder, sphere, torus, coil, pipe.
- **Patterns** [P0]: rectangular, circular, path; features/bodies/components; pattern spacing and suppression; **Mirror**.
- **Pipe, Thicken** [P1]

### 7.7 Modify [P0 unless noted]
- **Press/Pull**: see 7.0.
- **Fillet:** constant, variable radius, chord length, rule-based, setbacks, corner types, tangent chain, G1/G2 continuity, **robust** (see 9.2).
- **Chamfer:** equal, two distances, distance and angle, corner options.
- **Shell:** inside/outside/both, remove faces, per-face thickness override.
- **Draft:** fixed plane, parting line, angle; **Scale** (uniform/non-uniform); **Combine** (join/cut/intersect, keep tools).
- **Replace Face, Split Face, Split Body, Silhouette Split** [P1]
- **Move/Copy** with manipulator gizmo (free move, translate, rotate, point to point), **Align**, **Delete**, **Offset Face**, **Physical Material / Appearance** assignment [P1].

### 7.8 Construct [P1]
Offset plane, plane at angle, tangent plane, midplane, plane through three points / two edges / along path; axes (through two points, edge, cylinder, perpendicular to face at point); points (vertex, center, intersection, along path).

### 7.9 Surface (basics only) [P1]
Patch, stitch, unstitch, trim, extend, offset surface, ruled surface, boundary fill, thicken, delete face. Enough to make and repair the kinds of surfaces needed for typical product shapes. No sculpt.

### 7.10 Assemble [P1]
- Components, new component from bodies, activate component, external references to other design files (local files).
- Joints: rigid, revolute, slider, cylindrical, pin-slot, planar, ball; joint origins with the same picker behavior; as-built joints; joint limits; rigid group; ground; contact sets (basic). Basic joint-driven motion preview is in scope; **no simulation**.
- Decide early whether to base this on FreeCAD's Assembly workbench or write a new assembly layer (spike in Phase 2).

### 7.11 Inspect [P1]
Measure (distance, angle, area, volume, units), interference check, section analysis, curvature comb, zebra analysis, draft analysis, center of mass, component color cycling.

### 7.12 Insert, import, export, make [P0/P1]
- Import/export: STEP, STL, 3MF, OBJ, DXF, SVG; mesh insert and mesh-to-solid helper; insert canvas (reference image); decal [P2].
- **3D print flow:** export to 3MF/STL with quality options and open the folder.
- One command exports the whole design to open formats with previews (ownership guarantee).

### 7.13 Direct modeling mode [P1, K]
Fusion lets a design run without history (capture off) and edit imported bodies directly. SciForge needs the same: faces move/offset/delete/replace, Press/Pull on featureless geometry, with the same behavior. Shares the engine with 7.0.

### 7.14 Selection, navigation and viewport [P0, L3]
- **Navigation matching Fusion:** orbit, pan, zoom to cursor, zoom window, fit, look-at, orbit-around-selection, with Fusion's default mouse mapping and an optional touchpad profile. Navigation bar with orbit/pan/zoom/fit/display settings/grid and snaps.
- **ViewCube** with identical interaction (click faces/edges/corners, drag-orbit, home).
- **Selection:** hover highlight and preview identical in character, window vs crossing select, selection filters, tangent-chain selection, select-through, "select other" for overlapping geometry, paint select.
- Visual styles (shaded, shaded with edges, wireframe, hidden-line), per-body visibility, section view, environment/ground basics, appearance and materials.
- Investigate whether the viewport (Coin3D) can reach acceptable rendering/selection quality and speed; if not, scope a replacement as a separate program (9.5).

### 7.15 Files, versions and data (replaces Fusion's cloud) [P1]
Local project browser with thumbnails, named versions via git (works with the owner's Forgejo later), autosave and crash recovery, linked designs by relative path, export-all command.

### 7.16 Drawings [P2]
One command to make a drawing from a body (standard views, dimensions, title block, original templates), built on the existing TechDraw code where practical.

### 7.17 Quality and packaging [P0]
Installer, portable zip, side-by-side install with FreeCAD, Linux package, docs (cheat sheet, "Fusion to SciForge" mapping), update mechanism, compatibility notes.

---

## 8. Explicitly out of scope

Sculpt (T-spline), simulation and FEA, generative design, rendering and animation, CAM and manufacturing toolpaths, PCB/electronics, cloud collaboration, accounts, cloud storage, team data management, mobile apps. Do not spend time on them and do not design the architecture around them.

## 9. Hard technical programs

These determine whether Fusion parity is reachable. Schedule early, track with benchmarks, and report honestly.

### 9.1 Press/Pull and face-editing engine [K]
Goal: reliable offset/move/delete/replace of faces on solids, with and without history. Tasks: spike on OpenCASCADE offset and local operations, face extension and re-intersection, shape healing; build a regression set of face-edit cases (40+ at start); design a feature type that stores the edit parametrically; plan for fallback algorithms when OCC fails.

### 9.2 Fillet and chamfer robustness [K]
OpenCASCADE blends are a known weak point versus commercial kernels. Build a benchmark of 100+ real fillet cases from typical part workflows (variable radius, corners where three or more fillets meet, fillets across tangent chains, fillets near thin walls, setbacks). Measure success rate. Improve through shape healing before/after, automatic retry strategies (radius reduction, face extension), alternative algorithms, and contributions to OpenCASCADE or FreeCAD where possible. Report success rate every milestone.

### 9.3 Reference stability (the "model survives edits" problem) [L3, UP]
FreeCAD's topological naming problem was substantially improved in 1.0, but real parity requires that feature references survive edits earlier in the timeline in the situations Fusion handles. Build edit-stability tests (change an early dimension on 20-80 feature models; reorder; suppress), measure breakage, and extend the core's element-mapping where gaps remain.

### 9.4 Sketch solver and interaction feel [L3]
Test the existing solver against Fusion-like drags, auto-constraints and redundancy handling; fix instabilities; add inference and glyph interaction in the sketch editor. Fork the Sketcher module as needed.

### 9.5 Viewport and selection engine [L3]
Measure picking accuracy, highlight quality, large-model performance and navigation feel. If limits are inherent to the renderer, scope an upgrade or replacement as its own program.

### 9.6 Timeline/history data model [L3]
Define how history capture on/off, rollback marker insertion, suppression, grouping, reordering and component structure map onto FreeCAD's document model; decide what is a new object type and what is reuse.

---

## 10. Phases and milestones (exit criteria, no dates)

**Phase 0: Foundations.** Fork, branding, reproducible Windows/Linux builds, CI producing downloadable builds, golden-model harness, parity-capture of the owner's Fusion workflow, behavior specs for Phase 1 features, spikes for 9.1 and 9.2 with initial benchmarks. *Exit:* an installable SciForge build exists and runs the benchmark harness; Press/Pull and fillet feasibility reports are written.

**Phase 1: The modeling core.** Shell, browser, timeline, parameters, sketcher parity (7.5), Extrude/Revolve/Hole/Pattern, Fillet/Chamfer/Shell/Combine, Move/Copy, navigation and selection parity. *Exit:* the owner models a bracket and an enclosure from scratch using only Fusion's workflow and keystrokes.

**Phase 2: Press/Pull and direct editing.** 7.0 and 7.13 to parity, fillet robustness to the agreed success rate, sweep/loft, reference-stability work. *Exit:* all 40 Press/Pull scenarios pass; the "edit an early step" tests pass.

**Phase 3: Breadth.** Remaining Create/Modify/Construct, surface basics, Inspect, Insert/Export, assemblies and joints, files and versioning, drawings basics. *Exit:* the owner completes a real multi-part project (e.g., a robotics mechanism) end to end in SciForge and does not need to open Fusion.

**Phase 4: Polish and daily-driver quality.** Performance, stability, installer, docs, Linux release, second round of parity review against fresh captures.

**Phase 5: Optional.** Anything in P3, upstream contributions, further drawings and assembly depth.

## 11. Risks

- **Kernel gap.** OpenCASCADE is not Autodesk's kernel. The risk is concentrated in 9.1 and 9.2; they are scheduled first so failure shows up early. If parity cannot be reached, the honest options are kernel-level work, a hybrid approach, or documented exceptions the owner explicitly approves. They are not silent downgrades.
- **Fork maintenance load.** Keep core patches small and tagged; merge upstream on a schedule.
- **Build and CI complexity.** C++ builds are slow and fragile on Windows; invest in reproducible CI in Phase 0.
- **Single tester.** The owner is the only GUI tester. Counter with golden models, headless tests and rich diagnostics.
- **Legal.** Fusion's EULA forbids reverse engineering; stay black-box. Original assets only.
- **Scope creep.** Video editing, image editing and other apps the owner wants are separate projects, not part of SciForge.

## 12. Open questions for the owner (answer before Phase 1)

1. Can he record screen captures of his everyday Fusion workflows (Section 2.4), and does he still have scripting/MCP access to Fusion for generating reference models (2.3)?
2. Which 5-10 real objects has he made in Fusion that should become the first golden models?
3. Windows build machine: does he have a PC suitable for compiling (RAM, disk), or should CI do everything?
4. Where will CI run (the future NAS with Forgejo, or a hosted service during development)?
5. License and publication plan for SciForge (default: LGPL-2.1-or-later, source published).
6. Does he want SciForge to open Fusion's `.f3d` files? (Probably not possible legally or technically; STEP import is the supported route.)
