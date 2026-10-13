# Parity spec: files, versions and recovery (outline 7.15)

Fusion keeps every save of a design as a numbered version with a description, lists them in
a version history you can open or promote, writes a recovery copy of open designs every few
minutes and offers it back after a crash, and shows a project's designs with thumbnails in
its Data Panel. All of that lives in Autodesk's cloud; SciForge does the same with local
files in a project folder (Luca's NAS). Implemented in `src/Mod/SciForge/sciforge/`:
`versions.py` (stores, recovery files, summaries; no Qt, unit tested in
`test_versions_core.py`) and `versions_ui.py` (dialogs, Data Panel, autosave, commands).
Status: **built and tested with real clicks, not yet checked by Luca in real Fusion.**

Tests: scenarios `versions_save.py` (8 paths: first save, second save with a description,
history, open a version read-only, promote, compare, git underneath, Save As),
`versions_recovery.py` (5 paths: autosave, a clean save clears the copy, Ctrl+Shift+S,
simulated crash and recovery, Recover Documents / Delete / closed design, no copy while a
command runs), `versions_data_panel.py` (5 paths: show, open, folders, badges, hide/show),
`versions_link.py` (5 paths: insert into an unsaved design, the relative path in the file,
the folder moved as a whole, the linked design edited, the linked design missing); unit
tests `test_versions_core.py` (30). The older QA scenarios that press Ctrl+S with a dialog
open (`hole_qa` P7, `fillet_qa` P7, `extrude_presspull_qa5` P22) now press Enter in the
version description box, as a Fusion user does.

## Sources (Fusion's behaviour, read 2026-10-13)

Autodesk help pages (help.autodesk.com, Fusion): "Create and save designs" (ASM-CREATE-
DESIGN: the Save dialog's Name and Location, New Folder / New Project; the Version
Description when saving changes to an existing design), "Save a version of a design as the
latest version" (ASM-SAVE-AS-LATEST: Save blocked on an out-of-date design, Save As Latest
with a description, the saved version does not include later changes), "Open older versions
of designs" (ASM-OPEN-OLDER-VERSION: version drop-down, Open, the Out-of-Date icon in the
Application bar), "View design history and related data" (ASM-VIEW-DESIGN-HISTORY: the
History dialog from the Data Panel, newest first), "Recover designs" (ASM-RECOVER-DESIGN:
File > Recover Documents, the Recover dialog, Open / Delete), the Data Panel pages (hidden
by default, Show Data Panel icon, Ctrl+Alt+P, New Folder above the panel, folders first,
double-click opens, right-click a thumbnail). Autodesk's Fusion blog: "Fusion 360 Mastery:
How to Use Version Control" (hover a non-current version: Open and Promote; promoting makes
a new version, the later ones stay; an older version opened is read-only), "Fusion data
panel guide", "QUICK TIP: Recover Documents". Autodesk support article "How to find recovery
files in Fusion" (backups every 5 minutes by default, interval in Preferences; not while a
command dialog is open). Autodesk community threads: "Reduce recovery interval below 5min"
(5 minutes is the minimum, Preferences > General), "Disable Version Description Dialog Box
on SAVE" / "How to Disable Add Version Description prompt" (Autodesk: no way to turn it off;
Enter saves without one), "trick to save design without advancing version number"
(Ctrl+S always makes a version; Ctrl+Shift+S forces a recovery save and makes no version;
"Automatic version on close"), "Recovered Documents" (after a crash Fusion asks at the next
start whether to open the recovery document), "Fusion 360 no Version history" (right-click
a design in the Data Panel > Version History). Nothing from Fusion is copied but behaviour.

## Save (Ctrl+S, the Save button)

| Fusion | SciForge |
|---|---|
| A new design: the Save dialog asks for a **Name** and a **Location** (a project or a folder in it; New Folder, New Project), Save. No version description on the first save. | Same: Name (a free name is suggested), Location (the project folder by default, `...` for another folder, **New Folder** makes one and selects it), Save. The file is `<Name>.FCStd` in that folder; it becomes **v1**. A name that is taken, an empty name or a folder that cannot be written is said in the dialog, which stays open. |
| A saved design: Ctrl+S ("Save (Version)") opens the Save dialog with a **Version Description** box; Enter saves without one. Every save is the next version (v1, v2, ...). There is no setting to skip the box. | Same: the Version Description box, Enter saves. Every save records the next version with the description, the date, the size and who saved. SciForge adds the switch Fusion lacks: *Ask for a version description on every save* (on by default) in Project and Recovery Settings. |
| The design tab shows the design as saved / changed. | The title in the application bar loses its `*`. |
| Milestone checkbox, Save dependent files | Not built: Milestone is for collaborative hubs; a linked design is saved on its own. |
| Automatic version on close (Preferences > General) | Not built (gap): closing a changed design still asks FreeCAD's Save / Discard / Cancel. |
| File > Save As: a new design in the chosen location. | Same (`SciForge_SaveAs`, in the application menu and UTILITIES): the Name/Location dialog with "<Name> copy" suggested; the copy is v1 where it is saved; the original keeps its versions. |

FreeCAD's own File > Save (in the application menu) records a version too: every finished
save of a design counts, whichever button did it.

Where the versions live:
- Inside the project folder, with the git program installed and *Keep versions with git*
  on (default): the project folder is one git repository (made on the first save, with a
  `.gitignore` for FreeCAD's backup files); a version is a commit of that one file with the
  description as the message. Works with Luca's Forgejo later (push the project folder).
- Elsewhere, or without git: copies in `<Design>.versions/` beside the design (`v0001.FCStd`,
  `v0002.FCStd`, ... and `index.json`: number, time, description, size, who). A save that
  changed nothing in the file shares the previous copy. A folder that cannot be written
  (a read-only share) keeps the copies under the user folder instead and says so in the
  log. A broken index is rebuilt from the copies (only the descriptions are lost).
- Every file is written whole or not at all (temporary file, then rename).

## Version History

| Fusion | SciForge |
|---|---|
| Data Panel: click the design's version number (v3) or right-click > Version History: the list, newest first, with time, who and the description. | **Version History** (application menu, UTILITIES, or right-click a design in the Data Panel): a table newest first: Version (the newest marked current), Date, Description, Size. Double-click a row opens it. |
| Hover a non-current version: **Open** (read-only, in its own tab; the Out-of-Date icon shows in the Application bar) and **Promote** (Save As Latest). | **Open**: a copy opens in its own tab as "<Name> v2", read-only in the sense Fusion means: Save there is blocked with the choice *Save As Latest* / *Save As New Design* / Cancel. **Promote**: the Save As Latest dialog ("You are saving v2 of X as the latest version..."), a description ("Promoted v2" suggested), Enter: the design file is that version again, recorded as a new number; the later versions stay in the list; the design tab is reloaded and the read-only tab closed. A design with unsaved changes must be saved or closed first (said in words). |
| No comparison of versions. | **Compare** (SciForge's addition): the selected version against the newest: bodies, sketches, features, objects, total volume, file size, last saved; changed rows in bold orange. |

## Recovery (autosave and crash recovery)

| Fusion | SciForge |
|---|---|
| A recovery copy of every changed design every N minutes (Preferences > General, "Recovery save time interval", default 5, minimum 5, up to 120); not while a command runs. | A recovery copy of every changed design every N minutes (Project and Recovery Settings, default 5, SciForge allows 1 to 120); postponed while a command dialog is open (a sketch being edited is not a command) or a recompute runs. Copies go to `<user data>/SciForge/recovery/` with a sidecar naming the design, its file and the session. |
| Ctrl+Shift+S forces a recovery save; no version is made. | Same (`SciForge_RecoverySaveNow`). |
| After a crash, Fusion asks at the next start whether to open the recovery document; declining warns it will be lost. File > Recover Documents shows the Recover dialog (the list; Open, Delete); the menu shows a count. | At the next start with SciForge on: **"Recover unsaved work?"** with the designs ticked (name, time, file or "never saved"): **Recover** opens them under their own file name, shown as changed; the next Ctrl+S suggests the description "Recovered after a crash" and saves them into their file as the next version. **Delete** throws the ticked copies away, **Later** keeps them for **Recover Documents** (application menu, UTILITIES), which says in words when there is nothing to recover. |
| A clean save or close removes the recovery data. | Same: a finished save or a closed design drops its copy; a clean quit drops the session's copies; what is left at the next start came from a crash. |
| Fusion's cloud keeps the saved versions safe. | FreeCAD's own autosave (Preferences > General > Document) is switched off while SciForge is on (two autosavers would write every design twice and show two recovery dialogs) and switched back when SciForge is off, also after a quit with SciForge on. |

## Data Panel (the project folder)

| Fusion | SciForge |
|---|---|
| Hidden by default; the Show Data Panel icon at the left of the Application bar or Ctrl+Alt+P shows it; it slides in on the left. | The **Data Panel** button at the left of the application bar or **Ctrl+Alt+P** shows / hides a dock on the left; hidden at start. |
| Hub > projects > folders first, then designs as cards: thumbnail, name, version number. | The project folder (chosen in the settings or with the panel's `...` button; `Documents/SciForge Designs` until then): folders first, then designs as cards with FreeCAD's own thumbnail (`Document/SaveThumbnail`, on by default), the name and the version badge (v3). A breadcrumb (Project / Robots / Arm) and an Up arrow; list view as an option. |
| Double-click a folder opens it; double-click a design opens it. | Same; a design already open comes to the front instead. |
| New Folder above the panel. | **New Folder** in the panel's toolbar (and the right-click menu): "New Folder", "New Folder 2", ... |
| Right-click a design: Open, Version History, Insert into Current Design, Rename, Move, Copy, Delete. | Open, Version History, Insert into Current Design, Rename, Delete (to the project's `.sciforge-trash` folder, after a question), Show in Folder. Move / Copy: not built (do it in the file manager; the panel refreshes). |
| Grid / list view in the panel's settings. | A toggle button. |

The panel hides `.git`, `<Design>.versions`, the trash and FreeCAD's `.FCBak` backups.

## Linked designs by relative path (basic)

| Fusion | SciForge |
|---|---|
| Insert into Current Design (Data Panel right-click, Insert menu): the other design comes in as a component that follows the original. | **Insert Component** (INSERT, the application menu, the Data Panel's right-click): the other design's bodies come in as links (`App::Link`) that follow the file. The design must be saved first (the link is stored relative to this file): an unsaved design gets the Save dialog and the insert goes on after it. |
| References live in the cloud. | FreeCAD stores the linked file by its path relative to the design (`file="Wheel.FCStd"`), and resolves it from the design's folder, so the project folder can move as a whole (a NAS folder, another drive letter) and the links hold. A linked design that is not found is said in words when the design opens. |

## Known gaps and guesses (to check in real Fusion)

- The exact look of Fusion's Save dialog (field order, the Location tree with projects) is
  from Autodesk's help text, not a screenshot: SciForge uses Name, Location, New Folder, Save.
- Fusion's version list shows who saved and comments; SciForge shows Version, Date,
  Description, Size (who saved is kept in the index / commit author, not shown).
- Milestone, Automatic version on close, Move / Copy in the Data Panel, the Out-of-Date icon
  (SciForge names the tab "<Name> v2" instead) are not built.
- Compare is SciForge's own addition (Fusion has none).
- Fusion inserts a whole design as one component; SciForge links each body (components are
  plan item "Components").
- Fusion's recovery copies are kept in Autodesk's CrashRecovery folder and offered even for
  designs closed without saving in some reports; SciForge drops the copy when a design is
  closed on purpose (Discard) and when it is saved.
- Fusion refuses a recovery interval under 5 minutes; SciForge allows 1 (small designs save
  in well under a second).
