<!-- A copy of docs/sciforge/parity/selection.md for AI models, made by tools/sciforge/make_ai_docs.py: edit the original, then run the script. -->

# Parity spec: selection (outline 7.14 "Selection")

Built 2026-10-13 on branch `sf/selection`: `src/Mod/SciForge/sciforge/selection_core.py`
(the rules and the box maths, no Qt, unit tested) and `selection_ui.py` (the mouse filter on
the 3D view, the box drawn over it, the Select Other list, the filter gate, the commands).
Scenarios with real input: `selection_box`, `selection_dialogs`, `selection_filters`,
`selection_other`, `selection_sketch` (172 checks). Status: **first pass, researched from
Autodesk's pages and forum answers, not yet checked against Luca's Fusion**.

Evidence labels: **Autodesk** (help page or Autodesk blog), **Forum** (an answer on the
Autodesk forums, often by Autodesk staff), **Guess** (nothing found; SciForge's own choice).

## What Fusion does (the behaviour spec, with sources)

| Behaviour | Evidence |
|---|---|
| Click selects; a click on empty space clears the selection | Autodesk, [Selection in Fusion](https://help.autodesk.com/cloudhelp/ENU/Fusion-Model/files/SLD-SELECTION.htm) |
| **Ctrl** (Cmd on a Mac) adds what is not selected and removes what is; **Shift** only adds (a second click never removes) | Autodesk, same page; Autodesk, [Select multiple components](https://www.autodesk.com/products/fusion-360/blog/select-multiple-components-fusion-360-tutorial/) ("hold Ctrl to unselect") |
| **Window selection** (the default, key **1**): drag left to right and only what is entirely inside the box is selected; drag right to left and everything the box crosses or encloses is selected | Autodesk, [Select multiple objects with selection modes](https://help.autodesk.com/cloudhelp/ENU/Fusion-Model/files/SLD-SELECTION-MODES.htm) |
| **Freeform selection** (key **2**): an irregular shape drawn by hand; the same direction rule | Autodesk, same page |
| **Paint selection** (key **3**): everything the pointer passes over with the button down; always a "crossing" selection | Autodesk, same page and [3 ways to select an area](https://www.autodesk.com/products/fusion-360/blog/tip-tuesday-3-ways-to-select-an-area-in-fusion-360/) |
| The two boxes look different: a 2014 tip shows the inclusion preview orange and the crossing one yellow; a user compares it to AutoCAD's solid / dashed outline ("Fusion 360 and AutoCAD do both") | Autodesk (2014 blog), Forum (Bambu Lab forum, not Autodesk); the exact current look is **Guess** |
| A box outside a command takes **faces and edges**, not whole bodies and not every vertex (Autodesk limited window selection of vertices for speed); inside Fillet / Chamfer a box picks edges for the command | Forum, [Faces selection](https://forums.autodesk.com/t5/fusion-support/faces-selection/m-p/9629981) (moderator), [Can't select edges with mouse window](https://forums.autodesk.com/t5/fusion-design-validate-document/can-t-select-edges-with-mouse-window/td-p/5887526) (Jeff Strater, Autodesk), [Window selection isn't selecting vertex](https://forums.autodesk.com/t5/fusion-design-validate-document/window-selection-isn-t-selecting-vertex/td-p/8099370) (Autodesk) |
| **Select Other**: press and hold the left button on the model for about a second without moving; a list of everything under the pointer appears, ordered front to back; moving over a row selects (shows) the matching item on the model; a Parents tab lists the body / component the item belongs to | Autodesk, [How to use Select Other](https://www.autodesk.com/products/fusion-360/blog/quick-tip-how-to-use-select-other/); Forum, [How can I hide a face](https://forums.autodesk.com/t5/fusion-360-support/how-can-i-hide-a-face-faces/td-p/7442678) (reaches a face behind a body) |
| **Selection Filters** (Select menu): a checklist of what can be selected: Bodies, Body Faces, Body Edges, Body Vertices, Components, Sketch Curves, Sketch Points, Work Geometry (planes, axes, points), Joint Origins, Canvas, and more; unchecked kinds cannot be selected | Autodesk, [Use selection filters](https://help.autodesk.com/cloudhelp/ENU/Fusion-Model/files/SLD-SELECTION-FILTERS.htm) |
| The filters also bite inside commands ("cannot select faces, edges, sketches" with Body priority stuck on) | Forum, [Select Body Priority is stuck ON](https://forums.autodesk.com/t5/fusion-support/select-body-priority-is-stuck-on-cannot-select-faces-edges/td-p/9203674) |
| **Select Through**: when checked, a window or freeform box also takes hidden objects; unchecked, only objects not obscured by others can be selected. People are told to turn it on to reach hidden geometry | Autodesk, same filters page; Forum, [Select Hidden Edge for Fillet](https://forums.autodesk.com/t5/fusion-design-validate-document/select-hidden-edge-for-fillet/m-p/5051132). Whether it starts checked: **Guess** (off) |
| **Selection Priority**: Select Body / Face / Edge / Component Priority; one at a time; choosing one checks that filter and unchecks all the others; clicking the active one again removes the filter | Autodesk, [Use selection priority filters](https://help.autodesk.com/cloudhelp/ENU/Fusion-Model/files/SLD-SELECTION-PRIORITY-FILTERS.htm) |
| With Body priority a click on a face selects (and a box takes) the whole body | Autodesk, same page |
| With Body priority the whole body lights up under the pointer, also inside a command that takes bodies and for bodies inside components (Luca 2026-10-16: "when using a tool and selection is set to 'body', the whole body should be highlighted when hovering over it. not just the face") | Luca; Autodesk (same page: the priority decides what is picked); the highlight itself **Guess** |
| **Tangent Chain** is an option of Fillet, Chamfer and Press Pull (on by default in Fillet / Chamfer): one edge brings the edges tangent to it | Autodesk, [Tangent chain reference](https://help.autodesk.com/cloudhelp/ENU/Fusion-Model/files/SLD-REF-TANGENT-CHAIN.htm) |
| In a sketch, a double-click on a curve selects the connected chain of curves, without a window | Forum / course, [Selecting sketch chained entities](https://origin-www.lynda.com/Fusion-360-tutorials/Selecting-sketch-chained-entities/2810401/2884089-4.html); Forum, [chain select](https://forums.autodesk.com/t5/fusion-360-ideastation-archived/chain-select/idi-p/6717640) ("double clicking a curve that's part of a chain") |
| Esc clears the selection when no command runs (a single Esc inside a command keeps its picks) | Forum, [How to exit orbit without deselecting](https://forums.autodesk.com/t5/fusion-support-forum/how-to-exit-orbit-without-deselecting/m-p/12320285) (Autodesk community manager); outside a command: **Guess** |
| Component Drag (Select menu): a drag on a component moves it; off, a drag draws the box | Autodesk, [Select multiple components](https://www.autodesk.com/products/fusion-360/blog/select-multiple-components-fusion-360-tutorial/) |
| Inside a command only what the command takes can be picked (Fillet: edges and faces, Shell: faces); the pointer picks what the command takes under it, so the corner at the end of a short edge does not stop a Fillet from taking the edge | Autodesk, [Use selection filters](https://help.autodesk.com/cloudhelp/ENU/Fusion-Model/files/SLD-SELECTION-FILTERS.htm) (commands restrict what can be selected); the short-edge case is **Guess** (follows from the restriction) |

## What SciForge does

| Fusion | SciForge |
|---|---|
| Click, Ctrl toggles, Shift adds, empty space clears | FreeCAD's own click (it selects on the release; Ctrl toggles). Shift is SciForge's: a Shift click on something not selected is handed to FreeCAD as a Ctrl click (adds); on something selected it is swallowed (kept); on empty space it keeps the selection. `selection_box` F, `selection_filters` C |
| Window / crossing box | A press on the model or on empty space followed by a move of more than 5 px draws SciForge's box over the view (a see-through widget, `RubberBand`): **solid blue** when the drag goes to the right (window), **dashed green** to the left (crossing). The release selects what the box takes (through `Gui.Selection`, so every dialog's observer gets the picks) and never reaches FreeCAD, which would select what is under the pointer. A window takes an element whose every screen point lies inside; a crossing box takes one with a point inside, a boundary piece touched, or the box inside the element's own outline. Faces and edges of visible bodies and loose Part features, curves of visible sketches not being edited; vertices only when faces and edges are filtered off; whole bodies with the Body priority. `selection_box` A-F |
| Freeform (2) and Paint (3) | The same filter: the lasso is the drag's path (points closer than 3 px dropped); paint selects what is under the pointer at every move (a crossing selection), a plain stroke replaces the selection at its first pick and adds from then on. `selection_box` I, J |
| Keys 1 / 2 / 3 | Taken before FreeCAD's own 1 / 2 / 3 (front / top / right view) with a ShortcutOverride, only while no command and no sketch is open (digits are values there). Remembered in `Mod/SciForge/SelectionMode` |
| Modifiers on a box | Plain: replaces; Shift: adds; Ctrl: toggles each element; inside a command a plain box adds (commands collect picks). `selection_box` F, `selection_dialogs` |
| Select Through | Off at first (**Guess**, see above). Off: an element counts only when the view shows it (FreeCAD's pick at one of its sample points lands on it, or within 0.2 % of the part's size of it). On: hidden faces and edges too. `selection_box` A, H |
| Select Other | A left press that stays within 5 px for FreeCAD's `LongPressTimeout` (1 s) opens SciForge's list (`SelectOtherMenu`, a QMenu) at the pointer: everything FreeCAD picks along the ray (`getObjectsInfo`), nearest first, the faces an edge bounds added after it, then a separator and the bodies they belong to (Fusion's Parents tab, as rows). Hovering a row highlights it (`setPreselection`); a click selects it with the press's modifiers; Esc or a click elsewhere closes it; the release of the held button selects nothing. Only what the filters allow is listed; nothing opens on empty space, on a handle, or in a sketch. FreeCAD's own long-press "Clarify Selection" menu is turned off while SciForge is on (`EnableLongPressClarifySelection`, kept and given back by `theme.py`). Also the Select Other entry of the SELECT menu. `selection_other` |
| Selection Filters | SELECT > Selection Filters: Select Through, Bodies, Body Faces, Body Edges, Body Vertices, Sketch Curves, Sketch Points, Work Geometry (Components greyed: no components yet). Each is a tick that flips on its own. The filters are a FreeCAD selection gate (`FilterGate`): a filtered kind does not light up under the mouse and a click on it selects nothing (a note by the pointer says which filter is off). A dialog that installs its own gate gets it combined with the filters (`Gui.Selection.addSelectionGate` / `removeSelectionGate` are wrapped while SciForge is on), so the filters bite inside commands as in Fusion; when the dialog removes its gate the filter gate comes back. Whole objects picked in the browser or the timeline are never refused. Remembered in `Mod/SciForge/SelectionFiltersOff` and `SelectThrough`; SciForge off: FreeCAD's own selection, nothing filtered. `selection_filters` B, D, E, F |
| Selection Priority | SELECT > Selection Priority: Body / Face / Edge (Component greyed). A preset: that kind on, the others off; the active one clicked again puts every filter back. With the Body priority a click on a face selects the whole body (SciForge takes the click: FreeCAD's gate would refuse the face), the body lights up under the mouse, a box takes bodies, Ctrl + click drops one. `selection_filters` C, `selection_dialogs` E |
| Body priority hover (view-3, 2026-10-16) | The whole body lights up under the pointer outside and inside commands (Shell, Move, Combine...; also while a command holds FreeCAD's edit mode: Coil, Pipe, a construction; not in a sketch). A mouse callback of the view does it: FreeCAD runs it right after its own preselection of the same move (`SoFCUnifiedSelection::handleEvent` preselects, then traverses its children, among them the view's `SoEventCallback`), so the body is lit again before the view is drawn: steady (before, a timer lit it after FreeCAD had cleared it on every move: it blinked). Bodies inside components are lit and clicked through their path (`Part.Body001.`), loose solids (STEP) too (`analysis.body_of`, plus a loose solid inside a component). `selection_filters` G, H |
| A gate FreeCAD dropped (view-3) | A FreeCAD command written in C++ puts in its own selection gate, which silently replaces SciForge's filter gate, and takes it away when it ends, leaving none (Python cannot read the active gate). SciForge notices it on the next mouse move: something the filters refuse got preselected while no command is open; the filter gate is put back (`selection_ui._gate_lost`, logged). `selection_filters` I |
| Esc | With no command and no sketch open, Esc clears the selection; while a box is being dragged, Esc cancels it (the release then selects nothing). Inside a sketch Esc stays the Sketcher's. `selection_box` G |
| Tangent Chain | Already there: Fillet / Chamfer always follow tangent edges (the kernel cannot stop at one), Press Pull has the Tangent Chain box (`parity/fillet.md`, `parity/extrude-presspull.md`) |
| A drag on a handle | A press on one of the open dialog's handles (their screen extents, `taskui.BoxCarrier`) or on a `handles3d` handle just pressed is the handle's drag: no box, no Select Other. FreeCAD's edit modes (a sketch, a datum, Move's manipulator) get the mouse untouched. `selection_dialogs` C, `extrude_presspull_qa` |
| In a sketch | SciForge's box, Select Other and mode keys stay out: FreeCAD's Sketcher draws its own box (window to the right, crossing to the left, 1.1.4). Since sketch-2 (`sketch_select.py`): a plain box replaces the selection, Shift adds, Ctrl toggles (FreeCAD's only added), and a double-click on a curve selects its chain (the curves joined end to end, of its line type). `selection_sketch`, `sketch2_select` |
| Construction planes, axes, points | Since sketch-2: a window takes the planes, axes and points that are shown (an origin's only while the origin is shown), measured as FreeCAD draws them at rest; a crossing box touching one takes it; whole objects, selected by their path like a click; the Work Geometry filter applies. `sketch2_box_planes` |
| A click a command's own gate refuses | Since the Pi 5 case test (2026-10-16): when an open command's gate refuses what is nearest the pointer, SciForge selects the first thing under the pointer it takes (`getObjectsInfo`, front to back; for a refused corner an edge first), with the click's modifiers (a plain click on a pick drops it). FreeCAD's own pick can also meet a refused corner while `getObjectInfo` reports the edge: when a click inside a command made no selection event at all (`_EventCount`), SciForge takes the edge under the pointer the same way. Before, the click selected nothing: the corners of the 2 mm edges of a lid could not be rounded. `pi5_case` (lid corners) |

## Facts found on the way

- FreeCAD's click pick (`SoFCUnifiedSelection`) prefers a corner within the pick radius to
  the edge under the pointer, while `view.getObjectInfo` at the same pixel reports the edge.
  When a selection gate refuses the corner, FreeCAD selects nothing on that click. Seen on a
  2 mm edge (about 10 px on the screen, both corners within 5 px).

- FreeCAD selects on the **release** of the left button (`SoFCUnifiedSelection`), so a box
  drag only has to swallow the release; the press goes on to FreeCAD and to every handle.
- FreeCAD 1.1.4 has a long-press "Clarify Selection" menu of its own (`LongPressTimeout`
  1 s, cancelled at 5 px); in the Revit navigation style (SciForge's) it opens without Ctrl.
- `Gui.Selection.addSelection(doc, "Body", "Pad.Face6")` is stored as the feature's
  `Face6`; `setPreselection(body, "")` highlights a whole body.
- A `SoRayPickAction` made from Python finds things only right after FreeCAD's own pick
  (`getObjectsInfo`); the next one finds nothing. Not relied on: the handle test uses the
  handles' own screen extents, Select Other uses `getObjectsInfo`.
- A rectangle drawn around the top face of a box in the isometric view also fully contains
  the two vertical edges hanging below its leftmost and rightmost corners: a window takes
  them too (Fusion would as well; they are inside).
- A mouse event Quarter does not accept is handed on by Qt to the viewer widget around the
  drawing area, where the same filter sees it a second time: the filter only acts on the
  drawing area's own events.
- Under xvfb, X now and then sends a move with no button while the left button is held
  (a new view appearing under the pointer, a cursor move): a move without the button does
  not end a box while `QApplication.mouseButtons()` still says the button is down.
- A dialog may replace its arrow while a drag runs (the preview recomputes), so whether a
  Coin dragger holds the event grab at the first move says nothing: the handle test is
  made at the press, from the handles' own screen extents (`extrude_presspull_qa` P3
  turned into a box before that).

## Gaps and guesses (check in real Fusion)

- The box's colours and the dashed outline (SciForge: solid blue / dashed green).
- Whether Select Through starts checked (SciForge: off).
- Whether a box outside a command takes vertices at all (SciForge: only with faces and
  edges filtered off) and sketch curves (SciForge: yes, when Sketch Curves is on).
- Select Other's exact list (Fusion shows a dialog with a Parents tab; SciForge one list
  with the bodies after a separator) and its radius for nearby edges (SciForge: twice
  FreeCAD's pick radius, 10 px).
- Esc outside a command clearing the selection (SciForge: yes).
- Component Drag is built by the joints work (wave 4, `joints_drag.py`, spec in
  `parity/joints.md` "Dragging components"): a plain drag that starts on a component moves
  it along its joints instead of drawing a box; SELECT > Component Drag turns it off.
- Not built: the Components filter and priority, the Joint Origins / Canvas
  filters (nothing to filter). (The sketch double-click chain and window selection of
  planes and axes: sketch-2.)
- Whether Fusion's window takes construction planes and axes (Guess: yes, under the Work
  Geometry filter), and whether its sketch double-click chain crosses into construction
  curves (Guess: no).
- A box drag that starts on a shaded sketch area while Extrude waits also picks that area
  (FreeCAD's area picker acts on the press, which SciForge does not hold back).
- With filters on, FreeCAD shows its "forbidden" cursor over a filtered element (its gate
  behaviour); Fusion shows nothing.
- Body priority hover: tools with their own pickers draw their own hover over it (Extrude's
  shaded sketch areas, Revolve's axis lines); the body is lit as FreeCAD's preselection under
  them. A body found only through Select Other's Parents rows is still selected by its own
  name (not through its component's path).
- A FreeCAD C++ gate that replaced SciForge's is only noticed when the pointer passes over
  something the filters refuse (nothing else shows that the gate is gone).
