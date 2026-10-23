# Parity spec: Components (outline 7.2 browser, 7.10 Assemble; plan.md "Next" item 2)

Implemented in `src/Mod/SciForge/sciforge/`: `components_core.py` (pure logic, unit tested),
`components.py` (the document model, no Qt: dialogs, golden builder and headless tests use
it), `components_ui.py` (commands and the New Component / Move to Component dialogs),
`browser_core.py` + `browser_ui.py` (the component tree, activate ring, menus, drag and drop),
`timeline_core.py` / `timeline_ops.py` / `timeline_ui.py` (component steps, the component of
every step, the active component's filter), the New Component operation in `extrude.py`,
`revolve.py`, `sweep.py`, `loft.py` and their dialogs.
Tests: `SciForgeTests/unit/test_components_core.py` (16 tests), GUI scenarios
`components_basic.py` (9 paths), `components_extrude.py` (5 paths), `components_move.py`
(6 paths), all real clicks (helpers in `SciForgeTests/gui/component_steps.py`).
Status: **built and tested with real clicks, not yet signed off by Luca.** Part 2 (moving, copying, patterning components; components-2) is described in its own section below.

## Sources (Fusion's behaviour, researched before building; Autodesk's sites were not
reachable from the sandbox, so the summaries of their pages found by web search are cited)

1. Autodesk Fusion API user manual, "Documents, Products, Components, Occurrences, and
   Proxies": a component node is added to the browser for each new component; "clicking the
   radio button to the right of a component node in the browser activates that component";
   geometry made through the UI goes into the active component; "the root component is always
   active by default after opening or creating a document".
2. Autodesk Community, "How do you deactivate a component?" (accepted answer by an Autodesk
   community manager): to leave a sub-component you activate the root component, the top node
   in the browser; "you are always working inside an activated component. It may be the root".
3. Autodesk Community (several threads): activating a component routes new sketches to that
   component's Sketches folder and bodies to its Bodies folder.
4. Autodesk Learn, "Create a component within an assembly" and the course "Creating
   assemblies": the New Component dialog offers Standard / Sheet Metal, Internal / External,
   From Bodies, a Name, a Parent and Activate; "the new component appears at the bottom of
   the browser"; with Activate on it is activated as soon as it is created.
5. Autodesk Learn ("Creating assemblies") and the Community thread "Sketch to Component":
   Create Components from Bodies (right-click a body) makes a component with an Origin folder
   and a Bodies folder holding the body; the body's sketch "is still resident at the top level
   of the design" (a sketch outside the body stays where it was); several bodies give one
   component per body (thread "Move multiple bodies to new component"); a body called V-block
   gave a component called V-block.
6. Autodesk Fusion help, "Isolate" (GUID-38F2A3B4): "isolate selected bodies or components and
   hide all other objects. When you unisolate, visibility is restored to all objects that were
   visible before you used the isolate. Any objects that were hidden before isolation remain
   hidden." Community threads: Isolate is in the browser's right-click menu.
7. Autodesk Knowledge, "Unable to drag a body from one component to another": bodies are moved
   between components by dragging them in the browser (or cut / paste), which the timeline can
   refuse when it has errors.
8. Autodesk blog "Master the Timeline, Browser, & Preferences" and the Community threads
   "Timeline - All components rolling back", "My brain is fried trying to figure out
   components and timeline history": Fusion has one timeline for the design; activating a
   component "changes the timeline to show features specific to the activated component";
   rolling the marker before a component's creation makes the component disappear from the
   browser (so a component's creation is a step in the timeline).
9. Autodesk's Fusion shortcut list: no key for New Component, Activate or Isolate (Community
   thread "Keyboard Hotkey for Isolate/UnIsolate" asks for one). SciForge gives them none.
10. Extrude with Operation "New Component" (Community thread "along"): the result is a new
    component holding the new body; users then drag the sketch into it if they want it there,
    so the sketch stays in its own component.

Guesses (not found in a source, marked for Luca's Fusion check): the component's icon; that
the activate ring is drawn for every component row (Fusion may show it on hover only); the
default name "Component1" (Fusion numbers bodies "Body1", "Body2": components follow); that
Extrude > New Component activates the new component; whether From Bodies in the New Component
dialog makes one component per body (built so, like the right-click command).

## The model (a contract: Joints and other features rely on it)

| Fusion | SciForge / FreeCAD |
|---|---|
| A component holds bodies, sketches, construction geometry, joints and nested components | An `App::Part` container. Its name is its `Label`. Bodies (`PartDesign::Body`) are in `part.Group`; sketches, features and construction live inside their body (FreeCAD's PartDesign needs that), so they are in the component through the body. A nested component is an `App::Part` in an `App::Part`. SciForge tags its components with the string property `SciForgeType = "Component"`; an `App::Part` from elsewhere (an old FreeCAD file) is a component too. |
| The root component | The document itself: a design without components has no container, so every earlier file and single-body workflow is unchanged. |
| One active component (the radio button); new sketches, bodies and features go into it | FreeCAD's active-object slot `"part"` (`Gui.ActiveDocument.ActiveView.setActiveObject("part", obj)`) plus the rule that the active body (slot `"pdbody"`) lies inside it. `components.active_component(doc)` = the active body's container when a body is active, else the `"part"` slot, else the root (None). `components.set_active(component)` activates a component and makes its preferred body (the one active there last, else the oldest) the active body, or no body when it has none. `components.activate_body(body)` activates a body together with its component. |
| New work goes into the active component | `commands.find_body()` returns the active body, else a body inside the active component (made active); `commands.ensure_body()` creates one *inside the active component* when it has none (FreeCAD's Body command uses the `"part"` slot; SciForge moves the body if the slot lagged). Every command that works on "the body" (Create Sketch, Extrude, Hole, patterns ...) therefore works in the active component without knowing about components. |
| A file opens with the root active | FreeCAD stores no active objects: a reopened file has none, so the root is active. |
| Bodies are numbered per component (Body1 in every component) | `components.new_body_in(doc, container)`; FreeCAD's "allow duplicate labels" preference is switched on while SciForge is on (kept and given back like the viewer settings, `theme.VIEWER_SETTINGS`), else FreeCAD renamed the second Body1 to Body1001 and the component made from body "Body" to "Body001". |
| Components in the timeline | A component is a timeline step (kind `component`, icon `new_component`, called by the component's name) at its creation, hidden while the history marker stands before it (components-2) and never suppressed. Each step knows its component (`Item.component`, shown in the hover text). |

API for other features (all in `components.py`): `list_components(doc)`, `container_of(obj)`,
`component_of(obj)`, `is_inside(obj, component)`, `ancestors(obj)`, `bodies_in(doc,
component, recursive)`, `components_in(doc, component)`, `new_component(doc, label, parent)`,
`new_body_in(doc, container)`, `from_bodies(doc, bodies, parent, label)`, `place(obj,
component)`, `remove(doc, component)`, `active_component(doc)`, `set_active(component)`,
`activate_body(body)`, `preferred_body(doc, component)`, `isolate_hidden(doc, obj)`,
`move_targets(doc, moving)`. Nothing here opens an undo step except `remove` (one step); the
callers (dialogs, browser) wrap the rest in their own transaction.

## Browser

| Fusion | SciForge |
|---|---|
| Root row: Document Settings, Named Views, Origin, Bodies, Sketches, Construction, then the components | Same (`browser_core.build`), components in the order they were made. |
| Component row: eye, icon, name; inside: Origin, Bodies, Sketches, Construction, nested components | Same. The component's Origin folder lists the `App::Part`'s own origin planes and axes (the eye shows and hides them); Create Sketch on one of them puts the sketch on the body's plane of the same role (same place) inside the component. The root's Origin stays the active root body's (as before). |
| The activate radio button; the active component's name is bold | A ring at the end of every component row and of the design's row, filled blue for the active one; the name is bold. Click the ring (or double-click the row) to activate. Activating a component makes its last active body the active body (bold with a dot) or, with no body yet, none: the next sketch or body is made inside it. |
| Right-click a component: Activate, New Component, Show/Hide, Isolate / Unisolate, Find in Window, Find in Timeline, Rename, Delete (Fusion also has Ground, Rigid Group, Copy, Paste, Opacity Control, Selectable, Properties...) | Activate (not on the active one), New Component (the new one goes inside this component), Hide / Show, Isolate / Exit Isolate, Find in Window, Find in Timeline (selects the component's step and every step inside it), Move to Component (SciForge: a submenu with the root and the components it may go to), Rename, Delete. Joints entries belong to the Joints work. |
| Right-click a body: Create Components from Bodies, ... | Activate Body, Create Components from Bodies (every selected body gets a component named after it, where the body was), Hide / Show, Isolate / Exit Isolate, Find in Window, Find in Timeline, Move to Component, Rename, Delete. |
| Right-click the root row: New Component, Activate ... | Activate (when a sub-component is active), New Component (at the root), Show All Bodies, Show / Hide All Sketches, Rename. |
| Drag a body onto a component to move it there (also a component into a component) | Same, with a blue frame on the row it can be dropped on; the design's row is the root. One undo step. A component never goes into itself. Fusion refuses a drag while the timeline has errors; SciForge moves anyway (features keep their links; FreeCAD's PartDesign allows cross-component links). |
| A component's eye hides and shows the component; what is inside keeps its own eyes | Hiding sets the rows under it hidden and remembers which were shown; showing it again shows only those (its origin planes and the sketches its extrudes hid stay hidden; journey_plastic). Without a memory (hidden before a reopen) it shows all but the origin, sketches and construction. |
| Isolate a body or component: everything else hidden; Unisolate restores what Isolate hid | Same: what was hidden before stays hidden; a body's component (and its parents) stay shown. |
| Delete a component deletes its bodies and nested components | Same, one undo step (Undo brings all of it back). F2 renames, Del deletes, as for bodies. |
| Rename in place | Same (`Rename` or F2; Enter keeps, Esc cancels); the timeline's component step follows. |

## Commands

| Fusion | SciForge |
|---|---|
| ASSEMBLE > New Component (no key): dialog Type (Standard / Sheet Metal), Internal / External, From Bodies, Name, Parent, Activate (on) | `SciForge_NewComponent` on the ASSEMBLE tab: Name (Component1, Component2 ... proposed), Parent (a drop-down of the root and every component, the active one preselected; Fusion has a selection box), From Bodies (ticked by itself when bodies were picked before the command; the bodies are listed and more can be clicked in the window or the browser, a click on a listed one drops it), Activate (on). OK makes the component(s); Cancel makes nothing. Sheet Metal and External are out of scope (no sheet metal; one design per file). |
| Activate | `SciForge_ActivateComponent` (command search; the browser's ring is the usual way). |
| Isolate / Unisolate | `SciForge_Isolate`, `SciForge_Unisolate` (command search and the browser's menus). |
| Create Components from Bodies (right-click a body) | `SciForge_ComponentsFromBodies` and the browser's body menu. |
| Drag a body into a component | `SciForge_MoveToComponent` (a small dialog: what moves, Into) and the browser's drag or submenu. |
| Extrude / Revolve / Sweep / Loft, Box / Cylinder / Sphere / Torus / Coil / Pipe: Operation New Component | The fifth operation in these dialogs (the primitives since 2026-10-13: **Autodesk** SLD-BOX-SOLID / SLD-CREATE-SOLID-PRIMITIVE list it for Box and the other solid primitives): a new component (Component N, under the active component) with Body1 holding the result; the sketch stays in its own body (Fusion: the sketch stays, people drag it in if they want); the new component becomes active (guess). Editing the step keeps the same component and body; Operation reads New Component. Cancel (or a failed preview) removes the component again. Switching between New Body and New Component in the dialog (or in an edit) moves the result: out of the component (which goes), or into a new one. |

## Timeline

| Fusion | SciForge |
|---|---|
| One timeline for the design; a component's creation is a step | Same: the component step at its creation, called by its name; Rename / Delete / Roll Here / Find in Browser work on it; double-click activates it; it is never suppressed (greyed out); with the marker before it the component is hidden and gone from the browser (Part 2 below). Create Components from Bodies adds a step per component. |
| With a component active the timeline shows that component's features | Same: only the steps of the active component and of the components inside it show (the component's own step included); a grey note at the end counts the hidden ones and says how to see all (activate the design's row). The history marker stands before the first shown step after its slot. Dragging the marker or a step still acts on the whole design, as in Fusion. |
| Hover a feature: its name | Also "In component: X" for steps inside a component. |

## Part 2: moving, copying and patterning components (components-2, 2026-10-14)

Built in `src/Mod/SciForge/sciforge/`: `component_move.py` (the document side of moving a
component, its captured Move step, the marker), `component_move_ui.py` (the Move/Copy dialog
with Move Object Components; Set Pivot is in `move_ui.py`, shared with bodies),
`instances.py` (linked instances and Paste New), `clipboard_ui.py` (Copy / Paste / Paste New),
`component_pattern.py` (Pattern Type Components), `component_look.py` (Active Component
Visibility); Combine New Component (`combine.py`), Split Body with several tools (`split.py`).
Tests: scenarios `components2_move` (344 checks), `components2_copy` (277),
`components2_pattern` (278), `components2_bodies` (298), `components2_marker` (208); golden
models `comp_*`, `bodies_split_two_planes`, `bodies_combine_new_component`; unit tests in
`test_components_core.py`, `test_timeline_core.py`.

### Sources (Autodesk's sites cannot be opened from the sandbox: search excerpts are quoted)

11. **Autodesk** help, *Move or copy geometry* (SLD-USE-MOVE-COPY): Move Object Bodies /
    Components / Faces / Sketch Objects; Move Types Free Move, Translate, Rotate, Point to
    Point, Point to Position; "Click Set Pivot to adjust the pivot point of the manipulator.
    In the canvas, hover over the geometry you want to snap to, then click to place the pivot
    point, or enter exact values in the dialog"; "Optional (components only): Check the box
    next to Capture Position to capture the new position of the component"; "Check Create
    Copy".
12. **Forum**, *Rotating Assemblies?* and *How to rotate a rectangle?* (Autodesk staff): Set
    Pivot is a toggle; pick the pivot, then click the green check to finish; then type the
    angle.
13. **Forum**, *Move operation not included in Design History?*, *Capturing position*, *Move
    Component Workflow*: a component move is not a timeline step unless its position is
    captured (Capture Position in the dialog or the POSITION panel); the design is then in a
    "position pending" state; **Autodesk** blog *How To Use Capture or Revert*: Capture stores
    the position "on the timeline", Revert returns the component to its last location.
14. **Autodesk** help, *Copy / paste a component* (excerpt): "The new component is linked to
    the original component as an identical duplicate"; **Forum**, *Duplicating or copying
    components*: copies named "Comp: 1", "Comp: 2", editing one changes the other; Paste New
    "pastes independent copies"; **Autodesk** API, *Occurrences.addNewComponentCopy*: "the
    equivalent of copying and using the Paste New command ... a new component that has its
    own definition (sketches, features, etc.)".
15. **Forum** (*Can someone help me copy and paste new for a component?*): after the paste
    Fusion invokes Move with the new component selected.
16. **Forum** (*Break link between copied and pasted components*): "a move on a component
    applies only to that component instance".
17. **Autodesk** help, *Create a rectangular pattern*: Object Type "Components duplicates
    components in an assembly and distributes them according to the pattern settings".
18. **Autodesk** knowledge, *Changing the opacity of a body does not work in Fusion*: the
    preference "Active component visibility" (General > Design) dims the other components;
    **Forum** (*Turn Off See Through / Transparent Components*): other components "are dimmed
    to better show the active component".
19. **Autodesk** help, *Combine reference*: New Component "creates a new component with the
    results".
20. No source shows a "New Body" command that makes an empty body: bodies come from features
    (Operation New Body), components from New Component (Autodesk blog *Getting Started:
    Start with an empty design*, forum *What can bodies do that components cannot?*). Not
    built (brief item 6 asked "if Fusion has it").

Guesses (for Luca's Fusion check): Capture Position starts unticked; Paste goes into the
active component (the right-clicked component from the browser menu); Paste New is named
"Name (1)"; Esc in the Move after a paste keeps the paste where it was pasted; Move with
Create Copy of a component makes a linked instance; the dimmed transparency (75 %).

### What the user does (and what SciForge does)

| Fusion | SciForge |
|---|---|
| M, Move Object Components: click a component (in the canvas or its browser row) | Same. Move Object switches the dialog to the components one (the move type and values are kept); a component selected before M opens it directly. A click in the canvas picks the component just below the active component on the way to what was clicked (`components_core.component_to_pick`); clicking it again drops it |
| The component moves with everything in it | Same: its Placement changes (a nested component's relative to its parent); its bodies are not changed |
| Free Move / Translate / Rotate / Point to Point / Point to Position; the manipulator; typed values | Same as for bodies (the manipulator sits at the middle of the components); axes and points are taken where they were before the move |
| Set Pivot, then Done (the check) | Same (`parity/bodies.md` Move/Copy); the scenario sets the pivot on a corner and turns the component 90° about it |
| Capture Position (components only) | Ticked: OK records the move as a **Move** step in the timeline (`ComponentMove`, one per component, one undo step). Double-click it to edit it (the dialog opens on it, Capture on); Suppress, Delete or the marker before it put the component back where it stood before it (`component_move.apply_history`). Not ticked: the component just stands there ("position pending"): with joints, joints' Capture Position / Revert are offered (the joints work owns them); a captured move also becomes where Revert returns to |
| A grounded component does not move | Refused with the reason in the dialog ("Bracket is grounded, so it cannot move. Unground it first") |
| Create Copy | The component stays; a linked instance ("Name:2") is moved instead |
| Ctrl+C / Ctrl+V on a component (also the browser's Copy / Paste) | A linked instance "Name:2" in the active component (or in the component whose row was right-clicked; never inside itself). The browser then names the original "Name:1". It is no timeline step. Move/Copy opens on it; Esc leaves it on the original |
| Editing one occurrence changes all | The instance's bodies are copies of the original's (`InstanceCopy`): every change to the original (an extrude made longer, a fillet, a new body in it) shows in every instance. Activating an instance (its ring) activates the original, with a note; renaming one renames the component (all occurrences) |
| Paste New | An independent component "Name (1)" with copies of every feature (its steps join the timeline, the component step first); Move opens on it |
| Ctrl+C / Ctrl+V on a body | Move/Copy opens on the body with Create Copy ticked (a copy body) |
| Pattern Type Components | Rectangular, Circular and Pattern on Path (`parity/patterns.md`): one pattern step; its copies are instances "Name:2" ... placed by the pattern, following edits of the component; Quantity, Distance, Angle, Suppression; edited from the timeline; deleting the step (or undo) takes the copies with it; the marker before it hides them |
| Combine New Component | `parity/bodies.md` Combine |
| Split Body with several tools | `parity/bodies.md` Split Body |
| An active component shows the rest dimmed (Active Component Visibility, on) | Same: while a component is active, every body and component outside it is drawn see-through (still pickable); the design's ring shows everything normally. Preferences > General > Design > *Active component visibility* switches it off. A look only (a Coin material over the dimmed objects, `component_look.py`): nothing is saved, no undo step |
| The marker before a component's step hides the component | Same: hidden in the window and gone from the browser while the marker stands before its step (unless steps inside it come before the marker: a component made from an existing body stays, else the body would vanish); back when the marker passes it; kept in the file |
| A step made while the timeline is rolled back goes in at the marker | Now also a new component, a captured Move and a pattern of components (`timeline_ops.place_root_step`); steps outside the bodies stand by their own creation order (`timeline_core.merge`) |
| Body Move/Copy with Create Copy, Split Body pieces, pattern-of-bodies copies of a body inside a moved component | The new body's first step now sits in that component (FreeCAD warned "Link(s) ... go out of the allowed scope") and takes its shape in the body's own coordinates (the copy landed moved twice) |

### How it is built on FreeCAD

| Fusion | SciForge / FreeCAD |
|---|---|
| A component occurrence's position | The `App::Part`'s Placement |
| A captured component move | `App::FeaturePython` "Move" (SciForgeType `ComponentMove`): Component, Movement (design coordinates), Before (the component's own placement before it), MoveId; it computes nothing; `apply_history` replays the moves that count at the marker from the first one's Before. The timeline treats it, a component step and a pattern of components as steps outside the bodies that roll back (`timeline_core`, "rolls") |
| An instance (Copy/Paste, Create Copy, a pattern's copy) | An `App::Part` with `SciForgeInstanceOf` (the source component), labelled "Source:n", hidden from the timeline, holding one copy body per body of the source (nested components' bodies flattened). Each copy body's first step is an `InstanceCopy` (`Part::FeaturePython` inside the instance part: FreeCAD's link scope) that copies the source body's solid: in the source component's frame (the instance's own Placement places it), or moved by its pattern's `Moves` entry. `instances.sync` adds / removes copy bodies when the source's bodies change and keeps the labels (after recomputes, never during undo / redo or a file load). An `App::Link` was not used: everything else in SciForge (joints, export, measure, drawings, interference) works on bodies inside components |
| A pattern of components | `App::FeaturePython` (SciForgeType Rectangular/CircularPattern / PatternOnPath, "SciForgeRolls") with Source, the references and choices of a pattern of bodies, and `Moves` (each copy's movement, design coordinates); each reference is read in the frame of its body or component (`component_pattern.frame_of`) |
| Paste New | `doc.copyObject(part, True)` |
| Active Component Visibility | an `SoMaterial` with only its transparency set and the override flag on, at the top of each dimmed object's scene node (a body or a whole component), removed again when it is no longer dimmed |


## Known gaps (honest list)

- Ghosting, the marker and instances are built (components-2); what is still missing:
- A component made from bodies that existed before it (Create Components from Bodies) stays
  shown when the marker stands before its step (Fusion puts the body back at the root): hiding
  it would hide the body.
- Sheet Metal components, External components (a component as its own file), Opacity Control,
  Selectable, component colour cycling and Properties are not built.
- A sketch that sits outside every body cannot exist in FreeCAD's PartDesign, so "a sketch at
  the root while the body goes to a component" (Fusion's Create Components from Bodies) is
  approximated: the body's sketches move with the body.
- The New Component dialog's Parent is a drop-down, not Fusion's click-in-the-browser box.
- Instances: nested components of the copied component are flattened into the instance (its
  bodies are there, the nested component rows are not); editing happens through the
  original (activating an instance activates the original; a sketch put directly on an
  instance's face goes into the instance's copy body only, Fusion would edit the component);
  deleting the original leaves its instances frozen as they were (Fusion keeps the component
  while an occurrence remains); a body deleted from an instance comes back at the next sync.
- A pattern's copies cannot be moved on their own (refused with the reason); Mirror of
  components is not built (greyed in Mirror's Pattern Type).
- A component move that is not captured, in a design without joints, cannot be reverted
  (joints' Capture Position / Revert need the joints' assembly); Fusion asks to capture or
  revert before the next feature (not built: the pending position simply stays). Rolling the
  marker over a captured move recomputes the component's position from its captured moves, so
  a pending (uncaptured) move of that component made after them is dropped.
- Joints on instances work like on any component, but a joint between two occurrences of one
  component is not special-cased.
- Selection filters / priority Components (SELECT menu) and Component Drag in the canvas belong
  to the selection and joints-2 work.
- No "New Body" command (Fusion has none: bodies come from features).
- STEP files open and insert as components (exchange-2, parity/insert-export.md Part 2): a
  repeated part is an instance; another SciForge design inserts as one linked component
  (Break Link copies its features in); both bring nested components of an inserted design
  in flat only where noted there.
