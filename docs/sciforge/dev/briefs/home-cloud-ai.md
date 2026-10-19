# Brief: Home screen, Bring-Your-Own-Cloud and AI connectors

Written 2026-10-19 for a separate Claude Code session that builds this on its own branch and
merges into `develop` once the fundamentals work. The owner is Luca, a beginner: explain
every choice in plain words, never assume he can read code.

## In plain words (for Luca)

Three additions, built on a branch of their own:

1. **A Home screen.** SciForge opens to a page with your recent designs (with pictures), a
   "New design" button, your storage places (this computer, your clouds, your NAS) and your
   AI helpers. You get back to it with a Home tab, like FreeCAD's Start page and Fusion's
   data panel, in SciForge's look.
2. **Your own cloud (BYOCloud).** You connect SciForge to *your* storage: Google Drive,
   Dropbox, OneDrive or your NAS. Step one uses the folder those apps already keep in sync on
   your computer (works offline, very reliable). Step two adds signing in from inside
   SciForge, for computers without those apps. SciForge warns you when a design was changed
   on another computer, so a save never silently overwrites it.
3. **AI connectors.** Two ways: (a) your AI app (Claude, Gemini, later ChatGPT) gets a
   connector that lets it build in SciForge while you chat in that app; (b) a chat panel
   inside SciForge where you pick an AI and paste your own key. Every AI action is a normal
   timeline step you can undo, and nothing happens unless you switch it on.

Luca's answers (2026-10-19): AI = **both** (connector for outside AI apps first, then a
built-in chat panel); cloud = **sync folders first, sign-in later**; users = **just Luca, on
several computers** (no multi-user locking beyond "open on another computer"); clouds =
**Google Drive, Dropbox, NAS and OneDrive**.

---

## 0. Before you start (rules for the implementing session)

Read, in this order: `CLAUDE.md`, `MEMORY.md` (status, decisions, traps learned),
`docs/sciforge/feature-outline.md` sections 0-5, then this brief.

- **Branch.** Work on `sf/home-cloud-ai`, branched from `develop`. Merge `develop` into it
  regularly (merge commits, no rebase of pushed history). Do not push to `develop`; Luca
  merges (or asks for the merge) when milestones M1-M3 are done (section 6). No pull
  request unless Luca asks.
- **Where code goes.** New code in `src/Mod/SciForge/`. A FreeCAD core change needs a
  `SCIFORGE:` comment and an entry in `docs/sciforge/core-patches.md`. Avoid core changes:
  Luca gets most updates as a module-only "quick update" zip on stock FreeCAD 1.1.4, which
  carries no compiled code.
- **Dependencies.** Only the Python standard library (FreeCAD 1.1.4 bundles Python 3.11 with
  `ssl`, `urllib`, `http.server`, `json`, `threading`, `zipfile`, `ctypes`) plus small
  pure-Python, LGPL-compatible code vendored under `src/Mod/SciForge/sciforge/vendor/` with
  its license. No `pip install` at run time, no compiled wheels: the quick update must keep
  working. `tools/sciforge/check_install.sh` must say every file is installed.
- **House style.** Every SciForge log line starts `[SciForge]` (use `sciforge.log()` /
  `warn()`). No exception may escape a command, timer, event handler, thread or network
  callback. Pure logic goes in `*_core.py` modules without Qt/FreeCAD, unit-tested in
  `SciForgeTests/unit/`. Match the surrounding code's comment density and naming.
- **Fusion parity.** Copy Fusion's behaviour, never its assets, wording or code. Every
  visible behaviour gets a row in a `docs/sciforge/parity/*.md` file with its source, or
  marked **Guess** / "beyond Fusion".
- **Tests.** Every visible change gets a GUI scenario with real clicks
  (`SciForgeTests/gui/scenarios/`, see `harness.py`); run with
  `tools/sciforge/run_tests.sh --freecad /home/user/SciForge/.sciforge-cache/freecad
  --only scenarios --scenario a,b,c --out DIR`. Never push before the affected scenarios
  pass locally. Never weaken a check to make it pass.
- **Machine limits (learned the hard way).** The sandbox has 4 cores and 15 GB: at most two
  FreeCAD test runs at once, or the container is killed. Wrap runs in
  `flock /tmp/claude-0/sciforge-agent-tests.lock ...` if other sessions test at the same time.
  Never `pkill -f` a pattern that matches your own shell. Never edit files a running test
  run loads.
- **Origin squares are becoming small** (2026-10-18, arriving on `develop` soon; this
  branch starts just before it): once you merge `develop`, scenarios click them through
  `SciForgeTests/gui/plane_input.py` (`click_square`, `click_on_plane`), never fixed points.
  New scenarios should use `plane_input.click_square` from the start.
- **Luca is the user.** He runs Windows. Every message to him is plain language: what
  changed, what to click, what to expect.

---

## 1. What already exists (build on it, don't duplicate it)

| Area | Where | What it gives you |
|---|---|---|
| Start in SciForge | `sciforge/start_in.py` | FreeCAD opens in SciForge, its Start page off (`Mod/Start/ShowOnStartup`), the user's old values kept and given back. The Home screen replaces the "empty view" at start. |
| Startup hooks | `sciforge/shell.py` `startup()`, `_show_own_bars()`; base test `SciForgeTests/gui/restart_gui.py` | Where SciForge comes up at launch; the ribbon/timeline re-show after FreeCAD restores its saved layout (the 2026-10-17 empty-start bug). The Home screen must keep `restart_gui` green. |
| Project folder, versions, recovery, Data Panel | `sciforge/versions.py` (pure), `sciforge/versions_ui.py` (`DataPanel`, `SaveDialog`, `HistoryDialog`, `Recovery`) | Fusion-style saves with versions (git `GitStore` or plain copies `PlainStore`, chosen by `store_for`), crash recovery in `<user data>/SciForge/recovery/`, a Data Panel listing the project folder with thumbnails (`thumbnail_bytes`), Insert Design, relative links (`relative_path`). Preference `Mod/SciForge/Files/ProjectFolder` (`prefs_core.py`). |
| Preferences | `sciforge/prefs_core.py`, `sciforge/preferences_ui.py` | Pages and stored values; add "Home", "Cloud" and "AI" pages here. |
| Document tabs | `ribbon_ui` / shell (F18: tabs at the top mirror `QMdiArea`) | The Home tab sits in this strip. |
| Ribbon, commands | `sciforge/ribbon_config.py`, `commands.py`, icons via `tools/sciforge/make_icons.py` | Original icon recipes, never Fusion's. |
| A declarative CAD op language | `SciForgeTests/golden/builder.py`, `schema.py`, `selectors.py` | JSON steps (`sketch`, `extrude`, `revolve`, `hole`, `fillet`, patterns...) and geometry **selectors** ("the 4 top edges") instead of fragile `Edge7` names. 434 golden models prove it. The AI tools reuse this (section 4.2). |
| Export / 3D print | `sciforge/export.py`, `export_ui.py`, `slicer_core.py` (branch `sf/slicer`, merging soon) | Export and Send to Slicer, usable as AI tools later. |
| Hardware library | branch `sf/hardware` (in progress) | Insertable screws/inserts/magnets, later an AI tool. |

---

## 2. Feature 1: the Home screen

### Behaviour
- At launch (option "Show Home at start", default **on**) SciForge shows a **Home** tab as
  the first document tab instead of an empty design. A Home button (application bar, left of
  the document tabs) and File > Home bring it back; it stays as a tab while designs are open
  (closing it is allowed; the button reopens it).
- Layout (SciForge's own look, dark theme like the rest):
  - **Left column: Places.** "This computer" (the project folder), every connected cloud /
    NAS location with a status chip (Synced, Offline, Sign-in needed, Conflict), and
    "+ Connect a cloud or NAS" (section 3). Clicking a place shows its designs in the main
    area (the Data Panel's listing, larger tiles).
  - **Main area: New design** button, **Open...** (file dialog), a search box, then
    **Recent** as a grid of tiles: thumbnail, name, place (icon of the location), "edited
    2 h ago", version count. Pinned designs first. Double-click opens; right-click: Open,
    Pin/Unpin, Show in folder, Version History, Remove from list. A missing file shows
    greyed with "Locate..." and "Remove".
  - **Recovery banner** when crash leftovers exist (reuse `versions_ui.Recovery`).
  - **Right column: AI helpers** (section 4): one card per configured assistant with status
    ("Claude: connected, used 14:02"), "+ Add an AI" (Claude, ChatGPT, Gemini, Other), and
    "Open chat panel".
- Research task (record in `docs/sciforge/parity/home.md`): Fusion's current start
  experience (the Data Panel, recent designs, the "Home" view in recent releases) and
  FreeCAD 1.1's Start page (`src/Mod/Start/`). Copy behaviour that helps; the look is
  SciForge's own.

### Backend
- `sciforge/home_core.py` (pure, unit-tested): the recent list. One JSON file
  `<user data>/SciForge/home/recent.json`: entries `{key, path, location_id, name,
  last_opened, pinned, thumb}`; merge in FreeCAD's own MRU
  (`User parameter:BaseApp/Preferences/RecentFiles`) once; dedupe by `versions.path_key`;
  cap 50; relative paths stored per location (a cloud folder sits at different absolute
  paths on Luca's computers: `location_id` + path inside it).
- Thumbnails: `versions.thumbnail_bytes(design)` reads `thumbnails/Thumbnail.png` from the
  `.FCStd` zip. Cache PNGs in `<user data>/SciForge/home/thumbs/<sha1(key, mtime)>.png`.
  **Never read an online-only cloud file just to draw a thumbnail** (it would download it):
  on Windows check `os.stat(...).st_file_attributes` for
  `FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS` (0x400000) / `FILE_ATTRIBUTE_OFFLINE` (0x1000) and
  show a placeholder. Also write a small sidecar thumbnail beside designs in cloud places
  (`.sciforge/thumbs/<name>.png`, see 3.4) so other computers get previews without
  downloading.
- Load tiles lazily (a `QTimer` working through the list a few at a time, or a worker thread
  that only does file IO and hands PNG bytes back by signal); the Home tab must appear in
  under ~200 ms.
- Hook: record "opened" / "saved" from FreeCAD's document signals (an `App` document observer
  `slotFinishOpenDocument`, `slotFinishSaveDocument`) and from `versions_ui` saves.
- UI: `sciforge/home_ui.py`, a `QWidget` shown as an MDI sub-window (FreeCAD's Start page is
  one too), so it lives in the document tab strip. Commands `SciForge_Home`.
- Preferences "Home": Show Home at start; clear recent list.

### Tests
- Unit: `test_home_core.py` (merge, dedupe, pin order, cap, missing files, relative paths
  per location, online-only detection with fake attributes).
- Scenario `home_screen.py`: a start shows Home (ribbon and timeline also shown, as
  `restart_gui` checks); New design; save a design, close it, it is first in Recent with a
  thumbnail; double-click reopens it; Pin; a deleted file shows Locate/Remove; Home button
  brings the tab back. Extend `restart_gui.py`: the second start shows Home with the recent
  design.

---

## 3. Feature 2: Bring-Your-Own-Cloud

### 3.1 The idea: "places"
A **place** (internally `Location`) is somewhere designs live: this computer's project folder,
a cloud, a NAS. Everything that lists, opens, saves or versions designs goes through a place.
Phase A places are **folders on disk** (the cloud's own app syncs them), so FreeCAD always
opens and saves real local files and all of `versions.py`/`versions_ui.py` keeps working.
Phase B adds places reached through a cloud's web API, backed by a local cache folder, so the
same rule holds: FreeCAD only ever touches local files; a sync engine moves them.

`sciforge/locations_core.py` (pure): `Location {id, kind (local|dropbox|gdrive|onedrive|nas|
webdav), name, root (local folder or cache folder), mode (sync_folder|api), status}`, stored
in `<user data>/SciForge/locations.json`; the project folder becomes the first place
("This computer"). The Data Panel gets a place switcher; the Save dialog's Location row picks
a place; Home lists places.

### 3.2 Phase A: sync folders and NAS shares (build first)
- **Detection** (pure functions, unit-tested with fake home folders and environment):
  - Dropbox: `info.json` in `%APPDATA%\Dropbox\` or `%LOCALAPPDATA%\Dropbox\`
    (`~/.dropbox/info.json` elsewhere) gives `personal.path` / `business.path`.
  - OneDrive: environment variables `OneDrive`, `OneDriveConsumer`, `OneDriveCommercial`
    (Windows); `~/OneDrive*` elsewhere.
  - Google Drive for desktop: a virtual drive (often `G:\My Drive`) or a mirrored folder;
    look for drive letters with a `My Drive` folder, else ask the person to browse.
    (Verify the current Drive for desktop layout on Windows when implementing.)
  - NAS: the person picks a mapped drive or a UNC path (`\\nas\share\SciForge`); also any
    folder at all ("Other folder"). WebDAV-only NAS: mount it in Windows (or wait for phase B).
- **Connect wizard** (Home "+ Connect a cloud or NAS", Preferences > Cloud): choose a
  provider -> SciForge shows the folder it found (or Browse) -> choose or create a
  `SciForge` folder inside -> name the place -> done. A place whose folder is missing
  (cloud app not running, NAS offline) shows "Offline" and its designs grey, never an error.
- **Versions in cloud places use the plain store**, not git: a `.git` folder inside
  Dropbox/Drive/OneDrive gets corrupted by syncing many small files while git writes them.
  `versions.store_for` gains a rule: a design inside a sync-folder place -> `PlainStore`
  (`<Design>.versions/` + `index.json`). Git stays for local folders and NAS shares (a
  per-place option, default off for cloud kinds).
- **Saving safely**: always write a temporary file in the same folder and rename it over the
  design (`versions.atomic_copy` / `atomic_write_text`): sync apps then upload one complete
  file, never a half-written one. Recovery copies stay in the local recovery folder.

### 3.3 "Changed on another computer" (single user, several machines)
- On open, remember the file's `(mtime, size, sha1)` (`versions.file_sha1`).
- On save, if the file on disk no longer matches, a newer version arrived from another
  computer: ask "This design was changed on another computer at 14:02. Keep both (save mine
  as a copy) / Replace theirs / Open theirs". Default Keep both. Never overwrite silently.
- Sync apps make their own conflict copies; recognise them (pure, unit-tested name patterns:
  Dropbox `Name (Luca's conflicted copy 2026-10-19).FCStd`, OneDrive `Name-PCNAME.FCStd`,
  Google Drive `Name (1).FCStd`) and show them in the Data Panel / Home with a "Conflict"
  badge and "Compare" (reuse `versions_ui.CompareDialog`) / "Keep this one".
- **Open-elsewhere note** (not a hard lock, one user): while a design is open, write
  `.sciforge/locks/<name>.json` `{computer, user, since}` in its place; delete on close; on
  open, if another computer's note is younger than 12 h: "This design is open on LAPTOP since
  14:02. Open anyway / Open read-only". Stale notes (older than 12 h, or the same computer)
  are ignored and replaced.

### 3.4 Small metadata beside designs
`.sciforge/` inside each place holds `thumbs/` (preview PNGs, sec. 2) and `locks/`. Small
files sync fine; keep them out of the Data Panel listing.

### 3.5 Phase B: signing in from inside SciForge (later)
Same `Location` interface; `mode = "api"`; a local cache folder
`<user data>/SciForge/cloud/<location id>/` mirrors the place's `SciForge` folder.
- **Sync engine** (`sciforge/cloud/sync_engine.py`, threads, no FreeCAD calls off the GUI
  thread): list remote changes (delta/cursor APIs), download on open (with progress), upload
  after save (queue, retries with backoff, resumable uploads for big files), offline queue
  that empties when the network returns, conflict check by the server's revision id (upload
  "only if the remote revision is still X", else section 3.3's dialog).
- **Providers** (`sciforge/cloud/<name>.py`, stdlib `urllib` + `ssl` only):
  - Dropbox API v2: OAuth 2 with PKCE (no client secret), access type "App folder"
    (`/Apps/SciForge`), `files/upload` (+ upload sessions over 150 MB),
    `files/download`, `files/list_folder` + `/continue` cursor, `rev` for conflicts.
  - Google Drive API v3: OAuth "installed app" with loopback redirect + PKCE, scope
    `drive.file` (only files SciForge created or opened: the least-privilege, non-restricted
    scope), a `SciForge` folder, resumable uploads, `changes.list` with page tokens,
    `headRevisionId` / `md5Checksum` for conflicts. Google's consent screen in "testing"
    mode expires tokens after 7 days: publish the app (Luca's Google Cloud project).
  - OneDrive: Microsoft Graph with a public-client (PKCE) app registration, scope
    `Files.ReadWrite.AppFolder` (`/drive/special/approot`), `delta` for changes, `eTag` for
    conflicts, upload sessions over 4 MB.
  - NAS: WebDAV over HTTPS (Synology/QNAP/Nextcloud all speak it) with user + password;
    `PROPFIND`, `GET`, `PUT`, `ETag`. SMB stays an OS mount (phase A).
- **Sign-in flow** (`sciforge/cloud/oauth.py`): open the browser to the provider, listen on
  `http://127.0.0.1:<random port>/callback` (stdlib `http.server`, one request, then stop),
  exchange the code with PKCE, store tokens.
- **Secrets** (`sciforge/secrets.py`, also used by the AI keys): Windows DPAPI via `ctypes`
  (`CryptProtectData`, per-user), macOS Keychain via the `security` tool, Linux Secret
  Service if the `secretstorage`/`keyring` module is present, else an owner-only file with a
  clear warning. Never log a token or key.
- **App registrations Luca must make** (the session prepares step-by-step instructions with
  screenshots when M5 starts): a Dropbox app (App Console), a Google Cloud project with the
  Drive API + OAuth consent screen, an Azure app registration (public client). Client IDs of
  public PKCE apps are not secret and may live in `sciforge/cloud/config.py`.

### Tests
- Unit: detection with fake folders/env, conflict-copy names, the open-elsewhere note rules,
  "changed on another computer" decisions, store choice per place, online-only attributes.
- Scenario `cloud_place.py`: a temp folder posing as a Dropbox folder (fake `info.json` in a
  temp `APPDATA`), connect it from Home, save a design there (plain-store versions appear),
  change the file behind SciForge's back (another computer), Save -> the dialog, Keep both ->
  two designs; a `(conflicted copy)` file shows the badge; an offline place greys out.
- Phase B: a fake provider (stdlib `http.server` in a thread speaking a Dropbox-like subset)
  for upload/download/revision conflicts, offline queue and token refresh; never call real
  clouds in CI.

---

## 4. Feature 3: AI connectors

### 4.1 Shape
```
 AI app (Claude Desktop, Gemini CLI, ...)          SciForge (FreeCAD process)
 ┌───────────────────────┐  MCP over stdio  ┌──────────────────────┐  localhost  ┌──────────────────────────┐
 │ chats with Luca       │ ───────────────> │ sciforge_mcp.py       │ ──────────> │ AI bridge (ai/bridge.py) │
 │ calls tools           │ <─────────────── │ (small server process │ <────────── │ runs each tool on the GUI│
 └───────────────────────┘                  │  the AI app starts)   │  JSON + key │ thread, one undo step    │
                                            └──────────────────────┘             └──────────────────────────┘
 Built-in chat panel (ai/chat_ui.py) ── provider API (Anthropic, OpenAI, Gemini, OpenAI-compatible) ──> same tools
```
One **tool registry** feeds both: the MCP server and the chat panel offer the same tools with
the same JSON Schemas, and both run them through the bridge.

### 4.2 The tools (one source of truth)
- `sciforge/ai/tools_core.py` (pure): each tool's name, plain description, JSON Schema for its
  arguments, and whether it changes the design (read-only tools run without asking).
- `sciforge/ai/ops.py`: the code that performs operations. **Move** the reusable parts of
  `SciForgeTests/golden/builder.py` and `selectors.py` into product code here (sketch
  geometry, extrude/revolve/hole/fillet/chamfer/pattern/shell options, geometry selectors),
  and make the golden builder import them, so the 434 golden models keep proving the same
  code the AI uses. Product code must never import from `SciForgeTests`.
- First tool set: `get_design` (bodies, sizes, volume, timeline, parameters, sketches and
  their areas), `screenshot` (PNG of the view, optional view name: iso/front/top..., returned
  as MCP image content so the AI can *see*), `measure`, `create_sketch` (plane or face
  selector + geometry list), `extrude`, `revolve`, `fillet`, `chamfer`, `hole`, `pattern`,
  `shell`, `set_parameter`, `undo`, `redo`, `save`, `export`. Later: `insert_hardware`,
  `send_to_slicer`, `joint`.
- Errors come back as plain sentences (reuse SciForge's dialog messages: "the profile is not
  closed", "the radius is too big for this edge") so the AI can correct itself.

### 4.3 The bridge (inside SciForge)
- `sciforge/ai/bridge.py`: a localhost-only server (stdlib `http.server` on `127.0.0.1`, a
  random port, a random key) started only when "Allow AI apps to control SciForge" is on
  (Preferences > AI, default **off**). It writes `<user data>/SciForge/ai/bridge.json`
  `{port, key, pid}` (owner-only permissions) for the MCP server to find.
- Requests arrive on a server thread and are queued to the GUI thread (a `QTimer`/signal);
  FreeCAD is only touched there. Each changing tool runs in one named transaction (one Undo
  step: "AI: Extrude 10 mm"). While a SciForge dialog or sketch is open, changing tools
  answer "SciForge is busy: finish or cancel the open dialog".
- **Safety**: the first connection of each session asks Luca in SciForge ("Claude wants to
  control SciForge: Allow / Deny"); deleting, overwriting a file or closing without saving
  always asks in SciForge; no "run any Python" tool; an **AI activity** panel lists every tool
  call with its result and an Undo; a Stop button cuts the connection.

### 4.4 The MCP server and the "+ Add an AI" buttons
- `sciforge/ai/sciforge_mcp.py`: a standalone MCP server (stdio transport, JSON-RPC 2.0 per
  the MCP specification; write the small subset needed: `initialize`, `tools/list`,
  `tools/call`, image content), run by FreeCAD's bundled Python (its path is known at setup
  time) so nothing extra is installed. It reads `bridge.json`, forwards calls with the key,
  and returns results. Optional later: the streamable HTTP transport (needed for ChatGPT).
- Buttons on Home ("+ Add an AI") and in Preferences > AI write the connection for that app,
  backing up any file they change, and explain the next step in plain words:
  - **Claude Desktop**: build a `.mcpb` desktop extension (a zip with `manifest.json` + the
    server) and open it (Claude installs it with one click); fallback: add an `mcpServers`
    entry to `claude_desktop_config.json` (`%APPDATA%\Claude\`).
  - **Gemini CLI**: add an `mcpServers` entry to `~/.gemini/settings.json` (`command` +
    `args`); check with `/mcp` in Gemini CLI.
  - **Claude Code, Codex CLI, other MCP apps**: show the command line to copy.
  - **ChatGPT** (experimental, last): ChatGPT's Developer Mode only connects to *remote
    HTTPS* MCP servers, and the plans that allow custom connectors (and write actions) are
    unclear in mid-2026 sources. It needs the HTTP transport, a tunnel (OpenAI's MCP tunnel
    client or similar) and real authentication: do it as M6 with its own security review.
  - **Gemini app (consumer)**: MCP support unconfirmed; check when implementing.
  Verify every config path and format against the vendors' current docs at build time; they
  move often.
- Home shows each configured AI with "connected / used at ... / not running".

### 4.5 The built-in chat panel
- `sciforge/ai/chat_ui.py` (a dock panel) + `sciforge/ai/chat_core.py` (pure agent loop):
  messages + tool definitions -> the model -> tool calls -> run through the bridge on the GUI
  thread -> results (text, and screenshots as images) -> repeat until the model answers;
  a step limit, a Stop button, streamed text.
- `sciforge/ai/providers/`: one adapter per API, translating the common tool registry into
  that API's function-calling format and back (stdlib `urllib`, server-sent events parsed by
  hand): Anthropic Messages API, OpenAI Responses API, Google Gemini API, and any
  OpenAI-compatible endpoint (local Ollama / LM Studio: free, private). Model lists come from
  each provider's models endpoint where it has one, with a sensible default; do not hard-code
  model names in many places.
- Keys: "Add key" stores it with `sciforge/secrets.py`; the panel says plainly that API use
  is billed by the provider per use (separate from a chat subscription) and that the design's
  data and screenshots are sent to that provider.

### Tests
- Unit: tool schemas valid; ops round-trips (the golden models now run through
  `sciforge/ai/ops.py`); each provider adapter against recorded request/response fixtures (no
  network); the agent loop with a scripted fake model; MCP JSON-RPC framing.
- Scenario `ai_bridge.py`: switch the option on, start `sciforge_mcp.py` as a subprocess,
  speak MCP to it over stdio like an AI app: `tools/list`; `create_sketch` + `extrude` -> the
  body's volume; `screenshot` returns a PNG; a changing call while a dialog is open is
  refused; Undo removes the AI's step; with the option off the bridge does not answer.
- Scenario `ai_chat.py`: the chat panel against a fake provider (`http.server` returning
  scripted tool calls) builds a part; Stop works; the key is stored and never logged.

---

## 5. Files to add (proposed)
```
sciforge/home_core.py, home_ui.py
sciforge/locations_core.py, locations_ui.py          (places, detection, wizard, conflicts, notes)
sciforge/secrets.py                                  (DPAPI / Keychain / Secret Service)
sciforge/cloud/__init__.py, oauth.py, sync_engine.py, dropbox.py, gdrive.py, onedrive.py, webdav.py, config.py
sciforge/ai/__init__.py, tools_core.py, ops.py, bridge.py, sciforge_mcp.py, installers.py,
            chat_core.py, chat_ui.py, providers/{anthropic,openai,gemini,openai_compat}.py
docs/sciforge/parity/home.md, cloud.md, ai.md
SciForgeTests/unit/test_home_core.py, test_locations_core.py, test_cloud_*.py, test_ai_*.py
SciForgeTests/gui/scenarios/home_screen.py, cloud_place.py, ai_bridge.py, ai_chat.py
```

## 6. Milestones (each one mergeable, tests green, Luca told what to try)
- **M0 Groundwork**: branch; move the golden builder's ops/selectors into `sciforge/ai/ops.py`
  with the golden models still green (434 pass, 2 known xfail).
  **Done 2026-10-19** (`sciforge/ai/ops/`; 434 models: 432 pass + 2 known xfail; MEMORY.md log).
- **M1 Home screen** (local project folder + recent designs + New/Open + recovery banner).
  **Built 2026-10-19** (`home_core.py`, `home_ui.py`, parity `home.md`; MEMORY.md log).
- **M2 Places, phase A** (**built 2026-10-19**, parity `cloud.md`): sync-folder and NAS places for all four providers, plain-store
  versions in cloud places, "changed on another computer", conflict copies, open-elsewhere
  notes, Home and Data Panel place switcher.
- **M3 AI bridge + MCP server** (**built 2026-10-19**, parity `ai.md`): the tool set, safety prompts, activity panel, Claude Desktop
  and Gemini CLI buttons, "Other app" command line.
  -> **Fundamentals done: ask Luca to merge `sf/home-cloud-ai` into `develop`.**
- **M4 Chat panel**: Anthropic first, then OpenAI, Gemini, OpenAI-compatible (local).
- **M5 Sign-in clouds (phase B)**: Dropbox, then Google Drive, OneDrive, WebDAV NAS (after Luca's
  app registrations).
- **M6 ChatGPT connector (experimental)**: HTTP transport, tunnel, authentication, security
  review.

## 7. Acceptance (what Luca checks)
- Start SciForge: Home shows recent designs with pictures; one double-click opens one.
- Connect Dropbox (or Drive / OneDrive / NAS): its designs show on Home; a design saved on
  the laptop opens on the desktop; editing on both warns instead of overwriting.
- Claude Desktop: "+ Add an AI > Claude", one click to install, then "make me a 40 x 30 x 10
  box with 3 mm rounded edges" builds it in SciForge; every step is in the timeline and Undo
  removes it.
- The chat panel does the same with a pasted API key.

## 8. Open points to settle with Luca as you go
- Home at start: always, or only when no design was open at the last close? **Luca
  (2026-10-19): always** ("Make the home screen default every time").
- AI order after Claude: Gemini CLI or the chat panel first?
- Whether git versions should stay available for NAS places.
- Budget: API keys cost money per use; suggest the local OpenAI-compatible option for free use.
