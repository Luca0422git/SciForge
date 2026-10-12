# FreeCAD 1.1.4 internals for sketch snapping/auto-constraints, the navigation cube and viewport orbit (SciForge route to Fusion-like behavior)

Source note: the main source is the local FreeCAD 1.1.4 tree at `/home/user/SciForge` (it carries full upstream git history, so 1.0-vs-1.1 dates come from `git log`). Citations are repo-relative paths with line numbers. Online pages could not be used: `wiki.freecad.org` is refused by the sandbox proxy (HTTP 403 on CONNECT). The only web source is one search result on the 1.1 release. Claims about how *Fusion* behaves are not researched here (other researchers cover that). They appear only where the SciForge repo's own notes make them, and they are marked as such.

## Q1. Orbit / viewport navigation: styles, parameters, defaults, and the combination closest to Fusion (Shift+middle orbit, middle pan, zoom at cursor, constrained "up" orbit)

### Takeaway
`Gui::RevitNavigationStyle` is the only built-in style that maps middle-drag to pan and Shift+middle-drag to orbit. SciForge already selects it, along with `ZoomAtCursor=True`. For an orbit that keeps the world up axis vertical (like Fusion's Constrained Orbit), the direct route is `OrbitStyle = 2` ("Free Turntable"). It turns about world Z and tilts about the screen X axis, with no roll. Optionally `RotationMode = 1` orbits about the model point under the cursor. All of this can be set from Python through `App.ParamGet("User parameter:BaseApp/Preferences/View")`, and the change reaches open views live. No C++ is needed unless SciForge wants Y-up turntable or a different pivot behavior.

### Cited Findings

**Navigation style classes and mouse mapping**
- The styles live in `src/Gui/Navigation/`: Blender, CAD, Gesture, Inventor, MayaGesture, OpenCascade, OpenSCAD, Revit, SiemensNX, SolidWorks, TinkerCAD and Touchpad (`*NavigationStyle.cpp`). The base class and orbit math are in `NavigationStyle.cpp`. — [src/Gui/Navigation/](src/Gui/Navigation/)
- Revit style help strings: selection "Press left mouse button", panning "Press middle mouse button", orbit (DRAGGING) "Press Shift and middle mouse button", zoom "Scroll middle mouse button". — [src/Gui/Navigation/RevitNavigationStyle.cpp:47-60](src/Gui/Navigation/RevitNavigationStyle.cpp)
- Revit's state machine:
  - `BUTTON3DOWN` (middle) and `BUTTON1DOWN|BUTTON2DOWN` mean PANNING.
  - `SHIFTDOWN|BUTTON3DOWN` means DRAGGING (orbit). It calls `saveCursorPosition(ev)` first, which fixes the orbit pivot.
  - `CTRLDOWN|BUTTON3DOWN` and `CTRL|SHIFT|BUTTON2` mean ZOOMING.
  - Releasing the middle button while Shift is still held ends the orbit.
  
  — [src/Gui/Navigation/RevitNavigationStyle.cpp:234-294](src/Gui/Navigation/RevitNavigationStyle.cpp)
- In Revit style, a short middle click (shorter than the Qt double-click interval, with no drag) calls `lookAtPoint(pos)`, which re-centres the view on the clicked point. Pressing left or right while panning or zooming switches to orbit ("Alternative way of rotating"). — [src/Gui/Navigation/RevitNavigationStyle.cpp:118-190](src/Gui/Navigation/RevitNavigationStyle.cpp)
- Other styles use different mappings:
  - Blender: middle = orbit, Shift+middle = pan.
  - SolidWorks: middle = orbit, Ctrl+middle = pan.
  - CAD (FreeCAD's default style): middle = pan, middle+left or middle+right = orbit.
  
  — [BlenderNavigationStyle.cpp:46-57](src/Gui/Navigation/BlenderNavigationStyle.cpp); [SolidWorksNavigationStyle.cpp:46-58](src/Gui/Navigation/SolidWorksNavigationStyle.cpp); [CADNavigationStyle.cpp:49-55](src/Gui/Navigation/CADNavigationStyle.cpp)
- The `NavigationStyle` parameter (ASCII, in group View) defaults to `Gui::CADNavigationStyle` and is applied live to every viewer through `setNavigationType`. — [src/Gui/View3DSettings.cpp:288-298](src/Gui/View3DSettings.cpp); [src/Gui/PreferencePackTemplates/View.cfg:27](src/Gui/PreferencePackTemplates/View.cfg)
- `setNavigationType` creates a new style instance. It copies only the panning plane, menu flag, animation flags and orbit style (`operator=`). The new instance's `initialize()` re-reads `InvertZoom`, `ZoomAtCursor`, `ZoomStep` and `RotationMode` from the parameters, and resets sensitivity to 2.0. — [src/Gui/View3DInventorViewer.cpp:1677-1703](src/Gui/View3DInventorViewer.cpp); [src/Gui/Navigation/NavigationStyle.cpp:318-397](src/Gui/Navigation/NavigationStyle.cpp)

**Orbit styles (`OrbitStyle`, Int, `User parameter:BaseApp/Preferences/View`)**
- The enum order is: 0 Turntable, 1 Trackball, 2 FreeTurntable, 3 TrackballClassic, 4 RoundedArcball. The projector's built-in default is RoundedArcball. — [src/Gui/Navigation/NavigationStyle.cpp:68-75, 279](src/Gui/Navigation/NavigationStyle.cpp)
- Defaults in 1.1.4 are 4 (Rounded Arcball) everywhere: in `View3DSettings` (`GetInt("OrbitStyle", 4)`), in the preference page, in the .ui `currentIndex` and in the preference-pack template. — [src/Gui/View3DSettings.cpp:299-304](src/Gui/View3DSettings.cpp); [src/Gui/PreferencePages/DlgSettingsNavigation.cpp:172-176](src/Gui/PreferencePages/DlgSettingsNavigation.cpp); [src/Gui/PreferencePackTemplates/View.cfg:28](src/Gui/PreferencePackTemplates/View.cfg)
- The preference tooltip describes each style:
  - "Rounded Arcball: moving the mouse in the corners of the screen will only roll the part."
  - "Trackball: moving the mouse horizontally will rotate the part around the Y-axis."
  - "Trackball Classic: … allowing precession."
  - "Turntable: the part will be rotated around the Z-axis (with constrained axes)."
  - "Free Turntable: the part will be rotated around the Z-axis."
  
  — [src/Gui/PreferencePages/DlgSettingsNavigation.ui:~455-475](src/Gui/PreferencePages/DlgSettingsNavigation.ui)
- Turntable math (`getTurntable`): for each mouse step, the code checks whether the vertical or horizontal component of the drag dominates.
  - If vertical dominates, it rotates about the camera's own X axis (screen horizontal), which tilts the view.
  - Otherwise it rotates about **world Z**, transformed into camera space with `worldToScreen`. The sign is flipped when the camera is upside down.
  - So it applies one axis per event and never rolls.
  
  — [src/Gui/Navigation/NavigationStyle.cpp:228-259](src/Gui/Navigation/NavigationStyle.cpp)
- Free Turntable: `spin()` splits each mouse move into a horizontal part and a vertical part (`midpos`) and runs `spinInternal` twice. Both components are applied in the same step, through the same turntable math (world-Z yaw plus screen-X tilt). — [src/Gui/Navigation/NavigationStyle.cpp:1103-1128, 1205-1218](src/Gui/Navigation/NavigationStyle.cpp)
- Trackball Classic composes a rotation about screen X by `dif[1]` with a rotation about screen Y by `-dif[0]`. — [src/Gui/Navigation/NavigationStyle.cpp:261-275](src/Gui/Navigation/NavigationStyle.cpp)
- For Trackball, TrackballClassic and RoundedArcball only, when the pivot is a picked scene point, the virtual trackball sphere is re-centred on the pivot's screen position and scaled. Turntable styles do not use this. — [src/Gui/Navigation/NavigationStyle.cpp:1130-1155](src/Gui/Navigation/NavigationStyle.cpp)
- The rotation angle is multiplied by `Sensitivity` (Float, View, default 2.0) only when it is greater than 1.0. — [src/Gui/Navigation/NavigationStyle.cpp:1166-1173](src/Gui/Navigation/NavigationStyle.cpp); [src/Gui/View3DSettings.cpp:305-310](src/Gui/View3DSettings.cpp)
- After the rotation is computed, `reorientCamera(cam, r, rotationCenter)` is called when a rotation centre was found; otherwise `reorientCamera(cam, r)` is called. — [src/Gui/Navigation/NavigationStyle.cpp:1175-1181](src/Gui/Navigation/NavigationStyle.cpp)

**Rotation centre (`RotationMode`, Int, View)**
- The preference combo offers "Window center" (0), "Drag at cursor" (1) and "Object center" (2). The tooltip reads "Rotations in 3D will use current cursor position as center for rotation". — [src/Gui/PreferencePages/DlgSettingsNavigation.ui:521-555](src/Gui/PreferencePages/DlgSettingsNavigation.ui)
- The modes map to flags as follows:
  - 0 means `WindowCenter`: the pivot is the camera focal point at screen centre.
  - 1 means `ScenePointAtCursor | FocalPointAtCursor`: the pivot is the model point under the cursor when the drag starts. If no model is under the cursor, it is the cursor's point on the focal plane.
  - 2 means `ScenePointAtCursor | BoundingBoxCenter`: the pivot is the picked model point if there is one, otherwise the centre of the whole scene's bounding box.
  
  — [src/Gui/Navigation/NavigationStyle.cpp:380-397, 1291-1360](src/Gui/Navigation/NavigationStyle.cpp)
- Defaults are inconsistent:
  - `NavigationStyle::initialize()` and the preference page use 0 (Window center), and the template has `RotationMode` 0.
  - `View3DSettings::OnChange("RotationMode")` falls back to 1. That fallback is used only when the parameter changes, and `RotationMode` is not in `applySettings()`. The value is picked up only when a style instance is created or the parameter is written.
  
  — [src/Gui/Navigation/NavigationStyle.cpp:380-382](src/Gui/Navigation/NavigationStyle.cpp); [src/Gui/View3DSettings.cpp:72-118, 335-358](src/Gui/View3DSettings.cpp); [src/Gui/PreferencePackTemplates/View.cfg:33](src/Gui/PreferencePackTemplates/View.cfg)
- `ShowRotationCenter` (Bool, View, default true) draws a marker at the pivot. Its size is `RotationCenterSize` (Float, default 5.0) and its colour is `RotationCenterColor` (Unsigned, default 4278190131 = 0xFF000033, red). — [src/Gui/View3DInventorViewer.cpp:1598-1620](src/Gui/View3DInventorViewer.cpp); [DlgSettingsNavigation.ui](src/Gui/PreferencePages/DlgSettingsNavigation.ui)

**Zoom and animation parameters (all in `User parameter:BaseApp/Preferences/View`)**
- `ZoomAtCursor` (Bool) defaults to true. `doZoom` pans the camera so the point under the cursor stays fixed while zooming. — [src/Gui/Navigation/NavigationStyle.cpp:374-376, 979-1000](src/Gui/Navigation/NavigationStyle.cpp); [src/Gui/View3DSettings.cpp:323-328](src/Gui/View3DSettings.cpp)
- `ZoomStep` (Float) defaults to 0.2 (.ui, template and `initialize()`); the .ui range is 0.01-1.0. A wheel event zooms by `zoomStep * delta/120`, negated when `InvertZoom` is true. `View3DSettings::OnChange` uses a fallback of 0.0, which only matters if the parameter is removed while FreeCAD runs. — [src/Gui/Navigation/NavigationStyle.cpp:377-379, 965-972](src/Gui/Navigation/NavigationStyle.cpp); [src/Gui/View3DSettings.cpp:329-334](src/Gui/View3DSettings.cpp)
- `InvertZoom` (Bool) defaults to true. — [src/Gui/Navigation/NavigationStyle.cpp:371-373](src/Gui/Navigation/NavigationStyle.cpp); [View.cfg:24](src/Gui/PreferencePackTemplates/View.cfg)
- `UseNavigationAnimations` (Bool) defaults to true and `UseSpinningAnimations` (Bool) to false. `AnimationDuration` (Int, ms) defaults to 500 with a .ui range of 100-10000. `NavigationAnimationEasingCurve` (Int, a QEasingCurve type) defaults to InOutCubic and has no UI. — [src/Gui/View3DSettings.cpp:387-396](src/Gui/View3DSettings.cpp); [src/Gui/View3DInventorViewer.cpp:3918-3955](src/Gui/View3DInventorViewer.cpp)
- Camera changes made with `setCameraOrientation` (NaviCube clicks, standard views, Python `view.setCameraOrientation`) animate when animations are enabled. Otherwise the camera is set directly while keeping the focal point. — [src/Gui/Navigation/NavigationStyle.cpp:515-560](src/Gui/Navigation/NavigationStyle.cpp)

**Python access**
- The View3D Python object exposes:
  - `getNavigationType()` / `setNavigationType()` (per view)
  - `setCameraOrientation(rot[, move])`
  - `getCameraOrientation()`
  - `setAnimationEnabled()` / `isAnimationEnabled()`
  - `viewDefaultOrientation(ori_str, scale)`
  - `addEventCallback`, `getCameraNode`, `getViewer`
  
  The `NavigationStyle` Python class itself exposes nothing ("This is the base class for navigation styles"). — [src/Gui/View3DPy.cpp:84-278, 885-915](src/Gui/View3DPy.cpp); [src/Gui/Navigation/NavigationStyle.pyi](src/Gui/Navigation/NavigationStyle.pyi)
- FreeCAD's own Python status-bar navigation indicator (Tux) changes these preferences with `App.ParamGet("User parameter:BaseApp/Preferences/View")`. This is a working in-tree example of the Python route. — [src/Mod/Tux/NavigationIndicatorGui.py:31-33](src/Mod/Tux/NavigationIndicatorGui.py)
- `View3DSettings` observes the View group, so writing `NavigationStyle`, `OrbitStyle`, `Sensitivity`, `InvertZoom`, `ZoomAtCursor`, `ZoomStep`, `RotationMode`, `UseNavigationAnimations` or `ShowNaviCube` updates all open viewers immediately. — [src/Gui/View3DSettings.cpp:288-416](src/Gui/View3DSettings.cpp)

**What SciForge sets today**
- `theme.py` `VIEWER_SETTINGS` sets:
  - `NavigationStyle = "Gui::RevitNavigationStyle"` and `ZoomAtCursor = True`
  - background colours
  - NaviCube `BaseColor`, `EmphaseColor` and `HiliteColor`
  
  It does **not** set `OrbitStyle`, `RotationMode`, `ZoomStep`, `InvertZoom` or the animation settings. It records each parameter's previous existence and value and restores both on disable. — [src/Mod/SciForge/sciforge/theme.py:139-218](src/Mod/SciForge/sciforge/theme.py)
- The SciForge GUI tests turn `UseNavigationAnimations` off. — [src/Mod/SciForge/SciForgeTests/gui/journey_gui.py:149](src/Mod/SciForge/SciForgeTests/gui/journey_gui.py); [harness.py:531](src/Mod/SciForge/SciForgeTests/gui/harness.py)
- The project notes say: "FreeCAD's 'Revit' navigation style is exactly Fusion's default mouse mapping." — [MEMORY.md:343](MEMORY.md)
- The spec asks for "Navigation matching Fusion: orbit, pan, zoom to cursor, zoom window, fit, look-at, orbit-around-selection…" (section 7.14). — [docs/sciforge/feature-outline.md:201-203](docs/sciforge/feature-outline.md)

**1.0 vs 1.1**
- Trackball Classic was added on 2025-04-28 (commit 8d2cb99712, #20535). Commit 3fcadd01f5 (2025-05-02) made Rounded Arcball the default. It changed the defaults from `OrbitStyle` 1 (Trackball) and `RotationMode` 1 (Drag at cursor) to `OrbitStyle` 4 and `RotationMode` 0. These commits postdate 1.0, so in 1.0 the defaults were Trackball and Drag at cursor, and the Trackball Classic and Rounded Arcball styles did not exist. — `git show 3fcadd01f5`, `git log -S TrackballClassic` in the local repo
- Free Turntable has existed since 2022-12-20 (commit 9cda82cf20, #8048). — local `git log`
- A third-party article on the 1.1 release says "Rounded Arcball" is the new default orbit style and that "Trackball Classic" was added. — [alternativeto.net](https://alternativeto.net/news/2026/3/freecad-1-1-adds-three-point-lighting-part-design-previews-and-major-fem-upgrades) (search snippet only)

### Inferences
- **Recommended Python-only settings**, applied in `theme.VIEWER_SETTINGS` with the same save/restore pattern:
  - `NavigationStyle = "Gui::RevitNavigationStyle"` (already set)
  - `OrbitStyle = 2` (Free Turntable)
  - `RotationMode = 1` (pivot at the picked point), or 0 for the screen centre
  - `ZoomAtCursor = True` (already set)
  - `InvertZoom` and `ZoomStep` chosen to match Fusion's wheel direction and step (to confirm against the Fusion research)
  - `UseNavigationAnimations = True`, `AnimationDuration` of about 300-500
  - `ShowRotationCenter` set to taste

  Write `NavigationStyle` **before** the others, because switching style creates a new instance that resets sensitivity to 2.0 and re-reads the other parameters.
- Free Turntable is the closest built-in match to a "constrained orbit" because each step is world-Z yaw plus screen-X pitch, with no roll. Turntable (0) applies only one axis per mouse event, so diagonal drags feel stepped. Trackball, Trackball Classic and Rounded Arcball allow roll and do not keep the up axis vertical.
- The turntable axis is hard-wired to world **Z** (`SbVec3f zaxis(0, 0, 1)` at NavigationStyle.cpp:243). If SciForge ever adopts a Y-up convention, which the project notes list as an open Fusion-parity decision ([MEMORY.md:330-331](MEMORY.md)), it needs a C++ change in `getTurntable`, for example reading an "up axis" parameter. That would be a small, self-contained core patch.
- Because the pivot is fixed in `saveCursorPosition`, "orbit around the selection" (from the spec) is not a built-in mode. Two ways to get it:
  - C++: add a `RotationCenterMode` that uses the selection's bounding-box centre.
  - Python: call `NavigationStyle::setRotationCenter`. It has no Python binding, so this route would need a binding or the pivy camera.
- Revit's middle-click re-centre (`lookAtPoint`) and its Ctrl+middle zoom drag are extras. They can be left alone unless they conflict with Fusion's behavior.

### Gaps
- Fusion's exact defaults (wheel direction, zoom step, whether orbit pivots on the cursor point or the screen centre, spin after release) were not researched here. These decide `InvertZoom`, `ZoomStep` and `RotationMode`.
- The FreeCAD wiki pages "Mouse navigation" and the 1.1 release notes could not be fetched (proxy 403), so they are not cross-checked.
- Whether 1.0.x point releases backported the new orbit defaults was not verified. The commit dates suggest they did not.

## Q2. Navigation cube (NaviCube): geometry, configurable parameters, click-to-view mapping, animation, orientation conventions, and whether a Python/Coin replacement is viable

### Takeaway
The NaviCube is a single C++ class (`NaviCubeImplementation` in `src/Gui/NaviCube.cpp`, 1411 lines). It draws a chamfered cube, edge and corner facets, 2D "flat buttons" (four orbit arrows, two roll arrows, a back-side dot and a view-menu icon) and an XYZ axis tripod, all with legacy fixed-function OpenGL and no lighting. Clicks are picked through a colour-coded offscreen framebuffer and become animated `setCameraOrientation` calls.
- **Parameters can change** size, chamfer, colours, border width, fonts, labels, corner and offset, opacity, the tripod, rotate-to-nearest and the arrow step.
- **Parameters cannot change** the shape, shading, the set of buttons, a Home button, drag-to-orbit on the cube, or the menu's command list. The menu is a QMenu, so it can be edited from Python.

Two direct routes exist:
- **(a)** A small C++ patch to `NaviCube.cpp`, which needs a full build.
- **(b)** Hiding the cube (`ShowNaviCube=False`) and drawing a Python QWidget overlay that calls `view.setCameraOrientation()`. It gets FreeCAD's animation for free and can be shipped as a quick update.

### Cited Findings

**Integration**
- The cube is created per viewer and drawn after the scene in each render path. It sees mouse events before the navigation style: `if (naviCubeEnabled && naviCube->processSoEvent(ev))`. — [src/Gui/View3DInventorViewer.cpp:701-702, 2522, 2555, 2684, 2829](src/Gui/View3DInventorViewer.cpp)
- The settings object `NaviCubeSettings` is bound to `User parameter:BaseApp/Preferences/NaviCube`. It listens to the parameter manager's global `signalParamChanged` and dispatches by parameter name. — [src/Gui/View3DInventor.cpp:235-236](src/Gui/View3DInventor.cpp); [src/Gui/View3DSettings.cpp:556-675](src/Gui/View3DSettings.cpp)
- `ShowNaviCube` (Bool) lives in the **View** group, not the NaviCube group, and defaults to true. It is applied live through `setEnabledNaviCube`. — [src/Gui/View3DSettings.cpp:414-418](src/Gui/View3DSettings.cpp); [View.cfg:37](src/Gui/PreferencePackTemplates/View.cfg)

**Geometry (`prepare()`)**
- Coordinates use Z up. The main faces are built by `addCubeFace(xdir, normal, …)`:
  - Top: normal +Z
  - Front: normal -Y, so the Front view looks from -Y toward +Y with Z up
  - Left: -X
  - Rear: +Y
  - Right: +X
  - Bottom: -Z
  
  There are 8 corner facets (hexagons), 12 edge facets (rectangles) and the flat buttons. — [src/Gui/NaviCube.cpp:702-762](src/Gui/NaviCube.cpp)
- Each main face is an octagon (`1 - 2·chamfer` and `1 - 4·chamfer`). Edge facets have half-width `chamfer`. Corner hexagons are built from `chamfer`. The label quad spans `±(1 - 2·chamfer)`. Each face stores a "standard orientation" `SbRotation`, which is the camera orientation used when that facet is clicked. — [src/Gui/NaviCube.cpp:619-693](src/Gui/NaviCube.cpp)
- The `PickId` list covers 6 faces, 12 edges, 8 corners, ArrowNorth/South/East/West, ArrowRight/Left (roll), DotBackside and ViewMenu. There is no "Home" id. — [src/Gui/NaviCube.cpp:84-121](src/Gui/NaviCube.cpp)
- The flat buttons are hard-coded 2D polygons:
  - the curved roll arrows
  - triangle arrows at the four sides
  - the view-menu icon, an isometric-cube glyph at (0.84, 0.84)
  - a 16-gon dot at (+87, -87), the backside button
  
  — [src/Gui/NaviCube.cpp:549-617](src/Gui/NaviCube.cpp)

**Rendering (`drawNaviCube`)**
- The cube is drawn with fixed-function GL: `glDisable(GL_LIGHTING)`, so every facet is a flat `BaseColor`, or `HiliteColor` when hovered.
  - Face outlines are drawn as lines in `EmphaseColor` with width `BorderWidth`.
  - Labels are textures tinted with `EmphaseColor`.
  - The XYZ tripod is drawn at the cube corner from (-1.1, -1.1, -1.1) in `AxisXColor`, `AxisYColor` and `AxisZColor` when `ShowCS` is on.
  - The projection is ortho or perspective to match the 3D camera.
  
  — [src/Gui/NaviCube.cpp:805-1002](src/Gui/NaviCube.cpp) (lighting off at 835, tripod at 886, faces at 918, labels at 948, flat buttons at 968)
- When the cursor is not hovering, the whole cube is drawn at `InactiveOpacity`. — [src/Gui/NaviCube.cpp:764-773](src/Gui/NaviCube.cpp)
- Label textures are 192 px images painted with QPainter. The default font is "Arial" (`FontString`), with `FontWeight`, `FontStretch` and `FontZoom` applied. — [src/Gui/NaviCube.cpp:476-547](src/Gui/NaviCube.cpp)
- Picking redraws the cube into an offscreen FBO with the `PickId` encoded in the red channel and reads one pixel back. — [src/Gui/NaviCube.cpp:1035-1063](src/Gui/NaviCube.cpp)

**Clicks, animation and dragging**
- On release, a click on a face, edge or corner calls `setCameraOrientation(orientation)`. The orientation is the facet's standard orientation, or `getNearestOrientation` when `NaviRotateToNearest` is on. Nearest means the roll closest to the current camera: four candidates for faces and edges, six for corners. — [src/Gui/NaviCube.cpp:1079-1174, 1176-1241](src/Gui/NaviCube.cpp)
- Flat buttons:
  - The arrows rotate by `2π / NaviStepByTurn` (clamped to 4-36, default 8, so 45°) about the screen axes. ArrowLeft/Right roll about the view axis.
  - DotBackside rotates 180°.
  - Repeated clicks during an animation accumulate onto the target orientation.
  - ViewMenu opens the QMenu.
  
  — [src/Gui/NaviCube.cpp:1211-1238](src/Gui/NaviCube.cpp)
- Camera moves animate through `NavigationStyle::setCameraOrientation` and `View3DInventorViewer::startAnimation`, using `AnimationDuration` (500 ms) and `NavigationAnimationEasingCurve` (InOutCubic) when `UseNavigationAnimations` is on. — [src/Gui/Navigation/NavigationStyle.cpp:515-560](src/Gui/Navigation/NavigationStyle.cpp); [src/Gui/View3DInventorViewer.cpp:3918-3955](src/Gui/View3DInventorViewer.cpp)
- Dragging the cube **moves the widget** within the view. It does not orbit, and only works when "Movable Navigation Cube" (`NaviCubeDraggableCmd`) is checked and the press started in the central quarter (`inDragZone`). The cube has no drag-to-orbit. — [src/Gui/NaviCube.cpp:1251-1289, 1335-1372](src/Gui/NaviCube.cpp)
- The default menu contains `Std_OrthographicCamera`, `Std_PerspectiveCamera`, `Std_ViewIsometric`, `Std_ViewFitAll`, `Std_ViewFitSelection`, `Std_AlignToSelection` and `NaviCubeDraggableCmd`. It is a `QMenu` with objectName `"NaviCube_Menu"`, parented to the main window. A static C++ list (`NaviCube::setNaviCubeCommands`) can replace it, but nothing calls that and it has no Python binding. — [src/Gui/NaviCube.cpp:1330-1333, 1374-1411](src/Gui/NaviCube.cpp)
- `Std_ViewHome` (key Home) restores `NewDocumentCameraOrientation` (default "Top" in this command) and then runs ViewFit. It is a normal command, not a cube button. — [src/Gui/CommandView.cpp:1346-1375](src/Gui/CommandView.cpp)

**Parameters (group `User parameter:BaseApp/Preferences/NaviCube` unless noted) and defaults**

| Parameter | Type | Default | In Preferences UI? | Source |
|---|---|---|---|---|
| CubeSize | Int | 132 px | yes | View3DSettings.cpp:609-611; NaviCube.cpp:228 |
| ChamferSize | Float | 0.12 | no (hidden) | View3DSettings.cpp:606-608 |
| CornerNaviCube | Int | 1 (TopRight; 0 TL, 2 BL, 3 BR) | yes | View3DSettings.cpp:600-602; NaviCube.h:43-48 |
| OffsetX / OffsetY | Int | 0 / 0 | no | View3DSettings.cpp:603-605 |
| NaviRotateToNearest | Bool | true | yes | View3DSettings.cpp:612-614 |
| NaviStepByTurn | Int | 8 | yes | View3DSettings.cpp:615-617 |
| BaseColor | Unsigned RGBA | 3806916544 = 0xE2E8EFC0 (226,232,239, alpha 192) | yes | View3DSettings.cpp:630-635 |
| EmphaseColor | Unsigned | black or white, chosen from BaseColor brightness | no | View3DSettings.cpp:636-641 |
| HiliteColor | Unsigned | 2867003391 = 0xAAE2FFFF | no | View3DSettings.cpp:642-645 |
| BorderWidth | Float | 1.1 | no | View3DSettings.cpp:646-648 |
| ShowCS | Bool | true | no | View3DSettings.cpp:649-651 |
| InactiveOpacity | Int (%) | 50 | yes | View3DSettings.cpp:652-655 |
| FontString | ASCII | "" (uses Arial) | yes | View3DSettings.cpp:621-623 |
| FontZoom | Float | 0.3 | no | View3DSettings.cpp:618-620 |
| FontWeight / FontStretch | Int | 0 / 0 | no | View3DSettings.cpp:624-629 |
| TextFront/TextTop/TextRight/TextRear/TextBottom/TextLeft | ASCII | translated "FRONT", "TOP", "RIGHT", "REAR", "BOTTOM", "LEFT" | no | View3DSettings.cpp:656-672 |
| ShowNaviCube (View group) | Bool | true | yes | View3DSettings.cpp:414-418 |

(The .ui file confirms the UI-exposed entries and defaults: CubeSize 132, CornerNaviCube 1, NaviRotateToNearest true, NaviStepByTurn 8, InactiveOpacity 50, BaseColor rgb(226,232,239). — [src/Gui/PreferencePages/DlgSettingsNavigation.ui](src/Gui/PreferencePages/DlgSettingsNavigation.ui))

**What SciForge does with the cube today**
- It sets only colours: `BaseColor = 0xF0F0F0E6`, `EmphaseColor = #4a4f57`, `HiliteColor = #6fb7f0`. The comment reads "a light ViewCube with dark labels and a blue hover". — [src/Mod/SciForge/sciforge/theme.py:148-161](src/Mod/SciForge/sciforge/theme.py)
- "ViewCube shape" is still an open item in MEMORY. The spec asks for a "ViewCube with identical interaction (click faces/edges/corners, drag-orbit, home)". — [MEMORY.md:100](MEMORY.md); [docs/sciforge/feature-outline.md:203](docs/sciforge/feature-outline.md)

**1.0 vs 1.1**
- `NaviCube.cpp` changes after 1.0 (Nov 2024) were maintenance only:
  - HiDPI fix (2025-03-01, 7f70feb9f4)
  - flat-button animation accumulation (2025-02-19, ad84f57ceb)
  - framebuffer re-creation (2025-07-17, 6ef6a70822)
  - Color/Qt/OpenGL clean-ups and reformatting
  
  The cube's design and parameters are essentially the same in 1.0 and 1.1. — local `git log -- src/Gui/NaviCube.cpp`

### Inferences
- **Parameter-only tuning** (Python, already the SciForge pattern):
  - `ChamferSize` of about 0.06-0.08 makes edges and corners thin hot-zones on a more box-like cube.
  - Lower `BorderWidth` (about 0.6-0.8).
  - `ShowCS=False` if the tripod is unwanted.
  - `InactiveOpacity` of about 80-100, unless the Fusion research says the cube fades.
  - `NaviRotateToNearest=False` makes clicks always land in the standard "up" orientation.
  - `TextRear` relabelled if wanted. The CLAUDE.md rule "copy Fusion's behavior, never its assets, wording" applies here.
  - `CubeSize` and `CornerNaviCube`.
  - Edit the `NaviCube_Menu` QMenu(s) from Python (`mw.findChildren(QtWidgets.QMenu, "NaviCube_Menu")`) to add Home or other commands. There is one menu per viewer, so new views need hooking.
- **Needs C++** in `NaviCube.cpp`:
  - per-face shading
  - a Home button (a new `PickId` plus `addButtonFace` geometry plus a `mouseReleased` branch that runs `Std_ViewHome` or a stored home pose)
  - drag-to-orbit (in `mouseMoved`, when not in movable mode, call the navigation style's spin or rotate the camera by mouse delta)
  - removing or replacing the arrows or the backside dot
  - hover highlighting that groups facets

  All of this is confined to one file. It needs a `SCIFORGE:` comment, an entry in `docs/sciforge/core-patches.md` and a full build.
- **Python replacement** (the Fusion look without a rebuild):
  1. Set `ShowNaviCube=False` (View group, applied live).
  2. Add a translucent `QWidget` child over the 3D view's GL viewport. SciForge's `NavBar` already floats a QWidget over the view ([navbar_ui.py](src/Mod/SciForge/sciforge/navbar_ui.py)). The viewport is a `QOpenGLWidget`, so child widgets composite correctly (NaviCube.cpp:1043 casts `viewport()` to `QOpenGLWidget`).
  3. Paint the cube with QPainter from the camera orientation (`view.getCameraOrientation()`, or the pivy camera node's `orientation` with an `SoFieldSensor` to repaint).
  4. Hit-test in 2D.
  5. On click, call `view.setCameraOrientation(Rotation)`. It animates with FreeCAD's duration and easing (NavigationStyle.cpp:540-542).
  6. For drag-orbit, rotate the pivy camera directly per mouse move. `setCameraOrientation` would start a new animation on each move when animations are on.
  7. For Home, store or restore a camera pose.

  This fits SciForge's quick-update path ([MEMORY.md:346-349](MEMORY.md)) and its rule that pivy and Qt hooks only schedule work through `QTimer`.
- Orientation convention: in FreeCAD, Front looks along **+Y** (camera on -Y) with **Z up**; Top looks down -Z; Right looks along -X. A cube that matches Fusion only by labels keeps FreeCAD's Z-up mapping. If SciForge chooses Y-up parity, the face-to-orientation table must be remapped (C++ `prepare()`, or a Python overlay's own table) and the turntable axis changed too (see Q1).

### Gaps
- Fusion's ViewCube details (exact hot-zones, whether a compass or roll arrows exist, Home icon placement, fade behavior, label words) were not researched here.
- The wiki page "Navigation Cube" could not be fetched (proxy 403).
- No test checked whether `ChamferSize = 0` is safe. Edge and corner facets would collapse to zero area and become unpickable.

## Q3. Sketcher snapping, auto-constraints, on-view parameters (OVP), colours and constraint icons: what exists in 1.1.4, what is tunable, what is missing for Fusion-like inference

### Takeaway
FreeCAD 1.1.4 has a `SnapManager` with the following priority order:
1. angle snap while **Ctrl** is held (step `SnapAngle`, default 5°)
2. snap to the pre-selected point or curve (including the midpoints of lines and arcs and the H/V axes)
3. grid snap

Auto-constraint suggestions come from `DrawSketchHandler::seekAutoConstraint`. They cover only Coincident, PointOnObject, Symmetric (line midpoint), Tangent (to circles, arcs and ellipses), and Horizontal or Vertical within a hard-coded 2°. They appear as 16 px constraint icons fused into the mouse cursor. On-view parameters (OVP: in-view length, angle and position boxes) are close to Fusion's heads-up dimension inputs.

Missing compared with Fusion-style inference:
- dashed alignment and inference lines to other points
- snapping to another point's X or Y
- parallel and perpendicular suggestions toward non-adjacent lines

These need C++ in `SnapManager` and `DrawSketchHandler`, plus an `EditModeCoinManager` drawing hook. Everything parameter-driven (on/off switches, colours, widths, sizes, OVP visibility, Autoconstraints) can be set from Python and is applied live.

### Cited Findings

**Auto-constraints (while drawing)**
- `seekAutoConstraint(suggested, Pos, Dir, type)` returns nothing when the view-provider property `Autoconstraints` is false. Otherwise it runs, in order:
  1. `seekPreselectionAutoConstraint`
  2. `seekAlignmentAutoConstraint`, when the direction is non-zero and type is not CURVE
  3. `seekTangentAutoConstraint`, unless type is VERTEX_NO_TANGENCY
  
  — [src/Mod/Sketcher/Gui/DrawSketchHandler.cpp:741-765](src/Mod/Sketcher/Gui/DrawSketchHandler.cpp)
- Preselection-based suggestions:
  - Cursor on a vertex (or the root point): Coincident.
  - Cursor on a curve: PointOnObject, or Symmetric when within 5% of the line length from the line's midpoint (`isLineCenterAutoConstraint`).
  - Cursor on the H or V axis: PointOnObject.
  - CURVE targets get Tangent, rejected when the drawing direction is within about 6° of the hit line (|cos| > 0.995).
  
  — [src/Mod/Sketcher/Gui/DrawSketchHandler.cpp:433-544](src/Mod/Sketcher/Gui/DrawSketchHandler.cpp)
- Alignment: Horizontal if the drawing direction is within **2°** of horizontal, Vertical if within 2° of vertical (`angleDevRad = toRadians(2)`, hard-coded). — [src/Mod/Sketcher/Gui/DrawSketchHandler.cpp:546-571](src/Mod/Sketcher/Gui/DrawSketchHandler.cpp)
- Tangent inference scans all circles, arcs, ellipses and arcs of ellipse for a line heading tangentially, with tolerance `0.1 * scaleFactor`. There is **no** Parallel or Perpendicular inference, and no inference toward lines. — [src/Mod/Sketcher/Gui/DrawSketchHandler.cpp:573-739](src/Mod/Sketcher/Gui/DrawSketchHandler.cpp)
- `AutoConstraint::TargetType` is one of `VERTEX`, `CURVE` or `VERTEX_NO_TANGENCY`. — [src/Mod/Sketcher/Gui/AutoConstraint.h:35-41](src/Mod/Sketcher/Gui/AutoConstraint.h)
- The icons near the cursor work like this:
  - `seekAndRenderAutoConstraint` calls `renderSuggestConstraintsCursor`.
  - That maps each suggestion to an SVG (`Constraint_Horizontal`, `Constraint_Vertical`, `Constraint_PointOnPoint`, `Constraint_PointOnObject`, `Constraint_Symmetric`, `Constraint_Tangent`) at 16 px.
  - `Gui::ToolHandler::addCursorTail` composites them to the right of the cursor pixmap. They are part of the **mouse cursor**, not Coin geometry.
  
  — [src/Mod/Sketcher/Gui/DrawSketchHandler.cpp:391-431, 929-950](src/Mod/Sketcher/Gui/DrawSketchHandler.cpp); [src/Gui/ToolHandler.cpp:184-215](src/Gui/ToolHandler.cpp)
- Example handler (new Line tool): in SeekFirst it seeks with direction (0, 0). In SeekSecond it seeks with `onSketchPos - startPoint` and enables angle snapping relative to `startPoint`. — [src/Mod/Sketcher/Gui/DrawSketchHandlerLine.h:99-125, 233-243](src/Mod/Sketcher/Gui/DrawSketchHandlerLine.h)
- On/off controls:
  - The `ViewProviderSketch` properties `Autoconstraints` and `AvoidRedundant` (both default true) are fed from `User parameter:BaseApp/Preferences/Mod/Sketcher/General` → `AutoConstraints` and `AvoidRedundantAutoconstraints` (Bool, default true), and update live.
  - The task panel's settings menu toggles the property, not the parameter.
  
  — [src/Mod/Sketcher/Gui/ViewProviderSketch.cpp:131-140, 306-315, 557-566](src/Mod/Sketcher/Gui/ViewProviderSketch.cpp); [src/Mod/Sketcher/Gui/TaskSketcherConstraints.cpp:866, 1035-1042](src/Mod/Sketcher/Gui/TaskSketcherConstraints.cpp)
- Related parameters (from the preference .ui files):
  - `AutoRemoveRedundants` (Mod/Sketcher, false)
  - `NotifyConstraintSubstitutions` (Mod/Sketcher/General, true)
  - `UnifiedCoincident` and `AutoHorVer` (Mod/Sketcher/Constraints, true, need a restart)
  - `UnifiedLineCommands` (Mod/Sketcher/Commands, false)
  
  — [src/Mod/Sketcher/Gui/SketcherSettings.ui](src/Mod/Sketcher/Gui/SketcherSettings.ui); [SketcherSettings.cpp:258-272](src/Mod/Sketcher/Gui/SketcherSettings.cpp)

**Snapping (SnapManager)**
- Parameters live in `User parameter:BaseApp/Preferences/Mod/Sketcher/Snap` and are observed live:
  - `Snap` (Bool, true): master switch
  - `SnapToObjects` (Bool, true)
  - `SnapToGrid` (Bool, false)
  - `SnapAngle` (Float, degrees, 5.0)
  
  — [src/Mod/Sketcher/Gui/SnapManager.cpp:66-121, 177-182](src/Mod/Sketcher/Gui/SnapManager.cpp)
- `snap()` priority:
  1. Angle snap, only when the handler enabled it **and** `keyboardModifiers() == Qt::ControlModifier`. It rounds the angle around the reference point to multiples of `SnapAngle`.
  2. Object snap, based on preselection:
     - a vertex or the origin gives the exact point
     - the H or V axis locks Y=0 or X=0 and continues to the grid snap
     - a curve gives the closest point, pulled to a line's midpoint within 5% of its length or to an arc's middle within 10% of its angle
  3. Grid snap per coordinate, with tolerance `gridSize / 5`. It works even when the grid is hidden.
  
  — [src/Mod/Sketcher/Gui/SnapManager.cpp:197-245, 247-330, 332-407](src/Mod/Sketcher/Gui/SnapManager.cpp)
- `SnapType` bits are Angle, Point, Edge and Grid. A handler can pass a mask. — [src/Mod/Sketcher/Gui/SnapManager.h](src/Mod/Sketcher/Gui/SnapManager.h)
- Object snap depends on preselection under the cursor, which comes from the Coin pick radius (View `PickRadius`, default 5.0 in the template). The snap handle is built in `ViewProviderSketch::mouseMove` before preselection is updated and before the handler gets the position. — [src/Mod/Sketcher/Gui/ViewProviderSketch.cpp:1452-1515](src/Mod/Sketcher/Gui/ViewProviderSketch.cpp); [View.cfg:31](src/Gui/PreferencePackTemplates/View.cfg)
- UI: the `Sketcher_Snap` toolbar command toggles `Snap` and has a drop-down with `SnapToObjects` and a `SnapAngle` spin box. `Sketcher_Grid` has a drop-down that includes `SnapToGrid`. — [src/Mod/Sketcher/Gui/Command.cpp:1165, 1249, 1307, 1407-1461, 1507-1545](src/Mod/Sketcher/Gui/Command.cpp)
- `SnapManager` dates from 2023-03-15 (commit 0f274c2e07): "creation of SnapManager class… Add snap to object. Add snap at angle". It is therefore in 1.0 as well. — local `git log`
- A recent 1.1 fix: "Sketcher: Fix snap to axis not working (#26558)" (3672610617). — local `git log -- src/Mod/Sketcher/Gui/SnapManager.cpp`

**On-view parameters (OVP)**
- `User parameter:BaseApp/Preferences/Mod/Sketcher/Tools` → `OnViewParameterVisibility` (Int): 0 None/Hidden, **1 "Dimensions only"** (the default), 2 "Position and dimensions". It is read when a tool starts. — [src/Mod/Sketcher/Gui/DrawSketchController.h:191-263](src/Mod/Sketcher/Gui/DrawSketchController.h); [src/Mod/Sketcher/Gui/SketcherSettings.cpp:172-176, 242-250](src/Mod/Sketcher/Gui/SketcherSettings.cpp)
- OVP boxes are `Gui::EditableDatumLabel` objects: a `QuantitySpinBox` attached to an `SoDatumLabel`, with a function of Positioning, Dimensioning or Forced. Forced boxes are always shown. — [src/Gui/EditableDatumLabel.h:30-86](src/Gui/EditableDatumLabel.h); [DrawSketchController.h:217-236](src/Mod/Sketcher/Gui/DrawSketchController.h)
- Keys and behaviour:
  - Tab moves focus to the next OVP (`tabShortcut` → `passFocusToNextOnViewParameter`).
  - U, J, R and F toggle the tool widget's first to fourth options.
  - M cycles the construction method.
  - `DrawSketchKeyboardManager` routes typed numbers and units into the parameters "while still allowing operation of shortcuts".
  - A `toggleDynamicOverride()` helper exists, but nothing in 1.1.4 calls it.
  
  — [DrawSketchController.h:536-539](src/Mod/Sketcher/Gui/DrawSketchController.h); [DrawSketchControllableHandler.h:184-207](src/Mod/Sketcher/Gui/DrawSketchControllableHandler.h); [DrawSketchDefaultHandler.h:453](src/Mod/Sketcher/Gui/DrawSketchDefaultHandler.h); [DrawSketchKeyboardManager.h:49-56](src/Mod/Sketcher/Gui/DrawSketchKeyboardManager.h)
- OVP preference support dates from 2023-11-07 (commit 0282d3844a). The OVP framework therefore predates 1.0. — local `git log`
- OVP colours come from View `ConstrainedDimColor` and `DeactivatedConstrDimColor`. — [DrawSketchController.h:160-189](src/Mod/Sketcher/Gui/DrawSketchController.h)
- Other cursor feedback:
  - `ShowCursorCoords` (Mod/Sketcher, true) shows the "(length, angle)" or "(w x h)" text by the cursor in `CursorTextColor`.
  - `ContinuousCreationMode` and `ContinuousConstraintMode` (Mod/Sketcher, true) keep tools running.
  - `ShowDialogOnDistanceConstraint` (Mod/Sketcher, true).
  
  — [DrawSketchHandler.cpp:1002-1050](src/Mod/Sketcher/Gui/DrawSketchHandler.cpp); [SketcherSettingsDisplay.ui](src/Mod/Sketcher/Gui/SketcherSettingsDisplay.ui)

**Colours, widths and constraint display (applied live by `EditModeCoinManager`'s parameter observer)**
- Colours (group View; defaults from the .ui files, which match `EditModeCoinManagerParameters.cpp`):

  | Parameter | Meaning | Default |
  |---|---|---|
  | `EditedEdgeColor` | normal (under-constrained) curves | white |
  | `FullyConstraintElementColor` | fully constrained element | 128,208,160 |
  | `FullyConstrainedColor` | whole sketch fully constrained | 0,255,0 |
  | `ConstructionColor` | construction curves | 0,0,220 |
  | `FullyConstraintConstructionElementColor` | fully constrained construction | 143,169,253 |
  | `InternalAlignedGeoColor` | internal alignment geometry | 178,178,127 |
  | `FullyConstraintInternalAlignmentColor` | fully constrained internal alignment | 222,222,200 |
  | `ExternalColor` | external geometry | 204,51,115 |
  | `ExternalDefiningColor` | external defining geometry | 204,51,153 |
  | `InvalidSketchColor` | invalid sketch | 255,109,0 |
  | `ConstrainedIcoColor` | constraint glyphs | 255,38,0 |
  | `ConstrainedDimColor` | dimensions | 255,38,0 |
  | `NonDrivingConstrDimColor` | reference dimensions | 0,38,255 |
  | `ExprBasedConstrDimColor` | expression dimensions | 255,127,38 |
  | `DeactivatedConstrDimColor` | deactivated dimensions | 127,127,127 |
  | `CursorTextColor` | cursor text | 0,0,255 |
  | `CursorCrosshairColor` | cursor crosshair | white |
  | `CreateLineColor` | rubber-band preview | 127,127,127 |
  | `HighlightColor` / `SelectionColor` | pre-selection / selection | — |
  | `SketchFaceColor` (Mod/Sketcher/General) | sketch faces | 84,171,255 |

  Widths `EdgeWidth`, `ConstructionWidth`, `InternalWidth`, `ExternalWidth` and `ExternalDefiningWidth` (Mod/Sketcher/View) all default to 2. Line patterns are `EdgePattern`, `ConstructionPattern` and so on. — [src/Mod/Sketcher/Gui/SketcherSettingsAppearance.ui](src/Mod/Sketcher/Gui/SketcherSettingsAppearance.ui); [EditModeCoinManager.cpp:80-243](src/Mod/Sketcher/Gui/EditModeCoinManager.cpp); [EditModeCoinManagerParameters.cpp:55-99](src/Mod/Sketcher/Gui/EditModeCoinManagerParameters.cpp)
- Sizes:
  - `ConstraintSymbolSize` (View, 15 px)
  - `EditSketcherFontSize` (View, 17)
  - `ViewScalingFactor` (View, 1.0)
  - `MarkerSize`
  - `ShowDimensionalName` (true) with `DimensionalStringFormat` "%N = %V"
  - `HideUnits`
  
  — [SketcherSettingsDisplay.ui](src/Mod/Sketcher/Gui/SketcherSettingsDisplay.ui); [EditModeCoinManager.cpp:118-126](src/Mod/Sketcher/Gui/EditModeCoinManager.cpp)
- Grid (Mod/Sketcher/General):
  - `ShowGrid` (false), `GridAuto` (true), `GridSize` (10 mm)
  - `GridSizePixelThreshold` (15), `GridNumberSubdivision` (10)
  - `GridLineWidth` (1), `GridDivLineWidth` (2)
  - `GridLineColor` and `GridDivLineColor` (178,178,178)
  - `GridLinePattern` and `GridDivLinePattern`
  
  — [SketcherSettingsGrid.ui](src/Mod/Sketcher/Gui/SketcherSettingsGrid.ui); [ViewProviderSketch.cpp:331-380](src/Mod/Sketcher/Gui/ViewProviderSketch.cpp)
- No Python API reaches the draw handlers: the only `.pyi` in Sketcher/Gui is `ViewProviderSketchGeometryExtension.pyi`. — [src/Mod/Sketcher/Gui/](src/Mod/Sketcher/Gui/)

**What SciForge already overrides in sketches**
- `sketch_mode.PARAMS` sets, while SciForge is on:
  - `LeaveSketchWithEscape=False` and `ShowDialogOnDistanceConstraint=False`
  - both constraint and element lists collapsed
  - `AlwaysExtGeoReference=False`
  - a solid quiet grid
  - Fusion-like colours: `EditedEdgeColor`/`CreateLineColor` blue `#5cb3ff`, fully constrained white, construction orange, external purple, glyphs `#9fe0a8`, reference dims `#9fb4cc`, cursor text and crosshair white
  - notification balloons off (`MaxOpenNotifications 0`, which hides "Autoconstraints cause redundancy…")
  - `SnapToGrid` from the palette "snap" option
  
  It restores everything on disable. It does **not** touch `Snap`, `SnapToObjects`, `SnapAngle`, `AutoConstraints`, `AvoidRedundantAutoconstraints`, `OnViewParameterVisibility`, `ConstraintSymbolSize` or `PickRadius`. — [src/Mod/SciForge/sciforge/sketch_mode.py:36-100, 158-169, 207-212](src/Mod/SciForge/sciforge/sketch_mode.py)
- SciForge's Line (L) runs FreeCAD's new `Sketcher_CreateLine`, which has OVP Length and Angle fields ("type 50, Tab, 30, Enter, which also adds the dimension, like Fusion"). It chains lines by re-clicking the end point from a Qt timer, so FreeCAD's own coincident auto-constraint applies. — [src/Mod/SciForge/sciforge/sketch_line.py:1-60](src/Mod/SciForge/sciforge/sketch_line.py)
- `ENTER_FINISHES` covers the Line, Rectangle and SciForge polygon tools. SciForge's own in-place `DimensionEditor` replaces FreeCAD's modal dimension dialog. Closed regions are shaded through `ProfileShading`. — [sketch_mode.py:116-123, 1284, 1555](src/Mod/SciForge/sciforge/sketch_mode.py)
- The spec requires "Auto-constraining and inference while drawing (snap markers, glyphs, tangent/perpendicular/coincident inferred), constraint glyphs, hover and delete". It allows "Fork the Sketcher module as needed". — [docs/sciforge/feature-outline.md:151, 237](docs/sciforge/feature-outline.md)

### Inferences
- **Already close to Fusion:**
  - OVP, which plays the role of heads-up dimension boxes with Tab to move between fields
  - coincident, point-on-curve and midpoint (Symmetric) inference with cursor glyphs
  - H/V inference
  - tangent-from-line-to-arc inference
  - snap to points, curves, midpoints and axes
  - Ctrl angle snap (a step of 15° may suit better than 5°)
  - continuous mode

  SciForge can tune from Python (all applied live):
  - `SnapAngle`
  - `OnViewParameterVisibility` (2 to also show X/Y position boxes before the first click)
  - `ConstraintSymbolSize`
  - `AutoConstraints` and `AvoidRedundantAutoconstraints` (or `sketch.ViewObject.Autoconstraints`)
  - `PickRadius`, which sets how close the cursor must be for point and curve snaps
- **Missing; needs C++ for true behavior:**
  1. Inference lines: dashed guide lines to existing points with matching X or Y, plus snapping onto those alignments.
  2. Parallel and Perpendicular suggestions toward any existing line (not only the previous one).
  3. Perpendicular or tangent continuation from the previous segment in the plain Line tool. The polyline tool has its own M-key arc modes.
  4. Snap-point markers drawn in the scene. Today feedback is only the preselection highlight and cursor icons.
  5. Tunable tolerances: 2° H/V, 5% midpoint and 0.1×scale tangent are hard-coded.
- **Most direct C++ route** (one coherent Sketcher patch):
  - Add an "alignment" step to `SnapManager::snap()`, with a new `SnapType` bit. It scans sketch vertices for |x−x_i| or |y−y_i| within a pixel tolerance and locks that coordinate, as the H/V-axis branch already does at SnapManager.cpp:263-272. It records the source vertex for drawing.
  - Extend `seekAutoConstraint()` with Parallel and Perpendicular, and with alignment-to-vertex (for example Horizontal/Vertical between points, or DistanceX/Y = 0). The icons already map from the ConstraintType enum at DrawSketchHandler.cpp:391-431.
  - Draw the dashed guides with a new attorney call into `EditModeCoinManager`. That code already supports line patterns, so the edit-curve node or a new `SoLineSet` with an `SoDrawStyle` `linePattern` can render them.
  - These files are under `src/Mod/Sketcher/Gui/` and need `SCIFORGE:` markers, a core-patches entry and a full build.
- **Python-only stopgap:**
  - Draw dashed guide lines with a pivy `SoAnnotation` overlay driven by `view.addEventCallback("SoLocation2Event")`, scheduled through `QTimer`.
  - Add the inferred constraints after the geometry is created, as `LineChain` does.

  This route cannot move the point FreeCAD's handler uses, because snapping happens in C++ before the handler sees the position. The visuals and the result could disagree, so it is only an interim option.
- The cursor-tail icons are FreeCAD's SVGs, loaded by name through `BitmapFactory`. A restyle could be done by providing same-named icons earlier in the icon search path, or by patching `suggestedConstraintsPixmaps`. This was not verified (see Gaps).

### Gaps
- Not verified: whether `Gui::BitmapFactory` lets a Python-added icon path override built-in `Constraint_*` SVGs. Built-ins may come from compiled Qt resources first.
- Not verified at run time: the effect of `OnViewParameterVisibility=2` on SciForge's line chaining (`sketch_line.py`). It may show X/Y boxes that then take focus on typed numbers.
- Fusion's exact inference set and tolerances (which snaps exist, glyph look, dashed-line rules) belong to the Fusion research, not here.
- The FreeCAD wiki pages "Sketcher Preferences" and "Sketcher on-view parameters" could not be fetched (proxy 403). Everything above comes from the 1.1.4 source.
