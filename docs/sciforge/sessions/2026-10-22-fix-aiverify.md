# Session log: fixes to the AI checking tools, MCP resources and render (branch `fix/aiverify`)

To be copied into MEMORY.md by whoever merges (this branch does not edit MEMORY.md).
Started from `integration` (3e515b5). An adversarial review of item 3 (`wf/ai-verify`) found
ten problems (F1-F10); each was reproduced on this branch first, then fixed with a test that
fails before the fix. No FreeCAD core file changed (nothing for `core-patches.md`).

## In plain words (for Luca)

When an AI app is connected to SciForge it can ask for a picture of the design, with some
faces "highlighted in orange". In the open SciForge window that picture showed no orange at
all (it only said so), a selected body came out tinted blue, a picture "from the side" could
come out turned on its side, and odd picture sizes left the part small. Those four are fixed:
the window now really paints the asked-for faces and edges orange, ignores your selection
while it takes the picture (and puts it back), keeps Z up, and fills the picture.

The AI's "refs" (a description of one exact edge or face that it can pass to Fillet) now
remember which body they came from: if another body is active, Fillet refuses with a clear
sentence instead of rounding the matching edge of the wrong body.

The checking tools were very slow on a plate with 400 chamfered holes (a picture took 35 s
and 1.3 GB of memory, a list of 500 edges with refs 53 s). Now: about 4 s and 0.4 GB for the
picture, under 1 s for the refs, and the hidden cost added to every AI change went from
0.5 s to 0.03 s.

Smaller things: "what changed since snapshot S1" no longer compares two different designs
that happen to have the same name, MCP clients get proper errors for unknown steps, a design
called "Bracket {v2}" no longer breaks the design resource, and "diff since a rolled-back
step" says the step is rolled back instead of reporting made-up numbers.

## What was fixed

| Id | Problem | Fix | Test |
|---|---|---|---|
| F1 | Window render: highlight not drawn (saveImage ignores selected faces); the person's selection tinted every plain picture | `bridge.GuiHost.push_highlight` takes the selection (and preselection) off during the picture and adds a Coin node (`_highlight_node`) with the marked faces (orange, polygon offset forward, tessellated on the displayed shape with a deflection no finer than the view's, so OCC hands back the window's own triangles) and edges (4 px; an earlier step's edges drawn on top); `pop_highlight` removes it, restores the selection and says whether it was drawn (else the answer does not claim orange) | GUI scenario `ai_render_window` (orange pixel counts, selected body vs nothing selected); `ai_agent_e2e` now counts orange pixels too |
| F2 | Window render `direction` kept the camera's roll | `_turn` sets the camera node's orientation from `render_core.camera` (Z up, same basis as the software renderer), for named views too (no animation) | `ai_render_window` path 3 (from +X the boss stands up on the right after rolling the camera) |
| F3 | query_geometry refs applied to the active body, silently changing the wrong body | A selector may carry `"body"` (refs from query_geometry and the window selection do); `selectors.select` refuses it when the shape belongs to another body (`_check_body`: OCC partner shapes), naming the active body and `activate`; query_geometry warns when the queried body is not active. Catalogue: `body` is a selector key (`kit.SELECTOR_KEYS`, help, docs) | headless `VERIFY_SESSION` (wrong body refused, plate unchanged; after activate the ref rounds exactly the box's edge) |
| F4 | Software render: an earlier step's highlight drawn in body coordinates (100 mm off for a moved component) | The earlier step's shape goes through `bodies.global_shape`; its faces are drawn "in front" (`render_core` mesh `in_front`, a depth bias) so they are not lost against the coincident face of the current solid | `VERIFY_SESSION` renders (orange pixels where the moved box is) |
| F5 | Slow and memory-hungry on a big part | `face_meshes`: one MeshPart mesh per body with a segment per face (checked against face bounding boxes; face by face as fallback) instead of 806 `tessellate` calls (25 s -> 2 s); one mesh per colour; `render_core._fill` rasterises every triangle row by row in bounded batches (no per-triangle loop), float32 buffers, no supersampling above 2048 x 2048; `geometry_facts`: candidate lists cached per filter set and refs checked with `_Index.select` (the same rules as `selectors.select` on facts measured once); `record()` keeps the bodies' solids and measures them only when diffed; validity cached per solid | Measured on the reviewer's 400-hole plate (806 faces): render 800x600 36.8 s / 1237 MB -> 3.9 s / 419 MB, 2048x2048 48.6 s -> 11 s; query_geometry 500 faces 53.7 s -> 0.9 s, 500 edges 53.2 s -> 0.7 s; record() 0.44 s -> 0.03 s; inspect_design again 4.2 s -> about 1.3 s. `VERIFY_SESSION` checks every ref with the real `selectors.select`; unit tests of render_core unchanged and passing (pixel-identical on a fan test) |
| F6 | Snapshots / last_change outlived a design closed in the window | Records carry the document's `Uid`; `_snapshots(doc)` drops those of a closed namesake; inspect_design takes `snapshot: false`, used by the resource sciforge://design so reading it does not push out the AI's snapshot ids | `VERIFY_SESSION` (closed with App.closeDocument, same name reused: "no snapshot", "No AI change") and a unit test that the resource asks with snapshot false |
| F7 | MCP resource errors returned as contents; a brace in the label broke the JSON | `_from_tool` raises -32002 (with data uri and reason) for a template id that names nothing, -32603 for other failures; `_json_part` takes the JSON at the start or after a newline | `test_ai_docs_contract`: unknown step, braces in the sentence, SciForge not running |
| F8 | Tests did not prove pictures or ref round trips | Pixel checks (both renderers through `agent_e2e.script`, plain-Python PNG decoder `png_rgb`), a chamfer driven by a ref, a two-body design with a moved component (inspect, check, diff, render), a rolled-back step | the tests above |
| F9 | diff_design since a rolled-back (or failed) step used a stale solid | `_since_step` refuses with a sentence (roll forward first, or use a snapshot) | `VERIFY_SESSION` |
| F10 | Window render framed for the window's shape | `_frame` fits the shown bodies' / sketches' box corners to the requested picture (orthographic camera: lateral shift and height with Coin's aspect rule and render_core's margin; fitAll first for near / far) | `ai_render_window` path 4 (1600 x 200 and 200 x 900 filled to 0.87 of the short side, was 0.48 / 0.72) |

## Notes

- The reviewer's GUI repro also flagged "camera of sketch edit restored" (render while a
  sketch is open); it was not one of the findings and is unchanged here.
- inspect_design's first call after opening a file still recomputes sketches to count their
  closed areas (`extrude.regions`, 2-4 s on a 400-circle sketch); later calls do not.
- Repro scripts used: the reviewer's (`scratchpad/review-aiverify`), run against this branch.
