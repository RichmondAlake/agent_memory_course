#!/usr/bin/env bash
#
# oracle.sh — one Oracle AI Database (23ai Free) for the whole AI Maturity Ladder.
#
# Spins up a `gvenzl/oracle-free` container that BOTH surfaces share:
#   • notebook/  — Form Factor 2 (RAG) connects in §2.1
#   • appbook/   — the production app's RAG store
#
# It is preprovisioned so the notebook runs end-to-end with no manual SQL:
#   • a VECTOR schema user (matches appbook/.env.example)
#   • Oracle Text          — keyword & hybrid search (CTXSYS.CONTEXT index)
#   • AI Vector Search pool — so the HNSW vector index actually builds (§2.4/§2.6.3)
#   • CREATE PROPERTY GRAPH — the graph-retrieval section (§2.6.5)
#
# Usage:
#   ./oracle.sh start      # create/start + provision the DB   (default)
#   ./oracle.sh stop       # stop the container (data is kept)
#   ./oracle.sh restart    # restart the container
#   ./oracle.sh status     # show health + connection details
#   ./oracle.sh logs       # follow the container logs
#   ./oracle.sh sql        # open SQL*Plus as the VECTOR user
#   ./oracle.sh remove     # delete the container (add --data to wipe the volume)
#
# Everything is overridable via environment variables — see the CONFIG block.
#
set -euo pipefail

# ----------------------------------------------------------------------------
# CONFIG  (override by exporting first, e.g.  ORACLE_PORT=1530 ./oracle.sh)
# ----------------------------------------------------------------------------
# Regular flavor (NOT -slim): the slim image removes Oracle Text, which the
# notebook's keyword/hybrid search requires.
IMAGE="${ORACLE_IMAGE:-gvenzl/oracle-free:23}"
CONTAINER="${ORACLE_CONTAINER:-acme-oracle-free}"
VOLUME="${ORACLE_VOLUME:-acme-oracle-data}"
DB_PORT="${ORACLE_PORT:-1521}"

# These mirror appbook/.env.example so the notebook and the app share one DB.
DB_APP_USER="${ORACLE_USER:-VECTOR}"
DB_APP_PASSWORD="${ORACLE_PASSWORD:-VectorPwd_2025}"
DB_SYS_PASSWORD="${ORACLE_SYS_PASSWORD:-OraclePwd_2025}"   # SYS/SYSTEM admin password
PDB="FREEPDB1"                                             # gvenzl default PDB name
VECTOR_MEMORY_SIZE="${ORACLE_VECTOR_MEMORY_SIZE:-512M}"    # set 0 to skip the vector pool

DSN="localhost:${DB_PORT}/${PDB}"

# ----------------------------------------------------------------------------
# Pretty logging
# ----------------------------------------------------------------------------
log()  { printf '\033[0;36m▸ %s\033[0m\n' "$*"; }
ok()   { printf '\033[0;32m✓ %s\033[0m\n' "$*"; }
warn() { printf '\033[0;33m! %s\033[0m\n' "$*" >&2; }
die()  { printf '\033[0;31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

require_docker() {
  command -v docker >/dev/null 2>&1 || die "Docker is not installed — see https://docs.docker.com/get-docker/"
  docker info >/dev/null 2>&1        || die "Docker daemon is not running — start Docker Desktop and retry."
}

container_exists()  { [ -n "$(docker ps -aq -f "name=^${CONTAINER}$")" ]; }
container_running() { [ -n "$(docker ps  -q -f "name=^${CONTAINER}$")" ]; }

# Block until the container's built-in healthcheck reports healthy.
wait_healthy() {
  log "Waiting for the database to report healthy (first run creates the DB — can take a few minutes)…"
  local i status
  for (( i=0; i<150; i++ )); do
    status="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$CONTAINER" 2>/dev/null || echo missing)"
    case "$status" in
      healthy) printf '\n'; ok "Database is healthy."; return 0 ;;
      missing) printf '\n'; die "Container '$CONTAINER' vanished. Inspect: docker logs $CONTAINER" ;;
    esac
    printf '.'; sleep 5
  done
  printf '\n'; die "Timed out waiting for health. Inspect: docker logs $CONTAINER"
}

# Run a SQL*Plus script inside the container as SYSDBA (OS auth, no password).
sysdba() { docker exec -i "$CONTAINER" sqlplus -S / as sysdba; }

# ----------------------------------------------------------------------------
# Provisioning — privileges, then the vector memory pool (idempotent)
# ----------------------------------------------------------------------------
provision() {
  log "Granting '$DB_APP_USER' the privileges the notebook needs…"
  sysdba >/dev/null 2>&1 <<SQL || warn "Some grants reported an issue (usually harmless if already granted)."
WHENEVER SQLERROR CONTINUE
ALTER SESSION SET CONTAINER = ${PDB};
GRANT CREATE SESSION, RESOURCE, CREATE VIEW, CREATE PROPERTY GRAPH TO ${DB_APP_USER};
GRANT CTXAPP TO ${DB_APP_USER};
ALTER USER ${DB_APP_USER} QUOTA UNLIMITED ON USERS;
EXIT
SQL
  ok "Privileges granted (RESOURCE, CREATE VIEW, CREATE PROPERTY GRAPH, CTXAPP)."

  if [ "$VECTOR_MEMORY_SIZE" = "0" ]; then
    warn "ORACLE_VECTOR_MEMORY_SIZE=0 — skipping vector pool (the HNSW index will be skipped in the notebook)."
    return 0
  fi

  # AI Vector Search needs a non-zero vector_memory_size to build HNSW indexes.
  # Read the current value (note: v$parameter must stay literal — quoted heredoc).
  local vms
  vms="$(sysdba 2>/dev/null <<'SQL' | tr -dc '0-9'
SET HEADING OFF FEEDBACK OFF PAGESIZE 0 VERIFY OFF
SELECT NVL(value, '0') FROM v$parameter WHERE name = 'vector_memory_size';
EXIT
SQL
)"
  vms="${vms:-0}"

  if [ "$vms" != "0" ]; then
    ok "Vector pool already configured."
    return 0
  fi

  log "Enabling AI Vector Search pool (vector_memory_size=${VECTOR_MEMORY_SIZE}); a one-time restart follows…"
  local out
  out="$(sysdba 2>/dev/null <<SQL
WHENEVER SQLERROR EXIT SQL.SQLCODE
ALTER SYSTEM SET vector_memory_size = ${VECTOR_MEMORY_SIZE} SCOPE=SPFILE;
PROMPT VPOOL_SET_OK
EXIT
SQL
)"
  if printf '%s' "$out" | grep -q 'VPOOL_SET_OK'; then
    docker restart "$CONTAINER" >/dev/null
    wait_healthy
    ok "Vector pool active (${VECTOR_MEMORY_SIZE})."
  else
    warn "Could not set vector_memory_size — the HNSW vector index will be skipped (the notebook still runs). Detail: ${out}"
  fi
}

smoke_test() {
  log "Verifying '$DB_APP_USER' can log in…"
  if docker exec -i "$CONTAINER" sqlplus -S "${DB_APP_USER}/${DB_APP_PASSWORD}@localhost:1521/${PDB}" >/dev/null 2>&1 <<'SQL'
WHENEVER SQLERROR EXIT 1
SELECT 1 FROM dual;
EXIT
SQL
  then ok "Schema login works."
  else warn "Could not log in as $DB_APP_USER yet — the DB may still be finishing setup. Re-check with: ./oracle.sh status"
  fi
}

print_summary() {
  cat <<EOF

  Oracle AI Database is ready.

    Host / port : localhost:${DB_PORT}
    Service     : ${PDB}
    User        : ${DB_APP_USER}
    Password    : ${DB_APP_PASSWORD}
    DSN         : ${DSN}

  These values match appbook/.env.example, so both surfaces connect with no extra setup:

    • Notebook → open notebook/ai_maturity_form_factors_notebook.ipynb  (run §2.1 "Connect to Oracle")
    • App      → cd appbook && cp .env.example .env && ./run.sh

  Manage the database:  ./oracle.sh status | logs | sql | stop | remove
EOF
}

# ----------------------------------------------------------------------------
# Commands
# ----------------------------------------------------------------------------
cmd_start() {
  require_docker
  if container_running; then
    ok "Container '$CONTAINER' is already running."
  else
    if container_exists; then
      log "Starting existing container '$CONTAINER'…"
      docker start "$CONTAINER" >/dev/null
    else
      docker image inspect "$IMAGE" >/dev/null 2>&1 || { log "Pulling $IMAGE (first time, ~2 GB)…"; docker pull "$IMAGE"; }
      log "Creating container '$CONTAINER' (port ${DB_PORT}, volume '${VOLUME}')…"
      docker run -d \
        --name "$CONTAINER" \
        -p "${DB_PORT}:1521" \
        -e ORACLE_PASSWORD="$DB_SYS_PASSWORD" \
        -e APP_USER="$DB_APP_USER" \
        -e APP_USER_PASSWORD="$DB_APP_PASSWORD" \
        -v "${VOLUME}:/opt/oracle/oradata" \
        --restart unless-stopped \
        "$IMAGE" >/dev/null
    fi
    wait_healthy
  fi
  provision
  smoke_test
  print_summary
}

cmd_stop()    { require_docker; docker stop "$CONTAINER" >/dev/null && ok "Stopped '$CONTAINER' (data kept in volume '$VOLUME')."; }
cmd_restart() { require_docker; docker restart "$CONTAINER" >/dev/null && wait_healthy; }
cmd_logs()    { require_docker; docker logs -f "$CONTAINER"; }

cmd_sql() {
  require_docker
  container_running || die "Container '$CONTAINER' is not running. Start it with: ./oracle.sh start"
  exec docker exec -it "$CONTAINER" sqlplus "${DB_APP_USER}/${DB_APP_PASSWORD}@localhost:1521/${PDB}"
}

cmd_status() {
  require_docker
  if ! container_exists; then echo "Container '$CONTAINER' does not exist. Create it with: ./oracle.sh start"; return 0; fi
  local state health
  state="$(docker inspect -f '{{.State.Status}}' "$CONTAINER")"
  health="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}n/a{{end}}' "$CONTAINER")"
  printf 'Container : %s\nState     : %s\nHealth    : %s\nDSN       : %s  (user %s)\n' \
    "$CONTAINER" "$state" "$health" "$DSN" "$DB_APP_USER"
}

cmd_remove() {
  require_docker
  docker rm -f "$CONTAINER" >/dev/null 2>&1 && ok "Removed container '$CONTAINER'." || true
  if [ "${1:-}" = "--data" ]; then
    docker volume rm "$VOLUME" >/dev/null 2>&1 && ok "Removed data volume '$VOLUME'." || true
  else
    echo "Data volume '$VOLUME' kept. To wipe it too: ./oracle.sh remove --data"
  fi
}

usage() {
  grep -E '^#( |$)' "$0" | sed -E 's/^# ?//' | head -n 26
}

case "${1:-start}" in
  start)          cmd_start ;;
  stop)           cmd_stop ;;
  restart)        cmd_restart ;;
  status)         cmd_status ;;
  logs)           cmd_logs ;;
  sql)            cmd_sql ;;
  remove)         cmd_remove "${2:-}" ;;
  -h|--help|help) usage ;;
  *)              die "Unknown command '$1'. Try: start | stop | restart | status | logs | sql | remove" ;;
esac
