@echo off
setlocal
cd /d "%~dp0"

echo ========================================================
echo   Setting up AI Quotas 1-Click Desktop Overlay...
echo ========================================================

:: 1. Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Python is required. Please install Python from python.org.
    pause
    exit /b 1
)

:: 2. Install PyQt6 if missing
python -c "import PyQt6" >nul 2>&1
if %errorlevel% neq 0 (
    echo [*] Installing PyQt6 GUI framework...
    pip install PyQt6
)

:: 3. Create Windows Desktop & Startup Shortcuts using PowerShell
powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\AI Quotas.lnk'); $s.TargetPath = 'pythonw.exe'; $s.Arguments = '\"%~dp0hud\crossplatform_hud.py\"'; $s.WorkingDirectory = '%~dp0'; $s.IconLocation = 'shell32.dll,238'; $s.Save();"
powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut([Environment]::GetFolderPath('Startup') + '\AI Quotas.lnk'); $s.TargetPath = 'pythonw.exe'; $s.Arguments = '\"%~dp0hud\crossplatform_hud.py\"'; $s.WorkingDirectory = '%~dp0'; $s.IconLocation = 'shell32.dll,238'; $s.Save();"

echo [✓] Desktop shortcut "AI Quotas" created!
echo [✓] Added to Windows Startup (launches on boot).

:: 4. Launch immediately
echo [*] Launching AI Quotas HUD...
start "" pythonw "%~dp0hud\crossplatform_hud.py"

echo.
echo ========================================================
echo   Done! Double-click 'AI Quotas' on your desktop anytime.
echo ========================================================
timeout /t 3 >nul
exit /b 0
