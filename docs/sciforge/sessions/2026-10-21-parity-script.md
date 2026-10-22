# Session notes: measuring Fusion parity with a script (branch `wf/parity-script`)

Idea 5 of [../dev/cadcraft-lessons.md](../dev/cadcraft-lessons.md), approved by Luca on
2026-10-21: count how much of Fusion SciForge has with a script, instead of numbers typed by
hand that go stale. Built on `experimental` at 0b1da82. MEMORY.md was not edited (other
agents work in parallel); merge these notes into it.

## In plain words (for Luca)

- `tools/sciforge/data/fusion-menus.txt` is a checklist of Fusion's commands, by name only,
  in Fusion's own layout: the tabs and their panels, the sketch tab, the drawing workspace,
  the File menu, the right-click marking menus, the browser's and timeline's right-click
  menus, the ViewCube and the navigation bar. 631 entries. Names I am not sure of end in "?"
  (125 of them): if you open Fusion and see a name is wrong, fix that line, it is plain text.
- `python3 tools/sciforge/parity.py` reads SciForge's real menus from its source code (no need
  to start SciForge) and writes **`docs/sciforge/parity-checklist.md`**: the headline, a table
  per tab and panel, and the list of what SciForge does not have yet. Today:
  **Fusion commands present: 457 / 631 (72.4%)**; in the areas SciForge builds (leaving out
  sculpting, sheet metal, plastic, CAM, cloud and the other things you decided against):
  **457 / 543 (84.2%)**.
- That number counts **breadth, not depth**: a command counts when the menu entry exists and
  works, however many of Fusion's options it has. The file says so. The depth check is a new
  page, **`docs/sciforge/dev/core-workflows.md`**: six things you do every day in Fusion, each
  "works end to end: yes / partly / no" with the tests that prove it. Today: sketch-to-fillet
  yes, editing early timeline steps partly, components and joints partly, drawings yes, STEP
  round trip yes, 3D printing export yes.
- **`docs/sciforge/dev/remaining-gaps.md` is now the one work list**: 71 gaps in one ranked
  table (ID, area, impact, effort), plus 5 that need FreeCAD's C++ or the geometry kernel, and
  a "Closed" history. Every gap of the old survey is in it; new rows came from the checklist
  and the workflow check.
- A unit test fails when the checklist is out of date, so after changing a menu run
  `python3 tools/sciforge/parity.py` and commit the new checklist with the change.

## What was built

| File | What |
|---|---|
| `tools/sciforge/data/fusion-menus.txt` | Fusion's command tree by name; the header explains the format (2-space indent, headings are not counted, `?` = not sure, `[in=scope]` where to look in SciForge, `[out=reason]` left out on purpose) |
| `tools/sciforge/data/parity-aliases.txt` | 16 deliberate naming differences ("Activate Component = Activate", the timeline's playback tooltips, Fusion's three sketch chamfer types = SciForge's one Chamfer with types...) |
| `tools/sciforge/parity.py` | Reads SciForge's catalogue, matches, writes the checklist; `--check` (exit 1 when out of date; only the date in the header may differ), `--summary`, `--out`, `--date`, `--repo` |
| `docs/sciforge/parity-checklist.md` | Generated, "do not edit by hand" |
| `docs/sciforge/dev/core-workflows.md` | The six everyday workflows with evidence |
| `docs/sciforge/dev/remaining-gaps.md` | Rewritten as the ranked list (content kept) |
| `src/Mod/SciForge/SciForgeTests/unit/test_parity.py` | 24 unit tests |

### Where SciForge's catalogue comes from (the single sources of truth)

- `sciforge/ribbon_config.py`: the ribbon tabs (`TABS`), `FILE_MENU`, `QUICK_ACCESS`,
  `NAV_BAR`, `MARKING_MENU` + `MARKING_LIST`. Loaded as a plain module by file path: it
  imports nothing, so no FreeCAD is needed. An entry whose command is `None` (shown greyed,
  "not available in SciForge yet") is **not** counted as present.
  `test_ribbon_config.test_mapped_commands_exist_in_freecad_1_1_4` already guarantees every
  other entry names a command that is registered, so "has a command" = "works".
- `sketch_marking.py` (`RING`, `LIST`, OK / Cancel) and `marking_menu.py` (OK / Cancel): every
  `item("Label", command, ...)` call, read with `ast` (both modules import FreeCADGui).
- `browser_core.MENUS` (literal dict, `ast.literal_eval`): one scope per node kind
  (`browser:body`, `browser:component`...).
- Menus built in code, read with `ast` by `menu_labels()`: the strings given to `addAction` /
  `addMenu` (after an icon argument) and to named helpers (`add`, `_tool`), following local
  variables through `for label in (...)`, `for text, fn, enabled in actions` with a literal
  `actions` list, `x if c else y` and `{...}.get(kind, "default")`. Used for the timeline's
  step / group / settings menus and playback buttons (`timeline_ui.TimelineWidget`), the
  ViewCube menu, the workspace menu (`ribbon_ui`, `drawing_ui.fill_workspace_menu`) and the
  drawing sheet bar; plus `derive_ui.MENU_EXTRAS` (Update Derive, Break Link in the timeline).

### Matching rules (decisions)

- Names compared case-insensitively, spaces round "/" and a trailing "..." / "?" ignored.
- A Fusion command is looked for in its own scope first. Commands of SOLID / SURFACE /
  UTILITIES, the File menu, application bar and workspace menu may be found in another of
  those places (SURFACE's Fillet is SOLID's Fillet); the checklist lists those under
  "Present in another place". Context menus, the navigation bar and the SKETCH, MESH and
  DRAWING tabs never borrow (a ribbon command is not a right-click entry; a mesh Shell is not
  a solid Shell; a first run matched the selection filter "Joint Origins" to the navigation
  bar's visibility switch of that name, hence the navigation bar is excluded).
- Panels Fusion repeats on several tabs are listed once (under SOLID); a command in two
  genuinely different places (Delete in MODIFY and in the marking menu) counts in both.
- Out-of-scope entries count in the overall headline and are left out of the second figure,
  so neither number hides the other. Reasons come from feature-outline.md section 8 and the
  decision of 2026-10-09 (no SHEET METAL / PLASTIC / MANAGE tabs).
- An alias is only for the same command under another name; one deliberate merge is aliased
  with a comment (Fusion's "Axis Perpendicular at Point" and "... to Face at Point" are one
  SciForge entry that does both, parity/inspect.md).

## Findings

- The checklist's "Not in SciForge yet" list is short and concrete: the browser's right-click
  menus for bodies and components (Physical Material, Appearance, Properties, Opacity
  Control, Selectable, Create Selection Set, Cut, Move/Copy) are the biggest block (33 of 86
  missing in-scope entries); then drawing extras (Arrange Dimensions, hole notes, DWG, Move /
  Rotate greyed), the Components selection filter and priority still greyed although
  components exist, the File menu's View submenu, ViewCube Set Current View as Front.
- No golden model edits step 2 of a 20-step part (outline 2.3 asks for one); the longest edit
  chains tested are about five steps. That is why workflow 2 is "partly" and why it is G-01,
  the top of the work list (cheap and important: build it from the Pi 5 case).
- `remaining-gaps.md`'s survey was partly stale: document tabs moved to the top on
  2026-10-16, and the insert-export items exchange-2 closed were still listed (its session
  notes said so). Both moved to "Closed". The revolve / pattern "edit does not roll back"
  rows were narrowed: `edit_rollback.py` (2026-10-21) rolls the marker back for dialog edits
  from the timeline; whether patterns and revolves are fully covered is marked "check".
- SciForge entries Fusion's list does not have are listed at the end of the checklist
  (SciForge's own additions: AI, FreeCAD Tools, Export Everything, Gear, Set Orbit Center...;
  also label variants such as Unsuppress Features). That section is the place to spot an
  alias that is needed.

## Limitations

- Fusion's tree is from memory, not a capture (Luca: no recordings; Autodesk's site is not
  reachable from the sandbox): 125 names carry "?". The headline will move as Luca corrects
  them. Not covered: dialog options, the Sketch Palette's check boxes, the Data Panel, Help
  and account menus, keyboard-only actions.
- Presence only: a present command may still lack options (that is what core-workflows.md
  and the parity docs are for).
- The static reading of code-built menus covers the patterns used today; a menu rewritten in
  another style would drop out silently. `test_every_sciforge_menu_is_read` checks one or
  more labels of every source so such a refactor fails a test.
- Merges: the committed checklist goes out of date whenever another branch changes a menu;
  `test_the_committed_checklist_is_up_to_date` then fails until someone runs
  `python3 tools/sciforge/parity.py` and commits the result. That is intended (the number
  never goes stale), but it means **after merging the parallel branches, regenerate the
  checklist once**.

## Tests

- `test_parity.py`, 24 tests: parser (headings not counted, inherited scopes / out, "?",
  malformed lines refused with their line number), aliases (plain, qualified, malformed),
  matcher (present, greyed, borrowed between ribbon tabs, never borrowed by context menus,
  out, alias), rendering (header, both headline figures, tables, lists), `same_checklist`
  (only the date may differ, CRLF tolerated), the real catalogue (an entry of every source
  read, greyed entries read as greyed, every Fusion scope names a real SciForge place, every
  alias still matches a Fusion name and a SciForge label, core commands found), and
  `--check` (the committed checklist is up to date; passes after writing, also on another
  day; fails after a change and when the file is missing; a broken Fusion list gives exit 2
  and the line, no traceback).
- `run_tests.sh --only base`: unit 1823 OK (9 skipped), golden 446 pass + 2 known xfail,
  smoke, journey, restart: all passed.
- No SciForge module was changed, so no existing scenario is affected. The 52 scenarios cited
  as evidence in core-workflows.md were run here with real FreeCAD 1.1.4 under xvfb, all
  passed:
  - workflows 1-2: fillet_qa_part, fixsketch_fillet / _hole / _join / _move / _presspull /
    _shell_draft, gaps_timeline_start, patterns_qa_edit, pi5_case (124 checks),
    revolve_qa_part, sketch_infer, sketch_qa_part, sketch_tools_constraints,
    sketch_tools_extrude, timeline_browser_qa, timeline_rolled_cut;
  - workflow 3: components_basic, components2_move / _copy / _pattern / _bodies,
    joints_basic, joints_types, joints_components, joints2_drag / _slider / _motion /
    _nested, joints_asbuilt_group;
  - workflow 4: drawing_new, drawing_views, drawing2_views, drawing_section, drawing_detail,
    drawing_dimensions, drawing2_tolerance, drawing2_ordinate, drawing2_symbols,
    drawing_annotations, drawing_update, drawing2_update, drawing_assembly, drawing_export,
    drawing2_sheets;
  - workflows 5-6: exchange2_step_open, exchange2_step_insert, insert_step, exchange2_export,
    export_formats, export_print, send_to_slicer, export_everything, mesh_print.
- Resumed after a machine restart: the second scenario batch was cut off and was run again
  in full (all passed); `--only unit` rerun after the resume: 1823 OK (9 skipped);
  `parity.py --check` passes. One count corrected in core-workflows.md (19 `sf_revolve_*`
  golden models, not 21).
