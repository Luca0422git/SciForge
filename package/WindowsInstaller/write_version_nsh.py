# SPDX-License-Identifier: LGPL-2.1-or-later
#
# this script is meant to be called by nsis installer scripts, it gets version information
# from freecad and writes version.nsh file in the directory the script is located at
import FreeCAD
import datetime
import os

filepath=os.path.join(os.path.dirname(os.path.abspath(__file__)),"version.nsh")
v=FreeCAD.Version()
# SCIFORGE: the installer shows SciForge's own version (src/Mod/SciForge/VERSION, "0.1.0-beta"),
# not FreeCAD's (core-patches.md #15). FreeCAD's numbers stay in APP_FREECAD_VERSION.
sv=FreeCAD.ConfigGet("SciForgeVersion") or "{}.{}.{}".format(v[0], v[1], v[2])
sv_numbers=(sv.split("-")[0].split(".") + ["0", "0", "0"])[:3]
content=f'''\
!define COPYRIGHT_YEAR {datetime.date.today().year}
!define APP_VERSION_MAJOR "{sv_numbers[0]}"
!define APP_VERSION_MINOR "{sv_numbers[1]}"
!define APP_VERSION_PATCH "{sv_numbers[2]}"
!define APP_VERSION_DISPLAY "{sv}"
!define APP_FREECAD_VERSION "{v[0]}.{v[1]}.{v[2]}"
!define APP_VERSION_REVISION "{v[3].split()[0]}"
!define APP_NAME "{FreeCAD.ConfigGet('ExeName')}"
'''

with open(filepath, "w", encoding="utf-8") as file:
    file.writelines(content)
