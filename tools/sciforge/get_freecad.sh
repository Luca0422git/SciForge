#!/usr/bin/env bash
# Downloads the official FreeCAD Linux AppImage and unpacks it, so SciForge's
# tests can run against real FreeCAD without building SciForge first.
#
#   tools/sciforge/get_freecad.sh [target_dir]      (default: .sciforge-cache/freecad)
#
# Afterwards: <target_dir>/squashfs-root/AppRun freecadcmd   (headless)
#             <target_dir>/squashfs-root/AppRun freecad      (GUI)
set -euo pipefail

VERSION="${FREECAD_VERSION:-1.1.4}"
NAME="FreeCAD_${VERSION}-Linux-x86_64-py311.AppImage"
URL="https://github.com/FreeCAD/FreeCAD/releases/download/${VERSION}/${NAME}"
TARGET="${1:-.sciforge-cache/freecad}"

if [ -x "${TARGET}/squashfs-root/AppRun" ]; then
    echo "[SciForge] FreeCAD ${VERSION} already unpacked in ${TARGET}"
    exit 0
fi

mkdir -p "${TARGET}"
TARGET="$(cd "${TARGET}" && pwd)"
echo "[SciForge] downloading ${URL}"
curl -fsSL --retry 4 -o "${TARGET}/${NAME}" "${URL}"
chmod +x "${TARGET}/${NAME}"
# Unpack instead of running the AppImage directly: works without FUSE (CI, containers).
(cd "${TARGET}" && "./${NAME}" --appimage-extract >/dev/null)
rm -f "${TARGET}/${NAME}"
echo "[SciForge] FreeCAD ${VERSION} ready in ${TARGET}/squashfs-root"
