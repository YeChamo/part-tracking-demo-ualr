@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
start /wait "UALR runtime check" "%~dp0PartTrackingUALR.exe" --self-test
if errorlevel 1 (
  echo Runtime check failed. See data\runtime-check.json.
  pause
  exit /b 1
)
type "%~dp0data\runtime-check.json"
echo.
echo Runtime check passed. No cameras or motion hardware were opened.
pause
