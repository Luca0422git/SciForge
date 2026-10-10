export const meta = {
  name: 'sciforge-fusion-features',
  description: 'Build every missing Fusion SOLID/SKETCH feature in SciForge in isolated worktrees, then have a second agent attack and fix each one',
  whenToUse: 'SciForge: implement Fusion-style features with click-driven scenario tests and adversarial QA',
  phases: [
    { title: 'Build', detail: 'one agent per feature, own git worktree and branch sf/<key>' },
    { title: 'Break and fix', detail: 'a fresh agent attacks each feature like a demanding Fusion user and fixes what breaks (branch sf/<key>-qa)' },
  ],
}

const S = args.scratch
const FC = S + '/fc'
const TRAILER = 'Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01DkiL5juAKFcjzVEsGXBPzX'
const FEATURES = args.features

const SHARED = [
  'sciforge/taskui.py', 'sciforge/commands.py', 'sciforge/config.py', 'sciforge/theme.py',
  'sciforge/workbench.py', 'sciforge/ribbon_ui.py', 'sciforge/shortcuts.py', 'sciforge/__init__.py',
  'sciforge/registry.py', 'sciforge/compat.py', 'SciForgeTests/gui/harness.py',
  'SciForgeTests/gui/smoke_gui.py', 'SciForgeTests/gui/journey_gui.py', 'tools/sciforge/run_tests.sh',
]

function ownershipTable(me) {
  return FEATURES.filter(f => f.key !== me.key)
    .map(f => '  - ' + f.key + ': ' + f.owns.join(', ')).join('\n')
}

const IMPL_SCHEMA = {
  type: 'object',
  properties: {
    branch: { type: 'string' },
    commit: { type: 'string', description: 'final commit sha on the branch' },
    summary: { type: 'string', description: 'what a Fusion user can now do, plain language' },
    commands_added: { type: 'array', items: { type: 'string' } },
    scenarios_added: { type: 'array', items: { type: 'string' } },
    golden_added: { type: 'array', items: { type: 'string' } },
    tests_run: { type: 'string', description: 'exact commands run and their PASS/FAIL counts' },
    all_tests_pass: { type: 'boolean' },
    known_gaps: { type: 'array', items: { type: 'string' }, description: 'Fusion behaviour not done, each with the reason' },
    shared_changes: { type: 'array', items: { type: 'string' }, description: 'files outside your ownership you changed, and why' },
    core_patches: { type: 'array', items: { type: 'string' } },
    shortcut_requests: { type: 'array', items: { type: 'string' }, description: 'Fusion keys that should run your commands, e.g. "F -> SciForge_Fillet"' },
  },
  required: ['branch', 'commit', 'summary', 'tests_run', 'all_tests_pass', 'known_gaps', 'shared_changes'],
}

const QA_SCHEMA = {
  type: 'object',
  properties: {
    branch: { type: 'string' },
    commit: { type: 'string' },
    bugs: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          title: { type: 'string' },
          how_found: { type: 'string' },
          fixed: { type: 'boolean' },
          scenario: { type: 'string' },
        },
        required: ['title', 'fixed'],
      },
    },
    tests_run: { type: 'string' },
    all_tests_pass: { type: 'boolean' },
    remaining_problems: { type: 'array', items: { type: 'string' } },
    summary: { type: 'string' },
    shared_changes: { type: 'array', items: { type: 'string' } },
  },
  required: ['branch', 'commit', 'bugs', 'tests_run', 'all_tests_pass', 'remaining_problems', 'summary'],
}

function common(f, stage) {
  const out = S + '/wf/' + f.key + '-' + stage
  return `
## Situation
SciForge is a fork of FreeCAD 1.1.4 being reshaped into Autodesk Fusion (repo: this git worktree, your cwd).
The owner, Luca, is a beginner programmer and an everyday Fusion user. His last two test sessions found
SciForge unusable: errors everywhere, a second extrude destroyed the part, Finish Sketch crashed. He said:
"make it work, make it all work, don't hold back, make it feature complete". The bar is now: a Fusion user
does the workflow with the mouse exactly as in Fusion and sees ZERO errors (Report view), zero pop-ups,
zero crashes. Green tests that do not click are worthless here.

## Before writing code (mandatory)
1. Read docs/sciforge/dev/feature-guide.md (the rules; each one cost a broken release).
2. Read MEMORY.md sections "Known issues / findings" and the latest session log.
3. Read the examples: src/Mod/SciForge/sciforge/{taskui.py, extrude_ui.py, extrude.py, presspull_ui.py,
   sketch_ui.py, profile_pick.py, commands.py}, src/Mod/SciForge/SciForgeTests/gui/harness.py,
   SciForgeTests/gui/scenarios/luca_session.py, SciForgeTests/golden/README.md.
4. Read the FreeCAD C++/Python of the PartDesign/Sketcher features you build on (src/Mod/PartDesign,
   src/Mod/Sketcher) to know their real properties and failure modes. Check property names in the
   running FreeCAD (freecadcmd below) instead of guessing.
5. You know Fusion well. You may use WebSearch/WebFetch on Autodesk's public Fusion help
   (help.autodesk.com) to confirm dialog fields and behaviour. Copy behaviour only, never wording,
   icons or code.

## Tools in this sandbox
- FreeCAD 1.1.4 unpacked at ${FC}. Headless Python: ${FC}/squashfs-root/AppRun freecadcmd script.py
- One scenario: tools/sciforge/run_tests.sh --freecad ${FC} --out ${out} --scenario <name>
- Golden models: tools/sciforge/run_tests.sh --freecad ${FC} --out ${out} --only golden
- Everything (~15 min): tools/sciforge/run_tests.sh --freecad ${FC} --out ${out}
- Screenshots land in ${out}; LOOK at them (Read tool) to check it looks and behaves like Fusion.
- Another agent runs GUI tests at the same time on this 4-CPU machine. If xvfb fails to start, retry.
- Black formatting, line length 100: ${S}/venv/bin/black --line-length 100 <files>
- Baseline at the start: everything passes except scenario ribbon_sweep's 2 known failures
  ("Shell" prints <Exception> Base feature's TopoShape is invalid when nothing is selected -> owned by
  shell_draft; "Circumscribed Polygon" opens a pop-up -> owned by sketch). Your branch must not add any
  failure anywhere. If you own one of those two, fix it.

## Ownership (other agents work in parallel on other branches; merges must stay conflict-free)
Files you own (create/edit freely; paths under src/Mod/SciForge unless absolute): ${f.owns.join(', ')}.
Plus your own new files (new modules, scenarios SciForgeTests/gui/scenarios/${f.key}*.py, golden models).
Other agents own (do NOT edit):
${ownershipTable(f)}
Shared files (do NOT edit, except a truly unavoidable minimal change you list in shared_changes):
  ${SHARED.join(', ')}.
Allowed small shared edits: one-line changes in sciforge/ribbon_config.py pointing an item at your
command (most items already point at ("SciForge_X", fallback)); append-only new ops in
SciForgeTests/golden/builder.py and schema.py; new rows in docs/sciforge/core-patches.md.
If you need a helper that would belong in taskui.py, put it in your own module.

## Git
Never push. Commit with clear messages ending with exactly these two lines:
${TRAILER}
Never put a model name/identifier in commits or files.`
}

function implPrompt(f) {
  return `You are one engineer on the SciForge team. Build this feature to Fusion parity.

# Feature: ${f.title}
${f.spec}
${common(f, 'build')}

## What done means
- Every command in your spec works from its ribbon button (and key, if any) with real mouse input,
  with Fusion's dialog fields, live preview, blue drag handles where Fusion has them, OK/Cancel/Esc,
  one undo step, edit again via timeline double-click (declare EDITORS = {...} in your *_ui.py),
  and errors shown inside the dialog (never in the Report view, never a pop-up).
- Scenario tests in SciForgeTests/gui/scenarios/${f.key}*.py that use ONLY real input
  (h.ribbon / h.press / h.click / h.drag / h.task_button) and check the resulting geometry exactly
  (volume/area/faces/bbox with hand-derived values), including: starting with nothing selected,
  starting with a valid selection, Cancel leaves the model unchanged, editing the feature again,
  undo/redo, and a second use of the same command.
- Golden models for new geometry (hand-derived expectations) where the builder can express it.
- The full suite (run_tests.sh with no --only) passes on your branch apart from the 2 known baseline
  failures you do not own. Run it at the end and report the exact numbers.
- Never fake parity: no silent no-ops, no buttons that pretend. If something is impossible in this
  FreeCAD after a real attempt, say so in known_gaps with the reason.

Start with: git checkout -b sf/${f.key}
End with: everything committed on sf/${f.key}; return the structured result.`
}

function qaPrompt(f, built) {
  return `You are SciForge's toughest tester and fixer: a demanding everyday Fusion user who also writes
excellent code. A teammate just built "${f.title}" on branch ${built ? built.branch : 'sf/' + f.key}.
Their report: ${JSON.stringify(built || { note: 'the build agent returned nothing; inspect the branch yourself' }).slice(0, 6000)}

# The feature spec they worked from
${f.spec}
${common(f, 'qa')}

## Your job
Start with: git checkout -b sf/${f.key}-qa ${built ? built.branch : 'sf/' + f.key}
(If that branch does not exist, the build failed: then build the feature yourself on sf/${f.key}-qa.)

1. Use the feature like Luca will. Write SciForgeTests/gui/scenarios/${f.key}_qa.py with at least 8
   realistic paths, beginner and power user, only real input: picks in the "wrong" order; OK with
   nothing picked; Esc in the middle of a pick; changing values while the preview runs; dragging
   handles far and negative; editing from the timeline twice; undo/redo afterwards; save to a temp
   .FCStd, close, reopen, edit again; combining with Create Sketch / Extrude / Press Pull before and
   after; running on a part made of several features; pressing another command's key while the
   dialog is open; whatever else Fusion users do with this feature. For each, decide what Fusion
   does and make the scenario check that.
2. Also compare against the spec: every field and behaviour listed must really exist and work. Missing
   pieces count as bugs.
3. Fix every bug at its root (code, not test tweaks), keep the teammate's scenarios passing, and make
   the screenshots look like Fusion.
4. Run the full suite at the end (no --only). It must pass apart from the 2 known baseline failures
   you do not own. Report exact numbers.
Commit everything on sf/${f.key}-qa and return the structured result.`
}

const results = await pipeline(
  FEATURES,
  (f) => agent(implPrompt(f), { label: 'build:' + f.key, phase: 'Build', schema: IMPL_SCHEMA, isolation: 'worktree' })
    .then(r => { log('built ' + f.key + ': ' + (r ? (r.all_tests_pass ? 'tests pass' : 'TESTS FAIL') : 'no result')); return r }),
  (built, f) => agent(qaPrompt(f, built), { label: 'qa:' + f.key, phase: 'Break and fix', schema: QA_SCHEMA, isolation: 'worktree' })
    .then(q => { log('qa ' + f.key + ': ' + (q ? (q.bugs.length + ' bugs, ' + (q.all_tests_pass ? 'tests pass' : 'TESTS FAIL')) : 'no result')); return { key: f.key, built, qa: q } }),
)
return results
