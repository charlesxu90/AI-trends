#!/usr/bin/env bash
#
# Monthly AI-Trend refresh, driven by Claude Code in headless mode — designed for
# crontab. It lets Claude run the agentic pipeline (track-conferences web search +
# curate-topics reasoning) on top of the deterministic `ai-trend` CLI, then open a PR.
#
# Crontab example (06:00 UTC on the 1st of each month):
#   0 6 1 * * /ABS/PATH/AI-trend/scripts/monthly_refresh.sh >> /ABS/PATH/AI-trend/monthly_refresh.log 2>&1
#
# Prerequisites:
#   - `claude` (Claude Code CLI) installed and authenticated for this user.
#   - `gh` authenticated (for opening the PR).
#   - The repo-local Python env at ./env (see CLAUDE.md / AUTOMATION.md).
#   - Optional: a .env file in the repo root exporting ANTHROPIC_API_KEY to enable
#     headless topic curation (`ai-trend refresh --curate`).
set -euo pipefail

# cron has a minimal PATH; make sure user-local bins (claude) are reachable.
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
export PYTHONNOUSERSITE=1   # the project's hard requirement (isolate from user site-packages)

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

echo "===== AI-Trend monthly refresh: $(date -u +%FT%TZ) ====="

# Optional secrets (e.g. ANTHROPIC_API_KEY for --curate).
[ -f "$REPO/.env" ] && set -a && . "$REPO/.env" && set +a

# Start from a clean, up-to-date main.
git checkout -q main || true
git pull --ff-only origin main || echo "warning: could not fast-forward main"

if ! command -v claude >/dev/null 2>&1; then
  echo "error: 'claude' CLI not found on PATH" >&2
  exit 1
fi

# Headless run. allowedTools keeps it unattended without --dangerously-skip-permissions.
claude -p "$(cat "$REPO/scripts/monthly_prompt.md")" \
  --permission-mode acceptEdits \
  --allowedTools Bash Read Edit Write Glob Grep WebSearch WebFetch

echo "===== done: $(date -u +%FT%TZ) ====="
