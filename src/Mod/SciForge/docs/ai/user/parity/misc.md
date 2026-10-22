<!-- A copy of docs/sciforge/parity/misc.md for AI models, made by tools/sciforge/make_ai_docs.py: edit the original, then run the script. -->

# Parity spec: Derive, Decal, Preferences, Scripts and Add-Ins, Manage Materials, Compute All, Capture Image (outline 7.1, 7.6, 7.12, 7.17)

The ribbon entries that still had no command or ran FreeCAD's raw dialogs, built Fusion's way.
Copied behaviour only, never Fusion's assets, wording or code. Status: **built and tested with
real clicks (7 scenarios, 356 checks, and the ribbon sweep), not yet checked by Luca in real Fusion**. Every row is
marked with its source: **Autodesk** (help pages, API reference, Autodesk's blog), **Forum**
(Autodesk Community answers, tutorials) or **Guess** (no source found: SciForge's choice, to
check in real Fusion).

| File (all in `src/Mod/SciForge/sciforge/`) | What |
|---|---|
| `derive_core.py`, `derive.py`, `derive_ui.py` | Derive / Insert Derive: no Qt core, the document side, the dialog, the out-of-date watch |
| `decal_core.py`, `decal.py`, `decal_ui.py` | Decal: the maths (mapping, clipping), the feature, the dialog + handles + the drawing |
| `prefs_core.py`, `preferences_ui.py` | Preferences: the pages and options as data, the window, applying them |
| `scripts_core.py`, `scripts_ui.py` | Scripts and Add-Ins |
| `compute_core.py`, `compute_ui.py` | Compute All |
| `materials_ui.py` (+ `material.py`) | Manage Materials (the Material Browser) and the user's own materials |
| `capture_ui.py` | Capture Image (File menu) |

Tests: scenarios `misc_derive` (76 checks), `misc_decal` (54), `misc_preferences` (84),
`misc_scripts` (52), `misc_materials` (51), `misc_compute` (14), `misc_capture` (25), and the
ribbon sweep; unit tests `SciForgeTests/unit/test_misc_cores.py` (40). Decals following their
faces (fix-decal, 2026-10-16): `fixdecal_body_move` (132), `fixdecal_components` (130),
`fixdecal_face_change` (104), `fixdecal_face_gone` (61), `fixdecal_joints` (88),
`fixdecal_reopen` (75), helpers in `SciForgeTests/gui/fixdecal_steps.py` (they check where
Coin draws the picture, not only what the decal stores).

## Sources (read 2026-10-14 through search summaries; help.autodesk.com is not reachable from the build sandbox)

- Derive: Autodesk help "Derive design features from one design into another" (ASM-DERIVE)
  and "Derived design features"; support article "How to use the Insert Derive command";
  Autodesk help "Update components in an assembly" (Get All Latest); Autodesk Community threads
  "Derived Component not fully updating?", "Update a derived part", "Greyed out parameters when
  using derive", "Insert Derive is not importing favorite parameters", "Derive Parameters to
  Multiple Designs are renamed after Copy"; Product Design Online "global parameters" guide.
- Decal: Autodesk help "Add a decal" (SLD-INS-DECAL); Fusion API `DecalInput` (faces,
  isChainFaces default true, opacity 0..1 default 1.0), `Decal.redefine` (the decal is a
  timeline object); Autodesk Community "Placing a Decal at Correct Scale", "Decal improvements";
  (fix-decal, 2026-10-16, through search summaries) Fusion API `DecalInput.transform` (the
  matrix's origin is the decal's centre and must lie on the first face, its Z the face's
  normal there), `Decal.faces` (the first face is the primary one that sets position and
  orientation), `Decal.redefine` (position, orientation and faces changed with the marker
  rolled to just before the decal); Autodesk Community "Decal not attached to component"
  (a decal left behind when its body moved; the answer: "the decal is part of the component
  and will move with it"), "Decal moving when making hole" (the decal re-sits when a later
  hole removes the face under its centre; Autodesk staff: decals are hard to position, the
  centre cannot sit over a hole), "Decal won't apply around face cutout", "Decals on things
  with holes?"; general Fusion threads on lost references ("No fix for a broken copy-paste
  of a body", "Face 1 Missing": edit the feature and select the face again);
  a rendering course page (Chain Faces wraps; often better off).
- Preferences: Autodesk help, Preferences reference (pages General with API / Design / Render /
  Manufacture / Simulation, Material, Graphics, Unit and Value Display, Default Units; Restore
  Defaults at the lower left); Autodesk blog "How to Set Your Pan, Zoom, & Orbit Controls"
  (the presets table), "Master the Timeline, Browser, & Preferences" (Design History),
  "How to Set Units" (default units of new designs, Set as Default); support article "How to
  change the user language" (restart needed), "How to change the default XYZ orientation"
  (new designs only); Autodesk support "How to find recovery files" (interval in Preferences);
  tutorials (Lynda, Hagerman, VDCI) for the General page's contents.
- Scripts and Add-Ins: Autodesk help "Manage scripts and add-ins" (SLD-MANAGE-SCRIPTS-ADD-INS):
  Shift+S, Create / Edit / Run, the + button, Open File Location, Run on Startup; Autodesk
  Community "What do you think about the new Scripts and Add-Ins Dialog?" (2025: one list,
  favourites, enable at start-up); Medium "Installing and running Fusion 360 add-ins".
- Compute All: Autodesk help "Compute parameters, features, and assembly relationships in a
  design" (SLD-COMPUTE-ALL): Modify > Compute All, Ctrl+B, everything computes, the design
  updates; Fusion API `Design.computeAll` (says nothing about failures: each timeline item's
  health tells); Autodesk keyboard shortcut list.
- Manage Materials: Autodesk help "Manage materials" (SLD-MANAGE-MATERIALS): the Material
  Browser, Physical and Appearance tabs, libraries, search, Favorites, the libraries are
  read-only, New Material > Create New Material; Autodesk Community "How to change material
  for part" (drag onto the body).
- Capture Image: Fusion API `SaveImageFileOptions` (width / height, 0 = the view's, transparent
  background off by default, anti-aliased).

## Derive and Insert Derive

| Fusion | SciForge | Source |
|---|---|---|
| INSERT > Insert Derive: pick the source design; the Derive dialog lists what can be derived; Insert Derive needs a saved design | Same: an unsaved design gets the Save dialog first (the source is kept by a path relative to it), then the file picker (project folder first), then the **Derive** dialog with the source's browser as a tick list: Bodies, Sketches, Construction, Parameters (each body with its component: "Arm > Body1"; each parameter with its value) | Autodesk (dialog), Forum (save first) |
| The source opens in its own tab while you tick | The source is **never opened**: a copy of its saved file is read and thrown away (an open source with unsaved changes is left alone, only saved versions are derived) | SciForge (no cloud tab) |
| Components, bodies, sketches, construction geometry, flat patterns, favourite and feature parameters | Components (with their structure, since polish-2), bodies, sketches, construction planes / axes / points, user parameters (SciForge has no favourites column: every user parameter is offered) | Autodesk |
| Place Objects At Origin | Same: off = where they are in the source design; on = at their own component's origin | Autodesk |
| A Derive feature in the timeline | Same: one **Derive** step; the derived bodies / sketches / planes have no steps of their own | Autodesk |
| Derived bodies can be built on | Same: a derived body's first step holds the derived solid (hidden); later steps on it follow an update | Guess (Fusion works this way in practice) |
| Derived sketches | The source's curves in a sketch, each **fixed** (green), construction curves kept | Guess |
| Derived parameters are greyed while linked; usable in formulas; the same name twice is numbered | Same: Change Parameters lists them greyed with "Derived from <source>" (typing over them is refused with the reason); bare names work in every value box; a taken name becomes `width_1` | Forum |
| When the source is saved again: the Derive shows a yellow out-of-date mark; Get All Latest / right-click to update | Same: the Derive turns **yellow** in the timeline ("Out of date: … was saved again…"), a note says so once; right-click > **Update Derive**; also **Update Derives** (command search) for all of a design's | Forum (yellow mark), Autodesk (Get All Latest) |
| Edit Derive Feature (timeline right-click) | Double-click / Edit Feature: the dialog again with what is ticked; tick more, untick (those objects go, later steps keep working where they can), Place Objects At Origin, **Update**, **Break Link** | Autodesk |
| Break the link: objects stay, parameters become editable | Same: right-click > Break Link (or in the dialog); derived parameters become the design's own | Forum |
| CREATE > Derive (in the source): Destination New Design / Existing Design | Same: the selection is ticked; New Design opens in its own tab; Existing Design asks for the file; the source must be saved (saved first otherwise) | Autodesk |
| (cloud data) | The source is found by its relative path first, then its absolute path: a project folder moved as a whole keeps working; a copied folder with unchanged designs is not "out of date" (the content is compared) | SciForge |
| — | Refused with the reason: a design deriving from itself, from a design that already derives from it (directly or through other designs), an older version opened read-only | SciForge |
| Undo | Insert, Update, Edit, Break Link: one undo step each | — |

### Components with their structure, the source version (branch `sf/polish-2`, 2026-10-16)

Sources: **Autodesk** blog "Copy and paste in Fusion" (Insert > Derive, pick the design and the
body or component; it stays linked); **Autodesk** blog "How to derive from configurations"
(derive the top component rather than a body); **Forum** "Derive Function does not retain
grouped bodies" (nested components derive fine, as components); **Forum** "Insert Derive
directs me to old version" (a Derive reads a particular version of the source); **Autodesk**
help "Update designs" (a reference with a newer version shows the Out-of-Date icon, Get
Latest). **Guess**: the Version drop-down in the dialog (Fusion picks the version through its
reference's version in the Data Panel), and that Update Derive always takes the newest.

| Fusion | SciForge |
|---|---|
| A ticked component comes in as a component, with its bodies and the components inside it | The dialog lists **Components** first ("Arm", "Arm > Hand"). A ticked component is made as a component (App::Part, no timeline step of its own: the Derive is the step) at its place in the source, holding its bodies at their place in it and its components (at any depth) the same way. A body ticked on its own still comes in flat into the active component. Place Objects At Origin puts a derived component at the active component's origin. |
| The source changes: Get Latest | Update Derive also brings bodies and components added since inside a ticked component (deleted ones stay deleted); a ticked component unticked in Edit Derive takes what is in it along. |
| Which version of the source | **Version** in the Derive dialog (Insert and Edit): Latest (vN, the default), or any saved version (milestones marked). A Derive of an older version is yellow at once ("uses v1 of Robot and a newer version exists") and the application bar shows Out-of-Date; Update Derive takes the newest. |

Code: `derive_core.expand` (unit tested), `derive._component_rows`, `_build_components`,
`_component_place`, `update`, `remove_items`, `remove_master_parts`, `derive_ui._version_row`,
`read_source_version`. Scenario `polish2_derive`.

## Decal

| Fusion | SciForge | Source |
|---|---|---|
| INSERT > Decal: pick the picture (PNG, JPG, JPEG, TIF, TIFF), then a face | Same (BMP too); a face picked before the command is used; a design without a body is refused with the reason | Autodesk |
| On flat and curved faces | Flat faces: laid straight; **cylinders: wrapped round the axis without stretching**; other curved faces: laid straight onto the decal's plane (stretches on strong curves) | Autodesk (curved faces), SciForge (the mapping) |
| Opacity, position, scale with the manipulators or the dialog; horizontal / vertical flip | Opacity (0..100, default 100), X / Y Distance, Z Angle, Scale X / Y, Scale Plane XY, Horizontal / Vertical Flip; on the face: two blue **move arrows**, a curved **turn handle**, an **edge arrow that scales** (in proportion), each with its value box | Autodesk (options), API (opacity default 1.0) |
| Chain Faces (on by default in the API) wraps onto connected faces | Same: on by default, takes the faces meeting it tangentially | Autodesk / API |
| The first size | 80 % of the face's smaller side, the picture's proportions kept | Guess (Fusion's default size is not documented; users ask for "fit to face") |
| Centred where the face is picked | Same | Guess |
| A Decal folder in the browser; a timeline object | **Decals** folder in the body's component (eye, Edit Decal, Find in Timeline, Rename, Delete); a **Decal** step in the timeline (double-click edits it) | Autodesk (folder), API (timeline) |
| The decal is stuck to its face: it moves with its body and its component | Same, see **Following the face** below | Forum ("the decal is part of the component and will move with it") |
| The picture is part of the design | Same: kept inside the design file | — |
| Cancel / Esc, Ctrl+Z | Nothing left; one undo step | — |

### Following the face (fix-decal, Luca: "decals dont follow their faces when moved")

The decal used to keep a fixed frame and look for a face at that spot after every change, so
any move of its body left it behind (red, or drawn where the face had been). Now it is stuck
to its face (`decal.follow()`): at every compute it compares the face with what it remembered
of it at the last good compute (`FaceRecord`: the face's own surface frame under the decal's
middle, its corners, area, normal, and the body's volume and middle) and moves the same way.

| Fusion | SciForge | Source |
|---|---|---|
| The decal's centre is a point on its (first) face, its Z the face's normal there | Same: its frame sits on the face | Autodesk (API `DecalInput.transform`, `Decal.faces`) |
| The body moved (Move/Copy, live in the dialog, edited from the timeline) | The decal moves and turns with its face, on flat, wrapped and other faces; a Create Copy leaves it on the original | Forum (moves with it) |
| The component moved (Move/Copy of components, captured or not; Component Drag; a joint driven, made or dragged; undo of any of them) | Drawn in its body's component and at its body's own placement, so it goes along at once, without a recompute (a joint moves a body at the root by its placement) | Forum |
| A body made into a component (Create Components from Bodies) or dragged into another component | Its decals go into that component with it (the browser lists them there) and stay where they are in the design | Forum ("part of the component") |
| The face changed by a later step: pushed / pulled (Press Pull, an edited extrude distance, a parameter) | The decal stays on it: moved with a face that moved as a whole; on a flat face pushed along its normal; on a cylinder made thicker or thinner (still wrapped round it, the picture keeps its size) | Guess (Fusion re-sits the decal on the changed face: Forum, hole thread) |
| The face grows or is cut (a neighbour pulled out, a hole under the decal) | The decal stays where it is on the face (cut where the face is cut); Fusion's decal can jump when a hole removes the point under its centre, SciForge keeps it | Forum (the jump), SciForge (keeps it) |
| The face is gone (its step deleted, replaced) | The decal's step turns **red** with the reason and the picture is not drawn (nothing floats in the air); double-click it: Edit Decal says the face is gone and waits for a click on a face; **Select Face** in Edit Decal moves it to any face, of any body | Forum (lost references: edit the feature, select the face again), API (`Decal.redefine`) |
| A component copied (Copy / Paste, Move's Create Copy, a component pattern): every occurrence shows the component's decals | Same: the picture is drawn on each copy of the body too, and follows the copy when it moves, is hidden or the pattern changes (Paste New copies the decal with the component) | Guess (the decal belongs to the component: Forum) |
| Undo / redo; save and reopen | Every move and change undoes with the decal; a red decal turns red again after a redo; a reopened design shows its decals where their faces are, and they go on following | — |
| — | Decals saved by the earlier SciForge (no face remembered) are brought up to date when the design is opened | SciForge |

## Preferences (UTILITIES > Preferences)

Fusion's window: the pages on the left, the page's options on the right, **Restore Defaults**
at the lower left, OK / Cancel / Apply (Autodesk). SciForge's pages: General (with Design and
API under it), Material, Graphics, Unit and Value Display, Default Units (with Design),
Network, and SciForge's own Keyboard Shortcuts and 3D Print. Options SciForge cannot honour are shown **greyed with the reason** (as the ribbon greys
what is not built). Restore Defaults puts every option back (OK or Apply keeps it, Cancel does
not); options that are FreeCAD's own go back to FreeCAD's default. The options that change the
mouse are applied while SciForge is on; the user's own FreeCAD values come back when it is off.

| Page: option (Fusion) | SciForge (where it is kept) | Source |
|---|---|---|
| General: User Language (restart) | FreeCAD's language (its own windows; SciForge's words stay English), restart said | Autodesk |
| General: Pan, Zoom, Orbit Shortcuts: Fusion (default), SolidWorks, Inventor, Tinkercad, Alias, PowerMill | **Fusion** (middle pans, Shift+middle orbits, wheel zooms; SciForge's own middle-button handling) and **SolidWorks** (middle orbits, Ctrl+middle pans: FreeCAD's SolidWorks style). Greyed: Inventor (F2/F3/F4 not built), Tinkercad (right-drag orbit clashes with the marking menu), Alias, PowerMill | Autodesk blog |
| General: Reverse zoom direction | Same (off: rolling the wheel away zooms in) | Autodesk (which way is default: Guess) |
| General: default orbit type | Constrained Orbit / Free Orbit (the navigation bar's choice) | Forum |
| General: Recovery save time interval | Same (1..120 minutes; Fusion's minimum is 5) | Autodesk support |
| General: Automatic version on close | On by default (Fusion): closing a changed, saved design saves a version; off: the Close dialog asks (polish-2, `parity/versions.md`) | Autodesk (support article), Forum |
| — | Ask for a version description, Project folder, Keep versions with git (SciForge's local files; also in Project and Recovery Settings) | SciForge |
| General > Design: Design History | **Capture design history**: off makes every new design a direct design from the start | Autodesk blog |
| General > Design: Default modeling orientation Y up / Z up | Z up; Y up greyed (SciForge's views, ViewCube and sketches are made for Z up) | Autodesk |
| — (Fusion has no switch) | Sketch: inference guides on/off, constraint on a guide click | SciForge |
| General > API | Scripts folder, Add-ins folder, the editor Edit opens | Guess (Fusion's API page holds script settings) |
| Material: default physical material | Same: what a body counts as (its mass) until it gets a material (Steel by default) | Autodesk |
| Material: default appearance | Greyed: a body shows its material's look | Autodesk |
| Graphics: graphics driver | Greyed: always OpenGL | Autodesk |
| Graphics: anti-aliasing, transparency, frame rate | FreeCAD's anti-aliasing (new views), transparency effects, show frame rate | Guess (Fusion's Graphics page lists different words) |
| Unit and Value Display: precision | General precision (FreeCAD's decimals; restart said); angular precision greyed | Autodesk (page), Guess (rows) |
| Default Units > Design | Default units for new designs (Millimeter, Centimeter, Meter, Inch, Foot): FreeCAD's unit schema of new documents | Autodesk |
| Network: proxy | System / none / custom host and port (FreeCAD's Add-on Manager, the only part that goes online) | Guess |
| — (Fusion keeps its print utility in the 3D Print dialog only) | **3D Print** page (SciForge's own): Send to (the first slicer found / a slicer / Other / Save file only), Program (Other), Format, Also save a copy next to the design; lists the slicers found on the computer. The 3D Print dialog remembers its choices here (`parity/insert-export.md`) | SciForge |

Not listed at all (out of scope): Default workspace (Design only), Data Collection and Use
(SciForge collects nothing), Preview Features, Render / Manufacture / Simulation / Electronics
pages, cloud and account settings.

## Scripts and Add-Ins (UTILITIES > ADD-INS, Shift+S)

| Fusion | SciForge | Source |
|---|---|---|
| One window listing scripts and add-ins (2025: one list; earlier: two tabs), a search box | One list (Name, Type, Run on Startup, Status) with a search box; the folders shown below | Autodesk / Forum |
| Run: a script runs once; an add-in is loaded and runs until stopped | Same: a script runs once (what it does to the open design is one undo step); an add-in's `run(context)` is called and it shows **Running**; the button says **Stop** (its `stop(context)`); double-click = Run | Autodesk |
| Run on Startup | Same, for scripts and add-ins (the 2025 dialog has it for both) | Forum |
| Create: script or add-in, name | Same (Create New Script or Add-In: Type, Name, Description), from SciForge's own templates (FreeCAD's Python API); names checked with the reason | Autodesk |
| Edit: in the code editor | The editor named in Preferences > General > API, else FreeCAD's own editor | Autodesk (VS Code in Fusion) |
| + adds a script from the computer | Same: copied into the scripts folder (a taken name refused) | Autodesk |
| Right-click: Open File Location | Same (with Run / Edit) | Autodesk |
| Autodesk App Store | **Get Add-Ons**: FreeCAD's Add-on Manager (also UTILITIES > Add-on Manager) | SciForge |
| A script that fails | The window says what went wrong (the error's last line), its changes are undone; SciForge goes on. `sys.exit()` is a normal end (its changes stay) | — |

Scripts are FreeCAD macros (`.FCMacro`, `.py`) in the scripts folder (FreeCAD's macro folder);
add-ins are folders with a Python file of the same name defining `run(context)` and
`stop(context)` (Fusion's layout; the code uses FreeCAD's API, Fusion's `adsk` API does not
exist here).

## Compute All (MODIFY > Compute All, Ctrl+B)

| Fusion | SciForge | Source |
|---|---|---|
| Every parameter, feature and assembly relationship computes again; the design updates | Same: every object is computed again from the start (a parameter changed without a recompute is taken up) | Autodesk |
| A progress message while it runs | "Computing all N steps of <design>..." in the status bar, the busy cursor | Guess |
| Failures show in the timeline | Same (red / yellow), never as Report-view errors; plus a **summary**: with failures, the Compute All window lists each step (Error / Warning, why), double-click or **Find in Timeline** selects it; without, a note "N steps in x s, all computed" | Autodesk (timeline health), SciForge (summary window) |
| Ctrl+B | Same; nothing added to undo | Autodesk |

## Manage Materials (MODIFY > Manage Materials)

| Fusion | SciForge | Source |
|---|---|---|
| The Material Browser: Physical and Appearance tabs | Same | Autodesk |
| In This Design, Favorites, the libraries, search | Same, with how many bodies use each; the Library by group (Metal, Plastic, Other); My Materials / My Appearances | Autodesk |
| The libraries are read-only; your own in a library of yours | Same: Delete only for your own | Autodesk |
| New Material > Create New Material | **New Material**: from the selected one, your name and density (g/cm³), kept in FreeCAD's User material library (FreeCAD's tools and Physical Material list it too); **New Appearance**: a name and a colour | Autodesk |
| Drag a material onto a body | **Assign to Selection** (the selected bodies, one undo step); dragging stays in the Physical Material / Appearance dialogs | Forum |
| The material's properties | Density, Young's modulus, Poisson's ratio, yield and tensile strength, thermal conductivity, specific heat (FreeCAD's values) | Autodesk |

## Capture Image (File menu)

| Fusion | SciForge | Source |
|---|---|---|
| File > Capture Image: Image Options (size: the view's or chosen, lock aspect ratio, transparent background, anti-alias), then the file | Same: Current view size, HD / Full HD / 4K presets, Custom with Lock aspect ratio; Transparent background; PNG / JPEG / TIFF / BMP; Anti-alias greyed (the view's anti-aliasing is used) | API (options), Guess (window layout and presets) |

## The other ribbon entries that ran raw FreeCAD dialogs

| Entry | Now | Why |
|---|---|---|
| MODIFY > Manage Materials, Compute All; UTILITIES > Scripts and Add-Ins, Preferences; File > Capture Image | SciForge's (above) | — |
| CREATE > Derive, INSERT > Insert Derive, Decal (were greyed) | SciForge's (above) | — |
| UTILITIES > Add-on Manager | FreeCAD's Add-on Manager (kept) | Fusion's nearest is its App Store (online); the Add-on Manager installs FreeCAD workbenches and macros. Also Get Add-Ons in Scripts and Add-Ins |
| CONSTRUCT > User Coordinate System | FreeCAD's coordinate system dialog (kept) | No Fusion source shows a coordinate system in Design's Construct menu; left for the CONSTRUCT owner to decide (remove, or build) |
| File > Open | The system's file dialog (kept) | Fusion opens from its cloud Data Panel; SciForge's Data Panel (Ctrl+Alt+P) is the Fusion way, Open is the plain way |
| SELECT > Select All, marking menu Hide / Show All | FreeCAD's commands (no dialog) | They do what Fusion's do |

## Known gaps (never faked: listed here)

| Fusion | Why not (yet) |
|---|---|
| Sheet-metal flat patterns, feature parameters "From Components" | SciForge has no favourites / flat patterns (components come with their structure since polish-2) |
| The source opening in its own tab while deriving | The saved file is read instead (no cloud copy to show) |
| Fusion's Get Latest Version of one reference from the application bar | The Out-of-Date button's Get Latest updates every out-of-date Derive (and inserted design) at once; one Derive: right-click > Update Derive |
| Decal on spheres / free-form faces without stretching; decal manipulators on the picture's corners | Other curved faces are laid straight onto the decal's plane; one edge arrow scales (in proportion) |
| Decals rendered in Render / in drawings | No Render workspace (out of scope); TechDraw does not draw textures |
| A copy's own Decals folder in the browser (Copy / Paste, Create Copy, a component pattern) | The picture is drawn on every copy, but the browser lists the decal under the original only (the copies have no decal objects of their own; edit the original's) |
| Which face a decal sticks to when a face is rebuilt in a way that changes it and moves it at the same time (Fusion keeps its own face names) | SciForge follows what it remembered of the face's shape and place; FreeCAD's own face names are lost by SciForge's Python steps (a Move gives "?Face6"), so they are not used |
| Preferences: Inventor / Tinkercad / Alias / PowerMill mouse presets, Y up, default appearance, angular precision | Greyed with the reason in the window (see above) |
| Fusion's add-in API (`adsk.core`, `adsk.fusion`) | FreeCAD's Python API instead: Fusion scripts do not run unchanged |
| Your own materials travel with the design (Fusion keeps them in the cloud) | They live in FreeCAD's User library of each computer; a body keeps its material's name, density and base in the design, and SciForge makes the material again when the design is opened on a computer without it (FreeCAD first prints "Material not found" for it) |
