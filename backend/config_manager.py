"""Configuration manager for AI Quota Overlay."""
import json
import os
from pathlib import Path
from typing import Any, Dict

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "ai-quota-overlay"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.json"
DEFAULT_STATE_FILE = DEFAULT_CONFIG_DIR / "state.json"

DEFAULT_CONFIG = {
    "refresh_interval_seconds": 60,
    "accounts": {
        "claude": [
            {
                "id": "claude_primary",
                "name": "Claude (Primary)",
                "enabled": True,
                "type": "claude_code",
                "config_dir": str(Path.home() / ".claude"),
                "claude_json": str(Path.home() / ".claude.json"),
                "credentials_file": str(Path.home() / ".claude" / ".credentials.json")
            },
            {
                "id": "claude_secondary",
                "name": "Claude (Secondary)",
                "enabled": True,
                "type": "claude_code",
                "config_dir": str(Path.home() / ".claude-2"),
                "claude_json": str(Path.home() / ".claude-2.json"),
                "credentials_file": str(Path.home() / ".claude-2" / ".credentials.json")
            }
        ],
        "antigravity": [
            {
                "id": "antigravity_ide",
                "name": "Antigravity (IDE)",
                "enabled": True,
                "type": "antigravity_local",
                "data_dir": str(Path.home() / ".gemini" / "antigravity-ide"),
                "state_file": str(Path.home() / ".gemini" / "antigravity-ide" / "antigravity_state.pbtxt")
            },
            {
                "id": "antigravity_cli",
                "name": "Antigravity (CLI)",
                "enabled": True,
                "type": "antigravity_local",
                "data_dir": str(Path.home() / ".gemini" / "antigravity-cli"),
                "state_file": str(Path.home() / ".gemini" / "antigravity-cli" / "jetski_state.pbtxt")
            }
        ],
        "codex": [
            {
                "id": "codex_primary",
                "name": "Codex (ChatGPT)",
                "enabled": True,
                "type": "codex_local",
                "auth_file": str(Path.home() / ".codex" / "auth.json"),
                "config_file": str(Path.home() / ".codex" / "config.toml")
            }
        ],
        "cursor": [
            {
                "id": "cursor_primary",
                "name": "Cursor",
                "enabled": True,
                "type": "cursor_local"
            }
        ]
    },
    "ui": {
        "top_bar_format": "{ag} | {cl} | {cx} | {cu}",
        "show_reset_timer": True,
        "warning_threshold_pct": 80.0,
        "critical_threshold_pct": 90.0,
        "notifications_enabled": True
    },
    "routing_policy": {
        "strategy": "claude_first_relay",
        "switch_threshold_pct": 3.0,
        "recovery_threshold_pct": 20.0,
        "fallback_chain": [
            "claude_primary",
            "claude_secondary",
            "antigravity_cli",
            "codex_primary"
        ]
    },
    "polling": {
        "daemon_interval_seconds": 60,
        "hud_refresh_seconds": 5
    }
}


def load_config() -> Dict[str, Any]:
    """Load configuration from ~/.config/ai-quota-overlay/config.json or create default."""
    if not DEFAULT_CONFIG_DIR.exists():
        DEFAULT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    if not DEFAULT_CONFIG_FILE.exists():
        with open(DEFAULT_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
        return DEFAULT_CONFIG

    try:
        with open(DEFAULT_CONFIG_FILE, "r", encoding="utf-8") as f:
            user_config = json.load(f)
            # merge defaults for missing keys
            for k, v in DEFAULT_CONFIG.items():
                if k not in user_config:
                    user_config[k] = v
            return user_config
    except Exception:
        return DEFAULT_CONFIG


def save_config(config: Dict[str, Any]) -> None:
    """Save configuration."""
    DEFAULT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(DEFAULT_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
