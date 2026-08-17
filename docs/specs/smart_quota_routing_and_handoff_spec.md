# Smart Quota Relay Routing & Lightweight Harness Handoff Spec

## 1. Overview
**QuotaPulse Relay Router** is an intelligent orchestration layer that optimizes multi-account AI coding workflows across **Claude (Account 1 & 2)**, **Antigravity (Gemini)**, and **Codex (ChatGPT)**.

It eliminates workflow interruptions by:
1. Monitoring real-time 5-hour rolling pool usage and reset countdowns.
2. Automatically routing tasks to the optimal available model before hitting hard rate limits.
3. Preserving task intent, sub-step progress, and architectural decisions across account and tool handoffs with zero cognitive loss.

---

## 2. Core Architecture

```
                       ┌────────────────────────┐
                       │  User Command: `ai`    │
                       └───────────┬────────────┘
                                   │
                                   ▼
                       ┌────────────────────────┐
                       │   Quota Relay Router   │
                       │  - Live `state.json`   │
                       │  - Time-Paced Scoring  │
                       └───────────┬────────────┘
                                   │
         ┌─────────────────────────┼─────────────────────────┐
         ▼                         ▼                         ▼
┌──────────────────┐      ┌──────────────────┐      ┌──────────────────┐
│ Claude Primary   │      │ Claude Secondary │      │ Antigravity / CX │
│ (Threshold < 80%)│      │ (When P1 >= 80%) │      │ (Bridge Window)  │
└────────┬─────────┘      └────────┬─────────┘      └────────┬─────────┘
         │                         │                         │
         └─────────────────────────┼─────────────────────────┘
                                   ▼
                       ┌────────────────────────┐
                       │ Harness Handoff Engine │
                       │ (.git/handoff.json)    │
                       │ - Goal & Current Step  │
                       │ - Next Action & Diffs  │
                       └────────────────────────┘
```

---

## 3. Decision Engine & Scoring Formula

The router evaluates every account in the fallback chain:

$$\text{Score} = (100.0 - \text{used\_pct}) \times \left(1.0 + \frac{\text{elapsed\_in\_window}}{5\text{h}}\right)$$

### Routing Rules:
- **Exhaustion / Threshold Switch**: If active account's `used_pct >= switch_threshold_pct` (e.g. 80.0%, or 3.0% in test mode), the router automatically promotes the next eligible candidate in the priority chain.
- **Time-Aware Bridge**: If Account 1 is near threshold but resets in $< 15\text{ minutes}$, the router bridges the time gap using secondary models before reverting to Account 1.
- **Recovery Auto-Promotion**: When Account 1's rolling 5h window drops below `recovery_threshold_pct` (20.0%), it is restored as primary.

---

## 4. Harness Handoff Protocol

Stored at `.git/ai-quota-handoff.json` (or `~/.config/ai-quota-overlay/handoff.json`):

```json
{
  "version": 1,
  "timestamp": "2026-08-17T10:15:00Z",
  "source_agent": "claude_primary",
  "target_agent": "claude_secondary",
  "active_goal": "Refactor token counter in desktop_hud.py",
  "current_step": "Step 2/3: Update progress bar widget",
  "next_action": "Run python3 hud/desktop_hud.py and verify GTK4 output",
  "decisions_and_constraints": [
    "Do not alter backend database schema",
    "Use design tokens from theme palette"
  ],
  "uncommitted_files": [
    "hud/desktop_hud.py",
    "backend/quota_engine.py"
  ]
}
```

When the target agent launches, the router injects a concise 3-line handoff summary into the session initialization so the new agent begins executing immediately without exploration overhead.

---

## 5. User-Facing Behavior & CLI Interface

1. **Smart CLI Launcher**:
   ```bash
   ai [prompt / task]
   ```
   Automatically picks the healthiest model and executes.

2. **Explicit Routing Status**:
   ```bash
   ai-quota-overlay route
   ```
   Displays the active route, candidate scores, and next in line.

3. **Manual Override**:
   ```bash
   ai --use antigravity
   ai --use claude-2
   ```

4. **Handoff Checkpoint & Resume**:
   ```bash
   ai-quota-overlay handoff save --goal "..." --step "..." --next "..."
   ai-quota-overlay handoff resume
   ```
