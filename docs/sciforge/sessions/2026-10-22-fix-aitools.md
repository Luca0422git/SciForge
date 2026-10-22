# 2026-10-22: fixes to the AI tools after the adversarial review (branch `fix/aitools`)

To be copied into MEMORY.md by whoever merges `fix/aitools` (this branch does not edit
MEMORY.md). Based on `integration` (3e515b5). No FreeCAD core file changed (nothing for
`core-patches.md`). All seven findings of the review reproduced on this branch and are fixed.

## In plain words (for Luca)

1. **An AI can no longer close or switch to the wrong design by name (F1).** Every open design
   has an id (unique, like `Part1`) and a name (what the tab shows, like `housing`). When an
   AI gave a text that was one design's id *and* another design's name, SciForge took the
   first one it found. In the review this closed the saved design "housing" (whose id was
   "Part") and threw away its unsaved fillet, while the AI meant the new design called "Part".
   Now such a text is refused and the answer lists both designs with the exact text to give
   for each ("give 'housing'", "give 'Part1'"). Nothing is closed or switched on a guess.
2. **One File Per Body never overwrites files without asking (F2).** An STL / 3MF / OBJ
   export with one file per body only checked the name you typed (`parts.stl`), but wrote
   `parts-Body1.stl`, `parts-Body2.stl`... over existing files. Now every file it will write is
   checked first: without the window the export is refused (unless the server was started with
   --allow-overwrite); in the window you are asked once, with the list of files.
3. **Editing a step with a wrong option name is refused instead of answering "Done" (F3).**
   `edit_step` with a misspelled name (`lenght`), a capitalised one (`Length`, `Radius`, as
   the "values" part of get_step spells them) or a shell's `thickness` used to be ignored for
   fillets, holes, shells, primitives and most other steps, and still said "Done" (sometimes
   with an empty Undo step). Now: capitalised names and spaces are understood (`Length` =
   `length`), a shell's `thickness` sets its wall the way the shell tool does, and a name the
   step does not have is refused with the list of names it has. An edit that changes nothing
   ("set the radius to what it already is") answers "No change" and adds no Undo step.
4. **After closing a design without the window, another open design becomes active (F4).**
   Command-line FreeCAD leaves no design active after a close, so every later tool said "No
   design is open" although others were. Now the newest open design becomes active (as the
   window does with its tabs) and the answer says which one. `close_design` with a design
   named also works when none is active.
5. **`~` means your home folder, and a path without its folder is refused (F5).** An AI that
   wrote `~/Desktop/part.step` got a folder literally named `~` inside SciForge's working
   folder. Now `~` is your home folder, and a path like `part.step` (no folder) is refused
   with a sentence asking for the whole path, because the AI cannot know which folder
   SciForge happens to run in. `sciforge-cli` keeps reading such paths from the folder where
   you typed the command, as any command-line program does.
6. **`sciforge-cli` messages name its own option, and a bad `--tool` exits with 2 (F6).** The
   refusal said "--allow-overwrite" (the MCP server's option); on the command line it now says
   "add --force to the command to replace it". A `--tool` whose arguments are not JSON, or a
   `--tools-file` item without a tool name, now exits with status 2 ("bad command line", as
   documented) and says what is wrong, before FreeCAD even starts.
7. **The step names get_timeline shows work everywhere (F7).** `extrude {"profile": "Sketch
   1"}` (the timeline's name, with the space) used to fail with "there is no step called
   'Sketch 1'" while `edit_step` took the same name. Now the design-step tools look the name
   up and use the step's id (`Sketch1`), at no cost for calls that use ids.

## What was changed (for the next session)

- `sciforge/ai/actions/document_actions.py`: `_find_design()` collects every design whose id,
  name, file name or file path (absolute) is the text; one match is used, several are refused
  with `_handle()` (the shortest text naming that design alone; `id:<id>` when nothing else
  does, and `id:<id>` is always accepted). `close_design`: when no design (or a closed one) is
  active afterwards, `ctx.host.show_document(others[-1])`; the answer gives the new active
  design's name and id. `_check_overwrite(ctx, paths)` takes a list and asks once
  (`host.confirm_overwrite(list)`); `_mesh_files()` lists what `export.export_mesh_files`
  writes (`export.body_file_names` when per body with several bodies).
- `sciforge/ai/executor.py`: `Context.full_path()` (expanduser; relative refused unless the
  host has `relative_base`), used by save / save_as / open_design / export / import_file /
  export_drawing. `Host.overwrite_option` / `relative_base`; `refuse_overwrite_text` takes a
  list and, for the command line, says "add --force to the command". `Context.build()`: on a
  KeyError (an id the steps did not find) `_ids_for_names()` swaps the timeline name / label
  for the id in the arguments (not in label / name / text / value fields) and builds again,
  up to 8 names; the failed try is taken back (no Undo step).
- `sciforge/ai/headless.py`: `HeadlessHost(allow_overwrite, overwrite_option, relative_base)`.
  `sciforge/ai/cli.py`: `read_calls()` parses `--tool` / `--tools-file` before FreeCAD is
  needed (exit 2 on a bad one); the host gets `--force` and the current folder.
- `sciforge/ai/bridge.py` (the window): `_confirm_overwrite` / `refuse_overwrite_text` take a
  list of files (one question naming them all).
- `sciforge/ai/actions/timeline_actions.py`: `_option_keys(obj, kind)` (the option names an
  edit takes, from the step module's own `read()`, plus the extra keys each `*_edit` op
  reads: refs for modify_edit, `type` for patterns, HARDWARE_KEYS, MOVE_KEYS...; None for a
  kind it cannot list), `_checked_changes()` (case / space-insensitive mapping, shell
  thickness -> inside / outside by direction, unknown names refused), `_edit_state()` +
  `_Unchanged` (definition, formulas, own shape, every solid equal before and after: the
  transaction is aborted and the answer is "No change ... (no Undo step)", not an error).
- Catalogue texts: close_design (needs nothing; ambiguity; another design becomes active),
  switch_design, edit_step (names refused, values spellings, shell thickness, extrude distance
  keeps its side: flip reverses). AI docs regenerated; the recorded close_design example
  re-recorded (it showed the F4 bug: "No design is open now" with Example still open).

## Tests

- Headless (`SciForgeTests/headless/runner.py`, `FIX_SESSION` after `SESSION`): F1 refusal
  with both handles, switch by name / `id:` / file name, nothing closed; F3 unknown names
  refused with no Undo step, `Radius` / `Length` / shell `thickness` work, "No change" adds no
  Undo step; F7 `extrude "Sketch 1"`; F2 second per-body export refused; F5 relative path
  refused, `~` with HOME set to the test folder, no `~` folder; F6 command-line host (relative
  path from its folder, "add --force"); F4 the answer names the design that is active.
- Unit (`test_ai_catalog.py`): bad `--tool` / `--tools-file` exit 2 with the reason;
  close_design needs nothing.
- Agent end to end (`agent_e2e.py`, real `sciforge-cli`): convert over an existing file says
  "add --force", a bad `--tool` exits 2.
- GUI scenario `ai_tools_gui` Path 8: per-body overwrite asks once naming both files, denied
  writes nothing, allowed replaces both; a name that is another design's id is refused with
  both ids; closing a design names the active one.

## Left as it is

- An extrude edit with a negative `distance` keeps the side the extrude goes to (`flip: true`
  reverses it). That was the intended design; the catalogue text now says so.
