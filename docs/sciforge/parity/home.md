# Parity spec: the Home tab (brief home-cloud-ai.md, milestone M1)

Fusion opens on its **Home**: recent designs, buttons to start or open a design, and its
projects. SciForge does the same with local files: its Home tab lists the designs opened and
saved on this computer, with their pictures. Implemented in `src/Mod/SciForge/sciforge/`:
`home_core.py` (the recent list, places, thumbnails cache; no Qt, no FreeCAD, unit tested
in `test_home_core.py`) and `home_ui.py` (the tab, its tiles and menus, the command). Luca
(2026-10-19): Home at every start. Status: **built and tested with real clicks, not yet
checked by Luca.**

Tests: scenario `home_screen.py` (11 paths: start with the ribbon's commands hidden, empty
list and New design (the commands come back), closing the last design shows Home with the
saved design and its picture, the tab closed and brought back, newest first and Pin, a
deleted design greyed with Locate / Remove, Locate after a move, search, the rows (Recent,
This computer with its path, its folders' designs, a design saved in another folder; a new
design's Save starts in This computer's folder), the recovery banner, the option off); the
restart test (`restart_gui.py`): both starts open on Home, the second lists the design the
first one saved; unit tests `test_home_core.py` (19).

**Luca's changes (2026-10-19, after trying it; his sketch):** the ribbon's commands hidden on
Home; one row per place, top to bottom, each showing all its designs; This computer is
where designs are saved, its folder shown on Home (his saves had not shown there).

## Sources

Fusion (searched 2026-10-19; the Autodesk pages could not be opened from the sandbox, so
these come from search summaries of the pages named: **re-check in a browser**):
- Autodesk Fusion help, "The Fusion interface" (GS-THE-FUSION-INTERFACE) and "Home tab"
  (GS-HOME-TAB): a Home icon at the far left of the Application Bar, next to the Data Panel
  icon, "to switch hubs, open or create designs and projects, and find your work"; Home
  takes the place of the design area; its pages My Fusion, Projects, Samples; Recents with a
  grid / list view, Sort by, search and filter, a details panel.
- Autodesk Fusion blog, April 2026 product update (build 2702.1.47): Fusion starts in Home;
  closing the last open design goes back to Home instead of a new Untitled design.
- Autodesk Fusion blog, May 2026 product update, and the Autodesk forum thread "Changes to
  Fusion startup, Home and document close behavior": Preferences > General > Start-up
  experience, Home or a design type (a blank design at start, and when the last one closes).
- Man and Machine, "Autodesk Fusion Home page improvements" (July 2026, build 2704.1.15):
  My Fusion has Start Working (new design / part / project, open, upload), Recents, Ways to
  Explore.
- Autodesk forum "Future improvements to Home and My Fusion": pinning in Home is planned
  ("Data Panel parity"), not shipped; the Data Panel pins projects.
- Autodesk forum "Moving the data panel icon is just malicious": clicking the Home icon
  while Home shows does not close it.

FreeCAD 1.1's Start page (`src/Mod/Start/`, read 2026-10-19): an MDI view in the document
tabs (`Gui/StartView.cpp`), shown at start when `Mod/Start/ShowOnStartup`; recent files
from `BaseApp/Preferences/RecentFiles` (`MRU0..`, count `RecentFiles`); the FCStd's own
`thumbnails/Thumbnail.png`, cached on disk and used while newer than the file
(`App/DisplayedFilesModel.cpp`, `FileUtilities.cpp`); missing files are left out.

Nothing from Fusion is copied but behaviour; the look, words and icons are SciForge's.

## Behaviour

| Fusion | SciForge |
|---|---|
| Fusion starts on Home (since April 2026). | SciForge starts on its **Home** tab, the first document tab (Preferences > General > *Show Home at start*, on). FreeCAD started with a file: Home is added behind it, the design stays in front. While Home is in front the ribbon shows only its top bar (Home, File, Save, Undo, the document tabs): its commands come back on a design (Luca: "on the home screen, lets hide the toolbar"). The browser closes while Home is in front and comes back on a design (Luca); the timeline stays. Home's top row has **Preferences** (Look: dark or light, and the rest). |
| Preferences: Start-up experience = Home or a design type. | *Show Home at start* off: no Home at start and none when the last design closes, the empty window of before. The Home button always works. |
| Closing the last open design goes back to Home. | Same (when *Show Home at start* is on): if the Home tab was closed, it opens again. |
| A Home icon at the far left of the Application Bar, next to the Data Panel icon; clicking it while Home shows keeps Home. | The house icon is the first button of the application bar, before the Data Panel button; also **File > Home** at the top of the File menu. It brings the Home tab to the front, or opens it again. |
| Home takes the place of the design area. | Home is a tab of the document tabs (as FreeCAD's Start page): designs open in tabs beside it, the tab has an x. **Guess** whether Fusion's Home sits in the tab strip. The navigation bar (orbit, pan, zoom) hides while Home is in front and comes back on a design. |
| Start Working: new design / part / project, open, upload. | **New design** (a new design with its first body, in front) and **Open...** (File > Open: designs, STEP, IGES). New part / project / upload: not built (no projects or parts in SciForge; Upload is in the Data Panel). |
| Recents: a grid with pictures. | One page of **rows**, top to bottom (Luca's sketch): **Recent**, then **This computer**, then each cloud and NAS connected. A row's tiles run left to right on as many lines as they need, so every design shows; the page scrolls. Recent: the designs opened and saved (newest first), each with the picture FreeCAD stores in the design, the name, the place and "edited 2 h ago" (the file's time), and its version count (v3). At most 50 are kept. The first time, FreeCAD's own recent files join the list. |
| Pinning in Home: planned by Autodesk, not shipped (the Data Panel pins projects). | **Pin** / **Unpin** (right-click): pinned designs come first, with a blue pin on the picture, and stay when the list is cleared or full. **Beyond Fusion** (planned there). |
| Search and filter in Recents. | The search box narrows the tiles by every word typed (name, folder inside the place); nothing found says so. Sort, filter, list view, details panel: not built. |
| Right-click a design in Home: no source found. | **Guess**, from the Data Panel's menu: Open, Pin, Show in Folder, Version History, Remove from List (the file stays). |
| Double-click a design opens it in a document tab (Data Panel; Home: a guess). | Same; an open design is brought to the front instead of opened twice (versions_ui.open_design). |
| A missing or offline design: no source (Fusion's offline mode opens cached designs only). FreeCAD's Start page leaves missing files out. | **Guess**: a design no longer there stays listed, greyed, "Not found"; double-click says where it was and what to do; right-click: **Locate...** (pick where it is now: it keeps its pin and its place in the list) and **Remove from List**. A file the cloud app keeps online only is never read for its picture (reading it would download it): "online only". |
| AI. | Home's right column: the **AI control** switch, the AIs added with their badges (as many as there are), + Add an AI, Open AI panel (`ai_panel_ui.py`). |
| Projects / places. | A place's row shows **all** its designs, its folders' too ("in Robots"), the last saved first. **This computer** is the folder designs are saved in (Documents\SciForge Designs unless changed; made at once so it shows): its path is beside its name, and a new design's Save dialog always starts there (it used to start in the last folder used, and Luca's saves did not show). Designs remembered in Recent but saved in another folder of this computer show in This computer's row too ("another folder", the path in the tooltip), so none is lost. A row's **...**: Show in Folder; Change Folder... (This computer: Project and Recovery Settings); Disconnect (a cloud or NAS). **+ Connect a cloud or NAS** is beside Open.... A design in two places (Documents inside OneDrive) belongs to the innermost. Home's Open... starts in This computer's folder. |
| Recovery: File > Recover Documents; after a crash Fusion asks at the next start. | The same question at start stays (versions_ui), and Home shows a **banner** while another session's recovery copies are kept ("SciForge did not close properly last time: 1 design has unsaved work..."), with **Recover...** (the Recover dialog). It goes when nothing is left to recover. **Beyond Fusion**. |
| Clear the list: no source. | **Clear List** (above the tiles): every design that is not pinned leaves the list; the files stay. **Guess**. |

## How it works (for the next session)

- The list: `<user data>/SciForge/home/recent.json` (home_core.py has the format). A design
  inside a place is kept as the place's id and its path inside it, so the same cloud folder
  at another drive letter on another computer still finds it (milestone M2).
- Recorded: every design opened (a moment after FreeCAD creates the document: then it has
  its file name) and every finished save. SciForge's own copies (recovery copies, older
  versions opened read-only, `<Design>.versions/`) are not.
- Pictures, file checks and version counts are read on a worker thread (file work only);
  the tiles fill in as the answers come. The pictures are cached in
  `<user data>/SciForge/home/thumbs/`, one per design and save.
- A place's row walks its folders (home_core.walk: at most 6 folders deep and 1000
  designs) when Home is refreshed (a save, an open, a place connected); the search box
  filters what was found without walking again.
- Not built yet: sort and list view.
