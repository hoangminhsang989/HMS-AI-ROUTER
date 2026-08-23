@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0HMS_Runtime_Orchestrator.ps1" -Stage ALL_READY -Root "%~dp0"
pause
