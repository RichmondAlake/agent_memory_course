#!/usr/bin/env bash
# Launch the Agent Memory zero-to-hero appbook.
#   Python: $PYTHON if set, else part7/.venv/bin/python if it exists, else python3.
#   Installs requirements.txt when MemoRizz is older than 0.17.8, or FastAPI, SSE support or tiktoken is missing.
set -euo pipefail

cd "$(dirname "$0")"

PART7_VENV="../../../.venv/bin/python"
if [ -n "${PYTHON:-}" ]; then
  PY="$PYTHON"
elif [ -x "$PART7_VENV" ]; then
  PY="$PART7_VENV"
else
  PY="python3"
fi

"$PY" -c 'from importlib.metadata import version; import fastapi, sse_starlette, oracledb, tiktoken, requests; v = tuple(int(p) for p in version("memorizz").split(".")[:3]); assert (0, 17, 8) <= v < (0, 18)' 2>/dev/null \
  || "$PY" -m pip install -q -r requirements.txt \
  || { command -v uv >/dev/null && uv pip install --python "$PY" -q -r requirements.txt; }

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8710}"
echo "→ Agent Memory, from Scratch to MemoRizz on http://${HOST}:${PORT}  (python: ${PY})"
exec "$PY" -m uvicorn backend.main:app --host "${HOST}" --port "${PORT}" "$@"
