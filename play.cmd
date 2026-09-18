@echo off
cd /d "%~dp0"
".venv\Scripts\tetris-jev.exe" %*
if errorlevel 1 pause
