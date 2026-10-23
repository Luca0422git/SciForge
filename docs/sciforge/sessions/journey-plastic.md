# Session: PLASTIC journey (wave 6 integration, 2026-10-23)

Branch `sf/journey-pl` from `wave6-integration`. Nobody had built a whole plastic part with
the new tools together; this session did it with real clicks and keys only, the way a Fusion
user would, and fixed what broke on the way.

## The journey (scenarios `journey_plastic`, `journey_plastic_rule`, `journey_plastic_timeline`)

Steps and hand-worked numbers: `SciForgeTests/gui/journey_plastic_steps.py`.

1. New design; New Component "Base": Create Sketch on XY, a 80 x 50 rectangle, E, 25
   (100000 mm3). The root again, New Component "Lid": the same rectangle, E, Start Offset 25,
   10, Operation New Body (z 25..35, 40000).
2. PLASTIC > Assign Plastic Rule: "ABS 2 mm" for Base, then for Lid (one design copy, ABS
   material, no timeline step).
3. Shell (the Lid hidden with its eye): the Base's top face, the rule's 2 mm comes up by
   itself (19592 by hand); the Base hidden, the view from below with the ViewCube, the Lid's
   bottom face (12032).
4. Create Sketch on the Base's rim (the parting plane), four points 10 mm in from the
   corners; Boss: a click on the sketch's browser row, head side in the Lid, thread side in
   the Base (both by hand, plastic_steps' formulas at this height), ribs on the thread side.
5. A second rim sketch with a point on the inside of the long back wall; Snap Fit: the hook
   on the Lid, turned with Rotation Angle to face the wall, its groove in the Base's back
   wall (21.824 exact, all inside the wall).
6. Lip (the Lid hidden): the rim's four inside edges clicked, Lip And Groove: the lip on the
   Base (248 - drafts = 243.67 exact), the groove in the Lid; Ctrl+Z (both gone), Ctrl+Y.
7. Offset Plane 3 mm in front of the front wall, a 20 x 10 rectangle on it, Rest: a pad
   standing 3 mm out of the wall, one flat 20 x 10 face at y -3.
8. Design Advice on both bodies: issues listed (the walls have no draft), no error. Then
   "PC 2 mm" assigned to the Base alone: the Base becomes polycarbonate, the Lid stays ABS,
   the analysis names both rules; Ctrl+Z.
9. (`journey_plastic_rule`) Manage Plastic Rules: the design's rule edited to 2.5 mm: both
   Shell steps (by hand), the Boss's ribs (0.6 x T), the Snap Fit's beam, the Lip's width
   (T / 2) and the Rest's thickness follow; Ctrl+Z all back to 2 mm, Ctrl+Y to 2.5.
10. Save, close, reopen: same volumes and steps. Double-click Boss (Offset Position 1 moves
    both halves, OK, Ctrl+Z), Snap Fit (rule thickness and the turn read back, Beam Length
    14, OK), Lip (4 edges, rule width 1.25, height 1.5 grows it, Esc leaves it).
11. (`journey_plastic_timeline`) The root active: the history marker before the Boss (both
    halves back to their shells, by hand) and to the end; the Lip suppressed from its
    right-click menu (the lip and its groove in the Lid gone; the Rest goes too, see below)
    and unsuppressed; the Snap Fit deleted (its groove step goes with it, the back wall whole
    again: + 21.824, the Lip still fine), Ctrl+Z.

## Bugs found and fixed

- **Rest on a wall of a shelled box filled the box** (`plastic_rest.py`): the profile's
  shadow crossed the far wall too; that wall's inside face looks towards the sketch plane like
  the outer skin, so the rest's walls ran through the whole inside (+1717 mm3 instead of
  about 312). Only the first layer of material along the rest's direction is used now
  (`_first_layer`).
- **New Body after an automatic Join left an empty body** (`extrude.py` `_structure`): the
  Lid's box touched the Base, so the dialog previewed a Join into the Base's body; choosing
  New Body then made a second body in the Lid and left the sketch's own (empty) body beside
  it. An empty sketch body now takes the new solid, as when the dialog opens.
- **A component's eye showed every row under it** (`browser_ui.py`): hiding then showing a
  component turned on its origin planes and the sketches its extrudes had hidden (they then
  took the clicks in the view: the Lid's Shell click hit its sketch). The eye now shows back
  what it hid (Fusion: what is inside keeps its own eyes); without a memory (hidden before a
  reopen) it shows all but the origin, sketches and construction.

- **Deleting the Snap Fit broke the Lip after it** (`timeline_ops.py`): the Lip's `Edges`
  sit on the step before it, here the Snap Fit's hidden groove step in the Base; Delete took
  that step and FreeCAD emptied the link, so the Lip failed and the lip vanished. The
  timeline's reference memory (which keeps a fillet's edges when the step under it goes)
  now covers `Edges` too (Lip, Hem, Corner Round), and a link FreeCAD emptied is found
  again by geometry on the new base step.

## Not bugs (documented behaviour, worked around in the journey)

- Suppressing the Lip also suppressed the Rest (parity `timeline-browser.md`: "Suppress
  also suppresses what depends on it"): the offset plane for the Rest was made on the front
  face of the Base's last step at that time (the Lip), so it counts as depending on the Lip.
  Fusion would see that face as the Shell's and leave the Rest on. Listed as an open issue
  (attachments follow the Tip step, not the step that made the face).

## Not bugs (documented behaviour, worked around in the journey)

- A Join touching a body of another component joins into that body (parity
  `extrude-presspull.md`, Objects To Cut row: "Join merges the bodies it touches"). The Lid
  is made with New Body. Open question for Luca: Fusion keeps a feature's bodies in the
  active component (G); if so the automatic operation should be New Body there.
- The timeline shows only the active component's steps (parity `components.md`); a
  double-click edit of the Snap Fit makes the Lid active, so the root is activated again
  before the Lip's step can be double-clicked.
- The Snap Fit's catch faces the sketch's X (parity `plastic-2.md`): a sketch on a rim face
  gets its axes from the face, so the catch is turned with Rotation Angle to face the wall.

## Seen, not fixed (small)

- Design Advice names bodies by label only: with two components each holding "Body1" its
  rule line reads "Body1: ABS 2 mm; Body1: ABS 2 mm" and the issues list "Body1 Face3" for
  either body (the component's name would tell them apart).

## Tests (real FreeCAD 1.1.4 under xvfb)

- `journey_plastic` 215 checks, `journey_plastic_rule` 291, `journey_plastic_timeline` 218:
  PASS.
- After the fixes: golden models with "plastic" in their name (31, with the new
  `plastic_rest_closed_box`), `plastic_rest`, `plastic_qa_tools`, `plastic_boss_face`,
  `plastic2_lip`, `extrude_multibody`, `components_extrude`, `gaps_join_new_body`,
  `fixdecal_components`, `components_basic`, `timeline_browser_qa3`, `smmore_hem`,
  `smmore_corner`, `smmore_round`, `fixpattern_marker`: PASS; `--only unit` (1994): OK.
- `extrude_multibody_edit` fails one timing check ("the drag answered quickly": 11-12.8 s
  for 16 moves, limit 8 s) with and without this branch's changes (checked by running it on
  the base code): a speed problem of the integration branch or this machine, not a
  regression of this session. `--only base` (unit 1994, golden 583 + 2 xfail, smoke,
  journey, restart): all passed.
