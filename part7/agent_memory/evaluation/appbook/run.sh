#!/usr/bin/env bash
# Launch the agent memory evaluation studio.
#
# Python, in order of preference:
#   1. $PYTHON, if you set it                  (PYTHON=/path/to/python ./run.sh)
#   2. part7/.venv/bin/python, if it exists     (the shared Part 7 environment)
#   3. python3 on your PATH
# Requirements are installed into that interpreter when an import check fails.
#
#   ./run.sh                     → http://127.0.0.1:8715
#   PORT=9000 ./run.sh           → another port
#   HOST=0.0.0.0 ./run.sh        → listen on every interface (dev containers)
set -euo pipefail

cd "$(dirname "$0")"

PART7_VENV="../../../.venv/bin/python"
if [ -n "${PYTHON:-}" ]; then
  PY="$PYTHON"
elif [ -x "$PART7_VENV" ]; then
  PY="$PART7_VENV"
else
  PY="$(command -v python3 || command -v python)"
fi

install_requirements() {
  "$PY" -m pip install -q -r requirements.txt 2>/dev/null \
    || uv pip install -q --python "$PY" -r requirements.txt
}
"$PY" -c "import anthropic, openai, fastapi, uvicorn, oracledb, sse_starlette, dotenv, huggingface_hub, numpy, pandas, pyarrow, requests, tiktoken, memorizz" 2>/dev/null \
  || install_requirements
"$PY" - <<'PY' || install_requirements
import importlib.metadata, re
version = tuple(int(p) for p in re.findall(r"\d+", importlib.metadata.version("memorizz"))[:3])
raise SystemExit(0 if version >= (0, 17, 8) else 1)
PY

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8715}"
echo "→ Agent memory evaluation studio on http://${HOST}:${PORT}  (python: ${PY})"
exec "$PY" -m uvicorn backend.main:app --host "${HOST}" --port "${PORT}" "$@"
