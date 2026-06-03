# Docker

Runs **frontend** and **backend** in containers, plus PostgreSQL, Redis, and RabbitMQ.

**Not included** (by design):

- **Celery worker** — document ingestion tasks will not run until you start a worker on the host (or add your own service).
- **ChromaDB** — the API connects to Chroma via `CHROMA_HOST` / `CHROMA_PORT` (default: `host.docker.internal:8001`). Start Chroma on the host, for example:

  ```bash
  chroma run --host 0.0.0.0 --port 8001 --path ./chroma-data
  ```

## Quick start

```bash
cp backend/.env.docker.example backend/.env
# Edit backend/.env — set OPENAI_API_KEY, SECRET_KEY, ADMIN_PASSWORD

docker compose up --build
```

| Service   | URL |
|-----------|-----|
| Frontend  | http://localhost:5173 |
| API / docs | http://localhost:8000/docs |
| Postgres  | `localhost:5432` (user/pass/db: `postgres` / `postgres` / `chatbot`) |
| Redis     | `localhost:6379` |
| RabbitMQ  | AMQP `localhost:5673`, UI http://localhost:15673 (guest/guest) — host ports avoid conflict with a local RabbitMQ on 5672 |

## Environment

Use `backend/.env.docker.example` as a template. Docker-specific values:

- `DATABASE` → `postgresql://postgres:postgres@localhost:5432/chatbot` (also set in `docker-compose.yml` so a host `.env` with `127.0.0.1` still works)
- `REDIS_URL` / `RABBITMQ_URL` → compose service hostnames
- `CHROMA_HOST` → `host.docker.internal` when Chroma runs on the host
- `UPLOAD_DIR` → `/app/files` (backed by the `upload_data` volume)

The frontend build reads `VITE_API_BASE_URL` at dev-server startup (default in compose: `http://localhost:8000/api`).

## Optional: Celery on the host

```bash
cd backend && source venv/bin/activate
export $(grep -v '^#' .env | xargs)   # use same .env; point REDIS_URL etc. at localhost ports
celery -A core.celery_app worker --loglevel=info
```

Use `localhost` instead of `redis` / `db` hostnames when running workers outside Docker.
