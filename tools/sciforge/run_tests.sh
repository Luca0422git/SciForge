#!/usr/bin/env bash
# Runs every SciForge test that does not need a full SciForge build:
#   1. unit tests          (plain Python, no FreeCAD)
#   2. golden models       (real FreeCAD, headless)
#   2b. headless AI tools  (every AI tool once, real FreeCAD without a window, every tool
#                           call of the documentation for AI models, and an AI agent
#                           building and checking a part only through MCP)
#   3. GUI smoke test      (real FreeCAD GUI on a virtual screen via xvfb-run)
#
#   tools/sciforge/run_tests.sh [--freecad DIR] [--out DIR]
#                               [--only unit|golden|headless|gui|scenarios|base]
#                               [--scenario NAME[,NAME...]]   (files of SciForgeTests/gui/
#                                                   scenarios; several share one profile)
#                               [--shard K/N]       (every N-th scenario, from the K-th)
#
# --freecad  folder from tools/sciforge/get_freecad.sh (default .sciforge-cache/freecad),
#            an unpacked SciForge AppImage, or a SciForge install prefix containing
#            bin/SciForgeCmd (bin/FreeCADCmd for a build before the branding pass)
# --out      where reports and the screenshot go (default .sciforge-cache/test-output)
# --only     base = everything but the scenarios (unit, golden, headless, smoke, journey)
# --shard    splits the scenarios over N runs (CI runs them side by side): 1/4 runs the
#            1st, 5th, 9th... scenario in name order, 2/4 the 2nd, 6th... (N runs cover all)
#
# FreeCAD runs with a throw-away user profile, so your own FreeCAD settings are untouched.
set -uo pipefail
LC_COLLATE=C  # the same scenario order everywhere (--shard relies on it)

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FREECAD_DIR="${REPO}/.sciforge-cache/freecad"
OUT="${REPO}/.sciforge-cache/test-output"
ONLY=""
SHARD_INDEX=1
SHARD_COUNT=1
while [ $# -gt 0 ]; do
    case "$1" in
        --freecad) FREECAD_DIR="$2"; shift 2 ;;
        --out) OUT="$2"; shift 2 ;;
        --only) ONLY="$2"; shift 2 ;;
        --scenario) SCENARIO="$2"; ONLY="scenarios"; shift 2 ;;
        --shard)
            SHARD_INDEX="${2%/*}"; SHARD_COUNT="${2#*/}"
            if ! [[ "${SHARD_INDEX}" =~ ^[0-9]+$ && "${SHARD_COUNT}" =~ ^[0-9]+$ ]] \
                || [ "${SHARD_INDEX}" -lt 1 ] || [ "${SHARD_INDEX}" -gt "${SHARD_COUNT}" ]; then
                echo "--shard must be K/N with 1 <= K <= N, e.g. 2/4" >&2; exit 2
            fi
            shift 2 ;;
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
    # A SciForge AppImage has sciforgecmd / sciforge (the branding pass), FreeCAD's has
    # freecadcmd / freecad.
    if [ -x "${FREECAD_DIR}/squashfs-root/usr/bin/sciforgecmd" ]; then
        FC_CMD=("${FREECAD_DIR}/squashfs-root/AppRun" sciforgecmd)
        FC_GUI=("${FREECAD_DIR}/squashfs-root/AppRun" sciforge)
    else
        FC_CMD=("${FREECAD_DIR}/squashfs-root/AppRun" freecadcmd)
        FC_GUI=("${FREECAD_DIR}/squashfs-root/AppRun" freecad)
    fi
    # A SciForge AppImage already has the module built in; stock FreeCAD needs the add-on link.
    if [ -d "${FREECAD_DIR}/squashfs-root/usr/Mod/SciForge" ]; then ADDON=0; else ADDON=1; fi
elif ls "${FREECAD_DIR}"/bin/{SciForgeCmd,sciforgecmd,FreeCADCmd,freecadcmd} >/dev/null 2>&1; then
    FC_CMD=("$(ls "${FREECAD_DIR}"/bin/{SciForgeCmd,sciforgecmd,FreeCADCmd,freecadcmd} 2>/dev/null | head -1)")
    FC_GUI=("$(ls "${FREECAD_DIR}"/bin/{SciForge,sciforge,FreeCAD,freecad} 2>/dev/null | head -1)")
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
# No test goes online: the update check (sciforge/update_core.py) refuses every address but
# this computer's own (the tests' fake GitHub), and does not even start by itself.
export SCIFORGE_NO_INTERNET=1

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

# Every AI tool called once in real FreeCAD without a window (SciForgeTests/headless).
run_headless() {
    echo "== [SciForge] headless AI tools"
    need_freecad headless || return
    SCIFORGE_HEADLESS_OUT="${OUT}" timeout 1200 "${FC_CMD[@]}" -c \
        "from SciForgeTests.headless import runner; runner.main()" > "${OUT}/headless.log" 2>&1
    grep -aoE "\[SciForge\] headless (FAIL|MISSING|summary).*" "${OUT}/headless.log"
    python3 - "${OUT}/headless-report.json" <<'EOF2' || FAILED+=("headless")
import json, sys
try:
    report = json.load(open(sys.argv[1]))
except Exception as exc:
    print("no headless report: %s" % exc); sys.exit(1)
sys.exit(0 if report.get("passed") else 1)
EOF2
    # Every tool call shown in the documentation for AI models, and every tool's reference
    # example, run in real FreeCAD (SciForgeTests/headless/docs_runner.py).
    echo "== [SciForge] documentation examples (headless)"
    SCIFORGE_HEADLESS_OUT="${OUT}" timeout 1200 "${FC_CMD[@]}" -c \
        "from SciForgeTests.headless import docs_runner; docs_runner.main()" > "${OUT}/docs.log" 2>&1
    grep -aoE "\[SciForge\] docs (FAIL|summary).*" "${OUT}/docs.log"
    python3 - "${OUT}/docs-report.json" <<'EOF3' || FAILED+=("docs examples")
import json, sys
try:
    report = json.load(open(sys.argv[1]))
except Exception as exc:
    print("no docs report: %s" % exc); sys.exit(1)
sys.exit(0 if report.get("passed") else 1)
EOF3
    # An AI agent builds a part and checks it only through MCP, as an AI app does
    # (tools/sciforge/sciforge-cli mcp --headless; SciForgeTests/headless/agent_e2e.py).
    echo "== [SciForge] AI agent end to end (MCP, headless)"
    SCIFORGE_FREECAD="${FREECAD_DIR}" SCIFORGE_CLI_PROFILE="${PROFILE}" timeout 900 python3 \
        "${MODULE}/SciForgeTests/headless/agent_e2e.py" --out "${OUT}" \
        > "${OUT}/agent-e2e.log" 2>&1 || FAILED+=("agent e2e")
    grep -aoE "\[SciForge\] agent (FAIL|summary).*" "${OUT}/agent-e2e.log"
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
    run_gui_base && run_scenarios
}

# The GUI smoke test and the journey (not the scenarios).
run_gui_base() {
    echo "== [SciForge] GUI tests"
    need_freecad gui || return
    if ! command -v xvfb-run >/dev/null; then
        echo "xvfb-run not installed; skipping GUI tests" >&2
        FAILED+=("gui (no xvfb-run)")
        return 1
    fi
    run_gui_script smoke smoke_gui.py gui.log result.json
    # The journey uses SciForge like a person: real clicks and drags on the 3D view.
    run_gui_script journey journey_gui.py journey.log journey-result.json
    # FreeCAD opened twice with one profile: the second start restores the window layout the
    # first one saved, after SciForge is on (Luca, 2026-10-17: only the browser was left)
    local phase
    for phase in 1 2; do
        SCIFORGE_RESTART_PHASE="${phase}" run_gui_script restart restart_gui.py \
            "restart-${phase}.log" "restart-${phase}.json"
    done
    return 0
}

# Scenario tests (SciForgeTests/gui/scenarios/*.py, see harness.py): each one a
# person's workflow with real input; any error FreeCAD prints fails it.
run_scenarios() {
    echo "== [SciForge] GUI scenarios"
    need_freecad scenarios || return
    local dir="${MODULE}/SciForgeTests/gui/scenarios" file name index=0
    for file in "${dir}"/*.py; do
        name="$(basename "${file}" .py)"
        [ "${name}" = "__init__" ] && continue
        index=$((index + 1))
        [ $(((index - 1) % SHARD_COUNT + 1)) -ne "${SHARD_INDEX}" ] && continue
        # --scenario a,b,c: those, in name order, sharing one profile (as a CI shard does)
        [ -n "${SCENARIO:-}" ] && [[ ",${SCENARIO}," != *",${name},"* ]] && continue
        # Each scenario starts from FreeCAD's own window layout: one left behind in the shared
        # profile (CI #135: with the Data Panel docked, the next scenario's browser came out
        # wider and FreeCAD sent a press on a browser row to the 3D view) is not this one's.
        if [ -f "${PROFILE}/user.cfg" ]; then
            python3 - "${PROFILE}/user.cfg" <<'PYEOF' || true
import re, sys
path = sys.argv[1]
text = open(path, encoding="utf-8").read()
clean = re.sub(r'\s*<FCText Name="MainWindowState"[^>]*>[^<]*</FCText>', "", text)
clean = re.sub(r'\s*<FCText Name="MainWindowState"[^>]*/>', "", clean)
if clean != text:
    open(path, "w", encoding="utf-8").write(clean)
PYEOF
        fi
        # Through the launcher: a scenario that does not even load fails at once
        # instead of leaving FreeCAD open until the timeout.
        SCIFORGE_SCENARIO="${name}" SCIFORGE_SCENARIO_FILE="${file}" SCIFORGE_SMOKE_OUT="${OUT}" \
            timeout 900 xvfb-run -a -s "-screen 0 1920x1200x24" \
            "${FC_GUI[@]}" "${MODULE}/SciForgeTests/gui/scenario_launcher.py" \
            > "${OUT}/scenario-${name}.log" 2>&1
        python3 - "${OUT}" "${name}" <<'EOF' || FAILED+=("scenario ${name}")
import glob, json, os, sys
out, name = sys.argv[1], sys.argv[2]
log = os.path.join(out, "scenario-%s.log" % name)
ok, found = True, False
for path in sorted(glob.glob(os.path.join(out, "*-result.json"))):
    try:
        result = json.load(open(path))
    except ValueError:
        continue
    if result.get("file") != name:
        continue
    found = True
    for c in result["checks"]:
        if not c["ok"]:
            print("  FAIL %s: %s %s" % (result["name"], c["name"], c["detail"][:600]))
    if not result.get("finished"):
        print("  %s did not finish (crash or hang? see %s)" % (result["name"], log))
    ok = ok and bool(result.get("passed"))
    print("  %s: %s (%d checks)" % (
        result["name"], "PASS" if result.get("passed") else "FAIL", len(result["checks"])))
if not found:
    print("  %s: no result (FreeCAD crashed before the first step? see %s)" % (name, log))
    ok = False
sys.exit(0 if ok else 1)
EOF
    done
}

case "${ONLY}" in
    unit) run_unit ;;
    golden) run_golden ;;
    headless) run_headless ;;
    gui) run_gui ;;
    scenarios) run_scenarios ;;
    base) run_unit; run_golden; run_headless; run_gui_base ;;
    "") run_unit; run_golden; run_headless; run_gui ;;
    *) echo "--only must be unit, golden, headless, gui, scenarios or base" >&2; exit 2 ;;
esac

echo "== [SciForge] reports in ${OUT}"
if [ ${#FAILED[@]} -gt 0 ]; then
    echo "== [SciForge] FAILED: ${FAILED[*]}"
    exit 1
fi
echo "== [SciForge] all passed"
