# Chatpaper — Security Audit Log

Full codebase security, reliability, and scalability audit. All 66 findings resolved across 4 audit rounds (2026-06-01 → 2026-06-02).
Legend: `[x]` fixed · `[-]` won't fix / accepted risk

---

## P0 — Crashes & Critical Security
*Must be fixed before any real user traffic.*

- [x] **P0-1 · Missing `chat_stream_ttl_seconds` in config**
  - File: `backend/services/chat_cache.py:165` references `settings.chat_stream_ttl_seconds`
  - Problem: Field not declared in `core/config.py` → `AttributeError` crash every time a stream chunk is appended and Redis is available. The entire Redis-backed chat path is broken.
  - Fix: Add `chat_stream_ttl_seconds: int = int(os.getenv("CHAT_STREAM_TTL_SECONDS", "300"))` to `Settings`.

- [x] **P0-2 · Google OAuth router never mounted**
  - File: `backend/api/router.py`
  - Problem: `google_auth` router is never `include_router`'d. `/api/auth/google-login` and the OAuth callback don't exist on the running server — Google login is silently dead.
  - Fix: Import and include the google_auth router in `api/router.py`.

- [x] **P0-3 · Google OAuth assigns every user the same hardcoded password**
  - File: `backend/api/routers/auth/google_auth.py:83` — `password="qwQW12!@"`
  - Problem: All Google OAuth users get this password stored as a bcrypt hash. Anyone who knows this constant (it's in the repo) can log in as any Google-authenticated user via the email/password endpoint. Complete auth bypass.
  - Fix: Generate a `secrets.token_urlsafe(32)` random password per user, or use a sentinel value that the password login rejects explicitly for OAuth accounts.

- [x] **P0-4 · `get_conversation_list` passes `db` as the `body` argument**
  - File: `backend/api/routers/conversation.py:148-152`
  - Problem: `create_conversation_list(current_user, db)` is called with only 2 args. The function signature is `(current_user, body: ConversationCreateRequest, db: Session)`. `db` is received as `body`, then `body.conversation_title` crashes with `AttributeError`.
  - Fix: Pass a proper `ConversationCreateRequest` as `body` and pass `db` as the third argument.

- [x] **P0-5 · `delete_conversation_list` calls a non-existent service function**
  - File: `backend/api/routers/conversation.py:181`
  - Problem: Calls `conversation_service.delete_conversation_list(list_id, db)` but `services/conversation.py` has no such function → `AttributeError` on every request to `DELETE /conversation/delete_list/{id}`.
  - Fix: Implement `delete_conversation_list` in `services/conversation.py` with an ownership check.

- [x] **P0-6 · `update_conversation_title` passes a `str` to a service expecting a Pydantic model**
  - File: `backend/api/routers/conversation.py:120` → `services/conversation.py:40`
  - Problem: Router extracts `title: str = Body(...)` and passes the raw string to the service, which calls `title.conversation_title` → `AttributeError`.
  - Fix: Either change the service to accept `str` directly, or change the router to pass a proper `ConversationListBase` object.

- [x] **P0-7 · IDOR: `get_conversation` ownership check commented out**
  - File: `backend/api/routers/conversation.py:171`
  - Problem: `#_get_owned_convo(db, chat_list_id, current_user)` — the check is commented out. Any authenticated user can read any other user's full chat history by guessing `chat_list_id`. Violates requirement #4.
  - Fix: Uncomment and restore the ownership check.

- [x] **P0-8 · IDOR: `delete_conversation_list` has no ownership check**
  - File: `backend/api/routers/conversation.py:175-181`
  - Problem: `current_user` is loaded but never compared against the conversation's `user_id`. Any user can delete any other user's conversation list.
  - Fix: Add `_get_owned_convo(db, list_id, current_user)` before the delete call.

---

## P1 — High Priority (Security & Production Reliability)

- [x] **P1-1 · JWT token exposed in URL (Google OAuth redirect)**
  - File: `backend/api/routers/auth/google_auth.py`
  - Fixed: `google_callback` now generates a `secrets.token_urlsafe(32)` code, stores the JWT in Redis under `oauth:code:{code}` with a 60 s TTL, and redirects to `?code=X`. Frontend POSTs to `POST /auth/exchange-token` which uses `GETDEL` (atomic read + delete) to return the JWT and prevent replay. 503 returned if Redis is unavailable.

- [x] **P1-2 · WebSocket `user_type` is fully client-controlled**
  - Files: `backend/schema/conversation.py`, `backend/api/routers/conversation.py`
  - Fixed: Removed `user_type` field from `ChatWsSendPayload`; hardcoded `"user"` at the `_handle_outgoing_message` call site in the WebSocket handler.

- [x] **P1-3 · `ConnectionManager` is single-process — broken under multi-worker deploy**
  - Files: `backend/core/websocket.py`, `backend/api/routers/conversation.py`
  - Fixed: `broadcast` now publishes to a Redis pub/sub channel (`chat:room:{id}`). Each WebSocket connection runs a background `_redis_listener` task that subscribes to its room channel and forwards messages locally. Includes retry-on-reconnect loop with 1 s backoff. Falls back to direct local send when Redis is unavailable.

- [x] **P1-4 · `InMemoryChatCache` fallback is not multi-process safe**
  - Files: `backend/core/config.py`, `backend/core/redis_client.py`
  - Fixed: Added `REQUIRE_REDIS` env var (default `false`). When `true`, `start_redis` raises `RuntimeError` at startup if Redis is unreachable, preventing silent in-memory fallback in multi-worker deploys.

- [x] **P1-5 · Race condition in Redis flush queue drain (TOCTOU)**
  - File: `backend/services/chat_cache.py`
  - Fixed: Replaced `lrange` + `delete` with an atomic Lua script (`_DRAIN_QUEUE_SCRIPT`) that reads and deletes in a single round-trip. Also removed stray `print()` debug statement.

- [x] **P1-6 · Alembic migration runs on every startup — race condition in multi-worker deploys**
  - Files: `backend/core/config.py`, `backend/core/main.py`
  - Fixed: Added `RUN_MIGRATIONS_ON_STARTUP` env var (default `true`). The `command.upgrade` call in `lifespan` is now guarded by this flag. Set to `false` in multi-worker production and run `alembic upgrade head` as a dedicated pre-start step.

- [x] **P1-7 · Synchronous SQLAlchemy blocks the event loop — no connection pool configured**
  - File: `backend/core/database.py`
  - Fixed: Added `pool_size=10, max_overflow=20, pool_timeout=30, pool_pre_ping=True` to `create_engine`. Full async migration (`create_async_engine`) deferred as follow-up.

- [x] **P1-8 · No rate limiting on auth or upload endpoints**
  - Files: `backend/core/limiter.py` (new), `backend/core/main.py`, `backend/api/routers/auth/auth.py`, `backend/api/routers/file_handling/files.py`
  - Fixed: Added `slowapi`. `POST /auth/login` limited to 5/min per IP; `POST /auth/users` to 3/min; `POST /files/upload` to 10/min. Limiter singleton lives in `core/limiter.py` to avoid circular imports.

---

## P2 — Architecture & Code Quality

- [x] **P2-1 · `_buffer` in `messaging.py` is populated but never drained**
  - File: `backend/services/messaging.py`
  - Problem: `_on_queue_message` (RabbitMQ consumer) adds messages to `_buffer`, but `flush_buffer_to_db` calls `drain_flush_queue()` which reads from Redis, not `_buffer`. Messages consumed from RabbitMQ land in a dead-end buffer and are never persisted.
  - Fix: Either drain `_buffer` inside `flush_buffer_to_db`, or remove the buffer entirely and rely solely on the Redis queue for persistence coordination.

- [x] **P2-2 · Duplicate `QueuedChatMessage` class definition**
  - Files: `backend/services/chat_cache.py:14` and `backend/services/messaging.py:30`
  - Problem: `messaging.py` imports `QueuedChatMessage` from `chat_cache` on line 15, then immediately shadows it with a new `@dataclass` definition on line 30. The import is dead code. Two definitions of the same class creates silent confusion.
  - Fix: Remove the duplicate definition from `messaging.py` and use the imported one.

- [x] **P2-3 · `print()` debug statement in production code**
  - File: `backend/services/chat_cache.py:162` — `print("key: ",key)`
  - Fixed: Removed during P1-5 work.

- [x] **P2-4 · Duplicate `get_db` import in conversation router**
  - File: `backend/api/routers/conversation.py` — imported twice (lines 8 and 19)
  - Fixed: Already resolved; single import present at line 12.

- [x] **P2-5 · ChromaDB collection handles not refreshed after disconnect**
  - File: `backend/core/chroma.py`
  - Problem: Collection handles are cached in module-level globals. If ChromaDB restarts, all subsequent queries raise errors with no recovery path — the app must be restarted manually.
  - Fix: Catch `chromadb` connection errors and re-fetch the collection (clear the cached handle and retry `get_or_create_collection`).

- [x] **P2-6 · Soft-deleted file reactivation doesn't verify disk file still exists**
  - File: `backend/services/files.py:108`
  - Problem: When a soft-deleted file hash is matched, the code reactivates the DB record and returns success, assuming "old disk copy is still present." If the file was manually cleaned from disk, the user gets a broken record pointing to a missing file.
  - Fix: Add a `disk_path.exists()` check before reactivation; if missing, fall through to the normal new-file upload path instead.

- [x] **P2-7 · LLM and embedder clients recreated on every request**
  - Files: `backend/services/retrieval.py:162` (`get_embedder()`), `backend/api/routers/chat.py:98` (`get_chat_llm()`)
  - Problem: A new client object is constructed on every HTTP request, including HTTP connection setup overhead.
  - Fix: Cache these as module-level singletons (same pattern as `get_chroma_client()`).

- [x] **P2-8 · Google OAuth callback route path is empty string `""`**
  - File: `backend/api/routers/auth/google_auth.py:50` — `@router.get("")`
  - Problem: When mounted, the callback route becomes `/api/auth` (ambiguous, clashes with the auth prefix root). `request.url_for("google_callback")` may also resolve incorrectly.
  - Fixed: Changed to `@router.get("/google-callback")` during P0-2/P0-3 work.

- [x] **P2-9 · Open user registration — no email verification**
  - File: `backend/api/routers/auth/auth.py:44`
  - Problem: `POST /api/auth/users` is publicly accessible with no email verification, invite code, or admin gate. Anyone can self-register unlimited accounts.
  - Fix: Add email verification (send a confirmation link) or make registration invite/admin-only before going to production.

- [x] **P2-10 · `SessionMiddleware` uses `https_only=False`**
  - File: `backend/core/main.py:37`
  - Problem: Session cookie is transmitted over plain HTTP in production, exposing it to network interception.
  - Fix: Set `https_only=True` for production; guard it behind a config flag (`settings.is_production`).

---

## Scalability Risks (No Bug Today, Breaks Under Load)

| # | Area | Problem | Fix | Status |
|---|---|---|---|---|
| S-1 | DB connection pool | `create_engine` with no pool settings | Added `pool_size=10, max_overflow=20, pool_timeout=30, pool_pre_ping=True` | Fixed (P1-7) |
| S-2 | Sync DB in async app | All DB queries block the event loop thread | Migrated to `AsyncSession` + `create_async_engine`; async embeddings + LLM calls | Fixed |
| S-3 | WebSocket fan-out | `ConnectionManager` in-process singleton breaks with >1 worker | Redis pub/sub cross-worker broadcast | Fixed (P1-3) |
| S-4 | In-memory chat cache | Pending messages lost across workers | `REQUIRE_REDIS` env flag; hard dep for multi-worker | Fixed (P1-4) |
| S-5 | Alembic on startup | Migration race on rolling deploys | `RUN_MIGRATIONS_ON_STARTUP` flag | Fixed (P1-6) |
| S-6 | No rate limiting | Auth brute-force, upload flooding | `slowapi` on login/register/upload | Fixed (P1-8) |
| S-7 | Redis drain TOCTOU | Occasional message loss under high write concurrency | Atomic Lua script drain | Fixed (P1-5) |
| S-8 | LLM/embedder re-init | Latency spike on every chat request | Module-level singleton + `lru_cache` | Fixed (P2-7) |
| S-9 | No conversation pagination | `GET /get_conversation_list` fetches all rows | `limit`/`offset` query params (default 50, max 500) | Fixed |

---

## Post-P0 Fixes (found during verification)

- [x] **V-1 · `delete_conversation_list` didn't deactivate associated file for per_file conversations**
  - File: `backend/services/conversation.py`
  - Problem: The new `delete_conversation_list` service function omitted the per_file file-deactivation logic present in `delete_conversation`. Deleting a per_file conversation left the FileRecord active with no conversation, causing orphaned files and 409 errors on re-upload.
  - Fixed: Added the same `per_file` file-deactivation block that exists in `delete_conversation`.

- [x] **V-2 · `get_conversation_list` auto-created a global conversation when user had orphaned files**
  - File: `backend/api/routers/conversation.py`
  - Problem: If a user had files but no active conversations, the endpoint silently created a `global` conversation. Per requirements, per_file conversations are owned by the upload flow; this fallback created the wrong type and imported an unused `get_file_by_user_id`.
  - Fixed: Removed the fallback — endpoint now returns `[]` when no conversations exist. Removed the unused import.

---

## Round-2 Findings (2026-06-01 — full codebase re-audit post all prior fixes)

### Security

- [x] **N-SEC-1 · `POST /conversation/conversation/{chat_id}` accepted arbitrary `user_type`**
  - Files: `backend/api/routers/conversation.py`, `backend/services/conversation.py`, `frontend/src/services/conversation_api.ts`
  - Problem: P1-2 hardened the WebSocket path but this HTTP direct-insert endpoint still used `ConversationResponse` as input, accepting any `user_type` string (e.g. `"system"`). Frontend function `postConversationChat` was exported but never called.
  - Fix: Removed the endpoint and `add_conversation` service function entirely; removed dead `postConversationChat` from the frontend.

- [x] **N-SEC-2 · Rate limiter IP key broken behind a reverse proxy**
  - Files: `backend/core/config.py`, `backend/core/main.py`
  - Problem: `slowapi` uses `request.client.host` as the rate-limit key. Behind nginx/ALB, all traffic has the same proxy IP, making all per-IP limits useless.
  - Fix: Added `TRUST_PROXY_HEADERS` env var (default `false`). When `true`, `ProxyHeadersMiddleware` is mounted so `request.client` is populated from `X-Forwarded-For`.

- [x] **N-SEC-3 · Google OAuth config fields typed as `str` but silently `None` if env vars not set**
  - File: `backend/core/config.py`
  - Problem: `google_client_id`, `google_client_secret`, `redirect_url`, `frontend_url` were declared `str` but defaulted to `None` via `os.getenv()`. Pydantic v2 stores `None` without error, so the app started with a broken OAuth client and an eventual `NoneType` crash at runtime.
  - Fix: Changed all four to `Optional[str] = None`. Added a startup validator that fails fast if only some of the four vars are set (partial config). Added a `501` guard in the `google-login` route. `google_auth.py` now only registers the OAuth client if both key and secret are present.

### Architecture / Reliability

- [x] **N-ARCH-1 · Sync file I/O blocked the event loop during upload**
  - File: `backend/services/files.py`
  - Problem: `shutil.copyfileobj` (write) and `_compute_file_hash` (read) were synchronous. For a 200 MB file this blocked the entire event loop for seconds, stalling all concurrent requests.
  - Fix: Replaced `_compute_file_hash` + inline write with `_save_and_hash`, a single function called via `asyncio.to_thread()` that writes and hashes in the thread pool.

- [x] **N-ARCH-2 · `ConnectionManager.broadcast` sent to `connections[0]` only in Redis fallback**
  - File: `backend/core/websocket.py`
  - Problem: The Redis-down fallback path sent messages to only the first WebSocket in the room. Multiple browser tabs silently missed all messages.
  - Fix: Changed to iterate `list(connections)` and send to every open socket, disconnecting any that raise.

- [x] **N-ARCH-3 · `get_conversations` hardcoded `.limit(25)` with no offset**
  - Files: `backend/services/conversation.py`, `backend/api/routers/conversation.py`
  - Problem: Users with more than 25 messages in a conversation could never retrieve older history.
  - Fix: Added `limit` (default 50, max 200) and `offset` query params, matching the conversation-list endpoint pattern.

- [x] **N-ARCH-4 · `get_current_user` hit the database on every authenticated request**
  - Files: `backend/core/auth.py`, `backend/services/auth.py`
  - Problem: Every request re-queried `users` by email even though the JWT already carries `id`, `email`, and `role`. Hot path under load.
  - Fix: Added a Redis user cache (`user:cache:{user_id}`, TTL = `ACCESS_TOKEN_EXPIRE_MINUTES * 60`). Cache miss falls through to DB and populates the cache. `update_user` and `delete_user` call `invalidate_user_cache` so stale entries are evicted immediately. Lazy import used in `services/auth.py` to avoid a circular import.

- [x] **N-ARCH-5 · Dead code**
  - Files: `backend/core/redis_client.py` (lines 1–23 commented-out sync client), `backend/services/files.py` (sync `get_file_by_user_id` — no callers since V-2)
  - Fix: Both deleted.

- [x] **N-ARCH-6 · `GET /files/` had no pagination**
  - File: `backend/api/routers/file_handling/files.py`
  - Problem: Returned all file records in one response. At scale (many files per user) this is a large payload.
  - Fix: Added `limit` (default 50, max 500) and `offset` query params.

- [x] **N-ARCH-7 · `_get_owned_convo` did not filter by `is_active`**
  - File: `backend/api/routers/conversation.py`
  - Problem: Soft-deleted conversations could still be renamed, queried, or "re-deleted" by their owner.
  - Fix: Added `ConversationList.is_active == True` to the `_get_owned_convo` query.

---

## Progress Summary

| Severity | Total | Fixed | Remaining |
|---|---|---|---|
| P0 (crash / critical security) | 8 | 8 | 0 |
| P1 (high security / reliability) | 8 | 8 | 0 |
| P2 (architecture / code quality) | 10 | 10 | 0 |
| Post-P0 verification fixes | 2 | 2 | 0 |
| Scalability risks | 9 | 9 | 0 |
| Round-2 security | 3 | 3 | 0 |
| Round-2 architecture / reliability | 7 | 7 | 0 |
| Round-3 findings | 17 | 17 | 0 |
| Round-4 findings | 2 | 2 | 0 |
| **Total** | **66** | **66** | **0** |

*Update the checkboxes and this table as issues are resolved.*

---

## Round-4 Findings (2026-06-02 — full codebase re-audit post Round-3 fixes)

- [x] **R4-1 · `hmac.compare_digest` short-circuit re-introduces timing oracle in admin login**
  - File: `backend/core/admin.py:41`
  - Problem: R3-H3 replaced `==` with `hmac.compare_digest`, but kept the `and` operator between the two calls. Python `and` short-circuits: if the username is wrong the password comparison never runs, so requests with a correct username take measurably longer — an attacker can confirm the correct username through timing before brute-forcing the password.
  - Fix: Always evaluate both comparisons independently (`username_ok = ...`, `password_ok = ...`), then `valid = username_ok and password_ok`.

- [x] **R4-2 · `FileUpload` dropzone configured `multiple: true` but discards all files except the first**
  - File: `frontend/src/components/fileUpload/FileUpload.tsx:68`
  - Problem: The dropzone allowed selecting/dropping multiple files, but `onDrop` silently took only `acceptedFiles[0]`. Users dropping multiple files got no error; the rest were quietly ignored.
  - Fix: Changed to `multiple: false` so the native file picker restricts selection to one file and the behaviour matches the implementation.

---

## Round-3 Findings (2026-06-02 — full codebase re-audit post Round-2 fixes)

### Critical Security

- [x] **R3-C1 · Path traversal in file upload**
  - File: `backend/services/files.py:50`
  - Problem: `f"{uuid4().hex}_{file.filename}"` was used directly as a path component. A filename like `../../etc/cron.d/evil` resolved the traversal outside `UPLOAD_DIR`; the uuid4 prefix did not protect against it.
  - Fix: `Path(file.filename).name` strips directory components; added `is_relative_to(UPLOAD_DIR)` assertion as a second guard.

- [x] **R3-C2 · WebSocket JWT exposed in server access logs via URL query parameter**
  - Files: `backend/api/routers/conversation.py`, `frontend/src/services/conversation_api.ts`, `frontend/src/hooks/useChatWebSocket.ts`
  - Problem: The JWT was passed as `?token=...` in the WebSocket upgrade URL. Every reverse proxy (nginx, ALB), uvicorn's access log, browser history, and Referer headers recorded the token in plain text.
  - Fix: Backend accepts the connection, then verifies a `{"action":"auth","token":"..."}` first message (10 s timeout). Frontend sends the token via `onopen`. Token no longer appears in any URL.

### High Priority

- [x] **R3-H1 · Deactivated user authenticated from stale Redis cache**
  - File: `backend/core/auth.py:103`
  - Problem: Cached `User` objects were returned without checking `is_active`. A deactivated user whose cache entry was not invalidated (Redis unavailable at deactivation time) could continue authenticating until the cache TTL expired.
  - Fix: Added `if not cached.is_active: raise credentials_exception` before returning the cached user.

- [x] **R3-H2 · Admin brute-force protection silently disabled during Redis outage**
  - File: `backend/core/admin.py`
  - Problem: The fail-counter check was guarded by `if redis is not None`, so unlimited login attempts were allowed when Redis was down.
  - Fix: Fail-closed — login returns `False` immediately when Redis is unavailable.

- [x] **R3-H3 · Admin password comparison not constant-time (timing oracle)**
  - File: `backend/core/admin.py:28`
  - Problem: `username == ... and password == ...` short-circuits on the first differing character, leaking how many leading characters are correct under timing analysis.
  - Fix: `hmac.compare_digest(username, ...) and hmac.compare_digest(password, ...)`.

- [x] **R3-H4 · `google_callback` leaked raw exception detail in HTTP 401 response**
  - File: `backend/api/routers/auth/google_auth.py:61`
  - Problem: `detail=f"Google authentication failed: {exc}"` exposed internal URLs, OAuth config, and downstream error messages to clients.
  - Fix: Static `detail="Google authentication failed."` — exception still logged internally.

- [x] **R3-H5 · Missing database indexes on high-frequency FK columns**
  - Files: `backend/models/conversation.py`, `backend/models/file_model.py`, migration `0012_add_fk_performance_indexes.py`
  - Problem: PostgreSQL does not auto-index FK columns. `conversation.chat_id`, `conversationlist.user_id`, `conversationlist.file_id`, and `files_data.user_id` were full-table scans — O(N) per user at scale.
  - Fix: Added `index=True` to all four columns; Alembic migration `0012` creates the indexes.

### Medium Priority

- [x] **R3-M1 · `ProxyHeadersMiddleware` trusted all upstream IPs — rate limiting bypassable**
  - Files: `backend/core/config.py`, `backend/core/main.py`
  - Problem: `trusted_hosts="*"` allowed any client to spoof `X-Forwarded-For`, defeating all slowapi per-IP rate limits.
  - Fix: Added `TRUSTED_PROXY_IPS` env var (default `"*"` for backward compat). Set to your LB IP(s) in production to prevent spoofing.

- [x] **R3-M2 · `_ASYNC_DATABASE_URL` conversion failed for `postgres://` and `psycopg2://` schemes**
  - File: `backend/core/database.py`
  - Problem: Only `postgresql://` was replaced. `postgres://` (Heroku, Railway, Render) and `postgresql+psycopg2://` were silently passed to asyncpg unchanged, crashing on the first async query.
  - Fix: Chain-replaces all three variants → `postgresql+asyncpg://`.

- [x] **R3-M3 · Admin lockout counter had non-atomic SETNX + EXPIRE + INCR race**
  - File: `backend/core/admin.py`
  - Problem: Three separate Redis commands allowed concurrent requests to both see `fails < 10` before either incremented, bypassing the lockout threshold under concurrent brute-force.
  - Fix: Single Lua script atomically increments and sets expiry only on the first call.

- [x] **R3-M4 · Alembic migration blocked the async event loop at startup**
  - File: `backend/core/main.py`
  - Problem: `command.upgrade(cfg, "head")` ran synchronously inside the async `lifespan`, blocking all uvicorn workers until migrations completed.
  - Fix: `await asyncio.to_thread(command.upgrade, cfg, "head")`.

- [x] **R3-M5 · `get_conversations` appended pending/stream messages on every paginated page**
  - File: `backend/services/conversation.py`
  - Problem: Unsaved pending messages and active streams were appended unconditionally regardless of `offset`, duplicating the "leading edge" on every page and producing unbounded response sizes under slow flush intervals.
  - Fix: Pending/stream messages are only appended when `offset == 0`.

- [x] **R3-M6 · Login.tsx signup button silently ran login instead (React state race)**
  - File: `frontend/src/pages/login/Login.tsx`
  - Problem: `setlogin_signup(true)` is an async state update; `handleSubmit` fired before re-render and read the stale `false` value, so clicking Signup always executed a login attempt instead.
  - Fix: Replaced `useState` with `useRef<"login" | "signup">` — the ref is written synchronously in `onClick` and read correctly inside the submit handler.

### Low Priority

- [x] **R3-L1 · Lua drain script sent full script body on every call (EVAL vs EVALSHA)**
  - File: `backend/services/chat_cache.py`
  - Problem: `redis_client.eval(...)` serializes the full Lua script over the wire on every drain invocation. Under high throughput this wastes bandwidth and Redis CPU.
  - Fix: Lazy `register_script()` on first use; subsequent calls use `EVALSHA` with automatic `EVAL` fallback.

- [x] **R3-L2 · `get_active_streams` used `SCAN` over full Redis keyspace**
  - File: `backend/services/chat_cache.py`
  - Problem: `scan_iter(match="chat:stream:{id}:*")` is O(N) over the entire Redis keyspace. Under many concurrent streams this caused measurable latency on every `get_conversations` call.
  - Fix: `append_stream_chunk` now also adds each stream key to a per-chat Redis `SET` (`chat:streamset:{id}`). `get_active_streams` uses `SMEMBERS` (O(1) per key) and cleans up dead members inline.

- [x] **R3-L3 · `InMemoryChatCache._streams` dict was unbounded**
  - File: `backend/services/chat_cache.py`
  - Problem: Streams were never evicted from the in-memory fallback dict. During a Redis outage under load the dict could grow until OOM.
  - Fix: Added `_MAX_IN_MEMORY_STREAMS = 500` cap with FIFO eviction of the oldest stream when the limit is reached.

- [x] **R3-L4 · `Content-Disposition` header allowed HTTP header injection**
  - File: `backend/api/routers/file_handling/files.py`
  - Problem: The original filename was injected directly into a response header. A filename containing `\r\n` would inject arbitrary HTTP response headers.
  - Fix: RFC 5987 encoding — `filename*=UTF-8''<percent-encoded>` via `urllib.parse.quote`.
