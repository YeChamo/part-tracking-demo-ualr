@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Build.ps1" %*
if errorlevel 1 (
  echo Build failed. See the error above. The installed demo was preserved.
  pause
  exit /b 1
)
pause
