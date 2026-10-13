# Parity spec: Assemble > Joints (outline 7.10; plan.md "Next" item 3)

Implemented in `src/Mod/SciForge/sciforge/`: `joints_core.py` (pure maths, unit tested),
`joints.py` (the document side, no Qt: joints, grounds, rigid groups, joint origins,
positions, the solver check, the delete / component watch), `joints_ui.py` (the dialogs,
the snap hover, the animation, the commands), plus the browser (`browser_core.py`,
`browser_ui.py`), the timeline kinds (`timeline_core.py`), the ribbon (`ribbon_config.py`),
the J key (`config.py`) and the icons (`tools/sciforge/make_icons.py`).
Tests: `SciForgeTests/unit/test_joints_core.py` (28 tests) and five GUI scenarios with real
clicks (see **Tests** at the end).

Status: **built and tested with real clicks, not yet signed off by Luca.** Everything marked
**(assumed)** is a guess at a Fusion detail no source settled; everything marked
**(SciForge)** is a deliberate difference, explained.

## Sources (read before building; nothing copied from them but the behaviour)

Autodesk's own help and learning pages (reached through search-result excerpts: the help site
itself is not reachable from the build sandbox), forum answers by Autodesk staff, and one
third-party guide:

1. Autodesk Fusion help, *Create a joint* (ASM-CREATE-JOINT): the Position tab's Mode
   (Simple = "Select a Snap point to place the joint origin"; Between Two Faces = "Select
   Plane 1 and Plane 2 to center the joint origin between them, then select a Snap point";
   Two Edge Intersection), Angle ("Drag the rotation manipulator handle or enter an exact
   angle"), Offset X/Y/Z ("Drag the move manipulator handle or enter an exact distance"),
   Flip ("Click to flip Component 1 over the Joint Origin"); the Motion tab: Type, a Rotate
   axis for Revolute, a Slide axis for Slider, both for Cylindrical / Pin-Slot, Pitch and Yaw
   axes for Ball ("a gimbal with three nested rotations").
2. Autodesk Fusion help, *Create an as-built joint* (ASM-CREATE-AS-BUILT-JOINT): components
   stay where they are; for any type but Rigid a Position (Simple / Between Two Faces / Two
   Edge Intersection); Maximum ("Specify the maximum limit on the range of motion"), Rest
   ("Specify the resting position for components within the range of motion"), Preview Motion.
3. Autodesk Fusion help, *Create a joint origin* (ASM-CREATE-JOINT-ORIGIN) and Autodesk's
   assemblies course: Simple mode "Select a Snap point"; on a face the snap icons mark
   "endpoints, edge or arc midpoints, the face centroid, and arc centers".
4. Autodesk Fusion help, *Ground and unground components* (ASM-GROUND-TO-PARENT-COMMAND):
   right-click the component in the Browser; Ground To Parent / Unground From Parent; a
   grounded component is "marked with an anchor icon" (Autodesk blog); grounding "prevents
   that component from moving and provides a stable reference point".
5. Autodesk Fusion help, *Create a rigid group of components* (ASM-CREATE-RIGID-GROUP): pick
   two or more components in the canvas or Browser, "Include Child Components", OK; "the group
   is locked in place and appears as a feature in the Timeline"; right-click the feature >
   Edit Rigid Group to add or remove components.
6. Autodesk Fusion help, *Capture or revert position of components* (ASM-CAPTURE-POSITION) and
   the blog *How To Use Capture or Revert*: after a component is moved the POSITION panel
   appears in the toolbar; Capture Position records the moved components' positions "stored on
   the timeline as a featured position"; Revert returns them "to their most recently captured
   position", no dialog; a command that depends on positions (Joint Origin, Joint) asks
   whether to capture or revert first.
7. Autodesk Learn, *Create realistic motion in assemblies* and *Define joints for component
   relationships*: right-click a joint in the Joints folder: Drive Joints ("giving it a very
   specific position"), Edit Joint, Edit Motion Limits (Minimum, Maximum, Rest; "Flags show on
   the canvas"; limits "only affect the specified joint"), Lock Motion, Suppress, Animate
   Joint ("the movement of the joint only"), Animate Joint Relationships; "Drag the gear to
   preview its circular motion".
8. Autodesk blog *Joints vs. Mates, and Moving Things Around in Autodesk Fusion* and an
   Autodesk engineering director on the forum (*rigid joint discrepancy in maintaining spatial
   relationships*): "The entire difference between Joint and As-Built Joint is that the latter
   does not require you to select geometry"; an as-built joint cannot follow later geometry
   changes.
9. Autodesk blog *Joints and constraints in Autodesk Fusion* and the Noble Desktop guide
   *Understanding Joints in Fusion 360*: the seven types and their degrees of freedom; "hit
   Animate to continue the animation"; Fusion animates the two parts after the second pick;
   Esc stops an animation.
10. Fusion API reference: `JointTypes` (Rigid 0, Revolute 1, Slider 2, Cylindrical 3,
    PinSlot 4, Planar 5, Ball 6), `JointLimits` (isMinimumValueEnabled / isMaximumValueEnabled
    / isRestValueEnabled), `RigidGroups.add(occurrences, includeChildren)`.

## What Fusion does (the behaviour copied)

### Joint (J; ASSEMBLE > Joint)

1. The dialog opens with the Component 1 snap box waiting (blue). Hover a component: snap
   points light up on the element under the mouse: a face's centre, its corners, the midpoints
   of its straight edges and the centres of its round edges; an edge's ends, middle and (for
   an arc) centre; a corner itself. The nearest snap is highlighted and a small triad shows
   where the joint origin would be and how it points (Z along the face normal / edge / axis).
2. Click: component 1's joint origin is set; the triad stays. The Component 2 box waits.
3. Click a snap on **another** component: component 1 moves so that its joint origin sits on
   component 2's (faces mate: the two Z axes point against each other), then the motion is
   previewed: the joint animates through its freedom and comes back.
4. Position tab: Mode (Simple; Between Two Faces and Two Edge Intersection), Offset X / Y / Z
   (along component 2's joint origin axes), Angle (about its Z), Flip (component 1 turned over
   the joint origin). Motion tab: Type (Rigid, Revolute, Slider, Cylindrical, Pin-Slot, Planar,
   Ball) with the axis choices of (1), Animate, and the motion limits (Minimum / Maximum /
   Rest). OK / Enter keeps it, Cancel / Esc puts component 1 back.
5. The joint appears in the browser's **Joints** folder and as a step in the timeline;
   double-click (Edit Joint) reopens the dialog. Right-click: Edit Joint, Edit Joint Limits,
   Drive Joints, Animate Joint, Suppress, Delete.
6. Picking a new Type plays the new motion once (the same preview as after the second
   pick); the Animate button plays it until it is pressed again.
7. A pick can be cleared (the box's clear button): the component that moved goes back and
   the box waits again **(SciForge: the whole dialog's change is taken back and a fresh undo
   step starts, so a ground the joint added goes too)**.
8. A joint origin made with Joint Origin can be picked in the 3D view or on its browser row
   (the snap is the joint origin itself).

### As-Built Joint (ASSEMBLE > As-built Joint)

Pick two components (click anywhere on each, or in the browser), choose the Type; for any type
but Rigid pick a Position (a snap point: the axis / origin of the motion). Nothing moves. The
joint does not follow later geometry changes of the picked position's part (as-built = "where
they are now").

### Joint Origin (ASSEMBLE > Joint Origin)

One snap pick with the same hover, plus Offset X / Y / Z, Angle, Flip: a joint origin (a small
triad) stored in the component, listed in the browser (Fusion: a Joint Origins folder in the
component) and in the timeline. It can be clicked as a snap by Joint and As-Built Joint.

### Ground / Unground

Right-click a component (browser): Ground; it cannot move; the row shows an anchor. Unground
frees it. Fusion needs no grounded component for a joint to work. **(SciForge)** FreeCAD's
solver needs one fixed part, so when neither component of a new joint is held by anything
SciForge grounds **component 2** of that joint and says so in the dialog; the ground is listed
(anchor on the body's row) and can be removed with Unground.

### Rigid Group

Pick two or more components, Include Child Components, OK: a Rigid Group step; the components
keep their relative places (as-built) and move as one. Edit Rigid Group (double-click) adds or
removes members. Suppress / Delete free them.

### Joint limits (Edit Joint Limits; also in the Joint dialog's Motion tab)

Minimum, Maximum, Rest, each with a check box and a value (an angle for Revolute, a distance
for Slider, both for Cylindrical). The motion stops at the limits (Drive Joints and Animate
stay inside them); Rest is where the component is put when the dialog closes with OK
**(assumed: Fusion's component returns to its rest after a drag)**; a Rest outside the
limits is refused with a message. A limit switched on starts at the joint's value now, so
switching it on moves nothing; a joint standing outside new limits goes to the nearest one.
Changing only limits never re-places the component (it stays where it was driven).
Fusion also lets you drag flag handles for the limits in the canvas.
**(SciForge)** Edit Joint Limits opens the joint's own dialog on its Motion tab (an
as-built joint's one page) instead of Fusion's separate small dialog.

### Drive Joints

Pick a joint (browser row, timeline step or a jointed component); a value box (Rotation in
degrees, Distance in mm; Cylindrical has both) with a slider over the joint's range; the
components follow live; Animate plays through the range and back; OK keeps the position (the
POSITION panel then offers Capture Position / Revert), Cancel puts everything back.

### Capture Position / Revert

After components were moved (Drive Joints), Fusion shows a POSITION panel: Capture Position
records the new positions as a step in the timeline ("Position N"); Revert returns the
components to the last captured position (or, without one, to where the joints had put them).
A command that depends on positions (Joint, Joint Origin) first asks to capture or revert.
**(SciForge)** the panel cannot appear and disappear in the ribbon yet: both entries live in
the ASSEMBLE menu and are greyed while nothing was moved.

### Delete, Suppress, Undo, save

Deleting a component deletes its joints (Fusion); deleting a joint leaves the components where
they are. Suppress turns a joint off (the component is free) and Unsuppress puts it back. Every
command is one undo step. Joints, grounds, rigid groups, joint origins and captured positions
are saved with the design and work again after reopening.

SciForge does the deleting inside the delete itself (whoever deletes: the browser, the
timeline, a component's Delete, a script), so **one Ctrl+Z brings the body and its joints
back**: the joints, Pin-Slot helpers and rigid-group links on the part, its ground, a rigid
group left with one member, and the joint origins inside it. Deleting a body that sits
inside a component removes the joints on that body only. Deleting a joint or a rigid group
from the timeline or the browser takes its hidden helpers with it.

### When the joints fight each other

FreeCAD's solver can report success on an arrangement that breaks a joint (its equations
also accept a half turn, so it may flip a part rather than fail). After every solve SciForge
checks each active joint itself (origins on top of each other, axes the same way, as the
type demands) and treats a broken one as a failure: the dialog says **"The joints cannot all
be satisfied together: <joint> fights the others"**, OK is refused, Cancel puts everything
back. (Fusion shows a similar warning and leaves the joint red.)

## How it is built (FreeCAD 1.1.4's Assembly solver underneath)

| Fusion | SciForge / FreeCAD |
|---|---|
| Joint | an `App::FeaturePython` in the hidden assembly's `Assembly::JointGroup`, proxy `sciforge.joints.JointProxy` (a subclass of FreeCAD's `JointObject.Joint`, so FreeCAD's solver understands it); `SciForgeType` Joint / AsBuiltJoint |
| Rigid, Revolute, Slider, Cylindrical, Ball | FreeCAD's Fixed, Revolute, Slider, Cylindrical, Ball joint types |
| Planar | FreeCAD's Distance joint between two flat faces at distance 0 (the solver's planar constraint: slide in the plane, turn about the normal) |
| Pin-Slot | that planar joint plus a hidden helper joint (Distance 0 between a point and a plane whose normal is the slot's side: the pin stays on the slot's line); the helper follows the joint (`SciForgeParent`) and goes with it |
| Joint origin's place | computed by SciForge from the picked element and snap (`SciForgeSnap1/2`), as `Placement1/2` relative to the component (FreeCAD's convention), so it follows geometry changes; as-built places are stored once |
| Offsets, Angle, Flip | folded into joint origin 1 as stored for the solver (`joints_core.stored_offset`): the solver makes the two stored origins coincide, which is where Fusion puts component 1; SciForge first moves the free component there exactly (`joints.align`, `joints_core.mate_transform`, `keep_heading` so it keeps its heading), then solves. FreeCAD's `preSolve` is not used (it keeps the closest of mated / un-mated, Fusion always mates unless flipped) |
| Solver check | `joints.satisfied` / `broken_joints` after every `solve` (code -2 = "cannot all be satisfied") |
| Limits | FreeCAD's `EnableAngleMin/Max`, `AngleMin/Max`, `EnableLengthMin/Max`, `LengthMin/Max`; the solver only honours them while dragging, so Drive / Animate clamp to them themselves; Rest is SciForge's (`SciForgeRest`) |
| Ground | FreeCAD's `GroundedJoint` (`ObjectToGround`), in the JointGroup, drawn by SciForge (no lock pad in the 3D view; an anchor on the browser row; the row's menu says Ground / Unground) |
| Delete with its part | `joints._DeleteWatch` (a document observer): `remove_joints_of(part)` runs while the part is being deleted, inside the same undo step; never during undo / redo or while a file closes |
| Rigid Group | a `RigidGroup` FeaturePython step (members, Include Child Components) whose hidden helper Fixed joints (as-built placements) sit in the JointGroup |
| Joint Origin | a `PartDesign::CoordinateSystem` datum in the body (or an `App::LocalCoordinateSystem` in a component), `MapMode Deactivated`, placed by SciForge; FreeCAD's joints take an LCS as a reference |
| Capture Position | a `Position` FeaturePython step holding every part's placement; Revert re-applies the newest one (or the positions after the last joint) |
| Drive / Animate | the moving side's placement is set from the joint value (`joints_core.driven_frame`) and the assembly is solved so the rest of the chain follows; a QTimer plays the animation |
| Joints folder, timeline steps | `browser_core` folder "Joints" (kind `joint`) and "Joint Origins"; `timeline_core` kinds `joint`, `as_built_joint`, `joint_origin`, `rigid_group`, `position` |

### The component contract (agreed with the Components work)

- A Fusion **component** is an `App::Part` at the document root (nested components are
  nested `App::Part`s); its bodies are `PartDesign::Body` objects inside it. The **root
  component is the document itself**: bodies with no component sit at the document root.
- Joints work on **parts**: the topmost object of what was clicked, a root `PartDesign::Body`
  or a root `App::Part` component (a `Part::Feature` solid at the root, e.g. an imported
  part, counts too). A body inside a component moves with its component; everything in a
  nested component moves with its top-level component (Fusion moves the nested component
  itself: gap below).
- The solver needs one `Assembly::AssemblyObject`. SciForge makes **one hidden root
  assembly** (`SciForgeAssembly`, Label "Assembly", `Placement` identity, never shown in the
  browser or the timeline) on the first joint, ground or rigid group. It **owns only the
  joints** (its `Joints` group); bodies and components stay where they are in the document
  (FreeCAD's solver reads a part's `Placement` from the joint references, not from the
  assembly's group: checked in the probes `scratchpad/joints/probe1-3.py`). So a design with
  two plain bodies and no component is jointed by `J`, pick, pick, OK; a design with
  components joints the components by the same code path. The Components work must not move
  bodies into the assembly object nor make a second `Assembly::AssemblyObject`.
- Motion is a change of the part's `Placement` (the body's or the component's), never of the
  solids inside: later modelling steps keep working, and a `Move/Copy` step inside a body
  composes with it.
- A joint reference is `[part, ["<body>.<element>", ...]]`: the part the solver moves, then
  the path to the body (or joint-origin datum) holding the element. Bodies inside one
  component are one part: a joint between two of them is refused ("Both picks are on
  Component1").
- **Bodies moving between components** (the components work's Create Components from Bodies,
  Move to Component, a drag in the browser): `joints.reroot` (run by the same observer on
  every component's `Group` change, inside the same undo step) points the joints, the grounds
  and the rigid groups at the part that now holds the body; a joint whose two sides end up in
  one component is switched off (Suppressed) with a warning. Tested headless with components
  made the way `components.py` makes them, and in `joints_components`.
- **Extrude > New Body from another body's sketch** (how the test designs are made): the
  hidden profile binder (`extrude._binder`) no longer follows the sketch's *global* place
  (FreeCAD's relative binding moved the new body's own geometry each time a joint moved one
  of the two bodies): it copies the profile in the sketch body's frame, frozen where that
  body stood when the extrude was made (`SciForgeFrame` on the binder).

Merge notes for the Components work (both branches touch `browser_core.py`,
`browser_ui.py`, `timeline_core.py`, `ribbon_config.py`, `config.py`, `bodies_gui.py`,
`extrude.py`):

- Add **Ground** to the component row's menu (`MENUS["component"]`, handled like the body
  row's: `_joint_action("toggle_ground", obj)`, text Unground when `node["grounded"]`) and
  set `"grounded"` on component rows (`_grounded_names` already collects component names).
- `components.place()` / `from_bodies()` move bodies without keeping their global place. A
  joint moves a whole component, so its `Placement` stops being identity: a body dragged into
  or out of a moved component then jumps. Fusion keeps the body where it is; the fix belongs
  in `components.place()` (`body.Placement = new_container_global⁻¹ * old_global`).
- With the components work's "allow duplicate labels" on, FreeCAD stops renaming a new
  "Rigid 1" to "Rigid 002" after an undo left the old label registered (seen once in
  `joints_asbuilt_group`, cosmetic).

## Known gaps (never faked: listed here)

| Fusion | Why not (yet) |
|---|---|
| Position Mode "Between Two Faces" and "Two Edge Intersection" | only Simple (a snap point) is built; the Mode box shows the other two greyed |
| Dragging a component by hand along its joints (Fusion's canvas drag) | not built; Drive Joints moves them |
| Limit flags dragged in the canvas | values typed in the dialog only |
| Pin-Slot and Ball limits; Planar (no limits in Fusion either) | FreeCAD limits exist for Revolute, Slider and Cylindrical only |
| Ball: Pitch / Yaw axis choices, Pin-Slot custom axes | a Ball turns about its origin whatever the axes; Pin-Slot takes Slide X or Y of the joint origin |
| Nested components move on their own | a nested `App::Part` moves with its top-level component (the solver reads one `Placement` per moving part) |
| The POSITION toolbar panel that appears after a move | Capture Position / Revert are menu entries, greyed while nothing moved |
| Motion Link, Contact Sets, Motion Study, Lock Motion, Animate Joint Relationships | not built (Motion Link stays greyed in the menu) |
| A joint between two ungrounded components leaves both free | FreeCAD's solver drops joints that are not chained to a grounded part, so SciForge grounds component 2 of such a joint (and says so); Unground it to free it |
| Joint names "Rigid1", "Rev1"... | SciForge names them "Rigid 1", "Revolute 1", ... **(assumed)** |
| Joint origins listed inside the component | the browser has a document-level "Joint Origins" folder (bodies have no child rows yet) |
| Files opened in plain FreeCAD | the joints' proxy classes are SciForge's: plain FreeCAD shows the parts where they are and warns about the missing module |
| Edit Joint Limits as its own small dialog | the joint's dialog opens on its Motion tab |
| Drive Joints / Animate Joint greyed for a Rigid joint in the menu | the entries are there and say "rigid: it has no motion" |
| A joint in error stays (red) when its geometry goes | SciForge deletes the joint with the body or component it was on (one undo step) |
| Two joints fighting: Fusion leaves the newest red but keeps it | SciForge refuses OK until it is changed or cancelled |
| Rigid Group of free components | FreeCAD needs a fixed part: the first member is grounded when nothing holds the group (not announced in the dialog yet) |
| Unground the only grounded part | FreeCAD's solver then drops every joint (Fusion's still work); ground another part |

## Tests (real FreeCAD 1.1.4, real clicks: `tools/sciforge/run_tests.sh --scenario ...`)

| Scenario | Paths (checks) |
|---|---|
| `joints_basic` | J, hover snaps, two picks, Revolute, OK, undo / redo; edit from the timeline (Angle, Offset Z, Flip, one-step undo); timeline Delete; same component twice refused; corner snap; Cancel; Esc; J with one body (85) |
| `joints_types` | every type on two boxes: Rigid, Slider (axis X, limits), Cylindrical, Pin-Slot, Planar, Ball, Revolute (limits, a refused Rest, Rest 10 on OK); the Animate button's motion is watched sample by sample (what turns, what slides, inside the limits); OK; one-step undo with the ground and the Pin-Slot helper (229) |
| `joints_asbuilt_group` | Ground / Unground from the browser with undo / redo; Joint Origin (hover, corner, Offset Z) picked by J from its browser row; As-Built Revolute (nothing moves, the axis where picked); Animate Joint + Esc; Edit Joint Limits; Rigid Group (the pin follows a drive, clamped at the limit); suppress / unsuppress the group; a joint the solver cannot satisfy (message, OK refused, Cancel); deleting a body takes its group and joint origin in one undo step (133) |
| `joints_drive` | Drive Joints (box, slider PageUp), undo / redo; Capture Position, drive, Revert Position; Edit Joint Limits (limit starts at the value, then clamps); Drive clamped at the limit, Cancel; Animate Joint + Esc; Suppress / Unsuppress from the timeline; save, close, reopen, drive again; deleting the jointed body, one undo step (107) |
| `joints_components` | a body inside an `App::Part` component (made like `components.from_bodies`): J picks through the component, the component moves (the body keeps its placement); Drive; the body leaves the component (the joint follows it), undo; the component deleted with its joint in one step, undo (46) |

