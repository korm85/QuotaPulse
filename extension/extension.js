/*
 * AI Quota & Rate Limit Monitor - GNOME Shell Extension
 * Compatible with GNOME 45, 46, 47, 48, 49, 50 (ESM)
 */

import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import GObject from 'gi://GObject';
import St from 'gi://St';

import { Extension, gettext as _ } from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';

const STATE_FILE_PATH = GLib.build_filenamev([
    GLib.get_home_dir(),
    '.config',
    'ai-quota-overlay',
    'state.json'
]);

const AIQuotaIndicator = GObject.registerClass(
class AIQuotaIndicator extends PanelMenu.Button {
    _init() {
        super._init(0.0, 'AI Quota Monitor', false);

        this.add_style_class_name('ai-quota-panel-btn');

        // Top bar container
        this._topBox = new St.BoxLayout({
            style_class: 'ai-quota-topbar-box',
            vertical: false,
            y_align: Clutter.ActorAlign.CENTER
        });
        this.add_child(this._topBox);

        // Individual service pills
        this._agLabel = new St.Label({
            text: '⚡ AG: --',
            style_class: 'ai-quota-pill ai-quota-pill-ok',
            y_align: Clutter.ActorAlign.CENTER
        });
        this._clLabel = new St.Label({
            text: '🟣 CL: --',
            style_class: 'ai-quota-pill ai-quota-pill-ok',
            y_align: Clutter.ActorAlign.CENTER
        });
        this._cxLabel = new St.Label({
            text: '🟢 CX: --',
            style_class: 'ai-quota-pill ai-quota-pill-ok',
            y_align: Clutter.ActorAlign.CENTER
        });

        this._topBox.add_child(this._agLabel);
        this._topBox.add_child(this._clLabel);
        this._topBox.add_child(this._cxLabel);

        // Build Dropdown menu
        this._buildMenu();

        // Load initial state
        this._updateState();

        // Refresh when menu opened
        this.menu.connect('open-state-changed', (menu, isOpen) => {
            if (isOpen) {
                this._updateState();
                this._triggerBackgroundRefresh();
            }
        });

        // Periodic UI update (every 10 seconds reads cached JSON)
        this._timerId = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 10, () => {
            this._updateState();
            return GLib.SOURCE_CONTINUE;
        });

        // Periodic background data refresh (every 60 seconds runs engine)
        this._refreshTimerId = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 60, () => {
            this._triggerBackgroundRefresh();
            return GLib.SOURCE_CONTINUE;
        });
    }

    _buildMenu() {
        this.menu.box.style_class = 'ai-quota-menu-box';

        // 1. Header
        let headerBox = new St.BoxLayout({
            style_class: 'ai-quota-header-box',
            vertical: false
        });
        
        let titleLabel = new St.Label({
            text: 'AI Quotas & Rate Limits',
            style_class: 'ai-quota-title',
            x_expand: true,
            y_align: Clutter.ActorAlign.CENTER
        });
        headerBox.add_child(titleLabel);

        let refreshBtn = new St.Button({
            label: '🔄 Refresh',
            style_class: 'ai-quota-footer-btn',
            y_align: Clutter.ActorAlign.CENTER
        });
        refreshBtn.connect('clicked', () => {
            this._triggerBackgroundRefresh(true);
        });
        headerBox.add_child(refreshBtn);

        let headerItem = new PopupMenu.PopupBaseMenuItem({
            reactive: false,
            can_focus: false
        });
        headerItem.add_child(headerBox);
        this.menu.addMenuItem(headerItem);

        // 2. Dynamic content container
        this._contentBox = new St.BoxLayout({
            vertical: true,
            spacing: 8
        });
        let contentItem = new PopupMenu.PopupBaseMenuItem({
            reactive: false,
            can_focus: false
        });
        contentItem.add_child(this._contentBox);
        this.menu.addMenuItem(contentItem);

        // 3. Separator
        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

        // 4. Footer Actions
        let footerBox = new St.BoxLayout({
            vertical: false,
            spacing: 8
        });

        let cliBtn = new St.Button({
            label: 'Terminal Dashboard',
            style_class: 'ai-quota-footer-btn',
            x_expand: true
        });
        cliBtn.connect('clicked', () => {
            this.menu.close();
            try {
                GLib.spawn_command_line_async('gnome-terminal -- ai-quota-overlay status');
            } catch (e) {
                log(`[AI Quota] Error opening terminal: ${e}`);
            }
        });
        footerBox.add_child(cliBtn);

        let hudBtn = new St.Button({
            label: 'Floating HUD',
            style_class: 'ai-quota-footer-btn',
            x_expand: true
        });
        hudBtn.connect('clicked', () => {
            this.menu.close();
            try {
                GLib.spawn_command_line_async('ai-quota-overlay hud');
            } catch (e) {
                log(`[AI Quota] Error launching HUD: ${e}`);
            }
        });
        footerBox.add_child(hudBtn);

        let footerItem = new PopupMenu.PopupBaseMenuItem({
            reactive: false,
            can_focus: false
        });
        footerItem.add_child(footerBox);
        this.menu.addMenuItem(footerItem);
    }

    _getPillStyle(pct, status) {
        if (status === 'rate_limited' || pct >= 90.0) {
            return 'ai-quota-pill ai-quota-pill-critical';
        }
        if (pct >= 70.0) {
            return 'ai-quota-pill ai-quota-pill-warning';
        }
        return 'ai-quota-pill ai-quota-pill-ok';
    }

    _getFillStyle(pct, status) {
        if (status === 'rate_limited' || pct >= 90.0) {
            return 'ai-quota-progress-fill ai-quota-progress-fill-critical';
        }
        if (pct >= 70.0) {
            return 'ai-quota-progress-fill ai-quota-progress-fill-warning';
        }
        return 'ai-quota-progress-fill ai-quota-progress-fill-ok';
    }

    _updateState() {
        let file = Gio.File.new_for_path(STATE_FILE_PATH);
        if (!file.query_exists(null)) {
            return;
        }

        try {
            let [ok, contents] = file.load_contents(null);
            if (!ok) return;

            let decoder = new TextDecoder('utf-8');
            let jsonText = decoder.decode(contents);
            let state = JSON.parse(jsonText);

            this._renderTopBar(state);
            this._renderDropdownContent(state);
        } catch (e) {
            log(`[AI Quota] Error reading state: ${e}`);
        }
    }

    _renderTopBar(state) {
        let accounts = state.accounts || {};
        let agList = accounts.antigravity || [];
        let clList = accounts.claude || [];
        let cxList = accounts.codex || [];

        // AG Pill
        let agMax = 0;
        let agStatus = 'ok';
        for (let a of agList) {
            if (a.used_pct > agMax) agMax = a.used_pct;
            if (a.status === 'rate_limited') agStatus = 'rate_limited';
        }
        this._agLabel.text = `⚡ AG: ${Math.round(agMax)}%`;
        this._agLabel.style_class = this._getPillStyle(agMax, agStatus);

        // CL Pill
        let clMax = 0;
        let clStatus = 'ok';
        for (let a of clList) {
            if (a.used_pct > clMax) clMax = a.used_pct;
            if (a.status === 'rate_limited') clStatus = 'rate_limited';
        }
        this._clLabel.text = `🟣 CL: ${Math.round(clMax)}%`;
        this._clLabel.style_class = this._getPillStyle(clMax, clStatus);

        // CX Pill
        let cxMax = 0;
        let cxStatus = 'ok';
        for (let a of cxList) {
            if (a.used_pct > cxMax) cxMax = a.used_pct;
            if (a.status === 'rate_limited') cxStatus = 'rate_limited';
        }
        this._cxLabel.text = `🟢 CX: ${Math.round(cxMax)}%`;
        this._cxLabel.style_class = this._getPillStyle(cxMax, cxStatus);
    }

    _renderDropdownContent(state) {
        this._contentBox.destroy_all_children();

        let accounts = state.accounts || {};

        // Helper to create account card
        const createCard = (acc, icon) => {
            let card = new St.BoxLayout({
                style_class: 'ai-quota-card',
                vertical: true
            });

            // Card Header
            let cardHeader = new St.BoxLayout({
                style_class: 'ai-quota-card-header',
                vertical: false
            });

            let nameText = `${icon} ${acc.name || 'Account'}`;
            let nameLabel = new St.Label({
                text: nameText,
                style_class: 'ai-quota-account-name',
                x_expand: true
            });
            cardHeader.add_child(nameLabel);

            if (acc.plan) {
                let badge = new St.Label({
                    text: acc.plan,
                    style_class: 'ai-quota-badge'
                });
                cardHeader.add_child(badge);
            }
            card.add_child(cardHeader);

            // Progress Bar
            let usedPct = Math.min(100, Math.max(0, acc.used_pct || 0));
            let progContainer = new St.BoxLayout({
                style_class: 'ai-quota-progress-container',
                vertical: false
            });

            let fillWidth = Math.max(2, Math.round(usedPct * 3.4)); // 340px max width approx
            let progFill = new St.BoxLayout({
                style_class: this._getFillStyle(usedPct, acc.status),
                width: fillWidth
            });
            progContainer.add_child(progFill);
            card.add_child(progContainer);

            // Info row
            let infoRow = new St.BoxLayout({
                style_class: 'ai-quota-info-row',
                vertical: false
            });

            let usedText = `Used: ${usedPct.toFixed(1)}%`;
            let resetText = acc.resets_in_human ? `Resets in: ${acc.resets_in_human}` : '';
            
            let usedLabel = new St.Label({
                text: usedText,
                x_expand: true
            });
            infoRow.add_child(usedLabel);

            if (resetText) {
                let resetLabel = new St.Label({
                    text: resetText,
                    style_class: 'ai-quota-reset-highlight'
                });
                infoRow.add_child(resetLabel);
            }
            card.add_child(infoRow);

            // Secondary detail row
            let extra = [];
            if (acc.model) extra.push(`Model: ${acc.model}`);
            if (acc.tokens_used && acc.token_limit) {
                let kUsed = Math.round(acc.tokens_used / 1000);
                let kLim = Math.round(acc.token_limit / 1000);
                extra.push(`${kUsed}k / ${kLim}k tokens`);
            }
            if (acc.cost_usd > 0) extra.push(`Cost: $${acc.cost_usd.toFixed(2)}`);
            if (acc.status === 'not_configured') extra.push('Not configured');

            if (extra.length > 0) {
                let extraLabel = new St.Label({
                    text: extra.join('  •  '),
                    style_class: 'ai-quota-info-row'
                });
                card.add_child(extraLabel);
            }

            return card;
        };

        // 1. Claude Section
        let clAccounts = accounts.claude || [];
        if (clAccounts.length > 0) {
            let secLabel = new St.Label({
                text: '🟣 Claude Accounts',
                style_class: 'ai-quota-section-title'
            });
            this._contentBox.add_child(secLabel);
            for (let a of clAccounts) {
                this._contentBox.add_child(createCard(a, '🟣'));
            }
        }

        // 2. Antigravity Section
        let agAccounts = accounts.antigravity || [];
        if (agAccounts.length > 0) {
            let secLabel = new St.Label({
                text: '⚡ Antigravity Accounts',
                style_class: 'ai-quota-section-title'
            });
            this._contentBox.add_child(secLabel);
            for (let a of agAccounts) {
                this._contentBox.add_child(createCard(a, '⚡'));
            }
        }

        // 3. Codex Section
        let cxAccounts = accounts.codex || [];
        if (cxAccounts.length > 0) {
            let secLabel = new St.Label({
                text: '🟢 Codex Accounts',
                style_class: 'ai-quota-section-title'
            });
            this._contentBox.add_child(secLabel);
            for (let a of cxAccounts) {
                this._contentBox.add_child(createCard(a, '🟢'));
            }
        }
    }

    _triggerBackgroundRefresh(force = false) {
        try {
            GLib.spawn_command_line_async('ai-quota-overlay refresh');
            // Give 1 second for fresh state then update
            GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 1, () => {
                this._updateState();
                return GLib.SOURCE_REMOVE;
            });
        } catch (e) {
            log(`[AI Quota] Refresh trigger failed: ${e}`);
        }
    }

    destroy() {
        if (this._timerId) {
            GLib.Source.remove(this._timerId);
            this._timerId = null;
        }
        if (this._refreshTimerId) {
            GLib.Source.remove(this._refreshTimerId);
            this._refreshTimerId = null;
        }
        super.destroy();
    }
});

export default class AIQuotaExtension extends Extension {
    enable() {
        this._indicator = new AIQuotaIndicator();
        Main.panel.addToStatusArea(this.uuid, this._indicator, 1, 'right');
    }

    disable() {
        if (this._indicator) {
            this._indicator.destroy();
            this._indicator = null;
        }
    }
}
