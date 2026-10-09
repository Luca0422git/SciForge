# SciForge memory and progress log

This file is the project's memory across work sessions. **Read it first, every session**, then
`docs/sciforge/feature-outline.md` (the spec). Update it at the end of every session: what was
done, what was learned, what is next. Newest session goes at the top of the log.

---

## Where things live

| What | Where |
|---|---|
| The spec (source of truth for scope) | `docs/sciforge/feature-outline.md` |
| This memory / progress log | `MEMORY.md` |
| SciForge's own module (workbench, timeline, search, ...) | `src/Mod/SciForge/` |
| Golden-model benchmark suite (step lists + runner) | `src/Mod/SciForge/SciForgeTests/golden/` |
| Every change to FreeCAD's own code (tagged `SCIFORGE:`) | `docs/sciforge/core-patches.md` |
| CI workflows (SciForge's own) | `.github/workflows/sciforge-*.yml` |
| Tooling scripts for CI / local runs | `tools/sciforge/` |
| Original "Forge" v0.1 prototype, kept verbatim for history | `prototype/forge-freecad/` |
| Upstream FreeCAD source | everything else (the fork base is tag `1.1.4`) |

## Fixed facts

- **Fork base:** FreeCAD tag `1.1.4` (commit `4fd3bf320d`), full upstream history kept so future
  FreeCAD releases can be merged (`git remote add upstream https://github.com/FreeCAD/FreeCAD.git`,
  then `git fetch upstream refs/tags/1.1.X:refs/tags/1.1.X` and merge the tag).
- **Repo:** `github.com/Luca0422git/SciForge`, **private**. Private repos get a limited monthly
  budget of GitHub Actions minutes (Windows minutes count double), so full C++ builds run only
  when started by hand (Actions tab → "SciForge build" → Run workflow). Cheap tests run on
  every push.
- **History is 2.4 GB**: GitHub rejects a single push over 2 GB, so the initial import was
  pushed in 5 fast-forward stages. Normal pushes are small and unaffected.
- **License:** LGPL-2.1-or-later (inherited from FreeCAD). Keep FreeCAD copyright notices.
- **Owner:** Luca, a beginner at software engineering who tests, not codes. Explain plainly. Primary
  platform Windows 10/11, then Linux. No macOS.
- **Sandbox can run real FreeCAD**: the official FreeCAD 1.1.4 Linux AppImage downloads and runs
  headless (`freecadcmd`) *and* with a GUI on a virtual screen (`xvfb-run`). Use
  `tools/sciforge/get_freecad.sh` to fetch it. The 3D view renders blank under xvfb (no GPU),
  but widgets, toolbars, commands and geometry all work, and screenshots of the window work.

## Decisions log

| Date | Decision | Why |
|---|---|---|
| 2026-10-09 | Fork at 1.1.4 with full history (not a flat copy) | Makes merging future FreeCAD releases a normal `git merge` |
| 2026-10-09 | Removed FreeCAD-org automation workflows (translations, stale bot, backport, labeler, CodeQL, scorecards, Fedora nightly, weekly release, dependabot); `CI_master.yml` made manual-only | They serve FreeCAD's organization, fail or waste minutes here; a weekly release cron would have run on our default branch |
| 2026-10-09 | SciForge module lives at `src/Mod/SciForge` and is installed by the normal CMake build | Ships inside every SciForge build; no separate add-on install step |
| 2026-10-09 | Golden models are JSON step lists run by a small interpreter in real FreeCAD | Same file runs in CI (headless) and can later be compared with Fusion reference metrics |
| 2026-10-09 | No SHEET METAL, PLASTIC or MANAGE tabs (Luca: "not for now") | Not used; out of scope |
| 2026-10-09 | Until the branding pass lands, CI's Windows build ships the portable 7z only, no installer | The FreeCAD NSIS installer would install over / clash with a real FreeCAD install |

## Status by phase (outline section 10)

### Phase 0: Foundations (in progress)

- [x] Fork FreeCAD 1.1.4 into the SciForge repo (full history)
- [x] Commit outline + Forge prototype
- [x] Disable upstream automation that does not apply
- [x] First real run of the prototype in FreeCAD 1.1.4 (GUI, under xvfb): found and fixed 2 bugs
- [x] SciForge module seeded from the prototype at `src/Mod/SciForge` (renamed, `[SciForge]` logs),
      built by CMake (`BUILD_SCIFORGE`, core patch #3)
- [x] Golden-model harness + 32 models with hand-derived expectations (31 pass on stock 1.1.4,
      1 = upstream bug fixed by core patch #4)
- [x] GUI smoke test in real FreeCAD under xvfb (14 checks, screenshot)
- [x] `tools/sciforge/run_tests.sh` runs all of it with one command
- [x] CI `sciforge-tests.yml`: unit + golden + GUI smoke on every push (against stock FreeCAD)
- [x] First `sciforge-tests.yml` run on GitHub is green (2026-10-09)
- [x] CI `sciforge-build.yml` written (manual): Windows portable 7z + Linux AppImage, then
      golden models run on the built SciForge
- [ ] First `sciforge-build.yml` run succeeds (never run yet: expect fixes; it is hours long)
- [ ] First CI build downloaded and launched by Luca on Windows
- [ ] Branding pass: app name, icons, user-data folder, installer (side by side with FreeCAD)
- [ ] Parity capture: Luca records Fusion workflows; behavior specs written + signed off
- [ ] Spike 9.1: Press/Pull feasibility report (OCC offset / local ops), with benchmark
- [ ] Spike 9.2: Fillet robustness benchmark + feasibility report
- [ ] Answers to the open questions in outline section 12

### Phase 1: The modeling core (started)

- [x] Interface shell, first pass (7.1): Fusion-style ribbon (tabs, groups, menus in Fusion's order,
      unavailable items greyed), dark theme with measured colours, 131 original icons in Fusion's
      visual style, quick-access bar, navigation bar, Fusion-style timeline with playback,
      contextual SKETCH tab, Fusion shortcut keys with clash handling, Revit mouse style (=Fusion).
      Spec + known gaps: `docs/sciforge/parity/ui-shell.md`. Not yet signed off by Luca.
- [x] Press/Pull v1 (7.0): faces push/pull (planar + cylindrical exact), edges -> fillet, fillet face ->
      radius; parametric feature in the timeline; dialog + drag arrow + live preview; 13 golden
      models (2 documented gaps: sloped neighbours, shared corners -> need C++ per-face offset, 9.1)
- [x] Fusion-style Extrude (E): join/cut/new body, one side/two sides/symmetric, distance/all,
      taper, drag arrow, auto-switch to Cut when dragged into material
- [x] Right-click marking menu (8 slots + list, Repeat last command). **Slot order unconfirmed.**
- [x] Browser panel with Fusion's structure (7.2), eye toggles, rename, activate
- [x] Change Parameters (7.4): user params (App::VarSet "Parameters"), model params, bare names
- [x] Construct presets (19 Fusion entries -> attacher modes; Offset Plane/Midplane computed)
- [x] Timeline marker drag + playback; ViewCube colours; 3D Print (3MF/STL) export
- [ ] Unified Revolve / Hole / Fillet dialogs Fusion-style (FreeCAD's dialogs used meanwhile)
- [ ] ViewCube shape, doc tabs in the app bar, floating command dialogs, Sketch Palette
- [ ] Timeline: reorder by drag, suppress, groups (7.3)
- [ ] Sketcher parity (7.5): inference, glyphs, Fusion dimension tool feel (needs captures)

## Known issues / findings

- Prototype bug (fixed in `src/Mod/SciForge`): `package.xml` lacked `<subdirectory>./</subdirectory>`,
  so FreeCAD 1.1 looked for `Forge/InitGui.py` and silently skipped the add-on. It would never have
  appeared on Luca's machine.
- Prototype bug (fixed): `Sketcher_External` no longer exists in 1.1. It is now
  `Sketcher_Projection` + `Sketcher_Intersection` (matches Fusion's Project / Intersect split).
- **Upstream bug (core patch #4):** `LinearPattern.Spacings2` defaults to `[0.0]`, so 2-direction
  linear patterns in Spacing mode stack row 2 on row 1. Fixed in C++ but **not yet compiled**:
  the first `sciforge-build.yml` run verifies it (golden `plate_hole_grid` must PASS there).
  Worth reporting upstream.
- FreeCAD API: `body.newObject()` does not move `Body.Tip` for pattern/mirror features (the GUI
  commands do it separately). The golden builder sets Tip explicitly. Anything SciForge builds
  from Python must do the same.
- Parity item: FreeCAD leaves split seam faces unless `Refine = True`; Fusion never shows them.
  SciForge features should default to refined. Golden models assume refined face counts.
- Sketch on XZ extrudes toward -Y in FreeCAD. Fusion's plane orientation differs (Y-up vs Z-up
  setting): needs a parity decision during the sketch behavior spec.
- OCC results matched the hand formulas for corner fillets (two fillets meeting a sharp edge),
  vertex blends (all-edge rounded box), chamfer corners, countersinks and shells: a good sign
  for 9.2, but these are easy cases. The real fillet benchmark (100+ hard cases) is still to do.
- **Editing a sketch switches FreeCAD to the Sketcher workbench** (and back after). So the
  SciForge interface is a "shell" (`shell.py`) that follows workbench changes instead of living in
  the workbench's Activated/Deactivated.
- **Trap:** FreeCAD's `ToolBarManager::saveState()` saves every toolbar's visibility on workbench
  switches. Hiding toolbars naively would hide them in plain FreeCAD forever. SciForge hides the
  toolbar's toggle action first (saveState skips those). Menu-bar visibility is not persisted.
- FreeCAD's Sketcher binds single letters (L, S, E, P, I, C, H, V, T...) to constraints. Fusion's
  keys win while SciForge is on; clashing FreeCAD keys are parked and restored (`shortcuts.py`).
- FreeCAD's "Revit" navigation style is exactly Fusion's default mouse mapping.
- The 3D view does render under xvfb in the GUI smoke test (screenshots show the part), the
  earlier blank view was just timing.
- **Quick updates**: SciForge is pure Python, so the CI artifact `SciForge-quick-update-<sha>`
  (made on every green `SciForge tests` run) + `install_update.ps1` replaces Mod\SciForge in
  Luca's portable build. Full builds only for C++ changes (core patches). Tell Luca when one is due.
- Installer lessons (Luca's Windows): a plain `.ps1` double-click closes at once, so start it via
  `install_update.cmd` (Bypass + pause). Renaming `Mod\SciForge` failed with "Access to the path
  is denied" (an open Explorer window/antivirus/OneDrive blocks folder renames), so the installer
  now copies files over the old ones, removes leftovers, backs up to `<SciForge>\SciForge-backups`
  (never inside `Mod`: FreeCAD loads every folder there) and self-elevates if the folder is not
  writable. Tested with pwsh as an unprivileged user (locked file, read-only folder).
- FreeCAD only honours a command's shortcut if the command is in a visible menu/toolbar. SciForge
  binds keys with QShortcut on the main window instead (`shortcuts.py`); GUI test presses real keys.
- FreeCAD saves dock visibility and toolbar state on exit: SciForge turns itself off on the main
  window's Close event (and back on if the close is cancelled). The browser lives *inside* the
  "Model" dock (its widget swapped), never hiding the dock.
- Preferences: SciForge records whether each preference existed and removes it again on exit
  (writing back GetBool's False default would have turned off FreeCAD's gradient for good).
- PartDesign::FeaturePython works as a timeline feature (Press Pull); its proxy class path is
  stored in files: keep `sciforge.presspull.PressPullFeature` stable.
- OCC's generic offset ("fill") gives BSpline end caps that do not merge with planar neighbours;
  build exact slabs for planes (prism) and cylinders (revolved ring).
- Sketch constraint expressions: path `.Constraints[i]` works; names with dots (base.width) do not.
- Attacher: AxisOfCurvature/CenterOfCurvature need a circular *edge*; SciForge maps a round face
  to its edge (Fusion lets you click the face).
- Fusion semantics still unknown (need parity capture before adding golden models): taper
  angle sign, chamfer two-distance side assignment, "intersect" and "new body" behavior.

## Questions waiting for Luca


(See outline section 12. Also:)
- OK to make the repo public at some point? Public repos get unlimited free Actions minutes,
  which matters a lot for C++ builds. Otherwise a self-hosted runner on the NAS is the route.

## Session log

### 2026-10-09: Session 1
- Forked FreeCAD 1.1.4 (latest stable) into the repo with full history, pushed in stages.
- Added outline and prototype verbatim; removed FreeCAD-org automation workflows.
- Got real FreeCAD 1.1.4 running in the sandbox (headless + GUI via xvfb).
- Ran the prototype for the first time in real FreeCAD; fixed 2 bugs (see Known issues).
- Created `src/Mod/SciForge` from the prototype (renamed), wired into CMake.
- Built the golden-model harness (schema, selectors, builder, runner) and 32 models;
  found and patched an upstream FreeCAD bug with it.
- Added GUI smoke test, `tools/sciforge/*.sh`, CI workflows, docs (`docs/sciforge/`).

### 2026-10-09: Session 1, part 2 (UI shell)
- Luca sent 5 screenshots of stock Fusion. Built the Fusion-style shell from them: `ribbon_config.py`
  (data), `ribbon_ui.py`, `theme.py`, `shell.py`, `navbar_ui.py`, new `timeline_ui.py`, icon
  generator `tools/sciforge/make_icons.py` (131 icons). GUI smoke test now 29 checks incl. sketch
  mode and clean switch-off; unit tests 53 (ribbon data checked against a snapshot of FreeCAD
  1.1.4's command list).
- Luca was compiling the first Windows build during this; result still unknown.

### 2026-10-09: Session 1, part 3 (big features)
- Luca asked for the big Fusion features and no more 4-hour waits. Added the quick-update path,
  then Press/Pull, Extrude, marking menu, Browser, Change Parameters, Construct presets, marker
  drag, ViewCube colours, 3D Print. Tests: 77 unit, 43 golden (+3 xfail), 70 GUI checks.
- Quick-update installer fixes after Luca's reports (closed at once; then "access denied" when
  renaming the old folder). See Known issues. Waiting for Luca to confirm it installs.

## Next steps (in order)

1. Luca installs the quick update on his portable build and reports (screenshots, Report view).
   Ask for: right-click marking menu screenshot (slot order), Press Pull and Extrude feel.
   Earlier: confirm the C++ build ran golden `plate_hole_grid` as PASS (patch #4).
2. Luca launches the portable build on Windows and reports (Report view + Diagnostics).
3. Get answers to outline section 12 + parity captures of Luca's Fusion workflows (2.4).
4. Spike 9.1 (Press/Pull): research OCC `BRepOffsetAPI_MakeOffsetShape`, `LocOpe`,
   `BRepAlgoAPI_Defeaturing`, `BRepOffset_MakeSimpleOffset`, face replacement; write
   feasibility report + first 40 Press/Pull golden cases (needs new ops in the builder).
5. Spike 9.2 (Fillets): 100+ case benchmark from real part workflows, success-rate metric.
6. Branding pass (app name, icons, user-data folder, installer) so CI can ship an installer.
7. Grow golden models toward 100 (gear, bottle loft+shell, sweep pipe, snap-fit, hinge, threads)
   once the builder supports loft/sweep/thread.
