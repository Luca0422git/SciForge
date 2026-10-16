# Parity spec: Extrude (E) and Press Pull (Q) (outline 7.0, 7.6, 9.1)

Source: Fusion's documented Extrude dialog (Start / Direction / Extent / Taper / Operation; a
negative taper narrows) and everyday Fusion behaviour. Implemented in
`src/Mod/SciForge/sciforge/` (`extrude.py` + `extrude_prism.py` geometry, `extrude_ui.py` dialog,
`profile_pick.py` picking, `presspull_core.py` geometry, `presspull_ui.py` dialog, `preview.py`
dialog helpers). Status: **built and tested with real clicks, not yet signed off by Luca**.

## Click a face to end the extrude (Luca's request, branch `sf/fix-extrude-to-face`, 2026-10-16)

Luca: "when extruding, clicking on a face should bring that extrusion to the same height as
that face". Sources (autodesk.com and the Autodesk forum were readable only through search
excerpts): **Autodesk** API reference `ExtrudeFeatureInput.profile`: "when an
ObjectCollection is used all of the profiles and faces must be co-planar"; **Autodesk**
Extrude reference: To Object ends at "a body, face, or plane". **Forum** "Extrude to Face /
Edge / Vertex" (Autodesk Community): To Object is parametric; without it "Fusion still
extrudes/revolves to that object but not parametrically, it only sets the extrusion distance
... to the current value"; "the 'To Object' in Fusion supports only Face, Body and Vertex, but
not Edge". **Forum** "Common Bug/Issue when using Extrude tool and snapping to surface or
face": fixed "by editing the existing extrude/push/pull feature, and dragging the arrow and
clicking on the face to snap to again". **Forum** (Press Pull): "Once you start the drag,
clicking a face will cause the face being dragged to snap to the clicked face". **Forum**
IdeaStation "Extrude to limit" (an Autodesk alumnus): Snap To "infers a distance value after
indicating a parallel plane". **Forum** (Shapr3D community, a user describing Fusion): "you
just click on any other geometry at that extent, a surface, a point, an offset, and the
extrude calculates the distance it needs to extrude by and snaps to the distance". **Forum**
"how do I extrude up to a body?": a curved surface is reached with the To extent. **Guess**:
rows marked so (Fusion's own wording is never copied: the dialog's words are SciForge's).

| Fusion (source) | SciForge |
|---|---|
| The profiles of one extrude lie in one plane (Autodesk) | Once a profile is picked, a click on a face out of the profile's plane is no profile: it says where the extrusion ends. A face in a profile's plane is picked or dropped as before; with the Profiles box empty a click on a flat face is the profile, as before (Guess: Fusion's first selection box takes the clicks until it has something) |
| Distance extent: a picked face or point sets the distance to reach it, not parametric (Forum) | A flat face parallel to the profile, a vertex, or a parallel construction plane sets Distance to the exact number (minus for one below), Extent stays Distance, the arrow and its value box move there, and the dialog says "Up to the face: 12.5 mm" ("the point", "the plane"); typing or dragging afterwards drops the words |
| Dragging the arrow over a face snaps to it (Forum, twice); a parallel plane gives the distance (Forum) | While the arrow is held, the mouse over a parallel flat face or a vertex makes the distance that height exactly (the preview and the value box show it, the face or point is marked in blue); let go there and it stays, the arrow jumps to it. Over anything else the arrow drags as before (two decimals). A press on the arrow let go without moving snaps to nothing. While the button is down Coin's arrow keeps following the mouse (its dragger takes its position from the mouse on every move), so the arrow itself jumps on the release |
| Two Sides, Symmetric (Guess) | Two Sides: the side the face is on (side one is the way its distance points); Symmetric: the same distance each way (Whole Length: twice it) |
| A face the extrusion cannot end on at one height: To Object (Autodesk; Forum for curved surfaces) | A curved or tilted face switches Extent to To Object with that face (Extend To Selected Face): "Ends on the curved face (To Object)". Symmetric cannot go To Object (Fusion's dialog): refused, with what to do. A side already To Object takes a clicked flat face as its new object (Guess). A face running along the extrusion is refused with the reason; an edge does nothing (Forum: To Object takes no edge) |
| Press Pull on a sketch area is an Extrude (Fusion) | The same clicks and snaps in the Extrude it opens |
| Every operation, edit from the timeline, one undo step | Join, Cut (a click below the sketch into the part turns it into a Cut by itself), New Body, bodies in (moved) components, edit from the timeline, Esc / Cancel, Undo / Redo, save / reopen (a plain length is stored) |

Found on the way: **FreeCAD's Pad "up to face" on a curved face of another body ends in the
wrong place** (a post up to a cylinder's underside came out 22494 mm^3 instead of 4753, through
the cylinder). To Object on a curved face of another body is now SciForge's own extrude
feature (`extrude.curved_elsewhere`, in `_structure`), which ends exactly on the face; golden
`extrude_to_cylinder_face`. With a curved face of the same body the Pad is right and stays a
Pad (an older one with later steps on it could not change its kind).

Built in `extrude_to_face_core.py` (the rules and words, Qt-free, `test_extrude_to_face_core`),
`extrude_to_face.py` (what is under a click or the mouse, the snap mark) and `extrude_ui.py`.
Scenarios `extrudeface_basic`, `extrudeface_sides`, `extrudeface_objects`, `extrudeface_drag`.

## Wave 4: To Object's Extend and Offset, a Start Object that follows (branch `sf/modeling-2`, 2026-10-14)

Sources: **Autodesk** Extrude reference, through search excerpts: To Object ends at "a body,
face, or plane"; "Extend (To Object extent type only) determines how the end of the extrusion
meets the selected object"; Start Object "starts extrusion from a face or plane that you
select"; the Extend labels To Selected Face, To Adjacent Faces, To Body, Through Body are
Fusion's dialog words (help "Extrude a solid body"). **Forum**: "Very Buggy Extrude From Object
To Object" (defect FUS-116774). **Guess**: rows marked so.

| Fusion (source) | SciForge |
|---|---|
| To Object a face, **Extend**: To Selected Face (the face's surface extended) or To Adjacent Faces (the face and its neighbours as they are) (Autodesk) | Same choice in an Extend row, for side one and side two. To Selected Face as before. To Adjacent Faces: the extrusion ends on the face and on the faces that share an edge with it (a column partly over a slope ends on the slope there) (golden `extrude_to_adjacent_faces`) |
| To Object a body: To Body or Through Body (Autodesk) | To Body: up to where the extrusion first meets the body (as before); Through Body: on through the body to its far side (golden `extrude_through_body`) |
| To Object a plane: no Extend choice (Guess: a plane is endless) | Same: the row hides |
| **Offset** from the object (Autodesk) | An Offset field for each side with To Object (it takes formulas): the end moves that far past the object, a negative value stops short of it (golden `extrude_to_object_offset`) |
| **Start: Object** follows when the object moves (Guess: Fusion is parametric there too) | A hidden helper measures the start offset from the profile to the object at every recompute, so the extrusion moves with the face or plane when an earlier step changes (golden `extrude_start_object_follows`) |

Tests: scenario `modeling2_extrude` (To Adjacent Faces and To Selected Face measured, edit
from the timeline, undo / redo, Esc, a plane with Offset -5, save / reopen); the goldens above
and `extrude_to_selected_face_extended`.

## Extrude

| Fusion | SciForge |
|---|---|
| Profiles: click closed areas; click more to add, again to drop | Same. Areas are FreeCAD's own sketch regions (`MakeInternals`, `InternalFaceN`): a circle in a rectangle gives the ring and the disc; crossing curves split areas (two overlapping circles: 3 areas). Flat faces of the part are profiles too. |
| One profile is picked by itself | A sketch just finished (or selected) with exactly one area is taken at once; with several, E waits for clicks. |
| Start: Profile Plane / Offset / Object | Same. Offset has its own blue arrow. Object: a flat face or plane parallel to the profile. |
| Direction: One Side / Two Sides / Symmetric | Same. Two Sides has a Side Two group (extent, distance, taper). Symmetric has Measurement Half / Whole Length (Half by default). |
| Extent: Distance / To Object / All | Same. To Object: a face, a plane or another body (extends the face's plane). All: through everything, with Flip. |
| Taper Angle with a handle | Field plus a curved blue handle at the end of the extrusion; negative narrows (as Fusion). |
| Operation: Join / Cut / Intersect / New Body / New Component | Join, Cut, Intersect, New Body, New Component (`parity/components.md`). Dragging into the part switches to Cut unless you chose. The first solid shows New Body. |
| Live preview, OK / Cancel / Esc, one undo step | Same. Esc works with the mouse in the 3D view. |
| Manipulators drawn over the model and grabbable through it | Same (2026-10-13, Luca: "arrows get occluded by bodies"): the arrows, the taper disc and the hole's position handle are drawn in front of any body (Coin's annotation node) and a press on a visible arrow starts the drag even when a body is nearer to the camera (pick style "shape on top"); `taskui.on_top_root`, scenario `handles_on_top`. The whole drawn arrow is grabbable, the half that sits inside the part included: a press on its line takes the arrow, a press beside it picks the face (`extrude_presspull_qa3` P14). |
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

### Thin Extrude (2026-10-13, branch `sf/gaps`)

Sources (Autodesk's own pages are not reachable from the sandbox; their search excerpts are
quoted): **Autodesk** Extrude reference (SLD-REF-EXTRUDE): Type "Thin Extrude: extrudes a thin
wall along selected open or closed profiles"; "Wall Location (Thin Extrude type only): Side 1,
Side 2 (offset the extrusion to one side of the profile), Center (centers the extrusion on the
profile)"; "Wall Thickness (Thin Extrude type only)". **Autodesk** API reference:
`ExtrudeFeatureInput.setThinExtrude(wallLocationOne, wallThicknessOne, wallLocationTwo,
wallThicknessTwo)`, so a Two Sides thin extrude has a wall location and thickness per side;
`ThinExtrudeWallLocation` Side1 / Center / Side2. **Forum** (Autodesk Community, "Thin Extrude
issue", "Thin extrudes of open sketch lines"): open sketch lines can be picked once Thin
Extrude is on; a user reports the wall goes inside the line by default and Side 2 puts it
outside. **Tutorial** (techandespresso "Thin Wall Tool"): a taper can be set with a thin
extrude. Not found anywhere: the default thickness (SciForge: 1 mm, **guess**), which side of an
open curve Side 1 is (SciForge: the left of the curve as drawn, seen from the sketch's normal,
**guess**), sharp or round outer corners (SciForge: sharp, **guess**), a drag handle for the
thickness (none found; SciForge has none).

| Fusion | SciForge |
|---|---|
| Type: Extrude / Thin Extrude, first in the dialog | Same (a drop-down). Thin Extrude shows Wall Location and Wall Thickness under the taper (and again under Side Two for Two Sides) |
| Profiles: closed areas and flat faces (the wall follows every loop of their outline: a rectangle gives a tube, a ring a wall at both circles), and open sketch curves | Same. A click on a sketch curve takes the curves joined to it (an L of two lines is one profile); a click on a picked curve drops them; picked curves are drawn in blue, a curve under the mouse lights up |
| Wall Location Side 1 / Center / Side 2 | Same. Side 1: into a closed profile (out of a hole), on the left of an open curve; Side 2 the other side; Center half each way |
| Wall Thickness (parameters and formulas) | Same; default 1 mm; too thick for the profile is said in the dialog ("closes up inside it") and OK waits |
| Every extent, direction, start, taper and operation | Same: a taper tilts the wall and keeps its thickness (a positive taper leans it towards Side 2, outward for a closed profile); To Object, All, Two Sides, Symmetric, Offset / Object start; Join / Cut / Intersect / New Body / New Component, the automatic operation and the bodies row use the wall, not the area inside it |
| Edit from the timeline, undo / redo | Same (everything comes back, also the curves) |
| Turning Thin Extrude off with curves picked | The curves are dropped and the dialog says why (a solid extrude needs areas or faces) |

Built as SciForge's own extrude feature (`sciforge.extrude.ExtrudeFeature`, properties `Thin`,
`WallLocation(2)`, `WallThickness(2)`); the wall's cross-section is worked out in
`extrude_prism.thin_walls` (OpenCASCADE's 2D offset of each loop or curve; a straight curve is
done directly, OpenCASCADE finds no plane for it). Golden models `extrude_thin_tube`,
`extrude_thin_open_l`, `extrude_thin_arc_center`, `extrude_thin_taper_center`,
`extrude_thin_to_cylinder_face`; scenario `gaps_thin_extrude` (4 paths).

### Taper with every extent (2026-10-13, branch `sf/gaps`)

Sources: **Forum** (Autodesk Community, "How to get the extrusion taper with an offset"): a taper
with To Object is measured against the "to" object; **Autodesk** Extrude reference: To Object
ends at "a body, face, or plane". So the taper works with To Object whatever the object is, and
each side of Two Sides has its own taper.

| Fusion | SciForge |
|---|---|
| Taper up to a flat face or plane | Same (since the first QA pass) |
| Taper up to a curved face | Same: the extrusion ends on the face's whole surface (a cylinder's face: the whole cylinder) |
| Taper up to a whole body (picked in the browser) | Same: the extrusion ends where it first meets the body; a profile partly missing the body is said in the dialog |
| Two Sides: a taper per side | Same (Side Two's Taper Angle) |

FreeCAD's Pad ignores a taper up to a face or a body, so these are SciForge's own extrude
feature (`extrude_prism._to_shape`: a long prism split by the face's surface or cut by the
body, keeping the piece that holds the profile). Golden `extrude_taper_to_body`; scenario
`gaps_extrude_taper_to` (a column tapered up to another body, edited, undone; Two Sides with
a taper per side).

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

- **Click a face to end the extrude** (2026-10-16): Press Pull on a *face* (an offset, not an
  extrude) does not snap its arrow to a clicked face yet (Fusion does once the drag started,
  Forum); the dragged arrow snaps to parallel faces and vertices, not to edges, sketch points
  or construction planes (a plane works with a click); the arrow itself jumps to the face
  only when let go (Coin's dragger, see the section at the top); a copy of a component (an
  App::Link instance) gives the height of the original's place, like every face pick of the
  extrude; a sketch area of another sketch at another height is still taken as a profile, as
  before (Fusion keeps the profiles in one plane); a sketch area hidden behind *another*
  body still takes a click there (the hiding test looks at the profile's own body only).

- Thin Extrude, New Component and tapers with every extent are built (sections above). Thin
  Extrude's defaults (1 mm, the side an open curve's Side 1 is, sharp outer corners) are
  guesses to check in Fusion.
- **To Object options** (2026-10-14): Extend and Offset are built (section at the top). Found
  on the way, not fixed: a Cut To Object a face that FreeCAD makes as its own Pocket, with the
  profile partly inside the material, also cut away material above the profile plane (900
  instead of 720 mm^3 in the scenario's first try, where the pocket's square overlapped the
  column extruded before it); the scenario's pocket was moved off the column.
- **Start: Object** works with flat faces/planes parallel to the profile (it follows them since
  2026-10-14).
- Several disjoint profiles in one extrude give one body with several solids, as in Fusion
  (FreeCAD 1.1's bodies allow it). A Join that touches no body at all is made as a New Body
  (also from scripts and old steps that have no bodies list; 2026-10-13, sources in
  `parity/revolve.md`); one whose profiles only partly touch keeps the far piece in the body,
  like Fusion's multi-lump bodies (guess).
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
