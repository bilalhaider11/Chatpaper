#!/bin/sh
set -e

# Compose must reach Postgres via the service name, not localhost.
if echo "${DATABASE:-}" | grep -qE '@(localhost|127\.0\.0\.1):'; then
  echo "ERROR: DATABASE points at localhost — use host 'db' in Docker (see docker-compose.yml environment)." >&2
  exit 1
fi

# Migrations also run in FastAPI lifespan; this ensures tables exist before seeding.
alembic upgrade head
python scripts/seed.py

exec uvicorn main:app --host 0.0.0.0 --port 8000
