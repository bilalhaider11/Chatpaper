# Chatpaper — RAG Architecture Reference

**Branch:** `RAG-Implementation`  
**Last updated:** 2026-05-20 (all phases implemented)

This document describes the implemented system architecture, design decisions, and configuration reference. All ingestion, retrieval, and security work described here is complete and in production code.

---

## System State

| Component | Status |
|---|---|
| FastAPI backend, JWT + RBAC auth | Working |
| PostgreSQL models + Alembic migrations (head: 0009) | Working |
| Celery + Redis task queue | Working |
| ChromaDB HTTP client — three collections, cached | Working |
| 7-stage ingestion pipeline | Working |
| File upload: pre-validation, MIME magic, size check | Working |
| Retrieval: dense + BM25 + RRF + summary routing + propositions | Working |
| Chat endpoint: multi-turn, grounded citations, contextualized retrieval | Working |
| sqladmin panel: authenticated, password hashes hidden | Working |
| Startup secret validation | Working |
| Authenticated file download endpoint (static mount removed) | Working |

---

## Storage Layers

```
PostgreSQL
  files_data          — file ownership, hash, ingestion status, language, embedding_model
  document_parents    — parent chunk text, page range, element types, is_committed flag, embedding_model
  ingestion_jobs      — per-stage progress, retry tracking, error classification

ChromaDB  (cosine distance, module-level cached references)
  child_chunks        — child embeddings + full per-chunk metadata (primary retrieval collection)
  document_summaries  — document-level summary embeddings (routing / coarse retrieval)
  propositions        — atomic factual proposition embeddings (optional; behind feature flag)
```

---

## Ingestion Pipeline (7 Stages)

```
Stage 0  Pre-Validation       File size (HTTP 413), python-magic MIME check (HTTP 415), concurrent-job guard
Stage 1  Structured Parse     unstructured per-element iteration; CSV/XLSX via pandas (Markdown table rows)
                               chardet encoding detection for TXT; scanned-PDF text density check
Stage 2  Hash + Dedup         SHA-256 streaming hash; global dedup by (user_id, file_hash)
                               page count enforced against max_pages_per_doc; language detection via langdetect
Stage 3  Parent Chunking      RecursiveCharacterTextSplitter (default) or SemanticChunker (USE_SEMANTIC_CHUNKER=true)
                               table elements kept atomic; page_start/page_end mapped per chunk
Stage 4  Child Chunking       per-parent child split; tables pass through as single child
Stage 5  Embed + Upsert       streaming one parent at a time; is_committed flag prevents partial re-upsert on retry
                               full metadata: user_id, filename, file_type, language, page_start, page_end,
                               element_types, file_hash, chunk_index, child_index, parent_id
Stage 6  Summarization        windowed map-reduce (SUMMARY_WINDOW_SIZE chars per window);
                               map phase parallelized with ThreadPoolExecutor (SUMMARY_EXTRACTION_CONCURRENCY)
                               short docs (< SUMMARY_SHORT_DOC_THRESHOLD) use single-call path
Stage 6.5 Proposition Extract optional (USE_PROPOSITION_EXTRACTION=true); LLM decomposes each parent into
                               atomic factual statements; parallelized with ThreadPoolExecutor
Stage 7  Finalization         status → COMPLETE, embedding_model written to files_data + document_parents
```

On any terminal failure:
- `document_parents` rows with `is_committed=False` are deleted (no orphaned partial writes)
- `files_data.ingestion_status` is synced to the job status (FAILED_RETRYABLE or FAILED_PERMANENT)

---

## ChromaDB Child Chunk Metadata Schema

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

## Retrieval Pipeline

```
retrieve(query, user_id, file_ids?, top_k)
  1. Summary routing   — if file_ids is None, embed query against document_summaries
                         to narrow to the top-N most relevant files
  2. Dense retrieve    — query child_chunks collection filtered by user_id (+ file_ids if set)
                         group by parent_id; keep best similarity per parent
  3. BM25 retrieve     — PostgreSQL full-text search on document_parents.content
                         returns {parent_id: rank} dict
  4. Proposition retr. — optional; query propositions collection; same grouping as dense
  5. RRF fusion        — Reciprocal Rank Fusion across all result lists
  6. Score filter      — drop parents below RETRIEVAL_MIN_SCORE (default 0.0; tune to ~0.3)
  7. DB fetch          — retrieve parent text from PostgreSQL for top_k parents
```

---

## Chat Endpoint

```
POST /api/chat/{conversation_id}/ask
  1. Fetch history    — last CHAT_HISTORY_TURNS turns, truncated to CHAT_HISTORY_MAX_CHARS
  2. Build query      — prepend last RETRIEVAL_HISTORY_CONTEXT_TURNS assistant turns to question
                        (fixes follow-up question retrieval degradation)
  3. Retrieve         — call retrieve() with contextualized query
  4. Build prompt     — numbered context blocks + history + HumanMessage(raw question)
  5. LLM invoke       — gpt-4o-mini
  6. Ground citations — regex scan for [N] markers in answer; only referenced contexts become citations
  7. Persist          — save user + assistant turns to conversation table
```

---

## Security Measures

| Threat | Mitigation |
|---|---|
| File type spoofing | `python-magic` reads first 2048 bytes; `Content-Type` header not trusted |
| Oversized uploads | Size checked before disk write; HTTP 413 returned |
| Unauthenticated file download | Static mount removed; `GET /files/{id}/download` requires valid JWT |
| Cross-user file access | All file endpoints verify `file.user_id == current_user.id`; return 404 not 403 |
| Cross-user conversation access | Conversation endpoints verify ownership; `PATCH /conversation-title/{id}` fixed |
| Admin panel exposure | `AuthenticationBackend` on sqladmin; `User.password` removed from column list |
| JWT forgery via empty secret | `model_validator` raises `ValueError` at startup if `SECRET_KEY` is empty |
| Hardcoded CORS origins | Read from `CORS_ALLOWED_ORIGINS` env var |
| Malformed email registration | `EmailStr` validator on `UserBase.email` |

---

## Configuration Reference

All settings are read from environment variables with the listed defaults.

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
| `REDIS_URL` | `redis://localhost:6379/0` | Redis client URL |
| `CELERY_BROKER_URL` | `redis://localhost:6379/0` | Celery broker |
| `CELERY_RESULT_BACKEND` | `redis://localhost:6379/1` | Celery result backend |
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

## Database Migrations

| Migration file | What it adds |
|---|---|
| `0001` – `0006` | Users, files_data, conversations, document_parents, ingestion_jobs baseline schema |
| `0007_add_dedup_and_job_guard_indexes.py` | `UNIQUE INDEX (user_id, file_hash)` on files_data; partial unique index on ingestion_jobs active jobs |
| `0008_add_is_committed_and_embedding_model.py` | `is_committed BOOLEAN` on document_parents; `embedding_model VARCHAR(100)` on files_data and document_parents |
| `0009_add_fts_index.py` | GIN full-text search index on document_parents.content for BM25 retrieval |

---

## Dependencies

| Package | Purpose |
|---|---|
| `langchain-experimental` | SemanticChunker (behind `USE_SEMANTIC_CHUNKER` flag) |
| `langdetect` | Language detection in Stage 2 |
| `chardet` | Encoding detection for TXT files in Stage 1 |
| `python-magic` | MIME type validation from file bytes at upload |
| `pandas` / `openpyxl` | Structured CSV/XLSX parsing in Stage 1 |
| `rank-bm25` | Not used — PostgreSQL FTS used instead (same DB, no extra infrastructure) |
| `pytesseract` | Not used — OCR is a future / optional enhancement |

---

## Design Decisions

| Decision | Reason | Alternatives rejected |
|---|---|---|
| Three ChromaDB collections | Separates precision retrieval (child chunks), routing signals (summaries), and atomic facts (propositions) | Single collection confounds embedding spaces |
| SHA-256 deterministic ChromaDB IDs | Idempotent upsert on retry; no vector duplication if worker crashes mid-stage | UUID IDs are non-deterministic; retry creates duplicate vectors |
| `is_committed` flag on document_parents | Allows Stage 5 to resume from the last uncommitted parent on retry without re-embedding already-upserted chunks | No flag means a crash mid-stage leaves partial writes with no recovery path |
| Global dedup by `(user_id, file_hash)` | Prevents re-embedding the same file uploaded twice under different names; hash computed during ingestion at Stage 2 | Dedup by file_id only catches same-record re-submission, not same-content re-uploads |
| Partial unique index for concurrent-job guard | Database-enforced: only one non-terminal IngestionJob per file at a time; prevents two workers racing on the same file | Application-level check alone is subject to race conditions |
| postgresql FTS over rank-bm25 | Same DB, no extra service; GIN index provides fast keyword search; BM25 scoring via `ts_rank` | Elasticsearch (separate infrastructure, operationally heavier) |
| ThreadPoolExecutor over asyncio in Celery | Celery workers are synchronous; `asyncio.gather` requires an event loop that Celery does not provide by default | `asyncio.run()` wrapper inside Celery adds overhead and nesting complexity |
| Authenticated download endpoint | Static file mounts bypass FastAPI's dependency injection — auth cannot be enforced; `FileResponse` from a route handler keeps the full JWT chain intact | Custom auth middleware on the static mount is fragile and runs before routing |
| 404 not 403 for cross-user resources | Do not reveal resource existence to non-owners — 403 confirms the resource exists | 403 leaks information about other users' data |
| Conversational query enrichment over HyDE | Prepending the last assistant turn to the retrieval query is deterministic, adds zero API calls, and fixes the majority of multi-turn follow-up degradation | HyDE (generate a hypothetical answer then embed it) adds one full LLM call to every retrieval |
| sqladmin AuthenticationBackend | Protects the admin panel with a separate credential without removing operational tooling | Removing sqladmin entirely; reverse-proxy basic auth (fragile, not app-integrated) |
| Startup validation for required secrets | An empty `SECRET_KEY` signs tokens that any attacker can forge; failing at startup surfaces misconfiguration in CI before any requests are served | Logging a warning only (ignored in automated deployments) |
| pandas for CSV/XLSX | Preserves column structure and headers; enables Markdown table serialization per row group | unstructured destroys table structure; rows become space-separated values |
| `text-embedding-3-small` | Cost-effective; 1536 dimensions; strong multilingual support | `text-embedding-3-large` (marginal quality gain at higher cost) |
