#!/usr/bin/env bash
# Launch the AI Application Evaluation app.
#   • Locally: activates the `oracle_demos` conda env (has all deps).
#   • In a Codespace / dev container: uses the system Python (deps already installed).
set -euo pipefail

cd "$(dirname "$0")"

# Use the oracle_demos conda env when it exists; otherwise fall back to current Python.
if command -v conda >/dev/null 2>&1 && conda env list 2>/dev/null | grep -q '/oracle_demos$\|oracle_demos '; then
  # shellcheck disable=SC1091
  source "$(conda info --base)/etc/profile.d/conda.sh"
  conda activate oracle_demos
fi

python -c "import fastapi" 2>/dev/null || pip install -q "fastapi>=0.110"

HOST="${HOST:-127.0.0.1}"   # devcontainer sets HOST=0.0.0.0 for port forwarding
PORT="${PORT:-8003}"        # 8001 = maturity ladder, 8002 = agent memory, 8003 = evaluation
echo "→ AI Application Evaluation on http://${HOST}:${PORT}"
exec uvicorn backend.main:app --host "${HOST}" --port "${PORT}" "$@"
