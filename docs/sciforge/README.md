# SciForge: start here

SciForge is a fork (a copy we are allowed to change) of FreeCAD 1.1.4, being reshaped until it
works like Autodesk Fusion. The plan is in [feature-outline.md](feature-outline.md); progress
is tracked in [MEMORY.md](../../MEMORY.md).

## Getting a SciForge build to test (Windows)

You never need to compile anything yourself. GitHub builds it:

1. On GitHub, open the repository, click **Actions**, then **SciForge build** in the left list.
2. Click **Run workflow**, pick `windows` (or `both`), and press the green button.
3. Wait. A full build takes a few hours (the C++ part of FreeCAD is large). Quick checks run
   first (about 10 minutes, including the test models on FreeCAD for Windows); when one fails,
   the run stops there instead of compiling for hours.
4. When the run is finished, open it and scroll to **Artifacts**. Download
   `SciForge-Windows-portable-...`. GitHub wraps it in a .zip; inside is a `.7z` file.
   The build is uploaded before its tests run, so it is there even when a test failed (the
   run then has a red cross): install the newest quick update on top, which has the fix.
5. Unpack the `.7z` (7-Zip) anywhere, for example `C:\SciForge`. Run `bin\FreeCAD.exe`.
   (The program is still called FreeCAD inside until the branding pass is done.)
6. Pick **SciForge** in the workbench drop-down at the top.

The portable build does not install anything and does not touch an installed FreeCAD.
Until the branding pass, it does share FreeCAD 1.1's settings folder.

About cost: the repository is public (since 2026-10-10), and GitHub's standard build machines are
free for public repositories, so builds cost nothing. A full build still takes a few hours, so it
is started by hand (or by a `sciforge-v*` tag) rather than on every change. The automatic test
run (**SciForge tests**) takes about 40 minutes (6 machines side by side, one of them Windows) and
runs on every push.

## Getting updates without rebuilding (most of the time)

See [quick-update.md](quick-update.md): download `SciForge-quick-update-...` from the newest green
**SciForge tests** run and install it with `install_update.ps1` (about a minute). A full build is
only needed when FreeCAD's C++ core changes; MEMORY.md says when.

## What to send back after testing

1. **View > Panels > Report view**: copy everything, especially lines starting with `[SciForge]`.
2. **SciForge > Diagnostics**: copy the text.
3. A screenshot if something looks wrong.

## What the automatic tests check

Every push runs **SciForge tests** (Actions tab). It uses the official FreeCAD 1.1.4 plus the
SciForge module and checks:

- **Unit tests**: the parts of SciForge that are plain logic (search ranking, timeline rules,
  golden-model format).
- **Golden models**: about 280 reference parts (bracket, enclosure, flange, holes, fillets, shells,
  patterns, Press Pull, Extrude on a face, and "edit an early step" cases). Each is rebuilt step
  by step and its volume, area, size and face count are compared with values worked out by hand.
  The report appears on the run's summary page.
- **GUI smoke test**: starts the real FreeCAD window on a virtual screen, switches to SciForge,
  checks toolbars, shortcuts and the timeline, and saves a screenshot (download
  `sciforge-test-output-base` from the run).
- **GUI journey test**: uses SciForge the way a person does, with real mouse clicks and drags:
  Create Sketch by clicking a plane, Extrude by clicking inside the profile and dragging the
  arrow, Press Pull by clicking a face, a second sketch on a face, a cut, a face extrude.
  Screenshots `journey-*.png` are in `sciforge-test-output-base`.
- **GUI scenarios**: about 130 complete workflows (one per feature, plus the "try to break
  it" rounds), each with real clicks, typing and keys, checking volumes worked out by hand
  and that no error or pop-up appears. They are split over 4 machines; the reports and
  screenshots are in `sciforge-test-output-scenarios-1` to `-4`.
- The quick update is only built when all five parts pass.

## Folder map

| Folder | What |
|---|---|
| `src/Mod/SciForge/` | SciForge's own module (workbench, timeline, search, tests) |
| `src/Mod/SciForge/SciForgeTests/golden/` | the golden models and how to write them |
| `docs/sciforge/` | the outline, this guide, the list of changes to FreeCAD's code |
| `tools/sciforge/` | scripts for running tests |
| `prototype/forge-freecad/` | the original "Forge" draft, kept for history |
| everything else | FreeCAD's source code |
