#!/usr/bin/env bash
# Launch the Application Modes app.
#   • Locally: activates the `oracle_demos` conda env (has oracleagentmemory + deps).
#   • Elsewhere: falls back to the current Python.
set -euo pipefail

cd "$(dirname "$0")"

if command -v conda >/dev/null 2>&1 && conda env list 2>/dev/null | grep -q '/oracle_demos$\|oracle_demos '; then
  # shellcheck disable=SC1091
  source "$(conda info --base)/etc/profile.d/conda.sh"
  conda activate oracle_demos
fi

# Web-server deps + local embedder the memory env may not have yet.
python -c "import fastapi, uvicorn, sse_starlette, dotenv, fastembed" 2>/dev/null \
  || pip install -q "fastapi>=0.110" "uvicorn>=0.27" "sse-starlette>=2.0" "python-dotenv>=1.0" "fastembed>=0.8"

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
echo "→ Application Modes on http://${HOST}:${PORT}"
exec uvicorn backend.main:app --host "${HOST}" --port "${PORT}" "$@"
