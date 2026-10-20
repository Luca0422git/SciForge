#!/usr/bin/env bash
# Makes the pictures for the GitHub page (README.md) with the real SciForge on a virtual screen:
# runs the scenario SciForgeTests/gui/scenarios/readme_shots.py, cuts the SciForge window out of
# each full-screen grab and writes docs/sciforge/images/<name>.png.
#
#   tools/sciforge/screenshots.sh [--freecad DIR] [--out DIR]
#
# --freecad  as for run_tests.sh (default .sciforge-cache/freecad: tools/sciforge/get_freecad.sh)
# --out      where the raw grabs go (default .sciforge-cache/shots-raw)
#
# Look at every picture before you commit it (the 3D view is drawn by software OpenGL here; a
# blank view means the picture is not usable). Needs xvfb-run and Python with Pillow.
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FREECAD_DIR="${REPO}/.sciforge-cache/freecad"
OUT="${REPO}/.sciforge-cache/shots-raw"
while [ $# -gt 0 ]; do
    case "$1" in
        --freecad) FREECAD_DIR="$2"; shift 2 ;;
        --out) OUT="$2"; shift 2 ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done

mkdir -p "${OUT}"
rm -f "${OUT}"/readme_shots-*.png "${OUT}"/readme_shots-result.json
"${REPO}/tools/sciforge/run_tests.sh" --freecad "${FREECAD_DIR}" --out "${OUT}" \
    --scenario readme_shots || { echo "the scenario failed; see ${OUT}" >&2; exit 1; }

python3 - "${OUT}" "${REPO}/docs/sciforge/images" <<'EOF'
import glob
import os
import sys

from PIL import Image, ImageChops

raw, dest = sys.argv[1], sys.argv[2]
os.makedirs(dest, exist_ok=True)
files = sorted(glob.glob(os.path.join(raw, "readme_shots-*.png")))
if not files:
    sys.exit("no pictures found in " + raw)
for path in files:
    name = os.path.basename(path)[len("readme_shots-"):]
    image = Image.open(path).convert("RGB")
    # the window sits on a black screen: cut away the black border
    box = ImageChops.difference(image, Image.new("RGB", image.size, (0, 0, 0))).getbbox()
    if box is None:
        sys.exit(name + " is all black")
    image = image.crop(box)
    # 256 colours keep the files small; the interface is flat colours (the 3D parts stay fine)
    image = image.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    image.save(os.path.join(dest, name), optimize=True)
    print("[SciForge] screenshots: %s %dx%d" % (name, box[2] - box[0], box[3] - box[1]))
EOF
