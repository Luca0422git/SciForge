# SPDX-License-Identifier: LGPL-2.1-or-later
"""The live pictures of Press Pull, Shell and Extrude (sciforge/live_shapes.py) against
FreeCAD's exact solids: runs SciForgeTests/headless/live_shapes_check.py in real FreeCAD
without a window and checks that every point of every picture lies on the exact solid built
for the same value (boxes, holes, a slope beside the pulled face, a turned and a moved body;
Shell inside / outside / both, hollow, a cylinder; Extrude one side, down, taper, symmetric,
two sides, start offset, thin). Skipped when FreeCAD is not found (run_tests.sh gives its
command in SCIFORGE_FC_CMD)."""

import os
import re
import shlex
import subprocess
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
MODULE = os.path.dirname(os.path.dirname(HERE))
TOL = 1e-4  # mm


def _command():
    cmd = os.environ.get("SCIFORGE_FC_CMD", "").strip()
    return shlex.split(cmd) if cmd else None


@unittest.skipUnless(_command(), "FreeCAD not given (SCIFORGE_FC_CMD)")
class LivePicturesOnExactSolids(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        code = (
            "import sys; sys.path.insert(0, %r); "
            "from SciForgeTests.headless import live_shapes_check as c; c.main()" % MODULE
        )
        run = subprocess.run(_command() + ["-c", code], capture_output=True, text=True, timeout=600)
        cls.output = (run.stdout + run.stderr).replace("\r", "\n")

    def test_every_case_ran(self):
        self.assertNotIn("live check ERROR", self.output)
        done = re.search(r"live check done (\d+)", self.output)
        self.assertIsNotNone(done, self.output[-2000:])
        self.assertGreaterEqual(int(done.group(1)), 40)

    def test_every_picture_lies_on_its_solid(self):
        found = re.findall(r"live check (.+?): worst ([0-9.e+-]+) over (\d+) points", self.output)
        self.assertGreaterEqual(len(found), 40, self.output[-2000:])
        bad = [(label, float(w)) for label, w, n in found if float(w) > TOL or int(n) == 0]
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
