"""
Shared fixtures for all test phases.

External services (ChromaDB, Redis, Celery broker) are never contacted
during tests — every client is mocked at the boundary.
"""

import pytest


@pytest.fixture(autouse=False)
def override_settings(monkeypatch):
    """
    Yield a helper that lets individual tests patch settings fields
    for the duration of the test, then restore them automatically.

    Usage inside a test:
        def test_something(override_settings):
            override_settings("chroma_host", "myhost")
            ...
    """
    from core.config import settings
    originals: dict = {}

    def _set(field: str, value):
        if field not in originals:
            originals[field] = getattr(settings, field)
        setattr(settings, field, value)

    yield _set

    for field, original_value in originals.items():
        setattr(settings, field, original_value)
