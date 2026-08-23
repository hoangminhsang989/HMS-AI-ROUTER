@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0HMS_Setup.ps1" -Mode preflight
if errorlevel 1 goto failed
echo.
choice /C IQR /M "I=Install per-user, Q=Quit, R=Rollback"
if errorlevel 3 goto rollback
if errorlevel 2 goto end
if errorlevel 1 goto install
:rollback
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0HMS_Setup.ps1" -Mode rollback
goto end
:install
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0HMS_Setup.ps1" -Mode install
goto end
:failed
echo.
echo HMS v18 preflight/source gate FAILED.
:end
pause
