# SPDX-License-Identifier: LGPL-2.1-or-later
"""INSPECT > Environmental Map Analysis (surface part 3): the kind and its pictures, without
FreeCAD (surface_analysis imports FreeCAD lazily)."""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from sciforge import surface_analysis as sa  # noqa: E402


class EnvironmentMapTests(unittest.TestCase):
    def test_kind(self):
        self.assertIn(sa.ENVIRONMENT, sa.KINDS)
        self.assertEqual(sa.title(sa.ENVIRONMENT), "Environmental Map Analysis")
        self.assertEqual(sa.icon(sa.ENVIRONMENT), "environment_map")
        self.assertEqual(sa.picks(sa.ENVIRONMENT), "bodies")
        names = [p[1] for p in sa.PROPS[sa.ENVIRONMENT]]
        for name in ("Environment", "ReflectionStrength", "Opacity", "HighQuality"):
            self.assertIn(name, names)
        self.assertEqual(sa.ENUMS["Environment"], ("Studio", "Horizon"))

    def test_pictures(self):
        for name in sa.ENVIRONMENTS:
            image = sa.environment_image(name, 64)
            self.assertEqual(len(image), 64 * 64)
            self.assertEqual(image[0], 0)  # outside the mirror ball
            middle = image[32 * 64 + 32]
            self.assertTrue(0 < middle <= 255)
            self.assertIs(image, sa.environment_image(name, 64))  # made once
        studio = sa.environment_image("Studio", 64)
        horizon = sa.environment_image("Horizon", 64)
        self.assertNotEqual(studio, horizon)
        # Studio: bright strips above, a dark floor below
        top = max(studio[row * 64 + 32] for row in range(40, 60))
        floor = max(studio[row * 64 + 32] for row in range(4, 20))
        self.assertGreater(top, 200)
        self.assertLess(floor, 80)


if __name__ == "__main__":
    unittest.main()
