# 2026-10-23: Suppressing a surface step keeps the surface before it (branch `sf/fix-surface-suppress`)

The defect (left open by surface-4's QA, `docs/sciforge/parity/surface-modify.md`): timeline
right-click > Suppress Features on one of the older SURFACE steps (`surface.py`'s
`SurfaceFeature`: Extrude, Revolve, Sweep, Loft, Patch, Ruled, Offset, Boundary Fill, Thicken,
Trim, Untrim, Extend, Stitch, Unstitch, Reverse Normal) left its body EMPTY and turned the steps
after it red. No core patch (no full build needed).

## Reproduced (before the fix)

- Golden model `surface_suppress_patch_trim` (Patch a 30 x 30 square, Trim a hole of radius 5,
  suppress the Trim): the body's shape was null ("shape is invalid" when measured) instead of
  the 900 mm² patch.
- `surface_trim` (new last part, run on the old `surface.py`): Suppress Features on "Trim 2"
  left wall 1 with area 0 (blank, no longer a surface body) instead of Trim 1's 30 x 10.

## Root cause

FreeCAD 1.1.4's `PartDesign::Feature::recompute` for a suppressed step runs the step's
`execute` and then replaces its Shape with the base's shape only when that holds a solid
(`getBaseTopoShape(true)`): a surface (a shell) gives an empty shape. So a suppressed surface
step came out empty, the body showed nothing and the steps after it had no surface to work on.
Probed with a bare `PartDesign::FeaturePython`: suppressed, its `execute` IS called (the
surface-4 session note says it is not; it is), then Shape is set empty and `onChanged("Shape")`
follows.

## The fix (`sciforge/surface.py`, `SurfaceFeature`)

- `onChanged("Shape")`: a suppressed step whose shape FreeCAD just emptied takes a copy of the
  step before it (`BaseFeature`) when that has faces, the same way surface-4's
  `SurfaceModifyFeature.onChanged` does. Skipped while the document restores or undoes (the
  file / the undo step brings its own shape); a guard stops it calling itself.
- `execute` does nothing while the step is suppressed: there is nothing to build, and building
  a step whose base went off (the first step of its body suppressed) could only fail and print
  an error at every recompute ("Failed to recompute suppressed feature").
- The first step of a body suppressed leaves the body empty (nothing before it); the
  timeline's Suppress already takes the steps that break with it off too
  (`timeline_ops.suppress`), so nothing turns red. Unsuppress gives everything back.

## Tests

- New golden model `surface_suppress_patch_trim`: Patch, Trim; suppress the Trim (900), save,
  close and reopen (still 900), unsuppress (900 - 25 pi); suppress the Patch, unsuppress
  (900 - 25 pi).
- `surface_trim`, new last part (real right-clicks on the timeline): Suppress "Trim 2": wall 1
  shows Trim 1's 30 x 10 and is still a surface body, nothing red, no pop-up; Unsuppress: 20 x
  10 again. Suppress "Extrude 1" (wall 1's first step): the Trims on it go off with it, wall 1
  is empty, wall 2 unchanged, nothing red, no pop-up; Unsuppress: all back. On the old
  `surface.py` it fails ("wall 1 shows Trim 1's 30 x 10": 0.0).
- `surface_patch`, new last part: Suppress "Patch 1" (the lid's body's first step): the lid's
  body is empty, the tube unchanged, nothing red, no pop-up; Unsuppress: the lid is back.

Results (FreeCAD 1.1.4, one scenario at a time): `surface_trim` 86 PASS, `surface_patch` 82
PASS, `surface_misc` 70, `surface_reopen` 44, `surface3_offset_patch` 76,
`surface4_delete_merge` 48, `timeline_browser` 92 all PASS; unit 1995 OK (9 skipped); golden
587 pass + 2 xfail (the known `plate_hole_grid`, `sf_loft_merge_slot_volume`).
