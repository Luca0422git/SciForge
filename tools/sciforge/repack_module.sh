#!/usr/bin/env bash
# SPDX-License-Identifier: LGPL-2.1-or-later
# SciForge: puts a new SciForge module into an earlier release's download, for a patch release
# (.github/workflows/sciforge-patch-release.yml, docs/sciforge/patch-release.md). The compiled
# program stays exactly as it was built; only Mod/SciForge is replaced.
#
#   tools/sciforge/repack_module.sh portable --module DIR --archive OLD.7z --name NEW --dir DIR
#   tools/sciforge/repack_module.sh appimage --module DIR --archive OLD.AppImage --out NEW.AppImage
#
# --module   the new module folder (make_quick_update.sh --out X makes X/SciForge, with the
#            build ids written in)
# portable:  unpacks OLD.7z in --dir, renames its folder to NEW, replaces the module and packs
#            DIR/NEW.7z the way package/rattler-build/windows/create_bundle.sh does. The folder
#            DIR/NEW stays for make_installer.sh (the installer is made from it).
# appimage:  unpacks the AppImage, replaces the module, packs it again with appimagetool (the
#            options of package/rattler-build/linux/create_bundle.sh).
# Both check that the module inside is the new one (its VERSION file) before packing.
set -euo pipefail

MODE="${1:-}"
shift || true
MODULE="" ARCHIVE="" NAME="" DIR="" OUT=""
while [ $# -gt 0 ]; do
    case "$1" in
        --module) MODULE="$2"; shift 2 ;;
        --archive) ARCHIVE="$2"; shift 2 ;;
        --name) NAME="$2"; shift 2 ;;
        --dir) DIR="$2"; shift 2 ;;
        --out) OUT="$2"; shift 2 ;;
        *) echo "repack_module.sh: unknown argument: $1" >&2; exit 2 ;;
    esac
done
fail() { echo "[SciForge] repack_module.sh: $*" >&2; exit 1; }
[ -f "${MODULE}/sciforge/__init__.py" ] || fail "--module ${MODULE} is not a SciForge module folder"
[ -f "${ARCHIVE}" ] || fail "--archive ${ARCHIVE} not found"
MODULE="$(cd "${MODULE}" && pwd)"
ARCHIVE="$(cd "$(dirname "${ARCHIVE}")" && pwd)/$(basename "${ARCHIVE}")"
WANT="$(tr -d '[:space:]' < "${MODULE}/VERSION")"

# The one Mod/SciForge folder below $1, replaced by the new module.
replace_module() {
    local root="$1" found
    mapfile -t found < <(find "${root}" -path '*/Mod/SciForge/sciforge/__init__.py' -not -path '*/__pycache__/*')
    [ "${#found[@]}" -eq 1 ] || fail "expected one Mod/SciForge in ${root}, found ${#found[@]}"
    local target
    target="$(dirname "$(dirname "${found[0]}")")"
    echo "[SciForge] old module: ${target} ($(tr -d '[:space:]' < "${target}/VERSION" 2>/dev/null || echo '?'))"
    rm -rf "${target}"
    cp -r "${MODULE}" "${target}"
    find "${target}" -name __pycache__ -prune -exec rm -rf {} +
    local got
    got="$(tr -d '[:space:]' < "${target}/VERSION")"
    [ "${got}" = "${WANT}" ] || fail "the module put in says ${got}, not ${WANT}"
    echo "[SciForge] new module: ${target} (${got})"
}

case "${MODE}" in
    portable)
        [ -n "${NAME}" ] && [ -n "${DIR}" ] || fail "portable needs --name and --dir"
        mkdir -p "${DIR}"
        cd "${DIR}"
        rm -rf "${NAME}" unpacked
        mkdir unpacked
        7z x -y -ounpacked "${ARCHIVE}" >/dev/null
        mapfile -t tops < <(find unpacked -mindepth 1 -maxdepth 1 -type d)
        [ "${#tops[@]}" -eq 1 ] || fail "expected one folder in ${ARCHIVE}, found ${#tops[@]}"
        mv "${tops[0]}" "${NAME}"
        rmdir unpacked
        replace_module "${NAME}"
        rm -f "${NAME}.7z"
        7z a -t7z -mx9 -mmt=on "${NAME}.7z" "${NAME}" -bb0 >/dev/null
        echo "[SciForge] packed $(pwd)/${NAME}.7z ($(du -h "${NAME}.7z" | cut -f1))"
        ;;
    appimage)
        [ -n "${OUT}" ] || fail "appimage needs --out"
        work="$(mktemp -d)"
        trap 'rm -rf "${work}"' EXIT
        chmod +x "${ARCHIVE}"
        (cd "${work}" && "${ARCHIVE}" --appimage-extract >/dev/null)
        [ -x "${work}/squashfs-root/AppRun" ] || fail "${ARCHIVE} did not unpack (no AppRun)"
        replace_module "${work}/squashfs-root"
        tool="${work}/appimagetool-$(uname -m).AppImage"
        curl -fsSL -o "${tool}" \
            "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-$(uname -m).AppImage"
        chmod +x "${tool}"
        mkdir -p "$(dirname "${OUT}")"
        OUT="$(cd "$(dirname "${OUT}")" && pwd)/$(basename "${OUT}")"
        # no FUSE on the runner: the tool unpacks itself and runs
        APPIMAGE_EXTRACT_AND_RUN=1 "${tool}" \
            --comp zstd --mksquashfs-opt -Xcompression-level --mksquashfs-opt 22 \
            "${work}/squashfs-root" "${OUT}" >/dev/null
        chmod +x "${OUT}"
        echo "[SciForge] packed ${OUT} ($(du -h "${OUT}" | cut -f1))"
        ;;
    *)
        echo "usage: repack_module.sh portable|appimage ... (see the first lines of this file)" >&2
        exit 2
        ;;
esac
