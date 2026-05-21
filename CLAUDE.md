# Chatpaper — Claude Rules

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

For every non-trivial change, follow this process **before writing a single line of code**:

1. **Understand the problem** — restate what needs to be solved and why.
2. **Generate multiple solutions** — propose at least 2-3 distinct approaches.
3. **Rank the solutions** — evaluate each on simplicity, correctness, maintainability, and fit with the existing codebase.
4. **Stress-test the winner** — enumerate edge cases, failure modes, and interactions with other parts of the system.
5. **If a problem is found** — go back to step 2 with a new candidate; repeat until the plan is clean.
6. **Only then implement** — follow the agreed plan without scope creep.

Present the plan to the user and wait for approval before implementing.

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
