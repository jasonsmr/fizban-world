#!/usr/bin/env bash
set -euo pipefail

base="${1:-http://127.0.0.1:8000}"

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
curl -sS 'http://127.0.0.1:8000/travel/options?from_location=RainbowBridge' | jq

echo "[5] travel go (RainbowBridge -> Whiterun, gold)"
curl -sS -X POST 'http://127.0.0.1:8000/travel/go' \
  -H 'Content-Type: application/json' \
  -d '{"actor":"Player","from_location":"RainbowBridge","to_location":"Whiterun","lane":"gold"}' | jq

ok="$(curl -sS -X POST 'http://127.0.0.1:8000/travel/go' \
  -H 'Content-Type: application/json' \
  -d '{"actor":"Player","from_location":"RainbowBridge","to_location":"Whiterun","lane":"gold"}' \
  | jq -r '.ok')"
test "$ok" = "true" || { echo "[FAIL] travel/go failed"; exit 1; }
echo "[OK] travel/go ok"

echo "[6] travel where (Player)"
curl -sS 'http://127.0.0.1:8000/travel/where?actor=Player' | jq

echo "[OK] smoke passed"
