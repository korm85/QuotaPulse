@echo off
title AI Quota Overlay
cd /d "%~dp0"

echo ========================================================
echo   AI Quota & Rate Limit Desktop Overlay for Windows
echo   Supports: Cursor, Claude, Antigravity, Codex (ChatGPT)
echo ========================================================
echo.

:: Check python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Python is not installed or not in PATH.
    echo [!] Please install Python 3.10+ from python.org
    pause
    exit /b 1
)

:: Install required dependencies if missing
python -c "import PyQt6" >nul 2>&1
if %errorlevel% neq 0 (
    echo [*] Installing PyQt6 GUI framework...
    pip install PyQt6
)

:: Launch HUD
echo [*] Launching AI Quota HUD...
start "" pythonw hud\crossplatform_hud.py
exit /b 0
