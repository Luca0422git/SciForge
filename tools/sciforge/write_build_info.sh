#!/usr/bin/env bash
# SciForge: writes the two small files that say which build this is, into a SciForge module
# folder (src/Mod/SciForge in the full build, SciForge/ in a quick update):
#   sciforge/build_info.py   COMMIT and DATE  (SciForge > Diagnostics shows them)
#   sciforge/core_info.py    CORE, the compiled part's id (tools/sciforge/core_id.sh); the update
#                            check installs only the small module update over a build with the
#                            same core (sciforge/update_core.py plan). Only written when given:
#                            without --core the file keeps saying "" (unknown).
#
#   tools/sciforge/write_build_info.sh --module DIR --commit SHA --date YYYY-MM-DD [--core ID]
set -euo pipefail
MODULE="" COMMIT="" DATE="" CORE=""
while [ $# -gt 0 ]; do
    case "$1" in
        --module) MODULE="$2"; shift 2 ;;
        --commit) COMMIT="$2"; shift 2 ;;
        --date) DATE="$2"; shift 2 ;;
        --core) CORE="$2"; shift 2 ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done
if [ ! -d "${MODULE}/sciforge" ]; then
    echo "write_build_info.sh: --module must be a SciForge module folder (with sciforge/ inside)" >&2
    exit 2
fi
if [[ ! "${COMMIT}" =~ ^[0-9A-Za-z._-]+$ || ! "${DATE}" =~ ^[0-9A-Za-z._-]+$ || ! "${CORE}" =~ ^[0-9A-Za-z._-]*$ ]]; then
    echo "write_build_info.sh: --commit and --date are required; values may only hold letters, digits and . _ -" >&2
    exit 2
fi
printf 'COMMIT = "%s"\nDATE = "%s"\n' "${COMMIT:0:8}" "${DATE}" > "${MODULE}/sciforge/build_info.py"
if [ -n "${CORE}" ]; then
    printf '# SPDX-License-Identifier: LGPL-2.1-or-later\n"""Written by tools/sciforge/write_build_info.sh."""\nCORE = "%s"\n' \
        "${CORE}" > "${MODULE}/sciforge/core_info.py"
fi
echo "[SciForge] build info written to ${MODULE}/sciforge (commit ${COMMIT:0:8}, ${DATE}, core ${CORE:-unknown})"
