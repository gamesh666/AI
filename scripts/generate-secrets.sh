#!/usr/bin/env bash
# Prints a .env built from .env.example with every "change-me" secret replaced by a random value.
#   ./scripts/generate-secrets.sh > .env
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

rand() { openssl rand -hex "${1:-24}"; }
# Fernet key = urlsafe base64 of 32 random bytes
fernet() { openssl rand -base64 32 | tr '+/' '-_'; }

sed \
  -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$(rand)|" \
  -e "s|^REDIS_PASSWORD=.*|REDIS_PASSWORD=$(rand)|" \
  -e "s|^JWT_SECRET_KEY=.*|JWT_SECRET_KEY=$(rand 32)|" \
  -e "s|^CREDENTIAL_ENCRYPTION_KEY=.*|CREDENTIAL_ENCRYPTION_KEY=$(fernet)|" \
  -e "s|^INITIAL_ADMIN_PASSWORD=.*|INITIAL_ADMIN_PASSWORD=$(rand 8)|" \
  -e "s|^EDGE_PROVISIONING_TOKEN=.*|EDGE_PROVISIONING_TOKEN=$(rand)|" \
  -e "s|^MQTT_BACKEND_PASSWORD=.*|MQTT_BACKEND_PASSWORD=$(rand)|" \
  -e "s|^MQTT_EDGE_PASSWORD=.*|MQTT_EDGE_PASSWORD=$(rand)|" \
  -e "s|^MINIO_ROOT_PASSWORD=.*|MINIO_ROOT_PASSWORD=$(rand)|" \
  "$ROOT/.env.example"
