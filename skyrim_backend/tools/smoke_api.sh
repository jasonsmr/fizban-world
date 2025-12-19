#!/usr/bin/env bash
set -euo pipefail

base="${1:-http://127.0.0.1:8000}"

need() { command -v "$1" >/dev/null 2>&1 || { echo "[FAIL] missing tool: $1" >&2; exit 1; }; }
need curl
need jq

echo "[1] health"
curl -fsS "$base/health" | jq .

echo "[2] npc/Puck"
curl -fsS "$base/npc/Puck" | jq .

echo "[3] realm selection"
curl -fsS -X POST "$base/realm/selection" \
  -H 'Content-Type: application/json' \
  -d '{
    "actor":"Player",
    "selection_id":"realm_shrine_akatosh",
    "location":"RealmOfLorkhan",
    "effects":[
      {"channel":"divine","key":"Akatosh","delta":0.10,"note":"start_shrine"},
      {"channel":"faction","key":"Companions","delta":0.05,"note":"start_affinity"},
      {"channel":"tag","tag":"alternate_start","delta":0.0,"note":"flag"}
    ],
    "tags":["test_room"]
  }' | jq .

echo "[4] travel options (RainbowBridge)"
opts_json="$(curl -fsS "$base/travel/options?from_location=RainbowBridge")"
echo "$opts_json" | jq .
opt_count="$(echo "$opts_json" | jq -r '.options | length')"
test "$opt_count" -gt 0 || { echo "[FAIL] travel/options returned 0 options" >&2; exit 1; }
echo "[OK] travel/options has $opt_count options"

echo "[5] travel go (RainbowBridge -> Whiterun, gold)"
go_json="$(curl -fsS -X POST "$base/travel/go" \
  -H 'Content-Type: application/json' \
  -d '{"actor":"Player","from_location":"RainbowBridge","to_location":"Whiterun","lane":"gold"}')"
echo "$go_json" | jq .
ok="$(echo "$go_json" | jq -r '.ok')"
test "$ok" = "true" || { echo "[FAIL] travel/go failed" >&2; exit 1; }
echo "[OK] travel/go ok"

echo "[6] travel where (Player)"
curl -fsS "$base/travel/where?actor=Player" | jq .

echo "[OK] smoke passed"
