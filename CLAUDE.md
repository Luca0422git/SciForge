# SciForge: instructions for Claude sessions

SciForge is a fork of FreeCAD that aims for Autodesk Fusion-level parametric CAD.

Before doing anything else in a session:

1. Read `MEMORY.md` (progress, decisions, known issues, what is next).
2. Read `docs/sciforge/feature-outline.md` (the spec; sections 0-5 are mandatory).
3. At the end of the session, update `MEMORY.md` (status checkboxes, findings, session log).

Rules that are easy to forget:

- Work on and push to the `develop` branch (Luca's choice), whatever branch name the session
  was given. Do not open pull requests unless Luca asks.
- `Release` holds released builds only: it is fast-forwarded to a tested `develop` commit, and
  tagged `sciforge-v<version>`, only when Luca gives the green light for that release. Never
  commit to it directly or force-push it (`docs/sciforge/dev/briefs/beta-release.md`).
- Bug fixes in SciForge's own files go out as **patch releases** (no 4-hour build): set the next
  number in `src/Mod/SciForge/VERSION` (`0.1.0-beta.2` -> `0.1.0-beta.2.1`) and its
  `_FALLBACK_VERSION`, add its CHANGELOG section, push `develop`; when the tests are green Luca
  runs Actions > SciForge patch release, which tags, publishes and moves `Release` itself
  (`docs/sciforge/patch-release.md`).

- New code goes in `src/Mod/SciForge/`. Any change to FreeCAD's own files gets a `SCIFORGE:`
  comment and an entry in `docs/sciforge/core-patches.md`.
- Every SciForge log line is prefixed `[SciForge]`. Never let an exception escape a command,
  timer or event handler.
- The owner is a beginner: explain changes in plain language.
- Real FreeCAD can run in the sandbox: `tools/sciforge/get_freecad.sh` then
  `tools/sciforge/run_tests.sh` (unit tests, golden models, GUI smoke test under xvfb).
- Copy Fusion's behavior, never its assets, wording or code.
