#!/bin/bash
# SPDX-License-Identifier: LGPL-2.1-or-later
# SCIFORGE: builds the Windows installer from the bundle folder <version_name> next to this
# script (create_bundle.sh calls it; the scenario-debug workflow's "installer" job runs it on an
# earlier build's portable files). Needs makensis in ${CONDA_PREFIX}/NSIS (pixi env "package").
# Leaves <version_name>-installer.exe here.
set -e
version_name="$1"
[ -n "${version_name}" ] && [ -d "${version_name}" ] || { echo "[SciForge] usage: make_installer.sh <bundle folder>"; exit 1; }

FILES_FREECAD="$(cygpath -w $(pwd))\\${version_name}"
# SCIFORGE: makensis cannot open files past Windows' 260-character path limit, and the
# checkout folder carries the repository's name twice (D:\a\<repo>\<repo>): with the repo
# named SciForge-Parametric-Design one debugpy file reached 277 characters and the
# sciforge-v0.1.0-beta build stopped here. A drive letter for the bundle folder keeps every
# path short whatever the repository is called.
bundle_drive=""
for letter in S T U V W X Y; do
    if MSYS_NO_PATHCONV=1 subst "${letter}:" "${FILES_FREECAD}"; then
        bundle_drive="${letter}:"
        break
    fi
done
if [ -n "${bundle_drive}" ]; then
    echo "[SciForge] installer reads the bundle from ${bundle_drive} (${FILES_FREECAD})"
    FILES_FREECAD="${bundle_drive}"
else
    echo "[SciForge] no free drive letter for the bundle, using the long path"
fi
nsis_cmd="${CONDA_PREFIX}/NSIS/makensis.exe"
nsis_status=0
"${nsis_cmd}" -V4 \
    -D"ExeFile=${version_name}-installer.exe" \
    -D"FILES_FREECAD=${FILES_FREECAD}" \
    -X'SetCompressor /FINAL lzma' \
    ../../WindowsInstaller/FreeCAD-installer.nsi || nsis_status=$?
if [ -n "${bundle_drive}" ]; then
    MSYS_NO_PATHCONV=1 subst "${bundle_drive}" /D || true
fi
[ "${nsis_status}" -eq 0 ] || exit "${nsis_status}"
mv ../../WindowsInstaller/${version_name}-installer.exe .
