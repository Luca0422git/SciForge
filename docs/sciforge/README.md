# SciForge: start here

SciForge is a fork (a copy we are allowed to change) of FreeCAD 1.1.4, being reshaped until it
works like Autodesk Fusion. The plan is in [feature-outline.md](feature-outline.md); progress
is tracked in [MEMORY.md](../../MEMORY.md).

## Getting a SciForge build to test (Windows)

You never need to compile anything yourself. GitHub builds it:

1. On GitHub, open the repository, click **Actions**, then **SciForge build** in the left list.
2. Click **Run workflow**, pick `windows` (or `both`), and press the green button.
3. Wait. A full build takes a few hours (the C++ part of FreeCAD is large).
4. When the run has a green tick, open it and scroll to **Artifacts**. Download
   `SciForge-Windows-portable-...`. GitHub wraps it in a .zip; inside is a `.7z` file.
5. Unpack the `.7z` (7-Zip) anywhere, for example `C:\SciForge`. Run `bin\FreeCAD.exe`.
   (The program is still called FreeCAD inside until the branding pass is done.)
6. Pick **SciForge** in the workbench drop-down at the top.

The portable build does not install anything and does not touch an installed FreeCAD.
Until the branding pass, it does share FreeCAD 1.1's settings folder.

About cost: the repository is private, and GitHub gives private repositories a limited number of
free build minutes per month (Windows minutes count double). One full build uses a large share
of it, so builds are started by hand rather than on every change. The small automatic test run
(**SciForge tests**) takes a few minutes and runs on every push.

## What to send back after testing

1. **View > Panels > Report view**: copy everything, especially lines starting with `[SciForge]`.
2. **SciForge > Diagnostics**: copy the text.
3. A screenshot if something looks wrong.

## What the automatic tests check

Every push runs **SciForge tests** (Actions tab). It uses the official FreeCAD 1.1.4 plus the
SciForge module and checks:

- **Unit tests**: the parts of SciForge that are plain logic (search ranking, timeline rules,
  golden-model format).
- **Golden models**: 32 reference parts (bracket, enclosure, flange, holes, fillets, shells,
  patterns, and "edit an early step" cases). Each is rebuilt step by step and its volume, area,
  size and face count are compared with values worked out by hand. The report appears on the
  run's summary page.
- **GUI smoke test**: starts the real FreeCAD window on a virtual screen, switches to SciForge,
  checks toolbars, shortcuts and the timeline, and saves a screenshot (download
  `sciforge-test-output` from the run).

## Folder map

| Folder | What |
|---|---|
| `src/Mod/SciForge/` | SciForge's own module (workbench, timeline, search, tests) |
| `src/Mod/SciForge/SciForgeTests/golden/` | the golden models and how to write them |
| `docs/sciforge/` | the outline, this guide, the list of changes to FreeCAD's code |
| `tools/sciforge/` | scripts for running tests |
| `prototype/forge-freecad/` | the original "Forge" draft, kept for history |
| everything else | FreeCAD's source code |
