# SPDX-License-Identifier: LGPL-2.1-or-later
"""The Qt-free cores of Derive (derive_core), Decal (decal_core), Preferences (prefs_core),
Scripts and Add-Ins (scripts_core) and Compute All (compute_core). Runs without FreeCAD."""

import math
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sciforge import compute_core, decal_core, derive_core, prefs_core, scripts_core  # noqa: E402


class DeriveCore(unittest.TestCase):
    def test_item_keys(self):
        key = derive_core.item_key("body", "Body001")
        self.assertEqual(key, "body:Body001")
        self.assertEqual(derive_core.parse_item(key), ("body", "Body001"))
        self.assertEqual(derive_core.parse_item("nonsense"), (None, None))
        self.assertEqual(derive_core.parse_item("plane:X"), (None, None))
        with self.assertRaises(derive_core.DeriveError):
            derive_core.item_key("wheel", "X")

    def test_results_round_trip(self):
        mapping = {"body:Body": "Body003", "parameter:width": "width_1"}
        stored = derive_core.result_entries(mapping)
        self.assertEqual(derive_core.result_map(stored), mapping)
        self.assertEqual(stored, sorted(stored))

    def test_plan_edit(self):
        added, removed, kept = derive_core.plan_edit(["a", "b", "c"], ["b", "d", "a"])
        self.assertEqual((added, removed, kept), (["d"], ["c"], ["b", "a"]))

    def test_tree_groups_in_browser_order(self):
        rows = [
            {"kind": "parameter", "name": "w"},
            {"kind": "body", "name": "B1"},
            {"kind": "sketch", "name": "S"},
            {"kind": "body", "name": "B2"},
        ]
        groups = derive_core.tree(rows)
        self.assertEqual([g[1] for g in groups], ["Bodies", "Sketches", "Parameters"])
        self.assertEqual([r["name"] for r in groups[0][2]], ["B1", "B2"])

    def test_row_text(self):
        self.assertEqual(
            derive_core.row_text({"kind": "body", "label": "Body1", "component": "Arm"}),
            "Arm > Body1",
        )
        self.assertEqual(
            derive_core.row_text({"kind": "parameter", "label": "w", "value_text": "12 mm"}),
            "w = 12 mm",
        )

    def test_summary_words(self):
        self.assertEqual(derive_core.summary([]), "nothing")
        self.assertEqual(derive_core.summary(["body:A"]), "1 body")
        self.assertEqual(
            derive_core.summary(["body:A", "body:B", "sketch:S", "parameter:p"]),
            "2 bodies, 1 sketch and 1 parameter",
        )

    def test_unique_parameter_names(self):
        self.assertEqual(derive_core.unique_name("width", []), "width")
        self.assertEqual(derive_core.unique_name("width", ["width"]), "width_1")
        self.assertEqual(derive_core.unique_name("width", ["width", "width_1"]), "width_2")

    def test_source_relative_first(self):
        here = "/nas/proj/Cart.FCStd"
        files = {"/nas/proj/parts/Wheel.FCStd", "/old/Wheel.FCStd"}
        found = derive_core.resolve_source(
            here, "parts/Wheel.FCStd", "/old/Wheel.FCStd", lambda p: p in files
        )
        self.assertEqual(found, os.path.normpath("/nas/proj/parts/Wheel.FCStd"))
        found = derive_core.resolve_source(
            here, "gone.FCStd", "/old/Wheel.FCStd", files.__contains__
        )
        self.assertEqual(found, "/old/Wheel.FCStd")
        self.assertIsNone(derive_core.resolve_source(here, "x", "/y", lambda p: False))
        self.assertIsNone(derive_core.resolve_source("", "", "", lambda p: True))

    def test_stamps(self):
        stamp = derive_core.stamp(100.5, 2048, "abc")
        self.assertEqual(derive_core.parse_stamp(stamp), (100.5, 2048, "abc"))
        self.assertEqual(derive_core.parse_stamp("broken"), (None, None, ""))
        self.assertEqual(
            derive_core.compare_stamp(stamp, 100.5, 2048), (derive_core.UP_TO_DATE, None)
        )
        # a newer save: different size and content
        state, fresh = derive_core.compare_stamp(stamp, 200.0, 4096, lambda: "def")
        self.assertEqual((state, fresh), (derive_core.NEWER, None))
        # a copied folder: new time, same content -> up to date, stamp refreshed
        state, fresh = derive_core.compare_stamp(stamp, 300.0, 2048, lambda: "abc")
        self.assertEqual(state, derive_core.UP_TO_DATE)
        self.assertEqual(derive_core.parse_stamp(fresh), (300.0, 2048, "abc"))
        self.assertEqual(derive_core.compare_stamp("", 1, 1)[0], derive_core.NEWER)

    def test_file_stamp_and_digest(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "a.FCStd")
            with open(path, "wb") as handle:
                handle.write(b"hello")
            mtime, size, digest = derive_core.parse_stamp(derive_core.file_stamp(path))
            self.assertEqual(size, 5)
            self.assertEqual(digest, derive_core.file_digest(path))
            self.assertEqual(len(digest), 40)

    def test_state_words_say_what_to_do(self):
        self.assertIn("Update Derive", derive_core.state_words(derive_core.NEWER, "Wheel"))
        self.assertIn("not found", derive_core.state_words(derive_core.MISSING, "Wheel"))
        self.assertIn("Link broken", derive_core.state_words(derive_core.BROKEN, "Wheel"))
        self.assertIn("Up to date", derive_core.state_words(derive_core.UP_TO_DATE, "Wheel"))

    def test_cycles_refused(self):
        with self.assertRaises(derive_core.DeriveError):
            derive_core.check_cycle("/a/X.FCStd", "/a/X.FCStd", [])
        with self.assertRaises(derive_core.DeriveError):
            derive_core.check_cycle("/a/X.FCStd", "/a/Y.FCStd", ["/a/X.FCStd"])
        derive_core.check_cycle("/a/X.FCStd", "/a/Y.FCStd", ["/a/Z.FCStd"])
        derive_core.check_cycle("", "/a/Y.FCStd", [""])

    def test_copy_name_is_hidden(self):
        path = derive_core.copy_name("/nas", "a-b/c")
        self.assertTrue(os.path.basename(path).startswith("."))
        self.assertTrue(path.endswith(".FCStd"))
        self.assertNotIn("/", os.path.basename(path))
        self.assertEqual(derive_core.design_name("/x/Wheel.FCStd"), "Wheel")


class DecalCore(unittest.TestCase):
    OPTS = {"width": 20.0, "height": 10.0}

    def test_frame_axes(self):
        x, y, z = decal_core.frame_axes((0, 0, 1))
        self.assertEqual((x, y, z), ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)))
        x, y, z = decal_core.frame_axes((1, 0, 0))  # X is the normal: X cannot be along it
        self.assertAlmostEqual(abs(decal_core._dot(x, (1, 0, 0))), 0.0)
        self.assertAlmostEqual(decal_core._dot(decal_core._cross(x, y), z), 1.0)

    def test_upright_on_a_wall(self):
        hint = decal_core.upright_hint((0, -1, 0))  # the front wall
        x, y, z = decal_core.frame_axes((0, -1, 0), hint)
        self.assertAlmostEqual(x[0], 1.0)  # reads left to right seen from the front
        self.assertAlmostEqual(y[2], 1.0)  # its up is the design's up
        self.assertEqual(decal_core.upright_hint((0, 0, 1)), (1.0, 0.0, 0.0))

    def test_placed_centre_corners_flips(self):
        self.assertEqual(decal_core.placed(0, 0, self.OPTS), (0.5, 0.5))
        self.assertEqual(decal_core.placed(10, 5, self.OPTS), (1.0, 1.0))
        self.assertEqual(decal_core.placed(-10, -5, self.OPTS), (0.0, 0.0))
        moved = dict(self.OPTS, dx=10)
        self.assertEqual(decal_core.placed(10, 0, moved), (0.5, 0.5))
        flipped = dict(self.OPTS, flip_h=True, flip_v=True)
        self.assertEqual(decal_core.placed(10, 5, flipped), (0.0, 0.0))
        scaled = dict(self.OPTS, scale_x=2.0, scale_y=2.0)
        self.assertEqual(decal_core.placed(20, 10, scaled), (1.0, 1.0))

    def test_placed_turned(self):
        turned = dict(self.OPTS, angle=90.0)
        u, v = decal_core.placed(0, 10, turned)  # 10 mm up = the picture's right edge
        self.assertAlmostEqual(u, 1.0)
        self.assertAlmostEqual(v, 0.5)

    def test_cylinder_unrolled(self):
        r = 10.0
        origin = (0.0, -r, 5.0)
        quarter = (r, 0.0, 8.0)  # a quarter turn on, 3 mm higher
        u, v = decal_core.cylinder_coords(quarter, origin, (0, 0, 0), (0, 0, 1), r)
        self.assertAlmostEqual(u, r * math.pi / 2)
        self.assertAlmostEqual(v, 3.0)
        u, v = decal_core.cylinder_coords((-r, 0.0, 5.0), origin, (0, 0, 0), (0, 0, 1), r)
        self.assertAlmostEqual(u, -r * math.pi / 2)

    def test_clip_to_the_picture(self):
        square = [(-0.5, 0.25), (1.5, 0.25), (1.5, 0.75), (-0.5, 0.75)]
        cut = decal_core.clip(square)
        us = sorted(p[0] for p in cut)
        self.assertAlmostEqual(us[0], 0.0)
        self.assertAlmostEqual(us[-1], 1.0)
        self.assertEqual(decal_core.clip([(2, 2), (3, 2), (3, 3)]), [])
        inside = [(0.2, 0.2, 7.0), (0.8, 0.2, 7.0), (0.5, 0.8, 7.0)]
        self.assertEqual(decal_core.clip(inside), inside)

    def test_clip_interpolates_every_entry(self):
        line = [(-1.0, 0.5, 0.0), (1.0, 0.5, 10.0), (1.0, 0.6, 10.0)]
        cut = decal_core.clip(line)
        at_zero = [p for p in cut if abs(p[0]) < 1e-12]
        self.assertTrue(at_zero)
        self.assertAlmostEqual(at_zero[0][2], 5.0)

    def test_cover_flat_square(self):
        points = [(0, 0, 0), (40, 0, 0), (40, 30, 0), (0, 30, 0)]
        triangles = [(0, 1, 2), (0, 2, 3)]
        opts = {"width": 10.0, "height": 10.0, "dx": 20.0, "dy": 15.0}

        def uv(p):
            return decal_core.placed(p[0], p[1], opts)

        pts, uvs, normals, tris = decal_core.cover(points, triangles, uv)
        self.assertAlmostEqual(decal_core.area(pts, tris), 100.0)
        self.assertTrue(all(-1e-9 <= u <= 1 + 1e-9 and -1e-9 <= v <= 1 + 1e-9 for u, v in uvs))
        self.assertTrue(all(abs(n[2]) > 0.99 for n in normals))
        lifted = decal_core.lifted(pts, normals, 0.1)
        self.assertTrue(all(abs(abs(p[2]) - 0.1) < 1e-12 for p in lifted))

    def test_cover_skips_far_triangles(self):
        points = [(100, 100, 0), (110, 100, 0), (110, 110, 0)]
        opts = {"width": 10.0, "height": 10.0}
        result = decal_core.cover(
            points, [(0, 1, 2)], lambda p: decal_core.placed(p[0], p[1], opts)
        )
        self.assertEqual(result, ([], [], [], []))

    def test_default_and_texture_sizes(self):
        self.assertEqual(decal_core.default_size((80, 40), 30.0), (24.0, 12.0))
        self.assertEqual(decal_core.default_size((40, 80), 30.0), (12.0, 24.0))
        self.assertEqual(decal_core.default_size((100, 100), 0), (50.0, 50.0))
        with self.assertRaises(ValueError):
            decal_core.default_size((0, 10), 30.0)
        self.assertEqual(decal_core.texture_size((4000, 2000)), (1024, 512))
        self.assertEqual(decal_core.texture_size((300, 200)), (300, 200))


class PrefsCore(unittest.TestCase):
    def test_pages_in_fusion_order(self):
        titles = [title for _pid, title, _parent in prefs_core.pages()]
        self.assertEqual(titles[0], "General")
        self.assertIn("Unit and Value Display", titles)
        self.assertIn("Network", titles)
        for pid, _title, parent in prefs_core.pages():
            if parent:
                self.assertIn(parent, [p for p, _t, _x in prefs_core.pages()])

    def test_every_option_is_on_a_page_and_greyed_ones_say_why(self):
        pages = {pid for pid, _t, _p in prefs_core.pages()}
        for opt in prefs_core.options():
            self.assertIn(opt["page"], pages, opt["key"])
            if not opt["available"]:
                self.assertTrue(opt["why"], opt["key"])
                self.assertIsNone(opt["store"], opt["key"])
            for value, label, available, why in opt["choices"]:
                if not available:
                    self.assertTrue(why, (opt["key"], label))

    def test_options_by_key(self):
        self.assertEqual(prefs_core.option("reverse_zoom")["kind"], "bool")
        with self.assertRaises(prefs_core.PrefError):
            prefs_core.option("nope")

    def test_normalise(self):
        self.assertEqual(prefs_core.normalise("recovery_minutes", "500"), 120)
        self.assertEqual(prefs_core.normalise("recovery_minutes", 0), 1)
        with self.assertRaises(prefs_core.PrefError):
            prefs_core.normalise("recovery_minutes", "soon")
        self.assertEqual(prefs_core.normalise("mouse_preset", "solidworks"), "solidworks")
        with self.assertRaises(prefs_core.PrefError):
            prefs_core.normalise("mouse_preset", "inventor")  # greyed: SciForge cannot
        with self.assertRaises(prefs_core.PrefError):
            prefs_core.normalise("mouse_preset", "blender")
        self.assertIs(prefs_core.normalise("reverse_zoom", 1), True)
        self.assertEqual(prefs_core.normalise("proxy_host", "  host  "), "host")

    def test_mouse_and_zoom_map_to_freecad(self):
        self.assertEqual(prefs_core.mouse_style("fusion"), "Gui::RevitNavigationStyle")
        self.assertEqual(prefs_core.mouse_style("solidworks"), "Gui::SolidWorksNavigationStyle")
        self.assertEqual(prefs_core.mouse_style("inventor"), "Gui::RevitNavigationStyle")
        self.assertTrue(prefs_core.invert_zoom(False))
        self.assertFalse(prefs_core.invert_zoom(True))

    def test_units(self):
        self.assertEqual(prefs_core.unit_label(3), "Inch")
        self.assertIsNone(prefs_core.unit_label(42))

    def test_writes(self):
        self.assertEqual(
            prefs_core.writes("default_units", 3),
            [(prefs_core.UNITS, "Int", "UserSchema", 3)],
        )
        proxy = prefs_core.writes("proxy", "none")
        self.assertEqual(proxy[0], (prefs_core.ADDONS, "String", "proxy_type", "none"))
        self.assertEqual(proxy[1][2], "proxy_settings_migrated_2025")
        self.assertEqual(prefs_core.writes("version_on_close", True), [])
        self.assertEqual(prefs_core.writes("decimals", None)[0][3], None)

    def test_restore_plan_and_groups(self):
        plan = dict(prefs_core.restore_plan())
        self.assertEqual(plan["mouse_preset"], "fusion")
        self.assertIs(plan["reverse_zoom"], False)
        self.assertIs(plan["capture_history"], True)
        self.assertNotIn("version_on_close", plan)
        groups = [g for g, _opts in prefs_core.groups("general")]
        self.assertEqual(groups, ["Language", "Navigation", "Saving and Recovery"])
        self.assertEqual(prefs_core.changed({"a": 1, "b": 2}, {"a": 1, "b": 3}), ["b"])


class ScriptsCore(unittest.TestCase):
    def test_lists_scripts_and_addins(self):
        with tempfile.TemporaryDirectory() as folder:
            for name in ("b.FCMacro", "A.py", "notes.txt", ".hidden.py"):
                open(os.path.join(folder, name), "w").close()
            os.makedirs(os.path.join(folder, "Greeter"))
            open(os.path.join(folder, "Greeter", "Greeter.py"), "w").close()
            os.makedirs(os.path.join(folder, "Broken"))  # no Broken.py inside
            scripts = scripts_core.list_scripts(folder)
            self.assertEqual([e["name"] for e in scripts], ["A", "b"])
            addins = scripts_core.list_addins(folder)
            self.assertEqual([e["name"] for e in addins], ["Greeter"])
            self.assertTrue(addins[0]["main"].endswith(os.path.join("Greeter", "Greeter.py")))
        self.assertEqual(scripts_core.list_scripts("/no/such/folder"), [])

    def test_names(self):
        self.assertEqual(scripts_core.check_name(" My Script ", "script"), "My Script")
        self.assertEqual(scripts_core.check_name("Greeter_2", "addin"), "Greeter_2")
        for bad, kind in (
            ("", "script"),
            ("1st", "script"),
            ("a/b", "script"),
            ("My Addin", "addin"),
            ("x" * 61, "script"),
        ):
            with self.assertRaises(scripts_core.ScriptError):
                scripts_core.check_name(bad, kind)
        with self.assertRaises(scripts_core.ScriptError):
            scripts_core.check_name("greeter", "addin", taken=["Greeter"])

    def test_templates_are_python(self):
        for text in (
            scripts_core.script_template("Box", "Makes a box"),
            scripts_core.addin_template("Greeter", "Says hello\nTwice"),
        ):
            compile(text, "template", "exec")
        self.assertIn("def run(context)", scripts_core.addin_template("G"))
        self.assertIn("def stop(context)", scripts_core.addin_template("G"))
        self.assertIn("# Twice", scripts_core.addin_template("G", "Hi\nTwice"))

    def test_new_file_layout(self):
        path, folder = scripts_core.new_file("addin", "/a", "Greeter")
        self.assertEqual(path, os.path.join("/a", "Greeter", "Greeter.py"))
        self.assertEqual(folder, os.path.join("/a", "Greeter"))
        self.assertEqual(
            scripts_core.new_file("script", "/a", "Box"), (os.path.join("/a", "Box.FCMacro"), None)
        )

    def test_startup_list(self):
        keys = scripts_core.parse_startup("script:Box;addin:Greeter;;junk")
        self.assertEqual(keys, {"script:Box", "addin:Greeter"})
        self.assertEqual(scripts_core.startup_text(keys), "addin:Greeter;script:Box")
        entries = [
            {"kind": "script", "name": "Box"},
            {"kind": "addin", "name": "Greeter"},
            {"kind": "script", "name": "Other"},
        ]
        order = scripts_core.startup_order(entries, keys)
        self.assertEqual([e["name"] for e in order], ["Greeter", "Box"])

    def test_filter_and_errors(self):
        entry = {"name": "Make Gear"}
        self.assertTrue(scripts_core.matches(entry, "gear"))
        self.assertTrue(scripts_core.matches(entry, "ma ge"))
        self.assertFalse(scripts_core.matches(entry, "box"))
        text = "Traceback (most recent call last):\n  File x\nZeroDivisionError: division by zero\n"
        self.assertEqual(scripts_core.short_error(text), "ZeroDivisionError: division by zero")
        self.assertEqual(scripts_core.short_error(""), "unknown error")


class ComputeCore(unittest.TestCase):
    def test_summary(self):
        self.assertEqual(
            compute_core.summary_words(3, 0.25, []), "Compute All: 3 steps in 0.2 s, all computed."
        )
        found = [
            ("F", "Fillet", "error", "x"),
            ("S", "Sketch", "warning", "y"),
            ("T", "Thing", "warning", "z"),
        ]
        words = compute_core.summary_words(1, 1.0, found)
        self.assertEqual(
            words, "Compute All: 1 step in 1.0 s: 1 could not be computed, 2 with warnings."
        )
        self.assertNotIn("error", words.lower())  # the Report view's error filter (tests)
        self.assertEqual(compute_core.counts(found), (1, 2))

    def test_errors_first(self):
        found = [("a", "A", "warning", ""), ("b", "B", "error", ""), ("c", "C", "warning", "")]
        self.assertEqual([f[0] for f in compute_core.ordered(found)], ["b", "a", "c"])


if __name__ == "__main__":
    unittest.main()
