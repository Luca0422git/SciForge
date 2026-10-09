# SciForge: instructions for Claude sessions

SciForge is a fork of FreeCAD that aims for Autodesk Fusion-level parametric CAD.

Before doing anything else in a session:

1. Read `MEMORY.md` (progress, decisions, known issues, what is next).
2. Read `docs/sciforge/feature-outline.md` (the spec; sections 0-5 are mandatory).
3. At the end of the session, update `MEMORY.md` (status checkboxes, findings, session log).

Rules that are easy to forget:

- New code goes in `src/Mod/SciForge/`. Any change to FreeCAD's own files gets a `SCIFORGE:`
  comment and an entry in `docs/sciforge/core-patches.md`.
- Every SciForge log line is prefixed `[SciForge]`. Never let an exception escape a command,
  timer or event handler.
- The owner is a beginner: explain changes in plain language.
- Real FreeCAD can run in the sandbox: `tools/sciforge/get_freecad.sh` then
  `tools/sciforge/run_tests.sh` (unit tests, golden models, GUI smoke test under xvfb).
- Copy Fusion's behavior, never its assets, wording or code.
