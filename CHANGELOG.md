# SciForge changelog

What changed in each release, newest first, in plain words. Each release's page on GitHub shows
its own section of this file (the release notes are made from it), so every release gets a
section here whose heading is exactly its version number, like `## 0.1.0-beta` below. Known
problems are in [docs/sciforge/known-issues.md](docs/sciforge/known-issues.md).

## 0.1.0-beta.2

**The second beta.** Two new tabs, a complete SURFACE tab, a Data Panel like Fusion's, and a big
round of work on speed and on SciForge explaining itself. If you have 0.1.0-beta, **Update now**
only has to replace SciForge's own part: the compiled program has not changed.

### New tabs and tools

- **SHEET METAL tab**: sheet metal rules (thickness, bend radius, K-factor, reliefs; a library
  and rules kept in the design), **Flange** (one command for base, contour and edge flanges),
  Bend, Hem (six kinds), Join by Bend, Corner Closure, Lofted Flange, sheet metal Fillet and
  Chamfer, Convert to Sheet Metal, Rip, Unfold and Refold, and **Create Flat Pattern** with
  **Export DXF** (bend lines on their own layers). Drawings get a Bend Table and Bend Notes.
- **PLASTIC tab**: plastic rules for each component (a library of 16, including FDM PLA and
  PETG) that Shell, Draft, Rib, Web and thin Extrude follow; Boss (with its screws), Rest, Rule
  Fillet, Snap Fit, Lip and Groove, and **Design Advice**.
- **The SURFACE tab is complete**: more of Fusion's options in Extrude, Revolve, Sweep, Loft,
  Patch, Offset, Untrim, Extend, Stitch, Trim and Ruled; SOLID's modify tools work on surface
  bodies (Fillet, Chamfer, Press Pull, Split Face, Merge, Replace Face, Move/Copy, Align, Scale,
  Pattern, Mirror); Environment Map analysis; Isoparametric Curve in sketches.
- **Draft takes curved and free-form walls** (splines, ellipses), not only flat and round ones.

### Designs, files and the browser

- **A Data Panel like Fusion's**: cards with pictures, search, sort, list or grid, and details
  with a design's versions and where it is used. **Drag a design into an open design** to
  insert a copy; drag files from your file manager onto the panel to add them.
- **Delete a design** from Home (the **...** on a tile, or the Delete key) and from the Data
  Panel. It goes to a trash folder in the same place, never deleted for good.
- **Opacity Control**: right-click a body or component in the browser.
- **Hovering over a body in the 3D view lights its row in the browser.**
- **Export and import reports**: after an export, a short card says what that file format does
  not keep; after an import, what did not come in.
- **Drawing PDFs** with layers you can switch on and off and text you can search.

### Faster, and it explains itself

- **Dragging never waits for the model**: Draft, Fillet, Chamfer, Shell, Press Pull and Extrude
  show a live picture while you drag; the exact result follows when the mouse rests.
- **Editing an earlier step rolls back the later ones while you edit**, as in Fusion.
- **Values stop at the limit**: Fillet, Chamfer, Draft, Shell, Press Pull, Thicken, a tapered or
  thin Extrude, Revolve, Coil, Pipe, Torus, Gear and sketch fillets stop at the largest value
  that works and say so, instead of failing.
- **Sketches explain themselves**: a conflict names the constraints involved and rings them in
  red; a padlock marks fully constrained sketches in the browser and the timeline, and the
  Sketch Palette says how many are left to define.
- **Big designs**: the browser and timeline re-read the design only after a change, and Undo /
  Redo on big parts take about a second instead of many.

### AI

- **117 AI tools** (there were 16), the same for the chat panel and for AI apps you connect,
  including tools the AI uses to check its own work (inspect the design, find geometry, check
  for problems, render a picture, compare two states), and a documentation library it can
  search.
- **Not yet**: the AI cannot use the new SHEET METAL and PLASTIC tabs, nor the SURFACE tab's
  Fillet, Chamfer, Press Pull, Delete and Merge on surface bodies. Its tools for them come
  next.

### Known problems

The list is in [docs/sciforge/known-issues.md](docs/sciforge/known-issues.md). New in this beta:
the SHEET METAL and PLASTIC tabs are the least used parts of SciForge so far, and the AI cannot
use them yet.

## 0.1.0-beta

**The first public beta.** SciForge is parametric CAD that works the way people who know Fusion
expect it to, free and open source, built on FreeCAD 1.1.4. It is a beta: every feature is tested
by driving the real program, but it has had little use by anyone but its author, so expect rough
edges (read the known issues).

### What you can do

- **Design the Fusion way**: the ribbon (SOLID, SURFACE, MESH, UTILITIES, and SKETCH while
  sketching), the browser, the timeline with a rollback marker, the navigation bar and ViewCube,
  the `S` command search, Fusion's keys and mouse. Dark look by default, a light look in
  Preferences. Home tab with your recent designs, places and a design picture for each.
- **Sketches** with the sketch palette: lines, rectangles, circles, arcs, polygons, slots,
  splines, text; the Sketch Dimension tool; automatic constraints and snapping guides; trim,
  offset, mirror, patterns and more.
- **Solid modeling**: Extrude (all start and extent types, taper, thin), Revolve, Sweep, Loft,
  Rib, Web, Emboss, **Press Pull** (faces, edges, fillet faces, with a draggable arrow), Fillet
  and Chamfer, Shell, Draft, Scale, Combine, Split Body and Split Face, Replace Face, Move/Copy
  and Align, Hole and Thread (simple, counterbore, countersink, tapped, modeled threads),
  primitives (box, cylinder, sphere, torus, coil, pipe), gears, mirror and rectangular, circular
  and path patterns of features, faces and bodies.
- **Components and joints**: components, moving and copying them, rigid, revolute, slider,
  cylindrical, pin-slot, planar and ball joints, as-built joints, joint motion limits, joint drives.
- **Surfaces**: patch, stitch, unstitch, trim, extend, ruled, boundary fill, thicken, delete face.
- **Mesh**: insert, tessellate, repair, reduce, remesh, plane cut, separate and combine, face
  groups, direct edit.
- **Drawings**: base, projected, section, detail and broken views, dimensions with tolerances,
  balloons and parts list, export to PDF and DXF.
- **3D printing**: send to a slicer or export 3MF / STL; **hardware library** (screws, nuts, washers, heat-set inserts, magnets);
  insert STEP, DXF, SVG, canvas pictures, meshes; export everything to open formats.
- **Inspect**: measure, interference, section analysis, curvature, zebra and draft analysis,
  center of mass, construction planes, axes and points.
- **Parameters** you can use in every number field, and **version history** for each design.
- **AI features, off unless you use them**: a chat panel where you connect your own Claude,
  ChatGPT, Gemini or local (Ollama, LM Studio) key and ask it to build; and a connector so AI
  apps such as Claude Desktop can build in SciForge (off until you switch it on in Preferences,
  asks you before the first change in each session, every step is one Undo).
- **FreeCAD Tools**: FreeCAD's own workbenches one click away, with a "Back to SciForge" bar.
- **An example design**: a Raspberry Pi 5 case, built with SciForge, in
  [docs/sciforge/examples/pi5-case](docs/sciforge/examples/pi5-case/README.md).

### New in the way you get and look after SciForge

- **Windows installer and portable download, and a Linux AppImage**, from the
  [Releases page](https://github.com/Luca0422git/SciForge/releases). SciForge installs next to
  FreeCAD without touching it (its own settings folder, own installer entry).
- **Help > Report a Problem**: one dialog that gathers the useful details (versions, graphics
  card, recent SciForge messages, the last crash log) with your name and folders removed. You
  see everything first, then Save it, Copy it, or Open it on GitHub in your browser. Nothing is
  uploaded by SciForge.
- **A crash log**: if SciForge closes unexpectedly, the next start shows a one-line note on Home
  with a button to report it.
- **Help > Check for Updates**, and a quiet check when SciForge starts (at most once a day, off in
  Preferences > General). A new version shows as an **update icon in the top right** of the window
  (next to the search button; it stays until you update) and as one line on Home with **Update
  now**, **What's new** and **Later**. Nothing is installed without your click.
- **A one-line welcome** on Home the first time you start it. It can be closed for good.
- **Version 0.1.0-beta** shown quietly on Home, in SciForge > Diagnostics, on the splash and in
  Help > About.
- **Privacy**: no accounts, no telemetry; the update check and the AI features you connect are
  the only things that go online ([docs/sciforge/privacy.md](docs/sciforge/privacy.md)).

### Known problems

The list is in [docs/sciforge/known-issues.md](docs/sciforge/known-issues.md). The ones to know
before you start: Windows will show "Windows protected your PC" for the unsigned installer
(the exact clicks are in the release notes and in the README); Press Pull is still work in
progress on complex curved shapes; SciForge has no macOS version and is English only.
