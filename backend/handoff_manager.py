"""Lightweight Harness Handoff Manager.
Preserves active goals, sub-step progress, decisions, and git context across model switches.
"""
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

HANDOFF_FILENAME = ".ai-quota-handoff.json"


def get_handoff_file() -> Path:
    """Find repository root or fallback to user config for handoff store."""
    try:
        res = subprocess.run(["git", "rev-parse", "--show-toplevel"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        if res.returncode == 0 and res.stdout.strip():
            return Path(res.stdout.strip()) / ".git" / HANDOFF_FILENAME
    except Exception:
        pass
    
    # Fallback to config dir
    fallback_dir = Path.home() / ".config" / "ai-quota-overlay"
    fallback_dir.mkdir(parents=True, exist_ok=True)
    return fallback_dir / HANDOFF_FILENAME


def get_git_diff_summary() -> List[str]:
    """Get list of modified/uncommitted files."""
    try:
        res = subprocess.run(["git", "status", "--porcelain"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        if res.returncode == 0 and res.stdout.strip():
            return [line.strip() for line in res.stdout.strip().split("\n")[:10]]
    except Exception:
        pass
    return []


def save_handoff_checkpoint(
    active_goal: str,
    current_step: str,
    next_action: str,
    source_agent: str,
    target_agent: Optional[str] = None,
    constraints: Optional[List[str]] = None
) -> Path:
    """Save an actionable handoff checkpoint before switching models."""
    handoff_file = get_handoff_file()
    handoff_file.parent.mkdir(parents=True, exist_ok=True)

    data: Dict[str, Any] = {
        "version": 1,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source_agent": source_agent,
        "target_agent": target_agent,
        "active_goal": active_goal,
        "current_step": current_step,
        "next_action": next_action,
        "constraints": constraints or [],
        "uncommitted_files": get_git_diff_summary()
    }

    with open(handoff_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    return handoff_file


def load_handoff_checkpoint() -> Optional[Dict[str, Any]]:
    """Load latest handoff checkpoint."""
    handoff_file = get_handoff_file()
    if handoff_file.exists():
        try:
            with open(handoff_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None


def format_handoff_prompt(checkpoint: Dict[str, Any]) -> str:
    """Format checkpoint into a concise, token-efficient initialization prompt for the next agent."""
    goal = checkpoint.get("active_goal", "Ongoing task")
    step = checkpoint.get("current_step", "In progress")
    next_act = checkpoint.get("next_action", "Continue implementation")
    source = checkpoint.get("source_agent", "Previous model")
    constraints = checkpoint.get("constraints", [])
    files = checkpoint.get("uncommitted_files", [])

    lines = [
        f"🔄 [QUOTA HANDOFF from {source}]",
        f"• Active Goal: {goal}",
        f"• Current Step: {step}",
        f"• Immediate Next Action: {next_act}"
    ]

    if constraints:
        lines.append(f"• Invariants/Rules: {', '.join(constraints)}")

    if files:
        lines.append(f"• In-flight Files: {', '.join(files[:5])}")

    return "\n".join(lines)
