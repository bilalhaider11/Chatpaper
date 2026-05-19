"""Shared fixtures. All external services (ChromaDB, Redis, Celery) are mocked."""

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
