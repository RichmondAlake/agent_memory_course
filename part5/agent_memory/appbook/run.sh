#!/usr/bin/env bash
# Launch the Agent Memory Stack app.
#   • Locally: activates the `oracle_demos` conda env if present (the part5 env).
#   • In a Codespace / dev container: uses the system Python.
# Ensures memorizz + FastAPI are installed (from requirements.txt) before booting.
set -euo pipefail

cd "$(dirname "$0")"

# Use the oracle_demos conda env when it exists; otherwise fall back to current Python.
if command -v conda >/dev/null 2>&1 && conda env list 2>/dev/null | grep -q '/oracle_demos$\|oracle_demos '; then
  # shellcheck disable=SC1091
  source "$(conda info --base)/etc/profile.d/conda.sh"
  conda activate oracle_demos
fi

# Install deps on first run (memorizz, fastapi, …) if anything is missing.
python -c "import memorizz, fastapi, sse_starlette" 2>/dev/null || pip install -q -r requirements.txt

HOST="${HOST:-127.0.0.1}"   # devcontainer sets HOST=0.0.0.0 for port forwarding
PORT="${PORT:-8000}"
echo "→ Agent Memory Stack on http://${HOST}:${PORT}"
exec uvicorn backend.main:app --host "${HOST}" --port "${PORT}" "$@"
