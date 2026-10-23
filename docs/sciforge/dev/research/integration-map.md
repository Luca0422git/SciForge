# Integration map: new SHEET METAL / PLASTIC tabs (and SURFACE part 3)

Read from `develop` @ 6d00b8b plus the orchestrator's uncommitted scaffold that was in the main
tree while this was written (the `*_ops.py` / `*_schema.py` stubs, the `icons_<area>.py` loader in
make_icons.py, `sheetmetal.py`, `sheetmetal_core.py`). Paths are relative to `src/Mod/SciForge/`
unless they start with `tools/`. `file:N` = line N.

## 0. The traps most likely to bite (read these first)

1. `COMMANDS = {...}` must be a **literal dict with string-literal keys** at module level of a
   **top-level** `sciforge/<name>_ui.py`. The ribbon unit test reads it with `ast`, and
   `commands._feature_commands` imports only `sciforge/*_ui.py`, not files in sub-packages.
2. A ribbon item that names a command no `*_ui.py` defines yet fails `test_ribbon_config`. Keep
   it `None` (greyed out) until your command exists. An icon name with no `.svg` fails too.
3. The ribbon reads the set of available commands **once**, when it is built
   (`ribbon_ui.py:340`). A `*_ui.py` that raises on import is skipped with only a warning, and
   its buttons stay greyed. The unit tests still pass, so only a GUI scenario proves the import works.
4. Contextual tabs are hard-coded as `"sketch"` and `"drawing"` in 5 places in `ribbon_ui.py`.
   `set_drawing_mode(False)` makes **every** non-sketch tab visible again, which includes any
   new contextual tab (see 1.4).
5. Picks survive edits automatically when they are stored in `App::PropertyLinkSub*`
   properties of a PartDesign feature inside a body (`picks.py`).
6. FreeCAD writes `module.Class` of every Proxy and view provider into saved files. Never rename
   a step's module or its classes after the first commit.
7. The harness fails a scenario on any Report-view error **or SciForge warning** after a step.
   A `warn()` from a missing icon, a missing big-button label or a missing shortcut target
   therefore fails every scenario that builds the ribbon.

---

## 1. Ribbon

### 1.1 From data to widgets

`sciforge/ribbon_config.py` (pure data, unit tested):

```python
SEP = None                                                       # :18 separator
def item(label, command, icon=None, key="", note="", checked=None, toggle=None)   # :21
def sub(label, items, icon=None, note="")                        # :35 submenu
def group(gid, title, big, items)                                # :40 big = labels shown as big icons
```

- A command slot can be `"Name"`, `"Name#2"` (entry 2 of a FreeCAD drop-down), `("A", "B")`
  (the first one that exists) or `None` (greyed out) (`:10-15`).
- Existing groups:
  - `SURFACE_CREATE` `:504` and `SURFACE_MODIFY` `:525`.
  - Shared groups, reused by identity in several tabs: `CONSTRUCT` `:175`, `INSPECT` `:214`,
    `INSERT` `:245`, `SELECT` `:354`.
- `TABS` `:1077-1137` is an ordered list of `{"id", "title", "groups", ["contextual": True]}`.
  Current order: solid, surface, mesh, utilities, sketch (contextual), drawing (contextual).
  Fusion's order puts SHEET METAL and PLASTIC after MESH and before UTILITIES.
- The SURFACE tab is defined as:
  `{"id": "surface", "title": "SURFACE", "groups": [SURFACE_CREATE, SURFACE_MODIFY, CONSTRUCT, INSPECT, INSERT, SELECT]}`.
- Helpers:
  - `iter_items` `:1545`.
  - `all_items` `:1556` skips a group it has already seen, by `id()`.
  - `find(grp, label)` `:1570` returns the first match and also searches submenus.
  - `command_names` `:1584`.

`sciforge/ribbon_ui.py` turns that data into Qt widgets:

- `RibbonWidget.__init__` `:335`:
  - `available = registry.available_commands()` `:340`, which is `set(Gui.listCommands())`
    (`registry.py:7`). It is computed once.
  - For each tab (`:362-384`) it makes a checkable tab button whose click runs
    `select_tab(id, user=True)`, plus a page holding one `GroupWidget(grp, available, tab_id=id)`
    per group, separated by `_separator()`.
- `resolve(command, available)` `:15` returns `(name, index)` or `None`.
- `run(resolved, label)` `:28` calls `recent.record(...)`, then `Gui.runCommand` inside try/warn.
- `GroupWidget` `:215`:
  - `refresh()` `:246` makes the big buttons for `group["big"]` and the pinned commands.
  - A big label that is not in the group logs `warn("ribbon: '%s' is not in group %s")`.
  - The drop-down menu is `build_menu` `:157`.
- A big button's objectName is `"SciForgeBig_" + label.replace(" ", "_")` (`:303`).
  `harness.ribbon(label)` clicks the first *visible* button with that name.

### 1.2 An item whose command does not exist (yet)

- When `resolve()` returns `None`:
  - The big button gets `setEnabled(False)` and the tooltip `note` or "Not available in SciForge
    yet" (`ribbon_ui.py:300-302`).
  - The menu entry is greyed the same way (`:201-203`).
  - No warning, no error.
- A command registered after the ribbon was built stays greyed until FreeCAD restarts.
- A `*_ui.py` that fails to import: `_feature_commands` logs `warn("could not load %s: %s")`
  (`commands.py:374-375`), and all of that module's buttons are greyed.

### 1.3 Tests that check the ribbon (and which fail on not-yet-built commands)

`SciForgeTests/unit/test_ribbon_config.py` (plain Python):

| test | fails when |
|---|---|
| `:64 test_every_icon_exists` | any non-None `icon` (submenus included) has no `sciforge/icons/ui/<icon>.svg`. **Fails for icons not drawn yet**: point at an existing icon (`not_available`, or a close one) until yours exist |
| `:79 test_big_buttons_exist_in_their_menu` | a `big` label is not found by `cfg.find` |
| `:84 test_mapped_commands_exist_in_freecad_1_1_4` | a non-None slot names nothing in `freecad_1_1_4_commands.txt`, the hand list `:16-28` or the keys of every `COMMANDS = {literal}` in `sciforge/*_ui.py` (AST, `:30-51`; comprehensions and `COMMANDS.update()` are invisible). **Fails for `"SciForge_Flange"` until a `*_ui.py` defines it**: use `None` |
| `:93 / :97` | a `config.SHORTCUTS` target is unknown, or two commands share a key |
| `:101` | the sketch tab is not contextual or has no FINISH SKETCH group |
| `:106` | SOLID's groups are not in Fusion's order |
| `:113` | Press Pull is not first in MODIFY with key Q |

Other tests that read the ribbon:

- `test_surface_core.py:127-170` (surface-3 must keep these):
  - `SURFACE_CREATE` contains Extrude, Revolve, Sweep, Loft, Patch, Ruled, Offset, Thicken and
    Boundary Fill, with `("Patch", "SciForge_Patch")`.
  - `SURFACE_MODIFY` contains Trim, Untrim, Extend, Stitch, Unstitch and Reverse Normal.
  - `SOLID_CREATE` has `("Thicken", "SciForge_Thicken")` and
    `("Boundary Fill", "SciForge_BoundaryFill")`.
- `test_inspect_core.py:60,68`: `TABS[0]` is SOLID and has groups `construct` and `inspect`.
  **Keep SOLID first.**
- GUI `smoke_gui.py:120-145` checks the state at start-up:
  - the SOLID tab is selected and the SKETCH tab is hidden;
  - SOLID's visible groups start with CREATE, MODIFY, CONSTRUCT;
  - `registry.MISSING` is empty (it is only about `config.GROUPS`).
- GUI `scenarios/ribbon_sweep.py:16,40-151` clicks every resolved command of the tabs in
  `$SWEEP_TABS` (default `solid,sketch`). Any pop-up or error fails it. Run it as
  `SWEEP_TABS=sheet_metal,plastic` to sweep your own tab.
- Nothing enforces unique labels. `find()`, pins and `h.ribbon()` all go by label, so keep
  labels unique within a group.

### 1.4 Contextual tabs (SKETCH, DRAWING) and how to add FLAT PATTERN

`"contextual": True` (`ribbon_config.py:1109, :1123`) is **not read by ribbon_ui**. The ids are
hard-coded:

```python
self.tab_buttons["sketch"].setVisible(False)                      # ribbon_ui.py:394
if "drawing" in self.tab_buttons: self.tab_buttons["drawing"].setVisible(False)   # :397-398
def select_tab(self, tab_id, user=False):                        # :620
    ...
    if user and tab_id not in ("sketch", "drawing"):
        self._user_tab = tab_id                                   # where Finish Sketch goes back to
def set_sketch_mode(self, on):                                    # :627-636: show/select "sketch", back to _user_tab
def set_drawing_mode(self, on):                                   # :638-656
    for tid, button in self.tab_buttons.items():
        if tid == "drawing": button.setVisible(on)
        elif tid == "sketch": button.setVisible(self._sketch_mode and not on)
        else: button.setVisible(not on)            # <- would also show a new contextual tab on exit
    self.workspace.setText("DRAWING ▾" if on else "DESIGN ▾")
def current_tab(self)                                             # :658
```

How each contextual tab is entered and left:

- **SKETCH**: `shell.on_workbench(name)` (`shell.py:55-85`). FreeCAD switches to the Sketcher
  workbench while a sketch is edited, which calls `_set_sketch_mode(True)` (`:63-68`). Coming
  back to the SciForge workbench calls it with `False`. `_set_sketch_mode` (`:153-155`) calls
  `ribbon.set_sketch_mode`.
- **DRAWING**: `drawing_ui._set_mode(on)` (`drawing_ui.py:325-332`) calls
  `shell.ribbon().set_drawing_mode(on)` (guarded with `hasattr`). It is run by the drawing's
  `_window_changed` / `sync_mode` (`drawing_ui.py:287-318`) when the active window tab changes.

Recipe for the FLAT PATTERN tab (owner sm-flat, the only builder that edits `ribbon_ui.py`):

1. Add `{"id": "flat_pattern", "title": "FLAT PATTERN", "contextual": True, "groups": [...]}` to
   `TABS` after `drawing`. Fusion's groups end with FINISH FLAT PATTERN.
2. Changes in `ribbon_ui.py`:
   - Replace `:394-398` with a loop that hides every tab whose `tab.get("contextual")` is set.
   - Make `select_tab` skip every contextual id when it remembers `_user_tab`.
   - Add `set_flat_pattern_mode(on)`, a copy of `set_drawing_mode`: show only `flat_pattern`; on
     exit select `"sheet_metal"` (or `_user_tab`).
   - Patch the `else:` branch of `set_drawing_mode` so it never shows a contextual tab.
   - Patch `set_sketch_mode` so a sketch opened in the flat pattern returns to `flat_pattern`
     (today it returns to `_user_tab`).
3. Call `r = shell.ribbon(); if r is not None and hasattr(r, "set_flat_pattern_mode"):
   r.set_flat_pattern_mode(on)` (`r` is `None` while SciForge is off):
   - with `on=True` from Create Flat Pattern and from a double-click on the browser node;
   - with `on=False` from Finish Flat Pattern, closing or switching the document, an undo that
     removes the flat pattern, and Esc.
   Keep your own state, as `drawing_ui.STATE["mode"]` does.
4. Check in scenarios with
   `ribbon.current_tab() == "flat_pattern" and ribbon.tab_buttons["flat_pattern"].isVisible()`
   (as `smoke_gui.py:269` and `scenarios/drawing_new.py:100` do).

### 1.5 Switching between SOLID, SURFACE and MESH, and what is kept per tab

- Per tab:
  - **Pins** (`ribbon_pins.py:21` `slot(tab_id, group_id)` = `"tab/group"`, kept as JSON in the
    parameter `Mod/SciForge/Ribbon/Pinned`). Shared groups get separate pins in each tab.
  - `RibbonWidget._user_tab`.
- Not per tab:
  - shortcuts (`config.SHORTCUTS` is global; `shortcuts.apply` binds `QShortcut`s on the main
    window);
  - search;
  - recent / repeat (`recent.record`);
  - the marking menu (`ribbon_config.MARKING_MENU`, static).
- **Ids to use:** tab ids `sheet_metal` and `plastic`. The scenario helper
  `insert_steps.ribbon_tab(label)` (`SciForgeTests/gui/insert_steps.py:189`) does
  `tab_buttons.get(label.lower())`, so pass it the **id**, e.g. `ins.ribbon_tab("sheet_metal")`.
  Group ids follow SURFACE's `s_create` / `s_modify`: use `sm_create`, `sm_modify`, `p_create`,
  `p_modify`, `fp_...`.

---

## 2. Commands

**Registration.** `workbench.build` calls `commands.register_all()` (`commands.py:380-390`),
which adds `FORGE_COMMANDS` and the result of `_feature_commands()` (`:342-377`):

```python
for filename in sorted(os.listdir(here)):          # sciforge/ only, not sub-packages
    if not filename.endswith("_ui.py"): continue
    module = importlib.import_module("." + name, __package__)
    found.update(getattr(module, "COMMANDS", {}))
    taskui.EDITORS.update(getattr(module, "EDITORS", {}))       # timeline/browser double-click
    taskui.MENU_EXTRAS.update(getattr(module, "MENU_EXTRAS", {}))
# except: warn("could not load %s: %s") and go on
```

Code at module level of a `*_ui.py` runs once, at registration. For example `surface_ui.py`
installs its document observer there (`:2945-2953`). Wrap such code in try/warn.

**Command class pattern** (`rib_ui.py:607-668`):

```python
def _start(kind):
    try:
        if not commands.finish_open_dialog(): return
        if commands.find_body() is None:
            commands.tell("Rib needs a part and a sketch curve: make the part first."); return
        Gui.Control.showDialog(RibPanel(App.ActiveDocument, kind)); log("rib started")
    except Exception as exc:
        warn("Rib failed to start: %s" % exc)
class RibCommand:
    def GetResources(self): return {"MenuText": "Rib", "ToolTip": "...", "Pixmap": ui_icon_path("rib")}
    def IsActive(self): return App.ActiveDocument is not None
    def Activated(self): _start("rib")
COMMANDS = {"SciForge_Rib": RibCommand, "SciForge_Web": WebCommand}
EDITORS = {"SciForge::Rib": edit, "SciForge::Web": edit}
```

**Search.** `search_ui._build_entries` (`search_ui.py:26-41`) lists every `Gui.listCommands()`
entry under its `MenuText`. A new command appears there by itself; `search_core.rank` does the
fuzzy matching. Use Fusion's label as the `MenuText`.

**Shortcuts.**

- `config.SHORTCUTS` (`config.py:146`) maps a command to a key.
- `config.PREFERRED` (`:189`) maps a FreeCAD command to the SciForge command that replaces it.
- `shortcuts.apply` (`shortcuts.py:99-153`) logs `warn("no shortcut for (command not found)")`
  when a target is missing. So never add a key before the command exists, and never repeat a key.
- `item(key=...)` only shows the key in the menu (`command_options.key_for :76`).

**Bodies.**

- `commands.find_body()` (`:17-68`):
  1. The active body, unless it is a surface body (`:29`) or not made yet at the marker.
  2. Otherwise, in this order: the active component's preferred body, the selection's body,
     then the component's other bodies.
  3. It then drops used-up bodies (`bodies.consumed`) and surface bodies (`:56`), prefers
     bodies that exist at the marker, activates the one it picks and returns it, or `None`.
- `ensure_body()` (`:193-224`) also creates a body (FreeCAD's `PartDesign_Body`) and places it
  in the active component.

**Messages and dialogs.**

- `tell(msg)` (`:112-136`) shows a tooltip at the mouse and logs it; it is shown again after
  250 ms.
- `finish_open_dialog()` (`:165-190`): when a task dialog is open, it calls
  `taskui.current().finish()` (OK, or Cancel when OK is refused) or `leave_edit()`. It returns
  False and `tell()`s the user if something is still open.
- `leave_edit()` (`:139-162`): never call `resetEdit()` on a sketch.

---

## 3. Body kinds: how SURFACE bodies were integrated

A surface body is a `PartDesign::Body` whose Tip has faces and no solid
(`surface.is_surface_body`, `surface.py:122-128`). Every special case **outside** `surface*.py`:

| file:line | what it does |
|---|---|
| `commands.py:29` | `find_body`: an active surface body is passed over |
| `commands.py:56` | `find_body`: surface bodies are removed from the candidates |
| `commands.py:87-94` | helper `_is_surface_body` (lazy import; on an exception returns False) |
| `sketch_ui.py:686-695` | `create_sketch`: a face of another body moves the sketch into that body, **unless** it is a surface body |
| `sketch_ui.py:719-724` | helper `_surface_body` |
| `browser_ui.py:92-97` | helper `_is_surface_body` |
| `browser_ui.py:174-175` | `_objects()`: `if obj.TypeId in core.BODY_TYPES and _is_surface_body(obj): row["surface"] = True` |
| `browser_core.py:206-224` | body node icon: `"ground" if grounded else ("surface_body" if obj.get("surface") else "box")`. The icon is part of `signature()` (`:382`), so the row redraws when it changes |
| `timeline_core.py:221-225` | `KINDS.update(surface_core.TIMELINE_KINDS)` and `KIND_BY_SCIFORGE_TYPE.update(surface_core.TIMELINE_BY_TYPE)` (`surface_core.py:276-305`) |
| `surface.py:986-992` | a new body for a CREATE tool: `components.new_body_in(doc, component)` (`components.py:219`) or `components.body_for_new(src_body, new_component)` (`:230`) |
| `surface.py:995-1015` | a step is `bodies.insert_after_tip` + `SurfaceFeature` + `SurfaceViewProvider` (`surface_ui.py:2740-2777`, icon by kind) |
| `surface_ui.py:2917-2953` | a document observer that deletes a step's followers and pieces with it |
| `test_surface_core.py:80-85` | the icons of every kind and of `surface_body` exist |

**Sheet metal contract** (scaffold `sciforge/sheetmetal.py`):

- A body is sheet metal when its `App::PropertyString` `SciForgeSheetMetalRule` is non-empty.
- Functions: `is_sheet_metal_body(body)`, `make_sheet_metal_body(body, rule)`,
  `rule_for_body(body)`, `sheet_metal_bodies(doc)`.

What to add for sheet metal bodies, the same way as surfaces:

- **Browser icon** (sm-forming):
  - In `browser_ui._objects`, next to `:174`, add `row["sheet_metal"] = True` (a lazy-import
    helper like `:92`).
  - In `browser_core.py:209`, check `sheet_metal` before `surface`. Order: ground, then
    sheet_metal_body, then surface_body, then box.
- **`find_body`: do not skip sheet metal bodies.** SOLID tools work on them in Fusion (Extrude
  cut, Hole, patterns). SHEET METAL tools should pick their own target:
  1. the active body, if `is_sheet_metal_body`;
  2. else the first sheet metal body of the active component (`components.bodies_in(doc,
     component)` `:133`, skipping `commands.not_made_yet`);
  3. else make a new one.
  Leave `commands.py` alone (a shared file).
- **`sketch_ui.create_sketch`:** no change. A sketch on a sheet metal face goes into that body,
  as on a solid.
- **A flat pattern object kept outside the body chain** (for example a `Part::FeaturePython` at
  component level; never put it in `Body.Group`):
  - By default it is a timeline step: `timeline_ops._is_step` (`:509-524`) treats any
    `Part::Feature` or any object with a `SciForgeType` as a step. Use
    `bodies.hide_from_timeline(obj)` (`bodies.py:299`, `SciForgeTimeline=False`) or set
    `SciForgeRole` (`timeline_ops.is_helper :460-463`).
  - `browser_core._folders` drops it unless you add:
    - an `elif sciforge_type == "FlatPattern":` branch (put it before `elif type_id in SKETCH_TYPES:`,
      `:263`);
    - its node or folder (next to `if drawings:`, `:309`);
    - a kind in `MENUS` (`:463`);
    - handlers in `browser_ui.build_menu` (`:1371-1420`) and `_double_clicked` (`:1050`).
  - These are other parts of the file than sm-forming's icon change at `:206-224`.
- **Timeline names and icons.** `timeline_core.classify` (`:253-268`) maps
  `"SciForge::<SciForgeType>"` through `KIND_BY_SCIFORGE_TYPE`. Failing that, it turns the
  CamelCase type into snake_case and looks it up in `KINDS`. Failing that, the kind is `other`:
  the title is the type's words ("Edge Flange") and the icon is `workspace_design`.
  - So `SciForgeType="EdgeFlange"` plus `KINDS["edge_flange"] = ("Flange", "sm_flange")` is
    enough.
  - To avoid editing this shared file, register from your own `*_ui.py` at import:
    `timeline_core.KINDS.update(MY_KINDS)` (and `KIND_BY_SCIFORGE_TYPE.update(...)` when the
    names differ). Alternatively, the orchestrator adds an import block once, like `:221-225`.
  - A kind that may never carry the history marker goes in `NON_SOLID_KINDS` (`:228-246`).

---

## 4. Steps (SciForge FeaturePython features)

### 4.1 The proxy (copy `rib.py:523-595`, `shelling.py:502-577` or `surface.py:167-227`)

```python
class FlangeFeature:            # saved as "sciforge.<module>.FlangeFeature": NEVER rename
    def __init__(self, obj):
        obj.Proxy = self
        self.ensure_properties(obj)
    @staticmethod
    def ensure_properties(obj):                       # idempotent: also adds props to old files
        def add(kind, name, doc, group="Flange"):
            if name not in obj.PropertiesList:
                obj.addProperty(kind, name, group, doc); return True
            return False
        add("App::PropertyLinkSubListGlobal", "Edges", "Picked edges")   # picks: LinkSub* props
        if add("App::PropertyLength", "Height", "Height"): obj.Height = 10.0  # numbers: typed props
        if add("App::PropertyEnumeration", "BendPosition", "..."): obj.BendPosition = ["Inside", "Outside"]
        if add("App::PropertyBool", "Refine", "Merge coplanar faces"): obj.Refine = True
        bodies.mark(obj, "EdgeFlange")                 # hidden SciForgeType (bodies.py:286)
    def onDocumentRestored(self, obj): self.ensure_properties(obj)
    def execute(self, obj):
        try:
            base = obj.BaseFeature.Shape                 # body-local
            obj.Shape = compute(...)                     # must be body-local too
        except Exception:
            bodies.pass_through(obj)                     # bodies.py:327: body shown as before, step red
            raise
    def dumps(self): return None
    def loads(self, state): return None
    __getstate__ = dumps
    __setstate__ = loads
```

**Making a step.**

- `step = bodies.insert_after_tip(body, "PartDesign::FeaturePython", name)` (`bodies.py:374`)
  makes the object and sets `body.Tip`. `BaseFeature` becomes the previous solid; `emboss.py:908`
  also sets it explicitly.
- Then `FlangeFeature(step)`.
- Then the view provider, only when `App.GuiUp`, imported lazily from your `*_ui.py` inside try
  (`rib.py:621-630`, `shelling.py:589-599`).

**Coordinates.**

- `BaseFeature.Shape` and `obj.Shape` are in the body's own coordinates.
- To work in design coordinates: `curves.to_global(shape, feature)` (`curves.py:52`), then come
  back with `bodies.to_local(shape, body)` (`bodies.py:228`, as surface does) or with
  `body.getGlobalPlacement().inverse()` (as rib does, `rib.py:575-580`).

**Choices.**

- Store the choices FreeCAD cannot hold as JSON in a hidden string property with
  `bodies.save_meta` / `load_meta` (`bodies.py:304-316`).
- Existing ones: `"SciForgeRib"`, `"SciForgeSurface"`, `"SciForgeShell"`.

### 4.2 The view provider (`rib_ui.py:571-604`)

```python
class ViewProviderFlange:                 # saved as "sciforge.<x>_ui.ViewProviderFlange": never rename
    def __init__(self, vobj): vobj.Proxy = self
    def attach(self, vobj): self.Object = vobj.Object
    def getIcon(self): return ui_icon_path("sm_flange")      # browser/tree icon
    def setEdit(self, vobj, mode=0):
        if mode != 0: return None
        edit(vobj.Object); return True
    def unsetEdit(self, vobj, mode=0): return None
    def doubleClicked(self, vobj): edit(vobj.Object); return True
    def dumps(self): return None
    def loads(self, state): return None
    __getstate__ = dumps
    __setstate__ = loads
```

`bodies_gui.StepViewProvider` (`:46-77`) could be reused, but its icon map `ICONS` (`:20-39`) is
a shared dict. Use your own view provider.

### 4.3 Editing, the timeline and Change Parameters

**Editing routes.**

- A double-click in the timeline goes to `timeline_ui.edit` (`:1155-1173`): it rolls the marker
  if needed, activates the body, then calls `taskui.edit_object(obj)`.
- `taskui.edit_object` (`:99-119`): first `finish_open_dialog()`, then
  `EDITORS.get(type_key(obj))`. `type_key` is `"SciForge::" + SciForgeType`, or the `TypeId`
  (`:94`). Without an editor it falls back to `Gui.ActiveDocument.setEdit(obj.Name)`, which
  reaches `vp.setEdit`.
- The browser's "Edit Feature" takes the same route.
- Declare `EDITORS = {"SciForge::EdgeFlange": edit}`.
- `edit(feature)` opens the Panel with `feature=`; its undo step is `"Edit X"`
  (`rib_ui.py:655-664`).
- `MENU_EXTRAS = {"SciForge::X": [(text, fn(obj), enabled(obj))]}` adds entries to the
  timeline's right-click menu (`timeline_ui.py:1528`).

**How the timeline shows a step.**

- Title: `"<KINDS title> <n>"`, numbered per kind, or the user's own name once renamed
  (`timeline_core.build :470-485`).
- Icon: `KINDS[kind][1]`.
- A step is "solid" (it can be the Tip and rolls back with the marker) unless its kind is in
  `NON_SOLID_KINDS`.
- Red or yellow comes from `obj.State` / `getStatusString` (`timeline_ops.problem`).
- Helpers made for a step are hidden with `SciForgeRole`, or with `SciForgeTimeline=False`
  (`bodies.hide_from_timeline`).

**Change Parameters.**

- `parameters.model_parameters` (`parameters.py:183-211`) lists two tables:
  - `FEATURE_PROPS[TypeId]` (`:18-33`);
  - `SCIFORGE_PROPS[SciForgeType]` (`:36-63`).
  It skips properties whose editor mode is hidden.
- No module extends these tables today, so surface steps are not listed (a gap).
- Add yours at import time from your `*_ui.py`:
  `parameters.SCIFORGE_PROPS["EdgeFlange"] = [("Height", "Height"), ("Angle", "Angle")]`.
- Formulas typed in fields:
  - `preview.set_formula(obj, prop, text)` and `preview.formula_of` (`preview.py:223-247`);
  - `preview.FormulaInput(panel, key, field)` (`:132`);
  - `taskui.DistanceField.bind(obj, prop)` (`taskui.py:146`).

### 4.4 References that survive edits

**Automatic** (`picks.py`).

- `install()` runs in `timeline_ops.py:298` and in `ai/ops/core.py:58`.
- Covered: every `App::PropertyLinkSub*` of any PartDesign feature (FeaturePython included)
  that sits in a body (`picks.watched :110`).
- How:
  - after each good compute it remembers where the picked elements are, in the hidden
    `SciForgePicks`;
  - when FreeCAD loses a name (`"?FaceN"`), it points the link at the element found again
    before the step computes.
- **You get this for free** if your picks are in LinkSub properties and your feature has no
  `SciForgeLinkMemory` property.

**Managed by the step itself** (`surface.py:202-217`):

```python
curves.refind(obj, LINKS)      # before compute (curves.py:397)
...; curves.remember(obj, LINKS)   # after a good compute (curves.py:366); kept in "SciForgeLinkMemory"
```

**When an earlier step is edited from a dialog:**

- `follow.snapshot(body, after)` before the change, then `follow.recompute(doc, records)` after
  it (`follow.py:182, :287`), as Shell, Draft and Scale do;
- `blend.References(body, after)` (`blend.py:624`) keeps later fillets on their edges;
- `revolve.FaceLink` (`revolve.py:1063`) is a hidden copy of picked profile faces.

---

## 5. Icons

**How they are drawn** (`tools/sciforge/make_icons.py`).

- `@icon("name")` registers a function that returns SVG elements on a 48×48 canvas.
- Drawing helpers (`:68-217`): `poly`, `line`, `path`, `circle`, `rect`, `ellipse`, `pt`, `iso`,
  `block(x, y, z, dx, dy, dz, colors, ox, oy)`, `plus_badge`, `warn_badge`, `arrow`.
- `svg()` frames a tight viewBox (`:219`).
- Palette (`:35-46`): `GREY`, `BLUE`, `DBLUE`, `GREEN`, `ORANGE`, `PURPLE`, `GOLD`, `RED`,
  `STROKE`, `POINT`, `WHITE`, `DARK`.

**Fewest merge conflicts** (scaffold, `make_icons.py:2532-2539`, not committed yet when this
was written).

- Every `tools/sciforge/icons_<area>.py` is run inside make_icons' globals, in sorted order.
  Put your icons there (`icons_sheetmetal.py`, `icons_flatpattern.py`, `icons_plastic.py`,
  ...). **Never edit `make_icons.py`.**
- Names are global: a later file silently replaces an earlier icon of the same name.
- `main()` (`:2555`) deletes `icons/ui/*.svg`, then writes the RAW icons and every `ICONS` entry.
  The result is deterministic.
- Run `python3 tools/sciforge/make_icons.py`; `git status` must show only your new `.svg`
  files. Commit them.

**Naming.**

- snake_case with an area prefix. Existing prefixes: `sk_`, `dw_`, `mesh_`, `nav_`, `qa_`, `tl_`,
  `surface_`, `joint_`, `select_`.
- Proposed: `sm_` (sheet metal), `fp_` (flat pattern), `pl_` (plastic).
- Body icon: `sheet_metal_body`.

**Using an icon.**

- A ribbon item's `icon` is the name.
- In code:
  - `ui_icon(name)` gives a QIcon. A missing file **warns** "missing icon" and shows
    `not_available` instead.
  - `ui_icon_path(name)` gives a path for `Pixmap` and `getIcon`.
  - Both are in `sciforge/__init__.py:48-93`.

**Light look.**

- `ui_icon_path` makes a light copy that swaps the colours in `_LIGHT_INK`
  (`__init__.py:36-44`): `STROKE #dfe3e8`, `WHITE #f5f5f5` and the `GREY` faces.
- Draw strokes and marks with `STROKE` / `WHITE`, and neutral solids with `GREY`, so they
  darken. The `BLUE` accents stay as they are.
- On a button you make yourself, call `setProperty("sciforgeIcon", name)` so
  `shell.theme_changed` (`shell.py:128`) redraws it when the look changes.

**Install.** CMake picks up `icons/ui/*.svg` by glob, so there is nothing to list.

---

## 6. Tests

### 6.1 GUI scenarios (`SciForgeTests/gui/harness.py`)

`h.run(name, steps, check_errors_each_step=True, start_ms=2500)` (`:607`):

- Steps run one by one, `STEP_MS` = 700 ms apart; a step can set `step.wait_ms = ...`.
- After every step, any Report error, traceback or SciForge warning is a FAIL.
- `prepare()` resets the selection, display, preferences, keys and pins.
- The harness never starts a step while a document is recomputing.

Actions:

- `click(App.Vector)` returns the hit;
- `click_edge(point)` clicks an edge;
- `double_click(point)`;
- `drag(qpointA, qpointB)` and `drag_points(a, b)`;
- `press(key or "x", modifiers)`;
- `ribbon(label)` clicks a big button;
- `task_button("OK")`;
- `fit()`;
- `idle_step()` (returns a step that waits while a recompute runs).

Checks and queries:

- `check(name, ok, detail)` and `shot(label)`;
- `popups()` and `close_popups()`;
- `in_sketch()`, `body()`, `solid_volume()`;
- `draw_rectangle(sketch, x0, y0, x1, y1)` and `to_sketch(sketch, point)`.

Helpers to reuse:

- `surface_steps.py`: `tab(id)`, `menu(group, label)`, `settle()`, `type_field(key, text)`,
  `choose`, `drag_arrow(key, mm)`, `ok`/`cancel`/`esc`, `undo`/`redo`, `timeline_titles()`,
  `double_click_timeline(title)`, `browser_labels()`, `browser_icon_of(body)`, `step_body`,
  `area`, `volume`.
- `insert_steps.ribbon_tab(id)` (`:189`) and `sketch_input.menu_item(group_title, label)`
  (`:43`, clicks with the mouse through submenus).
- `versions_input.accept_save()`.
- Save and reopen: see `scenarios/surface_reopen.py:143-175` (saveAs, Ctrl+S, `vi.accept_save()`,
  `App.closeDocument`, `App.openDocument`).

**Every file in `scenarios/` runs as a scenario.** Put helpers in
`SciForgeTests/gui/<area>_steps.py`.

A minimal scenario, taken from `scenarios/timeline_roll_view.py`:

```python
import FreeCAD as App
import FreeCADGui as Gui
from SciForgeTests.gui import harness as h

V = App.Vector
s = {}

def setup():
    from sciforge import commands, extrude, sketch_ui
    Gui.activateWorkbench("SciForgeWorkbench")
    App.newDocument("Roll")
    body = commands.ensure_body()
    planes = sketch_ui.origin_planes(body)
    base = sketch_ui.create_sketch(body, (planes["XY_Plane"], ""))
    h.draw_rectangle(base, 0, 0, 40, 30)
    s["first"] = extrude.make(body, base, {"distance": 10.0})
    App.ActiveDocument.recompute()
    h.fit()

def click_top():
    hit = h.click(V(30, 25, 10))
    h.check("a click on the part hits the extrude", hit and hit[0] == s["first"].Name, hit)

h.run("timeline_roll_view", [setup, click_top])
```

Run it with:

```
LC_COLLATE=C tools/sciforge/run_tests.sh --freecad /home/user/SciForge-Parametric-Design/.sciforge-cache/freecad --out <own dir> --scenario a,b
```

### 6.2 Golden models

The format is in `SciForgeTests/golden/README.md`:

```json
{"id": "<file name>", "title": "...", "tags": ["sheetmetal"],
 "steps": [{"op": "sf_primitive", "id": "b1", "kind": "box", "plane": "XY", "x": -30, "y": -30,
            "length": 60, "width": 60, "height": 10, "operation": "new_body"},
           {"op": "sf_gear", "id": "g1", "plane": {"face": {"normal": [0, 0, 1]}}, "x": 30, "y": 30,
            "module": 1.5, "teeth": 16, "thickness": -4, "operation": "cut"}],
 "expect": {"volume": 34246.27, "bbox": [-30, -30, 0, 30, 30, 10], "solids": 1, "abs_tol": 0.0001,
            "source": "analytic|fusion|baseline-freecad-1.1.4", "note": "how the numbers were derived"}}
```

An op (pattern from `sciforge/ai/ops/gear_ops.py`):

```python
from .core import Builder, BuildError
from .primitive_ops import _plane, _settle
def op_sf_gear(self, step):
    from sciforge import gear, primitives
    try:
        feature = gear.make(_plane(self, step), options, name=step["id"])   # the dialog's own Qt-free code
    except primitives.PrimitiveError as exc:
        raise BuildError("sf_gear %r: %s" % (step["id"], exc))
    return _settle(self, step, feature, "sf_gear")   # objects[id], ops[id], body follows, recompute+check
Builder.op_sf_gear = op_sf_gear
```

Builder API (`ai/ops/core.py:54-130`):

- attributes `self.body`, `self.objects[id]`, `self.ops[id]`;
- `self._tip()`, `self._origin("XY_Plane")`, `self._recompute(step, obj)`;
- `selectors.select(shape, selector, "faces" | "edges")`.

Registration:

- Your `<area>_ops.py` must be imported at the end of `core.py` (the scaffold already does this,
  `:747-751`). `test_ai_ops_layout.py:55` fails when an `*_ops.py` is not imported.
- `:61` fails when an `op_*` in `sciforge/ai/ops/` has "expect" in its name: such checks belong in
  `SciForgeTests/golden/checks.py` (`Builder.op_x_expect = ...`, `checks.py:342-352`).

Schema:

- `golden/<area>_schema.py` sets
  `schema.STEP_KEYS["op"] = ({required}, {optional, "comment"})` and wraps `schema.validate`, as
  `gear_schema.py` does. It is imported at the end of `schema.py` (scaffold).
- **The unit test `test_golden_schema.py:31` validates every `models/*.json` without FreeCAD.**
  An unknown op or key, an id that differs from the file name, or a missing
  `expect.source` / `note` fails it.

Measuring and running:

- The model is measured with `runner.measure(builder.shape())`, which is the **current
  `self.body.Shape`**. `expect.valid` defaults to requiring a valid solid. For several bodies use
  `expect_bodies` or `measure_bodies`.
- Run: `tools/sciforge/run_tests.sh --freecad <FC> --out <dir> --only golden`
  (filter with `SCIFORGE_GOLDEN_FILTER=sheetmetal`).

### 6.3 Unit tests and installation

**Unit tests.**

- Files: `SciForgeTests/unit/test_<area>_*.py`.
- Runner: `python3 -m unittest discover -s SciForgeTests/unit` from `src/Mod/SciForge`, without
  FreeCAD (`run_tests.sh --only unit`).
- Header pattern: `ROOT = dirname x3; sys.path.insert(0, ROOT); from sciforge import sheetmetal_core`.
- Import only modules free of FreeCAD and Qt. `sheetmetal_core` is fine; `sheetmetal.py` is not,
  because it imports `bodies`, which imports FreeCAD.

**The fake-FreeCAD test** (`test_smoke_fake_freecad.py:195`).

- It runs InitGui and every `*_ui.py` import against a fake FreeCAD and Qt.
- Only `PrintError` fails it. `warn()` uses `PrintWarning`, so import failures pass there.

**Installation.**

- `CMakeLists.txt` takes everything by glob: `sciforge/**/*.py`, `icons/*.svg`,
  `icons/ui/*.svg`, `SciForgeTests/*.{py,json,md,txt}`.
- **No new file needs listing.** `tools/sciforge/check_install.sh` verifies this.

### 6.4 Tests that enumerate everything

| test | what it enumerates |
|---|---|
| `test_ribbon_config` | icons, commands (AST of `COMMANDS`), shortcuts |
| `test_ai_ops_layout` | every `*_ops.py` registered; checks kept out of the ops |
| `test_golden_schema` | every model file valid; at least 30 models |
| `test_timeline_core:67` | every `KINDS` entry has a title and an icon |
| `test_surface_core:80` | surface icons exist |
| `test_ai_tools_core:84` | op names, read from the source |
| `smoke_gui` | the start-up state |
| `ribbon_sweep` | every command of the swept tabs |

---

## 7. Reusable pieces: what a new feature calls

### Dialogs, fields and handles

**`taskui.Panel(doc, transaction)`** (`taskui.py:1262`, init `:1273`):

- `__init__` opens one undo step.
- Fill `self.layout` (a QFormLayout), then call `finish_layout()` (`:1300`).
- Methods:
  - `feature()` (`:1401`): an invalid result keeps the dialog open on OK;
  - `schedule()` (`:1325`): recompute about 60 ms later;
  - `accept()` / `reject()` / `finish()` (`:1421`, `:1434`, `:1442`);
  - `cleanup()`: call `super()`;
  - `typing_field()` (`:1312`).
- Keys: `preview.EscapeCancels(panel)` (`preview.py:86`), `EnterFinishes(panel)` (`:250`),
  `UndoCancels(panel)` (`:302`).

**`taskui.DistanceField(value=0.0, unit="mm", on_change=None)`** (`:122`):

- `.widget`, `value()`, `set_value(v)`, `bind(obj, prop)`, `parse(text)`, `take(value)`.
- Formulas typed in it: `preview.FormulaInput(panel, key, field)` (`preview.py:132`); the panel
  implements `formula_typed`, `formula_cleared` and `formula_failed`.

**`taskui.ArrowDragger(origin, direction, distance=0.0, size=8.0, on_drag=None, on_release=None, value_box=None)`**
(`:1029`, init `:1047`):

- `.distance`, `set_distance(d)`, `remove()`.
- Size it for the screen with `taskui.handle_size_at(view, point, pixels=None, lo=None, hi=None)`
  (`:273`).

**`taskui.ValueBoxes(panel, default=None)`** (`:753`):

- `.attach(handle, key, text_fn, commit_fn, **where)` (`:782`), `.discard()`.
- A new handle class derives from `taskui.BoxCarrier` (`:661`), implements `box_geometry()`,
  calls `follow_box()` from its poll and `drop_box()` from `remove()`.

**`handles3d`:**

- `LinearHandle(origin, direction, value, size, on_drag=None, on_release=None, view=None, step=0.0)`
  (`:364`);
- `PathHandle(edge, parameter, size, on_drag=None, on_release=None, view=None)` (`:485`);
- `PointDots(view, dots, on_pick, size=1.0)` (`:561`);
- `Overlay(view=None)` (`:673`);
- `angle_handle(...)` (`:323`).

**`hole_common.SelectionField(panel, name, empty)`** (`:50`): Fusion's blue selection box.

### Picking

**`pickpanel.PickPanel(doc, transaction)`** (`:167`), used for face picks on a body:

- Set `self.body` / `self.base` / `self.target`, then call `start_picking()`.
- Implement `allow(obj, short)`, `picks_changed(added, dropped) -> bool`, `shown()` and
  `_preview()`.
- It gives:
  - a see-through base while picking;
  - click-to-toggle picks;
  - Esc, Enter and Ctrl+Z;
  - Delete held off;
  - `follow` of later steps (`remember_later` / `follow_later`, `:512`, `:522`).

**`bodypick.BodyPickPanel(doc, transaction)`** (`:46`): a click picks a whole body.
Use `self.picked` and implement `bodies_changed()`.

**`profile_pick`:**

- `ProfilePicker(view, sketches, on_pick, occluder=None, clicks_through=False, on_curve=None)`
  (`:165`): shades a sketch's closed areas and picks the one clicked;
- `candidate_sketches(body, extra=())` (`:558`);
- `picks()` (`:633`): the selection as `(obj, short)` pairs;
- `ray_plane(view, pos, base, normal)` (`:54`), `resolve(sel_obj, name)` (`:616`),
  `global_face(obj, short)` (`:644`).

**`curve_pick`:**

- `safe(prefix)` (`:33`);
- `RegionPicker(view, sketches, on_pick, occluder=None, skip=None)` (`:99`);
- `prepare_regions(body, extra=())` (`:125`);
- `CurveOverlay(view)` (`:189`);
- `PathHandle(samples, value, size, on_drag=None, on_release=None, color=...)` (`:255`);
- `RatioField(box)` (`:498`).

**`sketch_ui`:**

- `sketch_target(selection=None)` (`:657`);
- `create_sketch(body, (plane_or_feature, "" or "FaceN"))` (`:680`);
- `origin_planes(body)` (`:29`);
- `start(then=None, title="Create Sketch")` (`:998`).

### Feature modules (all Qt-free, all used by their dialogs)

**Rule Fillet:** `fillet_sets.make(body, base, spec, refs, refs2=(), features=(), features2=(), name=None)`
(`fillet_sets.py:1155`). Also `update(obj, base, spec, refs, ...)` (`:1166`) and `read(obj)`
(`:1172`). Build `spec` as `ai/ops/fillet2_ops.py:97-115` does:

```python
spec = fillet_core.default_spec("fillet")
spec.update(mode="rule", rule="all", radius=r, rounds=True, fillets=True)   # rule: "all" | "between"
spec["sets"] = [fillet_core.new_set("fillet", "rule")]
spec["sets"][0]["count"] = len(faces)
fillet_sets.compute(base.Shape, spec, faces, faces2, features, features2)   # raises blend.BlendError
```

**Plain Fillet / Chamfer:** `blend.make(body, base, refs, kind, options, name=None)` (`blend.py:469`).

**Shell:**

- `shelling.make(body, base, names, options, name="Shell", before=None, formulas=None)` (`:628`).
- Options: `{"inside", "outside", "direction": "inside" | "outside" | "both", "shell_type": "sharp" | "rounded", "tangent"}`
  (`default_options` `:55`).
- `update(feature, base, names, options, formulas)` (`:730`); errors raise `ShellError`.

**Draft:**

- `drafting.make(body, base, plane_ref, names, options, name="Draft", formula="", formula2="", before=None)`
  (`:332`).
- `plane_ref` is `(origin plane, "")` or `(base, "FaceN")`.
- Check first with `drafting.check(shape, plane_ref, names, options)` (`:149`).
- Options from `default_options()` (`:45`): angle, flip, tangent, draft_type fixed/parting,
  sides, angle2, parting.

**Rib / Web:**

- `rib.build(refs, options, name=None, feature=None, hide=True)` (`:633`); `refs` are
  `[(sketch, "EdgeN")]`.
- Options from `rib.DEFAULTS` (`:34`): kind rib/web, thickness, thickness_side, depth_type
  to_next/depth, depth, flip, extend.
- `update(feature, refs=None, options=None)` (`:716`).

**Hole (boss holes):**

- `hole.make_single(body, base, face_name, point, options=None, name="Hole", refs=None)` (`:741`).
- `hole.make_from_sketch(body, sketch, subs, options=None, name="Hole")` (`:798`).
- `hole.apply(hole, options)` (`:1394`).
- Options from `DEFAULTS` (`:64`): hole_type simple/counterbore/countersink, diameter, depth,
  extent, cbore_*, csink_*.

**Extrude** (cut through, thin walls):

- `extrude.make(body, profile, options, name="Extrude")` (`:2197`) and
  `build(profiles, options, name, feature=None, hide=True)` (`:1923`).
- Options from `DEFAULTS` (`:96`):
  - `operation`: join / cut / intersect / new_body / new_component;
  - `extent`: distance / to_object / all;
  - `direction`, `taper`;
  - `thin` with `wall_thickness`.

**Emboss:**

- `emboss.make(body, base, profiles, face_names, options, name="Emboss", formulas=None)` (`:901`).
- The geometry alone: `emboss.build(base_shape, profiles, targets, options, body=None)` (`:625`).

**Physical Material:** `material.assign(body, key)` (`:331`); see section 8.

**New bodies and components:**

- `components.new_body_in(doc, container, label=None)` (`:219`);
- `components.body_for_new(src_body, component=False)` (`:230`);
- `components.activate_body(body)` (`:510`);
- `components.active_component(doc)` (`:440`).

**`bodies` helpers:** `alive`, `is_body`, `body_of`, `list_bodies`, `has_solid`, `global_shape`,
`to_local`, `insert_after_tip`, `remove_step`, `mark`, `kind`, `save_meta`, `load_meta`,
`hide_from_timeline`, `pass_through`.

---

## 8. Where the sheet metal and plastic RULES can live

### 8.1 Stores that already exist

| store | where | saved with the file | undo | used for |
|---|---|---|---|---|
| `App::VarSet "Parameters"` | `parameters.container(doc, create)` (`parameters.py:68`) | yes | yes | user parameters. Any property expression can say `Parameters.x` (a dialog accepts a bare `x`: `parameters_core.to_freecad`) |
| hidden doc-level `App::FeaturePython` with typed properties | `direct.DesignSettings` (`direct.py:49-91`, object `"SciForgeDesign"`, `settings(doc, create)`; calls `hide_from_timeline`) | yes | **yes** | Capture Design History |
| `Document.Meta` (dict of strings) | `timeline_ops.py:915-928`, `viewcube_ui.py:162-184`, `browser_ui.py:1303-1324` | yes | **no** (`direct.py:52`) | marker note, named views, Home view |
| hidden property on a body | `bodies.add_prop(body, type, name, group, doc, hidden=True)` (`bodies.py:278`); e.g. `material.USER_PROP "SciForgeUserMaterial"` (`material.py:355-372`) | yes | yes | per-body facts |
| user preferences | `App.ParamGet("User parameter:BaseApp/Preferences/Mod/SciForge/...")` (`ribbon_pins.py`, `material.DEFAULT_PREF`) | per machine | no | a user's own rule **library** |

### 8.2 The sheet metal contract

The scaffold `sheetmetal.py` combines two of these: a store object `SheetMetalRules`
(`RulesJson`, `ActiveRule`) and `SciForgeSheetMetalRule` on the body and on the component.
Facts to know:

- It has no Proxy. That is fine:
  - it is no timeline step: an `App::FeaturePython` is not a `Part::Feature` and has no
    `SciForgeType`;
  - the browser drops unknown types.
- `make_sheet_metal_body` adds the property visible (mode 0). `bodies.add_prop` would hide it.
- `save_rule` only `touch()`es features. **The caller must run `doc.recompute()`.**
- Derive / Insert of a component does not bring the store along. `rule_for_body` then falls back
  to the library or the default rule **with a `warn`**, which fails a scenario.

### 8.3 Physical Material per body

- It is FreeCAD's own `body.ShapeMaterial`.
- `material.assign(body, key)` (`material.py:331`) sets it on the body and on every step, and
  applies the material's look.
- Reading:
  - `material.key_of(body)` (`:275`);
  - `material.effective(body)`, the default being Steel;
  - `bodies.density(body)` / `bodies.mass(body)`.
- `material.LIBRARY` keys (`:17-36`):
  - plastics: `abs`, `pla`, `pet`, `nylon`, `polycarbonate`, `acetal`, `acrylic`,
    `polypropylene`, `ptfe`, `peek`;
  - metals: `steel`, `stainless`, `aluminium`, `aluminium_6061`, `copper`, `titanium`, `iron`.
- A plastic rule should keep its material key and call `material.assign` when it is applied
  (Fusion ties plastic rules to materials).

### 8.4 The browser's Document Settings node

- `browser_core.build(doc_label, objects, units, active_body, views, active_component)`
  (`:343-380`). The settings node has one child, `"Units: <u>"` (kind `units`).
- `MENUS["settings"]` and `MENUS["units"]` are `["Change Active Units"]` (`:480-481`).
- A click on a `units` row runs `browser_ui._clicked` (`:1036-1048`), which runs
  `open_units_panel`.
- `build()` is called from `browser_ui.tree` (`:702-716`).
- To add rule rows (e.g. "Sheet Metal Rule: <name>"):
  - give `build()` one optional keyword argument (e.g. `settings_extra=()`) and pass it from
    `tree()`;
  - add a node kind with its `MENUS` entry and its `_clicked` branch.
  One builder (sm-forming) should make this change; plastic-1 merges it, rather than two
  branches editing the same lines.
