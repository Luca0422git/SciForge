<!-- A copy of docs/sciforge/dev/cadcraft-lessons.md for AI models, made by tools/sciforge/make_ai_docs.py: edit the original, then run the script. -->

# What SciForge can learn from CADCraft

**Written:** 2026-10-21 · **Source studied:** github.com/storytold/cadcraft (cloned 2026-10-21,
commit 54d9683; read only, nothing of it was built or run) · **Asked by:** Luca ("Learn as MUCH
as you can from it and draft some ideas as to how we can improve SciForge").

## What CADCraft is

An AutoCAD-style **2D drafting** app (command line, object snaps, layers, dimensions, DXF/DWG,
layouts and PDF plotting), written from scratch in Rust (about 190,000 lines, 2,100 tests), by
the ArtCraft team. Early development: they rate themselves "pre-alpha", about 40% of AutoCAD.
It is not a 3D parametric modeller, so it has nothing to teach SciForge about solids, the
timeline or joints. What it does well is the **craft around the features**: how every action
is a scriptable command, how AI agents drive and check it, how its sketch solver explains
itself, how it tells the user what a file export loses, and how it measures its own progress.

Licence: MIT or Apache-2.0, so ideas and even code may be reused with credit (a line in
`docs/sciforge/core-patches.md`-style notes and the file header). Almost all of it is Rust, so
in practice we borrow designs, not code.

SciForge already has several things CADCraft is proud of, sometimes in a better form: an MCP
server and a local AI bridge (ours is off by default, needs a key and asks Allow/Deny; theirs
has no password), Fusion-style Scripts and Add-Ins, a crash log with a "closed unexpectedly"
notice, an update check, golden models, about 400 GUI scenarios in CI. Those are not repeated
below.

## The ideas, best first

Effort: S = a session or less, M = a few sessions, L = a project of its own.

### 1. Sketch constraints that explain themselves (M)

CADCraft's solver (`crates/constraints`) never leaves a drawing broken and always says why.

- **Name the culprits.** Today SciForge says "it does not fit the sketch's other constraints"
  (`sketch_constrain_tools.py`). FreeCAD's solver already returns which constraints conflict
  (`ConflictingConstraints`, `RedundantConstraints`): say "conflicts with the Horizontal on
  Line 2 and the 30 mm dimension" and highlight those two in the sketch for a moment.
- **Fully constrained, visible.** Fusion shows a padlock on a fully constrained sketch in the
  browser and turns its curves black. SciForge colours curves but has no padlock or count. Add
  the padlock (browser and timeline) and, optionally, a small "2 left to define" note in the
  Sketch Palette.
- **Inferred constraints in priority order.** SciForge already drops inferred constraints that
  conflict (`sketch_infer.py`), but all at once. CADCraft adds them one by one, strongest first
  (coincident, concentric/tangent, horizontal/vertical, collinear, perpendicular only where the
  lines touch, parallel and equal last), so a weak guess never pushes out a strong one.
- **Move as little as possible.** When a dimension changes, the curve you just edited stays
  put and the rest moves (CADCraft weights the first pick 10,000 times heavier). FreeCAD's
  solver can be steered the same way with temporary block constraints.
- **Parameters checked on a trial copy.** CADCraft refuses a parameter change that would make
  any constraint fail (a negative length, a cycle), instead of applying it and leaving red.
  Change Parameters could do the same and say which dimension would break.

### 2. "Not saved in this file" reports on export (S)

CADCraft never drops data silently: when a DWG cannot hold something it says "Not saved in
the DWG file: 3 3D solids, ..." and the scripted call returns the list too
(`crates/engine/src/cmd/file.rs`). SciForge exports drawings to DXF/PDF and designs to
STEP/STL/3MF: each export could list what the target format cannot keep (appearances in STEP,
sketches and the timeline in STL, GD&T frames or associative dimensions in DXF), in one
non-blocking message. Importing could do the same ("skipped: 2 unsupported entities").

### 3. Give AI agents more to do, and ways to check their own work (M)

SciForge's MCP server offers 16 tools while the ops layer (`sciforge/ai/ops`) can build far
more. From CADCraft (`crates/mcp`, `docs/mcp.md`):

- **Expose the whole ops layer**: sweep, loft, joints, patterns, surfaces, drawings. One
  catalogue (id, label, ribbon path, parameter schema, "enabled, or why not") feeds the MCP
  tool list, the in-app assistant and the docs.
- **Checking tools**: `inspect_design` (bodies valid?, volume, area, bounding box, faces per
  feature, steps that failed) and `query_faces` by selector, so an agent confirms numbers
  before trusting a picture; `render` returning the image itself (not just a file path).
- **MCP resources**: the design summary and the command catalogue as readable resources.
- **Honest retries**: after a lost reply, re-send only read-only calls; for a change, tell the
  agent "may or may not have been applied, inspect first" (CADCraft does exactly this).
- **An agent end-to-end test**: build a part only through MCP (sketch, extrude, fillet,
  undo) and check it only through MCP, in CI (their `agent_draws_a_plate_with_holes`).
- **Docs that cannot drift**: a test that the tool table in the docs equals `tools/list`.

### 4. A command-line SciForge (M)

`cadcraft-cli` opens, converts and scripts drawings without a window: `info FILE` (JSON
summary), `convert IN OUT.step|stl|pdf`, `run FILE --op 'extrude {...}' --save --export`,
`commands` (the catalogue). SciForge can do the same on top of FreeCAD's command-line mode and
the golden-model runner: batch conversions for Luca, scripted checks in CI, and a headless
backend for the MCP server.

### 5. Measure progress with a script, keep one work list (S)

CADCraft's one number that never goes stale is generated: a script compares the registered
commands with AutoCAD's menu tree (names only, recorded by hand) and writes
`docs/parity-checklist.md` "do not edit by hand" (58% of 491 menu items). Their hand-kept
numbers already disagree between documents. For SciForge:

- record Fusion's ribbon and menu tree by name (`tools/sciforge/data/fusion-menus.txt`), and
  have a script compare it with SciForge's ribbon commands and write the checklist;
- keep `docs/sciforge/dev/remaining-gaps.md` as **the** work list: one row per gap, ranked,
  closed or narrowed in the same commit that fixes it;
- a short "alpha gate" of five Fusion workflows Luca does every day, each marked "works end to
  end: yes / partly / no" with evidence.

### 6. Faster and smoother on big models (M-L)

From `crates/render` and `crates/engine/src/spatial.rs`:

- **Cache by identity, not by revision**: keep tessellations and pick indexes keyed by the
  shape's identity (as SciForge started doing with `shape_checks`), so undo reuses them.
- **Rebuild in the background**: keep drawing the old picture while the new one is built, then
  swap (their pan/zoom stalls on a huge file went from 2-4 s to 26-64 ms).
- **Detail by zoom**: simplify what is too small to see (fine hatching in drawings, tiny
  faces); full detail for printing.
- **A speed readout** in the benchmark that fails when a measured action gets much slower.

### 7. Better PDFs from drawings (M)

CADCraft's PDF writer (`crates/io/src/pdf.rs`): layers you can switch on and off in the PDF
viewer (visible edges, hidden edges, dimensions, hatches, title block), text that can be
searched and copied (embedded font subsets, respecting font licences), links. SciForge already
merges sheets into one PDF; layers and searchable text are what a manufacturer notices.

### 8. Safer crashes and better bug reports (S)

SciForge has crash logs; two additions: a **plain running log** in a fixed place that rotates
(`sciforge.log`, `.1`, `.2`, capped size) so the log of a run that went wrong survives the next
start and can be attached to "Report a Problem"; and **hostile-input tests** for importers and
sketch inference (NaN, huge numbers, empty files) with seeded random cases, as CADCraft does
for its geometry (`crates/geom/src/property_tests.rs`). Their rule "every crash fix lands with
a test that reproduces it" is worth adopting word for word.

### 9. Accessibility (S-M)

CADCraft labels every icon-only button for screen readers, shows a visible keyboard focus and
follows Windows' "reduce motion" setting (no animated transitions). SciForge sets an accessible name
in only three places. A pass over the ribbon, timeline and browser (name = tooltip text)
is cheap; animated camera moves could follow the system setting.

### 10. Translations (L)

CADCraft ships 16 languages from simple tables (English text, translation), translated only
where text is shown, so files, scripts and AI tools stay in English; one language is checked
for completeness, the others are "as far as they go", each marked "AI-assisted, not yet
proofread". SciForge's own text is English only. Worth doing once the beta has users who ask.

### 11. Agents that look at the interface (M)

CADCraft's agents verify UI work by asking the running app for a screenshot and a list of its
widgets (name, role, position, enabled, focused) and clicking by name. SciForge's GUI
scenarios drive Qt directly; a widget list over the AI bridge would let agents check ribbon,
dialogs and timeline the same way, and would make some scenario code shorter.

### 12. Smaller ideas

- **Panel layout that cannot break**: every layout change validated before it is applied, the
  3D view can never be closed, closed panels reopen where they were, a damaged layout file
  falls back to the default with a message.
- **Ribbon overflow**: ribbon groups that do not fit go into a "..." menu instead of being cut.
- **Theme tokens**: one table of interface colours for dark and light, kept apart from the 3D
  view's colours.
- **Rules for agents**: "programmatic calls never open dialogs", "unfinished options say 'not
  available yet' instead of failing", "edit only the files your task owns" when agents run in
  parallel.

## What not to copy

- The command line, AutoLISP and AutoCAD aliases: Fusion has none of them; SciForge follows
  Fusion.
- A properties panel for selected objects: useful, but Fusion has none (SciForge hides
  FreeCAD's on purpose). Only if Luca wants to go beyond Fusion.
- The web build and the Rust rewrite: different technology from FreeCAD's.
- Their snapshot undo (the whole drawing kept as shared pieces): elegant, but FreeCAD's undo is
  built in and works; not worth replacing.

## Suggested order

1, 2 and 5 first (sketch messages, export reports, progress script: visible to Luca, small);
then 3 and 4 (agents and command line: they make every later task faster to build and check);
then 6 and 7; 8 and 9 alongside; 10 and 11 when there is time.
