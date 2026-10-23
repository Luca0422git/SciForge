<!-- A copy of docs/sciforge/parity/text-emboss.md for AI models, made by tools/sciforge/make_ai_docs.py: edit the original, then run the script. -->

# Parity spec: sketch Text and Emboss (outline 7.5 "text", 7.6 "Emboss")

Status: **first pass, not yet signed off by Luca** (no screen captures of his Fusion yet,
outline 2.4). Every behaviour below names where it comes from:

- **Autodesk**: Autodesk's own Fusion help and API reference (Sketch > Create > Text,
  "Text dialog" reference, "Emboss a solid body", "Emboss" reference, Fusion product
  update notes; API `SketchTexts`, `SketchTextInput`, `TextStyles`,
  `HorizontalAlignments`, `VerticalAlignments`, `MultiLineTextDefinition`,
  `AlongPathTextDefinition`, `FitOnPathTextDefinition`, `EmbossFeatures`).
- **Forum**: answers and threads on the Autodesk Fusion community forum.
- **Guess**: not documented anywhere found; SciForge's best guess, to be checked by Luca.

Only behaviour is copied: no Autodesk text, icon or code.

## Behaviour spec: Text (SKETCH > CREATE > Text)

| # | Fusion | Source | SciForge |
|---|---|---|---|
| T1 | Text works in an open sketch; the TEXT dialog opens | Autodesk | same (`SciForge_SketchText`; outside a sketch it says to open one) |
| T2 | Type: Text (in a frame) or Text On Path (the API also has Fit On Path, which the dialog shows as the Fit to Path option) | Autodesk | Type Text / Text On Path, Fit to Path on a path |
| T3 | the frame is placed by two clicks (opposite corners) | Autodesk | same; a click on a sketch point snaps to it; two clicks on the same spot make a frame just round the text |
| T4 | the Text box takes several lines (Enter = new line) | Autodesk | same (Ctrl+Enter = OK in the box) |
| T5 | since Sept 2025 the Text box is an expression: `'Serial ' + SN` (quoted text, parameters, `+`); an unquoted word that is no parameter shows red and OK is refused | Autodesk (product update) | the box takes the expression form (`'text' + param`, `\'` for a quote, numbers); **plain text without quotes is taken as it is** (a beginner types `LUCA`, not `'LUCA'`) **(Guess: kinder than Fusion, on purpose)** |
| T6 | Height: the letters' em box (a capital is about 0.7 of it in Arial) | Autodesk (definition) + Forum (measurements) | same: the font's em box (FreeType face height, calibrated per font) |
| T7 | Height accepts parameters and formulas; Fusion makes a text-height model parameter | Autodesk | Height takes formulas (`h*2`); Change Parameters lists each text's height (row "Text Height") |
| T8 | Angle; a round handle by the frame turns it; a click on one of the frame's points makes it the turning point | Autodesk (angle), Forum (pivot points) | same: 9 frame dots (corners, mid-sides, middle); the handle sits out from the top-right corner |
| T9 | Font: the fonts installed on the computer | Autodesk | same: Windows (`%WINDIR%\Fonts`, per-user fonts) and Linux (XDG / `~/.fonts` / `/usr/share/fonts`) font folders read by SciForge's own OpenType reader; TrueType, OpenType and the first face of TTC collections |
| T10 | Bold, Italic (and Underline in the API) | Autodesk | B / I / U; a family without a bold or italic face gets a thickened or slanted one **(Guess: what Fusion does then is unknown)** |
| T11 | Horizontal alignment Left / Center / Right, Vertical Top / Middle / Bottom (in the frame) | Autodesk | same |
| T12 | Character Spacing in % (0 = the font's own); a forum answer says it only spreads letters apart | Autodesk + Forum | -50 % to 1000 % (negative squeezes) **(Guess)** |
| T13 | Flip Horizontal / Vertical | Autodesk | same |
| T14 | Text On Path: Placement Above / Below the path, Fit to Path, alignment along the path | Autodesk | same; lines, arcs, circles, ellipses and splines; open curves read left to right, closed ones clockwise from their lowest point (a centred text sits on top) **(Guess)**; Fit on a closed curve spreads the letters evenly all round |
| T15 | no line spacing control | Autodesk (absent from the dialog) | none (the font's own line height) |
| T16 | OK makes one undo step; the text is part of the sketch (no timeline step of its own) | Autodesk | same ("Text"; "Edit Text" when changed) |
| T17 | the frame is sketch geometry: it can be dimensioned and constrained; resizing the frame does not scale the letters; the text does not grow the frame | Autodesk + Forum | the frame is four construction lines held as a rectangle; dimensions on them hold the text; letters keep their height. Since sketch-2: a press on a frame corner and a drag resizes the frame (the opposite corner stays, the angle stays, the letters are laid out again; one undo step "Resize Text Frame"); a dimension that holds the size wins and the reason shows by the pointer (`sketch2_text_frame`) |
| T18 | dragging the text moves it | Forum | press and drag on the letters (one undo step "Move Text") |
| T19 | double-click the text, or right-click > Edit Text, to change it later | Autodesk | same in the open sketch; after Finish Sketch, open the sketch (double-click its timeline step) and double-click the text, as in Fusion |
| T20 | Explode Text: the letters become ordinary sketch curves; the link to the text (and its parameter) is gone | Autodesk | same (right-click > Explode Text); features that used the text use the letters' sketch areas instead, so the part does not change |
| T21 | a text is one profile: a click picks the whole text; E / Q extrude it; Fusion's API keeps texts out of the sketch's profile list | Autodesk (API) + Forum | same: one click picks the whole text (in the sketch and after Finish Sketch); E with only a text in the sketch takes it by itself; Q (Press Pull) on a text is an Extrude of it |
| T22 | single-line ("stick") fonts cannot be extruded | Autodesk (Emboss help) | a font with open outlines makes no closed area; Emboss says so and asks for another font |
| T23 | a design opened where its font is missing | Forum (other font used) | the text keeps its saved letters until it is rebuilt, then uses the default font; a message next to the mouse and in the Text dialog says which font is missing and which is used **(message wording: Guess)** |
| T24 | text on the front plane may read mirrored (sketch seen from the back) | Forum | the text follows the sketch's own axes as Fusion does; Flip Horizontal fixes it |

## Behaviour spec: Emboss (SOLID > CREATE > Emboss)

| # | Fusion | Source | SciForge |
|---|---|---|---|
| E1 | Sketch Profiles: closed sketch areas and texts | Autodesk | same; a text counts as one profile |
| E2 | Faces: the faces to emboss on; Tangent Chain adds the faces joined smoothly to them | Autodesk | same |
| E3 | Effect Emboss (adds) / Deboss (removes) | Autodesk | same |
| E4 | Depth; a negative depth swaps Emboss and Deboss | Autodesk | same (also dragging the arrow through the face) |
| E5 | Alignment: Horizontal Distance, Vertical Distance, Rotation Angle, each also a handle on the face | Autodesk | same (two arrows, a turning ring, value boxes next to them) |
| E6 | the profile is wrapped onto flat, cylindrical and conical faces without stretching | Autodesk | same: flat faces exactly (the profile moved rigidly); cylinders by unrolling (an arc of length a is a turn of a / R); cones by unrolling about the apex |
| E7 | faces curved two ways (a ball) are not supported | Forum (Autodesk answer) | **SciForge goes further**: the profile is projected along the sketch's direction onto the face and the dialog says so (outline section 0 rule 8: say plainly what the kernel did) |
| E8 | the profile's middle lands where the sketch's normal meets the face | Guess (forum: placement moves when the text gets longer, i.e. it is centred) | same: the middle of the profiles' bounding box is the anchor |
| E9 | errors when the emboss cannot be made | Forum ("Cannot create emboss feature", "near some features") | plain sentences in the dialog: off the face's edge, longer than the way round the cylinder, deboss past the axis, would split the part, depth too big; OK is refused |
| E10 | live preview, one timeline step, edit by double-click, undo / redo | Autodesk (all features) | same ("Emboss"); the profile's sketch shows while the dialog is open and hides after OK |
| E11 | the depth is a model parameter | Autodesk | Depth, Horizontal / Vertical Distance and Rotation Angle are listed in Change Parameters and take formulas |

## Code

| File | What |
|---|---|
| `sciforge/fonts.py` | Qt-free OpenType reader (names, cmap, kerning, metrics), the font folders of Windows and Linux, a cached font catalogue, default family choice |
| `sciforge/text_core.py` | Qt-free layout: text expressions, lines, alignment, spacing, frame maths, turning about a frame point, letters along a path |
| `sciforge/text.py` | the text object (`Part::Part2DObjectPython`, SciForgeType `SketchText`): letters from `Part.makeWireString` per font, faces with holes, frame lines and their constraints, explode, missing-font fallback |
| `sciforge/text_ui.py` | the Text dialog in the sketch panel, the texts drawn in the open sketch (pick, drag, double-click, Delete, right-click entries), commands Text / Edit Text / Explode Text |
| `sciforge/emboss_core.py` | Qt-free maths: depth and effect, alignment, unrolling onto cylinders and cones |
| `sciforge/emboss.py` | the Emboss step (`PartDesign::FeaturePython`, SciForgeType `Emboss`): laying profiles onto faces, the tool solid, joining, remembering the faces |
| `sciforge/emboss_ui.py` | the Emboss dialog with its handles |
| shared files (only the lines for texts) | `sketch_areas.py`, `profile_pick.py` (a text is one area), `extrude.py`, `extrude_ui.py` (E takes texts), `presspull_ui.py` (Q on a text), `delete.py` (a sketch's texts go with it), `parameters.py` (model parameters), `sketch_marking.py` (right-click entries), `sketch_mode.py` (splines drawn plainly), `ribbon_config.py`, `shell.py` |

No FreeCAD core file was changed.

## Tests

- Unit (no FreeCAD): `SciForgeTests/unit/test_fonts.py`, `test_text_core.py`, `test_emboss_core.py`.
- Golden models (hand-worked numbers): `emboss_flat_rect`, `emboss_flat_deboss`, `emboss_cylinder_rect`, `emboss_cylinder_deboss`.
- Scenarios (real mouse and keys): `sketch_text_basic`, `sketch_text_edit`, `sketch_text_path`,
  `sketch_text_cut`, `sketch_text_more`, `emboss_cylinder`, `emboss_flat`.

## Not built (yet), and why

| Fusion | Why not |
|---|---|
| the red "unquoted word" check of the Text expression | plain text is accepted instead (T5) |
| text in non-sketch places (TechDraw / drawings) | outside this area |
| Emboss with single-line fonts | Fusion refuses them too |
| fonts embedded in the design file | Fusion does not embed fonts either; the fallback message covers a missing font |
| macOS font folders | SciForge targets Windows and Linux |
| Text ON a face (sketch on a curved face) | sketches lie on planes in SciForge, as in Fusion; use Emboss to put text on a curved face |
