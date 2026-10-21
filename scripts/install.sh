#!/usr/bin/env bash
# AIBOX SERVER: one-shot install / update on a Linux VM, right after `git clone`.
#
#   ./scripts/install.sh                   # auto-detect this VM's IP
#   ./scripts/install.sh 192.168.0.179     # or give the address browsers and edges use
#   ./scripts/install.sh 192.168.0.179 --with-mqtt   # keep the legacy shared MQTT edge account
#   ./scripts/install.sh --no-build        # restart with the images already built (no code changes)
#
# Safe to run again (e.g. after `git pull` or when the VM's IP changes): an existing .env and all data
# (database, snapshots) are kept; only the public address and the containers are refreshed.
# Never prints secrets except the initial admin password on the very first install.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

HOST=""
WITH_MQTT=false
BUILD=--build
for arg in "$@"; do
  case "$arg" in
    --with-mqtt) WITH_MQTT=true ;;
    --no-build) BUILD="" ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    -*) echo "unknown option: $arg" >&2; exit 2 ;;
    *) HOST="$arg" ;;
  esac
done

step() { printf '\n\033[1m== %s\033[0m\n' "$*"; }
die() { printf '\033[31mERROR\033[0m %s\n' "$*" >&2; exit 1; }
env_get() { grep -E "^$1=" .env 2>/dev/null | tail -1 | cut -d= -f2-; }
env_set() {  # replace KEY=... or append it
  if grep -qE "^$1=" .env; then sed -i "s|^$1=.*|$1=$2|" .env; else echo "$1=$2" >> .env; fi
}

step "1/5 Checking Docker"
command -v docker >/dev/null || die "Docker is not installed. See docs/AIBOX-SERVER-建置SOP.md step 1."
docker info >/dev/null 2>&1 || die "cannot talk to Docker. Run: sudo usermod -aG docker \$USER, log out and in again (or run this script with sudo)."
cv="$(docker compose version --short 2>/dev/null | sed 's/^v//')"
[ -n "$cv" ] || die "the 'docker compose' plugin is missing (install docker-compose-plugin from docker.com)."
[ "$(printf '%s\n' 2.24.0 "$cv" | sort -V | head -1)" = "2.24.0" ] || die "docker compose $cv is too old (need 2.24 or newer)."
command -v openssl >/dev/null || die "openssl is missing (sudo apt-get install -y openssl)."
echo "docker compose $cv"

step "2/5 Settings (.env)"
FIRST_INSTALL=false
if [ -f .env ]; then
  echo ".env exists: keeping its secrets"
else
  ./scripts/generate-secrets.sh > .env
  chmod 600 .env
  env_set APP_ENV production
  FIRST_INSTALL=true
  echo "new .env with random secrets (permissions 600; never commit it, the repository is public)"
fi
if [ "$WITH_MQTT" = true ]; then
  env_set MQTT_EDGE_ENABLED true
elif [ "$FIRST_INSTALL" = true ] || [ -z "$(env_get MQTT_EDGE_ENABLED)" ]; then
  env_set MQTT_EDGE_ENABLED false   # edges send telemetry over HTTP with their own device key
fi
echo "shared MQTT edge account: $( [ "$(env_get MQTT_EDGE_ENABLED)" = true ] && echo on || echo off )"

step "3/5 Public address"
if [ -z "$HOST" ]; then
  # the address of the default route, so docker / tailscale interfaces are not picked by accident
  HOST="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for (i = 1; i < NF; i++) if ($i == "src") print $(i + 1)}' | head -1 || true)"
  [ -n "$HOST" ] || HOST="$(hostname -I 2>/dev/null | awk '{print $1}' || true)"
fi
[ -n "$HOST" ] || die "cannot detect this VM's IP; pass it: ./scripts/install.sh <ip>"
./scripts/set-public-host.sh "$HOST" >/dev/null
rm -f .env.bak
echo "browsers and edges will use: $HOST"

step "4/5 Building and starting (first time: 5-15 minutes)"
docker compose up -d $BUILD --remove-orphans

step "5/5 Waiting for the platform"
for _ in $(seq 1 90); do
  if curl -sf -m 3 http://localhost:8000/api/v1/health/ready >/dev/null 2>&1; then READY=true; break; fi
  sleep 2
done
[ "${READY:-false}" = true ] || die "backend not ready after 3 minutes: docker compose logs backend --tail 50"
curl -sf -m 5 -o /dev/null http://localhost:3000/login || echo "(the web UI may need a few more seconds)"

printf '\n\033[32mAIBOX SERVER is running.\033[0m\n'
echo "  web:   http://$HOST:3000"
echo "  API:   http://$HOST:8000/api/v1   (for edge devices)"
if [ "$FIRST_INSTALL" = true ]; then
  echo "  login: $(env_get INITIAL_ADMIN_USERNAME) / $(env_get INITIAL_ADMIN_PASSWORD)"
  echo "         change it right after the first login (Users page)"
else
  echo "  login: your existing accounts; first-time password: grep ^INITIAL_ADMIN_PASSWORD .env"
  echo "         (forgot a changed password? docker compose exec backend python -m app.cli.set_password admin)"
fi
echo "  open these ports to browsers / edges if a firewall is on:"
echo "         TCP 3000 8000 8554 8888 8889 9000, UDP 8189$( [ "$(env_get MQTT_EDGE_ENABLED)" = true ] && echo ', TCP 1883 (MQTT)')"
