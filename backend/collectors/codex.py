"""Codex / OpenAI Quota Collector."""
import json
import os
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


def format_duration(seconds: float) -> str:
    """Format seconds into human readable duration."""
    if seconds <= 0:
        return "now"
    mins = int(seconds // 60)
    hours = int(mins // 60)
    days = int(hours // 24)
    if days > 0:
        rem_h = hours % 24
        return f"{days}d {rem_h}h"
    if hours > 0:
        rem_m = mins % 60
        return f"{hours}h {rem_m}m"
    return f"{mins}m"


def collect_codex_quota(account_config: Dict[str, Any]) -> Dict[str, Any]:
    """Collect usage and quota for a Codex / OpenAI account."""
    auth_file = Path(os.path.expanduser(account_config.get("auth_file", "~/.codex/auth.json")))
    account_id = account_config.get("id", "codex_primary")
    account_name = account_config.get("name", "Codex (ChatGPT)")

    result: Dict[str, Any] = {
        "id": account_id,
        "name": account_name,
        "service": "codex",
        "enabled": account_config.get("enabled", True),
        "status": "unknown",
        "email": None,
        "plan": "unknown",
        "used_pct": 0.0,
        "remaining_pct": 100.0,
        "resets_at": None,
        "resets_at_epoch": None,
        "resets_in_seconds": None,
        "resets_in_human": None,
        "window_duration_seconds": None,
        "details": {},
        "last_updated": datetime.now(timezone.utc).isoformat()
    }

    if not auth_file.exists():
        result["status"] = "not_configured"
        result["details"] = {"message": f"Auth file not found at {auth_file}"}
        return result

    try:
        with open(auth_file, "r", encoding="utf-8") as f:
            auth_data = json.load(f)

        tokens = auth_data.get("tokens", {})
        access_token = tokens.get("access_token")
        auth_mode = auth_data.get("auth_mode", "chatgpt")
        result["details"]["auth_mode"] = auth_mode
        result["details"]["account_id"] = tokens.get("account_id")

        if not access_token:
            result["status"] = "no_token"
            result["details"]["message"] = "No access token in auth.json"
            return result

        # Query live usage endpoint
        req = urllib.request.Request(
            "https://chatgpt.com/backend-api/wham/usage",
            headers={
                "Authorization": f"Bearer {access_token}",
                "User-Agent": "codex-cli/1.0"
            }
        )
        with urllib.request.urlopen(req, timeout=8) as res:
            if res.status == 200:
                raw_body = res.read().decode("utf-8")
                usage_data = json.loads(raw_body)
                
                result["email"] = usage_data.get("email")
                result["plan"] = usage_data.get("plan_type", "chatgpt").upper()
                
                rate_limit = usage_data.get("rate_limit", {})
                primary = rate_limit.get("primary_window") or {}
                
                used_pct = float(primary.get("used_percent", 0.0))
                result["used_pct"] = round(used_pct, 1)
                result["remaining_pct"] = round(max(0.0, 100.0 - used_pct), 1)
                
                reset_after = primary.get("reset_after_seconds")
                reset_at = primary.get("reset_at")
                window_secs = primary.get("limit_window_seconds")
                
                result["window_duration_seconds"] = window_secs
                
                if reset_after is not None:
                    result["resets_in_seconds"] = max(0, int(reset_after))
                    result["resets_in_human"] = format_duration(reset_after)
                    now_epoch = time.time()
                    calc_reset_epoch = now_epoch + reset_after
                    result["resets_at_epoch"] = int(calc_reset_epoch)
                    result["resets_at"] = datetime.fromtimestamp(calc_reset_epoch, tz=timezone.utc).isoformat()
                elif reset_at is not None:
                    result["resets_at_epoch"] = int(reset_at)
                    now_epoch = time.time()
                    diff = max(0, int(reset_at - now_epoch))
                    result["resets_in_seconds"] = diff
                    result["resets_in_human"] = format_duration(diff)
                    result["resets_at"] = datetime.fromtimestamp(reset_at, tz=timezone.utc).isoformat()
                
                result["details"]["allowed"] = rate_limit.get("allowed", True)
                result["details"]["limit_reached"] = rate_limit.get("limit_reached", False)
                result["details"]["secondary_window"] = rate_limit.get("secondary_window")
                result["status"] = "ok"
            else:
                result["status"] = "error"
                result["details"]["http_status"] = res.status

    except urllib.error.HTTPError as e:
        result["status"] = "http_error"
        result["details"]["error"] = f"HTTP {e.code}: {e.reason}"
        if e.code == 401:
            result["details"]["message"] = "Token expired. Please re-authenticate codex."
    except Exception as e:
        result["status"] = "offline"
        result["details"]["error"] = str(e)

    return result
