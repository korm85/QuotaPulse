#!/usr/bin/env python3
"""Desktop Floating HUD Overlay for AI Quotas (GTK4 - Resizable & Compact Mode)."""
import json
import os
import sys
import time
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("GLib", "2.0")
from gi.repository import Gtk, GLib, Gdk

STATE_FILE = Path.home() / ".config" / "ai-quota-overlay" / "state.json"

CSS_DATA = b"""
window.ai-hud-window {
    background-color: rgba(15, 18, 25, 0.94);
    border: 1px solid rgba(255, 255, 255, 0.18);
    border-radius: 14px;
    box-shadow: 0 16px 48px rgba(0, 0, 0, 0.75);
}

.hud-handle {
    background-color: rgba(255, 255, 255, 0.06);
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    border-top-left-radius: 14px;
    border-top-right-radius: 14px;
}

.hud-handle:active {
    background-color: rgba(255, 255, 255, 0.12);
}

.hud-header-inner {
    padding: 8px 12px;
}

.hud-title {
    font-size: 12px;
    font-weight: 800;
    color: #f8fafc;
    letter-spacing: 0.5px;
}

.hud-drag-hint {
    font-size: 10px;
    color: #64748b;
    margin-left: 2px;
}

.hud-action-btn {
    background-color: rgba(255, 255, 255, 0.08);
    border: none;
    color: #cbd5e1;
    font-size: 11px;
    font-weight: 600;
    padding: 2px 7px;
    border-radius: 5px;
}

.hud-action-btn:hover {
    background-color: rgba(255, 255, 255, 0.2);
    color: #ffffff;
}

.hud-action-btn-active {
    background-color: rgba(59, 130, 246, 0.35);
    color: #93c5fd;
    border: 1px solid rgba(147, 197, 253, 0.4);
}

.hud-close-btn {
    background: transparent;
    border: none;
    color: #94a3b8;
    font-size: 13px;
    font-weight: bold;
    padding: 2px 6px;
    border-radius: 5px;
}

.hud-close-btn:hover {
    background-color: rgba(239, 68, 68, 0.3);
    color: #f87171;
}

/* Full View Cards */
.hud-card {
    background-color: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.07);
    border-radius: 8px;
    padding: 8px 10px;
    margin-bottom: 4px;
}

.hud-account-name {
    font-size: 12px;
    font-weight: 700;
    color: #f1f5f9;
}

.hud-badge {
    font-size: 9px;
    font-weight: 800;
    padding: 1px 5px;
    border-radius: 4px;
    background-color: rgba(255, 255, 255, 0.12);
    color: #e2e8f0;
}

.hud-reset {
    font-size: 11px;
    font-weight: 700;
    color: #fde047;
}

.hud-subtext {
    font-size: 10px;
    color: #94a3b8;
}

/* Compact Mode Styling */
.hud-compact-box {
    padding: 6px 10px;
}

.hud-compact-row {
    background-color: rgba(255, 255, 255, 0.04);
    border-radius: 6px;
    padding: 5px 8px;
    margin-bottom: 4px;
}

.hud-compact-label {
    font-size: 11px;
    font-weight: 700;
    color: #f8fafc;
}

.hud-compact-reset {
    font-size: 10px;
    font-weight: 600;
    color: #facc15;
}

.hud-compact-na {
    font-size: 10px;
    color: #64748b;
    font-style: italic;
}

/* Progress Bars */
progressbar.ok trough {
    background-color: rgba(255, 255, 255, 0.08);
    border-radius: 3px;
    min-height: 6px;
}
progressbar.ok progress {
    background-color: #22c55e;
    border-radius: 3px;
    min-height: 6px;
}

progressbar.warning trough {
    background-color: rgba(255, 255, 255, 0.08);
    border-radius: 3px;
    min-height: 6px;
}
progressbar.warning progress {
    background-color: #eab308;
    border-radius: 3px;
    min-height: 6px;
}

progressbar.critical trough {
    background-color: rgba(255, 255, 255, 0.08);
    border-radius: 3px;
    min-height: 6px;
}
progressbar.critical progress {
    background-color: #ef4444;
    border-radius: 3px;
    min-height: 6px;
}
"""


def format_short_name(account_name: str) -> str:
    """Shorten name for compact mode without losing account distinction."""
    return (account_name
            .replace("Claude (Primary)", "Claude (1)")
            .replace("Claude (Secondary)", "Claude (2)")
            .replace("Antigravity (IDE)", "Antigrav (IDE)")
            .replace("Antigravity (CLI)", "Antigrav (CLI)")
            .replace("Codex (ChatGPT)", "Codex (GPT)"))


class AIQuotaHUD(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="AI Quotas Overlay")

        self.set_default_size(330, 440)
        self.set_resizable(True)
        self.set_decorated(False)
        self.add_css_class("ai-hud-window")

        self.is_compact = False

        # Main Layout Box
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_child(self.main_box)

        # Draggable Header (Gtk.WindowHandle)
        self.window_handle = Gtk.WindowHandle()
        self.window_handle.add_css_class("hud-handle")

        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        header_box.add_css_class("hud-header-inner")

        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        title = Gtk.Label(label="⚡ AI QUOTAS")
        title.add_css_class("hud-title")
        title_box.append(title)

        drag_hint = Gtk.Label(label="⋮⋮")
        drag_hint.add_css_class("hud-drag-hint")
        title_box.append(drag_hint)

        title_box.set_hexpand(True)
        title_box.set_halign(Gtk.Align.START)
        header_box.append(title_box)

        # Compact Toggle Button
        self.compact_btn = Gtk.Button(label="◰ Compact")
        self.compact_btn.add_css_class("hud-action-btn")
        self.compact_btn.connect("clicked", self._toggle_compact)
        header_box.append(self.compact_btn)

        # Refresh Button
        refresh_btn = Gtk.Button(label="🔄")
        refresh_btn.add_css_class("hud-action-btn")
        refresh_btn.connect("clicked", self._on_refresh_clicked)
        header_box.append(refresh_btn)

        # Close Button
        close_btn = Gtk.Button(label="✕")
        close_btn.add_css_class("hud-close-btn")
        close_btn.connect("clicked", lambda b: self.close())
        header_box.append(close_btn)

        self.window_handle.set_child(header_box)
        self.main_box.append(self.window_handle)

        # Full View Scroll Container
        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scrolled.set_vexpand(True)
        self.scrolled.set_hexpand(True)

        self.content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.content_box.set_margin_top(8)
        self.content_box.set_margin_bottom(8)
        self.content_box.set_margin_start(10)
        self.content_box.set_margin_end(10)
        self.scrolled.set_child(self.content_box)
        self.main_box.append(self.scrolled)

        # Compact View Container
        self.compact_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.compact_box.add_css_class("hud-compact-box")
        self.compact_box.set_visible(False)
        self.main_box.append(self.compact_box)

        # Load initial data
        self.update_ui()

        # Update timer (every 5 seconds)
        GLib.timeout_add_seconds(5, self.update_ui)

    def _toggle_compact(self, btn):
        self.is_compact = not self.is_compact
        if self.is_compact:
            self.compact_btn.set_label("◫ Full")
            self.compact_btn.add_css_class("hud-action-btn-active")
            self.scrolled.set_visible(False)
            self.compact_box.set_visible(True)
            self.set_default_size(310, 220)
        else:
            self.compact_btn.set_label("◰ Compact")
            self.compact_btn.remove_css_class("hud-action-btn-active")
            self.compact_box.set_visible(False)
            self.scrolled.set_visible(True)
            self.set_default_size(330, 440)
        self.update_ui()

    def _on_refresh_clicked(self, btn):
        try:
            GLib.spawn_command_line_async("ai-quota-overlay refresh")
            GLib.timeout_add_seconds(1, self.update_ui)
        except Exception as e:
            print("Refresh error:", e)

    def update_ui(self):
        if not STATE_FILE.exists():
            return True

        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)

            accounts = state.get("accounts", {})
            cl_accs = accounts.get("claude", [])
            ag_accs = accounts.get("antigravity", [])
            cx_accs = accounts.get("codex", [])
            cu_accs = accounts.get("cursor", [])

            icons = {"claude": "🟣", "antigravity": "⚡", "codex": "🟢", "cursor": "🖱️"}
            raw_accs = cl_accs + ag_accs + cx_accs + cu_accs
            # Filter out accounts that are not configured
            all_accs = [a for a in raw_accs if a.get("status") != "not_configured"]

            # 1. Update Full View (Cards)
            while self.content_box.get_first_child():
                self.content_box.remove(self.content_box.get_first_child())

            for acc in all_accs:
                card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
                card.add_css_class("hud-card")

                # Top row (Name + Badge)
                top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
                icon = icons.get(acc.get("service"), "🤖")
                name_lbl = Gtk.Label(label=f"{icon} {acc.get('name')}")
                name_lbl.add_css_class("hud-account-name")
                name_lbl.set_hexpand(True)
                name_lbl.set_halign(Gtk.Align.START)
                top_row.append(name_lbl)

                plan_lbl = Gtk.Label(label=acc.get("plan", "PRO"))
                plan_lbl.add_css_class("hud-badge")
                top_row.append(plan_lbl)
                card.append(top_row)

                # Progress Bar
                used = float(acc.get("used_pct", 0.0))
                status = acc.get("status")
                is_not_configured = (status == "not_configured")

                # Progress bar
                pbar = Gtk.ProgressBar()
                pbar.set_fraction(0.0 if is_not_configured else min(1.0, used / 100.0))
                pbar.add_css_class("quota-progress")
                if status == "rate_limited" or used >= 90:
                    pbar.add_css_class("critical")
                elif used >= 80:
                    pbar.add_css_class("warning")
                elif used >= 70:
                    pbar.add_css_class("caution")
                card.append(pbar)

                # Bottom info row
                info_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
                if is_not_configured:
                    usage_label = Gtk.Label(label="Not configured")
                    usage_label.add_css_class("dim-label")
                else:
                    warn_prefix = "⚠️ " if used >= 80 else ""
                    usage_label = Gtk.Label(label=f"{warn_prefix}{used:.1f}% used")
                    usage_label.add_css_class("warning-label" if used >= 80 else "sub-label")
                usage_label.set_halign(Gtk.Align.START)
                usage_label.set_hexpand(True)
                info_row.append(usage_label)

                reset_str = acc.get("resets_in_human")
                if reset_str and not is_not_configured:
                    reset_lbl = Gtk.Label(label=f"Resets: {reset_str}")
                    reset_lbl.add_css_class("hud-reset")
                    info_row.append(reset_lbl)
                card.append(info_row)

                # Extra details
                extra = []
                if acc.get("model"):
                    extra.append(f"Model: {acc.get('model')}")
                if acc.get("tokens_used") and acc.get("token_limit"):
                    k_u = round(acc["tokens_used"] / 1000)
                    k_l = round(acc["token_limit"] / 1000)
                    extra.append(f"{k_u}k/{k_l}k tok")
                if acc.get("cost_usd", 0) > 0:
                    extra.append(f"${acc['cost_usd']:.2f}")
                if acc.get("status") == "not_configured":
                    extra.append("Not configured")

                if extra:
                    extra_lbl = Gtk.Label(label=" • ".join(extra))
                    extra_lbl.add_css_class("hud-subtext")
                    extra_lbl.set_halign(Gtk.Align.START)
                    card.append(extra_lbl)

                self.content_box.append(card)

            # 2. Update Compact View (ALL 5 accounts preserved identically)
            while self.compact_box.get_first_child():
                self.compact_box.remove(self.compact_box.get_first_child())

            for acc in all_accs:
                row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
                row.add_css_class("hud-compact-row")

                icon = icons.get(acc.get("service"), "🤖")
                used = float(acc.get("used_pct", 0.0))
                short_name = format_short_name(acc.get("name", "Account"))
                
                is_not_cfg = (acc.get("status") == "not_configured")

                # Label (e.g. 🟣 Claude (1): 33%)
                if is_not_cfg:
                    lbl_text = f"{icon} {short_name}"
                else:
                    lbl_text = f"{icon} {short_name}: {used:.0f}%"

                lbl = Gtk.Label(label=lbl_text)
                lbl.add_css_class("hud-compact-label")
                lbl.set_hexpand(True)
                lbl.set_halign(Gtk.Align.START)
                row.append(lbl)

                # Mini progress bar
                fraction = max(0.0, min(1.0, used / 100.0))
                pbar = Gtk.ProgressBar()
                pbar.set_fraction(fraction)
                pbar.set_size_request(60, 6)
                if is_not_cfg:
                    pbar.set_fraction(0.0)
                    pbar.add_css_class("ok")
                elif acc.get("status") == "rate_limited" or used >= 90.0:
                    pbar.add_css_class("critical")
                elif used >= 70.0:
                    pbar.add_css_class("warning")
                else:
                    pbar.add_css_class("ok")
                row.append(pbar)

                # Timer / Status label
                if is_not_cfg:
                    r_lbl = Gtk.Label(label="Not setup")
                    r_lbl.add_css_class("hud-compact-na")
                else:
                    reset_str = acc.get("resets_in_human") or "N/A"
                    r_lbl = Gtk.Label(label=reset_str)
                    r_lbl.add_css_class("hud-compact-reset")
                row.append(r_lbl)

                self.compact_box.append(row)

        except Exception as e:
            print("HUD Update Error:", e, file=sys.stderr)

        return True


class HUDApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="ai.quota.hud")

    def do_activate(self):
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS_DATA)
        display = Gdk.Display.get_default()
        if display:
            Gtk.StyleContext.add_provider_for_display(
                display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

        win = AIQuotaHUD(self)
        win.present()


if __name__ == "__main__":
    app = HUDApp()
    app.run(sys.argv)
