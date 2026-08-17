"""Cross-platform Path and Environment Resolver."""
import os
import sys
from pathlib import Path
from typing import Optional


def get_user_home() -> Path:
    """Return user home directory across Windows, Linux, and macOS."""
    return Path.home()


def get_appdata_dir() -> Path:
    """Return platform-specific Application Data directory."""
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata)
        return Path.home() / "AppData" / "Roaming"
    elif sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support"
    else:
        # Linux
        xdg_config = os.environ.get("XDG_CONFIG_HOME")
        if xdg_config:
            return Path(xdg_config)
        return Path.home() / ".config"


def get_localappdata_dir() -> Path:
    """Return platform-specific Local AppData directory (Windows)."""
    if sys.platform == "win32":
        localappdata = os.environ.get("LOCALAPPDATA")
        if localappdata:
            return Path(localappdata)
        return Path.home() / "AppData" / "Local"
    return get_appdata_dir()


def resolve_service_paths() -> dict:
    """Resolve default config & auth paths for all supported coding agents."""
    home = get_user_home()
    appdata = get_appdata_dir()

    return {
        # Cursor IDE
        "cursor_db": [
            appdata / "Cursor" / "User" / "globalStorage" / "state.vscdb",
            home / ".config" / "Cursor" / "User" / "globalStorage" / "state.vscdb",
            home / ".cursor" / "state.vscdb"
        ],
        # Claude Code & Desktop
        "claude_dir": [
            home / ".claude",
            appdata / "Claude",
            home / ".config" / "Claude"
        ],
        "claude_json": [
            home / ".claude.json",
            appdata / "Claude" / "claude.json"
        ],
        # Antigravity CLI & IDE
        "antigravity_dir": [
            home / ".gemini" / "antigravity-cli",
            home / ".gemini" / "antigravity",
            home / ".gemini" / "antigravity-ide"
        ],
        # Codex CLI & Desktop
        "codex_auth": [
            home / ".codex" / "auth.json",
            appdata / "Codex" / "auth.json"
        ]
    }
