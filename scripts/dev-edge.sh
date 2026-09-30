#!/usr/bin/env bash
# Run an edge agent on the host (needs ffmpeg on PATH for the stream relay).
#   ./scripts/dev-edge.sh [device-id]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
set -a; . "$ROOT/.env"; set +a

export EDGE_DEVICE_UUID="${1:-${EDGE_DEVICE_UUID:-edge-dev-001}}"
export EDGE_API_URL="${EDGE_API_URL:-http://localhost:8000/api/v1}"
export EDGE_MQTT_USERNAME="${MQTT_EDGE_USERNAME}" EDGE_MQTT_PASSWORD="${MQTT_EDGE_PASSWORD}"
export EDGE_DATA_DIR="${EDGE_DATA_DIR:-$ROOT/edge-agent/data}"
# development defaults (override for real inference: DETECTOR_TYPE=yolo)
export EDGE_PLUGINS="${EDGE_PLUGINS:-aivms_sim.edge.plugin}"   # pip install -e simulation/python
export DETECTOR_TYPE="${DETECTOR_TYPE:-mock}"
export EDGE_METRICS_PROVIDER="${EDGE_METRICS_PROVIDER:-simulated}"

cd "$ROOT/edge-agent"
exec python -m agent.main
