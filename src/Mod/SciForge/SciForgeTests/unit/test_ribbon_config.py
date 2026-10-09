# SPDX-License-Identifier: LGPL-2.1-or-later
"""The ribbon layout data. Runs without FreeCAD."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from sciforge import config, ribbon_config as cfg, ui_icon_path  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
# Every command name FreeCAD 1.1.4 registers (with all workbench GUIs loaded).
with open(os.path.join(HERE, "freecad_1_1_4_commands.txt"), encoding="utf-8") as handle:
    FREECAD_COMMANDS = {line.strip() for line in handle if line.strip()}
SCIFORGE_COMMANDS = {
    "SciForge_NewDesign",
    "SciForge_NewSketch",
    "SciForge_CommandSearch",
    "SciForge_ToggleTimeline",
    "SciForge_ResetShortcuts",
    "SciForge_Diagnostics",
}


def all_groups():
    seen = []
    for tab in cfg.TABS:
        for grp in tab["groups"]:
            if all(grp is not g for g in seen):
                seen.append(grp)
    return seen


class RibbonConfigTests(unittest.TestCase):
    def test_every_icon_exists(self):
        missing = sorted(
            {
                i["icon"]
                for i in cfg.all_items()
                if i.get("icon") and not os.path.isfile(ui_icon_path(i["icon"]))
            }
        )
        for grp in all_groups():
            for entry in grp["items"]:
                if entry and entry.get("submenu") is not None and entry.get("icon"):
                    if not os.path.isfile(ui_icon_path(entry["icon"])):
                        missing.append(entry["icon"])
        self.assertEqual(missing, [], "run tools/sciforge/make_icons.py or fix the names")

    def test_big_buttons_exist_in_their_menu(self):
        for grp in all_groups():
            for label in grp["big"]:
                self.assertIsNotNone(cfg.find(grp, label), "%s: %s" % (grp["title"], label))

    def test_mapped_commands_exist_in_freecad_1_1_4(self):
        known = FREECAD_COMMANDS | SCIFORGE_COMMANDS | {"__menu__"}
        wrong = []
        for entry in cfg.all_items():
            names = cfg.command_names(entry["command"])
            if names and not any(n in known for n in names):
                wrong.append("%s -> %s" % (entry["label"], "/".join(names)))
        self.assertEqual(wrong, [])

    def test_shortcut_targets_exist(self):
        known = FREECAD_COMMANDS | SCIFORGE_COMMANDS
        self.assertEqual([n for n in config.SHORTCUTS if n not in known], [])

    def test_no_duplicate_shortcut_keys(self):
        keys = list(config.SHORTCUTS.values())
        self.assertEqual(len(keys), len(set(keys)))

    def test_sketch_tab_is_contextual(self):
        sketch = [t for t in cfg.TABS if t["id"] == "sketch"][0]
        self.assertTrue(sketch.get("contextual"))
        self.assertIn("FINISH SKETCH", [g["title"] for g in sketch["groups"]])

    def test_solid_tab_matches_fusion_group_order(self):
        solid = [t for t in cfg.TABS if t["id"] == "solid"][0]
        titles = [g["title"] for g in solid["groups"]]
        self.assertEqual(
            titles, ["CREATE", "MODIFY", "CONSTRUCT", "INSPECT", "INSERT", "ASSEMBLE", "SELECT"]
        )

    def test_press_pull_is_listed_with_q(self):
        modify = cfg.SOLID_MODIFY
        entry = cfg.find(modify, "Press Pull")
        self.assertEqual(entry["key"], "Q")
        self.assertEqual(modify["items"][0], entry, "Press Pull is first in Fusion's MODIFY menu")


if __name__ == "__main__":
    unittest.main()
