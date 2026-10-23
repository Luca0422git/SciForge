You are building one feature area of SciForge, a FreeCAD 1.1.4 fork that must behave exactly like Autodesk Fusion. The owner, Luca, is a beginner who only tests; he wants the finished product, so build the whole area, not a slice. Read `docs/sciforge/dev/briefs/wave6-common.md` first (and `common.md` it points to).

## Your area: PLASTIC, part 2 (Snap Fit, Lip, Design Advice), branch `sf/plastic-2`

Fusion's behaviour, with sources: `docs/sciforge/dev/research/fusion-plastic.md`. Use the
shared contract (`plastic_core.py`, `plastic.py`: `rule_for_body`, `default_for`); do not
edit those two files (plastic-1 owns them). You may `git merge sf/plastic-1` when you need
its committed work.

Build (each with Fusion's dialog options, live preview, handles with value boxes, timeline
step, edit later, undo/redo, refusals with the reason):
1. **Snap Fit**: every type and dimension the research lists (cantilever hook with catch:
   length, width, thickness, catch height / angles, retention and insertion angles, root
   fillet, ...), placement (a point and a direction), the mating catch/groove where Fusion
   makes one, Join / New Body.
2. **Lip** (Lip and Groove): the parting edges / faces, which body gets the lip and which the
   groove, widths, heights, clearances, draft, guide face, as the research lists.
3. **Design Advice** (PLASTIC > INSPECT; research 2.11): checks Thickness (range and
   variation), Draft (against the pull direction and the rule's minimum draft), Knife Edges
   and Undercuts for the bodies of components with a rule; a colour overlay, an issues list
   with click-to-zoom, kept in the browser's Analysis folder like the other analyses
   (`surface_analysis.py` / `analysis.py` show how). Draft, Accessibility and Minimum Radius
   Analysis already exist in INSPECT. Injection-moulding simulation is out of scope.
4. Tests: scenarios `plastic2_*.py` (8+ paths: a snap fit on an enclosure wall and its catch;
   lip on a base and groove on its lid; each option; edit from the timeline; undo/redo;
   save/reopen; Esc; a refusal), golden models with hand-derived volumes, unit tests. Parity
   doc `docs/sciforge/parity/plastic-2.md`.
