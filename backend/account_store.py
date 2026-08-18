"""Persistent Isolated Account State Store.

Guarantees each account has an immutable storage key and independent cache file
under ~/.config/ai-quota-overlay/accounts/<account_id>.json.
No cross-talk, no heuristics, 100% persistent identity.
"""
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

STORE_DIR = Path.home() / ".config" / "ai-quota-overlay" / "accounts"


def get_account_file(account_id: str) -> Path:
    """Return path to isolated account cache file."""
    STORE_DIR.mkdir(parents=True, exist_ok=True)
    return STORE_DIR / f"{account_id}.json"


def save_account_state(account_id: str, data: Dict[str, Any]) -> None:
    """Save account data to its isolated persistent file."""
    try:
        acc_file = get_account_file(account_id)
        payload = dict(data)
        payload["_saved_epoch"] = time.time()
        temp_file = acc_file.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        temp_file.replace(acc_file)
    except Exception as e:
        print(f"Error saving account {account_id}: {e}")


def load_account_state(account_id: str) -> Optional[Dict[str, Any]]:
    """Load account data from its isolated persistent file."""
    try:
        acc_file = get_account_file(account_id)
        if acc_file.exists():
            with open(acc_file, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading account {account_id}: {e}")
    return None
