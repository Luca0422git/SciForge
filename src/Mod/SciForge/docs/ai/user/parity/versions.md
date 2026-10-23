<!-- A copy of docs/sciforge/parity/versions.md for AI models, made by tools/sciforge/make_ai_docs.py: edit the original, then run the script. -->

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
| Milestone checkbox, Save dependent files | **Milestone** box in the Version Description dialog (polish-2, section below). Save dependent files: not built (a linked design is saved on its own). |
| Automatic version on close (Preferences > General, on) | Built (polish-2, section below): closing a changed design saves a version; off, SciForge asks. |
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
| Right-click a design: Open, Version History, Insert into Current Design, Rename, Move, Copy, Delete. | Open, Version History, Milestones, Insert into Current Design, Rename, **Move...**, **Copy...** (polish-2, section below), Delete (to the project's `.sciforge-trash` folder, after a question), Show in Folder. |
| Upload a file (a STEP from a supplier) into the project; it becomes a design (exchange-2) | **Upload** in the panel's toolbar copies a STEP / IGES file into the folder shown; the card shows its file name ("robot.step"); double-click opens it as a new design with its components; right-click: Open, Insert into Current Design (one component, then the Move dialog), Delete, Show in Folder (parity/insert-export.md, Part 2). |
| Grid / list view in the panel's settings. | A toggle button. |

The panel hides `.git`, `<Design>.versions`, the trash and FreeCAD's `.FCBak` backups.

## Data Panel, part 2 (Luca's requests, 2026-10-23)

Luca: "I want a more robust data panel. Something similar to how Fusion does it", and "I
should be able to drag files from the data panel into open files. Make it a copy of the
file." Built in `sciforge/data_panel_ui.py` (the panel) and `data_panel_core.py` (no Qt,
unit tested in `test_data_panel_core.py`); the copy is `versions_ui.insert_copy` /
`design_insert.insert_copy`. Scenario `data_panel_fusion` (59 checks).

Sources (search summaries; the sandbox cannot open autodesk.com, re-check in a browser):
**Autodesk** help "View design history and related data" (a design's details in the Data
Panel: a History tab with its versions newest first, **Uses** = the designs it inserts as
external components, **Used In** = the designs that insert it, Drawings); **Autodesk** blog
"Fusion data panel guide" (organise by name or by last updated; subfolders); **Autodesk**
help "Insert tools" / "Insert designs" (Insert into Current Design brings an external,
linked component; Break Link makes it stand-alone). Whether Fusion takes a card dragged onto
the canvas was not confirmed by the search (one forum thread reports it failing): the drag is
built because Luca asked for it, and as a **copy** because he asked for that.

| Fusion | SciForge |
|---|---|
| Cards: the design's picture, its name and the version number in a badge. | Cards drawn by SciForge (`_CardDelegate`): the picture with a **V3** badge in its top-right corner (accent blue), the name and "2 h ago" under it. Folders first. The list view puts each in a row: small picture, name, "2 h ago · 1.2 MB", the badge at the right. The list / grid choice is remembered. |
| Search the project. | **Search this place**: every folder of the place shown (This computer's project folder, a cloud, a NAS), words in any order, any case; results say where they are ("in Parts"); at most 200; Esc or the clear button brings the folder back. |
| Sort by name or by last updated. | A **Name / Last saved / Size** drop-down (folders stay first, by name); remembered. |
| Click a design: its details (picture, Open, versions, Uses, Used In, Drawings). | A click on a design shows its **details** under the cards: picture, name, "V2 · 2 h ago · 17.7 KB", **Open**, **Insert** (a copy, or linked), tabs **Versions** (newest first, the newest bold; double-click opens a version, the newest opens the design; right-click: Open, Promote, Version History), **Uses (n)** (designs it inserts or derives from, "(not found)" when missing; double-click opens), **Used In** (designs of this place that insert it; read only when the tab is shown). The X hides them until another card is clicked. No Drawings tab: SciForge keeps drawings inside the design (browser > Drawings). |
| Drag a design onto the canvas: it is inserted. | Drag a design card into an open design's **3D view**: an **independent copy** comes in (Luca's choice): one component named after the design ("Robot", a second one "Robot (2)") in the active component, holding the design's components, bodies and every step, with no link back to the file; one undo step "Insert Copy"; then the Move dialog places it (Cancel leaves it where it came in). Dropping on the **browser** works too: on a component row it goes into that component. The design need not be saved first (nothing is stored relative to its file). A design open with unsaved changes is copied as it is open (said in words); one not open is read hidden and closed again. Several cards dragged together come in one after another. Also on the right-click menu and the details' Insert: **Insert a Copy into Current Design**. |
| Drag a card onto a folder: it moves there. | Same (a design moves with its versions, the designs that insert it are pointed at its new place, as Move... does); the folder card is outlined while a card is over it. |
| Upload (designs and other files). | **Upload** (blue) takes designs (.FCStd, copied in as a separate design, v1 "Copy of ...") and STEP / IGES files; files dropped on the panel from the computer's file manager are uploaded the same way (onto a folder card: into that folder). |
| The panel follows changes made elsewhere (the cloud). | The folder shown is looked at every 4 s while the panel is shown; a design put there by another program (the file manager, another computer on the NAS) appears by itself. A folder slower than 0.5 s to list (a far NAS) is refreshed on Refresh only. |
| Keys | **Enter** opens, **F2** renames, **Delete** moves to the trash folder, **Backspace** goes up (while the cards have the keyboard). |
| Delete a design (right-click > Delete; the project's deleted items can be restored). | **Delete** in three places: right-click, the Delete key, and a **Delete** button in the details a click on a design shows (Luca, 2026-10-23: "clicking on a file should give you the option to delete it ... Same in the data panel"). One shared action with Home (`versions_ui.delete_design`): a question (Move to Trash / Cancel), then the design and its `.versions` copies go to the place's `.sciforge-trash` folder (never deleted for good); an open design is closed first (said in the question), Recent forgets it. A STEP / IGES file keeps its extension in the trash folder (before, it became "robot.step.FCStd"). Scenario `delete_designs`. |

What a drag carries: the files as file URLs (so another program sees files; the drag only
offers *copy*, so a file manager never moves a design out of the project) and SciForge's own
`application/x-sciforge-design` paths. While a card is dragged, the panel watches the whole
application (`data_panel_ui.DropSession`): a 3D view or the browser takes the drop, every
other place refuses it, so FreeCAD's own handling of dropped files (which would merge the file
into the design) never runs. The copy is made after the drag has ended, never inside it.

Gaps and guesses: the card size, the badge's place and colour, the 4 s look for changes and
the sort choices are SciForge's guesses at Fusion's look; Fusion's "People" tab, sharing and
locking are out of scope (outline 8); a parameter set (`Parameters`) used by the copied steps
comes along as a second parameter set in this design; joints of the copied design between its
own components are not copied.

## Linked designs by relative path (basic)

| Fusion | SciForge |
|---|---|
| Insert into Current Design (Data Panel right-click, Insert menu): "the design is inserted as an external component and the Initial Position dialog displays"; "An Insert feature displays in the Timeline"; right-click > Break Link makes it "a stand-alone part" (**Autodesk** help "Insert designs", blog on Break Link). | **Insert Component** (INSERT, the application menu, the Data Panel's right-click): one component named after the other design ("Wheel", a second one "Wheel (2)") in the active component, a step in the timeline; its bodies are copies of the other design's bodies (`design_insert.LinkedCopy`, an `App::PropertyXLink` to each) that follow the other design's saved file; then the Move dialog places it (Esc leaves it at the origin). Right-click the component > **Break Link**: the other design's bodies are copied in with every feature (their steps join the timeline), one undo step. The design must be saved first (the link is stored relative to this file): an unsaved design gets the Save dialog and the insert goes on after it (exchange-2; before, each body came in as an `App::Link` at the root). |
| References live in the cloud. | FreeCAD stores the linked file by its path relative to the design (`file="Wheel.FCStd"`), and resolves it from the design's folder, so the project folder can move as a whole (a NAS folder, another drive letter) and the links hold. A linked design that is not found is said in words when the design opens. |

## Known gaps and guesses (to check in real Fusion)

- The exact look of Fusion's Save dialog (field order, the Location tree with projects) is
  from Autodesk's help text, not a screenshot: SciForge uses Name, Location, New Folder, Save.
- Fusion's version list shows who saved and comments; SciForge shows Version, Date,
  Description, Size (who saved is kept in the index / commit author, not shown).
- Milestone, Automatic version on close, Move / Copy in the Data Panel and the Out-of-Date
  icon are built (polish-2); dragging a card onto a folder since 2026-10-23. Not built:
  moving a whole folder, Fusion's "Get Latest Version" of one reference (Get Latest takes
  all).
- Compare is SciForge's own addition (Fusion has none).
- An inserted design comes in as one component (exchange-2), but its own components come
  in flat (its bodies in that one component); the copies follow the other design when this
  design opens (no out-of-date icon, no Get Latest command); a linked copy can be edited in
  this design (Fusion keeps it locked until Break Link).
- Fusion's recovery copies are kept in Autodesk's CrashRecovery folder and offered even for
  designs closed without saving in some reports; SciForge drops the copy when a design is
  closed on purpose (Discard) and when it is saved.
- Fusion refuses a recovery interval under 5 minutes; SciForge allows 1 (small designs save
  in well under a second).

## Milestones, closing, Move / Copy, out of date (branch `sf/polish-2`, 2026-10-16)

Sources (read through search summaries, help.autodesk.com not reachable from the sandbox):
**Autodesk** "Fusion data panel guide" (version control: track changes, restore, set
milestones); **Forum** "F360 Not Prompting for Version Description/Milestone on Save" (the save
prompt has the description and Milestone), "V2.0.5966 Milestones"; **Autodesk** support "How to
turn automatic save off or on in Fusion" (Preferences > General > Automatic Version On Close:
closing a changed design makes a version; users find it on without having set it) and the
forum "Closing without saving?" (Autodesk: that checkbox; off, there is no version on close)
and "Cannot close design without saving in offline mode" (Autodesk: with it off, closing asks
Save / Don't Save); **Autodesk** help "Move designs" and "Copy designs" (right-click > Move /
Copy, pick the project and folder or make one; a moved design keeps its versions; a copy is a
separate design and its references still point at the original's); **Autodesk** help "Update
designs" and "Open older versions of designs" (the Out-of-Date icon in the application bar
when an older version is open or a reference has a newer version; Get Latest).
**Guess**: the wording of the dialogs, the flag mark of a milestone, the description of an
automatic version ("Automatic version on close") and of a copy's v1 ("Copy of Wheel v2").

| Fusion | SciForge |
|---|---|
| Milestone in the save prompt | The Version Description dialog has a **Milestone** box (off). A git version keeps it as a tag `sciforge-milestone-<commit>` on its commit (an ordinary git tag), a copy-kept version as `"milestone": true` in `index.json`. |
| Milestones listed with the versions | Version History: a **Milestone** column (a flag), **Milestones only**, **Mark as Milestone** / **Remove Milestone** on the selected version; Data Panel right-click > **Milestones** opens the history showing only those. Open works on any of them (read-only, as before). |
| Automatic version on close (on) | Closing the last view of a saved design with changes (its tab's close, Ctrl+F4) saves it as the next version without a question ("Automatic version on close"), then it closes. Preferences > General > Automatic version on close (on by default) switches it. |
| Off: Save / Don't Save / Cancel | The **Close** dialog: Version Description (Enter saves) + Save / Don't Save / Cancel. A design never saved: Save... opens the Save dialog (Name, Location), then it closes. An older version opened read-only: only Don't Save / Cancel (save it first with Save As Latest or Save As New Design). Quitting SciForge asks about each changed design in turn (Cancel keeps SciForge open). Designs closed by SciForge itself or by scripts are never asked about. |
| Move: the design and its versions to another folder | Right-click > **Move...**: the project's folders (New Folder makes one); Move. git: a `git mv` and a commit "[SciForge] moved ..." that is no version (the history follows the design: `GitStore._log` walks back through such commits); copies: the `<Design>.versions` folder goes along. The design's own links and Derives keep pointing at the same designs (their relative paths are rewritten in its Document.xml), and the project's designs that insert or derive it are pointed at its new place. Refused with the reason: the design open, a design that uses it open, the name taken there, the same folder. Rename now keeps git versions the same way and points the project's designs that use the design at its new name (refused while one of them is open). |
| Copy: a separate design | Right-click > **Copy...**: a copy in the folder picked ("Wheel 2" when the name is taken), its own v1 ("Copy of Wheel v2"); its links still point at the same designs. |
| Out-of-Date icon, Get Latest | An orange **Out-of-Date** button beside the design's name in the application bar while something of the active design has a newer saved version: an inserted design saved again (its file's saved date differs from the one read), a Derive's source saved again (or a Derive of an older version), or the design is an older version opened read-only. Its menu says what is newer and offers **Get Latest** (reads the inserted designs again, updates the Derives) or **Open the Newest Version**. |

Code: `versions.py` (`set_milestone`, `MILESTONE_TAG`, `GitStore._log` / `_moved_from`,
`count_versions`, `move_design`, `copy_design`, `retarget_xml`, `referrers`,
`project_folders`), `versions_ui.py` (`VersionDialog` Milestone, `HistoryDialog`,
`CloseDialog`, `_CloseWatch`, `save_version_now`, `MoveCopyDialog`, `move_design`,
`copy_design`, `out_of_date`, `get_latest`), `ribbon_ui.py` (the button), `prefs_core.py`.
Tests: unit `MilestoneTests`, `MoveCopyTests`; scenarios `polish2_versions` (milestones at save
and in the history, open a milestone, automatic version on close, the Close dialog's Cancel /
Save / Don't Save, a design never saved, quitting) and `polish2_data_panel` (Move with the
versions and the referring design, Copy, a refused move, Get Latest of an inserted design,
an older version's button).

Not built: Move / Copy of whole folders; dragging cards between folders; Fusion's per-reference
"Get Latest Version" (Get Latest takes every newer reference at once); FreeCAD's own Close All
Documents still asks FreeCAD's question (its Save makes a version all the same).
