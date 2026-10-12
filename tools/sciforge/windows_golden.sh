#!/usr/bin/env bash
# Runs SciForge's golden models with FreeCAD for Windows (on a Windows machine, in Git Bash).
#
#   tools/sciforge/windows_golden.sh --stock DIR OUT
#       the official FreeCAD for Windows (downloaded and unpacked into DIR when it is not
#       there yet) with SciForge added as an add-on, like the quick update on Luca's PC
#   tools/sciforge/windows_golden.sh --built DIR OUT
#       a SciForge build unpacked in DIR (SciForge built in)
#
# Writes OUT/golden-report.json and .md; exit 1 when a model fails.
#
# Why: the Linux tests cannot see what only Windows does. On 2026-10-12 a number too big
# for Windows' 32-bit C "long" failed every Shell Both, and it showed only at the end of a
# 3-hour Windows build. This runs in about 10 minutes on every push and before a build.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VERSION="${FREECAD_VERSION:-1.1.4}"
MODE="${1:-}"
DIR="${2:-}"
OUT="${3:-}"
if [ -z "${MODE}" ] || [ -z "${DIR}" ] || [ -z "${OUT}" ]; then
    echo "usage: $0 --stock|--built DIR OUT" >&2
    exit 2
fi
case "${MODE}" in
    --stock | --built) ;;
    *) echo "the first argument must be --stock or --built" >&2; exit 2 ;;
esac

if [ "${MODE}" = "--stock" ] && ! ls "${DIR}"/*/bin/freecadcmd.exe >/dev/null 2>&1; then
    NAME="FreeCAD_${VERSION}-Windows-x86_64-py311.7z"
    echo "[SciForge] downloading ${NAME}"
    mkdir -p "${DIR}"
    curl -fsSL --retry 4 -o "${DIR}/${NAME}" \
        "https://github.com/FreeCAD/FreeCAD/releases/download/${VERSION}/${NAME}"
    7z x -y -o"${DIR}" "${DIR}/${NAME}" >/dev/null
    rm -f "${DIR}/${NAME}"
fi

# The FreeCAD folder: the one with bin/freecadcmd.exe.
exe="$(ls "${DIR}"/bin/freecadcmd.exe "${DIR}"/*/bin/freecadcmd.exe 2>/dev/null | head -1 || true)"
if [ -z "${exe}" ]; then
    echo "[SciForge] no bin/freecadcmd.exe in ${DIR}" >&2
    exit 1
fi
echo "[SciForge] FreeCAD: ${exe}"

# A throw-away FreeCAD profile; with the official FreeCAD, SciForge goes into its Mod folder
# (a copy: links are not reliable on Windows).
profile="$(mktemp -d)"
trap 'rm -rf "${profile}"' EXIT
if [ "${MODE}" = "--stock" ]; then
    mkdir -p "${profile}/Mod"
    cp -r "${REPO}/src/Mod/SciForge" "${profile}/Mod/SciForge"
fi
mkdir -p "${OUT}"
export FREECAD_USER_HOME="$(cygpath -w "${profile}")"
export SCIFORGE_GOLDEN_OUT="$(cygpath -w "$(cd "${OUT}" && pwd)")"
rm -f "${OUT}/golden-report.json"

# FreeCAD's whole output goes to golden.log; the job log gets the SciForge lines, and the
# end of golden.log when no report came out (a start-up error has no [SciForge] in it).
"${exe}" -c "from SciForgeTests.golden import runner; runner.main()" 2>&1 | tr -d '\r' \
    > "${OUT}/golden.log" || true
grep -aE "\[SciForge\]" "${OUT}/golden.log" || true
if [ ! -f "${OUT}/golden-report.json" ]; then
    echo "[SciForge] no golden report; the end of FreeCAD's output:"
    tail -n 60 "${OUT}/golden.log"
fi

python - "${OUT}/golden-report.json" "${MODE}" <<'EOF'
import json
import sys

try:
    report = json.load(open(sys.argv[1], encoding="utf-8"))
except Exception as exc:
    print("[SciForge] no golden report (FreeCAD or SciForge did not start): %s" % exc)
    sys.exit(1)
built = sys.argv[2] == "--built"
passed = [r for r in report["results"] if r["status"] == "pass"]
print("[SciForge] Windows golden: %s, %s" % (
    report["summary"], "SciForge build" if report["sciforge_build"] else "official FreeCAD"))
if not passed:
    print("[SciForge] no model passed: SciForge was not found")
    sys.exit(1)
if built and not report["sciforge_build"]:
    print("[SciForge] this is not a SciForge build (no Mod/SciForge in it)")
    sys.exit(1)
if not built and report["sciforge_build"]:
    print("[SciForge] official FreeCAD expected, found SciForge built in")
    sys.exit(1)
sys.exit(0 if report["passed"] else 1)
EOF
