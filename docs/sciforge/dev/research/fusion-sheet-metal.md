# Fusion SHEET METAL tab: behaviour spec for SciForge

Black-box documentation research, done 2026-10-23, targeting Fusion as of the September 2026
release (v.2705). Copy the behaviour, never Autodesk's icons, wording or code.

## How to read this file

**Source tags.** Each fact carries one of these tags:

- **A[Rn]**: Autodesk sources: help pages, the API reference, the blog and release notes. The
  reference list is at the end.
- **F[Fn]**: community forums and third-party tutorials.
- **G**: my own inference, used where nothing confirmed the point. A "G" table row is a
  **recommended SciForge choice**, not a verified Fusion fact.
- **G(Inv)**: borrowed from Autodesk Inventor's documentation of the same concept. Fusion's
  sheet metal kernel and dialogs come from Inventor, so these are good hints, but they are still
  unconfirmed for Fusion.

**Research limits.** No page could be fetched directly. WebFetch failed on DNS for every host,
and curl was blocked. Every fact below therefore comes from search-engine excerpts of the cited
pages. The search budget ran out before I could confirm three things: the exact menu order, the
built-in rule library values, and the browser icons. Those points are marked G and listed in §5.

**API dates.** The API classes give exact option names. Their "introduced" dates tell when a
feature reached the API; the UI usually had it earlier:

| Version | Added |
|---|---|
| Nov 2022 | rules |
| Sep 2023 | Rip |
| Sep 2025 | Hem, BendPositionTypes |
| Jan 2026 | Corner Closure |
| May 2026 | Unfold-Refold pairing |
| Jul 2026 | Fold (the Bend command), Join by Bend |
| Sep 2026 | flange orientation, lofted flange forming type |

---

## 1. Tab layout, groups and menu order

The Design workspace has the tabs SOLID, SURFACE, MESH, **SHEET METAL**, PLASTIC, UTILITIES and
MANAGE. The full order is in SciForge `docs/sciforge/parity/ui-shell.md`. SHEET METAL holds every
sheet metal command (A[R4] "Design > Sheet Metal > Create > Flange"; A[R13]
"Sheet Metal > Create > Hem").

### 1.1 Groups (icon row, left to right)

| Group | Notes | Src |
|---|---|---|
| CREATE | New Component, Create Sketch, Flange, Bend, Hem, Create Flat Pattern, plus the repeated solid commands | A[R48], A[R13], A[R18], F[F5] (Flange and Bend in the CREATE drop-down) |
| MODIFY | Unfold, Refold, Rip, Convert to Sheet Metal, Sheet Metal Rules, plus the repeated solid modify commands | A[R48] (Unfold and Sheet Metal Rules under Modify), A[R7] (Modify > Sheet Metal Rules), A[R50] |
| ASSEMBLE | Same as the SOLID tab (joints and so on) | G |
| CONSTRUCT | Same as the SOLID tab (planes, axes, points) | G |
| INSPECT | Same as the SOLID tab (Measure, Interference, Section Analysis, Center of Mass...) | G |
| INSERT | Same as the SOLID tab | G |
| SELECT | Same as the SOLID tab | G |

### 1.2 CREATE menu

The exact order is G, built from the members the sources confirm.

1. New Component. A[R48]. The New Component dialog has Type: **Standard / Sheet Metal**
   (SciForge parity/components.md, item 4).
2. Create Sketch. G.
3. **Flange.** One command that covers base, edge, contour and lofted flanges. A[R4] A[R44]
4. **Bend.** A[R18] "Design > Sheet Metal > Create > Bend"
5. **Hem.** A[R13]. The API arrived Sep 2025 A[R30]; the UI was probably released at the same
   time (G).
6. **Join by Bend.** New in Sep 2026 A[R42]. Its menu position is unknown; G puts it in CREATE.
7. **Create Flat Pattern.** A[R48]. One forum post places it under Modify, and it may also have
   its own icon (G).
8. Separator, then the repeated solid commands (G, from memory of the UI):
   Extrude, Hole, Rectangular Pattern, Circular Pattern, Pattern on Path, Mirror, Derive.

### 1.3 MODIFY menu

The order is G.

1. Press Pull. F[F17]
2. **Fillet (sheet metal)** and **Chamfer (sheet metal)**: dedicated tools added Sep 2026
   A[R42] A[R41].
3. **Unfold.** A[R48] A[R12]
4. **Refold.** A[R46] A[R12] A[R50]. It becomes available on the ribbon once an Unfold is active
   (A[R50] handout).
5. **Rip.** A[R47] A[R33]
6. **Corner Closure.** API Jan 2026, with overlap control added Sep 2026 A[R39] A[R42]. The UI
   label is G.
7. **Convert to Sheet Metal.** A[R8] A[R9]
8. Separator, then the repeated modify commands (G): Split Face, Split Body, Combine,
   Move/Copy, Align, Delete, Physical Material, Appearance, Manage Materials.
9. **Sheet Metal Rules.** A[R7]
10. Change Parameters, Compute All. G

### 1.4 FLAT PATTERN contextual tab

Fusion shows this tab while a flat pattern is active (§2.12). A flat pattern is modal: you must
leave it to get back to the folded model (A[R48] "A flat pattern is modal... Exit Flat").

- **Export DXF**: "On the toolbar, click Export DXF. The Export Flat Pattern As DXF dialog
  displays" A[R19].
- Other groups (CREATE: sketch; INSPECT: Measure; SELECT): G.
- **Finish Flat Pattern**: the green check at the right end of the toolbar F[F13] F[F14]. The DXF
  Export button sits to its left F[F14].

### 1.5 Solid commands on sheet metal bodies (summary, detail in §2.13)

- An Extrude cut or a Hole that goes through the sheet, perpendicular to the top or bottom face,
  keeps the body valid sheet metal. It shows in the flat pattern as a cut-out (G).
- Cuts that cross a bend should be made in an Unfold-Refold pair (A[R12] A[R46]).
- Joins that break uniform thickness make the flat pattern fail (G; F[F5] says bodies must be
  uniform thickness).

---

## 2. Commands

### 2.1 Sheet Metal Rules (MODIFY > Sheet Metal Rules)

**Purpose.** A rule holds every manufacturing default: thickness, gap, bend radius, K-factor,
bend relief and corner relief. Sheet metal features take their values from it (A[R6] A[R20]).

**The dialog** (A[R7] F[F18] F[F19] F[F6]):

- **Two lists.**
  - **In This Design** holds the rules used by or copied into this document.
  - **Library** holds the user's rule library, a per-user store shared across documents
    (G, F[F8]).
- **The default rule.** One library rule is marked as the default, for example
  "Steel (mm) (Default)" F[F6]. The default library rule cannot be deleted (A[R26]).
- **Hover actions.** Hovering a rule shows a **pencil (Edit)** F[F6]. Other hover actions are
  **New Rule** (based on the hovered rule, inheriting its units) F[F5], copy between Library and
  In This Design ("Copy to library", F[F8]) and Delete.
- **Units.** A rule's units (mm or in) are fixed when the rule is created: "permanently
  associated with a rule" (A[R20]). This is why a new rule is started from a rule that already
  has the wanted units (F[F5]).
- **Rule edit dialog.** It has the fields in §3.1. Every length field accepts an expression that
  uses **`Thickness`**, for example `Thickness / 2` or `Thickness * 1` (A[R45]: "Values can be
  defined as parametric functions of the sheet metal thickness, by referring to 'Thickness' in
  the expression"). The shipped library uses this style (A[R45]).
- **Using a rule.**
  - **Active rule per component (G).** A sheet metal component has an active rule. The Flange
    dialog has a **Rule** drop-down for the body being created (A[R44] "specify the Sheet Metal
    Rule that applies to your part").
  - **Editing a rule in In This Design (G).** All sheet metal bodies that use the rule
    recompute, so thickness, bends and reliefs all update.
  - **Editing a rule in the Library (G).** Existing designs keep their own copy.
  - **Rules can be swapped, not detached.** Once attached, a rule cannot be detached, but it can
    be swapped or edited (A[R9]).
  - **Locked thickness.** A body made by Convert to Sheet Metal has its thickness locked to the
    detected value (A[R8], F[F7]). The user sees a lock icon on Thickness (F[F7]).

**Browser and timeline.** Rules do not appear in the browser or timeline (G). Rule edits behave
like parameter edits: the whole model recomputes.

**Errors.**
- K-factor outside 0 to 1 is refused (A[R25]).
- Duplicate rule names in the same list are refused: "name must be unique within the library or
  design" (A[R26]).
- Deleting the default library rule is refused (A[R26]).
- Deleting a rule that is in use is refused (G).

### 2.2 Flange (CREATE > Flange)

One command with several modes.

**Mode is chosen by what is selected** (A[R2] A[R4] A[R44] A[R5]):

| Selection | Mode | Result |
|---|---|---|
| A **closed** sketch profile | **Base flange** | A flat plate: the profile extruded by the rule thickness |
| An **open** sketch profile (lines, arcs, splines) | **Contour flange** | A multi-bend flange. Sharp corners become bends with the rule's Bend Radius |
| One or more **edges** of a sheet metal body | **Edge flange** | A wall bent up from each edge |
| Type = **Lofted**, plus two profiles | **Lofted flange** | A transition between two profiles (§2.2.4) |

A type selector at the top of the dialog switches between the standard flange and Lofted
(A[R44]: "create a lofted flange by selecting the Lofted Type within the Flange command dialog";
UI since July 2022).

**Common inputs (all modes)**

| Input | Type / choices | Default | What it does | Src |
|---|---|---|---|---|
| Type | Flange / Lofted | Flange | Lofted switches to the two-profile loft mode | A[R44] |
| Selection | Profiles or edges (multi-select; each row has its own settings) | – | Decides base, contour or edge mode | A[R2] ("Each row in the selection box is a separate profile, and each row can have its own settings") |
| Rule | Rules in This Design | The component's active rule | The thickness, radius and reliefs to use | A[R44], G |
| Operation | New Body / Join (Edge flange: only with a **single** edge selected) | New Body for base flange; Join for edge flange | Whether the result is a new body | A[R27] (BaseFlangeInput.operation defaults to new body), A[R3] ("the Operation option is only available when you select a single edge") |
| Bend Radius override | Checkbox + value | Off (rule value) | Overrides the rule bend radius for this flange; unchecking restores the rule | A[R1] |
| Bend Relief override | Checkbox + Relief Shape (Straight / Tear / Round), Relief Width, Relief Depth, Relief Remnant | Off | Overrides the rule's bend relief for this flange only | A[R1] |
| Corner Relief override (2 bends) | Checkbox + Relief Shape (Round / Square / Tear / Trim To Bend / Linear Weld / Arc Weld), Relief Size, Relief Placement (Tangent / Intersection) | Off | Overrides the 2-bend corner relief for this flange | A[R1] |
| Corner Relief override (3 bends) | Checkbox + Shape (No Replacement / Intersection / Full Round / Round With Radius), Radius | Off | Overrides the 3-bend corner relief | A[R1] ("a separate set for corners where 3 bends meet"), A[R23] |

#### 2.2.1 Base flange (plate)

| Input | Type / choices | Default | What it does | Src |
|---|---|---|---|---|
| Profile | One or more closed sketch profiles (regions) | – | The plate outline | A[R2] |
| Orientation | **Side 1 / Side 2 / Center** | Side 1 | Side 1 puts the thickness on the positive normal of the sketch plane. Side 2 puts it on the negative normal. Center splits it T/2 each side | A[R2], A[R28] (FlangeOrientations: SideOne=0, SideTwo=1, Centered=2; Sep 2026) |
| Rule | – | Active | The thickness comes from the rule; there is no thickness field in the dialog | A[R44], G |
| Operation | New Body / Join | New Body | | A[R27] |

- **Preview.** A semi-transparent plate, with a flip arrow on the canvas (G).
- **Browser and timeline.** The sheet metal body is added to the Bodies folder of the active
  component, which must be a Sheet Metal component (G). The timeline gets "Flange1" with the
  flange icon (G).
- **Errors.** Running Flange in a Standard component either offers to convert the component to
  sheet metal or is refused (G). Self-intersecting profiles are refused (G).

#### 2.2.2 Edge flange

**Selection.**
- Pick linear edges of an existing sheet metal body. These are the long edges where a top or
  bottom face meets a thickness (side) face (G).
- Several edges can be picked at once. Adjacent picked edges get mitered corners and corner
  reliefs automatically (G(Inv): auto-miter "during creation... of at least two flange edges in a
  single operation"; A[R1] corner relief override).
- Thickness edges (short side edges) cannot be picked (G).

| Input | Type / choices | Default | What it does | Src |
|---|---|---|---|---|
| Edges | Edge selection (multi) | – | Where the flanges go | A[R2] |
| Height extent | **Distance** / **To Object** | Distance | Distance gives a typed height measured from the Height Datum. To Object runs the flange until it meets a selected face, plane or body, with an offset; it is **only valid with a single edge** | A[R2], A[R27] (setDistanceExtent / setToObjectExtent) |
| Height (Distance) | Length, expression; drag arrow on canvas | G: 10 mm (0.5 in in inch documents) | The flange length | A[R2], G for the default |
| Height Datum | **Inner Faces / Outer Faces / Tangent To Bend** | G: Inner Faces | Inner Faces measures from the intersection of the inner faces of base and new flange. Outer Faces measures from the intersection of the outer faces. Tangent To Bend measures from the bend tangent line, parallel to the new flange | A[R2], F[F15] tutorial |
| Angle | Angle, expression | **90°** | Bend angle between the base flange and the new flange. 90° is perpendicular. G: range (0°, 180°]; 180° folds back onto the base (hem-like) | A[R27] (EdgeFlangeInput.angle default 90 deg), A[R48] ("great way to create features, such as hems") |
| Bend Position | **Inside / Outside / Adjacent / Tangent** | G: Inside | Where the bend sits relative to the selected edge (geometry in §4.4). Inside: the bend sits inside the boundary of the outermost faces, so outer dimensions are kept. Outside: the bend sits outside the innermost faces. Adjacent: the bend starts at the selected edge. Tangent: the bend is tangent to the selected edge | A[R2]. API names: Outside=1, Inside=2, StartEdge=3 (Adjacent), TangentToSide=4, Legacy=0 unused (A[R29]) |
| Flip | Toggle / arrow | Off | Turns the new flange 180° over the base flange (up or down) | A[R2] ("Flip the flange 180 degrees over the base flange") |
| Flange Width Type | **Full Edge / Symmetric / Two Sides / Two Offsets** | Full Edge | Full Edge: the whole edge length. Symmetric: a typed total width centred on the edge midpoint (half each side). Two Sides: centred, with a separate distance each side. Two Offsets: between two picked reference faces or planes, with an offset from each | A[R2] |
| Width / Distance 1 / Distance 2 / Offset 1 / Offset 2 | Lengths | G: width = edge length | Per the width type | A[R2] |
| Operation | Join / New Body (single edge only) | Join | New Body makes a separate body, for example for welded constructions | A[R3], G |
| Overrides | As in the common table | Off | | A[R1] |

- **Handles and preview.**
  - A distance arrow on each flange for Height (A[R2] "Drag the distance manipulator handle").
  - An angle handle (G).
  - Preview flanges with miters and reliefs computed live (G(Inv) "if adjacent flanges do not
    preview with miter corners...").
- **Miter between adjacent edge flanges.**
  - When two picked edges meet at a corner of the base and both flanges go up, they are
    auto-mitered. The two flanges are trimmed on the corner bisector, leaving a gap equal to the
    rule's **Miter/Rip/Seam Gap** (A[R6] "space between flange gaps"; G(Inv) auto-mitering).
  - The bend zones meet in a 2-bend corner, which gets the rule's 2-bend corner relief
    (A[R1] A[R22]).
- **Bend relief.** Where the flange is narrower than the parent edge (Symmetric, Two Sides, Two
  Offsets, or a partial To Object), the rule's bend relief is cut at each end of the bend zone
  (§4.5) (A[R6], G).
- **Browser and timeline.** "Flange<n>" joins the existing body (G).
- **Errors** (G unless noted):
  - Curved (non-linear) edges cannot be picked. F[F11] shows that wrapping a flange round a
    corner radius does not work; use a contour flange with arcs, or a lofted flange.
  - A flange that would intersect another part of the body fails to compute.
  - Height must be > 0.
  - To Object with more than one edge is refused (A[R27]).

#### 2.2.3 Contour flange

**Selection.** An open sketch profile made of lines, arcs or splines (A[R2]).

- The profile can stand alone, which makes a new body.
- Or it can start at the end of an edge of an existing sheet metal body, with the sketch plane
  perpendicular to that edge. The flange is then joined along the edge (G).
- Each selection row is a separate profile with its own settings (A[R2]).

| Input | Type / choices | Default | What it does | Src |
|---|---|---|---|---|
| Profile | Open sketch chain | – | The cross-section path; thickness is laid along it | A[R2] |
| Orientation / thickness side | Side 1 / Side 2 / Center | Side 1 | Which side of the path line the thickness goes | A[R2] (for closed profiles), G for contour |
| Distance (extent) | Length, with an arrow handle | G: 10 mm | How far the cross-section is extruded perpendicular to the sketch plane | A[R2] ("Drag the distance manipulator handle on the canvas, or specify an exact value") |
| Direction | One side / Symmetric / Two sides | One side | Which way the extrusion goes | A[R27] ("extent direction defaults to a one-sided extent") |
| Width type (when attached to an edge) | Full Edge / Symmetric / Two Sides / Two Offsets | Full Edge | Same as the edge flange | A[R2], A[R48] (tutorial sets each edge to Symmetric) |
| Height Datum / Bend Position (when attached to an edge) | As edge flange | | | A[R48] |
| Rule, Operation, overrides | As common | | | |

**Geometry.**
- Every **sharp vertex** of the open profile becomes a bend with the rule's Bend Radius, or the
  override (A[R5]: "When there are sharp corners in a flange profile, Fusion creates bends that
  use the Bend Radius value from the Sheet Metal Rule"; F[F15]).
- Sketched **arcs** become cylindrical bends of the arc radius (G). An arc smaller than the rule
  radius is probably still kept as drawn (G).
- The thickness sits on the chosen side of the sketch line, so the sketch line is the inner or
  outer mold line (G).

**Errors.** A closed profile switches the command to base flange. Self-intersection fails (G).

#### 2.2.4 Lofted flange (Type = Lofted; UI since July 2022 A[R44])

**Selection.** Two closed profiles or two open profiles, on separate planes (A[R15] A[R16]).

- The profiles may contain **only lines and arcs**; for splines use Contour (A[R15]).
- Auto-chain is on: clicking one segment of an open profile selects the whole connected chain
  (A[R15]).

| Input | Type / choices | Default | What it does | Src |
|---|---|---|---|---|
| Profile 1, Profile 2 | Sketch profiles, both open or both closed | – | The two ends of the transition | A[R15], A[R38] ("at least two profiles") |
| Orientation | Side 1 / Side 2 / Center | Side 1 | Which side of the profiles the thickness goes | A[R15] |
| Forming Type | **Brake Form / Die Form** | G: Brake Form | Brake Form makes a press-brake part: the surface is approximated by a series of straight bends (facets) and flattens with bend lines. Die Form makes a stamped part: a smooth, continuous ruled surface | A[R16], A[R38] (LoftedFlangeFormingTypes, Sep 2026) |
| Facet Control (Brake Form only) | **Chord Tolerance / Facet Angle / Facet Distance** (A[R44] also lists **Face Number**) | Chord Tolerance | Chord Tolerance: the maximum gap between a straight facet and the true curve. Facet Angle: the maximum angle between a facet chord and the curve tangent. Facet Distance: the maximum facet width (chord length). Face Number: a fixed number of facets per arc | A[R15], A[R38], A[R44], G(Inv) for Facet Distance |
| Value | Length / angle / count | G: chord tol 0.1 mm; angle 10°; count 6 | Per the facet control | G |
| Rule | Rules in the design | Active | | A[R44] |
| Operation | New Body / Join | New Body | | G |

- **Flattening.**
  - An open-profile lofted flange flattens directly in the flat pattern. The facet bend lines
    appear as bend lines (F[F12]).
  - A **closed**-profile lofted flange needs an extra sketch and feature, a rip or seam cut,
    before it can be flattened (F[F12]).
- **Errors.** Mixing an open and a closed profile is refused. A spline in a profile is refused.
  Coplanar profiles are refused (G, from the A[R15] requirements).

### 2.3 Bend (CREATE > Bend)

**Purpose.** Bends an **existing** flat sheet metal flange along one or more sketch lines. Unlike
Flange it **adds no material**: it reshapes the body (A[R11] A[R47]). The API calls it **Fold**
(FoldFeature, July 2026; A[R31]).

**Selection.**
1. A **Stationary Side**: a top or bottom planar face of the sheet metal body. It stays fixed
   (A[R18] "Stationary Side: A top or bottom planar face of a sheet metal body with sketched
   bend lines").
2. **Bend Lines**: sketch lines that lie in a plane parallel to the stationary face. In practice
   you sketch on the face (A[R11]). The lines must lie on the stationary face or on faces
   connected to it (A[R31]).
3. For several lines, **order matters**: pick the line **farthest from the stationary side
   first** (A[R11]).

| Input | Type / choices | Default | What it does | Src |
|---|---|---|---|---|
| Stationary Side | Planar face (top or bottom) | – | The face that does not move | A[R18], A[R31] |
| Bend Lines | Sketch lines (multi; each line has its own row and settings) | – | Where to bend | A[R11], A[R31] (FoldBendLineDefinitions collection) |
| Bend Line Position (per line) | **Start / Center / End** | G: Center | Where the sketch line sits on the bend zone *in the flat state*. Start: the line is the bend's start tangent line, on the stationary side. Center: the line is the bend centre line. End: the line is the far tangent line | A[R31] (FoldBendLinePositionTypes "start, center, or end of the bend" in the flat state), F[F3] (UI shows Start / Center ("Middle") / End) |
| Angle (per line) | Angle | **90°** (G) | The bend angle | A[R31] (bendAngle model parameter) |
| Flip / direction (per line) | Toggle | Off | Bends up or down relative to the stationary face | A[R47] ("bend direction control"), G |
| Bend Relief (per line) | Checkbox "allow bend relief" | On | Cuts the rule's bend relief at the ends of the bend line, where the bend meets material that does not bend | A[R31] (isBendReliefAllowed) |
| Corner Relief | Checkbox | On | Applies the rule's corner relief where two or more bend lines meet | A[R31] (FoldFeatureInput.isUseCornerRelief) |
| Bend Radius | Override checkbox + value | Rule | | G (the API shows no radius; it follows the rule, F[F5] "the Bend tool will automatically apply the information from the sheet metal rule") |

**Behaviour notes.**
- With **Center**, the bend extends across the whole body even where the drawn line is shorter;
  this can cause self-intersections (F[F3]). The bend is applied across the full face the line
  crosses (G).
- The sketch line positions are flat-state positions. To hit a finished outside dimension the
  user must place the line by subtracting the bend deduction (F[F3]).
- **Timeline:** "Bend<n>" (G). The sketch is consumed by the feature (G).

**Errors.**
- Sketch lines not parallel to (coplanar with) the stationary face are refused (A[R11]).
- A line that does not cross the face fully: G, refused or extended (F[F3]).
- A curved bend line is refused (G).

### 2.4 Hem (CREATE > Hem; API Sep 2025)

**Purpose.** Folds an edge back on itself in one of six standard hem shapes (A[R13] A[R14]
A[R30]).

**Selection.** Edges of a sheet metal body (the edge where a top or bottom face meets a side
face). Ctrl-click or Cmd-click picks several (A[R13]).

| Input | Type / choices | Default | Applies to | What it does | Src |
|---|---|---|---|---|---|
| Edges | Edge selection (multi) | – | all | Where to hem | A[R13] |
| Type | **Flat / Open / Rolled / Teardrop / Rope / Double** | G: Flat | – | See below | A[R13], A[R30] (enum: Undefined=0, Flat=1, Open=2, Rolled=3, Teardrop=4, Rope=5, Double=6) |
| Length | Length | G: 4×T | Flat, Open, Teardrop, Rope, Double | "Distance to extrude the hem from the selected edge": the length of the return leg | A[R14], A[R30] |
| Gap | Length | G: 0.5×T (Open) | Open, Teardrop, Rope, Double | The space between the sheet layers after folding | A[R14] |
| Angle | Angle | G: 270° | Rolled | How far the edge rolls; larger means a more pronounced roll | A[R14], A[R30] (setRolledHem(edge, radius, angle...)) |
| Radius | Length | G: 2×T | Rolled, Teardrop, Rope | The fold curvature; larger is smoother and more open | A[R14] |
| Setback | Length | G: 0 | Double | The distance from the edge to the inner side of the first fold (between the connecting edge and the start of the double fold) | A[R14], A[R30] (setDoubleHem(edge, gap, length, setback, ...)) |
| Bend Position | Inside / Outside / Adjacent / Tangent | G: Inside | all | Where the hem bend sits relative to the edge (same enum as flanges) | A[R14], A[R29] ("used for creating flanges and hems") |
| Flip | Toggle | Off | all | Hems to the other side (up or down) | A[R14], A[R30] (isFlipped) |
| Miter Corners | Checkbox | G: On | all | At a corner shared by two hemmed edges: gap (mitered) or overlapping material | A[R14] |
| Override Rules | Checkbox, plus bend radius and bend relief overrides | Off | all | Overrides rule values for this operation only; the rule itself is unchanged | A[R13], A[R14], A[R30] ("bend radius and bend relief overrides") |

**Type geometry** (A[R30] enum descriptions; A[R13]):
- **Flat:** an open hem with the gap closed. The edge lies flat against the main sheet (a 180°
  fold, gap 0; inner radius about 0 or the minimum).
- **Open:** a simple 180° bend that leaves a gap between the hem and the sheet. Good for thick
  material, because it reduces cracking (A[R13]).
- **Rolled:** the edge rolls over into a tube-like profile of the given Radius, through the
  given Angle.
- **Teardrop:** the edge is bent around a diameter, giving a teardrop section. Its parameters
  are Radius, Length and Gap.
- **Rope:** like Rolled, plus an extra straight Length after the roll, parallel to the main
  sheet. Its parameters are Length, Gap and Radius.
- **Double:** the edge is bent over twice, doubling back on itself. Its parameters are Gap,
  Length and Setback. "Double lets you reverse the fold direction" (A[R13]).

**API signatures**, which define the parameter set for each type (A[R30]):
- `setFlatHem(edge, length, isFlipped, bendPositionType)`
- `setOpenHem(edge, length, gap, isFlipped, bendPositionType)`
- `setRolledHem(edge, radius, angle, isFlipped, bendPositionType)`
- `setTeardropHem(edge, radius, length, gap, isFlipped, bendPositionType)`
- `setRopeHem(edge, length, gap, radius, isFlipped, bendPositionType)`
- `setDoubleHem(edge, gap, length, setback, isFlipped, bendPositionType)`

An existing hem can be redefined as another type (`redefineAsOpenHem` and so on).

**Browser and timeline.** "Hem<n>" (G).

**Errors.** Non-linear edges are refused (G). A hem that collides with other geometry fails (G).

### 2.5 Join by Bend (new Sep 2026)

**Purpose.** Creates a bend, with the connecting material, between two compatible sheet metal
bodies, using the active rule. This merges separate plates into one body (A[R42]: "Fusion can
now create a bend between compatible sheet metal bodies... automatically uses active sheet metal
rule settings").

**Selection.** Two edges: one open edge on each body (A[R40] sample: "one on the joined sheet
metal body and one on the unconnected flange").

| Input | Type / choices | Default | What it does | Src |
|---|---|---|---|---|
| First Edge | Edge of body A | – | Where body A gets the bend | A[R40] |
| Second Edge | Edge of body B | – | Where body B meets the bend | A[R40] |
| Use rule bend radius | Checkbox | **On** | Off enables Bend Radius | A[R40] (isUseSheetMetalRuleBendRadius default true) |
| Bend Radius | Length | Rule radius | Inner radius of the joining bend | A[R40] |

**Geometry (G).**
- The two plates must have the same thickness ("compatible").
- Each plate is extended or trimmed so that a bend of radius R joins them tangentially.
- The result is one body.

**Errors.** Different thickness, or no possible tangent bend (for example parallel coplanar
plates), is refused (G).

### 2.6 Unfold (MODIFY > Unfold)

**Purpose.**
- Flattens some or all bends **in the model timeline**, so that features crossing a bend (holes,
  slots) can be cut flat. Refold then bends the part back (A[R12] A[R46] A[R48]).
- This is a temporary, in-timeline state and **not** the Flat Pattern; the two are not
  interchangeable (A[R12]).

| Input | Type / choices | Default | What it does | Src |
|---|---|---|---|---|
| Stationary Entity | A planar face of the body | – | The face that stays fixed while the bends unfold against it | A[R48], A[R32] (stationary face set in createInput) |
| Bends | Bend faces (inner cylinder, outer cylinder or both) | – | The bends to unfold | A[R32] (bendFaces) |
| Unfold All Bends | Checkbox | **Off** | Unfolds every bend and ignores the Bends selection | A[R32] (isUnfoldAllBends default false), A[R48] ("You can unfold selected bodies or all of them") |

**Behaviour.**
- The body becomes flat, by bend allowance (§4).
- Features added after it act on the flat body until a **Refold** (A[R12]).
- Relief geometry stays aligned, so the refold returns the same folded state (A[R12]).
- The Unfold and its Refold are created as a pair, and the timeline groups everything between
  them (A[R46]: "Everything between the unfold and refold will be grouped in the timeline";
  A[R32] UnfoldFeature.refoldFeature, May 2026).
- **Timeline:** "Unfold<n>" (A[R12] "a feature is created in the timeline").

**Errors.**
- A stationary entity that cannot be picked: Press Pull or other non-sheet-metal edits can break
  the body (F[F17]).
- Closed loops cannot be unfolded until they are ripped (A[R47]).

### 2.7 Refold (MODIFY > Refold)

**Purpose.** Bends the unfolded bends back. It is available after an Unfold (A[R50] A[R12]).

| Input | Type / choices | Default | What it does | Src |
|---|---|---|---|---|
| Stationary Entity | Face | The Unfold's stationary face | The fixed face | G |
| Bends | Unfolded bends | All bends unfolded by the paired Unfold | Which bends to fold back | G(Inv) ("refold all or some of the unfolded bends") |
| Refold All Bends | Checkbox | On | | G |

**Timeline.** "Refold<n>" closes the Unfold group (A[R46]). Features after it apply to the folded
model (A[R12]).

**Errors.** F[F20] reports crashes on complex bodies (logged as a defect).

### 2.8 Rip (MODIFY > Rip; API Sep 2023)

**Purpose.** Opens a gap in a closed or overlapping shape, for example a box made from a rolled
tube or a closed contour, so it can unfold (A[R47]).

| Input | Type / choices | Default | What it does | Src |
|---|---|---|---|---|
| Type | **Face / Along Edge / Between Points** | G: Along Edge | Face: removes the whole selected face (a bend face or a corner face) to separate the flanges. Along Edge: cuts a gap along a selected edge where two faces meet. Between Points: cuts a straight gap between two points on the same face | A[R33] (RipFeatureDefinitionTypes: Undefined=0, FaceRip=1, AlongEdge=2, BetweenPoints=3), G(Inv) "Face Extents removes the entire face" |
| Face | Face (Face type) | – | | A[R33] (setByFace) |
| Edge | Edge (Along Edge) | – | | A[R33] (setAlongEdge(edge, gapDistance)) |
| Point 1, Point 2 | A vertex, or an edge plus an offset along it from the edge start; point 2 must be on the same face as point 1 | – | The ends of the rip line | A[R33] (setBetweenPoints(p1, p2, gap, offsets)) |
| Offset 1, Offset 2 | Length along the edge | 0 | Used when a point is given as an edge | A[R33] |
| Gap Distance | Length | G: the rule's Miter/Rip/Seam Gap | The width of the gap cut | A[R33] (gapDistance model parameter), A[R6] (the rule field name includes "Rip") |

**Geometry (G).** The gap is a slot of width = gap, through the thickness, centred on the
line or edge. Along Edge removes material symmetrically about the edge.

**Timeline.** "Rip<n>" (G).

**Errors.** For Between Points, point 2 not on the same face as point 1 is refused (A[R33]).

### 2.9 Corner Closure (MODIFY; API Jan 2026, overlap control Sep 2026)

**Purpose.** Closes or adjusts the corner between two flanges that meet: gap, overlap and
relief (A[R39] A[R42]).

**Selection.** A **dominant edge**, then a **submissive edge**. Their geometry decides whether
this is a **2-bend** or **3-bend** corner closure. Picking another edge can change the type
(A[R39]).

| Input | Type / choices | Default | What it does | Src |
|---|---|---|---|---|
| Dominant Edge / Submissive Edge | Edges | – | The two flange edges at the corner | A[R39] |
| Alignment | **Symmetric Gap / Overlap** | G: Symmetric Gap | Symmetric gap: both flanges stop with a gap centred on the corner. Overlap: one flange runs over the other's edge | A[R39] (alignment type, setToOverlapAlignmentType) |
| Gap | Length | G: the rule's Miter/Rip/Seam Gap | The corner gap | A[R39] (gap; "miterGap... fallback to rule") |
| Overlap | Unitless 0 to 1 | G: 1 | Overlap only: 0 = no overlap, 1 = full overlap of the material thickness | A[R39] |
| Flip overlap | Toggle | Off | Overlap only: dominant over submissive, or the reverse | A[R39] (isOverlapFlipped) |
| Extend aligned | Checkbox | **On** | On: the closure extends in line with the adjacent flange edges. Off: perpendicular to them | A[R39] (isExtendAligned default true) |
| Bend Transition | **Smooth / Straight Line / Trim To Bend** | Trim To Bend in the closure definitions (one input page says Smooth; conflicting) | How the bend zones blend at the corner | A[R39] (CornerBendTransitionTypes: Smooth=0, StraightLine=1, TrimToBend=2) |
| Use rule defaults | Checkbox | **On** for 2-bend; the 3-bend input page says off | Takes the relief shape, size and placement from the rule | A[R39] |
| Relief Shape (2-bend) | Round / Square / Tear / Trim To Bend / Linear Weld / Arc Weld / Laser Weld | Round | | A[R22], A[R39] (CornerTwoBendReliefShapeTypes) |
| Relief Size | Length | Rule | | A[R39] |
| Relief Placement | **Tangent / Intersection / Vertex** | Tangent | | A[R39] (CornerTwoBendReliefPlacementTypes: Tangent=0, Intersection=1, Vertex=2, default Tangent) |
| Relief Shape (3-bend) | No Replacement / Intersection / Full Round / Round With Radius | Rule | | A[R23] |

**Timeline.** "Corner Closure<n>" (G).

### 2.10 Sheet Metal Fillet and Chamfer (MODIFY; Sep 2026)

**Purpose.** Round or chamfer the **corners of plates** (the edges in the thickness direction)
without the risk of picking top or bottom edges (A[R42]).

**Selection.** Only **thickness-direction edges**: edges perpendicular to the front and back
faces of one sheet metal body. Other edges cannot be picked (A[R41]).

| Input | Type / choices | Default | What it does | Src |
|---|---|---|---|---|
| Edge sets | Edges + Radius per set (fillet). Multiple sets allowed; at least one set must remain | – | Constant-radius corner rounds | A[R41] |
| Chamfer distance (chamfer) | Length (G: equal distance) | – | Corner chamfers | A[R42], G |

**Flat pattern.** The rounds and chamfers appear as arcs and lines in the flat outline (G).

**Errors.** Any non-thickness edge is refused, and the feature returns nothing (A[R41]).

### 2.11 Convert to Sheet Metal (MODIFY)

**Purpose.** Turns a solid of uniform thickness (made with Shell, Extrude and so on, or imported
STEP) into sheet metal, so it can be flattened (A[R8] A[R9] A[R49]).

| Input | Type / choices | Default | What it does | Src |
|---|---|---|---|---|
| Source (face) | One planar face on a solid body; choose a **wide, flat** area | – | The thickness is measured at the picked point | A[R8], A[R9] |
| Thickness | Read-only display | Detected | Shown, and saved into the rule; **cannot be edited** | A[R8] |
| Rule | **Template Rule** (creates a new rule from the detected thickness), or a rule from In This Design or the Library | Template Rule (G) | A chosen rule is **duplicated** and its thickness set to the detected value | A[R8] |
| Show rules with matching thickness only | Checkbox | G: On | Filters the rule list by the detected thickness | A[R8] |

**Behaviour.**
- A Standard parent component becomes a **Sheet Metal component**. This cannot be reversed
  (A[R34] A[R9]).
- If the component is already sheet metal, the chosen rule is ignored and the active rule is
  used (A[R34]).
- Cylindrical faces of constant thickness become bends. Planar pairs become flanges (G).

**Errors.**
- Non-uniform thickness: rounded or organic shapes will not convert (F[F5]).
- If bend radii are not consistent, the flat pattern may fail later (A[R47]).

### 2.12 Create Flat Pattern, and the FLAT PATTERN environment

**Create Flat Pattern** (CREATE).

| Input | Type / choices | Default | What it does | Src |
|---|---|---|---|---|
| Stationary Face | A planar face on the **top or bottom** of the part (not an edge face) | – | This face is laid on the flat pattern's XY plane, and the rest is flattened relative to it | A[R35] (createFlatPattern), A[R49] |

**Rules and behaviour.**
- **One flat pattern per component.** Creating a second one fails; the API returns null
  (A[R35]).
- **Imported parts.** They must be converted to sheet metal first (A[R49]).
- **Browser (G).**
  - A **Flat Pattern** node appears under the sheet metal component.
  - Double-clicking it, or right-click > Activate / Edit, enters the flat state.
  - Under the node, Bend Lines and Bend Extents can be shown or hidden (F[F9]).
- **Timeline.** The flat pattern has its own compute chain. The error text
  "FlatPatternAlign1(FlatPattern1) Compute Failed" (F[F10]) shows a "FlatPattern1" item with a
  child "FlatPatternAlign1".
- **What can be done in the flat state.**
  - The flat pattern supports most component functionality (sketches, construction geometry)
    but **no sheet metal features, occurrences or new components** (A[R35]).
  - Edits made there do not flow back into the folded model (G).
- **Display.**
  - **Bend lines** are centre-line-style wire lines, one per bend centre line. **Bend extent
    lines** are the two tangent lines of each bend zone (A[R36] A[R37]).
  - Bend lines show only in "Shaded with visible edges" (F[F9]).
  - Each bend has an **up/down** direction relative to the bend line's natural direction, and
    an angle (A[R35] getBendInfo: isBendUp, bendAngle in radians).
  - Up and down bends get different colours in drawings; Fusion help's example shows up bends
    in red (A, flat-pattern view help as reported in the search excerpt).
- **Finish Flat Pattern.** The green check returns to the folded model (F[F13]).
- **Errors.**
  - The flat body overlaps itself, the body is not uniform thickness, or there is a closed loop
    that needs a Rip (G, A[R47]).
  - Compute failure: "FlatPatternAlign<n> Compute Failed" (F[F10]).

**Export Flat Pattern as DXF** (FLAT PATTERN tab > Export DXF; A[R19]).

| Option | Type | Default | What it does | Src |
|---|---|---|---|---|
| File name / location | Path | – | | A[R36] |
| Export bend center lines | Checkbox | **On** | Writes the bend centre lines | A[R36] (isCenterLinesExported) |
| Export bend extent lines | Checkbox | **On** | Writes the bend extent (tangent) lines | A[R36] (isExtentLinesExported) |
| Convert Splines to Polylines | Checkbox | **Off** | Replaces splines with polylines. Recommended for laser and waterjet shops | A[R36], F[F4] |
| Tolerance | Length | **0.01 cm (0.1 mm)** | The maximum deviation between polyline and spline; used only when conversion is on | A[R36], F[F4] |

**DXF content and layers.**
- Outer profiles, interior profiles, bend centre lines, bend extent lines and text each go on
  their **own layer** (F[F4]).
- Bend lines use a different line type, so cutters can ignore them (F[F9]).
- The file is 1:1 in the document units (G).
- There were DXF export improvements in March/April 2025 (A[R51]).

**Other outputs.**
- **Export flat pattern as STEP** (A[R36] STEPFlatPatternExportOptions, preview).
- **Drawing of a flat pattern:**
  - Use Drawing > From Design and choose the flat pattern as the view source.
  - The flat pattern view has a **Bend Extents** on/off checkbox, on by default (F[F9];
    A[R37] isShowBendExtents default true).
  - **Bend Table:** Tables > Bend Table, then pick a flat pattern view. The table is filled with
    the bends, and bend identifiers are added automatically to the view as labels (A[R17]).
    Automatic table creation is also available (A[R17]).
  - **Bend notes** (direction + angle + radius) are on the drawing (A help page
    "Create and modify bend notes", Fusion-Drawing DWG-CREATE-BEND-NOTE).

### 2.13 Solid commands inside a sheet metal component

**Allowed.** Create Sketch, Extrude, Hole, patterns, Mirror, Press Pull, Split, Combine,
construction geometry and so on can be used in a sheet metal component (G; A[R48] lists
New Component and sketch beside Flange).

**Expected behaviour** (G, consistent with A[R12] and F[F17]):

- **Extrude cut through the sheet**, perpendicular to the top or bottom face, with
  Through All or Distance ≥ T:
  - The result stays valid sheet metal and the cut shows in the flat pattern.
  - A cut through a **bend** should be made in an Unfold-Refold pair, so that it is
    perpendicular to the flat sheet (A[R12]: "add the necessary features that span across
    bends, like holes or slots... then click Refold").
- **Extrude join / Press Pull that changes thickness**: the body stops being valid sheet metal.
  Unfold, Flat Pattern and later sheet metal features fail. F[F17] shows a Press Pull blocking
  Unfold until suppressed.
  - Recommended SciForge behaviour: mark the body "not valid sheet metal" with a warning
    triangle on the timeline item, and have Flat Pattern explain why.
- **Hole** on a top or bottom face is fine (it acts like a cut).
- **Rectangular / Circular / Pattern on Path / Mirror**:
  - Patterning sheet metal **features** (flanges, cuts) on the same body works if the result is
    valid.
  - Patterning **bodies** gives independent sheet metal bodies that share the rule.
- **Physical Material** is separate from the rule (the rule names are just names). Use
  Physical Material to set the mass properties (G).
- **Thicken**: not offered on the SHEET METAL tab (G). Thickness always comes from the rule.

### 2.14 New Component (Sheet Metal)

- **Dialog.** The New Component dialog Type is **Standard / Sheet Metal** (A[R48]; SciForge
  parity/components.md item 4).
- **Rules in the component.** A Sheet Metal component carries an active rule, the library
  default unless changed (G). Sheet metal features can only be created in a Sheet Metal
  component (G).
- **Converting a component.** Converting is one way: a sheet metal component cannot be turned
  back into a Standard one (A[R9]).
- **Browser (G).** The component icon has a sheet-metal overlay. Bodies are listed normally.
  The Flat Pattern node is added after Create Flat Pattern.

---

## 3. Rules and data model

### 3.1 Rule fields

Sources: A[R6] SM-RULES-REF, A[R20] SheetMetalRule API (Nov 2022), A[R1].

| Group | Field | Type | Meaning | Src |
|---|---|---|---|---|
| – | Name | Text, unique within its list | e.g. "Steel (mm)", "Steel Two (mm)" | A[R26] |
| – | Units | mm or in, fixed at creation | Display units of all values | A[R20] |
| – | Thickness | Length or expression | Material thickness | A[R6], A[R20] |
| – | **Miter/Rip/Seam Gap** | Length or expression | "Space between flange gaps". Used for auto-miters, rips, seams and the arc-weld relief gap | A[R6], A[R1], A[R25] (SheetMetalRule.gap) |
| Bend | **Bend Radius** | Length or expression | The **inner** radius of bends: the distance from the inner sheet surface to the bend centre | A[R6], A[R20] |
| Bend (Unfold) | **K Factor** | Number, 0 to 1 | The neutral-axis offset from the inner bend surface ÷ thickness | A[R6], A[R25] |
| Bend Relief | **Relief Shape** | **Straight / Tear / Round** | Straight: a square-ended notch of the given width, depth and remnant. Round: a notch with a round end. Tear: no relief cut; the material tears, leaving a remnant | A[R6], A[R1], A[R21] (Straight=0, Tear=1, Round=2) |
| Bend Relief | Relief Width | Length or expression | The width of the relief slot | A[R6] |
| Bend Relief | Relief Depth | Length or expression | How far the relief goes past the bend zone | A[R6] |
| Bend Relief | Relief Remnant | Length or expression | The remnant used in the flat pattern. G(Inv): the minimum material strip; a sliver thinner than this between relief and edge is removed | A[R20], G(Inv) |
| Corner (2 bends) | **Relief Shape** | **Round / Square / Tear / Trim To Bend / Linear Weld / Arc Weld / Laser Weld** | The relief where two bends intersect | A[R22] (Round=0, Square=1, Tear=2, TrimToBend=3, LinearWeld=4, ArcWeld=5, LaserWeld=6), A[R1] |
| Corner (2 bends) | Relief Placement | Intersection / Tangent / (Vertex) | **Round** allows Intersection or Tangent. **Square** allows Intersection only. Other shapes have no placement (NoTwoBendReliefPlacement). Choosing Round or Square resets placement to Intersection | A[R24] (rule enum TwoBendReliefPlacements: None=0, Intersection=1, Tangent=2, Vertex=3) |
| Corner (2 bends) | Relief Size | Length or expression | Measured on the **unfolded** body. Round: the cut-out radius. Square: the cut-out width | A[R1], A[R24] |
| Corner (3 bends) | **Relief Shape** | **No Replacement / Intersection / Full Round / Round With Radius** | The relief where three bends meet | A[R23] (NoReplacement=0, Intersection=1, FullRound=2, RoundWithRadius=3) |
| Corner (3 bends) | Relief Radius | Length or expression | Used only for Round With Radius | A[R20] (threeBendReliefRadius) |

**Value objects.**
- Each length field is a `SheetMetalRuleValue`: an expression string, or a number in the rule's
  units (A[R26]).
- Expressions may reference **`Thickness`** (A[R45]).

**Not found in Fusion.** Bend tables, bend-deduction or bend-allowance tables, and per-angle
K-factor are not offered; users have requested them (F[F1] F[F16] and the feature-request
thread in F[F1]). Fusion has **K-factor only**.

### 3.2 Rule library values

| Material | Units | Thickness | Bend Radius | K Factor | Src |
|---|---|---|---|---|---|
| Steel (Default) | mm | G: 1.0 mm (F[F7]: rules defaulted to 1 mm) | `Thickness * 1` (F[F2]: "default rule Radius = Thickness") | **0.44** (F[F1]: 0.44 "for all listed materials from aluminum to stainless steel") | F[F6] (name "Steel (mm) (Default)"), A[R26] (library index 0 is the default steel rule) |
| Steel | in | G: 0.06 in (F[F16] a user's 0.06" carbon steel) | `Thickness * 1` | 0.44 | G |
| Stainless Steel | mm / in | G | `Thickness * 1` | 0.44 | F[F8] (library includes stainless) |
| Aluminum | mm / in | G | `Thickness * 1` | 0.44 | F[F8] |
| Copper | mm / in | Unconfirmed: F thread "Copper sheet metal rules" asks which rule to use for copper, which suggests there is no copper rule | | 0.44 if present | F |

**Recommended defaults for the other fields** (G, all as thickness expressions in the spirit of
A[R45]):

| Field | Value |
|---|---|
| Miter/Rip/Seam Gap | `Thickness * 1` (some CAD tools use 0.5×T) |
| Relief Shape | Round |
| Relief Width | `Thickness * 1` |
| Relief Depth | `Thickness * 0.5` (A[R45] uses "Thickness / 2" as its relief-depth example) |
| Relief Remnant | `Thickness * 0.5` |
| 2-bend Relief Shape | Round |
| 2-bend Relief Placement | Intersection |
| 2-bend Relief Size | `Thickness * 2` |
| 3-bend Relief Shape | Round With Radius |
| 3-bend Relief Radius | `Thickness * 2` |

**SciForge suggestion (G).** Ship eight library rules: Steel, Stainless Steel, Aluminum and
Copper, each in mm and in, with thicknesses 1.0 / 1.0 / 1.5 / 1.0 mm and
0.060 / 0.048 / 0.063 / 0.040 in. Mark them clearly as SciForge's own starting values. K = 0.44
matches Fusion, though users note it is inaccurate for steel; about 0.33 is common (F[F1]).

### 3.3 Sheet metal data per object (G, for implementation)

- **Component:**
  - Kind: Standard or SheetMetal.
  - ActiveRule.
  - Rules in this design: a list of rule copies.
  - FlatPattern: 0 or 1.
- **Body:**
  - isSheetMetal (A, BRepBody.isSheetMetal).
  - The rule it was built with.
  - Its thickness (locked when made by Convert).
- **Feature:** flange, bend, hem, rip, unfold, refold, corner closure, join by bend, SM fillet,
  SM chamfer, convert, flat pattern.
  - Each stores its own override values.
  - A value without an override reads through to the rule live, so rule edits propagate.

---

## 4. Maths and geometry rules

### 4.1 Symbols

| Symbol | Meaning |
|---|---|
| T | Thickness |
| R | Inner bend radius (rule Bend Radius) |
| K | K-factor |
| θ | Bend angle in radians: the deflection angle, 90° for a right-angle flange; Fusion's flange Angle |

### 4.2 Bend allowance and deduction

The **neutral-axis radius** is `Rn = R + K·T` (A[R6] defines K as neutral offset ÷ T).

| Quantity | Formula | Meaning |
|---|---|---|
| **Bend Allowance** | `BA = θ · (R + K·T)` | The arc length of the neutral axis |
| **Outside Setback** | `OSSB = tan(θ/2) · (R + T)` | For θ ≤ 180°; from the outer virtual sharp to the bend tangent line |
| Inside setback | `ISSB = tan(θ/2) · R` | |
| **Bend Deduction** | `BD = 2·OSSB − BA` | |

**Flat length** of a part with n bends:
- `L_flat = Σ (straight flat segment lengths) + Σ BA_i`, measured between tangent lines.
- Equivalently, `L_flat = Σ (outer mold-line lengths to virtual sharps) − Σ BD_i`.

**Worked example** (for a unit test): T = 1, R = 1, K = 0.44, θ = 90°.

| Quantity | Value |
|---|---|
| BA | (π/2)·1.44 = 2.26195 |
| OSSB | 2 |
| BD | 1.73805 |

An L bracket of 50 × 50 outer dimensions flattens to 100 − 1.73805 = **98.26195**.

**Flat-pattern geometry.**
- The bend zone is a strip of width BA between the two **bend extent lines**.
- The **bend centre line** sits at BA/2 (A[R36] centre and extent lines).

**K-factor conventions.**
- Fusion uses the ANSI-style K. In normal practice it ranges 0.3 to 0.5 (F[F1]).
- Some DIN tables use a doubled k. A SciForge dialog tooltip should say "K = neutral offset ÷
  thickness".

### 4.3 Height datum (edge flange)

Take a base plate in the XY plane, thickness T (z = 0 to T), inner side up, and the flange bent
up from the edge.

| Datum | Measured from | Flange top at (90°) |
|---|---|---|
| Outer Faces | The intersection (virtual sharp) of the base **outer** face (z = 0) with the flange outer face | z = H |
| Inner Faces | The intersection of the **inner** faces (z = T) | z = T + H |
| Tangent To Bend | The bend's tangent line on the flange (z = T + R), parallel to the flange | z = T + R + H |

- For θ ≠ 90°, the height is measured along the flange direction (parallel to the flange faces)
  from the datum point (G; Inventor also offers "orthogonal" variants, which Fusion does not
  list, A[R2]).
- Straight flange length beyond the bend:
  - Inner datum: H − ISSB.
  - Outer datum: H − OSSB.
  - Tangent datum: H.

### 4.4 Bend position (edge flange and hem)

Same setup: the selected edge at x = 0, the base occupying x ≤ 0, θ = 90°, flange going up.

| Position | Rule | Base trimmed by | Flange inner face | Flange outer face | Overall width change |
|---|---|---|---|---|---|
| **Inside** (API Inside=2) | The outer faces' virtual sharp stays at the edge, so the outermost faces stay within the original boundary | R + T | x = −T | **x = 0** | 0 (outer size kept) |
| **Outside** (Outside=1) | The inner faces' virtual sharp is at the edge | R | **x = 0** | x = T | +T |
| **Adjacent** (StartEdge=3) | The bend starts at the selected edge; the base is not trimmed | 0 | x = R | x = R + T | +R+T |
| **Tangent** (TangentToSide=4) | The outer bend surface is tangent to the plane of the edge's side face; this applies to θ ≥ 90° | – | – | – | – |

- **Tangent vs Inside.** At θ = 90° Tangent coincides with Inside. At θ > 90° Tangent keeps the
  bend bulge inside x ≤ 0, while Inside lets the bulge pass the edge. The A[R29] API text says
  "the bend tangent to the reference plane when the angle is 90 degrees or more".
- Sources: A[R2] (definitions) and A[R29] (Inside and Outside "place the reference plane through
  the selected edge with material on the respective side"; StartEdge and Tangent "use the side
  face as the reference plane"). The coordinates are G, derived from those definitions.
- Bend centre for Inside: (−T − R, T + R). For Outside: (−R, T + R). For Adjacent: (0, T + R).

### 4.5 Bend relief geometry (G, consistent with A[R6] and A[R1])

**When it applies.** A relief is needed at each **end** of a bend zone whose end is not on a free
edge of the parent face, i.e. when the flange is narrower than the parent edge or is inset.

**The cut.** A slot is cut in the parent flange starting at the bend end:

- **Width:** Relief Width, measured parallel to the bend line, on the side away from the
  flange.
- **Length:** across the full bend zone, plus Relief Depth past the bend tangent line into the
  parent.

**Shapes.**
- **Straight:** a rectangle.
- **Round:** the slot end is a semicircle of diameter = width.
- **Tear:** no material is removed; the side faces are split along the bend end (a zero-width
  rip).
- **Remnant:** if the material left between the relief and the parent's free edge is narrower
  than Relief Remnant, remove that sliver (G(Inv)).

### 4.6 Corner relief geometry (2-bend), measured in the flat state

| Shape | Geometry | Src |
|---|---|---|
| Round | A circle of radius = Size | A[R1] |
| Square | A square of side = Size | A[R1] |
| Tear | No cut | |
| Trim To Bend | The corner is trimmed along the bend extent lines of both bends | |
| Linear Weld | Straight edges that close to the Miter/Rip/Seam Gap | G(Inv) |
| Arc Weld | Two splines separated by the gap | A[R1] |
| Laser Weld | A tangent arc sized to the gap | G(Inv) |

**Placement.**
- **Intersection:** centred at the intersection of the two bend centre lines (A[R1]: "where the
  flanges meet the base flange").
- **Tangent:** Round only; the circle is tangent to the flange edges (bend extent lines) (A[R1]).
- **Vertex:** centred at the inner corner vertex (G).

**3-bend corners.**
- No Replacement: leave as built.
- Intersection: a cut at the intersection point.
- Full Round: a round tangent to all bend extents.
- Round With Radius: a circle of the given radius at the corner (A[R23], G for the geometry).

### 4.7 Miter (adjacent edge flanges) (G(Inv) and A[R6])

- The two flanges are cut on the plane that bisects the corner angle.
- Each is pulled back by Gap/2 from the bisector, leaving a total gap = Miter/Rip/Seam Gap.
- The bends meet in a 2-bend corner that gets the corner relief.
- At angles > 90° the auto-miter adds material between the flanges so the corner closes up to
  the gap (G(Inv)).

### 4.8 Flatten algorithm outline (G, for the builder)

1. **Classify faces.** Planar faces come in pairs offset by T (the **flanges**). Cylindrical
   faces come in pairs with radii r and r + T, sharing an axis (the **bends**). Side faces have
   width T.
2. **Build a graph.** Flanges are nodes and bends are edges. Start from the stationary face's
   flange.
3. **Unroll by BFS.** Each bend unrolls into a strip of width BA = θ·(r + K·T) on the neutral
   plane. The child flange is rotated by −θ about the bend axis and translated by
   BA − (geometric arc).
4. **Project and collect.**
   - Project the stationary face to XY.
   - Collect the outer loop, the inner loops, the bend centre lines (mid-strip) and the bend
     extent lines (the strip borders).
5. **Check validity.**
   - Graph cycles (closed loops) must be ripped. Report "closed loop: add a Rip".
   - Overlap in the flat state: report.
   - Non-uniform thickness: report.

---

## 5. Open questions (not settled)

1. **Exact menu order** of the CREATE and MODIFY drop-downs.
   - Unconfirmed: whether Create Flat Pattern has its own toolbar icon, where Join by Bend,
     Corner Closure and the SM Fillet/Chamfer sit, and whether Pattern on Path, Derive and
     Thread are repeated.
   - §1 is a G reconstruction.
2. **Built-in rule library.** The exact rule names, materials and units; per-material
   thickness, gap and relief defaults; whether Copper or Brass exist. Only K = 0.44 (F) and
   Radius = Thickness (F) are confirmed.
3. **Edge flange defaults.** Default Height, Height Datum, Bend Position and the allowed Angle
   range. Whether 0° is allowed, and whether angles beyond 180° are allowed.
4. **Rule assignment.** Is the rule per component (active rule) or per body, and can two bodies
   in one component use different rules? What does "set active" look like in the dialog?
5. **Hem defaults.** The default Type and the default Length, Gap, Radius, Angle and Setback.
   - Whether Teardrop's "length" parameter is really an angle: the API text was contradictory.
   - Whether Flat hem has an inner radius of 0 or the rule radius.
6. **Rip UI.** Labels, the default type, whether the gap defaults to the rule gap, and exactly
   what "Face" rip removes.
7. **Refold dialog.** Its inputs, whether it has its own stationary face, and whether
   Unfold/Refold show a contextual state or ribbon change beyond Refold becoming available.
8. **Corner Closure UI.**
   - Its menu name and dialog labels.
   - The default bend transition: the API pages conflict (Smooth vs Trim To Bend).
   - The default alignment.
9. **Join by Bend.** Its menu location and whether it has flip or position options. The API
   shows only two edges and a radius.
10. **Flat Pattern UI.**
    - The contents of the FLAT PATTERN contextual tab beyond Export DXF and Finish.
    - The browser node structure and icons, and the timeline representation.
    - How up and down bend lines are styled in the canvas (as opposed to drawings).
    - Whether DXF export offers layer naming or a "bend lines on separate layer" toggle in the
      UI.
11. **Browser and timeline icons and names** for every feature. The names
    (Flange1, Bend1, Hem1, Rip1, Unfold1, Refold1) are G apart from FlatPattern1 and
    FlatPatternAlign1 (F).
12. **Non-sheet-metal features on sheet metal bodies.** Is there an explicit warning or refusal
    when a join or press-pull breaks uniform thickness, and does Fusion's Extrude in a sheet
    metal component offer a "Thickness"-from-rule extent? Unconfirmed.
13. **Contour flange.**
    - Exact width and direction options (one side, symmetric, two sides).
    - How tangent arcs smaller than the rule radius are treated.
    - Whether contour flanges can start from an existing edge in every case.
14. **Lofted flange.** Whether "Face Number" facet control is still offered (it is in the 2022
    blog but not in the excerpt of the current reference), and the default values.
15. **Physical Material.** Whether a rule (for example "Aluminum") assigns a physical material
    automatically.
16. **Sheet metal Chamfer.** Its parameters: equal distance only, or also two distances or
    distance + angle.

---

## References

**Autodesk help (Fusion Sheet Metal)**
- R1 Flange reference (overrides): https://help.autodesk.com/cloudhelp/ENU/Fusion-Sheet-Metal/files/SM-REF-FLANGE.htm
- R2 The Flange (types, width, datum, bend position, orientation): https://help.autodesk.com/cloudhelp/ENU/Fusion-Sheet-Metal/files/SM-REF-BASE-EDGE-CONTOUR-FLANGE.htm
- R3 Create base/edge/contour flange: https://help.autodesk.com/cloudhelp/ENU/Fusion-Sheet-Metal/files/SM-CREATE-BASE-EDGE-CONTOUR-FLANGE.htm
- R4 Create sheet metal flanges: https://help.autodesk.com/cloudhelp/ENU/Fusion-Sheet-Metal/files/SM-CREATE-FLANGE.htm
- R5 Flanges overview (sharp corners → bends): https://help.autodesk.com/cloudhelp/ENU/Fusion-Sheet-Metal/files/SM-FLANGES.htm
- R6 Sheet metal rules reference: https://help.autodesk.com/cloudhelp/ENU/Fusion-Sheet-Metal/files/SM-RULES-REF.htm
- R7 Create sheet metal rules: https://help.autodesk.com/cloudhelp/ENU/Fusion-Sheet-Metal/files/SM-CREATE-RULE.htm
- R8 Convert to Sheet Metal dialog: https://help.autodesk.com/cloudhelp/ENU/Fusion-Sheet-Metal/files/SM-REF-CONVERT.htm
- R9 Convert to sheet metal: https://help.autodesk.com/cloudhelp/ENU/Fusion-Sheet-Metal/files/SM-TO-CONVERT-TO-SM.htm
- R10 Sheet metal components: https://help.autodesk.com/cloudhelp/ENU/Fusion-Sheet-Metal/files/SM-COMPONENTS.htm
- R11 Bends in sheet metal: https://help.autodesk.com/cloudhelp/ENU/Fusion-Sheet-Metal/files/SM-BENDS-IN-SM.htm
- R12 Unfold in sheet metal: https://help.autodesk.com/cloudhelp/ENU/Fusion-Sheet-Metal/files/SM-UNFOLD-IN-SM.htm
- R13 Create hem: https://help.autodesk.com/cloudhelp/ENU/Fusion-Sheet-Metal/files/SM-CREATE-HEM-FLANGE.htm
- R14 Hem reference: https://help.autodesk.com/cloudhelp/ENU/Fusion-Sheet-Metal/files/SM-REF-HEM-FLANGE.htm
- R15 Lofted flange reference: https://help.autodesk.com/cloudhelp/ENU/Fusion-Sheet-Metal/files/SM-REF-LOFTED-FLANGE.htm
- R16 Create lofted flange: https://help.autodesk.com/cloudhelp/ENU/Fusion-Sheet-Metal/files/SM-CREATE-LOFTED-FLANGE.htm
- R17 Create a bend table (Drawing): https://help.autodesk.com/cloudhelp/ENU/Fusion-Drawing/files/DWG-CREATE-BEND-TABLE.htm
- R18 Help search "bend" (Bend command path, Stationary Side): https://help.autodesk.com/view/fusion360/ENU/?query=bend
- R19 Help search "dxf" (Export DXF → Export Flat Pattern As DXF dialog): https://help.autodesk.com/view/fusion360/ENU/?query=dxf

**Autodesk Fusion API reference** (base https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/)
- R20 SheetMetalRule.htm (+ _kFactor, _bendRadius, _reliefShape, _threeBendReliefRadius, _twoBendReliefShape, _twoBendReliefSize)
- R21 BendReliefShapes.htm
- R22 TwoBendReliefShapes.htm
- R23 ThreeBendReliefShapes.htm
- R24 SheetMetalRule_twoBendReliefPlacement.htm, TwoBendReliefPlacements.htm
- R25 SheetMetalRule_gap.htm, fusion_SheetMetalRule_kFactor.htm
- R26 "Sheet Metal Rules Sample_Sample.htm", fusion_SheetMetalRules_addByCopy.htm, fusion_SheetMetalRuleValue.htm
- R27 fusion_FlangeFeatures.htm, fusion_EdgeFlangeInput.htm, fusion_BaseFlangeInput.htm
- R28 fusion_FlangeOrientations.htm
- R29 BendPositionTypes.htm
- R30 HemFeatureDefinitionTypes.htm, HemFeatureInput.htm, HemFeatureInput_setDoubleHem.htm, HemFeatureDefinition.htm
- R31 FoldFeatureInput.htm, FoldBendLineDefinition.htm, FoldFeatures_createInput.htm, FoldBendLineDefinition_isBendReliefAllowed.htm
- R32 fusion_UnfoldFeatureInput.htm, UnfoldFeature_refoldFeature.htm, UnfoldSample_Sample.htm
- R33 fusion_RipFeatureInput.htm, RipFeatureDefinitionTypes.htm, RipFeatureInput_setBetweenPoints.htm, RipFeatureInput_setAlongEdge.htm
- R34 BRepBody_convertToSheetMetal.htm
- R35 fusion_FlatPattern.htm, Component_createFlatPattern.htm, FlatPattern_getBendInfo.htm
- R36 DXFFlatPatternExportOptions.htm, STEPFlatPatternExportOptions.htm
- R37 drawing_DrawingViewFlatPatternPreferences.htm, FlatPatternPreferences.htm
- R38 fusion_LoftedFlangeFeatureInput.htm, fusion_LoftedFlangeFormingTypes.htm, fusion_LoftedFlangeFeatures_add.htm
- R39 fusion_CornerClosureFeatureInput.htm, CornerClosureFeatureInput_overlap.htm, TwoBendCornerClosureInputDefinition.htm, CornerBendTransitionTypes.htm, CornerTwoBendReliefPlacementTypes.htm, CornerClosureInputDefinition_miterGap.htm
- R40 JoinByBendFeatureInput.htm, JoinByBendFeatureInput_isUseSheetMetalRuleBendRadius.htm, JoinByBendSample_Sample.htm
- R41 fusion_SheetMetalFilletFeatures.htm, fusion_SheetMetalFilletEdgeSet.htm

**Autodesk blog, Learn and support**
- R42 September 2026 update: https://www.autodesk.com/products/fusion-360/blog/fusion-september-2026-update-top-features/ (and .../september-2026-major-product-update-whats-new/)
- R43 July 2026 update: https://www.autodesk.com/products/fusion-360/blog/july-2026-major-product-update-whats-new/
- R44 July 2022 update (Lofted flange): https://www.autodesk.com/products/fusion-360/blog/july-2022-product-update-whats-new/
- R45 Sheet Metal Preview: Status Update (Thickness expressions): https://www.autodesk.com/products/fusion-360/blog/fusion-360-sheet-metal-status-update/
- R46 Sheet Metal Check-in (unfold mode, timeline grouping, starter rules): https://www.autodesk.com/products/fusion-360/blog/sheet-metal-check-in/
- R47 Learn Essential Sheet Metal Basics (July 2025): https://www.autodesk.com/products/fusion-360/blog/learn-sheet-metal-basics-autodesk-fusion/
- R48 Autodesk Learn tutorial: https://autodesk.com/learn/ondemand/tutorial/creating-a-sheet-metal-component
- R49 Support: flat pattern of imported part: https://autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/How-to-create-flat-pattern-in-Fusion-360-for-a-sheet-metal-part-imported-from-another-software.html
- R50 AU handout MFG225530 (Robert Savage): https://static.au-uw2-stg.autodesk.com/Class_Handout_MFG225530_Sheet_Metal_Like_a_Pro_with_Fusion_360_Robert_Savage.pdf
- R51 March 2025 update: https://autodesk.com/products/fusion-360/blog/march-2025-product-update-whats-new

**Forums and tutorials**
- F1 K-factor 0.44 universal: https://forums.autodesk.com/t5/fusion-design-validate-document/k-factors-incorrect-for-sheet-metal-standard-library/td-p/13359052
- F2 Radius = Thickness default; press-brake mismatch: https://forums.autodesk.com/t5/fusion-design-validate-document/sheet-metal-unfold-flat-pattern-isnt-the-same-irl-settings/m-p/8679495
- F3 Bend line position (Start/Center/End): https://forums.autodesk.com/t5/fusion-design-validate-document/sheet-metal-bend-line-position/m-p/12369635 ; https://forums.autodesk.com/t5/fusion-support-forum/sheet-metal-bend-issue-center-and-radius/m-p/12418988
- F4 SendCutSend DXF export (layers, polylines): https://sendcutsend.com/blog/4-ways-to-export-a-dxf-from-fusion-360/
- F5 SendCutSend rule / bend tool / convert guides: https://sendcutsend.com/faq/how-to-create-a-sheet-metal-rule-in-fusion-360/ ; https://sendcutsend.com/faq/how-to-use-the-bend-tool-in-fusion-360/ ; https://sendcutsend.com/faq/how-to-convert-a-sketch-to-sheet-metal-in-fusion-360/
- F6 Tutorial "Steel (mm) (Default)": https://myriverside.sd43.bc.ca/akang/?p=2151
- F7 Rule thickness lock / 1 mm: https://forums.autodesk.com/t5/fusion-support-forum/sheet-metal-rules-unable-to-change-thicknes/m-p/8389401
- F8 Library empty (steel, stainless, aluminium defaults): https://forums.autodesk.com/t5/fusion-support/sheet-metal-library-is-empty/td-p/7373894
- F9 Hiding bend lines / extents; bend lines need visible edges: https://forums.autodesk.com/t5/fusion-support-forum/hiding-bend-lines-in-flat-pattern/m-p/11560510 ; https://forums.autodesk.com/t5/fusion-support-forum/sheet-metal-part-not-showing-bend-lines/m-p/11837691
- F10 Flat pattern compute failure: https://forums.autodesk.com/t5/fusion-support-forum/problem-creating-flat-pattern/m-p/10517200
- F11 Radiused flange limitation: https://forums.autodesk.com/t5/fusion-support-forum/radiused-flange/td-p/9743677
- F12 Arkance lofted flange overview: https://ukcommunity.arkance.world/hc/en-us/articles/21564849498386-Fusion-360-Lofted-Flange-Overview
- F13 VDCI flat pattern drawings / DXF: https://vdci.edu/learn/fusion/master-flat-pattern-drawings-using-fusion-360 ; https://vdci.edu/learn/fusion/fabricating-metal-folding-bracket-fusion-dxf-files
- F14 Exported DXF issue (DXF Export left of Finish Flat Pattern): https://forums.autodesk.com/t5/fusion-design-validate-document/exported-dxf-issue/m-p/12903518
- F15 HP Academy flanges course: https://www.hpacademy.com/courses/3d-modeling-and-cad-for-motorsport/flanges/
- F16 K-factor user modification (preview era): https://forums.autodesk.com/t5/fusion-360-preview-functionality/sheet-metal-k-factor-user-modification/m-p/6864342
- F17 Cannot unfold (Press Pull): https://forums.autodesk.com/t5/fusion-support-forum/cannot-unfold-sheet-metal/m-p/13972371
- F18 SendCutSend study guide: https://sendcutsend.com/wp-content/uploads/2025/11/5.8.pdf
- F19 In-design rules vs library: https://forums.autodesk.com/t5/fusion-design-validate-document/sheet-metal-library-and-quot-in-design-rules-quot-interface/td-p/14107797
- F20 Crash on refold: https://forums.autodesk.com/t5/fusion-support-forum/fusion-crashes-on-re-fold/td-p/14033151

**Inventor analogues used for G(Inv)**
- https://help.autodesk.com/cloudhelp/2026/ENU/Inventor-Help/files/GUID-EEFF7315-EF98-4922-AE22-09F9C6B3D488.htm (corners, auto-miter, miter gap, laser weld)
- https://help.autodesk.com/cloudhelp/2026/ENU/Inventor-Help/files/GUID-73672AED-283A-4F81-BB6F-647D28D3694F.htm (unfold/refold pairs)
- https://help.autodesk.com/cloudhelp/2014/ENU/Inventor/files/GUID-70D8FDA3-4A33-4FDF-93F7-7CAB67EE2C28.htm (lofted flange facet distance)

---

## Critic pass

Second, independent pass, 2026-10-23. The first researcher's text above is unchanged.

### CP0. What this pass could and could not check

- **No new web evidence was gathered.** WebSearch refused every query ("this turn's web
  search budget is used up": 200 searches per turn, shared by all agents in the run, already
  spent). WebFetch fails DNS on every host tried (help.autodesk.com, www.autodesk.com,
  forums.autodesk.com, sendcutsend.com), and the sandbox proxy answers 403 to a CONNECT to
  help.autodesk.com. The limits were not worked around.
- So this pass is:
  1. a check of the maths, geometry and internal consistency of §1 to §5;
  2. a comparison with the scaffold already committed on `develop` (commit a00bd39:
     `src/Mod/SciForge/sciforge/sheetmetal_core.py`, `sheetmetal.py`) and with
     `docs/sciforge/parity/ui-shell.md`;
  3. recalled knowledge of Fusion and Inventor, tagged so a later session can verify it.
- **Tags added in this pass.** Both are kinds of G: nothing here was checked against a source
  this session.
  - **D**: derived and checked here (arithmetic run in Python, geometry worked through,
    sections cross-read). Reliable as maths and logic, but adds no new fact about Fusion's UI.
  - **G(mem)**: recalled from training knowledge of Fusion or Inventor documentation, not
    verified. Treat it as a lead to check, not a fact.
- No new A or F tags were added, because no new source was read.

### CP1. Corrections (the wrong line quoted, then the fix)

1. **§4.8 step 3 (flatten algorithm).** The file says: "The child flange is rotated by −θ about
   the bend axis and translated by BA − (geometric arc)."
   - **Wrong.** Rotating the child wall by −θ about the bend axis already puts its tangent line
     onto the parent's tangent line, because both lie on the same bend cylinder. The bend
     zone is now zero long, so the child must then move by the **full BA**: in the parent's
     plane, perpendicular to the bend axis, away from the parent.
   - A point inside the bend zone, at angle φ from the parent's tangent line, maps to distance
     φ·(R + K·T) from that line. This holds whichever layer (inner face or outer face) the
     point is on.
   - Source: D. This also matches the sm-flat brief ("rotation about the bend axis ... then
     translation by the developed length").
2. **§4.2 table, OSSB row.** The file says: "`OSSB = tan(θ/2) · (R + T)` | For θ ≤ 180°".
   - **Should be θ < 180°.** tan 90° is infinite, so OSSB and BD do not exist for a 180° fold,
     which covers every hem and a 180° edge flange.
   - For those parts, compute the flat length from tangent lines only:
     `L = Σ straight segments between tangent lines + Σ BA`.
   - **Flat hem** (gap 0, inner radius 0): BA = π·K·T, which is 1.38230 for T = 1, K = 0.44.
   - **Open hem** with gap g: inner radius = g/2, and BA = π·(g/2 + K·T), which is 2.16770 for
     g = 0.5.
   - Source: D.
   - **Knock-on effect in §4.3.** The Inner Faces and Outer Faces height datums measure from a
     virtual sharp, and a 180° flange has none. §2.2.2 allows Angle up to 180°, so SciForge
     needs a rule for that case. Suggested: at 180°, measure from Tangent To Bend, or refuse
     Inner/Outer with a reason (G). Fusion's actual behaviour is unknown.
3. **§2.2, common inputs table, "Corner Relief override (2 bends)" row.** The file lists "Round /
   Square / Tear / Trim To Bend / Linear Weld / Arc Weld".
   - This omits **Laser Weld**, which §3.1 (rule field) and §2.9 (Corner Closure) both list
     from the API enum (A[R22] LaserWeld = 6). The help page A[R1] probably predates Laser
     Weld, or the search excerpt was cut short.
   - SciForge: offer the same seven shapes in the override as in the rule (D for the
     inconsistency, G for the choice).
4. **§3.2 "Recommended defaults for the other fields" contradicts the committed scaffold**
   (`sheetmetal_core.FIELDS`):

   | Field | §3.2 says | Scaffold has | Inventor default style, G(Inv)+G(mem) |
   |---|---|---|---|
   | Miter/Rip/Seam Gap | `Thickness * 1` | `Thickness` | Thickness |
   | Relief Width | `Thickness * 1` | `Thickness` | Thickness |
   | Relief Depth | `Thickness * 0.5` | `Thickness / 2` | Thickness * 0.5 |
   | Relief Remnant | `Thickness * 0.5` | `Thickness * 2` | Thickness * 2.0 ("Minimum Remnant") |
   | 2-bend Relief Size | `Thickness * 2` | `Thickness * 4` | Thickness * 4.0 |
   | 3-bend Relief Radius | `Thickness * 2` | `Thickness * 4` | not recalled |
   | Bend Relief Shape | Round | round | Straight (G(mem), Inventor) |

   - **Recommendation: keep the scaffold values and treat §3.2's table as superseded.** The
     scaffold values match Inventor's defaults, and Fusion's rules come from Inventor. None of
     these values is confirmed for Fusion itself.
   - A remnant of 0.5·T would remove almost no slivers, which defeats the purpose of that field
     (D).
5. **§1 opening sentence, tab order.** The file says "SOLID, SURFACE, MESH, **SHEET METAL**,
   PLASTIC, UTILITIES and MANAGE".
   - `docs/sciforge/parity/ui-shell.md` line 24, which the repo already ships, says "SOLID,
     SURFACE, MESH, SHEET METAL, PLASTIC, MANAGE, UTILITIES".
   - Neither order was re-sourced in this pass. Builders should keep ui-shell.md's order and
     not reorder the tabs based on this file (D).
6. **§3.1, Bend Relief Relief Shape row.** The file says "Tear: no relief cut; the material
   tears, leaving a remnant".
   - This mixes two separate things. **Tear** is a zero-width rip along the end of the bend
     zone: the bend's side faces are split from the parent and nothing is removed.
   - **Relief Remnant** is a separate field that applies to Straight and Round reliefs.
   - §4.5 already describes this correctly; §3.1 should match it (D).
7. **§3.1 and §4.6: Round 2-bend corner relief, "Relief Size = the cut-out radius".** This is
   unverified and looks too big when combined with the scaffold's default of `Thickness * 4`
   (D):
   - With T = R = 1, the two bend zones meet inside a square about R + T = 2 mm across.
   - A circle of **radius** 4 mm (8 mm across) would eat far past both bend zones.
   - A circle of **diameter** 4 mm (radius 2 mm) just covers the bend crossing.
   - G(mem): Inventor's dialog sketch dimensions the round corner relief across the circle,
     which suggests a diameter, but this was not confirmed.
   - **Decision needed.** Either Size = diameter with the 4·T default, or Size = radius with a
     2·T default. Write the choice in the parity doc and the rule dialog tooltip.

### CP2. Missing commands and options (all G(mem) or D: verify before calling them Fusion facts)

1. **Other DXF routes.** F[F4]'s title is "4 ways to export a DXF from Fusion 360", but the spec
   documents only FLAT PATTERN > Export DXF. Recalled routes (G(mem)):
   - Create Sketch on the flat face, project the face, then right-click the sketch > Save As
     DXF.
   - A Drawing of the flat pattern, then Output > DXF.
   - The flat pattern's Export DXF itself.
   - A fourth route (Manufacture, or the export dialog) was not recalled precisely.

   Builders only need Export DXF for the tab, but the sketch route is how many users really
   work.
2. **Users of the flat pattern outside the tab** (G(mem)).
   - Design > Arrange (2D true-shape nesting) and the Nesting & Fabrication extension accept
     sheet metal flat patterns.
   - This is out of scope for the tab, but it is a reason to keep the flat pattern a
     first-class object with a clean outline API.
3. **Where the Rule drop-down appears.**
   - G(mem): the Flange dialog shows **Rule** only when the flange makes a new body (a
     base/contour flange with New Body).
   - D: an edge flange, or any Join, must use the body's own rule. One sheet metal body has one
     thickness, so it cannot follow two rules.
   - The spec's common table (§2.2) puts Rule on every mode; restrict it as above.
4. **Parameters.**
   - G(mem): Height, Angle, Distance, Width and so on become model parameters (d1, d2, ...) in
     Change Parameters, like every Fusion feature.
   - Unknown: whether rule fields accept **user parameter** names besides `Thickness`, for
     example a user parameter `t` in a rule's Thickness. This matters because SciForge already
     has user parameters.
   - Suggested (G): accept user parameter names in rule expressions. If Fusion turns out not
     to, list it as a SciForge extension.
5. **Several sheet metal bodies in one component** (G(mem)).
   - Fusion has allowed several sheet metal bodies per sheet metal component for years.
   - With "one flat pattern per component" (A[R35]), the flat pattern flattens **only the body
     that owns the picked stationary face**. Flattening another body means deleting the flat
     pattern or moving that body to its own component.
   - The sm-flat brief puts the Flat Pattern node "under its body". Decide which node it hangs
     from (Fusion: under the component, §2.12), and what happens when that body is deleted.
6. **Convert to Sheet Metal on a solid with sharp inner corners** (a shelled box with no
   fillets). Fusion's behaviour was not found; A[R47] only warns that inconsistent radii break
   the flat pattern.
   - Suggested SciForge rule (G): refuse with a reason that names the sharp edge. The reason
     should suggest filleting the inside at R and the outside at R + T, or a Rip.
   - Do **not** silently insert bends. That would change the part's size.
7. **Lofted flange, Die Form flat pattern.**
   - G(Inv)+G(mem): Inventor flattens die-formed lofted flanges approximately, with no bend
     lines. Fusion's behaviour is unknown.
   - The sm-more brief's choice (refuse the flat pattern with a reason when the shape cannot
     be developed) is a safe SciForge default. Record it as a known gap.
8. **FLAT PATTERN contextual tab contents** (G(mem), extends §1.4): CREATE (Create Sketch...),
   CONSTRUCT, INSPECT (Measure...), SELECT, an EXPORT group with Export DXF, and FINISH FLAT
   PATTERN at the right. This matches the confirmed part of §1.4 (Export DXF sits left of
   Finish, F[F14]).
9. **Commands Fusion does NOT have.** Do not build these as "parity" (G(mem); §3.1 already
   says this about bend tables). Several are standing requests on the Fusion Ideas forum:
   - punch and form tools (louvers, dimples, lances, extruded holes);
   - jog/joggle, cross break, gusset, tab-and-slot generator;
   - Inventor's Contour Roll, and Corner Seam / Corner Round as separate commands (Corner
     Closure and the SM Fillet/Chamfer cover part of this);
   - bend tables and bend-deduction tables.
10. **Flat hem, how to build it** (D, implementation note for §2.4).
    - A 180° fold with inner radius 0 is a valid OCC solid: revolve the T × width
      cross-section about its inner edge, so the inner cylinder collapses to a line.
    - The unfolder must accept a bend with no inner cylindrical face, and use BA = π·K·T (CP1
      item 2).
    - Prefer this to a fake small radius, which would put a tiny wrong amount into the flat
      length.
11. **Corner Closure relief placement list.**
    - The scaffold's `TWO_BEND_PLACEMENTS = ("intersection", "tangent")` is correct for the
      **rule** dialog: per §3.1, only Round (Intersection/Tangent) and Square (Intersection)
      take a placement.
    - Corner Closure has its own enum with **Vertex** (A[R39]: Tangent = 0, Intersection = 1,
      Vertex = 2; default Tangent). It needs its own placement list. Do not add Vertex to the
      rule dialog (D).

### CP3. Guesses and maths confirmed by checking

1. **The §4.2 worked example is correct** (D, recomputed in Python). With T = R = 1,
   K = 0.44, θ = 90°:
   - BA = 2.26195, OSSB = 2, BD = 1.73805.
   - The 50 × 50 L bracket flattens to 98.26195. Computed the other way, through tangent
     lines, it is 48 + 48 + BA, the same number.
   - Extra values for unit tests, with the same T, R and K and θ the deflection angle:

   | θ | BA | OSSB | BD |
   |---|---|---|---|
   | 45° | 1.13097 | 0.82843 | 0.52588 |
   | 120° | 3.01593 | 3.46410 | 3.91227 |
   | 135° | 3.39292 | 4.82843 | 6.26393 |

2. **§4.3 height datum table and §4.4 bend position coordinates rechecked: consistent** (D).
   - Inside, 90°: the bend axis is at (−T−R, T+R) and the outer cylinder of radius R + T just
     reaches x = 0, so Tangent = Inside at 90°, as stated.
   - The straight lengths H − ISSB and H − OSSB are right at 90° and in general.
3. **The K-factor range 0 to 1** (§2.1, A[R25]) matches the scaffold's `validate()`. "K-factor
   only, no bend tables" (§3.1) matches the scaffold's `UNFOLD_RULES = ("k_factor",)` (D).
4. **Rule per body, active rule per component** (§2.1 "G" items) matches the scaffold contract
   (`sheetmetal.py`: a body stores `SciForgeSheetMetalRule`; a component stores its active
   rule). Deleting a rule that is in use is refused in the scaffold too. This is consistent,
   though still unconfirmed for Fusion (D).
5. **Library naming** (G(mem)).
   - Fusion's library lists each material as a pair, "<Material> (mm)" and "<Material> (in)".
     This is consistent with F[F6] "Steel (mm) (Default)" and with A[R20] (units fixed per
     rule).
   - A Copper pair is recalled in the default library, but not verified. The forum thread
     cited in §3.2 asks *which* rule to use for copper, which does not prove there is none.
   - The scaffold's eight rules (Steel, Stainless Steel, Aluminum, Copper, each in mm and in)
     are fine as SciForge's own data. Their thicknesses stay G.

### CP4. Verify these first when web access is back (most valuable first)

1. **API sample "Sheet Metal Rules Sample"** (R26). It prints the library rules, so it would
   settle the rule names and every default value at once (§3.2, CP1 item 4).
2. **HemFeatureInput and the Hem help page** (R13, R14, R30): the default type and values.
   Also whether Teardrop's second value is a length or an angle (§5 item 5).
3. **SM-REF-BASE-EDGE-CONTOUR-FLANGE** (R2): the default Height Datum and Bend Position, and
   whether Rule shows on edge flanges (CP2 item 3).
4. **TwoBendReliefShapes and SM-RULES-REF** (R22, R6): whether the Round corner relief size is
   a radius or a diameter (CP1 item 7).
5. **"What's New" posts for Sep 2025 to Sep 2026** (R42, R43, plus May 2026 and Jan 2026,
   which were not read): the UI names and menu places of Hem, Corner Closure, Join by Bend
   and SM Fillet/Chamfer (§5 items 1, 8, 9).
