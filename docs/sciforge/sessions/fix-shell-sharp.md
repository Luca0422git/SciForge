# Session log: fix-shell-sharp (2026-10-23)

**What was wrong.** plastic-1 found that FreeCAD's Thickness with Join = Intersection (SciForge's
Shell Type Sharp) gives a half pipe (a D profile extruded, its flat side taken away) back
unshelled, "valid", with no error. Reproduced headless on FreeCAD 1.1.4:
`makeThickness(..., join=2)` returns the base itself (same 4 faces, volume 37699.11) for
Inside and Outside walls; Join = Arc (Rounded) shells it (Inside 2 mm: 9198.58).
The Shell dialog's trial already refused Inside / Outside, but only by luck (the volume check
for a too-thick inside wall, then "cannot be made with these walls ... or try another
thickness"). **Direction Both + Sharp was accepted**: the unshelled inside "wall" was fused
with the outside one and the whole part came back, valid, no warning (SciForge's ShellFeature).

**Fix** (`shelling.py`). A wall that comes back as the part itself (same faces, same volume)
raises `Unshelled`; `build()` turns it into "Sharp corners cannot be built here: FreeCAD's
geometry kernel gives the part back unshelled. Choose Shell Type Rounded." when Rounded works,
else the old "too thick" text (a too-thick inside wall also comes back unchanged). Every path
that builds a shell uses `build()` (the dialog's trial, ShellFeature.execute, the hidden steps in
other bodies, the AI ops, the golden builder), so the step stays out (dialog) or invalid
(ShellFeature recompute) instead of wrong.

**Test.** New scenario `shell_draft_qa_sharp` (real input: the half pipe's bottom clicked from
below, Shell; Inside Sharp and Both Sharp refused with the reason, OK waits, nothing made;
Rounded: exact volume; OK; edit from the timeline to Sharp refused, Esc keeps the rounded shell;
Ctrl+Z / Ctrl+Y).

**Gap left.** A native Sharp shell (FreeCAD's `PartDesign::Thickness`) that was fine when made
and only fails after an earlier step is edited still recomputes to the unshelled part: the
native feature cannot be made to refuse without a core patch (FeatureThickness) or moving Sharp
face shells to SciForge's ShellFeature. Opening it from the timeline shows the reason.
Hollow (body picked) on the half pipe is refused as "too thick" for both types: FreeCAD's
`makeOffsetShape` returns a null shape there (pre-existing, not changed).
