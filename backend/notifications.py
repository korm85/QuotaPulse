"""Cross-platform Desktop Notification Dispatcher."""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Set

from backend.platform_paths import get_appdata_dir

ALERT_HISTORY_FILE = get_appdata_dir() / "ai-quota-overlay" / "alerts_history.json"


def load_alert_history() -> Dict[str, float]:
    """Load timestamps of already fired alerts to prevent spam."""
    if ALERT_HISTORY_FILE.exists():
        try:
            with open(ALERT_HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_alert_history(history: Dict[str, float]):
    """Save alert history."""
    try:
        ALERT_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(ALERT_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)
    except Exception:
        pass


def send_system_notification(title: str, message: str, urgency: str = "normal"):
    """Send native OS desktop notification on Linux and Windows."""
    if sys.platform == "win32":
        # Windows PowerShell notification
        ps_cmd = f"""
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
        $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
        $textNodes = $template.GetElementsByTagName('text')
        $textNodes.Item(0).AppendChild($template.CreateTextNode('{title}')) > $null
        $textNodes.Item(1).AppendChild($template.CreateTextNode('{message}')) > $null
        $notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('AI Quotas')
        $notification = [Windows.UI.Notifications.ToastNotification]::new($template)
        $notifier.Show($notification)
        """
        try:
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=4)
        except Exception:
            pass
    else:
        # Linux notify-send
        notify_send = shutil.which("notify-send")
        if notify_send:
            try:
                urgency_flag = "critical" if urgency == "critical" else "normal"
                cmd = [
                    notify_send,
                    "-u", urgency_flag,
                    "-a", "AI Quotas",
                    "-i", "dialog-warning",
                    title,
                    message
                ]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=4)
            except Exception:
                pass


def check_and_notify_quotas(all_accounts: list, warning_threshold: float = 80.0, critical_threshold: float = 90.0):
    """Check account quotas and fire notifications when thresholds are crossed."""
    history = load_alert_history()
    now = time.time()
    # Reset alert history if more than 4 hours passed since last alert
    cleaned_history = {k: v for k, v in history.items() if (now - v) < 14400}

    for acc in all_accounts:
        acc_id = acc.get("id", "unknown")
        acc_name = acc.get("name", "Model")
        used_pct = float(acc.get("used_pct", 0.0))
        resets = acc.get("resets_in_human") or "soon"
        status = acc.get("status")

        if status not in ("ok", "rate_limited"):
            continue

        # Critical alert (>= 90%)
        if used_pct >= critical_threshold:
            alert_key = f"{acc_id}_critical_90"
            if alert_key not in cleaned_history:
                send_system_notification(
                    f"🚨 Critical Quota: {acc_name} at {used_pct:.0f}%!",
                    f"Rate limit nearly exhausted ({used_pct:.1f}% used). Resets in {resets}.",
                    urgency="critical"
                )
                cleaned_history[alert_key] = now

        # Warning alert (>= 80%)
        elif used_pct >= warning_threshold:
            alert_key = f"{acc_id}_warning_80"
            if alert_key not in cleaned_history:
                send_system_notification(
                    f"⚠️ Quota Warning: {acc_name} approaching {used_pct:.0f}%!",
                    f"{used_pct:.1f}% quota used. Resets in {resets}.",
                    urgency="normal"
                )
                cleaned_history[alert_key] = now

    save_alert_history(cleaned_history)
