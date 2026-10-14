# Session log: sketch Text and Emboss (branch `sf/text-emboss`)

Outline 7.5 "text" and 7.6 "Emboss". Both ribbon entries were greyed out; both work now.
Behaviour spec with sources, what was built and what was not: `docs/sciforge/parity/text-emboss.md`.

## Status

- [x] SKETCH > CREATE > Text: frame by two clicks, live preview, height (formulas), angle
      (typed or round handle, about any of the frame's 9 dots), system fonts (Windows and
      Linux font folders), bold / italic / underline, alignment, character spacing, flip,
      Text On Path (above / below, fit, alignment), multi-line text, text expressions
      (`'text' + param`)
- [x] texts in the open sketch: one click picks the whole text, drag moves it, double-click
      edits it, Del deletes it, right-click Edit Text / Explode Text
- [x] texts are profiles: E (auto-pick when the sketch holds only a text), click-then-E,
      Q (Press Pull hands them to Extrude), Emboss
- [x] Explode Text keeps the extrudes / embosses that used the text (they use the letters'
      sketch areas instead)
- [x] save / reopen keeps the text editable; a missing font falls back with a plain message
- [x] SOLID > CREATE > Emboss: profiles and faces, Emboss / Deboss, depth (negative swaps),
      alignment distances and angle with handles, Tangent Chain, live preview, timeline
      step, edit, undo / redo
- [x] flat faces exact (rigid move), cylinders and cones unrolled exactly, other faces
      projected with a note in the dialog
- [x] model parameters (text height, emboss values), Delete takes a sketch's texts along
- [x] unit tests, 4 golden models, 7 scenarios

## Findings worth keeping

- `Part.makeWireString` scales by `height / face.height` (FreeType's face height, not the
  em size): `text._FontGlyphs` calibrates per font so the Height is the em box, as in
  Fusion. Kerning comes only from the old `kern` table.
- A Python-made B-spline copy of a circle makes OpenCASCADE's volume measure up to 1 % off
  (rational B-spline faces). Emboss on flat faces therefore moves the profile rigidly
  (circles stay circles).
- FreeCAD's sketch edit hides what depends on the sketch through `Show.TempoVis` and
  prints errors on closing the sketch when such an object was deleted meanwhile:
  `text._forget_hidden` drops the deleted text from it.
- FreeCAD's App observer has no "restore finished" slot (`slotFinishRestoreDocument` is
  never called; `thread_ui.py` also relies on it, worth checking by its owner).
- FreeCAD's progress during a long shape operation runs Qt events, so a scenario step can
  run inside a recompute, where FreeCAD's wait cursor ignores every key. `emboss_flat`
  has a `wait_idle` step that comes back until FreeCAD is done.
- FreeCAD's sketcher draws B-spline combs, degree and knot labels by default; an exploded
  text was unreadable. `sketch_mode.PARAMS` now switches them off (the control polygon
  stays).

## Session log

- 2026-10-13/14: research (Autodesk help and API, forum), fonts / layout / emboss maths
  (Qt-free, unit-tested), text object and dialog, emboss feature and dialog, integrations
  (sketch areas, profile picker, Extrude, Press Pull, Delete, Parameters, right-click
  menu), scenarios `sketch_text_basic`, `sketch_text_edit`, `sketch_text_path`,
  `sketch_text_cut`, `sketch_text_more`, `emboss_cylinder`, `emboss_flat`, golden models
  `emboss_flat_rect`, `emboss_flat_deboss`, `emboss_cylinder_rect`,
  `emboss_cylinder_deboss`. Regression runs: `sketch_areas`, `sketch_areas_face`,
  `sketch_areas_more`, `sketch_draw`, `extrude_presspull_qa`, `bodies_delete`,
  `sketch_menu_switch`, `--only base`: all pass. No FreeCAD core file changed.

## Next

- Luca to check the "Guess" rows of the parity spec against his Fusion.
- A corner handle to resize the frame (today: drag or dimension its lines).
- Text On Path: a drag handle along the path (today: alignment and the path itself).
