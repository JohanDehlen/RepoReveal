@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo RepoReveal virtual environment was not found.
    echo Run the project bootstrap/setup first.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m reporeveal.app