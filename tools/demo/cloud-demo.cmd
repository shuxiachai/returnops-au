@echo off
rem Double-click to deploy this folder to Railway and copy the new sessions:
rem demo.ps1 cloud (README, Railway deployment). Needs the Railway CLI, signed in
rem with railway login and linked once with railway link in this folder. Every
rem deployment is a fresh demonstration whose sessions last 899 s, so start it
rem about ten minutes before the demonstration. This window stays open.
rem AI-assisted implementation; author shuxiachai.
title ReturnOps demo - Railway
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0demo.ps1" cloud
echo.
pause
