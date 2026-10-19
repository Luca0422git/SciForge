# Parity spec: interface shell (outline 7.1, 7.3, 7.14)

Source: five screenshots of the owner's stock Fusion (dark theme), 2026-10-09: the SOLID tab with
the CREATE, MODIFY, CONSTRUCT and INSERT menus open, and a sketch with the SKETCH tab and its
CREATE menu. Implemented in `src/Mod/SciForge/sciforge/` (`ribbon_config.py` = layout data,
`theme.py` = colours, `shell.py` = on/off logic). Status: **first pass, not yet signed off**.

## Measured colours

| Element | Colour |
|---|---|
| Ribbon, tab row, browser header, timeline, nav bar | `#3b4453` |
| 3D view background (flat) | `#2a2a2a` |
| Drop-down menu background | `#454f61` |
| Text | `#f5f5f5` |
| Icon blue (feature faces) | about `#73c5ff` |

## Layout (top to bottom)

1. Application bar: quick access (home, data panel, file, save, undo, redo), document tab in the
   middle, account/help on the right. **SciForge:** menu (all FreeCAD menus), new, open, save,
   undo, redo, document name centred, command search on the right.
2. Workspace button `DESIGN ▾` on the left, spanning the tab row and the icon row.
3. Tab row: SOLID, SURFACE, MESH, SHEET METAL, PLASTIC, MANAGE, UTILITIES; a contextual SKETCH tab
   is added and selected while a sketch is open.
4. Icon row: groups of large icons, each group with `NAME ▾` underneath that opens the full menu.
   SOLID: CREATE, MODIFY, CONFIGURE, CONSTRUCT, INSPECT, INSERT, ASSEMBLE, SELECT.
   SKETCH: CREATE, MODIFY, CONSTRAINTS, CONFIGURE, INSPECT, INSERT, ASSEMBLE, SELECT, FINISH SKETCH.
5. Left: BROWSER (document settings, named views, origin, sketches...), COMMENTS at the bottom.
6. Right top: ViewCube. Sketch mode: SKETCH PALETTE panel on the right.
7. Bottom centre of the view: navigation bar (orbit, look at, pan, zoom, fit, display settings,
   grid and snaps, viewports).
8. Bottom: timeline with playback buttons on the left, settings gear on the right.

Menus list items with an icon, the label, and the shortcut right-aligned (Extrude `E`, Hole `H`,
Press Pull `Q`, Fillet `F`, Move/Copy `M`, Align `A`, Delete `Del`, Line `L`, Sketch Dimension `D`).
Unavailable items are greyed out. Separators group related commands.

## Decisions

- **Icons are original** (`tools/sciforge/make_icons.py`): same visual language (flat-shaded grey
  solids with a light-blue acted-on face, thin light sketch strokes with blue points, red
  constraint glyphs, green "create" badge), drawn from scratch. No Autodesk artwork (outline 2.5).
- Omitted on purpose: Create Form (sculpt, out of scope), Create PCB (electronics, out of scope),
  McMaster-Carr / manufacturer / TraceParts inserts (cloud catalogues; INSERT > Hardware... is
  SciForge's offline library of standard hardware instead, parity/hardware.md), CONFIGURE group.
- Tabs not shown: SHEET METAL, PLASTIC, MANAGE. Out of scope; Luca confirmed he does not need
  them for now (2026-10-09).
- Commands SciForge does not have yet appear greyed out with "Not available in SciForge yet",
  so the menus double as a parity to-do list.
- Interim: Extrude and Revolve have separate "(Cut)" entries until the unified Fusion-style Extrude
  dialog (join/cut/intersect/new body in one) exists.
- Construct menu: all plane items open FreeCAD's datum plane dialog (pick the attachment mode
  there), all axis items the datum line dialog, all point items the datum point dialog. Each needs
  its own pre-set mode for parity.
- Mouse: FreeCAD's "Revit" navigation style = Fusion's default (middle pans, Shift+middle orbits,
  wheel zooms at the cursor). Applied while SciForge is on.
- Sketch editing switches FreeCAD to its Sketcher workbench; SciForge keeps its interface on and
  shows the SKETCH tab (`shell.py`).
- While SciForge is on, Fusion's single-letter keys win: FreeCAD shortcuts on the same key
  (e.g. the Sketcher's L, S, E, P constraint keys) are parked and given back when leaving.

## Done since the first pass

- Browser with Fusion's structure (browser_ui.py), marking menu (marking_menu.py), Press Pull,
  Extrude, Change Parameters, Construct presets, draggable timeline marker, ViewCube colours,
  3D Print.
- Create Sketch: origin plane squares (coloured by axis and labelled since view-3) light up
  under the mouse; click one or a flat face and the sketch opens (sketch_ui.py). No
  attachment pop-ups.
- Extrude: closed sketch profiles are shaded and light up under the mouse; click inside one, or
  click a flat face of the part. Blue drag arrow.
- Starting a command finishes the one in progress (as in Fusion) instead of doing nothing.

## Known gaps (next passes)

- Marking menu slot order is a guess (needs a screenshot of Fusion's right-click menu),
  except OK and Cancel while a command is open: Autodesk's marking-menu help puts OK on the
  drag-right gesture (3 o'clock) and a forum answer Cancel at 9 o'clock, so SciForge shows
  them there (2026-10-13; they were at the top and in the list before).
- ViewCube: see the ViewCube section below for what is still unconfirmed.
- (Document tabs: at the top since 2026-10-16, see "Keyboard shortcuts, pins, document tabs".)
- Sketch Palette: FreeCAD's sketch task panel, restyled; Fusion's palette options differ.
- Command dialogs appear in the Tasks dock on the right; Fusion shows floating dialogs.
- Extrude picks a whole sketch (all its closed regions), not one region of it as Fusion can.
- Origin plane squares are only drawn while Create Sketch waits; Fusion shows them on demand from
  the browser too.
- (Timeline: drag-to-reorder, suppress and groups are built, groups dragged as a whole since
  polish-2: `parity/timeline-browser.md`.)
- Menu icons are 16 px (Fusion about 20 px); COMMENTS panel and "Unsaved" banner not done.

## Keyboard shortcuts, pins, document tabs (2026-10-16, Luca's list)

Luca: "There should be a way to change the keybinds of each tool", "there should be a way to
pin tools to the toolbar", "the toolbar where open documents sit should be at the top. like
fusion". Code: `shortcuts_core.py` and `ribbon_pins.py` (the rules, no Qt, unit tested),
`command_options.py` (the menu and the dialog), `ribbon_ui.py`, `doc_tabs.py`,
`preferences_ui.py` (Keyboard page). Scenarios `ribbon_customize` (57 checks) and
`doc_tabs_top` (17).

| Fusion | Source | SciForge |
|---|---|---|
| A command in a panel's drop-down has a three-dot button; its menu: Pin to Toolbar, Pin to Shortcuts, Change Keyboard Shortcut | Autodesk (blog on keyboard shortcuts; forum "Customizable Keyboard Shortcuts") | A small "..." button at the right of every command row in the ribbon drop-downs (and a right-click on the row): Pin to Toolbar / Unpin from Toolbar, Change Keyboard Shortcut... Pin to Shortcuts is not built (see gaps). |
| Change Keyboard Shortcut: press one key with optional Shift / Ctrl / Alt; blank = no key; Reset = the default | Autodesk (forum) | Same dialog: one key with modifiers (a chord is refused), Clear = no key, Reset = the default key. Saved in `<user data>/SciForge/shortcuts.json` and bound at once. |
| A key another command has: the dialog names that command; you can override (it loses the key) | Autodesk (forum) | Same: "X is the key of Fillet. Override gives it to ... and takes it away from Fillet."; OK becomes Override. FreeCAD's own menu commands on a key SciForge uses are parked while SciForge is on (as before) and given back when it is off. |
| No list of all shortcuts | Forum (users asked for one) | Beyond Fusion: Preferences > SciForge > Keyboard lists every command and its key, with a search box, Change (double-click a row) and Reset All Shortcuts. |
| Shown keys | Autodesk | The keys shown in the drop-downs, tooltips and command search follow the changes. The keys a mode handles itself (sketch letters, 1/2/3 selection filters) stay fixed. |
| Pin to Toolbar: the command's icon is added to its panel's row of big icons; Unpin from the same menu | Autodesk (blog), Forum | Same, per tab and panel, remembered (`Mod/SciForge/Ribbon/Pinned`); a right-click on a pinned icon also offers Unpin. A command that is already a big icon shows Pin greyed. |
| Right-click on the toolbar: Reset All Toolbar Customization | Forum (it resets without asking; users asked for a confirmation) | Same, after a Yes / No question. |
| Document tabs in the application bar at the top, the active one highlighted, an x on each | Autodesk (UI overview), owner's screenshots | Same: a tab strip in the application bar in place of the plain document name. A click activates the document (or drawing / sheet), the x closes it as FreeCAD's own x did (asks to save when changed). FreeCAD's tab bar under the 3D view is hidden while SciForge is on and comes back when it is off. |

Gaps:
- **Pin to Shortcuts** (the S box) and the drop-down's own pinned section: not built yet.
- Pins cannot be dragged into another order; they are added at the end of the panel's icons.
- Document tabs cannot be dragged to reorder or torn off into their own window.

## Origin planes, axes and turn handles (view-3, 2026-10-16)

Luca's reports after the CI #131 quick update:
- "the yellow axis selector is ugly, unruly, too big, gets in the way, and you can't tell
  which face is the x y or z. none of them are labeled. give it the red green blue of all the
  rest of the axis and make it smaller. and label them."
- "maybe add a visual wheel of where its snapping and the angle its at" (angle snapping at
  0 / 45 / 90 / 135..., always on, Ctrl = free: his choice when asked).

| Behaviour | Source | SciForge |
|---|---|---|
| Origin planes in the axis colours: a plane in the colour of the axis it faces (XY blue, XZ green, YZ red), see-through, brighter with a thicker outline under the mouse, a label "XY" / "XZ" / "YZ" at the corner away from the part | Luca (Fusion draws its origin planes in one colour and unlabelled: beyond Fusion) | `origin_look.py` (colours, sizes, labels; unit `test_origin_look`), used by Create Sketch's `PlanePicker` and every tool that reuses it (Construct, Section, Draft, Insert, the patterns' Mirror Plane, Align / Split / Silhouette / Replace Face, the primitives, the surfaces) and by the Mesh plane cut's squares. Scenario `view_origin_planes` |
| Small squares like Fusion's (Luca 2026-10-18, with a picture of Fusion's Create Sketch: "make it small like that, but keep the color") | Luca's picture; pixel size and "same size whatever the zoom" **Guess** | Each square lies in the + quarter of its plane, 10 % of its side off the axes, about 120 px on the screen (`origin_look.SCREEN_SIDE`), redrawn when the zoom changes; a square a part would hide moves out beside the part along its plane, on the side facing the viewer (re-placed when the view turns). When the view looks away from the origin (zoomed on a part far from it) and no place round the origin shows, the square goes on the part of its plane in view, nearest the origin (beyond Fusion, whose squares then stay off the screen). A new, empty design is framed as before (the room the old 100 mm squares took), with the small squares in it. Was: 0.6 x the design, centred on the origin, 100 mm and framed in an empty design. Scenario `origin_squares_small` |
| Origin axes labelled X / Y / Z in red / green / blue | Luca | Revolve's and Construct's axis lines (`revolve_ui.AxisPicker`) and the patterns' (`pattern_ui.AxisPicker`) carry a label on their + half; the patterns use the shared colours |
| Turn handles snap to 0 / 45 / 90 / 135 / 180 ... | Luca (Fusion: rotation increments depend on the zoom, no fixed 45 / 90 snap: Forum, [Smallest rotation unit too large](https://forums.autodesk.com/t5/fusion-support-forum/smallest-rotation-unit-too-large/td-p/11811166)): beyond Fusion | `angle_snap_core.py` (unit `test_angle_snap_core`): the angle is pulled onto the nearest multiple of 45 degrees when the hand is within 6 px of it along the ring as drawn (between 1 and 4 degrees); **Ctrl held: free**; Incremental Move (navigation bar) on: its steps instead. Every turn handle: Move's triad turns and Rotate handle, Revolve, the taper and Draft discs, Plane at Angle, Section, Emboss, the Mesh plane cut, the patterns' angle handle, Insert's and Decal's turn handles. A disc (Coin dragger) keeps the snap at the release too |
| A protractor wheel while a turn handle is held | Luca: beyond Fusion | `protractor.ProtractorRing`: a ring in the plane the handle turns in, a tick every 15 degrees (longer at every 45, longest at every 90), the tick the angle sits on lit yellow, a dashed needle at the current angle and the angle as text ("90.0 deg"); gone when the handle is let go. Scenario `view_angle_snap` |

Not built: the sketch's own Rotate (FreeCAD's `Sketcher_Rotate`, which snaps with Ctrl) keeps
FreeCAD's behaviour; the 45-degree snap of sketch lines is the sketch area's (sf/sketch-3).

## Value fields: a formula of the wrong kind (2026-10-14, gaps work)

Fusion's formulas carry units and a field takes only its own kind: a length parameter typed
into an angle field (or an angle into a distance, a length into a count) is an error, and a
formula without a unit counts in the field's unit. Sources: **Autodesk** API "Understanding
Units in Fusion" (expressions carry units and must match what the value expects); **Forum**
(Autodesk's community manager: "Fusion's equation is indeed unit sensitive", the usual fix for
a unitless field is to divide by 1 mm). **Guess**: the wording of the message.

SciForge took the bare number before: "gap" (12 mm) typed as a draft angle made a 12 degree
draft. Now every field fed by `preview.FormulaInput` (Extrude's distances, tapers and wall
thicknesses, Revolve's angles, the patterns' distances, angle and quantities, Draft, Shell,
Press Pull, Section, Pipe, Scale, Construct, Thread, Hole, the primitives) refuses it in the
dialog like a typo: "'gap' is a length, not an angle. Type an angle, for example 30.", and the
preview keeps the last good value (`extrude.check_kind`; Construct's OK waits, tested).
"gap / 1 mm" (no unit) is 12 degrees.
Fillet / Chamfer already refused it (`blend_field`). Scenario `gaps_formula_units.py`.

## ViewCube (2026-10-12)

SciForge draws its own cube (`viewcube.py`: shape and camera maths, no Qt; `viewcube_ui.py`:
the widget). FreeCAD's NaviCube is switched off while SciForge is on (`ShowNaviCube` in
`theme.VIEWER_SETTINGS`) and comes back when you leave SciForge. Scenarios:
`viewcube_click`, `viewcube_drag`, `viewcube_arrows`, `viewcube_home`, `viewcube_menu`.

Matches Fusion (Autodesk sources, see the research report):
- Top-right corner of every 3D view, fixed size, Z up (FRONT looks at the XZ plane).
- 26 click targets: a face turns the view straight onto it, an edge halfway between its
  two faces, a corner to the isometric view. The turn uses FreeCAD's camera animation
  (on/off and its length are FreeCAD's "UseNavigationAnimations" / "AnimationDuration").
- Dragging the cube orbits the model with the same constrained (turntable) orbit as
  Shift + middle-drag: turns about Z, tilts, never rolls. A click that moves up to 5 px is
  still a click.
- House icon: Go Home. Home belongs to the design (document `Meta`, key `SciForgeHome`,
  saved in the file); without one: the isometric view from front-right-top, fitted. Also
  right after a pan or zoom at the Home direction with FreeCAD's animation on (the model
  ends centred; review fix 2026-10-13).
- Arrow clicks add up: a second click while the view is still turning (a normal
  double-click, 150 ms) turns on from where the first one is going.
- Right-click: Go Home; Orthographic / Perspective / Perspective with Ortho Faces (the
  navigation bar's Camera choice, the same setting); Set Current View as Home > Fit to View
  / Fixed Distance; Reset Home. Ctrl+Alt+V shows or hides the cube (remembered).
- X/Y/Z triad in red/green/blue.

Unconfirmed (check in real Fusion, research report checks 4 and 5), SciForge's guess:
- Four triangles (90 degrees to the next face) and two curved arrows (turn the picture 90
  degrees) while a face is seen straight on: Autodesk Inventor's set; no Fusion page
  confirms them. They turn literally, so from TOP the left triangle shows LEFT lying on
  its side (Z pointing right), like Inventor.
- TOP always comes with +Y up and BOTTOM with -Y up, whatever view you come from
  (FreeCAD's convention); Fusion may keep the nearest roll instead.
- Default Home corner front-right-top (one forum post claims top-right-back).
- Nothing snaps when a drag ends.
- Idle see-through 55 %, hover blue `#6fb7f0`, label font and colours, the triad at the
  lower left of the cube, the house at its upper left: SciForge's own look.
- Go Home turns first, then fits (Fit to View) or jumps to the stored zoom and position
  (Fixed Distance); Fusion probably does it in one move.

Not done yet: Set current view as Front / Reset Front; the cube is always drawn without
perspective. The mouse wheel over the cube zooms the view;
clicks and right-clicks on the see-through corners of the cube's square go to the 3D view
underneath (selection, marking menu).

## Orbit (2026-10-13)

`orbit.py` (the two modes and the camera maths, no Qt, unit tested) and `orbit_ui.py` (the
drop-down, the mouse filter, the orbit-centre dot, the commands). Scenario `orbit_feel`
(67 checks with real middle-button input); `viewcube_drag`, `navigation_orbit` and
`viewer_settings_restart` cover the rest.

Matches Fusion (Autodesk sources, see the research report):
- **Orbit drop-down** in the bottom navigation bar: Constrained Orbit (default: turns about
  the up axis and tilts, never rolls, FreeCAD's "Free Turntable") or Free Orbit (tumbles,
  rolling included). One exclusive choice with a tick, remembered in SciForge's own
  preference `Mod/SciForge/OrbitMode`. Applied as FreeCAD's `OrbitStyle` while SciForge is
  on; the user's own FreeCAD value comes back when SciForge is off (also after a quit with
  SciForge on, through `theme.keep_and_set` / `give_back`).
- **Double-click of the middle button**: Fit. A single middle click does nothing (FreeCAD's
  Revit style, which gives Fusion's mouse layout, would re-centre the view on the point).
- **Ctrl + Shift + middle-drag**: zoom (drag up = in).
- **Shift + a single middle click on the model**: the orbit centre goes there with a small
  green dot (9 px, a picture-only node: clicks go through it). Shift + middle-drag and the
  ViewCube drag then turn about that point, which stays on the same pixel. The dot and the
  centre belong to the design and go when it is closed. **Set Orbit Center** (the next click
  on the model sets it, Esc gives up) and **Reset Orbit Center** are in the right-click
  menu; both are greyed when no design is open.
- A middle press is held back until the mouse moves 4 px, so a shaky click never pans.
- The ViewCube drag follows the chosen mode and the orbit centre.

Unconfirmed (check in real Fusion), SciForge's guess:
- Free Orbit is FreeCAD's "Rounded Arcball" (an arcball with a clean roll near the edges);
  with an orbit centre set, SciForge's own trackball maths is used instead.
- The dot's colour, size and that it stays visible after the drag.
- Fusion turns about the model's centre after a Fit; SciForge turns about the middle of the
  window (FreeCAD's `RotationMode` 0) until an orbit centre is set.
- The orbit about a centre turns about 1.4 % less than FreeCAD's own orbit for the same drag
  (FreeCAD drops the first move of a drag; SciForge starts where the 4 px were crossed).

Known limits: Shift + middle click on sketch geometry inside an open sketch sets nothing
(FreeCAD reports no object for edit-mode geometry; a body face works). With two views of
one design the dot is drawn only in the view where it was set, the centre applies to both.

## Navigation bar (2026-10-14)

The bar at the bottom centre of the view (`navbar_ui.py`, entries in `ribbon_config.NAV_BAR`):
Orbit (see above), Look At, Pan, Zoom / Zoom Window, Fit, Display Settings, Grid and Snaps,
Viewports. Code: `nav_core.py` (choices and maths, no Qt, unit tested), `navigate_ui.py`
(Pan, Zoom, Zoom Window), `display_ui.py`, `grid_ui.py` + `increments.py`, `viewports_ui.py`.
Scenarios: `navbar_display` (71 checks), `navbar_grid` (55), `navbar_viewports` (57), plus
`viewcube_menu` for the shared Camera choice. The choices are remembered (preferences
`Mod/SciForge/Display` and `Mod/SciForge/Grid`, Object Visibility excepted); the test
harness puts them back to the defaults before every scenario.

Source column as in `inspect-analysis.md`: **Autodesk** (help or API, through search
excerpts), **Forum** (Autodesk Community, tutorials), **Guess**.

| Fusion | Source | SciForge |
|---|---|---|
| Pan: the hand; drag with the left button moves the view; until Esc | Autodesk (Pan moves the view parallel to the screen), Guess (Esc) | Same; the model follows the pointer exactly. Esc, a right click or another command ends it. While it runs the left button picks nothing. |
| Zoom (drop-down): Zoom, Zoom Window | Autodesk | Zoom: drag up = in (160 px halves the view), until Esc / right click. Zoom Window: drag a box, what is inside fills the view, then the command ends. |
| Display Settings > Visual Style: Shaded, Shaded with Hidden Edges, Shaded with Visible Edges Only (default), Wireframe, Wireframe with Hidden Edges, Wireframe with Visible Edges Only | Autodesk | Same six, every 3D view. Hidden edges are drawn dashed and lighter where something is in front of them; the two hidden-line wireframe styles fill the faces with the background colour (FreeCAD's own Hidden Line draws every triangle's edges). |
| Environment: Theme (default), Photo Booth, Dark Sky and other lit scenes | Autodesk (Theme, Photo Booth, Dark Sky), Guess (Grey Room, Infinity Pool, Tranquility Blue, Warm Light) | The background only (a gradient per scene); the model is lit as before (see gaps). |
| Effects: Ground Shadow, Ground Plane (Ground Plane off = plain background) | Autodesk, Forum | Ground Shadow: the bodies' outline straight below the model, soft dark; Ground Plane: a light floor. Ambient Occlusion and Reflections are in the menu greyed with the reason. |
| Ground Plane Offset: moves the ground up / down | Autodesk | A slider under the bar: 0 = touching the model's lowest point, 100 = the model's size (its diagonal) below it. Ground Shadow and Ground Plane move with it. |
| Object Visibility: Show All, Origins, Analysis, Joints, Joint Origins, Sketches, Construction Planes / Axes / Points, Canvases, Mesh Bodies | Autodesk (API ObjectVisibility) | Same kinds. A hidden kind is neither drawn nor clickable; the browser eyes stay as they are. Show All shows everything (or hides everything when all are shown). Not remembered (it belongs to this session). |
| Camera: Orthographic, Perspective, Perspective with Ortho Faces | Autodesk | Same, every 3D view, and the same choice as the ViewCube's right-click menu. Perspective with Ortho Faces: orthographic while the view looks straight at a face (after a ViewCube face click, Top / Front ...), perspective otherwise. Default Orthographic (see gaps). |
| Grid and Snaps > Layout Grid | Forum | A grid on the XY ground in the 3D views, light major and darker minor lines. Adaptive: about six major lines across the view, the spacing a 1-2-5 step that changes with the zoom. Default off (see gaps). |
| Layout Grid Lock | Forum | The adaptive spacing stays as it is while zooming. |
| Snap to Grid | Forum | The same setting as the Sketch Palette's Snap (new sketch points snap to the sketch grid). |
| Grid Settings: Adaptive / Fixed, Major Grid Spacing, Minor Subdivisions | Forum | Same dialog values; they go to the layout grid and to the grid of every sketch (the open one at once, every sketch opened later). |
| Incremental Move, Set Increments (linear, angular) | Forum | While on, dragging a handle goes in steps: the blue distance arrows (`taskui.ArrowDragger`, `handles3d.LinearHandle`: Extrude, Press Pull, Fillet, Hole, Offset Plane, Section ...), the angle handles made through `handles3d.angle_handle` (Section, Plane at Angle, Emboss) and Move/Copy's arrows and rings. Defaults 1 mm and 15 deg (Guess). Typed values are never rounded. |
| Viewports: Single View, Multiple Views (Shift+!) | Forum | Multiple Views: four panes, Top, Front, Right and the 3D view that was there; Shift+1 switches it on and off. A click in a pane makes it the active one; each pane has its own camera and ViewCube. |
| Two views side by side / one above the other | Guess (the brief's list; these names are SolidWorks', no Fusion source) | Two Views Horizontal and Two Views Vertical: the 3D view and Front. |

How it maps onto FreeCAD: visual styles are FreeCAD's per-view draw styles (`setOverrideMode`:
As Is, Flat Lines, Shaded, Wireframe) plus SciForge's own Coin nodes (hidden edges through a
`SoDepthBuffer` with function GREATER, background-coloured fill faces); environments are the
view's background (`setGradientBackground` / `setBackgroundColor`); Object Visibility puts a
draw-style and pick-style override at child 0 of each hidden object's root node; the camera
is `view.setCameraType` (a timer watches the view direction for Perspective with Ortho Faces);
the extra panes are `Gui.Document.createView("Gui::View3DInventor")` shown frameless and tiled
in the main window's MDI area (sub-window mode), Single View closes them and puts the tabs
back; Pan / Zoom / Zoom Window edit the camera node directly from a Qt event filter.

Gaps (not built, and why):
- **Lit environments, reflections, ambient occlusion.** Fusion's environments light the
  model from a picture all round it; FreeCAD's Coin viewer has a headlight and a background,
  no image-based lighting, no environment maps on its materials and no screen-space effects.
  SciForge gives each environment's background look only. Ambient Occlusion and Reflections
  are greyed in the menu with that reason; Anti-aliasing is FreeCAD's preference (it only
  applies to views opened afterwards), not in the menu.
- **Ground Shadow** is the bodies' outline projected straight down (a flat soft shape), not a
  light-dependent shadow.
- **Defaults kept from FreeCAD:** the camera starts Orthographic and the Layout Grid off.
  Fusion probably starts Perspective with the grid on (Guess); switching the default would
  change every existing scenario's picture and clicks. One click in the menu changes it, and
  the choice is remembered.
- **Viewports:** the panes are equal and cannot be resized by dragging the border (Fusion's
  quad view can, per a blog); no "synchronize views" (no source found). While several panes
  are shown the document tabs are hidden; views of other open designs wait behind until
  Single View.
- **Incremental Move** does not yet step Extrude's taper angle, Revolve's own angle handles,
  Primitives' arrows, Pattern's turn handle and Hole's point (each command's own handle
  class, in other areas).
- Environment names other than Theme, Photo Booth and Dark Sky, the grid colours, the 1-2-5
  spacing steps and the increments' defaults need a look at real Fusion.
