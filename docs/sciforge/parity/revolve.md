# Parity spec: Revolve (outline 7.6)

Source: Fusion's documented behaviour and everyday use. Not yet checked against Luca's own
screen captures (outline 2.4). Implemented in `src/Mod/SciForge/sciforge/revolve_ui.py` (the
dialog, the clickable axes and planes, the angle handles, the command) and
`sciforge/revolve.py` (the geometry rules, no GUI; on top of FreeCAD's `PartDesign::Revolution`
and `PartDesign::Groove` with Refine on, plus SciForge's own Intersect feature). Status:
**first pass plus one QA round (branch `sf/revolve-qa`), not yet signed off**.

## What the user does (and what SciForge does)

| Fusion | SciForge |
|---|---|
| CREATE > Revolve; with nothing selected the dialog waits for a profile | Same. With no sketch in the design it says a sketch is needed and opens nothing |
| **Profile**: click inside closed sketch areas (they light up) or on flat faces of the part; click again to drop one | Same. A sketch's only area is taken by itself (the sketch just finished, or the one open when Revolve starts). A face of the part keeps being found when an earlier step renumbers the faces (a hidden helper finds it again by place; golden `sf_revolve_face_profile_follows`) |
| **Axis**: a sketch line, a straight edge of the part, a construction axis or an origin axis | Same. The origin axes are drawn as long red / green / blue lines while the axis is picked (hidden where the part is in front of them, like Fusion's; Fit frames the part, not the lines); construction lines of sketches are drawn dashed. Axes square to the profile are not offered. Profile and axis can be picked in either order; whatever is selected before the command is taken |
| **Type Angle** with a blue handle dragged round the axis | Same; the handle can be dragged past 180 degrees to a full turn and works seen edge-on. A number typed with the mouse over the 3D view goes into the angle box (FreeCAD's view keys do not fire) |
| **Type Full** | Same (one full turn, no direction) |
| **Type To**: as far as an object | Same. While the Object box waits, the origin planes that contain the axis are drawn as squares to click; a flat face, an edge or a corner of the part, a construction plane or point can be clicked as well (where the part is under the mouse the click is the part's). The revolve turns the shorter way to the half-plane the object marks (half a turn either way: the positive way) and **follows the object** when it moves (a hidden helper measures the angle on every recompute; goldens `sf_revolve_to_plane`, `sf_revolve_to_vertex_follows`, `sf_revolve_to_cut`). Objects that cannot work are refused with the reason (a curved face, a plane that does not contain the axis, the object the profile already lies on); OK waits for the object. Switching back to Angle keeps the angle To gave (golden `sf_revolve_to_then_angle`) |
| **Direction** One Side / Two Sides / Symmetric | Same (Symmetric: the angle on each side; Two Sides: a second handle and angle) |
| **Operation** Join / Cut / Intersect / New Body / New Component; turning into material picks Cut by itself, a revolve that touches nothing New Body | Same, unless the user picked the operation. A Join picked by hand that touches nothing is made as a New Body too (Fusion never leaves a second piece in the body; it used to be a second lump). Join <-> Cut keeps the step's place in the timeline, and later steps that used its faces or edges move with it. New Component: `parity/components.md` |
| Value fields take parameters and formulas | Same ("turn / 4"); the revolve follows the parameter later; a typo is said in the dialog and Enter / OK wait; a plain number typed over a formula wins at once |
| Problems are shown in the dialog | Same, in plain words: an axis through the profile, a cut that misses the part, removes all of it or has no solid before it (FreeCAD's Groove accepts these silently), separate solids in one body |
| OK / Enter, Cancel / Esc, one undo step | Same; Enter works with the mouse over the 3D view, Ctrl+Z in the dialog cancels the revolve being made, Ctrl+S / N / O finish it first, other command keys keep a good revolve and start the command. A dialog closed without a change keeps the Redo list |
| Edit: double-click the revolve in the timeline | Same: profile, axis, type (To with its object), direction, angles, formulas and operation are offered again; the sketches are shown so a line can be re-picked as the axis |

## Known gaps (never faked)

| Fusion option | Why not yet |
|---|---|
| **Objects To Cut** (choose which bodies a Cut touches) | A Cut acts on the profile's body only |
| Revolving open curves into a surface (SURFACE tab) | Only closed profiles (solids) |

## A Join that touches nothing (2026-10-13, gaps work)

Sources: **Forum** "Join produces New Body", "Recurring problem with Join vs New Body",
"Cannot Join Bodies with Extrude" (Autodesk Community): a Join whose result touches no body is
made as a new body. A ring revolved beside the part with Join (picked by hand or by itself) is
a body of its own; its timeline edit reads New Body. Golden `sf_revolve_to_vertex_follows` (now
two bodies), scenarios `gaps_join_new_body.py` (J2), `revolve_axes.py` (path 3),
`inspect_construct_use.py` (step 5).

## Value boxes and typing over the view (2026-10-13)

Every drag handle of this dialog has a value box beside it (`taskui.ValueBoxes`): it shows the
field's text with units, follows the handle, takes a value or formula (Enter = OK, a click away
keeps it), never covers a handle or another box, and goes with the dialog. A digit, minus or
decimal point typed with the mouse over the 3D view goes into the box of the handle last dragged
or hovered (else the main one), with its text selected (`taskui.TypeOverView`; FreeCAD's view
keys 0-6 no longer turn the view while the dialog is open). Which handle a digit goes to is
SciForge's guess at Fusion's rule.
