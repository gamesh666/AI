#!/usr/bin/env bash
# Restore a backup made by scripts/backup.sh into THIS installation (replaces its database and snapshots).
#   ./scripts/restore.sh backups/aibox-20261021-0930
# Moving to a new VM: copy the backup's `env` to the new VM as .env BEFORE the first ./scripts/install.sh
# (same secrets), then run this. Edge devices keep their keys; point them at the new address if it changed.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
SRC="${1:?usage: ./scripts/restore.sh <backup directory>}"
SRC="$(cd "$SRC" && pwd)"
[ -f "$SRC/db.dump" ] && [ -f "$SRC/minio.tgz" ] || { echo "$SRC has no db.dump / minio.tgz" >&2; exit 1; }
env_get() { grep -E "^$1=" .env | tail -1 | cut -d= -f2-; }
docker compose ps --status running --services | grep -qx postgres || { echo "start the platform first (./scripts/install.sh)" >&2; exit 1; }
PROJECT="$(docker compose config --format json | python3 -c 'import json,sys; print(json.load(sys.stdin)["name"])')"

read -r -p "This REPLACES all data of this installation with $SRC. Type yes to continue: " answer
[ "$answer" = yes ] || { echo "cancelled"; exit 1; }

docker compose stop backend frontend
echo "database ..."
docker compose exec -T postgres pg_restore -U "$(env_get POSTGRES_USER)" -d "$(env_get POSTGRES_DB)" \
  --clean --if-exists --no-owner < "$SRC/db.dump"
echo "snapshots ..."
docker compose stop minio
docker run --rm -v "${PROJECT}_minio-data:/data" -v "$SRC:/backup:ro" alpine:3.22 \
  sh -c 'find /data -mindepth 1 -delete && tar xzf /backup/minio.tgz -C /data'
docker compose start minio backend frontend
echo "restored from $SRC (backend runs pending migrations on start)"
