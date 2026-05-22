# Chatpaper — Developer Manual

This document covers the system architecture, component design, patterns to follow when extending the codebase, and operational procedures.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│  Browser  (React 19 + Redux + Tailwind)                      │
└────────────────────────┬─────────────────────────────────────┘
                         │ HTTPS / JWT Bearer
┌────────────────────────▼─────────────────────────────────────┐
│  FastAPI  (uvicorn)                                           │
│  /api/auth  /api/files  /api/conversation  /api/chat         │
└──────┬────────────────────────────────────┬───────────────────┘
       │ SQLAlchemy ORM                      │ run_ingestion.delay()
┌──────▼──────────────┐          ┌──────────▼─────────────────┐
│  PostgreSQL          │          │  Celery Worker              │
│  users               │          │  7-stage ingestion          │
│  files_data          │◄─────────┤  (parse → chunk → embed)   │
│  document_parents    │          └──────────┬─────────────────┘
│  ingestion_jobs      │                     │ ChromaDB HTTP API
│  conversation_lists  │          ┌──────────▼─────────────────┐
│  conversations       │          │  ChromaDB                   │
└──────────────────────┘          │  child_chunks               │
                                  │  document_summaries         │
        Redis ◄───────────────────┤  propositions               │
        (broker + results)        └─────────────────────────────┘
```

---

## Repository Layout

```
Chatpaper/
├── backend/
│   ├── api/
│   │   ├── router.py                # Mounts all sub-routers under /api
│   │   └── routers/
│   │       ├── auth/auth.py         # /api/auth — login, register, user CRUD
│   │       ├── chat.py              # /api/chat — Q&A with citations
│   │       ├── conversation.py      # /api/conversation — session management
│   │       └── file_handling/
│   │           └── files.py         # /api/files — upload, download, status, delete
│   ├── core/
│   │   ├── main.py                  # App factory, middleware, sqladmin, lifespan
│   │   ├── config.py                # Pydantic Settings — single source of truth for env vars
│   │   ├── auth.py                  # JWT creation/validation, bcrypt password helpers
│   │   ├── celery_app.py            # Celery instance (broker + result backend from config)
│   │   ├── chroma.py                # ChromaDB HTTP client + 3 cached collection handles
│   │   ├── database.py              # SQLAlchemy engine + SessionLocal factory
│   │   ├── dependencies.py          # get_db(), oauth2_scheme
│   │   ├── limiter.py               # Rate limiting (slowapi)
│   │   └── llm.py                   # OpenAI client factory (embedder + chat LLM)
│   ├── models/                      # SQLAlchemy ORM models
│   ├── schema/                      # Pydantic request/response schemas
│   ├── services/                    # Business logic layer (called by routers)
│   ├── tasks/
│   │   └── ingestion_tasks.py       # Celery task — 7-stage ingestion pipeline
│   ├── alembic/versions/            # Migration files (0001–0009)
│   ├── tests/                       # pytest test suite
│   └── requirements.txt
└── frontend/                        # React SPA
```

---

## Component Breakdown

### Configuration (`core/config.py`)

All environment variables are declared as fields on the Pydantic `Settings` class. A `model_validator` raises `ValueError` at startup if any required variable (`SECRET_KEY`, `DATABASE`, `OPENAI_API_KEY`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`) is missing or empty — the server will not start with a misconfigured environment.

**Rule:** Never call `os.getenv` outside `core/config.py`. Always import the `settings` singleton.

### Authentication (`core/auth.py` + `services/auth.py`)

- Passwords hashed with bcrypt via `passlib`. `verify_password` and `authenticate_user` live in `core/auth.py`.
- Tokens are HS256-signed JWTs containing `{id, email, role}`. `create_access_token` appends an `exp` claim.
- `get_current_user` is a FastAPI dependency: decodes the token, looks up the user by email, raises HTTP 401 on any failure.
- RBAC is enforced by `models/check_role.py` `RoleChecker` — a dependency class that raises HTTP 403 if the user's role is not in the allowed set.

```python
# Admin-only route pattern
@router.get("/users", dependencies=[Depends(RoleChecker(["admin"]))])
```

### File Upload (`api/routers/file_handling/files.py` + `services/files.py`)

Upload flow:
1. `Content-Type` header checked against `settings.allowed_mime_types`.
2. File size checked via `seek(0, 2)` — no large reads into memory.
3. First 2048 bytes passed to `python-magic` to verify actual MIME (prevents Content-Type spoofing). Falls back gracefully if `python-magic` is not installed.
4. File written to `UPLOAD_DIR` with a UUID prefix.
5. `FileRecord` row created. `IngestionJob` row created. `run_ingestion.delay(job_id, file_id)` dispatches the Celery task.

Ownership is enforced by `_get_owned_file` — a module-private helper that fetches the record and raises HTTP 404 if the record does not exist or belongs to another user (admin bypasses the user check). All four file endpoints (`download`, `ingestion-status`, `reingest`, `delete`) call this helper.

### Ingestion Pipeline (`tasks/ingestion_tasks.py`)

A single Celery task (`run_ingestion`) that executes 7 stages sequentially:

| Stage | Name | Key work |
|---|---|---|
| 0 | Pre-Validation | Concurrent-job guard (DB-enforced partial unique index) |
| 1 | Structured Parse | `unstructured` per-element iteration; pandas for CSV/XLSX; chardet encoding detection; scanned-PDF density check |
| 2 | Hash + Dedup | SHA-256 streaming hash; global dedup by `(user_id, file_hash)`; page count limit; language detection |
| 3 | Parent Chunking | `RecursiveCharacterTextSplitter` (default) or `SemanticChunker`; tables kept atomic |
| 4 | Child Chunking | Per-parent child split; tables pass through as a single child |
| 5 | Embed + Upsert | Streaming one parent at a time; `is_committed` flag prevents duplicate upserts on retry |
| 6 | Summarization | Windowed map-reduce; short docs take single-call path; parallelized with `ThreadPoolExecutor` |
| 6.5 | Proposition Extract | Optional (flag); LLM decomposes parents into atomic facts; parallelized |
| 7 | Finalization | Status → `COMPLETE`; `embedding_model` written to both tables |

**Retry safety:** `document_parents.is_committed` is set to `True` after each parent's vectors are upserted. On retry, already-committed parents are skipped. On terminal failure, uncommitted rows and their ChromaDB vectors are cleaned up.

### Retrieval (`services/retrieval.py`)

Called by the chat endpoint. The `retrieve(query, user_id, file_ids, top_k)` function:

1. **Summary routing** — if `file_ids` is `None`, embeds the query against `document_summaries` to shortlist the most relevant files (avoids searching the entire corpus).
2. **Dense retrieval** — queries `child_chunks` with OpenAI embeddings; groups results by `parent_id`, keeps best similarity per parent.
3. **BM25** — PostgreSQL `ts_rank` full-text search on `document_parents.content` via a GIN index.
4. **Proposition retrieval** — optional; queries the `propositions` collection; same grouping as dense.
5. **RRF fusion** — Reciprocal Rank Fusion combines the ranked lists from steps 2–4.
6. **Score filter** — drops parents below `RETRIEVAL_MIN_SCORE` (default `0.0`; tune to `~0.3` in production).
7. **DB fetch** — fetches parent text from PostgreSQL for the top-k survivors.

All ChromaDB queries include a `user_id` filter in the `where` clause — multi-tenancy is enforced at the vector store layer, not just at the application layer.

### Chat Endpoint (`api/routers/chat.py`)

`POST /api/chat/{conversation_id}/ask`:

1. Verifies the user owns the conversation (HTTP 404 otherwise).
2. Fetches the last `CHAT_HISTORY_TURNS` messages from the DB, truncated to `CHAT_HISTORY_MAX_CHARS`.
3. Builds a contextualized query by prepending the last `RETRIEVAL_HISTORY_CONTEXT_TURNS` assistant turns to the user's question — this fixes retrieval degradation on follow-up questions like "What did they find there?".
4. Calls `retrieve()` with the enriched query and optional `file_ids`.
5. Builds a LangChain prompt: numbered context blocks + history + `HumanMessage(raw question)`.
6. Invokes the chat LLM (`gpt-4o-mini` by default).
7. Scans the answer for `[N]` citation markers using regex; only referenced contexts are returned as citations.
8. Saves the user turn and assistant turn to the `conversations` table.

### ChromaDB Client (`core/chroma.py`)

Three collections are used:
- `child_chunks` — primary retrieval (child-level embeddings with full metadata)
- `document_summaries` — document-level summary embeddings for summary routing
- `propositions` — optional atomic fact embeddings

Collection handles are module-level cached — the HTTP client is created once and reused. `delete_vectors_for_file(file_id)` removes all vectors for a given file from all three collections (called during file deletion).

Every vector upserted to `child_chunks` carries this metadata:

```
file_id        int     — links to files_data.id
user_id        int     — multi-tenant filtering
parent_id      str     — SHA-256 of file_hash:chunk_index (links to document_parents.id)
child_index    int     — position within parent
chunk_index    int     — parent position within document
page_start     int     — first page this chunk covers
page_end       int     — last page this chunk covers
element_types  str     — comma-separated: "NarrativeText,Table"
file_type      str     — MIME type
language       str     — ISO 639-1 code (or "unknown")
file_hash      str     — global dedup cross-reference
filename       str     — display convenience
```

---

## Database Schema

| Table | Key columns |
|---|---|
| `users` | `id`, `email`, `password` (hashed), `role` (user/admin), `is_active` |
| `files_data` | `id`, `user_id`, `filename`, `filepath`, `file_hash`, `ingestion_status`, `language`, `embedding_model` |
| `document_parents` | `id` (SHA-256), `file_id`, `user_id`, `content`, `chunk_index`, `page_start`, `page_end`, `element_types`, `is_committed`, `embedding_model` |
| `ingestion_jobs` | `id`, `file_id`, `status`, `stage`, `error_message`, `error_type`, `retry_count`, `celery_task_id` |
| `conversation_lists` | `id`, `user_id`, `conversation_title`, `is_active` |
| `conversations` | `id`, `chat_id` (FK → conversation_lists), `statement`, `user_type` |

Migration chain runs `0001` → `0009` (head) automatically at startup via `alembic upgrade head` inside the FastAPI `lifespan` hook.

---

## Security Measures

| Threat | Mitigation |
|---|---|
| File type spoofing | `python-magic` reads first 2048 bytes; `Content-Type` header not trusted |
| Oversized uploads | Size checked before disk write; HTTP 413 returned |
| Unauthenticated file download | Static mount removed; `GET /files/{id}/download` requires valid JWT |
| Cross-user file access | All file endpoints verify `file.user_id == current_user.id`; return 404 not 403 |
| Cross-user conversation access | Conversation endpoints verify ownership |
| Admin panel exposure | `AuthenticationBackend` on sqladmin; `User.password` removed from column list |
| JWT forgery via empty secret | `model_validator` raises `ValueError` at startup if `SECRET_KEY` is empty |
| Hardcoded CORS origins | Read from `CORS_ALLOWED_ORIGINS` env var |
| Malformed email registration | `EmailStr` validator on `UserBase.email` |

---

## Configuration Reference

All settings are read from environment variables. Declared in `core/config.py` — never call `os.getenv` elsewhere.

| Env Var | Default | Purpose |
|---|---|---|
| `SECRET_KEY` | **required** | JWT signing key |
| `DATABASE` | **required** | PostgreSQL connection string |
| `OPENAI_API_KEY` | **required** | OpenAI API key |
| `ADMIN_USERNAME` | **required** | sqladmin login username |
| `ADMIN_PASSWORD` | **required** | sqladmin login password |
| `ALGORITHM` | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | JWT lifetime |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding model |
| `OPENAI_CHAT_MODEL` | `gpt-4o-mini` | Chat / summarization model |
| `LLM_SUMMARY_TEMPERATURE` | `0.1` | LLM temperature for summarization |
| `CHROMA_HOST` | `localhost` | ChromaDB host |
| `CHROMA_PORT` | `8001` | ChromaDB port |
| `CHROMA_COLLECTION_CHILD_CHUNKS` | `child_chunks` | Collection name |
| `CHROMA_COLLECTION_SUMMARIES` | `document_summaries` | Collection name |
| `CHROMA_COLLECTION_PROPOSITIONS` | `propositions` | Collection name |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis client URL. If auth required: `redis://:password@localhost:6379/0` |
| `CELERY_BROKER_URL` | `redis://localhost:6379/0` | Celery broker. Same auth format as `REDIS_URL` |
| `CELERY_RESULT_BACKEND` | `redis://localhost:6379/1` | Celery result backend. Same auth format as `REDIS_URL` |
| `MAX_FILE_SIZE_MB` | `200` | Reject uploads above this size |
| `MAX_PAGES_PER_DOC` | `500` | Fail ingestion if page count exceeds |
| `PARENT_CHUNK_SIZE` | `1800` | Max chars per parent chunk |
| `PARENT_CHUNK_OVERLAP` | `200` | Overlap between parent chunks |
| `CHILD_CHUNK_SIZE` | `400` | Max chars per child chunk |
| `CHILD_CHUNK_OVERLAP` | `60` | Overlap between child chunks |
| `EMBEDDING_BATCH_SIZE` | `100` | Vectors per ChromaDB upsert batch |
| `SCANNED_PDF_MIN_FILE_SIZE_BYTES` | `51200` | Min file size to trigger density check |
| `SCANNED_PDF_TEXT_DENSITY_THRESHOLD` | `0.001` | text_len / file_size below this → LIKELY_SCANNED_PDF |
| `SUMMARY_SHORT_DOC_THRESHOLD` | `12000` | Docs below this use single-call summarization |
| `SUMMARY_WINDOW_SIZE` | `10000` | Chars per map-reduce window |
| `SUMMARY_EXTRACTION_CONCURRENCY` | `5` | ThreadPoolExecutor workers for map phase |
| `USE_SEMANTIC_CHUNKER` | `false` | Enable SemanticChunker for parent splitting |
| `USE_PROPOSITION_EXTRACTION` | `false` | Enable Stage 6.5 proposition extraction |
| `PROPOSITION_EXTRACTION_CONCURRENCY` | `5` | ThreadPoolExecutor workers for proposition LLM calls |
| `UPLOAD_DIR` | *(project root `files/`)* | Absolute path for uploaded files |
| `RETRIEVAL_MIN_SCORE` | `0.0` | Drop RRF results below this score (tune to ~0.3) |
| `RETRIEVAL_HISTORY_CONTEXT_TURNS` | `2` | Prior assistant turns prepended to retrieval query |
| `CHAT_HISTORY_TURNS` | `6` | Max conversation turns fetched |
| `CHAT_HISTORY_MAX_CHARS` | `8000` | Total char budget for history before truncation |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173,...` | Comma-separated allowed origins |

---

## Dependencies

| Package | Purpose |
|---|---|
| `fastapi` / `uvicorn` | Web framework and ASGI server |
| `sqlalchemy` / `alembic` | ORM and database migrations |
| `python-jose` / `passlib` | JWT creation/validation and bcrypt hashing |
| `celery` / `redis` | Background task queue and broker |
| `chromadb` | Vector store HTTP client |
| `openai` / `langchain` | Embeddings, chat LLM, and prompt construction |
| `unstructured` | Document parsing (PDF, DOCX, TXT) |
| `pandas` / `openpyxl` | Structured CSV/XLSX parsing in Stage 1 |
| `langdetect` | Language detection in Stage 2 |
| `chardet` | Encoding detection for TXT files in Stage 1 |
| `python-magic` | MIME type validation from file bytes at upload |
| `sqladmin` | Admin panel (authenticated, password-safe) |
| `langchain-experimental` | SemanticChunker (behind `USE_SEMANTIC_CHUNKER` flag) |
| `rank-bm25` | Not used — PostgreSQL FTS used instead |
| `pytesseract` | Not used — OCR is a future enhancement |

---

## Running the Test Suite

```bash
cd backend && source venv/bin/activate
pytest tests/ -v
```

Tests use `pytest-mock`. The test files follow a consistent structure:
- One class per route or service function.
- One test method per behavior (happy path + at least one failure/edge case).
- Router tests use `FastAPI` + `TestClient` with `dependency_overrides` for `get_current_user` and `get_db`.
- Service tests call service functions directly with mock DB objects.

**Do not mock the database in integration tests.** Use a real test database to catch migration and query issues that mocks would hide.

---

## Creating a Migration

```bash
cd backend && source venv/bin/activate
alembic revision --autogenerate -m "describe your change"
```

Review the generated file in `alembic/versions/` before applying — autogenerate misses server-side defaults and custom index types. Then apply:

```bash
alembic upgrade head
```

**Never edit an existing migration file.** Once a migration has been committed and run, it is immutable. Create a new migration for any follow-up changes.

---

## Adding a New Endpoint

1. Add the route to the appropriate router in `api/routers/` (or create a new router).
2. If it's a new router, mount it in `api/router.py`.
3. Put business logic in `services/` — keep routers thin (validate input, call service, return response).
4. For user-owned data, follow the ownership helper pattern:

```python
def _get_owned_thing(db: Session, thing_id: int, user: User) -> Thing:
    record = db.query(Thing).filter(Thing.id == thing_id).first()
    if record is None or (user.role != UserRole.admin and record.user_id != user.id):
        raise HTTPException(status_code=404, detail="Not found")
    return record
```

5. Return **404, not 403**, for cross-user resource access — 403 reveals that the resource exists.
6. Every query on user-owned data must include a `user_id` filter. No exceptions.
7. Add tests in `tests/` covering the happy path and at least one error case.

---

## Multi-Tenancy Rules

| Layer | Enforcement |
|---|---|
| API routers | `_get_owned_*` helpers check `record.user_id == current_user.id` |
| ChromaDB queries | `where={"user_id": user_id}` on every collection query |
| PostgreSQL queries | `filter(Model.user_id == user_id)` on every service query |
| Celery tasks | Exempt — `file_id` ownership was verified when the task was queued |

---

## Design Decisions

| Decision | Reason | Alternatives rejected |
|---|---|---|
| Three ChromaDB collections | Separates precision retrieval (child chunks), routing signals (summaries), and atomic facts (propositions) | Single collection confounds embedding spaces |
| SHA-256 deterministic ChromaDB IDs | Idempotent upsert on retry; no vector duplication if worker crashes mid-stage | UUID IDs are non-deterministic; retry creates duplicate vectors |
| `is_committed` flag on document_parents | Allows Stage 5 to resume from the last uncommitted parent on retry without re-embedding already-upserted chunks | No flag means a crash mid-stage leaves partial writes with no recovery path |
| Global dedup by `(user_id, file_hash)` | Prevents re-embedding the same file uploaded twice under different names; hash computed during ingestion at Stage 2 | Dedup by file_id only catches same-record re-submission, not same-content re-uploads |
| Partial unique index for concurrent-job guard | Database-enforced: only one non-terminal IngestionJob per file at a time; prevents two workers racing on the same file | Application-level check alone is subject to race conditions |
| PostgreSQL FTS over rank-bm25 | Same DB, no extra service; GIN index provides fast keyword search; BM25 scoring via `ts_rank` | Elasticsearch (separate infrastructure, operationally heavier) |
| ThreadPoolExecutor over asyncio in Celery | Celery workers are synchronous; `asyncio.gather` requires an event loop that Celery does not provide by default | `asyncio.run()` wrapper inside Celery adds overhead and nesting complexity |
| Authenticated download endpoint | Static file mounts bypass FastAPI's dependency injection — auth cannot be enforced; `FileResponse` from a route handler keeps the full JWT chain intact | Custom auth middleware on the static mount is fragile and runs before routing |
| 404 not 403 for cross-user resources | Do not reveal resource existence to non-owners — 403 confirms the resource exists | 403 leaks information about other users' data |
| Conversational query enrichment over HyDE | Prepending the last assistant turn to the retrieval query is deterministic, adds zero API calls, and fixes the majority of multi-turn follow-up degradation | HyDE (generate a hypothetical answer then embed it) adds one full LLM call to every retrieval |
| sqladmin AuthenticationBackend | Protects the admin panel with a separate credential without removing operational tooling | Removing sqladmin entirely; reverse-proxy basic auth (fragile, not app-integrated) |
| Startup validation for required secrets | An empty `SECRET_KEY` signs tokens that any attacker can forge; failing at startup surfaces misconfiguration in CI before any requests are served | Logging a warning only (ignored in automated deployments) |
| pandas for CSV/XLSX | Preserves column structure and headers; enables Markdown table serialization per row group | unstructured destroys table structure; rows become space-separated values |
| `text-embedding-3-small` | Cost-effective; 1536 dimensions; strong multilingual support | `text-embedding-3-large` (marginal quality gain at higher cost) |
