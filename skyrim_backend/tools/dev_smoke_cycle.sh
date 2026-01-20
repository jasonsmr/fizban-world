#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
TMPROOT="${TMP:-${TMPDIR:-$HOME/tmp}}"
mkdir -p "$TMPROOT"
LOGFILE="$TMPROOT/fizban_uvicorn.log"

RUN_CMD="${RUN_CMD:-python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level info}"

echo "[RUN] starting server: $RUN_CMD"
echo "[LOG] $LOGFILE"

bash -lc "$RUN_CMD" >"$LOGFILE" 2>&1 &
pid="$!"

cleanup() {
  echo "[CLEANUP] stopping server pid=$pid"
  kill "$pid" >/dev/null 2>&1 || true
  wait "$pid" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "[WAIT] $BASE_URL/health"
for i in $(seq 1 80); do
  if curl -fsS "$BASE_URL/health" 2>/dev/null 2>&1; then
    echo "[OK] server is up"
    break
  fi

  sleep 0.2

  if ! kill -0 "$pid" >/dev/null 2>&1; then
    echo "[FAIL] server died early; tail log:"
    tail -n 200 "$LOGFILE" || true
    exit 1
  fi

  if [ "$i" -eq 80 ]; then
    echo "[FAIL] server never became healthy; tail log:"
    tail -n 200 "$LOGFILE" || true
    exit 1
  fi
done

echo "[TEST] api_contract_check"
if ! ./tools/api_contract_check.sh "$BASE_URL"; then
  echo "[FAIL] contract check failed; tail log:"
  tail -n 240 "$LOGFILE" || true
  exit 1
fi

echo "[TEST] smoke_api"
if ! ./tools/smoke_api.sh "$BASE_URL"; then
  echo "[FAIL] smoke_api failed; tail log:"
  tail -n 240 "$LOGFILE" || true
  exit 1
fi

echo "[OK] dev smoke cycle passed"
