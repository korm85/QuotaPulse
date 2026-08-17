# AI Quota Overlay ⚡

A real-time desktop overlay, floating HUD, and top bar taskbar monitor for AI coding agents.

Keep track of your live token usage, rate limits, costs, and rolling window reset countdowns across **Claude**, **Google Antigravity**, **OpenAI Codex (ChatGPT)**, and **Cursor IDE** directly from your desktop.

---

![AI Quotas Demo](https://raw.githubusercontent.com/MichaelGavanAI/ai-quota-overlay/main/hud/preview.png) *(Preview)*

---

## 🚀 Key Features

- **🖥️ Floating Desktop HUD**:
  - Always-on-top translucent dark glass widget.
  - Resizable and draggable on both Wayland and X11.
  - **1-Click Compact / Full View**: Switch between compact chip rows and detailed usage cards with progress bars.
- **📊 Top Bar Taskbar Multi-Chips**:
  - Direct, glanceable chips embedded in the top bar: `[🟣 CL: 52%]` `[⚡ AG: 31%]` `[🟢 CX: 0%]`.
  - Color-coded per service with live percentages and real-time reset timers.
- **🔍 Zero-Config Auto-Detection**:
  - **Claude**: Auto-detects **Claude Code** session logs and **Claude Desktop** Electron local storage.
  - **Google Antigravity**: Auto-detects active CLI conversations, step counts, and Gemini 5-hour rolling pool limits.
  - **OpenAI Codex / ChatGPT**: Auto-queries live rate limits and plan tiers using local session tokens.
  - **Cursor IDE**: Reads local session tokens to track Fast Requests (`used / 500`) and monthly billing cycles.
- **🔔 Smart Quota Alerts**:
  - Native system notifications (`notify-send` on Linux / Windows Action Center Toasts) when any model reaches **≥ 80%** (Warning) or **≥ 90%** (Critical).
  - Anti-spam debounce prevents repeated alerts within the same reset window.
- **🪟 Cross-Platform Support**:
  - Native GTK4 & GNOME StatusNotifier integration on Ubuntu / Linux.
  - Standalone PyQt6 frameless HUD and 1-click batch launcher on Windows 10/11.

---

## Supported AI Services

| AI Agent | Supported Flavors | Metrics Tracked |
|---|---|---|
| **🟣 Claude** | Claude Code CLI & Claude Desktop App | Rolling 5h tokens, token limit, total cost ($), burn rate ($/hr), model distribution (Sonnet/Haiku/Opus), reset timer |
| **⚡ Antigravity** | Antigravity CLI & Antigravity IDE | Active 5h Gemini pool usage (%), step counts, dynamic rolling reset countdown |
| **🟢 Codex** | Codex CLI & ChatGPT Session | Production rate limit usage (%), plan tier (`FREE` / `PLUS` / `PRO`), reset epoch |
| **🖱️ Cursor** | Cursor IDE | Fast Requests used vs limit (`125 / 500`), slow requests, monthly billing period reset |

---

## 🐧 Quick Start on Linux (Ubuntu / GNOME / Wayland)

### 1. Clone and Install
```bash
git clone https://github.com/MichaelGavanAI/ai-quota-overlay.git
cd ai-quota-overlay
pip install --user -r requirements.txt
```

### 2. Launch
- **Floating Desktop HUD**:
  ```bash
  python3 hud/desktop_hud.py
  ```
- **Top Bar Taskbar Indicator**:
  ```bash
  python3 hud/topbar_indicator.py
  ```
- **Terminal Status Dashboard**:
  ```bash
  ./bin/ai-quota-overlay status
  ```

---

## 🪟 Quick Start on Windows

1. Download or clone this repository.
2. Double-click **`setup_windows.bat`**.
   - Automatically installs required dependencies (PyQt6).
   - Creates an **`AI Quotas`** shortcut on your Windows Desktop.
   - Enables autostart on Windows boot (`shell:startup`).
   - Launches the floating overlay.

---

## ⚙️ Configuration

Configuration is located at `~/.config/ai-quota-overlay/config.json` (or `%APPDATA%\ai-quota-overlay\config.json` on Windows):

```json
{
  "ui": {
    "show_reset_timer": true,
    "warning_threshold_pct": 80.0,
    "critical_threshold_pct": 90.0,
    "notifications_enabled": true
  },
  "polling": {
    "daemon_interval_seconds": 60,
    "hud_refresh_seconds": 5
  }
}
```

---

## 📄 License

MIT License. Free and open source.
