# Unfinished feature work (not loaded by SciForge)

`hole_thread_wip.patch`: the Hole/Thread feature agent's work when the agent spend limit
stopped it (2026-10-10). Untested, not merged. It adds `sciforge/hole.py`,
`sciforge/hole_ui.py` and `sciforge/thread_tables.py`. To continue:

    git apply tools/sciforge/workflows/wip/hole_thread_wip.patch

then follow `docs/sciforge/dev/feature-guide.md` (scenarios with real clicks, golden models,
full suite) before merging. The feature spec is the "hole" entry in
`tools/sciforge/workflows/fusion_features_args.json`.
