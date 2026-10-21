#!/usr/bin/env bash
# Point every browser- and edge-facing URL in .env at this host, so the UI works from other machines.
#   ./scripts/set-public-host.sh            # auto-detect the primary IP
#   ./scripts/set-public-host.sh 192.168.56.10
#   ./scripts/set-public-host.sh vms.example.local
# Then rebuild/recreate (NEXT_PUBLIC_API_URL is baked into the frontend at build time):
#   ./scripts/install.sh   (or: docker compose up -d --build frontend backend mediamtx)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$ROOT/.env"
HOST="${1:-$(hostname -I 2>/dev/null | awk '{print $1}')}"
[ -n "$HOST" ] || { echo "cannot detect the host address; pass it as the first argument" >&2; exit 1; }
[ -f "$ENV_FILE" ] || { echo ".env not found (./scripts/generate-secrets.sh > .env)" >&2; exit 1; }

cp "$ENV_FILE" "$ENV_FILE.bak"
set_var() {  # replace KEY=... or append it
  if grep -qE "^$1=" "$ENV_FILE"; then sed -i "s|^$1=.*|$1=$2|" "$ENV_FILE"; else echo "$1=$2" >> "$ENV_FILE"; fi
}
set_var CORS_ORIGINS "http://$HOST:3000,http://localhost:3000"
set_var NEXT_PUBLIC_API_URL "http://$HOST:8000"
set_var MINIO_PUBLIC_URL "http://$HOST:9000"
set_var MINIO_EDGE_URL "http://$HOST:9000"     # snapshot uploads from edges
set_var MEDIAMTX_WEBRTC_PUBLIC_URL "http://$HOST:8889"
set_var MEDIAMTX_HLS_PUBLIC_URL "http://$HOST:8888"
set_var MEDIAMTX_WEBRTC_ADDITIONAL_HOSTS "$HOST"
# edge devices push video here
set_var MEDIAMTX_RTSP_PUBLISH_URL "rtsp://$HOST:8554"
set_var MEDIAMTX_SRT_PUBLISH_URL "srt://$HOST:8890"

echo "public host set to $HOST (previous .env saved as .env.bak)"
echo "open: http://$HOST:3000"
echo "apply: docker compose up -d --build frontend backend mediamtx   (or ./scripts/install.sh)"
echo "firewall: allow TCP 3000 8000 8554 8888 8889 9000 and UDP 8189"
