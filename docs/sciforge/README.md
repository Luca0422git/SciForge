# SciForge: start here

SciForge is a fork (a copy we are allowed to change) of FreeCAD 1.1.4, being reshaped until it
works the way Fusion users expect (Fusion is Autodesk's trademark; SciForge is not affiliated with
Autodesk). The plan is in [feature-outline.md](feature-outline.md); progress
is tracked in [MEMORY.md](../../MEMORY.md).

## Releases

Releases (0.1.0-beta and later) follow the brief [dev/briefs/beta-release.md](dev/briefs/beta-release.md):
all work goes to `develop`; the `Release` branch only ever receives a tested `develop` commit, on
Luca's green light, and the tag `sciforge-v<version>` on that commit starts the build that
publishes the GitHub release (section 1 of the brief has the exact steps). The user-facing side
is the repository's [README.md](../../README.md), the [CHANGELOG.md](../../CHANGELOG.md) (the
release notes are made from its newest section), [known-issues.md](known-issues.md),
[privacy.md](privacy.md) and [smartscreen.md](smartscreen.md) (the fixed "Windows protected your
PC" text, also in the README and in every release's notes). Screenshots for the README are made
by `tools/sciforge/screenshots.sh`. `tools/sciforge/check_links.py` checks the links in those
documents (it also runs as a unit test).

## Getting a SciForge build to test (Windows)

You never need to compile anything yourself. GitHub builds it:

1. On GitHub, open the repository, click **Actions**, then **SciForge build** in the left list.
2. Click **Run workflow**, pick `windows` (or `both`), and press the green button.
3. Wait. A full build takes a few hours (the C++ part of FreeCAD is large). Quick checks run
   first (about 10 minutes, including the test models on FreeCAD for Windows); when one fails,
   the run stops there instead of compiling for hours.
4. When the run is finished, open it and scroll to **Artifacts**. Two downloads:
   - `SciForge-Windows-installer-...`: GitHub wraps it in a .zip; inside is
     `SciForge_..._installer.exe`. Run it: it installs to `C:\Program Files\SciForge`, adds a
     Start menu entry (and a desktop icon if you tick it) and an uninstaller in Windows'
     "Installed apps". A FreeCAD on the same PC stays as it is (see "Compatibility" below).
   - `SciForge-Windows-portable-...`: a `.7z` inside. Unpack it (7-Zip) anywhere, for example
     `C:\SciForge`, and run `bin\SciForge.exe`. Nothing is installed or registered.
   The build is uploaded before its tests run, so it is there even when a test failed (the
   run then has a red cross). Then ask Claude what failed before relying on it: the same
   test models already passed on FreeCAD for Windows before compiling, so a failure here is
   usually in the compiled part, which a quick update cannot fix.
5. SciForge opens in its own interface (the SciForge workbench is the start workbench). The
   Start page is still FreeCAD's for now.

About cost: the repository is public (since 2026-10-10), and GitHub's standard build machines are
free for public repositories, so builds cost nothing. A full build still takes a few hours, so it
is started by hand (or by a `sciforge-v*` tag) rather than on every change. The automatic test
run (**SciForge tests**) takes about 40 minutes (6 machines side by side, one of them Windows) and
runs on every push.

Linux: the same run uploads `SciForge-Linux-...` with an `.AppImage`: make it executable and
run it (`./SciForge_....AppImage`; `--appimage-extract` unpacks it when FUSE is missing).

## Compatibility: SciForge next to FreeCAD

SciForge is a separate program since the branding pass (2026-10-13, `core-patches.md` #8 to
#13). On one PC, SciForge and FreeCAD do not see each other:

| | SciForge | FreeCAD 1.1 |
|---|---|---|
| Program | `SciForge.exe`, `SciForgeCmd.exe` (Linux: `sciforge`, `sciforgecmd`) | `FreeCAD.exe` |
| Install folder (installer) | `C:\Program Files\SciForge` | `C:\Program Files\FreeCAD 1.1` |
| Settings, add-ons, macros | `%APPDATA%\SciForge` (Linux: `~/.config/SciForge`, `~/.local/share/SciForge`) | `%APPDATA%\FreeCAD` |
| Registry / uninstall entry | `SciForge` keys only | `FreeCAD` keys only |
| `.FCStd` double-click | Only if ticked in the installer (off by default) | Unchanged |
| Window title, About, splash | SciForge, with FreeCAD credited | FreeCAD |

What this means in practice:

- **A fresh settings folder.** The first start of a SciForge build is like a first start:
  FreeCAD's settings, add-ons and macros are not copied (and not touched). SciForge sets its own
  theme and keys, so there is little to carry over; copy `%APPDATA%\FreeCAD\Macro` by hand if
  you need your macros.
- **Designs are shared.** `.FCStd` files open in both; a design saved by SciForge opens in
  FreeCAD 1.1 (SciForge's features are FreeCAD features). File > Open in either program.
- **The quick update works on both layouts** (`quick-update.md`): the installed SciForge is found
  by itself; a portable build or an older FreeCAD-named folder is picked in the dialog.
- **Fusion files** (`.f3d`) cannot be opened; export STEP (solids) or 3MF/STL (meshes) from
  Fusion. The Fusion-to-SciForge keys and mouse are in `cheat-sheet.md`.
- **Uninstalling** SciForge (Windows "Installed apps") removes the program folder and, only if
  you tick it, `%APPDATA%\SciForge`; FreeCAD's files and settings are never removed.
- The window title says `SciForge 1.1.4`: 1.1.4 is the FreeCAD core inside; SciForge's own
  build number is in SciForge > Diagnostics.

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
