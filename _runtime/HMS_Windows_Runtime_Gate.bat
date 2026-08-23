@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0HMS_Windows_Runtime_Gate.ps1" -Root "%~dp0" -Profile PREFLIGHT -Output "%~dp0runtime-gate-result-v25_23_1.json"
pause
