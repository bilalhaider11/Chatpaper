# Chatpaper — Claude Rules

---

## Product Requirements (Always Verify Against These)

Chatpaper is a document-chat SaaS. Every feature, fix, and test must satisfy all four of these invariants:

1. **Upload & ingest** — Authenticated users can upload documents (PDF, DOCX, TXT, CSV, XLSX). Each upload is processed asynchronously through a 6-stage ingestion pipeline and stored in ChromaDB + PostgreSQL.
2. **Per-document chat** — Every uploaded document automatically gets its own conversation (`conversation_type = "per_file"`). A per-file conversation can only retrieve context from that single document. One document = one active per-file conversation.
3. **Global chat room** — Users can also open a global conversation (`conversation_type = "global"`) that retrieves context across all their documents simultaneously. Multiple global conversations are allowed.
4. **Strict data isolation** — A user can only see, query, download, and chat about their own documents and conversations. No cross-user data access, ever. Violations must return 404 (not 403) to avoid leaking existence information.

---

## Core Principles

### KISS (Keep It Simple, Stupid)
- Prefer the simplest solution that correctly solves the problem.
- Avoid over-engineering, unnecessary abstractions, or premature generalization.
- If something can be done in 10 lines instead of 50, do it in 10.

### DRY (Don't Repeat Yourself)
- Extract shared logic into a single place — utility function, base class, or shared module.
- Before writing new code, check if similar logic already exists in the codebase.
- Duplication is acceptable only when the two pieces of logic are genuinely independent and likely to diverge.

## Code Quality

### Comments
- Write comments only when the **why** is non-obvious — hidden constraints, subtle invariants, workarounds for known bugs.
- Comments should read like a developer left a note for a teammate, not auto-generated documentation.
- Bad: `# Increment counter by 1` — Good: `# offset by 1 because the API returns 0-indexed but the UI expects 1-indexed`
- No multi-line docstring blocks unless the function is a public API boundary.

### Modern Techniques
- Use up-to-date language features and idioms (Python 3.10+ match statements, walrus operator where it aids clarity, dataclasses/Pydantic over raw dicts for structured data, etc.).
- Prefer async/await patterns consistently — don't mix sync and async code paths without good reason.
- Use type hints throughout; avoid `Any` unless truly unavoidable.

## Planning Before Implementation

For every non-trivial change, produce this full plan **before writing a single line of code** and
**wait for explicit user approval** before implementing:

1. **Problem statement** — one paragraph: what needs to be solved, why, and what the success
   condition looks like.

2. **Approaches** — at least 2–3 distinct options. For each: name, one-sentence description,
   key trade-offs.

3. **Ranking table** — score each option 1–10 on: simplicity, correctness, maintainability,
   fit with existing codebase. State the winner and why.

4. **Step-by-step implementation plan** — for the winning approach only. Each step must
   include: file path, what changes, and why.

5. **Edge cases & failure modes table** — columns: scenario | risk | mitigation. Cover at
   minimum: concurrent operations, missing/deleted dependencies, pre-existing data
   (migration safety), security boundaries, and partial failure states.

6. **Test scenarios table** — columns: # | what to test | expected result. Must include
   happy path, each edge case from step 5, and at least one security/tenancy check.

7. **Overall plan rating** — score out of 10 with a one-sentence justification and any
   remaining risk.

If any step reveals a flaw in the chosen approach, return to step 2 before continuing.
Do not implement anything until the user explicitly approves the plan.

## General Guardrails
- Match the scope of changes to what was actually requested — no opportunistic refactors or unrelated cleanup.
- No dead code, commented-out code blocks, or `TODO` stubs left behind unless explicitly agreed.
- Security-first: validate at system boundaries (user input, external APIs); never trust raw input downstream.

---

## Backend Rules (Python / FastAPI)

### Alembic Migrations
- **Never edit an existing migration file.** Once a migration has been committed, it is immutable — editing it breaks any environment that already ran it.
- Always generate new migrations with `alembic revision --autogenerate -m "<description>"`.
- Review the auto-generated migration before committing — autogenerate misses some things (e.g. server-side defaults, custom index types).

### Multi-Tenancy Enforcement
- Every database query and every ChromaDB query that touches user-owned data **must** include a `user_id` filter. No exceptions.
- When adding a new endpoint or service method, the first thing to verify is that all data access is scoped to the authenticated user.
- Cross-user resource access must return **404, not 403** — returning 403 reveals that the resource exists, which leaks information about other users' data.

### Configuration & Environment Variables
- All environment variables must be declared in `core/config.py` as fields on the Pydantic `Settings` class.
- Never call `os.environ` or `os.getenv` directly anywhere else in the codebase — always go through the `settings` singleton.
- Required secrets (e.g. `SECRET_KEY`, `DATABASE`) must use Pydantic validators to fail at startup if missing or empty, not silently at request time.

### Celery Task Idempotency
- Every Celery task must be safe to retry — assume any task can be interrupted mid-execution and re-queued.
- For operations that write partial state (e.g. ingestion stages), use a committed/uncommitted flag pattern (like `is_committed` on `document_parents`) so a retry can resume from the last safe checkpoint rather than re-doing or duplicating work.
- Clean up uncommitted partial writes on terminal failure — don't leave orphaned rows or vectors.

### Tests
- Every new service module or endpoint must have a corresponding test file under `backend/tests/`.
- Tests should cover the happy path and at least one failure/edge case per function.
- Do not mock the database in integration tests — use a real test database to catch migration and query issues that mocks would hide.

### Post-Implementation Verification (mandatory)
- After every non-trivial implementation, run the app and exercise the changed code paths end-to-end via the actual HTTP API before declaring the task complete.
- This means: start the server, send real requests, capture real responses — not just syntax-checking or running unit tests.
- If the server is already running, use it; do not restart it unless the change requires it.
- A task is **not done** until at least the happy path and one failure/edge case have been observed at the API surface.
