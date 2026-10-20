# Brief: SciForge 0.1.0-beta, the first public release

For a new Claude session. Written 2026-10-20 at Luca's request ("Make an extremely detailed
outline for a new instance so it can work on that"). Read `CLAUDE.md`, `MEMORY.md` and
`docs/sciforge/feature-outline.md` sections 0-5 first, as always. Then this whole brief before
writing any code.

---

## 0. Luca's decisions (fixed, do not re-ask)

| Topic | Decision (Luca, 2026-10-20) |
|---|---|
| Version | **0.1.0-beta** (the first public build). Later betas: `0.1.0-beta.2`, `0.1.0-beta.3`...; the first non-beta is `0.1.0` |
| Installer | Luca installed the CI `...-installer.exe` on Windows: "it worked fine. no issues there". The full build is proven; do not redo it unless the C++ side changes |
| Code signing | **None.** "I dont have $10 a month just laying around." Windows SmartScreen will warn ("Windows protected your PC"); **explain it** on the GitHub page and in the release notes, with the exact clicks |
| GitHub page | "A fledged out github page is definetly needed" |
| Updates | "update checks with an easy install is also a must" |
| First-run welcome | Wanted, but **small**: "the whole point of sciforge is that its supposed to feel like fusion for those who like fusion. so dont overdo it." No tour, no wizard, no modal dialog at start |
| Everything else proposed | "sounds great": version + beta label, Report a Problem, crash log, known issues, AI privacy note, licence/credits check, Fusion-name hygiene, issue templates, feedback channel, small closed beta first |
| Paid services | None. Everything here must be free (GitHub's free tier for public repos covers Actions and Releases) |

## 1. Branches and the release flow (new rule)

Luca: "Make a branch called "Release". thats where we will put the releases after we test on
develop. So everything goes on develop until i give the green light".

- **All work goes to `develop`**, as `CLAUDE.md` says (this brief's session too, whatever
  branch name the session was given). Push to `develop` in batches (a push cancels the CI run
  in progress, MEMORY: sandbox rules).
- **`Release`** (capital R) exists since 2026-10-20 (made from `develop` at `a6a5f7bd`). It only
  ever receives **tested `develop` commits, on Luca's explicit green light** for that release.
  Never commit to `Release` directly, never push to it without that green light in the
  conversation, never force-push it.
- A release = fast-forward `Release` to the `develop` commit Luca approved
  (`git push origin <commit>:Release`; it must be a fast-forward), then tag that commit
  `sciforge-v0.1.0-beta` and push the tag. The tag starts `sciforge-build.yml` (already
  triggered by `sciforge-v*` tags), which builds and (after R3 of this brief) publishes the
  GitHub Release.
- If `Release` and `develop` ever diverge (a hotfix), ask Luca; never rewrite either branch.
- This rule is already in `CLAUDE.md` and in `MEMORY.md`'s Decisions log (2026-10-20).
- Do not open pull requests (Luca's standing rule).

## 2. What exists already (do not rebuild it)

| Piece | Where | State |
|---|---|---|
| Full build (Windows installer, portable .7z, Linux AppImage) | `.github/workflows/sciforge-build.yml` (manual or `sciforge-v*` tag) | Works; Luca installed the installer. **Uploads artifacts only, publishes no GitHub Release** (`permissions: contents: read`) |
| Tests on every push | `.github/workflows/sciforge-tests.yml` (base, Windows golden, 4 scenario shards, `quick-update` artifact) | ~75 min; a shard has a 90 min limit |
| Module-only update | `tools/sciforge/install_update.ps1` / `.cmd`, docs `docs/sciforge/quick-update.md` | Finds the installed SciForge, asks for admin, backs up to `SciForge-backups\<date>`, stops SciForge's own `python.exe` (the AI connector), logs to `install_update.log` |
| App identity | core patches #8-#13 (`docs/sciforge/core-patches.md`): `SciForge.exe`, `%APPDATA%\SciForge`, own icon/splash/About, own installer keys, FreeCAD credited in Help > About | Built and installed |
| Version | `src/Mod/SciForge/sciforge/__init__.py`: `__version__ = "0.2.0"` (an internal number; becomes `0.1.0-beta` in R0); `sciforge/build_info.py` (COMMIT, DATE) is written by the quick-update packaging | Shown in SciForge > Diagnostics |
| Diagnostics | `sciforge/diagnostics.py` (`report()`), command `SciForge_Diagnostics`; `sciforge.RECENT` keeps the last 200 `[SciForge]` messages | Text you can copy |
| Recovery | `versions_ui.recovery()`, Home's recovery banner | Unsaved work after a crash is offered back |
| Home tab | `sciforge/home_ui.py` (rows of places, AI column, recovery banner) | The welcome strip goes here |
| Cheat sheet | `docs/sciforge/cheat-sheet.md` | Exists; link it |
| Example design | `docs/sciforge/examples/pi5-case/` | Can be the "open an example" link |
| GitHub templates | `.github/ISSUE_TEMPLATE/` (`config.yml`, `PROBLEM_REPORT.yml`, `BACKPORT_REQUEST.yml`), `.github/FUNDING.yml`, `.github/pull_request_template.md` | **Still FreeCAD's**: they send people to FreeCAD's forum, issue tracker and donation pages. Replace (R1) |
| README.md | repo root | **FreeCAD's README** with a 4-line SciForge banner on top. Replace (R1) |
| Known issues | MEMORY.md "Known issues / findings" (long, developer-facing) | Needs a short user-facing list (R1) |

Before starting, skim `MEMORY.md`'s newest session logs (Home/cloud/AI, merge, origin squares)
so you know what changed most recently.

## 3. Milestones (each one: tests green, pushed to `develop`, Luca told what to try)

Work in this order. Each milestone ends with a quick-update zip sent to Luca (see MEMORY:
"Zip" for the layout) so he can try it without waiting for CI, plus plain-language notes on
what to try.

### R0. Groundwork (small)

1. **Version.** `__version__ = "0.1.0-beta"` in `sciforge/__init__.py`. Everything that shows
   a version reads it from there (Diagnostics, the MCP server's `version`, About, the update
   check). Grep for other hard-coded versions (`0.2.0`) and for code that parses
   `__version__` as numbers only.
2. **One place for the version rules**: a pure module `sciforge/version_core.py`:
   - `parse(text)` -> comparable key; follows semver ordering:
     `0.1.0-beta < 0.1.0-beta.2 < 0.1.0-beta.10 < 0.1.0-rc.1 < 0.1.0 < 0.1.1-beta`;
     accepts a leading `v` or `sciforge-v` (tag names);
   - `newer(a, b)`, `is_prerelease(v)`, `tag_for(v)` -> `sciforge-v0.1.0-beta`;
   - unit tests in `SciForgeTests/unit/test_version_core.py`, covering every ordering above
     plus junk input (returns None, never raises).
3. **The C++ / installer side shows it too.** The splash and Help > About show a version that
   comes from the C++ build. Find where (core patch #8 mentions `SplashInfoPosition`;
   `src/Main`, `src/Gui/Splashscreen.cpp`, the CMake version variables) and make them read
   **SciForge 0.1.0-beta** ("based on FreeCAD 1.1.4" in About). The NSIS installer's displayed
   version and the uninstall entry too (`package/WindowsInstaller/`). This is a C++/CMake
   change: tag it `SCIFORGE:`, add a row to `docs/sciforge/core-patches.md`, and it only takes
   effect in a full build (fine: the release needs one anyway). Keep the single source of
   truth idea: e.g. a `SCIFORGE_VERSION` CMake variable set from one file
   (`src/Mod/SciForge/VERSION` holding `0.1.0-beta`) that the Python side reads too. Verify in
   `check_install.sh` that the file is installed.
4. **Beta label in the UI, quietly** (Fusion shows nothing like this, so keep it small):
   Home's heading line gets a small grey "0.1.0-beta" after "SciForge"; Diagnostics and About
   show it. No banner, no title-bar text.
5. **Clean FreeCAD leftovers in `.github/`** that point users at FreeCAD: `FUNDING.yml`
   (delete it, or leave only a comment: Luca has no donation page), `BACKPORT_REQUEST.yml`
   (delete), `pull_request_template.md` (replace with a short SciForge one or delete; PRs are
   not used). Keep `.github/labels.yml` only if the labels make sense for SciForge.

Tests: unit tests for `version_core`; `misc_preferences`/`restart_gui` style check that Home
and Diagnostics show `0.1.0-beta`.

### R1. The GitHub page and the user-facing docs

**README.md** (repo root) becomes SciForge's page. FreeCAD's README moves to
`README.FreeCAD.md` (keep it: credits), linked from the new one. The new README, in this
order:

1. Title, one-line pitch in our own words, e.g. *"Parametric CAD that works the way Fusion
   users expect, free and open source (based on FreeCAD)."* Beta badge text: "0.1.0-beta".
2. One large screenshot (Home tab) and 3-4 smaller ones (sketching with the palette, the
   timeline, Press Pull with its arrow, the AI panel). Make them with the GUI harness on the
   real sandbox FreeCAD (scenarios already take screenshots with `h.shot`; write a small
   `tools/sciforge/screenshots.sh` that runs a dedicated scenario
   `SciForgeTests/gui/scenarios/readme_shots.py` and copies the PNGs to
   `docs/sciforge/images/`). Dark look. Crop to the window. **Check every image yourself
   before committing** (the 3D view renders with Mesa under xvfb; if a view comes out blank,
   say so and ask Luca for his own screenshots instead).
3. **Download**: a big link to the latest release
   (`https://github.com/Luca0422git/SciForge/releases/latest` does not show prereleases;
   use `.../releases` until 0.1.0 is out, and say "pick the newest at the top"). Which file
   to take: `...-installer.exe` (Windows, recommended), `...-Windows-...7z` (portable, no
   install), `...AppImage` (Linux). System requirements: Windows 10/11 64-bit or Linux x86-64;
   a graphics card with OpenGL 3.3 (FreeCAD's own requirement; check the FreeCAD 1.1 docs and
   cite them); about 2 GB of disk; no macOS.
4. **"Windows protected your PC"**: a section with a screenshot-like description of the exact
   clicks: *More info* -> *Run anyway*. Why it appears (the installer is not signed with a
   paid certificate; SciForge is free and open source; the checksum to verify the download:
   the `SHA256` file next to each download and the PowerShell command
   `Get-FileHash .\SciForge_...-installer.exe`). Antivirus false positives: what to do.
   Same text goes into each release's notes (R3 template). Plain and calm; no blame on
   Microsoft.
5. **First steps** (short): open SciForge, the Home tab, New design, the ribbon works like
   Fusion's, the S key search, link to the cheat sheet (`docs/sciforge/cheat-sheet.md`) and
   to "Fusion to SciForge" if it exists (outline 7.17 lists it; if not, the cheat sheet is
   enough for the beta).
6. **What works / what does not yet** (user-facing, short): the big features list
   (sketches, extrude/revolve/sweep/loft, Press Pull, fillets, holes and threads, patterns,
   components and joints, surfaces, mesh, drawings, 3D print / slicer, hardware library,
   AI connectors) and a link to **Known issues** (`docs/sciforge/known-issues.md`, new: 10-20
   lines a user cares about, from MEMORY's "Known issues", e.g. the OverlayRight frame outline,
   chat answers not streamed, English only, no macOS, not all of Fusion's features; each with
   a workaround if there is one).
7. **Updating**: SciForge checks for updates itself (R3); manual way: download the new
   installer, or the quick update.
8. **Reporting problems**: Help > Report a Problem (R2) or the Issues tab; what to include.
   Questions and ideas: GitHub **Discussions** (Luca has to switch it on: repo Settings >
   General > Features > Discussions; tell him the clicks, you cannot do it).
9. **Privacy**: a short section + `docs/sciforge/privacy.md`: SciForge sends nothing anywhere
   by itself except the update check (R3: one request to `api.github.com`, can be switched off
   in Preferences); the AI features only talk to the AI service the user connects, keys are
   stored on the user's computer (`secrets_store.py`: DPAPI / Keychain / Secret Service);
   cloud places are just folders synced by the user's own cloud app. No telemetry, no
   accounts. Verify every sentence against the code before writing it.
10. **Building from source** (one paragraph, link to `docs/sciforge/README.md`).
11. **Licence and credits**: LGPL-2.1-or-later (link `LICENSE`), based on FreeCAD (link,
    thanks, "not FreeCAD and not endorsed by the FreeCAD project"), the anvil artwork is
    SciForge's own.
12. **Trademark note**: "SciForge is not affiliated with or endorsed by Autodesk. Autodesk and
    Fusion are trademarks of Autodesk, Inc." Use "Fusion" only to say who it is for ("if you
    know Fusion, you know SciForge"); never in a heading as a product claim, never Autodesk's
    logo, colours or screenshots. The current banner's "working toward Autodesk Fusion-level
    modeling" goes.

Also in R1:

- **Issue templates** (`.github/ISSUE_TEMPLATE/`): `bug_report.yml` (what happened, what you
  expected, steps, the Diagnostics text box marked required, the SciForge version, Windows or
  Linux, attachments hint: the report file from R2), `idea.yml` (short), `config.yml`
  (`blank_issues_enabled: false`; contact link to Discussions for questions). Labels used:
  `bug`, `idea`, `beta`.
- **`docs/sciforge/README.md`** (the developer start page) gets a "Releases" line pointing to
  this brief and the release flow.
- A **`CHANGELOG.md`** at the root (user-facing, newest first; `0.1.0-beta` = "first public
  beta" with the big features list). Each later release adds a section; the release notes
  (R3) are generated from it.

Tests: none for prose, but run a link check (a tiny script: every relative link in README,
known-issues, privacy, CHANGELOG resolves to a file in the repo).

### R2. Report a Problem + crash log

Goal: when something goes wrong, a tester can send a useful report in one minute, and nothing
is ever sent without them seeing it.

**Crash log** (`sciforge/crashlog.py`, pure parts in `crashlog_core.py`):

- At SciForge start (the earliest SciForge hook that runs: `InitGui.py` / `shell.startup`;
  check which runs first) enable `faulthandler` into
  `<user data>/SciForge/crash/session-<date-time>.log` (`App.getUserAppDataDir()`; the file
  stays open for the session; keep the newest 5 files, delete older).
- Also chain `sys.excepthook` (log uncaught Python exceptions to the same file and to
  `RECENT`; call the previous hook).
- A "session running" marker file; removed on a clean exit (`App` close / workbench
  deactivate path that runs at quit: find it; MEMORY notes how Home handles "the window
  closes"). At the next start, a marker still present and a non-empty log = the last session
  crashed.
- After a crash: one line on Home, next to the recovery banner (reuse its look): "SciForge
  closed unexpectedly last time. [Report it] [Dismiss]". No popup.
- Never let an exception escape (CLAUDE.md rule); the crash log must never stop SciForge from
  starting (wrap everything; if the folder is not writable, skip silently with one `[SciForge]`
  warning).

**Report a Problem** (Help menu / the app menu's Help area, and the Home crash line;
`sciforge/report_ui.py`, pure `report_core.py`):

- A small dialog: "What happened?" (multi-line, required), "What did you expect?"
  (optional), checkbox "Include the last crash log" (ticked when there is one), a read-only
  preview of exactly what will be included.
- Included: SciForge version + build (`diagnostics.report()`), OS and version, Qt, OpenGL
  renderer/vendor string (from the 3D view's GL context if available; else "unknown"), screen
  scaling, the last 200 `[SciForge]` lines (`RECENT`), the crash log tail (last ~300 lines).
- **Redaction** (`report_core.redact`): replace the user's home folder and user name with
  `~` / `<user>`, drop anything that looks like an API key (`sk-...`, `AIza...`, long
  hex/base64 runs after `key`/`token`), and never include `secrets_store` contents or the
  AI chat transcript. Unit-test the redaction with realistic Windows and Linux paths.
- Buttons:
  - **Open on GitHub**: opens
    `https://github.com/Luca0422git/SciForge/issues/new?template=bug_report.yml&title=...&...`
    in the browser with the fields pre-filled (GitHub issue forms accept field ids as URL
    parameters; verify against GitHub's docs). URLs over ~7000 characters fail: put the long
    parts (log, crash log) into the clipboard and into a saved file instead, and say so in
    the dialog ("the log is copied; paste it into the issue").
  - **Save report...**: writes `SciForge-report-<date>.txt` (Desktop by default).
  - **Copy**: everything to the clipboard.
- Nothing is uploaded by SciForge itself. The user's browser does the GitHub part (they need a
  GitHub account; say so, and offer Save/Copy for those without one).

Tests:
- unit: `crashlog_core` (file naming, rotation, crashed-last-time logic with a temp folder),
  `report_core` (redaction, URL building, length limit, body layout);
- GUI scenario `report_problem.py`: open the dialog from the menu, type text, check the
  preview contains the version and redacted paths, Save writes the file, Copy fills the
  clipboard, Open on GitHub calls a stub (`report_ui.OPEN_URL`, a test seam: never open a
  real browser in tests) with a URL that parses back to the right fields;
- GUI scenario `crash_notice.py`: fake a crashed session (marker + log in a temp user data
  dir via the harness's profile), start, Home shows the line, Report it opens the dialog with
  the crash log ticked, Dismiss removes the marker.

### R3. Update check + easy install, and publishing releases

**Publishing** (`sciforge-build.yml`, runs on the tag):

- New final job `release` (needs the build jobs; `permissions: contents: write` on that job
  only; the rest stays `contents: read`). It downloads the built artifacts and creates the
  GitHub Release for the tag with `gh release create` (the `gh` CLI is on GitHub's runners;
  `GH_TOKEN: ${{ github.token }}`), marked **prerelease** when the version has `-beta`/`-rc`.
- Assets: the Windows installer, the portable .7z, the Linux AppImage, the
  **quick-update zip** built from the same commit (reuse the packaging step from
  `sciforge-tests.yml`'s `quick-update` job; make it a script `tools/sciforge/make_quick_update.sh`
  used by both), a `SHA256SUMS.txt` covering all of them, and **`sciforge-release.json`**:
  ```json
  {"version": "0.1.0-beta", "tag": "sciforge-v0.1.0-beta", "core": "<core id>",
   "date": "2026-10-..", "notes_url": "...",
   "assets": {"installer": "...exe", "portable": "...7z", "appimage": "...AppImage",
              "module": "SciForge-quick-update-....zip"},
   "sha256": {"<file>": "<hash>", "...": "..."}}
  ```
  `core` identifies the compiled part (FreeCAD + SciForge core patches). Define it as the hash
  of the last commit that touched anything outside `src/Mod/SciForge` and `docs/` that ends up
  in the build (simplest robust rule: `git log -1 --format=%h -- src ':!src/Mod/SciForge' cMake
  CMakeLists.txt package`), written at build time into a file the installed SciForge can read
  (`<install>/Mod/SciForge/sciforge/core_info.py` or the `VERSION` neighbour). A module-only
  update is safe only when the installed `core` equals the release's `core`.
- Release notes: the tag's section of `CHANGELOG.md` + the fixed "Windows protected your PC"
  text + "How to update" + checksums. Generated by a small script, not typed in the workflow.
- Test the workflow without publishing first: `workflow_dispatch` input `publish: false`
  (default) that does everything but `gh release create`, and print the would-be notes and
  JSON. Only a tag publishes.

**Update check** (`sciforge/update_core.py` pure, `sciforge/update_ui.py`):

- When: at start, in a background thread (never block or slow the start; the Home tab's
  thread + timer pattern: "tiles read on a daemon worker thread, answers polled by a 50 ms
  QTimer"), at most once a day (last check time in the SciForge preferences), plus a manual
  **Help > Check for Updates** that always checks.
- What: `GET https://api.github.com/repos/Luca0422git/SciForge/releases?per_page=10`
  (unauthenticated: 60 requests/hour per IP, plenty), `User-Agent: SciForge/<version>`,
  5 s timeout, `urllib` from the standard library only (no new dependencies). Pick the newest
  release whose version is newer than ours; prereleases count while we are a prerelease (a
  beta user gets the next beta; a 0.1.0 user only gets stable ones; a Preferences choice
  "Updates: Stable only / Betas too" defaults to match the installed version). Read its
  `sciforge-release.json` asset (download it; small) for `core`, assets and hashes.
- Offline, rate-limited, GitHub down, malformed JSON: say nothing at start (log one
  `[SciForge]` line); the manual check says "Could not reach GitHub" plainly.
- Preference: Preferences > General > "Check for updates when SciForge starts" (default on;
  `prefs_core` option, group "Updates"), and the channel choice above. Privacy doc says what
  the request contains (nothing but the request itself and the User-Agent).
- How it is shown (Fusion-like, quiet): a small line at the top of the Home tab, "SciForge
  0.1.0-beta.2 is available. [What's new] [Update now] [Later]", and the same in Help > Check
  for Updates' answer. No popup at start. "Later" hides it until the next version.

**Easy install** ("Update now"):

1. Decide the kind (`update_core.plan(installed, release, layout)`):
   - **module update** when the release's `core` equals ours and we are the installed or
     portable Windows build: download the quick-update zip (the 4-5 MB module);
   - **full installer** otherwise on Windows (or when the module asset is missing): download
     the installer .exe;
   - **Linux AppImage**: the AppImage is read-only, so open the release page in the browser
     with one line "download the new AppImage and replace the old one" (no in-place update);
     other Linux layouts: the same.
2. Download with a progress bar in a small dialog (Cancel works), to
   `<user data>/SciForge/updates/<version>/`; **verify the SHA256** from
   `sciforge-release.json`; a mismatch deletes the file and says so.
3. Unsaved designs: the same question FreeCAD/SciForge asks at quit (save / don't save /
   cancel); Cancel stops the update.
4. Hand over and quit:
   - module update: extract the zip, start its `install_update.ps1` **detached** with new
     parameters (add them; keep the interactive mode working exactly as now):
     `-Target "<install dir>" -WaitPid <SciForge's pid> -Restart -Quiet`. It waits for
     SciForge to exit, asks for admin itself when the target is under Program Files (it does
     now: keep the UAC prompt; it is expected), stops SciForge's own `python.exe` (already
     does), backs up, replaces `Mod\SciForge`, writes its log, and starts `SciForge.exe`
     again. On any failure it restores the backup and shows a message box with the log path.
   - full installer: start the downloaded installer after SciForge exits (a tiny detached
     helper, or the .ps1 with `-RunInstaller <exe> -WaitPid <pid>`), interactive (the user
     sees the normal installer; SmartScreen may appear again: the dialog says so beforehand).
     The NSIS installer must update over the existing install cleanly: test it (install
     0.1.0-beta, then a 0.1.0-beta.2 test build over it; the user's settings in
     `%APPDATA%\SciForge` must survive).
5. After the restart: one line on Home, "Updated to 0.1.0-beta.2. [What's new]" (shown once),
   linking the release notes.

Rules: never install anything without the click on "Update now"; never update while a command
dialog is open (ask to finish or cancel it first); never delete the backup automatically
(the quick-update doc says how to restore; old backups can stay; mention their size in
Diagnostics later if it grows).

Tests:
- unit `test_update_core.py`: version choice (channels, our own version, junk entries,
  drafts ignored), plan choice (core equal/different, layout, missing assets), hash check,
  JSON parsing;
- GUI scenario `update_check.py` with a **fake GitHub**: a local `http.server` in a thread
  serving `/repos/.../releases` and the assets from a temp folder (the base URL is a test
  seam: `update_core.API_BASE`, overridable from the scenario; never call the real GitHub in
  tests). Paths: newer beta shown on Home; "Later" hides it; manual check with no newer
  version says "up to date"; offline (server stopped) says "Could not reach GitHub"; Update
  now on a module update downloads, verifies, and calls the hand-over seam
  (`update_ui.HAND_OVER`, a stub in the test: never quit FreeCAD or run PowerShell in the
  test) with the right arguments; a wrong hash refuses;
- `install_update.ps1`'s new parameters: a Windows-only test cannot run in the Linux sandbox;
  add a check job to `sciforge-tests.yml`'s Windows golden runner that runs the script in
  `-Quiet` mode against a fake SciForge folder (a `bin\SciForge.exe` dummy and a `Mod\SciForge`
  folder) and checks the files were replaced and the backup made. If that is too much for
  the first beta, ask Luca to try "Update now" between two test builds before 0.1.0-beta goes
  out, and write down the steps for him.

### R4. The small welcome

Luca: "first run welcome is fine, but ... its supposed to feel like fusion ... so dont overdo
it."

- **First start only** (a preference flag `WelcomeShown`): one slim line at the top of the
  Home tab, same style as the recovery banner: "Welcome to SciForge 0.1.0-beta. It works like
  Fusion: the ribbon, the timeline, S for search. This is a beta: save often.
  [Cheat sheet] [Open an example] [Report a problem] [x]". The x hides it for good.
- [Cheat sheet] opens `docs/sciforge/cheat-sheet.md` (installed with the module? check
  `CMakeLists.txt`; otherwise open its GitHub URL in the browser).
- [Open an example] opens the Pi 5 case design if it is installed with the module (check; if
  not, install it under `Mod/SciForge/examples/` and add it to `check_install.sh`); otherwise
  drop the button.
- Nothing else: no tour, no tips at start, no modal, no change to the ribbon or the start
  view. "What's new" after an update is R3's one line.

Tests: scenario `welcome_line.py`: fresh profile shows it once; x hides it; the next start
does not show it; the links call their seams.

### R5. Release dry run, then 0.1.0-beta (only with Luca's green light)

1. Everything above on `develop`, CI green, quick-update tried by Luca.
2. Run `sciforge-build.yml` manually on `develop` with `publish: false`: the installer, the
   portable build and the AppImage build; the release JSON and notes print correctly.
3. Ask Luca to install that build fresh (uninstall the old one first, or on another PC if he
   can) and to try: start, welcome line, new design, save, Report a Problem (Save report),
   Help > Check for Updates (says up to date or could not reach GitHub: no release exists
   yet).
4. **Update test before going public** (the one thing that cannot be fixed after people
   have it): publish a throwaway prerelease from a test tag only if Luca agrees. **It must
   sort BEFORE the real beta in semver order** (`0.1.0-beta.0` sorts AFTER `0.1.0-beta`, so
   an installed `.0` would never be offered the beta): use `sciforge-v0.1.0-alpha.1`. The
   release job refuses a tag that differs from `src/Mod/SciForge/VERSION`, so the throwaway
   needs a `develop` commit that sets `VERSION` to `0.1.0-alpha.1` (and a commit setting it
   back to `0.1.0-beta` afterwards). Install the alpha, publish `0.1.0-beta`, check that the
   installed alpha offers the update and the module update works end to end. Delete the
   throwaway release afterwards (Luca's OK). If he prefers not to, write down that the first
   real update (`beta.2`) is the test and warn him. The R3 session also built a way to try
   "Update now" with nothing published: `tools/sciforge/fake_release_server.py` (steps in the
   MEMORY session log "R3").
5. Luca's green light ("release it" or similar, in the conversation): fast-forward `Release`
   to the approved `develop` commit, tag `sciforge-v0.1.0-beta`, push the tag, watch the
   build (~3-4 h for the full build; MEMORY), check the published release page (assets,
   notes, prerelease flag, checksums), and send Luca the link.
6. Tell Luca the small-beta plan (below) and the Discussions switch.

## 4. The closed beta (advice to give Luca at R5, not code)

- Start with 5-10 people he knows, for a week or two, before posting the link publicly.
- Ask them for: Windows version, screen scaling (100/125/150 %), graphics card, whether
  OneDrive/Google Drive backs up their Documents (Luca's own save problem), antivirus.
- Collect reports through Issues (bug template) and questions through Discussions.
- Fix on `develop`, release `0.1.0-beta.2` etc. through the same flow; the update check
  brings it to the testers.

## 5. Things to watch (lessons that apply here)

- **Never edit module files while a test run is going** (MEMORY: a sweep loads files per
  scenario; a half-edited file gave a false failure).
- At most 2 FreeCAD processes in the sandbox (MEMORY sandbox rules); `--only gui` runs every
  scenario (~8 h): use `--scenario a,b`.
- CI shards take ~75 of their 90 minutes; new scenarios add time. If a shard runs out, ask
  before raising the limit or adding a fifth shard (both are fine ideas; the workflow has the
  shard count in one place).
- Test what the user sees, not the code's idea of it (MEMORY, 2026-10-19: the palette test
  compared a colour with an already wrong style sheet and passed while the screen was grey).
  For R2-R4: check the Home lines on the screenshot, not just the widget text.
- Every network call has a timeout, runs off the GUI thread, and has a test seam. No test may
  touch the real internet.
- The sandbox's outbound HTTPS goes through a proxy (see the environment notes); the real
  GitHub API may still be reachable for a manual one-off check, but do not depend on it.
- Plain language for Luca: what changed, what to try, what is not done. He is a beginner and
  wants fixes right the first time; prove a fix with a test that fails without it.
- Copy Fusion's behaviour, never its assets or wording (`CLAUDE.md`).

## 6. Done means

- [x] R0 (2026-10-20): `0.1.0-beta` everywhere (Home, Diagnostics, About, splash, installer); FreeCAD's
      funding/backport templates gone.
- [x] R1 (2026-10-20): new README with screenshots, download section, SmartScreen explanation, privacy,
      licence, trademark note; `known-issues.md`, `privacy.md`, `CHANGELOG.md`; SciForge issue
      templates; link check passes; Luca told how to switch on Discussions.
- [x] R2 (2026-10-20): crash log + crashed-last-time line + Report a Problem (save/copy/open on GitHub,
      redacted); unit + 2 scenarios green.
- [x] R3 (2026-10-20): release job + `sciforge-release.json` + checksums + generated notes; update check
      (background, daily, channel, opt-out) + Update now (module and installer paths, hash
      check, hand-over, restart, "Updated to" line); unit + scenario green; update path
      tried by Luca or the Windows CI check.
- [x] R4 (2026-10-20): the one-line welcome, shown once.
- [ ] R5: dry-run build installed by Luca; with his green light: `Release` fast-forwarded,
      tag pushed, release published as prerelease, link sent.
- [ ] MEMORY.md session log written (what was built, what was learned, what is next), and
      `docs/sciforge/parity/*` untouched unless behaviour changed.
