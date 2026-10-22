# Recipe: a pair of meshing spur gears

Tags: gear, gear-pair, spur, involute, module, move_copy, interference, components, joint

Two metric spur gears with module 2: a 20-tooth pinion and a 40-tooth wheel (ratio 2:1),
10 mm wide, meshing at the right centre distance. Every call was run by SciForge's tests;
`expect` is what the answer must contain.

The maths a CAD designer uses: pitch diameter d = m z (40 mm and 80 mm), outside diameter
d + 2 m (44 mm and 84 mm), centre distance a = m (z1 + z2) / 2 = 60 mm.

## 1. The two gears

[gear](sciforge://docs/reference/gear.md) makes an involute gear as a new body (by default) centred at
x / y on its plane. The wheel goes 60 mm along X.

```json sciforge-calls
[
  {"tool": "new_design", "args": {"name": "Gears"}},
  {"tool": "gear", "args": {"module": 2, "teeth": 20, "thickness": 10, "hole": 8},
   "expect": {"contains": ["44 x 44 x 10 mm"]}},
  {"tool": "gear", "args": {"module": 2, "teeth": 40, "thickness": 10, "hole": 12, "x": 60},
   "expect": {"contains": ["84 x 84 x 10 mm"]}}
]
```

## 2. Turn the wheel half a tooth so the teeth mesh

Both gears have a tooth pointing along +X. Seen from the pinion, the wheel's tooth at 180
degrees points straight at the pinion's tooth: they collide.
[interference](sciforge://docs/reference/interference.md) shows it. Turning the wheel by half its tooth
pitch (360 / 40 / 2 = 4.5 degrees) about its own centre puts a gap opposite each tooth. The
wheel's body is named by its step id (the id the gear answer gave).

```json sciforge-calls
[
  {"tool": "interference", "args": {}, "expect": {"contains": ["overlap"]}},
  {"tool": "get_timeline", "args": {}, "expect": {"json": {"steps.#": 2}}},
  {"tool": "move_copy", "args": {"bodies": ["Gear2"], "move_type": "rotate", "angle": 4.5,
    "axis": "Z", "pivot": [60, 0, 0]},
   "expect": {"contains": ["Done"]}},
  {"tool": "interference", "args": {}, "expect": {"contains": ["No bodies overlap"]}}
]
```

## 3. Components (optional)

For an assembly, put each body in a component of its own
([components_from_bodies](sciforge://docs/reference/components_from_bodies.md): the answer gives the
component's id and its label) and ground the pinion, so nothing moves it when joints solve.

```json sciforge-calls
[
  {"tool": "components_from_bodies", "args": {"bodies": ["Gear1"], "label": "Pinion"}},
  {"tool": "components_from_bodies", "args": {"bodies": ["Gear2"], "label": "Wheel"}},
  {"tool": "ground", "args": {"component": "Pinion"}},
  {"tool": "inspect_design", "args": {},
   "expect": {"json": {"bodies.#": 2, "summary.failed_steps": []}}},
  {"tool": "check_design", "args": {}, "expect": {"json": {"ok": true}}}
]
```

## Variations

- Another ratio: `edit_step` on a gear (`{"step": "Gear2", "set": {"teeth": 30}}`), then
  move it to the new centre distance m (z1 + z2) / 2 and check `interference` again.
- An internal gear (a ring with teeth inside): `type: "internal"` with `rim`.
- A rack: `type: "rack"` with `rack_length` and `rack_height`.
- Motion: a `joint` needs a face, edge or vertex on each of two components (for example a
  shaft component through the wheel's bore, `type: "revolute"`, snapping the two circle
  centres), then `drive_joint` turns it; the handbook's
  [components and joints](sciforge://docs/handbook.md#components-and-joints) section explains.
