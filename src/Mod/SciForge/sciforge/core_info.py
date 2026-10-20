# SPDX-License-Identifier: LGPL-2.1-or-later
"""Which compiled part (FreeCAD plus SciForge's core patches) this SciForge was built with.

The build writes the real value here (tools/sciforge/core_id.sh: the last commit that
changed anything outside src/Mod/SciForge that ends up in the build). "" means unknown (a
source tree, or a quick update from a test run): the update check then offers the full
installer, never the small module update. The module update is safe only when the installed
core and the release's core are the same (update_core.plan)."""
CORE = ""
