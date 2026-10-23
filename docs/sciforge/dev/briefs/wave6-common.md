## Wave 6 (2026-10-23): SHEET METAL, PLASTIC, SURFACE part 3. Rules for every builder

Luca asked (2026-10-23, overnight): "There are two areas of fusion that we are missing. Sheet
metal and plastic. ... plan all the features that belong in those tabs, and then build them
all. In one shot. Both tabs. And ... take a look at the surface tab and make sure everything is
fully fledged out." This reverses the decision of 2026-10-09 ("No SHEET METAL, PLASTIC or
MANAGE tabs"). The plan is `docs/sciforge/plan-sheet-metal-plastic-surface.md`.

Read first, in this order: `docs/sciforge/dev/briefs/common.md` (every rule there applies,
except where this file says otherwise), this file, your own brief, the plan above, the
research files `docs/sciforge/dev/research/fusion-*.md` (Fusion's behaviour, with sources:
the source of truth for what to build; the sheet metal and plastic files get a "## Critic
pass" section from a second researcher at the end: if your copy has none, read it from
`/tmp/claude-0/-home-user-SciForge-Parametric-Design/b3b58fe0-e649-51d5-b6e4-7edc97b46dc5/scratchpad/research/`
(sheet_metal.md, plastic.md) once it is there) and `docs/sciforge/dev/research/integration-map.md`
(how a tab, a body kind, a step, an icon and a test plug into SciForge, with file:line).

### Seven builders at the same time

| Builder | Branch | Owns (only it edits these) |
|---|---|---|
| sm-forming | `sf/sm-forming` | `sheetmetal_core.py`, `sheetmetal.py`, `sheetmetal_form.py`, `sheetmetal_rules_ui.py`, `sheetmetal_flange_ui.py`, `sheetmetal_*` files it creates, `icons_sheetmetal.py`, `sheetmetal_ops.py`, `sheetmetal_schema.py`, `parity/sheet-metal.md` |
| sm-flat | `sf/sm-flat` | `sheetmetal_unfold.py`, `sheetmetal_flat.py`, `flatpattern*` / `unfold*` / `rip*` / `sm_convert*` files it creates, `icons_flatpattern.py`, `flatpattern_ops.py`, `flatpattern_schema.py`, `parity/sheet-metal-flat.md` |
| sm-more | `sf/sm-more` | `sheetmetal_hem*`, `sheetmetal_bend*`, `sheetmetal_corner*`, `sheetmetal_lofted*` files it creates, `icons_sheetmetal2.py`, `parity/sheet-metal-more.md` (its golden steps go in `sheetmetal_ops.py` ONLY by appending at the end, in a block headed `# --- sm-more ---`) |
| plastic-1 | `sf/plastic-1` | `plastic_core.py`, `plastic.py`, `plastic_rules_ui.py`, `plastic_boss*`, `plastic_rest*` files, `icons_plastic.py`, `plastic_ops.py`, `plastic_schema.py`, `parity/plastic.md` |
| plastic-2 | `sf/plastic-2` | `plastic_snap*`, `plastic_lip*` files and any other plastic feature its brief names, `icons_plastic2.py`, `plastic2_ops.py`, `plastic2_schema.py`, `parity/plastic-2.md` |
| surface-3 | `sf/surface-3` | the `surface*` files, `icons_surface3.py`, `surface3_ops.py`, `surface3_schema.py`, `parity/surface.md` |
| surface-4 | `sf/surface-4` | `surfmod_*` files it creates; the surface-body changes in `split*.py`, `delete*.py`, `fillet_ui.py`, `move*.py`, `align*.py`, `pattern*.py`, `scale*.py`, `presspull*.py`; `icons_surface4.py`; a `# --- surface-4 ---` block at the END of `surface3_ops.py` / `surface3_schema.py`; `parity/surface-modify.md` |

- **Shared contracts (already on `develop`, written by the orchestrator):** `sheetmetal_core.py`
  (rules: fields, library, expressions, bend maths) and `sheetmetal.py` (where a design keeps its
  rules, which body is sheet metal and its rule: `rule_for_body(body)`), `plastic_core.py` and
  `plastic.py` (the same for plastic rules: `default_for(body, field)` for the existing tools, `rule_for_body(body)` for the plastic ones). sm-flat and sm-more only *call* the sheet metal
  contract; if they need a change in it, they say so in their report and add what they need in
  their own files. sm-forming may extend the contract but never rename or remove what is in
  it. The same for plastic-2 and plastic-1.
- **Reusing a sibling's work in progress:** worktrees share one repository, so a sibling's
  branch is visible. You may `git merge sf/<sibling>` into your own branch when you need code
  it has committed (sm-more needs sm-forming's edge flange code for Hem; sm-flat needs real
  flanges to unfold). Never commit to a sibling's branch, never rebase.
- **Ribbon:** `ribbon_config.py` already has the SHEET METAL and PLASTIC tabs and the SURFACE
  tab in Fusion's order (only sm-flat edits `ribbon_ui.py` and adds the FLAT PATTERN tab to `TABS`), with every new command present but greyed (`None`) and labelled with
  the builder that owns it in a `# owner:` comment. Change only your own lines: the command
  name, the icon, the note. Keep the order.
- **Icons:** draw yours in your own `tools/sciforge/icons_<area>.py` (make_icons.py runs every
  `icons_*.py` in its namespace, so `@icon("name")`, `block`, `path`, `rect`... work there),
  then run `python3 tools/sciforge/make_icons.py` and commit your new `.svg` files. Never edit
  make_icons.py. Original artwork only (outline 0.7), in the style of the existing icons.
- **Golden models:** your `*_ops.py` and `*_schema.py` already exist (empty) and are imported by
  `core.py` / `schema.py`; fill them. Golden models `SciForgeTests/golden/models/<area>_*.json`.
- **Scenarios:** `SciForgeTests/gui/scenarios/<area>_*.py` with real clicks (feature-guide).
  Helpers in your own `SciForgeTests/gui/<area>_steps.py`.
- **Machine:** 4 CPUs shared by seven builders. Run one scenario at a time; re-run a timeout
  alone before you conclude anything. FreeCAD 1.1.4 is unpacked at
  `/home/user/SciForge-Parametric-Design/.sciforge-cache/freecad` (pass it with `--freecad`;
  do not download another copy). Use your own `--out` folder.
- **Web:** WebFetch cannot reach any host in this sandbox; WebSearch works (its result
  excerpts). Research what the research files leave open with WebSearch; mark guesses G.
- **Time:** check `date -u`. Commit working increments at least every hour (a builder that
  runs out of time must leave a branch that passes its tests). **Stop building at 10:40 UTC**:
  from then on only finish tests, docs and the report; be done by 11:00 UTC.
- **Scope honesty:** build everything your brief lists. Where OpenCASCADE or FreeCAD cannot do
  what Fusion does, build the closest honest behaviour, refuse the rest in the dialog with the
  reason, and list it in your parity doc's Known gaps with the evidence. Never ship a silent
  wrong result.
- Your session log goes to `docs/sciforge/sessions/<area>.md` (never MEMORY.md).
- Report (your final message): branch, commits, every command you built with its options,
  each scenario with its check count and PASS/FAIL, golden models, unit tests, gaps with
  reasons, and a plain-language "how to use it" for Luca (a beginner).
