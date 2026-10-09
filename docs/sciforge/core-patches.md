# SciForge core patches

Every change SciForge makes to files that came from upstream FreeCAD is listed here. Code
changes also carry a `SCIFORGE:` comment at the change site, so `git grep SCIFORGE:` finds them all.

Why this matters: each patch is a potential merge conflict when a new FreeCAD release is merged
in. Keeping them few, small and documented keeps upstream merges survivable (outline 3.1).

Columns: **Upstreamable?** = could this be contributed back to FreeCAD so we stop carrying it?

| # | Files | What | Why | Upstreamable? |
|---|---|---|---|---|
| 1 | `.github/workflows/*` (13 files deleted), `.github/dependabot.yml` (deleted) | Removed FreeCAD-organization automation: translations, stale-issue bot, backport, labeler, CodeQL, scorecards, Fedora nightly, issue metrics, weekly release, dependabot | Not applicable to SciForge; several ran on a schedule against our default branch and would burn the private repo's Actions minutes or try to publish releases | No (project-specific) |
| 2 | `.github/workflows/CI_master.yml` | Triggers reduced to `workflow_dispatch` (manual) | Full upstream CI is expensive; SciForge runs its own `sciforge-*.yml` workflows | No |
| 3 | `src/Mod/CMakeLists.txt`, `cMake/FreeCAD_Helpers/InitializeFreeCADBuildOptions.cmake`, `cMake/FreeCAD_Helpers/PrintFinalReport.cmake` | Adds the `BUILD_SCIFORGE` option (default ON) and builds `src/Mod/SciForge` | Ships the SciForge module in every build | No |
| 4 | `src/Mod/PartDesign/App/FeatureLinearPattern.cpp` | `Spacings2` default changed from `({})` to `({-1.0})` | **Upstream bug** in 1.1.4: `({})` stores `[0.0]`, i.e. a custom 0 mm first gap in direction 2, so a 2-direction linear pattern in Spacing mode puts its second row on top of the first. Found by golden model `plate_hole_grid`. Documents saved by stock FreeCAD keep their stored `[0.0]` | **Yes**: report and send upstream |
| 5 | `README.md` | SciForge banner prepended | Visitors must see this is SciForge (outline 2.5: do not imply it is FreeCAD) | No |

## Merging a new FreeCAD release

1. `git fetch upstream refs/tags/1.1.X:refs/tags/1.1.X`
2. `git merge 1.1.X` on a new branch.
3. Conflicts on files deleted in patch 1: keep them deleted (`git rm`).
4. Conflicts elsewhere: check this table, re-apply the patch, update the row if it changed.
5. Run `tools/sciforge/run_tests.sh` and the golden models before merging the branch.
