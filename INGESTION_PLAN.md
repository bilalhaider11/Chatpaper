# Chatpaper — Ingestion & Vectorization Implementation Plan

**Branch:** `RAG-Implementation`  
**Last updated:** 2026-05-19  
**Purpose:** Authoritative reference for what is implemented, what is in progress, and what is planned. Consult this when context is lost between sessions.

---

## How to Read This Document

- `[x]` — Fully implemented and verified
- `[ ]` — Not yet implemented
- Each phase must be completed in order before the next begins
- Each item includes a **Why** (the production risk it addresses) and **Where** (which file(s) to touch)

---

## Current System State (as of 2026-05-19)

### What Is Working

| Component | Status |
|---|---|
| FastAPI backend, auth (JWT + RBAC), file upload endpoint | Working |
| PostgreSQL models: `users`, `files_data`, `conversationlist`, `conversation` | Working |
| PostgreSQL models: `document_parents`, `ingestion_jobs` | Working |
| Alembic migrations 0001–0006 | Applied |
| Celery + Redis task queue | Working |
| ChromaDB HTTP client (`core/chroma.py`) with two collections | Working |
| 6-stage ingestion Celery task (`tasks/ingestion_tasks.py`) | Working (with gaps — see below) |
| Ingestion status endpoint `GET /files/{id}/ingestion-status` | Working |
| File delete endpoint `DELETE /files/{id}` | Working — ChromaDB vector cleanup added (Phase 0) |

### Known Gaps in the Existing Implementation

These are bugs or missing features that exist today and must be fixed before the retrieval layer is designed.

| # | Gap | Severity | Phase |
|---|---|---|---|
| G1 | `user_id` is absent from all ChromaDB metadata — multi-tenant filtering is impossible | Critical | Phase 0 |
| G2 | No pre-validation before Celery dispatch — oversized/corrupt files occupy a worker for minutes before failing | High | Phase 0 |
| G3 | Dedup checks `DocumentParent` existence by `file_id`, not by `(user_id, file_hash)` — same file uploaded twice under different name is re-embedded at full cost | High | Phase 0 |
| G4 | No concurrent-job guard — double-dispatch creates two workers racing on the same file | High | Phase 0 |
| G5 | Scanned PDFs (zero extractable text) are ingested silently as near-empty vectors, polluting the vector space | High | Phase 0 |
| G6 | `page_start` / `page_end` columns exist in `document_parents` but are never populated — always NULL | Medium | Phase 1 |
| G7 | `element_types` is a document-level array in `document_parents`, never written to ChromaDB child chunk metadata — structural filtering at retrieval time is impossible | Medium | Phase 1 |
| G8 | `DELETE /files/{id}` deletes the file and PostgreSQL row but does NOT delete ChromaDB vectors — orphaned vectors accumulate indefinitely | High | Phase 0 |
| G9 | No `is_committed` flag on `document_parents` — a failure at Stage 5 after partial writes causes the dedup check to falsely return COMPLETE on retry, leaving vectors permanently missing | Medium | Phase 1 |
| G10 | No `embedding_model` column anywhere — when the embedding model is upgraded, there is no way to identify which documents need re-embedding | Low | Phase 1 |
| G11 | Entire `parents_with_children` list is held in memory simultaneously — unsafe for large documents | Medium | Phase 1 |
| G12 | Document summary is generated from only the first 12,000 characters — unreliable for documents > ~10 pages | Medium | Phase 1 |
| G13 | Language is never detected despite `langdetect` being installed — `language` column in `files_data` is always NULL | Low | Phase 1 |
| G14 | CSV/XLSX uses `unstructured` raw text extraction — table structure is destroyed, chunking is semantically meaningless for tabular data | Medium | Phase 1.5 |
| G15 | TXT files have no encoding detection — `chardet` is installed but not used; non-UTF-8 files produce garbled text silently | Low | Phase 1.5 |
| G16 | Table boundaries are not enforced during chunking — a table can be split mid-row across two parent chunks | Medium | Phase 1.5 |

---

## Architecture Summary (Agreed Design)

### Storage Layers

```
PostgreSQL
  files_data          — file ownership, hash, ingestion status, embedding model
  document_parents    — parent chunk text, page range, element types, is_committed flag
  ingestion_jobs      — per-stage progress, retry tracking, error classification

ChromaDB
  child_chunks        — child embeddings + full per-chunk metadata (primary retrieval collection)
  document_summaries  — document-level summary embeddings (routing / coarse retrieval)
```

### Pipeline Stages (Target: 7 stages)

```
Stage 0  Pre-Validation       file size, MIME whitelist, concurrent-job guard
Stage 1  Structured Parse     unstructured with per-element iteration; CSV/XLSX via pandas
Stage 2  Hash + Dedup         SHA-256 streaming hash; global dedup by (user_id, file_hash)
Stage 3  Parent Chunking      RecursiveCharacterTextSplitter → SemanticChunker (Phase 1.5)
Stage 4  Child Chunking       per-parent child split; table boundary enforcement
Stage 5  Embed + Upsert       streaming generator (one parent at a time); full metadata
Stage 6  Summarization        windowed map-reduce for long docs; embed + upsert
Stage 7  Finalization         status update, embedding_model write, lock release
```

### Target ChromaDB Child Chunk Metadata Schema

```
file_id        int     — links to files_data.id
user_id        int     — multi-tenant filtering (CRITICAL, currently missing)
parent_id      str     — SHA-256 of file_hash:chunk_index (links to document_parents.id)
child_index    int     — position within parent
chunk_index    int     — parent position within document
page_start     int     — first page this chunk covers (currently always NULL)
page_end       int     — last page this chunk covers (currently always NULL)
element_types  str     — comma-separated: "NarrativeText,Table" (currently missing from Chroma)
file_type      str     — MIME type
language       str     — ISO 639-1 code (currently always NULL)
file_hash      str     — global dedup cross-reference
filename       str     — display convenience
```

---

## Phase 0 — Foundation Hardening

**Goal:** Fix all critical/high-severity gaps that block correctness and data integrity. No new features. No retrieval work begins until Phase 0 is complete.

**Why this phase first:** Gaps G1, G3, G4, and G8 are data integrity issues — existing documents are missing multi-tenant isolation, and deleted files leave orphaned vectors. These cannot be patched later without a full re-ingestion of all existing documents.

---

### P0.1 — Add `user_id` to ChromaDB Metadata
**Status:** `[x]`  
**Fixes:** G1  
**Why:** Without `user_id` in ChromaDB metadata, the retrieval layer cannot filter by user — every query returns results from all users' documents. This is a data isolation failure. Adding it after documents are already embedded requires re-ingesting all of them.  
**Where:**
- `backend/tasks/ingestion_tasks.py` — `_stage_embed_upsert()`: add `"user_id": file_record.user_id` to `child_metas`
- `backend/tasks/ingestion_tasks.py` — `_stage_summarize()`: add `"user_id"` to summary metadata; requires passing `user_id` as a parameter
- `backend/tasks/ingestion_tasks.py` — `run_ingestion()`: pass `file_record.user_id` into both stage functions
- `backend/core/chroma.py` — no schema change needed; ChromaDB metadata is schemaless

**Acceptance criteria:**
- Every document upserted to `child_chunks` has `metadata["user_id"]` set to the owning user's integer ID
- Every document upserted to `document_summaries` has `metadata["user_id"]` set
- Verified by querying ChromaDB after a test upload and inspecting the metadata dict

---

### P0.2 — ChromaDB Vector Cleanup on File Delete
**Status:** `[x]`  
**Fixes:** G8  
**Why:** Currently `DELETE /files/{id}` removes the file from disk and from `files_data` (which cascades to `document_parents` and `ingestion_jobs`), but ChromaDB vectors are never touched. Every deleted file leaves orphaned child chunk and summary vectors in ChromaDB forever. This accumulates silently and costs money on every query that returns irrelevant results.  
**Where:**
- `backend/services/files.py` — `delete_file()`: before `db.delete(record)`, call `collection.delete(where={"file_id": file_id})` on both `child_chunks` and `document_summaries` collections
- `backend/core/chroma.py` — add helper `delete_vectors_for_file(file_id: int)` that issues the delete on both collections

**Acceptance criteria:**
- After `DELETE /files/{id}`, a ChromaDB `get(where={"file_id": id})` returns empty results for both collections

---

### P0.3 — Global Dedup by `(user_id, file_hash)`
**Status:** `[x]`  
**Fixes:** G3  
**Why:** The current dedup check is `db.query(DocumentParent).filter(DocumentParent.file_id == file_id).first()`. This only catches re-submission of the same `file_id`, not the same file uploaded twice under a different name. A user can upload the same 50-page PDF with a different filename and pay full embedding cost twice. The SHA-256 hash is already computed at Stage 2 — it just isn't used as the dedup key.  
**Where:**
- `backend/tasks/ingestion_tasks.py` — Stage 2: replace the `DocumentParent` existence check with a query on `files_data` for any other record with the same `(user_id, file_hash)` that is not the current `file_id` and has status COMPLETE
- `backend/alembic/versions/` — new migration: add `UNIQUE INDEX ix_files_data_user_file_hash ON files_data (user_id, file_hash)`; this is a partial unique constraint to avoid blocking on NULL hashes before ingestion runs

**Acceptance criteria:**
- Uploading the same file twice (different filenames, same user) results in the second ingestion job completing immediately with `deduped=True`
- The second `files_data` row exists (for UI listing) but no new vectors are written to ChromaDB

---

### P0.4 — Concurrent Ingestion Job Guard
**Status:** `[x]`  
**Fixes:** G4  
**Why:** If the API is called twice rapidly for the same file (e.g., network retry from the client), two `IngestionJob` rows are created and two Celery workers race to write the same vectors. ChromaDB `upsert` is idempotent by ID so vectors are not duplicated, but PostgreSQL writes and status updates from two workers interleave non-deterministically, leaving the job in an inconsistent state.  
**Where:**
- `backend/alembic/versions/` — new migration: `CREATE UNIQUE INDEX ix_ingestion_jobs_one_active_per_file ON ingestion_jobs (file_id) WHERE status NOT IN ('COMPLETE', 'FAILED_PERMANENT')`
- `backend/services/files.py` — `upload_files()`: before creating a new `IngestionJob`, query for any existing non-terminal job for this `file_id`; if found, return the existing record without dispatching a second task

**Acceptance criteria:**
- Calling the upload endpoint twice for the same file in quick succession creates exactly one active `IngestionJob`

---

### P0.5 — Scanned PDF Detection
**Status:** `[x]`  
**Fixes:** G5  
**Why:** A scanned PDF has no extractable text — `unstructured` returns empty or near-empty elements in `"fast"` mode. The current pipeline does not check text yield and will ingest the document as a near-empty vector (`""` or a few whitespace characters). This produces noise vectors in the retrieval collection that degrade retrieval quality for every query.  
**Where:**
- `backend/tasks/ingestion_tasks.py` — after `_stage_parse()` returns, compute `text_density = len(raw_text.strip()) / max(file_path.stat().st_size, 1)`. If the file is > 50 KB and `text_density < 0.001` (configurable), call `_fail_permanent()` with `error_type="LIKELY_SCANNED_PDF"` and a user-readable message.
- `backend/core/config.py` — add `scanned_pdf_text_density_threshold: float` setting

**Acceptance criteria:**
- A scanned PDF (or any near-empty parsed document) results in `IngestionJob.status = "FAILED_PERMANENT"` and `error_type = "LIKELY_SCANNED_PDF"`
- No vectors are written to ChromaDB for the document

---

### P0.6 — Pre-Validation Stage (Stage 0)
**Status:** `[x]`  
**Fixes:** G2  
**Why:** Currently, a 300 MB file is written to disk, a database row is created, and a Celery task is dispatched before any size check happens. The size check occurs inside the task after the file has already occupied worker memory during parsing. Validation must happen at the API layer before the file is even saved to disk.  
**Where:**
- `backend/api/routers/file_handling/files.py` — `upload_file()`: before calling `files.upload_files()`, check `file.size` (or read the first chunk to compute size) against `settings.max_file_size_mb`; reject with HTTP 413 if exceeded
- `backend/services/files.py` — `upload_files()`: validate `file.content_type` against a whitelist of accepted MIME types; reject with HTTP 415 if not in the list
- `backend/core/config.py` — add `allowed_mime_types: list[str]` setting

**Accepted MIME types:**
```
application/pdf
application/vnd.openxmlformats-officedocument.wordprocessingml.document
application/msword
text/plain
text/csv
application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
application/vnd.ms-excel
```

**Acceptance criteria:**
- Uploading a file above `MAX_FILE_SIZE_MB` returns HTTP 413 with a clear message before any disk write
- Uploading an unsupported file type returns HTTP 415

---

## Phase 1 — Metadata Enrichment & Pipeline Correctness

**Goal:** Populate all metadata fields that the retrieval layer will need. Fix the partial-write bug. Add memory-safe streaming. Improve summarization for long documents.

**Why this phase second:** Phase 0 ensures no more corrupt data enters the system. Phase 1 makes the data that does enter rich enough to support every planned retrieval strategy without re-ingestion.

**Prerequisite:** All Phase 0 items complete.

---

### P1.1 — Per-Chunk `page_start` / `page_end` Population
**Status:** `[x]`  
**Fixes:** G6  
**Why:** The `page_start` and `page_end` columns exist in `document_parents` and the Alembic migration is already applied, but they are never written. Without them, page-level filtering ("show me what's on page 12") is impossible at retrieval time. This requires refactoring Stage 1 to return element-level data rather than a single concatenated string.  
**Where:**
- `backend/tasks/ingestion_tasks.py` — `_stage_parse()`: instead of returning `raw_text: str`, return a list of `ParsedElement(text, page_number, element_type)` objects
- `backend/tasks/ingestion_tasks.py` — `_stage_parent_chunk()`: accept `list[ParsedElement]`; after splitting, map each parent chunk to the page range of the elements it contains
- `backend/tasks/ingestion_tasks.py` — `_stage_embed_upsert()`: write `page_start` and `page_end` to `DocumentParent` row and include them in ChromaDB child chunk metadata

**Acceptance criteria:**
- After ingesting a multi-page PDF, `document_parents.page_start` and `page_end` are non-NULL for every row
- ChromaDB child chunk metadata contains `page_start` and `page_end` as integers

---

### P1.2 — Per-Chunk `element_types` in ChromaDB Metadata
**Status:** `[x]`  
**Fixes:** G7  
**Why:** `element_types` is currently a PostgreSQL array on `document_parents` at the document level — it is never written to individual child chunk metadata in ChromaDB. At retrieval time, there is no way to filter for only narrative text or only table content. ChromaDB metadata values must be flat strings; the array will be serialized as a comma-separated string.  
**Where:**
- Builds on P1.1 refactor — element type is already tracked per `ParsedElement`
- `backend/tasks/ingestion_tasks.py` — `_stage_parent_chunk()`: collect unique element types from elements within each parent chunk; pass as comma-separated string
- `backend/tasks/ingestion_tasks.py` — `_stage_embed_upsert()`: add `"element_types": "NarrativeText,Table"` to `child_metas`

**Acceptance criteria:**
- ChromaDB child chunk metadata contains `element_types` as a non-empty comma-separated string for every chunk

---

### P1.3 — Language Detection
**Status:** `[x]`  
**Fixes:** G13  
**Why:** `langdetect` is already installed. The `language` column exists in `files_data`. Language is simply never detected. Without it, future language-aware retrieval (e.g., only query English documents, or use a multilingual embedding model for non-English content) is impossible.  
**Where:**
- `backend/tasks/ingestion_tasks.py` — Stage 2 (after hash): `from langdetect import detect; language = detect(raw_text[:2000])`; write to `file_record.language` and include `"language"` in ChromaDB metadata via P1.1 refactor
- Wrap in `try/except LangDetectException` — if detection fails, default to `"unknown"`

**Acceptance criteria:**
- `files_data.language` is populated (e.g., `"en"`) after ingestion
- ChromaDB child chunk metadata contains `"language"` for every chunk

---

### P1.4 — Streaming Generator Pattern + `is_committed` Flag
**Status:** `[x]`  
**Fixes:** G9, G11  
**Why (G11 — memory):** `_stage_child_chunk()` currently returns `list[tuple[str, list[str]]]` — the entire document's parent and child texts in one list. For a 500-page document this can be thousands of strings held simultaneously in a single worker's heap. The fix is to yield one parent at a time.  
**Why (G9 — partial write bug):** If `_stage_embed_upsert()` crashes halfway through, some `DocumentParent` rows exist in PostgreSQL but their children are absent from ChromaDB. The Stage 2 dedup check finds the `DocumentParent` rows and incorrectly declares the document COMPLETE. An `is_committed` flag on each `DocumentParent` row marks which parents have had their children successfully upserted to ChromaDB. On retry, Stage 5 skips committed parents and resumes from the first uncommitted one.  
**Where:**
- `backend/alembic/versions/` — new migration: add `is_committed BOOLEAN NOT NULL DEFAULT FALSE` to `document_parents`
- `backend/models/ingestion.py` — add `is_committed` column to `DocumentParent`
- `backend/tasks/ingestion_tasks.py` — `_stage_child_chunk()`: convert to a generator that yields `(ParentChunk, list[str])` one at a time
- `backend/tasks/ingestion_tasks.py` — `_stage_embed_upsert()`: process one parent at a time; after successful ChromaDB upsert for a parent, set `is_committed=True` on its `DocumentParent` row and commit; on retry, skip rows where `is_committed=True`

**Acceptance criteria:**
- Ingesting a large document does not require holding all chunks in memory at once
- If Stage 5 is interrupted mid-document, retry resumes from the last uncommitted parent and the document reaches COMPLETE status

---

### P1.5 — `embedding_model` Column Tracking
**Status:** `[x]`  
**Fixes:** G10  
**Why:** When the embedding model is upgraded (e.g., from `text-embedding-3-small` to `text-embedding-3-large`), there is no way to identify which documents are already on the new model and which need re-embedding. Without this column, the only option is to re-embed everything — expensive and time-consuming.  
**Where:**
- `backend/alembic/versions/` — new migration: add `embedding_model VARCHAR(100)` to both `files_data` and `document_parents`
- `backend/models/file_model.py` — add `embedding_model` column to `FileRecord`
- `backend/models/ingestion.py` — add `embedding_model` column to `DocumentParent`
- `backend/tasks/ingestion_tasks.py` — Stage 7 (finalization): write `settings.openai_embedding_model` to `file_record.embedding_model` and to each `DocumentParent.embedding_model`

**Acceptance criteria:**
- After ingestion, `files_data.embedding_model` contains the model name (e.g., `"text-embedding-3-small"`)

---

### P1.6 — Map-Reduce Summarization for Long Documents
**Status:** `[x]`  
**Fixes:** G12  
**Why:** The current summarizer passes `raw_text[:12_000]` to the LLM. For a 500-page document this covers roughly the first 2% of the content. The generated summary describes only the introduction and is useless for retrieval routing. A windowed map-reduce approach summarizes the document in sections and then combines the section summaries into a final document summary.  
**Where:**
- `backend/tasks/ingestion_tasks.py` — `_stage_summarize()`: split `raw_text` into windows of `settings.summary_window_size` characters (default 10,000); summarize each window with a short prompt ("summarize this section in 2 sentences"); combine section summaries into a final summary with a second LLM call
- `backend/core/config.py` — add `summary_window_size: int` and `summary_short_doc_threshold: int` (documents below threshold use the existing single-call path)

**Acceptance criteria:**
- A 100-page PDF produces a summary that accurately describes the full document, not just the first few pages

---

## Phase 1.5 — Parser & Chunker Upgrades

**Goal:** Replace the weakest parsing and chunking components with production-quality alternatives. These are isolated module swaps — they do not change the pipeline stage structure or database schema (except where noted).

**Why this phase third:** Phase 0 and Phase 1 fix correctness and data integrity. Phase 1.5 improves the quality of what enters the pipeline. SemanticChunker in particular will produce measurably better retrieval results but requires Phase 1 metadata enrichment to be in place first (chunk boundaries are derived from parsed elements).

**Prerequisite:** All Phase 0 and Phase 1 items complete.

---

### P1.5.1 — SemanticChunker Integration
**Status:** `[x]`  
**Why:** `RecursiveCharacterTextSplitter` splits by character count with no awareness of topic boundaries. A paragraph about one topic and the next paragraph about a different topic may land in the same chunk — or the same topic may be split across two chunks. `SemanticChunker` (from `langchain-experimental`) uses embedding similarity between consecutive sentences to find natural topic boundary points, producing chunks that align with semantic shifts. This directly improves retrieval precision.  
**Where:**
- `backend/tasks/ingestion_tasks.py` — `_stage_parent_chunk()`: add a config flag `settings.use_semantic_chunker: bool`; if True, use `SemanticChunker(embeddings=OpenAIEmbeddings(...), breakpoint_threshold_type="percentile")` instead of `RecursiveCharacterTextSplitter`
- `backend/core/config.py` — add `use_semantic_chunker: bool = False` (feature flag — disabled by default, enabled after validation)

**Note:** `SemanticChunker` uses embedding calls during ingestion (one per sentence boundary candidate). This increases ingestion cost slightly. Enable only after validating retrieval quality improvement on a representative document set.

**Acceptance criteria:**
- With `USE_SEMANTIC_CHUNKER=true`, parent chunks align with topic boundaries rather than character counts
- Pipeline still completes successfully; per-chunk page range and element type metadata are still populated

---

### P1.5.2 — CSV / XLSX Structured Parsing via Pandas
**Status:** `[x]`  
**Fixes:** G14  
**Why:** `unstructured` extracts CSV/XLSX as raw text, discarding column structure. A row becomes a space-separated string of values with no column headers — indistinguishable from prose. `pandas` preserves the tabular structure, enabling row-group chunking (e.g., 50 rows per parent chunk as a Markdown table) that produces coherent, filterable chunks.  
**Where:**
- `backend/tasks/ingestion_tasks.py` — `_stage_parse()`: detect `file_type in {"text/csv", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}`; branch to a pandas-based parse path
- Pandas path: read CSV/XLSX with header validation; serialize each row group as Markdown using `df.to_markdown()`; yield as `ParsedElement(text=markdown_table, page_number=1, element_type="Table")`
- Empty sheets detected and skipped; `pandas.errors.ParserError` classified as `FAILED_PERMANENT`

**Acceptance criteria:**
- After ingesting a CSV, each parent chunk contains a Markdown table with column headers
- Empty or malformed CSVs result in `FAILED_PERMANENT` with a clear error type

---

### P1.5.3 — Table Boundary Enforcement During Chunking
**Status:** `[x]`  
**Fixes:** G16  
**Why:** A table split mid-row across two parent chunks is meaningless — row context requires the header to be present. The chunker must treat each table element as an atomic unit that is never split across chunk boundaries.  
**Where:**
- `backend/tasks/ingestion_tasks.py` — `_stage_parent_chunk()`: before applying the text splitter, identify `ParsedElement` items with `element_type="Table"`; if a table's text is below `parent_chunk_size`, inject it as an atomic chunk; if it exceeds `parent_chunk_size`, keep it as a single oversized parent chunk (do not split) and log a warning
- Child chunker: tables that are a single parent receive a single child (no further splitting)

**Acceptance criteria:**
- After ingesting a PDF with tables, no child chunk contains a partial table row without its corresponding header

---

### P1.5.4 — `chardet` Encoding Detection for TXT Files
**Status:** `[x]`  
**Fixes:** G15  
**Why:** Legacy TXT files encoded in Windows-1252, ISO-8859-1, or Latin-1 produce `UnicodeDecodeError` or garbled characters when read as UTF-8. `chardet` is already installed. Detecting encoding before parsing and passing it as a hint to `unstructured` prevents silent data corruption.  
**Where:**
- `backend/tasks/ingestion_tasks.py` — `_stage_parse()`: for `file_type="text/plain"`, read the first 10 KB with `chardet.detect()`; pass the detected encoding to `partition(filename=..., encoding=detected_encoding)`
- If confidence < 0.7, default to UTF-8 and log a warning

**Acceptance criteria:**
- A Windows-1252 encoded TXT file is parsed without garbled characters or `UnicodeDecodeError`

---

## Phase 2 — Retrieval Layer Design & Implementation

**Goal:** Design and implement the query-time retrieval pipeline using the enriched vectors and metadata produced by Phases 0–1.5.

**Why this phase last:** Retrieval quality is entirely dependent on ingestion quality. Beginning retrieval design before ingestion metadata is correct and complete leads to retrieval strategies that are constrained by missing data. Phases 0–1.5 ensure the ingestion data is production-ready; Phase 2 then has full flexibility.

**Prerequisite:** All Phase 0, Phase 1, and Phase 1.5 items complete. At least 10 representative documents ingested and their ChromaDB metadata verified.

---

### P2.1 — Retrieval Layer Architecture Design
**Status:** `[x]`  
**Why:** This is a separate design exercise. The retrieval layer will use the enriched metadata (user_id, page_start, element_types, language, parent_id) to implement one or more of the following strategies, selected based on query type. To be designed in a dedicated session.

**Planned retrieval strategies (to be selected and implemented):**
- Dense vector retrieval (baseline — child chunk similarity search)
- Parent-child retrieval (retrieve child → fetch parent from PostgreSQL for answer synthesis)
- Metadata filtering (user_id scope, page range, element type, language)
- Multi-vector retrieval (child chunks + document summary routing)
- Reranking (parent text as context window for cross-encoder reranking)
- Contextual compression (LLM-based compression of retrieved parent to relevant span)
- Hybrid retrieval (dense + BM25 keyword index — requires P2.3)

---

### P2.2 — Proposition Extraction Pipeline (Phase 2 addition)
**Status:** `[x]`  
**Why:** Proposition extraction decomposes parent chunks into atomic, self-contained factual statements. Each proposition is embedded separately. At retrieval time, a question like "what year was X founded?" matches a proposition vector more precisely than a full paragraph chunk. This was deferred from Phase 1 because LLM hallucination during extraction is a silent failure mode that requires validation tooling before production use.  
**Where:** New ChromaDB collection `propositions`; new Stage 6.5 in the ingestion pipeline (additive — no existing stages modified).

---

### P2.3 — BM25 Hybrid Retrieval Index
**Status:** `[x]`  
**Why:** Dense vector retrieval fails on exact keyword matches (product codes, model numbers, proper nouns). BM25 keyword retrieval is complementary — it excels exactly where dense retrieval is weak. Hybrid retrieval combines both scores (Reciprocal Rank Fusion or weighted sum). `rank-bm25` is already installed.  
**Where:** Either a PostgreSQL full-text index on `document_parents.content` (simpler, already in the same DB) or a dedicated Elasticsearch index (more scalable, separate infrastructure). Decision to be made at Phase 2 design time.

---

## Migration Checklist

Migrations that need to be created in `backend/alembic/versions/`:

| # | Migration | Phase | Status |
|---|---|---|---|
| M1 | Add `UNIQUE INDEX` on `files_data(user_id, file_hash)` | Phase 0 | `[x]` `0007_add_dedup_and_job_guard_indexes.py` |
| M2 | Add partial unique index on `ingestion_jobs(file_id) WHERE status NOT IN ('COMPLETE','FAILED_PERMANENT')` | Phase 0 | `[x]` `0007_add_dedup_and_job_guard_indexes.py` |
| M3 | Add `is_committed BOOLEAN NOT NULL DEFAULT FALSE` to `document_parents` | Phase 1 | `[x]` `0008_add_is_committed_and_embedding_model.py` |
| M4 | Add `embedding_model VARCHAR(100)` to `files_data` | Phase 1 | `[x]` `0008_add_is_committed_and_embedding_model.py` |
| M5 | Add `embedding_model VARCHAR(100)` to `document_parents` | Phase 1 | `[x]` `0008_add_is_committed_and_embedding_model.py` |
| M6 | Add GIN FTS index on `document_parents.content` | Phase 2 | `[x]` `0009_add_fts_index.py` |

---

## Dependency Status

All required dependencies are already in `requirements.txt` and installed:

| Package | Purpose | Used? |
|---|---|---|
| `langchain-experimental` | SemanticChunker | `[x]` Wired behind `USE_SEMANTIC_CHUNKER` flag (Phase 1.5) |
| `langdetect` | Language detection | `[x]` Wired in Stage 2 (Phase 1) |
| `chardet` | TXT encoding detection | `[x]` Wired in `_stage_parse()` for `text/plain` (Phase 1.5) |
| `python-magic` | MIME validation | `[x]` Wired via `settings.allowed_mime_types` in router (Phase 0) |
| `rank-bm25` | BM25 hybrid retrieval | `[x]` PostgreSQL FTS used instead (simpler, same DB); `rank-bm25` not needed |
| `pandas` / `openpyxl` | CSV/XLSX structured parse | `[x]` Wired in `_parse_tabular()` (Phase 1.5) |
| `pytesseract` | OCR (scanned PDFs) | `[ ]` Future / optional |

---

## Decision Log

| Decision | Reason | Alternatives Rejected |
|---|---|---|
| Two ChromaDB collections (child_chunks + document_summaries) | Separates precision retrieval units from routing signals; avoids mixing embedding spaces | Single collection (confounds retrieval types), three collections (premature before proposition extraction is validated) |
| `RecursiveCharacterTextSplitter` for Phase 1 parent chunking | Deterministic, fast, no extra API calls during ingestion, well-understood failure modes | `SemanticChunker` deferred to Phase 1.5 — adds embedding cost per-ingestion; validate quality first |
| `text-embedding-3-small` as default model | Cost-effective; 1536 dimensions; strong multilingual support | `text-embedding-3-large` (higher cost, marginal quality gain for this domain); open-source models (require self-hosted inference) |
| SHA-256 deterministic IDs for all ChromaDB entries | Idempotent upsert on retry; no vector duplication on worker crash and restart | UUID-based IDs (non-deterministic; retry creates duplicate vectors) |
| Proposition extraction deferred to Phase 2 | LLM hallucination during extraction is a silent quality failure; requires validation tooling | Implementing in Phase 1 (risks polluting the vector space with hallucinated propositions before we can detect them) |
| pandas for CSV/XLSX instead of unstructured | Preserves column structure; enables Markdown table serialization; headers are retained in every chunk | unstructured (destroys structure; row becomes space-separated values with no column context) |
| PostgreSQL for parent storage (not ChromaDB) | Parent chunks are large text blobs; ChromaDB is not optimized for large document storage; PostgreSQL supports efficient `WHERE parent_id = ?` lookups | Storing parents in ChromaDB as a second collection (expensive full collection scan to retrieve one parent) |

---

## Session Handoff Notes

When resuming work in a new session:

1. Read this file first
2. Check the `[x]` / `[ ]` status for each item in the current phase
3. Verify the current phase's items are actually complete by reading the relevant source files — do not trust the checklist alone if time has passed
4. Do not begin Phase N+1 work until all Phase N items are checked off
5. Update this file's status markers as work is completed
6. The branch is `RAG-Implementation`; the main branch is `main`
