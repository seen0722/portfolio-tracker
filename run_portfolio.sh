#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

# Load local secrets (FRED_API_KEY, LLM_API_KEY, TELEGRAM_*, ...) from an
# untracked .env so they never enter version control. set -a exports them.
if [[ -f .env ]]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

PYTHON_BIN="${PYTHON_BIN:-python3.13}"
VENV_DIR=".venv"

if [[ ! -d "$VENV_DIR" ]]; then
    python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"
pip install -r requirements.txt >/dev/null

exec "$PYTHON_BIN" main.py "$@"
