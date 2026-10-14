You are building one feature area of SciForge, a FreeCAD 1.1.4 fork that must behave exactly like Autodesk Fusion. The owner, Luca, is a beginner who only tests; he wants the finished product, so build the whole area, not a slice. Wave 5 closes more of the gaps in `docs/sciforge/dev/remaining-gaps.md` (read it).

## Your area: Polish, part 2, branch `sf/polish-2`

Read MEMORY.md "Next steps" (item 0a), `docs/sciforge/parity/extrude-presspull.md`, `timeline-browser.md`, `versions.md`, `misc.md` and `ui-shell.md` to the end. Build:
1. **Value boxes on every handle** that still has none: Move's triad (distance / angle by the arrow being dragged), Scale's arrows, Draft's angle disc, and any other drag handle you find without one (grep `taskui.BoxCarrier` subclasses and compare with `taskui.ValueBoxes` users). Digits typed over the view go into the box of the handle in use, like everywhere else.
2. **Fusion's floating green check** near the pointer while a sketch line (and other multi-click sketch tools) is being drawn: a small OK button that finishes the tool, as Fusion shows it.
3. **Timeline groups**: drag a whole group in the timeline, collapse / expand, rename, ungroup; the marker over a group (check `timeline_ui.py`).
4. **Versions**: Milestones (mark a version as a milestone, list them, open one), an automatic version on close when the design changed (Fusion asks on close), the out-of-date icon when an inserted / derived design has a newer version, and the Data panel's Move / Copy of designs between folders.
5. **Derive**: bring components with their structure (not flat) and choose the source version.
6. **Extrude made while rolled back before a fillet can switch to Cut** (timeline-browser gap), and any other small gap of `timeline-browser.md` / `ui-shell.md` that does not touch where dialogs are docked (floating dialogs and top document tabs stay as they are this wave).
Scenarios `polish2_*.py` (8+ paths: a Move typed in the triad's value box, a Scale typed at its arrow, a Draft angle typed at its disc, the green check ends a line, a timeline group dragged before an earlier step, a milestone made and opened, the close prompt makes a version, a derived design flagged out of date and updated, undo/redo, save/reopen). Unit tests for the Qt-free parts. Update the parity docs you touch.
