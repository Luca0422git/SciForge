# Fusion ViewCube: geometry, interaction, menu, settings and orientation conventions

Method note (read first). This sandbox could not open help.autodesk.com, autodesk.com, forums.autodesk.com,
research.autodesk.com or patents.google.com (DNS failure in WebFetch, proxy 403 for curl). Everything
from the web below comes from search-engine result text (titles, snippets and the search tool's
quotes of those pages), not from reading whole pages. Treat quoted wording as "as surfaced by search".
Source labels used on every finding:
- **[OFFICIAL-FUSION]**: Autodesk Fusion help, Fusion API docs or Autodesk support articles about Fusion.
- **[OFFICIAL-OTHER]**: Autodesk help for another product (Inventor, AutoCAD, Revit, Maya, 3ds Max, Alias).
  Same widget family, but behavior and wording can differ from Fusion. Never assume they match.
- **[RESEARCH/PATENT]**: the 2008 Autodesk Research paper or the ViewCube patents.
- **[FORUM]** / **[TUTORIAL]**: Autodesk Community posts, third-party tutorials or blogs.
- **[LOCAL CODE]**: FreeCAD's own NaviCube source in this repo (useful because SciForge would build on it).
- **Recollection (unverified)**: my own memory of Fusion's UI. Always placed under Gaps, never under findings.

## 1. Shape and look (geometry, regions, labels, colors, transparency, size, position, compass)

### Takeaway
The ViewCube is a labeled cube in a corner of the canvas that exposes 26 clickable views (6 faces,
12 edges, 8 corners). In Fusion it cannot be resized, there is no documented opacity or compass setting,
and the cube shows an X/Y/Z axis triad with letters. Exact colors, bevel proportions and idle transparency
for Fusion could not be confirmed from text sources.

### Cited Findings
- [OFFICIAL-FUSION] "The ViewCube is the 3D navigation cube in the corner of the canvas." Drag it to orbit,
  right-click for a context menu with more view and camera settings. — [Fusion ViewCube reference](https://help.autodesk.com/cloudhelp/ENU/Fusion-GetStarted/files/GS-VIEWCUBE.htm)
- [OFFICIAL-FUSION] Faces are "named" (labeled) faces: "Click a named face of the ViewCube to rotate the camera
  to that orthographic view." — [Fusion ViewCube reference](https://help.autodesk.com/cloudhelp/ENU/Fusion-GetStarted/files/GS-VIEWCUBE.htm)
- [RESEARCH/PATENT] The ViewCube is "a cube-shaped widget placed in a corner of the window"; it acts as an
  orientation indicator (it turns to reflect the current view direction when the scene is moved with other
  tools) and as a controller (drag it, or click faces, edges or corners). — [Khan et al., "ViewCube: A 3D Orientation Indicator and Controller", I3D 2008 (Autodesk Research)](https://research.autodesk.com/publications/viewcube-a-3d-orientation-indicator-and-controller); [Semantic Scholar record](https://www.semanticscholar.org/paper/ViewCube:-a-3D-orientation-indicator-and-controller-Khan-Mordatch/db6644bab70a371cfb4dae856c5840ec56cb7b76)
- [RESEARCH/PATENT] The widget covers 26 views: 8 corners, 12 edges, 6 faces. Corners give a "three-quarter"
  view; edges give a "half view based on two sides of the model". — [US 7,782,319 "Three-dimensional orientation indicator and controller"](https://patents.google.com/patent/US7782319B2/en) (as surfaced by search)
- [RESEARCH/PATENT] Study result about labels: no significant performance effect from varying labeling
  schemes (text, 2D graphics, 3D proxy model, or no labels). So text labels are a design choice, not a
  usability requirement. — [US 7,782,319](https://patents.google.com/patent/US7782319B2/en); [Khan et al. 2008](https://research.autodesk.com/publications/viewcube-a-3d-orientation-indicator-and-controller)
- [OFFICIAL-FUSION] Fusion's ViewCube cannot be resized: "it is by the design and currently, it is not
  possible to resize the ViewCube." — [Autodesk support: Is it possible to resize the Viewcube in Fusion](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/Is-it-possible-to-resize-the-Viewcube-in-Fusion-360.html)
- [OFFICIAL-FUSION] On 4K monitors the cube looks small; Autodesk's workaround is to turn off "High-DPI
  Application scaling" (Preferences > Compatibility and Troubleshooting), which changes the whole UI. — [Autodesk support: ViewCube scale on 4K](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/How-to-change-the-scale-of-Viewcube-in-4k-monitor-in-Fusion.html)
- [FORUM] Users repeatedly ask for a bigger ViewCube; replies say resizing is not possible. — [Can I make the viewcube larger?](https://forums.autodesk.com/t5/fusion-design-validate-document/can-i-make-the-viewcube-larger/td-p/10897436); [ViewCube size](https://forums.autodesk.com/t5/fusion-support-forum/viewcube-size/td-p/8977102)
- [OFFICIAL-FUSION] The ViewCube shows an axis triad with the letters X, Y, Z; red = X, green = Y, blue = Z.
  The origin axes in the model itself show colors only, no letters. — [Autodesk support: XYZ letters on origin axes as shown in the View Cube](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/Is-it-possible-to-place-the-letter-X-Y-Z-on-the-origin-axes-as-is-shown-in-the-View-Cube.html)
- [OFFICIAL-OTHER] Other Autodesk products expose size, inactive opacity and a compass:
  AutoCAD's ViewCube Settings has "Inactive Opacity" (system variable NAVVCUBEOPACITY) and "Show compass
  below the ViewCube" (north from NORTHDIRECTION); Maya's inactive opacity runs 0-100% and at 0% the cube
  disappears when the cursor leaves it; 3ds Max has size and inactive opacity in Viewport Configuration;
  Showcase has maximum size and inactive opacity. None of these are documented for Fusion. — [AutoCAD ViewCube Settings dialog](https://help.autodesk.com/cloudhelp/2016/ENU/AutoCAD-Core/files/GUID-78043EE2-114B-4F08-BFD7-7E5E429708A9.htm); [Maya ViewCube preferences](https://help.autodesk.com/cloudhelp/2016/ENU/Maya/files/GUID-F8DD60C0-A955-4D51-9D3D-9FFE1E8D3D16.htm); [3ds Max ViewCube panel](https://help.autodesk.com/view/3DSMAX/2024/ENU/?guid=GUID-775D2B7E-3EFB-4769-94F8-0FCA49F2EE6C)
- [TUTORIAL, low reliability] A tutoring site calls Fusion's cube "a compass"; this is loose wording, not
  evidence of a compass ring. — [Varsity Tutors: View Controls](https://www.varsitytutors.com/practice/subjects/autodesk-fusion-360/lessons/view-controls)
- [LOCAL CODE] FreeCAD's NaviCube already models a chamfered cube: chamfer default 0.12 of the cube size,
  clamped to 0.05-0.18 (`setChamfer`); 6 main faces, 12 edge faces and 8 corner faces are separate pick
  regions (`PickId::Front` ... `FrontTopRight` ... `RearBottomLeft`); idle opacity `m_InactiveOpacity = 0.5`,
  full opacity while the pointer is inside the widget square; it can draw a coordinate-system triad
  (`m_ShowCS`, per-axis colors); it can sit in any of the four corners (`moveToCorner`). — [src/Gui/NaviCube.cpp](/home/user/SciForge/src/Gui/NaviCube.cpp) (lines ~180-195, 289-292, 401-415, 721-729, 772)
- [LOCAL CODE] SciForge's theme already sets a Fusion-like NaviCube: light base color 0xF0F0F0 (alpha 0xE6),
  dark gray label/emphasis color #4a4f57, blue hover #6fb7f0. — [src/Mod/SciForge/sciforge/theme.py](/home/user/SciForge/src/Mod/SciForge/sciforge/theme.py) (lines 148-162)

### Inferences
- Region count is settled: 26 click targets (6 + 12 + 8), consistent between the patent and every
  Autodesk product page. FreeCAD's NaviCube already has exactly this region set, so geometry work is mostly
  visual tuning (chamfer size, colors, labels), not new picking logic.
- "Chamfered edges and corners" is the standard way to give edges and corners a clickable area of their own
  (that is what FreeCAD's NaviCube does with its 0.12 chamfer). Whether Fusion draws visible bevels or uses
  flat faces with invisible border hot-zones is not confirmed by any text source; for SciForge a small,
  subtle chamfer (around FreeCAD's 0.10-0.12) is a safe approximation of "general shape".
- Since Fusion offers no size/opacity/compass settings, a faithful Fusion clone needs no compass ring and no
  user-facing size or opacity preference (SciForge may still keep FreeCAD's parameters internally).

### Gaps
- Exact face, edge and label colors in Fusion, idle opacity value, and bevel proportions: not found in any
  text source. Recollection (unverified): light gray/near-white faces with dark gray uppercase labels
  (FRONT, BACK, TOP, BOTTOM, LEFT, RIGHT), subtle darker outline, slightly translucent when the pointer is
  away and opaque on hover; the cube sits at the top-right of the canvas.
- Label orientation (does TOP read upright when seen from Front-Top? do side labels stay upright?) could not
  be confirmed. Recollection (unverified): labels are painted on the faces and rotate with the cube, like
  decals; side labels read upright in the default home view.
- Whether Fusion has any compass ring: no source states it. Recollection (unverified): Fusion has none (unlike
  AutoCAD/Revit/Civil where it is optional). Treat "no compass" as likely but unconfirmed.
- Where the triad sits on the cube (which corner/edges the X/Y/Z lines run along) could not be confirmed.
  Recollection (unverified): three colored lines with letter labels running along three cube edges that meet
  at one lower corner (I cannot recall which corner); verify against a live Fusion screenshot before copying.
- Screen size in pixels: not found.

## 2. Hover behavior (highlighting, cursor)

### Takeaway
All Autodesk ViewCubes highlight the region under the pointer and become more opaque when the pointer is
over them; Fusion-specific details (color, cursor shape) were not found in text sources.

### Cited Findings
- [OFFICIAL-OTHER] Inactive opacity is the opacity "when inactive" (pointer away); the cube becomes fully
  visible when the pointer approaches. — [AutoCAD ViewCube Settings dialog](https://help.autodesk.com/cloudhelp/2016/ENU/AutoCAD-Core/files/GUID-78043EE2-114B-4F08-BFD7-7E5E429708A9.htm); [Maya ViewCube preferences](https://help.autodesk.com/cloudhelp/2016/ENU/Maya/files/GUID-F8DD60C0-A955-4D51-9D3D-9FFE1E8D3D16.htm)
- [FORUM] Fusion highlights model faces/edges on mouse-over in the canvas as a core behavior (context only;
  these threads do not discuss the ViewCube). — [Turn off part highlighting when mousing over](https://forums.autodesk.com/t5/fusion-design-validate-document/turn-off-part-highlighting-when-mousing-over/td-p/10680760)
- [LOCAL CODE] FreeCAD's NaviCube highlights the single picked region under the cursor (`setHilite(pickFace(x,y))`)
  in `m_HiliteColor` (default light blue RGB 170,226,255); highlight is suppressed while dragging. — [src/Gui/NaviCube.cpp](/home/user/SciForge/src/Gui/NaviCube.cpp) (lines 383, 1243-1276)

### Inferences
- Fusion behavior is very likely "one region at a time highlighted": hovering a face lights the face, an edge
  lights the whole edge region (on both adjacent faces), a corner lights the corner region (on its three faces).
  This matches the 26-region model and FreeCAD's implementation.

### Gaps
- Fusion's hover color and whether the cursor changes shape: not found. Recollection (unverified): light-blue
  highlight; the normal arrow cursor stays (no special hand cursor).
- Whether the Home icon and the menu control appear only on hover: not confirmed (see section 6).

## 3. Click behavior (faces, edges, corners, current face, animation)

### Takeaway
Clicking a face gives that orthographic view, a corner gives an isometric view, an edge gives a view between
two faces; the camera moves with a smooth animated transition. Fusion-specific animation duration and the
"click the already-current face" behavior could not be confirmed.

### Cited Findings
- [OFFICIAL-FUSION] "Click a named face of the ViewCube to rotate the camera to that orthographic view."
  "Click a corner of the ViewCube to rotate the camera to a predefined isometric view." — [Fusion ViewCube reference](https://help.autodesk.com/cloudhelp/ENU/Fusion-GetStarted/files/GS-VIEWCUBE.htm)
- [RESEARCH/PATENT] Edges: "a half view based on two sides of the model" (i.e. looking at the edge, 45 degrees
  between the two faces); corners: "three-quarter view". — [US 7,782,319](https://patents.google.com/patent/US7782319B2/en)
- [RESEARCH/PATENT] In the 2008 user study, dragging the cube was preferred and almost twice as fast as clicking
  its parts or clicking a row of view buttons. — [Khan et al. 2008](https://research.autodesk.com/publications/viewcube-a-3d-orientation-indicator-and-controller)
- [OFFICIAL-FUSION] Fusion preference "Animate view transitions": "Animates named view and sketch view
  transitions. Uncheck to skip animation and improve performance." (wording as surfaced by search; the exact
  page could not be opened). — [Fusion Help (preferences)](https://help.autodesk.com/view/fusion360/ENU/?guid=GUID-878489CD-3A23-4303-8450-C2F4F8E410B1)
- [OFFICIAL-OTHER] Maya's "Fit-to-view on view change" and AutoCAD's "Zoom to extents after view change"
  re-frame the model after a ViewCube click; these are options in those products, not documented for Fusion. — [Maya ViewCube preferences](https://help.autodesk.com/cloudhelp/2016/ENU/Maya/files/GUID-F8DD60C0-A955-4D51-9D3D-9FFE1E8D3D16.htm); [AutoCAD ViewCube Settings dialog](https://help.autodesk.com/cloudhelp/2016/ENU/AutoCAD-Core/files/GUID-78043EE2-114B-4F08-BFD7-7E5E429708A9.htm)
- [LOCAL CODE] FreeCAD's NaviCube on click of a face/edge/corner calls `setCameraOrientation(...)` (animated via
  FreeCAD's NavigationAnimation); with `m_RotateToNearest = true` it picks the target orientation whose "up"
  is nearest the current one instead of a fixed up vector. — [src/Gui/NaviCube.cpp](/home/user/SciForge/src/Gui/NaviCube.cpp) (lines 1186-1201)

### Inferences
- For edges and corners there is no single obvious "up" direction; keeping world-up (Z in Z-up mode) pointing
  up on screen for side/edge/corner views, and choosing the nearest up only for Top/Bottom views, is the
  behavior users expect ("keep scene upright"). FreeCAD's "rotate to nearest" covers the Top/Bottom case.
- Fusion appears to keep the zoom/target when clicking (no documented fit-on-click option); the separate
  "Fit to View" option belongs to the Home view (section 6).

### Gaps
- Animation duration in Fusion: not found anywhere. Recollection (unverified): roughly half a second to one
  second, ease-in/ease-out. A tunable value in that range is a reasonable SciForge default.
- What happens when clicking the face that is already current: not documented for Fusion. Recollection
  (unverified): nothing visible happens (camera is already there). Do not treat as confirmed.
- Whether a click also re-centers the camera on the model: not confirmed.

## 4. Face-on controls: curved roll arrows and the four triangles

### Takeaway
In Autodesk ViewCubes, when a face is viewed straight on, small triangles appear next to the cube's four
sides (click one to roll over to the adjacent face) and two curved arrows appear near the top-right (rotate the
view 90 degrees about the viewing axis). This is documented for Inventor/Revit/Maya/Alias and the 2008
paper; it is not explicitly confirmed for Fusion by any text source found.

### Cited Findings
- [OFFICIAL-OTHER] Inventor: "Click one of the triangles displayed near the edges of the ViewCube tool. Each
  triangle switches to one of the adjacent face views." — [Inventor 2026: To Reorient the View](https://help.autodesk.com/cloudhelp/2026/ENU/Inventor-Help/files/GUID-94F44C80-7313-4529-85D1-E64ABF732700.htm)
- [OFFICIAL-OTHER] Inventor roll arrows: the left arrow rotates the view 90 degrees counterclockwise, the
  right arrow 90 degrees clockwise. Revit and Inventor place the roll arrows above and to the right of the
  cube; Alias places them above it. — [Inventor 2026: To Reorient the View](https://help.autodesk.com/cloudhelp/2026/ENU/Inventor-Help/files/GUID-94F44C80-7313-4529-85D1-E64ABF732700.htm); [Revit 2022 ViewCube help](https://help.autodesk.com/view/RVT/2022/ENU/?guid=GUID-E7200513-77CD-42C2-A898-5A4F5BD5B8DA); [Alias: Use the ViewCube tool and NavBar](https://help.autodesk.com/cloudhelp/2014/ENU/Alias/files/GUID-50C3D2D9-16E0-4F88-999C-7D626BF90640.htm)
- [OFFICIAL-OTHER] Maya/Mudbox: in an orthographic (face) view, "four small arrows surrounding the ViewCube"
  rotate the camera to an adjacent orthographic view. — [Maya: Using the ViewCube](https://help.autodesk.com/cloudhelp/2022/ENU/Maya-Basics/files/GUID-C1861E55-85FA-47F9-B4D2-71366875E56D.htm); [Mudbox: Navigate the 3D view](https://download.autodesk.com/global/docs/mudbox2013/en_us/files/GUID-12ACE365-DC1A-4692-ADFA-35A8EF7F659D.htm)
- [RESEARCH/PATENT] The 2008 paper's figure shows triangles "around the edges" pointing to the orthogonal
  faces, a "home" button at the top-left, and "roll" arrows at the top-right. — [Khan et al. 2008, figures via Semantic Scholar](https://www.semanticscholar.org/paper/ViewCube:-a-3D-orientation-indicator-and-controller-Khan-Mordatch/db6644bab70a371cfb4dae856c5840ec56cb7b76/figure/7)
- [LOCAL CODE] FreeCAD's NaviCube has the same kinds of buttons: `ArrowNorth/South/East/West` (step to
  neighbor), `ArrowLeft/ArrowRight` (roll), `DotBackside` (flip 180 degrees to the opposite face) and
  `ViewMenu`. Its step angle is 360 / `NaviStepByTurn` with default 8 (45 degrees), clamped 4-36, so a
  Fusion-like 90-degree step means `NaviStepByTurn = 4`. — [src/Gui/NaviCube.cpp](/home/user/SciForge/src/Gui/NaviCube.cpp) (lines 113-120, 187, 549-616, 1186-1240)

### Inferences
- Layout to copy (general shape only): four small flat triangles just outside the middle of each side of the
  cube's on-screen silhouette, each pointing outward; two small curved arrows near the top-right corner of the
  cube, one per rotation direction. Each triangle rolls the view 90 degrees to the neighboring face; each curved
  arrow rolls the view 90 degrees about the line of sight. Show them only while a face is viewed straight on.
- FreeCAD's NaviCube defaults (45-degree steps, a back-side dot, buttons drawn whenever the pointer is near) are
  not Fusion-like; SciForge should set 90-degree steps and consider hiding the extra back-side dot.

### Gaps
- Fusion-specific confirmation that the triangles and curved arrows exist and appear only in face-on views:
  no text source found. Recollection (unverified): Fusion shows them, same placement as Inventor (triangles
  around the cube, curved arrows top-right), visible on hover while in a face view.
- Whether Fusion's roll arrows animate: not found.

## 5. Drag behavior

### Takeaway
Dragging Fusion's ViewCube orbits the design (official). Autodesk's design adds optional snapping to the
nearest standard view when released near one; whether Fusion snaps or constrains the orbit is not documented.
FreeCAD's NaviCube does something different on drag (it moves the widget), so this must be new work.

### Cited Findings
- [OFFICIAL-FUSION] "Click and drag it to orbit your design." — [Fusion ViewCube reference](https://help.autodesk.com/cloudhelp/ENU/Fusion-GetStarted/files/GS-VIEWCUBE.htm)
- [RESEARCH/PATENT] Patent: when the viewpoint is within a threshold of a face, edge or corner while dragging,
  it "automatically snaps the current viewpoint to that face, edge, or corner." — [US 7,782,319](https://patents.google.com/patent/US7782319B2/en)
- [OFFICIAL-OTHER] "Snap to closest view" (AutoCAD/ProgeCAD wording): the cube snaps to a predefined view when
  dragged near it; default on. "Keep scene upright" prevents the view from turning upside down. — [AutoCAD ViewCube Settings dialog](https://help.autodesk.com/cloudhelp/2016/ENU/AutoCAD-Core/files/GUID-78043EE2-114B-4F08-BFD7-7E5E429708A9.htm); [progeCAD manual: changing view cube settings](https://www.progesoft.com/products/progecad-professional/manual?mp=drawing-in-three-dimensions%2Fviewing-entities-in-three-dimensions%2Fusing-the-view-cube-to-switch-the-view%2Fchanging-view-cube-settings); [Inventor ViewCube Options reference](https://help.autodesk.com/cloudhelp/2019/ENU/Inventor-Help/files/GUID-F91783E5-41BC-46BC-B0CF-9D07FE75C574.htm)
- [FORUM] An Autodesk engineer suspected that dragging the view cube triggers a bug where the cube becomes
  unresponsive (not reproducible on demand). Context only. — [view cube becomes deactivated](https://forums.autodesk.com/t5/fusion-support-forum/view-cube-becomes-deactivated/m-p/11730892)
- [LOCAL CODE] In FreeCAD's NaviCube, a drag on the cube (when `m_Draggable`) moves the widget's position on
  screen (`m_RelPos`), it does not orbit the camera. — [src/Gui/NaviCube.cpp](/home/user/SciForge/src/Gui/NaviCube.cpp) (lines 1273-1287)

### Inferences
- A Fusion-like drag should orbit the camera around the model like the canvas orbit tool, with world-up kept
  upright (turntable style), and the cube rotating in sync. Snapping on release near a standard view is an
  Autodesk-family behavior that would feel familiar, but is optional.

### Gaps
- Free vs constrained orbit when dragging Fusion's cube, and whether it snaps on release: not documented for
  Fusion. Recollection (unverified): it behaves like Fusion's constrained orbit (world-up stays up) and does
  not obviously snap.
- Drag sensitivity (degrees per pixel): not found.

## 6. Home icon and Home view

### Takeaway
A small house icon sits above (upper-left of) the ViewCube; clicking it goes to the Home view. Right-clicking it
or the cube gives "Set current view as Home" with Fit to View or Fixed Distance, plus Reset Home. The default
Home is an isometric corner view; which corner depends on the modeling orientation and sources conflict.

### Cited Findings
- [OFFICIAL-FUSION] "Click the Home icon on the ViewCube to return to the home view." — [Fusion ViewCube reference](https://help.autodesk.com/cloudhelp/ENU/Fusion-GetStarted/files/GS-VIEWCUBE.htm)
- [OFFICIAL-FUSION] "Set current view as Home: Sets the current view as the new home view. Select from the
  following options: Fit to View, Fixed Distance." "Reset Home: Resets the home view to its default." — [Fusion ViewCube reference](https://help.autodesk.com/cloudhelp/ENU/Fusion-GetStarted/files/GS-VIEWCUBE.htm)
- [OFFICIAL-FUSION] To change the Home view: "Right-click the Home button above the view cube", select "Set
  Current View as Home". — [Autodesk support: change the default position for Home view in Fusion](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/How-to-change-the-default-position-for-Home-view-in-Fusion-360.html)
- [RESEARCH/PATENT] The original design places the home button at the top-left of the cube. — [Khan et al. 2008 figure](https://www.semanticscholar.org/paper/ViewCube:-a-3D-orientation-indicator-and-controller-Khan-Mordatch/db6644bab70a371cfb4dae856c5840ec56cb7b76/figure/7)
- [FORUM] Default Home depends on modeling orientation: with Z up, "Top, Right and Back"; with Y up, "Top,
  Front, Right" (a community post roughly four years old; which thread exactly is unclear from search). — [view cube home position](https://forums.autodesk.com/t5/fusion-design-validate-document/view-cube-home-position/td-p/5453761); [Default Orientation/ViewCube](https://forums.autodesk.com/t5/fusion-support-forum/default-orientation-viewcube/td-p/10162606)
- [OFFICIAL-OTHER] Alias: Home is "a special view stored with a model that makes it easy to return to a known
  or familiar view". — [Alias: Use the ViewCube tool and NavBar](https://help.autodesk.com/cloudhelp/2019/ENU/Alias-InterfaceGeneralTasks/files/GUID-50C3D2D9-16E0-4F88-999C-7D626BF90640.htm)
- [TUTORIAL, conflicting] Fit shortcut reported as F (Varsity Tutors) vs F6 (another tutorial). — [Varsity Tutors: View Controls](https://www.varsitytutors.com/practice/subjects/autodesk-fusion-360/lessons/view-controls); [autocadeverything: Fusion 360 Camera](https://autocadeverything.com/fusion-360-camera/)

### Inferences
- "Fit to View" home: going Home re-fits the whole model in that direction (zoom changes with the model).
  "Fixed Distance" home: going Home restores the saved camera distance/zoom exactly. This reading matches the
  same option names in Inventor/Revit; Fusion's page lists the names but the meaning is inferred.
- The Home view is per design (stored with the document) in Autodesk products; SciForge should store it in the
  FreeCAD document, not in user preferences.
- The "Top, Right and Back" claim for Z-up is surprising (most users expect front-right-top). It may describe
  an older Fusion build or a misreading. Verify in current Fusion before copying.

### Gaps
- Current (2024-2026) default Home corner in Z-up designs: not confirmed by an official source.
- Whether the Home icon is always visible or only on hover: not confirmed. Recollection (unverified): appears
  when the pointer is near the cube.
- Fusion's keyboard shortcut for Home (if any) and for Fit: conflicting tutorial claims; not confirmed.

## 7. Context menu (right-click on the cube)

### Takeaway
Fusion's ViewCube context menu (official) contains: Go Home; Camera > Orthographic / Perspective / Perspective
with Ortho Faces; Set current view as Home (Fit to View / Fixed Distance); Reset Home; Set current view as
[Face] and Reset [Face], where [Face] is the face currently toward the camera (for example Front or Top). The
camera options are shared with the Navigation bar's Display Settings camera control.

### Cited Findings
- [OFFICIAL-FUSION] "Go Home: Returns the camera to the home view." — [Fusion ViewCube reference](https://help.autodesk.com/cloudhelp/ENU/Fusion-GetStarted/files/GS-VIEWCUBE.htm)
- [OFFICIAL-FUSION] "Camera: Sets the projection used to render the canvas" with Orthographic, Perspective and
  Perspective with Ortho Faces; the active one shows a checkmark. — [Fusion ViewCube reference](https://help.autodesk.com/cloudhelp/ENU/Fusion-GetStarted/files/GS-VIEWCUBE.htm)
- [OFFICIAL-FUSION] "These camera options are shared with the Camera control in the Navigation bar's Display
  Settings menu." — [Fusion ViewCube reference](https://help.autodesk.com/cloudhelp/ENU/Fusion-GetStarted/files/GS-VIEWCUBE.htm)
- [OFFICIAL-FUSION] "Set current view as [Face]" redefines that named face to the current view; "Reset [Face]:
  Resets the named face shown in the previous option to its default view" (label reads e.g. "Reset Front"). The
  labels update with the face currently facing the camera. — [Fusion ViewCube reference](https://help.autodesk.com/cloudhelp/ENU/Fusion-GetStarted/files/GS-VIEWCUBE.htm) (Portuguese-UI copy with English text: [Fusion Ajuda](https://help.autodesk.com/view/fusion360/PTB/?guid=GS-VIEWCUBE&l=ENU))
- [FORUM] Typical use: rotate until you look straight at what should be the top, right-click the cube, "Set
  Current View as TOP". Autodesk staff note right-clicking the cube lets you set Top or Front relative to Z. — [View Cube and Orientation](https://forums.autodesk.com/t5/fusion-design-validate-document/view-cube-and-orientation/td-p/9540275); [How do I change the X,Y & Z orientation on the view cube?](https://forums.autodesk.com/t5/fusion-manufacture-forum/how-do-i-change-the-x-y-amp-z-orientation-on-the-view-cube/td-p/11262827); [how come my axis colors are off](https://forums.autodesk.com/t5/fusion-design-validate-document/how-come-my-axis-colors-are-off/td-p/6003638)
- [OFFICIAL-OTHER] "Perspective with Ortho Faces" (Inventor): views are perspective unless viewing from one of
  the face views (Top, Bottom, Front, Back, Left, Right), which are shown orthographic. — [Inventor 2024: ViewCube Menu Reference](https://help.autodesk.com/cloudhelp/2024/ENU/Inventor-Help/files/GUID-285B9036-0E97-4F18-A6D2-EF78B8B8FAA9.htm)
- [FORUM] In Fusion, "ortho" in "Perspective with Ortho Faces" refers to the ViewCube's face orientations, not
  to a selected model face: after "Look At" on a part face that is not aligned to a cube face, the view stays
  perspective. — [Ortho Faces with Look At](https://forums.autodesk.com/t5/fusion-design-validate-document/ortho-faces-with-look-at/td-p/11989228)

### Inferences
- "Set current view as Front/Top" changes only how the cube is labeled/oriented relative to the model (and what
  Front/Top clicks do), not the model geometry. "Reset Front" restores the default mapping. In SciForge this
  should be a per-document rotation applied to the cube's reference frame.
- Rough menu order to mirror (from the official list): Go Home / Camera submenu / Set current view as Home
  (two choices) / Reset Home / Set current view as [Face] / Reset [Face]. Use own wording, not Autodesk's.

### Gaps
- Whether Fusion also has a small visible menu button (a down-arrow under or beside the cube, as in AutoCAD,
  Inventor and Alias) or only right-click: not confirmed. Recollection (unverified): right-click only.
- Default projection for new Fusion designs (Perspective vs Orthographic): not confirmed by a source.

## 8. Orientation conventions (Y-up vs Z-up, which plane is Front, default Home)

### Takeaway
Current Fusion's default "Default modeling orientation" is Z up (official); Y up is still available and only
affects new designs. In Z-up, Front looks at the XZ plane, Top at XY, Right at YZ. In Y-up, Front looks at
XY and Top at XZ. Older tutorials and articles assume Y-up, so sources conflict by date.

### Cited Findings
- [OFFICIAL-FUSION] The default modeling orientation is Z up; to use Y up, choose it in Preferences > General,
  click OK and restart Fusion; the ViewCube then reflects the change. — [Fusion Help (preferences)](https://help.autodesk.com/view/fusion360/ENU/?guid=GUID-878489CD-3A23-4303-8450-C2F4F8E410B1); [Autodesk support: change the default XYZ orientation of a new design](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/How-to-change-the-orientation-of-the-origin-planes-in-Fusion-360.html)
- [OFFICIAL-FUSION] API enum `DefaultModelingOrientations`: `YUpModelingOrientation = 0` ("The model Y is the up
  direction"), `ZUpModelingOrientation = 1`. — [Fusion API: DefaultModelingOrientations](https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/DefaultModelingOrientations.htm)
- [FORUM] The setting affects only new designs; open/existing designs keep their orientation, and users
  have asked for it to apply to existing files. — [Modeling orientation (Z up) should apply to all existing design files](https://forums.autodesk.com/t5/fusion-design-validate-document/modeling-orientation-z-up-should-apply-to-all-existing-design/td-p/14069985)
- [FORUM] Z-up became the default "a long time ago - several years"; an older Autodesk support article still
  said Y is up for new designs and appeared outdated. — [Default orientation is now Z-Up in latest version?](https://forums.autodesk.com/t5/fusion-support-forum/default-orientation-is-now-z-up-in-latest-version/td-p/11665030)
- [FORUM/TUTORIAL, older] Earlier Fusion defaulted to Y up. — [SketchUp STL issue #162](https://github.com/SketchUp/sketchup-stl/issues/162); [Lynda: Fusion 360 Basic Part Modeling, Change settings](https://origin-www.lynda.com/Fusion-360-tutorials/Change-settings/685025/689603-4.html); [Lynda: Z up for 3D printing](https://origin-www.lynda.com/Fusion-360-tutorials/Z-up-3D-printing/2810401/2822271-4.html)
- [FORUM] Y-up era: users asked "Why is XZ plane 'top'?" (in Y-up, XZ is the Top plane, so XY is Front). — [Why is XZ plane "top"?](https://forums.autodesk.com/t5/fusion-design-validate-document/why-is-xz-plane-quot-top-quot/td-p/5810257)
- [FORUM] Z-up: the XZ plane is the front face; the ViewCube shows a right-handed system with +Z up. A sketch on
  XZ can show its local vertical axis pointing down (sketch-local axes differ from world axes). — [Sketch on XZ plane shows Z positive downwards](https://forums.autodesk.com/t5/fusion-support/sketch-on-xz-plane-shows-z-positive-downwards-left-handed-coord/td-p/11675127)
- [FORUM] Staff: ViewCube/axis colors differ across tutorials because of the modeling orientation change from
  Y-up to Z-up. — [how come my axis colors are off](https://forums.autodesk.com/t5/fusion-design-validate-document/how-come-my-axis-colors-are-off/td-p/6003638)
- [TUTORIAL, unreliable as surfaced] A Micrographics preference guide was summarized as saying XY becomes the
  front plane in Z-up; that contradicts the forum evidence above and is likely a garbled summary. A blog claim
  that Front shows YZ also conflicts and looks wrong. — [Micrographics: Fusion basic design preference settings](https://mgfx.co.za/blog/fusion-360/fusion-for-basic-design-preference-settings/); [industrialmonitordirect blog](https://industrialmonitordirect.com/blogs/knowledgebase/fusion-360-z-axis-direction-sketch-vs-model-coordinate-system)

### Inferences
- Z-up (current default) mapping, consistent with a right-handed system and the forum evidence:
  Front = camera on the -Y side looking along +Y at the XZ plane (X to the right, Z up); Back = the opposite;
  Right = camera on the +X side looking along -X at the YZ plane (+Y to the right, Z up); Left = the opposite;
  Top = camera above looking down -Z at XY (X right, +Y up on screen); Bottom = camera below looking up +Z.
- Y-up mapping: Front = camera on the +Z side looking along -Z at the XY plane (X right, Y up); Top = camera
  above looking down -Y at XZ (X right, -Z up on screen); Right = camera on the +X side looking along -X at YZ.
- FreeCAD is natively Z-up with the same Front = XZ convention, so SciForge's Z-up default needs no axis remap;
  supporting Y-up would be a cube-frame rotation, like "Set current view as Top".
- Default Home in Z-up is most likely the front-right-top isometric (camera at +X, -Y, +Z), but see the
  conflicting forum claim in section 6.

### Gaps
- Exact Fusion release that switched the default to Z up: not found.
- Official statement of the default Home corner for Z-up: not found.

## 9. Axis triad / origin indicator and ViewCube-related preferences

### Takeaway
Fusion's ViewCube carries a small X/Y/Z triad with letters (red/green/blue). Fusion exposes very few ViewCube
settings: show/hide (View menu, Ctrl+Alt+V on Windows), the shared camera projection, "Animate view transitions"
and the modeling orientation. No size, opacity, compass, snap or "keep scene upright" settings are documented
for Fusion; those exist in AutoCAD, Inventor, Maya and 3ds Max.

### Cited Findings
- [OFFICIAL-FUSION] ViewCube shows X, Y, Z letters per axis; red X, green Y, blue Z. — [Autodesk support: XYZ letters as shown in the View Cube](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/Is-it-possible-to-place-the-letter-X-Y-Z-on-the-origin-axes-as-is-shown-in-the-View-Cube.html)
- [OFFICIAL-FUSION] Show/Hide ViewCube shortcut: Ctrl+Alt+V (Windows), Option+Command+V (macOS). — [Fusion Help: keyboard shortcuts](https://help.autodesk.com/view/fusion360/ENU/?guid=GUID-F0491540-0324-470A-B651-2238D0EFAC30); [Autodesk Fusion shortcuts guide](https://www.autodesk.com/shortcuts/fusion-360)
- [TUTORIAL/FORUM, conflicting] CAD Forum gives View > Show/Hide ViewCube (Ctrl+Alt+V) and Ctrl+Command+V on Mac;
  a forum user reported Shift+Command+C on macOS 15.2 with Fusion 2.0.20981. — [CAD Forum: hide or display ViewCube in Fusion](https://www.cadforum.cz/en/how-to-hide-or-display-viewcube-in-fusion-360-tip11679); [View cube disappears](https://forums.autodesk.com/t5/fusion-support-forum/view-cube-disappears/td-p/13236116)
- [OFFICIAL-FUSION] ViewCube camera projection is shared with Navigation bar > Display Settings > Camera. — [Fusion ViewCube reference](https://help.autodesk.com/cloudhelp/ENU/Fusion-GetStarted/files/GS-VIEWCUBE.htm)
- [OFFICIAL-FUSION] "Animate view transitions" preference (named view and sketch view transitions). — [Fusion Help (preferences)](https://help.autodesk.com/view/fusion360/ENU/?guid=GUID-878489CD-3A23-4303-8450-C2F4F8E410B1)
- [OFFICIAL-FUSION] Fusion's orbit/pan/zoom presets (General preferences) and Mac gesture-based navigation are
  separate from the ViewCube. — [Fusion blog: How to set your pan, zoom & orbit controls](https://www.autodesk.com/products/fusion-360/blog/quick-tip-pan-zoom-orbit-preferences/)
- [OFFICIAL-OTHER] Other products' ViewCube settings: Inactive Opacity, Size, Snap to closest view (default on),
  Fit-to-view / Zoom to extents after view change, Use animated transitions, Keep scene upright, Show compass.
  — [AutoCAD ViewCube Settings dialog](https://help.autodesk.com/cloudhelp/2016/ENU/AutoCAD-Core/files/GUID-78043EE2-114B-4F08-BFD7-7E5E429708A9.htm); [Inventor ViewCube Options reference](https://help.autodesk.com/cloudhelp/2019/ENU/Inventor-Help/files/GUID-F91783E5-41BC-46BC-B0CF-9D07FE75C574.htm); [Maya ViewCube preferences](https://help.autodesk.com/cloudhelp/2016/ENU/Maya/files/GUID-F8DD60C0-A955-4D51-9D3D-9FFE1E8D3D16.htm); [3ds Max ViewCube panel](https://help.autodesk.com/view/3DSMAX/2024/ENU/?guid=GUID-775D2B7E-3EFB-4769-94F8-0FCA49F2EE6C)
- [RESEARCH/PATENT] A later Autodesk patent covers a "configurable viewcube controller" (details not read). — [US 9,043,707 Configurable viewcube controller (USPTO PDF)](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/9043707)
- [LOCAL CODE] FreeCAD NaviCube already has parameters for corner position, offset, chamfer, step-by-turn,
  rotate-to-nearest, hilite/base/emphasis colors, inactive opacity, label texts and fonts, and show-CS. — [src/Gui/NaviCube.cpp](/home/user/SciForge/src/Gui/NaviCube.cpp) (lines 263-377)

### Inferences
- A Fusion-faithful SciForge ViewCube needs only: show/hide toggle with a shortcut, projection choice shared with
  the bottom navigation bar, an "animate view transitions" switch, the per-document Home and face redefinition,
  and the modeling-orientation preference. Everything else can stay as fixed internal defaults.

### Gaps
- Whether Fusion has any "keep scene upright" style option for the ViewCube: none found (absence of evidence).
- Whether the triad sits at a cube corner or beside the cube, and its exact edge alignment: not confirmed.
- Fusion API details for camera transitions (for example a smooth-transition flag on the Camera object):
  Recollection (unverified) only; not sourced in this session.
