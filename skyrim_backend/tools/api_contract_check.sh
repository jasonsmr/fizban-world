#!/usr/bin/env bash
set -euo pipefail

req() {
  local url="$1"
  echo "[contract] GET $url"
  # -sS: quiet but show errors, -D-: print headers, keep body
  if ! out="$(curl -sS -D- "$url")"; then
    echo "[FAIL] curl failed: $url"
    return 1
  fi
  # If server returned non-2xx, curl still exits 0 unless -f is used.
  # So detect status line:
  status="$(printf "%s" "$out" | head -n1)"
  if ! echo "$status" | grep -qE " 2[0-9][0-9] "; then
    echo "[FAIL] $status"
    echo "$out" | sed -n '1,200p'
    return 1
  fi
  # Print body only (strip headers) so callers can pipe to jq / capture JSON
  printf "%s" "$out" | awk 'BEGIN{h=1} h && $0==""{h=0; next} !h{print}'
  return 0
}

req_post_json() {
  local url="$1"
  local json="$2"
  echo "[contract] POST $url"
  if ! out="$(curl -sS -D- -X POST "$url" -H 'Content-Type: application/json' -d "$json")"; then
    echo "[FAIL] curl failed: $url"
    return 1
  fi
  status="$(printf "%s" "$out" | head -n1)"
  if ! echo "$status" | grep -qE " 2[0-9][0-9] "; then
    echo "[FAIL] $status"
    echo "$out" | sed -n '1,200p'
    return 1
  fi
  printf "%s" "$out" | awk 'BEGIN{h=1} h && $0==""{h=0; next} !h{print}'
  return 0
}

base="${1:-http://127.0.0.1:8000}"

echo "[contract] health"
req "$base/health" | jq -e '.ok == true' >/dev/null

echo "[contract] addons"
req "$base/addons" | jq -e '.ok == true' >/dev/null

echo "[contract] travel/options RainbowBridge"
opts="$(req "$base/travel/options?from_location=RainbowBridge")"
echo "$opts" | jq -e '.ok == true' >/dev/null
# require non-empty options (this catches regressions where provider stops registering)
echo "$opts" | jq -e '.options | length > 0' >/dev/null

echo "[contract] travel/go RainbowBridge -> Whiterun (gold)"
go="$(req_post_json "$base/travel/go" '{"actor":"Player","from_location":"RainbowBridge","to_location":"Whiterun","lane":"gold"}')"
echo "$go" | jq -e '.ok == true' >/dev/null

echo "[contract] travel/where Player"
where="$(req "$base/travel/where?actor=Player")"
echo "$where" | jq -e '.ok == true' >/dev/null
# allow either "Whiterun" or whatever your provider sets as final
echo "$where" | jq -e '.location != null and .location != ""' >/dev/null

echo "[OK] contract check passed"
