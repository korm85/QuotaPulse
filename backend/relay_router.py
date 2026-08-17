"""Smart Quota Relay Router.
Evaluates live account capacities and determines optimal model routing.
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.config_manager import load_config, DEFAULT_STATE_FILE
from backend.handoff_manager import load_handoff_checkpoint, format_handoff_prompt


def calculate_readiness_score(account: Dict[str, Any]) -> float:
    """Calculate time-paced readiness score (0-200). Higher = more ready to take work."""
    status = account.get("status")
    if status == "not_configured":
        return -100.0
    if status == "rate_limited":
        return 0.0

    used_pct = float(account.get("used_pct", 0.0))
    remaining_pct = max(0.0, 100.0 - used_pct)

    # Factor in reset countdown
    rem_secs = float(account.get("resets_in_seconds", 18000) or 18000)
    elapsed_in_window = max(0.0, min(18000.0, 18000.0 - rem_secs))
    time_weight = 1.0 + (elapsed_in_window / 18000.0)

    return round(remaining_pct * time_weight, 2)


def select_best_account() -> Tuple[Dict[str, Any], str, List[Dict[str, Any]]]:
    """Select the optimal model based on routing policy and live quotas.
    Returns: (selected_account, selection_reason, candidate_rankings)
    """
    config = load_config()
    policy = config.get("routing_policy", {})
    switch_thresh = float(policy.get("switch_threshold_pct", 80.0))
    chain = policy.get("fallback_chain", ["claude_primary", "claude_secondary", "antigravity_cli", "codex_primary"])

    if not DEFAULT_STATE_FILE.exists():
        from backend.quota_engine import collect_all_quotas
        state = collect_all_quotas()
    else:
        with open(DEFAULT_STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)

    all_accounts = state.get("all_accounts", [])
    acc_map = {a.get("id"): a for a in all_accounts}

    # Evaluate chain in priority order
    candidates = []
    for cid in chain:
        acc = acc_map.get(cid)
        if not acc:
            continue
        score = calculate_readiness_score(acc)
        used = float(acc.get("used_pct", 0.0))
        status = acc.get("status")

        is_eligible = (status in ("ok", "idle")) and (used < switch_thresh)
        candidates.append({
            "id": cid,
            "name": acc.get("name"),
            "service": acc.get("service"),
            "used_pct": used,
            "resets_in": acc.get("resets_in_human", "N/A"),
            "score": score,
            "eligible": is_eligible,
            "account_data": acc
        })

    # Find first eligible candidate in the priority chain
    for cand in candidates:
        if cand["eligible"]:
            reason = f"Primary eligible in chain (Usage: {cand['used_pct']}%, Score: {cand['score']})"
            return cand["account_data"], reason, candidates

    # If all exceed switch threshold, pick candidate with highest readiness score
    sorted_by_score = sorted([c for c in candidates if c["account_data"].get("status") != "not_configured"], key=lambda x: x["score"], reverse=True)
    if sorted_by_score:
        best = sorted_by_score[0]
        reason = f"All models exceeded {switch_thresh}% threshold. Selected highest readiness score ({best['score']}) with shortest reset."
        return best["account_data"], reason, candidates

    # Fallback to first available account
    default_acc = all_accounts[0] if all_accounts else {}
    return default_acc, "Fallback to default account", candidates


def get_agent_launch_command(account: Dict[str, Any], prompt_args: Optional[List[str]] = None) -> Tuple[List[str], Dict[str, str]]:
    """Build exact command line and environment to launch the selected agent."""
    service = account.get("service")
    acc_id = account.get("id")
    env = os.environ.copy()
    args = prompt_args or []

    # Inject handoff prompt if checkpoint exists
    checkpoint = load_handoff_checkpoint()
    handoff_text = format_handoff_prompt(checkpoint) if checkpoint else ""

    if service == "claude":
        claude_bin = shutil.which("claude") or "claude"
        if acc_id == "claude_secondary":
            env["CLAUDE_CONFIG_DIR"] = str(Path.home() / ".claude-secondary")
        
        cmd = [claude_bin]
        if args:
            cmd.extend(args)
        return cmd, env

    elif service == "antigravity":
        agy_bin = shutil.which("agy") or str(Path.home() / ".local" / "bin" / "agy")
        cmd = [agy_bin]
        if args:
            cmd.extend(["--prompt", " ".join(args)])
        return cmd, env

    elif service == "codex":
        codex_bin = shutil.which("codex") or "codex"
        cmd = [codex_bin]
        if args:
            cmd.extend(args)
        return cmd, env

    return ["echo", f"Launching {account.get('name')}"], env
