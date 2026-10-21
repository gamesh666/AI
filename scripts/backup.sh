#!/usr/bin/env bash
# Back up AIBOX SERVER data: database (devices, keys, owners, logs, users) + snapshots + settings.
#   ./scripts/backup.sh                  # -> backups/aibox-YYYYmmdd-HHMM/
#   ./scripts/backup.sh /mnt/usb/aibox   # or a directory of your choice
# The backup contains secrets (.env, device key hashes): keep it private, never commit it.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
OUT="${1:-backups/aibox-$(date +%Y%m%d-%H%M)}"
env_get() { grep -E "^$1=" .env | tail -1 | cut -d= -f2-; }
[ -f .env ] || { echo ".env not found: run this in the AIBOX SERVER directory" >&2; exit 1; }
docker compose ps --status running --services | grep -qx postgres || { echo "the platform is not running (./scripts/install.sh --no-build)" >&2; exit 1; }

mkdir -p "$OUT"
chmod 700 "$OUT"
OUT="$(cd "$OUT" && pwd)"
PROJECT="$(docker compose config --format json | python3 -c 'import json,sys; print(json.load(sys.stdin)["name"])')"

echo "database ..."
docker compose exec -T postgres pg_dump -U "$(env_get POSTGRES_USER)" -Fc "$(env_get POSTGRES_DB)" > "$OUT/db.dump"
echo "snapshots ..."
docker run --rm -v "${PROJECT}_minio-data:/data:ro" -v "$OUT:/backup" alpine:3.22 tar czf /backup/minio.tgz -C /data .
cp .env "$OUT/env"
chmod 600 "$OUT"/*
du -sh "$OUT"/* | sed 's/^/  /'
echo "backup written to $OUT"
