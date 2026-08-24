@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoLogo -NoProfile -File "%~dp0_runtime\HMS_Run_UAC_Validation.ps1"
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
  echo.
  echo HMS UAC validation stopped with exit code %RC%.
  pause
)
exit /b %RC%
