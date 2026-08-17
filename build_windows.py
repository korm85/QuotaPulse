"""Windows Single .EXE Builder using PyInstaller."""
import os
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent

def build():
    print("[*] Building standalone Windows executable...")
    
    # Check pyinstaller
    try:
        import PyInstaller
    except ImportError:
        print("[*] Installing PyInstaller...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller", "PyQt6"], check=True)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconsole",
        "--onefile",
        "--name", "AIQuotaOverlay",
        "--add-data", f"backend{os.pathsep}backend",
        "--add-data", f"hud{os.pathsep}hud",
        str(ROOT_DIR / "hud" / "crossplatform_hud.py")
    ]

    print("Running:", " ".join(cmd))
    subprocess.run(cmd, cwd=str(ROOT_DIR), check=True)
    print("\n[✓] Build complete! Executable located at: dist/AIQuotaOverlay.exe")

if __name__ == "__main__":
    build()
