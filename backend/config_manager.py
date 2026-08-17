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
        "emergency_failover_mode": "transparent_proxy",
        "switch_threshold_pct": 80.0,
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


def auto_discover_system(cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Automatically scan the OS and configure all installed AI tools with zero user prompts."""
    import shutil
    from backend.platform_paths import get_appdata_dir, get_user_home
    home = get_user_home()
    appdata = get_appdata_dir()

    if cfg is None:
        cfg = json.loads(json.dumps(DEFAULT_CONFIG))

    detected_accounts = {
        "claude": [],
        "antigravity": [],
        "codex": [],
        "cursor": []
    }
    fallback_chain = []

    # 1. Claude Primary
    cl_primary = home / ".claude"
    if cl_primary.exists() or (home / ".claude.json").exists():
        detected_accounts["claude"].append({
            "id": "claude_primary",
            "name": "Claude (Primary)",
            "enabled": True,
            "type": "claude_code",
            "config_dir": str(cl_primary),
            "claude_json": str(home / ".claude.json"),
            "credentials_file": str(cl_primary / ".credentials.json")
        })
        fallback_chain.append("claude_primary")

    # 2. Claude Secondary (Explicit CLI Profile only)
    for sec_name in [".claude-secondary", ".claude-2"]:
        cl_sec = home / sec_name
        if cl_sec.exists() and (cl_sec / ".credentials.json").exists():
            detected_accounts["claude"].append({
                "id": "claude_secondary",
                "name": "Claude (Secondary)",
                "enabled": True,
                "type": "claude_code",
                "config_dir": str(cl_sec),
                "claude_json": str(cl_sec / ".claude.json"),
                "credentials_file": str(cl_sec / ".credentials.json")
            })
            if "claude_secondary" not in fallback_chain:
                fallback_chain.append("claude_secondary")
            break

    # 4. Antigravity CLI & IDE
    ag_cli = home / ".gemini" / "antigravity-cli"
    if ag_cli.exists() or shutil.which("agy") or shutil.which("antigravity"):
        detected_accounts["antigravity"].append({
            "id": "antigravity_cli",
            "name": "Antigravity (CLI)",
            "enabled": True,
            "type": "antigravity_local",
            "data_dir": str(ag_cli),
            "state_file": str(ag_cli / "jetski_state.pbtxt")
        })
        fallback_chain.append("antigravity_cli")

    ag_ide = home / ".gemini" / "antigravity-ide"
    if ag_ide.exists():
        detected_accounts["antigravity"].append({
            "id": "antigravity_ide",
            "name": "Antigravity (IDE)",
            "enabled": True,
            "type": "antigravity_local",
            "data_dir": str(ag_ide),
            "state_file": str(ag_ide / "antigravity_state.pbtxt")
        })

    # 5. Codex / OpenAI
    codex_dir = home / ".codex"
    if codex_dir.exists():
        detected_accounts["codex"].append({
            "id": "codex_primary",
            "name": "Codex (ChatGPT)",
            "enabled": True,
            "type": "codex_local",
            "auth_file": str(codex_dir / "auth.json"),
            "config_file": str(codex_dir / "config.toml")
        })
        fallback_chain.append("codex_primary")

    # 6. Cursor
    cursor_dir = home / ".config" / "Cursor"
    if cursor_dir.exists():
        detected_accounts["cursor"].append({
            "id": "cursor_primary",
            "name": "Cursor",
            "enabled": True,
            "type": "cursor_local"
        })

    cfg["accounts"] = detected_accounts
    if fallback_chain:
        cfg["routing_policy"]["fallback_chain"] = fallback_chain

    return cfg


def load_config() -> Dict[str, Any]:
    """Load configuration from ~/.config/ai-quota-overlay/config.json or create via auto-discovery."""
    if not DEFAULT_CONFIG_DIR.exists():
        DEFAULT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    if not DEFAULT_CONFIG_FILE.exists():
        discovered = auto_discover_system()
        save_config(discovered)
        return discovered

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
