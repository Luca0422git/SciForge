# Fusion PLASTIC tab: behaviour spec for SciForge

Black-box documentation research only. SciForge copies **behaviour**, never Autodesk's assets, wording, icons or code.
Every dialog label below is a *description of behaviour*. SciForge should use its own wording when a Fusion label is
distinctive (see CLAUDE.md).

---

## 0. Sources, confidence and research limits

### 0.1 How this was researched (read this first)

- The sandbox could not open Autodesk web pages (help.autodesk.com, autodesk.com blog, forums, AU PDFs, YouTube, tutorial
  sites were all refused by the proxy; WebFetch had no DNS). Autodesk help and blog text was therefore read **only through
  search-result excerpts**. Help-page facts below are paraphrases of those excerpts.
- The **official Fusion API reference** (May 2026 release) was readable in full from Autodesk's own GitHub mirror
  `AutodeskFusion360/FusionAPIReference` (Python stubs `Fusion_API_Python_Reference/defs/adsk/fusion.py`, the C++ headers
  and the HTML pages, including `BossFeatureSample_Sample.htm` and the "Introduced in version" footers). It is the most
  precise source here: it has exact option names, enums and units for **Boss**, **Plastic Rules** and **Rule Fillet**.
- The API has **no** objects for Snap Fit, Lip or Rest. There are no `SnapFit*`, `Lip*` or `Rest*` classes, and no
  headers under `include/Fusion/Plastic/` for them (checked: 404). Their dimension lists therefore rest on help excerpts
  plus inference (tag G).
- The shared web-search budget (200 per turn) ran out before every dialog label could be confirmed. The open questions in
  section 5 list what is still unconfirmed.

### 0.2 Source tags

| Tag | Meaning |
|---|---|
| **A** | Autodesk: help page, API reference, Autodesk blog, release notes, AU class page, Autodesk support article, Autodesk's own social post |
| **A-api** | Autodesk Fusion API reference (May 2026), read in full from github.com/AutodeskFusion360/FusionAPIReference |
| **A-inv** | Autodesk **Inventor** help. Same vendor, analogous feature. Used only as a hint for naming; not proof of Fusion behaviour |
| **F** | Forum / tutorial / reseller blog |
| **G** | My inference, or a SciForge design decision. Nothing confirms it |

### 0.3 URL list (cited by short id)

| Id | URL |
|---|---|
| A-BOSS | https://help.autodesk.com/cloudhelp/ENU/Fusion-Model/files/SLD-BOSS.htm ("Create a boss") |
| A-SNAP | https://help.autodesk.com/view/fusion360/ENU/?guid=SLD-SNAP-FIT (also .../cloudhelp/ENU/Fusion-Model/files/SLD-SNAP-FIT.htm) |
| A-SNAPCOURSE | https://help.autodesk.com/view/fusion360/ENU/courses/AP-PDE-SNAP-FIT ("Add snap fits to solid bodies") |
| A-LIP | https://help.autodesk.com/view/fusion360/ENU/?guid=SLD-LIP |
| A-SKETCHSOLIDS | https://help.autodesk.com/view/fusion360/ENU/?guid=SLD-CREATE-SOLID-FROM-SKETCH (lists Boss, Rest, Snap Fit, Lip, Rib, Web, Emboss; Rest text) |
| A-RULES | https://help.autodesk.com/view/fusion360/ENU/?guid=SLD-SETUP-PLASTIC-RULES |
| A-DA | https://help.autodesk.com/view/fusion360/ENU/?guid=SLD-DESIGN-ADVICE |
| A-RIB | https://help.autodesk.com/cloudhelp/ENU/Fusion-Model/files/SLD-RIB.htm |
| A-WEB | https://help.autodesk.com/cloudhelp/ENU/Fusion-Model/files/SLD-WEB.htm |
| A-DRAFTREF | https://help.autodesk.com/cloudhelp/ENU/Fusion-Model/files/SLD-REF-DRAFT.htm |
| A-BLOG-ASSIGN | https://www.autodesk.com/products/fusion-360/blog/plastic-rules-fusion-360-product-design-extension/ |
| A-BLOG-MANAGE | https://www.autodesk.com/products/fusion-360/blog/how-to-manage-plastic-rules-fusion-360-product-design-extension/ |
| A-BLOG-SNAPBOSS | https://www.autodesk.com/products/fusion-360/blog/fusion-360-product-design-extension-snap-fit-and-bosses/ |
| A-BLOG-DA | https://www.autodesk.com/products/fusion-360/blog/design-advice-make-better-design-decisions-in-fusion-360/ |
| A-JUL22 | https://www.autodesk.com/products/fusion-360/blog/july-2022-product-update-whats-new/ (v2.0.13619, 13 Jul 2022) |
| A-MAY23 | https://www.autodesk.com/products/fusion-360/blog/may-2023-product-update-whats-new/ |
| A-X-LIP | https://x.com/adskFusion/status/1666150649447186438 (Autodesk Fusion account, June 2023) |
| A-AU22-TIPS | https://www.autodesk.com/autodesk-university/class/Fusion-Product-Design-Extension-Tips-and-Tricks-2022 |
| A-AU22-SWAIN | https://www.autodesk.com/autodesk-university/class/How-Design-Plastic-Parts-More-Effectively-Fusion-360-2022 (+ handout CP500829) |
| A-EXT | https://help.autodesk.com/cloudhelp/ENU/Fusion-Extensions/files/EXT-PRODUCT-DESIGN.htm |
| A-SUPPORT | https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/Where-does-tab-Plastic-come-from-in-Fusion-360.html |
| A-COMPARE | https://damassets.autodesk.net/content/dam/autodesk/www/pdfs/fusion360-product-design-extension-comparison-matrix.pdf |
| A-API | https://github.com/AutodeskFusion360/FusionAPIReference (fusion.py, `BossFeatureSample_Sample.htm`, `PlasticRule*.htm`) |
| A-APIWN | https://help.autodesk.com/view/fusion360/ENU/?contextId=APIWhatsNew (October 2026 notes, excerpt only) |
| A-inv-SNAP | https://help.autodesk.com/cloudhelp/2024/ENU/Inventor-Help/files/GUID-64112579-9BD8-45E7-8A8F-7B83739861E5.htm |
| A-inv-LIP | https://help.autodesk.com/view/INVNTOR/2024/ENU/?guid=GUID-6A70A843-8425-4AE1-9894-1F26FE35FF4C |
| F-MANMACHINE | https://www.manandmachine.co.uk/fusion-360-plastic-part-modelling/ |
| F-SYMETRI | https://www.symetri.co.uk/insights/blog/autodesk-fusion-360-product-design-extension/ |
| F-MOLDFLOW | https://www.moldflow.eu/how-to-use-the-design-advice-feature-for-plastic-parts-in-fusion-360/?lang=en |
| F-FORUM-RIB | https://forums.autodesk.com/t5/fusion-support-forum/require-help-creating-gussets-ribs-on-plastic-bosses/td-p/11481167 |
| F-RJC | https://rjcmold.com/guides/lip-and-groove-design/ (generic lip/groove guidance) |
| F-HUBS | https://www.hubs.com/blog/cad-modeling-3-snap-fits/ (generic snap-fit guidance) |

### 0.4 Timeline of the plastic toolset (what was added when)

| When | What | Src |
|---|---|---|
| ~2021 | "Product Design Extension" launched with plastic features (Boss, Snap Fit, Rib/Web draft, plastic rules, Design Advice) | A (A-BLOG-SNAPBOSS, A-BLOG-ASSIGN); date G |
| 13 Jul 2022 | **Rest** command added. Snap Fit gets **Selection Mode** (Automatic/Manual) and **Rotation Type** (Uniform/Independent/Aligned) | A-JUL22 |
| Oct 2022 | Boss exposed in the API (`BossFeatures`, `BossFeatureInput`, `BossFeatureSideInput`) | A-api |
| Jan 2023 | Draft, Accessibility and Minimum Radius analyses exposed in the API | A-api |
| May 2023 | **Lip** command (types Lip / Groove / Lip And Groove) | A-MAY23, A-X-LIP |
| Jan 2024 | Plastic rules exposed in the API (`PlasticRule`, `PlasticRules`, `PlasticRuleValue`, incl. `revealHeight`, `clearance`), plus configuration "plastic rule table" | A-api |
| Nov 2025 | Rule Fillet exposed in the API | A-api |
| Oct 2026 | API: create/edit Rib and Web (`RibFeatureInput`), `RibFeature.draftAngle`, `RibFeature.draftPullDirection`, `DraftAnalysis.directionEntity`, `DraftFeature.fixedPlaneAngleMode` | A-APIWN (excerpt) |
| now | Extension renamed **"Fusion Design Extension"** (formerly Product Design Extension) | A-JUL22 / A-EXT |

Licensing: the plastic options appear when the Design Extension is owned (A-SUPPORT). The comparison matrix lists
"plastic design tools (bosses, snap fits, ribs, webs)" as extension-only (A-COMPARE). Plain Rib/Web/Emboss also exist on
the SOLID tab; only their **draft** and **fillet** steps are extension features (A-RIB, A-WEB, F-FORUM-RIB).
SciForge has no licensing: everything is always on (G).

---

## 1. Tab layout, groups and menu order

### 1.1 What is confirmed

| Fact | Src |
|---|---|
| Design workspace has a **PLASTIC** tab, next to SOLID / SURFACE / MESH / SHEET METAL / UTILITIES | A (A-BLOG-ASSIGN: "switch to the Plastic tab") |
| **Plastic > Setup** panel holds **Assign Plastic Rule** and **Manage Plastic Rules** | A-RULES (excerpt: "the Plastic > Setup panel") |
| **Plastic > Create** holds **Boss**, **Snap Fit**, **Lip**, **Rest** | A-BOSS, A-SNAP, A-LIP, A-JUL22 |
| Boss: "Only available on the Plastic tab" | A-BOSS / A-SKETCHSOLIDS |
| Rib, Web and Emboss are SOLID > Create commands. The plastic tab carries them too, and their draft/fillet steps belong to the extension | A-WEB ("Solid > Create > Web"), A-RIB, A-SKETCHSOLIDS |
| Plastic-rule values (Thickness, Draft Angle, Nominal Radius) are "referenced as parameters and used by" **Extrude, Rib, Web, Boss, Snap Fit, Emboss, Thicken, Shell, Draft** | A-RULES / A-BLOG-ASSIGN |
| Lip also takes its values from the rule ("Assign a Plastic Rule before creating a Lip feature") | A-LIP |
| AU 2022: the manufacturing-aware features are Boss, Snap Fit, Rest, (Geometric) Pattern, Rib, Web, Thin Extrude, Shell, Fillet | A-AU22-TIPS |
| Rule Fillet exists as a fillet type (`FilletFeatureTypes.RuleFilletFeatureType`) | A-api |
| Draft Analysis, Accessibility Analysis and Minimum Radius Analysis exist (INSPECT) | A-api |
| Design Advice is the plastic manufacturability check driven by the rule | A-DA, A-BLOG-DA |

### 1.2 Menu order: Fusion (best reconstruction) and SciForge proposal

The exact order of every dropdown could **not** be confirmed (no screenshot or text listing was reachable). Below is the
order SciForge should implement. Fusion-confirmed membership is marked A; ordering is G. It follows the SOLID tab's
order, with the plastic-only commands grouped together.

**SETUP** (A for both items; panel position G: put it first, because the rule must be assigned before modelling, A-RULES best practice)
1. Assign Plastic Rule (A)
2. Manage Plastic Rules (A)

**CREATE** (dropdown; plastic-only items A, the rest G)
1. New Component
2. Create Sketch
3. Extrude (thin-extrude thickness and taper take rule defaults: A for "Extrude uses rule", field mapping G)
4. Revolve
5. Sweep
6. Loft
7. Rib (rule thickness + draft; A)
8. Web (rule thickness + draft + base fillet; A)
9. Emboss (rule; A)
10. Hole
11. Thread
12. ---- separator ----
13. **Boss** (A)
14. **Snap Fit** (A)
15. **Lip** (A)
16. **Rest** (A)
17. ---- separator ----
18. Thicken (rule thickness; A)
19. Mirror
20. Pattern (Rectangular / Circular / On Path / Geometric Pattern)

Toolbar promoted icons (G): Create Sketch, Extrude, Boss, Snap Fit, Lip, Rest.

**MODIFY** (G order; rule-aware items A)
1. Press Pull
2. Fillet (default radius = rule Nominal Radius: G mapping)
3. **Rule Fillet** (A-api exists; default radius = Nominal Radius, G)
4. Chamfer
5. Shell (rule thickness; A)
6. Draft (rule draft angle; A)
7. Scale
8. Combine
9. Offset Face, Replace Face, Split Face, Split Body, Silhouette Split
10. Move/Copy, Align, Delete
11. Physical Material, Appearance, Manage Materials
12. Change Parameters, Compute All

**ASSEMBLE / CONSTRUCT / INSERT / SELECT**: identical to the SOLID tab (G).

**INSPECT** (G order)
1. Measure, Interference, Curvature Comb, Zebra, **Draft Analysis**, Curvature Map, **Accessibility Analysis**,
   **Minimum Radius Analysis**, Isocurve, Section Analysis, Center of Mass, Display Component Colours
2. **Design Advice** (G placement. Fusion shows it as a rule-driven check, A-DA. SciForge exposes it as an INSPECT
   command plus an always-on alert badge.)

Simulation: injection-moulding / mould-fill simulation lives in Fusion's Simulation workspace and extension
(A-AU22-SWAIN: "Simulation Extension supports stress analysis and mold-filling simulation"). **Out of scope for SciForge.**

### 1.3 Which repeated SOLID commands pick up plastic-rule defaults

Rule: when the active component has a plastic rule, these dialogs open with the rule value **as an expression linked to
the rule**, not as a copied number. Editing the rule later updates the feature (A: "referenced as parameters";
A-AU22-TIPS: "Changing materials can update the features, and each feature connects to the rules update with proper wall
thickness, draft angle, and inner fillet radius"). Field mapping is G unless noted.

| Command | Input that gets the rule value | Rule field | Src |
|---|---|---|---|
| Extrude (Thin extrude) | Wall thickness | Thickness | A (Extrude listed; AU "Thin Extrude"), mapping G |
| Extrude | Taper angle | Draft Angle | G (only when a draft is requested; default stays 0 for normal extrudes) |
| Shell | Inside thickness | Thickness | A ("assign plastic rules prior to Shell or Thicken… inherit settings") |
| Thicken | Thickness | Thickness | A |
| Draft | Angle | Draft Angle | A (Draft listed), mapping G |
| Rib | Thickness; Draft Angle | Thickness; Draft Angle | A (Rib listed; rib draft step), mapping G |
| Web | Thickness; Draft Angle; base Fillet Radius | Thickness; Draft Angle; Nominal Radius | A (Web listed; draft + fillet step), mapping G |
| Emboss | Depth (and taper if present) | Thickness (fraction) / Draft Angle | A (Emboss listed), mapping G |
| Fillet / Rule Fillet | Radius | Nominal Radius | G (Nominal Radius is "the default nominal radius used in certain settings", A-BLOG-MANAGE) |
| Boss | Shank wall thickness (constant-thickness shape), shank/hole/rib draft | Thickness, Draft Angle | A-api (`BossFeature.thickness`: "plastic part rule reference"; `taperAngle`: "plastic part rule reference") |
| Snap Fit | Beam thickness, draft | Thickness, Draft Angle | A (Snap Fit listed; F-MANMACHINE: "picking up the Thickness and Draft Angle") |
| Lip | Lip width, lip height, clearance | Thickness, Reveal Height, Clearance | A (Lip uses rule; `revealHeight`, `clearance` are "used for plastic features"), mapping G |
| Rest | Thickness, draft | Thickness, Draft Angle | G (A-JUL22: Rest "can also adjust draft-type angles") |

If the component has **no** rule, SciForge uses the library **default** rule (A: a library rule can be "Set As Default"),
shows a one-time hint "No plastic rule assigned: using <default>", and does not auto-assign (G).

---

## 2. Commands

### 2.1 Assign Plastic Rule (SETUP)

**Purpose.** Attach one plastic rule to a component, so that its plastic features read their thickness, draft, radius,
material and so on from that rule (A-RULES: "assigns a plastic rule to a component to automatically control the
properties of plastic features, like physical material and thickness").

**Selection.** One component, picked in the browser or the canvas (A-BLOG-ASSIGN). Rules are assigned **at component
level only, never to individual bodies** (A-BLOG-ASSIGN).

| Input | Type / choices | Default | What it does | Src |
|---|---|---|---|---|
| Component | component selection (browser or canvas) | active component | Target of the assignment | A |
| Rule list | list grouped **In this Design** / **Library**; each row can be expanded to show its values | currently assigned rule, else library default | Picks the rule | A (A-BLOG-ASSIGN, A-BLOG-MANAGE) |
| (row expand) | read-only value list | n/a | Shows Thickness, Draft Angle, Nominal Radius, Design Advice values | A |

**Behaviour.**
- Picking a **Library** rule copies it into the design ("In this Design"). The component then references the design
  copy, so later library edits do not silently change the design (G, mirrors sheet-metal rule behaviour. The API
  separates `designPlasticRules` and `libraryPlasticRules`, and `PlasticRules.addByCopy` copies library to design: A-api).
- The rule's **material** becomes the component's physical material (A: "control … physical material"; `PlasticRule.material`, A-api).
- Every rule-linked feature in the component recomputes (A-AU22-TIPS).
- Best practice: assign before modelling, especially before Shell/Thicken (A-RULES).
- Configurations: a "plastic rule table" can switch the rule per configuration row, one column per component (A-api:
  `ConfigurationPlasticRuleTable`, `ConfigurationPlasticRuleColumns.add(component)`, Jan 2024). SciForge: support later (G).

**Browser/timeline.** Not a timeline feature (G, same as sheet-metal rule assignment). SciForge shows the rule name in
the component's tooltip/property view and greys the rule's "delete" when it is in use (A-api: `isUsed`).

**Errors.** Selecting a body instead of a component is refused: "Plastic rules apply to components" (G wording, A behaviour).

### 2.2 Manage Plastic Rules (SETUP)

**Purpose.** Create, edit, copy, delete and set-default rules, in the design and in the library (A-RULES: "Create new
rules, edit existing rules, or save rules to a library to use them in multiple designs").

**Dialog layout (A-BLOG-MANAGE).**
- Two collapsible lists: **In this Design** (local to the document) and **Library** (cloud library shared across
  projects. SciForge: a user-level library file).
- Each rule row has a **pencil** (edit) icon that opens **Edit Plastic Rule**.
- Right-click a library rule > **Set As Default**.
- Fusion ships "base plastic rules in metric and imperial" (A-BLOG-MANAGE), and "several common engineering grade resins
  are included in the Library" (A-AU22-SWAIN handout excerpt; an example rule is named like "ABS (1.5mm)"). The exact
  Fusion list is unknown (section 5). SciForge ships **its own** library (section 3.3).

**Row actions (G except where noted).** New (copy of the selected rule, A-api `addByCopy` semantics), Edit, Duplicate,
Delete, Rename, Copy to Library / Copy to Design, Set As Default (library only, A-api `isDefault`: "only valid for rules
in a library").

**Edit Plastic Rule dialog**: every field (names A-api; UI labels A-BLOG-ASSIGN/A-BLOG-MANAGE where known).

| Input (UI label) | API name | Type / units | Default (SciForge) | What it does | Src |
|---|---|---|---|---|---|
| Name | `name` | text, unique within design or library | "New rule" | Identifies the rule | A-api |
| Units | `units` | "mm" or "in", **fixed when the rule is created**, cannot change | document units | Units used to show values; bare numbers in expressions use these units | A-api |
| Material | `material` | physical material from library | ABS (SciForge library) | Becomes the component's physical material | A-api / A |
| **Thickness** | `thickness` (PlasticRuleValue) | length expression | 2.0 mm | "default nominal wall thickness" used by plastic commands when a wall thickness is needed; **must lie inside [Minimum, Maximum] thickness** | A-api, A-BLOG-MANAGE |
| **Draft Angle** | `draftAngle` (PlasticRuleValue) | angle expression (degrees in UI; radians as API float) | 1° | "default nominal draft angle" | A-api, A-BLOG-MANAGE |
| **Nominal Radius** | `nominalRadius` (PlasticRuleValue) | length expression | `Thickness / 2` | "default nominal radius" (fillets/rounds) | A-api, A-BLOG-MANAGE |
| **Reveal Height** | `revealHeight` (PlasticRuleValue) | length expression | `Thickness / 2` (G) | "reveal height used for plastic features": lip height / reveal step of Lip | A-api (field), mapping to Lip G |
| **Clearance** | `clearance` (PlasticRuleValue) | length expression | 0.1 mm (G) | "clearance used for plastic features": lip/groove, snap-fit and boss clearances | A-api (field), mapping G |
| *Design Advice group* | | | | | |
| **Thickness Range**: minimum | `minimumThickness` | length (float, cm in API) | 1.0 mm | Lower bound used by Design Advice | A-api, A-BLOG-MANAGE |
| **Thickness Range**: maximum | `maximumThickness` | length | 4.0 mm | Upper bound used by Design Advice | A-api |
| **Thickness Variation** | `thicknessVariation` (PlasticRuleValue) | blog: a **percentage** ("maximum percentage variation of thickness allowed"); API: a length-unit value | 25 % (G) | Design Advice flags walls whose thickness varies more than this | A-BLOG-MANAGE vs A-api (conflict, section 5) |
| **Minimum Draft Angle** | `minimumDraftAngle` | angle (float, radians in API) | 0.5° | Design Advice flags faces with less draft | A-api, A-BLOG-MANAGE |
| **Knife Edge Threshold** | `knifeEdgeThreshold` (PlasticRuleValue) | length expression | `Thickness / 4` (G) | "minimal thickness where an edge is considered a knife edge"; Design Advice flags thinner wedges | A-api, A-RULES |

**Expression rules (A-api `PlasticRuleValue`).**
- Every PlasticRuleValue holds an **expression string** and a value.
- The expression may reference **`Thickness`** (the same rule's thickness) and may carry units, e.g. `Thickness / 2 + 1 mm`.
- A bare number takes the rule's units: `3` means 3 mm in a mm rule and 3 in in an inch rule.
- Setting the value as a number generates an equivalent expression.
- Angles: typed in degrees, stored in radians.
- G: allow only `Thickness` and constants (no document parameters), so that library rules stay self-contained.

**Validation (A-api + G).**
- Name must be unique (A).
- Thickness must be within [min, max] (A).
- min < max (G); all lengths > 0 (G); draft 0–30° (G); min draft ≤ draft (G warning only).

**Delete rules (A-api).**
- You cannot delete the library rule that is the default.
- You cannot delete a design rule that a component uses (`isUsed`).

**What editing a rule does (A + G).**
- Editing a **design** rule recomputes every component using it, and every rule-linked feature input changes
  (A-AU22-TIPS).
- Editing a **library** rule does not touch designs that hold a copy (G). SciForge offers "Update from library" on the
  design copy (G).

### 2.3 Boss (CREATE)

**Purpose.** "Creates a boss feature to fasten two solid bodies together and reinforce thin areas of a design" (A-BOSS).
A boss is a **screw-boss connection**:

- **Side 1** is the side "where the screw head engages the boss".
- **Side 2** is the side "where the screw thread engages the part or metal insert" (A-api).
- Each side becomes geometry joined into its own participant body.
- An optional **fastener** (screw) can be created as a component.

**Workflow (A-BOSS, paraphrased).**
1. Plastic > Create > Boss.
2. Select **sketch points**. A preview shows for each point.
3. Optionally **Flip** to swap Side 1 and Side 2.
4. Set **Offset Position** from the sketch plane.
5. Fastener section.
6. Side 1 settings.
7. Side 2 settings.
8. Ribs tab.
9. OK.

Tips (A-BOSS):
- Save before creating a boss.
- Put the sketch on a **parting plane between the two bodies**, with one point at each boss centre.
- Assign a plastic rule first, so the boss inherits dimensions.

**Placement and orientation rules (A-api `BossFeatureInput`).**
- Position = one or many **sketch points**, all from the **same sketch** (`setPositionBySketchPoints`).
- Orientation comes from the sketch normal (sketch Z):
  - **Side 1 direction = +Z of the sketch.**
  - **Side 2 direction = −Z.**
  - The "natural direction (direction of the screw)" is **opposite** the sketch normal, i.e. the screw goes from Side 1
    toward Side 2.
- `isDefaultDirection = false` (UI **Flip**) reverses the direction, which swaps which body gets head side and which
  gets thread side.
- **Participant bodies.** Solid bodies only. If none are given, Fusion auto-detects the **closest visible body** that the
  direction ray hits at each point, one per side. If several bodies intersect, only the closest is used. A given body that
  the ray does not hit is ignored.
- `offset` = "offset of the parting face from the selected position point" (UI **Offset Position**; A-BOSS).
- Rib angular reference = sketch **X axis** (`ribRotation` measured from it).
- `creationOccurrence` sets the assembly context.

**Dialog: SciForge layout.** Tabs follow Fusion's sections. A confirms a "Fastener section" and a "Ribs tab"; the rest
of the tab split is G.

Tab **Boss** (placement + both sides):

| Input | Type / choices | Default | What it does | Src |
|---|---|---|---|---|
| Points | sketch point selection (multi; same sketch) | none (required) | One boss connection per point | A |
| Flip | toggle button | off | Swaps Side 1 / Side 2 directions | A-BOSS, A-api `isDefaultDirection` |
| Offset Position | length | 0 | Moves the parting face along the sketch normal from the point | A-BOSS, A-api `offset` |
| Side 1 body | body selection | auto (closest along +Z) | Head-side participant | A-api `participantBodies` |
| Side 2 body | body selection | auto (closest along −Z) | Thread-side participant | A-api |

Per side (Side 1 group, Side 2 group, same fields; A-api `BossFeatureSideInput`, UI names A-BOSS where known):

| Input | API | Type / choices | Default (SciForge) | What it does | Src |
|---|---|---|---|---|---|
| Side enabled | (side1/side2 set or not) | checkbox | both on | A one-sided boss is allowed (only one body) | G (API sides are independent) |
| Shape | `BossShapeTypes` | **Blank** (no hole) / **Constant Diameter** / **Constant Thickness** | Constant Diameter | Blank = solid pin. Constant Diameter = OD set directly. Constant Thickness = OD follows hole + 2×rule Thickness | A-api (enum), UI labels G |
| Hole Type | `HoleTypes` via `setSimple/setCounterbore/setCountersink` | **Simple / Counterbore / Countersink** | Side 1: Counterbore; Side 2: Simple | Hole form for this side | A-BOSS, A-api |
| Hole Extent | `BossHoleExtentTypes` | **Through** / **Blind Full** / **Blind Depth** (UI: **Through Body / From Bottom / From Top**) | Side 1: Through (**forced**); Side 2: From Bottom | Through = through the boss and the body wall. From Bottom = depth measured from the farthest face (leaves a floor). From Top = depth from the hole's start face | A-api ("For top side only through hole extent is accepted"), A-BOSS (UI names) |
| Step Type (alignment) | `BossAlignmentTypes` | **None (Flat) / In (StepIn) / Out (StepOut)** | Side 1: In, Side 2: Flat (mate fits into the recess) | Locating step on the tip face so the two halves align | A-BOSS ("Step Type… In, Out"), A-api |
| Offset Clearance | `offsetClearance` | length ≥ 0 | rule Clearance / 2 (G) | "additional small offset from the selected parting plane": pulls this side's tip back from the parting face | A-api |
| Diameter (outer) | `diameter` | length | 2.5 × screw diameter (G) | Shank outer diameter at the tip | A-api |
| Draft Angle (shank) | `draftAngle` | angle | rule Draft Angle | Outer wall draft; widens toward the root | A-api, rule link A-api `taperAngle` |
| Hole Diameter | `holeDiameter` | length | Side 1: screw clearance (d + 0.4 mm, G); Side 2: pilot 0.8·d (G) | Minor/through hole diameter | A-api |
| Hole Draft Angle | `holeDraftAngle` | angle | 0.5° (G; API sample 1°) | Draft of the hole wall | A-api |
| Hole Depth | `holeDepth` | length | 2·d (G) | Meaning depends on Hole Extent (ignored for Through) | A-api |
| Major Diameter | `holeMajorDiameter` | length | head Ø + 0.5 mm (G) | Counterbore/countersink diameter | A-api |
| Major Depth | `holeMajorDepth` | length | head height (G) | "either the counterbore depth or thickness of the material under the screw head", depending on the side's hole orientation | A-api |
| Major Draft Angle | `holeMajorDraftAngle` | angle | rule Draft | Draft of the counterbore wall | A-api |
| Countersink Angle | `holeCountersinkAngle` | angle | **90°** | Countersink included angle | A-api ("If not specified it is set to 90 deg") |
| Alignment Diameter | `alignmentDiameter` | length | mating side OD + 2·clearance (G) | Step diameter | A-api |
| Alignment Depth | `alignmentDepth` | length | 1 mm (G; sample 1 mm) | Step height/depth | A-api |
| Alignment Draft Angle | `alignmentDraftAngle` | angle | rule Draft | Step wall draft | A-api |
| Root Radius | `rootRadius` | length | rule Nominal Radius | Blend where the shank meets the participant body | A-api |
| Tip Radius | `tipRadius` | length | 0.25 × T (G) | Blend at the shank top (parting) face | A-api |
| Alignment Tip / Root Radius | `alignmentTipRadius`, `alignmentRootRadius` | length | 0 | Blends of the step | A-api |
| Hole Start / End Radius | `holeStartRadius`, `holeEndRadius` | length | 0 | Blend at the hole mouth / hole bottom | A-api |
| Major Tip / Root Radius | `holeMajorTipRadius`, `holeMajorRootRadius` | length | 0 | Blends of the counterbore | A-api |

Tab **Ribs**. Per side: a checkbox **Side 1** and a checkbox **Side 2** (A-BOSS: "Check Side 2 to add ribs on the other side").

| Input (UI) | API | Type / choices | Default (SciForge) | What it does | Src |
|---|---|---|---|---|---|
| Side 1 / Side 2 | (ribCount > 0) | checkbox | off | Adds ribs (gussets) around that side's shank | A-BOSS, A-BLOG-SNAPBOSS |
| Quantity | `ribCount` | integer ≥ 1 | 4 | Number of ribs | A-BOSS, A-api |
| Total Angle | `ribTotalAngle` | angle (0, 360] | **360°** | Angular span the ribs are spread over | A-api ("Default is 360 deg"), A-BOSS |
| Rotation Angle | `ribRotation` | angle | 0° | Angle of the first rib from the sketch X axis | A-api, A-BOSS |
| Profile | `ribType` = `BossRibShapeTypes` | **None / Chamfer / Fillet** | Chamfer | Shape of the rib's top-outer corner (chamfer = angular, fillet = rounded) | A-api, A-BOSS |
| Cut Size | `ribCutSize` | length | 0.5 × rib height (G) | Size of the chamfer/fillet cut | A-api |
| Chamfer Angle | `ribChamferAngle` | angle | 60° (API sample) | Only for chamfer profile | A-api |
| Thickness | `ribThickness` | length | 0.6 × rule Thickness (G) | Rib thickness, "measured perpendicular to the outer face of the boss" | A-BOSS, A-api |
| Draft Angle | `ribDraftAngle` | angle | rule Draft | Draft on the rib side faces (taper of the thickness) | A-BOSS, A-api |
| Outer Draft Angle | `ribOuterDraftAngle` | angle | 0° (sample 10°) | Draft on the rib's outer end face | A-api |
| Rib Length | `ribLength` | length | OD/2 + 2·T (G) | Rib reach "measured from the shank axis" | A-api, A-BOSS |
| Step Offset | `ribOffset` | length | 1 mm (G) | Rib top is lowered this much "from the top face or alignment face" | A-api, A-BOSS ("Rib Length or Step Offset") |
| Outer Fillet Radius | `ribTipRadius` | length | 0 | "fillet along the outer edge of the ribs where they meet Side 1" | A-BOSS, A-api |
| Base Fillet Radius | `ribRootRadius` (`ribBlendRadius` on the feature) | length | rule Nominal Radius | Fillet at the rib base | A-BOSS, A-api |
| Per-rib extent | `setRibExtent(point, [BossRibExtentTypes])` | per rib: **By Length / To Next / Suppressed** | By Length | Each rib individually: fixed length, run to the next wall, or removed. Set per point | A-api, BossFeatureSample |

Blog (A-BLOG-SNAPBOSS): rib values "automatically populate based on your material selection", and the preview lets you
check interference.

Fastener section (A-BOSS; the values are descriptive metadata plus optional geometry):

| Input | Type / choices | Default | What it does | Src |
|---|---|---|---|---|
| Create Component | checkbox | off | Creates an (external) component holding the screw geometry, referenced into the design at each boss | A-BOSS |
| Head Type | Pan, Round, Round Washer, Flat, Oval, Hex, Hex Washer | Pan (G) | Screw head shape | A-BOSS |
| Drive Type | Phillips, Pozidriv, Torx Plus, Security Torx Plus, Slotted, Hex, None, plus slotted combinations (Slotted Phillips, Slotted Pozidriv, Slotted Torx Plus) | Phillips (G) | Recess shape | A-BOSS |
| Thread Form | Metric Forming Fine, Metric Forming Coarse, Inch Forming Fine, Inch Forming Coarse | Metric Forming Coarse (G) | Thread-forming screw for plastics | A-BOSS |
| Thread Angle | angle | 30° (G: typical plastic-forming screw) | Flank angle | A-BOSS (field), default G |
| Thread Diameter | length | 3 mm (G) | Nominal screw diameter d. Drives the hole defaults | A-BOSS, defaults G |
| Length | length | auto = boss stack length (G) | Screw length | A-BOSS |
| Fastener Material | text | empty | Text-only property | A-BOSS ("text-only properties") |
| Surface Finish | text (or pick from a "More" menu) | empty | Text-only property | A-BOSS |

Rule linkage (A-api `BossFeature`):
- `thickness` and `taperAngle` are "plastic part rule reference" parameters.
- `innerRadius`, `screwDiameter`, `screwHeadDiameter`, `screwHeadAngle` are parameters exposed "for parametric
  expressions".
- So in the parameters table, boss values can be written as expressions of screw size and rule values.

**Handles / preview (G).**
- Live preview of both sides at every point, coloured per body.
- An arrow handle on the first point for Offset Position and Flip.
- A rotation handle for Rotation Angle in the Ribs tab.
- Points without a body hit along a direction get a warning glyph, and that side is skipped.

**Browser / timeline (A-api + G).**
- `BossFeatures.add` returns **a list of BossFeature objects**. Each instance represents one side
  (`isGeometryOpposite` = true for the thread side).
- SciForge: one timeline node "Boss" per command, holding the per-side results; editing either side reopens the shared
  dialog (G).
- Geometry is **joined** into the participant bodies. No new body is created, apart from the optional fastener component
  (A-api "Boss feature works with solid bodies only"; G).
- Model parameters: one per field listed above (A-api: each is a `ModelParameter`).

**Errors (G).**
- No sketch point: OK disabled.
- Points from different sketches: refused (A-api "all must belong to the same sketch").
- No solid body hit on either side: "No body found for this boss point".
- Hole Ø ≥ OD, or Major Ø ≤ Hole Ø: refused with a field highlight.
- Side 1 extent ≠ Through: forced to Through (A-api).
- Rib count < 1 or Total Angle ≤ 0: refused.
- Boolean failure: feature in error state; the timeline node turns red.

### 2.4 Snap Fit (CREATE)

**Purpose.** "Creates a cantilever snap fit feature to fasten two solid bodies together" (A-SNAP). You pick a type, pick
sketch points between the two bodies, then set the hook / groove / loop on each side (A-AU22-TIPS).

**Types (A-SNAP, F-MANMACHINE).**
1. **Parallel Hook and Groove**: hook on one body, groove (catch window/ledge) on the other. Hook section, then a
   **Groove** section to enable and size the groove.
2. **Perpendicular Hook and Groove**: same pair in the perpendicular orientation. The groove side is enabled from the
   **Hook Undercut** section ("check Groove to create the groove side").
3. **Hook and Loop**: hook on one body, a **loop** (a frame the hook catches) on the other. A **Loop** section sets the
   loop body and dimensions, and a **Hook** checkbox in the Hook section creates the hook side.

Meaning of parallel/perpendicular (G, not confirmed):
- **Parallel** = the hook's catch acts along a direction parallel to the sketch (parting) plane, catching on a ledge in
  the other body's side wall. This is the classic box-and-lid snap.
- **Perpendicular** = the hook beam lies parallel to the parting plane, and the catch engages an undercut normal to it.
- See section 5.

**Placement (A).**
- Hook side is placed at **sketch points** (A-SNAP). Best practice: sketch on the parting plane between the two bodies
  (A-SNAP tip).
- **Selection Mode** (A-JUL22):
  - **Automatic** (default): takes all visible sketch points and places many snap fits at once.
  - **Manual**: you pick points one by one.
- **Rotation Type** (A-JUL22, A-SNAP):
  - **Uniform**: every snap fit gets one angle.
  - **Independent**: each snap fit gets its own rotation manipulator.
  - **Aligned**: all snap fits align to a picked plane, line or point.
  - Aligned (G): each hook's catch faces toward/away from the reference, so hooks round a box all face outward.

**Dialog.** Confirmed rows are A. The dimension rows are G: modelled on a standard cantilever and on Autodesk Inventor's
Snap Fit fields (A-inv-SNAP). Exact Fusion labels are unconfirmed.

| Input | Type / choices | Default | What it does | Src |
|---|---|---|---|---|
| Type | Parallel Hook and Groove / Perpendicular Hook and Groove / Hook and Loop | Parallel Hook and Groove (G) | Feature family | A |
| Selection Mode | Automatic / Manual | Automatic | See above | A-JUL22 |
| Points | sketch points | (auto: all visible points of the picked sketch) | One snap fit per point | A |
| Rotation Type | Uniform / Independent / Aligned | Uniform (G) | Orientation control | A |
| Rotation Angle | angle (per snap in Independent) | 0° from sketch X (G) | Turns the hook about the sketch normal | A (concept), reference axis G |
| Align To | plane / line / point | none | Used by Aligned | A-JUL22 |
| Flip | toggle | off | Swaps which body is hook / groove side (G) | G |
| **Hook section** | | | | |
| Hook | checkbox | on | Create the hook side | A-SNAP (Hook and Loop) |
| Hook Body | body selection | auto (closest along the hook direction) | Body that receives the hook | A ("hook section sets the hook body") |
| Extent Type | **To Next** / **Distance** | To Next | To Next: the hook base is extruded "from the sketch plane to the nearest faces on a solid body". Distance: base extruded a given distance | A-SNAP |
| Extent Distance | length | 5 mm (G) | For Distance | A (type), default G |
| Beam Length L | length | 6 × T (G) | Free length of the flexing arm, from its root to the catch | G (A-inv: "Beam Length") |
| Beam Width w | length | 3 × T (G) | Arm width | G (A-inv: "Beam Width at the Wall") |
| Beam Thickness at root t₀ | length | rule Thickness | Arm thickness where it meets the wall | G + F-MANMACHINE (rule Thickness picked up) |
| Beam Thickness at catch t₁ | length | = t₀ (G; optional taper t₁ = t₀/2 halves the strain) | Tapered arm | G (A-inv "Beam Thickness at the Hook") |
| Catch Depth (undercut) y | length | 0.5 × T (G) | How far the catch protrudes (= required deflection) | G (A-inv "Hook Undercut Depth") |
| Catch Length (tip length) | length | 1.5 × y (G) | Length of the catch along the beam | G (A-inv "Hook Tip Length") |
| Insertion Angle α_in | angle | 30° (G) | Lead-in face angle (low = easy to insert) | G (A-inv "Hook Insertion Face Angle") |
| Retention Angle α_ret | angle | 90° (G; < 90° makes it releasable) | Back face angle (90° = permanent) | G (A-inv "Hook Retention Face Angle") |
| Draft Angle | angle | rule Draft Angle | Draft on the hook side faces | A (rule draft picked up, F-MANMACHINE) |
| Base Fillet Radius | length | rule Nominal Radius | Fillet at the hook's base (root) | A-SNAP ("base fillet radius… at the hook's base") |
| **Groove section** (Parallel) / **Hook Undercut** section (Perpendicular) | | | | |
| Groove | checkbox | on | Create the mating groove side | A-SNAP |
| Groove Body | body selection | auto (closest body on the other side of the parting plane) | Body that gets the groove | A ("assigned to a body") |
| Groove Extent | To Next / Distance | To Next | Like the hook extent | G (mirrors hook; A mentions extents generically) |
| Clearance | length | rule Clearance | Gap between catch and groove on every mating face; groove = catch + clearance | G (A field `clearance` "used for plastic features"; F-MANMACHINE "clearance") |
| Groove Wall Thickness | length | rule Thickness | Wall around the groove pocket | G |
| **Loop section** (Hook and Loop) | | | | |
| Loop | checkbox | on | Create the loop side | A-SNAP (implied) |
| Loop Body | body selection | auto | Body that receives the loop | A-SNAP |
| Loop Length / Width / Thickness / Opening Length | lengths | Length = L + catch length; Width = w + 2·T + 2·clearance; Thickness = T; Opening = catch length + 2·clearance (G) | Frame the catch snaps behind | G (A-inv: "Clip Length, Clip Width, Beam thickness, Catch Opening Length") |

**Handles / preview (A + G).**
- Preview at every point (G).
- In Independent rotation, each snap fit has its **own rotation manipulator** (A-JUL22).
- An extent arrow handle (G).

**Browser / timeline (G).**
- One timeline feature "Snap Fit" per command.
- Hook geometry is joined into the hook body; the groove is joined/cut into the groove body. No new bodies.
- Every dimension is a model parameter, linked to the rule where defaulted.
- A-BLOG-SNAPBOSS mentions **visibility controls** in Snap Fit: G reading is "show/hide the other body while editing so
  the hook is visible".

**Errors (G).**
- No hook body hit: skip the point with a warning glyph.
- Beam longer than the available distance to the parting plane: warning.
- Groove body cannot be found: create the hook only, with a warning.
- Optional strain check (section 4.3): yellow warning if ε > material allowable. This is a SciForge addition (Fusion
  does stress via Simulation).

### 2.5 Lip (CREATE): Lip / Groove / Lip And Groove

**Purpose.**
- Make a raised **lip**, a recessed **groove**, or a matched **lip and groove** along the parting edge of an enclosure,
  so the two halves locate and seal, and a **reveal** (shadow line) is visible on the outside (A-LIP, A-MAY23).
- Introduced May 2023 (A-MAY23).
- Autodesk: the feature "automates modeling of Lip, Groove, or combined… parameters with plastic rules, allowing for
  editable dimensions" (A-X-LIP).

**Selection and rules (A-LIP).**
- Select **one or more tangent edges** on a solid body. They define the path.
- **Select the inside edge** of the shell rim so the **reveal is on the outside** (tip).
- For **Lip And Groove**: the two bodies must be **touching**, so the edges line up, and the faces must be normal to each
  other (tip).
- **Assign a Plastic Rule first** (tip).
- **Groove dimensions are automatically determined by the lip dimensions and the clearance** (Lip And Groove).
- Fine-tune dimensions on the **Advanced** tab.

| Input | Type / choices | Default | What it does | Src |
|---|---|---|---|---|
| Type | **Lip** / **Groove** / **Lip And Groove** | Lip And Groove (G) | Lip = raised lip on one body. Groove = recessed groove on one body. Lip And Groove = lip on one body and the matching groove on the touching body | A-LIP |
| Edges | edge chain (tangent-continuous) | none | Path of the lip/groove | A-LIP |
| Guide Type | **Face Guide** / **Pull Direction** | Face Guide (G) | Face Guide: pick a face on either side of the selected edge; the cross-section is located relative to that face (constant angle along the path). Pull Direction: pick a plane or face; the cross-section is swept along a fixed direction. Edges must be tangent-continuous | A-LIP; "constant angle" A-inv-LIP |
| Guide Face / Direction | face or plane selection | auto: the wall face adjacent to the edge (G) | Reference for the section | A-LIP |
| Flip | toggle | off | Swap which side of the edge the profile sits (inside/outside) | G |
| Lip Body / Groove Body | body selections | auto (edge owner = lip body; touching body = groove body) | Which body gets which | G (A: "pair of solid bodies") |
| **Advanced tab** | | | | A-LIP ("adjust the feature dimensions") |
| Lip Width (thickness) | length | `Thickness / 2` (rule) | Lip wall thickness, measured from the selected edge into the wall | G (A-inv: "lip thickness") |
| Lip Height | length | rule **Reveal Height** | Height the lip stands above the parting face | G (A-api `revealHeight`; A-inv "lip height") |
| Lip Inner Draft / Outer Draft | angle | rule Draft Angle | Draft on the lip's two side faces | G (A-inv "lip draft angles") |
| Shoulder (reveal) Width | length | wall − lip width (derived) | Width of the step left on the outer half of the rim | G (A-inv "shoulder width") |
| Clearance | length | rule **Clearance** | Groove = lip + clearance, on the side walls and the bottom | A (groove from lip + clearance), default G |
| Clearance Height (vertical) | length | = Clearance | Extra groove depth beyond the lip height | G (A-inv "clearance height") |
| Groove Width / Depth (Groove-only type) | length | Width = T/2 + clearance; Depth = Reveal Height + clearance | Used when Type = Groove (no lip to derive from) | G |
| Tip / Root Radius | length | 0 / rule Nominal Radius | Edge blends | G |

**Handles / preview (G).**
- Preview of lip (join colour) and groove (cut colour).
- Distance arrow handle for Lip Height.
- Side handle for Lip Width.

**Browser / timeline (G).**
- One timeline node "Lip".
- It modifies one or two bodies (join on the lip body, cut on the groove body).
- Parameters linked to the rule.

**Errors (G; tangent rule A).**
- Edges not tangent-continuous with Pull Direction: refused (A-LIP).
- Lip And Groove with non-touching bodies: "Bodies must touch along the selected edges".
- Lip width ≥ wall thickness: refused.
- Self-intersection at tight corners: feature error.

### 2.6 Rest (CREATE)

**Purpose.**
- "Creates a rest feature that intersects the overall solid body and forms a flat area that can be used for other
  features or placement of other components" (A-SKETCHSOLIDS).
- It is a flat landing (pad or pocket) on a curved plastic wall, e.g. for a label, a switch or a PCB standoff.
- Added July 2022 (A-JUL22: "grab a sketch profile and use it to create a flat face, in relation to the curved surface of
  your existing body. The command will then … cut away or add material depending on the thickness you require").

**Selection (A).** A **closed sketch profile** and a **solid body**, then a **thickness**.

| Input | Type / choices | Default | What it does | Src |
|---|---|---|---|---|
| Profile | closed sketch profile(s) | none | Outline of the flat area; the flat face lies in the sketch plane (G) | A |
| Body | solid body | auto: body the profile projects onto (G) | Body to modify | A |
| Thickness | length | rule Thickness | Wall thickness of the landing (flat plate and its side walls) | A (thickness), default G |
| Direction / Flip | toggle | toward the body interior (G) | Which side of the sketch plane is "inside" | G |
| Draft Angle | angle | rule Draft Angle | Draft of the rest's side walls | A-JUL22 ("can also adjust draft-type angles"), default G |
| Clearance (optional) | length | 0 | Gap around a part that will sit on the rest | G (Inventor's Rest has it; A-inv not fetched) |

**Behaviour.**
- The result is always a flat face of the given profile at the sketch plane, backed by a wall of the given thickness.
- Where the body bulges past the plane, material is removed. Where the body lies below the plane, material is added
  (A-JUL22).
- Geometry recipe: section 4.5 (G).

**Browser / timeline (G).** One node "Rest". It modifies the body. Parameters linked to the rule.

**Errors (G).**
- Open profile: refused.
- Profile does not project onto the body: "Profile does not intersect the body".
- Thickness ≤ 0: refused.

### 2.7 Rib (CREATE; plastic-aware)

The rib exists on the SOLID tab. On the PLASTIC tab it additionally gets draft (Design Extension) and rule defaults
(A-RIB, A-RULES).

| Input | Type / choices | Default | What it does | Src |
|---|---|---|---|---|
| Profile | open sketch curve(s) | none | Rib centreline | A-RIB |
| Thickness Direction | **Symmetric** / **One Side** | Symmetric | Half thickness each side vs. full thickness on one side | A-RIB |
| Thickness | length | rule Thickness × 0.6 (G; Fusion may use rule Thickness directly) | Rib thickness | A (rule used), factor G |
| Start | **From Top** / **From Bottom** | From Bottom (A-api: Web default measures from bottom) | Where the thickness is measured when draft makes it vary | A-RIB, A-api `isThicknessFromTop` |
| Extent Type | **To Next** / **Distance** | To Next | To Next: from the profile to the nearest faces. Distance: a set depth | A-RIB |
| Depth | length | 10 mm (G) | For Distance: "distance to extrude the rib, parallel to the sketch plane, toward the nearest faces" | A-RIB |
| Draft Angle | angle | rule Draft Angle | Taper of the rib sides (Design Extension step). 0 removes the draft (A-APIWN) | A-RIB, A-APIWN |
| Draft Pull Direction | plane or face | sketch plane (G) | Pull direction for the draft; **Flip Pull Direction** reverses it | A-RIB |

### 2.8 Web (CREATE; plastic-aware)

| Input | Type / choices | Default | What it does | Src |
|---|---|---|---|---|
| Profile | open sketch profile(s) | none | Network of thin walls, "extruded perpendicular to the sketch plane, to the nearest faces" | A-WEB |
| Thickness Direction | Symmetric / One Side | Symmetric | As Rib | A-WEB |
| Thickness | length | rule Thickness × 0.6 (G) | Wall thickness | A (rule), factor G |
| Start | Bottom / Top | Bottom | Where thickness is measured when drafted. Setting From Top needs the plastic capability | A-WEB, A-api ("Setting this property requires the Plastic Design Tools capability") |
| Extent Type | To Next / Distance (+ Depth) | To Next | As Rib | A-WEB |
| Draft Angle | angle | rule Draft Angle | Extension step | A-WEB |
| Draft Pull Direction | plane/face (+ flip) | sketch plane | As Rib (G for Web) | A-RIB analogue |
| Fillet Radius | length | rule Nominal Radius | Fillet at the web base (extension step) | A-WEB |

### 2.9 Extrude / Shell / Thicken / Draft / Emboss on the PLASTIC tab

These are the SOLID dialogs unchanged, **except** that the inputs in the table in section 1.3 open with rule-linked
expressions (A for "uses rule", G for exact field).

- In the dialog, the linked value shows the rule name, e.g. `2 mm (ABS rule)`. Typing a number breaks the link for that
  field only (G).
- A small "reset to rule" button restores the link (G).

### 2.10 Rule Fillet (MODIFY)

**Purpose.**
- Fillet by **rule**, not by picked edges. Pick faces or features, and the command fillets all their edges, or only the
  edges between two groups.
- The rule is re-evaluated on every recompute, so edges that appear later still get filleted (A-api semantics; G
  wording).
- In the API it is a `FilletFeature` of type `RuleFilletFeatureType` (A-api; API introduced Nov 2025).

| Input | API | Type / choices | Default | What it does | Src |
|---|---|---|---|---|---|
| Rule | `RuleFilletRuleTypes` | **All Edges** / **Between Faces/Features** | All Edges | All Edges: every edge of the selected faces/features. Between: only edges shared by set 1 and set 2 | A-api |
| Faces/Features | `facesOrFeatures` | faces and/or timeline features | none | Input for All Edges. Picking a *feature* (e.g. a Boss) means "all faces that feature made" | A-api |
| Set 1 / Set 2 | `facesOrFeaturesOne/Two` | faces and/or features | none | Inputs for Between | A-api |
| Radius Type | `isConstantRadius` | **Constant** / **Asymmetric** | Constant | Asymmetric uses two offsets | A-api |
| Radius | `radius` | length | rule Nominal Radius (G) | Constant radius | A-api |
| Offset 1 / Offset 2 | `asymmetricOffsetOne/Two` | length | = radius | Asymmetric distances | A-api |
| Topology | `RuleFilletTopologyTypes` | **Rounds and Fillets** / **Rounds Only** / **Fillets Only** | Rounds and Fillets | Rounds = convex edges (material removed). Fillets = concave edges (material added) | A-api (enum); round/fillet meaning G (standard CAD usage) |
| Corner Type | `isRollingBallCorner` | **Rolling Ball** / **Setback** | Rolling Ball (G) | Corner blend solution where several edges meet | A-api |

**Browser/timeline.** One Fillet node marked as a rule fillet (A-api). Errors are as for Fillet (G).

### 2.11 Design Advice (INSPECT; rule-driven manufacturability check)

**Facts (A).**
- Uses "the Plastic Rule assigned to the component that contains the solid body" (A-DA).
- Alerts cover **thickness**, flagged when regions fall outside the **Thickness Range** or exceed the **Thickness
  Variation**, and **draft** (A-DA).
- Also checks **knife edges** and **undercuts** (A-AU22-TIPS: "potential issues with face draft, wall thickness, knife
  edges, or undercuts"; A-BLOG-DA).

**SciForge spec (G).**

| Input | Type | Default | What it does |
|---|---|---|---|
| Bodies | solid bodies (multi) | all visible bodies in components with a rule | Bodies to analyse |
| Pull Direction | plane/face/axis | Z of the component | Mould opening direction for draft and undercut |
| Checks | checkboxes: Thickness, Thickness Variation, Draft, Knife Edges, Undercuts | all on | Which checks run |
| Rule | read-only | component rule | Thresholds come from the rule |

**Output (G).**
- A colour overlay: thickness heat map; faces failing a check in a warning colour.
- An issues list (check, body, face count, worst value) with click-to-zoom.
- An alert badge on the component in the browser.
- Not a timeline feature. It re-runs on recompute while shown (G).

### 2.12 Draft Analysis / Accessibility Analysis / Minimum Radius Analysis (INSPECT)

- All three exist as analyses listed under the browser's Analysis folder (A-api; API Jan 2023).
- Draft Analysis has a **pull-direction entity** (A-APIWN Oct 2026: `DraftAnalysis.directionEntity`) and a colour band
  between ± limits. One excerpt mentions limits within −15°…+15° (A-APIWN excerpt; unverified).
- Accessibility (G): colours faces visible from the pull direction (accessible to a straight-pull mould half) versus
  hidden faces (undercuts).
- Minimum Radius (G): colours faces whose minimum curvature radius is below a threshold (default = rule Nominal Radius /
  2).
- These are shared with the SOLID tab. SciForge may already provide some. The plastic tab only adds rule-based defaults
  (G).

### 2.13 Simulation (out of scope)

Injection-moulding / mould-fill simulation and snap-deflection stress studies run in Fusion's Simulation workspace
(A-AU22-SWAIN). **Not implemented in SciForge.** Only the optional analytic snap-fit strain check (section 4.3) is
proposed.

---

## 3. Rules / data model

### 3.1 PlasticRule (A-api, exact)

| Field | API type | Units (API) | Used by | Notes |
|---|---|---|---|---|
| name | str | n/a | dialog lists | unique per design/library |
| units | str "mm" or "in" | n/a | display | fixed at creation |
| material | Material | n/a | component physical material | |
| thickness | PlasticRuleValue | cm / expression | Extrude, Rib, Web, Boss, Snap Fit, Emboss, Thicken, Shell, Lip, Rest | must be within min..max |
| draftAngle | PlasticRuleValue | rad / expression in deg | Draft, Rib, Web, Boss, Snap Fit, Rest, Lip, Extrude taper | |
| nominalRadius | PlasticRuleValue | cm | Fillet, Rule Fillet, Web base fillet, Boss root, Snap base fillet | |
| revealHeight | PlasticRuleValue | cm | Lip (reveal / lip height) | Jan 2024 API |
| clearance | PlasticRuleValue | cm | Lip/groove, Snap Fit, Boss | Jan 2024 API |
| minimumThickness | float | cm | Design Advice | "Thickness Range" low |
| maximumThickness | float | cm | Design Advice | "Thickness Range" high |
| thicknessVariation | PlasticRuleValue | cm per API; **% per blog** | Design Advice | conflict, section 5 |
| minimumDraftAngle | float | rad | Design Advice | |
| knifeEdgeThreshold | PlasticRuleValue | cm | Design Advice | |
| isDefault | bool | n/a | library only | Set As Default |
| isUsed | bool | n/a | design only | blocks delete |
| parentDesign | Design / null | n/a | n/a | null = library rule |

Collections: `Design.designPlasticRules`, `Design.libraryPlasticRules`, `PlasticRules.addByCopy(rule, name)`,
`itemByName` (name as shown in the Plastic Rules dialog) (A-api).

**API gap worth copying (A-api).** `Component.activeSheetMetalRule` exists, but there is **no**
`Component.activePlasticRule` property in the API. Assignment is UI- and configuration-table-driven. SciForge should
still store it as a component property (G).

### 3.2 SciForge storage proposal (G)

- **Library**: a JSON file in the user config dir (e.g. `SciForge/plastic_rules.json`), seeded from the bundled default
  library. One rule has `isDefault: true`.
- **Design rules**: a hidden document object `PlasticRules` (FeaturePython) holding the rule list. Each rule has name,
  units, material and expression strings.
- **Assignment**: an App::Part (component) property `PlasticRule` (string = design rule name).
- **Linking**: a consuming feature stores, for each rule-defaulted input, the rule field it is linked to (e.g.
  `{"Thickness": "thickness"}`). On recompute, a linked input re-reads the component's rule. Typing a number clears the
  link. Equivalent: bind through FreeCAD expressions to a spreadsheet-like rule object (e.g.
  `PlasticRules.ABS_2mm_thickness`), so FreeCAD's dependency graph does the update.
- Expression evaluation: substitute `Thickness`, then evaluate with units; a unitless number takes the rule's units
  (A-api semantics).

### 3.3 SciForge default library (G: SciForge's own data, not Fusion's)

Values are typical injection-moulding guidance, chosen as starting points.
- Nominal Radius = `Thickness / 2`
- Knife Edge Threshold = `Thickness / 4`
- Reveal Height = `Thickness / 2`
- Clearance = 0.1 mm (0.004 in), unless listed
- Thickness Variation = 25 %

| Rule name (SciForge) | Material | Thickness | Range min–max | Draft | Min draft | Notes |
|---|---|---|---|---|---|---|
| Default (mm) | ABS | 2.0 mm | 1.0–4.0 mm | 1.0° | 0.5° | default rule |
| Default (in) | ABS | 0.080 in | 0.040–0.160 in | 1.0° | 0.5° | inch rule |
| ABS 2 mm | ABS | 2.0 | 1.2–3.5 | 1.0° | 0.5° | |
| ABS 1.5 mm | ABS | 1.5 | 1.2–3.5 | 1.0° | 0.5° | |
| PC 2 mm | Polycarbonate | 2.0 | 1.0–3.8 | 1.0° | 0.5° | |
| PC/ABS 2 mm | PC/ABS | 2.0 | 1.0–3.5 | 1.0° | 0.5° | |
| PP 1.5 mm | Polypropylene | 1.5 | 0.8–3.8 | 1.5° | 1.0° | clearance 0.15 mm |
| PA66 1.5 mm | Nylon 6/6 | 1.5 | 0.8–3.0 | 1.0° | 0.5° | |
| POM 1.5 mm | Acetal | 1.5 | 0.8–3.0 | 1.0° | 0.5° | |
| HIPS 2 mm | Polystyrene (HI) | 2.0 | 1.0–3.8 | 1.0° | 0.5° | |
| HDPE 2 mm | Polyethylene HD | 2.0 | 0.8–5.0 | 1.5° | 1.0° | clearance 0.15 mm |
| PBT 1.8 mm | PBT | 1.8 | 0.8–3.0 | 1.0° | 0.5° | |
| PMMA 2.5 mm | Acrylic | 2.5 | 0.8–3.8 | 1.0° | 0.5° | |
| TPE 1.5 mm | TPE | 1.5 | 0.6–3.0 | 2.0° | 1.0° | |
| FDM PLA 2 mm | PLA | 2.0 | 0.8–6.0 | 0.0° | 0.0° | 3D-print rule, clearance 0.3 mm |
| FDM PETG 2 mm | PETG | 2.0 | 0.8–6.0 | 0.0° | 0.0° | 3D-print rule, clearance 0.3 mm |

Allowable strain for the snap-fit check (G, typical published values): ABS 2.5 %, PC 4 %, PC/ABS 3 %, PP 6 %, PA66 4 %
(dry), POM 6 %, HIPS 2 %, HDPE 6 %, PBT 4 %, PMMA 1.5 %, TPE 10 %, PLA 2 %, PETG 3 %.

---

## 4. Maths and geometry rules

Notation:
- T = rule Thickness, α = rule Draft Angle, R = rule Nominal Radius, c = rule Clearance, h_r = rule Reveal Height.
- **n** = sketch normal (unit), **x** = sketch X axis, P = sketch point.

### 4.1 Boss (A-api semantics; construction G)

Parting plane and side directions:
1. Parting point P' = P + offset·**n**. The parting plane Π passes through P' with normal **n** (A-api `offset`).
2. Directions: d₁ = +**n** (Side 1, head side) and d₂ = −**n** (Side 2, thread side). If flipped, swap them (A-api).
3. Participant body for side k = the first solid body hit by the ray P' + s·d_k, s > 0 (closest only). Or use the
   user's pick (A-api).

Per side k:

4. Tip plane: Π_k = Π shifted by offsetClearance_k along d_k (G sign: pulled away from the mate, so the gap between the
   two tips = clearance₁ + clearance₂).
5. Shank: a drafted cylinder (cone frustum) on axis (P', d_k).
   - It starts at Π_k and extends along d_k **until it is fully embedded in the participant body**. Implementation:
     extrude to "to next" plus a margin, then intersect with the body's convex region / trim at the far body face
     (G; matches "root radius = blend of shank and participant body").
   - Radius along the axis: r(s) = D/2 + s·tan(draftAngle), with s ≥ 0 measured from the tip. The shank widens toward
     the root (the mould pulls toward the tip).
   - Constant Thickness shape: D = d_hole + 2T, and the outer draft follows the hole draft so the wall stays T (G).
   - Blank shape: no hole.
6. Union the shank with the body. Apply rootRadius on the shank/body intersection edge and tipRadius on the tip outer
   edge.
7. Alignment step at the tip:
   - **StepOut**: add a frustum of diameter D_a, height h_a, draft α_a beyond Π_k, so the spigot protrudes toward the
     mate.
   - **StepIn**: cut a recess of diameter D_a, depth h_a into the tip.
   - Flat: nothing.
   - Matching rule (API sample): mate's OD ≈ D_a of the StepIn side, or the mate's StepOut D_a ≈ this side's recess
     D_a − 2c (G).
8. Hole (axis = boss axis, drafted by holeDraftAngle, hole widening toward its open end):
   - Side 1 (head): always **Through**. Bore of d_hole from the tip through the boss **and the body wall** to the outside.
     - Counterbore/countersink opens from the **outside face** (screw-head entry).
     - holeMajorDepth = thickness of material **under the head**, measured from the tip (so the head sits deep in a tall
       boss, typical of enclosures) (A-api wording "thickness of the material under the screw head"; geometry G).
   - Side 2 (thread):
     - **Through**: as above.
     - **Blind Depth** ("From Top"): depth measured from the hole start (tip).
     - **Blind Full** ("From Bottom"): the bottom sits holeDepth short of the **farthest face**, i.e. leaves a floor of
       that thickness (A-api).
     - Counterbore/countersink here sits at the tip (thread lead-in / insert pocket); holeMajorDepth = counterbore depth
       (A-api "either the counterbore depth or…").
   - holeStartRadius / holeEndRadius blend the mouth and the bottom.
9. Ribs (per point, per side):
   - Count n, total angle Θ (default 360°), rotation φ₀ from **x**.
   - Angles:
     - If Θ = 360°: φ_i = φ₀ + i·360°/n.
     - Else: φ_i = φ₀ + i·Θ/(n−1) for n ≥ 2 (G: spread inclusive over the span); n = 1 gives φ₀.
   - Rib i is a slab in the plane containing the axis and direction (cos φ_i·**x** + sin φ_i·(**n**×**x**)):
     - thickness t_r (perpendicular to that plane, symmetric);
     - running radially from the shank axis to ribLength (By Length), **or** until it meets the body wall (To Next), or
       absent (Suppressed);
     - axially from the body (root) up to the tip minus ribOffset ("Step Offset").
   - Side faces drafted by ribDraftAngle (thicker at the root). The outer end face is drafted by ribOuterDraftAngle.
   - Top-outer corner shaped by ribType:
     - Chamfer: size ribCutSize at ribChamferAngle.
     - Fillet: radius ribCutSize.
     - None: square.
   - Blends: ribTipRadius (outer edges), ribRootRadius (base edges).
   - Union with the shank and the body.
10. Fastener (optional): a simplified screw solid. Head per Head Type, shank cylinder of Thread Diameter, Length L,
    placed with the head on the Side 1 counterbore floor, axis −d₁. Cosmetic thread only (G).

Default sizing helpers (G, generic plastics guidance), with d = screw diameter:
- thread-side pilot ≈ 0.8·d;
- head-side clearance hole ≈ d + 0.4 mm;
- boss OD ≈ 2.0–2.5·d;
- thread engagement ≈ 2·d;
- boss wall ≈ 0.6·T (avoid sink);
- root radius 0.25–0.5·T;
- rib thickness 0.5–0.6·T;
- rib height ≤ 3·T below the tip.

### 4.2 Snap Fit geometry (G)

Local frame per point:
- origin P (on the parting plane);
- **e_z** = insertion axis = ±**n** (from hook body toward groove body);
- **e_x** = catch direction = rotate **x** by the rotation angle about **n** (Uniform / Independent), or toward the
  Aligned reference;
- **e_y** = **e_z** × **e_x**.

Hook (cantilever + catch):
- Base block: the profile w × (t₀ + margin) at P, extruded from the sketch plane back into the hook body, To Next or
  Distance (A extent semantics).
- Beam: a prism of width w along **e_y**, thickness tapering t₀→t₁ along **e_x**, length L along **e_z**, root at the
  parting plane offset.
- Catch at the free end: a triangular/trapezoidal prism.
  - Protrusion y along +**e_x**.
  - Lead-in face at insertion angle α_in to **e_z**, so the lead-in length along **e_z** = y / tan(α_in).
  - Retention face at α_ret (90° = perpendicular to **e_z**).
  - Flat tip land = catch length − lead-in length.
- Base fillet radius R_b at the beam root; draft on the side faces.

Groove (Parallel):
- In the groove body's wall facing the catch, cut a window/ledge.
  - Width w + 2c.
  - Height (catch length + c).
  - Depth ≥ y + c.
  - The retention ledge sits at L (+c) from the parting plane.
- If the groove body has no wall there, build a groove block with wall thickness T (joined), then cut the window.

Groove via Hook Undercut (Perpendicular):
- Same cut, but the undercut is formed normal to the beam on the other body (orientation per type, G).

Loop (Hook and Loop):
- A rectangular frame on the loop body. Inner opening (w + 2c) × (catch length + 2c), frame thickness T, height L +
  catch length.
- The catch passes through the opening and hooks behind its far bar.

### 4.3 Snap-fit strain check (G; standard cantilever beam theory, as published in resin-supplier design guides)

- Constant rectangular section: allowable deflection y_max = (2/3)·ε·L²/t₀. Equivalently, the strain at deflection y
  is ε = 1.5·t₀·y / L².
- Thickness tapered to t₀/2 at the tip: ε ≈ 1.09·t₀·y / L² (strain about 0.73× the constant-section value).
- Deflection force: P = (w·t₀²/6)·(E_s·ε/L), with E_s = secant modulus.
- Mating force: W = P·(μ + tan α_in)/(1 − μ·tan α_in). μ = friction (≈0.3–0.5).
- Separation force: the same formula with α_ret. It is infinite when α_ret = 90°.
- SciForge: show ε vs. the material allowable (section 3.3). Warn if ε > allowable. No FEA.

### 4.4 Lip / Groove (A for the groove-from-lip rule; G for the section)

Section at a path point on edge E (inside rim edge):
- Wall thickness W = distance from the inner to the outer face of the rim (≈ T).
- Lip: a rectangle (plus drafts) of width w_l (default T/2) and height h_l (default h_r). It sits **on the parting face**
  of the lip body, flush with the inner wall face (selected inside edge), so the outer W − w_l of the rim becomes the
  visible reveal shoulder.
  - Side faces drafted by α_inner / α_outer about the pull/guide direction.
- Groove on the mate (A: groove dims from lip dims + clearance):
  - w_g = w_l + 2c (G: clearance each side; alternatively + c on the outer side only, see section 5).
  - h_g = h_l + c_v (c_v = vertical clearance, default c).
  - Cut into the mate's parting face along the same path. Groove drafts = lip drafts.
- Sweep method:
  - **Face Guide**: the section is attached to the guide face's normal frame, so it follows wall slope. Use a sweep
    with a binormal/auxiliary-surface mode.
  - **Pull Direction**: the section keeps a fixed orientation. Sweep with a fixed binormal = pull direction. Tangent
    continuity is required (A).
- Closed loops: close the sweep. Open chains: end faces square to the path (G).

### 4.5 Rest (G construction; A for the add/remove-by-thickness outcome)

Given profile S on plane Π (normal **n** pointing **out** of the part, flippable) and body B:
1. Remove: C = Prism(S, from Π outward, through all) ∩ B. B₁ = B − C (everything proud of the plane within the profile
   is cut).
2. Landing pad: L = Prism(S, from Π inward, depth = Thickness).
3. Side walls (only where the body is below Π inside the profile):
   - Wall = Prism(S, from Π inward To Next into B) − Prism(Offset(S, −Thickness), from Π − Thickness·**n** inward,
     through all).
   - The hollow pedestal keeps a uniform wall. Wall faces are drafted by the Draft Angle (widening toward the body).
4. Result = B₁ ∪ L ∪ Wall, then remove any material of the old wall that now lies inside the pedestal cavity and above
   the inner face (i.e. keep the body's cavity connected).
5. Flat face check: the face on Π must equal S (one planar face).

### 4.6 Rule Fillet edge selection (A-api enums; G algorithm)

- **All Edges**: E = ∪ edges(f) for every selected face f, plus all faces generated by each selected feature
  (re-resolved at each recompute).
- **Between**: E = { e | e is shared by a face in set 1 and a face in set 2 }.
- Topology filter, with convexity from the dihedral angle measured through the material:
  - convex edge (angle < 180° in material) = **round**;
  - concave edge = **fillet**;
  - Rounds Only keeps convex; Fillets Only keeps concave.
- Then one fillet operation over E (constant or asymmetric), with rolling-ball or setback corners.

### 4.7 Design Advice computations (G; thresholds A)

- **Local thickness**: for sample points on each face (tessellation vertices), cast a ray along the inward normal to the
  opposite face. Thickness = hit distance (or the inscribed-sphere diameter for robustness). The colour map is over
  [min, max].
- **Thickness Range**: flag samples with thickness < minimumThickness or > maximumThickness.
- **Thickness Variation**: flag regions where |t − T| / T > Variation (if % per the blog), or |t − T| > Variation (if a
  length per the API).
- **Draft**: for face normal **m** and pull **p**, draft angle δ = 90° − angle(**m**, **p**) taking the smaller of
  ±**p** (two-sided mould). Flag |δ| < minimumDraftAngle, excluding faces perpendicular to **p** (|δ| ≈ 90°).
- **Knife edge**: flag edges whose adjacent faces meet at a dihedral angle that produces thickness < knifeEdgeThreshold
  within one threshold distance of the edge (wedge thinner than the threshold).
- **Undercut**: a face is an undercut if it is visible from neither +**p** nor −**p** (occluded ray test, the same as
  Accessibility).

---

## 5. Open questions (could not settle)

1. **Exact menu order and panel list** of the PLASTIC tab, i.e. which SOLID commands are repeated, in what order, and
   whether SETUP sits first or after MODIFY. Only "Plastic > Setup" (two rule commands) and "Plastic > Create" (Boss,
   Snap Fit, Lip, Rest) are confirmed.
2. **Fusion's library rule names and values** (which resins; per-resin Thickness/Draft/Radius). Only "metric and imperial
   base rules" and an example like "ABS (1.5mm)" are known. SciForge uses its own table (3.3).
3. **Thickness Variation units**: the blog says a percentage; the API docs give it length units (and its doc string looks
   copy-pasted from maximum thickness).
4. **Exact field mapping** of rule values into each dialog (e.g. is Rib thickness = T or 0.6·T? Emboss depth?). Is
   Reveal Height = lip height or the reveal-step height? Which features use Clearance (Lip only, or Snap Fit and Boss
   too)?
5. **Snap Fit dimension labels and defaults**. No API, and the help excerpts only confirm the sections (Hook, Groove,
   Hook Undercut, Loop), Extent (To Next / Distance) and Base Fillet Radius. The parallel vs. perpendicular geometry is
   inferred.
6. **Lip Advanced-tab fields** (lip width/height, drafts, shoulder, clearance split per side). Only "groove = lip +
   clearance", Face Guide / Pull Direction and the Advanced tab are confirmed.
7. **Rest options** beyond profile + body + thickness (draft, direction, clearance) and its exact construction.
8. **Boss UI tab split** (Boss / Ribs / Fastener) and labels for Shape (Blank / Constant Diameter / Constant Thickness),
   Offset Clearance and the Alignment fields. Also whether the timeline shows one Boss node or one per side.
9. **Design Advice UI placement** (INSPECT command vs. automatic browser alerts) and how results are shown.
10. Whether **Rule Fillet** and the **analyses** are extension-only or base Fusion, and whether the Plastic tab's Fillet
    defaults to Nominal Radius.
11. What the Snap Fit **"visibility controls"** mentioned in the blog are.
12. Whether Assign Plastic Rule creates a timeline entry, and how the rule shows in the browser.
13. Boss "Create Component" makes an *external* component and needs a saved design (the "save first" tip). SciForge
    should use an internal body or part instead.

---

## Critic pass

Independent second review, 2026-10-23. The first researcher's text above is unchanged. This section only adds,
corrects or re-grades facts.

### CP.0 How this pass was done, and its limits

- **No new web searches were possible.** When this pass started, the shared WebSearch budget (200 per turn) was already
  used up. WebFetch and curl cannot resolve autodesk.com, help.autodesk.com, forums.autodesk.com, YouTube or tutorial
  sites. Searching through archive or reader services is not allowed.
- **What was reachable:** `raw.githubusercontent.com`, which hosts Autodesk's own mirror of the Fusion API reference
  (May 2026 release). This pass re-read that mirror on its own, using:
  - the full page index (17,898 pages);
  - the per-enum description pages, which give one-line meanings that the Python stubs leave out;
  - the official Boss sample;
  - the C++ header layout (`include/Fusion/Plastic/`);
  - the User Manual pages `UserInterface_UM.htm` and `Configurations_UM.htm`.
- **Also used:** the sibling research file `surface.md` (A-sourced Fillet/Thicken facts) and the SciForge repo (what
  already exists).
- **Consequence:** the open questions that need help pages or videos (Snap Fit labels, Lip Advanced tab, Rest options,
  menu order) could **not** be advanced. They stay open (CP.5).

New source ids used below:

| Id | Source |
|---|---|
| A-api-PG `<Page>` | `https://raw.githubusercontent.com/AutodeskFusion360/FusionAPIReference/main/Fusion_API_Documentation/files/<Page>.htm` (May 2026). Each page carries its own "Introduced in version" footer |
| A-api-SAMPLE | same path, `BossFeatureSample_Sample.htm` (official sample code) |
| A-api-H | C++ headers at `.../Fusion_API_CPP_Reference/include/Fusion/Plastic/<Name>.h` (HTTP 200 = exists, 404 = absent) |
| A-api-UM | same path, `UserInterface_UM.htm` and `Configurations_UM.htm` |
| A-SURF | sibling file `research/surface.md`: H-SFIL = help `SLD-REF-FILLET.htm`; B-SEP25 = September 2025 What's New |
| F-BAYER | Bayer/Covestro "Snap-Fit Joints for Plastics: A Design Guide" (standard resin-supplier formulas). Quoted from memory, not fetched |
| R | the SciForge repository (read-only check) |

### CP.1 Corrections

**C1. Boss "Constant Thickness" shape is not available in Fusion.**
- Wrong line (2.3): *"Shape | `BossShapeTypes` | **Blank** (no hole) / **Constant Diameter** / **Constant Thickness** |
  Constant Diameter | … Constant Thickness = OD follows hole + 2×rule Thickness"*. The same assumption appears in 1.3
  ("Shank wall thickness (constant-thickness shape)") and in 4.1 step 5.
- Right fact: the enum page describes the three values as follows (A-api-PG `BossShapeTypes`, Oct 2022):
  - `BossBlank`: "Blank boss with no hole and constant diameter."
  - `BossConstDiameter`: "Boss with constant outer shank diameter."
  - `BossConstThickness`: "Boss with constant shank thickness. **Not supported yet.**"
- The input object has only `setBlank`, `setSimple`, `setCounterbore` and `setCountersink`. Each one is documented as
  making a "constant diameter shank".
- So in Fusion the shank is always a constant-OD (drafted) cylinder, with or without a hole.
- SciForge: offer **Blank** plus hole type (Simple / Counterbore / Countersink). Treat a constant-wall option only as an
  optional SciForge extra, clearly labelled.

**C2. Boss rib Profile "None" means no ribs, not square ribs.**
- Wrong lines: 2.3 Ribs table *"Profile | `ribType` = `BossRibShapeTypes` | **None / Chamfer / Fillet** | Chamfer |
  Shape of the rib's top-outer corner"*, and 4.1 step 9 *"None: square."*
- Right fact: `BossRibShapeNone` = "Boss with **no ribs**". `BossRibShapeChamfer` = "Boss with chamfered ribs".
  `BossRibShapeFillet` = "Boss with filleted ribs" (A-api-PG `BossRibShapeTypes`).
- So a rib always has a chamfered or filleted top-outer corner. `ribType = None` is how one side turns its ribs off.
- The UI checkboxes "Side 1 / Side 2" in the Ribs tab most likely map to ribType ≠ None (G).
- SciForge: Rib shape = Chamfer / Fillet. The per-side "ribs on" checkbox stores None when off.

**C3. Rule Fillet is neither a plastic command nor new, and it is not a separate menu item.**
- Wrong lines:
  - 1.2 MODIFY *"2. Fillet … 3. **Rule Fillet** (A-api exists…)"*;
  - 0.4 *"Nov 2025 | Rule Fillet exposed in the API"* (read as the feature's arrival);
  - 2.10 heading "Rule Fillet (MODIFY)" as a plastic command.
- Right facts:
  - A read-only `RuleFilletFeature` / `Features.ruleFilletFeatures` existed since **September 2015**. Both were retired in
    November 2025 (A-api-PG `RuleFilletFeature`, `Features_ruleFilletFeatures`).
  - Creation came in **November 2025**: `FilletFeatures.createRuleFilletInput` / `addRuleFillet` return a normal
    `FilletFeature` (A-api-PG `FilletFeatures_addRuleFillet`).
  - `FilletFeatureTypes` (Sept 2025) = `FilletFeatureType` 0, `RuleFilletFeatureType` 1, `FullRoundFilletFeatureType` 2
    (A-api-PG `FilletFeatureTypes`).
  - The Fillet dialog has **Type = Fillet / Rule Fillet / Full Round Fillet** (A-SURF H-SFIL).
  - Autodesk files the Rule Fillet headers under `Fusion/Features/`, not `Fusion/Plastic/` (A-api-PG header lines).
- So the PLASTIC tab's MODIFY menu has one **Fillet** command whose dialog offers the three types. The only plastic
  link is the radius default (rule Nominal Radius: still G).
- The rest of 2.10 (rules, topology, asymmetric, corner) is correct.

**C4. Emboss has no taper/draft input.**
- Wrong line (1.3): *"Emboss | Depth (and taper if present) | Thickness (fraction) / Draft Angle"*.
- Right fact: `EmbossFeatureInput` (Sept 2025) has only these inputs:
  - `profiles`: sketch profiles **and SketchText**, all coplanar;
  - `inputFaces`: all on one body;
  - `isTangentChain`: default **true**;
  - `depth`: **positive = protrudes out of the body (emboss), negative = goes into the body (deboss)**;
  - `horizontalDistance`, `verticalDistance` and `rotationAngle`: each **defaults to 0**.
  (A-api-PG `EmbossFeatureInput`.) There is no draft or taper.
- Only the **depth** can take a rule value (G).

**C5. The tapered snap-fit strain formula is wrong (section 4.3).**
- Wrong line: *"Thickness tapered to t₀/2 at the tip: ε ≈ 1.09·t₀·y / L² (strain about 0.73× the constant-section
  value)."*
- Right fact: in the resin-supplier tables the 1.09 is the coefficient of the **deflection** formula (F-BAYER):
  - constant section: y = 0.67·ε·L²/t₀, so **ε = 1.5·t₀·y/L²** (the first researcher had this right);
  - tapered to t₀/2: y = 1.09·ε·L²/t₀, so **ε = 0.92·t₀·y/L²**, about **0.61×** the constant-section strain
    (0.67/1.09).
- The force formulas in 4.3 are correct.

**C6. The last Design tab is now TOOLS, not UTILITIES.**
- Wrong line (1.1): *"next to SOLID / SURFACE / MESH / SHEET METAL / UTILITIES"*.
- Right fact: Autodesk's current UI guide says "you have the SOLID, SURFACE, MESH, SHEET METAL, and **TOOLS** tabs in the
  Design workspace" (A-api-UM `UserInterface_UM`).
- PLASTIC is missing from that list, which fits it appearing only with the extension (A-SUPPORT).

**C7. Rib/Web "Start From Top/Bottom" and the "Plastic Design Tools capability" quote are graded too high.**
- Wrong source tags in 2.7 (*"A-RIB, A-api `isThicknessFromTop`"*) and 2.8 (*"A-WEB, A-api ('Setting this property
  requires the Plastic Design Tools capability')"*).
- Right fact: in the May 2026 API, `RibFeature` and `WebFeature` (both since **September 2015**) have **no
  feature-specific properties at all**. There is no `RibFeatureInput` and no `isThicknessFromTop` (A-api-PG
  `RibFeature`, `WebFeature`; fusion.py).
- These names can only come from the October 2026 What's New excerpt. Re-grade them to **"A-APIWN excerpt,
  unverified"**.
- The Rib/Web dialog facts that come from help-page excerpts (A-RIB, A-WEB) are unaffected.

**C8. The Boss alignment default is set by the mate's OD, not "OD + 2·clearance".**
- Wrong line (2.3): *"Alignment Diameter | … | mating side OD + 2·clearance (G)"*.
- Right fact: the official sample pairs the sides as follows (A-api-SAMPLE):
  - Side 1 (head): OD 13 mm, **countersink** hole 5 mm, major 9 mm, under-head depth 3 mm, `alignmentType = StepIn`,
    `alignmentDiameter` 9 mm, `alignmentDepth` 1 mm.
  - Side 2 (thread): shank `diameter = top.alignmentDiameter` (9 mm, the **same value**), `tipRadius =
    top.alignmentRootRadius`, alignment left at Flat.
- So the Side 2 shank tip **is** the spigot that drops into Side 1's recess.
- The API supports this: `alignmentType` "usually corresponds to the alignment shape of the boss counterpart".
- The fit gap is then axial, through `offsetClearance` (G). SciForge default: D_a(side 1) = OD(side 2), with an
  optional radial clearance as a SciForge extra.

**C9. The Boss rule parameters are not tied to a shank wall.**
- Wrong mapping (1.3): *"Boss | Shank wall thickness (constant-thickness shape)…"*.
- Right fact:
  - Every BossFeature exposes `thickness` and `taperAngle` as "plastic part rule reference" model parameters (A-api).
  - Constant-thickness shanks do not exist (C1), so what `thickness` drives geometrically is **unknown**.
  - G: `taperAngle` is the source of the default shank, hole-major, alignment and rib draft angles; `thickness` is the
    source of the default rib thickness and tip/root radii.

### CP.2 Missing commands and options

1. **Shell Type: Sharp / Rounded** (`ShellFeatureInput.shellType`; `SharpOffsetShellType` 0 / `RoundedOffsetShellType`
   1; default **Sharp**; API May 2024) (A-api-PG `ShellTypes`).
   - Rounded rounds the offset at convex corners, so the wall keeps a constant thickness. That matters for Design
     Advice's thickness checks (G).
   - Shell also has: inside thickness, outside thickness, faces or bodies, Tangent Chain (default **true**) (A-api).
2. **Thicken Type: Sharp / Rounded** (`ThickenFeatureInput.thickenType`, default **Sharp**, API Sept 2025)
   (A-api-PG `ThickenTypes`; A-SURF B-SEP25 "New Rounded Thicken").
3. **Full Round Fillet** is the third Fillet type (A-api `FullRoundFilletFeatureType`; A-SURF). It is useful for rib
   and boss-rib tops.
4. **Thin Extrude inputs**, where the rule Thickness lands:
   - wall location **Side1 / Center / Side2** (`ThinExtrudeWallLocation` 0/1/2);
   - one thickness per side for two-sided extrudes;
   - `taperAngleOne/Two`.
   (A-api `ExtrudeFeatureInput.setThinExtrude`.) Rule mapping G: Thickness → wall thickness one/two.
5. **Draft inputs**, where the rule Draft Angle lands:
   - `setSingleAngle(isSymmetric, angle)` or `setTwoAngles(a1, a2)`;
   - `plane` (the fixed plane / pull direction);
   - Tangent Chain, default **true**;
   - Flip direction, default **false**.
   (A-api `DraftFeatureInput`.) Rule mapping G: Draft Angle → angle one (and two).
6. **Boss rib "To Next" makes a web.** `RibSizeToNext` = "Boss rib has **shape of web** and extents to next face". So
   this rib runs out to the next wall, with no chamfer/fillet cut (A-api-PG `BossRibExtentTypes`).
   - `setRibExtent` takes one value **per rib**, so the vector length equals the rib count (A-api).
   - Each side has its own rib count and shape (sample: 4 chamfered ribs on Side 1, 3 filleted ribs on Side 2).
7. **Exact meanings of the Boss hole extents** (A-api-PG `BossHoleExtentTypes`):
   - `BossHoleThrough` = "Hole through all body";
   - `BossBlindFull` = "Blind hole of **max depth with offset from bottom**";
   - `BossBlindDepth` = "Blind hole set by hole depth".
   This confirms the From Bottom / From Top reading.
8. **Boss editing model** (A-api `BossFeature`):
   - Editing calls `createInput()` (timeline rolled to just before the feature) and then `update(input)`, so the whole
     connection, both sides, is re-specified through the creation dialog.
   - `isDirectionFlipped` can be changed on the feature, and `direction` returns the sketch Z.
   - "For **history free** model this interface has limited functionality."
   - SciForge: edit reopens the same two-sided dialog (agrees with the first researcher's G).
9. **Side 2 is meant for "the part or metal inserts"** (A-api). SciForge could add a heat-set-insert preset for the
   Side 2 hole (G).
10. **The Boss fastener section has no API.** Head, drive, thread form and Create Component appear nowhere in the
    reference, so they are UI-only (A-api absence).
11. **The plastic-only surface is small.** Autodesk's headers under `include/Fusion/Plastic/` exist only for
    `PlasticRule(s)`, `PlasticRuleValue` and `Boss*`; probes for `SnapFitFeature.h`, `LipFeature.h`, `RestFeature.h`,
    `DesignAdvice.h`, `RibFeature.h` and `EmbossFeature.h` there all return 404 (A-api-H). Rib, Web, Emboss, Shell,
    Thicken, Draft and Rule Fillet live in `Fusion/Features/`. The analyses live in `Fusion/Fusion/`.
    - So the **plastic-only** pieces are: rules, Boss, Snap Fit, Lip, Rest and Design Advice.
    - Everything else on the tab is a base command with rule-driven defaults.
12. **Design Advice is a command.** The rule docstrings say "used by the **Design Advice command** when analyzing the
    part for manufacturability" (A-api `PlasticRule`). This partly answers open question 9.
13. **The configuration plastic rule table is one of five "theme tables"**: custom, appearance, material, sheet-metal
    rule, plastic rule (A-api-UM `Configurations_UM`).
    - Creating it adds a ConfigurationThemeColumn to the top table.
    - Each column controls one component's **"active plastic rule"** (A-api `ConfigurationPlasticRuleColumns.add`
      docstring). This is the API's own name for the per-component assignment.
    - `clear()` removes the table and hides it in the UI.
14. **Rule Fillet corner type is set at creation only.** `RuleFilletSettings` (the edit object) has no rolling-ball /
    setback property; `topologyType` is editable after rolling the timeline (A-api). SciForge: keep everything
    editable (G).
15. **"Geometric Pattern" is unconfirmed** (1.2 CREATE item 20, taken from AU 2022 "(Geometric) Pattern"). The API has
    only Rectangular / Circular / Path patterns, with compute options Optimized / Identical / Adjust (A-api
    `PatternComputeOptions`). Do not build a separate "Geometric Pattern" (G).

### CP.3 Confirmed or re-checked

- **Boss**:
  - Enum numbers match the first pass: Flat 0 / StepOut 1 / StepIn 2; Through 0 / BlindFull 1 / BlindDepth 2; ByLength
    0 / ToNext 1 / Suppressed 2. All are dated **October 2022** (A-api-PG).
  - Side 1 = head (+sketch Z); Side 2 = thread (−Z); the screw runs opposite to the sketch normal.
  - Participant bodies: if none are given, the closest visible body is found automatically; only the closest body is
    used; solids only.
  - All points must come from one sketch. Only Through is accepted for the top side. Countersink defaults to 90°. Rib
    total angle defaults to 360°. Rib rotation is measured from the sketch X axis.
  - `add()` returns a list. `isGeometryOpposite` marks the thread side. Every value is a ModelParameter. (A-api)
- **Boss defaults the first researcher guessed (G) that now have support:**
  - Side 1 StepIn + Side 2 Flat is the pairing the official sample uses (A-api-SAMPLE).
  - More sample values: shank draft 2°, hole draft 1°, rib chamfer 60°, rib outer draft 10°, alignment depth 1 mm,
    Side 2 counterbore 5 mm × 1 mm with BlindFull depth 3 mm, rib offset 7 mm, rib cut size 5 mm.
  - Sample values are not UI defaults.
- **PlasticRule** (all A-api, Jan 2024):
  - fields, types and units as in 3.1;
  - units are mm or in, "permanently associated … cannot be modified";
  - thickness must lie within min..max;
  - expressions may use `Thickness`, and bare numbers take the rule's units;
  - you cannot delete the default library rule or a design rule that is in use;
  - the `thicknessVariation` docstring really is a copy of "The maximum thickness of the part", so open question 3
    stays open;
  - there is no `Component.activePlasticRule` property (the C++ `Component.h` has only `activeSheetMetalRule`).
- **Rule Fillet enums**: AllEdges 0 / BetweenFacesOrFeatures 1; RoundsAndFillets 0 / RoundsOnly 1 / FilletsOnly 2.
  Constant or asymmetric. Inputs may be faces **or features** (A-api).
- **Draft / Accessibility / Minimum Radius analyses**: API January 2023. They are base INSPECT analyses
  (`Fusion/Fusion/` headers), and the API exposes no settings beyond name and visibility (A-api).

### CP.4 Note for the planner: what SciForge already has (R)

Already in the repo, so the PLASTIC tab should reuse these rather than rebuild them:

- the Fillet dialog with the **Rule Fillet** and **Full Round** types (`SciForgeTests/gui/scenarios/fillet2_rule.py`,
  `fillet2_full_round.py`; golden steps `rule_fillet`, `full_round`);
- **Shell type** sharp/rounded (golden `shell_type`);
- **Thicken type** Sharp/Rounded (`surface_thicken.py`);
- **Rib** and **Web** (`sweep_loft_rib.py`, `sweep_loft_web.py`; **no draft or fillet step yet**);
- **Emboss** (`emboss_flat.py`, `emboss_cylinder.py`);
- **Draft / Accessibility** analysis (`inspect_analysis_draft.py`) and **Minimum Radius** (`sciforge/surface_analysis.py`).

New plastic work is therefore:

- plastic rules (Assign / Manage);
- Boss, Snap Fit, Lip, Rest;
- Design Advice;
- rule-linked defaults in the existing dialogs;
- the Rib/Web **draft + base fillet** extension step.

### CP.5 Still open (needs web access this pass did not have)

- Snap Fit dimension labels and defaults; the exact parallel vs. perpendicular geometry.
- The Lip Advanced-tab fields.
- Rest options beyond profile + body + thickness.
- The PLASTIC tab's panel list and dropdown order. In particular: does SETUP exist, or are the rules under MODIFY as
  "Plastic Rules"?
- Fusion's library rule names and values.
- Thickness Variation units.
- The October 2026 Rib/Web API items (C7).
- Whether the UI still lists "Constant Thickness" (greyed) or hides it (C1).
