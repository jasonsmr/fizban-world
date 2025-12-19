#!/usr/bin/env bash
set -euo pipefail

base="${1:-http://127.0.0.1:8000}"

curl -fsS "$base/health" >/dev/null
curl -fsS "$base/addons" >/dev/null
curl -fsS "$base/travel/options?from_location=RainbowBridge" >/dev/null

# Optional: ensure legacy endpoints are absent (if you had them before)
# curl -fsS "$base/travel/list_options" && { echo "legacy endpoint still exists"; exit 1; } || true

echo "[OK] api contract"
