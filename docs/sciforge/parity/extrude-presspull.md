# Parity spec: Extrude (E) and Press Pull (Q) (outline 7.0, 7.6, 9.1)

Source: Fusion's documented Extrude dialog (Start / Direction / Extent / Taper / Operation; a
negative taper narrows) and everyday Fusion behaviour. Implemented in
`src/Mod/SciForge/sciforge/` (`extrude.py` + `extrude_prism.py` geometry, `extrude_ui.py` dialog,
`profile_pick.py` picking, `presspull_core.py` geometry, `presspull_ui.py` dialog, `preview.py`
dialog helpers). Status: **built and tested with real clicks, not yet signed off by Luca**.

## Extrude

| Fusion | SciForge |
|---|---|
| Profiles: click closed areas; click more to add, again to drop | Same. Areas are FreeCAD's own sketch regions (`MakeInternals`, `InternalFaceN`): a circle in a rectangle gives the ring and the disc; crossing curves split areas (two overlapping circles: 3 areas). Flat faces of the part are profiles too. |
| One profile is picked by itself | A sketch just finished (or selected) with exactly one area is taken at once; with several, E waits for clicks. |
| Start: Profile Plane / Offset / Object | Same. Offset has its own blue arrow. Object: a flat face or plane parallel to the profile. |
| Direction: One Side / Two Sides / Symmetric | Same. Two Sides has a Side Two group (extent, distance, taper). Symmetric has Measurement Half / Whole Length (Half by default). |
| Extent: Distance / To Object / All | Same. To Object: a face, a plane or another body (extends the face's plane). All: through everything, with Flip. |
| Taper Angle with a handle | Field plus a curved blue handle at the end of the extrusion; negative narrows (as Fusion). |
| Operation: Join / Cut / Intersect / New Body / New Component | Join, Cut, Intersect, New Body. Dragging into the part switches to Cut unless you chose. The first solid shows New Body. |
| Live preview, OK / Cancel / Esc, one undo step | Same. Esc works with the mouse in the 3D view. |
| Manipulators drawn over the model and grabbable through it | Same (2026-10-13, Luca: "arrows get occluded by bodies"): the arrows, the taper disc and the hole's position handle are drawn in front of any body (Coin's annotation node) and a press on a visible arrow starts the drag even when a body is nearer to the camera (pick style "shape on top"); `taskui.on_top_root`, scenario `handles_on_top`. |
| Edit from the timeline: every option again; the profile sketch is shown while editing | Double-click: profiles, start, direction, extents, taper, operation come back (stored on the feature). The extrude's sketch is shown for the edit and hidden again on OK or Cancel, outside the undo step (Undo after OK never flips it); also for an extrude through several bodies. |
| Errors in the dialog | The message shows in the dialog and OK waits; FreeCAD's own recompute messages are kept out of the Report view while the dialog previews. |
| Starts at 0: nothing pops out until you drag or type (Luca R5) | Same: the arrow is there to drag at 0 and the dialog says "Drag the arrow or type a distance."; OK / Enter at 0 keep the dialog open and say the distance must not be zero. Two Sides: side two starts at 0 too (the preview shows side one alone). Scripts and golden models keep 10. |
| Live preview while dragging (R2) | The part follows the arrow while the button is held (rebuilt every 60 ms, up to 400 ms on a heavy part while a drag streams changes). The same in every SciForge dialog. |
| Distance shown next to the arrow, editable (R3); a number typed with the mouse over the view goes into it | A value box beside each handle (distance, side two, start offset, the taper disc) shows the dialog's value with units, never over a handle or another box; click it, type a value or formula, Enter (= OK) or click elsewhere (that click only leaves the box). Esc in it cancels. A digit, minus or decimal point typed with the mouse over the 3D view goes into the box of the handle last dragged or hovered (else the distance) with its text selected, so you type straight on; FreeCAD's view keys 0-6 no longer turn the view while a dialog is open. The same boxes in Hole, Fillet / Chamfer, Revolve, Box / Cylinder / Sphere / Torus / Coil, Pipe, the Patterns, Rib / Web, Thread and Shell (`taskui.ValueBoxes`, `taskui.TypeOverView`). |
| Sketch stays visible until OK (R6) | Same: hidden on OK in the same undo step (Undo shows it again); Cancel / Esc leave it. E or Q inside an open sketch open their dialog after FreeCAD's "leave sketch" step, so Cancel cannot undo that. |
| Cuts preview in red (R7) | A see-through red copy of the removed volume with a red outline (picture only, clicks pass through); "All" stops at the far side of every body it cuts. Press Pull pushing into the part shows the removed slab in red. |
| Pick one closed area of a sketch (R1) | Same, inside the open sketch (click; Shift / Ctrl add; click again drops; Esc, empty space or a curve drop) and after Finish Sketch (areas shaded, light up, a click selects one). E / Q extrude exactly the picked areas; Q with several opens Extrude with all. A whole sketch selected + E takes its areas (holes stay holes). |
| Objects To Cut: one extrude through several bodies (R8, "objects being edited") | Same, one timeline step. Row "Bodies to Cut / Join / Intersect" with "N bodies" and the names; click the row, then a body to leave it out or take it back; while the row is active the listed bodies show as see-through blue copies (picture only). Cut / Intersect: hidden follower steps in the other bodies; Join merges the bodies it touches; a Join touching nothing is a New Body. A cut through no body says so and OK waits. The step can be dragged along the timeline like any other (its follower steps go to the matching place in each body); the one refused move, with a plain message, would put it before a body it changes exists. |
| Automatic Cut / Join / New Body | Cut when the extrusion starts inside any shown body (a 0.01 mm start slice, at least 1 % inside); Join when it touches a body face to face; else New Body. Decided with the preview, not on every key. |

How it maps onto FreeCAD: Join/Cut are PartDesign Pad/Pocket (patterns, mirror and parameters
keep working on them). Intersect is a SciForge PartDesign feature (`sciforge.extrude.ExtrudeFeature`)
that keeps the part of the body inside the extrusion. New Body creates a PartDesign Body that becomes
the active one. When FreeCAD cannot link the profile directly (start offset, profiles from several
sketches, a profile in another body) a hidden SubShapeBinder carries it into the feature.

## Press Pull

| Fusion | SciForge |
|---|---|
| Faces: offset, neighbours extended or trimmed | Same: slabs are added/removed, then the step faces left at sloped neighbours or shared corners are removed with OpenCASCADE's defeaturing, which extends the neighbours (golden `pp_multi_face_corner`, `pp_slanted_neighbours`, `pp_three_faces_corner`, `pp_slanted_side_pull`, `pp_slanted_push`). |
| Several faces; click again to drop | Same, also on the moved face in the preview. Tangent Chain picks smoothly connected faces (off by default). |
| Edges -> fillet, fillet face -> radius | Same as before. |
| Q on a sketch profile -> Extrude | Same: visible sketch areas are shaded while Press Pull waits. |

## Known gaps (honest list)

- **Thin extrude** and **New Component**: not built (PartDesign has no thin Pad; components belong
  to the assembly work).
- **Taper with To Object** (and with a join's All): FreeCAD's Pad/Pocket ignore a taper up to an
  object, so SciForge switches the taper off there (the field shows 0 and is greyed) instead of
  pretending. Intersect tapers every extent.
- **Start: Object** works with flat faces/planes parallel to the profile; the offset is measured
  when you press OK (moving the start face later does not move the extrusion; edit it and OK).
- **Several disjoint profiles in a New Body** give one body with several solids in Fusion; a
  PartDesign body holds one solid, so the dialog says so.
- The hidden profile binder shows in the timeline as a Construct item for start-offset, multi-sketch
  and new-body extrudes (the timeline could skip objects with `SciForgeRole`).
- Value boxes: Move's triad, Scale's arrows (they set factor - 1 times a length, not a field)
  and Draft's angle disc have none. Which handle a typed digit goes to (last dragged or hovered,
  hover = within the handle plus 14 px) is SciForge's guess. The red colour and transparency of
  the cut preview, and the blue of the highlighted bodies, are SciForge's choice, not measured.
- Chamfer with Distance and Angle: the arrow sits on the face toward the viewer but still sets
  Distance 1 (measured on the reference face).
- Several bodies (R8): the list is not checked again when an earlier step changes; patterns and
  mirror of a multi-body extrude repeat only the sketch's body; hidden bodies are never listed;
  To Object up to a whole body acts on the sketch's body only; the highlight shows each body as
  it was before this extrude.
- Sketch areas after Finish Sketch light up and select in FreeCAD's yellow / green (SciForge does
  not change FreeCAD's selection colours); heavily crossing curves can shade more pieces inside
  the open sketch than FreeCAD makes areas (a pick extrudes the smallest area around it).
- Ctrl+Z / Ctrl+Y are not bound while SciForge is on (FreeCAD only honours them with its menu bar
  visible); the application-bar Undo/Redo buttons work.
