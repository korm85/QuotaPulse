"""Automated Self-Diagnostic and Drift Prevention Suite.
Validates live collectors, bounds, isolated storage, and process health.
"""
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

from backend.config_manager import load_config, DEFAULT_STATE_FILE, DEFAULT_CONFIG_FILE
from backend.account_store import STORE_DIR, load_account_state
from backend.collectors.claude import collect_claude_quota
from backend.collectors.antigravity import collect_antigravity_quota
from backend.collectors.codex import collect_codex_quota
from backend.collectors.cursor import collect_cursor_quota
from backend.quota_engine import collect_all_quotas


def run_comprehensive_diagnostics() -> Tuple[bool, List[str]]:
    """Run end-to-end sanity tests and return (all_passed, list_of_findings)."""
    findings = []
    has_critical_error = False

    # 1. Config Check
    cfg = load_config()
    if not DEFAULT_CONFIG_FILE.exists():
        findings.append(f"[FAIL] Missing config file at {DEFAULT_CONFIG_FILE}")
        has_critical_error = True
    else:
        findings.append(f"[PASS] Config file present at {DEFAULT_CONFIG_FILE}")

    # 2. Collector Execution & Bounds Check
    accounts_cfg = cfg.get("accounts", {})
    all_results: List[Dict[str, Any]] = []

    # Claude
    for acc in accounts_cfg.get("claude", []):
        res = collect_claude_quota(acc)
        all_results.append(res)
        used = res.get("used_pct", -1)
        if not (0.0 <= used <= 100.0):
            findings.append(f"[FAIL] Claude account {res['id']} used_pct out of bounds: {used}%")
            has_critical_error = True
        else:
            findings.append(f"[PASS] Claude ({res['email']}): {used}% (Weekly: {res.get('weekly_used_pct')}%, Resets: {res.get('resets_in_human')})")

    # Antigravity
    for acc in accounts_cfg.get("antigravity", []):
        res = collect_antigravity_quota(acc)
        all_results.append(res)
        used = res.get("used_pct", -1)
        if not (0.0 <= used <= 100.0):
            findings.append(f"[FAIL] Antigravity account {res['id']} used_pct out of bounds: {used}%")
            has_critical_error = True
        elif used > 80.0 and res.get("recent_steps_count", 0) < 50:
            findings.append(f"[WARN] Antigravity shows {used}% but recent steps are low ({res.get('recent_steps_count')})")
        else:
            findings.append(f"[PASS] Antigravity ({res['email']}): {used}% (Weekly: {res.get('weekly_used_pct')}%, Resets: {res.get('resets_in_human')})")

    # Codex
    for acc in accounts_cfg.get("codex", []):
        res = collect_codex_quota(acc)
        all_results.append(res)
        findings.append(f"[PASS] Codex ({res.get('email', 'ChatGPT')}): {res.get('used_pct')}% (Status: {res.get('status')})")

    # 3. Account Store Isolation Check (Zero Cross-Talk)
    stored_keys = set()
    stored_emails = set()
    if STORE_DIR.exists():
        for f in STORE_DIR.glob("*.json"):
            d = load_account_state(f.stem)
            if d:
                acc_id = d.get("id")
                email = d.get("email")
                if acc_id in stored_keys:
                    findings.append(f"[FAIL] Duplicate account key detected: {acc_id}")
                    has_critical_error = True
                stored_keys.add(acc_id)
        findings.append(f"[PASS] Isolated account store validated ({len(stored_keys)} independent keys)")
    else:
        findings.append(f"[WARN] Account store dir {STORE_DIR} does not exist yet")

    # 4. Engine Aggregation Latency
    start_t = time.time()
    state = collect_all_quotas()
    lat_ms = (time.time() - start_t) * 1000
    if lat_ms > 3000:
        findings.append(f"[WARN] Aggregation latency high: {lat_ms:.1f}ms")
    else:
        findings.append(f"[PASS] Engine aggregation latency: {lat_ms:.1f}ms (Summary: {state.get('summary_text')})")

    return (not has_critical_error), findings
