#!/usr/bin/env bash
# Pre-flight check for a host (e.g. an Ubuntu VM) before `docker compose [--profile demo] up`.
#   ./scripts/doctor.sh
# Read-only: prints OK / WARN / FAIL lines and never prints secret values.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
FAILS=0 WARNS=0
ok()   { printf '  \033[32mOK\033[0m    %s\n' "$*"; }
warn() { printf '  \033[33mWARN\033[0m  %s\n' "$*"; WARNS=$((WARNS + 1)); }
fail() { printf '  \033[31mFAIL\033[0m  %s\n' "$*"; FAILS=$((FAILS + 1)); }
env_get() { grep -E "^$1=" .env 2>/dev/null | tail -1 | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//'; }

echo "== Docker"
if ! command -v docker >/dev/null; then
  fail "docker not installed (install Docker Engine from docker.com's apt repository, not the snap)"
else
  if docker info >/dev/null 2>&1; then ok "docker daemon reachable"; else fail "cannot talk to the docker daemon (sudo usermod -aG docker \$USER, then log in again)"; fi
  cv="$(docker compose version --short 2>/dev/null | sed 's/^v//')"
  if [ -z "$cv" ]; then
    fail "'docker compose' plugin missing (legacy docker-compose v1 does not support this project)"
  elif [ "$(printf '%s\n' 2.24.0 "$cv" | sort -V | head -1)" != "2.24.0" ]; then
    fail "docker compose $cv is too old (need >= 2.24 for 'include'); install docker-compose-plugin from docker.com"
  else
    ok "docker compose $cv"
  fi
fi

echo "== Repository"
if [ -f docker-compose.demo.yml ] && grep -q "path: docker-compose.demo.yml" docker-compose.yml; then
  ok "root docker-compose.yml includes infra/ and docker-compose.demo.yml"
else
  fail "docker-compose.yml / docker-compose.demo.yml out of date (git status; git pull)"
fi
if [ -d .git ] && [ -n "$(git status --porcelain -- docker-compose*.yml infra simulation 2>/dev/null)" ]; then
  warn "local changes in compose / infra / simulation files (git status) — they may break build paths"
fi

echo "== .env"
if [ ! -f .env ]; then
  fail ".env missing: ./scripts/generate-secrets.sh > .env"
else
  placeholders="$(grep -E '^[A-Z_]+=change-me' .env | cut -d= -f1 | tr '\n' ' ')"
  if [ -n "$placeholders" ]; then warn "placeholder values: $placeholders(regenerate: ./scripts/generate-secrets.sh > .env)"; else ok "no change-me placeholders"; fi
  key="$(env_get CREDENTIAL_ENCRYPTION_KEY)"
  if python3 - "$key" <<'PY' 2>/dev/null
import base64, sys
sys.exit(0 if len(base64.urlsafe_b64decode(sys.argv[1].encode())) == 32 else 1)
PY
  then ok "CREDENTIAL_ENCRYPTION_KEY is a valid Fernet key"
  else fail "CREDENTIAL_ENCRYPTION_KEY is not a valid Fernet key -> POST /cameras with RTSP credentials fails (HTTP 500); backend now refuses to start"
  fi
  for v in POSTGRES_PASSWORD REDIS_PASSWORD JWT_SECRET_KEY INITIAL_ADMIN_PASSWORD EDGE_PROVISIONING_TOKEN \
           MQTT_BACKEND_PASSWORD MQTT_EDGE_PASSWORD MINIO_ROOT_USER MINIO_ROOT_PASSWORD; do
    [ -n "$(env_get "$v")" ] || fail "$v is empty"
  done
  for v in SIM_CAMERA_PASSWORD SIM_CAMERA_PUBLISH_PASSWORD; do
    [ -n "$(env_get "$v")" ] || warn "$v is empty (needed only for: docker compose --profile demo up)"
  done
  api="$(env_get NEXT_PUBLIC_API_URL)"; api="${api:-http://localhost:8000}"
  case "$api" in
    *localhost*|*127.0.0.1*) warn "NEXT_PUBLIC_API_URL=$api — only works in a browser ON this machine. From another PC: ./scripts/set-public-host.sh <vm-ip>" ;;
    *) ok "NEXT_PUBLIC_API_URL=$api" ;;
  esac
fi

echo "== Resources"
cpus="$(nproc)"; mem_gb="$(awk '/MemTotal/ {printf "%d", $2/1024/1024}' /proc/meminfo)"; disk_gb="$(df -Pk . | awk 'NR==2 {printf "%d", $4/1024/1024}')"
[ "$cpus" -ge 4 ] && ok "$cpus CPUs" || warn "$cpus CPUs — for the demo profile lower SIM_CAMERA_WIDTH/HEIGHT/FPS (e.g. 1280/720/15)"
[ "$mem_gb" -ge 7 ] && ok "${mem_gb} GB RAM" || warn "${mem_gb} GB RAM — 8 GB recommended for the full demo"
[ "$disk_gb" -ge 15 ] && ok "${disk_gb} GB free disk" || warn "${disk_gb} GB free disk — images need ~10 GB"

echo "== Ports"
for p in 3000 8000 1883 8554 8888 8889 9000; do
  owner="$(ss -Htlnp "sport = :$p" 2>/dev/null | head -1)"
  if [ -z "$owner" ]; then ok "port $p free"
  elif echo "$owner" | grep -q docker; then ok "port $p used by docker (this stack?)"
  else warn "port $p in use by another process: $(echo "$owner" | grep -o 'users:.*' )"; fi
done

echo "== Compose configuration"
if docker compose --profile demo config -q 2>/tmp/aivms-doctor.err; then
  ok "compose files parse (core + demo)"
  outside="$(docker compose --profile demo config --format json 2>/dev/null | python3 -c "
import json, os, sys
root = os.path.realpath(sys.argv[1])
d = json.load(sys.stdin)
bad = [f\"{n}={s['build']['context']}\" for n, s in d['services'].items()
       if s.get('build') and not os.path.realpath(s['build']['context']).startswith(root)]
print(' '.join(bad))" "$ROOT")"
  [ -z "$outside" ] && ok "all build contexts inside the repository" || fail "build context outside the repository: $outside"
else
  fail "docker compose config failed: $(head -3 /tmp/aivms-doctor.err)"
fi

echo "== Running stack"
if docker compose ps --format '{{.Service}}' 2>/dev/null | grep -q .; then
  docker compose --profile demo ps --format '  {{.Service}}\t{{.Status}}' 2>/dev/null
  if curl -sf -m 3 http://localhost:8000/api/v1/health/ready >/dev/null; then ok "backend ready"; else warn "backend not ready (docker compose logs backend)"; fi
else
  echo "  (not running)"
fi

echo
echo "result: $FAILS failure(s), $WARNS warning(s)"
[ "$FAILS" -eq 0 ]
