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
  McMaster-Carr / manufacturer / TraceParts inserts (cloud catalogues), CONFIGURE group.
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

## Known gaps (next passes)

- Marking menu slot order is a guess: needs a screenshot of Fusion's right-click menu.
- ViewCube: FreeCAD's navigation cube with Fusion-like colours; shape/behaviour differ (9.5).
- Document tabs sit at the bottom of the view (FreeCAD); Fusion has them in the application bar.
- Sketch Palette: FreeCAD's sketch task panel, restyled; Fusion's palette options differ.
- Command dialogs appear in the Tasks dock on the right; Fusion shows floating dialogs.
- Timeline: no drag-to-reorder, suppress or groups yet.
- Menu icons are 16 px (Fusion about 20 px); COMMENTS panel and "Unsaved" banner not done.
- Orbit and Pan buttons on the navigation bar are hints only (the mouse does it).
