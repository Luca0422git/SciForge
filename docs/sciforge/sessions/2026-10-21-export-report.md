### Session log: export and import reports (branch `wf/export-report`, 2026-10-21)

Written instead of a MEMORY.md entry (parallel branches; merge it into MEMORY.md's session
log when the branch is merged). Idea 2 of `docs/sciforge/dev/cadcraft-lessons.md`, approved
by Luca: "say what an export leaves out, and what an import skipped; never drop data
silently". Base: 0b1da82 (experimental). No FreeCAD core change (no `SCIFORGE:` patch, no
core-patches entry, no full build needed).

#### What Luca sees (plain language)

- After you export, a small dark card appears in the bottom right corner of the 3D view:
  "Exported parts.stl / Not kept in this file:" and a short list, for example "the timeline
  (4 steps): the file holds the finished shapes only", "2 sketches", "1 parameter (their
  values are built in)", "2 bodies become one mesh: no names, no separate parts", "the
  colours of 1 body". It only lists what *your* design really had, and it does not show at
  all when nothing is lost. It is not a pop-up: you do not have to click anything; it goes
  away by itself after 10-30 seconds (the mouse over it keeps it), or with its x.
- It works for File > Export (STEP, IGES, STL, 3MF, OBJ, DXF, DWG), right-click a sketch >
  Save As DXF, Save As Mesh, 3D Print (only what matters for printing: hidden bodies,
  colours, bodies merged in an STL, the unit, cosmetic threads, mesh bodies with holes),
  Export Everything (one card for the four files; "(STL, 3MF, OBJ)" after an item only some
  of them lose) and a drawing's Export PDF / Export DXF.
- After Insert Mesh, Insert SVG / DXF and File > Open / Insert STEP or IGES, the same card
  says what did not come in or came in changed: "the mesh is not closed: 4 open edges",
  "1 hatch (FreeCAD cannot read them)", "1 text or dimension (only curves go into the
  sketch)", "5 loose faces that are not part of a solid", "the file says its numbers are in
  inches; it came in as millimetres: change Unit Type if the size is wrong"...
- Every card is also written to the Report view as one line starting with `[SciForge]`.

#### Built

- `sciforge/export_report_core.py` (pure Python, unit tested): the rules per format and
  the sentences (`items(fmt, facts, purpose)`), `combine()` for several files, the import
  rules (`mesh_items`, `cad_items`, `curve_items`) and small readers for FreeCAD's DXF
  import statistics, SVG, 3MF and OBJ text.
- `sciforge/export_report.py` (FreeCAD, headless is fine): counts what the design has, by
  following each export path exactly (the same bodies, the same shown / hidden rules, the
  same STEP structure as `exchange._mirror_document`). **For the AI layer** (not wired in
  here: another branch rewrites `sciforge/ai/`): `export_report.losses(doc, objects, fmt,
  purpose="file", **options)` returns `[{"key", "count", "text"}]` (empty = nothing lost);
  `objects` None = the whole design as File > Export writes it, a list of bodies, a
  component, a sketch / `(body, "FaceN")` for DXF, a drawing page for `"drawing_pdf"` /
  `"drawing_dxf"` (`which="all"|"current"`); options `unit`, `per_body`, `level` /
  `surface` / `normal`, `whole=True` (the bodies a whole-design export took, as the AI
  export tool and Export Everything do: `export.exportable_bodies(doc)`: hidden bodies are
  then reported too). `export_report.describe(file_name, entries)` gives the one-line
  text. The AI export tool (`sciforge/ai/bridge.py` `_export`) should call
  `losses(doc, body_list, label, whole=True)` and return the items with its result.
- `sciforge/export_report_ui.py`: the card (`show`, `report_losses`, `report_combined`,
  `report_import`, `recent()` for tests / the AI, `current()`), theme-aware (dark colours
  through `theme.translate`), never takes the keyboard, never raises.
- Wired in (each call guarded, after the file is written, so a report problem never turns
  a good export into a failure): `export_ui.ExportDialog.run` (+ `report`), `PrintDialog.save`,
  `export_everything` (+ `report_everything`), `exchange_ui.save_as_dxf`, `open_file`,
  `insert_cad_file` (+ `report_cad_import`), `insert_ui.InsertMeshPanel.accept` and
  `InsertCurvesPanel.accept` (+ `report_mesh_import`, `report_curves_import`),
  `drawing_ui.ExportDialog._export` (+ `_report`).
- Import notes collected where the file is read: `step_import.read_tree(path, notes)`
  (`Made.notes`), `insert.read_curves(path, notes)` (DXF through
  `importDXF._import_dxf_file`, the function FreeCAD's own `insert()` runs, to get its
  statistics; falls back to `insert()` on another FreeCAD).
- `export.export_mesh_files`: "the mesh is not watertight" is now a log line, not a
  warning: the export card says it ("1 mesh body not closed (holes): a slicer may
  complain").

#### What each format keeps: checked in FreeCAD 1.1.4, not guessed

| File | Finding (how it was checked) |
|---|---|
| STL | binary: every triangle's colour bytes 0, header "MESH-MESH...", no names; all bodies in one mesh (file read back) |
| 3MF | one `<object>` per body with its name (SciForge writes them), the unit attribute as chosen; no `basematerials` / `colorgroup` (zip read back) |
| OBJ | `g <body name>` per body, no `mtllib` / `usemtl` (no colours) |
| STEP (headless, `Import.export`) | no `COLOUR_RGB` / named colour at all; one product per component; read back with SciForge's reader: components there, bodies in a component come back Body1, Body2 ... (exactly the count the report gives), no sketch, parameter, timeline step or material |
| STEP (window open, `ImportGui.export`) | colours written (an orange look came back as `COLOUR_RGB` 0.9 / 0.4 / 0.1; red, green, blue ... are written as STEP's named colours); see-through: `exchange._paint` writes alpha 1 (read in the code) |
| IGES | no colour entity (type 314) and no colour number in any directory entry; read back as one unnamed product "SciForgeExportCAD": body names lost except where a label happens to be Body2, Body3 ... in the right place (the count follows `exchange_core.body_labels`) |
| Sketch DXF | LINE / ARC / CIRCLE / ELLIPSE / SPLINE kept (splines stay splines); points, construction geometry, constraints and dimensions not written (DXF entities counted) |
| Drawing DXF | SciForge's own writer (`drawing_core.DxfWriter`): dimensions as LINE + TEXT, no DIMENSION entity; non-circle curves as polylines; hatching as LINEs on HATCH; no STYLE table (no font) (read in the code; `drawing_export` B checks the message) |
| Mesh import | `Mesh.Mesh` reads a 3MF's objects into one mesh, ignores its colours and its `unit="inch"` (a 1-inch cube came in 1 x 1 x 1) |
| DXF import | `Import.readDXF` statistics: HATCH listed as unsupported; TEXT read but not imported ("Import texts and dimensions: No"); POINT becomes a vertex SciForge's sketch does not take |
| STEP import | a part holding a solid, an open shell and a line: only the solid comes in (`_pieces` takes the solids when there are any); loose edges never come in |

#### Decisions

- The card lists only what this design has (counts), in SciForge's own words; nothing
  when nothing is lost. A design with features always loses its timeline in an exchange
  file, so most 3D exports show a card: that is the point (CADCraft does the same).
- 3D Print shows only print-relevant items (`PRINT_KEYS`): the timeline is not news when
  you send a part to the slicer.
- "the timeline (N steps)" counts the timeline's steps without components and without the
  shape a STEP / mesh file brought in (an opened STEP has no history to lose).
- The sketch of a New Body extrude lives in the body that was active when it was drawn
  (SciForge's structure), so exporting only the new body reports its own steps only.
- Joints are reported for whole-design exports only.

#### Tests (real FreeCAD 1.1.4)

- Unit: `test_export_report_core.py` (40 tests). Full unit suite: see below.
- Golden (headless, with round trips: `golden/export_checks.py`, schema
  `golden/export_schema.py`): `export_report_design` (STEP / IGES / STL / 3MF / OBJ of a
  design with a fillet, a New Body, a hidden body, a material, a component and its copy; a
  component; chosen bodies in inches / centimetres), `export_report_sketch_dxf`,
  `export_report_imports` (open STL, 3MF with two objects in inches, STEP with loose
  faces and a line, IGES of loose faces, DXF with a hatch / text / point, SVG with a text
  and a picture): all pass.
- New GUI scenarios with real input: `export_report` (61 checks: STL / STEP / 3MF via the
  Export dialog, the card's place, its x, the Report view line, colours in the STEP file),
  `import_report` (39: Insert Mesh of an open mesh, export of it, a clean mesh gives no
  card, Insert DXF, Ctrl+O of a STEP).
- `drawing_export` gained checks: the PDF gives no card, the DXF card lists the dimension,
  the hatching and the font.
- `--only base`: unit 1839 OK (9 skipped), golden 449 pass + 2 known XFAIL
  (`plate_hole_grid`, `sf_loft_merge_slot_volume`), smoke 79, journey 25: all passed.
- Existing scenarios that touch the changed export / import paths, all PASS:
  drawing2_breakout 96, drawing2_sheets 87, drawing_export 76, exchange2_export 89,
  exchange2_link 42, exchange2_manip 43, exchange2_step_insert 75, exchange2_step_open 80,
  export_everything 27, export_formats 54, export_print 44, insert_canvas 48, insert_dxf 35,
  insert_mesh 65, insert_reopen 25, insert_step 30, insert_svg 38, mesh_edit_reopen 50,
  mesh_erase_section 56, mesh_print 34, mesh_repair 73, mesh_separate_combine 80,
  meshinspect2_direct 79, meshinspect2_groups 74, misc_decal 54, misc_preferences 84,
  pi5_case 124, polish2_value_boxes 63, send_to_slicer 105, versions_data_panel 30,
  ribbon_sweep 218. No old expectation had to change.
- Round trips found real things on the way: the IGES product is named after SciForge's
  throw-away document, so body names come back Body1... (or the document's name for a
  single body); an opened STEP's base shapes are no history (first counted as timeline
  steps, fixed); STEP writes pure red / green / blue as named colours, not COLOUR_RGB.

#### Limitations / not done

- The AI export tool is not wired in (the `sciforge/ai/` rewrite is on another branch):
  call `export_report.losses(...)` there (see Built).
- Not checked with a real converter: DWG (same rules as DXF; no converter in the sandbox).
- See-through looks in STEP: from the code (`exchange._paint` writes alpha 1), not from a
  file read back.
- A drawing's "curved edges written as short lines" count comes from the views' edges;
  not compared with the file entity by entity.
- Self-intersections of an inserted mesh are not checked (slow on big meshes); open edges,
  edges shared by three triangles, flipped triangles and separate pieces are.
- The card is SciForge's own (bottom right of the 3D view); Fusion shows no such message.
