#!/bin/bash

set -e
set -x

conda_env="AppDir/usr"

mkdir -p ${conda_env}

cp -a ../.pixi/envs/default/* ${conda_env}

echo -e "\nDelete unnecessary stuff"
rm -rf ${conda_env}/include
find ${conda_env} -name \*.a -delete

mv ${conda_env}/bin ${conda_env}/bin_tmp
mkdir ${conda_env}/bin
# SCIFORGE: the programs are sciforge and sciforgecmd (docs/sciforge/core-patches.md #12).
cp ${conda_env}/bin_tmp/sciforge ${conda_env}/bin/
cp ${conda_env}/bin_tmp/sciforgecmd ${conda_env}/bin
cp ${conda_env}/bin_tmp/ccx ${conda_env}/bin/
cp ${conda_env}/bin_tmp/python ${conda_env}/bin/
cp ${conda_env}/bin_tmp/pip ${conda_env}/bin/
cp ${conda_env}/bin_tmp/pyside6-rcc ${conda_env}/bin/
cp ${conda_env}/bin_tmp/gmsh ${conda_env}/bin/
cp ${conda_env}/bin_tmp/dot ${conda_env}/bin/
cp ${conda_env}/bin_tmp/unflatten ${conda_env}/bin/
rm -rf ${conda_env}/bin_tmp

sed -i '1s|.*|#!/usr/bin/env python|' ${conda_env}/bin/pip

echo -e "\nCopying Icon and Desktop file"
# SCIFORGE: SciForge's desktop entry and icon (src/XDGData, src/Gui/Icons).
cp ${conda_env}/share/applications/org.sciforge.SciForge.desktop AppDir/
sed -i 's/Exec=sciforge/Exec=AppRun/g' AppDir/org.sciforge.SciForge.desktop
cp ${conda_env}/share/icons/hicolor/scalable/apps/org.sciforge.SciForge.svg AppDir/

# Remove __pycache__ folders and .pyc files
find . -path "*/__pycache__/*" -delete
find . -name "*.pyc" -type f -delete

# reduce size
rm -rf ${conda_env}/conda-meta/
rm -rf ${conda_env}/doc/global/
rm -rf ${conda_env}/share/gtk-doc/
rm -rf ${conda_env}/lib/cmake/

find . -name "*.h" -type f -delete
find . -name "*.cmake" -type f -delete

python_version=$(${conda_env}/bin/python -c 'import platform; print("py" + platform.python_version_tuple()[0] + platform.python_version_tuple()[1])')
version_name="SciForge_${BUILD_TAG}-Linux-$(uname -m)-${python_version}"  # SCIFORGE

echo -e "\################"
echo -e "version_name:  ${version_name}"
echo -e "################"

pixi list -e default > AppDir/packages.txt
sed -i "1s/.*/\nLIST OF PACKAGES:/" AppDir/packages.txt

echo "Running SciForge command-line smoke test..."
if ! "${conda_env}/bin/sciforgecmd" --safe-mode --version; then
    echo "SciForge command-line smoke test failed; the Linux bundle cannot start."
    exit 1
fi

curl -LO https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-$(uname -m).AppImage
chmod a+x appimagetool-$(uname -m).AppImage

if [ "${UPLOAD_RELEASE}" == "true" ]; then
    case "${BUILD_TAG}" in
        *weekly*)
            GH_UPDATE_TAG="weeklies"
            ;;
        *rc*)
            GH_UPDATE_TAG="${BUILD_TAG}"
            ;;
        *)
            GH_UPDATE_TAG="latest"
            ;;
    esac
fi

echo -e "\nCreate the appimage"
# export GPG_TTY=$(tty)
chmod a+x ./AppDir/AppRun
./appimagetool-$(uname -m).AppImage \
  --comp zstd \
  --mksquashfs-opt -Xcompression-level \
  --mksquashfs-opt 22 \
  -u "gh-releases-zsync|Luca0422git|SciForge|${GH_UPDATE_TAG:-latest}|SciForge*$(uname -m)*.AppImage.zsync" \
  AppDir ${version_name}.AppImage
  # -s --sign-key ${GPG_KEY_ID} \

echo -e "\nCreate hash"
sha256sum ${version_name}.AppImage > ${version_name}.AppImage-SHA256.txt

if [ "${UPLOAD_RELEASE}" == "true" ]; then
    gh release upload --clobber ${BUILD_TAG} "${version_name}.AppImage" "${version_name}.AppImage.zsync" "${version_name}.AppImage-SHA256.txt"
    if [ "${GH_UPDATE_TAG}" == "weeklies" ]; then
        generic_name="SciForge_weekly-Linux-$(uname -m)"
        mv "${version_name}.AppImage" "${generic_name}.AppImage"
        mv "${version_name}.AppImage.zsync" "${generic_name}.AppImage.zsync"
        mv "${version_name}.AppImage-SHA256.txt" "${generic_name}.AppImage-SHA256.txt"
        gh release create weeklies --prerelease | true
        gh release upload --clobber weeklies "${generic_name}.AppImage" "${generic_name}.AppImage.zsync" "${generic_name}.AppImage-SHA256.txt"
    fi
fi
