@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
if not exist "%~dp0PartTrackingUALR.exe" (
  echo The demo executable is missing. Keep the complete demo folder together.
  pause
  exit /b 1
)
start "UALR Part Tracking" "%~dp0PartTrackingUALR.exe"
