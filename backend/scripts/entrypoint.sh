#!/bin/sh
set -e

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  echo "[entrypoint] running database migrations"
  # retry: postgres may still be starting
  for i in 1 2 3 4 5 6 7 8 9 10; do
    alembic upgrade head && break
    echo "[entrypoint] migration attempt $i failed, retrying in 3s"
    sleep 3
  done
  echo "[entrypoint] seeding initial data"
  python -m app.cli.seed
fi

exec "$@"
