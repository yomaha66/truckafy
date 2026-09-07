#!/usr/bin/env bash
# Smoke test the live service: renders a clip to ~/truckafy/test.mp3
set -euo pipefail
URL=${1:-$(cat .service_url)}
TEXT=${2:-"Hey honey, don't forget to pick up oat milk on the way home. And feed the cat!"}
curl -sS "$URL/" ; echo
curl -sS -o test.mp3 -w 'HTTP %{http_code}  %{size_download} bytes  %{time_total}s\n' \
  -H 'Content-Type: application/json' \
  -d "{\"text\": \"$TEXT\", \"arena_prefix\": true, \"intensity\": 0.9}" "$URL/truckafy"
file test.mp3 || true
