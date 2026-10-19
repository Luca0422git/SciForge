# Parity spec: places, clouds and NAS (brief home-cloud-ai.md, milestone M2)

Fusion keeps every design in Autodesk's cloud. SciForge keeps them where Luca wants: this
computer, his Dropbox / OneDrive / Google Drive folder, his NAS. Phase A (this milestone)
uses the folders the clouds' own apps keep in sync on the computer: FreeCAD only ever opens
and saves real local files; the cloud app moves them. Phase B (milestone M5) adds signing
in from inside SciForge. Implemented in `src/Mod/SciForge/sciforge/`: `locations_core.py`
(the rules: places, detection, conflict copies, notes, store choice; no Qt, no FreeCAD; unit
tested in `test_locations_core.py`) and `locations_ui.py` (the wizard, the questions, the
notes); Home (`home_ui.py`) and the Data Panel / Save dialog (`versions_ui.py`) show places.
Status: **built and tested with real clicks on a made-up Dropbox folder; not yet tried with
a real cloud app on Windows** (see "To check on a real PC").

Tests: scenario `cloud_place.py` (7 paths: the wizard finds Dropbox and connects it, a
design saved there through the Save dialog's Place row with plain-copy versions, its
picture and this computer's note, changed on another computer and Keep both, Dropbox's
conflicted copy with Compare, a design open on another computer opened read-only, the place
offline, Disconnect); unit tests `test_locations_core.py` (21).

## Sources

Gathered 2026-10-19 by web search; the vendors' pages could not be opened from the sandbox,
so these are search summaries of the pages named: **re-check on a real PC**.
- Dropbox help, "Locate the Dropbox folder" (help.dropbox.com/installs/locate-dropbox-folder):
  `info.json` in `%APPDATA%\Dropbox\` or `%LOCALAPPDATA%\Dropbox\` (`~/.dropbox/` elsewhere),
  keys `personal` / `business` with `path`. A reported macOS case where the path in it did
  not exist: SciForge only offers folders that exist.
- Dropbox help, "Conflicted copies" (help.dropbox.com/organize/conflicted-copy): the copy is
  named with the editor's name, "conflicted copy" and the date
  ("Report (Jane's conflicted copy 2026-10-19).docx"). Whether a second copy the same day
  gets a number is not documented: accepted either way.
- OneDrive: `HKCU\Software\Microsoft\OneDrive\Accounts\<Personal|Business1..>\UserFolder`
  (third-party sources, Mozilla's test code); environment variables `OneDriveConsumer`,
  `OneDriveCommercial`, `OneDrive` (university help pages). Conflict copies: the computer's
  name added with a hyphen ("Budget-DELL-XPS15.xlsx"; university KB, clearcopies.com).
- Google Drive for desktop: streams "My Drive" on a drive letter, G: unless taken or changed
  (support.google.com/drive/answer/2374987); folder names follow the language ("Meine
  Ablage"); settings under `HKCU\Software\Google\DriveFS` (`PerAccountPreferences`, layout
  not documented), `DefaultMountPoint` set by administrators
  (support.google.com/a/answer/7644837). Its conflict copy naming is **not documented**;
  sources disagree ("Name (1)", "Name[Conflict]").
- Git inside sync folders breaks (Microsoft community "OneDrive is corrupting my git
  repositories", a Dropbox forum thread): the reason cloud places keep plain copies.
- Windows file attributes of online-only files (learn.microsoft.com, file attribute
  constants): RECALL_ON_DATA_ACCESS 0x400000, RECALL_ON_OPEN 0x40000; one report says
  ordinary calls can hide them (to check on a real PC).

Fusion has no equivalent (its data is Autodesk's cloud): everything here is **beyond
Fusion**; the dialogs' behaviour follows the brief (section 3) and is SciForge's own.

## Behaviour

| What | SciForge |
|---|---|
| Connect | Home's **+ Connect a cloud or NAS**, File > **Connect a Cloud or NAS**: Where (Dropbox, OneDrive, Google Drive, NAS or network folder, Another folder), the folder (the cloud's folder found, with a **SciForge** folder inside; not found: says so and offers Browse...), a name, Connect. A NAS or other folder can keep git versions (off by default); a cloud never. Refused in words: no folder, a folder that is already a place, one inside another place or holding one. |
| Places on Home | **This computer** and every place connected, **· Offline** (greyed) while its folder is not reachable (the cloud app not running, the NAS off; never an error). Click: its designs as tiles; its page says when it is offline. Right-click: Show in Folder, **Disconnect** (SciForge forgets it; the folder and designs stay). This computer is never offline (its folder is made when first needed). |
| Data Panel, Save dialog | The Data Panel has a place switcher (shown when a place is connected); the Save dialog a **Place** row: picking a place puts its folder in Location. |
| Versions | In a folder a cloud app syncs (a cloud place, or a cloud folder found on this computer even when it is not a place: the project folder could be inside Dropbox) versions are copies beside the design (`<Design>.versions/`), never git. |
| Saving | Files are written whole or not at all (FreeCAD writes a temporary file and renames it; versions' copies are written the same way): the cloud app never uploads half a file. |
| Changed on another computer | When a design is opened its file is remembered (date, size, content). Before a save, if the file on disk changed since (another computer saved it and the sync app brought it here), SciForge asks: **Keep both** (default: mine saved beside theirs as "<Name> (<this computer>).FCStd"), **Replace theirs**, **Open theirs** (a read-only copy opens next to mine), Cancel. A file only touched (same content) does not ask. |
| Conflict copies | Copies a sync app made when two computers changed one file show as **Conflict copy, <whose>** tiles on Home and "(conflict)" in the Data Panel; right-click: **Compare with <Name>** (the comparison of bodies, volume, size...) and **Keep This One** (it becomes the design; the other goes to the place's trash folder, never deleted). Recognised: Dropbox's "(X's conflicted copy DATE)" anywhere; OneDrive's "-COMPUTER" in a OneDrive folder with the original beside it and a computer-like name (this computer's, or capitals with a digit or hyphen: not "Bracket-V2"); Google Drive's "(1)" / "[Conflict]" only in a Google Drive folder with the original beside it. |
| Open on another computer | While a design in a place is open, a note in `<place>/.sciforge/locks/` says which computer and since when (kept fresh every hour, removed on close). Opening it on another computer within 12 hours asks: **Open read-only** (default; Ctrl+S then says to use Save As) or **Open anyway**. Older notes (a crash left them) and this computer's own are ignored. Never a hard lock. |
| Pictures | A save in a cloud place also writes the design's small picture to `<place>/.sciforge/thumbs/`: another computer's Home shows it for a design its cloud app keeps online only, without downloading the design. |

## To check on a real PC (Windows, Luca)

1. Dropbox, OneDrive and Google Drive are each found by the wizard (Google Drive: on G:, or
   another letter; its "My Drive" in Luca's language).
2. A design saved on one computer opens on the other; changing it on both asks instead of
   overwriting; the sync apps' own conflict copies show the Conflict tile.
3. Online-only designs show their picture on Home without being downloaded.
4. A NAS share (mapped drive or \\nas\share) connected as NAS; switched off: Offline.
