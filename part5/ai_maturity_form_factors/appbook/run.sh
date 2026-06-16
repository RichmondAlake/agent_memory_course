#!/usr/bin/env bash
# Launch the AI Maturity Ladder app.
#   • Locally: activates the `dbtlabs` conda env (has all deps).
#   • In a Codespace / dev container: uses the system Python (deps already installed).
set -euo pipefail

cd "$(dirname "$0")"

# Use the dbtlabs conda env when it exists; otherwise fall back to the current Python.
if command -v conda >/dev/null 2>&1 && conda env list 2>/dev/null | grep -q '/dbtlabs$\|dbtlabs '; then
  # shellcheck disable=SC1091
  source "$(conda info --base)/etc/profile.d/conda.sh"
  conda activate dbtlabs
fi

python -c "import fastapi" 2>/dev/null || pip install -q "fastapi>=0.110"

HOST="${HOST:-127.0.0.1}"   # devcontainer sets HOST=0.0.0.0 for port forwarding
PORT="${PORT:-8000}"
echo "→ AI Maturity Ladder on http://${HOST}:${PORT}"
exec uvicorn backend.main:app --host "${HOST}" --port "${PORT}" "$@"
