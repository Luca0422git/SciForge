// SPDX-License-Identifier: LGPL-2.1-or-later
/***************************************************************************
 *   SCIFORGE: the application's identity.                                 *
 *                                                                         *
 *   SciForge is a fork of FreeCAD (https://freecad.org). The values here  *
 *   make the fork a separate program that installs next to FreeCAD: its   *
 *   own name in every window title and dialog, its own settings folder    *
 *   (%APPDATA%\SciForge on Windows, ~/.config/SciForge and                *
 *   ~/.local/share/SciForge on Linux, derived by App::Application from    *
 *   "ExeName"), its own icon, splash screen and About banner.             *
 *                                                                         *
 *   Used by MainGui.cpp, MainCmd.cpp and MainPy.cpp. The build system     *
 *   keeps the same names in                                               *
 *   cMake/FreeCAD_Helpers/InitializeFreeCADBuildOptions.cmake (program    *
 *   names, Windows version resource, Linux desktop entry); the unit test  *
 *   SciForgeTests/unit/test_branding_files.py checks that they agree.     *
 *   See docs/sciforge/core-patches.md #8.                                 *
 ***************************************************************************/

#ifndef SCIFORGE_BRANDING_H
#define SCIFORGE_BRANDING_H

// SciForge's own version, from src/Mod/SciForge/VERSION through CMake (src/Main/CMakeLists.txt).
// FreeCAD's version numbers stay FreeCAD's: the "based on FreeCAD 1.1.4" in Help > About.
#ifndef SCIFORGE_VERSION
#error "SCIFORGE_VERSION is set by src/Main/CMakeLists.txt from src/Mod/SciForge/VERSION"
#endif

#define SCIFORGE_EXE_NAME "SciForge"
#define SCIFORGE_VENDOR "SciForge"
#define SCIFORGE_URL "https://github.com/Luca0422git/SciForge"
#define SCIFORGE_DESKTOP_ID "org.sciforge.SciForge"
#define SCIFORGE_START_WORKBENCH "SciForgeWorkbench"

// Pictures compiled into FreeCADGui's resources (src/Gui/Icons/resource.qrc), generated
// by tools/sciforge/make_app_icons.py. The splash already shows the wordmark; FreeCAD
// only paints the version number on it, at (x + 235, y - 7) of SplashInfoPosition.
#define SCIFORGE_APP_ICON "sciforgeapp"
#define SCIFORGE_SPLASH "sciforgesplash"
#define SCIFORGE_ABOUT_IMAGE "sciforgeabout"
#define SCIFORGE_SPLASH_TEXT_COLOR "#8FD0FF"
#define SCIFORGE_SPLASH_INFO_COLOR "#CFD8E3"
#define SCIFORGE_SPLASH_INFO_POSITION "190,189"

// Console banner; its first line is also shown next to the name in Help > About, so
// FreeCAD's credit stays visible (feature outline 2.5). {} is the copyright year.
#define SCIFORGE_BANNER_FORMAT                                                                 \
    "(C) 2026 SciForge contributors. Based on FreeCAD, (C) 2001-{} FreeCAD contributors.\n"    \
    "SciForge and FreeCAD are free and open-source software under the LGPL-2.1-or-later "      \
    "license.\n\n"

#endif  // SCIFORGE_BRANDING_H
