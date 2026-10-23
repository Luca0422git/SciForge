# SciForge cheat sheet: Fusion habits, SciForge answers

One page for someone who knows Fusion. Everything here is what SciForge does today (the parity
documents in `parity/` say where it still differs). Keys only work while the SciForge
interface is on (it is on from the start in a SciForge build; in FreeCAD with the quick update,
pick **SciForge** in the workbench list first).

## Keys

| Fusion key | SciForge | Notes |
|---|---|---|
| `S` | Command search | Type a few letters, Enter runs the best match |
| `Q` | Press Pull | Faces push/pull, edges fillet, a fillet face changes its radius |
| `E` | Extrude | In a sketch: finishes the sketch and extrudes the picked profile |
| `F` | Fillet | "+" adds a set with its own size; Type: Rule / Full Round; Radius Type: Chord Length / Variable |
| `H` | Hole | |
| `M` | Move / Copy | |
| `I` | Measure | |
| `Del` | Delete | Timeline step, body or sketch curve, with what depends on it |
| `F6` | Fit | Also a double-click of the middle mouse button |
| `Ctrl+Alt+V` | Show / hide the ViewCube | |
| `Ctrl+Z`, `Ctrl+Y` | Undo, Redo | One step per Fusion step where possible |
| `Ctrl+S`, `Ctrl+N`, `Ctrl+O` | Save, New design, Open | |
| `Esc` | Stop the tool; a second Esc clears the selection | Never leaves a sketch |

Sketch keys (the SKETCH tab is open):

| Fusion key | SciForge | Notes |
|---|---|---|
| `L` | Line | Type the length, `Tab`, the angle, `Enter`. Click the first point to close; double-click the end to end the chain; `Esc` leaves the tool |
| `R` | 2-point rectangle | |
| `C` | Centre-diameter circle | Type the diameter |
| `D` | Sketch Dimension | Click a curve (or two), place, type, `Enter`; double-click a dimension to change it |
| `T` | Trim | Click the piece (it lights up red), or press and drag across several pieces |
| `O` | Offset | |
| `X` | Construction on / off | With nothing selected: new curves become construction |
| `P` | Project | |
| `M`, `Del`, `Ctrl+C/X/V` | Move/copy, delete, copy/cut/paste sketch curves | |
| hold `Ctrl` while placing a point | No snapping, no automatic constraints | |
| `Enter` | Completes the tool (with a value typed: draws the shape) | |

## Mouse (Fusion's default layout)

| Action | SciForge |
|---|---|
| Middle drag | Pan |
| `Shift` + middle drag | Orbit (constrained: turns and tilts, never rolls; Free Orbit in the navigation bar) |
| Wheel | Zoom at the pointer |
| Double middle click | Fit |
| `Ctrl` + `Shift` + middle drag | Zoom by dragging |
| `Shift` + middle click on the model | Set the orbit centre there (green dot) |
| Right-click | Marking menu: 8 commands around the pointer plus a list; while a command runs, **OK** at 3 o'clock and **Cancel** at 9 o'clock |
| ViewCube | Click a face, edge or corner; drag to orbit; right-click: Go Home, Orthographic / Perspective, Set Home |
| Click inside a closed sketch area | Picks the profile (`Shift` / `Ctrl` add); `E` or `Q` use it |

## Where things are

- **DESIGN** workspace, SOLID tab: CREATE, MODIFY, ASSEMBLE, CONSTRUCT, INSPECT, INSERT, SELECT
  groups in Fusion's order. Greyed entries say "Not available in SciForge yet".
- **SKETCH** tab appears while a sketch is open; **Finish Sketch** is in the ribbon, the palette
  and the right-click menu.
- **Browser** (left): bodies, sketches, construction, with eye toggles; right-click a body or
  component > **Opacity Control** to make it see-through; the row of the body under the mouse
  in the 3D view lights up. **Timeline** (bottom):
  every step; drag the marker, double-click a step to edit it, right-click for Delete /
  Suppress. **Navigation bar** (bottom centre): orbit mode, look at, pan, zoom, fit, display.
- **Data Panel** (`Ctrl` + `Alt` + `P`): your project folder's designs with pictures and
  versions; search, sort, click a design for its versions and what uses it; **drag a design
  into the 3D view of an open design to insert a copy of it**.
- **SciForge menu** (top left): FreeCAD's own menus, Change Parameters, Diagnostics (the text
  to send when something misbehaves).

## Files

- Designs are FreeCAD documents (`.FCStd`), saved wherever you like (the NAS, a folder); no
  cloud, no account.
- Fusion's `.f3d` files cannot be opened. Export from Fusion as **STEP** (keeps solids) or
  **3MF / STL** (meshes) and insert that. SciForge exports STEP, STL, 3MF, OBJ, DXF, SVG.
- A design saved by SciForge opens in FreeCAD 1.1 too (its features are FreeCAD features).

## Not the same as Fusion (yet)

- One component per design (components, joints and versions are the next work items).
- Sheet metal, plastic rules, simulation, rendering, CAM and the cloud do not exist here.
- Where a dialog differs from Fusion's, the gap is listed at the end of the matching
  `docs/sciforge/parity/*.md`; tell Luca's assistant what Fusion does and it gets built.
