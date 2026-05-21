"""Shared fixtures. All external services (ChromaDB, Redis, Celery) are mocked."""

import os

# Set required env vars before any module-level settings = Settings() call runs.
# These must be at the top of conftest.py (not inside fixtures) so they are in place
# before pytest imports the test modules, which trigger config.py's module-level code.
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-tests-only")
os.environ.setdefault("DATABASE", "postgresql://testuser:testpass@localhost/testdb")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-dummy-key")
os.environ.setdefault("ADMIN_USERNAME", "testadmin")
os.environ.setdefault("ADMIN_PASSWORD", "testadminpass")

import pytest


@pytest.fixture(autouse=False)
def override_settings(monkeypatch):
    # patches a settings field for the test then restores it, e.g. override_settings("chroma_host", "x")
    from core.config import settings
    originals: dict = {}

    def _set(field: str, value):
        if field not in originals:
            originals[field] = getattr(settings, field)
        setattr(settings, field, value)

    yield _set

    for field, original_value in originals.items():
        setattr(settings, field, original_value)
