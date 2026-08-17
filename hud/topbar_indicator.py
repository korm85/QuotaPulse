#!/usr/bin/env python3
"""Multi-Chip Top Bar Taskbar Monitor for Ubuntu / GNOME.
Presents individual live chips on the top bar: [🟣 CL: 52%] [⚡ AG: 32%] [🟢 CX: 0%] [🖱️ CU: 0%]
"""
import json
import os
import struct
import subprocess
import sys
import time
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

import dbus
import fcntl
import dbus.service
import dbus.mainloop.glib
from gi.repository import GLib

# Add project root to sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.config_manager import DEFAULT_STATE_FILE
from backend.quota_engine import collect_all_quotas

def acquire_single_instance_lock(name: str):
    """Enforce strictly 1 instance running to prevent multi-screen top bar expansion."""
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
_LOCK = acquire_single_instance_lock("ai-quota-topbar")

dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

ICON_DIR = Path("/tmp/ai-quota-overlay-icons")
ICON_DIR.mkdir(parents=True, exist_ok=True)


def generate_chip_png(service_key: str, tag: str, pct_str: str, color_hex: str, width: int = 96, height: int = 34) -> str:
    """Generate high-DPI crisp compact PNG icon file on disk for GNOME top bar."""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Rounded pill container with colored border
    draw.rounded_rectangle([1, 1, width - 2, height - 2], radius=8, fill="#18181b", outline=color_hex, width=2)

    # Font setup
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 13)
    except Exception:
        font = ImageFont.load_default()

    full_text = f"{tag} {pct_str}"
    bbox = draw.textbbox((0, 0), full_text, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]

    # Draw centered text in bright white
    x_pos = (width - w) / 2
    y_pos = (height - h) / 2 - 1
    draw.text((x_pos, y_pos), full_text, font=font, fill="#ffffff")

    out_file = ICON_DIR / f"chip_{service_key}.png"
    img.save(out_file)
    return f"chip_{service_key}"


class ChipDBusMenu(dbus.service.Object):
    def __init__(self, bus, path, chip):
        super().__init__(bus, path)
        self.chip = chip
        self.revision = 1

    @dbus.service.method("org.freedesktop.DBus.Properties", in_signature="ss", out_signature="v")
    def Get(self, interface_name, property_name):
        return self.GetAll(interface_name).get(property_name, dbus.String(""))

    @dbus.service.method("org.freedesktop.DBus.Properties", in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface_name):
        if interface_name == "com.canonical.dbusmenu":
            return {
                "Version": dbus.UInt32(3),
                "version": dbus.UInt32(3),
                "TextDirection": dbus.String("ltr"),
                "text-direction": dbus.String("ltr"),
                "Status": dbus.String("normal"),
                "status": dbus.String("normal"),
                "IconThemePath": dbus.Array([str(ICON_DIR)], signature="s"),
                "icon-theme-path": dbus.Array([str(ICON_DIR)], signature="s")
            }
        return {}

    @dbus.service.method("com.canonical.dbusmenu", in_signature="iias", out_signature="u(ia{sv}av)")
    def GetLayout(self, parent_id, recursion_depth, property_names):
        return (self.revision, self.chip.get_menu_tree())

    @dbus.service.method("com.canonical.dbusmenu", in_signature="aias", out_signature="a(ia{sv})")
    def GetGroupProperties(self, ids, property_names):
        res = dbus.Array([], signature="(ia{sv})")
        # Return basic properties for requested ids
        for i in ids:
            pdict = dbus.Dictionary({"children-display": dbus.String("submenu") if i == 0 else dbus.String("")}, signature="sv")
            res.append(dbus.Struct((dbus.Int32(i), pdict), signature="(ia{sv})"))
        return res

    @dbus.service.method("com.canonical.dbusmenu", in_signature="i", out_signature="b")
    def AboutToShow(self, item_id):
        return dbus.Boolean(True)

    @dbus.service.method("com.canonical.dbusmenu", in_signature="isvu", out_signature="")
    def Event(self, item_id, event_id, data, timestamp):
        if event_id == "clicked":
            self.chip.handle_menu_click(item_id)

    @dbus.service.signal("com.canonical.dbusmenu", signature="uv")
    def LayoutUpdated(self, revision, parent):
        pass


class SingleChipIndicator(dbus.service.Object):
    def __init__(self, service_key: str, name: str, icon_tag: str, default_color: str, manager):
        self.service_key = service_key
        self.name = name
        self.icon_tag = icon_tag
        self.default_color = default_color
        self.manager = manager

        # Private bus connection per chip ensures clean object path registration
        self.bus = dbus.SessionBus(private=True)
        self.bus_name_str = f"org.kde.StatusNotifierItem-{os.getpid()}-{service_key}"
        self.bus_name = dbus.service.BusName(self.bus_name_str, self.bus)

        # Standard object path required by GNOME StatusNotifierWatcher
        super().__init__(self.bus, "/StatusNotifierItem")

        self.menu_path = "/MenuBar"
        self.dbus_menu = ChipDBusMenu(self.bus, self.menu_path, self)

        self.icon_name = "utilities-system-monitor"
        self.action_map = {}
        self.update_chip()

    @dbus.service.method("org.freedesktop.DBus.Properties", in_signature="ss", out_signature="v")
    def Get(self, interface_name, property_name):
        return self.GetAll(interface_name).get(property_name, "")

    @dbus.service.method("org.freedesktop.DBus.Properties", in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface_name):
        if interface_name in ("org.kde.StatusNotifierItem", "org.freedesktop.StatusNotifierItem"):
            return {
                "Category": "ApplicationStatus",
                "Id": f"ai-quota-{self.service_key}",
                "Title": f"{self.name} Quota",
                "Status": "Active",
                "WindowId": dbus.Int32(0),
                "IconName": self.icon_name,
                "IconThemePath": str(ICON_DIR),
                "OverlayIconName": "",
                "AttentionIconName": "dialog-warning",
                "AttentionMovieName": "",
                "ToolTip": dbus.Struct(
                    (self.icon_name, dbus.Array([], signature="(iiay)"), f"{self.name} Quota", self.get_tooltip()),
                    signature="sa(iiay)ss"
                ),
                "ItemIsMenu": True,
                "Menu": dbus.ObjectPath(self.menu_path)
            }
        return {}

    @dbus.service.method("org.kde.StatusNotifierItem", in_signature="ii", out_signature="")
    def Activate(self, x, y):
        self.manager.toggle_hud()

    @dbus.service.method("org.kde.StatusNotifierItem", in_signature="ii", out_signature="")
    def SecondaryActivate(self, x, y):
        self.manager.force_refresh()

    @dbus.service.method("org.kde.StatusNotifierItem", in_signature="ii", out_signature="")
    def ContextMenu(self, x, y):
        pass

    @dbus.service.signal("org.kde.StatusNotifierItem")
    def NewIcon(self):
        pass

    @dbus.service.signal("org.kde.StatusNotifierItem")
    def NewToolTip(self):
        pass

    def get_service_data(self):
        state = self.manager.state
        accounts = state.get("accounts", {}).get(self.service_key, [])
        return accounts

    def get_tooltip(self) -> str:
        accounts = self.get_service_data()
        if not accounts:
            return f"{self.name}: Not configured"
        lines = [f"{self.name} Quota:"]
        for a in accounts:
            used = a.get("used_pct", 0.0)
            resets = a.get("resets_in_human") or "N/A"
            lines.append(f"• {a.get('name')}: {used:.1f}% (Resets in {resets})")
        return "\n".join(lines)

    def update_chip(self):
        accounts = self.get_service_data()
        used_pcts = [float(a.get("used_pct", 0.0)) for a in accounts if a.get("status") in ("ok", "rate_limited")]
        max_used = max(used_pcts) if used_pcts else 0.0

        if max_used >= 90:
            border_color = "#ef4444"
        elif max_used >= 80:
            border_color = "#f59e0b"
        elif max_used > 0:
            border_color = self.default_color
        else:
            border_color = "#64748b"

        pct_label = f"{int(max_used)}%" if accounts else "OFF"
        self.icon_name = generate_chip_png(self.service_key, self.icon_tag, pct_label, border_color)

        try:
            self.NewIcon()
            self.NewToolTip()
            self.dbus_menu.LayoutUpdated(self.dbus_menu.revision + 1, 0)
        except Exception:
            pass

    def get_menu_tree(self):
        accounts = self.get_service_data()
        children = dbus.Array([], signature="v")
        item_id = 1
        self.action_map = {}

        def make_node(iid, props):
            pdict = dbus.Dictionary({}, signature="sv")
            for k, v in props.items():
                if isinstance(v, bool):
                    pdict[k] = dbus.Boolean(v)
                elif isinstance(v, int):
                    pdict[k] = dbus.Int32(v)
                else:
                    pdict[k] = dbus.String(str(v))
            return dbus.Struct((dbus.Int32(iid), pdict, dbus.Array([], signature="v")), signature="(ia{sv}av)")

        # Service Header
        children.append(make_node(item_id, {"label": f"{self.icon_tag}  {self.name.upper()} QUOTA"}))
        self.action_map[item_id] = "toggle_hud"
        item_id += 1

        children.append(make_node(item_id, {"type": "separator"}))
        item_id += 1

        for acc in accounts:
            name = acc.get("name", "Account")
            used = acc.get("used_pct", 0.0)
            resets = acc.get("resets_in_human") or "N/A"
            status = acc.get("status")

            if status == "not_configured":
                label = f"• {name}: Not configured"
            else:
                warn = "⚠️ " if used >= 80 else ""
                label = f"• {name}: {warn}{used:.1f}% used  │  Resets: {resets}"

            children.append(make_node(item_id, {"label": label}))
            self.action_map[item_id] = "toggle_hud"
            item_id += 1

        children.append(make_node(item_id, {"type": "separator"}))
        item_id += 1

        children.append(make_node(item_id, {"label": "🖥️ Open QuotaPulse"}))
        self.action_map[item_id] = "toggle_hud"
        item_id += 1

        children.append(make_node(item_id, {"label": "🔄 Force Refresh"}))
        self.action_map[item_id] = "force_refresh"
        item_id += 1

        children.append(make_node(item_id, {"type": "separator"}))
        item_id += 1

        children.append(make_node(item_id, {"label": "⏻ Turn Off QuotaPulse"}))
        self.action_map[item_id] = "turn_off"
        item_id += 1

        root_props = dbus.Dictionary({"children-display": dbus.String("submenu")}, signature="sv")
        return dbus.Struct((dbus.Int32(0), root_props, children), signature="(ia{sv}av)")

    def handle_menu_click(self, item_id):
        action = self.action_map.get(item_id)
        if action == "toggle_hud":
            self.manager.toggle_hud()
        elif action == "force_refresh":
            self.manager.force_refresh()
        elif action == "turn_off":
            self.manager.turn_off_all()


class MultiChipManager:
    def __init__(self):
        self.main_bus = dbus.SessionBus()
        self.state = {}
        self._load_state()

        # Service definitions
        service_defs = [
            ("claude", "Claude", "🟣 CL", "#a855f7"),
            ("antigravity", "Antigravity", "⚡ AG", "#38bdf8"),
            ("codex", "Codex", "🟢 CX", "#22c55e"),
            ("cursor", "Cursor", "🖱️ CU", "#06b6d4"),
        ]

        # Only create chips for services that are configured / present
        self.chips = []
        accounts = self.state.get("accounts", {})
        for sk, name, tag, color in service_defs:
            s_accs = accounts.get(sk, [])
            # Only include if at least one account is configured
            if any(a.get("status") != "not_configured" for a in s_accs):
                self.chips.append(SingleChipIndicator(sk, name, tag, color, self))

        self._register_all_chips()

        # Update every 5 seconds
        GLib.timeout_add_seconds(5, self._periodic_update)

    def turn_off_all(self):
        try:
            import subprocess
            subprocess.run(["pkill", "-9", "-f", "topbar_indicator.py"])
            subprocess.run(["pkill", "-9", "-f", "desktop_hud.py"])
        except Exception:
            pass
        sys.exit(0)

    def _register_all_chips(self):
        try:
            watcher = self.main_bus.get_object("org.kde.StatusNotifierWatcher", "/StatusNotifierWatcher")
            for chip in self.chips:
                watcher.RegisterStatusNotifierItem(chip.bus_name_str, dbus_interface="org.kde.StatusNotifierWatcher")
                print(f"[✓] Registered Top Bar Chip on Taskbar: {chip.icon_tag}")
        except Exception as e:
            print(f"[!] Registration error: {e}")

    def _load_state(self):
        if DEFAULT_STATE_FILE.exists():
            try:
                with open(DEFAULT_STATE_FILE, "r", encoding="utf-8") as f:
                    self.state = json.load(f)
            except Exception:
                pass

    def toggle_hud(self):
        subprocess.Popen([sys.executable, str(PROJECT_ROOT / "hud" / "desktop_hud.py")])

    def force_refresh(self):
        collect_all_quotas()
        self._load_state()
        for chip in self.chips:
            chip.update_chip()

    def _periodic_update(self):
        self._load_state()
        for chip in self.chips:
            chip.update_chip()
        return True


def main():
    manager = MultiChipManager()
    loop = GLib.MainLoop()
    try:
        loop.run()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
