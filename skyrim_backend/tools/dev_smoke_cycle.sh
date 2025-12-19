#!/usr/bin/env bash
set -euo pipefail

base="${BASE_URL:-http://127.0.0.1:8000}"
host="${HOST:-127.0.0.1}"
port="${PORT:-8000}"

# enable addons by default for this cycle
export FIZBAN_ADDONS="${FIZBAN_ADDONS:-all}"

# If user has their own venv runner, they can set RUN_CMD.
# Otherwise we default to uvicorn directly (assuming venv already active).
run_cmd="${RUN_CMD:-python -m uvicorn app.main:app --host $host --port $port --log-level info}"

need() { command -v "$1" >/dev/null 2>&1 || { echo "[FAIL] missing tool: $1" >&2; exit 1; }; }
need curl
need jq

cleanup() {
  if [[ -n "${uv_pid:-}" ]] && kill -0 "$uv_pid" >/dev/null 2>&1; then
    kill "$uv_pid" >/dev/null 2>&1 || true
    wait "$uv_pid" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

echo "[RUN] starting server: $run_cmd"
bash -lc "$run_cmd" >$TMP/fizban_uvicorn.log 2>&1 &
uv_pid="$!"

echo "[WAIT] $base/health"
for i in $(seq 1 40); do
  if curl -fsS "$base/health" >/dev/null 2>&1; then
    echo "[OK] server is up"
    break
  fi
  sleep 0.25
done

if ! curl -fsS "$base/health" >/dev/null 2>&1; then
  echo "[FAIL] server did not become healthy"
  echo "---- uvicorn log ----"
  tail -200 $TMP/fizban_uvicorn.log || true
  exit 1
fi

echo "[TEST] api_contract_check"
if [[ -x tools/api_contract_check.sh ]]; then
  tools/api_contract_check.sh "$base"
else
  echo "[WARN] tools/api_contract_check.sh not found or not executable"
fi

echo "[TEST] smoke_api"
tools/smoke_api.sh "$base"
