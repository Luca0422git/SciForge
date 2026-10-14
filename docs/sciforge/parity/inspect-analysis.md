# Parity spec: INSPECT surface analyses (outline 7.11)

Zebra, Draft, Curvature Comb, Curvature Map, Isocurve, Accessibility and Minimum Radius
Analysis, plus Display Component Colors. Measure, Interference, Section Analysis and Center
of Mass are in `inspect.md`; the navigation bar (outline 7.14) is in `ui-shell.md`.

Implemented in `src/Mod/SciForge/sciforge/`: `analysis_core.py` (the maths, no FreeCAD, no
Qt, unit tested), `surface_analysis.py` (the analysis objects, no Qt), `surface_analysis_ui.py`
(the commands, the dialog, the drawing), `component_colors_ui.py`. Status: **built and tested
with real clicks, not yet signed off by Luca** (2026-10-14).

Tests: scenarios `inspect_analysis_zebra` (74 checks), `inspect_analysis_draft` (56),
`inspect_analysis_curvature` (71), `inspect_analysis_components` (28); unit tests
`test_analysis_core.py`.

## Behaviour spec and sources

Source column: **Autodesk** = Fusion help or API reference (read through search excerpts:
help.autodesk.com is not reachable from the sandbox), **Forum** = Autodesk Community or a
tutorial, **Guess** = nothing found, SciForge's choice. Behaviour only; no Fusion wording or
pictures were copied.

### Shared by every analysis

| Fusion | Source | SciForge |
|---|---|---|
| INSPECT menu: Measure, Interference, Curvature Comb, Zebra, Draft, Curvature Map, Isocurve, Accessibility, Minimum Radius, Section, Center of Mass, Display Component Colors | Autodesk | Same entries, same order (`ribbon_config.py` INSPECT). |
| A dialog: pick bodies (Curvature Comb: edges, Isocurve: faces or bodies), set options, the result shows on the model at once | Autodesk | Same. Something selected before the command is used. A face or edge click on a body picks that body for the body-wide analyses. Clicking a picked thing again drops it. |
| OK keeps the analysis in the browser's **Analysis** folder; its eye shows / hides it; right-click > Edit opens the dialog again | Autodesk | Same, plus double-click to edit and Delete. Named Zebra1, Draft1 ... with the analysis' own icon. Not in the timeline. |
| Saved with the design | Autodesk (API: analyses are part of the design) | Same: an `App::FeaturePython` per analysis with what its dialog set; after reopening it draws itself again. |
| Hiding an analysis shows the model as it was | Guess (obvious) | Same: the model is never changed (the analysis only draws over it). |
| Opacity 0 .. 100 (Zebra, Draft, Curvature Map, Accessibility, Minimum Radius) | Autodesk | Same: 0 shows the body's own colour, 100 only the analysis. |
| High Quality: finer display, slower | Autodesk | Same: the analysis is worked out on about 2.7 times finer triangles. |
| The analysis follows model changes | Guess | Same: drawn again a moment after every recompute, undo, redo, show / hide. A deleted body or face: the analysis shows nothing and its dialog says why. |
| Undo | Guess | Creating or editing an analysis is one undo step; Ctrl+Z removes a new one, Ctrl+Y brings it back. Cancel / Esc leave nothing. |
| Mesh, T-spline bodies can be analysed | Autodesk (API lists mesh bodies for Zebra) | Solid and surface bodies only (see gaps). |

### Zebra Analysis

| Fusion | Source | SciForge |
|---|---|---|
| Black and white stripes on the body, as reflections: they move when the view turns or zooms | Autodesk | Same. Each point's view ray is mirrored at the surface; the stripe is where the mirrored ray meets a striped ball round the model (rings of stripes). Smooth surfaces give smooth stripes; a crease (only G0) breaks them. |
| Direction: Vertical (default) or Horizontal | Autodesk (API `isVertical`, default true) | Same. Inventor's Radial is not in Fusion. |
| Repeats 1 .. 100 | Autodesk | Same; default 20 (Guess: the API excerpt gives both 20 and 100). |
| Lock Stripes: the stripes stay on the model while it turns | Autodesk | Same: the camera at the moment of locking is kept with the analysis (saved too). |
| Opacity, High Quality | Autodesk | Same. |

### Draft Analysis

| Fusion | Source | SciForge |
|---|---|---|
| Colour gradient by draft angle against a pull direction | Autodesk | Same. |
| Direction: pick a plane, flat face, edge or axis; Flip | Autodesk | Same; nothing picked = +Z of the body. |
| Draft Angle start / stop | Autodesk | Same: below start red, from stop on green / blue, in between a blend; defaults 1 and 3 deg (Guess). |
| Green: enough draft along the pull; blue: enough against it; red: none | Forum | Same. |
| Tolerance Zone: the band between start and stop yellow | Forum | Same. |

### Curvature Comb Analysis

| Fusion | Source | SciForge |
|---|---|---|
| A comb along each picked edge: teeth perpendicular to the edge, as long as its curvature | Autodesk | Same; a straight stretch has no teeth. Teeth coloured blue (straight) to red (tightest). |
| Density: teeth per edge, 2 .. 100 | Autodesk | Same; default 30 (Guess). |
| Scale | Autodesk | Same: at 1 the tallest tooth is a quarter of the edge's size. |
| Sketch curves: Toggle Curvature Display (right-click) | Autodesk | Not here (sketch area). |

### Curvature Map Analysis

| Fusion | Source | SciForge |
|---|---|---|
| Gaussian: positive red / orange / yellow, flat (one way or both) green, negative blue / indigo / violet | Autodesk | Same. |
| Display Smooth or Bands (Gaussian only) | Autodesk | Same (four steps each side). |
| Scale (Gaussian only) | Autodesk | Same: at 1 a round about a tenth of the part's size shows warm. |
| Principal Minimum (Maximum Limit) and Principal Maximum (Minimum Limit): green where the value meets the limit, red where it goes past | Autodesk | Same; the limit is typed as a radius in mm (a round tighter than it is red; towards it green turns yellow). Guess: Fusion's field is a curvature "in design units". |

### Isocurve Analysis

| Fusion | Source | SciForge |
|---|---|---|
| U and V lines on the picked faces or bodies; Type U and V / U / V; Isocurves per direction | Autodesk | Same; default 5 per direction (Guess), 1 .. 50. |
| Curvature Combs on each isocurve, with Density and Scale | Autodesk | Same. |

### Accessibility Analysis

| Fusion | Source | SciForge |
|---|---|---|
| Shows where a tool coming from a direction cannot reach (undercuts) | Autodesk | Same: a point is reachable when it faces the tool and nothing of the body is in the way (a ray test against the body's own triangles). |
| Direction from an edge, axis or face; Direction 1 / Direction 2 / Both Directions; Opacity | Autodesk | Same. |
| Colours | Guess | Reachable green, not reachable red. |

### Minimum Radius Analysis

| Fusion | Source | SciForge |
|---|---|---|
| Colours concave rounds by radius: where a cutter of a given radius cannot go | Autodesk | Same: concave rounds a tool of Tool Radius fits green, tighter than Minimum Radius red, a blend through yellow in between; convex and flat faces neutral grey. |
| With tool radius 0 everything green; a bigger tool turns tight rounds red | Autodesk (example) | Same. A second Autodesk example (rounds under 1.6 mm green, over 6 mm red) reads the other way round; SciForge follows the first. |
| Include sharp curves | Forum | Not built (sharp inner corners count as radius 0 in Fusion; SciForge colours faces only). |

### Display Component Colors (Shift+N)

| Fusion | Source | SciForge |
|---|---|---|
| Each component's bodies in a colour of their own; Shift+N again: their appearances | Autodesk (shortcut), Forum | Same, display only (nothing in the design or the undo history); the INSPECT entry is ticked while on. Bodies under an analysis keep the analysis. |
| Right-click a component > Cycle Component Color | Forum | Not built. |

## How it maps onto FreeCAD

- Each analysis is an `App::FeaturePython` (`SciForgeType` "ZebraAnalysis" ...), so the
  browser puts it in the Analysis folder (`browser_core.ANALYSIS_ICONS`) and the timeline
  leaves it out. Saved files store `sciforge.surface_analysis.SurfaceAnalysis`.
- Drawing: the faces are tessellated at the view provider's own display deflection
  (`(lx+ly+lz)/300 x Deviation`, a hair finer), so OCC hands back the triangles the model
  is drawn with; they are split (new points lie on the old triangles) and each point gets
  the surface's normal and curvatures (`face.Surface.parameter`, `normalAt`, `curvatureAt`;
  sign flipped on reversed faces). The overlay sits under a `SoPolygonOffset(1, 1)` (the
  same as FreeCAD's faces), and while it covers a body that body's face draw style
  ("FaceStyle", in two display modes) is switched to INVISIBLE, so the two never fight for
  the same pixels. The model's edges stay on top.
- Zebra stripes are a 64 x 2 texture (`SoTexture2`, BLEND for opacity) with one texture
  coordinate per point; a 90 ms timer looks at the camera and works them out again (numpy)
  when it moved.
- Components: the overlay is put into the component's placement, so it lies on the body
  where the component has moved it.

## Gaps (not built, and why)

- **Mesh and T-spline bodies.** FreeCAD's `Mesh::Feature` has no exact surface (no
  curvature, no `normalAt`); Zebra and Draft could be done from mesh normals, not yet.
  T-splines do not exist in FreeCAD.
- **Stripe look.** Fusion draws its stripes from an environment picture on the GPU;
  SciForge's striped ball is a model of it (Guess), worked out per point on the CPU, so on
  very coarse triangles the stripes can look slightly stepped (High Quality helps).
- **Include Sharp Curves** (Minimum Radius) and **Cycle Component Color** (right-click) not
  built.
- Isocurve lines and comb teeth are drawn on the surface, not lifted towards the camera:
  on a face seen almost edge-on a line can dip behind it.
- Colours of Accessibility and Minimum Radius, and the default numbers marked Guess above,
  need a look at real Fusion.
