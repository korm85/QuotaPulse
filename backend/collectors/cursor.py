"""Cursor AI Quota & Usage Collector (Windows & Linux)."""
import json
import os
import sqlite3
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from backend.platform_paths import resolve_service_paths


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


def find_cursor_db() -> Optional[Path]:
    """Find Cursor SQLite state database on Windows or Linux."""
    paths = resolve_service_paths().get("cursor_db", [])
    for p in paths:
        if p.exists():
            return p
    return None


def extract_cursor_auth(db_path: Path) -> tuple:
    """Read token and email from Cursor state database."""
    token = None
    email = None
    plan = "PRO"

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=2.0)
        cur = conn.cursor()
        
        # Query auth items
        cur.execute("SELECT key, value FROM ItemTable WHERE key LIKE 'cursorAuth/%'")
        for k, v in cur.fetchall():
            if k == "cursorAuth/accessToken":
                token = v
            elif k == "cursorAuth/cachedEmail":
                email = v
            elif k == "cursorAuth/cachedSignUpType":
                plan = v.upper()

        conn.close()
    except Exception:
        pass

    return token, email, plan


def collect_cursor_quota(account_config: Dict[str, Any]) -> Dict[str, Any]:
    """Collect live quota for Cursor IDE account."""
    account_id = account_config.get("id", "cursor_primary")
    account_name = account_config.get("name", "Cursor")

    result: Dict[str, Any] = {
        "id": account_id,
        "name": account_name,
        "service": "cursor",
        "enabled": account_config.get("enabled", True),
        "status": "unknown",
        "email": None,
        "plan": "PRO",
        "used_pct": 0.0,
        "remaining_pct": 100.0,
        "fast_requests_used": 0,
        "fast_requests_limit": 500,
        "resets_at": None,
        "resets_at_epoch": None,
        "resets_in_seconds": None,
        "resets_in_human": None,
        "details": {},
        "last_updated": datetime.now(timezone.utc).isoformat()
    }

    db_path = find_cursor_db()
    if not db_path:
        result["status"] = "not_configured"
        result["details"]["message"] = "Cursor state database not found"
        return result

    token, email, plan = extract_cursor_auth(db_path)
    result["email"] = email
    result["plan"] = plan

    if not token:
        result["status"] = "not_logged_in"
        result["details"]["message"] = "No active Cursor login found"
        return result

    # Query Cursor live usage API
    try:
        req = urllib.request.Request(
            "https://www.cursor.com/api/usage",
            headers={
                "Cookie": f"WorkosCursorSessionToken={token}",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Cursor/1.0"
            }
        )
        with urllib.request.urlopen(req, timeout=6) as res:
            if res.status == 200:
                raw = res.read().decode("utf-8")
                usage = json.loads(raw)
                
                gpt4 = usage.get("gpt4", {})
                fast_used = gpt4.get("numRequests", 0)
                fast_limit = gpt4.get("maxRequestUsage", 500)
                
                result["fast_requests_used"] = fast_used
                result["fast_requests_limit"] = fast_limit
                
                used_pct = (fast_used / fast_limit) * 100.0 if fast_limit > 0 else 0.0
                result["used_pct"] = round(min(100.0, used_pct), 1)
                result["remaining_pct"] = round(max(0.0, 100.0 - result["used_pct"]), 1)
                
                # Monthly reset calculation
                start_month = usage.get("startOfMonth")
                if start_month:
                    result["resets_at"] = start_month
                    # standard 30 day cycle
                    now_epoch = time.time()
                    diff = max(0, int(30 * 86400 - (now_epoch % (30 * 86400))))
                    result["resets_in_seconds"] = diff
                    result["resets_in_human"] = format_duration(diff)

                result["details"]["slow_requests"] = usage.get("slowRequests", 0)
                result["status"] = "ok"
                return result
    except Exception as e:
        result["details"]["api_error"] = str(e)

    # Fallback if API was unreachable but login is valid
    result["status"] = "ok" if email else "idle"
    result["resets_in_human"] = "monthly"
    return result
