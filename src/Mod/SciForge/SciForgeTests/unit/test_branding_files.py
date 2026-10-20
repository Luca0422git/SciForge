# SPDX-License-Identifier: LGPL-2.1-or-later
"""The branding pass (an app called SciForge, installed next to FreeCAD) keeps several files
in step: the names in src/Main/SciForgeBranding.h and the CMake variables, the pictures the
C++ asks for and the Qt resource list, the installer's icon and pictures, the program names
the packaging scripts expect. A full build takes hours and only then would show a missing
picture or a wrong name, so these checks run on every push instead.

They read the repository and are skipped in an installed copy of the module.
"""

import os
import re
import struct
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
HEADER = os.path.join(REPO, "src", "Main", "SciForgeBranding.h")


def _read(*parts):
    with open(os.path.join(REPO, *parts), "r", encoding="utf-8-sig") as handle:
        return handle.read()


def _define(text, name):
    match = re.search(r'#define\s+%s\s+"([^"]*)"' % re.escape(name), text)
    return match.group(1) if match else None


def _cmake_set(text, name):
    match = re.search(r'set\(%s\s+"([^"]*)"\)' % re.escape(name), text)
    return match.group(1) if match else None


def _png_size(path):
    with open(path, "rb") as handle:
        head = handle.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", head[16:24])


def _ico_sizes(path):
    with open(path, "rb") as handle:
        data = handle.read()
    reserved, kind, count = struct.unpack("<HHH", data[:6])
    if reserved != 0 or kind != 1:
        return []
    sizes = []
    for i in range(count):
        entry = data[6 + 16 * i : 6 + 16 * (i + 1)]
        sizes.append((entry[0] or 256, entry[1] or 256))
    return sizes


def _bmp_size(path):
    with open(path, "rb") as handle:
        head = handle.read(30)
    if head[:2] != b"BM":
        return None
    width, height = struct.unpack("<ii", head[18:26])
    bits = struct.unpack("<H", head[28:30])[0]
    return width, abs(height), bits


@unittest.skipUnless(os.path.isfile(HEADER), "needs the repository (not an installed copy)")
class BrandingFilesTest(unittest.TestCase):
    def setUp(self):
        self.header = _read("src", "Main", "SciForgeBranding.h")
        self.cmake = _read("cMake", "FreeCAD_Helpers", "InitializeFreeCADBuildOptions.cmake")

    def test_names_agree_between_cpp_and_cmake(self):
        self.assertEqual(_define(self.header, "SCIFORGE_EXE_NAME"), "SciForge")
        self.assertEqual(_cmake_set(self.cmake, "SCIFORGE_APP_NAME"), "SciForge")
        desktop_id = _define(self.header, "SCIFORGE_DESKTOP_ID")
        self.assertEqual(desktop_id, _cmake_set(self.cmake, "SCIFORGE_DESKTOP_ID"))
        self.assertEqual(
            _define(self.header, "SCIFORGE_URL"), _cmake_set(self.cmake, "SCIFORGE_URL")
        )
        # The Linux desktop entry, AppStream data and MIME package carry that id.
        for name in (".desktop", ".metainfo.xml.in", ".xml"):
            self.assertTrue(
                os.path.isfile(os.path.join(REPO, "src", "XDGData", desktop_id + name)), name
            )
        self.assertIn(
            "<id>%s</id>" % desktop_id, _read("src", "XDGData", desktop_id + ".metainfo.xml.in")
        )
        desktop = _read("src", "XDGData", desktop_id + ".desktop")
        self.assertIn("Icon=%s\n" % desktop_id, desktop)
        self.assertIn("Exec=sciforge ", desktop)
        self.assertIn("StartupWMClass=SciForge", desktop)
        self.assertIn(
            desktop_id + ".desktop", _read("package", "rattler-build", "linux", "create_bundle.sh")
        )

    def test_main_programs_use_the_header(self):
        for name in ("MainGui.cpp", "MainCmd.cpp", "MainPy.cpp"):
            text = _read("src", "Main", name)
            self.assertIn('#include "SciForgeBranding.h"', text, name)
            self.assertIn('Config()["ExeName"] = SCIFORGE_EXE_NAME', text, name)
            self.assertNotIn('Config()["ExeName"] = "FreeCAD"', text, name)
        gui = _read("src", "Main", "MainGui.cpp")
        for key, macro in (
            ("AppIcon", "SCIFORGE_APP_ICON"),
            ("SplashScreen", "SCIFORGE_SPLASH"),
            ("AboutImage", "SCIFORGE_ABOUT_IMAGE"),
            ("StartWorkbench", "SCIFORGE_START_WORKBENCH"),
            ("DesktopFileName", "SCIFORGE_DESKTOP_ID"),
        ):
            self.assertIn('Config()["%s"] = %s;' % (key, macro), gui, key)
        self.assertEqual(_define(self.header, "SCIFORGE_START_WORKBENCH"), "SciForgeWorkbench")

    def test_one_version_file_feeds_cmake_the_programs_and_the_installer(self):
        version = _read("src", "Mod", "SciForge", "VERSION").strip()
        self.assertRegex(version, r"^\d+\.\d+\.\d+(-[0-9A-Za-z.]+)?$")
        # CMake reads the file (not a copy of the number) and hands it to src/Main
        self.assertIn("src/Mod/SciForge/VERSION", self.cmake)
        main = _read("src", "Main", "CMakeLists.txt")
        self.assertIn('SCIFORGE_VERSION="${SCIFORGE_VERSION}"', main)
        self.assertIn("#error", self.header)  # no silent fallback number
        for name in ("MainGui.cpp", "MainCmd.cpp", "MainPy.cpp"):
            self.assertIn(
                'Config()["SciForgeVersion"] = SCIFORGE_VERSION;', _read("src", "Main", name), name
            )
        # the splash paints it, About names it next to FreeCAD's, the exe's resource carries it
        self.assertIn(
            'Config()["SplashInfoVersion"] = SCIFORGE_VERSION;', _read("src", "Main", "MainGui.cpp")
        )
        self.assertIn("based on FreeCAD", _read("src", "Gui", "Dialogs", "DlgAbout.cpp"))
        for name in ("freecad.rc.cmake", "freecadCmd.rc.cmake"):
            rc = _read("src", "Main", name)
            self.assertIn('"ProductVersion", "${SCIFORGE_VERSION}"', rc, name)
            self.assertIn("FILEVERSION ${SCIFORGE_VERSION_MAJOR}", rc, name)
        # the installer shows SciForge's version, not FreeCAD's
        nsh = _read("package", "WindowsInstaller", "write_version_nsh.py")
        self.assertIn('ConfigGet("SciForgeVersion")', nsh)
        self.assertIn("APP_VERSION_DISPLAY", nsh)
        self.assertIn(
            '!define APP_VERSION "${APP_VERSION_DISPLAY}"',
            _read("package", "WindowsInstaller", "Settings.nsh"),
        )
        # and the module's CMake installs the file next to the package
        self.assertRegex(_read("src", "Mod", "SciForge", "CMakeLists.txt"), r"Init\.py\s+InitGui\.py\s+VERSION")

    def test_pictures_exist_and_are_qt_resources(self):
        qrc = _read("src", "Gui", "Icons", "resource.qrc")
        icons = os.path.join(REPO, "src", "Gui", "Icons")
        wanted = {
            _define(self.header, "SCIFORGE_APP_ICON") + ".svg": None,
            _define(self.header, "SCIFORGE_SPLASH") + ".png": (568, 368),
            _define(self.header, "SCIFORGE_SPLASH") + "_2x.png": (1136, 736),
            _define(self.header, "SCIFORGE_ABOUT_IMAGE") + ".png": (552, 189),
        }
        for name, size in wanted.items():
            path = os.path.join(icons, name)
            self.assertTrue(os.path.isfile(path), name)
            self.assertIn("<file>%s</file>" % name, qrc, name)
            if size:
                self.assertEqual(_png_size(path), size, name)
        # The splash leaves its version spot where the C++ puts the number.
        self.assertEqual(_define(self.header, "SCIFORGE_SPLASH_INFO_POSITION"), "190,189")
        generator = _read("tools", "sciforge", "make_app_icons.py")
        self.assertIn("SPLASH_TEXT_X, SPLASH_INFO_Y = 190, 189", generator)
        self.assertIn('Config()["SplashInfoExeName"] = ""', _read("src", "Main", "MainGui.cpp"))

    def test_linux_icons_match_the_install_rules(self):
        cmake = _read("src", "Gui", "CMakeLists.txt")
        match = re.search(r"foreach\(size ([0-9 ]+)\)", cmake)
        self.assertIsNotNone(match, "no foreach(size ...) for the SciForge icons")
        sizes = [int(s) for s in match.group(1).split()]
        self.assertIn(16, sizes)
        self.assertIn(256, sizes)
        for size in sizes:
            path = os.path.join(REPO, "src", "Gui", "Icons", "sciforge-icon-%d.png" % size)
            self.assertEqual(_png_size(path), (size, size), path)
        self.assertIn("sciforgeapp.svg", cmake)
        self.assertIn("${SCIFORGE_DESKTOP_ID}.svg", cmake)

    def test_windows_icon_and_program_names(self):
        ico = os.path.join(REPO, "src", "Main", "sciforge.ico")
        sizes = _ico_sizes(ico)
        for size in (16, 32, 48, 256):
            self.assertIn((size, size), sizes, "%s lacks %d px" % (ico, size))
        cmake = _read("src", "Main", "CMakeLists.txt")
        self.assertIn('set(SCIFORGE_WIN_ICON "sciforge.ico")', cmake)
        self.assertIn("SET_BIN_DIR(FreeCADMain ${SCIFORGE_APP_NAME})", cmake)
        self.assertIn("SET_BIN_DIR(FreeCADMainCmd ${SCIFORGE_APP_NAME}Cmd)", cmake)
        for name in ("freecad.rc.cmake", "freecadCmd.rc.cmake"):
            text = _read("src", "Main", name)
            self.assertIn('"${SCIFORGE_WIN_ICON}"', text, name)
            self.assertNotIn('"icon.ico"', text, name)
            self.assertIn('"ProductName", "${SCIFORGE_APP_NAME}"', text, name)

    def test_packaging_scripts_expect_the_new_names(self):
        windows = _read("package", "rattler-build", "windows", "create_bundle.sh")
        self.assertIn("bin/SciForgeCmd.exe", windows)
        self.assertIn("Library/bin/SciForge*.exe", windows)
        self.assertNotIn("Library/bin/freecad*", windows)
        self.assertIn('version_name="SciForge_', windows)
        linux = _read("package", "rattler-build", "linux", "create_bundle.sh")
        self.assertIn("bin_tmp/sciforgecmd", linux)
        self.assertIn('version_name="SciForge_', linux)
        apprun = _read("package", "rattler-build", "linux", "AppDir", "AppRun")
        self.assertIn('MAIN="$HERE/usr/bin/sciforge"', apprun)
        self.assertIn("freecadcmd)", apprun)  # the old name still works for the test runner
        self.assertIn(
            "bin/SciForge ${PREFIX}/bin/sciforge", _read("package", "rattler-build", "build.sh")
        )
        self.assertNotIn("ren %LIBRARY_PREFIX%", _read("package", "rattler-build", "build.bat"))
        tests = _read("tools", "sciforge", "run_tests.sh")
        self.assertIn("sciforgecmd", tests)
        self.assertIn("SciForgeCmd.exe", _read("tools", "sciforge", "windows_golden.sh"))

    def test_installer_pictures_and_strings(self):
        folder = os.path.join(REPO, "package", "WindowsInstaller")
        declarations = _read("package", "WindowsInstaller", "include", "declarations.nsh")
        for key, size in (
            ("SETUP_ICON", None),
            ("SETUP_HEADERIMAGE", (150, 57, 24)),
            ("SETUP_WIZARDIMAGE", (164, 314, 24)),
        ):
            match = re.search(r'!define %s "([^"]+)"' % key, declarations)
            self.assertIsNotNone(match, key)
            path = os.path.join(folder, *match.group(1).split("\\"))
            self.assertTrue(os.path.isfile(path), path)
            if size:
                self.assertEqual(_bmp_size(path), size, path)
            else:
                self.assertIn((256, 256), _ico_sizes(path))
        self.assertIn('!define APP_DIR "${APP_NAME}"', declarations)
        self.assertIn("SciForgeCmd.exe", _read("package", "WindowsInstaller", "Settings.nsh"))
        self.assertIn(
            'Section /o "$(SecFileAssocTitle)"',
            _read("package", "WindowsInstaller", "include", "init.nsh"),
        )
        for name in ("install.nsh", "configure.nsh", "uninstall.nsh"):
            self.assertNotIn(
                "FCStdThumbnail.dll $SYSDIR", _read("package", "WindowsInstaller", "setup", name)
            )
        english = _read("package", "WindowsInstaller", "lang", "english.nsh")
        self.assertIn('FinishPageRun "Launch ${APP_NAME}"', english)
        self.assertIn('UnInstallRunning "You must close ${APP_NAME} first!"', english)
        languages = _read("package", "WindowsInstaller", "lang", "TranslatedLanguages.nsh")
        self.assertIn('!insertmacro LANG "english"', languages)

    def test_build_workflow_ships_the_installer(self):
        workflow = _read(".github", "workflows", "sciforge-build.yml")
        self.assertIn('MAKE_INSTALLER: "true"', workflow)
        self.assertIn("SciForge-Windows-installer-", workflow)
        self.assertIn("*-installer.exe", workflow)


if __name__ == "__main__":
    unittest.main()
