#!/usr/bin/env python3
"""Desktop Floating HUD Overlay for AI Quotas (GTK4 - Resizable & Compact Mode)."""
import json
import os
import sys
import time
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import fcntl
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("GLib", "2.0")
from gi.repository import Gtk, GLib, Gdk

def acquire_single_instance_lock(name: str):
    """Enforce strictly 1 instance running to prevent window duplication/spillover."""
    lock_file = Path(f"/tmp/{name}.lock")
    lock_fd = open(lock_file, "a+")
    for attempt in range(6):
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            lock_fd.truncate(0)
            lock_fd.write(str(os.getpid()))
            lock_fd.flush()
            return lock_fd
        except (IOError, BlockingIOError):
            try:
                lock_fd.seek(0)
                pid_str = lock_fd.read().strip()
                if pid_str:
                    old_pid = int(pid_str)
                    if old_pid != os.getpid():
                        os.kill(old_pid, 9)
            except Exception:
                pass
            time.sleep(0.25)
    return lock_fd

# Acquire lock before anything else
_LOCK = acquire_single_instance_lock("ai-quota-hud")

STATE_FILE = Path.home() / ".config" / "ai-quota-overlay" / "state.json"

CSS_DATA = b"""
window.ai-hud-window {
    background-color: #090d16;
    border: 1px solid #334155;
    border-radius: 14px;
    box-shadow: 0 20px 50px rgba(0, 0, 0, 0.9);
}

.hud-handle {
    background-color: #0f172a;
    border-bottom: 1px solid #1e293b;
    border-top-left-radius: 14px;
    border-top-right-radius: 14px;
}

.hud-header-inner {
    padding: 8px 12px;
}

.hud-title {
    font-size: 12px;
    font-weight: 900;
    color: #ffffff;
    letter-spacing: 0.5px;
}

.hud-drag-hint {
    font-size: 11px;
    color: #94a3b8;
    margin-left: 2px;
}

/* Base Button Styling Override */
button {
    background-image: none;
    background-color: #1e293b;
    border: 1px solid #475569;
    color: #ffffff;
    box-shadow: none;
    text-shadow: none;
    border-radius: 6px;
}

button label {
    color: #ffffff;
    font-weight: 700;
}

button:hover {
    background-color: #334155;
    border-color: #38bdf8;
}

button:hover label {
    color: #38bdf8;
}

/* Header Buttons */
button.hud-action-btn {
    background-color: #1e293b;
    border: 1px solid #475569;
    color: #ffffff;
    font-size: 11px;
    font-weight: 700;
    padding: 3px 8px;
    border-radius: 6px;
}

button.hud-action-btn label {
    color: #ffffff;
    font-weight: 700;
}

button.hud-action-btn:hover {
    background-color: #334155;
    border-color: #38bdf8;
}

button.hud-action-btn:hover label {
    color: #38bdf8;
}

button.hud-action-btn-active {
    background-color: #2563eb;
    border: 1px solid #60a5fa;
    color: #ffffff;
}

button.hud-action-btn-active label {
    color: #ffffff;
}

button.hud-close-btn {
    background-color: transparent;
    border: none;
    color: #cbd5e1;
    font-size: 13px;
    font-weight: 900;
    padding: 2px 6px;
    border-radius: 5px;
}

button.hud-close-btn label {
    color: #cbd5e1;
}

button.hud-close-btn:hover {
    background-color: #dc2626;
    color: #ffffff;
}

button.hud-close-btn:hover label {
    color: #ffffff;
}

/* Full View Cards */
.hud-card {
    background-color: #131b2e;
    border: 1px solid #293548;
    border-radius: 10px;
    padding: 8px 10px;
    margin-bottom: 4px;
}

.hud-account-name {
    font-size: 13px;
    font-weight: 800;
    color: #ffffff;
}

.hud-badge {
    font-size: 10px;
    font-weight: 900;
    padding: 2px 6px;
    border-radius: 4px;
    background-color: #334155;
    color: #f8fafc;
    border: 1px solid #475569;
}

/* Usage & Detail Typography */
.sub-label {
    font-size: 13px;
    font-weight: 800;
    color: #38bdf8;
}

.warning-label {
    font-size: 13px;
    font-weight: 900;
    color: #fbbf24;
}

.critical-label {
    font-size: 13px;
    font-weight: 900;
    color: #f87171;
}

.dim-label {
    font-size: 12px;
    color: #64748b;
    font-style: italic;
}

.hud-reset {
    font-size: 12px;
    font-weight: 800;
    color: #facc15;
}

.hud-subtext {
    font-size: 11px;
    font-weight: 600;
    color: #cbd5e1;
}

/* Compact Mode Styling */
.hud-compact-box {
    padding: 6px 10px;
}

.hud-compact-row {
    background-color: #131b2e;
    border: 1px solid #293548;
    border-radius: 8px;
    padding: 6px 10px;
    margin-bottom: 4px;
}

.hud-compact-label {
    font-size: 12px;
    font-weight: 800;
    color: #ffffff;
}

.hud-compact-reset {
    font-size: 11px;
    font-weight: 700;
    color: #facc15;
}

.hud-compact-na {
    font-size: 11px;
    color: #64748b;
    font-style: italic;
}

/* Progress Bars */
progressbar trough {
    background-color: #1e293b;
    border-radius: 4px;
    min-height: 7px;
}

progressbar.ok progress {
    background-color: #22c55e;
    border-radius: 4px;
    min-height: 7px;
}

progressbar.warning progress {
    background-color: #eab308;
    border-radius: 4px;
    min-height: 7px;
}

progressbar.critical progress {
    background-color: #ef4444;
    border-radius: 4px;
    min-height: 7px;
}

/* Footer & Resize Grip Styles */
.hud-footer-bar {
    background-color: #0f172a;
    border-top: 1px solid #1e293b;
    padding: 3px 10px;
    border-bottom-left-radius: 14px;
    border-bottom-right-radius: 14px;
}

.hud-footer-text {
    font-size: 11px;
    font-weight: 700;
    color: #64748b;
}

.hud-resize-grip {
    color: #94a3b8;
    font-size: 14px;
    font-weight: 900;
    padding: 0 4px;
}

.hud-resize-grip:hover {
    color: #38bdf8;
}

/* Settings View Styles */
.hud-settings-box {
    padding: 8px 10px;
}

.hud-settings-title {
    font-size: 14px;
    font-weight: 900;
    color: #38bdf8;
    margin-bottom: 2px;
}

.hud-settings-card {
    background-color: #131b2e;
    border: 1px solid #293548;
    border-radius: 10px;
    padding: 10px 12px;
    margin-bottom: 8px;
}

.hud-settings-label {
    font-size: 12px;
    font-weight: 800;
    color: #ffffff;
}

.hud-settings-desc {
    font-size: 11px;
    font-weight: 500;
    color: #cbd5e1;
}

.hud-priority-name {
    font-size: 12px;
    font-weight: 700;
    color: #f8fafc;
}

button.hud-save-btn {
    background-color: #2563eb;
    border: 1px solid #3b82f6;
    color: #ffffff;
    font-size: 12px;
    font-weight: 800;
    border-radius: 8px;
    padding: 8px 16px;
    min-height: 34px;
}

button.hud-save-btn label {
    color: #ffffff;
    font-weight: 800;
}

button.hud-save-btn:hover {
    background-color: #1d4ed8;
    border-color: #60a5fa;
}

button.hud-arrow-btn {
    background-color: #1e293b;
    border: 1px solid #475569;
    color: #ffffff;
    font-size: 11px;
    font-weight: 900;
    border-radius: 6px;
    padding: 3px 8px;
    min-width: 28px;
    min-height: 24px;
}

button.hud-arrow-btn label {
    color: #ffffff;
    font-weight: 900;
}

button.hud-arrow-btn:hover {
    background-color: #334155;
    border-color: #38bdf8;
}

button.hud-arrow-btn:hover label {
    color: #38bdf8;
}
"""


def format_short_name(account_name: str) -> str:
    """Shorten name for compact mode without losing account distinction."""
    if "@" in account_name:
        parts = account_name.split("(")
        user_part = parts[1].split("@")[0] if len(parts) > 1 and "@" in parts[1] else account_name
        return f"Claude ({user_part})"
    return (account_name
            .replace("Claude (Primary)", "Claude (1)")
            .replace("Claude (Secondary)", "Claude (2)")
            .replace("Antigravity (IDE)", "Antigrav (IDE)")
            .replace("Antigravity (CLI)", "Antigrav (CLI)")
            .replace("Codex (ChatGPT)", "Codex (GPT)"))


class AIQuotaHUD(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="AI Quotas Overlay")

        from backend.config_manager import load_config, save_config
        self.config = load_config()
        ui_cfg = self.config.get("ui", {})
        self.saved_full_width = int(ui_cfg.get("window_width", 340))
        self.saved_full_height = int(ui_cfg.get("window_height", 460))
        self.saved_compact_width = int(ui_cfg.get("compact_width", 310))
        self.saved_compact_height = int(ui_cfg.get("compact_height", 220))

        self.set_default_size(self.saved_full_width, self.saved_full_height)
        self.set_resizable(True)
        self.set_decorated(False)
        self.add_css_class("ai-hud-window")

        self.is_compact = False
        self.connect("close-request", self._on_close_save_geometry)

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

        # Settings / Policy Button
        self.settings_btn = Gtk.Button(label="⚙️")
        self.settings_btn.add_css_class("hud-action-btn")
        self.settings_btn.connect("clicked", self._toggle_settings)
        header_box.append(self.settings_btn)

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

        # Settings View Scroll Container (Hidden by default)
        self.is_settings = False
        self.settings_scrolled = Gtk.ScrolledWindow()
        self.settings_scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.settings_scrolled.set_vexpand(True)
        self.settings_scrolled.set_hexpand(True)
        self.settings_scrolled.set_visible(False)

        self.settings_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.settings_box.add_css_class("hud-settings-box")
        self.settings_box.set_margin_top(8)
        self.settings_box.set_margin_bottom(8)
        self.settings_box.set_margin_start(10)
        self.settings_box.set_margin_end(10)
        self.settings_scrolled.set_child(self.settings_box)
        self.main_box.append(self.settings_scrolled)

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

        # Bottom Footer Bar with Interactive Resize Grips
        self.footer_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.footer_bar.add_css_class("hud-footer-bar")

        footer_lbl = Gtk.Label(label="🎯 QuotaPulse")
        footer_lbl.add_css_class("hud-footer-text")
        footer_lbl.set_halign(Gtk.Align.START)
        footer_lbl.set_hexpand(True)
        self.footer_bar.append(footer_lbl)

        # Bottom Edge Resize Handle
        bottom_handle = Gtk.Box()
        bottom_handle.set_hexpand(True)
        self._attach_resize_gesture(bottom_handle, Gdk.SurfaceEdge.SOUTH, "s-resize")
        self.footer_bar.append(bottom_handle)

        # Bottom-Right Corner Resize Grip (◢)
        self.resize_grip = Gtk.Label(label="◢")
        self.resize_grip.add_css_class("hud-resize-grip")
        self.resize_grip.set_halign(Gtk.Align.END)
        self._attach_resize_gesture(self.resize_grip, Gdk.SurfaceEdge.SOUTH_EAST, "se-resize")
        self.footer_bar.append(self.resize_grip)

        self.main_box.append(self.footer_bar)

        # Load initial data
        self.update_ui()

        # Update timer (every 5 seconds)
        GLib.timeout_add_seconds(5, self.update_ui)

    def _attach_resize_gesture(self, widget, edge, cursor_name):
        """Attach native Wayland/X11 interactive window resizing gesture to a widget."""
        gesture = Gtk.GestureClick.new()
        gesture.set_button(1)

        def _on_pressed(g, n_press, x, y):
            surface = self.get_surface()
            if surface and isinstance(surface, Gdk.Toplevel):
                surface.begin_resize(
                    edge,
                    g.get_device(),
                    1,
                    int(x),
                    int(y),
                    g.get_current_event_time()
                )

        gesture.connect("pressed", _on_pressed)
        widget.add_controller(gesture)

        # Set cursor on hover
        widget.set_cursor_from_name(cursor_name)

    def _toggle_settings(self, btn):
        self.is_settings = not self.is_settings
        if self.is_settings:
            self.settings_btn.add_css_class("hud-action-btn-active")
            self.scrolled.set_visible(False)
            self.compact_box.set_visible(False)
            self.settings_scrolled.set_visible(True)
            self._render_settings_view()
        else:
            self.settings_btn.remove_css_class("hud-action-btn-active")
            self.settings_scrolled.set_visible(False)
            if self.is_compact:
                self.compact_box.set_visible(True)
            else:
                self.scrolled.set_visible(True)
            self.update_ui()

    def _render_settings_view(self):
        while self.settings_box.get_first_child():
            self.settings_box.remove(self.settings_box.get_first_child())

        from backend.config_manager import load_config, save_config
        from backend.relay_router import select_best_account

        config = load_config()
        policy = config.get("routing_policy", {})
        switch_thresh = float(policy.get("switch_threshold_pct", 80.0))
        chain = list(policy.get("fallback_chain", ["claude_primary", "claude_secondary", "antigravity_cli", "codex_primary"]))
        strategy = policy.get("strategy", "claude_first_relay")

        best_acc, reason, _ = select_best_account()

        # 1. Title & Active Target Banner
        header = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        title = Gtk.Label(label="⚙️ ROUTING & PRIORITIES")
        title.add_css_class("hud-settings-title")
        title.set_halign(Gtk.Align.START)
        header.append(title)

        target_banner = Gtk.Label(label=f"🎯 Next Target: {best_acc.get('name', 'Claude')}")
        target_banner.add_css_class("hud-settings-label")
        target_banner.set_halign(Gtk.Align.START)
        header.append(target_banner)
        self.settings_box.append(header)

        # 2. Switch Threshold Slider
        thresh_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        thresh_card.add_css_class("hud-settings-card")

        t_lbl_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        t_lbl = Gtk.Label(label="Switch Threshold:")
        t_lbl.add_css_class("hud-settings-label")
        t_lbl_box.append(t_lbl)

        val_lbl = Gtk.Label(label=f"{switch_thresh:.1f}%")
        val_lbl.add_css_class("hud-reset")
        val_lbl.set_halign(Gtk.Align.END)
        val_lbl.set_hexpand(True)
        t_lbl_box.append(val_lbl)
        thresh_card.append(t_lbl_box)

        scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 1.0, 95.0, 1.0)
        scale.set_value(switch_thresh)
        scale.set_hexpand(True)
        def _on_scale_val(s):
            val_lbl.set_text(f"{s.get_value():.1f}%")
        scale.connect("value-changed", _on_scale_val)
        thresh_card.append(scale)

        desc = Gtk.Label(label="Auto-switches to backup when active model reaches this cap.")
        desc.add_css_class("hud-settings-desc")
        desc.set_halign(Gtk.Align.START)
        thresh_card.append(desc)
        self.settings_box.append(thresh_card)

        # 3. Priority Chain List
        p_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        p_card.add_css_class("hud-settings-card")

        p_title = Gtk.Label(label="Priority Chain (Order of Failover):")
        p_title.add_css_class("hud-settings-label")
        p_title.set_halign(Gtk.Align.START)
        p_card.append(p_title)

        names = {
            "claude_primary": "🟣 Claude (Primary)",
            "claude_secondary": "🟣 Claude (Secondary)",
            "antigravity_cli": "⚡ Antigravity (CLI)",
            "codex_primary": "🟢 Codex (ChatGPT)"
        }

        for idx, cid in enumerate(chain):
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            r_name = Gtk.Label(label=f"{idx+1}. {names.get(cid, cid)}")
            r_name.add_css_class("hud-priority-name")
            r_name.set_hexpand(True)
            r_name.set_halign(Gtk.Align.START)
            row.append(r_name)

            if idx > 0:
                up_btn = Gtk.Button(label="▲")
                up_btn.add_css_class("hud-arrow-btn")
                def _move_up(b, i=idx):
                    chain[i], chain[i-1] = chain[i-1], chain[i]
                    policy["fallback_chain"] = chain
                    config["routing_policy"] = policy
                    save_config(config)
                    self._render_settings_view()
                up_btn.connect("clicked", _move_up)
                row.append(up_btn)

            if idx < len(chain) - 1:
                down_btn = Gtk.Button(label="▼")
                down_btn.add_css_class("hud-arrow-btn")
                def _move_down(b, i=idx):
                    chain[i], chain[i+1] = chain[i+1], chain[i]
                    policy["fallback_chain"] = chain
                    config["routing_policy"] = policy
                    save_config(config)
                    self._render_settings_view()
                down_btn.connect("clicked", _move_down)
                row.append(down_btn)

            p_card.append(row)

        self.settings_box.append(p_card)

        # 4. Emergency Failover Mode Card
        failover_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        failover_card.add_css_class("hud-settings-card")

        fo_title = Gtk.Label(label="Emergency Failover Mode (When Claude Capped):")
        fo_title.add_css_class("hud-settings-label")
        fo_title.set_halign(Gtk.Align.START)
        failover_card.append(fo_title)

        curr_mode = policy.get("emergency_failover_mode", "transparent_proxy")
        self.selected_failover_mode = curr_mode

        mode_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)

        opt_a_btn = Gtk.Button(label="🔵 Option A: Transparent Proxy (Never leave Claude)")
        opt_b_btn = Gtk.Button(label="🚀 Option B: Native Handoff (Switch to Antigravity CLI)")

        if curr_mode == "transparent_proxy":
            opt_a_btn.add_css_class("hud-action-btn-active")
            opt_b_btn.add_css_class("hud-action-btn")
        else:
            opt_b_btn.add_css_class("hud-action-btn-active")
            opt_a_btn.add_css_class("hud-action-btn")

        mode_desc = Gtk.Label()
        mode_desc.add_css_class("hud-settings-desc")
        mode_desc.set_halign(Gtk.Align.START)

        def _update_desc():
            if self.selected_failover_mode == "transparent_proxy":
                mode_desc.set_text("Default: Seamlessly proxies Gemini into your active Claude prompt without exiting.")
            else:
                mode_desc.set_text("Opens Antigravity native CLI with full Michael harness rules & subagents.")

        _update_desc()

        def _select_a(b):
            self.selected_failover_mode = "transparent_proxy"
            opt_a_btn.add_css_class("hud-action-btn-active")
            opt_a_btn.remove_css_class("hud-action-btn")
            opt_b_btn.remove_css_class("hud-action-btn-active")
            opt_b_btn.add_css_class("hud-action-btn")
            _update_desc()

        def _select_b(b):
            self.selected_failover_mode = "native_handoff"
            opt_b_btn.add_css_class("hud-action-btn-active")
            opt_b_btn.remove_css_class("hud-action-btn")
            opt_a_btn.remove_css_class("hud-action-btn-active")
            opt_a_btn.add_css_class("hud-action-btn")
            _update_desc()

        opt_a_btn.connect("clicked", _select_a)
        opt_b_btn.connect("clicked", _select_b)

        mode_box.append(opt_a_btn)
        mode_box.append(opt_b_btn)
        mode_box.append(mode_desc)
        failover_card.append(mode_box)
        self.settings_box.append(failover_card)

        # 5. Save Button
        save_btn = Gtk.Button(label="💾 Save & Apply Policy")
        save_btn.add_css_class("hud-save-btn")
        def _save(b):
            policy["switch_threshold_pct"] = round(scale.get_value(), 1)
            policy["fallback_chain"] = chain
            policy["emergency_failover_mode"] = getattr(self, "selected_failover_mode", "transparent_proxy")
            config["routing_policy"] = policy
            save_config(config)
            save_btn.set_label("✓ Applied!")
            GLib.timeout_add_seconds(1, lambda: save_btn.set_label("💾 Save & Apply Policy"))
            # Update target banner
            new_best, _, _ = select_best_account()
            target_banner.set_text(f"🎯 Next Target: {new_best.get('name', 'Claude')}")
        save_btn.connect("clicked", _save)
        self.settings_box.append(save_btn)

    def _save_dimensions(self):
        try:
            from backend.config_manager import load_config, save_config
            cfg = load_config()
            if "ui" not in cfg:
                cfg["ui"] = {}
            cfg["ui"]["window_width"] = self.saved_full_width
            cfg["ui"]["window_height"] = self.saved_full_height
            cfg["ui"]["compact_width"] = self.saved_compact_width
            cfg["ui"]["compact_height"] = self.saved_compact_height
            save_config(cfg)
        except Exception as e:
            print("Save dimensions error:", e)

    def _on_close_save_geometry(self, window):
        w = self.get_width()
        h = self.get_height()
        if w > 100 and h > 100:
            if self.is_compact:
                self.saved_compact_width = w
                self.saved_compact_height = h
            else:
                self.saved_full_width = w
                self.saved_full_height = h
            self._save_dimensions()
        return False

    def _toggle_compact(self, btn):
        # Save current mode dimension before swapping
        w = self.get_width()
        h = self.get_height()
        if w > 100 and h > 100:
            if self.is_compact:
                self.saved_compact_width = w
                self.saved_compact_height = h
            else:
                self.saved_full_width = w
                self.saved_full_height = h
            self._save_dimensions()

        if self.is_settings:
            self._toggle_settings(None)

        self.is_compact = not self.is_compact
        if self.is_compact:
            self.compact_btn.set_label("◫ Full")
            self.compact_btn.add_css_class("hud-action-btn-active")
            self.scrolled.set_visible(False)
            self.compact_box.set_visible(True)
            self.set_default_size(self.saved_compact_width, self.saved_compact_height)
        else:
            self.compact_btn.set_label("◰ Compact")
            self.compact_btn.remove_css_class("hud-action-btn-active")
            self.compact_box.set_visible(False)
            self.scrolled.set_visible(True)
            self.set_default_size(self.saved_full_width, self.saved_full_height)
        self.update_ui()

    def _on_refresh_clicked(self, btn):
        try:
            GLib.spawn_command_line_async("ai-quota-overlay refresh")
            GLib.timeout_add_seconds(1, self.update_ui)
        except Exception as e:
            print("Refresh error:", e)

    def update_ui(self):
        # Track live user resize events
        w = self.get_width()
        h = self.get_height()
        if w > 100 and h > 100:
            if self.is_compact:
                if w != self.saved_compact_width or h != self.saved_compact_height:
                    self.saved_compact_width = w
                    self.saved_compact_height = h
                    self._save_dimensions()
            else:
                if w != self.saved_full_width or h != self.saved_full_height:
                    self.saved_full_width = w
                    self.saved_full_height = h
                    self._save_dimensions()

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
                    reset_lbl = Gtk.Label(label=f"5h Resets: {reset_str}")
                    reset_lbl.add_css_class("hud-reset")
                    info_row.append(reset_lbl)
                card.append(info_row)

                # Distinct Weekly Limit Row for Claude
                if acc.get("weekly_used_pct") is not None and not is_not_configured:
                    weekly_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
                    w_used = float(acc.get("weekly_used_pct", 0.0))
                    w_lbl = Gtk.Label(label=f"📅 Weekly Limit: {w_used:.1f}% used")
                    w_lbl.add_css_class("hud-subtext")
                    w_lbl.set_halign(Gtk.Align.START)
                    w_lbl.set_hexpand(True)
                    weekly_row.append(w_lbl)

                    w_reset = acc.get("weekly_resets_human", "Sat 8:59 PM")
                    w_reset_lbl = Gtk.Label(label=f"Resets {w_reset}")
                    w_reset_lbl.add_css_class("hud-subtext")
                    weekly_row.append(w_reset_lbl)
                    card.append(weekly_row)

                # Extra details (Cost, Models)
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

            # 2. Update Compact View
            while self.compact_box.get_first_child():
                self.compact_box.remove(self.compact_box.get_first_child())

            for acc in all_accs:
                row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
                row.add_css_class("hud-compact-row")

                icon = icons.get(acc.get("service"), "🤖")
                used = float(acc.get("used_pct", 0.0))
                short_name = format_short_name(acc.get("name", "Account"))
                
                is_not_cfg = (acc.get("status") == "not_configured")

                # Label (e.g. 🟣 Claude (michael): 74% (Wk: 25%))
                if is_not_cfg:
                    lbl_text = f"{icon} {short_name}"
                else:
                    if acc.get("weekly_used_pct") is not None:
                        lbl_text = f"{icon} {short_name}: {used:.0f}% (Wk: {acc['weekly_used_pct']:.0f}%)"
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
                display, provider, Gtk.STYLE_PROVIDER_PRIORITY_USER
            )

        win = AIQuotaHUD(self)
        win.present()


if __name__ == "__main__":
    app = HUDApp()
    app.run(sys.argv)
