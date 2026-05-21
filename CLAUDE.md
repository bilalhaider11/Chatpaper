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
