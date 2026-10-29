@echo off
rem Double-click to start the demonstration from scratch: demo.ps1 fresh opens
rem Docker Desktop if Docker does not answer, then runs stop -RemoveData,
rem prepare and start (README, Demo machine script). The data of an earlier run
rem is deleted, and the new sessions last 899 s, so start it about five minutes
rem before the demonstration. This window stays open to show the result.
rem AI-assisted implementation; author shuxiachai.
title ReturnOps demo - start
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0demo.ps1" fresh
echo.
pause
