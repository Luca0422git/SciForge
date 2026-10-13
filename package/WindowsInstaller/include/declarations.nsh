/*
declaration.nsh

Configuration and variables of FreeCAD installer
*/

#--------------------------------
# File locations

!define FILES_LICENSE "license.rtf"

#--------------------------------
# Names and version

!define APP_VERSION_NUMBER "${APP_VERSION_MAJOR}.${APP_VERSION_MINOR}.${APP_VERSION_PATCH}.${APP_VERSION_BUILD}"
# For the proposed install folder we use the scheme "FreeCAD x.x"
# however for the Registry, we need the scheme "FreeCAD x.x.x" in order
# to check if it is exactly this version (to support side-by-side installations)
!define APP_SERIES_NAME "${APP_VERSION_MAJOR}.${APP_VERSION_MINOR}"
!define APP_SERIES_KEY "${APP_VERSION_MAJOR}${APP_VERSION_MINOR}${APP_VERSION_PATCH}${APP_VERSION_EMERGENCY}"
!define APP_SERIES_KEY2 "${APP_VERSION_MAJOR}.${APP_VERSION_MINOR}.${APP_VERSION_PATCH}${APP_EMERGENCY_DOT}${APP_VERSION_EMERGENCY}"
# SCIFORGE: SciForge's installer (docs/sciforge/core-patches.md #13). APP_NAME is read from
# the program itself ("ExeName" = SciForge, version.nsh), so every key below is SciForge's
# own: SOFTWARE\SciForge114, Uninstall\SciForge114, the SciForge.Document class and the
# settings folder %APPDATA%\SciForge. A FreeCAD on the same machine is never touched.
!define APP_DIR_REGKEY "Software\Microsoft\Windows\CurrentVersion\App Paths\${APP_NAME}.exe"
!define APP_DIR "${APP_NAME}" # SCIFORGE: "Program Files\SciForge" (FreeCAD: "FreeCAD 1.1")
# Fixme: FC should use different preferences folder for every release
!define APP_DIR_USERDATA ${APP_NAME}
#!define APP_DIR_USERDATA "${APP_NAME}${APP_VERSION_MAJOR}.${APP_VERSION_MINOR}"
!define APP_SHORTCUT_INFO "${APP_NAME} - Parametric CAD with the Fusion workflow" # SCIFORGE
!define APP_INFO "Install/Uninstall ${APP_NAME}"
!define APP_WEBPAGE "https://github.com/Luca0422git/SciForge" # SCIFORGE
!define APP_WEBPAGE_INFO "${APP_NAME} on GitHub" # SCIFORGE
!define APP_WIKI "https://github.com/Luca0422git/SciForge/issues" # SCIFORGE
!define APP_WIKI_INFO "Report a ${APP_NAME} problem" # SCIFORGE
!define APP_COPYRIGHT "${APP_NAME} © 2026 ${APP_NAME} contributors, based on FreeCAD © 2001-${COPYRIGHT_YEAR} by the FreeCAD Team" # SCIFORGE

!define APP_RUN "bin\${APP_NAME}.exe"
!define BIN_FREECAD "${APP_NAME}.exe"
!define BIN_FREECADCMD "${APP_NAME}Cmd.exe" # SCIFORGE: SciForgeCmd.exe keeps its case

!define APP_REGKEY "SOFTWARE\${APP_NAME}${APP_SERIES_KEY}" # like "FreeCAD0180"
!define APP_REGKEY_SETUP "${APP_REGKEY}\Setup"
!define APP_REGKEY_SETTINGS "${APP_REGKEY}\Settings"

!define APP_REGNAME_DOC "${APP_NAME}.Document"

!define APP_EXT ".FCStd"
!define APP_EXT1 ".FCStd1"
!define APP_MIME_TYPE "application/x-zip-compressed"

!define APP_EXT_BAK ".FCBak"
!define APP_EXT_MACRO ".FCMacro"
!define APP_EXT_MAT ".FCMat"
!define APP_EXT_SCRIPT ".FCScript"

!define APP_UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${SETUP_UNINSTALLER_KEY}"

#--------------------------------
# Setup settings

!define SETUP_EXE ${ExeFile}

# SCIFORGE: own icon and pictures, made by tools/sciforge/make_app_icons.py
!define SETUP_ICON "icons\SciForge.ico"
!define SETUP_HEADERIMAGE "graphics\sciforge-header.bmp"
!define SETUP_WIZARDIMAGE "graphics\sciforge-banner.bmp"
!define SETUP_UNINSTALLER "Uninstall-${APP_NAME}.exe"
!define SETUP_UNINSTALLER_KEY "${APP_NAME}${APP_SERIES_KEY}"

#--------------------------------
# Variables that are shared between multiple files

Var APPDATemp
Var AppPre
var AppSubfolder
Var AppSuff
Var CreateDesktopIcon
Var CreateFileAssociations
Var OldVersionNumber
Var OriginalCmdInstDir
Var Pointer
Var RemoveInstDir
Var Search
Var StartmenuFolder
Var String
Var UserList
Var LangName
