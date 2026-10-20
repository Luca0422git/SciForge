// SPDX-License-Identifier: LGPL-2.1-or-later
/////////////////////////////////////////////////////////////////////////////
// For info about the file structrure see
// https://docs.microsoft.com/en-us/windows/win32/menurc/versioninfo-resource
// and
// https://docs.microsoft.com/en-us/windows/win32/menurc/stringfileinfo-block

// Icon
//
// Icon with lowest ID value placed first to ensure application icon
// remains consistent on all systems.
// SCIFORGE: SciForge's own icon and version strings (docs/sciforge/core-patches.md #9)
IDI_ICON1               ICON    DISCARDABLE     "${SCIFORGE_WIN_ICON}"

// File info for the FreeCAD.exe
//
1 VERSIONINFO
FILEVERSION ${SCIFORGE_VERSION_MAJOR},${SCIFORGE_VERSION_MINOR},${SCIFORGE_VERSION_PATCH},${PACKAGE_BUILD_VERSION}
BEGIN
    BLOCK "StringFileInfo"
    BEGIN
        BLOCK "040904b0" // 409 stands for US English
        BEGIN
            VALUE "CompanyName", "${SCIFORGE_APP_NAME} contributors"
            VALUE "FileDescription", "${SCIFORGE_APP_NAME} main executable (based on ${PROJECT_NAME})"
            VALUE "InternalName", "${SCIFORGE_APP_NAME}.exe"
            VALUE "LegalCopyright", "(C) SciForge contributors; based on FreeCAD, (C) FreeCAD contributors (LGPL-2.1-or-later)"
            VALUE "OriginalFilename", "${SCIFORGE_APP_NAME}.exe"
            VALUE "ProductName", "${SCIFORGE_APP_NAME}"
            VALUE "ProductVersion", "${SCIFORGE_VERSION}"
        END
    END
    BLOCK "VarFileInfo"
    BEGIN
        VALUE "Translation", 0x409, 1200 //US English, Unicode
    END
END
