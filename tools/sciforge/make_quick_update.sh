#!/usr/bin/env bash
# SciForge: packages the quick update (the SciForge module only, no rebuild needed) the way
# every download of it is made: the test workflow's artifact and the release's
# SciForge-quick-update-<version>.zip (sciforge-build.yml) both use this script.
#
#   tools/sciforge/make_quick_update.sh --out DIR [--zip FILE] [--commit SHA] [--date YYYY-MM-DD]
#                                       [--core ID]
#
# --out     the folder to build in (made fresh): SciForge/ (the module), install_update.ps1,
#           install_update.cmd and README.md (docs/sciforge/quick-update.md)
# --zip     also pack DIR's content into this zip (the folder content at the zip's root, as
#           the CI artifact has it; the same bytes for the same input: fixed file dates)
# --commit  written to sciforge/build_info.py (default: $GITHUB_SHA or git HEAD, 8 characters)
# --date    ditto (default: today, UTC)
# --core    the core id (tools/sciforge/core_id.sh) written to sciforge/core_info.py: only for a
#           release, whose module may replace the module of a build with the same compiled
#           part. Without it core_info.py says "" (unknown) and the update check then offers the
#           full installer, so a test run's quick update never claims a core it does not know.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="" ZIP="" COMMIT="" DATE="" CORE=""
while [ $# -gt 0 ]; do
    case "$1" in
        --out) OUT="$2"; shift 2 ;;
        --zip) ZIP="$2"; shift 2 ;;
        --commit) COMMIT="$2"; shift 2 ;;
        --date) DATE="$2"; shift 2 ;;
        --core) CORE="$2"; shift 2 ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done
[ -n "${OUT}" ] || { echo "make_quick_update.sh: --out DIR is required" >&2; exit 2; }
if [ -z "${COMMIT}" ]; then
    COMMIT="${GITHUB_SHA:-$(git -C "${REPO}" rev-parse HEAD 2>/dev/null || echo development)}"
fi
COMMIT="${COMMIT:0:8}"
[ -n "${DATE}" ] || DATE="$(date -u +%Y-%m-%d)"
if [[ ! "${CORE}" =~ ^[0-9A-Za-z._-]*$ ]]; then
    echo "make_quick_update.sh: --core may only hold letters, digits and . _ -" >&2; exit 2
fi

rm -rf "${OUT}"
mkdir -p "${OUT}"
cp -r "${REPO}/src/Mod/SciForge" "${OUT}/SciForge"
find "${OUT}" -name __pycache__ -prune -exec rm -rf {} +
"${REPO}/tools/sciforge/write_build_info.sh" --module "${OUT}/SciForge" \
    --commit "${COMMIT}" --date "${DATE}" ${CORE:+--core "${CORE}"}
cp "${REPO}/tools/sciforge/install_update.ps1" "${REPO}/tools/sciforge/install_update.cmd" "${OUT}/"
cp "${REPO}/docs/sciforge/quick-update.md" "${OUT}/README.md"
echo "[SciForge] quick update built in ${OUT}"

if [ -n "${ZIP}" ]; then
    mkdir -p "$(dirname "${ZIP}")"
    rm -f "${ZIP}"
    python3 - "${OUT}" "${ZIP}" <<'PYEOF'
import os, sys, zipfile
src, target = sys.argv[1], sys.argv[2]
stamp = (2020, 1, 1, 0, 0, 0)  # fixed, so the same input gives the same zip
with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
    for root, dirs, files in os.walk(src):
        dirs.sort()
        for name in sorted(files):
            path = os.path.join(root, name)
            info = zipfile.ZipInfo(os.path.relpath(path, src).replace(os.sep, "/"), stamp)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            with open(path, "rb") as handle:
                archive.writestr(info, handle.read())
print("[SciForge] quick update zip: %s (%d KB)" % (target, os.path.getsize(target) // 1024))
PYEOF
fi
