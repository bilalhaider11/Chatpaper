#!/bin/sh
set -e

if echo "${DATABASE:-}" | grep -qE '@(localhost|127\.0\.0\.1):'; then
  echo "ERROR: DATABASE points at localhost — use host 'db' in Docker (see docker-compose.yml environment)." >&2
  exit 1
fi

if [ $# -eq 0 ] || [ "$1" = "uvicorn" ]; then
  alembic upgrade head
  python scripts/seed.py
  exec uvicorn main:app --host 0.0.0.0 --port 8000 --reload
fi

exec "$@"
