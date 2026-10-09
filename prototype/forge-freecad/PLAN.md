# Forge: plan and progress log

Goal: make FreeCAD behave like Fusion 360 for daily modeling. FreeCAD (and its OpenCASCADE kernel) stays the engine; Forge is a Python/Qt add-on on top. Windows first, then Linux. Target: FreeCAD 1.1.x (stable as of Oct 2026 is 1.1.3).

## Decisions

- **Add-on, not a fork.** Python + Qt, no C++ for now. Survives FreeCAD updates.
- **Copy Fusion's workflow, not Autodesk's names, icons or artwork.** Keeps the project legally clean.
- **Command names are slots with alternatives** (config.py). Missing commands are skipped and reported, never fatal.
- **Layout is data** (config.py). Interface tweaks should not need GUI code.
- **Honest ceiling:** about 80% of daily feel. Engine behavior (fillet robustness, topological naming) stays FreeCAD's, except where we later fix it upstream.
- Windows is the primary test platform; Linux via VM or home-lab box later.

## Done

- [x] v0.1 scaffold: workbench, toolbars/drop-downs, shortcut map, command search (S), timeline with rollback, auto-body, diagnostics, Windows installer, tests (22 passing against fakes).

## Next (in rough priority)

1. **First real run in FreeCAD 1.1.x on Windows.** Expect a few wrong command names and Qt quirks; fix from Diagnostics + Report view output.
2. Timeline polish: real feature icons, drag to reorder, suppress, rename, delete with confirmation.
3. **Parameters table:** named dimensions, edit and reuse (maps to a spreadsheet + expressions).
4. **Browser panel** in Fusion style (bodies, sketches, origin, visibility toggles).
5. Contextual toolbars: show Sketch tools only while editing a sketch, solid tools otherwise.
6. Fusion-style dialogs with live preview for Extrude, Fillet, Hole, Shell.
7. Navigation: research which FreeCAD navigation style (or custom mouse mapping) matches Fusion's orbit/pan.
8. Sketch feel: dimension tool behavior, auto-constrain, trim/extend on hover.
9. Linux pass (AppImage). Then maybe automated tests on a self-hosted Forgejo.

## Open questions

- Exact FreeCAD version Luca installs (needed for the versioned Mod path and API checks).
- Which Fusion behavior Luca misses most (reorders items above).
- Do drop-down group commands behave on 1.1.x? Fallback: `USE_DROPDOWNS = False`.
- Unconfirmed API assumptions to verify on first run: `Command.setShortcut/getShortcut/getInfo`, `Body.Tip` assignment from Python, `ActiveView.getActiveObject("pdbody")`.

## How we work across sessions

I cannot run in the background; each session I write code, Luca tests in FreeCAD and sends the Report view text, Diagnostics output and screenshots. This file plus git history is the memory. Update the Done / Next lists at the end of every session.
