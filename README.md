# QuotaPulse

Know how close you are to an AI usage limit, and when you'll hit it.

QuotaPulse keeps a local history of your usage and forecasts when each account
will cross a threshold. It uses only the Python standard library, sends nothing
off your machine, and stores everything in one SQLite file.

## Install

```bash
pip install -e .        # or run in place: python3 -m quotapulse --help
```

Requires Python 3.10+.

## Use

```bash
# Claude Code: sum tokens from your local transcripts over the last 5 hours.
# Add --budget-tokens to turn that into a percentage of your own allowance.
quotapulse collect --budget-tokens 400000

# Any other service: copy the percentage from its usage page.
quotapulse record codex --used-pct 42 --resets-in-minutes 90

# Latest reading, burn rate, and when each account hits the threshold (default 80%).
quotapulse status --threshold 80

# Sparkline of the last 6 hours for one account.
quotapulse history claude --hours 6
```

Example `status` output:

```
ACCOUNT         USED                          RESETS  PACE
claude           61%  ████████████░░░░░░░░    3h 04m  +24.0%/h, hits 80% in 47m
codex            42%  ████████░░░░░░░░░░░░    1h 29m  flat
```

Run `collect` on a schedule to build history. For example, a cron entry every
five minutes:

```
*/5 * * * * quotapulse collect --budget-tokens 400000 >/dev/null 2>&1
```

## How the forecast works

Each `status` call looks at the last 2 hours of readings for an account. A
least-squares line through the last 30 minutes gives the burn rate. Any drop in
usage means old usage aged out of the window, so only readings after the latest
drop count. The forecast is the time when that line reaches the threshold. It
needs at least two readings in the window.

## Where data lives

- Database: `$XDG_DATA_HOME/quotapulse/quotapulse.db`, or `~/.local/share/quotapulse/quotapulse.db`.
  Override with `QUOTAPULSE_DB=/path/to/file.db`.
- Claude transcripts are read from `$CLAUDE_CONFIG_DIR/projects`, or `~/.claude/projects`.

## Limits

- Claude's real limit isn't exposed locally, so the percentage is only as good as
  the `--budget-tokens` you give it. Without a budget, `collect` records tokens only.
- Cache tokens are included in the total. If your plan counts them differently,
  adjust the budget.
- Services other than Claude Code need `record`, which is manual for now.

## Tests

```bash
python3 -m unittest discover -s tests -v
```
