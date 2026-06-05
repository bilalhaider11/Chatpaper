# Chatpaper

AI-powered document Q&A. Upload PDFs, Word docs, spreadsheets, or plain text files and ask questions grounded in your content. Every answer includes numbered citations linked back to the exact source passage.

---

## How It Works

```
Upload → Celery ingestion (parse → chunk → embed) → ChromaDB + PostgreSQL
Ask    → dense retrieval + BM25 + RRF fusion → GPT-4o-mini → cited answer
```

---

## Tech Stack

**Backend**
- Python 3.11+, FastAPI, Uvicorn
- SQLAlchemy 2.0 + Alembic (PostgreSQL)
- Celery + Redis (background ingestion tasks)
- ChromaDB (vector store — 3 collections)
- OpenAI (embeddings: `text-embedding-3-small`, chat: `gpt-4o-mini`)
- JWT auth (python-jose + passlib/bcrypt), sqladmin panel

**Frontend**
- React 19 + TypeScript + Vite (build tooling), served via `serve` in Docker
- Redux Toolkit, React Router DOM, Tailwind CSS, Axios

---

## Quick Start with Docker

Docker Compose runs the full stack — PostgreSQL, Redis, RabbitMQ, ChromaDB, FastAPI backend, Celery worker, Celery Beat scheduler, and the React frontend — with a single command.

### 1. Copy and fill in secrets

```bash
cp backend/.env.example backend/.env
```

Edit `backend/.env` and set at minimum:

```env
SECRET_KEY=   # python -c "import secrets; print(secrets.token_hex(32))"
OPENAI_API_KEY=sk-...
ADMIN_USERNAME=admin
ADMIN_PASSWORD=changeme
```

### 2. Start the stack

```bash
docker compose up --build
```

The first build takes several minutes (Python/torch dependencies). Subsequent starts are fast.

### 3. Service URLs (Docker)

| Service | URL / Connection |
|---|---|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| Swagger / API docs | http://localhost:8000/docs |
| Admin panel | http://localhost:8000/admin |
| RabbitMQ management | http://localhost:15673 |
| Flower (Celery monitor) | http://localhost:5555 |
| ChromaDB API | http://localhost:8001 |
| PostgreSQL (pgAdmin) | host `localhost`, port `5434`, db `chatpaper`, user `postgres`, password `postgres` |
| Redis (RedisInsight) | host `localhost`, port `6380` |

---

## Prerequisites (local development)

| Service | Version | Notes |
|---|---|---|
| Python | 3.11+ | |
| Node.js | 18+ | |
| PostgreSQL | 14+ | Database for app data |
| Redis | 7+ | Celery broker + result backend |
| ChromaDB | latest | Vector store; run as HTTP server on port 8001 |
| OpenAI API key | — | Required for embeddings and chat |

---

## Quick Start (local development)

### 1. Start external services

```bash
# Redis
redis-server

# ChromaDB (use venv path — system may have an unrelated 'chroma' command)
backend/venv/bin/chroma run --host localhost --port 8001 --path ./chroma-data
```

### 2. Clone and run setup

```bash
git clone <repository-url>
cd Chatpaper
bash setup.sh
```

`setup.sh` will:
- Create a Python virtual environment and install backend dependencies
- Generate `backend/.env` with a random `SECRET_KEY` and `ADMIN_PASSWORD`
- Create the PostgreSQL database
- Run Alembic migrations to head
- Seed an admin user
- Install frontend npm dependencies

### 3. Add required secrets to `backend/.env`

`setup.sh` cannot fill these — add them manually:

```env
OPENAI_API_KEY=sk-...
```

See [Environment Variables](#environment-variables) for the full list.

### 4. Start all services

**Backend API** (terminal 1):
```bash
cd backend && source venv/bin/activate
uvicorn main:app --reload --port 8000
```

**Celery worker** (terminal 2 — required for document ingestion):
```bash
cd backend && source venv/bin/activate
celery -A core.celery_app worker --loglevel=info
```

**Frontend** (terminal 3):
```bash
cd frontend && npm run dev
```

---

## Service URLs (local development)

| Service | URL |
|---|---|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| Swagger / API docs | http://localhost:8000/docs |
| Admin panel | http://localhost:8000/admin |

---

## Environment Variables

`backend/.env` — all variables and their defaults.

| Variable | Required | Default | Description |
|---|---|---|---|
| `SECRET_KEY` | **yes** | — | JWT signing key; generate with `python -c "import secrets; print(secrets.token_hex(32))"` |
| `DATABASE` | **yes** | — | PostgreSQL connection string, e.g. `postgresql://user:pass@localhost:5432/chatpaper` |
| `OPENAI_API_KEY` | **yes** | — | OpenAI API key |
| `ADMIN_USERNAME` | **yes** | — | sqladmin login username |
| `ADMIN_PASSWORD` | **yes** | — | sqladmin login password |
| `ALGORITHM` | no | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | no | `30` | JWT lifetime in minutes |
| `OPENAI_EMBEDDING_MODEL` | no | `text-embedding-3-small` | Embedding model |
| `OPENAI_CHAT_MODEL` | no | `gpt-4o-mini` | Chat and summarization model |
| `CHROMA_HOST` | no | `localhost` | ChromaDB host |
| `CHROMA_PORT` | no | `8001` | ChromaDB port |
| `REDIS_URL` | no | `redis://localhost:6379/0` | Redis URL for the app |
| `CELERY_BROKER_URL` | no | `redis://localhost:6379/0` | Celery broker |
| `CELERY_RESULT_BACKEND` | no | `redis://localhost:6379/1` | Celery result backend |
| `MAX_FILE_SIZE_MB` | no | `200` | Maximum upload size in MB |
| `UPLOAD_DIR` | no | `<project root>/files/` | Absolute path for uploaded files on disk |
| `RETRIEVAL_MIN_SCORE` | no | `0.0` | Minimum RRF score to include a passage (tune to ~0.3) |
| `CORS_ALLOWED_ORIGINS` | no | `http://localhost:5173,...` | Comma-separated list of allowed CORS origins |
| `USE_SEMANTIC_CHUNKER` | no | `false` | Use LangChain SemanticChunker instead of recursive splitter |
| `USE_PROPOSITION_EXTRACTION` | no | `false` | Enable atomic proposition extraction (Stage 6.5) |

For the full list of ingestion and retrieval tuning variables see [INGESTION_PLAN.md — Configuration Reference](INGESTION_PLAN.md#configuration-reference).

---

## API Overview

| Method | Route | Description | Auth |
|---|---|---|---|
| POST | `/api/auth/login` | Login, returns JWT | Public |
| POST | `/api/auth/users` | Register a new user | Public |
| GET | `/api/auth/users/me` | Get current user | User |
| GET | `/api/auth/users` | List all users | Admin |
| POST | `/api/files/upload` | Upload a document | User |
| GET | `/api/files/` | List your files | User |
| GET | `/api/files/{id}/download` | Download a file | User |
| GET | `/api/files/{id}/ingestion-status` | Check ingestion progress | User |
| POST | `/api/files/{id}/reingest` | Re-queue a failed ingestion | User |
| DELETE | `/api/files/{id}` | Delete a file and its vectors | User |
| POST | `/api/conversation/inconversationlist` | Create a conversation | User |
| PATCH | `/api/conversation/conversation-title/{id}` | Rename a conversation | User |
| GET | `/api/conversation/get_conversation_list` | List conversations | User |
| GET | `/api/conversation/get-conversation/{id}` | Get messages in a conversation | User |
| POST | `/api/chat/{conversation_id}/ask` | Ask a question, get a cited answer | User |

---

## Further Reading

- [User Manual](USER_MANUAL.md) — how to upload documents, start conversations, and read citations
- [Developer Manual](DEVELOPER_MANUAL.md) — architecture, components, configuration reference, and design decisions
