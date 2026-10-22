# Recipe: enclosure with a lid

Tags: enclosure, box, lid, shell, fillet, fillet_sets, new_body, interference, 3d-printing

An 80 x 60 x 30 mm electronics box with rounded corners and 2 mm walls, open at the top, and
a 3 mm lid with a plug that fits inside the box with 0.2 mm of clearance. The box and the
lid are two bodies, so they can be exported (and printed) separately. Every call was run by
SciForge's tests; `expect` is what the answer must contain, not a tool argument.

## 1. The box: extrude, round the corners, shell

Round the vertical corners before shelling: the shell then follows the rounded outline and
the inside corners get radius 5 - 2 = 3 by themselves (Fusion behaves the same). The corner
fillet removes 4 x r^2 (1 - pi / 4) = 21.46 mm2 of the 80 x 60 outline: 4778.54 mm2 x 30 =
143356.2 mm3. The shell removes the 76 x 56 inside with r 3 corners, 28 mm deep: the walls
are 24404.5 mm3.

```json sciforge-calls
[
  {"tool": "new_design", "args": {"name": "Enclosure"}},
  {"tool": "create_sketch", "args": {"plane": "XY", "geometry": [
    {"rect": [0, 0, 80, 60], "name": "outline"}]}},
  {"tool": "extrude", "args": {"profile": "Sketch1", "distance": 30},
   "expect": {"contains": ["Its id is 'Extrude1'", "144000 mm3"]}},
  {"tool": "fillet", "args": {"edges": {"type": "line", "parallel": [0, 0, 1], "count": 4},
    "radius": 5},
   "expect": {"contains": ["143356 mm3"]}},
  {"tool": "shell", "args": {"faces": {"normal": [0, 0, 1], "at": {"axis": "z",
    "value": "max"}, "count": 1}, "thickness": 2},
   "expect": {"contains": ["Its id is 'Shell1'", "24404.5 mm3", "80 x 60 x 30 mm"]}}
]
```

## 2. The lid, a body of its own

[new_body](sciforge://docs/reference/new_body.md) makes an empty body and makes it the active one: the
next sketches and extrudes go into it (Fusion: a new body, or a new component for parts that
move). The lid sits on the box (z = 30 to 33). The plug hangs 3 mm down from the lid's
underside: a sketch on XY at offset 30 extruded with `flip: true` goes down (-Z). Its outline
is the box's inside (76 x 56) minus 0.2 mm on every side.

```json sciforge-calls
[
  {"tool": "new_body", "args": {"label": "Lid"}, "expect": {"contains": ["Lid"]}},
  {"tool": "create_sketch", "args": {"plane": "XY", "offset": 30, "geometry": [
    {"rect": [0, 0, 80, 60]}]}},
  {"tool": "extrude", "args": {"profile": "Sketch2", "distance": 3},
   "expect": {"contains": ["Lid: 14400 mm3"]}},
  {"tool": "create_sketch", "args": {"plane": "XY", "offset": 30, "geometry": [
    {"rect": [2.2, 2.2, 77.8, 57.8]}]}},
  {"tool": "extrude", "args": {"profile": "Sketch3", "distance": 3, "flip": true},
   "expect": {"contains": ["Lid: 27010.1 mm3", "80 x 60 x 6 mm"]}}
]
```

## 3. Round the lid's corners and the plug's corners in one step

Both sets of vertical edges are straight lines along Z; `at` with a number keeps the edges
whose centre is at that height: the lid's edges are centred at z = 31.5, the plug's at
z = 28.5. [fillet_sets](sciforge://docs/reference/fillet_sets.md) gives each set its own radius in one
timeline step: 5 mm outside (like the box) and 2.8 mm on the plug (the box's inside radius 3
minus the clearance), so the plug clears the box's rounded inside corners.

```json sciforge-calls
[
  {"tool": "query_geometry", "args": {"element": "edges", "select": {"type": "line",
    "parallel": [0, 0, 1], "at": {"axis": "z", "value": 28.5}}},
   "expect": {"json": {"count": 4}}},
  {"tool": "fillet_sets", "args": {"sets": [
    {"edges": {"type": "line", "parallel": [0, 0, 1], "at": {"axis": "z", "value": 31.5},
     "count": 4}, "radius": 5},
    {"edges": {"type": "line", "parallel": [0, 0, 1], "at": {"axis": "z", "value": 28.5},
     "count": 4}, "radius": 2.8}]},
   "expect": {"contains": ["Lid: 26925.5 mm3"]}}
]
```

## 4. Check the fit

[check_design](sciforge://docs/reference/check_design.md) also looks for bodies that overlap
(Fusion's Interference): with the clearance there is none. Two bodies, both valid.

```json sciforge-calls
[
  {"tool": "check_design", "args": {},
   "expect": {"json": {"ok": true, "interference": [], "bodies.#": 2}}},
  {"tool": "interference", "args": {}, "expect": {"contains": ["No bodies overlap"]}},
  {"tool": "inspect_design", "args": {},
   "expect": {"json": {"bodies.0.volume_mm3": [24404.51, 0.05],
     "bodies.1.volume_mm3": [26925.51, 0.05], "bodies.1.label": "Lid"}}}
]
```

## 5. Export each part for printing

`export` with `bodies` writes only those bodies; a body is named by any of its steps (the
box by Extrude1, the lid by Extrude2).

```json sciforge-calls
[
  {"tool": "export", "args": {"format": "stl", "path": "{tmp}/box.stl", "bodies": ["Extrude1"]},
   "expect": {"contains": ["box.stl"]}},
  {"tool": "export", "args": {"format": "stl", "path": "{tmp}/lid.stl", "bodies": ["Extrude2"]},
   "expect": {"contains": ["lid.stl"]}}
]
```

## Variations

- Screw bosses: sketch circles on the box's floor (XY, offset 2), extrude them up into the
  box body (`activate` the box first: `{"target": "Extrude1"}`), then `hole` from a sketch on
  their tops.
- Ventilation slots: draw `slot` items on a side face (XZ plane: sketch x is X, sketch y is
  Z) and cut them with `extrude` (`operation: "cut"`, `through_all: true`).
- A lid that moves in an assembly: use `new_component` instead of `new_body`, then
  `joint` (see [the gear pair](sciforge://docs/recipes/gear-pair.md)).
