#!/usr/bin/env bash
# Launch the AI Maturity Ladder appbook.
#
# Python, in order of preference:
#   1. $PYTHON, if you set it                  (PYTHON=/path/to/python ./run.sh)
#   2. part7/.venv/bin/python, if it exists     (the shared Part 7 environment)
#   3. python3 on your PATH                     (Codespaces / dev containers)
# Requirements are installed into that interpreter when an import check fails.
#
#   ./run.sh                     → http://127.0.0.1:8700
#   PORT=9000 ./run.sh           → another port
#   HOST=0.0.0.0 ./run.sh        → listen on every interface (dev containers)
set -euo pipefail

cd "$(dirname "$0")"

PART7_VENV="../../.venv/bin/python"
if [ -n "${PYTHON:-}" ]; then
  PY="$PYTHON"
elif [ -x "$PART7_VENV" ]; then
  PY="$PART7_VENV"
else
  PY="$(command -v python3 || command -v python)"
fi

install_requirements() {
  # uv-made environments have no pip; fall back to `uv pip` for those.
  "$PY" -m pip install -q -r requirements.txt 2>/dev/null \
    || uv pip install -q --python "$PY" -r requirements.txt
}
"$PY" -c "import anthropic, fastapi, uvicorn, fastembed, oracledb, sse_starlette, claude_agent_sdk, dotenv, huggingface_hub, matplotlib, pandas" 2>/dev/null \
  || install_requirements

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8700}"
echo "→ AI Maturity Ladder on http://${HOST}:${PORT}  (python: ${PY})"
exec "$PY" -m uvicorn backend.main:app --host "${HOST}" --port "${PORT}" "$@"
