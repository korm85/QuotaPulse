"""Claude AI Quota Collector (Claude Code & Claude Desktop on Windows/Linux)."""
import json
import os
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from backend.platform_paths import get_appdata_dir, get_user_home


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


def find_claude_desktop_dir() -> Optional[Path]:
    """Find Claude Desktop application data directory."""
    candidates = [
        get_appdata_dir() / "Claude",
        get_user_home() / ".config" / "Claude",
        get_user_home() / "AppData" / "Roaming" / "Claude"
    ]
    for c in candidates:
        if c.exists() and (c / "plan-usage-history.json").exists():
            return c
    for c in candidates:
        if c.exists():
            return c
    return None


def collect_claude_desktop_quota(account_config: Dict[str, Any]) -> Dict[str, Any]:
    """Collect usage from Claude Desktop Electron app."""
    account_id = account_config.get("id", "claude_secondary")
    account_name = account_config.get("name", "Claude (Desktop)")

    result: Dict[str, Any] = {
        "id": account_id,
        "name": account_name,
        "service": "claude",
        "enabled": account_config.get("enabled", True),
        "status": "unknown",
        "email": None,
        "plan": "PRO",
        "tier": None,
        "organization": None,
        "used_pct": 0.0,
        "remaining_pct": 100.0,
        "tokens_used": 0,
        "token_limit": 0,
        "resets_at": None,
        "resets_at_epoch": None,
        "resets_in_seconds": None,
        "resets_in_human": None,
        "cost_usd": 0.0,
        "burn_rate_cost_per_hour": 0.0,
        "model_distribution": [],
        "details": {},
        "last_updated": datetime.now(timezone.utc).isoformat()
    }

    desktop_dir = find_claude_desktop_dir()
    if not desktop_dir:
        result["status"] = "not_configured"
        result["details"]["message"] = "Claude Desktop app data not found"
        return result

    # 1. Read plan-usage-history.json
    plan_history_file = desktop_dir / "plan-usage-history.json"
    if plan_history_file.exists():
        try:
            with open(plan_history_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                samples = data.get("samples", [])
                if samples:
                    last_sample = samples[-1]
                    usage = last_sample.get("u", {})
                    fh = float(usage.get("fh", 0))  # 5-hour used %
                    sd = float(usage.get("sd", 0))  # 7-day used %
                    
                    result["used_pct"] = round(fh, 1)
                    result["remaining_pct"] = round(max(0.0, 100.0 - fh), 1)
                    result["details"]["7_day_used_pct"] = f"{sd:.1f}%"
                    result["details"]["org_id"] = last_sample.get("org")

                    sample_epoch = last_sample.get("t", int(time.time() * 1000)) / 1000.0
                    now_epoch = time.time()

                    # Try getting exact reset from claude-monitor if active
                    claude_monitor_bin = shutil.which("claude-monitor")
                    projects_dir = get_user_home() / ".claude" / "projects"
                    if claude_monitor_bin and projects_dir.exists():
                        try:
                            cmd = [claude_monitor_bin, "--once", "--output", "json", "--data-paths", str(projects_dir)]
                            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=8)
                            if proc.returncode == 0 and proc.stdout.strip():
                                m_data = json.loads(proc.stdout)
                                reset_epoch = m_data.get("limits", {}).get("five_hour", {}).get("resets_at_epoch")
                                if reset_epoch and reset_epoch > now_epoch:
                                    diff = int(reset_epoch - now_epoch)
                                    result["resets_at_epoch"] = reset_epoch
                                    result["resets_in_seconds"] = diff
                                    result["resets_in_human"] = format_duration(diff)
                                    result["resets_at"] = m_data.get("limits", {}).get("five_hour", {}).get("resets_at")
                        except Exception:
                            pass

                    if not result["resets_in_seconds"]:
                        rem_secs = max(0, int(5 * 3600 - ((now_epoch - sample_epoch) % (5 * 3600))))
                        result["resets_in_seconds"] = rem_secs
                        result["resets_in_human"] = format_duration(rem_secs)
                        result["resets_at_epoch"] = int(now_epoch + rem_secs)
                        result["resets_at"] = datetime.fromtimestamp(now_epoch + rem_secs, tz=timezone.utc).isoformat()

                    result["status"] = "ok"
        except Exception as e:
            result["details"]["plan_history_err"] = str(e)

    # 2. Read config.json for account info
    cfg_file = desktop_dir / "config.json"
    if cfg_file.exists():
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                cdata = json.load(f)
                if "lastKnownAccountUuid" in cdata:
                    result["details"]["account_uuid"] = cdata["lastKnownAccountUuid"]
        except Exception as e:
            result["details"]["config_json_err"] = str(e)

    if result["status"] == "unknown":
        result["status"] = "idle"
        result["resets_in_human"] = "rolling 5h"

    return result


def compute_exact_claude_5h_usage(projects_dir: Path, plan: str = "TEAM") -> Dict[str, Any]:
    """Calculate ground-truth 5h rolling usage directly from local Claude Code JSONL logs."""
    now = time.time()
    window_5h_ago = now - 5 * 3600

    total_out = 0
    total_in = 0
    total_cache_create = 0
    total_cache_read = 0
    first_ts = now
    active_records = 0

    jsonl_files = list(projects_dir.glob("**/*.jsonl")) if projects_dir.exists() else []

    for jf in jsonl_files:
        try:
            if os.path.getmtime(jf) < window_5h_ago:
                continue
            with open(jf, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    try:
                        d = json.loads(line)
                        ts_str = d.get("timestamp")
                        if ts_str:
                            dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                            t_epoch = dt.timestamp()
                            if t_epoch < window_5h_ago:
                                continue
                            if t_epoch < first_ts:
                                first_ts = t_epoch

                        msg = d.get("message", {})
                        usage = msg.get("usage", {}) if isinstance(msg, dict) else {}
                        if usage:
                            total_out += usage.get("output_tokens", 0)
                            total_in += usage.get("input_tokens", 0)
                            total_cache_create += usage.get("cache_creation_input_tokens", 0)
                            total_cache_read += usage.get("cache_read_input_tokens", 0)
                            active_records += 1
                    except Exception:
                        pass
        except Exception:
            pass

    # Weighted standard Anthropic pricing
    cost = (total_out * 15.0 + total_cache_create * 3.75 + total_cache_read * 0.30 + total_in * 3.0) / 1000000.0
    
    # Team Plan budget = $74.00, Pro Plan budget = $45.00
    plan_budget = 74.0 if "TEAM" in plan.upper() else 45.0
    used_pct = min(100.0, (cost / plan_budget) * 100.0) if plan_budget > 0 else 0.0
    
    rem_secs = max(0, int(5 * 3600 - (now - first_ts))) if active_records > 0 else (5 * 3600)
    
    return {
        "used_pct": round(used_pct, 1),
        "cost_usd": round(cost, 2),
        "tokens_used": total_out + total_in,
        "resets_in_seconds": rem_secs,
        "resets_in_human": format_duration(rem_secs),
        "resets_at_epoch": int(now + rem_secs),
        "resets_at": datetime.fromtimestamp(now + rem_secs, tz=timezone.utc).isoformat(),
        "active_records": active_records
    }


def collect_claude_quota(account_config: Dict[str, Any]) -> Dict[str, Any]:
    """Collect usage and quota for a Claude account (Claude Code or Claude Desktop)."""
    account_id = account_config.get("id", "claude_primary")
    account_type = account_config.get("type", "claude_code")

    # If configured as desktop or secondary, try Claude Desktop detection
    if account_type == "claude_desktop" or "desktop" in account_config.get("name", "").lower():
        return collect_claude_desktop_quota(account_config)

    # If it's claude_secondary and ~/.claude-2 doesn't exist, auto-fallback to Claude Desktop!
    config_dir_str = account_config.get("config_dir", "")
    config_dir = Path(os.path.expanduser(config_dir_str)) if config_dir_str else None
    
    if account_id == "claude_secondary" and (not config_dir or not config_dir.exists()):
        desktop_dir = find_claude_desktop_dir()
        if desktop_dir and (desktop_dir / "plan-usage-history.json").exists():
            account_config["name"] = "Claude (Desktop)"
            return collect_claude_desktop_quota(account_config)

    # Standard Claude Code Collector
    account_name = account_config.get("name", "Claude (Primary)")
    if not config_dir:
        config_dir = get_user_home() / ".claude"
    
    claude_json_str = account_config.get("claude_json", "")
    claude_json_path = Path(os.path.expanduser(claude_json_str)) if claude_json_str else (get_user_home() / ".claude.json")
    
    cred_file_str = account_config.get("credentials_file", "")
    cred_file = Path(os.path.expanduser(cred_file_str)) if cred_file_str else (config_dir / ".credentials.json")

    result: Dict[str, Any] = {
        "id": account_id,
        "name": account_name,
        "service": "claude",
        "enabled": account_config.get("enabled", True),
        "status": "unknown",
        "email": None,
        "plan": "TEAM",
        "tier": None,
        "organization": None,
        "used_pct": 0.0,
        "remaining_pct": 100.0,
        "tokens_used": 0,
        "token_limit": 0,
        "resets_at": None,
        "resets_at_epoch": None,
        "resets_in_seconds": None,
        "resets_in_human": None,
        "cost_usd": 0.0,
        "burn_rate_cost_per_hour": 0.0,
        "model_distribution": [],
        "details": {},
        "last_updated": datetime.now(timezone.utc).isoformat()
    }

    if not config_dir.exists() and not claude_json_path.exists() and not cred_file.exists():
        result["status"] = "not_configured"
        result["details"] = {"message": f"Profile dir {config_dir} not found"}
        return result

    # 1. Read metadata from claude.json
    if claude_json_path.exists():
        try:
            with open(claude_json_path, "r", encoding="utf-8") as f:
                cdata = json.load(f)
                oauth_acc = cdata.get("oauthAccount", {})
                result["email"] = oauth_acc.get("emailAddress")
                result["organization"] = oauth_acc.get("organizationName")
                result["tier"] = oauth_acc.get("organizationRateLimitTier") or oauth_acc.get("userRateLimitTier")
                billing_type = oauth_acc.get("billingType")
                if billing_type:
                    result["plan"] = billing_type.upper()
        except Exception as e:
            result["details"]["claude_json_err"] = str(e)

    # 2. Read credentials metadata
    if cred_file.exists():
        try:
            with open(cred_file, "r", encoding="utf-8") as f:
                creds = json.load(f)
                claude_oauth = creds.get("claudeAiOauth", {})
                sub_type = claude_oauth.get("subscriptionType")
                if sub_type:
                    result["plan"] = sub_type.upper()
                if not result["tier"]:
                    result["tier"] = claude_oauth.get("rateLimitTier")
        except Exception as e:
            result["details"]["cred_file_err"] = str(e)

    # 3. Calculate Ground Truth 5h Rolling Usage directly from active JSONL logs
    projects_dir = config_dir / "projects"
    if projects_dir.exists():
        try:
            live_usage = compute_exact_claude_5h_usage(projects_dir, result["plan"])
            if live_usage.get("active_records", 0) > 0:
                result["used_pct"] = live_usage["used_pct"]
                result["remaining_pct"] = round(max(0.0, 100.0 - live_usage["used_pct"]), 1)
                result["cost_usd"] = live_usage["cost_usd"]
                result["tokens_used"] = live_usage["tokens_used"]
                result["resets_in_seconds"] = live_usage["resets_in_seconds"]
                result["resets_in_human"] = live_usage["resets_in_human"]
                result["resets_at_epoch"] = live_usage["resets_at_epoch"]
                result["resets_at"] = live_usage["resets_at"]
                result["status"] = "ok"
        except Exception as e:
            result["details"]["live_calc_err"] = str(e)

    # 4. Integrate server-side authoritative telemetry from desktop history if available
    desktop_dir = find_claude_desktop_dir()
    if desktop_dir:
        plan_hist = desktop_dir / "plan-usage-history.json"
        if plan_hist.exists():
            try:
                with open(plan_hist, "r", encoding="utf-8") as f:
                    pdata = json.load(f)
                    samples = pdata.get("samples", [])
                    if samples:
                        last_s = samples[-1]
                        s_time = last_s.get("t", 0) / 1000.0
                        if time.time() - s_time < 86400:
                            usage = last_s.get("u", {})
                            fh = float(usage.get("fh", 0))
                            sd = float(usage.get("sd", 0))
                            if fh > result["used_pct"]:
                                result["used_pct"] = round(fh, 1)
                                result["remaining_pct"] = round(max(0.0, 100.0 - fh), 1)
                            result["details"]["7_day_used_pct"] = f"{sd:.1f}%"
                            result["status"] = "ok"
            except Exception:
                pass

    if result["status"] == "ok":
        return result

    # 5. Fallback calculation if claude-monitor didn't run
    if result["status"] == "unknown":
        if result["email"] or result["plan"]:
            result["status"] = "idle"
            result["resets_in_human"] = "rolling 5h"
        else:
            result["status"] = "not_configured"

    return result
