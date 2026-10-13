# Parity spec: Assemble > Joints (outline 7.10; plan.md "Next" item 3)

Status: **first full pass, not yet signed off by Luca.** Everything marked **(assumed)** is a
guess at a Fusion detail no source settled; everything marked **(SciForge)** is a deliberate
difference, explained.

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
stay inside them); Rest is where the component is put when the dialog closes **(assumed)**.
Fusion also lets you drag flag handles for the limits in the canvas.

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

## How it is built (FreeCAD 1.1.4's Assembly solver underneath)

| Fusion | SciForge / FreeCAD |
|---|---|
| Joint | an `App::FeaturePython` in the hidden assembly's `Assembly::JointGroup`, proxy `sciforge.joints.JointProxy` (a subclass of FreeCAD's `JointObject.Joint`, so FreeCAD's solver understands it); `SciForgeType` Joint / AsBuiltJoint |
| Rigid, Revolute, Slider, Cylindrical, Ball | FreeCAD's Fixed, Revolute, Slider, Cylindrical, Ball joint types |
| Planar | FreeCAD's Distance joint between two flat faces at distance 0 (the solver's planar constraint: slide in the plane, turn about the normal) |
| Pin-Slot | that planar joint plus a hidden helper joint (Distance 0 between a point and a plane whose normal is the slot's side: the pin stays on the slot's line); the helper follows the joint (`SciForgeParent`) and goes with it |
| Joint origin's place | computed by SciForge from the picked element and snap (`SciForgeSnap1/2`), as `Placement1/2` relative to the component (FreeCAD's convention), so it follows geometry changes; as-built places are stored once |
| Offsets, Angle, Flip | component 1 is placed by SciForge's own maths (`joints_core.aligned_frame`); FreeCAD's `preSolve` is not used (it keeps the closest of mated / un-mated, Fusion always mates unless flipped) |
| Limits | FreeCAD's `EnableAngleMin/Max`, `AngleMin/Max`, `EnableLengthMin/Max`, `LengthMin/Max`; the solver only honours them while dragging, so Drive / Animate clamp to them themselves; Rest is SciForge's (`SciForgeRest`) |
| Ground | FreeCAD's `GroundedJoint` (`ObjectToGround`), in the JointGroup, drawn by SciForge (no lock pad in the 3D view; an anchor on the browser row) |
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
