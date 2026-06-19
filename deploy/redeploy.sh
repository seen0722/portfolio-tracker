#!/usr/bin/env bash
# Server-side redeploy, run by the GitHub Actions SSH job (as root) from the repo
# root after `git reset --hard origin/main`. Installs deps, re-asserts the
# systemd unit (self-healing), and restarts the service.
#
# Untracked files (.env with secrets, portfolio.db with holdings) are NOT touched
# by git reset, so they survive every deploy.
set -euo pipefail

cd "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

echo ">>> Installing dependencies…"
[ -d .venv ] || python3 -m venv .venv
./.venv/bin/pip install -q --upgrade pip
./.venv/bin/pip install -q -r requirements.txt

echo ">>> Asserting systemd unit…"
install -m 644 deploy/portfolio.service /etc/systemd/system/portfolio.service
systemctl daemon-reload
systemctl enable portfolio >/dev/null 2>&1 || true

echo ">>> Restarting service…"
systemctl restart portfolio
sleep 1
systemctl --no-pager --lines=0 status portfolio || true

echo ">>> Deployed $(git rev-parse --short HEAD)"
