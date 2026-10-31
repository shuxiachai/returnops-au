@echo off
rem Double-click after the demonstration: demo.ps1 stop -RemoveData closes the
rem demo windows and deletes this folder's demo database and identities
rem (README, Demo machine script). Sign out in the browsers stays manual.
rem AI-assisted implementation; author shuxiachai.
title ReturnOps demo - stop
echo This stops the demonstration and deletes its demo data.
echo Close this window to cancel, or
pause
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0demo.ps1" stop -RemoveData
echo.
pause
