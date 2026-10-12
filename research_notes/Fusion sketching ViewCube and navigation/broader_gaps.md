# Fusion beyond part modeling: what a Fusion user needs, how Fusion behaves, and what FreeCAD 1.1 offers

Researched 2026-10-12. How to read the source tags:
- **[Official]**: Autodesk help (help.autodesk.com) or the Fusion API reference.
- **[Autodesk blog/Learn]**: Autodesk's own blog or Learn tutorials. These are official but informal.
- **[Forum]**: Autodesk community forum. Authors range from staff to ordinary users, and each finding says which.
- **[3rd-party]**: tutorials, news coverage, and Lemmy or other forums.
- **[FreeCAD source]**: read straight from this repo, which is upstream FreeCAD at tag 1.1.4.
- **[Inference]**: my own reasoning.

**Access caveat:** the sandbox proxy blocked direct page fetches of autodesk.com, help.autodesk.com and wiki.freecad.org. Every Fusion finding therefore comes from search-engine extracts of the pages cited, not from reading the full page. FreeCAD findings come mostly from this repo's own source, which is the most reliable kind of evidence here. Some items are things I believe from memory but could not source this session. They are listed under "Gaps" as unverified, so the planner can confirm them by hand.

---

## 1. Components and assemblies: components vs bodies, New Component, activation, browser tree, external (linked) components, Insert into Current Design

### Takeaway
Fusion builds assemblies inside one design file. Components are containers that own bodies, sketches and construction geometry. One component is "active" at a time, and new geometry goes into it. Other designs can be inserted as linked (XREF) components, and a link can be broken. FreeCAD 1.1 has a separate Assembly workbench that works bottom-up with links, plus Part containers. A Fusion-style "one design, many components, activate one" workflow has to be built by SciForge on top of those pieces.

### Cited Findings
- **[3rd-party]** Bodies are raw geometry. They cannot be jointed, are hard to reuse, and have no timeline of their own. Components are containers that can be jointed and reused, and each has its own browser node and timeline. You create one by right-clicking the top-level design, or an existing component in the browser, and choosing New Component. — [Fab Academy Fusion notes](https://fabacademy.org/2026/labs/kochi/students/merin-cyriac/Assignments/Week_02/Fusion.html)
- **[3rd-party]** Joints can only be applied between components, not between bodies. — [Noble Desktop: Understanding Joints](https://nobledesktop.com/learn/cad/understanding-joints-in-fusion-360)
- **[Forum, Autodesk employee]** Activating a component only decides who owns the new items. It does not limit what a feature can affect. A hole cut while one component is active can still cut through other components. — [Forum: Activate Component, what is it used for](https://forums.autodesk.com/t5/fusion-design-validate-document/activate-component-what-is-it-used-for-and-perhaps-a-better/m-p/5696860)
- **[Autodesk blog]** In a multi-component design, you create and activate a component first. The new sketch then appears nested inside that component, in both the Timeline and the Browser. — [Autodesk blog p=28362](https://www.autodesk.com/products/fusion-360/blog/?p=28362)
- **[Forum, moderator]** Clicking Activate again does not switch back to the root component. You have to activate the root, or another component, explicitly. — [Forum: How do you deactivate a component?](https://forums.autodesk.com/t5/fusion-design-validate-document/how-do-you-deactivate-a-component/m-p/5446590/highlight/true)
- **[3rd-party, unverified]** A quiz site says you activate a component by double-clicking it in the Browser, or with right-click > Activate, and that the active component's name shows in bold. I could not confirm this in Autodesk's docs. — [Varsity Tutors quiz](https://internal.varsitytutors.com/practice/subjects/autodesk-fusion-360/quiz/fusion-360-interface)
- **[Autodesk blog]** In the Data Panel, Insert > Insert into Current Design brings another design in as a linked component and leaves the original files untouched. This is the XREF-style workflow: to change the part, you edit the original. "Derive" is a different option. It brings in a copy that keeps some connection to the source but can be modified on its own. — [Autodesk blog: Fusion files, links, components](https://www.autodesk.com/products/fusion-360/blog/fusion-files-links-components/)
- **[Autodesk Learn]** Right-click a linked component in the Browser and choose Break Link. The component then becomes local to the design and can be changed without affecting the source file. — [Autodesk Learn: creating assemblies](https://app.learn-one.autodesk.com/learn/ondemand/curated/creating-assemblies/4K0lxcYbcGyJWc3Id0L9sq)
- **[FreeCAD source]** In FreeCAD 1.1.4 the Assembly workbench's "Insert Component" group holds two commands: "Component" (`Assembly_InsertLink`, shortcut I) and "New Part" (`Assembly_InsertNewPart`, shortcut P). Insert Component makes dynamic links to parts, bodies, primitives and assemblies. External components can only be inserted if their file is open in the current session. Shift-click places several instances. — [CommandInsertLink.py](../../src/Mod/Assembly/CommandInsertLink.py), [CommandInsertNewPart.py](../../src/Mod/Assembly/CommandInsertNewPart.py)
- **[3rd-party]** FreeCAD 1.1 news coverage reports a new insert-part tool for assemblies. It also says core Datum tools (coordinate systems, planes, lines, points) can now be attached and used in Assembly. — [linuxadictos: FreeCAD 1.1](https://en.linuxadictos.com/FreeCAD-1.1-introduces-profound-improvements-in-visualization-and-interaction-with-transparent-previews-and-three-point-lighting.html)
- **[3rd-party]** In practice the FreeCAD 1.0 Assembly workbench is bottom-up: insert parts as links, ground one, add joints, then test motion, explode and make a BOM. — [LibreArts: FreeCAD 1.0](https://librearts.org/2024/11/freecad-1-0/)

### Inferences
- **[Inference]** The biggest conceptual gap is that Fusion users think "one design file, many components, the timeline spans all of them", while FreeCAD separates "Part/Body modeling" from "Assembly". SciForge needs a "Component" concept that maps to an App::Part (or Assembly) node containing a Body, has an "active component" marker, and routes new sketches and features into the active component's Body.
- **[Inference]** "Insert into Current Design" maps naturally onto FreeCAD's App::Link to another .FCStd file. Today that requires the file to be open, so SciForge should open it hidden on its own. "Break Link" maps onto copying the linked object into the document.
- **[Inference]** Ownership-only activation (a feature in one component can cut bodies in other components) has to be mirrored. Otherwise cross-component cuts, which robotics brackets often need (for example, a servo pocket cut by the servo model), will be blocked.

### Gaps
- No official Fusion help page text on New Component's options. Unverified recollection: the dialog offers Standard/Sheet Metal type, a parent component, and a "From bodies" option that turns existing bodies into a component.
- Unverified recollection: the Browser shows a component tree with Origin, Joints, Bodies, Sketches, Construction and child-component folders, plus an "activate" radio button next to each component.
- Not researched in depth: Fusion's "Make components from bodies" bulk command, and how the timeline groups features per component in multi-component designs.

---

## 2. Joints: types, joint origins and snap points, as-built joints, rigid groups, ground, limits, drive joints, motion link, motion study, contact sets, and a typical robot-arm setup

### Takeaway
Fusion's Joint command positions and constrains one component against another with a single command. You pick a snap point on component 1, then a snap point on component 2. The first component moves to the second, and you choose the motion type. Seven motion types exist. As-built joints keep the current positions. On top of joints come Ground, Rigid Group, Limits, Motion Link, Drive Joints, Motion Study and Contact Sets. FreeCAD 1.1's Assembly workbench already has a joint solver (Ondsel) with comparable basic joint types, limits, grounding and a new Simulation tool. What it lacks is Fusion's picking UX, Pin-slot and Planar as first-class joints, as-built joints, rigid groups, motion links in Fusion's form, and contact sets.

### Cited Findings
- **[Official API]** There are seven joint types: Rigid=0, Revolute=1, Slider=2, Cylindrical=3, PinSlot=4, Planar=5, Ball=6, plus an "Inferred" type (7) for joints derived from the input geometry. — [Fusion API JointTypes](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/JointTypes.htm)
- **[Autodesk Learn / API]** Degrees of freedom by type:
  - Rigid: 0 DOF.
  - Revolute: 1 rotation about X, Y, Z or a custom edge axis.
  - Slider: 1 translation.
  - Cylindrical: a slide and a rotation about the same axis.
  - Pin-slot: a slide plus a rotation normal to the slide direction.
  - Planar: 2 slides in a plane plus a rotation normal to it.
  - Ball: 3 rotations (pitch, roll, yaw).

  — [Fusion API JointMotionTypes](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_JointMotionTypes.htm); [Autodesk Learn: define joints](https://www.autodesk.com/learn/ondemand/tutorial/define-joints-for-component-relationships)
- **[Official]** In the Joint help, you place a joint origin on each component by snapping to component geometry or construction geometry. — [Create a joint](https://help.autodesk.com/cloudhelp/ENU/Fusion-Assemble/files/ASM-CREATE-JOINT.htm)
- **[Official / Autodesk blog]** The "Between Two Faces" mode lets you pick Plane 1 and Plane 2, and the joint origin is centred between them, even when the faces are angled (it uses the mid-plane). You then pick a snap point. You right-click inside the Joint command to choose the mode, and it works for every joint type. The Joint Origin command has the same mode. — [Create a joint origin](https://help.autodesk.com/cloudhelp/ENU/Fusion-Assemble/files/ASM-CREATE-JOINT-ORIGIN.htm); [Autodesk blog: Joints between two faces](https://www.autodesk.com/products/fusion-360/blog/quick-tip-adding-joints-between-two-faces/)
- **[Forum, community manager]** Holding Ctrl (Cmd on Mac) locks the hovered face's snap points in the Joint and Align commands. It does not do this in Move; Autodesk tracks that as known issue FUS-43691. — [Forum: keep snap points visible](https://forums.autodesk.com/t5/fusion-support-forum/keep-snap-points-visible-for-selection-holding-ctlr-doesn-t-work/m-p/12687354)
- **[Forum, support staff]** Hovering a circular edge snaps to its centre point. Hovering the edge at the end of a feature can snap to its midpoint. Joint origins can only be placed on snap points. — [Forum: How to keep snap points visible](https://forums.autodesk.com/t5/fusion-design-validate-document/how-to-keep-snap-points-visible-for-selection/m-p/7316906/highlight/true); [Lynda: joint origin](https://origin-www.lynda.com/Fusion-360-tutorials/joint-origin/667363/703417-4.html)
- **[Official / 3rd-party]** As-built joints use each component's current position instead of moving one component to meet the other. — [Create an as-built joint](https://help.autodesk.com/cloudhelp/ENU/Fusion-Assemble/files/ASM-CREATE-AS-BUILT-JOINT.htm); [Noble Desktop: as-built joints](https://www.nobledesktop.com/learn/cad/applying-joints-and-as-built-joints-to-assemble-the-model-fusion-360-tutorial)
- **[Autodesk Learn / Forum]** A rigid group locks several components together so they move as one, without adding joints between them. Its main difference from a rigid joint is that it locks the components' origins together. Users typically put all stationary parts in one rigid group (for example, the base and fixed jaws). — [Forum: joined components move together](https://forums.autodesk.com/t5/fusion-design-validate-document/how-do-i-make-my-joined-components-move-together/td-p/11510547); [Autodesk Learn: create motion](https://www-pt.autodesk.com/learn/ondemand/course/fusion360-design-for-manufacturing-cert-prep/unit/O8Gp1DCoR5QrsmygLIIgJ)
- **[Forum]** For an assembly to move, one component normally has to be grounded relative to the model origin. — [Forum: joined components move together](https://forums.autodesk.com/t5/fusion-design-validate-document/how-do-i-make-my-joined-components-move-together/td-p/11510547)
- **[Autodesk Learn]** Edit Motion Limits sets a joint's range of motion and its rest position. Limits apply only to that one joint and ignore related components. A Motion Link ties joints together, for example a revolute to a slider with a rotation-to-distance ratio, or two bevel gears. — [Autodesk Learn: create realistic motion](https://www.autodesk.com/learn/ondemand/tutorial/create-realistic-motion-in-assemblies)
- **[Official API]** JointLimits has separate switches for the minimum, maximum and rest values. — [Fusion API JointLimits](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_JointLimits.htm)
- **[Forum, community manager]** Motion Study is the only way to drive several joints together at different rates and with values that vary over time. — [Forum: animate two joints simultaneously](https://forums.autodesk.com/t5/fusion-support-forum/how-to-i-animate-two-joints-simultaneously/m-p/10616346/highlight/true)
- **[Forum / 3rd-party]** Contact Sets (in the Assemble menu) make chosen bodies collide instead of passing through each other. "Enable Contact Sets" must be switched on in the browser's Contacts folder. They give mechanical motion without joints, as in the Geneva drive example. — [Instructables: Geneva drive contact sets](https://instructables.com/Exercise-File-for-This-Tutorial); [Autodesk Learn: create realistic motion](https://www.autodesk.com/learn/ondemand/tutorial/create-realistic-motion-in-assemblies)
- **[Official]** After you drag components, a Position panel offers Capture Position (record the positions in the timeline) or Revert (go back to the last captured position). Commands that depend on positions, such as Joint Origin, ask you to capture or revert first. — [Capture or revert position](https://help.autodesk.com/cloudhelp/ENU/Fusion-Assemble/files/ASM-CAPTURE-POSITION.htm); [Autodesk blog: Capture or Revert](https://www.autodesk.com/products/fusion-360/blog/how-to-capture-or-revert-autodesk-fusion/)
- **[3rd-party/Autodesk blog]** Robot-arm practice in Fusion: model a base plate with servo mounts, then join each link with revolute joints. One maker project modelled each joint in Fusion before printing, using 5 servos with an Arduino and a PCA9685 driver. An Autodesk developer blog offers a script that drives all revolute joints from one slider and respects their limits. — [open-electronics: robotic arm with Fusion](https://www.open-electronics.org/learn-how-to-design-and-control-a-robotic-arm-with-arduino-and-fusion-360/); [Fab Academy robot base](https://fabacademy.org/2021/labs/ingegno/students/cristiano-lemes/assignments/week03/); [Autodesk dev blog: drive all revolute joints](https://blog.autodesk.io/drive-all-revolute-joints/); [UMD guide: assemblies](https://dozuki.umd.edu/Guide/Assemblies/303)
- **[FreeCAD source]** The FreeCAD 1.1.4 Assembly workbench offers these joint types: Fixed, Revolute, Cylindrical, Slider, Ball, Distance, Parallel, Perpendicular, Angle, RackPinion, Screw, Gears and Belt. Icons also exist for Planar and Tangent, which appear to be sub-modes, not separate types. There is no Pin-slot joint. — [JointObject.py lines 49-79](../../src/Mod/Assembly/JointObject.py)
- **[FreeCAD source]** Joint limits exist (EnableLengthMin/Max, EnableAngleMin/Max). Length limits apply to Cylindrical and Slider, angle limits to Revolute and Cylindrical. Grounding uses a "GroundedJoint" object (Assembly_ToggleGrounded). The workbench also has Simulation (shortcut V) with Motion objects, Exploded View, Bill of Materials, Solve and Export ASMT. — [JointObject.py](../../src/Mod/Assembly/JointObject.py); [CommandCreateJoint.py](../../src/Mod/Assembly/CommandCreateJoint.py); [CommandCreateSimulation.py](../../src/Mod/Assembly/CommandCreateSimulation.py); [CommandCreateView.py](../../src/Mod/Assembly/CommandCreateView.py)
- **[3rd-party]** FreeCAD 1.1 joints can drive motion simulations and produce animations. — [linuxadictos: FreeCAD 1.1](https://en.linuxadictos.com/FreeCAD-1.1-introduces-profound-improvements-in-visualization-and-interaction-with-transparent-previews-and-three-point-lighting.html); [alternativeTo news](https://alternativeto.net/news/2026/3/freecad-1-1-adds-three-point-lighting-part-design-previews-and-major-fem-upgrades)
- **[3rd-party]** FreeCAD's solver is the Ondsel Solver, an LGPL C++ library for assembly constraints and multibody dynamics. Ondsel's design write-up says FreeCAD shows a local joint coordinate system for each feature. It also says the workbench aims to cover about 80% of use cases, with add-on workbenches handling the rest. — [Ondsel: assembly workbench preview](https://www.ondsel.com/blog/assembly-workbench-preview/); [Ondsel blog: default assembly workbench](https://ondsel.com/blog/default-assembly-workbench-7)
- **[GitHub issue]** A dev build crashed on belt, gear and rack-and-pinion joints. The report is old and may already be fixed. — [FreeCAD issue #14458](https://github.com/FreeCAD/FreeCAD/issues/14458)

### Inferences
- **[Inference]** The minimum viable Fusion-style joint workflow for a robot arm is: Ground the base, join each link with Revolute, set angle limits, then drag or "Drive Joints" to pose it. The FreeCAD 1.1 solver can already do every one of these steps. The work for SciForge is mostly UX:
  - A single Joint dialog where component 1 moves to component 2.
  - Hover-snap keypoints (face centre, edge midpoint, circle centre, vertices), with Ctrl to lock a face.
  - Motion type chosen after picking, with an animated preview.
  - Offset and angle fields, and a Flip button.
  - Joints, Ground and Rigid Groups shown in the browser and timeline.
- **[Inference]** Pin-slot can be built by mapping it onto existing solver primitives (cylindrical plus an in-plane constraint, or a Distance-type combination). Planar can be built the same way. As-built joints amount to "do not pre-solve placement; record the current relative placement as the joint offset". Rigid Group amounts to several Fixed joints, or a sub-assembly treated as rigid (FreeCAD has an "AssemblyLinkRigid" icon, which suggests rigid sub-assembly links already exist).
- **[Inference]** Contact sets need collision detection during drag. That is the costliest feature and the least needed by hobbyists, so defer it.
- **[Inference]** Fusion's Capture Position / Revert maps onto FreeCAD placements that the solver resets. SciForge would need a "position state" that is temporary until captured.

### Gaps
- No official text on "Drive Joints" dialog fields or "Motion Link" dialog fields. Unverified recollection: Drive Joints takes one joint and a value (angle or distance) and snaps the joint to it. Motion Link takes 2 joints, with a distance/angle per joint and an Animate button. The Joint dialog has a "Motion" tab with an animate preview.
- Unverified: when exactly Fusion auto-infers the joint type ("Inferred" in the API), and how the joint-origin types work (Simple, Between Two Faces, Two Edge Intersection).
- I found no 2025-2026 user reports comparing FreeCAD 1.1 Assembly against Fusion for reliability (joint flipping, solver failures).

---

## 3. Files and versions: cloud data panel, version history, autosave/recovery, and what a local-first replacement must offer

### Takeaway
Fusion keeps every design in the cloud, inside projects. Every save creates a new version in a version history. Fusion autosaves backups locally once a file has been saved at least once, and offers recovered documents after a crash. Offline work is limited to cached files. FreeCAD is local-file based, with 15-minute autosave, crash recovery and one backup file by default, but it has no version history. A local-first SciForge should copy Fusion's "versions on every save, browsable and restorable" without a cloud.

### Cited Findings
- **[Forum]** Fusion autosaves backups at an interval set in Preferences, but only after the design has been saved once with a project and name. Unsaved work after a crash shows up in a recovered-documents list under the File menu. — [Forum: recently saved models](https://forums.autodesk.com/t5/fusion-support-forum/can-t-access-recently-saved-models/td-p/7256251)
- **[Forum]** Every save creates a new version. Users complain about cluttered version history and ask for a "save without new version" option. — [Forum: save without advancing version](https://forums.autodesk.com/t5/fusion-support-forum/trick-to-save-design-without-advancing-version-number/m-p/7482769)
- **[Forum, Fusion engineer]** Offline, only files in the local cache can be edited; files that are not cached appear greyed out. "File > New Design From File" opens a cached file but loses its version history. — [Forum: save without advancing version (thread)](https://forums.autodesk.com/t5/fusion-support-forum/trick-to-save-design-without-advancing-version-number/m-p/9323483)
- **[Autodesk blog 2020]** Personal-use licences are limited to 10 active (editable) documents. PDFs, images and similar files do not count toward the limit. — [Autodesk blog: changes for personal use](https://www.autodesk.com/products/fusion-360/blog/changes-to-fusion-360-for-personal-use/)
- **[FreeCAD source]** FreeCAD's autosave defaults to every 15 minutes (`AutoSaveTimeout`, default 15) and a DocumentRecovery dialog runs after a crash. On save it creates backup files by default (`CreateBackupFiles=true`), keeping 1 backup (`CountBackupFiles=1`). — [StartupProcess.cpp:265](../../src/Gui/StartupProcess.cpp); [Document.cpp:1870](../../src/App/Document.cpp); [DocumentRecovery.cpp](../../src/Gui/DocumentRecovery.cpp)

### Inferences
- **[Inference]** A local-first replacement should offer:
  1. A project folder ("data panel") with thumbnails.
  2. Automatic numbered versions on save (v1, v2, ...) stored beside the file, with a history list that can open, compare or promote an old version.
  3. Autosave and crash recovery, which FreeCAD already has.
  4. Optional milestones or notes per version.
  5. Linked components that resolve by relative path inside the project.

  Raising FreeCAD's `CountBackupFiles` and adding a version browser would cover most of this cheaply.
- **[Inference]** Fusion's cloud model is a common reason hobbyists leave (the 10-document limit, offline restrictions). A local-first approach is a selling point, not just parity.

### Gaps
- No official Fusion help text on the current Data Panel, version promotion, milestones, or the autosave interval default (unverified recollection: Preferences > General has an auto-save interval, and milestones/"Promote" exist in the version list).
- I could not confirm current (2024-2026) personal-use limits from an official page.

---

## 4. Direct modeling (capture design history off) and editing imported STEP bodies

### Takeaway
Imported STEP files come into Fusion as "direct" models with no history, and users edit them with Press Pull, Move Face and Delete Face. History capture can be switched on later from the browser's root node, and recording starts from that moment. In FreeCAD, an imported STEP file is a static Part feature. Editing it means PartDesign features on a BaseFeature, or Part Defeaturing. The SciForge Press Pull already covers part of this.

### Cited Findings
- **[Autodesk blog]** Imported models are created as direct models, so the operations performed are not captured as history. Direct modeling is good for small changes to imported geometry. To capture history, right-click the base node in the browser and choose Capture Design History. — [Autodesk blog post 426](https://www.autodesk.com/products/fusion-360/blog/wp-json/wp/v2/posts/426)
- **[3rd-party]** STEP and other neutral formats carry no timeline. A file edited in direct-modeling mode saves without design history. — [GrabCAD: enable parametric history](https://cad.grabcad.com/tutorials/how-to-enable-missing-parametric-design-history-in-fusion)
- **[Forum]** Turning history on for an opened STEP file starts recording at that moment, so earlier sketches do not appear. — [Forum: can't find previous sketches after opening STEP](https://forums.autodesk.com/t5/fusion-design-validate-document/can-t-find-previous-sketches-after-opening-step-file-opens-as-a/td-p/6361756)
- **[Official]** Mesh conversion has a "Base Feature" option, which stores the result as a non-parametric base feature inside a parametric timeline. — [Mesh Convert to Solid](https://help.autodesk.com/cloudhelp/ENU/Fusion-Mesh/files/MESH-CONVERT-TO-SOLID.htm)
- **[FreeCAD source]** FreeCAD 1.1.4 has `Part_Defeaturing` (remove selected faces and heal), `Part_Thickness`, `Part_Offset` and `Part_RefineShape`. Together these are FreeCAD's building blocks for face-level editing of dumb solids. — `src/Mod/Part/Gui/Command*.cpp` (grep of `Command("Part_...")`)

### Inferences
- **[Inference]** For hobbyists the main use is editing a downloaded STEP of a servo, motor or bracket: add a hole, delete a fillet, shorten a tab. SciForge should:
  - Import STEP straight into a component, as a Body with a BaseFeature.
  - Let Press Pull, Delete Face, Move Face, Hole and Fillet work on it.
  - Optionally offer a per-document "do not capture history" switch, though this is low value. Fusion users mostly hit it only by accident through imports.

### Gaps
- No source found for Fusion's "Delete Face" behaviour (heal versus leave an opening), or for the "Base Feature" edit mode in parametric designs (unverified recollection: Create Base Feature lets you do direct edits inside a parametric timeline).

---

## 5. Surface workspace basics: patch, stitch, thicken, trim, extend, offset surface, ruled, delete face

### Takeaway
Fusion's Surface tab has a compact, consistent toolset that mirrors the solid tools: Extrude, Revolve, Sweep, Loft, Patch, Offset, Ruled, Extend, Trim, Untrim, Stitch, Unstitch, Thicken and Delete. FreeCAD spreads equivalents across the Surface and Part workbenches with different names and behaviours. This area matters little for robotics or printing.

### Cited Findings
- **[Official]** Patch fills a closed loop with a planar or 3D surface. The missing face needs a connected chain of boundary edges. Stitch joins surfaces into one quilt. Trim splits intersecting surfaces and removes regions. Untrim extends trimmed surfaces and fills holes. Extend pushes edges outward. Ruled creates a surface at a distance and angle from edges. — [Fusion help: modify tools for surface bodies](https://help.autodesk.com/cloudhelp/ENU/Fusion-Patch/files/SFC-MODIFY-SURFACE.htm); [Fusion help: surfaces from existing geometry](https://help.autodesk.com/cloudhelp/ENU/Fusion-Patch/files/SFC-CREATE-SURFACE-FROM-SKETCH.htm)
- **[Forum, Autodesk consultant]** Offset moves surface data away by a value without connecting anything, whereas Thicken makes a solid. Offset with "Chain Selection" off copies a single face. — [Forum: copy a face](https://forums.autodesk.com/t5/fusion-design-validate-document/copy-a-face/m-p/7779040)
- **[Autodesk blog]** Extend can follow the surface's curvature to continue it naturally. — [Autodesk blog: surfaces to machine complex geometry](https://www.autodesk.com/products/fusion-360/blog/fusion-360-surfaces-machine-complex-geometries/)
- **[FreeCAD source]** The Surface workbench in 1.1.4 has BlendCurve, CurveOnMesh, Cut, ExtendFace, Filling (the patch equivalent), GeomFillSurface and Sections. The Part workbench has Thickness, Offset, Offset2D, RuledSurface, Section, SectionCut and Defeaturing. — `src/Mod/Surface/Gui/Command.cpp`, `src/Mod/Part/Gui/Command*.cpp`

### Inferences
- **[Inference]** For makers, the only regularly used surface tools are Patch (closing holes in imported or converted meshes), Stitch (turning a surface into a solid after mesh conversion), Thicken and Split Body with a surface. The rest can wait. Patch maps to Surface_Filling, Stitch to sewing (Part's ShapeFromMesh and shape-builder sewing), Thicken to Part_Thickness or Offset with fill, and Ruled to Part_RuledSurface.

### Gaps
- No official Fusion source found this session for Thicken or Delete Face. I did not confirm whether FreeCAD 1.1 exposes a dedicated "sew/stitch" command (Part_Sewing was not found in the Part Gui command list grep).

---

## 6. Import/export: STEP/IGES/STL/3MF/OBJ/DXF/SVG/F3D, inserting meshes, mesh to BRep, canvases and calibration, decals

### Takeaway
Fusion exports F3D/F3Z, STEP, IGES, SAT, SMT, STL, OBJ, 3MF, USDZ, DWG and DXF. DXF is exported per sketch, and personal use loses the "additional" formats. Inserted meshes convert to BRep (Faceted, or Prismatic with face groups) as a parametric or base feature, capped at around 10k facets. Canvases are images on a plane, calibrated by two points and a known distance. Decals are images wrapped on faces for appearance. FreeCAD 1.1 already reads and writes most of these formats, but the workflows (insert mesh into a component, convert, calibrate an image) are clunky.

### Cited Findings
- **[Official]** Fusion export types include F3D, F3Z, 3MF, DWG, DXF, IGES, OBJ, SAT, SMT, STEP and STL. The supported-formats page lists USDZ and SMT as standard formats and DWG/DXF as "additional" formats, which every licence type gets except Personal Use. DXF export is right-click on a sketch > Export DXF. SAT is supported up to ACIS 7. — [Export designs](https://help.autodesk.com/cloudhelp/ENU/Fusion-Designs/files/ASM-EXPORT-DESIGN.htm); [Supported file formats](https://help.autodesk.com/cloudhelp/ENU/Fusion-Designs/files/TPD-SUPPORTED-FILE-FORMATS.htm)
- **[Autodesk blog 2020]** STEP export was kept for personal use after a backlash. The earlier notice listed F3Z, DWG, DXF, IGES, SAT and STEP export as removed, and drawing output as print-only. — [Autodesk blog: STEP export stays](https://www.autodesk.com/products/fusion-360/blog/changes-to-fusion-360-for-personal-use/)
- **[Official]** Convert Mesh (Mesh tab > Modify) has two options:
  - Operation: Parametric (keeps upstream relationships) or Base Feature.
  - Method: Faceted (one face per triangle) or Prismatic (merges face groups into single faces). Running Generate Face Groups first improves Prismatic results.

  — [Mesh Convert to Solid](https://help.autodesk.com/cloudhelp/ENU/Fusion-Mesh/files/MESH-CONVERT-TO-SOLID.htm); [Autodesk blog: convert mesh to solid](https://www.autodesk.com/products/fusion-360/blog/convert-mesh-to-solid-surface-body-fusion-360/)
- **[Autodesk support]** Converting a mesh to BRep or T-spline is limited to roughly 10,000 mesh elements. — [Autodesk support: insert a mesh body](https://autodesk.com/support/technical/article/How-to-insert-a-mesh-body-into-Fusion-360)
- **[3rd-party]** Personal-use users reportedly get only Faceted conversion, not Prismatic. — [UNBC Sparklab: converting STL for editing in Fusion](https://sparklab.unbc.ca/?p=760)
- **[Official]** To calibrate a canvas, expand Canvases in the browser, right-click the image > Calibrate, pick two points, type the real distance and press Enter. The image scales uniformly. — [Calibrate canvas](https://help.autodesk.com/cloudhelp/ENU/Fusion-Model/files/SLD-SCALE-CANVAS.htm); [Fusion API: Canvases](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/Canvases_UM.htm)
- **[Forum, 2017]** Calibrate did not exist for decals at that time. — [Forum idea: canvas width/height precision](https://forums.autodesk.com/t5/fusion-360-ideastation-archived/ability-to-control-with-precision-the-width-and-height-of-canvas/idi-p/6248581)
- **[Official]** Decals are applied as part of appearance/render setup, alongside materials, texture maps and lighting environment. — [Fusion help: appearances](https://help.autodesk.com/cloudhelp/ENU/Fusion-Render/files/RND-MATS-APPEARANCES.htm)
- **[FreeCAD source]** FreeCAD 1.1.4 file support:
  - Mesh: imports OBJ and 3MF; exports OBJ, AMF and 3MF.
  - Draft: imports and exports DXF, SVG and DWG (DWG needs an external converter).
  - Import module: glTF and STEPZ, with STEP and IGES built in.
  - Mesh to BRep: `Part_ShapeFromMesh`.
  - Images: opening an image file creates an ImagePlane object.

  — [Mesh/Init.py](../../src/Mod/Mesh/Init.py); [Draft/Init.py](../../src/Mod/Draft/Init.py); [Import/Init.py](../../src/Mod/Import/Init.py); `src/Gui/FileHandler.cpp` (ImagePlane)

### Inferences
- **[Inference]** For makers, the order of importance is:
  1. STEP import as a component, for vendor parts such as servos and bearings.
  2. STL/3MF/OBJ insert as a mesh body, with "Convert to solid": faceted first, prismatic later.
  3. DXF/SVG insert into a sketch, for laser-cut or logo outlines.
  4. A canvas with two-point calibration, for tracing photos of parts.

  Decals are low priority because they are only visual.
- **[Inference]** F3D import is not realistic, since the format is proprietary. Users would export STEP from Fusion. A clear "Import from Fusion: use STEP" message is enough.

### Gaps
- Not verified: the current Fusion "Insert" menu items (Insert Mesh, Insert SVG, Insert DXF, Insert McMaster-Carr Component, Decal, Canvas), or the canvas dialog options (opacity, "display through", selectable).
- Not verified: how FreeCAD 1.1's Part_ShapeFromMesh handles large meshes, or whether a "prismatic" (plane/cylinder recognition) conversion exists. ReverseEngineering offers some fitting.

---

## 7. Drawings workspace basics: base and projected views, dimensions, title block, PDF/DXF export

### Takeaway
Fusion Drawings create a sheet from a design. You place a base view, project views from it, add dimensions, and the title block is filled in. Output is PDF or DXF, though personal use has historically restricted output. FreeCAD's TechDraw already covers views, projection groups, sections, details, dimensions, templates and PDF/DXF/SVG export. The gap is UX, not capability, and hobbyists rarely need drawings.

### Cited Findings
- **[Autodesk blog 2020 / Forum]** In personal use, drawing output was "print only". Users reported they could not export a PDF or DXF of a dimensioned drawing. Reports are anecdotal and dated. — [Autodesk blog: changes for personal use](https://www.autodesk.com/products/fusion-360/blog/changes-to-fusion-360-for-personal-use/); [LightBurn forum](https://forum.lightburnsoftware.com/t/getting-fusion-360-files-into-lightburn/125673); [V1 Engineering forum](https://forum.v1e.com/t/fusion-360-changes/20975)
- **[Forum, Autodesk staff]** The Drawings "Shaded" view style keeps strong silhouette linework compared with the design workspace. — [Forum: Fusion drawing shaded mode](https://forums.autodesk.com/t5/fusion-support-forum/fusion-drawing-wont-display-shaded-mode-correctly/m-p/14128614/highlight/true)
- **[FreeCAD source]** TechDraw in 1.1.4 has PageDefault, PageTemplate, View, ProjectionGroup, SectionView, SectionGroup, DetailView, LengthDimension (and other dimensions), ExportPageDXF, ExportPageSVG, PrintAll and PDF printing (PagePrinter). — `src/Mod/TechDraw/Gui/Command*.cpp`, `src/Mod/TechDraw/Gui/PagePrinter.cpp`
- **[3rd-party]** In FreeCAD 1.0 and later, BOMs and exploded views from Assembly can be placed on TechDraw pages. — [LibreArts: FreeCAD 1.0](https://librearts.org/2024/11/freecad-1-0/)

### Inferences
- **[Inference]** For robotics and printing hobbyists, drawings are low priority. A thin Fusion-style wrapper is enough:
  - "New Drawing from Design" with a base view, its projections, and a pre-filled template.
  - Fusion-like auto-dimension placement.
  - One-click export to PDF and DXF.

  DXF of a face or sketch, for laser cutting, matters more than full drawings.

### Gaps
- No official Fusion Drawings help was retrieved (the base-view dialog, projected-view clicks, title-block fields, and the sheet sizes and standards ASME/ISO). The "New Drawing > From Design" flow is unverified recollection.

---

## 8. Selection behaviors: window vs crossing, filters, select through, select other (click and hold), selection priority

### Takeaway
Fusion's selection model:
- Dragging left to right selects only objects fully inside the box (window). Dragging right to left selects anything touched (crossing).
- Freeform and paint selection exist too.
- Ctrl toggles items in and out of the selection; Shift only adds.
- Click and hold opens "Select Other", a depth-ordered list plus a parents list.
- A Selection Filters list includes "Select Through".
- Selection Priority presets (Body, Face, Edge, Component) can be bound to hotkeys.

FreeCAD 1.1 has box selection with a similar left/right meaning for faces, and a new "Clarify Selection" (G, G) picker. It has no unified filter and priority menu and no click-and-hold.

### Cited Findings
- **[Forum/Autodesk blog]** Left to right selects only objects completely enclosed. Right to left selects anything the box touches. The two are drawn in different colours. — [Autodesk blog: 3 ways to select an area](https://www.autodesk.com/products/fusion-360/blog/tip-tuesday-3-ways-to-select-an-area-in-fusion-360/); [Autodesk blog: selection tricks](https://www.autodesk.com/products/fusion-360/blog/?p=5026)
- **[Autodesk blog]** Freeform selection works like this: a clockwise boundary selects everything inside, and a counter-clockwise boundary selects visible objects that it crosses. Paint selection is always crossing-style. — [Autodesk blog: select an area](https://www.autodesk.com/products/fusion-360/blog/?p=40170)
- **[Official]** Ctrl/Cmd adds or removes objects; Shift only adds. — [Selection in Fusion](https://help.autodesk.com/cloudhelp/ENU/Fusion-Model/files/SLD-SELECTION.htm)
- **[Official / Autodesk blog]** Click and hold, without dragging, for about a second over the geometry to open the Select Other list. Hovering an entry highlights it, and the mouse wheel scrolls the list. It has two tabs. The "Depth" tab lists objects front to back. The "Parents" tab lists the chain from the item under the cursor up to the root. — [Select objects](https://help.autodesk.com/cloudhelp/ENU/Fusion-Model/files/SLD-SELECT-OBJECTS.htm); [Autodesk blog: Select Other](https://www.autodesk.com/products/fusion-360/blog/quick-tip-how-to-use-select-other/)
- **[Official]** Select > Selection Filters lists Select All, Bodies, Body Edges, Body Faces, Body Vertices, Components, Features and more. "Select Through" is one entry: unchecked, it means box and freeform selection picks only unobscured objects. — [Use selection filters](https://help.autodesk.com/cloudhelp/ENU/Fusion-Model/files/SLD-SELECTION-FILTERS.htm)
- **[Official / Forum]** Select > Selection Priority presets each switch one filter on and all the others off. For example, Component priority checks only Components, and Body priority (Alt+B per a forum answer) checks only Bodies. The presets can take hotkeys, and there is no built-in shortcut back to "Select All". — [Use selection priority filters](https://help.autodesk.com/cloudhelp/ENU/Fusion-Model/files/SLD-SELECTION-PRIORITY-FILTERS.htm); [Forum: fast selection filter](https://forums.autodesk.com/t5/fusion-design-validate-document/fast-selection-filter-selection/m-p/8569315); [Forum: edge priority selects component](https://forums.autodesk.com/t5/fusion-support-forum/component-gets-selected-despite-edge-selection-priority-selected/m-p/12867042)
- **[Autodesk blog]** In assemblies, a box drag that starts on a component drags the component instead. The fix is turning off "Component Drag" in the Select menu. — [Autodesk blog: select multiple components](https://www.autodesk.com/products/fusion-360/blog/select-multiple-components-fusion-360-tutorial/)
- **[FreeCAD source]** FreeCAD 1.1.4 has `Std_ClarifySelection` (shortcut "G, G"): "Displays a context menu at the mouse cursor to select overlapping or obstructed geometry in the 3D view". It also has `Std_BoxSelection`, `Std_BoxElementSelection` and `Std_SelBoundingBox`. — [CommandView.cpp:4224-4236](../../src/Gui/CommandView.cpp)
- **[FreeCAD wiki via search]** In Std_BoxElementSelection, a left-to-right drag selects faces whose centre lies inside the box. A right-to-left drag selects faces partly inside or touched. A whole object inside the box is selected as an object. — [FreeCAD wiki: Std_BoxElementSelection](https://wiki.freecad.org/Std_BoxElementSelection)
- **[3rd-party]** FreeCAD 1.1's Clarify Selection makes nearby objects temporarily transparent and lists selectable elements. — [digitalproduction: FreeCAD 1.1](https://digitalproduction.com/2026/04/01/freecad-1-1-stacks-workflow-upgrades/)

### Inferences
- **[Inference]** This is cheap, high-value work that affects every workflow:
  - Bind click-and-hold to Std_ClarifySelection's picker, adding the Depth and Parents ordering.
  - Make a plain left-mouse drag in empty space start a box selection with Fusion's window/crossing meaning, without first entering a box mode.
  - Add a Select menu with Filters, Select Through and Priority presets.

  FreeCAD's default needs Shift+B or a mode to box-select.

### Gaps
- Not verified: whether Fusion's window selection in a sketch obeys the same direction rule (unverified recollection: yes), or the exact default hotkeys for the priority presets apart from Alt+B (forum).

---

## 9. Display: visual styles, appearance, physical materials, section view, environment

### Takeaway
Fusion separates **physical material** (density for mass and centre of mass, used by Simulation and CAM) from **appearance** (visual only, overrides the material's colour). It also has visual styles (Shaded, Shaded with Hidden Edges, Shaded with Visible Edges Only, Wireframe variants) and preset lighting environments. FreeCAD 1.1 has the Material system, appearance and draw styles, clip planes and three-point lighting. SciForge already has appearance and material dialogs, so the remaining work is visual-style presets and environment polish.

### Cited Findings
- **[Official]** Appearances override the colour assigned by the physical material and do not affect engineering properties. Render setup handles materials, appearances, texture maps, lighting environment and decals. — [Fusion help: appearances](https://help.autodesk.com/cloudhelp/ENU/Fusion-Render/files/RND-MATS-APPEARANCES.htm)
- **[3rd-party / Forum]** The physical material defines density, and through it mass. Simulation and CAM use it. Users assign aluminium physically but colour parts with appearances. — [Noble Desktop: materials and visuals](https://nobledesktop.com/learn/cad/updating-materials-and-visuals-in-fusion-360); [Forum: material vs appearance](https://forums.autodesk.com/t5/fusion-design-validate-document/material-versus-appearance/m-p/8334366/highlight/true)
- **[Official API]** The VisualStyles enum includes ShadedWithVisibleEdgesOnly (2) and Wireframe (3), among others. — [Fusion API VisualStyles](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/VisualStyles.htm)
- **[3rd-party]** Fusion's preset environments differ a lot from one another and suit different uses. — [Instructables: render models in Fusion](https://instructables.com/Render-Models-In-Fusion-360)
- **[FreeCAD source / 3rd-party]** FreeCAD 1.1.4 has `Std_DrawStyle` and `Std_ToggleClipPlane`, plus Part_SectionCut. FreeCAD 1.1 added three-point lighting and transparent previews. — [CommandView.cpp](../../src/Gui/CommandView.cpp); [alternativeTo news](https://alternativeto.net/news/2026/3/freecad-1-1-adds-three-point-lighting-part-design-previews-and-major-fem-upgrades)

### Inferences
- **[Inference]** For robotics, correct physical materials (PLA/PETG density, aluminium, steel) matter more than looks. Fusion users expect mass and centre of mass per component, which feeds the motor torque sizing a robot arm needs. Visual-style presets matching Fusion's six are a small task on top of Std_DrawStyle. Environments are cosmetic and low priority.

### Gaps
- Not verified: the full list of Fusion visual styles and environment presets, or Fusion's display-settings menu items (Ground Shadow, Object Shadow, Reflections, Ambient Occlusion, Effects).

---

## 10. Other daily conveniences: Compute All, Capture Position, user parameters in dialogs, measure snaps, sketch text, Find in Browser/Timeline

### Takeaway
Small items that Fusion users reach for daily:
- Compute All (Ctrl+B).
- Capture/Revert Position.
- Typing expressions and parameter names into any value box.
- Sketch Text, including Text on Path, followed by Emboss.
- Find in Browser and Find in Timeline.

FreeCAD has recompute, expressions in inputs (the `=` key) and Draft ShapeString for text, but no sketch text tool. Sketch text plus emboss matters for 3D-printed labels.

### Cited Findings
- **[Official]** Compute All is in Modify > Compute All, or Ctrl+B. It recomputes all parameters, features and assembly relationships. Use it after upstream edits that touch referenced geometry, and before saving after big changes. Failing features show a yellow warning or red error in the timeline, and right-click > Review Warning explains them. — [Compute All](https://help.autodesk.com/cloudhelp/ENU/Fusion-Model/files/SLD-COMPUTE-ALL.htm)
- **[Official API]** `computeAll` does not report success. You check each timeline item's health state instead. — [Design.computeAll](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/fusion_Design_computeAll.htm)
- **[Official]** Capture Position / Revert works as described in area 2. — [Capture or revert position](https://help.autodesk.com/cloudhelp/ENU/Fusion-Assemble/files/ASM-CAPTURE-POSITION.htm)
- **[Official]** Sketch Text has a "Text on Path" type that follows a sketch curve and updates when the path changes. It uses the system's installed TrueType fonts. Single-line fonts are not suitable for Emboss. — [Fusion help: Create text](https://help.autodesk.com/cloudhelp/ENU/Fusion-Sketch/files/SKT-SKETCH-CREATE-TEXT.htm); [Fusion help: Text dialog](https://help.autodesk.com/cloudhelp/ENU/Fusion-Sketch/files/SKT-REF-TEXT-DIALOG.htm); [All3DP: Fusion text](https://all3dp.com/2/fusion-360-text-extrude-tutorial/)
- **[Forum]** Emboss sometimes fails with "not coplanar" on curved faces. One workaround is to extrude the text and cut. — [Forum: Emboss not coplanar](https://forums.autodesk.com/t5/fusion-design-validate-document/emboss-sketch-profiles-are-not-coplanar/m-p/13094766/highlight/true)
- **[Forum]** A "Find in Timeline" command exists, but users find long timelines still hard to navigate. Dragging to reorder timeline items works only in parametric mode. — [Forum: History / timeline](https://forums.autodesk.com/t5/fusion-design-validate-document/history-timeline/m-p/6358022)
- **[FreeCAD source]** FreeCAD has `Draft_ShapeString` (text as geometry from a font file) but no Sketcher text tool. — `src/Mod/Draft/draftguitools/` (grep of `Draft_ShapeString`)

### Inferences
- **[Inference]** Priority order:
  1. Sketch Text with Text on Path, plus Emboss/Deboss onto flat and curved faces. Makers label printed parts and robot links.
  2. Expressions and parameter names in every SciForge dialog value box, which may already be partly done through Change Parameters.
  3. Find in Browser and Find in Timeline, via right-click on geometry: highlight the owning feature.
  4. Compute All (Ctrl+B) mapped to recompute-all with an error summary.

  Measure snaps were not researched further, since Measure is already done.

### Gaps
- No source found for the exact Fusion "Find in Browser" / "Find in Window" context-menu wording, or for Measure-tool snap behaviour (unverified recollection: Measure shows snap points such as centre and midpoint when you hover, and the Ctrl lock applies there too).
- Not verified whether Fusion 2024-2026 changed the Emboss command, which was added in 2021-2022.

---

## 11. Which areas matter most to hobbyist/maker and small-robotics users (multi-part robots + 3D printing)?

### Takeaway
For the owner's goals (multi-part robots, 3D printing), the ranking is:
1. Components and joints.
2. Selection UX.
3. Local versions, autosave and recovery.
4. Import and editing of vendor STEP parts and STL meshes.
5. Physical materials for mass.
6. Sketch text and emboss.

Drawings, surfacing, decals, environments and contact sets come last. This is mostly inference, grounded in the findings above.

### Cited Findings
- **[3rd-party]** Maker robot-arm projects in Fusion model a base with servo mounts and links joined by revolute joints, then print them and drive them with servos and an Arduino. — [open-electronics: robotic arm](https://www.open-electronics.org/learn-how-to-design-and-control-a-robotic-arm-with-arduino-and-fusion-360/); [Fab Academy](https://fabacademy.org/2021/labs/ingegno/students/cristiano-lemes/assignments/week03/)
- **[3rd-party]** A recurring complaint from Fusion users trying FreeCAD (pre-1.0): editing an earlier feature breaks later ones (topological naming), and the overall feel is "Fusion just works" versus FreeCAD feeling like "trying to write Latin". — [Lemmy thread](https://lemm.ee/comment/7196372)
- **[Ondsel]** Users found the many conflicting FreeCAD assembly add-ons discouraging. Ondsel contrasted this with proprietary CAD, where you "just grab it and drag it". — [Ondsel: assembly workbench preview](https://www.ondsel.com/blog/assembly-workbench-preview/)
- **[Autodesk blog / Forum]** Fusion personal-use limits (10 active documents, export and drawing restrictions) are a hobbyist pain point. — [Autodesk blog: personal use changes](https://www.autodesk.com/products/fusion-360/blog/changes-to-fusion-360-for-personal-use/); [Forum: limitations of free version](https://forums.autodesk.com/t5/fusion-design-validate-document/specific-limitations-of-fusion-free-version/m-p/13194021)

### Inferences
- **[Inference] Suggested priority, highest first, for the owner's use case:**
  1. **Components plus an active-component model** (area 1). Nothing multi-part works the Fusion way without it.
  2. **Joints with Fusion picking UX:**
     - Rigid, Revolute, Slider, Cylindrical and Ball are already available in FreeCAD's solver.
     - Add Pin-slot and Planar, Ground, Rigid Group, As-built, Limits, Drive Joints, and Capture/Revert Position.
     - Motion Link and Motion Study come next. Contact Sets come last.
  3. **Selection UX:** window vs crossing drag, click-and-hold Select Other, filters and priority. This is a daily friction point and cheap to do.
  4. **Local-first file and version management:** a version list, recovery and a project folder. This protects work and replaces Fusion's cloud.
  5. **Import:**
     - Insert STEP as a component.
     - Insert STL/3MF/OBJ mesh, with mesh-to-solid conversion.
     - Insert DXF/SVG into a sketch.
     - Calibrated canvas.
  6. **Direct edits on imported bodies:** reuse Press Pull and add Delete Face and Move Face.
  7. **Physical materials:** density-based mass for components and assemblies, appearances separate.
  8. **Sketch Text and Emboss.**
  9. **Display presets:** visual styles and a section view toggle.
  10. **Drawings:** base and projected views, dimensions, PDF/DXF.
  11. **Surface basics:** Patch, Stitch, Thicken, Trim.
  12. **Decals, environments, contact sets.**
- **[Inference]** Much of the heavy lifting already exists in FreeCAD 1.1.4: the Ondsel solver, joint limits, simulation, BOM, exploded views, TechDraw and the mesh/STEP/3MF/DXF I/O. SciForge's remaining work is mostly Fusion-style UX layers over those engines, not new geometry kernels. The exceptions are contact sets (collision) and prismatic mesh conversion.

### Gaps
- No survey data found on which Fusion workspaces hobbyists actually use. The ranking above is reasoned, not measured.
