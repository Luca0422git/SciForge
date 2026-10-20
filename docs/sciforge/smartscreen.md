<!-- SciForge: the fixed "Windows protected your PC" explanation. README.md (between its smartscreen markers) and every release's notes (the release-notes generator) use this text word for word, so it must stay self-contained: no relative links, only full https:// addresses. A unit test (test_docs_links.py) checks that README.md still carries this exact text. Everything below this line is the text. -->
### "Windows protected your PC" (SciForge is not signed)

When you start the SciForge installer for the first time, Windows may show a blue window called
**Windows protected your PC**. This is normal for SciForge, and it does not mean the download
is broken or dangerous.

**Why it appears.** The installer is not signed with a paid code-signing certificate. Those
certificates cost money every year, and SciForge is free and open source, so it does not have one
yet. Windows (the feature is called Microsoft Defender SmartScreen) warns about every program it
has not seen many times before, signed or not. That is its job, and it is a sensible default. It
only tells you that Windows does not know this program yet, not that anything is wrong with it.

**What to click** (Windows 10 and 11):

1. In the blue window, click **More info** (the small text under the message).
2. The window now shows the file name and says "Publisher: Unknown publisher", and a new button
   **Run anyway** appears. Click **Run anyway**.
3. Windows then asks "Do you want to allow this app to make changes to your device?". Click
   **Yes**. The installer needs this to put SciForge in `C:\Program Files\SciForge`.

If you use the portable download (the `.7z` file), unpack it with 7-Zip and start
`bin\SciForge.exe`. The same blue window can appear the first time; click **More info**, then
**Run anyway**, the same way.

**If your browser already complained while downloading.** Edge and Chrome may say the file "is
not commonly downloaded". In Edge, open the download's `...` menu, click **Keep**, then **Show
more**, then **Keep anyway**. In Chrome, open the download's menu and click **Keep** (and **Keep anyway** if it asks
again). This is the same warning, one step earlier.

**If there is no "More info" link at all.** Right-click the downloaded file, choose
**Properties**, tick **Unblock** at the bottom of the General tab, click **OK**, and start the
file again. (An administrator can also have set Windows to block unknown programs completely. In
that case ask them.)

**Check that your download is the real one (optional, takes a minute).** Every release has a
checksum file, `SHA256SUMS.txt`, next to the downloads on the releases page. A checksum is a
fingerprint of a file. If your copy gives the same fingerprint as the one on the page, nothing
changed it on the way to you. In PowerShell (Start menu, type "PowerShell"), go to your
Downloads folder and run this, with your real file name:

```
cd $HOME\Downloads
Get-FileHash .\SciForge_YOUR_FILE_NAME-installer.exe -Algorithm SHA256
```

Compare the long `Hash` value with the line for the same file in `SHA256SUMS.txt` (capital or
small letters do not matter). If they differ, delete the file, download it again, and if it
still differs, please tell us:
https://github.com/Luca0422git/SciForge/issues

**If your antivirus program blocks or removes the file.** Programs that are new, unsigned, and
bring their own Python and many libraries (like SciForge and FreeCAD, which it is based on) are
sometimes flagged by mistake. This is called a false positive. What to do:

- Do not switch your antivirus off for good. Check the checksum as described above first.
- Look in the antivirus program's quarantine or history list. If it moved the SciForge file
  there and the checksum matched, you can restore it. If you trust the checked download, you can
  tell the antivirus to allow SciForge's folder (usually `C:\Program Files\SciForge`). How to do
  this differs by program; its help page has the steps ("add an exclusion").
- Most antivirus makers have a page to report a false positive; sending them the file helps
  everyone who downloads SciForge after you.
- If you are not comfortable with any of this, wait: nothing is lost by not installing a beta.
  And if you would like help, open an issue and tell us which antivirus program it was.

SciForge never needs an account. The installer puts the program in its own folder
(`C:\Program Files\SciForge`), adds a Start menu entry and an entry in Windows' "Installed apps"
(so you can uninstall it), and only if you tick them, a desktop icon and the `.FCStd` file type.
It leaves an installed FreeCAD alone. All of the source code can be read at
https://github.com/Luca0422git/SciForge
