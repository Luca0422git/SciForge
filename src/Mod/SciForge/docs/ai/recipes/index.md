# Recipes: common parts step by step

Each recipe builds a real part with SciForge's tools, one call at a time, and checks it with
numbers. Every call in every recipe is run by SciForge's tests in real FreeCAD (the
`expect` part of a call is what its answer must contain, not a tool argument), so the
arguments, the ids the answers report and the numbers are known to be right. Copy the
calls, change the sizes, and check with the same tools.

| Recipe | What it shows |
|---|---|
| [L bracket with mounting holes](sciforge://docs/recipes/bracket.md) | a side profile extruded, inside fillet, outside chamfer, holes into two faces, material and mass |
| [Enclosure with a lid](sciforge://docs/recipes/enclosure-with-lid.md) | rounded box, shell, a second body, fillet sets, a plug with clearance, interference, STL per body |
| [Stepped shaft with a keyway](sciforge://docs/recipes/shaft-with-keyway.md) | revolve, a slot cut from a tangent plane with flip, chamfers with any_of, shoulder fillet |
| [A pair of meshing spur gears](sciforge://docs/recipes/gear-pair.md) | gear maths, two gears, interference, rotating a body about a pivot, components, ground |
| [Flange with a bolt circle](sciforge://docs/recipes/flange-bolt-pattern.md) | revolved turned part, one hole then a circular pattern, fillet and chamfer on circles |
| [Threaded fastener (hex bolt M8 x 30)](sciforge://docs/recipes/threaded-fastener.md) | polygon, extrude down with flip, modeled thread, diff_design to prove a change |
| [Cantilever snap-fit hook](sciforge://docs/recipes/snap-fit.md) | a side profile extruded symmetric, root fillet picked by coordinates |
| [Sheet-like U bracket](sciforge://docs/recipes/sheet-like-part.md) | open profile, thin extrude, bends as fillet sets, hole through sheet |
| [Revolved knob with grip grooves](sciforge://docs/recipes/revolved-knob.md) | revolve, a cut then a circular pattern of it, bore from below, hole vs cut direction |
| [Lofted handle](sciforge://docs/recipes/lofted-handle.md) | loft through three profiles, ellipses, checking the size, diff of a cut |
| [Curved panel from a surface patch](sciforge://docs/recipes/surface-patch.md) | 3D boundary curves, surface patch, thicken, surface bodies |
| [Parametric mounting plate](sciforge://docs/recipes/parametric-plate.md) | user parameters, sketch dimensions and model parameters with expressions, a pattern that follows, change and verify |

Looking for something else? `examples_search` finds recipes and the golden models (about
450 small designs with measured results) by words, tool or op, and
[the golden model index](sciforge://docs/examples/golden-models.md) lists them by feature.
