@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
if not exist "%~dp0PartTrackingUALR.exe" (
  echo The demo executable is missing. Keep the complete demo folder together.
  pause
  exit /b 1
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0SetupRuntime.ps1"
if errorlevel 1 (
  echo Runtime setup failed with exit code %ERRORLEVEL%.
  echo Demo folder: "%~dp0"
  echo Read the error above or data\runtime-setup-error.txt in this folder.
  echo For offline startup, extract the complete portable ZIP with all folders.
  echo Your models and settings were preserved.
  pause
  exit /b 1
)
start "UALR Part Tracking" "%~dp0PartTrackingUALR.exe"
