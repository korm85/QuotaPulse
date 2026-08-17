#!/usr/bin/env python3
"""Cross-Platform (Windows / Linux / macOS) AI Quota Overlay HUD in PyQt6."""
import json
import os
import sys
import time
from pathlib import Path

# Add project root to sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.config_manager import DEFAULT_STATE_FILE
from backend.quota_engine import collect_all_quotas

try:
    from PyQt6.QtCore import Qt, QTimer, QPoint
    from PyQt6.QtGui import QFont, QColor, QPalette, QIcon
    from PyQt6.QtWidgets import (
        QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
        QProgressBar, QPushButton, QScrollArea, QFrame, QSystemTrayIcon, QMenu
    )
    HAS_PYQT6 = True
except ImportError:
    HAS_PYQT6 = False


if not HAS_PYQT6:
    print("PyQt6 is required for Windows Native HUD. Install with: pip install PyQt6")


class CrossPlatformHUD(QWidget if HAS_PYQT6 else object):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("AI Quotas Overlay")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(340, 460)

        self.is_compact = False
        self.drag_position = QPoint()

        self._init_ui()

        # Update timer (every 5 seconds)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_ui)
        self.timer.start(5000)

        self.update_ui()

    def _init_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Background Container
        self.bg_frame = QFrame(self)
        self.bg_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(15, 18, 25, 240);
                border: 1px solid rgba(255, 255, 255, 45);
                border-radius: 14px;
            }
        """)
        bg_layout = QVBoxLayout(self.bg_frame)
        bg_layout.setContentsMargins(12, 10, 12, 12)
        bg_layout.setSpacing(8)

        # Header Bar
        header = QHBoxLayout()
        header.setSpacing(6)

        title = QLabel("⚡ AI QUOTAS ⋮⋮")
        title.setStyleSheet("font-weight: 800; font-size: 13px; color: #f8fafc; border: none;")
        header.addWidget(title)
        header.addStretch()

        self.compact_btn = QPushButton("◰ Compact")
        self.compact_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,25); color: #cbd5e1;
                border: none; border-radius: 4px; padding: 3px 8px; font-size: 11px; font-weight: bold;
            }
            QPushButton:hover { background: rgba(255,255,255,50); color: #fff; }
        """)
        self.compact_btn.clicked.connect(self._toggle_compact)
        header.addWidget(self.compact_btn)

        refresh_btn = QPushButton("🔄")
        refresh_btn.setStyleSheet("""
            QPushButton { background: rgba(255,255,255,25); color: #fff; border: none; border-radius: 4px; padding: 3px 6px; }
            QPushButton:hover { background: rgba(255,255,255,50); }
        """)
        refresh_btn.clicked.connect(self._refresh_data)
        header.addWidget(refresh_btn)

        close_btn = QPushButton("✕")
        close_btn.setStyleSheet("""
            QPushButton { background: transparent; color: #94a3b8; border: none; border-radius: 4px; padding: 2px 6px; font-weight: bold; }
            QPushButton:hover { background: rgba(239, 68, 68, 80); color: #f87171; }
        """)
        close_btn.clicked.connect(self.close)
        header.addWidget(close_btn)

        bg_layout.addLayout(header)

        # Scrollable Content Box (Full view)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.cards_widget = QWidget()
        self.cards_widget.setStyleSheet("background: transparent;")
        self.cards_layout = QVBoxLayout(self.cards_widget)
        self.cards_layout.setContentsMargins(0, 4, 0, 4)
        self.cards_layout.setSpacing(6)
        self.scroll.setWidget(self.cards_widget)
        bg_layout.addWidget(self.scroll)

        # Compact View Container
        self.compact_widget = QWidget()
        self.compact_widget.setStyleSheet("background: transparent;")
        self.compact_layout = QVBoxLayout(self.compact_widget)
        self.compact_layout.setContentsMargins(0, 4, 0, 4)
        self.compact_layout.setSpacing(4)
        self.compact_widget.setVisible(False)
        bg_layout.addWidget(self.compact_widget)

        self.main_layout.addWidget(self.bg_frame)

    def _toggle_compact(self):
        self.is_compact = not self.is_compact
        if self.is_compact:
            self.compact_btn.setText("◫ Full")
            self.scroll.setVisible(False)
            self.compact_widget.setVisible(True)
            self.resize(310, 240)
        else:
            self.compact_btn.setText("◰ Compact")
            self.compact_widget.setVisible(False)
            self.scroll.setVisible(True)
            self.resize(340, 460)
        self.update_ui()

    def _refresh_data(self):
        collect_all_quotas()
        self.update_ui()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def update_ui(self):
        if not DEFAULT_STATE_FILE.exists():
            collect_all_quotas()

        try:
            with open(DEFAULT_STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)

            accounts = state.get("accounts", {})
            cl_accs = accounts.get("claude", [])
            ag_accs = accounts.get("antigravity", [])
            cx_accs = accounts.get("codex", [])
            cu_accs = accounts.get("cursor", [])
            all_accs = cl_accs + ag_accs + cx_accs + cu_accs

            icons = {"claude": "🟣", "antigravity": "⚡", "codex": "🟢", "cursor": "🖱️"}

            # Clear full cards
            while self.cards_layout.count():
                item = self.cards_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            # Clear compact rows
            while self.compact_layout.count():
                item = self.compact_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()

            for acc in all_accs:
                icon = icons.get(acc.get("service"), "🤖")
                used = float(acc.get("used_pct", 0.0))
                name = acc.get("name", "Account")
                plan = acc.get("plan", "PRO")
                resets = acc.get("resets_in_human") or "N/A"
                is_not_cfg = (acc.get("status") == "not_configured")

                # Progress color
                if acc.get("status") == "rate_limited" or used >= 90:
                    bar_color = "#ef4444"
                elif used >= 70:
                    bar_color = "#eab308"
                else:
                    bar_color = "#22c55e"

                # 1. Add Full Card
                card = QFrame()
                card.setStyleSheet("""
                    QFrame {
                        background: rgba(255, 255, 255, 12);
                        border: 1px solid rgba(255, 255, 255, 20);
                        border-radius: 8px;
                    }
                """)
                card_layout = QVBoxLayout(card)
                card_layout.setContentsMargins(8, 8, 8, 8)
                card_layout.setSpacing(4)

                top_h = QHBoxLayout()
                lbl_name = QLabel(f"{icon} {name}")
                lbl_name.setStyleSheet("font-weight: 700; font-size: 12px; color: #f8fafc; border: none;")
                top_h.addWidget(lbl_name)
                top_h.addStretch()

                lbl_plan = QLabel(plan)
                lbl_plan.setStyleSheet("background: rgba(255,255,255,30); color: #cbd5e1; border-radius: 4px; padding: 1px 5px; font-size: 9px; font-weight: bold; border: none;")
                top_h.addWidget(lbl_plan)
                card_layout.addLayout(top_h)

                pbar = QProgressBar()
                pbar.setRange(0, 100)
                pbar.setValue(0 if is_not_cfg else int(used))
                pbar.setTextVisible(False)
                pbar.setFixedHeight(6)
                pbar.setStyleSheet(f"""
                    QProgressBar {{ background: rgba(255,255,255,25); border-radius: 3px; border: none; }}
                    QProgressBar::chunk {{ background-color: {bar_color}; border-radius: 3px; }}
                """)
                card_layout.addWidget(pbar)

                info_h = QHBoxLayout()
                lbl_used = QLabel("Not configured" if is_not_cfg else f"{used:.1f}% used")
                lbl_used.setStyleSheet("font-size: 11px; color: #94a3b8; border: none;")
                info_h.addWidget(lbl_used)
                info_h.addStretch()

                if not is_not_cfg and resets:
                    lbl_rst = QLabel(f"Resets: {resets}")
                    lbl_rst.setStyleSheet("font-size: 11px; font-weight: bold; color: #fde047; border: none;")
                    info_h.addWidget(lbl_rst)
                card_layout.addLayout(info_h)

                self.cards_layout.addWidget(card)

                # 2. Add Compact Row
                c_row = QFrame()
                c_row.setStyleSheet("QFrame { background: rgba(255,255,255,10); border-radius: 6px; border: none; }")
                c_layout = QHBoxLayout(c_row)
                c_layout.setContentsMargins(6, 4, 6, 4)
                c_layout.setSpacing(6)

                c_name = QLabel(f"{icon} {name.split()[0]}: {used:.0f}%" if not is_not_cfg else f"{icon} {name.split()[0]}")
                c_name.setStyleSheet("font-size: 11px; font-weight: bold; color: #f8fafc; border: none;")
                c_layout.addWidget(c_name)
                c_layout.addStretch()

                c_pbar = QProgressBar()
                c_pbar.setRange(0, 100)
                c_pbar.setValue(0 if is_not_cfg else int(used))
                c_pbar.setTextVisible(False)
                c_pbar.setFixedSize(50, 5)
                c_pbar.setStyleSheet(f"""
                    QProgressBar {{ background: rgba(255,255,255,25); border-radius: 2px; border: none; }}
                    QProgressBar::chunk {{ background-color: {bar_color}; border-radius: 2px; }}
                """)
                c_layout.addWidget(c_pbar)

                c_rst = QLabel("Not setup" if is_not_cfg else resets)
                c_rst.setStyleSheet("font-size: 10px; font-weight: bold; color: #facc15; border: none;" if not is_not_cfg else "font-size: 10px; color: #64748b; border: none;")
                c_layout.addWidget(c_rst)

                self.compact_layout.addWidget(c_row)

        except Exception as e:
            print(f"Update error: {e}")


def main():
    if not HAS_PYQT6:
        print("Please install PyQt6: pip install PyQt6")
        sys.exit(1)

    app = QApplication(sys.argv)
    hud = CrossPlatformHUD()
    hud.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
