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
  echo Runtime setup failed. See the error above. No models or settings were replaced.
  pause
  exit /b 1
)
start "UALR Part Tracking" "%~dp0PartTrackingUALR.exe"
