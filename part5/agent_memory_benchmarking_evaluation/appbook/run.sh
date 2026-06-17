#!/usr/bin/env bash
# Launch the Agent Memory Benchmarks app.
#   Activates the `oracle_demos` conda env (oracleagentmemory, anthropic, litellm,
#   fastembed, oracledb, fastapi, uvicorn, sse-starlette all live there).
set -euo pipefail

cd "$(dirname "$0")"

if command -v conda >/dev/null 2>&1 && conda env list 2>/dev/null | grep -qE '/oracle_demos$|oracle_demos '; then
  # shellcheck disable=SC1091
  source "$(conda info --base)/etc/profile.d/conda.sh"
  conda activate oracle_demos
fi

# Install the web stack only if it's missing (it ships with oracle_demos here).
python -c "import fastapi, uvicorn, sse_starlette, dotenv" 2>/dev/null \
  || pip install -q "fastapi>=0.110" "uvicorn[standard]" sse-starlette python-dotenv

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8004}"
echo "→ Agent Memory Benchmarks on http://${HOST}:${PORT}"
exec uvicorn backend.main:app --host "${HOST}" --port "${PORT}" "$@"
