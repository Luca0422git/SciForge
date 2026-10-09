@echo off
title SciForge quick update
rem Starts install_update.ps1 even where Windows blocks downloaded scripts,
rem and keeps this window open so you can read what happened.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_update.ps1" -NoPause %*
echo.
pause
