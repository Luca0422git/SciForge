# Fusion viewport navigation: orbit, pan, zoom, orbit center and the navigation bar

Source note (read first): in this session the page-fetch tool could not resolve any host (DNS failure for
autodesk.com, help.autodesk.com, forums.autodesk.com and even wikipedia.org). Every web finding below
therefore comes from search-engine extracts of the cited pages, not from reading the full page. Each line is
tagged with its source type: **[Official]** = Autodesk help, API reference, support article or Autodesk blog;
**[Forum]** = Autodesk Community or other user forum (including Autodesk staff replies, noted when known);
**[Tutorial]** = third-party tutorial or course; **[Code]** = SciForge/FreeCAD source in this repo;
**[Ref]** = general 3D-graphics reference. Fusion was renamed from "Fusion 360" to "Fusion" in January 2024
([Wikipedia](https://en.wikipedia.org/wiki/Autodesk_Fusion)), so older sources use the old name.

## 1. Default mouse mappings and the navigation presets ("Pan, Zoom, Orbit Shortcuts")

### Takeaway
Fusion's default ("Fusion" preset) is: middle-drag = pan, Shift + middle-drag = orbit, wheel = zoom,
Ctrl+Shift + middle-drag = drag-zoom, double-click middle = fit. A preference in Preferences > General lets the
user pick one of six presets: Fusion (default), Alias, Inventor (Windows only), SolidWorks, Tinkercad, PowerMill.

### Cited Findings
- **[Official]** The preset dropdown lives in Preferences > General and is named "Pan, Zoom, Orbit Shortcuts"
  in the Autodesk blog; the Fusion Help preferences page calls it "Mouse setup (pan, zoom, orbit)", describes
  it as setting "the behavior of the middle mouse button for view navigation", and lists Fusion (default),
  Alias, Inventor, SolidWorks — [Autodesk blog: quick tip pan/zoom/orbit](https://www.autodesk.com/products/fusion-360/blog/quick-tip-pan-zoom-orbit-preferences/);
  [Fusion Help, Preferences page](https://help.autodesk.com/view/fusion360/ENU/?guid=GUID-878489CD-3A23-4303-8450-C2F4F8E410B1)
- **[Official]** The Autodesk blog shortcut table additionally lists Tinkercad and PowerMill presets, giving six
  in total — [Autodesk blog: quick tip](https://www.autodesk.com/products/fusion-360/blog/quick-tip-pan-zoom-orbit-preferences/);
  [Autodesk blog: Navigation and Preferences, 2026 update (dated 16 Mar 2026)](https://www.autodesk.com/products/fusion-360/blog/understanding-navigation-and-preferences-in-autodesk-fusion/)
- **[Official]** Preset mappings as listed by Autodesk (search extracts of the help page and blog table; the two
  agree):
  | Preset | Pan | Orbit | Zoom |
  |---|---|---|---|
  | Fusion (default) | Middle-drag | Shift + middle-drag | Wheel, or Ctrl+Shift + middle-drag |
  | Alias | Shift+Alt + middle-drag | Shift+Alt + left-drag | Shift+Alt + right-drag |
  | Inventor (Windows only) | F2 + left-drag | F4 + left-drag | F3 + left-drag |
  | SolidWorks | Ctrl + middle-drag (Cmd + middle on Mac) | Middle-drag | Shift + wheel (per extract) |
  | Tinkercad | Middle-drag | Right-drag | Wheel, or Ctrl+Shift + middle-drag |
  | PowerMill | Shift + middle-drag | Middle-drag | Wheel |
  — [Autodesk blog: quick tip](https://www.autodesk.com/products/fusion-360/blog/quick-tip-pan-zoom-orbit-preferences/);
  [Fusion Help, Preferences page](https://help.autodesk.com/view/fusion360/ENU/?guid=GUID-878489CD-3A23-4303-8450-C2F4F8E410B1)
- **[Official]** The PowerMill preset is described as using its own orbit type; the Help page mentions a
  separate "Default Orbit type" option associated with it — [Fusion Help, Preferences page](https://help.autodesk.com/view/fusion360/ENU/?guid=GUID-878489CD-3A23-4303-8450-C2F4F8E410B1)
- **[Official]** Double-clicking the wheel zooms to fit; middle = pan, Shift+middle = orbit, wheel = zoom —
  [Autodesk blog: Navigation and Preferences 2026](https://www.autodesk.com/products/fusion-360/blog/understanding-navigation-and-preferences-in-autodesk-fusion/)
- **[Official]** The Inventor preset is recommended for laptop/trackpad users without a middle button
  (F2/F3/F4 + left button), Windows only — [Autodesk blog: quick tip](https://www.autodesk.com/products/fusion-360/blog/quick-tip-pan-zoom-orbit-preferences/)
- **[Official]** Autodesk's shortcut reference lists "Orbit: hold Shift + middle mouse button" and "orbit around a
  point: Shift + click, then middle button" — [Autodesk Fusion shortcuts guide](https://www.autodesk.com/shortcuts/fusion-360)
- **[Forum]** A user found the preset had silently switched to "SolidWorks" and trackpad gestures broke until
  it was set back to "Fusion" — [Macbook trackpad behavior randomly changes](https://forums.autodesk.com/t5/fusion-support-forum/macbook-trackpad-behavior-zoom-orbit-pan-randomly-changes-while/td-p/8863917)
- **[Forum]** Users report that Set Orbit Center / Reset Orbit Center only work when the preset is "Fusion" —
  [How is the center of rotation determined (2024)](https://forums.autodesk.com/t5/fusion-design-validate-document/when-rotating-the-view-how-is-the-center-of-rotation-determined/td-p/12565830)
- **[Forum]** Older thread: there was no built-in modifier + right-click orbit option outside the presets —
  [Orbit and pan keyboard shortcuts?](https://forums.autodesk.com/t5/fusion-design-validate-document/orbit-and-pan-keyboard-shortcuts/td-p/6813596)

### Inferences
- For SciForge, a "Fusion" navigation style in FreeCAD terms is: MMB-drag pan, Shift+MMB-drag orbit,
  wheel zoom, Ctrl+Shift+MMB-drag zoom, MMB double-click fit. Presets are just alternative button/modifier
  tables over the same pan/orbit/zoom operations, so one data table can drive all six.
- A plain left-click must never start navigation in the Fusion preset (left button is reserved for selection),
  which is the main difference from FreeCAD's default "CAD" style that some users find "jumpy".

### Gaps
- The SolidWorks preset zoom ("Shift + wheel") came from a search extract and may be garbled; SolidWorks itself
  uses plain wheel for zoom. Needs a live check.
- Exact mappings for Alias/PowerMill on Mac (Option vs Alt, Cmd vs Ctrl) were not confirmed.
- No default keyboard shortcut for orbit/pan/zoom modes in the Fusion preset was found. F6 = "Zoom to Fit" is
  listed by Autodesk, but the official shortcut page lists it only in the Electronics section, so whether F6
  fits the view in the Design workspace is unconfirmed — [Autodesk blog: keyboard shortcuts](https://www.autodesk.com/products/fusion-360/blog/quick-tip-custom-keyboard-shortcuts/);
  [Autodesk Fusion shortcuts guide](https://www.autodesk.com/shortcuts/fusion-360). No source supports
  "F4 / Shift+F4" as orbit-type shortcuts in the Fusion preset; F2/F3/F4 belong to the Inventor preset. One
  forum post says Home is on F6 when the Inventor preset is active — [Orbit and pan keyboard shortcuts?](https://forums.autodesk.com/t5/fusion-design-validate-document/orbit-and-pan-keyboard-shortcuts/td-p/6813596)
- A forum thread asked for a free-orbit hotkey, which suggests none exists by default; not confirmed —
  [Free orbit hotkey](https://forums.autodesk.com/t5/fusion-design-validate-document/free-orbit-hotkey/td-p/8504502)

## 2. Free Orbit vs Constrained Orbit (why Fusion feels "stable")

### Takeaway
Fusion has exactly two orbit modes (API enum DefaultOrbits: Constrained = 0, Free = 1). Constrained Orbit
rotates only about the ViewCube's Top/Bottom axis (the document's up axis) while keeping the ViewCube Top
upright, i.e. a turntable (yaw about world up + pitch about the screen-horizontal axis, no roll). Free Orbit
lets the model tumble in any orientation (trackball). The "stable" feel the user describes is the constrained
(turntable) behavior: roll is never introduced, so vertical edges of a Z-up model stay vertical on screen.

### Cited Findings
- **[Official]** The Fusion API enumerator `DefaultOrbits` has two values: Constrained orbit mode (0) and Free
  orbit mode (1) — [Fusion API: DefaultOrbits](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/DefaultOrbits.htm)
- **[Forum, Autodesk description quoted in thread]** Constrained Orbit "will now rotate only about the Top/Bottom
  axis of the ViewCube, attempting to keep the Top of the ViewCube upright", whereas Free Orbit "allows your
  model to tumble in any orientation" — [Orbit - How does it really work?](https://forums.autodesk.com/t5/fusion-design-validate-document/orbit-how-does-it-really-work/td-p/6884264)
- **[Official]** Autodesk University tip (2019): constrained orbit is locked to orbiting around the axis between
  the Top and Bottom faces of the ViewCube — [AU: 11 Fusion 360 Tips & Tricks](https://www.autodesk.com/autodesk-university/article/11-Fusion-360-Tips-Tricks-2019)
- **[Forum, version change]** In older releases, Constrained Orbit picked whichever of the three origin axes was
  closest to screen-up at the moment the orbit started (e.g. Home view -> Top/Bottom axis; Front view ->
  Left/Right axis). This was later changed to always use the ViewCube Top/Bottom axis —
  [Orbit - How does it really work?](https://forums.autodesk.com/t5/fusion-design-validate-document/orbit-how-does-it-really-work/td-p/6884264);
  [Constrained vs Free Orbit (2025)](https://forums.autodesk.com/t5/fusion-design-validate-document/constrained-vs-free-orbit/td-p/13689573);
  [Fix Constrained Orbit (idea)](https://forums.autodesk.com/t5/fusion-360-ideastation-archived/fix-constrained-orbit/idi-p/5811455)
- **[Forum, Autodesk QA engineer, 2025]** "Lock Horizon" (3Dconnexion) constrains orbit about the axis
  perpendicular to the viewport, often the Y axis in Home view with a Z-up layout; it is toggled in the
  3Dconnexion settings app (Navigation Modes tab) while Fusion is focused. 3Dconnexion drivers can flip
  Fusion's orbit to Constrained in some cases (Sketch Lock, Lock Horizon) —
  [Constrained vs Free Orbit (2025)](https://forums.autodesk.com/t5/fusion-design-validate-document/constrained-vs-free-orbit/td-p/13689573);
  [3Dconnexion forum: Fusion 360 Constrained Orbit / Lock Horizon](https://forum.3dconnexion.com/viewtopic.php?t=39140)
- **[Official]** Tinkercad-oriented Autodesk guide: Constrained Orbit rotates the view around a specified point
  (the center mark) and behaves very much like Tinkercad; Free Orbit rotates freely around the X and Y (screen)
  axes — [Tinkercad blog: make Fusion similar to Tinkercad](https://www.tinkercad.com/blog/fusion-setup)
- **[Official]** May 2026 update: up to 42% faster constrained orbit in large assemblies (performance only, no
  behavior change described) — [May 2026 Product Update](https://www.autodesk.com/products/fusion-360/blog/may-2026-product-update-whats-new/)
- **[Ref]** Turntable = keeps the horizon level, like a record player / potter's wheel; trackball = any
  orientation, less restrictive — [Blender Manual: Navigation preferences](https://docs.blender.org/manual/en/latest/editors/preferences/navigation.html)
- **[Ref]** Canonical turntable: left-right drag rotates about the global up (z) axis, up-down drag rotates about
  the camera's local x axis; use turntable when the model has a real-world up axis —
  [Matt Keeter: 3D Rotation Design](https://www.mattkeeter.com/projects/rotation/)
- **[Ref]** Trackball tumbles about camera-space axes, so it introduces roll; the usual fix is azimuth about
  world up, elevation clamped, camera up set to world up —
  [Blender D1868 turntable/trackball options](https://developer.blender.org/D1868);
  [Babylon.js forum](https://forum.babylonjs.com/t/blender-trackball-orbit-method-for-arcrotatecamera/51823);
  [coilbox PR #12](https://github.com/0xCarnival/coilbox/pull/12)
- **[Code]** FreeCAD's default orbit style is `RoundedArcball` (a trackball variant):
  `hGrp->GetInt("OrbitStyle", int(NavigationStyle::RoundedArcball))` — [DlgSettingsNavigation.cpp:174](../../src/Gui/PreferencePages/DlgSettingsNavigation.cpp).
  Available styles: Turntable, Trackball, FreeTurntable, TrackballClassic, RoundedArcball —
  [NavigationStyle.h:118](../../src/Gui/Navigation/NavigationStyle.h)
- **[Code]** FreeCAD's `Turntable` per mouse-move event applies EITHER a rotation about screen-x OR about world
  +Z (whichever mouse delta is larger), never both; `FreeTurntable` splits the move into a horizontal and a
  vertical step so both apply — [NavigationStyle.cpp:228-258, 1116-1123](../../src/Gui/Navigation/NavigationStyle.cpp)

### Inferences
- Root cause of the user's complaint: stock FreeCAD defaults to a trackball-family orbit (Rounded Arcball), which
  accumulates roll, so the model "tips off axis". Fusion users normally live in Constrained Orbit, which is a
  turntable. To match Fusion: default to a turntable whose yaw axis is the document up axis (+Z for Z-up, +Y for
  Y-up, i.e. the ViewCube Top/Bottom axis), pitch about the camera's right vector, and re-orthonormalize the camera
  so its up vector stays in the plane spanned by world-up and the view direction (zero roll). Apply yaw and pitch
  from the same mouse delta every event (like FreeCAD's FreeTurntable, not its dominant-axis Turntable, which
  feels stepped).
- Suggested math per mouse event (dx, dy in pixels, k = radians/pixel): `q = R(worldUp, -k*dx) * R(cameraRight, -k*dy)`;
  rotate the camera position about the pivot P by q and the camera orientation by q. Because yaw is about a fixed
  world axis and pitch is about the camera's own horizontal axis, roll stays zero by construction.
- Free Orbit is a trackball: rotation axis perpendicular to the drag direction in screen space (axis = viewDir x
  dragDir), angle proportional to drag length; it can roll.
- If the scene is Y-up (per preference), the turntable axis must be +Y; reading it from the same place the
  ViewCube reads "Top" keeps them consistent.

### Gaps
- Whether constrained orbit clamps at straight-up/straight-down (pitch limit at +/-90 degrees) or allows going
  over the top (which turns the model upside down while still rotating about the Top/Bottom axis) was not
  documented anywhere I could reach. Needs a live check in Fusion.
- Which mode Shift+middle-drag uses by default on a fresh 2025-2026 install is not confirmed by an official
  source. Evidence is mixed: a tutoring site claims Constrained is default (low reliability,
  [VarsityTutors](https://www.varsitytutors.com/practice/subjects/autodesk-fusion-360/lessons/view-controls));
  a 2019 thread reports the preference kept resetting to Free
  ([Default Orbit Type always resets to Free Orbit](https://forums.autodesk.com/t5/fusion-support-forum/default-orbit-type-always-resets-to-free-orbit/td-p/8637905));
  a 2025 thread reports it switching to Constrained after users set Free
  ([I set the default orbit type... suddenly changes to constrained](https://forums.autodesk.com/t5/fusion-support-forum/i-set-the-default-orbit-type-in-the-preferences-but-it-suddenly/td-p/13659435)).
  An old (2017) user report claimed Shift+middle-drag always gave free orbit regardless of the icon —
  [Orbit - How does it really work?](https://forums.autodesk.com/t5/fusion-design-validate-document/orbit-how-does-it-really-work/td-p/6884264).
  Recommendation for SciForge regardless: default to constrained/turntable, since that is what the owner asked for.
- Free Orbit has known path bugs in Fusion (camera follows an unintended path on horizontal drags; toggling
  orbit type fixes it); these are bugs, not behavior to copy —
  [Free Orbit Bug - Closer to a Fix?](https://forums.autodesk.com/t5/fusion-support-forum/free-orbit-bug-closer-to-a-fix/td-p/10168742);
  [Free Orbit rotation bug with bizarre fix](https://forums.autodesk.com/t5/fusion-support-forum/free-orbit-rotation-bug-with-bizarre-fix/td-p/9477005)

## 3. Choosing the orbit type: preference, navigation bar and the on-screen orbit tool

### Takeaway
The orbit type is chosen in Preferences ("Default Orbit type") and in the navigation bar's Orbit dropdown; the
two are linked (changing it in the bar also changes the preference). The navigation-bar Orbit command shows an
on-screen tool: dragging inside the circle = free tumble, on/outside the circle = roll about the view axis, on
the four handle lines = rotation about the screen horizontal or vertical axis.

### Cited Findings
- **[Official]** Free orbit may not persist as the default after sign-out/sign-in; Autodesk's workaround is to
  restart, set Free orbit, run `Options.Save` in the Text Commands window, restart again —
  [Autodesk support: Free orbit does not stay as default](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/Free-orbit-does-not-stay-as-default-preference-after-sign-out-and-sign-in-to-Fusion-360.html)
- **[Forum]** Changing the orbit type in the navigation bar also changes the preference to that type —
  [Default Orbit Type always resets to Free Orbit](https://forums.autodesk.com/t5/fusion-support-forum/default-orbit-type-always-resets-to-free-orbit/td-p/8637905)
- **[Official, older training PDF]** The navigation bar sits at the bottom of the canvas; its Orbit command can be
  constrained or free, set in Preferences — [Autodesk Upskill PDF: Navigation and display settings](https://files.upskill-dev.autodesk.com/public/introduction-to-cad-learn-fusion-360-in-90-minutes/211004_SBS_M4-01_Navigation-and-display-settings.pdf)
- **[Forum]** Clicking the navigation-bar Orbit tool shows a circle; drag inside = free orbit; drag on one of the
  four lines off the circle = rotate along that plane; drag outside the circle between lines = rotate about the
  view normal (roll) — [Rotate/orbit screen in single plane](https://forums.autodesk.com/t5/fusion-design-validate-document/rotate-orbit-screen-in-single-plane/td-p/6239198)
- **[Forum]** Second account: dragging on the circle pivots about the viewing axis; dragging on the cross hairs
  gives constrained rotation about horizontal or vertical axes; a single click on a cross hair shifts the view —
  [Orbit - How does it really work?](https://forums.autodesk.com/t5/fusion-design-validate-document/orbit-how-does-it-really-work/td-p/6884264)
- **[Forum]** Idea request to make the free orbit tool's handles more visible (confirms handles exist) —
  [Better free orbit tool handle visibility](https://forums.autodesk.com/t5/fusion-360-ideastation-archived/better-free-orbit-tool-handle-visibility-like-on-the-web-based/idi-p/7612424)
- **[Forum]** Fix for 3Dconnexion-related reverting: choose the "Legacy" SpaceMouse driver in Preferences —
  [Default Orbit Type thread](https://forums.autodesk.com/t5/fusion-support-forum/default-orbit-type-always-resets-to-free-orbit/td-p/8637905);
  [Constrained orbit not working with SpaceMouse](https://forums.autodesk.com/t5/fusion-design-validate-document/constrained-orbit-is-not-working-with-spacemouse/td-p/6821472)

### Inferences
- The circle-with-four-handles tool is the classic Autodesk "free orbit" gizmo (also in Inventor). It is a modal
  command (click the button, then left-drag), whereas Shift+MMB is a transient drag. SciForge can ship the
  transient drag first and add the gizmo later.

### Gaps
- Exact name of the preference ("Default Orbit type"?) and whether it sits in General or General > Design in the
  current UI were not confirmed from a page read.
- What the constrained-orbit command shows on screen (if anything besides the pivot dot) was not found.

## 4. Orbit center (pivot)

### Takeaway
Fusion orbits around an automatically chosen pivot shown as a small green dot: the center of the bounding box of
the design when the whole model is on screen, otherwise a point on the model nearest the camera / under the cursor.
The user can set a pivot explicitly (right-click empty canvas > Set Orbit Center, then click a point; or
Shift + single middle-click on the model), and reset it (Reset Orbit Center / Home). A preference ("camera
pivot") switches between orbiting around the window center and around the model's focal point.

### Cited Findings
- **[Official]** By default the orbit pivot is at the center of the bounding box around the component group of the
  design; to set a custom pivot, right-click off the design in the Design workspace, choose "Set Orbit Center",
  then click the desired point — [Autodesk support: change or reset the orbit pivot](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/How-to-reset-the-orbit-pivot-point-in-Fusion-360.html)
- **[Official]** If the whole model is on screen, the orbit point is the middle of the design; if the model is
  partly off screen, the orbit point is the point nearest the camera; override with right-click > Set Orbit Point —
  [Autodesk support: Unable to orbit around selected point](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/Fusion-360-fails-to-orbit-around-selected-point.html)
- **[Forum]** A community reply contradicts the off-screen rule, saying the point under the mouse is the pivot;
  another notes the pivot may snap to a nearby vertex/edge that can be off screen —
  [How is the center of rotation determined (2024)](https://forums.autodesk.com/t5/fusion-design-validate-document/when-rotating-the-view-how-is-the-center-of-rotation-determined/td-p/12565830);
  [Set Orbit Center & Model Views](https://forums.autodesk.com/t5/fusion-support-forum/set-orbit-center-amp-model-views/td-p/8578945)
- **[Official]** The blog lists a "Camera pivot" preference: switch between orbiting around the window's center or
  the focal point of the part or assembly — [Autodesk blog: quick tip](https://www.autodesk.com/products/fusion-360/blog/quick-tip-pan-zoom-orbit-preferences/)
- **[Forum]** "Enable camera pivot" (Preferences > General) must be checked for the orbit center to be settable;
  unchecking it was the fix in one Mac thread where the dot misbehaved —
  [Set Orbit Center & Model Views](https://forums.autodesk.com/t5/fusion-support-forum/set-orbit-center-amp-model-views/td-p/8578945);
  [Green dot (orbit origin) on macOS + Magic Mouse](https://forums.autodesk.com/t5/fusion-design-validate-document/how-to-change-the-green-dot-orbit-origin-when-rotating-using/td-p/13754732)
- **[Forum]** Shift + a single middle-click on the model places a small green dot there, which becomes the new
  rotation center; it only lands if the cursor is over the model —
  [Set Orbit Center & Model Views](https://forums.autodesk.com/t5/fusion-support-forum/set-orbit-center-amp-model-views/td-p/8578945)
- **[Tutorial]** While Shift+wheel orbiting, a green dot is shown at the pivot (initially at the origin); Shift +
  click of the wheel on a new location moves it — [LinkedIn Learning: Center of rotation in camera orbit](https://www.linkedin.com/learning/fusion-360-tips-tricks-and-techniques/center-of-rotation-in-camera-orbit)
- **[Forum]** Right-clicking empty space offers both "Set Orbit Center" and "Reset Orbit Center"; Home also resets;
  workaround: Look At a face, then Set Orbit Center —
  [How is the center of rotation determined (2024)](https://forums.autodesk.com/t5/fusion-design-validate-document/when-rotating-the-view-how-is-the-center-of-rotation-determined/td-p/12565830)
- **[Forum]** In sketch edit mode, double-clicking the wheel created a new green dot (user called it a possible
  bug) — [How to orbit in sketch mode](https://forums.autodesk.com/t5/fusion-design-validate-document/how-to-orbit-in-sketch-mode-like-it-s-orbiting-when-out-of/td-p/9151593)
- **[Forum]** In toolpath simulation (Manufacture), the pivot is tied to the tool tip and cannot be chosen —
  [Camera orbit center changes during toolpath simulation](https://forums.autodesk.com/t5/fusion-manufacture-forum/camera-orbit-center-point-changes-when-running-a-toolpath/td-p/11983211)
- **[Forum, old 2016]** Earlier versions showed a red dot instead of green —
  [pivot point](https://forums.autodesk.com/t5/fusion-design-validate-document/pivot-point/td-p/5486975)
- **[Code]** FreeCAD already has rotation-center modes: WindowCenter, ScenePointAtCursor, FocalPointAtCursor,
  BoundingBoxCenter (UI labels "Window center", "Drag at cursor", "Object center") —
  [NavigationStyle.h:127](../../src/Gui/Navigation/NavigationStyle.h);
  [DlgSettingsNavigation.ui:521-553](../../src/Gui/PreferencePages/DlgSettingsNavigation.ui)

### Inferences
- A faithful SciForge pivot rule: (1) if the user set an orbit center, use it until reset (Reset Orbit Center,
  Home, or Fit); (2) else if the whole model's bounding box is on screen, use its center; (3) else use the scene
  point under the cursor at drag start (fallback: focal point). Show a small green dot at the pivot for the
  duration of the drag only.
- Implementing Set Orbit Center as a context-menu item on empty canvas plus Shift+MMB single-click matches the
  documented entry points.

### Gaps
- Whether the green dot is visible only during orbit or persists after Set Orbit Center could not be confirmed.
- Whether a user-set pivot survives Fit / view changes is unconfirmed (one forum hint says Home resets it).
- The exact preference name today ("Enable camera pivot" vs "Camera pivot") is unconfirmed.

## 5. Pan

### Takeaway
Pan is middle-drag (Fusion preset), moving the view parallel to the screen. No source states explicitly that the
point under the cursor stays exactly under the cursor, but that is the standard behavior.

### Cited Findings
- **[Official]** Pan moves the view parallel to the screen; Pan is also a navigation-bar command —
  [Autodesk Upskill PDF: Navigation and display settings](https://files.upskill-dev.autodesk.com/public/introduction-to-cad-learn-fusion-360-in-90-minutes/211004_SBS_M4-01_Navigation-and-display-settings.pdf);
  [Autodesk blog: Fusion interface beginners guide](https://www.autodesk.com/products/fusion-360/blog/autodesk-fusion-interface/)
- **[Official]** Default pan is middle mouse button; a tutoring site's claim of Shift+middle for pan conflicts with
  Autodesk and should be ignored — [Autodesk blog: Navigation and Preferences 2026](https://www.autodesk.com/products/fusion-360/blog/understanding-navigation-and-preferences-in-autodesk-fusion/);
  contradicted by [VarsityTutors](https://www.varsitytutors.com/practice/subjects/autodesk-fusion-360/lessons/view-controls)

### Inferences
- Implement pan so that the 3D point under the cursor at drag start stays under the cursor (in perspective, use
  the depth of the picked point, or the focal plane if nothing is hit). This is what users expect from Fusion.

### Gaps
- "Cursor-locked" pan (exact 1:1 tracking at the picked depth) was not confirmed from any source.

## 6. Zoom

### Takeaway
Wheel zoom in the Design workspace zooms toward the cursor position. A "Reverse zoom direction" preference flips
the wheel direction. Ctrl+Shift+middle-drag gives continuous zoom. Zoom Window and Fit exist on the navigation
bar; double-click middle = Fit.

### Cited Findings
- **[Official]** "Reverse zoom direction" preference changes whether scrolling up zooms in or out —
  [Autodesk blog: quick tip](https://www.autodesk.com/products/fusion-360/blog/quick-tip-pan-zoom-orbit-preferences/);
  it applies to the modeling environments, and Electronics has its own setting —
  [Zoom opposite direction (Electronics forum)](https://forums.autodesk.com/t5/fusion-electronics-forum/zoom-opposite-direction/td-p/12313335)
- **[Forum]** Fusion zooms toward the point of reference under the cursor (hover over a corner, zoom goes there) —
  [Is it possible to zoom to mouse cursor?](https://forums.autodesk.com/t5/fusion-design-validate-document/is-it-possible-to-zoom-to-mouse-cursor/td-p/7957949)
- **[Forum]** On Mac trackpads, zoom goes toward screen center instead of the cursor, while an external mouse
  zooms to the cursor — [Is it possible to zoom to mouse cursor?](https://forums.autodesk.com/t5/fusion-design-validate-document/is-it-possible-to-zoom-to-mouse-cursor/td-p/7957949)
- **[Official]** In the Drawing workspace, wheel zoom does not go to the cursor in some setups (known issue,
  workaround: single monitor) — [Autodesk support: zoom not at cursor in a Fusion Drawing](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/Zoom-to-point-function-not-working-in-Fusion-360-drawing-workspace-on-Sonoma-MAC-Os.html);
  [Forum: drawing zoom to cursor](https://forums.autodesk.com/t5/fusion-support-forum/in-drawing-workspace-scroll-wheel-does-not-zoom-to-cursor/td-p/13048568)
- **[Official]** Fit positions the entire model on screen; double-click wheel = zoom to fit —
  [Autodesk blog: Fusion interface](https://www.autodesk.com/products/fusion-360/blog/autodesk-fusion-interface/);
  [Autodesk blog: Navigation and Preferences 2026](https://www.autodesk.com/products/fusion-360/blog/understanding-navigation-and-preferences-in-autodesk-fusion/)
- **[Official]** May 2026: up to 26% faster zoom during selection in large assemblies —
  [May 2026 Product Update](https://www.autodesk.com/products/fusion-360/blog/may-2026-product-update-whats-new/)
- **[Code]** FreeCAD has matching knobs: "ZoomAtCursor", "InvertZoom", "UseNavigationAnimations",
  animation duration — [DlgSettingsNavigation.cpp:93-150](../../src/Gui/PreferencePages/DlgSettingsNavigation.cpp)

### Inferences
- Default SciForge: zoom-at-cursor ON, wheel-up = zoom in (Fusion default as far as can be told), with an
  "invert" checkbox mirroring "Reverse zoom direction".

### Gaps
- No official statement of the default wheel direction (which direction is "in") was found.
- No separate "Zoom to cursor" on/off preference was found in Fusion; it appears to be always on in Design.
- No Fusion preference for view-transition animation time was found. Animated transitions for ViewCube clicks
  exist in other Autodesk products with a toggle, but nothing Fusion-specific surfaced.
- Zoom Window behavior (rectangle drag, then fit that rectangle) is from recollection only; not confirmed here.

## 7. Trackpad gestures (Mac and Windows)

### Takeaway
With "Use gesture-based view navigation" enabled and the Fusion preset: two-finger drag = pan, pinch = zoom,
Shift + two-finger drag = orbit. On Mac this has existed for years; on Windows, pan/zoom gestures arrived around
mid-2025 and Shift + two-finger orbit arrived in the September 2026 update.

### Cited Findings
- **[Forum]** Mac, Fusion preset: two fingers = pan, Shift + two fingers = orbit, pinch = zoom —
  [Macbook trackpad behavior randomly changes](https://forums.autodesk.com/t5/fusion-support-forum/macbook-trackpad-behavior-zoom-orbit-pan-randomly-changes-while/td-p/8863917)
- **[Forum, Autodesk reply]** Ensure "Use gesture based view navigation" is enabled in Preferences —
  [Macbook trackpad behavior thread](https://forums.autodesk.com/t5/fusion-support-forum/macbook-trackpad-behavior-zoom-orbit-pan-randomly-changes-while/td-p/8863917);
  [Gesture based view navigation problems on OS X](https://forums.autodesk.com/t5/fusion-design-validate-document/gesture-based-view-navigation-problems-on-os-x-since-fusion/td-p/5546148)
- **[Official]** September 2026 major update (build 2705.1.11, 3 Sep 2026): Windows users can orbit with Shift +
  two-finger touchpad swipe; direct camera control without inertia; requires gesture-based view navigation enabled;
  described as a first iteration. Release notes also mention smoother trackpad pan/zoom/orbit —
  [September 2026 Major Product Update](https://www.autodesk.com/products/fusion-360/blog/september-2026-major-product-update-whats-new/);
  [Fusion release notes](https://help.autodesk.com/view/fusion360/ENU/?guid=FIC-REL-NOTES-INC)
- **[Forum, Autodesk reply, June 2025]** Pan and zoom gestures on Windows trackpads had been added —
  [Orbit and Pan with touchpad](https://forums.autodesk.com/t5/fusion-support-forum/orbit-and-pan-with-touchpad/td-p/12416754)
- **[Forum]** Known issue: Mac gestures stop after sleep; restart Fusion —
  [Mac Trackpad Zoom/Pan Bug](https://forums.autodesk.com/t5/fusion-support-forum/mac-trackpad-zoom-pan-bug/td-p/6657339)
- **[Tutorial/add-in]** The unmaintained "Native Trackpad" add-in required turning gesture-based navigation off and
  replaced the gestures — [GitHub: Native-Trackpad](https://github.com/mertrois/Native-Trackpad)
- **[Official]** Autodesk has a support article for being unable to pan/zoom/orbit with mouse or trackpad —
  [Autodesk support: Unable to Pan, Zoom, or Orbit](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/Unable-to-use-Mouse-Wheel-to-activate-Orbit-and-Pan-in-Fusion-360.html)

### Inferences
- In Qt, this maps to: QWheelEvent with pixelDelta (two-finger scroll) = pan, QNativeGestureEvent ZoomNativeGesture
  (pinch) = zoom, two-finger scroll + Shift = orbit. When the gesture preference is off, two-finger scroll should
  behave like a wheel (zoom).

### Gaps
- What gesture-off mode does on Mac (two-finger scroll = zoom?) was not confirmed.
- Whether pinch zooms toward the cursor or the screen center: one forum report says Mac trackpad zoom goes to the
  screen center (see section 6), likely a bug rather than intent.

## 8. The navigation bar (bottom center of the canvas)

### Takeaway
The navigation bar holds: Orbit (dropdown with free / constrained), Look At, Pan, Zoom (with Zoom Window), Fit,
then Display Settings, Grid and Snaps, and Viewports menus.

### Cited Findings
- **[Official]** The navigation bar is at the bottom of the canvas; Orbit rotates the current view, Look At views
  the model face-on from a selected plane/face, Pan moves parallel to the screen, Zoom changes magnification, Fit
  positions the whole model on screen — [Autodesk Upskill PDF: Navigation and display settings](https://files.upskill-dev.autodesk.com/public/introduction-to-cad-learn-fusion-360-in-90-minutes/211004_SBS_M4-01_Navigation-and-display-settings.pdf);
  [Autodesk blog: Fusion interface](https://www.autodesk.com/products/fusion-360/blog/autodesk-fusion-interface/)
- **[Tutorial]** Orbit rotates around the center mark (constrained) or about the X and Y axes (free); the menus at
  the right end control Display Settings and Grid/Snaps; up to four viewports can be shown —
  [ETSU OER: Introduction to Fusion 360](https://dc.etsu.edu/cgi/viewcontent.cgi?article=1009&context=engr-1110-oer);
  [Instructables: Fusion 360 orientation](https://www.instructables.com/3D-Printing-101-3-Intro-to-3D-Modeling/)
- **[Forum]** The bar can disappear (hidden/zoomed UI); restoring it from display settings was one fix —
  [Free orbit and toolbar gone after update](https://forums.autodesk.com/t5/fusion-support-forum/free-orbit-and-toolbar-gone-after-update/td-p/10988916)
- **[Forum, Autodesk staff]** Camera type is set from Navigation bar > Display Settings > Camera and persists across
  sessions — [Default camera view keeps switching to perspective](https://forums.autodesk.com/t5/fusion-design-validate-document/default-camera-view-keeps-switching-to-quot-perspective-quot/td-p/12414138)

### Inferences
- Order left to right (from screenshots in memory, unverified this session): ViewCube-independent tools first
  (Orbit, Look At, Pan, Zoom, Fit), separator, then three dropdown menus (Display Settings, Grid and Snaps,
  Viewports).

### Gaps
- Exact sub-items of each dropdown were not confirmed from a page read. From recollection only (needs live check):
  Display Settings = Visual Style, Environment, Effects, Object Visibility, Camera (Orthographic / Perspective /
  Perspective with Ortho Faces), Ground Plane Offset, Full Screen; Grid and Snaps = Layout Grid, Layout Grid Lock,
  Snap to Grid, Grid Settings, Incremental Move, Set Increments; Viewports = Single View / Multiple Views.

## 9. Camera: orthographic vs perspective; up axis

### Takeaway
Fusion offers three camera modes (Orthographic, Perspective, Perspective with Ortho Faces), chosen in Display
Settings > Camera and remembered across sessions. Default modeling orientation for new designs is Z up (Y up
optional). The "Auto look at sketch" preference forces an orthographic, normal-to-sketch view when a sketch is
created or edited.

### Cited Findings
- **[Forum, Autodesk staff]** Camera mode set via Navigation bar > Display Settings > Camera persists across
  sessions; "Auto look at sketch" (Preferences > General > Design, on by default) switches to the sketch-normal
  view and can force Orthographic — [Default camera view keeps switching to perspective](https://forums.autodesk.com/t5/fusion-design-validate-document/default-camera-view-keeps-switching-to-quot-perspective-quot/td-p/12414138)
- **[Forum]** Users ask for a global preference for which of the three camera modes to use (implying no such global
  default exists) — [Default camera view keeps switching](https://forums.autodesk.com/t5/fusion-design-validate-document/default-camera-view-keeps-switching-to-quot-perspective-quot/td-p/12414138);
  [Display settings -> camera view changes all the time](https://forums.autodesk.com/t5/fusion-support-forum/display-settings-gt-camera-view-changes-all-the-time/td-p/9060963)
- **[Official]** A support article explains a "slightly distorted" model view (perspective camera) —
  [Autodesk support: Model view is slightly distorted](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/Model-view-is-slightly-distorted-in-Fusion-360.html)
- **[Official]** Default modeling orientation is Z up; Y up can be chosen in Preferences > General (affects only new
  designs; restart required) — [Fusion Help, Preferences page](https://help.autodesk.com/view/fusion360/ENU/?guid=GUID-878489CD-3A23-4303-8450-C2F4F8E410B1);
  [Autodesk support: change default XYZ orientation](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/How-to-change-the-orientation-of-the-origin-planes-in-Fusion-360.html);
  [Autodesk support: switch Y and Z axes](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/How-to-switch-Y-and-Z-axes-of-origin-in-Fusion-360.html)
- **[Tutorial]** The default used to be Y up in older Fusion 360 and is now Z up (version change) —
  [Product Design Online: default settings](https://productdesignonline.com/default-settings-for-fusion-360-tutorials/)

### Inferences
- "Perspective with Ortho Faces" = perspective normally, but snap to orthographic when the view is aligned to a
  standard face (ViewCube face click / Look At). SciForge can implement it as: on view-align to an axis direction,
  switch Coin camera to SoOrthographicCamera; on orbit start, switch back to perspective, keeping the visible size
  at the focal distance equal.
- Constrained orbit's yaw axis must follow the document's modeling orientation (Z up vs Y up).

### Gaps
- Fusion's out-of-box default camera mode (Perspective vs Orthographic) was not confirmed from an official source.
- Field of view for the perspective camera was not found.
