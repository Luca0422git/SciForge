# Parity spec: body tools (outline 7.6 / 7.8): Combine, Split Body, Move/Copy, Delete, Appearance, Physical Material

Source: Fusion's documented behaviour (public help topics on Combine, Split Body, Move/Copy,
Delete, Appearance and Physical Material) and everyday use. Not yet checked against Luca's own
screen captures (outline 2.4); the choices marked **(assumed)** need his confirmation.
Status: **first pass, not yet signed off**.

Code (all in `src/Mod/SciForge/sciforge/`):

| File | What |
|---|---|
| `bodies.py` | helpers every multi-body tool uses: `list_bodies(doc)`, `new_body(doc, label)`, `active_body(doc)`, `set_active_body(body)`, `find_body(doc)`, `body_of(obj)`, `global_shape()`, `to_local()`, `mass(body)` / `density(body)`, bodies "used up" by a step (`consumed`, `sync_consumed`) |
| `combine.py`, `combine_ui.py` | Combine (document side / dialog) |
| `split.py`, `split_ui.py` | Split Body |
| `move.py`, `move_ui.py` | Move/Copy (the manipulator is `move_ui.Triad`) |
| `delete.py`, `delete_ui.py` | Delete (Del), the Delete Face step |
| `appearance.py`, `appearance_ui.py` | Appearance |
| `material.py`, `material_ui.py` | Physical Material |
| `bodies_panel.py` | the dialog base all of them share (selection boxes, preview, OK/Cancel/Esc/Enter, Ctrl+Z) |
| `bodies_gui.py` | the view provider of their timeline steps; a document watch that keeps the view in line after recomputes, undo and deletes |

## What gets built (and why)

| Tool | Built as |
|---|---|
| Combine | a "Combine" step (`PartDesign::FeaturePython`, SciForgeType `Combine`) at the history marker of the target body; with New Body the first step of a new body. It links the step each tool body ended with when the Combine was made, so later steps of a kept tool body do not change an earlier Combine, and edits of earlier steps flow through (golden `bodies_combine_follows_tool`). FreeCAD's `PartDesign::Boolean` was not used: it adopts the tool bodies as its children (they move with the target and drop out of the body list) |
| Split Body | a "Split Body" step in the split body (it keeps one piece) + one new body per other piece, whose first step (hidden) takes that piece from the split. The body keeps the biggest piece; equal pieces: the one nearest the origin in X, then Y, then Z **(assumed)**. Pieces are matched by where they were, so edits of earlier steps keep each piece in its body |
| Move/Copy | a "Move" step at the end of each moved body (it moves the body's solid; later steps build on the moved solid, sketches made earlier stay where they are, as in Fusion). Create Copy: a "Move" step outside the bodies that copies the body's solid as it was at that point and moves it; a new body starts from it. One step per body, sharing a MoveId: editing one edits them all. The movement is stored as numbers (a placement), like Fusion's Move feature |
| Delete on faces | a "Delete Face" step: the faces go and the faces around them grow to close the gap (OpenCASCADE defeaturing) |
| Physical Material | the body's FreeCAD `ShapeMaterial` (FreeCAD's material library), on every step of the body |
| Appearance | stored in the design (a hidden JSON property of the body), so it is saved and undone with Ctrl+Z; put on every step's view after each recompute and undo |

## What the user does (and what SciForge does)

### Combine (MODIFY > Combine)

| Fusion | SciForge |
|---|---|
| Target Body, Tool Bodies, Operation Join / Cut / Intersect, New Component, Keep Tools (**Autodesk**, *Combine reference*: New Component "creates a new component with the results") | Target Body, Tool Bodies, Operation Join / Cut / Intersect, **New Body** (a SciForge extra from before components: the result goes into a new body, the target is used up like the tools **(assumed)**), **New Component** (components-2: the result is the body of a new component, made in the active component; the target and the tools are used up; New Body is greyed while it is on; unticking it in an edit joins the target again and the component goes), Keep Tools |
| nothing selected: the dialog waits for the target | same; the Target Body box takes the first click, then the Tool Bodies box every further one (a click on a picked tool drops it, also where the Join preview is drawn over it: the click means the body really under the pointer) |
| bodies selected first | taken at once: the first is the target, the others tools |
| live preview | same; the tool bodies stay visible, see-through, while the dialog is open (they can be clicked to drop them) |
| tool bodies disappear after OK (Keep Tools off) | they are hidden while the Combine is part of the design and come back when it is deleted, suppressed, undone or rolled back (timeline marker). A used-up body is never left as the active body (new sketches and extrudes would go into a body nobody sees): the Combine's body becomes the active one, also in a design opened again |
| editing a Combine (timeline double-click) shows its tools | same: the used-up tools show, see-through, as soon as the dialog opens |
| problems shown in the dialog (Intersect of bodies that do not overlap...) | same; OK keeps the dialog open |
| OK / Enter, Cancel / Esc, one undo step, Ctrl+Z in the dialog cancels it, double-click in the timeline edits | same |

### Split Body (MODIFY > Split Body)

| Fusion | SciForge |
|---|---|
| Body to Split, Splitting Tool(s), Extend Splitting Tool | same; the Splitting Tool(s) box takes several tools (components-2): every click adds one, a click on a picked tool drops it, the box reads "2 tools"; all of them split the body in one step (**Guess**: the dialog's "(s)"; older Autodesk forum posts ask for it, *Split body with multiple splitting tools*); click the box to show the origin squares again for a second plane |
| tools: planes, faces, bodies, sketch curves | origin planes (the big squares of Create Sketch are drawn while the box waits for a tool), construction planes, faces of any body (flat or round), bodies (click them in the browser), sketch lines and arcs (cut straight through along the sketch's normal) |
| Extend Splitting Tool | on: a flat face is taken as its whole plane, a round face as its whole cylinder; off: only where the face is (the reason is shown when it then does not cut) |
| result: bodies in the browser and the timeline | same; deleting the Split Body step deletes the bodies it made |

### Move/Copy (M, MODIFY > Move/Copy)

| Fusion | SciForge |
|---|---|
| Move Object Bodies / Components / Faces / Sketch Objects | Bodies and Components (components-2: the dialog switches to the components one, `parity/components.md`; a component selected first opens it directly); M in an open sketch moves sketch curves (the sketch's own Move/Copy). Faces: modify-2 |
| Move Type Free Move: manipulator with arrows and rotation handles; X/Y/Z Distance, X/Y/Z Angle | same: three arrows (X red, Y green, Z blue) and three curved turn handles at the middle of the bodies, drawn on top of the part; turns are about X, then Y, then Z through that middle **(assumed order)** |
| Translate: X/Y/Z Distance, arrows | same |
| Set Pivot (Free Move): press it, click geometry to snap the manipulator to it or type where it goes, the check (Done) to finish; turns are about the pivot from then on (**Autodesk**, *Move or copy geometry*: "Click Set Pivot to adjust the pivot point of the manipulator. In the canvas, hover over the geometry you want to snap to, then click to place the pivot point, or enter exact values in the dialog"; **Forum**, *Rotating Assemblies?*: "it is a toggle", click the green check when done) | same (components-2): Set Pivot and ✓ Done buttons; while it is on the arrows move only the manipulator (no turn handles), a click takes the corner / edge middle / circle centre / face centre under the pointer, Pivot X / Y / Z show and take its place; nothing that was moved moves (the distances are adjusted, `components_core.pivot_shift`); Done goes back to moving |
| Rotate: Axis, Angle | same; the axis: an origin axis (drawn as long lines while the box waits), a straight edge, a round edge or face (its axis); a blue handle turns round it |
| Point to Point | same; a click near a corner takes the corner (Fusion lights it up), a round edge its centre (also right next to the point where OpenCASCADE starts the circle, which is no corner), a straight edge its middle |
| Move Type chosen before the bodies | the Objects box keeps the first click (the body), then the dialog moves on to the axis or the point |
| Point to Position | same: pick the point, X / Y / Z start at where it is; type where it goes |
| Create Copy | same: new bodies; the originals stay |
| recorded in the timeline, editable, undo | same (one Move step per body, edited together) |

### Delete (Del, MODIFY > Delete, marking menu)

| Fusion | SciForge |
|---|---|
| a body | deleted with everything in it; bodies copied or split from it keep their shape; a Combine that used it as a tool (or, with New Body, as its target) keeps it as it was (same result). This also holds for the browser's and the timeline's own Delete (bodies_gui.Watch keeps it, in the same undo step); editing such a Combine lists "N deleted bodies" in Tool Bodies, the X of the box drops them |
| a feature / sketch / plane | deleted; steps after it keep working where they can: fillets, sketches and other steps that used its edges or faces move onto the same edges/faces of the step before it, a Combine or a copy that used it uses the step before it, the body's history is re-linked, the Tip moves back; what cannot (an extrude whose sketch is gone; a fillet whose edge FreeCAD's naming loses because everything moved) is shown red in the timeline with the reason, never as errors in the Report view |
| faces | a Delete Face step closing the gap; refused with the reason next to the pointer when the faces around cannot close it (the box's top face) |
| sketch curves | deleted from the sketch |
| nothing selected | a note next to the pointer, nothing else |
| the browser and the timeline's own Delete | they keep doing theirs; deleting a Split Body or a copy there also deletes the bodies it made (a moment later, as their own undo step) |

### Appearance and Physical Material (MODIFY menu)

| Fusion | SciForge |
|---|---|
| Appearance: Apply To Bodies/Components / Faces, In This Design, Library, drag a look onto a body or face | Apply To Bodies / Faces, In This Design, a library (steel, stainless, aluminium incl. anodized, titanium, iron, brass, copper, chrome, glossy plastics in 9 colours, matte plastics, clear plastic, rubber black/grey, glass, wood), a custom colour (#RRGGBB or R/G/B sliders). Pick a swatch and click bodies/faces, or drag the swatch onto them. A face keeps its look through later steps while it survives, also when the body is moved (Move/Copy); the faces without a look of their own keep the grey every part has |
| Physical Material: library, In This Design, assign to bodies | same; 19 materials from FreeCAD's library with their density (steel, stainless steel, iron, aluminium, aluminium 6061, copper, titanium, ABS, PLA, PET/PETG, nylon 6, polycarbonate, acetal, acrylic, polypropylene, PTFE, PEEK, wood, glass); the mass of each body is shown. A material gives the body its look unless the body has an Appearance of its own (as in Fusion). Drag a material from the library onto a body (Fusion's way), or pick it and click bodies |
| a design starts in Steel | FreeCAD starts with a weightless "Default"; such a body counts as Steel for its mass (`material.effective`) |
| OK / Cancel, undo | same (one undo step for everything done in the dialog) |

## Known gaps (never faked: listed here)

| Fusion behaviour | Why not (yet) |
|---|---|
| Move: Move Object Faces | not built here (modify-2's area; Press Pull moves faces). Set Pivot only re-places the pivot; Fusion's manipulator can also be turned while setting it (its axes then follow): SciForge's axes stay the design's X / Y / Z |
| The timeline's and the browser's own Delete re-route dependants like SciForge's Delete | they belong to the timeline/browser module; they delete the bodies a Split Body or a copy made (bodies_gui.Watch), and flag what breaks |
| Rolling the timeline marker back before a Create Copy hides the copy | the copy's step sits outside the bodies, so the marker does not hide it (a body copy inside a component sits in that component since components-2, so it is placed right in a moved component) |
| Physical material shown in the browser | the browser module shows no material; the Physical Material dialog lists them ("In This Design") with each body's mass |
| Inspect > mass properties | `bodies.mass(body)` gives the mass from the material; the Inspect module (separate work) is to use it |
| Fusion's photo-real appearances (textures, reflections) | FreeCAD's material colours (diffuse, specular, shininess, transparency) |
| A step on a Combine's face survives changing the Combine's operation | FreeCAD's naming (toponaming) keeps a face through dimension changes, but a face a Join merged from two faces is made another way by Cut: a Press Pull or sketch on it then says in the timeline that its face must be picked again (the same happens with FreeCAD's own Boolean) |
