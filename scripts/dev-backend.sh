#!/usr/bin/env bash
# Run the backend on the host with hot reload, against the infra started by docker compose.
#   docker compose up -d postgres redis mosquitto mediamtx minio
#   ./scripts/dev-backend.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
set -a; . "$ROOT/.env"; set +a

export POSTGRES_HOST=localhost REDIS_URL="redis://:${REDIS_PASSWORD}@localhost:6379/0"
export MQTT_HOST=localhost MQTT_USERNAME="${MQTT_BACKEND_USERNAME}" MQTT_PASSWORD="${MQTT_BACKEND_PASSWORD}"
export MINIO_ENDPOINT=localhost:9000 MINIO_ACCESS_KEY="${MINIO_ROOT_USER}" MINIO_SECRET_KEY="${MINIO_ROOT_PASSWORD}"
export MINIO_EDGE_URL=http://localhost:9000

cd "$ROOT/backend"
alembic upgrade head
python -m app.cli.seed
exec uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
