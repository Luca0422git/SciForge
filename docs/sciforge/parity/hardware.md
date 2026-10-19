# Parity spec: Hardware library (INSERT > Hardware...)

Luca 3D-prints parts that take screws, nuts, washers, heat-set inserts and magnets (a
Raspberry Pi 5 case, for example). He wanted to insert real-size hardware offline and get the
matching hole in the part as a normal timeline step. Implemented in
`src/Mod/SciForge/sciforge/`: `hardware_core.py` (the tables and rules, no FreeCAD, unit
tested), `hardware.py` (the solids, the component, the Hole step), `hardware_ui.py` (the
dialog). Status: **first pass**.

## Behaviour spec (what Fusion does), with sources

Fusion has three ways to bring a standard part in, all online. Source column: **Autodesk**
(Autodesk's own pages, read through search excerpts: help.autodesk.com and autodesk.com
could not be fetched from the sandbox), **Forum** (Autodesk Community / course pages),
**Guess** (no source found in this session).

| # | Fusion | Source |
|---|---|---|
| 1 | INSERT > **Insert McMaster-Carr Component** opens McMaster-Carr's online catalogue; you open a part's page, pick a 3D format (STEP or SAT only) and save: the part comes into the design as a **component** | Autodesk: [How to insert a standard part from McMaster-Carr](https://autodesk.com/de/support/technical/article/How-to-insert-a-standard-part-into-a-Fusion-360-design), [Insert McMaster-Carr Component dialog](https://help.autodesk.com/cloudhelp/ENU/Fusion-Model/files/GUID-90FD5419-A8AF-4A7C-AB1E-75D027077709.htm) |
| 2 | Only its part number, name and description can be edited afterwards (it is a plain imported solid) | Autodesk: Insert McMaster-Carr Component dialog (search excerpt) |
| 3 | The inserted part is then positioned with a **Joint** (tutorials use Rigid; Flip turns a fastener that lands the wrong way round) | Forum: [Lynda/LinkedIn course "Inserting McMaster-Carr components"](https://www.lynda.com/Fusion-360-tutorials/Inserting-McMaster-Carr-components/2810401/2874131-4.html), [VDCI fastener assemblies guide](https://vdci.edu/learn/cad/inserting-fastener-assemblies-in-fusion-360-step-by-step-guide) |
| 4 | INSERT > **Insert a manufacturer part** (TraceParts): a browser window, log in, pick a supplier (400+ catalogues) and a part, set its properties, send it to Fusion: it arrives as a component. Greyed out in a Part document (it makes components) | Autodesk: [Insert manufacturer parts](https://help.autodesk.com/cloudhelp/ENU/Fusion-Model/files/GUID-5A946771-D1A7-4817-A43E-2869EFFC1FA5.htm); Forum: [Inserting components menu not working?](https://forums.autodesk.com/t5/fusion-support-forum/inserting-components-menu-not-working/m-p/13995647/highlight/true) |
| 5 | INSERT > **Insert Fastener** (cloud fastener library, 2024): search / filter / browse folders, then select a **circular edge, a cylindrical or conical face, a sketch point or another fastener** to position it; for a countersunk fastener the circular edge of the cone | Autodesk: [Insert a fastener](https://help.autodesk.com/cloudhelp/ENU/Fusion-Model/files/SLD-INSERT-FASTENER.htm), [Insert Fastener reference](https://help.autodesk.com/cloudhelp/ENU/Fusion-Model/files/SLD-REF-INSERT-FASTENER.htm) |
| 6 | Size **Automatic**: the size is chosen from the selected geometry; hovering a hole previews the fastener at the hole's size; the length from a manipulator or the Nominal Length list | Autodesk: Insert a fastener; [Fusion blog: Integrated Fasteners Library](https://www.autodesk.com/products/fusion-360/blog/autodesk-fusion-fasteners-library/) |
| 7 | **Select Similar** (on by default) fills every identical hole on the same face | Autodesk: Insert Fastener reference; Fusion blog |
| 8 | Fasteners are placed with **joints** and follow the model when it changes; Auto sizes flag a fastener that no longer fits | Autodesk: Fusion blog; Insert Fastener reference |
| 9 | **Flip** reverses the joint direction (only for a fastener placed on a sketch point) | Autodesk: Insert Fastener reference (search excerpt) |
| 10 | Nuts and washers are inserted the same way; a washer placed on a bolt pushes it out | Autodesk: Insert a fastener; Forum: [Insert Fastener issues](https://forums.autodesk.com/t5/fusion-design-validate-document/insert-fastener-issues/td-p/12937842) |
| 11 | The size and length can be changed later from the browser or timeline; the height is changed by editing the joint | Forum: Insert Fastener issues |
| 12 | Insert Fastener does **not make holes**: it fills holes made with the Hole command (third-party add-ins cut holes for screws) | Forum: search excerpts of [Hole wizard idea](https://forums.autodesk.com/t5/fusion-360-ideastation/hole-wizard/idi-p/5738407) and the App Store listings |

## What SciForge does

| Fusion | SciForge |
|---|---|
| Online catalogues (McMaster-Carr, TraceParts, the cloud fastener library) | **INSERT > Hardware...**: SciForge's own tables, **offline**: ISO 4762 socket head, ISO 7380 button head, ISO 10642 countersunk, ISO 4032 hex nut, ISO 7089 washer, heat-set inserts M2-M5, round magnets 3x2 ... 20x3 |
| A downloaded STEP solid, with modelled threads or not | A solid built from the tables; threads not modelled (plain cylinders at the nominal diameter, like a cosmetic thread); hexagon sockets and heads as plain hexagons; the size in the name ("M3x10 ISO 4762") |
| Inserted as a component | The same: a new component named after the part, under the active component, with one body ("Body1") and one step **Hardware** |
| Positioned afterwards with a Joint | Placed by the click: a **round edge** (a hole's rim: on its axis, head on the rim's face; a boss's edge) or a **flat face** (where you clicked, square to the face). One selected before the command is taken at once. Flip turns the part round |
| Size Automatic from the hole | A rim of a hole that is already there sets the size from its diameter (a clearance hole of any fit, a tap drill, the counterbore / countersink of the head, an insert's hole, a magnet's pocket; the current size wins a tie) |
| Does not make holes | **Make the hole too** (on by default, off by itself on the rim of a hole that is there): a normal **Hole** step in the clicked body, SciForge's own Hole feature (editable in the Hole dialog): screws a clearance hole (Fit Close / Normal / Loose, ISO 273) with, when **Head sunk in**, the counterbore (socket head: DIN 974-1, the Hole dialog's numbers; button head dk + 1 mm) or the 90 degree countersink (ISO 10642, the head's theoretical diameter, flush); Hole depth Through All or Screw length; nuts and washers a clearance hole through; inserts the insert's hole 1 mm deeper than the insert; magnets the diameter + Clearance (0.2 mm) as deep as the magnet |
| Live preview on hover | Live preview after the click: the part and its hole appear at once and follow every change in the dialog |
| One undo step per insert | Same: the component, its body, its step and the Hole step are one undo step (Cancel / Esc removes all of them) |
| Edit size and length from the timeline | Double-click the **Hardware** step: the dialog opens with everything as left (type, standard, size, length, place, hole options); the hole follows; a new click moves the part (and its hole) |
| Follows the part through joints | Placed once: when the part changes, edit the Hardware step (or add a joint) to put it back on its hole. **Gap** |

Every Hardware step keeps its options and where it was clicked as JSON (hidden property
`SciForgeHardware` of the step).

### Sizes (the tables in `hardware_core.py`)

| Part | Sizes | Dimensions used | Source |
|---|---|---|---|
| ISO 4762 socket head cap screw | M2-M8, lengths of the standard series within the standard's range (M3: 5-30) | dk, k, socket s, socket depth t | ISO 4762 (the usual largest dimensions) |
| ISO 7380-1 button head | M3-M8 (the standard starts at M3) | dk, k, s, t; the head is a spherical cap | ISO 7380-1; length ranges: the commonly sold ones, **Guess** |
| ISO 10642 countersunk | M3-M8 | theoretical dk, k = (dk - d) / 2, s, t; the length counts the head | ISO 10642 |
| ISO 4032 hex nut | M2-M8 | s, m | ISO 4032 |
| ISO 7089 washer | M2-M8 | d1, d2, h | ISO 7089 |
| Heat-set insert | M2-M5: outside 3.6 / 4.6 / 4.6 / 6.3 / 7.1, length 3.0 / 4.0 / 5.7 / 8.1 / 9.5, hole 3.2 / 4.0 / 4.0 / 5.6 / 6.4 | the "standard length" set most 3D-printing sellers list | **Guess** (vendor data varies; e.g. [a reseller's comparison table](https://www.3djake.com/cnc-kitchen/threaded-inserts-m4-standard)); hole 1 mm deeper than the insert, **Guess** |
| Round magnet | 3x2, 4x2, 5x2, 5x3, 6x2, 6x3, 8x2, 8x3, 10x2, 10x3, 10x5, 12x3, 15x3, 20x3 | diameter x thickness | common neodymium disc sizes, **Guess**; pocket clearance 0.2 mm, **Guess** |

### Guesses (to confirm in Luca's Fusion, or to change if he wants)

- The command's place and name: INSERT > Hardware..., after Insert STEP (Fusion's own is
  "Insert Fastener"; SciForge uses its own wording).
- The part sits on the face where the rim or face was clicked, head out of the part;
  a sunk socket / button head sits on the counterbore's floor.
- A button head sits on the face by default (its hole has no counterbore); socket and
  countersunk heads are sunk by default.
- Screw holes are Through All by default.
- Nuts and washers get a plain clearance hole (no hexagon nut trap).
- The heat-set insert size set, the 1 mm extra depth, the magnet sizes and the 0.2 mm
  pocket clearance.
- The look: screws dark (black oxide), nuts and washers satin steel, inserts brass,
  magnets polished steel.
- Editing a Hardware step keeps the part it is in active (the timeline otherwise makes
  the edited step's component the active one).

### Known gaps (with the reason)

- No joint is made: the part does not follow its hole when the part changes; edit the
  Hardware step to put it back (Fusion's fasteners follow through joints).
- No hover preview before the click, no Select Similar (one hole at a time), no sketch
  point or cylindrical face as the place (a rim or a flat face).
- Metric only (no inch screws); no hex head bolts (ISO 4017), set screws, nylon lock nuts,
  square nuts; no nut trap (hexagon pocket) for a nut.
- Threads are never modelled (Fusion's library parts may have them).
