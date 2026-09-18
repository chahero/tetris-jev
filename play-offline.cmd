@echo off
cd /d "%~dp0"
".venv\Scripts\tetris-jev.exe" --policy heuristic %*
if errorlevel 1 pause
