@echo off
cd /d "%~dp0"
python "%~dp0HMS_Codex_ProductionDoctor.py" --mode audit --root "%~dp0" --data "%LOCALAPPDATA%\HMS_AI_MultiRouter"
pause
