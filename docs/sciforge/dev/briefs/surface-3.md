You are building one feature area of SciForge, a FreeCAD 1.1.4 fork that must behave exactly like Autodesk Fusion. The owner, Luca, is a beginner who only tests; he wants the finished product, so build the whole area, not a slice. Read `docs/sciforge/dev/briefs/wave6-common.md` first (and `common.md` it points to).

## Your area: SURFACE part 3, the options of the surface tools, branch `sf/surface-3`

Fusion's behaviour: `docs/sciforge/dev/research/fusion-surface.md`; the audit of SciForge's
SURFACE tab against it, with file:line evidence and probes: `docs/sciforge/dev/research/
surface-gaps.md`. Read `docs/sciforge/parity/surface.md` to the end. You own the `surface*`
files (surface.py, surface_core.py, surface_geom.py, surface_ui.py, surface_pick.py,
surface_analysis*.py). surface-4 makes the SOLID modify tools (Split Body, Delete, Fillet,
Move, Pattern, Scale, Press Pull) take surface bodies and builds Merge: stay out of those.

Close these gaps of the audit (numbers = its ranking), biggest value first:
- #3 **Offset Type Sharp / Rounded**, default Sharp (Fusion May 2025); files saved before keep
  Rounded (their result must not change on reopen).
- #7 **Sweep Path + Guide Surface** (reuse the solid sweep's `sweep.py` guide-face code).
- #8 **Patch**: Reverse Normal + Flip, Group Edges off (a Continuity per edge), Tangency Weight
  (default 0.5; build what OpenCASCADE allows and say what it cannot).
- #9 **Extend Natural** on free-form / sphere / torus / revolved / extruded faces (extend the
  surface by its own definition or by sampling and re-fitting); Align Edges where possible.
- #11 **Untrim** Type Manual and Keep Copy.
- #12 **Revolve**: Project Axis, the extent called Partial, To Object with Two Sides.
- #13 **Extrude**: To Object Match Shape, Chain Faces / Extend Faces, planar faces as profiles.
- #14 **Sweep Path + Guide Rail** extents (Perpendicular to Path / Full Extents) and the Path /
  Guide Rail distances.
- #15 **Loft** Edge Alignment (Free Edges / Align Edges / Align to Surface) and the Sep 2026
  closed-loft corner matching.
- #21 **Stitch** Operation (New Body / Join / Cut / Intersect when it closes).
- #22 **Trim** with a single face of a body as the tool.
- #24 **Ruled** default type and Corner Type as a Rounded / Mitered choice (check the research).
- #17 **INSPECT > Environmental Map Analysis** (Sept 2026: a reflection map on the faces, like
  Zebra; `surface_analysis.py`).
- #18 **Sketch > Project / Include > Isoparametric Curve** (U or V curves of a face) if time
  allows (sketch_project.py shows how projected curves live next to a sketch).
- Anything else in the audit that is in your files.
Each with Fusion's options, live preview, timeline edit, undo/redo, save/reopen (old files
unchanged), refusals with the reason. Scenarios `surface3_*.py` (8+ paths), golden models
for the new geometry (`surface3_ops.py` / `surface3_schema.py`), unit tests; keep every
existing `surface*` scenario and `test_surface_core.py` passing (run them). Update
`docs/sciforge/parity/surface.md` (new rows with sources, gaps closed / left).
