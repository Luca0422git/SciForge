# SPDX-License-Identifier: LGPL-2.1-or-later
"""Send to Slicer rules (sciforge/slicer_core.py): finding slicers on Windows, Linux and
macOS, the Send to list, the command line, units and file names. Runs without FreeCAD."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sciforge import slicer_core as core  # noqa: E402


class FakeDisk:
    """A pretend file system: files, folders, and what listdir sees. Windows paths compare
    without case, as Windows does."""

    def __init__(self, files=(), dirs=(), nocase=False):
        self.nocase = nocase
        self.files = {self._k(f) for f in files}
        self.dirs = {self._k(d) for d in dirs}
        self.all = list(files) + list(dirs)

    def _k(self, path):
        return path.lower() if self.nocase else path

    def is_file(self, path):
        return self._k(path) in self.files

    def is_dir(self, path):
        return self._k(path) in self.dirs

    def listdir(self, folder):
        sep = "\\" if self.nocase else "/"
        prefix = self._k(folder.rstrip(sep) + sep)
        names = set()
        for path in self.all:
            if self._k(path).startswith(prefix):
                names.add(path[len(prefix) :].split(sep)[0])
        if not names:
            raise OSError("no such folder")
        return sorted(names)


WIN_ENV = {
    "ProgramFiles": r"C:\Program Files",
    "ProgramW6432": r"C:\Program Files",
    "ProgramFiles(x86)": r"C:\Program Files (x86)",
    "LOCALAPPDATA": r"C:\Users\Luca\AppData\Local",
    "PATH": r"C:\Windows\system32",
}


def find(platform, disk, env, home=None):
    return core.find_slicers(platform, env, disk.is_file, disk.is_dir, disk.listdir, home)


class WindowsDetection(unittest.TestCase):
    def test_all_four_in_program_files(self):
        disk = FakeDisk(
            [
                r"C:\Program Files\Prusa3D\PrusaSlicer\prusa-slicer.exe",
                r"C:\Program Files\Bambu Studio\bambu-studio.exe",
                r"C:\Program Files\OrcaSlicer\orca-slicer.exe",
                r"C:\Program Files\UltiMaker Cura 5.8.1\UltiMaker-Cura.exe",
            ],
            nocase=True,
        )
        found = find("win32", disk, WIN_ENV)
        self.assertEqual(
            [(sid, name) for sid, name, _p in found],
            [
                ("prusaslicer", "PrusaSlicer"),
                ("bambustudio", "Bambu Studio"),
                ("orcaslicer", "OrcaSlicer"),
                ("cura", "UltiMaker Cura"),
            ],
        )
        self.assertEqual(found[1][2], r"C:\Program Files\Bambu Studio\bambu-studio.exe")

    def test_newest_cura_wins(self):
        disk = FakeDisk(
            [
                r"C:\Program Files\UltiMaker Cura 5.10.0\UltiMaker-Cura.exe",
                r"C:\Program Files\UltiMaker Cura 5.8.1\UltiMaker-Cura.exe",
                r"C:\Program Files\UltiMaker Cura 5.9.0\UltiMaker-Cura.exe",
            ],
            nocase=True,
        )
        found = find("win32", disk, WIN_ENV)
        self.assertEqual(found, [("cura", "UltiMaker Cura", disk.all[0])])

    def test_old_cura_and_case_differences(self):
        disk = FakeDisk([r"C:\Program Files\Ultimaker Cura 4.13.1\Cura.exe"], nocase=True)
        self.assertEqual(find("win32", disk, WIN_ENV)[0][0], "cura")

    def test_program_files_x86_and_per_user_installs(self):
        disk = FakeDisk(
            [
                r"C:\Program Files (x86)\Prusa3D\PrusaSlicer\prusa-slicer.exe",
                r"C:\Users\Luca\AppData\Local\Programs\OrcaSlicer\orca-slicer.exe",
            ],
            nocase=True,
        )
        self.assertEqual(
            [sid for sid, _n, _p in find("win32", disk, WIN_ENV)], ["prusaslicer", "orcaslicer"]
        )

    def test_upper_case_environment_names(self):
        # dict(os.environ) on Windows gives the names in capitals
        disk = FakeDisk([r"D:\Apps (x86)\OrcaSlicer\orca-slicer.exe"], nocase=True)
        env = {"PROGRAMFILES(X86)": r"D:\Apps (x86)", "PROGRAMFILES": r"D:\Apps"}
        self.assertEqual(find("win32", disk, env)[0][0], "orcaslicer")

    def test_nothing_installed(self):
        self.assertEqual(find("win32", FakeDisk([], nocase=True), WIN_ENV), [])

    def test_no_environment_falls_back_to_c_drive(self):
        disk = FakeDisk([r"C:\Program Files\Bambu Studio\bambu-studio.exe"], nocase=True)
        self.assertEqual(find("win32", disk, {})[0][0], "bambustudio")


class LinuxDetection(unittest.TestCase):
    HOME = "/home/luca"

    def test_path_programs(self):
        disk = FakeDisk(["/usr/bin/prusa-slicer", "/home/luca/.local/bin/orca-slicer"])
        env = {"PATH": "/home/luca/.local/bin:/usr/bin"}
        found = find("linux", disk, env, self.HOME)
        self.assertEqual(
            found,
            [
                ("prusaslicer", "PrusaSlicer", "/usr/bin/prusa-slicer"),
                ("orcaslicer", "OrcaSlicer", "/home/luca/.local/bin/orca-slicer"),
            ],
        )

    def test_flatpak(self):
        disk = FakeDisk(
            [
                "/var/lib/flatpak/exports/bin/com.bambulab.BambuStudio",
                "/home/luca/.local/share/flatpak/exports/bin/com.ultimaker.cura",
            ]
        )
        found = find("linux", disk, {"PATH": "/usr/bin"}, self.HOME)
        self.assertEqual([sid for sid, _n, _p in found], ["bambustudio", "cura"])

    def test_appimage_in_applications_newest_first(self):
        disk = FakeDisk(
            [
                "/home/luca/Applications/PrusaSlicer-2.8.1+linux-x64.AppImage",
                "/home/luca/Applications/PrusaSlicer-2.9.0+linux-x64.AppImage",
                "/home/luca/Applications/notes.txt",
            ]
        )
        found = find("linux", disk, {"PATH": ""}, self.HOME)
        self.assertEqual(found[0][2], "/home/luca/Applications/PrusaSlicer-2.9.0+linux-x64.AppImage")

    def test_path_first(self):
        disk = FakeDisk(
            ["/usr/bin/bambu-studio", "/var/lib/flatpak/exports/bin/com.bambulab.BambuStudio"]
        )
        found = find("linux", disk, {"PATH": "/usr/bin"}, self.HOME)
        self.assertEqual(found, [("bambustudio", "Bambu Studio", "/usr/bin/bambu-studio")])

    def test_nothing(self):
        self.assertEqual(find("linux", FakeDisk([]), {"PATH": "/usr/bin"}, self.HOME), [])


class MacDetection(unittest.TestCase):
    def test_app_bundles(self):
        disk = FakeDisk(dirs=["/Applications/OrcaSlicer.app", "/Users/l/Applications/UltiMaker Cura.app"])
        found = find("darwin", disk, {"PATH": "/usr/bin"}, "/Users/l")
        self.assertEqual(
            found,
            [
                ("orcaslicer", "OrcaSlicer", "/Applications/OrcaSlicer.app"),
                ("cura", "UltiMaker Cura", "/Users/l/Applications/UltiMaker Cura.app"),
            ],
        )


class SendToList(unittest.TestCase):
    FOUND = [("prusaslicer", "PrusaSlicer", "/p"), ("cura", "UltiMaker Cura", "/c")]

    def test_entries(self):
        self.assertEqual(
            core.send_to_entries(self.FOUND),
            [
                ("prusaslicer", "PrusaSlicer"),
                ("cura", "UltiMaker Cura"),
                (core.OTHER, "Other... (pick the program)"),
                (core.FILE_ONLY, "Save file only"),
            ],
        )
        self.assertEqual(
            core.send_to_entries([]),
            [(core.OTHER, core.OTHER_LABEL), (core.FILE_ONLY, core.FILE_ONLY_LABEL)],
        )

    def test_default_target(self):
        self.assertEqual(core.default_target(self.FOUND), "prusaslicer")
        self.assertEqual(core.default_target(self.FOUND, "cura"), "cura")
        self.assertEqual(core.default_target(self.FOUND, core.FILE_ONLY), core.FILE_ONLY)
        # remembered slicer uninstalled since: the first one found
        self.assertEqual(core.default_target(self.FOUND, "orcaslicer"), "prusaslicer")
        # Other... remembered, but its program forgotten: the first one found
        self.assertEqual(core.default_target(self.FOUND, core.OTHER, ""), "prusaslicer")
        self.assertEqual(core.default_target(self.FOUND, core.OTHER, "/x"), core.OTHER)
        self.assertEqual(core.default_target([], "", "/x"), core.OTHER)
        self.assertEqual(core.default_target([]), core.FILE_ONLY)

    def test_program_for(self):
        self.assertEqual(core.program_for("cura", self.FOUND), "/c")
        self.assertEqual(core.program_for(core.OTHER, self.FOUND, " /x "), "/x")
        self.assertEqual(core.program_for(core.FILE_ONLY, self.FOUND, "/x"), "")
        self.assertEqual(core.program_for("orcaslicer", self.FOUND), "")

    def test_slicer_name(self):
        self.assertEqual(core.slicer_name("cura", self.FOUND), "UltiMaker Cura")
        self.assertEqual(
            core.slicer_name(core.OTHER, [], r"C:\Tools\SuperSlicer\superslicer.exe"),
            "superslicer",
        )
        self.assertEqual(core.slicer_name(core.OTHER, [], "/opt/fake_slicer.sh"), "fake_slicer")
        self.assertEqual(core.slicer_name(core.OTHER, []), "your slicer")

    def test_check_program(self):
        disk = FakeDisk(["/usr/bin/x"], ["/Applications/A.app"])
        self.assertEqual(core.check_program("/usr/bin/x", disk.is_file), "")
        self.assertEqual(core.check_program("/Applications/A.app", disk.is_file, disk.is_dir), "")
        self.assertEqual(core.check_program("  ", disk.is_file), core.NO_PROGRAM)
        self.assertIn("not found", core.check_program("/nope", disk.is_file))


class Launch(unittest.TestCase):
    def test_plain_program_gets_the_file(self):
        self.assertEqual(
            core.launch_command("/usr/bin/prusa-slicer", ["/t/a.3mf"], "linux"),
            ("/usr/bin/prusa-slicer", ["/t/a.3mf"]),
        )
        exe = r"C:\Program Files\Bambu Studio\bambu-studio.exe"
        self.assertEqual(
            core.launch_command(exe, [r"C:\t\a b.3mf"], "win32"), (exe, [r"C:\t\a b.3mf"])
        )

    def test_windows_shortcut_and_batch(self):
        self.assertEqual(
            core.launch_command(r"C:\Desk\Cura.lnk", [r"C:\t\a.stl"], "win32"),
            ("cmd", ["/c", "start", "", r"C:\Desk\Cura.lnk", r"C:\t\a.stl"]),
        )
        self.assertEqual(core.launch_command(r"C:\x.BAT", ["f"], "win32")[0], "cmd")
        # a .lnk means nothing special on Linux
        self.assertEqual(core.launch_command("/x.lnk", ["f"], "linux"), ("/x.lnk", ["f"]))

    def test_mac_app(self):
        self.assertEqual(
            core.launch_command("/Applications/OrcaSlicer.app", ["/t/a.3mf"], "darwin"),
            ("open", ["-a", "/Applications/OrcaSlicer.app", "/t/a.3mf"]),
        )

    def test_no_program(self):
        with self.assertRaises(ValueError):
            core.launch_command("", ["f"], "linux")


class FilesAndUnits(unittest.TestCase):
    def test_slicers_get_millimetres(self):
        self.assertEqual(core.send_unit("Inch", True), "Millimeter")
        self.assertEqual(core.send_unit("Inch", False), "Inch")

    def test_print_name(self):
        self.assertEqual(core.print_name("Pi5 Case", ["Lid"]), "Lid")
        self.assertEqual(core.print_name("Pi5 Case", ["Lid", "Base"]), "Pi5 Case")
        self.assertEqual(core.print_name("a/b:c", []), "a_b_c")
        self.assertEqual(core.print_name("", []), "part")

    def test_free_path_never_overwrites(self):
        taken = {"/d/Case.3mf", "/d/Case-2.3mf"}
        self.assertEqual(core.free_path("/d/Lid.3mf", taken.__contains__), "/d/Lid.3mf")
        self.assertEqual(core.free_path("/d/Case.3mf", taken.__contains__), "/d/Case-3.3mf")
        self.assertEqual(
            core.free_path(r"C:\my.designs\Case.3mf", {r"C:\my.designs\Case.3mf"}.__contains__),
            r"C:\my.designs\Case-2.3mf",
        )

    def test_copy_folder(self):
        self.assertEqual(core.copy_folder("/d/Case.FCStd", "/home"), "/d")
        self.assertEqual(core.copy_folder(r"C:\Users\L\Case.FCStd", "x"), r"C:\Users\L")
        self.assertEqual(core.copy_folder("", "/home/l"), "/home/l")

    def test_stale_files(self):
        now = 100 * 86400.0
        entries = [("old.3mf", now - 8 * 86400), ("new.3mf", now - 3600)]
        self.assertEqual(core.stale_files(entries, now), ["old.3mf"])

    def test_platform_key(self):
        self.assertEqual(core.platform_key("win32"), "win")
        self.assertEqual(core.platform_key("darwin"), "mac")
        self.assertEqual(core.platform_key("linux"), "linux")


class Preferences(unittest.TestCase):
    def test_print_page_and_options(self):
        from sciforge import export, prefs_core

        self.assertIn(("print", "3D Print", None), prefs_core.pages())
        self.assertEqual(prefs_core.PRINT_FORMATS, export.PRINT_FORMATS)
        send_to = prefs_core.option("print_send_to")
        values = prefs_core.choice_values(send_to)
        self.assertEqual(values[0], "")  # the first slicer found
        self.assertEqual(values[1:-2], [e["id"] for e in core.SLICERS])
        self.assertEqual(values[-2:], [core.OTHER, core.FILE_ONLY])
        # the dialog and the page keep the same parameters
        self.assertEqual(prefs_core.option("slicer_program")["store"][2], "SlicerProgram")
        self.assertEqual(prefs_core.option("slicer_program")["store"][0], export.PREF_PATH)
        self.assertEqual(prefs_core.option("print_format")["default"], "3MF")


if __name__ == "__main__":
    unittest.main()
