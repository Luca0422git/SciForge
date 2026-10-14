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
Status: **built and tested with real clicks, not yet signed off by Luca.**

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
| Components in the timeline | A component is a timeline step (kind `component`, icon `new_component`, called by the component's name) at its creation, never rolled back (like every step outside a body) and never suppressed. Each step knows its component (`Item.component`, shown in the hover text). |

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
| One timeline for the design; a component's creation is a step | Same: the component step at its creation, called by its name; Rename / Delete / Roll Here / Find in Browser work on it; double-click activates it; it is never suppressed (greyed out) and never rolled back (gap below). Create Components from Bodies adds a step per component. |
| With a component active the timeline shows that component's features | Same: only the steps of the active component and of the components inside it show (the component's own step included); a grey note at the end counts the hidden ones and says how to see all (activate the design's row). The history marker stands before the first shown step after its slot. Dragging the marker or a step still acts on the whole design, as in Fusion. |
| Hover a feature: its name | Also "In component: X" for steps inside a component. |

## Known gaps (honest list)

- Rolling the marker before a component's step does not hide the component (steps outside
  bodies are never rolled back in SciForge; the marker rule is the one of the timeline doc).
- Fusion ghosts (dims) everything outside the active component in the 3D view (preference
  "Active Component Visibility"); SciForge shows all bodies normally.
- Fusion shows the activate radio button, by Autodesk's wording, "to the right of a component
  node"; whether it is drawn for every row or on hover only is unconfirmed.
- Sheet Metal components, External components (a component as its own file), Insert / Derive,
  copy / paste of components, Opacity Control, Selectable, component colour cycling and
  Properties are not built.
- A sketch that sits outside every body cannot exist in FreeCAD's PartDesign, so "a sketch at
  the root while the body goes to a component" (Fusion's Create Components from Bodies) is
  approximated: the body's sketches move with the body.
- The New Component dialog's Parent is a drop-down, not Fusion's click-in-the-browser box.
- A component's Placement (moving a whole component) is not exposed yet; joints will need it.
- Patterns / Mirror of components (Fusion's "Pattern Type: Components") are not built.
