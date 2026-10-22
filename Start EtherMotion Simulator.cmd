@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
set "UALR_ETHERMOTION=%USERPROFILE%\Desktop\EtherMotion\EtherMotion.exe"
if not exist "%UALR_ETHERMOTION%" set "UALR_ETHERMOTION=%~dp0EtherMotion\EtherMotion.exe"
if not exist "%UALR_ETHERMOTION%" (
  echo Install your authorized EtherMotion copy in Desktop\EtherMotion first.
  pause
  exit /b 1
)
if not exist "%~dp0data\ethermotion-simulator" mkdir "%~dp0data\ethermotion-simulator"
if not exist "%~dp0data\ethermotion-simulator\workspace.json" copy /y "%~dp0EtherMotion\UALR-simulator-workspace.json" "%~dp0data\ethermotion-simulator\workspace.json" >nul
if not exist "%~dp0data\ethermotion-simulator\workspace.json" (
  echo Could not create the simulator workspace. Check folder permissions.
  pause
  exit /b 1
)
start "EtherMotion UALR Simulator" "%UALR_ETHERMOTION%" --data "%~dp0data\ethermotion-simulator\workspace.json" --port 8766
