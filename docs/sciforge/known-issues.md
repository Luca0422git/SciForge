# Known issues in SciForge 0.1.0-beta.2.1

This is a beta: it works, but it is not finished. These are the things you are most likely to
run into, each with what you can do about it. The list is kept short on purpose and is updated
with every release (see [CHANGELOG.md](../../CHANGELOG.md)). Not on the list? Please report it:
**Help > Report a Problem** in SciForge, or the
[Issues page](https://github.com/Luca0422git/SciForge/issues).

**Save often.** If SciForge closes unexpectedly, Home offers to bring back unsaved work the next
time you start it, but treat that as a safety net, not a plan.

## Things that look or feel unfinished

- **A thin outline frame on the right.** While a panel is open at the right (the AI panel, the
  Sketch Palette, a command's dialog), a thin empty rectangle outline can show over the 3D view
  next to it. It is a leftover of FreeCAD's own overlay panel. As far as we know it is
  only cosmetic. *Workaround:* none needed.
- **Press Pull is work in progress on complex shapes.** On planes and cylinders it is solid. On
  curved or freeform faces, or with many faces picked at once, it can be slow and the result can
  look odd. SciForge says so in a small yellow warning on the Press Pull button and in its
  dialog. *Workaround:* use Fillet, Chamfer, Offset Face or Extrude for those faces, or press
  Undo (Ctrl+Z) when a result looks wrong.
- **The AI chat shows an answer only when it is complete.** Answers are not streamed word by
  word, so a long answer looks like nothing is happening for a while. *Workaround:* wait until
  the Send button works again; press Stop to end it early.
- **English only.** SciForge's own screens, menus and messages are in English; there are no
  translations yet.
- **The SHEET METAL and PLASTIC tabs are new in this beta** and the least used so far. A few
  of Fusion's options are not there yet (for example weld corner reliefs, and a flat pattern
  for a Brake Form lofted flange), and Design Advice is slow on big parts. The details are
  in [parity/sheet-metal.md](parity/sheet-metal.md) and [parity/plastic.md](parity/plastic.md).
- **The AI cannot use the SHEET METAL and PLASTIC tabs yet**, nor the SURFACE tab's Fillet,
  Chamfer, Press Pull, Delete and Merge on surface bodies. Everything else you can do, it
  can do. *Workaround:* make those steps yourself; the AI can carry on from there. Its tools
  for them come next.

## Not built (yet)

- **Not all of Fusion's features.** SciForge covers the Design workspace: sketches, solid and
  surface modeling, patterns, components and joints, mesh, drawings, 3D printing, and more. It
  does **not** have sculpting (T-splines), simulation, rendering and animation, CAM, electronics,
  or cloud collaboration. Some options inside the tools that do
  exist are shown greyed out with the reason. For example, the Fillet options Setback corners,
  Curvature (G2) continuity and Asymmetric radius, and the Chamfer corner types Miter and Blend,
  need work that OpenCASCADE (FreeCAD's geometry engine) does not do yet.
- **No `.f3d` files.** Fusion's own file format is closed, so SciForge cannot open it. *Workaround:*
  in Fusion, export **STEP** (solid parts) or **3MF / STL** (meshes) and open it from Home (Open...) or
  use INSERT > Insert STEP. You get the shapes, not Fusion's timeline.
- **No macOS version.** Windows 10/11 (64-bit) and Linux (x86-64) only.
- **Cloud accounts.** SciForge does not sign in to Dropbox, OneDrive or Google Drive. A "cloud
  place" is the folder your own cloud app keeps in sync. *Workaround:* install the cloud app and
  pick its folder under Home > Connect a cloud or NAS.
- **Components.** External components (a component that lives in another file) and a few of
  Fusion's component options are not built; the details are in
  [parity/components.md](parity/components.md).
- **Drawings.** Drawing templates cannot be edited, Export DWG is not available (use PDF or DXF),
  and a few annotation types (note, weld symbol) are missing.
- **Fusion's keyboard layout is copied, not all of it.** The cheat sheet lists what works:
  [cheat-sheet.md](cheat-sheet.md).

## Things to watch out for

- **Windows warns about the installer** ("Windows protected your PC") because it is not signed
  with a paid certificate. It is normal; the exact clicks are in
  [smartscreen.md](smartscreen.md).
- **Your antivirus may flag SciForge by mistake** (same reason; see the same page).
- **Linux: AI keys are not encrypted** unless your system's key store is available to SciForge
  (see [privacy.md](privacy.md)). SciForge says so next to the key field. Use a key with a
  spending limit you are comfortable with.
- **A design file whose faces were renamed by a big edit.** After a large change to an early step,
  a later step that was attached to a specific face or edge can lose it. SciForge says in the
  timeline which step needs its face picked again. It does not mean the file is damaged.
- **Designs in a folder that a backup program syncs (for example Documents with OneDrive or
  Google Drive backup).** Some of these folders refuse FreeCAD's normal way of saving a file.
  SciForge works around it by saving directly in those folders. If a save ever seems to do
  nothing, check the folder for a file ending in `.FCStd.` and a long code (a half-finished
  save) and tell us which backup program you use.
- **Sketch Rotate still snaps with Ctrl** the way FreeCAD does; hold Ctrl as you would in
  FreeCAD. Fusion's "Pin to Shortcuts" is not built.
- **Updating by "Update now" is new.** It is the part of this beta least tested on other
  people's computers. If an update fails, SciForge keeps a backup of your previous version
  (see [quick-update.md](quick-update.md)) and the manual way (download the new installer)
  always works.

## Reporting something that is not on this list

Help > Report a Problem puts everything useful (version, Windows or Linux version, graphics card,
recent SciForge messages) in one place, with your name and folders removed, and lets you look at
it before anything goes anywhere. More in the [README](../../README.md#reporting-problems-and-ideas).
