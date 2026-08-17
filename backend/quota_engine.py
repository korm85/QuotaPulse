"""Main Quota Engine that coordinates all account collectors."""
import concurrent.futures
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.config_manager import load_config, DEFAULT_STATE_FILE
from backend.collectors.claude import collect_claude_quota
from backend.collectors.codex import collect_codex_quota
from backend.collectors.antigravity import collect_antigravity_quota
from backend.collectors.cursor import collect_cursor_quota
from backend.notifications import check_and_notify_quotas


def collect_all_quotas() -> Dict[str, Any]:
    """Fetch quotas across all configured accounts in parallel."""
    config = load_config()
    accounts_cfg = config.get("accounts", {})
    ui_cfg = config.get("ui", {})
    warn_thresh = float(ui_cfg.get("warning_threshold_pct", 80.0))
    crit_thresh = float(ui_cfg.get("critical_threshold_pct", 90.0))
    notify_enabled = bool(ui_cfg.get("notifications_enabled", True))
    
    tasks = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        # 1. Claude accounts
        for acc in accounts_cfg.get("claude", []):
            if acc.get("enabled", True):
                tasks.append(executor.submit(collect_claude_quota, acc))

        # 2. Antigravity accounts
        for acc in accounts_cfg.get("antigravity", []):
            if acc.get("enabled", True):
                tasks.append(executor.submit(collect_antigravity_quota, acc))

        # 3. Codex accounts
        for acc in accounts_cfg.get("codex", []):
            if acc.get("enabled", True):
                tasks.append(executor.submit(collect_codex_quota, acc))

        # 4. Cursor accounts
        for acc in accounts_cfg.get("cursor", []):
            if acc.get("enabled", True):
                tasks.append(executor.submit(collect_cursor_quota, acc))

    results: List[Dict[str, Any]] = []
    for t in tasks:
        try:
            res = t.result(timeout=15)
            # Add warning status flags
            used = float(res.get("used_pct", 0.0))
            res["is_warning"] = (used >= warn_thresh)
            res["is_critical"] = (used >= crit_thresh)
            results.append(res)
        except Exception as e:
            results.append({
                "id": "unknown_account",
                "service": "unknown",
                "status": "error",
                "used_pct": 0.0,
                "is_warning": False,
                "is_critical": False,
                "error": str(e)
            })

    # Trigger desktop notification alerts if enabled
    if notify_enabled:
        check_and_notify_quotas(results, warning_threshold=warn_thresh, critical_threshold=crit_thresh)

    # Group by service
    claude_accounts = [r for r in results if r.get("service") == "claude"]
    antigravity_accounts = [r for r in results if r.get("service") == "antigravity"]
    codex_accounts = [r for r in results if r.get("service") == "codex"]
    cursor_accounts = [r for r in results if r.get("service") == "cursor"]

    # Calculate summary badges for top bar (only for configured services)
    badges = {}
    summary_parts = []
    
    if any(a.get("status") != "not_configured" for a in antigravity_accounts):
        ag_max = max([a.get("used_pct", 0.0) for a in antigravity_accounts if a.get("status") != "not_configured"], default=0.0)
        ag_top = f"AG: {int(ag_max)}%"
        badges["antigravity"] = ag_top
        summary_parts.append(ag_top)

    if any(a.get("status") != "not_configured" for a in claude_accounts):
        cl_max = max([a.get("used_pct", 0.0) for a in claude_accounts if a.get("status") != "not_configured"], default=0.0)
        cl_top = f"CL: {int(cl_max)}%"
        badges["claude"] = cl_top
        summary_parts.append(cl_top)

    if any(a.get("status") != "not_configured" for a in codex_accounts):
        cx_max = max([a.get("used_pct", 0.0) for a in codex_accounts if a.get("status") != "not_configured"], default=0.0)
        cx_top = f"CX: {int(cx_max)}%"
        badges["codex"] = cx_top
        summary_parts.append(cx_top)

    if any(a.get("status") != "not_configured" for a in cursor_accounts):
        cu_max = max([a.get("used_pct", 0.0) for a in cursor_accounts if a.get("status") != "not_configured"], default=0.0)
        cu_top = f"CU: {int(cu_max)}%"
        badges["cursor"] = cu_top
        summary_parts.append(cu_top)

    # Overall max usage
    all_used_pcts = [r.get("used_pct", 0.0) for r in results if r.get("status") in ("ok", "rate_limited")]
    max_used = max(all_used_pcts) if all_used_pcts else 0.0

    state: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "epoch": int(time.time()),
        "max_used_pct": max_used,
        "summary_text": " | ".join(summary_parts),
        "badges": badges,
        "accounts": {
            "claude": claude_accounts,
            "antigravity": antigravity_accounts,
            "codex": codex_accounts,
            "cursor": cursor_accounts
        },
        "all_accounts": results
    }

    # Save to ~/.config/ai-quota-overlay/state.json
    try:
        DEFAULT_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        temp_file = DEFAULT_STATE_FILE.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        temp_file.replace(DEFAULT_STATE_FILE)
    except Exception as e:
        print(f"Warning: Failed to write state file: {e}", file=sys.stderr)

    return state


def run_daemon(interval_seconds: int = 60) -> None:
    """Run continuous monitoring loop."""
    print(f"[*] AI Quota Daemon started. Refresh interval: {interval_seconds}s")
    while True:
        try:
            state = collect_all_quotas()
            print(f"[{datetime.now().strftime('%H:%M:%S')}] State updated: {state['summary_text']}")
        except Exception as e:
            print(f"[!] Error updating quota: {e}", file=sys.stderr)
        time.sleep(interval_seconds)


if __name__ == "__main__":
    state = collect_all_quotas()
    print(json.dumps(state, indent=2))
