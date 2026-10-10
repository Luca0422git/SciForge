#!/usr/bin/env bash
# Runs every SciForge test that does not need a full SciForge build:
#   1. unit tests          (plain Python, no FreeCAD)
#   2. golden models       (real FreeCAD, headless)
#   3. GUI smoke test      (real FreeCAD GUI on a virtual screen via xvfb-run)
#
#   tools/sciforge/run_tests.sh [--freecad DIR] [--out DIR] [--only unit|golden|gui]
#
# --freecad  folder from tools/sciforge/get_freecad.sh (default .sciforge-cache/freecad),
#            or a SciForge install prefix containing bin/FreeCADCmd
# --out      where reports and the screenshot go (default .sciforge-cache/test-output)
#
# FreeCAD runs with a throw-away user profile, so your own FreeCAD settings are untouched.
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FREECAD_DIR="${REPO}/.sciforge-cache/freecad"
OUT="${REPO}/.sciforge-cache/test-output"
ONLY=""
while [ $# -gt 0 ]; do
    case "$1" in
        --freecad) FREECAD_DIR="$2"; shift 2 ;;
        --out) OUT="$2"; shift 2 ;;
        --only) ONLY="$2"; shift 2 ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done

MODULE="${REPO}/src/Mod/SciForge"
mkdir -p "${OUT}"
OUT="$(cd "${OUT}" && pwd)"
FAILED=()

# Locate FreeCAD: an unpacked AppImage (stock FreeCAD + SciForge as a user add-on)
# or a SciForge install where the module is already built in.
if [ -x "${FREECAD_DIR}/squashfs-root/AppRun" ]; then
    FC_CMD=("${FREECAD_DIR}/squashfs-root/AppRun" freecadcmd)
    FC_GUI=("${FREECAD_DIR}/squashfs-root/AppRun" freecad)
    # A SciForge AppImage already has the module built in; stock FreeCAD needs the add-on link.
    if [ -d "${FREECAD_DIR}/squashfs-root/usr/Mod/SciForge" ]; then ADDON=0; else ADDON=1; fi
elif [ -x "${FREECAD_DIR}/bin/FreeCADCmd" ] || [ -x "${FREECAD_DIR}/bin/freecadcmd" ]; then
    FC_CMD=("$(ls "${FREECAD_DIR}"/bin/{FreeCADCmd,freecadcmd} 2>/dev/null | head -1)")
    FC_GUI=("$(ls "${FREECAD_DIR}"/bin/{FreeCAD,freecad} 2>/dev/null | head -1)")
    ADDON=0
else
    FC_CMD=()
fi

# Throw-away FreeCAD profile; with stock FreeCAD, SciForge is linked in as an add-on.
PROFILE="$(mktemp -d)"
trap 'rm -rf "${PROFILE}"' EXIT
mkdir -p "${PROFILE}/Mod"
if [ "${ADDON:-0}" = 1 ]; then
    ln -s "${MODULE}" "${PROFILE}/Mod/SciForge"
fi
export FREECAD_USER_HOME="${PROFILE}"
export LANG=C.UTF-8

run_unit() {
    echo "== [SciForge] unit tests"
    (cd "${MODULE}" && python3 -m unittest discover -s SciForgeTests/unit -v) > "${OUT}/unit.log" 2>&1
    local rc=$?
    tail -3 "${OUT}/unit.log"
    [ $rc -eq 0 ] || FAILED+=("unit")
}

need_freecad() {
    if [ ${#FC_CMD[@]} -eq 0 ]; then
        echo "FreeCAD not found in ${FREECAD_DIR}. Run tools/sciforge/get_freecad.sh first." >&2
        FAILED+=("$1 (no FreeCAD)")
        return 1
    fi
}

run_golden() {
    echo "== [SciForge] golden models"
    need_freecad golden || return
    SCIFORGE_GOLDEN_OUT="${OUT}" "${FC_CMD[@]}" -c \
        "from SciForgeTests.golden import runner; runner.main()" > "${OUT}/golden.log" 2>&1
    grep -aoE "\[SciForge\] golden (FAIL|ERROR|XFAIL|XPASS|summary).*" "${OUT}/golden.log"
    python3 - "${OUT}/golden-report.json" <<'EOF' || FAILED+=("golden")
import json, sys
try:
    report = json.load(open(sys.argv[1]))
except Exception as exc:
    print("no golden report: %s" % exc); sys.exit(1)
sys.exit(0 if report.get("passed") else 1)
EOF
}

# run_gui_script NAME SCRIPT LOG RESULT: one GUI test in a real FreeCAD window.
run_gui_script() {
    local name="$1" script="$2" log="$3" result="$4"
    rm -f "${OUT}/${result}"
    SCIFORGE_SMOKE_OUT="${OUT}" timeout 300 xvfb-run -a -s "-screen 0 1920x1200x24" \
        "${FC_GUI[@]}" "${MODULE}/SciForgeTests/gui/${script}" > "${OUT}/${log}" 2>&1
    grep -aoE "\[SciForge\] ${name} .*" "${OUT}/${log}"
    # A Python error that FreeCAD only printed (e.g. inside a Qt callback) is still a failure.
    if grep -aq "Traceback (most recent call last)" "${OUT}/${log}"; then
        echo "Python errors in ${log}:"
        grep -a -A 6 "Traceback (most recent call last)" "${OUT}/${log}" | head -40
        FAILED+=("gui ${name} (Python errors in log)")
    fi
    python3 - "${OUT}/${result}" "${log}" <<'EOF' || FAILED+=("gui ${name}")
import json, sys
try:
    result = json.load(open(sys.argv[1]))
except Exception as exc:
    print("no GUI result (FreeCAD may have crashed; see %s): %s" % (sys.argv[2], exc)); sys.exit(1)
sys.exit(0 if result.get("passed") else 1)
EOF
}

run_gui() {
    echo "== [SciForge] GUI tests"
    need_freecad gui || return
    if ! command -v xvfb-run >/dev/null; then
        echo "xvfb-run not installed; skipping GUI tests" >&2
        FAILED+=("gui (no xvfb-run)")
        return
    fi
    run_gui_script smoke smoke_gui.py gui.log result.json
    # The journey uses SciForge like a person: real clicks and drags on the 3D view.
    run_gui_script journey journey_gui.py journey.log journey-result.json
}

case "${ONLY}" in
    unit) run_unit ;;
    golden) run_golden ;;
    gui) run_gui ;;
    "") run_unit; run_golden; run_gui ;;
    *) echo "--only must be unit, golden or gui" >&2; exit 2 ;;
esac

echo "== [SciForge] reports in ${OUT}"
if [ ${#FAILED[@]} -gt 0 ]; then
    echo "== [SciForge] FAILED: ${FAILED[*]}"
    exit 1
fi
echo "== [SciForge] all passed"
