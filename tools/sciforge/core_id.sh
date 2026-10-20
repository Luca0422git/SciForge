#!/usr/bin/env bash
# SciForge: the "core id" of a commit: the short hash of the last commit that changed anything
# that ends up in the compiled part of the build (FreeCAD's C++ and its packaging) rather
# than SciForge's own Python module and the docs. Two builds with the same core id have
# the same compiled program, so a release can be installed by replacing only Mod/SciForge
# (the "module update"; update_core.plan decides, brief beta-release.md R3).
#
#   tools/sciforge/core_id.sh [COMMIT]      prints the id (default: HEAD)
#
# Needs the full git history of the paths (not a shallow clone): in a shallow clone the id
# would be the oldest commit, which is wrong, so that case fails loudly.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
commit="${1:-HEAD}"
if [ "$(git rev-parse --is-shallow-repository)" = "true" ]; then
    echo "core_id.sh: this is a shallow clone; use fetch-depth: 0 (the history decides the id)" >&2
    exit 2
fi
# VERSION is left out on purpose: a new version number alone must not force the full installer.
id="$(git log -1 --format=%h "${commit}" -- src ':!src/Mod/SciForge' \
    cMake CMakeLists.txt CMakePresets.json package pixi.toml pixi.lock)"
if [ -z "${id}" ]; then
    echo "core_id.sh: no commit found for the compiled part" >&2
    exit 1
fi
echo "${id}"
