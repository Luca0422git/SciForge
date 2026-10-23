# Golden models by feature

<!-- Generated from the tool catalogue (src/Mod/SciForge/sciforge/ai/catalog) by tools/sciforge/make_ai_docs.py: do not edit by hand. The unit test test_ai_docs_contract.py fails when this file and the catalogue differ. -->

SciForge's golden models are 469 small designs, each a list of design steps with the measurements the finished part must have (volume, area, faces, bounding box), worked out by hand where possible (`expect.source: analytic`, the formula in `expect.note`). The tests rebuild every one in real FreeCAD. They prove what each feature does and show which options exist. Their steps are SciForge's design-step language (what the AI tools build), not tool calls: the table at the end gives the tools that build each op. Read one with docs_read `golden/<id>` (or the resource sciforge://examples/golden/<id>); examples_search finds them by words, op, tool or tag. Models marked (known gap) document something SciForge does not do yet.

## By feature

Each model is listed under its first tag; its other tags follow it.

### extrude (55)

- `box_basic`: Rectangle 40x20 extruded 10 [basic]
- `box_symmetric`: Center rectangle 30x30, symmetric extrude 20 [symmetric]
- `box_two_sides`: Extrude two sides 5 and 3 [two-sides]
- `cylinder_extrude`: Circle r10 extruded 25 [cylinder]
- `extrude_face_cut`: Box 40x30x10, top face extruded 4 into the part (flip) as a cut [face-profile, cut]
- `extrude_face_join`: Box 40x30x10, side face extruded 3 (Extrude on a picked face) [face-profile]
- `extrude_intersect`: Intersect: keep the 20x20x6 part of the box inside the extrusion [intersect]
- `extrude_multi_cut`: Cut from Body1's top across the gap into Body2: both bodies are cut, one timeline step [bodies, multi_body]
- `extrude_multi_cut_all`: Cut All from the XY plane up through both bodies [bodies, multi_body]
- `extrude_multi_cut_all_far`: Cut All reaches a second body 300 mm higher [bodies, multi_body]
- `extrude_multi_cut_edit`: Cut through both bodies, then its distance edited from 5 to 8: both follow [bodies, multi_body]
- `extrude_multi_cut_excluded`: Cut across both bodies with Body2 taken out of the bodies to cut [bodies, multi_body]
- `extrude_multi_cut_other_body`: Body1's sketch over Body2 only: the cut goes into Body2, Body1 stays whole [bodies, multi_body]
- `extrude_multi_cut_profile_body_excluded`: Cut across both bodies with the sketch's own body left out: only Body2 is cut [bodies, multi_body]
- `extrude_multi_cut_reopen`: Multi-body cut saved and opened again: both bodies keep their cut [bodies, multi_body]
- `extrude_multi_cut_split`: A slot cut through both bodies splits Body2 into two pieces [bodies, multi_body]
- `extrude_multi_cut_timeline`: Multi-body cut rolled back and forward, suppressed, unsuppressed and deleted [bodies, multi_body]
- `extrude_multi_intersect`: Intersect through both bodies: each keeps what lies inside the extrusion [bodies, multi_body]
- `extrude_multi_join_delete`: Join merging two bodies, suppressed, unsuppressed and deleted: Body2 comes back [bodies, multi_body]
- `extrude_multi_join_edge_touch`: Join whose side only meets the next body along an edge: that body is not merged [bodies, multi_body]
- `extrude_multi_join_fills_hole`: A disc extruded into the round hole of a plate joins the plate (it touches the wall) [bodies, multi_body, join]
- `extrude_multi_join_merge`: Join from inside both bodies: the bodies merge into one [bodies, multi_body]
- `extrude_multi_join_nothing`: Join away from every body makes a new body (Fusion) [bodies, multi_body]
- `extrude_multi_join_other_body`: Body1's sketch on Body2's top joined upwards: Body2 grows, Body1 stays [bodies, multi_body]
- `extrude_multi_move`: A multi-body cut dragged after a later step of the other body, and back [bodies, multi_body, timeline]
- `extrude_new_body`: New Body: a 10x10x5 block on the box is a separate body [new-body]
- `extrude_region_disc`: Rectangle with a circle inside: extrude only the disc [regions]
- `extrude_region_lens`: Two overlapping circles: extrude only the lens where they cross [regions]
- `extrude_region_ring`: Rectangle with a circle inside: extrude only the ring [regions]
- `extrude_regions_both`: Ring and disc picked together give the full block [regions, multi-profile]
- `extrude_start_object_follows`: Extrude with Start: Object follows the face when an earlier step moves it [start, follow, edit]
- `extrude_start_offset`: Extrude that starts 5 mm off the sketch plane [start-offset]
- `extrude_symmetric_half`: Symmetric extrude, distance measured per side (Half Length) [symmetric]
- `extrude_taper_cut`: Tapered pocket: 20x20 cut 5 deep, narrowing 10 degrees [cut, taper]
- `extrude_taper_cut_to_plane`: Tapered hole from the top of a 20 mm block Cut To Object (the XY plane), narrowing 5 degrees [cut, to-object, taper]
- `extrude_taper_join_all`: Tapered column from a sketch 30 up, Join with Extent All downwards, widening 10 degrees [all, taper]
- `extrude_taper_to_body`: Tapered column To Object a whole other body (its bottom 30 up), widening 5 degrees, joined to the plate [to-object, taper, bodies]
- `extrude_taper_to_face`: Tapered column from a sketch 30 up, down To Object (the box top), widening 10 degrees [to-object, taper]
- `extrude_thin_arc_center`: Thin Extrude of an open quarter arc, wall centred on the curve (2 mm), 5 high [thin, open-profile]
- `extrude_thin_open_l`: Thin Extrude of an open L of two sketch lines: a 2 mm wall on the curve's left (Side 1), 10 high [thin, open-profile]
- `extrude_thin_taper_center`: Thin Extrude of a rectangle, wall centred (2 mm), widening 5 degrees over 10: the wall keeps its thickness [thin, taper]
- `extrude_thin_to_cylinder_face`: Thin Extrude (2 mm, Side 1) of a rectangle up To Object the round face of a cylinder above it, joined [thin, to-object]
- `extrude_thin_tube`: Thin Extrude of a rectangle on a plate: a 2 mm wall inside the outline (Side 1), 10 high, joined [thin]
- `extrude_through_body`: Extrude Cut To Object a body, Through Body: through the upper plate only [to_object, extend, bodies]
- `extrude_to_adjacent_faces`: Extrude To Object, To Adjacent Faces: ends on the face and the slope next to it [to_object, extend]
- `extrude_to_cylinder_face`: Extrude a rectangle as a new body up To Object the round face of a cylinder in another body above it (a click on a curved face while extruding) [to-object]
- `extrude_to_face`: Extrude from a sketch 30 up down to the top face of the box [to-object]
- `extrude_to_object_offset`: Extrude Cut To Object with an Offset: stops 3 mm short of the bottom face [to_object, offset, cut]
- `extrude_to_plane`: Extrude from a sketch 30 up to the XY origin plane (through the box) [to-object]
- `extrude_to_selected_face_extended`: Extrude To Object, To Selected Face: the face's plane, extended past the slope [to_object, extend]
- `extrude_two_sides_taper`: Two sides: 5 up straight, 3 down tapered -10 degrees [two-sides, taper]
- `extrude_two_sketches`: Two sketches picked together, joined to the box [multi-profile]
- `hex_prism`: Hexagon (circumradius 10) extruded 10 [polygon]
- `l_bracket_profile`: L profile on XZ extruded 20 [bracket, polyline]
- `slot_extrude`: Slot 30 long, 10 wide, extruded 5 [slot]

### primitive (37)

- `sf_box_basic`: Box on XY: corner at the origin, 40 x 20 x 10 (first solid: new body) [box]
- `sf_box_param_driven`: Box whose Length is the parameter w and Height w / 3; then w changes from 30 to 60 [box, parameters]
- `sf_box_pocket_edit_join`: The pocket box edited in the timeline: height +3, Join (SubtractiveBox becomes AdditiveBox) [box, edit]
- `sf_box_pocket_top`: Box 40x20x10, then a Box on its top face 10x10 going 5 down: the dialog picks Cut [box, cut, auto-operation]
- `sf_box_xz_flipped`: Box on XZ, going left (sx -1) and to the other side of the plane (height -3) [box, plane-frame]
- `sf_coil_basic`: Coil on XY: diameter 20, 4 revolutions, height 20, circular section 2 inside the diameter [coil]
- `sf_coil_cut_block`: Block 40x40x35 (two boxes, z -5..30), a coil d20, 4 turns, height 20 inside it: the dialog picks Cut [coil, cut, auto-operation]
- `sf_coil_edit_turns`: Coil edited in the timeline: 2 revolutions instead of 4 [coil, edit]
- `sf_coil_param_driven`: Coil whose Diameter is coil_d, Height rise and Revolutions turns (20, 20, 4, then 30, 40, 3), section 2 [coil, parameters]
- `sf_coil_square_spiral`: Coil, Spiral: diameter 20, 3 revolutions, pitch 5, square section 2 on center [coil, spiral]
- `sf_coil_taper_height_pitch_param`: Narrowing coil (Height and Pitch, angle -10) whose height and pitch are parameters; the parameters change [coil, taper, parameters]
- `sf_coil_taper_narrow`: Coil d20 on XY (centre 3, -2), 4 turns, height 20, angle -10: it narrows as it rises [coil, taper, new-body]
- `sf_coil_taper_param_driven`: Narrowing coil (Revolution and Height) whose angle, height and revolutions are parameters; the parameters change [coil, taper, parameters]
- `sf_coil_taper_raised_narrow_down`: Block 60x60x30, a coil d20 on the middle of its top face going down 20, angle -10 (it narrows as it goes), New Body (measured alone) [coil, taper, new-body, face]
- `sf_coil_taper_raised_widen`: Block 60x60x30, a coil d20 on the middle of its top face, 4 turns, height 20, angle 10 (widening), New Body (measured alone) [coil, taper, new-body, face]
- `sf_coil_taper_rev_pitch_param`: Narrowing coil (Revolution and Pitch, angle -10) whose pitch and revolutions are parameters; the parameters change [coil, taper, parameters]
- `sf_cylinder_boss`: Box 40x20x10 and a Cylinder d10 h5 on its top face (the dialog picks Join) [cylinder, join, auto-operation]
- `sf_cylinder_new_component`: Cylinder d10 h5 on a box's top face with operation New Component: a new component holding a new body [cylinder, new-component, components]
- `sf_cylinder_through_hole`: Box 40x20x10 and a Cylinder d6 going 10 down from the top face: a through hole (Cut picked) [cylinder, cut, auto-operation]
- `sf_cylinder_xz`: Cylinder d10 h10 on XZ (it grows along -Y, the XZ plane's normal) [cylinder, plane-frame]
- `sf_pipe_corner_hollow_cut`: Box 40x30x10, a hollow Pipe d2 wall 0.5 round the corner of two top edges, Cut: a mitred groove [pipe, cut, hollow, model-edges, corner]
- `sf_pipe_corner_intersect`: Box 40x30x10, a Pipe d2 round the corner of two top edges, Intersect: SciForge's own sweep keeps both legs [pipe, intersect, model-edges, corner]
- `sf_pipe_corner_mitre_join`: Box 40x30x10, a Pipe d2 round the corner of two top edges (front, then right), Join: the corner is mitred like Fusion's [pipe, join, model-edges, corner]
- `sf_pipe_edge_auto_join`: Box 40x20x10 and a Pipe d2 along its top front edge: mostly outside, the dialog picks Join [pipe, join, auto-operation, model-edges]
- `sf_pipe_edge_cut`: Box 40x20x10 and a Pipe d2 along its top front edge, Cut: a quarter-round groove [pipe, cut, model-edges]
- `sf_pipe_hollow_half`: Pipe d2 hollow (wall 0.25) half way along the same path [pipe, hollow]
- `sf_pipe_param_driven`: Hollow Pipe along the sketch path: Section Size dia, wall dia / 8; then dia changes from 2 to 4 [pipe, hollow, parameters]
- `sf_pipe_ring_hollow`: A hollow Pipe d2 wall 0.5 round a closed sketch circle r15 (two half arcs, Chain Selection): a hollow ring [pipe, hollow, closed-path]
- `sf_pipe_ring_hollow_cut`: Block 40x40x10 on XY, a hollow Pipe d2 wall 0.5 round a sketch circle r15 on its bottom face, Cut: a hollow groove [pipe, hollow, closed-path, cut]
- `sf_pipe_sketch_path`: Pipe d2 along a sketch path line + tangent arc r10 + line (Chain Selection from the first line) [pipe]
- `sf_pipe_square`: Pipe with a square section (circle round it d2) along the same path [pipe, square]
- `sf_pipe_triangle_edit`: Pipe edited in the timeline: Triangular section, whole path [pipe, edit]
- `sf_sphere_cut_corner`: Box 40x20x10 and a Sphere d8 centred on the top face's corner (40, 20), Cut: an eighth taken away [sphere, cut]
- `sf_sphere_intersect`: Box 40x20x10 and a Sphere d16 centred on the bottom (XY) at (20, 10), Intersect: the upper half [sphere, intersect]
- `sf_torus_inside_cut`: Box 40x40x20 around the origin, a Torus on XY (inner 30, torus 6, Inside) cut into it [torus, cut]
- `sf_torus_new_body`: Box, then a Torus away from it on XY (inner 20, torus 4, Outside): the dialog makes a new body [torus, new-body, auto-operation]
- `sf_torus_param_driven`: Torus whose inner diameter is the parameter ring_d (30, then 40), torus diameter 6, Inside [torus, parameters]

### fillet (31)

- `blend_edit_keeps_later_chamfer`: Fillet r2 then chamfer 1 mm; edit the fillet to round one more edge that trims the chamfered edge [chamfer, blend, edit, reference]
- `blend_fillet_boss_feature`: Fillet dialog: click the boss extrude in the timeline, radius 1 (top and foot rounded) [blend, feature-pick, concave]
- `blend_fillet_edit_radius`: Fillet two top edges meeting at a corner r2, then edit the fillet to r3 [blend, edit]
- `blend_fillet_presspull_radius`: Fillet dialog r1 on a vertical edge, then Press Pull on its round face: r5 [blend, press-pull]
- `blend_fillet_slot_chain`: Slot 30 long, 10 wide, 10 high: Fillet one straight top edge r2, the tangent chain rounds the whole top outline [blend, tangent-chain]
- `blend_fillet_top_face`: Fillet dialog: click the top face of a 40x30x10 box, radius 2 (its 4 edges round) [blend, face-pick]
- `blend_insert_chamfer_before_fillet`: Fillet the front edge r2, roll the marker back, insert a chamfer on the right edge before it [chamfer, blend, timeline, rollback, reference]
- `bracket_inner_fillet`: L bracket with the inside corner filleted r3 [concave, bracket]
- `fillet2_chord_90_120`: Fillet dialog: Chord Length 3 on a 90 degree edge and a 120 degree edge (one set) [blend, fillet-2]
- `fillet2_face_and_its_edge_in_two_sets`: Two fillet sets: set 1 the top face r 1, set 2 one of its edges r 2: the edge picked on its own takes set 2's radius [blend, fillet-2]
- `fillet2_full_round_rib`: Full Round Fillet: the end of a 4 mm rib becomes a half round (r 2) [blend, fillet-2, full_round]
- `fillet2_presspull_set_radius`: Press Pull on the round of set 2 of a two-set fillet edits set 2's radius (3 -> 2) [blend, fillet-2, presspull]
- `fillet2_rule_all_edges`: Rule Fillet: All Edges of the extrude, r 1 (every edge of the box) [blend, fillet-2, rule]
- `fillet2_rule_between_follows_edit`: Rule Fillet: Between the plate and the boss (fillets at its foot, r 1), then the boss made wider: the rule follows [blend, fillet-2, rule]
- `fillet2_sets_tangent_chain_each`: Fillet dialog: Tangent Chain is a setting of each set: set 1 (top front edge of a slot, chain off) rounds that edge only, set 2 (bottom front edge, chain on) rounds the whole bottom loop [blend, fillet-2]
- `fillet2_tangent_chain_off`: Fillet dialog: Tangent Chain off, r 1 on one straight top edge of a slot (the arcs stay sharp) [blend, fillet-2]
- `fillet2_two_sets`: Fillet dialog: two selection sets in one step (r 1 on the front top edge, r 3 on the back top edge), saved and reopened [blend, fillet-2]
- `fillet2_variable_points`: Fillet dialog: Variable radius on the front top edge, start 1, point 0.5 at 3, end 1.5 [blend, fillet-2]
- `fillet_all_edges`: Box 40x20x10, all 12 edges filleted r2 [vertex-blend]
- `fillet_one_vertical_edge`: Box 40x20x10, one vertical edge fillet r5
- `fillet_top_edges`: Box 40x20x10, the 4 top edges filleted r2 [corner]
- `live_blend_fillet_boss_feature`: Live picture on the exact result: Fillet dialog: click the boss extrude in the timeline, radius 1 (top and foot rounded) [blend, feature-pick, concave, live-blend]
- `live_blend_fillet_slot_chain`: Live picture on the exact result: Slot 30 long, 10 wide, 10 high: Fillet one straight top edge r2, the tangent chain rounds the whole top outline [blend, tangent-chain, live-blend]
- `live_bracket_inner_fillet`: Live picture on the exact result: L bracket with the inside corner filleted r3 [concave, bracket, live-blend]
- `live_fillet2_chord_90_120`: Live picture on the exact result: Fillet dialog: Chord Length 3 on a 90 degree edge and a 120 degree edge (one set) [blend, fillet-2, live-blend]
- `live_fillet2_rule_all_edges`: Live picture on the exact result: Rule Fillet: All Edges of the extrude, r 1 (every edge of the box) [blend, fillet-2, rule, live-blend]
- `live_fillet2_sets_tangent_chain_each`: Live picture on the exact result: Fillet dialog: Tangent Chain is a setting of each set: set 1 (top front edge of a slot, chain off) rounds that edge only, set 2 (bottom front edge, chain on) rounds the whole bottom loop [blend, fillet-2, live-blend]
- `live_fillet2_tangent_chain_off`: Live picture on the exact result: Fillet dialog: Tangent Chain off, r 1 on one straight top edge of a slot (the arcs stay sharp) [blend, fillet-2, live-blend]
- `live_fillet2_two_sets`: Live picture on the exact result: Fillet dialog: two selection sets in one step (r 1 on the front top edge, r 3 on the back top edge), saved and reopened [blend, fillet-2, live-blend]
- `live_fillet2_variable_points`: Live picture on the exact result: Fillet dialog: Variable radius on the front top edge, start 1, point 0.5 at 3, end 1.5 [blend, fillet-2, live-blend]
- `live_fillet_top_edges`: Live picture on the exact result: Box 40x20x10, the 4 top edges filleted r2 [corner, live-blend]

### bodies (28)

- `bodies_combine_cut`: Combine Cut: the overlap of the second body is cut from the first [combine]
- `bodies_combine_cut_cylinder`: A cylinder body cut through a box body with Combine: a through hole [combine, hole]
- `bodies_combine_edit_operation`: Combine Join edited to Cut from the timeline [combine, edit]
- `bodies_combine_follows_tool`: Combine Cut follows an edit of the tool body's extrude (blind hole becomes a through hole) [combine, edit, keep-tools]
- `bodies_combine_intersect`: Combine Intersect keeps the volume both bodies share [combine]
- `bodies_combine_join`: Two overlapping boxes in two bodies joined with Combine [combine]
- `bodies_combine_new_body`: Combine Join with New Body: the result is a third body, the two stay as they were [combine, new-body]
- `bodies_combine_new_body_target_deleted`: Combine Join with New Body, then the (used-up) target body is deleted: the new body keeps its shape [combine, new-body, delete]
- `bodies_combine_new_component`: Combine (Join) with New Component: the result is the body of a new component [combine, components]
- `bodies_combine_tool_deleted`: A body used as a Combine tool is deleted: the Combine keeps it as it was (same result) [combine, delete]
- `bodies_delete_face_fillet`: Delete on a fillet face: the sharp edge comes back [delete, delete-face, fillet]
- `bodies_delete_face_hole`: Delete on the wall of a hole: the hole closes (Delete Face) [delete, delete-face]
- `bodies_move_copy`: Move/Copy with Create Copy: a copy 50 to the right as a new body [move, copy, new-body]
- `bodies_move_edit`: A Move edited from the timeline [move, edit]
- `bodies_move_free`: Free Move: Z Angle 90 about the middle of the body and X Distance 10 [move, free]
- `bodies_move_point_to_point`: Move/Copy Point to Point: corner (0, 0, 0) to (5, 5, 5) [move, point-to-point]
- `bodies_move_point_to_position`: Move/Copy Point to Position: the corner (0, 0, 0) goes to X 10, Y 20, Z 30 [move, point-to-position]
- `bodies_move_rotate_pivot`: Move/Copy Rotate 90 degrees about Z through a pivot at the body's corner (not the origin) [move, rotate, pivot]
- `bodies_move_rotate_z`: Move/Copy Rotate 90 degrees about the Z axis [move, rotate]
- `bodies_move_then_cut`: A body moved, then cut: the cut sketch stays where it was drawn (Fusion) [move, extrude]
- `bodies_move_translate`: Move/Copy Translate 10, 5, 20 [move]
- `bodies_move_two_bodies`: Move/Copy of two bodies at once: both go up 10 (one Move per body, edited together) [move, multi-body]
- `bodies_split_by_body`: Split Body along a cylinder body: a box with a hole and the plug [split, body-tool]
- `bodies_split_edit_tool`: Split Body edited from the timeline: the XZ plane instead of YZ [split, edit]
- `bodies_split_face_extended`: Split Body with a face of another body, Extend Splitting Tool on [split, extend]
- `bodies_split_sketch_line`: Split Body with a sketch line across the box's diagonal: two wedges [split, sketch-tool]
- `bodies_split_two_planes`: Split Body with two splitting tools at once (YZ and XZ planes): four bodies, one step [split]
- `bodies_split_yz`: A box centred on the origin split by the YZ origin plane into two bodies [split]

### pattern (24)

- `flange_polar_holes`: Disc r40 x 10 with 6 holes r4 on a circular pattern [circular]
- `modify2_pattern_adjust_to_slope`: Wedge, a hole cut from below up to the sloped top, repeated 3 times with Compute Option Adjust [compute-option, adjust, fusion-dialog]
- `modify2_pattern_identical_to_slope`: The same wedge and hole, repeated 3 times with Compute Option Identical [compute-option, identical, fusion-dialog]
- `modify2_pattern_multibody_cut`: Two boxes, one cut through both, repeated 3 times: the copies cut both bodies [multi-body, extrude, fusion-dialog]
- `modify2_pattern_path_auto_start`: The same boss and L path, the pattern starting by itself (nearest the boss) [path, start-point, fusion-dialog]
- `modify2_pattern_path_start_point`: Box 40x40x10, a boss repeated along an L path that starts a quarter of the way along it [path, start-point, fusion-dialog]
- `pattern_bodies_in_moved_component`: A body in a component turned 90 degrees and moved 100 along X, patterned along its own X: the copy lands beside it [rectangular, bodies, new-body, components, fusion-dialog]
- `pattern_bodies_move_original_after`: A body patterned along X (Spacing 50, Quantity 3), then the original moved 20 up: the copies stay [rectangular, bodies, new-body, move, fusion-dialog]
- `pattern_bodies_rect_new`: A 20x10x5 body patterned along X (Spacing 30, Quantity 3): two new bodies [rectangular, bodies, new-body, fusion-dialog]
- `pattern_circ_faces_bolt_circle`: Disc r40x10: the wall of a hole r4 patterned around Z, Full, 6 (Pattern Type Faces) [circular, faces, fusion-dialog]
- `pattern_circ_suppressed_bodies`: A 4x4x4 body patterned around Z (Full, 4) into new bodies, one copy suppressed [circular, bodies, suppression, fusion-dialog]
- `pattern_circ_symmetric_holes`: Disc r40x10, a hole r4 at (30, 0) patterned Symmetric, 2 per side over 60 degrees [circular, symmetric, fusion-dialog]
- `pattern_edit_keeps_later_fillet`: A hole pattern, a fillet on the patterned part's edge, then one copy suppressed [rectangular, edit, suppression, fillet, fusion-dialog]
- `pattern_edit_quantity_fusion`: Hole pattern edited in the dialog from 3 over 20 mm to 5 over 40 mm [rectangular, edit, fusion-dialog]
- `pattern_path_bosses`: Box 40x30x10, a boss r2x4 repeated 4 times over 30 mm of a sketch line [path, fusion-dialog]
- `pattern_path_circle_turned`: A 4x2 boss repeated 4 times round a circle path, Orientation Path Direction [path, orientation, fusion-dialog]
- `pattern_quantity_parameter`: A row of holes whose Quantity is a parameter n; n changed from 3 to 5 [rectangular, parameter, fusion-dialog]
- `pattern_rect_features_any_order`: A boss with a hole in it, picked hole first, repeated along X: each copy keeps its hole [rectangular, features, order, fusion-dialog]
- `pattern_rect_hole_grid_fusion`: Plate 60x40x5, a 3x2 Rectangular Pattern of a hole (Fusion dialog, Extent) [rectangular, fusion-dialog]
- `pattern_rect_suppressed`: Plate 60x40x5, a 3x2 hole pattern with the middle copy of the back row suppressed [rectangular, suppression, fusion-dialog]
- `pattern_rect_symmetric_bosses`: Plate 60x40x5 centred, a boss r3x4 patterned symmetric 3x2 per side (15 bosses) [rectangular, symmetric, fusion-dialog]
- `pattern_sciforge_extrude`: A tapered column (SciForge's own extrude: taper to a face) repeated along X [rectangular, features, fusion-dialog]
- `pattern_symmetric_parameter`: A tab patterned Symmetric with Spacing = gap; gap changed from 20 to 30 [rectangular, symmetric, parameter, fusion-dialog]
- `plate_hole_grid`: Plate 60x40x5 with a 3x2 rectangular pattern of holes [rectangular]

### revolve (23)

- `groove_ring`: Cylinder r10 h20 with a 2 mm deep ring groove [cut]
- `revolve_cylinder`: Rectangle on XZ revolved 360 about Z
- `revolve_quarter`: Offset rectangle revolved 90 degrees [angle]
- `revolve_washer`: Offset rectangle revolved 360 (washer)
- `sf_revolve_cone`: Revolve dialog: right triangle about Z: a cone [fusion-revolve]
- `sf_revolve_construction_follows`: Revolve dialog: a new body follows when the construction line it turns about moves [fusion-revolve, new-body, construction-line, reference-stability]
- `sf_revolve_cut_other_body`: Revolve Cut acting on the other body only (its own body left out) [bodies, cut]
- `sf_revolve_cut_two_bodies`: Revolve Cut through two bodies in one step (Objects To Cut: both) [bodies, cut]
- `sf_revolve_cylinder`: Revolve dialog: rectangle against Z, Full: a cylinder [fusion-revolve]
- `sf_revolve_edit_operation`: Revolve dialog: edit a groove to Join (nothing added) and back to Cut 180 degrees [fusion-revolve, edit, cut]
- `sf_revolve_face_edge`: Revolve dialog: a side face turned 90 degrees out about its top edge [fusion-revolve, face-profile, edge-axis]
- `sf_revolve_face_profile_follows`: Revolve dialog: a face profile is found again after an earlier revolve changes it [fusion-revolve, face-profile, edge-axis, reference-stability]
- `sf_revolve_groove_auto_cut`: Revolve dialog: profile inside a shaft turns into a Cut by itself (groove) [fusion-revolve, cut, auto-operation]
- `sf_revolve_intersect`: Revolve dialog: Intersect keeps the box inside a revolved cylinder [fusion-revolve, intersect]
- `sf_revolve_new_body_construction`: Revolve dialog: ring about a construction line, New Body next to a box [fusion-revolve, new-body, construction-line]
- `sf_revolve_ring_two_sides`: Revolve dialog: ring section, Two Sides 90 and 30 degrees [fusion-revolve, two-sides]
- `sf_revolve_sketch_line_axis`: Revolve dialog: square about its own right line [fusion-revolve, sketch-line]
- `sf_revolve_symmetric`: Revolve dialog: ring section, Symmetric 45 degrees each way [fusion-revolve, symmetric]
- `sf_revolve_to_cut`: Revolve dialog: a Cut of Type To stops at an origin plane [fusion-revolve, revolve-to, cut]
- `sf_revolve_to_plane`: Revolve dialog: Type To, as far as an origin plane through the axis [fusion-revolve, revolve-to]
- `sf_revolve_to_then_angle`: Revolve dialog: a Type To revolve edited back to Angle keeps working [fusion-revolve, revolve-to]
- `sf_revolve_to_vertex_follows`: Revolve dialog: Type To a corner of the part follows when the part changes [fusion-revolve, revolve-to, reference-stability]
- `sf_revolve_torus`: Revolve dialog: circle r5 at x = 20 about Z, Full: a torus [fusion-revolve]

### loft (22)

- `sf_loft_centerline_ends`: Loft along a straight centerline with Direction at the first profile (a prism) [fusion-loft, centerline, end-conditions]
- `sf_loft_centerline_torus`: Loft: two circles r5 square to a quarter-arc centerline (a quarter torus) [fusion-loft, centerline]
- `sf_loft_closed_direction`: Closed loft of four squares round the Z axis with Direction at the first one [fusion-loft, closed, end-conditions]
- `sf_loft_cone_point`: Loft: a circle r5 to a sketch point 20 above (a cone) [fusion-loft]
- `sf_loft_cut_cone`: Loft: circle r10 on the top of a block down to a point 15 below: Cut by itself [fusion-loft, cut]
- `sf_loft_cut_two_bodies`: Loft Cut through two bodies in one step [bodies, cut]
- `sf_loft_edit_intersect`: Loft edited from the timeline: Join -> Intersect inside a block [fusion-loft, edit]
- `sf_loft_ends_direction`: Loft square 20 to square 10, 20 up, Direction on both profiles (weight 1, angle 0) [fusion-loft, end-conditions]
- `sf_loft_ends_direction_weight`: Loft square 20 to square 10 with Direction, the last profile's Takeoff Weight 2 (edited) [fusion-loft, end-conditions, edit]
- `sf_loft_ends_dome`: Loft square 20 to a point 10 up: Direction at the square, Point Tangent at the point (a dome) [fusion-loft, end-conditions, point]
- `sf_loft_ends_face_curvature`: Loft from a block's top face (Curvature G2) to a square 20 above [fusion-loft, end-conditions, face]
- `sf_loft_ends_face_tangent`: Loft from a block's top face (Tangent G1) to a square 20 above: it carries the walls on [fusion-loft, end-conditions, face]
- `sf_loft_frustum`: Loft: a 20 x 20 square to a 10 x 10 square 30 higher (a pyramid frustum) [fusion-loft]
- `sf_loft_merge_slot`: Loft Tangent Edges Merge: a slot lofted to the same slot 30 up, Keep then Merge [fusion-loft, merge]
- `sf_loft_merge_slot_volume`: Loft Tangent Edges Merge: the merged slot's volume (OpenCASCADE measures it wrong) [fusion-loft, merge, kernel] (known gap)
- `sf_loft_one_rail`: Loft: two 10 x 10 squares 40 apart with one bulging rail (the loft leans out to it) [fusion-loft, rails]
- `sf_loft_rail_body_edges`: Loft with two rails that are edges of a body (a wedge's slanted edges): a frustum [fusion-loft, rails]
- `sf_loft_rails_ends`: Loft with two straight rails and Direction at both profiles (a straight prism) [fusion-loft, rails, end-conditions]
- `sf_loft_rails_turning`: Loft with two quarter-arc rails between a square on XY and a square on YZ (a turn) [fusion-loft, rails]
- `sf_loft_square_circle`: Loft: a 20 x 20 square up into a circle r10, 30 mm higher [fusion-loft]
- `sf_loft_three_circles`: Loft: three equal circles r5 at z 0, 20, 40 (a cylinder) [fusion-loft]
- `sf_loft_two_rails`: Loft: two 10 x 10 squares 40 apart between two bulging rails (a barrel) [fusion-loft, rails]

### press-pull (22)

- `modify2_presspull_modify_extrude`: Press Pull, Offset Type Modify Existing Feature: the box's top pulled 5 mm makes the extrude 15 long [offset-type, fusion-dialog]
- `modify2_presspull_modify_offset`: Press Pull, Offset Type Modify Existing Feature on a face an earlier Press Pull moved: that step's distance changes, no new step [offset-type, fusion-dialog]
- `modify2_presspull_modify_pocket`: Press Pull Modify Existing Feature on a pocket's floor: the pocket gets 1 mm shallower [offset-type, fusion-dialog]
- `modify2_presspull_new_offset`: Press Pull, Offset Type New Offset: the box's top pulled 5 mm by a Press Pull step [offset-type, fusion-dialog]
- `pp_boss_grow`: Press Pull: boss wall +2 (boss r5 -> r7)
- `pp_edge_fillet`: Press Pull on an edge = fillet r5
- `pp_edit_distance`: Edit a Press Pull's distance afterwards [edit]
- `pp_fillet_face_radius`: Press Pull on a fillet face edits its radius (1 -> 5)
- `pp_hole_grow`: Press Pull: hole wall -1 (hole r3 -> r4)
- `pp_hole_shrink`: Press Pull: hole wall +1 (hole r3 -> r2)
- `pp_multi_face_corner`: Press Pull: top and side together +2
- `pp_multi_face_push_corner`: Press Pull: top and side together -2 [multi-face]
- `pp_opposite_faces`: Press Pull: top and bottom +2 together [multi-face]
- `pp_pocket_deeper`: Press Pull: pocket floor -4 (pocket 8 -> 12 deep)
- `pp_side_pull`: Press Pull: side face +10
- `pp_slanted_neighbours`: Press Pull: top of a trapezoid, sloped sides extend
- `pp_slanted_push`: Press Pull: top of a trapezoid pushed -5, sloped sides trimmed
- `pp_slanted_side_pull`: Press Pull: a sloped side of a trapezoid +2 (top and bottom extend) [multi-face]
- `pp_then_edit_extrude`: Press Pull survives editing the extrude before it [reference-stability]
- `pp_three_faces_corner`: Press Pull: top, right and back faces +2 meet in one corner [multi-face]
- `pp_top_pull`: Press Pull: top face of a box +5
- `pp_top_push`: Press Pull: top face of a box -4

### hole (20)

- `hole_blind`: Blind hole d6 depth 6 in a 40x40x10 plate
- `hole_clearance_countersunk`: Clearance hole for an M6 countersunk screw (ISO 10642), close fit [clearance, fastener, countersink]
- `hole_clearance_m6`: Clearance hole for M6, normal fit, through [clearance]
- `hole_clearance_socket_cbore`: Clearance hole for an M6 socket head cap screw: counterbore from the head [clearance, fastener, counterbore]
- `hole_counterbore`: Through hole d6.6 with counterbore d11 x 6.5 [counterbore]
- `hole_countersink`: Through hole d6 with 90 degree countersink d12 [countersink]
- `hole_curved_follows`: A hole on a cylinder stays on the cylinder when its radius changes [curved, follow, edit]
- `hole_points_flipped`: Two through holes d3 from circle centres of a sketch under the plate (turned round) [sketch]
- `hole_references_follow_edge`: Through hole d10 placed 3 from the right edge and 15 from the front; plate made wider [single, references, edit]
- `hole_second_survives_first`: Two single holes on the top face; the first suppressed, then deleted: the second stays [single, suppress, delete]
- `hole_single_angled`: Single Hole d5 x 6 with a 118 degree drill point [single, drill_point]
- `hole_single_counterbore`: Single Hole d5 x 6 with a counterbore d10 x 3 [single, counterbore]
- `hole_single_countersink`: Single Hole d5 x 6 with a 90 degree countersink d10 [single, countersink]
- `hole_single_edit_diameter`: Single Hole d5 x 6 edited to d4 [single, edit]
- `hole_single_flat`: Single Hole d5 x 6 (flat) clicked on the top face of a 40x30x10 plate [single]
- `hole_taper_bspt_through`: Taper Tapped hole Rc 1/4 (BSPT) through a 10 mm plate [taper, bspt]
- `hole_taper_npt`: Taper Tapped hole 1/8-27 NPT, 12 deep, flat bottom [taper, npt]
- `hole_tapped_m6`: Tapped hole M6x1 through, cosmetic thread [tapped]
- `hole_to_face`: Hole d6 from the top face To the bottom face [single, to]
- `hole_to_face_follows`: Hole d6 from the top face To the bottom face; the plate made thicker afterwards [single, to, edit]

### surface (19)

- `surface2_extrude_all`: Surface Extrude Extent All: through two boxes above and below, Flip, Two Sides [extrude, all]
- `surface2_extrude_from_curved_face`: Surface Extrude From Object: a line extruded 10 up from a cylinder below it [extrude, from-object]
- `surface2_extrude_from_face`: Surface Extrude From Object: a line extruded 15 from a box's top face, then Offset 5 [extrude, from-object]
- `surface2_extrude_to_body`: Surface Extrude To Object: a line extruded up to a cylinder body, and to its face [extrude, to-object]
- `surface2_extrude_to_chain_faces`: Surface Extrude To Object with Chain Faces: up to a box's filleted underside (fillet + bottom) [extrude, to-object]
- `surface2_loft_centerline`: Surface Loft of two circles r 5 along a quarter-circle centerline r 30, then Direction [loft, centerline, end-conditions]
- `surface2_loft_tangent_end`: Surface Loft from a wall's top edge to a line, Tangent (G1) at the edge [loft, end-conditions]
- `surface2_loft_two_rails`: Surface Loft: two 20 long lines 30 apart between two bulging arc rails (flat) [loft, rails]
- `surface2_revolve_to_plane`: Surface Revolve Type To: a line 10 from the Z axis turned to the YZ plane, then to XZ [revolve, to-object]
- `surface2_sweep_rail`: Surface Sweep Path + Guide Rail: a 10 high line along 40, its top on a rising rail [sweep, rail]
- `surface2_sweep_taper`: Surface Sweep Taper Angle 10: a circle r 5 swept 20 up a straight path opens out [sweep, taper]
- `surface_boundary_fill_cone`: Boundary Fill: tube, cone and XY plane close a cell; fill the one inside [boundary_fill, revolve]
- `surface_extrude_line`: SURFACE Extrude of an open sketch line, 10 each way (Symmetric) [extrude]
- `surface_offset_thicken_join`: Offset a box's top face 5, thicken the offset back down onto the box (Join) [offset, thicken]
- `surface_patch_trim_untrim`: Patch a square, Trim a hole with a sketch circle, Untrim the hole (Internal) [patch, trim, untrim]
- `surface_stitch_cylinder`: A tube and two patched ends stitched into a solid cylinder [stitch, patch]
- `surface_sweep_loft_ruled_extend`: Sweep a V along a line, Loft two lines, Ruled from an edge, Extend an edge [sweep, loft, ruled, extend]
- `surface_thicken_corner`: Thicken an L of walls: sharp, rounded, then symmetric rounded [thicken]
- `surface_trim_plane`: A wall trimmed by the XY plane, the lower piece removed [trim]

### draft (18)

- `modify2_draft_fixed_symmetric`: The same box, its sides drafted Symmetric by 4 deg about the XY plane [symmetric, fusion-dialog]
- `modify2_draft_fixed_two_side`: Box 20x20x20 around the XY plane, its 4 sides drafted Two Side: 5 deg up, 3 deg down [two-side, fusion-dialog]
- `modify2_draft_parting_plane_two_side`: Box z -8..12, Parting Line at the XY plane, pull from the top face, Two Side 5 / 2 deg [parting-line, two-side, fusion-dialog]
- `modify2_draft_parting_sketch_one_side`: The same box, Parting Line a sketch line at z = 0 on the XZ plane, One Side 5 deg [parting-line, one-side, fusion-dialog]
- `modify2_draft_two_bodies`: Two boxes (two bodies) drafted in one step: Fixed Plane XY, One Side, 3 deg [multi-body, fusion-dialog]
- `sf_draft_cylinder`: Cylinder r10 h10, Draft of its round face 5 degrees about XY: a cone frustum [sciforge-draft, round]
- `sf_draft_edit_angle`: Box, Draft of the front face 5 degrees, edited to 3 degrees [sciforge-draft, edit]
- `sf_draft_ellipse_wall`: Ellipse 12 x 6 extruded 10, Draft of its free-form wall 5 degrees about XY (FreeCAD's own Draft cannot tilt such a face) [sciforge-draft, free-form]
- `sf_draft_ellipse_wall_edit`: The ellipse wall drafted 3 degrees, then the step edited to 6 degrees [sciforge-draft, free-form, edit]
- `sf_draft_ellipse_wall_flip`: The ellipse wall drafted 5 degrees with the pull direction flipped: wider toward the top [sciforge-draft, free-form]
- `sf_draft_flip`: Box, Draft: fixed plane XY with the pull direction flipped, 4 sides 5 degrees [sciforge-draft]
- `sf_draft_four_sides`: Box, Draft: fixed plane XY, the 4 sides 5 degrees (narrower toward the top) [sciforge-draft]
- `sf_draft_front_face`: Box, Draft: fixed plane XY, the front face 5 degrees [sciforge-draft]
- `sf_draft_spline_pocket`: Box 40 x 30 x 10 with a closed-spline pocket cut through it, the pocket wall drafted 4 degrees about XY (the pocket opens up toward the top) [sciforge-draft, free-form, pocket]
- `sf_draft_spline_side_corners`: Three straight sides and a spline side meeting at sharp corners, extruded 10; all 4 side walls drafted 5 degrees about XY [sciforge-draft, free-form, corners]
- `sf_draft_tangent_chain`: Rounded rectangle with a spline side, extruded 10; one Draft of its 8 side walls (lines, arcs, the spline: one tangent chain) 3 degrees about XY [sciforge-draft, free-form, tangent-chain]
- `sf_draft_then_shell`: Box, Draft the 4 sides 2 degrees about XY, then Shell 1.5 mm with the top taken away [shell, sciforge-draft, sciforge-shell, enclosure]
- `sf_draft_top_face_fixed`: Box, Draft: the top face is the fixed plane (pull up), the 4 sides 5 degrees [sciforge-draft]

### sweep (18)

- `sf_sweep_both_sides`: Sweep: the profile inside the path, Distance One 0.5 and Distance Two 0.25 [fusion-sweep]
- `sf_sweep_distance_parameter`: Sweep Distance typed as a parameter (share); share changes 0.5 -> 0.25 later [fusion-sweep, parameters]
- `sf_sweep_edit_distance`: Sweep edited from the timeline: Distance 1 -> 0.5 [fusion-sweep, edit]
- `sf_sweep_face_taper`: Sweep: the end face of a box along a 10 mm line with a 5 degree taper [fusion-sweep, taper]
- `sf_sweep_groove_cut`: Sweep: circle r3 along a line through a box; Fusion picks Cut by itself (a groove) [fusion-sweep, cut]
- `sf_sweep_guide_surface`: Sweep Path + Guide Surface: a thin 6 x 1 strip along the slanted ellipse edge of a cut cylinder, the cylinder's side as the guide surface: the strip keeps hugging the cylinder [fusion-sweep, guide-surface]
- `sf_sweep_half_distance`: Sweep: Distance 0.5 sweeps half of a 30 mm path [fusion-sweep]
- `sf_sweep_intersect`: Sweep: Intersect keeps only the rod inside a block [fusion-sweep, intersect]
- `sf_sweep_join_two_bodies`: Sweep Join touching two bodies merges them in one step [bodies, join]
- `sf_sweep_mitre_corner`: Sweep: circle r2 along an L-shaped path with a sharp corner (mitred joint) [fusion-sweep]
- `sf_sweep_parallel_arc`: Sweep: Orientation Parallel keeps the circle level along a quarter arc [fusion-sweep]
- `sf_sweep_rail_scale`: Sweep: Path + Guide Rail, Profile Scaling Scale (the square grows to 30 x 30) [fusion-sweep, guide-rail]
- `sf_sweep_rail_stretch`: Sweep: Path + Guide Rail, Profile Scaling Stretch (wider only towards the rail) [fusion-sweep, guide-rail]
- `sf_sweep_taper_cone`: Sweep: circle r5 up a straight 20 mm path with a 10 degree taper (a cone frustum) [fusion-sweep]
- `sf_sweep_taper_parameter`: Sweep Taper Angle and Distance typed as formulas (lean, reach / 2) [fusion-sweep, parameters]
- `sf_sweep_torus_closed`: Sweep: circle r2 round a closed circular path r20 (a torus) [fusion-sweep]
- `sf_sweep_tube_bend`: Sweep: circle r2 along a line, a bend of radius 10 and a line (a bent tube) [fusion-sweep]
- `sf_sweep_twist_square`: Sweep: a 10 x 10 square up a straight 50 mm path with a 45 degree twist [fusion-sweep]

### shell (14)

- `modify2_shell_two_bodies`: Two boxes shelled in one step: the first opened at the top, the second hollow [multi-body, fusion-dialog]
- `sf_shell_both`: Box, Shell Both: 2 mm inside, 1 mm outside (top taken away) [sciforge-shell]
- `sf_shell_both_edit_presspull`: Shell Both 2 in / 1 out, Press Pull on its outside front wall, the shell edited to 2 out: the Press Pull keeps its wall [sciforge-shell, edit, press-pull, reference-stability]
- `sf_shell_both_follows_extrude_edit`: Shell Both on the top face, then the extrude edited 10 -> 20 [sciforge-shell, reference-stability, edit]
- `sf_shell_cup`: A cup: cylinder r 10 x 20, Shell taking the top away, 1 mm walls (the part drawn on screen first) [round]
- `sf_shell_edit_to_both`: Shell inside 2 mm edited to Both with 1 mm outside (FreeCAD's Thickness -> SciForge's) [sciforge-shell, edit]
- `sf_shell_hollow_body`: Box 40x30x10, Shell on the body (nothing taken away): closed hollow, 2 mm [sciforge-shell, hollow]
- `sf_shell_hollow_both`: Box, Shell on the body, Both: 2 mm inside, 1 mm outside [sciforge-shell, hollow]
- `sf_shell_open_box`: Box 40x30x10, Shell: top face taken away, 2 mm inside [sciforge-shell]
- `sf_shell_outside_rounded`: Box, Shell Outside 1 mm (top taken away), Shell Type Rounded [sciforge-shell]
- `sf_shell_outside_sharp`: Box, Shell Outside 1 mm (top taken away), sharp corners [sciforge-shell]
- `sf_shell_swap_presspull_follows`: Shell inside 2 (FreeCAD's Thickness), Press Pull on the front wall, the shell edited to Both 1 out (SciForge's shell): the Press Pull keeps its wall [sciforge-shell, edit, press-pull, reference-stability]
- `shell_filleted_box`: Enclosure: box 60x40x30, vertical edges r5, shell 2 open top [fillet, enclosure]
- `shell_open_box`: Box 60x40x30 shelled 2 mm inward, top removed [enclosure]

### direct (13)

- `direct_align_block_on_table`: Align: a block's top face onto a table's top face (they end up facing each other) [modify, align]
- `direct_align_flip_angle`: Align with Flip and one Angle click: turned over into the table and a quarter turn [modify, align]
- `direct_history_off_on`: Capture Design History off (one frozen step), on again, then a Press Pull step [history, press-pull]
- `direct_remove_body`: Remove: a body taken out of the design by a timeline step [modify, remove]
- `direct_replace_face_edit_down`: Replace Face edited: the target changed to a lower body's top, the box comes down [modify, replace-face, edit]
- `direct_replace_face_up_to_body`: Replace Face: a box's top goes up to the top of another body [modify, replace-face]
- `direct_silhouette_body_sphere`: Silhouette Split, Split Solid Body: a ball split into two halves at its outline [modify, silhouette-split]
- `direct_silhouette_edit_to_faces`: Silhouette Split edited from Split Solid Body back to Split Faces Only [modify, silhouette-split, edit]
- `direct_silhouette_faces_sphere`: Silhouette Split, Split Faces Only: a ball seen from above, split at its equator [modify, silhouette-split]
- `direct_split_face_closest_point`: Split Face, Closest Point: another body's face edges split a box's side [modify, split-face]
- `direct_split_face_extend`: Split Face, Extend Splitting Tool: a face beside the box, taken as its whole plane [modify, split-face]
- `direct_split_face_then_press_pull`: Split Face then Press Pull on one half of the split top [modify, split-face, press-pull]
- `direct_split_face_yz`: Split Face: a box's top split by the YZ origin plane (one more face, same solid) [modify, split-face]

### chamfer (10)

- `blend_chamfer_angle`: Chamfer dialog: Distance and Angle, 3 mm at 30 degrees on the front top edge [blend]
- `blend_chamfer_top_face`: Chamfer dialog: click the top face of a 40x30x10 box, equal distance 2 [blend, face-pick]
- `blend_chamfer_two_flip`: Chamfer dialog: Two Distances 2 and 4 on the front top edge, flipped [blend]
- `chamfer_one_edge`: Box 40x20x10, one top edge chamfer 3
- `chamfer_top_edges`: Box 40x20x10, the 4 top edges chamfered 2 [corner]
- `fillet2_chamfer_sets_angle_flip`: Chamfer dialog: two sets in one step, Equal 1 on the front top edge, Distance and Angle 2 mm at 30 degrees flipped on the back top edge [blend, fillet-2]
- `live_blend_chamfer_angle`: Live picture on the exact result: Chamfer dialog: Distance and Angle, 3 mm at 30 degrees on the front top edge [blend, live-blend]
- `live_blend_chamfer_top_face`: Live picture on the exact result: Chamfer dialog: click the top face of a 40x30x10 box, equal distance 2 [blend, face-pick, live-blend]
- `live_blend_chamfer_two_flip`: Live picture on the exact result: Chamfer dialog: Two Distances 2 and 4 on the front top edge, flipped [blend, live-blend]
- `live_fillet2_chamfer_sets_angle_flip`: Live picture on the exact result: Chamfer dialog: two sets in one step, Equal 1 on the front top edge, Distance and Angle 2 mm at 30 degrees flipped on the back top edge [blend, fillet-2, live-blend]

### timeline (10)

- `tl_delete_before_fillet`: Box, hole, round on a box edge; delete the hole: the round stays on its edge [delete, fillet]
- `tl_delete_hole`: Box, hole, boss; delete the hole from the timeline [delete]
- `tl_insert_before_fillet`: Roll back before a round, add a boss at the marker, roll to the end [roll, fillet]
- `tl_move_fillet_earlier`: Drag the fillet before the boss sketch in the timeline [reorder]
- `tl_roll_back`: Drag the history marker back after the first extrude [rollback]
- `tl_roll_back_and_forward`: Roll the history marker back, then to the end again [rollback]
- `tl_roll_to_start`: Roll the history marker to the very start (an empty design), add a plate there, roll to the end [rollback, insert]
- `tl_suppress_boss`: Box with a round boss; suppress the boss in the timeline [suppress]
- `tl_suppress_first_roundtrip`: Suppress the first extrude (the fillet on it goes off too), then unsuppress [suppress, reference-stability]
- `tl_suppress_sketch`: Suppress the boss sketch: the extrude made from it goes off too [suppress]

### mirror (9)

- `mirror_body_join_face`: Plate with a boss mirrored as a body across its right face, Operation Join [bodies, fusion-dialog]
- `mirror_body_new_body`: Plate with a boss mirrored as a body across its right face, Operation New Body [bodies, new-body, fusion-dialog]
- `mirror_body_new_body_move_after`: A body mirrored across YZ as a New Body, then the original moved 20 up: the mirrored body stays [bodies, new-body, move, fusion-dialog]
- `mirror_boss`: Plate with a boss mirrored across YZ
- `mirror_faces_hole`: Plate 40x30x10 centred: the wall of a hole r3 at (10, 5) mirrored across YZ (Faces) [faces, fusion-dialog]
- `mirror_features_yz_fusion`: Plate 40x30x10 centred, a boss r3x6 at (10, 5) mirrored across YZ (Mirror dialog) [fusion-dialog]
- `mirror_fillet_feature`: Box 40x30x10 centred, one vertical edge filleted r3, the fillet mirrored across YZ [fillet, fusion-dialog]
- `mirror_hole_and_its_pattern`: A hole and its Rectangular Pattern mirrored together across YZ [pattern, features, fusion-dialog]
- `modify2_mirror_adjust_to_slope`: Wedge, a hole cut from below up to the sloped top, mirrored about YZ with Compute Option Adjust [compute-option, adjust, fusion-dialog]

### hardware (8)

- `hardware_button_head_m4`: An M4x10 ISO 7380 button head on the top face: plain clearance hole, the dome on the face [screw, button]
- `hardware_countersunk_m4_on_rim`: A d4.5 through hole, then an M4x12 ISO 10642 screw clicked on its rim: the countersink is added, head flush [screw, countersink, rim]
- `hardware_edit_length`: M3x10 socket head with the hole as deep as the screw, edited to M3x16: the hole follows [screw, edit]
- `hardware_insert_m3_hole`: Insert an M3 heat-set insert on the top face: a 4.0 x 6.7 flat hole [insert]
- `hardware_magnet_6x3_pocket`: Insert a 6 x 3 round magnet on the top face: a 6.2 x 3 flat pocket, magnet flush [magnet]
- `hardware_nut_top`: An M3 ISO 4032 hex nut on the top face: clearance hole, nut on the face [nut]
- `hardware_shcs_m3_counterbore`: Insert an M3x10 ISO 4762 screw on the top face: counterbored clearance hole [screw, counterbore]
- `hardware_washer_bottom`: An M3 ISO 7089 washer on the bottom face: clearance hole, washer under the part [washer]

### scale (8)

- `modify2_scale_sketch`: A sketch scaled x1.5 after it was extruded, the scale then edited to x2 [sketch, fusion-dialog]
- `modify2_scale_two_bodies`: Two cubes scaled x2 about the origin in one step [multi-body, fusion-dialog]
- `sf_scale_about_corner`: Box scaled 0.5 about its corner (40, 30, 10) [sciforge-scale]
- `sf_scale_corner_follows_edit`: Box scaled 0.5 about its top corner, then the extrude edited 10 -> 20 [sciforge-scale, reference-stability, edit]
- `sf_scale_edit_factor`: Box scaled 2, edited to 1.5 [sciforge-scale, edit]
- `sf_scale_non_uniform`: Box scaled non uniformly X 2, Y 1, Z 0.5 about the origin [sciforge-scale]
- `sf_scale_non_uniform_keeps_faces`: Scale 2, Press Pull the top 5, the scale edited to Non Uniform 2 / 1 / 1: the Press Pull keeps the top [edit, press-pull, reference-stability]
- `sf_scale_uniform`: Box 40x30x10 scaled 2 about the origin [sciforge-scale]

### sketch (8)

- `sketch_face_line_through_circle`: Block 100x40x20, sketch on its top with the face's edges projected, a line across the face and a circle r6 on it: both halves of the circle extruded 10 [auto-project, regions]
- `sketch_face_line_through_circle_half`: Same sketch: only the left half of the circle extruded 10 [auto-project, regions]
- `sketch_face_projected_corner`: Block 40x30x10, sketch on its top with the face's edges projected, a 10x10 rectangle from the projected corner: only the rectangle extruded 5 [auto-project, regions]
- `sketch_face_projected_rest`: Block 40x30x10, sketch on its top with the face's edges projected, a 10x10 rectangle from the projected corner: the L-shaped rest of the face extruded 5 [auto-project, regions]
- `sketch_inscribed_pentagon`: Plate with an inscribed pentagon (corner radius 8) cut through [polygon]
- `sketch_line_through_circle_overhang`: Rectangle 40x30, a line past both its sides through a circle r5: both halves of the circle extruded 8 [regions]
- `sketch_nut_trap_polygon`: Plate with a circumscribed hexagon (5.5 across flats) cut through, resized to 8 [polygon, edit]
- `sketch_trim_union`: Circle and overlapping rectangle trimmed into one outline, extruded 10 [trim]

### thread (8)

- `thread_edit_length`: Modeled M6x1 thread, 8 long, edited to 5 [modeled, edit]
- `thread_hole_modeled`: Modeled inside M6x1 thread in a d5 through hole (size taken from the hole) [modeled, inside]
- `thread_second_after_modeled`: Two cosmetic threads on one boss; the first made Modeled afterwards: the second stays [modeled, edit]
- `thread_shaft_cosmetic`: Cosmetic M6 thread on a d6 x 12 boss [cosmetic]
- `thread_shaft_modeled`: Modeled M6x1 thread over the whole d6 x 12 boss [modeled]
- `thread_shaft_modeled_6e`: Modeled M6x1 thread of class 6e on a d6 shaft (the class moves it in) [modeled, class]
- `thread_shaft_partial`: Modeled M6x1 thread 8 long, 2 in from the end of the boss [modeled, partial]
- `thread_two_holes`: One modeled M6x1 thread on two d5 through holes at once [modeled, inside, multiple]

### gear (7)

- `sf_gear_cut_block`: Gear cut 4 mm deep into the top of a 60 x 60 x 10 block (module 1.5, 16 teeth, no bore) [cut]
- `sf_gear_edit_teeth`: Spur gear edited in the timeline: 28 teeth instead of 24, thickness symmetric on the plane [spur, edit]
- `sf_gear_english`: Spur gear, English standard: diametral pitch 10, 20 teeth, 0.5 in thick, 0.5 in bore [spur, english]
- `sf_gear_internal`: Internal (ring) gear on XY: module 2, 40 teeth, rim 5, 8 thick [internal]
- `sf_gear_join_block`: Gear joined onto the top of a 60 x 60 x 10 block, 5 mm up (module 1.5, 16 teeth, 6 mm bore) [join]
- `sf_gear_rack`: Rack on XY: module 2, 10 teeth, 20 degrees, root fillet 0.5, 5 mm under the root, 6 thick [rack]
- `sf_gear_spur_basic`: Spur gear on XY: module 2, 24 teeth, 20 degrees, root fillet 0.5, 10 thick, 10 mm bore [spur]

### rib (7)

- `sf_rib_arc`: Rib: a quarter arc r20 (centre (25, 25)) across the inside corner, To Next [fusion-rib]
- `sf_rib_depth`: Rib: Depth 5 instead of To Next: a strip 5 wide along the corner line [fusion-rib]
- `sf_rib_edit_thickness`: Rib: the corner gusset, then edited to 4 thick [fusion-rib]
- `sf_rib_far_from_origin`: Rib: the gusset of sf_rib_gusset 450 mm along X (the sketch's origin far from the part) [fusion-rib, ai-tools]
- `sf_rib_gusset`: Rib: a line across the inside corner of an L bracket, To Next, 2 thick (a gusset) [fusion-rib]
- `sf_rib_one_side`: Rib: the gusset line on the bracket's side face y = 0, One Side 3 thick [fusion-rib]
- `sf_rib_one_side_flip`: Rib: the gusset line on the bracket's far face y = -20, One Side 3 thick, Flip Side [fusion-rib]

### web (7)

- `sf_web_arc`: Web: a half circle r10 on the rim, its free ends carried on to the near wall [fusion-web]
- `sf_web_cross`: Web: a cross of two 20 long lines on the tray's rim, To Next, extended to the walls [fusion-web]
- `sf_web_depth`: Web: the cross with Depth 4 instead of To Next [fusion-web]
- `sf_web_depth_thin_wall`: Web: Depth 4, One Side 3 thick, carried on to 2 mm walls (it must stop at the walls) [fusion-web, regression]
- `sf_web_not_extended`: Web: the cross, then edited with Extend Curves off (only the drawn 20 long lines) [fusion-web]
- `sf_web_one_side`: Web: one line 1 from a wall, One Side 3 thick (towards the wall: only 1 of it is new) [fusion-web]
- `sf_web_one_side_flip`: Web: the same line, One Side 3 thick, edited to Flip Side (away from the wall) [fusion-web]

### components (6)

- `comp_move_captured_roll`: A component moved with Capture Position, then the history marker before the move and back [move, timeline]
- `comp_move_rotate_pivot`: A component turned 90 degrees about Z through a pivot at its corner (Free Move, Set Pivot) [move]
- `comp_paste_instance_follows`: Copy / Paste of a component: the linked instance follows an edit of the original [paste]
- `comp_paste_new_independent`: Paste New of a component: the independent copy keeps its shape when the original changes [paste]
- `comp_pattern_circular_6`: Circular pattern of a component: 6 instances about the Z axis [pattern]
- `comp_pattern_rect_extent`: Rectangular pattern of a component along X: 3 instances over an extent of 100 [pattern]

### construct (6)

- `inspect_angle_plane_notch`: Box, Plane at Angle 90 about the front top edge, a circle r 5 on the edge cut symmetric 10 [plane-at-angle, sketch-on-plane]
- `inspect_construct_all`: Box with a round boss; every CONSTRUCT entry built on it and checked
- `inspect_midplane_hole`: Box, Midplane of front and back faces, a circle r 3 on it cut symmetric 40 (a hole along Y) [midplane, sketch-on-plane]
- `inspect_offset_plane_boss`: Box, Offset Plane 5 above the top, a circle r 5 sketched on it extruded 5 down (join) [offset-plane, sketch-on-plane]
- `inspect_offset_plane_to_object`: Offset Plane with Extent To Object: the YZ plane offset through a corner of the box, following the corner when the box grows [offset-plane, to-object, reference-stability]
- `inspect_three_points_oblique_hole`: Box, Point at Vertex, Plane Through Three Points (two corners + that point), a circle r 2 on the slanted plane cut symmetric 20 through the box [three-points, construction-point, sketch-on-plane, measure]

### move (5)

- `modify2_move_face_boss_down`: A boss r3 x 5 on top of the box, its faces moved 2 mm down [faces, boss, fusion-dialog]
- `modify2_move_face_edit`: The same move of the top face, edited to 3 mm down [faces, edit, fusion-dialog]
- `modify2_move_face_hole`: A hole through the box moved 28 mm along X, so it breaks out of the right side [faces, hole, fusion-dialog]
- `modify2_move_face_tilt`: The box's right face turned 10 deg about its top edge (Move, Rotate) [faces, rotate, fusion-dialog]
- `modify2_move_face_top`: Box 40x20x10, its top face moved 5 mm up (Move, Move Object Faces) [faces, fusion-dialog]

### emboss (4)

- `emboss_cylinder_deboss`: Deboss a 10x4 rectangle 1 mm into a cylinder r20 [cylinder]
- `emboss_cylinder_rect`: Emboss a 10x4 rectangle 1 mm round a cylinder r20 (wrapped like a label) [cylinder]
- `emboss_flat_deboss`: Deboss a 10x4 rectangle 1 mm into the top of a 40x20x10 block
- `emboss_flat_rect`: Emboss a 10x4 rectangle 1 mm up on the top of a 40x20x10 block [basic]

### reference-stability (4)

- `edit_extrude_then_shell`: Shelled box whose extrude height is edited 30 -> 50 [edit, shell]
- `edit_fillet_radius`: Fillet all edges r1, then edit radius to 3 [edit, fillet]
- `edit_pattern_count`: Hole pattern count edited from 3 to 5 [edit, pattern]
- `edit_width_after_fillet_and_hole`: Change the first sketch's width after fillet + hole [edit]

### cut (3)

- `plate_through_hole_cut`: Plate 50x30x8 with a through cut r5 [through-all]
- `pocket_depth`: Block 50x50x20 with a 20x20 pocket 8 deep [pocket]
- `symmetric_cut_slot`: Slot cut symmetric through a block from the XZ plane [symmetric]

### inspect (3)

- `inspect_com_interference`: Two bodies overlapping 10x10x5: centre of mass and interference [center-of-mass, interference]
- `inspect_com_materials`: Center of Mass of a steel and an aluminium box (mass-weighted) [center-of-mass, material]
- `inspect_measure_section`: Box with a round boss: Measure distances / angles and Section Analysis cuts [measure, section]

### blend (2)

- `live_spline_top_chamfer`: Live picture on the exact result: spline wall's top edge, chamfer 1 mm [chamfer, live-blend, free-form]
- `live_spline_top_fillet`: Live picture on the exact result: spline wall's top edge, fillet 1 mm [fillet, live-blend, free-form]

### export (2)

- `export_report_design`: Export report: what STEP, IGES, STL, 3MF and OBJ leave out of a design with components, a hidden body and a material [export-report, components]
- `export_report_sketch_dxf`: Export report: what Save As DXF leaves out of a sketch (dimensions, constraints, construction, points, reference curves, its place in 3D) [export-report, dxf, sketch]

### picks (2)

- `picks_fillet_chamfer_kept_after_reopen`: A round and a chamfer keep their edges when the extrude under them gets a taper, after the design was saved and opened again [reference-stability, reopen]
- `picks_shell_kept_on_taper`: A shell keeps its open top face when the extrude under it gets a taper [reference-stability, edit]

### coil (1)

- `sf_coil_old_narrow_upgraded`: A narrowing coil saved by SciForge before the 2026-10-11 fixes (its mirror image) is rebuilt right when the file is opened [reopen, upgrade]

### import (1)

- `export_report_imports`: Import report: what Insert Mesh, Insert DXF / SVG and Open / Insert STEP say did not come in [export-report]

### join (1)

- `sf_join_away_new_body`: Join away from the part makes a new body (Extrude, Box, Coil, Pipe), never a second lump [new-body, extrude, primitive, coil, pipe, bodies]

### parameters (1)

- `param_driven_box`: Box driven by user parameters, then width changed [edit, reference-stability]

### pipe (1)

- `sf_pipe_old_upgraded`: A pipe saved by SciForge before the 2026-10-11 fixes (its section linked to the path object) is rebuilt when the file is opened and stays the same [reopen, upgrade]

### replace-face (1)

- `modify2_replace_face_cone`: A box's top face replaced onto the face of a cone (another body) [cone, fusion-dialog]

## By design-step op

| Op | Built by the tools | Models | Some of them |
|---|---|---|---|
| `age` | (a test helper) | 2 | `sf_coil_old_narrow_upgraded`, `sf_pipe_old_upgraded` |
| `align_bodies` | `align` | 2 | `direct_align_block_on_table`, `direct_align_flip_angle` |
| `blend_chamfer` | `chamfer` | 9 | `blend_chamfer_angle`, `blend_chamfer_top_face`, `blend_chamfer_two_flip`, `blend_edit_keeps_later_chamfer`, `live_blend_chamfer_angle` |
| `blend_edit` | `edit_step` | 1 | `blend_edit_keeps_later_chamfer` |
| `blend_fillet` | `fillet` | 14 | `blend_edit_keeps_later_chamfer`, `blend_fillet_boss_feature`, `blend_fillet_edit_radius`, `blend_fillet_presspull_radius`, `blend_fillet_slot_chain` |
| `blend_insert` | `fillet`, `chamfer` | 1 | `blend_insert_chamfer_before_fillet` |
| `blend_radius_expect` | (a test helper) | 2 | `fillet2_variable_points`, `live_fillet2_variable_points` |
| `body_material` | `physical_material` | 2 | `export_report_design`, `inspect_com_materials` |
| `body_tool_edit` | `edit_step` | 4 | `bodies_combine_edit_operation`, `bodies_move_edit`, `bodies_move_two_bodies`, `bodies_split_edit_tool` |
| `chamfer` | (a test helper) | 2 | `chamfer_one_edge`, `chamfer_top_edges` |
| `check` | (a test helper) | 59 | `blend_edit_keeps_later_chamfer`, `blend_fillet_edit_radius`, `blend_insert_chamfer_before_fillet`, `bodies_combine_edit_operation`, `bodies_combine_follows_tool` |
| `circular_pattern` | `circular_pattern` | 3 | `pattern_circ_faces_bolt_circle`, `pattern_circ_suppressed_bodies`, `pattern_circ_symmetric_holes` |
| `com_expect` | (a test helper) | 2 | `inspect_com_interference`, `inspect_com_materials` |
| `combine` | `combine` | 10 | `bodies_combine_cut`, `bodies_combine_cut_cylinder`, `bodies_combine_edit_operation`, `bodies_combine_follows_tool`, `bodies_combine_intersect` |
| `component_move` | `move_copy` | 3 | `comp_move_captured_roll`, `comp_move_rotate_pivot`, `pattern_bodies_in_moved_component` |
| `component_paste` | `copy_component` | 3 | `comp_paste_instance_follows`, `comp_paste_new_independent`, `export_report_design` |
| `component_pattern` | `pattern_components` | 2 | `comp_pattern_circular_6`, `comp_pattern_rect_extent` |
| `components_from_bodies` | `components_from_bodies` | 8 | `comp_move_captured_roll`, `comp_move_rotate_pivot`, `comp_paste_instance_follows`, `comp_paste_new_independent`, `comp_pattern_circular_6` |
| `construct` | `construct_plane`, `construct_axis`, `construct_point` | 6 | `inspect_angle_plane_notch`, `inspect_construct_all`, `inspect_midplane_hole`, `inspect_offset_plane_boss`, `inspect_offset_plane_to_object` |
| `construct_expect` | (a test helper) | 6 | `inspect_angle_plane_notch`, `inspect_construct_all`, `inspect_midplane_hole`, `inspect_offset_plane_boss`, `inspect_offset_plane_to_object` |
| `construct_extrude` | (a test helper) | 5 | `inspect_angle_plane_notch`, `inspect_midplane_hole`, `inspect_offset_plane_boss`, `inspect_offset_plane_to_object`, `inspect_three_points_oblique_hole` |
| `delete` | `delete_step` | 5 | `extrude_multi_cut_timeline`, `extrude_multi_join_delete`, `hole_second_survives_first`, `tl_delete_before_fillet`, `tl_delete_hole` |
| `delete_bodies` | `delete_bodies` | 2 | `bodies_combine_new_body_target_deleted`, `bodies_combine_tool_deleted` |
| `delete_face` | `delete_face` | 2 | `bodies_delete_face_fillet`, `bodies_delete_face_hole` |
| `edit` | `set_sketch_dimension`, `edit_step` | 32 | `blend_fillet_edit_radius`, `bodies_combine_follows_tool`, `comp_paste_instance_follows`, `comp_paste_new_independent`, `edit_extrude_then_shell` |
| `emboss` | `emboss` | 4 | `emboss_cylinder_deboss`, `emboss_cylinder_rect`, `emboss_flat_deboss`, `emboss_flat_rect` |
| `expect_bodies` | (a test helper) | 38 | `extrude_multi_cut`, `extrude_multi_cut_all`, `extrude_multi_cut_all_far`, `extrude_multi_cut_edit`, `extrude_multi_cut_excluded` |
| `expect_component` | (a test helper) | 1 | `sf_cylinder_new_component` |
| `expect_move_refused` | (a test helper) | 1 | `extrude_multi_move` |
| `expect_radius` | (a test helper) | 1 | `sf_sweep_guide_surface` |
| `export_report_expect` | (a test helper) | 2 | `export_report_design`, `export_report_sketch_dxf` |
| `extrude` | `extrude` | 367 | `blend_chamfer_angle`, `blend_chamfer_top_face`, `blend_chamfer_two_flip`, `blend_edit_keeps_later_chamfer`, `blend_fillet_boss_feature` |
| `fillet` | (a test helper) | 16 | `bodies_delete_face_fillet`, `bracket_inner_fillet`, `edit_fillet_radius`, `edit_width_after_fillet_and_hole`, `fillet_all_edges` |
| `fillet_sets` | `fillet_sets` | 14 | `fillet2_chamfer_sets_angle_flip`, `fillet2_chord_90_120`, `fillet2_face_and_its_edge_in_two_sets`, `fillet2_presspull_set_radius`, `fillet2_sets_tangent_chain_each` |
| `full_round` | `full_round_fillet` | 1 | `fillet2_full_round_rib` |
| `fusion_mirror` | `mirror` | 8 | `mirror_body_join_face`, `mirror_body_new_body`, `mirror_body_new_body_move_after`, `mirror_faces_hole`, `mirror_features_yz_fusion` |
| `hide_bodies` | (a test helper) | 1 | `export_report_design` |
| `history_off` | `capture_design_history` | 1 | `direct_history_off_on` |
| `history_on` | `capture_design_history` | 1 | `direct_history_off_on` |
| `hole` | `hole` | 3 | `hole_blind`, `hole_counterbore`, `hole_countersink` |
| `hole_at` | `hole` | 17 | `hardware_countersunk_m4_on_rim`, `hole_clearance_countersunk`, `hole_clearance_m6`, `hole_clearance_socket_cbore`, `hole_curved_follows` |
| `hole_points` | `hole` | 1 | `hole_points_flipped` |
| `import_report_expect` | (a test helper) | 1 | `export_report_imports` |
| `interference_expect` | (a test helper) | 1 | `inspect_com_interference` |
| `live_blend_expect` | (a test helper) | 16 | `live_blend_chamfer_angle`, `live_blend_chamfer_top_face`, `live_blend_chamfer_two_flip`, `live_blend_fillet_boss_feature`, `live_blend_fillet_slot_chain` |
| `measure_bodies` | (a test helper) | 28 | `bodies_combine_tool_deleted`, `extrude_multi_cut`, `extrude_multi_cut_all`, `extrude_multi_cut_all_far`, `extrude_multi_cut_edit` |
| `measure_components` | (a test helper) | 3 | `comp_paste_instance_follows`, `comp_paste_new_independent`, `pattern_bodies_in_moved_component` |
| `measure_expect` | (a test helper) | 2 | `inspect_measure_section`, `inspect_three_points_oblique_hole` |
| `mirror` | (a test helper) | 1 | `mirror_boss` |
| `modify_edit` | `edit_step` | 2 | `direct_replace_face_edit_down`, `direct_silhouette_edit_to_faces` |
| `move` | `move_step` | 2 | `extrude_multi_move`, `tl_move_fillet_earlier` |
| `move_bodies` | `move_copy` | 12 | `bodies_move_copy`, `bodies_move_edit`, `bodies_move_free`, `bodies_move_point_to_point`, `bodies_move_point_to_position` |
| `move_face` | `move_copy` | 5 | `modify2_move_face_boss_down`, `modify2_move_face_edit`, `modify2_move_face_hole`, `modify2_move_face_tilt`, `modify2_move_face_top` |
| `move_face_edit` | `edit_step` | 1 | `modify2_move_face_edit` |
| `parameter` | `set_parameter` | 13 | `export_report_design`, `param_driven_box`, `pattern_quantity_parameter`, `pattern_symmetric_parameter`, `sf_box_param_driven` |
| `path_pattern` | `pattern_on_path` | 4 | `modify2_pattern_path_auto_start`, `modify2_pattern_path_start_point`, `pattern_path_bosses`, `pattern_path_circle_turned` |
| `pattern_circ` | `pattern` | 1 | `flange_polar_holes` |
| `pattern_edit` | `edit_step` | 2 | `pattern_edit_keeps_later_fillet`, `pattern_edit_quantity_fusion` |
| `pattern_rect` | `pattern` | 2 | `edit_pattern_count`, `plate_hole_grid` |
| `press_pull` | `press_pull` | 25 | `blend_fillet_presspull_radius`, `direct_history_off_on`, `direct_split_face_then_press_pull`, `fillet2_presspull_set_radius`, `pp_boss_grow` |
| `press_pull_type` | `press_pull` | 4 | `modify2_presspull_modify_extrude`, `modify2_presspull_modify_offset`, `modify2_presspull_modify_pocket`, `modify2_presspull_new_offset` |
| `rectangular_pattern` | `rectangular_pattern` | 16 | `mirror_hole_and_its_pattern`, `modify2_pattern_adjust_to_slope`, `modify2_pattern_identical_to_slope`, `modify2_pattern_multibody_cut`, `pattern_bodies_in_moved_component` |
| `remove_bodies` | `remove_bodies` | 1 | `direct_remove_body` |
| `reopen` | (a test helper) | 5 | `fillet2_two_sets`, `live_fillet2_two_sets`, `picks_fillet_chamfer_kept_after_reopen`, `sf_coil_old_narrow_upgraded`, `sf_pipe_old_upgraded` |
| `reopen_check` | (a test helper) | 1 | `extrude_multi_cut_reopen` |
| `replace_face` | `replace_face` | 3 | `direct_replace_face_edit_down`, `direct_replace_face_up_to_body`, `modify2_replace_face_cone` |
| `revolve` | (a test helper) | 4 | `groove_ring`, `revolve_cylinder`, `revolve_quarter`, `revolve_washer` |
| `roll` | `roll_timeline` | 8 | `blend_insert_chamfer_before_fillet`, `comp_move_captured_roll`, `extrude_multi_cut_timeline`, `extrude_multi_move`, `tl_insert_before_fillet` |
| `rule_fillet` | `rule_fillet` | 3 | `fillet2_rule_all_edges`, `fillet2_rule_between_follows_edit`, `live_fillet2_rule_all_edges` |
| `section_expect` | (a test helper) | 1 | `inspect_measure_section` |
| `sf_coil` | `coil` | 13 | `sf_coil_basic`, `sf_coil_cut_block`, `sf_coil_edit_turns`, `sf_coil_old_narrow_upgraded`, `sf_coil_param_driven` |
| `sf_curves` | `create_curve_sketch` | 60 | `extrude_thin_arc_center`, `extrude_thin_open_l`, `sf_loft_centerline_ends`, `sf_loft_centerline_torus`, `sf_loft_cone_point` |
| `sf_draft` | `draft` | 13 | `sf_draft_cylinder`, `sf_draft_edit_angle`, `sf_draft_ellipse_wall`, `sf_draft_ellipse_wall_edit`, `sf_draft_ellipse_wall_flip` |
| `sf_draft2` | `draft` | 5 | `modify2_draft_fixed_symmetric`, `modify2_draft_fixed_two_side`, `modify2_draft_parting_plane_two_side`, `modify2_draft_parting_sketch_one_side`, `modify2_draft_two_bodies` |
| `sf_draft_edit` | `edit_step` | 2 | `sf_draft_edit_angle`, `sf_draft_ellipse_wall_edit` |
| `sf_gear` | `gear` | 7 | `sf_gear_cut_block`, `sf_gear_edit_teeth`, `sf_gear_english`, `sf_gear_internal`, `sf_gear_join_block` |
| `sf_gear_edit` | `edit_step` | 1 | `sf_gear_edit_teeth` |
| `sf_hardware` | `insert_hardware` | 8 | `hardware_button_head_m4`, `hardware_countersunk_m4_on_rim`, `hardware_edit_length`, `hardware_insert_m3_hole`, `hardware_magnet_6x3_pocket` |
| `sf_hardware_edit` | `edit_step` | 1 | `hardware_edit_length` |
| `sf_loft` | `loft` | 22 | `sf_loft_centerline_ends`, `sf_loft_centerline_torus`, `sf_loft_closed_direction`, `sf_loft_cone_point`, `sf_loft_cut_cone` |
| `sf_loft_edit` | `edit_step` | 3 | `sf_loft_edit_intersect`, `sf_loft_ends_direction_weight`, `sf_loft_merge_slot` |
| `sf_path_sketch` | (a test helper) | 9 | `sf_join_away_new_body`, `sf_pipe_hollow_half`, `sf_pipe_old_upgraded`, `sf_pipe_param_driven`, `sf_pipe_ring_hollow` |
| `sf_pipe` | `pipe` | 14 | `sf_join_away_new_body`, `sf_pipe_corner_hollow_cut`, `sf_pipe_corner_intersect`, `sf_pipe_corner_mitre_join`, `sf_pipe_edge_auto_join` |
| `sf_primitive` | `primitive` | 29 | `direct_silhouette_body_sphere`, `direct_silhouette_edit_to_faces`, `direct_silhouette_faces_sphere`, `sf_box_basic`, `sf_box_param_driven` |
| `sf_primitive_edit` | `edit_step` | 3 | `sf_box_pocket_edit_join`, `sf_coil_edit_turns`, `sf_pipe_triangle_edit` |
| `sf_revolve` | `revolve` | 20 | `modify2_replace_face_cone`, `sf_revolve_cone`, `sf_revolve_construction_follows`, `sf_revolve_cut_other_body`, `sf_revolve_cut_two_bodies` |
| `sf_revolve_edit` | `edit_step` | 3 | `sf_revolve_edit_operation`, `sf_revolve_face_profile_follows`, `sf_revolve_to_then_angle` |
| `sf_rib` | `rib`, `web` | 14 | `sf_rib_arc`, `sf_rib_depth`, `sf_rib_edit_thickness`, `sf_rib_far_from_origin`, `sf_rib_gusset` |
| `sf_rib_edit` | `edit_step` | 3 | `sf_rib_edit_thickness`, `sf_web_not_extended`, `sf_web_one_side_flip` |
| `sf_scale` | `scale` | 6 | `sf_scale_about_corner`, `sf_scale_corner_follows_edit`, `sf_scale_edit_factor`, `sf_scale_non_uniform`, `sf_scale_non_uniform_keeps_faces` |
| `sf_scale_bodies` | `scale` | 1 | `modify2_scale_two_bodies` |
| `sf_scale_edit` | `edit_step` | 2 | `sf_scale_edit_factor`, `sf_scale_non_uniform_keeps_faces` |
| `sf_scale_sketch` | `scale` | 1 | `modify2_scale_sketch` |
| `sf_scale_sketch_edit` | `edit_step` | 1 | `modify2_scale_sketch` |
| `sf_shell` | `shell` | 13 | `picks_shell_kept_on_taper`, `sf_draft_then_shell`, `sf_shell_both`, `sf_shell_both_edit_presspull`, `sf_shell_both_follows_extrude_edit` |
| `sf_shell_bodies` | `shell` | 1 | `modify2_shell_two_bodies` |
| `sf_shell_edit` | `edit_step` | 3 | `sf_shell_both_edit_presspull`, `sf_shell_edit_to_both`, `sf_shell_swap_presspull_follows` |
| `sf_surface` | `surface` | 19 | `surface2_extrude_all`, `surface2_extrude_from_curved_face`, `surface2_extrude_from_face`, `surface2_extrude_to_body`, `surface2_extrude_to_chain_faces` |
| `sf_surface_edit` | `edit_step` | 5 | `surface2_extrude_all`, `surface2_extrude_from_face`, `surface2_loft_centerline`, `surface2_sweep_rail`, `surface_thicken_corner` |
| `sf_sweep` | `sweep` | 18 | `sf_sweep_both_sides`, `sf_sweep_distance_parameter`, `sf_sweep_edit_distance`, `sf_sweep_face_taper`, `sf_sweep_groove_cut` |
| `sf_sweep_edit` | `edit_step` | 1 | `sf_sweep_edit_distance` |
| `shell` | `shell` | 3 | `edit_extrude_then_shell`, `shell_filleted_box`, `shell_open_box` |
| `silhouette_split` | `silhouette_split` | 3 | `direct_silhouette_body_sphere`, `direct_silhouette_edit_to_faces`, `direct_silhouette_faces_sphere` |
| `sketch` | `create_sketch` | 405 | `blend_chamfer_angle`, `blend_chamfer_top_face`, `blend_chamfer_two_flip`, `blend_edit_keeps_later_chamfer`, `blend_fillet_boss_feature` |
| `sketch_extras` | (a test helper) | 1 | `export_report_sketch_dxf` |
| `sketch_polygon` | `sketch_polygon` | 2 | `sketch_inscribed_pentagon`, `sketch_nut_trap_polygon` |
| `sketch_trim` | `sketch_trim` | 1 | `sketch_trim_union` |
| `split_body` | `split_body` | 6 | `bodies_split_by_body`, `bodies_split_edit_tool`, `bodies_split_face_extended`, `bodies_split_sketch_line`, `bodies_split_two_planes` |
| `split_face` | `split_face` | 4 | `direct_split_face_closest_point`, `direct_split_face_extend`, `direct_split_face_then_press_pull`, `direct_split_face_yz` |
| `suppress` | `suppress_step` | 7 | `extrude_multi_cut_timeline`, `extrude_multi_join_delete`, `extrude_multi_move`, `hole_second_survives_first`, `tl_suppress_boss` |
| `thread` | `thread` | 8 | `thread_edit_length`, `thread_hole_modeled`, `thread_second_after_modeled`, `thread_shaft_cosmetic`, `thread_shaft_modeled` |
| `unsuppress` | `suppress_step` | 6 | `extrude_multi_cut_timeline`, `extrude_multi_join_delete`, `extrude_multi_move`, `hole_second_survives_first`, `tl_suppress_first_roundtrip` |
| `use_body` | `activate` | 26 | `extrude_multi_cut`, `extrude_multi_cut_all`, `extrude_multi_cut_all_far`, `extrude_multi_cut_edit`, `extrude_multi_cut_excluded` |
